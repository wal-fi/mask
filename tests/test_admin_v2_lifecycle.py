"""Fase 9, Etapa 4: lifecycle da v2 (F9-036, D-090, D-092, D-093).

- shutdown com um candidato preso em DNS lento termina dentro do prazo de DNS,
  sem thread, processo filho ou conexao para tras;
- `build_application(datasource_catalog=..., admin_http=...)` publica a v2 pela
  porta real; sem catalogo, a v2 nao existe; `close()` solta porta e locks.
"""

from __future__ import annotations

import json
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, ClassVar, cast

import pytest
from mcp.server import MCPServer

import maskgw.bootstrap.application as application_module
import maskgw.datasource.resolver as resolver_module
from maskgw.admin.http.settings import build as build_admin_settings
from maskgw.datasource import CatalogStore
from maskgw.runtime.datasource_service import DatasourceCatalogSettings
from maskgw.secretsource import MappingSecretProvider
from tests.admin_http_support import TOKEN, free_port, request, thread_snapshot
from tests.admin_v2_support import (
    ALIAS,
    HMAC_KEY,
    build_v2,
    create_body,
    dns,
    draft_body,
)
from tests.datasource_runtime_support import KEY, FakeFactory

LEGACY_CONFIG = "database:\n  statement_timeout_ms: 2000\n  max_rows: 10\n"


class _LegacyAdapter:
    events: ClassVar[list[str]] = []

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def connect(self) -> None:
        type(self).events.append("legacy:connect")

    def close(self) -> None:
        type(self).events.append("legacy:close")


class _McpServer:
    def run(self, transport: str = "stdio", **_kwargs: Any) -> None:
        del transport


def test_shutdown_with_slow_dns_in_flight_is_bounded_and_leaves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    processes: list[subprocess.Popen[bytes]] = []
    original = subprocess.Popen

    def spy(args: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        process: subprocess.Popen[bytes] = original(args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", spy)
    monkeypatch.setattr(resolver_module, "_CHILD_CODE", "import time\ntime.sleep(60)\n")
    monkeypatch.setattr(resolver_module, "DNS_TIMEOUT_SECONDS", 1.5)

    baseline = thread_snapshot()
    harness = build_v2(tmp_path, resolver=None)
    harness.start()
    outcome: list[object] = []

    def call() -> None:
        try:
            outcome.append(harness.call("POST", "/admin/v2/datasources:test", draft_body()))
        except OSError as exc:  # pragma: no cover - so se o servidor cortasse a conexao
            outcome.append(exc)

    worker = threading.Thread(target=call)
    worker.start()
    deadline = time.monotonic() + 10
    while not processes and time.monotonic() < deadline:
        time.sleep(0.02)
    assert processes, "a resolucao nao chegou a comecar"

    started = time.monotonic()
    harness.close()
    elapsed = time.monotonic() - started
    worker.join(10)

    # O shutdown esperou a resolucao em voo, e ela tem teto: o prazo de DNS.
    assert elapsed < 10
    assert not worker.is_alive()
    assert all(process.returncode is not None for process in processes)
    reply = outcome[0]
    assert getattr(reply, "status", None) == 422
    assert harness.factory.adapters == []
    assert thread_snapshot() == baseline


def _catalog(tmp_path: Path) -> tuple[DatasourceCatalogSettings, Path, Path]:
    store_path = tmp_path / "catalog" / "datasources.store"
    store_path.parent.mkdir()
    anchor_path = tmp_path / "catalog-anchor" / "datasources.anchor"
    CatalogStore.initialize(store_path, anchor_path=anchor_path, master_key=KEY).close()
    settings = DatasourceCatalogSettings(
        store_path=store_path,
        anchor_path=anchor_path,
        resolver=dns,
        adapter_factory=FakeFactory(),
    )
    return settings, store_path, anchor_path


def _compose(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(application_module, "PostgresAdapter", _LegacyAdapter)
    monkeypatch.setattr(
        application_module, "build_mcp_server", lambda _g: cast(MCPServer, _McpServer())
    )
    config = tmp_path / "masking.yaml"
    config.write_text(LEGACY_CONFIG, encoding="utf-8")
    return config


def _port_closed(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def test_composition_root_publishes_v2_and_closes_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _compose(monkeypatch, tmp_path)
    settings, store_path, anchor_path = _catalog(tmp_path)
    secrets = MappingSecretProvider(
        {"MASKGW_DATASOURCE_MASTER_KEY": KEY, "MASKGW_HMAC_KEY": HMAC_KEY}
    )
    port = free_port()
    app = application_module.build_application(
        config_path=config,
        conninfo="host=legado-dubl",
        secrets=secrets,
        admin_http=build_admin_settings(token=TOKEN, host="127.0.0.1", port=port),
        datasource_catalog=settings,
    )
    try:
        assert app.admin_http is not None
        status = request(port, "GET", "/admin/v2/status")
        assert status.status == 200
        assert status.json()["catalog_revision"] == 1
        created = request(
            port,
            "POST",
            "/admin/v2/datasources",
            body=json.dumps(create_body()).encode(),
            content_type="application/json",
        )
        assert created.status == 200, created.text()
        assert app.datasources is not None
        assert [g.alias for g in app.datasources.registry.status().published] == [ALIAS]
        # A v1 continua no mesmo app, intacta.
        assert request(port, "GET", "/admin/v1/status").status == 200
    finally:
        app.close()
    assert _port_closed(port)
    # Os locks do catalogo sairam: outro processo (aqui, outro objeto) abre.
    CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY).close()


def test_without_the_catalog_the_process_has_no_v2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _compose(monkeypatch, tmp_path)
    port = free_port()
    app = application_module.build_application(
        config_path=config,
        conninfo="host=legado-dubl",
        secrets=MappingSecretProvider({}),
        admin_http=build_admin_settings(token=TOKEN, host="127.0.0.1", port=port),
    )
    try:
        reply = request(port, "GET", "/admin/v2/status")
        assert reply.status == 404
        assert reply.json()["error"] == "NOT_FOUND"
        assert app.datasources is None
    finally:
        app.close()
