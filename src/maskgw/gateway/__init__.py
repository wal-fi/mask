"""Orquestrador. Unica camada que toca o valor original."""

from __future__ import annotations

from maskgw.gateway.factory import (
    DEFAULT_CONFIG_PATH,
    DSN_ENV,
    Application,
    build_application,
    resolve_dsn,
)
from maskgw.gateway.models import (
    CATEGORY_MESSAGES,
    ErrorCategory,
    GatewayError,
    QueryColumn,
    QueryResult,
    categorize,
)
from maskgw.gateway.service import Gateway

__all__ = [
    "CATEGORY_MESSAGES",
    "DEFAULT_CONFIG_PATH",
    "DSN_ENV",
    "Application",
    "ErrorCategory",
    "Gateway",
    "GatewayError",
    "QueryColumn",
    "QueryResult",
    "build_application",
    "categorize",
    "resolve_dsn",
]
