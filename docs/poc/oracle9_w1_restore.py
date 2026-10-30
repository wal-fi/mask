"""One-shot recovery of the unstarted W1 install CID. No A/B/install/retry.

Uses the frozen coordinator only as a library for bounded CLI and restoration.
The consumed attempt and its failed result remain unchanged.
"""

import asyncio
import hashlib
import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "docs/poc/oracle9_w1_run.py"
RUNNER_SHA = "4bc0b083c9df44edd2aa532de7f43cf9f7f9f5a581edb267d8414d21057fd753"
TASK = "8c0680599bcc4a2db241bbfbcf6669dc"
CID = "72891af0601c6b787a18673db037a4155e0cec344d50605ecc540eab8160c883"
NAME = "maskgw-ol9-w1-8c0680599bcc-install"
INSPECT_SHA = "04fe93b220e163b1b3aeeeef796e7d1991df2cfa6f7f54d35e5062f8a134c43e"
WITNESS = REPO / "docs/poc/evidence/oracle9-w1-run-attempt1-20261027"
WITNESS_SHA = "ce09d005178d52fb090886e2de70fa42463b6d0bd7db6b396d1dea82f71976bf"


def need(value, reason):
    if not value:
        raise RuntimeError(reason)


def library():
    raw = RUNNER.read_bytes()
    need(len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == RUNNER_SHA, "RUNNER_PIN")
    ns = {"__name__": "_w1_restore_frozen_runner", "__file__": str(RUNNER)}
    exec(compile(raw, str(RUNNER), "exec"), ns)
    return ns


def witness(run, name):
    raw = run["pinned"](WITNESS / "transport-manifest.json", WITNESS_SHA)
    manifest = json.loads(raw)
    expected = manifest["files"][name]
    raw = run["pinned"](WITNESS / name, expected["sha256"])
    need(len(raw) == expected["bytes"], "WITNESS_SIZE")
    return json.loads(raw)


def admit_container(host, info, raw):
    need(hashlib.sha256(raw).hexdigest() == INSPECT_SHA, "INSPECT_CHANGED")
    builders = host.libs["builders"]
    command = builders["native_command"](
        builders["read_pinned"](builders["PAYLOAD"], builders["PAYLOAD_SHA"], 32768),
        "install",
        TASK,
    )
    # Reuse the original full security/profile validator; only the added,
    # disproved requirement to inherit Desktop ports.scheme is inapplicable.
    host.policy["validate_container"](
        info, NAME, TASK, builders["IMAGE"], command, False, host.libs["foundation"]
    )
    need(info["Id"] == CID, "CID")
    need(
        info["Config"]["Labels"]
        == {
            "maskgw.task": TASK,
            "maskgw.source-sha256": builders["PAYLOAD_SHA"],
            "maskgw.manifest-sha256": builders["MANIFEST_SHA"],
        },
        "LABELS",
    )
    need(
        info["State"]["Status"] == "created"
        and info["State"]["Running"] is False
        and info["State"]["Pid"] == 0,
        "NOT_UNSTARTED",
    )


async def recover(host):
    code, raw = await host.cli(
        "recovery-inspect", "inspect", "--type", "container", CID, cleanup=True
    )
    need(code == 0, "INSPECT_EXIT")
    values = json.loads(raw)
    need(type(values) is list and len(values) == 1, "INSPECT_SHAPE")
    admit_container(host, values[0], raw)
    host.write_new("inspect-before.json", raw)
    code, raw = await host.cli("recovery-rm", "rm", CID, cleanup=True)
    need(code == 0, "RM_EXIT")
    host.write_new("rm.stdout", raw)
    code, raw = await host.cli(
        "recovery-absent", "ps", "-aq", "--no-trunc", "--filter", "id=" + CID, cleanup=True
    )
    need(code == 0 and not raw.strip(), "ABSENCE_UNPROVEN")
    host.result["owned_cleanup"] = True
    await host.empty_inventory("recovery-inventory", cleanup=True)
    host.result["inventory_restored"] = True
    await host.restore_desktop()  # same boot/PID/FILETIME, fresh inventory, bounded stop+absence


async def main(root):
    run = library()
    need(
        sys.platform == "win32"
        and sys.flags.isolated == 1
        and sys.flags.dont_write_bytecode == 1
        and not sys.flags.optimize,
        "RUNTIME",
    )
    need(
        root.parent == run["HOME"] / "AppData/Local/Temp"
        and re.fullmatch(r"maskgw-oracle9-w1-restore-20261027-[0-9a-f]{32}", root.name),
        "ROOT",
    )
    need(
        not getattr(root.lstat(), "st_file_attributes", 0) & 0x400
        and {p.name for p in root.iterdir()} == {"state.json"},
        "FRESH_ROOT",
    )
    state = json.loads(run["regular"](root / "state.json", 4096))
    need(
        set(state) == {"kind", "program_sha256", "invoked"}
        and state["kind"] == "w1-stopped-cid-recovery-v1"
        and state["invoked"] is False,
        "STATE",
    )
    run["pinned"](Path(__file__), state["program_sha256"])
    old_state = witness(run, "attempt.json")
    need(
        old_state["task"] == TASK
        and old_state["phase"] == "ABORTED"
        and old_state["invoked"] is True
        and old_state["program_sha256"] == RUNNER_SHA,
        "OLD_STATE",
    )
    host = run["Host"](root, old_state)
    desktop = witness(run, "desktop.json")
    need(
        desktop
        == {
            "identity": {"created": "134375830785499297", "name": "Docker Desktop", "pid": 27644},
            "initial_active": False,
            "phase": "STARTED",
        },
        "DESKTOP_WITNESS",
    )
    host.initial_active, host.started = False, desktop["identity"]
    host.cycle = host.libs["core"]["decode"](run["json_bytes"](witness(run, "cycle.json")))
    host.pins(cleanup=True)
    host.write_new("invoked.json", run["json_bytes"](state))
    try:
        await recover(host)
    except BaseException as error:
        host.result.update(failure_category=type(error).__name__, outcome="RECOVERY_PENDING")
    passed = all(
        host.result.get(k) is True
        for k in ("owned_cleanup", "inventory_restored", "desktop_restored")
    )
    host.result.update(
        outcome="W1_OWNED_RESOURCES_RESTORED" if passed else "RECOVERY_PENDING",
        commands=host.commands,
    )
    host.save("result.json", host.result)
    print(
        json.dumps(
            {
                k: host.result.get(k)
                for k in (
                    "outcome",
                    "owned_cleanup",
                    "inventory_restored",
                    "desktop_restored",
                    "desktop_state",
                )
            }
        ),
        flush=True,
    )
    return 0 if passed else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(2)
    try:
        status = asyncio.run(main(Path(sys.argv[1])))
    except BaseException as error:
        print(
            json.dumps({"outcome": "RECOVERY_REFUSED", "category": type(error).__name__}),
            flush=True,
        )
        status = 1
    raise SystemExit(status)
