"""Resolucao DNS com prazo efetivo, sem thread nem conexao abandonada (D-092).

`socket.getaddrinfo` nao tem timeout nem cancelamento portatil: uma thread que
a chama fica presa ate o resolver do sistema desistir — medido em 11 s para um
nome `.invalid` num host Windows. Uma thread com `join(timeout=...)` so
esconderia essa espera, deixando a thread viva depois do prazo, e D-090 proibe
exatamente isso.

Aqui a resolucao roda num PROCESSO FILHO descartavel, e o prazo e imposto pelo
sistema operacional: estourado, o filho recebe `kill()` e e recolhido com
`communicate()`/`wait()` antes de a funcao retornar. Nenhuma thread deste
processo sobrevive ao prazo, nenhuma conexao existe ainda — a conexao upstream
usa `hostaddr` com os enderecos validados e nao resolve nome (D-089) — e o
chamador recebe uma falha fechada de destino.

O filho e isolado do segredo do processo:

- `python -I -S`: sem `PYTHON*` do ambiente, sem `site`, sem diretorio do
  script no `sys.path`;
- ambiente reduzido ao minimo que o resolver do sistema exige (`SYSTEMROOT` no
  Windows, nada no POSIX): chave-mestra, token administrativo, DSN e chave HMAC
  nunca chegam ao filho;
- host e porta viajam por `stdin`, nunca por `argv`, que e visivel na lista de
  processos; o resultado volta por `stdout` como JSON de tamanho limitado;
- `stderr` e descartado: nenhum traceback do filho chega a log ou resposta; o
  `stdin`/`stdout` do MCP nao sao herdados, porque os tres fluxos do filho sao
  pipes proprios.

O numero de filhos simultaneos e limitado; sem vaga, a resolucao falha fechada
em vez de enfileirar trabalho sem teto.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from typing import Final

from maskgw.datasource.destination import DestinationValidationError

#: Prazo total, em segundos, de uma resolucao. Nao ha variavel de ambiente: a
#: Etapa 4 nao introduz settings novos (D-092).
DNS_TIMEOUT_SECONDS: Final = 5.0

#: Resolucoes simultaneas no processo. Os candidatos ja sao limitados pelo
#: registry (D-089: 2 globais) e a revalidacao do store roda sob a secao
#: critica do coordenador; a folga cobre startup e migracao.
MAX_CONCURRENT_RESOLUTIONS: Final = 4

#: Teto da resposta do filho e do numero de enderecos aceitos.
MAX_OUTPUT_BYTES: Final = 16 * 1024
MAX_ADDRESSES: Final = 64

#: Teto da entrada lida pelo filho (host validado de ate 253 caracteres).
_MAX_INPUT_BYTES: Final = 1024

#: Codigo fixo do filho. Nao e montado com dado algum: host e porta chegam por
#: `stdin`. Qualquer falha termina com codigo diferente de zero e sem saida.
_CHILD_CODE: Final = (
    "import json, socket, sys\n"
    "try:\n"
    f"    host, port = json.loads(sys.stdin.read({_MAX_INPUT_BYTES}))\n"
    "    if not isinstance(host, str) or type(port) is not int:\n"
    "        raise ValueError\n"
    "    found = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)\n"
    "    addresses = sorted({item[4][0] for item in found})\n"
    "    if not all(isinstance(item, str) for item in addresses):\n"
    "        raise ValueError\n"
    "except Exception:\n"
    "    sys.exit(3)\n"
    "sys.stdout.write(json.dumps(addresses))\n"
)

_SLOTS: Final = threading.BoundedSemaphore(MAX_CONCURRENT_RESOLUTIONS)


class DnsResolutionError(DestinationValidationError):
    """Resolucao recusada, falha ou fora do prazo. Mensagem fixa, sem host."""

    def __init__(self) -> None:
        super().__init__("destino nao resolvido")


def _child_environment() -> dict[str, str]:
    """Somente o que o resolver do sistema precisa; nenhum segredo."""
    if sys.platform != "win32":
        return {}
    root = os.environ.get("SYSTEMROOT")
    return {} if root is None else {"SYSTEMROOT": root}


def _run_child(host: str, port: int, *, timeout: float) -> bytes | None:
    """Executa o filho e o recolhe SEMPRE antes de retornar.

    Devolve a saida de um filho que terminou com sucesso, ou `None`. No prazo
    estourado, `kill()` e seguido de `communicate()`, que espera o termino e
    junta as threads de leitura de pipe do proprio `subprocess` no Windows;
    nenhuma delas sobrevive a esta funcao.
    """
    executable = sys.executable
    if not executable:
        return None
    payload = json.dumps([host, port]).encode("ascii")
    try:
        process = subprocess.Popen(  # noqa: S603 - executavel e codigo fixos, sem shell
            [executable, "-I", "-S", "-c", _CHILD_CODE],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=_child_environment(),
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, ValueError):
        return None
    try:
        try:
            output, _ = process.communicate(payload, timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return None
    finally:
        # Qualquer saida anormal — inclusive `KeyboardInterrupt` — ainda mata
        # e recolhe o filho antes de propagar.
        if process.poll() is None:
            process.kill()
            process.wait()
    if process.returncode != 0 or len(output) > MAX_OUTPUT_BYTES:
        return None
    return output


def _parse(output: bytes) -> tuple[str, ...] | None:
    try:
        value = json.loads(output.decode("ascii"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(value, list) or not 0 < len(value) <= MAX_ADDRESSES:
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    return tuple(value)


def bounded_system_resolver(host: str, port: int) -> tuple[str, ...]:
    """Resolver do sistema com prazo total de `DNS_TIMEOUT_SECONDS`.

    Levanta somente `DnsResolutionError`, sem cadeia de excecao e sem citar o
    host. A validacao dos enderecos (loopback, metadata, allowlist, pinning)
    continua em `resolve_destination`.
    """
    return resolve_with_timeout(host, port, timeout=DNS_TIMEOUT_SECONDS)


def resolve_with_timeout(host: str, port: int, *, timeout: float) -> tuple[str, ...]:
    """Mesmo mecanismo, com prazo explicito — usado pelos testes de prazo."""
    if not _SLOTS.acquire(blocking=False):
        raise DnsResolutionError
    try:
        output = _run_child(host, port, timeout=timeout)
    finally:
        _SLOTS.release()
    addresses = None if output is None else _parse(output)
    if addresses is None:
        raise DnsResolutionError
    return addresses


__all__ = [
    "DNS_TIMEOUT_SECONDS",
    "MAX_ADDRESSES",
    "MAX_CONCURRENT_RESOLUTIONS",
    "MAX_OUTPUT_BYTES",
    "DnsResolutionError",
    "bounded_system_resolver",
    "resolve_with_timeout",
]
