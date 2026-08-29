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


class CapabilityError(MaskGatewayError):
    """Uma capacidade essencial nao esta disponivel na instalacao.

    Fatal no startup. Nao e politica de masking: e validacao de instalacao.
    A protecao contra bypass por alias depende de resolver `(oid, attnum)` no
    catalogo; uma role sem esse acesso desligaria a protecao em silencio.
    Ver docs/DECISIONS.md (D-026).
    """


class InvalidQuery(MaskGatewayError):  # noqa: N818 - nome definido pelo contrato externo
    """A consulta nao e SQL valida.

    Mensagem generica: o texto do parser cita trechos da propria SQL.
    """


class QueryRejected(MaskGatewayError):  # noqa: N818 - nome definido pelo contrato externo
    """A consulta e valida, mas a politica do Gateway a recusa.

    Carrega um `reason` de um conjunto FIXO de motivos (`RejectionReason`).
    Nem a SQL, nem nomes vindos dela, entram na mensagem.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"consulta rejeitada: {reason}")
        self.reason = reason


class QueryTimeout(DatabaseError):  # noqa: N818 - nome definido pelo contrato externo
    """A consulta excedeu o `statement_timeout` do PostgreSQL."""
