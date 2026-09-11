"""Quatro recursos fixos; nenhuma dependencia de servico, estado ou filesystem."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from fastapi import FastAPI, Request, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from maskgw.admin.errors import AdminErrorCategory
from maskgw.admin.http.middleware import AuthenticationMiddleware
from maskgw.admin.http.responses import error_response

UI_ROUTES: Final = MappingProxyType(
    {
        "/admin/ui": ("index.html", "text/html; charset=utf-8"),
        "/admin/ui/assets/ui.js": ("ui.js", "text/javascript; charset=utf-8"),
        "/admin/ui/assets/ui.css": ("ui.css", "text/css; charset=utf-8"),
        "/admin/ui/presentation.json": ("presentation.json", "application/json"),
    }
)
PUBLIC_PATHS: Final = frozenset(path.encode("ascii") for path in list(UI_ROUTES)[:3])
RAW_PATHS: Final = frozenset(path.encode("ascii") for path in UI_ROUTES)


def public_request(scope: Scope) -> bool:
    """Query nao concede bytes: o roteamento devolve 404 conforme a matriz."""
    return scope.get("method") in {"GET", "HEAD"} and scope.get("raw_path") in PUBLIC_PATHS


def register_ui(app: FastAPI, resources: Mapping[str, bytes]) -> None:
    owned = MappingProxyType(dict(resources))

    async def resource(request: Request) -> Response:
        name, mime = UI_ROUTES[request.scope["raw_path"].decode("ascii")]
        return Response(owned[name], headers={"content-type": mime})

    for path in UI_ROUTES:
        app.add_api_route(path, resource, methods=["GET", "HEAD"], response_class=Response)


class UiAuthentication:
    def __init__(self, app: ASGIApp, *, token: str) -> None:
        self._app = app
        self._authenticated = AuthenticationMiddleware(app, token=token)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        target = (
            self._app if scope["type"] == "http" and public_request(scope) else self._authenticated
        )
        await target(scope, receive, send)


class UiRouting:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            raw = scope.get("raw_path", b"")
            path = scope.get("path", "")
            candidate = path.startswith("/admin/ui") or raw.startswith(b"/admin/ui")
            if candidate and (
                raw not in RAW_PATHS or raw.decode("ascii") != path or scope.get("query_string")
            ):
                await error_response(AdminErrorCategory.NOT_FOUND)(scope, receive, send)
                return
        await self._app(scope, receive, send)
