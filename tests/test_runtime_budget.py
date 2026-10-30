"""B2-B1 logical model only: no OS quota, worker, pressure, SQL or registry."""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from functools import partial
from itertools import permutations, product
from pathlib import Path
from typing import Any

import pytest

from maskgw.runtime import budget
from maskgw.runtime.budget import (
    BudgetError,
    BudgetFailure,
    BudgetLedger,
    BudgetLimits,
    BudgetToken,
    CleanupConfirmation,
    DatasourceCapacity,
    ReleaseOutcome,
    ReservationKind,
    ReservationState,
    ReservationView,
)

ROOT = Path(__file__).resolve().parents[1]
COMPLETE = CleanupConfirmation(True, True, True, True, True)
INVALID_NUMBERS = (True, False, 0, -1, 1.5, float("nan"), float("inf"), "1", None, 1 << 63)


def limits(**changes: int) -> BudgetLimits:
    fields = {
        "total_bytes": 1000,
        "base_bytes": 2,
        "headroom_bytes": 3,
        "entries": 16,
        "sessions": 4,
        "workers": 4,
        "candidates": 2,
        "generations": 8,
        "auxiliaries": 8,
    }
    fields.update(changes)
    return BudgetLimits(**fields)


def ledger(**changes: int) -> BudgetLedger:
    return BudgetLedger(limits(**changes), (DatasourceCapacity(4, 2), DatasourceCapacity(4, 2)))


def generation(
    model: BudgetLedger,
    datasource: int = 0,
    cost: int = 10,
    replacing: BudgetToken | None = None,
) -> BudgetToken:
    token = model.reserve_candidate(datasource, shared_bytes=cost)
    model.publish(token, replacing=replacing)
    return token


def dispose(model: BudgetLedger, token: BudgetToken) -> ReleaseOutcome:
    model.begin_drain(token)
    return model.release(token, COMPLETE)


def refused(
    model: BudgetLedger,
    category: BudgetFailure,
    operation: Callable[[], object],
) -> None:
    before = model.status
    with pytest.raises(BudgetError) as caught:
        operation()
    assert caught.value.category is category
    assert str(caught.value) == "reserva logica recusada"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert model.status == before


def invariant(model: BudgetLedger) -> None:
    status = model.status
    assert status.available_bytes >= 0
    assert status.reserved_bytes == (
        status.base_bytes
        + status.headroom_bytes
        + status.worker_bytes
        + status.parent_bytes
        + status.quarantined_bytes
    )
    assert status.reserved_bytes + status.available_bytes == model._limits.total_bytes
    assert len(status.entries) == model._limits.entries
    assert len(status.epochs) == model._limits.entries
    assert len(status.quarantined_entries) <= 2


def entry_at(model: BudgetLedger, token: BudgetToken) -> ReservationView:
    entry = model.status.entries[token._slot]
    assert entry is not None
    return entry


@pytest.mark.parametrize("field", tuple(BudgetLimits.__dataclass_fields__))
@pytest.mark.parametrize("value", INVALID_NUMBERS)
def test_limits_strict_bounded_integers(field, value):
    with pytest.raises(BudgetError) as caught:
        limits(**{field: value})
    assert caught.value.category is BudgetFailure.INVALID


@pytest.mark.parametrize(
    "changes",
    [
        {"total_bytes": 4},
        {"entries": 1},
        {"entries": 4097},
        {"base_bytes": (1 << 63) - 1},
        {"headroom_bytes": (1 << 63) - 1},
    ],
)
def test_config_cross_field_bounds(changes):
    with pytest.raises(BudgetError):
        limits(**changes)


@pytest.mark.parametrize("field", ("sessions", "candidates"))
@pytest.mark.parametrize("value", (*INVALID_NUMBERS, 4097))
def test_datasource_capacity_is_strict(field, value):
    with pytest.raises(BudgetError):
        DatasourceCapacity(**({"sessions": 2, "candidates": 1} | {field: value}))


@pytest.mark.parametrize("capacities", ([], (), (object(),), (DatasourceCapacity(1, 1),) * 1025))
def test_datasources_fixed_bounded_tuple(capacities):
    with pytest.raises(BudgetError):
        BudgetLedger(limits(), capacities)


def test_limits_type_checked_before_access():
    invalid: Any = object()
    with pytest.raises(BudgetError):
        BudgetLedger(invalid, (DatasourceCapacity(1, 1),))


@pytest.mark.parametrize("field", tuple(CleanupConfirmation.__dataclass_fields__))
@pytest.mark.parametrize("value", (0, 1, None, "yes"))
def test_cleanup_facts_are_exact_bool(field, value):
    values = dict.fromkeys(CleanupConfirmation.__dataclass_fields__, True)
    with pytest.raises(BudgetError):
        CleanupConfirmation(**(values | {field: value}))


def test_exact_budget_and_one_byte_excess():
    model = ledger(total_bytes=25)
    gen = generation(model)
    session = model.reserve_session(gen, worker_bytes=4, parent_bytes=6)
    assert model.status.reserved_bytes == 25
    refused(model, BudgetFailure.CAPACITY, lambda: model.reserve_auxiliary(shared_bytes=1))
    model.mark_live(session)
    assert model.status.reserved_bytes == 25
    invariant(model)


def test_base_and_headroom_not_admission_credit():
    model = ledger(total_bytes=5)
    assert model.status.available_bytes == 0
    refused(model, BudgetFailure.CAPACITY, lambda: model.reserve_candidate(0, shared_bytes=1))
    invariant(model)


@pytest.mark.parametrize("value", INVALID_NUMBERS)
@pytest.mark.parametrize("field", ("worker_bytes", "parent_bytes", "shared_bytes"))
def test_charges_strict_before_mutation(field, value):
    model = ledger()
    gen = generation(model)
    if field == "shared_bytes":
        call = partial(model.reserve_auxiliary, shared_bytes=value)
    else:
        call = partial(
            model.reserve_session,
            gen,
            **(
                {"worker_bytes": 4, "parent_bytes": 6}
                | {
                    field: value,
                }
            ),
        )
    refused(model, BudgetFailure.INVALID, call)


@pytest.mark.parametrize("value", (True, -1, 2, 1.0, "0", None, 1 << 63))
def test_datasource_ordinal_not_client_string(value):
    model = ledger()
    refused(model, BudgetFailure.INVALID, lambda: model.reserve_candidate(value, shared_bytes=1))


@pytest.mark.parametrize("same_datasource", (True, False))
@pytest.mark.parametrize("order", tuple(permutations((0, 1))))
def test_last_memory_credit_orders(same_datasource, order):
    model = ledger(total_bytes=19)
    gens = [generation(model, 0, 2), generation(model, 1, 2)]
    choices = [gens[0], gens[0] if same_datasource else gens[1]]
    model.reserve_session(choices[order[0]], worker_bytes=4, parent_bytes=6)
    refused(
        model,
        BudgetFailure.CAPACITY,
        lambda: model.reserve_session(
            choices[order[1]],
            worker_bytes=4,
            parent_bytes=6,
        ),
    )
    assert model.status.sessions == 1
    invariant(model)


@pytest.mark.parametrize("bound", ("sessions", "workers", "datasource", "entries"))
def test_each_session_capacity_refuses_all_or_nothing(bound):
    options = {bound: 1} if bound in ("sessions", "workers") else {}
    if bound == "entries":
        options = {
            "entries": 2,
            "sessions": 2,
            "workers": 2,
            "candidates": 2,
            "generations": 2,
            "auxiliaries": 2,
        }
    caps = (DatasourceCapacity(1 if bound == "datasource" else 4, 2),)
    model = BudgetLedger(limits(**options), caps)
    gen = generation(model)
    model.reserve_session(gen, worker_bytes=4, parent_bytes=6)
    refused(
        model,
        BudgetFailure.CAPACITY,
        lambda: model.reserve_session(
            gen,
            worker_bytes=4,
            parent_bytes=6,
        ),
    )


@pytest.mark.parametrize("bound", ("candidates", "datasource", "auxiliaries", "generations"))
def test_each_shared_capacity_retains_previous_credits(bound):
    call: Callable[[], object]
    model = ledger(**({bound: 1} if bound != "datasource" else {}))
    if bound == "datasource":
        model = BudgetLedger(limits(), (DatasourceCapacity(4, 1),))
    if bound == "auxiliaries":
        model.reserve_auxiliary(shared_bytes=10)
        call = partial(model.reserve_auxiliary, shared_bytes=10)
    elif bound == "generations":
        gen = generation(model)
        token = model.reserve_candidate(0, shared_bytes=10)
        call = partial(model.publish, token, replacing=gen)
    else:
        model.reserve_candidate(0, shared_bytes=10)
        call = partial(model.reserve_candidate, 0 if bound == "datasource" else 1, shared_bytes=10)
    refused(model, BudgetFailure.CAPACITY, call)


@pytest.mark.parametrize("order", tuple(permutations(("admit", "shutdown"))))
def test_admission_shutdown_orders(order):
    model = ledger()
    gen = generation(model)
    for action in order:
        if action == "shutdown":
            model.begin_shutdown()
        elif model.status.closing:
            refused(
                model,
                BudgetFailure.CLOSED,
                lambda: model.reserve_session(
                    gen,
                    worker_bytes=4,
                    parent_bytes=6,
                ),
            )
        else:
            token = model.reserve_session(gen, worker_bytes=4, parent_bytes=6)
    if order[0] == "admit":
        refused(model, BudgetFailure.CLOSED, lambda: model.mark_live(token))
        assert dispose(model, token) is ReleaseOutcome.RELEASED
    assert dispose(model, gen) is ReleaseOutcome.RELEASED
    model.finish_shutdown()
    assert model.status.closed


def test_prebarrier_candidate_can_publish_without_new_credit():
    model = ledger()
    old = generation(model)
    session = model.reserve_session(old, worker_bytes=4, parent_bytes=6)
    new = model.reserve_candidate(0, shared_bytes=20)
    charged = model.status.reserved_bytes
    model.begin_shutdown()
    model.publish(new, replacing=old)
    assert model.status.reserved_bytes == charged
    assert model.status.candidates == 0
    assert model.status.generations == 2
    assert model.release(old, COMPLETE) is ReleaseOutcome.HELD
    refused(model, BudgetFailure.CAPACITY, model.finish_shutdown)
    assert dispose(model, session) is ReleaseOutcome.RELEASED
    assert model.release(old, COMPLETE) is ReleaseOutcome.RELEASED
    assert dispose(model, new) is ReleaseOutcome.RELEASED
    model.finish_shutdown()
    final = model.status
    model.begin_shutdown()
    model.finish_shutdown()
    assert model.status == final


def test_shutdown_never_implicitly_releases_or_waits():
    model = ledger()
    token = model.reserve_auxiliary(shared_bytes=5)
    refused(model, BudgetFailure.STATE, model.finish_shutdown)
    model.begin_shutdown()
    before = model.status
    model.begin_shutdown()
    assert model.status == before
    refused(model, BudgetFailure.CAPACITY, model.finish_shutdown)
    assert dispose(model, token) is ReleaseOutcome.RELEASED
    model.finish_shutdown()
    assert model.release(token, COMPLETE) is ReleaseOutcome.ALREADY_RELEASED
    refused(model, BudgetFailure.CLOSED, lambda: model.reserve_auxiliary(shared_bytes=1))


@pytest.mark.parametrize("missing", tuple(CleanupConfirmation.__dataclass_fields__))
def test_every_cleanup_condition_holds_both_memory_and_capacity(missing):
    model = ledger()
    gen = generation(model)
    session = model.reserve_session(gen, worker_bytes=7, parent_bytes=11)
    model.mark_live(session)
    model.begin_drain(session)
    initial = model.status
    facts = replace(COMPLETE, **{missing: False})
    assert model.release(session, facts) is ReleaseOutcome.HELD
    assert model.status.reserved_bytes == initial.reserved_bytes
    assert model.status.sessions == 1
    assert entry_at(model, session).state is ReservationState.HELD
    assert model.release(session, COMPLETE) is ReleaseOutcome.RELEASED
    assert model.release(session, COMPLETE) is ReleaseOutcome.ALREADY_RELEASED
    assert model.status.sessions == 0
    invariant(model)


def test_idle_and_job_completion_have_no_credit_release():
    model = ledger()
    gen = generation(model)
    session = model.reserve_session(gen, worker_bytes=7, parent_bytes=11)
    model.mark_live(session)
    before = model.status
    # No lifecycle transition occurs merely because a request has completed.
    for _ in range(10):
        assert model.status == before
    refused(model, BudgetFailure.STATE, lambda: model.release(session, COMPLETE))
    model.begin_drain(session)
    assert model.release(session, replace(COMPLETE, output=False)) is ReleaseOutcome.HELD
    assert model.release(session, COMPLETE) is ReleaseOutcome.RELEASED


def test_generation_stays_charged_until_sessions_and_disposal_confirmed():
    model = ledger()
    old = generation(model)
    session = model.reserve_session(old, worker_bytes=7, parent_bytes=11)
    new = generation(model, cost=20, replacing=old)
    assert model.status.base_bytes == 32
    assert entry_at(model, session).generation_slot == old._slot
    assert model.release(old, COMPLETE) is ReleaseOutcome.HELD
    assert dispose(model, session) is ReleaseOutcome.RELEASED
    assert model.release(old, replace(COMPLETE, handles=False)) is ReleaseOutcome.HELD
    assert model.status.base_bytes == 32
    assert model.release(old, COMPLETE) is ReleaseOutcome.RELEASED
    assert model.status.base_bytes == 22
    assert entry_at(model, new).state is ReservationState.LIVE


def test_one_shared_generation_plus_private_session_costs():
    model = ledger()
    gen = generation(model, cost=20)
    for _ in range(3):
        model.reserve_session(gen, worker_bytes=7, parent_bytes=11)
    assert model.status.base_bytes == 22
    assert model.status.worker_bytes == 21
    assert model.status.parent_bytes == 33
    assert model.status.reserved_bytes == 79
    invariant(model)


def test_withdraw_reenable_cycles_not_bounded_by_nominal_retired_limit():
    model = BudgetLedger(
        limits(entries=20, sessions=8, workers=8),
        (DatasourceCapacity(8, 2),),
    )
    pairs = []
    for _ in range(6):
        gen = generation(model)
        session = model.reserve_session(gen, worker_bytes=4, parent_bytes=6)
        model.begin_drain(gen)
        assert model.release(gen, COMPLETE) is ReleaseOutcome.HELD
        pairs.append((gen, session))
    assert model.status.generations == 6
    assert model.status.base_bytes == 62
    for gen, session in reversed(pairs):
        assert dispose(model, session) is ReleaseOutcome.RELEASED
        assert model.release(gen, COMPLETE) is ReleaseOutcome.RELEASED
    assert model.status.reserved_bytes == 5


def test_growth_refused_without_modifying_published_generation():
    model = ledger(total_bytes=25)
    gen = generation(model)
    refused(model, BudgetFailure.CAPACITY, lambda: model.reserve_candidate(0, shared_bytes=11))
    assert entry_at(model, gen).state is ReservationState.LIVE


def test_auxiliary_cost_retained_independently_of_sessions():
    model = ledger()
    shared = model.reserve_auxiliary(shared_bytes=17)
    gen = generation(model)
    session = model.reserve_session(gen, worker_bytes=4, parent_bytes=6)
    assert dispose(model, session) is ReleaseOutcome.RELEASED
    assert dispose(model, gen) is ReleaseOutcome.RELEASED
    assert model.status.base_bytes == 19
    model.retain(shared)
    before = model.status
    model.begin_drain(shared)
    model.retain(shared)
    assert model.status == before
    assert model.release(shared, COMPLETE) is ReleaseOutcome.RELEASED


def test_no_implicit_replacement_or_cross_datasource_replacement():
    model = ledger()
    old = generation(model)
    candidate = model.reserve_candidate(0, shared_bytes=10)
    refused(model, BudgetFailure.STATE, lambda: model.publish(candidate))
    other = generation(model, 1)
    refused(model, BudgetFailure.STATE, lambda: model.publish(candidate, replacing=other))
    model.publish(candidate, replacing=old)


@pytest.mark.parametrize("action", ("session", "publish", "mark_live"))
def test_wrong_kind_or_state_never_allocates(action):
    call: Callable[[], object]
    model = ledger()
    aux = model.reserve_auxiliary(shared_bytes=10)
    if action == "session":
        call = partial(model.reserve_session, aux, worker_bytes=4, parent_bytes=6)
    elif action == "publish":
        call = partial(model.publish, aux)
    else:
        model.begin_drain(aux)
        call = partial(model.mark_live, aux)
    refused(model, BudgetFailure.STATE, call)


def test_wrong_instance_cannot_return_credit():
    first, second = ledger(), ledger()
    token = first.reserve_auxiliary(shared_bytes=10)
    second.reserve_auxiliary(shared_bytes=10)
    refused(second, BudgetFailure.INVALID, lambda: second.release(token, COMPLETE))


@pytest.mark.parametrize(
    "field,value",
    (
        ("_slot", True),
        ("_slot", -1),
        ("_slot", 16),
        ("_epoch", True),
        ("_epoch", 0),
        ("_epoch", 1 << 63),
    ),
)
def test_token_fields_are_strict(field, value):
    model = ledger()
    token = model.reserve_auxiliary(shared_bytes=10)
    invalid = replace(token, **{field: value})
    refused(model, BudgetFailure.INVALID, lambda: model.release(invalid, COMPLETE))


def test_stale_epoch_cannot_release_reused_slot():
    model = ledger()
    old = model.reserve_auxiliary(shared_bytes=10)
    assert dispose(model, old) is ReleaseOutcome.RELEASED
    new = model.reserve_auxiliary(shared_bytes=20)
    assert new._slot == old._slot and new._epoch > old._epoch
    refused(model, BudgetFailure.STATE, lambda: model.release(old, COMPLETE))
    assert dispose(model, new) is ReleaseOutcome.RELEASED
    assert model.release(new, COMPLETE) is ReleaseOutcome.ALREADY_RELEASED


def test_epoch_exhaustion_never_wraps():
    model = ledger()
    # Private test-only boundary setup, impossible to reach in a short fixture.
    model._image = replace(
        model._image, slots=tuple(replace(slot, epoch=(1 << 63) - 1) for slot in model._image.slots)
    )
    refused(model, BudgetFailure.CAPACITY, lambda: model.reserve_auxiliary(shared_bytes=1))


def test_bookkeeping_does_not_grow_with_cycles_or_refusals():
    model = ledger(auxiliaries=1)
    fields = type(model).__slots__
    for _ in range(200):
        token = model.reserve_auxiliary(shared_bytes=10)
        refused(model, BudgetFailure.CAPACITY, lambda: model.reserve_auxiliary(shared_bytes=10))
        assert dispose(model, token) is ReleaseOutcome.RELEASED
        assert all(row is None for row in model.status.entries)
        assert len(model.status.epochs) == 16
        assert type(model).__slots__ == fields
        assert not model.status.quarantined_entries
    assert max(model.status.epochs) == 200


@pytest.mark.parametrize(
    "sequence", tuple(product(("reserve", "drain", "release", "shutdown"), repeat=3))
)
def test_small_transition_orders_preserve_invariant(sequence):
    model = ledger(total_bytes=15)
    token = None
    for action in sequence:
        try:
            if action == "reserve":
                token = model.reserve_auxiliary(shared_bytes=10)
            elif action == "drain" and token is not None:
                model.begin_drain(token)
            elif action == "release" and token is not None:
                model.release(token, COMPLETE)
            elif action == "shutdown":
                model.begin_shutdown()
        except BudgetError as error:
            assert error.category in (
                BudgetFailure.CAPACITY,
                BudgetFailure.STATE,
                BudgetFailure.CLOSED,
            )
        invariant(model)


def operation_case(name: str) -> tuple[BudgetLedger, Callable[[], object]]:  # noqa: PLR0911 - closed fault scenarios
    model = ledger()
    if name == "reserve":
        return model, lambda: model.reserve_auxiliary(shared_bytes=10)
    if name == "begin_shutdown":
        return model, model.begin_shutdown
    if name == "finish_shutdown":
        model.begin_shutdown()
        return model, model.finish_shutdown
    if name in ("publish", "publish_replacement"):
        old = generation(model) if name == "publish_replacement" else None
        token = model.reserve_candidate(0, shared_bytes=10)
        return model, lambda: model.publish(token, replacing=old)
    token = model.reserve_auxiliary(shared_bytes=10)
    if name == "mark_live":
        return model, lambda: model.mark_live(token)
    if name == "drain":
        return model, lambda: model.begin_drain(token)
    if name == "retain":
        return model, lambda: model.retain(token)
    model.begin_drain(token)
    return model, lambda: model.release(token, COMPLETE)


@pytest.mark.parametrize("after_write", (False, True))
@pytest.mark.parametrize(
    "operation",
    (
        "reserve",
        "mark_live",
        "drain",
        "retain",
        "release",
        "publish",
        "publish_replacement",
        "begin_shutdown",
        "finish_shutdown",
    ),
)
def test_failure_before_or_after_publication_restores_whole_image(
    monkeypatch, operation, after_write
):
    model, call = operation_case(operation)
    original = BudgetLedger._write_image

    def fail(self, image):
        if after_write:
            original(self, image)
        raise MemoryError("CANARY_unexpected_failure")

    monkeypatch.setattr(BudgetLedger, "_write_image", fail)
    refused(model, BudgetFailure.FAULT, call)
    invariant(model)


@pytest.mark.parametrize("after_write", (False, True))
@pytest.mark.parametrize("operation", ("reserve", "release", "publish", "publish_replacement"))
def test_failed_rollback_quarantines_all_credits_and_both_owners(
    monkeypatch,
    operation,
    after_write,
):
    model, call = operation_case(operation)
    original = BudgetLedger._write_image
    before = model.status

    def write_then_fail(self, image):
        if after_write:
            original(self, image)
        raise RuntimeError("CANARY_write")

    def restore_fails(self, image):
        del self, image
        raise RuntimeError("CANARY_restore")

    monkeypatch.setattr(BudgetLedger, "_write_image", write_then_fail)
    monkeypatch.setattr(BudgetLedger, "_restore_image", restore_fails)
    with pytest.raises(BudgetError) as caught:
        call()
    assert caught.value.__context__ is None
    assert caught.value.category is BudgetFailure.FAULT
    assert model.status.failed
    assert model.status.available_bytes == 0
    assert model.status.reserved_bytes == 1000
    assert model.status.quarantined_entries[0] == before.entries
    next_entries = model.status.quarantined_entries[1]
    assert model.status.entries == (next_entries if after_write else before.entries)
    if operation in ("publish", "publish_replacement"):
        for index, row in enumerate(before.entries):
            if row is None:
                continue
            expected = (
                replace(
                    row,
                    kind=ReservationKind.GENERATION,
                    state=ReservationState.LIVE,
                )
                if row.kind is ReservationKind.CANDIDATE
                else replace(
                    row,
                    state=ReservationState.DRAINING,
                )
            )
            assert next_entries[index] == expected
    elif operation == "release":
        assert all(row is None for row in next_entries)
    refused(model, BudgetFailure.FAULT, lambda: model.reserve_auxiliary(shared_bytes=1))
    refused(model, BudgetFailure.FAULT, model.begin_shutdown)
    refused(model, BudgetFailure.FAULT, model.finish_shutdown)
    invariant(model)


@pytest.mark.parametrize("boundary", ("_Slot", "replace"))
def test_build_failure_leaves_image_and_epochs_intact(monkeypatch, boundary):
    model = ledger()

    def fail(*args, **kwargs):
        del args, kwargs
        raise MemoryError("CANARY_build")

    monkeypatch.setattr(budget, boundary, fail)
    refused(model, BudgetFailure.FAULT, lambda: model.reserve_auxiliary(shared_bytes=1))


def test_readonly_status_and_redacted_repr():
    model = ledger()
    token = model.reserve_auxiliary(shared_bytes=10)
    before = model.status
    with pytest.raises(FrozenInstanceError):
        before.reserved_bytes = 0  # type: ignore[misc]  # deliberate runtime immutability check
    with pytest.raises(FrozenInstanceError):
        token._epoch = 0  # type: ignore[misc]  # deliberate runtime immutability check
    assert repr(token) == "BudgetToken(<private>)"
    assert repr(model) == "BudgetLedger(<logical-only>)"
    assert model.status == before


def test_core_only_imports_closed_stdlib_and_no_operational_caller():
    source = ROOT / "src/maskgw/runtime/budget.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert set(modules) <= {
        "__future__",
        "collections.abc",
        "dataclasses",
        "enum",
        "functools",
        "typing",
    }
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"open", "print", "exec", "eval", "__import__"}
        for node in ast.walk(tree)
    )
    for path in (ROOT / "src/maskgw").rglob("*.py"):
        if path in (
            source,
            ROOT / "src/maskgw/pgwire/result_receiver.py",
            ROOT / "src/maskgw/runtime/domain.py",  # C1 pure limits reconciliation only.
            ROOT / "src/maskgw/runtime/worker_session.py",  # private owner, no ingress
        ):
            continue
        package = path.relative_to(ROOT / "src").parts[:-1]
        text = path.read_text(encoding="utf-8")
        assert not imports_budget(text, package), path
        # Complement direct/relative AST imports with literal dynamic-import paths.
        # Computed/reflected imports are not proven absent by this check alone.
        assert "runtime.budget" not in text, path
        assert "result_receiver" not in text, path


def test_review_release_outcomes_distinguish_retained_from_already_released():
    model = ledger()
    first = model.reserve_auxiliary(shared_bytes=10)
    second = model.reserve_auxiliary(shared_bytes=10)
    model.begin_drain(first)
    model.begin_drain(second)
    held = model.release(first, replace(COMPLETE, output=False))
    released = model.release(second, COMPLETE)
    already = model.release(second, COMPLETE)
    assert held is not already
    assert released is not held and released is not already
    assert held is ReleaseOutcome.HELD
    assert released is ReleaseOutcome.RELEASED
    assert already is ReleaseOutcome.ALREADY_RELEASED


def test_review_held_noop_never_attempts_publication(monkeypatch):
    model = ledger()
    token = model.reserve_auxiliary(shared_bytes=10)
    model.begin_drain(token)
    facts = replace(COMPLETE, output=False)
    assert model.release(token, facts) is ReleaseOutcome.HELD
    before = model.status

    def fail(self, image):
        del self, image
        raise RuntimeError("CANARY_noop_must_not_write")

    monkeypatch.setattr(BudgetLedger, "_write_image", fail)
    monkeypatch.setattr(BudgetLedger, "_restore_image", fail)
    assert model.release(token, facts) is ReleaseOutcome.HELD
    assert model.status == before


@pytest.mark.parametrize("outcome", tuple(ReleaseOutcome))
def test_release_outcome_requires_explicit_comparison(outcome):
    with pytest.raises(TypeError, match="compare o estado"):
        bool(outcome)


def test_caller_exception_context_is_suppressed_not_an_internal_leak():
    model = ledger()
    try:
        raise OSError("CANARY_CALLER_CONTEXT")
    except OSError as caller:
        with pytest.raises(BudgetError) as caught:
            model.reserve_auxiliary(shared_bytes=1000)
        assert caught.value.__context__ is caller
        assert caught.value.__suppress_context__
        assert caught.value.__cause__ is None
        assert "CANARY" not in str(caught.value)


def imports_budget(source: str, package: tuple[str, ...]) -> bool:
    target = ("maskgw", "runtime", "budget")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            if any(tuple(name.name.split(".")) == target for name in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            prefix = package[: len(package) - node.level + 1] if node.level else ()
            module = prefix + (() if node.module is None else tuple(node.module.split(".")))
            if module == target or any((*module, name.name) == target for name in node.names):
                return True
    return False


@pytest.mark.parametrize(
    "source,package,expected",
    (
        ("import maskgw.runtime.budget as b", ("maskgw", "gateway"), True),
        ("from maskgw.runtime.budget import BudgetLedger", ("maskgw",), True),
        ("from maskgw.runtime import budget", ("maskgw",), True),
        ("from .budget import BudgetLedger", ("maskgw", "runtime"), True),
        ("from . import budget", ("maskgw", "runtime"), True),
        ("from ..runtime.budget import BudgetLedger", ("maskgw", "gateway"), True),
        ("from . import budget", ("maskgw", "gateway"), False),
        ("'maskgw.runtime.budget'", ("maskgw",), False),
    ),
)
def test_isolation_contraproof_detects_absolute_and_relative_imports(source, package, expected):
    assert imports_budget(source, package) is expected


@pytest.mark.parametrize(
    "action",
    (
        "reserve_candidate",
        "reserve_session",
        "reserve_auxiliary",
        "publish",
        "mark_live",
        "begin_drain",
        "retain",
        "release",
        "begin_shutdown",
        "finish_shutdown",
    ),
)
def test_failed_instance_refuses_every_mutator_without_losing_owners(monkeypatch, action):
    model = ledger()
    gen = generation(model)
    candidate = model.reserve_candidate(1, shared_bytes=10)
    session = model.reserve_session(gen, worker_bytes=4, parent_bytes=6)
    aux = model.reserve_auxiliary(shared_bytes=1)
    original = BudgetLedger._write_image

    def fail_write(self, image):
        original(self, image)
        raise RuntimeError("CANARY_FAIL_WRITE")

    def fail_restore(self, image):
        del self, image
        raise RuntimeError("CANARY_FAIL_RESTORE")

    monkeypatch.setattr(BudgetLedger, "_write_image", fail_write)
    monkeypatch.setattr(BudgetLedger, "_restore_image", fail_restore)
    with pytest.raises(BudgetError):
        model.begin_drain(aux)
    calls: dict[str, Callable[[], object]] = {
        "reserve_candidate": partial(model.reserve_candidate, 0, shared_bytes=1),
        "reserve_session": partial(model.reserve_session, gen, worker_bytes=1, parent_bytes=1),
        "reserve_auxiliary": partial(model.reserve_auxiliary, shared_bytes=1),
        "publish": partial(model.publish, candidate),
        "mark_live": partial(model.mark_live, session),
        "begin_drain": partial(model.begin_drain, gen),
        "retain": partial(model.retain, session),
        "release": partial(model.release, aux, COMPLETE),
        "begin_shutdown": model.begin_shutdown,
        "finish_shutdown": model.finish_shutdown,
    }
    refused(model, BudgetFailure.FAULT, calls[action])
    assert len(model.status.quarantined_entries) == 2
    invariant(model)


@pytest.mark.parametrize("mode", ("skip", "last_epoch"))
def test_partial_epoch_exhaustion_and_last_epoch_release(mode):
    model = ledger()
    slots = list(model._image.slots)
    if mode == "skip":
        slots[0] = replace(slots[0], epoch=(1 << 63) - 1)
    else:
        slots = [replace(slot, epoch=(1 << 63) - 1) for slot in slots]
        slots[0] = replace(slots[0], epoch=(1 << 63) - 2)
    model._image = replace(model._image, slots=tuple(slots))
    token = model.reserve_auxiliary(shared_bytes=1)
    assert token._slot == (1 if mode == "skip" else 0)
    if mode == "last_epoch":
        assert token._epoch == (1 << 63) - 1
        assert dispose(model, token) is ReleaseOutcome.RELEASED
        assert model.release(token, COMPLETE) is ReleaseOutcome.ALREADY_RELEASED
        refused(model, BudgetFailure.CAPACITY, lambda: model.reserve_auxiliary(shared_bytes=1))


def test_admitted_session_can_start_after_generation_replacement():
    model = ledger()
    old = generation(model)
    session = model.reserve_session(old, worker_bytes=4, parent_bytes=6)
    generation(model, replacing=old)
    model.mark_live(session)
    assert entry_at(model, session).generation_slot == old._slot
    assert entry_at(model, session).state is ReservationState.LIVE
    refused(
        model,
        BudgetFailure.STATE,
        lambda: model.reserve_session(
            old,
            worker_bytes=4,
            parent_bytes=6,
        ),
    )
    assert model.release(old, COMPLETE) is ReleaseOutcome.HELD
    assert dispose(model, session) is ReleaseOutcome.RELEASED
    assert model.release(old, COMPLETE) is ReleaseOutcome.RELEASED


@pytest.mark.parametrize(
    "stage,action",
    (
        ("closing", "candidate"),
        ("closing", "session"),
        ("closed", "candidate"),
        ("closed", "session"),
        ("closed", "publish"),
    ),
)
def test_closing_and_closed_refusals(stage, action):
    model = ledger()
    gen = generation(model)
    candidate = model.reserve_candidate(1, shared_bytes=1)
    model.begin_shutdown()
    if stage == "closed":
        assert dispose(model, gen) is ReleaseOutcome.RELEASED
        assert dispose(model, candidate) is ReleaseOutcome.RELEASED
        model.finish_shutdown()
    calls: dict[str, Callable[[], object]] = {
        "candidate": partial(model.reserve_candidate, 0, shared_bytes=1),
        "session": partial(model.reserve_session, gen, worker_bytes=1, parent_bytes=1),
        "publish": partial(model.publish, candidate),
    }
    refused(model, BudgetFailure.CLOSED, calls[action])


@pytest.mark.parametrize(
    "subject,state",
    tuple(
        product(
            ("candidate", "replacing"),
            ("draining", "held", "stale"),
        )
    ),
)
def test_publish_invalid_candidate_or_replacement(subject, state):
    model = ledger()
    gen = generation(model)
    candidate = model.reserve_candidate(0, shared_bytes=1)
    token = candidate if subject == "candidate" else gen
    model.begin_drain(token)
    if state == "held":
        model.retain(token)
    elif state == "stale":
        assert model.release(token, COMPLETE) is ReleaseOutcome.RELEASED
        model.reserve_auxiliary(shared_bytes=1)
    refused(model, BudgetFailure.STATE, lambda: model.publish(candidate, replacing=gen))


@pytest.mark.parametrize("datasource", (0, 1))
@pytest.mark.parametrize("order", tuple(permutations(("publish", "admit", "shutdown"))))
def test_generation_session_shutdown_orders_on_two_datasources(datasource, order):
    model = ledger()
    gens = [generation(model, 0), generation(model, 1)]
    old = gens[datasource]
    candidate = model.reserve_candidate(datasource, shared_bytes=20)
    current = old
    session = None
    for action in order:
        if action == "publish":
            model.publish(candidate, replacing=old)
            current = candidate
        elif action == "admit":
            if model.status.closing:
                refused(
                    model,
                    BudgetFailure.CLOSED,
                    partial(
                        model.reserve_session,
                        current,
                        worker_bytes=4,
                        parent_bytes=6,
                    ),
                )
            else:
                session = model.reserve_session(current, worker_bytes=4, parent_bytes=6)
        else:
            model.begin_shutdown()
        invariant(model)
    if session is not None:
        assert dispose(model, session) is ReleaseOutcome.RELEASED
    for gen in (*gens, candidate):
        assert dispose(model, gen) is ReleaseOutcome.RELEASED
    model.finish_shutdown()


@pytest.mark.parametrize("order", tuple(permutations(("publish", "release_old", "shutdown"))))
def test_withdraw_dispose_publish_shutdown_orders(order):
    model = ledger()
    old = generation(model)
    candidate = model.reserve_candidate(0, shared_bytes=20)
    model.begin_drain(old)  # Withdrawn, but remains charged until confirmed disposal.
    for action in order:
        if action == "publish":
            # No currently published generation remains after withdrawal.
            model.publish(candidate)
        elif action == "release_old":
            assert model.release(old, COMPLETE) is ReleaseOutcome.RELEASED
        else:
            model.begin_shutdown()
        invariant(model)
    assert model.status.generations == 1
    assert model.status.base_bytes == 22
    assert dispose(model, candidate) is ReleaseOutcome.RELEASED
    model.finish_shutdown()
