"""Root QA: compare only the proposed fake with the pinned SDK waiter contract."""

import json
import runpy
from pathlib import Path


TEST = Path("tests/test_oracle9_w1_proactor_pump.py")
OUT = Path(
    "docs/poc/evidence/oracle9-w1-proactor-tests-review-20261112/"
    "probe-waiter-controls-result.json"
)


def probe(control_type):
    ns = runpy.run_path(str(TEST), run_name="_root_fake_sdk_probe")
    loop = ns["FakeLoop"]()
    control = control_type()
    transport_type = ns["FakeTransport"]
    original = transport_type.connect_pipes

    def resolve_with_control(transport, waiter):
        waiter.set_exception(control)

    transport_type.connect_pipes = resolve_with_control
    protocol = ns["DummyProtocol"]([])

    async def body():
        await loop.subprocess_exec(
            lambda: protocol,
            "helper",
            "act-term-0",
            stdin=ns["FAKE_DEVNULL"],
            stdout=ns["FAKE_PIPE"],
            stderr=ns["FAKE_PIPE"],
        )

    observed = None
    loop.create_task(body())
    loop.call_at(loop.t + 1.0, loop.stop)
    try:
        loop.run_forever()
    except BaseException as error:
        observed = error
    finally:
        transport_type.connect_pipes = original
        for coro in loop.task_coros:
            coro.close()
    row = {
        "kind": control_type.__name__,
        "same_control_propagated": observed is control,
        "sdk_close": loop.count("sdk.close"),
        "sdk_kill": loop.count("sdk.kill"),
    }
    row["pass"] = (
        row["same_control_propagated"]
        and row["sdk_close"] == 0
        and row["sdk_kill"] == 0
    )
    return row


rows = [probe(KeyboardInterrupt), probe(SystemExit)]
result = {
    "source": "CPython v3.11.3 windows_events.py:403-410",
    "subject": "proposed FakeLoop only; no Proactor implementation loaded",
    "rows": rows,
    "passed": sum(row["pass"] for row in rows),
    "failed": sum(not row["pass"] for row in rows),
    "native_effects": False,
}
OUT.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
print(json.dumps(result))
raise SystemExit(0 if result["failed"] == 0 else 1)
