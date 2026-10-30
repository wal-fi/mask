"""Private typed execution intent, not connection health or a worker.

No original SQLSTATE, message, diagnostic or exception is retained. TIMEOUT
keeps the historical QueryTimeout type for any server query cancellation;
it does not establish that statement_timeout caused that cancellation.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

import psycopg

from maskgw.db.sanitize import TIMEOUT_MESSAGE
from maskgw.errors import DatabaseError, QueryTimeout


class ExecutionFailure(StrEnum):
    """Intent only: CONNECTION also includes unclassified local/driver failure."""

    QUERY = "QUERY"
    TIMEOUT = "TIMEOUT"
    RESOURCE = "RESOURCE"
    CONNECTION = "CONNECTION"
    INTERNAL = "INTERNAL"


_MESSAGES: Final = {
    ExecutionFailure.QUERY: "consulta recusada pelo banco de dados",
    ExecutionFailure.RESOURCE: "recursos insuficientes na execucao",
    ExecutionFailure.CONNECTION: "conexao indisponivel na execucao",
    ExecutionFailure.INTERNAL: "falha interna na execucao",
}
_QUERY_CLASSES: Final = frozenset({"0A", "21", "22", "23", "40", "42", "54"})
_STATE_CHARS: Final = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
_STATE_LENGTH: Final = 5


class TypedExecutionError(DatabaseError):
    """Closed intent only; continuation still needs a post-settle health check."""

    def __init__(self, category: ExecutionFailure) -> None:
        if type(category) is not ExecutionFailure or category is ExecutionFailure.TIMEOUT:
            category = ExecutionFailure.INTERNAL
        self.category = category
        super().__init__(_MESSAGES[category])

    @property
    def continuation_candidate(self) -> bool:
        return self.category is ExecutionFailure.QUERY


class TypedExecutionTimeout(QueryTimeout):
    """Server query cancellation; cause is not inferred from 57014."""

    def __init__(self) -> None:
        self.category = ExecutionFailure.TIMEOUT
        super().__init__(TIMEOUT_MESSAGE)

    @property
    def continuation_candidate(self) -> bool:
        return True


def classify_typed_error(error: psycopg.Error) -> TypedExecutionError | TypedExecutionTimeout:
    """Read only canonical SQLSTATE; never raise or retain the driver error.

    Missing state is an unclassified local/connection failure, including
    possible native allocation failures. It is fatal, without claiming OOM.
    Class53 is a server resource category, not evidence of local memory use.
    """
    state: object = None
    read = False
    if isinstance(error, psycopg.Error):
        try:
            state = error.sqlstate
            read = True
        except Exception:
            read = False
    if not read:
        return TypedExecutionError(ExecutionFailure.INTERNAL)
    if state is None:
        return TypedExecutionError(ExecutionFailure.CONNECTION)
    if (
        type(state) is not str
        or len(state) != _STATE_LENGTH
        or any(c not in _STATE_CHARS for c in state)
    ):
        return TypedExecutionError(ExecutionFailure.INTERNAL)
    if state == "57014":
        return TypedExecutionTimeout()
    category = ExecutionFailure.INTERNAL
    prefix = state[:2]
    if state == "25006" or prefix in _QUERY_CLASSES:
        category = ExecutionFailure.QUERY
    elif prefix == "53":
        category = ExecutionFailure.RESOURCE
    elif prefix == "08":
        category = ExecutionFailure.CONNECTION
    return TypedExecutionError(category)
