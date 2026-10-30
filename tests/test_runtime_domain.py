"""B2-C1 contract tests: accounting is not OS evidence or SQL activation."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any, cast

import pytest

from maskgw.runtime import domain
from maskgw.runtime.budget import (
    BudgetLedger,
    BudgetLimits,
    CleanupConfirmation,
    DatasourceCapacity,
    ReleaseOutcome,
)
from maskgw.runtime.domain import (
    LINUX_HELD_AS128,
    WINDOWS_JOB_PRIVATE32,
    AggregateKind,
    Cost,
    CostLocation,
    CostOwner,
    CostPlan,
    Coverage,
    DomainProfile,
    DomainReason,
    MemberKind,
    Quantity,
    reconcile,
)

ROOT = Path(__file__).resolve().parents[1]
Q = Quantity.VIRTUAL_ADDRESS_SPACE
IN = CostLocation.IN_DOMAIN
OUT = CostLocation.OUT_OF_DOMAIN


def limits(**changes: int) -> BudgetLimits:
    values = {
        "total_bytes": 10000,
        "base_bytes": 200,
        "headroom_bytes": 100,
        "entries": 8,
        "sessions": 2,
        "workers": 2,
        "candidates": 1,
        "generations": 2,
        "auxiliaries": 1,
    }
    return BudgetLimits(**(values | changes))


# Any is confined to adversarial overrides that deliberately build wrong-type records.
def plan(**changes: Any) -> CostPlan:
    costs = (
        Cost(1, CostOwner.BASE, IN, Q, 200, 1),
        Cost(2, CostOwner.HEADROOM, IN, Q, 100, 1),
        Cost(3, CostOwner.WORKER, IN, Q, 256, 2),
        Cost(4, CostOwner.PARENT, IN, Q, 256, 2),
        Cost(5, CostOwner.CANDIDATE, IN, Q, 50, 1),
        Cost(6, CostOwner.GENERATION, IN, Q, 50, 2),
        Cost(7, CostOwner.AUXILIARY, IN, Q, 64, 1),
    )
    baseline = CostPlan(
        quantity=Q,
        costs=costs,
        supervisor_cost_id=1,
        supervisor_threads=2,
        worker_threads=1,
        auxiliary_threads=1,
        fixed_auxiliaries=0,
        fixed_auxiliary_threads=1,
        fixed_auxiliary_cost_id=None,
        frame_bytes=80,
        output_overhead_bytes=40,
    )
    return replace(baseline, **changes)


def hypothetical(**changes: Any) -> DomainProfile:
    # NEVER registered as trusted, including when every field claims proof.
    baseline = DomainProfile(
        name="synthetic",
        evidence="not-measured",
        member_kind=MemberKind.AS_VIRTUAL,
        member_quantity=Q,
        member_bytes=128,
        aggregate_kind=AggregateKind.STRICT_PROVEN,
        aggregate_quantity=Q,
        aggregate_bytes=10000,
        observed_peak_bytes=9999,
        vectors=(Coverage.DOMAIN_PROVEN,) * len(domain.CoverageVector),
        max_processes=16,
        max_tasks=64,
        members_attached_at_creation=True,
        supervisor_attached_at_creation=True,
        limits_before_work=True,
        owner_loss_cleanup_proven=True,
    )
    return replace(baseline, **changes)


def changed_cost(subject: CostPlan, identifier: int, **changes: Any) -> CostPlan:
    return replace(
        subject,
        costs=tuple(
            replace(cost, **changes) if cost.identity == identifier else cost
            for cost in subject.costs
        ),
    )


def reasons(
    subject: CostPlan | None = None,
    profile: DomainProfile | None = None,
    budget: BudgetLimits | None = None,
) -> tuple[DomainReason, ...]:
    verdict = reconcile(
        hypothetical() if profile is None else profile,
        plan() if subject is None else subject,
        limits() if budget is None else budget,
    )
    assert verdict.ready is False
    assert type(verdict.reasons) is tuple
    assert len(verdict.reasons) <= len(DomainReason)
    assert len(set(verdict.reasons)) == len(verdict.reasons)
    return verdict.reasons


def test_hypothetical_complete_plan_cannot_self_certify():
    verdict = reconcile(hypothetical(), plan(), limits())
    assert verdict.reasons == (DomainReason.UNVERIFIED_PROFILE,)
    assert (verdict.inside_bytes, verdict.outside_bytes) == (1538, 0)
    assert verdict.total_bytes == 1538
    assert not verdict.ready


@pytest.mark.parametrize("profile", [LINUX_HELD_AS128, WINDOWS_JOB_PRIVATE32])
def test_every_real_profile_is_not_ready_for_exact_measured_reasons(profile):
    result = reasons(profile=profile)
    assert DomainReason.UNVERIFIED_PROFILE not in result
    assert DomainReason.AGGREGATE_UNPROVEN in result
    assert DomainReason.COVERAGE_GAP in result
    assert DomainReason.CLEANUP_UNPROVEN in result
    assert profile.evidence.startswith("docs/PHASE-9-STAGE-8-")


@pytest.mark.parametrize("profile", [LINUX_HELD_AS128, WINDOWS_JOB_PRIVATE32])
def test_clone_of_trusted_record_is_still_unverified(profile):
    clone = replace(profile)
    assert clone == profile and clone is not profile
    assert DomainReason.UNVERIFIED_PROFILE in reasons(profile=clone)


def test_windows_shared_section_gap_is_recorded_as_measured_not_unknown():
    index = tuple(domain.CoverageVector).index(domain.CoverageVector.SHARED_ANON)
    assert WINDOWS_JOB_PRIVATE32.vectors[index].value == "GAP_OBSERVED"
    assert DomainReason.COVERAGE_GAP in reasons(profile=WINDOWS_JOB_PRIVATE32)


def test_coverage_vector_order_is_part_of_the_closed_record_contract():
    assert tuple(vector.value for vector in domain.CoverageVector) == (
        "PRIVATE_MAPPED",
        "SHARED_ANON",
        "TMPFS_WRITE",
        "PAGE_CACHE",
        "KERNEL_SOCKET_PIPE",
        "LISTENER_TLS_OUTPUT",
        "SUPERVISOR",
        "AUXILIARY",
        "GENERATION_CANDIDATE",
        "SNAPSHOT",
    )


@pytest.mark.parametrize("worker_bytes,under", [(127, True), (128, False), (129, False)])
def test_reservation_covers_imposed_limit_not_the_inverse(worker_bytes, under):
    result = reasons(changed_cost(plan(), 3, bytes_per_slot=worker_bytes))
    assert (DomainReason.WORKER_UNDER_RESERVED in result) is under


def test_same_generation_in_base_and_reservation_is_double_charge():
    subject = replace(
        plan(),
        costs=(
            *plan().costs,
            Cost(6, CostOwner.BASE, IN, Q, 10, 1),
        ),
    )
    assert DomainReason.DOUBLE_CHARGE in reasons(subject)


@pytest.mark.parametrize("owner", list(CostOwner))
def test_every_cost_needs_exactly_one_identity_owner(owner):
    subject = replace(
        plan(),
        costs=(
            *plan().costs,
            Cost(3, owner, IN, Q, 1, 1),
        ),
    )
    assert DomainReason.DOUBLE_CHARGE in reasons(subject)


def test_external_generation_without_own_evidence_blocks_even_when_inside_fits():
    result = reconcile(hypothetical(), changed_cost(plan(), 6, location=OUT), limits())
    assert DomainReason.OUTSIDE_UNPROVEN in result.reasons
    assert result.inside_bytes == 1438 and result.outside_bytes == 100


def test_external_cost_cannot_borrow_unused_capacity_from_inside():
    subject = changed_cost(plan(), 6, location=OUT, bound=LINUX_HELD_AS128)
    result = reasons(subject, hypothetical(aggregate_bytes=1000000))
    assert DomainReason.OUTSIDE_UNPROVEN in result
    assert DomainReason.UNIT_MISMATCH in result


def test_outside_bound_cannot_be_a_forged_strict_record():
    subject = changed_cost(plan(), 6, location=OUT, bound=hypothetical())
    assert DomainReason.OUTSIDE_UNPROVEN in reasons(subject)


def test_outside_costs_share_their_own_bound_without_cross_domain_offset():
    quantity = Quantity.RESIDENT_AND_CHARGED
    subject = replace(
        plan(),
        quantity=quantity,
        costs=tuple(replace(cost, quantity=quantity) for cost in plan().costs),
    )
    subject = changed_cost(
        subject, 5, location=OUT, bytes_per_slot=100 * 1024 * 1024, bound=LINUX_HELD_AS128
    )
    subject = changed_cost(
        subject, 6, location=OUT, bytes_per_slot=50 * 1024 * 1024, bound=LINUX_HELD_AS128
    )
    # Each component fits 192 MiB; their shared outside sum (200 MiB) does not.
    result = reasons(
        subject,
        hypothetical(aggregate_quantity=quantity, member_quantity=quantity),
        limits(total_bytes=1024 * 1024 * 1024),
    )
    assert DomainReason.DOMAIN_LIMIT in result and DomainReason.OUTSIDE_UNPROVEN in result


def test_quantities_never_mix_inside_outside_or_with_the_domain():
    subject = changed_cost(plan(), 6, location=OUT, quantity=Quantity.RESIDENT_AND_CHARGED)
    assert DomainReason.UNIT_MISMATCH in reasons(subject)
    assert DomainReason.UNIT_MISMATCH in reasons(
        profile=hypothetical(aggregate_quantity=Quantity.RESIDENT_AND_CHARGED)
    )
    assert DomainReason.UNIT_MISMATCH in reasons(
        profile=hypothetical(member_quantity=Quantity.PRIVATE_COMMIT)
    )


def test_mixed_cost_units_never_publish_a_meaningless_numeric_total():
    subject = changed_cost(plan(), 6, location=OUT, quantity=Quantity.RESIDENT_AND_CHARGED)
    verdict = reconcile(hypothetical(), subject, limits())
    assert (verdict.inside_bytes, verdict.outside_bytes, verdict.total_bytes) == (0, 0, 0)
    assert verdict.reasons == (DomainReason.UNIT_MISMATCH,)


@pytest.mark.parametrize(
    "kind,quantity",
    [
        (MemberKind.AS_VIRTUAL, Quantity.PRIVATE_COMMIT),
        (MemberKind.JOB_PRIVATE, Quantity.VIRTUAL_ADDRESS_SPACE),
    ],
)
def test_member_kind_cannot_be_relabelled_to_match_the_plan(kind, quantity):
    subject = replace(
        plan(),
        quantity=quantity,
        costs=tuple(replace(cost, quantity=quantity) for cost in plan().costs),
    )
    profile = hypothetical(member_kind=kind, member_quantity=quantity, aggregate_quantity=quantity)
    assert DomainReason.UNIT_MISMATCH in reasons(subject, profile)


@pytest.mark.parametrize("kind", [AggregateKind.NONE, AggregateKind.TRANSIENT_DOCUMENTED])
def test_margin_or_low_observed_peak_cannot_certify_aggregate(kind):
    profile = hypothetical(
        aggregate_kind=kind,
        aggregate_bytes=None if kind is AggregateKind.NONE else 1000000,
        observed_peak_bytes=1,
    )
    assert DomainReason.AGGREGATE_UNPROVEN in reasons(profile=profile)


@pytest.mark.parametrize("coverage", [Coverage.UNKNOWN, Coverage.MEMBER_ONLY])
def test_uncovered_vectors_never_pass(coverage):
    profile = hypothetical(vectors=(coverage,) * len(domain.CoverageVector))
    assert DomainReason.COVERAGE_GAP in reasons(profile=profile)


@pytest.mark.parametrize(
    "field",
    [
        "members_attached_at_creation",
        "supervisor_attached_at_creation",
        "limits_before_work",
        "owner_loss_cleanup_proven",
    ],
)
def test_missing_creation_limit_or_owner_loss_proof_blocks(field):
    result = reasons(profile=hypothetical(**{field: False}))
    expected = (
        DomainReason.CLEANUP_UNPROVEN
        if field == "owner_loss_cleanup_proven"
        else DomainReason.CREATION_UNPROVEN
    )
    assert expected in result


@pytest.mark.parametrize("processes,tasks", [(3, 64), (16, 4), (None, 64), (16, None)])
def test_supervisor_workers_and_auxiliary_threads_all_count(processes, tasks):
    # 1 supervisor + 2 workers + 1 auxiliary; 2+2+1 tasks = 5.
    assert DomainReason.TOPOLOGY in reasons(
        profile=hypothetical(max_processes=processes, max_tasks=tasks)
    )


def test_tasks_are_not_just_processes_and_fixed_auxiliaries_count():
    extra = Cost(8, CostOwner.BASE, IN, Q, 10, 2)
    subject = replace(
        plan(),
        costs=(*plan().costs, extra),
        fixed_auxiliaries=2,
        fixed_auxiliary_threads=3,
        fixed_auxiliary_cost_id=8,
    )
    assert DomainReason.TOPOLOGY in reasons(
        subject, hypothetical(max_processes=5), limits(base_bytes=220)
    )
    assert DomainReason.TOPOLOGY in reasons(
        subject, hypothetical(max_tasks=10), limits(base_bytes=220)
    )


def test_supervisor_and_bootstrap_must_be_fixed_inside_cost():
    assert DomainReason.SUPERVISOR_COST in reasons(replace(plan(), supervisor_cost_id=6))
    assert DomainReason.SUPERVISOR_COST in reasons(changed_cost(plan(), 1, location=OUT))


@pytest.mark.parametrize("missing", list(CostOwner))
def test_missing_cost_category_not_silently_zero(missing):
    subject = replace(plan(), costs=tuple(c for c in plan().costs if c.owner is not missing))
    assert DomainReason.MISSING_COST in reasons(subject)


def test_budget_and_domain_checks_keep_exact_boundary_and_one_byte_excess():
    for total, expected in [(1538, False), (1537, True)]:
        result = reasons(budget=limits(total_bytes=total))
        assert (DomainReason.BUDGET_EXCEEDED in result) is expected
        result = reasons(profile=hypothetical(aggregate_bytes=total))
        assert (DomainReason.DOMAIN_LIMIT in result) is expected


@pytest.mark.parametrize("parent_bytes,short", [(199, True), (200, False), (201, False)])
def test_output_reserves_two_frames_and_overhead(parent_bytes, short):
    result = reasons(changed_cost(plan(), 4, bytes_per_slot=parent_bytes))
    assert (DomainReason.OUTPUT_UNDER_RESERVED in result) is short


@pytest.mark.parametrize("identifier,count", [(3, 1), (3, 3), (4, 1), (5, 2), (6, 1), (7, 2)])
def test_plan_counts_match_existing_ledger_capacities(identifier, count):
    assert DomainReason.CAPACITY in reasons(changed_cost(plan(), identifier, slots=count))


def test_all_sessions_need_persistent_workers():
    assert DomainReason.TOPOLOGY in reasons(budget=limits(sessions=3))


@pytest.mark.parametrize("value", [True, False, -1, 0, 1.0, float("nan"), 1 << 63, "secret"])
def test_bad_cost_integer_is_rejected_without_exposing_it(value):
    result = reconcile(hypothetical(), changed_cost(plan(), 3, bytes_per_slot=value), limits())
    assert result.reasons == (DomainReason.INVALID,)
    assert "secret" not in repr(result)


@pytest.mark.parametrize(
    "field",
    [
        "supervisor_threads",
        "worker_threads",
        "auxiliary_threads",
        "frame_bytes",
        "output_overhead_bytes",
    ],
)
@pytest.mark.parametrize("value", [True, 0, -1, 1.5])
def test_plan_numbers_are_bounded_exact_integers(field, value):
    assert reasons(replace(plan(), **{field: value})) == (DomainReason.INVALID,)


@pytest.mark.parametrize("costs", [[], (), (None,), tuple([plan().costs[0]] * 65)])
def test_collection_is_closed_bounded_tuple(costs):
    assert reasons(replace(plan(), costs=costs)) == (DomainReason.INVALID,)


def test_no_numeric_overflow_in_products_sums_or_frame_copies():
    for subject in (
        changed_cost(plan(), 3, bytes_per_slot=(1 << 63) - 1),
        replace(plan(), frame_bytes=(1 << 63) - 1),
    ):
        assert reasons(subject) == (DomainReason.INVALID,)


def test_unsupported_owner_is_invalid_without_custom_equality_or_callbacks():
    class Hostile:
        def __hash__(self) -> int:
            raise AssertionError("never hash unvalidated input")

        def __eq__(self, _other: object) -> bool:
            raise AssertionError("never compare unvalidated input")

    subject = changed_cost(plan(), 3, owner=Hostile())
    assert reasons(subject) == (DomainReason.INVALID,)
    assert reconcile(cast(DomainProfile, Hostile()), plan(), limits()).reasons == (
        DomainReason.INVALID,
    )


def test_errors_during_reconciliation_return_closed_fault_without_chain(monkeypatch):
    def fail(*_args, **_kwargs):
        raise MemoryError("secret-value")

    monkeypatch.setattr(domain, "_totals", fail)
    result = reconcile(hypothetical(), plan(), limits())
    assert result.reasons == (DomainReason.FAULT,)
    assert "secret" not in repr(result)


def test_reconciliation_never_changes_live_ledger_or_held_output():
    model = BudgetLedger(limits(), (DatasourceCapacity(2, 1),))
    generation = model.reserve_candidate(0, shared_bytes=50)
    model.publish(generation)
    token = model.reserve_session(generation, worker_bytes=256, parent_bytes=256)
    model.mark_live(token)
    pin = model.begin_output(token, frame_bytes=80, overhead_bytes=40)
    before = model.status
    reasons(budget=limits())
    assert model.status == before
    complete = CleanupConfirmation(True, True, True, True, True)
    model.begin_drain(token)
    assert model.release(token, complete) is ReleaseOutcome.HELD
    assert model.status.available_bytes == before.available_bytes
    model.end_output(pin, discarded=True)
    assert model.release(token, complete) is ReleaseOutcome.RELEASED


def test_records_are_immutable_and_never_implicitly_truthy():
    subject = plan()
    with pytest.raises(FrozenInstanceError):
        subject.quantity = Quantity.PRIVATE_COMMIT  # type: ignore[misc]  # runtime immutability
    verdict = reconcile(hypothetical(), subject, limits())
    with pytest.raises(TypeError):
        bool(verdict)
    assert repr(subject) == "CostPlan(<logical-only>)"
    assert repr(hypothetical()) == "DomainProfile(<evidence-only>)"


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "x" * 257),
        ("evidence", "segredo\u00e7"),
        ("member_kind", "AS_VIRTUAL"),
        ("aggregate_kind", "STRICT_PROVEN"),
        ("vectors", []),
        ("vectors", (Coverage.DOMAIN_PROVEN,)),
        ("max_processes", True),
        ("max_tasks", 0),
        ("members_attached_at_creation", 1),
        ("member_bytes", 0),
    ],
)
def test_partial_or_relabelled_profile_is_invalid_not_an_evidence_record(field, value):
    result = reasons(profile=hypothetical(**{field: value}))
    assert result == (DomainReason.INVALID,)


def imports_domain(source: str, package: tuple[str, ...]) -> bool:
    target = ("maskgw", "runtime", "domain")
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
    [
        ("import maskgw.runtime.domain as d", ("maskgw", "gateway"), True),
        ("from maskgw.runtime import domain", ("maskgw",), True),
        ("from .domain import reconcile", ("maskgw", "runtime"), True),
        ("from . import domain", ("maskgw", "runtime"), True),
        ("from ..runtime import domain", ("maskgw", "gateway"), True),
        ("from . import domain", ("maskgw", "gateway"), False),
        ("'maskgw.runtime.domain'", ("maskgw",), False),
    ],
)
def test_isolation_contraproof_resolves_relative_and_absolute_imports(source, package, expected):
    assert imports_domain(source, package) is expected


def test_core_has_no_io_or_operational_caller():
    source = ROOT / "src/maskgw/runtime/domain.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    assert all(
        node.module in {"__future__", "dataclasses", "enum", "typing", "maskgw.runtime.budget"}
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    forbidden = {"open", "print", "exec", "eval", "__import__"}
    assert not any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in forbidden
        for node in ast.walk(tree)
    )
    for path in (ROOT / "src/maskgw").rglob("*.py"):
        if path != source:
            text = path.read_text(encoding="utf-8")
            package = path.relative_to(ROOT / "src").parts[:-1]
            assert not imports_domain(text, package), path
            assert "maskgw.runtime.domain" not in text, path
