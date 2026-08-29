"""Sanitizacao de erros do PostgreSQL.

A mensagem do PostgreSQL pode embutir valores de dados:

    invalid input syntax for type integer: "12345678901"

Por isso ela NUNCA e repassada. Tambem nao saem `str(exc)`, `repr(exc)`,
`exc.diag`, a query interna nem os parametros. Ver docs/SECURITY.md.

O SQLSTATE e usado APENAS para classificacao interna: a classe (dois primeiros
caracteres) escolhe uma das mensagens genericas fixas abaixo. Nem o SQLSTATE
nem qualquer outro dado da excecao original entram na mensagem devolvida.

A excecao original tambem nao e encadeada: o adapter levanta
`DatabaseError(...) from None`, para que nem um traceback renderizado
reexponha o texto do servidor.
"""

from __future__ import annotations

from typing import Final

import psycopg

from maskgw.errors import DatabaseError, QueryTimeout

#: Um SQLSTATE tem 5 caracteres; os dois primeiros identificam a classe.
_SQLSTATE_CLASS_LENGTH: Final = 2

#: `query_canceled`: e o que o `statement_timeout` produz.
QUERY_CANCELED_SQLSTATE: Final = "57014"

#: Mensagem do timeout. Nao cita a consulta nem a duracao real.
TIMEOUT_MESSAGE: Final = "a consulta excedeu o tempo maximo de execucao"

#: Mensagem usada quando a classe do SQLSTATE e desconhecida ou ausente.
GENERIC_MESSAGE: Final = "erro ao consultar o banco de dados"

#: Classe do SQLSTATE -> mensagem generica. Nenhum texto vem do servidor.
_MESSAGE_BY_CLASS: Final[dict[str, str]] = {
    "08": "falha de comunicacao com o banco de dados",
    "0A": "recurso nao suportado pelo banco de dados",
    "22": "erro de dados na consulta",
    "23": "violacao de restricao de integridade",
    "25": "estado de transacao invalido",
    "28": "falha de autenticacao no banco de dados",
    "40": "transacao revertida pelo banco de dados",
    "42": "consulta invalida ou nao permitida",
    "53": "recursos insuficientes no banco de dados",
    "54": "limite do banco de dados excedido",
    "57": "operacao interrompida pelo banco de dados",
    "58": "falha de sistema no banco de dados",
}


def classify(exc: psycopg.Error) -> str:
    """Classe do SQLSTATE, ou string vazia quando nao houver.

    Uso interno. O valor devolvido nao entra em nenhuma mensagem ao chamador.
    """
    sqlstate = exc.sqlstate
    if isinstance(sqlstate, str) and len(sqlstate) >= _SQLSTATE_CLASS_LENGTH:
        return sqlstate[:_SQLSTATE_CLASS_LENGTH]
    return ""


def sanitize_error(exc: psycopg.Error) -> DatabaseError:
    """Traduz um erro do psycopg em `DatabaseError` sem nenhum dado original.

    O cancelamento por `statement_timeout` vira `QueryTimeout`, que e um
    `DatabaseError` — o chamador distingue o caso sem receber nada do servidor.
    """
    if exc.sqlstate == QUERY_CANCELED_SQLSTATE:
        return QueryTimeout(TIMEOUT_MESSAGE)
    return DatabaseError(_MESSAGE_BY_CLASS.get(classify(exc), GENERIC_MESSAGE))
