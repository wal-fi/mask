"""Pure bounded result validation, not a worker or operational transport.

D-113: correlate a complete private frame and validate its raw PGWire T/D/C
body before exposing read-only chunks. No row objects, I/O, SQL or callbacks
other than a trusted monotonic clock. The caller must reserve receive/copy,
TLS/native and retained-owner costs BEFORE reading; this is not an OS quota.
"""

from __future__ import annotations

import codecs
import math
import struct
import time
from collections.abc import Callable, Generator
from contextlib import suppress
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, NoReturn, TypeGuard

_MIB: Final = 1024 * 1024
_MAX_FRAME: Final = 16 * _MIB
_MAX_CELL: Final = _MIB
_MAX_COLUMNS: Final = 1664
_MAX_NAME: Final = 256
_MAX_ROWS: Final = (1 << 31) - 1
_MAX_EPOCH: Final = (1 << 63) - 1
_TEXT_BLOCK: Final = 4096
_WORK_CHECK: Final = 256
_MAX_CHUNK: Final = 64 * 1024
_IDENTITY_BYTES: Final = 16
_INTEGER_TEXT_BYTES: Final = 20
_DECIMAL_BASE: Final = 10
_MAX_DIGIT: Final = 9
_NAME_OID: Final = 19
_NAME_VALUE_BYTES: Final = 63
_ASCII_LIMIT: Final = 128
_HEADER: Final = struct.Struct("!4sBBH16s16sQQQIII")
RESULT_HEADER_BYTES: Final = _HEADER.size
_U16: Final = struct.Struct("!H")
_U32: Final = struct.Struct("!I")
_I32: Final = struct.Struct("!i")
_COLUMN: Final = struct.Struct("!IhIhih")
_UTF8: Final = codecs.getincrementaldecoder("utf-8")
_TYPE_SIZES: Final = {16: 1, 21: 2, 23: 4, 20: 8, 19: 64, 25: -1, 1042: -1, 1043: -1}
_INTEGER_BITS: Final = {21: 16, 23: 32, 20: 64}
_TEXT_TYPES: Final = frozenset({19, 25, 1042, 1043})


class ResultErrorCategory(StrEnum):
    PROTOCOL = "RESULT_PROTOCOL_ERROR"
    LIMIT = "RESULT_LIMIT_EXCEEDED"
    IDENTITY = "RESULT_IDENTITY_MISMATCH"
    DEADLINE = "RESULT_DEADLINE_EXCEEDED"


class ResultFrameError(Exception):
    """Fixed scalar category only; never attach input, offset or native errors."""

    def __init__(self, category: ResultErrorCategory, *, memory_exhausted: bool = False) -> None:
        if type(category) is not ResultErrorCategory:
            category = ResultErrorCategory.PROTOCOL
        self.category = category
        self.memory_exhausted = memory_exhausted is True
        super().__init__(category.value)


def _fail(
    category: ResultErrorCategory = ResultErrorCategory.PROTOCOL, *, memory_exhausted: bool = False
) -> NoReturn:
    raise ResultFrameError(category, memory_exhausted=memory_exhausted) from None


def _positive(value: object, maximum: int, minimum: int = 1) -> bool:
    return type(value) is int and minimum <= value <= maximum


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class ResultIdentity:
    session_id: bytes
    datasource_id: bytes
    generation: int
    record_revision: int
    job_id: int

    def __post_init__(self) -> None:
        if (
            type(self.session_id) is not bytes
            or len(self.session_id) != _IDENTITY_BYTES
            or type(self.datasource_id) is not bytes
            or len(self.datasource_id) != _IDENTITY_BYTES
            or not all(
                _positive(value, _MAX_EPOCH)
                for value in (
                    self.generation,
                    self.record_revision,
                    self.job_id,
                )
            )
        ):
            _fail(ResultErrorCategory.IDENTITY)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultLimits:
    max_rows: int
    max_frame_bytes: int = _MAX_FRAME
    max_cell_bytes: int = _MAX_CELL
    max_columns: int = _MAX_COLUMNS
    max_name_bytes: int = _MAX_NAME

    def __post_init__(self) -> None:
        if not (
            _positive(self.max_rows, _MAX_ROWS)
            and _positive(self.max_frame_bytes, _MAX_FRAME, _HEADER.size)
            and _positive(self.max_cell_bytes, _MAX_CELL)
            and _positive(self.max_columns, _MAX_COLUMNS)
            and _positive(self.max_name_bytes, _MAX_NAME)
        ):
            _fail(ResultErrorCategory.LIMIT)


def _finite(value: object, *, positive: bool = False) -> TypeGuard[int | float]:
    if type(value) is int:
        return (1 if positive else 0) <= value <= _MAX_EPOCH
    if type(value) is float:
        return math.isfinite(value) and (value > 0 if positive else value >= 0)
    return False


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultDeadline:
    expires_at: float
    clock: Callable[[], float] = field(default=time.monotonic, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not _finite(self.expires_at, positive=True) or not callable(self.clock):
            _fail(ResultErrorCategory.DEADLINE)

    def check(self) -> None:
        if self.remaining() <= 0:
            _fail(ResultErrorCategory.DEADLINE)

    def remaining(self) -> float:
        """Same absolute deadline for I/O and validation; invalid clocks fail closed."""
        value: object = None
        with suppress(Exception):  # discard collaborator failure; never log its contents
            value = self.clock()
        if not _finite(value) or value >= self.expires_at:
            return 0.0
        return float(self.expires_at - value)


@dataclass(frozen=True, slots=True)
class ResultHeader:
    frame_bytes: int
    columns: int
    rows: int
    truncated: bool


def inspect_result_header(
    header: bytes, *, expected: ResultIdentity, limits: ResultLimits
) -> ResultHeader:
    """Validate only the fixed header BEFORE the receiver allocates its body."""
    if type(header) is not bytes or len(header) != _HEADER.size:
        _fail()
    if type(expected) is not ResultIdentity or type(limits) is not ResultLimits:
        _fail()
    (
        magic,
        version,
        flags,
        reserved,
        session,
        datasource,
        generation,
        revision,
        job,
        columns,
        rows,
        body,
    ) = _HEADER.unpack(header)
    if magic != b"MGWR" or version != 1 or flags not in (0, 1) or reserved != 0:
        _fail()
    if (session, datasource, generation, revision, job) != (
        expected.session_id,
        expected.datasource_id,
        expected.generation,
        expected.record_revision,
        expected.job_id,
    ):
        _fail(ResultErrorCategory.IDENTITY)
    if not 1 <= columns <= limits.max_columns or rows > limits.max_rows:
        _fail(ResultErrorCategory.LIMIT)
    if flags == 1 and rows != limits.max_rows:
        _fail()
    total = _HEADER.size + body
    if total > limits.max_frame_bytes:
        _fail(ResultErrorCategory.LIMIT)
    # Empty names and NULL cells still need all structural fields. No body read.
    minimum = 7 + 19 * columns + rows * (7 + 4 * columns) + 5 + len(f"SELECT {rows}\0")
    if body < minimum:
        _fail()
    return ResultHeader(total, columns, rows, flags == 1)


class ValidatedResult:
    """Immutable owner; public API contains counts and body chunks, not data repr.

    The internal constructor is a code contract, not a sandbox against hostile
    Python/reflection in this process. Chunks retain the immutable frame owner.
    """

    __slots__ = ("_columns", "_rows", "_truncated", "_wire")
    _columns: int
    _rows: int
    _truncated: bool
    _wire: bytes

    def __new__(cls) -> ValidatedResult:
        raise TypeError("validated result requires successful validation")

    def __setattr__(self, name: str, value: object) -> NoReturn:
        raise AttributeError("immutable validated result")

    def __delattr__(self, name: str) -> NoReturn:
        raise AttributeError("immutable validated result")

    @property
    def columns(self) -> int:
        return self._columns

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def truncated(self) -> bool:
        return self._truncated

    def __repr__(self) -> str:
        return (
            f"ValidatedResult(columns={self.columns}, rows={self.rows}, truncated={self.truncated})"
        )

    def iter_chunks(
        self,
        *,
        deadline: ResultDeadline,
        chunk_bytes: int = _MAX_CHUNK,
    ) -> Generator[memoryview, None, None]:
        if type(deadline) is not ResultDeadline or not _positive(chunk_bytes, _MAX_CHUNK):
            _fail(ResultErrorCategory.LIMIT)
        try:
            view = memoryview(self._wire)
            for offset in range(_HEADER.size, len(self._wire), chunk_bytes):
                deadline.check()
                yield view[offset : min(offset + chunk_bytes, len(self._wire))]
            deadline.check()
            return
        except MemoryError:
            pass
        _fail(ResultErrorCategory.LIMIT, memory_exhausted=True)


def _result(raw: bytes, columns: int, rows: int, truncated: bool) -> ValidatedResult:
    result = object.__new__(ValidatedResult)
    object.__setattr__(result, "_wire", raw)
    object.__setattr__(result, "_columns", columns)
    object.__setattr__(result, "_rows", rows)
    object.__setattr__(result, "_truncated", truncated)
    return result


def _decode_block(decoder: codecs.IncrementalDecoder, view: memoryview, *, final: bool) -> bool:
    """No UnicodeDecodeError (which holds bytes) escapes or becomes a context."""
    try:
        decoder.decode(view, final=final)
    except UnicodeDecodeError:
        return False
    return True


def _short_utf8(piece: bytes) -> bool:
    """Only a bounded <=4KiB block; never decode a proportional whole value."""
    try:
        piece.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return False
    return True


class _Parser:
    def __init__(self, raw: bytes, limits: ResultLimits, deadline: ResultDeadline) -> None:
        self.raw = raw
        self.view = memoryview(raw)
        self.limits = limits
        self.deadline = deadline
        self.offset = _HEADER.size
        self.columns = 0
        self.rows = 0
        self.work = 0
        self.oids = bytearray(_MAX_COLUMNS * _U32.size)  # fixed, independent of declared dimensions

    def tick(self) -> None:
        self.work += 1
        if self.work >= _WORK_CHECK:
            self.deadline.check()
            self.work = 0

    def message(self, tag: int, minimum: int) -> int:
        self.deadline.check()
        if self.offset + 5 > len(self.raw) or self.raw[self.offset] != tag:
            _fail()
        length = int(_U32.unpack_from(self.raw, self.offset + 1)[0])
        end = self.offset + 1 + length
        if length < minimum or end > len(self.raw):
            _fail()
        self.offset += 5
        return end

    def exact_end(self, end: int) -> None:
        if self.offset != end:
            _fail()

    def text(self, start: int, end: int) -> None:
        if start == end:
            return
        if end - start == 1:
            if not 0 < self.raw[start] < _ASCII_LIMIT:
                _fail()
            return  # per-cell tick/message checks already bound cooperative work
        if end - start <= _TEXT_BLOCK:
            piece = self.raw[start:end]
            if b"\0" in piece or (not piece.isascii() and not _short_utf8(piece)):
                _fail()
            return  # fixed block, not a frame-sized copy
        decoder = _UTF8(errors="strict")
        for offset in range(start, end, _TEXT_BLOCK):
            self.deadline.check()
            stop = min(offset + _TEXT_BLOCK, end)
            if self.raw.find(b"\0", offset, stop) != -1 or not _decode_block(
                decoder,
                self.view[offset:stop],
                final=stop == end,
            ):
                _fail()

    def description(self) -> None:
        end = self.message(ord("T"), 6 + 19 * self.columns)
        if _U16.unpack_from(self.raw, self.offset)[0] != self.columns:
            _fail()
        self.offset += 2
        for index in range(self.columns):
            self.tick()
            stop = min(end, self.offset + self.limits.max_name_bytes + 1)
            name_end = self.raw.find(b"\0", self.offset, stop)
            if name_end == -1:
                _fail(ResultErrorCategory.LIMIT)
            self.text(self.offset, name_end)
            self.offset = name_end + 1
            if self.offset + _COLUMN.size > end:
                _fail()
            table, attribute, oid, size, modifier, fmt = _COLUMN.unpack_from(self.raw, self.offset)
            if (
                table != 0
                or attribute != 0
                or oid not in _TYPE_SIZES
                or size != _TYPE_SIZES[oid]
                or modifier != -1
                or fmt != 0
            ):
                _fail()
            _U32.pack_into(self.oids, index * _U32.size, oid)
            self.offset += _COLUMN.size
        self.exact_end(end)

    def integer(self, start: int, end: int, oid: int) -> None:
        length = end - start
        if not 1 <= length <= _INTEGER_TEXT_BYTES:
            _fail()
        negative = self.raw[start] == ord("-")
        cursor = start + int(negative)
        if cursor == end or (self.raw[cursor] == ord("0") and (negative or cursor + 1 != end)):
            _fail()
        bound = (1 << (_INTEGER_BITS[oid] - 1)) - int(not negative)
        value = 0
        for position in range(cursor, end):
            digit = self.raw[position] - ord("0")
            if not 0 <= digit <= _MAX_DIGIT or value > (bound - digit) // _DECIMAL_BASE:
                _fail()
            value = value * _DECIMAL_BASE + digit

    def value(self, start: int, end: int, oid: int) -> None:
        if oid in _TEXT_TYPES:
            if oid == _NAME_OID and end - start > _NAME_VALUE_BYTES:
                _fail(ResultErrorCategory.LIMIT)
            self.text(start, end)
        elif oid in _INTEGER_BITS:
            self.integer(start, end, oid)
        elif end - start != 1 or self.raw[start] not in (ord("t"), ord("f")):
            _fail()

    def data_rows(self, command_size: int) -> None:
        if self.rows * (7 + 4 * self.columns) + command_size > len(self.raw) - self.offset:
            _fail()
        for _ in range(self.rows):
            end = self.message(ord("D"), 6 + 4 * self.columns)
            if _U16.unpack_from(self.raw, self.offset)[0] != self.columns:
                _fail()
            self.offset += 2
            for index in range(self.columns):
                self.tick()
                if self.offset + _I32.size > end:
                    _fail()
                length = _I32.unpack_from(self.raw, self.offset)[0]
                self.offset += _I32.size
                if length == -1:
                    continue
                if length < 0 or self.offset + length > end:
                    _fail()
                if length > self.limits.max_cell_bytes:
                    _fail(ResultErrorCategory.LIMIT)
                oid = _U32.unpack_from(self.oids, index * _U32.size)[0]
                self.value(self.offset, self.offset + length, oid)
                self.offset += length
            self.exact_end(end)

    def run(self, header: ResultHeader) -> ValidatedResult:
        self.columns, self.rows = header.columns, header.rows
        self.description()
        command = b"SELECT " + str(self.rows).encode("ascii") + b"\0"  # at most 18 bytes
        self.data_rows(5 + len(command))
        end = self.message(ord("C"), 4 + len(command))
        if end - self.offset != len(command) or self.raw[self.offset : end] != command:
            _fail()
        self.offset = end
        self.exact_end(len(self.raw))
        self.deadline.check()
        return _result(self.raw, self.columns, self.rows, header.truncated)


def validate_result(
    raw: bytes,
    *,
    expected: ResultIdentity,
    limits: ResultLimits,
    deadline: ResultDeadline,
) -> ValidatedResult:
    """Validate completely before returning any output. No operational callers.

    Byte quotas are checked here AFTER a complete immutable frame exists;
    the future receiver must enforce its declared limit before allocation.
    """
    if type(raw) is not bytes or type(expected) is not ResultIdentity:
        _fail()
    if type(limits) is not ResultLimits or type(deadline) is not ResultDeadline:
        _fail(ResultErrorCategory.LIMIT)
    if not _HEADER.size <= len(raw) <= limits.max_frame_bytes:
        _fail(ResultErrorCategory.LIMIT)
    deadline.check()
    try:
        header = inspect_result_header(raw[: _HEADER.size], expected=expected, limits=limits)
        if header.frame_bytes != len(raw):
            _fail()
        return _Parser(raw, limits, deadline).run(header)
    except MemoryError:
        pass
    _fail(ResultErrorCategory.LIMIT, memory_exhausted=True)
