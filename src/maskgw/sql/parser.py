"""Parsing de SQL com pglast.

O parser oficial do PostgreSQL, via libpg_query. Nenhuma decisao do Gateway
sobre SQL e tomada por regex ou por comparacao de palavra-chave.

A SQL invalida e rejeitada ANTES de chegar ao banco.

A mensagem do pglast cita trechos da propria consulta
(`syntax error at or near "SELEC"`). Ela nunca e propagada: sai
`InvalidQuery` com texto fixo, e sem encadeamento — nem `__cause__`, nem
`__context__`. Ver D-017.
"""

from __future__ import annotations

from typing import Any, Final, NoReturn

from pglast import ast, parse_sql
from pglast.parser import ParseError

from maskgw.errors import InvalidQuery, QueryRejected

#: Motivos de rejeicao. Conjunto FIXO: nenhum texto vem da consulta.
NO_STATEMENT: Final = "nenhum statement executavel"
MULTIPLE_STATEMENTS: Final = "mais de um statement"


def parse_single_statement(sql: str) -> ast.RawStmt:
    """Parseia e exige exatamente UM statement executavel.

    O parser do PostgreSQL descarta statements vazios: `SELECT 1;;` e
    `SELECT 1;` produzem um unico statement, enquanto `;` e a string vazia
    produzem nenhum. Medido em `tests/test_sql_parser.py`.

    O criterio, portanto, e o numero de statements EXECUTAVEIS que o parser
    reconheceu — nao a contagem de ponto e virgula.
    """
    statements = parse_statements(sql)

    if not statements:
        raise QueryRejected(NO_STATEMENT)
    if len(statements) > 1:
        raise QueryRejected(MULTIPLE_STATEMENTS)

    return statements[0]


def parse_statements(sql: str) -> tuple[ast.RawStmt, ...]:
    """Parseia a SQL. Nunca propaga a mensagem do parser."""
    if not isinstance(sql, str):
        _reject_invalid()
    try:
        parsed: Any = parse_sql(sql)
    except ParseError:
        # Fora do handler para nao deixar a excecao original em __context__.
        parsed = None
    except ValueError:
        # pglast levanta ValueError para entradas degeneradas.
        parsed = None

    if parsed is None:
        _reject_invalid()

    return tuple(parsed)


def _reject_invalid() -> NoReturn:
    """Levanta `InvalidQuery` sem encadeamento e sem citar a consulta."""
    msg = "sintaxe SQL invalida"
    raise InvalidQuery(msg) from None
