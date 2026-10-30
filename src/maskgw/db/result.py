"""Result set ja processado pelo Masking Engine.

Este e o UNICO tipo de resultado que sai da API publica de `maskgw.db`. Nao ha
cursor, nem `fetchone`/`fetchmany`/`fetchall` cru, nem iterador de valores
originais: quando um `MaskedResult` existe, a politica ja foi aplicada.

As linhas sao POSICIONAIS (tuplas), nunca dicionarios indexados por nome —
nomes de coluna duplicados sao validos em PostgreSQL.

Tipos, conforme a decisao da Fase 2:

- coluna SEM transformacao preserva exatamente o objeto devolvido pelo
  psycopg (`Decimal` continua `Decimal`, `datetime` continua `datetime`,
  JSONB continua `dict`, `bytes` continuam `bytes`);
- coluna COM transformacao carrega a saida do transformer, que e `str`;
- NULL permanece NULL nos dois casos.

`truncated` indica que o result set do banco tinha mais linhas que `max_rows`.
As linhas excedentes nao sao mascaradas nem devolvidas. Ver D-030.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

from maskgw.errors import DatabaseError
from maskgw.masking.descriptor import ColumnDescriptor
from maskgw.masking.engine import Action, Decision

WIRE_TYPE_SIZES: Final = MappingProxyType(
    {16: 1, 21: 2, 23: 4, 20: 8, 19: 64, 25: -1, 1042: -1, 1043: -1}
)
MAX_WIRE_COLUMNS: Final = 1664
WIRE_TEXT_OID: Final = 25


class DatabaseResultTypeError(DatabaseError):
    """Fixed refusal before fetch; no type name, OID, value or driver error."""

    def __init__(self) -> None:
        super().__init__("tipo de resultado nao suportado")


class DatabaseResultIntegrityError(DatabaseError):
    """Fatal internal typed-result failure, not a recoverable unsupported type."""

    def __init__(self) -> None:
        super().__init__("metadados de resultado indisponiveis")


@dataclass(frozen=True, slots=True, repr=False)
class MaskedResult:
    """Colunas, decisoes de matching e linhas ja mascaradas."""

    columns: tuple[ColumnDescriptor, ...]
    decisions: tuple[Decision, ...]
    rows: tuple[tuple[Any, ...], ...]
    #: Havia mais linhas do que `max_rows`. As excedentes nunca sao devolvidas.
    truncated: bool = False

    def __post_init__(self) -> None:
        # Desalinhamento aqui seria falha de seguranca, nao de ergonomia:
        # um valor sensivel poderia sair na posicao de outra coluna.
        if len(self.columns) != len(self.decisions):
            msg = f"{len(self.decisions)} decisoes para {len(self.columns)} colunas"
            raise ValueError(msg)
        width = len(self.columns)
        for row in self.rows:
            if len(row) != width:
                msg = f"linha com {len(row)} valores para {width} colunas"
                raise ValueError(msg)

    @property
    def column_names(self) -> tuple[str, ...]:
        """Nomes devolvidos ao cliente, na ordem e com duplicatas preservadas."""
        return tuple(column.output_name for column in self.columns)

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self) -> Iterator[tuple[Any, ...]]:
        """Itera as linhas MASCARADAS. Nao existe iterador do valor original."""
        return iter(self.rows)

    def __repr__(self) -> str:
        # Somente contagens: um repr com linhas vazaria dado em traceback e log.
        return (
            f"MaskedResult(columns={len(self.columns)}, "
            f"rows={len(self.rows)}, truncated={self.truncated})"
        )


@dataclass(frozen=True, slots=True, repr=False)
class TypedMaskedResult:
    """Internal opt-in wrapper of ALREADY masked rows and advertised type OIDs.

    No original/source type for MASK; no cursor, raw row or last-result state.
    This code contract is not a sandbox against hostile Python/reflection.
    """

    masked: MaskedResult
    type_oids: tuple[int, ...]

    def __post_init__(self) -> None:
        item = self.masked
        if type(item) is not MaskedResult or type(self.type_oids) is not tuple:
            raise DatabaseResultIntegrityError from None
        if (
            type(item.columns) is not tuple
            or type(item.decisions) is not tuple
            or type(item.rows) is not tuple
            or type(item.truncated) is not bool
        ):
            raise DatabaseResultIntegrityError from None
        width = len(item.columns)
        if (
            not 1 <= width <= MAX_WIRE_COLUMNS
            or len(item.decisions) != width
            or len(self.type_oids) != width
        ):
            raise DatabaseResultIntegrityError from None
        for descriptor, decision, oid in zip(
            item.columns, item.decisions, self.type_oids, strict=True
        ):
            if (
                type(descriptor) is not ColumnDescriptor
                or type(descriptor.output_name) is not str
                or type(decision) is not Decision
                or type(decision.action) is not Action
                or type(decision.output_name) is not str
                or decision.output_name != descriptor.output_name
                or type(oid) is not int
                or oid not in WIRE_TYPE_SIZES
                or (decision.action is Action.MASK and oid != WIRE_TEXT_OID)
            ):
                raise DatabaseResultIntegrityError from None
        if any(type(row) is not tuple or len(row) != width for row in item.rows):
            raise DatabaseResultIntegrityError from None

    def __repr__(self) -> str:
        return f"TypedMaskedResult(columns={len(self.type_oids)}, rows={self.masked.row_count})"
