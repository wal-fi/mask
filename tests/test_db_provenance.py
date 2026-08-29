"""Resolucao de proveniencia sem banco (Fase 3).

O comportamento real do PostgreSQL esta medido em
`tests/test_pgresult_metadata.py`. Aqui se testa o que o Gateway FAZ com essa
metadata: classificacao, cache, alinhamento posicional e — o ponto mais
delicado — o que acontece quando o catalogo nao responde.

Regra da fase: falha ao resolver NAO e fatal e NAO muda o default ALLOW. A
coluna volta a `UNKNOWN`, `origin_name` fica `None`, e o matching recai sobre
`output_name`.
"""

from __future__ import annotations

from typing import Any, cast

import psycopg
import pytest

from maskgw.db.columns import DERIVED_ORIGIN, UNKNOWN_ORIGIN, ColumnOrigin, describe_columns
from maskgw.db.provenance import ProvenanceResolver, provenance_keys
from maskgw.errors import CapabilityError, DatabaseError
from maskgw.masking.descriptor import ProvenanceKind
from tests.conftest import FakeColumn, FakePgResult

CLIENTE = 18208
VIEW = 18218

#: Linha do catalogo: (attrelid, attnum, nspname, relname, attname, relkind)
ROW_CPF = (CLIENTE, 2, "public", "cliente", "cpf", "r")
ROW_EMAIL = (CLIENTE, 3, "public", "cliente", "email", "r")
ROW_VIEW = (VIEW, 2, "public", "cliente_vw", "cpf", "v")
ROW_MATVIEW = (VIEW, 3, "public", "cliente_mv", "cpf", "m")


class CatalogCursor:
    """Imita o `unnest ... JOIN pg_attribute`: so devolve o que foi pedido."""

    def __init__(self, rows: list[tuple[Any, ...]], error: BaseException | None) -> None:
        self._rows = rows
        self._error = error
        self._requested: set[tuple[int, int]] = set()
        self.queries: list[tuple[str, Any]] = []

    def __enter__(self) -> CatalogCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: Any = None) -> None:
        self.queries.append((query, params))
        if self._error is not None:
            raise self._error
        oids, attnums = params
        self._requested = set(zip(oids, attnums, strict=True))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return [row for row in self._rows if (row[0], row[1]) in self._requested]


class CatalogConnection:
    """Conexao que so serve o catalogo, contando quantas vezes foi consultada."""

    def __init__(
        self,
        rows: list[tuple[Any, ...]] | None = None,
        *,
        error: BaseException | None = None,
    ) -> None:
        self.rows = rows if rows is not None else []
        self.error = error
        self.cursors: list[CatalogCursor] = []

    def cursor(self) -> CatalogCursor:
        created = CatalogCursor(self.rows, self.error)
        self.cursors.append(created)
        return created

    @property
    def query_count(self) -> int:
        return sum(len(cursor.queries) for cursor in self.cursors)


def build(rows: list[tuple[Any, ...]] | None = None, **kwargs: Any) -> Any:
    connection = CatalogConnection(rows, **kwargs)
    resolver = ProvenanceResolver(cast("psycopg.Connection[Any]", connection))
    return resolver, connection


class TestProvenanceKeys:
    def test_reads_ftable_and_ftablecol_per_column(self):
        pgresult = FakePgResult([(CLIENTE, 2), (0, 0)])
        keys = provenance_keys(pgresult, [FakeColumn("cpf"), FakeColumn("md5")])
        assert keys == ((CLIENTE, 2), (0, 0))

    def test_no_description_means_no_keys(self):
        assert provenance_keys(FakePgResult([]), None) is None

    def test_no_pgresult_means_no_keys(self):
        assert provenance_keys(None, [FakeColumn("cpf")]) is None

    def test_empty_result_set(self):
        assert provenance_keys(FakePgResult([]), []) == ()


class TestClassification:
    def test_table_column_is_direct(self):
        resolver, _ = build([ROW_CPF])
        origin = resolver.resolve([(CLIENTE, 2)])[0]
        assert origin == ColumnOrigin(
            kind=ProvenanceKind.DIRECT, name="cpf", schema="public", table="cliente"
        )

    def test_view_column_is_view(self):
        resolver, _ = build([ROW_VIEW])
        origin = resolver.resolve([(VIEW, 2)])[0]
        assert origin.kind is ProvenanceKind.VIEW
        assert origin.table == "cliente_vw"

    def test_materialized_view_is_view(self):
        resolver, _ = build([ROW_MATVIEW])
        assert resolver.resolve([(VIEW, 3)])[0].kind is ProvenanceKind.VIEW

    def test_zero_oid_is_derived_without_touching_the_catalog(self):
        resolver, connection = build([ROW_CPF])
        assert resolver.resolve([(0, 0)]) == (DERIVED_ORIGIN,)
        assert connection.query_count == 0

    def test_zero_attnum_is_derived(self):
        resolver, connection = build()
        assert resolver.resolve([(CLIENTE, 0)]) == (DERIVED_ORIGIN,)
        assert connection.query_count == 0

    def test_catalog_silence_means_unknown(self):
        """Origem existe, mas nao conseguimos traduzi-la."""
        resolver, _ = build([])
        assert resolver.resolve([(CLIENTE, 2)]) == (UNKNOWN_ORIGIN,)

    def test_derived_and_unknown_are_distinct(self):
        resolver, _ = build([])
        derived, unknown = resolver.resolve([(0, 0), (CLIENTE, 2)])
        assert derived.kind is ProvenanceKind.DERIVED
        assert unknown.kind is ProvenanceKind.UNKNOWN
        assert derived.name is None and unknown.name is None


class TestPositionalAlignment:
    def test_result_is_aligned_with_the_keys(self):
        resolver, _ = build([ROW_CPF, ROW_EMAIL])
        origins = resolver.resolve([(0, 0), (CLIENTE, 3), (CLIENTE, 2)])
        assert [origin.name for origin in origins] == [None, "email", "cpf"]

    def test_repeated_keys_resolve_to_the_same_origin(self):
        resolver, _ = build([ROW_CPF])
        origins = resolver.resolve([(CLIENTE, 2), (CLIENTE, 2)])
        assert len(origins) == 2
        assert origins[0] == origins[1]

    def test_empty_input(self):
        resolver, connection = build([ROW_CPF])
        assert resolver.resolve([]) == ()
        assert connection.query_count == 0


class TestCache:
    """Resolver uma vez por COLUNA, nunca por linha ou celula (D-021)."""

    def test_one_query_for_many_columns(self):
        resolver, connection = build([ROW_CPF, ROW_EMAIL])
        resolver.resolve([(CLIENTE, 2), (CLIENTE, 3), (0, 0)])
        assert connection.query_count == 1

    def test_second_resolve_uses_the_cache(self):
        resolver, connection = build([ROW_CPF])
        resolver.resolve([(CLIENTE, 2)])
        resolver.resolve([(CLIENTE, 2)])
        assert connection.query_count == 1
        assert resolver.cache_size == 1

    def test_only_the_new_keys_are_queried(self):
        resolver, connection = build([ROW_CPF, ROW_EMAIL])
        resolver.resolve([(CLIENTE, 2)])
        resolver.resolve([(CLIENTE, 2), (CLIENTE, 3)])
        assert connection.query_count == 2
        second = connection.cursors[-1].queries[-1][1]
        assert second == ([CLIENTE], [3])

    def test_absence_is_cached_too(self):
        """Chave sem linha no catalogo nao e reconsultada a cada result set."""
        resolver, connection = build([])
        resolver.resolve([(CLIENTE, 2)])
        resolver.resolve([(CLIENTE, 2)])
        assert connection.query_count == 1

    def test_derived_columns_never_enter_the_cache(self):
        resolver, _ = build([])
        resolver.resolve([(0, 0), (0, 0)])
        assert resolver.cache_size == 0


class TestCatalogFailure:
    """Falha de catalogo e ERRO OPERACIONAL, nao ausencia de origem (D-040).

    Ate a Fase 5 a falha virava `UNKNOWN`, e a coluna caia no default ALLOW —
    o que devolvia em claro uma coluna que deveria estar mascarada. Medido na
    Fase 6 e corrigido: a consulta falha.
    """

    def test_failure_rejects_the_query(self):
        resolver, _ = build(error=psycopg.errors.InsufficientPrivilege("sem permissao"))
        with pytest.raises(CapabilityError):
            resolver.resolve([(CLIENTE, 2)])

    def test_failure_is_not_cached_so_it_can_recover(self):
        """Erro transitorio nao pode desligar a proveniencia para sempre."""
        resolver, connection = build(error=psycopg.OperationalError("falha"))
        with pytest.raises(CapabilityError):
            resolver.resolve([(CLIENTE, 2)])
        assert resolver.cache_size == 0

        connection.error = None
        connection.rows = [ROW_CPF]
        assert resolver.resolve([(CLIENTE, 2)])[0].name == "cpf"

    def test_failure_message_never_escapes(self):
        resolver, _ = build(error=psycopg.errors.InsufficientPrivilege("permission denied"))
        with pytest.raises(CapabilityError) as info:
            resolver.resolve([(CLIENTE, 2)])
        assert "permission denied" not in str(info.value)
        assert info.value.__cause__ is None
        assert info.value.__context__ is None

    def test_derived_columns_never_touch_the_catalog(self):
        """`ftable = 0` nao consulta nada, entao nao pode falhar."""
        resolver, _ = build(error=psycopg.OperationalError("falha"))
        assert resolver.resolve([(0, 0)]) == (DERIVED_ORIGIN,)

    def test_absent_catalog_row_is_still_unknown(self):
        """Catalogo respondeu, mas nao ha linha: isso NAO e falha operacional."""
        resolver, _ = build([])
        assert resolver.resolve([(CLIENTE, 2)]) == (UNKNOWN_ORIGIN,)


class TestDescribeColumnsWithOrigins:
    def test_descriptor_carries_the_whole_origin(self):
        origin = ColumnOrigin(
            kind=ProvenanceKind.DIRECT, name="cpf", schema="public", table="cliente"
        )
        column = describe_columns([FakeColumn("documento")], [origin])[0]
        assert column.output_name == "documento"
        assert column.origin_name == "cpf"
        assert column.origin_schema == "public"
        assert column.origin_table == "cliente"
        assert column.provenance_kind is ProvenanceKind.DIRECT
        assert column.names == ("documento", "cpf")

    def test_without_origins_everything_is_unknown(self):
        column = describe_columns([FakeColumn("cpf")])[0]
        assert column.origin_name is None
        assert column.provenance_kind is ProvenanceKind.UNKNOWN
        assert column.names == ("cpf",)

    def test_derived_origin_leaves_no_name(self):
        column = describe_columns([FakeColumn("md5")], [DERIVED_ORIGIN])[0]
        assert column.origin_name is None
        assert column.provenance_kind is ProvenanceKind.DERIVED

    def test_same_name_is_not_duplicated_in_matching(self):
        origin = ColumnOrigin(kind=ProvenanceKind.DIRECT, name="cpf")
        assert describe_columns([FakeColumn("cpf")], [origin])[0].names == ("cpf",)

    @pytest.mark.parametrize("count", [0, 1, 3])
    def test_misalignment_fails_closed(self, count):
        """Uma coluna herdaria a origem de outra. Nunca continuar assim."""
        description = [FakeColumn("cpf"), FakeColumn("email")]
        origins = [DERIVED_ORIGIN] * count
        with pytest.raises(DatabaseError, match="desalinhada"):
            describe_columns(description, origins)

    def test_alignment_error_reports_only_counts(self):
        with pytest.raises(DatabaseError) as info:
            describe_columns([FakeColumn("cpf")], [])
        assert "0 origens" in str(info.value)
        assert "1 colunas" in str(info.value)

    def test_duplicate_names_keep_distinct_origins(self):
        description = [FakeColumn("id"), FakeColumn("id")]
        origins = [
            ColumnOrigin(kind=ProvenanceKind.DIRECT, name="id", table="cliente"),
            ColumnOrigin(kind=ProvenanceKind.DIRECT, name="id", table="pedido"),
        ]
        columns = describe_columns(description, origins)
        assert columns[0].origin_table == "cliente"
        assert columns[1].origin_table == "pedido"


class TestQualifiedOrigin:
    def test_full_path(self):
        column = describe_columns(
            [FakeColumn("d")],
            [ColumnOrigin(kind=ProvenanceKind.DIRECT, name="cpf", schema="s", table="t")],
        )[0]
        assert column.qualified_origin == "s.t.cpf"

    def test_none_without_origin(self):
        assert describe_columns([FakeColumn("md5")], [DERIVED_ORIGIN])[0].qualified_origin is None

    def test_partial_path_omits_the_missing_parts(self):
        column = describe_columns(
            [FakeColumn("d")], [ColumnOrigin(kind=ProvenanceKind.DIRECT, name="cpf")]
        )[0]
        assert column.qualified_origin == "cpf"
