"""Fase 9, Etapa 7 (D-110, lote 2): driver contra o libpq real, so loopback.

Servidor de TESTE: um socket em `127.0.0.1`, porta efemera, UMA conexao, numa
thread nao daemon que chama `run_startup_session` e fecha o socket aceito em
`finally` (o driver nunca fecha). O fim da thread e provado sob watchdog. Nao
e o listener de produto (lote 3). Nenhuma query e enviada: psycopg conecta e
fecha (o `close` envia `Terminate`). Prova:

- SCRAM-SHA-256 sem TLS; -PLUS sobre TLS do lote 1 com
  `channel_binding=require`; `verify-full` com a CA de teste;
- senha errada e alias inexistente com a mesma mensagem `authentication failed`;
- reserva recusada -> `too many connections`;
- TLS exigido e cliente em claro -> recusa;
- thread e sockets do servidor de teste fechados.
"""

from __future__ import annotations

import os
import secrets
import socket
import threading
from collections.abc import Callable
from typing import Any

import psycopg
import pytest

from maskgw.pgwire.credential import prepare_principal
from maskgw.pgwire.driver import DriverLimits, SessionOutcome, run_startup_session
from maskgw.pgwire.tls import ServerTls, prepare_server_tls
from maskgw.pgwire.transport import Deadline, TransportLimits
from tests.pgwire_support import _wait_dead_under_watchdog, make_certificate

USER = "gwuser"


@pytest.fixture(scope="module")
def password() -> str:
    return "senha-interop-" + secrets.token_urlsafe(12)


@pytest.fixture(scope="module")
def principal(password):
    return prepare_principal(USER, password)


@pytest.fixture(scope="module")
def certs(tmp_path_factory):
    directory = tmp_path_factory.mktemp("driver-interop")
    leaf_ca, ca_cert, ca_key = make_certificate(directory, "rsa-sha256", common_name="ca.test")
    leaf, _, _ = make_certificate(directory, "rsa-sha256", issuer=(ca_cert, ca_key))
    other_ca, _, _ = make_certificate(directory, "rsa-sha256", common_name="outra-ca.test")
    return {
        "ca": leaf_ca,
        "other_ca": other_ca,
        "tls": prepare_server_tls(leaf.cert_path, leaf.key_path),
    }


@pytest.fixture(autouse=True)
def _sem_ambiente_libpq(monkeypatch):
    for name in list(os.environ):
        if name.startswith("PG"):
            monkeypatch.delenv(name)


class OneShotServer:
    """Servidor de teste de uma conexao; dono do listener e do socket aceito."""

    def __init__(
        self,
        principal: Any,
        *,
        tls: ServerTls | None = None,
        tls_required: bool = False,
        reserve: Callable[[], bool] = lambda: True,
    ) -> None:
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.listener.settimeout(10)
        self.port = self.listener.getsockname()[1]
        self.accepted: socket.socket | None = None
        self.result: Any = None
        self.error: BaseException | None = None
        self.stop = threading.Event()
        self._options = {
            "principal": principal,
            "tls": tls,
            "tls_required": tls_required,
            "alias_accepted": lambda alias: alias == "crm",
            "reserve_session": reserve,
            "limits": DriverLimits(5_000, 5_000, TransportLimits(poll_ms=50, linger_ms=300)),
            "stop": self.stop.is_set,
        }
        self.thread = threading.Thread(target=self._serve, name="pgwire-interop-server")

    def _serve(self) -> None:
        try:
            conn, _ = self.listener.accept()
        except OSError as error:
            self.error = error
            return
        # O dono cria o prazo absoluto no accept e o entrega ao driver.
        deadline = Deadline(self._options["limits"].startup_deadline_ms / 1000)
        self.accepted = conn
        try:
            self.result = run_startup_session(conn, deadline=deadline, **self._options)
        except BaseException as error:  # registrado e conferido
            self.error = error
        finally:
            conn.close()

    def __enter__(self) -> OneShotServer:
        self.thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.thread.join(15)
        if self.thread.is_alive():
            self.stop.set()
            self.listener.close()
        _wait_dead_under_watchdog(self.thread)
        self.listener.close()


def connect(server: OneShotServer, password: str, **options: Any) -> str | None:
    settings = {
        "host": "127.0.0.1",
        "port": server.port,
        "user": USER,
        "dbname": "crm",
        "password": password,
        "sslmode": "disable",
        "gssencmode": "disable",
        "channel_binding": "disable",
        "connect_timeout": 5,
        **options,
    }
    try:
        with psycopg.connect(**settings):
            return None
    except psycopg.OperationalError as error:
        return str(error)


def assert_closed(server: OneShotServer) -> None:
    assert server.error is None, repr(server.error)
    assert not server.thread.is_alive()
    assert server.listener.fileno() == -1
    assert server.accepted is not None and server.accepted.fileno() == -1


class TestLibpq:
    def test_sha256_sem_tls(self, principal, password):
        with OneShotServer(principal) as server:
            assert connect(server, password) is None
        assert server.result.outcome is SessionOutcome.TERMINATED
        assert not server.result.tls_used
        assert_closed(server)

    def test_plus_com_binding_exigido(self, principal, password, certs):
        with OneShotServer(principal, tls=certs["tls"], tls_required=True) as server:
            assert connect(server, password, sslmode="require", channel_binding="require") is None
        assert server.result.outcome is SessionOutcome.TERMINATED
        assert server.result.tls_used
        assert_closed(server)

    def test_verify_full_com_a_ca_de_teste(self, principal, password, certs):
        with OneShotServer(principal, tls=certs["tls"], tls_required=True) as server:
            error = connect(
                server,
                password,
                sslmode="verify-full",
                sslrootcert=str(certs["ca"].cert_path),
                channel_binding="require",
            )
        assert error is None
        assert server.result.outcome is SessionOutcome.TERMINATED
        assert_closed(server)

    def test_verify_full_com_outra_ca_recusa(self, principal, password, certs):
        with OneShotServer(principal, tls=certs["tls"], tls_required=True) as server:
            error = connect(
                server,
                password,
                sslmode="verify-full",
                sslrootcert=str(certs["other_ca"].cert_path),
            )
        assert error is not None
        assert server.result.outcome in (SessionOutcome.TLS, SessionOutcome.EOF)
        assert_closed(server)

    @pytest.mark.parametrize("options", [{"password_suffix": "x"}, {"dbname": "inexistente"}])
    def test_falha_uniforme(self, principal, password, options):
        secret = password + options.get("password_suffix", "")
        extra = {k: v for k, v in options.items() if k != "password_suffix"}
        with OneShotServer(principal) as server:
            error = connect(server, secret, **extra)
        assert error is not None and "authentication failed" in error
        assert "inexistente" not in error and password not in error
        assert server.result.outcome is SessionOutcome.AUTHENTICATION_FAILED
        assert_closed(server)

    def test_reserva_recusada(self, principal, password):
        with OneShotServer(principal, reserve=lambda: False) as server:
            error = connect(server, password)
        assert error is not None and "too many connections" in error
        assert server.result.outcome is SessionOutcome.TOO_MANY_CONNECTIONS
        assert_closed(server)

    def test_tls_exigido_e_cliente_em_claro(self, principal, password, certs):
        with OneShotServer(principal, tls=certs["tls"], tls_required=True) as server:
            error = connect(server, password, sslmode="disable")
        assert error is not None
        assert server.result.outcome is SessionOutcome.PROTOCOL_VIOLATION
        assert_closed(server)


def test_nenhuma_thread_de_teste_sobrevive():
    names = {thread.name for thread in threading.enumerate()}
    for name in ("pgwire-interop-server", "pgwire-peer", "pgwire-driver-watchdog"):
        assert name not in names
