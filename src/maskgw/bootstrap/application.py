"""Composition root e lifecycle ordenado da aplicacao.

Este e o unico lugar que conhece a montagem do data plane MCP e do admin
plane. Os planos nao se importam entre si: `mcp/` conhece somente o Gateway, e
`admin/` conhece somente o `RuntimeRegistry`, o `ConfigFileStore` e a propria
fronteira HTTP.

Ordem de startup (secao 9.2), e falha em qualquer passo termina o processo:

1. ler e validar `MASKGW_ADMIN_ENABLED`, `MASKGW_ADMIN_TOKEN` (>= 32),
   `MASKGW_ADMIN_BIND` (so loopback) e `MASKGW_ADMIN_PORT`. Acontece ANTES de
   tudo, em `resolve_admin_settings`, chamado pela fronteira de processo: um
   token curto nao deve chegar a abrir arquivo algum;
2. com admin habilitado, verificar o filesystem e adquirir o lock exclusivo;
3. carregar e compilar a configuracao — dos bytes exatos do lock, quando ha
   admin, para que o digest de referencia case com o runtime publicado;
4. construir e conectar o runtime inicial, com todos os capability checks;
5. iniciar a thread HTTP administrativa, nao-daemon;
6. AGUARDAR a confirmacao de que o socket esta escutando, com timeout. Porta
   ocupada, bind recusado ou timeout desmontam tudo e o processo NAO sobe;
7. so entao construir o servidor MCP e, em `run()`, disponibiliza-lo em stdio;
8. registrar em `stderr` a revision carregada — nunca em `stdout`.

O passo 6 e o que impede o pior caso: se o MCP subisse antes, o Gateway
atenderia queries por um tempo e entao morreria por uma porta ocupada, com o
administrador convencido de que a Admin API esta no ar.

Shutdown, na ordem inversa e igualmente exigida:

1. parar de aceitar novas queries MCP (o `run()` ja retornou);
2. recusar novas operacoes administrativas;
3. sinalizar o servidor HTTP e AGUARDAR (`join`) a thread;
4. so entao fechar o runtime publicado e todos os aposentados;
5. liberar o lock de arquivo por ultimo.

Aguardar a thread HTTP **antes** de fechar os runtimes e o que impede uma
requisicao administrativa em voo de encontrar um registry ja desmontado. O
passo 3 nao tem timeout: `AdminHttpServer.stop()` bloqueia ate a thread
terminar, e so entao os passos 4 e 5 acontecem. Uma ordem que pudesse avancar
sem o passo anterior ter concluido nao seria uma ordem.

`_closing` marca que a sequencia comecou e nunca volta atras. A partir dai
`run()` recusa a aplicacao e `repr()` reporta `closing`: entre o inicio e o fim
do shutdown o `AdminConfigService` ja recusa operacoes, e oferecer o MCP sobre
esse estado seria atender queries sobre recursos em desmontagem.

Se qualquer passo de construcao falhar, todo recurso ja construido e fechado —
inclusive um servidor HTTP cujo proprio `start()` tenha falhado depois de criar
a thread, porque a referencia e adotada ANTES de inicia-lo.

## Dois parametros, nao um

`admin_enabled` compoe a SECAO CRITICA administrativa: lock de arquivo, digest
de referencia e caminho de escrita. `admin_http` acrescenta a FRONTEIRA HTTP:
thread, socket e rotas. Sao separados porque a secao critica e utilizavel — e
testavel — sem abrir porta nenhuma, e porque `admin_http` implica
`admin_enabled`, nunca o contrario.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Final

from mcp.server import MCPServer
from starlette.types import ASGIApp

from maskgw.admin import AdapterFactory, AdminConfigService, decode_document
from maskgw.admin.http import AdminHttpServer, AdminHttpSettings, build_admin_app
from maskgw.admin.http import resolve as resolve_admin_http_settings
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
        "_admin_http",
        "_close_lock",
        "_closed",
        "_closing",
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
        admin_http: AdminHttpServer | None = None,
    ) -> None:
        self._gateway = gateway
        self._config = config
        self._registry = registry
        self._mcp_server = mcp_server
        self._admin = admin
        self._config_store = config_store
        self._admin_http = admin_http
        self._lifecycle_lock = threading.Lock()
        # Curto: cobre so as transicoes de estado, nunca o `join` da thread
        # HTTP nem o fechamento das conexoes.
        self._close_lock = threading.Lock()
        self._running = False
        self._closed = False
        # O shutdown COMECOU. Distinto de `_closed`, que so passa a verdadeiro
        # quando a sequencia inteira concluiu. Uma vez verdadeiro nunca volta
        # atras: a aplicacao nao torna a ser utilizavel, e `run()` a recusa.
        self._closing = False

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
    def admin_http(self) -> AdminHttpServer | None:
        """Servidor HTTP administrativo, ou None sem a fronteira HTTP.

        Quando existe, ele JA esta escutando: `build_application` so retorna
        depois da confirmacao de bind (secao 9.2, passo 6).
        """
        return self._admin_http

    @property
    def revision(self) -> int:
        """Revision carregada, unica metadata emitida no startup (§9.2)."""
        return self._registry.current.revision

    @property
    def mcp_server(self) -> MCPServer:
        """Servidor do data plane, ja composto mas ainda nao iniciado."""
        return self._mcp_server

    def run(self) -> None:
        """Executa o data plane MCP em stdio e sempre faz shutdown ordenado.

        Recusa uma aplicacao cujo shutdown ja COMECOU, e nao apenas uma ja
        encerrada. Sao coisas diferentes: entre o inicio e o fim do `close()` o
        `AdminConfigService` ja recusa operacoes e o servidor HTTP ja esta
        parando. Disponibilizar o MCP sobre esse estado ofereceria queries
        sobre recursos em desmontagem.
        """
        with self._lifecycle_lock:
            if self._closed or self._closing:
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

        Recusar operacoes administrativas vem primeiro; parar e AGUARDAR a
        thread HTTP, depois; fechar os runtimes, so entao; liberar o lock de
        arquivo, por ultimo.

        As duas inversoes que esta ordem evita sao concretas: fechar os
        runtimes antes do `join` deixaria uma requisicao administrativa em voo
        tentando um swap sobre um registry ja desmontado; liberar o lock antes
        de fechar as conexoes deixaria um segundo processo entrar cedo demais.

        `_closing` marca que a sequencia COMECOU, e nunca volta atras: um
        shutdown iniciado nao se desfaz, e `run()` passa a recusar a aplicacao a
        partir dai. `_closed` so e marcado no fim. Entre os dois, `repr()`
        reporta `closing`, e nao `ready` — apresentar como pronta uma aplicacao
        cujo `AdminConfigService` ja recusa operacoes seria mentir para quem
        estivesse diagnosticando.

        `_close_lock` serializa chamadas concorrentes sem impedir repeticao: um
        segundo `close()` simultaneo espera e encontra `_closed`; um `close()`
        posterior a uma falha refaz a sequencia, e cada passo e idempotente. O
        passo do HTTP bloqueia ate a thread terminar, entao a ordem nao avanca
        com nada de pe.
        """
        with self._lifecycle_lock:
            if self._closed or self._running:
                return
            # Permanente. Um shutdown interrompido continua sendo um shutdown
            # em andamento, e a aplicacao nao volta a ser utilizavel.
            self._closing = True

        with self._close_lock:
            # Reconferido DEPOIS de adquirir o lock: quem esperou aqui pode ter
            # esperado justamente o fechamento que ja concluiu.
            if self._is_closed():
                return

            if self._admin is not None:
                self._admin.close()
            if self._admin_http is not None:
                # Bloqueia ate a thread HTTP acabar. So depois disso os
                # runtimes podem fechar e o lock pode sair (secao 9.2).
                self._admin_http.stop()
            self._registry.close_all()
            if self._config_store is not None:
                self._config_store.close()

            with self._lifecycle_lock:
                self._closed = True

    def _is_closed(self) -> bool:
        with self._lifecycle_lock:
            return self._closed

    def __enter__(self) -> Application:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        with self._lifecycle_lock:
            if self._closed:
                state = "closed"
            elif self._closing:
                # Nunca `ready` depois que o shutdown comecou.
                state = "closing"
            elif self._running:
                state = "running"
            else:
                state = "ready"
        return (
            f"Application(revision={self._registry.current.revision}, state={state!r}, "
            f"admin={self._admin is not None}, admin_http={self._admin_http is not None})"
        )


def resolve_admin_settings(secrets: SecretProvider | None = None) -> AdminHttpSettings | None:
    """Passo 1 da secao 9.2: le e valida enable, token, bind e porta.

    Vive no composition root, e nao no plano administrativo, porque e aqui que
    a decisao "este processo expoe uma Admin API" pertence — e porque a ordem
    do startup e responsabilidade deste modulo. A validacao em si continua em
    `admin/http/settings.py`.

    Devolve `None` quando a Admin API nao esta habilitada; nesse caso o
    processo e exatamente o de antes da Etapa 7. Com ela habilitada e algo
    invalido, levanta `ConfigError` **antes** de qualquer arquivo ser aberto.
    """
    return resolve_admin_http_settings(secrets)


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


def build_application(  # noqa: PLR0913 - parametros de composicao, keyword-only
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    conninfo: str | None = None,
    secrets: SecretProvider | None = None,
    audit: AuditLog | None = None,
    admin_enabled: bool = False,
    admin_http: AdminHttpSettings | None = None,
) -> Application:
    """Constroi os planos inteiros ou levanta sem deixar recurso de pe.

    Com `admin_enabled=False` e `admin_http=None` — os defaults — o processo e
    exatamente o de hoje: nenhuma porta, nenhuma thread, nenhum lock de arquivo,
    nenhuma secao critica administrativa e nenhum caminho de escrita.

    `admin_http` implica a secao critica: nao existe fronteira HTTP sobre uma
    configuracao que o processo nao esteja segurando com o lock exclusivo.
    """
    # A fronteira HTTP so existe sobre a secao critica.
    admin_enabled = admin_enabled or admin_http is not None

    store: ConfigFileStore | None = None
    adapter: PostgresAdapter | None = None
    registry: RuntimeRegistry | None = None
    http_server: AdminHttpServer | None = None

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

        # Passos 5 e 6: a thread HTTP sobe e o bind e CONFIRMADO antes de o
        # MCP existir. Porta ocupada, bind recusado ou timeout levantam aqui,
        # e o `except` abaixo desmonta tudo — o MCP nunca fica disponivel.
        #
        # A referencia e ADOTADA antes de `start()`, e nao vinda do retorno
        # dele. Construir e iniciar numa expressao so perderia o servidor
        # exatamente no caso que importa: se `start()` criasse a thread e
        # falhasse depois, o `except` abaixo veria `http_server is None`,
        # pularia o `stop()` e fecharia registry e store. A propriedade de um
        # recurso nao pode depender de a construcao dele ter dado certo.
        if admin_http is not None and admin is not None:
            http_server = _build_admin_http(admin, admin_http, secrets=secrets)
            http_server.start()

        # Passo 7: o MCP e construido por ultimo e ainda nao esta disponivel.
        # Somente `Application.run()` abre o stdio.
        mcp_server = build_mcp_server(gateway)
        return Application(
            gateway=gateway,
            config=config,
            registry=registry,
            mcp_server=mcp_server,
            admin=admin,
            config_store=store,
            admin_http=http_server,
        )
    except BaseException:
        # Falha parcial: desmontar na mesma ordem do shutdown. A thread HTTP
        # para e recebe `join` ANTES de os runtimes fecharem; o lock de arquivo
        # sai por ultimo. O adapter e fechado diretamente apenas se o registry
        # ainda nao existia.
        #
        # `http_server` esta preenchido mesmo quando foi o proprio `start()` que
        # falhou — e por isso que a adocao vem antes dele. `stop()` bloqueia ate
        # a thread terminar, entao nenhum runtime e fechado com ela viva, e
        # `stop()` sobre um servidor que nunca iniciou nao faz nada.
        if http_server is not None:
            http_server.stop()
        if registry is not None:
            registry.close_all()
        elif adapter is not None:
            adapter.close()
        if store is not None:
            store.close()
        raise


def _build_admin_http(
    admin: AdminConfigService,
    settings: AdminHttpSettings,
    *,
    secrets: SecretProvider | None,
) -> AdminHttpServer:
    """Monta a fronteira HTTP **sem** inicia-la.

    Construir e iniciar sao passos separados de proposito: quem chama adota a
    referencia antes de `start()`, e por isso nunca fica sem ela numa falha
    parcial de startup.

    A aplicacao e montada por uma fabrica que recebe a porta EFETIVAMENTE
    vinculada, e nao a desejada: a allowlist de `Host` e derivada dela, e com
    porta escolhida pelo sistema as duas diferem.

    O nome da variavel do DSN e passado daqui porque ele pertence a este
    modulo: `admin/` nao importa `bootstrap/`, e nao deve adivinhar como o
    plano de dados nomeia seu segredo. O VALOR do DSN continua sem atravessar —
    o que a Admin API publica e `configured`/`missing`, nunca o conteudo.
    """

    def factory(bound_port: int) -> ASGIApp:
        return build_admin_app(
            admin,
            token=settings.token,
            port=bound_port,
            secrets=secrets,
            database_dsn_env=DSN_ENV,
        )

    # Sem `start()`: quem chama adota a referencia e so entao inicia.
    return AdminHttpServer(
        app_factory=factory,
        host=settings.host,
        port=settings.port,
    )


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
