"""Adapter de banco de dados.

Superficie publica deliberadamente estreita: nada aqui devolve cursor, linha
crua ou iterador de valores originais. O unico resultado que sai e
`MaskedResult`, ja processado pelo Masking Engine.
"""

from __future__ import annotations

from maskgw.db.columns import describe_columns
from maskgw.db.postgres import DEFAULT_BATCH_SIZE, PostgresAdapter
from maskgw.db.result import MaskedResult
from maskgw.db.sanitize import sanitize_error

__all__ = [
    "DEFAULT_BATCH_SIZE",
    "MaskedResult",
    "PostgresAdapter",
    "describe_columns",
    "sanitize_error",
]
