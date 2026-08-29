"""Modelos de configuracao (Pydantic).

`extra="forbid"` em todos os modelos: uma chave desconhecida — inclusive um
erro de digitacao como `transfomer:` — impede a inicializacao. Fail-closed.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from maskgw.masking.rules import MatchMode

_STRICT = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)


class MatchConfig(BaseModel):
    """Campos comuns a regras e exceptions."""

    model_config = _STRICT

    match: str = Field(min_length=1, description="Padrao comparado ao nome da coluna")
    mode: MatchMode = MatchMode.CONTAINS
    case_sensitive: bool = False


class ExceptionConfig(MatchConfig):
    """Exception: tem prioridade absoluta e nao possui transformer."""


class RuleConfig(MatchConfig):
    """Regra de masking."""

    transformer: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class MaskingFileConfig(BaseModel):
    """Conteudo completo do `masking.yaml`."""

    model_config = _STRICT

    masking: list[RuleConfig] = Field(default_factory=list)
    exceptions: list[ExceptionConfig] = Field(default_factory=list)
