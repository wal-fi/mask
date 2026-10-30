"""Adapter PostgreSQL.

Componente INTERNO: nao ha superficie MCP ligada a ele (Fase 5).

Duas portas de entrada, deliberadamente distintas:

- `execute_validated(sql)` — passa pelo validator antes de tocar o banco. E o
  que um Gateway ou servidor MCP deve chamar.
- `execute(sql, params)` — NAO valida. Existe porque a seguranca nao pode
  depender so do parser: os testes chamam esta porta para provar que o
  PostgreSQL rejeita escrita mesmo com o validator deliberadamente contornado.

Invariantes:

- Valor original nunca sai. As duas portas devolvem `MaskedResult`; o fetch
  cru vive num gerador privado, consumido inteiramente dentro de `execute`.
- A proveniencia de cada coluna vem da metadata do PostgreSQL, resolvida ANTES
  de qualquer linha ser lida. Nunca dos valores das linhas.
- A analise de sensitividade por AST complementa a proveniencia onde ela nao
  alcanca (expressoes, UNION). Roda uma vez por consulta. Ver D-043.
- A sessao e read-only e tem `statement_timeout`, ambos aplicados pelo
  PostgreSQL e conferidos apos a conexao. Ver D-028.
- No maximo `max_rows` linhas saem. A linha N+1 e lida para detectar excesso,
  mas descartada ANTES do masking e nunca devolvida. Ver D-030.
- Leitura em LOTES via `fetchmany`: o adapter nao carrega o result set inteiro.
- Erros do PostgreSQL saem sanitizados e SEM referencia a excecao original,
  nem por `__cause__` nem por `__context__`. Ver `_raise_sanitized`.
- A sessao nunca fica `idle in transaction`. Ver D-016.
- `conninfo` pode conter senha: nao aparece em `repr`, log ou erro.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator, Sequence
from types import TracebackType
from typing import Any, Final, NoReturn

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import tuple_row

from maskgw.config.gateway import DatabaseSettings
from maskgw.db.capabilities import check_provenance_capability
from maskgw.db.columns import describe_columns
from maskgw.db.execution_error import classify_typed_error
from maskgw.db.provenance import ProvenanceResolver, provenance_keys
from maskgw.db.result import (
    MAX_WIRE_COLUMNS,
    WIRE_TEXT_OID,
    WIRE_TYPE_SIZES,
    DatabaseResultIntegrityError,
    DatabaseResultTypeError,
    MaskedResult,
    TypedMaskedResult,
)
from maskgw.db.sanitize import sanitize_error
from maskgw.db.session_state import SESSION_STATE_SQL, WorkerSessionState, WorkerSessionStateError
from maskgw.errors import CapabilityError, DatabaseError
from maskgw.masking.descriptor import ColumnDescriptor
from maskgw.masking.engine import Action, Decision, MaskingEngine
from maskgw.sql.policy import DEFAULT_SQL_POLICY, SqlPolicy
from maskgw.sql.sensitivity import Sensitivity, analyze_sensitivity
from maskgw.sql.validator import validate_select

#: Linhas buscadas por `fetchmany`. Nao e o limite de resposta: e `max_rows`.
DEFAULT_BATCH_SIZE: Final = 500

#: Espera maxima, em segundos, do pedido de cancelamento de `cancel`.
_CANCEL_TIMEOUT_SECONDS: Final = 5.0

#: Limites default, quando nenhuma configuracao e passada.
DEFAULT_SETTINGS: Final = DatabaseSettings(statement_timeout_ms=30_000, max_rows=1_000)

_SESSION_QUERY: Final = """
SELECT name, setting FROM pg_settings
WHERE name IN ('default_transaction_read_only', 'statement_timeout')
"""

#: Reexportado de proposito: a suite de seguranca instrumenta este simbolo
#: para provar que a analise roda uma vez por consulta, nunca por linha.
__all__ = ["DEFAULT_BATCH_SIZE", "DEFAULT_SETTINGS", "PostgresAdapter", "analyze_sensitivity"]

_Connection = psycopg.Connection[tuple[Any, ...]]
_Cursor = psycopg.Cursor[tuple[Any, ...]]


class PostgresAdapter:
    """Executa consultas e devolve apenas result sets ja mascarados."""

    def __init__(  # noqa: PLR0913 - limites e politicas, todos keyword-only
        self,
        conninfo: str,
        engine: MaskingEngine,
        *,
        settings: DatabaseSettings = DEFAULT_SETTINGS,
        sql_policy: SqlPolicy = DEFAULT_SQL_POLICY,
        batch_size: int = DEFAULT_BATCH_SIZE,
        verify_capabilities: bool = True,
    ) -> None:
        if batch_size < 1:
            msg = "batch_size deve ser >= 1"
            raise ValueError(msg)
        # Guardado apenas para conectar; nunca exposto.
        self._conninfo = conninfo
        self._engine = engine
        self._settings = settings
        self._sql_policy = sql_policy
        self._batch_size = batch_size
        self._verify_capabilities = verify_capabilities
        self._connection: _Connection | None = None
        self._provenance: ProvenanceResolver | None = None

    @property
    def closed(self) -> bool:
        connection = self._connection
        return connection is None or connection.closed

    @property
    def settings(self) -> DatabaseSettings:
        return self._settings

    def connect(self) -> None:
        """Abre a conexao, aplica os limites e confere que eles pegaram."""
        if not self.closed:
            return
        failure: DatabaseError | None = None
        try:
            # autocommit: cada statement roda na propria transacao implicita e
            # a sessao volta a IDLE sozinha. Sem COMMIT explicito de operacao
            # arbitraria. `options` chega ao backend na inicializacao, antes de
            # qualquer statement.
            self._connection = psycopg.connect(
                self._session_conninfo(),
                autocommit=True,
                row_factory=tuple_row,
            )
            # Cache de proveniencia vive junto com a conexao (D-021).
            self._provenance = ProvenanceResolver(self._connection)
        except psycopg.Error as exc:
            self._connection = None
            self._provenance = None
            failure = sanitize_error(exc)
        if failure is not None:
            _raise_sanitized(failure)

        try:
            self._verify_session()
            if self._verify_capabilities:
                check_provenance_capability(self._require_connection())
        except CapabilityError:
            self.close()
            raise

    def cancel(self) -> None:
        """Pede ao servidor o cancelamento do statement em andamento.

        Unico metodo seguro para chamar de OUTRA thread enquanto `execute`
        roda: usa o protocolo de cancelamento do PostgreSQL por uma conexao
        propria (`cancel_safe`), sem tocar no estado da conexao em uso. A
        consulta cancelada termina na thread que a executava, com erro ja
        sanitizado. Sem conexao aberta, nao faz nada. Falha do pedido e
        silenciosa: cancelar e melhor esforco, e o `statement_timeout` continua
        limitando a execucao (Fase 9, Etapa 3).
        """
        connection = self._connection
        if connection is None or connection.closed:
            return
        with contextlib.suppress(psycopg.Error):
            cancel_safe = getattr(connection, "cancel_safe", None)
            if cancel_safe is not None:
                cancel_safe(timeout=_CANCEL_TIMEOUT_SECONDS)
            else:
                # psycopg < 3.2, ainda aceito pelo pyproject: mesmo protocolo
                # de cancelamento, sem o timeout configuravel.
                connection.cancel()

    def close(self) -> None:
        """Fecha a conexao. Idempotente."""
        connection, self._connection = self._connection, None
        self._provenance = None
        if connection is not None and not connection.closed:
            with contextlib.suppress(psycopg.Error):
                connection.close()

    def execute_validated(self, sql: str) -> MaskedResult:
        """Valida, analisa a sensitividade e so entao executa.

        Porta de entrada de qualquer chamador nao confiavel. `InvalidQuery` e
        `QueryRejected` sao levantadas antes de o banco ver a consulta.

        A analise de AST roda UMA VEZ por consulta, nunca por linha: o
        resultado e um indice de regra por posicao, que os descritores
        carregam. Ver D-043.
        """
        return self.execute(sql, sensitivity=self._validated_sensitivity(sql))

    def _validated_sensitivity(self, sql: str) -> Sensitivity | None:
        statement = validate_select(sql, policy=self._sql_policy)
        return analyze_sensitivity(statement, self._engine.policy)

    def _execute_typed_validated(self, sql: str) -> TypedMaskedResult:
        """Internal worker opt-in: same pipeline, plus advertised OIDs before fetch.

        No operational caller yet. Legacy API and cursor behavior are unchanged.
        Source type is never read/retained for a MASK column, announced as text.
        """
        result, oids = self._run(sql, sensitivity=self._validated_sensitivity(sql), typed=True)
        return TypedMaskedResult(result, oids)

    def _typed_connection_healthy(self) -> bool:
        """Local state after settle, under the owner's exclusive connection use.

        No I/O or mutation. This does not prove a live network, read-only
        settings or future success: a peer may have closed without libpq
        noticing. Error intent must separately permit continuation. Nothing
        operational calls this method until the worker is integrated.
        """
        connection = self._connection
        if connection is None:
            return False
        try:
            return (
                connection.closed is False
                and connection.broken is False
                and connection.info.status is psycopg.pq.ConnStatus.OK
                and connection.info.transaction_status is psycopg.pq.TransactionStatus.IDLE
            )
        except Exception:
            return False

    def _worker_session_state(self) -> WorkerSessionState:
        """Opt-in W1 metadata probe; parent never receives this private record.

        Call exclusively in the worker before and after every job, within the
        same hard parent deadline. Failure is fatal; never reset or reconnect.
        No current caller. Legacy connect/execute behavior is unchanged.
        """
        state: WorkerSessionState | None = None
        row: tuple[Any, ...] | None = None
        try:
            if not self._typed_connection_healthy():
                raise WorkerSessionStateError()
            connection = self._require_connection()
            with connection.cursor() as cursor:
                cursor.execute(SESSION_STATE_SQL)
                row = cursor.fetchone()
                if row is None or cursor.fetchone() is not None:
                    raise WorkerSessionStateError()
                state = WorkerSessionState(row)
            if not self._typed_connection_healthy():
                state = None
        except MemoryError:
            raise
        except Exception:
            state = None
        row = None
        if state is None:
            raise WorkerSessionStateError()
        return state

    def execute(
        self,
        query: str,
        params: Sequence[Any] | None = None,
        *,
        sensitivity: Sensitivity | None = None,
    ) -> MaskedResult:
        """Executa SEM validar e devolve o result set ja mascarado.

        Porta interna. A protecao contra escrita aqui e o privilegio do
        PostgreSQL, nao o validator — e disso que dependem os testes de defesa
        em profundidade.
        """
        result, _ = self._run(query, params, sensitivity=sensitivity, typed=False)
        return result

    def _run(
        self,
        query: str,
        params: Sequence[Any] | None = None,
        *,
        sensitivity: Sensitivity | None,
        typed: bool,
    ) -> tuple[MaskedResult, tuple[int, ...]]:
        """Single execution/provenance/masking/settle body for both result APIs."""
        connection = self._require_connection()
        failure: DatabaseError | None = None
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                columns = self._describe(cursor, sensitivity)
                decisions = tuple(self._engine.decide(column) for column in columns)
                oids = self._typed_oids(cursor, decisions) if typed else ()
                rows, truncated = self._read_masked(cursor, columns)
        except psycopg.Error as exc:
            # Guardado, nao levantado aqui: ver `_raise_sanitized`.
            failure = classify_typed_error(exc) if typed else sanitize_error(exc)
        finally:
            # Roda inclusive quando uma excecao nao-psycopg esta a caminho.
            self._settle()

        if failure is not None:
            _raise_sanitized(failure)

        return (
            MaskedResult(columns=columns, decisions=decisions, rows=rows, truncated=truncated),
            oids,
        )

    @staticmethod
    def _typed_oids(cursor: _Cursor, decisions: tuple[Decision, ...]) -> tuple[int, ...]:
        description = cursor.description
        if description is None or not 1 <= len(description) <= MAX_WIRE_COLUMNS:
            raise DatabaseResultTypeError from None
        if len(description) != len(decisions):
            raise DatabaseResultIntegrityError from None
        result: list[int] = []
        for column, decision in zip(description, decisions, strict=True):
            if decision.action is Action.MASK:
                result.append(WIRE_TEXT_OID)
                continue
            oid: object = None
            memory_failed = False
            integrity_failed = False
            try:
                oid = column.type_code
            except MemoryError:
                memory_failed = True
            except AttributeError:
                oid = None
            except Exception:
                integrity_failed = True
            if memory_failed:
                raise MemoryError from None  # fatal worker condition, never recoverable TYPE
            if integrity_failed:
                raise DatabaseResultIntegrityError from None
            if type(oid) is not int or oid not in WIRE_TYPE_SIZES:
                raise DatabaseResultTypeError from None
            result.append(oid)
        return tuple(result)

    def _session_conninfo(self) -> str:
        """DSN com os limites de execucao anexados em `options`.

        Os `-c` do Gateway vao por ultimo: em caso de conflito com o que ja
        estava no DSN, prevalece o ultimo.
        """
        existing = conninfo_to_dict(self._conninfo).get("options")
        ours = (
            "-c default_transaction_read_only=on "
            f"-c statement_timeout={self._settings.statement_timeout_ms}"
        )
        options = f"{existing} {ours}" if isinstance(existing, str) and existing else ours
        return make_conninfo(self._conninfo, options=options)

    def _verify_session(self) -> None:
        """Confere que read-only e timeout realmente valem nesta sessao.

        Um DSN com `options` conflitante, um pooler que reescreve parametros ou
        um `ALTER ROLE ... SET` poderiam neutralizar os limites em silencio.
        """
        connection = self._require_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(_SESSION_QUERY)
                settings: dict[str, str] = dict(cursor.fetchall())
        except psycopg.Error:
            settings = {}

        expected = {
            "default_transaction_read_only": "on",
            "statement_timeout": str(self._settings.statement_timeout_ms),
        }
        for name, wanted in expected.items():
            if settings.get(name) != wanted:
                # Nomes de parametro do PostgreSQL: constantes, nunca dado.
                msg = (
                    f"a sessao nao aplicou o limite de execucao {name!r}; "
                    "o Gateway nao opera sem read-only e statement_timeout"
                )
                raise CapabilityError(msg)

    def _describe(
        self, cursor: _Cursor, sensitivity: Sensitivity | None = None
    ) -> tuple[ColumnDescriptor, ...]:
        """Monta os descritores, resolvendo a proveniencia antes do fetch.

        A ordem importa: `cursor.pgresult` e lido enquanto o resultado ainda
        esta intacto, e so depois as linhas sao buscadas.
        """
        keys = provenance_keys(cursor.pgresult, cursor.description)
        resolver = self._provenance
        origins = None if keys is None or resolver is None else resolver.resolve(keys)
        return describe_columns(cursor.description, origins, sensitivity)

    def _require_connection(self) -> _Connection:
        connection = self._connection
        if connection is None or connection.closed:
            msg = "conexao com o banco de dados nao esta aberta"
            raise DatabaseError(msg)
        return connection

    def _read_masked(
        self,
        cursor: _Cursor,
        columns: tuple[ColumnDescriptor, ...],
    ) -> tuple[tuple[tuple[Any, ...], ...], bool]:
        """Le em lotes, mascara e corta em `max_rows`.

        Busca deliberadamente UMA linha alem do limite, para saber se havia
        mais. Essa linha e descartada antes do masking: ela nunca e
        transformada e nunca chega ao chamador.
        """
        limit = self._settings.max_rows
        masked: list[tuple[Any, ...]] = []
        truncated = False

        while True:
            wanted = min(self._batch_size, limit - len(masked) + 1)
            batch = cursor.fetchmany(wanted)
            if not batch:
                break
            if len(masked) + len(batch) > limit:
                batch = batch[: limit - len(masked)]
                truncated = True
                masked.extend(self._mask(columns, batch))
                break
            masked.extend(self._mask(columns, batch))

        return tuple(masked), truncated

    def _mask(
        self,
        columns: tuple[ColumnDescriptor, ...],
        batch: Sequence[Sequence[Any]],
    ) -> Iterator[tuple[Any, ...]]:
        return (tuple(row) for row in self._engine.mask_rows(columns, batch))

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
