"""Modelos de configuracao (Pydantic).

`extra="forbid"` em todos os modelos: uma chave desconhecida — inclusive um
erro de digitacao como `transfomer:` — impede a inicializacao. Fail-closed.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from maskgw.masking.rules import MatchMode

_STRICT = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)


class MatchConfig(BaseModel):
    """Campos comuns a regras e exceptions."""

    model_config = _STRICT

    match: str = Field(min_length=1, description="Padrao comparado ao nome da coluna")
    mode: MatchMode = MatchMode.CONTAINS
    case_sensitive: bool = False


class ExceptionConfig(MatchConfig):
    """Exception: tem prioridade absoluta e nao possui transformer."""


class RuleConfig(MatchConfig):
    """Regra de masking."""

    transformer: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


#: Limites do `statement_timeout`. Abaixo do minimo qualquer consulta real
#: falharia; acima do maximo o timeout deixaria de ser uma protecao.
MIN_STATEMENT_TIMEOUT_MS = 100
MAX_STATEMENT_TIMEOUT_MS = 600_000

#: Limites do numero maximo de linhas devolvidas por consulta.
MIN_MAX_ROWS = 1
MAX_MAX_ROWS = 1_000_000


class DatabaseConfig(BaseModel):
    """Limites de execucao aplicados no lado do PostgreSQL.

    Nao ha DSN nem credencial aqui: elas continuam fora do `masking.yaml`.
    """

    model_config = _STRICT

    statement_timeout_ms: int = Field(
        default=30_000,
        ge=MIN_STATEMENT_TIMEOUT_MS,
        le=MAX_STATEMENT_TIMEOUT_MS,
        description="Timeout por statement, aplicado pelo PostgreSQL",
    )
    max_rows: int = Field(
        default=1_000,
        ge=MIN_MAX_ROWS,
        le=MAX_MAX_ROWS,
        description="Maximo de linhas devolvidas; o excesso marca truncated",
    )


class SqlConfig(BaseModel):
    """Extensoes da politica de funcoes SQL.

    A politica default vive em `maskgw.sql.policy`. Aqui so se acrescenta.
    Em conflito, a negacao vence.
    """

    model_config = _STRICT

    allowed_pg_functions: list[str] = Field(default_factory=list)
    denied_functions: list[str] = Field(default_factory=list)


class MaskingFileConfig(BaseModel):
    """Conteudo completo do `masking.yaml`."""

    model_config = _STRICT

    masking: list[RuleConfig] = Field(default_factory=list)
    exceptions: list[ExceptionConfig] = Field(default_factory=list)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    sql: SqlConfig = Field(default_factory=SqlConfig)
