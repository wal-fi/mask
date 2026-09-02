"""Fase 7, Etapa 7: startup e shutdown com a fronteira HTTP (secoes 9.2, 12.10).

Duas ordens sao verificadas literalmente, e nenhuma delas e detalhe de
implementacao:

**Startup.** O bind e CONFIRMADO antes de o MCP existir. Se a porta estiver
ocupada, o processo nao sobe — em vez de atender queries por um tempo e entao
morrer, com o administrador convencido de que a Admin API esta no ar.

**Shutdown.** A thread HTTP recebe `join` ANTES de os runtimes fecharem, e o
lock de arquivo sai por ultimo. A primeira ordem impede uma requisicao
administrativa em voo de encontrar um registry desmontado; a segunda impede um
segundo processo de entrar enquanto uma conexao ainda esta sendo fechada.
"""

from __future__ import annotations

import contextlib
import socket
import threading
from pathlib import Path
from typing import Any, ClassVar, cast

import anyio
import pytest
from mcp.server import MCPServer

import maskgw.bootstrap.application as application_module
import maskgw.bootstrap.main as main_module
from maskgw.admin.http import AdminHttpServer, AdminHttpUnavailableError, build_settings
from maskgw.admin.http.server import DEFAULT_STARTUP_TIMEOUT_SECONDS
from maskgw.config import ConfigFileStore
from maskgw.errors import ConfigError
from maskgw.secretsource import MappingSecretProvider
from tests.admin_http_support import TOKEN, free_port, request, thread_snapshot

SENSITIVE_DSN = "postgresql://user:super-secret@database.example.invalid/private"

CONFIG = """
revision: 0
database:
  statement_timeout_ms: 2000
  max_rows: 10
"""


class FakeAdapter:
    """Adapter sem banco, com a linha do tempo compartilhada do lifecycle."""

    instances: ClassVar[list[FakeAdapter]] = []
    events: ClassVar[list[str]] = []

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.connect_calls = 0
        self.close_calls = 0
        type(self).instances.append(self)

    def connect(self) -> None:
        self.connect_calls += 1
        type(self).events.append("runtime:connected")

    def close(self) -> None:
        self.close_calls += 1
        type(self).events.append("runtime:closed")


class FakeMcpServer:
    def __init__(self) -> None:
        self.transports: list[str] = []

    def run(self, transport: str = "stdio", **_kwargs: Any) -> None:
        self.transports.append(transport)
        FakeAdapter.events.append("mcp:started")
        FakeAdapter.events.append("mcp:stopped")


class ObservableStore(ConfigFileStore):
    def close(self) -> None:
        already = self.closed
        super().close()
        if not already:
            FakeAdapter.events.append("lock:released")


class ObservableHttpServer(AdminHttpServer):
    def start(self) -> None:
        super().start()
        FakeAdapter.events.append("http:listening")

    def stop(self) -> None:
        running = self.running
        super().stop()
        if running:
            FakeAdapter.events.append("http:joined")


class FailingStartHttpServer(AdminHttpServer):
    """Sobe a thread e SO ENTAO falha, como um timeout de confirmacao faria.

    Serve a uma pergunta so: o composition root ficou com a referencia? Se
    ficou, ele chama `stop()`; se nao, fecha registry e lock com a thread viva.
    """

    instances: ClassVar[list[FailingStartHttpServer]] = []

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.stop_calls = 0
        type(self).instances.append(self)

    @classmethod
    def reset(cls) -> None:
        cls.instances = []

    def start(self) -> None:
        super().start()
        # A thread existe e o socket ja escuta; so entao a falha.
        msg = "falha apos criar a thread"
        raise RuntimeError(msg)

    def stop(self) -> None:
        self.stop_calls += 1
        ativo = self.running
        super().stop()
        if ativo:
            FakeAdapter.events.append("http:stopped")


class ObservingStateHttpServer(ObservableHttpServer):
    """Inspeciona a aplicacao de DENTRO do `stop()`.

    E a unica janela em que o shutdown ja comecou e ainda nao terminou — o
    `AdminConfigService` ja recusa operacoes, a thread HTTP ainda esta parando,
    e nenhum runtime foi fechado. Observar de fora nao alcanca esse instante.
    """

    application: ClassVar[Any] = None
    observed: ClassVar[list[str]] = []
    run_refused: ClassVar[bool | None] = None

    @classmethod
    def reset(cls) -> None:
        cls.application = None
        cls.observed = []
        cls.run_refused = None

    def stop(self) -> None:
        app = type(self).application
        if app is not None:
            rendered = repr(app)
            type(self).observed.append(rendered.split("state='", 1)[1].split("'", 1)[0])
            type(self).run_refused = _run_is_refused(app)
        super().stop()


class SlowRouteHttpServer(ObservableHttpServer):
    """Serve uma aplicacao que segura a requisicao ate ser liberada.

    O limite gracioso vai BEM alto de proposito. O teste que usa este duble
    precisa provar que o `join` e integral — que ele espera enquanto for
    preciso —, e o corte do uvicorn no default de 10 s encerraria a requisicao
    antes de a espera passar dos dois timeouts de 10 s que existiam. Que o corte
    funciona e assunto de outro teste, no nivel do servidor.
    """

    entrou: ClassVar[threading.Event] = threading.Event()
    liberar: ClassVar[threading.Event] = threading.Event()

    @classmethod
    def configure(cls, entrou: threading.Event, liberar: threading.Event) -> None:
        cls.entrou = entrou
        cls.liberar = liberar

    def __init__(self, **kwargs: Any) -> None:
        kwargs["app_factory"] = _blocking_app(type(self).entrou, type(self).liberar)
        kwargs["graceful_timeout"] = 300
        super().__init__(**kwargs)


@pytest.fixture(autouse=True)
def reset_fakes() -> None:
    FakeAdapter.instances = []
    FakeAdapter.events = []


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "masking.yaml"
    path.write_text(CONFIG, encoding="utf-8")
    return path


def settings(port: int = 0) -> Any:
    return build_settings(token=TOKEN, host="127.0.0.1", port=port or free_port())


def compose(
    monkeypatch: pytest.MonkeyPatch,
    config_file: Path,
    *,
    observable: bool = False,
    http_server: type[AdminHttpServer] | None = None,
    **kwargs: Any,
) -> Any:
    monkeypatch.setattr(application_module, "PostgresAdapter", FakeAdapter)
    monkeypatch.setattr(
        application_module,
        "build_mcp_server",
        lambda _gateway: cast(MCPServer, FakeMcpServer()),
    )
    if observable:
        monkeypatch.setattr(application_module, "ConfigFileStore", ObservableStore)
        monkeypatch.setattr(application_module, "AdminHttpServer", ObservableHttpServer)
    if http_server is not None:
        monkeypatch.setattr(application_module, "AdminHttpServer", http_server)
    return application_module.build_application(
        config_path=config_file,
        conninfo=SENSITIVE_DSN,
        **kwargs,
    )


# --------------------------------------------------------------------------
# O servidor isolado
# --------------------------------------------------------------------------


class TestBindReal:
    def test_start_vincula_de_verdade_e_expoe_a_porta(self) -> None:
        server = AdminHttpServer(app_factory=_null_app, host="127.0.0.1", port=0)
        server.start()
        try:
            assert server.port > 0
            assert server.running
            # A porta esta REALMENTE escutando quando `start` retorna.
            with socket.create_connection(("127.0.0.1", server.port), timeout=5):
                pass
        finally:
            server.stop()

    def test_porta_explicita_e_respeitada(self) -> None:
        port = free_port()
        server = AdminHttpServer(app_factory=_null_app, host="127.0.0.1", port=port)
        server.start()
        try:
            assert server.port == port
        finally:
            server.stop()

    def test_bind_em_ipv6_loopback(self) -> None:
        server = AdminHttpServer(app_factory=_null_app, host="::1", port=0)
        server.start()
        try:
            assert server.port > 0
        finally:
            server.stop()

    def test_porta_ocupada_falha_e_nao_deixa_thread(self) -> None:
        """O `bind` acontece na thread chamadora: nao ha corrida."""
        before = thread_snapshot()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as squatter:
            squatter.bind(("127.0.0.1", 0))
            squatter.listen(1)
            port = squatter.getsockname()[1]

            server = AdminHttpServer(app_factory=_null_app, host="127.0.0.1", port=port)
            with pytest.raises(AdminHttpUnavailableError):
                server.start()

        assert thread_snapshot() == before
        assert not server.running

    def test_o_erro_de_bind_nao_carrega_host_porta_nem_errno(self) -> None:
        """O `OSError` original cita host, porta e `errno`; nada disso sai."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as squatter:
            squatter.bind(("127.0.0.1", 0))
            squatter.listen(1)
            port = squatter.getsockname()[1]

            server = AdminHttpServer(app_factory=_null_app, host="127.0.0.1", port=port)
            with pytest.raises(AdminHttpUnavailableError) as raised:
                server.start()

        rendered = f"{raised.value!s} {raised.value!r}"
        assert str(port) not in rendered
        assert "127.0.0.1" not in rendered
        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None

    def test_timeout_de_confirmacao_desmonta_tudo(self) -> None:
        """Sem confirmacao de escuta, o processo nao sobe (secao 9.2, passo 6)."""
        before = thread_snapshot()

        def stalling(_port: int) -> Any:
            # Uma app que nunca sera exercitada; o que trava e o timeout zero.
            return _null_app(_port)

        server = AdminHttpServer(
            app_factory=stalling,
            host="127.0.0.1",
            port=0,
            startup_timeout=0.0,
        )
        with pytest.raises(AdminHttpUnavailableError):
            server.start()

        assert thread_snapshot() == before

    def test_falha_da_fabrica_de_app_nao_deixa_socket_nem_thread(self) -> None:
        before = thread_snapshot()

        def failing(_port: int) -> Any:
            raise RuntimeError(SENSITIVE_DSN)

        server = AdminHttpServer(app_factory=failing, host="127.0.0.1", port=0)
        with pytest.raises(RuntimeError):
            server.start()

        assert thread_snapshot() == before
        # A porta foi liberada: outro servidor consegue o mesmo endereco.
        again = AdminHttpServer(app_factory=_null_app, host="127.0.0.1", port=0)
        again.start()
        again.stop()

    def test_o_default_de_timeout_e_generoso_mas_finito(self) -> None:
        assert 0 < DEFAULT_STARTUP_TIMEOUT_SECONDS <= 60


class TestShutdownDoServidor:
    def test_stop_faz_join_e_nao_deixa_thread_viva(self) -> None:
        before = thread_snapshot()
        server = AdminHttpServer(app_factory=_null_app, host="127.0.0.1", port=0)
        server.start()
        assert thread_snapshot() != before

        server.stop()
        assert thread_snapshot() == before

    def test_a_thread_http_nao_e_daemon(self) -> None:
        """Uma thread daemon e morta no meio do que estiver fazendo."""
        server = AdminHttpServer(app_factory=_null_app, host="127.0.0.1", port=0)
        server.start()
        try:
            criadas = [t for t in threading.enumerate() if t.name == "maskgw-admin-http"]
            assert criadas
            assert all(not t.daemon for t in criadas)
        finally:
            server.stop()

    def test_stop_e_idempotente(self) -> None:
        server = AdminHttpServer(app_factory=_null_app, host="127.0.0.1", port=0)
        server.start()
        server.stop()
        server.stop()
        server.stop()
        assert not server.running

    def test_stop_sem_start_nao_levanta(self) -> None:
        AdminHttpServer(app_factory=_null_app, host="127.0.0.1", port=0).stop()

    def test_start_duas_vezes_e_recusado(self) -> None:
        server = AdminHttpServer(app_factory=_null_app, host="127.0.0.1", port=0)
        server.start()
        try:
            with pytest.raises(RuntimeError):
                server.start()
        finally:
            server.stop()

    def test_a_porta_e_liberada_depois_do_stop(self) -> None:
        port = free_port()
        first = AdminHttpServer(app_factory=_null_app, host="127.0.0.1", port=port)
        first.start()
        first.stop()

        second = AdminHttpServer(app_factory=_null_app, host="127.0.0.1", port=port)
        second.start()
        second.stop()

    def test_repr_nao_expoe_token_nem_app(self) -> None:
        server = AdminHttpServer(app_factory=_null_app, host="127.0.0.1", port=0)
        rendered = repr(server)

        assert TOKEN not in rendered
        assert "app_factory" not in rendered


class TestShutdownNaoAbandonaAThread:
    """`stop()` bloqueia ate a thread terminar. Nao ha retorno parcial.

    `Thread.join(timeout=...)` devolve `None` tanto quando a thread terminou
    quanto quando o tempo acabou. Com timeout, `stop()` so tinha dois desfechos
    possiveis e ambos ruins: abandonar a thread — o que a secao 9.2 proibe — ou
    devolver o controle com o shutdown pela metade, obrigando cada chamador a
    saber o que fazer com esse meio-estado. Sem timeout nao existe o meio: ou
    ele nao voltou, ou acabou.

    A aplicacao ASGI abaixo segura uma requisicao ate um `Event` ser liberado.
    O uvicorn nao encerra enquanto ela estiver em voo, entao a thread continua
    viva depois do `should_exit` — que e exatamente o cenario.

    Por isso `stop()` roda numa thread auxiliar: se ele bloqueia, um teste que o
    chamasse direto travaria em vez de falhar.
    """

    def test_stop_nao_retorna_enquanto_a_requisicao_esta_presa(self) -> None:
        entrou = threading.Event()
        liberar = threading.Event()
        server = AdminHttpServer(
            app_factory=_blocking_app(entrou, liberar),
            host="127.0.0.1",
            port=0,
            # Limite gracioso ALTO de proposito: o corte do uvicorn nao pode ser
            # o que faz `stop()` voltar durante a janela negativa abaixo. Assim,
            # se ele voltar em 3 s, foi porque abandonou a thread — o bug —, e
            # nao porque o servidor cancelou a requisicao no tempo.
            graceful_timeout=300,
        )
        server.start()
        chamador = _issue_stuck_request(server.port)
        try:
            assert entrou.wait(15), "a requisicao nunca chegou ao handler"

            parada = _Stopper(server)
            parada.start()

            # Com a requisicao presa, `stop()` NAO pode terminar. Antes da
            # correcao ele retornava aqui, deixando `maskgw-admin-http` viva.
            assert not parada.wait(3.0), "stop() retornou com a requisicao presa"
            assert _http_threads(), "a thread HTTP deveria continuar viva"

            liberar.set()

            # Solta a requisicao, `stop()` conclui sozinho — sem nova chamada.
            assert parada.wait(30.0), "stop() nao terminou apos a liberacao"
            assert parada.error is None
        finally:
            liberar.set()
            chamador.join(timeout=20)
            server.stop()

        assert _http_threads() == []
        assert server.running is False

    def test_as_referencias_so_sao_soltas_depois_do_fim_da_thread(self) -> None:
        """Solta-las antes tornaria o abandono invisivel."""
        entrou = threading.Event()
        liberar = threading.Event()
        server = AdminHttpServer(
            app_factory=_blocking_app(entrou, liberar),
            host="127.0.0.1",
            port=0,
            # Ver a nota no teste acima: o corte gracioso nao pode competir com
            # a janela negativa.
            graceful_timeout=300,
        )
        server.start()
        chamador = _issue_stuck_request(server.port)
        try:
            assert entrou.wait(15)
            parada = _Stopper(server)
            parada.start()
            assert not parada.wait(3.0)

            # Ainda em `stop()`: thread, servidor e socket continuam de pe.
            assert all(item is not None for item in _internals(server))

            liberar.set()
            assert parada.wait(30.0)
        finally:
            liberar.set()
            chamador.join(timeout=20)
            server.stop()

        assert _internals(server) == (None, None, None)

    def test_uma_requisicao_muito_longa_termina_pelo_limite_do_uvicorn(self) -> None:
        """O limite fica no trabalho, nao na espera.

        A requisicao aqui nunca e liberada. Mesmo assim o shutdown TERMINA,
        porque o uvicorn cancela o que restou depois de
        `timeout_graceful_shutdown` — e a thread chega ao fim. E o oposto de
        abandonar: ninguem desiste de esperar, o servidor e que para de aguardar
        o cliente.
        """
        entrou = threading.Event()
        nunca = threading.Event()
        server = AdminHttpServer(
            app_factory=_blocking_app(entrou, nunca),
            host="127.0.0.1",
            port=0,
            graceful_timeout=1,
        )
        server.start()
        chamador = _issue_stuck_request(server.port)
        try:
            assert entrou.wait(15)
            parada = _Stopper(server)
            parada.start()

            assert parada.wait(45.0), "o shutdown nao terminou pelo limite gracioso"
            assert parada.error is None
        finally:
            nunca.set()
            chamador.join(timeout=20)
            server.stop()

        assert _http_threads() == []
        assert _internals(server) == (None, None, None)

    def test_o_caminho_normal_continua_imediato(self) -> None:
        server = AdminHttpServer(app_factory=_null_app, host="127.0.0.1", port=0)
        server.start()
        server.stop()

        assert not server.running
        assert _http_threads() == []

    def test_start_que_falha_apos_criar_a_thread_nao_deixa_nada(self) -> None:
        """Timeout de confirmacao: o teardown tambem espera a thread ate o fim."""
        before = thread_snapshot()
        server = AdminHttpServer(
            app_factory=_null_app,
            host="127.0.0.1",
            port=0,
            startup_timeout=0.0,
        )
        with pytest.raises(AdminHttpUnavailableError):
            server.start()

        assert thread_snapshot() == before
        assert _internals(server) == (None, None, None)
        assert not server.running


class _Stopper:
    """Executa `stop()` numa thread auxiliar e informa se ele terminou.

    Chamar `stop()` direto de um teste nao serve: ele bloqueia de proposito, e o
    teste travaria em vez de reprovar.
    """

    def __init__(self, server: AdminHttpServer) -> None:
        self._server = server
        self._done = threading.Event()
        self.error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, name="stopper", daemon=True)

    def _run(self) -> None:
        try:
            self._server.stop()
        except BaseException as exc:  # pragma: no cover - stop() nao deve levantar
            self.error = exc
        finally:
            self._done.set()

    def start(self) -> None:
        self._thread.start()

    def wait(self, timeout: float) -> bool:
        """True se `stop()` JA terminou; False se ainda esta bloqueado."""
        return self._done.wait(timeout)


def _run_is_refused(app: Any) -> bool:
    """`app.run()` e recusado rapidamente? Sondado de OUTRA thread.

    Chamar `run()` direto de dentro do `stop()` nao serve: um `run()` aceito
    terminaria em `close()`, que espera o mesmo lock que a thread atual ja
    segura — e o teste travaria em vez de reprovar. Numa thread separada, um
    `run()` indevidamente aceito simplesmente nao devolve `RuntimeError` a
    tempo, e a assercao falha como deve.
    """
    resultado: list[BaseException | None] = []

    def probe() -> None:
        try:
            app.run()
        except BaseException as exc:
            resultado.append(exc)
        else:  # pragma: no cover - seria o bug
            resultado.append(None)

    thread = threading.Thread(target=probe, name="probe-run", daemon=True)
    thread.start()
    thread.join(timeout=5.0)
    return bool(resultado) and isinstance(resultado[0], RuntimeError)


def _internals(server: AdminHttpServer) -> tuple[object | None, object | None, object | None]:
    """Thread, servidor e socket guardados. Preserva-los e o que torna o
    cleanup repetivel depois de um timeout."""
    return (server._thread, server._server, server._socket)


def _http_threads() -> list[threading.Thread]:
    return [thread for thread in threading.enumerate() if thread.name == "maskgw-admin-http"]


def _issue_stuck_request(port: int) -> threading.Thread:
    """Dispara, de outra thread, a requisicao que vai ficar presa."""

    def call() -> None:
        # A conexao pode cair quando o servidor finalmente encerra; para este
        # teste o que importa e a requisicao ter CHEGADO ao handler.
        with contextlib.suppress(OSError):
            request(port, "GET", "/qualquer", timeout=60.0)

    thread = threading.Thread(target=call, name="requisicao-presa", daemon=True)
    thread.start()
    return thread


def _blocking_app(entrou: threading.Event, liberar: threading.Event) -> Any:
    """ASGI que segura a requisicao ate `liberar` ser sinalizado.

    A espera vai para um worker via `anyio.to_thread`, e nao bloqueia o loop:
    assim o uvicorn PROCESSA o `should_exit` e ainda assim nao termina, porque
    ha uma requisicao em voo. E o caso dificil, nao o facil.
    """

    def factory(_port: int) -> Any:
        async def app(scope: Any, receive: Any, send: Any) -> None:
            if scope["type"] != "http":
                return
            entrou.set()
            await anyio.to_thread.run_sync(liberar.wait)
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        return app

    return factory


def _null_app(_port: int) -> Any:
    async def app(scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            return
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    return app


# --------------------------------------------------------------------------
# O composition root
# --------------------------------------------------------------------------


class TestBootstrapComAdminHttp:
    def test_a_porta_ja_esta_escutando_quando_build_retorna(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        """Passo 6 antes do passo 7: o MCP so existe depois da confirmacao."""
        app = compose(monkeypatch, config_file, admin_http=settings())
        try:
            server = app.admin_http
            assert server is not None
            assert server.running
            assert request(server.port, "GET", "/admin/v1/status").status == 200
            # O MCP foi construido, mas ainda nao esta disponivel.
            assert cast(FakeMcpServer, app.mcp_server).transports == []
        finally:
            app.close()

    def test_admin_http_implica_a_secao_critica(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        """Nao ha fronteira HTTP sobre configuracao que ninguem esta segurando."""
        app = compose(monkeypatch, config_file, admin_http=settings())
        try:
            assert app.admin is not None
            assert app.config_store is not None
            with pytest.raises(Exception, match=""):
                ConfigFileStore.open(config_file)
        finally:
            app.close()

    def test_porta_ocupada_impede_o_startup_e_o_MCP_nunca_sobe(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        before = thread_snapshot()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as squatter:
            squatter.bind(("127.0.0.1", 0))
            squatter.listen(1)
            port = squatter.getsockname()[1]

            with pytest.raises(AdminHttpUnavailableError):
                compose(monkeypatch, config_file, admin_http=settings(port))

        # Nada de pe: conexao fechada, lock liberado, nenhuma thread.
        assert FakeAdapter.instances[0].close_calls == 1
        assert thread_snapshot() == before
        with ConfigFileStore.open(config_file) as store:
            assert not store.closed

    def test_falha_de_bind_libera_o_lock_de_arquivo(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as squatter:
            squatter.bind(("127.0.0.1", 0))
            squatter.listen(1)
            with pytest.raises(AdminHttpUnavailableError):
                compose(
                    monkeypatch,
                    config_file,
                    admin_http=settings(squatter.getsockname()[1]),
                )

        # O lock saiu: outro processo administrativo consegue abrir.
        with ConfigFileStore.open(config_file) as store:
            assert not store.closed

    def test_a_ordem_do_shutdown_e_http_runtimes_lock(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        """Secao 9.2: `join` da thread HTTP ANTES de fechar os runtimes."""
        app = compose(monkeypatch, config_file, observable=True, admin_http=settings())
        app.run()
        app.close()

        assert FakeAdapter.events == [
            "runtime:connected",
            "http:listening",
            "mcp:started",
            "mcp:stopped",
            "http:joined",
            "runtime:closed",
            "lock:released",
        ]

    def test_o_http_sobe_DEPOIS_do_runtime_conectado(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        """Passo 4 antes do passo 5: nao se abre porta sobre runtime nao verificado."""
        app = compose(monkeypatch, config_file, observable=True, admin_http=settings())
        try:
            assert FakeAdapter.events.index("runtime:connected") < FakeAdapter.events.index(
                "http:listening"
            )
        finally:
            app.close()

    def test_nenhuma_thread_viva_ao_final(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        before = thread_snapshot()
        app = compose(monkeypatch, config_file, admin_http=settings())
        assert thread_snapshot() != before
        app.run()
        assert thread_snapshot() == before

    def test_close_idempotente_com_http(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        app = compose(monkeypatch, config_file, admin_http=settings())
        app.close()
        app.close()
        app.close()

        assert FakeAdapter.instances[0].close_calls == 1
        assert FakeAdapter.events.count("lock:released" if False else "runtime:closed") == 1

    def test_start_que_falha_apos_criar_a_thread_nao_fecha_registry_nem_lock(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        """A referencia do servidor e adotada ANTES de `start()`.

        Com `http_server = _start_admin_http(...)`, a atribuicao so acontecia
        se `start()` retornasse. Um `start()` que criasse a thread e falhasse
        depois deixava `http_server is None`, o `except` pulava o `stop()` e
        fechava registry e store com a thread ainda viva. A propriedade de um
        recurso nao pode depender de a construcao dele ter dado certo.
        """
        before = thread_snapshot()
        FailingStartHttpServer.reset()

        with pytest.raises(RuntimeError, match="falha apos criar a thread"):
            compose(
                monkeypatch,
                config_file,
                observable=True,
                http_server=FailingStartHttpServer,
                admin_http=settings(),
            )

        # A referencia existiu e o `stop()` foi chamado sobre ela.
        assert FailingStartHttpServer.instances, "o servidor nem chegou a ser construido"
        assert FailingStartHttpServer.instances[0].stop_calls == 1

        # O `stop()` veio ANTES do fechamento do runtime e da liberacao do lock.
        assert FakeAdapter.events == [
            "runtime:connected",
            "http:stopped",
            "runtime:closed",
            "lock:released",
        ]
        # E nada ficou de pe: nem thread, nem lock de arquivo.
        assert thread_snapshot() == before
        with ConfigFileStore.open(config_file) as store:
            assert not store.closed

    def test_run_e_recusado_no_meio_do_shutdown_e_depois_dele(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        """O MCP nao sobe sobre uma aplicacao em desmontagem.

        A tentativa acontece DENTRO do `stop()`: o `AdminConfigService` ja
        recusa operacoes e o servidor HTTP ja esta parando. Um `run()` aceito
        ali ofereceria queries sobre recursos que estao sendo fechados.
        """
        ObservingStateHttpServer.reset()
        app = compose(
            monkeypatch,
            config_file,
            observable=True,
            http_server=ObservingStateHttpServer,
            admin_http=settings(),
        )
        ObservingStateHttpServer.application = app
        app.close()

        assert ObservingStateHttpServer.run_refused is True
        # E depois de concluido, tambem.
        with pytest.raises(RuntimeError, match="ja encerrada"):
            app.run()
        assert cast(FakeMcpServer, app.mcp_server).transports == []

    def test_repr_nunca_diz_ready_depois_do_inicio_do_shutdown(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        """`ready` durante a desmontagem mentiria para quem diagnostica."""
        ObservingStateHttpServer.reset()
        app = compose(
            monkeypatch,
            config_file,
            observable=True,
            http_server=ObservingStateHttpServer,
            admin_http=settings(),
        )
        ObservingStateHttpServer.application = app

        assert "state='ready'" in repr(app)
        app.close()

        # Capturado DENTRO do `stop()`, com o shutdown ja em andamento.
        assert ObservingStateHttpServer.observed == ["closing"]
        assert "state='closed'" in repr(app)
        assert "state='ready'" not in repr(app)

    def test_requisicao_longa_atrasa_o_shutdown_mas_tudo_fecha_na_ordem(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        """Uma requisicao presa segura o shutdown ate ser liberada.

        Ela dura mais que qualquer timeout que existisse antes, e ainda assim o
        desfecho e completo: HTTP, runtime e lock, nessa ordem, sem thread viva
        e sem ninguem precisar retomar o cleanup depois.
        """
        before = thread_snapshot()
        entrou = threading.Event()
        liberar = threading.Event()
        SlowRouteHttpServer.configure(entrou, liberar)

        app = compose(
            monkeypatch,
            config_file,
            observable=True,
            http_server=SlowRouteHttpServer,
            admin_http=settings(),
        )
        server = app.admin_http
        assert server is not None
        chamador = _issue_stuck_request(server.port)
        assert entrou.wait(15)

        # `graceful_timeout=300` no duble: enquanto a requisicao nao e liberada,
        # `close()` fica preso no `join` do `stop()`, e nada abaixo dele roda.
        fechamento = threading.Thread(target=app.close, name="fechador", daemon=True)
        fechamento.start()
        try:
            # 25 s: bem mais que os dois timeouts de 10 s que existiam antes. A
            # PROVA e o invariante de ordem — `runtime:closed` e `lock:released`
            # nao podem aparecer enquanto a requisicao esta presa, ponto que
            # independe de relogio. `is_alive` e so um sinal de apoio: uma
            # suspensao da maquina poderia fazer os 25 s passarem sem trabalho,
            # entao ele nao carrega a assercao.
            fechamento.join(timeout=25.0)
            assert "runtime:closed" not in FakeAdapter.events
            assert "lock:released" not in FakeAdapter.events

            liberar.set()
            fechamento.join(timeout=60.0)
            assert not fechamento.is_alive(), "o shutdown nao concluiu apos a liberacao"
        finally:
            liberar.set()
            chamador.join(timeout=30)
            fechamento.join(timeout=60)

        assert FakeAdapter.events == [
            "runtime:connected",
            "http:listening",
            "http:joined",
            "runtime:closed",
            "lock:released",
        ]
        assert thread_snapshot() == before
        assert [t for t in threading.enumerate() if t.name == "maskgw-admin-http"] == []
        with ConfigFileStore.open(config_file) as store:
            assert not store.closed

    def test_repr_reporta_a_fronteira_sem_vazar(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        app = compose(monkeypatch, config_file, admin_http=settings())
        try:
            rendered = repr(app)
            assert "admin_http=True" in rendered
            assert TOKEN not in rendered
            assert SENSITIVE_DSN not in rendered
        finally:
            app.close()


class TestAdminDesabilitado:
    def test_sem_admin_http_nao_ha_porta_nem_thread(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        """Comportamento identico ao de antes da Etapa 7."""
        before = thread_snapshot()
        app = compose(monkeypatch, config_file)
        try:
            assert app.admin_http is None
            assert app.admin is None
            assert app.config_store is None
            assert thread_snapshot() == before
            assert not (config_file.parent / "masking.yaml.lock").exists()
        finally:
            app.close()
        assert thread_snapshot() == before

    def test_admin_enabled_sozinho_nao_abre_porta(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config_file: Path,
    ) -> None:
        """A secao critica da Etapa 6 continua utilizavel sem fronteira HTTP."""
        before = thread_snapshot()
        app = compose(monkeypatch, config_file, admin_enabled=True)
        try:
            assert app.admin is not None
            assert app.admin_http is None
            assert thread_snapshot() == before
        finally:
            app.close()


# --------------------------------------------------------------------------
# A fronteira de processo
# --------------------------------------------------------------------------


class TestProcessBoundary:
    def test_sem_a_variavel_o_processo_e_o_de_hoje(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("MASKGW_ADMIN_ENABLED", raising=False)
        assert application_module.resolve_admin_settings() is None

    def test_a_variavel_e_lida_do_ambiente(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MASKGW_ADMIN_ENABLED", "1")
        monkeypatch.setenv("MASKGW_ADMIN_TOKEN", TOKEN)
        monkeypatch.setenv("MASKGW_ADMIN_PORT", "9123")

        resolved = application_module.resolve_admin_settings()
        assert resolved is not None
        assert resolved.port == 9123

    def test_token_curto_impede_o_startup_com_mensagem_fixa(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("MASKGW_ADMIN_ENABLED", "1")
        monkeypatch.setenv("MASKGW_ADMIN_TOKEN", "curto")

        assert main_module.main() == 1
        captured = capsys.readouterr()

        assert captured.out == ""
        assert captured.err == main_module.STARTUP_FAILURE
        assert "curto" not in captured.err

    def test_bind_externo_impede_o_startup(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("MASKGW_ADMIN_ENABLED", "1")
        monkeypatch.setenv("MASKGW_ADMIN_TOKEN", TOKEN)
        monkeypatch.setenv("MASKGW_ADMIN_BIND", "0.0.0.0")

        assert main_module.main() == 1
        assert capsys.readouterr().err == main_module.STARTUP_FAILURE

    def test_o_startup_anuncia_host_e_porta_em_stderr_sem_o_token(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        class StubServer:
            host = "127.0.0.1"
            port = 8765

        class StubApplication:
            revision = 4
            admin_http = StubServer()

            def run(self) -> None:
                return None

            def close(self) -> None:
                return None

        monkeypatch.setattr(main_module, "resolve_admin_settings", lambda: None)
        monkeypatch.setattr(main_module, "build_application", lambda **_k: StubApplication())

        assert main_module.main() == 0
        captured = capsys.readouterr()

        assert captured.out == ""
        assert captured.err == (
            f"{main_module.REVISION_LOADED_PREFIX}4\n{main_module.ADMIN_LISTENING_PREFIX}127.0.0.1:8765\n"
        )
        assert TOKEN not in captured.err

    def test_sem_admin_o_stderr_nao_menciona_porta(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        class StubApplication:
            revision = 4
            admin_http = None

            def run(self) -> None:
                return None

            def close(self) -> None:
                return None

        monkeypatch.setattr(main_module, "resolve_admin_settings", lambda: None)
        monkeypatch.setattr(main_module, "build_application", lambda **_k: StubApplication())

        assert main_module.main() == 0
        captured = capsys.readouterr()

        assert captured.out == ""
        assert captured.err == f"{main_module.REVISION_LOADED_PREFIX}4\n"

    def test_resolucao_invalida_nunca_chega_a_construir(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Passo 1 antes do passo 2: nenhum arquivo e aberto."""
        chamadas: list[object] = []

        def spy(**kwargs: object) -> object:
            chamadas.append(kwargs)
            raise AssertionError("build_application nao deveria ser chamado")

        monkeypatch.setattr(main_module, "build_application", spy)

        def failing() -> None:
            raise ConfigError("token curto")

        monkeypatch.setattr(main_module, "resolve_admin_settings", failing)

        assert main_module.main() == 1
        assert chamadas == []


class TestSettingsIntegracao:
    def test_settings_invalidas_nunca_chegam_ao_servidor(self) -> None:
        with pytest.raises(ConfigError):
            build_settings(token="curto", host="127.0.0.1", port=1)

    def test_provider_explicito_e_respeitado(self) -> None:
        from maskgw.admin.http import resolve

        resolved = resolve(
            MappingSecretProvider(
                {"MASKGW_ADMIN_ENABLED": "1", "MASKGW_ADMIN_TOKEN": TOKEN},
            )
        )
        assert resolved is not None
        assert resolved.token == TOKEN
