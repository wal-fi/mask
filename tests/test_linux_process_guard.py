"""Deterministic guard tests. No actual process limits or Linux syscall here."""

from __future__ import annotations

import ast
import sys
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from maskgw.runtime import linux_guard as guard

MIB = 1024 * 1024


class FakeSystem:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.identity = 123
        self.parent = 1
        self.valid = True
        self.limits: dict[str, tuple[int, int]] = {"as": (-1, -1), "core": (-1, -1)}
        self.dump = 1
        self.death = 0
        self.fault_at: str | None = None
        self.hook: Callable[[str], None] = lambda _label: None
        self.virtual_bytes = 16 * MIB
        self.infinite = -1

    def event(self, label: str) -> None:
        self.events.append(label)
        self.hook(label)
        if label == self.fault_at:
            raise OSError("PRIVATE_OS_MARKER")

    def pid(self) -> int:
        self.event("pid")
        return self.identity

    def parent_pid(self) -> int:
        self.event("ppid")
        return self.parent

    def address_size(self) -> int:
        self.event("vms")
        return self.virtual_bytes

    def infinity(self) -> int:
        return self.infinite

    def profile(self) -> bool:
        self.event("profile")
        return self.valid

    def get_limit(self, name: str) -> tuple[int, int]:
        self.event("get_" + name)
        return self.limits[name]

    def set_limit(self, name: str, value: tuple[int, int]) -> None:
        self.event("set_" + name)
        self.limits[name] = value

    def set_prctl(self, option: int, value: int) -> None:
        self.event("prctl_" + str(option))
        if option == 4:
            self.dump = value
        else:
            self.death = value

    def dumpable(self) -> int:
        self.event("get_dump")
        return self.dump

    def death_signal(self) -> int:
        self.event("get_death")
        return self.death


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeSystem:
    system = FakeSystem()
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(guard, "_LinuxSystem", lambda: system)
    return system


def protect(**changes: Any) -> guard.GuardFacts:
    args: dict[str, Any] = {
        "role": guard.ProcessRole.WORKER,
        "address_limit_bytes": 256 * MIB,
        "expected_parent_pid": 1,
    }
    return guard.protect_process(**(args | changes))


def test_worker_one_way_hard_limits_and_immutable_facts(fake):
    facts = protect()
    assert facts.pid == 123 and facts.parent_pid == 1
    assert facts.core == (0, 0) and facts.dumpable == 0 and facts.parent_death_signal == 9
    assert fake.limits["as"] == (256 * MIB, 256 * MIB)
    assert fake.events.index("set_as") < fake.events.index("get_dump")
    with pytest.raises(FrozenInstanceError):
        setattr(facts, "pid", 9)  # noqa: B010 - deliberate mutation of a frozen record
    with pytest.raises(TypeError):
        bool(facts)
    assert "123" not in repr(facts)


def test_controller_requires_pid1_and_no_parent_death_signal(fake):
    fake.identity = 1
    fake.parent = 0
    result = protect(role=guard.ProcessRole.CONTROLLER, expected_parent_pid=None)
    assert result.pid == 1 and result.parent_death_signal == 0
    fake.identity = 12
    with pytest.raises(guard.ProcessGuardError) as exc:
        protect(role=guard.ProcessRole.CONTROLLER, expected_parent_pid=None)
    assert exc.value.category is guard.GuardFailure.PARENT


@pytest.mark.parametrize(
    "changes",
    [
        {"role": "WORKER"},
        {"address_limit_bytes": True},
        {"address_limit_bytes": 0},
        {"address_limit_bytes": 64 * MIB - 1},
        {"address_limit_bytes": 4096 * MIB + 1},
        {"expected_parent_pid": None},
        {"expected_parent_pid": True},
        {"expected_parent_pid": 0},
        {"expected_parent_pid": 1 << 31},
        {"role": guard.ProcessRole.CONTROLLER, "expected_parent_pid": 1},
    ],
)
def test_invalid_inputs_have_no_system_access(fake, changes):
    with pytest.raises(guard.ProcessGuardError) as exc:
        protect(**changes)
    assert exc.value.category is guard.GuardFailure.INVALID and fake.events == []


@pytest.mark.parametrize("limit", [64 * MIB, 4096 * MIB])
def test_address_range_boundaries(fake, limit):
    assert protect(address_limit_bytes=limit).address_limit_bytes == limit
    assert fake.limits["as"] == (limit, limit)


def test_windows_refuses_before_backend_creation(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(guard, "_LinuxSystem", lambda: pytest.fail("backend created"))
    with pytest.raises(guard.ProcessGuardError) as exc:
        protect()
    assert exc.value.category is guard.GuardFailure.UNSUPPORTED


@pytest.mark.parametrize("limits", [(128 * MIB, -1), (-1, 128 * MIB), (128 * MIB, 512 * MIB)])
def test_never_increases_existing_limits(fake, limits):
    fake.limits["as"] = limits
    with pytest.raises(guard.ProcessGuardError) as exc:
        protect()
    assert exc.value.category is guard.GuardFailure.LIMIT
    assert not any(v.startswith("set_") for v in fake.events)


@pytest.mark.parametrize("when", ["before", "after_death", "final"])
def test_parent_death_races_fail_before_admission(fake, when):
    if when == "before":
        fake.parent = 2
    elif when == "after_death":
        fake.hook = lambda label: setattr(fake, "parent", 2) if label == "prctl_1" else None
    else:
        fake.hook = lambda label: setattr(fake, "parent", 2) if label == "get_death" else None
    with pytest.raises(guard.ProcessGuardError) as exc:
        protect()
    assert exc.value.category is guard.GuardFailure.PARENT


@pytest.mark.parametrize(
    "event",
    [
        "pid",
        "ppid",
        "profile",
        "get_as",
        "set_core",
        "set_as",
        "prctl_4",
        "prctl_1",
        "get_core",
        "get_dump",
        "get_death",
    ],
)
def test_os_faults_are_closed_and_chainless(fake, event):
    fake.fault_at = event
    with pytest.raises(guard.ProcessGuardError) as exc:
        protect()
    assert exc.value.category is guard.GuardFailure.SYSTEM
    assert exc.value.__cause__ is None and exc.value.__context__ is None
    assert "PRIVATE_OS_MARKER" not in str(exc.value) + repr(exc.value)


@pytest.mark.parametrize("target", ["profile", "core", "as", "dump", "death", "identity"])
def test_each_postcondition_is_required(fake, target):
    def change(label):
        if target == "profile" and label == "get_death":
            fake.valid = False
        elif target in {"core", "as"} and label == "prctl_1":
            fake.limits[target] = (-1, -1)
        elif target == "dump" and label == "get_dump":
            fake.dump = 1
        elif target == "death" and label == "get_death":
            fake.death = 0
        elif target == "identity" and label == "get_death":
            fake.identity = 999

    fake.hook = change
    with pytest.raises(guard.ProcessGuardError):
        protect()


def profile_fields() -> dict[str, str]:
    return {
        "Uid": "10001 10001 10001 10001",
        "Gid": "10001 10001 10001 10001",
        **dict.fromkeys(("CapEff", "CapPrm", "CapInh", "CapBnd", "CapAmb"), "00000000"),
        "NoNewPrivs": "1",
        "Seccomp": "2",
        "Threads": "1",
    }


@pytest.mark.parametrize("key", list(profile_fields()))
def test_kernel_profile_requires_every_field(key):
    fields = profile_fields()
    assert guard._profile_fields(fields)
    fields[key] = "0" if key in {"NoNewPrivs", "Seccomp", "Threads", "Uid", "Gid"} else "01"
    assert not guard._profile_fields(fields)


def test_status_parser_is_bounded_and_rejects_duplicate_keys():
    assert guard._status(b"Threads:\t1\n") == {"Threads": "1"}
    for data in (b"Threads: 1\nThreads: 1\n", b"x" * 32769):
        with pytest.raises(guard.ProcessGuardError):
            guard._status(data)


def test_no_operational_importer():
    root = Path(__file__).resolve().parents[1] / "src/maskgw"
    for path in root.rglob("*.py"):
        if path in (
            root / "runtime/linux_guard.py",
            root / "runtime/worker_process.py",
            root
            / "runtime/worker_session.py",  # checks trusted controller facts, no new guard call
        ):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert all(not alias.name.endswith("linux_guard") for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").endswith("linux_guard")
                assert all(alias.name != "linux_guard" for alias in node.names)


@pytest.mark.parametrize("current", [256 * MIB, 256 * MIB - 8 * MIB])
def test_current_address_space_and_bootstrap_margin_checked_before_mutation(fake, current):
    fake.virtual_bytes = current
    with pytest.raises(guard.ProcessGuardError) as exc:
        protect()
    assert exc.value.category is guard.GuardFailure.LIMIT
    assert not any(v.startswith("set_") for v in fake.events)


def test_infinity_is_the_platform_constant(fake):
    fake.infinite = -(1 << 63)
    fake.limits["as"] = (fake.infinite, fake.infinite)
    assert protect().address_limit_bytes == 256 * MIB
