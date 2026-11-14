# C0: root contract for the first real Owner setup/close probe

Root read both complete proposals from terminal74524 and terminal73934. The original child-canary proposal is NOT accepted. A killed S does not let the host observe its child. C1/LAST_CLOSE and the two child canaries remain unadmitted; do not prepare or implement those profiles now.

Accepted next increment ONLY: C0, public Owner setup then close, NEVER start. This exercises no child of the Owner. It is the concrete native entry prerequisite, not another owner, guardian or generic pure framework. W1 local authority is already granted. Native execution follows source/host review; Docker/PG/SQL/credentials/external network/state16/consumed attempt/deploy stay excluded.

## First files and review order

1. tests/test_oracle9_w1_supervisor_setup_probe.py ONLY first. Source docs/poc/oracle9_w1_supervisor_setup_probe.py stays ABSENT until root reads all oracles and measures/freezes RED.
2. Source is the actual C0 entry; import defines only. No change to existing qualifier, backend, adapter, enums or frozen140 tests.
3. A specific PowerShell host will reuse the measured Process custody/stop primitive. Its source and prospective native/transport oracles require separate root review before running C0. No native effect in the first tests/source QA.

## Exact narrow public entry API for first oracles

- load_qualifier() -> types.ModuleType: fixed sibling oracle9_w1_supervisor_qualification.py, captured bounded bytes <=65536, exact SHA999f4a8d627e1550e8c95c6c6fa42aaa7a5edfb7045acbb33ccf51561d5fe015, execute SAME captured bytes. Regular non-reparse final file. No qualifier/backend load at entry import. Normal module registration solely for defining the checked module is allowed; no owner/take registry or lookup of mutable global owners.
- C0LoadError(Exception): closed fixed message C0_LOAD, raised outside except without original error/cause/context. Never stringify an original exception.
- run_c0(q:Any, backend:types.ModuleType, application:object, directory:object, custody:object) -> tuple[str,str,str]. q is the trusted already-loaded qualifier namespace. Custody is its exact fresh QualCustody class, retained by the caller. No new custody/report framework; leave custody.report None (it is reserved for QualReport). Store original backend/request/owner/error/first_control in the existing fields. q and backend are trusted loaded definitions, never arbitrary untrusted objects.
- encode_c0(result:object) -> bytes: validate a closed exact tuple of three exact strings, canonical ASCII 'W1C0 STATUS STEP STATE\n', <=128 bytes including LF, exactly one line. Invalid structure/domain raises fixed ValueError C0_RECORD without opaque conversions. No JSON/parsing framework.

Closed domains: STATUS OBSERVED/REFUSED/UNKNOWN; STEP INPUT/CUSTODY/LOAD/SETUP/CLOSE/CONTROL/INTERNAL/DONE; STATE EMPTY/NEW/SETUP/READY/SETUP_FAILED/STARTING/LAUNCH_FAILED/RUNNING/HELD/CLOSED/OTHER. Reject impossible combinations: OBSERVED only DONE+CLOSED; REFUSED only INPUT/CUSTODY/LOAD with EMPTY; UNKNOWN never DONE. Do not invent HELD.

## C0 behavior

- Invalid or reused custody: REFUSED/CUSTODY/EMPTY without modifying it. Fresh custody is claimed once. Input validation is pure and matches SQ2 local path rules: exact str,1..1024, absolute drive letter, no UNC/device/quotes/NUL/CR/LF; generated fixed command <=2048. No filesystem/environment inspection in run_c0. Invalid input REFUSED/INPUT/EMPTY before Request/Owner.
- Backend must be an exact ModuleType with trusted callable Request/Owner. Invalid namespace REFUSED/LOAD/EMPTY before construction. Capture both once.
- Request uses the exact existing signature application/command_line/environment/directory. Environment ONLY (("W1_NATIVE_PROBE","1"),). Fixed inert command profile -I -B -S with pass; it is NEVER started. No user code/arguments.
- Retain backend then Request then Owner in caller custody BEFORE setup. Constructor is source-verified non-IO. Call setup once; require return None and actual ordinary state READY. Then close once; require None and actual state CLOSED. ONLY this conjunction returns OBSERVED/DONE/CLOSED.
- Every other post-acquisition outcome is UNKNOWN, actual sanitized ordinary state, original error by identity when an exception occurred, no retry and no speculative cleanup. setup error/invalid return/state forbids close; close error/invalid return/state forbids second close.
- A first BaseException-not-Exception is captured in error and first_control by identity and returned as UNKNOWN/CONTROL/state. This is the prospective S entry's weaker policy, NOT P B4 and NOT a change to qualify(). Zero later SDK method calls, no bool/repr of opaque values, no manual traceback/context changes. Public state metadata may be observed.
- Allowed Owner calls are ONLY setup and close. No start/check_config/wait/exit_code/accounting/members/terminate/available/read, private ledger/PID/native helpers. Caller retains all original references even after CLOSED. No claim physical destruction from a string state.

## Future native main/host obligations (not executed by first tests)

Main accepts only application/directory; validates before loading; loads pinned q then q.load_backend, creates q.QualCustody and invokes run_c0. One bounded frame then natural exit0 for OBSERVED or exit2 for resource-free refusal. UNKNOWN parks with strong custody/control, including repeated controls, no unhandled traceback/raw stderr, no SDK cleanup. Emission/parking controls must never replace the first. No voluntary exit while native resources are uncertain. No new canary profile.

Host owns a Process instance BEFORE Start, direct pinned base, cleared child environment, no shell. Captured stdout/stderr are NEW transport evidence, not inherited-stdout assumptions. Read only after positive S exit; stdout <=129 sentinel bytes, stderr <=1, no ReadToEnd/async/thread. Require exact one allowed LF frame and EOF for success; overflow stops reading, never drains unboundedly. In C0 only, source proves S never creates descendants. Positive EOF still must be measured, not inferred. Kill fallback/unknown Start/IO failure never passes. Dispose only after observed S exit; retain uncertain same instance. No absolute OS deadline promised. Host fields/limits and native oracles must be closed before implementation/execution.

## First oracle requirements

Reuse frozen faithful Request/Owner fakes and trusted qualifier namespace from tests/test_oracle9_w1_supervisor_qualification.py; do not modify them or monkeypatch production operations. Existing fake close accepts READY, matching backend. Verify independent fake sanity for READY->CLOSED with no start. Load missing candidate inside bodies, never collection/setup, so RED is failures not collection errors.

Cover exact order/custody/signature/environment; success; setup and close ordinary errors and both hostile controls including fail_states HELD; invalid returns and states including opaque values; original error/control identity and zero later calls; no close after setup uncertainty and no repeated close; exact input/custody/backend refusal before acquisition; encoding closed domains/limits/redaction and invalid opaque records; import defines only; checked-byte fixed-sibling loader success/tamper/missing/oversize without executing altered bytes. Tampered fixture must be valid Python. No weak assertions, cast/ignore/noqa/skip/xfail, private Owner bypass or duplicate C0 implementation. Root reads all oracles and runs statics before freezing RED.

All native/product gates remain OPEN. A prospective C0 success will qualify only this local setup/close path and transport, never S admission, descendant containment, child canaries or production readiness.
