"""Admission probe fakes. Temporary HOME, fake stages/clocks/runtime only.

No real launcher/config/executable read, real admission prefix, operational
root, Host instance, process, thread or event loop. Stages, clocks and the
runtime are injected only through the probe's internal names.
"""

import ast
import asyncio
import hashlib
import io
import json
import math
import os
import runpy
import stat
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Self

import pytest

REPO = Path(__file__).resolve().parents[1]
PROBE = REPO / "docs/poc/pg16_shell_admission_probe.py"
TASK = "c" * 32
NONCE = "e" * 32
STATE = b'{"synthetic":"fresh-state"}\n'
STAGE_NAMES = ("ADMIT", "HOST", "CONTEXT", "FINAL_PINS")
RESULT_KEYS = {
    "kind",
    "task",
    "nonce",
    "root_name",
    "probe_sha256",
    "preparer_sha256",
    "entry_sha256",
    "state_sha256",
    "state_bytes",
    "outcome",
    "stage",
    "category",
    "clock_valid",
    "elapsed_seconds",
    "stages_ns",
    "limit_seconds",
    "runtime",
    "claim_sha256",
}


class Clock:
    def __init__(self, monotonic: list[Any], ticks: list[Any]) -> None:
        self.values = list(monotonic)
        self.ticks = list(ticks)

    def monotonic(self) -> Any:
        return self.values.pop(0)

    def perf_counter_ns(self) -> Any:
        return self.ticks.pop(0)


def runtime(**changes: Any) -> Any:
    flags = {"isolated": 1, "dont_write_bytecode": 1, "optimize": 0}
    base = {"platform": "win32", "version_info": (3, 11, 3), "stdout": io.StringIO()}
    for key, value in changes.items():
        if key in flags:
            flags[key] = value
        else:
            base[key] = value
    return SimpleNamespace(flags=SimpleNamespace(**flags), **base)


@pytest.fixture
def lab(tmp_path: Path, monkeypatch: Any) -> Any:
    module = runpy.run_path(str(PROBE))
    namespace = module["probe"].__globals__
    home = tmp_path / "home"
    temp = home / "AppData" / "Local" / "Temp"
    temp.mkdir(parents=True)
    root = temp / (module["ROOT_PREFIX"] + NONCE)
    root.mkdir()
    (root / "attempt.json").write_bytes(STATE)
    claim = temp / (module["CLAIM_PREFIX"] + NONCE + ".json")
    final = temp / (module["RESULT_PREFIX"] + NONCE + ".json")
    pending = temp / (module["RESULT_PREFIX"] + NONCE + ".json.next")
    marker = root / module["MARKER"]
    calls: list[str] = []

    def admit(path: Path) -> Any:
        # The first measured operation sees a FRESH root and an existing claim.
        assert sorted(item.name for item in path.iterdir()) == ["attempt.json"]
        assert claim.is_file() and not marker.exists()
        calls.append("ADMIT")
        return {"phase": "FRESH"}

    def host(_path: Path, state: Any) -> Any:
        assert state == {"phase": "FRESH"}
        calls.append("HOST")
        return "host"

    def context(_path: Path, _state: Any, host_value: Any) -> Any:
        assert host_value == "host"
        calls.append("CONTEXT")
        return "context"

    def final_pins(context_value: Any) -> None:
        assert context_value == "context"
        calls.append("FINAL_PINS")

    stages = {
        "admit": admit,
        "Host": host,
        "Context": context,
        "final_pins": final_pins,
        "home": home,
        "state_raw": STATE,
    }
    monkeypatch.setitem(namespace, "definitions", lambda _task: dict(stages))
    monkeypatch.setitem(namespace, "sys", runtime())
    monkeypatch.setitem(namespace, "time", Clock([10.0, 11.0], [100, 200, 300, 400, 500]))

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("native effect attempted")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(threading.Thread, "start", forbidden)
    monkeypatch.setattr(asyncio, "new_event_loop", forbidden)
    return SimpleNamespace(
        module=module,
        namespace=namespace,
        home=home,
        temp=temp,
        root=root,
        claim=claim,
        final=final,
        pending=pending,
        marker=marker,
        calls=calls,
        stages=stages,
        monkeypatch=monkeypatch,
    )


def clocks(lab: Any, monotonic: list[Any], ticks: list[Any]) -> None:
    lab.monkeypatch.setitem(lab.namespace, "time", Clock(monotonic, ticks))


def refused(lab: Any, code: str, root: Any = None, task: Any = TASK) -> Any:
    with pytest.raises(lab.module["ProbeError"]) as caught:
        lab.module["probe"](lab.root if root is None else root, task)
    assert caught.value.args == (code,)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    return caught


def strict(raw: bytes) -> Any:
    def reject(_value: str) -> Any:
        raise ValueError("non-finite")

    return json.loads(raw, parse_constant=reject)


def snapshot(lab: Any) -> dict[str, bytes]:
    """Every file under Temp (claim, results, root files) by relative name."""
    return {
        str(path.relative_to(lab.temp)): path.read_bytes()
        for path in sorted(lab.temp.rglob("*"))
        if path.is_file()
    }


def canonical(item: Any) -> bytes:
    text = json.dumps(item, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return (text + "\n").encode("ascii")


def test_import_defines_only(tmp_path: Path) -> None:
    before = sorted(item.name for item in tmp_path.iterdir())
    module = runpy.run_path(str(PROBE))
    assert all(callable(module[name]) for name in ("probe", "main"))
    assert module["LIMIT_SECONDS"] == 3.0 and module["STATE_LIMIT"] == 32768
    assert sorted(item.name for item in tmp_path.iterdir()) == before


def test_probe_source_has_no_forbidden_surface() -> None:
    tree = ast.parse(PROBE.read_bytes())
    forbidden = {"prepare", "run", "drive", "start_supervision", "start_cycle", "sample"}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    names |= {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not names & forbidden
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    imported |= {
        str(node.module).split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not imported & {"subprocess", "asyncio", "threading", "multiprocessing"}


def test_within_order_and_persistence(lab: Any) -> None:
    result = lab.module["probe"](lab.root, TASK)
    assert lab.calls == list(STAGE_NAMES)
    assert result["outcome"] == "WITHIN_3S" and result["elapsed_seconds"] == 1.0
    assert result["stages_ns"] == [100, 100, 100, 100] and result["clock_valid"] is True
    assert set(result) == RESULT_KEYS and result["stage"] is None
    final = lab.final.read_bytes()
    assert final == canonical(result) and strict(final) == result
    assert len(final) <= lab.module["OUTPUT_LIMIT"] and not lab.pending.exists()
    claim = lab.claim.read_bytes()
    assert result["claim_sha256"] == hashlib.sha256(claim).hexdigest()
    assert strict(claim)["nonce"] == NONCE and strict(claim)["task"] == TASK
    assert strict(lab.marker.read_bytes())["claim_sha256"] == result["claim_sha256"]
    assert sorted(item.name for item in lab.root.iterdir()) == [
        "admission-probe.json",
        "attempt.json",
    ]
    for raw in (final, claim, lab.marker.read_bytes()):
        assert str(lab.temp).encode() not in raw and b"\\\\" not in raw
    # Replay of a completed probe: the marker makes the root guard refuse first.
    before = snapshot(lab)
    refused(lab, "PROBE_ROOT")
    assert lab.calls == list(STAGE_NAMES) and snapshot(lab) == before


@pytest.mark.parametrize(
    ("start", "end", "outcome"),
    [
        (10.0, 13.0, "WITHIN_3S"),
        (0.0, math.nextafter(3.0, math.inf), "OVER_3S"),
        (5.0, 5.0, "WITHIN_3S"),
        (5.0, 4.0, "CLOCK_INVALID"),
        (math.nan, 1.0, "CLOCK_INVALID"),
        (0.0, math.inf, "CLOCK_INVALID"),
        (1, 2, "CLOCK_INVALID"),
    ],
)
def test_original_float_boundary(lab: Any, start: Any, end: Any, outcome: str) -> None:
    clocks(lab, [start, end], [100, 200, 300, 400, 500])
    result = lab.module["probe"](lab.root, TASK)
    assert result["outcome"] == outcome
    if outcome == "CLOCK_INVALID":
        assert result["elapsed_seconds"] is None and result["stages_ns"] is None
        assert result["clock_valid"] is False and result["category"] == "CLOCK_INVALID"
    else:
        assert result["elapsed_seconds"] == end - start
    assert strict(lab.final.read_bytes()) == result


@pytest.mark.parametrize(
    ("ticks", "outcome", "stages"),
    [
        ([7, 7, 7, 7, 7], "WITHIN_3S", [0, 0, 0, 0]),
        ([100, 90, 300, 400, 500], "CLOCK_INVALID", None),
        ([100, 200.0, 300, 400, 500], "CLOCK_INVALID", None),
        ([100, True, 300, 400, 500], "CLOCK_INVALID", None),
    ],
)
def test_diagnostic_ticks(lab: Any, ticks: list[Any], outcome: str, stages: Any) -> None:
    clocks(lab, [10.0, 11.0], ticks)
    result = lab.module["probe"](lab.root, TASK)
    assert result["outcome"] == outcome and result["stages_ns"] == stages


class HostileError(Exception):
    def __str__(self) -> str:
        raise AssertionError("exception message read")

    def __repr__(self) -> str:
        raise AssertionError("exception repr read")


@pytest.mark.parametrize("index", range(4))
def test_each_stage_failure_is_closed(lab: Any, index: int) -> None:
    key = ("admit", "Host", "Context", "final_pins")[index]

    def failing(*_args: Any) -> Any:
        lab.calls.append("FAILED")
        raise HostileError()

    lab.stages[key] = failing
    result = lab.module["probe"](lab.root, TASK)
    assert result["outcome"] == "STAGE_FAILED" and result["stage"] == STAGE_NAMES[index]
    assert result["category"] == "STAGE_EXCEPTION"
    assert lab.calls == [*STAGE_NAMES[:index], "FAILED"]
    assert result["stages_ns"] == [100] * (index + 1) + [None] * (3 - index)
    assert lab.marker.is_file() and strict(lab.final.read_bytes()) == result


def test_stage_failure_takes_precedence_over_invalid_clock(lab: Any) -> None:
    def failing(*_args: Any) -> Any:
        raise RuntimeError("private")

    lab.stages["Host"] = failing
    clocks(lab, [math.nan, 1.0], [100, 200, 300])
    result = lab.module["probe"](lab.root, TASK)
    assert result["outcome"] == "STAGE_FAILED" and result["stage"] == "HOST"
    assert result["clock_valid"] is False and result["elapsed_seconds"] is None
    assert b"NaN" not in lab.final.read_bytes() and b"private" not in lab.final.read_bytes()


def test_interruption_is_never_a_result_and_burns_the_claim(lab: Any) -> None:
    def interrupted(*_args: Any) -> Any:
        raise KeyboardInterrupt

    lab.stages["Context"] = interrupted
    with pytest.raises(KeyboardInterrupt):
        lab.module["probe"](lab.root, TASK)
    assert lab.claim.is_file() and not lab.marker.exists()
    assert not lab.final.exists() and not lab.pending.exists()
    # Honest limit: the root is still FRESH; only the claim blocks this caller.
    assert [item.name for item in lab.root.iterdir()] == ["attempt.json"]
    lab.stages["Context"] = lambda *_args: "context"
    refused(lab, "PROBE_CLAIMED")


def occupy_file(_lab: Any, path: Path) -> None:
    path.write_bytes(b"earlier")


def occupy_empty(_lab: Any, path: Path) -> None:
    path.write_bytes(b"")


def occupy_directory(_lab: Any, path: Path) -> None:
    path.mkdir()


def fake_lstat(lab: Any, selected: Path, mode: int, attributes: int = 0) -> None:
    original = Path.lstat

    def lstat(self: Path) -> Any:
        if self == selected:
            return SimpleNamespace(st_mode=mode, st_size=0, st_file_attributes=attributes)
        return original(self)

    lab.monkeypatch.setattr(Path, "lstat", lstat)


def occupy_dangling(lab: Any, path: Path) -> None:
    fake_lstat(lab, path, stat.S_IFLNK | 0o777)


def occupy_reparse(lab: Any, path: Path) -> None:
    fake_lstat(lab, path, stat.S_IFREG | 0o600, 0x400)


OCCUPIERS: dict[str, Callable[[Any, Path], None]] = {
    "file": occupy_file,
    "empty": occupy_empty,
    "directory": occupy_directory,
    "dangling": occupy_dangling,
    "reparse": occupy_reparse,
}


@pytest.mark.parametrize("target", ["claim", "pending", "final"])
@pytest.mark.parametrize("kind", sorted(OCCUPIERS))
def test_any_existing_claim_or_result_refuses_without_opening(
    lab: Any, target: str, kind: str
) -> None:
    path = getattr(lab, target)
    OCCUPIERS[kind](lab, path)
    refused(lab, "PROBE_CLAIMED")
    assert not lab.calls and not lab.marker.exists()
    if kind == "file":
        assert path.read_bytes() == b"earlier"
    if target != "claim":
        assert not lab.claim.exists()


def test_exclusive_create_race_never_overwrites(lab: Any) -> None:
    original = Path.open

    def opener(self: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if self == lab.claim and mode == "xb":
            with original(self, "wb") as racer:
                racer.write(b"racer")
        return original(self, mode, *args, **kwargs)

    lab.monkeypatch.setattr(Path, "open", opener)
    refused(lab, "PROBE_CLAIMED")
    lab.monkeypatch.setattr(Path, "open", original)
    assert lab.claim.read_bytes() == b"racer" and not lab.calls


class Short:
    def __init__(self, stream: Any) -> None:
        self.stream = stream

    def __enter__(self) -> Self:
        self.stream.__enter__()
        return self

    def __exit__(self, *args: Any) -> Any:
        return self.stream.__exit__(*args)

    def write(self, raw: bytes) -> int:
        self.stream.write(raw[:-1])
        return len(raw) - 1

    def flush(self) -> None:
        self.stream.flush()

    def fileno(self) -> int:
        return int(self.stream.fileno())


def short_write(lab: Any, path: Path, _index: int) -> None:
    original = Path.open

    def opener(self: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        stream = original(self, mode, *args, **kwargs)
        return Short(stream) if self == path and mode == "xb" else stream

    lab.monkeypatch.setattr(Path, "open", opener)


def fsync_failure(lab: Any, _path: Path, index: int) -> None:
    count = [0]

    def fsync(descriptor: int) -> None:
        count[0] += 1
        if count[0] == index:
            raise OSError("private-detail")
        os.fsync(descriptor)

    lab.monkeypatch.setitem(lab.namespace, "os", SimpleNamespace(fsync=fsync, rename=os.rename))


def readback_failure(lab: Any, path: Path, _index: int) -> None:
    original = lab.namespace["regular"]

    def regular(candidate: Any, maximum: Any, code: Any) -> Any:
        raw = original(candidate, maximum, code)
        return raw + b"x" if candidate == path else raw

    lab.monkeypatch.setitem(lab.namespace, "regular", regular)


FAILURES: dict[str, Callable[[Any, Path, int], None]] = {
    "short": short_write,
    "fsync": fsync_failure,
    "readback": readback_failure,
}
BOUNDARIES = {
    "claim": ("claim", 1, "PROBE_CLAIM_IO"),
    "marker": ("marker", 2, "PROBE_MARK_IO"),
    "result": ("pending", 3, "PROBE_RESULT_IO"),
}


@pytest.mark.parametrize("boundary", sorted(BOUNDARIES))
@pytest.mark.parametrize("failure", sorted(FAILURES))
def test_persistence_failure_never_returns_success(lab: Any, boundary: str, failure: str) -> None:
    target, index, code = BOUNDARIES[boundary]
    FAILURES[failure](lab, getattr(lab, target), index)
    caught = refused(lab, code)
    assert "private-detail" not in str(caught.value)
    assert not lab.final.exists() and lab.claim.exists()
    calls = list(lab.calls)
    assert calls == ([] if boundary == "claim" else list(STAGE_NAMES))
    lab.monkeypatch.setitem(lab.namespace, "os", os)
    # First applicable guard on replay: a claim failure leaves the root FRESH,
    # so the consumed claim refuses; after measurement the marker file exists
    # (complete or partial) and the root guard refuses first.
    before = snapshot(lab)
    refused(lab, "PROBE_CLAIMED" if boundary == "claim" else "PROBE_ROOT")
    assert lab.calls == calls and snapshot(lab) == before


def test_rename_failure_leaves_no_completion(lab: Any) -> None:
    def rename(*_args: Any) -> None:
        raise OSError("private-detail")

    lab.monkeypatch.setitem(lab.namespace, "os", SimpleNamespace(fsync=os.fsync, rename=rename))
    refused(lab, "PROBE_RESULT_IO")
    assert lab.pending.is_file() and not lab.final.exists() and lab.marker.is_file()


def test_output_bound_checked_before_marker(lab: Any) -> None:
    lab.monkeypatch.setitem(lab.namespace, "OUTPUT_LIMIT", 64)
    refused(lab, "PROBE_RESULT_IO")
    assert lab.claim.is_file() and not lab.marker.exists() and not lab.pending.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"platform": "linux"},
        {"version_info": (3, 11, 4)},
        {"isolated": 0},
        {"dont_write_bytecode": 0},
        {"optimize": 1},
    ],
)
def test_runtime_refused_before_sources_or_claim(lab: Any, changes: dict[str, Any]) -> None:
    def forbidden(_task: Any) -> Any:
        raise AssertionError("sources loaded")

    lab.monkeypatch.setitem(lab.namespace, "definitions", forbidden)
    lab.monkeypatch.setitem(lab.namespace, "sys", runtime(**changes))
    refused(lab, "PROBE_RUNTIME")
    assert not lab.claim.exists() and not lab.calls


class Text(str):
    pass


@pytest.mark.parametrize(
    "task", [None, "", "C" * 32, "c" * 31, "c" * 33, "g" * 32, b"c" * 32, Text("c" * 32)]
)
def test_invalid_task_refused_before_sources(lab: Any, task: Any) -> None:
    def forbidden(_task: Any) -> Any:
        raise AssertionError("sources loaded")

    lab.monkeypatch.setitem(lab.namespace, "definitions", forbidden)
    refused(lab, "PROBE_TASK", task=task)
    assert not lab.claim.exists()


def outside(lab: Any) -> Any:
    other = lab.home / (lab.module["ROOT_PREFIX"] + NONCE)
    other.mkdir()
    return other


def other_prefix(lab: Any) -> Any:
    other = lab.temp / ("maskgw-pg16-public-20261030-" + NONCE)
    other.mkdir()
    return other


def text_root(lab: Any) -> Any:
    return str(lab.root)


def relative_root(lab: Any) -> Any:
    return Path(lab.root.name)


def extra_entry(lab: Any) -> Any:
    (lab.root / "invoked.json").write_bytes(b"{}\n")
    return lab.root


def missing_attempt(lab: Any) -> Any:
    (lab.root / "attempt.json").unlink()
    return lab.root


def reparse_ancestor(lab: Any) -> Any:
    fake_lstat(lab, lab.temp, stat.S_IFDIR | 0o700, 0x400)
    return lab.root


def file_root(lab: Any) -> Any:
    root = lab.temp / (lab.module["ROOT_PREFIX"] + "f" * 32)
    root.write_bytes(b"")
    return root


ROOTS: dict[str, tuple[Callable[[Any], Any], str]] = {
    "outside": (outside, "PROBE_ROOT"),
    "other-prefix": (other_prefix, "PROBE_ROOT"),
    "text": (text_root, "PROBE_ROOT"),
    "relative": (relative_root, "PROBE_ROOT"),
    "extra-entry": (extra_entry, "PROBE_ROOT"),
    "missing-attempt": (missing_attempt, "PROBE_ROOT"),
    "reparse-ancestor": (reparse_ancestor, "PROBE_ROOT"),
    "file-root": (file_root, "PROBE_ROOT"),
}


@pytest.mark.parametrize("name", sorted(ROOTS))
def test_root_refused_before_claim(lab: Any, name: str) -> None:
    build, code = ROOTS[name]
    refused(lab, code, root=build(lab))
    assert not lab.claim.exists() and not lab.calls


@pytest.mark.parametrize(
    "raw", [b'{"other":"state"}\n', b"x" * 32769], ids=["mismatch", "oversize"]
)
def test_state_mismatch_or_oversize_refused(lab: Any, raw: bytes) -> None:
    (lab.root / "attempt.json").write_bytes(raw)
    refused(lab, "PROBE_STATE")
    assert not lab.claim.exists() and not lab.calls


def test_real_pinned_definitions_resolve_without_host(lab: Any) -> None:
    # The fixture only guards native effects; this call uses no injected fake.
    assert lab.module["PREPARER_SHA"].startswith("8d0bf39e")
    module = runpy.run_path(str(PROBE))
    loaded = module["definitions"](TASK)
    assert loaded["admit"].__name__ == "admit"
    assert loaded["Host"].__name__ == "Host" and loaded["Context"].__name__ == "Context"
    assert loaded["final_pins"].__name__ == "final_pins"
    assert loaded["home"] == Path("C:/Users/w.filho")
    preparer = runpy.run_path(str(REPO / "docs/poc/pg16_shell_prepare.py"))
    expected = preparer["state_for"](TASK)
    assert loaded["state_raw"] == canonical(expected) and len(loaded["state_raw"]) <= 32768


@pytest.mark.parametrize("change", ["PREPARER_SHA", "ENTRY_SHA", "SOURCE_LIMIT"])
def test_source_pins_and_size_refuse_before_claim(lab: Any, change: str) -> None:
    lab.monkeypatch.setitem(lab.namespace, "definitions", lab.module["definitions"])
    value = 100 if change == "SOURCE_LIMIT" else "0" * 64
    lab.monkeypatch.setitem(lab.namespace, change, value)
    refused(lab, "PROBE_SOURCE")
    assert not lab.claim.exists() and not lab.calls


class Stream:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.requested: list[int] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def read(self, size: int) -> bytes:
        self.requested.append(size)
        return self.raw[:size]


def fake_file(size: int, raw: bytes) -> tuple[Any, Stream]:
    stream = Stream(raw)
    path = SimpleNamespace(
        lstat=lambda: SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_size=size),
        open=lambda _mode: stream,
    )
    return path, stream


@pytest.mark.parametrize(
    "case",
    [(1, b"xx", 64, "PROBE_SOURCE", 65), (4, b"x" * 4096, 4, "PROBE_SIZE", 5)],
)
def test_bounded_read_on_growth(lab: Any, case: tuple[int, bytes, int, str, int]) -> None:
    size, raw, limit, code, requested = case
    path, stream = fake_file(size, raw)
    with pytest.raises(lab.module["ProbeError"]) as caught:
        lab.module["regular"](path, limit, "PROBE_SOURCE")
    assert caught.value.args == (code,) and stream.requested == [requested]


def cli(lab: Any, argv: Any) -> tuple[int, Any]:
    output = io.StringIO()
    fake = runtime(stdout=output)
    lab.monkeypatch.setitem(lab.namespace, "sys", fake)
    status = lab.module["main"](argv)
    lines = output.getvalue().splitlines()
    assert len(lines) == 1 and str(lab.temp) not in lines[0]
    return status, json.loads(lines[0])


def test_cli_exit_zero_only_for_persisted_within(lab: Any) -> None:
    status, summary = cli(lab, ["probe", str(lab.root), TASK])
    assert status == 0 and summary["outcome"] == "WITHIN_3S" and lab.final.is_file()


@pytest.mark.parametrize("outcome", ["OVER_3S", "CLOCK_INVALID", "STAGE_FAILED"])
def test_cli_nonzero_for_every_other_outcome(lab: Any, outcome: str) -> None:
    if outcome == "OVER_3S":
        clocks(lab, [0.0, 4.0], [1, 2, 3, 4, 5])
    elif outcome == "CLOCK_INVALID":
        clocks(lab, [math.inf, 0.0], [1, 2, 3, 4, 5])
    else:
        lab.stages["admit"] = lambda _root: (_ for _ in ()).throw(RuntimeError())
    status, summary = cli(lab, ["probe", str(lab.root), TASK])
    assert status == 1 and summary["outcome"] == outcome


@pytest.mark.parametrize("argv", [[], ["probe"], ["probe", "x", TASK, "extra"], "probe"])
def test_cli_argument_guard(lab: Any, argv: Any) -> None:
    status, summary = cli(lab, argv)
    assert status == 1 and summary == {
        "kind": "MASKGW_PG16_SHELL_ADMISSION_CLI_V1",
        "outcome": "REFUSED",
        "category": "PROBE_RUNTIME",
    }
    assert not lab.claim.exists()


def test_cli_closed_error_and_interruption_are_nonzero(lab: Any) -> None:
    status, summary = cli(lab, ["probe", str(lab.root), "bad"])
    assert status == 1 and summary["category"] == "PROBE_TASK"

    def interrupted(*_args: Any) -> Any:
        raise KeyboardInterrupt

    lab.monkeypatch.setitem(lab.namespace, "probe", interrupted)
    status, summary = cli(lab, ["probe", str(lab.root), TASK])
    assert status == 2 and summary["outcome"] == "INTERRUPTED"
