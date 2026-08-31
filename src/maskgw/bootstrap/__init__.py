"""Composition root e lifecycle do processo MaskGW.

Somente este pacote monta os planos da aplicacao. O data plane MCP continua
fino e nao conhece o futuro plano administrativo; quando `admin/` existir,
tambem sera composto aqui, sem criar dependencia entre os dois.
"""

from __future__ import annotations

from maskgw.bootstrap.application import (
    CONFIG_PATH_ENV,
    DEFAULT_CONFIG_PATH,
    DSN_ENV,
    Application,
    build_application,
    resolve_dsn,
)

__all__ = [
    "CONFIG_PATH_ENV",
    "DEFAULT_CONFIG_PATH",
    "DSN_ENV",
    "Application",
    "build_application",
    "resolve_dsn",
]
