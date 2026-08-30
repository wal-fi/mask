"""Gateway: orquestracao e fronteira de erro (Fase 5), sem banco.

O que se prova aqui: o Gateway traduz o `MaskedResult` interno para o modelo
publico SEM deixar vazar proveniencia nem detalhe de politica, e converte todo
erro interno em `GatewayError` com categoria — sem encadeamento.
"""

from __future__ import annotations

import datetime as dt
import logging
import traceback
from decimal import Decimal
from uuid import UUID

import psycopg
import pytest

from maskgw.audit import FAILURE, LOGGER_NAME, SUCCESS, AuditLog
from maskgw.db.result import MaskedResult
from maskgw.errors import (
    CapabilityError,
    ConfigError,
    DatabaseError,
    InvalidQuery,
    QueryRejected,
    QueryTimeout,
    TransformerError,
)
from maskgw.gateway.models import ErrorCategory, GatewayError, categorize, jsonable
from maskgw.gateway.service import Gateway
from maskgw.masking.descriptor import ColumnDescriptor, ProvenanceKind
from maskgw.masking.engine import Action, Decision
from tests.conftest import make_test_registry

CPF = "11122233344"
MASKED = "9f2c1e0d"


def masked_result(*, truncated: bool = False) -> MaskedResult:
    columns = (
        ColumnDescriptor(
            output_name="documento",
            origin_name="cpf",
            origin_schema="publico",
            origin_table="cliente",
            provenance_kind=ProvenanceKind.DIRECT,
        ),
        ColumnDescriptor(output_name="nome", origin_name="nome"),
    )
    decisions = (
        Decision(
            action=Action.MASK,
            output_name="documento",
            origin_name="cpf",
            rule_index=0,
            transformer_name="hmac_sha256",
        ),
        Decision(action=Action.ALLOW, output_name="nome", origin_name="nome"),
    )
    return MaskedResult(
        columns=columns,
        decisions=decisions,
        rows=((MASKED, "Joao"),),
        truncated=truncated,
    )


class FakeAdapter:
    def __init__(self, result: MaskedResult | None = None, error: BaseException | None = None):
        self._result = result if result is not None else masked_result()
        self._error = error
        self.queries: list[str] = []
        self.connects = 0
        self.closed_calls = 0

    def connect(self) -> None:
        self.connects += 1

    def execute_validated(self, sql: str) -> MaskedResult:
        self.queries.append(sql)
        if self._error is not None:
            raise self._error
        return self._result

    def close(self) -> None:
        self.closed_calls += 1


def build(adapter: object, audit: AuditLog | None = None) -> Gateway:
    # Desde a Fase 7 o Gateway recebe um RuntimeRegistry, nao um adapter: ele
    # adquire e libera um runtime por query (D-054).
    return Gateway(make_test_registry(adapter), audit if audit is not None else AuditLog())


class TestTranslation:
    def test_column_names_and_masked_flag(self):
        result = build(FakeAdapter()).query("SELECT cpf AS documento, nome FROM cliente")
        assert [c.name for c in result.columns] == ["documento", "nome"]
        assert [c.masked for c in result.columns] == [True, False]

    def test_rows_are_positional(self):
        result = build(FakeAdapter()).query("x")
        assert result.rows == [[MASKED, "Joao"]]

    def test_counts_and_truncation(self):
        result = build(FakeAdapter(masked_result(truncated=True))).query("x")
        assert result.row_count == 1
        assert result.truncated is True

    def test_the_sql_reaches_the_adapter_untouched(self):
        adapter = FakeAdapter()
        build(adapter).query("SELECT 1 -- comentario")
        assert adapter.queries == ["SELECT 1 -- comentario"]

    def test_connect_is_called_before_the_query(self):
        adapter = FakeAdapter()
        build(adapter).query("x")
        assert adapter.connects == 1


class TestProvenanceIsNotExposed:
    """O cliente recebe o dado seguro, nao o mapa do mecanismo (D-033)."""

    def test_result_model_has_no_provenance_fields(self):
        result = build(FakeAdapter()).query("x")
        rendered = result.model_dump_json()
        for internal in ("origin_name", "origin_schema", "origin_table", "provenance", "cliente"):
            assert internal not in rendered

    def test_column_model_has_only_name_and_masked(self):
        result = build(FakeAdapter()).query("x")
        assert set(result.columns[0].model_dump()) == {"name", "masked"}

    def test_transformer_name_is_not_exposed(self):
        result = build(FakeAdapter()).query("x")
        rendered = result.model_dump_json()
        assert "hmac_sha256" not in rendered
        assert "rule_index" not in rendered

    def test_result_model_has_exactly_four_fields(self):
        result = build(FakeAdapter()).query("x")
        assert set(result.model_dump()) == {"columns", "rows", "row_count", "truncated"}


class TestErrorCategories:
    @pytest.mark.parametrize(
        ("error", "category"),
        [
            (InvalidQuery("sintaxe SQL invalida"), ErrorCategory.INVALID_QUERY),
            (QueryRejected("somente SELECT e permitido"), ErrorCategory.QUERY_REJECTED),
            (QueryTimeout("tempo excedido"), ErrorCategory.QUERY_TIMEOUT),
            (DatabaseError("erro"), ErrorCategory.DATABASE_ERROR),
            (ConfigError("config"), ErrorCategory.CONFIGURATION_ERROR),
            (CapabilityError("capability"), ErrorCategory.CONFIGURATION_ERROR),
            (TransformerError("tipo"), ErrorCategory.DATABASE_ERROR),
            (RuntimeError("inesperado"), ErrorCategory.DATABASE_ERROR),
            (psycopg.OperationalError("cru"), ErrorCategory.DATABASE_ERROR),
        ],
    )
    def test_mapping(self, error, category):
        with pytest.raises(GatewayError) as info:
            build(FakeAdapter(error=error)).query("x")
        assert info.value.category is category

    def test_timeout_is_not_confused_with_database_error(self):
        """`QueryTimeout` e subclasse de `DatabaseError`: a ordem importa."""
        assert categorize(QueryTimeout("x")) is ErrorCategory.QUERY_TIMEOUT
        assert categorize(DatabaseError("x")) is ErrorCategory.DATABASE_ERROR

    def test_only_gateway_error_escapes(self):
        for error in (RuntimeError("x"), psycopg.Error("x"), ValueError("x")):
            with pytest.raises(GatewayError):
                build(FakeAdapter(error=error)).query("x")


class TestErrorsCarryNothing:
    def test_message_is_the_fixed_category_message(self):
        with pytest.raises(GatewayError) as info:
            build(FakeAdapter(error=QueryRejected("somente SELECT e permitido"))).query("x")
        assert str(info.value) == "The query was rejected by the database security policy."
        assert "SELECT" not in str(info.value).replace("The query", "")

    def test_internal_message_does_not_survive(self):
        internal = DatabaseError(f'invalid input syntax for type integer: "{CPF}"')
        with pytest.raises(GatewayError) as info:
            build(FakeAdapter(error=internal)).query("x")
        assert CPF not in str(info.value)
        assert "invalid input syntax" not in str(info.value)

    def test_not_chained(self):
        with pytest.raises(GatewayError) as info:
            build(FakeAdapter(error=DatabaseError(CPF))).query("x")
        assert info.value.__cause__ is None
        assert info.value.__context__ is None

    def test_traceback_render_is_clean(self):
        with pytest.raises(GatewayError) as info:
            build(FakeAdapter(error=DatabaseError(f"vazando {CPF}"))).query("x")
        rendered = "".join(
            traceback.format_exception(type(info.value), info.value, info.value.__traceback__)
        )
        assert CPF not in rendered

    def test_gateway_repr_has_nothing(self):
        assert repr(build(FakeAdapter())) == "Gateway()"


class TestAudit:
    def test_success_is_audited_with_metadata_only(self, caplog):
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            build(FakeAdapter(masked_result(truncated=True))).query(
                f"SELECT cpf FROM cliente WHERE cpf = '{CPF}'"
            )
        record = caplog.records[0]
        assert record.maskgw["outcome"] == SUCCESS
        assert record.maskgw["row_count"] == 1
        assert record.maskgw["truncated"] is True
        assert record.maskgw["error_category"] is None
        assert len(record.maskgw["request_id"]) == 32

    def test_failure_is_audited_with_the_category(self, caplog):
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME), pytest.raises(GatewayError):
            build(FakeAdapter(error=QueryRejected("x"))).query("INSERT INTO t VALUES (1)")
        record = caplog.records[0]
        assert record.maskgw["outcome"] == FAILURE
        assert record.maskgw["error_category"] == "QUERY_REJECTED"
        assert record.maskgw["row_count"] is None

    def test_no_sql_and_no_values_in_the_audit(self, caplog):
        sql = f"SELECT cpf FROM cliente WHERE cpf = '{CPF}'"
        with caplog.at_level(logging.DEBUG):
            build(FakeAdapter()).query(sql)
        rendered = " ".join(f"{r.getMessage()} {getattr(r, 'maskgw', '')}" for r in caplog.records)
        assert CPF not in rendered
        assert "SELECT" not in rendered
        assert MASKED not in rendered

    def test_each_query_gets_its_own_request_id(self, caplog):
        gateway = build(FakeAdapter())
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            gateway.query("a")
            gateway.query("b")
        ids = {record.maskgw["request_id"] for record in caplog.records}
        assert len(ids) == 2

    def test_duration_is_recorded(self, caplog):
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            build(FakeAdapter()).query("x")
        assert caplog.records[0].maskgw["duration_ms"] >= 0


class TestJsonable:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (b"ab", "YWI="),
            (bytearray(b"ab"), "YWI="),
            (memoryview(b"ab"), "YWI="),
            (b"\xff\xfe", "//4="),
        ],
    )
    def test_binary_becomes_base64(self, value, expected):
        assert jsonable(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            "texto",
            42,
            None,
            True,
            Decimal("1.50"),
            dt.date(2026, 8, 29),
            UUID("2f6b0e5c-2b4a-4c1e-9a3d-6f1c0b8e7d42"),
            {"a": 1},
            [1, 2],
        ],
    )
    def test_everything_else_passes_through(self, value):
        assert jsonable(value) is value


class TestLifecycle:
    def test_close_closes_the_adapter(self):
        adapter = FakeAdapter()
        build(adapter).close()
        assert adapter.closed_calls == 1

    def test_context_manager_closes(self):
        adapter = FakeAdapter()
        with build(adapter) as gateway:
            gateway.query("x")
        assert adapter.closed_calls == 1

    def test_connect_is_called_on_every_query(self):
        """Idempotente quando aberta; reconecta com verificacao se caiu."""
        adapter = FakeAdapter()
        gateway = build(adapter)
        gateway.query("a")
        gateway.query("b")
        assert adapter.connects == 2
