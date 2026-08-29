"""Descritores de coluna a partir de `cursor.description` e da proveniencia.

Na Fase 3 o `ColumnDescriptor` passa a carregar tambem a origem da coluna,
resolvida por `maskgw.db.provenance` a partir da metadata do PostgreSQL. O
matching entao avalia `output_name` OR `origin_name`, e o bypass por alias
(`SELECT cpf AS documento`) deixa de funcionar.

Tres invariantes de seguranca:

- A representacao e POSICIONAL. Nomes de coluna duplicados sao validos em
  PostgreSQL (`SELECT cpf, cpf`, ou um JOIN com `id` nas duas tabelas).
  Indexar por nome colapsaria colunas e poderia alinhar um valor sensivel a
  posicao de uma coluna nao mascarada.
- Descritores e origens precisam ter o mesmo comprimento. Desalinhamento aqui
  daria a uma coluna a origem de outra: falha fechada, nao silenciosa.
- Este modulo nao importa psycopg: recebe `description` estruturalmente e
  origens ja resolvidas.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from maskgw.errors import DatabaseError
from maskgw.masking.descriptor import ColumnDescriptor, ProvenanceKind


class ColumnSource(Protocol):
    """Minimo que este modulo consome de `psycopg.Column`."""

    @property
    def name(self) -> str:
        """Nome da coluna como o PostgreSQL a devolve (o alias, se houver)."""
        ...


@dataclass(frozen=True, slots=True)
class ColumnOrigin:
    """Origem resolvida de uma coluna do result set."""

    kind: ProvenanceKind
    name: str | None = None
    schema: str | None = None
    table: str | None = None


#: O PostgreSQL afirma que a coluna nao vem de uma unica coluna de tabela.
DERIVED_ORIGIN: Final = ColumnOrigin(kind=ProvenanceKind.DERIVED)

#: Nao foi possivel determinar a origem. Default conservador.
UNKNOWN_ORIGIN: Final = ColumnOrigin(kind=ProvenanceKind.UNKNOWN)


def describe_columns(
    description: Sequence[ColumnSource] | None,
    origins: Sequence[ColumnOrigin] | None = None,
) -> tuple[ColumnDescriptor, ...]:
    """Converte `cursor.description` em descritores, preservando a ordem.

    `description` e `None` quando o statement nao produz result set. Nesse caso
    nao ha o que mascarar e o adapter falha fechado, em vez de devolver vazio.

    `origins` ausente significa consulta sem proveniencia resolvida: toda
    coluna fica `UNKNOWN` e o matching recai sobre `output_name`.
    """
    if description is None:
        msg = "a consulta nao produziu result set"
        raise DatabaseError(msg)

    resolved = [UNKNOWN_ORIGIN] * len(description) if origins is None else list(origins)
    if len(resolved) != len(description):
        # Uma coluna herdaria a origem de outra. Nunca continuar assim.
        msg = f"proveniencia desalinhada: {len(resolved)} origens para {len(description)} colunas"
        raise DatabaseError(msg)

    return tuple(
        ColumnDescriptor(
            output_name=column.name,
            origin_name=origin.name,
            origin_schema=origin.schema,
            origin_table=origin.table,
            provenance_kind=origin.kind,
        )
        for column, origin in zip(description, resolved, strict=True)
    )
