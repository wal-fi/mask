"""PG16 real -> authoritative masking -> typed encoder -> bounded receiver.

Synthetic schema only, on the explicit disposable MASKGW_TEST_DSN. This is
NOT an operational worker, a new listener or proof of process memory quotas.
"""

from __future__ import annotations

import hashlib
import hmac
import socket
import string
import time
import uuid
from dataclasses import replace
from typing import Any

import psycopg
import pytest
from psycopg import sql

from maskgw.config import load_config_text
from maskgw.config.gateway import DatabaseSettings
from maskgw.db.postgres import PostgresAdapter
from maskgw.db.provenance import ProvenanceResolver
from maskgw.db.result import DatabaseResultTypeError
from maskgw.errors import CapabilityError, DatabaseError, QueryRejected, QueryTimeout
from maskgw.masking.engine import MaskingEngine
from maskgw.pgwire.result_encoder import encode_result
from maskgw.pgwire.result_frame import ResultDeadline, ResultLimits, validate_result
from maskgw.pgwire.transport import RawChannel, TransportLimits
from maskgw.sql.policy import DEFAULT_SQL_POLICY
from tests.conftest import TEST_HMAC_KEY
from tests.test_result_frame import HEADER, IDENTITY
from tests.test_result_receiver import deadline, setup

pytestmark = pytest.mark.integration

CONFIG = """
masking:
  - match: cpf
    transformer: hmac_sha256
  - match: email
    transformer: regex
    config:
      pattern: "^(.{2}).*(@.*)$"
      replacement: "\\\\1***\\\\2"
  - match: numeric_secret
    transformer: fixed
    config: {value: "[NUMBER]"}
  - match: token
    transformer: random
    config: {strategy: alphanumeric, preserve_length: false, length: 12}
exceptions:
  - match: tipo_cpf
    mode: exact
"""


@pytest.fixture
def source_table(dsn):
    schema = "maskgw_typed_" + uuid.uuid4().hex[:12]
    namespace = sql.Identifier(schema)
    relation = sql.Identifier(schema, "data")
    domain = sql.Identifier(schema, "label")
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(namespace))
        try:
            admin.execute(sql.SQL("CREATE DOMAIN {} AS text").format(domain))
            admin.execute(
                sql.SQL("""
                CREATE TABLE {} (
                    id integer, cpf text, tipo_cpf text, email text,
                    numeric_secret numeric, amount numeric, token text,
                    active boolean, label {}
                )
            """).format(relation, domain)
            )
            for row in (
                (
                    1,
                    "11122233344",
                    "physical",
                    "alice@example.test",
                    123,
                    19.5,
                    "secret1",
                    True,
                    "label1",
                ),
                (
                    2,
                    "55566677788",
                    "company",
                    "bob@example.test",
                    456,
                    99.5,
                    "secret2",
                    False,
                    "label2",
                ),
                (3, None, None, None, None, None, None, None, None),
            ):
                admin.execute(
                    sql.SQL("INSERT INTO {} VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)").format(relation),
                    row,
                )
            yield relation.as_string(admin)
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(namespace))


@pytest.fixture
def typed_adapter(dsn, secrets):
    opened = []

    def make(*, settings: DatabaseSettings | None = None, config: str = CONFIG) -> PostgresAdapter:
        item = PostgresAdapter(
            dsn,
            MaskingEngine(load_config_text(config, secrets=secrets)),
            settings=settings or DatabaseSettings(statement_timeout_ms=30000, max_rows=1000),
            sql_policy=replace(
                DEFAULT_SQL_POLICY, allowed_pg_functions=frozenset({"pg_sleep", "pg_backend_pid"})
            ),
        )
        item.connect()
        opened.append(item)
        return item

    yield make
    for item in opened:
        item.close()


def encoded(item: PostgresAdapter, query: str) -> tuple[Any, bytes]:
    result = item._execute_typed_validated(query)
    limits = ResultLimits(max_rows=item.settings.max_rows)
    raw = encode_result(
        result,
        identity=IDENTITY,
        limits=limits,
        deadline=ResultDeadline(expires_at=time.monotonic() + 5),
    )
    validate_result(
        raw,
        expected=IDENTITY,
        limits=limits,
        deadline=ResultDeadline(expires_at=time.monotonic() + 5),
    )
    return result, raw


def test_real_hmac_provenance_alias_and_authoritative_exception(typed_adapter, source_table):
    item = typed_adapter()
    query = (
        sql.SQL("SELECT cpf AS tipo_cpf, tipo_cpf AS cpf FROM {} WHERE id=1")
        .format(sql.SQL(source_table))
        .as_string()
    )
    result, raw = encoded(item, query)
    expected = hmac.new(TEST_HMAC_KEY.encode(), b"11122233344", hashlib.sha256).hexdigest()
    assert result.masked.rows == ((expected, "physical"),)
    assert result.type_oids == (25, 25)
    assert b"11122233344" not in raw and expected.encode() in raw


def test_real_derived_duplicate_columns_and_nullable_types(typed_adapter, source_table):
    item = typed_adapter()
    query = (
        sql.SQL("SELECT substr(cpf,1,3) AS same, email AS same, active, id FROM {} ORDER BY id")
        .format(sql.SQL(source_table))
        .as_string()
    )
    result, raw = encoded(item, query)
    expected = hmac.new(TEST_HMAC_KEY.encode(), b"111", hashlib.sha256).hexdigest()
    assert result.masked.rows[0] == (expected, "al***@example.test", True, 1)
    assert result.masked.rows[-1] == (None, None, None, 3)
    assert result.type_oids == (25, 25, 16, 23)
    assert b"11122233344" not in raw and b"alice@example.test" not in raw


def test_masked_numeric_is_text_not_preserved_numeric(typed_adapter, source_table):
    item = typed_adapter()
    result, raw = encoded(
        item,
        sql.SQL("SELECT numeric_secret FROM {} ORDER BY id")
        .format(sql.SQL(source_table))
        .as_string(),
    )
    assert result.type_oids == (25,) and result.masked.rows == (
        ("[NUMBER]",),
        ("[NUMBER]",),
        (None,),
    )
    assert b"[NUMBER]" in raw


@pytest.mark.parametrize("where", [1, 3])
def test_unmasked_numeric_refused_before_fetch_even_null(
    typed_adapter, source_table, monkeypatch, where
):
    item = typed_adapter()
    called = []
    monkeypatch.setattr(item, "_read_masked", lambda *args: called.append(args))
    with pytest.raises(DatabaseResultTypeError):
        item._execute_typed_validated(
            sql.SQL("SELECT amount FROM {} WHERE id={}")
            .format(sql.SQL(source_table), sql.Literal(where))
            .as_string()
        )
    assert not called
    assert item._connection.info.transaction_status is psycopg.pq.TransactionStatus.IDLE


def test_domain_metadata_measured_as_base_type_on_pg16(typed_adapter, source_table):
    item = typed_adapter()
    result, _ = encoded(
        item, sql.SQL("SELECT label FROM {} ORDER BY id").format(sql.SQL(source_table)).as_string()
    )
    assert result.type_oids == (25,)
    assert result.masked.rows == (("label1",), ("label2",), (None,))


def test_random_invariants_and_row_limit_excess_not_masked(
    typed_adapter, source_table, monkeypatch
):
    item = typed_adapter(settings=DatabaseSettings(statement_timeout_ms=30000, max_rows=1))
    original = item._engine.mask_rows
    seen = []

    def mask(columns, rows):
        seen.extend(rows)
        return original(columns, rows)

    monkeypatch.setattr(item._engine, "mask_rows", mask)
    result, raw = encoded(
        item, sql.SQL("SELECT token FROM {} ORDER BY id").format(sql.SQL(source_table)).as_string()
    )
    value = result.masked.rows[0][0]
    assert len(value) == 12 and set(value) <= set(string.ascii_letters + string.digits)
    assert len(seen) == 1 and result.masked.truncated
    assert b"secret1" not in raw and b"secret2" not in raw


def test_same_connection_legacy_typed_and_read_only_defense(typed_adapter, source_table):
    item = typed_adapter()
    first = item.execute_validated("SELECT pg_backend_pid()").rows[0][0]
    second = item._execute_typed_validated("SELECT pg_backend_pid()").masked.rows[0][0]
    assert first == second
    with pytest.raises(QueryRejected):
        item._execute_typed_validated(
            sql.SQL("DELETE FROM {}").format(sql.SQL(source_table)).as_string()
        )
    with pytest.raises(DatabaseError):
        item.execute(sql.SQL("DELETE FROM {}").format(sql.SQL(source_table)).as_string())
    assert item._execute_typed_validated("SELECT 1").masked.rows == ((1,),)


def test_server_timeout_remains_sanitized_and_session_idle(typed_adapter):
    item = typed_adapter(settings=DatabaseSettings(statement_timeout_ms=100, max_rows=10))
    with pytest.raises(QueryTimeout) as caught:
        item._execute_typed_validated("SELECT pg_sleep(1)")
    assert caught.value.__context__ is None
    assert item._connection.info.transaction_status is psycopg.pq.TransactionStatus.IDLE


def test_catalog_failure_injected_after_real_query_refuses_before_fetch(
    typed_adapter, source_table, monkeypatch
):
    item = typed_adapter()
    read = []

    def unavailable(self, keys):
        del self, keys
        raise CapabilityError("catalog unavailable")

    monkeypatch.setattr(ProvenanceResolver, "_load", unavailable)
    monkeypatch.setattr(item, "_read_masked", lambda *args: read.append(args))
    with pytest.raises(CapabilityError):
        item._execute_typed_validated(
            sql.SQL("SELECT cpf AS x FROM {}").format(sql.SQL(source_table)).as_string()
        )
    assert not read


def test_actual_pipeline_frame_is_accepted_and_sent_by_receiver(typed_adapter, source_table):
    item = typed_adapter(settings=DatabaseSettings(statement_timeout_ms=30000, max_rows=1000))
    _, raw = encoded(
        item,
        sql.SQL("SELECT cpf AS x, id FROM {} ORDER BY id")
        .format(sql.SQL(source_table))
        .as_string(),
    )
    _, _, _, receiver = setup()
    source, worker = socket.socketpair()
    output, client = socket.socketpair()
    try:
        worker.settimeout(2)
        worker.sendall(raw)
        receiver.receive(RawChannel(source, stop=lambda: False, limits=TransportLimits()))
        receiver.send_to(
            RawChannel(output, stop=lambda: False, limits=TransportLimits()), deadline=deadline()
        )
        client.settimeout(2)
        assert client.recv(4096) == raw[HEADER.size :]
    finally:
        for sock in (source, worker, output, client):
            sock.close()
        receiver.close(deadline=deadline())


def test_all_eight_advertised_types_from_real_psycopg_loaders(typed_adapter):
    item = typed_adapter(config="{}")
    result, _ = encoded(
        item,
        """
        SELECT true AS b, (-32768)::int2 AS i2, (-2147483648)::int4 AS i4,
               (-9223372036854775808)::int8 AS i8, 'name'::name AS n,
               'text'::text AS t, 'v'::varchar(4) AS v, 'c'::character(4) AS c
    """,
    )
    assert result.type_oids == (16, 21, 23, 20, 19, 25, 1043, 1042)
    assert result.masked.rows == (
        (True, -32768, -2147483648, -9223372036854775808, "name", "text", "v", "c   "),
    )
