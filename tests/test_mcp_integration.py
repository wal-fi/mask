"""Fluxo end-to-end: cliente MCP real -> Gateway -> PostgreSQL (Fase 5).

O caminho inteiro, pelo protocolo, contra um banco de verdade:

    MCP Client -> query_database -> Gateway -> SQL Validator
               -> PostgresAdapter -> PostgreSQL -> provenance
               -> Masking Engine -> row limit -> MCP response

`TestTheFundamentalSecurityTest` e o teste central do projeto: o CPF original
nao pode aparecer em NENHUMA parte da resposta, nem no log, nem na excecao.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

import anyio
import psycopg
import pytest
from mcp import Client
from mcp.types import CallToolResult, TextContent

from maskgw.errors import ConfigError, DatabaseError
from maskgw.gateway.factory import build_application
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.mcp.server import build_mcp_server
from maskgw.secretsource import MappingSecretProvider
from tests.conftest import TEST_HMAC_KEY

pytestmark = pytest.mark.integration

SCHEMA = "maskgw_fase5"
TABLE = f"{SCHEMA}.cliente"

NOME = "Joao"
CPF = "11122233344"
EMAIL = "joao@example.com"

CONFIG = """
masking:
  - match: cpf
    transformer: hmac_sha256
  - match: email
    transformer: regex
    config:
      pattern: "^(.{2}).*(@.*)$"
      replacement: "\\\\1***\\\\2"

database:
  statement_timeout_ms: 2000
  max_rows: 5
"""

#: DDL sem parametros: o protocolo estendido recusa multiplos comandos quando
#: ha parametros (medido na Fase 2), entao a insercao vai separada.
DDL = f"""
DROP SCHEMA IF EXISTS {SCHEMA} CASCADE;
CREATE SCHEMA {SCHEMA};
CREATE TABLE {TABLE} (
    id integer, nome text, cpf text, email text, obs text, criado date
);
INSERT INTO {TABLE}
SELECT i, 'Cliente ' || i, lpad(i::text, 11, '0'), 'c' || i || '@example.com',
       NULL, DATE '2026-01-01'
FROM generate_series(2, 20) AS i;
CREATE TABLE {SCHEMA}.pedido (id integer, cliente_id integer);
INSERT INTO {SCHEMA}.pedido VALUES (1, 1);
"""

INSERT_JOAO = f"INSERT INTO {TABLE} VALUES (1, %s, %s, %s, NULL, DATE '2026-08-29')"


def text_of(result: CallToolResult) -> str:
    """Texto do primeiro bloco de conteudo, com o tipo estreitado."""
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


@pytest.fixture
def database(dsn: str) -> Iterator[str]:
    with psycopg.connect(dsn, autocommit=True) as setup:
        setup.execute(DDL)
        setup.execute(INSERT_JOAO, [NOME, CPF, EMAIL])
    yield dsn
    with psycopg.connect(dsn, autocommit=True) as teardown:
        teardown.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "masking.yaml"
    path.write_text(CONFIG, encoding="utf-8")
    return path


@pytest.fixture
def application(database, config_file):
    app = build_application(
        config_path=config_file,
        conninfo=database,
        secrets=MappingSecretProvider({HMAC_KEY_ENV: TEST_HMAC_KEY}),
    )
    yield app
    app.close()


@pytest.fixture
def ask(application):
    """Chama a tool pelo protocolo MCP, com cliente in-memory."""

    def _ask(sql: str, **extra: Any) -> CallToolResult:
        async def run() -> CallToolResult:
            async with Client(build_mcp_server(application.gateway)) as client:
                return await client.call_tool("query_database", {"sql": sql, **extra})

        return anyio.run(run)

    return _ask


class TestTheFundamentalSecurityTest:
    """O teste central do projeto.

    Dados: nome = Joao, cpf = 11122233344, email = joao@example.com
    """

    def test_the_three_columns_behave_as_configured(self, ask):
        result = ask(f"SELECT nome, cpf, email FROM {TABLE} WHERE id = 1")
        content = result.structured_content
        assert content is not None
        row = content["rows"][0]

        assert row[0] == NOME, "nome nao casa regra: passa original"
        assert row[1] != CPF, "cpf tem de estar transformado"
        assert len(row[1]) == 64, "hmac_sha256 produz 64 hex"
        assert row[2] == "jo***@example.com", "email segue o transformer regex"

        assert content["columns"] == [
            {"name": "nome", "masked": False},
            {"name": "cpf", "masked": True},
            {"name": "email", "masked": True},
        ]

    def test_the_cpf_appears_nowhere_in_the_response(self, ask):
        result = ask(f"SELECT nome, cpf, email FROM {TABLE} WHERE id = 1")
        assert CPF not in json.dumps(result.structured_content, ensure_ascii=False)
        assert CPF not in json.dumps(
            result.model_dump(mode="json"), ensure_ascii=False, default=str
        )
        for item in result.content:
            assert CPF not in getattr(item, "text", "")
        assert CPF not in repr(result)

    def test_the_cpf_appears_nowhere_in_the_logs(self, ask, caplog):
        with caplog.at_level(logging.DEBUG):
            ask(f"SELECT nome, cpf, email FROM {TABLE} WHERE cpf = '{CPF}'")
        rendered = " ".join(
            f"{r.getMessage()} {getattr(r, 'maskgw', '')} {r.exc_text or ''}"
            for r in caplog.records
        )
        assert CPF not in rendered

    def test_the_cpf_appears_nowhere_even_when_the_query_fails(self, ask, caplog):
        with caplog.at_level(logging.DEBUG):
            result = ask(f"SELECT cpf::integer FROM {TABLE} WHERE cpf = '{CPF}'")
        assert result.is_error is True
        rendered = " ".join(
            f"{r.getMessage()} {getattr(r, 'maskgw', '')} {r.exc_text or ''}"
            for r in caplog.records
        )
        assert CPF not in rendered
        assert CPF not in str(result.model_dump())

    def test_alias_does_not_help(self, ask):
        result = ask(f"SELECT cpf AS documento FROM {TABLE} WHERE id = 1")
        content = result.structured_content
        assert content is not None
        assert content["rows"][0][0] != CPF
        assert content["columns"][0] == {"name": "documento", "masked": True}

    def test_select_star_masks_the_sensitive_columns(self, ask):
        result = ask(f"SELECT * FROM {TABLE} WHERE id = 1")
        content = result.structured_content
        assert content is not None
        assert CPF not in json.dumps(content, ensure_ascii=False)
        masked = {c["name"]: c["masked"] for c in content["columns"]}
        assert masked["cpf"] is True
        assert masked["email"] is True
        assert masked["nome"] is False

    def test_expression_over_the_cpf_is_masked(self, ask):
        """Fase 6.1 (D-043): a analise de AST cobre o que a proveniencia nao."""
        result = ask(f"SELECT substr(cpf, 1, 3) AS x FROM {TABLE} WHERE id = 1")
        content = result.structured_content
        assert content is not None
        assert content["rows"][0][0] != CPF[:3]
        assert content["columns"][0]["masked"] is True


class TestQueryShapes:
    def test_join(self, ask):
        sql = (
            f"SELECT c.cpf, p.id FROM {TABLE} c "
            f"JOIN {SCHEMA}.pedido p ON p.cliente_id = c.id WHERE c.id = 1"
        )
        content = ask(sql).structured_content
        assert content is not None
        assert content["rows"][0][0] != CPF
        assert content["rows"][0][1] == 1

    def test_duplicate_column_names_survive_independently(self, ask):
        sql = (
            f"SELECT c.id, p.id FROM {TABLE} c "
            f"JOIN {SCHEMA}.pedido p ON p.cliente_id = c.id WHERE c.id = 1"
        )
        content = ask(sql).structured_content
        assert content is not None
        assert content["columns"] == [
            {"name": "id", "masked": False},
            {"name": "id", "masked": False},
        ]
        assert content["rows"] == [[1, 1]]

    def test_null_survives(self, ask):
        content = ask(f"SELECT obs FROM {TABLE} WHERE id = 1").structured_content
        assert content is not None
        assert content["rows"] == [[None]]

    def test_unicode_survives(self, ask):
        content = ask("SELECT 'coração ção 日本'::text AS texto").structured_content
        assert content is not None
        assert content["rows"] == [["coração ção 日本"]]

    def test_date_is_serialised(self, ask):
        content = ask(f"SELECT criado FROM {TABLE} WHERE id = 1").structured_content
        assert content is not None
        assert content["rows"] == [["2026-08-29"]]

    def test_empty_result(self, ask):
        content = ask(f"SELECT cpf FROM {TABLE} WHERE false").structured_content
        assert content is not None
        assert content["rows"] == []
        assert content["row_count"] == 0
        assert content["truncated"] is False


class TestTruncation:
    def test_result_is_truncated_at_max_rows(self, ask):
        content = ask(f"SELECT id FROM {TABLE} ORDER BY id").structured_content
        assert content is not None
        assert content["row_count"] == 5
        assert content["truncated"] is True
        assert content["rows"] == [[1], [2], [3], [4], [5]]

    def test_exactly_max_rows_is_not_truncated(self, ask):
        content = ask(f"SELECT id FROM {TABLE} ORDER BY id LIMIT 5").structured_content
        assert content is not None
        assert content["row_count"] == 5
        assert content["truncated"] is False

    def test_fewer_rows_is_not_truncated(self, ask):
        content = ask(f"SELECT id FROM {TABLE} ORDER BY id LIMIT 2").structured_content
        assert content is not None
        assert content["truncated"] is False

    def test_truncated_rows_are_still_masked(self, ask):
        content = ask(f"SELECT cpf FROM {TABLE} ORDER BY id").structured_content
        assert content is not None
        assert content["truncated"] is True
        assert all(len(row[0]) == 64 for row in content["rows"])


class TestRejections:
    @pytest.mark.parametrize(
        ("sql", "category"),
        [
            ("SELEC 1", "INVALID_QUERY"),
            (f"INSERT INTO {TABLE} VALUES (99, 'x', 'y', 'z', NULL, NULL)", "QUERY_REJECTED"),
            (f"UPDATE {TABLE} SET cpf = 'x'", "QUERY_REJECTED"),
            (f"DELETE FROM {TABLE}", "QUERY_REJECTED"),
            (f"DROP TABLE {TABLE}", "QUERY_REJECTED"),
            ("SELECT 1 INTO nova", "QUERY_REJECTED"),
            ("SELECT 1; SELECT 2", "QUERY_REJECTED"),
            (f"SELECT 1; DROP TABLE {TABLE}", "QUERY_REJECTED"),
            (f"WITH x AS (DELETE FROM {TABLE} RETURNING *) SELECT * FROM x", "QUERY_REJECTED"),
            ("SELECT pg_read_file('/etc/passwd')", "QUERY_REJECTED"),
            ("SET statement_timeout = 0", "QUERY_REJECTED"),
            ("SELECT * FROM tabela_que_nao_existe", "DATABASE_ERROR"),
            ("SELECT pg_sleep(30)", "QUERY_REJECTED"),
        ],
    )
    def test_category_reaches_the_client(self, ask, sql, category):
        result = ask(sql)
        assert result.is_error is True
        assert category in text_of(result)

    def test_timeout_category(self, ask):
        result = ask("SELECT count(*) FROM generate_series(1, 500000000)")
        assert result.is_error is True
        assert "QUERY_TIMEOUT" in text_of(result)

    def test_rejection_never_echoes_the_query(self, ask):
        result = ask(f"INSERT INTO {TABLE} VALUES (99, 'x', '{CPF}', 'z', NULL, NULL)")
        rendered = str(result.model_dump())
        assert CPF not in rendered
        assert "INSERT" not in rendered
        assert SCHEMA not in rendered

    def test_postgres_message_never_reaches_the_client(self, ask):
        result = ask("SELECT * FROM tabela_que_nao_existe")
        rendered = str(result.model_dump())
        assert "tabela_que_nao_existe" not in rendered
        assert "does not exist" not in rendered

    def test_the_table_is_intact(self, ask, database):
        for sql in (f"DELETE FROM {TABLE}", f"UPDATE {TABLE} SET cpf = 'x'"):
            assert ask(sql).is_error is True
        with psycopg.connect(database, autocommit=True) as control:
            row = control.execute(f"SELECT count(*) FROM {TABLE}").fetchone()
            assert row is not None
            assert row[0] == 20


class TestClientCannotDisableMasking:
    def test_extra_argument_does_not_change_anything(self, ask):
        baseline = ask(f"SELECT cpf FROM {TABLE} WHERE id = 1")
        attempt = ask(f"SELECT cpf FROM {TABLE} WHERE id = 1", disable_masking=True)
        assert attempt.structured_content == baseline.structured_content
        assert CPF not in json.dumps(attempt.structured_content, ensure_ascii=False)

    def test_sql_cannot_read_the_masking_config(self, ask):
        """A configuracao nao esta no banco: nao ha o que consultar."""
        result = ask("SELECT * FROM masking_rules")
        assert result.is_error is True

    def test_sql_cannot_change_session_limits(self, ask):
        assert ask("SET statement_timeout = 0").is_error is True
        assert ask("SET default_transaction_read_only = off").is_error is True
        content = ask(
            "SELECT setting FROM pg_settings WHERE name = 'default_transaction_read_only'"
        ).structured_content
        assert content is not None
        assert content["rows"] == [["on"]]


class TestAuditDuringRealQueries:
    def test_success_and_failure_are_audited(self, ask, caplog):
        with caplog.at_level(logging.INFO, logger="maskgw.audit"):
            ask(f"SELECT cpf FROM {TABLE} WHERE id = 1")
            ask(f"DELETE FROM {TABLE}")
        outcomes = [record.maskgw["outcome"] for record in caplog.records]
        assert outcomes == ["success", "failure"]
        assert caplog.records[1].maskgw["error_category"] == "QUERY_REJECTED"

    def test_audit_never_carries_the_sql_or_values(self, ask, caplog):
        with caplog.at_level(logging.DEBUG):
            ask(f"SELECT nome, cpf FROM {TABLE} WHERE cpf = '{CPF}'")
        rendered = " ".join(f"{r.getMessage()} {getattr(r, 'maskgw', '')}" for r in caplog.records)
        assert CPF not in rendered
        assert NOME not in rendered
        assert "SELECT" not in rendered


class TestStartup:
    def test_invalid_config_prevents_startup(self, database, tmp_path):
        path = tmp_path / "ruim.yaml"
        path.write_text(
            "masking:\n  - match: cpf\n    transformer: inexistente\n", encoding="utf-8"
        )
        with pytest.raises(ConfigError):
            build_application(config_path=path, conninfo=database)

    def test_missing_hmac_key_prevents_startup(self, database, config_file):
        with pytest.raises(ConfigError):
            build_application(
                config_path=config_file,
                conninfo=database,
                secrets=MappingSecretProvider({}),
            )

    def test_unavailable_database_prevents_startup(self, config_file):
        with pytest.raises(DatabaseError):
            build_application(
                config_path=config_file,
                conninfo="host=127.0.0.1 port=1 dbname=x connect_timeout=2",
                secrets=MappingSecretProvider({HMAC_KEY_ENV: TEST_HMAC_KEY}),
            )

    def test_application_is_usable_right_after_build(self, application):
        result = application.gateway.query(f"SELECT cpf FROM {TABLE} WHERE id = 1")
        assert result.rows[0][0] != CPF
