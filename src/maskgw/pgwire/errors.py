"""Erros fechados da fronteira PostgreSQL (D-109).

Toda falha externa e uma categoria com SQLSTATE e texto FIXOS. Nenhuma mensagem
cita usuario, alias, mecanismo recebido, causa interna ou excecao original — o
`scramp` ecoa entrada do cliente nas mensagens dele (medido), e nada dela sai.
Usuario, senha e alias errados sao a MESMA categoria.
"""

from __future__ import annotations

import struct
from enum import StrEnum
from typing import Final


class PgwireErrorCategory(StrEnum):
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    PROTOCOL_VIOLATION = "PROTOCOL_VIOLATION"
    FEATURE_NOT_SUPPORTED = "FEATURE_NOT_SUPPORTED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    #: D-110: reserva de sessao recusada (capacidade). Sem consulta ao banco.
    TOO_MANY_CONNECTIONS = "TOO_MANY_CONNECTIONS"


#: Categoria -> (SQLSTATE, mensagem fixa).
PGWIRE_ERRORS: Final[dict[PgwireErrorCategory, tuple[str, str]]] = {
    PgwireErrorCategory.AUTHENTICATION_FAILED: ("28P01", "authentication failed"),
    PgwireErrorCategory.PROTOCOL_VIOLATION: ("08P01", "protocol violation"),
    PgwireErrorCategory.FEATURE_NOT_SUPPORTED: ("0A000", "feature not supported"),
    PgwireErrorCategory.INTERNAL_ERROR: ("XX000", "internal error"),
    PgwireErrorCategory.TOO_MANY_CONNECTIONS: ("53300", "too many connections"),
}


class PgwireStartupError(Exception):
    """Falha do startup: so a categoria. Levantada fora de `except` (D-017)."""

    def __init__(self, category: PgwireErrorCategory) -> None:
        super().__init__(category.value)
        self.category = category


def error_response(category: PgwireErrorCategory) -> bytes:
    """`ErrorResponse` FATAL com SQLSTATE e mensagem fixos."""
    code, message = PGWIRE_ERRORS[category]
    fields = b"".join(
        (
            b"SFATAL\x00",
            b"VFATAL\x00",
            b"C" + code.encode("ascii") + b"\x00",
            b"M" + message.encode("ascii") + b"\x00",
            b"\x00",
        )
    )
    return b"E" + struct.pack("!I", len(fields) + 4) + fields


__all__ = [
    "PGWIRE_ERRORS",
    "PgwireErrorCategory",
    "PgwireStartupError",
    "error_response",
]
