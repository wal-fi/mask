"""Private public-executor fakes. Never invokes Docker, PS, native kill or a thread."""

import asyncio
import json
import runpy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_emergency.py"))


def executor(module: Any, monkeypatch: Any) -> tuple[Any, list[float], list[Any]]:
    bounded = (REPO / "docs/poc/run_linux_as_probe.py").read_bytes()
    identity = (REPO / "docs/poc/w1_bootstrap_identity.py").read_bytes()
    owner = module["PublicEmergency"](bounded, identity)
    clock = [0.0]
    pins: list[Any] = []
    api = module["PublicEmergency"].invoke.__globals__
    monkeypatch.setitem(api, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setitem(api, "cleanup_pins", lambda: pins.append(True))
    owner.begin()
    return owner, clock, pins


@pytest.mark.parametrize("name", ["CID_ABSENCE", "CID_INSPECT", "CID_KILL", "CID_REMOVE"])
def test_only_fixed_public_cid_commands_have_own_loop_and_pins(module, monkeypatch, name):
    owner, _clock, pins = executor(module, monkeypatch)
    target = module["Target"]("c" * 64)
    calls = []

    async def bounded(args, *, limit, timeout):
        calls.append((args, limit, timeout, asyncio.get_running_loop()))
        return 0, b"public-output"

    owner._bounded["bounded"] = bounded
    assert owner.invoke(getattr(module["Action"], name), target) == b"public-output"
    args, limit, timeout, loop = calls[0]
    assert args[:3] == [module["CLI"], "--context", "desktop-linux"]
    expected = {"CID_KILL": 4.0, "CID_REMOVE": 8.0}.get(name, 2.0)
    assert timeout == expected and limit <= 2097152 and loop.is_closed()
    assert pins == [True] and owner.metadata()["steps"] == [{"action": name, "outcome": "OK"}]
    assert "public-output" not in str(owner.metadata())


def test_every_instance_owns_captured_namespaces_and_environment_globals(module, monkeypatch):
    first, _, _ = executor(module, monkeypatch)
    second, _, _ = executor(module, monkeypatch)
    assert first._bounded is not second._bounded and first._identity is not second._identity
    assert first._bounded["environment"].__globals__ is first._bounded
    assert second._bounded["environment"].__globals__ is second._bounded
    first._bounded["marker"] = "not-shared"
    assert "marker" not in second._bounded


@pytest.mark.parametrize("failure", ["timeout", "output", "cleanup", "exit", "bytes", "late"])
def test_first_failure_is_sticky_and_never_logs_raw_output(module, monkeypatch, failure):
    owner, clock, pins = executor(module, monkeypatch)
    calls = []

    async def bounded(*_args, **_kwargs):
        calls.append(True)
        if failure == "timeout":
            raise TimeoutError("public-marker-must-not-escape")
        if failure == "output":
            raise owner._bounded["HostFault"]("OUTPUT_LIMIT")
        if failure == "cleanup":
            raise owner._bounded["HostFault"]("CLI_CLEANUP")
        if failure == "exit":
            return 1, b"public-marker-must-not-escape"
        if failure == "bytes":
            return 0, "not-bytes"
        clock[0] = 46.0
        return 0, b"public-marker-must-not-escape"

    owner._bounded["bounded"] = bounded
    with pytest.raises(module["EmergencyError"], match=r"^COMMAND$") as caught:
        owner.invoke(module["Action"].CID_INSPECT, module["Target"]("c" * 64))
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    with pytest.raises(module["EmergencyError"], match="INPUT"):
        owner.invoke(module["Action"].CID_INSPECT, module["Target"]("c" * 64))
    assert calls == pins == [True]
    assert "public-marker-must-not-escape" not in str(owner.metadata())


def test_exhausted_budget_after_pin_work_never_spawns(module, monkeypatch):
    owner, clock, pins = executor(module, monkeypatch)
    clock[0] = 34.5  # 10.5s left in the calibrated45s budget, before the pin work

    def expired_pins():
        pins.append(True)
        clock[0] += 0.75

    monkeypatch.setitem(module["PublicEmergency"].invoke.__globals__, "cleanup_pins", expired_pins)
    with pytest.raises(module["EmergencyError"], match="BUDGET"):
        owner.invoke(module["Action"].CID_INSPECT, module["Target"]("c" * 64))
    assert pins == [True] and owner.metadata()["failed"]


def test_pin_failure_executes_nothing(module, monkeypatch):
    owner, _, _ = executor(module, monkeypatch)

    def denied():
        raise OSError("public-marker-must-not-escape")

    monkeypatch.setitem(module["PublicEmergency"].invoke.__globals__, "cleanup_pins", denied)
    with pytest.raises(module["EmergencyError"], match=r"^PIN$") as caught:
        owner.invoke(module["Action"].CID_INSPECT, module["Target"]("c" * 64))
    assert caught.value.__cause__ is None and caught.value.__context__ is None


def test_main_loop_cannot_be_used_as_the_emergency_executor(module, monkeypatch):
    owner, _, pins = executor(module, monkeypatch)

    async def scenario() -> None:
        with pytest.raises(module["EmergencyError"], match="INPUT"):
            owner.invoke(module["Action"].CID_INSPECT, module["Target"]("c" * 64))
        assert pins == []

    asyncio.run(scenario())


@pytest.mark.parametrize("status", ["KILLED", "ABSENT", "IDENTITY_MISMATCH", "ERROR"])
def test_ps_reply_requires_closed_parser_and_successful_status(module, monkeypatch, status):
    owner, _, pins = executor(module, monkeypatch)
    created = 134375857978266391
    target = module["Target"]("c" * 64, 123, created)

    async def bounded(args, *, limit, timeout):
        assert args[0] == module["SHELL"] and args[-2] == "-EncodedCommand"
        assert limit == 512 and timeout == 4.0
        observed = str(created + 1 if status == "IDENTITY_MISMATCH" else created)
        return 0, json.dumps({"status": status, "pid": 123, "observed_filetime": observed}).encode()

    owner._bounded["bounded"] = bounded
    if status in ("KILLED", "ABSENT"):
        assert owner.invoke(module["Action"].CLI_KILL, target)
    else:
        with pytest.raises(module["EmergencyError"], match="COMMAND"):
            owner.invoke(module["Action"].CLI_KILL, target)
    assert pins == [True]


@pytest.mark.parametrize("duration", [6.3, 9.0])
def test_remove_budget_covers_measured_baseline_but_stays_finite(module, monkeypatch, duration):
    owner, clock, _ = executor(module, monkeypatch)

    async def bounded(_args, *, limit, timeout):
        assert limit == 65536
        clock[0] += min(duration, timeout)
        if duration > timeout:
            raise TimeoutError("public-marker-must-not-escape")
        return 0, b"c" * 64 + b"\n"

    owner._bounded["bounded"] = bounded
    if duration == 6.3:
        assert owner.invoke(module["Action"].CID_REMOVE, module["Target"]("c" * 64))
    else:
        with pytest.raises(module["EmergencyError"], match="COMMAND"):
            owner.invoke(module["Action"].CID_REMOVE, module["Target"]("c" * 64))


def test_slow_pin_work_aborts_before_a_command(module, monkeypatch):
    owner, clock, _ = executor(module, monkeypatch)

    def slow():
        clock[0] += 1.1

    monkeypatch.setitem(module["PublicEmergency"].invoke.__globals__, "cleanup_pins", slow)
    with pytest.raises(module["EmergencyError"], match="PIN"):
        owner.invoke(module["Action"].CID_INSPECT, module["Target"]("c" * 64))


def test_calibrated_worst_sequence_keeps_the_final_ten_second_reserve(module, monkeypatch):
    owner, clock, pins = executor(module, monkeypatch)
    target = module["Target"]("c" * 64, 123, 134375857978266391)

    def measured_pins():
        pins.append(True)
        clock[0] += 1.0  # accepted per-call ceiling, above observed0.3-0.4s

    monkeypatch.setitem(module["PublicEmergency"].invoke.__globals__, "cleanup_pins", measured_pins)

    async def bounded(args, *, limit, timeout):
        assert limit <= 2097152
        clock[0] += timeout  # every command consumes its entire declared cap
        if args[0] == module["SHELL"]:
            return 0, json.dumps(
                {"status": "KILLED", "pid": 123, "observed_filetime": str(target.filetime)}
            ).encode()
        return 0, b"public-output"

    owner._bounded["bounded"] = bounded
    for name in (
        "CLI_KILL",
        "CID_ABSENCE",
        "CID_INSPECT",
        "CID_KILL",
        "CID_INSPECT",
        "CID_REMOVE",
        "CID_ABSENCE",
    ):
        owner.invoke(getattr(module["Action"], name), target)
    assert len(pins) == 7 and clock[0] == 31.0
    assert owner._end - clock[0] == 14.0  # 10s cleanup reserve plus4s margin
