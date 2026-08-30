"""Gateway: a fachada publica da aplicacao.

Unica camada que orquestra validacao, execucao, proveniencia, masking e
limites. A camada MCP chama SOMENTE isto — nunca `PostgresAdapter`, nunca
psycopg, nunca o Masking Engine.

Nada de logica nova aqui: a validacao e da Fase 4, o masking da Fase 1, a
proveniencia da Fase 3, os limites da Fase 4. O Gateway compoe e traduz.

Fronteira de erro: `Gateway.query` levanta APENAS `GatewayError`, com uma
categoria e uma mensagem fixa. A excecao interna nao e encadeada — nem por
`__cause__`, nem por `__context__` (D-017).

Desde a Fase 7 o Gateway nao guarda um adapter: ele ADQUIRE um runtime por
query no `RuntimeRegistry` e o libera no fim (D-054). A query usa ESSA
referencia do inicio ao fim, sem releitura no meio — e o que garante "o
runtime antigo inteiro ou o novo inteiro", nunca uma mistura.

A referencia e liberada assim que a execucao sincrona termina e o
`QueryResult` ja protegido esta montado. NAO se prolonga a referencia porque o
cliente MCP demorou a consumir a saida: o resultado ja e imutavel e ja passou
pelo Masking Engine, entao nada nele depende mais do runtime. Prolongar
seguraria uma conexao PostgreSQL pelo tempo do cliente, e um cliente que
parasse de consumir bloquearia todo reload por RELOAD_BUSY.
"""

from __future__ import annotations

import time
import uuid
from types import TracebackType
from typing import NoReturn

from maskgw.audit import FAILURE, SUCCESS, AuditLog, QueryAudit
from maskgw.gateway.models import (
    ErrorCategory,
    GatewayError,
    QueryColumn,
    QueryResult,
    categorize,
    jsonable,
)
from maskgw.masking.engine import Action
from maskgw.runtime import RuntimeRegistry


class Gateway:
    """Orquestrador. A unica camada que toca o valor original."""

    def __init__(self, registry: RuntimeRegistry, audit: AuditLog) -> None:
        self._registry = registry
        self._audit = audit

    @property
    def revision(self) -> int:
        """Revision do runtime publicado. Metadata, para o plano admin."""
        return self._registry.current.revision

    def query(self, sql: str) -> QueryResult:
        """Executa uma consulta e devolve o resultado ja seguro."""
        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        category: ErrorCategory | None = None
        result: QueryResult | None = None

        try:
            # Uma unica aquisicao, usada ate o fim. O `finally` do `borrow`
            # garante o release inclusive quando a query levanta.
            with self._registry.borrow() as runtime:
                # O lock de conexao e POR RUNTIME: cada runtime tem seu
                # proprio adapter, e uma conexao psycopg nao suporta consultas
                # concorrentes intercaladas (D-034). Ele nao serializa o
                # Gateway inteiro, so aquele adapter.
                with runtime.connection_lock:
                    # Idempotente quando ja aberta; reconecta com verificacao
                    # completa se a conexao caiu.
                    runtime.adapter.connect()
                    masked = runtime.adapter.execute_validated(sql)
                # Montado ainda dentro da referencia: depois daqui o resultado
                # e imutavel e nao depende mais do runtime.
                result = _to_query_result(masked)
        except BaseException as exc:
            category = categorize(exc)

        elapsed_ms = int((time.perf_counter() - started) * 1000)

        if category is not None:
            self._audit.record(
                QueryAudit(
                    request_id=request_id,
                    outcome=FAILURE,
                    duration_ms=elapsed_ms,
                    error_category=category.value,
                )
            )
            _raise_gateway_error(category)

        assert result is not None  # noqa: S101 - invariante do fluxo acima
        self._audit.record(
            QueryAudit(
                request_id=request_id,
                outcome=SUCCESS,
                duration_ms=elapsed_ms,
                row_count=result.row_count,
                truncated=result.truncated,
            )
        )
        return result

    def close(self) -> None:
        """Fecha o runtime publicado e os aposentados. Idempotente."""
        self._registry.close_all()

    def __enter__(self) -> Gateway:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        # Nem adapter, nem DSN, nem politica.
        return "Gateway()"


def _to_query_result(masked: object) -> QueryResult:
    """Traduz o `MaskedResult` interno no modelo publico.

    O que se perde na traducao e o que nao deve sair: proveniencia, decisoes
    detalhadas, indices de regra e nomes de transformer.
    """
    from maskgw.db.result import MaskedResult  # noqa: PLC0415 - evita ciclo

    assert isinstance(masked, MaskedResult)  # noqa: S101
    columns = [
        QueryColumn(name=column.output_name, masked=decision.action is Action.MASK)
        for column, decision in zip(masked.columns, masked.decisions, strict=True)
    ]
    rows = [[jsonable(value) for value in row] for row in masked.rows]
    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=masked.row_count,
        truncated=masked.truncated,
    )


def _raise_gateway_error(category: ErrorCategory) -> NoReturn:
    """Levanta FORA do handler, para zerar `__cause__` e `__context__`."""
    raise GatewayError(category) from None
