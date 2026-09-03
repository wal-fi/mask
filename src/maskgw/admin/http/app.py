"""A aplicacao HTTP administrativa: rotas de leitura, `config:validate` e erros.

Etapas 7 e 8 da Fase 7. As oito rotas de leitura da Etapa 7 continuam sendo
**somente leitura**. A Etapa 8 acrescenta UMA rota com corpo,
`POST /admin/v1/config:validate`, que **nao e uma escrita**: valida o schema,
compila os transformers e a policy, e descarta o resultado. Ela nao persiste,
nao altera `revision`, nao conecta ao PostgreSQL e nao entra na secao critica
administrativa (secao 1.2). As rotas de escrita e a adocao com backup sao a
Etapa 9; `AdminAudit` e a Etapa 10.

## O conjunto de rotas e literal

Prefixo unico `/admin/v1`, e nada fora dele. As oito rotas de leitura estao em
`READ_PATHS` e a unica rota com corpo em `VALIDATE_PATH`; um teste compara o que
o router registrou com essas listas — rota nova quebra a suite em vez de
aparecer sem que ninguem tenha decidido (secao 12.7).

O que **nao existe**, e nao e "recusado" mas inexistente (D-049):

```text
/query   /sql   /execute   /explain   /schema   /tables   /preview
/secrets   /hmac-key   /token   /dsn   /database/dsn
/config:reload
/protected/*  (qualquer metodo de escrita)
```

`/docs`, `/redoc` e `/openapi.json` tambem nao existem: entregariam a
superficie inteira a um chamador nao autenticado. Sao desligados na construcao,
e nao escondidos.

`redirect_slashes=False`: `/admin/v1/rules/` responde `404`, e nunca um `307`
para `/admin/v1/rules`. Um redirect implicito e uma rota que ninguem registrou.

## Uma resposta, um snapshot

Cada handler chama `service.snapshot()` **uma vez** e passa o resultado adiante.
Nenhum deles le `service.revision`, `service.document` ou `service.sql_policy`:
duas leituras da referencia publicada admitem um swap entre elas, e a resposta
sairia com o conteudo de um runtime e a revision de outro. Como as funcoes de
`views.py` recebem `AdminSnapshot`, elas nao teriam nem como fazer a segunda
leitura (D-057).

## Os handlers substituidos (secao 10.3)

| handler | por que |
|---|---|
| `RequestValidationError` | o default inclui o valor `input` que falhou -> `SCHEMA_INVALID` |
| `AdminError` | traduz a categoria fechada de `config:validate` em resposta uniforme |
| `HTTPException` | o default ecoa `detail` arbitrario |
| `Exception` | sem ele a excecao sobe para o servidor, que registra o traceback |

O ultimo nao basta sozinho: o `ServerErrorMiddleware` do Starlette responde e
em seguida **relevanta**. Quem realmente contem a excecao e o
`BoundaryMiddleware`, fora dele. Ver `middleware.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, NoReturn

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp

from maskgw.admin.errors import AdminError, AdminErrorCategory
from maskgw.admin.http.middleware import (
    AuthenticationMiddleware,
    BodyLimitMiddleware,
    BoundaryMiddleware,
    BrowserOriginMiddleware,
    ContentTypeMiddleware,
    HostAllowlistMiddleware,
)
from maskgw.admin.http.responses import (
    STATUS_BY_CATEGORY,
    error_response,
    field_path,
    reason_for,
)
from maskgw.admin.http.schemas import (
    AdminConfigResponse,
    AdminExceptionResponse,
    AdminExceptionsResponse,
    AdminProtectedResponse,
    AdminRuleResponse,
    AdminRulesResponse,
    AdminStatusResponse,
    AdminTransformersResponse,
    ConfigValidateRequest,
    ConfigValidateResponse,
)
from maskgw.admin.http.validate import validate_candidate
from maskgw.admin.http.views import (
    build_config,
    build_exceptions,
    build_protected,
    build_rules,
    build_status,
    build_transformers,
    find_exception,
    find_rule,
)
from maskgw.admin.service import AdminConfigService
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.secretsource import EnvSecretProvider, SecretProvider

#: Prefixo unico. Nenhuma rota fora dele.
API_PREFIX: Final = "/admin/v1"

#: Os metodos de cada rota. `HEAD` acompanha todo `GET`: mesma autenticacao,
#: mesmo status, corpo vazio (secao 12.7). Declarado explicitamente em vez de
#: herdado do Starlette, para que o teste de superficie compare o que foi
#: DECIDIDO, e nao o que o framework acrescentou.
READ_METHODS: Final[frozenset[str]] = frozenset({"GET", "HEAD"})

#: O conjunto literal de caminhos de leitura (secao 1.1).
READ_PATHS: Final[tuple[str, ...]] = (
    f"{API_PREFIX}/status",
    f"{API_PREFIX}/config",
    f"{API_PREFIX}/rules",
    f"{API_PREFIX}/rules/{{rule_id}}",
    f"{API_PREFIX}/exceptions",
    f"{API_PREFIX}/exceptions/{{exception_id}}",
    f"{API_PREFIX}/transformers",
    f"{API_PREFIX}/protected",
)

#: A unica rota com corpo desta fase (secao 1.2). `POST` e so `POST`: nenhum
#: `GET`, `HEAD`, `PUT`, `PATCH`, `DELETE` ou `OPTIONS` e registrado nela. Um
#: `HEAD` implicito seria pior que inutil — sugeriria que a validacao tem uma
#: forma sem corpo, que ela nao tem.
VALIDATE_PATH: Final = f"{API_PREFIX}/config:validate"

#: Os metodos de `config:validate`. Declarado como as leituras, para que o teste
#: de superficie compare o que foi DECIDIDO, e nao o que o framework acrescentou.
VALIDATE_METHODS: Final[frozenset[str]] = frozenset({"POST"})

#: Status HTTP -> categoria, para traduzir o que o Starlette levanta sozinho:
#: o `404` de caminho desconhecido e o `405` de metodo nao registrado.
_CATEGORY_BY_STATUS: Final[dict[int, AdminErrorCategory]] = {
    400: AdminErrorCategory.HOST_NOT_ALLOWED,
    401: AdminErrorCategory.UNAUTHORIZED,
    403: AdminErrorCategory.CROSS_ORIGIN_REJECTED,
    404: AdminErrorCategory.NOT_FOUND,
    405: AdminErrorCategory.METHOD_NOT_ALLOWED,
    413: AdminErrorCategory.PAYLOAD_TOO_LARGE,
    415: AdminErrorCategory.UNSUPPORTED_MEDIA_TYPE,
    422: AdminErrorCategory.SCHEMA_INVALID,
}


def _not_found() -> NoReturn:
    """`NOT_FOUND` sanitizado, sem citar o ID pedido nem quantos existem.

    Um ID malformado cai aqui tambem, e nao num `422`: distinguir "malformado"
    de "inexistente" seria um oraculo sobre o formato interno dos IDs, sem
    contrapartida alguma para quem chama legitimamente.
    """
    raise StarletteHTTPException(status_code=STATUS_BY_CATEGORY[AdminErrorCategory.NOT_FOUND])


def install_error_handlers(app: FastAPI) -> None:
    """Substitui os tres handlers default (secao 10.3).

    Separado de `build_admin_app` de proposito: o comportamento dos handlers e
    exercitavel sobre uma aplicacao de teste minima, sem registrar nenhuma rota
    de producao so para provoca-los.
    """

    @app.exception_handler(RequestValidationError)
    async def _schema_invalid(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # Somente CAMINHO de campo e reason code fechado. O `input` rejeitado
        # jamais entra: um `fixed.value` ou um `regex.replacement` recusado
        # voltaria no corpo do erro e dali para o log do cliente (secao 4.5).
        fields = [
            {
                "path": field_path(tuple(error.get("loc", ()))),
                "reason": reason_for(str(error.get("type", ""))),
            }
            for error in exc.errors()
        ]
        return error_response(AdminErrorCategory.SCHEMA_INVALID, fields=fields)

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # `exc.detail` NAO e lido. Ele carrega texto do framework — e, numa
        # etapa futura, poderia carregar o que um handler tenha posto ali.
        category = _CATEGORY_BY_STATUS.get(exc.status_code, AdminErrorCategory.INTERNAL_ERROR)
        return error_response(category)

    @app.exception_handler(AdminError)
    async def _admin_error(_request: Request, exc: AdminError) -> JSONResponse:
        # `config:validate` (e, na Etapa 9, as escritas) levanta `AdminError` de
        # categoria fechada. So a categoria e lida — nunca `str(exc)`, que ja e
        # o texto fixo da categoria, e nunca a cadeia, que `raise_admin_error`
        # deixou nula. `current_revision` viaja quando a categoria o carrega.
        return error_response(exc.category, current_revision=exc.current_revision)

    @app.exception_handler(Exception)
    async def _unexpected(_request: Request, _exc: Exception) -> JSONResponse:
        # Categoria fixa, sem `str(exc)`, sem traceback, sem cadeia. A excecao
        # nao e relevantada por nos; o `BoundaryMiddleware` impede que o
        # Starlette a devolva ao servidor, que a registraria com `exc_info`.
        return error_response(AdminErrorCategory.INTERNAL_ERROR)


def build_router(
    service: AdminConfigService,
    *,
    secrets: SecretProvider,
    database_dsn_env: str,
    hmac_key_env: str = HMAC_KEY_ENV,
) -> FastAPI:
    """Aplicacao FastAPI com as oito rotas de leitura e os handlers.

    Sem middleware: a fronteira e composta por fora, em `build_admin_app`, para
    que a ordem das camadas seja explicita e testavel separadamente.
    """
    app = FastAPI(
        title="maskgw admin",
        version="1",
        # A superficie inteira, entregue sem autenticacao. Desligadas.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        # Sem redirect implicito: `/rules/` e 404, nunca 307 para `/rules`.
        redirect_slashes=False,
    )
    # Redundante com o parametro acima em versoes que o aceitam, e a garantia
    # em versoes que o ignoram silenciosamente. Um `307` para um caminho que
    # ninguem registrou seria uma rota implicita.
    app.router.redirect_slashes = False

    install_error_handlers(app)

    @app.api_route(
        f"{API_PREFIX}/status",
        methods=sorted(READ_METHODS),
        response_model=AdminStatusResponse,
    )
    async def status() -> AdminStatusResponse:
        return build_status(
            service.snapshot(),
            service,
            secrets=secrets,
            hmac_key_env=hmac_key_env,
            database_dsn_env=database_dsn_env,
        )

    @app.api_route(
        f"{API_PREFIX}/config",
        methods=sorted(READ_METHODS),
        response_model=AdminConfigResponse,
    )
    async def config() -> AdminConfigResponse:
        return build_config(service.snapshot())

    @app.api_route(
        f"{API_PREFIX}/rules",
        methods=sorted(READ_METHODS),
        response_model=AdminRulesResponse,
    )
    async def rules() -> AdminRulesResponse:
        return build_rules(service.snapshot())

    @app.api_route(
        f"{API_PREFIX}/rules/{{rule_id}}",
        methods=sorted(READ_METHODS),
        response_model=AdminRuleResponse,
    )
    async def rule(rule_id: str) -> AdminRuleResponse:
        found = find_rule(service.snapshot(), rule_id)
        if found is None:
            _not_found()
        return found

    @app.api_route(
        f"{API_PREFIX}/exceptions",
        methods=sorted(READ_METHODS),
        response_model=AdminExceptionsResponse,
    )
    async def exceptions() -> AdminExceptionsResponse:
        return build_exceptions(service.snapshot())

    @app.api_route(
        f"{API_PREFIX}/exceptions/{{exception_id}}",
        methods=sorted(READ_METHODS),
        response_model=AdminExceptionResponse,
    )
    async def exception(exception_id: str) -> AdminExceptionResponse:
        found = find_exception(service.snapshot(), exception_id)
        if found is None:
            _not_found()
        return found

    @app.api_route(
        f"{API_PREFIX}/transformers",
        methods=sorted(READ_METHODS),
        response_model=AdminTransformersResponse,
    )
    async def transformers() -> AdminTransformersResponse:
        return build_transformers(service.snapshot())

    @app.api_route(
        f"{API_PREFIX}/protected",
        methods=sorted(READ_METHODS),
        response_model=AdminProtectedResponse,
    )
    async def protected() -> AdminProtectedResponse:
        return build_protected(service.snapshot())

    @app.api_route(
        VALIDATE_PATH,
        methods=sorted(VALIDATE_METHODS),
        response_model=ConfigValidateResponse,
    )
    async def config_validate(candidate: ConfigValidateRequest) -> ConfigValidateResponse:
        # O corpo ja passou pelo schema HTTP (senao o handler de
        # `RequestValidationError` teria respondido `SCHEMA_INVALID`). A funcao
        # compila e descarta; ela NAO recebe o `service`, entao nao alcanca
        # snapshot, registry, filesystem nem secao critica (secao 1.2, D-058).
        #
        # `async def` e sem `to_thread`: a validacao e limitada pelo corpo de
        # 1 MiB e nao toca I/O, entao roda no event loop. Um worker thread aqui
        # poderia sobreviver ao graceful shutdown de D-057.
        return validate_candidate(candidate, secrets=secrets)

    return app


def wrap_boundary(app: ASGIApp, *, token: str, port: int) -> ASGIApp:
    """Empilha as camadas de fronteira na ordem documentada em `middleware.py`.

    A composicao e de dentro para fora, entao a leitura desta funcao e o
    inverso da ordem de execucao: a ultima linha e a camada mais EXTERNA.

    Exposta separadamente para que a pilha inteira possa ser exercitada sobre
    uma aplicacao ASGI de teste — em particular o limite de corpo e o
    `Content-Type`, que nenhuma rota desta etapa alcanca, porque nenhuma tem
    corpo. Testa-los assim evita registrar um endpoint de producao so para
    provoca-los.
    """
    stack: ASGIApp = ContentTypeMiddleware(app)
    stack = AuthenticationMiddleware(stack, token=token)
    stack = BodyLimitMiddleware(stack)
    stack = BrowserOriginMiddleware(stack)
    stack = HostAllowlistMiddleware(stack, port=port)
    return BoundaryMiddleware(stack)


def build_admin_app(  # noqa: PLR0913 - parametros de composicao, keyword-only
    service: AdminConfigService,
    *,
    token: str,
    port: int,
    secrets: SecretProvider | None = None,
    database_dsn_env: str,
    hmac_key_env: str = HMAC_KEY_ENV,
) -> ASGIApp:
    """A aplicacao administrativa completa, pronta para o servidor.

    `port` e a porta em que o servidor REALMENTE escuta, e nao a desejada: a
    allowlist de `Host` e construida a partir dela. Quando a porta e escolhida
    pelo sistema, o app precisa ser montado depois do bind.

    `database_dsn_env` chega de fora porque o nome dessa variavel pertence ao
    composition root: `admin/` nao importa `bootstrap/`, e nao deve adivinhar
    como o plano de dados nomeia seu segredo.
    """
    provider = secrets if secrets is not None else EnvSecretProvider()
    router = build_router(
        service,
        secrets=provider,
        database_dsn_env=database_dsn_env,
        hmac_key_env=hmac_key_env,
    )
    return wrap_boundary(router, token=token, port=port)


#: Assinatura de uma fabrica de aplicacao que so conhece a porta ja vinculada.
AppFactory = Callable[[int], ASGIApp]
