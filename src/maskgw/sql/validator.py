"""Validacao de SQL por allowlist de nos da AST.

Decisoes tomadas sobre a arvore que o proprio PostgreSQL produz, nunca por
texto. `docs/SECURITY.md`: allowlist, jamais blocklist de palavras-chave.

Quatro regras, nesta ordem:

1. **Um statement executavel.** Ver `parser.parse_single_statement`.
2. **Raiz `SelectStmt`.** Qualquer outro tipo de statement e recusado — e isso
   cobre INSERT, UPDATE, DELETE, MERGE, CREATE, ALTER, DROP, TRUNCATE, GRANT,
   REVOKE, COPY, CALL, DO, VACUUM, ANALYZE, REFRESH, SET e RESET sem que
   nenhum deles precise ser nomeado.
3. **Nenhum outro statement em lugar nenhum da arvore.** Raiz `SelectStmt` NAO
   basta: `WITH x AS (DELETE ... RETURNING *) SELECT * FROM x` tem raiz
   `SelectStmt`. A arvore inteira e percorrida, e todo no `*Stmt` que nao seja
   `SelectStmt` ou `RawStmt` derruba a consulta — CTE, CTE aninhada ou CTE
   dentro de subquery, indiferentemente.
4. **Clausulas de escrita disfarcadas de SELECT.** Medido: `SELECT 1 INTO t`
   parseia como `SelectStmt` e CRIA UMA TABELA. `IntoClause` e
   `LockingClause` (`FOR UPDATE`/`FOR SHARE`) sao recusadas em qualquer ponto
   da arvore.

Depois disso, a politica de `policy.py` e aplicada a cada `FuncCall` e a cada
`RangeVar` — a segunda para barrar as relacoes de estatistica do catalogo, que
guardam amostras reais dos dados e nao metadata (D-039).

Nenhuma mensagem de erro contem a consulta, nomes vindos dela ou valores. O
motivo vem de um conjunto fixo de constantes.
"""

from __future__ import annotations

from typing import Final

from pglast import ast
from pglast.visitors import Visitor

from maskgw.errors import QueryRejected
from maskgw.sql.parser import parse_single_statement
from maskgw.sql.policy import DEFAULT_SQL_POLICY, SqlPolicy

#: Motivos de rejeicao. Conjunto FIXO: nada aqui vem da consulta.
NOT_A_SELECT: Final = "somente SELECT e permitido"
NESTED_STATEMENT: Final = "statement que modifica dados dentro da consulta"
WRITES_A_RELATION: Final = "SELECT que grava em relacao (INTO)"
LOCKS_ROWS: Final = "SELECT que trava linhas (FOR UPDATE/SHARE)"
FORBIDDEN_FUNCTION: Final = "funcao nao permitida"
FORBIDDEN_RELATION: Final = "relacao nao permitida"

#: Unicos nos de statement aceitos em qualquer ponto da arvore.
_ALLOWED_STATEMENTS: Final[tuple[type, ...]] = (ast.RawStmt, ast.SelectStmt)


def _is_statement(node: object) -> bool:
    """Um no de statement da AST do PostgreSQL.

    Criterio estrutural, extraido da taxonomia do pglast — nao uma lista de
    palavras-chave mantida a mao. Toda classe de statement da gramatica
    termina em `Stmt`, e sao 117 delas.
    """
    return type(node).__name__.endswith("Stmt")


class _Inspector(Visitor):
    """Percorre a arvore inteira e coleta a primeira violacao encontrada."""

    def __init__(self, policy: SqlPolicy) -> None:
        super().__init__()
        self._policy = policy
        self.reason: str | None = None

    def visit(self, ancestors: object, node: object) -> None:  # noqa: ARG002
        if self.reason is not None:
            return

        if _is_statement(node) and not isinstance(node, _ALLOWED_STATEMENTS):
            self.reason = NESTED_STATEMENT
        elif isinstance(node, ast.IntoClause):
            self.reason = WRITES_A_RELATION
        elif isinstance(node, ast.LockingClause):
            self.reason = LOCKS_ROWS
        elif isinstance(node, ast.FuncCall) and not self._allows(node):
            self.reason = FORBIDDEN_FUNCTION
        elif isinstance(node, ast.RangeVar) and not self._allows_relation(node):
            self.reason = FORBIDDEN_RELATION

    def _allows(self, node: ast.FuncCall) -> bool:
        name = _function_name(node)
        return name is None or self._policy.allows(name)

    def _allows_relation(self, node: ast.RangeVar) -> bool:
        name = node.relname
        return not isinstance(name, str) or self._policy.allows_relation(name)


def _function_name(node: ast.FuncCall) -> str | None:
    """Nome final da funcao, sem o schema. O parser ja normalizou o caixa."""
    parts = node.funcname
    if not parts:
        return None
    last = parts[-1]
    value = getattr(last, "sval", None)
    return value if isinstance(value, str) else None


def validate_select(sql: str, *, policy: SqlPolicy = DEFAULT_SQL_POLICY) -> ast.RawStmt:
    """Valida a consulta e devolve a arvore, ou levanta.

    `InvalidQuery` para SQL malformada; `QueryRejected` para SQL valida que a
    politica recusa. Nenhuma das duas cita a consulta.
    """
    statement = parse_single_statement(sql)

    if not isinstance(statement.stmt, ast.SelectStmt):
        raise QueryRejected(NOT_A_SELECT)

    inspector = _Inspector(policy)
    inspector(statement)
    if inspector.reason is not None:
        raise QueryRejected(inspector.reason)

    return statement
