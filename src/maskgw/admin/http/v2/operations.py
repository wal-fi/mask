"""Traducao da Admin API v2 para o coordenador de datasources (D-093/D-094).

Nada aqui decide ordem, lock, candidato, persistencia ou publicacao: tudo isso
e do `DatasourceRuntimeService` (D-091), e cada escrita e UMA chamada a ele.
Este modulo faz tres coisas e nenhuma outra:

1. converte o corpo ja validado num `DatasourceDraft` — ou, para escrever sobre
   um datasource existente, numa FUNCAO que o coordenador chama com o registro
   lido sob a propria secao critica (sem TOCTOU, como D-059);
2. monta as leituras a partir de UM snapshot do catalogo por resposta, de modo
   que `catalog_revision` e conteudo descrevam o mesmo estado (D-057). O estado
   do registry e lido a parte e e instantaneo: sessoes e geracoes mudam sem
   commit do catalogo;
3. traduz TODA falha para uma categoria fechada, levantando o erro sanitizado
   FORA do `except` (D-017): nem `__cause__` nem `__context__` alcancam a
   excecao interna, que pode carregar destino ou detalhe do PostgreSQL.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, Final, TypeVar

from maskgw.admin.errors import AdminErrorCategory
from maskgw.admin.http.v2.errors import (
    DatasourceAdminError,
    DatasourceErrorCategory,
    V2Category,
    raise_v2_error,
)
from maskgw.admin.http.v2.schemas import (
    CatalogCounts,
    ConnectionBody,
    ConnectionView,
    CredentialView,
    DatasourceCreateRequest,
    DatasourceDeleteRequest,
    DatasourceDeleteResponse,
    DatasourceListResponse,
    DatasourcePolicyRequest,
    DatasourcePolicyResponse,
    DatasourceResponse,
    DatasourceRevisionRequest,
    DatasourceRotateRequest,
    DatasourceSummary,
    DatasourceTestDraftRequest,
    DatasourceTestResponse,
    DatasourceUpdateRequest,
    DatasourceView,
    DatasourceWriteResponse,
    DestinationPolicyBody,
    DestinationPolicyView,
    EffectiveLimitsView,
    LastTestView,
    LimitsBody,
    LimitsView,
    PolicyBody,
    PolicyDatabaseView,
    PolicyExceptionView,
    PolicyRuleView,
    PolicySqlView,
    PolicyView,
    RegistryLimitsView,
    RegistryView,
    RuntimeView,
    TlsView,
    V2StatusResponse,
)
from maskgw.config.models import MaskingFileConfig
from maskgw.datasource.destination import DestinationValidationError
from maskgw.datasource.models import (
    DATASOURCE_ID_PATTERN,
    DatasourceDraft,
    DatasourceIdError,
    DatasourceLimits,
    DatasourcePolicy,
    DatasourceRecord,
    DatasourceValidationError,
    DestinationPolicy,
    TlsSettings,
)
from maskgw.datasource.resolver import DNS_TIMEOUT_SECONDS
from maskgw.datasource.store import (
    CatalogOutcomeUncertainError,
    CatalogRevisionConflictError,
    CatalogWriteError,
)
from maskgw.runtime.candidate import CandidateFailure, DatasourceCandidateError
from maskgw.runtime.datasource_service import (
    DatasourceAliasConflictError,
    DatasourceDisabledError,
    DatasourceNotFoundError,
    DatasourceRenameError,
    DatasourceRevisionConflictError,
    DatasourceServiceBlockedError,
    DatasourceServiceClosedError,
    DatasourceWriteProbe,
    draft_from_record,
)
from maskgw.runtime.datasources import (
    DatasourceBusyError,
    DatasourceRegistryClosedError,
    GenerationStatus,
)

if TYPE_CHECKING:
    from maskgw.runtime.datasource_service import DatasourceRuntime

_T = TypeVar("_T")

_DATASOURCE_ID_RE: Final = re.compile(DATASOURCE_ID_PATTERN)

_CANDIDATE_CATEGORY: Final[dict[CandidateFailure, DatasourceErrorCategory]] = {
    CandidateFailure.DESTINATION: DatasourceErrorCategory.DATASOURCE_DESTINATION_REJECTED,
    CandidateFailure.POLICY: DatasourceErrorCategory.DATASOURCE_POLICY_INVALID,
    CandidateFailure.CONNECTION: DatasourceErrorCategory.DATASOURCE_CONNECTION_FAILED,
    CandidateFailure.CAPABILITY: DatasourceErrorCategory.DATASOURCE_CAPABILITY_MISSING,
}


def canonical_datasource_id(value: str) -> str | None:
    """O ID do path so quando casa `dso_<32 hex>`; senao `None`."""
    return value if _DATASOURCE_ID_RE.fullmatch(value) else None


def _require_id(value: str) -> str:
    """ID malformado e `NOT_FOUND`, como na v1: nao ha oraculo de formato."""
    canonical = canonical_datasource_id(value)
    if canonical is None:
        raise_v2_error(DatasourceAdminError(AdminErrorCategory.NOT_FOUND))
    return canonical


def _immutable() -> DatasourceAdminError:
    return DatasourceAdminError(AdminErrorCategory.IMMUTABLE_FIELD)


#: Excecao -> categoria, do especifico ao geral: a PRIMEIRA que casar decide.
#: `DestinationValidationError` antes de `DatasourceValidationError` (subclasse),
#: os erros proprios do coordenador antes de `CatalogStoreError`.
_CATEGORY_BY_EXCEPTION: Final[tuple[tuple[tuple[type[BaseException], ...], V2Category], ...]] = (
    ((CatalogRevisionConflictError,), AdminErrorCategory.REVISION_CONFLICT),
    ((DatasourceNotFoundError, DatasourceIdError), AdminErrorCategory.NOT_FOUND),
    ((DatasourceAliasConflictError,), DatasourceErrorCategory.ALIAS_CONFLICT),
    ((DatasourceRenameError,), AdminErrorCategory.IMMUTABLE_FIELD),
    ((DatasourceDisabledError,), DatasourceErrorCategory.DATASOURCE_DISABLED),
    ((DestinationValidationError,), DatasourceErrorCategory.DATASOURCE_DESTINATION_REJECTED),
    ((DatasourceValidationError,), AdminErrorCategory.SCHEMA_INVALID),
    ((DatasourceBusyError,), DatasourceErrorCategory.DATASOURCE_BUSY),
    ((DatasourceServiceBlockedError,), DatasourceErrorCategory.CATALOG_BLOCKED),
    (
        (DatasourceServiceClosedError, DatasourceRegistryClosedError),
        DatasourceErrorCategory.DATASOURCE_SERVICE_UNAVAILABLE,
    ),
    ((CatalogOutcomeUncertainError,), DatasourceErrorCategory.CATALOG_OUTCOME_UNCERTAIN),
    ((CatalogWriteError,), DatasourceErrorCategory.CATALOG_WRITE_ERROR),
)


#: Categorias que, com o catalogo JA bloqueado antes da operacao, sao o proprio
#: bloqueio — e nao uma falha nova de escrita ou um erro interno.
_BLOCKED_OVERRIDES: Final = frozenset(
    {DatasourceErrorCategory.CATALOG_WRITE_ERROR, AdminErrorCategory.INTERNAL_ERROR}
)


def categorize(exc: BaseException, *, became_blocked: bool) -> tuple[V2Category, int | None]:
    """Categoria fechada de uma falha e, num conflito, a revision observada.

    Uma falha que envenenou o store sem ser `CatalogWriteError` — qualquer erro
    dentro do commit, antes do replace — e reconhecida pela CONDICAO (o
    coordenador ficou bloqueado nesta operacao), como em D-091: nada foi
    aplicado, e o erro e de escrita do catalogo. O resto e `INTERNAL_ERROR`.
    """
    if isinstance(exc, DatasourceRevisionConflictError):
        return AdminErrorCategory.REVISION_CONFLICT, exc.current_revision
    if isinstance(exc, DatasourceCandidateError):
        return _CANDIDATE_CATEGORY[exc.category], None
    for types, category in _CATEGORY_BY_EXCEPTION:
        if isinstance(exc, types):
            return category, None
    if became_blocked:
        return DatasourceErrorCategory.CATALOG_WRITE_ERROR, None
    return AdminErrorCategory.INTERNAL_ERROR, None


def _tls(body: ConnectionBody) -> TlsSettings:
    return TlsSettings(mode=body.tls.mode, server_name=body.tls.server_name)


def _limits(body: LimitsBody) -> DatasourceLimits:
    return DatasourceLimits(
        statement_timeout_ms=body.statement_timeout_ms,
        max_rows=body.max_rows,
        max_sessions=body.max_sessions,
    )


def _destination_policy(body: DestinationPolicyBody) -> DestinationPolicy:
    return DestinationPolicy(
        allow_public=body.allow_public,
        allow_loopback=body.allow_loopback,
        allowed_hosts=tuple(body.allowed_hosts),
    )


def _policy(body: PolicyBody, *, allowed_pg_functions: list[str]) -> DatasourcePolicy:
    """Politica integral, sem `revision` nem IDs; o allowlist vem do servidor."""
    if body.sql.allowed_pg_functions_present:
        raise_v2_error(_immutable())
    return DatasourcePolicy.from_mapping(
        {
            "masking": [rule.model_dump(mode="json") for rule in body.masking],
            "exceptions": [item.model_dump(mode="json") for item in body.exceptions],
            "database": body.database.model_dump(mode="json"),
            "sql": {
                "allowed_pg_functions": list(allowed_pg_functions),
                "denied_functions": list(body.sql.denied_functions),
            },
        }
    )


def _current_allowed(record: DatasourceRecord) -> list[str]:
    sql = record.policy.to_mapping().get("sql", {})
    allowed = sql.get("allowed_pg_functions", []) if isinstance(sql, dict) else []
    return [str(item) for item in allowed] if isinstance(allowed, list) else []


def _draft(  # noqa: PLR0913 - campos de um rascunho, todos keyword-only
    *,
    alias: str,
    display_name: str,
    enabled: bool,
    connection: ConnectionBody,
    limits: LimitsBody,
    destination_policy: DestinationPolicyBody,
    policy: DatasourcePolicy,
    resolved_addresses: tuple[str, ...] = (),
) -> DatasourceDraft:
    return DatasourceDraft(
        alias=alias,
        display_name=display_name,
        host=connection.host,
        port=connection.port,
        database=connection.database,
        username=connection.username,
        enabled=enabled,
        tls=_tls(connection),
        policy=policy,
        limits=_limits(limits),
        destination_policy=_destination_policy(destination_policy),
        resolved_addresses=resolved_addresses,
    )


def _file_config(record: DatasourceRecord) -> MaskingFileConfig:
    return MaskingFileConfig.model_validate(record.policy.to_mapping())


def _effective(record: DatasourceRecord, config: MaskingFileConfig) -> EffectiveLimitsView:
    """D-088, pela mesma regra de `effective_database_settings`, sem compilar."""
    return EffectiveLimitsView(
        statement_timeout_ms=min(
            config.database.statement_timeout_ms, record.limits.statement_timeout_ms
        ),
        max_rows=min(config.database.max_rows, record.limits.max_rows),
    )


def _runtime(record: DatasourceRecord, published: dict[str, GenerationStatus]) -> RuntimeView:
    generation = published.get(record.id)
    return RuntimeView(
        published=generation is not None,
        generation=None if generation is None else generation.generation,
        sessions=0 if generation is None else generation.sessions,
    )


def _summary(record: DatasourceRecord, published: dict[str, GenerationStatus]) -> DatasourceSummary:
    return DatasourceSummary(
        id=record.id,
        alias=record.alias,
        display_name=record.display_name,
        enabled=record.enabled,
        revision=record.revision,
        last_test=LastTestView(
            status=record.last_test.status, checked_at=record.last_test.checked_at
        ),
        runtime=_runtime(record, published),
    )


def _view(record: DatasourceRecord, published: dict[str, GenerationStatus]) -> DatasourceView:
    summary = _summary(record, published)
    return DatasourceView(
        **summary.model_dump(),
        connection=ConnectionView(
            host=record.host,
            port=record.port,
            database=record.database,
            username=record.username,
            tls=TlsView(mode=record.tls.mode, server_name=record.tls.server_name),
        ),
        credential=CredentialView(configured=True),
        limits=LimitsView(
            statement_timeout_ms=record.limits.statement_timeout_ms,
            max_rows=record.limits.max_rows,
            max_sessions=record.limits.max_sessions,
        ),
        effective_limits=_effective(record, _file_config(record)),
        destination_policy=DestinationPolicyView(
            allow_public=record.destination_policy.allow_public,
            allow_loopback=record.destination_policy.allow_loopback,
            allowed_hosts=list(record.destination_policy.allowed_hosts),
        ),
    )


def _policy_view(record: DatasourceRecord) -> PolicyView:
    config = _file_config(record)
    return PolicyView(
        masking=[
            PolicyRuleView(
                match=rule.match,
                mode=rule.mode,
                case_sensitive=rule.case_sensitive,
                transformer=rule.transformer,
                config=dict(rule.config),
            )
            for rule in config.masking
        ],
        exceptions=[
            PolicyExceptionView(
                match=item.match, mode=item.mode, case_sensitive=item.case_sensitive
            )
            for item in config.exceptions
        ],
        database=PolicyDatabaseView(
            statement_timeout_ms=config.database.statement_timeout_ms,
            max_rows=config.database.max_rows,
        ),
        sql=PolicySqlView(
            allowed_pg_functions=list(config.sql.allowed_pg_functions),
            denied_functions=list(config.sql.denied_functions),
        ),
    )


class DatasourceAdmin:
    """As operacoes v2 sobre UM runtime de datasources. Sem estado proprio."""

    __slots__ = ("_runtime",)

    def __init__(self, runtime: DatasourceRuntime) -> None:
        self._runtime = runtime

    # -- execucao com traducao -------------------------------------------

    def _run(self, operation: Callable[[], _T]) -> _T:
        """Executa e traduz; o erro sanitizado sai fora do `except` (D-017).

        Com o catalogo ja bloqueado (D-081/D-091), o store recusa ate leituras;
        a falha resultante e `CATALOG_BLOCKED`, e nao um erro de escrita desta
        operacao. As demais categorias — por exemplo, a de um teste de
        rascunho, que continua permitido — sao preservadas.
        """
        blocked_before = self._blocked()
        try:
            return operation()
        except DatasourceAdminError:
            raise
        except Exception as exc:
            category, current = categorize(
                exc, became_blocked=self._blocked() and not blocked_before
            )
            if blocked_before and category in _BLOCKED_OVERRIDES:
                category = DatasourceErrorCategory.CATALOG_BLOCKED
        # Fora do `except`: `__cause__` e `__context__` ficam nulos (D-017).
        raise DatasourceAdminError(category, current_revision=current) from None

    def _blocked(self) -> bool:
        return self._runtime.service.blocked or self._runtime.store.requires_reopen

    def _published(self) -> dict[str, GenerationStatus]:
        return {item.datasource_id: item for item in self._runtime.registry.status().published}

    # -- leituras ---------------------------------------------------------

    def status(self) -> V2StatusResponse:
        def read() -> V2StatusResponse:
            registry = self._runtime.registry.status()
            limits = self._runtime.registry.limits
            catalog_available = not self._runtime.store.requires_reopen
            revision: int | None = None
            counts: CatalogCounts | None = None
            if catalog_available:
                snapshot = self._runtime.store.snapshot()
                published_ids = {item.datasource_id for item in registry.published}
                revision = snapshot.catalog_revision
                counts = CatalogCounts(
                    total=len(snapshot.datasources),
                    enabled=sum(1 for record in snapshot.datasources if record.enabled),
                    published=sum(
                        1 for record in snapshot.datasources if record.id in published_ids
                    ),
                )
            return V2StatusResponse(
                catalog_available=catalog_available,
                catalog_revision=revision,
                datasources=counts,
                registry=RegistryView(
                    published=len(registry.published),
                    sessions=registry.sessions,
                    retired_open=registry.retired_open,
                    candidates=registry.candidates,
                    closing=registry.closing,
                ),
                limits=RegistryLimitsView(
                    max_sessions=limits.max_sessions,
                    max_retired=limits.max_retired,
                    max_candidates=limits.max_candidates,
                ),
                writes_blocked=self._blocked(),
                dns_timeout_ms=int(DNS_TIMEOUT_SECONDS * 1000),
            )

        return self._run(read)

    def list(self) -> DatasourceListResponse:
        def read() -> DatasourceListResponse:
            snapshot = self._runtime.store.snapshot()
            published = self._published()
            return DatasourceListResponse(
                catalog_revision=snapshot.catalog_revision,
                datasources=[_summary(record, published) for record in snapshot.datasources],
            )

        return self._run(read)

    def _record(self, datasource_id: str) -> tuple[int, DatasourceRecord]:
        snapshot = self._runtime.store.snapshot()
        for record in snapshot.datasources:
            if record.id == datasource_id:
                return snapshot.catalog_revision, record
        raise DatasourceNotFoundError

    def get(self, datasource_id: str) -> DatasourceResponse:
        canonical = _require_id(datasource_id)

        def read() -> DatasourceResponse:
            catalog_revision, record = self._record(canonical)
            return DatasourceResponse(
                catalog_revision=catalog_revision, datasource=_view(record, self._published())
            )

        return self._run(read)

    def policy(self, datasource_id: str) -> DatasourcePolicyResponse:
        canonical = _require_id(datasource_id)

        def read() -> DatasourcePolicyResponse:
            catalog_revision, record = self._record(canonical)
            return DatasourcePolicyResponse(
                catalog_revision=catalog_revision,
                datasource_id=record.id,
                revision=record.revision,
                policy=_policy_view(record),
            )

        return self._run(read)

    # -- testes sem efeito ----------------------------------------------

    def test_draft(self, body: DatasourceTestDraftRequest) -> DatasourceTestResponse:
        def run() -> DatasourceTestResponse:
            draft = _draft(
                alias=body.alias,
                display_name=body.display_name,
                enabled=True,
                connection=body.connection,
                limits=body.limits,
                destination_policy=body.destination_policy,
                policy=_policy(body.policy, allowed_pg_functions=[]),
            )
            self._runtime.service.test_draft(draft, body.credential.password)
            return DatasourceTestResponse()

        return self._run(run)

    def test(self, datasource_id: str) -> DatasourceTestResponse:
        canonical = _require_id(datasource_id)

        def run() -> DatasourceTestResponse:
            self._runtime.service.test_datasource(canonical)
            return DatasourceTestResponse()

        return self._run(run)

    # -- escritas ---------------------------------------------------------

    def create(
        self, body: DatasourceCreateRequest, probe: DatasourceWriteProbe
    ) -> DatasourceWriteResponse:
        def run() -> DatasourceWriteResponse:
            draft = _draft(
                alias=body.alias,
                display_name=body.display_name,
                enabled=body.enabled,
                connection=body.connection,
                limits=body.limits,
                destination_policy=body.destination_policy,
                policy=_policy(body.policy, allowed_pg_functions=[]),
            )
            record = self._runtime.service.create(
                draft,
                body.credential.password,
                expected_revision=body.expected_catalog_revision,
                probe=probe,
            )
            return _write_response(record, probe, changed=True)

        return self._run(run)

    def update(
        self, datasource_id: str, body: DatasourceUpdateRequest, probe: DatasourceWriteProbe
    ) -> DatasourceWriteResponse:
        canonical = _require_id(datasource_id)
        if body.alias_present:
            raise_v2_error(_immutable())

        def mutate(current: DatasourceRecord) -> DatasourceDraft:
            # O conjunto DNS fixado so e mantido com o MESMO destino (D-084):
            # outro host/porta e resolvido e validado de novo pelo candidato.
            same_destination = (body.connection.host, body.connection.port) == (
                current.host,
                current.port,
            )
            return _draft(
                alias=current.alias,
                display_name=body.display_name,
                enabled=current.enabled,
                connection=body.connection,
                limits=body.limits,
                destination_policy=body.destination_policy,
                policy=current.policy,
                resolved_addresses=current.resolved_addresses if same_destination else (),
            )

        def run() -> DatasourceWriteResponse:
            record = self._runtime.service.update(
                canonical,
                mutate,
                expected_datasource_revision=body.expected_revision,
                probe=probe,
            )
            return _write_response(record, probe, changed=True)

        return self._run(run)

    def put_policy(
        self, datasource_id: str, body: DatasourcePolicyRequest, probe: DatasourceWriteProbe
    ) -> DatasourceWriteResponse:
        canonical = _require_id(datasource_id)
        if body.policy.sql.allowed_pg_functions_present:
            raise_v2_error(_immutable())

        def mutate(current: DatasourceRecord) -> DatasourceDraft:
            # O allowlist vem do registro lido SOB o lock: preservado em
            # conteudo e ordem, nunca do corpo (D-050).
            policy = _policy(body.policy, allowed_pg_functions=_current_allowed(current))
            return replace(draft_from_record(current), policy=policy)

        def run() -> DatasourceWriteResponse:
            record = self._runtime.service.update(
                canonical,
                mutate,
                expected_datasource_revision=body.expected_revision,
                probe=probe,
            )
            return _write_response(record, probe, changed=True)

        return self._run(run)

    def rotate(
        self, datasource_id: str, body: DatasourceRotateRequest, probe: DatasourceWriteProbe
    ) -> DatasourceWriteResponse:
        canonical = _require_id(datasource_id)

        def run() -> DatasourceWriteResponse:
            record = self._runtime.service.rotate_secret(
                canonical,
                body.credential.password,
                expected_datasource_revision=body.expected_revision,
                probe=probe,
            )
            return _write_response(record, probe, changed=True)

        return self._run(run)

    def set_enabled(
        self,
        datasource_id: str,
        body: DatasourceRevisionRequest,
        probe: DatasourceWriteProbe,
        *,
        enabled: bool,
    ) -> DatasourceWriteResponse:
        canonical = _require_id(datasource_id)

        def run() -> DatasourceWriteResponse:
            record = self._runtime.service.set_enabled(
                canonical,
                enabled,
                expected_datasource_revision=body.expected_revision,
                probe=probe,
            )
            changed = probe.catalog_revision_after != probe.catalog_revision_before
            return _write_response(record, probe, changed=changed)

        return self._run(run)

    def delete(
        self, datasource_id: str, body: DatasourceDeleteRequest, probe: DatasourceWriteProbe
    ) -> DatasourceDeleteResponse:
        canonical = _require_id(datasource_id)

        def confirm(current: DatasourceRecord) -> None:
            # Lido sob o lock, depois da revision. O alias recebido nao volta
            # em resposta nem em auditoria.
            if current.alias != body.confirm_alias:
                raise_v2_error(DatasourceAdminError(DatasourceErrorCategory.CONFIRMATION_MISMATCH))

        def run() -> DatasourceDeleteResponse:
            self._runtime.service.remove(
                canonical,
                expected_datasource_revision=body.expected_revision,
                probe=probe,
                confirm=confirm,
            )
            return DatasourceDeleteResponse(catalog_revision=_after(probe))

        return self._run(run)


def _after(probe: DatasourceWriteProbe) -> int:
    after = probe.catalog_revision_after
    if after is None:  # pragma: no cover - o coordenador sempre preenche no sucesso
        msg = "revision publicada ausente"
        raise RuntimeError(msg)
    return after


def _write_response(
    record: DatasourceRecord, probe: DatasourceWriteProbe, *, changed: bool
) -> DatasourceWriteResponse:
    return DatasourceWriteResponse(
        catalog_revision=_after(probe),
        datasource_id=record.id,
        datasource_revision=record.revision,
        changed=changed,
    )


__all__ = ["DatasourceAdmin", "canonical_datasource_id", "categorize"]
