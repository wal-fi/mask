"""Root QA: mutation-check only the proposed test witness, never the product helper."""

import hashlib
import json
import runpy
from pathlib import Path


TEST = Path("tests/test_oracle9_w1_proactor_bind.py")
OUT = Path("docs/poc/evidence/oracle9-w1-proactor-tests-review-20261112")
ns = runpy.run_path(str(TEST), run_name="_root_bind_witness_probe")
cases = [(name, value) for name, value in ns.items() if name.startswith("test_sanity_")]
assert len(cases) == 3
shared = cases[0][1].__globals__
original = shared["helper_frames_hold"]


def broken_without_code_filter(throwable, _code, known):
    """Deliberate witness defect: accepts any own synthetic traceback frame."""
    entry = throwable.__traceback__
    walked = 0
    while entry is not None and walked < 64:
        walked += 1
        if any(value is known for value in entry.tb_frame.f_locals.values()):
            return True
        entry = entry.tb_next
    return False


rows = []
try:
    for mode, witness in (("original", original), ("code-filter-removed", broken_without_code_filter)):
        shared["helper_frames_hold"] = witness
        for name, case in cases:
            failure = None
            try:
                case()
            except BaseException as error:
                failure = type(error).__name__
            rows.append({"mode": mode, "case": name, "passed": failure is None,
                         "failure_type": failure})
finally:
    shared["helper_frames_hold"] = original

result = {
    "subject": "proposed witness/sanity cases only; no product helper loaded or replaced",
    "test_sha256": hashlib.sha256(TEST.read_bytes()).hexdigest(),
    "rows": rows,
    "original_passed": sum(r["passed"] for r in rows if r["mode"] == "original"),
    "mutation_detected": any(not r["passed"] for r in rows if r["mode"] != "original"),
    "native_effects": False,
    "product_source_changed": False,
}
(OUT / "probe-bind-witness-filter-result.json").write_bytes(
    (json.dumps(result, indent=2) + "\n").encode()
)
print(json.dumps(result))
raise SystemExit(0 if result["mutation_detected"] and result["original_passed"] == 3 else 1)
