"""Fase 9, Etapa 7 (D-110, lote 2): driver de startup/autenticacao, socketpair.

O cliente roda numa thread de teste nao daemon (`Peer`, fim provado); o
driver roda na thread do teste, sob watchdog. Prova:

- sucesso: SASLFinal, AuthenticationOk, ParameterStatus fixos, BackendKeyData
  aleatorio, ReadyForQuery I; so `Terminate` encerra limpo;
- reserva chamada uma vez, depois da prova e ANTES do AuthenticationOk;
  recusa -> 53300, erro -> XX000, sem causa;
- falha uniforme 28P01 para senha, usuario, alias inexistente, invalido,
  ausente e callback de alias que falha; reserva nao chamada;
- pos-autenticacao: qualquer mensagem alem de `X` -> 0A000 FATAL sem ler o
  corpo; `X` malformado -> 08P01; ociosidade absoluta;
- pre-autenticacao: N/S, SSLRequest duplicado, TLS exigido, GSSENC/Cancel,
  tamanho, EOF, gotejamento, parada; falha TLS depois de `S` nao envia erro em
  claro; SCRAM-PLUS sobre TLS com o binding do lote 1;
- o driver nao fecha o socket do chamador e nao cria thread.
"""

from __future__ import annotations

import contextlib
import socket
import ssl
import struct
import threading
import time
from collections.abc import Callable
from typing import Any

import pytest

from maskgw.pgwire.channel_binding import tls_server_end_point
from maskgw.pgwire.driver import (
    PARAMETER_STATUS,
    DriverLimits,
    SessionOutcome,
    SessionResult,
    run_startup_session,
)
from maskgw.pgwire.errors import PgwireErrorCategory, error_response
from maskgw.pgwire.tls import prepare_server_tls
from maskgw.pgwire.transport import Deadline
from tests.pgwire_driver_support import (
    Peer,
    ScramClient,
    authenticate,
    exact,
    frame,
    new_principal,
    read_message,
    read_messages,
    run_driver,
    ssl_request,
    startup,
    terminate,
)
from tests.pgwire_support import make_certificate

AUTH_ERROR = error_response(PgwireErrorCategory.AUTHENTICATION_FAILED)


@pytest.fixture(scope="module")
def credential():
    return new_principal()


@pytest.fixture(scope="module")
def server_tls(tmp_path_factory):
    directory = tmp_path_factory.mktemp("driver-tls")
    cert, _, _ = make_certificate(directory, "rsa-sha256")
    return prepare_server_tls(cert.cert_path, cert.key_path)


def session(
    script: Callable[[socket.socket], Any], principal: Any, **options: Any
) -> tuple[SessionResult, Any, list[str]]:
    """Roda o driver contra `script`; prova que o socket do chamador fica aberto."""
    server, client = socket.socketpair()
    client.settimeout(10)
    events: list[str] = []
    before = {t.ident for t in threading.enumerate()}
    try:
        with Peer(client, script) as peer:
            result = run_driver(server, principal, events=events, **options)
            assert server.fileno() != -1  # o driver nao fecha o socket do chamador
            created = {t.ident for t in threading.enumerate()} - before - {peer.thread.ident}
            assert not created  # o driver nao cria thread
            server.close()  # o chamador fecha (aqui, para liberar o peer)
    finally:
        server.close()
    assert peer.error is None, repr(peer.error)
    return result, peer.result, events


def kinds(messages: list[tuple[bytes, bytes]]) -> list[bytes]:
    return [kind for kind, _ in messages]


class TestSucesso:
    def test_fluxo_completo_e_terminate(self, credential):
        principal, password = credential
        client = ScramClient(password)

        def script(sock):
            messages = authenticate(sock, client)
            sock.sendall(terminate())
            return messages

        result, messages, events = session(script, principal)
        assert result == SessionResult(SessionOutcome.TERMINATED, False, True)
        assert events == ["alias", "reserve"]
        assert kinds(messages) == [b"R", b"R"] + [b"S"] * len(PARAMETER_STATUS) + [b"K", b"Z"]
        assert messages[0][1] == struct.pack("!I", 12) + client.expected_final
        assert messages[1][1] == struct.pack("!I", 0)
        statuses = [
            tuple(body.rstrip(b"\x00").split(b"\x00")) for kind, body in messages if kind == b"S"
        ]
        assert statuses == [(n.encode(), v.encode()) for n, v in PARAMETER_STATUS]
        assert messages[-1] == (b"Z", b"I")

    def test_backend_key_data_aleatorio(self, credential):
        principal, password = credential
        keys = set()
        for _ in range(3):
            client = ScramClient(password)

            def script(sock, client=client):
                messages = authenticate(sock, client)
                sock.sendall(terminate())
                return messages

            _, messages, _ = session(script, principal)
            keys.add(dict(messages)[b"K"])
        assert len(keys) == 3

    def test_reserva_antes_do_authentication_ok(self, credential):
        principal, password = credential
        client = ScramClient(password)

        def script(sock):
            return authenticate(sock, client)

        result, messages, events = session(script, principal, reserve=lambda: False)
        assert result.outcome is SessionOutcome.TOO_MANY_CONNECTIONS
        assert not result.authenticated
        assert events == ["alias", "reserve"]
        # Nenhum SASLFinal/AuthenticationOk saiu: so o 53300 fixo.
        assert messages == [
            read_message_bytes(error_response(PgwireErrorCategory.TOO_MANY_CONNECTIONS))
        ]

    def test_erro_do_callback_de_reserva_e_fechado(self, credential):
        principal, password = credential
        client = ScramClient(password)

        def broken():
            raise RuntimeError("canario-reserva")

        result, messages, _ = session(
            lambda sock: authenticate(sock, client), principal, reserve=broken
        )
        assert result.outcome is SessionOutcome.INTERNAL_ERROR
        assert messages == [read_message_bytes(error_response(PgwireErrorCategory.INTERNAL_ERROR))]
        assert b"canario" not in b"".join(body for _, body in messages)


def read_message_bytes(data: bytes) -> tuple[bytes, bytes]:
    (length,) = struct.unpack("!I", data[1:5])
    return data[:1], data[5 : 1 + length]


class TestFalhaUniforme:
    @pytest.mark.parametrize(
        ("user", "database", "wrong_password"),
        [
            ("gwuser", "crm", True),
            ("desconhecido", "crm", False),
            ("gwuser", "inexistente", False),
            ("gwuser", "Invalido!", False),
            ("gwuser", None, False),
        ],
    )
    def test_mesmo_28p01(self, credential, user, database, wrong_password):
        principal, password = credential
        client = ScramClient(password + ("x" if wrong_password else ""))

        def script(sock):
            return authenticate(sock, client, user=user, database=database)

        result, messages, events = session(script, principal)
        assert result.outcome is SessionOutcome.AUTHENTICATION_FAILED
        assert messages == [read_message_bytes(AUTH_ERROR)]
        assert "reserve" not in events

    def test_callback_de_alias_que_falha_e_alias_recusado(self, credential):
        principal, password = credential
        client = ScramClient(password)

        class Exploding(frozenset[str]):
            def __contains__(self, _item):
                raise RuntimeError("canario-selo")

        result, messages, events = session(
            lambda sock: authenticate(sock, client), principal, aliases=Exploding({"crm"})
        )
        assert result.outcome is SessionOutcome.AUTHENTICATION_FAILED
        assert messages == [read_message_bytes(AUTH_ERROR)]
        assert "reserve" not in events

    def test_prova_adulterada(self, credential):
        principal, password = credential
        client = ScramClient(password)
        result, messages, _ = session(
            lambda sock: authenticate(sock, client, tamper=True), principal
        )
        assert result.outcome is SessionOutcome.AUTHENTICATION_FAILED
        assert messages == [read_message_bytes(AUTH_ERROR)]


def authenticated_then(payload: bytes, password: str) -> Callable[[socket.socket], Any]:
    client = ScramClient(password)

    def script(sock):
        authenticate(sock, client)
        sock.sendall(payload)
        return read_messages(sock)

    return script


class TestPosAutenticacao:
    @pytest.mark.parametrize(
        "kind",
        [
            b"Q",
            b"P",
            b"B",
            b"D",
            b"E",
            b"C",
            b"S",
            b"H",
            b"F",
            b"d",
            b"c",
            b"f",
            b"p",
            b"\x00",
            b"\xff",
        ],
    )
    def test_qualquer_mensagem_alem_de_terminate_e_recusada_sem_ler_corpo(self, credential, kind):
        principal, password = credential
        # Cabecalho declarando 1 GB e nenhum corpo: se o driver lesse o corpo,
        # esperaria ate o prazo. Ele responde de imediato, sem ler.
        payload = kind + struct.pack("!I", 1_000_000_000)
        started = time.monotonic()
        result, messages, _ = session(
            authenticated_then(payload, password), principal, idle_ms=5_000
        )
        elapsed = time.monotonic() - started
        assert result.outcome is SessionOutcome.FEATURE_NOT_SUPPORTED
        assert messages == [
            read_message_bytes(error_response(PgwireErrorCategory.FEATURE_NOT_SUPPORTED))
        ]
        assert elapsed < 4

    def test_query_simples_nao_e_interpretada(self, credential):
        principal, password = credential
        payload = frame(b"Q", b"SELECT 'canario-sql'\x00")
        result, _messages, events = session(authenticated_then(payload, password), principal)
        assert result.outcome is SessionOutcome.FEATURE_NOT_SUPPORTED
        assert events == ["alias", "reserve"]  # nada alem do selo e da reserva

    @pytest.mark.parametrize("length", [0, 3, 5, 8, 0xFFFFFFFF])
    def test_terminate_malformado(self, credential, length):
        principal, password = credential
        payload = b"X" + struct.pack("!I", length)
        result, messages, _ = session(authenticated_then(payload, password), principal)
        assert result.outcome is SessionOutcome.PROTOCOL_VIOLATION
        assert messages == [
            read_message_bytes(error_response(PgwireErrorCategory.PROTOCOL_VIOLATION))
        ]

    def test_ociosidade_absoluta(self, credential):
        principal, password = credential
        client = ScramClient(password)

        def script(sock):
            authenticate(sock, client)
            return read_messages(sock)

        started = time.monotonic()
        result, _, _ = session(script, principal, idle_ms=300)
        assert result.outcome is SessionOutcome.TIMEOUT
        assert time.monotonic() - started < 3

    def test_gotejamento_do_cabecalho_nao_renova_ociosidade(self, credential):
        principal, password = credential
        client = ScramClient(password)

        def script(sock):
            authenticate(sock, client)
            for byte in b"X\x00\x00\x00\x04":
                with contextlib.suppress(OSError):
                    sock.send(bytes([byte]))
                time.sleep(0.15)
            return read_messages(sock)

        result, _, _ = session(script, principal, idle_ms=400)
        assert result.outcome is SessionOutcome.TIMEOUT


class TestPreAutenticacao:
    def test_ssl_request_sem_contexto_recebe_n(self, credential):
        principal, password = credential
        client = ScramClient(password)

        def script(sock):
            sock.sendall(ssl_request())
            answer = exact(sock, 1)
            messages = authenticate(sock, client)
            sock.sendall(terminate())
            return answer, messages

        result, (answer, _), _ = session(script, principal)
        assert answer == b"N"
        assert result.outcome is SessionOutcome.TERMINATED

    def test_segundo_ssl_request_e_violacao(self, credential):
        principal, _ = credential

        def script(sock):
            sock.sendall(ssl_request())
            answer = exact(sock, 1)
            sock.sendall(ssl_request())
            return answer, read_messages(sock)

        result, (answer, messages), _ = session(script, principal)
        assert answer == b"N"
        assert result.outcome is SessionOutcome.PROTOCOL_VIOLATION
        assert messages == [
            read_message_bytes(error_response(PgwireErrorCategory.PROTOCOL_VIOLATION))
        ]

    def test_tls_exigido_recusa_startup_em_claro(self, credential, server_tls):
        principal, _ = credential

        def script(sock):
            sock.sendall(startup())
            return read_messages(sock)

        result, messages, events = session(script, principal, tls=server_tls, tls_required=True)
        assert result.outcome is SessionOutcome.PROTOCOL_VIOLATION
        assert messages == [
            read_message_bytes(error_response(PgwireErrorCategory.PROTOCOL_VIOLATION))
        ]
        assert events == []

    def test_tls_exigido_sem_contexto_e_erro_de_programacao(self, credential):
        principal, _ = credential
        server, client = socket.socketpair()
        try:
            with pytest.raises(ValueError, match="TLS"):
                run_driver(server, principal, tls_required=True)
        finally:
            server.close()
            client.close()

    @pytest.mark.parametrize(
        ("payload", "category"),
        [
            (struct.pack("!II", 8, 80877104), PgwireErrorCategory.FEATURE_NOT_SUPPORTED),
            (struct.pack("!IIII", 16, 80877102, 1, 2), PgwireErrorCategory.FEATURE_NOT_SUPPORTED),
            (struct.pack("!I", 20_000), PgwireErrorCategory.PROTOCOL_VIOLATION),
            (struct.pack("!I", 3), PgwireErrorCategory.PROTOCOL_VIOLATION),
            (
                struct.pack("!II", 12, 80877103) + b"\x00" * 4,
                PgwireErrorCategory.PROTOCOL_VIOLATION,
            ),
        ],
    )
    def test_pacote_inicial_recusado(self, credential, payload, category):
        principal, _ = credential

        def script(sock):
            sock.sendall(payload)
            return read_messages(sock)

        result, messages, _ = session(script, principal)
        assert messages == [read_message_bytes(error_response(category))]
        assert result.outcome.value == category.value.lower()

    @pytest.mark.parametrize("prefix", [b"", b"\x00\x00", startup()[:10]])
    def test_eof_em_cada_estagio(self, credential, prefix):
        principal, _ = credential

        def script(sock):
            sock.sendall(prefix)
            sock.shutdown(socket.SHUT_WR)
            return read_messages(sock)

        result, messages, _ = session(script, principal)
        assert result.outcome is SessionOutcome.EOF
        assert messages == []

    def test_eof_no_meio_do_scram(self, credential):
        principal, password = credential
        client = ScramClient(password)

        def script(sock):
            sock.sendall(startup())
            read_message(sock)
            sock.sendall(client.first())
            read_message(sock)
            sock.shutdown(socket.SHUT_WR)
            return read_messages(sock)

        result, _, events = session(script, principal)
        assert result.outcome is SessionOutcome.EOF
        assert events == []

    def test_startup_gotejado_estoura_o_prazo_absoluto(self, credential):
        principal, _ = credential

        def script(sock):
            for byte in startup():
                with contextlib.suppress(OSError):
                    sock.send(bytes([byte]))
                time.sleep(0.05)
            return read_messages(sock)

        started = time.monotonic()
        result, _, _ = session(script, principal, startup_ms=300)
        assert result.outcome is SessionOutcome.TIMEOUT
        assert time.monotonic() - started < 5

    def test_parada_encerra_sem_resposta(self, credential):
        principal, _ = credential
        stopped = threading.Event()
        timer = threading.Timer(0.1, stopped.set)
        timer.start()
        try:
            result, messages, _ = session(read_messages, principal, stop=stopped.is_set)
        finally:
            timer.cancel()
            timer.join()
        assert result.outcome is SessionOutcome.STOPPED
        assert messages == []


class CountingSocket:
    """Proxy de teste: conta toda operacao de IO feita pelo driver."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.calls: list[str] = []

    def settimeout(self, value: float) -> None:
        self.calls.append("settimeout")
        self.sock.settimeout(value)

    def recv(self, size: int) -> bytes:
        self.calls.append("recv")
        return self.sock.recv(size)

    def send(self, data: Any) -> int:
        self.calls.append("send")
        return self.sock.send(data)

    def shutdown(self, how: int) -> None:
        self.calls.append("shutdown")
        self.sock.shutdown(how)


class TestPrazoDoDono:
    """O prazo e criado pelo DONO no accept e nunca reiniciado pelo driver."""

    def test_prazo_ja_expirado_na_entrada(self, credential):
        principal, _ = credential
        server, client = socket.socketpair()
        try:
            client.sendall(startup())  # ha bytes prontos: mesmo assim nada e lido
            counting = CountingSocket(server)
            events: list[str] = []
            expired = Deadline(-1.0)
            result = run_driver(counting, principal, deadline=expired, events=events)  # type: ignore[arg-type]
        finally:
            server.close()
            client.close()
        assert result == SessionResult(SessionOutcome.TIMEOUT, False, False)
        assert counting.calls == []  # sem recv, sem send, sem settimeout
        assert events == []  # nem alias, nem reserva

    def test_prazo_do_accept_nao_e_renovado_pelo_atraso_da_thread(self, credential):
        principal, _ = credential
        clock = [0.0]
        deadline = Deadline(1.0, clock=lambda: clock[0])
        clock[0] = 5.0  # a thread do driver comecou depois do prazo do accept
        server, client = socket.socketpair()
        try:
            client.sendall(startup())
            result = run_driver(server, principal, deadline=deadline, startup_ms=60_000)
        finally:
            server.close()
            client.close()
        assert result.outcome is SessionOutcome.TIMEOUT

    def test_alias_que_consome_o_prazo_impede_a_reserva(self, credential):
        principal, password = credential
        clock = [0.0]
        deadline = Deadline(30.0, clock=lambda: clock[0])
        client = ScramClient(password)

        def consume() -> None:
            clock[0] = 31.0  # o callback do selo levou alem do prazo

        def script(sock):
            return authenticate(sock, client)

        result, messages, events = session(script, principal, deadline=deadline, alias_hook=consume)
        assert result.outcome is SessionOutcome.TIMEOUT
        assert not result.authenticated
        assert events == ["alias"]  # reserva NAO chamada
        assert messages == []  # nem SASLFinal nem AuthenticationOk

    def test_parada_pedida_durante_o_alias_impede_a_reserva(self, credential):
        principal, password = credential
        stopped = threading.Event()
        client = ScramClient(password)

        result, messages, events = session(
            lambda sock: authenticate(sock, client),
            principal,
            stop=stopped.is_set,
            alias_hook=stopped.set,
        )
        assert result.outcome is SessionOutcome.STOPPED
        assert events == ["alias"]
        assert messages == []

    def test_driver_exige_prazo_explicito(self, credential):
        principal, _ = credential
        server, client = socket.socketpair()
        try:
            with pytest.raises(TypeError):
                run_startup_session(  # type: ignore[call-arg]
                    server,
                    principal=principal,
                    tls=None,
                    tls_required=False,
                    alias_accepted=lambda _alias: True,
                    reserve_session=lambda: True,
                    limits=DriverLimits(1_000, 1_000),
                    stop=lambda: False,
                )
        finally:
            server.close()
            client.close()


def tls_client_socket(sock: socket.socket) -> ssl.SSLSocket:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context.wrap_socket(sock)


class TestTls:
    @pytest.mark.parametrize("plus", [True, False])
    def test_scram_sobre_tls(self, credential, server_tls, plus):
        principal, password = credential

        def script(sock):
            sock.sendall(ssl_request())
            assert exact(sock, 1) == b"S"
            tls = tls_client_socket(sock)
            der = tls.getpeercert(binary_form=True)
            if plus:
                assert der is not None
                client = ScramClient(
                    password,
                    mechanism="SCRAM-SHA-256-PLUS",
                    header="p=tls-server-end-point,,",
                    binding=tls_server_end_point(der),
                )
            else:
                client = ScramClient(password)
            messages = authenticate(tls, client)
            tls.sendall(terminate())
            return messages

        result, messages, _ = session(script, principal, tls=server_tls, tls_required=True)
        assert result == SessionResult(SessionOutcome.TERMINATED, True, True)
        assert messages[-1] == (b"Z", b"I")

    def test_falha_tls_depois_de_s_nao_envia_erro_em_claro(self, credential, server_tls):
        principal, _ = credential

        def script(sock):
            sock.sendall(ssl_request())
            answer = exact(sock, 1)
            sock.sendall(b"\x16\x03\x01\x00\x05lixo!")
            rest = bytearray()
            with contextlib.suppress(OSError):
                while chunk := sock.recv(4096):
                    rest += chunk
            return answer, bytes(rest)

        result, (answer, rest), _ = session(script, principal, tls=server_tls, tls_required=True)
        assert answer == b"S"
        assert result.outcome is SessionOutcome.TLS
        assert b"E" not in rest[:1] and b"SFATAL" not in rest  # nada de ErrorResponse em claro

    def test_binding_de_outro_certificado(self, credential, server_tls, tmp_path):
        principal, password = credential
        other, _, _ = make_certificate(tmp_path, "rsa-sha256")

        def script(sock):
            sock.sendall(ssl_request())
            exact(sock, 1)
            tls = tls_client_socket(sock)
            client = ScramClient(
                password,
                mechanism="SCRAM-SHA-256-PLUS",
                header="p=tls-server-end-point,,",
                binding=tls_server_end_point(other.der),
            )
            return authenticate(tls, client)

        result, messages, _ = session(script, principal, tls=server_tls, tls_required=True)
        assert result.outcome is SessionOutcome.AUTHENTICATION_FAILED
        assert messages == [read_message_bytes(AUTH_ERROR)]
