"""Suporte de TESTE da fronteira PGWire (D-109): certificados e harness.

Nada aqui e produto. O `SSLContext`, os sockets e a thread existem SO para
provar a interoperabilidade das pecas puras (`framing`, `credential`, `scram`,
`channel_binding`) com o libpq real. O harness:

- escuta so em `127.0.0.1`, porta efemera, uma unica conexao;
- nao executa SQL e nao conecta a nenhum upstream: depois do
  `AuthenticationOk` envia o minimo que o libpq exige para concluir o startup
  e so aceita `Terminate`;
- registra o resultado em categorias fechadas e fecha tudo o que abriu.
"""

from __future__ import annotations

import contextlib
import datetime
import ipaddress
import os
import socket
import ssl
import struct
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa
from cryptography.hazmat.primitives.asymmetric.types import CertificateIssuerPrivateKeyTypes
from cryptography.x509.oid import NameOID

from maskgw.pgwire import framing
from maskgw.pgwire.channel_binding import tls_server_end_point
from maskgw.pgwire.credential import PrincipalCredential
from maskgw.pgwire.errors import PgwireErrorCategory, PgwireStartupError, error_response
from maskgw.pgwire.scram import ScramServerExchange

IO_TIMEOUT = 5.0
#: Espera normal pelo worker no `__exit__` antes de fecha-lo a forca.
EXIT_GRACE = IO_TIMEOUT
#: Teto do watchdog independente: sem fim do worker ate aqui, aborta o processo.
WATCHDOG_DEADLINE = 60.0
WATCHDOG_EXIT_CODE = 97


def _abort_hung_harness() -> None:
    sys.stderr.write("pgwire harness: worker nao terminou; abortando o processo\n")
    sys.stderr.flush()
    os._exit(WATCHDOG_EXIT_CODE)


def _wait_dead_under_watchdog(thread: threading.Thread) -> None:
    """Espera SEM prazo ate `thread` nao estar viva; o watchdog aborta se nao vier.

    Nao usa `thread.join`: o fim fisico e provado por `is_alive()` mesmo quando
    o `join` falhou ou foi substituido. Thread nunca iniciada retorna logo.
    """
    if not thread.is_alive():
        return
    watchdog = threading.Timer(WATCHDOG_DEADLINE, _abort_hung_harness)
    watchdog.name = "pgwire-harness-watchdog"
    watchdog.start()
    try:
        while thread.is_alive():
            time.sleep(0.01)
    finally:
        watchdog.cancel()
        watchdog.join()


# ---- certificados de teste ---------------------------------------------------


def _key(kind: str) -> CertificateIssuerPrivateKeyTypes:
    if kind.startswith("rsa"):
        return rsa.generate_private_key(public_exponent=65537, key_size=2048)
    if kind.startswith("ecdsa-p384"):
        return ec.generate_private_key(ec.SECP384R1())
    if kind.startswith("ecdsa"):
        return ec.generate_private_key(ec.SECP256R1())
    if kind == "ed25519":
        return ed25519.Ed25519PrivateKey.generate()
    if kind == "ed448":
        return ed448.Ed448PrivateKey.generate()
    raise AssertionError(kind)


def _hash(kind: str) -> hashes.SHA224 | hashes.SHA256 | hashes.SHA384 | hashes.SHA512 | None:
    if kind in ("ed25519", "ed448"):
        return None
    name = kind.rsplit("-", 1)[1]
    if name == "sha384":
        return hashes.SHA384()
    if name == "sha512":
        return hashes.SHA512()
    return hashes.SHA256()


@dataclass
class PgCertificate:
    der: bytes
    cert_path: Path
    key_path: Path


def make_certificate(
    directory: Path,
    kind: str = "rsa-sha256",
    *,
    issuer: tuple[x509.Certificate, CertificateIssuerPrivateKeyTypes] | None = None,
    common_name: str = "gateway.test",
) -> tuple[PgCertificate, x509.Certificate, CertificateIssuerPrivateKeyTypes]:
    """Gera um certificado (autoassinado ou emitido por `issuer`) em `directory`.

    `kind`: `rsa-sha256`, `rsa-sha512`, `ecdsa-sha256`, `ecdsa-p384-sha384`,
    `ed25519`, `ed448`. O SAN cobre `127.0.0.1` e `localhost`.
    """
    key = _key(kind)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.UTC)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
    )
    if issuer is None:
        builder = builder.issuer_name(subject).add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
        signer = key
    else:
        issuer_cert, signer = issuer
        builder = builder.issuer_name(issuer_cert.subject).add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        )
    builder = builder.add_extension(
        x509.SubjectAlternativeName(
            [x509.IPAddress(ipaddress.ip_address("127.0.0.1")), x509.DNSName("localhost")]
        ),
        critical=False,
    )
    certificate = builder.sign(signer, _hash(kind) if issuer is None else hashes.SHA256())
    stem = f"{kind}-{certificate.serial_number:x}"
    cert_path, key_path = directory / f"{stem}.crt", directory / f"{stem}.key"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    write_private_key(
        key_path,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    der = certificate.public_bytes(serialization.Encoding.DER)
    return PgCertificate(der, cert_path, key_path), certificate, key


#: Modo da chave de teste: o mesmo que o produto exige no POSIX (D-110).
PRIVATE_KEY_MODE = 0o600


def write_private_key(path: Path, data: bytes) -> None:
    """Grava a chave de TESTE ja com `0600` no POSIX (o umask so remove bits).

    Criacao exclusiva com o modo privado desde o `open`, e `chmod` explicito
    depois. No Windows o modo POSIX nao se aplica (e as ACLs nao sao tratadas).
    O produto nao e relaxado: e o gerador que passa a cumprir o contrato.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, PRIVATE_KEY_MODE)
    try:
        os.write(descriptor, data)
    finally:
        os.close(descriptor)
    if os.name == "posix":
        os.chmod(path, PRIVATE_KEY_MODE)


def server_context(cert: PgCertificate) -> ssl.SSLContext:
    """Contexto TLS do HARNESS (nao e produto): TLS 1.2+, sem compressao."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.options |= ssl.OP_NO_COMPRESSION
    context.load_cert_chain(cert.cert_path, cert.key_path)
    return context


def presented_leaf(context: ssl.SSLContext) -> bytes:
    """O leaf que `context` EFETIVAMENTE apresenta, por handshake em memoria."""
    client = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client.check_hostname = False
    client.verify_mode = ssl.CERT_NONE
    s_in, s_out, c_in, c_out = ssl.MemoryBIO(), ssl.MemoryBIO(), ssl.MemoryBIO(), ssl.MemoryBIO()
    server_side = context.wrap_bio(s_in, s_out, server_side=True)
    client_side = client.wrap_bio(c_in, c_out, server_side=False)
    done = {"client": False, "server": False}
    for _ in range(50):
        for name, side in (("client", client_side), ("server", server_side)):
            if not done[name]:
                with contextlib.suppress(ssl.SSLWantReadError):
                    side.do_handshake()
                    done[name] = True
        s_in.write(c_out.read())
        c_in.write(s_out.read())
        if all(done.values()):
            break
    leaf = client_side.getpeercert(binary_form=True)
    assert leaf is not None
    return leaf


# ---- harness ----------------------------------------------------------------


@dataclass
class Outcome:
    authenticated: bool = False
    category: str | None = None
    mechanism: str | None = None
    gs2_flag: str | None = None
    tls_used: bool = False
    sent_error: bytes | None = None
    after_ready: list[bytes] = field(default_factory=list)
    unexpected: str | None = None


def _exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise EOFError
        data += chunk
    return bytes(data)


def _typed(sock: socket.socket, expected_type: bytes) -> bytes:
    size = framing.message_length(_exact(sock, 5), expected_type=expected_type)
    return _exact(sock, size)


def _frame(kind: bytes, body: bytes) -> bytes:
    return kind + struct.pack("!I", len(body) + 4) + body


#: O minimo pos-autenticacao que o libpq exige para concluir o startup. Nao e
#: sessao: nenhuma consulta e aceita depois disto.
_POST_AUTH = b"".join(
    [
        *(
            _frame(b"S", name + b"\x00" + value + b"\x00")
            for name, value in (
                (b"server_version", b"16.0"),
                (b"client_encoding", b"UTF8"),
                (b"standard_conforming_strings", b"on"),
                (b"integer_datetimes", b"on"),
                (b"DateStyle", b"ISO, MDY"),
            )
        ),
        _frame(b"K", struct.pack("!II", 1, 2)),
        _frame(b"Z", b"I"),
    ]
)


class LoopbackHarness:
    """Servidor de uma conexao, so loopback, para o libpq de teste."""

    def __init__(
        self,
        credential: PrincipalCredential,
        *,
        context: ssl.SSLContext | None = None,
        offer_plus: bool = True,
        aliases: frozenset[str] = frozenset({"crm"}),
    ) -> None:
        self.credential = credential
        self.context = context
        self.channel_binding = None
        if context is not None and offer_plus:
            self.channel_binding = tls_server_end_point(presented_leaf(context))
        self.aliases = aliases
        self.outcome = Outcome()
        self.client_error = ""
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.listener.settimeout(IO_TIMEOUT * 2)
        self.port = self.listener.getsockname()[1]
        # Worker NAO daemon: nada fica escondido; o fim e provado no __exit__.
        self.thread = threading.Thread(target=self._serve, name="pgwire-harness", daemon=False)
        self.sockets: list[socket.socket] = []
        self._sockets_lock = threading.Lock()

    def _track(self, sock: socket.socket) -> None:
        with self._sockets_lock:
            self.sockets.append(sock)

    def _close_owned(self) -> None:
        """Fecha listener e sockets aceitos. Idempotente; seguro de qualquer thread."""
        with self._sockets_lock:
            owned = [*reversed(self.sockets), self.listener]
        for item in owned:
            with contextlib.suppress(OSError):
                item.close()

    def _reap(self) -> None:
        """Fecha tudo o que o harness possui e prova o fim fisico do worker.

        Vale para worker nunca iniciado, iniciado por um `start` que depois
        falhou, ou em qualquer estado no `__exit__`. Retorna so com o worker
        morto e listener/sockets fechados; um hang aborta pelo watchdog.
        """
        self._close_owned()
        _wait_dead_under_watchdog(self.thread)
        self._close_owned()  # o que o worker tenha aberto ate morrer

    def __enter__(self) -> LoopbackHarness:
        # O harness ja e dono do listener e, se o `start` chegou a iniciar o
        # worker antes de falhar, tambem dele: recolhe tudo antes de propagar.
        try:
            self.thread.start()
        except BaseException:
            self._reap()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:
        """Prova o fim fisico do worker e fecha tudo, sem mascarar falha anterior.

        Espera o worker terminar sozinho por ate `EXIT_GRACE`. Depois, falhe ou
        nao essa espera, `_reap` fecha os sockets e prova a morte do worker por
        `is_alive()` sob watchdog. So entao uma falha da espera e reportada:
        levantada se nao havia falha anterior, ou anotada na anterior, que
        continua sendo a propagada.
        """
        wait_error: BaseException | None = None
        try:
            self.thread.join(EXIT_GRACE)
        except RuntimeError as error:
            if self.thread.ident is not None:  # nunca iniciado nao e falha
                wait_error = error
        except BaseException as error:
            wait_error = error
        self._reap()
        if wait_error is None:
            return
        if exc is None:
            raise wait_error
        exc.add_note(f"limpeza do harness tambem falhou: {type(wait_error).__name__}")

    def _serve(self) -> None:
        try:
            self._serve_one()
        except Exception as error:  # registrado e verificado pelos testes
            self.outcome.unexpected = type(error).__name__
        finally:
            self._close_owned()

    def _serve_one(self) -> None:
        try:
            conn, _ = self.listener.accept()
        except OSError:
            self.outcome.unexpected = "accept"
            return
        self._track(conn)
        conn.settimeout(IO_TIMEOUT)
        try:
            self._startup(conn)
        except PgwireStartupError as error:
            self.outcome.category = error.category.value
            self.outcome.sent_error = error_response(error.category)
            # O socket mais recente: o TLS, se o handshake ocorreu.
            with contextlib.suppress(OSError):
                self.sockets[-1].sendall(self.outcome.sent_error)
        except (OSError, EOFError) as error:
            self.outcome.unexpected = type(error).__name__

    def _read_initial(self, sock: socket.socket) -> tuple[framing.InitialKind, bytes]:
        length = framing.initial_length(_exact(sock, 4))
        body = _exact(sock, length - 4)
        return framing.classify_initial(body), body

    def _startup(self, conn: socket.socket) -> None:
        sock: socket.socket = conn
        kind, body = self._read_initial(sock)
        if kind is framing.InitialKind.SSL_REQUEST:
            if self.context is None:
                sock.sendall(b"N")
            else:
                sock.sendall(b"S")
                sock = self.context.wrap_socket(conn, server_side=True)
                self._track(sock)
                self.outcome.tls_used = True
            kind, body = self._read_initial(sock)
            if kind is not framing.InitialKind.STARTUP:
                raise PgwireStartupError(PgwireErrorCategory.PROTOCOL_VIOLATION)
        startup = framing.parse_startup(body)
        binding = self.channel_binding if self.outcome.tls_used else None
        exchange = ScramServerExchange(
            self.credential.verifier_for(startup.user), channel_binding=binding
        )
        sock.sendall(framing.authentication_sasl(exchange.mechanisms))
        mechanism, first = framing.parse_sasl_initial(_typed(sock, b"p"))
        self.outcome.mechanism = mechanism
        self.outcome.gs2_flag = first.split(b",", 1)[0].decode("ascii", "replace")
        sock.sendall(framing.authentication_sasl_continue(exchange.client_first(mechanism, first)))
        accepted = framing.valid_alias(startup.database) and startup.database in self.aliases
        final = exchange.client_final(_typed(sock, b"p"), identity_accepted=accepted)
        sock.sendall(framing.authentication_sasl_final(final) + framing.authentication_ok())
        self.outcome.authenticated = True
        sock.sendall(_POST_AUTH)
        with contextlib.suppress(OSError, EOFError):
            while True:
                kind_byte = _exact(sock, 1)
                self.outcome.after_ready.append(kind_byte)
                (length,) = struct.unpack("!I", _exact(sock, 4))
                if kind_byte != b"X" or length != 4:
                    break
