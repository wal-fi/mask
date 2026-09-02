"""Fase 7, etapas 4 e 6: composition root, startup e shutdown.

**Sem a fronteira HTTP.** Estes testes cobrem a composicao com `admin_enabled`
sozinho — lock de arquivo adquirido no startup, secao critica construida sobre
os bytes exatos que originaram o runtime, e lock liberado por ultimo no
shutdown —, e continuam afirmando que isso NAO abre porta nem cria thread.

A fronteira HTTP da Etapa 7 e um parametro separado (`admin_http`) e tem
arquivo proprio: `test_admin_http_lifecycle.py`. A separacao entre os dois
parametros e o que permite este arquivo continuar valendo sem afrouxar nada.

Os demais testes cobrem o lifecycle ja existente: MCP stdio construido por
ultimo, falha parcial fechando o que ja subiu, data plane parado antes dos
runtimes, shutdown idempotente e fronteira de processo sem vazamento nem byte
nao protocolar em stdout.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, ClassVar, cast

import pytest
from mcp.server import MCPServer

import maskgw.bootstrap.application as application_module
import maskgw.bootstrap.main as main_module
from maskgw.bootstrap import Application
from maskgw.config import ConfigFileStore, ConfigLockUnavailableError, digest_bytes

SENSITIVE_DSN = "postgresql://user:super-secret@database.example.invalid/private"
SENSITIVE_SQL = "SELECT cpf FROM cliente WHERE cpf = '11122233344'"
SENSITIVE_VALUE = "11122233344"
SENSITIVE_CREDENTIAL = "bootstrap-credential-leak-marker"

CONFIG = """
database:
  statement_timeout_ms: 2000
  max_rows: 10
"""


class FakeAdapter:
    """Adapter que registra conexao e fechamento, sem banco."""

    instances: ClassVar[list[FakeAdapter]] = []
    events: ClassVar[list[str]] = []
    connect_error: ClassVar[BaseException | None] = None

    def __init__(self, conninfo: str, *_args: object, **_kwargs: object) -> None:
        self.conninfo = conninfo
        self.connect_calls = 0
        self.close_calls = 0
        type(self).instances.append(self)

    def connect(self) -> None:
        self.connect_calls += 1
        type(self).events.append("runtime:connected")
        error = type(self).connect_error
        if error is not None:
            raise error

    def close(self) -> None:
        self.close_calls += 1
        type(self).events.append("runtime:closed")


class FakeMcpServer:
    """Servidor sincrono controlavel para provar a ordem do lifecycle."""

    def __init__(self, *, run_error: BaseException | None = None) -> None:
        self.run_error = run_error
        self.transports: list[str] = []

    def run(self, transport: str = "stdio", **_kwargs: Any) -> None:
        self.transports.append(transport)
        FakeAdapter.events.append("mcp:started")
        if self.run_error is not None:
            raise self.run_error
        FakeAdapter.events.append("mcp:stopped")


class BlockingMcpServer(FakeMcpServer):
    """Mantem o data plane ativo ate o teste autorizar o shutdown."""

    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.stop = threading.Event()

    def run(self, transport: str = "stdio", **_kwargs: Any) -> None:
        self.transports.append(transport)
        FakeAdapter.events.append("mcp:started")
        self.started.set()
        assert self.stop.wait(timeout=5)
        FakeAdapter.events.append("mcp:stopped")


@pytest.fixture(autouse=True)
def reset_fakes() -> None:
    FakeAdapter.instances = []
    FakeAdapter.events = []
    FakeAdapter.connect_error = None


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "masking.yaml"
    path.write_text(CONFIG, encoding="utf-8")
    return path


def compose(
    monkeypatch: pytest.MonkeyPatch,
    config_file: Path,
    *,
    server: FakeMcpServer | None = None,
) -> tuple[Application, FakeMcpServer, FakeAdapter]:
    data_plane = server if server is not None else FakeMcpServer()
    monkeypatch.setattr(application_module, "PostgresAdapter", FakeAdapter)
    monkeypatch.setattr(
        application_module,
        "build_mcp_server",
        lambda _gateway: cast(MCPServer, data_plane),
    )
    app = application_module.build_application(config_path=config_file, conninfo=SENSITIVE_DSN)
    return app, data_plane, FakeAdapter.instances[0]


class TestComposition:
    def test_build_constructs_runtime_before_mcp_and_starts_nothing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        before = {(thread.ident, thread.name) for thread in threading.enumerate()}
        app, server, adapter = compose(monkeypatch, config_file)

        assert adapter.connect_calls == 1
        assert server.transports == []
        assert {(thread.ident, thread.name) for thread in threading.enumerate()} == before
        app.close()

    def test_application_contains_the_composed_data_plane(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        app, server, _adapter = compose(monkeypatch, config_file)
        assert cast(object, app.mcp_server) is server
        assert app.gateway.revision == 0
        app.close()

    def test_repr_contains_no_dsn_or_secret(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        app, _server, _adapter = compose(monkeypatch, config_file)
        rendered = repr(app)
        assert SENSITIVE_DSN not in rendered
        assert SENSITIVE_CREDENTIAL not in rendered
        assert "Application(revision=0" in rendered
        app.close()


class TestPartialStartupFailure:
    def test_mcp_construction_failure_closes_the_connected_runtime(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        monkeypatch.setattr(application_module, "PostgresAdapter", FakeAdapter)

        def fail_after_runtime(_gateway: object) -> MCPServer:
            raise RuntimeError(f"{SENSITIVE_DSN} {SENSITIVE_SQL}")

        monkeypatch.setattr(application_module, "build_mcp_server", fail_after_runtime)

        with pytest.raises(RuntimeError):
            application_module.build_application(
                config_path=config_file,
                conninfo=SENSITIVE_DSN,
            )

        adapter = FakeAdapter.instances[0]
        assert adapter.connect_calls == 1
        assert adapter.close_calls == 1

    def test_connection_failure_closes_the_partially_open_adapter(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        FakeAdapter.connect_error = RuntimeError(SENSITIVE_CREDENTIAL)
        monkeypatch.setattr(application_module, "PostgresAdapter", FakeAdapter)

        with pytest.raises(RuntimeError):
            application_module.build_application(
                config_path=config_file,
                conninfo=SENSITIVE_DSN,
            )

        assert FakeAdapter.instances[0].close_calls == 1


class TestLifecycle:
    def test_run_uses_stdio_and_closes_only_after_the_data_plane_stops(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        app, server, adapter = compose(monkeypatch, config_file)
        app.run()

        assert server.transports == ["stdio"]
        assert FakeAdapter.events == [
            "runtime:connected",
            "mcp:started",
            "mcp:stopped",
            "runtime:closed",
        ]
        assert adapter.close_calls == 1

    def test_run_failure_still_closes_the_runtime_once(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        server = FakeMcpServer(run_error=RuntimeError(SENSITIVE_VALUE))
        app, _server, adapter = compose(monkeypatch, config_file, server=server)

        with pytest.raises(RuntimeError):
            app.run()
        app.close()

        assert server.transports == ["stdio"]
        assert adapter.close_calls == 1

    def test_close_is_idempotent_and_closes_runtimes_once(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        app, _server, adapter = compose(monkeypatch, config_file)
        app.close()
        app.close()
        app.close()
        assert adapter.close_calls == 1

    def test_close_during_stdio_defers_resources_until_the_data_plane_stops(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        server = BlockingMcpServer()
        app, _server, adapter = compose(monkeypatch, config_file, server=server)
        worker = threading.Thread(target=app.run)
        worker.start()
        assert server.started.wait(timeout=5)

        app.close()
        app.close()
        assert adapter.close_calls == 0

        server.stop.set()
        worker.join(timeout=5)
        assert not worker.is_alive()
        assert adapter.close_calls == 1
        assert FakeAdapter.events[-2:] == ["mcp:stopped", "runtime:closed"]

    def test_no_thread_is_left_after_shutdown(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        before = {(thread.ident, thread.name) for thread in threading.enumerate()}
        app, _server, _adapter = compose(monkeypatch, config_file)
        app.run()
        assert {(thread.ident, thread.name) for thread in threading.enumerate()} == before


class ObservableStore(ConfigFileStore):
    """Registra o fechamento do lock na mesma linha do tempo dos runtimes."""

    def close(self) -> None:
        already = self.closed
        super().close()
        if not already:
            FakeAdapter.events.append("lock:released")


class TestAdminComposition:
    """Etapa 6: o admin plane composto em processo, sem HTTP."""

    def test_admin_disabled_is_the_process_of_today(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        app, _server, _adapter = compose(monkeypatch, config_file)

        assert app.admin is None
        assert app.config_store is None
        # Sem admin nao ha escrita, entao nao ha lock a adquirir.
        assert not (config_file.parent / "masking.yaml.lock").exists()
        app.close()

    def test_admin_enabled_holds_the_lock_and_exposes_the_critical_section(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        monkeypatch.setattr(application_module, "PostgresAdapter", FakeAdapter)
        monkeypatch.setattr(
            application_module,
            "build_mcp_server",
            lambda _gateway: cast(MCPServer, FakeMcpServer()),
        )
        app = application_module.build_application(
            config_path=config_file,
            conninfo=SENSITIVE_DSN,
            admin_enabled=True,
        )
        try:
            admin = app.admin
            assert admin is not None
            assert app.config_store is not None
            assert admin.revision == 0
            assert not admin.adopted
            # O digest de referencia sao os BYTES que originaram o runtime.
            assert admin.reference_digest == digest_bytes(config_file.read_bytes())
            # Um segundo processo administrativo sobre o mesmo arquivo nao
            # entra: o lock exclusivo esta preso a este.
            with pytest.raises(ConfigLockUnavailableError):
                ConfigFileStore.open(config_file)
        finally:
            app.close()

        # Liberado no shutdown, e so entao outro pode abrir.
        with ConfigFileStore.open(config_file) as store:
            assert not store.closed

    def test_shutdown_releases_the_lock_after_the_runtimes(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        monkeypatch.setattr(application_module, "PostgresAdapter", FakeAdapter)
        monkeypatch.setattr(application_module, "ConfigFileStore", ObservableStore)
        monkeypatch.setattr(
            application_module,
            "build_mcp_server",
            lambda _gateway: cast(MCPServer, FakeMcpServer()),
        )
        app = application_module.build_application(
            config_path=config_file,
            conninfo=SENSITIVE_DSN,
            admin_enabled=True,
        )
        app.run()
        app.close()

        admin = app.admin
        assert admin is not None
        assert admin.closed
        assert FakeAdapter.events == [
            "runtime:connected",
            "mcp:started",
            "mcp:stopped",
            "runtime:closed",
            "lock:released",
        ]
        assert FakeAdapter.instances[0].close_calls == 1

    def test_partial_startup_with_admin_releases_the_lock(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        monkeypatch.setattr(application_module, "PostgresAdapter", FakeAdapter)

        def fail_after_runtime(_gateway: object) -> MCPServer:
            raise RuntimeError(f"{SENSITIVE_DSN} {SENSITIVE_SQL}")

        monkeypatch.setattr(application_module, "build_mcp_server", fail_after_runtime)

        with pytest.raises(RuntimeError):
            application_module.build_application(
                config_path=config_file,
                conninfo=SENSITIVE_DSN,
                admin_enabled=True,
            )

        assert FakeAdapter.instances[0].close_calls == 1
        # Nem lock nem conexao ficaram de pe.
        with ConfigFileStore.open(config_file) as store:
            assert not store.closed

    def test_admin_composition_creates_no_thread(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        """A secao critica sozinha nao abre porta nem cria thread.

        Continua valendo na Etapa 7, e por isso `admin_enabled` e `admin_http`
        sao parametros distintos: compor a secao critica administrativa nao
        implica expor uma fronteira HTTP. A fronteira, quando pedida, e coberta
        em `test_admin_http_lifecycle.py`.
        """
        before = {(thread.ident, thread.name) for thread in threading.enumerate()}
        monkeypatch.setattr(application_module, "PostgresAdapter", FakeAdapter)
        monkeypatch.setattr(
            application_module,
            "build_mcp_server",
            lambda _gateway: cast(MCPServer, FakeMcpServer()),
        )
        app = application_module.build_application(
            config_path=config_file,
            conninfo=SENSITIVE_DSN,
            admin_enabled=True,
        )
        try:
            assert {(thread.ident, thread.name) for thread in threading.enumerate()} == before
        finally:
            app.close()
        assert {(thread.ident, thread.name) for thread in threading.enumerate()} == before

    def test_repr_reports_admin_without_leaking(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        monkeypatch.setattr(application_module, "PostgresAdapter", FakeAdapter)
        monkeypatch.setattr(
            application_module,
            "build_mcp_server",
            lambda _gateway: cast(MCPServer, FakeMcpServer()),
        )
        app = application_module.build_application(
            config_path=config_file,
            conninfo=SENSITIVE_DSN,
            admin_enabled=True,
        )
        try:
            rendered = repr(app)
            assert "admin=True" in rendered
            assert SENSITIVE_DSN not in rendered
            assert str(config_file) not in rendered
        finally:
            app.close()


class StubApplication:
    def __init__(self, *, run_error: BaseException | None = None) -> None:
        self.run_error = run_error
        self.revision = 7
        self.run_calls = 0
        self.close_calls = 0
        # Etapa 7: a fronteira de processo consulta a fronteira HTTP para
        # anunciar host e porta em stderr. `None` e o caso sem Admin API, que e
        # o que estes testes exercitam.
        self.admin_http: object | None = None

    def run(self) -> None:
        self.run_calls += 1
        if self.run_error is not None:
            raise self.run_error

    def close(self) -> None:
        self.close_calls += 1


class TestProcessBoundary:
    @pytest.mark.parametrize(
        "payload",
        [SENSITIVE_DSN, SENSITIVE_CREDENTIAL, SENSITIVE_SQL, SENSITIVE_VALUE, "Traceback"],
    )
    def test_startup_error_is_fixed_and_stdout_stays_empty(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        payload: str,
    ) -> None:
        def fail(**_kwargs: object) -> Application:
            raise RuntimeError(payload)

        monkeypatch.setattr(main_module, "build_application", fail)
        assert main_module.main() == 1

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == main_module.STARTUP_FAILURE
        assert payload not in captured.err

    def test_runtime_error_is_fixed_and_application_is_closed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        original = f"{SENSITIVE_DSN} {SENSITIVE_CREDENTIAL} {SENSITIVE_SQL} Traceback"
        app = StubApplication(run_error=RuntimeError(original))
        monkeypatch.setattr(main_module, "build_application", lambda **_kwargs: app)

        assert main_module.main() == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == (
            f"{main_module.REVISION_LOADED_PREFIX}{app.revision}\n{main_module.RUNTIME_FAILURE}"
        )
        assert original not in captured.err
        assert app.close_calls == 1

    def test_success_writes_nothing_and_closes(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        app = StubApplication()
        monkeypatch.setattr(main_module, "build_application", lambda **_kwargs: app)

        assert main_module.main() == 0
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == f"{main_module.REVISION_LOADED_PREFIX}{app.revision}\n"
        assert app.run_calls == 1
        assert app.close_calls == 1

    def test_python_m_maskgw_mcp_delegates_without_non_protocol_stdout(
        self,
        tmp_path: Path,
    ) -> None:
        config = tmp_path / "masking.yaml"
        config.write_text("{}\n", encoding="utf-8")
        env = os.environ.copy()
        env.pop("MASKGW_DATABASE_DSN", None)
        env["MASKGW_CONFIG"] = str(config)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

        result = subprocess.run(
            [sys.executable, "-m", "maskgw.mcp"],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr == main_module.STARTUP_FAILURE
        assert "Traceback" not in result.stderr

    def test_error_writer_uses_only_the_supplied_stderr_stream(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sink = io.StringIO()

        def fail(**_kwargs: object) -> Application:
            raise RuntimeError(SENSITIVE_CREDENTIAL)

        monkeypatch.setattr(main_module, "build_application", fail)
        assert main_module.main(stderr=sink) == 1
        assert sink.getvalue() == main_module.STARTUP_FAILURE
