"""Fase 9, Etapa 7 (D-110, lote 3): listener PGWire, so loopback efemero.

Clientes por socket cru na thread do teste; listener com fim fisico provado
pela fixture. Prova:

- settings injetados revalidados ANTES do bind; TLS obrigatorio fora dos
  literais; hostname so com endereco literal ja resolvido, sem DNS;
- admissao: bucket global por tentativa (relogio falso), vagas pre-auth,
  teto de threads `1 + P + S`, recusa `53300` sem thread;
- ownership D-107/D-108: `start()` que falha antes de rodar, com o alvo
  retido (cancelado sem entrar) e depois de rodar; `close()` falho; erro
  inesperado do driver sem excepthook; recolhimento so pelo dono;
- parada: durante cabecalho, TLS, gotejamento e peer que nao le; corrida
  accept x stop; pre-auth x auth x stop; idempotencia, retry e self-stop;
- isolamento: sem env, registry, upstream, log ou thread daemon.
"""

from __future__ import annotations

import ast
import contextlib
import pathlib
import socket
import threading
import time
from typing import Any

import pytest

import maskgw.pgwire.listener as listener_module
from maskgw.errors import ConfigError
from maskgw.pgwire.errors import PgwireErrorCategory, error_response
from maskgw.pgwire.listener import (
    ListenerState,
    PgwireListener,
    PgwireListenerError,
    PgwireListenerIncompleteError,
)
from maskgw.pgwire.tls import prepare_server_tls
from tests.pgwire_driver_support import ScramClient, authenticate, ssl_request, startup, terminate
from tests.pgwire_listener_support import (
    THREAD_PREFIX,
    connect_raw,
    drain,
    faulty_factory,
    listener_threads,
    make_settings,
    new_credential,
    running,
    wait_until,
)
from tests.pgwire_support import make_certificate

REFUSAL = error_response(PgwireErrorCategory.TOO_MANY_CONNECTIONS)


@pytest.fixture(scope="module")
def credential():
    return new_credential()


@pytest.fixture(scope="module")
def server_tls(tmp_path_factory):
    directory = tmp_path_factory.mktemp("listener-tls")
    cert, _, _ = make_certificate(directory, "rsa-sha256")
    return prepare_server_tls(cert.cert_path, cert.key_path)


@pytest.fixture(autouse=True)
def _sem_threads_remanescentes():
    yield
    assert not listener_threads(), [t.name for t in listener_threads()]


def build(settings: Any, principal: Any, **options: Any) -> PgwireListener:
    options.setdefault("tls", None)
    options.setdefault("alias_accepted", lambda alias: alias == "crm")
    return PgwireListener(settings, principal=principal, **options)


class TestConfiguracao:
    @pytest.mark.parametrize(
        "changes",
        [
            {"port": 0},
            {"port": 65536},
            {"bind": "gateway.test"},  # hostname sem a marca
            {"bind": "127.0.0.1", "bind_is_hostname": True},
            {"max_sessions": 0},
            {"idle_timeout_ms": True},
            {"password": ""},
            {"username": "a" * 64},
            {"bind": "0.0.0.0"},  # noqa: S104 - externo sem TLS: recusado
            {"tls_cert": "c.crt"},  # cert sem chave
        ],
    )
    def test_settings_injetados_invalidos_falham_antes_do_bind(
        self, credential, monkeypatch, changes
    ):
        principal, password = credential
        created: list[Any] = []
        monkeypatch.setattr(
            "maskgw.pgwire.listener.socket.socket", lambda *a, **_k: created.append(a)
        )
        settings = make_settings(password)
        fields = {f: getattr(settings, f) for f in settings.__dataclass_fields__}
        fields.update(changes)
        with pytest.raises(ConfigError) as info:
            build(type(settings)(**fields), principal)
        assert info.value.__context__ is None
        assert created == []
        assert password not in str(info.value)

    def test_tls_coerente_com_as_settings(self, credential, server_tls):
        principal, password = credential
        with pytest.raises(ConfigError):
            build(make_settings(password, tls=True), principal)  # cert sem contexto
        with pytest.raises(ConfigError):
            build(make_settings(password), principal, tls=server_tls)  # contexto sem cert

    @pytest.mark.parametrize("bind", ["127.0.0.2", "::ffff:127.0.0.1", "localhost"])
    def test_tls_obrigatorio_fora_dos_literais(self, credential, bind):
        principal, password = credential
        with pytest.raises(ConfigError):
            build(
                make_settings(password, bind=bind, bind_is_hostname=bind == "localhost"), principal
            )

    def test_porta_de_teste_so_efemera(self, credential):
        principal, password = credential
        with pytest.raises(ConfigError):
            build(make_settings(password), principal, test_port=5432)

    def test_hostname_sem_colaborador_falha_antes_do_bind(self, credential, server_tls):
        principal, password = credential
        settings = make_settings(password, bind="gateway.test", bind_is_hostname=True, tls=True)
        for resolved in (None, [], ["127.0.0.1", "127.0.0.2"], ["gateway.test"], "127.0.0.1"):
            with pytest.raises(ConfigError):
                build(settings, principal, tls=server_tls, resolved_addresses=resolved)

    def test_endereco_resolvido_so_para_hostname(self, credential):
        principal, password = credential
        with pytest.raises(ConfigError):
            build(make_settings(password), principal, resolved_addresses=["127.0.0.1"])

    def test_hostname_com_literal_resolvido_sem_dns_e_com_tls(
        self, credential, server_tls, monkeypatch
    ):
        principal, password = credential
        flags: list[int] = []
        original = socket.getaddrinfo

        def numeric_only(host, port, *args, **kwargs):
            flags.append(kwargs.get("flags", 0))
            return original(host, port, *args, **kwargs)

        monkeypatch.setattr("maskgw.pgwire.listener.socket.getaddrinfo", numeric_only)
        monkeypatch.setattr(socket, "gethostbyname", lambda *_a: pytest.fail("DNS"))
        settings = make_settings(password, bind="localhost", bind_is_hostname=True, tls=True)
        with running(
            settings, principal, tls=server_tls, resolved_addresses=["127.0.0.1"]
        ) as listener:
            bind_flags = list(flags)  # so as chamadas do bind, antes do cliente
            sock = connect_raw(listener)
            with sock:
                sock.sendall(startup())  # em claro, com TLS obrigatorio
                answer = drain(sock)
        assert answer == error_response(PgwireErrorCategory.PROTOCOL_VIOLATION)
        assert bind_flags and all(f & socket.AI_NUMERICHOST for f in bind_flags)

    def test_construir_nao_cria_thread_nem_socket(self, credential, monkeypatch):
        principal, password = credential
        monkeypatch.setenv("MASKGW_PGWIRE_ENABLED", "1")
        listener = build(make_settings(password), principal, test_port=0)
        assert listener.status().state is ListenerState.NEW
        assert not listener_threads()
        listener.stop()
        assert listener.status().state is ListenerState.STOPPED


class TestCicloBasico:
    def test_autentica_termina_e_recolhe(self, credential):
        principal, password = credential
        with running(make_settings(password), principal) as listener:
            assert listener.status().state is ListenerState.RUNNING
            sock = connect_raw(listener)
            with sock:
                messages = authenticate(sock, ScramClient(password))
                assert messages[-1] == (b"Z", b"I")
                assert listener.status().authenticated == 1
                sock.sendall(terminate())
                assert drain(sock) == b""
            assert wait_until(lambda: listener.status().connections == 0)
            status = listener.status()
            assert (status.pre_auth, status.authenticated) == (0, 0)
        assert listener.status().state is ListenerState.STOPPED

    def test_threads_nao_daemon(self, credential):
        principal, password = credential
        with running(make_settings(password), principal) as listener:
            sock = connect_raw(listener)
            with sock:
                assert wait_until(lambda: len(listener_threads()) == 2)
                assert all(not t.daemon for t in listener_threads())

    def test_stop_idempotente_e_start_unico(self, credential):
        principal, password = credential
        with (
            running(make_settings(password), principal) as listener,
            pytest.raises(PgwireListenerError),
        ):
            listener.start()
        listener.stop()
        listener.stop()
        assert listener.status().state is ListenerState.STOPPED
        with pytest.raises(PgwireListenerError):
            listener.start()

    def test_porta_fechada_depois_do_stop(self, credential):
        principal, password = credential
        with running(make_settings(password), principal) as listener:
            port = listener.port
        with pytest.raises(OSError), socket.create_connection(("127.0.0.1", port), timeout=1):
            pass


class TestAdmissao:
    def test_vagas_pre_auth_recusam_sem_thread(self, credential):
        principal, password = credential
        with running(make_settings(password, pre_auth_slots=1), principal) as listener:
            first = connect_raw(listener)
            with first:
                assert wait_until(lambda: listener.status().pre_auth == 1)
                threads = len(listener_threads())
                second = connect_raw(listener)
                with second:
                    assert drain(second) == REFUSAL
                assert len(listener_threads()) == threads  # nenhuma thread nova

    def test_teto_de_threads_1_mais_p_mais_s(self, credential):
        principal, password = credential
        settings = make_settings(password, pre_auth_slots=2, max_sessions=1)
        with running(settings, principal) as listener:
            socks = [connect_raw(listener) for _ in range(2)]
            try:
                assert wait_until(lambda: listener.status().pre_auth == 2)
                extras = [connect_raw(listener) for _ in range(3)]
                try:
                    assert [drain(s) for s in extras] == [REFUSAL] * 3
                    assert len(listener_threads()) <= 1 + 2 + 1
                finally:
                    for s in extras:
                        s.close()
            finally:
                for s in socks:
                    s.close()

    def test_sessao_autenticada_ocupa_s_e_libera_pre_auth(self, credential):
        principal, password = credential
        settings = make_settings(password, pre_auth_slots=1, max_sessions=1)
        with running(settings, principal) as listener:
            first = connect_raw(listener)
            with first:
                authenticate(first, ScramClient(password))
                status = listener.status()
                assert (status.pre_auth, status.authenticated) == (0, 1)
                second = connect_raw(listener)  # pre-auth livre de novo
                with second:
                    messages = authenticate(second, ScramClient(password))
                    # Sem vaga S: a reserva e recusada, sem AuthenticationOk.
                    assert messages == [(b"E", REFUSAL[5:])]

    def test_bucket_global_por_tentativa_com_relogio_falso(self, credential):
        principal, password = credential
        clock = [1000.0]
        settings = make_settings(password, admission_burst=2, admission_refill_per_s=1)
        with running(settings, principal, clock=lambda: clock[0]) as listener:

            def attempt() -> bytes:
                sock = connect_raw(listener)
                with sock:
                    sock.shutdown(socket.SHUT_WR)  # EOF imediato: tambem gasta token
                    return drain(sock)

            first, second, third = attempt(), attempt(), attempt()
            assert (first, second) == (b"", b"")
            assert third == REFUSAL
            clock[0] += 1.0  # recarga de 1 token
            assert attempt() == b""
            assert attempt() == REFUSAL


class TestOwnership:
    def test_start_que_falha_antes_de_rodar_retem_vaga_e_quebra(self, credential):
        principal, password = credential
        factory = faulty_factory("maskgw-pgwire-connection", "before")
        settings = make_settings(password)
        with running(
            settings, principal, thread_factory=factory, allow_incomplete=True
        ) as listener:
            sock = connect_raw(listener)
            with sock:
                assert wait_until(lambda: listener.status().state is ListenerState.BROKEN)
                assert drain(sock) == b""  # socket fechado pelo dono (cancelado sem entrar)
            status = listener.status()
            assert (status.pre_auth, status.connections) == (1, 1)  # retidos: sem prova
            other = socket.create_connection(("127.0.0.1", listener.port), timeout=2)
            with other:
                other.settimeout(0.5)
                with contextlib.suppress(TimeoutError):
                    assert other.recv(1) == b""  # nao admitido
            assert len(listener_threads()) == 1  # so o acceptor
        with pytest.raises(PgwireListenerIncompleteError):
            listener.stop()  # retry: continua sem prova
        assert listener.status().state is ListenerState.INCOMPLETE
        assert listener.status().connections == 1

    def test_start_que_falha_com_alvo_retido_e_cancelado_sem_entrar(self, credential, monkeypatch):
        principal, password = credential
        gate = threading.Event()
        calls: list[str] = []
        monkeypatch.setattr(
            listener_module, "run_startup_session", lambda *_a, **_k: calls.append("driver")
        )
        factory = faulty_factory("maskgw-pgwire-connection", "gated", gate=gate)
        with running(make_settings(password), principal, thread_factory=factory) as listener:
            sock = connect_raw(listener)
            with sock:
                assert wait_until(lambda: listener.status().state is ListenerState.BROKEN)
                assert drain(sock) == b""
            gate.set()  # o alvo entra agora: ve `cancelled` e sai
            assert wait_until(lambda: listener.status().connections == 0)
        assert calls == []  # o driver nunca foi chamado
        assert listener.status().state is ListenerState.STOPPED

    def test_start_que_falha_depois_de_rodar_e_recolhido(self, credential):
        principal, password = credential
        factory = faulty_factory("maskgw-pgwire-connection", "after_run")
        with running(make_settings(password), principal, thread_factory=factory) as listener:
            sock = connect_raw(listener)
            with sock:
                assert wait_until(lambda: listener.status().state is ListenerState.BROKEN)
        assert listener.status().state is ListenerState.STOPPED
        assert listener.status().connections == 0

    def test_acceptor_que_nao_inicia(self, credential):
        principal, password = credential
        factory = faulty_factory("maskgw-pgwire-acceptor", "before")
        listener = build(make_settings(password), principal, test_port=0, thread_factory=factory)
        with pytest.raises(PgwireListenerError):
            listener.start()
        assert listener.status().state is ListenerState.BROKEN
        for _ in range(2):
            with pytest.raises(PgwireListenerIncompleteError):
                listener.stop()
        assert listener.status().state is ListenerState.INCOMPLETE

    def test_acceptor_que_falha_depois_de_rodar_e_recolhido(self, credential):
        principal, password = credential
        factory = faulty_factory("maskgw-pgwire-acceptor", "after_run")
        listener = build(make_settings(password), principal, test_port=0, thread_factory=factory)
        with pytest.raises(PgwireListenerError):
            listener.start()
        listener.stop()
        assert listener.status().state is ListenerState.STOPPED

    def test_close_falho_retem_registro(self, credential, monkeypatch):
        principal, password = credential
        original = listener_module._close_socket
        holder: dict[str, Any] = {}

        def failing(sock: socket.socket) -> bool:
            if sock is not holder.get("listener_socket"):
                return False  # close() da conexao "falhou"
            return original(sock)

        with running(make_settings(password), principal, allow_incomplete=True) as listener:
            holder["listener_socket"] = listener._socket
            monkeypatch.setattr(listener_module, "_close_socket", failing)
            sock = connect_raw(listener)
            sock.close()
            assert wait_until(lambda: listener.status().state is ListenerState.BROKEN)
            assert listener.status().connections == 1
        assert listener.status().state is ListenerState.INCOMPLETE
        monkeypatch.setattr(listener_module, "_close_socket", original)
        # Higiene do teste: o socket retido pelo produto e fechado aqui.
        for record in listener._connections:
            record.sock.close()

    def test_falha_inesperada_na_admissao_quebra_e_fecha_o_socket(self, credential, monkeypatch):
        principal, password = credential
        hooked: list[Any] = []
        monkeypatch.setattr(threading, "excepthook", hooked.append)
        armed = {"on": False}

        def clock() -> float:
            if armed["on"]:
                raise RuntimeError("canario-relogio")
            return time.monotonic()

        with running(make_settings(password), principal, clock=clock) as listener:
            armed["on"] = True
            sock = connect_raw(listener)
            with sock:
                assert wait_until(lambda: listener.status().state is ListenerState.BROKEN)
                assert drain(sock) == b""  # o dono fechou o socket nao adotado
            assert listener.status().connections == 0
        assert listener.status().state is ListenerState.STOPPED
        assert hooked == []

    def test_erro_inesperado_do_driver_nao_chega_ao_excepthook(self, credential, monkeypatch):
        principal, password = credential
        hooked: list[Any] = []
        monkeypatch.setattr(threading, "excepthook", hooked.append)

        def explode(*_args, **_kwargs):
            raise RuntimeError("canario-driver")

        monkeypatch.setattr(listener_module, "run_startup_session", explode)
        with running(make_settings(password), principal) as listener:
            sock = connect_raw(listener)
            with sock:
                assert wait_until(lambda: listener.status().connections == 0)
        assert hooked == []

    def test_self_stop_recusado_antes_de_efeito(self, credential):
        principal, password = credential
        refused: list[str] = []
        holder: dict[str, PgwireListener] = {}

        def alias(name: str) -> bool:
            try:
                holder["listener"].stop()
            except RuntimeError:
                refused.append("recusado")
            return name == "crm"

        with running(make_settings(password), principal, alias_accepted=alias) as listener:
            holder["listener"] = listener
            sock = connect_raw(listener)
            with sock:
                messages = authenticate(sock, ScramClient(password))
            assert messages[-1] == (b"Z", b"I")
            assert refused == ["recusado"]
            assert listener.status().state is ListenerState.RUNNING


class TestParada:
    def _stop_with(
        self, credential: Any, prepare: Any, *, tls: Any = None, settings: Any = None
    ) -> float:
        principal, password = credential
        settings = settings or make_settings(password, tls=tls is not None)
        listener = None
        sock = None
        try:
            with running(settings, principal, tls=tls) as listener:
                sock = connect_raw(listener)
                prepare(sock)
                assert wait_until(lambda: listener.status().connections == 1)
                started = time.monotonic()
                listener.stop()
                elapsed = time.monotonic() - started
        finally:
            if sock is not None:
                sock.close()
        assert listener is not None
        assert listener.status().state is ListenerState.STOPPED
        assert elapsed < 3.0
        return elapsed

    def test_durante_o_cabecalho(self, credential):
        self._stop_with(credential, lambda s: s.sendall(startup()[:3]))

    def test_durante_o_tls(self, credential, server_tls):
        def partial_tls(sock):
            sock.sendall(ssl_request())
            assert sock.recv(1) == b"S"
            sock.sendall(b"\x16\x03\x01")  # ClientHello truncado

        self._stop_with(credential, partial_tls, tls=server_tls)

    def test_durante_gotejamento(self, credential):
        stop_drip = threading.Event()

        def prepare(sock):
            def drip():
                for byte in startup():
                    if stop_drip.is_set():
                        return
                    with contextlib.suppress(OSError):
                        sock.send(bytes([byte]))
                    time.sleep(0.05)

            thread = threading.Thread(target=drip, name="teste-gotejamento")
            thread.start()
            prepare.thread = thread  # type: ignore[attr-defined]

        try:
            self._stop_with(credential, prepare)
        finally:
            stop_drip.set()
            prepare.thread.join(5)  # type: ignore[attr-defined]
            assert not prepare.thread.is_alive()  # type: ignore[attr-defined]

    def test_peer_que_nao_le(self, credential, server_tls):
        def no_read(sock):
            sock.sendall(ssl_request())
            sock.sendall(b"\x16\x03\x01\x00\x05lixo!")  # nunca le a resposta

        self._stop_with(credential, no_read, tls=server_tls)

    def test_pre_auth_e_auth_durante_stop(self, credential):
        principal, password = credential
        with running(make_settings(password), principal) as listener:
            authenticated = connect_raw(listener)
            idle = connect_raw(listener)
            try:
                authenticate(authenticated, ScramClient(password))
                assert wait_until(lambda: listener.status().connections == 2)
                listener.stop()
                assert drain(idle) == b""
                assert drain(authenticated) == b""
            finally:
                authenticated.close()
                idle.close()
        assert listener.status().state is ListenerState.STOPPED

    def test_request_stop_fecha_a_admissao_sem_esperar(self, credential):
        principal, password = credential
        with running(make_settings(password), principal) as listener:
            idle = connect_raw(listener)
            try:
                assert wait_until(lambda: listener.status().connections == 1)
                started = time.monotonic()
                listener.request_stop()
                listener.request_stop()  # idempotente
                assert time.monotonic() - started < 0.1  # sem join nem espera
                assert listener.status().state is ListenerState.STOPPING
                listener.stop()  # o recolhimento com prova continua sendo o stop
                assert drain(idle) == b""
            finally:
                idle.close()
        assert listener.status().state is ListenerState.STOPPED

    def test_request_stop_antes_do_start(self, credential):
        principal, password = credential
        listener = build(make_settings(password), principal, test_port=0)
        listener.request_stop()
        assert listener.status().state is ListenerState.STOPPED
        listener.stop()
        with pytest.raises(PgwireListenerError):
            listener.start()

    def test_corrida_accept_x_stop(self, credential):
        principal, password = credential
        done = threading.Event()
        attempts = {"n": 0}

        def hammer(port: int) -> None:
            while not done.is_set():
                with contextlib.suppress(OSError):
                    s = socket.create_connection(("127.0.0.1", port), timeout=0.5)
                    s.close()
                attempts["n"] += 1

        with running(make_settings(password), principal) as listener:
            thread = threading.Thread(target=hammer, args=(listener.port,), name="teste-martelo")
            thread.start()
            try:
                time.sleep(0.3)
                listener.stop()
            finally:
                done.set()
                thread.join(5)
        assert not thread.is_alive()
        assert attempts["n"] > 0
        assert listener.status().state is ListenerState.STOPPED
        assert listener.status().connections == 0


class TestIsolamento:
    def test_modulo_sem_env_registry_upstream_nem_log(self):
        path = pathlib.Path(listener_module.__file__)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        forbidden = (
            "logging",
            "maskgw.runtime",
            "maskgw.db",
            "maskgw.datasource",
            "maskgw.bootstrap",
            "maskgw.audit",
            "psycopg",
        )
        assert not [m for m in imported if m.startswith(forbidden)]
        source = path.read_text(encoding="utf-8")
        for token in ("environ", "getenv", "print(", "wrap_socket(", "daemon=True"):
            assert token not in source

    def test_threads_do_listener_tem_o_prefixo_observado(self, credential):
        principal, password = credential
        with running(make_settings(password), principal) as listener:
            sock = connect_raw(listener)
            with sock:
                assert wait_until(lambda: len(listener_threads()) == 2)
                names = {t.name for t in threading.enumerate() if t.name.startswith(THREAD_PREFIX)}
                assert names == {"maskgw-pgwire-acceptor", "maskgw-pgwire-connection"}
