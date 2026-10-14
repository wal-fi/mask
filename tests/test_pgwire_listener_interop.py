"""Fase 9, Etapa 7 (D-110, lote 3): listener de produto contra o libpq real.

Somente `127.0.0.1` com porta efemera (`test_port=0`). Nenhuma query: o
psycopg conecta e fecha (`Terminate`). Prova SCRAM-SHA-256, -PLUS com
`channel_binding=require`, `verify-full` com a CA de teste, senha errada,
capacidade S esgotada (`too many connections`) e `stop()` com uma sessao
autenticada aberta; ao fim, nenhuma thread do listener viva.
"""

from __future__ import annotations

import os
import select
from typing import Any

import psycopg
import pytest

from maskgw.pgwire.listener import ListenerState, PgwireListener
from maskgw.pgwire.tls import prepare_server_tls
from tests.pgwire_listener_support import (
    USER,
    listener_threads,
    make_settings,
    new_credential,
    running,
    wait_until,
)
from tests.pgwire_support import make_certificate


@pytest.fixture(scope="module")
def credential():
    return new_credential()


@pytest.fixture(scope="module")
def certs(tmp_path_factory):
    directory = tmp_path_factory.mktemp("listener-interop")
    ca, ca_cert, ca_key = make_certificate(directory, "rsa-sha256", common_name="ca.test")
    leaf, _, _ = make_certificate(directory, "rsa-sha256", issuer=(ca_cert, ca_key))
    return {"ca": ca, "tls": prepare_server_tls(leaf.cert_path, leaf.key_path)}


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    for name in list(os.environ):
        if name.startswith("PG"):
            monkeypatch.delenv(name)
    yield
    assert not listener_threads()


def options(listener: PgwireListener, password: str, **extra: Any) -> dict[str, Any]:
    return {
        "host": "127.0.0.1",
        "port": listener.port,
        "user": USER,
        "dbname": "crm",
        "password": password,
        "sslmode": "disable",
        "gssencmode": "disable",
        "channel_binding": "disable",
        "connect_timeout": 5,
        **extra,
    }


def failure(listener: PgwireListener, password: str, **extra: Any) -> str:
    with pytest.raises(psycopg.OperationalError) as info:
        psycopg.connect(**options(listener, password, **extra)).close()
    return str(info.value)


class TestLibpq:
    def test_sha256_sem_tls(self, credential):
        principal, password = credential
        with running(make_settings(password), principal) as listener:
            with psycopg.connect(**options(listener, password)):
                assert listener.status().authenticated == 1
            assert wait_until(lambda: listener.status().connections == 0)

    def test_plus_e_verify_full(self, credential, certs):
        principal, password = credential
        settings = make_settings(password, tls=True)
        with running(settings, principal, tls=certs["tls"]) as listener:
            with psycopg.connect(
                **options(listener, password, sslmode="require", channel_binding="require")
            ):
                pass
            with psycopg.connect(
                **options(
                    listener,
                    password,
                    sslmode="verify-full",
                    sslrootcert=str(certs["ca"].cert_path),
                    channel_binding="require",
                )
            ):
                pass
            assert wait_until(lambda: listener.status().connections == 0)

    def test_senha_errada_e_alias_inexistente(self, credential):
        principal, password = credential
        with running(make_settings(password), principal) as listener:
            for message in (
                failure(listener, password + "x"),
                failure(listener, password, dbname="inexistente"),
            ):
                assert "authentication failed" in message
                assert password not in message and "inexistente" not in message

    def test_capacidade_de_sessoes_esgotada(self, credential):
        principal, password = credential
        with running(make_settings(password, max_sessions=1), principal) as listener:
            with psycopg.connect(**options(listener, password)):
                assert "too many connections" in failure(listener, password)
            assert wait_until(lambda: listener.status().connections == 0)

    def test_stop_com_sessao_autenticada_aberta(self, credential):
        principal, password = credential
        with running(make_settings(password), principal) as listener:
            conn = psycopg.connect(**options(listener, password))
            try:
                listener.stop()
                assert listener.status().state is ListenerState.STOPPED
                readable, _, _ = select.select([conn.fileno()], [], [], 3)
                assert readable  # o servidor encerrou: EOF pendente no cliente
            finally:
                conn.close()
