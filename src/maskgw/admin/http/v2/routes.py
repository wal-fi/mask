"""Rotas `/admin/v2` de datasources (Fase 9, Etapa 4, spec §8, D-093).

Registradas SOMENTE quando o composition root recebe o catalogo de datasources
e a fronteira HTTP (`build_application(datasource_catalog=..., admin_http=...)`).
Sem catalogo, este modulo nem e importado e o app administrativo e a v1 byte a
byte. Nenhuma variavel de ambiente liga a v2 nesta etapa.

A v2 passa pela MESMA pilha de fronteira da v1 — Host na allowlist, `Origin`/
`Referer` recusados, corpo ate 1 MiB, bearer token, `application/json`,
`no-store`, sem CORS, sem `OPTIONS`, sem `/docs` — porque e registrada no mesmo
roteador, por dentro das mesmas camadas.

## O conjunto de rotas e literal

`V2_READ_PATHS` e `V2_WRITE_ROUTES` sao o inventario decidido; um teste compara
com o que o roteador registrou. Nao ha rota de SQL, de consulta, de DSN, de
segredo, de chave-mestra, de auditoria, nem de default do MCP (adiado para a
Etapa 11, D-096).

As acoes `:test`, `:rotate-credential`, `:enable` e `:disable` sao `POST` e sao
registradas ANTES das rotas de `{datasource_id}`: o FastAPI casa na ordem de
registro.

## Handlers

`async def` chamando o coordenador sincrono direto no event loop, como as
escritas da v1 (D-059): nenhuma thread de worker sobrevive ao graceful shutdown.
NAO ha prazo total para uma operacao com candidato. O prazo de DNS (D-092)
limita a resolucao, e o `connect_timeout` limita o estabelecimento da conexao;
as consultas de verificacao que `PostgresAdapter.connect()` executa depois de
autenticar (read-only, `statement_timeout`, proveniencia) dependem do
`statement_timeout` do PROPRIO servidor. Um upstream que autentica e para de
responder prende o handler, o event loop administrativo e o shutdown. Esse
limite e gate da ativacao da v2 pelo operador (Etapa 7, D-090) e ainda nao
existe.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from maskgw.admin.http.v2.audit import DatasourceAuditor
from maskgw.admin.http.v2.errors import DatasourceAdminError, v2_error_response
from maskgw.admin.http.v2.operations import DatasourceAdmin, canonical_datasource_id
from maskgw.admin.http.v2.schemas import (
    DatasourceCreateRequest,
    DatasourceDeleteRequest,
    DatasourceDeleteResponse,
    DatasourceListResponse,
    DatasourcePolicyRequest,
    DatasourcePolicyResponse,
    DatasourceResponse,
    DatasourceRevisionRequest,
    DatasourceRotateRequest,
    DatasourceTestDraftRequest,
    DatasourceTestRequest,
    DatasourceTestResponse,
    DatasourceUpdateRequest,
    DatasourceWriteResponse,
    V2StatusResponse,
)
from maskgw.audit import AuditLog
from maskgw.audit.datasource import DatasourceOperationName

if TYPE_CHECKING:
    from maskgw.runtime.datasource_service import DatasourceRuntime

V2_PREFIX: Final = "/admin/v2"

V2_READ_METHODS: Final[frozenset[str]] = frozenset({"GET", "HEAD"})

V2_READ_PATHS: Final[tuple[str, ...]] = (
    f"{V2_PREFIX}/status",
    f"{V2_PREFIX}/datasources",
    f"{V2_PREFIX}/datasources/{{datasource_id}}",
    f"{V2_PREFIX}/datasources/{{datasource_id}}/policy",
)

V2_WRITE_ROUTES: Final[tuple[tuple[str, str], ...]] = (
    (f"{V2_PREFIX}/datasources", "POST"),
    (f"{V2_PREFIX}/datasources:test", "POST"),
    (f"{V2_PREFIX}/datasources/{{datasource_id}}:test", "POST"),
    (f"{V2_PREFIX}/datasources/{{datasource_id}}:rotate-credential", "POST"),
    (f"{V2_PREFIX}/datasources/{{datasource_id}}:enable", "POST"),
    (f"{V2_PREFIX}/datasources/{{datasource_id}}:disable", "POST"),
    (f"{V2_PREFIX}/datasources/{{datasource_id}}", "PUT"),
    (f"{V2_PREFIX}/datasources/{{datasource_id}}", "DELETE"),
    (f"{V2_PREFIX}/datasources/{{datasource_id}}/policy", "PUT"),
)


def register_v2(app: FastAPI, runtime: DatasourceRuntime, *, audit: AuditLog) -> None:
    """Acrescenta as rotas v2 e o handler do erro v2 ao app administrativo."""
    admin = DatasourceAdmin(runtime)
    auditor = DatasourceAuditor(audit)
    ops = DatasourceOperationName
    reads = sorted(V2_READ_METHODS)

    @app.exception_handler(DatasourceAdminError)
    async def _v2_error(_request: Request, exc: DatasourceAdminError) -> JSONResponse:
        # So a categoria e a revision: nunca `str(exc)` nem a cadeia (nula).
        return v2_error_response(exc.category, current_revision=exc.current_revision)

    # -- leituras ---------------------------------------------------------

    @app.api_route(f"{V2_PREFIX}/status", methods=reads, response_model=V2StatusResponse)
    async def status() -> V2StatusResponse:
        return admin.status()

    @app.api_route(f"{V2_PREFIX}/datasources", methods=reads, response_model=DatasourceListResponse)
    async def datasources() -> DatasourceListResponse:
        return admin.list()

    # -- acoes (antes das rotas de `{datasource_id}`) ---------------------

    @app.post(f"{V2_PREFIX}/datasources", response_model=DatasourceWriteResponse)
    async def create(body: DatasourceCreateRequest) -> DatasourceWriteResponse:
        return auditor.run(ops.CREATE, None, lambda probe: admin.create(body, probe))

    @app.post(f"{V2_PREFIX}/datasources:test", response_model=DatasourceTestResponse)
    async def test_draft(body: DatasourceTestDraftRequest) -> DatasourceTestResponse:
        return auditor.run(ops.TEST_DRAFT, None, lambda _probe: admin.test_draft(body))

    @app.post(
        f"{V2_PREFIX}/datasources/{{datasource_id}}:test",
        response_model=DatasourceTestResponse,
    )
    async def test(datasource_id: str, body: DatasourceTestRequest) -> DatasourceTestResponse:
        del body
        return auditor.run(
            ops.TEST, canonical_datasource_id(datasource_id), lambda _p: admin.test(datasource_id)
        )

    @app.post(
        f"{V2_PREFIX}/datasources/{{datasource_id}}:rotate-credential",
        response_model=DatasourceWriteResponse,
    )
    async def rotate(datasource_id: str, body: DatasourceRotateRequest) -> DatasourceWriteResponse:
        return auditor.run(
            ops.ROTATE_CREDENTIAL,
            canonical_datasource_id(datasource_id),
            lambda probe: admin.rotate(datasource_id, body, probe),
        )

    @app.post(
        f"{V2_PREFIX}/datasources/{{datasource_id}}:enable",
        response_model=DatasourceWriteResponse,
    )
    async def enable(
        datasource_id: str, body: DatasourceRevisionRequest
    ) -> DatasourceWriteResponse:
        return auditor.run(
            ops.ENABLE,
            canonical_datasource_id(datasource_id),
            lambda probe: admin.set_enabled(datasource_id, body, probe, enabled=True),
        )

    @app.post(
        f"{V2_PREFIX}/datasources/{{datasource_id}}:disable",
        response_model=DatasourceWriteResponse,
    )
    async def disable(
        datasource_id: str, body: DatasourceRevisionRequest
    ) -> DatasourceWriteResponse:
        return auditor.run(
            ops.DISABLE,
            canonical_datasource_id(datasource_id),
            lambda probe: admin.set_enabled(datasource_id, body, probe, enabled=False),
        )

    # -- recurso individual -------------------------------------------------

    @app.api_route(
        f"{V2_PREFIX}/datasources/{{datasource_id}}",
        methods=reads,
        response_model=DatasourceResponse,
    )
    async def datasource(datasource_id: str) -> DatasourceResponse:
        return admin.get(datasource_id)

    @app.put(f"{V2_PREFIX}/datasources/{{datasource_id}}", response_model=DatasourceWriteResponse)
    async def update(datasource_id: str, body: DatasourceUpdateRequest) -> DatasourceWriteResponse:
        return auditor.run(
            ops.UPDATE,
            canonical_datasource_id(datasource_id),
            lambda probe: admin.update(datasource_id, body, probe),
        )

    @app.delete(
        f"{V2_PREFIX}/datasources/{{datasource_id}}", response_model=DatasourceDeleteResponse
    )
    async def delete(datasource_id: str, body: DatasourceDeleteRequest) -> DatasourceDeleteResponse:
        return auditor.run(
            ops.DELETE,
            canonical_datasource_id(datasource_id),
            lambda probe: admin.delete(datasource_id, body, probe),
        )

    @app.api_route(
        f"{V2_PREFIX}/datasources/{{datasource_id}}/policy",
        methods=reads,
        response_model=DatasourcePolicyResponse,
    )
    async def policy(datasource_id: str) -> DatasourcePolicyResponse:
        return admin.policy(datasource_id)

    @app.put(
        f"{V2_PREFIX}/datasources/{{datasource_id}}/policy",
        response_model=DatasourceWriteResponse,
    )
    async def put_policy(
        datasource_id: str, body: DatasourcePolicyRequest
    ) -> DatasourceWriteResponse:
        return auditor.run(
            ops.POLICY_PUT,
            canonical_datasource_id(datasource_id),
            lambda probe: admin.put_policy(datasource_id, body, probe),
        )


__all__ = ["V2_PREFIX", "V2_READ_METHODS", "V2_READ_PATHS", "V2_WRITE_ROUTES", "register_v2"]
