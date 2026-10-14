"""Suporte de TESTE do driver PGWire (D-110, lote 2). Nada aqui e produto.

- `Peer`: o lado cliente numa thread NAO daemon, cujo fim fisico e provado
  (`_wait_dead_under_watchdog`, que aborta o processo se nao vier);
- `watchdog`: teto independente para a chamada do driver na thread do teste;
- builders de mensagens do cliente e um cliente SCRAM minimo de teste;
- `read_messages`: le as mensagens do servidor ate o fim da conexao.

Os sockets sao `socketpair` locais; nenhum bind, DNS ou upstream.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import re
import secrets
import socket
import struct
import threading
from collections.abc import Callable, Iterator
from typing import Any

from maskgw.pgwire.credential import PrincipalCredential, prepare_principal
from maskgw.pgwire.driver import DriverLimits, SessionResult, run_startup_session
from maskgw.pgwire.tls import ServerTls
from maskgw.pgwire.transport import Deadline, TransportLimits
from tests.pgwire_support import _abort_hung_harness, _wait_dead_under_watchdog

USER = "gwuser"
PROTOCOL_3_0 = 196608
SERVER_FIRST = re.compile(r"r=([\x21-\x2b\x2d-\x7e]+),s=([A-Za-z0-9+/]+={0,2}),i=(\d+)")
FAST = TransportLimits(poll_ms=20, linger_ms=300)


def new_principal() -> tuple[PrincipalCredential, str]:
    password = "senha-teste-" + secrets.token_urlsafe(12)
    return prepare_principal(USER, password), password


@contextlib.contextmanager
def watchdog(seconds: float) -> Iterator[None]:
    """Aborta o processo se o bloco nao terminar no prazo (hang nao e silencioso)."""
    timer = threading.Timer(seconds, _abort_hung_harness)
    timer.name = "pgwire-driver-watchdog"
    timer.start()
    try:
        yield
    finally:
        timer.cancel()
        timer.join()


class Peer:
    """Roda `target(sock)` numa thread nao daemon e prova o fim no `__exit__`."""

    def __init__(self, sock: socket.socket, target: Callable[[socket.socket], Any]) -> None:
        self.sock = sock
        self.result: Any = None
        self.error: BaseException | None = None
        self.thread = threading.Thread(target=self._run, args=(target,), name="pgwire-peer")

    def _run(self, target: Callable[[socket.socket], Any]) -> None:
        try:
            self.result = target(self.sock)
        except BaseException as error:  # registrado e conferido pelo teste
            self.error = error

    def __enter__(self) -> Peer:
        self.thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        # O peer termina sozinho (EOF do servidor) ou e destravado aqui.
        self.thread.join(5.0)
        if self.thread.is_alive():
            with contextlib.suppress(OSError):
                self.sock.shutdown(socket.SHUT_RDWR)
            with contextlib.suppress(OSError):
                self.sock.close()
        _wait_dead_under_watchdog(self.thread)
        with contextlib.suppress(OSError):
            self.sock.close()


def run_driver(  # noqa: PLR0913 - cada colaborador do driver e um parametro do teste
    server: socket.socket,
    principal: PrincipalCredential,
    *,
    tls: ServerTls | None = None,
    tls_required: bool = False,
    aliases: frozenset[str] = frozenset({"crm"}),
    reserve: Callable[[], bool] | None = None,
    startup_ms: int = 3_000,
    idle_ms: int = 3_000,
    transport: TransportLimits = FAST,
    stop: Callable[[], bool] = lambda: False,
    events: list[str] | None = None,
    deadline: Deadline | None = None,
    alias_hook: Callable[[], None] | None = None,
) -> SessionResult:
    log = events if events is not None else []

    def alias_accepted(alias: str) -> bool:
        log.append("alias")
        if alias_hook is not None:
            alias_hook()
        return alias in aliases

    def reserve_session() -> bool:
        log.append("reserve")
        return True if reserve is None else reserve()

    with watchdog(30.0):
        return run_startup_session(
            server,
            principal=principal,
            tls=tls,
            tls_required=tls_required,
            alias_accepted=alias_accepted,
            reserve_session=reserve_session,
            limits=DriverLimits(startup_ms, idle_ms, transport),
            stop=stop,
            # O dono cria o prazo no accept; os testes que nao o passam
            # simulam esse accept aqui mesmo.
            deadline=deadline if deadline is not None else Deadline(startup_ms / 1000),
        )


# ---- mensagens do cliente ----------------------------------------------------


def frame(kind: bytes, body: bytes) -> bytes:
    return kind + struct.pack("!I", len(body) + 4) + body


def ssl_request() -> bytes:
    return struct.pack("!II", 8, 80877103)


def startup(user: str = USER, database: str | None = "crm") -> bytes:
    pairs = [("user", user)] + ([("database", database)] if database is not None else [])
    payload = b"".join(k.encode() + b"\x00" + v.encode() + b"\x00" for k, v in pairs) + b"\x00"
    return struct.pack("!II", 8 + len(payload), PROTOCOL_3_0) + payload


def sasl_initial(mechanism: str, data: bytes) -> bytes:
    return frame(b"p", mechanism.encode() + b"\x00" + struct.pack("!i", len(data)) + data)


def terminate() -> bytes:
    return frame(b"X", b"")


def exact(sock: Any, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise EOFError
        data += chunk
    return bytes(data)


def read_message(sock: Any) -> tuple[bytes, bytes]:
    kind = exact(sock, 1)
    (length,) = struct.unpack("!I", exact(sock, 4))
    return kind, exact(sock, length - 4)


def read_messages(sock: Any) -> list[tuple[bytes, bytes]]:
    """Le mensagens do servidor ate EOF (ou erro de socket)."""
    messages: list[tuple[bytes, bytes]] = []
    with contextlib.suppress(EOFError, OSError):
        while True:
            messages.append(read_message(sock))
    return messages


class ScramClient:
    """Cliente SCRAM minimo de TESTE (sem SASLprep: senhas ASCII)."""

    def __init__(
        self,
        password: str,
        *,
        mechanism: str = "SCRAM-SHA-256",
        header: str = "n,,",
        binding: bytes = b"",
    ) -> None:
        self.password = password
        self.mechanism = mechanism
        self.header = header
        self.binding = binding
        self.bare = "n=,r=" + base64.b64encode(secrets.token_bytes(18)).decode()
        self.expected_final = b""

    def first(self) -> bytes:
        return sasl_initial(self.mechanism, (self.header + self.bare).encode())

    def final(self, server_first: bytes, *, tamper: bool = False) -> bytes:
        match = SERVER_FIRST.fullmatch(server_first.decode("ascii"))
        assert match is not None
        nonce, salt, iterations = match.group(1), match.group(2), int(match.group(3))
        salted = hashlib.pbkdf2_hmac(
            "sha256", self.password.encode(), base64.b64decode(salt), iterations
        )
        client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
        stored = hashlib.sha256(client_key).digest()
        server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
        cbind = base64.b64encode(self.header.encode() + self.binding).decode()
        without = f"c={cbind},r={nonce}"
        auth = f"{self.bare},{server_first.decode()},{without}".encode()
        signature = hmac.new(stored, auth, hashlib.sha256).digest()
        proof = bytearray(a ^ b for a, b in zip(client_key, signature, strict=True))
        if tamper:
            proof[0] ^= 1
        self.expected_final = b"v=" + base64.b64encode(
            hmac.new(server_key, auth, hashlib.sha256).digest()
        )
        return frame(b"p", f"{without},p={base64.b64encode(bytes(proof)).decode()}".encode())


def authenticate(
    sock: Any,
    client: ScramClient,
    *,
    user: str = USER,
    database: str | None = "crm",
    tamper: bool = False,
) -> list[tuple[bytes, bytes]]:
    """Startup + SCRAM pelo socket ja negociado; devolve as mensagens recebidas."""
    sock.sendall(startup(user, database))
    kind, body = read_message(sock)
    assert kind == b"R" and body[:4] == struct.pack("!I", 10)
    sock.sendall(client.first())
    kind, body = read_message(sock)
    if kind != b"R":
        return [(kind, body), *read_messages(sock)]
    sock.sendall(client.final(body[4:], tamper=tamper))
    return read_until_ready(sock)


def read_until_ready(sock: Any) -> list[tuple[bytes, bytes]]:
    messages: list[tuple[bytes, bytes]] = []
    with contextlib.suppress(EOFError, OSError):
        while True:
            message = read_message(sock)
            messages.append(message)
            if message[0] in (b"Z", b"E"):
                break
    return messages
