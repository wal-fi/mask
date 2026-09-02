"""Fronteira HTTP: as camadas que decidem antes de qualquer rota existir.

Todas sao middleware ASGI **puro**. Nenhuma usa `BaseHTTPMiddleware`, e a razao
e concreta: `BaseHTTPMiddleware` materializa a requisicao num objeto `Request` e
introduz um task group por chamada. O limite de corpo desta etapa precisa cortar
um envio chunked **enquanto ele chega**, sem bufferizar — e isso exige tocar o
`receive` cru.

## A ordem, e por que e esta

```text
1. BoundaryMiddleware        no-store em TUDO; nenhum header CORS sai;
                             nenhuma excecao chega ao servidor
2. HostAllowlistMiddleware   Host alheio            -> 400
3. BrowserOriginMiddleware   Origin/Referer presente-> 403
4. BodyLimitMiddleware       corpo > 1 MiB          -> 413
5. AuthenticationMiddleware  Bearer ausente/errado  -> 401
6. ContentTypeMiddleware     metodo com corpo != json -> 415
7. router
```

As camadas 2 e 3 vem ANTES da autenticacao de proposito. Elas nao dependem do
token e nao revelam nada sobre ele: um `Host` alheio e um `Origin` presente sao
propriedades da requisicao, nao da credencial. Sao a defesa contra DNS
rebinding e contra a pagina que o administrador abriu no navegador (secao 3.3),
e cortar essas requisicoes na borda externa e mais barato e mais claro do que
autentica-las primeiro para recusa-las depois.

A camada 4 vem antes da 5 por um motivo diferente: um `Content-Length` acima do
limite precisa falhar **antes da leitura integral**, e nao depois de um trabalho
que ja gastou memoria.

A camada 5 vem antes da 6, e as duas vem antes do router. E o que garante a
regra da secao 2: **sem credencial valida nunca ocorre um `422`**. Um `422` que
chegasse antes do `401` transformaria o schema num oraculo para quem nao tem
token.

## O que nao existe aqui

Nao ha middleware de CORS, e `OPTIONS` nao e registrado em rota alguma. Nao ha
front-end nesta fase, entao CORS nao tem funcao — e um
`Access-Control-Allow-Origin` num plano administrativo deixaria qualquer pagina
aberta no navegador do administrador ler a configuracao (secao 3.2).
"""

from __future__ import annotations

import hmac
from typing import Final

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from maskgw.admin.errors import AdminErrorCategory
from maskgw.admin.http.responses import error_response

#: Limite total de corpo, em bytes (secao 12.7).
MAX_BODY_BYTES: Final = 1 * 1024 * 1024

#: Unico media type aceito em metodo com corpo. Um `<form>` HTML so emite
#: `urlencoded`, `multipart` ou `text/plain`, entao exigir JSON e a terceira
#: camada anti-CSRF da secao 3.3.
JSON_MEDIA_TYPE: Final = "application/json"

#: Metodos para os quais o `Content-Type` e exigido. `GET` e `HEAD` ficam de
#: fora: a secao 12.7 exige explicitamente que um `GET` sem `Content-Type`
#: responda `200`.
BODY_METHODS: Final[frozenset[str]] = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Esquema de autorizacao, comparado sem diferenciar caixa (RFC 7235).
BEARER_SCHEME: Final = "bearer"

_CACHE_CONTROL: Final = "no-store"
_CORS_HEADER_PREFIX: Final = "access-control-"


class _ResponseState:
    """Se a resposta ja comecou a ser enviada.

    Sem isto, o catch-all nao consegue distinguir "falhou antes de responder"
    — caso em que ainda cabe um `500` — de "falhou depois de responder", em que
    enviar qualquer coisa corromperia a resposta ja em transito.
    """

    __slots__ = ("started",)

    def __init__(self) -> None:
        self.started = False


class BoundaryMiddleware:
    """Camada mais externa: cabecalhos obrigatorios e contencao de excecao.

    Faz tres coisas, e nenhuma delas pertence a uma rota:

    1. **`Cache-Control: no-store` em TODA resposta**, inclusive as que nenhum
       handler nosso produz — o `404` do router, o `405` do Starlette e o `500`
       do catch-all. Aplicar isso nos handlers deixaria justamente esses tres
       de fora.
    2. **Remove qualquer header CORS que tenha escapado.** Nos nunca os
       adicionamos; apagar aqui transforma "nao adicionamos" em "nao sai",
       que e uma garantia e nao uma afirmacao.
    3. **Nenhuma excecao chega ao servidor.** Sem isto, o
       `ServerErrorMiddleware` do Starlette responde `500` e em seguida
       **relevanta** a excecao para que o servidor a registre — e o uvicorn a
       registraria com `exc_info`, ou seja, o traceback inteiro, com o que
       quer que a excecao carregue. E o mesmo motivo de D-038 no plano MCP.

    `asyncio.CancelledError` e demais `BaseException` NAO sao capturadas:
    engolir um cancelamento quebraria o desligamento do proprio servidor.
    """

    __slots__ = ("_app",)

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        state = _ResponseState()

        async def decorated_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                state.started = True
                headers = MutableHeaders(scope=message)
                headers["cache-control"] = _CACHE_CONTROL
                for name in [
                    key
                    for key in headers.keys()  # noqa: SIM118 - MutableHeaders nao e dict
                    if key.lower().startswith(_CORS_HEADER_PREFIX)
                ]:
                    del headers[name]
            await send(message)

        try:
            await self._app(scope, receive, decorated_send)
        except Exception:
            if not state.started:
                # Fora de qualquer `except` nao da para levantar; aqui a
                # resposta e CONSTRUIDA, nao levantada, entao nao ha cadeia de
                # excecao para vazar. O corpo e o texto fixo da categoria.
                await _send_error(AdminErrorCategory.INTERNAL_ERROR, scope, receive, decorated_send)


class HostAllowlistMiddleware:
    """`Host` fora da allowlist -> `400`. Fecha DNS rebinding.

    Uma API em `127.0.0.1` e alcancavel por qualquer pagina que o administrador
    abra. Um atacante que controle DNS pode fazer `evil.example` resolver para
    `127.0.0.1` e transformar a requisicao em same-origin do ponto de vista do
    navegador — mas o `Host` enviado continua sendo `evil.example`.

    A allowlist e exatamente as tres formas com a porta em que o servidor
    escuta. Um `Host` sem porta nao e aceito: a Admin API nunca escuta em 80 ou
    443, entao a forma sem porta so apareceria numa requisicao que nao veio
    daqui.
    """

    __slots__ = ("_allowed", "_app")

    def __init__(self, app: ASGIApp, *, port: int) -> None:
        self._app = app
        self._allowed = allowed_hosts(port)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        host = Headers(scope=scope).get("host", "")
        if host.strip().casefold() not in self._allowed:
            await _send_error(AdminErrorCategory.HOST_NOT_ALLOWED, scope, receive, send)
            return
        await self._app(scope, receive, send)


class BrowserOriginMiddleware:
    """`Origin` ou `Referer` presentes -> `403`.

    Um cliente de API nao envia nenhum dos dois; um navegador envia sempre. A
    presenca de qualquer um e, portanto, prova de que a requisicao nasceu num
    contexto de navegacao — e nenhuma requisicao administrativa deveria.

    Recusa-se pela PRESENCA, nao pelo valor. Comparar o valor com uma lista de
    origens permitidas seria CORS por outro nome, e reintroduziria a pergunta
    "qual origem confiar" que a secao 3.2 fecha respondendo "nenhuma".
    """

    __slots__ = ("_app",)

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        if "origin" in headers or "referer" in headers:
            await _send_error(AdminErrorCategory.CROSS_ORIGIN_REJECTED, scope, receive, send)
            return
        await self._app(scope, receive, send)


class _BodyLimitExceededError(Exception):
    """Sinal interno: o corpo passou do limite durante a leitura.

    Existe para interromper o `receive` de dentro, sem que o middleware precise
    bufferizar o corpo para descobrir o tamanho. Nunca sai deste modulo.
    """


class BodyLimitMiddleware:
    """Corta o corpo em `MAX_BODY_BYTES`, com ou sem `Content-Length`.

    Dois caminhos, porque as duas situacoes falham em momentos diferentes:

    - **com `Content-Length`**, a recusa acontece pelo header, antes de ler um
      unico byte do corpo;
    - **sem `Content-Length`** — `Transfer-Encoding: chunked` —, o tamanho so
      se conhece recebendo. O `receive` e envolvido e os bytes sao CONTADOS a
      medida que chegam; assim que a soma passa do limite, a leitura para. O
      chunk que estoura o limite **nao e repassado** para baixo, entao nada
      alem do proprio limite chega a existir em memoria. Nao ha bufferizacao
      intermediaria aqui: este middleware nunca guarda o corpo, so o mede.
    """

    __slots__ = ("_app", "_limit")

    def __init__(self, app: ASGIApp, *, limit: int = MAX_BODY_BYTES) -> None:
        self._app = app
        self._limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        if self._declared_length_exceeds(Headers(scope=scope)):
            await _send_error(AdminErrorCategory.PAYLOAD_TOO_LARGE, scope, receive, send)
            return

        state = _ResponseState()
        received = 0

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._limit:
                    raise _BodyLimitExceededError
            return message

        async def tracking_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                state.started = True
            await send(message)

        try:
            await self._app(scope, counting_receive, tracking_send)
        except _BodyLimitExceededError:
            if not state.started:
                await _send_error(AdminErrorCategory.PAYLOAD_TOO_LARGE, scope, receive, send)

    def _declared_length_exceeds(self, headers: Headers) -> bool:
        raw = headers.get("content-length")
        if raw is None:
            return False
        declared: int | None = None
        try:
            declared = int(raw)
        except ValueError:
            declared = None
        # Um `Content-Length` ilegivel nao e recusado aqui: o proprio servidor
        # HTTP ja rejeita a requisicao antes de chegar ao ASGI. O que este
        # ramo garante e que um valor ilegivel nunca seja lido como "cabe".
        return declared is not None and declared > self._limit


class AuthenticationMiddleware:
    """`Authorization: Bearer <token>`, e so isso.

    **Nunca por query string, nunca por cookie.** Query string vaza em log de
    proxy, em historico e em `Referer`; cookie e exatamente o que torna CSRF
    possivel. Aceitar apenas o header e o que faz a primeira camada da secao
    3.3 funcionar: um `<form>` cross-origin nao define headers, e um `fetch`
    com `Authorization` dispara preflight — que nunca e respondido, porque
    `OPTIONS` nao existe.

    Ausente, malformado e errado produzem o MESMO `401`, com o mesmo corpo. Uma
    resposta que distinguisse "ausente" de "errado" ja seria meio oraculo.

    A comparacao e `hmac.compare_digest` sobre os bytes UTF-8 dos dois lados:
    tempo constante em relacao ao CONTEUDO. Um `==` vazaria o prefixo correto
    por tempo, um caractere por requisicao.
    """

    __slots__ = ("_app", "_token")

    def __init__(self, app: ASGIApp, *, token: str) -> None:
        self._app = app
        self._token = token.encode("utf-8")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        if not self._authorized(Headers(scope=scope).get("authorization")):
            await _send_error(AdminErrorCategory.UNAUTHORIZED, scope, receive, send)
            return
        await self._app(scope, receive, send)

    def _authorized(self, header: str | None) -> bool:
        if header is None:
            return False
        scheme, separator, candidate = header.partition(" ")
        if not separator or scheme.strip().casefold() != BEARER_SCHEME:
            return False
        return hmac.compare_digest(candidate.strip().encode("utf-8"), self._token)


class ContentTypeMiddleware:
    """Metodo com corpo sem `Content-Type: application/json` -> `415`.

    `GET` e `HEAD` nao sao afetados: a secao 12.7 exige que um `GET` sem
    `Content-Type` responda `200`.

    Parametros do media type sao ignorados — `application/json; charset=utf-8`
    e aceito —, mas o tipo em si tem de ser exatamente `application/json`.
    """

    __slots__ = ("_app",)

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        if scope.get("method", "").upper() in BODY_METHODS:
            declared = Headers(scope=scope).get("content-type", "")
            media_type = declared.split(";", 1)[0].strip().casefold()
            if media_type != JSON_MEDIA_TYPE:
                await _send_error(
                    AdminErrorCategory.UNSUPPORTED_MEDIA_TYPE,
                    scope,
                    receive,
                    send,
                )
                return
        await self._app(scope, receive, send)


def allowed_hosts(port: int) -> frozenset[str]:
    """As tres unicas formas de `Host` aceitas, com a porta em que se escuta."""
    return frozenset({f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"})


async def _send_error(
    category: AdminErrorCategory,
    scope: Scope,
    receive: Receive,
    send: Send,
) -> None:
    await error_response(category)(scope, receive, send)
