"""O que o PostgreSQL realmente devolve em `ftable`/`ftablecol` (Fase 3).

Este arquivo NAO testa codigo do Gateway. Ele mede o comportamento do
PostgreSQL e do psycopg, cenario a cenario, e fixa o resultado em asercoes.

Motivo: `docs/ARCHITECTURE.md` afirmava que `table_oid` e `table_column` sao
expostos por psycopg3 em `cursor.description`. **Nao sao.** O `Column` oferece
apenas `name`, `type_code`, `display_size`, `internal_size`, `precision`,
`scale` e `null_ok`. Os dois campos vivem no resultado de baixo nivel, em
`cursor.pgresult.ftable(i)` e `cursor.pgresult.ftablecol(i)`.

O resolver de provenance da Fase 3 e desenhado a partir do que se mede aqui,
nao a partir de suposicao. Se uma versao futura do PostgreSQL ou do psycopg
mudar esse contrato, estes testes quebram primeiro.

Convencao do protocolo (documentada pelo PostgreSQL para `RowDescription`):
`ftable = 0` significa que a coluna NAO vem de uma unica coluna de tabela.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import psycopg
import pytest

pytestmark = pytest.mark.integration

SCHEMA = "maskgw_fase3_probe"

DDL = f"""
DROP SCHEMA IF EXISTS {SCHEMA} CASCADE;
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.cliente (id int, cpf text, email text);
CREATE TABLE {SCHEMA}.pedido (id int, cliente_id int, total numeric);
CREATE VIEW {SCHEMA}.cliente_vw AS SELECT id, cpf FROM {SCHEMA}.cliente;
CREATE VIEW {SCHEMA}.cliente_alias_vw AS
    SELECT id, cpf AS documento FROM {SCHEMA}.cliente;
CREATE MATERIALIZED VIEW {SCHEMA}.cliente_mv AS SELECT id, cpf FROM {SCHEMA}.cliente;
CREATE TABLE {SCHEMA}."Cliente Maiusculo" (id int, "CPF" text);
INSERT INTO {SCHEMA}.cliente VALUES (1, '11122233344', 'a@b.co');
INSERT INTO {SCHEMA}.pedido VALUES (1, 1, 10.5);
INSERT INTO {SCHEMA}."Cliente Maiusculo" VALUES (1, '11122233344');
"""


@pytest.fixture
def probe(dsn: str) -> Iterator[psycopg.Connection[tuple[Any, ...]]]:
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(DDL)
        yield connection
        connection.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")


def metadata(connection: object, sql: str) -> list[tuple[str, int, int]]:
    """`(name, ftable, ftablecol)` por coluna, medido no resultado real."""
    conn: Any = connection
    with conn.cursor() as cursor:
        cursor.execute(sql)
        result = cursor.pgresult
        assert cursor.description is not None
        return [
            (column.name, result.ftable(index), result.ftablecol(index))
            for index, column in enumerate(cursor.description)
        ]


def oid_of(connection: object, relation: str) -> int:
    conn: Any = connection
    row = conn.execute("SELECT %s::regclass::oid", [relation]).fetchone()
    return int(row[0])


def attname(connection: object, oid: int, attnum: int) -> str | None:
    conn: Any = connection
    row = conn.execute(
        "SELECT attname FROM pg_attribute WHERE attrelid = %s AND attnum = %s",
        [oid, attnum],
    ).fetchone()
    return None if row is None else str(row[0])


class TestColumnDoesNotCarryProvenance:
    """A premissa corrigida: `cursor.description` nao basta."""

    def test_column_has_no_table_oid_attribute(self, probe):
        with probe.cursor() as cursor:
            cursor.execute(f"SELECT cpf FROM {SCHEMA}.cliente")
            column = cursor.description[0]
        assert not hasattr(column, "table_oid")
        assert not hasattr(column, "table_column")

    def test_pgresult_is_where_provenance_lives(self, probe):
        with probe.cursor() as cursor:
            cursor.execute(f"SELECT cpf FROM {SCHEMA}.cliente")
            assert hasattr(cursor.pgresult, "ftable")
            assert hasattr(cursor.pgresult, "ftablecol")


class TestProvenanceIsPreserved:
    """Cenarios em que `ftable`/`ftablecol` apontam para a coluna de origem."""

    def test_direct_column(self, probe):
        oid = oid_of(probe, f"{SCHEMA}.cliente")
        assert metadata(probe, f"SELECT cpf FROM {SCHEMA}.cliente") == [("cpf", oid, 2)]
        assert attname(probe, oid, 2) == "cpf"

    def test_alias(self, probe):
        """O criterio central da Fase 3: o alias muda o nome, nao a origem."""
        oid = oid_of(probe, f"{SCHEMA}.cliente")
        measured = metadata(probe, f"SELECT cpf AS documento FROM {SCHEMA}.cliente")
        assert measured == [("documento", oid, 2)]
        assert attname(probe, oid, 2) == "cpf"

    def test_select_star_resolves_each_column(self, probe):
        oid = oid_of(probe, f"{SCHEMA}.cliente")
        assert metadata(probe, f"SELECT * FROM {SCHEMA}.cliente") == [
            ("id", oid, 1),
            ("cpf", oid, 2),
            ("email", oid, 3),
        ]

    def test_join_keeps_one_origin_per_position(self, probe):
        cliente = oid_of(probe, f"{SCHEMA}.cliente")
        pedido = oid_of(probe, f"{SCHEMA}.pedido")
        measured = metadata(
            probe,
            f"SELECT c.cpf, p.total FROM {SCHEMA}.cliente c "
            f"JOIN {SCHEMA}.pedido p ON p.cliente_id = c.id",
        )
        assert measured == [("cpf", cliente, 2), ("total", pedido, 3)]

    def test_join_with_duplicate_names_keeps_distinct_origins(self, probe):
        cliente = oid_of(probe, f"{SCHEMA}.cliente")
        pedido = oid_of(probe, f"{SCHEMA}.pedido")
        measured = metadata(
            probe,
            f"SELECT c.id, p.id FROM {SCHEMA}.cliente c "
            f"JOIN {SCHEMA}.pedido p ON p.cliente_id = c.id",
        )
        assert measured == [("id", cliente, 1), ("id", pedido, 1)]

    def test_subquery(self, probe):
        oid = oid_of(probe, f"{SCHEMA}.cliente")
        query = f"SELECT cpf FROM (SELECT cpf FROM {SCHEMA}.cliente) x"
        assert metadata(probe, query) == [("cpf", oid, 2)]

    def test_alias_inside_subquery(self, probe):
        """Cenario-chave de docs/THREAT-MODEL.md: a origem sobrevive."""
        oid = oid_of(probe, f"{SCHEMA}.cliente")
        query = f"SELECT d FROM (SELECT cpf AS d FROM {SCHEMA}.cliente) x"
        assert metadata(probe, query) == [("d", oid, 2)]
        assert attname(probe, oid, 2) == "cpf"

    def test_cte(self, probe):
        oid = oid_of(probe, f"{SCHEMA}.cliente")
        query = f"WITH x AS (SELECT cpf FROM {SCHEMA}.cliente) SELECT cpf FROM x"
        assert metadata(probe, query) == [("cpf", oid, 2)]

    def test_cte_with_alias(self, probe):
        oid = oid_of(probe, f"{SCHEMA}.cliente")
        query = f"WITH x AS (SELECT cpf AS d FROM {SCHEMA}.cliente) SELECT d FROM x"
        assert metadata(probe, query) == [("d", oid, 2)]

    def test_cast_keeps_provenance(self, probe):
        """`cpf::text` sobre coluna ja `text` nao cria expressao."""
        oid = oid_of(probe, f"{SCHEMA}.cliente")
        assert metadata(probe, f"SELECT cpf::text FROM {SCHEMA}.cliente") == [("cpf", oid, 2)]

    def test_quoted_uppercase_identifiers(self, probe):
        oid = oid_of(probe, f'{SCHEMA}."Cliente Maiusculo"')
        query = f'SELECT "CPF" AS "Documento" FROM {SCHEMA}."Cliente Maiusculo"'
        assert metadata(probe, query) == [("Documento", oid, 2)]
        assert attname(probe, oid, 2) == "CPF"

    def test_null_value_does_not_affect_provenance(self, probe):
        """Provenance vem da metadata, nunca do conteudo das linhas."""
        oid = oid_of(probe, f"{SCHEMA}.cliente")
        query = f"SELECT cpf FROM {SCHEMA}.cliente WHERE false"
        assert metadata(probe, query) == [("cpf", oid, 2)]

    def test_where_clause_does_not_affect_provenance(self, probe):
        oid = oid_of(probe, f"{SCHEMA}.cliente")
        query = f"SELECT cpf AS d FROM {SCHEMA}.cliente WHERE id = 1 ORDER BY id LIMIT 1"
        assert metadata(probe, query) == [("d", oid, 2)]


class TestProvenancePointsToTheView:
    """A view resolve para a coluna DA VIEW, nao da tabela base."""

    def test_view_reports_the_view_oid(self, probe):
        view = oid_of(probe, f"{SCHEMA}.cliente_vw")
        base = oid_of(probe, f"{SCHEMA}.cliente")
        measured = metadata(probe, f"SELECT cpf FROM {SCHEMA}.cliente_vw")
        assert measured == [("cpf", view, 2)]
        assert view != base

    def test_view_column_name_is_the_view_name(self, probe):
        """Uma view que renomeia perde o nome original nesta camada."""
        view = oid_of(probe, f"{SCHEMA}.cliente_alias_vw")
        measured = metadata(probe, f"SELECT documento FROM {SCHEMA}.cliente_alias_vw")
        assert measured == [("documento", view, 2)]
        # A coluna da view chama-se `documento`; `cpf` so existe na tabela base.
        assert attname(probe, view, 2) == "documento"

    def test_relkind_distinguishes_view_from_table(self, probe):
        rows = probe.execute(
            "SELECT relname, relkind FROM pg_class WHERE oid = ANY(%s) ORDER BY relname",
            [
                [
                    oid_of(probe, f"{SCHEMA}.cliente"),
                    oid_of(probe, f"{SCHEMA}.cliente_vw"),
                    oid_of(probe, f"{SCHEMA}.cliente_mv"),
                ]
            ],
        ).fetchall()
        assert dict(rows) == {"cliente": "r", "cliente_vw": "v", "cliente_mv": "m"}

    def test_materialized_view_also_carries_provenance(self, probe):
        mv = oid_of(probe, f"{SCHEMA}.cliente_mv")
        assert metadata(probe, f"SELECT cpf FROM {SCHEMA}.cliente_mv") == [("cpf", mv, 2)]


class TestProvenanceIsLost:
    """`ftable = 0`: o PostgreSQL afirma que nao ha coluna de origem unica."""

    def test_union_loses_provenance(self, probe):
        query = f"SELECT cpf FROM {SCHEMA}.cliente UNION ALL SELECT cpf FROM {SCHEMA}.cliente"
        assert metadata(probe, query) == [("cpf", 0, 0)]

    def test_union_with_alias_loses_both_name_and_origin(self, probe):
        """Bypass residual: nem `output_name` nem origem casam a regra."""
        query = (
            f"SELECT cpf AS documento FROM {SCHEMA}.cliente "
            f"UNION ALL SELECT cpf FROM {SCHEMA}.cliente"
        )
        assert metadata(probe, query) == [("documento", 0, 0)]

    def test_expression_loses_provenance(self, probe):
        assert metadata(probe, f"SELECT md5(cpf) FROM {SCHEMA}.cliente") == [("md5", 0, 0)]

    def test_expression_with_alias_loses_provenance(self, probe):
        query = f"SELECT substr(cpf, 1, 3) AS x FROM {SCHEMA}.cliente"
        assert metadata(probe, query) == [("x", 0, 0)]

    def test_literal_has_no_provenance(self, probe):
        assert metadata(probe, "SELECT 'x' AS cpf") == [("cpf", 0, 0)]

    def test_aggregate_has_no_provenance(self, probe):
        query = f"SELECT count(cpf) AS total FROM {SCHEMA}.cliente"
        assert metadata(probe, query) == [("total", 0, 0)]

    def test_catalog_lookup_of_zero_returns_nothing(self, probe):
        """Confirma que `ftable = 0` nao e um oid valido a consultar."""
        assert attname(probe, 0, 0) is None


class TestSystemColumns:
    """Coluna de sistema tem attnum negativo e ainda resolve."""

    def test_ctid_has_negative_attnum(self, probe):
        oid = oid_of(probe, f"{SCHEMA}.cliente")
        measured = metadata(probe, f"SELECT ctid FROM {SCHEMA}.cliente")
        assert measured == [("ctid", oid, -1)]
        assert attname(probe, oid, -1) == "ctid"
