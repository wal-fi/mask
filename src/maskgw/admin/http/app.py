"""A aplicacao HTTP administrativa: leitura, `config:validate`, escrita e erros.

Etapas 7, 8 e 9 da Fase 7. As oito rotas de leitura da Etapa 7 sao `GET`/`HEAD`.
A Etapa 8 acrescentou `POST /admin/v1/config:validate`, que valida e compila um
documento candidato **sem efeito algum** (nao e uma escrita: nao persiste, nao
altera `revision`, nao conecta, nao entra na secao critica). A Etapa 9
acrescentou as **onze rotas de escrita** (secao 1.3): cada uma valida o corpo,
constroi um `ConfigMutation` (em `mutations.py`) e chama `AdminConfigService.apply()`,
que executa o fluxo de onze passos DENTRO da secao critica. A Etapa 10 acrescentou
a **auditoria administrativa** (`audit.py`): `config:validate` e cada escrita que
alcanca o handler emitem exatamente um `AdminAudit` pelo `AuditLog` injetado, sem
que `admin/http/` importe `logging` (secao 13).

## O conjunto de rotas e literal

Prefixo unico `/admin/v1`, e nada fora dele. As oito leituras estao em
`READ_PATHS`, o `config:validate` em `VALIDATE_PATH` e as onze escritas em
`WRITE_ROUTES`; um teste compara o que o router registrou com essas listas —
rota nova quebra a suite em vez de aparecer sem que ninguem tenha decidido
(secao 12.7). Nao ha `PATCH`.

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
from maskgw.admin.http import mutations
from maskgw.admin.http.audit import (
    AdminAuditor,
    AuditContext,
    exception_target_id,
    rule_target_id,
)
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
    AdoptRequest,
    ConfigReplaceRequest,
    ConfigValidateRequest,
    ConfigValidateResponse,
    DatabaseWriteRequest,
    DeleteRequest,
    ExceptionCreateRequest,
    ExceptionReplaceRequest,
    RuleCreateRequest,
    RuleReorderRequest,
    RuleReplaceRequest,
    SqlWriteRequest,
    WriteResponse,
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
from maskgw.admin.service import AdminConfigService, AdminOperation
from maskgw.audit import (
    AdminOperationName,
    AuditLog,
)
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

#: As onze rotas de escrita da Etapa 9 (secao 1.3), cada uma com o seu unico
#: metodo. Declaradas literalmente, como as leituras, para que o teste de
#: superficie compare o conjunto DECIDIDO — uma rota nova, ou um metodo a mais
#: numa rota existente, quebra a suite em vez de aparecer sem decisao (secao 12.7).
#:
#: A ordem importa para o roteamento: `/rules:reorder` e uma rota ESTATICA e
#: precisa ser registrada ANTES de `/rules/{rule_id}`, senao o `:reorder` seria
#: capturado como um `rule_id`. O FastAPI casa na ordem de registro.
WRITE_ROUTES: Final[tuple[tuple[str, str], ...]] = (
    (f"{API_PREFIX}/config:adopt", "POST"),
    (f"{API_PREFIX}/config", "PUT"),
    (f"{API_PREFIX}/rules:reorder", "POST"),
    (f"{API_PREFIX}/rules", "POST"),
    (f"{API_PREFIX}/rules/{{rule_id}}", "PUT"),
    (f"{API_PREFIX}/rules/{{rule_id}}", "DELETE"),
    (f"{API_PREFIX}/exceptions", "POST"),
    (f"{API_PREFIX}/exceptions/{{exception_id}}", "PUT"),
    (f"{API_PREFIX}/exceptions/{{exception_id}}", "DELETE"),
    (f"{API_PREFIX}/database", "PUT"),
    (f"{API_PREFIX}/sql", "PUT"),
)

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
    audit: AuditLog,
    hmac_key_env: str = HMAC_KEY_ENV,
) -> FastAPI:
    """Aplicacao FastAPI com as rotas de leitura, `config:validate`, escrita e handlers.

    Sem middleware: a fronteira e composta por fora, em `build_admin_app`, para
    que a ordem das camadas seja explicita e testavel separadamente.

    `audit` e o `AuditLog` — o mesmo do plano MCP — por onde toda operacao
    administrativa que alcanca um handler emite exatamente um `AdminAudit`
    (secao 13). Vem de fora porque `admin/` nao importa `logging`: quem loga e
    `audit/`.
    """
    auditor = AdminAuditor(audit)
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
        #
        # Auditado como operacao `validate` (secao 13.2): UM evento, alvo
        # `config`, `revision_before`/`after` None, e sem tocar o contador de
        # operacoes — `validate_candidate` nao entra na secao critica.
        return auditor.validate(lambda: validate_candidate(candidate, secrets=secrets))

    _register_write_routes(app, service, auditor)

    return app


def _register_write_routes(
    app: FastAPI,
    service: AdminConfigService,
    auditor: AdminAuditor,
) -> None:
    """As onze rotas de escrita da Etapa 9 (secao 1.3), auditadas na Etapa 10.

    Cada handler e `async def` e delega a `auditor.write`, que gera o
    `request_id`, mede a duracao, chama `service.apply` com um `AdminAuditProbe`
    e emite exatamente um `AdminAudit`. Toda a semantica — lock, adocao,
    `expected_revision`, digest, compilacao, conexao, persistencia, swap, backup —
    continua no servico; a rota so constroi a mutacao, o contexto de auditoria e
    chama `write`. `async def` chama o fluxo SINCRONO direto no event loop
    (secao 4.4): nada de `to_thread`, para que uma escrita nao sobreviva ao
    graceful shutdown (D-057). Uma recusa relevanta o `AdminError` sem alteracao,
    entao status e corpo permanecem os da Etapa 9.

    `/rules:reorder` e registrada ANTES de `/rules/{rule_id}`: a ordem de registro
    no FastAPI e a ordem de casamento, e sem isso `:reorder` seria capturado como
    um `rule_id` (secao 12.7).

    Mapeamento de alvo (secao 13.2): fixado por `OPERATION_TARGET_KIND` em
    `audit/`, e derivado dele por `AuditContext.target_kind` — o handler nao
    escolhe o `target_kind`, so a operacao. `target_id` so existe em update/delete
    de uma unica regra/exception, e so quando o path e um ID canonico (secao 13.3).
    """

    def _ctx(operation: AdminOperationName, target_id: str | None = None) -> AuditContext:
        return AuditContext(operation=operation, target_id=target_id)

    @app.post(f"{API_PREFIX}/config:adopt", response_model=WriteResponse)
    async def config_adopt(body: AdoptRequest) -> WriteResponse:
        revision = auditor.write(
            service,
            mutations.adopt(),
            expected_revision=body.expected_revision,
            operation=AdminOperation.ADOPT,
            context=_ctx(AdminOperationName.ADOPT),
        )
        return WriteResponse(revision=revision)

    @app.put(f"{API_PREFIX}/config", response_model=WriteResponse)
    async def config_replace(body: ConfigReplaceRequest) -> WriteResponse:
        revision = auditor.write(
            service,
            mutations.replace_config(body),
            expected_revision=body.expected_revision,
            operation=AdminOperation.WRITE,
            context=_ctx(AdminOperationName.CONFIG_PUT),
        )
        return WriteResponse(revision=revision)

    @app.post(f"{API_PREFIX}/rules:reorder", response_model=WriteResponse)
    async def rules_reorder(body: RuleReorderRequest) -> WriteResponse:
        revision = auditor.write(
            service,
            mutations.reorder_rules(body),
            expected_revision=body.expected_revision,
            operation=AdminOperation.WRITE,
            context=_ctx(AdminOperationName.RULES_REORDER),
        )
        return WriteResponse(revision=revision)

    @app.post(f"{API_PREFIX}/rules", response_model=WriteResponse)
    async def rules_create(body: RuleCreateRequest) -> WriteResponse:
        revision = auditor.write(
            service,
            mutations.create_rule(body),
            expected_revision=body.expected_revision,
            operation=AdminOperation.WRITE,
            context=_ctx(AdminOperationName.RULE_CREATE),
        )
        return WriteResponse(revision=revision)

    @app.put(f"{API_PREFIX}/rules/{{rule_id}}", response_model=WriteResponse)
    async def rules_replace(rule_id: str, body: RuleReplaceRequest) -> WriteResponse:
        revision = auditor.write(
            service,
            mutations.replace_rule(rule_id, body),
            expected_revision=body.expected_revision,
            operation=AdminOperation.WRITE,
            context=_ctx(AdminOperationName.RULE_UPDATE, rule_target_id(rule_id)),
        )
        return WriteResponse(revision=revision)

    @app.delete(f"{API_PREFIX}/rules/{{rule_id}}", response_model=WriteResponse)
    async def rules_delete(rule_id: str, body: DeleteRequest) -> WriteResponse:
        revision = auditor.write(
            service,
            mutations.delete_rule(rule_id),
            expected_revision=body.expected_revision,
            operation=AdminOperation.WRITE,
            context=_ctx(AdminOperationName.RULE_DELETE, rule_target_id(rule_id)),
        )
        return WriteResponse(revision=revision)

    @app.post(f"{API_PREFIX}/exceptions", response_model=WriteResponse)
    async def exceptions_create(body: ExceptionCreateRequest) -> WriteResponse:
        revision = auditor.write(
            service,
            mutations.create_exception(body),
            expected_revision=body.expected_revision,
            operation=AdminOperation.WRITE,
            context=_ctx(AdminOperationName.EXCEPTION_CREATE),
        )
        return WriteResponse(revision=revision)

    @app.put(f"{API_PREFIX}/exceptions/{{exception_id}}", response_model=WriteResponse)
    async def exceptions_replace(exception_id: str, body: ExceptionReplaceRequest) -> WriteResponse:
        revision = auditor.write(
            service,
            mutations.replace_exception(exception_id, body),
            expected_revision=body.expected_revision,
            operation=AdminOperation.WRITE,
            context=_ctx(AdminOperationName.EXCEPTION_UPDATE, exception_target_id(exception_id)),
        )
        return WriteResponse(revision=revision)

    @app.delete(f"{API_PREFIX}/exceptions/{{exception_id}}", response_model=WriteResponse)
    async def exceptions_delete(exception_id: str, body: DeleteRequest) -> WriteResponse:
        revision = auditor.write(
            service,
            mutations.delete_exception(exception_id),
            expected_revision=body.expected_revision,
            operation=AdminOperation.WRITE,
            context=_ctx(AdminOperationName.EXCEPTION_DELETE, exception_target_id(exception_id)),
        )
        return WriteResponse(revision=revision)

    @app.put(f"{API_PREFIX}/database", response_model=WriteResponse)
    async def database_replace(body: DatabaseWriteRequest) -> WriteResponse:
        revision = auditor.write(
            service,
            mutations.replace_database(body),
            expected_revision=body.expected_revision,
            operation=AdminOperation.WRITE,
            context=_ctx(AdminOperationName.DATABASE_PUT),
        )
        return WriteResponse(revision=revision)

    @app.put(f"{API_PREFIX}/sql", response_model=WriteResponse)
    async def sql_replace(body: SqlWriteRequest) -> WriteResponse:
        revision = auditor.write(
            service,
            mutations.replace_sql(body),
            expected_revision=body.expected_revision,
            operation=AdminOperation.WRITE,
            context=_ctx(AdminOperationName.SQL_PUT),
        )
        return WriteResponse(revision=revision)


def wrap_boundary(app: ASGIApp, *, token: str, port: int) -> ASGIApp:
    """Empilha as camadas de fronteira na ordem documentada em `middleware.py`.

    A composicao e de dentro para fora, entao a leitura desta funcao e o
    inverso da ordem de execucao: a ultima linha e a camada mais EXTERNA.

    Exposta separadamente para que a pilha inteira possa ser exercitada sobre
    uma aplicacao ASGI de teste — em particular o limite de corpo e o
    `Content-Type`. Desde a Etapa 9 ha rotas com corpo (`config:validate` e as
    onze escritas), e a fronteira as protege igualmente; testar a pilha sobre um
    app de teste minimo continua util para provocar os cortes de corpo sem
    depender de uma rota especifica.
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
    audit: AuditLog | None = None,
    hmac_key_env: str = HMAC_KEY_ENV,
) -> ASGIApp:
    """A aplicacao administrativa completa, pronta para o servidor.

    `port` e a porta em que o servidor REALMENTE escuta, e nao a desejada: a
    allowlist de `Host` e construida a partir dela. Quando a porta e escolhida
    pelo sistema, o app precisa ser montado depois do bind.

    `database_dsn_env` chega de fora porque o nome dessa variavel pertence ao
    composition root: `admin/` nao importa `bootstrap/`, e nao deve adivinhar
    como o plano de dados nomeia seu segredo.

    `audit` e o `AuditLog` por onde as operacoes administrativas registram
    (secao 13). O default constroi um `AuditLog` sobre o logger padrao — util em
    teste; em producao o composition root injeta o MESMO do plano MCP, para nao
    criar handler global nem duplicar configuracao de logging.
    """
    provider = secrets if secrets is not None else EnvSecretProvider()
    audit_log = audit if audit is not None else AuditLog()
    router = build_router(
        service,
        secrets=provider,
        database_dsn_env=database_dsn_env,
        audit=audit_log,
        hmac_key_env=hmac_key_env,
    )
    return wrap_boundary(router, token=token, port=port)


#: Assinatura de uma fabrica de aplicacao que so conhece a porta ja vinculada.
AppFactory = Callable[[int], ASGIApp]
