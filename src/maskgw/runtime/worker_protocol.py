"""Private bounded worker wire v2. Pure codecs, no I/O, SQL execution or caller.

Headers are checked BEFORE allocating a body. Empty RESULT precedes an existing
self-delimited D-113 frame. DONE must precede exposure. No v1 fallback.
No record, digest or READY authenticates arbitrary malicious worker code.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Final

from maskgw.pgwire.result_frame import ResultIdentity, ResultLimits

MAX_SNAPSHOT_BYTES: Final = 65536
MAX_SQL_BYTES: Final = 65536
_MAX_ID: Final = (1 << 63) - 1
_MAX_PID: Final = (1 << 31) - 1
_MAX_FRAME: Final = 16 * 1024 * 1024
_NONCE_SIZE: Final = 32
_MAX_DEADLINE_SECONDS: Final = 610.0  # 600s setting + 10s budget
_SIGKILL: Final = 9
_HEADER: Final = struct.Struct("!4sBBHI")
_MAGIC: Final = b"MGW2"
_VERSION: Final = 2
HEADER_BYTES: Final = _HEADER.size
_KEY: Final = struct.Struct("!16s16sQQ")
_LIMITS: Final = struct.Struct("!IIIHH")
_INIT: Final = struct.Struct("!d32sI")
_QUERY: Final = struct.Struct("!Qd")
_GUARD: Final = struct.Struct("!IIQBBH")
_ERROR: Final = struct.Struct("!QBBH")
_JOB: Final = struct.Struct("!Q")
_INIT_FIXED: Final = _KEY.size + _LIMITS.size + _INIT.size
_QUERY_FIXED: Final = _KEY.size + _QUERY.size


class Kind(IntEnum):
    GUARD_READY = 1
    INIT = 2
    OPENED = 3
    QUERY = 4
    ERROR = 5
    RESULT = 6
    DONE = 7
    CLOSE = 8


class WireFailure(IntEnum):
    QUERY = 1
    TIMEOUT = 2
    TYPE = 3
    LIMIT = 4
    MEMORY = 5
    RESOURCE = 6
    CONNECTION = 7
    INTERNAL = 8
    PROTOCOL = 9
    DEADLINE = 10


_KINDS: Final = {item.value: item for item in Kind}
_FAILURES: Final = {item.value: item for item in WireFailure}
_RECOVERABLE: Final = frozenset(
    {WireFailure.QUERY, WireFailure.TIMEOUT, WireFailure.TYPE, WireFailure.LIMIT}
)
_LENGTHS: Final = {
    Kind.GUARD_READY: (_GUARD.size, _GUARD.size),
    Kind.INIT: (_INIT_FIXED + 1, _INIT_FIXED + MAX_SNAPSHOT_BYTES),
    Kind.OPENED: (_NONCE_SIZE, _NONCE_SIZE),
    Kind.QUERY: (_QUERY_FIXED + 1, _QUERY_FIXED + MAX_SQL_BYTES),
    Kind.ERROR: (_KEY.size + _ERROR.size, _KEY.size + _ERROR.size),
    Kind.RESULT: (0, 0),
    Kind.DONE: (_KEY.size + _JOB.size, _KEY.size + _JOB.size),
    Kind.CLOSE: (0, 0),
}


class WorkerProtocolError(Exception):
    """Fixed error only. The owner must discard buffers and clear tracebacks."""

    def __init__(self) -> None:
        super().__init__("protocolo privado do worker recusado")


def _need(condition: bool) -> None:
    if not condition:
        raise WorkerProtocolError()


def _number(value: object, maximum: int, *, minimum: int = 1) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _bytes(value: object, size: int) -> bool:
    return type(value) is bytes and len(value) == size


def _expiry(value: object) -> bool:
    return type(value) is float and math.isfinite(value) and value > 0


def check_deadline(expires_at: float, *, now: float, maximum_seconds: float) -> None:
    """Same Linux monotonic clock in both processes; never rebase a deadline."""
    _need(_expiry(expires_at) and _expiry(maximum_seconds))
    _need(type(now) is float and math.isfinite(now) and now >= 0)
    _need(0 < expires_at - now <= maximum_seconds <= _MAX_DEADLINE_SECONDS)


@dataclass(frozen=True, slots=True, repr=False)
class SessionKey:
    session_id: bytes
    datasource_id: bytes
    generation: int
    record_revision: int

    def __post_init__(self) -> None:
        _need(_bytes(self.session_id, 16) and _bytes(self.datasource_id, 16))
        _need(_number(self.generation, _MAX_ID) and _number(self.record_revision, _MAX_ID))

    def result_identity(self, job_id: int) -> ResultIdentity:
        SessionKey.__post_init__(self)
        _need(_number(job_id, _MAX_ID))
        return ResultIdentity(
            session_id=self.session_id,
            datasource_id=self.datasource_id,
            generation=self.generation,
            record_revision=self.record_revision,
            job_id=job_id,
        )

    def datasource_text(self) -> str:
        SessionKey.__post_init__(self)
        return "dso_" + self.datasource_id.hex()

    def __repr__(self) -> str:
        return "SessionKey(<private>)"


def _key_bytes(key: SessionKey) -> bytes:
    _need(type(key) is SessionKey)
    SessionKey.__post_init__(key)
    return _KEY.pack(key.session_id, key.datasource_id, key.generation, key.record_revision)


def _key_from(data: bytes) -> SessionKey:
    return SessionKey(*_KEY.unpack_from(data))


def _limits_valid(limits: ResultLimits) -> None:
    _need(type(limits) is ResultLimits)
    failed = False
    try:
        ResultLimits.__post_init__(limits)
    except MemoryError:
        raise
    except Exception:
        failed = True
    if failed:
        raise WorkerProtocolError()


@dataclass(frozen=True, slots=True, repr=False, eq=False)
class SecretInit:
    key: SessionKey
    limits: ResultLimits
    expires_at: float
    nonce: bytes
    snapshot: bytes

    def __post_init__(self) -> None:
        _key_bytes(self.key)
        _limits_valid(self.limits)
        _need(_expiry(self.expires_at) and _bytes(self.nonce, _NONCE_SIZE))
        _need(type(self.snapshot) is bytes and 1 <= len(self.snapshot) <= MAX_SNAPSHOT_BYTES)

    def __repr__(self) -> str:
        return "SecretInit(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class Query:
    key: SessionKey
    job_id: int
    expires_at: float
    sql: bytes

    def __post_init__(self) -> None:
        _key_bytes(self.key)
        _need(_number(self.job_id, _MAX_ID) and _expiry(self.expires_at))
        _need(
            type(self.sql) is bytes
            and 1 <= len(self.sql) <= MAX_SQL_BYTES
            and b"\0" not in self.sql
        )
        invalid = False
        try:
            self.sql.decode("utf-8", errors="strict")
        except UnicodeError:
            invalid = True
        if invalid:
            raise WorkerProtocolError()

    def __repr__(self) -> str:
        return "Query(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class ErrorReply:
    key: SessionKey
    job_id: int
    category: WireFailure
    can_continue: bool

    def __post_init__(self) -> None:
        _key_bytes(self.key)
        _need(_number(self.job_id, _MAX_ID, minimum=0))
        _need(type(self.category) is WireFailure and type(self.can_continue) is bool)
        _need(not self.can_continue or (self.job_id > 0 and self.category in _RECOVERABLE))

    def __repr__(self) -> str:
        return "ErrorReply(<private>)"


def _body(kind: Kind, data: bytes) -> None:
    _need(type(kind) is Kind and type(data) is bytes)
    check_length(kind, len(data))


def check_length(kind: Kind, size: int) -> None:
    _need(type(kind) is Kind and _number(size, _MAX_FRAME, minimum=0))
    low, high = _LENGTHS[kind]
    _need(low <= size <= high)


def parse_header(data: bytes) -> tuple[Kind, int]:
    _need(_bytes(data, HEADER_BYTES))
    magic, version, tag, reserved, size = _HEADER.unpack(data)
    _need(magic == _MAGIC and version == _VERSION and reserved == 0 and tag in _KINDS)
    kind = _KINDS[tag]
    check_length(kind, size)
    return kind, size


def _packet(kind: Kind, data: bytes) -> bytes:
    _body(kind, data)
    return _HEADER.pack(_MAGIC, _VERSION, kind.value, 0, len(data)) + data


def encode_init(value: SecretInit) -> bytes:
    _need(type(value) is SecretInit)
    SecretInit.__post_init__(value)
    limits = value.limits
    data = (
        _key_bytes(value.key)
        + _LIMITS.pack(
            limits.max_rows,
            limits.max_frame_bytes,
            limits.max_cell_bytes,
            limits.max_columns,
            limits.max_name_bytes,
        )
        + _INIT.pack(value.expires_at, value.nonce, len(value.snapshot))
        + value.snapshot
    )
    return _packet(Kind.INIT, data)


def decode_init(data: bytes) -> SecretInit:
    _body(Kind.INIT, data)
    key = _key_from(data)
    rows, frame, cell, columns, name = _LIMITS.unpack_from(data, _KEY.size)
    failed = False
    limits: ResultLimits | None = None
    try:
        limits = ResultLimits(
            max_rows=rows,
            max_frame_bytes=frame,
            max_cell_bytes=cell,
            max_columns=columns,
            max_name_bytes=name,
        )
    except MemoryError:
        raise
    except Exception:
        failed = True
    if failed or limits is None:
        raise WorkerProtocolError()
    expiry, nonce, size = _INIT.unpack_from(data, _KEY.size + _LIMITS.size)
    _need(size == len(data) - _INIT_FIXED)
    return SecretInit(key, limits, expiry, nonce, data[_INIT_FIXED:])


def encode_query(value: Query) -> bytes:
    _need(type(value) is Query)
    Query.__post_init__(value)
    return _packet(
        Kind.QUERY, _key_bytes(value.key) + _QUERY.pack(value.job_id, value.expires_at) + value.sql
    )


def decode_query(data: bytes) -> Query:
    _body(Kind.QUERY, data)
    job, expiry = _QUERY.unpack_from(data, _KEY.size)
    return Query(_key_from(data), job, expiry, data[_QUERY_FIXED:])


def encode_error(value: ErrorReply) -> bytes:
    _need(type(value) is ErrorReply)
    ErrorReply.__post_init__(value)
    return _packet(
        Kind.ERROR,
        _key_bytes(value.key)
        + _ERROR.pack(value.job_id, value.category.value, int(value.can_continue), 0),
    )


def decode_error(data: bytes) -> ErrorReply:
    _body(Kind.ERROR, data)
    job, code, continuing, reserved = _ERROR.unpack_from(data, _KEY.size)
    _need(code in _FAILURES and continuing in (0, 1) and reserved == 0)
    return ErrorReply(_key_from(data), job, _FAILURES[code], bool(continuing))


def encode_done(key: SessionKey, job_id: int) -> bytes:
    _need(_number(job_id, _MAX_ID))
    return _packet(Kind.DONE, _key_bytes(key) + _JOB.pack(job_id))


def decode_done(data: bytes) -> tuple[SessionKey, int]:
    _body(Kind.DONE, data)
    job = _JOB.unpack_from(data, _KEY.size)[0]
    _need(_number(job, _MAX_ID))
    return _key_from(data), job


def encode_result_notice() -> bytes:
    """Only a notice; D-113 is the single authority for the following size."""
    return _packet(Kind.RESULT, b"")


def encode_opened(tag: bytes) -> bytes:
    return _packet(Kind.OPENED, tag)


def decode_opened(data: bytes) -> bytes:
    _body(Kind.OPENED, data)
    return data


def encode_guard(pid: int, parent: int, address_bytes: int) -> bytes:
    _need(_number(pid, _MAX_PID, minimum=2) and _number(parent, _MAX_PID) and pid != parent)
    _need(_number(address_bytes, 4096 * 1024 * 1024, minimum=64 * 1024 * 1024))
    return _packet(Kind.GUARD_READY, _GUARD.pack(pid, parent, address_bytes, 0, _SIGKILL, 0))


def decode_guard(data: bytes) -> tuple[int, int, int]:
    _body(Kind.GUARD_READY, data)
    pid, parent, address, dumpable, death, reserved = _GUARD.unpack(data)
    _need(dumpable == 0 and death == _SIGKILL and reserved == 0)
    encode_guard(pid, parent, address)  # same scalar checks, no proof of OS state
    return pid, parent, address


def encode_close() -> bytes:
    return _packet(Kind.CLOSE, b"")
