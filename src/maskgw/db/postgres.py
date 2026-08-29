"""Adapter PostgreSQL.

Componente INTERNO da Fase 2. Nao ha superficie MCP nem cliente externo
ligado a ele: a validacao de SQL (allowlist de SELECT, bloqueio de multiplos
statements), o enforcement read-only, o `statement_timeout` e o limite de
linhas sao da Fase 4 e NAO estao implementados aqui.

Invariantes:

- Valor original nunca sai. `execute` devolve `MaskedResult`; o fetch cru vive
  num gerador privado, consumido inteiramente dentro de `execute`.
- A proveniencia de cada coluna vem da metadata do PostgreSQL, resolvida ANTES
  de qualquer linha ser lida. Nunca dos valores das linhas.
- Leitura em LOTES via `fetchmany`, para que o adapter nao dependa de carregar
  o result set inteiro em memoria. Isso e estrategia de consumo, nao row
  limiting: nenhuma linha e descartada.
- Erros do PostgreSQL saem sanitizados e SEM referencia a excecao original,
  nem por `__cause__` nem por `__context__`. Ver `_raise_sanitized`.
- A sessao nunca fica `idle in transaction`. Ver docs/DECISIONS.md (D-016).
- `conninfo` pode conter senha: nao aparece em `repr`, log ou erro.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator, Sequence
from types import TracebackType
from typing import Any, Final, NoReturn

import psycopg
from psycopg.rows import tuple_row

from maskgw.db.columns import describe_columns
from maskgw.db.provenance import ProvenanceResolver, provenance_keys
from maskgw.db.result import MaskedResult
from maskgw.db.sanitize import sanitize_error
from maskgw.errors import DatabaseError
from maskgw.masking.descriptor import ColumnDescriptor
from maskgw.masking.engine import MaskingEngine

#: Linhas buscadas por `fetchmany`. Nao e limite de resposta (Fase 4).
DEFAULT_BATCH_SIZE: Final = 500

_Connection = psycopg.Connection[tuple[Any, ...]]
_Cursor = psycopg.Cursor[tuple[Any, ...]]


class PostgresAdapter:
    """Executa consultas e devolve apenas result sets ja mascarados."""

    def __init__(
        self,
        conninfo: str,
        engine: MaskingEngine,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        if batch_size < 1:
            msg = "batch_size deve ser >= 1"
            raise ValueError(msg)
        # Guardado apenas para conectar; nunca exposto.
        self._conninfo = conninfo
        self._engine = engine
        self._batch_size = batch_size
        self._connection: _Connection | None = None
        self._provenance: ProvenanceResolver | None = None

    @property
    def closed(self) -> bool:
        connection = self._connection
        return connection is None or connection.closed

    def connect(self) -> None:
        """Abre a conexao, se ainda nao estiver aberta."""
        if not self.closed:
            return
        try:
            # autocommit: cada statement roda na propria transacao implicita e
            # a sessao volta a IDLE sozinha. Sem COMMIT explicito de operacao
            # arbitraria e compativel com o read-only da Fase 4.
            self._connection = psycopg.connect(
                self._conninfo,
                autocommit=True,
                row_factory=tuple_row,
            )
            # Cache de proveniencia vive junto com a conexao (D-021).
            self._provenance = ProvenanceResolver(self._connection)
        except psycopg.Error as exc:
            self._connection = None
            self._provenance = None
            failure = sanitize_error(exc)
        else:
            return
        _raise_sanitized(failure)

    def close(self) -> None:
        """Fecha a conexao. Idempotente."""
        connection, self._connection = self._connection, None
        self._provenance = None
        if connection is not None and not connection.closed:
            with contextlib.suppress(psycopg.Error):
                connection.close()

    def execute(self, query: str, params: Sequence[Any] | None = None) -> MaskedResult:
        """Executa uma consulta e devolve o result set ja mascarado."""
        connection = self._require_connection()
        failure: DatabaseError | None = None
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                columns = self._describe(cursor)
                decisions = tuple(self._engine.decide(column) for column in columns)
                rows = tuple(self._masked_batches(cursor, columns))
        except psycopg.Error as exc:
            # Guardado, nao levantado aqui: ver `_raise_sanitized`.
            failure = sanitize_error(exc)
        finally:
            # Roda inclusive quando uma excecao nao-psycopg esta a caminho.
            self._settle()

        if failure is not None:
            _raise_sanitized(failure)

        return MaskedResult(columns=columns, decisions=decisions, rows=rows)

    def _describe(self, cursor: _Cursor) -> tuple[ColumnDescriptor, ...]:
        """Monta os descritores, resolvendo a proveniencia antes do fetch.

        A ordem importa: `cursor.pgresult` e lido enquanto o resultado ainda
        esta intacto, e so depois as linhas sao buscadas.
        """
        keys = provenance_keys(cursor.pgresult, cursor.description)
        resolver = self._provenance
        origins = None if keys is None or resolver is None else resolver.resolve(keys)
        return describe_columns(cursor.description, origins)

    def _require_connection(self) -> _Connection:
        connection = self._connection
        if connection is None or connection.closed:
            msg = "conexao com o banco de dados nao esta aberta"
            raise DatabaseError(msg)
        return connection

    def _masked_batches(
        self,
        cursor: _Cursor,
        columns: tuple[ColumnDescriptor, ...],
    ) -> Iterator[tuple[Any, ...]]:
        """Le em lotes e mascara cada lote. Privado: linha crua nao escapa."""
        while True:
            batch = cursor.fetchmany(self._batch_size)
            if not batch:
                return
            for row in self._engine.mask_rows(columns, batch):
                yield tuple(row)

    def _settle(self) -> None:
        """Garante que a sessao nao fique `idle in transaction`.

        Em autocommit a transacao implicita ja se encerra sozinha; esta e uma
        rede de seguranca para o caso de algum caminho abrir transacao. Nunca
        faz COMMIT: se ha transacao pendente, ela e revertida.
        """
        connection = self._connection
        if connection is None or connection.closed:
            return
        try:
            if connection.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
                connection.rollback()
        except psycopg.Error:
            # Conexao inutilizavel. Fecha em vez de propagar detalhe do driver
            # — e de mascarar o erro original, ja que isto roda em `finally`.
            self.close()

    def __enter__(self) -> PostgresAdapter:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        # Nunca o conninfo: ele carrega usuario, host e senha.
        return f"PostgresAdapter(closed={self.closed})"


def _raise_sanitized(error: DatabaseError) -> NoReturn:
    """Levanta o erro ja sanitizado FORA do bloco `except` que o originou.

    `raise ... from None` zera `__cause__`, mas o interpretador ainda pendura a
    excecao original em `__context__` quando o `raise` acontece dentro de um
    handler ativo. O texto bruto do PostgreSQL — que pode conter valores, como
    em `invalid input syntax for type integer: "..."` — continuaria alcancavel
    por `error.__context__`, e qualquer formatador ou logger que percorra a
    cadeia o exporia.

    Levantar aqui, ja fora do handler, deixa `__cause__` e `__context__` nulos.
    """
    raise error from None
