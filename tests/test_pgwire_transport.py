"""Fase 9, Etapa 7 (D-110, lote 2): transporte limitado sobre socketpair.

Prova:

- prazo ABSOLUTO: peer que goteja bytes nao o renova; parada atende rapido;
- envio com offset: peer que nao le leva a TIMEOUT sem reenviar bytes (o que
  chegou e prefixo exato do payload); blocos no socket <= `chunk_bytes`;
- EOF e erro de IO viram categorias fechadas;
- TLS por `SSLObject`/MemoryBIO sobre o MESMO socket raw (fd nunca muda):
  roundtrip, lixo, ClientHello gotejado, limites de voltas/bytes, EOF no meio,
  falha ao criar o objeto TLS; saida cifrada drenada em blocos limitados.
"""

from __future__ import annotations

import contextlib
import os
import socket
import ssl
import threading
import time
from collections.abc import Callable
from typing import Any

import pytest

from maskgw.pgwire.tls import prepare_server_tls
from maskgw.pgwire.transport import (
    Deadline,
    RawChannel,
    TlsChannel,
    TransportError,
    TransportFailure,
    TransportLimits,
)
from tests.pgwire_driver_support import Peer, watchdog
from tests.pgwire_support import make_certificate

FAST = TransportLimits(poll_ms=20, chunk_bytes=4096)


class RecordingSocket:
    """Proxy de teste: registra o tamanho de cada `send`/`recv`."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.sent: list[int] = []
        self.received: list[int] = []

    def settimeout(self, value: float) -> None:
        self.sock.settimeout(value)

    def send(self, data: Any) -> int:
        sent = self.sock.send(data)
        self.sent.append(sent)
        return sent

    def recv(self, size: int) -> bytes:
        data = self.sock.recv(size)
        self.received.append(len(data))
        return data

    def shutdown(self, how: int) -> None:
        self.sock.shutdown(how)


@pytest.fixture
def pair():
    server, client = socket.socketpair()
    try:
        yield server, client
    finally:
        server.close()
        client.close()


def failure_of(call: Callable[..., object], *args: Any) -> TransportFailure:
    with pytest.raises(TransportError) as info:
        call(*args)
    assert info.value.__cause__ is None
    assert info.value.__context__ is None
    return info.value.kind


def channel(
    sock: Any, *, stop: Callable[[], bool] = lambda: False, limits: TransportLimits = FAST
) -> RawChannel:
    return RawChannel(sock, stop=stop, limits=limits)


class TestDeadline:
    def test_absoluto_e_decrescente(self):
        now = [100.0]
        deadline = Deadline(2.0, clock=lambda: now[0])
        assert deadline.remaining() == 2.0
        now[0] = 101.5
        assert deadline.remaining() == 0.5
        now[0] = 103.0
        assert deadline.remaining() < 0


class TestRaw:
    def test_gotejamento_nao_renova_o_prazo(self, pair):
        server, client = pair
        stop_drip = threading.Event()

        def drip(sock):
            while not stop_drip.is_set():
                with contextlib.suppress(OSError):
                    sock.send(b"x")
                time.sleep(0.03)

        with Peer(client, drip):
            started = time.monotonic()
            with watchdog(10):
                kind = failure_of(channel(server).recv_exact, 10_000, Deadline(0.3))
            elapsed = time.monotonic() - started
            stop_drip.set()
        assert kind is TransportFailure.TIMEOUT
        assert 0.25 <= elapsed < 1.5

    def test_parada_atende_dentro_de_uma_fatia(self, pair):
        server, _client = pair
        stopped = threading.Event()
        timer = threading.Timer(0.1, stopped.set)
        timer.start()
        try:
            started = time.monotonic()
            with watchdog(10):
                kind = failure_of(channel(server, stop=stopped.is_set).recv_exact, 1, Deadline(5))
            elapsed = time.monotonic() - started
        finally:
            timer.cancel()
            timer.join()
        assert kind is TransportFailure.STOPPED
        assert elapsed < 1.0

    def test_eof(self, pair):
        server, client = pair
        client.sendall(b"ab")
        client.close()
        assert failure_of(channel(server).recv_exact, 3, Deadline(2)) is TransportFailure.EOF

    def test_erro_de_io(self):
        sock = socket.socket()
        sock.close()
        assert failure_of(channel(sock).recv_exact, 1, Deadline(1)) is TransportFailure.IO
        assert failure_of(channel(sock).send_all, b"x", Deadline(1)) is TransportFailure.IO

    def test_peer_que_nao_le_sem_reenvio(self, pair):
        server, client = pair
        payload = os.urandom(8 * 1024 * 1024)
        with watchdog(20):
            kind = failure_of(channel(server).send_all, payload, Deadline(0.3))
        assert kind is TransportFailure.TIMEOUT
        server.shutdown(socket.SHUT_WR)
        received = bytearray()
        client.settimeout(5)
        while chunk := client.recv(65536):
            received += chunk
        assert 0 < len(received) < len(payload)
        assert bytes(received) == payload[: len(received)]  # prefixo exato, sem repeticao

    def test_send_que_devolve_zero_falha_na_hora(self):
        class ZeroSend:
            def __init__(self) -> None:
                self.sends = 0

            def settimeout(self, _value: float) -> None:
                pass

            def send(self, _data: Any) -> int:
                self.sends += 1
                return 0

        fake = ZeroSend()
        started = time.monotonic()
        kind = failure_of(channel(fake).send_all, b"abc", Deadline(30))
        assert kind is TransportFailure.IO
        assert fake.sends == 1  # nenhum laco de CPU ate o prazo
        assert time.monotonic() - started < 1.0

    def test_envio_parcial_continua_do_offset(self):
        class OneByte:
            def __init__(self) -> None:
                self.data = bytearray()
                self.sends = 0

            def settimeout(self, _value: float) -> None:
                pass

            def send(self, data: Any) -> int:
                self.sends += 1
                self.data += bytes(data[:1])
                return 1

        fake = OneByte()
        channel(fake).send_all(b"abcdef", Deadline(5))
        assert bytes(fake.data) == b"abcdef"  # cada byte uma vez, na ordem
        assert fake.sends == 6

    def test_blocos_limitados_no_socket(self, pair):
        server, client = pair
        recording = RecordingSocket(server)
        payload = os.urandom(100_000)

        def drain(sock):
            data = bytearray()
            while len(data) < len(payload):
                data += sock.recv(65536)
            return bytes(data)

        with Peer(client, drain) as peer:
            channel(recording).send_all(payload, Deadline(5))
        assert peer.result == payload
        assert max(recording.sent) <= FAST.chunk_bytes

    def test_linger_envia_fin_depois_dos_dados(self, pair):
        server, client = pair
        raw = channel(server)
        raw.send_all(b"erro-final", Deadline(2))
        client.sendall(b"entrada-nao-lida")
        client.shutdown(socket.SHUT_WR)
        raw.linger()
        client.settimeout(2)
        assert client.recv(100) == b"erro-final"
        assert client.recv(100) == b""  # FIN do servidor
        assert server.fileno() != -1  # linger nao fecha o socket

    def test_linger_limitado_em_tempo_com_peer_que_nao_fecha(self, pair):
        server, _client = pair
        limits = TransportLimits(poll_ms=20, linger_ms=200)
        started = time.monotonic()
        channel(server, limits=limits).linger()
        assert time.monotonic() - started < 1.0

    def test_linger_limitado_em_bytes(self, pair):
        server, client = pair
        client.sendall(os.urandom(50_000))
        limits = TransportLimits(poll_ms=20, linger_ms=5_000, linger_bytes=1_000)
        recording = RecordingSocket(server)
        started = time.monotonic()
        channel(recording, limits=limits).linger()
        assert sum(recording.received) <= 1_000
        assert time.monotonic() - started < 2.0

    def test_linger_atende_a_parada(self, pair):
        server, _client = pair
        limits = TransportLimits(poll_ms=20, linger_ms=5_000)
        started = time.monotonic()
        channel(server, stop=lambda: True, limits=limits).linger()
        assert time.monotonic() - started < 0.5

    @pytest.mark.parametrize(
        "field",
        [
            "poll_ms",
            "chunk_bytes",
            "tls_handshake_rounds",
            "tls_handshake_bytes",
            "linger_ms",
            "linger_bytes",
        ],
    )
    @pytest.mark.parametrize("value", [0, -1, True])
    def test_limites_estritos(self, field, value):
        with pytest.raises(ValueError, match="limite"):
            TransportLimits(**{field: value})


@pytest.fixture(scope="module")
def server_tls(tmp_path_factory):
    directory = tmp_path_factory.mktemp("transport-tls")
    cert, _, _ = make_certificate(directory, "rsa-sha256")
    return prepare_server_tls(cert.cert_path, cert.key_path)


def tls_client(sock: socket.socket) -> ssl.SSLSocket:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    sock.settimeout(5)
    return context.wrap_socket(sock)


def client_hello() -> bytes:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
    obj = context.wrap_bio(incoming, outgoing)
    with contextlib.suppress(ssl.SSLWantReadError):
        obj.do_handshake()
    return outgoing.read()


class TestTls:
    def test_roundtrip_sobre_o_mesmo_socket(self, pair, server_tls):
        server, client = pair
        fileno = server.fileno()
        recording = RecordingSocket(server)
        payload = os.urandom(300_000)

        def echo(sock):
            tls = tls_client(sock)
            data = bytearray()
            while len(data) < len(payload):
                data += tls.recv(65536)
            tls.sendall(bytes(data))
            return bytes(data)

        with Peer(client, echo) as peer, watchdog(30):
            raw = channel(recording)
            tls = TlsChannel(raw, server_tls.context)
            tls.handshake(Deadline(5))
            tls.send_all(payload, Deadline(10))
            back = tls.recv_exact(len(payload), Deadline(10))
        assert peer.error is None
        assert back == payload
        assert server.fileno() == fileno  # o socket raw nunca foi destacado
        assert max(recording.sent) <= FAST.chunk_bytes
        assert max(recording.received) <= FAST.chunk_bytes

    def test_lixo_no_lugar_do_client_hello(self, pair, server_tls):
        server, client = pair
        client.sendall(b"\x16\x03\x01\x00\x05lixo!" + os.urandom(64))
        tls = TlsChannel(channel(server), server_tls.context)
        assert failure_of(tls.handshake, Deadline(3)) is TransportFailure.TLS

    def test_client_hello_gotejado_estoura_o_prazo(self, pair, server_tls):
        server, client = pair
        hello = client_hello()
        stop_drip = threading.Event()

        def drip(sock):
            for byte in hello:
                if stop_drip.is_set():
                    return
                with contextlib.suppress(OSError):
                    sock.send(bytes([byte]))
                time.sleep(0.02)

        with Peer(client, drip):
            tls = TlsChannel(channel(server), server_tls.context)
            started = time.monotonic()
            kind = failure_of(tls.handshake, Deadline(0.3))
            elapsed = time.monotonic() - started
            stop_drip.set()
        assert kind is TransportFailure.TIMEOUT
        assert elapsed < 1.5

    def test_limite_de_bytes_do_handshake(self, pair, server_tls):
        server, client = pair
        client.sendall(client_hello())
        limits = TransportLimits(poll_ms=20, tls_handshake_bytes=100)
        tls = TlsChannel(channel(server, limits=limits), server_tls.context)
        assert failure_of(tls.handshake, Deadline(3)) is TransportFailure.LIMIT

    def test_limite_de_voltas_do_handshake(self, pair, server_tls):
        server, client = pair
        client.sendall(client_hello()[:10])  # parcial: precisa de mais voltas
        limits = TransportLimits(poll_ms=20, tls_handshake_rounds=1)
        tls = TlsChannel(channel(server, limits=limits), server_tls.context)
        assert failure_of(tls.handshake, Deadline(3)) is TransportFailure.LIMIT

    def test_eof_no_meio_do_handshake(self, pair, server_tls):
        server, client = pair
        client.sendall(client_hello()[:20])
        client.close()
        tls = TlsChannel(channel(server), server_tls.context)
        assert failure_of(tls.handshake, Deadline(3)) is TransportFailure.EOF

    def test_falha_ao_criar_o_objeto_tls(self, pair):
        server, _client = pair

        class BrokenContext:
            def wrap_bio(self, *_args, **_kwargs):
                raise ssl.SSLError("canario-wrap")

        with pytest.raises(TransportError) as info:
            TlsChannel(channel(server), BrokenContext())  # type: ignore[arg-type]
        assert info.value.kind is TransportFailure.TLS
        assert "canario" not in str(info.value)
        assert info.value.__context__ is None
