"""Fase 7, etapa 3: o Gateway adquire e libera um runtime por query.

Cobre a secao 12.2 da especificacao e a diretriz de liberacao: a referencia
sai assim que a execucao sincrona termina e o `QueryResult` protegido esta
montado — nao quando o cliente MCP termina de consumir.
"""

from __future__ import annotations

import threading

import pytest

from maskgw.audit import AuditLog
from maskgw.db.result import MaskedResult
from maskgw.errors import QueryRejected
from maskgw.gateway.models import GatewayError, QueryResult
from maskgw.gateway.service import Gateway
from maskgw.masking.descriptor import ColumnDescriptor
from maskgw.masking.engine import Action, Decision
from maskgw.runtime import RetiredRuntimeInUseError, RuntimeRegistry
from tests.conftest import make_test_registry, make_test_runtime


def result_with(value: str, *, masked: bool) -> MaskedResult:
    action = Action.MASK if masked else Action.ALLOW
    return MaskedResult(
        columns=(ColumnDescriptor(output_name="cpf", origin_name="cpf"),),
        decisions=(Decision(action=action, output_name="cpf"),),
        rows=((value,),),
    )


class Adapter:
    """Adapter duble com bloqueio opcional, para simular query em voo."""

    def __init__(self, value: str, *, masked: bool = True) -> None:
        self.value = value
        self.masked = masked
        self.close_calls = 0
        self.entered = threading.Event()
        self.release = threading.Event()
        self.block = False
        self.error: Exception | None = None

    def connect(self) -> None:
        return

    def execute_validated(self, sql: str) -> MaskedResult:  # noqa: ARG002
        self.entered.set()
        if self.block:
            self.release.wait(timeout=5)
        if self.error is not None:
            raise self.error
        return result_with(self.value, masked=self.masked)

    def close(self) -> None:
        self.close_calls += 1


def refcount(registry: RuntimeRegistry) -> int:
    return registry.current._refcount


class TestAcquisitionPerQuery:
    def test_reference_is_released_when_the_query_returns(self) -> None:
        adapter = Adapter("x")
        registry = make_test_registry(adapter)
        gateway = Gateway(registry, AuditLog())

        gateway.query("SELECT cpf FROM cliente")
        assert refcount(registry) == 0

    def test_reference_is_released_when_the_query_fails(self) -> None:
        adapter = Adapter("x")
        adapter.error = QueryRejected("nao permitido")
        registry = make_test_registry(adapter)
        gateway = Gateway(registry, AuditLog())

        with pytest.raises(GatewayError):
            gateway.query("SELECT cpf FROM cliente")
        assert refcount(registry) == 0

    def test_many_queries_do_not_leak_references(self) -> None:
        adapter = Adapter("x")
        registry = make_test_registry(adapter)
        gateway = Gateway(registry, AuditLog())
        for _ in range(50):
            gateway.query("SELECT cpf FROM cliente")
        assert refcount(registry) == 0

    def test_result_does_not_hold_the_runtime(self) -> None:
        """Diretriz: a referencia nao se prolonga pelo consumo do cliente.

        Depois que `query` devolve, o resultado ja e imutavel e ja passou pelo
        Masking Engine. Um cliente lento nao pode segurar uma conexao — e nao
        pode bloquear um reload por RELOAD_BUSY.
        """
        adapter = Adapter("x")
        registry = make_test_registry(adapter)
        gateway = Gateway(registry, AuditLog())

        result = gateway.query("SELECT cpf FROM cliente")

        # O cliente ainda nem olhou o resultado, e o reload ja pode acontecer.
        registry.check_can_swap()
        registry.swap_and_close(make_test_runtime(Adapter("y"), revision=2))
        assert adapter.close_calls == 1

        # E o resultado continua integro depois do runtime ter sido fechado.
        assert result.rows == [["x"]]
        assert result.columns[0].masked is True


class TestReloadWithQueryInFlight:
    def test_in_flight_query_keeps_the_old_runtime_open(self) -> None:
        old_adapter = Adapter("antigo")
        registry = make_test_registry(old_adapter)
        gateway = Gateway(registry, AuditLog())
        old_adapter.block = True

        outcome: list[QueryResult] = []

        def run() -> None:
            outcome.append(gateway.query("SELECT cpf FROM cliente"))

        worker = threading.Thread(target=run)
        worker.start()
        assert old_adapter.entered.wait(timeout=5)

        # Reload no meio da query: publica o novo, aposenta o antigo, e NAO
        # bloqueia esperando (regra 1 da secao 8.3).
        new_adapter = Adapter("novo")
        registry.swap_and_close(make_test_runtime(new_adapter, revision=2))
        assert old_adapter.close_calls == 0

        old_adapter.release.set()
        worker.join(timeout=5)

        # A query em voo terminou com o runtime ANTIGO inteiro.
        assert outcome[0].rows == [["antigo"]]
        # E o antigo so foi fechado quando ela liberou a referencia.
        assert old_adapter.close_calls == 1

    def test_query_started_after_the_swap_uses_the_new_runtime(self) -> None:
        old_adapter = Adapter("antigo")
        registry = make_test_registry(old_adapter)
        gateway = Gateway(registry, AuditLog())

        new_adapter = Adapter("novo")
        registry.swap_and_close(make_test_runtime(new_adapter, revision=2))

        assert gateway.query("SELECT cpf FROM cliente").rows == [["novo"]]

    def test_no_query_is_aborted_by_the_swap(self) -> None:
        adapters = [Adapter(f"v{i}") for i in range(6)]
        registry = make_test_registry(adapters[0])
        gateway = Gateway(registry, AuditLog())

        errors: list[BaseException] = []
        stop = threading.Event()

        def worker() -> None:
            while not stop.is_set():
                try:
                    gateway.query("SELECT cpf FROM cliente")
                except BaseException as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()

        for index in range(1, len(adapters)):
            while True:
                try:
                    registry.check_can_swap()
                    registry.swap_and_close(make_test_runtime(adapters[index], revision=index + 1))
                except RetiredRuntimeInUseError:
                    continue
                break

        stop.set()
        for thread in threads:
            thread.join(timeout=5)

        assert errors == []

    def test_revision_is_visible_and_follows_the_swap(self) -> None:
        registry = make_test_registry(Adapter("x"))
        gateway = Gateway(registry, AuditLog())
        assert gateway.revision == 1
        registry.swap_and_close(make_test_runtime(Adapter("y"), revision=7))
        assert gateway.revision == 7


class TestClose:
    def test_close_closes_published_and_retired(self) -> None:
        old_adapter = Adapter("antigo")
        registry = make_test_registry(old_adapter)
        gateway = Gateway(registry, AuditLog())
        registry.acquire()

        new_adapter = Adapter("novo")
        registry.swap_and_close(make_test_runtime(new_adapter, revision=2))
        assert old_adapter.close_calls == 0

        gateway.close()
        assert old_adapter.close_calls == 1
        assert new_adapter.close_calls == 1

    def test_close_is_idempotent(self) -> None:
        adapter = Adapter("x")
        gateway = Gateway(make_test_registry(adapter), AuditLog())
        gateway.close()
        gateway.close()
        assert adapter.close_calls == 1
