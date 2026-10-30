"""Member and Linux backend via fakes only: no mmap, /proc, child or load."""

from __future__ import annotations

import errno
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_linux_imports_probe import PROBE, load

M = load("loaded_memory_member")
P = load("loaded_memory_protocol")


class Block:
    def __init__(self, size: int, events: list[Any], name: str) -> None:
        self.size, self.events, self.name = size, events, name
        self.touched = self.closed = False

    def __setitem__(self, key: slice, value: bytes) -> None:
        assert key == slice(0, None, 4096)
        assert value == b"x" * (self.size // 4096)
        self.touched = True
        self.events.append(("touch", self.name))


class FakeIO:
    def __init__(self, case: str = "private", fail_at: int = 2) -> None:
        self.case, self.fail_at = case, fail_at
        self.events: list[Any] = []
        kinds = ["private", "shared"] if case == "control" else [case]
        self.commands = [b"GO_IMPORTS\n"]
        for kind in kinds:
            self.commands.extend(
                [
                    b"PRESSURE_" + kind.upper().encode() + b"\n",
                    b"RELEASE_" + kind.upper().encode() + b"\n",
                ]
            )
        self.commands.append(b"FINISH\n")
        self.output: list[dict[str, Any]] = []
        self.blocks: list[Block] = []
        self.pid, self.ppid, self.failed = 7, 1, False
        self.allocator_error: BaseException = MemoryError("private-data")
        self.close_failure: str | None = None

    def check(self) -> None:
        self.events.append("check")

    def sample(self) -> tuple[dict[str, int], list[int]]:
        self.events.append("sample")
        return {"size": 120 << 20, "peak": 126 << 20, "rss": 20 << 20, "threads": 1}, (
            [-1, -1] if self.case == "control" else [128 << 20] * 2
        )

    def allocate_reserve(self) -> Block:
        block = Block(2 << 20, self.events, "reserve")
        self.blocks.append(block)
        return block

    def allocate(self, kind: str) -> Block:
        self.events.append(("allocate", kind))
        live = sum(not b.closed and b.name != "reserve" for b in self.blocks)
        if self.case != "control" and live == self.fail_at:
            raise self.allocator_error
        block = Block(4 << 20, self.events, str(len(self.blocks)))
        self.blocks.append(block)
        return block

    def free(self, block: Block) -> None:
        self.events.append(("free", block.name))
        if block.name == self.close_failure:
            raise OSError("private-data")
        block.closed = True

    def command(self, expected: bytes) -> None:
        self.events.append(("command", expected))
        assert self.commands.pop(0) == expected

    def emit(self, event: dict[str, Any]) -> None:
        self.events.append(("emit", event["phase"]))
        self.output.append(event)

    def write(self, raw: Any) -> None:
        event = P.decode_held(bytes(raw))
        self.events.append(("held", event["kind"]))
        self.output.append(event)
        assert all(b.touched for b in self.blocks if not b.closed)
        if self.case != "control":
            assert self.blocks[0].closed  # reserve only; payload retained until RELEASE
        assert sum(not b.closed and b.name != "reserve" for b in self.blocks) == event["blocks"]

    def close(self) -> bool:
        self.events.append("io-close")
        return True


def imported(io: Any) -> int:
    io.events.append("imports")
    return 0


@pytest.mark.parametrize("case", ["control", "private", "shared"])
def test_complete_retention_order_and_fixed_hold_encoding(case):
    io = FakeIO(case)
    assert M.run_member(case, io, imported) == 0
    held = [item for item in io.output if item["phase"] == "held"]
    assert len(held) == (2 if case == "control" else 1)
    assert all(item["blocks"] == (10 if case == "control" else 2) for item in held)
    assert all(b.closed for b in io.blocks)
    first_hold = io.events.index(("held", held[0]["kind"]))
    assert io.events[first_hold - (1 if case == "control" else 2)] == "sample"
    if case != "control":
        assert io.events[first_hold - 1] == ("free", "reserve")
    assert io.output[-1] == {"phase": "done"}
    assert io.events[-1] == "io-close"


@pytest.mark.parametrize(
    "error,category,number",
    [
        (MemoryError(), "MEMORY", None),
        (OSError(12, "x"), "ENOMEM", 12),
        (OSError(5, "x"), "OTHER", 5),
        (OSError(), "OTHER", None),
    ],
)
def test_only_allocator_error_is_categorized(error, category, number):
    io = FakeIO(fail_at=1)
    io.allocator_error = error
    assert M.run_member("private", io, imported) == 0
    held = next(row for row in io.output if row["phase"] == "held")
    assert (held["failure"], held["errno"], held["accepted_bytes"]) == (category, number, 4 << 20)
    assert io.events.count(("allocate", "private")) == 2


def test_first_refusal_is_reported_zero_not_claimed_imposed():
    io = FakeIO(fail_at=0)
    assert M.run_member("private", io, imported) == 0
    held = next(row for row in io.output if row["phase"] == "held")
    assert held["blocks"] == 0
    assert held["failure"] == "MEMORY"  # classification belongs only to supervisor core


@pytest.mark.parametrize("operation", ["check", "sample", "command", "write", "emit"])
@pytest.mark.parametrize("error", [MemoryError, OSError, KeyboardInterrupt, SystemExit])
def test_diagnostic_failure_never_reports_refusal(monkeypatch, operation, error):
    io = FakeIO()

    def fail(*_args):
        raise error("private-data")

    monkeypatch.setattr(io, operation, fail)
    assert M.run_member("private", io, imported) == 77
    assert not any(row["phase"] == "held" for row in io.output)
    assert all(b.closed for b in io.blocks)
    assert io.events[-1] == "io-close"


def test_touch_failure_owned_and_cleaned_not_refusal(monkeypatch):
    io = FakeIO()
    original = Block.__setitem__

    def touch(self, key, value):
        if self.name != "reserve":
            raise MemoryError("private-data")
        original(self, key, value)

    monkeypatch.setattr(Block, "__setitem__", touch)
    assert M.run_member("private", io, imported) == 77
    assert all(b.closed for b in io.blocks)
    assert not any(row["phase"] == "held" for row in io.output)


@pytest.mark.parametrize("code", [72, 73, 74, 75, 76])
def test_import_failure_code_preserved_cleanup_overrides(code):
    io = FakeIO()
    assert M.run_member("private", io, lambda _io: code) == code
    assert not any(row["phase"] in ("loaded", "held") for row in io.output)
    io = FakeIO()
    io.close_failure = "reserve"
    assert M.run_member("private", io, lambda _io: code) == 77


@pytest.mark.parametrize("code", [True, 1, 77, None, "0"])
def test_unrecognized_import_code_is_fixed_diagnostic(code):
    assert M.run_member("private", FakeIO(), lambda _io: code) == 77


def test_swallowed_writer_failure_overrides_import_category():
    io = FakeIO()

    def failed_transport(io):
        io.failed = True
        return 75

    assert M.run_member("private", io, failed_transport) == 77


def test_failed_cleanup_still_attempts_every_owned_block():
    io = FakeIO()
    io.close_failure = "1"
    assert M.run_member("private", io, imported) == 77
    assert ("free", "2") in io.events
    assert io.events[-1] == "io-close"


STATUS = b"Name:\tprobe\nVmPeak:\t129024 kB\nVmSize:\t122880 kB\nVmRSS:\t20480 kB\nThreads:\t1\n"


def test_status_parser_uses_bounded_scratch_and_real_units():
    value = M.parse_status(memoryview(STATUS), len(STATUS))
    assert value == {"size": 120 << 20, "peak": 126 << 20, "rss": 20 << 20, "threads": 1}


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        STATUS[:-1],
        STATUS + b"Threads:\t1\n",
        STATUS.replace(b"kB", b"MB"),
        STATUS.replace(b"\t1\n", b"\t2\n"),
        STATUS.replace(b"122880", b"99999999999999999999999999999"),
        STATUS.replace(b"VmRSS:", b"Other:"),
        STATUS.replace(b"20480", b"-1"),
    ],
)
def test_status_parser_rejects_invalid_without_raw_message(raw):
    with pytest.raises(M.MemberFault, match=r"^DIAGNOSTIC$") as caught:
        M.parse_status(memoryview(raw), len(raw))
    assert caught.value.__context__ is None


class FakeOS:
    O_RDONLY, O_CLOEXEC, SEEK_SET = 0, 0x80000, 0

    def __init__(self) -> None:
        self.flags = {0: True, 1: True}
        self.closed: list[int] = []
        self.writes: list[bytes] = []
        self.chunks = [b"GO_IMPORTS\n"]
        self.write_steps: list[Any] = []

    def open(self, path: str, flags: int) -> int:
        assert (path, flags) == ("/proc/self/status", self.O_CLOEXEC)
        return 9

    def close(self, fd: int) -> None:
        self.closed.append(fd)

    def get_blocking(self, fd: int) -> bool:
        return self.flags[fd]

    def set_blocking(self, fd: int, value: bool) -> None:
        self.flags[fd] = value

    def lseek(self, fd: int, offset: int, whence: int) -> int:
        assert (fd, offset, whence) == (9, 0, 0)
        return 0

    def readv(self, fd: int, buffers: list[Any]) -> int:
        assert fd == 9
        buffers[0][: len(STATUS)] = STATUS
        return len(STATUS)

    def read(self, fd: int, size: int) -> bytes:
        assert fd == 0 and size <= 32
        return self.chunks.pop(0)

    def write(self, fd: int, data: Any) -> int:
        assert fd == 1
        step = self.write_steps.pop(0) if self.write_steps else len(data)
        if isinstance(step, BaseException):
            raise step
        self.writes.append(bytes(data[:step]))
        return step


def native_io(os_api: Any = None, **updates: Any) -> tuple[Any, Any]:
    os_api = os_api or FakeOS()
    clock = updates.pop("clock", lambda: 100.0)
    resource = SimpleNamespace(RLIMIT_AS=9, getrlimit=lambda _key: (128 << 20, 128 << 20))
    io = M.LinuxIO._with_apis(
        deadline=120.0,
        os_api=os_api,
        mmap_api=SimpleNamespace(),
        resource_api=resource,
        select_fn=lambda reads, writes, _errors, _timeout: (reads, writes, []),
        clock=clock,
        pid=7,
        ppid=1,
        **updates,
    )
    return io, os_api


def test_native_backend_partial_writes_eagain_readv_and_restore():
    io, os_api = native_io()
    assert os_api.flags == {0: False, 1: False}
    os_api.write_steps = [BlockingIOError(errno.EAGAIN, "private-data"), 3, 1]
    io.emit({"phase": "done"})
    assert b"".join(os_api.writes) == b'{"phase":"done"}\n'
    io.command(b"GO_IMPORTS\n")
    assert io.sample()[0]["peak"] == 126 << 20
    assert io.close() is True
    assert os_api.closed == [9]
    assert os_api.flags == {0: True, 1: True}


@pytest.mark.parametrize("chunks", [[b""], [b"GO_", b""], [b"GO_IMPORTS\nFINISH\n"], [b"OTHER\n"]])
def test_command_rejects_eof_partial_extra_or_wrong(chunks):
    io, os_api = native_io()
    os_api.chunks = chunks
    with pytest.raises(M.MemberFault):
        io.command(b"GO_IMPORTS\n")
    assert io.failed is True
    assert io.close() is True


def test_io_timeout_never_retries_past_deadline():
    ticks = iter([100.0, 120.0])
    io, _os_api = native_io(clock=lambda: next(ticks))
    with pytest.raises(M.MemberFault):
        io.write(b"hello\n")
    assert io.failed is True
    assert io.close() is True


def test_partial_construction_restores_flags_and_closes_fd(monkeypatch):
    os_api = FakeOS()
    original = os_api.set_blocking

    def fail(fd, value):
        original(fd, value)
        if fd == 1 and value is False:
            raise OSError("private-data")

    monkeypatch.setattr(os_api, "set_blocking", fail)
    with pytest.raises(M.MemberFault) as caught:
        native_io(os_api)
    assert caught.value.__context__ is None
    assert os_api.closed == [9]
    assert os_api.flags == {0: True, 1: True}


def test_real_factory_refuses_windows_before_open_or_import(monkeypatch):
    monkeypatch.setattr(M.sys, "platform", "win32")
    with pytest.raises(M.MemberFault):
        M.LinuxIO.from_linux(deadline=1)


class CoreChannel(FakeIO):
    """Commands come from the real core, not a second handwritten protocol."""

    def __init__(self, case: str) -> None:
        super().__init__(case)
        self.rows: list[list[Any]] = [[-1, ["sys", "stdlib", "builtin-or-frozen"]]]
        digest = P.inventory_digest(self.rows, PROBE.validate_inventory)
        self.core = P.PressureProtocol(
            case,
            "-" if case == "control" else digest,
            deadline=120.0,
            clock=lambda: 100.0,
            validator=PROBE.validate_inventory,
            pid=7,
        )
        self.last_sample = super().sample()
        self.core_commands: list[bytes] = []

    def command(self, expected: bytes) -> None:
        self.events.append(("command", expected))
        if expected == b"GO_IMPORTS\n":
            actual = self.commands.pop(0)
        elif expected.startswith(b"PRESSURE_"):
            actual = self.core.pressure(*self.last_sample)
        elif expected.startswith(b"RELEASE"):
            actual = self.core.release(*self.last_sample, anon=100 << 20, inventory=[1, 7])
        elif expected == b"FINISH\n":
            actual = self.core.finish()
        else:
            raise AssertionError("unexpected-command")
        self.core_commands.append(actual)
        assert actual == expected

    def sample(self) -> tuple[dict[str, int], list[int]]:
        self.last_sample = super().sample()
        return self.last_sample

    def emit(self, event: dict[str, Any]) -> None:
        super().emit(event)
        phase = event["phase"]
        if phase == "ready":
            self.commands = [self.core.ready(event["vm"], event["limits"], pid=7, ppid=1)]
        elif phase == "loaded":
            assert self.core.admit_imports(self.rows, event["vm"], event["limits"])
        elif phase == "released":
            vm, limits = self.last_sample
            self.last_sample = ({**vm, "size": 80 << 20}, limits)
            assert self.core.released(*self.last_sample, anon=60 << 20)

    def write(self, raw: Any) -> None:
        super().write(raw)
        assert self.core.held(bytes(raw)) == ("control_ok" if self.case == "control" else "imposed")


@pytest.mark.parametrize("case", ["control", "private", "shared"])
def test_member_driven_by_exact_commands_from_real_core(case):
    io = CoreChannel(case)
    assert M.run_member(case, io, imported) == 0
    assert io.core.completed(io.output[-1], eof=True, returncode=0, cleanup=True, inventory=[1])
    assert io.core.state == "DONE"
    assert io.core_commands[0] == b"GO_IMPORTS\n"
    assert io.core_commands[-1] == b"FINISH\n"


@pytest.mark.parametrize(
    "case,wrong", [("private", b"RELEASE_SHARED\n"), ("shared", b"RELEASE_PRIVATE\n")]
)
def test_wrong_allocator_release_keeps_payload_until_failure_cleanup(case, wrong):
    io = FakeIO(case)
    io.commands[2] = wrong
    assert M.run_member(case, io, imported) == 77
    held = io.events.index(("held", case))
    assert io.events[held + 1] == ("command", b"RELEASE_" + case.upper().encode() + b"\n")
    assert not any(item["phase"] == "released" for item in io.output)
    assert all(block.closed for block in io.blocks)


@pytest.mark.parametrize("command", [b"RELEASE_PRIVATE\n", b"RELEASE_SHARED\n"])
def test_linux_reader_accepts_only_exact_kind_specific_release(command):
    io, os_api = native_io()
    os_api.chunks = [command]
    io.command(command)
    assert io.close()
    io, os_api = native_io()
    os_api.chunks = [b"RELEASE\n"]
    with pytest.raises(M.MemberFault):
        io.command(command)
    assert io.close()


def test_generic_release_is_not_in_reader_command_allowlist():
    io, _os_api = native_io()
    with pytest.raises(M.MemberFault):
        io.command(b"RELEASE\n")
    assert io.failed and io.close()


def test_linux_allocator_apis_are_explicit_private_reserve_and_shared(monkeypatch):
    io, _os_api = native_io()
    calls: list[Any] = []
    io.mmap = SimpleNamespace(
        MAP_PRIVATE=2,
        MAP_SHARED=1,
        MAP_ANONYMOUS=32,
        PROT_READ=1,
        PROT_WRITE=2,
        mmap=lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    io.allocate_reserve()
    io.allocate("shared")
    assert calls == [
        ((-1, 2 << 20), {"flags": 34, "prot": 3}),
        ((-1, 4 << 20), {"flags": 33, "prot": 3}),
    ]
    monkeypatch.setattr(M, "bytearray", calls.append, raising=False)
    io.allocate("private")  # spy, no actual payload allocation
    assert calls[-1] == 4 << 20
    assert io.close()


def test_fd_close_failure_does_not_skip_flag_restoration(monkeypatch):
    io, os_api = native_io()

    def fail(_fd):
        raise OSError("private-data")

    monkeypatch.setattr(os_api, "close", fail)
    assert io.close() is False
    assert os_api.flags == {0: True, 1: True}


@pytest.mark.parametrize("index", [1, 2, 3, 4])
def test_sample_failure_after_allocation_never_emits_held(monkeypatch, index):
    io = FakeIO()
    original, count = io.sample, 0

    def sample():
        nonlocal count
        count += 1
        if count == index:
            raise MemoryError("private-data")
        return original()

    monkeypatch.setattr(io, "sample", sample)
    assert M.run_member("private", io, imported) == 77
    assert not any(row["phase"] == "held" for row in io.output)
    assert all(block.closed for block in io.blocks)


@pytest.mark.parametrize("index", [1, 2, 3, 4])
def test_limit_drift_at_any_sample_refuses_diagnostic(monkeypatch, index):
    io = FakeIO()
    original, count = io.sample, 0

    def sample():
        nonlocal count
        count += 1
        vm, limits = original()
        return vm, ([-1, -1] if count == index else limits)

    monkeypatch.setattr(io, "sample", sample)
    assert M.run_member("private", io, imported) == 77
    assert not any(row["phase"] == "held" for row in io.output)
    assert all(block.closed for block in io.blocks)
