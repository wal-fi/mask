"""Fase 7, Etapa 7: as camadas de fronteira, exercitadas isoladamente.

Nenhuma rota desta etapa tem corpo, entao o limite de 1 MiB e a exigencia de
`Content-Type` **nao sao alcancaveis por endpoint de producao**. Registrar um
so para provoca-los criaria superficie que a especificacao nao pede, e o teste
de conjunto literal de rotas (secao 12.7) passaria a proteger uma rota
inventada pelo proprio teste.

A saida e exercitar os middlewares sobre uma aplicacao ASGI **interna a este
arquivo**: ela nao existe em `src/`, nao e registrada em lugar nenhum e some
com o teste.

Os testes que precisam do fio de verdade — chunked sem `Content-Length` — sobem
a pilha inteira num servidor real, ainda por cima da mesma app interna.
"""

from __future__ import annotations

import asyncio
import json
import tracemalloc
from typing import Any

import pytest
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from maskgw.admin.errors import CATEGORY_DETAILS, AdminErrorCategory
from maskgw.admin.http import (
    MAX_BODY_BYTES,
    AdminHttpServer,
    AuthenticationMiddleware,
    BodyLimitMiddleware,
    BoundaryMiddleware,
    BrowserOriginMiddleware,
    ContentTypeMiddleware,
    HostAllowlistMiddleware,
    allowed_hosts,
    install_error_handlers,
    wrap_boundary,
)
from maskgw.admin.http.responses import CLOSED_REASONS
from tests.admin_http_support import TOKEN, Reply, chunked_request, request

# --------------------------------------------------------------------------
# Aplicacao ASGI interna: existe SO neste arquivo
# --------------------------------------------------------------------------


class EchoApp:
    """Le o corpo inteiro e responde com quantos bytes recebeu.

    O contador e o instrumento central do teste de memoria: se o middleware
    bufferizasse, ou repassasse o chunk que estoura o limite, este numero
    passaria de `MAX_BODY_BYTES`.
    """

    def __init__(self) -> None:
        self.body_bytes = 0
        self.calls = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.calls += 1
        received = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            received += len(message.get("body", b""))
            if not message.get("more_body", False):
                break
        self.body_bytes = max(self.body_bytes, received)
        payload = json.dumps({"received": received}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": payload})


class ExplodingApp:
    """Levanta com uma mensagem cheia de coisa que nao pode vazar."""

    payload = "DSN=postgres://u:p@h/db SQL=SELECT cpf VALOR=11122233344"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        raise RuntimeError(self.payload)


class CorsLeakingApp:
    """Emite headers CORS de proposito, para provar que eles nao saem."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"access-control-allow-origin", b"*"),
                    (b"access-control-allow-credentials", b"true"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b"{}"})


def drive(
    app: ASGIApp,
    *,
    method: str = "GET",
    path: str = "/admin/v1/status",
    headers: list[tuple[bytes, bytes]] | None = None,
    chunks: list[bytes] | None = None,
) -> Reply:
    """Invoca a app ASGI direto, sem servidor. Deterministico e sem socket."""

    async def run() -> Reply:
        sent: list[Message] = []
        pending = list(chunks or [])

        async def receive() -> Message:
            if pending:
                body = pending.pop(0)
                return {"type": "http.request", "body": body, "more_body": bool(pending)}
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: Message) -> None:
            sent.append(message)

        scope: Scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": headers if headers is not None else [],
            "client": ("127.0.0.1", 1234),
            "server": ("127.0.0.1", 8765),
        }
        await app(scope, receive, send)

        status = 0
        response_headers: dict[str, str] = {}
        body = b""
        for message in sent:
            if message["type"] == "http.response.start":
                status = int(message["status"])
                response_headers = {
                    key.decode().lower(): value.decode() for key, value in message["headers"]
                }
            elif message["type"] == "http.response.body":
                body += message.get("body", b"")
        return Reply(status=status, headers=response_headers, body=body)

    return asyncio.run(run())


def base_headers(port: int = 8765, *, token: str | None = TOKEN) -> list[tuple[bytes, bytes]]:
    headers = [(b"host", f"127.0.0.1:{port}".encode())]
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    return headers


# --------------------------------------------------------------------------
# BoundaryMiddleware
# --------------------------------------------------------------------------


class TestBoundary:
    def test_no_store_em_resposta_de_sucesso(self) -> None:
        reply = drive(BoundaryMiddleware(EchoApp()))
        assert reply.status == 200
        assert reply.headers["cache-control"] == "no-store"

    def test_headers_cors_emitidos_por_dentro_nao_saem(self) -> None:
        """Nos nunca os adicionamos; apagar aqui torna isso uma garantia."""
        reply = drive(BoundaryMiddleware(CorsLeakingApp()))
        assert reply.status == 200
        assert reply.cors_headers == []

    def test_excecao_vira_internal_error_e_nao_sobe_para_o_servidor(self) -> None:
        """Sem esta contencao o uvicorn registraria o traceback com `exc_info`."""
        reply = drive(BoundaryMiddleware(ExplodingApp()))

        assert reply.status == 500
        assert reply.json() == {
            "error": "INTERNAL_ERROR",
            "detail": CATEGORY_DETAILS[AdminErrorCategory.INTERNAL_ERROR],
        }
        assert reply.headers["cache-control"] == "no-store"

    def test_a_mensagem_original_nao_aparece_em_lugar_nenhum(self) -> None:
        reply = drive(BoundaryMiddleware(ExplodingApp()))
        rendered = reply.text() + repr(reply.headers)

        for fragment in ("postgres://", "SELECT cpf", "11122233344", "Traceback", "RuntimeError"):
            assert fragment not in rendered

    def test_cancelamento_nao_e_engolido(self) -> None:
        """Engolir `CancelledError` quebraria o desligamento do proprio servidor."""

        class Cancelling:
            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            drive(BoundaryMiddleware(Cancelling()))

    def test_scope_nao_http_passa_direto(self) -> None:
        """`lifespan` nao pode ser tocado por uma camada de fronteira HTTP."""
        seen: list[str] = []

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            seen.append(scope["type"])

        async def run() -> None:
            await BoundaryMiddleware(app)({"type": "lifespan"}, _noop_receive, _noop_send)

        asyncio.run(run())
        assert seen == ["lifespan"]


async def _noop_receive() -> Message:  # pragma: no cover - nunca consumido
    return {"type": "http.request", "body": b"", "more_body": False}


async def _noop_send(_message: Message) -> None:  # pragma: no cover - nunca consumido
    return None


# --------------------------------------------------------------------------
# Host, Origin e Referer
# --------------------------------------------------------------------------


class TestHostAllowlist:
    def test_as_tres_formas_canonicas(self) -> None:
        assert allowed_hosts(8765) == {"127.0.0.1:8765", "localhost:8765", "[::1]:8765"}

    @pytest.mark.parametrize("host", ["127.0.0.1:8765", "localhost:8765", "[::1]:8765"])
    def test_host_da_allowlist_passa(self, host: str) -> None:
        app = HostAllowlistMiddleware(EchoApp(), port=8765)
        reply = drive(app, headers=[(b"host", host.encode())])
        assert reply.status == 200

    def test_localhost_em_maiusculas_passa(self) -> None:
        app = HostAllowlistMiddleware(EchoApp(), port=8765)
        reply = drive(app, headers=[(b"host", b"LocalHost:8765")])
        assert reply.status == 200

    @pytest.mark.parametrize(
        "host",
        [
            "evil.example:8765",
            "attacker.test",
            "127.0.0.1",
            "127.0.0.1:9999",
            "localhost",
            "127.0.0.1:8765.evil.example",
            "",
            "0.0.0.0:8765",
        ],
    )
    def test_host_alheio_e_400(self, host: str) -> None:
        """Fecha DNS rebinding: o nome resolve para loopback, o `Host` nao."""
        app = BoundaryMiddleware(HostAllowlistMiddleware(EchoApp(), port=8765))
        reply = drive(app, headers=[(b"host", host.encode())])

        assert reply.status == 400
        assert reply.json()["error"] == "HOST_NOT_ALLOWED"
        assert reply.headers["cache-control"] == "no-store"

    def test_host_ausente_e_400(self) -> None:
        app = BoundaryMiddleware(HostAllowlistMiddleware(EchoApp(), port=8765))
        assert drive(app, headers=[]).status == 400

    def test_o_corpo_do_erro_nao_repete_o_host_recebido(self) -> None:
        app = BoundaryMiddleware(HostAllowlistMiddleware(EchoApp(), port=8765))
        reply = drive(app, headers=[(b"host", b"marcador-de-host-alheio")])
        assert "marcador-de-host-alheio" not in reply.text()


class TestBrowserOrigin:
    @pytest.mark.parametrize("header", [b"origin", b"referer"])
    def test_presenca_e_403(self, header: bytes) -> None:
        app = BoundaryMiddleware(BrowserOriginMiddleware(EchoApp()))
        reply = drive(app, headers=[(header, b"http://evil.example")])

        assert reply.status == 403
        assert reply.json()["error"] == "CROSS_ORIGIN_REJECTED"

    @pytest.mark.parametrize("value", [b"", b"null", b"http://127.0.0.1:8765"])
    def test_recusa_pela_PRESENCA_e_nao_pelo_valor(self, value: bytes) -> None:
        """Comparar o valor seria CORS por outro nome (secao 3.2).

        Inclusive uma origem que aponta para o proprio servidor e recusada: se
        ela fosse aceita, bastaria ao atacante forja-la.
        """
        app = BoundaryMiddleware(BrowserOriginMiddleware(EchoApp()))
        assert drive(app, headers=[(b"origin", value)]).status == 403

    def test_ausencia_dos_dois_passa(self) -> None:
        app = BrowserOriginMiddleware(EchoApp())
        assert drive(app, headers=[(b"user-agent", b"curl/8")]).status == 200

    def test_o_corpo_do_erro_nao_repete_a_origem(self) -> None:
        app = BoundaryMiddleware(BrowserOriginMiddleware(EchoApp()))
        reply = drive(app, headers=[(b"origin", b"http://marcador-de-origem")])
        assert "marcador-de-origem" not in reply.text()


# --------------------------------------------------------------------------
# Autenticacao
# --------------------------------------------------------------------------


class TestAuthentication:
    def test_bearer_correto_passa(self) -> None:
        app = AuthenticationMiddleware(EchoApp(), token=TOKEN)
        reply = drive(app, headers=[(b"authorization", f"Bearer {TOKEN}".encode())])
        assert reply.status == 200

    def test_esquema_e_case_insensitive(self) -> None:
        app = AuthenticationMiddleware(EchoApp(), token=TOKEN)
        reply = drive(app, headers=[(b"authorization", f"bEaReR {TOKEN}".encode())])
        assert reply.status == 200

    @pytest.mark.parametrize(
        "header",
        [
            None,
            b"",
            b"Bearer",
            b"Bearer ",
            b"Bearer errado",
            b"Basic " + TOKEN.encode(),
            TOKEN.encode(),
            b"Bearer " + TOKEN.encode() + b"x",
            b"Bearer " + TOKEN.encode()[:-1],
            b"Token " + TOKEN.encode(),
        ],
    )
    def test_ausente_malformado_e_errado_sao_o_MESMO_401(self, header: bytes | None) -> None:
        """Uma resposta que distinguisse os casos ja seria meio oraculo."""
        app = BoundaryMiddleware(AuthenticationMiddleware(EchoApp(), token=TOKEN))
        headers = [] if header is None else [(b"authorization", header)]
        reply = drive(app, headers=headers)

        assert reply.status == 401
        assert reply.json() == {
            "error": "UNAUTHORIZED",
            "detail": CATEGORY_DETAILS[AdminErrorCategory.UNAUTHORIZED],
        }

    def test_nenhuma_resposta_de_401_revela_nada_do_token(self) -> None:
        app = BoundaryMiddleware(AuthenticationMiddleware(EchoApp(), token=TOKEN))
        reply = drive(app, headers=[(b"authorization", b"Bearer errado")])
        rendered = reply.text() + repr(reply.headers)

        assert TOKEN not in rendered
        assert TOKEN[:8] not in rendered
        assert str(len(TOKEN)) not in rendered

    def test_a_app_protegida_nao_e_chamada_sem_token(self) -> None:
        echo = EchoApp()
        drive(BoundaryMiddleware(AuthenticationMiddleware(echo, token=TOKEN)), headers=[])
        assert echo.calls == 0

    def test_token_com_caractere_nao_ascii_nao_quebra_a_comparacao(self) -> None:
        """`hmac.compare_digest` sobre `str` recusa nao-ASCII; usamos bytes."""
        app = BoundaryMiddleware(AuthenticationMiddleware(EchoApp(), token=TOKEN))
        reply = drive(app, headers=[(b"authorization", "Bearer çãé".encode())])
        assert reply.status == 401

    def test_o_modulo_usa_compare_digest(self) -> None:
        """A comparacao precisa ser de tempo constante (secao 2)."""
        import inspect

        from maskgw.admin.http import middleware

        source = inspect.getsource(middleware.AuthenticationMiddleware)
        assert "hmac.compare_digest" in source
        assert "==" not in source.split("_authorized")[-1].replace("!=", "")


# --------------------------------------------------------------------------
# Content-Type
# --------------------------------------------------------------------------


class TestContentType:
    @pytest.mark.parametrize("method", ["GET", "HEAD"])
    def test_metodo_sem_corpo_nao_exige_content_type(self, method: str) -> None:
        """Secao 12.7: `GET` sem `Content-Type` responde 200."""
        app = ContentTypeMiddleware(EchoApp())
        assert drive(app, method=method).status == 200

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    @pytest.mark.parametrize(
        "content_type",
        [None, b"text/plain", b"application/x-www-form-urlencoded", b"multipart/form-data"],
    )
    def test_metodo_com_corpo_sem_json_e_415(self, method: str, content_type: bytes | None) -> None:
        """Um `<form>` HTML so emite estes tres tipos: e a camada 3 da secao 3.3."""
        app = BoundaryMiddleware(ContentTypeMiddleware(EchoApp()))
        headers = [] if content_type is None else [(b"content-type", content_type)]
        reply = drive(app, method=method, headers=headers)

        assert reply.status == 415
        assert reply.json()["error"] == "UNSUPPORTED_MEDIA_TYPE"

    @pytest.mark.parametrize(
        "content_type",
        [b"application/json", b"application/json; charset=utf-8", b"APPLICATION/JSON"],
    )
    def test_json_com_parametros_e_aceito(self, content_type: bytes) -> None:
        app = ContentTypeMiddleware(EchoApp())
        reply = drive(app, method="POST", headers=[(b"content-type", content_type)])
        assert reply.status == 200

    def test_a_app_protegida_nao_e_chamada_com_tipo_errado(self) -> None:
        echo = EchoApp()
        drive(
            BoundaryMiddleware(ContentTypeMiddleware(echo)),
            method="POST",
            headers=[(b"content-type", b"text/plain")],
        )
        assert echo.calls == 0


# --------------------------------------------------------------------------
# Limite de corpo
# --------------------------------------------------------------------------


class TestBodyLimit:
    def test_o_limite_e_1_mib(self) -> None:
        assert MAX_BODY_BYTES == 1024 * 1024

    def test_corpo_dentro_do_limite_chega_inteiro(self) -> None:
        echo = EchoApp()
        size = 4096
        reply = drive(
            BodyLimitMiddleware(echo),
            method="POST",
            chunks=[b"y" * size],
            headers=[(b"content-length", str(size).encode())],
        )
        assert reply.status == 200
        assert echo.body_bytes == size

    def test_content_length_acima_do_limite_falha_ANTES_de_ler(self) -> None:
        """A recusa vem do header: nem um byte do corpo e consumido."""
        echo = EchoApp()
        app = BoundaryMiddleware(BodyLimitMiddleware(echo))
        reply = drive(
            app,
            method="POST",
            headers=[(b"content-length", str(MAX_BODY_BYTES + 1).encode())],
            chunks=[b"z" * 4096],
        )

        assert reply.status == 413
        assert reply.json()["error"] == "PAYLOAD_TOO_LARGE"
        assert echo.calls == 0
        assert echo.body_bytes == 0

    def test_content_length_exatamente_no_limite_passa(self) -> None:
        app = BodyLimitMiddleware(EchoApp())
        reply = drive(
            app,
            method="POST",
            headers=[(b"content-length", str(MAX_BODY_BYTES).encode())],
            chunks=[b"w" * 1024],
        )
        assert reply.status == 200

    def test_streaming_sem_content_length_e_cortado_no_limite(self) -> None:
        """Sem `Content-Length` o tamanho so se conhece recebendo."""
        echo = EchoApp()
        app = BoundaryMiddleware(BodyLimitMiddleware(echo))
        chunk = b"q" * (64 * 1024)
        chunks = [chunk] * 100  # ~6.4 MiB

        reply = drive(app, method="POST", chunks=chunks)

        assert reply.status == 413
        assert reply.json()["error"] == "PAYLOAD_TOO_LARGE"

    def test_o_chunk_que_estoura_o_limite_NAO_e_repassado(self) -> None:
        """E esta a propriedade de memoria: nada alem do limite existe embaixo."""
        echo = EchoApp()
        app = BoundaryMiddleware(BodyLimitMiddleware(echo))
        chunk = b"q" * (64 * 1024)

        drive(app, method="POST", chunks=[chunk] * 100)

        assert echo.body_bytes <= MAX_BODY_BYTES

    def test_a_memoria_do_processo_nao_acompanha_o_envio(self) -> None:
        """8 MiB enviados, e o pico rastreado fica na ordem do limite.

        A margem e generosa de proposito — o objetivo e detectar bufferizacao
        do corpo inteiro, nao medir alocacao com precisao.
        """
        echo = EchoApp()
        app = BoundaryMiddleware(BodyLimitMiddleware(echo))
        chunk = b"q" * (64 * 1024)
        chunks = [chunk] * 128  # 8 MiB

        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            drive(app, method="POST", chunks=chunks)
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        assert peak < 4 * MAX_BODY_BYTES, f"pico de {peak} bytes sugere bufferizacao"

    def test_content_length_ilegivel_nao_e_lido_como_cabe(self) -> None:
        app = BodyLimitMiddleware(EchoApp())
        reply = drive(
            app,
            method="POST",
            headers=[(b"content-length", b"nao-e-numero")],
            chunks=[b"k" * 16],
        )
        # Nao ha recusa pelo header; o corte por contagem continua valendo.
        assert reply.status == 200


# --------------------------------------------------------------------------
# A pilha inteira, e a ordem entre as camadas
# --------------------------------------------------------------------------


class TestStackOrder:
    def stack(self, app: ASGIApp | None = None) -> ASGIApp:
        return wrap_boundary(app if app is not None else EchoApp(), token=TOKEN, port=8765)

    def test_host_alheio_vence_a_ausencia_de_token(self) -> None:
        """`Host` e `Origin` sao propriedades da requisicao, nao da credencial."""
        reply = drive(self.stack(), headers=[(b"host", b"evil.example:8765")])
        assert reply.status == 400

    def test_origin_vence_a_ausencia_de_token(self) -> None:
        reply = drive(
            self.stack(),
            headers=[(b"host", b"127.0.0.1:8765"), (b"origin", b"http://evil")],
        )
        assert reply.status == 403

    def test_401_vem_ANTES_do_415(self) -> None:
        """Sem credencial valida, nada do corpo e sequer classificado."""
        reply = drive(
            self.stack(),
            method="POST",
            headers=[(b"host", b"127.0.0.1:8765"), (b"content-type", b"text/plain")],
        )
        assert reply.status == 401

    def test_413_por_content_length_vem_ANTES_do_401(self) -> None:
        """Um corpo declarado gigante nao deve nem chegar a ser autenticado."""
        reply = drive(
            self.stack(),
            method="POST",
            headers=[
                (b"host", b"127.0.0.1:8765"),
                (b"content-length", str(MAX_BODY_BYTES + 1).encode()),
            ],
        )
        assert reply.status == 413

    def test_todas_as_recusas_carregam_no_store_e_nenhum_header_cors(self) -> None:
        cases = [
            ([(b"host", b"evil:1")], 400),
            ([(b"host", b"127.0.0.1:8765"), (b"origin", b"http://e")], 403),
            ([(b"host", b"127.0.0.1:8765")], 401),
        ]
        for headers, expected in cases:
            reply = drive(self.stack(), headers=headers)
            assert reply.status == expected
            assert reply.headers["cache-control"] == "no-store"
            assert reply.cors_headers == []


# --------------------------------------------------------------------------
# Chunked de verdade, sobre um servidor de verdade
# --------------------------------------------------------------------------


class TestChunkedOverTheWire:
    @pytest.fixture
    def echo_server(self) -> Any:
        echo = EchoApp()
        server = AdminHttpServer(
            app_factory=lambda port: wrap_boundary(echo, token=TOKEN, port=port),
            host="127.0.0.1",
            port=0,
        )
        server.start()
        try:
            yield server, echo
        finally:
            server.stop()

    def test_corpo_chunked_de_varios_mib_e_cortado_com_413(self, echo_server: Any) -> None:
        """Sem `Content-Length`, com 8 MiB enviados em chunks de 64 KiB."""
        server, echo = echo_server
        reply = chunked_request(server.port, total_bytes=8 * 1024 * 1024)

        assert reply.status == 413
        assert reply.json()["error"] == "PAYLOAD_TOO_LARGE"
        assert reply.headers["cache-control"] == "no-store"
        assert echo.body_bytes <= MAX_BODY_BYTES

    def test_corpo_chunked_dentro_do_limite_chega_inteiro(self, echo_server: Any) -> None:
        server, echo = echo_server
        size = 256 * 1024
        reply = chunked_request(server.port, total_bytes=size)

        assert reply.status == 200
        assert echo.body_bytes == size

    def test_o_servidor_continua_atendendo_depois_de_um_413(self, echo_server: Any) -> None:
        """Cortar um corpo grande nao pode derrubar a thread HTTP."""
        server, _echo = echo_server
        chunked_request(server.port, total_bytes=4 * 1024 * 1024)

        assert request(server.port, "GET", "/qualquer").status == 200


# --------------------------------------------------------------------------
# Handlers de erro (secao 10.3), sobre uma app de teste
# --------------------------------------------------------------------------


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    size: int


class TestErrorHandlers:
    """`RequestValidationError` nao e alcancavel pelas rotas desta etapa.

    Nenhuma delas tem corpo, e os path params sao `str` livres — um ID
    malformado vira `NOT_FOUND`, e nao `422`. O handler existe mesmo assim
    (secao 10.3 o exige), e e exercitado aqui sobre uma app de teste.
    """

    @pytest.fixture
    def app(self) -> ASGIApp:
        application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        install_error_handlers(application)

        @application.post("/echo")
        async def echo(payload: Payload) -> dict[str, str]:  # pragma: no cover - via HTTP
            return {"name": payload.name}

        return wrap_boundary(application, token=TOKEN, port=8765)

    def run(self, app: ASGIApp, body: bytes) -> Reply:
        return drive(
            app,
            method="POST",
            path="/echo",
            headers=[
                (b"host", b"127.0.0.1:8765"),
                (b"authorization", f"Bearer {TOKEN}".encode()),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
            chunks=[body],
        )

    def test_campo_desconhecido_vira_unknown_field(self, app: ASGIApp) -> None:
        reply = self.run(app, b'{"name":"a","size":1,"extra":"x"}')

        assert reply.status == 422
        payload = reply.json()
        assert payload["error"] == "SCHEMA_INVALID"
        assert {item["reason"] for item in payload["fields"]} <= CLOSED_REASONS
        assert any(item["reason"] == "unknown_field" for item in payload["fields"])

    def test_campo_ausente_vira_missing(self, app: ASGIApp) -> None:
        reply = self.run(app, b'{"name":"a"}')
        payload = reply.json()

        assert reply.status == 422
        assert any(
            item["reason"] == "missing" and item["path"].endswith("size")
            for item in payload["fields"]
        )

    def test_tipo_errado_vira_wrong_type(self, app: ASGIApp) -> None:
        reply = self.run(app, b'{"name":"a","size":"nao-e-inteiro"}')
        payload = reply.json()

        assert reply.status == 422
        assert any(item["reason"] == "wrong_type" for item in payload["fields"])

    def test_o_valor_rejeitado_NUNCA_aparece_no_corpo(self, app: ASGIApp) -> None:
        """O handler default do FastAPI inclui `input`; e por isso que ele sai.

        Um `fixed.value` ou um `regex.replacement` recusado voltaria no corpo do
        erro e dali para o log do cliente (secao 4.5).
        """
        marcador = "11122233344-valor-que-nao-pode-voltar"
        reply = self.run(app, f'{{"name":"a","size":"{marcador}"}}'.encode())

        assert reply.status == 422
        assert marcador not in reply.text()
        assert "input" not in reply.text()
        assert "ctx" not in reply.text()

    def test_todo_reason_pertence_ao_conjunto_fechado(self, app: ASGIApp) -> None:
        bodies = [
            b"{}",
            b'{"name":1,"size":"x"}',
            b'{"name":"a","size":1,"a":1,"b":2}',
            b"[]",
            b'"texto"',
        ]
        for body in bodies:
            payload = self.run(app, body).json()
            for item in payload.get("fields", []):
                assert item["reason"] in CLOSED_REASONS

    def test_json_malformado_nao_devolve_o_texto_do_parser(self, app: ASGIApp) -> None:
        reply = self.run(app, b'{"name": marcador-invalido')

        assert reply.status == 422
        assert "marcador-invalido" not in reply.text()
        assert "Expecting" not in reply.text()
