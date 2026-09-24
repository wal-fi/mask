"""Vocabulario fechado de erro da Admin API v2 (Fase 9, Etapa 4, D-095).

A v2 tem categorias proprias, num enum SEPARADO de `AdminErrorCategory`: aquele
enum e o contrato da v1 e alimenta o gerador da UI v1, e estende-lo mudaria os
artefatos da v1. As recusas de fronteira (host, origem, token, corpo, media
type, schema, 404/405) continuam saindo pelos handlers da v1, com as categorias
da v1 — sao as mesmas camadas. Os handlers v2 produzem somente
`V2_SHARED_CATEGORIES` (valores e status identicos aos da v1) e
`DatasourceErrorCategory`.

A forma da resposta e a mesma da v1: `error` de conjunto fechado, `detail` de
texto FIXO por categoria, `current_revision` quando a categoria a carrega. Nunca
`str(exc)`, alias, host, porta, database, usuario, senha, endereco resolvido,
mensagem do PostgreSQL, traceback ou cadeia de excecao.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Final, NoReturn

from fastapi.responses import JSONResponse

from maskgw.admin.errors import CATEGORY_DETAILS, AdminErrorCategory
from maskgw.admin.http.responses import STATUS_BY_CATEGORY
from maskgw.errors import MaskGatewayError


class DatasourceErrorCategory(StrEnum):
    """Categorias que so existem na v2."""

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


#: Categorias da v1 que um handler v2 tambem produz, com o mesmo significado.
V2_SHARED_CATEGORIES: Final = frozenset(
    {
        AdminErrorCategory.REVISION_CONFLICT,
        AdminErrorCategory.NOT_FOUND,
        AdminErrorCategory.IMMUTABLE_FIELD,
        AdminErrorCategory.SCHEMA_INVALID,
        AdminErrorCategory.INTERNAL_ERROR,
    }
)

V2Category = AdminErrorCategory | DatasourceErrorCategory

#: Texto fixo por categoria propria. Nenhum cita alias, destino ou causa.
V2_DETAILS: Final[dict[DatasourceErrorCategory, str]] = {
    DatasourceErrorCategory.ALIAS_CONFLICT: "A datasource with this alias already exists.",
    DatasourceErrorCategory.CONFIRMATION_MISMATCH: (
        "The confirmation does not match the datasource."
    ),
    DatasourceErrorCategory.DATASOURCE_BUSY: (
        "The datasource capacity for candidates or draining generations is exhausted; retry later."
    ),
    DatasourceErrorCategory.DATASOURCE_DISABLED: "The datasource is disabled.",
    DatasourceErrorCategory.DATASOURCE_DESTINATION_REJECTED: (
        "The datasource destination was rejected or could not be resolved in time."
    ),
    DatasourceErrorCategory.DATASOURCE_POLICY_INVALID: "The datasource policy is not valid.",
    DatasourceErrorCategory.DATASOURCE_CONNECTION_FAILED: (
        "The connection to the datasource failed."
    ),
    DatasourceErrorCategory.DATASOURCE_CAPABILITY_MISSING: (
        "The datasource does not provide the required guarantees."
    ),
    DatasourceErrorCategory.CATALOG_WRITE_ERROR: (
        "The datasource catalog could not be persisted; the previous state is unchanged."
    ),
    DatasourceErrorCategory.CATALOG_OUTCOME_UNCERTAIN: (
        "The outcome of the catalog change is unknown; restart before further changes."
    ),
    DatasourceErrorCategory.CATALOG_BLOCKED: (
        "Datasource changes are unavailable until the Gateway restarts."
    ),
    DatasourceErrorCategory.DATASOURCE_SERVICE_UNAVAILABLE: (
        "Datasource operations are unavailable."
    ),
}

#: Status por categoria propria.
V2_STATUS: Final[dict[DatasourceErrorCategory, int]] = {
    DatasourceErrorCategory.ALIAS_CONFLICT: 409,
    DatasourceErrorCategory.CONFIRMATION_MISMATCH: 422,
    DatasourceErrorCategory.DATASOURCE_BUSY: 409,
    DatasourceErrorCategory.DATASOURCE_DISABLED: 409,
    DatasourceErrorCategory.DATASOURCE_DESTINATION_REJECTED: 422,
    DatasourceErrorCategory.DATASOURCE_POLICY_INVALID: 422,
    DatasourceErrorCategory.DATASOURCE_CONNECTION_FAILED: 422,
    DatasourceErrorCategory.DATASOURCE_CAPABILITY_MISSING: 422,
    DatasourceErrorCategory.CATALOG_WRITE_ERROR: 500,
    DatasourceErrorCategory.CATALOG_OUTCOME_UNCERTAIN: 500,
    DatasourceErrorCategory.CATALOG_BLOCKED: 503,
    DatasourceErrorCategory.DATASOURCE_SERVICE_UNAVAILABLE: 503,
}


def status_for(category: V2Category) -> int:
    if isinstance(category, DatasourceErrorCategory):
        return V2_STATUS[category]
    return STATUS_BY_CATEGORY[category]


def detail_for(category: V2Category) -> str:
    if isinstance(category, DatasourceErrorCategory):
        return V2_DETAILS[category]
    return CATEGORY_DETAILS[category]


class DatasourceAdminError(MaskGatewayError):
    """Unico erro que sai de uma operacao v2: categoria e, opcional, revision."""

    __slots__ = ("category", "current_revision")

    def __init__(self, category: V2Category, *, current_revision: int | None = None) -> None:
        if isinstance(category, AdminErrorCategory) and category not in V2_SHARED_CATEGORIES:
            msg = "categoria da v1 fora do conjunto compartilhado"
            raise ValueError(msg)
        super().__init__(detail_for(category))
        self.category = category
        self.current_revision = current_revision

    def __repr__(self) -> str:
        return (
            f"DatasourceAdminError(category={self.category.value!r}, "
            f"current_revision={self.current_revision!r})"
        )


def raise_v2_error(error: DatasourceAdminError) -> NoReturn:
    """Levanta FORA do handler de origem: `__cause__` e `__context__` nulos (D-017)."""
    raise error from None


def v2_error_payload(
    category: V2Category, *, current_revision: int | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {"error": category.value, "detail": detail_for(category)}
    if current_revision is not None:
        payload["current_revision"] = current_revision
    return payload


def v2_error_response(category: V2Category, *, current_revision: int | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_for(category),
        content=v2_error_payload(category, current_revision=current_revision),
    )


__all__ = [
    "V2_DETAILS",
    "V2_SHARED_CATEGORIES",
    "V2_STATUS",
    "DatasourceAdminError",
    "DatasourceErrorCategory",
    "V2Category",
    "detail_for",
    "raise_v2_error",
    "status_for",
    "v2_error_payload",
    "v2_error_response",
]
