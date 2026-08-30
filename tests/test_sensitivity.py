"""Analise de sensitividade por AST (Fase 6.1), sem banco.

O que se prova aqui: a analise identifica a dependencia certa, respeita
exceptions sobre o nome REFERENCIADO, recusa o que nao consegue provar, e nao
mascara demais.
"""

from __future__ import annotations

import time

import pytest

from maskgw.config import load_config_text
from maskgw.errors import QueryRejected
from maskgw.masking.rules import MaskingPolicy
from maskgw.sql.parser import parse_single_statement
from maskgw.sql.sensitivity import (
    AMBIGUOUS_SENSITIVE_EXPRESSION,
    MAX_DEPTH,
    WHOLE_ROW_SERIALIZATION,
    analyze_sensitivity,
)

CONFIG = """
masking:
  - match: cpf
    transformer: md5
  - match: email
    transformer: sha256
exceptions:
  - match: tipo_cpf
    mode: exact
"""


@pytest.fixture
def policy(secrets):
    return load_config_text(CONFIG, secrets=secrets)


def analyze(sql: str, policy: MaskingPolicy) -> tuple[int | None, ...] | None:
    return analyze_sensitivity(parse_single_statement(sql), policy)


class TestDirectDependencies:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT substr(cpf, 1, 11) AS d FROM cliente",
            "SELECT cpf || '' AS d FROM cliente",
            "SELECT upper(cpf) AS d FROM cliente",
            "SELECT reverse(cpf) AS d FROM cliente",
            "SELECT encode(convert_to(cpf, 'UTF8'), 'base64') AS d FROM cliente",
            "SELECT coalesce(cpf, '') AS d FROM cliente",
            "SELECT CASE WHEN true THEN cpf END AS d FROM cliente",
            "SELECT min(cpf) AS d FROM cliente",
            "SELECT array_agg(cpf) AS d FROM cliente",
            "SELECT json_agg(cpf) AS d FROM cliente",
            "SELECT to_json(cpf) AS d FROM cliente",
            "SELECT cpf::varchar AS d FROM cliente",
            "SELECT substr(c.cpf, 1, 11) AS d FROM cliente c",
            "SELECT (SELECT cpf FROM cliente LIMIT 1) AS d",
            "SELECT nr_cpf AS d FROM cliente",
        ],
    )
    def test_first_rule_is_found(self, policy, sql):
        assert analyze(sql, policy) == (0,)

    def test_second_rule_is_found(self, policy):
        assert analyze("SELECT upper(email) AS d FROM cliente", policy) == (1,)

    def test_position_is_respected(self, policy):
        sql = "SELECT nome, upper(cpf) AS d, id FROM cliente"
        assert analyze(sql, policy) == (None, 0, None)


class TestNoFalsePositives:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT nome FROM cliente",
            "SELECT upper(nome) AS d FROM cliente",
            "SELECT count(*) AS n FROM cliente",
            "SELECT 1 AS n",
            "SELECT upper('literal') AS d",
            "SELECT substr(tipo_cpf, 1, 3) AS d FROM cliente",
            "SELECT tipo_cpf FROM cliente",
        ],
    )
    def test_nothing_sensitive_found(self, policy, sql):
        assert analyze(sql, policy) == (None,)

    def test_exception_is_honoured_on_the_referenced_name(self, policy):
        """`tipo_cpf` casaria a regra `cpf` por contains; a exception vence."""
        assert analyze("SELECT min(tipo_cpf) AS d FROM cliente", policy) == (None,)


class TestUnion:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT cpf FROM a UNION ALL SELECT cpf FROM b",
            "SELECT cpf AS d FROM a UNION ALL SELECT 'x'",
            "SELECT 'x' AS d UNION ALL SELECT cpf FROM b",
            "SELECT cpf AS d FROM a UNION SELECT 'x'",
            "SELECT cpf AS d FROM a INTERSECT SELECT 'x'",
            "SELECT cpf AS d FROM a EXCEPT SELECT 'x'",
            "SELECT cpf AS d FROM a UNION ALL (SELECT cpf FROM b UNION ALL SELECT cpf FROM c)",
        ],
    )
    def test_any_sensitive_branch_makes_the_position_sensitive(self, policy, sql):
        assert analyze(sql, policy) == (0,)

    def test_position_is_respected_across_branches(self, policy):
        sql = "SELECT id, cpf AS d FROM a UNION ALL SELECT id, nome FROM b"
        assert analyze(sql, policy) == (None, 0)

    def test_harmless_union(self, policy):
        assert analyze("SELECT nome FROM a UNION ALL SELECT nome FROM b", policy) == (None,)


class TestAmbiguity:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT concat(cpf, email) AS x FROM cliente",
            "SELECT cpf || email AS x FROM cliente",
            "SELECT CASE WHEN true THEN cpf ELSE email END AS x FROM cliente",
            "SELECT cpf FROM a UNION ALL SELECT email FROM b",
        ],
    )
    def test_two_different_rules_are_rejected(self, policy, sql):
        with pytest.raises(QueryRejected) as info:
            analyze(sql, policy)
        assert info.value.reason == AMBIGUOUS_SENSITIVE_EXPRESSION

    def test_two_columns_of_the_same_rule_are_not_ambiguous(self, policy):
        assert analyze("SELECT concat(cpf, nr_cpf) AS x FROM cliente", policy) == (0,)

    def test_the_reason_names_no_column(self, policy):
        with pytest.raises(QueryRejected) as info:
            analyze("SELECT concat(cpf, email) AS x FROM cliente", policy)
        assert "cpf" not in info.value.reason
        assert "email" not in info.value.reason


class TestWholeRowSerialisation:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT row_to_json(c) AS d FROM cliente c",
            "SELECT to_json(c) AS d FROM cliente c",
            "SELECT row_to_json(cliente) AS d FROM cliente",
        ],
    )
    def test_rejected(self, policy, sql):
        with pytest.raises(QueryRejected) as info:
            analyze(sql, policy)
        assert info.value.reason == WHOLE_ROW_SERIALIZATION

    def test_a_normal_column_of_the_same_name_is_not_confused(self, policy):
        """`SELECT c.cpf` qualifica: nao e referencia a linha inteira."""
        assert analyze("SELECT c.cpf FROM cliente c", policy) == (0,)


class TestNamesBehindAliases:
    """Um passo entre niveis: os nomes que CTEs e subqueries exportam."""

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT substr(d, 1, 11) AS x FROM (SELECT cpf AS d FROM cliente) t",
            "WITH t AS (SELECT cpf AS d FROM cliente) SELECT upper(d) AS x FROM t",
            "SELECT d FROM (SELECT cpf AS d FROM a UNION ALL SELECT 'y') t",
            "WITH x AS (SELECT cpf AS d FROM a UNION ALL SELECT 'y') SELECT d FROM x",
            "SELECT upper(e) AS x FROM (SELECT d AS e FROM (SELECT cpf AS d FROM t) a) b",
        ],
    )
    def test_exported_name_is_resolved(self, policy, sql):
        assert analyze(sql, policy) == (0,)

    def test_harmless_alias_is_not_over_masked(self, policy):
        sql = "SELECT upper(n) AS x FROM (SELECT nome AS n FROM cliente) t"
        assert analyze(sql, policy) == (None,)


class TestWildcards:
    def test_star_yields_a_single_unprovable_position(self, policy):
        """A contagem nao bate com o result set; o adapter ignora a analise."""
        assert analyze("SELECT * FROM cliente", policy) == (None,)

    def test_qualified_star(self, policy):
        assert analyze("SELECT c.* FROM cliente c", policy) == (None,)


class TestBounds:
    def test_deep_nesting_is_bounded(self, policy):
        sql = "SELECT 1 AS n"
        for _ in range(200):
            sql = f"SELECT * FROM ({sql}) t"
        started = time.perf_counter()
        analyze(sql, policy)
        assert time.perf_counter() - started < 2.0

    def test_the_depth_limit_gives_up_instead_of_guessing(self, policy):
        sql = "SELECT cpf AS d0 FROM cliente"
        for level in range(MAX_DEPTH + 4):
            sql = f"SELECT d{level} AS d{level + 1} FROM ({sql}) t{level}"
        # Alem do limite a analise desiste; a proveniencia segue sozinha.
        assert analyze(sql, policy) in {(0,), (None,)}
