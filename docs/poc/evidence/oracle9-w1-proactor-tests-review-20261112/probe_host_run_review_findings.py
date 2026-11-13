"""Root QA: attribute oracle defects, then probe public admission of OWN malformed DTOs."""

import hashlib
import json
import runpy
from pathlib import Path
from types import SimpleNamespace


BASE = Path("docs/poc/evidence/oracle9-w1-proactor-tests-review-20261112")
SOURCE = Path("docs/poc/oracle9_w1_host_run.py")
TEST = Path("tests/test_oracle9_w1_host_run.py")
candidate = runpy.run_path(str(TEST), run_name="_root_host_review_findings_test")
pt, frozen, ht = candidate["pt"], candidate["base"], candidate["ht"]
core = ht.d1.driver()["load_pure"](ht.PinnedReader())

namespace = pt._pump_namespace()
vars_error = None
try:
    vars(namespace)
except TypeError as error:
    vars_error = type(error).__name__

h = pt.ProHarness(core)
protocol = h.bridge.run().done.outcome.name
h.owner.seal()
h.owner.settle(h.loop.t + 5.0)
audit_error = None
try:
    h.owner.begin_audit(h.m.AuditKind.GATEWAY_ABSENT, h.loop.t + 5.0)
except h.m.OwnershipRefusal as error:
    audit_error = error.category.name
process_kinds = (h.m.InvocationKind.SPAWN, h.m.InvocationKind.CHILD)
targets = [r for r in h.owner.records() if r.kind in process_kinds]
closed_count = h.close_all_settled()  # the ALREADY-FROZEN public composition helper
all_released = all(
    r.physical is h.m.PhysicalState.RELEASED_LOCAL
    for r in h.owner.records() if r.kind in process_kinds
)
oracle_attribution = {
    "namespace_fixture_exact_type": type(namespace).__name__,
    "vars_on_dict_error": vars_error,
    "direct_lookup_yields_helper": callable(namespace["_bind_over"]),
    "frozen_harness_done": protocol,
    "frozen_clock_audit_error": audit_error,
    "frozen_process_records": len(targets),
    "frozen_confirmed_local_closes": closed_count,
    "frozen_all_processes_released_local": all_released,
    "old_h11_minimum15_would_pass": closed_count >= 15,
    "future_host_source_used_for_oracle_attribution": False,
}

hr = SimpleNamespace(**runpy.run_path(str(SOURCE), run_name="_root_host_review_findings_source"))
rows = []
for name in ("custody-no-fields", "custody-missing-report", "inputs-no-fields", "window-missing-audit"):
    kit = candidate["make_kit"](hr, core, candidate["KitSpec"]())
    inputs, custody = kit.inputs, kit.custody
    expected = "REFUSED_INPUT"
    if name == "custody-no-fields":
        custody = object.__new__(hr.HostCustody)
        expected = "REFUSED_CUSTODY"
    elif name == "custody-missing-report":
        object.__delattr__(custody, "report")  # OWN public input slot, not an engine
        expected = "REFUSED_CUSTODY"
    elif name == "inputs-no-fields":
        inputs = object.__new__(hr.HostRunInputs)
    else:
        object.__delattr__(inputs.windows, "audit_s")
    before = candidate["custody_snapshot"](custody)
    raised = None
    report = None
    try:
        report = hr.run_host(inputs, custody)
    except BaseException as error:
        raised = type(error).__name__  # never inspect args, text, cause or foreign runtime
    stage = report.stage.name if type(report) is hr.HostRunReport else None
    after = candidate["custody_snapshot"](custody)
    unchanged = all(x is y for x, y in zip(before, after, strict=True))
    rows.append({
        "case": name, "expected_stage": expected, "actual_stage": stage,
        "exception_type": raised, "bind_calls": len(kit.bind_calls),
        "custody_unchanged": unchanged,
        "pass": stage == expected and raised is None and not kit.bind_calls
                and (expected != "REFUSED_CUSTODY" or unchanged),
    })

result = {
    "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    "test_sha256": hashlib.sha256(TEST.read_bytes()).hexdigest(),
    "oracle_attribution": oracle_attribution,
    "admission_cases": rows,
    "admission_passed": sum(row["pass"] for row in rows),
    "admission_failed": sum(not row["pass"] for row in rows),
    "subject": "public run_host with OWN malformed carrier data; no engine mutation",
    "native_effects": False,
    "product_modified": False,
}
(BASE / "host-run-review-findings-result.json").write_bytes(
    (json.dumps(result, indent=2) + "\n").encode()
)
print(json.dumps(result))
raise SystemExit(0 if result["admission_failed"] == 0 else 1)
