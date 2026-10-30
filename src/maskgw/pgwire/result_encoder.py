"""D-115: encode ONLY already-masked typed results, for the future worker.

No I/O or operational caller. Preflight, exact allocation, bounded UTF-8 writes,
immutable copy, then independent D-113 validation. 2F does not bound materialized
rows, libpq, masking or OS/native memory; those remain the worker's B-2 gate.
"""

from __future__ import annotations

import struct
import traceback
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NoReturn

from maskgw.db.result import (
    WIRE_TYPE_SIZES,
    DatabaseResultIntegrityError,
    MaskedResult,
    TypedMaskedResult,
)
from maskgw.pgwire.result_frame import (
    ResultDeadline,
    ResultErrorCategory,
    ResultFrameError,
    ResultIdentity,
    ResultLimits,
    validate_result,
)

_HEADER: Final = struct.Struct("!4sBBH16s16sQQQIII")
_U16: Final = struct.Struct("!H")
_U32: Final = struct.Struct("!I")
_I32: Final = struct.Struct("!i")
_COLUMN: Final = struct.Struct("!IhIhih")
_BLOCK_CHARS: Final = 4096
_INTEGER_BITS: Final = {21: 16, 23: 32, 20: 64}
_TEXT: Final = frozenset({19, 25, 1042, 1043})
_NAME_OID: Final = 19
_NAME_MAX: Final = 63
_BOOL_OID: Final = 16
_WORK_CHECK: Final = 256


class EncodeFailure(StrEnum):
    TYPE = "RESULT_ENCODE_TYPE"
    LIMIT = "RESULT_ENCODE_LIMIT"
    MEMORY = "RESULT_ENCODE_MEMORY"
    DEADLINE = "RESULT_ENCODE_DEADLINE"
    PROTOCOL = "RESULT_ENCODE_PROTOCOL"


class EncodeError(Exception):
    def __init__(self, category: EncodeFailure) -> None:
        self.category = category if type(category) is EncodeFailure else EncodeFailure.PROTOCOL
        super().__init__(self.category.value)

    @property
    def fatal(self) -> bool:
        return self.category in (
            EncodeFailure.MEMORY,
            EncodeFailure.PROTOCOL,
            EncodeFailure.DEADLINE,
        )


def _fail(category: EncodeFailure) -> NoReturn:
    raise EncodeError(category) from None


def _utf8(text: str) -> bytes:
    if text.isascii():
        return text.encode("ascii")
    encoded = None
    with suppress(UnicodeEncodeError):  # never attach .object (possibly a data value)
        encoded = text.encode("utf-8", errors="strict")
    if encoded is None:
        _fail(EncodeFailure.TYPE)
    return encoded


@dataclass(frozen=True, slots=True)
class _ColumnPlan:
    name: str
    oid: int
    name_bytes: int


class _Writer:
    def __init__(self, size: int) -> None:
        self.buffer = bytearray(size)
        self.offset = _HEADER.size

    def put(self, value: bytes) -> None:
        end = self.offset + len(value)
        if end > len(self.buffer):
            _fail(EncodeFailure.PROTOCOL)
        self.buffer[self.offset : end] = value  # exact-size replacement, never growth
        self.offset = end

    def number(self, fmt: struct.Struct, value: int) -> None:
        if self.offset + fmt.size > len(self.buffer):
            _fail(EncodeFailure.PROTOCOL)
        fmt.pack_into(self.buffer, self.offset, value)
        self.offset += fmt.size

    def start(self, tag: bytes) -> int:
        self.put(tag)
        prefix = self.offset
        self.number(_U32, 0)
        return prefix

    def end(self, prefix: int) -> None:
        _U32.pack_into(self.buffer, prefix, self.offset - prefix)


class _Encoder:
    def __init__(
        self,
        result: TypedMaskedResult,
        identity: ResultIdentity,
        limits: ResultLimits,
        deadline: ResultDeadline,
    ) -> None:
        deadline.check()
        item = result.masked
        if (
            type(item) is not MaskedResult
            or type(item.rows) is not tuple
            or type(item.columns) is not tuple
        ):
            _fail(EncodeFailure.PROTOCOL)
        if len(item.rows) > limits.max_rows or len(item.columns) > limits.max_columns:
            _fail(EncodeFailure.LIMIT)
        # Revalidate closed, immutable shape; never rely on construction alone.
        TypedMaskedResult.__post_init__(result)
        deadline.check()
        self.item = result.masked
        self.identity, self.limits, self.deadline = identity, limits, deadline
        self.work = 0
        self.columns: tuple[_ColumnPlan, ...] = tuple(
            _ColumnPlan(
                col.output_name, oid, self.text_size(col.output_name, limits.max_name_bytes)
            )
            for col, oid in zip(self.item.columns, result.type_oids, strict=True)
        )

    def tick(self) -> None:
        self.work += 1
        if self.work >= _WORK_CHECK:
            self.deadline.check()
            self.work = 0

    def text_size(
        self, value: str, maximum: int, *, over: EncodeFailure = EncodeFailure.LIMIT
    ) -> int:
        self.tick()
        if len(value) > maximum:  # UTF-8 cannot be shorter than the codepoint count
            _fail(over)
        if len(value) <= _BLOCK_CHARS and value.isascii():
            if "\0" in value:
                _fail(EncodeFailure.TYPE)
            return len(value)
        size = 0
        for start in range(0, len(value), _BLOCK_CHARS):
            if start or len(value) > _BLOCK_CHARS:
                self.deadline.check()
            block = value[start : start + _BLOCK_CHARS]
            if "\0" in block:
                _fail(EncodeFailure.TYPE)
            size += len(_utf8(block))
            if size > maximum:
                _fail(over)
        return size

    def cell_size(self, value: object, oid: int) -> int:
        self.tick()
        if value is None:
            return -1
        if oid in _TEXT:
            if type(value) is not str:
                _fail(EncodeFailure.TYPE)
            if oid == _NAME_OID:
                size = self.text_size(value, _NAME_MAX, over=EncodeFailure.TYPE)
                if size > self.limits.max_cell_bytes:
                    _fail(EncodeFailure.LIMIT)
                return size
            return self.text_size(value, self.limits.max_cell_bytes)
        if oid in _INTEGER_BITS:
            bits = _INTEGER_BITS[oid]
            if type(value) is not int or not -(1 << (bits - 1)) <= value < (1 << (bits - 1)):
                _fail(EncodeFailure.TYPE)
            size = len(str(value))  # bounded BEFORE conversion, at most 20 ASCII bytes
        elif oid == _BOOL_OID and type(value) is bool:
            size = 1
        else:
            _fail(EncodeFailure.TYPE)
        if size > self.limits.max_cell_bytes:
            _fail(EncodeFailure.LIMIT)
        return size

    def preflight(self) -> int:
        self.deadline.check()
        rows = self.item.row_count
        if len(self.columns) > self.limits.max_columns or rows > self.limits.max_rows:
            _fail(EncodeFailure.LIMIT)
        if self.item.truncated and rows != self.limits.max_rows:
            _fail(EncodeFailure.PROTOCOL)
        total = _HEADER.size + 7 + sum(19 + col.name_bytes for col in self.columns)
        total += 5 + len(f"SELECT {rows}\0")
        if total > self.limits.max_frame_bytes:
            _fail(EncodeFailure.LIMIT)
        for row in self.item.rows:
            total += 7
            for value, col in zip(row, self.columns, strict=True):
                total += 4 + max(0, self.cell_size(value, col.oid))
                if total > self.limits.max_frame_bytes:
                    _fail(EncodeFailure.LIMIT)
        return total

    def write_text(self, writer: _Writer, value: str) -> None:
        self.tick()
        if len(value) <= _BLOCK_CHARS and value.isascii():
            writer.put(value.encode("ascii"))
            return
        for start in range(0, len(value), _BLOCK_CHARS):
            if start or len(value) > _BLOCK_CHARS:
                self.deadline.check()
            writer.put(_utf8(value[start : start + _BLOCK_CHARS]))

    def write_cell(self, writer: _Writer, value: object, oid: int) -> None:
        self.tick()
        if oid in _TEXT and type(value) is str and len(value) <= _BLOCK_CHARS and value.isascii():
            data = value.encode("ascii")  # <=4KiB, preflight verified type/NUL/limits
            end = writer.offset + _I32.size + len(data)
            if end > len(writer.buffer):
                _fail(EncodeFailure.PROTOCOL)
            _I32.pack_into(writer.buffer, writer.offset, len(data))
            writer.buffer[writer.offset + _I32.size : end] = data
            writer.offset = end
            return
        prefix = writer.offset
        writer.number(_I32, -1 if value is None else 0)
        if value is None:
            return
        if oid in _TEXT:
            assert type(value) is str  # noqa: S101 - exact immutable scalar validated in preflight
            self.write_text(writer, value)
        elif oid in _INTEGER_BITS:
            if type(value) is not int:
                _fail(EncodeFailure.PROTOCOL)
            writer.put(str(value).encode("ascii"))
        else:
            writer.put(b"t" if value is True else b"f")
        _I32.pack_into(writer.buffer, prefix, writer.offset - prefix - _I32.size)

    def run(self) -> bytes:
        total = self.preflight()
        writer = _Writer(total)
        prefix = writer.start(b"T")
        writer.number(_U16, len(self.columns))
        for col in self.columns:
            self.deadline.check()
            self.write_text(writer, col.name)
            writer.put(b"\0")
            writer.put(_COLUMN.pack(0, 0, col.oid, WIRE_TYPE_SIZES[col.oid], -1, 0))
        writer.end(prefix)
        for row in self.item.rows:
            prefix = writer.start(b"D")
            writer.number(_U16, len(self.columns))
            for value, col in zip(row, self.columns, strict=True):
                self.write_cell(writer, value, col.oid)
            writer.end(prefix)
        prefix = writer.start(b"C")
        writer.put(f"SELECT {self.item.row_count}\0".encode("ascii"))
        writer.end(prefix)
        if writer.offset != total:
            _fail(EncodeFailure.PROTOCOL)
        identity = self.identity
        _HEADER.pack_into(
            writer.buffer,
            0,
            b"MGWR",
            1,
            int(self.item.truncated),
            0,
            identity.session_id,
            identity.datasource_id,
            identity.generation,
            identity.record_revision,
            identity.job_id,
            len(self.columns),
            self.item.row_count,
            total - _HEADER.size,
        )
        wire = bytes(writer.buffer)
        del writer  # proportional mutable allocation MUST be gone before validation
        validate_result(wire, expected=identity, limits=self.limits, deadline=self.deadline)
        return wire


def encode_result(
    result: TypedMaskedResult,
    *,
    identity: ResultIdentity,
    limits: ResultLimits,
    deadline: ResultDeadline,
) -> bytes:
    """Atomic complete private frame; never returns partial output or raw rows."""
    if type(result) is not TypedMaskedResult or type(identity) is not ResultIdentity:
        _fail(EncodeFailure.PROTOCOL)
    if type(limits) is not ResultLimits or type(deadline) is not ResultDeadline:
        _fail(EncodeFailure.PROTOCOL)
    category = EncodeFailure.PROTOCOL
    try:
        return _Encoder(result, identity, limits, deadline).run()
    except Exception as error:
        if isinstance(error, EncodeError):
            category = error.category
        elif isinstance(error, MemoryError) or (
            isinstance(error, ResultFrameError) and error.memory_exhausted
        ):
            category = EncodeFailure.MEMORY
        elif isinstance(error, ResultFrameError) and error.category is ResultErrorCategory.DEADLINE:
            category = EncodeFailure.DEADLINE
        elif isinstance(error, DatabaseResultIntegrityError):
            category = EncodeFailure.PROTOCOL
        try:
            traceback.clear_frames(error.__traceback__)
        except Exception:
            category = EncodeFailure.PROTOCOL
    del result
    _fail(category)
