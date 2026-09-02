"""Construcao das respostas de leitura a partir do estado publicado.

Uma so regra governa este modulo: **a resposta e derivada do modelo validado do
arquivo, nunca dos objetos runtime compilados** (D-047). O caminho e sempre
`arquivo -> modelo validado -> objetos runtime`, e nunca o inverso.

A unica excecao e `GET /admin/v1/protected`, que descreve deliberadamente a
politica EFETIVA — defaults do produto mais o que a configuracao acrescentou.
E o que a secao 11.2 pede: exibir a protecao que de fato esta valendo. Os dois
convivem sem ambiguidade porque `GET /admin/v1/config` mostra o que o ARQUIVO
declara, e `GET /admin/v1/protected` mostra o que o VALIDATOR aplica.

Nenhuma referencia mutavel do runtime publicado atravessa daqui para fora:
`AdminSnapshot.document` ja e copia profunda, e `SqlPolicy` e uma dataclass
congelada sobre `frozenset` e `tuple` (D-055).

## Por que estas funcoes recebem um snapshot, e nao o servico

Uma resposta administrativa precisa ser coerente: a `revision` que ela carimba
tem de descrever o conteudo que ela devolve. Enquanto estas funcoes recebiam o
`AdminConfigService`, elas liam `service.document` e, em seguida,
`service.revision` — duas leituras da referencia publicada, com um swap
cabendo entre elas. O resultado possivel era conteudo do runtime antigo
rotulado com a revision nova, e na Etapa 9 uma escrita baseada nesse par
passaria pelo `expected_revision` e sobrescreveria uma mudanca que ninguem
leu.

Receber `AdminSnapshot` fecha isso por construcao, e nao por disciplina: quem
so tem um snapshot **nao consegue** misturar runtimes, porque nao tem como
fazer a segunda leitura. `build_status` e a unica que tambem recebe o servico,
e o usa exclusivamente para os contadores instantaneos (D-057).
"""

from __future__ import annotations

from typing import Final

from maskgw.admin.http.schemas import (
    AdminConfigResponse,
    AdminCounters,
    AdminExceptionResponse,
    AdminExceptionsResponse,
    AdminProtectedResponse,
    AdminRuleResponse,
    AdminRulesResponse,
    AdminRuntimeState,
    AdminSecrets,
    AdminStatusResponse,
    AdminTransformersResponse,
    ConfigDocument,
    DatabaseDocument,
    ExceptionDocument,
    ExceptionView,
    ProtectedSession,
    RuleDocument,
    RuleView,
    SecretState,
    SqlDocument,
    TransformerView,
)
from maskgw.admin.service import AdminConfigService, AdminSnapshot
from maskgw.config.models import ExceptionConfig, MaskingFileConfig, RuleConfig
from maskgw.masking.transformers.registry import TransformerRegistry, build_default_registry
from maskgw.secretsource import SecretProvider
from maskgw.sql.policy import SqlPolicy

#: As quatro regras do validator, por tipo de no da AST (D-031). Texto fixo:
#: descrevem a politica, e nao a consulta de ninguem.
#:
#: A regra 4 existe porque `SELECT 1 INTO nova` parseia como `SelectStmt` e
#: **cria uma tabela**, e `SELECT ... FOR UPDATE` trava linhas. Raiz SELECT nao
#: basta.
VALIDATOR_RULES: Final[tuple[str, ...]] = (
    "exactly one executable statement",
    "the root node must be a SELECT statement",
    "no other statement node anywhere in the tree, including nested CTEs",
    "INTO and locking clauses are rejected at any depth",
)

#: Ordem do pipeline por coluna do result set.
PIPELINE: Final[tuple[str, ...]] = ("DERIVED", "EXCEPTION", "MASKING", "ORIGINAL")

#: Coluna sem correspondencia passa em claro. Consequencia direta do modelo,
#: documentada como risco aceito; mudar exige aprovacao propria.
UNMATCHED_POLICY: Final = "allow"

#: `pg_` e negado por default; a allowlist e a excecao explicita (D-027).
PG_NAMESPACE_DEFAULT: Final = "deny"

#: Onde o `statement_timeout` e aplicado. Nao e o Gateway que o conta: ele viaja
#: em `options` do DSN e e conferido em `pg_settings` apos conectar (D-028).
STATEMENT_TIMEOUT_ENFORCED_BY: Final = "postgresql"


def secret_state(secrets: SecretProvider, name: str) -> SecretState:
    """`configured` ou `missing`. O valor nunca sai daqui, nem derivado dele."""
    return SecretState.CONFIGURED if secrets.get(name) is not None else SecretState.MISSING


def build_status(
    snapshot: AdminSnapshot,
    service: AdminConfigService,
    *,
    secrets: SecretProvider,
    hmac_key_env: str,
    database_dsn_env: str,
) -> AdminStatusResponse:
    """`GET /admin/v1/status`.

    A identidade da configuracao — `revision` e `adopted`, no topo e dentro de
    `runtime` — vem TODA do snapshot, e `adopted` e derivado da revision
    capturada. Os contadores continuam sendo leituras instantaneas: eles nao
    descrevem uma configuracao, e sim atividade do processo desde o start, e um
    swap entre a captura e a contagem nao produz afirmacao falsa alguma.
    """
    return AdminStatusResponse(
        revision=snapshot.revision,
        adopted=snapshot.adopted,
        runtime=AdminRuntimeState(
            revision=snapshot.revision,
            retired_runtimes_open=service.retired_runtimes_open,
        ),
        counters=AdminCounters(
            queries_total=service.queries_total,
            admin_operations_total=service.operations_total,
        ),
        secrets=AdminSecrets(
            hmac_sha256_key=secret_state(secrets, hmac_key_env),
            # Sempre `configured`: sem token o processo nao teria subido.
            admin_token=SecretState.CONFIGURED,
            database_dsn=secret_state(secrets, database_dsn_env),
        ),
    )


def build_config(snapshot: AdminSnapshot) -> AdminConfigResponse:
    """`GET /admin/v1/config`, a partir da copia profunda do documento."""
    return AdminConfigResponse(
        revision=snapshot.revision,
        adopted=snapshot.adopted,
        config=_config_document(snapshot.document),
    )


def build_rules(snapshot: AdminSnapshot) -> AdminRulesResponse:
    """`GET /admin/v1/rules`, na ordem de avaliacao do arquivo."""
    return AdminRulesResponse(
        revision=snapshot.revision,
        adopted=snapshot.adopted,
        rules=[
            _rule_view(item, position) for position, item in enumerate(snapshot.document.masking)
        ],
    )


def find_rule(snapshot: AdminSnapshot, rule_id: str) -> AdminRuleResponse | None:
    """`GET /admin/v1/rules/{rule_id}`, ou None quando nao existe.

    Numa configuracao ainda nao adotada todo `id` e nulo, entao nenhuma busca
    encontra nada — e a resposta e `NOT_FOUND`, nao um erro especial. Nao ha o
    que apontar antes de a adocao atribuir os IDs.

    A busca percorre o documento DO SNAPSHOT, e o achado e rotulado com a
    revision dele. Uma regra removida ou alterada por um reload concorrente nao
    produz meia-resposta: ou o snapshot e anterior ao reload, e a regra aparece
    com a revision antiga, ou e posterior, e o resultado e `NOT_FOUND` — nunca
    a regra antiga sob a revision nova.
    """
    for position, item in enumerate(snapshot.document.masking):
        if item.id is not None and item.id == rule_id:
            return AdminRuleResponse(
                revision=snapshot.revision,
                adopted=snapshot.adopted,
                rule=_rule_view(item, position),
            )
    return None


def build_exceptions(snapshot: AdminSnapshot) -> AdminExceptionsResponse:
    """`GET /admin/v1/exceptions`."""
    return AdminExceptionsResponse(
        revision=snapshot.revision,
        adopted=snapshot.adopted,
        exceptions=[
            _exception_view(item, position)
            for position, item in enumerate(snapshot.document.exceptions)
        ],
    )


def find_exception(snapshot: AdminSnapshot, exception_id: str) -> AdminExceptionResponse | None:
    """`GET /admin/v1/exceptions/{exception_id}`, ou None quando nao existe."""
    for position, item in enumerate(snapshot.document.exceptions):
        if item.id is not None and item.id == exception_id:
            return AdminExceptionResponse(
                revision=snapshot.revision,
                adopted=snapshot.adopted,
                exception=_exception_view(item, position),
            )
    return None


def build_transformers(
    snapshot: AdminSnapshot,
    *,
    registry: TransformerRegistry | None = None,
) -> AdminTransformersResponse:
    """`GET /admin/v1/transformers`: o catalogo fechado, so nome e parametros.

    O catalogo e do PRODUTO, e nao da configuracao: ele nao muda com um reload.
    A `revision` vem do snapshot ainda assim, para que a resposta diga sobre
    qual estado ela foi produzida.
    """
    catalog = registry if registry is not None else build_default_registry()
    return AdminTransformersResponse(
        revision=snapshot.revision,
        transformers=[
            TransformerView(
                name=spec.name,
                required_parameters=list(spec.required_parameters),
                optional_parameters=list(spec.optional_parameters),
            )
            for spec in catalog.specs()
        ],
    )


def build_protected(snapshot: AdminSnapshot) -> AdminProtectedResponse:
    """`GET /admin/v1/protected`: a politica EFETIVA, exibida e nao editavel.

    Politica e revision saem do MESMO runtime. Uma politica antiga rotulada com
    a revision nova afirmaria protecoes estruturais que ja nao estao valendo —
    e e justamente esta rota que o administrador consulta para conferi-las.
    """
    policy: SqlPolicy = snapshot.sql_policy
    return AdminProtectedResponse(
        revision=snapshot.revision,
        denied_relations=sorted(policy.denied_relations),
        pg_namespace_default=PG_NAMESPACE_DEFAULT,
        allowed_pg_functions=sorted(policy.allowed_pg_functions),
        denied_functions=sorted(policy.denied_functions),
        denied_function_prefixes=sorted(policy.denied_prefixes),
        validator_rules=list(VALIDATOR_RULES),
        session=ProtectedSession(
            read_only=True,
            statement_timeout_enforced_by=STATEMENT_TIMEOUT_ENFORCED_BY,
            provenance_capability_required=True,
        ),
        pipeline=list(PIPELINE),
        unmatched_policy=UNMATCHED_POLICY,
        editable=False,
    )


def _config_document(document: MaskingFileConfig) -> ConfigDocument:
    return ConfigDocument(
        revision=document.revision,
        masking=[_rule_document(item) for item in document.masking],
        exceptions=[_exception_document(item) for item in document.exceptions],
        database=DatabaseDocument(
            statement_timeout_ms=document.database.statement_timeout_ms,
            max_rows=document.database.max_rows,
        ),
        sql=SqlDocument(
            allowed_pg_functions=list(document.sql.allowed_pg_functions),
            denied_functions=list(document.sql.denied_functions),
        ),
    )


def _rule_document(item: RuleConfig) -> RuleDocument:
    return RuleDocument(
        id=item.id,
        match=item.match,
        mode=item.mode,
        case_sensitive=item.case_sensitive,
        transformer=item.transformer,
        # `dict(...)` sobre a copia profunda: nem o dicionario externo e
        # compartilhado com o documento que acabou de ser copiado.
        config=dict(item.config),
    )


def _rule_view(item: RuleConfig, position: int) -> RuleView:
    return RuleView(
        id=item.id,
        match=item.match,
        mode=item.mode,
        case_sensitive=item.case_sensitive,
        transformer=item.transformer,
        config=dict(item.config),
        position=position,
    )


def _exception_document(item: ExceptionConfig) -> ExceptionDocument:
    return ExceptionDocument(
        id=item.id,
        match=item.match,
        mode=item.mode,
        case_sensitive=item.case_sensitive,
    )


def _exception_view(item: ExceptionConfig, position: int) -> ExceptionView:
    return ExceptionView(
        id=item.id,
        match=item.match,
        mode=item.mode,
        case_sensitive=item.case_sensitive,
        position=position,
    )


__all__ = [
    "PG_NAMESPACE_DEFAULT",
    "PIPELINE",
    "STATEMENT_TIMEOUT_ENFORCED_BY",
    "UNMATCHED_POLICY",
    "VALIDATOR_RULES",
    "build_config",
    "build_exceptions",
    "build_protected",
    "build_rules",
    "build_status",
    "build_transformers",
    "find_exception",
    "find_rule",
    "secret_state",
]
