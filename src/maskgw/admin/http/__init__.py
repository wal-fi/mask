"""Fronteira HTTP do plano administrativo (Fase 7, Etapa 7).

Subpacote separado de proposito: importar `maskgw.admin` continua **nao**
carregando FastAPI, uvicorn nem starlette. A secao critica administrativa da
Etapa 6 nao depende de HTTP, e mante-la importavel sozinha e o que permite
testa-la, e usa-la, sem servidor. Um teste afirma essa separacao.

Este subpacote tampouco importa `maskgw.mcp` ou `maskgw.gateway`: os planos sao
separados, e so o composition root em `bootstrap/` conhece os dois (secao 9).
Ele tambem nao importa `logging` — `audit/` continua sendo o unico modulo
autorizado, e `AdminAudit` e a Etapa 10.

Somente leitura nesta etapa. `config:validate` e a Etapa 8; escrita e adocao,
a Etapa 9.
"""

from __future__ import annotations

from maskgw.admin.http.app import (
    API_PREFIX,
    READ_METHODS,
    READ_PATHS,
    build_admin_app,
    build_router,
    install_error_handlers,
    wrap_boundary,
)
from maskgw.admin.http.middleware import (
    MAX_BODY_BYTES,
    AuthenticationMiddleware,
    BodyLimitMiddleware,
    BoundaryMiddleware,
    BrowserOriginMiddleware,
    ContentTypeMiddleware,
    HostAllowlistMiddleware,
    allowed_hosts,
)
from maskgw.admin.http.responses import STATUS_BY_CATEGORY, error_payload, error_response
from maskgw.admin.http.server import (
    AdminHttpServer,
    AdminHttpUnavailableError,
)
from maskgw.admin.http.settings import (
    ADMIN_BIND_ENV,
    ADMIN_ENABLED_ENV,
    ADMIN_ENABLED_VALUE,
    ADMIN_PORT_ENV,
    ADMIN_TOKEN_ENV,
    ADMIN_TOKEN_MIN_LENGTH,
    DEFAULT_ADMIN_BIND,
    DEFAULT_ADMIN_PORT,
    LOOPBACK_BINDS,
    AdminHttpSettings,
    is_enabled,
    resolve,
)
from maskgw.admin.http.settings import (
    build as build_settings,
)

__all__ = [
    "ADMIN_BIND_ENV",
    "ADMIN_ENABLED_ENV",
    "ADMIN_ENABLED_VALUE",
    "ADMIN_PORT_ENV",
    "ADMIN_TOKEN_ENV",
    "ADMIN_TOKEN_MIN_LENGTH",
    "API_PREFIX",
    "DEFAULT_ADMIN_BIND",
    "DEFAULT_ADMIN_PORT",
    "LOOPBACK_BINDS",
    "MAX_BODY_BYTES",
    "READ_METHODS",
    "READ_PATHS",
    "STATUS_BY_CATEGORY",
    "AdminHttpServer",
    "AdminHttpSettings",
    "AdminHttpUnavailableError",
    "AuthenticationMiddleware",
    "BodyLimitMiddleware",
    "BoundaryMiddleware",
    "BrowserOriginMiddleware",
    "ContentTypeMiddleware",
    "HostAllowlistMiddleware",
    "allowed_hosts",
    "build_admin_app",
    "build_router",
    "build_settings",
    "error_payload",
    "error_response",
    "install_error_handlers",
    "is_enabled",
    "resolve",
    "wrap_boundary",
]
