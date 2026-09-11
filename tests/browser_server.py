"""Harness privado: composition root e PostgreSQL reais, sem rota auxiliar."""

import logging
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

import maskgw.bootstrap.application as composition
from maskgw.admin.http import build_admin_app
from maskgw.admin.http.settings import build
from maskgw.bootstrap.application import build_application
from tests.admin_http_support import free_port


def redirect_fixture(target: str) -> None:
    """Fault injection privada no harness; nenhuma rota/opcao no produto."""
    original = build_admin_app

    def build_app(*args: Any, **kwargs: Any) -> ASGIApp:
        app = original(*args, **kwargs)

        async def intercept(scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] == "http" and scope.get("raw_path") == b"/admin/ui/presentation.json":
                await RedirectResponse(target, status_code=302)(scope, receive, send)
            else:
                await app(scope, receive, send)

        return intercept

    patch.object(composition, "build_admin_app", build_app).start()


class MemoryProbe(logging.Handler):
    """Inspeciona em memoria; conserva somente contagens e flags, nunca registros."""

    def __init__(self, token: str, dsn: str, *, allow_peer_reset: bool = False) -> None:
        super().__init__()
        self.markers = (token, dsn)
        self.allow_peer_reset = allow_peer_reset
        self.peer_resets = 0
        self.leaked = False
        self.failed = False
        self.admin_events = 0

    def emit(self, record: logging.LogRecord) -> None:
        rendered = repr(record.__dict__)
        self.leaked |= any(value in rendered for value in self.markers)
        exception = record.exc_info[1] if record.exc_info else None
        peer_reset = (
            self.allow_peer_reset
            and record.name == "asyncio"
            and record.levelno == logging.ERROR
            and isinstance(exception, ConnectionResetError)
            and getattr(exception, "winerror", None) == 10054
        )
        if peer_reset:
            self.peer_resets += 1
        else:
            self.failed |= record.levelno >= logging.WARNING
        if record.name == "maskgw.audit":
            self.admin_events += 1
            fields = getattr(record, "maskgw", {})
            self.failed |= record.getMessage() != "admin" or fields.get("operation") != "validate"


def network_probe(probe: MemoryProbe) -> None:
    """Observa o que realmente chegou ao ASGI; nao registra headers/valores."""
    original = composition.__dict__["build_admin_app"]

    def build_app(*args: Any, **kwargs: Any) -> ASGIApp:
        app = original(*args, **kwargs)

        async def inspect(scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] == "http":
                headers = dict(scope["headers"])
                origin = headers.get(b"origin")
                expected = b"http://" + headers.get(b"host", b"")
                if origin is not None and origin != expected and b"authorization" in headers:
                    probe.failed = True
            await app(scope, receive, send)

        return inspect

    patch.object(composition, "build_admin_app", build_app).start()


def main() -> int:
    app = None
    root = logging.getLogger()
    old_handlers, old_level = root.handlers[:], root.level
    try:
        dsn = os.environ["MASKGW_TEST_DSN"]
        token = os.environ["MASKGW_BROWSER_TOKEN"]
        probe = MemoryProbe(
            token,
            dsn,
            allow_peer_reset=os.name == "nt" and os.environ.get("MASKGW_BROWSER_CSRF") == "1",
        )
        root.handlers = [probe]
        root.setLevel(logging.INFO)
        if target := os.environ.get("MASKGW_BROWSER_REDIRECT"):
            redirect_fixture(target)
        network_probe(probe)
        with TemporaryDirectory(prefix="maskgw-browser-") as directory:
            config = Path(directory) / "masking.yaml"
            text = "masking: []\nexceptions: []\n"
            config.write_text(text, encoding="utf-8")
            try:
                app = build_application(
                    config_path=config,
                    conninfo=dsn,
                    admin_http=build(token=token, host="127.0.0.1", port=free_port()),
                    admin_ui_enabled=True,
                )
                assert app.admin_http is not None and app.admin is not None
                before = app.admin.snapshot()
                print(app.admin_http.port, flush=True)
                sys.stdin.readline()
                assert config.read_text(encoding="utf-8") == text
                assert app.admin.snapshot() == before and app.admin.operations_total == 0
            finally:
                if app is not None:
                    app.close()
            assert not probe.leaked and not probe.failed and probe.admin_events <= 1
            assert probe.peer_resets <= 2

    except BaseException:
        sys.stderr.write("Browser harness failed.\n")
        return 1
    finally:
        root.handlers = old_handlers
        root.setLevel(old_level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
