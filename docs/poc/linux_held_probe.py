"""PID1 capture-only wrapper. No backend/helper load or workload on import."""

from __future__ import annotations

import hashlib
import math
import os
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace

TAP_SHA = "aae25eb187ccd483847b725049e8932df469a5d1b9722dad786cb328436f504d"
SUPERVISOR_SHA = "40ead31f7fe57cb2102f30c1be3f535fa342e3ae22d8696e0970d4eab4315466"


class EntryFault(Exception):
    def __init__(self):
        super().__init__("ENTRY")


def load_checked(path, expected, name):
    try:
        with path.open("rb") as handle:
            raw = handle.read(65537)
        if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != expected:
            raise EntryFault()
        module = ModuleType(name)
        module.__file__ = str(path)
        exec(compile(raw, str(path), "exec"), module.__dict__)
        return module
    except BaseException:
        pass
    raise EntryFault()


def load_bundle():
    return SimpleNamespace(
        supervisor=load_checked(
            Path(__file__).with_name("linux_loaded_probe.py"), SUPERVISOR_SHA, "held_supervisor"
        ),
        tap=load_checked(Path(__file__).with_name("loaded_memory_tap.py"), TAP_SHA, "held_tap"),
    )


def allowed(platform, flags, os_api):
    if type(platform) is not str or platform != "linux":
        return False
    for name in ("isolated", "no_site", "dont_write_bytecode"):
        value = getattr(flags, name, None)
        if type(value) is not int or value != 1:
            return False
    uid, pid = os_api.getuid(), os_api.getpid()
    return type(uid) is int and uid == 65534 and type(pid) is int and pid == 1


def instant(clock):
    value = clock()
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value < 1 << 50:
        raise EntryFault()
    return value


def remaining(clock, previous, deadline):
    value = instant(clock)
    if not previous <= value < deadline:
        raise EntryFault()
    return value


def run(args, *, platform, flags, os_api, clock, loader):
    try:
        if not allowed(platform, flags, os_api):
            return 64
        started = instant(clock)
        deadline = started + 20
        bundle = loader()
        now = remaining(clock, started, deadline)
        supervisor, tap = bundle.supervisor, bundle.tap
        parts = supervisor.load_parts()
        try:
            case, expected = parts.protocol.parse_case_args(args)
        except parts.protocol.ProtocolFault:
            return 64
        remaining(clock, now, deadline)
        io = supervisor.LinuxSupervisor.from_linux(parts, deadline)
        raw = tap.capture(supervisor, case, expected, io, parts, deadline=deadline)
        if type(raw) is not bytes or not 1 <= len(raw) <= 65536:
            return 70
        supervisor.write_report(raw, os_api=io.os, select_fn=io.select, clock=io.clock)
        return 0  # Emission only. Host must decode/classify transport and original.
    except BaseException:
        return 70  # Never a traceback, unlimited stdout or blocking fallback.


def main():
    return run(
        sys.argv[1:],
        platform=sys.platform,
        flags=sys.flags,
        os_api=os,
        clock=time.monotonic,
        loader=load_bundle,
    )


if __name__ == "__main__":
    raise SystemExit(main())
