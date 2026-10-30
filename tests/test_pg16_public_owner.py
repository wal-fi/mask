"""Public owner lifecycle fakes; no native subprocess, Docker or private input."""

import asyncio
import hashlib
import runpy
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_w1_bootstrap_channel import (
    Handle,
    Input,
    Process,
    watchdog,  # noqa: F401 - independent pytest bound
)

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def module(monkeypatch: pytest.MonkeyPatch) -> Any:
    value = runpy.run_path(str(REPO / "docs/poc/pg16_public_owner.py"))
    channel = value["C"]
    monkeypatch.setitem(channel, "PIPE_TYPE", Handle)
    monkeypatch.setitem(channel, "CLOSE_SECONDS", 0.05)
    monkeypatch.setitem(channel, "admit_runtime", lambda: None)
    return value


def target(module: Any) -> Any:
    task = "a" * 32
    profile, channel = module["P"], module["C"]
    source = profile["blueprint"](task)[0][-1].encode("ascii")
    return channel["Target"](
        "c" * 64, task, profile["IMAGE"], hashlib.sha256(source).hexdigest(), channel["Role"].PG
    )


def process() -> Any:
    value: Any = Process()
    value.stdin = None
    transport = value._transport
    value._transport = SimpleNamespace(
        get_pipe_transport=lambda fd: None if fd == 0 else transport.get_pipe_transport(fd)
    )
    return value


async def release(owner: Any, module: Any) -> None:
    ticket = await owner.quiesce()
    assert ticket is not None and all(task.done() for task in owner._tasks.values())
    assert await owner.close(module["C"]["Absent"](ticket, module["time"].monotonic()))
    owner.assert_released()


def test_exact_eight_overrides_and_remaining_lifecycle_is_same_object(module):
    cls, base = module["PublicProbeOwner"], module["C"]["ManagedBootstrap"]
    assert {name for name in cls.__dict__ if callable(getattr(base, name, None))} == {
        "__init__",
        "_pipe_closed",
        "_pump",
        "start",
        "drain",
        "await_ready",
        "send_seed",
        "retain",
    }
    for name in (
        "_adopt",
        "_task",
        "_until",
        "_ensure_pumps",
        "_wait",
        "_close_input",
        "quiesce",
        "_issue_ticket",
        "close",
        "metadata",
        "assert_released",
    ):
        assert getattr(cls, name) is getattr(base, name)


def test_fixed_spawn_runtime_admission_and_normal_eof_have_no_spurious_io(module, monkeypatch):
    channel = module["C"]
    calls = []
    monkeypatch.setitem(channel, "admit_runtime", lambda: calls.append("admit"))
    monkeypatch.setenv("MASKGW_TEST_DSN", "fake-private-canary")
    monkeypatch.setenv("PYTHONPATH", "fake-private-canary")

    async def scenario() -> None:
        owner = module["PublicProbeOwner"](target(module))
        child = process()

        async def spawn(*args, **kwargs):
            calls.append("spawn")
            assert calls == ["admit", "spawn"]
            assert args[-3:] == ("start", "--attach", owner.target.cid)
            assert "--interactive" not in args
            assert kwargs["stdin"] == kwargs["stderr"] == subprocess.DEVNULL
            assert kwargs["stdout"] == subprocess.PIPE
            assert "MASKGW_TEST_DSN" not in kwargs["env"] and "PYTHONPATH" not in kwargs["env"]
            child.stdout.feed_data(b"public-report\n")
            child.finish(0)
            return child

        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        await owner.start()
        code, output = await owner.drain()
        assert code == 0 and output.reveal() == b"public-report\n"
        assert owner._stdin_closed and owner.fault is None
        assert owner.metadata()["seed_delivery"] == "NOT_SENT"
        await release(owner, module)
        assert owner.fault is None and child.kills == 0

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "code,body",
    [
        (42, b"fault=TOOLS\n"),
        (42, b"fault=UID\n"),
        (42, b"fault=OS\n"),
        (42, b"fault=MOUNTS\n"),
        (42, b"fault=VERSION\n"),
        (42, b"fault=TOOLS\nextra\n"),
        (137, b"not-success\n"),
    ],
)
def test_container_exit_and_complete_output_reach_parser_without_generic_exit(
    module, monkeypatch, code, body
):
    async def scenario() -> None:
        child = process()
        child.stdout.feed_data(body)
        child.finish(code)

        async def spawn(*_args, **_kwargs):
            return child

        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        owner = module["PublicProbeOwner"](target(module))
        await owner.start()
        actual, output = await owner.drain()
        assert actual == code and output.reveal() == body and owner.fault is None
        await release(owner, module)

    asyncio.run(scenario())


@pytest.mark.parametrize("method", ["ready", "seed", "retain"])
def test_private_protocol_methods_refuse_before_any_effect(module, method):
    async def scenario() -> None:
        owner = module["PublicProbeOwner"](target(module))
        with pytest.raises(module["C"]["BootstrapError"], match="STATE"):
            if method == "ready":
                await owner.await_ready()
            elif method == "seed":
                await owner.send_seed(object())
            else:
                owner.retain()
        assert owner.phase == "NEW" and owner._tasks == {} and owner._process is None
        await release(owner, module)

    asyncio.run(scenario())


def test_excess_output_is_discarded_and_never_becomes_a_success_prefix(module, monkeypatch):
    async def scenario() -> None:
        child = process()
        child.stdout.feed_data(b"x" * 65536)
        child.finish(0)

        async def spawn(*_args, **_kwargs):
            return child

        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        owner = module["PublicProbeOwner"](target(module))
        await owner.start()
        with pytest.raises(module["C"]["BootstrapError"], match="STDOUT_LIMIT"):
            await owner.drain()
        assert owner.metadata()["retained_stdout_bytes"] == 0
        await release(owner, module)

    asyncio.run(scenario())


def test_io_after_prefix_never_returns_output(module, monkeypatch):
    async def scenario() -> None:
        child = process()
        calls = [0]

        async def read(_size):
            calls[0] += 1
            if calls[0] == 1:
                return b"partial-success\n"
            raise OSError("fake-private-canary")

        child.stdout.read = read
        child.finish(0)

        async def spawn(*_args, **_kwargs):
            return child

        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        owner = module["PublicProbeOwner"](target(module))
        await owner.start()
        with pytest.raises(module["C"]["BootstrapError"], match="IO") as caught:
            await owner.drain()
        assert "fake-private-canary" not in str(caught.value)
        assert owner.metadata()["retained_stdout_bytes"] == 0
        await release(owner, module)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "fault", ["stdin-present", "stdin-transport", "stdout-open", "stdout-unknown"]
)
def test_unproven_input_or_stdout_handle_prevents_ticket(module, monkeypatch, fault):
    async def scenario() -> None:
        child = process()
        child.finish(0)
        old = child._transport.get_pipe_transport
        if fault == "stdin-present":
            child.stdin = Input()
        elif fault == "stdin-transport":
            child._transport.get_pipe_transport = lambda fd: object() if fd == 0 else old(fd)
        elif fault == "stdout-open":
            child.handles[1]._handle = 100
        else:
            child._transport.get_pipe_transport = lambda _fd: None

        async def spawn(*_args, **_kwargs):
            return child

        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        owner = module["PublicProbeOwner"](target(module))
        await owner.start()
        assert await owner.quiesce() is None and owner.phase == "HELD"
        assert not owner.metadata()["released"]
        child.stdin = None
        child.handles[1].close()
        child._transport.get_pipe_transport = lambda fd: (
            None if fd == 0 else SimpleNamespace(get_extra_info=lambda _key: child.handles[1])
        )
        await release(owner, module)

    asyncio.run(scenario())


def test_late_spawn_is_adopted_with_devnull_proof_before_cleanup(module, monkeypatch):
    monkeypatch.setitem(
        module["PublicProbeOwner"].start.__wrapped__.__globals__, "OPEN_SECONDS", 0.02
    )

    async def scenario() -> None:
        child = process()
        gate = asyncio.Event()

        async def spawn(*_args, **_kwargs):
            await gate.wait()
            return child

        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        owner = module["PublicProbeOwner"](target(module))
        with pytest.raises(module["C"]["BootstrapError"], match="DEADLINE"):
            await owner.start()
        assert await owner.quiesce() is None
        gate.set()
        await asyncio.sleep(0)
        await release(owner, module)
        assert owner.fault is module["C"]["Fault"].DEADLINE
        assert child.kills > 0 and owner._stdin_closed

    asyncio.run(scenario())


def test_caller_cancellation_retains_pending_spawn_until_collected(module, monkeypatch):
    async def scenario() -> None:
        child = process()
        gate = asyncio.Event()

        async def spawn(*_args, **_kwargs):
            await gate.wait()
            return child

        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        owner = module["PublicProbeOwner"](target(module))
        task = asyncio.create_task(owner.start())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not owner._tasks["spawn"].cancelled() and owner._busy is False
        gate.set()
        await asyncio.sleep(0)
        await release(owner, module)

    asyncio.run(scenario())


def test_drain_does_not_approve_a_complete_buffer_after_absolute_deadline(module, monkeypatch):
    async def scenario() -> None:
        child = process()
        child.stdout.feed_data(b"public-report\n")
        child.finish(0)

        async def spawn(*_args, **_kwargs):
            return child

        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        owner = module["PublicProbeOwner"](target(module))
        await owner.start()
        await asyncio.gather(*owner._tasks.values())
        assert owner._waited and owner._stdout_eof
        owner._opened = module["time"].monotonic() - 13.0
        with pytest.raises(module["C"]["BootstrapError"], match="DEADLINE"):
            await owner.drain()
        await release(owner, module)

    asyncio.run(scenario())


def test_continuous_output_is_stopped_without_waiting_for_producer_eof(module, monkeypatch):
    async def scenario() -> None:
        child = process()

        async def read(_size):
            await asyncio.sleep(0)
            return b"x" * 4096 if child.returncode is None else b""

        child.stdout.read = read

        async def spawn(*_args, **_kwargs):
            return child

        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        owner = module["PublicProbeOwner"](target(module))
        await owner.start()
        with pytest.raises(module["C"]["BootstrapError"], match="STDOUT_LIMIT"):
            await owner.drain()
        assert child.returncode is None and owner.metadata()["retained_stdout_bytes"] == 0
        await release(owner, module)
        assert child.kills > 0

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "point,category", [("runtime", "RUNTIME"), ("spawn", "SPAWN"), ("task", "IO")]
)
def test_failures_before_native_ownership_are_sanitized_and_collected(
    module, monkeypatch, point, category
):
    async def scenario() -> None:
        calls = []

        def fail_runtime():
            raise OSError("fake-private-canary")

        async def spawn(*_args, **_kwargs):
            calls.append("spawn")
            raise OSError("fake-private-canary")

        if point == "runtime":
            monkeypatch.setitem(module["C"], "admit_runtime", fail_runtime)
        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        original = module["asyncio"].create_task

        def create_task(coroutine, **kwargs):
            if kwargs.get("name") == "maskgw-bootstrap-spawn":
                raise RuntimeError("fake-private-canary")
            return original(coroutine, **kwargs)

        if point == "task":
            monkeypatch.setattr(module["asyncio"], "create_task", create_task)
        owner = module["PublicProbeOwner"](target(module))
        with pytest.raises(module["C"]["BootstrapError"], match=category) as caught:
            await owner.start()
        assert caught.value.__context__ is None and "fake-private-canary" not in str(caught.value)
        assert calls == (["spawn"] if point == "spawn" else [])
        await release(owner, module)

    asyncio.run(scenario())


@pytest.mark.parametrize("field", ["image", "role", "source"])
def test_only_the_exact_public_pg_target_is_accepted(module, field):
    wanted = target(module)
    channel = module["C"]
    candidate = channel["Target"](
        wanted.cid,
        wanted.task,
        "sha256:" + "b" * 64 if field == "image" else wanted.image,
        "0" * 64 if field == "source" else wanted.source_sha256,
        channel["Role"].CONTROLLER if field == "role" else wanted.role,
    )
    with pytest.raises(channel["BootstrapError"], match="STATE"):
        module["PublicProbeOwner"](candidate)


def test_expired_runtime_admission_cannot_register_a_late_spawn(module, monkeypatch):
    async def scenario() -> None:
        child = process()
        clock = [10.0]
        fake_time = SimpleNamespace(monotonic=lambda: clock[0])
        monkeypatch.setitem(
            module["PublicProbeOwner"].start.__wrapped__.__globals__, "time", fake_time
        )
        monkeypatch.setitem(module["C"], "time", fake_time)

        def admit():
            clock[0] = 23.0

        monkeypatch.setitem(module["C"], "admit_runtime", admit)

        async def spawn(*_args, **_kwargs):
            return child

        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        owner = module["PublicProbeOwner"](target(module))
        with pytest.raises(module["C"]["BootstrapError"], match="DEADLINE"):
            await owner.start()
        before_collection = tuple(owner._tasks)
        await release(owner, module)
        assert before_collection == ()

    asyncio.run(scenario())
