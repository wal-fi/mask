"""Fase 9, Etapa 4 contra PostgreSQL 16 real (F9-004, F9-022, F9-025, F9-026, F9-034).

A aplicacao inteira e composta por `build_application(datasource_catalog=...,
admin_http=...)`: runtime legado conectado ao banco, catalogo cifrado, registry,
coordenador, porta HTTP administrativa real, resolver DNS de producao (processo
filho com prazo) e adapters REAIS com as verificacoes de read-only, timeout e
proveniencia. O DSN vem so de `MASKGW_TEST_DSN` e nunca e impresso; a senha
upstream entra somente no corpo write-only e e procurada como canario em toda
resposta.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from maskgw.admin.http.settings import build as build_admin_settings
from maskgw.bootstrap.application import Application, build_application
from maskgw.datasource import CatalogStore
from maskgw.runtime.datasource_service import DatasourceCatalogSettings
from maskgw.runtime.datasources import DatasourceUnavailableError
from maskgw.secretsource import MappingSecretProvider
from tests.admin_http_support import TOKEN, Reply, free_port, request
from tests.datasource_runtime_support import KEY

pytestmark = pytest.mark.integration

HMAC_KEY = "chave-de-teste-para-hmac-com-tamanho-suficiente"
SCHEMA = "maskgw_etapa4"
TABLE = f"{SCHEMA}.cliente"
CPF = "11122233344"
EMAIL = "joana.ficticia@example.test"
WRONG_PASSWORD = "senha-errada-canario-5c2e"  # noqa: S105 - marcador sintetico


class _Target:
    def __init__(self, dsn: str) -> None:
        values: dict[str, Any] = conninfo_to_dict(dsn)
        host = values.get("hostaddr") or values.get("host")
        if not isinstance(host, str) or not host or "/" in host or "," in host:
            pytest.fail("MASKGW_TEST_DSN precisa de um unico host TCP")
        self.host = host.lower()
        self.port = int(values.get("port") or 5432)
        self.database = str(values["dbname"])
        self.username = str(values["user"])
        self.password = str(values.get("password") or "")
        if not self.password:
            pytest.fail("MASKGW_TEST_DSN precisa de senha para a credencial upstream")

    def body(self, alias: str, *, password: str | None = None, expected: int = 1) -> dict[str, Any]:
        return {
            "expected_catalog_revision": expected,
            "alias": alias,
            "display_name": alias,
            "enabled": True,
            "connection": {
                "host": self.host,
                "port": self.port,
                "database": self.database,
                "username": self.username,
                "tls": {"mode": "disable", "server_name": None},
            },
            "credential": {"password": self.password if password is None else password},
            "limits": {"statement_timeout_ms": 30_000, "max_rows": 100, "max_sessions": 2},
            "destination_policy": {
                "allow_public": True,
                "allow_loopback": True,
                "allowed_hosts": [self.host] if not self.host[0].isdigit() else [],
            },
            "policy": {
                "masking": [{"match": "cpf", "transformer": "hmac_sha256"}],
                "exceptions": [],
                "database": {"statement_timeout_ms": 5_000, "max_rows": 50},
                "sql": {"denied_functions": []},
            },
        }


def _hmac(value: str) -> str:
    return hmac.new(HMAC_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


@pytest.fixture
def target(dsn: str) -> Iterator[_Target]:
    with psycopg.connect(dsn, autocommit=True) as setup:
        setup.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
        setup.execute(f"CREATE SCHEMA {SCHEMA}")
        setup.execute(f"CREATE TABLE {TABLE} (id integer PRIMARY KEY, cpf text, email text)")
        setup.execute(f"INSERT INTO {TABLE} VALUES (1, %s, %s)", [CPF, EMAIL])
    yield _Target(dsn)
    with psycopg.connect(dsn, autocommit=True) as teardown:
        teardown.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")


class _App:
    def __init__(self, application: Application, port: int, store: Path, anchor: Path) -> None:
        self.application = application
        self.port = port
        self.store = store
        self.anchor = anchor

    def call(self, method: str, path: str, body: Any = None) -> Reply:
        payload = None if body is None else json.dumps(body).encode()
        return request(
            self.port,
            method,
            path,
            body=payload,
            content_type="application/json" if payload is not None else None,
            timeout=60,
        )

    def rows(self, alias: str) -> list[list[Any]]:
        gateway = self.application.datasource_gateway
        assert gateway is not None
        with gateway.open_session(alias) as session:
            return session.query(f"SELECT id, cpf, email FROM {TABLE}").rows

    def disk(self) -> tuple[bytes, bytes]:
        return self.store.read_bytes(), self.anchor.read_bytes()


@pytest.fixture
def app(
    tmp_path: Path,
    dsn: str,
    target: _Target,  # noqa: ARG001 - o schema de teste existe antes da aplicacao
) -> Iterator[_App]:
    config = tmp_path / "masking.yaml"
    config.write_text("database:\n  statement_timeout_ms: 2000\n  max_rows: 10\n", encoding="utf-8")
    store = tmp_path / "catalog" / "datasources.store"
    store.parent.mkdir()
    anchor = tmp_path / "catalog-anchor" / "datasources.anchor"
    CatalogStore.initialize(store, anchor_path=anchor, master_key=KEY).close()
    port = free_port()
    application = build_application(
        config_path=config,
        conninfo=dsn,
        secrets=MappingSecretProvider(
            {"MASKGW_DATASOURCE_MASTER_KEY": KEY, "MASKGW_HMAC_KEY": HMAC_KEY}
        ),
        admin_http=build_admin_settings(token=TOKEN, host="127.0.0.1", port=port),
        datasource_catalog=DatasourceCatalogSettings(store_path=store, anchor_path=anchor),
    )
    try:
        yield _App(application, port, store, anchor)
    finally:
        application.close()
    # Locks liberados: o catalogo reabre com a chave.
    CatalogStore.open(store, anchor_path=anchor, master_key=KEY).close()


def _clean(reply: Reply, target: _Target) -> None:
    text = reply.text() + json.dumps(reply.headers)
    for canary in (target.password, WRONG_PASSWORD):
        assert canary not in text


def test_create_publishes_a_real_generation_that_masks(app: _App, target: _Target) -> None:
    reply = app.call("POST", "/admin/v2/datasources", target.body("crm"))
    assert reply.status == 200, reply.text()
    _clean(reply, target)
    assert app.rows("crm") == [[1, _hmac(CPF), EMAIL]]
    detail = app.call("GET", f"/admin/v2/datasources/{reply.json()['datasource_id']}")
    assert detail.status == 200
    _clean(detail, target)
    assert detail.json()["datasource"]["runtime"]["published"] is True


def test_wrong_credential_is_refused_without_effect_and_without_leak(
    app: _App, target: _Target
) -> None:
    before = app.disk()
    for path, body in (
        ("/admin/v2/datasources", target.body("crm", password=WRONG_PASSWORD)),
        (
            "/admin/v2/datasources:test",
            {
                k: v
                for k, v in target.body("crm", password=WRONG_PASSWORD).items()
                if k not in {"expected_catalog_revision", "enabled"}
            },
        ),
    ):
        reply = app.call("POST", path, body)
        assert reply.status == 422, reply.text()
        assert reply.json()["error"] == "DATASOURCE_CONNECTION_FAILED"
        _clean(reply, target)
        assert "password authentication" not in reply.text()
    assert app.disk() == before
    assert app.application.datasources is not None
    assert app.application.datasources.registry.status().published == ()


def test_real_candidate_test_has_no_effect(app: _App, target: _Target) -> None:
    created = app.call("POST", "/admin/v2/datasources", target.body("crm")).json()
    before = app.disk()
    draft = {
        k: v
        for k, v in target.body("fin").items()
        if k not in {"expected_catalog_revision", "enabled"}
    }
    reply = app.call("POST", "/admin/v2/datasources:test", draft)
    assert reply.status == 200, reply.text()
    persisted = app.call("POST", f"/admin/v2/datasources/{created['datasource_id']}:test", {})
    assert persisted.status == 200, persisted.text()
    assert app.disk() == before
    assert app.application.datasources is not None
    assert [g.alias for g in app.application.datasources.registry.status().published] == ["crm"]


def test_rotation_disable_enable_and_delete_against_postgresql(app: _App, target: _Target) -> None:
    created = app.call("POST", "/admin/v2/datasources", target.body("crm")).json()
    ds_id = created["datasource_id"]
    failed = app.call(
        "POST",
        f"/admin/v2/datasources/{ds_id}:rotate-credential",
        {"expected_revision": 1, "credential": {"password": WRONG_PASSWORD}},
    )
    assert failed.status == 422
    _clean(failed, target)
    # A credencial anterior continua publicada e funcionando.
    assert app.rows("crm") == [[1, _hmac(CPF), EMAIL]]
    rotated = app.call(
        "POST",
        f"/admin/v2/datasources/{ds_id}:rotate-credential",
        {"expected_revision": 1, "credential": {"password": target.password}},
    )
    assert rotated.status == 200, rotated.text()
    _clean(rotated, target)

    disabled = app.call("POST", f"/admin/v2/datasources/{ds_id}:disable", {"expected_revision": 2})
    assert disabled.status == 200
    gateway = app.application.datasource_gateway
    assert gateway is not None
    with pytest.raises(DatasourceUnavailableError):
        gateway.open_session("crm")
    enabled = app.call("POST", f"/admin/v2/datasources/{ds_id}:enable", {"expected_revision": 3})
    assert enabled.status == 200, enabled.text()
    assert app.rows("crm") == [[1, _hmac(CPF), EMAIL]]

    policy = app.call(
        "PUT",
        f"/admin/v2/datasources/{ds_id}/policy",
        {
            "expected_revision": 4,
            "policy": {
                "masking": [{"match": "email", "transformer": "fixed", "config": {"value": "[E]"}}],
                "exceptions": [],
                "database": {"statement_timeout_ms": 5_000, "max_rows": 50},
                "sql": {"denied_functions": []},
            },
        },
    )
    assert policy.status == 200, policy.text()
    assert app.rows("crm") == [[1, CPF, "[E]"]]

    deleted = app.call(
        "DELETE", f"/admin/v2/datasources/{ds_id}", {"expected_revision": 5, "confirm_alias": "crm"}
    )
    assert deleted.status == 200
    with pytest.raises(DatasourceUnavailableError):
        gateway.open_session("crm")
