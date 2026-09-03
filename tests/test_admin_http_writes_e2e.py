"""Fase 7, Etapa 9 — provas end-to-end da rodada corretiva (grupo 6).

Duas garantias, ambas exercitando a fronteira HTTP administrativa REAL:

1. **Uma escrita `PUT /admin/v1/config` autenticada, pela porta administrativa,
   troca o runtime; a consulta seguinte pela tool MCP `query_database`, no MESMO
   processo e sem restart, ve a politica nova** — e o valor original nunca
   aparece na resposta MCP. A escrita vai pela porta admin com token, headers e
   payload completos; a consulta vai pelo protocolo MCP (cliente in-memory).

2. **Uma escrita em andamento, ja dentro da secao critica quando o shutdown
   comeca, TERMINA COM SUCESSO antes do fechamento dos recursos.** `close()` nao
   retorna enquanto a escrita esta presa; liberada, ela recebe exatamente `200`;
   o arquivo persistido contem exatamente a revisao nova; nenhuma thread
   `writer`/`closer`/`maskgw-admin-http` fica viva; nenhuma escrita e aceita
   depois do shutdown; nenhum trabalho administrativo continua.

Ambos exigem PostgreSQL real (`MASKGW_TEST_DSN`); sem ele o arquivo da SKIP.
Deterministico: `Event`/barreiras e joins, sem `sleep`.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import anyio
import psycopg
import pytest
import yaml
from mcp import Client

from maskgw.admin.http import AdminHttpSettings
from maskgw.bootstrap import build_application
from maskgw.bootstrap.application import Application
from maskgw.config.models import MaskingFileConfig
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.mcp.server import build_mcp_server
from maskgw.secretsource import MappingSecretProvider
from tests.admin_http_support import request as admin_request
from tests.conftest import TEST_HMAC_KEY

pytestmark = pytest.mark.integration

SCHEMA = "maskgw_etapa9_e2e"
TABLE = f"{SCHEMA}.cliente"
CPF = "11122233344"
TOKEN = "admin-token-para-teste-com-40-caracteres"
RULE_ID = "rul_" + "a" * 32

#: Config inicial ADOTADA: cpf mascarado por md5, com ID (revision 1).
INITIAL_CONFIG = f"""\
revision: 1
masking:
  - id: {RULE_ID}
    match: cpf
    transformer: md5
exceptions: []
database:
  statement_timeout_ms: 30000
  max_rows: 1000
sql:
  denied_functions: []
"""

DDL = f"""
DROP SCHEMA IF EXISTS {SCHEMA} CASCADE;
CREATE SCHEMA {SCHEMA};
CREATE TABLE {TABLE} (id integer PRIMARY KEY, cpf text);
INSERT INTO {TABLE} (id, cpf) VALUES (1, '{CPF}');
"""


@pytest.fixture
def database(dsn: str) -> Iterator[str]:
    with psycopg.connect(dsn, autocommit=True) as setup:
        setup.execute(DDL)
    try:
        yield dsn
    finally:
        with psycopg.connect(dsn, autocommit=True) as teardown:
            teardown.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "masking.yaml"
    path.write_text(INITIAL_CONFIG, encoding="utf-8")
    return path


def _secrets() -> MappingSecretProvider:
    return MappingSecretProvider({HMAC_KEY_ENV: TEST_HMAC_KEY})


def _build(config_file: Path, database: str) -> Application:
    """Aplicacao com HTTP administrativo E MCP, compartilhando o mesmo registry."""
    return build_application(
        config_path=config_file,
        conninfo=database,
        secrets=_secrets(),
        admin_http=AdminHttpSettings(token=TOKEN, host="127.0.0.1", port=0),
    )


def _mcp_call(app: Application, sql: str) -> Any:
    """Consulta pela tool MCP, cliente in-memory — o protocolo real."""

    async def run() -> Any:
        async with Client(build_mcp_server(app.gateway)) as client:
            return await client.call_tool("query_database", {"sql": sql})

    return anyio.run(run)


def _mcp_cpf(result: Any) -> tuple[str, str]:
    """Devolve `(celula_cpf, texto_bruto_da_resposta)` da tool MCP.

    O texto bruto e usado para provar que o valor original nunca aparece — em
    nenhum campo, nem no envelope inteiro da resposta.
    """
    payload = result.structured_content
    raw = json.dumps(payload) if payload is not None else result.content[0].text
    if payload is None:
        payload = json.loads(result.content[0].text)
    return str(payload["rows"][0][0]), raw


def _admin_put_config(port: int, revision: int) -> Any:
    """`PUT /admin/v1/config` autenticado, com o transformer de cpf trocado."""
    body = {
        "expected_revision": revision,
        "masking": [
            {
                "id": RULE_ID,
                "match": "cpf",
                "transformer": "fixed",
                "config": {"value": "[REDACTED]"},
            }
        ],
        "exceptions": [],
        "database": {"statement_timeout_ms": 30000, "max_rows": 1000},
        "sql": {"denied_functions": []},
    }
    return admin_request(
        port,
        "PUT",
        "/admin/v1/config",
        token=TOKEN,
        content_type="application/json",
        body=json.dumps(body).encode("utf-8"),
        timeout=30.0,
    )


# --------------------------------------------------------------------------
# 6.1 — PUT /admin/v1/config real, refletido na consulta MCP seguinte
# --------------------------------------------------------------------------


class TestPutConfigHttpRefletidoNaToolMCP:
    def test_put_config_pela_porta_admin_muda_o_masking_da_tool(
        self, database: str, config_file: Path
    ) -> None:
        app = _build(config_file, database)
        try:
            assert app.admin_http is not None
            port = app.admin_http.port
            query = f"SELECT cpf FROM {TABLE} WHERE id = 1"

            # Antes: cpf mascarado por md5 (revision 1). O valor original nunca
            # aparece nem aqui.
            before_cell, before_raw = _mcp_cpf(_mcp_call(app, query))
            assert before_cell == hashlib.md5(CPF.encode()).hexdigest()  # noqa: S324
            assert CPF not in before_raw

            # Escrita REAL pela porta administrativa: token, headers e payload.
            reply = _admin_put_config(port, revision=1)
            assert reply.status == 200
            assert reply.json() == {"revision": 2, "applied": True}

            # Depois, no MESMO processo, sem restart: a tool ve o runtime novo.
            after_cell, after_raw = _mcp_cpf(_mcp_call(app, query))
            assert after_cell == "[REDACTED]"
            # O valor original NUNCA apareceu na resposta MCP, nem antes nem depois.
            assert CPF not in after_raw
        finally:
            app.close()


# --------------------------------------------------------------------------
# 6.2 — o shutdown aguarda a escrita em voo, que termina com sucesso
# --------------------------------------------------------------------------


class TestShutdownAguardaEscrita:
    def test_escrita_em_voo_conclui_com_sucesso_antes_do_close(  # noqa: PLR0915 - orquestracao deterministica de threads/eventos
        self, database: str, config_file: Path
    ) -> None:
        """Uma escrita ja na secao critica quando o shutdown comeca TERMINA COM
        SUCESSO antes do fechamento dos recursos.

        Comportamento unico esperado, sem alternativas: a escrita recebe `200`, o
        arquivo persiste a revisao nova, `close()` so retorna depois disso, e nada
        administrativo sobrevive. A escrita e presa dentro da mutacao com um
        `Event`; `close()` faz `join` incondicional da thread HTTP.
        """
        app = _build(config_file, database)
        assert app.admin is not None
        assert app.admin_http is not None
        admin_service = app.admin
        port = app.admin_http.port

        entrou = threading.Event()
        liberar = threading.Event()
        escrita_terminou = threading.Event()
        write_status: dict[str, int] = {}

        def fire_write() -> None:
            reply = _admin_put_config(port, revision=1)
            write_status["status"] = reply.status
            escrita_terminou.set()

        # A mutacao prende a escrita: sinaliza que entrou e espera `liberar`. Roda
        # dentro da secao critica, na thread HTTP.
        original_apply = type(admin_service).apply
        holding = threading.Event()

        def blocking_apply(self: Any, mutation: Any, **kwargs: Any) -> Any:
            def wrapped(current: MaskingFileConfig) -> Any:
                if not holding.is_set():
                    holding.set()
                    entrou.set()
                    liberar.wait(timeout=30)
                return mutation(current)

            return original_apply(self, wrapped, **kwargs)

        stopped = threading.Event()
        closer: threading.Thread | None = None
        writer: threading.Thread | None = None

        try:
            with patch.object(type(admin_service), "apply", blocking_apply):
                writer = threading.Thread(target=fire_write, name="e2e-writer")
                writer.start()
                assert entrou.wait(timeout=30), "a escrita nao entrou na mutacao"

                def do_close() -> None:
                    app.close()
                    stopped.set()

                closer = threading.Thread(target=do_close, name="e2e-closer")
                closer.start()

                # `close()` NAO retorna enquanto a escrita esta presa.
                assert not stopped.wait(timeout=2.0), "close() retornou com escrita presa"
                assert closer.is_alive()
                assert not escrita_terminou.is_set()

                # Libera; agora a escrita conclui e close() retorna.
                liberar.set()
                assert stopped.wait(timeout=30), "close() nao concluiu apos liberar"
                assert escrita_terminou.wait(timeout=30)
                writer.join(timeout=30)
                closer.join(timeout=30)

            # A escrita em voo terminou com EXATAMENTE 200 — comportamento unico.
            assert write_status.get("status") == 200

            # O arquivo persistido contem exatamente a revisao/config nova.
            persisted = yaml.safe_load(config_file.read_text(encoding="utf-8"))
            assert persisted["revision"] == 2
            assert persisted["masking"][0]["transformer"] == "fixed"
            assert persisted["masking"][0]["config"]["value"] == "[REDACTED]"

            # Nenhuma das threads envolvidas segue viva.
            vivas = {t.name for t in threading.enumerate()}
            assert "maskgw-admin-http" not in vivas
            assert not writer.is_alive()
            assert not closer.is_alive()

            # Nenhuma escrita e aceita depois do shutdown: a porta esta fechada,
            # entao uma nova requisicao nem conecta.
            with pytest.raises(OSError):
                _admin_put_config(port, revision=2)

            # Nenhum trabalho administrativo continua: o servico recusa operacoes.
            assert admin_service.closed is True
        finally:
            liberar.set()
            if not stopped.is_set():
                app.close()
            if writer is not None:
                writer.join(timeout=10)
            if closer is not None:
                closer.join(timeout=10)
