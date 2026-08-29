"""Resolucao da proveniencia de coluna a partir da metadata do PostgreSQL.

Fonte, medida empiricamente em `tests/test_pgresult_metadata.py`:

    cursor.pgresult.ftable(i)     oid da relacao de origem, ou 0
    cursor.pgresult.ftablecol(i)  attnum da coluna de origem, ou 0

O `Column` de `cursor.description` NAO expoe esses campos (verificado em
psycopg 3.3.4). Eles vivem no resultado de baixo nivel.

`ftable = 0` e uma afirmacao do protocolo: a coluna nao vem de uma unica
coluna de tabela. E o caso de expressao, literal, agregado e UNION.

A traducao de `(oid, attnum)` para `(schema, relacao, coluna)` sai de
`pg_attribute`, `pg_class` e `pg_namespace`. Nunca dos valores das linhas.

Falha ao resolver NAO e fatal: `docs/DECISIONS.md` (D-020) define que a coluna
volta a `UNKNOWN`, `origin_name` fica `None` e o matching recai sobre
`output_name`. O default ALLOW do MVP nao muda.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final, Protocol

import psycopg

from maskgw.db.columns import DERIVED_ORIGIN, UNKNOWN_ORIGIN, ColumnOrigin
from maskgw.masking.descriptor import ProvenanceKind

#: `relkind` de `pg_class` que caracteriza view. Ver o teste empirico.
_VIEW_RELKINDS: Final[frozenset[str]] = frozenset({"v", "m"})

#: Uma consulta so, para todas as colunas ainda nao conhecidas.
_CATALOG_QUERY: Final = """
SELECT k.attrelid, k.attnum, n.nspname, c.relname, a.attname, c.relkind
FROM unnest(%s::oid[], %s::int2[]) AS k(attrelid, attnum)
JOIN pg_attribute a ON a.attrelid = k.attrelid AND a.attnum = k.attnum
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
"""

#: `(oid, attnum)` por coluna do result set.
ProvenanceKey = tuple[int, int]


class PgResultSource(Protocol):
    """Minimo que este modulo consome de `psycopg.pq.PGresult`."""

    def ftable(self, column_number: int) -> int: ...

    def ftablecol(self, column_number: int) -> int: ...


def provenance_keys(
    pgresult: PgResultSource | None,
    description: Sequence[object] | None,
) -> tuple[ProvenanceKey, ...] | None:
    """Le `(ftable, ftablecol)` de cada coluna, na ordem do result set.

    Devolve `None` quando nao ha result set ou metadata de baixo nivel — o
    chamador entao trata todas as colunas como sem proveniencia.
    """
    if pgresult is None or description is None:
        return None
    return tuple(
        (pgresult.ftable(index), pgresult.ftablecol(index)) for index in range(len(description))
    )


class ProvenanceResolver:
    """Traduz `(oid, attnum)` em origem, com cache por conexao.

    O cache e um dicionario simples com chave `(oid, attnum)`, vivo enquanto a
    conexao existir. Resolve-se uma vez por COLUNA, nunca por linha ou celula.
    Ver docs/DECISIONS.md (D-021) para o alcance e o risco do cache.
    """

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self._connection = connection
        self._cache: dict[ProvenanceKey, ColumnOrigin] = {}

    @property
    def cache_size(self) -> int:
        """Quantas colunas distintas ja foram resolvidas. Metadata, nao dado."""
        return len(self._cache)

    def resolve(self, keys: Sequence[ProvenanceKey]) -> tuple[ColumnOrigin, ...]:
        """Origem de cada coluna, alinhada posicionalmente com `keys`."""
        missing = sorted({key for key in keys if _has_origin(key) and key not in self._cache})
        if missing:
            self._load(missing)
        return tuple(self._origin_of(key) for key in keys)

    def _origin_of(self, key: ProvenanceKey) -> ColumnOrigin:
        if not _has_origin(key):
            # O PostgreSQL afirma que nao ha coluna de origem unica.
            return DERIVED_ORIGIN
        return self._cache.get(key, UNKNOWN_ORIGIN)

    def _load(self, keys: Sequence[ProvenanceKey]) -> None:
        """Consulta o catalogo para as chaves ainda desconhecidas.

        Falha aqui e absorvida: as colunas afetadas ficam `UNKNOWN` nesta
        consulta e NAO entram no cache, para que um erro transitorio nao
        desligue a proveniencia pelo resto da vida da conexao.
        """
        oids = [oid for oid, _ in keys]
        attnums = [attnum for _, attnum in keys]
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(_CATALOG_QUERY, (oids, attnums))
                rows = cursor.fetchall()
        except psycopg.Error:
            # Sem mensagem, sem log, sem re-raise: nada do erro do PostgreSQL
            # pode escapar, e a ausencia de proveniencia ja e tratada.
            return

        for attrelid, attnum, schema, relation, column, relkind in rows:
            kind = ProvenanceKind.VIEW if relkind in _VIEW_RELKINDS else ProvenanceKind.DIRECT
            self._cache[(int(attrelid), int(attnum))] = ColumnOrigin(
                kind=kind,
                name=str(column),
                schema=str(schema),
                table=str(relation),
            )

        # Chave consultada e nao devolvida pelo catalogo: registra a ausencia
        # para nao repetir a consulta a cada result set.
        for key in keys:
            self._cache.setdefault(key, UNKNOWN_ORIGIN)


def _has_origin(key: ProvenanceKey) -> bool:
    """`ftable = 0` (ou `ftablecol = 0`) significa: sem coluna de origem."""
    oid, attnum = key
    return oid != 0 and attnum != 0
