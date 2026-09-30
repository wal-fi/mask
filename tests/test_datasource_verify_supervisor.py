"""Fase 9, Etapa 7: ownership supervisionado dos filhos de verificacao (D-090).

Regressoes dos tres findings da revisao do `8261dc7`, mais o gerenciador
supervisionado aprovado pelo usuario:

1. sucesso SOMENTE com processo efetivamente terminado (`poll()`), todas as
   threads efetivamente encerradas (`is_alive()`) e TODOS os pipes
   efetivamente fechados (`closed`). Erro de fechamento nunca aprova;
2. cleanup com UM orcamento compartilhado, separado do prazo da verificacao,
   sem multiplicar esperas por etapa, thread ou registro;
3. ownership de processo, threads e pipes pendentes: recolhimento retentado
   antes de novas verificacoes e no shutdown, vaga liberada exatamente uma vez
   e somente com tudo recolhido, capacidade recuperada apos falha transitoria.

Cada teste roda com capacidade e ledger proprios, para que um pendente
deliberado nao contamine o resto da suite. Falhas sao injetadas em envelopes
do `Popen`/streams reais; todo caso com risco de travar tem watchdog
independente que derruba o processo de teste em vez de pendurar.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from psycopg.conninfo import make_conninfo

import maskgw.bootstrap.application as application_module
import maskgw.datasource.verify as verify_module
from maskgw.datasource import CatalogStore
from maskgw.datasource.verify import (
    MAX_CONCURRENT_VERIFICATIONS,
    VerificationShutdownIncompleteError,
    VerificationSupervisor,
)
from maskgw.runtime.candidate import (
    CandidateFailure,
    DatasourceCandidateError,
    PreparedRuntime,
)
from maskgw.runtime.datasource_service import DatasourceCatalogSettings
from tests.datasource_runtime_support import (
    KEY,
    SECRET,
    FakeFactory,
    draft,
    resolver,
    secrets_provider,
)
from tests.test_datasource_bootstrap import LEGACY_CONFIG, _catalog, _compose, _LegacyAdapter

SLEEP_CHILD = "import time\ntime.sleep(600)\n"
ACK_CHILD = "import sys\n_ = sys.stdin.read()\nsys.stdout.write('{\"ok\": true}')\n"
SLOW_ACK_CHILD = (
    "import sys, time\n_ = sys.stdin.read()\ntime.sleep(2)\nsys.stdout.write('{\"ok\": true}')\n"
)
REFUSE_CHILD = 'import sys\n_ = sys.stdin.read()\nsys.stdout.write(\'{"failure": "CONNECTION"}\')\n'


def _conninfo(password: str = "p") -> str:  # noqa: S107 - senha sintetica de teste
    return make_conninfo(
        "",
        host="localhost",
        hostaddr="127.0.0.1",
        port=5432,
        dbname="x",
        user="u",
        password=password,
        sslmode="disable",
        connect_timeout=10,
    )


def _closed(target: Any) -> bool:
    """Le `closed` sem que o mypy estreite o valor entre chamadas que o mudam."""
    return bool(target.closed)


def _watchdog(seconds: float) -> threading.Timer:
    """Mata o proprio processo de teste se ele travar; falha visivel, sem hang."""
    timer = threading.Timer(seconds, lambda: os._exit(99))
    timer.daemon = True
    timer.start()
    return timer


def _verify_threads_alive() -> list[str]:
    return [t.name for t in threading.enumerate() if t.name.startswith("maskgw-verify-")]


def _assert_no_verify_threads(deadline_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + deadline_seconds
    while _verify_threads_alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert _verify_threads_alive() == []


class _CountingSlots(threading.BoundedSemaphore):
    """Semaforo de vagas que conta liberacoes: prova o "exatamente uma vez"."""

    def __init__(self, value: int) -> None:
        super().__init__(value)
        self.releases = 0
        self._count_lock = threading.Lock()

    def release(self, n: int = 1) -> None:
        with self._count_lock:
            self.releases += n
        super().release(n)

    @property
    def free(self) -> int:
        return int(self._value)


@pytest.fixture(autouse=True)
def slots(monkeypatch: pytest.MonkeyPatch) -> Iterator[_CountingSlots]:
    """Capacidade, ledger e supervisor padrao proprios deste teste."""
    value = _CountingSlots(MAX_CONCURRENT_VERIFICATIONS)
    ledger = verify_module._Ledger(value)
    monkeypatch.setattr(verify_module, "_SLOTS", value)
    monkeypatch.setattr(verify_module, "_LEDGER", ledger)
    monkeypatch.setattr(verify_module, "_DEFAULT_SUPERVISOR", VerificationSupervisor(ledger=ledger))
    # Orcamentos curtos: os casos persistentes nao alongam a suite.
    monkeypatch.setattr(verify_module, "_REAP_GRACE_SECONDS", 0.3)
    monkeypatch.setattr(verify_module, "_REAP_ATTEMPTS", 2)
    monkeypatch.setattr(verify_module, "_ADMISSION_COLLECT_SECONDS", 0.3)
    yield value


# ---- injecao de falhas -----------------------------------------------------


class Faults:
    """Falhas por operacao: `once` falha a primeira chamada; `always`, todas.

    `heal()` simula o SO voltando a funcionar: nenhuma falha a partir dali.
    `interrupt` levanta `KeyboardInterrupt` (BaseException) no lugar de OSError.
    """

    def __init__(self, spec: dict[str, str] | None = None) -> None:
        self.spec = dict(spec or {})
        self.healed = False
        self._fired: dict[str, int] = {}
        self._lock = threading.Lock()

    def hit(self, op: str) -> str | None:
        mode = self.spec.get(op)
        if mode is None or self.healed:
            return None
        with self._lock:
            count = self._fired.get(op, 0)
            self._fired[op] = count + 1
        if mode in ("always", "interrupt-always") or count == 0:
            return mode
        return None

    def raise_if(self, op: str) -> None:
        mode = self.hit(op)
        if mode is None:
            return
        if mode.startswith("interrupt"):
            raise KeyboardInterrupt
        msg = f"{op} injetado"
        raise OSError(msg)

    def heal(self) -> None:
        self.healed = True


class FaultyStream:
    def __init__(self, real: Any, faults: Faults, name: str) -> None:
        self._real = real
        self._faults = faults
        self._name = name

    def read(self, size: int = -1) -> bytes:
        self._faults.raise_if("read")
        data: bytes = self._real.read(size)
        return data

    def write(self, data: bytes) -> int:
        self._faults.raise_if("write")
        written: int = self._real.write(data)
        return written

    def flush(self) -> None:
        self._real.flush()

    def close(self) -> None:
        self._faults.raise_if(f"close_{self._name}")
        self._real.close()

    @property
    def closed(self) -> bool:
        return bool(self._real.closed)


class FaultyProcess:
    def __init__(self, real: subprocess.Popen[bytes], faults: Faults) -> None:
        self._proc = real
        self._faults = faults
        self.stdin = FaultyStream(real.stdin, faults, "stdin")
        self.stdout = FaultyStream(real.stdout, faults, "stdout")

    def kill(self) -> None:
        self._faults.raise_if("kill")
        self._proc.kill()

    def wait(self, timeout: float | None = None) -> int:
        self._faults.raise_if("wait")
        return self._proc.wait(timeout=timeout)

    def poll(self) -> int | None:
        self._faults.raise_if("poll")
        return self._proc.poll()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._proc, name)


class Harness:
    """Cada `Popen` recebe as falhas vigentes no momento da criacao."""

    def __init__(self) -> None:
        self.next_faults = Faults()
        self.procs: list[subprocess.Popen[bytes]] = []
        self.faults: list[Faults] = []

    def heal_all(self) -> None:
        for faults in self.faults:
            faults.heal()


def _start_failure(mode: str) -> None:
    if mode.startswith("interrupt"):
        raise KeyboardInterrupt
    msg = "start injetado"
    raise RuntimeError(msg)


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[Harness]:
    value = Harness()
    # Seam `_spawn`: cria o `Popen` REAL ja adotado pelo registro; o harness so
    # envolve o objeto devolvido com as falhas.
    real = verify_module._spawn
    real_start = threading.Thread.start

    def wrap(*args: Any, **kwargs: Any) -> Any:
        proc = real(*args, **kwargs)
        faults = value.next_faults
        value.procs.append(proc)
        value.faults.append(faults)
        return FaultyProcess(proc, faults)

    def start(self: threading.Thread) -> None:
        # Falha de `start()` por nome de thread, enquanto a falha estiver ativa:
        # `start_reader` falha ANTES do inicio real; `start_reader_late`, DEPOIS
        # de a thread ja rodar (inicio parcial). Modo `interrupt*` levanta
        # `KeyboardInterrupt`; os demais, `RuntimeError`.
        op = {"maskgw-verify-stdin": "start_writer", "maskgw-verify-stdout": "start_reader"}.get(
            self.name
        )
        if op is None:
            real_start(self)
            return
        faults = value.next_faults
        early = faults.hit(op)
        if early is not None:
            _start_failure(early)
        late = faults.hit(f"{op}_late")
        real_start(self)
        if late is not None:
            _start_failure(late)

    monkeypatch.setattr(verify_module, "_spawn", wrap)
    monkeypatch.setattr(threading.Thread, "start", start)
    yield value
    # Isolamento: o SO "volta"; nenhum filho real sobrevive ao teste.
    value.heal_all()
    for proc in value.procs:
        with contextlib.suppress(Exception):
            proc.kill()
            proc.wait(timeout=5)
        for stream in (proc.stdin, proc.stdout):
            with contextlib.suppress(Exception):
                if stream is not None:
                    stream.close()


def _assert_fully_reaped(harness: Harness) -> None:
    for proc in harness.procs:
        assert proc.poll() is not None, "processo efetivamente terminado"
        assert proc.stdin is not None and proc.stdin.closed, "stdin efetivamente fechado"
        assert proc.stdout is not None and proc.stdout.closed, "stdout efetivamente fechado"
    _assert_no_verify_threads()


def _verify(supervisor: VerificationSupervisor | None = None, *, timeout: float) -> None:
    target = supervisor if supervisor is not None else verify_module._DEFAULT_SUPERVISOR
    target.verify(_conninfo(), statement_timeout_ms=30_000, timeout=timeout)


def _refused(supervisor: VerificationSupervisor | None = None, *, timeout: float) -> None:
    with pytest.raises(DatasourceCandidateError) as caught:
        _verify(supervisor, timeout=timeout)
    error = caught.value
    assert error.category is CandidateFailure.CONNECTION
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "injetado" not in f"{error!s}{error!r}"


# ---- matriz de combinacoes kill/wait/poll/start/read/write/close -----------

APPROVE = "approve"
REAPED = "refuse-reaped"
PENDING = "refuse-pending"
#: `start()` que nao retornou: inicio incerto. Sem prova de termino fisico, o
#: registro e a vaga ficam retidos ate o reinicio (garantia estrita, opcao 1).
RETAINED = "refuse-retained"

_MATRIX = [
    ("kill-once", {"kill": "once"}, SLEEP_CHILD, 0.25, REAPED),
    ("kill-always", {"kill": "always"}, SLEEP_CHILD, 0.25, PENDING),
    ("wait-once", {"wait": "once"}, SLEEP_CHILD, 0.25, REAPED),
    ("wait-always", {"wait": "always"}, SLEEP_CHILD, 0.25, REAPED),
    ("poll-once", {"poll": "once"}, SLEEP_CHILD, 0.25, REAPED),
    ("poll-always", {"poll": "always"}, SLEEP_CHILD, 0.25, PENDING),
    ("start-writer", {"start_writer": "always"}, ACK_CHILD, 5.0, RETAINED),
    ("start-reader", {"start_reader": "always"}, ACK_CHILD, 5.0, RETAINED),
    ("read-once", {"read": "once"}, ACK_CHILD, 5.0, REAPED),
    ("read-always", {"read": "always"}, ACK_CHILD, 5.0, REAPED),
    ("write-once", {"write": "once"}, ACK_CHILD, 5.0, REAPED),
    ("write-always", {"write": "always"}, ACK_CHILD, 5.0, REAPED),
    # O writer nao consegue fechar o stdin: o filho espera EOF ate o prazo.
    ("close-stdin-once", {"close_stdin": "once"}, ACK_CHILD, 1.0, REAPED),
    ("close-stdin-always", {"close_stdin": "always"}, ACK_CHILD, 1.0, PENDING),
    # Transitorio apos o ack: o recolhimento fecha de verdade, tudo confirmado.
    ("close-stdout-once", {"close_stdout": "once"}, ACK_CHILD, 5.0, APPROVE),
    # Finding 1: persistente apos o ack valido nunca aprova.
    ("close-stdout-always", {"close_stdout": "always"}, ACK_CHILD, 5.0, PENDING),
    (
        "kill-once+close-stdout-always",
        {"kill": "once", "close_stdout": "always"},
        SLEEP_CHILD,
        0.25,
        PENDING,
    ),
    ("wait-always+kill-once", {"wait": "always", "kill": "once"}, SLEEP_CHILD, 0.25, REAPED),
    ("poll-once+close-stdin-once", {"poll": "once", "close_stdin": "once"}, ACK_CHILD, 1.0, REAPED),
    (
        "read-always+close-stdout-once",
        {"read": "always", "close_stdout": "once"},
        ACK_CHILD,
        5.0,
        REAPED,
    ),
    (
        "start-reader+kill-once",
        {"start_reader": "always", "kill": "once"},
        SLEEP_CHILD,
        5.0,
        RETAINED,
    ),
    (
        "write-always+close-stdin-always",
        {"write": "always", "close_stdin": "always"},
        ACK_CHILD,
        1.0,
        PENDING,
    ),
    ("poll-always+kill-always", {"poll": "always", "kill": "always"}, SLEEP_CHILD, 0.25, PENDING),
]


@pytest.mark.parametrize(
    ("spec", "child", "timeout", "expected"),
    [case[1:] for case in _MATRIX],
    ids=[case[0] for case in _MATRIX],
)
def test_fault_matrix_never_approves_or_frees_over_live_resources(  # noqa: PLR0913, PLR0917
    monkeypatch: pytest.MonkeyPatch,
    harness: Harness,
    slots: _CountingSlots,
    spec: dict[str, str],
    child: str,
    timeout: float,
    expected: str,
) -> None:
    monkeypatch.setattr(verify_module, "_CHILD_CODE", child)
    harness.next_faults = Faults(spec)
    guard = _watchdog(40.0)
    try:
        if expected == APPROVE:
            _verify(timeout=timeout)
        else:
            _refused(timeout=timeout)
        ledger = verify_module._LEDGER
        if expected == RETAINED:
            # Processo e pipes recolhidos, mas o inicio da thread e incerto:
            # nem a cura do SO nem novas coletas liberam a vaga.
            harness.heal_all()
            assert not verify_module._DEFAULT_SUPERVISOR.collect()
            assert ledger.pending == 1
            assert slots.releases == 0
            assert slots.free == MAX_CONCURRENT_VERIFICATIONS - 1
            _assert_fully_reaped(harness)
            return
        if expected == PENDING:
            # Recurso vivo/aberto: registro com dono, vaga retida, nada liberado.
            assert ledger.pending == 1
            assert slots.free == MAX_CONCURRENT_VERIFICATIONS - 1
            assert slots.releases == 0
            # Uma passada sem cura continua sem liberar nada.
            assert not verify_module._DEFAULT_SUPERVISOR.collect()
            assert slots.releases == 0
            harness.heal_all()
            assert verify_module._DEFAULT_SUPERVISOR.collect()
        assert ledger.pending == 0
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS
        assert slots.releases == 1, "vaga liberada exatamente uma vez"
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


# ---- P2-A: coleta interrompida nao deixa reivindicacao sem coletor ----------


def _make_pending(harness: Harness, count: int) -> None:
    """`count` registros genuinamente pendentes (stdout que nao fecha), curados."""
    harness.next_faults = Faults({"close_stdout": "always"})
    for _ in range(count):
        _refused(timeout=5.0)
    assert verify_module._LEDGER.pending == count


def _interrupting_reap(monkeypatch: pytest.MonkeyPatch, at: int) -> list[int]:
    """`reap` real, exceto a chamada numero `at`, que levanta KeyboardInterrupt."""
    real_reap = verify_module._ChildRecord.reap
    calls = [0]
    lock = threading.Lock()

    def reap(self: Any, deadline: float) -> bool:
        with lock:
            calls[0] += 1
            current = calls[0]
        if current == at:
            raise KeyboardInterrupt
        return bool(real_reap(self, deadline))

    monkeypatch.setattr(verify_module._ChildRecord, "reap", reap)
    return calls


@pytest.mark.parametrize("interrupt_at", [1, 2], ids=["primeiro", "meio"])
def test_interrupted_collection_leaves_no_claim_without_a_collector(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: _CountingSlots, interrupt_at: int
) -> None:
    monkeypatch.setattr(verify_module, "_CHILD_CODE", ACK_CHILD)
    guard = _watchdog(60.0)
    try:
        _make_pending(harness, 3)
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS - 3
        harness.heal_all()
        _interrupting_reap(monkeypatch, interrupt_at)
        with pytest.raises(KeyboardInterrupt):
            verify_module._DEFAULT_SUPERVISOR.collect()
        # So o que foi recolhido antes da interrupcao liberou vaga.
        assert slots.releases == interrupt_at - 1
        assert verify_module._LEDGER.pending == 3 - (interrupt_at - 1)
        # Coleta posterior repetida recupera TODOS: nenhuma reivindicacao orfa.
        for _ in range(3):
            verify_module._DEFAULT_SUPERVISOR.collect()
        assert verify_module._LEDGER.pending == 0
        assert slots.releases == 3
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


def test_interrupted_concurrent_collection_releases_each_slot_exactly_once(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: _CountingSlots
) -> None:
    monkeypatch.setattr(verify_module, "_CHILD_CODE", ACK_CHILD)
    guard = _watchdog(60.0)
    try:
        _make_pending(harness, 3)
        harness.heal_all()
        _interrupting_reap(monkeypatch, 1)
        barrier = threading.Barrier(6)
        interrupted: list[int] = []
        lock = threading.Lock()

        def collect() -> None:
            barrier.wait()
            try:
                verify_module._DEFAULT_SUPERVISOR.collect()
            except KeyboardInterrupt:
                with lock:
                    interrupted.append(1)

        workers = [threading.Thread(target=collect) for _ in range(6)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=30)
        assert not any(worker.is_alive() for worker in workers)
        assert interrupted == [1]
        for _ in range(3):
            verify_module._DEFAULT_SUPERVISOR.collect()
        assert verify_module._LEDGER.pending == 0
        assert slots.releases == 3, "cada vaga liberada exatamente uma vez"
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


# ---- P2-B: thread iniciada antes de `start()` falhar continua com dono ------


@pytest.mark.parametrize("mode", ["always", "interrupt-once"], ids=["RuntimeError", "interrupt"])
@pytest.mark.parametrize("side", ["writer", "reader"])
def test_thread_started_before_start_raises_keeps_ownership_until_it_ends(
    monkeypatch: pytest.MonkeyPatch,
    harness: Harness,
    slots: _CountingSlots,
    side: str,
    mode: str,
) -> None:
    # `start()` inicia a thread de verdade e SO DEPOIS levanta. A thread segue
    # viva apos os pipes fecharem (o pump real roda e entao espera `hold`): o
    # registro precisa adota-la, reter a vaga e so libera-la quando ela acabar.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", SLEEP_CHILD)
    hold = threading.Event()
    pump_name = "_pump_stdin" if side == "writer" else "_pump_stdout"
    thread_name = "maskgw-verify-stdin" if side == "writer" else "maskgw-verify-stdout"
    original_pump = getattr(verify_module, pump_name)

    def held_pump(*args: Any) -> None:
        try:
            original_pump(*args)
        finally:
            hold.wait(30)

    monkeypatch.setattr(verify_module, pump_name, held_pump)
    harness.next_faults = Faults({f"start_{side}_late": mode})
    guard = _watchdog(60.0)
    try:
        if mode == "always":
            _refused(timeout=5.0)
        else:
            with pytest.raises(KeyboardInterrupt):
                _verify(timeout=5.0)
        assert thread_name in _verify_threads_alive()
        proc = harness.procs[0]
        assert proc.poll() is not None
        assert proc.stdin is not None and proc.stdin.closed
        assert proc.stdout is not None and proc.stdout.closed
        # Thread viva: nada liberado, registro com dono.
        assert verify_module._LEDGER.pending == 1
        assert slots.releases == 0
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS - 1
        assert not verify_module._DEFAULT_SUPERVISOR.collect()
        assert slots.releases == 0
        hold.set()
        assert verify_module._DEFAULT_SUPERVISOR.collect()
        assert slots.releases == 1
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS
        _assert_fully_reaped(harness)
    finally:
        hold.set()
        guard.cancel()


@pytest.mark.parametrize("side", ["writer", "reader"])
def test_interrupt_before_the_real_start_retains_capacity_conservatively(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: _CountingSlots, side: str
) -> None:
    # `KeyboardInterrupt` ANTES do inicio real: o produto nao tem como provar
    # que a thread nativa nunca existira. Sem `join` invalido, processo e pipes
    # recolhidos, mas registro e vaga ficam retidos ate o reinicio (opcao 1). O
    # outro pump, cujo `start()` nunca foi tentado, nao retem nada.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", SLEEP_CHILD)
    harness.next_faults = Faults({f"start_{side}": "interrupt-once"})
    guard = _watchdog(30.0)
    try:
        with pytest.raises(KeyboardInterrupt):
            _verify(timeout=5.0)
        assert verify_module._LEDGER.pending == 1
        assert slots.releases == 0
        assert not verify_module._DEFAULT_SUPERVISOR.collect()
        assert slots.releases == 0
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS - 1
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


def _block_reader_before_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    entered: threading.Event,
    hold: threading.Event,
    captured: list[threading.Thread],
) -> None:
    """Injecao (internals do CPython, so no teste): o reader nativo nasce, para
    ANTES do bootstrap Python ate `hold`, e o `start()` e interrompido."""
    patched_start = threading.Thread.start  # o do harness

    def start(self: threading.Thread) -> None:
        if self.name != "maskgw-verify-stdout":
            patched_start(self)
            return
        captured.append(self)
        original_inner = self._bootstrap_inner  # type: ignore[attr-defined]

        def blocked_inner() -> None:
            entered.set()
            hold.wait(30)
            original_inner()

        def interrupted_wait(timeout: float | None = None) -> bool:
            del timeout
            raise KeyboardInterrupt

        self._bootstrap_inner = blocked_inner  # type: ignore[attr-defined]
        self._started.wait = interrupted_wait  # type: ignore[attr-defined]
        patched_start(self)

    monkeypatch.setattr(threading.Thread, "start", start)


def test_native_thread_blocked_before_bootstrap_keeps_record_and_slot_until_it_ends(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: _CountingSlots
) -> None:
    # Caminho completo registro+semaforo. A thread nativa do reader EXISTE e
    # fica presa ANTES do bootstrap Python (`ident is None`, `is_alive()`
    # falso), e o `start()` e interrompido esperando por ela. Nada disso prova
    # ausencia: a verificacao e recusada, o shutdown do supervisor fica
    # incompleto e a vaga retida. So depois do termino FISICO confirmado a
    # coleta libera a vaga, uma vez. Internals do CPython SO aqui, na injecao.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", SLEEP_CHILD)
    entered = threading.Event()
    hold = threading.Event()
    captured: list[threading.Thread] = []
    _block_reader_before_bootstrap(monkeypatch, entered, hold, captured)
    supervisor = VerificationSupervisor()
    guard = _watchdog(60.0)
    try:
        with pytest.raises(KeyboardInterrupt):
            _verify(supervisor, timeout=5.0)
        (reader,) = captured
        assert entered.wait(5), "a thread nativa esta executando"
        assert reader.ident is None
        assert not reader.is_alive()
        assert verify_module._LEDGER.pending == 1
        assert slots.releases == 0
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS - 1
        assert not supervisor.collect()
        with pytest.raises(VerificationShutdownIncompleteError):
            supervisor.close()
        assert not _closed(supervisor)
        assert slots.releases == 0
        # Termino fisico: a thread segue o bootstrap real, encontra o alvo
        # cancelado e sai sem tocar pipe algum.
        del reader._started.wait  # type: ignore[attr-defined]
        hold.set()
        reader._started.wait(10)  # type: ignore[attr-defined]
        reader.join(10)
        assert not reader.is_alive()
        supervisor.close()
        assert supervisor.closed
        assert verify_module._LEDGER.pending == 0
        assert slots.releases == 1
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS
        _assert_fully_reaped(harness)
    finally:
        hold.set()
        for thread in captured:
            with contextlib.suppress(AttributeError):
                del thread._started.wait  # type: ignore[attr-defined]
            # Nenhuma thread de teste abandonada: espera o bootstrap e o fim.
            thread._started.wait(10)  # type: ignore[attr-defined]
            with contextlib.suppress(RuntimeError):
                thread.join(10)
        guard.cancel()


# ---- criacao do filho: ownership antes do construtor do Popen -------------


def _fail_execute_child(
    monkeypatch: pytest.MonkeyPatch,
    *,
    create: bool,
    error: type[BaseException],
    created: list[subprocess.Popen[bytes]],
    hide_stdout: list[Any] | None = None,
) -> None:
    """Injecao (internals do CPython SO no teste): o `_execute_child` real cria
    o filho (ou nao) e DEPOIS levanta, dentro do construtor do `Popen` real.

    `hide_stdout` simula construcao incompleta: o pipe de stdout ja existe, mas
    o objeto deixa de expo-lo (guardado para o cleanup do teste).
    """
    original = subprocess.Popen._execute_child  # type: ignore[attr-defined]

    def fake(self: subprocess.Popen[bytes], *args: Any, **kwargs: Any) -> None:
        if create:
            original(self, *args, **kwargs)
            created.append(self)
        if hide_stdout is not None:
            hide_stdout.append(self.stdout)
            self.stdout = None
        if error is OSError:
            msg = "execute injetado"
            raise OSError(msg)
        raise error

    monkeypatch.setattr(subprocess.Popen, "_execute_child", fake)


def _cleanup_children(procs: list[subprocess.Popen[bytes]], extra: list[Any]) -> None:
    """Nenhum filho real nem pipe do teste sobrevive, mesmo se um assert falhar."""
    for proc in procs:
        with contextlib.suppress(Exception):
            proc.kill()
            proc.wait(timeout=5)
        for stream in (proc.stdin, proc.stdout):
            with contextlib.suppress(Exception):
                if stream is not None:
                    stream.close()
    for stream in extra:
        with contextlib.suppress(Exception):
            stream.close()


def _call(supervisor: VerificationSupervisor, error: type[BaseException]) -> None:
    if error is KeyboardInterrupt:
        with pytest.raises(KeyboardInterrupt):
            _verify(supervisor, timeout=5.0)
    else:
        _refused(supervisor, timeout=5.0)


@pytest.mark.parametrize("error", [KeyboardInterrupt, OSError], ids=["interrupt", "OSError"])
def test_constructor_failing_after_real_creation_is_reaped_through_the_adopted_object(
    monkeypatch: pytest.MonkeyPatch, slots: _CountingSlots, error: type[BaseException]
) -> None:
    # O construtor CRIA o filho e depois levanta. O registro ja tinha adotado o
    # objeto: recolhe pelo `kill`/`poll` publicos. O filho dorme e nao le o
    # stdin — so o recolhimento o encerra, nao o EOF.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", SLEEP_CHILD)
    created: list[subprocess.Popen[bytes]] = []
    supervisor = VerificationSupervisor()
    guard = _watchdog(30.0)
    try:
        with monkeypatch.context() as patch:
            _fail_execute_child(patch, create=True, error=error, created=created)
            _call(supervisor, error)
        (proc,) = created
        assert proc.poll() is not None, "filho recolhido pelo supervisor"
        assert proc.stdin is not None and proc.stdin.closed
        assert proc.stdout is not None and proc.stdout.closed
        assert verify_module._LEDGER.pending == 0
        assert slots.releases == 1
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS
        _assert_no_verify_threads()
        supervisor.close()
        assert supervisor.closed
    finally:
        guard.cancel()
        _cleanup_children(created, [])


@pytest.mark.parametrize("error", [KeyboardInterrupt, OSError], ids=["interrupt", "OSError"])
def test_constructor_failing_before_creation_is_uncertain_and_retained(
    monkeypatch: pytest.MonkeyPatch, slots: _CountingSlots, error: type[BaseException]
) -> None:
    # Construtor entrado, sem PID exposto: nada prova que nada foi criado. O
    # registro e a vaga ficam retidos ate o reinicio, sem queimar orcamento.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", SLEEP_CHILD)
    created: list[subprocess.Popen[bytes]] = []
    supervisor = VerificationSupervisor()
    guard = _watchdog(30.0)
    try:
        with monkeypatch.context() as patch:
            _fail_execute_child(patch, create=False, error=error, created=created)
            _call(supervisor, error)
        assert created == []
        assert supervisor.owned == 1
        assert slots.releases == 0
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS - 1
        for _ in range(3):
            started = time.monotonic()
            assert not supervisor.collect()
            assert time.monotonic() - started < 0.5, "incerto nao queima orcamento"
        assert slots.releases == 0
        with pytest.raises(VerificationShutdownIncompleteError):
            supervisor.close()
        assert not _closed(supervisor)
        assert slots.releases == 0
    finally:
        guard.cancel()
        _cleanup_children(created, [])


@pytest.mark.parametrize("error", [KeyboardInterrupt, OSError], ids=["interrupt", "OSError"])
def test_failure_before_the_constructor_is_entered_consumes_no_capacity(
    monkeypatch: pytest.MonkeyPatch, slots: _CountingSlots, error: type[BaseException]
) -> None:
    def never_entered(*_args: Any, **_kwargs: Any) -> Any:
        if error is OSError:
            msg = "spawn injetado"
            raise OSError(msg)
        raise error

    monkeypatch.setattr(verify_module, "_spawn", never_entered)
    supervisor = VerificationSupervisor()
    _call(supervisor, error)
    assert verify_module._LEDGER.pending == 0
    assert slots.releases == 1
    assert slots.free == MAX_CONCURRENT_VERIFICATIONS
    supervisor.close()
    assert supervisor.closed


def test_adopted_child_with_failing_poll_is_never_released_until_poll_proves_the_end(
    monkeypatch: pytest.MonkeyPatch, slots: _CountingSlots
) -> None:
    # PID exposto nao prova que os metodos funcionam: com `poll()` falhando, o
    # termino nunca e confirmado e nada e liberado; curado, libera uma vez.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", SLEEP_CHILD)
    created: list[subprocess.Popen[bytes]] = []
    supervisor = VerificationSupervisor()

    def broken_poll(self: subprocess.Popen[bytes]) -> int | None:
        del self
        msg = "poll injetado"
        raise OSError(msg)

    guard = _watchdog(30.0)
    try:
        with monkeypatch.context() as patch:
            _fail_execute_child(patch, create=True, error=KeyboardInterrupt, created=created)
            patch.setattr(verify_module._TrackedPopen, "poll", broken_poll)
            with pytest.raises(KeyboardInterrupt):
                _verify(supervisor, timeout=5.0)
            assert supervisor.owned == 1
            assert not supervisor.collect()
            assert slots.releases == 0
        assert supervisor.collect()
        (proc,) = created
        assert proc.poll() is not None
        assert slots.releases == 1
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS
    finally:
        guard.cancel()
        _cleanup_children(created, [])


def test_adopted_child_with_incomplete_pipes_is_ended_but_retained_until_the_pipe_is_known(
    monkeypatch: pytest.MonkeyPatch, slots: _CountingSlots
) -> None:
    # PID exposto mas pipe pedido ausente: construcao incompleta. O processo
    # conhecido e ENCERRADO pelos metodos publicos e o pipe conhecido, fechado;
    # o pipe desconhecido nao prova fechamento, entao registro e vaga ficam
    # retidos. Exposto o pipe de novo, a coleta recupera exatamente uma vez.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", SLEEP_CHILD)
    created: list[subprocess.Popen[bytes]] = []
    hidden: list[Any] = []
    supervisor = VerificationSupervisor()
    guard = _watchdog(30.0)
    try:
        with monkeypatch.context() as patch:
            _fail_execute_child(
                patch, create=True, error=KeyboardInterrupt, created=created, hide_stdout=hidden
            )
            with pytest.raises(KeyboardInterrupt):
                _verify(supervisor, timeout=5.0)
        (proc,) = created
        (stdout,) = hidden
        assert proc.poll() is not None, "filho real encerrado pelo supervisor"
        assert proc.stdin is not None and proc.stdin.closed, "pipe conhecido fechado"
        assert not stdout.closed, "pipe desconhecido nao foi tocado"
        for _ in range(2):
            started = time.monotonic()
            assert not supervisor.collect()
            assert time.monotonic() - started < 0.5, "nada observavel muda: sem queimar orcamento"
        assert supervisor.owned == 1
        assert slots.releases == 0
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS - 1
        with pytest.raises(VerificationShutdownIncompleteError):
            supervisor.close()
        assert slots.releases == 0
        # Restaurado SO o pipe: fechado pela coleta, a vaga volta uma vez.
        proc.stdout = stdout
        supervisor.close()
        assert supervisor.closed
        assert stdout.closed
        assert slots.releases == 1
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS
    finally:
        guard.cancel()
        _cleanup_children(created, hidden)


# ---- orcamento compartilhado ------------------------------------------------


def test_one_collection_pass_shares_one_budget_across_pending_records(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: _CountingSlots
) -> None:
    # Dois registros com `kill()` persistente: UMA passada de recolhimento tem
    # UM prazo para todos, e nao um prazo por registro.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", SLEEP_CHILD)
    harness.next_faults = Faults({"kill": "always"})
    guard = _watchdog(60.0)
    try:
        _refused(timeout=0.1)
        _refused(timeout=0.1)
        assert verify_module._LEDGER.pending == 2
        monkeypatch.setattr(verify_module, "_REAP_GRACE_SECONDS", 0.5)
        budget = verify_module._REAP_ATTEMPTS * verify_module._REAP_GRACE_SECONDS
        started = time.monotonic()
        assert not verify_module._DEFAULT_SUPERVISOR.collect()
        elapsed = time.monotonic() - started
        assert elapsed < budget + 0.5, elapsed
        assert slots.releases == 0
        harness.heal_all()
        assert verify_module._DEFAULT_SUPERVISOR.collect()
        assert slots.releases == 2
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


def test_owner_cleanup_is_separate_from_the_verification_deadline(
    monkeypatch: pytest.MonkeyPatch, harness: Harness
) -> None:
    # O prazo da verificacao (aqui 0,1 s) nao consome o orcamento de cleanup,
    # e o cleanup nao estende a verificacao alem de prazo + orcamento.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", SLEEP_CHILD)
    harness.next_faults = Faults({"kill": "always"})
    budget = verify_module._REAP_ATTEMPTS * verify_module._REAP_GRACE_SECONDS
    guard = _watchdog(30.0)
    started = time.monotonic()
    try:
        _refused(timeout=0.1)
    finally:
        guard.cancel()
    elapsed = time.monotonic() - started
    # Kill falha sempre: o recolhimento usou o orcamento inteiro, e so ele.
    assert budget <= elapsed < 0.1 + budget + 1.0, elapsed


# ---- concorrencia, admissao e recuperacao de capacidade ---------------------


def test_concurrent_collectors_release_a_recovered_slot_exactly_once(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: _CountingSlots
) -> None:
    monkeypatch.setattr(verify_module, "_CHILD_CODE", ACK_CHILD)
    harness.next_faults = Faults({"close_stdout": "always"})
    guard = _watchdog(40.0)
    try:
        _refused(timeout=5.0)
        assert verify_module._LEDGER.pending == 1
        harness.heal_all()
        barrier = threading.Barrier(8)
        results: list[bool] = []
        lock = threading.Lock()

        def collect() -> None:
            barrier.wait()
            outcome = verify_module._DEFAULT_SUPERVISOR.collect()
            with lock:
                results.append(outcome)

        workers = [threading.Thread(target=collect) for _ in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=20)
        assert not any(worker.is_alive() for worker in workers)
        assert len(results) == 8
        assert verify_module._LEDGER.pending == 0
        assert slots.releases == 1
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


def test_pending_record_holds_capacity_until_recovered_before_admission(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: _CountingSlots
) -> None:
    # Um pendente retem UMA vaga: com 4, so 3 verificacoes simultaneas entram e
    # a quarta e recusada sem criar filho. Curado o SO, a proxima admissao
    # recolhe o pendente ANTES de admitir, e a capacidade volta a 4.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", ACK_CHILD)
    first = Faults({"close_stdout": "always"})
    harness.next_faults = first
    guard = _watchdog(60.0)
    try:
        _refused(timeout=5.0)
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS - 1

        monkeypatch.setattr(verify_module, "_CHILD_CODE", SLOW_ACK_CHILD)
        harness.next_faults = Faults()
        barrier = threading.Barrier(MAX_CONCURRENT_VERIFICATIONS)
        outcomes: list[str] = []
        lock = threading.Lock()

        def run() -> None:
            barrier.wait()
            try:
                _verify(timeout=10.0)
                outcome = "ok"
            except DatasourceCandidateError as exc:
                outcome = exc.category.value
            with lock:
                outcomes.append(outcome)

        workers = [threading.Thread(target=run) for _ in range(MAX_CONCURRENT_VERIFICATIONS)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=30)
        assert not any(worker.is_alive() for worker in workers)
        assert sorted(outcomes) == ["CONNECTION", "ok", "ok", "ok"]
        assert len(harness.procs) == 1 + 3, "a recusada nao criou filho"
        assert verify_module._LEDGER.pending == 1

        first.heal()
        monkeypatch.setattr(verify_module, "_CHILD_CODE", ACK_CHILD)
        _verify(timeout=5.0)  # a admissao recolhe o pendente primeiro
        assert verify_module._LEDGER.pending == 0
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS
        assert slots.releases == 1 + 3 + 1
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


def test_base_exception_in_the_owner_does_not_abandon_the_record(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: _CountingSlots
) -> None:
    # `KeyboardInterrupt` durante a supervisao propaga, mas o registro nunca e
    # abandonado: recolhido no `finally`, vaga liberada uma vez.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", SLEEP_CHILD)
    harness.next_faults = Faults({"wait": "interrupt-once"})
    guard = _watchdog(30.0)
    try:
        with pytest.raises(KeyboardInterrupt):
            _verify(timeout=5.0)
        assert verify_module._LEDGER.pending == 0
        assert slots.releases == 1
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


def test_base_exception_with_unreapable_child_keeps_ownership(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: _CountingSlots
) -> None:
    monkeypatch.setattr(verify_module, "_CHILD_CODE", SLEEP_CHILD)
    harness.next_faults = Faults({"wait": "interrupt-once", "kill": "always"})
    guard = _watchdog(30.0)
    try:
        with pytest.raises(KeyboardInterrupt):
            _verify(timeout=5.0)
        assert verify_module._LEDGER.pending == 1
        assert slots.releases == 0
        assert harness.procs[0].poll() is None
        harness.heal_all()
        assert verify_module._DEFAULT_SUPERVISOR.collect()
        assert slots.releases == 1
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


# ---- shutdown do proprio supervisor ------------------------------------------


def test_close_with_persistent_pending_is_incomplete_until_recovered(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: _CountingSlots
) -> None:
    monkeypatch.setattr(verify_module, "_CHILD_CODE", ACK_CHILD)
    harness.next_faults = Faults({"close_stdout": "always"})
    supervisor = VerificationSupervisor()
    guard = _watchdog(40.0)
    try:
        _refused(supervisor, timeout=5.0)
        assert supervisor.owned == 1
        with pytest.raises(VerificationShutdownIncompleteError) as caught:
            supervisor.close()
        error = caught.value
        assert error.__cause__ is None
        assert error.__context__ is None
        assert str(error) == "recolhimento de verificacoes pendente no shutdown"
        # Nao declarado fechado, capacidade NAO liberada sobre recurso aberto.
        assert supervisor.closing
        assert not _closed(supervisor)
        assert supervisor.owned == 1
        assert slots.releases == 0
        assert "closed=False" in repr(supervisor)
        # Admissao recusada desde o inicio do shutdown, sem criar filho.
        _refused(supervisor, timeout=5.0)
        assert len(harness.procs) == 1
        harness.heal_all()
        supervisor.close()  # o retry do shutdown recolhe
        assert supervisor.closed
        assert supervisor.owned == 0
        assert slots.releases == 1
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS
        supervisor.close()  # idempotente
        assert slots.releases == 1
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


def test_close_during_an_in_flight_verification_waits_for_nothing_and_frees_nothing(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: _CountingSlots
) -> None:
    # O shutdown nao espera sem teto pela verificacao em voo, nem libera a vaga
    # dela: reporta incompleto; depois que ela termina, o retry fecha.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", SLOW_ACK_CHILD)
    supervisor = VerificationSupervisor()
    outcome: list[BaseException | None] = []

    def run() -> None:
        try:
            _verify(supervisor, timeout=10.0)
            outcome.append(None)
        except BaseException as exc:
            outcome.append(exc)

    guard = _watchdog(40.0)
    worker = threading.Thread(target=run)
    try:
        worker.start()
        deadline = time.monotonic() + 10
        while not harness.procs and time.monotonic() < deadline:
            time.sleep(0.01)
        assert harness.procs, "a verificacao em voo criou o filho"
        started = time.monotonic()
        with pytest.raises(VerificationShutdownIncompleteError):
            supervisor.close()
        assert time.monotonic() - started < 1.5
        assert not _closed(supervisor)
        assert slots.releases == 0
        _refused(supervisor, timeout=5.0)
        worker.join(timeout=20)
        assert not worker.is_alive()
        assert outcome == [None]
        supervisor.close()
        assert supervisor.closed
        assert slots.releases == 1
        assert len(harness.procs) == 1
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


def test_shutdown_collects_records_left_by_another_owner(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: _CountingSlots
) -> None:
    # O ledger e do processo: um pendente deixado por um supervisor anterior
    # (ex. startup que falhou) e retentado pelo shutdown de outro.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", ACK_CHILD)
    harness.next_faults = Faults({"close_stdout": "always"})
    old = VerificationSupervisor()
    guard = _watchdog(40.0)
    try:
        _refused(old, timeout=5.0)
        with pytest.raises(VerificationShutdownIncompleteError):
            old.close()
        harness.heal_all()
        new = VerificationSupervisor()
        new.close()
        assert new.closed
        assert verify_module._LEDGER.pending == 0
        assert slots.releases == 1
        assert old.owned == 0
        old.close()
        assert old.closed
    finally:
        guard.cancel()


def test_supervisor_is_a_verifier_and_repr_carries_no_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(verify_module, "_CHILD_CODE", ACK_CHILD)
    supervisor = VerificationSupervisor()

    class _Prepared:
        def verify_target(self) -> tuple[str, int]:
            return _conninfo(password=SECRET), 30_000

    supervisor(cast(Any, _Prepared()))
    text = repr(supervisor)
    assert SECRET not in text
    assert "localhost" not in text
    supervisor.close()
    assert supervisor.closed


# ---- composition root -------------------------------------------------------


@pytest.fixture
def spy_supervisors(monkeypatch: pytest.MonkeyPatch) -> list[VerificationSupervisor]:
    created: list[VerificationSupervisor] = []

    class Recording(VerificationSupervisor):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            created.append(self)

    monkeypatch.setattr(verify_module, "VerificationSupervisor", Recording)
    return created


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "masking.yaml"
    path.write_text(LEGACY_CONFIG, encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _reset_legacy() -> None:
    _LegacyAdapter.events = []


def _production(tmp_path: Path, *drafts: object) -> DatasourceCatalogSettings:
    # Caminho de producao: sem `adapter_factory` nem `verifier` injetados.
    base = _catalog(tmp_path, *drafts)
    return DatasourceCatalogSettings(
        store_path=base.store_path, anchor_path=base.anchor_path, resolver=resolver
    )


def _reopen(settings: DatasourceCatalogSettings) -> None:
    CatalogStore.open(settings.store_path, anchor_path=settings.anchor_path, master_key=KEY).close()


def test_production_catalog_composes_and_closes_a_supervisor(
    monkeypatch: pytest.MonkeyPatch,
    config_file: Path,
    tmp_path: Path,
    spy_supervisors: list[VerificationSupervisor],
    slots: _CountingSlots,
) -> None:
    events: list[str] = []
    _compose(monkeypatch, events)
    monkeypatch.setattr(verify_module, "_CHILD_CODE", ACK_CHILD)
    settings = _production(tmp_path, draft("crm"))
    app = application_module.build_application(
        config_path=config_file,
        conninfo="host=x",
        secrets=secrets_provider(),
        datasource_catalog=settings,
    )
    try:
        assert app.datasources is not None
        (supervisor,) = spy_supervisors
        assert app.datasources.verification is supervisor
        assert slots.releases == 1  # a verificacao de startup, recolhida
    finally:
        app.close()
    assert supervisor.closed
    assert verify_module._LEDGER.pending == 0
    assert slots.free == MAX_CONCURRENT_VERIFICATIONS


@pytest.mark.parametrize("injected", ["adapter_factory", "verifier"])
def test_injected_doubles_compose_no_supervisor(
    monkeypatch: pytest.MonkeyPatch,
    config_file: Path,
    tmp_path: Path,
    spy_supervisors: list[VerificationSupervisor],
    injected: str,
) -> None:
    events: list[str] = []
    _compose(monkeypatch, events)
    base = _catalog(tmp_path, draft("crm"))
    calls: list[object] = []

    def record(prepared: PreparedRuntime) -> None:
        calls.append(prepared)

    settings = DatasourceCatalogSettings(
        store_path=base.store_path,
        anchor_path=base.anchor_path,
        resolver=resolver,
        adapter_factory=FakeFactory() if injected == "adapter_factory" else None,
        verifier=None if injected == "adapter_factory" else record,
    )
    app = application_module.build_application(
        config_path=config_file,
        conninfo="host=x",
        secrets=secrets_provider(),
        datasource_catalog=settings,
    )
    try:
        assert app.datasources is not None
        assert app.datasources.verification is None
        assert spy_supervisors == []
        if injected == "verifier":
            assert len(calls) == 1
    finally:
        app.close()


def test_partial_startup_before_runtime_keeps_ownership_of_unreaped_child(  # noqa: PLR0913, PLR0917 - fixtures do pytest
    monkeypatch: pytest.MonkeyPatch,
    config_file: Path,
    tmp_path: Path,
    harness: Harness,
    spy_supervisors: list[VerificationSupervisor],
    slots: _CountingSlots,
) -> None:
    # Falha de startup ANTES de existir `DatasourceRuntime`, com o filho da
    # verificacao irrecolhivel: o erro original sai intacto, nada e publicado,
    # o catalogo e solto, e o registro continua com dono no ledger do processo.
    events: list[str] = []
    _compose(monkeypatch, events)
    monkeypatch.setattr(verify_module, "_CHILD_CODE", ACK_CHILD)
    harness.next_faults = Faults({"close_stdout": "always"})
    settings = _production(tmp_path, draft("crm"))
    guard = _watchdog(40.0)
    try:
        with pytest.raises(DatasourceCandidateError) as caught:
            application_module.build_application(
                config_path=config_file,
                conninfo="host=x",
                secrets=secrets_provider(),
                datasource_catalog=settings,
            )
        assert caught.value.category is CandidateFailure.CONNECTION
        assert caught.value.__context__ is None
        assert SECRET not in f"{caught.value!s}{caught.value!r}"
        assert events == []
        assert _LegacyAdapter.events == []
        _reopen(settings)
        (supervisor,) = spy_supervisors
        assert supervisor.closing
        assert not _closed(supervisor)
        assert verify_module._LEDGER.pending == 1
        assert slots.releases == 0
        harness.heal_all()
        supervisor.close()
        assert supervisor.closed
        assert slots.releases == 1
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


def test_partial_startup_before_runtime_with_reaped_child_closes_the_supervisor(
    monkeypatch: pytest.MonkeyPatch,
    config_file: Path,
    tmp_path: Path,
    spy_supervisors: list[VerificationSupervisor],
    slots: _CountingSlots,
) -> None:
    events: list[str] = []
    _compose(monkeypatch, events)
    monkeypatch.setattr(verify_module, "_CHILD_CODE", REFUSE_CHILD)
    settings = _production(tmp_path, draft("crm"))
    with pytest.raises(DatasourceCandidateError):
        application_module.build_application(
            config_path=config_file,
            conninfo="host=x",
            secrets=secrets_provider(),
            datasource_catalog=settings,
        )
    (supervisor,) = spy_supervisors
    assert supervisor.closed
    assert verify_module._LEDGER.pending == 0
    assert slots.releases == 1
    _reopen(settings)


def test_later_startup_failure_keeps_the_original_error_and_ownership(  # noqa: PLR0913, PLR0917 - fixtures do pytest
    monkeypatch: pytest.MonkeyPatch,
    config_file: Path,
    tmp_path: Path,
    harness: Harness,
    spy_supervisors: list[VerificationSupervisor],
    slots: _CountingSlots,
) -> None:
    # Falha DEPOIS de `DatasourceRuntime` existir, com um registro proprio
    # irrecolhivel: o shutdown incompleto do supervisor nao substitui o erro
    # original de startup, e o registro segue com dono.
    events: list[str] = []
    _compose(monkeypatch, events)
    monkeypatch.setattr(verify_module, "_CHILD_CODE", ACK_CHILD)
    settings = _production(tmp_path, draft("crm"))

    def failing_mcp(_gateway: object) -> Any:
        (supervisor,) = spy_supervisors
        harness.next_faults = Faults({"close_stdout": "always"})
        _refused(supervisor, timeout=5.0)
        msg = "falha sintetica do MCP"
        raise RuntimeError(msg)

    monkeypatch.setattr(application_module, "build_mcp_server", failing_mcp)
    guard = _watchdog(40.0)
    try:
        with pytest.raises(RuntimeError, match="falha sintetica do MCP"):
            application_module.build_application(
                config_path=config_file,
                conninfo="host=x",
                secrets=secrets_provider(),
                datasource_catalog=settings,
            )
        _reopen(settings)
        assert _LegacyAdapter.events == ["legacy:connect", "legacy:close"]
        (supervisor,) = spy_supervisors
        assert not _closed(supervisor)
        assert verify_module._LEDGER.pending == 1
        harness.heal_all()
        supervisor.close()
        assert supervisor.closed
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS
    finally:
        guard.cancel()


def test_application_close_is_incomplete_while_a_verification_resource_lives(  # noqa: PLR0913, PLR0917 - fixtures do pytest
    monkeypatch: pytest.MonkeyPatch,
    config_file: Path,
    tmp_path: Path,
    harness: Harness,
    spy_supervisors: list[VerificationSupervisor],
    slots: _CountingSlots,
) -> None:
    events: list[str] = []
    _compose(monkeypatch, events)
    monkeypatch.setattr(verify_module, "_CHILD_CODE", ACK_CHILD)
    settings = _production(tmp_path, draft("crm"))
    app = application_module.build_application(
        config_path=config_file,
        conninfo="host=x",
        secrets=secrets_provider(),
        datasource_catalog=settings,
    )
    assert app.datasources is not None
    (supervisor,) = spy_supervisors
    harness.next_faults = Faults({"close_stdout": "always"})
    guard = _watchdog(40.0)
    try:
        with pytest.raises(DatasourceCandidateError):
            app.datasources.service.test_draft(draft("tmp"), SECRET)
        assert supervisor.owned == 1
        with pytest.raises(VerificationShutdownIncompleteError) as caught:
            app.close()
        assert SECRET not in f"{caught.value!s}{caught.value!r}"
        assert caught.value.__context__ is None
        # Nada declarado fechado; o resto do shutdown aconteceu mesmo assim.
        assert "state='closing'" in repr(app)
        assert not _closed(supervisor)
        assert slots.releases == 1  # so a verificacao de startup
        _reopen(settings)
        assert _LegacyAdapter.events == ["legacy:connect", "legacy:close"]
        # Curado o SO, o retry do shutdown recolhe e fecha.
        harness.heal_all()
        app.close()
        assert "state='closed'" in repr(app)
        assert supervisor.closed
        assert slots.releases == 2
        assert slots.free == MAX_CONCURRENT_VERIFICATIONS
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


def test_begin_shutdown_stops_verification_admission(
    monkeypatch: pytest.MonkeyPatch,
    config_file: Path,
    tmp_path: Path,
    spy_supervisors: list[VerificationSupervisor],
) -> None:
    events: list[str] = []
    _compose(monkeypatch, events)
    monkeypatch.setattr(verify_module, "_CHILD_CODE", ACK_CHILD)
    settings = _production(tmp_path, draft("crm"))
    app = application_module.build_application(
        config_path=config_file,
        conninfo="host=x",
        secrets=secrets_provider(),
        datasource_catalog=settings,
    )
    try:
        assert app.datasources is not None
        (supervisor,) = spy_supervisors
        app.datasources.begin_shutdown()
        assert supervisor.closing
        _refused(supervisor, timeout=5.0)
    finally:
        app.close()
    assert supervisor.closed
