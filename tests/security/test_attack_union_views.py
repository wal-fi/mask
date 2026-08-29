"""Classes de ataque: UNION e VIEWS.

Ver `docs/SECURITY-REVIEW.md` (F-02 e F-03).
"""

from __future__ import annotations

import psycopg
import pytest

from maskgw.gateway.models import ErrorCategory, GatewayError
from maskgw.masking.descriptor import ProvenanceKind
from tests.security.conftest import CPF, OUTRA, SCHEMA, TABLE, leaks

pytestmark = pytest.mark.integration


class TestUnionThatStaysMasked:
    """MASKED — o `output_name` sobrevive e ainda casa a regra."""

    def test_name_preserved_in_both_branches(self, gateway):
        sql = f"SELECT cpf FROM {TABLE} UNION ALL SELECT cpf FROM {OUTRA}"
        result = gateway.query(sql)
        assert not leaks(result)
        assert result.columns[0].masked is True

    def test_mixed_columns_still_masked_by_output_name(self, gateway):
        sql = f"SELECT cpf FROM {TABLE} UNION ALL SELECT email FROM {TABLE}"
        assert not leaks(gateway.query(sql))

    def test_select_star_union_keeps_per_column_names(self, gateway):
        sql = f"SELECT * FROM {OUTRA} UNION ALL SELECT * FROM {OUTRA}"
        result = gateway.query(sql)
        assert not leaks(result)
        assert [c.name for c in result.columns] == ["id", "cpf", "nome"]


class TestUnionBypass:
    """KNOWN LIMITATION — UNION apaga a origem; com alias, nada casa."""

    def test_union_has_no_provenance(self, gateway):
        sql = f"SELECT cpf FROM {TABLE} UNION ALL SELECT cpf FROM {OUTRA}"
        assert gateway.query(sql).columns[0].masked is True
        # A protecao veio do nome, nao da origem: com alias ela cai.

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
                "union aninhada",
                f"SELECT cpf AS d FROM {TABLE} UNION ALL "
                f"(SELECT cpf FROM {OUTRA} UNION ALL SELECT cpf FROM {OUTRA})",
            ),
            (
                "union com literal",
                f"SELECT cpf AS documento FROM {TABLE} UNION ALL SELECT 'x'",
            ),
        ],
    )
    def test_known_limitation_alias_over_union_leaks(self, gateway, attack, sql):
        result = gateway.query(sql)
        assert leaks(result), f"{attack}: fechou? atualizar SECURITY-REVIEW"
        assert result.columns[0].masked is False

    def test_union_is_the_cheapest_remaining_bypass(self, gateway):
        """Uma clausula a mais transforma coluna protegida em coluna aberta."""
        protegida = gateway.query(f"SELECT cpf AS documento FROM {TABLE} WHERE id = 1")
        aberta = gateway.query(
            f"SELECT cpf AS documento FROM {TABLE} WHERE id = 1 UNION ALL SELECT 'x'"
        )
        assert protegida.columns[0].masked is True
        assert aberta.columns[0].masked is False


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
        masked = application.gateway._adapter.execute_validated(
            f"SELECT documento FROM {SCHEMA}.v2 WHERE id = 1"
        )
        assert masked.columns[0].provenance_kind is ProvenanceKind.VIEW
        assert masked.columns[0].origin_name == "documento"
        assert masked.columns[0].origin_table == "v2"


class TestCombinedAttacks:
    def test_view_plus_union_plus_alias(self, gateway):
        """KNOWN LIMITATION — combinar nao piora nem melhora; ja vaza."""
        sql = (
            f"SELECT documento FROM {SCHEMA}.v2 WHERE id = 1 "
            f"UNION ALL SELECT cpf AS documento FROM {TABLE} WHERE id = 1"
        )
        assert leaks(gateway.query(sql))

    def test_expression_inside_cte_over_view(self, gateway):
        sql = f"WITH x AS (SELECT substr(cpf, 1, 11) AS d FROM {SCHEMA}.v1) SELECT d FROM x LIMIT 1"
        assert CPF in str(gateway.query(sql).rows)
