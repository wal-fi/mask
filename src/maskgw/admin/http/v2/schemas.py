"""Schemas fechados da Admin API v2 de datasources (Fase 9, Etapa 4, D-093).

Modulo separado de `admin/http/schemas.py` de proposito: aquele modulo inteiro e
lido pelo gerador da UI v1, e um modelo novo ali mudaria os artefatos da v1.

Regras estruturais, cada uma com teste:

- **todo modelo e fechado** (`extra="forbid"`, `frozen=True`) e todo escalar e
  estrito: `"5432"` nao vira `5432`, `1` nao vira `true`;
- **nenhum DSN pronto.** Destino e credencial sao campos distintos — host,
  porta, database, usuario, senha. Um campo `dsn`, `conninfo`, `url` ou
  `password` fora de `credential` cai no `extra="forbid"`;
- **a senha e write-only.** So existe nos corpos de criar, testar rascunho e
  rotacionar. Nenhuma resposta tem campo para ela, nem derivado: `credential`
  e `{"configured": true}` e o tipo nao admite outro valor;
- **os enderecos DNS fixados nao saem** — sao mecanismo interno de D-084;
- **o alias e imutavel.** Presente num `PUT` (em qualquer forma), vira
  `IMMUTABLE_FIELD`, como `allowed_pg_functions` (D-050/D-059), que tambem nao
  e administravel aqui: presente em qualquer forma e recusado, ausente e
  preservado;
- **a politica nao tem `revision` nem `id` no fio.** A revision da politica e a
  do datasource, e a substituicao e integral e posicional.

Os validadores de campo aplicam as MESMAS funcoes do modelo do catalogo, para
que um valor que o catalogo recusaria seja `SCHEMA_INVALID` com o caminho do
campo — e nunca com o valor enviado.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, JsonValue, Strict

from maskgw.config.models import (
    MAX_MAX_ROWS,
    MAX_STATEMENT_TIMEOUT_MS,
    MIN_MAX_ROWS,
    MIN_STATEMENT_TIMEOUT_MS,
)
from maskgw.datasource.models import (
    ALIAS_PATTERN,
    DATASOURCE_ID_PATTERN,
    DatasourceValidationError,
    validate_host,
)
from maskgw.masking.rules import MatchMode

_STRICT = ConfigDict(extra="forbid", frozen=True)

StrictInt = Annotated[int, Strict()]
StrictBool = Annotated[bool, Strict()]
StrictStr = Annotated[str, Strict()]
JsonOrAbsent = JsonValue | None

#: Limites dos campos, iguais aos de `DatasourceDraft`/`DatasourceLimits`.
MAX_DISPLAY_NAME = 128
MAX_IDENTIFIER = 63
MAX_PASSWORD = 1024
MAX_ALLOWED_HOSTS = 64
MIN_DS_TIMEOUT_MS = 100
MAX_DS_TIMEOUT_MS = 600_000
MAX_DS_ROWS = 1_000_000
MAX_DS_SESSIONS = 1_000


def _host(value: str) -> str:
    try:
        return validate_host(value)
    except DatasourceValidationError:
        msg = "invalid host"
        raise ValueError(msg) from None


def _safe_text(value: str) -> str:
    if value.strip() != value or any(ord(char) < 0x20 or ord(char) == 0x7F for char in value):  # noqa: PLR2004
        msg = "invalid text"
        raise ValueError(msg)
    return value


def _password(value: str) -> str:
    if "\x00" in value:
        msg = "invalid password"
        raise ValueError(msg)
    return value


def _allowed_hosts(value: list[str]) -> list[str]:
    normalized = [host.lower() for host in value]
    if normalized != value or len(set(normalized)) != len(normalized):
        msg = "invalid allowlist"
        raise ValueError(msg)
    for host in value:
        _host(host)
    return value


Host = Annotated[StrictStr, Field(min_length=1, max_length=253), AfterValidator(_host)]
SafeIdentifier = Annotated[
    StrictStr, Field(min_length=1, max_length=MAX_IDENTIFIER), AfterValidator(_safe_text)
]
DisplayName = Annotated[
    StrictStr, Field(min_length=1, max_length=MAX_DISPLAY_NAME), AfterValidator(_safe_text)
]
Alias = Annotated[StrictStr, Field(pattern=ALIAS_PATTERN)]
Password = Annotated[
    StrictStr, Field(min_length=1, max_length=MAX_PASSWORD), AfterValidator(_password)
]


# -- corpos -------------------------------------------------------------------


class TlsBody(BaseModel):
    model_config = _STRICT

    mode: Literal["disable", "require", "verify-full"]
    server_name: Host | None = None


class ConnectionBody(BaseModel):
    """Destino em campos distintos. Nao existe forma de enviar um DSN."""

    model_config = _STRICT

    host: Host
    port: StrictInt = Field(ge=1, le=65_535)
    database: SafeIdentifier
    username: SafeIdentifier
    tls: TlsBody


class CredentialBody(BaseModel):
    """Senha upstream, write-only. Nunca volta em resposta alguma."""

    model_config = _STRICT

    #: `repr=False`: nem o `repr` do corpo carrega a senha (defesa em profundidade).
    password: Password = Field(repr=False)


class LimitsBody(BaseModel):
    model_config = _STRICT

    statement_timeout_ms: StrictInt = Field(ge=MIN_DS_TIMEOUT_MS, le=MAX_DS_TIMEOUT_MS)
    max_rows: StrictInt = Field(ge=1, le=MAX_DS_ROWS)
    max_sessions: StrictInt = Field(ge=1, le=MAX_DS_SESSIONS)


class DestinationPolicyBody(BaseModel):
    model_config = _STRICT

    allow_public: StrictBool
    allow_loopback: StrictBool
    allowed_hosts: Annotated[
        list[StrictStr], Field(max_length=MAX_ALLOWED_HOSTS), AfterValidator(_allowed_hosts)
    ]


class PolicyRuleBody(BaseModel):
    model_config = _STRICT

    match: StrictStr = Field(min_length=1)
    mode: MatchMode = MatchMode.CONTAINS
    case_sensitive: StrictBool = False
    transformer: StrictStr = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class PolicyExceptionBody(BaseModel):
    model_config = _STRICT

    match: StrictStr = Field(min_length=1)
    mode: MatchMode = MatchMode.EXACT
    case_sensitive: StrictBool = False


class PolicyDatabaseBody(BaseModel):
    model_config = _STRICT

    statement_timeout_ms: StrictInt = Field(
        ge=MIN_STATEMENT_TIMEOUT_MS, le=MAX_STATEMENT_TIMEOUT_MS
    )
    max_rows: StrictInt = Field(ge=MIN_MAX_ROWS, le=MAX_MAX_ROWS)


class PolicySqlBody(BaseModel):
    """`denied_functions` obrigatorio: `sql: {}` nao apaga negacoes em silencio.

    `allowed_pg_functions` e declarado so para que sua PRESENCA — inclusive
    `null` ou `[]` — vire `IMMUTABLE_FIELD`; ausente, o valor corrente e
    preservado (D-050).
    """

    model_config = _STRICT

    denied_functions: list[StrictStr]
    allowed_pg_functions: JsonOrAbsent = None

    @property
    def allowed_pg_functions_present(self) -> bool:
        return "allowed_pg_functions" in self.model_fields_set


class PolicyBody(BaseModel):
    """Politica integral do datasource. As quatro secoes sao obrigatorias."""

    model_config = _STRICT

    masking: list[PolicyRuleBody]
    exceptions: list[PolicyExceptionBody]
    database: PolicyDatabaseBody
    sql: PolicySqlBody


class DatasourceCreateRequest(BaseModel):
    """`POST /admin/v2/datasources`. Tudo explicito, inclusive `enabled`."""

    model_config = _STRICT

    expected_catalog_revision: StrictInt = Field(ge=0)
    alias: Alias
    display_name: DisplayName
    enabled: StrictBool
    connection: ConnectionBody
    credential: CredentialBody
    limits: LimitsBody
    destination_policy: DestinationPolicyBody
    policy: PolicyBody


class DatasourceTestDraftRequest(BaseModel):
    """`POST /admin/v2/datasources:test`: rascunho completo, sem efeito."""

    model_config = _STRICT

    alias: Alias
    display_name: DisplayName
    connection: ConnectionBody
    credential: CredentialBody
    limits: LimitsBody
    destination_policy: DestinationPolicyBody
    policy: PolicyBody


class DatasourceUpdateRequest(BaseModel):
    """`PUT /admin/v2/datasources/{id}`: campos nao secretos, fora a politica.

    `enabled`, `policy` e `credential` tem rotas proprias e caem no
    `extra="forbid"`. `alias` e declarado so para ser recusado.
    """

    model_config = _STRICT

    expected_revision: StrictInt = Field(ge=1)
    display_name: DisplayName
    connection: ConnectionBody
    limits: LimitsBody
    destination_policy: DestinationPolicyBody
    alias: JsonOrAbsent = None

    @property
    def alias_present(self) -> bool:
        return "alias" in self.model_fields_set


class DatasourceRotateRequest(BaseModel):
    model_config = _STRICT

    expected_revision: StrictInt = Field(ge=1)
    credential: CredentialBody


class DatasourceRevisionRequest(BaseModel):
    """Habilitar/desabilitar: so a revision do datasource."""

    model_config = _STRICT

    expected_revision: StrictInt = Field(ge=1)


class DatasourceDeleteRequest(BaseModel):
    """Remocao com confirmacao destrutiva pelo alias (spec §9.1)."""

    model_config = _STRICT

    expected_revision: StrictInt = Field(ge=1)
    confirm_alias: StrictStr = Field(min_length=1, max_length=MAX_IDENTIFIER)


class DatasourcePolicyRequest(BaseModel):
    model_config = _STRICT

    expected_revision: StrictInt = Field(ge=1)
    policy: PolicyBody


class DatasourceTestRequest(BaseModel):
    """`POST /admin/v2/datasources/{id}:test`: corpo `{}` e nada mais."""

    model_config = _STRICT


# -- respostas ----------------------------------------------------------------


class TlsView(BaseModel):
    model_config = _STRICT

    mode: str
    server_name: str | None


class ConnectionView(BaseModel):
    """Destino para o administrador. Nunca a senha nem os enderecos fixados."""

    model_config = _STRICT

    host: str
    port: int
    database: str
    username: str
    tls: TlsView


class CredentialView(BaseModel):
    """So o estado. O tipo nao admite valor, tamanho, hash, nonce ou data."""

    model_config = _STRICT

    configured: Literal[True]


class LimitsView(BaseModel):
    model_config = _STRICT

    statement_timeout_ms: int
    max_rows: int
    max_sessions: int


class EffectiveLimitsView(BaseModel):
    """O mais restritivo entre `policy.database` e `limits` (D-088)."""

    model_config = _STRICT

    statement_timeout_ms: int
    max_rows: int


class DestinationPolicyView(BaseModel):
    model_config = _STRICT

    allow_public: bool
    allow_loopback: bool
    allowed_hosts: list[str]


class LastTestView(BaseModel):
    model_config = _STRICT

    status: Literal["never", "passed", "failed"]
    checked_at: str | None


class RuntimeView(BaseModel):
    """Estado instantaneo da geracao publicada, sem destino nem sessao."""

    model_config = _STRICT

    published: bool
    generation: int | None
    sessions: int


class DatasourceSummary(BaseModel):
    model_config = _STRICT

    id: Annotated[str, Field(pattern=DATASOURCE_ID_PATTERN)]
    alias: str
    display_name: str
    enabled: bool
    revision: int
    last_test: LastTestView
    runtime: RuntimeView


class DatasourceView(DatasourceSummary):
    connection: ConnectionView
    credential: CredentialView
    limits: LimitsView
    effective_limits: EffectiveLimitsView
    destination_policy: DestinationPolicyView


class DatasourceListResponse(BaseModel):
    model_config = _STRICT

    catalog_revision: int
    datasources: list[DatasourceSummary]


class DatasourceResponse(BaseModel):
    model_config = _STRICT

    catalog_revision: int
    datasource: DatasourceView


class PolicyRuleView(BaseModel):
    model_config = _STRICT

    match: str
    mode: MatchMode
    case_sensitive: bool
    transformer: str
    config: dict[str, Any]


class PolicyExceptionView(BaseModel):
    model_config = _STRICT

    match: str
    mode: MatchMode
    case_sensitive: bool


class PolicyDatabaseView(BaseModel):
    model_config = _STRICT

    statement_timeout_ms: int
    max_rows: int


class PolicySqlView(BaseModel):
    """`allowed_pg_functions` e leitura, nunca escrita (D-050)."""

    model_config = _STRICT

    allowed_pg_functions: list[str]
    denied_functions: list[str]


class PolicyView(BaseModel):
    model_config = _STRICT

    masking: list[PolicyRuleView]
    exceptions: list[PolicyExceptionView]
    database: PolicyDatabaseView
    sql: PolicySqlView


class DatasourcePolicyResponse(BaseModel):
    model_config = _STRICT

    catalog_revision: int
    datasource_id: str
    revision: int
    policy: PolicyView


class CatalogCounts(BaseModel):
    model_config = _STRICT

    total: int
    enabled: int
    published: int


class RegistryView(BaseModel):
    model_config = _STRICT

    published: int
    sessions: int
    retired_open: int
    candidates: int
    closing: bool


class RegistryLimitsView(BaseModel):
    model_config = _STRICT

    max_sessions: int
    max_retired: int
    max_candidates: int


class V2StatusResponse(BaseModel):
    """`GET /admin/v2/status`: agregado, sem alias, destino ou segredo.

    Depois de uma falha de persistencia o catalogo exige reabertura (D-081) e
    recusa inclusive leituras: o status continua respondendo, com
    `catalog_available=false`, sem revision nem contagens do catalogo — o que
    esta em memoria pode divergir do disco —, e com o registry, que continua
    servindo as geracoes ja publicadas.
    """

    model_config = _STRICT

    catalog_available: bool
    catalog_revision: int | None
    datasources: CatalogCounts | None
    registry: RegistryView
    limits: RegistryLimitsView
    writes_blocked: bool
    dns_timeout_ms: int


class DatasourceWriteResponse(BaseModel):
    """Sucesso de uma escrita. `changed=false` so no habilitar/desabilitar ocioso."""

    model_config = _STRICT

    catalog_revision: int
    datasource_id: str
    datasource_revision: int
    changed: bool


class DatasourceDeleteResponse(BaseModel):
    model_config = _STRICT

    catalog_revision: int
    removed: Literal[True] = True


class DatasourceTestResponse(BaseModel):
    """Um teste passa ou falha com categoria; nunca persiste nem publica."""

    model_config = _STRICT

    passed: Literal[True] = True
    persisted: Literal[False] = False
    published: Literal[False] = False
