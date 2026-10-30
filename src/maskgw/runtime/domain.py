"""B2-C1: pure reconciliation, never OS attestation or SQL activation.

The two closed historical profiles are NOT READY. A caller-created record,
even a byte-for-byte clone, is unverified. Costs are trusted MODEL inputs,
not measured allocation bounds. No operational caller imports this module.
D-112 remains the only ledger and owns all credits, pins and cleanup states.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final, NoReturn

from maskgw.runtime.budget import BudgetError, BudgetLimits

_MAX_NUMBER: Final = (1 << 63) - 1
_MAX_SLOTS: Final = 4096
_MAX_COSTS: Final = 64
_MAX_LABEL: Final = 256
_MIB: Final = 1024 * 1024


class Quantity(StrEnum):
    VIRTUAL_ADDRESS_SPACE = "VIRTUAL_ADDRESS_SPACE"
    PRIVATE_COMMIT = "PRIVATE_COMMIT"
    RESIDENT_AND_CHARGED = "RESIDENT_AND_CHARGED"


class MemberKind(StrEnum):
    NONE = "NONE"
    AS_VIRTUAL = "AS_VIRTUAL"
    JOB_PRIVATE = "JOB_PRIVATE"


class AggregateKind(StrEnum):
    NONE = "NONE"
    STRICT_PROVEN = "STRICT_PROVEN"
    TRANSIENT_DOCUMENTED = "TRANSIENT_DOCUMENTED"


class CoverageVector(StrEnum):
    PRIVATE_MAPPED = "PRIVATE_MAPPED"
    SHARED_ANON = "SHARED_ANON"
    TMPFS_WRITE = "TMPFS_WRITE"
    PAGE_CACHE = "PAGE_CACHE"
    KERNEL_SOCKET_PIPE = "KERNEL_SOCKET_PIPE"
    LISTENER_TLS_OUTPUT = "LISTENER_TLS_OUTPUT"
    SUPERVISOR = "SUPERVISOR"
    AUXILIARY = "AUXILIARY"
    GENERATION_CANDIDATE = "GENERATION_CANDIDATE"
    SNAPSHOT = "SNAPSHOT"


class Coverage(StrEnum):
    UNKNOWN = "UNKNOWN"
    GAP_OBSERVED = "GAP_OBSERVED"
    MEMBER_ONLY = "MEMBER_ONLY"
    DOMAIN_PROVEN = "DOMAIN_PROVEN"
    EXCLUDED_PROVEN = "EXCLUDED_PROVEN"


class CostOwner(StrEnum):
    BASE = "BASE"
    HEADROOM = "HEADROOM"
    WORKER = "WORKER"
    PARENT = "PARENT"
    CANDIDATE = "CANDIDATE"
    GENERATION = "GENERATION"
    AUXILIARY = "AUXILIARY"


class CostLocation(StrEnum):
    IN_DOMAIN = "IN_DOMAIN"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"


class DomainReason(StrEnum):
    INVALID = "INVALID"
    FAULT = "FAULT"
    UNVERIFIED_PROFILE = "UNVERIFIED_PROFILE"
    AGGREGATE_UNPROVEN = "AGGREGATE_UNPROVEN"
    MEMBER_LIMIT_UNPROVEN = "MEMBER_LIMIT_UNPROVEN"
    COVERAGE_GAP = "COVERAGE_GAP"
    CREATION_UNPROVEN = "CREATION_UNPROVEN"
    CLEANUP_UNPROVEN = "CLEANUP_UNPROVEN"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    OUTSIDE_UNPROVEN = "OUTSIDE_UNPROVEN"
    DOUBLE_CHARGE = "DOUBLE_CHARGE"
    MISSING_COST = "MISSING_COST"
    CAPACITY = "CAPACITY"
    WORKER_UNDER_RESERVED = "WORKER_UNDER_RESERVED"
    OUTPUT_UNDER_RESERVED = "OUTPUT_UNDER_RESERVED"
    SUPERVISOR_COST = "SUPERVISOR_COST"
    TOPOLOGY = "TOPOLOGY"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    DOMAIN_LIMIT = "DOMAIN_LIMIT"


@dataclass(frozen=True, slots=True, repr=False)
class DomainProfile:
    """Closed evidence record; identity in the registry is necessary, not attestation."""

    name: str
    evidence: str
    member_kind: MemberKind
    member_quantity: Quantity
    member_bytes: int | None
    aggregate_kind: AggregateKind
    aggregate_quantity: Quantity
    aggregate_bytes: int | None
    observed_peak_bytes: int | None
    vectors: tuple[Coverage, ...]
    max_processes: int | None
    max_tasks: int | None
    members_attached_at_creation: bool
    supervisor_attached_at_creation: bool
    limits_before_work: bool
    owner_loss_cleanup_proven: bool

    def __repr__(self) -> str:
        return "DomainProfile(<evidence-only>)"


@dataclass(frozen=True, slots=True, repr=False)
class Cost:
    """One model identity/owner, not a measured allocation or deduplicator.

    A trusted plan must give the same physical cost the same identity. Aliasing
    one cost under different IDs cannot be detected by this pure checker.
    """

    identity: int
    owner: CostOwner
    location: CostLocation
    quantity: Quantity
    bytes_per_slot: int
    slots: int
    bound: DomainProfile | None = None

    def __repr__(self) -> str:
        return "Cost(<logical-only>)"


@dataclass(frozen=True, slots=True, repr=False)
class CostPlan:
    quantity: Quantity
    costs: tuple[Cost, ...]
    supervisor_cost_id: int
    supervisor_threads: int
    worker_threads: int
    auxiliary_threads: int
    fixed_auxiliaries: int
    fixed_auxiliary_threads: int
    fixed_auxiliary_cost_id: int | None
    frame_bytes: int
    output_overhead_bytes: int

    def __repr__(self) -> str:
        return "CostPlan(<logical-only>)"


@dataclass(frozen=True, slots=True)
class DomainVerdict:
    ready: bool
    reasons: tuple[DomainReason, ...]
    inside_bytes: int = 0
    outside_bytes: int = 0
    total_bytes: int = 0

    def __bool__(self) -> NoReturn:
        raise TypeError("consulte ready explicitamente")


# Exact scope of HELD III: PID1 + one loaded member, not a production capacity.
# cgroup pids.max=16 counts tasks, not sixteen admitted processes.
LINUX_HELD_AS128: Final = DomainProfile(
    name="linux-held-as128",
    evidence="docs/PHASE-9-STAGE-8-HELD-RUN-VALIDATION.md",
    member_kind=MemberKind.AS_VIRTUAL,
    member_quantity=Quantity.VIRTUAL_ADDRESS_SPACE,
    member_bytes=128 * _MIB,
    aggregate_kind=AggregateKind.TRANSIENT_DOCUMENTED,
    aggregate_quantity=Quantity.RESIDENT_AND_CHARGED,
    aggregate_bytes=192 * _MIB,
    observed_peak_bytes=138907648,
    vectors=(Coverage.MEMBER_ONLY, Coverage.MEMBER_ONLY) + (Coverage.UNKNOWN,) * 8,
    max_processes=2,
    max_tasks=16,
    members_attached_at_creation=True,
    supervisor_attached_at_creation=True,
    limits_before_work=True,
    owner_loss_cleanup_proven=False,
)
# B2-B2a: two separate jobs and a guardian OUTSIDE, no aggregate quota.
# The strict 384MiB failure is a different experiment and is not merged here.
WINDOWS_JOB_PRIVATE32: Final = DomainProfile(
    name="windows-job-private32",
    evidence="docs/PHASE-9-STAGE-8-B2-B2A-VALIDATION.md",
    member_kind=MemberKind.JOB_PRIVATE,
    member_quantity=Quantity.PRIVATE_COMMIT,
    member_bytes=32 * _MIB,
    aggregate_kind=AggregateKind.NONE,
    aggregate_quantity=Quantity.PRIVATE_COMMIT,
    aggregate_bytes=None,
    observed_peak_bytes=None,
    vectors=(Coverage.MEMBER_ONLY, Coverage.GAP_OBSERVED) + (Coverage.UNKNOWN,) * 8,
    max_processes=2,
    max_tasks=None,
    members_attached_at_creation=True,
    supervisor_attached_at_creation=False,
    limits_before_work=True,
    owner_loss_cleanup_proven=False,
)
_PROFILES: Final = (LINUX_HELD_AS128, WINDOWS_JOB_PRIVATE32)
_INVALID: Final = DomainVerdict(False, (DomainReason.INVALID,))
_FAULT: Final = DomainVerdict(False, (DomainReason.FAULT,))
_UNIT_MISMATCH: Final = DomainVerdict(False, (DomainReason.UNIT_MISMATCH,))


class _ValidationError(Exception):
    """No input values or native error data."""


def _number(value: int, *, minimum: int = 1, maximum: int = _MAX_NUMBER) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise _ValidationError


def _optional(value: int | None, *, maximum: int = _MAX_NUMBER) -> None:
    if value is not None:
        _number(value, maximum=maximum)


def _checked(value: int) -> int:
    _number(value, minimum=0)
    return value


def _validate_profile(profile: DomainProfile) -> None:
    if type(profile) is not DomainProfile:
        raise _ValidationError
    for label in (profile.name, profile.evidence):
        if type(label) is not str or not 1 <= len(label) <= _MAX_LABEL or not label.isascii():
            raise _ValidationError
    for value, kind in (
        (profile.member_kind, MemberKind),
        (profile.member_quantity, Quantity),
        (profile.aggregate_kind, AggregateKind),
        (profile.aggregate_quantity, Quantity),
    ):
        if type(value) is not kind:
            raise _ValidationError
    for limit in (profile.member_bytes, profile.aggregate_bytes, profile.observed_peak_bytes):
        _optional(limit)
    for capacity in (profile.max_processes, profile.max_tasks):
        _optional(capacity, maximum=_MAX_SLOTS)
    if (profile.member_kind is MemberKind.NONE) != (profile.member_bytes is None) or (
        profile.aggregate_kind is AggregateKind.NONE
    ) != (profile.aggregate_bytes is None):
        raise _ValidationError
    if (
        type(profile.vectors) is not tuple
        or len(profile.vectors) != len(CoverageVector)
        or any(type(value) is not Coverage for value in profile.vectors)
    ):
        raise _ValidationError
    for flag in (
        profile.members_attached_at_creation,
        profile.supervisor_attached_at_creation,
        profile.limits_before_work,
        profile.owner_loss_cleanup_proven,
    ):
        if type(flag) is not bool:
            raise _ValidationError


def _validate_plan(plan: CostPlan) -> None:
    if type(plan) is not CostPlan or type(plan.quantity) is not Quantity:
        raise _ValidationError
    if type(plan.costs) is not tuple or not 1 <= len(plan.costs) <= _MAX_COSTS:
        raise _ValidationError
    _number(plan.supervisor_cost_id)
    for value in (
        plan.supervisor_threads,
        plan.worker_threads,
        plan.auxiliary_threads,
        plan.fixed_auxiliary_threads,
    ):
        _number(value, maximum=_MAX_SLOTS)
    # Zero here means exactly no fixed auxiliaries, never an unlimited quota.
    _number(plan.fixed_auxiliaries, minimum=0, maximum=_MAX_SLOTS)
    _optional(plan.fixed_auxiliary_cost_id)
    _number(plan.frame_bytes)
    _number(plan.output_overhead_bytes)
    _checked(2 * plan.frame_bytes + plan.output_overhead_bytes)
    for cost in plan.costs:
        if type(cost) is not Cost:
            raise _ValidationError
        _number(cost.identity)
        _number(cost.bytes_per_slot)
        _number(cost.slots, maximum=_MAX_SLOTS)
        _checked(cost.bytes_per_slot * cost.slots)
        if (
            type(cost.owner) is not CostOwner
            or type(cost.location) is not CostLocation
            or type(cost.quantity) is not Quantity
        ):
            raise _ValidationError
        if cost.bound is not None:
            _validate_profile(cost.bound)
        if cost.location is CostLocation.IN_DOMAIN and cost.bound is not None:
            raise _ValidationError


def _known(profile: DomainProfile) -> bool:
    return any(profile is item for item in _PROFILES)


def _profile_reasons(profile: DomainProfile) -> set[DomainReason]:
    result: set[DomainReason] = set()
    if not _known(profile):
        result.add(DomainReason.UNVERIFIED_PROFILE)
    if (
        profile.aggregate_kind is not AggregateKind.STRICT_PROVEN
        or profile.observed_peak_bytes is None
        or profile.aggregate_bytes is None
        or profile.observed_peak_bytes > profile.aggregate_bytes
    ):
        result.add(DomainReason.AGGREGATE_UNPROVEN)
    if profile.member_kind is MemberKind.NONE:
        result.add(DomainReason.MEMBER_LIMIT_UNPROVEN)
    if (
        profile.member_kind is MemberKind.AS_VIRTUAL
        and profile.member_quantity is not Quantity.VIRTUAL_ADDRESS_SPACE
    ) or (
        profile.member_kind is MemberKind.JOB_PRIVATE
        and profile.member_quantity is not Quantity.PRIVATE_COMMIT
    ):
        result.add(DomainReason.UNIT_MISMATCH)
    if any(
        value not in (Coverage.DOMAIN_PROVEN, Coverage.EXCLUDED_PROVEN) for value in profile.vectors
    ):
        result.add(DomainReason.COVERAGE_GAP)
    if not all(
        (
            profile.members_attached_at_creation,
            profile.supervisor_attached_at_creation,
            profile.limits_before_work,
        )
    ):
        result.add(DomainReason.CREATION_UNPROVEN)
    if not profile.owner_loss_cleanup_proven:
        result.add(DomainReason.CLEANUP_UNPROVEN)
    return result


def _totals(plan: CostPlan) -> tuple[int, int]:
    inside = sum(
        cost.bytes_per_slot * cost.slots
        for cost in plan.costs
        if cost.location is CostLocation.IN_DOMAIN
    )
    outside = sum(
        cost.bytes_per_slot * cost.slots
        for cost in plan.costs
        if cost.location is CostLocation.OUT_OF_DOMAIN
    )
    return _checked(inside), _checked(outside)


def _cost_reasons(plan: CostPlan, limits: BudgetLimits) -> set[DomainReason]:
    result: set[DomainReason] = set()
    seen: set[int] = set()
    owners: dict[CostOwner, list[Cost]] = {owner: [] for owner in CostOwner}
    for cost in plan.costs:
        if cost.identity in seen:
            result.add(DomainReason.DOUBLE_CHARGE)
        seen.add(cost.identity)
        owners[cost.owner].append(cost)
        if cost.quantity is not plan.quantity:
            result.add(DomainReason.UNIT_MISMATCH)
    expected = {
        CostOwner.HEADROOM: 1,
        CostOwner.WORKER: limits.workers,
        CostOwner.PARENT: limits.sessions,
        CostOwner.CANDIDATE: limits.candidates,
        CostOwner.GENERATION: limits.generations,
        CostOwner.AUXILIARY: limits.auxiliaries,
    }
    if any(not rows for rows in owners.values()):
        result.add(DomainReason.MISSING_COST)
    for owner, slots in expected.items():
        if len(owners[owner]) != 1 or any(cost.slots != slots for cost in owners[owner]):
            result.add(DomainReason.CAPACITY)
    base = sum(cost.bytes_per_slot * cost.slots for cost in owners[CostOwner.BASE])
    headroom = sum(cost.bytes_per_slot * cost.slots for cost in owners[CostOwner.HEADROOM])
    if base != limits.base_bytes or headroom != limits.headroom_bytes:
        result.add(DomainReason.CAPACITY)
    supervisor = [cost for cost in plan.costs if cost.identity == plan.supervisor_cost_id]
    if (
        len(supervisor) != 1
        or supervisor[0].owner is not CostOwner.BASE
        or supervisor[0].location is not CostLocation.IN_DOMAIN
        or supervisor[0].slots != 1
    ):
        result.add(DomainReason.SUPERVISOR_COST)
    if any(
        cost.location is not CostLocation.IN_DOMAIN
        for owner in (CostOwner.WORKER, CostOwner.PARENT)
        for cost in owners[owner]
    ):
        result.add(DomainReason.TOPOLOGY)
    minimum = 2 * plan.frame_bytes + plan.output_overhead_bytes
    if any(cost.bytes_per_slot < minimum for cost in owners[CostOwner.PARENT]):
        result.add(DomainReason.OUTPUT_UNDER_RESERVED)
    return result


def _topology(plan: CostPlan, limits: BudgetLimits, profile: DomainProfile) -> set[DomainReason]:
    result: set[DomainReason] = set()
    processes = _checked(1 + limits.workers + limits.auxiliaries + plan.fixed_auxiliaries)
    tasks = _checked(
        plan.supervisor_threads
        + limits.workers * plan.worker_threads
        + limits.auxiliaries * plan.auxiliary_threads
        + plan.fixed_auxiliaries * plan.fixed_auxiliary_threads
    )
    if (
        limits.workers < limits.sessions
        or profile.max_processes is None
        or profile.max_tasks is None
        or processes > profile.max_processes
        or tasks > profile.max_tasks
    ):
        result.add(DomainReason.TOPOLOGY)
    fixed = [cost for cost in plan.costs if cost.identity == plan.fixed_auxiliary_cost_id]
    if plan.fixed_auxiliaries:
        if (
            len(fixed) != 1
            or fixed[0].owner is not CostOwner.BASE
            or fixed[0].location is not CostLocation.IN_DOMAIN
            or fixed[0].slots != plan.fixed_auxiliaries
            or plan.fixed_auxiliary_cost_id == plan.supervisor_cost_id
        ):
            result.add(DomainReason.MISSING_COST)
    elif plan.fixed_auxiliary_cost_id is not None:
        result.add(DomainReason.CAPACITY)
    return result


def _outside_reasons(plan: CostPlan) -> set[DomainReason]:
    result: set[DomainReason] = set()
    groups = [0] * len(_PROFILES)
    for cost in plan.costs:
        if cost.location is not CostLocation.OUT_OF_DOMAIN:
            continue
        bound = cost.bound
        if bound is None or not _known(bound) or _profile_reasons(bound):
            result.add(DomainReason.OUTSIDE_UNPROVEN)
        if bound is not None:
            if bound.aggregate_quantity is not plan.quantity:
                result.add(DomainReason.UNIT_MISMATCH)
            for index, known in enumerate(_PROFILES):
                if bound is known:
                    groups[index] = _checked(groups[index] + cost.bytes_per_slot * cost.slots)
    for index, total in enumerate(groups):
        bound = _PROFILES[index]
        if (
            total
            and bound.aggregate_quantity is plan.quantity
            and bound.aggregate_bytes is not None
            and total > bound.aggregate_bytes
        ):
            result.add(DomainReason.DOMAIN_LIMIT)
    return result


def _reconcile(profile: DomainProfile, plan: CostPlan, limits: BudgetLimits) -> DomainVerdict:
    _validate_profile(profile)
    _validate_plan(plan)
    if type(limits) is not BudgetLimits:
        raise _ValidationError
    replace(limits)  # Reuse the exact D-112 validation; do not duplicate it.
    if any(cost.quantity is not plan.quantity for cost in plan.costs):
        # Never even publish a logical sum of incomparable quantities.
        return _UNIT_MISMATCH
    inside, outside = _totals(plan)
    total = _checked(inside + outside)
    result = (
        _profile_reasons(profile) | _cost_reasons(plan, limits) | _topology(plan, limits, profile)
    )
    result |= _outside_reasons(plan)
    if (
        plan.quantity is not profile.aggregate_quantity
        or plan.quantity is not profile.member_quantity
    ):
        result.add(DomainReason.UNIT_MISMATCH)
    if (
        profile.member_quantity is plan.quantity
        and profile.member_bytes is not None
        and any(
            cost.bytes_per_slot < profile.member_bytes
            for cost in plan.costs
            if cost.owner is CostOwner.WORKER
        )
    ):
        result.add(DomainReason.WORKER_UNDER_RESERVED)
    if total > limits.total_bytes:
        result.add(DomainReason.BUDGET_EXCEEDED)
    if (
        profile.aggregate_quantity is plan.quantity
        and profile.aggregate_bytes is not None
        and inside > profile.aggregate_bytes
    ):
        result.add(DomainReason.DOMAIN_LIMIT)
    reasons = tuple(reason for reason in DomainReason if reason in result)
    return DomainVerdict(not reasons, reasons, inside, outside, total)


def reconcile(profile: DomainProfile, plan: CostPlan, limits: BudgetLimits) -> DomainVerdict:
    """Model consistency only; no OS/process/ledger mutation or activation.

    Registry identity proves only which reviewed evidence description is being
    used. It does not attest the live runtime or calibrate supplied costs.
    Current profiles always yield NOT READY. Future operational code must
    reconcile BEFORE constructing the ledger and prove actual OS association,
    limits, input bounds and cleanup separately, before any work is admitted.
    It must also pass charges at least as large as this plan to D-112 reserve
    operations; this function cannot enforce the values used by later calls.
    """
    try:
        return _reconcile(profile, plan, limits)
    except (_ValidationError, BudgetError):
        return _INVALID
    except Exception:
        return _FAULT
