"""Referencia imutavel + refcount + marca de aposentadoria.

O problema, e por que nao ha solucao mais simples: uma mudanca administrativa
constroi um runtime NOVO por inteiro (D-048) e troca a referencia. O runtime
antigo nao pode ser fechado enquanto uma query ainda o estiver usando — fechar
a conexao psycopg sob uma query em execucao aborta a consulta e produz um erro
que o cliente nao causou.

Mecanismo (D-054):

- o runtime e um agregado cujo CONTEUDO nunca muda; trocar de runtime e
  reatribuir uma unica referencia;
- toda query ADQUIRE a referencia atual uma vez, no inicio, e usa ESSA
  referencia ate o fim — e isso que garante "o antigo inteiro ou o novo
  inteiro";
- a aquisicao incrementa um contador; o fim da query o decrementa, sempre em
  `finally`;
- o swap publica o novo e APOSENTA o antigo. Quem fecha o antigo e o ultimo
  usuario que o libera, ou o proprio swap quando ja nao ha nenhum.

As seis regras da secao 8.3 da especificacao estao implementadas aqui, e cada
uma tem teste. A que mais custa esquecer e a regra 5: sem fechar no proprio
swap quando o contador ja e zero, um Gateway ocioso nunca fecharia o runtime
antigo, porque nao havera release algum para disparar o fechamento.

Alternativa descartada: lock compartilhado de leitura/escrita segurado durante
toda a query. E mais simples de escrever, mas um reload passaria a esperar a
query mais longa, e queries novas ficariam em fila atras dele.
"""

from __future__ import annotations

import threading
from types import TracebackType
from typing import Final

from maskgw.config.gateway import GatewayConfig
from maskgw.config.models import MaskingFileConfig
from maskgw.db.postgres import PostgresAdapter
from maskgw.masking.engine import MaskingEngine

#: Quantos runtimes aposentados podem estar abertos ao mesmo tempo.
#:
#: Cada aposentado segura UMA conexao PostgreSQL ate seu ultimo usuario sair.
#: Com o limite em 1, o numero de conexoes simultaneas do processo e no maximo
#: 2 — o publicado mais um aposentado ainda em uso.
#:
#: Nao existe teto de TEMPO. `statement_timeout` limita a execucao dentro do
#: PostgreSQL; nao limita bloqueio de rede, o `fetchmany` em lotes (D-018), a
#: canonicalizacao (D-015), o masking, a serializacao, nem um cliente que pare
#: de consumir. O aposentado vive ate a query liberar a referencia.
MAX_RETIRED_RUNTIMES: Final = 1


class RetiredRuntimeInUseError(RuntimeError):
    """Ja ha aposentado demais em uso; o reload nao pode prosseguir.

    Levantada ANTES de compilar, construir e conectar o candidato: nada e
    criado para uma operacao que ja se sabe que vai falhar. A fronteira
    administrativa a traduz em `409 RELOAD_BUSY`.
    """


class Runtime:
    """Agregado de configuracao, objetos compilados e adapter.

    O CONTEUDO e imutavel: os componentes sao expostos so por propriedade e
    nunca sao trocados. O unico estado mutavel e o do ciclo de vida —
    `refcount`, `retired` e `closed` — e ele so pode ser tocado pelo
    `RuntimeRegistry`, sob o lock dele.

    Uma query nunca ve uma mistura: um `MaskingEngine` novo com um `SqlPolicy`
    antigo produziria decisoes que nenhuma configuracao jamais descreveu.
    """

    __slots__ = (
        "_adapter",
        "_closed",
        "_config",
        "_connection_lock",
        "_engine",
        "_file_config",
        "_refcount",
        "_retired",
        "_revision",
    )

    def __init__(
        self,
        *,
        revision: int,
        file_config: MaskingFileConfig,
        config: GatewayConfig,
        engine: MaskingEngine,
        adapter: PostgresAdapter,
    ) -> None:
        self._revision = revision
        self._file_config = file_config
        self._config = config
        self._engine = engine
        self._adapter = adapter
        # D-034: uma conexao psycopg nao suporta consultas concorrentes
        # intercaladas, e nao ha pool. O lock e POR RUNTIME, porque cada
        # runtime tem seu proprio adapter.
        self._connection_lock = threading.Lock()

        # Estado de ciclo de vida. Escrito SOMENTE pelo `RuntimeRegistry`
        # deste modulo, e somente sob o lock dele. O acoplamento entre as duas
        # classes e deliberado: a decisao de fechar depende de ler `retired` e
        # `refcount` JUNTOS, numa unica secao critica, e expor isso como API
        # publica conviteria a leitura parcial — que fecha runtime em uso ou
        # vaza aposentado.
        self._refcount = 0
        self._retired = False
        self._closed = False

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def file_config(self) -> MaskingFileConfig:
        """Modelo validado do arquivo: a fonte administrativa (D-047)."""
        return self._file_config

    @property
    def config(self) -> GatewayConfig:
        return self._config

    @property
    def engine(self) -> MaskingEngine:
        return self._engine

    @property
    def adapter(self) -> PostgresAdapter:
        return self._adapter

    @property
    def connection_lock(self) -> threading.Lock:
        return self._connection_lock

    def __repr__(self) -> str:
        # Sem DSN, sem politica, sem adapter. So metadata de ciclo de vida.
        return (
            f"Runtime(revision={self._revision}, refcount={self._refcount}, "
            f"retired={self._retired}, closed={self._closed})"
        )


class RuntimeRegistry:
    """Publica um runtime por vez e coordena o fechamento dos aposentados.

    Um unico lock cobre as quatro operacoes que leem ou escrevem o par
    `(retired, refcount)`: aquisicao, swap, release e decisao de fechamento.
    Uma decisao tomada sobre leitura parcial desse par fecha um runtime em uso
    ou vaza um aposentado.

    O lock NAO cobre a execucao da query, e nao cobre o `close` do adapter:
    fechar uma conexao psycopg pode demorar, e segurar o lock durante isso
    bloquearia a aquisicao de toda query nova.
    """

    __slots__ = ("_acquired_total", "_current", "_lock", "_max_retired", "_retired")

    def __init__(self, initial: Runtime, *, max_retired: int = MAX_RETIRED_RUNTIMES) -> None:
        self._lock = threading.Lock()
        self._current = initial
        # Aposentados ainda nao fechados, na ordem em que foram aposentados.
        self._retired: list[Runtime] = []
        self._max_retired = max_retired
        # Aquisicoes desde o start. Uma query adquire exatamente uma vez
        # (D-054), entao este contador E a contagem de queries que a secao
        # 13.4 pede em `GET /admin/v1/status`. Vive aqui, e nao no Gateway,
        # porque `runtime/` fica abaixo dos dois planos: o admin plane pode
        # le-lo sem conhecer `gateway/`. E contador, nunca historico — se
        # perde no restart, e o schema do status diz isso.
        self._acquired_total = 0

    # -- leitura ---------------------------------------------------------

    @property
    def current(self) -> Runtime:
        """O runtime publicado, SEM adquirir referencia.

        Para leitura de metadata administrativa (revision, config). Uma query
        nunca usa isto: ela precisa de `acquire`, que impede o fechamento.
        """
        with self._lock:
            return self._current

    def retired_in_use(self) -> int:
        """Quantos aposentados ainda estao abertos."""
        with self._lock:
            return len(self._retired)

    def acquired_total(self) -> int:
        """Aquisicoes bem-sucedidas desde o start. Metadata, nunca historico."""
        with self._lock:
            return self._acquired_total

    def check_can_swap(self) -> None:
        """Regra do limite, avaliada ANTES de construir o candidato.

        Levanta `RetiredRuntimeInUseError` quando ja ha aposentado demais. E o
        passo 4 do fluxo da secao 7.4: nenhuma conexao nova e aberta para uma
        operacao que ja se sabe condenada.
        """
        with self._lock:
            self._check_can_swap_locked()

    def _check_can_swap_locked(self) -> None:
        if len(self._retired) >= self._max_retired:
            msg = (
                f"ha {len(self._retired)} runtime(s) aposentado(s) ainda em uso; "
                f"o limite e {self._max_retired}"
            )
            raise RetiredRuntimeInUseError(msg)

    # -- ciclo de vida de uma query --------------------------------------

    def acquire(self) -> Runtime:
        """Adquire o runtime publicado e incrementa seu contador.

        Ler a referencia e incrementar precisam ser atomicos entre si. Sem
        isso existe a janela: ler a referencia, o reload trocar e fechar, e so
        entao incrementar — uma query executando sobre uma conexao ja fechada.
        """
        with self._lock:
            runtime = self._current
            # Regra 6: nenhuma query adquire um runtime aposentado. Um
            # aposentado nunca e a referencia publicada, entao isto e uma
            # afirmacao de invariante, nao um caminho esperado.
            if runtime._retired or runtime._closed:
                msg = "runtime publicado esta aposentado ou fechado"
                raise RuntimeError(msg)
            runtime._refcount += 1
            # Contado somente na aquisicao BEM-SUCEDIDA, sob o mesmo lock que
            # incrementa o refcount: um contador atualizado fora dele contaria
            # aquisicoes que nunca aconteceram.
            self._acquired_total += 1
            return runtime

    def release(self, runtime: Runtime) -> None:
        """Libera a referencia. Fecha o aposentado se este for o ultimo.

        Chamada sempre em `finally`. O `close` acontece FORA do lock.
        """
        with self._lock:
            to_close = self._release_locked(runtime)
        if to_close is not None:
            to_close.adapter.close()

    def _release_locked(self, runtime: Runtime) -> Runtime | None:
        if runtime._refcount <= 0:
            msg = "release sem acquire correspondente"
            raise RuntimeError(msg)
        runtime._refcount -= 1
        return self._take_closable_locked(runtime)

    def _take_closable_locked(self, runtime: Runtime) -> Runtime | None:
        """Decide o fechamento e marca `closed` na MESMA secao critica.

        Marcar aqui e o que garante "exatamente uma vez": a transicao para
        `closed` acontece sob o lock, entao duas threads nao podem ambas
        concluir que cabe fechar. Verificar sob o lock e fechar depois, sem
        marcar, permitiria dois `close` no mesmo adapter.
        """
        if not runtime._retired:
            return None
        if runtime._refcount > 0:
            return None
        if runtime._closed:
            return None
        runtime._closed = True
        self._retired.remove(runtime)
        return runtime

    # -- ciclo de vida do runtime ----------------------------------------

    def swap(self, new: Runtime) -> Runtime | None:
        """Publica `new`, aposenta o atual e devolve o que deve ser fechado.

        O chamador fecha o retorno FORA de qualquer lock. Devolver em vez de
        fechar aqui dentro e deliberado: mantem o `close` fora da secao
        critica sem espalhar o conhecimento do lock.

        Nao bloqueia esperando queries antigas (regra 1). Se o antigo ainda
        tiver usuarios, ele fica aposentado e sera fechado pelo ultimo release.
        """
        with self._lock:
            self._check_can_swap_locked()
            old = self._current
            if old is new:
                msg = "swap para o mesmo runtime"
                raise RuntimeError(msg)
            # Regra 2: aposentar o antigo e publicar o novo na MESMA secao
            # critica. Entre uma coisa e outra nao pode haver aquisicao.
            old._retired = True
            self._retired.append(old)
            self._current = new
            # Regra 5: se ja nao ha usuarios, fecha agora. Sem isto um Gateway
            # ocioso nunca fecharia o antigo — nao havera release algum.
            return self._take_closable_locked(old)

    def swap_and_close(self, new: Runtime) -> None:
        """`swap` que ja fecha o aposentado, quando couber."""
        to_close = self.swap(new)
        if to_close is not None:
            to_close.adapter.close()

    def close_all(self) -> None:
        """Fecha publicado e aposentados. Para o shutdown."""
        with self._lock:
            pending = [*self._retired, self._current]
            self._retired.clear()
            closing = []
            for runtime in pending:
                if not runtime._closed:
                    runtime._closed = True
                    closing.append(runtime)
        for runtime in closing:
            runtime.adapter.close()

    # -- conveniencia ----------------------------------------------------

    def borrow(self) -> _Borrowed:
        """`with registry.borrow() as runtime:` — adquire e libera."""
        return _Borrowed(self)

    def __repr__(self) -> str:
        return f"RuntimeRegistry(retired_open={len(self._retired)})"


class _Borrowed:
    """Context manager que garante o `release` em `finally`."""

    __slots__ = ("_registry", "_runtime")

    def __init__(self, registry: RuntimeRegistry) -> None:
        self._registry = registry
        self._runtime: Runtime | None = None

    def __enter__(self) -> Runtime:
        self._runtime = self._registry.acquire()
        return self._runtime

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._runtime is not None:
            self._registry.release(self._runtime)
            self._runtime = None
