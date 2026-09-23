"""Registry multi-datasource: geracoes por alias, sessoes e drenagem.

Fase 9, Etapa 3 (spec §§7 e 11; D-071, D-087 a D-091).

```text
DatasourceRegistry
├── crm-producao  → geracao 12 → PreparedRuntime (politica, limites, alvo)
├── financeiro    → geracao 4  → PreparedRuntime
└── homologacao   → geracao 9  → PreparedRuntime
```

E o mesmo mecanismo de D-054 — referencia imutavel, refcount e marca de
aposentadoria — aplicado por datasource, com uma diferenca que vem de D-071:
a geracao NAO guarda conexao. Cada sessao admitida captura a geracao publicada
e abre a SUA propria conexao upstream, preservando estado de sessao sem
pooling transacional. O refcount de uma geracao e o numero de sessoes que a
capturaram.

Regras, todas com teste:

1. **Uma geracao nunca muda de conteudo.** Trocar de politica, destino ou
   segredo e publicar uma geracao NOVA, com numero novo, nunca reutilizado —
   nem quando um alias e removido e recriado.
2. **A sessao admitida fica com a geracao que capturou.** Uma troca, uma
   desabilitacao ou uma remocao nao muda o destino de sessao ja admitida: novas
   admissoes veem a geracao nova (ou nenhuma), as antigas drenam.
3. **Um lock curto cobre admissao, publicacao, retirada, release e a decisao
   de fechamento** — tudo que le ou escreve o par `(retired, sessions)`. Ele
   nao cobre a execucao de consulta, a conexao upstream nem o fechamento.
4. **A geracao aposentada fecha exatamente uma vez**: no ultimo release ou,
   se ja estiver ociosa, na propria troca/retirada. `closed` e marcado sob o
   lock pela transicao que decide fechar; o descarte acontece fora dele.
5. **Nenhuma sessao e admitida numa geracao aposentada ou fechada.**
6. **Isolamento.** A contabilidade e por datasource: a troca, a falha ou a
   drenagem de um nao muda a geracao, as sessoes nem os limites dos demais.
7. **Limites** (D-089): sessoes por datasource (`limits.max_sessions`, contando
   as geracoes em drenagem) e globais; geracoes aposentadas e candidatos em voo
   por datasource e globais. O excesso e recusado como ocupado ANTES de
   construir candidato ou abrir conexao. Retirar (desabilitar/remover) nunca e
   recusado por limite: so reduz exposicao.
8. **Shutdown** (D-090): para a admissao, cancela consultas em voo, encerra
   sessoes ociosas, aguarda TODOS os releases — sem abandonar thread nem
   conexao — e so entao descarta as geracoes. Idempotente.

Este modulo fica abaixo dos planos: nao importa `gateway/`, `admin/` nem
`mcp/`.
"""

from __future__ import annotations

import threading
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from types import TracebackType
from typing import Final

from maskgw.db.postgres import PostgresAdapter
from maskgw.runtime.candidate import DatasourceRuntimeError, PreparedRuntime

#: Sessoes simultaneas no processo inteiro (default de
#: `MASKGW_PGWIRE_MAX_SESSIONS`, spec §5.1). Parametrizavel no composition root.
MAX_GLOBAL_SESSIONS: Final = 32

#: Geracoes aposentadas ainda drenando, no processo inteiro.
MAX_GLOBAL_RETIRED: Final = 4

#: Candidatos em construcao/verificacao ao mesmo tempo, no processo inteiro.
MAX_GLOBAL_CANDIDATES: Final = 2

#: Geracoes aposentadas drenando por datasource antes de aceitar outra troca.
MAX_RETIRED_PER_DATASOURCE: Final = 1

#: Candidatos em voo por datasource.
MAX_CANDIDATES_PER_DATASOURCE: Final = 1

#: Intervalo, em segundos, entre pedidos de cancelamento repetidos no shutdown.
_RECANCEL_INTERVAL_SECONDS: Final = 1.0


class DatasourceUnavailableError(DatasourceRuntimeError):
    """Alias desconhecido, desabilitado, removido ou registry encerrando.

    Uma unica mensagem fixa para todos os casos: nao distingue alias
    inexistente de desabilitado, e nunca ecoa o alias recebido.
    """

    def __init__(self) -> None:
        super().__init__("datasource indisponivel")


class DatasourceBusyError(DatasourceRuntimeError):
    """Limite de sessoes, candidatos ou aposentados atingido."""

    def __init__(self) -> None:
        super().__init__("capacidade do datasource esgotada")


class DatasourceRegistryClosedError(DatasourceRuntimeError):
    """O registry ja iniciou o shutdown; nada novo e aceito."""

    def __init__(self) -> None:
        super().__init__("registry de datasources encerrado")


@dataclass(frozen=True, slots=True)
class RegistryLimits:
    """Limites globais do registry. Os por datasource vem do registro."""

    max_sessions: int = MAX_GLOBAL_SESSIONS
    max_retired: int = MAX_GLOBAL_RETIRED
    max_candidates: int = MAX_GLOBAL_CANDIDATES

    def __post_init__(self) -> None:
        for value in (self.max_sessions, self.max_retired, self.max_candidates):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                msg = "limite do registry invalido"
                raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class GenerationStatus:
    """Metadata de uma geracao publicada: sem destino, segredo ou politica."""

    alias: str
    datasource_id: str
    generation: int
    record_revision: int
    sessions: int


@dataclass(frozen=True, slots=True)
class RegistryStatus:
    """Retrato coerente do registry, lido sob um unico lock."""

    published: tuple[GenerationStatus, ...]
    retired_open: int
    sessions: int
    candidates: int
    closing: bool


class DatasourceGeneration:
    """Uma geracao imutavel de um datasource.

    O CONTEUDO nunca muda. O estado de ciclo de vida (`sessions`, `retired`,
    `closed`) so e tocado pelo `DatasourceRegistry`, sob o lock dele — a
    decisao de fechar depende de ler `retired` e `sessions` juntos.
    """

    __slots__ = (
        "_alias",
        "_closed",
        "_datasource_id",
        "_generation",
        "_prepared",
        "_record_revision",
        "_retired",
        "_sessions",
    )

    def __init__(
        self,
        *,
        datasource_id: str,
        alias: str,
        generation: int,
        record_revision: int,
        prepared: PreparedRuntime,
    ) -> None:
        self._datasource_id = datasource_id
        self._alias = alias
        self._generation = generation
        self._record_revision = record_revision
        self._prepared: PreparedRuntime | None = prepared
        self._sessions = 0
        self._retired = False
        self._closed = False

    @property
    def datasource_id(self) -> str:
        return self._datasource_id

    @property
    def alias(self) -> str:
        return self._alias

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def record_revision(self) -> int:
        return self._record_revision

    @property
    def max_sessions(self) -> int:
        prepared = self._require_prepared()
        return prepared.max_sessions

    @property
    def prepared(self) -> PreparedRuntime:
        """Conteudo compilado; indisponivel depois do descarte."""
        return self._require_prepared()

    def _require_prepared(self) -> PreparedRuntime:
        prepared = self._prepared
        if prepared is None:
            raise DatasourceUnavailableError()
        return prepared

    def _dispose(self) -> None:
        """Descarte unico: solta o alvo de conexao (e a senha) da memoria.

        Chamado somente pelo registry, fora do lock, pela transicao que marcou
        `closed`. Nenhuma sessao pode existir aqui: o fechamento so e decidido
        com `sessions == 0`.
        """
        self._prepared = None

    def __repr__(self) -> str:
        # Sem alias, destino, politica ou segredo: so ciclo de vida.
        return (
            f"DatasourceGeneration(generation={self._generation}, sessions={self._sessions}, "
            f"retired={self._retired}, closed={self._closed})"
        )


class DatasourceLease:
    """Uma sessao admitida: a geracao capturada e a conexao PROPRIA dela.

    Uso de uma thread por vez, como uma sessao PGWire. `use()` serializa o
    acesso ao adapter com o shutdown: enquanto uma consulta roda, o shutdown
    so pode CANCELAR (pelo protocolo do PostgreSQL); a conexao e fechada e o
    release acontece quando a consulta termina.
    """

    __slots__ = (
        "_adapter",
        "_closed",
        "_generation",
        "_lock",
        "_registry",
        "_terminating",
    )

    def __init__(
        self,
        registry: DatasourceRegistry,
        generation: DatasourceGeneration,
        adapter: PostgresAdapter,
    ) -> None:
        self._registry = registry
        self._generation = generation
        self._adapter = adapter
        # Cobre o adapter desta sessao: consulta, fechamento e shutdown.
        self._lock = threading.Lock()
        # Escritos sob `_lock`.
        self._closed = False
        self._terminating = False

    @property
    def generation(self) -> int:
        return self._generation.generation

    @property
    def datasource_id(self) -> str:
        return self._generation.datasource_id

    @property
    def closed(self) -> bool:
        return self._closed

    @contextmanager
    def use(self) -> Iterator[PostgresAdapter]:
        """Adapter desta sessao, exclusivo durante o bloco.

        Sessao fechada ou encerrada pelo shutdown nao e utilizavel. Se o
        shutdown pediu encerramento durante o bloco, a sessao fecha ao sair.
        """
        with self._lock:
            if self._closed or self._terminating:
                self._close_locked()
                raise DatasourceUnavailableError()
            try:
                yield self._adapter
            finally:
                # Relido aqui: o shutdown pode te-lo marcado durante o bloco.
                if self._termination_requested():
                    self._close_locked()

    def _termination_requested(self) -> bool:
        return self._terminating

    def close(self) -> None:
        """Fecha a conexao e libera a geracao. Idempotente."""
        with self._lock:
            self._close_locked()

    def _close_locked(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._adapter.close()
        finally:
            self._registry._release(self)

    def _request_termination(self) -> None:
        """Fase 1 do shutdown: fecha a sessao ociosa ja; em uso, cancela.

        Nunca bloqueia: se o lock da sessao esta ocupado, marca a sessao e
        pede ao servidor o cancelamento da consulta em voo. A marca vem ANTES
        do cancelamento, para que a saida de `use()` a encontre.
        """
        if self._lock.acquire(blocking=False):
            try:
                self._terminating = True
                self._close_locked()
            finally:
                self._lock.release()
            return
        self._terminating = True
        self._adapter.cancel()

    def _finish_termination(self) -> None:
        """Fase 2 do shutdown: espera a consulta cancelada sair e fecha.

        Fecha a janela da fase 1: se a consulta terminou entre a checagem da
        marca em `use()` e a liberacao do lock, a sessao continuaria aberta e o
        shutdown esperaria para sempre. Aqui o lock e adquirido de forma
        bloqueante — a consulta ja recebeu cancelamento — e o fechamento e
        idempotente.
        """
        # O cancelamento da fase 1 pode ter chegado antes de o statement
        # existir no servidor (sessao ainda validando a SQL). Enquanto o lock
        # estiver ocupado, o pedido e repetido; o `statement_timeout` continua
        # sendo o teto.
        while not self._lock.acquire(timeout=_RECANCEL_INTERVAL_SECONDS):
            self._terminating = True
            self._adapter.cancel()
        try:
            self._terminating = True
            self._close_locked()
        finally:
            self._lock.release()

    def __enter__(self) -> DatasourceLease:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"DatasourceLease(generation={self.generation}, closed={self._closed})"


class CandidateReservation:
    """Vaga de candidato reservada ANTES de construir e verificar.

    Com `publish=True` reserva tambem a vaga de aposentado que a publicacao
    VAI gerar quando o datasource ja tem geracao publicada (troca), de modo que
    uma troca reservada nunca falha por limite depois de o candidato ter sido
    verificado e persistido. Criar ou reabilitar nao aposenta nada e nao
    consome essa vaga.
    """

    __slots__ = (
        "_datasource_id",
        "_key",
        "_publish",
        "_registry",
        "_released",
        "_retired_slot",
    )

    def __init__(
        self,
        registry: DatasourceRegistry,
        *,
        key: str,
        datasource_id: str | None,
        publish: bool,
    ) -> None:
        self._registry = registry
        self._key = key
        self._datasource_id = datasource_id
        self._publish = publish
        self._released = False
        # Escrito pelo registry, sob o lock dele, na reserva.
        self._retired_slot = False

    def publish(
        self,
        *,
        datasource_id: str,
        alias: str,
        record_revision: int,
        prepared: PreparedRuntime,
    ) -> DatasourceGeneration:
        """Publica a geracao nova e aposenta a anterior do mesmo datasource."""
        if not self._publish or self._released:
            msg = "reserva sem direito de publicacao"
            raise RuntimeError(msg)
        return self._registry._publish(
            self,
            datasource_id=datasource_id,
            alias=alias,
            record_revision=record_revision,
            prepared=prepared,
        )

    def release(self) -> None:
        self._registry._release_reservation(self)

    def __enter__(self) -> CandidateReservation:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


class DatasourceRegistry:
    """Publica uma geracao por alias e coordena sessoes e drenagem."""

    __slots__ = (
        "_candidates",
        "_close_lock",
        "_closed",
        "_closing",
        "_drained",
        "_ds_candidates",
        "_ds_retired",
        "_ds_sessions",
        "_limits",
        "_lock",
        "_next_generation",
        "_published",
        "_reserved_retired",
        "_retired",
        "_sessions",
    )

    def __init__(self, limits: RegistryLimits | None = None) -> None:
        self._limits = limits if limits is not None else RegistryLimits()
        self._lock = threading.Lock()
        self._drained = threading.Condition(self._lock)
        # Serializa chamadas concorrentes de `close()` sem cobrir a admissao.
        self._close_lock = threading.Lock()
        self._published: dict[str, DatasourceGeneration] = {}
        self._retired: list[DatasourceGeneration] = []
        self._sessions: set[DatasourceLease] = set()
        self._ds_sessions: Counter[str] = Counter()
        self._ds_retired: Counter[str] = Counter()
        self._ds_candidates: Counter[str] = Counter()
        self._candidates = 0
        self._reserved_retired = 0
        # Numero de geracao do processo: monotonico e nunca reutilizado.
        self._next_generation = 1
        self._closing = False
        self._closed = False

    @property
    def limits(self) -> RegistryLimits:
        return self._limits

    # -- leitura ---------------------------------------------------------

    def status(self) -> RegistryStatus:
        with self._lock:
            published = tuple(
                GenerationStatus(
                    alias=generation.alias,
                    datasource_id=generation.datasource_id,
                    generation=generation.generation,
                    record_revision=generation.record_revision,
                    sessions=generation._sessions,
                )
                for _alias, generation in sorted(self._published.items())
            )
            return RegistryStatus(
                published=published,
                retired_open=len(self._retired),
                sessions=len(self._sessions),
                candidates=self._candidates,
                closing=self._closing,
            )

    def current(self, alias: str) -> DatasourceGeneration:
        """Geracao publicada, SEM admitir sessao. Metadata administrativa."""
        with self._lock:
            generation = self._published.get(alias)
            if generation is None or self._closing:
                raise DatasourceUnavailableError()
            return generation

    # -- candidatos e publicacao -----------------------------------------

    def reserve(
        self,
        key: str,
        *,
        datasource_id: str | None = None,
        publish: bool,
    ) -> CandidateReservation:
        """Reserva a vaga ANTES de construir o candidato (D-089).

        `key` identifica o datasource para o limite de candidatos: o ID, ou
        uma chave derivada do alias quando o datasource ainda nao existe.
        """
        with self._lock:
            if self._closing:
                raise DatasourceRegistryClosedError()
            if self._ds_candidates[key] >= MAX_CANDIDATES_PER_DATASOURCE:
                raise DatasourceBusyError()
            if self._candidates >= self._limits.max_candidates:
                raise DatasourceBusyError()
            # A publicacao so aposenta quando o datasource ja tem geracao
            # publicada; criar ou reabilitar nao consome vaga de aposentado.
            retires = (
                publish
                and datasource_id is not None
                and self._published_for_locked(datasource_id) is not None
            )
            if retires:
                assert datasource_id is not None  # noqa: S101 - narrowing do mypy
                self._check_retired_capacity_locked(datasource_id)
                self._reserved_retired += 1
            self._ds_candidates[key] += 1
            self._candidates += 1
            reservation = CandidateReservation(
                self, key=key, datasource_id=datasource_id, publish=publish
            )
            reservation._retired_slot = retires
            return reservation

    def _published_for_locked(self, datasource_id: str) -> DatasourceGeneration | None:
        for generation in self._published.values():
            if generation.datasource_id == datasource_id:
                return generation
        return None

    def _check_retired_capacity_locked(self, datasource_id: str) -> None:
        """Ha vaga para UMA aposentada nova deste datasource e do processo?"""
        if self._ds_retired[datasource_id] >= MAX_RETIRED_PER_DATASOURCE:
            raise DatasourceBusyError()
        if len(self._retired) + self._reserved_retired >= self._limits.max_retired:
            raise DatasourceBusyError()

    def _release_reservation(self, reservation: CandidateReservation) -> None:
        with self._lock:
            if reservation._released:
                return
            reservation._released = True
            key = reservation._key
            self._ds_candidates[key] -= 1
            if self._ds_candidates[key] <= 0:
                del self._ds_candidates[key]
            self._candidates -= 1
            if reservation._retired_slot:
                reservation._retired_slot = False
                self._reserved_retired -= 1
            # O shutdown tambem espera candidatos em voo (teste de conexao).
            self._drained.notify_all()

    def _publish(
        self,
        reservation: CandidateReservation,
        *,
        datasource_id: str,
        alias: str,
        record_revision: int,
        prepared: PreparedRuntime,
    ) -> DatasourceGeneration:
        with self._lock:
            if reservation._released:
                msg = "reserva ja liberada"
                raise RuntimeError(msg)
            # `_closed`, e nao `_closing`: uma operacao ja reservada antes do
            # inicio do shutdown ainda pode publicar ate o fechamento, e o
            # fechamento descarta o que ela publicou.
            if self._closed:
                raise DatasourceRegistryClosedError()
            old = self._published.get(alias)
            if old is not None and old.datasource_id != datasource_id:
                msg = "alias publicado pertence a outro datasource"
                raise RuntimeError(msg)
            for other_alias, generation in self._published.items():
                if generation.datasource_id == datasource_id and other_alias != alias:
                    msg = "datasource ja publicado sob outro alias"
                    raise RuntimeError(msg)
            if old is not None:
                if reservation._retired_slot:
                    # A vaga reservada vira a aposentada real logo abaixo.
                    reservation._retired_slot = False
                    self._reserved_retired -= 1
                else:
                    # Defensivo: uma geracao surgiu depois da reserva.
                    self._check_retired_capacity_locked(datasource_id)
            new = DatasourceGeneration(
                datasource_id=datasource_id,
                alias=alias,
                generation=self._next_generation,
                record_revision=record_revision,
                prepared=prepared,
            )
            self._next_generation += 1
            # Publicar o novo e aposentar o antigo na MESMA secao critica:
            # entre uma coisa e outra nao pode haver admissao.
            self._published[alias] = new
            to_close = None if old is None else self._retire_locked(old)
        if to_close is not None:
            to_close._dispose()
        return new

    def withdraw(self, datasource_id: str) -> bool:
        """Retira a geracao publicada do datasource (desabilitar/remover).

        Novas admissoes deixam de encontra-lo imediatamente; sessoes ja
        admitidas drenam na geracao que capturaram. Nunca recusado por limite.
        Devolve se havia geracao publicada.
        """
        with self._lock:
            found = next(
                (
                    (alias, generation)
                    for alias, generation in self._published.items()
                    if generation.datasource_id == datasource_id
                ),
                None,
            )
            if found is None:
                return False
            alias, generation = found
            del self._published[alias]
            to_close = self._retire_locked(generation)
        if to_close is not None:
            to_close._dispose()
        return True

    def _retire_locked(self, generation: DatasourceGeneration) -> DatasourceGeneration | None:
        generation._retired = True
        self._retired.append(generation)
        self._ds_retired[generation.datasource_id] += 1
        # Ja ociosa: fecha agora. Sem isto uma geracao sem sessoes nunca
        # fecharia, porque nao havera release algum para dispara-lo.
        return self._take_closable_locked(generation)

    def _take_closable_locked(
        self, generation: DatasourceGeneration
    ) -> DatasourceGeneration | None:
        """Decide o fechamento e marca `closed` na MESMA secao critica."""
        if not generation._retired or generation._sessions > 0 or generation._closed:
            return None
        generation._closed = True
        self._retired.remove(generation)
        self._ds_retired[generation.datasource_id] -= 1
        if self._ds_retired[generation.datasource_id] <= 0:
            del self._ds_retired[generation.datasource_id]
        return generation

    # -- sessoes ---------------------------------------------------------

    def open_session(self, alias: str) -> DatasourceLease:
        """Admite uma sessao na geracao publicada do alias e a conecta.

        A contagem e feita sob o lock ANTES de abrir a conexao: dois pedidos
        simultaneos nunca ultrapassam o limite. A conexao e aberta fora do
        lock, com o lock da propria sessao seguro — o shutdown que chegar nesse
        meio tempo so pode cancelar e marcar, nunca fechar sob o `connect`.
        """
        with self._lock:
            # Ordem das recusas: nada que dependa do alias antes do limite
            # global, para que a lotacao global nao revele o catalogo.
            if self._closing:
                raise DatasourceUnavailableError()
            if len(self._sessions) >= self._limits.max_sessions:
                raise DatasourceBusyError()
            generation = self._published.get(alias)
            if generation is None or generation._retired or generation._closed:
                raise DatasourceUnavailableError()
            prepared = generation.prepared
            if self._ds_sessions[generation.datasource_id] >= prepared.max_sessions:
                raise DatasourceBusyError()
            # Construir o adapter (sem conectar) ANTES de mexer em contador:
            # uma falha aqui nao pode deixar admissao contada sem lease.
            lease = DatasourceLease(self, generation, prepared.new_adapter())
            generation._sessions += 1
            self._ds_sessions[generation.datasource_id] += 1
            self._sessions.add(lease)
            lease._lock.acquire()
        try:
            lease._adapter.connect()
        except BaseException:
            lease._close_locked()
            lease._lock.release()
            raise
        try:
            if lease._terminating:
                lease._close_locked()
                raise DatasourceUnavailableError()
        finally:
            lease._lock.release()
        return lease

    def _release(self, lease: DatasourceLease) -> None:
        with self._lock:
            if lease not in self._sessions:
                return
            self._sessions.remove(lease)
            generation = lease._generation
            generation._sessions -= 1
            self._ds_sessions[generation.datasource_id] -= 1
            if self._ds_sessions[generation.datasource_id] <= 0:
                del self._ds_sessions[generation.datasource_id]
            to_close = self._take_closable_locked(generation)
            self._drained.notify_all()
        if to_close is not None:
            to_close._dispose()

    # -- shutdown --------------------------------------------------------

    def begin_shutdown(self) -> None:
        """Interrompe a admissao e as reservas. Nao espera nada."""
        with self._lock:
            self._closing = True

    def close(self) -> None:
        """Shutdown ordenado, idempotente e sem abandono (D-090).

        1. para a admissao e as reservas;
        2. encerra toda sessao: ociosa fecha ja; em uso recebe cancelamento e
           fecha quando a consulta termina;
        3. aguarda TODOS os releases, sem timeout — o que limita a espera e o
           cancelamento e o `statement_timeout` de cada sessao;
        4. descarta, uma vez cada, a geracao publicada e as aposentadas.
        """
        with self._close_lock:
            with self._lock:
                if self._closed:
                    return
                self._closing = True
                leases = list(self._sessions)
            # Duas fases: todo cancelamento e pedido antes de esperar qualquer
            # sessao, para que as consultas em voo terminem em paralelo.
            for lease in leases:
                lease._request_termination()
            for lease in leases:
                lease._finish_termination()
            with self._lock:
                # Sessoes E candidatos: um teste de conexao em voo segura uma
                # conexao de verificacao com o segredo upstream, e nao pode
                # sobreviver ao shutdown. O candidato ja e limitado pelo
                # `connect_timeout` e fecha a conexao antes de soltar a vaga.
                while self._sessions or self._candidates:
                    self._drained.wait()
                pending = [*self._published.values(), *self._retired]
                self._published.clear()
                self._retired.clear()
                self._ds_retired.clear()
                disposing = []
                for generation in pending:
                    if not generation._closed:
                        generation._retired = True
                        generation._closed = True
                        disposing.append(generation)
                self._closed = True
            for generation in disposing:
                generation._dispose()

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"DatasourceRegistry(published={len(self._published)}, "
                f"retired_open={len(self._retired)}, sessions={len(self._sessions)}, "
                f"closing={self._closing})"
            )


__all__ = [
    "MAX_CANDIDATES_PER_DATASOURCE",
    "MAX_GLOBAL_CANDIDATES",
    "MAX_GLOBAL_RETIRED",
    "MAX_GLOBAL_SESSIONS",
    "MAX_RETIRED_PER_DATASOURCE",
    "CandidateReservation",
    "DatasourceBusyError",
    "DatasourceGeneration",
    "DatasourceLease",
    "DatasourceRegistry",
    "DatasourceRegistryClosedError",
    "DatasourceUnavailableError",
    "GenerationStatus",
    "RegistryLimits",
    "RegistryStatus",
]
