"""Configuracao completa do Gateway.

`load_config` continua devolvendo apenas a `MaskingPolicy`, para quem so
precisa do engine. `load_gateway_config` devolve tambem os limites de execucao
e a politica de funcoes SQL da Fase 4.

Fail-closed como o resto: valor fora dos limites impede a inicializacao.
Credenciais e DSN continuam fora do `masking.yaml`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from maskgw.config.loader import (
    compile_policy,
    deserialize,
    read_config_text,
    validate_file_config,
)
from maskgw.config.models import MaskingFileConfig
from maskgw.masking.rules import MaskingPolicy
from maskgw.masking.transformers.registry import TransformerRegistry
from maskgw.secretsource import SecretProvider
from maskgw.sql.policy import SqlPolicy


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Limites de execucao, aplicados no PostgreSQL."""

    statement_timeout_ms: int
    max_rows: int


@dataclass(frozen=True, slots=True)
class GatewayConfig:
    """Configuracao imutavel do Gateway, carregada uma vez no boot."""

    masking: MaskingPolicy
    database: DatabaseSettings
    sql: SqlPolicy


def build_gateway_config(
    parsed: MaskingFileConfig,
    policy: MaskingPolicy,
) -> GatewayConfig:
    """Monta a configuracao a partir do arquivo ja validado."""
    return GatewayConfig(
        masking=policy,
        database=DatabaseSettings(
            statement_timeout_ms=parsed.database.statement_timeout_ms,
            max_rows=parsed.database.max_rows,
        ),
        sql=SqlPolicy.build(
            extra_allowed_pg_functions=parsed.sql.allowed_pg_functions,
            extra_denied_functions=parsed.sql.denied_functions,
        ),
    )


def parse_gateway_config(
    raw: object,
    *,
    secrets: SecretProvider | None = None,
    registry: TransformerRegistry | None = None,
) -> GatewayConfig:
    """Valida uma estrutura ja desserializada e compila tudo."""
    parsed = validate_file_config(raw)
    policy = compile_policy(parsed, secrets=secrets, registry=registry)
    return build_gateway_config(parsed, policy)


def load_gateway_config_text(
    text: str,
    *,
    secrets: SecretProvider | None = None,
    registry: TransformerRegistry | None = None,
) -> GatewayConfig:
    """Carrega a configuracao completa a partir de texto YAML."""
    return parse_gateway_config(deserialize(text), secrets=secrets, registry=registry)


def load_gateway_config(
    path: str | Path,
    *,
    secrets: SecretProvider | None = None,
    registry: TransformerRegistry | None = None,
) -> GatewayConfig:
    """Carrega a configuracao completa a partir de um arquivo."""
    return load_gateway_config_text(read_config_text(path), secrets=secrets, registry=registry)
