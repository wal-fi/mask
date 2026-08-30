"""Classe de ataque: EXPRESSOES sobre coluna sensivel.

Era o bypass residual mais relevante do MVP. Quando o PostgreSQL informa
`ftable = 0` nao ha origem a resolver, e o matching recaia sobre o
`output_name` — que o atacante escolhe.

**F-01 estava ABERTO na Fase 6 e foi FECHADO na Fase 6.1.** A analise de AST
(`maskgw.sql.sensitivity`) prova a dependencia da coluna referenciada e aplica
a regra dela ao resultado da expressao. Ver `docs/SECURITY-REVIEW.md`.
"""

from __future__ import annotations

import base64

import pytest

from maskgw.gateway.models import ErrorCategory, GatewayError
from tests.security.conftest import CPF, TABLE, dump, leaks

pytestmark = pytest.mark.integration


class TestExpressionsAreNowMasked:
    """MASKED desde a Fase 6.1 — cada entrada era um bypass reproduzivel."""

    @pytest.mark.parametrize(
        ("attack", "sql"),
        [
            ("substr", f"SELECT substr(cpf, 1, 11) AS documento FROM {TABLE}"),
            ("concat", f"SELECT concat(cpf, '') AS documento FROM {TABLE}"),
            ("operador ||", f"SELECT cpf || '' AS documento FROM {TABLE}"),
            ("upper", f"SELECT upper(cpf) AS documento FROM {TABLE}"),
            ("lower", f"SELECT lower(cpf) AS documento FROM {TABLE}"),
            ("lpad", f"SELECT lpad(cpf, 11, '0') AS documento FROM {TABLE}"),
            ("trim", f"SELECT trim(cpf) AS documento FROM {TABLE}"),
            ("coalesce", f"SELECT coalesce(cpf, '') AS documento FROM {TABLE}"),
            ("CASE", f"SELECT CASE WHEN true THEN cpf END AS documento FROM {TABLE}"),
            ("min", f"SELECT min(cpf) AS documento FROM {TABLE}"),
            ("max", f"SELECT max(cpf) AS documento FROM {TABLE}"),
            ("array", f"SELECT ARRAY[cpf] AS documento FROM {TABLE}"),
            ("array_agg", f"SELECT array_agg(cpf) AS documento FROM {TABLE}"),
            ("json_agg", f"SELECT json_agg(cpf) AS documento FROM {TABLE}"),
            ("string_agg", f"SELECT string_agg(cpf, ',') AS documento FROM {TABLE}"),
            ("to_json", f"SELECT to_json(cpf) AS documento FROM {TABLE}"),
            ("cast varchar", f"SELECT cpf::varchar AS documento FROM {TABLE}"),
            ("cast char", f"SELECT cpf::char(11) AS documento FROM {TABLE}"),
            ("cast jsonb", f"SELECT cpf::jsonb AS documento FROM {TABLE}"),
            ("format", f"SELECT format('%s', cpf) AS documento FROM {TABLE}"),
            ("qualificado", f"SELECT substr(c.cpf, 1, 11) AS d FROM {TABLE} c"),
            ("aninhado", f"SELECT upper(substr(trim(cpf), 1, 11)) AS d FROM {TABLE}"),
        ],
    )
    def test_masked(self, gateway, attack, sql):
        result = gateway.query(f"{sql} WHERE id = 1")
        assert not leaks(result), attack
        assert result.columns[0].masked is True

    def test_scalar_subquery_is_masked(self, gateway):
        result = gateway.query(f"SELECT (SELECT cpf FROM {TABLE} LIMIT 1) AS documento")
        assert not leaks(result)
        assert result.columns[0].masked is True

    def test_the_transformer_is_the_one_from_the_matched_rule(self, gateway):
        """A expressao recebe a regra da coluna que ela referencia."""
        direto = gateway.query(f"SELECT cpf FROM {TABLE} WHERE id = 1")
        derivado = gateway.query(f"SELECT cpf::varchar AS d FROM {TABLE} WHERE id = 1")
        assert len(derivado.rows[0][0]) == len(direto.rows[0][0]) == 64


class TestReversibleEncodingsAreMasked:
    """MASKED — codificacao nunca foi protecao, e agora nao passa mais."""

    @pytest.mark.parametrize(
        ("attack", "sql", "encoded"),
        [
            ("reverse", "reverse(cpf)", CPF[::-1]),
            ("base64", "encode(convert_to(cpf, 'UTF8'), 'base64')", "MTExMjIyMzMzNDQ="),
            ("hex", "encode(convert_to(cpf, 'UTF8'), 'hex')", "3131313232323333333434"),
        ],
    )
    def test_encoded_form_never_reaches_the_client(self, gateway, attack, sql, encoded):
        result = gateway.query(f"SELECT {sql} AS documento FROM {TABLE} WHERE id = 1")
        rendered = dump(result)
        assert CPF not in rendered, attack
        assert encoded not in rendered, attack
        assert result.columns[0].masked is True

    def test_base64_would_have_been_trivially_reversible(self):
        assert base64.b64decode("MTExMjIyMzMzNDQ=").decode() == CPF


class TestExpressionsThatAreRejected:
    """BLOCKED — nao ha transformer unico comprovavel (D-043, D-044)."""

    @pytest.mark.parametrize(
        ("attack", "sql"),
        [
            ("row_to_json", f"SELECT row_to_json(t) AS d FROM {TABLE} t"),
            ("to_json da linha", f"SELECT to_json(t) AS d FROM {TABLE} t"),
            ("row_to_json aninhado", f"SELECT to_json(row_to_json(t)) AS d FROM {TABLE} t"),
        ],
    )
    def test_whole_row_serialisation_is_rejected(self, gateway, attack, sql):
        with pytest.raises(GatewayError) as info:
            gateway.query(sql)
        assert info.value.category is ErrorCategory.QUERY_REJECTED, attack

    @pytest.mark.parametrize(
        ("attack", "sql"),
        [
            ("concat cpf+email", f"SELECT concat(cpf, email) AS x FROM {TABLE}"),
            ("cpf || email", f"SELECT cpf || email AS x FROM {TABLE}"),
            (
                "CASE com duas regras",
                f"SELECT CASE WHEN true THEN cpf ELSE email END AS x FROM {TABLE}",
            ),
            ("cpf + senha", f"SELECT concat(cpf, senha) AS x FROM {TABLE}"),
        ],
    )
    def test_ambiguous_expression_is_rejected(self, gateway, attack, sql):
        """Duas classes sensiveis com transformers diferentes: recusar."""
        with pytest.raises(GatewayError) as info:
            gateway.query(sql)
        assert info.value.category is ErrorCategory.QUERY_REJECTED, attack

    def test_the_rejection_message_names_nothing(self, gateway):
        with pytest.raises(GatewayError) as info:
            gateway.query(f"SELECT concat(cpf, email) AS x FROM {TABLE}")
        message = str(info.value)
        assert "cpf" not in message
        assert "email" not in message
        assert CPF not in message

    def test_two_references_to_the_same_rule_are_not_ambiguous(self, gateway):
        """`cpf` e `cliente_cpf` casam a MESMA regra: nao ha conflito."""
        result = gateway.query(f"SELECT concat(cpf, cpf) AS x FROM {TABLE} WHERE id = 1")
        assert not leaks(result)
        assert result.columns[0].masked is True


class TestExpressionsThatStayOriginal:
    """ALLOW — a analise nao pode virar over-masking indiscriminado."""

    def test_expression_over_an_excepted_column(self, gateway):
        """A analise respeita a exception sobre o nome REFERENCIADO."""
        result = gateway.query(f"SELECT substr(tipo_cpf, 1, 3) AS d FROM {TABLE} WHERE id = 1")
        assert result.rows[0][0] == "fis"
        assert result.columns[0].masked is False

    def test_expression_over_a_harmless_column(self, gateway):
        result = gateway.query(f"SELECT upper(nome) AS d FROM {TABLE} WHERE id = 1")
        assert result.rows[0][0] == "JOAO"
        assert result.columns[0].masked is False

    def test_literal_expression(self, gateway):
        assert gateway.query("SELECT upper('abc') AS d").rows[0][0] == "ABC"

    def test_aggregate_over_a_harmless_column(self, gateway):
        assert gateway.query(f"SELECT count(*) AS n FROM {TABLE}").rows[0][0] == 60


class TestExpressionsThatStayMasked:
    """MASKED — a proveniencia do PostgreSQL ja cobria estes."""

    @pytest.mark.parametrize(
        ("attack", "sql"),
        [
            ("cast text", f"SELECT cpf::text AS documento FROM {TABLE}"),
            ("cast AS text", f"SELECT cast(cpf AS text) AS documento FROM {TABLE}"),
            ("alias simples", f"SELECT cpf AS documento FROM {TABLE}"),
            ("alias em subquery", f"SELECT d FROM (SELECT cpf AS d FROM {TABLE}) x"),
            ("alias em CTE", f"WITH x AS (SELECT cpf AS d FROM {TABLE}) SELECT d FROM x"),
        ],
    )
    def test_masked(self, gateway, attack, sql):
        result = gateway.query(sql)
        assert not leaks(result), attack
        assert result.columns[0].masked is True

    def test_both_casts_are_masked_now(self, gateway):
        """`::text` pela proveniencia, `::varchar` pela analise de AST."""
        preservado = gateway.query(f"SELECT cpf::text AS d FROM {TABLE} WHERE id = 1")
        derivado = gateway.query(f"SELECT cpf::varchar AS d FROM {TABLE} WHERE id = 1")
        assert preservado.columns[0].masked is True
        assert derivado.columns[0].masked is True
        assert preservado.rows[0][0] == derivado.rows[0][0], "mesma regra, mesma saida"


class TestNamesHiddenBehindAliases:
    """MASKED — os nomes exportados por CTE e subquery sao resolvidos (D-046).

    Sem este passo, um alias interno esconderia `cpf` da analise externa. E o
    unico ponto em que a analise atravessa niveis, e ela casa por nome, sem
    resolver escopo.
    """

    @pytest.mark.parametrize(
        ("attack", "sql"),
        [
            (
                "expressao sobre alias de subquery",
                f"SELECT substr(d, 1, 11) AS x FROM (SELECT cpf AS d FROM {TABLE}) t",
            ),
            (
                "expressao sobre alias de CTE",
                f"WITH t AS (SELECT cpf AS d FROM {TABLE}) SELECT upper(d) AS x FROM t",
            ),
            (
                "dois niveis de alias",
                f"SELECT upper(e) AS x FROM (SELECT d AS e FROM "
                f"(SELECT cpf AS d FROM {TABLE}) a) b",
            ),
        ],
    )
    def test_masked(self, gateway, attack, sql):
        result = gateway.query(f"{sql} LIMIT 1")
        assert not leaks(result), f"{attack}: reabriu o bypass"
        assert result.columns[0].masked is True

    def test_the_same_query_without_the_expression_is_masked(self, gateway):
        """A proveniencia sozinha ja cobria o alias de subquery."""
        sql = f"SELECT d FROM (SELECT cpf AS d FROM {TABLE}) t LIMIT 1"
        assert not leaks(gateway.query(sql))

    def test_a_harmless_alias_is_not_over_masked(self, gateway):
        sql = f"SELECT upper(n) AS x FROM (SELECT nome AS n FROM {TABLE}) t LIMIT 1"
        assert gateway.query(sql).columns[0].masked is False


class TestExpressionsBlockedByPolicy:
    """BLOCKED — a politica de funcoes barra antes de qualquer dado."""

    @pytest.mark.parametrize(
        "sql",
        [
            f"SELECT pg_read_file('/etc/passwd') AS d FROM {TABLE}",
            f"SELECT query_to_xml('SELECT cpf FROM {TABLE}', true, true, '') AS d",
            f"SELECT dblink('host=x', 'SELECT cpf FROM {TABLE}') AS d",
        ],
    )
    def test_blocked(self, gateway, sql):
        with pytest.raises(GatewayError) as info:
            gateway.query(sql)
        assert info.value.category is ErrorCategory.QUERY_REJECTED
