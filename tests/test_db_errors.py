"""Sanitizacao de erros do PostgreSQL e estado transacional (Fase 2).

Criterio de aceite 5 da Fase 2: nenhum erro do PostgreSQL chega ao chamador
com o texto original. A mensagem do servidor pode embutir valores —
`invalid input syntax for type integer: "12345678901"` — e por isso nunca e
repassada, nem encadeada como `__cause__`.
"""

from __future__ import annotations

import datetime as dt
import traceback
from typing import Any, cast

import psycopg
import pytest

from maskgw.config import load_config_text
from maskgw.db.postgres import PostgresAdapter
from maskgw.db.sanitize import (
    GENERIC_MESSAGE,
    TIMEOUT_MESSAGE,
    classify,
    sanitize_error,
)
from maskgw.errors import DatabaseError, MaskGatewayError, QueryTimeout
from maskgw.masking.engine import MaskingEngine
from tests.conftest import INTRANS, FakeColumn, FakeConnection, FakeCursor

CPF = "11122233344"

#: Texto tipico do PostgreSQL: repare que ele CARREGA o valor.
LEAKY_MESSAGE = f'invalid input syntax for type integer: "{CPF}"'

CONFIG = "masking:\n  - match: cpf\n    transformer: md5\n"


def pg_error(sqlstate: str, message: str = LEAKY_MESSAGE) -> psycopg.Error:
    """Erro do psycopg com SQLSTATE e mensagem realistas."""
    error = psycopg.Error(message)
    error.sqlstate = sqlstate
    return error


@pytest.fixture
def engine(secrets):
    return MaskingEngine(load_config_text(CONFIG, secrets=secrets))


@pytest.fixture
def failing_adapter(engine):
    def _build(error, *, status=INTRANS):
        cursor = FakeCursor([FakeColumn("cpf")], [], error=error)
        connection = FakeConnection(cursor, transaction_status=status)
        adapter = PostgresAdapter("", engine)
        adapter._connection = cast("Any", connection)
        return adapter, connection

    return _build


class TestClassification:
    """SQLSTATE serve APENAS para escolher uma mensagem generica fixa."""

    @pytest.mark.parametrize(
        ("sqlstate", "fragment"),
        [
            ("08006", "comunicacao"),
            ("22P02", "dados"),
            ("23505", "integridade"),
            ("25P02", "transacao"),
            ("28P01", "autenticacao"),
            ("40001", "revertida"),
            ("42601", "invalida"),
            ("42P01", "invalida"),
            ("53200", "recursos"),
            ("54000", "limite"),
        ],
    )
    def test_class_selects_a_generic_message(self, sqlstate, fragment):
        assert fragment in str(sanitize_error(pg_error(sqlstate)))

    @pytest.mark.parametrize("sqlstate", ["XX000", "P0001", "", "9"])
    def test_unknown_class_falls_back_to_generic(self, sqlstate):
        assert str(sanitize_error(pg_error(sqlstate))) == GENERIC_MESSAGE

    def test_query_canceled_becomes_a_timeout(self):
        """`statement_timeout` produz 57014: o chamador distingue o caso."""
        error = sanitize_error(pg_error("57014", "canceling statement due to statement timeout"))
        assert isinstance(error, QueryTimeout)
        assert isinstance(error, DatabaseError)
        assert str(error) == TIMEOUT_MESSAGE
        assert "canceling statement" not in str(error)
        assert CPF not in str(error)

    def test_other_57_codes_are_not_timeouts(self):
        assert not isinstance(sanitize_error(pg_error("57P01")), QueryTimeout)

    def test_missing_sqlstate_falls_back_to_generic(self):
        assert str(sanitize_error(psycopg.Error(LEAKY_MESSAGE))) == GENERIC_MESSAGE

    def test_classify_is_the_two_character_class(self):
        assert classify(pg_error("42P01")) == "42"
        assert classify(psycopg.Error("x")) == ""

    def test_sqlstate_itself_never_reaches_the_message(self):
        """Classificacao e interna: o codigo nao vai junto ao chamador."""
        for sqlstate in ("42P01", "22P02", "23505", "XX000"):
            message = str(sanitize_error(pg_error(sqlstate)))
            assert sqlstate not in message
            assert sqlstate[:2] not in message


class TestNothingFromTheOriginalErrorEscapes:
    @pytest.mark.parametrize("sqlstate", ["22P02", "42P01", "23505", "XX000"])
    def test_value_is_never_in_the_message(self, sqlstate):
        assert CPF not in str(sanitize_error(pg_error(sqlstate)))

    def test_server_text_is_never_in_the_message(self):
        message = str(sanitize_error(pg_error("22P02")))
        assert "invalid input syntax" not in message
        assert LEAKY_MESSAGE not in message

    def test_result_is_a_plain_database_error(self):
        error = sanitize_error(pg_error("22P02"))
        assert isinstance(error, DatabaseError)
        assert isinstance(error, MaskGatewayError)
        assert not isinstance(error, psycopg.Error)

    def test_repr_carries_no_value_either(self):
        assert CPF not in repr(sanitize_error(pg_error("22P02")))

    def test_sanitized_error_has_no_diag_or_query(self):
        error = sanitize_error(pg_error("22P02"))
        for attribute in ("diag", "sqlstate", "query", "params", "pgresult", "pgconn"):
            assert not hasattr(error, attribute), attribute


class TestAdapterBoundary:
    def test_execute_raises_sanitized_error(self, failing_adapter):
        adapter, _ = failing_adapter(pg_error("22P02"))
        with pytest.raises(DatabaseError) as info:
            adapter.execute("SELECT cpf::int FROM cliente")
        assert CPF not in str(info.value)
        assert "invalid input syntax" not in str(info.value)

    def test_original_exception_is_not_chained(self, failing_adapter):
        """Nem `__cause__` nem `__context__` podem apontar para o erro bruto.

        `raise ... from None` sozinho NAO basta: o interpretador pendura a
        excecao original em `__context__` quando o `raise` ocorre dentro de um
        handler ativo, e o texto do PostgreSQL continuaria alcancavel.
        """
        adapter, _ = failing_adapter(pg_error("22P02"))
        with pytest.raises(DatabaseError) as info:
            adapter.execute("SELECT cpf::int FROM cliente")
        assert info.value.__cause__ is None
        assert info.value.__context__ is None
        assert info.value.__suppress_context__ is True

    def test_connect_failure_is_not_chained_either(self, engine, monkeypatch):
        def explode(*_args: object, **_kwargs: object) -> None:
            raise pg_error("08006")

        monkeypatch.setattr(psycopg, "connect", explode)
        with pytest.raises(DatabaseError) as info:
            PostgresAdapter("", engine).connect()
        assert info.value.__cause__ is None
        assert info.value.__context__ is None

    def test_whole_exception_chain_is_clean(self, failing_adapter):
        """Percorre `__cause__` E `__context__`: um logger seguiria os dois."""
        adapter, _ = failing_adapter(pg_error("22P02"))
        with pytest.raises(DatabaseError) as info:
            adapter.execute("SELECT cpf::int FROM cliente")

        seen: list[str] = []
        pending: list[BaseException] = [info.value]
        while pending:
            current = pending.pop()
            seen.append(str(current))
            pending.extend(
                link for link in (current.__cause__, current.__context__) if link is not None
            )
        assert CPF not in " ".join(seen)
        assert "invalid input syntax" not in " ".join(seen)

    def test_traceback_render_has_no_value(self, failing_adapter):
        """Render completo do traceback, do jeito que um handler faria."""
        adapter, _ = failing_adapter(pg_error("22P02"))
        with pytest.raises(DatabaseError) as info:
            adapter.execute("SELECT cpf::int FROM cliente")
        rendered = "".join(
            traceback.format_exception(type(info.value), info.value, info.value.__traceback__)
        )
        assert CPF not in rendered
        assert "invalid input syntax" not in rendered

    def test_connect_failure_is_sanitized(self, engine, monkeypatch):
        def explode(*_args: object, **_kwargs: object) -> None:
            raise pg_error("08006", "connection to server at ... failed: password authentication")

        monkeypatch.setattr(psycopg, "connect", explode)
        adapter = PostgresAdapter("host=x password=segredo-do-banco", engine)
        with pytest.raises(DatabaseError) as info:
            adapter.connect()
        assert "password" not in str(info.value)
        assert "segredo-do-banco" not in str(info.value)
        assert adapter.closed is True


class TestTransactionSettling:
    """A sessao nunca fica `idle in transaction` (D-016)."""

    def test_open_transaction_is_rolled_back_after_success(self, engine):
        cursor = FakeCursor([FakeColumn("cpf")], [(CPF,)])
        connection = FakeConnection(cursor, transaction_status=INTRANS)
        adapter = PostgresAdapter("", engine)
        adapter._connection = cast("Any", connection)
        adapter.execute("SELECT cpf FROM cliente")
        assert connection.rollbacks == 1
        assert connection.commits == 0
        assert connection.info.transaction_status is not INTRANS

    def test_open_transaction_is_rolled_back_after_error(self, failing_adapter):
        adapter, connection = failing_adapter(pg_error("42601"))
        with pytest.raises(DatabaseError):
            adapter.execute("SELECT")
        assert connection.rollbacks == 1
        assert connection.commits == 0

    def test_idle_connection_is_left_alone(self, engine):
        cursor = FakeCursor([FakeColumn("cpf")], [(CPF,)])
        connection = FakeConnection(cursor)
        adapter = PostgresAdapter("", engine)
        adapter._connection = cast("Any", connection)
        adapter.execute("SELECT cpf FROM cliente")
        assert connection.rollbacks == 0

    def test_failed_rollback_closes_instead_of_masking_the_error(self, failing_adapter):
        """A limpeza roda em `finally`: nao pode substituir o erro original."""
        adapter, connection = failing_adapter(pg_error("42601"))
        connection._rollback_error = psycopg.OperationalError("conexao morta")
        with pytest.raises(DatabaseError) as info:
            adapter.execute("SELECT")
        assert "invalida" in str(info.value)
        assert connection.closed is True
        assert adapter.closed is True

    def test_non_psycopg_error_still_settles(self, engine):
        """Falha da canonicalizacao tambem nao pode deixar transacao aberta."""
        cursor = FakeCursor([FakeColumn("cpf")], [(dt.timedelta(days=1),)])
        connection = FakeConnection(cursor, transaction_status=INTRANS)
        adapter = PostgresAdapter("", engine)
        adapter._connection = cast("Any", connection)
        with pytest.raises(MaskGatewayError):
            adapter.execute("SELECT intervalo AS cpf")
        assert connection.rollbacks == 1
        assert connection.commits == 0
