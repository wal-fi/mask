"""Fase 9, Etapa 3: candidato, coordenador e startup fail-closed (F9-022, F9-023).

Catalogo real (`CatalogStore` em diretorio temporario) e adapters dublês: o que
se prova aqui e a ORDEM e o EFEITO — candidato verificado antes de persistir,
teste sem publicacao, falha sem rastro em bytes/revision/registry, bloqueio
apos falha de persistencia e startup que nao deixa recurso de pe. A mesma
cadeia contra PostgreSQL 16 real esta em
`test_datasource_runtime_integration.py`.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from maskgw.config.gateway import GatewayConfig
from maskgw.datasource import (
    CatalogHooks,
    CatalogOutcomeUncertainError,
    CatalogRevisionConflictError,
    CatalogStore,
    CatalogStoreError,
    CatalogWriteError,
    CrashPoint,
    DestinationPolicy,
    FilesystemPolicyError,
)
from maskgw.datasource.models import DatasourceLimits, DatasourcePolicy
from maskgw.db.postgres import PostgresAdapter
from maskgw.errors import DatabaseError
from maskgw.masking.engine import MaskingEngine
from maskgw.runtime.candidate import (
    CandidateFailure,
    CandidateSpec,
    DatasourceCandidateError,
    build_candidate,
    build_conninfo,
    effective_database_settings,
)
from maskgw.runtime.datasource_service import (
    DatasourceCatalogSettings,
    DatasourceRenameError,
    DatasourceRuntimeService,
    DatasourceServiceBlockedError,
    DatasourceServiceClosedError,
    open_datasource_runtime,
)
from maskgw.runtime.datasources import (
    DatasourceBusyError,
    DatasourceRegistry,
    DatasourceUnavailableError,
    RegistryLimits,
)
from tests.datasource_runtime_support import (
    ADDRESS,
    HOST,
    KEY,
    OTHER_SECRET,
    SECRET,
    FakeFactory,
    capability_failure,
    draft,
    resolver,
    secrets_provider,
)


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "datasources.store", tmp_path / "private-anchor" / "datasources.anchor"


class _Crash:
    """Ponto de falha armado sob demanda nos hooks do catalogo."""

    def __init__(self) -> None:
        self.point: CrashPoint | None = None

    def __call__(self, point: CrashPoint) -> None:
        if point == self.point:
            self.point = None
            raise CatalogWriteError("falha sintetica de persistencia")


class _Harness:
    def __init__(self, tmp_path: Path, *, limits: RegistryLimits | None = None) -> None:
        self.store_path, self.anchor_path = _paths(tmp_path)
        CatalogStore.initialize(
            self.store_path, anchor_path=self.anchor_path, master_key=KEY
        ).close()
        self.crash = _Crash()
        self.store = CatalogStore.open(
            self.store_path,
            anchor_path=self.anchor_path,
            master_key=KEY,
            hooks=CatalogHooks(after_point=self.crash),
        )
        self.factory = FakeFactory()
        self.registry = DatasourceRegistry(limits)
        self.service = DatasourceRuntimeService(
            store=self.store,
            registry=self.registry,
            secrets=secrets_provider(),
            resolver=resolver,
            adapter_factory=self.factory,
        )

    def disk(self) -> tuple[bytes, bytes]:
        return self.store_path.read_bytes(), self.anchor_path.read_bytes()

    def published(self) -> dict[str, int]:
        return {item.alias: item.generation for item in self.registry.status().published}

    def close(self) -> None:
        self.service.close()
        self.registry.close()
        self.store.close()


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[_Harness]:
    value = _Harness(tmp_path)
    try:
        yield value
    finally:
        value.close()


# -- candidato -----------------------------------------------------------------


def test_effective_limits_are_the_most_restrictive_of_policy_and_limits() -> None:
    policy = DatasourcePolicy.from_mapping(
        {"database": {"statement_timeout_ms": 5_000, "max_rows": 50_000}}
    )
    loaded = policy.to_mapping()
    from maskgw.config.loader import validate_file_config  # noqa: PLC0415

    file_config = validate_file_config(loaded)
    settings = effective_database_settings(
        file_config, DatasourceLimits(statement_timeout_ms=20_000, max_rows=200)
    )
    assert settings.statement_timeout_ms == 5_000
    assert settings.max_rows == 200


def test_candidate_pins_resolved_addresses_and_keeps_name_for_tls() -> None:
    spec = CandidateSpec.from_draft(draft(), SECRET)
    conninfo = build_conninfo(spec, ("10.0.0.7", "10.0.0.8"))
    assert "hostaddr=10.0.0.7,10.0.0.8" in conninfo
    assert f"host={HOST},{HOST}" in conninfo
    assert "sslmode=disable" in conninfo
    assert "connect_timeout=10" in conninfo
    assert SECRET not in repr(spec)


def test_candidate_verification_connection_is_always_closed() -> None:
    factory = FakeFactory()
    prepared = build_candidate(
        CandidateSpec.from_draft(draft(), SECRET),
        secrets=secrets_provider(),
        resolver=resolver,
        adapter_factory=factory,
    )
    assert prepared.addresses == (ADDRESS,)
    assert [adapter.closes for adapter in factory.adapters] == [1]
    assert factory.open_adapters() == []
    assert SECRET not in repr(prepared)


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda spec, _f: dataclasses.replace(spec, host="169.254.169.254"), "DESTINATION"),
        (
            lambda spec, _f: dataclasses.replace(spec, expected_addresses=("10.9.9.9",)),
            "DESTINATION",
        ),
        (
            lambda spec, _f: dataclasses.replace(
                spec,
                policy=DatasourcePolicy.from_mapping(
                    {"masking": [{"match": "cpf", "transformer": "regex"}]}
                ),
            ),
            "POLICY",
        ),
        (lambda _spec, factory: _fail(factory, DatabaseError(SECRET)), "CONNECTION"),
        (lambda _spec, factory: _fail(factory, capability_failure()), "CAPABILITY"),
        (lambda _spec, factory: _fail(factory, RuntimeError(SECRET)), "CONNECTION"),
    ],
)
def test_candidate_failures_are_categorized_and_sanitized(
    mutate: Callable[[CandidateSpec, FakeFactory], CandidateSpec | None], expected: str
) -> None:
    factory = FakeFactory()
    spec = CandidateSpec.from_draft(draft(), SECRET)
    spec = mutate(spec, factory) or spec
    with pytest.raises(DatasourceCandidateError) as caught:
        build_candidate(
            spec, secrets=secrets_provider(), resolver=resolver, adapter_factory=factory
        )
    error = caught.value
    assert error.category == CandidateFailure(expected)
    assert error.__cause__ is None
    assert error.__context__ is None
    assert SECRET not in str(error)
    assert HOST not in str(error)
    assert factory.open_adapters() == []


def _fail(factory: FakeFactory, failure: BaseException) -> None:
    factory.connect_failure = failure


def test_policy_needing_absent_secret_fails_as_policy() -> None:
    from maskgw.secretsource import MappingSecretProvider  # noqa: PLC0415

    with pytest.raises(DatasourceCandidateError) as caught:
        build_candidate(
            CandidateSpec.from_draft(draft(), SECRET),
            secrets=MappingSecretProvider({}),
            resolver=resolver,
            adapter_factory=FakeFactory(),
        )
    assert caught.value.category is CandidateFailure.POLICY


def test_adapter_cancel_is_a_noop_without_connection_and_never_raises() -> None:
    import psycopg  # noqa: PLC0415

    from maskgw.masking.rules import MaskingPolicy  # noqa: PLC0415

    adapter = PostgresAdapter("host=x", MaskingEngine(MaskingPolicy(exceptions=(), rules=())))
    adapter.cancel()  # sem conexao: nada acontece

    class _Connection:
        closed = False
        timeouts: list[float] = []  # noqa: RUF012 - dublê local

        def cancel_safe(self, *, timeout: float) -> None:
            self.timeouts.append(timeout)
            raise psycopg.OperationalError(SECRET)

    connection = _Connection()
    adapter._connection = connection  # type: ignore[assignment]
    adapter.cancel()  # falha do pedido e silenciosa: melhor esforco
    assert connection.timeouts == [5.0]

    class _OldConnection:
        """psycopg < 3.2: sem `cancel_safe`, o protocolo e o mesmo."""

        closed = False
        cancels = 0

        def cancel(self) -> None:
            type(self).cancels += 1

    adapter._connection = _OldConnection()  # type: ignore[assignment]
    adapter.cancel()
    assert _OldConnection.cancels == 1
    adapter._connection = None


# -- testes de candidato nao publicam (F9-022/F9-026) ---------------------------


def test_testing_a_draft_or_datasource_never_persists_or_publishes(harness: _Harness) -> None:
    record = harness.service.create(draft("crm"), SECRET, expected_revision=1)
    before_disk = harness.disk()
    before_revision = harness.store.revision
    before_published = harness.published()
    before_record = harness.store.get(record.id)

    harness.service.test_draft(draft("novo"), SECRET)
    harness.service.test_datasource(record.id)

    assert harness.disk() == before_disk
    assert harness.store.revision == before_revision
    assert harness.published() == before_published
    assert harness.store.get(record.id).last_test == before_record.last_test
    assert harness.registry.status().candidates == 0
    # Cada teste abriu e fechou a propria conexao de verificacao.
    assert harness.factory.open_adapters() == []


def test_failed_test_has_no_effect_either(harness: _Harness) -> None:
    record = harness.service.create(draft("crm"), SECRET, expected_revision=1)
    before = (harness.disk(), harness.store.revision, harness.published())
    harness.factory.connect_failure = DatabaseError("falha sintetica")
    with pytest.raises(DatasourceCandidateError):
        harness.service.test_datasource(record.id)
    with pytest.raises(DatasourceCandidateError):
        harness.service.test_draft(draft("novo"), SECRET)
    assert (harness.disk(), harness.store.revision, harness.published()) == before


# -- escritas: candidato antes de persistir e publicar -------------------------


def test_create_verifies_persists_pinned_addresses_and_publishes(harness: _Harness) -> None:
    record = harness.service.create(draft("crm"), SECRET, expected_revision=1)
    assert record.resolved_addresses == (ADDRESS,)
    assert harness.published() == {"crm": 1}
    status = harness.registry.status().published[0]
    assert status.datasource_id == record.id
    assert status.record_revision == record.revision
    session = harness.registry.open_session("crm")
    session.close()


def test_create_disabled_persists_without_publishing(harness: _Harness) -> None:
    record = harness.service.create(draft("crm", enabled=False), SECRET, expected_revision=1)
    assert not record.enabled
    assert harness.published() == {}
    assert harness.factory.adapters == []  # nenhum candidato para desabilitado


@pytest.mark.parametrize("failure", [DatabaseError("x"), capability_failure(), RuntimeError("x")])
def test_candidate_failure_leaves_bytes_revision_and_registry_intact(
    harness: _Harness, failure: BaseException
) -> None:
    crm = harness.service.create(draft("crm"), SECRET, expected_revision=1)
    before = (harness.disk(), harness.store.revision, harness.published())
    harness.factory.connect_failure = failure

    with pytest.raises(DatasourceCandidateError):
        harness.service.create(draft("fin"), SECRET, expected_revision=2)
    with pytest.raises(DatasourceCandidateError):
        harness.service.rotate_secret(crm.id, OTHER_SECRET, expected_revision=2)
    with pytest.raises(DatasourceCandidateError):
        harness.service.update(crm.id, draft("crm", max_rows=10), expected_revision=2)

    assert (harness.disk(), harness.store.revision, harness.published()) == before
    assert harness.store.read_upstream_secret(crm.id) == SECRET
    assert harness.registry.status().candidates == 0
    assert harness.registry.status().retired_open == 0
    assert not harness.service.blocked


def test_rotate_secret_swaps_generation_and_keeps_old_session(harness: _Harness) -> None:
    crm = harness.service.create(draft("crm"), SECRET, expected_revision=1)
    session = harness.registry.open_session("crm")
    old_generation = session.generation

    rotated = harness.service.rotate_secret(crm.id, OTHER_SECRET, expected_revision=2)

    assert harness.store.read_upstream_secret(crm.id) == OTHER_SECRET
    assert harness.published()["crm"] > old_generation
    assert session.generation == old_generation
    fresh = harness.registry.open_session("crm")
    assert OTHER_SECRET in harness.factory.adapters[-1].conninfo
    assert SECRET in harness.factory.adapters[1].conninfo
    assert rotated.revision == crm.revision + 1
    session.close()
    fresh.close()
    assert harness.registry.status().retired_open == 0


def test_disable_drains_enable_verifies_again_and_remove_withdraws(harness: _Harness) -> None:
    crm = harness.service.create(draft("crm"), SECRET, expected_revision=1)
    session = harness.registry.open_session("crm")

    harness.service.set_enabled(crm.id, False, expected_revision=2)
    assert harness.published() == {}
    with pytest.raises(DatasourceUnavailableError):
        harness.registry.open_session("crm")
    # Sessao admitida drena na geracao que capturou.
    with session.use() as adapter:
        adapter.execute_validated("SELECT 1")
    assert harness.registry.status().retired_open == 1

    # No-op nao escreve.
    unchanged = harness.service.set_enabled(crm.id, False, expected_revision=3)
    assert unchanged.revision == harness.store.get(crm.id).revision
    assert harness.store.revision == 3

    # Habilitar de novo exige candidato verificado.
    harness.factory.connect_failure = DatabaseError("falha sintetica")
    with pytest.raises(DatasourceCandidateError):
        harness.service.set_enabled(crm.id, True, expected_revision=3)
    assert harness.store.revision == 3
    assert not harness.store.get(crm.id).enabled
    harness.factory.connect_failure = None
    session.close()
    harness.service.set_enabled(crm.id, True, expected_revision=3)
    assert set(harness.published()) == {"crm"}

    live = harness.registry.open_session("crm")
    harness.service.remove(crm.id, expected_revision=4)
    assert harness.published() == {}
    with pytest.raises(CatalogStoreError):
        harness.store.get(crm.id)
    live.close()
    assert harness.registry.status().retired_open == 0


def test_rename_is_refused_before_any_candidate(harness: _Harness) -> None:
    crm = harness.service.create(draft("crm"), SECRET, expected_revision=1)
    adapters = len(harness.factory.adapters)
    with pytest.raises(DatasourceRenameError):
        harness.service.update(crm.id, draft("crm-novo"), expected_revision=2)
    assert len(harness.factory.adapters) == adapters
    assert harness.store.revision == 2


def test_revision_conflict_and_duplicate_alias_fail_before_the_candidate(
    harness: _Harness,
) -> None:
    harness.service.create(draft("crm"), SECRET, expected_revision=1)
    adapters = len(harness.factory.adapters)
    with pytest.raises(CatalogRevisionConflictError):
        harness.service.create(draft("fin"), SECRET, expected_revision=1)
    with pytest.raises(CatalogStoreError):
        harness.service.create(draft("crm"), SECRET, expected_revision=2)
    assert len(harness.factory.adapters) == adapters


def test_busy_is_refused_before_building_the_candidate(tmp_path: Path) -> None:
    harness = _Harness(tmp_path, limits=RegistryLimits(max_retired=1))
    try:
        crm = harness.service.create(draft("crm"), SECRET, expected_revision=1)
        held = harness.registry.open_session("crm")
        harness.service.rotate_secret(crm.id, OTHER_SECRET, expected_revision=2)
        adapters = len(harness.factory.adapters)
        before = (harness.disk(), harness.store.revision, harness.published())

        with pytest.raises(DatasourceBusyError):
            harness.service.rotate_secret(crm.id, SECRET, expected_revision=3)
        with pytest.raises(DatasourceBusyError):
            harness.service.update(crm.id, draft("crm", max_rows=5), expected_revision=3)

        assert len(harness.factory.adapters) == adapters  # nenhuma conexao nova
        assert (harness.disk(), harness.store.revision, harness.published()) == before
        # Criar outro datasource nao aposenta nada e nao precisa da vaga.
        harness.service.create(draft("fin"), SECRET, expected_revision=3)
        # Desabilitar nao e recusado por limite.
        harness.service.set_enabled(crm.id, False, expected_revision=4)
        held.close()
    finally:
        harness.close()


def test_write_failure_before_replace_blocks_service_and_keeps_runtime(
    harness: _Harness,
) -> None:
    crm = harness.service.create(draft("crm"), SECRET, expected_revision=1)
    before_published = harness.published()
    before_disk = harness.disk()
    harness.crash.point = CrashPoint.AFTER_JOURNAL_FSYNC

    with pytest.raises(CatalogWriteError) as caught:
        harness.service.rotate_secret(crm.id, OTHER_SECRET, expected_revision=2)
    assert not isinstance(caught.value, CatalogOutcomeUncertainError)
    assert harness.published() == before_published
    assert harness.store_path.read_bytes() == before_disk[0]
    assert harness.service.blocked
    assert harness.registry.status().retired_open == 0
    with pytest.raises(DatasourceServiceBlockedError):
        harness.service.create(draft("fin"), SECRET, expected_revision=2)
    with pytest.raises(DatasourceServiceBlockedError):
        harness.service.remove(crm.id, expected_revision=2)
    # O store envenenado recusa ate leitura; um rascunho ainda pode ser testado,
    # porque nao toca no catalogo.
    with pytest.raises(CatalogWriteError):
        harness.service.test_datasource(crm.id)
    harness.service.test_draft(draft("fin"), SECRET)
    # Sessoes do runtime publicado continuam atendendo.
    harness.registry.open_session("crm").close()


def test_any_failure_that_poisons_the_store_blocks_the_service(harness: _Harness) -> None:
    crm = harness.service.create(draft("crm"), SECRET, expected_revision=1)

    def failing(point: CrashPoint) -> None:
        # Recusa de filesystem no meio do commit: envenena o store sem ser
        # `CatalogWriteError`.
        if point == CrashPoint.AFTER_JOURNAL_FSYNC:
            raise FilesystemPolicyError("falha sintetica de filesystem")

    harness.store._hooks = CatalogHooks(after_point=failing)
    with pytest.raises(FilesystemPolicyError):
        harness.service.rotate_secret(crm.id, OTHER_SECRET, expected_revision=2)
    assert not issubclass(FilesystemPolicyError, CatalogWriteError)
    assert harness.store.requires_reopen
    assert harness.service.blocked


def test_refusals_before_commit_do_not_block(harness: _Harness) -> None:
    harness.service.create(draft("crm"), SECRET, expected_revision=1)
    with pytest.raises(CatalogRevisionConflictError):
        harness.service.create(draft("fin"), SECRET, expected_revision=1)
    assert not harness.store.requires_reopen
    assert not harness.service.blocked


def test_disable_never_depends_on_dns(harness: _Harness) -> None:
    crm = harness.service.create(draft("crm"), SECRET, expected_revision=1)
    session = harness.registry.open_session("crm")

    def dns_down(_host: str, _port: int) -> tuple[str, ...]:
        from maskgw.datasource import DestinationValidationError  # noqa: PLC0415

        raise DestinationValidationError("destino nao resolvido")

    harness.service._resolver = dns_down
    record = harness.service.set_enabled(crm.id, False, expected_revision=2)
    assert not record.enabled
    assert record.resolved_addresses == crm.resolved_addresses
    assert harness.published() == {}
    # Reabilitar exige candidato, e o candidato depende de DNS: recusado.
    with pytest.raises(DatasourceCandidateError) as caught:
        harness.service.set_enabled(crm.id, True, expected_revision=3)
    assert caught.value.category is CandidateFailure.DESTINATION
    session.close()


def test_uncertain_enable_or_update_never_publishes(harness: _Harness) -> None:
    crm = harness.service.create(draft("crm"), SECRET, expected_revision=1)
    before = harness.published()
    harness.crash.point = CrashPoint.AFTER_STORE_REPLACE
    with pytest.raises(CatalogOutcomeUncertainError):
        harness.service.update(crm.id, draft("crm", max_rows=10), expected_revision=2)
    assert harness.published() == before
    assert harness.service.blocked


@pytest.mark.parametrize("operation", ["disable", "remove"])
def test_uncertain_disable_or_remove_withdraws_anyway(harness: _Harness, operation: str) -> None:
    crm = harness.service.create(draft("crm"), SECRET, expected_revision=1)
    session = harness.registry.open_session("crm")
    harness.crash.point = CrashPoint.AFTER_STORE_REPLACE
    with pytest.raises(CatalogOutcomeUncertainError):
        if operation == "disable":
            harness.service.set_enabled(crm.id, False, expected_revision=2)
        else:
            harness.service.remove(crm.id, expected_revision=2)
    # Reduzir exposicao nao espera confirmacao; a sessao admitida drena.
    assert harness.published() == {}
    assert harness.service.blocked
    session.close()
    assert harness.registry.status().retired_open == 0


def test_certain_failure_of_disable_keeps_the_datasource_published(harness: _Harness) -> None:
    crm = harness.service.create(draft("crm"), SECRET, expected_revision=1)
    harness.crash.point = CrashPoint.AFTER_JOURNAL_FSYNC
    with pytest.raises(CatalogWriteError):
        harness.service.set_enabled(crm.id, False, expected_revision=2)
    # O par antigo foi preservado: disco e runtime continuam concordando.
    assert set(harness.published()) == {"crm"}


def test_close_refuses_new_operations_and_is_idempotent(harness: _Harness) -> None:
    harness.service.close()
    harness.service.close()
    with pytest.raises(DatasourceServiceClosedError):
        harness.service.create(draft("crm"), SECRET, expected_revision=1)
    with pytest.raises(DatasourceServiceClosedError):
        harness.service.test_draft(draft("crm"), SECRET)


def test_errors_never_carry_secret_destination_or_alias(harness: _Harness) -> None:
    crm = harness.service.create(draft("crm"), SECRET, expected_revision=1)
    harness.factory.connect_failure = DatabaseError(f"{SECRET} {HOST}")
    failures: list[BaseException] = []
    for call in (
        lambda: harness.service.rotate_secret(crm.id, OTHER_SECRET, expected_revision=2),
        lambda: harness.service.test_draft(draft("fin"), SECRET),
        lambda: harness.service.update(crm.id, draft("outro"), expected_revision=2),
        lambda: harness.registry.open_session("inexistente"),
    ):
        with pytest.raises(Exception) as caught:
            call()
        failures.append(caught.value)
    for error in failures:
        text = f"{error!s} {error!r}"
        for canary in (SECRET, OTHER_SECRET, HOST, ADDRESS, "crm", "fin", "outro"):
            assert canary not in text


# -- startup fail-closed (F9-023) ------------------------------------------------


def _catalog_with(tmp_path: Path, *drafts: object) -> tuple[Path, Path]:
    store_path, anchor_path = _paths(tmp_path)
    with CatalogStore.initialize(store_path, anchor_path=anchor_path, master_key=KEY) as store:
        for item in drafts:
            store.create(item, SECRET, resolver=resolver)  # type: ignore[arg-type]
    return store_path, anchor_path


def _settings(tmp_path: Path, factory: FakeFactory, **kwargs: object) -> DatasourceCatalogSettings:
    store_path, anchor_path = _paths(tmp_path)
    return DatasourceCatalogSettings(
        store_path=store_path,
        anchor_path=anchor_path,
        resolver=kwargs.pop("resolver", resolver),  # type: ignore[arg-type]
        adapter_factory=factory,
        **kwargs,  # type: ignore[arg-type]
    )


def test_startup_publishes_every_enabled_and_skips_disabled(tmp_path: Path) -> None:
    _catalog_with(tmp_path, draft("crm"), draft("fin"), draft("hml", enabled=False))
    factory = FakeFactory()
    runtime = open_datasource_runtime(_settings(tmp_path, factory), secrets=secrets_provider())
    try:
        assert {item.alias for item in runtime.registry.status().published} == {"crm", "fin"}
        # Um candidato verificado por habilitado, e nenhuma conexao sobra.
        assert len(factory.adapters) == 2
        assert factory.open_adapters() == []
    finally:
        runtime.close()
        runtime.close()


@pytest.mark.parametrize("failure", ["connect", "capability", "dns", "key"])
def test_startup_fails_closed_and_releases_everything(tmp_path: Path, failure: str) -> None:
    store_path, anchor_path = _catalog_with(tmp_path, draft("crm"), draft("fin"))
    before = (store_path.read_bytes(), anchor_path.read_bytes())
    factory = FakeFactory()
    kwargs: dict[str, object] = {}
    provider = secrets_provider()
    if failure == "connect":
        factory.connect_failure = DatabaseError(SECRET)
    elif failure == "capability":
        factory.connect_failure = capability_failure()
    elif failure == "dns":
        kwargs["resolver"] = lambda _h, _p: ("10.0.0.99",)
    else:
        from maskgw.secretsource import MappingSecretProvider  # noqa: PLC0415

        provider = MappingSecretProvider({"MASKGW_DATASOURCE_MASTER_KEY": "0" * 64})

    with pytest.raises(Exception) as caught:
        open_datasource_runtime(_settings(tmp_path, factory, **kwargs), secrets=provider)
    assert SECRET not in str(caught.value)
    assert caught.value.__context__ is None or failure == "key"
    assert factory.open_adapters() == []
    assert (store_path.read_bytes(), anchor_path.read_bytes()) == before
    # Os locks do catalogo foram soltos: outro processo pode abri-lo.
    CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY).close()


def test_startup_failure_on_second_datasource_disposes_the_first(tmp_path: Path) -> None:
    _catalog_with(tmp_path, draft("crm"), draft("fin"))
    calls = {"count": 0}

    class _SecondFails(FakeFactory):
        def __call__(
            self, conninfo: str, *, config: GatewayConfig, engine: MaskingEngine
        ) -> PostgresAdapter:
            calls["count"] += 1
            self.connect_failure = DatabaseError("x") if calls["count"] == 2 else None
            return super().__call__(conninfo, config=config, engine=engine)

    failing = _SecondFails()
    from maskgw.runtime.datasources import DatasourceGeneration  # noqa: PLC0415

    disposed: list[int] = []
    original_dispose = DatasourceGeneration._dispose

    def counting(self: DatasourceGeneration) -> None:
        disposed.append(self.generation)
        original_dispose(self)

    DatasourceGeneration._dispose = counting  # type: ignore[method-assign]
    try:
        with pytest.raises(DatasourceCandidateError):
            open_datasource_runtime(_settings(tmp_path, failing), secrets=secrets_provider())
    finally:
        DatasourceGeneration._dispose = original_dispose  # type: ignore[method-assign]
    assert disposed == [1]
    assert failing.open_adapters() == []


def test_startup_with_missing_catalog_or_key_fails_closed(tmp_path: Path) -> None:
    from maskgw.secretsource import MappingSecretProvider  # noqa: PLC0415

    with pytest.raises(CatalogStoreError):
        open_datasource_runtime(_settings(tmp_path, FakeFactory()), secrets=secrets_provider())
    _catalog_with(tmp_path, draft("crm"))
    with pytest.raises(CatalogStoreError):
        open_datasource_runtime(
            _settings(tmp_path, FakeFactory()), secrets=MappingSecretProvider({})
        )


def test_startup_does_not_verify_or_open_disabled_datasources(tmp_path: Path) -> None:
    _catalog_with(tmp_path, draft("hml", enabled=False))
    factory = FakeFactory(connect_failure=DatabaseError("nunca chamado"))
    runtime = open_datasource_runtime(_settings(tmp_path, factory), secrets=secrets_provider())
    try:
        assert runtime.registry.status().published == ()
        assert factory.adapters == []
    finally:
        runtime.close()


def test_destination_policy_is_revalidated_on_startup(tmp_path: Path) -> None:
    item = dataclasses.replace(draft("crm"), destination_policy=DestinationPolicy())
    _catalog_with(tmp_path, item)
    factory = FakeFactory()
    with pytest.raises(DatasourceCandidateError) as caught:
        open_datasource_runtime(
            _settings(tmp_path, factory, resolver=lambda _h, _p: ("127.0.0.1",)),
            secrets=secrets_provider(),
        )
    assert caught.value.category is CandidateFailure.DESTINATION
    assert factory.adapters == []
