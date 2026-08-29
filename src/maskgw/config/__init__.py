"""Carregamento e validacao da configuracao externa."""

from __future__ import annotations

from maskgw.config.loader import load_config, load_config_text, parse_config
from maskgw.config.models import (
    ExceptionConfig,
    MaskingFileConfig,
    MatchConfig,
    RuleConfig,
)

__all__ = [
    "ExceptionConfig",
    "MaskingFileConfig",
    "MatchConfig",
    "RuleConfig",
    "load_config",
    "load_config_text",
    "parse_config",
]
