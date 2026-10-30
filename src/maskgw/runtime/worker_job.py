"""One private job composition; no worker loop, I/O transport or OS boundary.

Use only under exclusive adapter ownership. This is not cancellation/shutdown
middleware: every interruption becomes a fatal outcome that the future owner
MUST stop/reap. No operational module imports this body yet. A cooperative
deadline is not containment of a blocked driver, parser or native allocation.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, cast

from maskgw.db.execution_error import ExecutionFailure, TypedExecutionError, TypedExecutionTimeout
from maskgw.db.postgres import PostgresAdapter
from maskgw.db.result import DatabaseResultTypeError, TypedMaskedResult
from maskgw.errors import InvalidQuery, QueryRejected
from maskgw.pgwire.result_encoder import EncodeError, EncodeFailure, encode_result
from maskgw.pgwire.result_frame import (
    RESULT_HEADER_BYTES,
    ResultDeadline,
    ResultErrorCategory,
    ResultFrameError,
    ResultIdentity,
    ResultLimits,
)

_MAX_SQL_BYTES: Final = 64 * 1024
_SQL_BLOCK: Final = 4096
_MAX_FRAME_BYTES: Final = 16 * 1024 * 1024


class JobFailure(StrEnum):
    QUERY = "QUERY"
    TIMEOUT = "TIMEOUT"
    TYPE = "TYPE"
    LIMIT = "LIMIT"
    MEMORY = "MEMORY"
    RESOURCE = "RESOURCE"
    CONNECTION = "CONNECTION"
    INTERNAL = "INTERNAL"
    PROTOCOL = "PROTOCOL"
    DEADLINE = "DEADLINE"


_CANDIDATES: Final = frozenset(
    {JobFailure.QUERY, JobFailure.TIMEOUT, JobFailure.TYPE, JobFailure.LIMIT}
)
_TYPED: Final = {
    ExecutionFailure.QUERY: JobFailure.QUERY,
    ExecutionFailure.RESOURCE: JobFailure.RESOURCE,
    ExecutionFailure.CONNECTION: JobFailure.CONNECTION,
    ExecutionFailure.INTERNAL: JobFailure.INTERNAL,
}
_ENCODE: Final = {category: JobFailure[category.name] for category in EncodeFailure}


@dataclass(frozen=True, slots=True, repr=False, kw_only=True)
class JobOutcome:
    """Trusted local construction only; not an IPC schema or frame authenticator."""

    frame: bytes | None
    failure: JobFailure | None
    can_continue: bool

    def __post_init__(self) -> None:
        valid = type(self.can_continue) is bool
        if self.failure is None:
            valid = (
                valid
                and type(self.frame) is bytes
                and RESULT_HEADER_BYTES <= len(self.frame) <= _MAX_FRAME_BYTES
                and self.can_continue is True
            )
        else:
            valid = (
                valid
                and type(self.failure) is JobFailure
                and self.frame is None
                and (not self.can_continue or self.failure in _CANDIDATES)
            )
        if not valid:
            raise ValueError("resultado de job invalido")

    def __repr__(self) -> str:
        return "JobOutcome(<redacted>)"

    def __bool__(self) -> bool:
        raise TypeError("resultado de job exige inspecao explicita")


def _classify(error: BaseException) -> JobFailure:  # noqa: PLR0911 - closed exact-type mapping
    """No message, chaining, driver inspection or subclass-based recovery."""
    kind = type(error)
    if kind is TypedExecutionTimeout:
        return JobFailure.TIMEOUT
    if kind is TypedExecutionError:
        category = cast(TypedExecutionError, error).category
        if type(category) is ExecutionFailure:
            return _TYPED.get(category, JobFailure.INTERNAL)
    if kind is InvalidQuery or kind is QueryRejected:
        return JobFailure.QUERY
    if kind is DatabaseResultTypeError:
        return JobFailure.TYPE
    if kind is EncodeError:
        encode_category = cast(EncodeError, error).category
        if type(encode_category) is EncodeFailure:
            return _ENCODE[encode_category]
    if kind is MemoryError:
        return JobFailure.MEMORY
    if kind is ResultFrameError:
        frame_error = cast(ResultFrameError, error)
        if frame_error.memory_exhausted is True:
            return JobFailure.MEMORY
        if frame_error.category is ResultErrorCategory.DEADLINE:
            return JobFailure.DEADLINE
        return JobFailure.PROTOCOL
    return JobFailure.INTERNAL


def _valid_sql(sql: str) -> bool:
    if type(sql) is not str or len(sql) > _MAX_SQL_BYTES:
        return False
    total = 0
    for start in range(0, len(sql), _SQL_BLOCK):
        block = sql[start : start + _SQL_BLOCK]
        if "\0" in block:
            return False
        try:
            total += len(block.encode("utf8", errors="strict"))
        except UnicodeEncodeError:
            return False
        if total > _MAX_SQL_BYTES:
            return False
    return True


def _healthy(adapter: PostgresAdapter, deadline: ResultDeadline) -> bool:
    """Never renew the same absolute clock around possibly slow introspection."""
    deadline.check()
    healthy = adapter._typed_connection_healthy() is True
    deadline.check()
    return healthy


def run_job(  # noqa: PLR0911, PLR0912 - explicit fail-closed gates, no shared side effects
    adapter: PostgresAdapter,
    sql: str,
    *,
    identity: ResultIdentity,
    limits: ResultLimits,
    deadline: ResultDeadline,
) -> JobOutcome:
    """One masked execution, one encode; return only a complete frame or intent.

    The future owner binds identity to its generation/lease, tracks sticky fatal
    state and monotonic jobs, reserves resources, and stops/reaps on fatal.
    Neither health nor can_continue grants that ownership or OS certification.
    No connect/close/cancel/retry or resource release is performed here.
    """
    frame: bytes | None = None
    result: TypedMaskedResult | None = None
    category = JobFailure.PROTOCOL
    candidate = False
    try:
        if (
            type(identity) is not ResultIdentity
            or type(limits) is not ResultLimits
            or type(deadline) is not ResultDeadline
            or type(adapter) is not PostgresAdapter
        ):
            return JobOutcome(frame=None, failure=category, can_continue=False)
        ResultIdentity.__post_init__(identity)
        ResultLimits.__post_init__(limits)
        ResultDeadline.__post_init__(deadline)
        deadline.check()
        if not _valid_sql(sql):
            return JobOutcome(frame=None, failure=category, can_continue=False)
        rows = adapter._settings.max_rows
        if type(rows) is not int or rows != limits.max_rows:
            return JobOutcome(frame=None, failure=category, can_continue=False)
        if not _healthy(adapter, deadline):
            return JobOutcome(frame=None, failure=JobFailure.CONNECTION, can_continue=False)
        result = adapter._execute_typed_validated(sql)
        if not _healthy(adapter, deadline):
            return JobOutcome(frame=None, failure=JobFailure.CONNECTION, can_continue=False)
        frame = encode_result(result, identity=identity, limits=limits, deadline=deadline)
        result = None
        if (
            type(frame) is not bytes
            or not RESULT_HEADER_BYTES <= len(frame) <= limits.max_frame_bytes
        ):
            return JobOutcome(frame=None, failure=JobFailure.INTERNAL, can_continue=False)
        if not _healthy(adapter, deadline):
            return JobOutcome(frame=None, failure=JobFailure.CONNECTION, can_continue=False)
        return JobOutcome(frame=frame, failure=None, can_continue=True)
    except BaseException as error:  # fatal control signals, never a reusable interruption
        frame = None
        result = None
        try:
            category = _classify(error)
            traceback.clear_frames(error.__traceback__)
            candidate = category in _CANDIDATES
        except BaseException:
            category, candidate = JobFailure.INTERNAL, False
    # No original error, data result or traceback is attached to this outcome.
    if candidate:
        try:
            if not _healthy(adapter, deadline):
                category, candidate = JobFailure.CONNECTION, False
        except BaseException as error:
            category, candidate = JobFailure.INTERNAL, False
            try:
                if type(error) is ResultFrameError:
                    category = _classify(error)
                traceback.clear_frames(error.__traceback__)
            except BaseException:
                category = JobFailure.INTERNAL
    return JobOutcome(frame=None, failure=category, can_continue=candidate)
