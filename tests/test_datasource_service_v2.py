"""Fase 9, Etapa 4: acrescimos do coordenador para a Admin API v2 (D-094).

Sem HTTP: a revision por datasource, a mutacao e a confirmacao DENTRO da secao
critica, o probe de revisions, a recusa de teste de datasource desabilitado e
a compilacao da politica de um datasource desabilitado.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from maskgw.datasource import CatalogHooks, CatalogStore, CatalogWriteError, CrashPoint
from maskgw.datasource.models import DatasourcePolicy, DatasourceRecord
from maskgw.runtime.candidate import CandidateFailure, DatasourceCandidateError
from maskgw.runtime.datasource_service import (
    DatasourceDisabledError,
    DatasourceNotFoundError,
    DatasourceRevisionConflictError,
    DatasourceRuntimeService,
    DatasourceWriteProbe,
    draft_from_record,
)
from maskgw.runtime.datasources import DatasourceRegistry
from maskgw.secretsource import SecretProvider
from tests.datasource_runtime_support import HMAC_KEY as HMAC
from tests.datasource_runtime_support import KEY, SECRET, FakeFactory, draft, resolver

BAD_POLICY = DatasourcePolicy.from_mapping(
    {"masking": [{"match": "x", "transformer": "nao_existe"}]}
)
MISSING = "dso_" + "f" * 32


class _Secrets(SecretProvider):
    """Provider mutavel: a chave HMAC pode sumir do ambiente entre escritas."""

    def __init__(self) -> None:
        self.values = {"MASKGW_DATASOURCE_MASTER_KEY": KEY, "MASKGW_HMAC_KEY": HMAC}

    def get(self, name: str) -> str | None:
        return self.values.get(name)


class _Crash:
    def __init__(self) -> None:
        self.point: CrashPoint | None = None

    def __call__(self, point: CrashPoint) -> None:
        if point == self.point:
            self.point = None
            msg = "falha sintetica"
            raise CatalogWriteError(msg)


class _Harness:
    def __init__(self, tmp_path: Path) -> None:
        store_path = tmp_path / "datasources.store"
        anchor_path = tmp_path / "anchor" / "datasources.anchor"
        CatalogStore.initialize(store_path, anchor_path=anchor_path, master_key=KEY).close()
        self.crash = _Crash()
        self.store = CatalogStore.open(
            store_path,
            anchor_path=anchor_path,
            master_key=KEY,
            hooks=CatalogHooks(after_point=self.crash),
        )
        self.secrets = _Secrets()
        self.factory = FakeFactory()
        self.registry = DatasourceRegistry()
        self.service = DatasourceRuntimeService(
            store=self.store,
            registry=self.registry,
            secrets=self.secrets,
            resolver=resolver,
            adapter_factory=self.factory,
        )

    def close(self) -> None:
        self.service.close()
        self.registry.close()
        self.store.close()


@pytest.fixture
def h(tmp_path: Path) -> Iterator[_Harness]:
    value = _Harness(tmp_path)
    try:
        yield value
    finally:
        value.close()


def test_exactly_one_revision_form_is_accepted(h: _Harness) -> None:
    record = h.service.create(draft("crm"), SECRET, expected_revision=1)
    with pytest.raises(ValueError, match="exatamente uma"):
        h.service.set_enabled(record.id, False)
    with pytest.raises(ValueError, match="exatamente uma"):
        h.service.set_enabled(record.id, False, expected_revision=2, expected_datasource_revision=1)


def test_datasource_revision_is_checked_under_the_lock(h: _Harness) -> None:
    a = h.service.create(draft("crm"), SECRET, expected_revision=1)
    b = h.service.create(draft("fin"), SECRET, expected_revision=2)
    # Uma escrita em B nao invalida a revision propria de A.
    h.service.set_enabled(b.id, False, expected_datasource_revision=1)
    updated = h.service.update(
        a.id, replace(draft("crm"), display_name="Novo"), expected_datasource_revision=1
    )
    assert updated.revision == 2
    with pytest.raises(DatasourceRevisionConflictError) as caught:
        h.service.update(a.id, draft("crm"), expected_datasource_revision=1)
    assert caught.value.current_revision == 2
    with pytest.raises(DatasourceRevisionConflictError) as catalog:
        h.service.remove(a.id, expected_revision=1)
    assert catalog.value.current_revision == h.store.revision
    with pytest.raises(DatasourceNotFoundError):
        h.service.remove(MISSING, expected_datasource_revision=1)


def test_mutation_and_confirmation_run_inside_the_critical_section(h: _Harness) -> None:
    record = h.service.create(draft("crm"), SECRET, expected_revision=1)
    seen: list[tuple[bool, int]] = []

    def mutate(current: DatasourceRecord) -> object:
        seen.append((h.service._lock.locked(), current.revision))
        return replace(draft_from_record(current), display_name="Sob lock")

    h.service.update(record.id, mutate, expected_datasource_revision=1)  # type: ignore[arg-type]
    assert seen == [(True, 1)]

    confirmed: list[bool] = []

    def refuse(_current: DatasourceRecord) -> None:
        confirmed.append(h.service._lock.locked())
        msg = "confirmacao recusada"
        raise LookupError(msg)

    revision = h.store.revision
    with pytest.raises(LookupError):
        h.service.remove(record.id, expected_datasource_revision=2, confirm=refuse)
    assert confirmed == [True]
    assert h.store.revision == revision
    assert h.store.get(record.id).alias == "crm"


def test_probe_records_revisions_observed_under_the_lock(h: _Harness) -> None:
    probe = DatasourceWriteProbe()
    record = h.service.create(draft("crm"), SECRET, expected_revision=1, probe=probe)
    assert (probe.catalog_revision_before, probe.catalog_revision_after) == (1, 2)

    idle = DatasourceWriteProbe()
    h.service.set_enabled(record.id, True, expected_datasource_revision=1, probe=idle)
    assert (idle.catalog_revision_before, idle.catalog_revision_after) == (2, 2)

    refused = DatasourceWriteProbe()
    with pytest.raises(DatasourceRevisionConflictError):
        h.service.update(record.id, draft("crm"), expected_datasource_revision=9, probe=refused)
    assert refused.catalog_revision_after is None

    uncertain = DatasourceWriteProbe()
    h.crash.point = CrashPoint.AFTER_STORE_REPLACE
    with pytest.raises(CatalogWriteError):
        h.service.set_enabled(record.id, False, expected_datasource_revision=1, probe=uncertain)
    assert uncertain.catalog_revision_before == 2
    assert uncertain.catalog_revision_after is None


def test_a_disabled_datasource_is_never_tested(h: _Harness) -> None:
    record = h.service.create(draft("crm", enabled=False), SECRET, expected_revision=1)
    with pytest.raises(DatasourceDisabledError):
        h.service.test_datasource(record.id)
    assert h.factory.adapters == []
    with pytest.raises(DatasourceNotFoundError):
        h.service.test_datasource(MISSING)


def test_disabled_writes_compile_a_new_policy(h: _Harness) -> None:
    with pytest.raises(DatasourceCandidateError) as caught:
        h.service.create(
            replace(draft("crm", enabled=False), policy=BAD_POLICY), SECRET, expected_revision=1
        )
    assert caught.value.category is CandidateFailure.POLICY
    assert h.store.revision == 1
    record = h.service.create(draft("crm", enabled=False), SECRET, expected_revision=1)
    with pytest.raises(DatasourceCandidateError):
        h.service.update(
            record.id,
            lambda current: replace(draft_from_record(current), policy=BAD_POLICY),
            expected_datasource_revision=1,
        )
    assert h.store.get(record.id).revision == 1
    assert h.factory.adapters == []


def test_disabling_never_depends_on_the_policy_still_compiling(h: _Harness) -> None:
    record = h.service.create(draft("crm"), SECRET, expected_revision=1)
    # A chave HMAC da politica sumiu do ambiente: reduzir exposicao continua possivel.
    del h.secrets.values["MASKGW_HMAC_KEY"]
    disabled = h.service.set_enabled(record.id, False, expected_datasource_revision=1)
    assert disabled.enabled is False
    assert h.registry.status().published == ()
    h.service.remove(record.id, expected_datasource_revision=2)
    assert h.store.snapshot().datasources == ()


def test_concurrent_updates_of_one_datasource_have_one_winner(h: _Harness) -> None:
    record = h.service.create(draft("crm"), SECRET, expected_revision=1)
    barrier = threading.Barrier(6)
    outcomes: list[str] = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        barrier.wait()
        try:
            h.service.update(
                record.id,
                replace(draft("crm"), display_name=f"W{index}"),
                expected_datasource_revision=1,
            )
            result = "ok"
        except DatasourceRevisionConflictError:
            result = "conflict"
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert sorted(outcomes) == ["conflict"] * 5 + ["ok"]
    assert h.store.get(record.id).revision == 2
    (published,) = h.registry.status().published
    assert published.record_revision == 2
    assert h.registry.status().candidates == 0
    assert h.factory.open_adapters() == []


def test_failure_before_replace_is_certain_and_blocks(h: _Harness) -> None:
    record = h.service.create(draft("crm"), SECRET, expected_revision=1)
    h.crash.point = CrashPoint.AFTER_JOURNAL_FSYNC
    with pytest.raises(CatalogWriteError):
        h.service.update(record.id, draft("crm"), expected_datasource_revision=1)
    assert h.service.blocked
    assert h.store.requires_reopen
