"""Independent transport invariants, including buffered TLS operations."""

from __future__ import annotations

import socket
import ssl
from typing import cast

import pytest

from maskgw.pgwire.transport import (
    Deadline,
    RawChannel,
    TlsChannel,
    TransportError,
    TransportFailure,
    TransportLimits,
)


class _Socket:
    def settimeout(self, _value: float) -> None:
        pass

    def send(self, data: bytes | memoryview) -> int:
        return len(data)


class _Ssl:
    def __init__(
        self, outgoing: ssl.MemoryBIO, *, handshake_output: bytes = b"", partial: bool = False
    ) -> None:
        self.outgoing = outgoing
        self.handshake_output = handshake_output
        self.partial = partial
        self.accepted = bytearray()

    def do_handshake(self) -> None:
        self.outgoing.write(self.handshake_output)

    def read(self, size: int) -> bytes:
        return b"x" * size

    def write(self, data: bytes | memoryview) -> int:
        accepted = 1 if self.partial else len(data)
        self.accepted += data[:accepted]
        return accepted


class _Context:
    def __init__(self, *, handshake_output: bytes = b"", partial: bool = False) -> None:
        self.handshake_output = handshake_output
        self.partial = partial
        self.instance: _Ssl | None = None

    def wrap_bio(
        self, _incoming: ssl.MemoryBIO, outgoing: ssl.MemoryBIO, *, server_side: bool
    ) -> _Ssl:
        assert server_side
        self.instance = _Ssl(outgoing, handshake_output=self.handshake_output, partial=self.partial)
        return self.instance


def _channel(
    *, stopped: bool = False, context: _Context | None = None, limits: TransportLimits | None = None
) -> TlsChannel:
    raw = RawChannel(
        cast(socket.socket, _Socket()), stop=lambda: stopped, limits=limits or TransportLimits()
    )
    return TlsChannel(raw, cast(ssl.SSLContext, context or _Context()))


@pytest.mark.parametrize("operation", ["handshake", "read", "write"])
@pytest.mark.parametrize("stopped", [False, True])
def test_buffered_tls_checks_deadline_and_stop(operation, stopped):
    channel = _channel(stopped=stopped)
    deadline = Deadline(10 if stopped else 0)
    with pytest.raises(TransportError) as captured:
        if operation == "handshake":
            channel.handshake(deadline)
        elif operation == "read":
            channel.recv_exact(1, deadline)
        else:
            channel.send_all(b"x", deadline)
    assert captured.value.kind == (
        TransportFailure.STOPPED if stopped else TransportFailure.TIMEOUT
    )
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_successful_tls_handshake_cannot_exceed_byte_budget():
    channel = _channel(
        context=_Context(handshake_output=b"12345"),
        limits=TransportLimits(tls_handshake_bytes=4),
    )
    with pytest.raises(TransportError) as captured:
        channel.handshake(Deadline(10))
    assert captured.value.kind == TransportFailure.LIMIT


def test_tls_write_preserves_partial_plaintext_acceptance():
    context = _Context(partial=True)
    channel = _channel(context=context)
    channel.send_all(b"abc", Deadline(10))
    assert context.instance is not None
    assert context.instance.accepted == b"abc"


def test_raw_write_without_progress_is_an_immediate_io_failure():
    class NoProgress(_Socket):
        calls = 0

        def send(self, data: bytes | memoryview) -> int:
            assert data
            self.calls += 1
            assert self.calls == 1, "send(0) must not spin until the deadline"
            return 0

    peer = NoProgress()
    channel = RawChannel(cast(socket.socket, peer), stop=lambda: False, limits=TransportLimits())
    with pytest.raises(TransportError) as captured:
        channel.send_all(b"abc", Deadline(10))
    assert captured.value.kind is TransportFailure.IO
    assert peer.calls == 1
