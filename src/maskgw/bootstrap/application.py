"""Composition root e lifecycle ordenado da aplicacao.

Este e o unico lugar que conhece a montagem do data plane MCP e do admin
plane. Os planos nao se importam entre si: `mcp/` conhece somente o Gateway, e
`admin/` conhece somente o `RuntimeRegistry` e o `ConfigFileStore`.

Etapa 6 da Fase 7: o admin plane existe como SECAO CRITICA, sem HTTP. Nao ha
thread nova, porta, bind nem autenticacao — isso e a Etapa 7. Por isso o admin
e composto por um parametro explicito de construcao, e nao por variavel de
ambiente: `MASKGW_ADMIN_ENABLED`, `MASKGW_ADMIN_TOKEN`, `MASKGW_ADMIN_BIND` e
`MASKGW_ADMIN_PORT` sao lidos pela aplicacao HTTP, quando ela existir.

Ordem de startup aplicavel hoje (secao 9.2, sem os passos de HTTP):

1. com admin habilitado, verificar o filesystem e adquirir o lock exclusivo;
2. carregar e compilar a configuracao — dos bytes exatos do lock, quando ha
   admin, para que o digest de referencia case com o runtime publicado;
3. construir e conectar o runtime inicial, com todos os capability checks;
4. construir o servidor MCP, ainda indisponivel;
5. executar exclusivamente em stdio;
6. depois que o data plane parar: recusar operacoes administrativas, fechar
   todos os runtimes uma unica vez e so entao liberar o lock de arquivo.

Se qualquer passo de construcao falhar, todo recurso ja construido e fechado.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Final

from mcp.server import MCPServer

from maskgw.admin import AdapterFactory, AdminConfigService, decode_document
from maskgw.audit import AuditLog
from maskgw.config import (
    ConfigFileStore,
    GatewayConfig,
    LoadedConfig,
    load_config_bundle,
    load_config_bundle_text,
)
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
        "_admin",
        "_closed",
        "_config",
        "_config_store",
        "_gateway",
        "_lifecycle_lock",
        "_mcp_server",
        "_registry",
        "_running",
    )

    def __init__(  # noqa: PLR0913 - colaboradores compostos, todos keyword-only
        self,
        *,
        gateway: Gateway,
        config: GatewayConfig,
        registry: RuntimeRegistry,
        mcp_server: MCPServer,
        admin: AdminConfigService | None = None,
        config_store: ConfigFileStore | None = None,
    ) -> None:
        self._gateway = gateway
        self._config = config
        self._registry = registry
        self._mcp_server = mcp_server
        self._admin = admin
        self._config_store = config_store
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
    def admin(self) -> AdminConfigService | None:
        """Secao critica administrativa, ou None sem admin habilitado."""
        return self._admin

    @property
    def config_store(self) -> ConfigFileStore | None:
        """Filesystem com lock exclusivo, ou None sem admin habilitado."""
        return self._config_store

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
        """Fecha tudo uma unica vez, na ordem da secao 9.2.

        Recusar operacoes administrativas vem primeiro; fechar os runtimes,
        depois; liberar o lock de arquivo, por ultimo. Inverter a ultima ordem
        deixaria o lock livre enquanto uma conexao ainda esta sendo fechada, e
        um segundo processo poderia entrar cedo demais.
        """
        with self._lifecycle_lock:
            if self._closed or self._running:
                return
            self._closed = True
        if self._admin is not None:
            self._admin.close()
        self._registry.close_all()
        if self._config_store is not None:
            self._config_store.close()

    def __enter__(self) -> Application:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        with self._lifecycle_lock:
            state = "closed" if self._closed else "running" if self._running else "ready"
        return (
            f"Application(revision={self._registry.current.revision}, state={state!r}, "
            f"admin={self._admin is not None})"
        )


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


def make_adapter_factory(dsn: str) -> AdapterFactory:
    """Fabrica de adapters que captura o DSN, para que o admin nunca o veja.

    Credenciais, host e banco continuam vindo so de secret/env e nao sao campo
    administrativo — nem para leitura (D-048). O que a configuracao muda sao os
    parametros de sessao derivados dela, e por isso o candidato reconecta.
    """

    def factory(*, config: GatewayConfig, engine: MaskingEngine) -> PostgresAdapter:
        return PostgresAdapter(
            dsn,
            engine,
            settings=config.database,
            sql_policy=config.sql,
            verify_capabilities=True,
        )

    return factory


def build_application(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    conninfo: str | None = None,
    secrets: SecretProvider | None = None,
    audit: AuditLog | None = None,
    admin_enabled: bool = False,
) -> Application:
    """Constroi os planos inteiros ou levanta sem deixar recurso de pe.

    Com `admin_enabled=False` — o default — o processo e exatamente o de hoje:
    nenhum lock de arquivo, nenhuma secao critica administrativa e nenhum
    caminho de escrita.
    """
    store: ConfigFileStore | None = None
    adapter: PostgresAdapter | None = None
    registry: RuntimeRegistry | None = None

    try:
        # Passos 2 e 3 da secao 9.2: o filesystem e verificado e o lock
        # exclusivo e adquirido ANTES de qualquer coisa ser construida. Um
        # segundo processo administrativo sobre o mesmo arquivo falha aqui.
        bundle, store, digest = _load_configuration(
            config_path,
            secrets=secrets,
            admin_enabled=admin_enabled,
        )
        file_config = bundle.file_config
        config = bundle.gateway
        engine = MaskingEngine(config.masking)

        # Runtime inicial: conexao read-only, timeout e capability de
        # proveniencia sao conferidos antes de qualquer plano ficar disponivel.
        dsn = conninfo if conninfo is not None else resolve_dsn(secrets)
        adapter_factory = make_adapter_factory(dsn)
        adapter = adapter_factory(config=config, engine=engine)
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

        # O admin plane e o registry mais o filesystem, e nada do plano de
        # dados: ele nao conhece Gateway nem MCP. O digest de referencia sao os
        # bytes EXATOS dos quais este runtime foi construido.
        admin = (
            None
            if store is None
            else AdminConfigService(
                store=store,
                registry=registry,
                adapter_factory=adapter_factory,
                reference_digest=digest,
                secrets=secrets,
            )
        )

        # O MCP e construido por ultimo e ainda nao esta disponivel: somente
        # `Application.run()` abre o stdio.
        mcp_server = build_mcp_server(gateway)
        return Application(
            gateway=gateway,
            config=config,
            registry=registry,
            mcp_server=mcp_server,
            admin=admin,
            config_store=store,
        )
    except BaseException:
        # Falha parcial: fechar o maior agregado ja construido, e o lock de
        # arquivo por ultimo. O adapter e fechado diretamente apenas se o
        # registry ainda nao existia.
        if registry is not None:
            registry.close_all()
        elif adapter is not None:
            adapter.close()
        if store is not None:
            store.close()
        raise


def _load_configuration(
    config_path: str | Path,
    *,
    secrets: SecretProvider | None,
    admin_enabled: bool,
) -> tuple[LoadedConfig, ConfigFileStore | None, str]:
    """Carrega a configuracao e, com admin, prende o arquivo que a originou.

    Sem admin nao ha digest a manter, porque nao ha escrita: o Gateway le o
    arquivo uma vez e nunca mais o toca.

    Com admin, o runtime inicial e construido a partir dos BYTES do snapshot, e
    nao de uma segunda leitura. Duas leituras poderiam divergir — bastaria uma
    edicao entre elas — e o digest de referencia passaria a descrever um
    arquivo que nao originou o runtime publicado. Modelo validado e objetos
    compilados continuam viajando juntos (D-047).
    """
    if not admin_enabled:
        return load_config_bundle(config_path, secrets=secrets), None, ""

    store = ConfigFileStore.open(config_path)
    try:
        snapshot = store.read_snapshot()
        bundle = load_config_bundle_text(decode_document(snapshot.data), secrets=secrets)
    except BaseException:
        store.close()
        raise
    return bundle, store, snapshot.digest
