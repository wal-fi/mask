"""Fase 9, Etapa 4: contrato, fronteira, vazamento e v1 intacta (F9-004, F9-022,
F9-024, F9-026, F9-034, spec §8, D-093 a D-095).

Tudo pela porta HTTP real, com o catalogo cifrado real e o coordenador real; so
os adapters upstream sao dubles. Cada operacao sem efeito e conferida contra o
MESMO estado: bytes do store e da ancora, revision do catalogo, revisions e
`last_test` dos registros, geracoes publicadas e candidatos em voo.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import threading
from collections.abc import Callable, Iterator
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute

from maskgw.admin.http import READ_PATHS, VALIDATE_PATH, WRITE_ROUTES, AdminHttpServer
from maskgw.admin.http import build_admin_app as build_app
from maskgw.admin.http.app import build_router
from maskgw.admin.http.v2.errors import DatasourceAdminError
from maskgw.admin.http.v2.operations import DatasourceAdmin
from maskgw.admin.http.v2.routes import V2_READ_PATHS, V2_WRITE_ROUTES
from maskgw.admin.http.v2.schemas import DatasourceCreateRequest, DatasourceTestDraftRequest
from maskgw.audit import AuditLog
from maskgw.datasource import CrashPoint
from maskgw.datasource.models import DatasourceDraft, DatasourcePolicy
from maskgw.errors import DatabaseError
from maskgw.runtime.datasource_service import DatasourceWriteProbe
from maskgw.runtime.datasources import RegistryLimits
from tests.admin_http_support import (
    EXCEPTION_ID,
    RULE_ID,
    TOKEN,
    Reply,
    request,
)
from tests.admin_v2_support import (
    ADDRESS,
    ALIAS,
    HOST,
    OTHER_ADDRESS,
    OTHER_ALIAS,
    OTHER_HOST,
    OTHER_SECRET,
    SECRET,
    V2Harness,
    build_v2,
    create_body,
    draft_body,
    scan,
    update_body,
)
from tests.datasource_runtime_support import capability_failure

REPO_ROOT = Path(__file__).resolve().parents[1]
MISSING_ID = "dso_" + "e" * 32


@pytest.fixture
def v2(tmp_path: Path) -> Iterator[V2Harness]:
    harness = build_v2(tmp_path)
    harness.start()
    try:
        yield harness
    finally:
        harness.close()


def _error(reply: Reply, status: int, category: str) -> dict[str, Any]:
    assert reply.status == status, reply.text()
    body: dict[str, Any] = reply.json()
    assert body["error"] == category
    assert set(body) <= {"error", "detail", "current_revision", "fields"}
    return body


def _no_leak(reply: Reply) -> None:
    assert scan(reply.text()) == [], reply.text()
    assert scan(json.dumps(reply.headers)) == []


# -- superficie -----------------------------------------------------------------


def _pairs(app: Any) -> set[tuple[str, str]]:
    return {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods or ()
    }


def _router(v2: V2Harness, *, with_v2: bool) -> Any:
    return build_router(
        v2.v1.service,
        secrets=v2.secrets,
        database_dsn_env="MASKGW_DATABASE_DSN",
        audit=AuditLog(),
        datasources=v2.runtime if with_v2 else None,
    )


def test_v2_inventory_is_literal_and_v1_is_unchanged(v2: V2Harness) -> None:
    v1_pairs = {(path, method) for path in READ_PATHS for method in ("GET", "HEAD")}
    v1_pairs |= {(VALIDATE_PATH, "POST"), *WRITE_ROUTES}
    v2_pairs = {(path, method) for path in V2_READ_PATHS for method in ("GET", "HEAD")}
    v2_pairs |= set(V2_WRITE_ROUTES)

    assert _pairs(_router(v2, with_v2=False)) == v1_pairs
    assert _pairs(_router(v2, with_v2=True)) == v1_pairs | v2_pairs
    assert all(path.startswith("/admin/v2/") for path, _ in v2_pairs)
    assert not any(method in {"OPTIONS", "PATCH"} for _, method in v2_pairs)
    forbidden = ("sql", "query", "execute", "dsn", "secret", "master", "audit", "mcp", "default")
    assert not any(word in path for path, _ in v2_pairs for word in forbidden)


def test_without_the_catalog_v2_does_not_exist(tmp_path: Path) -> None:
    harness = build_v2(tmp_path)
    harness.start(with_v2=False)
    try:
        for path in ("/admin/v2/status", "/admin/v2/datasources"):
            _error(harness.call("GET", path), 404, "NOT_FOUND")
        _error(
            harness.call("POST", "/admin/v2/datasources", create_body()),
            404,
            "NOT_FOUND",
        )
        assert harness.store.revision == 1
    finally:
        harness.close()


def test_the_v1_app_never_imports_v2_or_the_catalog() -> None:
    script = textwrap.dedent(
        """
        import pathlib, sys, tempfile
        from maskgw.admin.http import build_admin_app
        from maskgw.admin.http.app import build_router
        from maskgw.audit import AuditLog
        from maskgw.secretsource import MappingSecretProvider
        import maskgw.bootstrap.application
        from tests.admin_http_support import build_service

        # Um app v1 CONSTRUIDO, e nao so importado: o registro condicional da
        # v2 tambem nao pode carregar nada do catalogo.
        harness = build_service(pathlib.Path(tempfile.mkdtemp()))
        try:
            build_admin_app(
                harness.service, token="t" * 40, port=1, database_dsn_env="X", audit=AuditLog()
            )
            router = build_router(
                harness.service,
                secrets=MappingSecretProvider({}),
                database_dsn_env="X",
                audit=AuditLog(),
            )
            assert not any(
                getattr(route, "path", "").startswith("/admin/v2") for route in router.routes
            )
        finally:
            harness.close()
        loaded = sorted(
            name for name in sys.modules
            if name.startswith(
                ("maskgw.admin.http.v2", "maskgw.datasource", "maskgw.audit.datasource")
            )
        )
        print(loaded)
        """
    )
    result = subprocess.run(  # noqa: S603 - interpretador e script fixos
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
        env={
            "PYTHONPATH": os.pathsep.join((str(REPO_ROOT / "src"), str(REPO_ROOT))),
            "SYSTEMROOT": _systemroot(),
        },
    )
    assert result.stdout.strip().splitlines()[-1] == "[]"


def _systemroot() -> str:
    return os.environ.get("SYSTEMROOT", "")


# -- v1 byte a byte ---------------------------------------------------------------


def _v1_probes() -> list[Callable[[int], Reply]]:
    """Sondas da v1: leituras, recusas de fronteira, validate e uma escrita recusada."""
    probes: list[Callable[[int], Reply]] = [
        partial(
            _probe,
            method=method,
            path=path.replace("{rule_id}", RULE_ID).replace("{exception_id}", EXCEPTION_ID),
        )
        for path in READ_PATHS
        for method in ("GET", "HEAD")
    ]
    probes += [
        partial(_probe, path="/admin/v1/rules/rul_malformed"),
        partial(_probe, path="/admin/v1/nao-existe"),
        partial(_probe, token=None),
        partial(_probe, token="x" * 40),
        partial(_probe, host="evil.example:1"),
        partial(_probe, headers={"Origin": "http://evil.example"}),
        partial(_probe, method="OPTIONS"),
        partial(_probe, method="POST", body=b"{}"),
        partial(_probe, method="POST", path=VALIDATE_PATH, body=b"{}", content_type="text/plain"),
        partial(_probe, method="POST", path=VALIDATE_PATH, body=b"{}"),
        partial(
            _probe,
            method="POST",
            path=VALIDATE_PATH,
            body=b'{"masking": [{"match": "x", "transformer": "nao_existe"}]}',
        ),
        partial(_probe, method="POST", path=VALIDATE_PATH, body=b'{"x": 1}'),
        partial(
            _probe,
            method="PUT",
            path="/admin/v1/database",
            body=b'{"expected_revision": 99, "statement_timeout_ms": 1000, "max_rows": 5}',
        ),
        partial(
            _probe,
            method="POST",
            path=VALIDATE_PATH,
            body=b"{" + b" " * (1024 * 1024 + 10) + b"}",
        ),
        partial(_probe),
    ]
    return probes


def _probe(
    port: int,
    *,
    method: str = "GET",
    path: str = "/admin/v1/status",
    body: bytes | None = None,
    content_type: str | None = None,
    **kwargs: Any,
) -> Reply:
    if body is not None and content_type is None:
        content_type = "application/json"
    return request(port, method, path, body=body, content_type=content_type, **kwargs)


def _comparable(reply: Reply) -> tuple[int, dict[str, str], bytes]:
    headers = {name: value for name, value in reply.headers.items() if name != "date"}
    return reply.status, headers, reply.body


def test_v1_responses_are_byte_for_byte_identical_with_v2_enabled(v2: V2Harness) -> None:
    # O catalogo tem conteudo, para que a v2 nao seja comparada vazia.
    v2.create()
    plain = AdminHttpServer(
        app_factory=lambda bound: build_app(
            v2.v1.service,
            token=TOKEN,
            port=bound,
            secrets=v2.secrets,
            database_dsn_env="MASKGW_DATABASE_DSN",
            audit=v2.audit_log,
        ),
        host="127.0.0.1",
        port=0,
    )
    plain.start()
    try:
        # A MESMA sonda nos dois apps, em sequencia: os contadores da v1
        # (`admin_operations_total`) avancam juntos e o estado comparado e igual.
        for probe in _v1_probes():
            with_v2 = _comparable(probe(v2.port))
            without = _comparable(probe(plain.port))
            assert with_v2 == without
    finally:
        plain.stop()
    assert v2.v1.service.revision == 3
    # Nenhuma sonda da v1 gerou auditoria de datasource.
    assert [e["operation"] for e in v2.audit.datasource_events()] == ["datasource_create"]


# -- fronteira ----------------------------------------------------------------


def test_v2_sits_behind_the_same_boundary(v2: V2Harness) -> None:
    body = json.dumps({"expected_catalog_revision": "nao-e-int"}).encode()
    cases: list[tuple[dict[str, Any], int, str]] = [
        ({"token": None}, 401, "UNAUTHORIZED"),
        ({"token": "y" * 40}, 401, "UNAUTHORIZED"),
        ({"host": "evil.example:1"}, 400, "HOST_NOT_ALLOWED"),
        ({"headers": {"Origin": "http://127.0.0.1"}}, 403, "CROSS_ORIGIN_REJECTED"),
        ({"headers": {"Referer": "http://127.0.0.1/"}}, 403, "CROSS_ORIGIN_REJECTED"),
        ({"content_type": "text/plain"}, 415, "UNSUPPORTED_MEDIA_TYPE"),
    ]
    for kwargs, status, category in cases:
        options: dict[str, Any] = {"content_type": "application/json", **kwargs}
        reply = request(v2.port, "POST", "/admin/v2/datasources", body=body, **options)
        # Sem credencial valida nunca ha 422: o schema nao vira oraculo.
        _error(reply, status, category)
        assert reply.headers["cache-control"] == "no-store"
        assert reply.cors_headers == []
    big = request(
        v2.port,
        "POST",
        "/admin/v2/datasources",
        body=b"{" + b" " * (1024 * 1024 + 1) + b"}",
        content_type="application/json",
    )
    _error(big, 413, "PAYLOAD_TOO_LARGE")
    _error(v2.call("OPTIONS", "/admin/v2/datasources"), 405, "METHOD_NOT_ALLOWED")
    _error(v2.call("PATCH", "/admin/v2/datasources", {}), 405, "METHOD_NOT_ALLOWED")
    for path in ("/admin/v2/docs", "/admin/v2/openapi.json", "/admin/v2/datasources/", "/admin/v2"):
        _error(v2.call("GET", path), 404, "NOT_FOUND")
    assert v2.audit.datasource_events() == []
    assert v2.store.revision == 1


def test_schema_errors_are_closed_and_never_echo_the_value(v2: V2Harness) -> None:
    dsn = f"postgresql://{SECRET}@{HOST}:5432/x"
    variants: list[dict[str, Any]] = []
    root = create_body()
    root["dsn"] = dsn
    variants.append(root)
    for where, name in (("connection", "dsn"), ("connection", "url"), ("credential", "conninfo")):
        body = create_body()
        body[where][name] = dsn
        variants.append(body)
    wrong_types: list[tuple[str | None, str, object]] = [
        ("connection", "port", "5432"),
        (None, "enabled", 1),
        (None, "expected_catalog_revision", "1"),
    ]
    for section, name, value in wrong_types:
        body = create_body()
        (body if section is None else body[section])[name] = value
        variants.append(body)
    for host in (dsn, f"{SECRET}@{HOST}", "a/b.example", " db.example", "localhost"):
        body = create_body()
        body["connection"]["host"] = host
        variants.append(body)
    for password in (f"{SECRET}\x00", "x" * 1025, ""):
        variants.append(create_body(password=password))
    body = create_body()
    body["credential"]["password"] = 12345
    variants.append(body)
    body = create_body()
    del body["policy"]
    variants.append(body)
    body = create_body()
    body["policy"]["sql"] = {}
    variants.append(body)
    body = create_body()
    body["policy"]["masking"][0]["id"] = "rul_" + "a" * 32
    variants.append(body)
    body = create_body()
    body["policy"]["revision"] = 3
    variants.append(body)

    before = v2.state()
    for payload in variants:
        reply = v2.call("POST", "/admin/v2/datasources", payload)
        error = _error(reply, 422, "SCHEMA_INVALID")
        assert "fields" in error
        _no_leak(reply)
        assert "postgresql://" not in reply.text()
    assert v2.state() == before
    # Falha de schema nao alcanca o handler: nenhuma auditoria.
    assert v2.audit.datasource_events() == []


# -- leituras -------------------------------------------------------------------


def test_reads_never_carry_the_secret_or_the_pinned_addresses(v2: V2Harness) -> None:
    created = v2.create()
    ds_id = created["datasource_id"]
    replies = [
        v2.call("GET", "/admin/v2/status"),
        v2.call("GET", "/admin/v2/datasources"),
        v2.call("GET", f"/admin/v2/datasources/{ds_id}"),
        v2.call("GET", f"/admin/v2/datasources/{ds_id}/policy"),
    ]
    for reply in replies:
        assert reply.status == 200, reply.text()
        text = reply.text()
        for forbidden in (SECRET, ADDRESS, "nonce", "ciphertext", "upstream_secret", "resolved"):
            assert forbidden not in text
        assert reply.headers["cache-control"] == "no-store"

    listing = replies[1].json()
    assert listing["catalog_revision"] == 2
    (summary,) = listing["datasources"]
    assert set(summary) == {
        "id",
        "alias",
        "display_name",
        "enabled",
        "revision",
        "last_test",
        "runtime",
    }
    assert HOST not in replies[1].text()

    detail = replies[2].json()
    assert detail["catalog_revision"] == 2
    view = detail["datasource"]
    assert view["credential"] == {"configured": True}
    assert view["connection"]["host"] == HOST
    assert view["effective_limits"] == {"statement_timeout_ms": 5_000, "max_rows": 100}
    assert view["runtime"]["published"] is True
    assert view["runtime"]["sessions"] == 0
    assert view["last_test"] == {"status": "never", "checked_at": None}

    policy = replies[3].json()
    assert policy["revision"] == 1
    assert "id" not in json.dumps(policy["policy"]["masking"])
    assert policy["policy"]["sql"] == {
        "allowed_pg_functions": [],
        "denied_functions": ["dblink_exec"],
    }

    status = replies[0].json()
    assert status["datasources"] == {"total": 1, "enabled": 1, "published": 1}
    assert status["writes_blocked"] is False
    assert status["dns_timeout_ms"] == 5000

    head = v2.call("HEAD", f"/admin/v2/datasources/{ds_id}")
    assert head.status == 200
    assert head.body == b""
    assert v2.audit.datasource_events()[-1]["operation"] == "datasource_create"
    assert len(v2.audit.datasource_events()) == 1


def test_unknown_and_malformed_ids_are_the_same_not_found(v2: V2Harness) -> None:
    replies = [
        v2.call("GET", f"/admin/v2/datasources/{MISSING_ID}"),
        v2.call("GET", "/admin/v2/datasources/dso_malformado"),
        v2.call("GET", f"/admin/v2/datasources/{SECRET}"),
        v2.call("GET", f"/admin/v2/datasources/{MISSING_ID}/policy"),
    ]
    bodies = {reply.body for reply in replies}
    assert len(bodies) == 1
    _error(replies[0], 404, "NOT_FOUND")
    assert SECRET not in replies[2].text()


# -- criar ------------------------------------------------------------------------


def test_create_enabled_verifies_persists_and_publishes(v2: V2Harness) -> None:
    reply = v2.call("POST", "/admin/v2/datasources", create_body())
    assert reply.status == 200, reply.text()
    body = reply.json()
    assert set(body) == {"catalog_revision", "datasource_id", "datasource_revision", "changed"}
    assert body["catalog_revision"] == 2
    assert body["datasource_revision"] == 1
    assert body["changed"] is True
    _no_leak(reply)
    assert v2.published() == {ALIAS: 1}
    record = v2.store.get(body["datasource_id"])
    assert record.resolved_addresses == (ADDRESS,)
    assert v2.store.read_upstream_secret(record.id) == SECRET
    # A conexao de verificacao abriu e fechou.
    assert len(v2.factory.adapters) == 1
    assert v2.factory.open_adapters() == []


def test_create_disabled_persists_without_connecting(v2: V2Harness) -> None:
    body = v2.create(enabled=False)
    assert v2.published() == {}
    assert v2.factory.adapters == []
    assert v2.store.get(body["datasource_id"]).enabled is False


@pytest.mark.parametrize("enabled", [True, False])
def test_invalid_policy_is_refused_without_effect_even_when_disabled(
    v2: V2Harness, enabled: bool
) -> None:
    policy = {
        "masking": [{"match": "cpf", "transformer": "nao_existe"}],
        "exceptions": [],
        "database": {"statement_timeout_ms": 1000, "max_rows": 10},
        "sql": {"denied_functions": []},
    }
    before = v2.state()
    reply = v2.call("POST", "/admin/v2/datasources", create_body(enabled=enabled, policy=policy))
    _error(reply, 422, "DATASOURCE_POLICY_INVALID")
    assert v2.state() == before
    assert v2.factory.adapters == []


@pytest.mark.parametrize("value", [None, [], ["pg_read_file"], "pg_read_file", {"x": 1}])
def test_allowed_pg_functions_is_never_administrable(v2: V2Harness, value: object) -> None:
    body = create_body()
    body["policy"]["sql"]["allowed_pg_functions"] = value
    before = v2.state()
    _error(v2.call("POST", "/admin/v2/datasources", body), 422, "IMMUTABLE_FIELD")
    draft = draft_body()
    draft["policy"]["sql"]["allowed_pg_functions"] = value
    _error(v2.call("POST", "/admin/v2/datasources:test", draft), 422, "IMMUTABLE_FIELD")
    assert v2.state() == before
    assert v2.factory.adapters == []


def test_create_conflicts_are_refused_before_the_candidate(v2: V2Harness) -> None:
    v2.create()
    before = v2.state()
    adapters = len(v2.factory.adapters)
    stale = _error(
        v2.call("POST", "/admin/v2/datasources", create_body(alias=OTHER_ALIAS, expected=1)),
        409,
        "REVISION_CONFLICT",
    )
    assert stale["current_revision"] == 2
    duplicate = v2.call("POST", "/admin/v2/datasources", create_body(expected=2))
    _error(duplicate, 409, "ALIAS_CONFLICT")
    assert ALIAS not in duplicate.text()
    assert v2.state() == before
    assert len(v2.factory.adapters) == adapters


@pytest.mark.parametrize(
    ("host", "category"),
    [
        ("127.0.0.1", "DATASOURCE_DESTINATION_REJECTED"),
        ("169.254.169.254", "DATASOURCE_DESTINATION_REJECTED"),
        ("0.0.0.0", "DATASOURCE_DESTINATION_REJECTED"),  # noqa: S104 - destino recusado
        ("8.8.8.8", "DATASOURCE_DESTINATION_REJECTED"),
    ],
)
def test_forbidden_destinations_are_refused_without_effect(
    v2: V2Harness, host: str, category: str
) -> None:
    before = v2.state()
    for method, path, body in (
        ("POST", "/admin/v2/datasources", create_body(host=host)),
        ("POST", "/admin/v2/datasources:test", draft_body(host=host)),
    ):
        reply = v2.call(method, path, body)
        _error(reply, 422, category)
        assert host not in reply.text()
    assert v2.state() == before
    assert v2.factory.adapters == []


@pytest.mark.parametrize(
    ("failure", "category"),
    [
        (
            DatabaseError(f"FATAL: password authentication failed {SECRET} {HOST}"),
            "DATASOURCE_CONNECTION_FAILED",
        ),
        (capability_failure(), "DATASOURCE_CAPABILITY_MISSING"),
    ],
)
def test_candidate_failures_have_no_effect_and_no_leak(
    v2: V2Harness, failure: BaseException, category: str
) -> None:
    before = v2.state()
    v2.factory.connect_failure = failure
    for method, path, body in (
        ("POST", "/admin/v2/datasources", create_body()),
        ("POST", "/admin/v2/datasources:test", draft_body()),
    ):
        reply = v2.call(method, path, body)
        _error(reply, 422, category)
        _no_leak(reply)
    assert v2.state() == before
    assert v2.factory.open_adapters() == []


# -- testes de candidato sem efeito ---------------------------------------------------


def test_testing_a_draft_or_a_datasource_has_no_effect(v2: V2Harness) -> None:
    created = v2.create()
    before = v2.state()
    draft = v2.call(
        "POST", "/admin/v2/datasources:test", draft_body(alias=OTHER_ALIAS, host=OTHER_HOST)
    )
    assert draft.status == 200, draft.text()
    assert draft.json() == {"passed": True, "persisted": False, "published": False}
    persisted = v2.call("POST", f"/admin/v2/datasources/{created['datasource_id']}:test", {})
    assert persisted.status == 200
    assert persisted.json() == {"passed": True, "persisted": False, "published": False}
    assert v2.state() == before
    assert v2.factory.open_adapters() == []
    tests = [
        e for e in v2.audit.datasource_events() if e["operation"].startswith("datasource_test")
    ]
    assert [e["operation"] for e in tests] == ["datasource_test_draft", "datasource_test"]
    assert all(e["revision_before"] is None and e["revision_after"] is None for e in tests)
    assert tests[0]["target_id"] is None
    assert tests[1]["target_id"] == created["datasource_id"]


def test_testing_a_disabled_or_unknown_datasource_is_refused(v2: V2Harness) -> None:
    disabled = v2.create(enabled=False)
    adapters = len(v2.factory.adapters)
    _error(
        v2.call("POST", f"/admin/v2/datasources/{disabled['datasource_id']}:test", {}),
        409,
        "DATASOURCE_DISABLED",
    )
    _error(v2.call("POST", f"/admin/v2/datasources/{MISSING_ID}:test", {}), 404, "NOT_FOUND")
    _error(
        v2.call("POST", f"/admin/v2/datasources/{disabled['datasource_id']}:test", {"x": 1}),
        422,
        "SCHEMA_INVALID",
    )
    assert len(v2.factory.adapters) == adapters


# -- editar ---------------------------------------------------------------------------


def test_update_uses_the_datasource_revision_not_the_catalog_one(v2: V2Harness) -> None:
    first = v2.create()
    second = v2.create(alias=OTHER_ALIAS, host=OTHER_HOST)
    # Uma escrita em B muda a revision do CATALOGO...
    reply = v2.call(
        "PUT", f"/admin/v2/datasources/{second['datasource_id']}", update_body(1, host=OTHER_HOST)
    )
    assert reply.status == 200, reply.text()
    # ...e nao invalida a edicao pendente de A, cuja revision propria e 1 (F9-025).
    reply = v2.call("PUT", f"/admin/v2/datasources/{first['datasource_id']}", update_body(1))
    assert reply.status == 200, reply.text()
    body = reply.json()
    assert body["datasource_revision"] == 2
    assert body["catalog_revision"] == 5
    record = v2.store.get(first["datasource_id"])
    assert record.display_name == "Novo"
    assert record.limits.max_rows == 50
    # O que a rota nao administra fica: habilitacao, politica e segredo.
    assert record.enabled is True
    expected_policy = create_body()["policy"]
    expected_policy["sql"] = {"allowed_pg_functions": [], "denied_functions": ["dblink_exec"]}
    assert record.policy == DatasourcePolicy.from_mapping(expected_policy)
    assert v2.store.read_upstream_secret(record.id) == SECRET
    assert v2.published()[ALIAS] > 1


def test_stale_datasource_revision_is_a_conflict_with_the_current_one(v2: V2Harness) -> None:
    created = v2.create()
    ds_id = created["datasource_id"]
    assert v2.call("PUT", f"/admin/v2/datasources/{ds_id}", update_body(1)).status == 200
    before = v2.state()
    for method, path, body in (
        ("PUT", f"/admin/v2/datasources/{ds_id}", update_body(1)),
        (
            "POST",
            f"/admin/v2/datasources/{ds_id}:rotate-credential",
            {"expected_revision": 1, "credential": {"password": OTHER_SECRET}},
        ),
        ("POST", f"/admin/v2/datasources/{ds_id}:disable", {"expected_revision": 1}),
        (
            "DELETE",
            f"/admin/v2/datasources/{ds_id}",
            {"expected_revision": 1, "confirm_alias": ALIAS},
        ),
        (
            "PUT",
            f"/admin/v2/datasources/{ds_id}/policy",
            {"expected_revision": 1, "policy": create_body()["policy"]},
        ),
    ):
        reply = v2.call(method, path, body)
        conflict = _error(reply, 409, "REVISION_CONFLICT")
        assert conflict["current_revision"] == 2
        _no_leak(reply)
    assert v2.state() == before


@pytest.mark.parametrize("alias", [ALIAS, OTHER_ALIAS, None, 1])
def test_alias_is_immutable(v2: V2Harness, alias: object) -> None:
    created = v2.create()
    body = update_body(1)
    body["alias"] = alias
    before = v2.state()
    _error(
        v2.call("PUT", f"/admin/v2/datasources/{created['datasource_id']}", body),
        422,
        "IMMUTABLE_FIELD",
    )
    assert v2.state() == before


@pytest.mark.parametrize(
    ("name", "value"),
    [("enabled", False), ("policy", {}), ("credential", {"password": OTHER_SECRET}), ("dsn", "x")],
)
def test_update_body_is_closed(v2: V2Harness, name: str, value: object) -> None:
    created = v2.create()
    body = update_body(1)
    body[name] = value
    before = v2.state()
    reply = v2.call("PUT", f"/admin/v2/datasources/{created['datasource_id']}", body)
    _error(reply, 422, "SCHEMA_INVALID")
    assert OTHER_SECRET not in reply.text()
    assert v2.state() == before


def test_new_destination_is_resolved_again_and_pinned(v2: V2Harness) -> None:
    created = v2.create()
    reply = v2.call(
        "PUT", f"/admin/v2/datasources/{created['datasource_id']}", update_body(1, host=OTHER_HOST)
    )
    assert reply.status == 200, reply.text()
    assert v2.store.get(created["datasource_id"]).resolved_addresses == (OTHER_ADDRESS,)


def test_same_destination_keeps_the_dns_pin(tmp_path: Path) -> None:
    table = {HOST: (ADDRESS,)}
    harness = build_v2(tmp_path, resolver=lambda host, _port: table.get(host, (host,)))
    harness.start()
    try:
        created = harness.create()
        before = harness.state()
        table[HOST] = ("10.99.99.99",)  # DNS trocado depois da validacao (D-084)
        reply = harness.call(
            "PUT", f"/admin/v2/datasources/{created['datasource_id']}", update_body(1)
        )
        _error(reply, 422, "DATASOURCE_DESTINATION_REJECTED")
        assert "10.99.99.99" not in reply.text()
        assert harness.state() == before
    finally:
        harness.close()


def test_update_of_a_disabled_datasource_never_connects(v2: V2Harness) -> None:
    created = v2.create(enabled=False)
    reply = v2.call("PUT", f"/admin/v2/datasources/{created['datasource_id']}", update_body(1))
    assert reply.status == 200, reply.text()
    assert v2.factory.adapters == []
    assert v2.published() == {}


# -- credencial -------------------------------------------------------------------------


def test_rotation_verifies_the_new_secret_and_swaps_the_generation(v2: V2Harness) -> None:
    created = v2.create()
    ds_id = created["datasource_id"]
    generation = v2.published()[ALIAS]
    reply = v2.call(
        "POST",
        f"/admin/v2/datasources/{ds_id}:rotate-credential",
        {"expected_revision": 1, "credential": {"password": OTHER_SECRET}},
    )
    assert reply.status == 200, reply.text()
    _no_leak(reply)
    assert reply.json()["datasource_revision"] == 2
    assert v2.published()[ALIAS] > generation
    assert v2.store.read_upstream_secret(ds_id) == OTHER_SECRET
    # O candidato conectou com a senha NOVA (alvo interno, nunca exposto).
    assert OTHER_SECRET in v2.factory.adapters[-1].conninfo


def test_failed_rotation_keeps_the_old_secret_and_generation(v2: V2Harness) -> None:
    created = v2.create()
    ds_id = created["datasource_id"]
    before = v2.state()
    v2.factory.connect_failure = DatabaseError(f"auth failed for {OTHER_SECRET}")
    reply = v2.call(
        "POST",
        f"/admin/v2/datasources/{ds_id}:rotate-credential",
        {"expected_revision": 1, "credential": {"password": OTHER_SECRET}},
    )
    _error(reply, 422, "DATASOURCE_CONNECTION_FAILED")
    _no_leak(reply)
    assert v2.state() == before
    assert v2.store.read_upstream_secret(ds_id) == SECRET


# -- habilitar, desabilitar, remover -----------------------------------------------------


def test_disable_withdraws_enable_verifies_and_idle_requests_change_nothing(v2: V2Harness) -> None:
    created = v2.create()
    ds_id = created["datasource_id"]
    disabled = v2.call("POST", f"/admin/v2/datasources/{ds_id}:disable", {"expected_revision": 1})
    assert disabled.status == 200
    assert disabled.json()["changed"] is True
    assert v2.published() == {}

    before = v2.state()
    idle = v2.call("POST", f"/admin/v2/datasources/{ds_id}:disable", {"expected_revision": 2})
    assert idle.status == 200
    assert idle.json() == {
        "catalog_revision": 3,
        "datasource_id": ds_id,
        "datasource_revision": 2,
        "changed": False,
    }
    assert v2.state() == before

    v2.factory.connect_failure = capability_failure()
    _error(
        v2.call("POST", f"/admin/v2/datasources/{ds_id}:enable", {"expected_revision": 2}),
        422,
        "DATASOURCE_CAPABILITY_MISSING",
    )
    assert v2.state() == before
    v2.factory.connect_failure = None
    enabled = v2.call("POST", f"/admin/v2/datasources/{ds_id}:enable", {"expected_revision": 2})
    assert enabled.status == 200
    assert ALIAS in v2.published()

    events = v2.audit.datasource_events()
    idle_event = [e for e in events if e["operation"] == "datasource_disable"][1]
    assert idle_event["outcome"] == "success"
    assert idle_event["revision_before"] == idle_event["revision_after"] == 3


def test_delete_requires_the_alias_confirmation(v2: V2Harness) -> None:
    created = v2.create()
    ds_id = created["datasource_id"]
    before = v2.state()
    for confirm in (OTHER_ALIAS, ALIAS.upper(), f"{ALIAS} "):
        reply = v2.call(
            "DELETE",
            f"/admin/v2/datasources/{ds_id}",
            {"expected_revision": 1, "confirm_alias": confirm},
        )
        _error(reply, 422, "CONFIRMATION_MISMATCH")
        assert confirm not in reply.text()
    _error(
        v2.call("DELETE", f"/admin/v2/datasources/{ds_id}", {"expected_revision": 1}),
        422,
        "SCHEMA_INVALID",
    )
    assert v2.state() == before

    reply = v2.call(
        "DELETE", f"/admin/v2/datasources/{ds_id}", {"expected_revision": 1, "confirm_alias": ALIAS}
    )
    assert reply.status == 200, reply.text()
    assert reply.json() == {"catalog_revision": 3, "removed": True}
    assert v2.published() == {}
    _error(v2.call("GET", f"/admin/v2/datasources/{ds_id}"), 404, "NOT_FOUND")
    _error(
        v2.call(
            "DELETE",
            f"/admin/v2/datasources/{ds_id}",
            {"expected_revision": 1, "confirm_alias": ALIAS},
        ),
        404,
        "NOT_FOUND",
    )


# -- politica -------------------------------------------------------------------------


def test_policy_replacement_swaps_and_preserves_the_allowlist(v2: V2Harness) -> None:
    # Um registro migrado do legado pode trazer `allowed_pg_functions`; a v2
    # nunca o altera, mas preserva em conteudo e ordem.
    policy = DatasourcePolicy.from_mapping(
        {"sql": {"allowed_pg_functions": ["pg_typeof", "format_type"], "denied_functions": []}}
    )
    record = v2.service.create(
        DatasourceDraft(
            alias=ALIAS,
            display_name="Legado",
            host=HOST,
            port=5432,
            database="app",
            username="gateway",
            policy=policy,
        ),
        SECRET,
        expected_revision=1,
    )
    generation = v2.published()[ALIAS]
    new_policy = {
        "masking": [{"match": "email", "transformer": "fixed", "config": {"value": "[EMAIL]"}}],
        "exceptions": [],
        "database": {"statement_timeout_ms": 2000, "max_rows": 20},
        "sql": {"denied_functions": ["dblink"]},
    }
    reply = v2.call(
        "PUT",
        f"/admin/v2/datasources/{record.id}/policy",
        {"expected_revision": 1, "policy": new_policy},
    )
    assert reply.status == 200, reply.text()
    assert v2.published()[ALIAS] > generation
    read = v2.call("GET", f"/admin/v2/datasources/{record.id}/policy").json()
    assert read["policy"]["sql"] == {
        "allowed_pg_functions": ["pg_typeof", "format_type"],
        "denied_functions": ["dblink"],
    }
    assert read["policy"]["masking"][0]["transformer"] == "fixed"

    before = v2.state()
    for value in (None, [], ["pg_read_file"]):
        body = {
            "expected_revision": 2,
            "policy": {
                **new_policy,
                "sql": {"denied_functions": [], "allowed_pg_functions": value},
            },
        }
        _error(
            v2.call("PUT", f"/admin/v2/datasources/{record.id}/policy", body),
            422,
            "IMMUTABLE_FIELD",
        )
    bad = {**new_policy, "masking": [{"match": "x", "transformer": "nao_existe"}]}
    _error(
        v2.call(
            "PUT",
            f"/admin/v2/datasources/{record.id}/policy",
            {"expected_revision": 2, "policy": bad},
        ),
        422,
        "DATASOURCE_POLICY_INVALID",
    )
    assert v2.state() == before


# -- persistencia ----------------------------------------------------------------------


def test_write_failure_before_replace_blocks_writes_and_the_catalog(v2: V2Harness) -> None:
    created = v2.create()
    disk = v2.disk()
    published = v2.published()
    v2.crash.point = CrashPoint.AFTER_JOURNAL_FSYNC
    reply = v2.call(
        "POST", "/admin/v2/datasources", create_body(alias=OTHER_ALIAS, host=OTHER_HOST, expected=2)
    )
    _error(reply, 500, "CATALOG_WRITE_ERROR")
    _no_leak(reply)
    # Falha antes do replace: nada aplicado, e as geracoes publicadas ficam.
    assert v2.disk() == disk
    assert v2.published() == published

    ds_id = created["datasource_id"]
    for method, path, body in (
        ("PUT", f"/admin/v2/datasources/{ds_id}", update_body(1)),
        ("POST", f"/admin/v2/datasources/{ds_id}:disable", {"expected_revision": 1}),
        ("GET", "/admin/v2/datasources", None),
        ("GET", f"/admin/v2/datasources/{ds_id}", None),
        ("POST", f"/admin/v2/datasources/{ds_id}:test", {}),
    ):
        blocked = v2.call(method, path, body)
        _error(blocked, 503, "CATALOG_BLOCKED")
        _no_leak(blocked)
    # O status continua respondendo, degradado: o operador ve o bloqueio.
    status = v2.call("GET", "/admin/v2/status")
    assert status.status == 200, status.text()
    payload = status.json()
    assert payload["catalog_available"] is False
    assert payload["catalog_revision"] is None
    assert payload["datasources"] is None
    assert payload["writes_blocked"] is True
    assert payload["registry"]["published"] == 1
    # Testar um rascunho nao escreve nada e continua possivel.
    assert (
        v2.call("POST", "/admin/v2/datasources:test", draft_body(alias=OTHER_ALIAS)).status == 200
    )
    assert v2.disk() == disk
    events = v2.audit.datasource_events()
    categories = [e["error_category"] for e in events]
    assert categories[1:5] == [
        "CATALOG_WRITE_ERROR",
        "CATALOG_BLOCKED",
        "CATALOG_BLOCKED",
        "CATALOG_BLOCKED",
    ]
    assert all(scan(json.dumps(event)) == [] for event in events)


@pytest.mark.parametrize("operation", ["update", "disable"])
def test_uncertain_outcome_is_reported_and_only_withdrawal_takes_effect(
    v2: V2Harness, operation: str
) -> None:
    created = v2.create()
    ds_id = created["datasource_id"]
    generation = v2.published()[ALIAS]
    v2.crash.point = CrashPoint.AFTER_STORE_REPLACE
    if operation == "update":
        reply = v2.call("PUT", f"/admin/v2/datasources/{ds_id}", update_body(1))
    else:
        reply = v2.call("POST", f"/admin/v2/datasources/{ds_id}:disable", {"expected_revision": 1})
    body = _error(reply, 500, "CATALOG_OUTCOME_UNCERTAIN")
    assert "applied" not in body
    _no_leak(reply)
    if operation == "update":
        # Resultado incerto nunca publica: a geracao antiga continua.
        assert v2.published() == {ALIAS: generation}
    else:
        # Reduzir exposicao nao espera confirmacao (D-091).
        assert v2.published() == {}
    event = v2.audit.datasource_events()[-1]
    assert event["outcome"] == "error"
    assert event["revision_after"] is None


# -- capacidade e encerramento ------------------------------------------------------------


def test_busy_registry_refuses_before_building_the_candidate(tmp_path: Path) -> None:
    harness = build_v2(tmp_path, limits=RegistryLimits(max_candidates=1))
    harness.start()
    gate = threading.Event()
    harness.factory.connect_gate = gate
    worker = threading.Thread(
        target=lambda: harness.call(
            "POST", "/admin/v2/datasources:test", draft_body(alias=OTHER_ALIAS)
        ),
        daemon=True,
    )
    try:
        # O teste de candidato ocupa a unica vaga; o handler bloqueia o loop,
        # entao a segunda operacao vem pelo coordenador, como faria outra thread.
        worker.start()
        assert harness.factory.connect_started.wait(10)
        admin = DatasourceAdmin(harness.runtime)
        before = harness.store.revision
        with pytest.raises(DatasourceAdminError) as caught:
            admin.create(
                DatasourceCreateRequest.model_validate(create_body()), DatasourceWriteProbe()
            )
        assert caught.value.category.value == "DATASOURCE_BUSY"
        assert harness.store.revision == before
        assert len(harness.factory.adapters) == 1
    finally:
        gate.set()
        worker.join(10)
        harness.factory.connect_gate = None
        harness.close()
    assert not worker.is_alive()


def test_shutting_down_registry_makes_candidates_unavailable(v2: V2Harness) -> None:
    v2.registry.begin_shutdown()
    before = v2.state()
    _error(
        v2.call("POST", "/admin/v2/datasources", create_body()),
        503,
        "DATASOURCE_SERVICE_UNAVAILABLE",
    )
    _error(
        v2.call("POST", "/admin/v2/datasources:test", draft_body()),
        503,
        "DATASOURCE_SERVICE_UNAVAILABLE",
    )
    assert v2.state() == before


# -- vazamento e erros sanitizados --------------------------------------------------------


def test_errors_never_chain_the_internal_exception(v2: V2Harness) -> None:
    v2.factory.connect_failure = DatabaseError(f"{SECRET} {HOST}")
    admin = DatasourceAdmin(v2.runtime)
    with pytest.raises(DatasourceAdminError) as caught:
        admin.test_draft(DatasourceTestDraftRequest.model_validate(draft_body()))
    error = caught.value
    assert error.__cause__ is None
    assert error.__context__ is None
    assert scan(str(error) + repr(error)) == []


def test_upstream_canaries_never_reach_errors_or_audit(v2: V2Harness) -> None:
    created = v2.create()
    ds_id = created["datasource_id"]
    v2.factory.connect_failure = DatabaseError(f"{SECRET} {OTHER_SECRET} {HOST} {ADDRESS}")
    replies = [
        v2.call(
            "POST",
            "/admin/v2/datasources:test",
            draft_body(alias=OTHER_ALIAS, host=OTHER_HOST, password=OTHER_SECRET),
        ),
        v2.call("POST", f"/admin/v2/datasources/{ds_id}:test", {}),
        v2.call(
            "POST",
            f"/admin/v2/datasources/{ds_id}:rotate-credential",
            {"expected_revision": 1, "credential": {"password": OTHER_SECRET}},
        ),
        v2.call("PUT", f"/admin/v2/datasources/{ds_id}", update_body(1, host=OTHER_HOST)),
        v2.call(
            "POST",
            "/admin/v2/datasources",
            create_body(alias=OTHER_ALIAS, host=OTHER_HOST, expected=2),
        ),
    ]
    for reply in replies:
        assert reply.status == 422
        _no_leak(reply)
    for event in v2.audit.events:
        text = json.dumps(event)
        assert scan(text) == []
        assert ALIAS not in text
        assert OTHER_ALIAS not in text


def test_request_models_never_show_the_password_in_repr() -> None:
    for model in (
        DatasourceCreateRequest.model_validate(create_body()),
        DatasourceTestDraftRequest.model_validate(draft_body()),
    ):
        assert SECRET not in repr(model)
        assert SECRET not in str(model)
