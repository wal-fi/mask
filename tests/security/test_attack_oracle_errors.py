"""Classes de ataque: ORACULO/INFERENCIA e VAZAMENTO POR ERRO.

Ver `docs/SECURITY-REVIEW.md` (F-07 e o veredito de erro).
"""

from __future__ import annotations

import logging
import traceback

import pytest

from maskgw.gateway.models import ErrorCategory, GatewayError
from tests.security.conftest import CPF, EMAIL, SCHEMA, SENHA, TABLE, dump

pytestmark = pytest.mark.integration


class TestInferenceOracle:
    """ACCEPTED RISK — o predicado nao passa pelo Masking Engine.

    A coluna sensivel nao aparece no result set, entao nao ha o que mascarar:
    o que vaza e a RESPOSTA do predicado. Controle de inferencia esta fora do
    escopo do MVP (`docs/FUTURE-HARDENING.md`), e estes testes medem o alcance.
    """

    def test_equality_confirms_existence(self, gateway):
        presente = gateway.query(f"SELECT count(*) AS n FROM {TABLE} WHERE cpf = '{CPF}'")
        ausente = gateway.query(f"SELECT count(*) AS n FROM {TABLE} WHERE cpf = '00000000000'")
        assert presente.rows[0][0] > 0
        assert ausente.rows[0][0] == 0

    def test_prefix_predicate_narrows_the_value(self, gateway):
        """Um digito por consulta: 11 consultas reconstroem o CPF."""
        digitos: list[str] = []
        for posicao in range(1, 12):
            for digito in "0123456789":
                prefixo = "".join(digitos) + digito
                sql = (
                    f"SELECT count(*) AS n FROM {TABLE} "
                    f"WHERE id = 1 AND substr(cpf, 1, {posicao}) = '{prefixo}'"
                )
                if gateway.query(sql).rows[0][0] > 0:
                    digitos.append(digito)
                    break
        assert "".join(digitos) == CPF, "reconstrucao por oraculo de prefixo"

    def test_binary_search_on_ordering(self, gateway):
        acima = gateway.query(f"SELECT count(*) AS n FROM {TABLE} WHERE cpf > '5'")
        abaixo = gateway.query(f"SELECT count(*) AS n FROM {TABLE} WHERE cpf < '5'")
        assert acima.rows[0][0] + abaixo.rows[0][0] > 0

    @pytest.mark.parametrize(
        ("attack", "sql"),
        [
            (
                "CASE booleano",
                f"SELECT CASE WHEN cpf = '{CPF}' THEN 1 ELSE 0 END AS b FROM {TABLE}",
            ),
            ("ORDER BY", f"SELECT id FROM {TABLE} ORDER BY cpf"),
            ("GROUP BY", f"SELECT count(*) AS n FROM {TABLE} GROUP BY cpf"),
            ("HAVING", f"SELECT count(*) AS n FROM {TABLE} GROUP BY cpf HAVING count(*) > 1"),
            ("LIKE", f"SELECT count(*) AS n FROM {TABLE} WHERE cpf LIKE '111%'"),
            ("LIMIT/OFFSET", f"SELECT id FROM {TABLE} ORDER BY cpf LIMIT 1 OFFSET 3"),
        ],
    )
    def test_oracle_shapes_are_allowed(self, gateway, attack, sql):
        assert gateway.query(sql).row_count >= 0, attack

    def test_the_row_limit_slows_but_does_not_stop_extraction(self, gateway):
        """`max_rows` limita a saida, nao o numero de consultas."""
        result = gateway.query(f"SELECT id FROM {TABLE} ORDER BY id")
        assert result.truncated is True
        assert result.row_count == 5


class TestErrorOracleIsBlocked:
    """BLOCKED — nenhuma mensagem do PostgreSQL alcanca o cliente."""

    @pytest.mark.parametrize(
        ("attack", "sql"),
        [
            ("cast invalido", f"SELECT cpf::integer AS d FROM {TABLE} WHERE id = 1"),
            ("divisao por zero", f"SELECT 1 / (length(cpf) - 11) AS d FROM {TABLE} WHERE id = 1"),
            ("regex invalida", f"SELECT regexp_replace(cpf, '([', 'x') AS d FROM {TABLE}"),
            ("cast uuid", f"SELECT cpf::uuid AS d FROM {TABLE} WHERE id = 1"),
            ("cast date", f"SELECT cpf::date AS d FROM {TABLE} WHERE id = 1"),
        ],
    )
    def test_postgres_message_never_reaches_the_client(self, gateway, attack, sql):
        with pytest.raises(GatewayError) as info:
            gateway.query(sql)
        message = str(info.value)
        assert CPF not in message, attack
        assert "invalid input syntax" not in message
        assert info.value.__cause__ is None
        assert info.value.__context__ is None

    def test_casts_that_do_not_fail_are_masked_as_expressions(self, gateway):
        """Nem todo cast falha; os que passam sao cobertos pela analise de AST.

        Um CPF so de digitos e JSON valido, entao `cpf::jsonb` NAO levanta.
        Ate a Fase 6 isso virava expressao comum e saia em claro.
        """
        result = gateway.query(f"SELECT cpf::jsonb AS d FROM {TABLE} WHERE id = 1")
        assert CPF not in dump(result)
        assert result.columns[0].masked is True

    def test_out_of_range_subscript_returns_null_not_an_error(self, gateway):
        result = gateway.query(f"SELECT (ARRAY[cpf])[999999999] AS d FROM {TABLE} LIMIT 1")
        assert result.rows[0][0] is None

    def test_function_raising_with_the_value_is_sanitized(self, gateway):
        """A funcao levanta com o proprio CPF na mensagem."""
        with pytest.raises(GatewayError) as info:
            gateway.query(f"SELECT {SCHEMA}.boom(cpf) AS d FROM {TABLE} WHERE id = 1")
        assert CPF not in str(info.value)
        assert "valor recebido" not in str(info.value)

    def test_error_category_is_all_the_client_learns(self, gateway):
        with pytest.raises(GatewayError) as info:
            gateway.query(f"SELECT cpf::integer AS d FROM {TABLE} WHERE id = 1")
        assert info.value.category is ErrorCategory.DATABASE_ERROR
        assert str(info.value) == "The database could not complete the query."

    def test_no_sensitive_value_reaches_the_audit_on_error(self, gateway, caplog):
        with caplog.at_level(logging.DEBUG):
            for sql in (
                f"SELECT cpf::integer AS d FROM {TABLE} WHERE id = 1",
                f"SELECT {SCHEMA}.boom(cpf) AS d FROM {TABLE} WHERE id = 1",
            ):
                with pytest.raises(GatewayError):
                    gateway.query(sql)
        rendered = " ".join(
            f"{r.getMessage()} {getattr(r, 'maskgw', '')} {r.exc_text or ''}"
            for r in caplog.records
        )
        for secret in (CPF, EMAIL, SENHA):
            assert secret not in rendered

    def test_traceback_render_is_clean(self, gateway):
        with pytest.raises(GatewayError) as info:
            gateway.query(f"SELECT cpf::integer AS d FROM {TABLE} WHERE id = 1")
        rendered = "".join(
            traceback.format_exception(type(info.value), info.value, info.value.__traceback__)
        )
        assert CPF not in rendered


class TestOtherColumnsAreProtected:
    """MASKED — email e senha seguem as suas proprias regras."""

    def test_email_and_password(self, gateway):
        result = gateway.query(f"SELECT email, senha FROM {TABLE} WHERE id = 1")
        assert EMAIL not in dump(result)
        assert SENHA not in dump(result)
        assert result.rows[0] == ["jo***@example.com", "[REDACTED]"]

    def test_password_via_expression_is_masked_too(self, gateway):
        """A correcao vale para qualquer regra, nao so para `cpf`."""
        result = gateway.query(f"SELECT senha || '' AS s FROM {TABLE} WHERE id = 1")
        assert SENHA not in dump(result)
        assert result.rows[0][0] == "[REDACTED]"
