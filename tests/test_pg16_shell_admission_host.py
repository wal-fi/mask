"""Fake tests for the private admission caller. No real process, DLL, launcher,
configuration or root: backend, launcher pin, expected state, clock, sleep and
environment are internal seams replaced in a freshly executed namespace.
"""

import ast
import ctypes
import hashlib
import itertools
import json
import math
import os
import runpy
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "docs/poc/pg16_shell_admission_host.py"
TASK = "c" * 32
NONCE = "e" * 32
ENV_VALUES = {
    "SystemRoot": "C:\\env-sysroot-7f3a",
    "WINDIR": "C:\\env-windir-7f3a",
    "TEMP": "C:\\env-temp-7f3a",
    "TMP": "C:\\env-tmp-7f3a",
    "USERPROFILE": "C:\\env-profile-7f3a",
    "LOCALAPPDATA": "C:\\env-local-7f3a",
    "APPDATA": "C:\\env-roaming-7f3a",
    "HOMEDRIVE": "env-drive-7f3a",
    "HOMEPATH": "\\env-homepath-7f3a",
    "SystemDrive": "env-sysdrive-7f3a",
}
STATE_KEYS = frozenset(
    (
        "kind",
        "task",
        "phase",
        "invoked",
        "program_sha256",
        "v2_sha256",
        "parent_sha256",
        "host_sha256",
        "entry_sha256",
        "pins",
        "pg_pins",
        "transitive_pins",
        "stdlib_pins",
        "image",
        "create_measurements",
        "delivery_plan",
    )
)


def canonical(value: Any) -> bytes:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return text.encode("ascii")


def state_value() -> dict[str, Any]:
    value: dict[str, Any] = dict.fromkeys(STATE_KEYS, "x")
    value.update(task=TASK, phase="FRESH", invoked=False)
    return value


STATE_RAW = canonical(state_value()) + b"\n"


class Win32Error(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)


class Request:
    def __init__(self, *args: Any) -> None:
        self.args = args


class Scenario:
    def __init__(self) -> None:
        self.setup = "ok"
        self.start = "ok"
        self.chunks: list[bytes] = []
        self.wait_true_after = 1
        self.exit = 0
        self.total = 1
        self.stuck = False
        self.tree_error = False
        self.terminate = "ok"
        self.close = "ok"
        self.interrupt: Any = None
        # Exact control exception raised at the interrupt point (identity checked).
        self.interrupt_error: BaseException | None = None
        self.write: Callable[[], None] = lambda: None


class Owner:
    def __init__(self, lab: Any, request: Any) -> None:
        self.lab, self.request, self.scenario = lab, request, lab.scenario
        self.state, self.eof = "NEW", False
        self.finished, self.terminated, self.waits = False, False, 0
        lab.owners.append(self)

    def _event(self, name: str) -> None:
        self.lab.events.append(name)
        if self.scenario.interrupt == name:
            error = self.scenario.interrupt_error
            raise error if error is not None else KeyboardInterrupt()

    def setup(self) -> None:
        self._event("setup")
        mode = self.scenario.setup
        if mode == "fail":
            self.state = "SETUP_FAILED"
            raise Win32Error("WIN32_JOB")
        if mode == "held":
            self.state = "HELD"
            raise Win32Error("WIN32_HELD")
        if mode == "interrupt":
            self.state = "HELD"
            raise KeyboardInterrupt
        self.state = "READY"

    def start(self) -> None:
        self._event("start")
        mode = self.scenario.start
        if mode == "fail":
            self.state = "LAUNCH_FAILED"
            raise Win32Error("WIN32_CREATE")
        if mode == "interrupt":
            self.state = "HELD"
            raise KeyboardInterrupt
        self.state = "RUNNING"
        self.scenario.write()

    def _running(self) -> None:
        if self.state != "RUNNING":
            raise Win32Error("WIN32_HELD" if self.state == "HELD" else "WIN32_STATE")

    def read(self) -> bytes:
        self._event("read")
        self._running()
        chunks: list[bytes] = self.scenario.chunks
        if chunks:
            chunk: bytes = chunks.pop(0)
            return chunk
        if self.finished:
            self.eof = True
        return b""

    def wait(self, milliseconds: int) -> bool:
        self._event("wait")
        self._running()
        assert milliseconds == 50
        self.waits += 1
        if self.waits >= self.scenario.wait_true_after and not self.scenario.stuck:
            self.finished = True
        return self.finished

    def accounting(self) -> tuple[int, int]:
        self._event("accounting")
        self._running()
        if self.scenario.tree_error:
            raise Win32Error("WIN32_TREE")
        return self.scenario.total, 0 if self.finished else 1

    def members(self) -> tuple[int, ...]:
        self._event("members")
        self._running()
        return () if self.finished else (4242,)

    def exit_code(self) -> int:
        self._event("exit_code")
        self._running()
        return int(self.scenario.exit)

    def terminate(self) -> None:
        self._event("terminate")
        self._running()
        if self.scenario.terminate == "held":
            self.state = "HELD"
            raise Win32Error("WIN32_HELD")
        if self.scenario.terminate == "interrupt":
            raise KeyboardInterrupt("second")
        self.terminated = True
        if not self.scenario.stuck:
            self.finished = True

    def close(self) -> None:
        self._event("close")
        if self.scenario.close == "fail":
            self.state = "HELD"
            raise Win32Error("WIN32_HELD")
        self.state = "CLOSED"


def runtime(**changes: Any) -> Any:
    flags = {"isolated": 1, "dont_write_bytecode": 1, "optimize": 0}
    base = {"platform": "win32", "version_info": (3, 11, 3), "maxsize": (1 << 63) - 1}
    for key, value in changes.items():
        if key in flags:
            flags[key] = value
        else:
            base[key] = value
    return SimpleNamespace(flags=SimpleNamespace(**flags), **base)


class Clock:
    def __init__(self) -> None:
        self.values: list[Any] = []
        self.now = 0.0
        self.calls = 0

    def __call__(self) -> Any:
        self.calls += 1
        if self.values:
            value = self.values.pop(0)
            if isinstance(value, BaseException):
                raise value
            return value
        self.now += 0.001
        return self.now


@pytest.fixture
def lab(tmp_path: Path, monkeypatch: Any) -> Any:
    module = runpy.run_path(str(MODULE))
    namespace = module["run"].__globals__
    home = tmp_path / "home"
    temp = home / "AppData" / "Local" / "Temp"
    temp.mkdir(parents=True)
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    root = temp / ("maskgw-pg16-shell-reader-v1-" + NONCE)
    root.mkdir()
    (root / "attempt.json").write_bytes(STATE_RAW)
    item = SimpleNamespace(
        module=module,
        namespace=namespace,
        tmp=tmp_path,
        home=home,
        temp=temp,
        root=root,
        evidence=evidence,
        events=[],
        owners=[],
        sleeps=[],
        loads=[],
        scenario=Scenario(),
        clock=Clock(),
        monkeypatch=monkeypatch,
    )

    def load(raw: bytes) -> Any:
        item.loads.append(len(raw))
        return {
            "Request": Request,
            "Win32Error": Win32Error,
            "Owner": lambda request: Owner(item, request),
        }

    def launcher() -> None:
        item.events.append("launcher")

    monkeypatch.setitem(namespace, "HOME", home)
    monkeypatch.setitem(namespace, "EVIDENCE", evidence)
    monkeypatch.setitem(namespace, "sys", runtime())
    monkeypatch.setitem(namespace, "_environ", lambda: dict(ENV_VALUES))
    monkeypatch.setitem(namespace, "_monotonic", item.clock)
    monkeypatch.setitem(namespace, "_sleep", item.sleeps.append)
    monkeypatch.setitem(namespace, "_launcher_pin", launcher)
    monkeypatch.setitem(namespace, "_load_backend", load)
    monkeypatch.setitem(namespace, "_expected_state", lambda _task: (STATE_RAW, STATE_KEYS))

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("native effect attempted")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(threading.Thread, "start", forbidden)
    monkeypatch.setattr(ctypes, "WinDLL", forbidden)
    probe(item, "WITHIN_3S")
    return item


def identity(lab: Any) -> dict[str, Any]:
    sources = lab.module["SOURCES"]
    return {
        "task": TASK,
        "nonce": NONCE,
        "root_name": lab.root.name,
        "probe_sha256": sources["probe"][1],
        "preparer_sha256": sources["preparer"][1],
        "entry_sha256": sources["entry"][1],
        "state_sha256": hashlib.sha256(STATE_RAW).hexdigest(),
        "state_bytes": len(STATE_RAW),
    }


def classification(outcome: str) -> dict[str, Any]:
    table: dict[str, dict[str, Any]] = {
        "WITHIN_3S": {
            "outcome": "WITHIN_3S",
            "stage": None,
            "category": None,
            "clock_valid": True,
            "elapsed_seconds": 1.5,
            "stages_ns": [10, 20, 30, 0],
        },
        "OVER_3S": {
            "outcome": "OVER_3S",
            "stage": None,
            "category": None,
            "clock_valid": True,
            "elapsed_seconds": math.nextafter(3.0, math.inf),
            "stages_ns": [10, 20, 30, 40],
        },
        "STAGE_FAILED": {
            "outcome": "STAGE_FAILED",
            "stage": "HOST",
            "category": "STAGE_EXCEPTION",
            "clock_valid": True,
            "elapsed_seconds": 0.25,
            "stages_ns": [10, 0, None, None],
        },
        "CLOCK_INVALID": {
            "outcome": "CLOCK_INVALID",
            "stage": None,
            "category": "CLOCK_INVALID",
            "clock_valid": False,
            "elapsed_seconds": None,
            "stages_ns": None,
        },
    }
    return table[outcome]


@dataclass(frozen=True)
class Forge:
    """Scenario deviations from the exact frozen-probe artifacts."""

    terminator: bytes = b"\r\n"
    change: Callable[[dict[str, Any]], None] | None = None
    cli: bytes | None = None
    exit_code: int | None = None
    marker: bool = True


def probe(lab: Any, outcome: str, forge: Forge | None = None) -> None:
    """Scenario: the fake child writes the exact artifacts of the frozen probe."""
    options = forge if forge is not None else Forge()
    change, marker = options.change, options.marker

    def write() -> None:
        ident = identity(lab)
        claim_raw = canonical({"kind": "MASKGW_PG16_SHELL_ADMISSION_CLAIM_V1", **ident}) + b"\n"
        claim_sha = hashlib.sha256(claim_raw).hexdigest()
        claim_path = lab.temp / ("maskgw-pg16-shell-admission-claim-v1-" + NONCE + ".json")
        claim_path.write_bytes(claim_raw)
        result = {
            "kind": "MASKGW_PG16_SHELL_ADMISSION_RESULT_V1",
            **ident,
            **classification(outcome),
            "limit_seconds": 3.0,
            "runtime": "win32-3.11.3-isolated-nobytecode-optimize0",
            "claim_sha256": claim_sha,
        }
        if change is not None:
            change(result)
        if marker:
            marker_value = {
                "kind": "MASKGW_PG16_SHELL_ADMISSION_MARKER_V1",
                "task": TASK,
                "nonce": NONCE,
                "claim_sha256": claim_sha,
            }
            (lab.root / "admission-probe.json").write_bytes(canonical(marker_value) + b"\n")
        name = "maskgw-pg16-shell-admission-result-v1-" + NONCE + ".json"
        (lab.temp / name).write_bytes(
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
        )

    summary = {
        "kind": "MASKGW_PG16_SHELL_ADMISSION_CLI_V1",
        "outcome": outcome,
        "category": classification(outcome)["category"],
    }
    raw = options.cli if options.cli is not None else canonical(summary) + options.terminator
    lab.scenario.chunks = [raw]
    lab.scenario.write = write
    default = 0 if outcome == "WITHIN_3S" else 1
    lab.scenario.exit = default if options.exit_code is None else options.exit_code


def run(lab: Any) -> Any:
    return lab.module["run"](lab.root, TASK)


def refused(lab: Any, code: str) -> Any:
    with pytest.raises(lab.module["HostError"]) as caught:
        run(lab)
    assert caught.value.args == (code,)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    return caught


def tree(lab: Any) -> dict[str, bytes]:
    return {
        str(path.relative_to(lab.tmp)): path.read_bytes()
        for path in sorted(lab.tmp.rglob("*"))
        if path.is_file()
    }


def public(lab: Any) -> Path:
    path: Path = lab.evidence / ("pg16-shell-admission-" + NONCE[:12])
    return path


def private(lab: Any) -> Path:
    path: Path = lab.temp / ("maskgw-pg16-shell-admission-caller-v1-" + NONCE)
    return path


# -- surface -------------------------------------------------------------------


def test_import_defines_only_and_no_operational_surface() -> None:
    tree_ = ast.parse(MODULE.read_bytes())
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree_)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not imported & {"threading", "asyncio", "multiprocessing", "ctypes"}
    for node in ast.walk(tree_):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
            if isinstance(owner, ast.Name) and owner.id == "subprocess":
                assert node.func.attr == "list2cmdline"
            if isinstance(owner, ast.Name) and owner.id == "os":
                assert node.func.attr in ("fsync", "rename")
        if isinstance(node, ast.Name):
            assert node.id not in ("Thread", "Popen", "startfile")
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name):
            assert node.left.id != "__name__"
    module = runpy.run_path(str(MODULE))
    assert callable(module["run"]) and module["_LIVE"] == [] and "main" not in module


# -- positive outcomes ------------------------------------------------------------


@pytest.mark.parametrize("terminator", [b"\n", b"\r\n"])
def test_within_is_evidence_only_and_publication_is_last(lab: Any, terminator: bytes) -> None:
    probe(lab, "WITHIN_3S", Forge(terminator=terminator))
    order: list[str] = []
    original = lab.namespace["os"]

    def rename(source: Any, target: Any) -> None:
        order.append("rename")
        original.rename(source, target)

    lab.monkeypatch.setitem(
        lab.namespace, "os", SimpleNamespace(fsync=original.fsync, rename=rename)
    )
    summary = run(lab)
    assert summary["outcome"] == "ACCEPTED_WITHIN_3S" and summary["category"] is None
    assert summary["entry_gate"] == "NOT_EVALUATED"
    assert summary["stage_admit_ns"] == 10 and summary["stage_final_pins_ns"] == 0
    assert lab.events[:3] == ["launcher", "setup", "start"]
    assert lab.module["_LIVE"] == [] and lab.owners[0].state == "CLOSED"
    assert order == ["rename"]
    names = sorted(path.name for path in public(lab).iterdir())
    assert names == ["summary.json", "transport.json"]
    summary_raw = (public(lab) / "summary.json").read_bytes()
    transport = json.loads((public(lab) / "transport.json").read_bytes())
    assert transport["summary"]["sha256"] == hashlib.sha256(summary_raw).hexdigest()
    assert json.loads(summary_raw) == summary
    for raw in tree(lab).values():
        for value in ENV_VALUES.values():
            assert value.encode() not in raw
    assert str(lab.tmp).encode() not in summary_raw
    assert str(lab.tmp).encode() not in (public(lab) / "transport.json").read_bytes()
    assert sorted(path.name for path in private(lab).iterdir()) == [
        "invocation.json",
        "local-stdout.bin",
        "supervision.json",
    ]


@pytest.mark.parametrize("outcome", ["OVER_3S", "STAGE_FAILED", "CLOCK_INVALID"])
def test_other_valid_outcomes_are_evidence_not_admission(lab: Any, outcome: str) -> None:
    probe(lab, outcome)
    summary = run(lab)
    assert summary["outcome"] == "ACCEPTED_" + outcome
    assert summary["entry_gate"] == "NOT_EVALUATED"
    assert summary["probe_outcome"] == outcome


# -- stdout framing --------------------------------------------------------------


CLI_OK = b'{"category":null,"kind":"MASKGW_PG16_SHELL_ADMISSION_CLI_V1","outcome":"WITHIN_3S"}'


@pytest.mark.parametrize(
    "raw",
    [
        CLI_OK,
        CLI_OK + b"\r",
        CLI_OK + b"\n\n",
        CLI_OK + b"\r\n\r\n",
        CLI_OK + b" \n",
        b" " + CLI_OK + b"\n",
        CLI_OK + b"\n" + CLI_OK + b"\n",
        CLI_OK.replace(b",", b", ") + b"\n",
        CLI_OK[:-1] + b',"outcome":"WITHIN_3S"}\n',
        b'{"category":NaN,"kind":"MASKGW_PG16_SHELL_ADMISSION_CLI_V1","outcome":"WITHIN_3S"}\n',
        b'{"category":1e400,"kind":"MASKGW_PG16_SHELL_ADMISSION_CLI_V1","outcome":"WITHIN_3S"}\n',
        CLI_OK.replace(b"CLI_V1", b"CLI_V2") + b"\n",
        b"",
    ],
)
def test_stdout_framing_variants_are_mismatch(lab: Any, raw: bytes) -> None:
    probe(lab, "WITHIN_3S", Forge(cli=raw))
    summary = run(lab)
    assert summary["outcome"] == "NOT_ACCEPTED" and summary["category"] == "OUTPUT_MISMATCH"


@pytest.mark.parametrize(("outcome", "code"), [("WITHIN_3S", 1), ("OVER_3S", 0), ("WITHIN_3S", 2)])
def test_exit_code_must_match_probe_outcome(lab: Any, outcome: str, code: int) -> None:
    probe(lab, outcome, Forge(exit_code=code))
    assert run(lab)["category"] == "OUTPUT_MISMATCH"


@pytest.mark.parametrize(
    ("outcome", "category"),
    [("REFUSED", "RESULT_MISSING"), ("INTERRUPTED", "INTERRUPTED")],
)
def test_refused_or_interrupted_probe_is_never_accepted(
    lab: Any, outcome: str, category: str
) -> None:
    raw = canonical(
        {"kind": "MASKGW_PG16_SHELL_ADMISSION_CLI_V1", "outcome": outcome, "category": "X"}
    )
    code = 2 if outcome == "INTERRUPTED" else 1
    probe(lab, "WITHIN_3S", Forge(cli=raw + b"\n", exit_code=code))
    summary = run(lab)
    assert summary["outcome"] == "NOT_ACCEPTED" and summary["category"] == category


# -- forged results ----------------------------------------------------------------


def set_value(key: str, value: Any) -> Callable[[dict[str, Any]], None]:
    def change(result: dict[str, Any]) -> None:
        result[key] = value

    return change


FORGERIES: dict[str, tuple[str, Callable[[dict[str, Any]], None]]] = {
    "within-label-over-elapsed": ("WITHIN_3S", set_value("elapsed_seconds", 3.5)),
    "within-int-elapsed": ("WITHIN_3S", set_value("elapsed_seconds", 1)),
    "within-negative": ("WITHIN_3S", set_value("elapsed_seconds", -0.5)),
    "within-bool-delta": ("WITHIN_3S", set_value("stages_ns", [10, True, 30, 0])),
    "within-negative-delta": ("WITHIN_3S", set_value("stages_ns", [10, -1, 30, 0])),
    "within-short-deltas": ("WITHIN_3S", set_value("stages_ns", [10, 20, 30])),
    "within-null-delta": ("WITHIN_3S", set_value("stages_ns", [10, 20, 30, None])),
    "within-clock-invalid": ("WITHIN_3S", set_value("clock_valid", False)),
    "within-stage": ("WITHIN_3S", set_value("stage", "ADMIT")),
    "over-label-within-elapsed": ("OVER_3S", set_value("elapsed_seconds", 3.0)),
    "failed-prefix": ("STAGE_FAILED", set_value("stages_ns", [10, None, None, None])),
    "failed-gap": ("STAGE_FAILED", set_value("stages_ns", [None, 10, None, None])),
    "failed-category": ("STAGE_FAILED", set_value("category", "OTHER")),
    "failed-stage": ("STAGE_FAILED", set_value("stage", "BOOT")),
    "clock-elapsed": ("CLOCK_INVALID", set_value("elapsed_seconds", 1.0)),
    "clock-deltas": ("CLOCK_INVALID", set_value("stages_ns", [1, 2, 3, 4])),
    "clock-valid-true": ("CLOCK_INVALID", set_value("clock_valid", True)),
    "extra-key": ("WITHIN_3S", set_value("extra", 1)),
    "probe-sha": ("WITHIN_3S", set_value("probe_sha256", "0" * 64)),
    "state-bytes-bool": ("WITHIN_3S", set_value("state_bytes", True)),
    "claim-sha": ("WITHIN_3S", set_value("claim_sha256", "0" * 64)),
    "limit-int": ("WITHIN_3S", set_value("limit_seconds", 3)),
    "runtime": ("WITHIN_3S", set_value("runtime", "linux")),
    "task": ("WITHIN_3S", set_value("task", "d" * 32)),
}


@pytest.mark.parametrize("name", sorted(FORGERIES))
def test_forged_result_is_never_accepted(lab: Any, name: str) -> None:
    outcome, change = FORGERIES[name]
    probe(lab, outcome, Forge(change=change))
    summary = run(lab)
    assert summary["outcome"] == "NOT_ACCEPTED" and summary["category"] == "RESULT_MISMATCH"
    assert summary["probe_outcome"] is None


def test_missing_marker_pending_result_or_changed_state_is_mismatch(lab: Any) -> None:
    probe(lab, "WITHIN_3S", Forge(marker=False))
    assert run(lab)["category"] == "RESULT_MISMATCH"


def test_pending_result_left_is_mismatch(lab: Any) -> None:
    write = lab.scenario.write

    pending = lab.temp / ("maskgw-pg16-shell-admission-result-v1-" + NONCE + ".json.next")

    def both() -> None:
        write()
        pending.write_bytes(b"x")

    lab.scenario.write = both
    assert run(lab)["category"] == "RESULT_MISMATCH"


def test_changed_state_bytes_is_mismatch(lab: Any) -> None:
    write = lab.scenario.write

    def changed() -> None:
        write()
        (lab.root / "attempt.json").write_bytes(STATE_RAW.replace(b"FRESH", b"FRESX"))

    lab.scenario.write = changed
    assert run(lab)["category"] == "RESULT_MISMATCH"


def test_missing_result_is_never_accepted(lab: Any) -> None:
    lab.scenario.write = lambda: None
    assert run(lab)["category"] == "RESULT_MISSING"


# -- ownership registry -------------------------------------------------------------


def test_owner_retained_after_raising_and_second_run_refused_before_effects(lab: Any) -> None:
    lab.scenario.close = "fail"
    refused(lab, "HOST_HELD")
    owner = lab.owners[0]
    assert lab.module["_LIVE"] == [owner] and owner.state == "HELD"
    assert not public(lab).exists()
    before, loads = tree(lab), list(lab.loads)
    refused(lab, "HOST_RETAINED")
    assert tree(lab) == before and lab.loads == loads and len(lab.owners) == 1


@pytest.mark.parametrize("point", ["setup", "start", "read", "wait", "accounting", "members"])
def test_interruption_at_each_point_retains_owner(lab: Any, point: str) -> None:
    if point in ("setup", "start"):
        setattr(lab.scenario, point, "interrupt")
    else:
        lab.scenario.interrupt = point
    with pytest.raises(KeyboardInterrupt):
        run(lab)
    owner = lab.owners[0]
    assert lab.module["_LIVE"] == [owner]
    assert "INTERRUPTED" in lab.module["_HELD_REASONS"]
    terminated = "terminate" in lab.events
    assert terminated == (point not in ("setup", "start"))
    assert "close" not in lab.events and not public(lab).exists()
    refused(lab, "HOST_RETAINED")


def test_second_interruption_during_terminate_keeps_registry_and_original(lab: Any) -> None:
    original = KeyboardInterrupt("original")
    lab.scenario.interrupt, lab.scenario.interrupt_error = "read", original
    lab.scenario.terminate = "interrupt"
    with pytest.raises(KeyboardInterrupt) as caught:
        run(lab)
    assert caught.value is original
    assert lab.module["_LIVE"] == [lab.owners[0]] and "terminate" in lab.events
    assert not public(lab).exists()


def test_backend_held_guard_is_never_bypassed(lab: Any) -> None:
    lab.scenario.setup = "held"
    refused(lab, "HOST_HELD")
    assert lab.events == ["launcher", "setup"]
    assert lab.module["_LIVE"] == [lab.owners[0]]


@pytest.mark.parametrize("step", ["setup", "start"])
def test_clean_launch_failure_closes_and_publishes_not_accepted(lab: Any, step: str) -> None:
    setattr(lab.scenario, step, "fail")
    summary = run(lab)
    assert summary["outcome"] == "NOT_ACCEPTED" and summary["category"] == "LAUNCH_FAILED"
    assert lab.module["_LIVE"] == [] and lab.owners[0].state == "CLOSED"


# -- supervision -----------------------------------------------------------------------


def test_signaled_launcher_pauses_instead_of_busy_waiting(lab: Any) -> None:
    run(lab)
    assert lab.events.count("wait") == 1 and lab.sleeps == [0.05]


def test_overflow_terminates_retains_1024_and_drains(lab: Any) -> None:
    lab.scenario.chunks = [b"x" * 1500, b"y" * 4096, b"z" * 10]
    summary = run(lab)
    assert summary["category"] == "OUTPUT_OVERFLOW" and summary["terminated"] is True
    assert summary["retained_stdout_bytes"] == 1024 and not lab.scenario.chunks
    assert len((private(lab) / "local-stdout.bin").read_bytes()) == 1024


def after_start(lab: Any, effect: Callable[[Any], None]) -> None:
    """Causal injection: runs only once the fake child really started."""
    start = Owner.start

    def started(owner: Owner) -> None:
        start(owner)
        effect(owner.lab.clock)

    lab.monkeypatch.setattr(Owner, "start", started)


def jump(seconds: float) -> Callable[[Any], None]:
    def effect(clock: Any) -> None:
        clock.now = seconds

    return effect


def test_late_completion_after_deadline_never_wins(lab: Any) -> None:
    # The tree finishes inside the budget; only the completion read is late.
    exit_code = Owner.exit_code

    def late(owner: Owner) -> int:
        code = exit_code(owner)
        owner.lab.clock.now = 61.0  # clearly past 60 s, no float-edge reliance
        return code

    lab.monkeypatch.setattr(Owner, "exit_code", late)
    summary = run(lab)
    assert "exit_code" in lab.events and summary["terminated"] is False
    assert summary["outcome"] == "NOT_ACCEPTED" and summary["category"] == "DEADLINE"


def test_deadline_terminates_then_cleanup_collects(lab: Any) -> None:
    lab.scenario.wait_true_after = 10**6
    after_start(lab, jump(61.0))
    summary = run(lab)
    assert "start" in lab.events
    assert summary["category"] == "DEADLINE" and summary["terminated"] is True
    assert lab.module["_LIVE"] == []


def test_frozen_clock_is_bounded_by_turn_cap(lab: Any) -> None:
    lab.monkeypatch.setitem(lab.namespace, "MAX_TURNS", 5)
    lab.scenario.wait_true_after = 10**6
    lab.clock.values = [0.0] * 50
    summary = run(lab)
    assert summary["category"] == "DEADLINE" and summary["terminated"] is True


def queue(values: list[Any]) -> Callable[[Any], None]:
    def effect(clock: Any) -> None:
        clock.values = list(values)

    return effect


@pytest.mark.parametrize("bad", [math.nan, math.inf, 1, -1.0, "x", OSError("clock")])
def test_broken_clock_with_running_child_terminates(lab: Any, bad: Any) -> None:
    # Armed after the real start, so the running child must be terminated.
    # -1.0 is decreasing relative to the earlier valid readings.
    after_start(lab, queue([bad]))
    summary = run(lab)
    assert "start" in lab.events and "terminate" in lab.events
    assert summary["outcome"] == "NOT_ACCEPTED" and summary["category"] == "CALLER_CLOCK"
    assert summary["caller_seconds"] is None and summary["terminated"] is True
    assert lab.module["_LIVE"] == []


@pytest.mark.parametrize("bad", [math.nan, OSError("clock")])
def test_broken_clock_before_start_never_creates_child(lab: Any, bad: Any) -> None:
    setup = Owner.setup

    def setup_then_break(owner: Owner) -> None:
        setup(owner)
        owner.lab.clock.values = [bad]

    lab.monkeypatch.setattr(Owner, "setup", setup_then_break)
    summary = run(lab)
    assert "start" not in lab.events and "terminate" not in lab.events
    assert "close" in lab.events and lab.owners[0].state == "CLOSED"
    assert summary["outcome"] == "NOT_ACCEPTED" and summary["category"] == "CALLER_CLOCK"
    assert summary["terminated"] is False and lab.module["_LIVE"] == []


def test_broken_clock_before_setup_creates_no_owner(lab: Any) -> None:
    lab.clock.values = [math.nan]
    refused(lab, "HOST_INTERNAL")
    assert not lab.owners and lab.module["_LIVE"] == []


def test_cleanup_expiry_holds_and_retains(lab: Any) -> None:
    lab.monkeypatch.setitem(lab.namespace, "CLEANUP_TURNS", 3)
    lab.scenario.stuck = True
    after_start(lab, jump(61.0))
    refused(lab, "HOST_HELD")
    assert "start" in lab.events and "terminate" in lab.events
    assert lab.module["_LIVE"] == [lab.owners[0]] and "close" not in lab.events


@pytest.mark.parametrize("total", [0, 3])
def test_tree_count_outside_bound_is_unproven(lab: Any, total: int) -> None:
    lab.scenario.total = total
    assert run(lab)["category"] == "TREE_UNPROVEN"


def test_tree_error_terminates_and_is_unproven(lab: Any) -> None:
    lab.scenario.tree_error = True
    original = Owner.terminate

    def terminate(self: Owner) -> None:
        original(self)
        self.scenario.tree_error = False

    lab.monkeypatch.setattr(Owner, "terminate", terminate)
    summary = run(lab)
    assert summary["category"] == "TREE_UNPROVEN" and summary["terminated"] is True
    assert lab.module["_LIVE"] == []


def test_terminate_failure_holds(lab: Any) -> None:
    lab.scenario.chunks = [b"x" * 2000]
    lab.scenario.terminate = "held"
    refused(lab, "HOST_HELD")
    assert lab.module["_LIVE"] == [lab.owners[0]]


# -- pre-launch guards -------------------------------------------------------------------


@pytest.mark.parametrize(
    "changes", [{"platform": "linux"}, {"version_info": (3, 11, 4)}, {"isolated": 0}]
)
def test_runtime_refused_before_any_write(lab: Any, changes: dict[str, Any]) -> None:
    lab.monkeypatch.setitem(lab.namespace, "sys", runtime(**changes))
    before = tree(lab)
    refused(lab, "HOST_RUNTIME")
    assert tree(lab) == before and not lab.loads


@pytest.mark.parametrize("task", [None, "C" * 32, "c" * 31, b"c" * 32])
def test_invalid_task(lab: Any, task: Any) -> None:
    with pytest.raises(lab.module["HostError"]) as caught:
        lab.module["run"](lab.root, task)
    assert caught.value.args == ("HOST_TASK",)


def test_root_outside_temp_or_extra_file(lab: Any) -> None:
    with pytest.raises(lab.module["HostError"]) as caught:
        lab.module["run"](lab.home / lab.root.name, TASK)
    assert caught.value.args == ("HOST_ROOT",)
    (lab.root / "invoked.json").write_bytes(b"{}")
    refused(lab, "HOST_ROOT")


def test_state_mismatch_refused(lab: Any) -> None:
    (lab.root / "attempt.json").write_bytes(STATE_RAW.replace(b"FRESH", b"FRESX"))
    refused(lab, "HOST_STATE")


@pytest.mark.parametrize("target", ["claim", "result", "pending", "private", "public"])
def test_consumed_names_refused_before_any_write(lab: Any, target: str) -> None:
    paths = {
        "claim": lab.temp / ("maskgw-pg16-shell-admission-claim-v1-" + NONCE + ".json"),
        "result": lab.temp / ("maskgw-pg16-shell-admission-result-v1-" + NONCE + ".json"),
        "pending": lab.temp / ("maskgw-pg16-shell-admission-result-v1-" + NONCE + ".json.next"),
        "private": private(lab),
        "public": public(lab),
    }
    paths[target].mkdir()
    before = tree(lab)
    refused(lab, "HOST_CONSUMED")
    assert tree(lab) == before and not lab.owners


@pytest.mark.parametrize("change", ["missing", "nul", "empty"])
def test_environment_all_ten_required(lab: Any, change: str) -> None:
    values = dict(ENV_VALUES)
    if change == "missing":
        del values["TMP"]
    else:
        values["TMP"] = "a\0b" if change == "nul" else ""
    lab.monkeypatch.setitem(lab.namespace, "_environ", lambda: values)
    refused(lab, "HOST_ENVIRONMENT")
    assert not private(lab).exists()


def test_command_bound(lab: Any) -> None:
    lab.monkeypatch.setitem(lab.namespace, "COMMAND_LIMIT", 10)
    refused(lab, "HOST_COMMAND")
    assert not private(lab).exists()


def test_source_pin_refused(lab: Any) -> None:
    sources = dict(lab.module["SOURCES"])
    sources["probe"] = (sources["probe"][0], "0" * 64)
    lab.monkeypatch.setitem(lab.namespace, "SOURCES", sources)
    refused(lab, "HOST_SOURCE")
    assert not private(lab).exists()


def test_launcher_pin_failure_consumes_without_owner(lab: Any) -> None:
    def broken() -> None:
        raise lab.module["HostError"]("HOST_LAUNCHER")

    lab.monkeypatch.setitem(lab.namespace, "_launcher_pin", broken)
    refused(lab, "HOST_LAUNCHER")
    assert (private(lab) / "invocation.json").is_file() and not lab.owners


def test_invocation_is_durable_before_launch_and_has_no_env_values(lab: Any) -> None:
    run(lab)
    invocation = json.loads((private(lab) / "invocation.json").read_bytes())
    assert invocation["environment_names"] == list(ENV_VALUES)
    assert invocation["argv"][1:3] == ["-I", "-B"] and invocation["argv"][-1] == TASK


def test_invocation_fsync_failure_launches_nothing(lab: Any) -> None:
    def broken(_descriptor: int) -> None:
        raise OSError("secret-detail")

    lab.monkeypatch.setitem(lab.namespace, "os", SimpleNamespace(fsync=broken, rename=os.rename))
    caught = refused(lab, "HOST_PERSISTENCE")
    assert "secret" not in str(caught.value) and not lab.owners


# -- regressions for the four reviewed findings (expected red before helper fix) --


def test_invalid_clock_after_close_is_never_accepted(lab: Any) -> None:
    # P2-A, causal: every reading before close is valid; NaN is armed only
    # after the real close succeeded, so no earlier read can consume it.
    close = Owner.close
    observed: list[Any] = []

    def close_then_break_clock(owner: Owner) -> None:
        close(owner)
        observed.append((owner.state, list(owner.lab.module["_LIVE"])))
        owner.lab.clock.values = [math.nan]

    lab.monkeypatch.setattr(Owner, "close", close_then_break_clock)
    summary = run(lab)
    assert observed and observed[0][0] == "CLOSED" and lab.events.count("close") == 1
    assert not summary["outcome"].startswith("ACCEPTED_")
    assert summary["outcome"] == "NOT_ACCEPTED" and summary["category"] == "CALLER_CLOCK"
    assert summary["caller_seconds"] is None and summary["entry_gate"] == "NOT_EVALUATED"
    assert lab.owners[0].state == "CLOSED" and lab.module["_LIVE"] == []


def test_setup_exhausting_budget_never_starts_child(lab: Any) -> None:
    # P2-B: setup itself consumes 61 s of the decision budget.
    setup = Owner.setup

    def slow_setup(owner: Owner) -> None:
        setup(owner)
        owner.lab.clock.now = 61.0

    lab.monkeypatch.setattr(Owner, "setup", slow_setup)
    summary = run(lab)
    assert "start" not in lab.events and "close" in lab.events
    assert summary["outcome"] == "NOT_ACCEPTED" and summary["category"] == "DEADLINE"
    assert summary["terminated"] is False and summary["launcher_exit_code"] is None
    assert lab.owners[0].state == "CLOSED" and lab.module["_LIVE"] == []


def yields_between_reads(events: list[str]) -> bool:
    reads = [index for index, name in enumerate(events) if name == "read"]
    return all(
        "wait" in events[first:second] or "pause" in events[first:second]
        for first, second in itertools.pairwise(reads)
    )


@pytest.mark.parametrize(
    "chunks",
    [[b"x" * 1500] + [b"y" * 4096] * 5, [b"z" * 4096] * 40],
    ids=["overflow-then-five", "sustained-forty"],
)
def test_overflow_drain_yields_control_every_turn(lab: Any, chunks: list[bytes]) -> None:
    # P2-C: every drain turn must wait or pause; no read/continue bypass.
    lab.scenario.chunks = list(chunks)

    def pause(seconds: float) -> None:
        lab.events.append("pause")
        lab.sleeps.append(seconds)

    lab.monkeypatch.setitem(lab.namespace, "_sleep", pause)
    summary = run(lab)
    assert yields_between_reads(lab.events)
    assert summary["category"] == "OUTPUT_OVERFLOW" and summary["terminated"] is True
    assert summary["retained_stdout_bytes"] == 1024 and not lab.scenario.chunks
    assert lab.module["_LIVE"] == []


def test_supervision_interrupt_persists_private_held_record(lab: Any) -> None:
    # P2-D: the first read returns the probe line, then wait is interrupted.
    original = KeyboardInterrupt("original")
    lab.scenario.interrupt, lab.scenario.interrupt_error = "wait", original
    partial = lab.scenario.chunks[0]
    with pytest.raises(KeyboardInterrupt) as caught:
        run(lab)
    assert caught.value is original
    assert lab.module["_LIVE"] == [lab.owners[0]] and not public(lab).exists()
    record = json.loads((private(lab) / "supervision.json").read_bytes())
    assert record["kind"] == "MASKGW_PG16_SHELL_ADMISSION_SUPERVISION_V1"
    assert record["held"] == "INTERRUPTED"
    assert (private(lab) / "local-stdout.bin").read_bytes() == partial
    for raw in tree(lab).values():
        for value in ENV_VALUES.values():
            assert value.encode() not in raw


def fail_after_invocation(lab: Any, error: BaseException) -> list[int]:
    """Test-only counters: [fsync calls, injected faults actually raised]."""
    counts = [0, 0]

    def fsync(descriptor: int) -> None:
        counts[0] += 1
        if counts[0] > 1:  # the first fsync is the durable invocation record
            counts[1] += 1
            raise error
        os.fsync(descriptor)

    lab.monkeypatch.setitem(lab.namespace, "os", SimpleNamespace(fsync=fsync, rename=os.rename))
    return counts


@pytest.mark.parametrize(
    "fault",
    [OSError("secret-detail"), KeyboardInterrupt("second")],
    ids=["oserror", "second-interrupt"],
)
def test_held_record_fault_keeps_original_interrupt_and_registry(
    lab: Any, fault: BaseException
) -> None:
    original = KeyboardInterrupt("original")
    lab.scenario.interrupt, lab.scenario.interrupt_error = "wait", original
    counts = fail_after_invocation(lab, fault)
    with pytest.raises(KeyboardInterrupt) as caught:
        run(lab)
    # The best-effort HELD write must really have been attempted and faulted.
    assert counts[0] >= 2 and counts[1] >= 1
    assert caught.value is original
    assert lab.module["_LIVE"] == [lab.owners[0]] and not public(lab).exists()
    refused(lab, "HOST_RETAINED")


# -- regressions for review findings on 5dd5a9fe ----------------------------------


@pytest.mark.parametrize("outcome", ["WITHIN_3S", "OVER_3S", "STAGE_FAILED", "CLOCK_INVALID"])
def test_accepted_transport_binds_all_six_retained_artifacts(lab: Any, outcome: str) -> None:
    probe(lab, outcome)
    summary = run(lab)
    assert summary["outcome"] == "ACCEPTED_" + outcome
    transport = json.loads((public(lab) / "transport.json").read_bytes())
    expected = {
        "invocation.json": private(lab) / "invocation.json",
        "supervision.json": private(lab) / "supervision.json",
        "local-stdout.bin": private(lab) / "local-stdout.bin",
        "probe-claim": lab.temp / ("maskgw-pg16-shell-admission-claim-v1-" + NONCE + ".json"),
        "probe-result": lab.temp / ("maskgw-pg16-shell-admission-result-v1-" + NONCE + ".json"),
        "probe-marker": lab.root / "admission-probe.json",
    }
    rows = transport["private"]
    assert [row["name"] for row in rows] == sorted(expected)
    for row in rows:
        raw = expected[row["name"]].read_bytes()  # independent recomputation
        assert row == {
            "name": row["name"],
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    summary_raw = (public(lab) / "summary.json").read_bytes()
    assert transport["summary"]["sha256"] == hashlib.sha256(summary_raw).hexdigest()


@pytest.mark.parametrize(
    ("terminate", "confirmed"),
    [("ok", True), ("held", False), ("interrupt", False)],
    ids=["terminate-succeeded", "terminate-held", "terminate-second-interrupt"],
)
def test_held_record_terminated_reflects_only_a_successful_terminate_call(
    lab: Any, terminate: str, confirmed: bool
) -> None:
    original = KeyboardInterrupt("original")
    lab.scenario.interrupt, lab.scenario.interrupt_error = "wait", original
    lab.scenario.terminate = terminate
    with pytest.raises(KeyboardInterrupt) as caught:
        run(lab)
    assert caught.value is original and "terminate" in lab.events
    record = json.loads((private(lab) / "supervision.json").read_bytes())
    assert record["held"] == "INTERRUPTED" and record["terminated"] is confirmed
    # terminated is a successful call, never proof of reaping: owner stays held.
    assert lab.module["_LIVE"] == [lab.owners[0]] and "close" not in lab.events
    assert not public(lab).exists()
    refused(lab, "HOST_RETAINED")


def test_final_rename_failure_leaves_no_transport(lab: Any) -> None:
    def broken(*_args: Any) -> None:
        raise OSError("secret-detail")

    lab.monkeypatch.setitem(lab.namespace, "os", SimpleNamespace(fsync=os.fsync, rename=broken))
    refused(lab, "HOST_PERSISTENCE")
    assert not (public(lab) / "transport.json").exists()
    assert (public(lab) / "transport.json.next").is_file()
    assert lab.module["_LIVE"] == []
