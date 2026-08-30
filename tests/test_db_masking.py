"""ResultSet Masking sobre o adapter (Fase 2), sem depender de banco.

Os criterios de aceite da fase sao verificados aqui com dublês, e de novo
contra PostgreSQL real em `tests/test_db_integration.py`.

O que se prova aqui: o adapter aplica a politica coluna a coluna, na posicao
correta, em lotes, preservando NULL e preservando o tipo original das colunas
que nao casam nenhuma regra.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import psycopg
import pytest

from maskgw.config import load_config_text
from maskgw.db.columns import ColumnOrigin
from maskgw.db.postgres import DEFAULT_BATCH_SIZE, PostgresAdapter
from maskgw.db.result import MaskedResult
from maskgw.errors import DatabaseError, TransformerError
from maskgw.masking.descriptor import ProvenanceKind
from maskgw.masking.engine import Action, MaskingEngine
from tests.conftest import (
    NO_ORIGIN,
    TEST_HMAC_KEY,
    FakeColumn,
    FakeConnection,
    FakeCursor,
    FakeResolver,
    origin_key,
)

CPF = "11122233344"
EMAIL = "joao.silva@empresa.com.br"

CONFIG = """
masking:
  - match: cpf
    transformer: hmac_sha256
  - match: email
    transformer: regex
    config:
      pattern: "^(.{2}).*(@.*)$"
      replacement: "\\\\1***\\\\2"
  - match: senha
    transformer: fixed
    config:
      value: "[REDACTED]"

exceptions:
  - match: tipo_cpf
    mode: exact
"""


def hmac_of(text: str) -> str:
    """HMAC esperado, calculado de forma independente do codigo sob teste."""
    return hmac.new(TEST_HMAC_KEY.encode(), text.encode(), hashlib.sha256).hexdigest()


@pytest.fixture
def engine(secrets):
    return MaskingEngine(load_config_text(CONFIG, secrets=secrets))


@pytest.fixture
def adapter_factory(engine):
    """Monta um adapter ja ligado a uma conexao falsa.

    `origins` e posicional e alinhado a `names`: `None` numa posicao significa
    que o PostgreSQL nao informou origem (`ftable = 0`), e uma `ColumnOrigin`
    significa proveniencia resolvida.
    """

    def _build(names, rows=(), *, origins=None, error=None, batch_size=DEFAULT_BATCH_SIZE):
        origins = list(origins) if origins is not None else [None] * len(names)
        keys = [
            NO_ORIGIN if origin is None else origin_key(index)
            for index, origin in enumerate(origins)
        ]
        resolved = {
            origin_key(index): origin for index, origin in enumerate(origins) if origin is not None
        }
        cursor = FakeCursor([FakeColumn(name) for name in names], rows, error=error, keys=keys)
        connection = FakeConnection(cursor)
        adapter = PostgresAdapter("", engine, batch_size=batch_size)
        adapter._connection = cast("Any", connection)
        adapter._provenance = cast("Any", FakeResolver(resolved))
        return adapter, connection, cursor

    return _build


def direct(name: str, table: str = "cliente", schema: str = "public") -> ColumnOrigin:
    """Origem resolvida numa tabela."""
    return ColumnOrigin(kind=ProvenanceKind.DIRECT, name=name, schema=schema, table=table)


class TestAcceptanceCriteria:
    """Criterios 1 a 4 da Fase 2 (docs/ROADMAP.md)."""

    def test_select_cpf_returns_masked_value(self, adapter_factory):
        adapter, _, _ = adapter_factory(["cpf"], [(CPF,)])
        result = adapter.execute("SELECT cpf FROM cliente")
        assert result.rows == ((hmac_of(CPF),),)
        assert result.rows[0][0] != CPF

    def test_select_star_masks_every_matching_column(self, adapter_factory):
        adapter, _, _ = adapter_factory(
            ["id", "nome", "cpf", "email", "senha", "tipo_cpf"],
            [(7, "Maria", CPF, EMAIL, "s3cr3t", "fisica")],
        )
        result = adapter.execute("SELECT * FROM cliente")
        assert result.rows == (
            (7, "Maria", hmac_of(CPF), "jo***@empresa.com.br", "[REDACTED]", "fisica"),
        )

    def test_distinct_transformers_per_column(self, adapter_factory):
        adapter, _, _ = adapter_factory(["cpf", "email"], [(CPF, EMAIL)])
        result = adapter.execute("SELECT cpf, email FROM cliente")
        assert result.rows[0][0] == hmac_of(CPF)
        assert result.rows[0][1] == "jo***@empresa.com.br"

    def test_null_stays_null(self, adapter_factory):
        adapter, _, _ = adapter_factory(["cpf", "email", "nome"], [(None, None, None)])
        assert adapter.execute("SELECT cpf, email, nome FROM cliente").rows == ((None, None, None),)

    def test_null_alongside_values(self, adapter_factory):
        adapter, _, _ = adapter_factory(["cpf", "nome"], [(None, "Maria"), (CPF, None)])
        result = adapter.execute("SELECT cpf, nome FROM cliente")
        assert result.rows == ((None, "Maria"), (hmac_of(CPF), None))


class TestExceptionPriority:
    def test_exception_column_passes_original(self, adapter_factory):
        adapter, _, _ = adapter_factory(["tipo_cpf"], [("fisica",)])
        assert adapter.execute("SELECT tipo_cpf FROM cliente").rows == (("fisica",),)

    def test_contains_still_masks_the_others(self, adapter_factory):
        adapter, _, _ = adapter_factory(["num_cpf", "cpf_cliente"], [(CPF, CPF)])
        result = adapter.execute("SELECT num_cpf, cpf_cliente FROM cliente")
        assert result.rows == ((hmac_of(CPF), hmac_of(CPF)),)


class TestAliasProtection:
    """Fase 3: a proveniencia fecha o bypass por alias.

    Estes testes INVERTEM `TestPhaseTwoAliasGap`, que na Fase 2 fixava
    `SELECT cpf AS documento` passando em claro.
    """

    def test_alias_is_masked_by_origin(self, adapter_factory):
        adapter, _, _ = adapter_factory(["documento"], [(CPF,)], origins=[direct("cpf")])
        result = adapter.execute("SELECT cpf AS documento FROM cliente")
        assert result.rows == ((hmac_of(CPF),),)
        assert result.rows[0][0] != CPF
        assert result.decisions[0].action is Action.MASK

    def test_descriptor_carries_the_full_origin(self, adapter_factory):
        adapter, _, _ = adapter_factory(["documento"], [(CPF,)], origins=[direct("cpf")])
        column = adapter.execute("SELECT cpf AS documento FROM cliente").columns[0]
        assert column.output_name == "documento"
        assert column.origin_name == "cpf"
        assert column.origin_schema == "public"
        assert column.origin_table == "cliente"
        assert column.provenance_kind is ProvenanceKind.DIRECT
        assert column.qualified_origin == "public.cliente.cpf"

    def test_alias_cannot_create_an_exception(self, adapter_factory):
        """Fase 6.1 (D-042): a origem responde pela exception, nao o alias."""
        adapter, _, _ = adapter_factory(["tipo_cpf"], [(CPF,)], origins=[direct("cpf")])
        result = adapter.execute("SELECT cpf AS tipo_cpf FROM cliente")
        assert result.rows == ((hmac_of(CPF),),)
        assert result.decisions[0].action is Action.MASK

    def test_exception_matching_by_origin_wins(self, adapter_factory):
        adapter, _, _ = adapter_factory(["qualquer"], [("fisica",)], origins=[direct("tipo_cpf")])
        assert adapter.execute("SELECT tipo_cpf AS qualquer FROM cliente").rows == (("fisica",),)

    def test_output_name_alone_is_still_enough(self, adapter_factory):
        """Origem que nao casa nao anula um `output_name` que casa."""
        adapter, _, _ = adapter_factory(["cpf_cliente"], [(CPF,)], origins=[direct("documento")])
        assert adapter.execute("SELECT documento AS cpf_cliente FROM cliente").rows == (
            (hmac_of(CPF),),
        )

    def test_default_allow_is_unchanged(self, adapter_factory):
        """Nem nome nem origem casam: o valor continua passando."""
        adapter, _, _ = adapter_factory(["nome"], [("Maria",)], origins=[direct("nome")])
        result = adapter.execute("SELECT nome FROM cliente")
        assert result.rows == (("Maria",),)
        assert result.decisions[0].action is Action.ALLOW


class TestDerivedColumnsFallBackToOutputName:
    """`ftable = 0`: nao ha origem, e o matching recai sobre o nome de saida."""

    def test_derived_column_has_no_origin(self, adapter_factory):
        adapter, _, _ = adapter_factory(["md5"], [("abc",)])
        column = adapter.execute("SELECT md5(cpf) FROM cliente").columns[0]
        assert column.origin_name is None
        assert column.provenance_kind is ProvenanceKind.DERIVED

    def test_derived_column_still_matches_by_output_name(self, adapter_factory):
        adapter, _, _ = adapter_factory(["cpf"], [(CPF,)])
        assert adapter.execute("SELECT ... AS cpf").rows == ((hmac_of(CPF),),)

    def test_derived_column_without_a_matching_name_passes(self, adapter_factory):
        """Bypass residual do MVP, documentado em FUTURE-HARDENING."""
        adapter, _, _ = adapter_factory(["x"], [(CPF,)])
        result = adapter.execute("SELECT substr(cpf,1,3) AS x FROM cliente")
        assert result.rows == ((CPF,),)
        assert result.decisions[0].action is Action.ALLOW


class TestTypePreservation:
    """Coluna SEM transformacao preserva o objeto Python do psycopg."""

    @pytest.mark.parametrize(
        "value",
        [
            42,
            Decimal("1234.50"),
            dt.date(2026, 8, 29),
            dt.datetime(2026, 8, 29, 13, 45, 7, tzinfo=dt.UTC),
            UUID("2f6b0e5c-2b4a-4c1e-9a3d-6f1c0b8e7d42"),
            {"chave": "valor"},
            [1, 2, 3],
            b"binario",
            True,
            dt.timedelta(days=1),
        ],
    )
    def test_unmatched_column_keeps_the_original_object(self, adapter_factory, value):
        adapter, _, _ = adapter_factory(["saldo"], [(value,)])
        returned = adapter.execute("SELECT saldo FROM cliente").rows[0][0]
        assert returned is value
        assert type(returned) is type(value)

    def test_masked_column_becomes_text(self, adapter_factory):
        adapter, _, _ = adapter_factory(["cpf"], [(12345678901,)])
        returned = adapter.execute("SELECT cpf FROM cliente").rows[0][0]
        assert returned == hmac_of("12345678901")
        assert isinstance(returned, str)

    @pytest.mark.parametrize(
        ("value", "canonical"),
        [
            (Decimal("1234.50"), "1234.50"),
            (dt.date(2026, 8, 29), "2026-08-29"),
            (True, "true"),
            (b"ab", "YWI="),
            (memoryview(b"ab"), "YWI="),
            ({"b": 1, "a": 2}, '{"a":2,"b":1}'),
        ],
    )
    def test_masked_column_uses_canonical_form(self, adapter_factory, value, canonical):
        adapter, _, _ = adapter_factory(["cpf"], [(value,)])
        assert adapter.execute("SELECT x AS cpf").rows[0][0] == hmac_of(canonical)

    def test_unsupported_type_fails_closed(self, adapter_factory):
        """Nao ha fallback para `str()`: a consulta falha em vez de vazar."""
        adapter, _, _ = adapter_factory(["cpf"], [(dt.timedelta(days=1),)])
        with pytest.raises(TransformerError, match="tipo nao suportado"):
            adapter.execute("SELECT intervalo AS cpf")


class TestPositionalRows:
    def test_duplicate_column_names_are_not_collapsed(self, adapter_factory):
        adapter, _, _ = adapter_factory(["cpf", "cpf"], [(CPF, "99988877766")])
        result = adapter.execute("SELECT cpf, cpf FROM cliente")
        assert result.rows == ((hmac_of(CPF), hmac_of("99988877766")),)
        assert result.column_names == ("cpf", "cpf")

    def test_duplicate_names_with_different_policies(self, adapter_factory):
        """Mesmo nome repetido nao pode fazer uma posicao herdar a outra."""
        adapter, _, _ = adapter_factory(["nome", "cpf", "nome"], [("a", CPF, "b")])
        assert adapter.execute("SELECT ...").rows == (("a", hmac_of(CPF), "b"),)

    def test_rows_are_tuples(self, adapter_factory):
        adapter, _, _ = adapter_factory(["cpf"], [(CPF,)])
        result = adapter.execute("SELECT cpf FROM cliente")
        assert isinstance(result.rows, tuple)
        assert all(isinstance(row, tuple) for row in result.rows)


class TestBatching:
    """Leitura em lotes: o adapter nao depende de carregar tudo em memoria."""

    def test_uses_fetchmany_with_the_configured_size(self, adapter_factory):
        adapter, _, cursor = adapter_factory(["cpf"], [(CPF,)] * 10, batch_size=4)
        adapter.execute("SELECT cpf FROM cliente")
        assert cursor.batch_sizes == [4, 4, 4, 4]

    def test_every_row_survives_the_batching(self, adapter_factory):
        rows = [(f"{index:011d}",) for index in range(25)]
        adapter, _, _ = adapter_factory(["cpf"], rows, batch_size=4)
        result = adapter.execute("SELECT cpf FROM cliente")
        assert result.row_count == 25
        assert result.rows == tuple((hmac_of(row[0]),) for row in rows)

    def test_batching_does_not_change_the_output(self, adapter_factory):
        rows = [(f"{index:011d}", None) for index in range(7)]
        one, _, _ = adapter_factory(["cpf", "nome"], rows, batch_size=1)
        big, _, _ = adapter_factory(["cpf", "nome"], rows, batch_size=1000)
        assert one.execute("SELECT ...").rows == big.execute("SELECT ...").rows

    def test_default_batch_size_is_bounded(self):
        assert 1 <= DEFAULT_BATCH_SIZE <= 10_000

    def test_batch_size_must_be_positive(self, engine):
        with pytest.raises(ValueError, match="batch_size"):
            PostgresAdapter("", engine, batch_size=0)


class TestEmptyResults:
    def test_zero_rows_with_columns(self, adapter_factory):
        adapter, _, _ = adapter_factory(["cpf", "email"], [])
        result = adapter.execute("SELECT cpf, email FROM cliente WHERE false")
        assert result.rows == ()
        assert result.column_names == ("cpf", "email")
        assert result.row_count == 0

    def test_no_result_set_fails_closed(self, adapter_factory):
        adapter, _, _ = adapter_factory([], [])
        adapter._connection._cursor.description = None
        with pytest.raises(DatabaseError, match="result set"):
            adapter.execute("SET statement_timeout = 0")


class TestDecisions:
    def test_decisions_align_with_columns(self, adapter_factory):
        adapter, _, _ = adapter_factory(["cpf", "nome", "tipo_cpf"], [(CPF, "Maria", "fisica")])
        result = adapter.execute("SELECT ...")
        assert [decision.action for decision in result.decisions] == [
            Action.MASK,
            Action.ALLOW,
            Action.EXCEPTION,
        ]

    def test_decision_reports_the_transformer(self, adapter_factory):
        adapter, _, _ = adapter_factory(["cpf"], [(CPF,)])
        assert adapter.execute("SELECT cpf").decisions[0].transformer_name == "hmac_sha256"


class TestResultInvariants:
    def test_arity_mismatch_is_rejected(self):
        with pytest.raises(ValueError, match="valores para"):
            MaskedResult(columns=(), decisions=(), rows=((1,),))

    def test_decision_count_must_match(self, adapter_factory):
        adapter, _, _ = adapter_factory(["cpf"], [(CPF,)])
        result = adapter.execute("SELECT cpf")
        with pytest.raises(ValueError, match="decisoes para"):
            MaskedResult(columns=result.columns, decisions=(), rows=result.rows)

    def test_iteration_yields_masked_rows(self, adapter_factory):
        adapter, _, _ = adapter_factory(["cpf"], [(CPF,)])
        assert list(adapter.execute("SELECT cpf")) == [(hmac_of(CPF),)]

    def test_len_is_the_row_count(self, adapter_factory):
        adapter, _, _ = adapter_factory(["cpf"], [(CPF,)] * 3)
        assert len(adapter.execute("SELECT cpf")) == 3


class TestConnectionState:
    def test_execute_without_connection_fails(self, engine):
        adapter = PostgresAdapter("", engine)
        with pytest.raises(DatabaseError, match="nao esta aberta"):
            adapter.execute("SELECT 1")

    def test_query_and_params_reach_the_cursor(self, adapter_factory):
        adapter, _, cursor = adapter_factory(["cpf"], [(CPF,)])
        adapter.execute("SELECT cpf FROM cliente WHERE id = %s", [7])
        assert cursor.executed == [("SELECT cpf FROM cliente WHERE id = %s", [7])]

    def test_close_is_idempotent(self, adapter_factory):
        adapter, connection, _ = adapter_factory(["cpf"], [(CPF,)])
        adapter.close()
        adapter.close()
        assert connection.closed is True
        assert adapter.closed is True


class TestNeverCommits:
    """A limpeza transacional nunca pode ser um COMMIT (D-016)."""

    def test_success_does_not_commit(self, adapter_factory):
        adapter, connection, _ = adapter_factory(["cpf"], [(CPF,)])
        adapter.execute("SELECT cpf")
        assert connection.commits == 0

    def test_error_does_not_commit(self, adapter_factory):
        error = psycopg.errors.SyntaxError("boom")
        adapter, connection, _ = adapter_factory(["cpf"], [], error=error)
        with pytest.raises(DatabaseError):
            adapter.execute("SELECT")
        assert connection.commits == 0
