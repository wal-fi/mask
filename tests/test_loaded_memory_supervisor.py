"""Supervisor composition via fakes only; no child, /proc, Docker or allocation load."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_linux_imports_probe import LAB, PROBE, load
from tests.test_loaded_memory_collect import FDS, events

S = load("linux_loaded_probe")
P = load("loaded_memory_protocol")
C = load("loaded_memory_collect")
M = load("loaded_memory_member")
PARTS = SimpleNamespace(protocol=P, collect=C, member=M, probe=PROBE, lab=LAB)


def line(event: Any) -> bytes:
    return json.dumps(event, separators=(",", ":")).encode("ascii") + b"\n"


def vm(size: int = 100, peak: int = 110) -> dict[str, int]:
    return {"size": size << 20, "peak": peak << 20, "rss": 20 << 20, "threads": 1}


def cg(anon: int = 60) -> dict[str, Any]:
    return {
        "current": 140 << 20,
        "peak": 160 << 20,
        "events": {"max": 0, "oom": 0, "oom_kill": 0},
        "stat": {"anon": anon << 20, "file": 10 << 20, "shmem": 0, "kernel": 1 << 20, "sock": 0},
        "procs": [1, 7],
        "pids_current": 2,
    }


class FakeIO:
    def __init__(self, case: str) -> None:
        self.case, self.now = case, 100.0
        self.queue: list[bytes] = []
        self.commands: list[bytes] = []
        self.trace: list[Any] = []
        self.kind, self.phase, self.pid = "private", "ready", 7
        self.limits = [-1, -1] if case == "control" else [128 << 20] * 2
        self.rc, self.closed, self.spawned = 0, False, 0
        self.snapshot = vm(20, 20)
        self.natural_exit, self.outer, self.clean, self.final_ids = True, False, True, [1]
        self.import_error: str | None = None
        self.held_mutation: Any = None
        self.observe_mutation: Any = None
        self.extra: bytes | None = None

    def clock(self) -> float:
        return self.now

    def prepare(self, case: str, deadline: float) -> dict[str, Any]:
        self.trace.append("prepare")
        assert case == self.case and deadline == 120
        return {"startup_vm": vm(20, 20), "startup_cgroup": cg(), "supervisor_as": self.limits}

    def spawn(self, case: str) -> int:
        assert case == self.case
        self.spawned += 1
        self.trace.append("spawn")
        self.queue.append(
            line(
                {"phase": "ready", "pid": 7, "ppid": 1, "limits": self.limits, "vm": self.snapshot}
            )
        )
        return 7

    def observe(self, *, stable: bool = True) -> dict[str, Any]:
        self.trace.append(("observe", self.phase))
        result = {
            "vm": dict(self.snapshot),
            "limits": list(self.limits),
            "ppid": 1,
            "fds": copy.deepcopy(FDS),
            "inventory": [1, 7],
            "cgroup": cg(100 if self.phase == "held" else 60),
        }
        if self.observe_mutation:
            self.observe_mutation(result, self)
        if not stable:
            result["fds"] = None
        return result

    def read(self) -> bytes | None:
        self.trace.append("read")
        if not self.queue:
            return self.extra
        raw = self.queue.pop(0)
        event = json.loads(raw)
        self.phase = event["phase"]
        if self.phase in ("end", "loaded", "held"):
            self.snapshot = dict(event["vm"])
        elif self.phase == "released":
            self.snapshot["size"] = 100 << 20
        return raw

    def send(self, command: bytes) -> None:
        self.trace.append(("send", command))
        assert not self.queue  # fake's quiet gate; native channel tested separately
        self.commands.append(command)
        if command == b"GO_IMPORTS\n":
            stream = events()
            if self.import_error:
                stream = [
                    *stream[:2],
                    {"phase": "error", "stage": 0, "category": self.import_error},
                ]
            else:
                stream.append({"phase": "loaded", "limits": self.limits, "vm": vm()})
            self.queue.extend(line(event) for event in stream)
        elif command.startswith(b"PRESSURE_"):
            self.kind = "shared" if command == b"PRESSURE_SHARED\n" else "private"
            accepted = (40 if self.case == "control" else 16) << 20
            event = {
                "phase": "held",
                "kind": self.kind,
                "limits": self.limits,
                "vm": vm(140, 144) if self.case == "control" else vm(124, 126),
                "accepted_bytes": accepted,
                "touched_pages": accepted // 4096,
                "blocks": accepted // (4 << 20),
                "failure": "NONE" if self.case == "control" else "MEMORY",
                "errno": None,
            }
            if self.held_mutation:
                self.held_mutation(event)
            self.queue.append(line(event))
        elif command.startswith(b"RELEASE_"):
            self.queue.append(line({"phase": "released", "kind": self.kind}))
        elif command == b"FINISH\n":
            self.queue.append(line({"phase": "done"}))
        else:
            raise AssertionError("unexpected-command")

    def wait(self) -> int:
        self.trace.append("wait")
        return self.rc

    def sleep(self, delay: float) -> None:
        self.trace.append("sleep")
        self.now += delay

    def cleanup(self) -> dict[str, Any]:
        self.trace.append("cleanup")
        self.closed = True
        return {"confirmed": self.clean, "returncode": self.rc, "killed": not self.natural_exit}

    def final(self) -> dict[str, Any]:
        self.trace.append("final")
        return {"inventory": self.final_ids, "cgroup": cg(), "outer_pressure": self.outer}


def run(case: str = "private", expected: str | None = None, io: Any = None) -> tuple[Any, FakeIO]:
    io = io or FakeIO(case)
    rows = C.ImportCollector(PROBE)
    for event in events():
        rows.feed(event)
    digest = P.inventory_digest(rows.snapshot(), PROBE.validate_inventory)
    report = S.supervise(
        case, expected or ("-" if case == "control" else digest), io, PARTS, deadline=120.0
    )
    return report, io


@pytest.mark.parametrize("case", ["control", "private", "shared"])
def test_complete_supervisor_uses_independent_facts_before_commands(case):
    report, io = run(case)
    assert report["outcome"] == ("control_ok" if case == "control" else "imposed")
    assert report["cleanup_confirmed"] is True and report["final_inventory"] == [1]
    assert report["profile"] == "loaded-as128" and report["total_memory_contained"] is False
    assert ("inventory_digest" in report) == (case == "control")
    assert io.spawned == 1 and io.trace[-2:] == ["cleanup", "final"]
    assert io.commands[0] == b"GO_IMPORTS\n" and io.commands[-1] == b"FINISH\n"
    for index, item in enumerate(io.trace):
        if isinstance(item, tuple) and item[0] == "send":
            assert io.trace[index - 1][0] == "observe"
    assert not any(isinstance(item, tuple) and item == ("observe", "done") for item in io.trace)


def test_digest_mismatch_blocks_all_pressure_and_digest_export():
    report, io = run(expected="a" * 64)
    assert report["outcome"] == "inconclusive"
    assert io.commands == [b"GO_IMPORTS\n"]
    assert "inventory_digest" not in report and io.closed


@pytest.mark.parametrize("case", ["control", "private", "shared"])
@pytest.mark.parametrize("category,code", [("MEMORY", 72), ("IMPORT", 73), ("OTHER", 74)])
def test_import_failure_natural_matching_exit_only(case, category, code):
    io = FakeIO(case)
    io.import_error, io.rc = category, code
    report, io = run(case, io=io)
    assert report["outcome"] == (
        "incompatible" if case != "control" and code in (72, 73) else "inconclusive"
    )
    assert io.commands == [b"GO_IMPORTS\n"]
    assert "wait" in io.trace and io.closed


@pytest.mark.parametrize("code", [0, 77, -9])
def test_mismatching_import_exit_never_incompatible(code):
    io = FakeIO("private")
    io.import_error, io.rc = "MEMORY", code
    report, _io = run(io=io)
    assert report["outcome"] == "inconclusive" and "inventory_digest" not in report


@pytest.mark.parametrize("mode", ["cleanup", "final", "outer", "exit", "extra"])
def test_final_precedence_invalidates_success_and_digest(mode):
    io = FakeIO("control")
    if mode == "cleanup":
        io.clean = False
    elif mode == "final":
        io.final_ids = [1, 7]
    elif mode == "outer":
        io.outer = True
    elif mode == "exit":
        io.rc = 77
    else:
        io.extra = b'{"phase":"done"}\n'
    report, io = run("control", io=io)
    assert report["outcome"] == "inconclusive" and "inventory_digest" not in report
    assert io.closed


@pytest.mark.parametrize("field", ["limits", "ppid", "fds", "inventory"])
def test_independent_mismatch_refuses_before_go(field):
    io = FakeIO("private")

    def mutation(observed, _io):
        observed[field] = {
            "limits": [-1, -1],
            "ppid": 2,
            "fds": {"fds": [0, 1, 2], "proc_children_available": True},
            "inventory": [1, 7, 8],
        }[field]

    io.observe_mutation = mutation
    report, io = run(io=io)
    assert report["outcome"] == "inconclusive" and io.commands == [] and io.closed


@pytest.mark.parametrize("confirmed", [False, True])
def test_member_claimed_fail_requires_independent_confirmation_before_kill(confirmed):
    io = FakeIO("private")

    def held(event):
        event.update(
            accepted_bytes=40 << 20, blocks=10, touched_pages=10240, failure="NONE", errno=None
        )

    def observe(result, member):
        if member.phase == "held":
            result["vm"] = vm(140, 144) if confirmed else vm(124, 126)

    io.held_mutation, io.observe_mutation, io.natural_exit, io.rc = held, observe, False, -9
    report, io = run(io=io)
    assert report["outcome"] == ("fail" if confirmed else "inconclusive")
    assert not any(
        command.startswith(b"RELEASE") or command == b"FINISH\n" for command in io.commands
    )
    assert io.trace[-3][0] == "observe" and io.trace[-2:] == ["cleanup", "final"]


@pytest.mark.parametrize("method", ["prepare", "spawn", "read", "observe", "send", "wait"])
def test_unexpected_collaborator_failure_sanitized_cleanup(monkeypatch, method):
    io = FakeIO("private")

    def fail(*_args):
        raise OSError("private-data")

    monkeypatch.setattr(io, method, fail)
    report, io = run(io=io)
    assert report["outcome"] == "inconclusive" and "private-data" not in repr(report)
    assert io.closed and "inventory_digest" not in report


def test_report_cap_cannot_export_success_digest():
    report, _io = run("control")
    report["module_inventory"] = {"payload": "x" * 65536}
    raw = S.bounded_report(report)
    parsed = json.loads(raw)
    assert len(raw) <= 65536 and parsed["outcome"] == "inconclusive"
    assert "inventory_digest" not in parsed


class Pipe:
    def __init__(self, fd: int) -> None:
        self.fd, self.closed = fd, False

    def fileno(self) -> int:
        return self.fd

    def close(self) -> None:
        self.closed = True


class Process:
    def __init__(self) -> None:
        self.pid, self.stdin, self.stdout = 7, Pipe(10), Pipe(11)
        self.returncode: int | None = None
        self.kills, self.waits = 0, 0

    def poll(self) -> int | None:
        return self.returncode

    def kill(self) -> None:
        self.kills += 1
        self.returncode = -9

    def wait(self, timeout: float) -> int:
        assert 0 < timeout <= 20
        self.waits += 1
        self.returncode = 0 if self.returncode is None else self.returncode
        return self.returncode


class OS:
    def __init__(self) -> None:
        self.reads: list[bytes | BaseException] = []
        self.writes: list[bytes] = []
        self.steps: list[Any] = []
        self.blocking: dict[int, bool] = {}

    def set_blocking(self, fd: int, value: bool) -> None:
        self.blocking[fd] = value

    def read(self, _fd: int, limit: int) -> bytes:
        assert limit == 4096
        value = self.reads.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    def write(self, _fd: int, raw: Any) -> int:
        value = self.steps.pop(0) if self.steps else len(raw)
        if isinstance(value, BaseException):
            raise value
        self.writes.append(bytes(raw[:value]))
        return value

    def listdir(self, path: str) -> list[str]:
        assert path == "/proc/7/fd"
        return ["0", "1", "2", "9"]

    def readlink(self, path: str) -> str:
        assert path.startswith("/proc/7/fd/")
        return "/proc/7/status" if path.endswith("9") else "pipe:[1]"

    def confstr(self, _key: str) -> str:
        return "glibc 2.36"


def channel() -> tuple[Any, OS]:
    os_api = OS()
    timer = S.Timer(120.0, lambda: 100.0, lambda: False)
    result = S.Channel(
        Process(),
        os_api=os_api,
        select_fn=lambda reads, writes, _errors, _timeout: (reads, writes, []),
        timer=timer,
    )
    return result, os_api


def test_raw_channel_preserves_two_lines_and_canonical_held_bytes():
    state, os_api = channel()
    os_api.reads = [b'{"phase":"held"}\n{"phase":"released","kind":"private"}\n', b""]
    assert state.read() == b'{"phase":"held"}\n'
    assert state.read() == b'{"phase":"released","kind":"private"}\n'
    assert state.read() is None


@pytest.mark.parametrize("raw", [b"x" * 4096, b"partial", b'{"phase":"done"}'])
def test_raw_channel_partial_or_oversize_not_clean_eof(raw):
    state, os_api = channel()
    os_api.reads = [raw, b""]
    with pytest.raises(S.SupervisorFault) as caught:
        state.read()
    assert caught.value.__context__ is None


@pytest.mark.parametrize("buffer", [b"", b"pending\n"])
def test_channel_quiet_checks_both_buffer_and_select_before_write(buffer):
    state, os_api = channel()
    state.buffer = buffer
    with pytest.raises(S.SupervisorFault):
        state.send(b"FINISH\n")
    assert os_api.writes == []


def test_partial_writer_and_eagain_without_renewing_deadline():
    state, os_api = channel()
    state.select = lambda _reads, writes, _errors, _timeout: ([], writes, [])
    os_api.steps = [BlockingIOError(), 2, InterruptedError(), 1]
    state.send(b"FINISH\n")
    assert b"".join(os_api.writes) == b"FINISH\n"


@pytest.mark.parametrize("mode", ["late-held", "oversize-held", "extra-held"])
def test_raw_decoded_routing_blocks_before_release(mode, monkeypatch):
    io = FakeIO("private")
    original = io.read

    def read():
        raw = original()
        if mode == "late-held" and io.phase == "loaded":
            return b'{"phase":"held"}\n'
        if mode == "oversize-held" and io.phase == "held":
            return b" " * 1025 + (raw or b"")
        if mode == "extra-held" and io.phase == "held":
            return (raw or b"") + b'{"phase":"done"}\n'
        return raw

    monkeypatch.setattr(io, "read", read)
    report, io = run(io=io)
    assert report["outcome"] == "inconclusive" and io.closed
    assert not any(cmd.startswith(b"RELEASE") for cmd in io.commands)


def backend(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any, list[Any]]:
    os_api = OS()
    trace: list[Any] = []
    resource = SimpleNamespace(RLIMIT_AS=9)
    resource.limits = (-1, -1)

    def setlimit(_key, limits):
        trace.append("setrlimit")
        resource.limits = limits

    resource.getrlimit = lambda _key: resource.limits
    resource.setrlimit = setlimit
    process = Process()

    def popen(args, **kwargs):
        trace.append(("popen", args, kwargs))
        return process

    status = (
        b"VmSize:\t20480 kB\nVmPeak:\t20480 kB\nVmRSS:\t10240 kB\nThreads:\t1\n"
        b"PPid:\t1\nNoNewPrivs:\t1\nCapEff:\t0000000000000000\n"
    )
    limits = b"Max address space   134217728   134217728   bytes\n"

    def read_file(path):
        if path.endswith("status"):
            return status
        if path.endswith("limits"):
            return limits
        if path.endswith("children"):
            return b""  # real /proc children is empty without a newline
        if path == "/proc/self/cgroup":
            return b"0::/\n"
        raise AssertionError("unexpected-path")

    monkeypatch.setattr(
        PROBE, "effects", lambda: {"fds": [0, 1, 2], "proc_children_available": True}
    )
    monkeypatch.setattr(LAB, "inventory", sorted)
    monkeypatch.setattr(
        LAB,
        "number_file",
        lambda path: {"memory.max": 192 << 20, "memory.swap.max": 0, "pids.max": 16}[
            path.rsplit("/", 1)[1]
        ],
    )
    samples = []

    def sample():
        current = cg()
        current["procs"] = [1] if not trace or process.returncode is not None else [1, 7]
        current["pids_current"] = len(current["procs"])
        samples.append(current)
        return current

    monkeypatch.setattr(LAB, "cgroup_sample", sample)
    io = S.LinuxSupervisor._with_apis(
        PARTS,
        deadline=120,
        os_api=os_api,
        resource_api=resource,
        select_fn=lambda reads, writes, _errors, _timeout: (reads, writes, []),
        popen=popen,
        pipe=-1,
        devnull=-3,
        clock=lambda: 100.0,
        sleep=lambda _delay: None,
        read_file=read_file,
        executable="/usr/local/bin/python",
    )
    return io, process, trace


def test_linux_backend_as_before_spawn_exact_argv_and_independent_empty_children(monkeypatch):
    io, process, trace = backend(monkeypatch)
    io.prepare("private", 120)
    assert io.spawn("private") == 7
    assert trace[0] == "setrlimit" and trace[1][0] == "popen"
    _name, argv, options = trace[1]
    assert argv == [
        "/usr/local/bin/python",
        "-I",
        "-B",
        "-S",
        "/probe/linux_loaded_probe.py",
        "--member",
        "private",
    ]
    assert options == {
        "stdin": -1,
        "stdout": -1,
        "stderr": -3,
        "bufsize": 0,
        "close_fds": True,
        "env": {"PATH": "/usr/local/bin:/usr/bin"},
    }
    obs = io.observe()
    assert obs["fds"] == FDS and obs["limits"] == [128 << 20] * 2
    assert io.cleanup() == {"confirmed": True, "returncode": -9, "killed": True}
    assert process.kills == 1 and process.stdin.closed and process.stdout.closed
    assert io.final()["inventory"] == [1]


def test_own_child_reaped_when_channel_construction_fails(monkeypatch):
    io, process, _trace = backend(monkeypatch)
    io.prepare("private", 120)

    def fail(*_args, **_kwargs):
        raise MemoryError("private-data")

    monkeypatch.setattr(S, "Channel", fail)
    with pytest.raises(S.SupervisorFault) as caught:
        io.spawn("private")
    assert caught.value.__context__ is None
    assert io.cleanup()["confirmed"] is True
    assert process.kills == 1 and process.stdin.closed and process.stdout.closed


@pytest.mark.parametrize("operation", ["listdir", "readlink"])
def test_child_fd_access_failure_has_no_fallback(monkeypatch, operation):
    io, _process, _trace = backend(monkeypatch)
    io.prepare("private", 120)
    io.spawn("private")

    def denied(*_args):
        raise PermissionError("private-data")

    monkeypatch.setattr(io.os, operation, denied)
    with pytest.raises(S.SupervisorFault) as caught:
        io.observe()
    assert caught.value.__context__ is None
    assert io.cleanup()["confirmed"] is True


def test_member_accepts_existing_closed_runtime_manifest_with_versions(monkeypatch):
    io = SimpleNamespace(close=lambda: True)
    api = SimpleNamespace(
        LinuxIO=SimpleNamespace(from_linux=lambda **_kw: io),
        run_member=lambda _case, _io, _imports: 0,
    )
    parts = SimpleNamespace(member=api)
    manifest = {"owners": {"root": "owner"}, "generated": {}, "versions": {"owner": "1.0"}}
    monkeypatch.setattr(S, "read_file", lambda _path: json.dumps(manifest).encode())
    monkeypatch.setattr(S.sys, "path", list(S.sys.path))
    assert S.member("private", parts, 120) == 0


def test_factory_refuses_before_native_resources_on_windows(monkeypatch):
    monkeypatch.setattr(S, "sys", SimpleNamespace(platform="win32"))
    with pytest.raises(S.SupervisorFault):
        S.LinuxSupervisor.from_linux(PARTS, 120)


def test_transient_mid_import_fd_not_checked_but_blocked_point_is_checked(monkeypatch):
    io, _process, _trace = backend(monkeypatch)
    io.prepare("private", 120)
    io.spawn("private")
    io.observe()  # stable ready baseline
    original = io.os.listdir

    def transient(path):
        return [*original(path), "10"]

    monkeypatch.setattr(io.os, "listdir", transient)
    assert io.observe(stable=False)["fds"] is None
    with pytest.raises(S.SupervisorFault):
        io.observe(stable=True)
    assert io.cleanup()["confirmed"]


def test_diagnostic_report_uses_own_budget_after_measurement_deadline(monkeypatch):
    os_api = OS()
    os_api.getpid = lambda: 1  # type: ignore[attr-defined]
    os_api.getuid = lambda: 65534  # type: ignore[attr-defined]
    os_api.get_blocking = lambda _fd: True  # type: ignore[attr-defined]
    now = [100.0]
    timer = S.Timer(120, lambda: now[0], lambda: False)
    now[0] = 125.0
    io = SimpleNamespace(
        timer=timer,
        clock=lambda: now[0],
        select=lambda reads, writes, _errors, _timeout: (reads, writes, []),
    )
    monkeypatch.setattr(S, "os", os_api)
    monkeypatch.setattr(
        S,
        "sys",
        SimpleNamespace(
            platform="linux",
            flags=SimpleNamespace(isolated=True, no_site=True),
            argv=["/probe/linux_loaded_probe.py", "--case", "control", "--expected", "-"],
        ),
    )
    monkeypatch.setattr(S, "time", SimpleNamespace(monotonic=lambda: 100.0))
    monkeypatch.setattr(S, "load_parts", lambda: PARTS)
    monkeypatch.setattr(S.LinuxSupervisor, "from_linux", lambda _parts, _deadline: io)
    report = {
        "profile": "loaded-as128",
        "outcome": "inconclusive",
        "failure": {"stage": "exit", "category": "DEADLINE"},
    }
    monkeypatch.setattr(S, "supervise", lambda *_args, **_kwargs: report)
    assert S.main() == 0
    assert json.loads(b"".join(os_api.writes)) == report
    assert os_api.blocking[1] is True


@pytest.mark.parametrize("case", ["control", "private", "shared"])
def test_supervisor_mid_import_observations_never_inspect_transient_fds(monkeypatch, case):
    io = FakeIO(case)
    original = io.observe

    def observe(*, stable=True):
        if io.phase == "end":
            assert stable is False
        else:
            assert stable is True
        return original(stable=stable)

    monkeypatch.setattr(io, "observe", observe)
    report, _io = run(case, io=io)
    assert report["outcome"] == ("control_ok" if case == "control" else "imposed")
    assert sum(obs["fds"] is None for obs in report["observations"]) == 3


@pytest.mark.parametrize("releases", [3, 6])
def test_release_retries_observe_without_extra_command_or_renewal(releases):
    io = FakeIO("control")
    count = 0

    def mutate(observed, world):
        nonlocal count
        if world.phase == "released" and world.kind == "private":
            count += 1
            observed["cgroup"]["stat"]["anon"] = (95 if count < releases else 60) << 20

    io.observe_mutation = mutate
    report, io = run("control", io=io)
    assert io.trace.count("sleep") == min(releases - 1, 4)
    assert report["outcome"] == ("control_ok" if releases == 3 else "inconclusive")
    if releases == 6:
        assert b"PRESSURE_SHARED\n" not in io.commands and b"FINISH\n" not in io.commands


def test_release_sleep_failure_is_terminal_and_cleans(monkeypatch):
    io = FakeIO("control")

    def mutate(observed, world):
        if world.phase == "released" and world.kind == "private":
            observed["cgroup"]["stat"]["anon"] = 95 << 20

    def fail(_seconds):
        raise MemoryError("private-data")

    io.observe_mutation = mutate
    monkeypatch.setattr(io, "sleep", fail)
    report, io = run("control", io=io)
    assert report["outcome"] == "inconclusive" and io.closed
    assert b"PRESSURE_SHARED\n" not in io.commands and "private-data" not in repr(report)


def test_report_budget_is_fixed_and_restores_flags_on_timeout():
    os_api = OS()
    os_api.get_blocking = lambda _fd: True  # type: ignore[attr-defined]
    ticks = iter([125.0, 125.0, 127.0])
    with pytest.raises(S.SupervisorFault, match=r"^DEADLINE$"):
        S.write_report(
            b"{}\n",
            os_api=os_api,
            select_fn=lambda reads, writes, _errors, _timeout: (reads, writes, []),
            clock=lambda: next(ticks),
        )
    assert os_api.writes == [] and os_api.blocking[1] is True
