"""Fase 9, Etapa 7 (D-108): a fila administrativa dedicada, isolada.

Capacidade contada na admissao, barreira x shutdown, drenagem integral do
aceito (A1), notificacao fora do lock, estado desconhecido (quebra, contencao e
congelamento fail-closed), admissao que falha no meio, inicio de worker
incerto (antes/depois do inicio real e bootstrap nativo preso) e recusa de
self-join. Internals do CPython aparecem SO aqui, na injecao de falhas. Toda
espera tem watchdog independente e todo `Event` e solto no `finally`.
"""

from __future__ import annotations

import contextlib
import os
import threading
from collections import deque
from collections.abc import Callable, Iterator
from typing import Any

import pytest

import maskgw.runtime.admin_work as work_module
from maskgw.runtime.admin_work import (
    AdminWorkQueue,
    AdminWorkUnavailableError,
    WorkTicket,
)


def _watchdog(seconds: float) -> threading.Timer:
    timer = threading.Timer(seconds, lambda: os._exit(99))
    timer.daemon = True
    timer.start()
    return timer


@pytest.fixture(autouse=True)
def guard(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Watchdog e limpeza de TODA fila iniciada, mesmo se uma assercao falhar.

    O teardown fecha a admissao e drena cada fila (os testes soltam suas
    barreiras no proprio `finally`); o watchdog e cancelado POR ULTIMO.
    """
    timer = _watchdog(60.0)
    started: list[AdminWorkQueue] = []
    real_start = AdminWorkQueue.start

    def tracked(self: AdminWorkQueue) -> None:
        started.append(self)
        real_start(self)

    monkeypatch.setattr(AdminWorkQueue, "start", tracked)
    try:
        yield
    finally:
        for queue in started:
            with contextlib.suppress(Exception):
                queue.close_admission()
                queue.drain()
        timer.cancel()


def _blocking(gate: threading.Event, started: threading.Event | None = None) -> Callable[[], str]:
    def job() -> str:
        if started is not None:
            started.set()
        gate.wait(20)
        return "ok"

    return job


def _work_threads() -> list[str]:
    return [t.name for t in threading.enumerate() if t.name.startswith("maskgw-admin-work-")]


def _drain_in_thread(queue: AdminWorkQueue) -> tuple[threading.Thread, list[bool]]:
    box: list[bool] = []
    thread = threading.Thread(target=lambda: box.append(queue.drain()), daemon=True)
    thread.start()
    return thread, box


# ---- capacidade, barreira e drenagem integral --------------------------------


@pytest.mark.usefixtures("guard")
def test_capacity_counts_accepted_not_done_before_dispatch() -> None:
    queue = AdminWorkQueue()
    queue.start()
    gate = threading.Event()
    try:
        tickets = [queue.submit(_blocking(gate)) for _ in range(4)]
        assert queue.accepted == 4
        with pytest.raises(AdminWorkUnavailableError):
            queue.submit(_blocking(gate))
        assert queue.accepted == 4
    finally:
        gate.set()
        queue.close_admission()
        assert queue.drain()
    assert [ticket.take() for ticket in tickets] == ["ok"] * 4
    assert queue.accepted == 0
    assert _work_threads() == []


@pytest.mark.usefixtures("guard")
def test_shutdown_completes_every_accepted_operation_queued_and_running() -> None:
    queue = AdminWorkQueue()
    gate = threading.Event()
    drainer: threading.Thread | None = None
    try:
        queue.start()
        running = [threading.Event(), threading.Event()]
        tickets = [queue.submit(_blocking(gate, running[index])) for index in range(2)]
        tickets += [queue.submit(_blocking(gate)) for _ in range(2)]  # na fila
        assert all(event.wait(5) for event in running)
        queue.close_admission()
        with pytest.raises(AdminWorkUnavailableError):
            queue.submit(_blocking(gate))
        drainer, box = _drain_in_thread(queue)
        drainer.join(0.3)
        assert drainer.is_alive(), "a drenagem espera o aceito"
    finally:
        gate.set()
        if drainer is not None:
            drainer.join(20)
    assert box == [True]
    assert all(ticket.done and not ticket.failed for ticket in tickets)
    assert [ticket.take() for ticket in tickets] == ["ok"] * 4
    assert _work_threads() == []


@pytest.mark.usefixtures("guard")
def test_notification_runs_outside_the_lock_and_a_failing_notifier_keeps_the_result() -> None:
    queue = AdminWorkQueue()
    queue.start()
    seen: list[bool] = []

    def notify() -> None:
        free = queue._cond.acquire(blocking=False)
        if free:
            queue._cond.release()
        seen.append(free)
        msg = "loop fechado (simulado)"
        raise RuntimeError(msg)

    ticket = queue.submit(lambda: "ok", notify=notify)
    queue.close_admission()
    assert queue.drain()
    assert seen == [True]
    assert ticket.done
    assert ticket.take() == "ok"
    assert ticket.take() is None, "o resultado e entregue uma vez"


# ---- estado desconhecido -------------------------------------------------------


@pytest.mark.usefixtures("guard")
def test_base_exception_breaks_the_queue_and_contains_before_dispatching_more() -> None:
    order: list[str] = []
    contained = threading.Event()

    def on_unknown() -> None:
        order.append("contained")
        contained.set()

    queue = AdminWorkQueue(workers=1, on_unknown=on_unknown)
    queue.start()

    def interrupted() -> str:
        raise KeyboardInterrupt

    def following() -> str:
        order.append("next")
        return "ran"

    failed = queue.submit(interrupted)
    after = queue.submit(following)
    assert contained.wait(5)
    queue.close_admission()
    assert queue.drain()
    assert failed.failed and failed.take() is None
    assert order == ["contained", "next"], "nada despachado antes da contencao"
    assert after.take() == "ran"
    assert queue.broken
    with pytest.raises(AdminWorkUnavailableError):
        queue.submit(lambda: "x")


@pytest.mark.usefixtures("guard")
def test_failed_containment_freezes_the_queue_without_executing_accepted_work() -> None:
    def on_unknown() -> None:
        msg = "contencao falhou"
        raise RuntimeError(msg)

    queue = AdminWorkQueue(workers=1, on_unknown=on_unknown)
    gate = threading.Event()
    executed: list[str] = []
    abandoned: list[str] = []
    notified: list[str] = []

    def interrupted() -> str:
        gate.wait(10)
        raise KeyboardInterrupt

    def recorder(sink: list[str], value: str) -> Callable[[], None]:
        def record() -> None:
            sink.append(value)

        return record

    def runner(value: str) -> Callable[[], str]:
        def run() -> str:
            executed.append(value)
            return "ran"

        return run

    try:
        queue.start()
        first = queue.submit(interrupted)
        rest = [
            queue.submit(
                runner(str(index)),
                notify=recorder(notified, str(index)),
                abandon=recorder(abandoned, str(index)),
            )
            for index in range(2)
        ]
    finally:
        gate.set()
    queue.close_admission()
    assert queue.drain()
    assert first.failed
    assert queue.frozen
    assert executed == [], "nada executa sobre estado desconhecido nao contido"
    assert sorted(abandoned) == ["0", "1"]
    assert sorted(notified) == ["0", "1"]
    assert all(ticket.done and ticket.failed for ticket in rest)
    assert queue.accepted == 0


@pytest.mark.usefixtures("guard")
class _BeforeAppend(deque[Any]):
    """Falha ANTES de mutar a fila."""

    def append(self, item: Any) -> None:
        del item
        msg = "falha injetada antes de enfileirar"
        raise MemoryError(msg)


class _AfterAppend(deque[Any]):
    """Enfileira de fato e SO depois falha."""

    def append(self, item: Any) -> None:
        super().append(item)
        msg = "falha injetada depois de enfileirar"
        raise MemoryError(msg)


@pytest.mark.parametrize("point", ["before-append", "after-append", "notify"])
def test_admission_that_fails_midway_is_rolled_back_and_never_executes(
    monkeypatch: pytest.MonkeyPatch, point: str
) -> None:
    # A falha pode vir antes de mutar, depois de enfileirar ou no `notify`:
    # em todos os casos o ticket sai do registro E da fila sob o lock, antes
    # de qualquer worker poder ve-lo — a recusa e verdadeira e o job nunca roda.
    queue = AdminWorkQueue()
    queue.start()
    original = queue._pending
    ran: list[str] = []

    def job() -> str:
        ran.append("x")
        return "x"

    try:
        if point == "before-append":
            queue._pending = _BeforeAppend()
        elif point == "after-append":
            queue._pending = _AfterAppend()
        else:

            def broken_notify(n: int = 1) -> None:
                del n
                msg = "notify injetado"
                raise OSError(msg)

            monkeypatch.setattr(queue._cond, "notify", broken_notify)
        with pytest.raises((MemoryError, OSError)):
            queue.submit(job)
        assert queue.accepted == 0, "registro parcial desfeito"
        assert len(queue._pending) == 0, "nada ficou enfileirado"
    finally:
        queue._pending = original
        monkeypatch.undo()
        queue.close_admission()
        assert queue.drain()
    assert ran == [], "o job recusado nunca executa"
    assert _work_threads() == []


# ---- inicio de worker: antes, depois e bootstrap nativo incerto --------------


def _patch_start(
    monkeypatch: pytest.MonkeyPatch, name: str, *, after: bool, error: type[BaseException]
) -> None:
    real_start = threading.Thread.start

    def start(self: threading.Thread) -> None:
        if self.name != name:
            real_start(self)
            return
        if after:
            real_start(self)
        raise error

    monkeypatch.setattr(threading.Thread, "start", start)


@pytest.mark.usefixtures("guard")
@pytest.mark.parametrize("error", [RuntimeError, KeyboardInterrupt])
def test_start_failing_before_the_real_start_is_uncertain_and_retained(
    monkeypatch: pytest.MonkeyPatch, error: type[BaseException]
) -> None:
    queue = AdminWorkQueue()
    _patch_start(monkeypatch, "maskgw-admin-work-1", after=False, error=error)
    with pytest.raises(error):
        queue.start()
    monkeypatch.undo()
    queue.close_admission()
    # Sem prova de que a thread nunca existira: incompleto, sempre.
    assert not queue.drain()
    assert not queue.drain()
    assert "maskgw-admin-work-0" not in _work_threads()


@pytest.mark.usefixtures("guard")
@pytest.mark.parametrize("error", [RuntimeError, KeyboardInterrupt])
def test_start_failing_after_the_real_start_is_drained_once_the_worker_ends(
    monkeypatch: pytest.MonkeyPatch, error: type[BaseException]
) -> None:
    queue = AdminWorkQueue()
    _patch_start(monkeypatch, "maskgw-admin-work-1", after=True, error=error)
    with pytest.raises(error):
        queue.start()
    monkeypatch.undo()
    queue.close_admission()
    # A thread rodou de fato: entrou no alvo, serve e sai — a drenagem a espera.
    assert queue.drain()
    assert _work_threads() == []


@pytest.mark.usefixtures("guard")
def test_native_bootstrap_blocked_worker_retains_until_it_physically_ends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered, hold = threading.Event(), threading.Event()
    captured: list[threading.Thread] = []
    real_start = threading.Thread.start

    def start(self: threading.Thread) -> None:
        if self.name != "maskgw-admin-work-1":
            real_start(self)
            return
        captured.append(self)
        inner = self._bootstrap_inner  # type: ignore[attr-defined]

        def blocked() -> None:
            entered.set()
            hold.wait(30)
            inner()

        def interrupted(timeout: float | None = None) -> bool:
            del timeout
            raise KeyboardInterrupt

        self._bootstrap_inner = blocked  # type: ignore[attr-defined]
        self._started.wait = interrupted  # type: ignore[attr-defined]
        real_start(self)

    queue = AdminWorkQueue()
    monkeypatch.setattr(threading.Thread, "start", start)
    try:
        with pytest.raises(KeyboardInterrupt):
            queue.start()
        monkeypatch.undo()
        (thread,) = captured
        assert entered.wait(5)
        assert thread.ident is None
        queue.close_admission()
        assert not queue.drain(), "ident None/is_alive falso nao provam ausencia"
        del thread._started.wait  # type: ignore[attr-defined]
        hold.set()
        thread._started.wait(10)  # type: ignore[attr-defined]
        thread.join(10)
        assert queue.drain()
    finally:
        hold.set()
        for thread in captured:
            with contextlib.suppress(AttributeError):
                del thread._started.wait  # type: ignore[attr-defined]
            thread._started.wait(10)  # type: ignore[attr-defined]
            with contextlib.suppress(RuntimeError):
                thread.join(10)
    assert _work_threads() == []


@pytest.mark.usefixtures("guard")
def test_drain_before_a_started_worker_enters_its_target_still_runs_accepted_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regressao: um worker `started` que ainda nao entrou no alvo nao pode ser
    # cancelado pela drenagem — deixaria operacao aceita sem executor.
    release = threading.Event()
    original = work_module._worker_main

    def delayed(queue: AdminWorkQueue, worker: Any) -> None:
        release.wait(10)
        original(queue, worker)

    monkeypatch.setattr(work_module, "_worker_main", delayed)
    queue = AdminWorkQueue()
    queue.start()
    ran: list[str] = []

    def job() -> str:
        ran.append("job")
        return "ok"

    ticket = queue.submit(job)
    queue.close_admission()
    drainer, box = _drain_in_thread(queue)
    try:
        drainer.join(0.2)
        assert drainer.is_alive()
    finally:
        release.set()
        drainer.join(20)
    assert box == [True]
    assert ran == ["job"]
    assert ticket.done and ticket.take() == "ok"
    assert queue.accepted == 0
    assert _work_threads() == []


# ---- self-join ----------------------------------------------------------------


@pytest.mark.usefixtures("guard")
def test_drain_from_a_worker_is_refused_without_effect() -> None:
    queue = AdminWorkQueue()
    queue.start()
    seen: list[str] = []

    def job() -> str:
        assert queue.owns_current_thread()
        try:
            queue.drain()
        except RuntimeError as exc:
            seen.append(str(exc))
        return "ok"

    ticket: WorkTicket[str] = queue.submit(job)
    queue.close_admission()
    assert queue.drain()
    assert seen == ["drenagem recusada a partir de um worker administrativo"]
    assert ticket.take() == "ok"
    assert not queue.owns_current_thread()


# ---- registro global de ownership (startup parcial) --------------------------


class _Owner:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return self.name


class _PausingList(list[object]):
    """Pausa a PRIMEIRA remocao, ja com o indice escolhido, antes de apagar.

    Injecao so de teste: reproduz a corrida "achou o indice, outro removeu
    antes, apagou o vizinho".
    """

    def __init__(self, items: list[object]) -> None:
        super().__init__(items)
        self.paused = threading.Event()
        self.resume = threading.Event()
        self._first = True

    def __delitem__(self, index: Any) -> None:
        if self._first:
            self._first = False
            self.paused.set()
            self.resume.wait(10)
        super().__delitem__(index)


def test_concurrent_release_drops_only_the_requested_owners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a, b, c = _Owner("A"), _Owner("B"), _Owner("C")
    held = _PausingList([a, b, c])
    monkeypatch.setattr(work_module, "_RETAINED", held)
    first = threading.Thread(target=work_module.release_retained, args=(b,), daemon=True)
    second = threading.Thread(target=work_module.release_retained, args=(a,), daemon=True)
    try:
        first.start()
        assert held.paused.wait(5), "a primeira remocao achou o indice de B"
        second.start()
        # Serializado: a segunda remocao espera a primeira terminar.
        second.join(0.3)
        interleaved = not second.is_alive()
    finally:
        held.resume.set()
        first.join(10)
        second.join(10)
    assert not first.is_alive() and not second.is_alive()
    assert list(held) == [c], "so os donos pedidos (A e B) sairam"
    assert not interleaved, "a remocao concorrente nao pode intercalar"


def test_concurrent_retain_and_release_keep_exactly_the_unreleased_owners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    held: list[object] = []
    monkeypatch.setattr(work_module, "_RETAINED", held)
    owners = [[_Owner(f"{t}-{i}") for i in range(40)] for t in range(8)]
    barrier = threading.Barrier(len(owners))

    def churn(mine: list[_Owner]) -> None:
        barrier.wait()
        for owner in mine:
            work_module.retain(owner)
        # Solta so os de indice par, intercalando com as outras threads.
        for owner in mine[::2]:
            work_module.release_retained(owner)

    threads = [threading.Thread(target=churn, args=(mine,), daemon=True) for mine in owners]
    try:
        for thread in threads:
            thread.start()
    finally:
        for thread in threads:
            thread.join(20)
    assert not any(thread.is_alive() for thread in threads)
    expected = {id(owner) for mine in owners for owner in mine[1::2]}
    assert {id(owner) for owner in held} == expected
    assert len(held) == len(expected), "nenhuma duplicata nem perda"
