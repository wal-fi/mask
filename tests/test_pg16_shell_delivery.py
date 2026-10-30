"""Closed delivery policy and inherited lifecycle fakes. No shell or Docker."""

import asyncio
import dataclasses
import hashlib
import json
import os
import runpy
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.test_w1_bootstrap_channel import (
    Handle,
    Process,
    watchdog,  # noqa: F401 - independent lifecycle bound
)

REPO = Path(__file__).resolve().parents[1]
TASK, CID = "a" * 32, "c" * 64


@pytest.fixture
def module(monkeypatch: pytest.MonkeyPatch) -> Any:
    value = runpy.run_path(str(REPO / "docs/poc/pg16_shell_delivery.py"))
    monkeypatch.setitem(value["C"], "PIPE_TYPE", Handle)
    monkeypatch.setitem(value["C"], "CLOSE_SECONDS", 0.05)
    monkeypatch.setitem(value["C"], "admit_runtime", lambda: None)
    return value


def test_all23_cases_have_fixed_prefix_or_exact_policy_without_oracle_change(module):
    reader = module["R"]
    prefix, exact = [], []
    assert len(reader["Case"]) == 23
    for case in reader["Case"]:
        original = reader["vector"](case)
        delivered, description = module["delivery_for"](case.value)
        assert delivered.case is original.case and delivered.body == original.body
        assert delivered.fault is original.fault and delivered.tail == original.tail
        assert delivered.hold_open is original.hold_open
        assert description.case == case.value
        assert description.wire_bytes == len(delivered.wire)
        assert description.chunk_sizes == tuple(map(len, delivered.chunks))
        assert description.hold_open is delivered.hold_open
        if original.fault is reader["Code"].HEADER:
            prefix.append(case.value)
            assert description.mode == "HEADER_PREFIX"
            assert delivered.wire == original.wire[:16]
            assert delivered.chunks == (original.wire[:16],)
            assert 0 < description.wire_bytes <= 16 and not description.hold_open
            raw = b"fault=HEADER\n"
            assert reader["parse_report"](raw, 42, TASK, case) == {
                "ok": False,
                "category": "HEADER",
            }
        else:
            exact.append(case.value)
            assert description.mode == "EXACT_VECTOR" and delivered == original
        with pytest.raises(dataclasses.FrozenInstanceError):
            description.wire_bytes = 999
    assert len(prefix) == 9 and len(exact) == 14
    short, description = module["delivery_for"]("short-header")
    assert description.mode == "HEADER_PREFIX" and description.wire_bytes == 15
    assert short.wire == reader["vector"](reader["Case"].SHORT_HEADER).wire


def test_header_read_order_matches_captured_shell_source_not_a_substitute_decoder(module):
    reader = module["R"]
    source = reader["READER_SOURCE"]
    header = source.index("dd bs=1 count=16 of=/tmp/maskgw-reader/header")
    body = source.index('dd bs=1 count="$length" of=/tmp/maskgw-reader/body')
    assert header < source.index('case "$header" in') < source.rfind("fail HEADER") < body
    assert hashlib.sha256(source.encode("ascii")).hexdigest() == reader["CORE_SHA"]
    assert reader["CORE_SHA"] == "802192691f7294baf5b41a39979110a881453c6eb4cfe6d6585a655b7afabd32"


def test_subclass_only_overrides_constructor_and_resolves_every_other_attribute_identically(module):
    cls, parent = module["PublicDeliveryOwner"], module["O"]["PublicReaderOwner"]
    metadata = {"__module__", "__doc__", "__dict__", "__weakref__"}
    assert set(cls.__dict__) <= metadata | {"__init__"}
    for ancestor in (parent, module["C"]["ManagedBootstrap"]):
        for name in ancestor.__dict__:
            if name not in metadata | {"__init__"}:
                assert getattr(cls, name) is getattr(parent, name), name


def test_swap_occurs_after_parent_constructor_before_any_start(module, monkeypatch):
    parent = module["O"]["PublicReaderOwner"]
    original = parent.__init__
    before = []

    def construct(self: Any, task: str, cid: str, case: Any) -> None:
        original(self, task, cid, case)
        before.append(self._vector.wire)
        assert self.phase == "NEW" and self._tasks == {} and self._process is None

    monkeypatch.setattr(parent, "__init__", construct)
    owner = module["PublicDeliveryOwner"](TASK, CID, "header-nul")
    assert len(before[0]) == 16408 and owner._vector.wire == before[0][:16]
    assert owner.phase == "NEW" and owner._process is None and owner._tasks == {}


@pytest.mark.parametrize("case", [None, True, "", "unknown", "x" * 33, b"binary", "binary;evil"])
def test_untrusted_case_is_refused_before_constructor_or_spawn(module, case):
    with pytest.raises(RuntimeError, match=r"^PG16_READER_DELIVERY_INPUT$") as caught:
        module["PublicDeliveryOwner"](TASK, CID, case)
    assert caught.value.__cause__ is None and caught.value.__context__ is None


def test_own_enum_foreign_enum_and_str_subclass_are_not_coerced(module):
    profile = runpy.run_path(str(REPO / "docs/poc/pg16_shell_profile.py"))

    class Text(str):
        pass

    for case in (module["R"]["Case"].BINARY, profile["R"]["Case"].BINARY, Text("binary")):
        with pytest.raises(RuntimeError, match="DELIVERY_INPUT"):
            module["delivery_for"](case)
    # Only primitives compare across captured namespaces, with no Target/Case crossing.
    image = profile["admit_image"](
        json.dumps(
            [
                {
                    "Id": profile["IMAGE"],
                    "Os": "linux",
                    "Architecture": "amd64",
                    "Config": {
                        "Env": [
                            "PATH=" + profile["P"]["PATH"],
                            "PG_MAJOR=16",
                            "PG_VERSION=16.15",
                            "PGDATA=" + profile["P"]["DATA"],
                        ],
                        "Volumes": {profile["P"]["DATA"]: {}},
                        "ExposedPorts": {"5432/tcp": {}},
                        "Labels": None,
                    },
                }
            ]
        ).encode("ascii")
    )
    intent = profile["Intent"](TASK, image, profile["R"]["Case"].BINARY)
    owner = module["PublicDeliveryOwner"](TASK, CID, "binary")
    assert owner.wrapper == intent.command[1] and owner.wrapper_sha256 == intent.source_sha256
    assert owner.target.source_sha256 == intent.core_sha256
    assert (
        owner.target.cid == CID
        and owner.target.task == TASK
        and owner.target.image == profile["IMAGE"]
    )


@pytest.mark.parametrize(
    "case", ["one", "binary", "fragmented", "header-nul", "short-header", "retain", "wait-body"]
)
def test_inherited_transport_sends_exact_configured_wire_and_retains_or_closes_input(
    module, monkeypatch, case
):
    async def scenario() -> None:
        owner = module["PublicDeliveryOwner"](TASK, CID, case)
        child = Process()

        async def spawn(*args: Any, **kwargs: Any) -> Any:
            assert args[-4:] == ("start", "--attach", "--interactive", CID)
            assert kwargs["stdin"] == kwargs["stdout"] == subprocess.PIPE
            assert kwargs["stderr"] == subprocess.DEVNULL
            child.stdout.feed_data(owner.target.ready_line())
            return child

        monkeypatch.setattr(module["O"]["asyncio"], "create_subprocess_exec", spawn)
        vector = owner._vector
        if vector.fault is None:
            code = 0
            raw = module["R"]["_encoded"](module["R"]["expected_report"](TASK, vector.case))
        else:
            code, raw = 42, f"fault={vector.fault.value}\n".encode("ascii")
        close = child.stdin.close

        def finish() -> None:
            close()
            child.stdout.feed_data(raw)
            child.finish(code)

        if not vector.hold_open:
            monkeypatch.setattr(child.stdin, "close", finish)
        await owner.start()
        await owner.await_ready()
        await owner.send_vector()
        assert bytes(child.stdin.received) == vector.wire
        assert owner.delivery.wire_bytes == len(child.stdin.received)
        assert owner.metadata()["seed_delivery"] == "SENT"
        if vector.hold_open:
            assert not child.stdin.closed
            child.stdout.feed_data(raw)
            child.finish(code)
        observed = await owner.drain()
        assert observed.returncode == code and observed.output == raw
        assert child.stdin.closed
        assert observed.stdout_bytes == len(owner.target.ready_line()) + len(raw)
        ticket = await owner.quiesce()
        assert await owner.close(module["C"]["Absent"](ticket, module["O"]["time"].monotonic()))
        owner.assert_released()

    asyncio.run(scenario())


def test_broken_pipe_is_still_io_even_when_header_rejection_is_expected(module, monkeypatch):
    async def scenario() -> None:
        owner = module["PublicDeliveryOwner"](TASK, CID, "header-nul")
        child = Process()

        async def spawn(*_args: Any, **_kwargs: Any) -> Any:
            child.stdout.feed_data(owner.target.ready_line())
            return child

        async def broken() -> None:
            raise BrokenPipeError("raw-private-marker")

        monkeypatch.setattr(module["O"]["asyncio"], "create_subprocess_exec", spawn)
        monkeypatch.setattr(child.stdin, "wait_closed", broken)
        await owner.start()
        await owner.await_ready()
        with pytest.raises(module["C"]["BootstrapError"], match="IO") as caught:
            await owner.send_vector()
        assert caught.value.__context__ is None
        assert owner.metadata()["seed_delivery"] == "UNKNOWN"
        child.stdout.feed_data(b"fault=HEADER\n")
        child.finish(42)
        ticket = await owner.quiesce()
        assert await owner.close(module["C"]["Absent"](ticket, module["O"]["time"].monotonic()))

    asyncio.run(scenario())


def test_no_arbitrary_seed_method_and_no_native_effect_on_import(module, monkeypatch):
    async def scenario() -> None:
        owner = module["PublicDeliveryOwner"](TASK, CID, "one")
        with pytest.raises(module["C"]["BootstrapError"], match="STATE"):
            await owner.send_seed(object())
        assert not owner._tasks and owner._process is None

    asyncio.run(scenario())

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("public delivery attempted native action")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    loaded = runpy.run_path(str(REPO / "docs/poc/pg16_shell_delivery.py"))
    assert loaded["delivery_for"]("binary")[1].mode == "EXACT_VECTOR"


def test_capture_nested_failure_has_closed_source_error_without_context(module, monkeypatch):
    def refused(*_args: Any) -> None:
        raise OSError("raw-source-marker")

    monkeypatch.setitem(module["capture"].__globals__, "exec", refused)
    with pytest.raises(RuntimeError, match=r"^PG16_READER_DELIVERY_SOURCE$") as caught:
        module["capture"]()
    assert caught.value.__cause__ is None and caught.value.__context__ is None


def test_hostile_case_is_never_formatted_or_coerced(module):
    class Hostile:
        def __str__(self) -> str:
            raise AssertionError("caller str invoked")

        def __repr__(self) -> str:
            raise AssertionError("caller repr invoked")

    with pytest.raises(RuntimeError, match=r"^PG16_READER_DELIVERY_INPUT$") as caught:
        module["delivery_for"](Hostile())
    assert caught.value.__context__ is None


@pytest.mark.parametrize("close_io", [False, True])
def test_header_exit_before_input_close_preserves_io_policy(module, monkeypatch, close_io):
    async def scenario() -> None:
        owner = module["PublicDeliveryOwner"](TASK, CID, "header-nul")
        child = Process()

        async def spawn(*_args: Any, **_kwargs: Any) -> Any:
            child.stdout.feed_data(owner.target.ready_line())
            return child

        async def received() -> None:
            assert bytes(child.stdin.received) == owner._vector.wire
            assert not child.stdin.closed
            child.stdout.feed_data(b"fault=HEADER\n")
            child.finish(42)

        async def broken_close() -> None:
            raise BrokenPipeError("raw-close-marker")

        monkeypatch.setattr(module["O"]["asyncio"], "create_subprocess_exec", spawn)
        monkeypatch.setattr(child.stdin, "drain", received)
        if close_io:
            monkeypatch.setattr(child.stdin, "wait_closed", broken_close)
        await owner.start()
        await owner.await_ready()
        if close_io:
            with pytest.raises(module["C"]["BootstrapError"], match="IO"):
                await owner.send_vector()
            assert owner.metadata()["seed_delivery"] == "UNKNOWN"
        else:
            await owner.send_vector()
            observed = await owner.drain()
            assert observed.returncode == 42 and observed.output == b"fault=HEADER\n"
            assert owner.metadata()["seed_delivery"] == "SENT"
        ticket = await owner.quiesce()
        assert await owner.close(module["C"]["Absent"](ticket, module["O"]["time"].monotonic()))
        owner.assert_released()

    asyncio.run(scenario())
