"""Private Linux process bootstrap; no caller, spawn, secrets or SQL.

Call in the final, single-threaded process AFTER exec and BEFORE any secret
delivery/read. Failure requires the owner to terminate/reap that process.
These local facts are not a registered containment profile or authorization.
An exec or credential change after this call invalidates its guarantee.
"""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass
from enum import StrEnum
from importlib import import_module
from pathlib import Path
from typing import Final, Protocol, cast

_MIB: Final = 1024 * 1024
_MIN_AS: Final = 64 * _MIB
_MAX_AS: Final = 4096 * _MIB
_MAX_PID: Final = (1 << 31) - 1
_UID: Final = 10001
_SIGKILL: Final = 9
_SET_DUMPABLE: Final = 4
_GET_DUMPABLE: Final = 3
_SET_PDEATHSIG: Final = 1
_GET_PDEATHSIG: Final = 2
_MAX_STATUS: Final = 32 * 1024
_BOOTSTRAP_HEADROOM: Final = 8 * _MIB  # Admission margin only, not an allocator bound.


class ProcessRole(StrEnum):
    CONTROLLER = "CONTROLLER"
    WORKER = "WORKER"


class GuardFailure(StrEnum):
    INVALID = "INVALID"
    UNSUPPORTED = "UNSUPPORTED"
    PROFILE = "PROFILE"
    PARENT = "PARENT"
    LIMIT = "LIMIT"
    SYSTEM = "SYSTEM"


class ProcessGuardError(Exception):
    def __init__(self, category: GuardFailure) -> None:
        self.category = category
        super().__init__("protecao de processo indisponivel")


@dataclass(frozen=True, slots=True, repr=False)
class GuardFacts:
    role: ProcessRole
    pid: int
    parent_pid: int
    address_limit_bytes: int
    observed_address_bytes: int
    dumpable: int
    parent_death_signal: int
    core: tuple[int, int]

    def __repr__(self) -> str:
        return "GuardFacts(<local bootstrap>)"

    def __bool__(self) -> bool:
        raise TypeError("protecao exige inspecao explicita")


class _System(Protocol):
    def pid(self) -> int: ...
    def parent_pid(self) -> int: ...
    def address_size(self) -> int: ...
    def infinity(self) -> int: ...
    def profile(self) -> bool: ...
    def get_limit(self, name: str) -> tuple[int, int]: ...
    def set_limit(self, name: str, value: tuple[int, int]) -> None: ...
    def set_prctl(self, option: int, value: int) -> None: ...
    def dumpable(self) -> int: ...
    def death_signal(self) -> int: ...


class _Resources(Protocol):
    RLIMIT_CORE: int
    RLIMIT_AS: int
    RLIM_INFINITY: int

    def getrlimit(self, resource: int) -> tuple[int, int]: ...
    def setrlimit(self, resource: int, value: tuple[int, int]) -> None: ...


class _PosixOS(Protocol):
    def getresuid(self) -> tuple[int, int, int]: ...
    def getresgid(self) -> tuple[int, int, int]: ...
    def getgroups(self) -> list[int]: ...


def _need(value: bool, category: GuardFailure) -> None:
    if not value:
        raise ProcessGuardError(category)


def _status(raw: bytes) -> dict[str, str]:
    _need(len(raw) <= _MAX_STATUS, GuardFailure.PROFILE)
    fields: dict[str, str] = {}
    for line in raw.decode("ascii").splitlines():
        key, separator, value = line.partition(":")
        if separator:
            _need(key not in fields, GuardFailure.PROFILE)
            fields[key] = value.strip()
    return fields


def _profile_fields(fields: dict[str, str]) -> bool:
    return (
        all(fields[k].split() == [str(_UID)] * 4 for k in ("Uid", "Gid"))
        and all(int(fields[k], 16) == 0 for k in ("CapEff", "CapPrm", "CapInh", "CapBnd", "CapAmb"))
        and fields["NoNewPrivs"] == "1"
        and fields["Seccomp"] == "2"
        and fields["Threads"] == "1"
    )


class _LinuxSystem:
    """No syscall on import; instantiated only after platform/input checks."""

    def __init__(self) -> None:
        import ctypes  # noqa: PLC0415 - no native binding before the platform gate

        self._ctypes = ctypes
        # Fixed trusted stdlib names, loaded only after the Linux platform gate.
        # Protocols let Windows type checking retain the actual Linux-only body.
        self._resource = cast(_Resources, import_module("resource"))
        self._posix = cast(_PosixOS, os)
        self._prctl = ctypes.CDLL(None, use_errno=True).prctl
        self._prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
        self._prctl.restype = ctypes.c_int

    def pid(self) -> int:
        return os.getpid()

    def parent_pid(self) -> int:
        return os.getppid()

    def address_size(self) -> int:
        with Path("/proc/self/status").open("rb") as stream:
            fields = _status(stream.read(_MAX_STATUS + 1))
        size = fields["VmSize"].split()
        # Fixed Linux proc VmSize format: decimal value followed by its unit.
        _need(len(size) == 2 and size[1] == "kB" and size[0].isdecimal(), GuardFailure.PROFILE)  # noqa: PLR2004
        return int(size[0]) * 1024

    def infinity(self) -> int:
        return self._resource.RLIM_INFINITY

    def profile(self) -> bool:
        with Path("/proc/self/status").open("rb") as stream:
            fields = _status(stream.read(_MAX_STATUS + 1))
        return (
            set(self._posix.getresuid()) == set(self._posix.getresgid()) == {_UID}
            and set(self._posix.getgroups()) <= {_UID}
            and threading.active_count() == 1
            and _profile_fields(fields)
        )

    def get_limit(self, name: str) -> tuple[int, int]:
        which = self._resource.RLIMIT_CORE if name == "core" else self._resource.RLIMIT_AS
        return self._resource.getrlimit(which)

    def set_limit(self, name: str, value: tuple[int, int]) -> None:
        which = self._resource.RLIMIT_CORE if name == "core" else self._resource.RLIMIT_AS
        self._resource.setrlimit(which, value)

    def set_prctl(self, option: int, value: int) -> None:
        _need(self._prctl(option, value, 0, 0, 0) == 0, GuardFailure.SYSTEM)

    def dumpable(self) -> int:
        return int(self._prctl(_GET_DUMPABLE, 0, 0, 0, 0))

    def death_signal(self) -> int:
        value = self._ctypes.c_int(-1)
        pointer = self._ctypes.cast(self._ctypes.pointer(value), self._ctypes.c_void_p).value
        _need(self._prctl(_GET_PDEATHSIG, pointer, 0, 0, 0) == 0, GuardFailure.SYSTEM)
        return value.value


def _inputs(role: ProcessRole, address: int, parent: int | None) -> None:
    _need(type(role) is ProcessRole, GuardFailure.INVALID)
    _need(type(address) is int and _MIN_AS <= address <= _MAX_AS, GuardFailure.INVALID)
    _need(
        (role is ProcessRole.CONTROLLER and parent is None)
        or (role is ProcessRole.WORKER and type(parent) is int and 0 < parent <= _MAX_PID),
        GuardFailure.INVALID,
    )


def _apply(system: _System, role: ProcessRole, address: int, parent: int | None) -> GuardFacts:
    pid, before = system.pid(), system.parent_pid()
    _need(system.profile(), GuardFailure.PROFILE)
    _need(
        (role is ProcessRole.CONTROLLER and pid == 1)
        or (role is ProcessRole.WORKER and pid != parent and before == parent),
        GuardFailure.PARENT,
    )
    old = system.get_limit("as")
    _need(all(value == system.infinity() or address <= value for value in old), GuardFailure.LIMIT)
    observed = system.address_size()
    _need(0 < observed < address - _BOOTSTRAP_HEADROOM, GuardFailure.LIMIT)
    system.set_limit("core", (0, 0))
    system.set_limit("as", (address, address))
    system.set_prctl(_SET_DUMPABLE, 0)
    expected_signal = _SIGKILL if role is ProcessRole.WORKER else 0
    system.set_prctl(_SET_PDEATHSIG, expected_signal)
    after = system.parent_pid()
    _need(role is ProcessRole.CONTROLLER or after == parent, GuardFailure.PARENT)
    core, actual_as = system.get_limit("core"), system.get_limit("as")
    _need(core == (0, 0) and actual_as == (address, address), GuardFailure.LIMIT)
    dumpable, death = system.dumpable(), system.death_signal()
    _need(dumpable == 0 and death == expected_signal, GuardFailure.SYSTEM)
    _need(system.profile(), GuardFailure.PROFILE)
    _need(
        system.pid() == pid and (role is ProcessRole.CONTROLLER or system.parent_pid() == parent),
        GuardFailure.PARENT,
    )
    return GuardFacts(role, pid, after, address, observed, dumpable, death, core)


def protect_process(
    *, role: ProcessRole, address_limit_bytes: int, expected_parent_pid: int | None = None
) -> GuardFacts:
    """One-way hard limits; caller MUST exit/reap on any failure.

    Does not clear memory/env or deliver secrets. Use an explicit child env,
    close inherited descriptors and wait for protection before secret IPC.
    AS is virtual address space, not charged cgroup memory or a capacity proof.
    A PID1 parent is governed additionally by namespace termination: PPID1 alone
    cannot distinguish that parent from adoption by namespace PID1. Never fork
    a secret-bearing child without exec; the pre-guard exec window must be public.
    """
    result: GuardFacts | None = None
    category: GuardFailure | None = None
    try:
        _inputs(role, address_limit_bytes, expected_parent_pid)
        _need(sys.platform == "linux", GuardFailure.UNSUPPORTED)
        result = _apply(_LinuxSystem(), role, address_limit_bytes, expected_parent_pid)
    except ProcessGuardError as error:
        category = error.category
    except BaseException:
        category = GuardFailure.SYSTEM
    # Raise outside the handler: never retain an OS error/message/context chain.
    if category is not None:
        raise ProcessGuardError(category)
    if result is None:
        raise ProcessGuardError(GuardFailure.SYSTEM)
    return result
