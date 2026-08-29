"""Parsing e validacao de SQL.

Independente de MCP, de banco e do Masking Engine: recebe texto, devolve uma
arvore validada ou levanta. Ver docs/ARCHITECTURE.md.
"""

from __future__ import annotations

from maskgw.sql.parser import parse_single_statement, parse_statements
from maskgw.sql.policy import DEFAULT_SQL_POLICY, SqlPolicy
from maskgw.sql.validator import validate_select

__all__ = [
    "DEFAULT_SQL_POLICY",
    "SqlPolicy",
    "parse_single_statement",
    "parse_statements",
    "validate_select",
]
