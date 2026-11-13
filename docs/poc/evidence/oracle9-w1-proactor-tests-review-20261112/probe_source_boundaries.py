"""Independent root QA through public Pump APIs and the frozen fake SDK only."""

import hashlib
import json
import runpy
from pathlib import Path
from types import SimpleNamespace


HERE = Path("docs/poc/evidence/oracle9-w1-proactor-tests-review-20261112")
SOURCE = Path("docs/poc/oracle9_w1_proactor_pump.py")
TEST = Path("tests/test_oracle9_w1_proactor_pump.py")


def fixture():
    ns = runpy.run_path(str(TEST), run_name="_root_source_boundary_fakes")
    pm = SimpleNamespace(**runpy.run_path(str(SOURCE), run_name="_root_source_boundary"))
    loop = ns["FakeLoop"]()
    return ns, pm, loop, ns["make_pump"](pm, loop)


def cleanup_fakes(loop):
    for coro in loop.task_coros:
        coro.close()


def admission_read_failure(site, control=False, key="record_id", fail_on=1):
    ns, pm, loop, pump = fixture()
    req, events, auth = ns["request_for"](loop, 1)
    probes = []
    failure = ns["FalseCtl"](probes) if control else OSError(ns["CANARY"])

    class RefusingRead:
        def __init__(self, delegate, key):
            self.delegate, self.key = delegate, key
            self.reads = 0

        def __getattr__(self, name):
            if name == self.key:
                self.reads += 1
                if self.reads == fail_on:
                    raise failure
            return getattr(self.delegate, name)

    if site == "request":
        proxy = RefusingRead(req, key)
        bad = proxy
    else:
        bad = ns["request_for"](loop, 1)[0]
        proxy = RefusingRead(events, "started")
        bad.events = proxy
    caught = None
    try:
        pump.schedule_start(bad)
    except BaseException as error:
        caught = error
    # A validated immutable snapshot may read each field once. A second getter
    # that is never called cannot be required to fail: that admission is valid.
    single_read_admission = caught is None and proxy.reads < fail_on
    clean = single_read_admission or ((caught is failure) if control else (
        type(caught) is pm.PumpFault
        and caught.args == ()
        and caught.__cause__ is None
        and caught.__context__ is None
    ))
    idle = auth.calls == 0 and events.seen == []
    idle = idle and loop.count("call_at") == (1 if single_read_admission else 0)
    canary_exposed = isinstance(caught, Exception) and ns["CANARY"] in str(caught)
    if not single_read_admission:
        pump.schedule_start(req)  # a refusal must not consume its record id
    pump.run_until(loop.t + 1.0, lambda: "closed" in events.names())
    recovered = auth.calls == 1 and events.names()[-1] == "closed"
    cleanup_fakes(loop)
    return {
        "case": f"{site}-{key}-read{fail_on}" + ("-control" if control else "-exception"),
        "exception_type": type(caught).__name__,
        "getter_reads": proxy.reads,
        "single_read_admission": single_read_admission,
        "canary_exposed": canary_exposed,
        "no_admission_effects": idle,
        "subsequent_valid_request": recovered,
        "control_bool_probes": len(probes),
        "pass": clean and idle and recovered and not probes and not canary_exposed,
    }


def early_close(close_in_callback):
    ns, pm, loop, pump = fixture()
    loop.push_script("act-term-0", ns["ProcScript"](prestart=True))
    req, events, auth = ns["request_for"](loop, 1)
    if close_in_callback:
        events.hooks["closed"] = lambda: events.handle.close()
    pump.schedule_start(req)
    caught = None
    try:
        pump.run_until(loop.t + 1.0, lambda: "closed" in events.names())
        pump.run_until(loop.t + 1.0, lambda: False)  # let pending S4 validate its outcome
    except BaseException as error:
        caught = error
    if not close_in_callback:
        events.handle.close()
    closed = pump.close()
    cleanup_fakes(loop)
    return {
        "case": "prestart-close-in-callback" if close_in_callback else "prestart-close-after-run",
        "exception_type": type(caught).__name__ if caught is not None else None,
        "events": events.names(),
        "authorizations": auth.calls,
        "explicit_closes": loop.count("transport.close"),
        "sdk_kills": loop.count("sdk.kill"),
        "pump_closed": closed,
        "pass": caught is None and auth.calls == 1 and closed is True
        and events.names() == ["started", "pipe_lost", "pipe_lost", "exited", "closed"]
        and loop.count("transport.close") == 1 and loop.count("sdk.kill") == 0,
    }


rows = [
    admission_read_failure("request"), admission_read_failure("events"),
    admission_read_failure("request", key="record_id", fail_on=2),
    admission_read_failure("request", key="events", fail_on=2),
    admission_read_failure("request", key="stdin_pipe", fail_on=2),
    admission_read_failure("request", control=True),
    admission_read_failure("request", control=True, fail_on=2),
    early_close(False), early_close(True),
]
result = {
    "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    "test_sha256": hashlib.sha256(TEST.read_bytes()).hexdigest(),
    "subject": "public Pump API with frozen fake SDK; binding never called",
    "rows": rows,
    "passed": sum(r["pass"] for r in rows),
    "failed": sum(not r["pass"] for r in rows),
    "native_effects": False,
}
(HERE / "probe-source-boundaries-result.json").write_bytes(
    (json.dumps(result, indent=2) + "\n").encode()
)
print(json.dumps(result))
raise SystemExit(0 if result["failed"] == 0 else 1)
