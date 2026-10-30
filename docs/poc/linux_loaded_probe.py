"""Loaded lab supervisor/member entrypoint. Never imported by product code.

No workload on import. Actual execution still requires host/command review.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import math
import os
import sys
import time
from functools import wraps
from pathlib import Path
from types import SimpleNamespace

COMMANDS = (
    b"GO_IMPORTS\n",
    b"PRESSURE_PRIVATE\n",
    b"PRESSURE_SHARED\n",
    b"RELEASE_PRIVATE\n",
    b"RELEASE_SHARED\n",
    b"FINISH\n",
)
CATEGORIES = {
    "CASE",
    "DIGEST",
    "DEADLINE",
    "STATE",
    "SCHEMA",
    "INVENTORY",
    "LIMIT",
    "OBSERVED_FAIL",
    "OBSERVED_INCONCLUSIVE",
    "RELEASE",
    "PROCESS",
    "PROTOCOL",
    "DIAGNOSTIC",
    "OUTER",
    "MEMORY",
    "IMPORT",
    "OTHER",
    "AUDIT_ERROR",
    "CHECK_ERROR",
    "EXIT",
    "CLEANUP",
}
OUTER_BYTES, REPORT_MAX = 192 << 20, 65536


class SupervisorFault(Exception):
    def __init__(self, code="DIAGNOSTIC"):
        self.code = code if type(code) is str and code in CATEGORIES else "DIAGNOSTIC"
        super().__init__(self.code)


def closed(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        code = "DIAGNOSTIC"
        try:
            return method(self, *args, **kwargs)
        except SupervisorFault as error:
            if type(error) is SupervisorFault:
                code = error.code
        except BaseException:
            pass
        raise SupervisorFault(code)

    return guarded


class Timer:
    def __init__(self, deadline, clock, stopped):
        self.deadline, self.clock, self.stopped, self.last = deadline, clock, stopped, 0
        remaining = self.remaining()
        if remaining > 20:
            raise SupervisorFault("DEADLINE")

    @closed
    def remaining(self):
        now = self.clock()
        if (
            self.stopped()
            or type(now) not in (int, float)
            or type(self.deadline) not in (int, float)
            or not math.isfinite(now)
            or not math.isfinite(self.deadline)
            or not 0 <= self.last <= now < self.deadline <= 1 << 50
        ):
            raise SupervisorFault("DEADLINE")
        self.last = now
        return self.deadline - now


class Channel:
    """Own child pipes, raw bounded lines. Closing belongs to the Popen owner."""

    def __init__(self, process, *, os_api, select_fn, timer):
        self.process, self.os, self.select, self.timer = process, os_api, select_fn, timer
        self.buffer = b""
        self.read_fd, self.write_fd = process.stdout.fileno(), process.stdin.fileno()
        self.os.set_blocking(self.read_fd, False)
        self.os.set_blocking(self.write_fd, False)

    @closed
    def read(self):
        while True:
            remaining = self.timer.remaining()
            if b"\n" in self.buffer:
                end = self.buffer.index(b"\n") + 1
                if end > 4096:
                    raise SupervisorFault("PROTOCOL")
                line, self.buffer = self.buffer[:end], self.buffer[end:]
                return line
            if len(self.buffer) >= 4096:
                raise SupervisorFault("PROTOCOL")
            try:
                ready = self.select([self.read_fd], [], [], remaining)[0]
                if not ready:
                    raise SupervisorFault("DEADLINE")
                self.timer.remaining()
                block = self.os.read(self.read_fd, 4096)
            except (BlockingIOError, InterruptedError):
                continue
            if not block:
                if self.buffer:
                    raise SupervisorFault("PROTOCOL")
                return None
            self.buffer += block
            if len(self.buffer) > 8192:
                raise SupervisorFault("PROTOCOL")

    @closed
    def quiet(self):
        self.timer.remaining()
        if self.buffer or self.select([self.read_fd], [], [], 0)[0]:
            raise SupervisorFault("PROTOCOL")

    @closed
    def send(self, command):
        if type(command) is not bytes or command not in COMMANDS:
            raise SupervisorFault("PROTOCOL")
        self.quiet()
        write_all(self.write_fd, command, self.os, self.select, self.timer)


def write_all(fd, raw, os_api, select_fn, timer):
    offset = 0
    while offset < len(raw):
        try:
            if not select_fn([], [fd], [], timer.remaining())[1]:
                raise SupervisorFault("DEADLINE")
            timer.remaining()
            count = os_api.write(fd, memoryview(raw)[offset:])
        except (BlockingIOError, InterruptedError):
            continue
        if type(count) is not int or not 0 < count <= len(raw) - offset:
            raise SupervisorFault("PROTOCOL")
        offset += count
    timer.remaining()


def load_parts():
    modules = {}
    for key, filename, name in (
        ("protocol", "loaded_memory_protocol.py", "_lab_loaded_protocol"),
        ("member", "loaded_memory_member.py", "_lab_loaded_member"),
        ("collect", "loaded_memory_collect.py", "_lab_loaded_collect"),
        ("probe", "linux_import_probe.py", "_lab_import_probe"),
        ("lab", "linux_as_probe.py", "_lab_support"),
    ):
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[key] = module
    return SimpleNamespace(**modules)


def _event(io, parts):
    raw = io.read()
    if raw is None:
        raise SupervisorFault("PROTOCOL")
    event = parts.lab.decode_line(raw)
    if event.get("phase") == "held":
        raise SupervisorFault("PROTOCOL")
    return event


def _observation(io, parts, result, case, *, fds=None, stable=True):
    observed = io.observe(stable=stable)
    parts.protocol.facts(observed["vm"], observed["limits"])
    if stable:
        parts.collect.valid_effects(observed["fds"])
    elif observed["fds"] is not None:
        raise SupervisorFault("PROCESS")
    if (
        type(observed["ppid"]) is not int
        or observed["ppid"] != 1
        or type(observed["inventory"]) is not list
        or any(type(pid) is not int for pid in observed["inventory"])
        or observed["inventory"] != [1, io.pid]
        or observed["limits"] != ([-1, -1] if case == "control" else [128 << 20] * 2)
        or (stable and fds is not None and observed["fds"] != fds)
    ):
        raise SupervisorFault("PROCESS")
    if len(result["observations"]) >= 24:
        raise SupervisorFault("PROTOCOL")
    result["observations"].append(observed)
    return observed


def _reported(event, observed, parts, case):
    parts.protocol.facts(event["vm"], event["limits"])
    if event["limits"] != observed["limits"]:
        raise SupervisorFault("LIMIT")
    if case != "control" and event["vm"]["peak"] > 128 << 20:
        raise SupervisorFault("OBSERVED_FAIL")


def supervise(case, expected, io, parts, *, deadline):
    """Trusted IO facts, single member. No host admission or next-case invocation."""
    result = {
        "profile": "loaded-as128",
        "case": case if case in ("control", "private", "shared") else "invalid",
        "outcome": "inconclusive",
        "total_memory_contained": False,
        "observations": [],
        "cleanup_confirmed": False,
    }
    core, natural_rc, expected_rc, marker = None, None, None, None
    stage, reason, imported, confirmed_fail, fds = "setup", "DIAGNOSTIC", None, False, None
    try:
        parts.protocol.parse_case_args(["--case", case, "--expected", expected])
        result["startup"] = io.prepare(case, deadline)
        pid = io.spawn(case)
        core = parts.protocol.PressureProtocol(
            case,
            expected,
            deadline=deadline,
            clock=io.clock,
            validator=parts.probe.validate_inventory,
            pid=pid,
        )
        stage = "ready"
        ready = parts.collect.envelope(_event(io, parts), "ready")
        obs = _observation(io, parts, result, case)
        fds = obs["fds"]
        _reported(ready, obs, parts, case)
        if case != "control" and ready["vm"]["size"] > 124 << 20:
            raise SupervisorFault("LIMIT")
        io.send(core.ready(obs["vm"], obs["limits"], pid=ready["pid"], ppid=ready["ppid"]))
        stage = "imports"
        collector = parts.collect.ImportCollector(parts.probe)
        while collector.state != "VERIFIED":
            event = _event(io, parts)
            collection_failed = False
            try:
                collector.feed(event)
            except parts.collect.CollectFault:
                collection_failed = True
            if collection_failed:
                if collector.expected_exit not in (72, 73, 74, 75, 76):
                    raise SupervisorFault("PROTOCOL")
                imported, expected_rc = collector.failure, collector.expected_exit
                if io.read() is not None:
                    raise SupervisorFault("PROTOCOL")
                natural_rc = io.wait()
                raise SupervisorFault(imported)
            if event["phase"] == "end":
                obs = _observation(io, parts, result, case, stable=False)
                parts.protocol.facts(event["vm"], obs["limits"])
                if case != "control" and (
                    event["vm"]["peak"] > 128 << 20 or obs["vm"]["peak"] > 128 << 20
                ):
                    raise SupervisorFault("OBSERVED_FAIL")
        stage = "loaded"
        loaded = parts.collect.envelope(_event(io, parts), "loaded")
        obs = _observation(io, parts, result, case, fds=fds)
        _reported(loaded, obs, parts, case)
        rows = collector.snapshot()
        core.admit_imports(rows, obs["vm"], obs["limits"])
        result["module_inventory"] = parts.probe.pack_inventory(rows)
        while core.state == "ADMITTED":
            stage = "pressure"
            obs = _observation(io, parts, result, case, fds=fds)
            io.send(core.pressure(obs["vm"], obs["limits"]))
            stage = "held"
            raw = io.read()
            if type(raw) is not bytes or not 1 <= len(raw) <= 1024:
                raise SupervisorFault("PROTOCOL")
            core.held(raw)
            obs = _observation(io, parts, result, case, fds=fds)
            io.send(
                core.release(
                    obs["vm"],
                    obs["limits"],
                    anon=obs["cgroup"]["stat"]["anon"],
                    inventory=obs["inventory"],
                )
            )
            stage = "release"
            event = _event(io, parts)
            if (
                type(event) is not dict
                or set(event) != {"phase", "kind"}
                or type(event["phase"]) is not str
                or event["phase"] != "released"
                or type(event["kind"]) is not str
                or event["kind"] != core.kind
            ):
                raise SupervisorFault("PROTOCOL")
            obs = _observation(io, parts, result, case, fds=fds)
            released = core.released(obs["vm"], obs["limits"], anon=obs["cgroup"]["stat"]["anon"])
            while not released:
                io.sleep(core.release_wait())
                obs = _observation(io, parts, result, case, fds=fds)
                released = core.release_sample(
                    obs["vm"], obs["limits"], anon=obs["cgroup"]["stat"]["anon"]
                )
        stage = "finish"
        _observation(io, parts, result, case, fds=fds)  # Last stable point, BEFORE FINISH.
        io.send(core.finish())
        marker = _event(io, parts)
        if marker != {"phase": "done"}:
            raise SupervisorFault("PROTOCOL")
        stage, expected_rc = "exit", 0
        if io.read() is not None:
            raise SupervisorFault("PROTOCOL")
        natural_rc = io.wait()
        reason = None
    except BaseException as error:
        reason = "DIAGNOSTIC"
        if type(error) in (parts.protocol.ProtocolFault, SupervisorFault):
            reason = error.code if error.code in CATEGORIES else "DIAGNOSTIC"
        if reason == "OBSERVED_FAIL" and case != "control":
            try:
                obs = _observation(
                    io, parts, result, case, fds=fds, stable=stage != "imports"
                )  # No core call/command after abort.
                confirmed_fail = obs["vm"]["peak"] > 128 << 20 or (
                    stage == "held"
                    and core is not None
                    and core.pre_size > 0
                    and obs["vm"]["size"] >= core.pre_size + (40 << 20)
                )
            except BaseException:
                confirmed_fail = False
    finally:
        try:
            cleanup = io.cleanup()
            result["cleanup_confirmed"] = cleanup["confirmed"] is True
            result["member_returncode"] = cleanup["returncode"]
            final = io.final()
            result["final_inventory"], result["final_cgroup"] = final["inventory"], final["cgroup"]
            clean = (
                result["cleanup_confirmed"]
                and type(final["inventory"]) is list
                and (
                    len(final["inventory"]) == 1
                    and type(final["inventory"][0]) is int
                    and final["inventory"][0] == 1
                )
            )
            rc = cleanup["returncode"]
            spontaneous = (
                type(rc) is int and rc < 0 and not (cleanup["killed"] is True and rc == -9)
            )
            exit_ok = expected_rc is None or (
                type(natural_rc) is int
                and natural_rc == expected_rc
                and type(rc) is int
                and rc == natural_rc
            )
            if not clean or final["outer_pressure"] is not False or spontaneous or not exit_ok:
                reason = "CLEANUP" if not clean else "OUTER" if final["outer_pressure"] else "EXIT"
            elif confirmed_fail:
                result["outcome"] = "fail"
            elif imported in ("MEMORY", "IMPORT") and case != "control" and expected_rc in (72, 73):
                result["outcome"] = "incompatible"
            elif reason is None and core is not None:
                result["outcome"] = core.completed(
                    marker, eof=True, returncode=rc, cleanup=True, inventory=final["inventory"]
                )
                if case == "control":
                    result["inventory_digest"] = core.control_digest()
        except BaseException:
            result["outcome"], reason = "inconclusive", "CLEANUP"
    if result["outcome"] not in ("control_ok", "imposed"):
        result.pop("inventory_digest", None)
        result["failure"] = {"stage": stage, "category": reason or "DIAGNOSTIC"}
    return result


def bounded_report(result):
    try:
        raw = json.dumps(result, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        if len(raw) + 1 <= REPORT_MAX:
            return raw + b"\n"
    except BaseException:
        pass
    return (
        b'{"profile":"loaded-as128","outcome":"inconclusive",'
        b'"report_limit":true,"total_memory_contained":false}\n'
    )


class OwnedProcess:
    """Audit the cleanup's own kill without changing the frozen reap algorithm."""

    def __init__(self, process=None):
        self.process, self.killed = process, False

    @property
    def stdin(self):
        return self.process.stdin

    @property
    def stdout(self):
        return self.process.stdout

    def poll(self):
        return self.process.poll()

    def wait(self, *, timeout):
        return self.process.wait(timeout=timeout)

    def kill(self):
        self.process.kill()
        self.killed = True


class LinuxSupervisor:
    @classmethod
    def from_linux(cls, parts, deadline):
        if (
            sys.platform != "linux"
            or not sys.flags.isolated
            or not sys.flags.no_site
            or os.getpid() != 1
            or os.getuid() != 65534
        ):
            raise SupervisorFault("PROCESS")
        import resource
        import select
        import signal
        import subprocess

        signal.signal(signal.SIGTERM, parts.lab._stop)
        return cls._with_apis(
            parts,
            deadline=deadline,
            os_api=os,
            resource_api=resource,
            select_fn=select.select,
            popen=subprocess.Popen,
            pipe=subprocess.PIPE,
            devnull=subprocess.DEVNULL,
            clock=time.monotonic,
            sleep=time.sleep,
            read_file=read_file,
            executable=sys.executable,
        )

    @classmethod
    def _with_apis(
        cls,
        parts,
        *,
        deadline,
        os_api,
        resource_api,
        select_fn,
        popen,
        pipe,
        devnull,
        clock,
        sleep,
        read_file,
        executable,
    ):
        self = cls.__new__(cls)
        self.parts, self.os, self.resource, self.select = parts, os_api, resource_api, select_fn
        self.popen, self.pipe, self.devnull = popen, pipe, devnull
        self.clock, self.sleeper, self.read_file, self.executable = (
            clock,
            sleep,
            read_file,
            executable,
        )
        self.timer = Timer(deadline, clock, lambda: parts.lab.STOP)
        self.process, self.channel, self.pid = None, None, None
        self.initial, self.previous, self.expected_limits, self.fds = None, None, None, None
        self.outer = False
        return self

    def _read(self, path):
        raw = self.read_file(path)
        if type(raw) is not bytes or not 1 <= len(raw) <= 65536 or not raw.endswith(b"\n"):
            raise SupervisorFault("PROTOCOL")
        return raw

    def _status(self, path):
        raw = self._read(path)
        return self.parts.member.parse_status(memoryview(raw), len(raw)), raw

    def _effects(self, pid):
        fds = []
        for name in self.os.listdir(f"/proc/{pid}/fd"):
            if not name.isascii() or not name.isdecimal():
                raise SupervisorFault("PROCESS")
            # Child listing/readlink failures never fall back to a self-report.
            target = self.os.readlink(f"/proc/{pid}/fd/" + name)
            if target.startswith("socket:"):
                raise SupervisorFault("PROCESS")
            fds.append(int(name))
        try:
            children = self.read_file(f"/proc/{pid}/task/{pid}/children")
            if type(children) is not bytes or len(children) > 65536:
                raise SupervisorFault("PROTOCOL")
            children = children.strip()  # This proc interface may be empty, without newline.
            available = True
        except FileNotFoundError:
            children, available = b"", False
        if children:
            raise SupervisorFault("PROCESS")
        return {"fds": sorted(fds), "proc_children_available": available}

    def _cgroup(self, expected):
        sample = self.parts.lab.cgroup_sample()
        if sample["procs"] != expected or sample["pids_current"] != len(expected):
            raise SupervisorFault("PROCESS")
        if self.previous is not None:
            for key in ("max", "oom", "oom_kill"):
                if sample["events"][key] < self.previous["events"][key]:
                    raise SupervisorFault("OUTER")
                if sample["events"][key] > self.initial["events"][key]:
                    self.outer = True
            if sample["peak"] < self.previous["peak"]:
                raise SupervisorFault("OUTER")
        self.outer = self.outer or sample["peak"] > OUTER_BYTES or sample["current"] > OUTER_BYTES
        self.previous = sample
        return sample

    @closed
    def prepare(self, case, deadline):
        self.timer.remaining()
        if deadline != self.timer.deadline or self.process is not None or self.initial is not None:
            raise SupervisorFault("STATE")
        vm, raw = self._status("/proc/self/status")
        if (
            b"NoNewPrivs:\t1\n" not in raw
            or b"CapEff:\t0000000000000000\n" not in raw
            or self._read("/proc/self/cgroup") != b"0::/\n"
            or self.os.confstr("CS_GNU_LIBC_VERSION") != "glibc 2.36"
            or self.parts.lab.inventory({1}) != [1]
        ):
            raise SupervisorFault("PROCESS")
        for name, number in (("memory.max", OUTER_BYTES), ("memory.swap.max", 0), ("pids.max", 16)):
            if self.parts.lab.number_file("/sys/fs/cgroup/" + name) != number:
                raise SupervisorFault("LIMIT")
        initial_fds = self.parts.probe.effects()
        if initial_fds["fds"] != [0, 1, 2]:
            raise SupervisorFault("PROCESS")
        self.initial = self._cgroup([1])
        inherited = list(self.resource.getrlimit(self.resource.RLIMIT_AS))
        self.expected_limits = [-1, -1] if case == "control" else [128 << 20] * 2
        if case == "control":
            if inherited != [-1, -1]:
                raise SupervisorFault("LIMIT")
        else:
            if vm["size"] > 124 << 20 or (inherited[1] != -1 and inherited[1] < 128 << 20):
                raise SupervisorFault("LIMIT")
            self.resource.setrlimit(self.resource.RLIMIT_AS, tuple(self.expected_limits))
        if (
            list(self.resource.getrlimit(self.resource.RLIMIT_AS)) != self.expected_limits
            or self.outer
        ):
            raise SupervisorFault("LIMIT")
        self.timer.remaining()
        return {
            "startup_vm": vm,
            "startup_cgroup": self.initial,
            "inherited_as": inherited,
            "supervisor_as": list(self.expected_limits),
        }

    @closed
    def spawn(self, case):
        self.timer.remaining()
        if (
            self.initial is None
            or self.process is not None
            or case not in ("control", "private", "shared")
        ):
            raise SupervisorFault("STATE")
        self.process = OwnedProcess()  # Preallocate owner before the OS can create the child.
        process = self.popen(
            [self.executable, "-I", "-B", "-S", "/probe/linux_loaded_probe.py", "--member", case],
            stdin=self.pipe,
            stdout=self.pipe,
            stderr=self.devnull,
            bufsize=0,
            close_fds=True,
            env={"PATH": "/usr/local/bin:/usr/bin"},
        )
        self.process.process = process  # Existing slot: before channel setup can fail.
        self.pid = process.pid
        if type(self.pid) is not int or self.pid < 2:
            raise SupervisorFault("PROCESS")
        self.channel = Channel(process, os_api=self.os, select_fn=self.select, timer=self.timer)
        self.timer.remaining()
        return self.pid

    @closed
    def observe(self, *, stable=True):
        self.timer.remaining()
        if self.process.poll() is not None:
            raise SupervisorFault("PROCESS")
        vm, raw = self._status(f"/proc/{self.pid}/status")
        parent = [line.split()[1:] for line in raw.splitlines() if line.startswith(b"PPid:")]
        if parent != [[b"1"]]:
            raise SupervisorFault("PROCESS")
        limits = self.parts.collect.parse_limits(self._read(f"/proc/{self.pid}/limits"))
        if limits != self.expected_limits:
            raise SupervisorFault("LIMIT")
        fds = None
        if stable:
            fds = self._effects(self.pid)
            self.parts.collect.valid_effects(fds)
            if self.fds is not None and fds != self.fds:
                raise SupervisorFault("PROCESS")
            self.fds = fds
        inventory = self.parts.lab.inventory({1, self.pid})
        sample = self._cgroup([1, self.pid])
        if self.outer:
            raise SupervisorFault("OUTER")
        self.timer.remaining()
        return {
            "vm": vm,
            "limits": limits,
            "ppid": 1,
            "fds": fds,
            "inventory": inventory,
            "cgroup": sample,
        }

    @closed
    def read(self):
        return self.channel.read()

    @closed
    def send(self, command):
        self.channel.send(command)

    @closed
    def sleep(self, delay):
        if type(delay) not in (int, float) or delay != 1.0 or self.timer.remaining() < delay:
            raise SupervisorFault("DEADLINE")
        self.sleeper(delay)
        self.timer.remaining()

    @closed
    def wait(self):
        rc = self.process.wait(timeout=self.timer.remaining())
        if type(rc) is not int or self.process.poll() != rc:
            raise SupervisorFault("PROCESS")
        self.timer.remaining()
        return rc

    def cleanup(self):
        confirmed, rc, killed = False, None, False
        try:
            created = self.process is not None and self.process.process is not None
            confirmed = self.parts.lab.reap([self.process] if created else []) is True
            if created:
                rc, killed = self.process.poll(), self.process.killed
                confirmed = (
                    confirmed
                    and type(rc) is int
                    and all(
                        pipe is not None and pipe.closed
                        for pipe in (self.process.stdin, self.process.stdout)
                    )
                )
        except BaseException:
            confirmed = False
        return {"confirmed": confirmed, "returncode": rc, "killed": killed}

    @closed
    def final(self):
        inventory = self.parts.lab.inventory({1})
        sample = self._cgroup([1])
        return {"inventory": inventory, "cgroup": sample, "outer_pressure": self.outer}


def read_file(path):
    with open(path, "rb") as handle:
        return handle.read(65537)


def member(case, parts, deadline):
    io = parts.member.LinuxIO.from_linux(deadline=deadline)
    try:
        raw = read_file(Path(__file__).with_name("runtime.json"))
        if len(raw) > 65536:
            raise SupervisorFault("PROTOCOL")
        manifest = json.loads(raw)
        if (
            type(manifest) is not dict
            or set(manifest) != {"owners", "generated", "versions"}
            or type(manifest["owners"]) is not dict
            or type(manifest["generated"]) is not dict
            or type(manifest["versions"]) is not dict
            or any(
                type(key) is not str or type(value) is not str
                for key, value in manifest["versions"].items()
            )
        ):
            raise SupervisorFault("PROTOCOL")
        sys.path.insert(0, "/installed")
        return parts.member.run_member(
            case,
            io,
            lambda emitter: parts.collect.collect_imports(
                emitter,
                parts.probe,
                manifest["owners"],
                manifest["generated"],
                modules=sys.modules,
                importer=importlib.import_module,
                effects_fn=parts.probe.effects,
                native_fn=parts.probe.native_check,
            ),
        )
    except BaseException:
        try:
            io.close()
        except BaseException:
            pass
    return 77


def main():
    if (
        sys.platform != "linux"
        or not sys.flags.isolated
        or not sys.flags.no_site
        or os.getuid() != 65534
    ):
        return 64
    deadline = time.monotonic() + 20
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "--member" and args[1] in ("control", "private", "shared"):
        if os.getpid() < 2 or os.getppid() != 1:
            return 64
        return member(args[1], load_parts(), deadline)
    if os.getpid() != 1:
        return 64
    parts = load_parts()
    case, expected = parts.protocol.parse_case_args(args)
    io = LinuxSupervisor.from_linux(parts, deadline)
    result = supervise(case, expected, io, parts, deadline=deadline)
    raw = bounded_report(result)
    write_report(raw, os_api=os, select_fn=io.select, clock=io.clock)
    return 0


def write_report(raw, *, os_api, select_fn, clock):
    if type(raw) is not bytes or not 1 <= len(raw) <= REPORT_MAX:
        raise SupervisorFault("PROTOCOL")
    timer = Timer(clock() + 2.0, clock, lambda: False)  # Diagnostic only, never renew measurement.
    old = os_api.get_blocking(1)
    try:
        os_api.set_blocking(1, False)
        write_all(1, raw, os_api, select_fn, timer)
    finally:
        os_api.set_blocking(1, old)


if __name__ == "__main__":
    try:
        code = main()
    except BaseException:
        code = 70  # No unbounded/blocking fallback or raw traceback on a broken report channel.
    raise SystemExit(code)
