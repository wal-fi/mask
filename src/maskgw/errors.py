"""Erros do Gateway.

Nenhuma mensagem de erro deste modulo pode conter valores de dados, chaves ou
segredos. Apenas metadata: nomes de regra, nomes de transformer, nomes de
parametro.
"""

from __future__ import annotations


class MaskGatewayError(Exception):
    """Erro base do Gateway."""


class ConfigError(MaskGatewayError):
    """Configuracao invalida.

    Sempre fatal: impede a inicializacao do processo (fail-closed).
    """


class TransformerError(MaskGatewayError):
    """Falha na construcao ou execucao de um transformer."""


class DatabaseError(MaskGatewayError):
    """Falha ao falar com o banco de dados, ja sanitizada.

    E o unico erro de banco que sai do adapter. A excecao original do psycopg
    nunca e encadeada nem repassada: a mensagem do PostgreSQL pode embutir
    valores (`invalid input syntax for type integer: "..."`). Ver
    `maskgw.db.sanitize` e docs/SECURITY.md.
    """
