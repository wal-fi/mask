"""Gateway: a fachada publica da aplicacao.

Unica camada que orquestra validacao, execucao, proveniencia, masking e
limites. A camada MCP chama SOMENTE isto — nunca `PostgresAdapter`, nunca
psycopg, nunca o Masking Engine.

Nada de logica nova aqui: a validacao e da Fase 4, o masking da Fase 1, a
proveniencia da Fase 3, os limites da Fase 4. O Gateway compoe e traduz.

Fronteira de erro: `Gateway.query` levanta APENAS `GatewayError`, com uma
categoria e uma mensagem fixa. A excecao interna nao e encadeada — nem por
`__cause__`, nem por `__context__` (D-017).
"""

from __future__ import annotations

import threading
import time
import uuid
from types import TracebackType
from typing import NoReturn

from maskgw.audit import FAILURE, SUCCESS, AuditLog, QueryAudit
from maskgw.db.postgres import PostgresAdapter
from maskgw.gateway.models import (
    ErrorCategory,
    GatewayError,
    QueryColumn,
    QueryResult,
    categorize,
    jsonable,
)
from maskgw.masking.engine import Action


class Gateway:
    """Orquestrador. A unica camada que toca o valor original."""

    def __init__(self, adapter: PostgresAdapter, audit: AuditLog) -> None:
        self._adapter = adapter
        self._audit = audit
        # O SDK MCP executa tools sincronas numa thread pool. Uma conexao
        # psycopg nao suporta consultas concorrentes intercaladas, e nao ha
        # pool nesta fase (D-034): as consultas sao serializadas aqui.
        self._lock = threading.Lock()

    def query(self, sql: str) -> QueryResult:
        """Executa uma consulta e devolve o resultado ja seguro."""
        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        category: ErrorCategory | None = None
        result: QueryResult | None = None

        try:
            with self._lock:
                # Idempotente quando ja aberta; reconecta com verificacao
                # completa se a conexao caiu. Ver D-034.
                self._adapter.connect()
                masked = self._adapter.execute_validated(sql)
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
        """Fecha a conexao. Idempotente."""
        with self._lock:
            self._adapter.close()

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
