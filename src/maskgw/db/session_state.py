"""Private W1 session invariants. No user SQL, I/O, reset or complete DBA audit.

Only the worker may retain these metadata values; never serialize them to the
parent/client/log. Unexpected state is fatal, not repaired with SET/DISCARD.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

SESSION_STATE_SQL: Final = """
SELECT CURRENT_USER, SESSION_USER,
       pg_catalog.current_setting('search_path'),
       pg_catalog.current_schemas(true),
       pg_catalog.pg_my_temp_schema(),
       pg_catalog.current_setting('default_transaction_read_only'),
       pg_catalog.current_setting('transaction_read_only'),
       pg_catalog.current_setting('statement_timeout'),
       pg_catalog.current_setting('client_encoding'),
       pg_catalog.current_setting('DateStyle'),
       pg_catalog.current_setting('TimeZone'),
       pg_catalog.current_setting('default_transaction_isolation'),
       pg_catalog.current_setting('transaction_isolation'),
       pg_catalog.current_setting('row_security'),
       pg_catalog.pg_backend_pid(), pg_catalog.current_database(),
       pg_catalog.current_setting('standard_conforming_strings'),
       (SELECT pg_catalog.count(*) FROM pg_catalog.pg_locks
         WHERE pid OPERATOR(pg_catalog.=) pg_catalog.pg_backend_pid()
           AND locktype OPERATOR(pg_catalog.=) 'advisory'::pg_catalog.text),
       ARRAY(SELECT pg_catalog.pg_listening_channels()),
       pg_catalog.current_setting('IntervalStyle'),
       pg_catalog.current_setting('bytea_output'),
       pg_catalog.current_setting('extra_float_digits'),
       pg_catalog.current_setting('lc_monetary'),
       pg_catalog.current_setting('lc_numeric'),
       pg_catalog.current_setting('xmloption')
"""
_FIELDS: Final = 25
_ARRAYS: Final = frozenset({3, 18})
_NUMBERS: Final = frozenset({4, 14, 17})
_MAX_TEXT_BYTES: Final = 8192
_MAX_TOTAL_BYTES: Final = 65536
_MAX_SCHEMAS: Final = 64
_DEFAULT_READONLY: Final = 5
_READONLY: Final = 6
_ENCODING: Final = 8
_ROW_SECURITY: Final = 13
_BACKEND_PID: Final = 14
_STANDARD_STRINGS: Final = 16
_TEMP_SCHEMA: Final = 4
_ADVISORY_LOCKS: Final = 17
_CHANNELS: Final = 18


class WorkerSessionStateError(Exception):
    def __init__(self) -> None:
        super().__init__("estado da sessao do worker nao comprovado")


def _need(value: bool) -> None:
    if not value:
        raise WorkerSessionStateError()


def _text(value: object) -> int:
    _need(type(value) is str)
    text = cast(str, value)
    _need(len(text) <= _MAX_TEXT_BYTES and "\0" not in text)
    size: int | None = None
    try:
        size = len(text.encode("utf-8", errors="strict"))
    except UnicodeError:
        size = None
    if size is None:
        raise WorkerSessionStateError()
    _need(size <= _MAX_TEXT_BYTES)
    return size


def _normalize(row: object) -> tuple[object, ...]:
    _need(type(row) is tuple and len(row) == _FIELDS)
    values = cast(tuple[object, ...], row)
    normalized: list[object] = []
    total = 0
    for index, value in enumerate(values):
        if index in _ARRAYS:
            _need(type(value) in (list, tuple))
            array = cast(list[object] | tuple[object, ...], value)
            _need(len(array) <= _MAX_SCHEMAS)
            for name in array:
                total += _text(name)
            normalized.append(tuple(array))
        elif index in _NUMBERS:
            _need(type(value) is int)
            normalized.append(value)
        else:
            total += _text(value)
            normalized.append(value)
        _need(total <= _MAX_TOTAL_BYTES)
    _need(values[_TEMP_SCHEMA] == values[_ADVISORY_LOCKS] == 0 and not values[_CHANNELS])
    _need(
        values[_DEFAULT_READONLY]
        == values[_READONLY]
        == values[_ROW_SECURITY]
        == values[_STANDARD_STRINGS]
        == "on"
    )
    _need(values[_ENCODING] == "UTF8")
    backend = values[_BACKEND_PID]
    _need(type(backend) is int and 0 < backend < (1 << 31))
    return tuple(normalized)


@dataclass(frozen=True, slots=True, repr=False, eq=False)
class WorkerSessionState:
    _values: tuple[object, ...]

    def __post_init__(self) -> None:
        normalized: tuple[object, ...] | None = None
        try:
            normalized = _normalize(self._values)
        except MemoryError:
            raise
        except Exception:
            normalized = None
        if normalized is None:
            raise WorkerSessionStateError()
        object.__setattr__(self, "_values", normalized)

    def require_same(self, other: WorkerSessionState) -> None:
        _need(type(other) is type(self) is WorkerSessionState)
        # Revalidation rejects objects altered by bypassing frozen semantics.
        left, right = _normalize(self._values), _normalize(other._values)
        _need(left == right)

    def __repr__(self) -> str:
        return "WorkerSessionState(<private>)"

    def __bool__(self) -> bool:
        raise TypeError("estado da sessao exige comparacao explicita")
