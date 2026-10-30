"""Receiver owns real buffers; output credits remain pinned until disposal."""

from __future__ import annotations

import ast
import socket
import ssl
import threading
import time
import traceback
import tracemalloc
from _thread import LockType
from pathlib import Path
from typing import Any, cast

import pytest

import maskgw.pgwire.result_frame as frame_module
import maskgw.pgwire.result_receiver as receiver_module
from maskgw.pgwire.result_frame import ResultDeadline, ResultLimits
from maskgw.pgwire.result_receiver import (
    ReceiverError,
    ReceiverFailure,
    ReceiverState,
    ResultReceiver,
)
from maskgw.pgwire.tls import prepare_server_tls
from maskgw.pgwire.transport import RawChannel, TlsChannel, TransportLimits
from maskgw.runtime.budget import (
    BudgetLedger,
    BudgetLimits,
    CleanupConfirmation,
    DatasourceCapacity,
    OutputReleaseOutcome,
    ReleaseOutcome,
)
from tests.pgwire_driver_support import Peer, watchdog
from tests.pgwire_support import make_certificate
from tests.test_result_frame import HEADER, IDENTITY, frame

OVERHEAD = 512 * 1024
COMPLETE = CleanupConfirmation(True, True, True, True, True)


def deadline(seconds: float = 5) -> ResultDeadline:
    return ResultDeadline(expires_at=time.monotonic() + seconds)


def setup(maximum: int = 4096) -> tuple[BudgetLedger, Any, LockType, ResultReceiver]:
    model = BudgetLedger(
        BudgetLimits(100 * 1024 * 1024, 10, 10, 8, 2, 2, 2, 2, 2),
        (DatasourceCapacity(2, 2),),
    )
    generation = model.reserve_candidate(0, shared_bytes=10)
    model.publish(generation)
    token = model.reserve_session(generation, worker_bytes=100, parent_bytes=2 * maximum + OVERHEAD)
    model.mark_live(token)
    lock = threading.Lock()
    receiver = ResultReceiver(
        model,
        token,
        lock=lock,
        expected=IDENTITY,
        limits=ResultLimits(max_rows=1000, max_frame_bytes=maximum),
        overhead_bytes=OVERHEAD,
        deadline=deadline(),
    )
    return model, token, lock, receiver


def channel(sock: Any) -> RawChannel:
    return RawChannel(sock, stop=lambda: False, limits=TransportLimits(chunk_bytes=127, poll_ms=10))


class Source:
    def __init__(self, data: bytes, *, chunk: int = 7) -> None:
        self.data = data
        self.offset = 0
        self.chunk = chunk
        self.reads: list[int] = []

    def settimeout(self, timeout):
        assert timeout > 0

    def recv_into(self, view: memoryview, size: int) -> int:
        count = min(size, self.chunk, len(self.data) - self.offset)
        view[:count] = self.data[self.offset : self.offset + count]
        self.offset += count
        self.reads.append(count)
        return count


class Sink:
    def __init__(self) -> None:
        self.data = bytearray()

    def settimeout(self, timeout):
        assert timeout > 0

    def send(self, view: memoryview) -> int:
        self.data += view
        return len(view)


def test_receive_send_dispose_in_order_and_pin_survives_sent():
    model, token, _, receiver = setup()
    raw = frame(rows=[[b"masked"]])
    receiver.receive(channel(Source(raw)))
    assert receiver.status(deadline=deadline()) is ReceiverState.READY
    sink = Sink()
    result = receiver.send_to(channel(sink), deadline=deadline())
    assert (result.columns, result.rows, result.truncated) == (1, 1, False)
    assert sink.data == raw[HEADER.size :]
    assert receiver.status(deadline=deadline()) is ReceiverState.SENT
    model.begin_drain(token)
    assert model.release(token, COMPLETE) is ReleaseOutcome.HELD
    assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.CLEARED
    assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.ALREADY_CLEARED
    assert model.release(token, COMPLETE) is ReleaseOutcome.RELEASED


@pytest.mark.parametrize("cut", [0, 1, 75, 76, 90])
def test_eof_keeps_pin_then_drains_on_explicit_close(cut):
    model, token, _, receiver = setup()
    with pytest.raises(ReceiverError):
        receiver.receive(channel(Source(frame(rows=[[b"masked"]])[:cut])))
    assert receiver.status(deadline=deadline()) is ReceiverState.FAILED
    assert model.status.entries[token._slot].output_pinned
    assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.CLEARED
    entry = model.status.entries[token._slot]
    assert entry.state.value == "DRAINING" and not entry.output_pinned


def test_header_limit_refuses_before_body_read():
    _, _, _, receiver = setup()
    source = Source(frame(fields={11: 2**32 - 1}))
    with pytest.raises(ReceiverError):
        receiver.receive(channel(source))
    assert source.offset == HEADER.size
    assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.CLEARED


def test_unvalidated_body_cannot_send_a_single_byte():
    _, _, _, receiver = setup()
    raw = frame(rows=[[b"sensitive\0"]])
    with pytest.raises(ReceiverError):
        receiver.receive(channel(Source(raw)))
    sink = Sink()
    with pytest.raises(ReceiverError):
        receiver.send_to(channel(sink), deadline=deadline())
    assert not sink.data
    receiver.close(deadline=deadline())


def test_actual_local_socket_receive_and_send():
    _, _, _, receiver = setup()
    raw = frame(rows=[[b"masked"]])
    source, peer = socket.socketpair()
    output, client = socket.socketpair()
    try:
        peer.settimeout(2)
        peer.sendall(raw)
        receiver.receive(channel(source))
        receiver.send_to(channel(output), deadline=deadline())
        client.settimeout(2)
        assert client.recv(4096) == raw[HEADER.size :]
    finally:
        source.close()
        peer.close()
        output.close()
        client.close()
        receiver.close(deadline=deadline())


def test_partial_send_failure_never_retries_and_drains_session():
    model, token, _, receiver = setup()
    receiver.receive(channel(Source(frame(rows=[[b"masked"]]))))

    class PartialSink(Sink):
        def send(self, view):
            if self.data:
                raise OSError("CANARY_SEND")
            self.data += view[:3]
            return 3

    sink = PartialSink()
    with pytest.raises(ReceiverError) as caught:
        receiver.send_to(channel(sink), deadline=deadline())
    assert caught.value.category is ReceiverFailure.IO
    assert caught.value.__context__ is None and "CANARY" not in str(caught.value)
    prefix = bytes(sink.data)
    assert len(prefix) == 3
    with pytest.raises(ReceiverError):
        receiver.send_to(channel(sink), deadline=deadline())
    assert sink.data == prefix
    receiver.close(deadline=deadline())
    assert model.status.entries[token._slot].state.value == "DRAINING"


@pytest.mark.parametrize("operation", ["read", "send"])
def test_io_runs_outside_lock_and_concurrent_close_is_refused(operation):
    _, _, lock, receiver = setup()
    entered = threading.Event()
    proceed = threading.Event()
    errors = []

    class BlockSource(Source):
        def recv_into(self, view, size):
            entered.set()
            assert proceed.wait(2)
            return super().recv_into(view, size)

    class BlockSink(Sink):
        def send(self, view):
            entered.set()
            assert proceed.wait(2)
            return super().send(view)

    if operation == "send":
        receiver.receive(channel(Source(frame())))

    def run():
        try:
            if operation == "read":
                receiver.receive(channel(BlockSource(frame())))
            else:
                receiver.send_to(channel(BlockSink()), deadline=deadline())
        except BaseException as error:
            errors.append(error)

    worker = threading.Thread(target=run, name="result-test-io")
    with watchdog(10):
        worker.start()
        try:
            assert entered.wait(2)
            assert lock.acquire(timeout=0.1)
            lock.release()
            with pytest.raises(ReceiverError) as caught:
                receiver.close(deadline=deadline())
            assert caught.value.category is ReceiverFailure.STATE
            with pytest.raises(ReceiverError):
                receiver.receive(channel(Source(frame())))
        finally:
            proceed.set()
            worker.join(3)
        assert not worker.is_alive() and not errors
        receiver.close(deadline=deadline())


def test_plain_lock_reentry_is_bounded_and_rlock_rejected():
    model, token, lock, receiver = setup()
    with lock, watchdog(3):
        started = time.monotonic()
        with pytest.raises(ReceiverError) as caught:
            receiver.status(deadline=deadline())
        assert caught.value.category is ReceiverFailure.BUSY
        assert time.monotonic() - started < 1
    receiver.close(deadline=deadline())
    with pytest.raises(ReceiverError):
        ResultReceiver(
            model,
            token,
            lock=threading.RLock(),  # type: ignore[arg-type]  # runtime rejection
            expected=IDENTITY,
            limits=ResultLimits(max_rows=5),
            overhead_bytes=OVERHEAD,
            deadline=deadline(),
        )


def test_expired_read_deadline_requires_fresh_cleanup_deadline():
    model, token, _, receiver = setup()
    receiver._deadline = deadline(0.02)
    source, peer = socket.socketpair()
    try:
        with watchdog(3), pytest.raises(ReceiverError):
            receiver.receive(channel(source))
        assert receiver.status(deadline=deadline()) is ReceiverState.FAILED
        with pytest.raises(ReceiverError):
            receiver.close(deadline=receiver._deadline)
        assert model.status.entries[token._slot].output_pinned
        assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.CLEARED
    finally:
        source.close()
        peer.close()


@pytest.mark.parametrize("operation", ["read", "send"])
def test_interrupt_retains_pin_even_after_known_owner_dropped(operation):
    model, token, _, receiver = setup()

    class InterruptedSource(Source):
        def recv_into(self, view, size):
            del view, size
            raise KeyboardInterrupt

    class InterruptedSink(Sink):
        def send(self, view):
            del view
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        if operation == "read":
            receiver.receive(channel(InterruptedSource(frame())))
        else:
            receiver.receive(channel(Source(frame())))
            receiver.send_to(channel(InterruptedSink()), deadline=deadline())
    assert receiver.status(deadline=deadline()) is ReceiverState.FAILED
    assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.HELD
    assert receiver.status(deadline=deadline()) is ReceiverState.HELD
    assert model.status.entries[token._slot].output_pinned


def test_failed_traceback_cleanup_retains_pin(monkeypatch):
    model, token, _, receiver = setup()
    monkeypatch.setattr(traceback, "clear_frames", lambda _tb: (_ for _ in ()).throw(OSError()))
    with pytest.raises(ReceiverError):
        receiver.receive(channel(Source(b"")))
    assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.HELD
    assert model.status.entries[token._slot].output_pinned


def test_phase_three_commit_failure_retains_pin_and_cleanup_is_retryable(monkeypatch):
    model, token, _, receiver = setup()
    receiver.receive(channel(Source(frame())))
    original = BudgetLedger._write_image

    def failed(self, image):
        del self, image
        raise OSError("CANARY_COMMIT")

    monkeypatch.setattr(BudgetLedger, "_write_image", failed)
    with pytest.raises(ReceiverError) as caught:
        receiver.close(deadline=deadline())
    assert caught.value.category is ReceiverFailure.BUDGET
    assert receiver.status(deadline=deadline()) is ReceiverState.HELD
    assert model.status.entries[token._slot].output_pinned
    monkeypatch.setattr(BudgetLedger, "_write_image", original)
    assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.CLEARED


def test_16mib_real_socket_peak_and_disposal_before_unpin(monkeypatch):
    mib = 1024 * 1024
    empty = frame(rows=[[b""]] * 16)
    remaining = 16 * mib - len(empty) - 15 * mib
    raw = frame(rows=[[b"x" * mib]] * 15 + [[b"y" * remaining]])
    assert len(raw) == 16 * mib
    model, token, _, receiver = setup(len(raw))
    source, peer = socket.socketpair()
    observed = []
    original = BudgetLedger.end_output

    def disposal_observer(self, pin, *, discarded, drain=False):
        observed.append(tracemalloc.get_traced_memory()[0])
        assert receiver._owner is None and receiver._discarded.is_set()
        return original(self, pin, discarded=discarded, drain=drain)

    monkeypatch.setattr(BudgetLedger, "end_output", disposal_observer)
    peer.settimeout(5)
    try:
        with watchdog(15), Peer(peer, lambda sock: sock.sendall(raw)) as sender:
            tracemalloc.start()
            try:
                receiver.receive(RawChannel(source, stop=lambda: False, limits=TransportLimits()))
                retained, peak = tracemalloc.get_traced_memory()
                assert len(raw) <= retained < len(raw) + OVERHEAD
                assert peak < 2 * len(raw) + OVERHEAD
                assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.CLEARED
                assert observed and observed[0] < OVERHEAD
                assert not model.status.entries[token._slot].output_pinned
            finally:
                tracemalloc.stop()
        assert sender.error is None
    finally:
        source.close()
        peer.close()
    assert receiver.status(deadline=deadline()) is ReceiverState.CLOSED


@pytest.mark.parametrize("kind", ["oversized", "wrong_identity", "minimum"])
def test_bad_header_allocates_only_fixed_header(monkeypatch, kind):
    _, _, _, receiver = setup()
    fields = {"oversized": {11: 2**32 - 1}, "wrong_identity": {8: 9}, "minimum": {11: 0}}
    sizes = []

    def allocate(size):
        sizes.append(size)
        return bytearray(size)

    monkeypatch.setattr(receiver_module, "bytearray", allocate, raising=False)
    with pytest.raises(ReceiverError):
        receiver.receive(channel(Source(frame(fields=fields[kind]))))
    assert sizes == [HEADER.size]
    receiver.close(deadline=deadline())


def test_receiver_allocation_failure_is_sanitized_and_pin_retained(monkeypatch):
    model, token, _, receiver = setup()

    def broken(_size):
        raise MemoryError("CANARY_ALLOCATION")

    monkeypatch.setattr(receiver_module, "bytearray", broken, raising=False)
    with pytest.raises(ReceiverError) as caught:
        receiver.receive(channel(Source(frame())))
    assert caught.value.category is ReceiverFailure.LIMIT
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert "CANARY" not in str(caught.value)
    assert model.status.entries[token._slot].output_pinned
    receiver.close(deadline=deadline())


def test_saved_native_send_error_traceback_has_no_payload_after_disposal():
    model, _, _, receiver = setup(2 * 1024 * 1024)
    raw = frame(rows=[[b"x" * (1024 * 1024)]])
    receiver.receive(channel(Source(raw, chunk=65536)))
    native = OSError("CANARY_NATIVE")

    class ErrorSink(Sink):
        def send(self, view):
            del view
            raise native

    with pytest.raises(ReceiverError):
        receiver.send_to(channel(ErrorSink()), deadline=deadline())
    receiver.close(deadline=deadline())
    tb = native.__traceback__
    while tb is not None:
        assert not any(
            isinstance(value, (bytes, bytearray)) and len(value) >= len(raw)
            for value in tb.tb_frame.f_locals.values()
        )
        assert "owner" not in tb.tb_frame.f_locals
        tb = tb.tb_next
    assert not model.status.failed


def test_old_receive_completion_cannot_settle_an_inflight_send(monkeypatch):
    _, _, _, receiver = setup()
    received = threading.Event()
    finish_receive = threading.Event()
    sending = threading.Event()
    finish_send = threading.Event()
    failures = []

    class DelayedCompletion:
        def __init__(self) -> None:
            self.event = threading.Event()

        def set(self):
            received.set()
            assert finish_receive.wait(3)
            self.event.set()

        def is_set(self):
            return self.event.is_set()

    old = DelayedCompletion()
    events = iter((old, threading.Event()))
    monkeypatch.setattr(receiver_module, "Event", lambda: next(events))

    class BlockSink(Sink):
        def send(self, view):
            sending.set()
            assert finish_send.wait(3)
            return super().send(view)

    def receive():
        try:
            receiver.receive(channel(Source(frame())))
        except BaseException as error:
            failures.append(error)

    def send():
        try:
            receiver.send_to(channel(BlockSink()), deadline=deadline())
        except BaseException as error:
            failures.append(error)

    receiving = threading.Thread(target=receive, name="result-test-receive-completion")
    sender = threading.Thread(target=send, name="result-test-send-completion")
    with watchdog(10):
        receiving.start()
        try:
            assert received.wait(3)
            sender.start()
            assert sending.wait(3)
            finish_receive.set()
            receiving.join(3)
            assert not receiving.is_alive()
            assert receiver.status(deadline=deadline()) is ReceiverState.SENDING
            with pytest.raises(ReceiverError):
                receiver.close(deadline=deadline())
        finally:
            finish_receive.set()
            finish_send.set()
            receiving.join(3)
            if sender.ident is not None:
                sender.join(3)
        assert not receiving.is_alive() and not sender.is_alive() and not failures
    receiver.close(deadline=deadline())


@pytest.mark.parametrize("nested", [False, True])
def test_exception_group_cleanup_is_uncertain_not_confirmed(nested):
    model, token, _, receiver = setup()

    class GroupSource(Source):
        def recv_into(self, view, size):
            del view, size
            group = ExceptionGroup("CANARY_GROUP", [OSError("CANARY_INNER")])
            if nested:
                error = OSError("CANARY_CONTEXT")
                error.__context__ = group
                raise error
            raise group

    with pytest.raises(ReceiverError):
        receiver.receive(channel(GroupSource(frame())))
    assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.HELD
    assert model.status.entries[token._slot].output_pinned


def test_real_socket_eof_inside_body_is_closed_and_drained():
    model, token, _, receiver = setup()
    source, peer = socket.socketpair()
    try:
        peer.sendall(frame(rows=[[b"masked"]])[:-1])
        peer.close()
        with watchdog(3), pytest.raises(ReceiverError) as caught:
            receiver.receive(channel(source))
        assert caught.value.category is ReceiverFailure.IO
        receiver.close(deadline=deadline())
        assert model.status.entries[token._slot].state.value == "DRAINING"
    finally:
        source.close()
        peer.close()


def test_actual_slow_client_timeout_does_not_return_credit_before_close():
    raw = frame(rows=[[b"x" * (1024 * 1024)], [b"y" * (1024 * 1024)]])
    model, token, _, receiver = setup(len(raw))
    receiver.receive(
        RawChannel(
            cast(Any, Source(raw, chunk=65536)), stop=lambda: False, limits=TransportLimits()
        )
    )
    server, client = socket.socketpair()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    try:
        with watchdog(3), pytest.raises(ReceiverError) as caught:
            receiver.send_to(channel(server), deadline=deadline(0.3))
        assert caught.value.category is ReceiverFailure.DEADLINE
        client.settimeout(0.01)
        prefix = bytearray()
        while True:
            try:
                part = client.recv(65536)
            except TimeoutError:
                break
            assert part
            prefix += part
        assert 0 < len(prefix) < len(raw) - HEADER.size
        assert prefix == raw[HEADER.size : HEADER.size + len(prefix)]
        assert receiver.status(deadline=deadline()) is ReceiverState.FAILED
        assert model.status.entries[token._slot].output_pinned
        receiver.close(deadline=deadline())
        assert model.status.entries[token._slot].state.value == "DRAINING"
    finally:
        server.close()
        client.close()


def test_exact_session_pin_blocks_second_receiver_and_sent_close_allows_next():
    model, token, lock, first = setup()

    def another() -> ResultReceiver:
        return ResultReceiver(
            model,
            token,
            lock=lock,
            expected=IDENTITY,
            limits=ResultLimits(max_rows=5, max_frame_bytes=4096),
            overhead_bytes=OVERHEAD,
            deadline=deadline(),
        )

    with pytest.raises(ReceiverError) as caught:
        another()
    assert caught.value.category is ReceiverFailure.BUDGET
    first.receive(channel(Source(frame())))
    first.send_to(channel(Sink()), deadline=deadline())
    first.close(deadline=deadline())
    assert model.status.entries[token._slot].state.value == "LIVE"
    second = another()
    assert second.status(deadline=deadline()) is ReceiverState.NEW
    second.close(deadline=deadline())


def test_stop_callback_failure_is_sanitized_and_keeps_pin_until_disposal():
    model, token, _, receiver = setup()

    def broken():
        raise RuntimeError("CANARY_STOP")

    raw = RawChannel(cast(Any, Source(frame())), stop=broken, limits=TransportLimits())
    with pytest.raises(ReceiverError) as caught:
        receiver.receive(raw)
    assert caught.value.category is ReceiverFailure.IO
    assert caught.value.__context__ is None and "CANARY" not in str(caught.value)
    assert model.status.entries[token._slot].output_pinned
    receiver.close(deadline=deadline())


def test_concurrent_closers_cannot_steal_inflight_disposal(monkeypatch):
    model, token, _, receiver = setup()
    receiver.receive(channel(Source(frame())))
    entered = threading.Event()
    proceed = threading.Event()
    original = receiver._discarded.set
    outcomes = []

    def delayed():
        entered.set()
        assert proceed.wait(3)
        original()

    monkeypatch.setattr(receiver._discarded, "set", delayed)
    closer = threading.Thread(target=lambda: outcomes.append(receiver.close(deadline=deadline())))
    with watchdog(10):
        closer.start()
        try:
            assert entered.wait(3)
            with pytest.raises(ReceiverError) as caught:
                receiver.close(deadline=deadline())
            assert caught.value.category is ReceiverFailure.STATE
            assert model.status.entries[token._slot].output_pinned
        finally:
            proceed.set()
            closer.join(3)
        assert not closer.is_alive() and outcomes == [OutputReleaseOutcome.CLEARED]
    assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.ALREADY_CLEARED


@pytest.mark.parametrize("payload", [b"masked", b"x" * (256 * 1024)], ids=["small", "multi_chunk"])
def test_receiver_sends_only_validated_body_through_actual_tls(tmp_path, payload):
    raw = frame(rows=[[payload]])
    _, _, _, receiver = setup(max(4096, len(raw)))
    receiver.receive(channel(Source(raw)))
    certificate, _, _ = make_certificate(tmp_path, "rsa-sha256")
    tls = prepare_server_tls(certificate.cert_path, certificate.key_path)
    server, client = socket.socketpair()

    def read_tls(sock):
        context = ssl.create_default_context(cafile=str(certificate.cert_path))
        sock.settimeout(3)
        with context.wrap_socket(sock, server_hostname="localhost") as secured:
            result = bytearray()
            while len(result) < len(raw) - HEADER.size:
                data = secured.recv(4096)
                assert data
                result += data
            return bytes(result)

    try:
        with watchdog(10), Peer(client, read_tls) as peer:
            target = TlsChannel(channel(server), tls.context)
            target.handshake(deadline())
            receiver.send_to(target, deadline=deadline())
        assert peer.error is None and peer.result == raw[HEADER.size :]
        receiver.close(deadline=deadline())
    finally:
        server.close()
        client.close()


def test_receiver_dependencies_are_exact_and_no_operational_importer():
    root = Path(__file__).resolve().parents[1] / "src/maskgw"
    source = root / "pgwire/result_receiver.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            modules.add(node.module)
            if node.module == "threading":
                assert {name.name for name in node.names} == {"Event"}
            if node.module == "_thread":
                assert {name.name for name in node.names} == {"LockType"}
            if node.module == "contextlib":
                assert {name.name for name in node.names} == {"contextmanager"}
        elif isinstance(node, ast.Import):
            modules.update(name.name for name in node.names)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"Thread", "Popen", "open", "exec", "eval", "__import__"}
    assert modules == {
        "__future__",
        "traceback",
        "_thread",
        "collections.abc",
        "contextlib",
        "dataclasses",
        "enum",
        "threading",
        "typing",
        "maskgw.pgwire.result_frame",
        "maskgw.pgwire.transport",
        "maskgw.runtime.budget",
    }
    for path in root.rglob("*.py"):
        if path not in (source, root / "runtime/worker_session.py"):
            assert "result_receiver" not in path.read_text(encoding="utf-8")


def test_saved_receive_error_traceback_releases_proportional_buffers():
    raw = frame(rows=[[b"x" * (1024 * 1024)], [b"y" * (1024 * 1024)]])
    model, token, _, receiver = setup(len(raw))
    native = RuntimeError("CANARY_RECEIVE")

    class BrokenSource(Source):
        def recv_into(self, view, size):
            if self.offset > 1024 * 1024:
                raise native
            return super().recv_into(view, size)

    with pytest.raises(ReceiverError):
        receiver.receive(channel(BrokenSource(raw, chunk=65536)))
    assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.CLEARED
    tb = native.__traceback__
    while tb is not None:
        assert not any(
            isinstance(value, (bytes, bytearray)) and len(value) >= len(raw)
            for value in tb.tb_frame.f_locals.values()
        )
        for value in tb.tb_frame.f_locals.values():
            if isinstance(value, memoryview):
                with pytest.raises(ValueError):
                    _ = value.obj  # a live view would retain the proportional owner
        tb = tb.tb_next
    assert not model.status.entries[token._slot].output_pinned


def test_second_closer_can_complete_phase_three_once_disposal_is_proven(monkeypatch):
    _, _, _, receiver = setup()
    receiver.receive(channel(Source(frame())))
    marked = threading.Event()
    proceed = threading.Event()
    original = receiver._discarded.set
    outcomes = []

    def delayed():
        original()
        if threading.current_thread().name == "result-test-first-closer":
            marked.set()
            assert proceed.wait(3)

    monkeypatch.setattr(receiver._discarded, "set", delayed)
    first = threading.Thread(
        target=lambda: outcomes.append(receiver.close(deadline=deadline())),
        name="result-test-first-closer",
    )
    with watchdog(10):
        first.start()
        try:
            assert marked.wait(3)
            assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.CLEARED
        finally:
            proceed.set()
            first.join(3)
        assert not first.is_alive() and outcomes == [OutputReleaseOutcome.ALREADY_CLEARED]


def test_tls_peer_closes_during_large_result_no_retry_and_drain(tmp_path):
    raw = frame(rows=[[b"x" * (1024 * 1024)], [b"y" * (1024 * 1024)]])
    model, token, _, receiver = setup(len(raw))
    receiver.receive(channel(Source(raw, chunk=65536)))
    certificate, _, _ = make_certificate(tmp_path, "rsa-sha256")
    tls = prepare_server_tls(certificate.cert_path, certificate.key_path)
    server, client = socket.socketpair()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)

    def read_first_tls_block_then_close(sock):
        context = ssl.create_default_context(cafile=str(certificate.cert_path))
        sock.settimeout(3)
        with context.wrap_socket(sock, server_hostname="localhost") as secured:
            return secured.recv(1024)

    try:
        with watchdog(10), Peer(client, read_first_tls_block_then_close) as peer:
            target = TlsChannel(channel(server), tls.context)
            target.handshake(deadline())
            with pytest.raises(ReceiverError) as caught:
                receiver.send_to(target, deadline=deadline())
            assert caught.value.category is not ReceiverFailure.DEADLINE
        assert peer.error is None and peer.result
        assert receiver.status(deadline=deadline()) is ReceiverState.FAILED
        receiver.close(deadline=deadline())
        assert model.status.entries[token._slot].state.value == "DRAINING"
    finally:
        server.close()
        client.close()


@pytest.mark.parametrize("operation", ["read", "send"])
def test_opaque_timeout_is_not_silently_retried(operation):
    model, token, _, receiver = setup()
    native = TimeoutError("CANARY_TIMEOUT")
    native.__context__ = ExceptionGroup("CANARY_GROUP", [OSError()])

    class TimeoutSource(Source):
        def recv_into(self, view, size):
            if not self.reads:
                self.reads.append(-1)
                raise native
            return super().recv_into(view, size)

    class TimeoutSink(Sink):
        failed = False

        def send(self, view):
            if not self.failed:
                self.failed = True
                raise native
            return super().send(view)

    with pytest.raises(ReceiverError) as caught:
        if operation == "read":
            receiver.receive(channel(TimeoutSource(frame())))
        else:
            receiver.receive(channel(Source(frame())))
            receiver.send_to(channel(TimeoutSink()), deadline=deadline())
    assert caught.value.category is ReceiverFailure.IO
    assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.HELD
    assert model.status.entries[token._slot].output_pinned


def test_d113_oom_flag_does_not_change_receiver_limit_classification(monkeypatch):
    model, token, _, receiver = setup()

    def no_scratch(_size):
        raise MemoryError("CANARY_VALIDATOR")

    monkeypatch.setattr(frame_module, "bytearray", no_scratch, raising=False)
    with pytest.raises(ReceiverError) as caught:
        receiver.receive(channel(Source(frame())))
    assert caught.value.category is ReceiverFailure.LIMIT
    assert model.status.entries[token._slot].output_pinned
    assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.CLEARED


def test_phase_three_lock_timeout_retains_pin_and_retries_only_cleanup(monkeypatch):
    model, token, lock, receiver = setup()
    receiver.receive(channel(Source(frame())))
    original = receiver._discarded.set

    def finish_discard_then_hold_lock():
        original()
        assert lock.acquire(timeout=0.1)

    monkeypatch.setattr(receiver._discarded, "set", finish_discard_then_hold_lock)
    try:
        with pytest.raises(ReceiverError) as caught:
            receiver.close(deadline=deadline())
        assert caught.value.category is ReceiverFailure.BUSY
        assert model.status.entries[token._slot].output_pinned
    finally:
        lock.release()
    monkeypatch.setattr(receiver._discarded, "set", original)
    assert receiver.close(deadline=deadline()) is OutputReleaseOutcome.CLEARED
