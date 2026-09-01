"""Fase 7, etapa 6: secao critica administrativa e fluxo de escrita/reload.

Cobre as secoes 6, 7.4, 7.6, 12.1 e 12.4 da especificacao. Nenhum PostgreSQL
nesta camada: o adapter e um duble que CONTA construcoes, conexoes e
fechamentos, porque as garantias que importam — "nenhum candidato foi
construido", "fechado exatamente uma vez", "o total de conexoes nao cresce" —
so se afirmam contando. A camada com banco real esta em `TestRealReload`,
marcada `integration`.

Nao ha HTTP aqui, nem deve haver: rota, autenticacao, bind, porta, headers e
handlers pertencem a Etapa 7.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, cast

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from maskgw.admin import (
    AdminConfigService,
    AdminError,
    AdminErrorCategory,
    AdminOperation,
    parse_document,
    render_document,
)
from maskgw.bootstrap import Application, build_application
from maskgw.config import (
    ConfigDurabilityError,
    ConfigFileStore,
    FilesystemHooks,
    digest_bytes,
    load_config_bundle_text,
)
from maskgw.config.models import MaskingFileConfig
from maskgw.db.postgres import PostgresAdapter
from maskgw.masking.engine import MaskingEngine
from maskgw.runtime import Runtime, RuntimeRegistry

SENSITIVE_DSN = "postgresql://admin:super-secret@database.invalid/private"
SENSITIVE_SQL = "SELECT cpf FROM cliente WHERE cpf = '11122233344'"
SENSITIVE_VALUE = "11122233344"
SENSITIVE_PATH_MARKER = "super-secret-config-directory"

RULE_ID = f"rul_{'0' * 32}"
EXCEPTION_ID = f"exc_{'1' * 32}"

ADOPTED_CONFIG = f"""# comentario que a reserializacao vai perder
revision: 1
masking:
- match: cpf
  mode: contains
  case_sensitive: false
  transformer: fixed
  config:
    value: '[REDACTED]'
  id: {RULE_ID}
exceptions:
- match: tipo_cpf
  mode: exact
  case_sensitive: false
  id: {EXCEPTION_ID}
database:
  statement_timeout_ms: 2000
  max_rows: 10
sql:
  allowed_pg_functions:
  - pg_typeof
  - pg_backend_pid
  denied_functions: []
""".encode()

UNADOPTED_CONFIG = b"""masking:
- match: cpf
  transformer: md5
database:
  max_rows: 10
"""

EXTERNAL_EDIT = b"""revision: 1
masking: []
exceptions: []
"""


# --------------------------------------------------------------------------
# Dubles
# --------------------------------------------------------------------------


class CountingAdapter:
    """Adapter que conta conexao e fechamento, sem banco algum."""

    def __init__(self, *, connect_error: BaseException | None = None) -> None:
        self.connect_error = connect_error
        self.connect_calls = 0
        self.close_calls = 0
        self._lock = threading.Lock()

    def connect(self) -> None:
        with self._lock:
            self.connect_calls += 1
        if self.connect_error is not None:
            raise self.connect_error

    def close(self) -> None:
        with self._lock:
            self.close_calls += 1


class TrackingFactory:
    """Fabrica de adapters que registra cada candidato construido."""

    def __init__(
        self,
        *,
        connect_error: BaseException | None = None,
        build_error: BaseException | None = None,
    ) -> None:
        self.connect_error = connect_error
        self.build_error = build_error
        self.adapters: list[CountingAdapter] = []
        self._lock = threading.Lock()

    def __call__(self, *, config: object, engine: object) -> PostgresAdapter:  # noqa: ARG002
        if self.build_error is not None:
            raise self.build_error
        adapter = CountingAdapter(connect_error=self.connect_error)
        with self._lock:
            self.adapters.append(adapter)
        return cast(PostgresAdapter, adapter)

    @property
    def builds(self) -> int:
        with self._lock:
            return len(self.adapters)

    @property
    def connects(self) -> int:
        with self._lock:
            return sum(adapter.connect_calls for adapter in self.adapters)

    @property
    def closes(self) -> int:
        with self._lock:
            return sum(adapter.close_calls for adapter in self.adapters)


class DurabilityFailingStore(ConfigFileStore):
    """Instala o arquivo novo e so entao nega a durabilidade.

    Existe porque o `fsync` de diretorio nao existe no Windows: injetar a falha
    pela plataforma cobriria a semantica de depois-do-`replace` somente no
    POSIX. A falha real de `fsync` continua testada onde ela existe
    (`TestDurability`), e a omissao do Windows continua sendo afirmada, nao
    simulada. Este duble cobre o que e independente de plataforma: o que o
    servico FAZ quando o arquivo ja esta instalado e a durabilidade nao esta
    confirmada.
    """

    def write_atomic(self, data: bytes, *, expected_digest: str) -> NoReturn:
        result = super().write_atomic(data, expected_digest=expected_digest)
        raise ConfigDurabilityError(result.digest)


# --------------------------------------------------------------------------
# Montagem
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Harness:
    """Composicao minima equivalente a do composition root, sem banco."""

    path: Path
    store: ConfigFileStore
    registry: RuntimeRegistry
    service: AdminConfigService
    factory: TrackingFactory
    initial: Runtime

    @property
    def initial_adapter(self) -> CountingAdapter:
        return cast(CountingAdapter, self.initial.adapter)

    def read(self) -> bytes:
        return self.path.read_bytes()

    def document(self) -> MaskingFileConfig:
        return parse_document(self.read())


def build_harness(
    directory: Path,
    *,
    document: bytes = ADOPTED_CONFIG,
    hooks: FilesystemHooks | None = None,
    factory: TrackingFactory | None = None,
    store_class: type[ConfigFileStore] = ConfigFileStore,
) -> Harness:
    path = directory / "masking.yaml"
    path.write_bytes(document)

    store = store_class.open(path, hooks=hooks)
    snapshot = store.read_snapshot()
    bundle = load_config_bundle_text(snapshot.data.decode("utf-8"))
    used = factory if factory is not None else TrackingFactory()

    engine = MaskingEngine(bundle.gateway.masking)
    runtime = Runtime(
        revision=bundle.file_config.revision,
        file_config=bundle.file_config,
        config=bundle.gateway,
        engine=engine,
        adapter=used(config=bundle.gateway, engine=engine),
    )
    registry = RuntimeRegistry(runtime)
    return Harness(
        path=path,
        store=store,
        registry=registry,
        service=AdminConfigService(
            store=store,
            registry=registry,
            adapter_factory=used,
            reference_digest=snapshot.digest,
        ),
        factory=used,
        initial=runtime,
    )


HarnessFactory = Callable[..., Harness]


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[HarnessFactory]:
    """Fabrica de harnesses com fechamento garantido na ordem da secao 9.2."""
    created: list[Harness] = []

    def make(**kwargs: Any) -> Harness:
        built = build_harness(tmp_path, **kwargs)
        created.append(built)
        return built

    yield make

    for built in created:
        built.service.close()
        built.registry.close_all()
        built.store.close()


def set_max_rows(value: int) -> Callable[[MaskingFileConfig], Mapping[str, Any]]:
    """Mutacao minima e observavel: muda um limite e nada mais."""

    def mutation(document: MaskingFileConfig) -> Mapping[str, Any]:
        payload: dict[str, Any] = document.model_dump(mode="json")
        payload["database"]["max_rows"] = value
        return payload

    return mutation


def identity(document: MaskingFileConfig) -> Mapping[str, Any]:
    payload: dict[str, Any] = document.model_dump(mode="json")
    return payload


def assign_ids(document: MaskingFileConfig) -> Mapping[str, Any]:
    """O que a adocao da Etapa 9 fara: atribuir ID a todo item.

    Aqui ela e so uma mutacao de teste. A operacao `config:adopt` completa —
    `confirm_comment_loss`, IDs aleatorios e backup dos bytes originais — nao
    pertence a Etapa 6; o que pertence e a pre-condicao assimetrica do passo 1.
    """
    payload: dict[str, Any] = document.model_dump(mode="json")
    for index, rule in enumerate(payload["masking"]):
        rule["id"] = f"rul_{index:032x}"
    for index, item in enumerate(payload["exceptions"]):
        item["id"] = f"exc_{index:032x}"
    return payload


def failing(_document: MaskingFileConfig) -> Mapping[str, Any]:
    raise RuntimeError(f"{SENSITIVE_DSN} {SENSITIVE_SQL} {SENSITIVE_VALUE}")


def invalid_document(document: MaskingFileConfig) -> Mapping[str, Any]:
    payload: dict[str, Any] = document.model_dump(mode="json")
    payload["database"]["max_rows"] = 0  # abaixo do minimo do schema
    return payload


def unknown_transformer(document: MaskingFileConfig) -> Mapping[str, Any]:
    payload: dict[str, Any] = document.model_dump(mode="json")
    payload["masking"][0]["transformer"] = "nao_existe"
    return payload


def broken_regex(document: MaskingFileConfig) -> Mapping[str, Any]:
    payload: dict[str, Any] = document.model_dump(mode="json")
    payload["masking"][0]["transformer"] = "regex"
    payload["masking"][0]["config"] = {"pattern": "(", "replacement": "x"}
    return payload


# --------------------------------------------------------------------------
# Mutacoes hostis: o callback e codigo do plano administrativo, mas nada
# impede que ele altere o objeto que recebeu. `frozen=True` do Pydantic
# impede REATRIBUIR um campo; as listas e dicionarios de dentro continuam
# mutaveis. Se o documento entregue fosse o do runtime publicado, uma mutacao
# que falhasse ainda assim o corromperia — e a escrita seguinte, valida e sem
# relacao com ela, persistiria a corrupcao e publicaria um engine sem regras.
# --------------------------------------------------------------------------


def strip_masking(document: MaskingFileConfig) -> Mapping[str, Any]:
    document.masking.clear()
    raise RuntimeError(SENSITIVE_VALUE)


def strip_exceptions(document: MaskingFileConfig) -> Mapping[str, Any]:
    document.exceptions.clear()
    raise RuntimeError(SENSITIVE_VALUE)


def strip_allowed_pg_functions(document: MaskingFileConfig) -> Mapping[str, Any]:
    document.sql.allowed_pg_functions.clear()
    document.sql.allowed_pg_functions.append("pg_read_file")
    raise RuntimeError(SENSITIVE_VALUE)


def rewrite_rule_config(document: MaskingFileConfig) -> Mapping[str, Any]:
    document.masking[0].config["value"] = SENSITIVE_VALUE
    document.masking[0].config["extra"] = SENSITIVE_DSN
    raise RuntimeError(SENSITIVE_VALUE)


def strip_everything_but_return_a_valid_document(
    document: MaskingFileConfig,
) -> Mapping[str, Any]:
    """Corrompe o documento recebido e ainda assim devolve um payload valido.

    Serve para levar a operacao ate a conexao: a falha passa a acontecer com um
    candidato ja construido, e nao antes dele.
    """
    payload: dict[str, Any] = document.model_dump(mode="json")
    document.masking.clear()
    document.exceptions.clear()
    document.sql.allowed_pg_functions.clear()
    return payload


# --------------------------------------------------------------------------
# 12.1 — concorrencia administrativa
# --------------------------------------------------------------------------


class TestCriticalSection:
    def test_parallel_writes_with_the_same_expected_revision_have_one_winner(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness()
        workers = 12
        barrier = threading.Barrier(workers)
        guard = threading.Lock()
        winners: list[int] = []
        conflicts: list[AdminError] = []

        def attempt(index: int) -> None:
            barrier.wait()
            try:
                state.service.apply(set_max_rows(100 + index), expected_revision=1)
            except AdminError as exc:
                with guard:
                    conflicts.append(exc)
            else:
                with guard:
                    winners.append(index)

        threads = [threading.Thread(target=attempt, args=(index,)) for index in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert not any(thread.is_alive() for thread in threads)
        assert len(winners) == 1
        assert len(conflicts) == workers - 1
        assert {exc.category for exc in conflicts} == {AdminErrorCategory.REVISION_CONFLICT}
        assert {exc.current_revision for exc in conflicts} == {2}

        assert state.service.revision == 2
        document = state.document()
        assert document.revision == 2
        assert document.database.max_rows == 100 + winners[0]
        # Nenhum perdedor construiu candidato: o passo 2 vem antes do passo 6.
        assert state.factory.builds == 2

    def test_concurrent_different_writes_never_produce_a_mixed_document(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness()
        values = [11, 22, 33, 44]
        allowed = {10, *values}
        stop = threading.Event()
        observed: list[int] = []
        reader_failures: list[BaseException] = []
        applied = 0
        guard = threading.Lock()

        def write(value: int) -> None:
            nonlocal applied
            deadline = time.monotonic() + 30
            successes = 0
            while successes < 3 and time.monotonic() < deadline:
                try:
                    state.service.apply(
                        set_max_rows(value),
                        expected_revision=state.service.revision,
                    )
                except AdminError:
                    # Conflito com outro escritor, ou — so no Windows — um
                    # `replace` recusado enquanto o leitor mantem o destino
                    # aberto. Ambos sao pre-commit e nao mudam nada.
                    continue
                successes += 1
                with guard:
                    applied += 1

        def read() -> None:
            try:
                while not stop.is_set():
                    try:
                        data = state.read()
                    except PermissionError:
                        # No Windows uma abertura pode perder a corrida curta
                        # com ReplaceFile; nao ha meio-arquivo a observar.
                        time.sleep(0.001)
                        continue
                    document = parse_document(data)
                    observed.append(document.database.max_rows)
                    time.sleep(0.001)
            except BaseException as exc:  # guardado para a thread principal
                reader_failures.append(exc)

        reader = threading.Thread(target=read)
        reader.start()
        writers = [threading.Thread(target=write, args=(value,)) for value in values]
        for thread in writers:
            thread.start()
        for thread in writers:
            thread.join(timeout=60)
        stop.set()
        reader.join(timeout=10)

        assert not reader.is_alive()
        assert reader_failures == []
        assert applied > 0
        assert observed
        # Todo documento lido e valido e vem de UMA operacao — nunca metade de
        # uma com metade de outra.
        assert set(observed) <= allowed
        assert state.service.revision == 1 + applied

    def test_writes_do_not_interrupt_queries_in_flight(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness()
        stop = threading.Event()
        never_closed_while_used: list[bool] = []
        query_failures: list[BaseException] = []
        reloads = 0

        def query() -> None:
            try:
                while not stop.is_set():
                    with state.registry.borrow() as runtime:
                        adapter = cast(CountingAdapter, runtime.adapter)
                        adapter.connect()
                        # Enquanto a referencia esta adquirida, o adapter dela
                        # nao pode ter sido fechado.
                        never_closed_while_used.append(adapter.close_calls == 0)
            except BaseException as exc:  # guardado para a thread principal
                query_failures.append(exc)

        readers = [threading.Thread(target=query) for _ in range(4)]
        for thread in readers:
            thread.start()

        deadline = time.monotonic() + 20
        while reloads < 10 and time.monotonic() < deadline:
            try:
                state.service.apply(
                    set_max_rows(100 + reloads),
                    expected_revision=state.service.revision,
                )
            except AdminError as exc:
                # Um aposentado ainda em uso recusa o reload; nunca derruba
                # uma query.
                assert exc.category is AdminErrorCategory.RELOAD_BUSY
                continue
            reloads += 1

        stop.set()
        for thread in readers:
            thread.join(timeout=10)

        assert not any(thread.is_alive() for thread in readers)
        assert query_failures == []
        assert reloads > 0
        assert never_closed_while_used
        assert all(never_closed_while_used)

        state.registry.close_all()
        assert all(adapter.close_calls == 1 for adapter in state.factory.adapters)


# --------------------------------------------------------------------------
# 7.4, passos 1 a 4 — tudo antes de construir e conectar
# --------------------------------------------------------------------------


class TestPreconditions:
    def test_revision_conflict_changes_nothing(self, harness: HarnessFactory) -> None:
        state = harness()
        before = state.read()
        digest = state.service.reference_digest
        published = state.registry.current

        with pytest.raises(AdminError) as raised:
            state.service.apply(set_max_rows(99), expected_revision=7)

        assert raised.value.category is AdminErrorCategory.REVISION_CONFLICT
        assert raised.value.current_revision == 1
        assert not raised.value.applied
        assert state.read() == before
        assert state.registry.current is published
        assert state.service.reference_digest == digest
        assert state.factory.builds == 1

    def test_write_before_adoption_is_refused(self, harness: HarnessFactory) -> None:
        state = harness(document=UNADOPTED_CONFIG)
        before = state.read()

        with pytest.raises(AdminError) as raised:
            state.service.apply(set_max_rows(99), expected_revision=0)

        assert raised.value.category is AdminErrorCategory.CONFIG_NOT_ADOPTED
        assert not state.service.adopted
        assert state.read() == before
        assert state.factory.builds == 1

    def test_adopt_over_an_adopted_configuration_is_refused(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness()
        before = state.read()

        with pytest.raises(AdminError) as raised:
            state.service.apply(identity, expected_revision=1, operation=AdminOperation.ADOPT)

        assert raised.value.category is AdminErrorCategory.CONFIG_ALREADY_ADOPTED
        assert state.read() == before
        assert state.service.revision == 1
        assert state.factory.builds == 1

    def test_adopt_from_a_non_zero_expected_revision_is_a_conflict(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness(document=UNADOPTED_CONFIG)

        with pytest.raises(AdminError) as raised:
            state.service.apply(identity, expected_revision=3, operation=AdminOperation.ADOPT)

        assert raised.value.category is AdminErrorCategory.REVISION_CONFLICT
        assert raised.value.current_revision == 0

    def test_adopt_publishes_revision_one_from_the_unadopted_state(
        self,
        harness: HarnessFactory,
    ) -> None:
        """A pre-condicao do passo 1; a adocao completa e da Etapa 9."""
        state = harness(document=UNADOPTED_CONFIG)

        result = state.service.apply(
            assign_ids,
            expected_revision=0,
            operation=AdminOperation.ADOPT,
        )

        assert result.revision == 1
        assert result.applied
        assert state.service.adopted
        assert state.document().revision == 1

    def test_external_edit_before_the_operation_is_out_of_sync(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness()
        published = state.registry.current
        state.path.write_bytes(EXTERNAL_EDIT)

        with pytest.raises(AdminError) as raised:
            state.service.apply(set_max_rows(99), expected_revision=1)

        assert raised.value.category is AdminErrorCategory.CONFIG_OUT_OF_SYNC
        assert not raised.value.applied
        # O trabalho do editor externo e preservado, nao sobrescrito.
        assert state.read() == EXTERNAL_EDIT
        assert state.registry.current is published
        assert state.factory.builds == 1

    def test_reload_busy_refuses_before_building_or_connecting(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness()
        held = state.registry.acquire()
        try:
            state.service.apply(set_max_rows(50), expected_revision=1)
            assert state.registry.retired_in_use() == 1

            builds = state.factory.builds
            connects = state.factory.connects
            before = state.read()

            with pytest.raises(AdminError) as raised:
                state.service.apply(set_max_rows(60), expected_revision=2)

            assert raised.value.category is AdminErrorCategory.RELOAD_BUSY
            assert not raised.value.applied
            # A prova por contador: nenhum candidato construido, nenhuma
            # conexao nova aberta para uma operacao ja condenada.
            assert state.factory.builds == builds
            assert state.factory.connects == connects
            assert state.read() == before
            assert state.service.revision == 2
        finally:
            state.registry.release(held)

        assert state.registry.retired_in_use() == 0
        assert state.initial_adapter.close_calls == 1
        # Liberado o aposentado, o reload volta a ser possivel.
        assert state.service.apply(set_max_rows(70), expected_revision=2).revision == 3

    def test_revision_is_checked_before_the_retired_limit(
        self,
        harness: HarnessFactory,
    ) -> None:
        """A ordem dos passos e observavel: 2 vem antes de 4."""
        state = harness()
        held = state.registry.acquire()
        try:
            state.service.apply(set_max_rows(50), expected_revision=1)
            with pytest.raises(AdminError) as raised:
                state.service.apply(set_max_rows(60), expected_revision=1)
            assert raised.value.category is AdminErrorCategory.REVISION_CONFLICT
        finally:
            state.registry.release(held)


# --------------------------------------------------------------------------
# 12.4 — falhas ANTES do `os.replace`
# --------------------------------------------------------------------------


class TestPreCommitFailures:
    @pytest.mark.parametrize(
        ("mutation", "category"),
        [
            (failing, AdminErrorCategory.CONFIG_INVALID),
            (invalid_document, AdminErrorCategory.CONFIG_INVALID),
            (unknown_transformer, AdminErrorCategory.CONFIG_RELOAD_ERROR),
            (broken_regex, AdminErrorCategory.CONFIG_RELOAD_ERROR),
        ],
    )
    def test_document_failures_leave_everything_untouched(
        self,
        harness: HarnessFactory,
        mutation: Callable[[MaskingFileConfig], Mapping[str, Any]],
        category: AdminErrorCategory,
    ) -> None:
        state = harness()
        before = state.read()
        digest = state.service.reference_digest
        published = state.registry.current

        with pytest.raises(AdminError) as raised:
            state.service.apply(mutation, expected_revision=1)

        assert raised.value.category is category
        assert not raised.value.applied
        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None
        assert state.read() == before
        assert state.registry.current is published
        assert state.service.reference_digest == digest
        assert state.service.revision == 1
        # Nem a validacao nem a compilacao chegam a criar adapter: os dois
        # falham antes do passo que o constroi.
        assert state.factory.builds == 1
        assert state.initial_adapter.close_calls == 0

    def test_adapter_construction_failure_is_a_reload_error(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness()
        published = state.registry.current
        before = state.read()
        state.factory.build_error = RuntimeError(f"{SENSITIVE_DSN} {SENSITIVE_VALUE}")

        with pytest.raises(AdminError) as raised:
            state.service.apply(set_max_rows(99), expected_revision=1)

        assert raised.value.category is AdminErrorCategory.CONFIG_RELOAD_ERROR
        assert state.read() == before
        assert state.registry.current is published
        assert state.factory.builds == 1

    def test_connect_failure_closes_the_candidate_exactly_once(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness()
        published = state.registry.current
        before = state.read()
        digest = state.service.reference_digest
        state.factory.connect_error = RuntimeError(f"{SENSITIVE_DSN} {SENSITIVE_SQL}")

        with pytest.raises(AdminError) as raised:
            state.service.apply(set_max_rows(99), expected_revision=1)

        assert raised.value.category is AdminErrorCategory.CONFIG_RELOAD_ERROR
        assert not raised.value.applied
        assert state.factory.builds == 2
        candidate = state.factory.adapters[1]
        assert candidate.connect_calls == 1
        assert candidate.close_calls == 1
        assert state.initial_adapter.close_calls == 0
        assert state.read() == before
        assert state.registry.current is published
        assert state.service.reference_digest == digest

    @pytest.mark.parametrize("failing_hook", ["temp_token", "file_fsync", "replace"])
    def test_filesystem_failures_are_pre_commit(
        self,
        tmp_path: Path,
        harness: HarnessFactory,
        failing_hook: str,
    ) -> None:
        # Nao e segredo: e o sufixo hexadecimal do nome do temporario, fixado
        # para que o teste consiga colidir com ele de proposito.
        fixed_token = "0123456789abcdef"  # noqa: S105
        hooks_by_name = {
            # Colisao de `O_EXCL`: o temporario nao pode ser criado.
            "temp_token": FilesystemHooks(temp_token=lambda: fixed_token),
            "file_fsync": FilesystemHooks(
                file_fsync=_raise_os_error,
            ),
            "replace": FilesystemHooks(replace=lambda _source, _destination: _raise_os_error(0)),
        }
        state = harness(hooks=hooks_by_name[failing_hook])
        if failing_hook == "temp_token":
            collision = tmp_path / f".masking.yaml.tmp.{os.getpid()}.{fixed_token}"
            collision.write_bytes(b"terceiro")

        before = state.read()
        digest = state.service.reference_digest
        published = state.registry.current

        with pytest.raises(AdminError) as raised:
            state.service.apply(set_max_rows(99), expected_revision=1)

        assert raised.value.category is AdminErrorCategory.CONFIG_WRITE_ERROR
        assert not raised.value.applied
        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None
        # Byte a byte: o arquivo anterior nao foi tocado.
        assert state.read() == before
        assert state.registry.current is published
        assert state.service.reference_digest == digest
        assert state.service.revision == 1
        assert state.factory.builds == 2
        assert state.factory.adapters[1].close_calls == 1
        assert state.initial_adapter.close_calls == 0

    def test_unreadable_configuration_is_a_write_error(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness()
        published = state.registry.current
        state.path.unlink()

        with pytest.raises(AdminError) as raised:
            state.service.apply(set_max_rows(99), expected_revision=1)

        assert raised.value.category is AdminErrorCategory.CONFIG_WRITE_ERROR
        assert not raised.value.applied
        assert state.registry.current is published
        assert state.factory.builds == 1

    def test_external_edit_during_the_operation_is_caught_before_replace(
        self,
        tmp_path: Path,
        harness: HarnessFactory,
    ) -> None:
        """A corrida real da secao 7.5.1: edicao entre a 1a verificacao e o replace."""
        edits: list[str] = []
        config_path = tmp_path / "masking.yaml"

        def edit_between_checks(point: object) -> None:
            edits.append(str(point))
            if str(point) == "pre_replace":
                config_path.write_bytes(EXTERNAL_EDIT)

        state = harness(hooks=FilesystemHooks(before_digest_check=edit_between_checks))
        published = state.registry.current
        digest = state.service.reference_digest

        with pytest.raises(AdminError) as raised:
            state.service.apply(set_max_rows(99), expected_revision=1)

        assert raised.value.category is AdminErrorCategory.CONFIG_OUT_OF_SYNC
        assert not raised.value.applied
        assert edits == ["initial", "pre_replace"]
        # O conteudo do editor e preservado; o candidato, fechado.
        assert state.read() == EXTERNAL_EDIT
        assert state.registry.current is published
        assert state.service.reference_digest == digest
        assert state.factory.adapters[1].close_calls == 1


def _raise_os_error(_descriptor: int) -> None:
    raise OSError(f"{SENSITIVE_DSN} {SENSITIVE_SQL} {SENSITIVE_VALUE}")


# --------------------------------------------------------------------------
# 7.6 — depois do `os.replace`
# --------------------------------------------------------------------------


class TestDurability:
    def test_durability_failure_publishes_the_new_runtime(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness(store_class=DurabilityFailingStore)
        published = state.registry.current

        with pytest.raises(AdminError) as raised:
            state.service.apply(set_max_rows(99), expected_revision=1)

        assert raised.value.category is AdminErrorCategory.CONFIG_DURABILITY_ERROR
        # A unica categoria que afirma que a mudanca valeu.
        assert raised.value.applied
        assert raised.value.current_revision == 2
        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None

        # Arquivo novo, runtime novo, digest novo, revision nova.
        document = state.document()
        assert document.revision == 2
        assert document.database.max_rows == 99
        assert state.registry.current is not published
        assert state.registry.current.revision == 2
        assert state.service.revision == 2
        assert state.service.reference_digest == digest_bytes(state.read())
        # O candidato foi publicado, nao fechado; o antigo foi aposentado e
        # fechado uma unica vez.
        assert state.factory.adapters[1].close_calls == 0
        assert state.initial_adapter.close_calls == 1

    def test_blind_retry_after_durability_failure_conflicts(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness(store_class=DurabilityFailingStore)
        with pytest.raises(AdminError):
            state.service.apply(set_max_rows(99), expected_revision=1)
        applied = state.read()

        with pytest.raises(AdminError) as raised:
            state.service.apply(set_max_rows(123), expected_revision=1)

        assert raised.value.category is AdminErrorCategory.REVISION_CONFLICT
        assert raised.value.current_revision == 2
        assert not raised.value.applied
        assert state.read() == applied

    @pytest.mark.skipif(os.name != "posix", reason="fsync de diretorio somente no POSIX")
    def test_real_directory_fsync_failure_is_post_commit_on_posix(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness(hooks=FilesystemHooks(directory_fsync=_raise_os_error))

        with pytest.raises(AdminError) as raised:
            state.service.apply(set_max_rows(99), expected_revision=1)

        assert raised.value.category is AdminErrorCategory.CONFIG_DURABILITY_ERROR
        assert raised.value.applied
        assert raised.value.current_revision == 2
        assert state.document().database.max_rows == 99
        assert state.registry.current.revision == 2

    @pytest.mark.skipif(os.name != "nt", reason="omissao de fsync de diretorio no Windows")
    def test_directory_fsync_is_omitted_on_windows(self, harness: HarnessFactory) -> None:
        """A omissao e AFIRMADA, nunca simulada como sucesso (secao 12.5)."""
        calls = 0

        def never(_descriptor: int) -> None:
            nonlocal calls
            calls += 1
            raise OSError("nao deve executar")

        state = harness(hooks=FilesystemHooks(directory_fsync=never))
        result = state.service.apply(set_max_rows(99), expected_revision=1)

        assert calls == 0
        assert not result.directory_fsync_performed
        assert result.applied
        assert state.document().database.max_rows == 99


# --------------------------------------------------------------------------
# 12.3 aplicado ao fluxo — swap, refcount e aposentadoria
# --------------------------------------------------------------------------


class TestSwapLifecycle:
    def test_success_publishes_a_whole_new_runtime(self, harness: HarnessFactory) -> None:
        state = harness()
        published = state.registry.current

        result = state.service.apply(set_max_rows(99), expected_revision=1)

        assert result.revision == 2
        assert result.applied
        candidate = state.registry.current
        assert candidate is not published
        assert candidate.revision == 2
        assert candidate.config.database.max_rows == 99
        assert candidate.file_config.revision == 2
        # Nada e alterado em-place: o runtime antigo continua o que era.
        assert published.config.database.max_rows == 10
        assert published.revision == 1
        # Ocioso no swap: fechado ali mesmo, exatamente uma vez.
        assert state.initial_adapter.close_calls == 1
        assert state.factory.adapters[1].close_calls == 0

    def test_query_in_flight_finishes_on_the_old_runtime(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness()
        held = state.registry.acquire()

        state.service.apply(set_max_rows(99), expected_revision=1)

        # A query em voo continua com o runtime antigo, inteiro e aberto.
        assert held is state.initial
        assert held.config.database.max_rows == 10
        assert state.initial_adapter.close_calls == 0
        # Uma query nova ja pega o novo.
        assert state.registry.current.config.database.max_rows == 99

        state.registry.release(held)
        assert state.initial_adapter.close_calls == 1

    def test_reference_digest_matches_the_bytes_of_the_published_runtime(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness()
        state.service.apply(set_max_rows(99), expected_revision=1)

        data = state.read()
        assert state.service.reference_digest == digest_bytes(data)
        # E os bytes em disco reproduzem exatamente o documento publicado.
        assert parse_document(data) == state.registry.current.file_config
        assert render_document(state.registry.current.file_config).data == data

    def test_read_only_fields_survive_a_whole_document_write(
        self,
        harness: HarnessFactory,
    ) -> None:
        """`allowed_pg_functions` continua igual em conteudo e em ordem (11.3)."""
        state = harness()
        before = state.registry.current.file_config.sql.allowed_pg_functions

        state.service.apply(set_max_rows(99), expected_revision=1)

        assert state.registry.current.file_config.sql.allowed_pg_functions == before
        assert state.document().sql.allowed_pg_functions == ["pg_typeof", "pg_backend_pid"]

    def test_many_reloads_leak_no_adapter(self, harness: HarnessFactory) -> None:
        state = harness()
        for revision in range(1, 16):
            state.service.apply(set_max_rows(100 + revision), expected_revision=revision)

        assert state.service.revision == 16
        assert state.factory.builds == 16
        # Todos fechados menos o publicado.
        assert state.factory.closes == 15
        state.registry.close_all()
        assert all(adapter.close_calls == 1 for adapter in state.factory.adapters)

    def test_operations_after_close_are_refused(self, harness: HarnessFactory) -> None:
        state = harness()
        before = state.read()
        state.service.close()

        with pytest.raises(AdminError) as raised:
            state.service.apply(set_max_rows(99), expected_revision=1)

        assert raised.value.category is AdminErrorCategory.INTERNAL_ERROR
        assert not raised.value.applied
        assert state.read() == before
        assert state.factory.builds == 1


# --------------------------------------------------------------------------
# Isolamento do runtime publicado contra a mutacao
# --------------------------------------------------------------------------


def assert_published_is_intact(state: Harness, published: Runtime, before: bytes) -> None:
    """O runtime publicado nao mudou — nem de identidade, nem de conteudo."""
    # Arquivo byte a byte, e a MESMA referencia publicada.
    assert state.read() == before
    assert state.registry.current is published
    assert state.service.revision == 1
    assert state.service.reference_digest == digest_bytes(before)

    # O documento administrativo do runtime, campo a campo.
    document = published.file_config
    assert [rule.match for rule in document.masking] == ["cpf"]
    assert document.masking[0].transformer == "fixed"
    assert document.masking[0].config == {"value": "[REDACTED]"}
    assert [item.match for item in document.exceptions] == ["tipo_cpf"]
    assert document.sql.allowed_pg_functions == ["pg_typeof", "pg_backend_pid"]
    assert document.database.max_rows == 10
    assert document.revision == 1

    # E os objetos compilados que dependem dele: uma regra a menos aqui e
    # masking desligado.
    assert len(published.engine.policy.rules) == 1
    assert len(published.engine.policy.exceptions) == 1
    assert len(published.config.masking.rules) == 1
    assert "pg_typeof" in published.config.sql.allowed_pg_functions
    assert "pg_read_file" not in published.config.sql.allowed_pg_functions


class TestPublishedRuntimeIsolation:
    """Regressao: o callback nao pode alcancar o runtime publicado.

    O rollback pre-commit vale para o arquivo, para a identidade do runtime e
    para o CONTEUDO dele. Sem isso, uma mutacao que falha ainda desliga o
    masking na escrita seguinte.
    """

    @pytest.mark.parametrize(
        "mutation",
        [strip_masking, strip_exceptions, strip_allowed_pg_functions, rewrite_rule_config],
    )
    def test_hostile_mutation_that_fails_leaves_the_runtime_untouched(
        self,
        harness: HarnessFactory,
        mutation: Callable[[MaskingFileConfig], Mapping[str, Any]],
    ) -> None:
        state = harness()
        published = state.registry.current
        before = state.read()

        with pytest.raises(AdminError) as raised:
            state.service.apply(mutation, expected_revision=1)

        assert raised.value.category is AdminErrorCategory.CONFIG_INVALID
        assert not raised.value.applied
        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None
        assert_published_is_intact(state, published, before)
        # A falha e no passo 5: nenhum candidato chegou a ser construido.
        assert state.factory.builds == 1
        assert state.initial_adapter.close_calls == 0

    def test_hostile_mutation_that_reaches_the_connection_closes_only_the_candidate(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness()
        published = state.registry.current
        before = state.read()
        state.factory.connect_error = RuntimeError(SENSITIVE_DSN)

        with pytest.raises(AdminError) as raised:
            state.service.apply(
                strip_everything_but_return_a_valid_document,
                expected_revision=1,
            )

        assert raised.value.category is AdminErrorCategory.CONFIG_RELOAD_ERROR
        assert_published_is_intact(state, published, before)
        # Aqui o candidato existiu: construido uma vez, fechado uma vez.
        assert state.factory.builds == 2
        assert state.factory.adapters[1].close_calls == 1
        assert state.initial_adapter.close_calls == 0

    @pytest.mark.parametrize(
        "mutation",
        [strip_masking, strip_exceptions, strip_allowed_pg_functions, rewrite_rule_config],
    )
    def test_a_later_unrelated_write_persists_no_residue(
        self,
        harness: HarnessFactory,
        mutation: Callable[[MaskingFileConfig], Mapping[str, Any]],
    ) -> None:
        """O dano so apareceria aqui: a escrita seguinte parte do documento."""
        state = harness()
        with pytest.raises(AdminError):
            state.service.apply(mutation, expected_revision=1)

        result = state.service.apply(set_max_rows(99), expected_revision=1)

        assert result.revision == 2
        persisted = state.document()
        assert [rule.match for rule in persisted.masking] == ["cpf"]
        assert persisted.masking[0].config == {"value": "[REDACTED]"}
        assert [item.match for item in persisted.exceptions] == ["tipo_cpf"]
        assert persisted.sql.allowed_pg_functions == ["pg_typeof", "pg_backend_pid"]
        # Somente a mudanca pedida por ESTA operacao foi persistida.
        assert persisted.database.max_rows == 99
        # E o engine publicado continua com a regra: masking nao foi desligado.
        published = state.registry.current
        assert len(published.engine.policy.rules) == 1
        assert "pg_read_file" not in published.config.sql.allowed_pg_functions

    def test_mutating_the_exposed_document_never_reaches_the_runtime(
        self,
        harness: HarnessFactory,
    ) -> None:
        state = harness()
        published = state.registry.current
        before = state.read()

        exposed = state.service.document
        assert exposed is not published.file_config
        exposed.masking.clear()
        exposed.exceptions.clear()
        exposed.sql.allowed_pg_functions.clear()

        assert_published_is_intact(state, published, before)
        # E uma leitura seguinte nao herda o dano da anterior.
        assert [rule.match for rule in state.service.document.masking] == ["cpf"]

    def test_the_candidate_document_is_the_one_the_bytes_produce(
        self,
        harness: HarnessFactory,
    ) -> None:
        """D-055: os bytes persistidos originam o documento do runtime novo."""
        state = harness()
        state.service.apply(set_max_rows(99), expected_revision=1)

        data = state.read()
        published = state.registry.current
        assert published.file_config == parse_document(data)
        # Nao e so igualdade de valor: o documento publicado nao compartilha
        # objeto nenhum com quem chamou a operacao.
        assert published.file_config is not parse_document(data)
        assert state.service.reference_digest == digest_bytes(data)


# --------------------------------------------------------------------------
# 12.6 — vazamento
# --------------------------------------------------------------------------


class TestLeakage:
    @pytest.mark.parametrize("category", list(AdminErrorCategory))
    def test_error_text_and_repr_are_fixed_per_category(
        self,
        category: AdminErrorCategory,
    ) -> None:
        error = AdminError(category, current_revision=3)
        rendered = f"{error!s} {error!r}"

        for sensitive in (
            SENSITIVE_DSN,
            SENSITIVE_SQL,
            SENSITIVE_VALUE,
            SENSITIVE_PATH_MARKER,
            "masking.yaml",
            "Traceback",
        ):
            assert sensitive not in rendered
        assert category.value in rendered

    def test_failure_never_carries_the_original_message(
        self,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
        harness: HarnessFactory,
    ) -> None:
        state = harness()
        state.factory.connect_error = RuntimeError(
            f"{SENSITIVE_DSN} {SENSITIVE_SQL} {SENSITIVE_VALUE}"
        )

        with caplog.at_level(logging.DEBUG), pytest.raises(AdminError) as raised:
            state.service.apply(set_max_rows(99), expected_revision=1)

        rendered = f"{raised.value!s} {raised.value!r} {raised.value.args!r}"
        for sensitive in (SENSITIVE_DSN, SENSITIVE_SQL, SENSITIVE_VALUE):
            assert sensitive not in rendered
        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""
        assert caplog.records == []

    def test_service_repr_hides_path_digest_and_collaborators(
        self,
        tmp_path: Path,
    ) -> None:
        directory = tmp_path / SENSITIVE_PATH_MARKER
        directory.mkdir()
        state = build_harness(directory)
        try:
            rendered = repr(state.service)
            assert SENSITIVE_PATH_MARKER not in rendered
            assert state.service.reference_digest not in rendered
            assert rendered == "AdminConfigService(revision=1, closed=False)"
        finally:
            state.service.close()
            state.registry.close_all()
            state.store.close()

    def test_successful_operation_writes_nothing_to_stdout(
        self,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
        harness: HarnessFactory,
    ) -> None:
        state = harness()
        with caplog.at_level(logging.DEBUG):
            state.service.apply(set_max_rows(99), expected_revision=1)

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""
        assert caplog.records == []


# --------------------------------------------------------------------------
# Contra PostgreSQL real: o passo 7 conecta e verifica de verdade
# --------------------------------------------------------------------------

INTEGRATION_SCHEMA = "maskgw_fase7_etapa6"
INTEGRATION_TABLE = f"{INTEGRATION_SCHEMA}.cliente"
INTEGRATION_APP_NAME = "maskgw_fase7_etapa6_tests"
FICTITIOUS_CPF = "11122233344"

INTEGRATION_DDL = f"""
DROP SCHEMA IF EXISTS {INTEGRATION_SCHEMA} CASCADE;
CREATE SCHEMA {INTEGRATION_SCHEMA};
CREATE TABLE {INTEGRATION_TABLE} (id integer PRIMARY KEY, nome text, cpf text);
"""

# O nome da tabela e constante deste modulo; o unico valor e parametrizado.
INTEGRATION_INSERT = f"INSERT INTO {INTEGRATION_TABLE} VALUES (1, 'Maria Ficticia', %s)"  # noqa: S608


def integration_config(value: str) -> bytes:
    return f"""revision: 1
masking:
- match: cpf
  mode: contains
  case_sensitive: false
  transformer: fixed
  config:
    value: '{value}'
  id: {RULE_ID}
exceptions: []
database:
  statement_timeout_ms: 5000
  max_rows: 100
sql:
  allowed_pg_functions: []
  denied_functions: []
""".encode()


def replace_fixed_value(value: str) -> Callable[[MaskingFileConfig], Mapping[str, Any]]:
    def mutation(document: MaskingFileConfig) -> Mapping[str, Any]:
        payload: dict[str, Any] = document.model_dump(mode="json")
        payload["masking"][0]["config"]["value"] = value
        return payload

    return mutation


@pytest.mark.integration
class TestRealReload:
    """O que o duble nao prova: que o candidato conecta e passa nos checks."""

    @pytest.fixture
    def database(self, dsn: str) -> Iterator[str]:
        with psycopg.connect(dsn, autocommit=True) as setup:
            setup.execute(INTEGRATION_DDL)
            setup.execute(INTEGRATION_INSERT, [FICTITIOUS_CPF])
        yield dsn
        with psycopg.connect(dsn, autocommit=True) as teardown:
            teardown.execute(f"DROP SCHEMA IF EXISTS {INTEGRATION_SCHEMA} CASCADE")

    def live_sessions(self, dsn: str) -> int:
        """Conexoes abertas por esta aplicacao, vistas de fora pelo proprio banco."""
        with psycopg.connect(dsn, autocommit=True) as observer:
            row = observer.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE application_name = %s",
                [INTEGRATION_APP_NAME],
            ).fetchone()
        assert row is not None
        return int(row[0])

    def build(self, tmp_path: Path, database: str, value: str) -> tuple[Application, Path]:
        path = tmp_path / "masking.yaml"
        path.write_bytes(integration_config(value))
        conninfo = make_conninfo(database, application_name=INTEGRATION_APP_NAME)
        app = build_application(config_path=path, conninfo=conninfo, admin_enabled=True)
        return app, path

    def test_reload_publishes_the_new_policy_without_restart(
        self,
        tmp_path: Path,
        database: str,
    ) -> None:
        app, path = self.build(tmp_path, database, "[ANTES]")
        try:
            admin = app.admin
            assert admin is not None
            sql = f"SELECT cpf FROM {INTEGRATION_TABLE} ORDER BY id"  # noqa: S608
            assert app.gateway.query(sql).rows == [["[ANTES]"]]
            assert self.live_sessions(database) == 1

            result = admin.apply(replace_fixed_value("[DEPOIS]"), expected_revision=1)

            assert result.revision == 2
            assert result.applied
            # A politica nova vale para a proxima query, sem restart.
            assert app.gateway.query(sql).rows == [["[DEPOIS]"]]
            # O arquivo e o runtime concordam, e o digest e dos bytes exatos.
            assert parse_document(path.read_bytes()).revision == 2
            assert admin.reference_digest == digest_bytes(path.read_bytes())
            # O antigo estava ocioso no swap: foi fechado ali mesmo, e o total
            # de conexoes nao cresceu.
            assert self.live_sessions(database) == 1
        finally:
            app.close()

        assert self.live_sessions(database) == 0

    def test_invalid_candidate_keeps_the_published_runtime_serving(
        self,
        tmp_path: Path,
        database: str,
    ) -> None:
        app, path = self.build(tmp_path, database, "[ANTES]")
        try:
            admin = app.admin
            assert admin is not None
            before = path.read_bytes()
            published = app.registry.current
            sql = f"SELECT cpf FROM {INTEGRATION_TABLE} ORDER BY id"  # noqa: S608

            with pytest.raises(AdminError) as raised:
                admin.apply(unknown_transformer, expected_revision=1)

            assert raised.value.category is AdminErrorCategory.CONFIG_RELOAD_ERROR
            assert path.read_bytes() == before
            assert app.registry.current is published
            assert app.gateway.query(sql).rows == [["[ANTES]"]]
            assert self.live_sessions(database) == 1
        finally:
            app.close()
