"""Header-before-allocation and bounded in-place transport contracts (D-114)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from maskgw.pgwire.result_frame import (
    ResultDeadline,
    ResultFrameError,
    ResultLimits,
    inspect_result_header,
)
from maskgw.pgwire.transport import RawChannel, TransportError, TransportFailure, TransportLimits
from tests.test_result_frame import HEADER, IDENTITY, frame


def test_header_only_returns_exact_bounded_shape():
    raw = frame(rows=[[b"hello"]])
    header = inspect_result_header(
        raw[: HEADER.size], expected=IDENTITY, limits=ResultLimits(max_rows=5)
    )
    assert (header.frame_bytes, header.columns, header.rows, header.truncated) == (
        len(raw),
        1,
        1,
        False,
    )


@pytest.mark.parametrize("fields", [{11: 2**32 - 1}, {11: 0}, {9: 0}, {10: 100}, {8: 5}])
def test_impossible_or_wrong_header_refuses_without_body(fields):
    raw = frame(fields=fields)
    with pytest.raises(ResultFrameError):
        inspect_result_header(
            raw[: HEADER.size], expected=IDENTITY, limits=ResultLimits(max_rows=5)
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0, True, 10**1000, "CANARY"])
def test_remaining_invalid_clock_is_finite_zero(value):
    deadline = ResultDeadline(expires_at=100, clock=lambda: value)
    assert deadline.remaining() == 0.0
    assert math.isfinite(deadline.remaining())


def test_remaining_clock_failure_is_zero_not_native_error():
    def broken():
        raise OSError("CANARY_CLOCK")

    assert ResultDeadline(expires_at=100, clock=broken).remaining() == 0.0


class IntoSocket:
    def __init__(self, result: Any = 2, error: Exception | None = None):
        self.result = result
        self.error = error
        self.sizes: list[int] = []

    def settimeout(self, value):
        assert 0 < value <= 0.25

    def recv_into(self, view, size):
        self.sizes.append(size)
        if self.error is not None:
            raise self.error
        view[:2] = b"ok"
        return self.result


def channel(sock: Any) -> RawChannel:
    return RawChannel(sock, stop=lambda: False, limits=TransportLimits(chunk_bytes=3))


def test_recv_into_fills_existing_buffer_with_bounded_slice():
    buffer = bytearray(10)
    sock = IntoSocket()
    with memoryview(buffer) as view:
        assert channel(sock).recv_into(view, ResultDeadline(expires_at=100, clock=lambda: 0)) == 2
    assert buffer == b"ok" + bytes(8)
    assert sock.sizes == [3]


@pytest.mark.parametrize("progress", [True, -1, 4, 1.5, None, 0])
def test_recv_into_invalid_progress_or_eof_fails_closed(progress):
    with memoryview(bytearray(10)) as view, pytest.raises(TransportError) as caught:
        channel(IntoSocket(progress)).recv_into(
            view, ResultDeadline(expires_at=100, clock=lambda: 0)
        )
    assert caught.value.kind is (TransportFailure.EOF if progress == 0 else TransportFailure.IO)
    assert caught.value.__context__ is None


@pytest.mark.parametrize("error", [OSError("CANARY"), ValueError("CANARY"), TypeError("CANARY")])
def test_recv_into_sanitizes_native_failures(error):
    with memoryview(bytearray(10)) as view, pytest.raises(TransportError) as caught:
        channel(IntoSocket(error=error)).recv_into(
            view, ResultDeadline(expires_at=100, clock=lambda: 0)
        )
    assert caught.value.kind is TransportFailure.IO and caught.value.__context__ is None
    assert "CANARY" not in str(caught.value)


@pytest.mark.parametrize(
    "view", [memoryview(b"a"), memoryview(bytearray(8))[::2], memoryview(bytearray())]
)
def test_recv_into_refuses_readonly_noncontiguous_and_empty(view):
    try:
        with pytest.raises(TransportError):
            channel(IntoSocket()).recv_into(view, ResultDeadline(expires_at=100, clock=lambda: 0))
    finally:
        view.release()


def test_released_view_is_sanitized_transport_error():
    view = memoryview(bytearray(5))
    view.release()
    with pytest.raises(TransportError) as caught:
        channel(IntoSocket()).recv_into(view, ResultDeadline(expires_at=100, clock=lambda: 0))
    assert caught.value.kind is TransportFailure.IO and caught.value.__context__ is None
