"""Etapa 4: inventario fechado, produto HTTP e recusas antes de efeitos."""

import asyncio
import json
import socket
from collections.abc import Sequence
from typing import NoReturn, cast
from urllib.parse import unquote

import pytest
from fastapi.routing import APIRoute
from starlette.types import ASGIApp, Message, Scope

from maskgw.admin.errors import AdminErrorCategory
from maskgw.admin.http import AdminHttpServer, build_admin_app, build_router, wrap_boundary
from maskgw.admin.http.browser import BROWSER_HEADERS, DATA_CSP, UI_CSP, authority, same_origin
from maskgw.admin.http.responses import error_payload
from maskgw.admin.http.ui import UI_ROUTES
from maskgw.admin.service import AdminConfigService
from maskgw.admin.ui.resources import load_resources
from maskgw.audit import AuditLog
from maskgw.secretsource import MappingSecretProvider
from tests.admin_http_support import TOKEN, Reply, build_service, request
from tests.test_admin_http_surface import TestRouteSet as RouteReference
from tests.test_admin_http_surface import _service_stub

PATHS = list(UI_ROUTES)
METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"]
VARIANTS = [
    "/admin/ui/",
    "/admin/ui-other",
    "/admin/ui/assets/missing.js",
    "/%61dmin/ui",
    "/admin/%75i",
    "/admin/ui%2f",
    "/admin/ui/assets/../ui.js",
    "/admin/ui\\assets\\ui.js",
    "/admin/ui/assets/%75i.js",
    "/admin/ui/presentation%2ejson",
    "/admin/ui/assets/ui.js.map",
    "/admin/ui/../v1/status",
    "/admin/ui/assets/%2e%2e/presentation.json",
]


def drive(  # noqa: PLR0913 - dimensoes independentes da matriz
    app: ASGIApp,
    path: str = "/admin/ui",
    method: str = "GET",
    token: str | None = TOKEN,
    query: bytes = b"",
    *,
    headers: Sequence[tuple[bytes, bytes]] = (),
    json_type: bool = True,
) -> Reply:
    async def run() -> Reply:
        sent: list[Message] = []
        fields = [(b"host", b"127.0.0.1:8765")]
        if token is not None:
            fields.append((b"authorization", ("Bearer " + token).encode()))
        if json_type:
            fields.append((b"content-type", b"application/json"))
        fields.extend(headers)
        scope: Scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "scheme": "http",
            "method": method,
            "path": unquote(path),
            "raw_path": path.encode(),
            "query_string": query,
            "root_path": "",
            "headers": fields,
            "server": ("127.0.0.1", 8765),
            "client": ("127.0.0.1", 9999),
        }

        async def receive() -> Message:
            return {"type": "http.request", "body": b"{}", "more_body": False}

        async def send(message: Message) -> None:
            sent.append(message)

        await app(scope, receive, send)
        start = next(m for m in sent if m["type"] == "http.response.start")
        return Reply(
            start["status"],
            {k.decode(): v.decode() for k, v in start["headers"]},
            b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body"),
        )

    return asyncio.run(run())


class Untouchable:
    """Acesso a servico/audit falha mesmo se uma fronteira contiver a excecao."""

    def __init__(self) -> None:
        self.touches: list[str] = []

    def __getattr__(self, name: str) -> NoReturn:
        self.touches.append(name)
        raise AssertionError("UI accessed state")


@pytest.fixture(scope="module")
def assets():
    return load_resources()


@pytest.fixture
def app(assets):
    state = Untouchable()
    result = build_admin_app(
        cast(AdminConfigService, state),
        token=TOKEN,
        port=8765,
        database_dsn_env="unused",
        secrets=MappingSecretProvider({}),
        audit=cast(AuditLog, state),
        ui_resources=assets,
    )
    yield result
    assert state.touches == []


@pytest.mark.parametrize("enabled", [False, True])
def test_inventory_exact_twenty_or_twenty_four(enabled, assets):
    router = build_router(
        _service_stub(),
        secrets=MappingSecretProvider({}),
        database_dsn_env="unused",
        audit=AuditLog(),
        ui_resources=assets if enabled else None,
    )
    expected = RouteReference()._expected()
    if enabled:
        expected |= {(p, frozenset({"GET", "HEAD"})) for p in PATHS}
    actual = {
        (r.path, frozenset(r.methods or set())) for r in router.routes if isinstance(r, APIRoute)
    }
    assert actual == expected
    assert len(router.routes) == (24 if enabled else 20)
    assert sum(len(m) for _, m in actual) == (36 if enabled else 28)


@pytest.mark.parametrize("path", PATHS + VARIANTS)
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("token", [None, "wrong", TOKEN], ids=["absent", "wrong", "right"])
@pytest.mark.parametrize("query", [b"", b"x=1", b"token=ignored"])
def test_http_product(*, app, assets, path, method, token, query):  # noqa: PLR0913 - produto completo
    canonical = path in PATHS
    public = canonical and path != PATHS[-1] and method in {"GET", "HEAD"}
    expected = 401
    if public or token == TOKEN:
        expected = 404 if query or not canonical else (200 if method in {"GET", "HEAD"} else 405)
    reply = drive(app, path, method, token, query)
    assert reply.status == expected
    assert {k: reply.headers[k] for k in BROWSER_HEADERS} == BROWSER_HEADERS
    assert reply.headers["content-security-policy"] == (UI_CSP if expected == 200 else DATA_CSP)
    assert not any(
        k.startswith("access-control-")
        or k
        in {
            "set-cookie",
            "server",
            "etag",
            "last-modified",
            "allow",
            "content-encoding",
            "location",
        }
        for k in reply.headers
    )
    if expected == 200:
        name, mime = UI_ROUTES[path]
        body = assets[name]
        assert reply.headers["content-type"] == mime
    else:
        category = {
            401: AdminErrorCategory.UNAUTHORIZED,
            404: AdminErrorCategory.NOT_FOUND,
            405: AdminErrorCategory.METHOD_NOT_ALLOWED,
        }[expected]
        body = json.dumps(error_payload(category), separators=(",", ":")).encode()
        assert reply.headers["content-type"] == "application/json"
    assert reply.body == (b"" if method == "HEAD" else body)
    assert int(reply.headers["content-length"]) == len(body)


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("token", [None, "wrong", TOKEN])
def test_media_type_before_routing(app, method, token):
    reply = drive(app, method=method, token=token, json_type=False)
    assert reply.status == (415 if token == TOKEN else 401)


@pytest.mark.parametrize(
    "headers,status",
    [
        (
            [
                (b"host", b"evil.example:8765"),
                (b"origin", b"null"),
                (b"content-length", b"1048577"),
            ],
            400,
        ),
        ([(b"origin", b"null"), (b"content-length", b"1048577")], 403),
        ([(b"content-length", b"1048577")], 413),
        ([], 401),
    ],
)
def test_precedence(app, headers, status):
    reply = drive(app, method="POST", token=None, json_type=False, headers=headers)
    assert reply.status == status


@pytest.mark.parametrize(
    "host",
    [
        "evil.example:8765",
        "127.1:8765",
        "2130706433:8765",
        "[::ffff:127.0.0.1]:8765",
        "127.0.0.1:8766",
        "localhost.",
        "localhost:08765",
        "user@localhost:8765",
        "localhost:8765,localhost:8765",
        " localhost:8765",
        "localhost:8765 ",
        "[::1%25lo]:8765",
        "localhost",
        "",
        "localhost:65536",
    ],
)
def test_host_parser_refuses_ambiguity(host):
    assert authority(host, 8765) is None


@pytest.mark.parametrize("host", ["127.0.0.1:8765", "LOCALHOST:8765", "[::1]:8765"])
def test_host_parser_positive_and_port_eighty(host):
    assert authority(host, 8765) is not None
    assert authority("LOCALHOST", 80) == "localhost"
    assert authority("localhost:80", 80) == "localhost"


@pytest.mark.parametrize(
    "value",
    [
        "null",
        "",
        "http://localhost:8765",
        "http://127.0.0.1:8766",
        "https://127.0.0.1:8765",
        "http://evil.example:8765",
        "file:///",
        "data:text/plain,x",
        "http://127.0.0.1:8765/",
        "http://127.0.0.1:8765 http://127.0.0.1:8765",
        "http://127.0.0.1:8765@evil.example",
        "http://127.0.0.1:8765\\evil",
        "http://127.0.0.1:8765#x",
    ],
)
def test_origin_refusals(app, value):
    reply = drive(app, headers=[(b"origin", value.encode())])
    assert reply.status == 403
    assert reply.json() == {
        "error": "CROSS_ORIGIN_REJECTED",
        "detail": "The request origin is not accepted.",
    }


@pytest.mark.parametrize("name", [b"origin", b"referer"])
def test_both_origins_must_agree_and_duplicates_refused(app, name):
    other = b"referer" if name == b"origin" else b"origin"
    assert (
        drive(
            app, headers=[(name, b"http://evil.example"), (other, b"http://127.0.0.1:8765")]
        ).status
        == 403
    )
    assert drive(app, headers=[(name, b"http://127.0.0.1:8765")] * 2).status == 403
    assert drive(app, headers=[(name, b"http://127.0.0.1:8765")]).status == 200
    assert drive(app, headers=[(b"host", b"127.0.0.1:8765")]).status == 400


@pytest.mark.parametrize(
    "site,status",
    [
        ("none", 200),
        ("same-origin", 200),
        ("same-site", 403),
        ("cross-site", 403),
        ("", 403),
        ("None", 403),
    ],
)
def test_fetch_metadata(app, site, status):
    assert drive(app, headers=[(b"sec-fetch-site", site.encode())]).status == status
    assert (
        drive(app, path=PATHS[-1], token=None, headers=[(b"sec-fetch-site", b"none")]).status == 401
    )


def test_referer_paths_and_forwarding(app):
    assert same_origin("http://localhost/a?b=1", "localhost", 80, referer=True)
    assert (
        drive(
            app,
            headers=[
                (b"origin", b"http://127.0.0.1:8765"),
                (b"referer", b"http://127.0.0.1:8765/admin/ui"),
            ],
        ).status
        == 200
    )
    assert (
        drive(
            app,
            headers=[
                (b"forwarded", b"host=evil.example;proto=https"),
                (b"x-forwarded-host", b"evil.example"),
                (b"x-forwarded-proto", b"https"),
            ],
        ).status
        == 200
    )


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("token", [None, "wrong", TOKEN])
@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_internal_failure_fixed_and_headers(assets, path, token, method):
    broken = dict(assets)
    del broken[UI_ROUTES[path][0]]
    app = build_admin_app(
        cast(AdminConfigService, Untouchable()),
        token=TOKEN,
        port=8765,
        database_dsn_env="unused",
        ui_resources=broken,
    )
    reply = drive(app, path, method, token)
    assert reply.status == (401 if path == PATHS[-1] and token != TOKEN else 500)
    assert reply.headers["content-security-policy"] == DATA_CSP
    assert (reply.body == b"") is (method == "HEAD")
    category = (
        AdminErrorCategory.UNAUTHORIZED
        if reply.status == 401
        else AdminErrorCategory.INTERNAL_ERROR
    )
    body = json.dumps(error_payload(category), separators=(",", ":")).encode()
    assert reply.body == (b"" if method == "HEAD" else body)
    assert int(reply.headers["content-length"]) == len(body)
    assert {k: reply.headers[k] for k in BROWSER_HEADERS} == BROWSER_HEADERS


def test_real_server_resources_without_state_or_conditional_responses(tmp_path, assets):
    harness = build_service(tmp_path)
    before = (
        harness.service.snapshot(),
        harness.config_path.read_bytes(),
        harness.adapter.execute_calls,
    )
    state = Untouchable()
    server = AdminHttpServer(
        app_factory=lambda port: build_admin_app(
            cast(AdminConfigService, state),
            token=TOKEN,
            port=port,
            database_dsn_env="unused",
            audit=cast(AuditLog, state),
            ui_resources=assets,
        ),
        host="127.0.0.1",
        port=0,
        ui_enabled=True,
    )
    try:
        with server:
            for path in PATHS:
                get = request(
                    server.port,
                    "GET",
                    path,
                    headers={
                        "Range": "bytes=0-1",
                        "If-None-Match": "*",
                        "If-Modified-Since": "Wed, 01 Jan 2020 00:00:00 GMT",
                        "Accept-Encoding": "gzip",
                    },
                )
                head = request(server.port, "HEAD", path)
                assert get.status == head.status == 200
                assert get.body == assets[UI_ROUTES[path][0]] and head.body == b""
                assert {k: v for k, v in get.headers.items() if k != "date"} == {
                    k: v for k, v in head.headers.items() if k != "date"
                }
            assert (
                request(
                    server.port,
                    "GET",
                    PATHS[0],
                    headers={"X-Forwarded-Proto": "https", "Forwarded": "host=evil;proto=https"},
                ).status
                == 200
            )
            assert server._server is not None and server._server.config.proxy_headers is False
        assert state.touches == []
        assert before == (
            harness.service.snapshot(),
            harness.config_path.read_bytes(),
            harness.adapter.execute_calls,
        )
    finally:
        harness.close()


def test_data_headers_on_authenticated_api(tmp_path, assets):
    harness = build_service(tmp_path)
    try:
        app = build_admin_app(
            harness.service, token=TOKEN, port=8765, database_dsn_env="unused", ui_resources=assets
        )
        reply = drive(app, "/admin/v1/status")
        assert reply.status == 200 and reply.headers["content-security-policy"] == DATA_CSP
    finally:
        harness.close()


def test_outer_exception_containment_and_forbidden_headers():
    async def explode(_scope, _receive, _send):
        raise RuntimeError("private-marker")

    assert drive(wrap_boundary(explode, token=TOKEN, port=8765, ui_enabled=True)).status == 500


def test_server_parser_vs_asgi_and_loopback_aliases(assets):
    state = Untouchable()
    with AdminHttpServer(
        app_factory=lambda port: build_admin_app(
            cast(AdminConfigService, state),
            token=TOKEN,
            port=port,
            database_dsn_env="unused",
            ui_resources=assets,
        ),
        host="127.0.0.1",
        port=0,
        ui_enabled=True,
    ) as server:
        for host in ("127.0.0.1", "localhost", "LOCALHOST", "[::1]"):
            authority_header = f"{host}:{server.port}"
            reply = request(
                server.port,
                "GET",
                "/admin/ui",
                host=authority_header,
                headers={"Origin": "http://" + authority_header},
            )
            assert reply.status == 200
        assert (
            request(server.port, "GET", "/admin/ui", host=f"evil.example:{server.port}").status
            == 400
        )
        assert (
            request(
                server.port,
                "GET",
                "/admin/ui",
                headers={"Origin": f"http://localhost:{server.port}"},
            ).status
            == 403
        )
        with socket.create_connection(("127.0.0.1", server.port), timeout=5) as connection:
            connection.sendall(
                (
                    f"GET /admin/ui HTTP/1.1\r\nHost: localhost:{server.port}\r\n"
                    f"Host: localhost:{server.port}\r\nConnection: close\r\n\r\n"
                ).encode()
            )
            wire = b""
            while chunk := connection.recv(65536):
                wire += chunk
        assert wire.startswith(b"HTTP/1.1 400 ")
        # O parser recusa antes do ASGI: nao alegar headers da nossa fronteira.
        assert b"content-security-policy" not in wire.lower()
    assert state.touches == []


def test_response_headers_strip_forbidden_values():
    async def leaky(_scope, _receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (name.encode(), b"marker")
                    for name in (
                        "set-cookie",
                        "server",
                        "etag",
                        "last-modified",
                        "allow",
                        "access-control-allow-origin",
                        "access-control-allow-credentials",
                    )
                ],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    reply = drive(wrap_boundary(leaky, token=TOKEN, port=8765, ui_enabled=True))
    assert reply.status == 200
    assert all(value != "marker" for value in reply.headers.values())


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    "field,status", [(b"host", 400), (b"origin", 403), (b"content-length", 413)]
)
def test_head_early_refusals_equal_get(app, path, field, status):
    value = b"1048577" if field == b"content-length" else b"invalid"
    headers = [(field, value)]
    get = drive(app, path, "GET", None, headers=headers)
    head = drive(app, path, "HEAD", None, headers=headers)
    assert get.status == head.status == status
    assert get.headers == head.headers and head.body == b""
    assert int(head.headers["content-length"]) == len(get.body)
    assert head.headers["content-security-policy"] == DATA_CSP
    assert set(get.json()) == {"error", "detail"}


def test_duplicate_fetch_metadata_is_not_a_credential(app):
    assert drive(app, headers=[(b"sec-fetch-site", b"same-origin")] * 2).status == 403


def test_handlers_keep_immutable_snapshot_of_mapping(assets):
    supplied = dict(assets)
    app = build_admin_app(
        cast(AdminConfigService, Untouchable()),
        token=TOKEN,
        port=8765,
        database_dsn_env="unused",
        ui_resources=supplied,
    )
    supplied.clear()
    for path in PATHS:
        reply = drive(app, path)
        assert reply.status == 200 and reply.body == assets[UI_ROUTES[path][0]]
