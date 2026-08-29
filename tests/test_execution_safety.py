"""Seguranca de execucao contra PostgreSQL real (Fase 4).

Aqui se prova o que o validator sozinho nao prova:

- a escrita e barrada pelo PRIVILEGIO, com o validator deliberadamente
  contornado (os testes chamam `execute`, a porta interna sem validacao);
- o `statement_timeout` e do PostgreSQL, nao um timer em Python;
- `max_rows` e respeitado no consumo do result set, e a linha N+1 nunca sai;
- a capability de proveniencia falha alto quando a role nao le o catalogo.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from maskgw.config import load_gateway_config_text
from maskgw.config.gateway import DatabaseSettings
from maskgw.db.capabilities import check_provenance_capability
from maskgw.db.postgres import PostgresAdapter
from maskgw.errors import (
    CapabilityError,
    DatabaseError,
    InvalidQuery,
    QueryRejected,
    QueryTimeout,
)
from maskgw.masking.engine import MaskingEngine

pytestmark = pytest.mark.integration

SCHEMA = "maskgw_fase4"
TABLE = f"{SCHEMA}.cliente"
CPF = "11122233344"

CONFIG = """
masking:
  - match: cpf
    transformer: md5
"""

DDL = f"""
DROP SCHEMA IF EXISTS {SCHEMA} CASCADE;
CREATE SCHEMA {SCHEMA};
CREATE TABLE {TABLE} (id integer, cpf text);
INSERT INTO {TABLE}
SELECT i, lpad(i::text, 11, '0') FROM generate_series(1, 50) AS i;
"""


@pytest.fixture
def database(dsn: str) -> Iterator[str]:
    with psycopg.connect(dsn, autocommit=True) as setup:
        setup.execute(DDL)
    yield dsn
    with psycopg.connect(dsn, autocommit=True) as teardown:
        teardown.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")


@pytest.fixture
def engine(secrets):
    return MaskingEngine(load_gateway_config_text(CONFIG, secrets=secrets).masking)


@pytest.fixture
def adapter_factory(database, engine):
    created: list[PostgresAdapter] = []

    def _build(
        *, timeout_ms: int = 30_000, max_rows: int = 1_000, batch_size: int = 500
    ) -> PostgresAdapter:
        adapter = PostgresAdapter(
            database,
            engine,
            settings=DatabaseSettings(statement_timeout_ms=timeout_ms, max_rows=max_rows),
            batch_size=batch_size,
        )
        adapter.connect()
        created.append(adapter)
        return adapter

    yield _build
    for adapter in created:
        adapter.close()


@pytest.fixture
def adapter(adapter_factory):
    return adapter_factory()


class TestReadOnlyIsEnforcedByPostgres:
    """Defesa em profundidade: o validator e CONTORNADO de proposito.

    `execute` nao valida. Se o PostgreSQL nao barrasse, estas escritas
    aconteceriam — e a suite acusaria.
    """

    @pytest.mark.parametrize(
        "sql",
        [
            f"INSERT INTO {TABLE} VALUES (999, 'x')",
            f"UPDATE {TABLE} SET cpf = 'x'",
            f"DELETE FROM {TABLE}",
            f"CREATE TABLE {SCHEMA}.nova (a int)",
            f"DROP TABLE {TABLE}",
            f"TRUNCATE {TABLE}",
            f"ALTER TABLE {TABLE} ADD COLUMN novo int",
            f"CREATE INDEX ON {TABLE} (id)",
            f"SELECT * INTO {SCHEMA}.copia FROM {TABLE}",
            f"WITH x AS (DELETE FROM {TABLE} RETURNING *) SELECT * FROM x",
        ],
    )
    def test_write_is_rejected_even_bypassing_the_validator(self, adapter, sql):
        with pytest.raises(DatabaseError) as info:
            adapter.execute(sql)
        # 25006 read_only_sql_transaction -> classe 25.
        assert "transacao" in str(info.value)

    def test_the_table_is_intact_after_every_attempt(self, adapter, database):
        for sql in (f"DELETE FROM {TABLE}", f"UPDATE {TABLE} SET cpf = 'x'"):
            with pytest.raises(DatabaseError):
                adapter.execute(sql)
        with psycopg.connect(database, autocommit=True) as control:
            count = control.execute(f"SELECT count(*) FROM {TABLE}").fetchone()
            assert count is not None
            assert count[0] == 50

    def test_the_session_reports_read_only(self, adapter):
        result = adapter.execute("SELECT current_setting('transaction_read_only') AS estado")
        assert result.rows == (("on",),)

    def test_the_connection_survives_a_rejected_write(self, adapter):
        with pytest.raises(DatabaseError):
            adapter.execute(f"DELETE FROM {TABLE}")
        assert adapter.execute(f"SELECT count(*) FROM {TABLE} WHERE false").rows == ((0,),)

    def test_validator_rejects_before_the_database_sees_it(self, adapter):
        """A porta validada nem chega ao banco."""
        with pytest.raises(QueryRejected):
            adapter.execute_validated(f"DELETE FROM {TABLE}")


class TestSessionLimitsAreApplied:
    def test_read_only_is_on(self, adapter):
        result = adapter.execute(
            "SELECT setting FROM pg_settings WHERE name = 'default_transaction_read_only'"
        )
        assert result.rows == (("on",),)

    def test_statement_timeout_is_the_configured_value(self, adapter_factory):
        adapter = adapter_factory(timeout_ms=4321)
        result = adapter.execute("SELECT setting FROM pg_settings WHERE name = 'statement_timeout'")
        assert result.rows == (("4321",),)

    def test_a_conflicting_dsn_option_does_not_win(self, database, engine):
        """O `-c` do Gateway vai por ultimo e prevalece."""
        hostile = make_conninfo(
            database, options="-c default_transaction_read_only=off -c statement_timeout=0"
        )
        with PostgresAdapter(hostile, engine) as adapter:
            settings = adapter.execute(
                "SELECT name, setting FROM pg_settings "
                "WHERE name IN ('default_transaction_read_only', 'statement_timeout') "
                "ORDER BY name"
            )
        assert settings.rows == (
            ("default_transaction_read_only", "on"),
            ("statement_timeout", "30000"),
        )


class TestStatementTimeout:
    """Timeout do lado do PostgreSQL, nao um timer no cliente."""

    def test_slow_query_is_interrupted(self, adapter_factory):
        adapter = adapter_factory(timeout_ms=300)
        started = time.monotonic()
        with pytest.raises(QueryTimeout):
            adapter.execute("SELECT count(*) FROM generate_series(1, 500000000)")
        assert time.monotonic() - started < 20

    def test_timeout_error_is_sanitized(self, adapter_factory):
        adapter = adapter_factory(timeout_ms=200)
        with pytest.raises(QueryTimeout) as info:
            adapter.execute("SELECT count(*) FROM generate_series(1, 500000000)")
        message = str(info.value)
        assert "canceling statement" not in message
        assert "statement timeout" not in message
        assert info.value.__cause__ is None
        assert info.value.__context__ is None

    def test_timeout_is_a_database_error(self, adapter_factory):
        adapter = adapter_factory(timeout_ms=200)
        with pytest.raises(DatabaseError):
            adapter.execute("SELECT count(*) FROM generate_series(1, 500000000)")

    def test_the_connection_survives_a_timeout(self, adapter_factory):
        adapter = adapter_factory(timeout_ms=200)
        with pytest.raises(QueryTimeout):
            adapter.execute("SELECT count(*) FROM generate_series(1, 500000000)")
        assert adapter.execute("SELECT 1 AS um").rows == ((1,),)

    def test_a_fast_query_is_not_affected(self, adapter_factory):
        adapter = adapter_factory(timeout_ms=30_000)
        assert adapter.execute(f"SELECT count(*) FROM {TABLE}").rows == ((50,),)


class TestRowLimit:
    """Nunca devolver a linha N+1. `truncated` avisa que ela existia."""

    def test_more_rows_than_the_limit(self, adapter_factory):
        adapter = adapter_factory(max_rows=10)
        result = adapter.execute(f"SELECT id FROM {TABLE} ORDER BY id")
        assert result.row_count == 10
        assert result.truncated is True
        assert result.rows[-1] == (10,)
        assert (11,) not in result.rows

    def test_exactly_the_limit(self, adapter_factory):
        adapter = adapter_factory(max_rows=50)
        result = adapter.execute(f"SELECT id FROM {TABLE} ORDER BY id")
        assert result.row_count == 50
        assert result.truncated is False

    def test_fewer_rows_than_the_limit(self, adapter_factory):
        adapter = adapter_factory(max_rows=1_000)
        result = adapter.execute(f"SELECT id FROM {TABLE} ORDER BY id")
        assert result.row_count == 50
        assert result.truncated is False

    def test_empty_result_is_not_truncated(self, adapter_factory):
        adapter = adapter_factory(max_rows=10)
        result = adapter.execute(f"SELECT id FROM {TABLE} WHERE false")
        assert result.rows == ()
        assert result.truncated is False

    def test_limit_of_one(self, adapter_factory):
        adapter = adapter_factory(max_rows=1)
        result = adapter.execute(f"SELECT id FROM {TABLE} ORDER BY id")
        assert result.rows == ((1,),)
        assert result.truncated is True

    def test_truncation_still_masks_what_is_returned(self, adapter_factory):
        adapter = adapter_factory(max_rows=5)
        result = adapter.execute(f"SELECT cpf FROM {TABLE} ORDER BY id")
        assert result.truncated is True
        assert result.row_count == 5
        assert all(len(row[0]) == 32 for row in result.rows)
        assert all(row[0] != "00000000001" for row in result.rows)

    @pytest.mark.parametrize("batch_size", [1, 3, 7, 500])
    def test_batch_size_does_not_change_the_limit(self, adapter_factory, batch_size):
        adapter = adapter_factory(max_rows=10, batch_size=batch_size)
        result = adapter.execute(f"SELECT id FROM {TABLE} ORDER BY id")
        assert result.row_count == 10
        assert result.truncated is True

    def test_limit_is_applied_to_the_validated_door_too(self, adapter_factory):
        adapter = adapter_factory(max_rows=4)
        result = adapter.execute_validated(f"SELECT id FROM {TABLE} ORDER BY id")
        assert result.row_count == 4
        assert result.truncated is True


class TestValidatedDoor:
    def test_select_passes_through(self, adapter):
        result = adapter.execute_validated(f"SELECT cpf FROM {TABLE} WHERE id = 1")
        assert result.row_count == 1
        assert result.rows[0][0] != "00000000001"

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT 1; SELECT 2",
            f"WITH x AS (DELETE FROM {TABLE} RETURNING *) SELECT * FROM x",
            "SELECT pg_read_file('/etc/passwd')",
            "SELECT 1 INTO nova",
            f"SELECT * FROM {TABLE} FOR UPDATE",
            "SET statement_timeout = 0",
        ],
    )
    def test_rejected_before_the_database(self, adapter, sql):
        with pytest.raises(QueryRejected):
            adapter.execute_validated(sql)

    def test_invalid_sql_never_reaches_the_database(self, adapter):
        with pytest.raises(InvalidQuery):
            adapter.execute_validated("SELEC 1")


class TestProvenanceCapability:
    def test_capability_holds_on_a_normal_connection(self, database):
        with psycopg.connect(database, autocommit=True) as connection:
            check_provenance_capability(connection)

    def test_adapter_verifies_on_connect(self, database, engine):
        with PostgresAdapter(database, engine) as adapter:
            assert adapter.closed is False

    def test_capability_fails_without_catalog_access(self, database):
        """Role sem SELECT em pg_attribute: a protecao contra alias cairia."""
        role = "maskgw_sem_catalogo"
        with psycopg.connect(database, autocommit=True) as admin:
            admin.execute(f"DROP ROLE IF EXISTS {role}")
            admin.execute(f"CREATE ROLE {role} NOLOGIN")
            try:
                admin.execute("REVOKE SELECT ON pg_attribute FROM PUBLIC")
                with psycopg.connect(database, autocommit=True) as restricted:
                    restricted.execute(f"SET ROLE {role}")
                    with pytest.raises(CapabilityError) as info:
                        check_provenance_capability(restricted)
            finally:
                admin.execute("GRANT SELECT ON pg_attribute TO PUBLIC")
                admin.execute(f"DROP ROLE IF EXISTS {role}")

        message = str(info.value)
        assert "pg_attribute" in message
        assert "permission denied" not in message
        assert info.value.__cause__ is None
        assert info.value.__context__ is None

    def test_catalog_access_is_restored(self, database):
        """Guarda-corpo: o teste anterior nao pode deixar o banco quebrado."""
        with psycopg.connect(database, autocommit=True) as connection:
            check_provenance_capability(connection)


class TestNothingLeaks:
    def test_rejected_write_does_not_echo_the_query(self, adapter):
        with pytest.raises(DatabaseError) as info:
            adapter.execute(f"INSERT INTO {TABLE} VALUES (1, '{CPF}')")
        assert CPF not in str(info.value)
        assert TABLE not in str(info.value)

    def test_no_log_records_during_execution_safety_paths(self, adapter_factory, caplog):
        adapter = adapter_factory(timeout_ms=200, max_rows=3)
        with caplog.at_level(logging.DEBUG):
            adapter.execute(f"SELECT cpf FROM {TABLE} ORDER BY id")
            with pytest.raises(DatabaseError):
                adapter.execute(f"DELETE FROM {TABLE}")
            with pytest.raises(QueryTimeout):
                adapter.execute("SELECT count(*) FROM generate_series(1, 500000000)")
        assert caplog.records == []

    def test_adapter_repr_still_hides_the_dsn(self, adapter):
        assert repr(adapter) == "PostgresAdapter(closed=False)"
