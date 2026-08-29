"""Descritor de coluna consumido pelo Masking Engine.

O engine nao opera sobre uma string solta de nome de coluna: ele recebe os dois
nomes usados no matching.

- `output_name`: nome da coluna como sera devolvida ao cliente (o alias).
- `origin_name`: nome real da coluna de origem, quando determinavel.

A regra e aplicada se QUALQUER um dos dois casar. E isso que neutraliza o
bypass por alias:

    SELECT cpf AS documento
        output_name = "documento"  -> nao casa
        origin_name = "cpf"        -> casa
        resultado: mascarado

`origin_schema` e `origin_table` acompanham a origem como metadata de
auditoria; o matching da Fase 3 NAO os usa — as regras continuam globais por
nome de coluna, como manda `docs/MASKING-SPEC.md`.

A proveniencia e preenchida pelo adapter a partir da metadata do proprio
PostgreSQL. Nunca a partir dos valores das linhas.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProvenanceKind(StrEnum):
    """Quanto se sabe sobre a origem de uma coluna do result set.

    A distincao entre DERIVED e UNKNOWN e deliberada e vale a pena:

    - `DERIVED` e uma afirmacao DO POSTGRESQL. O protocolo devolve
      `ftable = 0` quando a coluna nao vem de uma unica coluna de tabela —
      expressao, literal, agregado ou ramo de UNION. Nao ha origem a resolver.
    - `UNKNOWN` e uma admissao NOSSA. O PostgreSQL indicou uma origem, mas nao
      conseguimos traduzi-la (consulta ao catalogo falhou, ou a linha de
      `pg_attribute` nao existe mais). A origem existe; nos e que nao a temos.

    Em ambos os casos `origin_name` fica `None` e o matching recai sobre
    `output_name`. Separa-los importa para auditoria e para o hardening futuro:
    um `UNKNOWN` frequente e sinal de privilegio faltando no catalogo, e nao de
    consulta legitimamente sem origem.
    """

    #: Coluna de uma tabela (ou similar): origem resolvida.
    DIRECT = "direct"
    #: Coluna de uma view ou materialized view. A origem e a coluna DA VIEW.
    VIEW = "view"
    #: O PostgreSQL afirma que nao ha coluna de origem unica.
    DERIVED = "derived"
    #: Nao foi possivel determinar. Default conservador.
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ColumnDescriptor:
    """Identificacao de uma coluna do result set."""

    output_name: str
    origin_name: str | None = None
    origin_schema: str | None = None
    origin_table: str | None = None
    provenance_kind: ProvenanceKind = ProvenanceKind.UNKNOWN

    @property
    def names(self) -> tuple[str, ...]:
        """Nomes avaliados no matching, sem duplicatas e sem None."""
        if self.origin_name is None or self.origin_name == self.output_name:
            return (self.output_name,)
        return (self.output_name, self.origin_name)

    @property
    def qualified_origin(self) -> str | None:
        """`schema.tabela.coluna`, quando conhecido. Metadata, nunca valor."""
        if self.origin_name is None:
            return None
        parts = [self.origin_schema, self.origin_table, self.origin_name]
        return ".".join(part for part in parts if part)
