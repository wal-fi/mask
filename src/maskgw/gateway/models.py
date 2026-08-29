"""Modelo publico de resultado e categorias de erro.

Isto e o que sai do Gateway — e, por consequencia, o que o cliente MCP ve.

O que NAO esta aqui e deliberado. A proveniencia (`origin_name`,
`origin_schema`, `origin_table`, `provenance_kind`) fica no lado de dentro: ela
descreve o MECANISMO de protecao, e o cliente precisa do dado ja seguro, nao do
mapa de como ele foi protegido. Expor `origin_table` diria a uma IA qual tabela
sustenta cada coluna, o que e reconhecimento gratuito. Ver D-033.

Tambem nao saem: `table_oid`, `attnum`, DSN, nomes de segredo, objetos psycopg,
cursor, traceback e as regras de masking.

As linhas sao POSICIONAIS. Nomes de coluna duplicados sao validos em
PostgreSQL, entao converter para dicionario por nome colapsaria colunas.
"""

from __future__ import annotations

import base64
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from maskgw.errors import (
    CapabilityError,
    ConfigError,
    DatabaseError,
    InvalidQuery,
    MaskGatewayError,
    QueryRejected,
    QueryTimeout,
)


class ErrorCategory(StrEnum):
    """Categorias externas de erro. O cliente nunca ve mais que isto."""

    INVALID_QUERY = "INVALID_QUERY"
    QUERY_REJECTED = "QUERY_REJECTED"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    DATABASE_ERROR = "DATABASE_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"


#: Mensagens curtas destinadas ao modelo. Fixas, em ingles, sem nenhum detalhe
#: da consulta, do banco ou da configuracao.
CATEGORY_MESSAGES: Final[dict[ErrorCategory, str]] = {
    ErrorCategory.INVALID_QUERY: "The query is not valid SQL.",
    ErrorCategory.QUERY_REJECTED: "The query was rejected by the database security policy.",
    ErrorCategory.QUERY_TIMEOUT: "The query exceeded the allowed execution time.",
    ErrorCategory.DATABASE_ERROR: "The database could not complete the query.",
    ErrorCategory.CONFIGURATION_ERROR: "The gateway is not correctly configured.",
}


def categorize(exc: BaseException) -> ErrorCategory:
    """Traduz um erro interno em categoria externa.

    A ordem importa: `QueryTimeout` e subclasse de `DatabaseError`, e
    `CapabilityError` e um problema de instalacao, nao do banco.
    """
    if isinstance(exc, InvalidQuery):
        return ErrorCategory.INVALID_QUERY
    if isinstance(exc, QueryRejected):
        return ErrorCategory.QUERY_REJECTED
    if isinstance(exc, QueryTimeout):
        return ErrorCategory.QUERY_TIMEOUT
    if isinstance(exc, ConfigError | CapabilityError):
        return ErrorCategory.CONFIGURATION_ERROR
    if isinstance(exc, DatabaseError):
        return ErrorCategory.DATABASE_ERROR
    # Erro inesperado: a categoria mais generica, nunca o detalhe.
    return ErrorCategory.DATABASE_ERROR


class GatewayError(MaskGatewayError):
    """Unico erro que sai do Gateway.

    Carrega apenas a categoria e a mensagem fixa correspondente. A excecao
    interna nunca e encadeada — nem por `__cause__`, nem por `__context__`.
    """

    def __init__(self, category: ErrorCategory) -> None:
        super().__init__(CATEGORY_MESSAGES[category])
        self.category = category


class QueryColumn(BaseModel):
    """Uma coluna do resultado, como o cliente a ve."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Column name as returned by the query")
    masked: bool = Field(description="Whether a data protection policy transformed this column")


class QueryResult(BaseModel):
    """Resultado seguro de uma consulta."""

    model_config = ConfigDict(frozen=True)

    columns: list[QueryColumn] = Field(description="Result columns, in order")
    rows: list[list[Any]] = Field(
        description="Result rows as positional arrays aligned with columns"
    )
    row_count: int = Field(description="Number of rows returned")
    truncated: bool = Field(description="True when the result was cut at the configured row limit")


def jsonable(value: object) -> object:
    """Converte um valor para algo que o structured output consiga serializar.

    `Decimal`, `datetime`, `date`, `UUID` e `dict` o Pydantic ja resolve. Bytes
    nao: uma coluna `bytea` NAO mascarada com conteudo que nao seja UTF-8 faz a
    serializacao falhar. Medido contra o SDK. Base64 mantem o valor completo e
    e a mesma forma usada na canonicalizacao (D-015).
    """
    if isinstance(value, bytes | bytearray):
        return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, memoryview):
        return base64.b64encode(value.tobytes()).decode("ascii")
    return value
