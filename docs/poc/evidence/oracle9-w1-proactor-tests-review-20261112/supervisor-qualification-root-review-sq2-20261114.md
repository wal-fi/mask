# Root normative review SQ2 - first fake oracles (2026-11-14)

Root read ALL1351lines of candidate586a5db6, ranges1-320/321-660/661-1010/1011-1351.6128 terminal success0/is_errorFalse/no denials, recovered. Source qualifier remains ABSENT. Five independent fake sanities PASS; Ruff1ARG002, format1change, mypy1fixture-variable error in BOTH3.11/3.14. No RED frozen, no source accepted or native S proof.

## Closed routine decisions (SQ2 supplements SQ1)

- Root ADOPTS one turn = one public Owner.wait(50) invocation, with ONE shared counter over LIVE/WAIT/EOF-drain. Every polling/draining retry must consume this budget; at most one data-read action per turn. wait(0) is the separate immediate alive observation before terminate and is NOT a budget turn. Never call wait50 after max_turns. The fake's operation-step scheduler is a deterministic admissible model, NOT physical elapsed time; no wallclock or cross-process scheduling claim.
- Root accepts conservative rejection/retention on wrong exit code BEFORE inventory. Channel mismatch/overflow may still cleanup ONLY after complete positive public quiescence as SQ1 specifies, retaining FAIL. No new success route.
- Approved native scope is LOCAL only: both spec paths must be local absolute drive-letter Windows paths; UNC/device paths are refused before construction, no network access. This is a qualification-profile rule, not a change to existing backend.
- Exact bounded report domains: exit_code None or exact int0..2**32-1; total/active/members None or exact int0..2; stdout_bytes exact int0..400*4096; eof exact int0/1; turns exact int0..400. Type/structure/success conjunction from SQ1 retained. Invalid unsigned API values must not be copied unbounded into reports; no bool-as-int, repr/eq or truthiness of opaque values.

## Fixes required in SAME test only before freezing

1. FakeRequest fidelity: real Request is frozen. Existing FakeRequest accepts application mutation (root direct probe exit1: expected refusedTrue, observedFalse). Make all four data fields immutable while preserving exact constructor signature and per-script request instrumentation; add independent immutability sanity. Do not implement a new generic fake framework or weaken assertions.
2. Strengthen assert_report upper/lower domains above. Add malformed API cases for available>DWORD, negative exitcode, malformed/oversize accounting integers, member bool/negative/oversize entries as appropriate; preserve no-close/retention and no opaque inspections. These are invalid contract values, not native proof.
3. Loader tamper bytes must be syntactically valid regardless of temporary path quoting. Build marker path with a valid Python literal and compile/parse the tampered fixture BEFORE refusal assertion; do not let SyntaxError masquerade as a digest check. Keep import-only/no-execution marker assertions and checked-byte-loader coverage.
4. Mypy: separate exception-queue and return-queue variable names at old lines259/264; do not widen types or suppress. Ruff unused private trap arg can be prefixed underscore; fix the single formatter difference. No ignore/cast/noqa/skip/xfail.

All original SQ1 oracles remain, with only the explicit root routine decisions above. No product/old-test changes; source remains absent. Root must read ALL semantic deltas, rerun statics and independent fake probes, then measure/freeze RED before requesting source. Test remains local/unpublished until reviewed with implementation. Native/product gates OPEN; gateway unavailable.
