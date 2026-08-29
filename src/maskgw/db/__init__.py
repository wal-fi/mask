"""Adapter de banco de dados.

Superficie publica deliberadamente estreita: nada aqui devolve cursor, linha
crua ou iterador de valores originais. O unico resultado que sai e
`MaskedResult`, ja processado pelo Masking Engine.
"""

from __future__ import annotations

from maskgw.db.capabilities import check_provenance_capability
from maskgw.db.columns import ColumnOrigin, describe_columns
from maskgw.db.postgres import DEFAULT_BATCH_SIZE, DEFAULT_SETTINGS, PostgresAdapter
from maskgw.db.provenance import ProvenanceResolver, provenance_keys
from maskgw.db.result import MaskedResult
from maskgw.db.sanitize import sanitize_error

__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_SETTINGS",
    "ColumnOrigin",
    "MaskedResult",
    "PostgresAdapter",
    "ProvenanceResolver",
    "check_provenance_capability",
    "describe_columns",
    "provenance_keys",
    "sanitize_error",
]
