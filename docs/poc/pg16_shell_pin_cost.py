"""Read-only public pin timing. No capture on import, no operational attempt."""

import sys

# Reject a native misinvocation before importing Python files or captures.
if __name__ == "__main__" and not (
    sys.platform == "win32"
    and sys.version_info[:3] == (3, 11, 3)
    and sys.flags.isolated == 1
    and sys.flags.dont_write_bytecode == 1
    and sys.flags.optimize == 0
    and len(sys.argv) == 1
):
    refusal = '{"category":"RUNTIME","kind":"MASKGW_PG16_PIN_COST_V1","outcome":"NOT_PASSED"}\n'
    try:
        written = sys.stdout.write(refusal)
        if type(written) is not int or written != len(refusal):
            raise OSError("OUTPUT")
        sys.stdout.flush()
    except BaseException:
        try:
            sys.stdout.close()
        except BaseException:
            pass
    raise SystemExit(1)

import asyncio
from dataclasses import asdict
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import stat
import threading
import time

REPO = Path(__file__).resolve().parents[2]
ENTRY = "docs/poc/pg16_shell_run.py"
ENTRY_SHA = "afaffad00ac2a2e9cd1666bdce5e18e6173240b4719592931b9cbda19c90c657"
KIND = "MASKGW_PG16_PIN_COST_V1"
CYCLES = 5
MAX_REPORT = 16384
MAX_NS = 2**63 - 1
TASK = "c" * 32  # public diagnostic identity; never an operational FRESH state


class Mode(StrEnum):
    NORMAL = "NORMAL"
    CLEANUP = "CLEANUP"
    FINAL0 = "FINAL0"
    FINAL23 = "FINAL23"


class Code(StrEnum):
    RUNTIME = "RUNTIME"
    SOURCE = "SOURCE"
    CLOCK = "CLOCK"
    EFFECT = "EFFECT"
    IO = "IO"
    PIN = "PIN"
    OUTPUT = "OUTPUT"
    INTERRUPTED = "INTERRUPTED"
    INTERNAL = "INTERNAL"


class CostError(Exception):
    def __init__(self, category):
        self.category = category if type(category) is Code else Code.INTERNAL
        super().__init__(self.category.value)


def need(value, code):
    if not value:
        raise CostError(code) from None


def runtime():
    need(
        sys.platform == "win32"
        and sys.version_info[:3] == (3, 11, 3)
        and sys.flags.isolated == 1
        and sys.flags.dont_write_bytecode == 1
        and sys.flags.optimize == 0,
        Code.RUNTIME,
    )


def quiet(hosts=()):
    main = threading.main_thread()
    need(threading.current_thread() is main and threading.enumerate() == [main], Code.EFFECT)
    # Neither of these inspections constructs a loop or policy.
    need(
        asyncio.events._event_loop_policy is None and asyncio.events._get_running_loop() is None,
        Code.EFFECT,
    )
    for host in hosts:
        need(
            not host._owners
            and not host._host_tasks
            and host._b_started is None
            and not host._monitor_attempted,
            Code.EFFECT,
        )
        need(
            all(m._started is False and m.thread is None for m in host._monitors.values()),
            Code.EFFECT,
        )


def absent(path):
    missing = False
    try:
        path.lstat()
    except FileNotFoundError:
        missing = True
    need(missing, Code.EFFECT)


def capture():
    path = REPO / ENTRY
    info = path.lstat()
    need(
        stat.S_ISREG(info.st_mode)
        and not getattr(info, "st_file_attributes", 0) & 0x400
        and info.st_size <= 65536,
        Code.SOURCE,
    )
    raw = path.read_bytes()
    need(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == ENTRY_SHA, Code.SOURCE)
    namespace = {"__name__": "_pg16_pin_cost_entry", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace


def diagnostic_state(entry):
    host = entry["H"]
    profile, _ = host["P"]["captured"](*host["SOURCES"]["profile"])
    delivery, _ = host["P"]["captured"](*host["SOURCES"]["delivery"])
    return {
        "kind": "MASKGW_PG16_PIN_COST_STATE_V1",
        "task": TASK,
        "pins": dict(entry["R"]["LIBRARIES"].values()),
        "host_sha256": entry["HOST_SHA"],
        "entry_sha256": ENTRY_SHA,
        "create_measurements": {
            case: profile["blueprint"](TASK, profile["R"]["Case"](case))[1]
            for case in host["CASES"]
        },
        "delivery_plan": {
            case: asdict(delivery["delivery_for"](case)[1]) for case in host["CASES"]
        },
    }


def forbidden_abort():
    raise CostError(Code.EFFECT)


def monitors(host, root):
    source = host.__class__.__init__.__globals__
    for index, case in enumerate(source["CASES"], 1):
        store = host.pg["watch"]["Store"](0.0)
        host._stores[case] = store
        host._monitors[case] = host.pg["watch"]["Watchdog"](
            root / ("watch-" + str(index).zfill(2)),
            store,
            host._cleanup_lock,
            forbidden_abort,
            host.pg_raw[source["SOURCES"]["emergency"][0]],
            host.pg_raw[source["SOURCES"]["policy"][0]],
            host.captured[source["R"]["LIBRARIES"]["bounded"][0]],
            host.pg_raw[source["SOURCES"]["identity"][0]],
            host.pg_raw[source["SOURCES"]["volumes"][0]],
        )


def elapsed(call):
    opened = time.perf_counter_ns()
    need(type(opened) is int and 0 <= opened <= MAX_NS, Code.CLOCK)
    value = call()
    closed = time.perf_counter_ns()
    need(type(closed) is int and opened < closed <= MAX_NS, Code.CLOCK)
    return value, closed - opened


def setup(entry, root):
    state, builder_ns = elapsed(lambda: diagnostic_state(entry))

    def build():
        host = entry["H"]["Host"](root, dict(state))
        return host, entry["Context"](root, dict(state), host)

    (host0, context0), build0 = elapsed(build)
    (host23, context23), build23 = elapsed(build)
    _, monitors23 = elapsed(lambda: monitors(host23, root))
    need(host0 is not host23 and not host0._monitors and len(host23._monitors) == 23, Code.EFFECT)
    return (
        host0,
        context0,
        host23,
        context23,
        {
            "builder_ns": builder_ns,
            "host_context0_ns": build0,
            "host_context23_ns": build23,
            "monitors23_ns": monitors23,
        },
    )


def public_sources(entry):
    return sorted(
        {
            ENTRY_SHA,
            entry["HOST_SHA"],
            *(digest for _, digest in entry["H"]["SOURCES"].values()),
            *entry["TRANSITIVE_PINS"].values(),
        }
    )


def measurement():
    runtime()
    quiet()
    root = REPO / ".maskgw-pg16-pin-cost-not-materialized"
    absent(root)
    entry = capture()
    host0, context0, host23, context23, construction = setup(entry, root)
    quiet((host0, host23))
    operations = {
        Mode.NORMAL: lambda: host23.pins(cleanup=False),
        Mode.CLEANUP: lambda: host23.pins(cleanup=True),
        Mode.FINAL0: lambda: entry["final_pins"](context0),
        Mode.FINAL23: lambda: entry["final_pins"](context23),
    }
    samples = []
    for cycle in range(CYCLES):
        for mode in Mode:
            _, duration = elapsed(operations[mode])
            samples.append({"cycle": cycle, "mode": mode.value, "ns": duration})
    quiet((host0, host23))
    absent(root)
    stats = {}
    for mode in Mode:
        values = sorted(row["ns"] for row in samples if row["mode"] == mode.value)
        need(len(values) == CYCLES, Code.OUTPUT)
        stats[mode.value] = {"observed_max_ns": values[-1], "median_ns": values[CYCLES // 2]}
    return {
        "kind": KIND,
        "outcome": "MEASURED",
        "cycles": CYCLES,
        "sample_count": len(samples),
        "samples": samples,
        "stats": stats,
        "construction": construction,
        "source_sha256": public_sources(entry),
        "host_counts": [0, 23],
    }


def validate(report):
    need(type(report) is dict, Code.OUTPUT)
    if report.get("outcome") == "NOT_PASSED":
        need(
            set(report) == {"kind", "outcome", "category"}
            and report["kind"] == KIND
            and type(report["category"]) is str
            and report["category"] in tuple(code.value for code in Code),
            Code.OUTPUT,
        )
        return
    need(
        set(report)
        == {
            "kind",
            "outcome",
            "cycles",
            "sample_count",
            "samples",
            "stats",
            "construction",
            "source_sha256",
            "host_counts",
        }
        and report["kind"] == KIND
        and report["outcome"] == "MEASURED"
        and type(report["cycles"]) is int
        and report["cycles"] == CYCLES
        and type(report["sample_count"]) is int
        and report["sample_count"] == CYCLES * len(Mode)
        and type(report["host_counts"]) is list
        and len(report["host_counts"]) == 2
        and all(type(count) is int for count in report["host_counts"])
        and report["host_counts"] == [0, 23],
        Code.OUTPUT,
    )
    rows = report["samples"]
    need(type(rows) is list and len(rows) == CYCLES * len(Mode), Code.OUTPUT)
    for index, row in enumerate(rows):
        need(
            type(row) is dict
            and set(row) == {"cycle", "mode", "ns"}
            and type(row["cycle"]) is int
            and row["cycle"] == index // len(Mode)
            and type(row["mode"]) is str
            and row["mode"] == tuple(Mode)[index % len(Mode)].value
            and type(row["ns"]) is int
            and 0 < row["ns"] <= MAX_NS,
            Code.OUTPUT,
        )
    need(
        type(report["stats"]) is dict and set(report["stats"]) == {mode.value for mode in Mode},
        Code.OUTPUT,
    )
    for mode in Mode:
        values = sorted(row["ns"] for row in rows if row["mode"] == mode.value)
        row = report["stats"][mode.value]
        need(
            type(row) is dict
            and set(row) == {"observed_max_ns", "median_ns"}
            and all(type(value) is int and 0 < value <= MAX_NS for value in row.values()),
            Code.OUTPUT,
        )
        need(
            row == {"observed_max_ns": values[-1], "median_ns": values[CYCLES // 2]},
            Code.OUTPUT,
        )
    construction = report["construction"]
    need(
        type(construction) is dict
        and set(construction)
        == {"builder_ns", "host_context0_ns", "host_context23_ns", "monitors23_ns"}
        and all(type(value) is int and 0 < value <= MAX_NS for value in construction.values()),
        Code.OUTPUT,
    )
    digests = report["source_sha256"]
    need(
        type(digests) is list
        and 0 < len(digests) <= 32
        and all(
            type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
            for value in digests
        )
        and digests == sorted(set(digests)),
        Code.OUTPUT,
    )


def collect():
    report = None
    try:
        report = measurement()
        validate(report)
        raw = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
        need(len(raw) <= MAX_REPORT, Code.OUTPUT)
        return raw
    except BaseException as error:
        code = Code.INTERNAL
        if type(error) is CostError and type(error.category) is Code:
            code = error.category
        elif type(error) is KeyboardInterrupt:
            code = Code.INTERRUPTED
        elif type(error) in (OSError, FileNotFoundError, PermissionError):
            code = Code.IO
        elif type(error) is RuntimeError:
            code = Code.PIN
        report = {"kind": KIND, "outcome": "NOT_PASSED", "category": code.value}
    return (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


if __name__ == "__main__":
    output = collect()
    try:
        written = sys.stdout.buffer.write(output)
        if type(written) is not int or written != len(output):
            raise OSError("OUTPUT")
        sys.stdout.buffer.flush()
    except BaseException:
        try:
            sys.stdout.close()
        except BaseException:
            pass
        raise SystemExit(1) from None
    raise SystemExit(0 if json.loads(output)["outcome"] == "MEASURED" else 1)
