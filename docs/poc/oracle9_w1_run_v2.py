"""Specific W1 revision: five hooks on the immutable, reviewed coordinator.

No Desktop/Docker/clock action on import. Never invokes the historical main.
"""

import asyncio
import hashlib
import json
from pathlib import Path
import re
import stat
import sys

REPO = Path(__file__).resolve().parents[2]
ORIGINAL = REPO / "docs/poc/oracle9_w1_run.py"
ORIGINAL_SHA = "4bc0b083c9df44edd2aa532de7f43cf9f7f9f5a581edb267d8414d21057fd753"


def need(value, reason):
    if not value:
        raise RuntimeError(reason)


def original():
    info = ORIGINAL.lstat()
    need(
        stat.S_ISREG(info.st_mode)
        and not getattr(info, "st_file_attributes", 0) & 0x400
        and info.st_size <= 65536,
        "ORIGINAL_TYPE",
    )
    raw = ORIGINAL.read_bytes()
    need(
        len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == ORIGINAL_SHA, "ORIGINAL_PIN"
    )
    ns = {"__name__": "_w1_v2_frozen_original", "__file__": str(ORIGINAL)}
    exec(compile(raw, str(ORIGINAL), "exec"), ns)
    return ns


R = original()
BaseHost = R["Host"]
CLI = R["CLI"]
WATCHDOG_SECONDS = R["WATCHDOG_SECONDS"]


def own(host, record, info):
    cid = host.policy["identity"](info, record["name"], host.state["task"], record["image"])
    need(record["cid"] is None or record["cid"] == cid, "OWN_ID_CHANGED")
    need(
        info["Config"]["Cmd"] == record["command"]
        and info["Config"]["Entrypoint"] == host.libs["foundation"]["ENTRY"],
        "OWN_COMMAND",
    )
    return cid


def action_for(core, previous, current):
    phase = core["Phase"]
    if previous is None:
        need(current.phase is phase.A and current.observations == 0, "JOURNAL_START")
        return "START"
    if (
        current.phase is phase.OBSERVING
        and previous.phase in (phase.A, phase.OBSERVING)
        and current.observations == previous.observations + 1
    ):
        return "OBSERVE"
    if (
        current.phase is phase.READY
        and previous.phase is phase.OBSERVING
        and current.observations == previous.observations == 9
    ):
        return "READY"
    if current.phase is phase.B_CONSUMED and previous.phase is phase.READY:
        return "B"
    raise RuntimeError("JOURNAL_TRANSITION")


def replay(core, records, require_b=True):
    need(type(records) in (list, tuple) and 1 <= len(records) <= 12, "JOURNAL_COUNT")
    head, state = "0" * 64, None
    for index, raw in enumerate(records):
        need(type(raw) is bytes and 0 < len(raw) <= 8192, "JOURNAL_SIZE")
        value = json.loads(raw)
        need(
            type(value) is dict
            and set(value)
            == {"kind", "index", "action", "sample", "state_encoded", "previous_sha256"}
            and R["json_bytes"](value) == raw,
            "JOURNAL_SCHEMA",
        )
        need(
            value["kind"] == "w1-cycle-checkpoint-v1"
            and type(value["index"]) is int
            and value["index"] == index
            and value["previous_sha256"] == head,
            "JOURNAL_CHAIN",
        )
        sample = value["sample"]
        need(
            type(sample) is dict and set(sample) == {"boot", "tick_ms", "utc_100ns"},
            "JOURNAL_SAMPLE",
        )
        sample = core["Sample"](**sample)
        if state is None:
            need(value["action"] == "START", "JOURNAL_ACTION")
            expected = core["start"](sample)
        else:
            need(value["action"] in ("OBSERVE", "READY", "B"), "JOURNAL_ACTION")
            admission = core["advance"](state, sample, value["action"])
            need(admission.decision == core["Decision"].ACCEPT, "JOURNAL_ADMISSION")
            expected = admission.state
        need(
            type(value["state_encoded"]) is str
            and value["state_encoded"].encode("ascii") == core["encode"](expected),
            "JOURNAL_STATE",
        )
        need(value["action"] == action_for(core, state, expected), "JOURNAL_ACTION")
        state, head = expected, hashlib.sha256(raw).hexdigest()
    need(
        not require_b or (len(records) == 12 and state.phase is core["Phase"].B_CONSUMED),
        "JOURNAL_INCOMPLETE",
    )
    return state, head


class Host(BaseHost):
    def pins(self, cleanup=False):
        super().pins(cleanup=cleanup)
        need(self.state["program_sha256"] == ORIGINAL_SHA, "INNER_PIN")
        R["pinned"](Path(__file__), self.state["entry_sha256"])

    def save(self, name, value):
        records = getattr(self, "_checkpoint_records", ())
        core = self.libs["core"]
        if name == "cycle.json":
            current = core["decode"](R["json_bytes"](value))
            encoded = core["encode"](current).decode("ascii")
            if current.phase not in (core["Phase"].FAILED, core["Phase"].ABORTED) and (
                not records or json.loads(records[-1])["state_encoded"] != encoded
            ):
                previous = (
                    None
                    if not records
                    else core["decode"](json.loads(records[-1])["state_encoded"].encode("ascii"))
                )
                data = {
                    "kind": "w1-cycle-checkpoint-v1",
                    "index": len(records),
                    "action": action_for(core, previous, current),
                    "sample": core["_sample_map"](current.last),
                    "state_encoded": encoded,
                    "previous_sha256": "0" * 64
                    if not records
                    else hashlib.sha256(records[-1]).hexdigest(),
                }
                raw = R["json_bytes"](data)
                replay(core, (*records, raw), require_b=False)
                super().save(name, value)
                self.write_new("checkpoint-" + str(len(records)).zfill(2) + ".json", raw, 8192)
                self._checkpoint_records = (*records, raw)
                return
        super().save(name, value)
        if name == "rejected-sample.json":
            self.write_new(
                "checkpoint-rejected.json",
                R["json_bytes"](
                    {
                        "kind": "w1-cycle-rejected-v1",
                        "action": value["action"],
                        "sample": value["sample"],
                        "reason": value["reason"],
                        "state_encoded": core["encode"](self.cycle).decode("ascii"),
                        "previous_sha256": "0" * 64
                        if not records
                        else hashlib.sha256(records[-1]).hexdigest(),
                    }
                ),
                8192,
            )

    async def cli(self, label, *args, **kwargs):
        if label == "commit-own":
            installs = [r for r in self.records if r["role"] == "install"]
            need(len(installs) == 1 and installs[0]["cid"] is not None, "COMMIT_OWNER")
            expected = (
                "commit",
                "--change",
                "USER 10001:10001",
                "--change",
                "WORKDIR /var/empty",
                "--change",
                "ENTRYPOINT " + json.dumps(self.libs["foundation"]["ENTRY"]),
                "--change",
                "CMD []",
                installs[0]["cid"],
                self.tag,
            )
            need(args == expected, "COMMIT_SHAPE")
            value = self.base["Config"]["Labels"]["desktop.docker.io/ports.scheme"]
            need(value == "v2", "COMMIT_PUBLIC_LABEL")
            args = (
                *args[:-2],
                "--change",
                "LABEL desktop.docker.io/ports.scheme=" + value,
                *args[-2:],
            )
            self.write_new("commit-arguments.json", R["json_bytes"](list(args)), 4096)
        return await super().cli(label, *args, **kwargs)

    async def inspect_own(self, record, cleanup=False):
        code, raw = await self.cli(
            "inspect-" + record["role"],
            "inspect",
            "--type",
            "container",
            record["cid"] or record["name"],
            cleanup=cleanup,
        )
        need(code == 0, "OWN_INSPECT")
        values = json.loads(raw)
        need(type(values) is list and len(values) == 1, "OWN_SHAPE")
        info = values[0]
        cid = own(self, record, info)
        if not cleanup:
            self.policy["validate_container"](
                info,
                record["name"],
                self.state["task"],
                record["image"],
                record["command"],
                record["role"] == "probe",
                self.libs["foundation"],
            )
            need(
                info["Config"]["Labels"]
                == {
                    "maskgw.task": self.state["task"],
                    "maskgw.source-sha256": self.libs["builders"]["PAYLOAD_SHA"],
                    "maskgw.manifest-sha256": self.libs["builders"]["MANIFEST_SHA"],
                },
                "CONTAINER_LABELS_EXACT",
            )
        record["cid"] = cid
        self.record_intents()
        return info, raw

    def watchdog(self):
        if self.stop.wait(WATCHDOG_SECONDS):
            return
        self.fired.set()
        with self.active_lock:
            record = None if self.active is None else dict(self.active)
        if record is None:
            return
        try:
            self.pins(cleanup=True)
            bounded = self.libs["bounded"]["bounded"]

            async def stop_exact():
                code, raw = await bounded(
                    [
                        str(CLI),
                        "--context",
                        "desktop-linux",
                        "inspect",
                        "--type",
                        "container",
                        record["cid"],
                    ],
                    timeout=10,
                    limit=2 * 1024 * 1024,
                )
                need(code == 0, "WATCHDOG_INSPECT")
                values = json.loads(raw)
                need(type(values) is list and len(values) == 1, "WATCHDOG_SHAPE")
                info = values[0]
                cid = own(self, record, info)
                if info["State"]["Running"]:
                    code, _ = await bounded(
                        [str(CLI), "--context", "desktop-linux", "kill", "--signal", "KILL", cid],
                        timeout=10,
                        limit=65536,
                    )
                    need(code == 0, "WATCHDOG_KILL")

            asyncio.run(stop_exact())
        except BaseException:
            self.watchdog_failed = True


def journal_from_disk(host):
    files = sorted(host.root.glob("checkpoint-[0-9][0-9].json"))
    need(
        [p.name for p in files] == ["checkpoint-" + str(i).zfill(2) + ".json" for i in range(12)],
        "JOURNAL_FILES",
    )
    core = host.libs["core"]
    state, head = replay(core, [R["regular"](p, 8192) for p in files])
    records = getattr(host, "_checkpoint_records", ())
    need(
        len(records) == 12
        and core["encode"](state) == core["encode"](host.cycle)
        and head == hashlib.sha256(records[-1]).hexdigest(),
        "JOURNAL_BINDING",
    )
    return state, head


def admit(root):
    need(
        sys.platform == "win32"
        and sys.flags.isolated == 1
        and sys.flags.dont_write_bytecode == 1
        and sys.flags.optimize == 0
        and sys.version_info[:3] == (3, 11, 3),
        "HOST_RUNTIME",
    )
    need(
        root.parent == R["HOME"] / "AppData/Local/Temp"
        and re.fullmatch(r"maskgw-oracle9-w1-run-v2-20261027-[0-9a-f]{32}", root.name),
        "ROOT",
    )
    info = root.lstat()
    need(
        stat.S_ISDIR(info.st_mode)
        and not getattr(info, "st_file_attributes", 0) & 0x400
        and {p.name for p in root.iterdir()} == {"attempt.json"},
        "FRESH_ROOT",
    )
    state = json.loads(R["regular"](root / "attempt.json", 16384))
    need(
        type(state) is dict
        and set(state)
        == {
            "kind",
            "task",
            "program_sha256",
            "entry_sha256",
            "pins",
            "phase",
            "invoked",
            "create_measurements",
        },
        "STATE_SHAPE",
    )
    need(
        state["kind"] == "maskgw-oracle9-w1-run-v2"
        and state["phase"] == "FRESH"
        and state["invoked"] is False
        and type(state["task"]) is str
        and re.fullmatch(r"[0-9a-f]{32}", state["task"]),
        "STATE",
    )
    need(
        state["program_sha256"] == ORIGINAL_SHA
        and state["pins"] == dict(R["LIBRARIES"].values())
        and type(state["entry_sha256"]) is str
        and re.fullmatch(r"[0-9a-f]{64}", state["entry_sha256"]),
        "STATE_PINS",
    )
    R["pinned"](Path(__file__), state["entry_sha256"])
    return state


async def main(root):
    state = admit(root)
    host = Host(root, state)
    host.pins()
    need(R["measure_commands"](host) == state["create_measurements"], "COMMAND_MEASUREMENT")
    host.write_new(
        "invoked.json",
        R["json_bytes"](
            {
                "task": state["task"],
                "program_sha256": ORIGINAL_SHA,
                "entry_sha256": state["entry_sha256"],
            }
        ),
    )
    state.update(invoked=True, phase="INVOKED")
    host.save("attempt.json", state)
    try:
        await host.start_cycle()
        _, head = journal_from_disk(host)
        host.result.update(journal_verified=True, journal_last_sha256=head)
        await host.perform_b()
    except BaseException as error:
        host.result["failure_category"] = type(error).__name__
        if host.cycle is not None:
            host.cycle = host.libs["core"]["abort"](host.cycle)
            host.save("cycle.json", json.loads(host.libs["core"]["encode"](host.cycle)))
    finally:
        try:
            await host.cleanup_owned()
        except BaseException as error:
            host.result.update(owned_cleanup=False, cleanup_category=type(error).__name__)
        await host.restore_desktop()
        try:
            host.pins()
            host.result["inputs_unchanged"] = True
        except BaseException:
            host.result["inputs_unchanged"] = False
        success = (
            all(
                host.result.get(k) is True
                for k in (
                    "update_verified",
                    "owned_cleanup",
                    "inventory_restored",
                    "desktop_restored",
                    "inputs_unchanged",
                    "journal_verified",
                )
            )
            and not host.fired.is_set()
            and not host.watchdog_failed
            and "failure_category" not in host.result
        )
        host.result.update(
            outcome="ORACLE9_W1_CANDIDATE_VERIFIED" if success else "NOT_PASSED",
            commands=host.commands,
            watchdog_fired=host.fired.is_set(),
            checkpoint_count=len(getattr(host, "_checkpoint_records", ())),
        )
        if host.result.get("update_verified"):
            host.result["candidate_disposition"] = (
                "VERIFIED_LOCAL_RETAINED"
                if success
                else "VERIFIED_LOCAL_RETAINED_OVERALL_NOT_PASSED"
            )
        state.update(phase="FINISHED" if success else "ABORTED")
        host.save("attempt.json", state)
        host.save("result.json", host.result)
    print(
        json.dumps(
            {
                k: host.result[k]
                for k in ("outcome", "owned_cleanup", "inventory_restored", "desktop_restored")
            }
        ),
        flush=True,
    )
    return 0 if success else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(2)
    try:
        status = asyncio.run(main(Path(sys.argv[1])))
    except BaseException as error:
        print(
            json.dumps({"outcome": "W1_V2_REFUSED", "category": type(error).__name__}), flush=True
        )
        status = 1
    raise SystemExit(status)
