"""Private bootstrap codec and lifecycle fakes. Never invokes Docker."""

import asyncio
import hashlib
import importlib
import os
import runpy
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def watchdog():
    """Independent bound: an asyncio cancellation bug must not hang pytest."""
    timer = threading.Timer(8.0, os._exit, args=(124,))
    timer.daemon = True
    timer.start()
    try:
        yield
    finally:
        timer.cancel()
        timer.join(0.5)
        assert not timer.is_alive()


@pytest.fixture
def module(monkeypatch: Any) -> Any:
    loaded = runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_channel.py"))
    monkeypatch.setitem(loaded["ManagedBootstrap"].start.__globals__, "PIPE_TYPE", Handle)
    return loaded


def target(module: Any) -> Any:
    return module["Target"](
        "c" * 64, "a" * 32, "sha256:" + "b" * 64, "d" * 64, module["Role"].CONTROLLER
    )


class Input:
    def __init__(self) -> None:
        self.closed = False
        self.received = bytearray()

    def write(self, data: bytes) -> None:
        self.received.extend(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        assert self.closed


class Handle:
    """Shape of the pinned windows_utils.PipeHandle, without any OS handle."""

    def __init__(self) -> None:
        self._handle: int | None = 100

    @property
    def handle(self) -> int | None:
        return self._handle

    def close(self) -> None:
        self._handle = None


class Process:
    def __init__(self) -> None:
        self.stdin = Input()
        self.stdout = asyncio.StreamReader()
        self.handles = {0: Handle(), 1: Handle()}
        self._transport = SimpleNamespace(
            get_pipe_transport=lambda fd: SimpleNamespace(
                get_extra_info=lambda key: self.handles[fd] if key == "pipe" else None
            )
        )
        self.returncode: int | None = None
        self.pid = 12345
        self.ended = asyncio.Event()
        self.kills = 0

    def kill(self) -> None:
        self.kills += 1
        self.finish(-9)

    def finish(self, code: int) -> None:
        self.returncode = code
        for handle in self.handles.values():
            handle.close()
        self.stdout.feed_eof()
        self.ended.set()

    async def wait(self) -> int:
        await self.ended.wait()
        assert self.returncode is not None
        return self.returncode


@pytest.mark.parametrize("length", [1, 8, 512, 16384])
@pytest.mark.parametrize("role", ["PG", "CONTROLLER"])
def test_seed_is_self_delimited_and_private(module, length, role):
    selected = getattr(module["Role"], role)
    body = (b"SEEDEND\n" * ((length // 8) + 1))[:length]
    seed = module["Seed"](selected, body)
    wire = seed.reveal_frame()
    assert len(wire) == length + 24 and len(wire[:16]) == 16
    assert wire[9:15] == f"{length:06d}".encode()
    output = module["decode_seed"](wire, selected)
    assert output.reveal() == body
    assert repr(seed) == "Seed(<private>)" and repr(output) == "PrivateOutput(<private>)"


@pytest.mark.parametrize("fault", ["zero", "oversize", "role", "sign", "short", "trailer", "extra"])
def test_seed_refuses_bad_frame_without_input_details(module, fault):
    role = module["Role"].CONTROLLER
    wire = module["Seed"](role, b"public-test").reveal_frame()
    if fault == "zero":
        wire = wire[:9] + b"000000" + wire[15:]
    elif fault == "oversize":
        wire = wire[:9] + b"016385" + wire[15:]
    elif fault == "role":
        role = module["Role"].PG
    elif fault == "sign":
        wire = wire[:9] + b"+00011" + wire[15:]
    elif fault == "short":
        wire = wire[:-1]
    elif fault == "trailer":
        wire = wire[:-8] + b"WRONGEND"
    else:
        wire += b"extra"
    with pytest.raises(module["BootstrapError"], match=r"^FRAME$"):
        module["decode_seed"](wire, role)


@pytest.mark.parametrize("chunk", [1, 7, 4096])
def test_container_reader_is_exact_and_does_not_wait_for_eof(module, monkeypatch, chunk):
    api = module["read_seed_fd"].__globals__
    role = module["Role"].CONTROLLER
    body = b"public-SEEDEND\n-canary"
    pending = bytearray(module["Seed"](role, body).reveal_frame())
    calls = []

    def read(fd, size):
        assert fd == 23 and size <= 4096 and pending
        calls.append(size)
        data = bytes(pending[: min(size, chunk)])
        del pending[: len(data)]
        return data

    monkeypatch.setitem(api, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setitem(api, "os", SimpleNamespace(read=read))
    monkeypatch.setitem(
        api, "select", SimpleNamespace(select=lambda *_args: ([23] if pending else [], [], []))
    )
    result = module["read_seed_fd"](23, role, module["time"].monotonic() + 1.0)
    assert result.reveal() == body and not pending
    assert calls[0] == 16


@pytest.mark.parametrize("defect", ["extra", "eof", "io", "deadline"])
def test_container_reader_refuses_visible_extra_partial_io_or_expired(module, monkeypatch, defect):
    api = module["read_seed_fd"].__globals__
    role = module["Role"].CONTROLLER
    pending = bytearray(module["Seed"](role, b"public-canary").reveal_frame())
    if defect == "extra":
        pending.extend(b"x")
    clock = [10.0]

    def read(_fd, size):
        if defect == "io":
            raise OSError("public-marker-must-not-escape")
        if defect == "eof":
            return b""
        data = bytes(pending[:size])
        del pending[: len(data)]
        return data

    def select(*_args):
        if defect == "deadline":
            clock[0] = 12.0
            return [], [], []
        return [23], [], []

    monkeypatch.setitem(api, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setitem(api, "os", SimpleNamespace(read=read))
    monkeypatch.setitem(api, "select", SimpleNamespace(select=select))
    monkeypatch.setitem(api, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    with pytest.raises(module["BootstrapError"], match=r"^FRAME$") as caught:
        module["read_seed_fd"](23, role, 11.0)
    assert caught.value.__cause__ is None and caught.value.__context__ is None


def test_late_spawn_cannot_use_a_cid_stop_fact_from_before_start(module, monkeypatch):
    """Red-first: a start request may complete after an apparently valid stop."""
    monkeypatch.setitem(module["ManagedBootstrap"].start.__globals__, "admit_runtime", lambda: None)
    monkeypatch.setitem(module["ManagedBootstrap"].start.__globals__, "OPEN_SECONDS", 0.02)

    async def scenario() -> None:
        owner = module["ManagedBootstrap"](target(module))
        process = Process()
        gate = asyncio.Event()
        container = {"running": False}

        async def spawn(*_args, **_kwargs):
            await gate.wait()
            container["running"] = True  # delayed docker start, AFTER the old stop fact
            return process

        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        with pytest.raises(module["BootstrapError"], match="DEADLINE"):
            await owner.start()
        stale = SimpleNamespace(cid=owner.target.cid, running=False, pid=0)
        gate.set()
        with pytest.raises(module["BootstrapError"], match="STATE"):
            await owner.close(stale)
        ticket = await owner.quiesce()
        assert ticket is not None and container["running"]
        assert not await owner.close()  # CLI reaped does not imply CID absent
        assert not process.stdin.received  # no private bytes, even on a late spawn
        assert not owner.metadata()["released"]
        container["running"] = False  # trusted external coordinator removes own CID
        absent = module["Absent"](ticket, module["time"].monotonic())
        assert await owner.close(absent)
        owner.assert_released()
        assert not [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]

    asyncio.run(scenario())


async def launch(
    module: Any,
    monkeypatch: Any,
    process: Any = None,
    role: str = "CONTROLLER",
    owners: list[Any] | None = None,
) -> tuple[Any, Any]:
    selected = target(module)
    if role == "PG":
        selected = module["Target"](
            selected.cid, selected.task, selected.image, selected.source_sha256, module["Role"].PG
        )
    owner = module["ManagedBootstrap"](selected)
    if owners is not None:
        owners.append(owner)
    process = Process() if process is None else process
    api = module["ManagedBootstrap"].start.__globals__
    monkeypatch.setitem(api, "admit_runtime", lambda: None)
    monkeypatch.setitem(api, "OPEN_SECONDS", 0.08)
    monkeypatch.setitem(api, "CLOSE_SECONDS", 0.08)
    monkeypatch.setitem(api, "PIPE_TYPE", Handle)

    async def spawn(*args, **kwargs):
        assert args[1:] == (
            "--context",
            "desktop-linux",
            "start",
            "--attach",
            "--interactive",
            selected.cid,
        )
        assert kwargs["stdin"] == module["subprocess"].PIPE
        assert kwargs["stdout"] == module["subprocess"].PIPE
        assert kwargs["stderr"] == module["subprocess"].DEVNULL
        assert "MASKGW_TEST_MARKER" not in kwargs["env"]
        return process

    monkeypatch.setenv("MASKGW_TEST_MARKER", "public-private-boundary-canary")
    monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
    await owner.start()
    return owner, process


async def collect(module: Any, owner: Any, process: Any) -> Any:
    ticket = await owner.quiesce()
    assert ticket is not None
    assert process.returncode is not None and process.stdin.closed
    assert not await owner.close()
    assert not owner.metadata()["released"]
    assert await owner.close(module["Absent"](ticket, module["time"].monotonic()))
    owner.assert_released()
    assert not [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    return ticket


@pytest.mark.parametrize("fragmented", [False, True])
def test_ready_then_single_seed_natural_exit_and_absence(module, monkeypatch, fragmented):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch)
        assert not process.stdin.received
        ready = owner.target.ready_line()
        for piece in [bytes([byte]) for byte in ready] if fragmented else [ready]:
            process.stdout.feed_data(piece)
            await asyncio.sleep(0)
        await owner.await_ready()
        seed = module["Seed"](owner.target.role, b"public-canary")
        await owner.send_seed(seed)
        assert bytes(process.stdin.received) == seed.reveal_frame()
        assert process.stdin.closed
        with pytest.raises(module["BootstrapError"], match="STATE"):
            await owner.send_seed(seed)
        process.stdout.feed_data(b"public-result")
        process.finish(0)
        output = await owner.drain()
        assert output.reveal() == b"public-result"
        assert "public-canary" not in repr(owner)
        assert "public-canary" not in str(owner.metadata())
        ticket = await collect(module, owner, process)
        assert await owner.quiesce() is ticket
        assert await owner.close(module["Absent"](ticket, module["time"].monotonic()))

    asyncio.run(scenario())


@pytest.mark.parametrize("defect", ["empty", "prefix", "keys", "role", "pid", "huge", "unicode"])
def test_bad_ready_never_receives_seed_and_keeps_draining(module, monkeypatch, defect):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch)
        good = owner.target.ready_line()
        bad = {
            "empty": b"\n",
            "prefix": b"unexpected\n" + good,
            "keys": good[:-2] + b',"extra":true}\n',
            "role": good.replace(b'"role":"C"', b'"role":"P"'),
            "pid": good.replace(b'"pid":1', b'"pid":2'),
            "huge": b"x" * 513,
            "unicode": b"\xff\n",
        }[defect]
        process.stdout.feed_data(bad)
        with pytest.raises(module["BootstrapError"], match="READY"):
            await owner.await_ready()
        process.stdout.feed_data(b"discard-after-error" * 32)
        await asyncio.sleep(0.01)
        assert not process.stdin.received
        assert owner.metadata()["retained_stdout_bytes"] == 0
        assert not process.stdout._buffer
        await collect(module, owner, process)

    asyncio.run(scenario())


def test_deadline_does_not_restart_for_partial_ready(module, monkeypatch):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch)
        process.stdout.feed_data(owner.target.ready_line()[:10])
        with pytest.raises(module["BootstrapError"], match="DEADLINE"):
            await owner.await_ready()
        assert not process.stdin.received
        await collect(module, owner, process)

    asyncio.run(scenario())


def test_stdout_limit_is_sticky_and_discard_drain_continues(module, monkeypatch):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch)
        process.stdout.feed_data(owner.target.ready_line())
        await owner.await_ready()
        await owner.send_seed(module["Seed"](owner.target.role, b"public-canary"))
        for _ in range(24):
            process.stdout.feed_data(b"x" * 4096)
            await asyncio.sleep(0)
        await asyncio.sleep(0.01)
        assert not process.stdout._buffer
        assert owner.metadata()["retained_stdout_bytes"] == 0
        process.finish(0)
        with pytest.raises(module["BootstrapError"], match="STDOUT_LIMIT"):
            await owner.drain()
        await collect(module, owner, process)

    asyncio.run(scenario())


def test_quiesce_rejects_old_or_other_ticket_and_all_future_operations(module, monkeypatch):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch)
        before = module["time"].monotonic() - 1.0  # earlier even on a coarse Windows clock
        ticket = await owner.quiesce()
        with pytest.raises(module["BootstrapError"], match="STATE"):
            module["Absent"](ticket, before)
        other = module["Quiesced"](ticket.cid, ticket.nonce, ticket.issued)
        with pytest.raises(module["BootstrapError"], match="STATE"):
            await owner.close(module["Absent"](other, module["time"].monotonic()))
        for method in (owner.start, owner.await_ready, owner.drain):
            with pytest.raises(module["BootstrapError"], match="STATE"):
                await method()
        with pytest.raises(module["BootstrapError"], match="STATE"):
            await owner.send_seed(module["Seed"](owner.target.role, b"public-canary"))
        with pytest.raises(module["BootstrapError"], match="STATE"):
            owner.retain()
        assert await owner.quiesce() is ticket
        await collect(module, owner, process)

    asyncio.run(scenario())


@pytest.mark.parametrize("point", ["write", "drain", "close", "wait_closed"])
def test_input_io_fault_is_sanitized_and_collectable(module, monkeypatch, point):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch)
        original = getattr(process.stdin, point)

        def fail_sync(*_args):
            raise OSError("public-marker-must-not-escape")

        async def fail_async():
            raise OSError("public-marker-must-not-escape")

        setattr(
            process.stdin, point, fail_async if point in ("drain", "wait_closed") else fail_sync
        )
        process.stdout.feed_data(owner.target.ready_line())
        await owner.await_ready()
        with pytest.raises(module["BootstrapError"], match=r"^IO$") as caught:
            await owner.send_seed(module["Seed"](owner.target.role, b"public-canary"))
        assert caught.value.__cause__ is None and caught.value.__context__ is None
        assert "public-canary" not in str(owner.metadata())
        setattr(process.stdin, point, original)
        await collect(module, owner, process)

    asyncio.run(scenario())


@pytest.mark.parametrize("name", ["spawn", "stdout", "wait", "feed", "input-close"])
def test_task_registration_failure_has_no_unowned_coroutine(module, monkeypatch, name):
    async def scenario() -> None:
        create = module["asyncio"].create_task
        failed = [False]

        def register(coroutine, *, name=None):
            if name == "maskgw-bootstrap-" + selected and not failed[0]:
                failed[0] = True
                raise RuntimeError("public-marker-must-not-escape")
            return create(coroutine, name=name)

        selected = name
        monkeypatch.setattr(module["asyncio"], "create_task", register)
        process = Process()
        if name in ("spawn", "stdout", "wait"):
            owners: list[Any] = []
            with pytest.raises(module["BootstrapError"], match=r"^IO$"):
                await launch(module, monkeypatch, process, owners=owners)
            owner = owners[0]
            ticket = await owner.quiesce()
            assert ticket is not None
            assert await owner.close(module["Absent"](ticket, module["time"].monotonic()))
            owner.assert_released()
            assert not [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        else:
            owner, process = await launch(module, monkeypatch, process)
            process.stdout.feed_data(owner.target.ready_line())
            await owner.await_ready()
            with pytest.raises(module["BootstrapError"], match=r"^IO$"):
                await owner.send_seed(module["Seed"](owner.target.role, b"public-canary"))
            await collect(module, owner, process)
        assert failed[0]

    asyncio.run(scenario())


@pytest.mark.parametrize("persistent", [False, True])
def test_kill_failure_retains_until_cli_is_proved_collected(module, monkeypatch, persistent):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch)
        # Exercise all three 250ms attempts; the other fake cases use an 80ms total.
        monkeypatch.setitem(module["ManagedBootstrap"].start.__globals__, "CLOSE_SECONDS", 0.85)
        original = process.kill
        attempts = [0]

        def kill():
            attempts[0] += 1
            if persistent or attempts[0] == 1:
                raise OSError("public-marker-must-not-escape")
            original()

        process.kill = kill
        ticket = await owner.quiesce()
        if persistent:
            assert ticket is None and process.returncode is None
            assert owner.metadata()["phase"] == "HELD"
            assert not await owner.close()
            with pytest.raises(module["BootstrapError"], match="HELD"):
                owner.assert_released()
        else:
            assert ticket is not None and process.returncode is not None
        process.kill = original
        await collect(module, owner, process)

    asyncio.run(scenario())


def test_read_error_cannot_turn_accumulated_success_prefix_into_success(module, monkeypatch):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch)
        process.stdout.feed_data(owner.target.ready_line())
        await owner.await_ready()
        await owner.send_seed(module["Seed"](owner.target.role, b"public-canary"))
        process.stdout.feed_data(b'{"ok":true}')
        await asyncio.sleep(0.01)
        original = process.stdout.read

        async def fail(_size):
            raise OSError("public-marker-must-not-escape")

        process.stdout.read = fail
        process.stdout.feed_data(b"untrusted-late-data")
        await asyncio.sleep(0.01)
        process.finish(0)
        with pytest.raises(module["BootstrapError"], match=r"^IO$"):
            await owner.drain()
        process.stdout.read = original
        await collect(module, owner, process)

    asyncio.run(scenario())


def test_backpressured_feed_is_reaped_without_cancelling_spawn(module, monkeypatch):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch)
        process.stdout.feed_data(owner.target.ready_line())
        await owner.await_ready()

        async def stalled():
            await process.ended.wait()
            raise BrokenPipeError("public-marker-must-not-escape")

        process.stdin.drain = stalled
        with pytest.raises(module["BootstrapError"], match=r"^DEADLINE$"):
            await owner.send_seed(module["Seed"](owner.target.role, b"p" * 16384))
        assert not owner._tasks["feed"].done()
        assert len(process.stdin.received) == 16408
        await collect(module, owner, process)
        assert owner._tasks["feed"].done()

    asyncio.run(scenario())


def test_pg_retains_attach_until_quiesce_and_absence(module, monkeypatch):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch, role="PG")
        process.stdout.feed_data(owner.target.ready_line())
        await owner.await_ready()
        await owner.send_seed(module["Seed"](owner.target.role, b"public-pg-canary"))
        with pytest.raises(module["BootstrapError"], match="STATE"):
            await owner.drain()
        owner.retain()
        assert process.returncode is None and not owner.metadata()["released"]
        await collect(module, owner, process)

    asyncio.run(scenario())


def test_pending_spawn_is_not_cancelled_and_has_no_ticket_or_release(module, monkeypatch):
    async def scenario() -> None:
        owner = module["ManagedBootstrap"](target(module))
        process = Process()
        gate = asyncio.Event()
        api = module["ManagedBootstrap"].start.__globals__
        monkeypatch.setitem(api, "admit_runtime", lambda: None)
        monkeypatch.setitem(api, "OPEN_SECONDS", 0.01)
        monkeypatch.setitem(api, "CLOSE_SECONDS", 0.01)

        async def spawn(*_args, **_kwargs):
            await gate.wait()
            return process

        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        with pytest.raises(module["BootstrapError"], match="DEADLINE"):
            await owner.start()
        assert await owner.quiesce() is None
        assert owner.metadata()["phase"] == "HELD"
        assert not owner._tasks["spawn"].cancelled()
        with pytest.raises(module["BootstrapError"], match="HELD"):
            owner.assert_released()
        gate.set()
        await collect(module, owner, process)
        assert not process.stdin.received

    asyncio.run(scenario())


@pytest.mark.parametrize("point", ["input", "stdout"])
@pytest.mark.parametrize("closed", [False, True])
def test_sticky_pipe_error_needs_positive_handle_closure(module, monkeypatch, point, closed):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch)
        process.stdout.feed_data(owner.target.ready_line())
        await owner.await_ready()
        original = process.stdin.wait_closed if point == "input" else process.stdout.read

        async def fail(*_args):
            raise BrokenPipeError("public-marker-must-not-escape")

        if point == "input":
            process.stdin.wait_closed = fail
        else:
            process.stdout.read = fail
            process.stdout.feed_data(b"public-wakeup-before-error")
            await asyncio.sleep(0.01)
        process.finish(0)
        process.handles[0 if point == "input" else 1]._handle = None if closed else 100
        try:
            ticket = await owner.quiesce()
            if closed:
                assert ticket is not None and owner.metadata()["fault"] == "IO"
            else:
                assert ticket is None and not owner.metadata()["released"]
        finally:
            if point == "input":
                process.stdin.wait_closed = original
            else:
                process.stdout.read = original
            process.handles[0 if point == "input" else 1].close()
            await collect(module, owner, process)

    asyncio.run(scenario())


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows PipeHandle unit")
def test_pinned_native_windows_pipe_handle_has_explicit_closed_state():
    """Two anonymous handles only; no process, Docker, network or private bytes."""
    utils = importlib.import_module("asyncio.windows_utils")
    read_handle, write_handle = utils.pipe()
    reader = utils.PipeHandle(read_handle)
    writer = utils.PipeHandle(write_handle)
    try:
        assert type(reader) is utils.PipeHandle and type(writer) is utils.PipeHandle
        read_number, write_number = reader.handle, writer.handle
        assert type(read_number) is int and type(write_number) is int
        assert reader.fileno() == reader.handle and writer.fileno() == writer.handle
        assert not hasattr(reader, "closed")  # do not model a nonexistent attribute
    finally:
        reader.close()
        writer.close()
    assert reader.handle is None and writer.handle is None
    with pytest.raises(ValueError, match="closed pipe"):
        reader.fileno()


@pytest.mark.skipif(sys.platform != "win32", reason="native pinned Windows stdlib")
@pytest.mark.parametrize(
    "name",
    [
        "windows_utils.py",
        "proactor_events.py",
        "base_subprocess.py",
        "windows_events.py",
        "streams.py",
        "subprocess.py",
    ],
)
def test_native_stdlib_coupling_matches_recorded_source_pins(module, name):
    assert sys.version_info[:3] == (3, 11, 3)
    raw = (module["STDLIB"] / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == module["STDLIB_PINS"][name]


@pytest.mark.parametrize("phase", ["start", "send", "drain"])
def test_external_cancellation_propagates_without_abandoning_owned_tasks(
    module, monkeypatch, phase
):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch)
        gate = asyncio.Event()
        if phase == "start":
            # Reuse the adopted process in a new owner so start itself is cancellable.
            await collect(module, owner, process)
            process = Process()
            owner = module["ManagedBootstrap"](target(module))

            async def spawn(*_args, **_kwargs):
                await gate.wait()
                return process

            monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
            pending = asyncio.create_task(owner.start())
        else:
            process.stdout.feed_data(owner.target.ready_line())
            await owner.await_ready()
            if phase == "send":

                async def blocked():
                    await process.ended.wait()

                process.stdin.drain = blocked
                pending = asyncio.create_task(
                    owner.send_seed(module["Seed"](owner.target.role, b"public-canary"))
                )
            else:
                await owner.send_seed(module["Seed"](owner.target.role, b"public-canary"))
                process.returncode = 0
                process.ended.set()  # process exited but stdout not yet terminal
                pending = asyncio.create_task(owner.drain())
        await asyncio.sleep(0.01)
        pending.cancel()
        try:
            with pytest.raises(asyncio.CancelledError):
                await pending
            if phase == "send":
                assert process.stdin.received
                assert owner.metadata()["seed_delivery"] == "UNKNOWN"
        finally:
            gate.set()
            if process.returncode is not None:
                process.finish(process.returncode)
            await collect(module, owner, process)

    asyncio.run(scenario())


def test_cancel_before_write_records_not_sent_and_never_sends_later(module, monkeypatch):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch)
        process.stdout.feed_data(owner.target.ready_line())
        await owner.await_ready()
        gate = asyncio.Event()
        entered = asyncio.Event()
        original = owner._feed

        async def delayed(seed):
            entered.set()
            await gate.wait()
            await original(seed)

        owner._feed = delayed
        pending = asyncio.create_task(
            owner.send_seed(module["Seed"](owner.target.role, b"public-canary"))
        )
        await entered.wait()
        pending.cancel()
        try:
            with pytest.raises(asyncio.CancelledError):
                await pending
            assert owner.metadata()["seed_delivery"] == "NOT_SENT"
        finally:
            gate.set()
            await collect(module, owner, process)
        assert not process.stdin.received

    asyncio.run(scenario())


def test_cancel_input_close_after_write_records_unknown(module, monkeypatch):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch)
        process.stdout.feed_data(owner.target.ready_line())
        await owner.await_ready()
        entered = asyncio.Event()

        async def closing():
            entered.set()
            await process.ended.wait()

        process.stdin.wait_closed = closing
        pending = asyncio.create_task(
            owner.send_seed(module["Seed"](owner.target.role, b"public-canary"))
        )
        await entered.wait()
        pending.cancel()
        try:
            with pytest.raises(asyncio.CancelledError):
                await pending
            assert owner.metadata()["seed_delivery"] == "UNKNOWN"
        finally:
            await collect(module, owner, process)

    asyncio.run(scenario())


def test_cancelled_internal_task_is_not_caller_cancellation(module):
    async def scenario() -> None:
        owner = module["ManagedBootstrap"](target(module))
        owner._bind()
        pending = asyncio.create_task(asyncio.sleep(10.0))
        owner._tasks["unit-cancelled"] = pending
        pending.cancel()
        assert await owner._until(pending, module["time"].monotonic() + 0.1)
        current = asyncio.current_task()
        assert current is not None and current.cancelling() == 0
        ticket = await owner.quiesce()
        assert ticket is not None
        assert await owner.close(module["Absent"](ticket, module["time"].monotonic()))
        owner.assert_released()

    asyncio.run(scenario())


def test_cancelled_quiesce_remains_held_and_collects_late_spawn(module, monkeypatch):
    async def scenario() -> None:
        api = module["ManagedBootstrap"].start.__globals__
        monkeypatch.setitem(api, "admit_runtime", lambda: None)
        monkeypatch.setitem(api, "OPEN_SECONDS", 0.01)
        monkeypatch.setitem(api, "CLOSE_SECONDS", 0.08)
        owner = module["ManagedBootstrap"](target(module))
        process = Process()
        gate = asyncio.Event()

        async def spawn(*_args, **_kwargs):
            await gate.wait()
            return process

        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        with pytest.raises(module["BootstrapError"], match="DEADLINE"):
            await owner.start()
        pending = asyncio.create_task(owner.quiesce())
        await asyncio.sleep(0.01)
        pending.cancel()
        try:
            with pytest.raises(asyncio.CancelledError):
                await pending
            assert owner.metadata()["phase"] == "HELD" and owner._ticket is None
            assert not owner._tasks["spawn"].cancelled()
        finally:
            gate.set()
            await collect(module, owner, process)

    asyncio.run(scenario())


@pytest.mark.parametrize("fd", [0, 1])
def test_missing_or_wrong_pipe_type_is_not_positive_closure(module, monkeypatch, fd):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch)
        process.finish(0)
        original = process.handles[fd]
        process.handles[fd] = SimpleNamespace(handle=None)
        try:
            assert await owner.quiesce() is None
            assert not owner.metadata()["released"]
        finally:
            process.handles[fd] = original
            await collect(module, owner, process)

    asyncio.run(scenario())


@pytest.mark.parametrize("persistent", [False, True])
def test_wait_error_requires_successful_reap_before_ticket(module, monkeypatch, persistent):
    async def scenario() -> None:
        process = Process()
        original = process.wait
        attempts = [0]

        async def wait():
            attempts[0] += 1
            if persistent or attempts[0] == 1:
                raise OSError("public-marker-must-not-escape")
            return await original()

        monkeypatch.setattr(process, "wait", wait)
        owner, process = await launch(module, monkeypatch, process)
        await asyncio.sleep(0.01)
        try:
            ticket = await owner.quiesce()
            if persistent:
                assert ticket is None and not owner._waited
            else:
                assert ticket is not None
        finally:
            process.wait = original
            await collect(module, owner, process)

    asyncio.run(scenario())


@pytest.mark.parametrize("fd", [0, 1])
def test_deferred_handle_callback_is_collected_in_same_quiesce(module, monkeypatch, fd):
    async def scenario() -> None:
        owner, process = await launch(module, monkeypatch)
        process.finish(0)
        process.handles[fd]._handle = 100
        asyncio.get_running_loop().call_later(0.02, process.handles[fd].close)
        try:
            assert await owner.quiesce() is not None
        finally:
            await asyncio.sleep(0.03)
            await collect(module, owner, process)

    asyncio.run(scenario())


@pytest.mark.parametrize("point", ["runtime", "spawn"])
def test_admission_and_spawn_exceptions_are_closed_categories(module, monkeypatch, point):
    async def scenario() -> None:
        api = module["ManagedBootstrap"].start.__globals__

        def admit():
            if point == "runtime":
                raise OSError("public-marker-must-not-escape")

        async def spawn(*_args, **_kwargs):
            raise OSError("public-marker-must-not-escape")

        monkeypatch.setitem(api, "admit_runtime", admit)
        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        owner = module["ManagedBootstrap"](target(module))
        with pytest.raises(module["BootstrapError"], match=point.upper()) as caught:
            await owner.start()
        assert caught.value.__cause__ is None and caught.value.__context__ is None
        ticket = await owner.quiesce()
        assert ticket is not None and owner.metadata()["seed_delivery"] == "NOT_SENT"
        assert await owner.close(module["Absent"](ticket, module["time"].monotonic()))
        owner.assert_released()

    asyncio.run(scenario())


def test_public_environment_drops_upstream_python_and_maskgw_values(module, monkeypatch):
    for name in ("MASKGW_TEST_DSN", "PGPASSWORD", "DSN", "PYTHONPATH", "MASKGW_KEY"):
        monkeypatch.setenv(name, "public-marker-must-not-escape")
    environment = module["environment"]()
    assert len(environment) <= 13
    assert "public-marker-must-not-escape" not in str(environment)
