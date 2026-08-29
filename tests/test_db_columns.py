"""Descritores de coluna a partir de `cursor.description` (Fase 2).

Duas invariantes desta fase:

- `origin_name` e SEMPRE None. Lineage e Fase 3.
- A representacao e posicional: nomes duplicados sao validos em PostgreSQL e
  nao podem ser colapsados.
"""

from __future__ import annotations

import pytest

from maskgw.db.columns import describe_columns
from maskgw.errors import DatabaseError
from tests.conftest import FakeColumn


def description(*names: str) -> list[FakeColumn]:
    return [FakeColumn(name) for name in names]


class TestOutputNames:
    def test_single_column(self):
        assert describe_columns(description("cpf"))[0].output_name == "cpf"

    def test_order_is_preserved(self):
        columns = describe_columns(description("id", "cpf", "email"))
        assert [column.output_name for column in columns] == ["id", "cpf", "email"]

    def test_alias_is_taken_as_output_name(self):
        assert describe_columns(description("documento"))[0].output_name == "documento"

    def test_expression_default_name(self):
        """PostgreSQL nomeia expressoes sem alias como `?column?`."""
        assert describe_columns(description("?column?"))[0].output_name == "?column?"

    def test_empty_result_set_columns(self):
        assert describe_columns([]) == ()

    def test_returns_a_tuple(self):
        assert isinstance(describe_columns(description("cpf")), tuple)


class TestNoLineageInPhaseTwo:
    @pytest.mark.parametrize("name", ["cpf", "documento", "?column?"])
    def test_origin_name_is_always_none(self, name):
        assert describe_columns(description(name))[0].origin_name is None

    def test_names_property_has_only_the_output_name(self):
        assert describe_columns(description("documento"))[0].names == ("documento",)


class TestDuplicateNames:
    """`SELECT cpf, cpf` e `SELECT *` num JOIN produzem nomes repetidos.

    Colapsar por nome poderia alinhar um valor sensivel a posicao de uma
    coluna nao mascarada.
    """

    def test_duplicates_are_kept(self):
        columns = describe_columns(description("cpf", "cpf"))
        assert len(columns) == 2
        assert [column.output_name for column in columns] == ["cpf", "cpf"]

    def test_duplicate_id_from_join(self):
        columns = describe_columns(description("id", "cpf", "id", "descricao"))
        assert len(columns) == 4
        assert [column.output_name for column in columns] == ["id", "cpf", "id", "descricao"]


class TestNoResultSet:
    def test_none_description_fails_closed(self):
        with pytest.raises(DatabaseError, match="result set"):
            describe_columns(None)
