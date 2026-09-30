"""Candidato de runtime de um datasource: validar, compilar e verificar.

Fase 9, Etapa 3. Um candidato e o conteudo IMUTAVEL de uma geracao ainda sem
identidade: politica compilada, limites efetivos e o alvo de conexao ja
ligado aos enderecos resolvidos. Construir um candidato nao publica nada — nao
toca no registry, no catalogo nem em runtime algum. E por isso que o teste de
conexao e a criacao/rotacao usam exatamente o mesmo caminho: a unica diferenca
e o que o chamador faz com o resultado (D-087).

Passos, e todo passo falha fechado com uma categoria fixa:

1. destino: resolver de novo e comparar com o conjunto persistido (D-084). O
   alvo de conexao usa `hostaddr` com esses enderecos, para que a conexao nao
   dependa de uma segunda resolucao que um DNS hostil poderia trocar;
2. politica: o mesmo schema fechado e o mesmo compilador do `masking.yaml`;
3. limites efetivos: o MAIS RESTRITIVO entre `policy.database` e `limits`
   (D-088) — nunca se excede nenhum dos dois valores configurados;
4. conexao de verificacao: read-only, `statement_timeout` e capability de
   proveniencia conferidos pelo proprio `PostgresAdapter.connect()`; a
   conexao e fechada logo depois — cada sessao abre a sua (D-071).

Nenhuma mensagem carrega host, database, usuario, senha, endereco, SQL ou a
excecao original, e a excecao sanitizada e levantada FORA do handler, para que
nem `__cause__` nem `__context__` apontem para o erro interno (D-017).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NoReturn, Protocol

from psycopg.conninfo import make_conninfo

from maskgw.config.gateway import (
    DatabaseSettings,
    GatewayConfig,
    LoadedConfig,
    parse_config_bundle,
)
from maskgw.config.models import MaskingFileConfig
from maskgw.datasource.destination import (
    AddressResolver,
    DestinationValidationError,
    resolve_destination,
)
from maskgw.datasource.models import (
    DatasourceDraft,
    DatasourceLimits,
    DatasourcePolicy,
    DatasourceRecord,
    DatasourceValidationError,
    DestinationPolicy,
    TlsSettings,
)
from maskgw.db.postgres import PostgresAdapter
from maskgw.errors import CapabilityError, ConfigError, TransformerError
from maskgw.masking.engine import MaskingEngine
from maskgw.secretsource import SecretProvider

#: Espera maxima, em segundos, para estabelecer uma conexao upstream. Um
#: destino que nao responde nao pode prender o startup nem a operacao
#: administrativa indefinidamente.
CONNECT_TIMEOUT_SECONDS: Final = 10


class CandidateFailure(StrEnum):
    """Categoria fechada da falha de um candidato."""

    DESTINATION = "DESTINATION"
    POLICY = "POLICY"
    CONNECTION = "CONNECTION"
    CAPABILITY = "CAPABILITY"


_FAILURE_MESSAGES: Final[dict[CandidateFailure, str]] = {
    CandidateFailure.DESTINATION: "destino do datasource recusado",
    CandidateFailure.POLICY: "politica do datasource invalida",
    CandidateFailure.CONNECTION: "conexao com o datasource falhou",
    CandidateFailure.CAPABILITY: "datasource sem as garantias exigidas",
}


class DatasourceRuntimeError(Exception):
    """Erro sanitizado do runtime multi-datasource.

    Nunca carrega alias, destino, usuario, segredo, SQL ou excecao original.
    """


class DatasourceCandidateError(DatasourceRuntimeError):
    """O candidato nao passou; `category` diz em qual passo, sem detalhe."""

    def __init__(self, category: CandidateFailure) -> None:
        super().__init__(_FAILURE_MESSAGES[category])
        self.category = category


class AdapterFactory(Protocol):
    """Constroi um adapter NAO conectado para um alvo e um runtime.

    Injetavel para os testes de concorrencia sem banco. Em producao e
    `default_adapter_factory`, que sempre verifica as capabilities.
    """

    def __call__(
        self,
        conninfo: str,
        *,
        config: GatewayConfig,
        engine: MaskingEngine,
    ) -> PostgresAdapter: ...


class Verifier(Protocol):
    """Verifica a conexao/sessao/capabilities de um candidato ja construido.

    Injetavel: em producao (Fase 9, Etapa 7) e o gate em processo filho com
    prazo efetivo (`maskgw.datasource.verify`), que limita UMA verificacao ao
    prazo dela mais o orcamento de cleanup. Sem executor dedicado, a chamada
    continua bloqueando o event loop administrativo durante esse tempo, e o
    shutdown inteiro nao herda teto algum deste gate; nos testes de
    concorrencia e o padrao em processo
    (`verify_prepared`), que usa o adapter da factory injetavel. Levanta somente
    `DatasourceCandidateError(CONNECTION`/`CAPABILITY)`.
    """

    def __call__(self, prepared: PreparedRuntime) -> None: ...


def default_adapter_factory(
    conninfo: str,
    *,
    config: GatewayConfig,
    engine: MaskingEngine,
) -> PostgresAdapter:
    return PostgresAdapter(
        conninfo,
        engine,
        settings=config.database,
        sql_policy=config.sql,
        verify_capabilities=True,
    )


@dataclass(frozen=True, slots=True, repr=False)
class CandidateSpec:
    """Entrada de um candidato: os campos do registro mais o segredo.

    Existe so em memoria e so durante a construcao. `repr` e redigido: o
    objeto carrega destino e senha.
    """

    host: str
    port: int
    database: str
    username: str
    tls: TlsSettings
    policy: DatasourcePolicy
    limits: DatasourceLimits
    destination_policy: DestinationPolicy
    expected_addresses: tuple[str, ...] | None
    secret: str

    @classmethod
    def from_record(cls, record: DatasourceRecord, secret: str) -> CandidateSpec:
        """Candidato de um registro persistido: o pinning DNS e obrigatorio."""
        return cls(
            host=record.host,
            port=record.port,
            database=record.database,
            username=record.username,
            tls=record.tls,
            policy=record.policy,
            limits=record.limits,
            destination_policy=record.destination_policy,
            expected_addresses=record.resolved_addresses,
            secret=secret,
        )

    @classmethod
    def from_draft(cls, draft: DatasourceDraft, secret: str) -> CandidateSpec:
        """Candidato de um rascunho; pinning quando o rascunho ja o traz."""
        return cls(
            host=draft.host,
            port=draft.port,
            database=draft.database,
            username=draft.username,
            tls=draft.tls,
            policy=draft.policy,
            limits=draft.limits,
            destination_policy=draft.destination_policy,
            expected_addresses=draft.resolved_addresses or None,
            secret=secret,
        )

    def __repr__(self) -> str:
        return "CandidateSpec(<redacted>)"


class PreparedRuntime:
    """Conteudo imutavel de uma geracao, ainda sem identidade.

    Guarda o alvo de conexao — que inclui a senha upstream — somente em
    memoria, pelo tempo de vida da geracao; `repr` nunca o mostra.
    """

    __slots__ = (
        "_adapter_factory",
        "_addresses",
        "_config",
        "_conninfo",
        "_engine",
        "_file_config",
        "_max_sessions",
    )

    def __init__(  # noqa: PLR0913 - conteudo da geracao, todo keyword-only
        self,
        *,
        file_config: MaskingFileConfig,
        config: GatewayConfig,
        engine: MaskingEngine,
        conninfo: str,
        addresses: tuple[str, ...],
        max_sessions: int,
        adapter_factory: AdapterFactory,
    ) -> None:
        self._file_config = file_config
        self._config = config
        self._engine = engine
        self._conninfo = conninfo
        self._addresses = addresses
        self._max_sessions = max_sessions
        self._adapter_factory = adapter_factory

    @property
    def file_config(self) -> MaskingFileConfig:
        return self._file_config

    @property
    def config(self) -> GatewayConfig:
        return self._config

    @property
    def engine(self) -> MaskingEngine:
        return self._engine

    @property
    def addresses(self) -> tuple[str, ...]:
        """Conjunto DNS validado; o chamador persiste exatamente este."""
        return self._addresses

    @property
    def max_sessions(self) -> int:
        return self._max_sessions

    def new_adapter(self) -> PostgresAdapter:
        """Adapter novo e NAO conectado para uma sessao ou verificacao."""
        return self._adapter_factory(self._conninfo, config=self._config, engine=self._engine)

    def verify_target(self) -> tuple[str, int]:
        """Alvo e limite para o gate de verificacao (conninfo com segredo).

        So o verifier em processo filho o consome; nunca vai para log, repr ou
        resposta. Devolve o MESMO `conninfo` e `statement_timeout` que uma sessao
        real usaria, para que o filho prove exatamente o alvo publicado.
        """
        return self._conninfo, self._config.database.statement_timeout_ms

    def __repr__(self) -> str:
        return f"PreparedRuntime(max_sessions={self._max_sessions}, target=<redacted>)"


def effective_database_settings(
    file_config: MaskingFileConfig, limits: DatasourceLimits
) -> DatabaseSettings:
    """O mais restritivo entre a politica e os limites do datasource (D-088)."""
    return DatabaseSettings(
        statement_timeout_ms=min(
            file_config.database.statement_timeout_ms, limits.statement_timeout_ms
        ),
        max_rows=min(file_config.database.max_rows, limits.max_rows),
    )


def build_conninfo(spec: CandidateSpec, addresses: Sequence[str]) -> str:
    """Alvo libpq com os enderecos validados em `hostaddr`.

    `host` continua sendo o nome (ou `server_name`), porque e contra ele que o
    certificado e verificado em `verify-full`; a conexao TCP, porem, vai so
    para os enderecos ja validados. Nenhum outro parametro do alvo vem de fora
    do registro.
    """
    name = spec.tls.server_name if spec.tls.server_name is not None else spec.host
    return make_conninfo(
        "",
        host=",".join(name for _ in addresses),
        hostaddr=",".join(addresses),
        port=spec.port,
        dbname=spec.database,
        user=spec.username,
        password=spec.secret,
        sslmode=spec.tls.mode,
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
    )


def build_candidate(
    spec: CandidateSpec,
    *,
    secrets: SecretProvider | None = None,
    resolver: AddressResolver | None = None,
    adapter_factory: AdapterFactory | None = None,
    verifier: Verifier | None = None,
) -> PreparedRuntime:
    """Constroi e VERIFICA um candidato. Nunca publica nem persiste.

    Levanta somente `DatasourceCandidateError`, sem cadeia de excecao. `verifier`
    e o gate pos-conexao: `None` usa `verify_prepared` (em processo); a producao
    injeta o gate em processo filho com prazo (Fase 9, Etapa 7).
    """
    verify = verifier if verifier is not None else verify_prepared
    factory = adapter_factory if adapter_factory is not None else default_adapter_factory
    failure: CandidateFailure | None = None

    addresses: tuple[str, ...] = ()
    try:
        addresses = resolve_destination(
            spec.host,
            spec.port,
            policy=spec.destination_policy,
            resolver=resolver,
            expected_addresses=spec.expected_addresses,
        ).addresses
    except (DestinationValidationError, DatasourceValidationError, OSError):
        failure = CandidateFailure.DESTINATION
    if failure is not None:
        _raise_candidate(failure)

    prepared: PreparedRuntime | None = None
    try:
        loaded, config = _compile(spec.policy, spec.limits, secrets=secrets)
        prepared = PreparedRuntime(
            file_config=loaded.file_config,
            config=config,
            engine=MaskingEngine(config.masking),
            conninfo=build_conninfo(spec, addresses),
            addresses=addresses,
            max_sessions=spec.limits.max_sessions,
            adapter_factory=factory,
        )
    except (ConfigError, TransformerError, DatasourceValidationError, TypeError, ValueError):
        failure = CandidateFailure.POLICY
    if failure is not None or prepared is None:
        _raise_candidate(failure or CandidateFailure.POLICY)

    verify(prepared)
    return prepared


def _compile(
    policy: DatasourcePolicy,
    limits: DatasourceLimits,
    *,
    secrets: SecretProvider | None,
) -> tuple[LoadedConfig, GatewayConfig]:
    loaded = parse_config_bundle(policy.to_mapping(), secrets=secrets)
    settings = effective_database_settings(loaded.file_config, limits)
    config = GatewayConfig(
        masking=loaded.gateway.masking, database=settings, sql=loaded.gateway.sql
    )
    return loaded, config


def verify_policy(
    policy: DatasourcePolicy,
    limits: DatasourceLimits,
    *,
    secrets: SecretProvider | None = None,
) -> None:
    """Compila a politica pelo MESMO caminho do candidato, sem destino nem conexao.

    Usado ao persistir um datasource DESABILITADO (Fase 9, Etapa 4, D-094): sem
    candidato, uma politica que nao compila seria gravada e so falharia na
    reabilitacao. Levanta somente `DatasourceCandidateError(POLICY)`.
    """
    failure: CandidateFailure | None = None
    try:
        MaskingEngine(_compile(policy, limits, secrets=secrets)[1].masking)
    except (ConfigError, TransformerError, DatasourceValidationError, TypeError, ValueError):
        failure = CandidateFailure.POLICY
    if failure is not None:
        _raise_candidate(failure)


def verify_adapter(adapter: PostgresAdapter) -> None:
    """Conecta, confere os limites e fecha, mapeando a falha para a categoria.

    Primitiva compartilhada e UNICA da verificacao pos-conexao: `verify_prepared`
    (pai, com o adapter da factory injetavel) e o caminho em processo filho
    (`maskgw.datasource.verify`, com um adapter real do `conninfo`) chamam esta
    funcao. As consultas de sessao e capability vivem em
    `PostgresAdapter.connect()`; nao ha copia divergente. Levanta somente
    `DatasourceCandidateError(CONNECTION` ou `CAPABILITY)`, sem cadeia (D-017).
    """
    failure: CandidateFailure | None = None
    try:
        adapter.connect()
    except CapabilityError:
        failure = CandidateFailure.CAPABILITY
    except Exception:
        failure = CandidateFailure.CONNECTION
    finally:
        adapter.close()
    if failure is not None:
        _raise_candidate(failure)


def verify_prepared(prepared: PreparedRuntime) -> None:
    """Abre uma conexao de verificacao e a fecha, sempre.

    O adapter vem da factory injetavel do `PreparedRuntime` (fakes nos testes de
    concorrencia); a verificacao em si e a mesma `verify_adapter` que o processo
    filho usa, sem copia das consultas de capability.
    """
    verify_adapter(prepared.new_adapter())


def _raise_candidate(category: CandidateFailure) -> NoReturn:
    """Levanta FORA do handler: sem `__cause__` nem `__context__` (D-017)."""
    raise DatasourceCandidateError(category) from None


__all__ = [
    "CONNECT_TIMEOUT_SECONDS",
    "AdapterFactory",
    "AddressResolver",
    "CandidateFailure",
    "CandidateSpec",
    "DatasourceCandidateError",
    "DatasourceRuntimeError",
    "PreparedRuntime",
    "Verifier",
    "build_candidate",
    "build_conninfo",
    "default_adapter_factory",
    "effective_database_settings",
    "verify_adapter",
    "verify_policy",
    "verify_prepared",
]
