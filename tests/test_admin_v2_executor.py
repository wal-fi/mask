"""Fase 9, Etapa 7 (D-108): fila administrativa dedicada e leitura selada da v2.

Regressoes pela porta HTTP real e pela traducao v2:

- leituras (status/list/get/policy) respondem enquanto uma escrita verifica;
- uma leitura no meio de persistencia -> publicacao (ou -> retirada) devolve UM
  selo coerente — o anterior —, nunca catalogo novo com geracao antiga;
- falha depois de um efeito possivel (publicacao, retirada, selagem) deixa as
  leituras indisponiveis (`CATALOG_BLOCKED`) e o servico bloqueado, em vez de
  uma resposta normal mista.

Todo caso com risco de travar tem watchdog independente; as barreiras sao
`Event`s soltos no `finally`, e as threads de teste recebem `join`.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from maskgw.admin.http.v2.audit import DatasourceAuditor
from maskgw.admin.http.v2.errors import DatasourceAdminError
from maskgw.admin.http.v2.operations import DatasourceAdmin
from maskgw.admin.http.v2.routes import _enqueue
from maskgw.admin.http.v2.schemas import DatasourceCreateRequest
from maskgw.audit.datasource import DatasourceOperationName
from maskgw.runtime.admin_work import AdminWorkQueue
from maskgw.runtime.datasources import CandidateReservation, DatasourceRegistry
from tests.admin_http_support import Reply
from tests.admin_v2_support import (
    ALIAS,
    SECRET,
    V2Harness,
    build_v2,
    create_body,
    update_body,
)


@pytest.fixture
def v2(tmp_path: Path) -> Iterator[V2Harness]:
    # Watchdog da fixture: cobre tambem a drenagem e o fechamento, e so e
    # cancelado DEPOIS deles.
    guard = _watchdog(120.0)
    harness = build_v2(tmp_path)
    try:
        harness.start()
        yield harness
    finally:
        harness.close()
        guard.cancel()


def _watchdog(seconds: float) -> threading.Timer:
    """Derruba o processo de teste se ele travar; falha visivel, sem hang."""
    timer = threading.Timer(seconds, lambda: os._exit(99))
    timer.daemon = True
    timer.start()
    return timer


def _background(call: Callable[[], Reply]) -> tuple[threading.Thread, list[Reply]]:
    box: list[Reply] = []

    def run() -> None:
        box.append(call())

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, box


def _hold(
    monkeypatch: pytest.MonkeyPatch, owner: type, name: str
) -> tuple[threading.Event, threading.Event]:
    """Barreira antes de `owner.name`: sinaliza `reached`, espera `release`."""
    reached, release = threading.Event(), threading.Event()
    original = getattr(owner, name)

    def held(self: Any, *args: Any, **kwargs: Any) -> Any:
        reached.set()
        release.wait(20)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(owner, name, held)
    return reached, release


# ---- responsividade -----------------------------------------------------------


def test_reads_stay_responsive_while_a_write_verifies(v2: V2Harness) -> None:
    created = v2.create()
    datasource_id = created["datasource_id"]
    revision = v2.store.revision
    gate = threading.Event()
    v2.factory.connect_gate = gate
    v2.factory.connect_started.clear()
    guard = _watchdog(60.0)
    writer, box = _background(
        lambda: v2.call(
            "PUT",
            f"/admin/v2/datasources/{datasource_id}",
            update_body(created["datasource_revision"]),
            timeout=30,
        )
    )
    try:
        assert v2.factory.connect_started.wait(10), "a escrita chegou a verificar"
        for path in (
            "/admin/v2/status",
            "/admin/v2/datasources",
            f"/admin/v2/datasources/{datasource_id}",
            f"/admin/v2/datasources/{datasource_id}/policy",
        ):
            started = time.monotonic()
            reply = v2.call("GET", path, timeout=3)
            assert reply.status == 200, path
            assert time.monotonic() - started < 1.5, path
            if "catalog_revision" in reply.json():
                assert reply.json()["catalog_revision"] == revision
    finally:
        gate.set()
        writer.join(30)
        guard.cancel()
    assert not writer.is_alive()
    assert box[0].status == 200


# ---- selo coerente entre persistencia e publicacao/retirada ------------------


def test_read_between_persist_and_publish_sees_the_previous_seal(
    v2: V2Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = v2.store.revision
    reached, release = _hold(monkeypatch, CandidateReservation, "publish")
    guard = _watchdog(60.0)
    writer, box = _background(
        lambda: v2.call("POST", "/admin/v2/datasources", create_body(expected=before), timeout=30)
    )
    try:
        assert reached.wait(10), "persistiu e chegou a publicacao"
        assert v2.store.revision == before + 1, "o disco ja tem a revisao nova"
        listing = DatasourceAdmin(v2.runtime).list()
        # Nunca o catalogo novo com o datasource ainda sem geracao publicada.
        assert listing.catalog_revision == before
        assert listing.datasources == []
    finally:
        release.set()
        writer.join(30)
        guard.cancel()
    assert box[0].status == 200
    after = DatasourceAdmin(v2.runtime).list()
    assert after.catalog_revision == before + 1
    assert [item.runtime.published for item in after.datasources] == [True]


def test_read_between_persist_and_withdraw_sees_the_previous_seal(
    v2: V2Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = v2.create()
    datasource_id = created["datasource_id"]
    before = v2.store.revision
    reached, release = _hold(monkeypatch, DatasourceRegistry, "withdraw")
    guard = _watchdog(60.0)
    writer, box = _background(
        lambda: v2.call(
            "POST",
            f"/admin/v2/datasources/{datasource_id}:disable",
            {"expected_revision": created["datasource_revision"]},
            timeout=30,
        )
    )
    try:
        assert reached.wait(10), "persistiu e chegou a retirada"
        listing = DatasourceAdmin(v2.runtime).list()
        # Nunca "desabilitado no catalogo" com a geracao ainda publicada.
        assert listing.catalog_revision == before
        (item,) = listing.datasources
        assert item.enabled
        assert item.runtime.published
    finally:
        release.set()
        writer.join(30)
        guard.cancel()
    assert box[0].status == 200
    (item,) = DatasourceAdmin(v2.runtime).list().datasources
    assert not item.enabled
    assert not item.runtime.published


# ---- leituras nunca esperam o lock do store (DNS/filesystem) -----------------

_READS = ("status", "list", "get", "policy")


def _read(admin: DatasourceAdmin, name: str, datasource_id: str) -> object:
    if name == "status":
        return admin.status()
    if name == "list":
        return admin.list()
    if name == "get":
        return admin.get(datasource_id)
    return admin.policy(datasource_id)


def _completes_quickly(call: Callable[[], object], seconds: float = 0.5) -> object:
    """Roda `call` numa thread e exige conclusao no prazo (sem esperar lock)."""
    box: list[object] = []
    thread = threading.Thread(target=lambda: box.append(call()), daemon=True)
    thread.start()
    thread.join(seconds)
    assert not thread.is_alive(), "a leitura esperou um lock do store"
    return box[0]


def _create_direct(harness: V2Harness, *, enabled: bool = True, alias: str = "crm") -> str:
    from maskgw.runtime.datasource_service import DatasourceWriteProbe  # noqa: PLC0415

    body = DatasourceCreateRequest.model_validate(
        create_body(expected=harness.store.revision, enabled=enabled, alias=alias)
    )
    return DatasourceAdmin(harness.runtime).create(body, DatasourceWriteProbe()).datasource_id


@pytest.mark.parametrize("name", _READS)
def test_reads_never_wait_on_the_store_lock_held_directly(tmp_path: Path, name: str) -> None:
    harness = build_v2(tmp_path)
    held, release = threading.Event(), threading.Event()
    guard = _watchdog(30.0)
    holder: threading.Thread | None = None
    try:
        datasource_id = _create_direct(harness)

        def hold() -> None:
            with harness.store._lifecycle_lock:
                held.set()
                release.wait(10)

        holder = threading.Thread(target=hold, daemon=True)
        holder.start()
        assert held.wait(5)
        _completes_quickly(lambda: _read(DatasourceAdmin(harness.runtime), name, datasource_id))
    finally:
        release.set()
        if holder is not None:
            holder.join(10)
        harness.close()
        guard.cancel()


@pytest.mark.parametrize("blocked", ["dns", "filesystem"])
@pytest.mark.parametrize("name", _READS)
def test_reads_stay_on_the_previous_seal_while_the_store_is_really_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, blocked: str
) -> None:
    # Bloqueio REAL do store: uma criacao desabilitada resolve o DNS DENTRO do
    # `store.create` (sob o lock interno do store) ou para num ponto do commit
    # de filesystem. As leituras seguem no selo anterior, sem esperar.
    from tests.admin_v2_support import Crash, dns  # noqa: PLC0415

    entered, release = threading.Event(), threading.Event()
    armed = threading.Event()

    def blocking_dns(host: str, port: int) -> tuple[str, ...]:
        if armed.is_set():
            entered.set()
            release.wait(20)
        return dns(host, port)

    harness = build_v2(tmp_path, resolver=blocking_dns)
    if blocked == "filesystem":
        from maskgw.datasource import CrashPoint  # noqa: PLC0415

        original_call = Crash.__call__

        def blocking_hook(self: Crash, point: CrashPoint) -> None:
            if armed.is_set() and point == CrashPoint.AFTER_STORE_REPLACE:
                entered.set()
                release.wait(20)
            original_call(self, point)

        monkeypatch.setattr(Crash, "__call__", blocking_hook)
    guard = _watchdog(60.0)
    writer: threading.Thread | None = None
    try:
        datasource_id = _create_direct(harness)
        before = harness.store.snapshot().catalog_revision
        if blocked == "dns":
            armed.set()
        else:
            # O DNS do store nao bloqueia; so o filesystem.
            monkeypatch.setattr(harness.service, "_resolver", dns, raising=False)
            armed.set()
        writer = threading.Thread(
            target=lambda: _create_direct(harness, enabled=False, alias="hml"), daemon=True
        )
        writer.start()
        assert entered.wait(10), "o store esta de fato bloqueado"
        result = _completes_quickly(
            lambda: _read(DatasourceAdmin(harness.runtime), name, datasource_id)
        )
        revision = getattr(result, "catalog_revision", None)
        assert revision == before
    finally:
        release.set()
        if writer is not None:
            writer.join(20)
        harness.close()
        guard.cancel()


# ---- indisponibilidade monotona -----------------------------------------------


def test_withdrawal_during_sealing_is_monotonic_and_never_reports_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `block_unknown` chega enquanto o escritor monta o selo novo. O selo NAO
    # pode voltar a ficar disponivel, e a escrita nao pode responder sucesso.
    from maskgw.runtime.datasource_service import DatasourceRuntimeService  # noqa: PLC0415

    harness = build_v2(tmp_path)
    built, release = threading.Event(), threading.Event()
    original_seal = DatasourceRuntimeService._seal

    def slow_seal(self: DatasourceRuntimeService) -> Any:
        view = original_seal(self)
        built.set()
        release.wait(20)
        return view

    monkeypatch.setattr(DatasourceRuntimeService, "_seal", slow_seal)
    outcome: list[object] = []

    def write() -> None:
        try:
            outcome.append(_create_direct(harness, enabled=False))
        except DatasourceAdminError as exc:
            outcome.append(exc.category.value)

    guard = _watchdog(30.0)
    writer = threading.Thread(target=write, daemon=True)
    try:
        writer.start()
        assert built.wait(10), "persistiu e montou o selo novo"
        harness.service.block_unknown()
        release.set()
        writer.join(10)
        assert outcome == ["CATALOG_OUTCOME_UNCERTAIN"]
        assert harness.service.view() is None
        assert harness.service.blocked
        status = DatasourceAdmin(harness.runtime).status()
        assert status.catalog_available is False
        with pytest.raises(DatasourceAdminError) as caught:
            DatasourceAdmin(harness.runtime).list()
        assert caught.value.category.value == "CATALOG_BLOCKED"
    finally:
        release.set()
        writer.join(10)
        harness.close()
        guard.cancel()


# ---- falha apos efeito possivel: indisponivel, nunca resposta mista ----------


def test_publish_failure_after_persist_makes_reads_unavailable(
    v2: V2Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(self: Any, **_kwargs: Any) -> Any:
        del self
        msg = "publicacao injetada"
        raise RuntimeError(msg)

    monkeypatch.setattr(CandidateReservation, "publish", broken)
    reply = v2.call("POST", "/admin/v2/datasources", create_body(expected=v2.store.revision))
    assert reply.status >= 500
    assert SECRET not in reply.text()
    assert "injetada" not in reply.text()
    listing = v2.call("GET", "/admin/v2/datasources")
    assert listing.status == 503
    assert listing.json()["error"] == "CATALOG_BLOCKED"
    status = v2.call("GET", "/admin/v2/status").json()
    assert status["catalog_available"] is False
    assert status["catalog_revision"] is None
    assert status["writes_blocked"] is True


def _seed(v2: V2Harness) -> dict[str, Any]:
    return v2.create()


def _op_request(op: str, seeded: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    ds_id, revision = seeded["datasource_id"], seeded["datasource_revision"]
    base = f"/admin/v2/datasources/{ds_id}"
    if op == "update":
        return "PUT", base, update_body(revision)
    if op == "rotate":
        return (
            "POST",
            f"{base}:rotate-credential",
            {"expected_revision": revision, "credential": {"password": "rotated-password-x1"}},
        )
    if op == "disable":
        return "POST", f"{base}:disable", {"expected_revision": revision}
    return "DELETE", base, {"expected_revision": revision, "confirm_alias": ALIAS}


@pytest.mark.parametrize(
    ("op", "owner", "name"),
    [
        ("update", CandidateReservation, "publish"),
        ("rotate", CandidateReservation, "publish"),
        ("disable", DatasourceRegistry, "withdraw"),
        ("delete", DatasourceRegistry, "withdraw"),
    ],
)
def test_failure_after_persist_on_each_write_never_answers_a_mixed_read(
    v2: V2Harness, monkeypatch: pytest.MonkeyPatch, op: str, owner: type, name: str
) -> None:
    seeded = _seed(v2)
    method, path, body = _op_request(op, seeded)

    def broken(self: Any, *_args: Any, **_kwargs: Any) -> Any:
        del self
        msg = "efeito injetado"
        raise RuntimeError(msg)

    monkeypatch.setattr(owner, name, broken)
    reply = v2.call(method, path, body)
    assert reply.status >= 500
    assert "injetado" not in reply.text()
    assert v2.call("GET", "/admin/v2/datasources").status == 503
    assert v2.call("GET", f"/admin/v2/datasources/{seeded['datasource_id']}").status == 503
    status = v2.call("GET", "/admin/v2/status").json()
    assert status["catalog_available"] is False
    assert status["writes_blocked"] is True
    events = [e for e in v2.audit.datasource_events() if e["operation"] != "datasource_create"]
    assert len(events) == 1, "uma auditoria por operacao"


def test_seal_failure_after_a_successful_write_is_uncertain_not_success(
    v2: V2Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    from maskgw.runtime.datasource_service import DatasourceRuntimeService  # noqa: PLC0415

    def broken_seal(self: Any) -> Any:
        del self
        msg = "selagem injetada"
        raise RuntimeError(msg)

    monkeypatch.setattr(DatasourceRuntimeService, "_seal", broken_seal)
    before = v2.store.revision
    reply = v2.call("POST", "/admin/v2/datasources", create_body(expected=before, enabled=False))
    assert reply.status == 500
    assert reply.json()["error"] == "CATALOG_OUTCOME_UNCERTAIN"
    assert v2.store.revision == before + 1, "o efeito existe; so a leitura nao o mostra"
    assert v2.call("GET", "/admin/v2/datasources").json()["error"] == "CATALOG_BLOCKED"
    (event,) = v2.audit.datasource_events()
    assert event["error_category"] == "CATALOG_OUTCOME_UNCERTAIN"


# ---- estado desconhecido vindo de OUTRO worker ---------------------------------


def test_unknown_state_from_another_worker_wins_over_a_concurrent_seal(
    v2: V2Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    from maskgw.runtime.datasource_service import DatasourceRuntimeService  # noqa: PLC0415
    from tests.admin_v2_support import draft_body  # noqa: PLC0415

    built, release = threading.Event(), threading.Event()
    original_seal = DatasourceRuntimeService._seal

    def slow_seal(self: DatasourceRuntimeService) -> Any:
        view = original_seal(self)
        built.set()
        release.wait(20)
        return view

    def interrupted(self: Any, body: Any) -> Any:
        del self, body
        raise KeyboardInterrupt

    monkeypatch.setattr(DatasourceRuntimeService, "_seal", slow_seal)
    monkeypatch.setattr(DatasourceAdmin, "test_draft", interrupted)
    guard = _watchdog(60.0)
    writer, box = _background(
        lambda: v2.call(
            "POST",
            "/admin/v2/datasources",
            create_body(expected=v2.store.revision, enabled=False),
            timeout=30,
        )
    )
    try:
        assert built.wait(10)
        other = v2.call("POST", "/admin/v2/datasources:test", draft_body(alias="other"))
        assert other.status == 500
        assert other.json()["error"] == "INTERNAL_ERROR"
        assert v2.work is not None and v2.work.broken
        assert v2.service.blocked
    finally:
        release.set()
        writer.join(30)
        guard.cancel()
    assert box[0].status == 500
    assert box[0].json()["error"] == "CATALOG_OUTCOME_UNCERTAIN"
    assert v2.call("GET", "/admin/v2/datasources").status == 503
    refused = v2.call("POST", "/admin/v2/datasources", create_body(expected=v2.store.revision))
    assert refused.json()["error"] == "DATASOURCE_SERVICE_UNAVAILABLE"
    by_operation: dict[str, list[str | None]] = {}
    for event in v2.audit.datasource_events():
        by_operation.setdefault(event["operation"], []).append(event["error_category"])
    assert by_operation["datasource_test_draft"] == ["INTERNAL_ERROR"]
    assert by_operation["datasource_create"] == [
        "CATALOG_OUTCOME_UNCERTAIN",
        "DATASOURCE_SERVICE_UNAVAILABLE",
    ]


# ---- sessoes da geracao EXATA do selo --------------------------------------------


def test_sealed_read_counts_sessions_of_its_own_generation_during_a_swap(
    v2: V2Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    from maskgw.runtime.datasource_service import DatasourceRuntimeService  # noqa: PLC0415

    created = v2.create()
    datasource_id = created["datasource_id"]
    lease = v2.registry.open_session(ALIAS)
    built, release = threading.Event(), threading.Event()
    original_seal = DatasourceRuntimeService._seal

    def slow_seal(self: DatasourceRuntimeService) -> Any:
        view = original_seal(self)
        built.set()
        release.wait(20)
        return view

    monkeypatch.setattr(DatasourceRuntimeService, "_seal", slow_seal)
    guard = _watchdog(60.0)
    writer, box = _background(
        lambda: v2.call(
            "PUT",
            f"/admin/v2/datasources/{datasource_id}",
            update_body(created["datasource_revision"]),
            timeout=30,
        )
    )
    try:
        assert built.wait(10), "a geracao 2 ja foi publicada; o selo ainda e o anterior"
        assert v2.published()[ALIAS] == 2
        view = DatasourceAdmin(v2.runtime).get(datasource_id).datasource.runtime
        # A geracao do selo (1, aposentada com a sessao aberta), nao a atual.
        assert (view.generation, view.sessions) == (1, 1)
        status = DatasourceAdmin(v2.runtime).status()
        assert status.registry.published == 1
    finally:
        release.set()
        writer.join(30)
        guard.cancel()
        lease.close()
    assert box[0].status == 200
    view = DatasourceAdmin(v2.runtime).get(datasource_id).datasource.runtime
    assert (view.generation, view.sessions) == (2, 0)


# ---- recusa verdadeira: admissao que falha no meio nunca executa ----------------


def test_admission_failing_in_notify_is_a_true_refusal_without_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = build_v2(tmp_path)
    queue = AdminWorkQueue(on_unknown=harness.service.block_unknown)
    guard = _watchdog(60.0)
    try:
        queue.start()
        before = harness.state()
        body = DatasourceCreateRequest.model_validate(create_body(expected=harness.store.revision))
        admin = DatasourceAdmin(harness.runtime)

        def broken_notify(n: int = 1) -> None:
            del n
            msg = "notify injetado"
            raise OSError(msg)

        monkeypatch.setattr(queue._cond, "notify", broken_notify)
        with pytest.raises(DatasourceAdminError) as caught:
            asyncio.run(
                _enqueue(
                    queue,
                    DatasourceAuditor(harness.audit_log),
                    DatasourceOperationName.CREATE,
                    None,
                    lambda probe: admin.create(body, probe),
                )
            )
        assert caught.value.category.value == "DATASOURCE_SERVICE_UNAVAILABLE"
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None
        assert queue.accepted == 0
        monkeypatch.undo()
        queue.close_admission()
        assert queue.drain()
        # Nada executou atras da recusa: sem efeito, auditada uma vez.
        assert harness.state() == before
        (event,) = harness.audit.datasource_events()
        assert event["error_category"] == "DATASOURCE_SERVICE_UNAVAILABLE"
    finally:
        monkeypatch.undo()
        queue.close_admission()
        queue.drain()
        harness.close()
        guard.cancel()


# ---- cancelamento do request nao abandona a operacao aceita ------------------


@pytest.mark.parametrize("moment", ["queued", "verify", "persist-publish"])
def test_cancelled_request_never_abandons_the_accepted_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, moment: str
) -> None:
    # Watchdog ANTES de qualquer recurso; cancelado so depois da limpeza.
    guard = _watchdog(60.0)
    harness = build_v2(tmp_path)
    queue = AdminWorkQueue(on_unknown=harness.service.block_unknown)
    gate = threading.Event()
    reached = threading.Event()
    gates = [gate]
    if moment == "verify":
        harness.factory.connect_gate = gate
        reached = harness.factory.connect_started
        reached.clear()
    elif moment == "persist-publish":
        reached, gate = _hold(monkeypatch, CandidateReservation, "publish")
        gates.append(gate)
    body = DatasourceCreateRequest.model_validate(create_body(expected=harness.store.revision))
    admin = DatasourceAdmin(harness.runtime)
    auditor = DatasourceAuditor(harness.audit_log)

    def condition() -> bool:
        return queue.accepted == 3 if moment == "queued" else reached.is_set()

    async def scenario() -> None:
        task = asyncio.ensure_future(
            _enqueue(
                queue,
                auditor,
                DatasourceOperationName.CREATE,
                None,
                lambda probe: admin.create(body, probe),
            )
        )
        for _ in range(500):
            if condition():
                break
            await asyncio.sleep(0.01)
        assert condition()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        assert task.cancelled()

    try:
        queue.start()
        if moment == "queued":
            for _ in range(2):
                queue.submit(lambda: gate.wait(20))
        # O loop termina (e fecha) ANTES de o worker concluir: a notificacao
        # tardia acha o loop fechado e nao tira o ticket de dono.
        asyncio.run(scenario())
        for event in gates:
            event.set()
        queue.close_admission()
        assert queue.drain()
        assert len(harness.store.snapshot().datasources) == 1, "a operacao aceita concluiu"
        assert harness.published() == {ALIAS: 1}
        creates = [
            e for e in harness.audit.datasource_events() if e["operation"] == "datasource_create"
        ]
        assert [e["outcome"] for e in creates] == ["success"], "auditada exatamente uma vez"
    finally:
        # Mesmo com falha acima: barreiras soltas, fila drenada, harness
        # fechado — e o watchdog cancelado POR ULTIMO.
        for event in gates:
            event.set()
        queue.close_admission()
        queue.drain()
        harness.close()
        guard.cancel()
