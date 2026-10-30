"""Known unstarted CID recovery, with fake CLI only."""

import asyncio
import json
import runpy
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    module = runpy.run_path(str(REPO / "docs/poc/oracle9_w1_restore.py"))
    run = module["library"]()
    state = module["witness"](run, "attempt.json")
    host = run["Host"](tmp_path, state)
    raw = (REPO / "docs/poc/evidence/oracle9-w1-run-attempt1-inspect-20261027.json").read_bytes()
    model: dict[str, Any] = {"fault": None, "effects": []}

    async def cli(label, *args, **kwargs):
        assert kwargs == (
            {"cleanup": True, "timeout": 3} if label == "recovery-inventory" else {"cleanup": True}
        )
        model["effects"].append((label, args))
        if label == "recovery-inspect":
            return (
                (1, b"")
                if model["fault"] == "inspect"
                else (0, raw + (b" " if model["fault"] == "changed" else b""))
            )
        if label == "recovery-rm":
            assert args == ("rm", module["CID"]) and "--force" not in args
            return (1 if model["fault"] == "rm" else 0), b"owned-id\n"
        if label in ("recovery-absent", "recovery-inventory"):
            return 0, b"unproven\n" if model["fault"] == label else b""
        raise AssertionError(label)

    async def restore():
        assert host.result["owned_cleanup"] is True and host.result["inventory_restored"] is True
        model["effects"].append(("restore", ()))
        host.result["desktop_restored"] = True

    monkeypatch.setattr(host, "cli", cli)
    monkeypatch.setattr(host, "restore_desktop", restore)
    return module, host, raw, model


def test_observed_three_own_labels_still_pass_original_full_security_profile(lab):
    module, host, raw, _ = lab
    info = json.loads(raw)[0]
    assert len(info["Config"]["Labels"]) == 3
    module["admit_container"](host, info, raw)


@pytest.mark.parametrize("fault", ["task", "id", "running", "pid", "status", "network", "command"])
def test_recovery_refuses_foreign_started_or_changed_profile(lab, fault):
    module, host, raw, _ = lab
    info = deepcopy(json.loads(raw)[0])
    if fault == "task":
        info["Config"]["Labels"]["maskgw.task"] = "foreign"
    elif fault == "id":
        info["Id"] = "f" * 64
    elif fault == "network":
        info["HostConfig"]["NetworkMode"] = "host"
    elif fault == "command":
        info["Config"]["Cmd"] = ["unexpected"]
    else:
        info["State"][{"running": "Running", "pid": "Pid", "status": "Status"}[fault]] = {
            "running": True,
            "pid": 9,
            "status": "exited",
        }[fault]
    with pytest.raises(RuntimeError):
        module["admit_container"](host, info, raw)


def test_recovery_removes_only_exact_stopped_cid_then_restores(lab):
    module, host, _, model = lab
    asyncio.run(module["recover"](host))
    labels = [label for label, _ in model["effects"]]
    assert labels == [
        "recovery-inspect",
        "recovery-rm",
        "recovery-absent",
        "recovery-inventory",
        "restore",
    ]
    assert host.result["desktop_restored"] is True


@pytest.mark.parametrize(
    "fault", ["inspect", "changed", "rm", "recovery-absent", "recovery-inventory"]
)
def test_failed_recovery_does_not_invent_absence_or_stop_desktop(lab, fault):
    module, host, _, model = lab
    model["fault"] = fault
    with pytest.raises(RuntimeError):
        asyncio.run(module["recover"](host))
    labels = [label for label, _ in model["effects"]]
    assert "restore" not in labels
    if fault in ("inspect", "changed"):
        assert "recovery-rm" not in labels
