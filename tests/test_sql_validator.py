"""Validacao adversarial de SQL (Fase 4).

Todo cenario da lista obrigatoria do escopo da fase esta aqui. A decisao vem
sempre da AST que o proprio PostgreSQL produz — nunca de regex ou de
comparacao de palavra-chave.
"""

from __future__ import annotations

import pytest
from pglast import ast

from maskgw.errors import InvalidQuery, QueryRejected
from maskgw.sql.parser import MULTIPLE_STATEMENTS, NO_STATEMENT
from maskgw.sql.policy import SqlPolicy
from maskgw.sql.validator import (
    FORBIDDEN_FUNCTION,
    LOCKS_ROWS,
    NESTED_STATEMENT,
    NOT_A_SELECT,
    WRITES_A_RELATION,
    validate_select,
)

CPF = "12345678901"


def reason_for(sql: str, **kwargs: object) -> str:
    with pytest.raises(QueryRejected) as info:
        validate_select(sql, **kwargs)  # type: ignore[arg-type]
    return info.value.reason


class TestAcceptedQueries:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT 1",
            "SELECT cpf FROM cliente",
            "SELECT cpf AS documento FROM cliente",
            "SELECT * FROM cliente",
            "select CPF from CLIENTE",
            "SeLeCt CpF FrOm ClIeNtE",
            "SELECT cpf FROM cliente;",
            "-- comentario\nSELECT cpf FROM cliente",
            "/* bloco */ SELECT cpf FROM cliente -- fim",
            "SELECT a.cpf FROM cliente a JOIN pedido p ON p.id = a.id",
            "SELECT cpf FROM (SELECT cpf FROM cliente) x",
            "WITH x AS (SELECT cpf FROM cliente) SELECT cpf FROM x",
            "WITH a AS (SELECT 1), b AS (SELECT 2) SELECT * FROM a, b",
            "SELECT cpf FROM cliente UNION ALL SELECT cpf FROM fornecedor",
            "SELECT count(*) FROM cliente GROUP BY tipo HAVING count(*) > 1",
            "SELECT cpf FROM cliente ORDER BY id LIMIT 10 OFFSET 5",
            "SELECT lower(nome), substr(cpf, 1, 3), coalesce(a, b) FROM cliente",
            "SELECT cpf::text FROM cliente",
            "SELECT CASE WHEN a THEN b ELSE c END FROM t",
            "VALUES (1), (2)",
        ],
    )
    def test_select_is_accepted(self, sql):
        assert isinstance(validate_select(sql), ast.RawStmt)

    def test_returns_the_parsed_tree(self):
        statement = validate_select("SELECT cpf FROM cliente")
        assert isinstance(statement.stmt, ast.SelectStmt)


class TestSingleStatement:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT 1; SELECT 2",
            "SELECT 1; DROP TABLE cliente",
            "SELECT 1; DELETE FROM cliente",
            "SELECT cpf FROM cliente; GRANT ALL ON cliente TO PUBLIC",
        ],
    )
    def test_two_statements_are_rejected(self, sql):
        assert reason_for(sql) == MULTIPLE_STATEMENTS

    @pytest.mark.parametrize("sql", ["SELECT 1;", "SELECT 1;;", "SELECT 1 ; ;"])
    def test_trailing_semicolons_are_accepted(self, sql):
        assert isinstance(validate_select(sql), ast.RawStmt)

    @pytest.mark.parametrize("sql", ["", ";", "-- nada"])
    def test_no_statement_is_rejected(self, sql):
        assert reason_for(sql) == NO_STATEMENT


class TestSelectOnly:
    """A raiz executavel tem de ser SELECT. Por tipo de no, nao por texto."""

    @pytest.mark.parametrize(
        "sql",
        [
            "INSERT INTO cliente (cpf) VALUES ('x')",
            "UPDATE cliente SET cpf = 'x'",
            "DELETE FROM cliente",
            "MERGE INTO cliente c USING outra o ON true WHEN MATCHED THEN DELETE",
            "CREATE TABLE nova (a int)",
            "CREATE VIEW v AS SELECT 1",
            "ALTER TABLE cliente ADD COLUMN novo int",
            "DROP TABLE cliente",
            "TRUNCATE cliente",
            "GRANT SELECT ON cliente TO PUBLIC",
            "REVOKE SELECT ON cliente FROM PUBLIC",
            "COPY cliente FROM '/etc/passwd'",
            "COPY cliente TO '/tmp/vazamento.csv'",
            "COPY cliente FROM PROGRAM 'curl http://exemplo'",
            "CALL procedimento()",
            "DO $$ BEGIN PERFORM 1; END $$",
            "VACUUM cliente",
            "ANALYZE cliente",
            "REFRESH MATERIALIZED VIEW mv",
            "SET work_mem = '1MB'",
            "SET statement_timeout = 0",
            "RESET statement_timeout",
            "RESET ALL",
            "BEGIN",
            "COMMIT",
            "EXPLAIN SELECT 1",
            "PREPARE p AS SELECT 1",
            "EXECUTE p",
            "CREATE FUNCTION f() RETURNS int AS $$ SELECT 1 $$ LANGUAGE sql",
            "ALTER ROLE gateway SET statement_timeout = 0",
            "LOCK TABLE cliente",
            "CREATE TABLE nova AS SELECT * FROM cliente",
            "SELECT 1 INTO nova FROM cliente",
        ],
    )
    def test_non_select_is_rejected(self, sql):
        assert reason_for(sql) in {NOT_A_SELECT, WRITES_A_RELATION, NESTED_STATEMENT}

    @pytest.mark.parametrize(
        "sql",
        ["insert into cliente values (1)", "DrOp TaBlE cliente", "  DELETE  FROM cliente  "],
    )
    def test_case_and_spacing_do_not_help(self, sql):
        assert reason_for(sql) == NOT_A_SELECT


class TestWritingSelects:
    """SELECT que grava ou trava: a raiz e SelectStmt e ainda assim escreve."""

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT 1 INTO nova",
            "SELECT * INTO nova FROM cliente",
            "SELECT * INTO TEMP nova FROM cliente",
            "SELECT * INTO UNLOGGED nova FROM cliente",
        ],
    )
    def test_select_into_is_rejected(self, sql):
        assert reason_for(sql) == WRITES_A_RELATION

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM cliente FOR UPDATE",
            "SELECT * FROM cliente FOR NO KEY UPDATE",
            "SELECT * FROM cliente FOR SHARE",
            "SELECT * FROM cliente FOR KEY SHARE",
            "WITH x AS (SELECT 1) SELECT * FROM cliente FOR UPDATE",
        ],
    )
    def test_row_locking_is_rejected(self, sql):
        assert reason_for(sql) == LOCKS_ROWS


class TestModifyingCte:
    """Raiz SelectStmt nao basta: a arvore inteira e percorrida."""

    @pytest.mark.parametrize(
        "sql",
        [
            "WITH x AS (DELETE FROM cliente RETURNING *) SELECT * FROM x",
            "WITH x AS (INSERT INTO cliente VALUES ('x') RETURNING *) SELECT * FROM x",
            "WITH x AS (UPDATE cliente SET cpf = 'x' RETURNING *) SELECT * FROM x",
            (
                "WITH x AS (MERGE INTO cliente c USING outra o ON true "
                "WHEN MATCHED THEN DELETE RETURNING *) SELECT * FROM x"
            ),
        ],
    )
    def test_data_modifying_cte_is_rejected(self, sql):
        assert reason_for(sql) == NESTED_STATEMENT

    def test_nested_cte_is_rejected(self):
        sql = (
            "WITH a AS (WITH b AS (DELETE FROM cliente RETURNING *) SELECT * FROM b) "
            "SELECT * FROM a"
        )
        assert reason_for(sql) == NESTED_STATEMENT

    def test_triple_nested_cte_is_rejected(self):
        sql = (
            "WITH a AS (WITH b AS (WITH c AS (INSERT INTO cliente VALUES ('x') RETURNING *) "
            "SELECT * FROM c) SELECT * FROM b) SELECT * FROM a"
        )
        assert reason_for(sql) == NESTED_STATEMENT

    def test_modifying_cte_inside_a_subquery_is_rejected(self):
        sql = (
            "SELECT * FROM (WITH y AS (UPDATE cliente SET cpf = 'x' RETURNING *) SELECT * FROM y) z"
        )
        assert reason_for(sql) == NESTED_STATEMENT

    def test_modifying_cte_in_the_second_position_is_rejected(self):
        sql = (
            "WITH inocente AS (SELECT 1), malicioso AS (DELETE FROM cliente RETURNING *) "
            "SELECT * FROM inocente"
        )
        assert reason_for(sql) == NESTED_STATEMENT

    def test_modifying_cte_inside_a_union_branch_is_rejected(self):
        sql = (
            "SELECT 1 UNION ALL (WITH x AS (DELETE FROM cliente RETURNING 1 AS a) SELECT a FROM x)"
        )
        assert reason_for(sql) == NESTED_STATEMENT

    def test_read_only_cte_is_accepted(self):
        sql = "WITH x AS (SELECT cpf FROM cliente) SELECT * FROM x"
        assert isinstance(validate_select(sql), ast.RawStmt)

    def test_recursive_read_only_cte_is_accepted(self):
        sql = (
            "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 5) "
            "SELECT i FROM n"
        )
        assert isinstance(validate_select(sql), ast.RawStmt)


class TestFunctionPolicy:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT lower(nome) FROM cliente",
            "SELECT upper(nome), substr(cpf, 1, 3), length(nome) FROM cliente",
            "SELECT count(*), sum(valor), avg(valor) FROM pedido",
            "SELECT coalesce(a, b), nullif(a, b) FROM t",
            "SELECT date_trunc('day', criado_em) FROM cliente",
            "SELECT now(), current_date",
            "SELECT pg_typeof(1)",
            "SELECT to_char(criado_em, 'YYYY-MM-DD') FROM cliente",
            "SELECT string_agg(nome, ',') FROM cliente",
            "SELECT row_number() OVER (ORDER BY id) FROM cliente",
        ],
    )
    def test_safe_functions_are_allowed(self, sql):
        assert isinstance(validate_select(sql), ast.RawStmt)

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT pg_read_file('/etc/passwd')",
            "SELECT pg_read_binary_file('/etc/passwd')",
            "SELECT pg_ls_dir('/')",
            "SELECT pg_stat_file('/etc/passwd')",
            "SELECT dblink('host=x', 'SELECT 1')",
            "SELECT dblink_exec('host=x', 'DROP TABLE t')",
            "SELECT query_to_xml('SELECT * FROM cliente', true, true, '')",
            "SELECT table_to_xml('cliente', true, true, '')",
            "SELECT lo_import('/etc/passwd')",
            "SELECT lo_export(1, '/tmp/vazamento')",
            "SELECT set_config('statement_timeout', '0', false)",
            "SELECT setseed(0.5)",
            "SELECT pg_sleep(60)",
            "SELECT pg_terminate_backend(1)",
            "SELECT pg_cancel_backend(1)",
            "SELECT pg_reload_conf()",
            "SELECT pg_rotate_logfile()",
            "SELECT pg_advisory_lock(1)",
            "SELECT pg_notify('canal', 'mensagem')",
            "SELECT pg_backend_pid()",
        ],
    )
    def test_dangerous_functions_are_rejected(self, sql):
        assert reason_for(sql) == FORBIDDEN_FUNCTION

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT pg_catalog.pg_read_file('/etc/passwd')",
            "SELECT public.dblink('host=x', 'SELECT 1')",
            "SELECT pg_catalog.\"pg_ls_dir\"('/')",
        ],
    )
    def test_explicit_schema_does_not_help(self, sql):
        assert reason_for(sql) == FORBIDDEN_FUNCTION

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT PG_READ_FILE('/etc/passwd')",
            "SELECT Pg_Ls_Dir('/')",
            "SELECT PG_CATALOG.PG_READ_FILE('/etc/passwd')",
            "SELECT \"pg_read_file\"('/etc/passwd')",
            "SELECT DbLink('host=x', 'SELECT 1')",
        ],
    )
    def test_case_variation_does_not_help(self, sql):
        assert reason_for(sql) == FORBIDDEN_FUNCTION

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT (SELECT pg_read_file('/etc/passwd'))",
            "WITH x AS (SELECT pg_ls_dir('/') AS d) SELECT * FROM x",
            "SELECT 1 FROM cliente WHERE pg_sleep(60) IS NULL",
            "SELECT 1 FROM cliente ORDER BY pg_sleep(60)",
            "SELECT * FROM pg_ls_dir('/')",
            "SELECT 1 UNION ALL SELECT pg_read_file('/etc/passwd')::int",
            "SELECT 1 FROM cliente GROUP BY pg_sleep(1)",
            "SELECT 1 FROM cliente HAVING pg_sleep(1) IS NULL",
        ],
    )
    def test_forbidden_function_anywhere_is_rejected(self, sql):
        assert reason_for(sql) == FORBIDDEN_FUNCTION

    def test_pg_namespace_is_deny_by_default(self):
        """Funcao `pg_*` desconhecida e negada sem precisar estar numa lista."""
        assert reason_for("SELECT pg_funcao_inventada_no_futuro()") == FORBIDDEN_FUNCTION

    def test_ordinary_unknown_function_is_allowed(self):
        """Fora do namespace `pg_`, o default e permitir. Limite declarado."""
        assert isinstance(validate_select("SELECT minha_funcao(1) FROM t"), ast.RawStmt)


class TestExtensiblePolicy:
    def test_extra_allowed_pg_function(self):
        policy = SqlPolicy.build(extra_allowed_pg_functions=["pg_backend_pid"])
        assert isinstance(validate_select("SELECT pg_backend_pid()", policy=policy), ast.RawStmt)

    def test_extra_denied_function(self):
        policy = SqlPolicy.build(extra_denied_functions=["minha_funcao"])
        assert reason_for("SELECT minha_funcao(1)", policy=policy) == FORBIDDEN_FUNCTION

    def test_denial_wins_over_allowance(self):
        policy = SqlPolicy.build(
            extra_allowed_pg_functions=["pg_read_file"],
            extra_denied_functions=["pg_read_file"],
        )
        assert reason_for("SELECT pg_read_file('/x')", policy=policy) == FORBIDDEN_FUNCTION

    def test_extra_names_are_case_insensitive(self):
        policy = SqlPolicy.build(extra_denied_functions=["MinhaFuncao"])
        assert reason_for("SELECT minhafuncao(1)", policy=policy) == FORBIDDEN_FUNCTION

    def test_default_policy_is_immutable(self):
        policy = SqlPolicy.build(extra_denied_functions=["lower"])
        assert not policy.allows("lower")
        assert SqlPolicy().allows("lower")


class TestErrorsRevealNothing:
    """Nenhuma mensagem pode carregar a consulta ou valores dela."""

    @pytest.mark.parametrize(
        "sql",
        [
            f"INSERT INTO cliente VALUES ('{CPF}')",
            f"SELECT 1; DELETE FROM cliente WHERE cpf = '{CPF}'",
            f"WITH x AS (DELETE FROM cliente WHERE cpf = '{CPF}' RETURNING *) SELECT * FROM x",
            f"SELECT pg_read_file('/etc/{CPF}')",
            f"SELECT * INTO nova FROM cliente WHERE cpf = '{CPF}'",
        ],
    )
    def test_rejection_message_has_no_query_and_no_values(self, sql):
        with pytest.raises(QueryRejected) as info:
            validate_select(sql)
        message = str(info.value)
        assert CPF not in message
        assert "cliente" not in message
        assert "/etc" not in message
        assert "nova" not in message

    def test_reason_comes_from_a_fixed_set(self):
        reasons = {
            reason_for("INSERT INTO t VALUES (1)"),
            reason_for("SELECT 1; SELECT 2"),
            reason_for("WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x"),
            reason_for("SELECT pg_read_file('/x')"),
            reason_for("SELECT 1 INTO t"),
            reason_for("SELECT * FROM t FOR UPDATE"),
            reason_for(";"),
        }
        assert reasons == {
            NOT_A_SELECT,
            MULTIPLE_STATEMENTS,
            NESTED_STATEMENT,
            FORBIDDEN_FUNCTION,
            WRITES_A_RELATION,
            LOCKS_ROWS,
            NO_STATEMENT,
        }

    def test_no_function_name_leaks_into_the_message(self):
        with pytest.raises(QueryRejected) as info:
            validate_select("SELECT pg_read_file('/etc/passwd')")
        assert "pg_read_file" not in str(info.value)
        assert "/etc/passwd" not in str(info.value)

    def test_rejection_is_not_chained(self):
        with pytest.raises(QueryRejected) as info:
            validate_select("INSERT INTO t VALUES (1)")
        assert info.value.__cause__ is None
        assert info.value.__context__ is None

    def test_invalid_sql_still_raises_invalid_query(self):
        with pytest.raises(InvalidQuery):
            validate_select(f"SELEC '{CPF}'")
