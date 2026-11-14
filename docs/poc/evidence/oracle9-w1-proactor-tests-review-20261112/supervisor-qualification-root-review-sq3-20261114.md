# Root source review SQ3 - stale state after control

Source execution16025 completed exit0/service success/is_errorFalse/no denials. Root read all705lines of source484980a0. Frozen132 oracles pass; strict mypy win32 targets3.11/3.14 pass (3.14 static only); contracted PoC Ruff E9,F63,F7,F82 passes. Full Ruff reports20 advisory differences outside that existing PoC gate. Formatting has2 differences still to fix. No native qualifier was executed.

## Reproduced finding

The real pinned backend `_interrupt` sets the ordinary public attribute `state` to `HELD` before propagating control. The qualifier's report instead uses `last_state` whenever a control was captured. A faithful injected fake using `fail_states={'wait':'HELD'}` reproduces: expectedHELD, reportedRUNNING, original control identity retained, zero truthiness probes, last SDK call wait. This is a report correctness defect, not a native containment observation.

SQ1 requires actual sanitized public state and never invented HELD. Pure public metadata observation after control is allowed; no later SDK method, clock, cleanup or private ledger access is allowed. Preserve the first control, original custody and UNKNOWN/CONTROL outcome.

## Next test-only lot

Write ONLY tests/test_oracle9_w1_supervisor_qualification_review.py. Keep the frozen132 test and source unchanged. Reuse definitions from the frozen fake test, without production monkeypatch or a duplicate implementation. Cover setup/start/wait/close controls with faithful transition to HELD. Assert same original control, error/first_control identity, zero opaque probes, last SDK method is the faulting method, retained original backend/request/owner, UNKNOWN/CONTROL, actual report stateHELD, and no false successful cleanup. Root must read all new oracles and measure/freeze RED against source484980a0 before requesting the source fix.

After RED, minimal source-only correction may observe sanitized public state metadata without SDK calls, preserving every control/custody rule. Formatting may be corrected with AST-equivalent changes. Do not change frozen tests or weaken assertions, add suppressions, or hide the pinned checked-byte loader to satisfy unrelated stylistic rules. Native S/G/product gates remain OPEN.
