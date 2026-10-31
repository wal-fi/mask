"""Pin timing contracts with fake clocks/pins. No real executable/config reads."""

import asyncio
import builtins
import io
import json
import runpy
import subprocess
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/pg16_shell_pin_cost.py"))


@pytest.fixture
def fake(module: Any, monkeypatch: Any) -> Any:
    calls: list[Any] = []
    clock = [0]

    def tick() -> int:
        clock[0] += 10
        return clock[0]

    host0 = SimpleNamespace(_monitors={})
    host23 = SimpleNamespace(
        pins=lambda *, cleanup: calls.append("CLEANUP" if cleanup else "NORMAL")
    )
    context0, context23 = object(), object()
    entry = {
        "HOST_SHA": "a" * 64,
        "H": {"SOURCES": {"public": ("public.py", "b" * 64)}},
        "TRANSITIVE_PINS": {"other.py": "c" * 64},
        "final_pins": lambda value: calls.append("FINAL0" if value is context0 else "FINAL23"),
    }
    monkeypatch.setitem(
        module["measurement"].__globals__, "runtime", lambda: calls.append("runtime")
    )
    monkeypatch.setitem(
        module["measurement"].__globals__, "quiet", lambda *_args: calls.append("quiet")
    )
    monkeypatch.setitem(
        module["measurement"].__globals__, "absent", lambda _path: calls.append("absent")
    )
    monkeypatch.setitem(module["measurement"].__globals__, "capture", lambda: entry)
    monkeypatch.setitem(
        module["measurement"].__globals__,
        "setup",
        lambda *_args: (
            host0,
            context0,
            host23,
            context23,
            {
                "builder_ns": 10,
                "host_context0_ns": 20,
                "host_context23_ns": 30,
                "monitors23_ns": 40,
            },
        ),
    )
    monkeypatch.setitem(
        module["measurement"].__globals__, "time", SimpleNamespace(perf_counter_ns=tick)
    )
    return calls, entry, clock


def test_twenty_interleaved_samples_and_stats_without_operator_input(
    module: Any, fake: Any
) -> None:
    calls, _, _ = fake
    raw = module["collect"]()
    report = json.loads(raw)
    assert report["outcome"] == "MEASURED" and report["sample_count"] == 20
    assert [row["mode"] for row in report["samples"]] == [
        "NORMAL",
        "CLEANUP",
        "FINAL0",
        "FINAL23",
    ] * 5
    assert all(row["ns"] == 10 for row in report["samples"])
    assert all(
        value == {"observed_max_ns": 10, "median_ns": 10} for value in report["stats"].values()
    )
    assert calls[:3] == ["runtime", "quiet", "absent"]
    assert calls.count("quiet") == 3 and calls.count("absent") == 2
    assert len(raw) <= 16384 and raw.count(b"\n") == 1
    assert raw == (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


@pytest.mark.parametrize("kind", ["backwards", "bool", "zero", "huge"])
@pytest.mark.usefixtures("fake")
def test_bad_clock_never_publishes_partial_statistics(
    module: Any, monkeypatch: Any, kind: str
) -> None:
    clocks: dict[str, list[Any]] = {
        "backwards": [10, 9],
        "bool": [True],
        "zero": [10, 10],
        "huge": [2**63],
    }
    ticks = clocks[kind]
    values = iter(ticks)
    monkeypatch.setitem(
        module["measurement"].__globals__,
        "time",
        SimpleNamespace(perf_counter_ns=lambda: next(values)),
    )
    report = json.loads(module["collect"]())
    assert report == {"kind": module["KIND"], "outcome": "NOT_PASSED", "category": "CLOCK"}


def test_middle_failure_discards_all_prior_samples_without_text_hooks(
    module: Any, fake: Any, monkeypatch: Any
) -> None:
    calls, entry, _ = fake

    class HostileError(Exception):
        def __str__(self) -> str:
            raise AssertionError("STR_CALLED")

        def __repr__(self) -> str:
            raise AssertionError("REPR_CALLED")

    def failed(_value: Any) -> None:
        raise HostileError("PRIVATE_CONFIG_PATH_TOKEN")

    monkeypatch.setitem(entry, "final_pins", failed)
    raw = module["collect"]()
    assert calls.count("NORMAL") == calls.count("CLEANUP") == 1
    assert json.loads(raw) == {
        "kind": module["KIND"],
        "outcome": "NOT_PASSED",
        "category": "INTERNAL",
    }
    assert b"PRIVATE" not in raw and b"samples" not in raw


@pytest.mark.parametrize(
    "error,category",
    [
        (OSError("PRIVATE_CONFIG"), "IO"),
        (RuntimeError("PRIVATE_CONFIG"), "PIN"),
        (KeyboardInterrupt(), "INTERRUPTED"),
    ],
)
@pytest.mark.usefixtures("fake")
def test_closed_failure_codes_no_raw_data(
    module: Any, monkeypatch: Any, error: Any, category: str
) -> None:
    def failed() -> Any:
        raise error

    monkeypatch.setitem(module["measurement"].__globals__, "capture", failed)
    report = json.loads(module["collect"]())
    assert report == {"kind": module["KIND"], "outcome": "NOT_PASSED", "category": category}


@pytest.mark.parametrize(
    "field", ["extra", "sample-count", "cycle-bool", "ns-bool", "source", "order", "stats"]
)
@pytest.mark.usefixtures("fake")
def test_closed_report_shape_refuses_mutations(module: Any, field: str) -> None:
    report = deepcopy(module["measurement"]())
    if field == "extra":
        report["config"] = "PRIVATE_CONFIG"
    elif field == "sample-count":
        report["sample_count"] = 19
    elif field == "cycle-bool":
        report["samples"][0]["cycle"] = False
    elif field == "ns-bool":
        report["samples"][0]["ns"] = True
    elif field == "source":
        report["source_sha256"] = ["PRIVATE_CONFIG"]
    elif field == "order":
        report["samples"][0]["mode"] = "FINAL23"
    else:
        report["stats"]["NORMAL"]["median_ns"] = 99
    with pytest.raises(module["CostError"]):
        module["validate"](report)


@pytest.mark.parametrize("field", ["host-count-bool", "stats-bool"])
@pytest.mark.usefixtures("fake")
def test_json_boolean_never_substitutes_for_count_or_statistic(module: Any, field: str) -> None:
    report = module["measurement"]()
    if field == "host-count-bool":
        report["host_counts"][0] = False
    else:
        for row in report["samples"]:
            row["ns"] = 1
        for values in report["stats"].values():
            values.update(observed_max_ns=1, median_ns=True)
    with pytest.raises(module["CostError"]):
        module["validate"](report)


@pytest.mark.usefixtures("fake")
def test_output_limit_is_fail_closed_not_truncated_success(module: Any, monkeypatch: Any) -> None:
    monkeypatch.setitem(module["collect"].__globals__, "MAX_REPORT", 200)
    report = json.loads(module["collect"]())
    assert report == {"kind": module["KIND"], "outcome": "NOT_PASSED", "category": "OUTPUT"}


@pytest.mark.parametrize(
    "bad", ["platform", "version", "bytecode", "isolation", "optimize", "argument"]
)
def test_native_refusal_precedes_every_nonbuiltin_import(module: Any, bad: str) -> None:

    output = io.StringIO()
    flags = SimpleNamespace(isolated=1, dont_write_bytecode=1, optimize=0)
    fake_sys = SimpleNamespace(
        platform="win32",
        version_info=(3, 11, 3),
        flags=flags,
        argv=["PUBLIC_SCRIPT"],
        stdout=output,
    )
    if bad == "platform":
        fake_sys.platform = "linux"
    elif bad == "version":
        fake_sys.version_info = (3, 14, 0)
    elif bad == "bytecode":
        flags.dont_write_bytecode = 0
    elif bad == "isolation":
        flags.isolated = 0
    elif bad == "optimize":
        flags.optimize = 1
    else:
        fake_sys.argv.append("PRIVATE_PATH")
    imports: list[str] = []

    def imported(name: str, *_args: Any, **_kwargs: Any) -> Any:
        imports.append(name)
        assert name == "sys"
        return fake_sys

    namespace = {
        "__name__": "__main__",
        "__file__": module["__file__"],
        "__builtins__": vars(builtins) | {"__import__": imported},
    }
    with pytest.raises(SystemExit) as caught:
        exec(compile(Path(module["__file__"]).read_bytes(), module["__file__"], "exec"), namespace)  # noqa: S102 - fixed source, fake sys, every later import refused
    assert caught.value.code == 1 and imports == ["sys"]
    assert json.loads(output.getvalue())["category"] == "RUNTIME"
    assert "PRIVATE" not in output.getvalue()


def test_real_constructors_are_read_only_and_match_reference_arguments(
    module: Any, monkeypatch: Any
) -> None:
    entry = runpy.run_path(str(REPO / "docs/poc/pg16_shell_run.py"))
    root = REPO / ".maskgw-pg16-pin-cost-not-materialized"
    assert not root.exists()
    original_open = Path.open

    def readonly(path: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        assert not any(marker in mode for marker in ("w", "x", "a", "+"))
        assert path.is_relative_to(REPO)
        return original_open(path, mode, *args, **kwargs)

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("NATIVE_OR_WRITE_CALLED")

    monkeypatch.setattr(Path, "open", readonly)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(module["threading"].Thread, "start", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    before = module["threading"].enumerate()
    host0, context0, host23, context23, _ = module["setup"](entry, root)
    assert host0 is not host23 and context0 is not context23
    assert not host0._monitors and len(host23._monitors) == 23
    assert "phase" not in host0.state and "invoked" not in host0.state
    assert all(not m._started and m.thread is None for m in host23._monitors.values())
    assert module["threading"].enumerate() == before and not root.exists()
    for index, case in enumerate(entry["H"]["CASES"], 1):
        monitor = host23._monitors[case]
        assert monitor.root == root / ("watch-" + str(index).zfill(2))
        assert monitor.store is host23._stores[case]
        assert monitor.cleanup_lock is host23._cleanup_lock
        assert monitor._policy["P"]["MANIFEST_SHA"] == host23.profile["MANIFEST_SHA"]
    with pytest.raises(module["CostError"], match="EFFECT"):
        module["forbidden_abort"]()


def test_constructor_arguments_match_start_supervision_with_only_callback_difference(
    module: Any, monkeypatch: Any
) -> None:
    entry = runpy.run_path(str(REPO / "docs/poc/pg16_shell_run.py"))
    state = module["diagnostic_state"](entry)
    root = REPO / ".maskgw-pg16-pin-cost-not-materialized"
    diagnostic = entry["H"]["Host"](root, dict(state))
    reference = entry["H"]["Host"](root, dict(state))
    rows: list[Any] = []

    def constructor(*args: Any) -> Any:
        rows.append(args)
        return object()

    monkeypatch.setitem(diagnostic.pg["watch"], "Watchdog", constructor)
    module["monitors"](diagnostic, root)
    diag_rows = rows[:]
    rows.clear()
    monkeypatch.setitem(reference.pg["watch"], "Watchdog", constructor)

    class LogicalDirectory:
        def __init__(self, path: Any) -> None:
            self.path = path

        def __str__(self) -> str:
            return str(self.path)

        def mkdir(self) -> None:
            return None

    class LogicalRoot:
        def __truediv__(self, name: str) -> LogicalDirectory:
            return LogicalDirectory(root / name)

    async def activate(_case: str) -> None:
        return None

    reference.root = LogicalRoot()
    monkeypatch.setattr(reference, "_activate", activate)
    asyncio.run(reference.start_supervision())
    assert len(rows) == len(diag_rows) == 23
    for diag, ref in zip(diag_rows, rows, strict=True):
        assert str(diag[0]) == str(ref[0])
        assert diag[2] is diagnostic._cleanup_lock and ref[2] is reference._cleanup_lock
        assert diag[1].read().snapshot is ref[1].read().snapshot is None
        assert diag[1].read().b_started is ref[1].read().b_started is None
        assert diag[3] is module["forbidden_abort"] and callable(ref[3])
        assert diag[4:] == ref[4:]
    assert not root.exists()


@pytest.mark.parametrize("effect", ["thread", "policy", "loop", "started", "owner"])
def test_quiet_checks_are_observations_not_loop_constructors(
    module: Any, monkeypatch: Any, effect: str
) -> None:
    main = object()
    fake_threads = SimpleNamespace(
        main_thread=lambda: main,
        current_thread=lambda: main,
        enumerate=lambda: [main] if effect != "thread" else [main, object()],
    )
    fake_async = SimpleNamespace(
        events=SimpleNamespace(
            _event_loop_policy=object() if effect == "policy" else None,
            _get_running_loop=lambda: object() if effect == "loop" else None,
        )
    )
    host = SimpleNamespace(
        _owners={"one": object()} if effect == "owner" else {},
        _host_tasks=[],
        _b_started=None,
        _monitor_attempted=set(),
        _monitors={"one": SimpleNamespace(_started=effect == "started", thread=None)},
    )
    monkeypatch.setitem(module["quiet"].__globals__, "threading", fake_threads)
    monkeypatch.setitem(module["quiet"].__globals__, "asyncio", fake_async)
    with pytest.raises(module["CostError"], match="EFFECT"):
        module["quiet"]((host,))


@pytest.mark.parametrize("valid_runtime", [False, True])
def test_stdout_io_failure_exits_without_original_exception_or_later_capture(
    module: Any, valid_runtime: bool
) -> None:
    class ClosedOutput:
        def __init__(self) -> None:
            self.buffer = self
            self.closed = False

        def write(self, _value: Any) -> Any:
            raise OSError("PRIVATE_OUTPUT_PATH_TOKEN")

        def flush(self) -> None:
            raise OSError("PRIVATE_OUTPUT_PATH_TOKEN")

        def close(self) -> None:
            self.closed = True

    output = ClosedOutput()
    fake_sys = SimpleNamespace(
        platform="win32" if valid_runtime else "linux",
        version_info=(3, 11, 3),
        flags=SimpleNamespace(isolated=1, dont_write_bytecode=1, optimize=0),
        argv=["PUBLIC_SCRIPT"],
        stdout=output,
    )
    fake_async = SimpleNamespace(
        events=SimpleNamespace(_event_loop_policy=object(), _get_running_loop=lambda: None)
    )
    original = builtins.__import__

    def imported(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "sys":
            return fake_sys
        if name == "asyncio":
            return fake_async  # quiet refuses before any entry or real pins
        return original(name, *args, **kwargs)

    namespace = {
        "__name__": "__main__",
        "__file__": module["__file__"],
        "__builtins__": vars(builtins) | {"__import__": imported},
    }
    with pytest.raises(SystemExit) as caught:
        exec(compile(Path(module["__file__"]).read_bytes(), module["__file__"], "exec"), namespace)  # noqa: S102 - fixed source, fake stdout/runtime, capture refused
    assert caught.value.code == 1 and output.closed
