"""Startup fail-closed e coordenador interno do runtime multi-datasource.

Fase 9, Etapa 3 (spec §§6.3, 7 e 11; D-076, D-087 a D-091). Sem HTTP: a Admin
API v2 da Etapa 4 sera uma traducao para estes metodos, como a Etapa 9 da
Fase 7 foi para `AdminConfigService.apply()`.

## Startup (§11, passos 3-7)

`open_datasource_runtime` abre o store com lock e chave-mestra, autentica o
catalogo, e para CADA datasource habilitado: revalida o destino contra o
conjunto DNS persistido, compila a politica, conecta com as verificacoes de
read-only, timeout e proveniencia, e so entao publica a geracao. Qualquer
falha fecha o que ja existia — registry e store — e propaga um erro
sanitizado. Nao ha modo parcial, retry nem fallback para o DSN legado
(D-075/D-076). Datasource desabilitado nao e aberto.

## Operacoes (serializadas, como D-052)

Toda escrita segue a mesma ordem, e cada passo so acontece se o anterior
passou:

1. servico aberto e nao bloqueado; `expected_revision` igual a revision do
   catalogo; pre-condicoes baratas (alias livre, rename recusado);
2. vaga de candidato reservada no registry — o limite e checado ANTES de
   construir e conectar qualquer coisa (D-089);
3. candidato construido e VERIFICADO (conexao real, capabilities);
4. persistencia no `CatalogStore` com `expected_revision`, gravando
   exatamente os enderecos DNS que o candidato validou;
5. publicacao da geracao nova (troca atomica) ou retirada da antiga.

Falha em 1-3 nao toca em bytes, revision nem registry. Falha de persistencia
(4) deixa o runtime publicado como estava e BLOQUEIA o servico, como o store
ja se bloqueia: um resultado incerto nao pode ser seguido de outra escrita
sobre memoria possivelmente divergente do disco. A unica excecao e a direcao
segura: numa desabilitacao ou remocao de resultado incerto, a geracao e
retirada mesmo assim — reduzir exposicao nunca espera confirmacao.

Testar candidato (`test_draft`, `test_datasource`) usa os passos 2-3 e
descarta o resultado: nunca persiste, publica, altera revision nem registra
`last_test` (F9-022/F9-026).

## Fase 9, Etapa 4 (D-094)

A Admin API v2 e uma traducao para estes metodos. Tres acrescimos vieram com
ela, todos dentro da mesma secao critica:

- **revision por datasource.** Cada escrita sobre um datasource existente
  aceita `expected_datasource_revision`, conferida sob o lock contra a revision
  do PROPRIO registro; a revision do catalogo so guarda a criacao. Edicoes em
  datasources distintos nao conflitam. Continua aceita a forma da Etapa 3
  (`expected_revision`, do catalogo) — exatamente uma das duas;
- **mutacao dentro da secao critica.** `update` aceita uma funcao que recebe o
  registro corrente, lido sob o lock, e devolve o rascunho; `remove` aceita uma
  confirmacao sobre o registro lido sob o lock. Nenhum campo e copiado de uma
  leitura anterior ao lock (sem TOCTOU, como D-059);
- **probe de revision.** `DatasourceWriteProbe` recebe a revision do catalogo
  observada sob o lock e a publicada, para a auditoria emitida DEPOIS da secao
  critica.

E duas correcoes de contrato: testar um datasource desabilitado e recusado
(spec §6.1: `enabled=false` impede novos testes de conexao), e persistir um
datasource desabilitado compila a politica — sem candidato, uma politica que
nao compila seria gravada e so falharia na reabilitacao.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TypeVar

from maskgw.datasource.destination import AddressResolver
from maskgw.datasource.models import DatasourceDraft, DatasourceRecord
from maskgw.datasource.store import (
    CatalogOutcomeUncertainError,
    CatalogRevisionConflictError,
    CatalogStore,
    CatalogStoreError,
)
from maskgw.runtime.candidate import (
    AdapterFactory,
    CandidateSpec,
    DatasourceRuntimeError,
    PreparedRuntime,
    build_candidate,
    verify_policy,
)
from maskgw.runtime.datasources import DatasourceRegistry, RegistryLimits
from maskgw.secretsource import SecretProvider

_T = TypeVar("_T")

#: Prefixo da chave de candidato de um datasource que ainda nao tem ID.
_NEW_KEY_PREFIX = "alias:"


class DatasourceServiceClosedError(DatasourceRuntimeError):
    def __init__(self) -> None:
        super().__init__("operacao de datasource indisponivel")


class DatasourceServiceBlockedError(DatasourceRuntimeError):
    """Uma persistencia falhou; o servico so volta apos reinicio."""

    def __init__(self) -> None:
        super().__init__("operacao de datasource requer reinicio apos falha de persistencia")


class DatasourceRenameError(DatasourceRuntimeError):
    """Rename nao existe no MVP (spec §4.1, D-066)."""

    def __init__(self) -> None:
        super().__init__("alias de datasource nao pode ser alterado")


class DatasourceNotFoundError(CatalogStoreError):
    """ID ausente do catalogo. Mensagem fixa, sem o ID pedido."""

    def __init__(self) -> None:
        super().__init__("datasource nao encontrado")


class DatasourceAliasConflictError(CatalogStoreError):
    """Alias ja usado por outro datasource. Mensagem fixa, sem o alias."""

    def __init__(self) -> None:
        super().__init__("alias ja existe")


class DatasourceRevisionConflictError(CatalogRevisionConflictError):
    """`expected_*revision` divergiu; carrega a revision observada sob o lock.

    Subclasse do erro do store para que chamadores da Etapa 3 continuem
    recebendo `CatalogRevisionConflictError`. `current_revision` e metadata
    administrativa, a mesma que o chamador le num GET.
    """

    def __init__(self, current_revision: int) -> None:
        super().__init__("revision divergiu")
        self.current_revision = current_revision


class DatasourceDisabledError(DatasourceRuntimeError):
    """Teste de conexao de datasource desabilitado (spec §6.1)."""

    def __init__(self) -> None:
        super().__init__("datasource desabilitado")


@dataclass(slots=True)
class DatasourceWriteProbe:
    """Revisions do catalogo observadas DENTRO da secao critica (D-094).

    `catalog_revision_before` e a revision lida sob o lock, antes de qualquer
    efeito; `catalog_revision_after`, a revision depois de um commit certo — ou
    a mesma, quando a operacao nao precisou gravar (habilitar o ja habilitado).
    Fica `None` quando nada foi confirmado, inclusive no resultado incerto.
    """

    catalog_revision_before: int | None = None
    catalog_revision_after: int | None = None


#: Rascunho pronto ou funcao que o deriva do registro corrente, sob o lock.
DraftSource = DatasourceDraft | Callable[[DatasourceRecord], DatasourceDraft]


@dataclass(frozen=True, slots=True)
class DatasourceCatalogSettings:
    """Ativacao interna do catalogo e do registry (D-087).

    Nao e lida do ambiente nesta etapa: somente o composition root a recebe.
    `resolver` e `adapter_factory` existem para os testes; em producao ficam
    `None` e usam o resolver do sistema e o adapter real com verificacao.
    """

    store_path: str | Path | None = None
    anchor_path: str | Path | None = None
    limits: RegistryLimits = field(default_factory=RegistryLimits)
    resolver: AddressResolver | None = None
    adapter_factory: AdapterFactory | None = None


def draft_from_record(record: DatasourceRecord, *, enabled: bool | None = None) -> DatasourceDraft:
    """Rascunho equivalente ao registro, com o pinning DNS persistido."""
    return DatasourceDraft(
        alias=record.alias,
        display_name=record.display_name,
        host=record.host,
        port=record.port,
        database=record.database,
        username=record.username,
        enabled=record.enabled if enabled is None else enabled,
        tls=record.tls,
        policy=record.policy,
        limits=record.limits,
        destination_policy=record.destination_policy,
        resolved_addresses=record.resolved_addresses,
    )


class DatasourceRuntimeService:
    """Coordena candidato, persistencia e publicacao, uma operacao por vez."""

    __slots__ = (
        "_adapter_factory",
        "_blocked",
        "_closed",
        "_lock",
        "_registry",
        "_resolver",
        "_secrets",
        "_state_lock",
        "_store",
    )

    def __init__(
        self,
        *,
        store: CatalogStore,
        registry: DatasourceRegistry,
        secrets: SecretProvider | None = None,
        resolver: AddressResolver | None = None,
        adapter_factory: AdapterFactory | None = None,
    ) -> None:
        self._store = store
        self._registry = registry
        self._secrets = secrets
        self._resolver = resolver
        self._adapter_factory = adapter_factory
        # Secao critica de escrita: revision, candidato, persistencia e
        # publicacao na mesma operacao (D-052).
        self._lock = threading.Lock()
        # Curto: so as marcas `_closed`/`_blocked`.
        self._state_lock = threading.Lock()
        self._closed = False
        self._blocked = False

    # -- testes de candidato, sem efeito ---------------------------------

    def test_draft(self, draft: DatasourceDraft, secret: str) -> None:
        """Verifica um rascunho sem persistir nem publicar."""
        self._ensure_open(allow_blocked=True)
        with self._registry.reserve(_new_key(draft.alias), publish=False):
            self._build(CandidateSpec.from_draft(draft, secret))

    def test_datasource(self, datasource_id: str) -> None:
        """Verifica o registro persistido sem publicar, persistir ou alterar revision.

        Datasource desabilitado nao e testado (spec §6.1): a desabilitacao
        impede novos testes de conexao, e reabilitar ja exige candidato.
        """
        self._ensure_open(allow_blocked=True)
        record = self._get(datasource_id)
        if not record.enabled:
            raise DatasourceDisabledError
        secret = self._store.read_upstream_secret(datasource_id)
        with self._registry.reserve(datasource_id, publish=False):
            self._build(CandidateSpec.from_record(record, secret))

    # -- escritas --------------------------------------------------------

    def create(
        self,
        draft: DatasourceDraft,
        secret: str,
        *,
        expected_revision: int,
        probe: DatasourceWriteProbe | None = None,
    ) -> DatasourceRecord:
        with self._lock:
            self._ensure_open()
            self._check_revision(expected_revision)
            _observe_before(probe, expected_revision)
            if any(record.alias == draft.alias for record in self._store.snapshot().datasources):
                raise DatasourceAliasConflictError
            if not draft.enabled:
                verify_policy(draft.policy, draft.limits, secrets=self._secrets)
                created = self._persist(
                    lambda: self._store.create(
                        draft,
                        secret,
                        expected_revision=expected_revision,
                        resolver=self._resolver,
                    )
                )
                self._observe_after(probe)
                return created
            with self._registry.reserve(_new_key(draft.alias), publish=True) as reservation:
                prepared = self._build(CandidateSpec.from_draft(draft, secret))
                pinned = replace(draft, resolved_addresses=prepared.addresses)
                record = self._persist(
                    lambda: self._store.create(
                        pinned,
                        secret,
                        expected_revision=expected_revision,
                        resolver=self._resolver,
                    )
                )
                self._observe_after(probe)
                reservation.publish(
                    datasource_id=record.id,
                    alias=record.alias,
                    record_revision=record.revision,
                    prepared=prepared,
                )
                return record

    def update(
        self,
        datasource_id: str,
        draft: DraftSource,
        *,
        expected_revision: int | None = None,
        expected_datasource_revision: int | None = None,
        probe: DatasourceWriteProbe | None = None,
    ) -> DatasourceRecord:
        """Substitui os campos nao secretos; `draft` pode derivar do corrente.

        Uma funcao em `draft` recebe o registro lido SOB o lock, depois da
        conferencia de revision: o rascunho nunca nasce de estado anterior a
        secao critica.
        """
        with self._lock:
            self._ensure_open()
            catalog_revision = self._guard(
                datasource_id,
                expected_revision=expected_revision,
                expected_datasource_revision=expected_datasource_revision,
                probe=probe,
            )
            resolved = draft(self._get(datasource_id)) if callable(draft) else draft
            record = self._update_locked(
                datasource_id, resolved, expected_revision=catalog_revision
            )
            self._observe_after(probe)
            return record

    def set_enabled(
        self,
        datasource_id: str,
        enabled: bool,
        *,
        expected_revision: int | None = None,
        expected_datasource_revision: int | None = None,
        probe: DatasourceWriteProbe | None = None,
    ) -> DatasourceRecord:
        """Habilita (com candidato verificado) ou desabilita (com drenagem).

        Pedir o estado que ja vale nao grava nada: devolve o registro corrente,
        e o probe registra a mesma revision antes e depois.
        """
        with self._lock:
            self._ensure_open()
            catalog_revision = self._guard(
                datasource_id,
                expected_revision=expected_revision,
                expected_datasource_revision=expected_datasource_revision,
                probe=probe,
            )
            current = self._get(datasource_id)
            if current.enabled == enabled:
                self._observe_after(probe)
                return current
            record = self._update_locked(
                datasource_id,
                draft_from_record(current, enabled=enabled),
                expected_revision=catalog_revision,
            )
            self._observe_after(probe)
            return record

    def rotate_secret(
        self,
        datasource_id: str,
        secret: str,
        *,
        expected_revision: int | None = None,
        expected_datasource_revision: int | None = None,
        probe: DatasourceWriteProbe | None = None,
    ) -> DatasourceRecord:
        with self._lock:
            self._ensure_open()
            catalog_revision = self._guard(
                datasource_id,
                expected_revision=expected_revision,
                expected_datasource_revision=expected_datasource_revision,
                probe=probe,
            )
            current = self._get(datasource_id)
            if not current.enabled:
                rotated = self._persist(
                    lambda: self._store.rotate_secret(
                        datasource_id, secret, expected_revision=catalog_revision
                    )
                )
                self._observe_after(probe)
                return rotated
            with self._registry.reserve(
                datasource_id, datasource_id=datasource_id, publish=True
            ) as reservation:
                prepared = self._build(CandidateSpec.from_record(current, secret))
                record = self._persist(
                    lambda: self._store.rotate_secret(
                        datasource_id, secret, expected_revision=catalog_revision
                    )
                )
                self._observe_after(probe)
                reservation.publish(
                    datasource_id=record.id,
                    alias=record.alias,
                    record_revision=record.revision,
                    prepared=prepared,
                )
                return record

    def remove(
        self,
        datasource_id: str,
        *,
        expected_revision: int | None = None,
        expected_datasource_revision: int | None = None,
        probe: DatasourceWriteProbe | None = None,
        confirm: Callable[[DatasourceRecord], None] | None = None,
    ) -> None:
        """Remove do catalogo e retira a geracao; sessoes admitidas drenam.

        `confirm` recebe o registro lido sob o lock, depois da revision, e pode
        recusar a remocao levantando — a confirmacao destrutiva da Admin v2.
        """
        with self._lock:
            self._ensure_open()
            catalog_revision = self._guard(
                datasource_id,
                expected_revision=expected_revision,
                expected_datasource_revision=expected_datasource_revision,
                probe=probe,
            )
            current = self._get(datasource_id)
            if confirm is not None:
                confirm(current)
            self._persist_withdrawal(
                datasource_id,
                lambda: self._store.remove(datasource_id, expected_revision=catalog_revision),
            )
            self._observe_after(probe)

    def _update_locked(
        self, datasource_id: str, draft: DatasourceDraft, *, expected_revision: int
    ) -> DatasourceRecord:
        current = self._get(datasource_id)
        if draft.alias != current.alias:
            raise DatasourceRenameError()
        if not draft.enabled:
            # Politica NOVA num datasource desabilitado e compilada, sem
            # conectar. A mesma politica nao: desabilitar reduz exposicao e nao
            # pode depender, por exemplo, da chave HMAC ainda estar no ambiente.
            if draft.policy != current.policy:
                verify_policy(draft.policy, draft.limits, secrets=self._secrets)
            # Desabilitar so reduz exposicao e nao pode depender de DNS: com o
            # mesmo destino, o conjunto persistido e reapresentado ao store em
            # vez de uma resolucao nova, que falharia justamente quando o DNS
            # esta fora do ar ou adulterado. Destino novo continua resolvido.
            same_destination = (draft.host, draft.port) == (current.host, current.port)
            persisted = current.resolved_addresses
            resolver: AddressResolver | None = (
                (lambda _host, _port: persisted) if same_destination else self._resolver
            )
            return self._persist_withdrawal(
                datasource_id,
                lambda: self._store.update(
                    datasource_id,
                    draft,
                    expected_revision=expected_revision,
                    resolver=resolver,
                ),
            )
        secret = self._store.read_upstream_secret(datasource_id)
        with self._registry.reserve(
            datasource_id, datasource_id=datasource_id, publish=True
        ) as reservation:
            prepared = self._build(CandidateSpec.from_draft(draft, secret))
            pinned = replace(draft, resolved_addresses=prepared.addresses)
            record = self._persist(
                lambda: self._store.update(
                    datasource_id,
                    pinned,
                    expected_revision=expected_revision,
                    resolver=self._resolver,
                )
            )
            reservation.publish(
                datasource_id=record.id,
                alias=record.alias,
                record_revision=record.revision,
                prepared=prepared,
            )
            return record

    # -- apoio -----------------------------------------------------------

    def _build(self, spec: CandidateSpec) -> PreparedRuntime:
        return build_candidate(
            spec,
            secrets=self._secrets,
            resolver=self._resolver,
            adapter_factory=self._adapter_factory,
        )

    def _check_revision(self, expected_revision: int) -> None:
        current = self._store.revision
        if expected_revision != current:
            raise DatasourceRevisionConflictError(current)

    def _guard(
        self,
        datasource_id: str,
        *,
        expected_revision: int | None,
        expected_datasource_revision: int | None,
        probe: DatasourceWriteProbe | None,
    ) -> int:
        """Confere a revision pedida sob o lock e devolve a do catalogo.

        Exatamente uma das duas formas. Com a do datasource, a revision do
        catalogo repassada ao store e a lida AGORA, sob a secao critica: so este
        coordenador escreve no store, entao ela nao muda ate o commit — e, se
        mudasse, o proprio store recusaria.
        """
        if (expected_revision is None) == (expected_datasource_revision is None):
            msg = "informe exatamente uma revision esperada"
            raise ValueError(msg)
        if expected_revision is not None:
            self._check_revision(expected_revision)
            _observe_before(probe, expected_revision)
            return expected_revision
        current = self._get(datasource_id)
        if current.revision != expected_datasource_revision:
            raise DatasourceRevisionConflictError(current.revision)
        catalog_revision = self._store.revision
        _observe_before(probe, catalog_revision)
        return catalog_revision

    def _get(self, datasource_id: str) -> DatasourceRecord:
        """Registro pelo ID; ausente ou malformado tem erro proprio e fixo."""
        for record in self._store.snapshot().datasources:
            if record.id == datasource_id:
                return record
        raise DatasourceNotFoundError

    def _observe_after(self, probe: DatasourceWriteProbe | None) -> None:
        if probe is not None:
            probe.catalog_revision_after = self._store.revision

    def _persist(self, write: Callable[[], _T]) -> _T:
        """Persiste; se o store exigir reabertura, o servico se bloqueia.

        A condicao e a do proprio store, e nao o tipo da excecao: qualquer
        falha dentro do protocolo de commit o envenena, inclusive uma de
        filesystem que nao e `CatalogWriteError`. Recusas anteriores ao commit
        (revision, alias, destino) nao o envenenam e nao bloqueiam.
        """
        try:
            return write()
        except BaseException:
            if self._store.requires_reopen:
                self._block()
            raise

    def _persist_withdrawal(self, datasource_id: str, write: Callable[[], _T]) -> _T:
        """Persistencia de desabilitar/remover, com a retirada no fim.

        Resultado incerto retira a geracao mesmo assim: o disco pode ja dizer
        "desabilitado", e reduzir exposicao e a direcao segura. Falha antes do
        replace preserva o par anterior, e entao o runtime tambem fica.
        """
        try:
            result = self._persist(write)
        except CatalogOutcomeUncertainError:
            self._registry.withdraw(datasource_id)
            raise
        self._registry.withdraw(datasource_id)
        return result

    def _block(self) -> None:
        with self._state_lock:
            self._blocked = True

    def _ensure_open(self, *, allow_blocked: bool = False) -> None:
        with self._state_lock:
            if self._closed:
                raise DatasourceServiceClosedError()
            if self._blocked and not allow_blocked:
                raise DatasourceServiceBlockedError()

    @property
    def blocked(self) -> bool:
        with self._state_lock:
            return self._blocked

    def close(self) -> None:
        """Recusa operacoes novas e espera a operacao em andamento. Idempotente."""
        with self._state_lock:
            self._closed = True
        # Adquirir a secao critica garante que nenhuma escrita esta no meio.
        with self._lock:
            pass

    def __repr__(self) -> str:
        with self._state_lock:
            return f"DatasourceRuntimeService(closed={self._closed}, blocked={self._blocked})"


class DatasourceRuntime:
    """Store, registry e coordenador de uma execucao, com shutdown unico."""

    __slots__ = ("_registry", "_service", "_store")

    def __init__(
        self,
        *,
        store: CatalogStore,
        registry: DatasourceRegistry,
        service: DatasourceRuntimeService,
    ) -> None:
        self._store = store
        self._registry = registry
        self._service = service

    @property
    def store(self) -> CatalogStore:
        return self._store

    @property
    def registry(self) -> DatasourceRegistry:
        return self._registry

    @property
    def service(self) -> DatasourceRuntimeService:
        return self._service

    def begin_shutdown(self) -> None:
        """Interrompe a admissao de sessoes. Nao espera nada."""
        self._registry.begin_shutdown()

    def close(self) -> None:
        """Coordenador, sessoes/geracoes e store, nesta ordem. Idempotente.

        O coordenador fecha primeiro e espera a escrita em voo; o registry
        drena e descarta as geracoes; o store — e seus locks — sai por ultimo,
        para que nenhum segundo processo abra o catalogo com este ainda vivo.
        """
        try:
            self._service.close()
            self._registry.close()
        finally:
            self._store.close()

    def __repr__(self) -> str:
        return f"DatasourceRuntime({self._registry!r})"


def open_datasource_runtime(
    settings: DatasourceCatalogSettings,
    *,
    secrets: SecretProvider | None = None,
) -> DatasourceRuntime:
    """Passos 3-7 da §11, integralmente fail-closed (D-076)."""
    store = CatalogStore.open(
        settings.store_path,
        anchor_path=settings.anchor_path,
        secrets_provider=secrets,
    )
    registry: DatasourceRegistry | None = None
    try:
        registry = DatasourceRegistry(settings.limits)
        for record in store.snapshot().datasources:
            if not record.enabled:
                continue
            secret = store.read_upstream_secret(record.id)
            with registry.reserve(record.id, datasource_id=record.id, publish=True) as reservation:
                prepared = build_candidate(
                    CandidateSpec.from_record(record, secret),
                    secrets=secrets,
                    resolver=settings.resolver,
                    adapter_factory=settings.adapter_factory,
                )
                reservation.publish(
                    datasource_id=record.id,
                    alias=record.alias,
                    record_revision=record.revision,
                    prepared=prepared,
                )
        service = DatasourceRuntimeService(
            store=store,
            registry=registry,
            secrets=secrets,
            resolver=settings.resolver,
            adapter_factory=settings.adapter_factory,
        )
        return DatasourceRuntime(store=store, registry=registry, service=service)
    except BaseException:
        try:
            if registry is not None:
                registry.close()
        finally:
            store.close()
        raise


def _new_key(alias: str) -> str:
    return f"{_NEW_KEY_PREFIX}{alias}"


def _observe_before(probe: DatasourceWriteProbe | None, catalog_revision: int) -> None:
    if probe is not None:
        probe.catalog_revision_before = catalog_revision


__all__ = [
    "DatasourceAliasConflictError",
    "DatasourceCatalogSettings",
    "DatasourceDisabledError",
    "DatasourceNotFoundError",
    "DatasourceRenameError",
    "DatasourceRevisionConflictError",
    "DatasourceRuntime",
    "DatasourceRuntimeService",
    "DatasourceServiceBlockedError",
    "DatasourceServiceClosedError",
    "DatasourceWriteProbe",
    "DraftSource",
    "draft_from_record",
    "open_datasource_runtime",
]
