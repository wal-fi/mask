"""Composition root e lifecycle do processo MaskGW.

Somente este pacote monta os planos da aplicacao. O data plane MCP continua
fino e nao conhece o plano administrativo, e o admin plane nao conhece o MCP:
o unico modulo autorizado a importar os dois e este, e isso e teste de AST.
"""

from __future__ import annotations

from maskgw.bootstrap.application import (
    CONFIG_PATH_ENV,
    DEFAULT_CONFIG_PATH,
    DSN_ENV,
    Application,
    build_application,
    make_adapter_factory,
    resolve_dsn,
)

__all__ = [
    "CONFIG_PATH_ENV",
    "DEFAULT_CONFIG_PATH",
    "DSN_ENV",
    "Application",
    "build_application",
    "make_adapter_factory",
    "resolve_dsn",
]
