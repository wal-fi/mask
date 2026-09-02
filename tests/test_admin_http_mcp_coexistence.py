"""Fase 7, Etapa 7: os dois planos vivos no mesmo processo (secoes 10.4, 12.6).

`stdout` e o canal do protocolo MCP. Qualquer byte escrito nele pelo uvicorn,
pelo `logging` ou por um handler de excecao **corrompe a sessao MCP**. Isso e
requisito com teste, e nao recomendacao.

O teste central deste arquivo sobe o processo de verdade —
`python -m maskgw.mcp`, com a Admin API habilitada por variavel de ambiente —,
abre uma sessao MCP real por stdio e, **enquanto ela esta aberta**, martela a
Admin API. Se um unico byte estranho aparecesse em `stdout`, o enquadramento
JSON-RPC quebraria e a sessao falharia: o proprio protocolo e o detector.

Rodar num subprocesso e o que torna este teste valido. Sob pytest, o
`LogCaptureHandler` e anexado a todo logger com `propagate=False` — inclusive
`uvicorn.access` —, e o uvicorn volta a emitir access log porque decide por
`hasHandlers()`. Aqui nao ha pytest do outro lado: o que se observa e o
processo como ele roda em producao.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import anyio
import psycopg
import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.types import CallToolResult, TextContent

import maskgw.bootstrap.main as main_module
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from tests.admin_http_support import TOKEN, free_port
from tests.conftest import TEST_HMAC_KEY

pytestmark = pytest.mark.integration

SCHEMA = "maskgw_fase7_http"
TABLE = f"{SCHEMA}.cliente"

NOME = "Joao"
CPF = "11122233344"

CONFIG = """
masking:
  - match: cpf
    transformer: hmac_sha256

database:
  statement_timeout_ms: 5000
  max_rows: 50
"""

DDL = f"""
DROP SCHEMA IF EXISTS {SCHEMA} CASCADE;
CREATE SCHEMA {SCHEMA};
CREATE TABLE {TABLE} (id int primary key, nome text, cpf text);
"""

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def database(dsn: str) -> Iterator[str]:
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(DDL)
        connection.execute(
            f"INSERT INTO {TABLE} (id, nome, cpf) VALUES (%s, %s, %s)",
            (1, NOME, CPF),
        )
    try:
        yield dsn
    finally:
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")


@pytest.fixture
def environment(database: str, tmp_path: Path) -> tuple[dict[str, str], int]:
    config = tmp_path / "masking.yaml"
    config.write_text(CONFIG, encoding="utf-8")

    port = free_port()
    env = os.environ.copy()
    env.update(
        {
            "MASKGW_CONFIG": str(config),
            "MASKGW_DATABASE_DSN": database,
            HMAC_KEY_ENV: TEST_HMAC_KEY,
            "MASKGW_ADMIN_ENABLED": "1",
            "MASKGW_ADMIN_TOKEN": TOKEN,
            "MASKGW_ADMIN_BIND": "127.0.0.1",
            "MASKGW_ADMIN_PORT": str(port),
            "PYTHONPATH": str(REPO_ROOT / "src"),
            # Sem isto o Python pode bufferizar e mascarar um byte perdido.
            "PYTHONUNBUFFERED": "1",
        }
    )
    return env, port


def admin_get(port: int, path: str, *, token: str | None = TOKEN) -> tuple[int, bytes]:
    """GET administrativo por `urllib`, para nao depender do apoio da suite."""
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        method="GET",
    )
    request.add_header("Host", f"127.0.0.1:{port}")
    if token is not None:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as error:
        return int(error.code), error.read()


def wait_for_port(port: int, *, timeout: float = 30.0) -> bool:
    deadline = threading.Event()
    waited = 0.0
    while waited < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            deadline.wait(0.05)
            waited += 0.05
    return False


class TestSessaoMcpComAdminAtivo:
    def test_uma_sessao_mcp_real_nao_ve_byte_estranho_em_stdout(
        self,
        environment: tuple[dict[str, str], int],
        tmp_path: Path,
    ) -> None:
        """O enquadramento JSON-RPC e o proprio detector.

        Um byte extra em `stdout` — uma linha do uvicorn, um `print`, um
        traceback — quebraria o parsing e a sessao falharia antes de qualquer
        asserta abaixo.
        """
        env, port = environment
        errlog_path = tmp_path / "stderr.txt"
        resultados: list[CallToolResult] = []
        respostas_admin: list[tuple[int, bytes]] = []

        async def run() -> None:
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "maskgw.mcp"],
                env=env,
                cwd=str(REPO_ROOT),
            )
            with errlog_path.open("w", encoding="utf-8") as errlog:
                async with (
                    stdio_client(parameters, errlog=errlog) as (read, write),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()

                    assert wait_for_port(port), "a Admin API nao subiu junto com o MCP"

                    # Carga administrativa CONCORRENTE com a sessao MCP: e
                    # exatamente a condicao em que um byte perdido apareceria.
                    def hammer() -> None:
                        for _ in range(15):
                            for path in (
                                "/admin/v1/status",
                                "/admin/v1/config",
                                "/admin/v1/rules",
                                "/admin/v1/protected",
                                "/admin/v1/inexistente",
                            ):
                                respostas_admin.append(admin_get(port, path))

                    worker = threading.Thread(target=hammer, name="admin-load")
                    worker.start()
                    try:
                        for _ in range(5):
                            resultados.append(
                                await session.call_tool(
                                    "query_database",
                                    {"sql": f"SELECT nome, cpf FROM {TABLE}"},
                                )
                            )
                    finally:
                        worker.join(timeout=60)
                        assert not worker.is_alive()

        anyio.run(run)

        # A sessao inteira funcionou: `stdout` carregou so o protocolo.
        assert len(resultados) == 5
        for resultado in resultados:
            assert resultado.is_error is not True
            rendered = "".join(
                block.text for block in resultado.content if isinstance(block, TextContent)
            )
            # O CPF original nao aparece; o nome, que nao casa regra, aparece.
            assert CPF not in rendered
            assert NOME in rendered

        # A carga administrativa foi atendida durante a sessao.
        assert len(respostas_admin) == 15 * 5
        assert {status for status, _body in respostas_admin} == {200, 404}

    def test_o_stderr_do_processo_carrega_so_metadata_fechada(
        self,
        environment: tuple[dict[str, str], int],
        tmp_path: Path,
    ) -> None:
        """Logs sao permitidos em `stderr`, mas nao os do uvicorn nem tracebacks."""
        env, port = environment
        errlog_path = tmp_path / "stderr.txt"

        async def run() -> None:
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "maskgw.mcp"],
                env=env,
                cwd=str(REPO_ROOT),
            )
            with errlog_path.open("w", encoding="utf-8") as errlog:
                async with (
                    stdio_client(parameters, errlog=errlog) as (read, write),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    assert wait_for_port(port)
                    for _ in range(10):
                        admin_get(port, "/admin/v1/status")
                        admin_get(port, "/admin/v1/status", token=None)
                    await session.call_tool(
                        "query_database",
                        {"sql": f"SELECT cpf FROM {TABLE}"},
                    )

        anyio.run(run)
        stderr = errlog_path.read_text(encoding="utf-8")

        # As duas linhas fechadas do startup, e nada alem.
        assert main_module.REVISION_LOADED_PREFIX in stderr
        assert f"{main_module.ADMIN_LISTENING_PREFIX}127.0.0.1:{port}" in stderr

        # Nem access log, nem traceback, nem segredo.
        for proibido in (
            "GET /admin",
            "HTTP/1.1",
            "Uvicorn running",
            "Traceback",
            TOKEN,
            TEST_HMAC_KEY,
            CPF,
            "SELECT",
        ):
            assert proibido not in stderr, f"{proibido!r} apareceu em stderr"

    def test_o_token_e_exigido_tambem_no_processo_real(
        self,
        environment: tuple[dict[str, str], int],
        tmp_path: Path,
    ) -> None:
        env, port = environment
        errlog_path = tmp_path / "stderr.txt"
        observado: list[tuple[int, bytes]] = []

        async def run() -> None:
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "maskgw.mcp"],
                env=env,
                cwd=str(REPO_ROOT),
            )
            with errlog_path.open("w", encoding="utf-8") as errlog:
                async with (
                    stdio_client(parameters, errlog=errlog) as (read, write),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    assert wait_for_port(port)
                    observado.append(admin_get(port, "/admin/v1/status", token=None))
                    observado.append(admin_get(port, "/admin/v1/status", token="errado"))
                    observado.append(admin_get(port, "/admin/v1/status"))

        anyio.run(run)

        assert [status for status, _body in observado] == [401, 401, 200]
        assert observado[0][1] == observado[1][1]

    def test_o_processo_encerra_sem_deixar_a_porta_aberta(
        self,
        environment: tuple[dict[str, str], int],
        tmp_path: Path,
    ) -> None:
        """Shutdown ordenado: a thread HTTP recebe `join` e o socket some."""
        env, port = environment
        errlog_path = tmp_path / "stderr.txt"

        async def run() -> None:
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "maskgw.mcp"],
                env=env,
                cwd=str(REPO_ROOT),
            )
            with errlog_path.open("w", encoding="utf-8") as errlog:
                async with (
                    stdio_client(parameters, errlog=errlog) as (read, write),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    assert wait_for_port(port)
                    assert admin_get(port, "/admin/v1/status")[0] == 200

        anyio.run(run)

        # O processo saiu; a porta precisa estar livre para outro servidor.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
            probe.listen(1)


class TestAdminDesabilitadoNoProcessoReal:
    def test_sem_a_variavel_nenhuma_porta_e_aberta(
        self,
        environment: tuple[dict[str, str], int],
        tmp_path: Path,
    ) -> None:
        """Admin desabilitado mantem exatamente o comportamento anterior."""
        env, port = environment
        env.pop("MASKGW_ADMIN_ENABLED")
        errlog_path = tmp_path / "stderr.txt"
        alcancavel: list[bool] = []

        async def run() -> None:
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "maskgw.mcp"],
                env=env,
                cwd=str(REPO_ROOT),
            )
            with errlog_path.open("w", encoding="utf-8") as errlog:
                async with (
                    stdio_client(parameters, errlog=errlog) as (read, write),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    alcancavel.append(wait_for_port(port, timeout=2.0))
                    result = await session.call_tool(
                        "query_database",
                        {"sql": f"SELECT cpf FROM {TABLE}"},
                    )
                    assert result.is_error is not True

        anyio.run(run)
        stderr = errlog_path.read_text(encoding="utf-8")

        assert alcancavel == [False]
        assert main_module.ADMIN_LISTENING_PREFIX not in stderr
        # E o arquivo de lock nunca chegou a existir: sem admin nao ha escrita.
        assert not (Path(env["MASKGW_CONFIG"]).parent / "masking.yaml.lock").exists()
