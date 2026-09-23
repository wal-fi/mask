"""Fase 9, Etapa 3: composition root, startup fail-closed e legado (F9-023, F9-036).

A capacidade nova so e ligada pelo parametro interno `datasource_catalog`
(D-087). Estes testes provam tres coisas:

1. **desligada, e o legado byte a byte**: nenhum modulo de catalogo carregado,
   nenhum arquivo tocado, o mesmo `repr`;
2. **ligada e invalida, nada e publicado**: nem runtime legado, nem Admin HTTP,
   nem MCP — o datasource habilitado e verificado ANTES de todos (§11);
3. **ligada e valida, shutdown ordenado**: admissao parada primeiro, consulta em
   voo cancelada, sessoes e geracoes fechadas, locks do catalogo soltos, sem
   thread ou conexao abandonada.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path
from typing import Any, ClassVar, cast

import psycopg
import pytest
from mcp.server import MCPServer

import maskgw.bootstrap.application as application_module
from maskgw.admin.http.settings import build as build_admin_settings
from maskgw.datasource import CatalogStore
from maskgw.errors import DatabaseError
from maskgw.runtime.candidate import DatasourceCandidateError
from maskgw.runtime.datasource_service import DatasourceCatalogSettings
from maskgw.runtime.datasources import DatasourceUnavailableError
from tests.admin_http_support import TOKEN, free_port, thread_snapshot
from tests.datasource_runtime_support import (
    KEY,
    SECRET,
    FakeFactory,
    draft,
    resolver,
    secrets_provider,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
LEGACY_CONFIG = """
database:
  statement_timeout_ms: 2000
  max_rows: 10
"""


class _LegacyAdapter:
    """Adapter legado dublê: registra a ordem sem banco."""

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


@pytest.fixture(autouse=True)
def _reset() -> None:
    _LegacyAdapter.events = []


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "masking.yaml"
    path.write_text(LEGACY_CONFIG, encoding="utf-8")
    return path


def _catalog(tmp_path: Path, *drafts: object) -> DatasourceCatalogSettings:
    store_path = tmp_path / "catalog" / "datasources.store"
    store_path.parent.mkdir(mode=0o755)
    anchor_path = tmp_path / "catalog-anchor" / "datasources.anchor"
    with CatalogStore.initialize(store_path, anchor_path=anchor_path, master_key=KEY) as store:
        for item in drafts:
            store.create(item, SECRET, resolver=resolver)  # type: ignore[arg-type]
    return DatasourceCatalogSettings(
        store_path=store_path, anchor_path=anchor_path, resolver=resolver
    )


def _compose(monkeypatch: pytest.MonkeyPatch, events: list[str]) -> None:
    monkeypatch.setattr(application_module, "PostgresAdapter", _LegacyAdapter)
    original_admin = application_module._build_admin_http

    def recording_admin(*args: Any, **kwargs: Any) -> Any:
        events.append("admin:build")
        return original_admin(*args, **kwargs)

    def recording_mcp(_gateway: object) -> MCPServer:
        events.append("mcp:build")
        return cast(MCPServer, _McpServer())

    monkeypatch.setattr(application_module, "_build_admin_http", recording_admin)
    monkeypatch.setattr(application_module, "build_mcp_server", recording_mcp)


# -- 1. desligada: legado intacto ---------------------------------------------


def test_disabled_capability_loads_no_catalog_module_and_keeps_repr(tmp_path: Path) -> None:
    config = tmp_path / "masking.yaml"
    config.write_text(LEGACY_CONFIG, encoding="utf-8")
    script = textwrap.dedent(
        f"""
        import sys
        import maskgw.bootstrap.application as app_module

        class Adapter:
            def __init__(self, *a, **k): pass
            def connect(self): pass
            def close(self): pass

        app_module.PostgresAdapter = Adapter
        app = app_module.build_application(config_path={str(config)!r}, conninfo="host=x")
        loaded = sorted(
            name for name in sys.modules
            if name.startswith(("maskgw.datasource", "maskgw.runtime.datasource",
                                 "maskgw.runtime.candidate", "maskgw.gateway.datasources"))
        )
        print(repr(app))
        print(loaded)
        app.close()
        """
    )
    before = sorted(path.name for path in tmp_path.iterdir())
    result = subprocess.run(  # noqa: S603 - interpretador e script do proprio teste
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONPATH": str(SRC)},
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    lines = result.stdout.splitlines()
    assert lines[0] == "Application(revision=0, state='ready', admin=False, admin_http=False)"
    assert lines[1] == "[]"
    assert sorted(path.name for path in tmp_path.iterdir()) == before


def test_disabled_capability_exposes_no_datasource_objects(
    monkeypatch: pytest.MonkeyPatch, config_file: Path
) -> None:
    events: list[str] = []
    _compose(monkeypatch, events)
    app = application_module.build_application(config_path=config_file, conninfo="host=x")
    try:
        assert app.datasources is None
        assert app.datasource_gateway is None
        assert "datasources" not in repr(app)
    finally:
        app.close()
    assert events == ["mcp:build"]


# -- 2. ligada e invalida: nada publicado ----------------------------------------


@pytest.mark.parametrize("failure", ["connect", "dns", "missing-key"])
def test_invalid_enabled_datasource_publishes_no_boundary(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path, failure: str
) -> None:
    events: list[str] = []
    _compose(monkeypatch, events)
    settings = _catalog(tmp_path, draft("crm"), draft("fin"))
    factory = FakeFactory()
    provider = secrets_provider()
    if failure == "connect":
        factory.connect_failure = DatabaseError(SECRET)
    elif failure == "dns":
        settings = DatasourceCatalogSettings(
            store_path=settings.store_path,
            anchor_path=settings.anchor_path,
            resolver=lambda _h, _p: ("10.0.0.99",),
        )
    else:
        from maskgw.masking.transformers.hashes import HMAC_KEY_ENV  # noqa: PLC0415
        from maskgw.secretsource import MappingSecretProvider  # noqa: PLC0415

        provider = MappingSecretProvider({HMAC_KEY_ENV: "x" * 40})
    settings = DatasourceCatalogSettings(
        store_path=settings.store_path,
        anchor_path=settings.anchor_path,
        resolver=settings.resolver,
        adapter_factory=factory,
    )
    port = free_port()
    threads = thread_snapshot()

    with pytest.raises(Exception) as caught:
        application_module.build_application(
            config_path=config_file,
            conninfo="host=x",
            secrets=provider,
            admin_http=build_admin_settings(token=TOKEN, host="127.0.0.1", port=port),
            datasource_catalog=settings,
        )

    assert SECRET not in f"{caught.value!s}{caught.value!r}"
    # Nada depois do catalogo aconteceu: nem legado, nem Admin HTTP, nem MCP.
    assert events == []
    assert _LegacyAdapter.events == []
    assert factory.open_adapters() == []
    assert thread_snapshot() == threads
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", port))  # a porta administrativa nunca foi tomada
    CatalogStore.open(settings.store_path, anchor_path=settings.anchor_path, master_key=KEY).close()


def test_later_startup_failure_also_closes_the_datasource_runtime(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path
) -> None:
    events: list[str] = []
    _compose(monkeypatch, events)

    def failing_mcp(_gateway: object) -> MCPServer:
        raise RuntimeError("falha sintetica do MCP")

    monkeypatch.setattr(application_module, "build_mcp_server", failing_mcp)
    settings = _catalog(tmp_path, draft("crm"))
    factory = FakeFactory()
    settings = DatasourceCatalogSettings(
        store_path=settings.store_path,
        anchor_path=settings.anchor_path,
        resolver=resolver,
        adapter_factory=factory,
    )
    with pytest.raises(RuntimeError):
        application_module.build_application(
            config_path=config_file,
            conninfo="host=x",
            secrets=secrets_provider(),
            datasource_catalog=settings,
        )
    assert _LegacyAdapter.events == ["legacy:connect", "legacy:close"]
    assert factory.open_adapters() == []
    CatalogStore.open(settings.store_path, anchor_path=settings.anchor_path, master_key=KEY).close()


# -- 3. ligada e valida: ordem e shutdown ---------------------------------------


def test_valid_catalog_is_built_before_legacy_admin_and_mcp(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path
) -> None:
    events: list[str] = []
    _compose(monkeypatch, events)
    factory = FakeFactory()
    original_call = FakeFactory.__call__

    def recording_call(self: FakeFactory, conninfo: str, **kwargs: Any) -> Any:
        events.append("datasource:candidate")
        return original_call(self, conninfo, **kwargs)

    monkeypatch.setattr(FakeFactory, "__call__", recording_call)
    base = _catalog(tmp_path, draft("crm"), draft("fin"), draft("hml", enabled=False))
    settings = DatasourceCatalogSettings(
        store_path=base.store_path,
        anchor_path=base.anchor_path,
        resolver=resolver,
        adapter_factory=factory,
    )
    port = free_port()
    app = application_module.build_application(
        config_path=config_file,
        conninfo="host=x",
        secrets=secrets_provider(),
        admin_http=build_admin_settings(token=TOKEN, host="127.0.0.1", port=port),
        datasource_catalog=settings,
    )
    try:
        # Legado conectado so depois dos dois candidatos; Admin e MCP depois.
        assert events == [
            "datasource:candidate",
            "datasource:candidate",
            "admin:build",
            "mcp:build",
        ]
        assert _LegacyAdapter.events == ["legacy:connect"]
        assert app.datasources is not None
        assert app.datasource_gateway is not None
        assert repr(app).endswith("datasources=True)")
        assert {item.alias for item in app.datasources.registry.status().published} == {
            "crm",
            "fin",
        }
        session = app.datasource_gateway.open_session("crm")
        assert session.query("SELECT 1").rows == []
    finally:
        app.close()
    assert session.closed
    assert factory.open_adapters() == []
    with pytest.raises(DatasourceUnavailableError):
        app.datasources.registry.open_session("crm")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", port))
    CatalogStore.open(base.store_path, anchor_path=base.anchor_path, master_key=KEY).close()
    app.close()  # idempotente


def test_application_close_stops_datasource_admission_before_waiting_http(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path
) -> None:
    events: list[str] = []
    _compose(monkeypatch, events)
    base = _catalog(tmp_path, draft("crm"))
    settings = DatasourceCatalogSettings(
        store_path=base.store_path,
        anchor_path=base.anchor_path,
        resolver=resolver,
        adapter_factory=FakeFactory(),
    )
    app = application_module.build_application(
        config_path=config_file,
        conninfo="host=x",
        secrets=secrets_provider(),
        admin_http=build_admin_settings(token=TOKEN, host="127.0.0.1", port=free_port()),
        datasource_catalog=settings,
    )
    assert app.admin_http is not None
    assert app.datasource_gateway is not None
    gateway = app.datasource_gateway
    server_type = type(app.admin_http)
    original_stop = server_type.stop
    during_stop: list[BaseException | None] = []

    def observing_stop(self: Any) -> None:
        # Enquanto o shutdown espera a thread HTTP, nenhuma sessao nova entra.
        try:
            gateway.open_session("crm").close()
            during_stop.append(None)
        except BaseException as exc:
            during_stop.append(exc)
        original_stop(self)

    monkeypatch.setattr(server_type, "stop", observing_stop)
    try:
        app.close()
    finally:
        original_stop(app.admin_http)
    assert isinstance(during_stop[0], DatasourceUnavailableError)


def test_application_close_cancels_in_flight_datasource_query(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path
) -> None:
    events: list[str] = []
    _compose(monkeypatch, events)
    factory = FakeFactory()
    base = _catalog(tmp_path, draft("crm"))
    settings = DatasourceCatalogSettings(
        store_path=base.store_path,
        anchor_path=base.anchor_path,
        resolver=resolver,
        adapter_factory=factory,
    )
    app = application_module.build_application(
        config_path=config_file,
        conninfo="host=x",
        secrets=secrets_provider(),
        datasource_catalog=settings,
    )
    assert app.datasource_gateway is not None
    session = app.datasource_gateway.open_session("crm")
    factory.block_execution = True
    outcome: list[BaseException | None] = []

    def run() -> None:
        try:
            session.query("SELECT 1")
            outcome.append(None)
        except BaseException as exc:
            outcome.append(exc)

    threads = thread_snapshot()
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    assert factory.adapters[-1].started.wait(timeout=5)
    app.close()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert outcome and outcome[0] is not None
    assert "SELECT" not in str(outcome[0])
    assert session.closed
    assert factory.open_adapters() == []
    assert thread_snapshot() == threads
    assert _LegacyAdapter.events == ["legacy:connect", "legacy:close"]


def test_legacy_close_failure_still_closes_datasources_and_catalog(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path
) -> None:
    events: list[str] = []
    _compose(monkeypatch, events)
    factory = FakeFactory()
    base = _catalog(tmp_path, draft("crm"))
    settings = DatasourceCatalogSettings(
        store_path=base.store_path,
        anchor_path=base.anchor_path,
        resolver=resolver,
        adapter_factory=factory,
    )
    app = application_module.build_application(
        config_path=config_file,
        conninfo="host=x",
        secrets=secrets_provider(),
        admin_enabled=True,
        datasource_catalog=settings,
    )
    assert app.datasource_gateway is not None
    session = app.datasource_gateway.open_session("crm")

    def failing_close_all(self: object) -> None:
        del self
        raise RuntimeError("falha sintetica do runtime legado")

    monkeypatch.setattr(type(app.registry), "close_all", failing_close_all)
    with pytest.raises(RuntimeError):
        app.close()
    # Mesmo com o legado falhando, sessoes, geracoes e os dois locks sairam.
    assert session.closed
    assert factory.open_adapters() == []
    CatalogStore.open(base.store_path, anchor_path=base.anchor_path, master_key=KEY).close()
    assert app.config_store is not None
    assert app.config_store.closed


def test_candidate_error_surfaces_from_build_application_unchanged(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path
) -> None:
    events: list[str] = []
    _compose(monkeypatch, events)
    base = _catalog(tmp_path, draft("crm"))
    settings = DatasourceCatalogSettings(
        store_path=base.store_path,
        anchor_path=base.anchor_path,
        resolver=resolver,
        adapter_factory=FakeFactory(connect_failure=DatabaseError("x")),
    )
    with pytest.raises(DatasourceCandidateError) as caught:
        application_module.build_application(
            config_path=config_file,
            conninfo="host=x",
            secrets=secrets_provider(),
            datasource_catalog=settings,
        )
    assert caught.value.__context__ is None


# -- integracao real: subprocesso fail-closed (F9-023) ----------------------------


_DRIVER = """
import os, sys
from maskgw.admin.http.settings import build
from maskgw.bootstrap.application import build_application
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.runtime.datasource_service import DatasourceCatalogSettings
from maskgw.secretsource import MappingSecretProvider

provider = MappingSecretProvider({
    "MASKGW_DATASOURCE_MASTER_KEY": os.environ["DRIVER_KEY"],
    HMAC_KEY_ENV: "chave-de-teste-para-hmac-com-tamanho-suficiente",
})
try:
    app = build_application(
        config_path=os.environ["DRIVER_CONFIG"],
        conninfo=os.environ["MASKGW_TEST_DSN"],
        secrets=provider,
        admin_http=build(token=os.environ["DRIVER_TOKEN"], host="127.0.0.1",
                         port=int(os.environ["DRIVER_PORT"])),
        datasource_catalog=DatasourceCatalogSettings(
            store_path=os.environ["DRIVER_STORE"], anchor_path=os.environ["DRIVER_ANCHOR"]),
    )
except BaseException:
    sys.stderr.write("maskgw: falha na inicializacao\\n")
    sys.exit(1)
sys.stderr.write("maskgw: pronto\\n")
app.close()
"""


def _client_backends(dsn: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as control:
        row = control.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
            "AND backend_type = 'client backend' AND pid <> pg_backend_pid()"
        ).fetchone()
    assert row is not None
    return int(row[0])


@pytest.mark.integration
@pytest.mark.parametrize("valid", [False, True])
def test_subprocess_startup_is_fail_closed_with_real_postgresql(
    dsn: str, tmp_path: Path, valid: bool
) -> None:
    from tests.test_datasource_runtime_integration import (  # noqa: PLC0415
        CRM_POLICY,
        _Target,
    )

    target = _Target(dsn)
    store_path = tmp_path / "catalog" / "datasources.store"
    store_path.parent.mkdir(mode=0o755)
    anchor_path = tmp_path / "catalog-anchor" / "datasources.anchor"
    with CatalogStore.initialize(store_path, anchor_path=anchor_path, master_key=KEY) as store:
        store.create(target.draft("crm", CRM_POLICY), target.password)
        store.create(
            target.draft("fin", CRM_POLICY),
            target.password if valid else "senha-errada-canario",
        )
    config = tmp_path / "masking.yaml"
    config.write_text(LEGACY_CONFIG, encoding="utf-8")
    port = free_port()
    baseline = _client_backends(dsn)
    result = subprocess.run(  # noqa: S603 - interpretador e script do proprio teste
        [sys.executable, "-c", _DRIVER],
        capture_output=True,
        timeout=120,
        env={
            **os.environ,
            "PYTHONPATH": str(SRC),
            "DRIVER_KEY": KEY,
            "DRIVER_CONFIG": str(config),
            "DRIVER_TOKEN": TOKEN,
            "DRIVER_PORT": str(port),
            "DRIVER_STORE": str(store_path),
            "DRIVER_ANCHOR": str(anchor_path),
        },
        check=False,
    )
    # stdout e exclusivo do MCP: nada foi publicado em nenhum dos casos.
    assert result.stdout == b""
    # TextIOWrapper traduz \n para CRLF no stderr do subprocesso Windows.
    # Normalizar somente essa representacao preserva a comparacao dos bytes.
    stderr = result.stderr.replace(b"\r\n", b"\n")
    if valid:
        assert result.returncode == 0, result.stderr[-2000:]
        # Depois do marcador, so as linhas fixas de encerramento do uvicorn da
        # Admin HTTP, preexistentes e sem dado (medido tambem sem a Etapa 3).
        assert stderr.startswith(b"maskgw: pronto\n")
        assert set(stderr.splitlines()[1:]) <= {
            b"Shutting down",
            *(
                line
                for line in stderr.splitlines()
                if line.startswith(b"Finished server process [")
            ),
        }
    else:
        assert result.returncode == 1
        assert stderr == b"maskgw: falha na inicializacao\n"
        assert b"senha-errada" not in stderr
    deadline = time.monotonic() + 5
    while _client_backends(dsn) != baseline and time.monotonic() < deadline:
        time.sleep(0.05)
    assert _client_backends(dsn) == baseline
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", port))
    CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY).close()
