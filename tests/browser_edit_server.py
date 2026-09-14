"""Harness de escrita real; controles por stdin, nunca rotas de produto."""

from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

import yaml
from starlette.types import ASGIApp, Message, Receive, Scope, Send

import maskgw.bootstrap.application as composition
from maskgw.admin.http import build_admin_app
from maskgw.admin.http.settings import build
from maskgw.admin.service import AdapterFactory, AdminConfigService
from maskgw.audit import (
    AdminAudit,
    AdminErrorCategoryName,
    AdminOperationName,
    AdminOutcome,
    AdminTargetKind,
)
from maskgw.bootstrap.application import Application, build_application
from maskgw.config import GatewayConfig
from maskgw.config.filesystem import (
    AtomicWriteResult,
    ConfigDurabilityError,
    ConfigFileStore,
    ConfigWriteError,
)
from maskgw.db.postgres import PostgresAdapter
from maskgw.masking.engine import MaskingEngine
from maskgw.runtime import Runtime
from tests.admin_http_support import free_port
from tests.test_admin_http_writes_e2e import _mcp_call


class EditProbe(logging.Handler):
    """Somente memoria, com auditoria validada pelo contrato original."""

    def __init__(self, token: str, dsn: str) -> None:
        super().__init__()
        self.markers = (token, dsn)
        self.failed = False
        self.events: list[dict[str, Any]] = []
        self.failure_line = 0

    def emit(self, record: logging.LogRecord) -> None:
        self.failed |= any(marker in repr(record.__dict__) for marker in self.markers)
        self.failed |= record.levelno >= logging.WARNING
        if record.exc_info:
            trace = record.exc_info[2]
            while trace is not None:
                if trace.tb_frame.f_code.co_filename == __file__:
                    self.failure_line = trace.tb_lineno
                trace = trace.tb_next
        if record.name == "maskgw.audit" and record.getMessage() == "admin":
            fields = getattr(record, "maskgw", {})
            try:
                typed = dict(fields)
                for name, enum in (
                    ("operation", AdminOperationName),
                    ("outcome", AdminOutcome),
                    ("target_kind", AdminTargetKind),
                    ("error_category", AdminErrorCategoryName),
                ):
                    if typed.get(name) is not None:
                        typed[name] = enum(typed[name])
                AdminAudit(**typed)
                self.events.append(dict(fields))
            except (TypeError, ValueError):
                self.failed = True


@dataclass
class Exchange:
    route: str
    method: str
    before: bytes
    events: int
    body: bytearray
    output: bytearray
    status: int


class Faults:
    """Injecao privada e explicita, conservando os efeitos reais de commit."""

    def __init__(self) -> None:
        self.mode = ""
        self.held: Runtime | None = None
        self.patches = ExitStack()
        original = ConfigFileStore.write_atomic
        make = composition.make_adapter_factory

        def persist(
            store: ConfigFileStore, data: bytes, *, expected_digest: str
        ) -> AtomicWriteResult:
            mode, self.mode = self.mode, ""
            if mode == "pre":
                raise ConfigWriteError()
            result = original(store, data, expected_digest=expected_digest)
            if mode == "durability":
                raise ConfigDurabilityError(result.digest)
            return result

        def make_factory(dsn: str) -> AdapterFactory:
            original_factory = make(dsn)

            def factory(*, config: GatewayConfig, engine: MaskingEngine) -> PostgresAdapter:
                if self.mode == "reload":
                    self.mode = ""
                    raise RuntimeError("injected")
                return original_factory(config=config, engine=engine)

            return factory

        self.patches.enter_context(patch.object(ConfigFileStore, "write_atomic", persist))
        self.patches.enter_context(patch.object(composition, "make_adapter_factory", make_factory))

    def command(self, command: str, app: Application) -> bool:
        if command.startswith("fault:"):
            self.mode = command.split(":")[1]
            assert self.mode in {"pre", "reload", "durability"}
        elif command == "hold":
            assert self.held is None
            self.held = app.registry.acquire()
        elif command == "release":
            assert self.held is not None
            app.registry.release(self.held)
            self.held = None
        else:
            return False
        return True

    def close(self, app: Application) -> None:
        if self.held is not None:
            app.registry.release(self.held)
            self.held = None
        self.patches.close()


def check_exchange(probe: EditProbe, path: Path, exchange: Exchange) -> None:
    route, method = exchange.route, exchange.method
    before, events = exchange.before, exchange.events
    body, output, status = exchange.body, exchange.output, exchange.status
    request = json.loads(body)
    response = json.loads(output)
    assert all(marker not in body.decode() for marker in probe.markers)
    assert ".bak." not in output.decode() and str(path.parent) not in output.decode()
    assert len(probe.events) == events + 1
    event = probe.events[-1]
    if route.endswith(":adopt"):
        operation, target = "adopt", "config"
    elif route.endswith(":validate"):
        operation, target = "validate", "config"
    else:
        target = "rule" if "/rules" in route else "exception"
        operation = target + "_" + {"POST": "create", "PUT": "update", "DELETE": "delete"}[method]
    assert event["operation"] == operation and event["target_kind"] == target
    if route.endswith(":validate"):
        assert "expected_revision" not in request and "revision" not in request
        assert "config" not in request
        assert all("id" not in item for key in ("masking", "exceptions") for item in request[key])
        assert path.read_bytes() == before
        assert len(probe.events) == events + 1
        assert probe.events[-1]["operation"] == "validate"
    else:
        assert type(request["expected_revision"]) is int
        assert "allowed_pg_functions" not in request and "position" not in request
        for member in ("rule", "exception"):
            if member in request:
                assert not {"id", "position", "revision"}.intersection(request[member])
        if status == 200 or response.get("applied"):
            assert response["applied"] is True
            after = response["revision"] if status == 200 else response["current_revision"]
            assert after == request["expected_revision"] + 1
            assert yaml.safe_load(path.read_bytes())["revision"] == after
            assert len(probe.events) == events + 1
            event = probe.events[-1]
            assert event["outcome"] == ("success" if status == 200 else "error")
            assert event["revision_before"] == request["expected_revision"]
            assert event["revision_after"] == after
            if method in {"PUT", "DELETE"}:
                assert event["target_id"] == route.rsplit("/", 1)[1]
        elif not response.get("applied"):
            assert path.read_bytes() == before


def instrument(probe: EditProbe, path: Path) -> None:
    def build_app(*args: Any, **kwargs: Any) -> ASGIApp:
        app = build_admin_app(*args, **kwargs)
        service = args[0]
        assert isinstance(service, AdminConfigService)

        async def inspect(scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] != "http":
                await app(scope, receive, send)
                return
            route = scope["path"]
            method = scope["method"]
            if method in {"GET", "HEAD"}:
                await app(scope, receive, send)
                return
            permitted = route in {"/admin/v1/config:adopt", "/admin/v1/config:validate"}
            permitted |= route in {"/admin/v1/rules", "/admin/v1/exceptions"}
            permitted |= route.startswith(("/admin/v1/rules/rul_", "/admin/v1/exceptions/exc_"))
            assert permitted
            headers = dict(scope["headers"])
            assert headers.get(b"origin") == b"http://" + headers[b"host"]
            assert headers.get(b"content-type") == b"application/json"
            before = path.read_bytes()
            state = (service.snapshot(), service.reference_digest, service.operations_total)
            events = len(probe.events)
            body = bytearray()
            output = bytearray()
            status = 0

            async def incoming() -> Message:
                message = await receive()
                if message["type"] == "http.request":
                    body.extend(message.get("body", b""))
                return message

            async def outgoing(message: Message) -> None:
                nonlocal status
                if message["type"] == "http.response.start":
                    status = message["status"]
                if message["type"] == "http.response.body":
                    output.extend(message.get("body", b""))
                await send(message)

            await app(scope, incoming, outgoing)
            if route.endswith(":validate"):
                assert (
                    service.snapshot(),
                    service.reference_digest,
                    service.operations_total,
                ) == state
            elif status != 200 and not json.loads(output).get("applied"):
                assert (service.snapshot(), service.reference_digest) == state[:2]
            check_exchange(
                probe, path, Exchange(route, method, before, events, body, output, status)
            )

        return inspect

    patch.object(composition, "build_admin_app", build_app).start()


def check_command(command: str, app: Application, path: Path, original: bytes) -> None:
    assert app.admin is not None
    if command.startswith("verify:"):
        expected = int(command.split(":")[1])
        assert app.revision == expected
        snapshot = app.admin.snapshot()
        if expected == 0:
            assert path.read_bytes() == original
        else:
            assert snapshot.document.model_dump(mode="json") == yaml.safe_load(path.read_bytes())
    elif command == "backup":
        backups = list(path.parent.glob("*.bak.*"))
        assert len(backups) == 1 and backups[0].read_bytes() == original
    elif command == "masking":
        result = _mcp_call(app, "SELECT 'original'::text AS protected_value")
        payload = result.structured_content
        assert payload is not None and payload["rows"] == [["masked"]]
        assert "original" not in json.dumps(payload)
    else:
        raise AssertionError("Unknown harness command")


def report_failure() -> None:
    trace = sys.exc_info()[2]
    line_number = 0
    while trace is not None:
        if trace.tb_frame.f_code.co_filename == __file__:
            line_number = trace.tb_lineno
        trace = trace.tb_next
    sys.stderr.write(f"Browser harness failed. check-line-{line_number}\n")


def main() -> int:
    root = logging.getLogger()
    old_handlers, old_level = root.handlers[:], root.level
    app: Application | None = None
    try:
        token, dsn = os.environ["MASKGW_BROWSER_TOKEN"], os.environ["MASKGW_TEST_DSN"]
        probe = EditProbe(token, dsn)
        root.handlers = [probe]
        root.setLevel(logging.INFO)
        with TemporaryDirectory(prefix="maskgw-browser-edit-") as directory:
            path = Path(directory) / "masking.yaml"
            original = b"# original comment\nmasking: []\nexceptions: []\n"
            path.write_bytes(original)
            instrument(probe, path)
            port = free_port()
            faults = Faults()

            def launch() -> Application:
                return build_application(
                    config_path=path,
                    conninfo=dsn,
                    admin_http=build(token=token, host="127.0.0.1", port=port),
                    admin_ui_enabled=True,
                )

            try:
                app = launch()
                assert app.admin_http is not None
                print(app.admin_http.port, flush=True)
                for line in sys.stdin:
                    command = line.strip()
                    if command == "stop":
                        break
                    assert app.admin is not None
                    if command == "restart":
                        snapshot = app.admin.snapshot()
                        app.close()
                        app = launch()
                        assert app.admin is not None and app.admin.snapshot() == snapshot
                    elif not faults.command(command, app):
                        check_command(command, app, path, original)
                    assert not probe.failed
                    print("ok", flush=True)
                assert not probe.failed
            finally:
                if app is not None:
                    faults.close(app)
                    app.close()
    except BaseException:
        report_failure()
        return 1
    finally:
        if app is not None:
            app.close()
        root.handlers, root.level = old_handlers, old_level
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
