"""Preparer admission/materialization only. No application, Docker or native process."""

import hashlib
import json
import runpy
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
TASK = "a" * 32


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/pg16_public_prepare.py"))


@pytest.fixture
def bound(module: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    definitions = module["entry"]()
    monkeypatch.setitem(module["state_for"].__globals__, "entry", lambda: definitions)
    monkeypatch.setitem(definitions["R"], "HOME", tmp_path)
    pinned = definitions["R"]["pinned"]
    reads = []

    def read(path: Path, digest: str, maximum: int = 65536) -> bytes:
        if path == module["PYTHON"]:
            assert digest == module["PYTHON_SHA"] and maximum == 1048576
            reads.append(path)
            return b"fake-public-launcher"
        value = pinned(path, digest, maximum)
        assert isinstance(value, bytes)
        return value

    monkeypatch.setitem(definitions["R"], "pinned", read)
    parent = tmp_path / "AppData/Local/Temp"
    parent.mkdir(parents=True)
    root = parent / ("maskgw-pg16-public-20261030-" + "b" * 32)
    return definitions, root, reads


def test_state_has_exact_entry_schema_and_blueprint_without_image_or_effects(module):
    state = module["state_for"](TASK)
    assert set(state) == {
        "kind",
        "task",
        "phase",
        "invoked",
        "program_sha256",
        "v2_sha256",
        "host_sha256",
        "entry_sha256",
        "pins",
        "pg_pins",
        "image",
        "create_measurement",
    }
    assert state["phase"] == "FRESH" and state["invoked"] is False
    assert (
        state["entry_sha256"]
        == hashlib.sha256((REPO / "docs/poc/pg16_public_run.py").read_bytes()).hexdigest()
    )
    definitions = module["entry"]()
    profile = definitions["H"]["captured"](*definitions["H"]["SOURCES"]["profile"])[0]
    assert state["create_measurement"] == profile["blueprint"](TASK)[1]
    assert state["image"] == profile["IMAGE"] and state["kind"] == "maskgw-pg16-public-v1"


@pytest.mark.parametrize("task", ["", "a" * 31, "A" * 32, "a" * 33, True, None, "../" + "a" * 29])
def test_invalid_task_refused_before_state(module, task):
    with pytest.raises(RuntimeError, match="TASK"):
        module["state_for"](task)


def test_command_is_explicit_isolated_no_shell_or_root_creation(module, bound):
    _, root, reads = bound
    argv = module["command_for"](root)
    assert argv == (str(module["PYTHON"]), "-I", "-B", str(module["ENTRY"]), str(root))
    assert not root.exists() and reads == [module["PYTHON"]]


@pytest.mark.parametrize(
    "suffix",
    [
        "wrong",
        "maskgw-pg16-public-20261030-" + "A" * 32,
        "maskgw-oracle9-t4-v2-20261029-" + "b" * 32,
    ],
)
def test_wrong_root_or_old_attempt_name_is_refused(module, bound, suffix):
    _, root, _ = bound
    bad = root.with_name(suffix)
    with pytest.raises(RuntimeError, match="ROOT"):
        module["command_for"](bad)
    assert not bad.exists()


def test_nested_root_is_refused(module, bound):
    _, root, _ = bound
    with pytest.raises(RuntimeError, match="ROOT"):
        module["command_for"](root / root.name)


def test_materialize_is_one_shot_and_returns_exact_bytes_and_hash(module, bound):
    definitions, root, _ = bound
    value = module["materialize"](root, TASK)
    raw = (root / "attempt.json").read_bytes()
    assert {p.name for p in root.iterdir()} == {"attempt.json"}
    assert raw == definitions["R"]["json_bytes"](module["state_for"](TASK))
    assert (
        hashlib.sha256(raw).hexdigest() == value["state_sha256"]
        and len(raw) == value["state_bytes"]
    )
    assert json.loads(raw)["invoked"] is False
    with pytest.raises(FileExistsError):
        module["materialize"](root, TASK)
    assert (root / "attempt.json").read_bytes() == raw


def test_entry_pin_failure_never_executes_changed_file(module, tmp_path, monkeypatch):
    bad = tmp_path / "changed_entry.py"
    bad.write_bytes(b"raise AssertionError('must not execute')\n")
    monkeypatch.setitem(module["entry"].__globals__, "ENTRY", bad)
    with pytest.raises(RuntimeError, match="ENTRY_PIN"):
        module["entry"]()


def test_existing_root_content_is_preserved(module, bound):
    _, root, _ = bound
    root.mkdir()
    (root / "notes.txt").write_bytes(b"public-preserved")
    with pytest.raises(FileExistsError):
        module["materialize"](root, TASK)
    assert (root / "notes.txt").read_bytes() == b"public-preserved"


def test_persistence_failure_never_returns_success_or_invokes_main(module, bound, monkeypatch):
    _, root, _ = bound

    def fail(_fd: int) -> None:
        raise OSError("synthetic-persistence-failure")

    monkeypatch.setattr(module["os"], "fsync", fail)
    with pytest.raises(OSError):
        module["materialize"](root, TASK)
    assert root.is_dir() and {p.name for p in root.iterdir()} == {"attempt.json"}
    assert json.loads((root / "attempt.json").read_bytes())["invoked"] is False
