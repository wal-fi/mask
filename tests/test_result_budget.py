"""Output pins bind real receiver ownership to the existing session credits."""

from __future__ import annotations

from dataclasses import replace

import pytest

from maskgw.runtime.budget import (
    BudgetError,
    BudgetFailure,
    BudgetLedger,
    BudgetLimits,
    BudgetToken,
    CleanupConfirmation,
    DatasourceCapacity,
    OutputReleaseOutcome,
    ReleaseOutcome,
)

COMPLETE = CleanupConfirmation(True, True, True, True, True)


def session() -> tuple[BudgetLedger, BudgetToken]:
    model = BudgetLedger(
        BudgetLimits(10000, 10, 10, 8, 2, 2, 2, 2, 2),
        (DatasourceCapacity(2, 2),),
    )
    generation = model.reserve_candidate(0, shared_bytes=10)
    model.publish(generation)
    token = model.reserve_session(generation, worker_bytes=100, parent_bytes=200)
    model.mark_live(token)
    return model, token


def test_pin_keeps_session_credits_even_with_complete_cleanup_claim():
    model, token = session()
    before = model.status.reserved_bytes
    pin = model.begin_output(token, frame_bytes=80, overhead_bytes=40)
    assert model.status.reserved_bytes == before
    model.begin_drain(token)
    assert model.release(token, COMPLETE) is ReleaseOutcome.HELD
    assert model.end_output(pin, discarded=False) is OutputReleaseOutcome.HELD
    assert model.release(token, COMPLETE) is ReleaseOutcome.HELD
    assert model.end_output(pin, discarded=True) is OutputReleaseOutcome.CLEARED
    assert model.end_output(pin, discarded=True) is OutputReleaseOutcome.ALREADY_CLEARED
    assert model.release(token, COMPLETE) is ReleaseOutcome.RELEASED


def test_second_output_and_insufficient_parent_budget_refuse_without_change():
    model, token = session()
    before = model._image
    with pytest.raises(BudgetError) as caught:
        model.begin_output(token, frame_bytes=80, overhead_bytes=41)
    assert caught.value.category is BudgetFailure.CAPACITY and model._image is before
    model.begin_output(token, frame_bytes=80, overhead_bytes=40)
    pinned = model._image
    with pytest.raises(BudgetError) as caught:
        model.begin_output(token, frame_bytes=1, overhead_bytes=1)
    assert caught.value.category is BudgetFailure.STATE and model._image is pinned


def test_old_output_or_other_ledger_never_clears_current_pin():
    model, token = session()
    old = model.begin_output(token, frame_bytes=1, overhead_bytes=1)
    assert model.end_output(old, discarded=True) is OutputReleaseOutcome.CLEARED
    current = model.begin_output(token, frame_bytes=1, overhead_bytes=1)
    other, _ = session()
    for ledger, pin in ((model, old), (other, current)):
        before = ledger._image
        with pytest.raises(BudgetError):
            ledger.end_output(pin, discarded=True)
        assert ledger._image is before
    assert model.end_output(current, discarded=True) is OutputReleaseOutcome.CLEARED


def test_barrier_blocks_new_output_but_allows_old_pin_cleanup():
    model, token = session()
    pin = model.begin_output(token, frame_bytes=1, overhead_bytes=1)
    model.begin_shutdown()
    assert model.end_output(pin, discarded=True) is OutputReleaseOutcome.CLEARED
    with pytest.raises(BudgetError) as caught:
        model.begin_output(token, frame_bytes=1, overhead_bytes=1)
    assert caught.value.category is BudgetFailure.CLOSED


def test_unconfirmed_discard_is_noop_and_outcome_is_not_boolean():
    model, token = session()
    pin = model.begin_output(token, frame_bytes=1, overhead_bytes=1)
    before = model._image
    assert model.end_output(pin, discarded=False) is OutputReleaseOutcome.HELD
    assert model._image is before
    with pytest.raises(TypeError):
        bool(OutputReleaseOutcome.HELD)


def test_output_epoch_exhaustion_and_slot_reuse_do_not_wrap():
    model, token = session()
    slot = model._image.slots[token._slot]
    assert slot.entry is not None
    slots = list(model._image.slots)
    slots[token._slot] = replace(slot, entry=replace(slot.entry, output_epoch=(1 << 63) - 1))
    model._image = replace(model._image, slots=tuple(slots))
    with pytest.raises(BudgetError) as caught:
        model.begin_output(token, frame_bytes=1, overhead_bytes=1)
    assert caught.value.category is BudgetFailure.CAPACITY


@pytest.mark.parametrize("after_write", [False, True])
@pytest.mark.parametrize("operation", ["begin", "end"])
def test_pin_commit_failure_restores_whole_image(monkeypatch, after_write, operation):
    model, token = session()
    pin = model.begin_output(token, frame_bytes=1, overhead_bytes=1) if operation == "end" else None
    before = model._image

    def broken(self, image):
        if after_write:
            self._image = image
        raise OSError("CANARY_PIN_FAILURE")

    monkeypatch.setattr(BudgetLedger, "_write_image", broken)
    with pytest.raises(BudgetError) as caught:
        if operation == "begin":
            model.begin_output(token, frame_bytes=1, overhead_bytes=1)
        else:
            assert pin is not None
            model.end_output(pin, discarded=True)
    assert model._image is before
    assert caught.value.__context__ is None and "CANARY" not in str(caught.value)


@pytest.mark.parametrize("value", [0, -1, True, 1.5, float("inf"), 1 << 63])
def test_minimum_parent_cost_requires_exact_finite_positive_integer(value):
    model, token = session()
    with pytest.raises(BudgetError) as caught:
        model.begin_output(token, frame_bytes=value, overhead_bytes=1)
    assert caught.value.category is BudgetFailure.INVALID


def test_discard_and_drain_are_one_publication_even_during_shutdown(monkeypatch):
    model, token = session()
    pin = model.begin_output(token, frame_bytes=1, overhead_bytes=1)
    model.begin_shutdown()
    writes = []
    original = BudgetLedger._write_image

    def record(self, image):
        writes.append(image)
        original(self, image)

    monkeypatch.setattr(BudgetLedger, "_write_image", record)
    assert model.end_output(pin, discarded=True, drain=True) is OutputReleaseOutcome.CLEARED
    assert len(writes) == 1
    entry = model.status.entries[token._slot]
    assert entry is not None and entry.state.value == "DRAINING" and not entry.output_pinned
    assert model.release(token, COMPLETE) is ReleaseOutcome.RELEASED
