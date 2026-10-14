"""Fase 9, Etapa 7 (D-109): interoperabilidade das pecas puras com o libpq real.

O servidor e o harness de TESTE (`tests/pgwire_support.py`): so loopback,
porta efemera, uma conexao, sem SQL e sem upstream. O cliente e o libpq do
psycopg instalado. Senhas geradas em memoria; nenhum valor e impresso.

Prova:

- SCRAM-SHA-256 sem TLS, com senha nao ASCII e com a forma equivalente que o
  SASLprep normaliza;
- senha errada, usuario desconhecido, alias inexistente e alias invalido saem
  com os MESMOS bytes de erro (`28P01`), sem nome nem alias;
- SCRAM-SHA-256-PLUS sobre TLS com RSA e ECDSA P-384, `channel_binding=require`;
  o leaf apresentado e o do arquivo;
- negociacao: `-PLUS` oferecido e cliente sem binding -> SHA-256 `n`; so
  SHA-256 oferecido -> `y`, e o cliente que exige binding desiste;
- `verify-full` com a CA de teste conecta; com outra CA o cliente recusa —
  TLS no servidor nao e identidade verificada sem o cliente exigir;
- framing hostil por socket cru; ao fim, thread e sockets do harness fechados.
"""

from __future__ import annotations

import os
import secrets
import socket
import struct
import threading

import psycopg
import pytest

from maskgw.pgwire.credential import prepare_principal
from maskgw.pgwire.errors import PgwireErrorCategory, error_response
from tests.pgwire_support import (
    LoopbackHarness,
    make_certificate,
    presented_leaf,
    server_context,
)

USER = "gwuser"
PLUS_FLAG = "p=tls-server-end-point"


@pytest.fixture(scope="module")
def password() -> str:
    return "senhaⅨ " + secrets.token_urlsafe(12)


@pytest.fixture(scope="module")
def principal(password):
    return prepare_principal(USER, password)


@pytest.fixture(autouse=True)
def _sem_ambiente_libpq(monkeypatch):
    for name in list(os.environ):
        if name.startswith("PG"):
            monkeypatch.delenv(name)


@pytest.fixture(scope="module")
def certs(tmp_path_factory):
    directory = tmp_path_factory.mktemp("pgwire-certs")
    rsa_cert, _, _ = make_certificate(directory, "rsa-sha256")
    ecdsa_cert, _, _ = make_certificate(directory, "ecdsa-p384-sha384")
    ca, ca_cert, ca_key = make_certificate(directory, "rsa-sha256", common_name="ca.test")
    leaf, _, _ = make_certificate(directory, "rsa-sha256", issuer=(ca_cert, ca_key))
    other_ca, _, _ = make_certificate(directory, "rsa-sha256", common_name="outra-ca.test")
    return {"rsa": rsa_cert, "ecdsa": ecdsa_cert, "ca": ca, "leaf": leaf, "other_ca": other_ca}


def connect(harness: LoopbackHarness, password: str, **options: object) -> bool:
    settings = {
        "host": "127.0.0.1",
        "port": harness.port,
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
            return True
    except psycopg.OperationalError as error:
        harness.client_error = str(error)
        return False


def assert_closed(harness: LoopbackHarness) -> None:
    assert not harness.thread.is_alive()
    assert harness.listener.fileno() == -1
    assert harness.sockets
    assert all(item.fileno() == -1 for item in harness.sockets)


def assert_clean_success(harness: LoopbackHarness) -> None:
    outcome = harness.outcome
    assert outcome.authenticated
    assert outcome.category is None
    assert outcome.unexpected is None
    assert outcome.after_ready == [b"X"]  # so Terminate: nenhuma consulta


class TestSemTls:
    def test_sha256_senha_nao_ascii(self, principal, password):
        with LoopbackHarness(principal) as harness:
            assert connect(harness, password)
        assert_clean_success(harness)
        assert harness.outcome.mechanism == "SCRAM-SHA-256"
        assert harness.outcome.gs2_flag == "n"
        assert not harness.outcome.tls_used
        assert_closed(harness)

    def test_forma_equivalente_pelo_saslprep(self, principal, password):
        with LoopbackHarness(principal) as harness:
            assert connect(harness, password.replace("Ⅸ", "IX"))
        assert_clean_success(harness)
        assert_closed(harness)

    def test_falhas_uniformes(self, principal, password):
        sent = set()
        for options in (
            {"password": password + "x"},
            {"user": "desconhecido"},
            {"dbname": "inexistente"},
            {"dbname": "Invalido!"},
        ):
            with LoopbackHarness(principal) as harness:
                assert not connect(harness, **{"password": password, **options})
            outcome = harness.outcome
            assert not outcome.authenticated
            assert outcome.category == PgwireErrorCategory.AUTHENTICATION_FAILED.value
            assert outcome.mechanism == "SCRAM-SHA-256"  # falhou DEPOIS da troca
            assert "authentication failed" in harness.client_error
            for value in ("desconhecido", "inexistente", "Invalido", password):
                assert value not in harness.client_error
            sent.add(outcome.sent_error)
            assert_closed(harness)
        assert sent == {error_response(PgwireErrorCategory.AUTHENTICATION_FAILED)}

    def test_cliente_exigindo_tls_nao_cai_para_texto_claro(self, principal, password):
        with LoopbackHarness(principal) as harness:
            assert not connect(harness, password, sslmode="require")
        assert not harness.outcome.authenticated
        assert_closed(harness)


class TestTls:
    @pytest.mark.parametrize("kind", ["rsa", "ecdsa"])
    def test_plus_com_channel_binding_exigido(self, principal, password, certs, kind):
        context = server_context(certs[kind])
        assert presented_leaf(context) == certs[kind].der
        with LoopbackHarness(principal, context=context) as harness:
            assert connect(harness, password, sslmode="require", channel_binding="require")
        assert_clean_success(harness)
        assert harness.outcome.tls_used
        assert harness.outcome.mechanism == "SCRAM-SHA-256-PLUS"
        assert harness.outcome.gs2_flag == PLUS_FLAG
        assert_closed(harness)

    def test_plus_oferecido_cliente_sem_binding(self, principal, password, certs):
        context = server_context(certs["rsa"])
        with LoopbackHarness(principal, context=context) as harness:
            assert connect(harness, password, sslmode="require", channel_binding="disable")
        assert_clean_success(harness)
        assert harness.outcome.mechanism == "SCRAM-SHA-256"
        assert harness.outcome.gs2_flag == "n"
        assert_closed(harness)

    def test_so_sha256_oferecido_cliente_prefer_envia_y(self, principal, password, certs):
        context = server_context(certs["rsa"])
        with LoopbackHarness(principal, context=context, offer_plus=False) as harness:
            assert connect(harness, password, sslmode="require", channel_binding="prefer")
        assert_clean_success(harness)
        assert harness.outcome.gs2_flag == "y"
        assert_closed(harness)

    def test_so_sha256_oferecido_cliente_require_desiste(self, principal, password, certs):
        context = server_context(certs["rsa"])
        with LoopbackHarness(principal, context=context, offer_plus=False) as harness:
            assert not connect(harness, password, sslmode="require", channel_binding="require")
        assert not harness.outcome.authenticated
        assert_closed(harness)

    def test_falha_sobre_tls_e_a_mesma(self, principal, password, certs):
        context = server_context(certs["rsa"])
        with LoopbackHarness(principal, context=context) as harness:
            assert not connect(
                harness, password + "x", sslmode="require", channel_binding="require"
            )
        assert harness.outcome.category == PgwireErrorCategory.AUTHENTICATION_FAILED.value
        assert harness.outcome.mechanism == "SCRAM-SHA-256-PLUS"
        assert "authentication failed" in harness.client_error
        assert_closed(harness)

    def test_verify_full_com_a_ca_de_teste(self, principal, password, certs):
        context = server_context(certs["leaf"])
        with LoopbackHarness(principal, context=context) as harness:
            assert connect(
                harness,
                password,
                sslmode="verify-full",
                sslrootcert=str(certs["ca"].cert_path),
                channel_binding="require",
            )
        assert_clean_success(harness)
        assert harness.outcome.mechanism == "SCRAM-SHA-256-PLUS"
        assert_closed(harness)

    def test_verify_full_com_outra_ca_recusa_antes_da_senha(self, principal, password, certs):
        context = server_context(certs["leaf"])
        with LoopbackHarness(principal, context=context) as harness:
            assert not connect(
                harness,
                password,
                sslmode="verify-full",
                sslrootcert=str(certs["other_ca"].cert_path),
                channel_binding="require",
            )
        assert not harness.outcome.authenticated
        assert harness.outcome.mechanism is None  # nenhuma troca SCRAM comecou
        assert_closed(harness)


def raw_exchange(harness: LoopbackHarness, payload: bytes) -> bytes:
    with socket.create_connection(("127.0.0.1", harness.port), timeout=5) as client:
        client.sendall(payload)
        data = bytearray()
        while chunk := client.recv(4096):
            data += chunk
    return bytes(data)


class TestFramingHostil:
    @pytest.mark.parametrize(
        ("payload", "category"),
        [
            (struct.pack("!II", 8, 80877104), PgwireErrorCategory.FEATURE_NOT_SUPPORTED),
            (struct.pack("!IIII", 16, 80877102, 1, 2), PgwireErrorCategory.FEATURE_NOT_SUPPORTED),
            (struct.pack("!I", 20_000), PgwireErrorCategory.PROTOCOL_VIOLATION),
            (struct.pack("!I", 4), PgwireErrorCategory.PROTOCOL_VIOLATION),
            (
                struct.pack("!II", 21, (3 << 16) | 2) + b"user\x00gwuser\x00\x00",
                PgwireErrorCategory.FEATURE_NOT_SUPPORTED,
            ),
            (
                struct.pack("!II", 31, 196608) + b"user\x00gwuser\x00options\x00x\x00\x00",
                PgwireErrorCategory.FEATURE_NOT_SUPPORTED,
            ),
        ],
    )
    def test_recusa_fechada(self, principal, payload, category):
        with LoopbackHarness(principal) as harness:
            answer = raw_exchange(harness, payload)
        assert answer == error_response(category)
        assert harness.outcome.category == category.value
        assert harness.outcome.mechanism is None
        assert_closed(harness)

    def test_segundo_ssl_request_e_violacao(self, principal):
        request = struct.pack("!II", 8, 80877103)
        with LoopbackHarness(principal) as harness:
            answer = raw_exchange(harness, request + request)
        assert answer == b"N" + error_response(PgwireErrorCategory.PROTOCOL_VIOLATION)
        assert_closed(harness)

    def test_mensagem_sasl_gigante_recusada_antes_de_alocar(self, principal):
        startup = b"user\x00gwuser\x00database\x00crm\x00\x00"
        payload = struct.pack("!II", 8 + len(startup), 196608) + startup
        payload += b"p" + struct.pack("!I", 1_000_000)
        with LoopbackHarness(principal) as harness:
            answer = raw_exchange(harness, payload)
        assert answer.endswith(error_response(PgwireErrorCategory.PROTOCOL_VIOLATION))
        assert harness.outcome.mechanism is None
        assert_closed(harness)


class TestHarnessLifecycle:
    """O harness prova o fim fisico do worker, sem esconder nem mascarar falhas."""

    def test_falha_no_bloco_propaga_e_limpa(self, principal, password):
        harness = LoopbackHarness(principal)
        with pytest.raises(AssertionError, match="falha-do-teste"), harness:
            assert connect(harness, password)
            raise AssertionError("falha-do-teste")
        assert harness.outcome.authenticated
        assert not harness.thread.daemon
        assert_closed(harness)

    def test_sem_conexao_o_worker_e_destravado_e_termina(self, principal):
        with LoopbackHarness(principal) as harness:
            pass
        assert not harness.thread.is_alive()
        assert harness.listener.fileno() == -1
        assert harness.outcome.unexpected == "accept"

    # Nos dois casos abaixo o `join` falha e o worker esta preso no `accept`:
    # o `__exit__` so pode sair com ele MORTO e tudo fechado, sem `join` depois.

    def test_falha_na_limpeza_nao_mascara_a_falha_anterior(self, principal, monkeypatch):
        harness = LoopbackHarness(principal)
        harness.__enter__()

        def broken_join(_timeout=None):
            raise RuntimeError("canario-da-limpeza")

        monkeypatch.setattr(harness.thread, "join", broken_join)
        original = AssertionError("falha-original")
        harness.__exit__(AssertionError, original, None)  # nao levanta: a original vale
        assert not harness.thread.is_alive()
        assert harness.listener.fileno() == -1
        assert any("RuntimeError" in note for note in original.__notes__)

    def test_falha_na_limpeza_sem_falha_anterior_e_reportada(self, principal, monkeypatch):
        harness = LoopbackHarness(principal)
        harness.__enter__()

        def broken_join(_timeout=None):
            raise RuntimeError("canario-da-limpeza")

        monkeypatch.setattr(harness.thread, "join", broken_join)
        with pytest.raises(RuntimeError, match="canario-da-limpeza"):
            harness.__exit__(None, None, None)
        assert not harness.thread.is_alive()
        assert harness.listener.fileno() == -1

    def test_start_que_falha_sem_iniciar_fecha_o_listener(self, principal, monkeypatch):
        harness = LoopbackHarness(principal)

        def broken_start():
            raise RuntimeError("canario-do-start")

        monkeypatch.setattr(harness.thread, "start", broken_start)
        with pytest.raises(RuntimeError, match="canario-do-start"):
            harness.__enter__()
        assert harness.thread.ident is None
        assert harness.listener.fileno() == -1


def test_nenhuma_thread_do_harness_sobrevive():
    names = {t.name for t in threading.enumerate()}
    assert "pgwire-harness" not in names
    assert "pgwire-harness-watchdog" not in names
