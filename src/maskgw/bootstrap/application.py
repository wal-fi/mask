"""Composition root e lifecycle ordenado da aplicacao.

Este e o unico lugar que conhece a montagem do data plane MCP e, no futuro,
do admin plane. Os planos nao se importam entre si: `mcp/` conhece somente o
Gateway, e o futuro `admin/` conhecera o RuntimeRegistry.

Etapa 4 da Fase 7: ainda nao existe admin HTTP, thread HTTP, bind, lock de
arquivo nem persistencia administrativa. A ordem aplicavel hoje e:

1. carregar e compilar a configuracao;
2. construir e conectar o runtime inicial, com todos os capability checks;
3. construir o servidor MCP, ainda indisponivel;
4. executar exclusivamente em stdio;
5. depois que o data plane parar, fechar todos os runtimes uma unica vez.

Se qualquer passo de construcao falhar, todo recurso ja construido e fechado.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Final

from mcp.server import MCPServer

from maskgw.audit import AuditLog
from maskgw.config import GatewayConfig, load_config_bundle
from maskgw.db.postgres import PostgresAdapter
from maskgw.errors import ConfigError
from maskgw.gateway.service import Gateway
from maskgw.masking.engine import MaskingEngine
from maskgw.mcp.server import build_mcp_server
from maskgw.runtime import Runtime, RuntimeRegistry
from maskgw.secretsource import EnvSecretProvider, SecretProvider

#: Variavel de ambiente com o DSN do PostgreSQL. Nunca no `masking.yaml`.
DSN_ENV: Final = "MASKGW_DATABASE_DSN"

#: Variavel opcional para apontar outro `masking.yaml`.
CONFIG_PATH_ENV: Final = "MASKGW_CONFIG"

#: Caminho default da configuracao.
DEFAULT_CONFIG_PATH: Final = "config/masking.yaml"


class Application:
    """Aplicacao inteiramente composta, com lifecycle centralizado.

    Construir nao disponibiliza o MCP e nao cria thread. `run()` e a unica
    porta que inicia o data plane, sempre em stdio. O fechamento dos runtimes
    ocorre somente depois que `MCPServer.run()` terminou, portanto nenhuma
    query nova pode ser aceita sobre um registry desmontado.

    `close()` e idempotente. Se for chamado enquanto o stdio ainda esta ativo,
    ele nao fecha recursos sob queries em andamento; o `finally` de `run()`
    completa o fechamento assim que o data plane terminar.
    """

    __slots__ = (
        "_closed",
        "_config",
        "_gateway",
        "_lifecycle_lock",
        "_mcp_server",
        "_registry",
        "_running",
    )

    def __init__(
        self,
        *,
        gateway: Gateway,
        config: GatewayConfig,
        registry: RuntimeRegistry,
        mcp_server: MCPServer,
    ) -> None:
        self._gateway = gateway
        self._config = config
        self._registry = registry
        self._mcp_server = mcp_server
        self._lifecycle_lock = threading.Lock()
        self._running = False
        self._closed = False

    @property
    def gateway(self) -> Gateway:
        return self._gateway

    @property
    def config(self) -> GatewayConfig:
        return self._config

    @property
    def registry(self) -> RuntimeRegistry:
        return self._registry

    @property
    def revision(self) -> int:
        """Revision carregada, unica metadata emitida no startup (§9.2)."""
        return self._registry.current.revision

    @property
    def mcp_server(self) -> MCPServer:
        """Servidor do data plane, ja composto mas ainda nao iniciado."""
        return self._mcp_server

    def run(self) -> None:
        """Executa o data plane MCP em stdio e sempre faz shutdown ordenado."""
        with self._lifecycle_lock:
            if self._closed:
                msg = "aplicacao ja encerrada"
                raise RuntimeError(msg)
            if self._running:
                msg = "aplicacao ja esta em execucao"
                raise RuntimeError(msg)
            self._running = True

        try:
            # D-036: o transporte continua exclusivamente stdio.
            self._mcp_server.run(transport="stdio")
        finally:
            # `run` terminou: o data plane ja nao aceita queries. So agora os
            # runtimes podem ser fechados (§9.2).
            with self._lifecycle_lock:
                self._running = False
            self.close()

    def close(self) -> None:
        """Fecha runtimes uma unica vez, sempre depois do data plane."""
        with self._lifecycle_lock:
            if self._closed or self._running:
                return
            self._closed = True
        self._registry.close_all()

    def __enter__(self) -> Application:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        with self._lifecycle_lock:
            state = "closed" if self._closed else "running" if self._running else "ready"
        return f"Application(revision={self._registry.current.revision}, state={state!r})"


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
    """Constroi os planos inteiros ou levanta sem deixar recurso de pe."""
    adapter: PostgresAdapter | None = None
    registry: RuntimeRegistry | None = None

    try:
        # Modelo validado e objetos compilados permanecem juntos (D-047).
        bundle = load_config_bundle(config_path, secrets=secrets)
        file_config = bundle.file_config
        config = bundle.gateway
        engine = MaskingEngine(config.masking)

        # Runtime inicial: conexao read-only, timeout e capability de
        # proveniencia sao conferidos antes de qualquer plano ficar disponivel.
        dsn = conninfo if conninfo is not None else resolve_dsn(secrets)
        adapter = PostgresAdapter(
            dsn,
            engine,
            settings=config.database,
            sql_policy=config.sql,
            verify_capabilities=True,
        )
        adapter.connect()

        registry = RuntimeRegistry(
            Runtime(
                revision=file_config.revision,
                file_config=file_config,
                config=config,
                engine=engine,
                adapter=adapter,
            )
        )
        gateway = Gateway(registry, audit if audit is not None else AuditLog())

        # O MCP e construido por ultimo e ainda nao esta disponivel: somente
        # `Application.run()` abre o stdio. O futuro admin plane sera composto
        # separadamente neste mesmo pacote.
        mcp_server = build_mcp_server(gateway)
        return Application(
            gateway=gateway,
            config=config,
            registry=registry,
            mcp_server=mcp_server,
        )
    except BaseException:
        # Falha parcial: fechar o maior agregado ja construido. O adapter e
        # fechado diretamente apenas se o registry ainda nao existia.
        if registry is not None:
            registry.close_all()
        elif adapter is not None:
            adapter.close()
        raise
