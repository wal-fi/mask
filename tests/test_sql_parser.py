"""Comportamento real do pglast ao contar statements (Fase 4).

Como em `test_pgresult_metadata`, este arquivo mede antes de decidir. O
criterio de "um statement" nao pode ser contagem de ponto e virgula: o parser
do PostgreSQL descarta statements vazios, e e o numero de statements
EXECUTAVEIS que importa.

Se uma versao futura do pglast mudar esse comportamento, estes testes quebram
antes do validator.
"""

from __future__ import annotations

import traceback

import pytest
from pglast import ast

from maskgw.errors import InvalidQuery, QueryRejected
from maskgw.sql.parser import (
    MULTIPLE_STATEMENTS,
    NO_STATEMENT,
    parse_single_statement,
    parse_statements,
)

SQL_INJECTION_MARKER = "12345678901"


class TestStatementCounting:
    """O que o parser considera um statement executavel."""

    @pytest.mark.parametrize(
        ("sql", "count"),
        [
            ("SELECT 1", 1),
            ("SELECT 1;", 1),
            ("SELECT 1;;", 1),
            ("SELECT 1 ;  ; ", 1),
            ("-- comentario\nSELECT 1", 1),
            ("/* bloco */ SELECT 1", 1),
            ("SELECT 1; SELECT 2", 2),
            ("SELECT 1; DROP TABLE t", 2),
            ("SELECT 1;SELECT 2;SELECT 3", 3),
            ("", 0),
            (";", 0),
            (";;;", 0),
            ("   ", 0),
            ("-- so comentario", 0),
        ],
    )
    def test_executable_statement_count(self, sql, count):
        assert len(parse_statements(sql)) == count

    def test_trailing_semicolon_is_not_a_second_statement(self):
        assert isinstance(parse_single_statement("SELECT 1;").stmt, ast.SelectStmt)

    def test_repeated_semicolons_are_not_statements(self):
        assert isinstance(parse_single_statement("SELECT 1;;").stmt, ast.SelectStmt)


class TestSingleStatementEnforcement:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT 1; SELECT 2",
            "SELECT 1; DROP TABLE t",
            "SELECT 1; INSERT INTO t VALUES (1)",
            "SELECT 1;SELECT 2;",
            "SELECT 1; UPDATE t SET a = 1",
        ],
    )
    def test_two_statements_are_rejected(self, sql):
        with pytest.raises(QueryRejected) as info:
            parse_single_statement(sql)
        assert info.value.reason == MULTIPLE_STATEMENTS

    @pytest.mark.parametrize("sql", ["", ";", "   ", "-- nada", ";;"])
    def test_no_statement_is_rejected(self, sql):
        with pytest.raises(QueryRejected) as info:
            parse_single_statement(sql)
        assert info.value.reason == NO_STATEMENT


class TestInvalidSql:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELEC 1",
            "SELECT FROM WHERE",
            "SELECT * FROM",
            "SELECT (1",
            "WITH x AS SELECT 1",
        ],
    )
    def test_malformed_sql_is_rejected_before_the_database(self, sql):
        with pytest.raises(InvalidQuery):
            parse_single_statement(sql)

    def test_message_is_generic(self):
        with pytest.raises(InvalidQuery) as info:
            parse_single_statement("SELEC 1")
        assert str(info.value) == "sintaxe SQL invalida"

    def test_message_does_not_echo_the_query(self):
        sql = f"SELEC '{SQL_INJECTION_MARKER}'"
        with pytest.raises(InvalidQuery) as info:
            parse_single_statement(sql)
        assert SQL_INJECTION_MARKER not in str(info.value)
        assert "SELEC" not in str(info.value)

    def test_parser_error_is_not_chained(self):
        """A mensagem do pglast cita a consulta: nao pode sobrar em __context__."""
        with pytest.raises(InvalidQuery) as info:
            parse_single_statement(f"SELEC '{SQL_INJECTION_MARKER}'")
        assert info.value.__cause__ is None
        assert info.value.__context__ is None

    def test_traceback_render_does_not_echo_the_query(self):
        with pytest.raises(InvalidQuery) as info:
            parse_single_statement(f"SELEC '{SQL_INJECTION_MARKER}'")
        rendered = "".join(
            traceback.format_exception(type(info.value), info.value, info.value.__traceback__)
        )
        assert SQL_INJECTION_MARKER not in rendered

    def test_non_string_input_is_rejected(self):
        with pytest.raises(InvalidQuery):
            parse_statements(None)  # type: ignore[arg-type]
