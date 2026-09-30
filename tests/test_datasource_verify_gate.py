"""Fase 9, Etapa 7: gate pos-conexao de candidato em processo filho (D-090).

As consultas de verificacao que `PostgresAdapter.connect()` executa depois de
autenticar so tem o `statement_timeout` do servidor como teto; um upstream que
autentica e para de responder prenderia o `recv` sem teto do lado do cliente. O
gate roda a verificacao num processo filho com prazo efetivo, morto e recolhido
ao fim do prazo (padrao D-092). Estes testes provam, a maioria sem rede:

- o prazo e efetivo: um filho que nunca responde e cortado perto do prazo;
- nada fica para tras: o filho termina e nenhuma thread sobrevive a chamada;
- toda falha e uma categoria fechada (`CONNECTION`/`CAPABILITY`), sem host,
  destino, senha nem cadeia de excecao;
- o filho nao herda segredo do ambiente e recebe o alvo (com a senha) so por
  `stdin`; nada por `argv`;
- pai e filho compartilham a MESMA primitiva de verificacao (`verify_adapter`);
- `python -I` importa `psycopg` e `maskgw` — o filho funciona sem PYTHONPATH;
- contra PostgreSQL 16 real, a verificacao aprova um alvo valido e recusa um
  segredo errado, no processo e no filho.
"""

from __future__ import annotations

import contextlib
import json
import os
import socket
import struct
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
from psycopg.conninfo import make_conninfo

import maskgw.datasource.verify as verify_module
from maskgw.datasource.verify import (
    MAX_CONCURRENT_VERIFICATIONS,
    VERIFY_TIMEOUT_SECONDS,
    verify_adapter,
    verify_connection,
    verify_connection_in_child,
)
from maskgw.runtime.candidate import (
    CandidateFailure,
    DatasourceCandidateError,
)
from maskgw.runtime.candidate import verify_adapter as candidate_verify_adapter

_DSN = os.environ.get("MASKGW_TEST_DSN")
_needs_dsn = pytest.mark.skipif(_DSN is None, reason="MASKGW_TEST_DSN nao definido")


class _PopenSpy:
    """Registra cada filho criado, para provar que todos terminaram.

    Envolve o seam `_spawn` (que cria o `Popen` REAL ja adotado pelo registro):
    desde a adocao antes do construtor, substituir `subprocess.Popen` nao
    alcancaria mais a criacao.
    """

    def __init__(self) -> None:
        self.processes: list[subprocess.Popen[bytes]] = []
        self.calls: list[tuple[list[str], dict[str, Any]]] = []
        self._original = verify_module._spawn

    def __call__(self, record: Any, args: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        self.calls.append((list(args), dict(kwargs)))
        process: subprocess.Popen[bytes] = self._original(record, args, **kwargs)
        self.processes.append(process)
        return process


@pytest.fixture(autouse=True)
def _isolated_ownership(monkeypatch: pytest.MonkeyPatch) -> None:
    """Capacidade, ledger e supervisor padrao proprios de cada teste.

    Um teste que deixa um registro pendente de proposito (falha persistente
    injetada) nao pode reduzir a capacidade dos seguintes nem fazer a
    admissao deles gastar o orcamento de recolhimento.
    """
    slots = threading.BoundedSemaphore(MAX_CONCURRENT_VERIFICATIONS)
    ledger = verify_module._Ledger(slots)
    monkeypatch.setattr(verify_module, "_SLOTS", slots)
    monkeypatch.setattr(verify_module, "_LEDGER", ledger)
    monkeypatch.setattr(
        verify_module, "_DEFAULT_SUPERVISOR", verify_module.VerificationSupervisor(ledger=ledger)
    )


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> Iterator[_PopenSpy]:
    value = _PopenSpy()
    monkeypatch.setattr(verify_module, "_spawn", value)
    yield value
    for process in value.processes:
        assert process.poll() is not None, "processo filho sobreviveu ao gate"


def _threads() -> set[int | None]:
    return {thread.ident for thread in threading.enumerate()}


def _verify_threads_alive() -> list[str]:
    """Threads de I/O proprias do gate que ainda estejam vivas."""
    return [t.name for t in threading.enumerate() if t.name.startswith("maskgw-verify-")]


def _assert_no_verify_threads(deadline_seconds: float = 5.0) -> None:
    """Nenhuma thread de I/O do gate sobrevive (daemon, recolhida apos o kill)."""
    deadline = time.monotonic() + deadline_seconds
    while _verify_threads_alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert _verify_threads_alive() == []


def _blackhole() -> tuple[socket.socket, int]:
    """Aceita TCP e nunca fala: simula autenticar-e-silenciar no nivel do socket."""
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(16)
    port = server.getsockname()[1]

    def acceptor() -> None:
        held: list[socket.socket] = []
        while True:
            try:
                conn, _ = server.accept()
                held.append(conn)  # segura aberto, nunca responde
            except OSError:
                break

    threading.Thread(target=acceptor, daemon=True).start()
    return server, port


def _conninfo(port: int, *, password: str = "p", hostaddr: str = "127.0.0.1") -> str:
    return make_conninfo(
        "",
        host="localhost",
        hostaddr=hostaddr,
        port=port,
        dbname="x",
        user="u",
        password=password,
        sslmode="disable",
        connect_timeout=10,
    )


def _postgres_startup_then_silent() -> tuple[socket.socket, int]:
    """Fala o inicio do protocolo 3.0 (AuthenticationOk, ReadyForQuery) e, ao
    receber a primeira Query, FICA EM SILENCIO.

    Diferente do blackhole TCP, isto prova o cenario da D-090: um upstream que
    conclui o startup/autenticacao do PostgreSQL e so entao para de responder,
    nas verificacoes pos-conexao. `sslmode=disable` evita o `SSLRequest`.
    """
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(4)
    port = server.getsockname()[1]

    def send(conn: socket.socket, typ: bytes, body: bytes) -> None:
        conn.sendall(typ + struct.pack("!I", len(body) + 4) + body)

    def serve() -> None:
        while True:
            try:
                conn, _ = server.accept()
            except OSError:
                return
            try:
                header = conn.recv(8)
                if len(header) >= 4:
                    length = struct.unpack("!I", header[:4])[0]
                    conn.recv(max(0, length - len(header)))
                send(conn, b"R", struct.pack("!I", 0))  # AuthenticationOk
                send(conn, b"K", struct.pack("!II", 1234, 5678))  # BackendKeyData
                send(conn, b"Z", b"I")  # ReadyForQuery (idle)
                conn.recv(4096)  # a Query chega; a partir daqui, silencio
            except OSError:
                with contextlib.suppress(OSError):
                    conn.close()

    threading.Thread(target=serve, daemon=True).start()
    return server, port


# ---- prazo, ausencia de residuo ------------------------------------------


def test_silent_upstream_is_cut_at_the_deadline_without_leftovers(spy: _PopenSpy) -> None:
    server, port = _blackhole()
    threads = _threads()
    started = time.monotonic()
    try:
        with pytest.raises(DatasourceCandidateError) as caught:
            verify_connection_in_child(_conninfo(port), statement_timeout_ms=30_000, timeout=1.0)
    finally:
        server.close()
    elapsed = time.monotonic() - started
    # O socket ficaria aberto para sempre: o corte veio do prazo.
    assert elapsed < 8
    assert elapsed >= 1.0
    assert caught.value.category is CandidateFailure.CONNECTION
    assert spy.processes[0].returncode is not None
    assert _threads() == threads
    error = caught.value
    assert error.__cause__ is None
    assert error.__context__ is None


def test_production_deadline_is_twelve_seconds() -> None:
    assert VERIFY_TIMEOUT_SECONDS == 12.0


def test_default_deadline_is_applied_without_an_explicit_timeout(
    monkeypatch: pytest.MonkeyPatch, spy: _PopenSpy
) -> None:
    server, port = _blackhole()
    monkeypatch.setattr(verify_module, "VERIFY_TIMEOUT_SECONDS", 0.5)
    started = time.monotonic()
    try:
        with pytest.raises(DatasourceCandidateError):
            verify_connection_in_child(_conninfo(port), statement_timeout_ms=30_000)
    finally:
        server.close()
    assert time.monotonic() - started < 8
    assert all(process.returncode is not None for process in spy.processes)


# ---- categoria fechada, sem vazamento ------------------------------------


@pytest.mark.parametrize(
    "child",
    [
        "import sys\nsys.exit(3)\n",
        "import sys\nsys.exit(4)\n",
        "import sys\nsys.stdout.write('not json')\n",
        "import sys\nsys.stdout.write('{}')\n",
        'import sys\nsys.stdout.write(\'{"failure": "POLICY"}\')\n',
        'import sys\nsys.stdout.write(\'{"failure": "NOPE"}\')\n',
        'import sys\nsys.stdout.write(\'{"ok": true, "extra": 1}\')\n',
        "import sys\nsys.stdout.write('x' * 5000)\n",
        "import sys\nsys.stderr.write('segredo no stderr')\nsys.exit(1)\n",
    ],
)
@pytest.mark.usefixtures("spy")
def test_every_child_failure_is_a_closed_connection_error(
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    child: str,
) -> None:
    monkeypatch.setattr(verify_module, "_CHILD_CODE", child)
    with pytest.raises(DatasourceCandidateError) as caught:
        verify_connection_in_child(_conninfo(5432), statement_timeout_ms=30_000, timeout=10)
    assert caught.value.category is CandidateFailure.CONNECTION
    assert caught.value.__context__ is None
    captured = capfd.readouterr()
    assert captured.out == ""
    assert "segredo" not in captured.err


@pytest.mark.usefixtures("spy")
def test_child_reports_capability_failure_as_its_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        verify_module,
        "_CHILD_CODE",
        'import sys\nsys.stdout.write(\'{"failure": "CAPABILITY"}\')\n',
    )
    with pytest.raises(DatasourceCandidateError) as caught:
        verify_connection_in_child(_conninfo(5432), statement_timeout_ms=30_000, timeout=10)
    assert caught.value.category is CandidateFailure.CAPABILITY


def test_secret_travels_by_stdin_and_child_gets_no_environment_secret(
    monkeypatch: pytest.MonkeyPatch, spy: _PopenSpy
) -> None:
    for name in (
        "MASKGW_DATASOURCE_MASTER_KEY",
        "MASKGW_ADMIN_TOKEN",
        "MASKGW_DATABASE_DSN",
        "MASKGW_HMAC_KEY",
    ):
        monkeypatch.setenv(name, "canary-secret-value")
    echo = (
        "import json, os, sys\n"
        "data = sys.stdin.read()\n"
        "sys.stdout.write(json.dumps([sorted(os.environ), data, sys.argv[1:]]))\n"
    )
    monkeypatch.setattr(verify_module, "_CHILD_CODE", echo)
    secret = "senha-canario-9f2c"
    payload = json.dumps(
        {"conninfo": _conninfo(5432, password=secret), "statement_timeout_ms": 30_000}
    ).encode("utf-8")
    output = verify_module._run_child(payload, timeout=10)
    assert output is not None
    env_names, received, argv = json.loads(output)
    assert secret in received  # veio por stdin
    assert argv == []
    assert not any(name.startswith(("MASKGW", "PYTHON")) for name in env_names)
    ((args, kwargs),) = spy.calls
    assert secret not in " ".join(args)
    assert kwargs["stdin"] is subprocess.PIPE
    assert kwargs["stdout"] is subprocess.PIPE
    assert kwargs["stderr"] is subprocess.DEVNULL
    assert "-I" in args
    # `-S` NAO pode estar: o filho precisa de `site` para importar `psycopg`.
    assert "-S" not in args


def test_concurrency_is_bounded_and_refused_without_waiting() -> None:
    acquired = 0
    try:
        for _ in range(MAX_CONCURRENT_VERIFICATIONS):
            assert verify_module._SLOTS.acquire(blocking=False)
            acquired += 1
        started = time.monotonic()
        with pytest.raises(DatasourceCandidateError) as caught:
            verify_connection_in_child(_conninfo(5432), statement_timeout_ms=30_000, timeout=10)
        assert time.monotonic() - started < 1
        assert caught.value.category is CandidateFailure.CONNECTION
    finally:
        for _ in range(acquired):
            verify_module._SLOTS.release()


def test_oversized_payload_fails_closed_without_a_child(spy: _PopenSpy) -> None:
    huge = "a" * (verify_module._MAX_INPUT_BYTES + 1)
    with pytest.raises(DatasourceCandidateError) as caught:
        verify_connection_in_child(
            _conninfo(5432, password=huge), statement_timeout_ms=30_000, timeout=10
        )
    assert caught.value.category is CandidateFailure.CONNECTION
    assert spy.processes == []  # nem chegou a criar filho


# ---- primitiva compartilhada e import do filho ---------------------------


def test_parent_and_child_share_the_single_verification_primitive() -> None:
    # A verificacao nao tem copia divergente: o modulo do filho reexporta a
    # MESMA funcao que o pai (`candidate.verify_prepared`) usa.
    assert verify_adapter is candidate_verify_adapter


def test_child_interpreter_imports_maskgw_and_psycopg_under_isolation() -> None:
    # `python -I` (sem `-S`) precisa achar `psycopg` e `maskgw` no site-packages
    # da venv, sem PYTHONPATH — a base do filho funcionar em checkout instalado
    # editavel e em wheel/sdist instalados.
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import psycopg, maskgw.datasource.verify; print('ok')",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


# ---- P1/P2: supervisao de envio/execucao/recebimento ---------------------


def _watchdog(seconds: float) -> threading.Timer:
    """Mata o proprio processo de teste se ele travar; falha visivel, sem hang."""
    timer = threading.Timer(seconds, lambda: os._exit(99))
    timer.daemon = True
    timer.start()
    return timer


def test_child_that_never_reads_stdin_is_cut_without_blocking_on_the_write(
    monkeypatch: pytest.MonkeyPatch, spy: _PopenSpy
) -> None:
    # P1: payload valido maior que o buffer do pipe e um filho que nunca le o
    # stdin. O prazo NAO pode depender da thread de envio presa no pipe cheio.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", "import time\ntime.sleep(600)\n")
    payload = b"a" * 17977  # maior que o buffer do pipe, menor que 64 KiB
    guard = _watchdog(20.0)
    started = time.monotonic()
    try:
        result = verify_module._run_child(payload, timeout=0.25)
    finally:
        guard.cancel()
    elapsed = time.monotonic() - started
    assert result is None
    assert elapsed < 8  # cortado pelo prazo, nao pelos 600 s do filho
    assert spy.processes[0].returncode is not None
    # Dê um instante para as threads daemon se recolherem apos o kill.
    _assert_no_verify_threads()


def test_oversized_output_is_cut_during_the_read_not_after(
    monkeypatch: pytest.MonkeyPatch, spy: _PopenSpy
) -> None:
    # P2: filho que despeja sem parar e cortado DURANTE a leitura, em tempo
    # limitado, sem acumular a saida inteira.
    monkeypatch.setattr(
        verify_module,
        "_CHILD_CODE",
        "import sys\nwhile True:\n    sys.stdout.write('x' * 65536)\n    sys.stdout.flush()\n",
    )
    guard = _watchdog(20.0)
    started = time.monotonic()
    try:
        with pytest.raises(DatasourceCandidateError) as caught:
            verify_connection_in_child(_conninfo(5432), statement_timeout_ms=30_000, timeout=10)
    finally:
        guard.cancel()
    assert caught.value.category is CandidateFailure.CONNECTION
    assert time.monotonic() - started < 8
    assert spy.processes[0].returncode is not None
    _assert_no_verify_threads()


def test_transport_failure_to_spawn_is_a_closed_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Falha operacional de transporte (nao foi possivel criar o filho) vira
    # categoria fechada, sem mensagem original nem cadeia, com o semaforo livre.
    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("falha de transporte do teste")

    # Falha ANTES de o construtor do `Popen` ser entrado: nada criado, vaga livre.
    monkeypatch.setattr(verify_module, "_spawn", boom)
    free_before = verify_module._SLOTS.acquire(blocking=False)
    if free_before:
        verify_module._SLOTS.release()
    with pytest.raises(DatasourceCandidateError) as caught:
        verify_connection_in_child(_conninfo(5432), statement_timeout_ms=30_000, timeout=10)
    assert caught.value.category is CandidateFailure.CONNECTION
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert "transporte" not in str(caught.value)
    # O semaforo foi liberado no `finally`: uma nova verificacao ainda cabe.
    assert verify_module._SLOTS.acquire(blocking=False)
    verify_module._SLOTS.release()


def test_upstream_that_finishes_startup_then_silences_is_cut(spy: _PopenSpy) -> None:
    # O cenario da D-090 que o blackhole TCP NAO prova: o upstream conclui o
    # startup/autenticacao do PostgreSQL e so entao silencia nas verificacoes
    # pos-conexao. Cortado no prazo, sem thread/processo/socket orfao.
    server, port = _postgres_startup_then_silent()
    guard = _watchdog(25.0)
    started = time.monotonic()
    try:
        with pytest.raises(DatasourceCandidateError) as caught:
            verify_connection_in_child(_conninfo(port), statement_timeout_ms=30_000, timeout=3.0)
    finally:
        guard.cancel()
        server.close()
    elapsed = time.monotonic() - started
    assert caught.value.category is CandidateFailure.CONNECTION
    assert 3.0 <= elapsed < 10  # chegou a consultar e foi cortado no prazo
    assert spy.processes[0].returncode is not None
    _assert_no_verify_threads()


# ---- lifecycle apos Popen: inicializacao parcial e pontos de supervisao ----


def test_failure_to_start_the_reader_reaps_process_and_writer(
    monkeypatch: pytest.MonkeyPatch, spy: _PopenSpy
) -> None:
    # Finding: se `reader.start()` falha, o filho e a thread de escrita ja
    # iniciada ficavam vivos. Agora tudo e recolhido antes da saida, e a falha
    # vira categoria fechada.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", "import time\ntime.sleep(600)\n")
    real_start = threading.Thread.start

    def flaky_start(self: threading.Thread) -> None:
        # A primeira thread (writer) inicia; a segunda (reader) falha.
        if self.name == "maskgw-verify-stdout":
            raise RuntimeError("falha ao iniciar a thread de leitura")
        real_start(self)

    monkeypatch.setattr(threading.Thread, "start", flaky_start)
    guard = _watchdog(20.0)
    try:
        with pytest.raises(DatasourceCandidateError) as caught:
            verify_connection_in_child(_conninfo(5432), statement_timeout_ms=30_000, timeout=10)
    finally:
        guard.cancel()
        monkeypatch.setattr(threading.Thread, "start", real_start)
    assert caught.value.category is CandidateFailure.CONNECTION
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert spy.processes, "o filho foi criado"
    assert spy.processes[0].returncode is not None, "o filho foi recolhido"
    _assert_no_verify_threads()
    # `start()` do reader nao retornou: inicio incerto. A vaga dele fica retida
    # ate o reinicio (garantia estrita), mas as demais seguem disponiveis.
    assert verify_module._LEDGER.pending == 1
    assert verify_module._SLOTS.acquire(blocking=False)
    verify_module._SLOTS.release()


def test_oserror_at_a_supervision_point_is_a_closed_connection_error(
    monkeypatch: pytest.MonkeyPatch, spy: _PopenSpy
) -> None:
    # Finding: um `OSError` nos pontos de supervisao (ex. `process.wait()`) tem
    # de virar `DatasourceCandidateError(CONNECTION)` com cleanup, nao vazar cru.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", "import time\ntime.sleep(600)\n")
    real_popen = verify_module._spawn

    class WaitExplodes:
        def __init__(self, proc: subprocess.Popen[bytes]) -> None:
            self._proc = proc
            self._boom = True

        def wait(self, timeout: float | None = None) -> int:
            if self._boom:
                self._boom = False  # so a primeira supervisao estoura
                raise OSError("falha de supervisao do teste")
            return self._proc.wait(timeout=timeout)

        def __getattr__(self, name: str) -> Any:
            return getattr(self._proc, name)

    def wrap(*args: Any, **kwargs: Any) -> Any:
        proc = real_popen(*args, **kwargs)
        spy.processes.append(proc)  # o spy real so registra via seu __call__
        return WaitExplodes(proc)

    monkeypatch.setattr(verify_module, "_spawn", wrap)
    guard = _watchdog(20.0)
    try:
        with pytest.raises(DatasourceCandidateError) as caught:
            verify_connection_in_child(_conninfo(5432), statement_timeout_ms=30_000, timeout=10)
    finally:
        guard.cancel()
    assert caught.value.category is CandidateFailure.CONNECTION
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert "supervisao" not in str(caught.value)
    assert spy.processes[-1].returncode is not None  # recolhido mesmo com OSError
    _assert_no_verify_threads()
    assert verify_module._SLOTS.acquire(blocking=False)
    verify_module._SLOTS.release()


class _OkThenBroken:
    """Stream que entrega `{"ok": true}` e entao falha a leitura seguinte."""

    def __init__(self) -> None:
        self._first = b'{"ok": true}'
        self._served = False

    def read(self, _size: int = -1) -> bytes:
        if not self._served:
            self._served = True
            return self._first
        raise OSError("falha de leitura apos a resposta")

    def close(self) -> None:
        return None


def test_read_error_after_ok_does_not_approve() -> None:
    # Finding: `_pump_stdout` ignorava `OSError` e publicava os bytes acumulados.
    # Um erro de I/O depois de receber `{"ok": true}` NAO pode aprovar.
    sink: dict[str, object] = {}
    verify_module._pump_stdout(_OkThenBroken(), sink)  # type: ignore[arg-type]
    assert sink.get("io_error") is True
    # O chamador recusa quando houve erro de I/O, mesmo com bytes "ok" lidos.


def test_write_error_is_recorded_and_refused() -> None:
    class _WriteBroken:
        def write(self, _data: bytes) -> int:
            raise OSError("falha de envio")

        def flush(self) -> None:
            return None

        def close(self) -> None:
            return None

    sink: dict[str, object] = {}
    verify_module._pump_stdin(_WriteBroken(), b"x", sink)  # type: ignore[arg-type]
    assert sink.get("io_error") is True


@pytest.mark.usefixtures("spy")
def test_io_error_during_read_refuses_success_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ponta a ponta: um filho que imprime `{"ok": true}` e depois fecha de modo
    # que a leitura do pai sofra erro de I/O deve recusar, nao aprovar. Simulado
    # injetando um `_pump_stdout` que marca `io_error` apos entregar o "ok".
    monkeypatch.setattr(
        verify_module,
        "_CHILD_CODE",
        "import sys\n_=sys.stdin.read()\nsys.stdout.write('{\"ok\": true}')\n",
    )

    def failing_pump(stream: Any, sink: dict[str, object]) -> None:
        with contextlib.suppress(OSError):
            stream.read()
        sink["io_error"] = True

    monkeypatch.setattr(verify_module, "_pump_stdout", failing_pump)
    guard = _watchdog(20.0)
    try:
        with pytest.raises(DatasourceCandidateError) as caught:
            verify_connection_in_child(_conninfo(5432), statement_timeout_ms=30_000, timeout=10)
    finally:
        guard.cancel()
    assert caught.value.category is CandidateFailure.CONNECTION
    _assert_no_verify_threads()


# ---- matriz deterministica de falhas do recolhimento ----------------------


class _Faulty:
    """Popen real envolvido para injetar falhas em `kill`/`wait`/`poll`.

    `mode="once"` falha a primeira chamada e depois delega; `mode="always"`
    falha sempre. Delega o resto ao processo real (inclusive os streams).
    """

    def __init__(self, proc: subprocess.Popen[bytes], op: str, mode: str) -> None:
        self._proc = proc
        self._op = op
        self._mode = mode
        self._failed = False

    def _should_fail(self) -> bool:
        if self._mode == "always":
            return True
        if not self._failed:
            self._failed = True
            return True
        return False

    def kill(self) -> None:
        if self._op == "kill" and self._should_fail():
            raise OSError("kill injetado")
        self._proc.kill()

    def wait(self, timeout: float | None = None) -> int:
        if self._op == "wait" and self._should_fail():
            raise OSError("wait injetado")
        return self._proc.wait(timeout=timeout)

    def poll(self) -> int | None:
        if self._op == "poll" and self._should_fail():
            raise OSError("poll injetado")
        return self._proc.poll()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._proc, name)


def _inject(monkeypatch: pytest.MonkeyPatch, op: str, mode: str, track: list[Any]) -> None:
    real = verify_module._spawn

    def wrap(*args: Any, **kwargs: Any) -> Any:
        proc = real(*args, **kwargs)
        faulty = _Faulty(proc, op, mode)
        track.append(proc)
        return faulty

    monkeypatch.setattr(verify_module, "_spawn", wrap)


@pytest.mark.parametrize("op", ["kill", "wait", "poll"])
def test_transient_supervision_failure_recovers_without_leftovers(
    monkeypatch: pytest.MonkeyPatch, op: str
) -> None:
    # Falha TRANSITORIA (uma vez) em `kill`/`wait`/`poll`: a retentativa recolhe
    # tudo; sem processo/thread/pipe orfao; `CONNECTION`; vaga liberada.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", "import time\ntime.sleep(600)\n")
    track: list[subprocess.Popen[bytes]] = []
    _inject(monkeypatch, op, "once", track)
    before = verify_module._SLOTS._value
    guard = _watchdog(30.0)
    try:
        with pytest.raises(DatasourceCandidateError) as caught:
            verify_connection_in_child(_conninfo(5432), statement_timeout_ms=30_000, timeout=0.25)
    finally:
        guard.cancel()
    assert caught.value.category is CandidateFailure.CONNECTION
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    proc = track[0]
    assert proc.poll() is not None, "processo recolhido"
    assert proc.stdin is not None and proc.stdin.closed
    assert proc.stdout is not None and proc.stdout.closed
    _assert_no_verify_threads()
    assert verify_module._SLOTS._value == before, "vaga liberada apos recolhimento limpo"


def test_persistent_kill_failure_retains_the_slot_and_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Falha PERSISTENTE do `kill()`: o processo nao morre, o recolhimento NAO
    # pode ser confirmado, e o gate NAO finge sucesso nem libera a vaga —
    # fail-closed de capacidade — e a falha vira `CONNECTION` sanitizada. Desde
    # o ownership supervisionado, a vaga fica retida enquanto o recurso vive e
    # volta, uma vez, quando o recolhimento posterior e confirmado.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", "import time\ntime.sleep(600)\n")
    monkeypatch.setattr(verify_module, "_REAP_GRACE_SECONDS", 0.3)
    monkeypatch.setattr(verify_module, "_REAP_ATTEMPTS", 2)
    track: list[subprocess.Popen[bytes]] = []
    _inject(monkeypatch, "kill", "always", track)
    before = verify_module._SLOTS._value
    guard = _watchdog(30.0)
    try:
        with pytest.raises(DatasourceCandidateError) as caught:
            verify_connection_in_child(_conninfo(5432), statement_timeout_ms=30_000, timeout=0.25)
    finally:
        guard.cancel()
        # Limpa o filho que a falha injetada impediu de recolher.
        with contextlib.suppress(Exception):
            track[0].kill()
            track[0].wait(timeout=5)
    assert caught.value.category is CandidateFailure.CONNECTION
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert "injetado" not in str(caught.value)
    # Vaga retida: nunca liberada sobre recurso vivo.
    assert verify_module._SLOTS._value == before - 1
    # O processo real ja foi morto no `finally`: o recolhimento posterior o
    # confirma e devolve a vaga (antes, o teste a devolvia a mao).
    assert verify_module._DEFAULT_SUPERVISOR.collect()
    assert verify_module._SLOTS._value == before


def test_persistent_wait_failure_still_reaps_via_kill_and_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `wait()` falhando sempre NAO impede o recolhimento: `kill()` encerra e
    # `poll()` confirma a morte. O recolhimento e confirmado e a vaga liberada.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", "import time\ntime.sleep(600)\n")
    monkeypatch.setattr(verify_module, "_REAP_GRACE_SECONDS", 0.3)
    monkeypatch.setattr(verify_module, "_REAP_ATTEMPTS", 3)
    track: list[subprocess.Popen[bytes]] = []
    _inject(monkeypatch, "wait", "always", track)
    before = verify_module._SLOTS._value
    guard = _watchdog(30.0)
    try:
        with pytest.raises(DatasourceCandidateError) as caught:
            verify_connection_in_child(_conninfo(5432), statement_timeout_ms=30_000, timeout=0.25)
    finally:
        guard.cancel()
        with contextlib.suppress(Exception):
            track[0].kill()
            track[0].wait(timeout=5)
    assert caught.value.category is CandidateFailure.CONNECTION
    proc = track[0]
    assert proc.poll() is not None
    _assert_no_verify_threads()
    assert verify_module._SLOTS._value == before, "recolhimento confirmado via kill+poll"


def test_oserror_in_the_effective_poll_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    # A conferencia final (`poll()` dentro do `_reap`) nao pode escapar cru: um
    # `OSError` persistente ali vira recurso nao-confirmado -> `CONNECTION`.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", "import sys\n_=sys.stdin.read()\n")
    monkeypatch.setattr(verify_module, "_REAP_GRACE_SECONDS", 0.3)
    monkeypatch.setattr(verify_module, "_REAP_ATTEMPTS", 2)
    track: list[subprocess.Popen[bytes]] = []
    _inject(monkeypatch, "poll", "always", track)
    guard = _watchdog(20.0)
    try:
        with pytest.raises(DatasourceCandidateError) as caught:
            verify_connection_in_child(_conninfo(5432), statement_timeout_ms=30_000, timeout=5)
    finally:
        guard.cancel()
        with contextlib.suppress(Exception):
            track[0].kill()
            track[0].wait(timeout=5)
    assert caught.value.category is CandidateFailure.CONNECTION
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_failure_to_start_the_writer_reaps_and_closes_pipes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Inicializacao parcial no PRIMEIRO start (writer): nenhuma thread arrancou,
    # mas o processo e os dois pipes tem de ser recolhidos/fechados. Como o
    # `start()` nao retornou, o inicio e incerto: a vaga fica retida.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", "import time\ntime.sleep(600)\n")
    real_start = threading.Thread.start

    def flaky_start(self: threading.Thread) -> None:
        if self.name == "maskgw-verify-stdin":
            raise RuntimeError("writer start falha")
        real_start(self)

    monkeypatch.setattr(threading.Thread, "start", flaky_start)
    track: list[subprocess.Popen[bytes]] = []
    _inject(monkeypatch, "none", "once", track)
    before = verify_module._SLOTS._value
    guard = _watchdog(20.0)
    try:
        with pytest.raises(DatasourceCandidateError) as caught:
            verify_connection_in_child(_conninfo(5432), statement_timeout_ms=30_000, timeout=5)
    finally:
        guard.cancel()
        monkeypatch.setattr(threading.Thread, "start", real_start)
    assert caught.value.category is CandidateFailure.CONNECTION
    proc = track[0]
    assert proc.poll() is not None
    assert proc.stdin is not None and proc.stdin.closed
    assert proc.stdout is not None and proc.stdout.closed
    _assert_no_verify_threads()
    assert verify_module._SLOTS._value == before - 1
    assert verify_module._LEDGER.pending == 1


# ---- findings da revisao do 8261dc7: invariante, orcamento e ownership ------

#: Filho que le o stdin ate EOF e responde o ack valido.
_ACK_CHILD = "import sys\n_ = sys.stdin.read()\nsys.stdout.write('{\"ok\": true}')\n"


class _StdoutCloseFails:
    """Proxy do stdout real cujo `close()` falha SEM fechar enquanto `failing`."""

    def __init__(self, real: Any) -> None:
        self._real = real
        self.failing = True

    def read(self, size: int = -1) -> bytes:
        data: bytes = self._real.read(size)
        return data

    def close(self) -> None:
        if self.failing:
            raise OSError("close injetado")
        self._real.close()

    @property
    def closed(self) -> bool:
        return bool(self._real.closed)


def _closed(target: Any) -> bool:
    """Le `closed` sem que o mypy estreite o valor entre chamadas que o mudam."""
    return bool(target.closed)


class _WithStdout:
    """Popen real com o stdout trocado pelo proxy de falha."""

    def __init__(self, proc: subprocess.Popen[bytes], stdout: _StdoutCloseFails) -> None:
        self._proc = proc
        self.stdout = stdout

    def __getattr__(self, name: str) -> Any:
        return getattr(self._proc, name)


def test_persistent_stdout_close_failure_after_valid_ack_never_approves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Finding 1: o filho emite `{"ok": true}` e termina, as threads acabam, mas o
    # pipe de stdout NAO fecha (OSError persistente). Sucesso exige TODOS os
    # pipes efetivamente fechados: aqui e `CONNECTION`, a vaga fica retida e o
    # registro continua sob ownership ate o pipe fechar de verdade.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", _ACK_CHILD)
    monkeypatch.setattr(verify_module, "_REAP_GRACE_SECONDS", 0.3)
    monkeypatch.setattr(verify_module, "_REAP_ATTEMPTS", 2)
    real = verify_module._spawn
    procs: list[subprocess.Popen[bytes]] = []
    proxies: list[_StdoutCloseFails] = []

    def wrap(*args: Any, **kwargs: Any) -> Any:
        proc = real(*args, **kwargs)
        proxy = _StdoutCloseFails(proc.stdout)
        procs.append(proc)
        proxies.append(proxy)
        return _WithStdout(proc, proxy)

    monkeypatch.setattr(verify_module, "_spawn", wrap)
    before = verify_module._SLOTS._value
    guard = _watchdog(30.0)
    try:
        with pytest.raises(DatasourceCandidateError) as caught:
            verify_connection_in_child(_conninfo(5432), statement_timeout_ms=30_000, timeout=10)
    finally:
        guard.cancel()
    assert caught.value.category is CandidateFailure.CONNECTION
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert "injetado" not in str(caught.value)
    assert procs[0].poll() is not None
    assert not _closed(proxies[0]), "o pipe continua aberto"
    # Nunca liberada sobre recurso aberto; o registro segue com dono.
    assert verify_module._SLOTS._value == before - 1
    assert verify_module._LEDGER.pending == 1
    # O SO volta a fechar: o recolhimento posterior libera a vaga uma vez.
    proxies[0].failing = False
    assert verify_module._DEFAULT_SUPERVISOR.collect()
    assert proxies[0].closed
    assert verify_module._LEDGER.pending == 0
    assert verify_module._SLOTS._value == before
    _assert_no_verify_threads()


def test_persistent_kill_failure_cleanup_uses_one_shared_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Finding 2: medido em 8261dc7, `kill()` persistente com entrada de 17.977
    # bytes e prazo 0,1 s levava 18,22 s (3 x [wait 2 + join 2 + join 2]). O
    # cleanup tem UM orcamento compartilhado (`_REAP_ATTEMPTS x
    # _REAP_GRACE_SECONDS`), nao multiplicado por etapa. Esgotado, os recursos
    # vivos NAO sao declarados livres: o registro fica pendente com dono.
    monkeypatch.setattr(verify_module, "_CHILD_CODE", "import time\ntime.sleep(600)\n")
    track: list[subprocess.Popen[bytes]] = []
    _inject(monkeypatch, "kill", "always", track)
    budget = verify_module._REAP_ATTEMPTS * verify_module._REAP_GRACE_SECONDS
    before = verify_module._SLOTS._value
    guard = _watchdog(60.0)
    started = time.monotonic()
    try:
        with pytest.raises(verify_module.VerificationResourceError):
            verify_module._run_child(b"a" * 17977, timeout=0.1)
        elapsed = time.monotonic() - started
        assert elapsed < 0.1 + budget + 1.5, elapsed
        assert track[0].poll() is None, "filho vivo nao e apresentado como recolhido"
        assert verify_module._SLOTS._value == before - 1
        assert verify_module._LEDGER.pending == 1
    finally:
        guard.cancel()
        # O SO "volta a funcionar": o processo real morre fora do gate.
        with contextlib.suppress(Exception):
            track[0].kill()
            track[0].wait(timeout=5)
    guard = _watchdog(30.0)
    try:
        assert verify_module._DEFAULT_SUPERVISOR.collect()
    finally:
        guard.cancel()
    proc = track[0]
    assert proc.stdin is not None and proc.stdin.closed
    assert proc.stdout is not None and proc.stdout.closed
    assert verify_module._LEDGER.pending == 0
    assert verify_module._SLOTS._value == before
    _assert_no_verify_threads()


# ---- integracao com PostgreSQL 16 real -----------------------------------


@_needs_dsn
def test_real_upstream_is_approved_in_process_and_in_child() -> None:
    assert _DSN is not None
    conninfo = make_conninfo(_DSN, connect_timeout=10)
    verify_connection(conninfo, statement_timeout_ms=30_000)  # em processo
    verify_connection_in_child(conninfo, statement_timeout_ms=30_000)  # no filho


@_needs_dsn
def test_real_upstream_with_wrong_secret_is_a_closed_connection_failure() -> None:
    assert _DSN is not None
    from psycopg.conninfo import conninfo_to_dict

    values = conninfo_to_dict(_DSN)
    values["password"] = "senha-errada-para-o-teste"
    values["connect_timeout"] = "10"
    bad = make_conninfo("", **{k: str(v) for k, v in values.items() if v is not None})
    with pytest.raises(DatasourceCandidateError) as caught:
        verify_connection_in_child(bad, statement_timeout_ms=30_000)
    assert caught.value.category is CandidateFailure.CONNECTION


@_needs_dsn
def test_multiple_addresses_pinned_are_used_without_second_resolution() -> None:
    # Nome que nao resolve + enderecos fixados: se o filho tentasse resolver o
    # nome, falharia; conectar prova que ele usou `hostaddr`.
    assert _DSN is not None
    from psycopg.conninfo import conninfo_to_dict

    values = conninfo_to_dict(_DSN)
    host = str(values.get("host") or values.get("hostaddr") or "127.0.0.1")
    conninfo = make_conninfo(
        "",
        host="nao-resolve.invalid,nao-resolve.invalid",
        hostaddr=f"{host},{host}",
        port=str(values.get("port") or 5432),
        dbname=str(values["dbname"]),
        user=str(values["user"]),
        password=str(values.get("password") or ""),
        sslmode="disable",
        connect_timeout=10,
    )
    verify_connection_in_child(conninfo, statement_timeout_ms=30_000)
