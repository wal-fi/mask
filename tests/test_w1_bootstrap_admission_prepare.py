"""Public state materializer fakes only; never invokes a runner/Docker."""

import json
import runpy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_admission_prepare.py"))


def test_closed_state_is_accepted_by_diagnostic_and_never_reuses_t4(module, tmp_path, monkeypatch):
    ns = module["entry"]()
    state = module["state_for"]("a" * 32)
    assert state["kind"] == "maskgw-oracle9-admission-v1"
    assert state["entry_sha256"] == module["ENTRY_SHA"]
    assert state["diagnostic_pins"] == {ns["CORE_RELATIVE"]: ns["CORE_SHA"]}
    monkeypatch.setitem(ns["R"], "HOME", tmp_path)
    monkeypatch.setitem(module["state_for"].__globals__, "entry", lambda: ns)
    root = tmp_path / "AppData/Local/Temp" / ("maskgw-oracle9-admission-20261028-" + "b" * 32)
    root.parent.mkdir(parents=True)
    proof = module["materialize"](root, "a" * 32)
    assert {path.name for path in root.iterdir()} == {"attempt.json"}
    raw = (root / "attempt.json").read_bytes()
    assert proof["command"][1:3] == ["-I", "-B"]
    assert json.loads(raw)["invoked"] is False
    monkeypatch.setitem(
        ns["admit"].__globals__,
        "sys",
        SimpleNamespace(
            platform="win32",
            version_info=(3, 11, 3),
            flags=SimpleNamespace(isolated=1, dont_write_bytecode=1, optimize=0),
        ),
    )
    assert ns["admit"](root) == state
    with pytest.raises(FileExistsError):
        module["materialize"](root, "a" * 32)
    assert (root / "attempt.json").read_bytes() == raw


@pytest.mark.parametrize("task", [None, 123, "", "x" * 32, "a" * 31])
def test_bad_task_cannot_build_state(module, task):
    with pytest.raises(RuntimeError, match="TASK"):
        module["state_for"](task)


@pytest.mark.parametrize("name", ["maskgw-oracle9-t4-20261028-" + "a" * 32, "other"])
def test_wrong_root_cannot_build_command(module, tmp_path, name):
    root = tmp_path / name
    with pytest.raises(RuntimeError, match="ROOT"):
        module["command_for"](root)
    assert not root.exists()
