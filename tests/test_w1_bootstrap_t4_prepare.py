"""Public files only; no T4 invocation, native thread/process or Docker."""

import json
import runpy
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_t4_prepare.py"))


def test_state_is_closed_and_all_seven_create_measurements_are_fixed(module):
    state = module["state_for"]("a" * 32)
    assert state["phase"] == "FRESH" and state["invoked"] is False
    assert len(state["pins"]) == 6 and len(state["t4_pins"]) == 5
    assert state["entry_sha256"] == module["ENTRY_SHA"]
    assert set(state["create_measurements"]) == {
        "normal",
        "retain",
        "bad-ready",
        "blackhole",
        "flood",
        "cancel-start",
        "reader-negative",
    }
    assert all(value["margin_chars"] > 12000 for value in state["create_measurements"].values())


@pytest.mark.parametrize("task", ["", "bad", "a" * 31, "G" * 32, 123])
def test_bad_task_refused(module, task):
    with pytest.raises(RuntimeError, match="TASK"):
        module["state_for"](task)


def test_public_materialization_never_invokes_and_refuses_reuse(module, tmp_path, monkeypatch):
    definitions = module["entry"]()
    monkeypatch.setitem(definitions["R"], "HOME", tmp_path)
    monkeypatch.setitem(module["materialize"].__globals__, "entry", lambda: definitions)
    root = tmp_path / "AppData/Local/Temp" / ("maskgw-oracle9-t4-20261028-" + "b" * 32)
    root.parent.mkdir(parents=True)
    result = module["materialize"](root, "a" * 32)
    assert {item.name for item in root.iterdir()} == {"attempt.json"}
    raw = (root / "attempt.json").read_bytes()
    state = json.loads(raw)
    assert state["invoked"] is False
    assert result["command"][1:3] == ["-I", "-B"]
    assert result["command"][-1] == str(root)
    assert result["state_bytes"] == len(raw)
    with pytest.raises(FileExistsError):
        module["materialize"](root, "a" * 32)
    assert (root / "attempt.json").read_bytes() == raw


@pytest.mark.parametrize("name", ["other", "maskgw-oracle9-t4-20261027-" + "a" * 32])
def test_wrong_root_refused_before_directory_creation(module, tmp_path, name):
    root = tmp_path / name
    with pytest.raises(RuntimeError, match="ROOT"):
        module["command_for"](root)
    assert not root.exists()
