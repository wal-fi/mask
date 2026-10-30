"""D-114: bounded internal result reception and ownership, NOT a SQL ingress.

The coordinator must serialize ALL ledger access with the same plain Lock.
Session P credits stay reserved; the output pin prevents reuse until private
buffers/views are discarded. Declared overhead is NOT an OS/native/TLS quota.
No listener, worker, thread, socket creation, registry or automatic retry here.
"""

from __future__ import annotations

import traceback
from _thread import LockType
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from threading import Event
from typing import Final, NoReturn

from maskgw.pgwire.result_frame import (
    RESULT_HEADER_BYTES,
    ResultDeadline,
    ResultErrorCategory,
    ResultFrameError,
    ResultIdentity,
    ResultLimits,
    ValidatedResult,
    inspect_result_header,
    validate_result,
)
from maskgw.pgwire.transport import RawChannel, TlsChannel, TransportError, TransportFailure
from maskgw.runtime.budget import (
    BudgetError,
    BudgetLedger,
    BudgetToken,
    OutputReleaseOutcome,
)

_LOCK_SLICE: Final = 0.25
_MAX_ERROR_CHAIN: Final = 32


class ReceiverFailure(StrEnum):
    STATE = "RESULT_RECEIVER_STATE"
    BUSY = "RESULT_RECEIVER_BUSY"
    BUDGET = "RESULT_RECEIVER_BUDGET"
    IO = "RESULT_RECEIVER_IO"
    LIMIT = "RESULT_RECEIVER_LIMIT"
    PROTOCOL = "RESULT_RECEIVER_PROTOCOL"
    DEADLINE = "RESULT_RECEIVER_DEADLINE"


class ReceiverError(Exception):
    def __init__(self, category: ReceiverFailure) -> None:
        self.category = category if type(category) is ReceiverFailure else ReceiverFailure.STATE
        super().__init__(self.category.value)


def _fail(category: ReceiverFailure) -> NoReturn:
    raise ReceiverError(category) from None


class ReceiverState(StrEnum):
    NEW = "NEW"
    READING = "READING"
    READY = "READY"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    DISCARDING = "DISCARDING"
    HELD = "HELD"
    CLOSED = "CLOSED"


@dataclass(frozen=True, slots=True)
class ResultSummary:
    columns: int
    rows: int
    truncated: bool


def _category(error: Exception) -> ReceiverFailure:
    if isinstance(error, ResultFrameError):
        if error.category is ResultErrorCategory.DEADLINE:
            return ReceiverFailure.DEADLINE
        if error.category is ResultErrorCategory.LIMIT:
            return ReceiverFailure.LIMIT
        return ReceiverFailure.PROTOCOL
    if isinstance(error, TransportError) and error.kind is TransportFailure.TIMEOUT:
        return ReceiverFailure.DEADLINE
    if isinstance(error, MemoryError):
        return ReceiverFailure.LIMIT
    return ReceiverFailure.IO


def _clear_error(error: BaseException) -> bool:
    """Clear inactive frames on BOTH chains. Unprovable cleanup retains the pin."""
    pending = [error]
    seen: set[int] = set()
    try:
        while pending:
            current = pending.pop()
            if isinstance(current, BaseExceptionGroup):
                return False  # nested exceptions may retain frames; quarantine, never guess
            if isinstance(current, TransportError) and current.cleanup_uncertain:
                return False  # transport sanitized a chain/group; no false disposal claim
            if id(current) in seen:
                continue
            if len(seen) == _MAX_ERROR_CHAIN:
                return False
            seen.add(id(current))
            traceback.clear_frames(current.__traceback__)
            if current.__cause__ is not None:
                pending.append(current.__cause__)
            if current.__context__ is not None:
                pending.append(current.__context__)
    except Exception:
        return False
    return True


def _fill(channel: RawChannel, buffer: bytearray, start: int, deadline: ResultDeadline) -> None:
    with memoryview(buffer) as view:
        offset = start
        while offset < len(view):
            with view[offset:] as piece:
                offset += channel.recv_into(piece, deadline)


def _read_payload(
    channel: RawChannel, expected: ResultIdentity, limits: ResultLimits, deadline: ResultDeadline
) -> ValidatedResult:
    header = bytearray(RESULT_HEADER_BYTES)
    _fill(channel, header, 0, deadline)
    info = inspect_result_header(bytes(header), expected=expected, limits=limits)
    deadline.check()
    buffer = bytearray(info.frame_bytes)
    buffer[:RESULT_HEADER_BYTES] = header
    del header
    _fill(channel, buffer, RESULT_HEADER_BYTES, deadline)
    raw = bytes(buffer)
    del buffer  # no proportional mutable buffer survives validation
    return validate_result(raw, expected=expected, limits=limits, deadline=deadline)


def _receive_captured(
    channel: RawChannel, expected: ResultIdentity, limits: ResultLimits, deadline: ResultDeadline
) -> tuple[ValidatedResult | None, ReceiverFailure | None, bool]:
    try:
        return _read_payload(channel, expected, limits, deadline), None, False
    except Exception as error:
        return None, _category(error), not _clear_error(error)


def _send_payload(
    owner: ValidatedResult, channel: RawChannel | TlsChannel, deadline: ResultDeadline
) -> None:
    chunks = owner.iter_chunks(deadline=deadline)
    try:
        for piece in chunks:
            try:
                channel.send_all(piece, deadline)
            finally:
                piece.release()
    finally:
        chunks.close()


def _send_captured(
    owner: ValidatedResult, channel: RawChannel | TlsChannel, deadline: ResultDeadline
) -> tuple[ReceiverFailure | None, bool]:
    try:
        _send_payload(owner, channel, deadline)
    except Exception as error:
        del owner  # this active frame cannot be cleared yet; retain no payload here
        return _category(error), not _clear_error(error)
    return None, False


class ResultReceiver:
    """One result, no payload-returning API and no GC finalizer returning credits.

    Exact channel classes are audited code collaborators, NOT a Python sandbox.
    Losing this object retains the ledger pin. The future coordinator still
    owns session/worker/socket cleanup and may not accept SQL yet.
    """

    def __init__(  # noqa: PLR0913 -- explicit trusted coordinator dependencies
        self,
        ledger: BudgetLedger,
        session: BudgetToken,
        *,
        lock: LockType,
        expected: ResultIdentity,
        limits: ResultLimits,
        overhead_bytes: int,
        deadline: ResultDeadline,
    ) -> None:
        if (
            type(ledger) is not BudgetLedger
            or type(session) is not BudgetToken
            or type(lock) is not LockType
            or type(expected) is not ResultIdentity
            or type(limits) is not ResultLimits
            or type(deadline) is not ResultDeadline
        ):
            _fail(ReceiverFailure.STATE)
        self._ledger = ledger
        self._lock = lock
        self._expected = expected
        self._limits = limits
        self._deadline = deadline
        self._state = ReceiverState.NEW
        self._owner: ValidatedResult | None = None
        self._summary: ResultSummary | None = None
        self._operation_done = Event()
        self._uncertain = Event()
        self._discarded = Event()
        self._drain = True
        failed = False
        with self._coordinated(deadline):
            try:
                self._pin = ledger.begin_output(
                    session, frame_bytes=limits.max_frame_bytes, overhead_bytes=overhead_bytes
                )
            except BudgetError:
                failed = True
        if failed:
            _fail(ReceiverFailure.BUDGET)

    def __repr__(self) -> str:
        return "ResultReceiver(<private>)"

    @contextmanager
    def _coordinated(self, deadline: ResultDeadline) -> Iterator[None]:
        if type(deadline) is not ResultDeadline:
            _fail(ReceiverFailure.DEADLINE)
        remaining = deadline.remaining()
        if remaining <= 0:
            _fail(ReceiverFailure.DEADLINE)
        if not self._lock.acquire(timeout=min(remaining, _LOCK_SLICE)):
            _fail(ReceiverFailure.BUSY)
        try:
            yield
        finally:
            self._lock.release()

    def _settle_locked(self) -> None:
        if (
            self._state in (ReceiverState.READING, ReceiverState.SENDING)
            and self._operation_done.is_set()
        ):
            self._state = ReceiverState.FAILED

    def status(self, *, deadline: ResultDeadline) -> ReceiverState:
        with self._coordinated(deadline):
            self._settle_locked()
            return self._state

    def receive(self, channel: RawChannel) -> None:
        with self._coordinated(self._deadline):
            if self._state is not ReceiverState.NEW or type(channel) is not RawChannel:
                _fail(ReceiverFailure.STATE)
            completion = Event()
            self._operation_done = completion
            self._state = ReceiverState.READING
        owner = None
        failure = None
        try:
            owner, failure, uncertain = _receive_captured(
                channel, self._expected, self._limits, self._deadline
            )
            if uncertain:
                self._uncertain.set()
            with self._coordinated(self._deadline):
                if failure is not None or owner is None:
                    self._state = ReceiverState.FAILED
                else:
                    self._summary = ResultSummary(owner.columns, owner.rows, owner.truncated)
                    self._owner = owner
                    owner = None  # no second local owner can survive READY publication
                    self._state = ReceiverState.READY
        except BaseException as error:
            if not isinstance(error, Exception):
                self._uncertain.set()  # caller's interrupt traceback may still own payload
            raise
        finally:
            owner = None
            completion.set()  # only THIS operation; cannot settle a subsequent send
        if failure is not None:
            _fail(failure)

    def send_to(
        self, channel: RawChannel | TlsChannel, *, deadline: ResultDeadline
    ) -> ResultSummary:
        with self._coordinated(deadline):
            if self._state is not ReceiverState.READY or type(channel) not in (
                RawChannel,
                TlsChannel,
            ):
                _fail(ReceiverFailure.STATE)
            if self._owner is None or self._summary is None:
                _fail(ReceiverFailure.STATE)
            completion = Event()
            self._operation_done = completion
            self._state = ReceiverState.SENDING
        try:
            failure, uncertain = _send_captured(self._owner, channel, deadline)
            if uncertain:
                self._uncertain.set()
            with self._coordinated(deadline):
                self._state = ReceiverState.SENT if failure is None else ReceiverState.FAILED
        except BaseException as error:
            if not isinstance(error, Exception):
                self._uncertain.set()
            raise
        finally:
            completion.set()
        if failure is not None:
            _fail(failure)
        return self._summary

    def close(self, *, deadline: ResultDeadline) -> OutputReleaseOutcome:
        """Discard outside lock, then unpin; fresh cleanup deadline is mandatory."""
        owner = None
        with self._coordinated(deadline):
            self._settle_locked()
            if self._state is ReceiverState.CLOSED:
                return OutputReleaseOutcome.ALREADY_CLEARED
            if self._state in (ReceiverState.READING, ReceiverState.SENDING):
                _fail(ReceiverFailure.STATE)
            if self._state in (ReceiverState.DISCARDING, ReceiverState.HELD):
                if not self._discarded.is_set():
                    _fail(ReceiverFailure.STATE)
            else:
                self._drain = self._state is not ReceiverState.SENT
                self._state = ReceiverState.DISCARDING
                owner = self._owner
                self._owner = None
        del owner  # actual last known reference dropped OUTSIDE the coordinator lock
        self._discarded.set()
        with self._coordinated(deadline):
            if self._state is ReceiverState.CLOSED:
                return OutputReleaseOutcome.ALREADY_CLEARED
            failed = False
            outcome = OutputReleaseOutcome.HELD
            try:
                outcome = self._ledger.end_output(
                    self._pin, discarded=not self._uncertain.is_set(), drain=self._drain
                )
            except BudgetError:
                failed = True
            self._state = (
                ReceiverState.HELD
                if failed or outcome is OutputReleaseOutcome.HELD
                else ReceiverState.CLOSED
            )
        if failed:
            _fail(ReceiverFailure.BUDGET)
        return outcome
