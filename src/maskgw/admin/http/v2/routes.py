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

## Handlers (Fase 9, Etapa 7, D-108)

As leituras sao `async def` sobre o selo do coordenador: so memoria, sem lock
do store, DNS, filesystem nem verificacao. As escritas e os testes de conexao
sao enfileirados na `AdminWorkQueue` dedicada (dona: o composition root) e
executados por um worker fixo, que roda a operacao E a auditoria inteiras com
ou sem request. O handler so espera, sob `asyncio.shield`, um future do loop
que o worker marca por `call_soon_threadsafe` — nenhum trabalho roda no loop.
Cancelar ou desconectar o request nao cancela a operacao aceita; a resposta
perdida e incerta. Fila cheia ou barreira fechada: `503
DATASOURCE_SERVICE_UNAVAILABLE`, auditado, sem efeito.

O gate limita UMA verificacao (prazo mais orcamento de cleanup, enquanto as
chamadas do SO retornam); a fila nao tem teto proprio, e uma chamada do SO
bloqueada nao tem teto. A D-090 continua aberta no gate 2, e a v2 segue
proibida em operacao real.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Generic, TypeVar, cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from maskgw.admin.errors import AdminErrorCategory
from maskgw.admin.http.v2.audit import AuditMark, DatasourceAuditor
from maskgw.admin.http.v2.errors import (
    DatasourceAdminError,
    DatasourceErrorCategory,
    V2Category,
    v2_error_response,
)
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
from maskgw.runtime.admin_work import AdminWorkQueue
from maskgw.runtime.datasource_service import DatasourceWriteProbe

if TYPE_CHECKING:
    from maskgw.runtime.datasource_service import DatasourceRuntime

_T = TypeVar("_T")

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


@dataclass(slots=True)
class _Outcome(Generic[_T]):
    """Desfecho fechado de uma operacao: resultado OU categoria, sem excecao."""

    result: _T | None = None
    category: V2Category | None = None
    current_revision: int | None = None


def _job(
    auditor: DatasourceAuditor,
    operation: DatasourceOperationName,
    target_id: str | None,
    call: Callable[[DatasourceWriteProbe], _T],
    mark: AuditMark,
) -> Callable[[], _Outcome[_T]]:
    """O trabalho do worker: operacao e auditoria inteiras, desfecho fechado.

    Uma falha que escape da traducao (defeito ou `BaseException`) e auditada
    como `INTERNAL_ERROR` so se nenhum evento saiu, e propaga para a fila, que
    se marca quebrada e bloqueia o coordenador (estado desconhecido).
    """

    def job() -> _Outcome[_T]:
        try:
            result = auditor.run(operation, target_id, call, mark=mark)
        except DatasourceAdminError as exc:
            return _Outcome(category=exc.category, current_revision=exc.current_revision)
        except BaseException:
            with contextlib.suppress(Exception):
                auditor.unknown(operation, target_id, mark)
            raise
        return _Outcome(result=result)

    return job


def _resolve(finished: asyncio.Future[None]) -> None:
    if not finished.done():
        finished.set_result(None)


async def _enqueue(
    work: AdminWorkQueue,
    auditor: DatasourceAuditor,
    operation: DatasourceOperationName,
    target_id: str | None,
    call: Callable[[DatasourceWriteProbe], _T],
) -> _T:
    """Enfileira e espera sem bloquear o loop; erro sempre fechado e sem cadeia."""
    loop = asyncio.get_running_loop()
    finished: asyncio.Future[None] = loop.create_future()

    def notify() -> None:
        # So marca o future, no loop; nenhum trabalho roda ali.
        loop.call_soon_threadsafe(_resolve, finished)

    mark = AuditMark()

    def abandon() -> None:
        # Concluido sem executar (contencao falhou): um evento, no maximo.
        auditor.unknown(operation, target_id, mark)

    refused = False
    ticket = None
    try:
        ticket = work.submit(
            _job(auditor, operation, target_id, call, mark), notify=notify, abandon=abandon
        )
    except Exception:
        # Inclui `AdminWorkUnavailableError`. Uma excecao de `submit` ocorre
        # antes de aceitar ou dentro do trecho protegido, que `submit` desfaz
        # sob o lock (job neutralizado, registro e fila removidos) antes de
        # qualquer worker ver o ticket: a recusa e sem efeito. Uma interrupcao
        # assincrona dentro desse desfazer nao e coberta.
        refused = True
    if refused or ticket is None:
        # Fora do lock da fila e fora do `except` (D-017): sem efeito, auditado.
        auditor.refused(operation, target_id)
        raise DatasourceAdminError(DatasourceErrorCategory.DATASOURCE_SERVICE_UNAVAILABLE)
    # `shield`: cancelar o request nao cancela o future que o worker marcara.
    await asyncio.shield(finished)
    outcome = ticket.take()
    if ticket.failed or outcome is None:
        raise DatasourceAdminError(AdminErrorCategory.INTERNAL_ERROR)
    if outcome.category is not None:
        raise DatasourceAdminError(outcome.category, current_revision=outcome.current_revision)
    return cast(_T, outcome.result)


def register_v2(
    app: FastAPI, runtime: DatasourceRuntime, *, audit: AuditLog, work: AdminWorkQueue
) -> None:
    """Acrescenta as rotas v2 e o handler do erro v2 ao app administrativo.

    `work` e a fila dedicada do composition root (D-108); as escritas e os
    testes de conexao so rodam nela.
    """
    admin = DatasourceAdmin(runtime)
    auditor = DatasourceAuditor(audit)
    ops = DatasourceOperationName
    reads = sorted(V2_READ_METHODS)

    async def submit(
        operation: DatasourceOperationName,
        target_id: str | None,
        call: Callable[[DatasourceWriteProbe], _T],
    ) -> _T:
        return await _enqueue(work, auditor, operation, target_id, call)

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
        return await submit(ops.CREATE, None, lambda probe: admin.create(body, probe))

    @app.post(f"{V2_PREFIX}/datasources:test", response_model=DatasourceTestResponse)
    async def test_draft(body: DatasourceTestDraftRequest) -> DatasourceTestResponse:
        return await submit(ops.TEST_DRAFT, None, lambda _probe: admin.test_draft(body))

    @app.post(
        f"{V2_PREFIX}/datasources/{{datasource_id}}:test",
        response_model=DatasourceTestResponse,
    )
    async def test(datasource_id: str, body: DatasourceTestRequest) -> DatasourceTestResponse:
        del body
        return await submit(
            ops.TEST, canonical_datasource_id(datasource_id), lambda _p: admin.test(datasource_id)
        )

    @app.post(
        f"{V2_PREFIX}/datasources/{{datasource_id}}:rotate-credential",
        response_model=DatasourceWriteResponse,
    )
    async def rotate(datasource_id: str, body: DatasourceRotateRequest) -> DatasourceWriteResponse:
        return await submit(
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
        return await submit(
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
        return await submit(
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
        return await submit(
            ops.UPDATE,
            canonical_datasource_id(datasource_id),
            lambda probe: admin.update(datasource_id, body, probe),
        )

    @app.delete(
        f"{V2_PREFIX}/datasources/{{datasource_id}}", response_model=DatasourceDeleteResponse
    )
    async def delete(datasource_id: str, body: DatasourceDeleteRequest) -> DatasourceDeleteResponse:
        return await submit(
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
        return await submit(
            ops.POLICY_PUT,
            canonical_datasource_id(datasource_id),
            lambda probe: admin.put_policy(datasource_id, body, probe),
        )


__all__ = ["V2_PREFIX", "V2_READ_METHODS", "V2_READ_PATHS", "V2_WRITE_ROUTES", "register_v2"]
