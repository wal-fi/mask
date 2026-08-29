"""Carregamento e validacao da configuracao externa."""

from __future__ import annotations

from maskgw.config.gateway import (
    DatabaseSettings,
    GatewayConfig,
    load_gateway_config,
    load_gateway_config_text,
    parse_gateway_config,
)
from maskgw.config.loader import load_config, load_config_text, parse_config
from maskgw.config.models import (
    DatabaseConfig,
    ExceptionConfig,
    MaskingFileConfig,
    MatchConfig,
    RuleConfig,
    SqlConfig,
)

__all__ = [
    "DatabaseConfig",
    "DatabaseSettings",
    "ExceptionConfig",
    "GatewayConfig",
    "MaskingFileConfig",
    "MatchConfig",
    "RuleConfig",
    "SqlConfig",
    "load_config",
    "load_config_text",
    "load_gateway_config",
    "load_gateway_config_text",
    "parse_config",
    "parse_gateway_config",
]
