"""Secao critica administrativa e o fluxo completo de escrita/reload.

Etapa 6 da Fase 7. Nada aqui e HTTP: nao ha rota, autenticacao, bind, porta,
schema de request nem handler. Este modulo compoe primitivos que ja existiam —
`ConfigFileStore` (Etapa 5), `RuntimeRegistry` (Etapa 2), o carregador validado
(`config/`) e o composition root (Etapa 4) — no unico ponto do processo onde
uma mudanca administrativa pode acontecer.

## Por que uma secao critica, e nao so `expected_revision`

Comparar `expected_revision` fora de uma secao critica nao controla nada: duas
requisicoes leem a mesma revision, ambas aprovam a comparacao, e a segunda
sobrescreve a primeira — que ja respondeu sucesso ao seu administrador. Por
isso a verificacao de adocao, a de `expected_revision`, a do digest, a do
limite de aposentados, a persistencia e o swap acontecem sob UM lock, um por
processo (D-052).

## A ordem dos onze passos (secao 7.4), e o que cada um evita

```text
 1. estado de adocao compativel   -> CONFIG_NOT_ADOPTED / CONFIG_ALREADY_ADOPTED
 2. expected_revision confere     -> REVISION_CONFLICT
 3. disco confere com o runtime   -> CONFIG_OUT_OF_SYNC
 4. nenhum aposentado em uso      -> RELOAD_BUSY
 5. aplicar a mudanca; validar    -> CONFIG_INVALID
 6. compilar e construir          -> CONFIG_RELOAD_ERROR
 7. conectar e verificar          -> CONFIG_RELOAD_ERROR
 8. persistir atomicamente        -> CONFIG_WRITE_ERROR
 9. fsync do diretorio            -> CONFIG_DURABILITY_ERROR
10. swap e atualizacao do digest
11. fechar o aposentado se couber
```

Os passos 1-4 sao TODOS anteriores a construir e conectar. Nenhum recurso e
criado para uma operacao que ja se sabe condenada, e nenhuma conexao nova e
aberta para ser fechada em seguida.

O passo 7 e o que separa isto de um reload ingenuo: um `statement_timeout_ms`
que o servidor recuse, ou uma role que tenha perdido o acesso ao catalogo,
falha AQUI, com o runtime antigo intacto — e nao no proximo restart, quando
ninguem estiver olhando (D-048).

## O ponto de nao-retorno

Nao existe atomicidade conjunta entre filesystem e memoria (D-048). O
`os.replace` e o unico ponto de nao-retorno, e os dois lados dele tem
semanticas diferentes:

- **antes dele**, qualquer falha preserva o arquivo anterior byte a byte,
  mantem o MESMO objeto runtime publicado, mantem o digest de referencia e
  fecha o candidato exatamente uma vez;
- **depois dele**, o arquivo novo ja esta instalado. Uma falha de `fsync` do
  diretorio nao pode afirmar rollback, entao o runtime novo E publicado, o
  digest E atualizado, a revision nova passa a ser corrente, e a resposta e
  `CONFIG_DURABILITY_ERROR` com `applied=True` (secao 7.6).

Se o processo morrer entre o `replace` e o swap, o disco tem a configuracao
nova — ja validada, compilada e comprovada conectavel — e o proximo start sobe
com ela. E por isso que a verificacao vem antes da persistencia: nao e
otimizacao, e o que torna a janela recuperavel.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import TracebackType
from typing import Any, Protocol

from maskgw.admin.document import RenderedDocument, render_document
from maskgw.admin.errors import AdminError, AdminErrorCategory, raise_admin_error
from maskgw.config.filesystem import (
    ConfigDurabilityError,
    ConfigFileStore,
    ConfigOutOfSyncError,
    ConfigSnapshot,
)
from maskgw.config.gateway import GatewayConfig, build_gateway_config
from maskgw.config.loader import compile_policy, validate_file_config
from maskgw.config.models import UNADOPTED_REVISION, MaskingFileConfig
from maskgw.db.postgres import PostgresAdapter
from maskgw.masking.engine import MaskingEngine
from maskgw.runtime import RetiredRuntimeInUseError, Runtime, RuntimeRegistry
from maskgw.secretsource import EnvSecretProvider, SecretProvider
from maskgw.sql.policy import SqlPolicy


def _default_epoch() -> int:
    """Epoch em segundos, para o nome do backup da adocao. Injetavel em teste."""
    return int(time.time())


#: Recebe o documento persistido e devolve o documento candidato, ainda cru.
#:
#: E o unico ponto de extensao do fluxo: as operacoes granulares da Etapa 9
#: (criar regra, reordenar, remover exception) sao acucar sobre ele. Toda uma
#: delas e "ler o documento inteiro -> aplicar a mudanca -> validar o documento
#: inteiro -> persistir -> trocar", na mesma secao critica. Nao existe caminho
#: que altere o arquivo parcialmente.
#:
#: A `revision` devolvida pela mutacao e IGNORADA: quem a escolhe e o servidor.
ConfigMutation = Callable[[MaskingFileConfig], Mapping[str, Any]]


class AdapterFactory(Protocol):
    """Constroi o adapter do runtime candidato, sem conectar.

    O DSN nunca chega ao plano administrativo: ele fica capturado nesta
    fabrica, construida pelo composition root. Credenciais, host e banco
    continuam vindo so de secret/env, e nao sao campo administrativo nem para
    leitura (D-048).
    """

    def __call__(self, *, config: GatewayConfig, engine: MaskingEngine) -> PostgresAdapter: ...


class AdminOperation(StrEnum):
    """O passo 1 e assimetrico, e por isso a operacao precisa se declarar.

    Exigir "estado adotado" para tudo impediria `config:adopt` de rodar — ela
    existe justamente para sair do estado nao adotado (secao 7.4.1).
    """

    #: Exige estado ADOTADO e `expected_revision >= 1`.
    WRITE = "write"

    #: Exige estado NAO adotado e `expected_revision == 0`. A operacao de
    #: adocao em si — atribuir IDs, exigir `confirm_comment_loss` e gravar o
    #: backup dos bytes originais — pertence a Etapa 9; o que existe aqui e a
    #: pre-condicao do passo 1, que e parte da secao critica.
    ADOPT = "adopt"


@dataclass(frozen=True, slots=True)
class AdminSnapshot:
    """Uma leitura COERENTE do runtime publicado: identidade e conteudo juntos.

    Existe porque ler `revision` e depois ler `document` sao duas leituras da
    referencia publicada, e um swap cabe entre elas. O resultado seria uma
    resposta com o conteudo do runtime antigo rotulada com a revision nova — e
    o dano nao para na leitura: na Etapa 9 um administrador editaria esse
    conteudo antigo usando a `expected_revision` nova, que o passo 2 da secao
    7.4 aprovaria, e sobrescreveria em silencio uma mudanca que ele nunca viu.
    `expected_revision` so protege se a revision que o cliente leu descrever o
    conteudo que ele leu.

    Um snapshot resolve isso por construcao: a referencia publicada e lida UMA
    vez, e revision, documento e politica saem todos dela. Um swap logo depois
    e irrelevante — a resposta descreve, inteira, o runtime que existia no
    instante da leitura.

    O documento e copia profunda (D-055); `SqlPolicy` e congelada sobre
    `frozenset` e `tuple`, e vai por referencia.
    """

    revision: int
    document: MaskingFileConfig
    sql_policy: SqlPolicy

    @property
    def adopted(self) -> bool:
        """Derivado da revision DESTE snapshot, nunca de uma segunda leitura."""
        return self.revision != UNADOPTED_REVISION


@dataclass(frozen=True, slots=True)
class AdminWriteResult:
    """Sucesso de escrita: a revision nova e a confirmacao de que foi aplicada."""

    revision: int

    #: Falso somente no Windows, onde o `fsync` de diretorio nao existe e e
    #: deliberadamente omitido. Nao e falha: o `os.replace` continua atomico, e
    #: o que nao se garante e que ele ja esteja em disco apos queda de energia.
    directory_fsync_performed: bool

    #: Sempre verdadeiro num sucesso. Existe porque a resposta administrativa
    #: carrega `applied` tambem no unico erro que o afirma (secao 4.4).
    applied: bool = True


@dataclass(frozen=True, slots=True)
class _Persisted:
    """Resultado interno do passo 8-9, com o lado do `replace` que ocorreu."""

    digest: str
    durable: bool
    directory_fsync_performed: bool


class AdminConfigService:
    """A secao critica administrativa. Um lock, um processo, uma operacao.

    Nao executa SQL e nao tem superficie para isso (D-049). Nao le nem escreve
    segredo algum: a chave HMAC vem do `SecretProvider` na compilacao, e o DSN
    fica na `AdapterFactory`.
    """

    __slots__ = (
        "_adapter_factory",
        "_clock",
        "_closed",
        "_critical_section",
        "_lifecycle_lock",
        "_operations_total",
        "_reference_digest",
        "_registry",
        "_secrets",
        "_store",
    )

    def __init__(  # noqa: PLR0913 - parametros de composicao, todos keyword-only
        self,
        *,
        store: ConfigFileStore,
        registry: RuntimeRegistry,
        adapter_factory: AdapterFactory,
        reference_digest: str,
        secrets: SecretProvider | None = None,
        clock: Callable[[], int] = _default_epoch,
    ) -> None:
        self._store = store
        self._registry = registry
        self._adapter_factory = adapter_factory
        self._secrets = secrets if secrets is not None else EnvSecretProvider()

        # Relogio injetavel para o nome do backup da adocao (`.bak.<epoch>`).
        # Injetavel para que o teste force um nome deterministico — inclusive uma
        # colisao — sem depender do relogio real (secao 5.4). Usado somente na
        # adocao, sob a secao critica.
        self._clock = clock

        # Digest dos bytes EXATOS a partir dos quais o runtime publicado foi
        # construido. Lido e escrito somente sob `_critical_section`.
        self._reference_digest = reference_digest

        # O lock administrativo de D-052. Cobre a operacao inteira, e nao toca
        # o caminho de query: uma consulta so interage com o runtime pelo
        # mecanismo de aquisicao de D-054, cuja secao critica e outra e curta.
        self._critical_section = threading.Lock()

        # Operacoes de escrita/reload TENTADAS desde o start, contadas sob a
        # propria secao critica. Conta tentativas, e nao sucessos, porque e
        # isso que `GET /admin/v1/status` pede (secao 13.4): um contador de
        # atividade administrativa. Nao e historico e nao substitui
        # `AdminAudit`, que e a Etapa 10 — nao ha aqui operacao, alvo, desfecho
        # nem instante, so um inteiro.
        self._operations_total = 0

        self._lifecycle_lock = threading.Lock()
        self._closed = False

    # -- leitura, sem entrar na secao critica ----------------------------

    def snapshot(self) -> AdminSnapshot:
        """UMA leitura do runtime publicado, com identidade e conteudo juntos.

        E a unica leitura que uma resposta administrativa pode usar. As
        propriedades abaixo continuam existindo, mas cada uma le a referencia
        publicada por conta propria: combinar duas delas reintroduz exatamente
        a incoerencia que este metodo elimina (D-057).

        O lock do registry NAO e segurado durante a copia profunda. `current`
        entra e sai da secao critica dele so para devolver a referencia; a
        copia acontece depois, sobre um agregado cujo conteudo e imutavel. Um
        swap concorrente troca a referencia PUBLICADA, e nao o objeto ja lido —
        e o runtime aposentado so e fechado quando ninguem mais o usa (D-054),
        o que nao afeta a leitura de `file_config`, que e memoria pura.
        """
        published = self._registry.current
        return AdminSnapshot(
            revision=published.revision,
            document=published.file_config.model_copy(deep=True),
            sql_policy=published.config.sql,
        )

    @property
    def revision(self) -> int:
        """Revision publicada. Leitura administrativa nao serializa (D-052).

        Sozinha, para metadata. Uma resposta que precise de revision E conteudo
        usa `snapshot()`.
        """
        return self._registry.current.revision

    @property
    def adopted(self) -> bool:
        """Se a configuracao ja passou pela adocao.

        Uma unica leitura da referencia publicada, e nao `self.revision` outra
        vez: duas leituras aqui teriam a mesma janela de swap que `snapshot()`
        existe para fechar.
        """
        return self._registry.current.revision != UNADOPTED_REVISION

    @property
    def document(self) -> MaskingFileConfig:
        """Copia do modelo validado do arquivo, a fonte administrativa (D-047).

        COPIA, e nao a referencia do runtime. `frozen=True` do Pydantic impede
        reatribuir um campo, mas nao congela as listas e dicionarios de dentro:
        `document.masking.clear()` funcionaria sobre o objeto do runtime
        publicado. Quem le nao pode ter esse poder.

        Nao rotule este documento com uma revision lida a parte: use
        `snapshot()`.
        """
        return self._registry.current.file_config.model_copy(deep=True)

    @property
    def sql_policy(self) -> SqlPolicy:
        """Politica de funcoes/relacoes efetiva do runtime publicado.

        Devolvida por referencia, e nao por copia, porque `SqlPolicy` e uma
        dataclass congelada sobre `frozenset` e `tuple`: nao ha o que mutar. E
        a excecao explicita a regra de copia de D-055, que existe para
        `MaskingFileConfig` — cujas listas e dicionarios internos `frozen=True`
        nao congela.

        Serve a `GET /admin/v1/protected`, que EXIBE as protecoes estruturais.
        Nao existe caminho que as altere (D-050). Tambem aqui, a revision que
        acompanha a politica numa resposta vem de `snapshot()`.
        """
        return self._registry.current.config.sql

    @property
    def retired_runtimes_open(self) -> int:
        """Aposentados ainda abertos. No maximo um, por MAX_RETIRED_RUNTIMES."""
        return self._registry.retired_in_use()

    @property
    def queries_total(self) -> int:
        """Aquisicoes de runtime desde o start — uma por query (D-054)."""
        return self._registry.acquired_total()

    @property
    def operations_total(self) -> int:
        """Operacoes administrativas de escrita/reload tentadas desde o start."""
        with self._critical_section:
            return self._operations_total

    @property
    def reference_digest(self) -> str:
        """SHA-256 dos bytes que originaram o runtime publicado."""
        with self._critical_section:
            return self._reference_digest

    @property
    def closed(self) -> bool:
        with self._lifecycle_lock:
            return self._closed

    # -- a operacao -------------------------------------------------------

    def apply(
        self,
        mutation: ConfigMutation,
        *,
        expected_revision: int,
        operation: AdminOperation = AdminOperation.WRITE,
    ) -> AdminWriteResult:
        """Executa o fluxo de onze passos inteiro, serializado.

        Levanta somente `AdminError`, com categoria do conjunto fechado e
        mensagem fixa. A excecao interna nunca e encadeada: o erro devolvido e
        uma instancia NOVA, levantada fora de qualquer handler, entao
        `__cause__` e `__context__` ficam nulos mesmo quando o passo que falhou
        levantou de dentro de um `except` (D-017).
        """
        failure: AdminError | None = None
        result: AdminWriteResult | None = None

        with self._critical_section:
            self._operations_total += 1
            try:
                result = self._execute(mutation, expected_revision, operation)
            except AdminError as exc:
                # Reconstruida: o objeto original pode carregar `__context__`
                # do handler interno em que nasceu.
                failure = AdminError(exc.category, current_revision=exc.current_revision)
            except BaseException:
                # Nada inesperado escapa com detalhe. Sem este ramo, um erro
                # nao previsto subiria com traceback e mensagem originais.
                failure = AdminError(AdminErrorCategory.INTERNAL_ERROR)

        if failure is not None:
            raise_admin_error(failure)

        assert result is not None  # noqa: S101 - invariante do fluxo acima
        return result

    def close(self) -> None:
        """Recusa operacoes seguintes. Nao fecha registry nem store.

        A propriedade dos dois e do composition root, que os fecha na ordem da
        secao 9.2: parar o plano de dados, aguardar a thread administrativa,
        fechar os runtimes e so entao liberar o lock de arquivo. Fechar aqui
        inverteria essa ordem.
        """
        with self._lifecycle_lock:
            self._closed = True

    # -- passos ------------------------------------------------------------

    def _execute(
        self,
        mutation: ConfigMutation,
        expected_revision: int,
        operation: AdminOperation,
    ) -> AdminWriteResult:
        self._require_open()

        published = self._registry.current
        current_revision = published.revision

        self._check_adoption(current_revision, operation)
        self._check_revision(current_revision, expected_revision)
        disk = self._check_disk_matches_reference()
        self._check_reload_capacity()

        revision = current_revision + 1
        document = self._next_document(published.file_config, mutation, revision)
        rendered = self._render(document)
        # Passo 6 sobre o documento REPARSEADO dos bytes do passo 5: o runtime
        # publicado passa a ser, literalmente, o que o arquivo descreve.
        candidate = self._build_candidate(rendered.document, revision)

        try:
            self._connect_candidate(candidate)
            # Backup byte a byte ANTES de persistir, so na adocao (secao 5.4). Os
            # bytes sao os do passo 3, ja comprovados iguais ao runtime publicado
            # — os originais, com comentarios. Colisao de nome -> CONFIG_WRITE_ERROR,
            # e o candidato e fechado pelo `except` abaixo; o arquivo principal
            # nao foi tocado, porque `_persist` ainda nao rodou.
            if operation is AdminOperation.ADOPT:
                self._write_adoption_backup(disk.data)
            persisted = self._persist(rendered.data)
        except BaseException:
            # Passo 6 ou 7 concluido e passo 8 falhado: o candidato existe e
            # precisa ser fechado exatamente uma vez. O caminho de durabilidade
            # NAO passa por aqui — la o candidato e publicado.
            candidate.adapter.close()
            raise

        try:
            self._publish(candidate, persisted.digest)
        except BaseException:
            # Caminho que nao deveria existir: o passo 4 ja garantiu que ha
            # espaco para aposentar, e este e o unico ponto do processo que
            # troca a referencia. Ainda assim, se a publicacao falhar, o
            # candidato nao pode ficar de pe segurando uma conexao. O digest
            # permanece o antigo, entao a operacao seguinte encontra o arquivo
            # ja trocado e recusa com `CONFIG_OUT_OF_SYNC` — fail-closed.
            if self._registry.current is not candidate:
                candidate.adapter.close()
            raise

        if not persisted.durable:
            raise AdminError(
                AdminErrorCategory.CONFIG_DURABILITY_ERROR,
                current_revision=revision,
            )
        return AdminWriteResult(
            revision=revision,
            directory_fsync_performed=persisted.directory_fsync_performed,
        )

    def _require_open(self) -> None:
        if self.closed:
            raise AdminError(AdminErrorCategory.INTERNAL_ERROR)

    def _check_adoption(self, current_revision: int, operation: AdminOperation) -> None:
        """Passo 1. `config:adopt` e o inverso das demais escritas (7.4.1)."""
        adopted = current_revision != UNADOPTED_REVISION
        if operation is AdminOperation.ADOPT:
            if adopted:
                # Reexecutar a adocao trocaria todos os IDs, que e exatamente o
                # que D-051 existe para impedir. Recusar sem alterar nada e o
                # que a torna idempotente na recusa, e nao na repeticao.
                raise AdminError(AdminErrorCategory.CONFIG_ALREADY_ADOPTED)
            return
        if not adopted:
            raise AdminError(AdminErrorCategory.CONFIG_NOT_ADOPTED)

    def _check_revision(self, current_revision: int, expected_revision: int) -> None:
        """Passo 2. Duas requisicoes com o mesmo `expected_revision` nao vencem ambas."""
        if expected_revision != current_revision:
            raise AdminError(
                AdminErrorCategory.REVISION_CONFLICT,
                current_revision=current_revision,
            )

    def _check_disk_matches_reference(self) -> ConfigSnapshot:
        """Passo 3. O arquivo pode ter sido editado por fora (secao 7.5).

        Digest de conteudo, e nao `mtime` ou tamanho: `mtime` tem granularidade
        grosseira e e falsificavel por `touch`, e uma edicao pode preservar o
        tamanho. Divergiu, nada e sobrescrito — a recuperacao e do
        administrador, que decide se a edicao externa vale.

        Devolve o snapshot lido: os mesmos bytes que a adocao usa para o backup
        byte a byte (secao 5.4), ja comprovados iguais ao runtime publicado.
        Assim o backup nao re-le o arquivo, e nao ha janela entre a verificacao
        e a copia.
        """
        snapshot: ConfigSnapshot | None = None
        try:
            snapshot = self._store.read_snapshot()
        except BaseException:
            snapshot = None

        if snapshot is None:
            # O arquivo ficou ilegivel ou deixou de satisfazer as verificacoes
            # de seguranca. Nada foi escrito e o anterior permanece: e
            # exatamente o que `CONFIG_WRITE_ERROR` promete (secao 7.6).
            raise AdminError(AdminErrorCategory.CONFIG_WRITE_ERROR)
        if snapshot.digest != self._reference_digest:
            raise AdminError(AdminErrorCategory.CONFIG_OUT_OF_SYNC)
        return snapshot

    def _check_reload_capacity(self) -> None:
        """Passo 4. Recusar ANTES de compilar, construir e conectar (secao 8.5)."""
        busy = False
        try:
            self._registry.check_can_swap()
        except RetiredRuntimeInUseError:
            busy = True
        if busy:
            raise AdminError(AdminErrorCategory.RELOAD_BUSY)

    def _next_document(
        self,
        current: MaskingFileConfig,
        mutation: ConfigMutation,
        revision: int,
    ) -> MaskingFileConfig:
        """Passo 5. A mutacao propoe; a validacao decide; o servidor numera.

        A mutacao recebe uma COPIA PROFUNDA, nunca o documento do runtime
        publicado. O motivo e concreto: `frozen=True` do Pydantic impede
        reatribuir um campo, mas `masking`, `exceptions`,
        `sql.allowed_pg_functions` e o `config` de cada regra sao lista e
        dicionario comuns, e continuam mutaveis. Uma mutacao que fizesse
        `document.masking.clear()` e em seguida falhasse deixaria a operacao
        com o desfecho correto — arquivo e engine antigos — e ainda assim
        corromperia o documento do runtime publicado. A escrita seguinte,
        valida e sem relacao com ela, partiria desse documento, persistiria
        zero regras e publicaria um engine SEM MASKING.

        O rollback pre-commit vale para a identidade do runtime e para o
        conteudo dele. A copia e o que torna isso verdade.
        """
        # A mutacao roda sob a MESMA secao critica e sobre a copia profunda do
        # documento corrente — nunca uma leitura anterior (sem janela TOCTOU). Os
        # erros ESPECIFICOS da mutacao — alvo inexistente, campo imutavel — sao
        # `AdminError` de categoria fechada, e devem sair com a categoria que a
        # mutacao escolheu (NOT_FOUND, IMMUTABLE_FIELD), nao viram `CONFIG_INVALID`.
        # Ja uma posicao invalida dependente do estado, ou a validacao do
        # documento inteiro, sao `CONFIG_INVALID`. Distinguimos pela categoria: a
        # mutacao levanta `AdminError`; a validacao levanta `ConfigError` (ou
        # outra coisa). Tudo capturado, nada reencadeado (D-017).
        mutation_error: AdminError | None = None
        document: MaskingFileConfig | None = None
        try:
            proposed = dict(mutation(current.model_copy(deep=True)))
            # `revision` e escolhida pelo servidor, nunca pelo cliente: um
            # valor vindo da mutacao e sobrescrito, sem discussao.
            proposed["revision"] = revision
            document = validate_file_config(proposed)
        except AdminError as exc:
            # Categoria preservada; instancia nova, sem cadeia. `_execute` roda
            # dentro do `try` de `apply`, que ja reconstroi qualquer `AdminError`,
            # entao propagar aqui e suficiente — mas reconstruimos por simetria e
            # para nao depender desse detalhe.
            mutation_error = AdminError(exc.category, current_revision=exc.current_revision)
        except BaseException:
            document = None
        if mutation_error is not None:
            raise mutation_error
        if document is None:
            raise AdminError(AdminErrorCategory.CONFIG_INVALID)
        return document

    def _render(self, document: MaskingFileConfig) -> RenderedDocument:
        """Ainda passo 5: os bytes que serao escritos E os que originam o runtime.

        Serializar aqui, e construir o candidato a partir do documento que
        ESTES bytes produzem, e o que faz o digest de referencia corresponder
        aos bytes exatos do runtime publicado. Sem isso, arquivo e memoria
        poderiam descrever coisas diferentes sem que nada notasse.
        """
        rendered: RenderedDocument | None = None
        try:
            rendered = render_document(document)
        except BaseException:
            rendered = None
        if rendered is None:
            raise AdminError(AdminErrorCategory.CONFIG_INVALID)
        return rendered

    def _build_candidate(self, document: MaskingFileConfig, revision: int) -> Runtime:
        """Passo 6. Runtime NOVO por inteiro; nunca alteracao parcial (D-048).

        Uma query enxerga o antigo inteiro ou o novo inteiro. Um
        `MaskingEngine` novo com um `SqlPolicy` antigo produziria decisoes que
        nenhuma configuracao jamais descreveu.
        """
        adapter: PostgresAdapter | None = None
        runtime: Runtime | None = None
        try:
            policy = compile_policy(document, secrets=self._secrets)
            config = build_gateway_config(document, policy)
            engine = MaskingEngine(policy)
            adapter = self._adapter_factory(config=config, engine=engine)
            runtime = Runtime(
                revision=revision,
                file_config=document,
                config=config,
                engine=engine,
                adapter=adapter,
            )
        except BaseException:
            # O adapter pode ter sido criado e o agregado nao. Fecha o que
            # existe, uma vez so, e nada fica de pe.
            if runtime is None and adapter is not None:
                adapter.close()
            runtime = None
        if runtime is None:
            raise AdminError(AdminErrorCategory.CONFIG_RELOAD_ERROR)
        return runtime

    def _connect_candidate(self, candidate: Runtime) -> None:
        """Passo 7. Read-only, `statement_timeout` e capability de proveniencia.

        As tres verificacoes ja vivem em `PostgresAdapter.connect()` (D-026,
        D-028). A reconexao e necessaria porque `statement_timeout_ms` viaja em
        `options` do DSN e so vale a partir de uma sessao nova.

        Um erro do PostgreSQL aqui vira `CONFIG_RELOAD_ERROR`: a mensagem
        original pode embutir valores e nao sai, como no plano MCP.
        """
        failed = False
        try:
            candidate.adapter.connect()
        except BaseException:
            failed = True
        if failed:
            raise AdminError(AdminErrorCategory.CONFIG_RELOAD_ERROR)

    def _write_adoption_backup(self, original: bytes) -> None:
        """Backup byte a byte dos bytes originais, so na adocao (secao 5.4).

        `write_backup` cria `<config>.bak.<epoch>` com `O_EXCL` e `0600` e nunca
        sobrescreve: colisao de nome ou qualquer falha vira `CONFIG_WRITE_ERROR`,
        levantado FORA do `except` (D-017). O epoch vem do relogio injetavel, e
        nao dos bytes: dois backups no mesmo segundo colidem, e a colisao e
        justamente o que a secao 5.4 exige recusar.
        """
        failed = False
        try:
            self._store.write_backup(original, epoch=self._clock())
        except BaseException:
            failed = True
        if failed:
            raise AdminError(AdminErrorCategory.CONFIG_WRITE_ERROR)

    def _persist(self, data: bytes) -> _Persisted:
        """Passos 8 e 9. O `os.replace` do store e o ponto de nao-retorno."""
        durability_digest: str | None = None
        write_error: AdminErrorCategory | None = None
        result = None
        try:
            result = self._store.write_atomic(data, expected_digest=self._reference_digest)
        except ConfigDurabilityError as exc:
            # Depois do `replace`. O arquivo novo esta instalado e nao ha
            # rollback: o fluxo SEGUE para o swap.
            durability_digest = exc.digest
        except ConfigOutOfSyncError:
            # Segunda verificacao de digest: um editor externo escreveu durante
            # a validacao, compilacao ou conexao. O temporario ja foi removido
            # pelo store e o trabalho do editor e preservado.
            write_error = AdminErrorCategory.CONFIG_OUT_OF_SYNC
        except BaseException:
            write_error = AdminErrorCategory.CONFIG_WRITE_ERROR

        if write_error is not None:
            raise AdminError(write_error)
        if durability_digest is not None:
            return _Persisted(
                digest=durability_digest,
                durable=False,
                directory_fsync_performed=False,
            )

        assert result is not None  # noqa: S101 - invariante dos ramos acima
        return _Persisted(
            digest=result.digest,
            durable=True,
            directory_fsync_performed=result.directory_fsync_performed,
        )

    def _publish(self, candidate: Runtime, digest: str) -> None:
        """Passos 10 e 11. Swap, digest de referencia e fechamento do aposentado.

        O swap e a reatribuicao de UMA referencia: ou a nova esta publicada, ou
        a antiga continua. O antigo e aposentado sob o mesmo lock que publica o
        novo, e o `close` acontece fora dele — fechar uma conexao psycopg pode
        demorar, e segurar o lock de ciclo de vida durante isso bloquearia a
        aquisicao de toda query nova (D-054).

        O reload nao espera queries antigas: se o aposentado ainda tem
        usuarios, quem o fecha e o ultimo release.
        """
        retired = self._registry.swap(candidate)
        self._reference_digest = digest
        if retired is not None:
            retired.adapter.close()

    def __enter__(self) -> AdminConfigService:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        # Sem caminho, sem digest, sem DSN, sem provider de segredo.
        return f"AdminConfigService(revision={self.revision}, closed={self.closed})"
