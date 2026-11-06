"""Fake-only tests for the private A->B bundle builder, written before the module.

docs/poc/pg16_shell_native_control_bundle_v2.py does not exist yet. The
`builder` fixture loads it lazily, so every builder case collects and fails at
setup until the module exists: a feature-absent baseline, never behavioural
evidence. Contract: PHASE-9-W1-PG16-BUNDLE-V2-DESIGN-REVIEW.md.

The `test_sanity_*` cases do NOT use the module. They run the real frozen
case V2 caller (A, 0fac3c7b) through its accepted fake harness, build the
expected evidence by hand with the frozen lifecycle/provenance test builders,
and check it with the real core verify and the real provenance validator (B,
eac97091): APPROVED and REJECTED with prefixes 1/2/3, plus the live shapes,
counts, original references and namespace bounds the builder relies on.

Every test builds its own live batch: a fresh A namespace, the group of eight
original references captured BEFORE the first allocate, allocate on demand
only after the previous case, one shared private map. Real Owner and
NestedJobOwner run against fake kernels with memory writes and fake clocks;
real WinDLL, Popen, os.system, Thread.start and time.sleep stay forbidden.
Helper seams are FunctionType(code, live A globals) so the group binding stays
valid; they are controlled injection, not malicious descriptors. Nothing here
creates a root, nonce, command, loader, collector or publisher.
"""

import ast
import builtins
import ctypes
import io
import json
import math
import os
import runpy
import subprocess
import threading
import time
from pathlib import Path
from types import FunctionType, SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "docs/poc/pg16_shell_native_control_bundle_v2.py"
CALLER = REPO / "docs/poc/pg16_shell_native_control_case_v2.py"
VALIDATOR = REPO / "docs/poc/pg16_shell_native_control_provenance_v2.py"
VERIFIER = REPO / "docs/poc/pg16_shell_native_control_verify.py"
CASE: dict[str, Any] = runpy.run_path(str(REPO / "tests/test_pg16_shell_native_control_case_v2.py"))
PROV: dict[str, Any] = runpy.run_path(
    str(REPO / "tests/test_pg16_shell_native_control_provenance_v2.py")
)
FROZEN: dict[str, Any] = CASE["FROZEN"]
NONCE: str = FROZEN["NONCE"]
ARGV0: str = FROZEN["ARGV0"]
PLANS: dict[str, Any] = PROV["PLANS"]
TREES: dict[str, Any] = PROV["TREES"]
LAST_REJECTION: dict[str, Any] = PROV["LAST_REJECTION"]
V2_RESULTS: dict[str, Any] = PROV["V2_RESULTS"]
ROWS: tuple[tuple[str, str, int, str], ...] = PROV["ROWS"]
LAUNCHER: str = PROV["LAUNCHER"]
POLICY = PROV["POLICY"]
Collider: Any = PROV["Collider"]
SneakyStr: Any = PROV["SneakyStr"]
ForeignMeta: Any = PROV["ForeignMeta"]
foreign: Any = PROV["foreign"]
forbidden: Any = PROV["forbidden"]
rebound: Any = PROV["rebound"]
canonical: Any = PROV["canonical"]
Namespace = dict[str, Any]
Args = tuple[Any, Any, Any, Any]
READY = "READY_FOR_VALIDATION"
REASONS = (
    "GROUP",
    "INPUT",
    "CAP",
    "KEEP",
    "SLOT",
    "SHAPE",
    "RECORD",
    "PREFIX",
    "ARTIFACTS",
    "DRIFT",
    "RELEASE",
    "SIZE",
    "INTERNAL",
)
HELPERS = ("_intact", "_released", "_record")
OTHER_SHA = "0" * 64
ATTR_CALLS: list[str] = []


class Signal(BaseException):
    """A fictitious control interruption."""


class AttrSpy:
    """Records every attribute read; must never be touched by the builder."""

    def __getattribute__(self, name: str) -> Any:
        ATTR_CALLS.append(name)
        raise AttributeError(name)


@pytest.fixture
def lab(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    base: SimpleNamespace = CASE["lab"].__wrapped__(monkeypatch)
    return base


@pytest.fixture
def cv2() -> Namespace:
    namespace: Namespace = runpy.run_path(str(CALLER))["allocate"].__globals__
    return namespace


@pytest.fixture
def builder() -> Namespace:
    namespace: Namespace = runpy.run_path(str(MODULE))["bundle"].__globals__
    return namespace


# -- live batches (per test, never shared) --


def measured() -> tuple[Any, str]:
    """Loader declarations: equal values, distinct objects from the reviewer policy."""
    return tuple((*row,) for row in ROWS), LAUNCHER


def batch(lab: SimpleNamespace, cv2: Namespace, plans: Any, reconcile: Any = None) -> Any:
    """Group captured before the first allocate; allocate each case on demand."""
    private: dict[str, bytes] = {}
    source = lab.helper if reconcile is None else reconcile
    group = (cv2, cv2["KEEP"], lab.runner, lab.lifecycle, source, lab.host, lab.original, private)
    staged: list[Any] = []
    for number, name, setup in plans:
        kernel_setup = None if setup is None else FROZEN[setup]
        st = CASE["staged"](lab, cv2, (number, name), private, kernel_setup)
        assert CASE["prepare"](lab, cv2, st, reconcile) == "PREPARED"
        assert CASE["run"](cv2, st) == READY
        staged.append(st)
    return SimpleNamespace(
        lab=lab,
        cv2=cv2,
        group=group,
        staged=tuple(staged),
        slots=tuple(st.slot for st in staged),
        private=private,
        measured=measured(),
    )


def args(b: Any) -> Args:
    return (b.group, b.slots, b.measured, NONCE)


def with_group(b: Any, index: int, value: Any) -> Args:
    group = list(b.group)
    group[index] = value
    return (tuple(group), b.slots, b.measured, NONCE)


def oracle(b: Any) -> tuple[Any, ...]:
    """Expected evidence built by hand from the live records and the shared map."""
    records = [slot.record for slot in b.slots]
    summary, transport, files = FROZEN["published"](b.lab, records, b.private)
    scenario = SimpleNamespace(
        summary=summary,
        transport=transport,
        private=tuple(sorted(files.items())),
        trees=tuple(slot.tree for slot in b.slots),
    )
    built: tuple[Any, ...] = PROV["build"](PROV["draft"](scenario))
    return built


def b_verify(evidence: Any) -> Any:
    core: Namespace = runpy.run_path(str(VERIFIER))["verify"].__globals__
    validator: Namespace = runpy.run_path(str(VALIDATOR))["verify_v2"].__globals__
    expected = core["Expected"](nonce=NONCE, argv0=ARGV0)
    return validator["verify_v2"](core, POLICY, expected, evidence)


def call(builder: Namespace, b: Any, override: Args | None = None) -> Any:
    group, slots, declared, nonce = args(b) if override is None else override
    return builder["bundle"](group, slots, declared, nonce)


def refused(result: Any, reason: str) -> None:
    assert type(result) is tuple and len(result) == 2
    assert type(result[0]) is str and type(result[1]) is str
    assert result == ("BUNDLE_REFUSED", reason)


def ready(result: Any) -> tuple[Any, ...]:
    assert type(result) is tuple and len(result) == 2 and result[0] == "BUNDLE_READY"
    evidence = result[1]
    assert type(evidence) is tuple and len(evidence) == 5
    assert all(type(raw) is bytes for raw in evidence[:3])
    assert type(evidence[3]) is dict and type(evidence[4]) is dict
    built: tuple[Any, ...] = evidence
    return built


def spy(b: Any, name: str, action: Any) -> list[Any]:
    """Replace a read helper of A by a seam with the same live globals."""
    namespace = b.cv2
    real = namespace[name]
    calls: list[Any] = []

    def fake(*values: Any) -> Any:
        calls.append(values[0])
        return action(real, values)

    namespace[name] = rebound(fake, namespace)
    return calls


def through(real: Any, values: Any) -> Any:
    return real(*values)


def fingerprint(b: Any) -> tuple[Any, ...]:
    """What the builder must never write: slot latches, owners, lists, map."""
    rows: list[Any] = []
    for slot in b.slots:
        rows.append(
            (
                slot.state,
                slot.outcome,
                slot.run_reserved,
                slot.tree,
                slot.failure,
                slot.control,
                slot.record,
                slot.owner.state,
                dict(slot.record),
            )
        )
    return (tuple(rows), list(b.group[1]), list(b.group[6]), dict(b.private))


# -- sanity of the live harness and the hand-built oracle (no new module) --


@pytest.mark.parametrize("name", list(PLANS))
def test_sanity_live_batch_oracle_verifies_with_real_b(
    lab: SimpleNamespace, cv2: Namespace, name: str
) -> None:
    b = batch(lab, cv2, PLANS[name])
    assert tuple(slot.tree for slot in b.slots) == TREES[name]
    assert b.slots[-1].record["rejection"] == LAST_REJECTION[name]
    assert PROV["closed"](b_verify(oracle(b)), V2_RESULTS[name]) is None


def test_sanity_live_shapes_counts_and_original_references(
    lab: SimpleNamespace, cv2: Namespace
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    case_ns, keep, legacy, lifecycle, reconcile, host, registry, private = b.group
    assert type(case_ns) is dict and len(case_ns) <= 128
    assert all(type(key) is str and 0 < len(key) <= 64 for key in case_ns)
    for namespace in (legacy, lifecycle, host):
        assert type(namespace) is dict and len(namespace) <= 256
        assert all(type(key) is str and 0 < len(key) <= 64 for key in namespace)
    assert type(case_ns["_Slot"]) is type and type(case_ns["_Refs"]) is type
    assert vars(case_ns["_Slot"])["__init__"].__globals__ is case_ns
    assert "__init__" not in vars(case_ns["_Refs"])
    for name in HELPERS:
        assert type(case_ns[name]) is FunctionType and case_ns[name].__globals__ is case_ns
    assert case_ns["KEEP"] is keep and type(keep) is list
    assert len(keep) == 3 and all(keep[i] is b.slots[i] for i in range(3))
    assert legacy["_LIVE"] is registry and type(registry) is list and registry == []
    assert type(private) is dict and len(private) == 11
    for slot in b.slots:
        refs: Any = slot.refs
        entries: Any = refs.entries
        context_type: Any = refs.context_type
        ctx: Any = slot.ctx
        assert type(refs) is case_ns["_Refs"] and len(entries) == 34
        mappings = (legacy, lifecycle, host, slot.case, slot.facts)
        for entry in entries:
            assert type(entry) is tuple and len(entry) == 3
            assert type(entry[1]) is str and len(entry[1]) <= 64
            assert any(entry[0] is mapping for mapping in mappings)
        assert type(slot.meta) is tuple and len(slot.meta) == 8
        assert len(slot.case) == 20 and len(slot.facts) == 10 and len(slot.record) == 13
        assert type(ctx) is lifecycle["_Context"] and context_type is lifecycle["_Context"]
        assert slot.legacy is legacy and slot.lifecycle is lifecycle and slot.reconcile is reconcile
        assert slot.host is host and slot.registry is registry and slot.artifacts is private
        assert slot.ledger == {} and slot.owner.ledger is slot.ledger
        assert slot.owner.state == "CLOSED" and slot.facts["held"] is None
        assert type(slot.retained) is bytearray and len(slot.retained) <= 1024
        assert slot.case["reconcile_reserved"] is slot.tree
    for field in ("owner", "case", "facts", "retained", "ledger", "ctx", "record", "refs", "clock"):
        values = [getattr(slot, field) for slot in b.slots]
        assert all(values[i] is not values[j] for i in range(3) for j in range(i + 1, 3))


def test_sanity_helper_seams_and_real_helpers_on_ready_slots(
    lab: SimpleNamespace, cv2: Namespace
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    for slot in b.slots:
        assert cv2["_intact"](slot) is True
        assert cv2["_released"](slot) is True
        assert cv2["_record"](slot, slot.record) is True
    calls = spy(b, "_record", through)
    seam = cv2["_record"]
    assert type(seam) is FunctionType and seam.__globals__ is cv2
    assert all(cv2["_record"](slot, slot.record) is True for slot in b.slots)
    assert len(calls) == 3 and all(calls[i] is b.slots[i] for i in range(3))


def worst_record(keys: Any) -> dict[str, Any]:
    """Every record field at its conservative domain bound (str enums at 64)."""
    record: dict[str, Any] = {}
    for key in keys:
        record[key] = "x" * 64
    record["exit_code"] = record["total_processes"] = (1 << 32) - 1
    record["seconds"] = -1.2345678901234567e-300
    return record


def test_sanity_conservative_bounds_hold_for_worst_domain_values() -> None:
    core: Namespace = runpy.run_path(str(VERIFIER))["verify"].__globals__
    record = worst_record(core["CASE_KEYS"])
    assert len(record) == 13 and len(canonical(record)) - 1 <= 1536
    assert len(repr(record["seconds"])) <= 32
    pins: dict[str, Any] = {key: "f" * 64 for key, _value in core["PINS"]}
    summary: dict[str, Any] = {"kind": "x" * 64, "nonce": "f" * 32, "outcome": "x" * 64}
    summary.update(scope="x" * 64, admission_3s="x" * 64, cases=[record, record, record])
    summary.update(pins)
    assert len(summary) == 10 and len(canonical(summary)) <= 8192
    descriptor: dict[str, Any] = {"name": "x" * 32, "bytes": 65536, "sha256": "f" * 64}
    assert len(canonical(descriptor)) - 1 <= 133
    transport: dict[str, Any] = {"kind": "x" * 64, "nonce": "f" * 32, "outcome": "x" * 64}
    transport.update(summary=descriptor, private=[descriptor] * 11)
    assert len(canonical(transport)) <= 2048
    source: dict[str, Any] = {"role": "x" * 32, "path": "x" * 64, "bytes": 65536}
    source["sha256"] = "f" * 64
    assert len(canonical(source)) - 1 <= 207
    case = dict(descriptor, number=3)
    manifest: dict[str, Any] = {"kind": "x" * 64, "nonce": "f" * 32, "executed": 3}
    manifest["summary"] = descriptor
    manifest.update(transport=descriptor, cases=[case] * 3, sources=[source] * 8)
    manifest.update(launcher={"sha256": "f" * 64})
    assert len(canonical(manifest)) <= 3072
    metadata = PROV["case_meta"](3, True)
    metadata["kind"] = "x" * 64
    assert len(canonical(metadata)) <= 512
    assert len(PROV["MANIFEST_KIND"]) == 41 and len(PROV["CASE_KIND"]) == 37
    assert max(len(row[1]) for row in ROWS) <= 64 and max(len(row[0]) for row in ROWS) <= 32


# -- positives --


@pytest.mark.parametrize("name", list(PLANS))
def test_positive_profiles_match_oracle_and_real_b(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, name: str
) -> None:
    b = batch(lab, cv2, PLANS[name])
    before = fingerprint(b)
    evidence = ready(call(builder, b))
    expected = oracle(b)
    assert evidence[:3] == expected[:3]
    assert evidence[3] == expected[3] and evidence[3] is not b.private
    assert evidence[4] == expected[4]
    PROV["closed"](b_verify(evidence), V2_RESULTS[name])
    assert fingerprint(b) == before  # no cleanup, no write


def test_positive_reentry_refusal_keeps_primary_ready(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    assert CASE["run"](cv2, b.staged[0]) == "RETAINED_REUSED"
    assert b.slots[0].outcome == READY
    PROV["closed"](b_verify(ready(call(builder, b))), V2_RESULTS["approved"])


def test_positive_repeated_build_is_deterministic_and_isolated(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace
) -> None:
    b = batch(lab, cv2, PLANS["last_close_tree"])
    first = ready(call(builder, b))
    first[3]["case-1/invocation.json"] = b"mutated"
    first[4].clear()
    second = ready(call(builder, b))
    assert second[:3] == first[:3] and second[3] is not first[3]
    assert second[3] == b.private and len(second[4]) == 3


def test_positive_wrong_measured_pin_is_left_to_b(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    rows = list(b.measured[0])
    rows[3] = (*rows[3][:3], OTHER_SHA)
    policy = (tuple((*row,) for row in ROWS), LAUNCHER)
    evidence = ready(call(builder, b, (b.group, b.slots, (tuple(rows), LAUNCHER), NONCE)))
    PROV["closed"](b_verify(evidence), ("V2_INVALID", "PIN"))
    assert policy == POLICY  # reviewer policy untouched


# -- GROUP --


def group_list(b: Any) -> Args:
    return (list(b.group), b.slots, b.measured, NONCE)


def group_seven(b: Any) -> Args:
    return (b.group[:7], b.slots, b.measured, NONCE)


def case_ns_copy(b: Any) -> Args:
    return with_group(b, 0, dict(b.cv2))


def case_ns_foreign(b: Any) -> Args:
    return with_group(b, 0, runpy.run_path(str(CALLER))["allocate"].__globals__)


def keep_copy(b: Any) -> Args:
    return with_group(b, 1, list(b.group[1]))


def registry_other(b: Any) -> Args:
    return with_group(b, 6, [])


def private_not_dict(b: Any) -> Args:
    return with_group(b, 7, tuple(b.private.items()))


def private_twelve(b: Any) -> None:
    b.private["case-1/extra.json"] = b"{}\n"


def padded(index: int, total: int) -> Any:
    def mutate(b: Any) -> None:
        namespace = b.group[index]
        for number in range(total - len(namespace)):
            namespace["_pad_" + str(number)] = None

    return mutate


def long_key(index: int) -> Any:
    def mutate(b: Any) -> None:
        b.group[index]["k" * 65] = None

    return mutate


def colliding_case_ns(b: Any) -> None:
    key = Collider("CASES")
    namespace: Any = b.cv2
    count = len(namespace)
    namespace[key] = namespace.pop("CASES")
    assert len(namespace) == count and any(item is key for item in namespace)
    key.calls.clear()
    b.probe = key.calls


def helper_foreign(b: Any) -> None:
    b.cv2["_intact"] = foreign


def helper_globals(b: Any) -> None:
    b.cv2["_record"] = rebound(b.cv2["_record"], {})


def slot_class_meta(b: Any) -> None:
    b.cv2["_Slot"] = ForeignMeta("_Slot", (), {})


def slot_init_globals(b: Any) -> None:
    init = vars(b.cv2["_Slot"])["__init__"]
    b.cv2["_Slot"] = type("_Slot", (), {"__init__": rebound(init, {})})


def refs_class_meta(b: Any) -> None:
    b.cv2["_Refs"] = ForeignMeta("_Refs", (), {})


def live_not_list(b: Any) -> Args:
    registry = tuple(b.group[6])
    b.lab.runner["_LIVE"] = registry
    return with_group(b, 6, registry)


GROUPS: list[Any] = [
    pytest.param(group_list, id="group-list"),
    pytest.param(group_seven, id="group-seven-items"),
    pytest.param(case_ns_copy, id="caller-runpy-style-copy"),
    pytest.param(case_ns_foreign, id="caller-foreign-namespace"),
    pytest.param(keep_copy, id="keep-not-caller-keep"),
    pytest.param(registry_other, id="registry-not-legacy-live"),
    pytest.param(live_not_list, id="registry-not-list"),
    pytest.param(private_not_dict, id="private-not-dict"),
    pytest.param(private_twelve, id="private-twelve-entries"),
    pytest.param(padded(0, 129), id="caller-129-keys"),
    pytest.param(long_key(0), id="caller-65-char-key"),
    pytest.param(colliding_case_ns, id="caller-colliding-key"),
    pytest.param(padded(2, 257), id="legacy-257-keys"),
    pytest.param(long_key(5), id="host-65-char-key"),
    pytest.param(helper_foreign, id="helper-foreign-function"),
    pytest.param(helper_globals, id="helper-foreign-globals"),
    pytest.param(slot_class_meta, id="slot-class-foreign-metaclass"),
    pytest.param(slot_init_globals, id="slot-init-foreign-globals"),
    pytest.param(refs_class_meta, id="refs-class-foreign-metaclass"),
]


@pytest.mark.parametrize("mutate", GROUPS)
def test_group_refusals(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, mutate: Any
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    b.probe = None
    override = mutate(b)
    refused(call(builder, b, override), "GROUP")
    assert b.probe is None or b.probe == []


def over_private(b: Any) -> Any:
    """A 12th private entry under a foreign key (hash of an absent name)."""
    key = Collider("case-9/absent.json")
    raw: Any = b.private
    raw[key] = b"{}\n"
    assert len(raw) == 12 and any(item is key for item in raw)
    return key


def over_namespace(index: int, total: int) -> Any:
    def make(b: Any) -> Any:
        namespace: Any = b.group[index]
        for number in range(total - 1 - len(namespace)):
            namespace["_pad_" + str(number)] = None
        key = Collider("_absent_name")
        namespace[key] = None
        assert len(namespace) == total and any(item is key for item in namespace)
        return key

    return make


OVERCOUNTS: list[Any] = [
    pytest.param(over_private, id="private-12-with-foreign-key"),
    pytest.param(over_namespace(0, 129), id="caller-129-with-foreign-key"),
    pytest.param(over_namespace(2, 257), id="legacy-257-with-foreign-key"),
]


@pytest.mark.parametrize("make", OVERCOUNTS)
def test_overcount_is_refused_before_any_key_scan(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, make: Any
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    calls = [spy(b, name, through) for name in HELPERS]
    key = make(b)
    key.calls.clear()
    refused(call(builder, b), "GROUP")
    assert key.calls == [] and calls == [[], [], []]


# -- INPUT --


def slots_value(value: Any) -> Any:
    def mutate(b: Any) -> Args:
        return (b.group, value(b.slots), b.measured, NONCE)

    return mutate


def measured_value(value: Any) -> Any:
    def mutate(b: Any) -> Args:
        return (b.group, b.slots, value(b.measured), NONCE)

    return mutate


def nonce_value(value: Any) -> Any:
    def mutate(b: Any) -> Args:
        return (b.group, b.slots, b.measured, value)

    return mutate


def row_set(index: int, field: int, value: Any) -> Any:
    def make(declared: Any) -> Any:
        rows = [list(row) for row in declared[0]]
        rows[index][field] = value
        return (tuple(tuple(row) for row in rows), declared[1])

    return make


def private_collider(b: Any) -> None:
    key = Collider("case-1/invocation.json")
    raw: Any = b.private
    count = len(raw)
    raw[key] = raw.pop("case-1/invocation.json")
    assert len(raw) == count and any(item is key for item in raw)
    key.calls.clear()
    b.probe = key.calls


def private_renamed(b: Any) -> None:
    b.private["case-1/unknown.json"] = b.private.pop("case-1/invocation.json")


def private_bytearray(b: Any) -> None:
    b.private["case-1/invocation.json"] = bytearray(b.private["case-1/invocation.json"])


def no_slots(_slots: Any) -> Any:
    return ()


INPUTS: list[Any] = [
    pytest.param(slots_value(list), id="slots-list"),
    pytest.param(slots_value(no_slots), id="slots-empty"),
    pytest.param(slots_value(lambda slots: (*slots, slots[0])), id="slots-four"),
    pytest.param(measured_value(list), id="measured-list"),
    pytest.param(measured_value(lambda m: (m[0][:7], m[1])), id="measured-seven-rows"),
    pytest.param(measured_value(lambda m: (*m, None)), id="measured-three-items"),
    pytest.param(measured_value(row_set(0, 2, True)), id="measured-size-bool"),
    pytest.param(measured_value(row_set(0, 2, 0)), id="measured-size-zero"),
    pytest.param(measured_value(row_set(0, 2, 65537)), id="measured-size-65537"),
    pytest.param(measured_value(row_set(1, 3, ROWS[1][3].upper())), id="measured-sha-upper"),
    pytest.param(measured_value(row_set(2, 1, "docs/poc/other.py")), id="measured-path"),
    pytest.param(measured_value(row_set(0, 0, "lifecycle_v2")), id="measured-role"),
    pytest.param(measured_value(lambda m: (m[0], LAUNCHER.encode())), id="measured-launcher"),
    pytest.param(nonce_value(NONCE.upper()), id="nonce-uppercase"),
    pytest.param(nonce_value(NONCE[:31]), id="nonce-short"),
    pytest.param(nonce_value(SneakyStr(NONCE)), id="nonce-str-subclass"),
    pytest.param(private_collider, id="private-colliding-key"),
    pytest.param(private_renamed, id="private-unknown-name"),
    pytest.param(private_bytearray, id="private-value-bytearray"),
]


@pytest.mark.parametrize("mutate", INPUTS)
def test_input_refusals(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, mutate: Any
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    b.probe = None
    refused(call(builder, b, mutate(b)), "INPUT")
    assert b.probe is None or b.probe == []


# -- CAP and KEEP --


@pytest.mark.parametrize(
    ("name", "size"),
    [
        pytest.param("case-1/invocation.json", 4097, id="invocation-4097"),
        pytest.param("case-3/audit.json", 65537, id="audit-65537"),
    ],
)
def test_cap_refusals(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, name: str, size: int
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    b.private[name] = b" " * size
    calls = spy(b, "_intact", through)
    refused(call(builder, b), "CAP")
    assert calls == []


def keep_extra(b: Any) -> None:
    b.cv2["allocate"]()


def keep_tuple(b: Any) -> Args:
    keep = tuple(b.group[1])
    b.cv2["KEEP"] = keep
    return with_group(b, 1, keep)


KEEPS: list[Any] = [
    pytest.param(keep_extra, id="keep-extra-allocated-slot"),
    pytest.param(slots_value(lambda slots: slots[:2]), id="keep-omitted-selected"),
    pytest.param(slots_value(lambda slots: (slots[1], slots[0], slots[2])), id="keep-order"),
    pytest.param(keep_tuple, id="keep-not-list"),
]


@pytest.mark.parametrize("mutate", KEEPS)
def test_keep_refusals(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, mutate: Any
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    refused(call(builder, b, mutate(b)), "KEEP")


# -- SLOT --


def fake_slot(b: Any) -> Args:
    fake = SimpleNamespace(state=READY, outcome=READY, run_reserved=True)
    b.group[1][0] = fake
    return (b.group, (fake, *b.slots[1:]), b.measured, NONCE)


def slot_set(field: str, value: Any) -> Any:
    def mutate(b: Any) -> None:
        setattr(b.slots[0], field, value)

    return mutate


def retained_outcome(b: Any) -> None:
    b.slots[0].state = b.slots[0].outcome = "RETAINED_DRIFT"


SLOTS: list[Any] = [
    pytest.param(fake_slot, id="slot-not-genuine-class"),
    pytest.param(retained_outcome, id="slot-retained-outcome"),
    pytest.param(slot_set("state", "PREPARED"), id="slot-state-not-ready"),
    pytest.param(slot_set("outcome", SneakyStr(READY)), id="slot-outcome-str-subclass"),
    pytest.param(slot_set("run_reserved", False), id="slot-run-not-reserved"),
    pytest.param(slot_set("failure", ValueError("first")), id="slot-failure-latched"),
    pytest.param(slot_set("control", Signal()), id="slot-control-latched"),
    pytest.param(slot_set("tree", 1), id="slot-tree-int"),
]


@pytest.mark.parametrize("mutate", SLOTS)
def test_slot_refusals(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, mutate: Any
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    override = mutate(b)
    latched = (b.slots[0].failure, b.slots[0].control)
    refused(call(builder, b, override), "SLOT")
    assert b.slots[0].failure is latched[0] and b.slots[0].control is latched[1]


def test_slot_real_retained_held_is_ineligible(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace
) -> None:
    private: dict[str, bytes] = {}
    kernels: list[Any] = []

    def foreign_member() -> None:
        kernels[0].extra["job"] = (0x9001,)

    reconcile = CASE["before_reconcile"](lab, foreign_member)
    sources = (lab.runner, lab.lifecycle, reconcile)
    group = (cv2, cv2["KEEP"], *sources, lab.host, lab.original, private)
    st = CASE["staged"](lab, cv2, (1, "NORMAL"), private, FROZEN["tree"])
    kernels.append(st.kernel)
    assert CASE["prepare"](lab, cv2, st, reconcile) == "PREPARED"
    assert CASE["run"](cv2, st) == "RETAINED_HELD"
    result = builder["bundle"](group, (st.slot,), measured(), NONCE)
    refused(result, "SLOT")
    assert st.slot.outcome == "RETAINED_HELD"


# -- SHAPE --


def refs_spy(b: Any) -> None:
    b.slots[0].refs = AttrSpy()


def refs_uninitialized(b: Any) -> None:
    b.slots[0].refs = object.__new__(b.cv2["_Refs"])


def entries_edit(edit: Any) -> Any:
    def mutate(b: Any) -> None:
        refs = b.slots[0].refs
        refs.entries = edit(refs.entries, b)

    return mutate


def entry_set(field: int, value: Any) -> Any:
    def edit(entries: Any, b: Any) -> Any:
        first = list(entries[0])
        first[field] = value(b) if callable(value) else value
        return (tuple(first), *entries[1:])

    return edit


def map_extra(field: str) -> Any:
    def mutate(b: Any) -> None:
        getattr(b.slots[0], field)["extra"] = None

    return mutate


def record_collider(b: Any) -> None:
    key = Collider("seconds")
    record: Any = b.slots[0].record
    record[key] = record.pop("seconds")
    assert len(record) == 13 and any(item is key for item in record)  # valid count
    key.calls.clear()
    b.probe = key.calls


def facts_set(key: str, value: Any) -> Any:
    def mutate(b: Any) -> None:
        b.slots[0].facts[key] = value

    return mutate


def ctx_uninitialized(b: Any) -> None:
    b.slots[0].ctx = object.__new__(b.lab.lifecycle["_Context"])


def share(field: str) -> Any:
    def mutate(b: Any) -> None:
        setattr(b.slots[1], field, getattr(b.slots[0], field))

    return mutate


def host_other(b: Any) -> Args:
    return with_group(b, 5, dict(b.lab.host))


def entries_33(entries: Any, _b: Any) -> Any:
    return entries[:33]


def entries_35(entries: Any, _b: Any) -> Any:
    return (*entries, entries[0])


def entry_two(entries: Any, _b: Any) -> Any:
    return (entries[0][:2], *entries[1:])


def runner_copy(b: Any) -> Any:
    return dict(b.lab.runner)


def meta_seven(b: Any) -> None:
    b.slots[0].meta = b.slots[0].meta[:7]


def legacy_copy(b: Any) -> None:
    b.slots[0].legacy = dict(b.lab.runner)


def map_copy(b: Any) -> None:
    b.slots[0].artifacts = dict(b.private)


def slot_uninitialized(b: Any) -> Args:
    """A genuine _Slot never initialized: mandatory attributes are missing."""
    fake = object.__new__(b.cv2["_Slot"])
    b.group[1][0] = fake
    return (b.group, (fake, *b.slots[1:]), b.measured, NONCE)


SHAPES: list[Any] = [
    pytest.param(slot_uninitialized, id="slot-genuine-uninitialized"),
    pytest.param(refs_spy, id="refs-foreign-object-no-attribute-read"),
    pytest.param(refs_uninitialized, id="refs-genuine-uninitialized"),
    pytest.param(entries_edit(entries_33), id="entries-33"),
    pytest.param(entries_edit(entries_35), id="entries-35"),
    pytest.param(entries_edit(entry_two), id="entry-two"),
    pytest.param(entries_edit(entry_set(1, "k" * 65)), id="entry-name-65"),
    pytest.param(entries_edit(entry_set(0, runner_copy)), id="entry-mapping"),
    pytest.param(slot_set("meta", None), id="meta-none"),
    pytest.param(meta_seven, id="meta-seven"),
    pytest.param(map_extra("case"), id="case-21-keys"),
    pytest.param(map_extra("facts"), id="facts-11-keys"),
    pytest.param(map_extra("record"), id="record-14-keys"),
    pytest.param(record_collider, id="record-colliding-key"),
    pytest.param(facts_set("reason", "WHATEVER"), id="facts-reason-enum"),
    pytest.param(facts_set("eof", 1), id="facts-eof-int"),
    pytest.param(facts_set("turns", -1), id="facts-turns-negative"),
    pytest.param(facts_set("exit_code", 1 << 32), id="facts-exit-uint32"),
    pytest.param(slot_set("ctx", object()), id="ctx-foreign-object"),
    pytest.param(ctx_uninitialized, id="ctx-genuine-uninitialized"),
    pytest.param(legacy_copy, id="origin-legacy"),
    pytest.param(host_other, id="origin-host"),
    pytest.param(map_copy, id="origin-map"),
    pytest.param(share("case"), id="shared-case"),
    pytest.param(share("owner"), id="shared-owner"),
    pytest.param(share("clock"), id="shared-clock"),
    pytest.param(share("ledger"), id="shared-ledger"),
]


@pytest.mark.parametrize("mutate", SHAPES)
def test_shape_refusals(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, mutate: Any
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    b.probe = None
    ATTR_CALLS.clear()
    calls = spy(b, "_intact", through)
    override = mutate(b)
    refused(call(builder, b, override), "SHAPE")
    assert calls == [] and ATTR_CALLS == [] and (b.probe is None or b.probe == [])


# -- RECORD domains before any equality or encode --


def record_set(index: int, key: str, value: Any) -> Any:
    def mutate(b: Any) -> None:
        b.slots[index].record[key] = value

    return mutate


RECORDS: list[Any] = [
    pytest.param(record_set(0, "case", SneakyStr("NORMAL")), id="record-case-str-subclass"),
    pytest.param(record_set(0, "case", "N" * 65), id="record-case-65-chars"),
    pytest.param(record_set(0, "outcome", "NOT_RUN"), id="record-outcome-domain"),
    pytest.param(record_set(0, "rejection", "WHATEVER"), id="record-rejection-domain"),
    pytest.param(record_set(0, "framing", "LFX"), id="record-framing-domain"),
    pytest.param(record_set(0, "exit_code", 1 << 32), id="record-exit-uint32"),
    pytest.param(record_set(0, "exit_code", True), id="record-exit-bool"),
    pytest.param(record_set(0, "terminated", None), id="record-terminated-none"),
    pytest.param(record_set(0, "seconds", math.nan), id="record-seconds-nan"),
    pytest.param(record_set(0, "seconds", math.inf), id="record-seconds-inf"),
    pytest.param(record_set(0, "seconds", -1.0), id="record-seconds-negative"),
    pytest.param(record_set(2, "audit_entries", 513), id="record-audit-513"),
    pytest.param(record_set(2, "terminate_calls", -1), id="record-terminate-negative"),
]


@pytest.mark.parametrize("mutate", RECORDS)
def test_record_domain_refusals(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, mutate: Any
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    calls = spy(b, "_intact", through)
    mutate(b)
    refused(call(builder, b), "RECORD")
    assert calls == []


# -- PREFIX and ARTIFACTS --


def reordered(b: Any) -> Args:
    keep = b.group[1]
    keep[0], keep[1] = keep[1], keep[0]
    return (b.group, (keep[0], keep[1], keep[2]), b.measured, NONCE)


PREFIXES: list[Any] = [
    pytest.param(((1, "NORMAL", None), (2, "TERMINATE", None)), None, id="approved-k2"),
    pytest.param(((1, "NORMAL", None),), None, id="approved-k1"),
    pytest.param(((1, "NORMAL", "tree"), (2, "TERMINATE", None)), None, id="case-after-rejection"),
    pytest.param(PLANS["approved"], reordered, id="order-swapped-with-keep"),
]


@pytest.mark.parametrize(("plans", "mutate"), PREFIXES)
def test_prefix_refusals(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, plans: Any, mutate: Any
) -> None:
    b = batch(lab, cv2, plans)
    override = None if mutate is None else mutate(b)
    refused(call(builder, b, override), "PREFIX")


def test_artifacts_missing_file(lab: SimpleNamespace, cv2: Namespace, builder: Namespace) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    del b.private["case-2/supervision.json"]
    refused(call(builder, b), "ARTIFACTS")


def test_artifacts_future_case_file(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace
) -> None:
    b = batch(lab, cv2, PLANS["terminate_rejected"])
    b.private["case-3/invocation.json"] = b"{}\n"
    refused(call(builder, b), "ARTIFACTS")


# -- RELEASE preflight before any helper --


def registry_append(value: Any) -> Any:
    def mutate(b: Any) -> None:
        b.group[6].append(value(b))

    return mutate


def owner_state(b: Any) -> None:
    b.slots[0].owner.state = "RUNNING"


def ledger_entry(b: Any) -> None:
    b.slots[0].ledger["job"] = 1


def ledger_replaced(b: Any) -> None:
    b.slots[0].owner.ledger = {}


def case_flag(key: str, value: Any) -> Any:
    def mutate(b: Any) -> None:
        b.slots[0].case[key] = value

    return mutate


def retained_grown(b: Any) -> None:
    retained = b.slots[0].retained
    retained.extend(b"x" * (1025 - len(retained)))


def ctx_owner(b: Any) -> None:
    b.slots[0].ctx.owner = b.slots[1].owner


def unknown_owner(_b: Any) -> Any:
    return object()


def known_owner(b: Any) -> Any:
    return b.slots[0].owner


RELEASES: list[Any] = [
    pytest.param(registry_append(unknown_owner), id="registry-unknown-owner"),
    pytest.param(registry_append(known_owner), id="registry-known-owner"),
    pytest.param(owner_state, id="owner-not-closed"),
    pytest.param(ledger_entry, id="ledger-not-empty"),
    pytest.param(ledger_replaced, id="ledger-replaced"),
    pytest.param(case_flag("lifecycle_reserved", False), id="lifecycle-flag-false"),
    pytest.param(case_flag("reconcile_reserved", True), id="reconcile-flag-not-latch"),
    pytest.param(facts_set("held", "CLEANUP"), id="facts-held"),
    pytest.param(retained_grown, id="retained-1025"),
    pytest.param(ctx_owner, id="ctx-owner-binding"),
]


@pytest.mark.parametrize("mutate", RELEASES)
def test_release_preflight_refusals_call_no_helper(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, mutate: Any
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    calls = [spy(b, name, through) for name in HELPERS]
    mutate(b)
    refused(call(builder, b), "RELEASE")
    assert calls == [[], [], []]


# -- helpers: at most nine, global guards, exact results, controls --


def test_helpers_called_at_most_three_per_slot(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    calls = [spy(b, name, through) for name in HELPERS]
    ready(call(builder, b))
    for seen in calls:
        assert len(seen) == 3 and all(any(item is slot for item in seen) for slot in b.slots)


def returning(value: Any) -> Any:
    def action(_real: Any, _values: Any) -> Any:
        return value

    return action


def raising(error: BaseException) -> Any:
    def action(_real: Any, _values: Any) -> Any:
        raise error

    return action


RESULTS: list[Any] = [
    pytest.param(("_intact", returning(False), "DRIFT"), id="intact-false"),
    pytest.param(("_released", returning(False), "RELEASE"), id="released-false"),
    pytest.param(("_record", returning(False), "RECORD"), id="record-false"),
    pytest.param(("_intact", returning(1), "INTERNAL"), id="intact-returns-one"),
    pytest.param(("_record", returning(None), "INTERNAL"), id="record-returns-none"),
    pytest.param(
        ("_released", raising(ValueError("fault")), "INTERNAL"),
        id="released-value-error",
    ),
]


@pytest.mark.parametrize("spec", RESULTS)
def test_helper_results(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, spec: Any
) -> None:
    name, action, reason = spec
    b = batch(lab, cv2, PLANS["approved"])
    spy(b, name, action)
    before = fingerprint(b)
    refused(call(builder, b), reason)
    assert fingerprint(b) == before


def mutate_earlier(kind: str) -> Any:
    def apply(b: Any) -> None:
        first = b.slots[0]
        if kind == "record":
            first.record["seconds"] = first.record["seconds"] + 1.0
        elif kind == "flag":
            first.case["reconcile_reserved"] = not first.tree
        elif kind in ("eof", "signaled"):
            first.facts[kind] = not first.facts[kind]
        elif kind == "turns":
            first.facts["turns"] += 1
        elif kind == "reason":
            first.facts["reason"] = "DEADLINE"
        elif kind == "retained":
            first.retained[0] ^= 1
        elif kind == "owner":
            first.owner.state = "RUNNING"
        else:
            b.group[6].append(object())

    return apply


EARLIER = ("record", "flag", "eof", "signaled", "turns", "reason", "retained", "owner")
LATER: list[Any] = [
    *[pytest.param(kind, id="later-helper-mutates-earlier-" + kind) for kind in EARLIER],
    pytest.param("registry", id="later-helper-appends-registry"),
]


@pytest.mark.parametrize("kind", LATER)
def test_later_helper_mutating_an_earlier_slot_is_drift(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, kind: str
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    change = mutate_earlier(kind)

    def action(real: Any, values: Any) -> Any:
        if values[0] is b.slots[2]:
            change(b)
        return real(*values)

    spy(b, "_record", action)
    refused(call(builder, b), "DRIFT")


def test_mutation_with_value_error_is_drift(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace
) -> None:
    b = batch(lab, cv2, PLANS["approved"])

    def action(_real: Any, _values: Any) -> Any:
        b.slots[0].facts["turns"] += 1
        raise ValueError("fault")

    spy(b, "_released", action)
    refused(call(builder, b), "DRIFT")


@pytest.mark.parametrize("mutating", [False, True], ids=["control", "control-with-mutation"])
def test_controls_in_helpers_keep_identity(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, mutating: bool
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    signal = Signal()

    def action(_real: Any, _values: Any) -> Any:
        if mutating:
            b.slots[0].facts["turns"] += 1
        raise signal

    spy(b, "_intact", action)
    latched = [(slot.failure, slot.control) for slot in b.slots]
    with pytest.raises(Signal) as caught:
        call(builder, b)
    assert caught.value is signal
    assert [(slot.failure, slot.control) for slot in b.slots] == latched


def test_final_guard_catches_serializer_mutation(
    lab: SimpleNamespace, cv2: Namespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Controlled stdlib fault: the normal stdlib is a trusted premise. The fault
    is installed BEFORE the module is loaded, so any import style sees it."""
    b = batch(lab, cv2, PLANS["approved"])
    real = json.dumps
    fired: list[bool] = []

    def dumps(*values: Any, **options: Any) -> Any:
        if not fired:
            fired.append(True)
            b.slots[0].facts["turns"] += 1
        return real(*values, **options)

    monkeypatch.setattr(json, "dumps", dumps)
    namespace: Namespace = runpy.run_path(str(MODULE))["bundle"].__globals__
    refused(namespace["bundle"](b.group, b.slots, b.measured, NONCE), "DRIFT")
    assert fired == [True]


def test_reason_set_is_closed(lab: SimpleNamespace, cv2: Namespace, builder: Namespace) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    for override in (group_list(b), slots_value(list)(b), nonce_value("x")(b)):
        result = call(builder, b, override)
        assert result[0] == "BUNDLE_REFUSED" and result[1] in REASONS
    assert len(REASONS) == 13


# -- import and call purity --


BANNED_IMPORTS = frozenset(
    ("builtins", "ctypes", "importlib", "io", "os", "pathlib", "runpy", "socket", "subprocess")
)
BANNED_NAMES = frozenset(("__import__", "compile", "eval", "exec", "open"))
TOP_LEVEL = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)


def test_module_body_is_definition_only() -> None:
    """Static boundary proof of the module body; not a proof of every IO path."""
    tree = ast.parse(MODULE.read_bytes())
    body = tree.body
    assert body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
    assert all(isinstance(node, TOP_LEVEL) for node in body[1:])
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not {alias.name.split(".")[0] for alias in node.names} & BANNED_IMPORTS
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in BANNED_IMPORTS
        if isinstance(node, ast.Name):
            assert node.id not in BANNED_NAMES


def test_import_and_call_have_no_file_process_or_native_effect(
    lab: SimpleNamespace, cv2: Namespace
) -> None:
    b = batch(lab, cv2, PLANS["normal_tree"])
    traps = (
        (builtins, "open"),
        (io, "open"),
        (Path, "open"),
        (Path, "read_bytes"),
        (os, "open"),
        (ctypes, "WinDLL"),
        (subprocess, "Popen"),
        (os, "system"),
        (threading.Thread, "start"),
        (time, "sleep"),
    )
    with pytest.MonkeyPatch.context() as patch:
        for owner, name in traps:
            patch.setattr(owner, name, forbidden)
        namespace: Namespace = runpy.run_path(str(MODULE))["bundle"].__globals__
        result = namespace["bundle"](b.group, b.slots, b.measured, NONCE)
    PROV["closed"](b_verify(ready(result)), V2_RESULTS["normal_tree"])


# -- regressions: a late helper mutating EARLIER bound state must be DRIFT --
#
# The trusted `_record` seam of slot 3 returns its real result, then changes
# state of slot 1 or of the group that the original bounded capture covers:
# namespace sizes, every _Refs field, the case metadata and the five case
# bindings recorded in refs.entries, and source pointers named by entries.
# All changes are in memory; Path.with_name only builds a replacement value.


def namespace_add(index: int) -> Any:
    def mutate(b: Any) -> None:
        b.group[index]["_late_probe"] = None

    return mutate


def namespace_drop(index: int, name: str) -> Any:
    def mutate(b: Any) -> None:
        namespace = b.group[index]
        assert name in namespace
        del namespace[name]

    return mutate


def closed_state(_owner: Any) -> Any:
    return "CLOSED"


def refs_field(name: str, make: Any) -> Any:
    def mutate(b: Any) -> None:
        refs = b.slots[0].refs
        setattr(refs, name, make(getattr(refs, name)))

    return mutate


def fresh_tuple(value: Any) -> Any:
    return (*value,)


def foreign_function(_value: Any) -> Any:
    return foreign


def benign_state(_value: Any) -> Any:
    return closed_state


def probe_exception(_value: Any) -> Any:
    return type("ProbeError", (Exception,), {})


def probe_class(_value: Any) -> Any:
    return type("ProbeClass", (), {})


def case_value(key: str, make: Any) -> Any:
    def mutate(b: Any) -> None:
        case = b.slots[0].case
        case[key] = make(case[key])

    return mutate


def other_name(_value: Any) -> Any:
    return "TERMINATE"


def other_prefix(_value: Any) -> Any:
    return "case-9/"


def other_directory(value: Any) -> Any:
    return value.with_name("case-9")


def read_4095(_value: Any) -> Any:
    return 4095


def audit_511(_value: Any) -> Any:
    return 511


def later_start(value: Any) -> Any:
    return value + 1.0


def copied_map(value: Any) -> Any:
    return dict(value)


def new_clock(value: Any) -> Any:
    return type(value)()


def source_pointer(index: int) -> Any:
    """Replace the object named by the first entry bound to group[index]."""

    def mutate(b: Any) -> None:
        namespace = b.group[index]
        for mapping, name, _value in b.slots[0].refs.entries:
            if mapping is namespace:
                namespace[name] = foreign
                return
        raise AssertionError("no entry bound to this namespace")

    return mutate


LATE: list[Any] = [
    pytest.param(namespace_add(0), id="late-caller-key-added"),
    pytest.param(namespace_add(2), id="late-legacy-key-added"),
    pytest.param(namespace_add(3), id="late-lifecycle-key-added"),
    pytest.param(namespace_add(5), id="late-host-key-added"),
    pytest.param(namespace_drop(0, "PREPARED"), id="late-caller-unbound-key-dropped"),
    pytest.param(namespace_drop(2, "NONCE_PATTERN"), id="late-legacy-unbound-key-dropped"),
    pytest.param(namespace_drop(3, "VERDICTS"), id="late-lifecycle-unbound-key-dropped"),
    pytest.param(namespace_drop(5, "TASK_PATTERN"), id="late-host-unbound-key-dropped"),
    pytest.param(refs_field("entries", fresh_tuple), id="late-refs-entries"),
    pytest.param(refs_field("now", foreign_function), id="late-refs-now"),
    pytest.param(refs_field("run_error", probe_exception), id="late-refs-run-error"),
    pytest.param(refs_field("refused", probe_exception), id="late-refs-refused"),
    pytest.param(refs_field("context_type", probe_class), id="late-refs-context-type"),
    pytest.param(refs_field("context", foreign_function), id="late-refs-context"),
    pytest.param(refs_field("lifecycle", foreign_function), id="late-refs-lifecycle"),
    pytest.param(refs_field("finish", foreign_function), id="late-refs-finish"),
    pytest.param(refs_field("state", benign_state), id="late-refs-state-benign-closed"),
    pytest.param(refs_field("case_keys", fresh_tuple), id="late-refs-case-keys"),
    pytest.param(case_value("name", other_name), id="late-case-name"),
    pytest.param(case_value("prefix", other_prefix), id="late-case-prefix"),
    pytest.param(case_value("directory", other_directory), id="late-case-directory"),
    pytest.param(case_value("read_limit", read_4095), id="late-case-read-limit"),
    pytest.param(case_value("audit_limit", audit_511), id="late-case-audit-limit"),
    pytest.param(case_value("start", later_start), id="late-case-start"),
    pytest.param(case_value("facts", copied_map), id="late-case-facts-binding"),
    pytest.param(case_value("host", copied_map), id="late-case-host-binding"),
    pytest.param(case_value("clock", new_clock), id="late-case-clock-binding"),
    pytest.param(case_value("error", probe_exception), id="late-case-error-binding"),
    pytest.param(source_pointer(2), id="late-legacy-entry-pointer"),
    pytest.param(source_pointer(3), id="late-lifecycle-entry-pointer"),
    pytest.param(source_pointer(5), id="late-host-entry-pointer"),
]


@pytest.mark.parametrize("mutate", LATE)
def test_late_helper_mutating_earlier_bound_state_is_drift(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, mutate: Any
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    for slot in b.slots:  # seed: the real helpers accept the untouched READY slots
        assert cv2["_intact"](slot) is True and cv2["_released"](slot) is True
        assert cv2["_record"](slot, slot.record) is True
    fired: list[bool] = []

    def action(real: Any, values: Any) -> Any:
        result = real(*values)
        if values[0] is b.slots[2] and not fired:
            fired.append(True)
            mutate(b)
        return result

    spy(b, "_record", action)
    latched = [(slot.failure, slot.control) for slot in b.slots]
    refused(call(builder, b), "DRIFT")
    assert fired == [True]
    assert [(slot.failure, slot.control) for slot in b.slots] == latched


# -- regressions: mandatory meta/case scalar domains of the A profile --
#
# meta and the case scalar change COHERENTLY before the call (the same float
# object for NaN/Inf), so A's own `_intact` still accepts the slot; the builder
# must refuse the out-of-profile domain itself, before any helper.


def meta_domain(index: int, key: str, value: Any) -> Any:
    def mutate(b: Any) -> None:
        slot = b.slots[0]
        meta = list(slot.meta)
        meta[index] = value
        slot.meta = tuple(meta)
        slot.case[key] = value

    return mutate


META_DOMAINS: list[Any] = [
    pytest.param(meta_domain(6, "start", math.nan), id="meta-start-nan"),
    pytest.param(meta_domain(6, "start", math.inf), id="meta-start-inf"),
    pytest.param(meta_domain(4, "read_limit", 4095), id="meta-read-limit-4095"),
    pytest.param(meta_domain(5, "audit_limit", 511), id="meta-audit-limit-511"),
]


@pytest.mark.parametrize("mutate", META_DOMAINS)
def test_meta_profile_domains_are_shape_before_helpers(
    lab: SimpleNamespace, cv2: Namespace, builder: Namespace, mutate: Any
) -> None:
    b = batch(lab, cv2, PLANS["approved"])
    mutate(b)
    assert cv2["_intact"](b.slots[0]) is True  # coherent: A's own guard still accepts it
    calls = [spy(b, name, through) for name in HELPERS]
    latched = [(slot.failure, slot.control) for slot in b.slots]
    refused(call(builder, b), "SHAPE")
    assert calls == [[], [], []]
    assert [(slot.failure, slot.control) for slot in b.slots] == latched
