# Mask Gateway W1 host reactor — proposed Gemini task

Only public source/contract snapshots, no runtime, credentials or private configuration.
This handoff is PREPARED, NOT SENT. Sending requires applicable explicit consent;
the previous Gemini consent covered only a different four-file EXPECT payload.

If authorized, use gemini-4-argon-high / effort high in this scratch context.
Read HOST-DESIGN-REVIEW.md first. Write ONLY HOST-DESIGN.md here: a prospective
minimal pure host reactor and future duplex-port contract, not code or tests.
No terminal, commands, execution, network, external reads, other writers or changes
to reference files. Public originals and installed app remain fixed. The C2 session
is at API429; no retry before2026-11-10T16:50:00Z. Root reviews every output.

Main89c99c65 pins driverb54a8a94 and pure4c155d76; EXPECTce6ff389.849 related
fake tests are historical green; no native/product gate is closed. Do not rewrite
or duplicate these accepted pieces. Exact three individual file binds RO. Future
host pins main, main is not self-verified. No public control encoder: use minimal
fixed16byte pack checked by decode_control; reuse ControlMachine for order.

Line<=512bytes INCLUDING LF,<=56lines,<=50controls. Exact b54 event keys, no
invented Threads field in GUARD or digest field in RESULT. One pending action;
advance only on exact full own receipt. SENT is local handoff, not container
receipt; UNKNOWN never retries. T1 terminate; T2 pause then restore before ACK;
T4 metadata observation->STOP/NOSTOP; T5 backend-zero before ACK; T6 timely
identity-bound kill/reap/backend proof. Typed future actions are not OS proof.

T6 clock bound is critical: never receive_time+live_window_ms. Use host time
BEFORE sending GO25 as lower bound to the driver calculation, with explicit
conservative margin and native clock/admission assumptions. No host/Linux clock
equality. Main exit64..70 and HOLD are failures/retention; natural69 and exit137
alone cannot prove a successful intended kill. A valid protocol transcript alone
is not production availability or permission to execute.

Close exact API/state/immutable DTO/receipt/error shapes, timing rules, bounded
parser/partial delivery/EOF/retention, focused fake test oracles, and the minimal
first tests-only increment before its module. No generic OS/provenance framework,
new loader, SDK change, prepared root/state/nonce/credentials/command/deploy.
Old NATIVE-PLAN is history with known stale clauses; reconcile facts, don't claim
an absent native test has passed. Upstream code/app124/state16/consumed attempt
remain fixed. All T5 native/B1/B2/D090gate2/C1/ingress/production gates OPEN.
