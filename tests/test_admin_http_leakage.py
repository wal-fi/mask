"""Fase 7, Etapa 7: vazamento pela fronteira HTTP (secao 12.6).

O que nunca pode aparecer em corpo, header, `repr` ou registro: o token
administrativo, a chave HMAC, o DSN, valores de dados, SQL, caminhos de arquivo,
`str(exc)`, traceback e cadeia de excecao.

Os caminhos de ERRO recebem a mesma atencao dos de sucesso. Historicamente e
neles que o vazamento aparece: o handler default do FastAPI para
`RequestValidationError` inclui o `input` rejeitado, e um `Exception` sem
handler faz o servidor registrar o traceback inteiro.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.types import Receive, Scope, Send

from maskgw.admin.errors import CATEGORY_DETAILS, AdminErrorCategory
from maskgw.admin.http import AdminHttpServer, build_admin_app, wrap_boundary
from maskgw.secretsource import MappingSecretProvider
from tests.admin_http_support import (
    DSN_PARTS,
    SENSITIVE_DSN,
    SENSITIVE_HMAC,
    SENSITIVE_SQL,
    SENSITIVE_VALUE,
    TOKEN,
    Harness,
    build_service,
    request,
)

#: Tudo o que nao pode atravessar, em nenhuma forma.
SECRETS = (TOKEN, SENSITIVE_DSN, SENSITIVE_HMAC, SENSITIVE_VALUE, *DSN_PARTS)

#: Os segredos cujos PEDACOS tambem sao procurados. O DSN inteiro fica de fora
#: desta lista porque seus 8 primeiros caracteres sao `postgres`, que aparece
#: legitimamente em `statement_timeout_enforced_by`; as partes secretas dele
#: entram, e sao elas que realmente identificariam um vazamento.
SECRET_FRAGMENTS = (TOKEN, SENSITIVE_HMAC, SENSITIVE_VALUE, *DSN_PARTS)

#: Caminho de arquivo, texto de excecao e nomes internos tambem nao saem.
INTERNALS = (
    "Traceback",
    "masking.yaml",
    "psycopg",
    "PostgresAdapter",
    "AdminConfigService",
    "RuntimeRegistry",
    "site-packages",
)


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    state = build_service(
        tmp_path,
        secrets=MappingSecretProvider({"MASKGW_HMAC_KEY": SENSITIVE_HMAC}),
    )
    state.start()
    try:
        yield state
    finally:
        state.close()


def every_response(harness: Harness) -> list[tuple[str, str]]:
    """Sucesso e erro, o corpo e os headers de cada um, como texto."""
    replies = [
        request(harness.port, "GET", "/admin/v1/status"),
        request(harness.port, "GET", "/admin/v1/config"),
        request(harness.port, "GET", "/admin/v1/rules"),
        request(harness.port, "GET", "/admin/v1/exceptions"),
        request(harness.port, "GET", "/admin/v1/transformers"),
        request(harness.port, "GET", "/admin/v1/protected"),
        request(harness.port, "GET", "/admin/v1/rules/rul_inexistente"),
        request(harness.port, "GET", "/admin/v1/nao-existe"),
        request(harness.port, token=None),
        request(harness.port, token="errado"),
        request(harness.port, host="evil.example:1"),
        request(harness.port, headers={"Origin": "http://evil"}),
        request(harness.port, "OPTIONS", "/admin/v1/status"),
        request(harness.port, "POST", "/admin/v1/config", content_type="text/plain", body=b"x"),
        request(
            harness.port,
            "POST",
            "/admin/v1/config",
            content_type="application/json",
            body=b"y" * (1024 * 1024 + 1),
        ),
    ]
    return [(reply.text(), repr(reply.headers)) for reply in replies]


class TestSecretsNuncaAparecem:
    def test_nenhum_secret_em_corpo_ou_header_de_nenhuma_resposta(
        self,
        harness: Harness,
    ) -> None:
        for body, headers in every_response(harness):
            for secret in SECRETS:
                assert secret not in body
                assert secret not in headers

    def test_nenhum_derivado_de_secret_aparece(self, harness: Harness) -> None:
        """Nem tamanho, nem prefixo, nem sufixo, nem hash (secao 11.1)."""
        for body, headers in every_response(harness):
            rendered = body + headers
            for secret in SECRET_FRAGMENTS:
                assert secret[:8] not in rendered
                assert secret[-8:] not in rendered
            for secret in SECRETS:
                assert hashlib.sha256(secret.encode()).hexdigest() not in rendered
                assert hashlib.sha1(secret.encode()).hexdigest() not in rendered
                assert hashlib.md5(secret.encode(), usedforsecurity=False).hexdigest() not in (
                    rendered
                )

    def test_nenhum_detalhe_interno_aparece(self, harness: Harness) -> None:
        for body, headers in every_response(harness):
            rendered = body + headers
            for fragment in INTERNALS:
                assert fragment not in rendered

    def test_nenhuma_resposta_carrega_sql_de_consulta(self, harness: Harness) -> None:
        """A Admin API nao executa SQL, e nao devolve SQL de consulta (D-049).

        `GET /admin/v1/protected` cita `SELECT` em texto FIXO de politica — "the
        root node must be a SELECT statement" —, e isso e a descricao da regra
        do validator, nao a consulta de ninguem. O que nao pode aparecer e uma
        consulta concreta, com predicado e valor.
        """
        for body, _headers in every_response(harness):
            assert SENSITIVE_SQL not in body
            assert "FROM cliente" not in body
            assert "WHERE" not in body

    def test_o_caminho_do_arquivo_de_configuracao_nunca_sai(self, harness: Harness) -> None:
        caminho = str(harness.config_path)
        for body, headers in every_response(harness):
            assert caminho not in body + headers
            assert str(harness.config_path.parent) not in body + headers


class TestReprs:
    def test_repr_do_servico_nao_carrega_segredo(self, harness: Harness) -> None:
        rendered = repr(harness.service)
        for secret in (*SECRETS, str(harness.config_path)):
            assert secret not in rendered

    def test_repr_do_registry_e_do_runtime_nao_carregam_segredo(self, harness: Harness) -> None:
        rendered = f"{harness.registry!r} {harness.registry.current!r}"
        for secret in SECRETS:
            assert secret not in rendered

    def test_repr_do_store_nao_carrega_caminho(self, harness: Harness) -> None:
        assert str(harness.config_path) not in repr(harness.store)

    def test_repr_do_servidor_nao_carrega_token(self, harness: Harness) -> None:
        assert harness.server is not None
        assert TOKEN not in repr(harness.server)


class TestExcecaoInterna:
    """Uma excecao com DSN, SQL, valor e caminho na mensagem nao pode vazar."""

    @pytest.fixture
    def exploding_server(self) -> Iterator[AdminHttpServer]:
        payload = f"{SENSITIVE_DSN} {SENSITIVE_SQL} {SENSITIVE_VALUE} {SENSITIVE_HMAC} {TOKEN}"

        class Exploding:
            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                raise RuntimeError(payload)

        server = AdminHttpServer(
            app_factory=lambda port: wrap_boundary(Exploding(), token=TOKEN, port=port),
            host="127.0.0.1",
            port=0,
        )
        server.start()
        try:
            yield server
        finally:
            server.stop()

    def test_erro_inesperado_vira_INTERNAL_ERROR_sanitizado(
        self,
        exploding_server: AdminHttpServer,
    ) -> None:
        reply = request(exploding_server.port, "GET", "/qualquer")

        assert reply.status == 500
        assert reply.json() == {
            "error": "INTERNAL_ERROR",
            "detail": CATEGORY_DETAILS[AdminErrorCategory.INTERNAL_ERROR],
        }

    def test_nada_da_mensagem_original_atravessa(
        self,
        exploding_server: AdminHttpServer,
    ) -> None:
        reply = request(exploding_server.port, "GET", "/qualquer")
        rendered = reply.text() + repr(reply.headers)

        for secret in (*SECRETS, SENSITIVE_SQL, "RuntimeError", "Traceback", 'File "'):
            assert secret not in rendered

    def test_o_erro_500_tambem_carrega_no_store_e_nenhum_cors(
        self,
        exploding_server: AdminHttpServer,
    ) -> None:
        reply = request(exploding_server.port, "GET", "/qualquer")

        assert reply.headers["cache-control"] == "no-store"
        assert reply.cors_headers == []

    def test_o_servidor_nao_registra_o_traceback(
        self,
        exploding_server: AdminHttpServer,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Sem a contencao, o uvicorn logaria com `exc_info` (secao 10.4)."""
        with caplog.at_level(logging.DEBUG):
            request(exploding_server.port, "GET", "/qualquer")

        registrado = "\n".join(record.getMessage() for record in caplog.records)
        for secret in (*SECRETS, SENSITIVE_SQL):
            assert secret not in registrado
        assert not any(record.exc_info for record in caplog.records)

    def test_o_servidor_continua_de_pe_depois_da_excecao(
        self,
        exploding_server: AdminHttpServer,
    ) -> None:
        """Uma excecao contida nao pode derrubar a thread administrativa."""
        for _ in range(5):
            assert request(exploding_server.port, "GET", "/qualquer").status == 500
        assert exploding_server.running


class TestNenhumRegistroDuranteLeitura:
    def test_as_rotas_de_leitura_nao_escrevem_em_stdout_stderr_nem_logging(
        self,
        harness: Harness,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """`stdout` e do protocolo MCP; nada do admin pode toca-lo (secao 10.4)."""
        with caplog.at_level(logging.DEBUG):
            for path in (
                "/admin/v1/status",
                "/admin/v1/config",
                "/admin/v1/rules",
                "/admin/v1/protected",
                "/admin/v1/nao-existe",
            ):
                request(harness.port, "GET", path)

        captured = capsys.readouterr()
        assert captured.out == ""
        assert [record for record in caplog.records if record.name.startswith("maskgw")] == []

    def test_o_access_log_esta_desligado_na_configuracao(self, harness: Harness) -> None:
        """O `uvicorn.access` fica sem handler e sem propagacao.

        **Este teste nao conta registros capturados, e a razao importa.** O
        pytest, ao instalar seu `LogCaptureHandler`, o anexa deliberadamente a
        todo logger com `propagate=False` — justamente para nao perder os
        loggers isolados (`_pytest/logging.py`, `catching_logs.__enter__`).
        Isso poe um handler em `uvicorn.access`, e o uvicorn decide emitir ou
        nao o access log com `access_logger.hasHandlers()`, avaliado por
        conexao. Ou seja: **sob pytest, o access log volta a existir**, por
        instrumentacao do proprio runner.

        A propriedade do PRODUTO e a configuracao — sem handler proprio e sem
        propagacao —, e e ela que este teste afirma. Que nada saia de fato e
        verificado onde a instrumentacao nao alcanca: num subprocesso real, em
        `test_admin_http_mcp_coexistence.py`.
        """
        access_logger = logging.getLogger("uvicorn.access")
        nossos = [
            handler
            for handler in access_logger.handlers
            if type(handler).__module__.startswith(("uvicorn", "maskgw"))
        ]

        assert access_logger.propagate is False
        assert nossos == []
        assert request(harness.port, "GET", "/admin/v1/status").status == 200


class TestCorpoDeErroFechado:
    def test_todo_corpo_de_erro_so_tem_chaves_do_conjunto_previsto(
        self,
        harness: Harness,
    ) -> None:
        permitidas = {"error", "detail", "applied", "current_revision", "fields"}
        for body, _headers in every_response(harness):
            payload = json.loads(body)
            if "error" not in payload:
                continue
            assert set(payload) <= permitidas

    def test_todo_detail_e_o_texto_FIXO_da_categoria(self, harness: Harness) -> None:
        for body, _headers in every_response(harness):
            payload = json.loads(body)
            if "error" not in payload:
                continue
            categoria = AdminErrorCategory(payload["error"])
            assert payload["detail"] == CATEGORY_DETAILS[categoria]

    def test_nenhuma_categoria_de_erro_e_inventada(self, harness: Harness) -> None:
        for body, _headers in every_response(harness):
            payload = json.loads(body)
            if "error" in payload:
                assert payload["error"] in {item.value for item in AdminErrorCategory}


class TestSuperficieDoApp:
    def test_o_repr_do_app_nao_carrega_o_token(self, tmp_path: Path) -> None:
        state = build_service(tmp_path)
        try:
            app: Any = build_admin_app(
                state.service,
                token=TOKEN,
                port=8765,
                secrets=MappingSecretProvider({}),
                database_dsn_env="MASKGW_DATABASE_DSN",
            )
            assert TOKEN not in repr(app)
        finally:
            state.close()
