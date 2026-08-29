"""Regras compiladas e politica de masking.

Estas sao as estruturas que o Masking Engine consome. Sao construidas pelo
config loader e sao imutaveis em runtime: o cliente MCP nao tem como altera-las.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from maskgw.masking.transformers.base import Transformer


class MatchMode(StrEnum):
    """Modo de comparacao de um nome de coluna contra o padrao da regra."""

    CONTAINS = "contains"
    EXACT = "exact"


@dataclass(frozen=True, slots=True)
class MatchSpec:
    """Criterio de correspondencia de um nome de coluna.

    Default do projeto: case-insensitive + contains.
    """

    pattern: str
    mode: MatchMode = MatchMode.CONTAINS
    case_sensitive: bool = False

    def matches(self, name: str | None) -> bool:
        """Avalia um unico nome. `None` nunca casa."""
        if name is None:
            return False

        needle = self.pattern
        haystack = name
        if not self.case_sensitive:
            needle = needle.casefold()
            haystack = haystack.casefold()

        if self.mode is MatchMode.EXACT:
            return haystack == needle
        return needle in haystack


@dataclass(frozen=True, slots=True)
class MaskingRule:
    """Regra de masking compilada, ja ligada ao seu transformer."""

    spec: MatchSpec
    transformer: Transformer
    transformer_name: str
    index: int


@dataclass(frozen=True, slots=True)
class MaskingException:
    """Exception compilada. Tem prioridade absoluta sobre qualquer regra."""

    spec: MatchSpec
    index: int


@dataclass(frozen=True, slots=True)
class MaskingPolicy:
    """Conjunto imutavel de exceptions e regras, na ordem do arquivo."""

    exceptions: tuple[MaskingException, ...] = ()
    rules: tuple[MaskingRule, ...] = ()
