"""Single measured-profile T4 v2 attempt. Import defines only; never invokes historical mains."""

import asyncio
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
import time

REPO = Path(__file__).resolve().parents[2]
HOST_RELATIVE = "docs/poc/w1_bootstrap_t4_host.py"
HOST_SHA = "88e220ebb342bba6889dc0934a3872b3bac3e29e3583c24f60d5503ad1d18c70"
PROGRAM_SHA = "4bc0b083c9df44edd2aa532de7f43cf9f7f9f5a581edb267d8414d21057fd753"
V2_SHA = "b59388f52a38319c19c2c60b25100347d319a59c2778395cc68bea64d2bc0c37"


def need(value, category):
    if not value:
        raise RuntimeError(category) from None


def binding():
    path = REPO / HOST_RELATIVE
    info = path.lstat()
    need(
        stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
        "HOST_FILE",
    )
    raw = path.read_bytes()
    need(len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == HOST_SHA, "HOST_PIN")
    ns = {"__name__": "_t4_binding", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), ns)
    return ns


H = binding()
R = H["R"]
PROFILE_RELATIVE = "docs/poc/w1_bootstrap_transport_profile_v2.py"
PROFILE_SHA = "3a5bb9a3c6b38fcefb910fd498d01fc3a4fc9c04ae379d81dbc48b462f8c116a"
PROFILE, PROFILE_RAW = H["captured"](PROFILE_RELATIVE, PROFILE_SHA)
TRANSPORT_PINS = {PROFILE_RELATIVE: PROFILE_SHA, **dict(PROFILE["DEPENDENCIES"].values())}


class TransportHost(H["Host"]):
    def __init__(self, root, state):
        super().__init__(root, state)
        need(state["transport_pins"] == TRANSPORT_PINS, "CAPTURE")
        self._transport, self._transport_raw = H["captured"](PROFILE_RELATIVE, PROFILE_SHA)
        self._transport_entry_raw = R["pinned"](Path(__file__), state["entry_sha256"])
        self._transport_captures = []
        self.result.update(
            transport_profile="STDIN_ONCE_TRUE_V2", cleanup_initial_raw_captured=False
        )

    def pins(self, cleanup=False):
        super().pins(cleanup=cleanup)
        need(hashlib.sha256(PROFILE_RAW).hexdigest() == PROFILE_SHA, "CAPTURE")
        need(hashlib.sha256(self._transport_raw).hexdigest() == PROFILE_SHA, "CAPTURE")
        need(
            hashlib.sha256(self._transport_entry_raw).hexdigest() == self.state["entry_sha256"],
            "CAPTURE",
        )
        self._transport["pins"](cleanup=cleanup)
        if not cleanup:
            R["pinned"](REPO / PROFILE_RELATIVE, PROFILE_SHA)
            R["pinned"](Path(__file__), self.state["entry_sha256"])
            config_path = next(path for path in R["EXTERNAL_PINS"] if path.name == "config.json")
            config = json.loads(R["regular"](config_path, 16384))
            need(type(config) is dict and not config.get("proxies"), "CONFIG")

    async def inspect_own(self, record, cleanup=False, timeout=3):
        need(record["cid"] is not None, "CID_REQUIRED")
        code, raw = await self.cli(
            "inspect-" + record["role"],
            "inspect",
            "--type",
            "container",
            record["cid"],
            cleanup=cleanup,
            timeout=timeout,
        )
        need(code == 0, "INSPECT")
        started = time.monotonic()
        name = (
            record["role"]
            + "-transport-inspect-"
            + str(len(self._transport_captures)).zfill(2)
            + ".json"
        )
        self.write_new(name, raw, 2097152)  # LOCAL Temp before ANY parse or acceptance
        capture = {
            "role": record["role"],
            "phase": "cleanup" if cleanup else "admission",
            "raw_name": name,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "validator_completed": False,
            "validator_category": None,
        }
        self._transport_captures.append(capture)
        self.save("transport-captures.json", self._transport_captures)
        policy, intent = self.t4["policy"], self._intents[record["role"]]
        publish = self._transport["publication"](
            raw,
            policy["ENV"],
            policy["labels_for"](self.state["task"]),
            intent.command,
            policy["ENTRY"],
            cid=record["cid"],
            name=record["name"],
        )
        capture["publication"] = publish
        self.save("transport-captures.json", self._transport_captures)
        try:
            info = self._owned_inspect(record, raw, cleanup)
        except BaseException as error:
            capture.update(validator_completed=True, validator_category=category(error, self))
            self.save("transport-captures.json", self._transport_captures)
            raise
        capture.update(validator_completed=True, profile_accepted=not cleanup)
        self.save("transport-captures.json", self._transport_captures)
        need(0 <= time.monotonic() - started <= 3.0, "REPORT_FACTS")
        if not cleanup:
            need(publish["allowed"], "REPORT_SCHEMA")
        return info, raw

    def _owned_inspect(self, record, raw, cleanup):
        values = json.loads(raw)
        need(type(values) is list and len(values) == 1, "INSPECT_SHAPE")
        policy, intent = self.t4["policy"], self._intents[record["role"]]
        need(policy["identity"](values[0], intent) == record["cid"], "CID_CHANGED")
        if not cleanup:
            need(
                self._transport["validate_container"](values[0], intent, policy) == record["cid"],
                "CID_CHANGED",
            )
        return values[0]


def admit(root):
    need(
        sys.platform == "win32"
        and sys.version_info[:3] == (3, 11, 3)
        and sys.flags.isolated == 1
        and sys.flags.dont_write_bytecode == 1
        and sys.flags.optimize == 0,
        "HOST_RUNTIME",
    )
    need(
        type(root) is type(R["HOME"])
        and root.parent == R["HOME"] / "AppData/Local/Temp"
        and re.fullmatch(r"maskgw-oracle9-t4-v2-20261029-[0-9a-f]{32}", root.name),
        "ROOT",
    )
    info = root.lstat()
    need(
        stat.S_ISDIR(info.st_mode)
        and not getattr(info, "st_file_attributes", 0) & 0x400
        and {item.name for item in root.iterdir()} == {"attempt.json"},
        "FRESH_ROOT",
    )
    raw = R["regular"](root / "attempt.json", 16384)
    state = json.loads(raw)
    need(
        type(state) is dict
        and set(state)
        == {
            "kind",
            "task",
            "phase",
            "invoked",
            "program_sha256",
            "v2_sha256",
            "host_sha256",
            "entry_sha256",
            "pins",
            "t4_pins",
            "transport_pins",
            "image",
            "create_measurements",
        }
        and R["json_bytes"](state) == raw,
        "STATE_SCHEMA",
    )
    need(
        state["kind"] == "maskgw-oracle9-t4-v2"
        and state["phase"] == "FRESH"
        and state["invoked"] is False
        and type(state["task"]) is str
        and re.fullmatch(r"[0-9a-f]{32}", state["task"])
        and state["program_sha256"] == PROGRAM_SHA
        and state["v2_sha256"] == V2_SHA
        and state["host_sha256"] == HOST_SHA
        and state["pins"] == dict(R["LIBRARIES"].values())
        and state["t4_pins"] == dict(H["SOURCES"].values())
        and state["transport_pins"] == TRANSPORT_PINS
        and state["image"] == H["captured"](*H["SOURCES"]["policy"])[0]["IMAGE"],
        "STATE_VALUES",
    )
    need(
        type(state["entry_sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", state["entry_sha256"]),
        "ENTRY_PIN",
    )
    R["pinned"](Path(__file__), state["entry_sha256"])
    return state


class Context:
    def __init__(self, root, state, host):
        self.root, self.state, self.host = root, state, host
        self.released = False
        self.interrupted = False
        self.held = False


def prepare(root):
    start = time.monotonic()
    state = admit(root)
    host = TransportHost(root, state)
    host.pins()
    channel = host.t4["channel"]
    for name, digest in channel["STDLIB_PINS"].items():
        R["pinned"](channel["STDLIB"] / name, digest, 262144)
    measurements = {
        key: host.t4["policy"]["create_args"](str(R["CLI"]), intent)[1]
        for key, intent in host._intents.items()
    }
    need(measurements == state["create_measurements"], "CREATE_MEASUREMENTS")
    need(time.monotonic() - start <= 3.0, "ADMISSION_TIME")
    context = Context(root, state, host)
    host.write_new(
        "invoked.json",
        R["json_bytes"](
            {
                "kind": "MASKGW_T4_INVOKED_V2",
                "task": state["task"],
                "host_sha256": HOST_SHA,
                "entry_sha256": state["entry_sha256"],
            }
        ),
    )
    state.update(phase="INVOKED", invoked=True)
    host.save("attempt.json", state)
    return context


def category(error, host):
    return host._transport["closed_category"](error, {**host.t4, "bounded": host.libs["bounded"]})


def join_ready(host):
    if host.result.get("owned_cleanup") is not True:
        return False
    if host._foreground is not None and not host._foreground.done():
        return False
    if any(not task.done() for task in host._host_tasks if task is not host._heartbeat):
        return False
    try:
        for owner in host._owners.values():
            owner.assert_released()
    except Exception:
        return False
    acquired = host._cleanup_lock is not None and host._cleanup_lock.acquire(blocking=False)
    if acquired:
        host._cleanup_lock.release()
    return bool(acquired)


def visible(context, phase, reason):
    print(json.dumps({"phase": phase, "category": reason, "root": str(context.root)}), flush=True)


async def retain(context, reason):
    # Never stop or replace a monitor here. It may still fire its ONE emergency.
    # No second cleanup attempt; thread/Host/loop retained for explicit recovery.
    context.held = True
    context.host.result.update(outcome="NOT_PASSED", retention_category=reason)
    context.state["phase"] = "HELD"
    try:
        context.host.save("attempt.json", context.state)
        context.host.save("result.json", context.host.result)
    except BaseException:
        pass
    visible(context, "HELD", reason)
    await asyncio.Event().wait()  # retains owning loop, tasks and all resources


def restore_budget(host, *, after):
    b = host._store.read().b_started if host._store is not None else None
    if b is None:
        return
    elapsed = time.monotonic() - b
    if elapsed < 0 or elapsed >= (600.0 if after else 507.0):
        host.result["deadline_category"] = "POST_B_OVERRUN" if after else "RESTORE_MARGIN"


async def run(context):
    host = context.host
    try:
        await host.start_supervision()
        await host.foreground(host.start_cycle())
        _, head = H["V2"]["journal_from_disk"](host)
        host.result.update(journal_verified=True, journal_last_sha256=head)
        await host.perform_b()
    except BaseException as error:
        host.result["failure_category"] = category(error, host)
        if host.cycle is not None:
            try:
                host.cycle = host.libs["core"]["abort"](host.cycle)
                host.save("cycle.json", json.loads(host.libs["core"]["encode"](host.cycle)))
            except BaseException:
                host.result["abort_category"] = "ABORT_RECORD_FAILED"
    if host._foreground is not None and not host._foreground.done():
        return await retain(context, "FOREGROUND_UNPROVEN")
    try:
        await host.cleanup_owned()
    except BaseException as error:
        host.result["cleanup_category"] = category(error, host)
    if not join_ready(host):
        return await retain(context, "RESOURCE_COLLECTION_UNPROVEN")
    try:
        await host.stop_supervision()
        host.assert_released()
    except BaseException as error:
        if isinstance(error, KeyboardInterrupt):
            context.interrupted = True
        return await retain(context, "THREAD_OR_OWNER_UNPROVEN")
    # No independent watchdog now. Overrun reproves the test but MUST NOT skip
    # safe restoration, which still verifies boot/identity/empty inventory.
    restore_budget(host, after=False)
    await host.restore_desktop()
    restore_budget(host, after=True)
    try:
        host.pins()
        host.result["inputs_unchanged"] = True
    except BaseException:
        host.result["inputs_unchanged"] = False
    success = (
        all(
            host.result.get(key) is True
            for key in (
                "t4_verified",
                "owned_cleanup",
                "inventory_restored",
                "desktop_restored",
                "inputs_unchanged",
                "journal_verified",
            )
        )
        and len(host._cases) == 7
        and host.result.get("watchdog", {}).get("thread_joined") is True
        and host.result["watchdog"].get("fired") is False
        and not context.interrupted
        and not any(
            key in host.result
            for key in (
                "failure_category",
                "abort_category",
                "cleanup_category",
                "deadline_category",
            )
        )
    )
    host.result.update(
        outcome="ORACLE9_T4_V2_VERIFIED" if success else "NOT_PASSED",
        commands=host.commands,
        checkpoint_count=len(getattr(host, "_checkpoint_records", ())),
    )
    context.state["phase"] = "FINISHED" if success else "ABORTED"
    host.save("attempt.json", context.state)
    host.save("result.json", host.result)
    host.assert_released()
    context.released = True
    visible(context, context.state["phase"], host.result["outcome"])
    return 0 if success else 1


def drive(context):
    loop = asyncio.new_event_loop()
    need(type(loop) is asyncio.ProactorEventLoop, "HOST_LOOP")
    asyncio.set_event_loop(loop)
    root = loop.create_task(run(context), name="maskgw-t4-root")
    while True:
        try:
            status = loop.run_until_complete(root)
            if context.released and not any(not task.done() for task in asyncio.all_tasks(loop)):
                loop.close()
                return status
            root = loop.create_task(
                retain(context, "RETURN_WITHOUT_RELEASE"), name="maskgw-t4-held"
            )
        except BaseException:
            context.interrupted = True
            visible(context, "HELD", "RUNNER_INTERRUPTED")
            # No asyncio.run teardown, task cancellation, loop.close or dropping
            # Host. A pending root continues on this same loop after the signal.
            if root.done():
                root = loop.create_task(
                    retain(context, "RUNNER_INTERRUPTED"), name="maskgw-t4-held"
                )
            elif context.host._monitor is not None:
                loop.call_soon(context.host._abort_foreground)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(2)
    try:
        admitted = prepare(Path(sys.argv[1]))
    except BaseException:
        print('{"phase":"REFUSED","category":"ADMISSION"}', flush=True)
        raise SystemExit(1) from None
    raise SystemExit(drive(admitted))
