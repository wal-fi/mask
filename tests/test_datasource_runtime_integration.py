"""Fase 9, Etapa 3 contra PostgreSQL 16 real (F9-002, F9-003, F9-020 a F9-023).

Dois datasources apontam para o MESMO banco de teste com politicas diferentes:
o que muda entre eles e so o que o registry publica. Assim cada teste prova o
isolamento por geracao — e nao a diferenca entre dois servidores. O DSN vem
exclusivamente de `MASKGW_TEST_DSN` e nunca e impresso.
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from maskgw.audit import AuditLog
from maskgw.datasource import CatalogStore, DatasourceDraft, DestinationPolicy
from maskgw.datasource.models import DatasourcePolicy, TlsSettings
from maskgw.errors import DatabaseError
from maskgw.gateway.datasources import DatasourceGateway
from maskgw.gateway.models import ErrorCategory, GatewayError
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.runtime.candidate import CandidateFailure, DatasourceCandidateError
from maskgw.runtime.datasource_service import (
    DatasourceCatalogSettings,
    DatasourceRuntime,
    open_datasource_runtime,
)
from maskgw.runtime.datasources import DatasourceUnavailableError
from maskgw.secretsource import MappingSecretProvider

pytestmark = pytest.mark.integration

KEY = "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
HMAC_KEY = "chave-de-teste-para-hmac-com-tamanho-suficiente"
SCHEMA = "maskgw_etapa3"
TABLE = f"{SCHEMA}.cliente"
CPF = "11122233344"
EMAIL = "maria.ficticia@example.test"

CRM_POLICY: Mapping[str, object] = {"masking": [{"match": "cpf", "transformer": "hmac_sha256"}]}
FIN_POLICY: Mapping[str, object] = {
    "masking": [{"match": "email", "transformer": "fixed", "config": {"value": "[EMAIL]"}}]
}
BOTH_POLICY: Mapping[str, object] = {
    "masking": [
        {"match": "cpf", "transformer": "hmac_sha256"},
        {"match": "email", "transformer": "fixed", "config": {"value": "[EMAIL]"}},
    ]
}


def _hmac(value: str) -> str:
    return hmac.new(HMAC_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def _provider() -> MappingSecretProvider:
    return MappingSecretProvider({"MASKGW_DATASOURCE_MASTER_KEY": KEY, HMAC_KEY_ENV: HMAC_KEY})


class _Target:
    """Campos do DSN de teste, separados como o catalogo exige."""

    def __init__(self, dsn: str) -> None:
        values: dict[str, Any] = conninfo_to_dict(dsn)
        host = values.get("host") or values.get("hostaddr")
        if not isinstance(host, str) or not host or "/" in host or "," in host:
            pytest.fail("MASKGW_TEST_DSN precisa de um unico host TCP para esta suite")
        self.host = host.lower()
        self.port = int(values.get("port") or 5432)
        self.database = str(values["dbname"])
        self.username = str(values["user"])
        self.password = str(values.get("password") or "")
        sslmode = str(values.get("sslmode") or "")
        if sslmode == "verify-full":
            self.tls = TlsSettings(mode="verify-full")
        elif sslmode in {"require", "verify-ca"}:
            self.tls = TlsSettings(mode="require")
        else:
            self.tls = TlsSettings()

    def draft(
        self, alias: str, policy: Mapping[str, object], *, enabled: bool = True
    ) -> DatasourceDraft:
        return DatasourceDraft(
            alias=alias,
            display_name=alias,
            host=self.host,
            port=self.port,
            database=self.database,
            username=self.username,
            enabled=enabled,
            tls=self.tls,
            policy=DatasourcePolicy.from_mapping(policy),
            destination_policy=DestinationPolicy(
                allow_loopback=True, allow_public=True, allowed_hosts=(self.host,)
            ),
        )


@pytest.fixture
def database(dsn: str) -> Iterator[str]:
    with psycopg.connect(dsn, autocommit=True) as setup:
        setup.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
        setup.execute(f"CREATE SCHEMA {SCHEMA}")
        setup.execute(f"CREATE TABLE {TABLE} (id integer PRIMARY KEY, cpf text, email text)")
        setup.execute(f"INSERT INTO {TABLE} VALUES (1, %s, %s)", [CPF, EMAIL])
    yield dsn
    with psycopg.connect(dsn, autocommit=True) as teardown:
        teardown.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")


@pytest.fixture
def target(database: str) -> _Target:
    return _Target(database)


def _catalog(
    tmp_path: Path, target: _Target, *drafts: DatasourceDraft
) -> DatasourceCatalogSettings:
    store_path = tmp_path / "datasources.store"
    anchor_path = tmp_path / "private-anchor" / "datasources.anchor"
    with CatalogStore.initialize(store_path, anchor_path=anchor_path, master_key=KEY) as store:
        for item in drafts:
            store.create(item, target.password)
    return DatasourceCatalogSettings(store_path=store_path, anchor_path=anchor_path)


@pytest.fixture
def runtime(tmp_path: Path, target: _Target) -> Iterator[DatasourceRuntime]:
    settings = _catalog(
        tmp_path, target, target.draft("crm", CRM_POLICY), target.draft("fin", FIN_POLICY)
    )
    opened = open_datasource_runtime(settings, secrets=_provider())
    try:
        yield opened
    finally:
        opened.close()


def _client_backends(dsn: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as control:
        row = control.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
            "AND backend_type = 'client backend' AND pid <> pg_backend_pid()"
        ).fetchone()
    assert row is not None
    return int(row[0])


def _rows(gateway: DatasourceGateway, alias: str, sql: str) -> list[list[Any]]:
    with gateway.open_session(alias) as session:
        return session.query(sql).rows


# -- pipeline unico e isolamento de politica -----------------------------------


def test_each_alias_masks_with_its_own_policy_through_the_same_pipeline(
    runtime: DatasourceRuntime,
) -> None:
    gateway = DatasourceGateway(runtime.registry, AuditLog())
    sql = f"SELECT id, cpf, email FROM {TABLE}"
    assert _rows(gateway, "crm", sql) == [[1, _hmac(CPF), EMAIL]]
    assert _rows(gateway, "fin", sql) == [[1, CPF, "[EMAIL]"]]
    # O alias do cliente adiciona protecao, nunca remove (D-042), por alias.
    assert _rows(gateway, "crm", f"SELECT cpf AS documento FROM {TABLE}") == [[_hmac(CPF)]]
    assert _rows(gateway, "crm", f"SELECT upper(cpf) FROM {TABLE}") == [[_hmac(CPF)]]


def test_session_refuses_writes_in_the_validator_and_in_postgresql(
    runtime: DatasourceRuntime, database: str
) -> None:
    gateway = DatasourceGateway(runtime.registry, AuditLog())
    with gateway.open_session("crm") as session:
        for statement in (
            f"INSERT INTO {TABLE} VALUES (2, 'x', 'y')",
            f"DELETE FROM {TABLE}",
            "SELECT pg_read_file('/etc/passwd')",
        ):
            with pytest.raises(GatewayError) as caught:
                session.query(statement)
            assert caught.value.category is ErrorCategory.QUERY_REJECTED
            assert caught.value.__context__ is None
    # Defesa em profundidade: mesmo sem o validator, a sessao e read-only.
    lease = runtime.registry.open_session("crm")
    try:
        with lease.use() as adapter:
            readonly = adapter.execute(
                "SELECT current_setting('default_transaction_read_only'), "
                "current_setting('statement_timeout')"
            )
            assert readonly.rows == (("on", "30s"),)
            with pytest.raises(DatabaseError):
                adapter.execute(f"INSERT INTO {TABLE} VALUES (3, 'x', 'y')")
    finally:
        lease.close()
    with psycopg.connect(database, autocommit=True) as check:
        row = check.execute(f"SELECT count(*) FROM {TABLE}").fetchone()
    assert row == (1,)


def test_every_session_owns_a_distinct_upstream_connection(
    runtime: DatasourceRuntime, database: str
) -> None:
    baseline = _client_backends(database)
    leases = [runtime.registry.open_session("crm") for _ in range(3)]
    pids = set()
    for lease in leases:
        with lease.use() as adapter:
            pids.add(adapter.execute("SELECT pg_backend_pid()").rows[0][0])
    assert len(pids) == 3
    assert _client_backends(database) == baseline + 3
    for lease in leases:
        lease.close()
    assert _client_backends(database) == baseline


# -- troca, drenagem e isolamento entre datasources -------------------------------


def test_policy_swap_keeps_admitted_session_and_never_touches_other_alias(
    runtime: DatasourceRuntime, target: _Target
) -> None:
    gateway = DatasourceGateway(runtime.registry, AuditLog())
    sql = f"SELECT id, cpf, email FROM {TABLE}"
    fin_before = runtime.registry.current("fin").generation
    old_session = gateway.open_session("crm")
    crm = runtime.store.by_alias("crm")

    runtime.service.update(
        crm.id, target.draft("crm", BOTH_POLICY), expected_revision=runtime.store.revision
    )

    # A sessao admitida continua com a politica que capturou.
    assert old_session.query(sql).rows == [[1, _hmac(CPF), EMAIL]]
    with gateway.open_session("crm") as fresh:
        assert fresh.query(sql).rows == [[1, _hmac(CPF), "[EMAIL]"]]
        assert fresh.generation > old_session.generation
    assert runtime.registry.current("fin").generation == fin_before
    assert runtime.registry.status().retired_open == 1
    old_session.close()
    assert runtime.registry.status().retired_open == 0


def test_disable_and_remove_drain_admitted_sessions(
    runtime: DatasourceRuntime, database: str
) -> None:
    gateway = DatasourceGateway(runtime.registry, AuditLog())
    sql = f"SELECT id FROM {TABLE}"
    baseline = _client_backends(database)
    session = gateway.open_session("crm")
    crm = runtime.store.by_alias("crm")

    runtime.service.set_enabled(crm.id, False, expected_revision=runtime.store.revision)
    with pytest.raises(DatasourceUnavailableError):
        gateway.open_session("crm")
    assert session.query(sql).rows == [[1]]
    assert _rows(gateway, "fin", sql) == [[1]]
    session.close()
    assert _client_backends(database) == baseline

    fin = runtime.store.by_alias("fin")
    fin_session = gateway.open_session("fin")
    runtime.service.remove(fin.id, expected_revision=runtime.store.revision)
    with pytest.raises(DatasourceUnavailableError):
        gateway.open_session("fin")
    assert fin_session.query(sql).rows == [[1]]
    fin_session.close()
    assert runtime.registry.status().published == ()
    assert _client_backends(database) == baseline


def test_wrong_credential_candidate_changes_nothing(
    runtime: DatasourceRuntime, database: str
) -> None:
    crm = runtime.store.by_alias("crm")
    revision = runtime.store.revision
    generation = runtime.registry.current("crm").generation
    store_bytes = runtime.store.store_path.read_bytes()
    baseline = _client_backends(database)

    with pytest.raises(DatasourceCandidateError) as caught:
        runtime.service.rotate_secret(crm.id, "senha-errada-canario", expected_revision=revision)
    assert caught.value.category is CandidateFailure.CONNECTION
    assert "senha-errada-canario" not in repr(caught.value)
    assert runtime.store.revision == revision
    assert runtime.store.store_path.read_bytes() == store_bytes
    assert runtime.registry.current("crm").generation == generation
    assert _client_backends(database) == baseline
    runtime.service.test_datasource(crm.id)
    assert runtime.store.revision == revision


# -- startup fail-closed e shutdown -------------------------------------------------


def test_startup_with_wrong_upstream_password_fails_closed(
    tmp_path: Path, target: _Target, database: str
) -> None:
    store_path = tmp_path / "datasources.store"
    anchor_path = tmp_path / "private-anchor" / "datasources.anchor"
    with CatalogStore.initialize(store_path, anchor_path=anchor_path, master_key=KEY) as store:
        store.create(target.draft("crm", CRM_POLICY), target.password)
        store.create(target.draft("fin", FIN_POLICY), "senha-errada-canario")
    baseline = _client_backends(database)
    settings = DatasourceCatalogSettings(store_path=store_path, anchor_path=anchor_path)

    with pytest.raises(DatasourceCandidateError) as caught:
        open_datasource_runtime(settings, secrets=_provider())

    assert caught.value.category is CandidateFailure.CONNECTION
    assert caught.value.__context__ is None
    assert _client_backends(database) == baseline
    CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY).close()


def test_shutdown_cancels_a_running_statement_and_leaves_no_backend(
    runtime: DatasourceRuntime, database: str
) -> None:
    baseline = _client_backends(database)
    lease = runtime.registry.open_session("fin")
    idle = runtime.registry.open_session("crm")
    outcome: list[BaseException | None] = []
    running = threading.Event()

    def long_query() -> None:
        try:
            with lease.use() as adapter:
                running.set()
                adapter.execute("SELECT pg_sleep(30)")
            outcome.append(None)
        except BaseException as exc:
            outcome.append(exc)

    worker = threading.Thread(target=long_query, daemon=True)
    worker.start()
    assert running.wait(timeout=5)
    time.sleep(0.3)  # o statement precisa estar no servidor
    started = time.monotonic()
    runtime.close()
    worker.join(timeout=15)

    assert not worker.is_alive()
    assert time.monotonic() - started < 10
    assert isinstance(outcome[0], DatabaseError)
    assert lease.closed
    assert idle.closed
    assert _client_backends(database) == baseline
    runtime.close()
