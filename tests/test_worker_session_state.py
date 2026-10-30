"""W1 state record and opt-in adapter probe with fakes; no PostgreSQL here."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from typing import Any, cast

import psycopg
import pytest

from maskgw.db.postgres import PostgresAdapter
from maskgw.db.session_state import SESSION_STATE_SQL, WorkerSessionState, WorkerSessionStateError
from maskgw.errors import InvalidQuery, QueryRejected
from maskgw.masking.engine import MaskingEngine
from maskgw.masking.rules import MaskingPolicy
from maskgw.sql.validator import validate_select


def row() -> tuple[Any, ...]:
    return (
        "PRIVATE_USER",
        "PRIVATE_USER",
        '"$user", public',
        ["pg_catalog", "public"],
        0,
        "on",
        "on",
        "2s",
        "UTF8",
        "ISO, MDY",
        "UTC",
        "read committed",
        "read committed",
        "on",
        123,
        "PRIVATE_DATABASE",
        "on",
        0,
        [],
        "postgres",
        "hex",
        "1",
        "C",
        "C",
        "content",
    )


def test_detached_immutable_state_never_exposes_metadata_in_repr() -> None:
    raw = row()
    state = WorkerSessionState(raw)
    state.require_same(WorkerSessionState(row()))
    raw[3].append("different")
    state.require_same(WorkerSessionState(row()))
    assert "PRIVATE" not in repr(state) and "public" not in repr(state)
    with pytest.raises(FrozenInstanceError):
        setattr(state, "_values", ())  # noqa: B010 - deliberate frozen-record violation
    with pytest.raises(TypeError):
        bool(state)


@pytest.mark.parametrize("index", range(25))
def test_every_observed_state_field_is_invariant(index: int) -> None:
    before = WorkerSessionState(row())
    values = list(row())
    if index in {3, 18}:
        values[index] = [*values[index], "changed"]
    elif type(values[index]) is int:
        values[index] += 1
    else:
        values[index] = "changed"
    with pytest.raises(WorkerSessionStateError):
        before.require_same(WorkerSessionState(tuple(values)))


@pytest.mark.parametrize("bad", [None, (), (None,) * 25, [None] * 25])
def test_closed_row_shape(bad: Any) -> None:
    with pytest.raises(WorkerSessionStateError) as exc:
        WorkerSessionState(bad)
    assert exc.value.__context__ is None


@pytest.mark.parametrize(
    "index,value",
    [
        (3, ["x"] * 65),
        (0, "x" * 8193),
        (0, "\ud800"),
        (0, "a\0b"),
        (4, True),
        (14, True),
        (14, 0),
        (14, 1 << 31),
        (17, False),
        (18, ""),
        (8, "LATIN1"),
        (13, "off"),
        (16, "off"),
    ],
)
def test_bounds_and_unsafe_initial_state_fail_closed(index: int, value: Any) -> None:
    values = list(row())
    values[index] = value
    with pytest.raises(WorkerSessionStateError):
        WorkerSessionState(tuple(values))


def test_total_text_budget_and_multibyte_size() -> None:
    values = list(row())
    for index in (0, 1, 2, 7, 9, 10, 11, 12, 15):
        values[index] = "a" * 8192
    with pytest.raises(WorkerSessionStateError):
        WorkerSessionState(tuple(values))
    values = list(row())
    values[0] = "あ" * 4096
    with pytest.raises(WorkerSessionStateError):
        WorkerSessionState(tuple(values))


def test_hostile_frozen_bypass_is_revalidated_before_comparison() -> None:
    state = WorkerSessionState(row())
    other = WorkerSessionState(row())
    changed = list(row())
    changed[0] = "\ud800"
    object.__setattr__(other, "_values", tuple(changed))
    with pytest.raises(WorkerSessionStateError) as exc:
        state.require_same(other)
    assert exc.value.__context__ is None


class Cursor:
    def __init__(self, rows: list[tuple[Any, ...] | None], failure: str | None = None) -> None:
        self.rows = list(rows)
        self.failure = failure
        self.calls: list[str] = []
        self.closed = False

    def __enter__(self) -> Cursor:
        return self

    def __exit__(self, *_args: object) -> None:
        self.closed = True
        if self.failure == "close":
            raise OSError("PRIVATE_DRIVER_MESSAGE")

    def execute(self, query: str) -> None:
        self.calls.append(query)
        if self.failure == "execute":
            raise OSError("PRIVATE_DRIVER_MESSAGE")
        if self.failure == "memory":
            raise MemoryError()

    def fetchone(self) -> tuple[Any, ...] | None:
        if self.failure == "fetch":
            raise OSError("PRIVATE_DRIVER_MESSAGE")
        return self.rows.pop(0)


def adapter(cursor: Cursor) -> PostgresAdapter:
    value = PostgresAdapter("PRIVATE_CONNINFO", MaskingEngine(MaskingPolicy()))
    info = SimpleNamespace(
        status=psycopg.pq.ConnStatus.OK, transaction_status=psycopg.pq.TransactionStatus.IDLE
    )
    value._connection = cast(
        psycopg.Connection[tuple[Any, ...]],
        SimpleNamespace(closed=False, broken=False, info=info, cursor=lambda: cursor),
    )
    return value


def test_probe_is_opt_in_fixed_metadata_sql_and_no_masking_call() -> None:
    cursor = Cursor([row(), None])
    value = adapter(cursor)
    state = value._worker_session_state()
    state.require_same(WorkerSessionState(row()))
    assert cursor.calls == [SESSION_STATE_SQL] and cursor.closed
    assert "OPERATOR(pg_catalog.=)" in SESSION_STATE_SQL
    assert "pg_catalog.current_schemas(true)" in SESSION_STATE_SQL
    assert "PRIVATE" not in SESSION_STATE_SQL


@pytest.mark.parametrize("failure", ["execute", "fetch", "close"])
def test_probe_errors_are_closed_chainless_and_cursor_closes(failure: str) -> None:
    cursor = Cursor([row(), None], failure=failure)
    value = adapter(cursor)
    with pytest.raises(WorkerSessionStateError) as exc:
        value._worker_session_state()
    assert cursor.closed and exc.value.__cause__ is None and exc.value.__context__ is None
    assert "PRIVATE" not in str(exc.value) + repr(exc.value)


@pytest.mark.parametrize("rows", [[None], [row(), row()]])
def test_probe_requires_exactly_one_row(rows: list[tuple[Any, ...] | None]) -> None:
    cursor = Cursor(rows)
    with pytest.raises(WorkerSessionStateError):
        adapter(cursor)._worker_session_state()
    assert cursor.closed


def test_probe_checks_health_before_and_after(monkeypatch: Any) -> None:
    cursor = Cursor([row(), None])
    value = adapter(cursor)
    monkeypatch.setattr(value, "_typed_connection_healthy", lambda: False)
    with pytest.raises(WorkerSessionStateError):
        value._worker_session_state()
    assert cursor.calls == []
    healthy = iter([True, False])
    monkeypatch.setattr(value, "_typed_connection_healthy", lambda: next(healthy))
    with pytest.raises(WorkerSessionStateError):
        value._worker_session_state()
    assert cursor.closed


def test_probe_memory_exhaustion_remains_fatal_resource_failure() -> None:
    cursor = Cursor([row(), None], failure="memory")
    with pytest.raises(MemoryError):
        adapter(cursor)._worker_session_state()
    assert cursor.closed


@pytest.mark.parametrize(
    "sql",
    [
        "PREPARE c AS SELECT 1",
        "EXECUTE c",
        "DECLARE c CURSOR WITH HOLD FOR SELECT 1",
        "SET search_path TO public",
        "SELECT set_config('search_path', 'public', false)",
    ],
)
def test_existing_validator_refuses_direct_session_mutators(sql: str) -> None:
    with pytest.raises((InvalidQuery, QueryRejected)):
        validate_select(sql)


def test_validator_does_not_claim_to_refuse_every_user_function() -> None:
    # Accepted D-027 risk: a non-pg user function can have unknown effects.
    assert validate_select("SELECT ordinary_user_function()") is not None
