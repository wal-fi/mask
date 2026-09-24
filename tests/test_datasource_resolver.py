"""Fase 9, Etapa 4: resolucao DNS com prazo efetivo (D-090, D-092, F9-036).

`getaddrinfo` em processo nao tem timeout nem cancelamento: medido em 11 s
para um nome `.invalid` neste host Windows. O resolver roda num processo filho
morto e recolhido ao fim do prazo. Estes testes provam, sem depender da rede:

- o prazo e efetivo: um filho que nunca responde e cortado perto do prazo;
- nada fica para tras: o filho termina (`returncode` definido) e nenhuma thread
  sobrevive a chamada;
- o filho nao herda segredo do ambiente nem recebe o host por `argv`;
- toda falha e a mesma `DnsResolutionError`, sem host e sem cadeia de excecao;
- `resolve_destination` usa esse resolver por default, e o candidato traduz a
  falha em `DESTINATION`.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

import maskgw.datasource.resolver as resolver_module
from maskgw.datasource.destination import DestinationValidationError, resolve_destination
from maskgw.datasource.models import DestinationPolicy
from maskgw.datasource.resolver import (
    MAX_CONCURRENT_RESOLUTIONS,
    DnsResolutionError,
    bounded_system_resolver,
    resolve_with_timeout,
)
from maskgw.runtime.candidate import (
    CandidateFailure,
    CandidateSpec,
    DatasourceCandidateError,
    build_candidate,
)
from tests.datasource_runtime_support import FakeFactory, draft, secrets_provider

SLOW_CHILD = "import time\ntime.sleep(60)\n"
HOST = "db-canary.internal.example"


class _PopenSpy:
    """Registra cada filho criado, para provar que todos terminaram."""

    def __init__(self) -> None:
        self.processes: list[subprocess.Popen[bytes]] = []
        self.calls: list[tuple[list[str], dict[str, Any]]] = []
        self._original = subprocess.Popen

    def __call__(self, args: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        self.calls.append((list(args), dict(kwargs)))
        process: subprocess.Popen[bytes] = self._original(args, **kwargs)
        self.processes.append(process)
        return process


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> Iterator[_PopenSpy]:
    value = _PopenSpy()
    monkeypatch.setattr(subprocess, "Popen", value)
    yield value
    for process in value.processes:
        assert process.poll() is not None, "processo filho sobreviveu ao resolver"


def _threads() -> set[int | None]:
    return {thread.ident for thread in threading.enumerate()}


def test_resolves_an_ip_literal_in_a_child_process(spy: _PopenSpy) -> None:
    assert bounded_system_resolver("10.0.0.7", 5432) == ("10.0.0.7",)
    assert len(spy.processes) == 1


def test_slow_resolution_is_cut_at_the_deadline_without_leftovers(
    monkeypatch: pytest.MonkeyPatch, spy: _PopenSpy
) -> None:
    monkeypatch.setattr(resolver_module, "_CHILD_CODE", SLOW_CHILD)
    threads = _threads()
    started = time.monotonic()
    with pytest.raises(DnsResolutionError) as caught:
        resolve_with_timeout(HOST, 5432, timeout=0.5)
    elapsed = time.monotonic() - started
    # O filho dormiria 60 s: o corte veio do prazo, e nao do fim do trabalho.
    assert elapsed < 10
    assert elapsed >= 0.5
    assert spy.processes[0].returncode is not None
    assert _threads() == threads
    error = caught.value
    assert error.__cause__ is None
    assert error.__context__ is None
    assert HOST not in str(error)
    assert HOST not in repr(error)


def test_default_deadline_is_applied_by_the_production_resolver(
    monkeypatch: pytest.MonkeyPatch, spy: _PopenSpy
) -> None:
    monkeypatch.setattr(resolver_module, "_CHILD_CODE", SLOW_CHILD)
    monkeypatch.setattr(resolver_module, "DNS_TIMEOUT_SECONDS", 0.5)
    started = time.monotonic()
    with pytest.raises(DnsResolutionError):
        bounded_system_resolver(HOST, 5432)
    assert time.monotonic() - started < 10
    assert all(process.returncode is not None for process in spy.processes)


def test_the_production_deadline_is_five_seconds() -> None:
    assert resolver_module.DNS_TIMEOUT_SECONDS == 5.0


@pytest.mark.parametrize(
    "child",
    [
        "import sys\nsys.exit(3)\n",
        "import sys\nsys.stdout.write('not json')\n",
        "import sys\nsys.stdout.write('[]')\n",
        "import sys\nsys.stdout.write('[1, 2]')\n",
        "import sys\nsys.stdout.write('\"10.0.0.1\"')\n",
        "import sys\nsys.stdout.write('[' + ','.join(['\"10.0.0.1\"'] * 65) + ']')\n",
        "import sys\nsys.stdout.write('x' * 20000)\n",
        "import sys\nsys.stderr.write('segredo no stderr')\nsys.exit(1)\n",
    ],
)
@pytest.mark.usefixtures("spy")
def test_every_child_failure_is_the_same_fixed_error(
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    child: str,
) -> None:
    monkeypatch.setattr(resolver_module, "_CHILD_CODE", child)
    with pytest.raises(DnsResolutionError) as caught:
        resolve_with_timeout(HOST, 5432, timeout=10)
    assert str(caught.value) == "destino nao resolvido"
    assert caught.value.__context__ is None
    # Nada do filho chega ao stdout (canal do MCP) nem ao stderr do processo.
    captured = capfd.readouterr()
    assert captured.out == ""
    assert "segredo" not in captured.err


def test_child_gets_no_secret_and_host_travels_by_stdin(
    monkeypatch: pytest.MonkeyPatch, spy: _PopenSpy
) -> None:
    for name in (
        "MASKGW_DATASOURCE_MASTER_KEY",
        "MASKGW_ADMIN_TOKEN",
        "MASKGW_DATABASE_DSN",
        "MASKGW_HMAC_KEY",
        "PYTHONPATH",
    ):
        monkeypatch.setenv(name, "canary-secret-value")
    echo_env = (
        "import json, os, sys\n"
        "data = json.loads(sys.stdin.read())\n"
        "sys.stdout.write(json.dumps([json.dumps(sorted(os.environ)), data[0], sys.argv[1:]]))\n"
    )
    monkeypatch.setattr(resolver_module, "_CHILD_CODE", echo_env)
    output = resolver_module._run_child(HOST, 5432, timeout=10)
    assert output is not None
    env_names, received_host, argv = json.loads(output)
    assert received_host == HOST
    assert argv == []
    assert not any(name.startswith(("MASKGW", "PYTHON")) for name in json.loads(env_names))
    ((args, kwargs),) = spy.calls
    assert HOST not in " ".join(args)
    assert kwargs["stdin"] is subprocess.PIPE
    assert kwargs["stdout"] is subprocess.PIPE
    assert kwargs["stderr"] is subprocess.DEVNULL
    assert "-I" in args
    assert "canary-secret-value" not in json.dumps(kwargs["env"])


def test_concurrency_is_bounded_and_refused_without_waiting() -> None:
    acquired = 0
    try:
        for _ in range(MAX_CONCURRENT_RESOLUTIONS):
            assert resolver_module._SLOTS.acquire(blocking=False)
            acquired += 1
        started = time.monotonic()
        with pytest.raises(DnsResolutionError):
            resolve_with_timeout(HOST, 5432, timeout=10)
        assert time.monotonic() - started < 1
    finally:
        for _ in range(acquired):
            resolver_module._SLOTS.release()


def test_resolve_destination_uses_the_bounded_resolver_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int]] = []

    def fake(host: str, port: int) -> tuple[str, ...]:
        calls.append((host, port))
        return ("10.0.0.9",)

    monkeypatch.setattr(resolver_module, "bounded_system_resolver", fake)
    resolved = resolve_destination(HOST, 5432, policy=DestinationPolicy())
    assert resolved.addresses == ("10.0.0.9",)
    assert calls == [(HOST, 5432)]


@pytest.mark.usefixtures("spy")
def test_slow_dns_fails_the_candidate_as_destination_within_the_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resolver_module, "_CHILD_CODE", SLOW_CHILD)
    monkeypatch.setattr(resolver_module, "DNS_TIMEOUT_SECONDS", 0.5)
    factory = FakeFactory()
    threads = _threads()
    started = time.monotonic()
    with pytest.raises(DatasourceCandidateError) as caught:
        build_candidate(
            CandidateSpec.from_draft(draft("crm", host=HOST), "segredo"),
            secrets=secrets_provider(),
            adapter_factory=factory,
        )
    assert time.monotonic() - started < 10
    assert caught.value.category is CandidateFailure.DESTINATION
    # Nenhuma conexao foi sequer construida: o destino falhou antes.
    assert factory.adapters == []
    assert _threads() == threads


def test_dns_failure_is_a_destination_validation_error() -> None:
    assert issubclass(DnsResolutionError, DestinationValidationError)


def _python_processes_with(marker: str) -> list[str]:
    """Processos Python vivos cuja linha de comando contem o marcador."""
    if sys.platform == "win32":
        script = (
            "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and "
            f"$_.CommandLine -like '*{marker}*' }} | ForEach-Object {{ $_.ProcessId }}"
        )
        output = subprocess.run(  # noqa: S603 - comando fixo
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        ).stdout
    else:
        output = subprocess.run(
            ["ps", "-eo", "pid=,args="],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        ).stdout
        output = "\n".join(line for line in output.splitlines() if marker in line)
    return [line for line in output.splitlines() if line.strip()]


def test_killing_the_child_leaves_no_interpreter_behind(monkeypatch: pytest.MonkeyPatch) -> None:
    # No Windows, o `python.exe` de um venv e um launcher que cria o
    # interpretador real como neto; o prazo so e efetivo se o neto tambem
    # morrer. Um marcador unico no codigo do filho o torna localizavel.
    marker = f"61.{uuid.uuid4().int % 10**9}"
    code = f"import time\ntime.sleep({marker})\n"
    # Contraprova: a busca encontra um interpretador vivo com o marcador, pelo
    # mesmo executavel (launcher do venv, no Windows) que o resolver usa.
    alive = subprocess.Popen([sys.executable, "-I", "-S", "-c", code])  # noqa: S603
    try:
        deadline = time.monotonic() + 10
        while not _python_processes_with(marker) and time.monotonic() < deadline:
            time.sleep(0.2)
        assert _python_processes_with(marker) != []
    finally:
        alive.kill()
        alive.wait()
    deadline = time.monotonic() + 10
    while _python_processes_with(marker) and time.monotonic() < deadline:
        time.sleep(0.2)
    assert _python_processes_with(marker) == []

    monkeypatch.setattr(resolver_module, "_CHILD_CODE", code)
    with pytest.raises(DnsResolutionError):
        resolve_with_timeout(HOST, 5432, timeout=1.0)
    deadline = time.monotonic() + 10
    while _python_processes_with(marker) and time.monotonic() < deadline:
        time.sleep(0.2)
    assert _python_processes_with(marker) == []
