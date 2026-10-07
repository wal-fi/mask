"""Fila administrativa dedicada da Admin API v2 (Fase 9, Etapa 7, D-108).

Os handlers v2 deixam de executar o coordenador sincrono no event loop: cada
operacao (as escritas e os testes de conexao) vira um `WorkTicket` executado
por um dos workers FIXOS desta fila. O event loop so espera a notificacao, e as
leituras continuam respondendo — elas leem o selo do coordenador, sem fila.

## Ownership

O composition root e o dono: cria a fila SO com catalogo + Admin HTTP, adota a
referencia antes de `start()` e a drena no shutdown. Os workers sao criados e
adotados ANTES do `start()` com os estados da D-107 (`idle`/`starting`/
`started`); a tentativa e gravada antes da chamada, e so o retorno comprova o
inicio. `submit` nunca cria thread: aceitar, registrar e enfileirar acontecem
na MESMA secao do lock, contra a mesma marca que `close_admission` liga.
`ThreadPoolExecutor.submit` nao serve aqui porque enfileira o trabalho e so
depois cria e inicia a thread, registrando-a apos o `start()`: uma falha nesse
ponto deixaria o trabalho aceito sem dono comprovado (a lacuna P2-B).

## Capacidade (aprovada pelo usuario)

`DEFAULT_WORKERS` (2) workers e `DEFAULT_WAITING` (2) posicoes de espera:
no maximo 4 operacoes aceitas e ainda nao concluidas (na fila ou em
execucao), contadas NO ato de aceitar, antes de qualquer despacho. Acima disso,
ou com a barreira fechada, `submit` recusa sem efeito. Nao ha fila duravel,
retry, rebase nem rollback automatico.

## Conclusao e shutdown

Toda operacao aceita e acompanhada ate terminar, com ou sem request: o
cancelamento ou a desconexao do cliente nao cancela o ticket, e a resposta
perdida e incerta. `drain()` conclui TODAS as aceitas — na fila e em execucao —
e so entao os workers saem; nao ha teto absoluto (a verificacao tem prazo, uma
chamada do SO bloqueada nao). Um worker cujo inicio ou termino nao e
comprovado deixa o `drain()` incompleto: quem chama nao solta o que ele usa.

## Falha com estado desconhecido

Um job que levanta (o v2 traduz toda falha conhecida antes; o que escapa e
`BaseException` ou defeito) marca a fila `broken` — novas admissoes recusadas
ate o reinicio — e chama `on_unknown` (o coordenador se bloqueia e retira o
selo de leitura). Enquanto isso, nenhum outro ticket e despachado. Se essa
contencao nao for confirmada, a fila CONGELA: os aceitos restantes concluem
como falha sem executar, acompanhados, notificados e auditados uma vez pelo
`abandon` do chamador. Nenhuma excecao ou traceback fica guardado no ticket.

## Limites

O lock cobre a concorrencia, nao toda interrupcao assincrona: uma
`BaseException` entregue entre duas instrucoes do proprio ciclo (ex. entre
registrar e desfazer na admissao, ou entre concluir o ticket e notificar) pode
deixar capacidade retida ou um request sem resposta. A direcao e conservadora —
nada e executado nem liberado sem dono —, mas nao ha atomicidade absoluta.
"""

from __future__ import annotations

import contextlib
import threading
from collections import deque
from collections.abc import Callable
from typing import Any, Final, Generic, TypeVar

#: Workers dedicados (aprovado pelo usuario, D-108).
DEFAULT_WORKERS: Final = 2

#: Posicoes de espera alem dos workers (aprovado pelo usuario, D-108).
DEFAULT_WAITING: Final = 2

_T = TypeVar("_T")

#: Estados de ownership de um worker (D-107).
_IDLE: Final = "idle"
_STARTING: Final = "starting"
_STARTED: Final = "started"

#: Estados de um ticket.
_QUEUED: Final = "queued"
_RUNNING: Final = "running"
_DONE: Final = "done"


class AdminWorkUnavailableError(Exception):
    """Admissao recusada: barreira fechada, fila quebrada ou capacidade cheia."""

    def __init__(self) -> None:
        super().__init__("fila administrativa indisponivel")


class AdminWorkShutdownIncompleteError(Exception):
    """O shutdown nao comprovou o termino de todos os workers/operacoes.

    Quem chama NAO solta catalogo, registry, supervisor nem store: eles podem
    estar em uso por um worker vivo ou de inicio incerto. Mensagem fixa.
    """

    def __init__(self) -> None:
        super().__init__("encerramento da fila administrativa incompleto")


class WorkTicket(Generic[_T]):
    """Uma operacao aceita. O job e o notificador sao soltos assim que usados.

    `failed` diz que o job levantou (estado desconhecido); `take()` entrega o
    resultado uma vez e o solta. Nenhuma excecao e guardada.
    """

    __slots__ = ("_abandon", "_failed", "_job", "_notify", "_result", "_state")

    def __init__(
        self,
        job: Callable[[], _T],
        notify: Callable[[], None] | None,
        abandon: Callable[[], None] | None = None,
    ) -> None:
        self._job: Callable[[], _T] | None = job
        self._notify = notify
        # Chamado (fora do lock) SO se o ticket for concluido sem executar,
        # porque a contencao de um estado desconhecido falhou.
        self._abandon = abandon
        self._state = _QUEUED
        self._result: _T | None = None
        self._failed = False

    @property
    def done(self) -> bool:
        return self._state == _DONE

    @property
    def failed(self) -> bool:
        return self._failed

    def take(self) -> _T | None:
        """O resultado, uma vez; `None` se o job falhou ou ja foi entregue."""
        result, self._result = self._result, None
        return result


class _Worker:
    """Uma thread de worker com dono, adotada antes do `start()` (D-107)."""

    __slots__ = ("cancelled", "done", "lock", "ran", "state", "thread")

    def __init__(self, queue: AdminWorkQueue, index: int) -> None:
        self.lock = threading.Lock()
        self.state = _IDLE
        self.ran = False
        self.cancelled = False
        self.done = threading.Event()
        self.thread = threading.Thread(
            target=_worker_main,
            args=(queue, self),
            name=f"maskgw-admin-work-{index}",
            daemon=False,
        )

    def joinable(self) -> bool:
        """Inicio comprovado: `start()` retornou, o alvo foi entrado ou saiu."""
        with self.lock:
            started = self.state == _STARTED or self.ran
        return started or self.done.is_set()

    def settled(self) -> bool:
        """Termino FISICO comprovado, ou `start()` nunca tentado.

        Cancela so o worker que NAO comprovou inicio e ainda nao rodou: um
        worker `started` vai servir a fila, e cancela-lo deixaria operacoes
        aceitas sem executor.
        """
        with self.lock:
            if not self.ran and self.state != _STARTED:
                self.cancelled = True
            state = self.state
        if state == _IDLE:
            return True
        return self.done.is_set() and not self.thread.is_alive()


def _worker_main(queue: AdminWorkQueue, worker: _Worker) -> None:
    try:
        with worker.lock:
            if worker.cancelled:
                return
            worker.ran = True
        queue._serve()
    finally:
        worker.done.set()


class AdminWorkQueue:
    """Workers fixos, admissao atomica e drenagem integral do aceito."""

    __slots__ = (
        "_broken",
        "_capacity",
        "_closing",
        "_cond",
        "_containing",
        "_frozen",
        "_on_unknown",
        "_pending",
        "_stopping",
        "_tickets",
        "_workers",
    )

    def __init__(
        self,
        *,
        workers: int = DEFAULT_WORKERS,
        waiting: int = DEFAULT_WAITING,
        on_unknown: Callable[[], None] | None = None,
    ) -> None:
        if workers < 1 or waiting < 0:
            msg = "capacidade da fila administrativa invalida"
            raise ValueError(msg)
        self._cond = threading.Condition(threading.Lock())
        self._capacity = workers + waiting
        self._pending: deque[WorkTicket[Any]] = deque()
        # Aceitos e ainda nao concluidos (na fila + em execucao).
        self._tickets: set[WorkTicket[Any]] = set()
        self._closing = False
        self._stopping = False
        self._broken = False
        # Um job falhou e `on_unknown` ainda nao terminou: nada e despachado.
        self._containing = False
        # A contencao falhou: nenhum job aceito restante e EXECUTADO; cada um
        # conclui como falha, acompanhado e notificado (fail-closed).
        self._frozen = False
        self._on_unknown = on_unknown
        self._workers = tuple(_Worker(self, index) for index in range(workers))

    # -- lifecycle -------------------------------------------------------

    def start(self) -> None:
        """Inicia os workers ja adotados. Falha propaga o erro original.

        A tentativa e gravada ANTES de cada `start()`; uma falha ou interrupcao
        deixa o worker em inicio incerto, e `drain()` o reportara incompleto.
        """
        for worker in self._workers:
            with worker.lock:
                worker.state = _STARTING
            worker.thread.start()
            with worker.lock:
                worker.state = _STARTED

    def close_admission(self) -> None:
        """Barreira: nenhuma submissao nova e aceita. Permanente; nao espera."""
        with self._cond:
            self._closing = True

    def drain(self) -> bool:
        """Conclui TODAS as operacoes aceitas e recolhe os workers.

        `True` so com a fila vazia e todo worker com termino fisico comprovado
        (ou nunca iniciado). Espera sem timeout os workers iniciados: o limite e
        o trabalho, nao a espera (D-057). Recusa ser chamado de um worker.
        """
        if self.owns_current_thread():
            msg = "drenagem recusada a partir de um worker administrativo"
            raise RuntimeError(msg)
        with self._cond:
            self._closing = True
            self._stopping = True
            self._cond.notify_all()
        for worker in self._workers:
            # Um worker de inicio incerto que nunca rodou e cancelado aqui: se
            # vier a rodar, sai sem tocar a fila.
            worker.settled()
            if worker.joinable():
                worker.thread.join()
        # Laco explicito, sem curto-circuito: todo worker e conferido.
        settled = True
        for worker in self._workers:
            if not worker.settled():
                settled = False
        with self._cond:
            empty = not self._tickets
        return settled and empty

    def owns_current_thread(self) -> bool:
        current = threading.current_thread()
        return any(worker.thread is current for worker in self._workers)

    # -- admissao --------------------------------------------------------

    def submit(
        self,
        job: Callable[[], _T],
        *,
        notify: Callable[[], None] | None = None,
        abandon: Callable[[], None] | None = None,
    ) -> WorkTicket[_T]:
        """Aceita, registra, enfileira e acorda um worker sob o lock; ou recusa.

        Nada e chamado sob o lock alem de mudar estado: nem o job, nem o
        notificador, nem auditoria. Uma excecao em QUALQUER passo do trecho
        protegido — registrar, enfileirar (antes ou depois de mutar a fila) ou
        acordar o worker — e desfeita ainda sob o lock, antes de qualquer
        worker poder ver o ticket: primeiro o job e os callbacks sao soltos
        (um ticket que porventura sobre na fila conclui sem executar nada),
        depois o registro e a posicao na fila sao removidos. Assim o job
        recusado nunca executa. Uma interrupcao assincrona entre as proprias
        instrucoes desse desfazer nao e coberta.
        """
        ticket: WorkTicket[_T] = WorkTicket(job, notify, abandon)
        with self._cond:
            if self._closing or self._broken or len(self._tickets) >= self._capacity:
                raise AdminWorkUnavailableError
            try:
                self._tickets.add(ticket)
                self._pending.append(ticket)
                self._cond.notify()
            except BaseException:
                ticket._job = None
                ticket._notify = None
                ticket._abandon = None
                self._tickets.discard(ticket)
                with contextlib.suppress(ValueError):
                    self._pending.remove(ticket)
                raise
        return ticket

    @property
    def accepted(self) -> int:
        """Operacoes aceitas e ainda nao concluidas."""
        with self._cond:
            return len(self._tickets)

    @property
    def broken(self) -> bool:
        with self._cond:
            return self._broken

    @property
    def closing(self) -> bool:
        with self._cond:
            return self._closing

    @property
    def frozen(self) -> bool:
        """A contencao de um estado desconhecido falhou: nada mais executa."""
        with self._cond:
            return self._frozen

    # -- worker ----------------------------------------------------------

    def _serve(self) -> None:
        while True:
            with self._cond:
                while self._containing or (not self._pending and not self._stopping):
                    self._cond.wait()
                if not self._pending:
                    return  # parando e sem nada aceito pendente
                ticket = self._pending.popleft()
                ticket._state = _RUNNING
                job, ticket._job = ticket._job, None
                skipped = self._frozen
            failed = skipped
            result: object = None
            if not skipped:
                try:
                    if job is not None:
                        result = job()
                except BaseException:
                    failed = True
                    with self._cond:
                        self._broken = True
                        self._containing = True
                    self._contain()
            del job
            with self._cond:
                ticket._result = None if failed else result
                ticket._failed = failed
                ticket._state = _DONE
                self._tickets.discard(ticket)
                notify, ticket._notify = ticket._notify, None
                abandon, ticket._abandon = ticket._abandon, None
                self._cond.notify_all()
            del result
            # Fora do lock. Loop ja fechado (`call_soon_threadsafe`) ou falha
            # do notificador/auditoria nao tira o ticket de dono: ele ja esta
            # concluido.
            if skipped and abandon is not None:
                with contextlib.suppress(Exception):
                    abandon()
            if notify is not None:
                with contextlib.suppress(Exception):
                    notify()

    def _contain(self) -> None:
        """Estado desconhecido: bloqueia o coordenador antes de despachar mais.

        Se o bloqueio NAO for confirmado (`on_unknown` ausente ou levantou), a
        fila congela: os aceitos restantes concluem como falha sem executar.
        Nunca se volta a executar escrita sobre um estado desconhecido nao
        contido.
        """
        contained = False
        try:
            if self._on_unknown is not None:
                self._on_unknown()
                contained = True
        except Exception:
            contained = False
        finally:
            with self._cond:
                if not contained:
                    self._frozen = True
                self._containing = False
                self._cond.notify_all()

    def __repr__(self) -> str:
        with self._cond:
            return (
                f"AdminWorkQueue(accepted={len(self._tickets)}, closing={self._closing}, "
                f"broken={self._broken})"
            )


#: Filas cujo encerramento nao foi comprovado e cujo dono (a `Application`)
#: nunca chegou a existir — startup parcial. Mantem as referencias vivas.
_RETAINED: Final[list[object]] = []

#: Serializa registro e busca+remocao por identidade em `_RETAINED`. Cobre SO
#: a lista: nenhuma limpeza nem chamada do SO roda sob ele.
_RETAINED_LOCK: Final = threading.Lock()


def retain(*resources: object) -> None:
    """Conserva o dono de recursos que um startup parcial nao pode soltar."""
    with _RETAINED_LOCK:
        _RETAINED.extend(resources)


def release_retained(*resources: object) -> None:
    """Solta, por identidade, recursos cujo encerramento foi comprovado.

    Achar o indice e apagar acontecem sob o MESMO lock: uma remocao
    concorrente nao desloca a lista entre os dois passos, e so os donos
    pedidos saem — nunca o de outro startup que nao comprovou fechamento.
    """
    with _RETAINED_LOCK:
        for resource in resources:
            for index, held in enumerate(_RETAINED):
                if held is resource:
                    del _RETAINED[index]
                    break


__all__ = [
    "DEFAULT_WAITING",
    "DEFAULT_WORKERS",
    "AdminWorkQueue",
    "AdminWorkShutdownIncompleteError",
    "AdminWorkUnavailableError",
    "WorkTicket",
    "release_retained",
    "retain",
]
