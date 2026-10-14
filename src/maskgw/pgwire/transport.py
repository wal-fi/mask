"""Transporte do startup PGWire sobre um socket JA aceito (D-110, lote 2).

O socket pertence ao CHAMADOR: este modulo nao o fecha, nao cria thread e nao
o substitui. Ajusta apenas o timeout de cada espera (fatias finitas).

Duas camadas, uma unica thread por conexao:

- `RawChannel`: `recv`/`send` em fatias de no maximo `poll`. Antes de cada
  fatia confere o pedido de parada e o `Deadline` ABSOLUTO; bytes parciais
  nunca renovam o prazo. Envio por `send` com offset: um timeout apenas
  continua do offset, sem `sendall` (que poderia reenviar bytes ja aceitos).
- `TlsChannel`: TLS via `SSLObject` + `MemoryBIO` sobre o MESMO socket raw
  (D-110). Sem `wrap_socket`: nada destaca o fd, e um futuro `stop` nunca
  precisa tocar um objeto SSL que outra thread usa. A saida cifrada e drenada
  em blocos de no maximo `chunk_bytes`; a entrada so e alimentada quando o
  `SSLObject` pede leitura, tambem em blocos limitados. O handshake e limitado
  em voltas e bytes, alem do prazo.

Falhas de transporte sao `TransportError` com uma categoria interna fechada,
levantadas fora de `except` (D-017); nada delas vai para o cliente.
"""

from __future__ import annotations

import contextlib
import socket
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NoReturn

_TLS_WRITE_BLOCK: Final = 16 * 1024


class TransportFailure(StrEnum):
    EOF = "eof"
    TIMEOUT = "timeout"
    STOPPED = "stopped"
    IO = "io"
    TLS = "tls"
    LIMIT = "limit"


class TransportError(Exception):
    """Falha de transporte: so a categoria interna."""

    def __init__(self, kind: TransportFailure) -> None:
        super().__init__(kind.value)
        self.kind = kind


def _fail(kind: TransportFailure) -> NoReturn:
    raise TransportError(kind)


@dataclass(frozen=True, slots=True)
class TransportLimits:
    """Limites do transporte (D-110): defaults delegados, internos.

    - `poll_ms`: fatia maxima de espera (confere parada e prazo);
    - `chunk_bytes`: maior bloco lido ou enviado de uma vez no socket;
    - `tls_handshake_rounds` / `tls_handshake_bytes`: teto do handshake TLS;
    - `linger_ms` / `linger_bytes`: teto do encerramento gracioso depois de um
      erro final (ver `RawChannel.linger`).
    """

    poll_ms: int = 250
    chunk_bytes: int = 16 * 1024
    tls_handshake_rounds: int = 64
    tls_handshake_bytes: int = 256 * 1024
    linger_ms: int = 1_000
    linger_bytes: int = 64 * 1024

    def __post_init__(self) -> None:
        for value in (
            self.poll_ms,
            self.chunk_bytes,
            self.tls_handshake_rounds,
            self.tls_handshake_bytes,
            self.linger_ms,
            self.linger_bytes,
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                msg = "limite do transporte pgwire invalido"
                raise ValueError(msg)


class Deadline:
    """Prazo absoluto, fixado na criacao. Nada o renova."""

    __slots__ = ("_clock", "_end")

    def __init__(self, seconds: float, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._end = clock() + seconds

    def remaining(self) -> float:
        return self._end - self._clock()

    def __repr__(self) -> str:
        return "Deadline(<absoluto>)"


class RawChannel:
    """`recv`/`send` limitados sobre o socket do chamador."""

    __slots__ = ("_limits", "_sock", "_stop")

    def __init__(
        self,
        sock: socket.socket,
        *,
        stop: Callable[[], bool],
        limits: TransportLimits,
    ) -> None:
        self._sock = sock
        self._stop = stop
        self._limits = limits

    @property
    def limits(self) -> TransportLimits:
        return self._limits

    def check(self, deadline: Deadline) -> float:
        """Parada e prazo; devolve o tempo restante. Usado tambem pelo TLS em
        passos que se resolvem so com dados em buffer, sem tocar o socket."""
        if self._stop():
            _fail(TransportFailure.STOPPED)
        remaining = deadline.remaining()
        if remaining <= 0:
            _fail(TransportFailure.TIMEOUT)
        return remaining

    def _slice(self, deadline: Deadline) -> float:
        return min(self.check(deadline), self._limits.poll_ms / 1000)

    def recv_some(self, maximum: int, deadline: Deadline) -> bytes:
        """Ate `maximum` bytes (no maximo `chunk_bytes`); EOF e falha."""
        size = min(maximum, self._limits.chunk_bytes)
        while True:
            wait = self._slice(deadline)
            failure: TransportFailure | None = None
            data = b""
            try:
                self._sock.settimeout(wait)
                data = self._sock.recv(size)
            except TimeoutError:
                continue
            except OSError:
                failure = TransportFailure.IO
            if failure is not None:
                _fail(failure)
            if not data:
                _fail(TransportFailure.EOF)
            return data

    def recv_exact(self, size: int, deadline: Deadline) -> bytes:
        buffer = bytearray()
        while len(buffer) < size:
            buffer += self.recv_some(size - len(buffer), deadline)
        return bytes(buffer)

    def send_all(self, data: bytes, deadline: Deadline) -> None:
        """Envia tudo com offset; timeout continua do offset, nunca reenvia."""
        view = memoryview(data)
        offset = 0
        while offset < len(view):
            wait = self._slice(deadline)
            failure: TransportFailure | None = None
            sent = 0
            try:
                self._sock.settimeout(wait)
                sent = self._sock.send(view[offset : offset + self._limits.chunk_bytes])
            except TimeoutError:
                continue
            except OSError:
                failure = TransportFailure.IO
            # Zero sem excecao nao progride: falha fechada imediata, nunca um
            # laco de CPU ate o prazo.
            if failure is None and (not isinstance(sent, int) or sent <= 0):
                failure = TransportFailure.IO
            if failure is not None:
                _fail(failure)
            offset += sent

    def linger(self) -> None:
        """Encerramento gracioso limitado depois de um erro final.

        Fechar um socket com entrada nao lida faz a pilha TCP enviar RST, que
        pode descartar no cliente o `ErrorResponse` ja enviado (medido no
        Windows). Aqui: `shutdown(SHUT_WR)` (o FIN segue o erro) e descarte,
        SEM interpretar, da entrada ate EOF, no maximo `linger_bytes` ou
        `linger_ms`, conferindo a parada. Nunca falha; nao fecha o socket.
        """
        with contextlib.suppress(OSError):
            self._sock.shutdown(socket.SHUT_WR)
        deadline = Deadline(self._limits.linger_ms / 1000)
        discarded = 0
        while discarded < self._limits.linger_bytes:
            try:
                data = self.recv_some(self._limits.linger_bytes - discarded, deadline)
            except TransportError:
                return
            discarded += len(data)


class TlsChannel:
    """TLS de servidor por `SSLObject`/`MemoryBIO` sobre o `RawChannel`.

    Usado por UMA thread. O socket raw nunca muda; o objeto SSL nunca e
    tocado por outra thread (a parada e so um sinal conferido a cada fatia).
    """

    __slots__ = ("_incoming", "_outgoing", "_raw", "_ssl")

    def __init__(self, raw: RawChannel, context: ssl.SSLContext) -> None:
        self._raw = raw
        self._incoming = ssl.MemoryBIO()
        self._outgoing = ssl.MemoryBIO()
        created: ssl.SSLObject | None = None
        try:
            created = context.wrap_bio(self._incoming, self._outgoing, server_side=True)
        except (ssl.SSLError, ValueError):
            created = None
        if created is None:
            _fail(TransportFailure.TLS)
        self._ssl = created

    def _flush(self, deadline: Deadline) -> int:
        """Drena a saida cifrada em blocos limitados; devolve bytes enviados."""
        sent = 0
        while self._outgoing.pending:
            block = self._outgoing.read(self._raw.limits.chunk_bytes)
            self._raw.send_all(block, deadline)
            sent += len(block)
        return sent

    def _feed(self, deadline: Deadline) -> int:
        data = self._raw.recv_some(self._raw.limits.chunk_bytes, deadline)
        self._incoming.write(data)
        return len(data)

    def handshake(self, deadline: Deadline) -> None:
        limits = self._raw.limits
        transferred = 0
        for _ in range(limits.tls_handshake_rounds):
            self._raw.check(deadline)
            want_read = False
            failure: TransportFailure | None = None
            try:
                self._ssl.do_handshake()
            except ssl.SSLWantReadError:
                want_read = True
            except (ssl.SSLError, ValueError):
                failure = TransportFailure.TLS
            if failure is not None:
                _fail(failure)
            transferred += self._flush(deadline)
            # O teto vale tambem para a saida do passo que CONCLUI o handshake.
            if transferred > limits.tls_handshake_bytes:
                _fail(TransportFailure.LIMIT)
            if not want_read:
                return
            transferred += self._feed(deadline)
            if transferred > limits.tls_handshake_bytes:
                _fail(TransportFailure.LIMIT)
        _fail(TransportFailure.LIMIT)

    def recv_exact(self, size: int, deadline: Deadline) -> bytes:
        buffer = bytearray()
        while len(buffer) < size:
            # Mesmo com texto ja decifrado em buffer, parada e prazo valem.
            self._raw.check(deadline)
            piece = b""
            outcome = "data"
            try:
                piece = self._ssl.read(min(size - len(buffer), self._raw.limits.chunk_bytes))
            except ssl.SSLWantReadError:
                outcome = "want_read"
            except ssl.SSLZeroReturnError:
                outcome = "eof"
            except (ssl.SSLError, ValueError):
                outcome = "tls"
            if outcome == "eof":
                _fail(TransportFailure.EOF)
            if outcome == "tls":
                _fail(TransportFailure.TLS)
            if outcome == "want_read":
                self._flush(deadline)
                self._feed(deadline)
                continue
            if not piece:
                _fail(TransportFailure.EOF)
            buffer += piece
        return bytes(buffer)

    def send_all(self, data: bytes, deadline: Deadline) -> None:
        view = memoryview(data)
        offset = 0
        while offset < len(view):
            self._raw.check(deadline)
            accepted = 0
            failed = False
            try:
                accepted = self._ssl.write(view[offset : offset + _TLS_WRITE_BLOCK])
            except (ssl.SSLError, ValueError):
                failed = True
            # `write` devolve quanto aceitou: avanca so isso. Zero sem excecao
            # seria laco sem progresso, e e tratado como falha.
            if failed or not isinstance(accepted, int) or accepted <= 0:
                _fail(TransportFailure.TLS)
            offset += accepted
            # Drena a cada escrita: a saida cifrada pendente nunca passa de um
            # bloco de texto mais o overhead dos registros TLS.
            self._flush(deadline)


__all__ = [
    "Deadline",
    "RawChannel",
    "TlsChannel",
    "TransportError",
    "TransportFailure",
    "TransportLimits",
]
