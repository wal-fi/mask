"""Orquestrador. Unica camada que toca o valor original."""

from __future__ import annotations

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
    "ErrorCategory",
    "Gateway",
    "GatewayError",
    "QueryColumn",
    "QueryResult",
    "categorize",
]
