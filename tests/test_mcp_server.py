"""Servidor MCP pela camada real do protocolo (Fase 5).

Todos os testes passam pelo cliente in-memory do SDK (`mcp.Client(server)`),
nunca chamando a funcao Python decorada diretamente. O que se mede e o que um
cliente MCP de verdade veria.

O Gateway e substituido por um duble para que estes testes rodem sem banco; o
fluxo end-to-end contra PostgreSQL real esta em `test_mcp_integration.py`.
"""

from __future__ import annotations

import logging
from typing import Any, cast

import anyio
import pytest
from mcp import Client
from mcp.types import CallToolResult, ListToolsResult, TextContent

from maskgw.gateway.models import (
    CATEGORY_MESSAGES,
    ErrorCategory,
    GatewayError,
    QueryColumn,
    QueryResult,
)
from maskgw.mcp.server import TOOL_DESCRIPTION, build_mcp_server

CPF = "11122233344"
EMAIL = "joao@example.com"
MASKED_CPF = "d41d8cd98f00b204e9800998ecf8427e"


class FakeGateway:
    """Duble do Gateway: devolve um resultado fixo ou levanta uma categoria."""

    def __init__(
        self,
        result: QueryResult | None = None,
        error: ErrorCategory | None = None,
    ) -> None:
        self._result = result
        self._error = error
        self.calls: list[str] = []

    def query(self, sql: str) -> QueryResult:
        self.calls.append(sql)
        if self._error is not None:
            raise GatewayError(self._error)
        assert self._result is not None
        return self._result

    def close(self) -> None:
        return None


def result_of(**kwargs: Any) -> QueryResult:
    defaults: dict[str, Any] = {
        "columns": [QueryColumn(name="nome", masked=False)],
        "rows": [["Joao"]],
        "row_count": 1,
        "truncated": False,
    }
    defaults.update(kwargs)
    return QueryResult(**defaults)


def call(gateway: object, arguments: dict[str, Any]) -> CallToolResult:
    """Chama a tool pelo protocolo, com cliente in-memory."""

    async def run() -> CallToolResult:
        async with Client(build_mcp_server(cast("Any", gateway))) as client:
            return await client.call_tool("query_database", arguments)

    return anyio.run(run)


def tools_of(gateway: object) -> ListToolsResult:
    async def run() -> ListToolsResult:
        async with Client(build_mcp_server(cast("Any", gateway))) as client:
            return await client.list_tools()

    return anyio.run(run)


def text_of(result: CallToolResult) -> str:
    """Texto do primeiro bloco de conteudo, com o tipo estreitado."""
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


@pytest.fixture
def gateway():
    return FakeGateway(result_of())


class TestToolDiscovery:
    def test_tools_list_finds_query_database(self, gateway):
        names = [tool.name for tool in tools_of(gateway).tools]
        assert names == ["query_database"]

    def test_there_is_exactly_one_tool(self, gateway):
        assert len(tools_of(gateway).tools) == 1

    def test_input_schema_has_only_sql(self, gateway):
        schema = tools_of(gateway).tools[0].input_schema
        assert set(schema["properties"]) == {"sql"}
        assert schema["required"] == ["sql"]
        assert schema["properties"]["sql"]["type"] == "string"

    @pytest.mark.parametrize(
        "forbidden",
        [
            "disable_masking",
            "raw",
            "unmasked",
            "masking",
            "transformer",
            "rules",
            "config",
            "timeout",
            "max_rows",
            "dsn",
            "password",
            "database",
        ],
    )
    def test_no_control_parameter_is_offered(self, gateway, forbidden):
        schema = tools_of(gateway).tools[0].input_schema
        assert forbidden not in schema["properties"]

    def test_output_schema_is_published(self, gateway):
        schema = tools_of(gateway).tools[0].output_schema
        assert schema is not None
        assert set(schema["properties"]) == {"columns", "rows", "row_count", "truncated"}

    def test_output_schema_does_not_expose_provenance(self, gateway):
        schema = tools_of(gateway).tools[0].output_schema
        rendered = str(schema)
        for internal in ("origin_name", "origin_schema", "origin_table", "provenance", "oid"):
            assert internal not in rendered

    def test_description_guides_without_revealing(self, gateway):
        description = tools_of(gateway).tools[0].description
        assert description == TOOL_DESCRIPTION
        assert "truncated" in description
        assert "masked" in description
        for internal in ("hmac", "md5", "cpf", "transformer", "pg_attribute", "masking.yaml"):
            assert internal not in description.lower()


class TestStructuredOutput:
    def test_simple_query(self, gateway):
        result = call(gateway, {"sql": "SELECT nome FROM cliente"})
        assert result.is_error is False
        assert result.structured_content == {
            "columns": [{"name": "nome", "masked": False}],
            "rows": [["Joao"]],
            "row_count": 1,
            "truncated": False,
        }

    def test_the_sql_reaches_the_gateway(self, gateway):
        call(gateway, {"sql": "SELECT 1"})
        assert gateway.calls == ["SELECT 1"]

    def test_masked_column_is_flagged(self):
        gateway = FakeGateway(
            result_of(
                columns=[
                    QueryColumn(name="nome", masked=False),
                    QueryColumn(name="cpf", masked=True),
                ],
                rows=[["Joao", MASKED_CPF]],
            )
        )
        content = call(gateway, {"sql": "x"}).structured_content
        assert content is not None
        assert content["columns"] == [
            {"name": "nome", "masked": False},
            {"name": "cpf", "masked": True},
        ]

    def test_rows_stay_positional(self):
        gateway = FakeGateway(
            result_of(
                columns=[
                    QueryColumn(name="id", masked=False),
                    QueryColumn(name="id", masked=False),
                ],
                rows=[[1, 2]],
            )
        )
        response = call(gateway, {"sql": "SELECT a.id, b.id FROM a JOIN b ON true"})
        content = response.structured_content
        assert content is not None
        assert content["columns"] == [
            {"name": "id", "masked": False},
            {"name": "id", "masked": False},
        ]
        assert content["rows"] == [[1, 2]]

    def test_null_survives(self):
        gateway = FakeGateway(result_of(rows=[[None]]))
        content = call(gateway, {"sql": "x"}).structured_content
        assert content is not None
        assert content["rows"] == [[None]]

    def test_unicode_survives(self):
        gateway = FakeGateway(result_of(rows=[["coração ção 日本"]]))
        content = call(gateway, {"sql": "x"}).structured_content
        assert content is not None
        assert content["rows"] == [["coração ção 日本"]]

    def test_truncated_is_reported(self):
        gateway = FakeGateway(result_of(rows=[["a"], ["b"]], row_count=2, truncated=True))
        content = call(gateway, {"sql": "x"}).structured_content
        assert content is not None
        assert content["truncated"] is True
        assert content["row_count"] == 2

    def test_empty_result(self):
        gateway = FakeGateway(result_of(rows=[], row_count=0))
        content = call(gateway, {"sql": "x"}).structured_content
        assert content is not None
        assert content["rows"] == []
        assert content["row_count"] == 0


class TestErrorMapping:
    @pytest.mark.parametrize("category", list(ErrorCategory))
    def test_each_category_reaches_the_client(self, category):
        gateway = FakeGateway(error=category)
        result = call(gateway, {"sql": "x"})
        assert result.is_error is True
        text = result.content[0].text  # type: ignore[union-attr]
        assert category.value in text
        assert CATEGORY_MESSAGES[category] in text

    @pytest.mark.parametrize("category", list(ErrorCategory))
    def test_error_never_carries_the_sql(self, category):
        gateway = FakeGateway(error=category)
        sql = f"SELECT cpf FROM cliente WHERE cpf = '{CPF}'"
        result = call(gateway, {"sql": sql})
        rendered = str(result.model_dump())
        assert CPF not in rendered
        assert "cliente" not in rendered
        assert "SELECT" not in rendered

    def test_error_message_is_short(self):
        gateway = FakeGateway(error=ErrorCategory.QUERY_REJECTED)
        text = text_of(call(gateway, {"sql": "x"}))
        assert len(text) < 160

    def test_no_traceback_reaches_the_client(self):
        gateway = FakeGateway(error=ErrorCategory.DATABASE_ERROR)
        rendered = str(call(gateway, {"sql": "x"}).model_dump())
        assert "Traceback" not in rendered
        assert "maskgw/" not in rendered
        assert ".py" not in rendered

    def test_unexpected_exception_is_still_redacted(self):
        class Exploding:
            def query(self, sql: str) -> QueryResult:  # noqa: ARG002
                raise RuntimeError(f"segredo interno {CPF}")

        result = call(Exploding(), {"sql": "x"})
        assert result.is_error is True
        assert CPF not in str(result.model_dump())

    def test_no_structured_content_on_error(self):
        gateway = FakeGateway(error=ErrorCategory.INVALID_QUERY)
        assert call(gateway, {"sql": "x"}).structured_content is None


class TestClientCannotControlMasking:
    """O cliente controla apenas a SQL."""

    @pytest.mark.parametrize(
        "extra",
        [
            {"disable_masking": True},
            {"raw": True},
            {"unmasked": True},
            {"masking": False},
            {"transformer": "none"},
            {"max_rows": 999999},
            {"timeout": 0},
            {"dsn": "host=evil"},
        ],
    )
    def test_extra_arguments_cannot_change_the_result(self, extra):
        """Medido no SDK v2.1.1: extras sao IGNORADOS, nao recusados (D-037).

        A garantia que importa e esta: o resultado com o argumento extra e
        identico ao sem ele, e o Gateway recebe exatamente a mesma chamada.
        """
        gateway = FakeGateway(
            result_of(columns=[QueryColumn(name="cpf", masked=True)], rows=[[MASKED_CPF]])
        )
        baseline = call(gateway, {"sql": "SELECT cpf FROM cliente"})
        with_extra = call(gateway, {"sql": "SELECT cpf FROM cliente", **extra})

        assert with_extra.structured_content == baseline.structured_content
        assert with_extra.structured_content is not None
        assert with_extra.structured_content["columns"][0]["masked"] is True
        assert with_extra.structured_content["rows"] == [[MASKED_CPF]]

    def test_extra_argument_never_reaches_the_gateway(self):
        gateway = FakeGateway(result_of())
        call(gateway, {"sql": "SELECT 1", "disable_masking": True})
        assert gateway.calls == ["SELECT 1"]

    def test_missing_sql_is_rejected_by_the_schema(self, gateway):
        result = call(gateway, {})
        assert result.is_error is True
        assert gateway.calls == []

    def test_wrong_type_is_rejected_by_the_schema(self, gateway):
        result = call(gateway, {"sql": 123})
        assert result.is_error is True
        assert gateway.calls == []


class TestSurfaceIsMinimal:
    def test_no_resources_are_exposed(self, gateway):
        async def run() -> Any:
            async with Client(build_mcp_server(cast("Any", gateway))) as client:
                return await client.list_resources()

        assert anyio.run(run).resources == []

    def test_no_prompts_are_exposed(self, gateway):
        async def run() -> Any:
            async with Client(build_mcp_server(cast("Any", gateway))) as client:
                return await client.list_prompts()

        assert anyio.run(run).prompts == []


class TestNoLogLeak:
    def test_protocol_round_trip_logs_nothing_sensitive(self, caplog):
        gateway = FakeGateway(
            result_of(columns=[QueryColumn(name="cpf", masked=True)], rows=[[MASKED_CPF]])
        )
        with caplog.at_level(logging.DEBUG):
            call(gateway, {"sql": f"SELECT cpf FROM cliente WHERE cpf = '{CPF}'"})
        rendered = " ".join(record.getMessage() for record in caplog.records)
        assert CPF not in rendered
