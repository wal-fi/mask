"""Typed failures retain closed intent; legacy errors and SQL ingress stay unchanged."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import psycopg
import pytest

import maskgw.db.postgres as postgres_module
from maskgw.db.execution_error import (
    ExecutionFailure,
    TypedExecutionError,
    TypedExecutionTimeout,
    classify_typed_error,
)
from maskgw.errors import DatabaseError, QueryTimeout
from tests.test_db_typed_result import TypedColumn, adapter


def native(state: object) -> psycopg.Error:
    error_type = type("SyntheticPsycopgError", (psycopg.Error,), {"sqlstate": state})
    return cast(psycopg.Error, error_type("CANARY_PASSWORD_DSN_OR_ROW"))


@pytest.mark.parametrize(
    "state,category,candidate",
    [
        ("0A000", ExecutionFailure.QUERY, True),
        ("21000", ExecutionFailure.QUERY, True),
        ("22012", ExecutionFailure.QUERY, True),
        ("23505", ExecutionFailure.QUERY, True),
        ("25006", ExecutionFailure.QUERY, True),
        ("40001", ExecutionFailure.QUERY, True),
        ("42501", ExecutionFailure.QUERY, True),
        ("54001", ExecutionFailure.QUERY, True),
        ("57014", ExecutionFailure.TIMEOUT, True),
        ("53000", ExecutionFailure.RESOURCE, False),
        ("53100", ExecutionFailure.RESOURCE, False),
        ("53200", ExecutionFailure.RESOURCE, False),
        ("08006", ExecutionFailure.CONNECTION, False),
        ("08P01", ExecutionFailure.CONNECTION, False),
        (None, ExecutionFailure.CONNECTION, False),
        ("25P02", ExecutionFailure.INTERNAL, False),
        ("25P03", ExecutionFailure.INTERNAL, False),
        ("25000", ExecutionFailure.INTERNAL, False),
        ("57P01", ExecutionFailure.INTERNAL, False),
        ("57P02", ExecutionFailure.INTERNAL, False),
        ("57P03", ExecutionFailure.INTERNAL, False),
        ("57P04", ExecutionFailure.INTERNAL, False),
        ("57P05", ExecutionFailure.INTERNAL, False),
        ("58000", ExecutionFailure.INTERNAL, False),
        ("P0001", ExecutionFailure.INTERNAL, False),
        ("XX000", ExecutionFailure.INTERNAL, False),
    ],
)
def test_exact_closed_category_and_continuation_candidate(state, category, candidate):
    original = native(state)
    result = classify_typed_error(original)
    assert isinstance(result, DatabaseError)
    assert result.category is category
    assert result.continuation_candidate is candidate
    assert result.__cause__ is None and result.__context__ is None
    assert result.__traceback__ is None
    assert "CANARY" not in str(result) and "CANARY" not in repr(result)
    assert vars(result) == {"category": category}
    if category is ExecutionFailure.TIMEOUT:
        assert type(result) is TypedExecutionTimeout and isinstance(result, QueryTimeout)
    else:
        assert type(result) is TypedExecutionError


@pytest.mark.parametrize("state", ["", "22", "220120", "2201a", "22 12", "\uff122012", 57014, True])
def test_noncanonical_state_is_fatal_without_parsing_native_text(state):
    result = classify_typed_error(native(state))
    assert result.category is ExecutionFailure.INTERNAL
    assert result.continuation_candidate is False


def test_only_sqlstate_is_read_never_message_repr_or_diag():
    class ForbiddenNative(psycopg.Error):
        sqlstate = "53200"

        def __str__(self) -> str:
            raise AssertionError("native message read")

        def __repr__(self) -> str:
            raise AssertionError("native repr read")

        @property
        def diag(self):
            raise AssertionError("native diagnostic read")

    result = classify_typed_error(ForbiddenNative())
    assert result.category is ExecutionFailure.RESOURCE and not result.continuation_candidate


def test_getter_failure_is_closed_internal_without_native_chain():
    class BrokenNative(psycopg.Error):
        def __init__(self) -> None:
            Exception.__init__(self)

        def __getattribute__(self, name: str) -> Any:
            if name == "sqlstate":
                raise RuntimeError("CANARY_SQLSTATE_GETTER")
            return super().__getattribute__(name)

    result = classify_typed_error(BrokenNative())
    assert result.category is ExecutionFailure.INTERNAL
    assert result.__context__ is None
    assert "CANARY" not in str(result)


@pytest.mark.parametrize("category", [None, True, "QUERY", ExecutionFailure.TIMEOUT])
def test_invalid_generic_constructor_cannot_create_recoverable_timeout(category):
    result = TypedExecutionError(category)
    assert result.category is ExecutionFailure.INTERNAL
    assert not result.continuation_candidate


@pytest.mark.parametrize("state", ["22012", "53200", "57014", None])
def test_typed_run_raises_after_settle_with_no_original_reference(state):
    item, cursor, connection = adapter([TypedColumn("x", 23)], [(1,)])
    original = native(state)

    def fail(*_args, **_kwargs):
        raise original

    cursor.execute = fail
    with pytest.raises(DatabaseError) as caught:
        item._execute_typed_validated("SELECT 1")
    assert type(caught.value) in (TypedExecutionError, TypedExecutionTimeout)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert "CANARY" not in repr(caught.value)
    assert connection.rollbacks == 1 and not connection.commits


def test_legacy_run_keeps_original_sanitizer_and_never_calls_typed_classifier(monkeypatch):
    item, cursor, connection = adapter([TypedColumn("x", 23)], [(1,)])

    def forbidden(*_args, **_kwargs):
        raise AssertionError("typed classifier reached by legacy")

    def fail(*_args, **_kwargs):
        raise native("53200")

    monkeypatch.setattr(postgres_module, "classify_typed_error", forbidden)
    cursor.execute = fail
    with pytest.raises(DatabaseError) as caught:
        item.execute_validated("SELECT 1")
    assert type(caught.value) is DatabaseError
    assert str(caught.value) == "recursos insuficientes no banco de dados"
    assert caught.value.__context__ is None and connection.rollbacks == 1


def healthy_connection() -> SimpleNamespace:
    return SimpleNamespace(
        closed=False,
        broken=False,
        info=SimpleNamespace(
            status=psycopg.pq.ConnStatus.OK,
            transaction_status=psycopg.pq.TransactionStatus.IDLE,
        ),
    )


def test_positive_health_is_local_nonmutating_and_not_an_execution():
    item, cursor, original = adapter([TypedColumn("x", 23)], [(1,)])
    connection = healthy_connection()
    item._connection = cast(Any, connection)
    assert item._typed_connection_healthy() is True
    assert item._connection is connection
    assert original.rollbacks == 0 and original.commits == 0
    assert cursor.executed == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("closed", True),
        ("closed", 0),
        ("closed", None),
        ("broken", True),
        ("broken", 0),
        ("broken", "false"),
    ],
)
def test_bad_or_inexact_connection_flags_are_not_healthy(field, value):
    item, _, _ = adapter([TypedColumn("x", 23)], [])
    connection = healthy_connection()
    setattr(connection, field, value)
    item._connection = cast(Any, connection)
    assert item._typed_connection_healthy() is False


@pytest.mark.parametrize(
    "status",
    [
        psycopg.pq.ConnStatus.BAD,
        0,
        None,
        "OK",
    ],
)
def test_health_requires_exact_libpq_connection_status(status):
    item, _, _ = adapter([TypedColumn("x", 23)], [])
    connection = healthy_connection()
    connection.info.status = status
    item._connection = cast(Any, connection)
    assert item._typed_connection_healthy() is False


@pytest.mark.parametrize(
    "status",
    [
        psycopg.pq.TransactionStatus.ACTIVE,
        psycopg.pq.TransactionStatus.INTRANS,
        psycopg.pq.TransactionStatus.INERROR,
        psycopg.pq.TransactionStatus.UNKNOWN,
        0,
        None,
        "IDLE",
    ],
)
def test_health_requires_exact_idle_transaction(status):
    item, _, _ = adapter([TypedColumn("x", 23)], [])
    connection = healthy_connection()
    connection.info.transaction_status = status
    item._connection = cast(Any, connection)
    assert item._typed_connection_healthy() is False


@pytest.mark.parametrize(
    "connection",
    [
        None,
        SimpleNamespace(),
        SimpleNamespace(closed=False),
        SimpleNamespace(closed=False, broken=False, info=SimpleNamespace()),
    ],
)
def test_missing_health_fields_fail_closed(connection):
    item, _, _ = adapter([TypedColumn("x", 23)], [])
    item._connection = cast(Any, connection)
    assert item._typed_connection_healthy() is False


def test_health_getter_failure_is_false_and_does_not_mutate_or_raise():
    class BrokenConnection:
        @property
        def closed(self):
            raise MemoryError("CANARY_HEALTH")

    item, _, _ = adapter([TypedColumn("x", 23)], [])
    connection = BrokenConnection()
    item._connection = cast(Any, connection)
    assert item._typed_connection_healthy() is False
    assert item._connection is connection


def test_candidacy_and_health_are_independent_after_real_settle_path():
    item, cursor, connection = adapter([TypedColumn("x", 23)], [])
    connection.broken = False
    connection.info.status = psycopg.pq.ConnStatus.OK
    assert item._typed_connection_healthy() is False  # INTRANS before settle.

    def fail(*_args, **_kwargs):
        raise native("53200")

    cursor.execute = fail
    with pytest.raises(TypedExecutionError) as caught:
        item._execute_typed_validated("SELECT 1")
    assert item._typed_connection_healthy() is True  # rollback settled locally.
    assert caught.value.continuation_candidate is False  # Resource stays fatal.
