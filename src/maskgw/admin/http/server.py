"""Servidor HTTP administrativo numa thread, com bind confirmado de verdade.

## O passo que importa: confirmar o bind, nao a partida da thread

A secao 9.2 exige, no startup, **aguardar a confirmacao de que o socket esta
efetivamente escutando**, com timeout, antes de disponibilizar o MCP. O motivo
e o pior caso: se o MCP subisse primeiro, o Gateway atenderia queries por um
tempo e entao morreria por uma porta ocupada — com o administrador convencido
de que a Admin API esta no ar.

Este modulo nao resolve isso esperando um flag do uvicorn. Ele **cria e vincula
o socket na thread chamadora**, antes de qualquer thread existir:

```text
socket() -> bind()   <- falha aqui, sincronamente, se a porta estiver ocupada
         -> listen()
         -> thread(uvicorn.Server.run(sockets=[sock]))
         -> espera server.started, com timeout
```

Com isso, "porta ocupada" deixa de ser uma corrida: `bind` levanta `OSError` no
mesmo `build_application` que constrói tudo o mais, e o processo nao sobe.
`server.started` cobre o resto — o loop de eventos ter comecado a aceitar.

## Por que a thread nao e daemon

Uma thread daemon e morta na saida do interpretador, no meio do que estiver
fazendo. A secao 9.2 exige `join` no shutdown e **nenhuma thread abandonada**:
toda thread criada aqui e regular e tem `join`.

E `join` com timeout nao basta. `Thread.join(timeout=...)` retorna `None` tanto
quando a thread terminou quanto quando o tempo acabou, entao um `join` expirado
fica indistinguivel de um concluido — e o objeto se declararia parado enquanto
uma requisicao ainda em execucao segura o registry que o composition root esta
prestes a fechar.

Conferir `is_alive()` e levantar resolveria a confusao, mas produziria um
**retorno parcial**: o shutdown teria comecado, nao teria terminado, e cada
chamador teria de saber o que fazer com esse meio-estado — inclusive nao fechar
runtime nenhum, nao soltar o lock e voltar depois. Estado a mais em todo mundo,
para um caso em que so ha uma resposta certa: esperar.

Por isso **nao existe timeout de shutdown**. `stop()` sinaliza e faz `join()`
integral; quando ele retorna, a thread ACABOU. O unico timeout do modulo e o da
confirmacao de escuta no startup, onde desistir e seguro porque nada foi
disponibilizado ainda.

O que se limita e o TRABALHO, nao a espera: o uvicorn recebe
`timeout_graceful_shutdown` e cancela sozinho requisicoes que se arrastem,
entao a thread sempre chega ao fim. Um cliente em loopback que pare de consumir
a resposta nao prende o processo — e nada e abandonado para consegui-lo.

## Por que `stdout` e intocado

`stdout` e o canal do protocolo MCP. Um unico byte escrito nele por um handler
default do uvicorn corromperia a sessao. Por isso `log_config=None` e
`access_log=False`: o uvicorn nao instala handler algum, e os registros dele
ficam sem destino ate que o operador configure `logging`. Sem handler
configurado, o `logging.lastResort` do Python entrega em **stderr**, e somente
a partir de WARNING — nunca em `stdout`, e nunca no caminho feliz.

Este modulo tambem nao importa `logging`: `admin/` continua proibido de faze-lo,
e o registro administrativo pertence a `audit/`, na Etapa 10.
"""

from __future__ import annotations

import socket
import threading
from types import TracebackType
from typing import Final

import uvicorn
from starlette.types import ASGIApp

from maskgw.admin.http.app import AppFactory
from maskgw.errors import CapabilityError

#: Quanto esperar pela confirmacao de escuta antes de desistir do startup.
#:
#: E o UNICO timeout deste modulo. No startup ele e seguro: nada foi
#: disponibilizado ainda, e desistir significa nao subir.
DEFAULT_STARTUP_TIMEOUT_SECONDS: Final = 10.0

#: Quanto o uvicorn espera por requisicoes em voo antes de cancela-las.
#:
#: Este limite fica no SERVIDOR, e nao no `join`. A diferenca e tudo: limitar o
#: `join` abandona a thread e devolve o controle com ela viva; limitar a espera
#: GRACIOSA faz a thread terminar, e o `join` continua sendo ate o fim. Uma
#: requisicao administrativa nao executa SQL (D-049) e le so memoria, entao
#: nenhuma legitima chega perto disso — o que este numero cobre e um cliente em
#: loopback que pare de consumir a resposta e, sem ele, prenderia o shutdown do
#: processo para sempre.
GRACEFUL_SHUTDOWN_SECONDS: Final = 10

#: Fila de conexoes pendentes. Pequena de proposito: e um plano administrativo
#: em loopback, com um operador, nao um servidor publico.
LISTEN_BACKLOG: Final = 16

_THREAD_NAME: Final = "maskgw-admin-http"


class AdminHttpUnavailableError(CapabilityError):
    """O servidor administrativo nao conseguiu escutar.

    `CapabilityError` porque e exatamente isso: uma capacidade essencial
    ausente na instalacao. Fatal no startup, como o capability check de
    proveniencia (D-026). A mensagem e fixa e nao cita host, porta, `errno` nem
    a excecao original.
    """

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("servidor administrativo nao conseguiu escutar")


class AdminHttpServer:
    """Cicla o uvicorn numa thread nao-daemon, com bind e parada deterministas.

    `start()` e sincrono: quando retorna sem erro, o socket ja esta escutando.
    Quando levanta, nada ficou de pe — nem socket, nem thread —, porque a
    desmontagem tambem espera a thread ate o fim.

    `stop()` e idempotente e **bloqueia ate a thread terminar**. Nao existe
    retorno parcial: quando ele volta, nao ha thread, nem socket, nem servidor.
    """

    __slots__ = (
        "_app_factory",
        "_graceful_timeout",
        "_host",
        "_lifecycle_lock",
        "_port",
        "_requested_port",
        "_server",
        "_socket",
        "_started",
        "_startup_timeout",
        "_stopped",
        "_thread",
    )

    def __init__(
        self,
        *,
        app_factory: AppFactory,
        host: str,
        port: int,
        startup_timeout: float = DEFAULT_STARTUP_TIMEOUT_SECONDS,
        graceful_timeout: int = GRACEFUL_SHUTDOWN_SECONDS,
    ) -> None:
        self._app_factory = app_factory
        self._host = host
        self._requested_port = port
        self._startup_timeout = startup_timeout
        self._graceful_timeout = graceful_timeout

        self._lifecycle_lock = threading.Lock()
        self._socket: socket.socket | None = None
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._port = 0
        self._started = False
        self._stopped = False

    @property
    def port(self) -> int:
        """Porta REALMENTE vinculada. So faz sentido depois de `start()`."""
        return self._port

    @property
    def host(self) -> str:
        return self._host

    @property
    def running(self) -> bool:
        with self._lifecycle_lock:
            return self._started and not self._stopped

    def start(self) -> None:
        """Vincula, sobe a thread e so retorna com o socket escutando."""
        with self._lifecycle_lock:
            if self._started:
                msg = "servidor administrativo ja iniciado"
                raise RuntimeError(msg)
            self._started = True

        listener: socket.socket | None = None
        try:
            # O `bind` acontece AQUI, na thread chamadora e dentro da protecao:
            # porta ocupada levanta sincronamente, e o estado do objeto fica
            # coerente com o fato de nada estar escutando.
            listener = self._bind()

            # A aplicacao so pode ser montada AGORA: a allowlist de `Host`
            # depende da porta efetivamente vinculada, que pode ter sido
            # escolhida pelo sistema.
            server = uvicorn.Server(self._config(self._app_factory(self._port)))
            thread = threading.Thread(
                target=server.run,
                kwargs={"sockets": [listener]},
                name=_THREAD_NAME,
                # Nao-daemon: o shutdown faz `join`, e nenhuma thread e
                # abandonada na saida do interpretador (secao 9.2).
                daemon=False,
            )
            thread.start()
            self._socket = listener
            self._server = server
            self._thread = thread
            self._await_listening(server, thread)
        except BaseException:
            # Falha parcial: nada fica de pe. O `_tear_down` cobre o caso em
            # que a thread ja existe — e ESPERA por ela ate o fim; o `close`
            # abaixo cobre o caso em que o socket foi criado mas nunca chegou a
            # ser adotado, e no qual nenhuma thread chegou a existir.
            orphan = listener if self._socket is None else None
            self._tear_down()
            with self._lifecycle_lock:
                self._stopped = True
            if orphan is not None:
                orphan.close()
            raise

    def stop(self) -> None:
        """Sinaliza o uvicorn e AGUARDA a thread ate o fim. Idempotente.

        Nao ha timeout aqui, e a ausencia dele e a garantia. Aguardar com
        timeout nao resolveria nada: expirado, ou se abandona a thread — que e
        justamente o que a secao 9.2 proibe — ou se devolve o controle com o
        shutdown pela metade, e quem chama fica com um estado que nao sabe
        interpretar. Bloquear ate o fim elimina o retorno parcial: quando este
        metodo volta, a thread ACABOU.

        O que precisa ser limitado e o trabalho, nao a espera. O uvicorn recebe
        `timeout_graceful_shutdown`, entao ele mesmo cancela requisicoes que se
        arrastem e a thread termina — e o `join` continua sendo integral.

        Esperar aqui, e nao depois, e o que impede uma requisicao
        administrativa em voo de encontrar um registry ja desmontado: quem
        chama fecha os runtimes somente apos este retorno (secao 9.2).
        """
        with self._lifecycle_lock:
            if not self._started:
                # Nunca subiu: nao ha thread, socket nem uvicorn.
                self._stopped = True
                return
            if self._stopped:
                return
        self._tear_down()
        with self._lifecycle_lock:
            self._stopped = True

    def _bind(self) -> socket.socket:
        """Cria e vincula o socket na thread chamadora.

        `SO_REUSEADDR` NAO e usado. No Windows ele permite que dois processos
        se liguem a mesma porta, e o segundo sequestraria silenciosamente a
        superficie administrativa do primeiro. Aqui, porta ocupada precisa
        falhar — e falhar e o comportamento correto.
        """
        family = socket.AF_INET6 if ":" in self._host else socket.AF_INET
        listener = socket.socket(family, socket.SOCK_STREAM)
        bound = False
        try:
            listener.bind((self._host, self._requested_port))
            listener.listen(LISTEN_BACKLOG)
            listener.setblocking(False)
            self._port = listener.getsockname()[1]
            bound = True
        except OSError:
            bound = False
        if not bound:
            listener.close()
            # Fora do `except`: nem `__cause__` nem `__context__` apontam para
            # o `OSError`, cuja mensagem carrega host, porta e `errno`
            # (D-017).
            raise AdminHttpUnavailableError()
        return listener

    def _config(self, app: ASGIApp) -> uvicorn.Config:
        return uvicorn.Config(
            app,
            # `log_config=None`: o uvicorn nao instala handler nenhum, e nada
            # e escrito em `stdout`, que e do protocolo MCP (secao 10.4).
            log_config=None,
            access_log=False,
            # Desligado, e nao "auto". A aplicacao administrativa nao registra
            # nenhum evento de startup ou shutdown: quem constroi e destroi
            # runtime, lock de arquivo e conexao e o composition root, na ordem
            # da secao 9.2. Deixar o protocolo ligado acrescentaria uma
            # superficie que ninguem usa e um caminho de erro a mais entre o
            # bind e o "escutando".
            lifespan="off",
            # Sem `Server:` na resposta: o nome e a versao do servidor sao
            # reconhecimento gratuito para quem sonda a porta.
            server_header=False,
            date_header=True,
            # O limite fica AQUI, no trabalho, e nao no `join`. Passado este
            # tempo o uvicorn cancela o que restou e a thread termina; o
            # shutdown continua sendo integral, e nada e abandonado.
            timeout_graceful_shutdown=self._graceful_timeout,
        )

    def _await_listening(self, server: uvicorn.Server, thread: threading.Thread) -> None:
        """Espera o uvicorn confirmar que comecou a servir, ou desiste."""
        deadline = threading.Event()
        waited = 0.0
        step = 0.01
        while waited < self._startup_timeout:
            if server.started:
                return
            if not thread.is_alive():
                # A thread morreu antes de confirmar: o startup falhou por um
                # motivo que nao chegou ate aqui, e nao vamos inventa-lo.
                raise AdminHttpUnavailableError()
            deadline.wait(step)
            waited += step
        raise AdminHttpUnavailableError()

    def _tear_down(self) -> None:
        """Sinaliza, espera a thread ATE O FIM e so entao solta as referencias.

        A ordem e o ponto. Apagar `_server`, `_thread` e `_socket` antes de a
        thread morrer tornaria o abandono invisivel: sem referencia nao ha o
        que esperar depois, e uma requisicao ainda ativa continuaria tocando o
        registry que o chamador esta prestes a fechar. O socket, pelo mesmo
        motivo, so e fechado depois: fecha-lo por baixo de um loop ainda ativo
        produziria erro numa requisicao que o cliente nao causou.

        `join()` sem timeout tambem torna desnecessario conferir `is_alive()`
        depois — ele so retorna quando a thread terminou. Com timeout seria
        obrigatorio conferir, porque `Thread.join` devolve `None` nos dois
        casos, e um `join` expirado ficaria indistinguivel de um concluido.
        """
        server = self._server
        thread = self._thread
        listener = self._socket

        if server is not None:
            # O uvicorn observa esta flag no proprio loop; nao ha sinal, e
            # sinais nem funcionariam fora da thread principal.
            server.should_exit = True
        if thread is not None:
            thread.join()

        self._server = None
        self._thread = None
        self._socket = None
        if listener is not None:
            listener.close()

    def __enter__(self) -> AdminHttpServer:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()

    def __repr__(self) -> str:
        # Sem token, sem app, sem socket. Host e porta sao operacionais.
        return (
            f"AdminHttpServer(host={self._host!r}, port={self._port!r}, running={self.running!r})"
        )
