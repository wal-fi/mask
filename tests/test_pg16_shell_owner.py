"""Public reader channel lifecycle fakes. No shell, Docker or native child."""

import asyncio
import dataclasses
import hashlib
import json
import runpy
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.test_w1_bootstrap_channel import (
    Handle,
    Process,
    watchdog,  # noqa: F401 - independent watchdog for lifecycle fakes
)

REPO = Path(__file__).resolve().parents[1]
TASK, CID = "a" * 32, "c" * 64


@pytest.fixture
def module(monkeypatch: pytest.MonkeyPatch) -> Any:
    value = runpy.run_path(str(REPO / "docs/poc/pg16_shell_owner.py"))
    monkeypatch.setitem(value["C"], "PIPE_TYPE", Handle)
    monkeypatch.setitem(value["C"], "CLOSE_SECONDS", 0.05)
    monkeypatch.setitem(value["C"], "admit_runtime", lambda: None)
    return value


async def begin(module: Any, monkeypatch: Any, name: str = "BINARY") -> tuple[Any, Any]:
    owner = module["PublicReaderOwner"](TASK, CID, getattr(module["R"]["Case"], name))
    child = Process()

    async def spawn(*args: Any, **kwargs: Any) -> Any:
        assert args[-4:] == ("start", "--attach", "--interactive", CID)
        assert kwargs["stdin"] == kwargs["stdout"] == subprocess.PIPE
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert "MASKGW_TEST_DSN" not in kwargs["env"] and "PYTHONPATH" not in kwargs["env"]
        child.stdout.feed_data(owner.target.ready_line())
        return child

    monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
    await owner.start()
    await owner.await_ready()
    return owner, child


def output_for(module: Any, owner: Any) -> tuple[int, bytes]:
    vector = owner._vector
    if vector.fault is not None:
        return 42, f"fault={vector.fault.value}\n".encode("ascii")
    value = module["R"]["expected_report"](TASK, vector.case)
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
    return 0, raw


async def release(owner: Any, module: Any) -> None:
    ticket = await owner.quiesce()
    assert ticket is not None and all(task.done() for task in owner._tasks.values())
    assert await owner.close(module["C"]["Absent"](ticket, module["time"].monotonic()))
    owner.assert_released()


def test_exact_overrides_preserve_original_spawn_cancel_collection_and_handles(module):
    cls, base = module["PublicReaderOwner"], module["C"]["ManagedBootstrap"]
    assert {name for name in cls.__dict__ if callable(getattr(base, name, None))} == {
        "__init__",
        "_pump",
        "send_seed",
        "retain",
        "drain",
    }
    for name in (
        "start",
        "_task",
        "_until",
        "_adopt",
        "_ensure_pumps",
        "_wait",
        "_pipe_closed",
        "_close_input",
        "quiesce",
        "_issue_ticket",
        "close",
        "metadata",
        "assert_released",
    ):
        assert getattr(cls, name) is getattr(base, name)


@pytest.mark.parametrize("name", ["ONE", "BINARY", "FRAGMENTED", "HEADER_NUL", "EXTRA_NUL"])
def test_exact_public_wire_and_exit_reach_parser_after_eof(module, monkeypatch, name):
    monkeypatch.setenv("MASKGW_TEST_DSN", "public-test-marker")
    monkeypatch.setenv("PYTHONPATH", "public-test-marker")

    async def scenario() -> None:
        owner, child = await begin(module, monkeypatch, name)
        code, raw = output_for(module, owner)
        old_close = child.stdin.close

        def close() -> None:
            old_close()
            child.stdout.feed_data(raw)
            child.finish(code)

        child.stdin.close = close
        await owner.send_vector()
        observed = await owner.drain()
        assert bytes(child.stdin.received) == owner._vector.wire
        assert child.stdin.closed and observed.returncode == code
        assert observed.report_bytes == len(raw) and observed.output == raw
        assert observed.stdout_bytes == len(owner.target.ready_line()) + len(raw)
        assert module["R"]["parse_report"](raw, observed.returncode, TASK, owner._vector.case)[
            "ok"
        ] is (code == 0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            observed.returncode = 99
        assert owner.wrapper_sha256 == hashlib.sha256(owner.wrapper.encode("ascii")).hexdigest()
        assert owner.metadata()["seed_delivery"] == "SENT" and owner.fault is None
        await release(owner, module)

    asyncio.run(scenario())


@pytest.mark.parametrize("name", ["RETAIN", "WAIT_HEADER", "WAIT_BODY", "WAIT_TRAILER"])
def test_hold_open_survives_feed_and_closes_only_after_actual_process_exit(
    module, monkeypatch, name
):
    async def scenario() -> None:
        owner, child = await begin(module, monkeypatch, name)
        await owner.send_vector()
        assert not child.stdin.closed and child.returncode is None and not owner._stdin_closed
        code, raw = output_for(module, owner)
        child.stdout.feed_data(raw)
        child.finish(code)
        observed = await owner.drain()
        assert child.stdin.closed and owner._stdin_closed and observed.returncode == code
        assert observed.output == raw and owner.fault is None
        await release(owner, module)

    asyncio.run(scenario())


def test_vector_is_not_sent_before_ready_or_twice_and_private_api_refuses(module, monkeypatch):
    async def scenario() -> None:
        owner = module["PublicReaderOwner"](TASK, CID, module["R"]["Case"].ONE)
        with pytest.raises(module["C"]["BootstrapError"], match="STATE"):
            await owner.send_vector()
        with pytest.raises(module["C"]["BootstrapError"], match="STATE"):
            await owner.send_seed(object())
        with pytest.raises(module["C"]["BootstrapError"], match="STATE"):
            owner.retain()
        assert owner.phase == "NEW" and owner._tasks == {}
        owner, child = await begin(module, monkeypatch, "RETAIN")
        await owner.send_vector()
        amount = len(child.stdin.received)
        with pytest.raises(module["C"]["BootstrapError"], match="STATE"):
            await owner.send_vector()
        assert len(child.stdin.received) == amount
        await release(owner, module)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "task,cid,name", [("A" * 32, CID, "ONE"), (TASK, "x", "ONE"), (TASK, CID, "raw")]
)
def test_invalid_input_refused_before_spawn_or_template_injection(module, task, cid, name):
    case = getattr(module["R"]["Case"], name, name)
    with pytest.raises((module["R"]["ReaderError"], module["C"]["BootstrapError"])):
        module["PublicReaderOwner"](task, cid, case)


def test_fragmentation_cannot_renew_deadline_or_write_after_quiesce(module, monkeypatch):
    async def scenario() -> None:
        owner, child = await begin(module, monkeypatch, "FRAGMENTED")
        old_drain = child.stdin.drain
        calls = []

        async def drain() -> None:
            calls.append(True)
            await old_drain()
            owner._quiescing = True

        child.stdin.drain = drain
        with pytest.raises(module["C"]["BootstrapError"], match="DEADLINE"):
            await owner.send_vector()
        assert len(calls) == 1 and bytes(child.stdin.received) == owner._vector.chunks[0]
        assert owner.metadata()["seed_delivery"] == "UNKNOWN"
        await release(owner, module)

    asyncio.run(scenario())


def test_container_fault_deadline_is_not_host_cli_deadline(module, monkeypatch):
    async def scenario() -> None:
        owner, child = await begin(module, monkeypatch, "WAIT_BODY")
        await owner.send_vector()
        code, raw = output_for(module, owner)
        assert code == 42 and raw == b"fault=DEADLINE\n"
        child.stdout.feed_data(raw)
        child.finish(code)
        # Logical clock: reader already emitted at 8s; CLI/EOF now observed after 12s.
        owner._opened = module["time"].monotonic() - 13.0
        with pytest.raises(module["C"]["BootstrapError"], match="DEADLINE"):
            await owner.drain()
        await release(owner, module)

    asyncio.run(scenario())


@pytest.mark.parametrize("code", [1, 137, -9, True])
def test_other_exit_is_never_a_transport_success(module, monkeypatch, code):
    async def scenario() -> None:
        owner, child = await begin(module, monkeypatch, "RETAIN")
        await owner.send_vector()
        _, raw = output_for(module, owner)
        child.stdout.feed_data(raw)
        child.finish(code)
        with pytest.raises(module["C"]["BootstrapError"], match="EXIT"):
            await owner.drain()
        await release(owner, module)

    asyncio.run(scenario())


@pytest.mark.parametrize("defect", ["limit", "report-limit", "io", "wrong-ready"])
def test_output_limit_io_and_invalid_ready_never_allow_success_prefix(module, monkeypatch, defect):
    async def scenario() -> None:
        owner, child = await begin(module, monkeypatch, "RETAIN")
        await owner.send_vector()
        _, raw = output_for(module, owner)
        if defect in ("limit", "report-limit"):
            child.stdout.feed_data(raw + b"x" * (3000 if defect == "limit" else 2049 - len(raw)))
            expected = "STDOUT_LIMIT"
        elif defect == "io":
            child.stdout.feed_data(raw)
            await asyncio.sleep(0)
            child.stdout.set_exception(OSError("raw-marker-must-not-leak"))
            expected = "IO"
        else:
            owner._ready = False
            child.stdout.feed_data(b"not-the-ready\n" + raw)
            expected = "READY"
        child.finish(0)
        with pytest.raises(module["C"]["BootstrapError"], match=expected) as caught:
            await owner.drain()
        assert caught.value.__cause__ is None and caught.value.__context__ is None
        assert "raw-marker" not in str(caught.value)
        if defect != "wrong-ready":
            assert not owner._output
        await release(owner, module)

    asyncio.run(scenario())


def test_close_error_after_expected_fault_remains_io_not_a_valid_rejection(module, monkeypatch):
    async def scenario() -> None:
        owner, child = await begin(module, monkeypatch, "HEADER_NUL")

        async def close_error() -> None:
            raise BrokenPipeError("private-os-detail")

        child.stdin.wait_closed = close_error
        with pytest.raises(module["C"]["BootstrapError"], match="IO"):
            await owner.send_vector()
        assert owner.metadata()["seed_delivery"] == "UNKNOWN"
        child.stdout.feed_data(b"fault=HEADER\n")
        child.finish(42)
        await release(owner, module)
        assert owner.fault is module["C"]["Fault"].IO

    asyncio.run(scenario())


def test_cancelled_public_feed_is_unknown_and_never_reopens(module, monkeypatch):
    async def scenario() -> None:
        owner, child = await begin(module, monkeypatch, "BINARY")
        writing = asyncio.Event()

        async def blocked_drain() -> None:
            writing.set()
            await asyncio.Event().wait()

        child.stdin.drain = blocked_drain
        sending = asyncio.create_task(owner.send_vector())
        await writing.wait()
        sending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await sending
        assert owner.phase == "HELD" and owner.metadata()["seed_delivery"] == "UNKNOWN"
        with pytest.raises(module["C"]["BootstrapError"]):
            await owner.send_vector()
        await release(owner, module)

    asyncio.run(scenario())


def test_late_spawn_is_adopted_and_old_absence_cannot_release(module, monkeypatch):
    channel = module["C"]
    monkeypatch.setitem(channel, "OPEN_SECONDS", 0.01)

    async def scenario() -> None:
        owner = module["PublicReaderOwner"](TASK, CID, module["R"]["Case"].ONE)
        child, gate = Process(), asyncio.Event()

        async def spawn(*_args: Any, **_kwargs: Any) -> Any:
            await gate.wait()
            return child

        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        with pytest.raises(channel["BootstrapError"], match="DEADLINE"):
            await owner.start()
        gate.set()
        ticket = await owner.quiesce()
        assert ticket is not None and child.kills == 1 and not child.stdin.received
        assert not await owner.close()
        with pytest.raises(channel["BootstrapError"]):
            await owner.close(channel["Absent"](ticket, ticket.issued - 1.0))
        assert await owner.close(channel["Absent"](ticket, ticket.issued + 1.0))
        owner.assert_released()

    asyncio.run(scenario())


def test_live_handle_does_not_become_released_by_task_completion(module, monkeypatch):
    async def scenario() -> None:
        owner, child = await begin(module, monkeypatch, "RETAIN")
        await owner.send_vector()
        # Simulate a still-live handle even though wait()/stdout EOF complete.
        child.finish(0)
        child.handles[0]._handle = 100
        assert not owner._pipe_closed(0)
        # Completed tasks alone cannot certify the still-live fake handle.
        ticket = await owner.quiesce()
        assert ticket is None and not owner.metadata()["released"]
        child.handles[0].close()
        await release(owner, module)

    asyncio.run(scenario())


def test_expired_feed_never_writes_or_reports_sent(module, monkeypatch):
    async def scenario() -> None:
        owner, child = await begin(module, monkeypatch, "RETAIN")
        owner._opened -= 13.0
        with pytest.raises(module["C"]["BootstrapError"], match="DEADLINE"):
            await owner.send_vector()
        assert not child.stdin.received and owner.metadata()["seed_delivery"] == "NOT_SENT"
        await release(owner, module)

    asyncio.run(scenario())


def test_task_creation_failure_is_io_and_retains_owner_until_collection(module, monkeypatch):
    async def scenario() -> None:
        owner, child = await begin(module, monkeypatch, "RETAIN")
        original = module["asyncio"].create_task

        def create(coro: Any, *, name: str | None = None) -> Any:
            if name == "maskgw-bootstrap-feed":
                raise OSError("raw-task-detail")
            return original(coro, name=name)

        monkeypatch.setattr(module["asyncio"], "create_task", create)
        with pytest.raises(module["C"]["BootstrapError"], match="IO") as caught:
            await owner.send_vector()
        assert not child.stdin.received and caught.value.__context__ is None
        assert not owner.metadata()["released"]
        await release(owner, module)

    asyncio.run(scenario())


def test_spawn_failure_is_sanitized_and_never_writes(module, monkeypatch):
    async def scenario() -> None:
        owner = module["PublicReaderOwner"](TASK, CID, module["R"]["Case"].ONE)

        async def spawn(*_args: Any, **_kwargs: Any) -> Any:
            raise OSError("raw-spawn-detail")

        monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", spawn)
        with pytest.raises(module["C"]["BootstrapError"], match="SPAWN") as caught:
            await owner.start()
        assert caught.value.__context__ is None and owner._process is None
        assert owner.metadata()["seed_delivery"] == "NOT_SENT"
        await release(owner, module)

    asyncio.run(scenario())


def test_zero_exit_without_stdout_eof_does_not_approve_prefix(module, monkeypatch):
    async def scenario() -> None:
        owner, child = await begin(module, monkeypatch, "RETAIN")
        await owner.send_vector()
        _, raw = output_for(module, owner)
        child.stdout.feed_data(raw)
        child.returncode = 0
        child.ended.set()
        for handle in child.handles.values():
            handle.close()
        with pytest.raises(module["C"]["BootstrapError"], match="IO"):
            await owner.drain()
        assert not owner._stdout_eof and not owner.metadata()["released"]
        child.stdout.feed_eof()
        await release(owner, module)

    asyncio.run(scenario())


def test_drain_waits_for_handle_callbacks_after_eof_without_false_state_failure(
    module, monkeypatch
):
    async def scenario() -> None:
        owner, child = await begin(module, monkeypatch, "RETAIN")
        await owner.send_vector()
        _, raw = output_for(module, owner)
        child.stdout.feed_data(raw)
        child.finish(0)
        child.handles[1]._handle = 100

        async def close_later() -> None:
            await asyncio.sleep(0.02)
            child.handles[1].close()

        closing = asyncio.create_task(close_later())
        try:
            observed = await owner.drain()
            assert observed.returncode == 0 and observed.output == raw
        finally:
            await closing
            await release(owner, module)

    asyncio.run(scenario())
