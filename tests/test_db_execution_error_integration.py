"""Real PG16 execution health on the explicitly supplied disposable test DSN."""

from __future__ import annotations

from dataclasses import replace

import psycopg
import pytest

from maskgw.config import load_config_text
from maskgw.config.gateway import DatabaseSettings
from maskgw.db.execution_error import ExecutionFailure, TypedExecutionError, TypedExecutionTimeout
from maskgw.db.postgres import PostgresAdapter
from maskgw.errors import DatabaseError, QueryTimeout
from maskgw.masking.engine import MaskingEngine
from maskgw.sql.policy import DEFAULT_SQL_POLICY

pytestmark = pytest.mark.integration


@pytest.fixture
def item(dsn):
    adapter = PostgresAdapter(
        dsn,
        MaskingEngine(load_config_text("{}")),
        settings=DatabaseSettings(statement_timeout_ms=100, max_rows=10),
        sql_policy=replace(DEFAULT_SQL_POLICY, allowed_pg_functions=frozenset({"pg_sleep"})),
    )
    adapter.connect()
    try:
        yield adapter
    finally:
        adapter.close()


def test_real_idle_success_has_exact_status_and_positive_health(item):
    assert item._connection.info.status is psycopg.pq.ConnStatus.OK
    assert item._connection.info.transaction_status is psycopg.pq.TransactionStatus.IDLE
    assert item._typed_connection_healthy() is True
    assert item._execute_typed_validated("SELECT 1").masked.rows == ((1,),)
    assert item._typed_connection_healthy() is True
    assert item._connection.execute("SHOW default_transaction_read_only").fetchone() == ("on",)


def test_real_data_error_is_candidate_only_after_healthy_settle_same_connection(item):
    pid = item._connection.info.backend_pid
    with pytest.raises(TypedExecutionError) as caught:
        item._execute_typed_validated("SELECT 'CANARY_SERVER_VALUE'::integer")
    assert caught.value.category is ExecutionFailure.QUERY
    assert caught.value.continuation_candidate
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert "CANARY" not in str(caught.value)
    assert item._typed_connection_healthy() is True
    assert item._execute_typed_validated("SELECT 2").masked.rows == ((2,),)
    assert item._connection.info.backend_pid == pid


def test_real_cardinality_error_is_query_and_connection_remains_healthy(item):
    with pytest.raises(TypedExecutionError) as caught:
        item._execute_typed_validated("SELECT (SELECT x FROM (VALUES (1), (2)) AS t(x))")
    assert caught.value.category is ExecutionFailure.QUERY
    assert caught.value.continuation_candidate
    assert item._typed_connection_healthy() is True
    assert item._execute_typed_validated("SELECT 3").masked.rows == ((3,),)


def test_real_server_timeout_keeps_querytimeout_type_and_healthy_connection(item):
    pid = item._connection.info.backend_pid
    with pytest.raises(TypedExecutionTimeout) as caught:
        item._execute_typed_validated("SELECT pg_sleep(1)")
    assert isinstance(caught.value, QueryTimeout)
    assert caught.value.category is ExecutionFailure.TIMEOUT
    assert caught.value.continuation_candidate
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert item._typed_connection_healthy() is True
    assert item._execute_typed_validated("SELECT 4").masked.rows == ((4,),)
    assert item._connection.info.backend_pid == pid


def test_real_terminated_owned_backend_is_never_healthy_or_recoverable(item, dsn):
    original = item._connection
    pid = item._connection.info.backend_pid
    with psycopg.connect(dsn, autocommit=True) as admin:
        assert admin.execute("SELECT pg_terminate_backend(%s)", (pid,)).fetchone() == (True,)
    with pytest.raises(DatabaseError) as caught:
        item._execute_typed_validated("SELECT 1")
    # A pre-cursor closed connection may fail in _require_connection (generic,
    # therefore fatal); native 57P01 or no state are also both fatal categories.
    if isinstance(caught.value, TypedExecutionError):
        assert not caught.value.continuation_candidate
        assert caught.value.category in (ExecutionFailure.CONNECTION, ExecutionFailure.INTERNAL)
    else:
        assert type(caught.value) is DatabaseError
    assert item._typed_connection_healthy() is False
    assert item._connection is original or item._connection is None
