"""Auditoria minima: apenas metadata operacional.

Este e o UNICO lugar do projeto autorizado a importar `logging`. Ate a Fase 4
nenhum modulo logava (D-012); a Fase 5 abre a excecao, e a abre estreita.

O que entra no log e definido por CONSTRUCAO, nao por disciplina: `QueryAudit`
tem exatamente os campos permitidos, e `AuditLog.record` so serializa esses
campos. Nao ha caminho pelo qual uma SQL, um valor de linha ou um segredo
cheguem aqui — nao existe parametro para isso.

NUNCA registrado: a SQL, valores, linhas, parametros, o result set (original ou
mascarado), segredos, o DSN ou a senha.

Correlacao entre entradas usa `request_id`, um UUID gerado por consulta.
Deliberadamente NAO se registra hash da SQL: um digest permitiria confirmar,
por comparacao, que uma consulta especifica foi executada — e com predicados
como `WHERE cpf = '...'` isso vira um oraculo sobre o dado. Ver D-035.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Final

#: Nome do logger. O operador controla destino e nivel por configuracao de
#: logging padrao do Python, sem que o Gateway precise saber onde vai parar.
LOGGER_NAME: Final = "maskgw.audit"

#: Mensagem fixa. O conteudo util vai em campos estruturados, nunca no texto.
MESSAGE: Final = "query"

#: Desfechos possiveis.
SUCCESS: Final = "success"
FAILURE: Final = "failure"


@dataclass(frozen=True, slots=True)
class QueryAudit:
    """Metadata de uma consulta. Estes sao os UNICOS campos auditados."""

    request_id: str
    outcome: str
    duration_ms: int
    row_count: int | None = None
    truncated: bool | None = None
    error_category: str | None = None

    def as_fields(self) -> dict[str, Any]:
        """Campos estruturados. Nada alem do que a dataclass declara."""
        return asdict(self)


class AuditLog:
    """Escreve entradas de auditoria. Sem estado, sem buffer, sem I/O proprio."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger if logger is not None else logging.getLogger(LOGGER_NAME)

    def record(self, entry: QueryAudit) -> None:
        """Registra uma consulta ja concluida."""
        self._logger.info(MESSAGE, extra={"maskgw": entry.as_fields()})

    def __repr__(self) -> str:
        return f"AuditLog(logger={self._logger.name!r})"
