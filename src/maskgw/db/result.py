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
from typing import Any

from maskgw.masking.descriptor import ColumnDescriptor
from maskgw.masking.engine import Decision


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
