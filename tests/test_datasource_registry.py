"""Fase 9, Etapa 3: registry multi-datasource sem banco (F9-020, F9-021).

Cada teste prova uma regra do docstring de `maskgw.runtime.datasources`, com
adapters dublês que registram conexao, fechamento e cancelamento. A integracao
com PostgreSQL 16 real esta em `test_datasource_runtime_integration.py`.
"""

from __future__ import annotations

import random
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from maskgw.config.gateway import GatewayConfig
from maskgw.db.postgres import PostgresAdapter
from maskgw.errors import CapabilityError, DatabaseError
from maskgw.masking.engine import MaskingEngine
from maskgw.runtime.datasources import (
    MAX_CANDIDATES_PER_DATASOURCE,
    MAX_RETIRED_PER_DATASOURCE,
    DatasourceBusyError,
    DatasourceGeneration,
    DatasourceRegistry,
    DatasourceRegistryClosedError,
    DatasourceUnavailableError,
    RegistryLimits,
)
from tests.datasource_runtime_support import (
    DS_A,
    DS_B,
    DS_C,
    SECRET,
    FakeFactory,
    capability_failure,
    prepared,
)


def _publish(  # noqa: PLR0913 - apoio de teste, keyword-only
    registry: DatasourceRegistry,
    factory: FakeFactory,
    datasource_id: str,
    alias: str,
    *,
    max_sessions: int = 8,
    record_revision: int = 1,
) -> DatasourceGeneration:
    with registry.reserve(datasource_id, datasource_id=datasource_id, publish=True) as slot:
        return slot.publish(
            datasource_id=datasource_id,
            alias=alias,
            record_revision=record_revision,
            prepared=prepared(factory, max_sessions=max_sessions),
        )


def _disposed(generation: DatasourceGeneration) -> bool:
    return generation._prepared is None


# -- geracoes, admissao e release -------------------------------------------


def test_session_captures_published_generation_with_its_own_connection() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry()
    generation = _publish(registry, factory, DS_A, "crm")

    first = registry.open_session("crm")
    second = registry.open_session("crm")

    assert first.generation == second.generation == generation.generation
    # D-071: uma conexao upstream POR sessao, nunca compartilhada.
    assert len(factory.adapters) == 2
    assert all(adapter.connected for adapter in factory.adapters)
    assert registry.status().published[0].sessions == 2

    first.close()
    first.close()  # idempotente: um unico release
    assert registry.status().published[0].sessions == 1
    second.close()
    assert registry.status().sessions == 0
    assert not any(adapter.connected for adapter in factory.adapters)
    registry.close()


def test_generation_numbers_are_monotonic_and_never_reused() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry()
    first = _publish(registry, factory, DS_A, "crm")
    second = _publish(registry, factory, DS_A, "crm", record_revision=2)
    other = _publish(registry, factory, DS_B, "fin")
    assert registry.withdraw(DS_A)
    # Mesmo alias, outro datasource depois da remocao: numero novo.
    recreated = _publish(registry, factory, DS_C, "crm")

    numbers = [first.generation, second.generation, other.generation, recreated.generation]
    assert numbers == sorted(numbers)
    assert len(set(numbers)) == 4
    registry.close()


def test_unknown_disabled_and_removed_aliases_share_one_fixed_error() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry()
    _publish(registry, factory, DS_A, "crm")
    _publish(registry, factory, DS_B, "fin")
    registry.withdraw(DS_B)

    messages = set()
    for alias in ("inexistente", "fin", "CRM", "crm;drop", ""):
        with pytest.raises(DatasourceUnavailableError) as caught:
            registry.open_session(alias)
        messages.add(str(caught.value))
        # Nunca ecoa o alias pedido nem o publicado.
        assert alias not in str(caught.value) or alias == ""
        assert "crm" not in str(caught.value)
    assert messages == {"datasource indisponivel"}
    assert factory.adapters == []  # nenhuma conexao aberta para alias recusado
    registry.close()


def test_swap_keeps_admitted_session_on_old_generation_and_closes_it_once() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry()
    old = _publish(registry, factory, DS_A, "crm")
    session = registry.open_session("crm")

    new = _publish(registry, factory, DS_A, "crm", record_revision=2)

    # Regra 2: a sessao admitida continua na geracao que capturou.
    assert session.generation == old.generation
    assert registry.status().retired_open == 1
    assert not _disposed(old)
    # Regra 5: sessao nova so na geracao publicada.
    fresh = registry.open_session("crm")
    assert fresh.generation == new.generation

    session.close()
    # Regra 4: o ultimo release fecha a aposentada, exatamente uma vez.
    assert _disposed(old)
    assert "closed=True" in repr(old)
    assert registry.status().retired_open == 0
    session.close()
    assert registry.status().retired_open == 0
    fresh.close()
    registry.close()


def test_idle_generation_is_closed_by_the_swap_itself() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry()
    old = _publish(registry, factory, DS_A, "crm")
    _publish(registry, factory, DS_A, "crm", record_revision=2)
    assert _disposed(old)
    assert "retired=True, closed=True" in repr(old)
    assert registry.status().retired_open == 0
    registry.close()


def test_dispose_drops_the_connection_target_and_blocks_new_adapters() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry()
    old = _publish(registry, factory, DS_A, "crm")
    _publish(registry, factory, DS_A, "crm", record_revision=2)
    with pytest.raises(DatasourceUnavailableError):
        _ = old.prepared
    registry.close()


def test_withdraw_drains_without_redirecting_admitted_sessions() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry()
    generation = _publish(registry, factory, DS_A, "crm")
    session = registry.open_session("crm")

    assert registry.withdraw(DS_A) is True
    assert registry.withdraw(DS_A) is False  # idempotente
    with pytest.raises(DatasourceUnavailableError):
        registry.open_session("crm")
    # A sessao admitida continua utilizavel, na mesma geracao, ate terminar.
    with session.use() as adapter:
        adapter.execute_validated("SELECT 1")
    assert not _disposed(generation)
    session.close()
    assert _disposed(generation)
    registry.close()


def test_failure_and_swap_of_one_datasource_never_touch_another() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry()
    crm = _publish(registry, factory, DS_A, "crm", max_sessions=1)
    fin = _publish(registry, factory, DS_B, "fin", max_sessions=1)
    fin_session = registry.open_session("fin")

    crm_session = registry.open_session("crm")
    with pytest.raises(DatasourceBusyError):
        registry.open_session("crm")
    _publish(registry, factory, DS_A, "crm", record_revision=2)
    registry.withdraw(DS_A)

    # A troca, a lotacao e a retirada do CRM nao mudaram nada no financeiro.
    status = {item.alias: item for item in registry.status().published}
    assert set(status) == {"fin"}
    assert status["fin"].generation == fin.generation
    assert status["fin"].sessions == 1
    with fin_session.use() as adapter:
        adapter.execute_validated("SELECT 1")
    assert not _disposed(fin)
    crm_session.close()
    assert _disposed(crm)
    fin_session.close()
    registry.close()


def test_admission_never_enters_a_retired_generation_even_if_published() -> None:
    """Regra 5 como invariante: nem um estado corrompido admite na aposentada."""
    factory = FakeFactory()
    registry = DatasourceRegistry()
    generation = _publish(registry, factory, DS_A, "crm")
    generation._retired = True
    with pytest.raises(DatasourceUnavailableError):
        registry.open_session("crm")
    generation._retired = False
    generation._closed = True
    with pytest.raises(DatasourceUnavailableError):
        registry.open_session("crm")
    assert factory.adapters == []
    generation._closed = False
    registry.close()


def test_adapter_construction_failure_leaves_no_admission_counted() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry()
    generation = _publish(registry, factory, DS_A, "crm", max_sessions=1)

    def exploding(
        conninfo: str, *, config: GatewayConfig, engine: MaskingEngine
    ) -> PostgresAdapter:
        del conninfo, config, engine
        raise RuntimeError("fabrica sintetica")

    generation.prepared._adapter_factory = exploding
    for _ in range(3):
        with pytest.raises(RuntimeError):
            registry.open_session("crm")
    assert registry.status().sessions == 0
    assert generation._sessions == 0
    generation.prepared._adapter_factory = factory
    registry.open_session("crm").close()
    # Sem contagem presa, a retirada fecha a geracao na hora.
    registry.withdraw(DS_A)
    assert registry.status().retired_open == 0
    registry.close()


def test_connect_failure_releases_the_admission_and_leaks_nothing() -> None:
    factory = FakeFactory(connect_failure=DatabaseError("falha sintetica"))
    registry = DatasourceRegistry(RegistryLimits(max_sessions=1))
    _publish(registry, factory, DS_A, "crm", max_sessions=1)

    for _ in range(3):
        with pytest.raises(DatabaseError):
            registry.open_session("crm")
    assert registry.status().sessions == 0
    assert all(adapter.closes >= 1 for adapter in factory.adapters)

    factory.connect_failure = capability_failure()
    with pytest.raises(CapabilityError):
        registry.open_session("crm")
    factory.connect_failure = None
    # O limite de 1 continua livre: nenhuma admissao ficou presa.
    registry.open_session("crm").close()
    registry.close()


# -- limites (D-089) ----------------------------------------------------------


def test_per_datasource_session_limit_counts_draining_generations() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry()
    _publish(registry, factory, DS_A, "crm", max_sessions=2)
    first = registry.open_session("crm")
    second = registry.open_session("crm")
    _publish(registry, factory, DS_A, "crm", max_sessions=2, record_revision=2)

    # As duas sessoes da geracao aposentada ainda contam para o datasource.
    with pytest.raises(DatasourceBusyError):
        registry.open_session("crm")
    first.close()
    third = registry.open_session("crm")
    assert third.generation != second.generation
    second.close()
    third.close()
    registry.close()


def test_global_session_limit_is_checked_before_the_alias() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry(RegistryLimits(max_sessions=2))
    _publish(registry, factory, DS_A, "crm")
    _publish(registry, factory, DS_B, "fin")
    sessions = [registry.open_session("crm"), registry.open_session("fin")]

    # Lotado, o erro e o mesmo para alias existente e inexistente: a lotacao
    # global nao revela o catalogo.
    for alias in ("crm", "inexistente"):
        with pytest.raises(DatasourceBusyError):
            registry.open_session(alias)
    assert len(factory.adapters) == 2  # nenhuma conexao aberta alem do limite
    for session in sessions:
        session.close()
    registry.close()


def test_candidate_limits_are_refused_before_anything_is_built() -> None:
    registry = DatasourceRegistry(RegistryLimits(max_candidates=2))
    first = registry.reserve(DS_A, publish=False)
    assert MAX_CANDIDATES_PER_DATASOURCE == 1
    with pytest.raises(DatasourceBusyError):
        registry.reserve(DS_A, publish=False)
    second = registry.reserve(DS_B, publish=False)
    with pytest.raises(DatasourceBusyError):
        registry.reserve(DS_C, publish=False)
    assert registry.status().candidates == 2

    first.release()
    first.release()  # idempotente
    third = registry.reserve(DS_C, publish=False)
    second.release()
    third.release()
    assert registry.status().candidates == 0
    registry.close()


def test_retired_limits_per_datasource_and_global() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry(RegistryLimits(max_retired=2))
    _publish(registry, factory, DS_C, "hml")
    held = []
    for datasource_id, alias in ((DS_A, "crm"), (DS_B, "fin")):
        _publish(registry, factory, datasource_id, alias)
        held.append(registry.open_session(alias))
        _publish(registry, factory, datasource_id, alias, record_revision=2)
    assert registry.status().retired_open == 2
    assert MAX_RETIRED_PER_DATASOURCE == 1

    # Por datasource: CRM ja tem uma aposentada drenando; outra troca espera.
    with pytest.raises(DatasourceBusyError):
        registry.reserve(DS_A, datasource_id=DS_A, publish=True)
    # Global: duas aposentadas abertas, limite 2, ate para a troca de um terceiro.
    with pytest.raises(DatasourceBusyError):
        registry.reserve(DS_C, datasource_id=DS_C, publish=True)
    # Publicar um datasource sem geracao (criar/reabilitar) nao aposenta nada.
    new_id = "dso_" + "d" * 32
    _publish(registry, factory, new_id, "novo")
    # Um teste de candidato nao publica e nao depende das aposentadas.
    registry.reserve("dso_" + "e" * 32, publish=False).release()
    # Retirar nunca e recusado por limite: so reduz exposicao.
    assert registry.withdraw(DS_A)
    # A geracao retirada estava ociosa: fechou na propria retirada.
    assert registry.status().retired_open == 2
    assert "crm" not in {item.alias for item in registry.status().published}

    for session in held:
        session.close()
    assert registry.status().retired_open == 0
    _publish(registry, factory, DS_C, "hml", record_revision=2)
    registry.close()


def test_reenabling_while_old_generation_drains_needs_no_retired_slot() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry(RegistryLimits(max_retired=1))
    old = _publish(registry, factory, DS_A, "crm")
    session = registry.open_session("crm")
    registry.withdraw(DS_A)
    # Desabilitado e drenando: reabilitar publica sem aposentar nada.
    new = _publish(registry, factory, DS_A, "crm", record_revision=3)
    assert registry.status().retired_open == 1
    assert session.generation == old.generation != new.generation
    # Mas uma TROCA agora excederia a aposentada unica do datasource.
    with pytest.raises(DatasourceBusyError):
        registry.reserve(DS_A, datasource_id=DS_A, publish=True)
    session.close()
    registry.close()


def test_reservation_holds_the_retired_slot_until_publication() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry(RegistryLimits(max_retired=1, max_candidates=2))
    _publish(registry, factory, DS_A, "crm")
    _publish(registry, factory, DS_B, "fin")
    sessions = [registry.open_session("crm"), registry.open_session("fin")]
    slot = registry.reserve(DS_A, datasource_id=DS_A, publish=True)
    # A unica vaga de aposentado esta reservada: outra troca nao entra.
    with pytest.raises(DatasourceBusyError):
        registry.reserve(DS_B, datasource_id=DS_B, publish=True)
    slot.publish(datasource_id=DS_A, alias="crm", record_revision=2, prepared=prepared(factory))
    slot.release()
    with pytest.raises(RuntimeError):
        slot.publish(datasource_id=DS_A, alias="crm", record_revision=3, prepared=prepared(factory))
    # A reserva virou a aposentada real: a vaga continua ocupada ate drenar.
    with pytest.raises(DatasourceBusyError):
        registry.reserve(DS_B, datasource_id=DS_B, publish=True)
    sessions[0].close()
    registry.reserve(DS_B, datasource_id=DS_B, publish=True).release()
    sessions[1].close()
    registry.close()


def test_released_reservation_returns_its_retired_slot() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry(RegistryLimits(max_retired=1))
    _publish(registry, factory, DS_A, "crm")
    for _ in range(3):
        # Candidato falhou: a reserva sai sem publicar e devolve a vaga.
        registry.reserve(DS_A, datasource_id=DS_A, publish=True).release()
    _publish(registry, factory, DS_A, "crm", record_revision=2)
    registry.close()


def test_publication_invariants_refuse_alias_takeover_and_rename() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry()
    _publish(registry, factory, DS_A, "crm")
    with pytest.raises(RuntimeError):
        _publish(registry, factory, DS_B, "crm")
    with pytest.raises(RuntimeError):
        _publish(registry, factory, DS_A, "outro")
    test_slot = registry.reserve(DS_C, publish=False)
    with pytest.raises(RuntimeError):
        test_slot.publish(
            datasource_id=DS_C, alias="hml", record_revision=1, prepared=prepared(factory)
        )
    test_slot.release()
    assert [item.alias for item in registry.status().published] == ["crm"]
    registry.close()


def test_invalid_global_limits_are_refused() -> None:
    for kwargs in ({"max_sessions": 0}, {"max_retired": -1}, {"max_candidates": True}):
        with pytest.raises(ValueError, match="limite do registry invalido"):
            RegistryLimits(**kwargs)


# -- shutdown (D-090) -------------------------------------------------------


def test_shutdown_cancels_in_flight_closes_idle_and_waits_every_release() -> None:
    factory = FakeFactory(block_execution=True)
    registry = DatasourceRegistry()
    generation = _publish(registry, factory, DS_A, "crm")
    idle = registry.open_session("crm")
    busy = registry.open_session("crm")
    busy_adapter = factory.adapters[1]
    outcome: list[BaseException | None] = []

    def run_query() -> None:
        try:
            with busy.use() as adapter:
                adapter.execute_validated("SELECT pg_sleep(60)")
            outcome.append(None)
        except BaseException as exc:
            outcome.append(exc)

    worker = threading.Thread(target=run_query, daemon=True)
    worker.start()
    assert busy_adapter.started.wait(timeout=5)

    registry.close()
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert busy_adapter.cancels == 1
    assert isinstance(outcome[0], DatabaseError)
    assert idle.closed
    assert busy.closed
    assert factory.open_adapters() == []
    assert _disposed(generation)
    assert registry.status().sessions == 0
    with pytest.raises(DatasourceUnavailableError):
        registry.open_session("crm")
    with pytest.raises(DatasourceUnavailableError), idle.use():
        pass
    with pytest.raises(DatasourceRegistryClosedError):
        registry.reserve(DS_B, publish=False)
    registry.close()  # idempotente


def test_shutdown_waits_for_query_finishing_between_check_and_release() -> None:
    """Fase 2 do shutdown: nenhuma sessao sobra aberta pela janela da marca."""
    factory = FakeFactory()
    registry = DatasourceRegistry()
    _publish(registry, factory, DS_A, "crm")
    lease = registry.open_session("crm")
    lease._lock.acquire()
    closer = threading.Thread(target=registry.close, daemon=True)
    closer.start()
    try:
        # O shutdown so pode cancelar enquanto o lock da sessao esta ocupado, e
        # repete o pedido: o primeiro pode ter chegado antes do statement existir.
        for _ in range(400):
            if factory.adapters[0].cancels >= 2:
                break
            threading.Event().wait(0.01)
        assert factory.adapters[0].cancels >= 2
        assert closer.is_alive()
    finally:
        lease._lock.release()
    closer.join(timeout=5)
    assert not closer.is_alive()
    assert lease.closed
    assert registry.status().sessions == 0


def test_session_marked_during_query_closes_itself_on_exit() -> None:
    """A saida de `use()` fecha a sessao marcada, sem depender da fase 2."""
    factory = FakeFactory(block_execution=True)
    registry = DatasourceRegistry()
    _publish(registry, factory, DS_A, "crm")
    lease = registry.open_session("crm")
    errors: list[BaseException] = []

    def run() -> None:
        try:
            with lease.use() as adapter:
                adapter.execute_validated("SELECT 1")
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    assert factory.adapters[0].started.wait(timeout=5)
    lease._request_termination()  # so a fase 1
    worker.join(timeout=5)
    assert lease.closed
    assert registry.status().sessions == 0
    assert isinstance(errors[0], DatabaseError)
    registry.close()


def test_shutdown_waits_for_candidate_in_flight() -> None:
    registry = DatasourceRegistry()
    reservation = registry.reserve(DS_A, publish=False)
    closer = threading.Thread(target=registry.close, daemon=True)
    closer.start()
    closer.join(timeout=0.3)
    # Um teste de conexao em voo segura a conexao de verificacao: o shutdown
    # nao pode terminar antes dele.
    assert closer.is_alive()
    reservation.release()
    closer.join(timeout=5)
    assert not closer.is_alive()


def test_shutdown_during_session_connect_never_closes_under_connect() -> None:
    gate = threading.Event()
    factory = FakeFactory(connect_gate=gate)
    registry = DatasourceRegistry()
    _publish(registry, factory, DS_A, "crm")
    result: list[BaseException | object] = []

    def admit() -> None:
        try:
            result.append(registry.open_session("crm"))
        except BaseException as exc:
            result.append(exc)

    worker = threading.Thread(target=admit, daemon=True)
    worker.start()
    assert factory.connect_started.wait(timeout=5)
    closer = threading.Thread(target=registry.close, daemon=True)
    closer.start()
    for _ in range(200):
        if factory.adapters[0].cancels:
            break
        threading.Event().wait(0.01)
    # Durante o connect o shutdown so marca e cancela; nao fecha.
    assert factory.adapters[0].closes == 0
    gate.set()
    worker.join(timeout=5)
    closer.join(timeout=5)
    assert isinstance(result[0], DatasourceUnavailableError)
    assert factory.adapters[0].closes == 1
    assert registry.status().sessions == 0


def test_concurrent_shutdown_calls_run_the_sequence_once() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry()
    generations = [_publish(registry, factory, DS_A, "crm")]
    sessions = [registry.open_session("crm") for _ in range(4)]
    generations.append(_publish(registry, factory, DS_A, "crm", record_revision=2))
    sessions.append(registry.open_session("crm"))
    with ThreadPoolExecutor(max_workers=8) as pool:
        for future in [pool.submit(registry.close) for _ in range(8)]:
            future.result(timeout=10)
    assert all(session.closed for session in sessions)
    assert all(_disposed(generation) for generation in generations)
    assert all(adapter.closes == 1 for adapter in factory.adapters)


def test_begin_shutdown_stops_admission_but_lets_reserved_publication_finish() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry()
    _publish(registry, factory, DS_A, "crm")
    slot = registry.reserve(DS_B, datasource_id=DS_B, publish=True)
    registry.begin_shutdown()
    with pytest.raises(DatasourceUnavailableError):
        registry.open_session("crm")
    with pytest.raises(DatasourceRegistryClosedError):
        registry.reserve(DS_C, publish=False)
    generation = slot.publish(
        datasource_id=DS_B, alias="fin", record_revision=1, prepared=prepared(factory)
    )
    slot.release()
    registry.close()
    assert _disposed(generation)


# -- concorrencia -------------------------------------------------------------


def test_concurrent_admission_swaps_and_withdrawals_keep_every_invariant() -> None:  # noqa: PLR0915
    factory = FakeFactory()
    registry = DatasourceRegistry(RegistryLimits(max_sessions=24, max_retired=4))
    aliases = {DS_A: "crm", DS_B: "fin"}
    for datasource_id, alias in aliases.items():
        _publish(registry, factory, datasource_id, alias, max_sessions=12)
    disposals: list[int] = []
    original_dispose = DatasourceGeneration._dispose

    def counting_dispose(self: DatasourceGeneration) -> None:
        with factory.lock:
            disposals.append(self.generation)
        original_dispose(self)

    stop = threading.Event()
    errors: list[BaseException] = []

    def client(seed: int) -> None:
        rng = random.Random(seed)  # noqa: S311 - so embaralha o teste
        while not stop.is_set():
            alias = rng.choice(("crm", "fin"))
            try:
                lease = registry.open_session(alias)
            except (DatasourceBusyError, DatasourceUnavailableError):
                continue
            try:
                generation = lease._generation
                # Regra 5: nunca admitida numa geracao aposentada no instante
                # da admissao; a geracao capturada continua viva ate o release.
                assert not generation._closed
                with lease.use() as adapter:
                    adapter.execute_validated("SELECT 1")
                assert not generation._closed
            except BaseException as exc:
                errors.append(exc)
            finally:
                lease.close()

    def admin(seed: int) -> None:
        rng = random.Random(seed)  # noqa: S311 - so embaralha o teste
        revision = 2
        while not stop.is_set():
            datasource_id = rng.choice((DS_A, DS_B))
            try:
                if rng.random() < 0.2:
                    registry.withdraw(datasource_id)
                _publish(
                    registry,
                    factory,
                    datasource_id,
                    aliases[datasource_id],
                    max_sessions=12,
                    record_revision=revision,
                )
                revision += 1
            except DatasourceBusyError:
                continue

    DatasourceGeneration._dispose = counting_dispose  # type: ignore[method-assign]
    try:
        threads = [threading.Thread(target=client, args=(seed,), daemon=True) for seed in range(10)]
        threads.append(threading.Thread(target=admin, args=(99,), daemon=True))
        for thread in threads:
            thread.start()
        threading.Event().wait(1.5)
        stop.set()
        for thread in threads:
            thread.join(timeout=10)
        registry.close()
    finally:
        DatasourceGeneration._dispose = original_dispose  # type: ignore[method-assign]

    assert errors == []
    assert len(disposals) == len(set(disposals))  # cada geracao descartada uma vez
    assert registry.status().sessions == 0
    assert registry.status().retired_open == 0
    assert factory.open_adapters() == []
    assert all(adapter.closes == 1 for adapter in factory.adapters)


def test_representations_never_carry_alias_target_or_secret() -> None:
    factory = FakeFactory()
    registry = DatasourceRegistry()
    generation = _publish(registry, factory, DS_A, "crm")
    lease = registry.open_session("crm")
    slot = registry.reserve(DS_B, publish=False)
    texts = [repr(registry), repr(generation), repr(lease), repr(generation.prepared)]
    for text in texts:
        assert SECRET not in text
        assert "db.internal.example" not in text
        assert "crm" not in text
    slot.release()
    lease.close()
    registry.close()
