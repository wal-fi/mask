"""Typed metadata opt-in shares the original protected adapter pipeline."""

from __future__ import annotations

from typing import Any, cast

import pytest

import maskgw.db.postgres as postgres_module
from maskgw.config import load_config_text
from maskgw.db.postgres import PostgresAdapter
from maskgw.db.result import (
    DatabaseResultIntegrityError,
    DatabaseResultTypeError,
    TypedMaskedResult,
)
from maskgw.masking.engine import Action, Decision, MaskingEngine
from tests.conftest import INTRANS, FakeColumn, FakeConnection, FakeCursor, FakeResolver


class TypedColumn(FakeColumn):
    def __init__(self, name: str, oid: int) -> None:
        super().__init__(name)
        self.type_code = oid


def adapter(
    description: list[Any], rows: list[tuple[Any, ...]], config: str = "{}"
) -> tuple[Any, Any, Any]:
    cursor = FakeCursor(description, rows)
    connection = FakeConnection(cursor, transaction_status=INTRANS)
    result = PostgresAdapter("", MaskingEngine(load_config_text(config)))
    result._connection = cast(Any, connection)
    result._provenance = cast(Any, FakeResolver())
    return result, cursor, connection


@pytest.mark.parametrize("description", [[TypedColumn("x", 1700)], []])
def test_unsupported_metadata_refuses_before_fetch_and_settles(description):
    item, cursor, connection = adapter(description, [])
    with pytest.raises(DatabaseResultTypeError) as caught:
        item._execute_typed_validated("SELECT 1")
    assert not cursor.batch_sizes
    assert connection.rollbacks == 1 and not connection.commits
    assert caught.value.__context__ is None


def test_legacy_does_not_require_type_code():
    item, _, connection = adapter([FakeColumn("x")], [(1,)])
    assert item.execute_validated("SELECT 1").rows == ((1,),)
    assert connection.rollbacks == 1


def test_masked_source_type_is_not_read_or_retained():
    class MaskedColumn(FakeColumn):
        @property
        def type_code(self):
            raise AssertionError("original type must not be read")

    item, cursor, connection = adapter(
        [MaskedColumn("cpf")],
        [(123,)],
        'masking:\n  - match: cpf\n    transformer: fixed\n    config:\n      value: "[MASK]"\n',
    )
    result = item._execute_typed_validated("SELECT 123 AS cpf")
    assert type(result) is TypedMaskedResult
    assert result.type_oids == (25,) and result.masked.rows == (("[MASK]",),)
    assert cursor.batch_sizes and connection.rollbacks == 1


@pytest.mark.parametrize("oid", [None, True, 25.0, 0, -1, 2**64])
def test_unmasked_invalid_oid_refuses_before_fetch(oid):
    item, cursor, connection = adapter([TypedColumn("x", oid)], [(None,)])
    with pytest.raises(DatabaseResultTypeError):
        item._execute_typed_validated("SELECT NULL AS x")
    assert not cursor.batch_sizes and connection.rollbacks == 1


def test_metadata_memory_error_is_not_reported_as_recoverable_type_error():
    class OomColumn(FakeColumn):
        @property
        def type_code(self):
            raise MemoryError("CANARY_METADATA_OOM")

    item, cursor, connection = adapter([OomColumn("x")], [(None,)])
    with pytest.raises(MemoryError) as caught:
        item._execute_typed_validated("SELECT NULL AS x")
    assert not cursor.batch_sizes and connection.rollbacks == 1
    assert "CANARY" not in str(caught.value) and caught.value.__context__ is None


def test_analysis_once_and_typed_result_has_no_cross_query_metadata(monkeypatch):
    item, _, connection = adapter([TypedColumn("x", 23)], [(1,)])
    original = postgres_module.analyze_sensitivity
    calls = []

    def analyze(statement, policy):
        calls.append(statement)
        return original(statement, policy)

    monkeypatch.setattr(postgres_module, "analyze_sensitivity", analyze)
    first = item._execute_typed_validated("SELECT 1 AS x")
    connection._cursor = FakeCursor([TypedColumn("x", 16)], [(False,)])
    second = item._execute_typed_validated("SELECT FALSE AS x")
    assert len(calls) == 2
    assert first.type_oids == (23,) and first.masked.rows == ((1,),)
    assert second.type_oids == (16,) and second.masked.rows == ((False,),)


def test_metadata_getter_error_is_fixed_and_settled():
    class BrokenColumn(FakeColumn):
        @property
        def type_code(self):
            raise RuntimeError("CANARY_TYPE_PROPERTY")

    item, cursor, connection = adapter([BrokenColumn("x")], [(None,)])
    with pytest.raises(DatabaseResultIntegrityError) as caught:
        item._execute_typed_validated("SELECT NULL AS x")
    assert not cursor.batch_sizes and connection.rollbacks == 1
    assert caught.value.__context__ is None and "CANARY" not in str(caught.value)


def test_metadata_width_divergence_is_integrity_not_unsupported_type():
    _, cursor, _ = adapter([TypedColumn("x", 23)], [(1,)])
    with pytest.raises(DatabaseResultIntegrityError):
        PostgresAdapter._typed_oids(cursor, (Decision(Action.ALLOW, "x"),) * 2)
