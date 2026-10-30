"""Capture-only lab wrapper/tap with injected OS/factory/clock; never Linux load."""

from __future__ import annotations

import ast
import builtins
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_linux_imports_probe import load
from tests.test_loaded_memory_evidence import E, RecordingIO, expectation, original
from tests.test_loaded_memory_supervisor import PARTS, S

T = load("loaded_memory_tap")
W = load("linux_held_probe")


class EntryIO(RecordingIO):
    def __init__(self, case: str) -> None:
        super().__init__(case)
        self.os, self.select = object(), object()


class Scenario:
    def __init__(self, case: str = "private") -> None:
        self.case, self.now = case, 100.0
        self.io = EntryIO(case)
        self.calls: list[str] = []
        self.writes: list[bytes] = []
        self.platform = "linux"
        self.flags = SimpleNamespace(isolated=1, no_site=1, dont_write_bytecode=1)
        self.os = SimpleNamespace(getuid=lambda: 65534, getpid=lambda: 1)
        self.supervisor = SimpleNamespace(
            load_parts=self.parts,
            LinuxSupervisor=SimpleNamespace(from_linux=self.factory),
            supervise=S.supervise,
            bounded_report=S.bounded_report,
            write_report=self.write,
        )
        self.bundle = SimpleNamespace(supervisor=self.supervisor, tap=T)

    def clock(self) -> float:
        return self.now

    def loader(self) -> Any:
        self.calls.append("load")
        return self.bundle

    def parts(self) -> Any:
        self.calls.append("parts")
        return PARTS

    def factory(self, parts: Any, deadline: float) -> RecordingIO:
        self.calls.append("factory")
        assert parts is PARTS and deadline == 120
        return self.io

    def write(self, raw: bytes, **kwargs: Any) -> None:
        self.calls.append("write")
        assert kwargs["os_api"] is self.io.os and kwargs["select_fn"] is self.io.select
        assert kwargs["clock"] == self.io.clock
        self.writes.append(raw)

    def run(self, argv: Any = None) -> int:
        result: int = W.run(
            argv
            if argv is not None
            else ["--case", self.case, "--expected", expectation(self.case)],
            platform=self.platform,
            flags=self.flags,
            os_api=self.os,
            clock=self.clock,
            loader=self.loader,
        )
        return result


@pytest.mark.parametrize("case", ["control", "private", "shared"])
def test_entry_emits_capture_only_transport_accepted_by_host_evidence(case):
    data = Scenario(case)
    assert data.run() == 0
    assert data.calls == ["load", "parts", "factory", "write"]
    assert data.io.closed and data.io.trace[-2:] == ["cleanup", "final"]
    transport = json.loads(data.writes[0])
    assert set(transport) == {"profile", "original", "held", "tap_broken"}
    assert transport["profile"] == "loaded-as128-held-transport-v1"
    assert transport["tap_broken"] is False and "outcome" not in transport
    held = tuple(item.encode("ascii") for item in transport["held"])
    assert held == tuple(data.io.emitted)
    encoded = E.encode(transport["original"].encode("ascii"), held, case, expectation(case))
    parsed = E.decode(encoded, case, expectation(case))
    assert parsed["outcome"] == ("control_ok" if case == "control" else "imposed")
    assert len(data.writes[0]) <= 65536


@pytest.mark.parametrize(
    "mode", ["windows", "isolation", "site", "bytecode", "root", "member", "bool-pid"]
)
def test_bad_runtime_does_not_load_or_construct_anything(mode):
    data = Scenario()
    if mode == "windows":
        data.platform = "win32"
    elif mode in ("isolation", "site", "bytecode"):
        setattr(
            data.flags,
            {"isolation": "isolated", "site": "no_site", "bytecode": "dont_write_bytecode"}[mode],
            0,
        )
    elif mode == "root":
        data.os.getuid = lambda: 0
    else:
        data.os.getpid = lambda: True if mode == "bool-pid" else 2
    assert data.run() == 64 and data.calls == [] and data.writes == []


@pytest.mark.parametrize(
    "argv",
    [
        ["--member", "private"],
        [],
        ["--case", "wrong", "--expected", "-"],
        ["--case", "private", "--expected", "-"],
    ],
    ids=["member", "empty", "case", "digest"],
)
def test_bad_argv_never_calls_factory_or_writer(argv):
    data = Scenario()
    assert data.run(argv) == 64
    assert "factory" not in data.calls and data.writes == []


@pytest.mark.parametrize("point", ["load", "parts", "factory", "capture", "write"])
def test_unexpected_failures_are_fixed_exit_without_traceback(monkeypatch, point):
    data = Scenario()

    def failed(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("must-not-be-printed")

    if point == "load":
        monkeypatch.setattr(data, "loader", failed)
    elif point == "parts":
        monkeypatch.setattr(data.supervisor, "load_parts", failed)
    elif point == "factory":
        monkeypatch.setattr(data.supervisor.LinuxSupervisor, "from_linux", failed)
    elif point == "capture":
        monkeypatch.setattr(T, "capture", failed)
    else:
        monkeypatch.setattr(data.supervisor, "write_report", failed)
    assert data.run() == 70 and data.writes == []
    if point == "write":
        assert data.io.closed
    elif point in ("load", "parts", "factory", "capture"):
        assert data.io.spawned == 0


@pytest.mark.parametrize("point", ["load", "parts"])
def test_loader_cost_is_inside_deadline_before_factory(monkeypatch, point):
    data = Scenario()
    method = data.loader if point == "load" else data.parts

    def late() -> Any:
        result = method()
        data.now = 121.0
        return result

    monkeypatch.setattr(
        data if point == "load" else data.supervisor,
        "loader" if point == "load" else "load_parts",
        late,
    )
    assert data.run() == 70
    assert "factory" not in data.calls and data.writes == []


def test_delegated_deadline_negative_is_preserved_not_rewritten(monkeypatch):
    data = Scenario()

    def failed() -> None:
        raise S.SupervisorFault("DEADLINE")

    monkeypatch.setattr(data.io, "read", failed)
    assert data.run() == 0 and data.io.closed
    transport = json.loads(data.writes[0])
    assert json.loads(transport["original"])["failure"]["category"] == "DEADLINE"
    assert transport["tap_broken"] is False and transport["held"] == []


@pytest.mark.parametrize("count", [1, 2])
def test_capture_tap_parity_with_frozen_evidence_tap(count):
    _source, held = original()
    left, right = RecordingIO("private"), RecordingIO("private")
    left.queue, right.queue = [held[0]] * count, [held[0]] * count
    a, b = T.Tap(left, E.CORE), E.Tap(right)
    assert [a.read() for _ in range(count)] == [b.read() for _ in range(count)]
    assert a.lines == b.lines == held * count


def test_capture_tap_broken_transport_keeps_negative_and_candidates(monkeypatch):
    data = Scenario()
    init = T.Tap.__init__

    def exhausted(self: Any, io: Any, core: Any) -> None:
        init(self, io, core)
        self._lines = (b"reserved\n", b"reserved\n")

    monkeypatch.setattr(T.Tap, "__init__", exhausted)
    assert data.run() == 0 and data.io.closed
    transport = json.loads(data.writes[0])
    assert transport["tap_broken"] is True
    assert json.loads(transport["original"])["outcome"] == "inconclusive"
    assert data.io.commands == [b"GO_IMPORTS\n", b"PRESSURE_PRIVATE\n"]


@pytest.mark.parametrize("mode", ["line", "count", "original", "overhead", "bool"])
def test_transport_caps_are_not_truncated_or_promoted(mode):
    source, held = original()
    broken: Any = False
    if mode == "line":
        held = (b"x" * 1025,)
    elif mode == "count":
        held *= 3
    elif mode == "original":
        source = b"x" * 65537
    elif mode == "overhead":
        source = source[:-1] + b" " * (65000 - len(source)) + b"\n"
    else:
        broken = 0
    assert T.transport(source, held, broken) == T.FALLBACK


def test_load_bundle_needs_only_stdlib_and_exact_sibling_sources():
    bundle = W.load_bundle()
    assert bundle.tap.__file__.endswith("loaded_memory_tap.py")
    assert bundle.supervisor.__file__.endswith("linux_loaded_probe.py")
    assert not any(key in vars(bundle.tap) for key in ("HOST", "E", "PREP", "packaging"))
    assert hashlib.sha256(Path(bundle.tap.__file__).read_bytes()).hexdigest() == W.TAP_SHA


@pytest.mark.parametrize("size", [10, 65537])
def test_wrong_source_never_executes_unverified_bytes(tmp_path, size):
    path = tmp_path / "wrong.py"
    path.write_bytes(b"x" * size)
    with pytest.raises(W.EntryFault, match=r"^ENTRY$"):
        W.load_checked(path, W.TAP_SHA, "unused")


def test_import_defines_only_entry_no_loaded_bundle_or_host_dependencies():
    assert not any(key in vars(W) for key in ("HOST", "E", "PREP", "packaging", "bundle"))
    assert not any(key in vars(T) for key in ("HOST", "E", "PREP", "packaging"))


def test_direct_imports_are_stdlib_and_parts_do_not_load_host_sources(monkeypatch):
    for module in (W, T):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    item.name.split(".")[0] in sys.stdlib_module_names for item in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                assert (
                    node.module is not None and node.module.split(".")[0] in sys.stdlib_module_names
                )
    imported = builtins.__import__
    forbidden = {"packaging", "loaded_memory_evidence", "run_linux_loaded", "prepare_linux_imports"}

    def guarded(name: str, *args: Any, **kwargs: Any) -> Any:
        assert name.split(".", maxsplit=1)[0] not in forbidden
        return imported(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    bundle = W.load_bundle()
    parts = bundle.supervisor.load_parts()
    assert {Path(value.__file__).name for value in vars(parts).values()} == {
        "loaded_memory_protocol.py",
        "loaded_memory_member.py",
        "loaded_memory_collect.py",
        "linux_import_probe.py",
        "linux_as_probe.py",
    }


@pytest.mark.parametrize("mode", ["bool", "nan", "negative", "regressed"])
def test_invalid_clock_does_not_call_factory(mode, monkeypatch):
    data = Scenario()
    values: list[Any] = (
        [100.0, 99.0]
        if mode == "regressed"
        else [{"bool": True, "nan": float("nan"), "negative": -1.0}[mode]]
    )
    iterator = iter(values)
    monkeypatch.setattr(data, "clock", lambda: next(iterator))
    assert data.run() == 70 and "factory" not in data.calls and data.writes == []


@pytest.mark.parametrize("raw", [b"", b"x" * 65537, "not-bytes"], ids=["empty", "large", "text"])
def test_invalid_capture_output_is_not_written(monkeypatch, raw):
    data = Scenario()
    monkeypatch.setattr(T, "capture", lambda *_args, **_kwargs: raw)
    assert data.run() == 70 and data.writes == [] and data.io.spawned == 0


def test_emitted_fallback_exit_zero_is_not_a_semantic_success(monkeypatch):
    data = Scenario()
    monkeypatch.setattr(T, "capture", lambda *_args, **_kwargs: T.FALLBACK)
    assert data.run() == 0 and data.writes == [T.FALLBACK]
    assert json.loads(data.writes[0])["outcome"] == "inconclusive"


def test_new_tap_delegated_error_has_same_identity_and_no_broken_flag(monkeypatch):
    io = RecordingIO("private")
    fault = S.SupervisorFault("PROTOCOL")

    def failed() -> None:
        raise fault

    monkeypatch.setattr(io, "read", failed)
    tap = T.Tap(io, PARTS.protocol)
    with pytest.raises(S.SupervisorFault) as error:
        tap.read()
    assert error.value is fault and tap.broken is False
    io.pid = 11
    assert tap.pid == 11


def test_new_tap_own_error_is_terminal_sanitized_and_matches_evidence_rules():
    io = RecordingIO("private")

    def failed(_raw: Any) -> None:
        raise MemoryError("not-a-refusal")

    core = SimpleNamespace(decode_held=failed, ProtocolFault=PARTS.protocol.ProtocolFault)
    tap = T.Tap(io, core)
    with pytest.raises(T.TapFault) as error:
        tap.read()
    assert tap.broken and error.value.__cause__ is None and error.value.__context__ is None


def test_checked_loader_executes_checked_buffer_not_reopened_file(tmp_path, monkeypatch):
    path = tmp_path / "small.py"
    source = b"value = 'checked'\n"
    path.write_bytes(source)
    compiler = builtins.compile

    def swapped(raw: Any, filename: str, mode: str) -> Any:
        path.write_bytes(b"value = 'changed'\n")
        return compiler(raw, filename, mode)

    monkeypatch.setattr(W, "compile", swapped, raising=False)
    module = W.load_checked(path, hashlib.sha256(source).hexdigest(), "verified_buffer")
    assert module.value == "checked" and path.read_bytes() != source
