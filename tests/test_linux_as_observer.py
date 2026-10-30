"""Host observer guards with fake Docker/processes only; no daemon on import."""

from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "docs/poc/run_linux_as_probe.py"
SPEC = importlib.util.spec_from_file_location("linux_as_observer", SOURCE)
assert SPEC is not None and SPEC.loader is not None
HOST: Any = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOST)
IMAGE = "python@sha256:" + "a" * 64
CID = "b" * 64
MIB = 1024 * 1024


def profile(source: Path) -> dict[str, Any]:
    return {
        "Id": CID,
        "Name": "/test-baseline",
        "Config": {
            "Image": IMAGE,
            "Labels": {"maskgw.task": "task", "maskgw.source-sha256": "sha"},
            "User": "65534:65534",
            "Entrypoint": ["python"],
            "Healthcheck": {"Test": ["NONE"]},
            "Cmd": ["-I", "-B", "/probe.py", "--case", "baseline"],
        },
        "Mounts": [
            {"Type": "bind", "Source": str(source), "Destination": "/probe.py", "RW": False}
        ],
        "HostConfig": {
            "Memory": 192 * MIB,
            "MemorySwap": 192 * MIB,
            "NanoCpus": 1_000_000_000,
            "ShmSize": MIB,
            "PidsLimit": 16,
            "ReadonlyRootfs": True,
            "Privileged": False,
            "NetworkMode": "none",
            "IpcMode": "private",
            "CgroupnsMode": "private",
            "Init": False,
            "RestartPolicy": {"Name": "no"},
            "LogConfig": {"Type": "none"},
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
            "Ulimits": [
                {"Name": "core", "Soft": 0, "Hard": 0},
                {"Name": "nofile", "Soft": 64, "Hard": 64},
            ],
        },
    }


def validate(info: dict[str, Any], source: Path) -> None:
    HOST.validate_inspect(
        info, image=IMAGE, task="task", source_hash="sha", source=source, name="test-baseline"
    )


def test_exact_profile_is_accepted_without_running_anything(tmp_path):
    validate(profile(tmp_path / "probe.py"), tmp_path / "probe.py")


@pytest.mark.parametrize(
    "key,value",
    [
        ("Memory", 0),
        ("MemorySwap", -1),
        ("PidsLimit", 0),
        ("NanoCpus", True),
        ("Privileged", True),
        ("ReadonlyRootfs", False),
        ("NetworkMode", "host"),
        ("IpcMode", "host"),
        ("PidMode", "host"),
        ("UTSMode", "host"),
        ("Init", True),
        ("CapAdd", ["SYS_ADMIN"]),
        ("SecurityOpt", []),
        ("LogConfig", {"Type": "json-file"}),
    ],
)
def test_profile_drift_is_rejected_before_start(tmp_path, key, value):
    source = tmp_path / "probe.py"
    info = profile(source)
    info["HostConfig"][key] = value
    with pytest.raises(HOST.HostFault):
        validate(info, source)


def test_mount_cannot_escape_the_single_readonly_file(tmp_path):
    source = tmp_path / "probe.py"
    for change in (
        {"Source": str(tmp_path)},
        {"RW": True},
        {"Destination": "/var/run/docker.sock"},
    ):
        info = profile(source)
        info["Mounts"][0].update(change)
        with pytest.raises(HOST.HostFault):
            validate(info, source)


def test_foreign_container_is_not_a_cleanup_target(tmp_path):
    source = tmp_path / "probe.py"
    for change in ({"maskgw.task": "foreign"}, {"maskgw.source-sha256": "changed"}):
        info = profile(source)
        info["Config"]["Labels"].update(change)
        with pytest.raises(HOST.HostFault):
            validate(info, source)


def test_profile_drift_removed_by_owned_id_without_start(tmp_path, monkeypatch):
    observer = HOST.Observer("not-called", IMAGE, tmp_path)
    calls: list[str] = []

    async def fake_cli(*args: str, **_kwargs: Any) -> tuple[int, bytes]:
        calls.append(args[0])
        if args[0] == "create":
            return 0, CID.encode() + b"\n"
        return 0, b""

    async def fake_inspect(_target: str) -> dict[str, Any]:
        pending = json.loads((tmp_path / "pending.json").read_bytes())
        assert pending["id"] == CID  # persisted before even first inspect
        info = profile(observer.source)
        info["Name"] = "/maskgw-as-" + observer.task[-12:] + "-baseline"
        info["Config"]["Labels"] = {
            "maskgw.task": observer.task,
            "maskgw.source-sha256": observer.source_hash,
        }
        info["HostConfig"]["Memory"] = 0  # owned, but must not start
        info["State"] = {"Running": False, "Pid": 0}
        return info

    monkeypatch.setattr(observer, "cli", fake_cli)
    monkeypatch.setattr(observer, "inspect", fake_inspect)
    result = asyncio.run(observer.case("baseline"))
    assert "start" not in calls and "rm" in calls
    assert result["container_id"] == CID and result["cleanup_confirmed"]
    assert result["outcome"] == "inconclusive"
    pending = json.loads((tmp_path / "pending.json").read_bytes())
    assert pending["id"] == CID and pending["phase"] == "removed"


def test_identity_rejects_wrong_exact_id_even_with_matching_labels(tmp_path):
    with pytest.raises(HOST.HostFault):
        HOST.validate_identity(
            profile(tmp_path / "probe.py"),
            task="task",
            source_hash="sha",
            name="test-baseline",
            container_id="c" * 64,
        )


def test_report_duplicate_keys_rejected():
    with pytest.raises(HOST.HostFault):
        json.loads('{"outcome":"fail","outcome":"imposed"}', object_pairs_hook=HOST.unique_pairs)


def test_unpinned_image_refused_before_artifact_copy(tmp_path):
    with pytest.raises(HOST.HostFault):
        HOST.Observer("not-called", "python:latest", tmp_path)
    assert not list(tmp_path.iterdir())


def test_watchdog_close_error_cannot_bypass_container_cleanup(tmp_path, monkeypatch):
    observer = HOST.Observer("not-called", IMAGE, tmp_path)
    calls = []

    class BadWatchdog:
        def __init__(self, *_args):
            self.thread = type("Thread", (), {"ident": None})()
            self.container_id = None
            self.fired = type("Event", (), {"is_set": lambda _self: False})()

        def start(self):
            self.thread.ident = 1

        def close(self):
            raise HOST.HostFault("WATCHDOG_CLEANUP")

    monkeypatch.setattr(HOST, "Watchdog", BadWatchdog)

    async def fake_cli(*args, **_kwargs):
        calls.append(args[0])
        if args[0] == "create":
            return 0, CID.encode() + b"\n"
        if args[0] == "start":
            return 0, json.dumps(
                {
                    "case": "baseline",
                    "outcome": "normal",
                    "total_memory_contained": False,
                    "cleanup_confirmed": True,
                    "final_inventory": [1],
                }
            ).encode()
        return 0, b""

    async def fake_inspect(_target):
        info = profile(observer.source)
        info["Name"] = "/maskgw-as-" + observer.task[-12:] + "-baseline"
        info["Config"]["Labels"] = {
            "maskgw.task": observer.task,
            "maskgw.source-sha256": observer.source_hash,
        }
        info["State"] = {"Running": False, "Pid": 0, "ExitCode": 0, "OOMKilled": False}
        return info

    monkeypatch.setattr(observer, "cli", fake_cli)
    monkeypatch.setattr(observer, "inspect", fake_inspect)
    result = asyncio.run(observer.case("baseline"))
    assert "rm" in calls
    assert result["container_cleanup_confirmed"]
    assert not result["cleanup_confirmed"] and result["outcome"] == "inconclusive"


def test_bounded_capture_caps_output_even_if_process_already_exited(monkeypatch):
    class Stream:
        def __init__(self) -> None:
            self.parts = iter([b"x" * 1024, b"y" * 1024, b""])

        async def read(self, _size):
            return next(self.parts)

    class Process:
        returncode = 0

        def __init__(self) -> None:
            self.stdout = Stream()

        async def wait(self):
            return 0

        def kill(self):
            raise AssertionError("already exited")

    async def fake_spawn(*_args, **_kwargs):
        return Process()

    monkeypatch.setattr(HOST.asyncio, "create_subprocess_exec", fake_spawn)
    with pytest.raises(HOST.HostFault) as caught:
        asyncio.run(HOST.bounded(["not-called"], limit=1024))
    assert caught.value.category == "OUTPUT_LIMIT"


def test_docker_environment_does_not_forward_gateway_secrets(monkeypatch):
    monkeypatch.setenv("MASKGW_CATALOG_MASTER_KEY", "CANARY_NOT_FORWARDED")
    monkeypatch.setenv("PYTHONPATH", "CANARY_NOT_FORWARDED")
    result = HOST.environment()
    assert "MASKGW_CATALOG_MASTER_KEY" not in result and "PYTHONPATH" not in result
    assert "CANARY_NOT_FORWARDED" not in str(result)


def test_profile_fixture_is_not_mutated(tmp_path):
    source = tmp_path / "probe.py"
    info = profile(source)
    before = copy.deepcopy(info)
    validate(info, source)
    assert info == before


def test_command_drift_rejected(tmp_path):
    source = tmp_path / "probe.py"
    info = profile(source)
    info["Config"]["Cmd"] = ["-c", "print('not the probe')"]
    with pytest.raises(HOST.HostFault):
        validate(info, source)


def test_diagnostic_success_is_not_just_complete_or_zero_exit():
    good: dict[str, Any] = {
        "complete": True,
        "container_inventory_restored": True,
        "watchdog_closed": True,
        "deadline_exceeded": False,
        "source_unchanged": True,
        "observer_unchanged": True,
        "total_memory_contained": False,
        "cases": [
            {"case": name, "outcome": outcome, "cleanup_confirmed": True}
            for name, outcome in zip(
                HOST.CASES, ("normal", "control_ok", "imposed", "imposed"), strict=True
            )
        ],
    }
    assert HOST.diagnostic_success(good)
    for key in (
        "complete",
        "container_inventory_restored",
        "watchdog_closed",
        "source_unchanged",
        "observer_unchanged",
    ):
        bad = copy.deepcopy(good)
        bad[key] = False
        assert not HOST.diagnostic_success(bad)
    for failure in ("fail", "inconclusive", "incompatible"):
        bad = copy.deepcopy(good)
        bad["cases"][3]["outcome"] = failure
        assert not HOST.diagnostic_success(bad)
    bad = copy.deepcopy(good)
    bad["cases"][2]["cleanup_confirmed"] = False
    assert not HOST.diagnostic_success(bad)
