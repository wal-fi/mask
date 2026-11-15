# C0 source review and final disposition

Call85216 completed exit0/service success/is_errorFalse/no denials and was recovered. Root read ALL340lines of source264e1133 (12380bytes). Frozen testd2180060 stayed intact. First-source QA:82PASS/2FAIL, Ruff test and contracted PoC lint PASS, format PASS, mypy strict win32 targets3.11/3.14 PASS (3.14 static only). No native execution or host implementation.

## S1 - checked qualifier definitions fail without normal module registration

Both frozen positive-loader tests fail with C0_LOAD. Independent language-level witness executes the SAME pinned qualifier definitions, no backend method or DLL: unregistered ModuleType gives AttributeError during dataclass construction; ordinary temporary sys.modules registration succeeds. runpy's temporary module registration is relevant; the raw ModuleType exec is not equivalent. Root contract explicitly permits normal definition-module registration, not an owner registry. Fix the loader only after the next regression-only lot; preserve captured-byte verification and original loader-refusal assertions.

## S2 - short stdout writes are incorrectly acknowledged

Independent public-main probe uses invalid input (before loading or acquisition) and ordinary public standard-stream capture. No source function, loader, run_c0 or Owner operation is monkeypatched. A stdout buffer whose write returns0 produces main exit2 and flush1, despite accepting no frame. The expected IO-failure result for this resource-free refusal is exit3. Main's emission helper currently ignores write's result. Receipt: supervisor-setup-c0-first-source-independent-probes-20261114.json.

Before the source fix, write ONLY tests/test_oracle9_w1_supervisor_setup_probe_review.py. Source264e1133 and frozen84 test stay read-only. Load candidate definitions via the existing lazy helper; call public main ONLY with definitely invalid relative application, never real/valid native inputs. Simulate the PUBLIC stdout buffer interface using standard contextlib redirection and capture stderr; no monkeypatch fixture, code/global-function substitution, loader/SDK replacement or real process.

Required oracles: complete exact-int write length + successful flush -> refusal exit2; invalid/short/zero/None/bool/negative/oversized/opaque write results -> exit3, exactly one write attempt, no retry, no flush after invalid write; opaque values never inspected by bool/eq/repr. A raised write/flush error or hostile control must also return exit3 without retry/raw stderr; valid write has one flush, failed write has none. Preserve every requested frame's exact closed bytes. Source control identity/errors must not be stringified or have traceback/context manually changed. This tests only safe preacquisition IO paths, not main's native success or retaining park.

After root reads all new oracles and measures/freezes RED against264e1133, source-only fix may close BOTH S1 and S2. Do not modify frozen84 or the qualifier/backend pins. No host or native operation yet.

## Routine decisions and limits

Root accepts exit3 for a failed emission after resource-free refusal or positively CLOSED Owner; host must never interpret it as a successful C0 observation. UNKNOWN still retains custody and parks. Parking before acquisition is conservative. Bytecode-interruption residuals remain explicit, not complete S/P B4 admission. Existing custody.first_control retains the first SDK control; other emission failures may be retained separately without replacing it. No new generic framework, Owner, profile or waiver of N1-N16.

## S1/S2 corrected; final static naming fix pending

Call26286 completed exit0/service success/is_errorFalse/no denials, recovered. Root read the entire delta against340line264e1133. Candidatebb9acae4 temporarily registers definitions and restores a prior binding; an existing blocking None binding is refused without mutation, accepted as a routine fail-closed choice. Exact-int/full-length write is required before flush, no retry. Both frozen tests remain unchanged.

Measured2083relatedPASS including99own,0failures/errors/skips,28.026s. Independent actual-public-loader and same zero-write-main probes now PASS. Ruff/format377 PASS. Mypy win32 targets3.11/3.14 each report3 static errors at main342-344: emission assignment reuses the name `failure` bound by the preceding except. Rename ONLY the emission target/uses to a distinct name; no control/data-flow change or suppression. Preserve the source/QA before this naming fix, read every delta and repeat final gates on the resulting exact source. No native host or native execution yet.

## Final exact-source acceptance under delegated review

Call87797 completed exit0/service success/is_errorFalse/no denials, recovered. Root read the complete3-name delta: emission_failure replaces only the emission tuple target and two uses. Original exception binding and control flow stay intact. Final source43ffbf92 has355lines/13196bytes. Frozen84d2180060 and frozen15a9e0430a remain unchanged.

Final exact-source matrix2083PASS including99C0own,0failures/errors/skips/deselections,28.392s. Product/test Ruff, contracted PoC lint, format377 and strict mypy win32 targets3.11/3.14 all PASS;3.14 static only. No further reproduced blocker in this increment.

Accepted only as the concrete C0 entry before native qualification. run_c0 is tested with faithful backend fakes; main's public preacquisition IO paths are tested with ordinary stream redirection, without replacing production functions. Real main success, retained UNKNOWN parking and native SDK/host transport are not dynamically proven. Bytecode-interruption residuals, external containment and every N1-N16/product gate remain OPEN. Native host/conditions require their own prospective review before implementation/execution. No production readiness claim.
