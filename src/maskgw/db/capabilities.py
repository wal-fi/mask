"""Verificacao de capacidades da conexao, para o startup do Gateway.

A protecao contra bypass por alias (Fase 3) depende de traduzir
`(table_oid, attnum)` em schema, relacao e coluna, lendo `pg_attribute`,
`pg_class` e `pg_namespace`. Uma role sem esse acesso faz TODA coluna cair em
`UNKNOWN`: `SELECT cpf AS documento` volta a passar em claro, e nada avisa.

A resolucao em runtime e deliberadamente tolerante a falha (D-025): derrubar
uma consulta inteira por um problema de catalogo seria pior. O preco disso e
que uma role mal configurada degradaria a protecao em silencio.

Este modulo cobre exatamente esse buraco: uma verificacao EXPLICITA, para rodar
no startup, que falha alto quando a capacidade nao existe.

Nao muda nenhuma politica de masking. Colunas `DERIVED` e `UNKNOWN` continuam
seguindo o default ALLOW. Isto e validacao de instalacao. Ver D-026.
"""

from __future__ import annotations

from typing import Any, Final

import psycopg

from maskgw.db.provenance import ProvenanceResolver
from maskgw.errors import CapabilityError
from maskgw.masking.descriptor import ProvenanceKind

#: Coluna-sonda. Um catalogo do sistema, presente em qualquer PostgreSQL, para
#: que a verificacao nao dependa do schema da aplicacao.
PROBE_RELATION: Final = "pg_catalog.pg_class"
PROBE_SCHEMA: Final = "pg_catalog"
PROBE_TABLE: Final = "pg_class"
PROBE_COLUMN: Final = "relname"

_PROBE_QUERY: Final = """
SELECT a.attrelid, a.attnum
FROM pg_attribute a
WHERE a.attrelid = %s::regclass AND a.attname = %s
"""


def check_provenance_capability(connection: psycopg.Connection[Any]) -> None:
    """Confirma que a conexao resolve `(oid, attnum)` para nome de coluna.

    Levanta `CapabilityError` se a capacidade nao estiver disponivel. A
    mensagem nunca inclui o erro do PostgreSQL, o DSN ou a role.
    """
    key = _probe_key(connection)

    # Passa pelo resolver REAL, e nao por uma consulta paralela: o que se quer
    # provar e que o caminho usado em producao funciona nesta instalacao.
    origin = ProvenanceResolver(connection).resolve([key])[0]

    if origin.kind is ProvenanceKind.UNKNOWN or origin.name is None:
        msg = (
            "a conexao nao consegue resolver a origem de uma coluna: verifique "
            "se a role tem SELECT em pg_attribute, pg_class e pg_namespace; "
            "sem isso a protecao contra alias fica desligada"
        )
        raise CapabilityError(msg)

    resolved = (origin.schema, origin.table, origin.name)
    if resolved != (PROBE_SCHEMA, PROBE_TABLE, PROBE_COLUMN):
        # Nomes de catalogo do sistema: constantes, nunca dado da aplicacao.
        msg = (
            "a resolucao de origem devolveu um resultado inesperado para a "
            f"coluna-sonda {PROBE_RELATION}.{PROBE_COLUMN}"
        )
        raise CapabilityError(msg)


def _probe_key(connection: psycopg.Connection[Any]) -> tuple[int, int]:
    """`(oid, attnum)` da coluna-sonda, lido do catalogo."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(_PROBE_QUERY, (PROBE_RELATION, PROBE_COLUMN))
            row = cursor.fetchone()
    except psycopg.Error:
        # O erro do PostgreSQL nao sai daqui: ele cita objetos e privilegios.
        row = None

    if row is None:
        msg = (
            "a conexao nao consegue ler o catalogo do PostgreSQL: verifique se "
            "a role tem SELECT em pg_attribute, pg_class e pg_namespace; sem "
            "isso a protecao contra alias fica desligada"
        )
        raise CapabilityError(msg)

    return (int(row[0]), int(row[1]))
