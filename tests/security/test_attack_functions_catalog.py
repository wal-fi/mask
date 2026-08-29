"""Classes de ataque: FUNCOES DE USUARIO e CATALOGO.

Ver `docs/SECURITY-REVIEW.md` (F-04, F-05, F-06).
"""

from __future__ import annotations

from typing import Any

import psycopg
import pytest

from maskgw.gateway.models import ErrorCategory, GatewayError
from tests.security.conftest import CPF, SCHEMA, TABLE, dump, leaks

pytestmark = pytest.mark.integration


def rejected(gateway: Any, sql: str) -> ErrorCategory:
    with pytest.raises(GatewayError) as info:
        gateway.query(sql)
    return info.value.category


class TestUserFunctionsThatLeak:
    """KNOWN LIMITATION — funcao de usuario com nome inocente le a coluna.

    Pre-condicao: a funcao ja existe no banco. O atacante NAO consegue cria-la
    (CREATE e recusado pelo validator e pela transacao read-only), mas tambem
    nao precisa: basta uma que ja esteja la.
    """

    def test_sql_function_returning_a_sensitive_column(self, gateway):
        result = gateway.query(f"SELECT {SCHEMA}.safe_lookup()")
        assert leaks(result)
        assert result.columns[0].name == "safe_lookup"
        assert result.columns[0].masked is False

    def test_security_definer_function(self, gateway):
        """SECURITY DEFINER roda com o privilegio do dono da funcao."""
        result = gateway.query(f"SELECT {SCHEMA}.definer_lookup()")
        assert leaks(result)
        assert result.columns[0].masked is False

    def test_security_definer_with_alias(self, gateway):
        result = gateway.query(f"SELECT {SCHEMA}.definer_lookup() AS documento")
        assert leaks(result)

    def test_dynamic_sql_function_is_a_full_read_bypass(self, gateway):
        """A funcao executa SQL arbitraria fora do validator."""
        result = gateway.query(f"SELECT {SCHEMA}.dyn('SELECT cpf FROM {TABLE} LIMIT 1') AS d")
        assert leaks(result)

    def test_the_masking_rule_would_still_apply_if_the_name_matched(self, gateway):
        """A protecao existe: ela depende do nome da coluna de saida."""
        result = gateway.query(f"SELECT {SCHEMA}.safe_lookup() AS cpf")
        assert not leaks(result)
        assert result.columns[0].masked is True


class TestUserFunctionsBlockedByPrivilege:
    """BLOCKED — a transacao read-only barra o efeito colateral de escrita."""

    def test_function_that_writes_is_rejected(self, gateway):
        assert rejected(gateway, f"SELECT {SCHEMA}.writer()") is ErrorCategory.DATABASE_ERROR

    def test_dynamic_sql_that_writes_is_rejected(self, gateway):
        sql = f"SELECT {SCHEMA}.dyn('INSERT INTO {TABLE} (id) VALUES (98)')"
        assert rejected(gateway, sql) is ErrorCategory.DATABASE_ERROR

    def test_the_table_is_intact(self, gateway, database):
        for sql in (f"SELECT {SCHEMA}.writer()", f"SELECT {SCHEMA}.dyn('DELETE FROM {TABLE}')"):
            with pytest.raises(GatewayError):
                gateway.query(sql)
        with psycopg.connect(database, autocommit=True) as control:
            row = control.execute(f"SELECT count(*) FROM {TABLE}").fetchone()
            assert row is not None
            assert row[0] == 60


class TestStatisticsRelationsAreBlocked:
    """BLOCKED — hardening da Fase 6 (D-039).

    `pg_statistic` guarda valores REAIS das colunas, e `pg_stats` os expoe.
    Uma consulta devolvia CPFs verdadeiros em claro.
    """

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT most_common_vals FROM pg_stats",
            "SELECT histogram_bounds FROM pg_stats",
            "SELECT * FROM pg_catalog.pg_stats",
            "SELECT * FROM PG_STATS",
            'SELECT * FROM "pg_stats"',
            "SELECT stavalues1 FROM pg_statistic",
            "SELECT * FROM pg_stats_ext",
            "WITH x AS (SELECT most_common_vals FROM pg_stats) SELECT * FROM x",
            "SELECT 1 FROM (SELECT * FROM pg_stats) y",
            "SELECT 1 FROM pg_class UNION ALL SELECT 1 FROM pg_stats",
            "SELECT (SELECT count(*) FROM pg_stats) AS n",
        ],
    )
    def test_blocked(self, gateway, sql):
        assert rejected(gateway, sql) is ErrorCategory.QUERY_REJECTED

    def test_the_leak_this_closes(self, database):
        """Prova que o dado esta la: sem o bloqueio, sairia em claro."""
        with psycopg.connect(database, autocommit=True) as control:
            row = control.execute(
                "SELECT coalesce(most_common_vals::text, '') "
                "    || coalesce(histogram_bounds::text, '') "
                "FROM pg_stats "
                f"WHERE schemaname = '{SCHEMA}' AND tablename = 'cliente' "
                "  AND attname = 'cpf'"
            ).fetchone()
        assert row is not None, "sem estatisticas: ANALYZE nao rodou"
        assert CPF in row[0], "o CPF real esta nas estatisticas do PostgreSQL"


class TestCatalogReconnaissance:
    """ACCEPTED RISK — metadata continua legivel, e isso e deliberado."""

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT relname FROM pg_class LIMIT 3",
            "SELECT attname FROM pg_attribute LIMIT 3",
            "SELECT proname FROM pg_proc LIMIT 3",
            "SELECT rolname FROM pg_roles LIMIT 3",
            "SELECT column_name FROM information_schema.columns LIMIT 3",
            "SELECT table_name FROM information_schema.tables LIMIT 3",
        ],
    )
    def test_metadata_is_readable(self, gateway, sql):
        assert gateway.query(sql).row_count > 0

    def test_view_definitions_are_readable(self, gateway):
        """Revela o mapa das views, inclusive quais renomeiam colunas."""
        result = gateway.query(f"SELECT definition FROM pg_views WHERE schemaname = '{SCHEMA}'")
        assert "cpf" in dump(result)

    def test_operational_settings_are_readable(self, gateway):
        result = gateway.query("SELECT setting FROM pg_settings WHERE name = 'data_directory'")
        assert result.row_count == 1

    def test_catalog_does_not_expose_column_values(self, gateway):
        """A distincao que importa: metadata sim, amostras de dado nao."""
        result = gateway.query(
            "SELECT attname FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid "
            "WHERE c.relname = 'cliente' AND a.attnum > 0"
        )
        assert not leaks(result)
