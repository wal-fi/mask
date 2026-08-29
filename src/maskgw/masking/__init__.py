"""Masking Engine — nucleo puro.

Este pacote NAO pode importar banco de dados, MCP, rede ou psycopg.
A regra e verificada por teste automatizado (`tests/test_purity.py`).
"""

from __future__ import annotations

from maskgw.masking.descriptor import ColumnDescriptor, ProvenanceKind
from maskgw.masking.engine import Action, Decision, MaskingEngine
from maskgw.masking.matcher import ExceptionMatcher, RuleMatcher
from maskgw.masking.rules import (
    MaskingException,
    MaskingPolicy,
    MaskingRule,
    MatchMode,
    MatchSpec,
)

__all__ = [
    "Action",
    "ColumnDescriptor",
    "Decision",
    "ExceptionMatcher",
    "MaskingEngine",
    "MaskingException",
    "MaskingPolicy",
    "MaskingRule",
    "MatchMode",
    "MatchSpec",
    "ProvenanceKind",
    "RuleMatcher",
]
