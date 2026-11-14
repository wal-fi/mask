# Supervisor qualification - root normative review SQ1 (2026-11-14)

The complete C2 proposal from execution61475 was read. Accepted ONLY for first fake oracles under THIS addendum. No source or native S admission yet. Native S/P, complete G and all product gates remain OPEN. W1 local implementation/native-test authority is granted; Docker/PG/SQL/credentials/externalnetwork/state16/consumedattempt/deploy remain excluded.

Targets: tests/test_oracle9_w1_supervisor_qualification.py FIRST; docs/poc/oracle9_w1_supervisor_qualification.py must remain ABSENT until root reads ALL oracles and measures/freezes RED. This is the concrete caller around existing public Owner, NOT a new owner/guardian/reducer framework. Existing protected sources/tests/pins remain fixed.

## Closed API (overrides underspecified fields of proposal)

- QualCase: NATURAL, TERMINATE.
- QualStatus: OBSERVED, FAIL, UNKNOWN, REFUSED_CUSTODY, REFUSED_INPUT.
- QualStep: SETUP, START, CONFIG, LIVE_LINE, TERMINATE, WAIT, EXIT_CODE, ACCOUNTING, MEMBERS, EOF, CLOSE.
- QualFault: NONE, INPUT, CUSTODY, BACKEND, SETUP, START, CONFIG, IO, TIME_BUDGET, EXIT_CODE, ACCOUNTING, MEMBERS, CLOSE, CONTROL, STATE, INTERNAL.
- OwnerState: EMPTY, NEW, SETUP, READY, SETUP_FAILED, STARTING, LAUNCH_FAILED, RUNNING, HELD, CLOSED, OTHER. Read public state, sanitize to this enum; never invent HELD.
- LineResult: MATCH, MISMATCH, OVERFLOW, ABSENT.
- CloseResult: NOT_ATTEMPTED, NONE_CLOSED, NONE_NOT_CLOSED, INVALID_RETURN, RAISED.
- TermResult: NOT_REQUESTED, RETURNED, INVALID_RETURN, RAISED.
- QualSpec: frozen/slotted/redacted repr; case:QualCase, application:str, directory:str, max_turns:int.
- QualCustody: slotted/redacted repr, caller-created EMPTY; claimed:bool=False, backend:object|None=None, request:object|None=None, owner:object|None=None, error:BaseException|None=None, first_control:BaseException|None=None, report:QualReport|None=None. No other owner/registry.
- QualReport: frozen/slotted/redacted repr; case:QualCase|None, status:QualStatus, fault:QualFault, step:QualStep|None, owner_state:OwnerState, exit_code:int|None, total:int|None, active:int|None, members:int|None, stdout_bytes:int, line:LineResult, eof:int, close:CloseResult, terminate:TermResult, turns:int.
- qualify(spec:object, custody:object, *, backend:types.ModuleType)->QualReport. NO clock callback: this is an explicit finite TURN decision budget, not a wallclock deadline.
- load_backend()->types.ModuleType: one purpose, fixed sibling pg16_shell_admission_win32.py, bounded captured bytes, exact accepted backend SHA10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726, execute SAME checked bytes. Import of qualifier defines only; no native backend load until load_backend explicitly called. No new generic loader.

## Bounds/profiles and trusted API assumptions

- OUTPUT_CAP=4096, READ_CAP=4096, WAIT_MS=50, max_turns exact int1..400 (reject bool). One GLOBAL turn counter across LIVE, WAIT and EOF drain; never rebase by phase. Bound every polling/draining loop. No claim absolute OS timing.
- Input path rules mirror backend: exact nonempty str <=1024, Windows absolute drive path, no NUL; additionally reject quotes/CR/LF in application/directory. Generated command_line <=2048. Pure validation before Owner construction, no filesystem/environment inspection in qualify.
- Request signature EXACT existing backend: application, command_line, environment:tuple, directory. Environment is ONLY (("W1_NATIVE_PROBE","1"),), not inherited. Native feasibility remains to be measured, not a permission blocker.
- Child profiles fixed, isolated -I -B -S, NO project/network/files/descendants. NATURAL emits exactly MASKGW-W1-SUPERVISOR-NATURAL with final LF or CRLF then exits0. TERMINATE emits exactly MASKGW-W1-SUPERVISOR-LIVE with flush then time.sleep(30). Caller supplies only application/directory, never arbitrary child code/argv.
- backend is a trusted exact ModuleType namespace from pinned load or faithful tests, containing Request/Owner/Win32Error; capture these references once. Constructor is verified source-defined non-IO. Retain backend/request/owner in caller custody BEFORE setup. Never use private Owner methods/ledger or query methods after CLOSED.
- API domains: setup/start/check_config/terminate/close return None. wait returns exact bool. available returns None (positive EOF) or exact int0..2**32-1; bool invalid. read returns exact bytes <=4096; empty bytes alone never EOF. exit_code exact int0..2**32-1, bool invalid. accounting exact tuple of2 exact ints; expected(1,0). members exact tuple of bounded ints; expected(). No truthiness/repr/str on opaque results/errors.

## Outcome and cleanup rules

- NATURAL and TERMINATE success: READY -> RUNNING -> check_config, waitTrue, expected code0/1, accounting(1,0), members(), FRESH positive availableNone while RUNNING, close returnsNone, stateCLOSED. Exact canary line required. One close only.
- TERMINATE: full LIVE marker BEFORE exactly one terminate; immediately before terminate require wait(0) false (positive alive observation). Unexpected exit is FAIL, never a kill observation. No retry/new child.
- Read only after available>0; retain at mostOUTPUT_CAP, count bounded consumed bytes, overflow stays FAIL; bounded draining may still establish cleanup. available0 does NOT call read. No fake EOF on readempty. Shared budget exhaustion is UNKNOWN/TIME_BUDGET, with owner retained.
- Important qualification: invalid channel (MISMATCH/OVERFLOW) can remain FAIL while cleanup proceeds ONLY if public wait/code/accounting/members/fresh EOF positively establish quiescence. Then close may be attempted but status NEVER becomes OBSERVED. Do not equate failed canary with live resources. This overrides proposal blanket 'no close on ANY failure'.
- SDK error, invalid inventory/config/state or unresolved EOF never permits close. Report actual sanitized state and keep same custody. No private bypass, no fabricated HELD, no abandoning original Owner. Failed/invalid close is retained, no second close. UNKNOWN is not cleanup.
- Controls: capture first BaseException-not-Exception by identity, put original in error/first_control, record closed UNKNOWN/CONTROL report using pure metadata, then re-raise SAME object outside except. No bool(control), manual traceback/context mutation, SDK call, clock or cleanup after first control. Backend's weaker internal S semantics are not global P B4.
- Report contains enums/exact bounded ints or allowedNone ONLY; no held_reason/raw error strings/bytes/paths/argv/exception contents. Custody retains original exception but reprs are redacted.
- Invalid spec/custody/backend refuses BEFORE Request/Owner construction. Never overwrite reused/nonempty custody. caseNone/OwnerState.EMPTY are valid for preacquisition refusal. OBSERVED requires every positive predicate; no broad allUNKNOWN substitute for success.

## FIRST oracle requirements

Preserve Q0..Q11 of proposal with above exact surface. Include: trusted FakeRequest signature and faithful minimal FakeOwner state/pipe model, no native calls; independent fake sanities; ownership before setup; natural and terminate order (including wait0-before-terminate); fresh EOF AFTER inventory; global budget across phases; emptyread!=EOF and available0 avoidsread; exact API types incl bool-int confusion and opaque truthiness traps; line fragmentation/LF-CRLF/mismatch/overflow; positive cleanup on channelFAIL only when full quiescence; never cleanup on inventory/state/API uncertainty; failed/invalid close; stateHELD is only observed state; redacted reprs; first-control identity/report/custody with zero later SDK calls; reused custody unchanged; source loader checked-byte integrity and fixed source target without private API bypass.

No source import at test module collection. Call missing-candidate loader INSIDE test bodies so absent source is measured FAIL, not collection/setupERROR. Do not weaken assertions/skip/xfail/cast/noqa/ignore. No monkeypatch of production operations or duplicate implementation; use injected trusted backend only. Loader fixture filesystem copies (source-identical qualifier in tmp directory with sibling backend bytes) may exercise tamper without changing production helpers.

Native entry/host wrapper is NOT part of this first module. Two canaries qualify ONLY public Owner paths for total1. Complete S admission still needs reviewed external-stop wiring, startup uncertainty, KILL_ON_JOB_CLOSE/descendant observation, runtime/hooks and other obligations. Existing NestedJobOwner.close_inner may support LAST_CLOSE observation later; no native run or waiver from this contract. Full N1-N16 remains required, and gateway remains unavailable.
