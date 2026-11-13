"""Root QA of proposed fixtures over existing composition; NEVER loads host_run."""

import hashlib
import json
import runpy
from pathlib import Path


BASE = Path("docs/poc/evidence/oracle9-w1-proactor-tests-review-20261112")
TEST = Path("tests/test_oracle9_w1_host_run.py")
candidate = runpy.run_path(str(TEST), run_name="_root_host_fixture_probe")
pt, frozen, ht = candidate["pt"], candidate["base"], candidate["ht"]
core = ht.d1.driver()["load_pure"](ht.PinnedReader())
rows = []


def observe(name, loop):
    """A probe of frozen ProHarness/bridge/fence, not a host caller implementation."""
    harness = pt.ProHarness(core, loop=loop)
    result = None
    fault = None
    try:
        result = harness.bridge.run()
    except harness.b_ns.BridgeRefusal as error:
        fault = error.category.name
    initial = harness.owner.seal()
    harness.owner.settle(loop.t + 5.0)
    refreshed = harness.owner.seal()
    late = [
        fact
        for record in harness.owner.records()
        for fact in record.late
        if fact.kind is harness.m.LateKind.PIPE_LOST and fact.code == 0
    ]
    audit_admitted = False
    audit_fault = None
    try:
        harness.owner.begin_audit(harness.m.AuditKind.GATEWAY_ABSENT, loop.t + 5.0)
        audit_admitted = True
    except harness.m.OwnershipRefusal as error:
        audit_fault = error.category.name
    row = {
        "case": name,
        "bridge_fault": fault,
        "done": None if result is None else result.done.outcome.name,
        "initial_settled": initial.work_settled_at,
        "refreshed_settled": refreshed.work_settled_at,
        "late_stdin_facts": len(late),
        "audit_admitted": audit_admitted,
        "audit_fault": audit_fault,
    }
    if name == "ticking-positive":
        row["pass"] = row["done"] == "COMPLETE_CANDIDATE" and audit_admitted
    elif name == "frozen-clock":
        row["pass"] = row["done"] == "COMPLETE_CANDIDATE" and audit_fault == "STATE"
    elif name == "late-stdin":
        row["pass"] = (
            initial.work_settled_at is None
            and refreshed.work_settled_at is not None
            and len(late) > 0
            and audit_admitted
        )
    elif name == "spawn-failure":
        row["pass"] = fault == "SPAWN" and refreshed.work_settled_at is None
    rows.append(row)


for name, loop in (
    ("ticking-positive", candidate["scripted_loop_class"]([], None, True)()),
    ("frozen-clock", pt.FakeLoop()),
    ("late-stdin", candidate["late_stdin_loop_class"]([], 2.0)()),
):
    try:
        observe(name, loop)
    except BaseException as error:
        rows.append({"case": name, "exception_type": type(error).__name__, "pass": False})

loop = pt.FakeLoop()
candidate["spawn_fails"](loop)
try:
    observe("spawn-failure", loop)
except BaseException as error:
    rows.append({"case": "spawn-failure", "exception_type": type(error).__name__, "pass": False})

harness = pt.ProHarness(core)
bad_plan = frozen.make_plan(harness.m, harness.r_ns, gateway_argv=("gateway-cli", "--no-scope"))
category = None
try:
    harness.m.PortOwnership(
        harness.pump, bad_plan, harness.limits,
        bridge_ns=harness.b_ns, reactor_ns=harness.r_ns,
    )
except harness.m.OwnershipRefusal as error:
    category = error.category.name
rows.append({"case": "invalid-plan-content", "category": category, "pass": category == "PLAN"})

result = {
    "test_sha256": hashlib.sha256(TEST.read_bytes()).hexdigest(),
    "subject": "fixture assumptions over FROZEN ProHarness; no host_run implementation",
    "rows": rows,
    "passed": sum(row["pass"] for row in rows),
    "failed": sum(not row["pass"] for row in rows),
    "native_effects": False,
    "future_host_module_loaded": False,
    "product_modified": False,
}
(BASE / "host-run-fixture-assumptions-v1.json").write_bytes(
    (json.dumps(result, indent=2) + "\n").encode()
)
print(json.dumps(result))
raise SystemExit(0 if result["failed"] == 0 else 1)
