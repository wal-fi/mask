"""Auditoria da Admin API v2 de datasources (Fase 9, Etapa 4, D-095).

Registro FECHADO proprio, separado de `AdminAudit`. O `AdminAudit` da Fase 7 e o
contrato da v1 (secao 13.2), e seus enums alimentam o gerador da UI v1: estende-
lo mudaria artefatos da v1 e afrouxaria invariantes que valem para ela. Aqui os
mesmos nove nomes de campo carregam enums proprios, validados na construcao.

O que entra e so metadata: um `request_id` gerado pelo servidor, a operacao, o
ID opaco `dso_...` do alvo, o desfecho, as revisions do CATALOGO observadas
dentro da secao critica, a duracao e uma categoria fechada. Nunca alias, nome de
apresentacao, host, porta, database, usuario, senha, ciphertext, endereco DNS,
politica, corpo de requisicao ou mensagem de excecao — nao ha parametro para
isso (spec §13).

Este modulo nao importa `logging`: quem emite e `AuditLog.record_datasource_admin`,
em `audit/log.py`, o unico modulo autorizado.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Final

from maskgw.audit.log import AdminOutcome


class DatasourceOperationName(StrEnum):
    """As operacoes auditaveis da v2: uma por rota que alcanca o handler."""

    CREATE = "datasource_create"
    UPDATE = "datasource_update"
    ROTATE_CREDENTIAL = "datasource_rotate_credential"
    ENABLE = "datasource_enable"
    DISABLE = "datasource_disable"
    DELETE = "datasource_delete"
    POLICY_PUT = "datasource_policy_put"
    TEST = "datasource_test"
    TEST_DRAFT = "datasource_test_draft"


class DatasourceTargetKind(StrEnum):
    """Unico alvo da v2."""

    DATASOURCE = "datasource"


class DatasourceAuditErrorCategory(StrEnum):
    """Espelho fechado das categorias que um handler v2 pode produzir.

    Declarado aqui, no modulo neutro, para nao criar o ciclo `audit -> admin`.
    A paridade EXATA com as categorias emitidas pela v2 e provada por teste.
    """

    # Compartilhadas com a v1 (mesmos valores, mesmos status).
    REVISION_CONFLICT = "REVISION_CONFLICT"
    NOT_FOUND = "NOT_FOUND"
    IMMUTABLE_FIELD = "IMMUTABLE_FIELD"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    # Proprias da v2.
    ALIAS_CONFLICT = "ALIAS_CONFLICT"
    CONFIRMATION_MISMATCH = "CONFIRMATION_MISMATCH"
    DATASOURCE_BUSY = "DATASOURCE_BUSY"
    DATASOURCE_DISABLED = "DATASOURCE_DISABLED"
    DATASOURCE_DESTINATION_REJECTED = "DATASOURCE_DESTINATION_REJECTED"
    DATASOURCE_POLICY_INVALID = "DATASOURCE_POLICY_INVALID"
    DATASOURCE_CONNECTION_FAILED = "DATASOURCE_CONNECTION_FAILED"
    DATASOURCE_CAPABILITY_MISSING = "DATASOURCE_CAPABILITY_MISSING"
    CATALOG_WRITE_ERROR = "CATALOG_WRITE_ERROR"
    CATALOG_OUTCOME_UNCERTAIN = "CATALOG_OUTCOME_UNCERTAIN"
    CATALOG_BLOCKED = "CATALOG_BLOCKED"
    DATASOURCE_SERVICE_UNAVAILABLE = "DATASOURCE_SERVICE_UNAVAILABLE"


#: Falhas do servidor (5xx) -> `error`; as demais sao recusas (4xx) ->
#: `rejected`. Paridade com a tabela de status da v2 provada por teste.
_SERVER_ERROR_CATEGORIES: Final = frozenset(
    {
        DatasourceAuditErrorCategory.INTERNAL_ERROR,
        DatasourceAuditErrorCategory.CATALOG_WRITE_ERROR,
        DatasourceAuditErrorCategory.CATALOG_OUTCOME_UNCERTAIN,
        DatasourceAuditErrorCategory.CATALOG_BLOCKED,
        DatasourceAuditErrorCategory.DATASOURCE_SERVICE_UNAVAILABLE,
    }
)

DATASOURCE_CATEGORY_OUTCOME: Final[dict[DatasourceAuditErrorCategory, AdminOutcome]] = {
    category: (
        AdminOutcome.ERROR if category in _SERVER_ERROR_CATEGORIES else AdminOutcome.REJECTED
    )
    for category in DatasourceAuditErrorCategory
}

#: Testes de candidato nao leem nem publicam revision: sempre `None`.
_TEST_OPERATIONS: Final = frozenset(
    {DatasourceOperationName.TEST, DatasourceOperationName.TEST_DRAFT}
)

#: Operacoes sem ID no path: criar e testar rascunho nunca carregam `target_id`.
_NO_TARGET_OPERATIONS: Final = frozenset(
    {DatasourceOperationName.CREATE, DatasourceOperationName.TEST_DRAFT}
)

#: Habilitar o ja habilitado (e o inverso) e sucesso SEM commit: `after == before`.
_IDEMPOTENT_OPERATIONS: Final = frozenset(
    {DatasourceOperationName.ENABLE, DatasourceOperationName.DISABLE}
)

_DATASOURCE_ID_PATTERN: Final = re.compile(r"^dso_[0-9a-f]{32}$")
_REQUEST_ID_PATTERN: Final = re.compile(r"^[0-9a-f]{32}$")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True, slots=True)
class DatasourceAdminAudit:
    """Metadata de uma operacao v2. Estes sao os UNICOS campos.

    `__post_init__` recusa com `TypeError`/`ValueError` qualquer evento
    incoerente antes de chegar ao logger: operacao, alvo, desfecho e categoria
    sao membros dos enums; `target_id` so e um ID `dso_` canonico e so onde ha
    ID no path; o desfecho casa a faixa de status da categoria; e as revisions
    casam a operacao — teste sem revisions, commit com `before + 1`, falha sem
    `after`.
    """

    request_id: str
    operation: DatasourceOperationName
    target_kind: DatasourceTargetKind
    target_id: str | None
    outcome: AdminOutcome
    revision_before: int | None
    revision_after: int | None
    duration_ms: int
    error_category: DatasourceAuditErrorCategory | None

    def __post_init__(self) -> None:
        self._check_types()
        self._check_request_id()
        self._check_target()
        self._check_outcome()
        self._check_revisions()

    def _check_types(self) -> None:
        fields: dict[str, object] = asdict(self)
        required: dict[str, type] = {
            "operation": DatasourceOperationName,
            "target_kind": DatasourceTargetKind,
            "outcome": AdminOutcome,
        }
        for name, expected in required.items():
            if not isinstance(fields[name], expected):
                msg = f"{name} must be a {expected.__name__} member"
                raise TypeError(msg)
        category = fields["error_category"]
        if category is not None and not isinstance(category, DatasourceAuditErrorCategory):
            msg = "error_category must be a DatasourceAuditErrorCategory member or None"
            raise TypeError(msg)
        if not _is_int(fields["duration_ms"]):
            msg = "duration_ms must be a non-boolean int"
            raise TypeError(msg)
        for name in ("revision_before", "revision_after"):
            value = fields[name]
            if value is not None and not _is_int(value):
                msg = f"{name} must be a non-boolean int or None"
                raise TypeError(msg)
        if not isinstance(fields["request_id"], str):
            msg = "request_id must be a str"
            raise TypeError(msg)
        target_id = fields["target_id"]
        if target_id is not None and not isinstance(target_id, str):
            msg = "target_id must be a str or None"
            raise TypeError(msg)
        if self.duration_ms < 0:
            msg = "duration_ms must be >= 0"
            raise ValueError(msg)
        for name in ("revision_before", "revision_after"):
            value = getattr(self, name)
            if value is not None and value < 0:
                msg = f"{name} must be >= 0 or None"
                raise ValueError(msg)

    def _check_request_id(self) -> None:
        if not _REQUEST_ID_PATTERN.fullmatch(self.request_id):
            msg = "request_id must be a 32-char lowercase hex uuid4"
            raise ValueError(msg)
        if uuid.UUID(hex=self.request_id).version != 4:  # noqa: PLR2004 - o servidor gera v4
            msg = "request_id must be a version-4 uuid"
            raise ValueError(msg)

    def _check_target(self) -> None:
        if self.target_id is None:
            return
        if self.operation in _NO_TARGET_OPERATIONS:
            msg = "this operation must not carry a target_id"
            raise ValueError(msg)
        if not _DATASOURCE_ID_PATTERN.fullmatch(self.target_id):
            msg = "target_id must be a canonical datasource id"
            raise ValueError(msg)

    def _check_outcome(self) -> None:
        if self.outcome is AdminOutcome.SUCCESS:
            if self.error_category is not None:
                msg = "success requires error_category=None"
                raise ValueError(msg)
            return
        if self.error_category is None:
            msg = "rejected and error require a closed error_category"
            raise ValueError(msg)
        if self.outcome is not DATASOURCE_CATEGORY_OUTCOME[self.error_category]:
            msg = "outcome does not match the status class of error_category"
            raise ValueError(msg)

    def _check_revisions(self) -> None:
        if self.operation in _TEST_OPERATIONS:
            if self.revision_before is not None or self.revision_after is not None:
                msg = "a candidate test never carries revisions"
                raise ValueError(msg)
            return
        if self.outcome is not AdminOutcome.SUCCESS:
            if self.revision_after is not None:
                msg = "a failure without confirmed publication requires revision_after=None"
                raise ValueError(msg)
            return
        if self.revision_before is None or self.revision_after is None:
            msg = "a successful write requires both revisions"
            raise ValueError(msg)
        allowed = {self.revision_before + 1}
        if self.operation in _IDEMPOTENT_OPERATIONS:
            allowed.add(self.revision_before)
        if self.revision_after not in allowed:
            msg = "revision_after is not coherent with the operation"
            raise ValueError(msg)

    def as_fields(self) -> dict[str, Any]:
        """Campos JSON-compativeis: os enums viram seus valores."""
        fields = asdict(self)
        fields["operation"] = self.operation.value
        fields["target_kind"] = self.target_kind.value
        fields["outcome"] = self.outcome.value
        fields["error_category"] = (
            self.error_category.value if self.error_category is not None else None
        )
        return fields


__all__ = [
    "DATASOURCE_CATEGORY_OUTCOME",
    "DatasourceAdminAudit",
    "DatasourceAuditErrorCategory",
    "DatasourceOperationName",
    "DatasourceTargetKind",
]
