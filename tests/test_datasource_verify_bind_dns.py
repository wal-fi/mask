"""D-110, opcao B, lote 1: job fixo de DNS do bind PGWire sobre a supervisao D-107.

Prova, sem DNS de rede (so filhos controlados e IP literal):

- o caminho LEGADO da verificacao continua lendo `_CHILD_CODE`,
  `_child_environment` e `MAX_OUTPUT_BYTES` no momento da execucao, com o
  mesmo argv, e nao e afetado pelas constantes do DNS (nem o inverso);
- o filho DNS e `-I -S -B`, com ambiente minimo, host so por `stdin`, `stderr`
  descartado, e devolve a resposta BRUTA (sem escolher, deduplicar nem
  filtrar), com tetos de entrada, saida e numero de entradas;
- prazo ABSOLUTO criado antes da admissao e nunca renovado por spawn,
  `start()` ou coleta lentos; cleanup separado;
- ownership: falha parcial de spawn e de `start()`, falhas de I/O,
  `kill`/`wait`/`poll`/`close` transitorias e persistentes, `BaseException`;
  nada e liberado sobre recurso vivo, e a vaga sai exatamente uma vez;
- 4 vagas proprias, separadas da verificacao e do `resolver.py`, sem fila;
- erro de categoria fechada, mensagem fixa, sem host nem cadeia.

Cada teste roda com vagas e ledgers proprios. Casos com risco de travar tem
watchdog independente que derruba o processo de teste em vez de pendurar.
"""

from __future__ import annotations

import ast
import json
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

import maskgw.datasource.resolver as resolver_module
import maskgw.datasource.verify as verify_module
from maskgw.datasource.verify import (
    MAX_CONCURRENT_VERIFICATIONS,
    BindDnsError,
    BindDnsFailure,
    VerificationSupervisor,
)
from maskgw.runtime.candidate import DatasourceCandidateError
from tests.test_datasource_verify_supervisor import (
    Faults,
    FaultyProcess,
    _cleanup_children,
    _CountingSlots,
    _fail_execute_child,
    _watchdog,
)

# Valores capturados no IMPORT deste modulo, antes de qualquer fixture.
_LEGACY = {
    "VERIFY_TIMEOUT_SECONDS": verify_module.VERIFY_TIMEOUT_SECONDS,
    "MAX_CONCURRENT_VERIFICATIONS": verify_module.MAX_CONCURRENT_VERIFICATIONS,
    "MAX_OUTPUT_BYTES": verify_module.MAX_OUTPUT_BYTES,
    "_MAX_INPUT_BYTES": verify_module._MAX_INPUT_BYTES,
    "_REAP_GRACE_SECONDS": verify_module._REAP_GRACE_SECONDS,
    "_REAP_ATTEMPTS": verify_module._REAP_ATTEMPTS,
    "_ADMISSION_COLLECT_SECONDS": verify_module._ADMISSION_COLLECT_SECONDS,
    "_ENV_ALLOWLIST": verify_module._ENV_ALLOWLIST,
}
#: Ligacao de capacidade do MODULO, tambem capturada no import: a fixture
#: autouse troca ledgers e vagas, entao so esta captura enxerga a original.
_WIRING = {
    "ledger_usa_vagas_do_dns": verify_module._BIND_LEDGER.slots is verify_module._BIND_SLOTS,
    "vagas_distintas_da_verificacao": verify_module._BIND_SLOTS is not verify_module._SLOTS,
    "ledger_distinto_da_verificacao": verify_module._BIND_LEDGER is not verify_module._LEDGER,
    "vagas_distintas_do_resolver": verify_module._BIND_SLOTS is not resolver_module._SLOTS,
    "vagas_iniciais": verify_module._BIND_SLOTS._value,
}
DNS_CODE = verify_module._BIND_DNS_CHILD_CODE
HOST = "gateway.test"
DNS_THREADS = ("maskgw-bind-dns-stdin", "maskgw-bind-dns-stdout")

SLEEP_CHILD = "import time\ntime.sleep(600)\n"
ANSWER = '[[2,"10.0.0.7",0]]'
ACK_CHILD = f"import sys\n_ = sys.stdin.read()\nsys.stdout.write('{ANSWER}')\n"
SLOW_ACK_CHILD = (
    f"import sys, time\n_ = sys.stdin.read()\ntime.sleep(1.5)\nsys.stdout.write('{ANSWER}')\n"
)
FLOOD_CHILD = "import sys\nwhile True:\n    sys.stdout.write('x' * 65536)\n"
EXIT_CHILD = "import sys\nsys.stdout.write('[]')\nsys.stdout.flush()\nsys.exit(7)\n"
LEGACY_ACK = "import sys\n_ = sys.stdin.read()\nsys.stdout.write('{\"ok\": true}')\n"


def _sized_child(size: int) -> str:
    return f"import sys\n_ = sys.stdin.read()\nsys.stdout.write('x' * {size})\n"


def _fake_answers(body: str) -> str:
    """O codigo DNS REAL, com um `getaddrinfo` controlado (sem DNS de rede)."""
    return "import socket\n" + body + "\nsocket.getaddrinfo = fake\n" + DNS_CODE


@dataclass
class Slots:
    dns: _CountingSlots
    verification: _CountingSlots


@pytest.fixture(autouse=True)
def slots(monkeypatch: pytest.MonkeyPatch) -> Iterator[Slots]:
    """Vagas e ledgers proprios, do DNS e da verificacao, por teste."""
    dns = _CountingSlots(verify_module._BIND_DNS_MAX_CONCURRENT)
    monkeypatch.setattr(verify_module, "_BIND_SLOTS", dns)
    monkeypatch.setattr(verify_module, "_BIND_LEDGER", verify_module._Ledger(dns))
    verification = _CountingSlots(MAX_CONCURRENT_VERIFICATIONS)
    ledger = verify_module._Ledger(verification)
    monkeypatch.setattr(verify_module, "_SLOTS", verification)
    monkeypatch.setattr(verify_module, "_LEDGER", ledger)
    monkeypatch.setattr(verify_module, "_DEFAULT_SUPERVISOR", VerificationSupervisor(ledger=ledger))
    # Orcamentos curtos: os casos persistentes nao alongam a suite.
    monkeypatch.setattr(verify_module, "_REAP_GRACE_SECONDS", 0.3)
    monkeypatch.setattr(verify_module, "_REAP_ATTEMPTS", 2)
    monkeypatch.setattr(verify_module, "_ADMISSION_COLLECT_SECONDS", 0.3)
    yield Slots(dns, verification)


@dataclass
class Spawned:
    args: list[str]
    kwargs: dict[str, Any]


class Harness:
    """Cada `Popen` recebe as falhas vigentes; argv/kwargs ficam registrados."""

    def __init__(self) -> None:
        self.next_faults = Faults()
        self.procs: list[subprocess.Popen[bytes]] = []
        self.faults: list[Faults] = []
        self.spawned: list[Spawned] = []
        self.started: list[str] = []


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[Harness]:
    value = Harness()
    real = verify_module._spawn
    real_start = threading.Thread.start

    def wrap(record: Any, args: list[str], **kwargs: Any) -> Any:
        value.spawned.append(Spawned(list(args), dict(kwargs)))
        proc = real(record, args, **kwargs)
        faults = value.next_faults
        value.procs.append(proc)
        value.faults.append(faults)
        return FaultyProcess(proc, faults)

    def start(self: threading.Thread) -> None:
        op = {DNS_THREADS[0]: "start_writer", DNS_THREADS[1]: "start_reader"}.get(self.name)
        if op is None:
            real_start(self)
            return
        value.started.append(self.name)
        faults = value.next_faults
        early = faults.hit(op)
        if early is not None:
            if early.startswith("interrupt"):
                raise KeyboardInterrupt
            msg = "start injetado"
            raise RuntimeError(msg)
        late = faults.hit(f"{op}_late")
        real_start(self)
        if late is not None:
            if late.startswith("interrupt"):
                raise KeyboardInterrupt
            msg = "start injetado"
            raise RuntimeError(msg)

    monkeypatch.setattr(verify_module, "_spawn", wrap)
    monkeypatch.setattr(threading.Thread, "start", start)
    yield value
    for faults in value.faults:
        faults.heal()
    _cleanup_children(value.procs, [])


def _dns_threads_alive() -> list[str]:
    return [t.name for t in threading.enumerate() if t.name.startswith("maskgw-bind-dns-")]


def _assert_no_dns_threads(seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while _dns_threads_alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert _dns_threads_alive() == []


def _assert_fully_reaped(harness: Harness) -> None:
    for proc in harness.procs:
        assert proc.poll() is not None, "processo efetivamente terminado"
        assert proc.stdin is not None and proc.stdin.closed
        assert proc.stdout is not None and proc.stdout.closed
    _assert_no_dns_threads()


def _resolve(host: str = HOST, *, seconds: float = 5.0) -> bytes:
    return verify_module.resolve_bind_host_in_child(host, deadline=time.monotonic() + seconds)


def _failure(host: str = HOST, *, seconds: float = 5.0) -> BindDnsFailure:
    with pytest.raises(BindDnsError) as caught:
        _resolve(host, seconds=seconds)
    error = caught.value
    assert error.__cause__ is None
    assert error.__context__ is None
    assert str(error) == "resolucao do bind nao concluida"
    assert host not in f"{error!s}{error!r}"
    assert "injetado" not in f"{error!s}{error!r}"
    return error.failure


def _run_dns_code(code: str, stdin: bytes) -> subprocess.CompletedProcess[bytes]:
    """Roda o codigo do filho DIRETAMENTE, como o supervisor o roda."""
    return subprocess.run(  # noqa: S603 - interpretador e codigo fixos de teste
        [sys.executable, "-I", "-S", "-B", "-c", code],
        input=stdin,
        capture_output=True,
        timeout=60,
        env=verify_module._bind_dns_environment(),
        check=False,
    )


# ---- legado intacto ---------------------------------------------------------


def test_legacy_verifier_constants_are_unchanged() -> None:
    assert _LEGACY == {
        "VERIFY_TIMEOUT_SECONDS": 12.0,
        "MAX_CONCURRENT_VERIFICATIONS": 4,
        "MAX_OUTPUT_BYTES": 4 * 1024,
        "_MAX_INPUT_BYTES": 64 * 1024,
        "_REAP_GRACE_SECONDS": 2.0,
        "_REAP_ATTEMPTS": 3,
        "_ADMISSION_COLLECT_SECONDS": 1.0,
        "_ENV_ALLOWLIST": (
            "PATH",
            "SYSTEMROOT",
            "SystemRoot",
            "WINDIR",
            "TEMP",
            "TMP",
            "LD_LIBRARY_PATH",
            "DYLD_LIBRARY_PATH",
            "VIRTUAL_ENV",
            "HOME",
            "USERPROFILE",
        ),
    }
    assert verify_module._CHILD_CODE.startswith(
        "import json, sys\nfrom maskgw.datasource.verify import verify_connection\n"
    )
    # Os tetos do DNS sao outros nomes; nada do legado foi reaproveitado.
    assert verify_module._BIND_DNS_MAX_OUTPUT_BYTES == 16 * 1024
    assert verify_module._BIND_DNS_MAX_INPUT_BYTES == 1024
    assert verify_module._BIND_DNS_MAX_ENTRIES == 64
    assert verify_module._BIND_DNS_MAX_CONCURRENT == 4
    assert verify_module._BIND_DNS_TIMEOUT_SECONDS == 5.0


def test_module_capacity_wiring_is_its_own() -> None:
    assert _WIRING == {
        "ledger_usa_vagas_do_dns": True,
        "vagas_distintas_da_verificacao": True,
        "ledger_distinto_da_verificacao": True,
        "vagas_distintas_do_resolver": True,
        "vagas_iniciais": verify_module._BIND_DNS_MAX_CONCURRENT,
    }


def test_legacy_run_reads_patched_symbols_at_execution_and_dns_is_isolated(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots
) -> None:
    marker_env = {"SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
    monkeypatch.setattr(verify_module, "_CHILD_CODE", LEGACY_ACK)
    monkeypatch.setattr(verify_module, "_child_environment", lambda: dict(marker_env))
    supervisor = verify_module._DEFAULT_SUPERVISOR
    supervisor.verify("host=127.0.0.1 dbname=x", statement_timeout_ms=1000, timeout=20)
    legacy = harness.spawned[0]
    assert legacy.args == [sys.executable, "-I", "-c", LEGACY_ACK]
    assert legacy.kwargs["env"] == marker_env
    # O teto legado e lido na execucao: 4 bytes cortam `{"ok": true}`.
    monkeypatch.setattr(verify_module, "MAX_OUTPUT_BYTES", 4)
    with pytest.raises(DatasourceCandidateError):
        supervisor.verify("host=127.0.0.1 dbname=x", statement_timeout_ms=1000, timeout=20)
    # O DNS nao usa nada disso: codigo, ambiente e teto proprios.
    assert _resolve("127.0.0.1") == b'[[2,"127.0.0.1",0]]'
    dns = harness.spawned[-1]
    assert dns.args == [sys.executable, "-I", "-S", "-B", "-c", DNS_CODE]
    assert dns.kwargs["env"] == verify_module._bind_dns_environment()
    # E o inverso: o teto do DNS nao alcanca a verificacao.
    monkeypatch.setattr(verify_module, "MAX_OUTPUT_BYTES", 4 * 1024)
    monkeypatch.setattr(verify_module, "_BIND_DNS_MAX_OUTPUT_BYTES", 1)
    supervisor.verify("host=127.0.0.1 dbname=x", statement_timeout_ms=1000, timeout=20)
    assert slots.verification.free == MAX_CONCURRENT_VERIFICATIONS
    assert slots.dns.free == verify_module._BIND_DNS_MAX_CONCURRENT
    _assert_fully_reaped(harness)


def test_verify_module_does_not_import_pgwire() -> None:
    tree = ast.parse(Path(verify_module.__file__).read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    assert not [name for name in modules if name.startswith("maskgw.pgwire")]
    assert "maskgw.pgwire" not in DNS_CODE


# ---- filho DNS: isolamento e resposta bruta ---------------------------------


@pytest.mark.parametrize(
    ("literal", "expected"),
    [
        ("127.0.0.1", [[int(socket.AF_INET), "127.0.0.1", 0]]),
        ("::1", [[int(socket.AF_INET6), "::1", 0]]),
    ],
)
def test_real_child_resolves_ip_literals_without_network_dns(
    harness: Harness, literal: str, expected: list[list[object]]
) -> None:
    output = _resolve(literal)
    assert json.loads(output.decode("ascii")) == expected
    assert output.isascii()
    _assert_fully_reaped(harness)


def test_child_is_isolated_and_host_travels_only_by_stdin(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, capfd: pytest.CaptureFixture[str]
) -> None:
    planted = "postgresql://u:segredo-do-teste@db.invalid/x"
    monkeypatch.setenv("MASKGW_DATABASE_DSN", planted)
    monkeypatch.setenv("MASKGW_PGWIRE_PASSWORD", "segredo-do-teste")
    monkeypatch.setenv("PYTHONPATH", "nao-deve-chegar")
    echo = (
        "import json, os, sys\n"
        "data = sys.stdin.buffer.read()\n"
        "sys.stderr.write('MARCA-STDERR-DO-FILHO')\n"
        "sys.stdout.write(json.dumps({'env': dict(os.environ), 'argv': sys.argv,\n"
        "    'stdin': data.decode('ascii'), 'flags': [sys.flags.isolated,\n"
        "    sys.flags.no_site, sys.flags.dont_write_bytecode]}))\n"
    )
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", echo)
    host = "segredo-do-host.test"
    seen = json.loads(_resolve(host).decode("ascii"))
    expected_env = {"SYSTEMROOT": os.environ["SYSTEMROOT"]} if sys.platform == "win32" else {}
    assert verify_module._bind_dns_environment() == expected_env
    assert seen["env"] == expected_env
    assert seen["argv"] == ["-c"]
    assert json.loads(seen["stdin"]) == host
    assert seen["flags"] == [1, 1, 1]
    (spawned,) = harness.spawned
    assert host not in " ".join(spawned.args)
    env_values = spawned.kwargs["env"].values()
    assert all(host not in value and planted not in value for value in env_values)
    assert spawned.kwargs["stderr"] is subprocess.DEVNULL
    assert spawned.kwargs["stdin"] is subprocess.PIPE
    assert spawned.kwargs["stdout"] is subprocess.PIPE
    assert spawned.kwargs["close_fds"] is True
    captured = capfd.readouterr()
    assert "MARCA-STDERR-DO-FILHO" not in captured.err + captured.out
    _assert_fully_reaped(harness)


def test_child_returns_the_raw_answer_without_choosing_dedup_or_filtering(
    monkeypatch: pytest.MonkeyPatch, harness: Harness
) -> None:
    fake = (
        "def fake(*args, **kwargs):\n"
        f"    if args != ({HOST!r}, None, socket.AF_UNSPEC, socket.SOCK_STREAM) or kwargs:\n"
        "        raise RuntimeError\n"
        "    return [\n"
        "        (socket.AF_INET, 1, 6, '', ('10.0.0.1', 0)),\n"
        "        (socket.AF_INET, 1, 6, '', ('10.0.0.1', 0)),\n"
        "        (socket.AF_INET6, 1, 6, '', ('fe80::1', 0, 0, 5)),\n"
        "        (socket.AF_INET6, 1, 6, '', ('2001:db8::1', 0, 0, 0)),\n"
        "        (999, 1, 6, '', 'nao-e-tupla'),\n"
        "        (socket.AF_INET, 1, 6, '', (b'bytes', 0)),\n"
        "    ]\n"
    )
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", _fake_answers(fake))
    answer = json.loads(_resolve().decode("ascii"))
    inet, inet6 = int(socket.AF_INET), int(socket.AF_INET6)
    assert answer == [
        [inet, "10.0.0.1", 0],
        [inet, "10.0.0.1", 0],
        [inet6, "fe80::1", 5],
        [inet6, "2001:db8::1", 0],
        [999, None, 0],
        [inet, None, 0],
    ]
    _assert_fully_reaped(harness)


@pytest.mark.parametrize(("count", "accepted"), [(64, True), (65, False)])
def test_raw_entry_bound_is_applied_before_any_dedup(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, count: int, accepted: bool
) -> None:
    # Entradas IGUAIS: deduplicar antes do teto esconderia o excesso.
    fake = (
        "def fake(*args, **kwargs):\n"
        f"    return [(socket.AF_INET, 1, 6, '', ('10.0.0.1', 0))] * {count}\n"
    )
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", _fake_answers(fake))
    if accepted:
        assert len(json.loads(_resolve())) == count
    else:
        assert _failure() is BindDnsFailure.FAILED
    _assert_fully_reaped(harness)


@pytest.mark.parametrize(
    ("label", "fake", "stdin"),
    [
        (
            "saida-acima-do-teto-no-filho",
            "def fake(*a, **k):\n    return [(socket.AF_INET, 1, 6, '', ('x' * 300, 0))] * 64\n",
            json.dumps(HOST).encode("ascii"),
        ),
        (
            "getaddrinfo-falha",
            "def fake(*a, **k):\n    raise socket.gaierror(11001, 'falha injetada')\n",
            json.dumps(HOST).encode("ascii"),
        ),
        (
            "resposta-vazia",
            "def fake(*a, **k):\n    return []\n",
            json.dumps(HOST).encode("ascii"),
        ),
        (
            "entrada-acima-de-1-kib",
            "def fake(*a, **k):\n    return [(socket.AF_INET, 1, 6, '', ('10.0.0.1', 0))]\n",
            json.dumps("h" * 1100).encode("ascii"),
        ),
        (
            "host-nao-texto",
            "def fake(*a, **k):\n    return [(socket.AF_INET, 1, 6, '', ('10.0.0.1', 0))]\n",
            b"123",
        ),
        (
            "host-vazio",
            "def fake(*a, **k):\n    return [(socket.AF_INET, 1, 6, '', ('10.0.0.1', 0))]\n",
            b'""',
        ),
    ],
)
def test_child_side_bounds_and_failures_exit_without_output(
    label: str, fake: str, stdin: bytes
) -> None:
    del label
    result = _run_dns_code(_fake_answers(fake), stdin)
    assert result.returncode == 3
    assert result.stdout == b""


def test_child_side_output_bound_also_fails_through_the_supervisor(
    monkeypatch: pytest.MonkeyPatch, harness: Harness
) -> None:
    fake = "def fake(*a, **k):\n    return [(socket.AF_INET, 1, 6, '', ('x' * 300, 0))] * 64\n"
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", _fake_answers(fake))
    assert _failure() is BindDnsFailure.FAILED
    _assert_fully_reaped(harness)


# ---- entrada recusada antes do spawn ----------------------------------------


@pytest.mark.parametrize("host", ["", "h" * 1100, 7, None, b"gateway.test"])
def test_invalid_or_oversized_host_is_refused_before_spawn(
    harness: Harness, slots: Slots, host: Any
) -> None:
    with pytest.raises(BindDnsError) as caught:
        verify_module.resolve_bind_host_in_child(host)
    assert caught.value.failure is BindDnsFailure.REFUSED
    assert caught.value.__context__ is None
    assert harness.spawned == []
    assert slots.dns.free == verify_module._BIND_DNS_MAX_CONCURRENT
    assert slots.dns.releases == 0


# ---- tetos de saida e falhas do filho ---------------------------------------


@pytest.mark.parametrize(("size", "accepted"), [(16 * 1024, True), (16 * 1024 + 1, False)])
def test_stdout_bound_is_exact(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots, size: int, accepted: bool
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", _sized_child(size))
    if accepted:
        assert len(_resolve()) == size
    else:
        assert _failure() is BindDnsFailure.FAILED
    assert slots.dns.releases == 1
    _assert_fully_reaped(harness)


def test_continuous_stdout_is_cut_during_reading_well_before_the_deadline(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", FLOOD_CHILD)
    guard = _watchdog(60.0)
    try:
        started = time.monotonic()
        assert _failure(seconds=30.0) is BindDnsFailure.FAILED
        assert time.monotonic() - started < 10, "cortado pelo teto, nao pelo prazo"
        assert slots.dns.releases == 1
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


def test_child_that_never_reads_stdin_is_cut_at_the_deadline(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", SLEEP_CHILD)
    guard = _watchdog(60.0)
    try:
        started = time.monotonic()
        assert _failure(seconds=0.5) is BindDnsFailure.FAILED
        elapsed = time.monotonic() - started
        assert 0.5 <= elapsed < 0.5 + 0.6 + 3.0, "prazo mais uma passada curta de cleanup"
        assert slots.dns.releases == 1
        assert slots.dns.free == verify_module._BIND_DNS_MAX_CONCURRENT
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


def test_nonzero_exit_with_output_is_a_failure(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", EXIT_CHILD)
    assert _failure() is BindDnsFailure.FAILED
    assert slots.dns.releases == 1
    _assert_fully_reaped(harness)


@pytest.mark.parametrize("op", ["read", "write"])
def test_io_error_never_approves_even_with_a_valid_answer(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots, op: str
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", ACK_CHILD)
    harness.next_faults = Faults({op: "always"})
    assert _failure() is BindDnsFailure.FAILED
    assert slots.dns.releases == 1
    _assert_fully_reaped(harness)


# ---- prazo absoluto, nunca renovado -----------------------------------------


def test_expired_deadline_spawns_nothing(harness: Harness, slots: Slots) -> None:
    with pytest.raises(BindDnsError) as caught:
        verify_module.resolve_bind_host_in_child("127.0.0.1", deadline=time.monotonic() - 0.01)
    assert caught.value.failure is BindDnsFailure.REFUSED
    assert harness.spawned == []
    assert slots.dns.releases == 0
    assert slots.dns.free == verify_module._BIND_DNS_MAX_CONCURRENT


class _SpyLedger(verify_module._Ledger):
    """Ledger real que registra o prazo de cada coleta; opcionalmente lenta."""

    def __init__(self, slots: threading.BoundedSemaphore, *, slow: bool) -> None:
        super().__init__(slots)
        self.seen: list[float] = []
        self.slow = slow

    def collect_until(self, deadline: float) -> bool:
        self.seen.append(deadline)
        if self.slow:
            # Coleta que so devolve depois do prazo (SO lento).
            time.sleep(max(0.0, deadline - time.monotonic()) + 0.05)
        return super().collect_until(deadline)


class _ReadyRecord:
    """Registro pendente minimo, pronto para recolher (so o que o ledger usa)."""

    def __init__(self, ledger: verify_module._Ledger, on_reap: Any) -> None:
        self.in_flight = False
        self.claimer: object | None = None
        self.owner = verify_module._BIND_OWNER
        self._on_reap = on_reap
        self._ledger = ledger

    def reap(self, deadline: float) -> bool:
        return bool(self._on_reap(self, deadline))


#: Referencias fortes a todo registro plantado: sem elas, um `id()` de um
#: registro ja recolhido pode ser reaproveitado por um novo, e o `visited` por
#: `id` do `collect` legado o pularia (parada antecipada, conservadora).
_PLANTED: list[_ReadyRecord] = []


def _plant(ledger: verify_module._Ledger, on_reap: Any) -> _ReadyRecord:
    with ledger.lock:
        assert ledger.slots.acquire(blocking=False)
        record = _ReadyRecord(ledger, on_reap)
        ledger.records.append(cast(Any, record))
    _PLANTED.append(record)
    return record


def test_admission_collection_does_not_follow_records_arriving_during_it() -> None:
    # Cada recolhimento faz "outro build" deixar um pendente novo, pronto. A
    # coleta da admissao so visita os que existiam no inicio da passada.
    ledger = verify_module._BIND_LEDGER
    seen: list[float] = []

    def arriving(_record: _ReadyRecord, deadline: float) -> bool:
        seen.append(deadline)
        if len(seen) < 50:
            _plant(ledger, arriving)
        return True

    _PLANTED.clear()
    _plant(ledger, arriving)
    deadline = time.monotonic() + 5.0
    ledger.collect_until(deadline)
    assert len(seen) == 1, "so o pendente que existia no inicio"
    assert len(ledger.records) == 1, "o que chegou durante a coleta ficou para depois"
    # Contraprova: o `collect` da verificacao (inalterado) segue os que chegam.
    ledger.collect(deadline)
    assert len(seen) == 50
    assert ledger.records == []
    _PLANTED.clear()


def test_admission_collection_stops_claiming_at_the_deadline(slots: Slots) -> None:
    ledger = verify_module._BIND_LEDGER
    seen: list[str] = []

    def slow(_record: _ReadyRecord, deadline: float) -> bool:
        seen.append("primeiro" if not seen else "segundo")
        time.sleep(max(0.0, deadline - time.monotonic()) + 0.05)
        return True

    _plant(ledger, slow)
    _plant(ledger, slow)
    ledger.collect_until(time.monotonic() + 0.3)
    assert seen == ["primeiro"], "o segundo nao e reivindicado depois do prazo"
    assert len(ledger.records) == 1
    assert slots.dns.free == verify_module._BIND_DNS_MAX_CONCURRENT - 1


def test_default_deadline_starts_before_admission(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots
) -> None:
    # A coleta da admissao recebe um prazo que NAO passa do instante calculado
    # na entrada: o relogio do trabalho comecou antes dela.
    monkeypatch.setattr(verify_module, "_BIND_DNS_TIMEOUT_SECONDS", 3.0)
    monkeypatch.setattr(verify_module, "_ADMISSION_COLLECT_SECONDS", 30.0)
    ledger = _SpyLedger(slots.dns, slow=False)
    monkeypatch.setattr(verify_module, "_BIND_LEDGER", ledger)
    before = time.monotonic()
    assert verify_module.resolve_bind_host_in_child("127.0.0.1") == b'[[2,"127.0.0.1",0]]'
    (limit,) = ledger.seen
    assert before < limit <= before + 3.0 + 0.05
    _assert_fully_reaped(harness)


def test_slow_admission_collection_consumes_the_same_deadline(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots
) -> None:
    monkeypatch.setattr(verify_module, "_ADMISSION_COLLECT_SECONDS", 30.0)
    ledger = _SpyLedger(slots.dns, slow=True)
    monkeypatch.setattr(verify_module, "_BIND_LEDGER", ledger)
    seen = ledger.seen
    deadline = time.monotonic() + 0.4
    with pytest.raises(BindDnsError) as caught:
        verify_module.resolve_bind_host_in_child("127.0.0.1", deadline=deadline)
    assert caught.value.failure is BindDnsFailure.REFUSED
    assert seen == [deadline], "coleta limitada pelo MESMO prazo, nao por um novo"
    assert harness.spawned == []
    assert slots.dns.free == verify_module._BIND_DNS_MAX_CONCURRENT


@pytest.mark.parametrize("budget", [0.4, 20.0], ids=["prazo-vencido-no-spawn", "contraprova"])
def test_late_spawn_does_not_renew_the_deadline(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots, budget: float
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", ACK_CHILD)
    spawn = verify_module._spawn  # o do harness

    def late(*args: Any, **kwargs: Any) -> Any:
        time.sleep(0.6)
        return spawn(*args, **kwargs)

    monkeypatch.setattr(verify_module, "_spawn", late)
    guard = _watchdog(60.0)
    try:
        if budget < 0.6:
            # O filho responderia na hora: so o prazo nao renovado o recusa.
            assert _failure(seconds=budget) is BindDnsFailure.FAILED
            assert harness.started == [], "nenhum pump iniciado depois do prazo"
        else:
            assert _resolve(seconds=budget) == ANSWER.encode("ascii")
        assert slots.dns.releases == 1
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


@pytest.mark.parametrize("budget", [0.4, 20.0], ids=["wait-volta-apos-o-prazo", "contraprova"])
def test_late_returning_wait_cannot_approve(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots, budget: float
) -> None:
    # O filho termina na hora, mas o `wait()` so DEVOLVE depois do prazo.
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", ACK_CHILD)
    spawn = verify_module._spawn  # o do harness

    def late_wait(*args: Any, **kwargs: Any) -> Any:
        # O harness devolve o envelope `FaultyProcess`, cujo `wait` e trocavel.
        process: Any = spawn(*args, **kwargs)
        real_wait = process.wait

        def wait(timeout: float | None = None) -> int:
            code: int = real_wait(timeout=timeout)
            time.sleep(0.6)
            return code

        process.wait = wait
        return process

    monkeypatch.setattr(verify_module, "_spawn", late_wait)
    guard = _watchdog(60.0)
    try:
        if budget < 0.6:
            assert _failure(seconds=budget) is BindDnsFailure.FAILED
        else:
            assert _resolve(seconds=budget) == ANSWER.encode("ascii")
        assert slots.dns.releases == 1
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


@pytest.mark.parametrize("held", [True, False], ids=["leitura-so-no-cleanup", "contraprova"])
def test_answer_read_only_during_cleanup_cannot_approve(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots, held: bool
) -> None:
    # O filho termina no prazo; os bytes so chegam ao pai quando o cleanup
    # libera o leitor. Concluir ai aprovaria uma resposta lida fora do prazo.
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", ACK_CHILD)
    release = threading.Event()
    read_done = threading.Event()
    original_reader = verify_module._pump_bind_dns_stdout
    original_reap = verify_module._ChildRecord.reap

    def held_reader(stream: Any, sink: dict[str, bytes | bool]) -> None:
        try:
            if held:
                release.wait(30)
            else:
                time.sleep(0.3)  # atrasa, mas termina dentro do prazo
            original_reader(stream, sink)
        finally:
            read_done.set()

    def reap(record: Any, deadline: float) -> bool:
        # So o harness: solta o leitor retido e espera ele terminar ANTES de o
        # recolhimento real fechar os pipes. A decisao de aprovar ja foi
        # tomada antes daqui (fora do prazo), entao o cenario adverso fica.
        release.set()
        assert read_done.wait(30), "o leitor do teste terminou"
        return bool(original_reap(record, deadline))

    monkeypatch.setattr(verify_module, "_pump_bind_dns_stdout", held_reader)
    monkeypatch.setattr(verify_module._ChildRecord, "reap", reap)
    guard = _watchdog(60.0)
    try:
        if held:
            assert _failure(seconds=1.0) is BindDnsFailure.FAILED
        else:
            assert _resolve(seconds=20.0) == ANSWER.encode("ascii")
        assert slots.dns.releases == 1
        _assert_fully_reaped(harness)
    finally:
        release.set()
        guard.cancel()


def test_late_thread_start_does_not_renew_the_deadline(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", ACK_CHILD)
    patched = threading.Thread.start  # o do harness

    def slow_start(self: threading.Thread) -> None:
        patched(self)
        if self.name == DNS_THREADS[0]:
            time.sleep(0.6)

    monkeypatch.setattr(threading.Thread, "start", slow_start)
    guard = _watchdog(60.0)
    try:
        assert _failure(seconds=0.4) is BindDnsFailure.FAILED
        assert harness.started == [DNS_THREADS[0]], "o leitor nao e iniciado apos o prazo"
        assert slots.dns.releases == 1
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


# ---- ownership: spawn parcial, start parcial, falhas do SO -----------------


@pytest.mark.parametrize("error", [KeyboardInterrupt, OSError], ids=["interrupt", "OSError"])
def test_spawn_failing_before_the_constructor_consumes_no_capacity(
    monkeypatch: pytest.MonkeyPatch, slots: Slots, error: type[BaseException]
) -> None:
    def never_entered(*_args: Any, **_kwargs: Any) -> Any:
        if error is OSError:
            msg = "spawn injetado"
            raise OSError(msg)
        raise error

    monkeypatch.setattr(verify_module, "_spawn", never_entered)
    if error is KeyboardInterrupt:
        with pytest.raises(KeyboardInterrupt):
            _resolve("127.0.0.1")
    else:
        assert _failure("127.0.0.1") is BindDnsFailure.REFUSED
    assert verify_module._BIND_LEDGER.pending == 0
    assert slots.dns.releases == 1
    assert slots.dns.free == verify_module._BIND_DNS_MAX_CONCURRENT


@pytest.mark.parametrize("error", [KeyboardInterrupt, OSError], ids=["interrupt", "OSError"])
def test_constructor_failing_after_real_creation_is_reaped(
    monkeypatch: pytest.MonkeyPatch, slots: Slots, error: type[BaseException]
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", SLEEP_CHILD)
    created: list[subprocess.Popen[bytes]] = []
    guard = _watchdog(30.0)
    try:
        with monkeypatch.context() as patch:
            _fail_execute_child(patch, create=True, error=error, created=created)
            if error is KeyboardInterrupt:
                with pytest.raises(KeyboardInterrupt):
                    _resolve()
            else:
                assert _failure() is BindDnsFailure.FAILED
        (proc,) = created
        assert proc.poll() is not None
        assert proc.stdin is not None and proc.stdin.closed
        assert proc.stdout is not None and proc.stdout.closed
        assert verify_module._BIND_LEDGER.pending == 0
        assert slots.dns.releases == 1
        _assert_no_dns_threads()
    finally:
        guard.cancel()
        _cleanup_children(created, [])


@pytest.mark.parametrize("error", [KeyboardInterrupt, OSError], ids=["interrupt", "OSError"])
def test_constructor_failing_before_creation_is_uncertain_and_retained(
    monkeypatch: pytest.MonkeyPatch, slots: Slots, error: type[BaseException]
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", SLEEP_CHILD)
    created: list[subprocess.Popen[bytes]] = []
    guard = _watchdog(30.0)
    try:
        with monkeypatch.context() as patch:
            _fail_execute_child(patch, create=False, error=error, created=created)
            if error is KeyboardInterrupt:
                with pytest.raises(KeyboardInterrupt):
                    _resolve()
            else:
                assert _failure() is BindDnsFailure.INCOMPLETE
        assert created == []
        ledger = verify_module._BIND_LEDGER
        (record,) = ledger.records
        assert record.owner is verify_module._BIND_OWNER
        assert slots.dns.releases == 0
        assert slots.dns.free == verify_module._BIND_DNS_MAX_CONCURRENT - 1
        started = time.monotonic()
        assert not ledger.collect(time.monotonic() + 5.0)
        assert time.monotonic() - started < 0.5, "incerto nao queima orcamento"
        assert slots.dns.releases == 0
    finally:
        guard.cancel()
        _cleanup_children(created, [])


@pytest.mark.parametrize("side", ["writer", "reader"])
def test_thread_start_that_did_not_return_is_uncertain_and_retained(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots, side: str
) -> None:
    # `start()` levantou sem retornar: nada prova que a thread nativa nunca
    # existira. Processo e pipes recolhidos, mas registro e vaga retidos, nem
    # a cura do SO libera (mesma garantia estrita do verificador, D-107).
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", SLEEP_CHILD)
    harness.next_faults = Faults({f"start_{side}": "always"})
    guard = _watchdog(30.0)
    try:
        assert _failure() is BindDnsFailure.INCOMPLETE
        for faults in harness.faults:
            faults.heal()
        ledger = verify_module._BIND_LEDGER
        assert not ledger.collect(time.monotonic() + 1.0)
        assert ledger.pending == 1
        assert slots.dns.releases == 0
        assert slots.dns.free == verify_module._BIND_DNS_MAX_CONCURRENT - 1
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


@pytest.mark.parametrize("side", ["writer", "reader"])
def test_interrupt_before_the_real_start_retains_conservatively(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots, side: str
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", SLEEP_CHILD)
    harness.next_faults = Faults({f"start_{side}": "interrupt-once"})
    guard = _watchdog(30.0)
    try:
        with pytest.raises(KeyboardInterrupt):
            _resolve()
        assert verify_module._BIND_LEDGER.pending == 1
        assert slots.dns.releases == 0
        assert not verify_module._BIND_LEDGER.collect(time.monotonic() + 1.0)
        assert slots.dns.releases == 0
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


@pytest.mark.parametrize("mode", ["always", "interrupt-once"])
def test_thread_started_before_start_raises_keeps_ownership_until_it_ends(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots, mode: str
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", SLEEP_CHILD)
    hold = threading.Event()
    original = verify_module._pump_stdin

    def held_pump(*args: Any) -> None:
        try:
            original(*args)
        finally:
            hold.wait(30)

    monkeypatch.setattr(verify_module, "_pump_stdin", held_pump)
    harness.next_faults = Faults({"start_writer_late": mode})
    guard = _watchdog(60.0)
    try:
        if mode == "always":
            assert _failure() is BindDnsFailure.INCOMPLETE
        else:
            with pytest.raises(KeyboardInterrupt):
                _resolve()
        assert DNS_THREADS[0] in _dns_threads_alive()
        proc = harness.procs[0]
        assert proc.poll() is not None
        ledger = verify_module._BIND_LEDGER
        assert ledger.pending == 1
        assert slots.dns.releases == 0
        assert not ledger.collect(time.monotonic() + 1.0)
        hold.set()
        assert ledger.collect(time.monotonic() + 5.0)
        assert slots.dns.releases == 1
        assert slots.dns.free == verify_module._BIND_DNS_MAX_CONCURRENT
        _assert_fully_reaped(harness)
    finally:
        hold.set()
        guard.cancel()


_FAULTS = [
    ({}, "reaped"),
    ({"kill": "once"}, "reaped"),
    ({"poll": "once"}, "reaped"),
    ({"wait": "always"}, "reaped"),
    ({"close_stdin": "once"}, "reaped"),
    ({"close_stdout": "once"}, "reaped"),
    ({"kill": "always"}, "retained"),
    ({"poll": "always"}, "retained"),
    ({"close_stdin": "always"}, "retained"),
    ({"close_stdout": "always"}, "retained"),
]


@pytest.mark.parametrize(("spec", "outcome"), _FAULTS, ids=[str(s) for s, _ in _FAULTS])
def test_os_fault_matrix_never_frees_capacity_over_live_resources(
    monkeypatch: pytest.MonkeyPatch,
    harness: Harness,
    slots: Slots,
    spec: dict[str, str],
    outcome: str,
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", SLEEP_CHILD)
    harness.next_faults = Faults(spec)
    guard = _watchdog(60.0)
    try:
        failure = _failure(seconds=0.5)
        ledger = verify_module._BIND_LEDGER
        if outcome == "reaped":
            assert failure is BindDnsFailure.FAILED
            assert ledger.pending == 0
            assert slots.dns.releases == 1
            _assert_fully_reaped(harness)
            return
        assert failure is BindDnsFailure.INCOMPLETE
        (record,) = ledger.records
        assert record.owner is verify_module._BIND_OWNER
        assert slots.dns.releases == 0
        assert slots.dns.free == verify_module._BIND_DNS_MAX_CONCURRENT - 1
        # Persistente: a passada seguinte tambem nao libera.
        assert not ledger.collect(time.monotonic() + 0.5)
        assert slots.dns.releases == 0
        # O SO volta: a PROXIMA admissao recolhe o pendente e segue.
        harness.faults[0].heal()
        harness.next_faults = Faults()
        monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", ACK_CHILD)
        assert _resolve() == ANSWER.encode("ascii")
        assert ledger.pending == 0
        assert slots.dns.releases == 2
        assert slots.dns.free == verify_module._BIND_DNS_MAX_CONCURRENT
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


def test_base_exception_in_the_owner_reaps_and_propagates(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", SLEEP_CHILD)
    harness.next_faults = Faults({"wait": "interrupt-once"})
    guard = _watchdog(30.0)
    try:
        with pytest.raises(KeyboardInterrupt):
            _resolve()
        assert verify_module._BIND_LEDGER.pending == 0
        assert slots.dns.releases == 1
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


def test_base_exception_with_unreapable_child_keeps_ownership(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", SLEEP_CHILD)
    harness.next_faults = Faults({"wait": "interrupt-once", "kill": "always"})
    guard = _watchdog(30.0)
    try:
        with pytest.raises(KeyboardInterrupt):
            _resolve()
        (record,) = verify_module._BIND_LEDGER.records
        assert record.owner is verify_module._BIND_OWNER
        assert slots.dns.releases == 0
        harness.faults[0].heal()
        assert verify_module._BIND_LEDGER.collect(time.monotonic() + 5.0)
        assert slots.dns.releases == 1
        _assert_fully_reaped(harness)
    finally:
        guard.cancel()


# ---- capacidade propria, sem fila -------------------------------------------


def test_retained_records_refuse_new_admission_without_spawning(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", SLEEP_CHILD)
    guard = _watchdog(120.0)
    try:
        for index in range(verify_module._BIND_DNS_MAX_CONCURRENT):
            harness.next_faults = Faults({"kill": "always"})
            if index:
                # A coleta dos pendentes ja consome o MESMO prazo: com 0,3 s
                # (= a coleta curta), nada sobra e a admissao recusa sem spawn.
                assert _failure(seconds=0.3) is BindDnsFailure.REFUSED
            assert _failure(seconds=1.0) is BindDnsFailure.INCOMPLETE
        assert slots.dns.free == 0
        spawned = len(harness.spawned)
        started = time.monotonic()
        assert _failure(seconds=5.0) is BindDnsFailure.REFUSED
        assert time.monotonic() - started < 2.0, "recusa sem fila nem espera do prazo"
        assert len(harness.spawned) == spawned
        assert slots.verification.free == MAX_CONCURRENT_VERIFICATIONS
    finally:
        for faults in harness.faults:
            faults.heal()
        assert verify_module._BIND_LEDGER.collect(time.monotonic() + 10.0)
        guard.cancel()


def test_four_concurrent_resolutions_and_capacity_distinct_from_verification(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, slots: Slots
) -> None:
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", SLOW_ACK_CHILD)
    monkeypatch.setattr(verify_module, "_CHILD_CODE", LEGACY_ACK)
    resolver_free = resolver_module._SLOTS._value
    results: list[bytes | BaseException] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            value: bytes | BaseException = _resolve(seconds=20.0)
        except BaseException as exc:
            value = exc
        with lock:
            results.append(value)

    guard = _watchdog(120.0)
    threads = [
        threading.Thread(target=worker, name=f"teste-dns-{index}")
        for index in range(verify_module._BIND_DNS_MAX_CONCURRENT)
    ]
    try:
        for thread in threads:
            thread.start()
        deadline = time.monotonic() + 15
        while slots.dns.free > 0 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert slots.dns.free == 0, "as 4 resolucoes estao em voo"
        started = time.monotonic()
        assert _failure(seconds=20.0) is BindDnsFailure.REFUSED
        assert time.monotonic() - started < 1.5, "quinta recusada sem fila"
        # Vagas distintas: a verificacao continua admitindo.
        assert slots.verification.free == MAX_CONCURRENT_VERIFICATIONS
        verify_module._DEFAULT_SUPERVISOR.verify(
            "host=127.0.0.1 dbname=x", statement_timeout_ms=1000, timeout=20
        )
        assert resolver_module._SLOTS._value == resolver_free
    finally:
        for thread in threads:
            thread.join(60)
        guard.cancel()
    assert results == [ANSWER.encode("ascii")] * verify_module._BIND_DNS_MAX_CONCURRENT
    assert slots.dns.releases == verify_module._BIND_DNS_MAX_CONCURRENT
    assert slots.dns.free == verify_module._BIND_DNS_MAX_CONCURRENT
    _assert_fully_reaped(harness)


def test_failure_categories_are_closed() -> None:
    assert {item.value for item in BindDnsFailure} == {"refused", "failed", "incomplete"}
    error = BindDnsError(BindDnsFailure.FAILED)
    assert str(error) == "resolucao do bind nao concluida"
    assert repr(verify_module._BIND_OWNER) == "BindDnsOwner()"
    # Interno: nada novo no `__all__` publico do modulo.
    assert not {"resolve_bind_host_in_child", "BindDnsError", "BindDnsFailure"} & set(
        verify_module.__all__
    )
