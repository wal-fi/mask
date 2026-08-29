"""Composicao das dependencias do Gateway.

Toda a construcao vive aqui. O handler MCP e fino por desenho: ele nao carrega
configuracao, nao conecta, nao constroi engine.

Ordem de inicializacao, e o que cada passo garante:

1. **configuracao** — `masking.yaml` validado; invalida impede subir
2. **segredos** — chave HMAC do ambiente; ausente com regra que a exige,
   impede subir
3. **Masking Engine** — politica imutavel, compilada uma vez
4. **conexao PostgreSQL** — read-only e `statement_timeout` aplicados e
   CONFERIDOS na sessao (D-028)
5. **capability check de proveniencia** — sem ela a protecao contra alias
   estaria desligada; impede subir (D-026)
6. **SQL Validator** — a politica de funcoes entra no adapter
7. **Gateway** — a fachada
8. so entao o MCP e disponibilizado, por quem chama esta funcao

Os passos 4 e 5 acontecem dentro de `PostgresAdapter.connect()`.

**Se qualquer passo falhar, `build_application` levanta e nada e devolvido.**
Nao existe estado parcialmente funcional: sem Gateway, nao ha servidor MCP.
PostgreSQL indisponivel no startup, portanto, impede a subida — o processo nao
fica de pe esperando o banco voltar. Ver D-034.

O DSN vem do ambiente, nunca do `masking.yaml`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from maskgw.audit import AuditLog
from maskgw.config import GatewayConfig, load_gateway_config
from maskgw.db.postgres import PostgresAdapter
from maskgw.errors import ConfigError
from maskgw.gateway.service import Gateway
from maskgw.masking.engine import MaskingEngine
from maskgw.secretsource import EnvSecretProvider, SecretProvider

#: Variavel de ambiente com o DSN do PostgreSQL. Nunca no `masking.yaml`.
DSN_ENV: Final = "MASKGW_DATABASE_DSN"

#: Caminho default da configuracao.
DEFAULT_CONFIG_PATH: Final = "config/masking.yaml"


@dataclass(frozen=True, slots=True)
class Application:
    """Aplicacao pronta. Se existe, esta inteiramente funcional."""

    gateway: Gateway
    config: GatewayConfig

    def close(self) -> None:
        self.gateway.close()


def resolve_dsn(secrets: SecretProvider | None = None) -> str:
    """Le o DSN do ambiente. Ausente e erro fatal de configuracao."""
    provider = secrets if secrets is not None else EnvSecretProvider()
    dsn = provider.get(DSN_ENV)
    if dsn is None:
        msg = (
            f"DSN do banco ausente: defina a variavel de ambiente {DSN_ENV}. "
            "Credenciais nunca sao lidas do masking.yaml"
        )
        raise ConfigError(msg)
    return dsn


def build_application(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    conninfo: str | None = None,
    secrets: SecretProvider | None = None,
    audit: AuditLog | None = None,
) -> Application:
    """Constroi a aplicacao inteira, ou levanta sem deixar nada de pe."""
    # 1 e 2: configuracao e segredos.
    config = load_gateway_config(config_path, secrets=secrets)

    # 3: Masking Engine.
    engine = MaskingEngine(config.masking)

    # 4, 5 e 6: conexao verificada, capability check e politica de funcoes.
    dsn = conninfo if conninfo is not None else resolve_dsn(secrets)
    adapter = PostgresAdapter(
        dsn,
        engine,
        settings=config.database,
        sql_policy=config.sql,
        verify_capabilities=True,
    )
    try:
        adapter.connect()
    except BaseException:
        adapter.close()
        raise

    # 7: a fachada.
    gateway = Gateway(adapter, audit if audit is not None else AuditLog())
    return Application(gateway=gateway, config=config)


def dsn_from_environment() -> str:
    """Atalho para bootstrap: le o DSN de `os.environ`."""
    raw = os.environ.get(DSN_ENV, "").strip()
    if not raw:
        msg = f"DSN do banco ausente: defina a variavel de ambiente {DSN_ENV}"
        raise ConfigError(msg)
    return raw
