"""Fase 7, etapa 2: ciclo de vida dos runtimes.

Cobre as seis regras da secao 8.3 da especificacao e D-054. Nenhum PostgreSQL:
o adapter e um duble que CONTA os fechamentos, porque a garantia que importa e
"fechado exatamente uma vez", e ela so se afirma contando.
"""

from __future__ import annotations

import threading
from typing import cast

import pytest

from maskgw.config.gateway import DatabaseSettings, GatewayConfig
from maskgw.config.models import MaskingFileConfig
from maskgw.db.postgres import PostgresAdapter
from maskgw.masking.engine import MaskingEngine
from maskgw.masking.rules import MaskingPolicy
from maskgw.runtime import (
    MAX_RETIRED_RUNTIMES,
    RetiredRuntimeInUseError,
    Runtime,
    RuntimeRegistry,
)
from maskgw.sql.policy import DEFAULT_SQL_POLICY


class CountingAdapter:
    """Conta `close`. Nao fala com banco algum."""

    def __init__(self) -> None:
        self.close_calls = 0
        self._lock = threading.Lock()

    def close(self) -> None:
        with self._lock:
            self.close_calls += 1


def make_runtime(revision: int = 1) -> tuple[Runtime, CountingAdapter]:
    adapter = CountingAdapter()
    policy = MaskingPolicy(exceptions=(), rules=())
    runtime = Runtime(
        revision=revision,
        file_config=MaskingFileConfig(),
        config=GatewayConfig(
            masking=policy,
            database=DatabaseSettings(statement_timeout_ms=30_000, max_rows=1_000),
            sql=DEFAULT_SQL_POLICY,
        ),
        engine=MaskingEngine(policy),
        adapter=cast(PostgresAdapter, adapter),
    )
    return runtime, adapter


class TestAcquireRelease:
    def test_acquire_returns_published_runtime(self) -> None:
        runtime, _ = make_runtime()
        registry = RuntimeRegistry(runtime)
        assert registry.acquire() is runtime
        registry.release(runtime)

    def test_release_without_acquire_is_an_error(self) -> None:
        runtime, _ = make_runtime()
        registry = RuntimeRegistry(runtime)
        with pytest.raises(RuntimeError):
            registry.release(runtime)

    def test_borrow_releases_even_on_exception(self) -> None:
        runtime, adapter = make_runtime()
        registry = RuntimeRegistry(runtime)
        with pytest.raises(ValueError, match="boom"), registry.borrow():
            raise ValueError("boom")
        new, _ = make_runtime(2)
        registry.swap_and_close(new)
        assert adapter.close_calls == 1

    def test_current_does_not_take_a_reference(self) -> None:
        """`current` e leitura de metadata: nao impede o fechamento."""
        runtime, adapter = make_runtime()
        registry = RuntimeRegistry(runtime)
        assert registry.current is runtime
        new, _ = make_runtime(2)
        registry.swap_and_close(new)
        assert adapter.close_calls == 1


class TestRule1ReloadDoesNotBlock:
    def test_swap_returns_immediately_with_query_in_flight(self) -> None:
        old, old_adapter = make_runtime(1)
        registry = RuntimeRegistry(old)
        registry.acquire()

        new, _ = make_runtime(2)
        assert registry.swap(new) is None  # nao fecha: ainda ha usuario
        assert registry.current is new
        assert old_adapter.close_calls == 0

        registry.release(old)
        assert old_adapter.close_calls == 1


class TestRule4ClosedExactlyOnce:
    def test_last_release_closes_once(self) -> None:
        old, adapter = make_runtime(1)
        registry = RuntimeRegistry(old)
        for _ in range(5):
            registry.acquire()

        new, _ = make_runtime(2)
        registry.swap_and_close(new)
        for _ in range(4):
            registry.release(old)
            assert adapter.close_calls == 0
        registry.release(old)
        assert adapter.close_calls == 1

    def test_never_closed_while_in_use(self) -> None:
        old, adapter = make_runtime(1)
        registry = RuntimeRegistry(old)
        registry.acquire()
        new, _ = make_runtime(2)
        registry.swap_and_close(new)
        assert adapter.close_calls == 0
        registry.release(old)
        assert adapter.close_calls == 1

    def test_concurrent_releases_close_exactly_once(self) -> None:
        old, adapter = make_runtime(1)
        registry = RuntimeRegistry(old)
        workers = 32
        for _ in range(workers):
            registry.acquire()
        new, _ = make_runtime(2)
        registry.swap_and_close(new)

        barrier = threading.Barrier(workers)

        def release() -> None:
            barrier.wait()
            registry.release(old)

        threads = [threading.Thread(target=release) for _ in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert adapter.close_calls == 1

    def test_close_all_does_not_double_close(self) -> None:
        old, old_adapter = make_runtime(1)
        registry = RuntimeRegistry(old)
        registry.acquire()
        new, new_adapter = make_runtime(2)
        registry.swap_and_close(new)
        registry.release(old)
        assert old_adapter.close_calls == 1

        registry.close_all()
        assert old_adapter.close_calls == 1
        assert new_adapter.close_calls == 1


class TestRule5CloseImmediatelyWhenIdle:
    def test_idle_swap_closes_old_right_away(self) -> None:
        """Sem isto, um Gateway ocioso nunca fecharia o antigo."""
        old, adapter = make_runtime(1)
        registry = RuntimeRegistry(old)
        new, _ = make_runtime(2)

        to_close = registry.swap(new)
        assert to_close is old
        to_close.adapter.close()
        assert adapter.close_calls == 1
        assert registry.retired_in_use() == 0

    def test_swap_and_close_closes_idle_old(self) -> None:
        old, adapter = make_runtime(1)
        registry = RuntimeRegistry(old)
        registry.swap_and_close(make_runtime(2)[0])
        assert adapter.close_calls == 1


class TestRule6NoAcquireAfterRetire:
    def test_acquire_after_swap_returns_the_new_runtime(self) -> None:
        old, _ = make_runtime(1)
        registry = RuntimeRegistry(old)
        new, _ = make_runtime(2)
        registry.swap_and_close(new)
        assert registry.acquire() is new

    def test_acquiring_a_retired_runtime_is_impossible(self) -> None:
        """Um aposentado nunca e a referencia publicada."""
        old, _ = make_runtime(1)
        registry = RuntimeRegistry(old)
        registry.acquire()
        new, _ = make_runtime(2)
        registry.swap(new)
        for _ in range(10):
            assert registry.acquire() is new
        registry.release(old)

    def test_acquire_under_concurrent_swap_never_yields_closed_runtime(self) -> None:
        """A corrida da regra 6: ler a referencia e incrementar sao atomicos."""
        first, _ = make_runtime(1)
        registry = RuntimeRegistry(first)
        seen: list[bool] = []
        stop = threading.Event()

        def reader() -> None:
            while not stop.is_set():
                runtime = registry.acquire()
                try:
                    # Se a aquisicao tivesse devolvido um aposentado ja
                    # fechado, este adapter teria close_calls > 0.
                    adapter = cast(CountingAdapter, runtime.adapter)
                    seen.append(adapter.close_calls == 0)
                finally:
                    registry.release(runtime)

        threads = [threading.Thread(target=reader) for _ in range(4)]
        for thread in threads:
            thread.start()
        for _ in range(60):
            nxt, _ = make_runtime()
            while True:
                try:
                    registry.swap_and_close(nxt)
                except RetiredRuntimeInUseError:
                    continue
                break
        stop.set()
        for thread in threads:
            thread.join()

        assert seen
        assert all(seen)


class TestRetiredLimit:
    def test_limit_is_one(self) -> None:
        assert MAX_RETIRED_RUNTIMES == 1

    def test_second_swap_with_retired_in_use_is_refused(self) -> None:
        first, _ = make_runtime(1)
        registry = RuntimeRegistry(first)
        registry.acquire()
        registry.swap_and_close(make_runtime(2)[0])
        assert registry.retired_in_use() == 1

        with pytest.raises(RetiredRuntimeInUseError):
            registry.swap_and_close(make_runtime(3)[0])

    def test_check_can_swap_refuses_before_building_the_candidate(self) -> None:
        """O passo 4 da secao 7.4: recusar ANTES de construir e conectar."""
        first, _ = make_runtime(1)
        registry = RuntimeRegistry(first)
        registry.acquire()
        registry.swap_and_close(make_runtime(2)[0])

        with pytest.raises(RetiredRuntimeInUseError):
            registry.check_can_swap()

    def test_swap_allowed_again_after_release(self) -> None:
        first, _ = make_runtime(1)
        registry = RuntimeRegistry(first)
        registry.acquire()
        second, _ = make_runtime(2)
        registry.swap_and_close(second)
        registry.release(first)
        assert registry.retired_in_use() == 0
        registry.check_can_swap()
        registry.swap_and_close(make_runtime(3)[0])

    def test_connection_count_never_exceeds_two(self) -> None:
        """A garantia da secao 8.5: o total de conexoes nao cresce.

        A amostra e a verdade de campo — quantos adapters existem sem `close` —
        e nao uma leitura combinada de duas fontes. Cada adapter entra na lista
        no instante em que e criado, inclusive o candidato, e sai so quando e
        fechado. Isso conta o candidato durante a janela em que ele ja esta
        conectado e ainda nao foi publicado, que e exatamente a janela que
        torna o passo 4 da secao 7.4 necessario: checar o limite ANTES de
        conectar. Sem essa ordem, um aposentado em uso mais um candidato ja
        conectado dariam 3.
        """
        state_lock = threading.Lock()
        adapters: list[CountingAdapter] = []

        def track(adapter: CountingAdapter) -> CountingAdapter:
            with state_lock:
                adapters.append(adapter)
            return adapter

        def open_adapters() -> int:
            with state_lock:
                return sum(1 for a in adapters if a.close_calls == 0)

        first, first_adapter = make_runtime(1)
        track(first_adapter)
        registry = RuntimeRegistry(first)

        stop = threading.Event()
        samples: list[int] = []

        def worker() -> None:
            while not stop.is_set():
                with registry.borrow():
                    samples.append(open_adapters())

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()

        swaps = 0
        attempts = 0
        while swaps < 40 and attempts < 20_000:
            attempts += 1
            # Passo 4 do fluxo: o limite e checado ANTES de construir e
            # conectar o candidato.
            try:
                registry.check_can_swap()
            except RetiredRuntimeInUseError:
                continue

            candidate, candidate_adapter = make_runtime(swaps + 2)
            track(candidate_adapter)
            try:
                registry.swap_and_close(candidate)
            except RetiredRuntimeInUseError:
                # Candidato abandonado: fecha, como faz o fluxo real.
                candidate_adapter.close()
                continue
            swaps += 1

        stop.set()
        for thread in threads:
            thread.join()

        registry.close_all()
        assert swaps > 0
        assert samples
        assert max(samples) <= 2, f"maximo de conexoes abertas: {max(samples)}"
        assert all(a.close_calls == 1 for a in adapters)

    def test_no_leak_after_many_reloads(self) -> None:
        adapters: list[CountingAdapter] = []
        first, first_adapter = make_runtime(1)
        adapters.append(first_adapter)
        registry = RuntimeRegistry(first)
        for revision in range(2, 32):
            candidate, adapter = make_runtime(revision)
            adapters.append(adapter)
            registry.swap_and_close(candidate)
        registry.close_all()
        assert all(a.close_calls == 1 for a in adapters)


class TestRuntimeSurface:
    def test_runtime_is_immutable_in_content(self) -> None:
        runtime, _ = make_runtime()
        with pytest.raises(AttributeError):
            runtime.revision = 9  # type: ignore[misc]

    def test_repr_leaks_nothing(self) -> None:
        runtime, _ = make_runtime()
        text = repr(runtime)
        assert "password" not in text
        assert "dsn" not in text.lower()
        assert "Runtime(revision=1" in text

    def test_registry_repr_leaks_nothing(self) -> None:
        runtime, _ = make_runtime()
        assert repr(RuntimeRegistry(runtime)) == "RuntimeRegistry(retired_open=0)"

    def test_each_runtime_has_its_own_connection_lock(self) -> None:
        one, _ = make_runtime(1)
        two, _ = make_runtime(2)
        assert one.connection_lock is not two.connection_lock

    def test_swap_to_same_runtime_is_refused(self) -> None:
        runtime, _ = make_runtime()
        registry = RuntimeRegistry(runtime)
        with pytest.raises(RuntimeError):
            registry.swap(runtime)
