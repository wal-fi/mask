"""Politica de navegador estrita, instalada somente com UI habilitada."""

import re
from http import HTTPStatus
from typing import Final

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from maskgw.admin.errors import AdminErrorCategory
from maskgw.admin.http.responses import error_payload, error_response
from maskgw.admin.http.ui import RAW_PATHS

UI_CSP: Final = (
    "default-src 'none'; script-src 'self'; script-src-attr 'none'; style-src 'self'; "
    "style-src-attr 'none'; connect-src 'self'; img-src 'none'; font-src 'none'; "
    "object-src 'none'; base-uri 'none'; form-action 'none'; frame-src 'none'; "
    "frame-ancestors 'none'; worker-src 'none'; manifest-src 'none'; media-src 'none'"
)
DATA_CSP: Final = "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
BROWSER_HEADERS: Final = {
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "cross-origin-resource-policy": "same-origin",
    "cross-origin-opener-policy": "same-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), fullscreen=()",
}
_AUTHORITY: Final = re.compile(r"(127\.0\.0\.1|localhost|\[::1\])(?::([1-9][0-9]{0,4}))?", re.I)


def authority(value: str, port: int) -> str | None:
    parsed = _AUTHORITY.fullmatch(value)
    if parsed is None or int(parsed[2] or "80") != port:
        return None
    return parsed[1].lower()


def same_origin(value: str, host: str, port: int, *, referer: bool) -> bool:
    if (
        not value.startswith("http://")
        or not value.isascii()
        or any(c.isspace() or not c.isprintable() for c in value)
    ):
        return False
    if "\\" in value or "#" in value:
        return False
    rest = value[7:]
    if referer:
        rest = re.split(r"[/?]", rest, maxsplit=1)[0]
    return authority(rest, port) == host


def values(scope: Scope, name: bytes) -> list[str]:
    return [v.decode("latin-1") for k, v in scope.get("headers", []) if k.lower() == name]


class BrowserAdmission:
    def __init__(self, app: ASGIApp, *, port: int) -> None:
        self._app = app
        self._port = port

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        hosts = values(scope, b"host")
        host = authority(hosts[0], self._port) if len(hosts) == 1 else None
        if host is None or scope.get("scheme") != "http":
            await error_response(AdminErrorCategory.HOST_NOT_ALLOWED)(scope, receive, send)
            return
        accepted = True
        for name in (b"origin", b"referer"):
            items = values(scope, name)
            if items and (
                len(items) != 1
                or not same_origin(items[0], host, self._port, referer=name == b"referer")
            ):
                accepted = False
        sites = values(scope, b"sec-fetch-site")
        if sites and (len(sites) != 1 or sites[0] not in {"same-origin", "none"}):
            accepted = False
        if not accepted:
            payload = error_payload(AdminErrorCategory.CROSS_ORIGIN_REJECTED)
            payload["detail"] = "The request origin is not accepted."
            await JSONResponse(payload, status_code=403)(scope, receive, send)
            return
        await self._app(scope, receive, send)


class BrowserHeaders:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        async def decorated(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name in list(headers.keys()):
                    if name.lower().startswith("access-control-") or name.lower() in {
                        "set-cookie",
                        "server",
                        "etag",
                        "last-modified",
                        "allow",
                    }:
                        del headers[name]
                for name, value in BROWSER_HEADERS.items():
                    headers[name] = value
                success = (
                    message["status"] == HTTPStatus.OK
                    and scope.get("raw_path") in RAW_PATHS
                    and scope.get("method") in {"GET", "HEAD"}
                    and not scope.get("query_string")
                )
                headers["content-security-policy"] = UI_CSP if success else DATA_CSP
            elif message["type"] == "http.response.body" and scope.get("method") == "HEAD":
                message = {**message, "body": b""}
            await send(message)

        await self._app(scope, receive, decorated)
