"""Shell-reader preparer fakes. Temporary directories and synthetic launcher only.

No real launcher/configuration bytes, operational root, entry run, Docker, PG,
SQL or process spawn. HOME is redirected to a private temporary tree inside a
freshly executed copy of the pinned definitions; frozen sources are unchanged.
"""

import ast
import hashlib
import json
import os
import runpy
import stat
import subprocess
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Self

import pytest

REPO = Path(__file__).resolve().parents[1]
PREPARE = REPO / "docs/poc/pg16_shell_prepare.py"
ENTRY = REPO / "docs/poc/pg16_shell_run.py"
TASK = "c" * 32
NONCE = "e" * 32  # root nonce is independent from the task
PREFIX = "maskgw-pg16-shell-reader-v1-"


def canonical(item: Any) -> bytes:
    return (json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def admit_keys() -> set[str]:
    """Key set literal of the accepted entry admit, read from its source AST."""
    tree = ast.parse(ENTRY.read_bytes())
    admit = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "admit"
    )
    for node in ast.walk(admit):
        if isinstance(node, ast.Set) and all(isinstance(item, ast.Constant) for item in node.elts):
            values = {item.value for item in node.elts if isinstance(item, ast.Constant)}
            if "stdlib_pins" in values:
                return {str(value) for value in values}
    raise AssertionError("admit key set not found")


@pytest.fixture
def prep(tmp_path: Path, monkeypatch: Any) -> Any:
    module = runpy.run_path(str(PREPARE))
    namespace = module["materialize"].__globals__
    home = tmp_path / "home"
    temp = home / "AppData" / "Local" / "Temp"
    temp.mkdir(parents=True)
    original = namespace["load"]

    def load() -> Any:
        exporter, d = original()
        # Private copy of the pinned 4bc namespace for this call only.
        d["base"]["HOME"] = home
        return exporter, d

    monkeypatch.setitem(namespace, "load", load)
    launcher = tmp_path / "venv" / "python.exe"
    launcher.parent.mkdir()
    launcher.write_bytes(b"synthetic launcher bytes, never an executable")
    monkeypatch.setitem(namespace, "PYTHON", launcher)
    monkeypatch.setitem(namespace, "PYTHON_SHA", hashlib.sha256(launcher.read_bytes()).hexdigest())

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("process spawn attempted")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    root: Path = temp / (PREFIX + NONCE)
    return SimpleNamespace(
        module=module, namespace=namespace, home=home, temp=temp, root=root, launcher=launcher
    )


def refused(prep: Any, function: str, *args: Any, code: str) -> Any:
    with pytest.raises(prep.module["PrepareError"]) as caught:
        prep.module[function](*args)
    assert caught.value.args == (code,)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    return caught


def fake_lstat(monkeypatch: Any, selected: Path, mode: int, attributes: int = 0) -> None:
    original = Path.lstat

    def lstat(self: Path) -> Any:
        if self == selected:
            return SimpleNamespace(st_mode=mode, st_size=0, st_file_attributes=attributes)
        return original(self)

    monkeypatch.setattr(Path, "lstat", lstat)


def test_import_defines_only(tmp_path: Path) -> None:
    before = sorted(path.name for path in tmp_path.iterdir())
    module = runpy.run_path(str(PREPARE))
    assert "main" not in module
    assert all(callable(module[name]) for name in ("state_for", "proposal", "materialize"))
    assert sorted(path.name for path in tmp_path.iterdir()) == before
    accepted = "bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82"
    assert module["PYTHON"] == REPO / ".venv/Scripts/python.exe"
    assert module["PYTHON_SHA"] == accepted
    assert module["STATE_LIMIT"] == 32768 and module["MAX_COMMAND_CHARS"] == 2048


def test_state_is_the_exact_fresh_admit_schema(prep: Any) -> None:
    state = prep.module["state_for"](TASK)
    entry = runpy.run_path(str(ENTRY))
    keys = admit_keys()
    assert len(keys) == 16 and set(state) == keys == set(prep.module["STATE_KEYS"])
    assert state["kind"] == "maskgw-pg16-shell-reader-v1" and state["task"] == TASK
    assert state["phase"] == "FRESH" and state["invoked"] is False
    assert state["program_sha256"] == entry["H"]["V2"]["ORIGINAL_SHA"]
    assert state["v2_sha256"] == entry["H"]["P"]["V2_SHA"]
    assert state["parent_sha256"] == entry["H"]["PARENT_SHA"]
    assert state["host_sha256"] == entry["HOST_SHA"]
    assert state["entry_sha256"] == hashlib.sha256(ENTRY.read_bytes()).hexdigest()
    assert state["image"] == entry["IMAGE"]
    expected = {
        "pins": dict(entry["R"]["LIBRARIES"].values()),
        "pg_pins": dict(entry["H"]["SOURCES"].values()),
        "transitive_pins": dict(entry["TRANSITIVE_PINS"]),
        "stdlib_pins": dict(entry["C"]["STDLIB_PINS"]),
    }
    for key, value in expected.items():
        assert entry["R"]["json_bytes"](state[key]) == entry["R"]["json_bytes"](value)
    profile = runpy.run_path(str(REPO / "docs/poc/pg16_shell_profile.py"))
    delivery = runpy.run_path(str(REPO / "docs/poc/pg16_shell_delivery.py"))
    cases = list(entry["H"]["CASES"])
    assert len(cases) == 23
    measurements = {
        case: profile["blueprint"](TASK, profile["R"]["Case"](case))[1] for case in cases
    }
    plan = {case: asdict(delivery["delivery_for"](case)[1]) for case in cases}
    assert canonical(state["create_measurements"]) == canonical(measurements)
    assert canonical(state["delivery_plan"]) == canonical(plan)
    raw = canonical(state)
    assert raw == entry["R"]["json_bytes"](state)
    assert raw.isascii() and len(raw) <= entry["STATE_LIMIT"] == 32768


def test_state_is_deterministic_and_bounded(prep: Any, monkeypatch: Any) -> None:
    first = canonical(prep.module["state_for"](TASK))
    assert canonical(prep.module["state_for"](TASK)) == first
    monkeypatch.setitem(prep.namespace, "STATE_LIMIT", len(first) - 1)
    refused(prep, "state_for", TASK, code="PREPARE_SIZE")
    refused(prep, "proposal", prep.root, TASK, code="PREPARE_SIZE")
    refused(prep, "materialize", prep.root, TASK, code="PREPARE_SIZE")
    assert not prep.root.exists()


class Text(str):
    pass


@pytest.mark.parametrize(
    "task",
    [None, "", "C" * 32, "c" * 31, "c" * 33, "g" * 32, b"c" * 32, Text("c" * 32), 7],
)
def test_invalid_task_refused_before_any_write(prep: Any, task: Any) -> None:
    refused(prep, "state_for", task, code="PREPARE_TASK")
    refused(prep, "proposal", prep.root, task, code="PREPARE_TASK")
    refused(prep, "materialize", prep.root, task, code="PREPARE_TASK")
    assert not prep.root.exists()


def test_proposal_is_exact_without_write_spawn_or_launcher_read(
    prep: Any, monkeypatch: Any
) -> None:
    def forbidden() -> None:
        raise AssertionError("launcher read in proposal")

    monkeypatch.setitem(prep.namespace, "launcher_pin", forbidden)
    described = prep.module["proposal"](prep.root, TASK)
    argv = [str(prep.launcher), "-I", "-B", str(ENTRY), str(prep.root)]
    raw = canonical(prep.module["state_for"](TASK))
    assert described["argv"] == argv
    assert described["command_chars"] == len(subprocess.list2cmdline(argv)) <= 2048
    assert described["state_bytes"] == len(raw)
    assert described["state_sha256"] == hashlib.sha256(raw).hexdigest()
    assert described["state_keys"] == 16 and described["case_count"] == 23
    assert described["root_name"] == PREFIX + NONCE and described["task"] == TASK
    assert described["materialized"] is False and described["launcher_verified"] is False
    assert described["admission_3s"] == "NOT_MEASURED"
    assert not prep.root.exists() and not list(prep.temp.iterdir())


def test_real_launcher_is_only_named_in_proposal(prep: Any, monkeypatch: Any) -> None:
    real = prep.module["PYTHON"]
    monkeypatch.setitem(prep.namespace, "PYTHON", real)
    monkeypatch.setitem(prep.namespace, "PYTHON_SHA", prep.module["PYTHON_SHA"])
    original = prep.namespace["regular"]

    def regular(path: Any, maximum: Any, code: Any) -> Any:
        assert path != real, "real launcher bytes read"
        return original(path, maximum, code)

    monkeypatch.setitem(prep.namespace, "regular", regular)
    described = prep.module["proposal"](prep.root, TASK)
    assert described["argv"][0] == str(REPO / ".venv/Scripts/python.exe")
    assert described["launcher_sha256"] == prep.module["PYTHON_SHA"]


def outside_temp(prep: Any, _monkeypatch: Any) -> Any:
    return prep.home / (PREFIX + NONCE)


def nested(prep: Any, _monkeypatch: Any) -> Any:
    (prep.temp / "inner").mkdir()
    return prep.temp / "inner" / (PREFIX + NONCE)


def other_prefix(prep: Any, _monkeypatch: Any) -> Any:
    return prep.temp / ("maskgw-pg16-public-20261030-" + NONCE)


def upper_nonce(prep: Any, _monkeypatch: Any) -> Any:
    return prep.temp / (PREFIX + "E" * 32)


def short_nonce(prep: Any, _monkeypatch: Any) -> Any:
    return prep.temp / (PREFIX + "e" * 31)


def text_root(prep: Any, _monkeypatch: Any) -> Any:
    return str(prep.root)


def relative_root(prep: Any, _monkeypatch: Any) -> Any:
    return Path(prep.root.name)


def existing_directory(prep: Any, _monkeypatch: Any) -> Any:
    prep.root.mkdir()
    return prep.root


def existing_file(prep: Any, _monkeypatch: Any) -> Any:
    prep.root.write_bytes(b"")
    return prep.root


def dangling_link(prep: Any, monkeypatch: Any) -> Any:
    fake_lstat(monkeypatch, prep.root, stat.S_IFLNK | 0o777)
    return prep.root


def reparse_ancestor(prep: Any, monkeypatch: Any) -> Any:
    fake_lstat(monkeypatch, prep.temp, stat.S_IFDIR | 0o700, 0x400)
    return prep.root


def linked_ancestor(prep: Any, monkeypatch: Any) -> Any:
    fake_lstat(monkeypatch, prep.temp.parent, stat.S_IFLNK | 0o777)
    return prep.root


def missing_temp(prep: Any, _monkeypatch: Any) -> Any:
    prep.temp.rmdir()
    return prep.root


ROOTS: dict[str, Callable[[Any, Any], Any]] = {
    "outside-temp": outside_temp,
    "nested": nested,
    "other-prefix": other_prefix,
    "upper-nonce": upper_nonce,
    "short-nonce": short_nonce,
    "text": text_root,
    "relative": relative_root,
    "existing-directory": existing_directory,
    "existing-file": existing_file,
    "dangling-link": dangling_link,
    "reparse-ancestor": reparse_ancestor,
    "linked-ancestor": linked_ancestor,
    "missing-temp": missing_temp,
}


@pytest.mark.parametrize("name", sorted(ROOTS))
def test_root_refused_without_creation(prep: Any, monkeypatch: Any, name: str) -> None:
    root = ROOTS[name](prep, monkeypatch)
    occupied = name in ("existing-directory", "existing-file")
    before = prep.root.read_bytes() if name == "existing-file" else None
    refused(prep, "proposal", root, TASK, code="PREPARE_ROOT")
    refused(prep, "materialize", root, TASK, code="PREPARE_ROOT")
    if occupied:
        assert prep.root.is_dir() == (name == "existing-directory")
        assert before is None or prep.root.read_bytes() == before
        assert not (prep.root.is_dir() and list(prep.root.iterdir()))
    elif name != "dangling-link":
        assert not prep.root.exists()


def test_command_size_bound_is_explicit(prep: Any, monkeypatch: Any) -> None:
    argv = [str(prep.launcher), "-I", "-B", str(ENTRY), str(prep.root)]
    size = len(subprocess.list2cmdline(argv))
    monkeypatch.setitem(prep.namespace, "MAX_COMMAND_CHARS", size)
    assert prep.module["proposal"](prep.root, TASK)["command_chars"] == size
    monkeypatch.setitem(prep.namespace, "MAX_COMMAND_CHARS", size - 1)
    refused(prep, "proposal", prep.root, TASK, code="PREPARE_COMMAND")
    refused(prep, "materialize", prep.root, TASK, code="PREPARE_COMMAND")
    assert not prep.root.exists()


def test_materialize_writes_only_exact_state_once(prep: Any) -> None:
    described = prep.module["materialize"](prep.root, TASK)
    raw = canonical(prep.module["state_for"](TASK))
    assert [path.name for path in prep.root.iterdir()] == ["attempt.json"]
    written = (prep.root / "attempt.json").read_bytes()
    assert written == raw
    assert described["state_sha256"] == hashlib.sha256(written).hexdigest()
    assert described["state_bytes"] == len(written)
    assert described["argv"][-1] == str(prep.root) and described["root"] == str(prep.root)
    assert described["materialized"] is True and described["launcher_verified"] is True
    assert described["admission_3s"] == "NOT_MEASURED"
    # One-shot: the same root is never reused, overwritten or proposed again.
    refused(prep, "materialize", prep.root, TASK, code="PREPARE_ROOT")
    refused(prep, "proposal", prep.root, TASK, code="PREPARE_ROOT")
    assert (prep.root / "attempt.json").read_bytes() == raw
    assert [path.name for path in prep.root.iterdir()] == ["attempt.json"]


def missing_launcher(prep: Any, monkeypatch: Any) -> None:
    monkeypatch.setitem(prep.namespace, "PYTHON", prep.launcher.parent / "absent.exe")


def changed_launcher(prep: Any, monkeypatch: Any) -> None:
    monkeypatch.setitem(prep.namespace, "PYTHON_SHA", "0" * 64)


def oversized_launcher(prep: Any, monkeypatch: Any) -> None:
    monkeypatch.setitem(prep.namespace, "PYTHON_LIMIT", 4)


def reparse_launcher(prep: Any, monkeypatch: Any) -> None:
    fake_lstat(monkeypatch, prep.launcher, stat.S_IFREG | 0o600, 0x400)


LAUNCHERS: dict[str, Callable[[Any, Any], None]] = {
    "missing": missing_launcher,
    "changed": changed_launcher,
    "oversized": oversized_launcher,
    "reparse": reparse_launcher,
}


@pytest.mark.parametrize("name", sorted(LAUNCHERS))
def test_launcher_pin_refused_before_mkdir(prep: Any, monkeypatch: Any, name: str) -> None:
    LAUNCHERS[name](prep, monkeypatch)
    refused(prep, "materialize", prep.root, TASK, code="PREPARE_LAUNCHER")
    assert not prep.root.exists()


def test_exporter_pin_refused(prep: Any, monkeypatch: Any) -> None:
    monkeypatch.setitem(prep.namespace, "EXPORTER_SHA", "0" * 64)
    refused(prep, "state_for", TASK, code="PREPARE_SOURCE")
    refused(prep, "proposal", prep.root, TASK, code="PREPARE_SOURCE")
    refused(prep, "materialize", prep.root, TASK, code="PREPARE_SOURCE")
    assert not prep.root.exists()


def test_captured_source_pin_change_refused_before_write(prep: Any, monkeypatch: Any) -> None:
    original = prep.namespace["load"]

    def load() -> Any:
        exporter, d = original()
        d["pins"]["docs/poc/pg16_shell_run.py"] = "0" * 64
        return exporter, d

    monkeypatch.setitem(prep.namespace, "load", load)
    # A proposal only describes; the source recheck guards materialization.
    assert prep.module["proposal"](prep.root, TASK)["materialized"] is False
    refused(prep, "materialize", prep.root, TASK, code="PREPARE_SOURCE")
    assert not prep.root.exists()


def test_exporter_changed_between_load_and_write_refused(prep: Any, monkeypatch: Any) -> None:
    original = prep.namespace["regular"]
    reads: list[Any] = []

    def regular(path: Any, maximum: Any, code: Any) -> Any:
        raw = original(path, maximum, code)
        if path.name == "pg16_shell_export.py":
            reads.append(path)
            if len(reads) > 1:
                return raw + b"\n"
        return raw

    monkeypatch.setitem(prep.namespace, "regular", regular)
    refused(prep, "materialize", prep.root, TASK, code="PREPARE_SOURCE")
    assert len(reads) == 2 and not prep.root.exists()


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


def test_short_write_leaves_consumed_root_without_retry(prep: Any, monkeypatch: Any) -> None:
    original = Path.open

    def opener(self: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        stream = original(self, mode, *args, **kwargs)
        return Short(stream) if self.name == "attempt.json" and mode == "xb" else stream

    monkeypatch.setattr(Path, "open", opener)
    refused(prep, "materialize", prep.root, TASK, code="PREPARE_IO")
    raw = canonical(prep.module["state_for"](TASK))
    assert (prep.root / "attempt.json").read_bytes() == raw[:-1]
    monkeypatch.setattr(Path, "open", original)
    refused(prep, "materialize", prep.root, TASK, code="PREPARE_ROOT")
    assert (prep.root / "attempt.json").read_bytes() == raw[:-1]


def test_fsync_failure_is_closed_and_not_cleaned(prep: Any, monkeypatch: Any) -> None:
    def broken(_descriptor: int) -> None:
        raise OSError("private-detail")

    monkeypatch.setitem(prep.namespace, "os", SimpleNamespace(fsync=broken))
    caught = refused(prep, "materialize", prep.root, TASK, code="PREPARE_IO")
    assert "private-detail" not in str(caught.value)
    assert [path.name for path in prep.root.iterdir()] == ["attempt.json"]


def test_readback_mismatch_never_returns_descriptor(prep: Any, monkeypatch: Any) -> None:
    original = prep.namespace["regular"]

    def regular(path: Any, maximum: Any, code: Any) -> Any:
        if path.name == "attempt.json":
            return b"{}\n"
        return original(path, maximum, code)

    monkeypatch.setitem(prep.namespace, "regular", regular)
    refused(prep, "materialize", prep.root, TASK, code="PREPARE_CHANGED")
    assert (prep.root / "attempt.json").is_file()


def test_intruder_entry_after_write_is_refused(prep: Any, monkeypatch: Any) -> None:
    original = Path.open

    def opener(self: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if self.name == "attempt.json" and mode == "xb":
            (self.parent / "intruder.txt").mkdir()
        return original(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opener)
    refused(prep, "materialize", prep.root, TASK, code="PREPARE_CHANGED")
    assert sorted(path.name for path in prep.root.iterdir()) == ["attempt.json", "intruder.txt"]


class Stream:
    """Fake open() stream recording every requested read size."""

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

    def unbounded() -> bytes:
        raise AssertionError("unbounded read_bytes")

    path = SimpleNamespace(
        lstat=lambda: SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_size=size),
        open=lambda _mode: stream,
        read_bytes=unbounded,
    )
    return path, stream


def test_grown_file_is_changed_without_unbounded_read(prep: Any) -> None:
    path, stream = fake_file(1, b"xx")
    with pytest.raises(prep.module["PrepareError"]) as caught:
        prep.module["regular"](path, 64, "PREPARE_SOURCE")
    assert caught.value.args == ("PREPARE_CHANGED",)
    assert stream.requested == [65]


def test_oversized_growth_reads_at_most_limit_plus_one(prep: Any) -> None:
    path, stream = fake_file(4, b"x" * 4096)
    with pytest.raises(prep.module["PrepareError"]) as caught:
        prep.module["regular"](path, 4, "PREPARE_SOURCE")
    assert caught.value.args == ("PREPARE_SIZE",)
    assert stream.requested == [5]


def test_unknown_internal_failure_is_closed(prep: Any, monkeypatch: Any) -> None:
    def broken(*_args: Any) -> Any:
        raise ValueError("private-detail")

    monkeypatch.setitem(prep.namespace, "descriptor", broken)
    caught = refused(prep, "proposal", prep.root, TASK, code="PREPARE_INTERNAL")
    assert "private-detail" not in str(caught.value)
    assert not prep.root.exists()
