"""Descritores de coluna a partir de `cursor.description`.

Na FASE 2 o matching usa somente `output_name`: `origin_name` e sempre `None`.
A resolucao de proveniencia (`table_oid` + `table_column` cruzados com
`pg_attribute`) e o objeto da Fase 3, e entra por aqui.

Consequencia assumida desta fase, documentada em teste: `SELECT cpf AS
documento` passa em claro, porque so o alias e conhecido.

Duas invariantes de seguranca:

- A representacao e POSICIONAL. Nomes de coluna duplicados sao validos em
  PostgreSQL (`SELECT cpf, cpf`, ou `SELECT *` num JOIN com `id` nas duas
  tabelas). Indexar por nome colapsaria colunas e poderia alinhar um valor
  sensivel a posicao de uma coluna nao mascarada.
- Este modulo nao importa psycopg: recebe a `description` estruturalmente.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from maskgw.errors import DatabaseError
from maskgw.masking.descriptor import ColumnDescriptor


class ColumnSource(Protocol):
    """Minimo que este modulo consome de `psycopg.Column`."""

    @property
    def name(self) -> str:
        """Nome da coluna como o PostgreSQL a devolve (o alias, se houver)."""
        ...


def describe_columns(description: Sequence[ColumnSource] | None) -> tuple[ColumnDescriptor, ...]:
    """Converte `cursor.description` em descritores, preservando a ordem.

    `description` e `None` quando o statement nao produz result set. Nesse caso
    nao ha o que mascarar e o adapter falha fechado, em vez de devolver vazio.
    """
    if description is None:
        msg = "a consulta nao produziu result set"
        raise DatabaseError(msg)

    return tuple(ColumnDescriptor(output_name=column.name) for column in description)
