"""Sessoes de consulta sobre o registry multi-datasource (Fase 9, Etapa 3).

E o plano de dados futuro — PGWire (Etapas 7-10) e o MCP multi-datasource
(Etapa 11) — reduzido ao minimo verificavel: abrir uma sessao por alias,
executar SELECT pelo MESMO pipeline do Gateway e fechar. Nenhuma fronteira
externa usa isto ainda: nao ha listener, rota nem parametro novo no MCP.

O que a sessao garante, e por que:

- **pipeline unico** (F9-002): validator, sensitividade, execucao read-only,
  proveniencia, masking, limite de linhas e traducao para `QueryResult` sao os
  do `PostgresAdapter.execute_validated` e de `run_audited`, identicos ao MCP;
- **somente SELECT, tambem no PostgreSQL** (F9-003): cada sessao abre a sua
  conexao com `default_transaction_read_only=on` e `statement_timeout`
  conferidos, e a capability de proveniencia verificada;
- **destino fixo** (D-066/D-071): a sessao usa, ate o fim, a geracao que
  capturou na admissao; uma troca administrativa nunca a redireciona;
- **sem reconexao silenciosa**: uma conexao perdida encerra a utilidade da
  sessao (erro sanitizado), em vez de reabrir outra com estado diferente;
- **erros fixos**: consulta falha so com `GatewayError`; admissao recusada so
  com `DatasourceUnavailableError`/`DatasourceBusyError`, sem alias, destino
  ou excecao original.
"""

from __future__ import annotations

from types import TracebackType
from typing import NoReturn

from maskgw.audit import AuditLog
from maskgw.errors import CapabilityError, DatabaseError
from maskgw.gateway.models import ErrorCategory, GatewayError, QueryResult, categorize
from maskgw.gateway.service import run_audited, to_query_result
from maskgw.runtime.datasources import DatasourceLease, DatasourceRegistry


class DatasourceSession:
    """Uma sessao admitida, com conexao upstream propria."""

    __slots__ = ("_audit", "_lease")

    def __init__(self, lease: DatasourceLease, audit: AuditLog) -> None:
        self._lease = lease
        self._audit = audit

    @property
    def generation(self) -> int:
        """Geracao capturada na admissao. Metadata interna."""
        return self._lease.generation

    @property
    def closed(self) -> bool:
        return self._lease.closed

    def query(self, sql: str) -> QueryResult:
        """Executa um SELECT e devolve o resultado ja mascarado."""

        def operation() -> QueryResult:
            with self._lease.use() as adapter:
                return to_query_result(adapter.execute_validated(sql))

        return run_audited(self._audit, operation)

    def close(self) -> None:
        """Fecha a conexao e libera a geracao. Idempotente."""
        self._lease.close()

    def __enter__(self) -> DatasourceSession:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"DatasourceSession(generation={self.generation}, closed={self.closed})"


class DatasourceGateway:
    """Abre sessoes por alias. Nao conhece catalogo, store nem Admin."""

    __slots__ = ("_audit", "_registry")

    def __init__(self, registry: DatasourceRegistry, audit: AuditLog) -> None:
        self._registry = registry
        self._audit = audit

    def open_session(self, alias: str) -> DatasourceSession:
        """Admite e conecta. Falha de conexao vira `GatewayError` fixo."""
        category: ErrorCategory | None = None
        lease: DatasourceLease | None = None
        try:
            lease = self._registry.open_session(alias)
        except (DatabaseError, CapabilityError) as exc:
            category = categorize(exc)
        if category is not None or lease is None:
            _raise_gateway_error(category or ErrorCategory.DATABASE_ERROR)
        return DatasourceSession(lease, self._audit)

    def __repr__(self) -> str:
        return "DatasourceGateway()"


def _raise_gateway_error(category: ErrorCategory) -> NoReturn:
    """Levanta FORA do handler, para zerar `__cause__` e `__context__`."""
    raise GatewayError(category) from None


__all__ = ["DatasourceGateway", "DatasourceSession"]
