"""Fase 9, Etapa 4: concorrencia pela porta HTTP real (F9-025, F9-026).

Os handlers v2 chamam o coordenador sincrono no event loop, como as escritas da
v1 (D-059); requisicoes simultaneas chegam por conexoes distintas e sao
serializadas pelo coordenador. O que se prova e o desfecho: um vencedor por
revision, nenhuma publicacao a mais, auditoria uma-por-requisicao, e o registry
coerente com o catalogo ao final. O ultimo teste dispensa o event loop e chama
a traducao v2 de varias threads ao mesmo tempo.
"""

from __future__ import annotations

import threading
from collections import Counter
from collections.abc import Callable, Iterator
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from maskgw.admin.http.v2.errors import DatasourceAdminError
from maskgw.admin.http.v2.operations import DatasourceAdmin
from maskgw.admin.http.v2.schemas import (
    DatasourceDeleteRequest,
    DatasourceRevisionRequest,
    DatasourceUpdateRequest,
)
from maskgw.runtime.datasource_service import DatasourceWriteProbe
from tests.admin_http_support import Reply
from tests.admin_v2_support import (
    ALIAS,
    OTHER_HOST,
    V2Harness,
    build_v2,
    create_body,
    draft_body,
    update_body,
)


@pytest.fixture
def v2(tmp_path: Path) -> Iterator[V2Harness]:
    harness = build_v2(tmp_path)
    harness.start()
    try:
        yield harness
    finally:
        harness.close()


def _race(calls: list[Callable[[], Any]]) -> list[Any]:
    barrier = threading.Barrier(len(calls))
    results: list[Any] = [None] * len(calls)

    def run(index: int) -> None:
        barrier.wait()
        results[index] = calls[index]()

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(calls))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    assert not any(thread.is_alive() for thread in threads)
    assert all(result is not None for result in results)
    return results


def _coherent(v2: V2Harness) -> None:
    """Registry e catalogo concordam; nada em voo; nenhuma conexao aberta."""
    published = {item.datasource_id: item for item in v2.registry.status().published}
    records = v2.store.snapshot().datasources
    for record in records:
        if record.enabled:
            assert published[record.id].record_revision == record.revision
        else:
            assert record.id not in published
    assert set(published) <= {record.id for record in records}
    assert v2.registry.status().candidates == 0
    assert v2.factory.open_adapters() == []


def test_one_winner_per_datasource_revision(v2: V2Harness) -> None:
    ds_id = v2.create()["datasource_id"]
    generation = v2.published()[ALIAS]
    replies: list[Reply] = _race(
        [
            partial(
                v2.call,
                "PUT",
                f"/admin/v2/datasources/{ds_id}",
                update_body(1, display_name=f"W{index}"),
            )
            for index in range(8)
        ]
    )
    assert Counter(reply.status for reply in replies) == {200: 1, 409: 7}
    for reply in replies:
        if reply.status == 409:
            body = reply.json()
            assert body["error"] == "REVISION_CONFLICT"
            assert body["current_revision"] == 2
    # Uma unica troca de geracao: so o vencedor publicou.
    assert v2.published()[ALIAS] == generation + 1
    events = [e for e in v2.audit.datasource_events() if e["operation"] == "datasource_update"]
    assert Counter(e["outcome"] for e in events) == {"success": 1, "rejected": 7}
    _coherent(v2)


def test_distinct_datasources_never_conflict(v2: V2Harness) -> None:
    ids = [v2.create(alias=f"ds-{index}")["datasource_id"] for index in range(4)]
    for expected in range(1, 4):
        replies: list[Reply] = _race(
            [
                partial(v2.call, "PUT", f"/admin/v2/datasources/{ds_id}", update_body(expected))
                for ds_id in ids
            ]
        )
        assert [reply.status for reply in replies] == [200] * 4
    assert all(v2.store.get(ds_id).revision == 4 for ds_id in ids)
    _coherent(v2)


def test_racing_creates_of_one_alias_have_one_winner(v2: V2Harness) -> None:
    replies: list[Reply] = _race(
        [
            partial(v2.call, "POST", "/admin/v2/datasources", create_body(expected=1))
            for _ in range(6)
        ]
    )
    statuses = Counter(reply.status for reply in replies)
    assert statuses[200] == 1
    assert statuses[409] == 5
    assert len(v2.store.snapshot().datasources) == 1
    _coherent(v2)


def test_mixed_tests_reads_and_writes_keep_state_coherent(v2: V2Harness) -> None:
    ids = [v2.create(alias=f"ds-{index}")["datasource_id"] for index in range(3)]
    calls: list[Callable[[], Any]] = []
    for index, ds_id in enumerate(ids):
        calls += [
            partial(v2.call, "POST", f"/admin/v2/datasources/{ds_id}:test", {}),
            partial(v2.call, "GET", "/admin/v2/datasources"),
            partial(
                v2.call,
                "POST",
                "/admin/v2/datasources:test",
                draft_body(alias=f"draft-{index}", host=OTHER_HOST),
            ),
            partial(
                v2.call,
                "POST",
                f"/admin/v2/datasources/{ds_id}:disable",
                {"expected_revision": 1},
            ),
            partial(v2.call, "GET", f"/admin/v2/datasources/{ds_id}"),
        ]
    replies: list[Reply] = _race(calls)
    for reply in replies:
        # Um teste pode perder a corrida para a desabilitacao (409), nunca falhar.
        assert reply.status in {200, 409}, reply.text()
    assert all(not v2.store.get(ds_id).enabled for ds_id in ids)
    assert v2.published() == {}
    assert len(v2.store.snapshot().datasources) == 3
    _coherent(v2)
    tests = [
        e for e in v2.audit.datasource_events() if e["operation"].startswith("datasource_test")
    ]
    assert len(tests) == 6
    assert all(e["revision_before"] is None for e in tests)


def _attempt(action: Callable[[], object]) -> str:
    try:
        action()
    except DatasourceAdminError as exc:
        return exc.category.value
    return "ok"


def test_service_level_parallel_writes_and_removals_stay_coherent(v2: V2Harness) -> None:
    ids = [v2.create(alias=f"ds-{index}")["datasource_id"] for index in range(4)]
    admin = DatasourceAdmin(v2.runtime)
    actions: list[Callable[[], object]] = []
    for index, ds_id in enumerate(ids):
        actions.append(
            partial(
                admin.update,
                ds_id,
                DatasourceUpdateRequest.model_validate(update_body(1)),
                DatasourceWriteProbe(),
            )
        )
        actions.append(
            partial(
                admin.set_enabled,
                ds_id,
                DatasourceRevisionRequest(expected_revision=1),
                DatasourceWriteProbe(),
                enabled=False,
            )
        )
        if index % 2 == 0:
            actions.append(
                partial(
                    admin.delete,
                    ds_id,
                    DatasourceDeleteRequest(expected_revision=1, confirm_alias=f"ds-{index}"),
                    DatasourceWriteProbe(),
                )
            )
    outcomes: list[str] = _race([partial(_attempt, action) for action in actions])
    # Por datasource, exatamente UMA das escritas com revision 1 venceu.
    assert Counter(outcomes)["ok"] == len(ids)
    assert set(outcomes) <= {"ok", "REVISION_CONFLICT", "NOT_FOUND"}
    _coherent(v2)
