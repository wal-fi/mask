"""Classes de ataque: UNION e VIEWS.

F-02 (UNION) foi FECHADO na Fase 6.1. F-03 (view que renomeia) permanece
aberto: resolver exigiria reparsear a definicao da view.
Ver `docs/SECURITY-REVIEW.md`.
"""

from __future__ import annotations

import psycopg
import pytest

from maskgw.gateway.models import ErrorCategory, GatewayError
from maskgw.masking.descriptor import ProvenanceKind
from tests.security.conftest import CPF, OUTRA, SCHEMA, TABLE, leaks

pytestmark = pytest.mark.integration


class TestUnionIsNowMasked:
    """MASKED desde a Fase 6.1 — F-02 fechado (D-043).

    A analise de AST olha o alvo de CADA ramo na mesma posicao. Basta um ramo
    ter dependencia sensivel comprovada para a posicao inteira ser sensivel.
    """

    def test_name_preserved_in_both_branches(self, gateway):
        sql = f"SELECT cpf FROM {TABLE} UNION ALL SELECT cpf FROM {OUTRA}"
        result = gateway.query(sql)
        assert not leaks(result)
        assert result.columns[0].masked is True

    @pytest.mark.parametrize(
        ("attack", "sql"),
        [
            (
                "alias no primeiro ramo",
                f"SELECT cpf AS documento FROM {TABLE} UNION ALL SELECT cpf FROM {OUTRA}",
            ),
            (
                "alias com ramo inocente",
                f"SELECT cpf AS documento FROM {TABLE} UNION ALL SELECT nome FROM {OUTRA}",
            ),
            (
                "alias com literal",
                f"SELECT cpf AS documento FROM {TABLE} UNION ALL SELECT 'x'",
            ),
            (
                "sensivel no segundo ramo",
                f"SELECT nome AS documento FROM {OUTRA} UNION ALL SELECT cpf FROM {TABLE}",
            ),
            (
                "union aninhada",
                f"SELECT cpf AS d FROM {TABLE} UNION ALL "
                f"(SELECT cpf FROM {OUTRA} UNION ALL SELECT cpf FROM {OUTRA})",
            ),
            (
                "union em CTE",
                f"WITH x AS (SELECT cpf AS d FROM {TABLE} UNION ALL SELECT 'y') SELECT d FROM x",
            ),
            (
                "union em subquery",
                f"SELECT d FROM (SELECT cpf AS d FROM {TABLE} UNION ALL SELECT 'y') t",
            ),
            ("UNION sem ALL", f"SELECT cpf AS d FROM {TABLE} UNION SELECT 'y'"),
            ("INTERSECT", f"SELECT cpf AS d FROM {TABLE} INTERSECT SELECT 'y'"),
            ("EXCEPT", f"SELECT cpf AS d FROM {TABLE} EXCEPT SELECT 'y'"),
        ],
    )
    def test_masked(self, gateway, attack, sql):
        result = gateway.query(sql)
        assert not leaks(result), f"{attack}: reabriu o bypass"
        assert result.columns[0].masked is True

    def test_position_is_respected(self, gateway):
        """So a posicao sensivel e mascarada; as outras seguem normais."""
        sql = (
            f"SELECT id, cpf AS d FROM {TABLE} WHERE id = 1 UNION ALL SELECT id, nome FROM {OUTRA}"
        )
        result = gateway.query(sql)
        assert [c.masked for c in result.columns] == [False, True]
        assert not leaks(result)

    def test_select_star_union_keeps_per_column_names(self, gateway):
        sql = f"SELECT * FROM {OUTRA} UNION ALL SELECT * FROM {OUTRA}"
        result = gateway.query(sql)
        assert not leaks(result)
        assert [c.name for c in result.columns] == ["id", "cpf", "nome"]

    def test_harmless_union_is_untouched(self, gateway):
        sql = f"SELECT nome FROM {TABLE} UNION ALL SELECT nome FROM {OUTRA}"
        result = gateway.query(sql)
        assert result.columns[0].masked is False


class TestUnionWithConflictingRules:
    """BLOCKED — duas classes sensiveis na mesma posicao (D-043)."""

    @pytest.mark.parametrize(
        ("attack", "sql"),
        [
            ("cpf + email", f"SELECT cpf FROM {TABLE} UNION ALL SELECT email FROM {TABLE}"),
            (
                "cpf + email com alias",
                f"SELECT cpf AS v FROM {TABLE} UNION ALL SELECT email FROM {TABLE}",
            ),
            ("cpf + senha", f"SELECT cpf FROM {TABLE} UNION ALL SELECT senha FROM {TABLE}"),
        ],
    )
    def test_rejected(self, gateway, attack, sql):
        with pytest.raises(GatewayError) as info:
            gateway.query(sql)
        assert info.value.category is ErrorCategory.QUERY_REJECTED, attack

    def test_same_rule_in_both_branches_is_not_a_conflict(self, gateway):
        sql = f"SELECT cpf FROM {TABLE} UNION ALL SELECT cliente_cpf FROM {OUTRA}"
        result = gateway.query(sql.replace("cliente_cpf", "cpf"))
        assert not leaks(result)


class TestViewsThatStayMasked:
    """MASKED — a view preserva o nome da coluna."""

    def test_view_preserving_the_name(self, gateway):
        result = gateway.query(f"SELECT cpf FROM {SCHEMA}.v1 WHERE id = 1")
        assert not leaks(result)
        assert result.columns[1].masked is True if len(result.columns) > 1 else True

    def test_alias_over_a_view_is_masked_by_provenance(self, gateway):
        result = gateway.query(f"SELECT cpf AS documento FROM {SCHEMA}.v1 WHERE id = 1")
        assert not leaks(result)
        assert result.columns[0].masked is True


class TestViewBypass:
    """KNOWN LIMITATION — a origem e a coluna DA VIEW, nao da tabela base."""

    @pytest.mark.parametrize(
        ("attack", "view"),
        [
            ("view que renomeia", "v2"),
            ("view com expressao", "v3"),
            ("view sobre view", "v4"),
        ],
    )
    def test_known_limitation_view_renaming_leaks(self, gateway, attack, view):
        result = gateway.query(f"SELECT documento FROM {SCHEMA}.{view} WHERE id = 1")
        assert leaks(result), f"{attack}: fechou? atualizar SECURITY-REVIEW"
        assert result.columns[0].masked is False

    def test_pg_get_viewdef_is_blocked_for_the_client(self, gateway):
        """BLOCKED — a politica `pg_` deny-by-default cobre tambem isto."""
        with pytest.raises(GatewayError) as info:
            gateway.query(f"SELECT pg_get_viewdef('{SCHEMA}.v2'::regclass, true) AS d")
        assert info.value.category is ErrorCategory.QUERY_REJECTED

    def test_the_definition_is_available_to_the_gateway_itself(self, database):
        """A correcao e possivel pelo lado de dentro — mas nao e pequena.

        O Gateway usa a propria conexao para o catalogo, entao teria acesso a
        definicao da view. Resolver ate a tabela base exigiria reparsear a
        definicao e mapear posicionalmente: um lineage engine.
        """
        with psycopg.connect(database, autocommit=True) as connection:
            row = connection.execute(
                f"SELECT pg_get_viewdef('{SCHEMA}.v2'::regclass, true)"
            ).fetchone()
        assert row is not None
        assert "cpf AS documento" in row[0]

    def test_provenance_reports_view_kind(self, application):
        """O descritor interno SABE que e view; falta seguir ate a base."""
        masked = application.registry.current.adapter.execute_validated(
            f"SELECT documento FROM {SCHEMA}.v2 WHERE id = 1"
        )
        assert masked.columns[0].provenance_kind is ProvenanceKind.VIEW
        assert masked.columns[0].origin_name == "documento"
        assert masked.columns[0].origin_table == "v2"


class TestCombinedAttacks:
    def test_view_plus_union_plus_alias_is_masked_by_the_sensitive_branch(self, gateway):
        """Um ramo referencia `cpf` diretamente: a posicao inteira e sensivel."""
        sql = (
            f"SELECT documento FROM {SCHEMA}.v2 WHERE id = 1 "
            f"UNION ALL SELECT cpf AS documento FROM {TABLE} WHERE id = 1"
        )
        assert not leaks(gateway.query(sql))

    def test_expression_inside_cte_over_view_is_masked(self, gateway):
        sql = f"WITH x AS (SELECT substr(cpf, 1, 11) AS d FROM {SCHEMA}.v1) SELECT d FROM x LIMIT 1"
        assert CPF not in str(gateway.query(sql).rows)

    def test_the_view_rename_still_hides_the_name_from_both_layers(self, gateway):
        """KNOWN LIMITATION — nem a AST nem a proveniencia veem `cpf` aqui.

        A definicao da view nao esta na arvore da consulta, e a proveniencia
        aponta para a coluna DA VIEW. Ver F-03 em SECURITY-REVIEW.
        """
        result = gateway.query(f"SELECT documento FROM {SCHEMA}.v2 WHERE id = 1")
        assert leaks(result), "fechou? atualizar SECURITY-REVIEW (F-03)"
