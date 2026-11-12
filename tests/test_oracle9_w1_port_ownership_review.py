"""Additive public-API review regressions for W1 port ownership (PORT-DESIGN V4 + V4.1).

Reproduces the eight root review probes against V1 (4276d9fc) through the public
``PortOwnership`` surface and the shared deterministic ``FakePump``/``FakeHandle``
harness in ``tests.test_oracle9_w1_port_ownership``, without touching private owner
state, clearing bridge slots, or altering the frozen 171-case suite.
"""

from __future__ import annotations

import enum
import types
from typing import Any

import pytest

from tests import test_oracle9_w1_driver as d1
from tests import test_oracle9_w1_port_ownership as base

core = base.core


def assert_closed_refusal(m: Any, error: BaseException, expected_fault: str | None = None) -> None:
    refusal: Any = error
    assert type(refusal) is m.OwnershipRefusal
    assert type(refusal.category) is m.OwnershipFault
    if expected_fault is not None:
        assert refusal.category is getattr(m.OwnershipFault, expected_fault)
    assert refusal.args == (refusal.category.value,)
    assert refusal.__cause__ is None and refusal.__context__ is None
    text = str(refusal) + repr(refusal)
    assert all(secret not in text for secret in base.SECRET_TEXTS)


def assert_slot_occupied(slot: Any, expected: bool) -> None:
    assert slot.occupied is expected


# ---------------------------------------------------------------- Probe 1: queued spawn & settle


def test_probe1_queued_spawn_stays_open_before_pump_and_settle_pumps_authorize_not_started(
    core: types.ModuleType,
) -> None:
    """Section 7: queued work is never inferred NOT_STARTED before pump runs authorize()."""
    h = base.Harness(core)
    m, owner, pump, b_ns = h.m, h.owner, h.pump, h.b_ns

    slot = b_ns.OperationSlot("spawn")
    owner.gateway().begin_spawn_into(slot, pump.t + 5.0)

    # Before run_until: request is only queued; no authorize/not_started event has occurred.
    assert len(pump.requests) == 1
    assert not any(entry[0] == "pump.authorize" for entry in pump.trace)
    rec_before = h.first_of("SPAWN")
    assert rec_before.gate is m.Gate.ARMED
    assert rec_before.protocol is m.ProtocolState.PENDING
    assert rec_before.physical in (m.PhysicalState.OPEN, m.PhysicalState.UNKNOWN)

    fence = owner.seal()
    assert rec_before.record_id in fence.open_ids or rec_before.record_id in fence.unknown_ids
    assert fence.work_settled_at is None

    # settle() must actually pump the queued request so authorize() -> False -> not_started().
    owner.settle(pump.t + 5.0)
    auth_events = [(entry[1], entry[2]) for entry in pump.trace if entry[0] == "pump.authorized"]
    assert auth_events == [(rec_before.record_id, False)]
    assert pump.handles == {}
    rec_after = h.first_of("SPAWN")
    assert rec_after.gate is m.Gate.NOT_ARMED
    assert rec_after.protocol is m.ProtocolState.NOT_STARTED
    assert rec_after.physical is m.PhysicalState.NOT_STARTED


# ---------------------------------------------------------------- Probe 2: immutable spawn outcome


def test_probe2_late_start_failed_after_observed_spawn_outcome_preserves_cached_protocol(
    core: types.ModuleType,
) -> None:
    """Section 5.1 & 7: once spawn outcome(True) is observed, late start_failed cannot mutate it."""
    h = base.Harness(core)
    m, owner, pump, b_ns = h.m, h.owner, h.pump, h.b_ns

    slot = b_ns.OperationSlot("spawn")
    owner.gateway().begin_spawn_into(slot, pump.t + 5.0)
    owner.clock().poll((slot,), pump.t + 5.0)

    first_outcome = slot.op.outcome()
    assert first_outcome.ok is True and first_outcome.process is not None
    spawn_before = h.first_of("SPAWN")
    assert spawn_before.protocol is m.ProtocolState.SUCCEEDED
    assert spawn_before.protocol_at is not None
    gw_handle = pump.gateway_handle
    assert gw_handle is not None

    pump.schedule_at(pump.t + base.DT, gw_handle.events.start_failed)
    owner.seal()
    owner.settle(pump.t + 1.0)

    # Cached op outcome object and record protocol snapshot remain strictly immutable.
    assert slot.op.outcome() is first_outcome
    assert first_outcome.ok is True and first_outcome.process is not None
    spawn_after = h.first_of("SPAWN")
    assert spawn_after.protocol is m.ProtocolState.SUCCEEDED
    assert spawn_after.protocol_at == spawn_before.protocol_at
    assert m.FaultKind.START in spawn_after.faults
    assert spawn_after.physical is m.PhysicalState.OPEN
    assert owner.custody().entries != ()


# ---------------------------------------------------------------- Probe 3: late child in poll


def test_probe3_late_helper_settlement_during_poll_without_seal_keeps_act_pending_with_fresh_time(
    core: types.ModuleType,
) -> None:
    """Section 5.5 & 7: helper settling at deadline + DT in poll keeps ACT
    PENDING and fresh time.
    """
    pump = base.FakePump()
    pump.push_child_script("act-term-0", base.ChildScript(start_mode="never_settle"))
    h = base.Harness(core, pump=pump)
    m, owner = h.m, h.owner

    act = h.make_act("TERMINATE_ONE_BACKEND", 20, window=1.0)
    slot = h.run_act(act)
    assert slot.op.done() is False
    act_before = h.first_of("ACT")
    child_before = h.first_of("CHILD")
    assert act_before.protocol is m.ProtocolState.PENDING
    assert child_before.physical is m.PhysicalState.OPEN

    child_handle = pump.handles[child_before.record_id]
    event_at = act.deadline + base.DT

    def deliver_late_child_exit() -> None:
        child_handle.events.data(1, base.terminate_line())
        child_handle.settle_exit(0)

    pump.schedule_at(event_at, deliver_late_child_exit)
    owner.clock().poll((slot,), act.deadline + 2 * base.DT)

    # Op stays pending (never call slot.op.outcome()); protocol never flips to SUCCEEDED.
    assert slot.op.done() is False
    act_after = h.first_of("ACT")
    assert act_after.protocol is m.ProtocolState.PENDING
    assert act_after.protocol_at is None
    assert act_after.settled_at == event_at
    assert any(lf.kind is m.LateKind.CHILD_DONE and lf.at == event_at for lf in act_after.late)

    child_after = h.first_of("CHILD")
    assert child_after.physical is m.PhysicalState.SETTLED_RETAINED
    assert child_after.settled_at == event_at
    assert child_after.late != ()
    assert all(lf.at == event_at for lf in child_after.late)


# ---------------------------------------------------------------- Probe 4: write_limits OSError


def test_probe4_write_limits_oserror_in_begin_write_raises_closed_sanitized_refusal(
    core: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Precondition handle.write_limits() raising OSError must not leak raw exception or canary."""
    h = base.Harness(core)
    m, pump, b_ns = h.m, h.pump, h.b_ns
    proc, gw_handle = h.spawn_gateway()
    pump.gateway_auto_respond = False

    def broken_write_limits() -> tuple[int, int]:
        raise OSError(base.STDERR_CANARY)

    monkeypatch.setattr(gw_handle, "write_limits", broken_write_limits)
    w_slot = b_ns.OperationSlot("write")
    with pytest.raises(m.OwnershipRefusal) as caught:
        proc.begin_write_into(w_slot, d1.frame(base.GO, 1, 1), pump.t + 5.0)
    assert_closed_refusal(m, caught.value)
    assert gw_handle.writes == []


# ---------------------------------------------------------------- Probe 5: write_limits control


def test_probe5_write_limits_keyboard_interrupt_records_first_control_and_closes_work(
    core: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Control BaseException in write_limits() must record first_control and block later work."""
    h = base.Harness(core)
    m, owner, pump, b_ns = h.m, h.owner, h.pump, h.b_ns
    proc, gw_handle = h.spawn_gateway()
    pump.gateway_auto_respond = False
    control = KeyboardInterrupt("write-limits-control")

    def interrupt_write_limits() -> tuple[int, int]:
        raise control

    monkeypatch.setattr(gw_handle, "write_limits", interrupt_write_limits)
    w_slot = b_ns.OperationSlot("write")
    with pytest.raises(KeyboardInterrupt) as caught:
        proc.begin_write_into(w_slot, d1.frame(base.GO, 1, 1), pump.t + 5.0)
    assert caught.value is control
    assert owner.first_control() is control
    assert gw_handle.writes == []

    records_before = len(owner.records())
    requests_before = len(pump.requests)
    act_slot = b_ns.OperationSlot("act")
    act = h.make_act("ZERO_BACKENDS", 24, token=11)
    with pytest.raises(m.OwnershipRefusal) as work_refused:
        owner.acts().begin_act_into(act_slot, act, act.deadline)
    assert_closed_refusal(m, work_refused.value)
    assert act_slot.occupied is False
    assert (len(owner.records()), len(pump.requests)) == (
        records_before,
        requests_before,
    )
    assert owner.first_control() is control


# ---------------------------------------------------------------- Probe 6: read bind __context__


def test_probe6_read_slot_bind_oserror_raises_closed_port_refusal_without_context(
    core: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OperationSlot.bind raising OSError on read must raise PORT with __context__ is None."""
    h = base.Harness(core)
    m, pump, b_ns = h.m, h.pump, h.b_ns
    proc, _ = h.spawn_gateway()
    genuine_bind = b_ns.OperationSlot.bind

    def failing_read_bind(slot: Any, op: object) -> None:
        if slot.name == "read":
            raise OSError(base.STDERR_CANARY)
        genuine_bind(slot, op)

    monkeypatch.setattr(b_ns.OperationSlot, "bind", failing_read_bind)
    r_slot = b_ns.OperationSlot("read")
    with pytest.raises(m.OwnershipRefusal) as caught:
        proc.begin_read_into(r_slot, 16, pump.t + 5.0)
    base.assert_refusal(m, caught.value, "PORT")
    assert r_slot.occupied is False


# ---------------------------------------------------------------- Probe 7: HelperRaw validation


INVALID_HELPER_RAW_CASES: list[tuple[str, dict[str, object]]] = [
    ("bool-index", {"index": True}),
    ("negative-index", {"index": -1}),
    ("overflow-index", {"index": 24}),
    ("bool-code", {"code": False}),
    ("negative-code", {"code": -1}),
    ("overflow-code", {"code": 256}),
    ("oversize-stdout", {"stdout": b"x" * (base.CHILD_STDOUT_CAP + 1)}),
    ("str-stdout", {"stdout": "not-bytes"}),
    ("negative-stdout-dropped", {"stdout_dropped": -1}),
    ("bool-stdout-dropped", {"stdout_dropped": True}),
    ("negative-stderr-bytes", {"stderr_bytes": -1}),
    ("bool-stderr-bytes", {"stderr_bytes": True}),
]


@pytest.mark.parametrize(
    ("case_id", "overrides"),
    INVALID_HELPER_RAW_CASES,
    ids=[item[0] for item in INVALID_HELPER_RAW_CASES],
)
def test_probe7_helper_raw_rejects_invalid_field_types_and_domains(
    case_id: str, overrides: dict[str, object]
) -> None:
    """Section 3: HelperRaw validates exact int/bytes types and closed domains."""
    assert case_id
    m = base.ownership_module()
    fields: dict[str, object] = {
        "index": 0,
        "code": 0,
        "stdout": b"",
        "stdout_dropped": 0,
        "stderr_bytes": 0,
        **overrides,
    }
    with pytest.raises(m.OwnershipRefusal) as caught:
        m.HelperRaw(**fields)
    assert_closed_refusal(m, caught.value)


def test_probe7_helper_raw_accepts_valid_boundary_values() -> None:
    m = base.ownership_module()
    low = m.HelperRaw(index=0, code=None, stdout=b"", stdout_dropped=0, stderr_bytes=0)
    high = m.HelperRaw(
        index=23,
        code=255,
        stdout=b"a" * base.CHILD_STDOUT_CAP,
        stdout_dropped=0,
        stderr_bytes=0,
    )
    assert (low.index, low.code, low.stdout, low.stdout_dropped, low.stderr_bytes) == (
        0,
        None,
        b"",
        0,
        0,
    )
    assert (high.index, high.code, len(high.stdout)) == (23, 255, base.CHILD_STDOUT_CAP)
    assert repr(low) == repr(high) and "<" in repr(low)


# ---------------------------------------------------------------- Probe 8: enum alias in namespace


class AliasedDelivery(enum.Enum):
    NOT_SENT = "NOT_SENT"
    SENT = "SENT"
    UNKNOWN = "UNKNOWN"
    EXTRA_ALIAS = "NOT_SENT"


def test_probe8_reactor_namespace_rejects_enum_alias_and_accepts_exact_namespace() -> None:
    """Section 2.4: __members__ must match exact enum member names without hidden aliases."""
    m = base.ownership_module()
    pump = base.FakePump()
    b_ns = base.bridge_mod()
    good_r_ns = base.reactor_mod()
    plan = base.make_plan(m, good_r_ns)
    limits = m.OwnerLimits()

    bad_r_ns = base.reactor_variant(Delivery=AliasedDelivery)
    assert type(bad_r_ns) is types.ModuleType
    assert "EXTRA_ALIAS" in AliasedDelivery.__members__
    with pytest.raises(m.OwnershipRefusal) as caught:
        m.PortOwnership(pump, plan, limits, bridge_ns=b_ns, reactor_ns=bad_r_ns)
    base.assert_refusal(m, caught.value, "NAMESPACE")
    assert pump.trace == []

    owner = m.PortOwnership(pump, plan, limits, bridge_ns=b_ns, reactor_ns=good_r_ns)
    assert owner.records() == ()
    assert pump.trace == []


# ---------------------------------------------------------------- Probe 9: second WAIT refused


def test_probe9_second_wait_refused_before_bind_and_first_wait_resolves_on_exit(
    core: types.ModuleType,
) -> None:
    """Section 5.4: at most one WAIT per owner life; second WAIT is refused cleanly."""
    h = base.Harness(core)
    m, owner, pump, b_ns = h.m, h.owner, h.pump, h.b_ns
    proc, gw_handle = h.spawn_gateway()

    wait_slot_1 = b_ns.OperationSlot("wait")
    proc.begin_wait_into(wait_slot_1, pump.t + 5.0)
    assert wait_slot_1.occupied is True
    first_wait_op = wait_slot_1.op
    assert first_wait_op is not None
    assert first_wait_op.done() is False
    assert len(h.records_of("WAIT")) == 1

    records_before = len(owner.records())
    wait_slot_2 = b_ns.OperationSlot("wait")
    with pytest.raises(m.OwnershipRefusal) as caught:
        proc.begin_wait_into(wait_slot_2, pump.t + 5.0)
    assert_closed_refusal(m, caught.value)
    assert wait_slot_2.occupied is False
    assert len(owner.records()) == records_before
    assert len(h.records_of("WAIT")) == 1
    assert wait_slot_1.op is first_wait_op
    assert first_wait_op.done() is False

    def deliver_gateway_exit() -> None:
        gw_handle.settle_exit(0)

    pump.schedule_at(pump.t + base.DT, deliver_gateway_exit)
    owner.clock().poll((wait_slot_1,), pump.t + 1.0)
    assert wait_slot_1.op is first_wait_op
    assert first_wait_op.done() is True
    assert first_wait_op.outcome().code == 0
    assert h.first_of("WAIT").protocol is m.ProtocolState.SUCCEEDED


# ---------------------------------------------------------------- Probe 10: overlapping READ


def test_probe10_overlapping_pending_read_refused_then_sequential_read_succeeds(
    core: types.ModuleType,
) -> None:
    """Section 5.2: second pending READ is refused; next READ after completion works."""
    pump = base.FakePump()
    pump.gateway_emit_guard = False
    h = base.Harness(core, pump=pump)
    m, owner, b_ns = h.m, h.owner, h.b_ns
    proc, gw_handle = h.spawn_gateway()

    read_slot_1 = b_ns.OperationSlot("read")
    proc.begin_read_into(read_slot_1, 1, pump.t + 5.0)
    assert read_slot_1.occupied is True
    first_read_op = read_slot_1.op
    assert first_read_op is not None
    assert first_read_op.done() is False

    records_before = len(owner.records())
    read_slot_2 = b_ns.OperationSlot("read")
    with pytest.raises(m.OwnershipRefusal) as caught:
        proc.begin_read_into(read_slot_2, 1, pump.t + 5.0)
    assert_closed_refusal(m, caught.value)
    assert_slot_occupied(read_slot_2, False)
    assert len(owner.records()) == records_before
    assert read_slot_1.op is first_read_op
    assert first_read_op.done() is False

    def emit_x() -> None:
        gw_handle.events.data(1, b"X")

    pump.schedule_at(pump.t + base.DT, emit_x)
    owner.clock().poll((read_slot_1,), pump.t + 1.0)
    assert first_read_op.done() is True
    first_outcome = first_read_op.outcome()
    assert first_outcome.ok is True
    assert first_outcome.data == b"X"

    proc.begin_read_into(read_slot_2, 1, pump.t + 5.0)
    assert_slot_occupied(read_slot_2, True)
    second_read_op = read_slot_2.op
    assert second_read_op is not None
    assert second_read_op.done() is False

    def emit_y() -> None:
        gw_handle.events.data(1, b"Y")

    pump.schedule_at(pump.t + base.DT, emit_y)
    owner.clock().poll((read_slot_2,), pump.t + 1.0)
    assert second_read_op.done() is True
    second_outcome = second_read_op.outcome()
    assert second_outcome.ok is True
    assert second_outcome.data == b"Y"

    assert read_slot_1.op is first_read_op
    assert first_read_op.outcome() is first_outcome
    assert first_outcome.ok is True
    assert first_outcome.data == b"X"


# ---------------------------------------------------------------- Probe 11: poll raw op refused


def test_probe11_clock_poll_rejects_raw_operation_handle_before_run_until(
    core: types.ModuleType,
) -> None:
    """Section 3 & 4: clock().poll requires OperationSlots, refusing raw op as PORT."""
    h = base.Harness(core)
    m, owner, pump, b_ns = h.m, h.owner, h.pump, h.b_ns

    slot = b_ns.OperationSlot("spawn")
    owner.gateway().begin_spawn_into(slot, pump.t + 5.0)
    own_op = slot.op
    assert own_op is not None
    run_until_before = [
        entry for entry in pump.trace if entry[0] in ("pump.run_until.enter", "pump.run_until.exit")
    ]
    requests_before = len(pump.requests)
    handles_before = dict(pump.handles)

    with pytest.raises(m.OwnershipRefusal) as caught:
        owner.clock().poll((own_op,), pump.t + 5.0)
    base.assert_refusal(m, caught.value, "PORT")
    run_until_after = [
        entry for entry in pump.trace if entry[0] in ("pump.run_until.enter", "pump.run_until.exit")
    ]
    assert run_until_after == run_until_before
    assert len(pump.requests) == requests_before
    assert pump.handles == handles_before
    assert own_op.done() is False

    owner.clock().poll((slot,), pump.t + 5.0)
    assert own_op.done() is True
    outcome = own_op.outcome()
    assert outcome.ok is True and outcome.process is not None
