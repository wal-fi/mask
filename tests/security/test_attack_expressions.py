"""Classe de ataque: EXPRESSOES sobre coluna sensivel.

O bypass residual mais relevante do MVP. Quando o PostgreSQL informa
`ftable = 0`, nao ha origem a resolver, e o matching recai sobre o
`output_name` — que o atacante escolhe.

Vereditos medidos na Fase 6. Ver `docs/SECURITY-REVIEW.md` (F-01).
"""

from __future__ import annotations

import base64

import pytest

from maskgw.gateway.models import ErrorCategory, GatewayError
from tests.security.conftest import CPF, TABLE, dump, first_value, leaks

pytestmark = pytest.mark.integration


class TestExpressionsThatLeakTheValueVerbatim:
    """KNOWN LIMITATION — o CPF sai em claro.

    Cada entrada aqui e um bypass reproduzivel, fixado para nao passar
    despercebido. Se um hardening futuro fechar algum, este teste quebra.
    """

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
            ("to_json", f"SELECT to_json(cpf) AS documento FROM {TABLE}"),
            ("cast varchar", f"SELECT cpf::varchar AS documento FROM {TABLE}"),
            ("cast char", f"SELECT cpf::char(11) AS documento FROM {TABLE}"),
            ("format", f"SELECT format('%s', cpf) AS documento FROM {TABLE}"),
        ],
    )
    def test_known_limitation_value_reaches_the_client(self, gateway, attack, sql):
        result = gateway.query(f"{sql} WHERE id = 1")
        assert leaks(result), f"{attack}: fechou? atualizar SECURITY-REVIEW"
        assert result.columns[0].masked is False

    def test_scalar_subquery_leaks(self, gateway):
        """KNOWN LIMITATION — subquery escalar tambem perde a origem."""
        result = gateway.query(f"SELECT (SELECT cpf FROM {TABLE} LIMIT 1) AS documento")
        assert leaks(result)
        assert result.columns[0].masked is False

    def test_row_to_json_dumps_the_whole_row(self, gateway):
        """KNOWN LIMITATION — o pior caso: a linha inteira, sem masking."""
        result = gateway.query(f"SELECT row_to_json(t) AS d FROM {TABLE} t WHERE id = 1")
        assert leaks(result)
        assert "joao@example.com" in dump(result)


class TestExpressionsThatLeakAReversibleForm:
    """KNOWN LIMITATION — nao e o valor literal, mas e reversivel.

    'Transformado por SQL' nao significa seguro: base64, hex e reverse sao
    codificacoes, nao protecao.
    """

    @pytest.mark.parametrize(
        ("attack", "sql", "expected"),
        [
            ("reverse", "reverse(cpf)", CPF[::-1]),
            ("base64", "encode(convert_to(cpf, 'UTF8'), 'base64')", "MTExMjIyMzMzNDQ="),
            ("hex", "encode(convert_to(cpf, 'UTF8'), 'hex')", "3131313232323333333434"),
        ],
    )
    def test_known_limitation_encoded_value_reaches_the_client(
        self, gateway, attack, sql, expected
    ):
        result = gateway.query(f"SELECT {sql} AS documento FROM {TABLE} WHERE id = 1")
        assert first_value(result) == expected, attack
        assert result.columns[0].masked is False

    def test_base64_is_trivially_reversible(self):
        assert base64.b64decode("MTExMjIyMzMzNDQ=").decode() == CPF


class TestExpressionsThatStayMasked:
    """MASKED — o PostgreSQL preserva a origem e a protecao segue valendo."""

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

    def test_cast_to_text_is_a_no_op_so_provenance_survives(self, gateway):
        """Assimetria medida: `::text` preserva a origem, `::varchar` nao."""
        preservado = gateway.query(f"SELECT cpf::text AS d FROM {TABLE} WHERE id = 1")
        perdido = gateway.query(f"SELECT cpf::varchar AS d FROM {TABLE} WHERE id = 1")
        assert preservado.columns[0].masked is True
        assert perdido.columns[0].masked is False


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
