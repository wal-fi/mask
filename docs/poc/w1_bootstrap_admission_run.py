"""Public create/inspect admission diagnostic. Never starts a canary or consumes a seed."""

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

CORE_RELATIVE = "docs/poc/w1_bootstrap_admission_fields.py"
CORE_SHA = "9612a46b3a38ef1d96e90bf12d41975a3acde66209f88e38fdea04a95efec9e3"


def capture_core():
    return H["captured"](CORE_RELATIVE, CORE_SHA)


CORE, CORE_RAW = capture_core()


class DiagnosticHost(H["Host"]):
    def __init__(self, root, state):
        super().__init__(root, state)
        need(state["diagnostic_pins"] == {CORE_RELATIVE: CORE_SHA}, "CAPTURE")
        self._admission_fields, self._admission_raw = capture_core()
        self._diagnostic_raw = R["pinned"](Path(__file__), state["entry_sha256"])
        self._admission_captures, self._admission_reports = [], []
        self.result.update(diagnostic_only=True, cleanup_initial_raw_captured=False)

    def pins(self, cleanup=False):
        super().pins(cleanup=cleanup)
        need(hashlib.sha256(self._admission_raw).hexdigest() == CORE_SHA, "CAPTURE")
        need(hashlib.sha256(CORE_RAW).hexdigest() == CORE_SHA, "CAPTURE")
        need(
            hashlib.sha256(self._diagnostic_raw).hexdigest() == self.state["entry_sha256"],
            "CAPTURE",
        )
        if not cleanup:
            R["pinned"](REPO / CORE_RELATIVE, CORE_SHA)
            R["pinned"](Path(__file__), self.state["entry_sha256"])
            config_path = next(path for path in R["EXTERNAL_PINS"] if path.name == "config.json")
            config = json.loads(R["regular"](config_path, 16384))
            need(type(config) is dict and not config.get("proxies"), "CONFIG")

    async def _case(self, *_args):
        raise RuntimeError("DIAGNOSTIC_NO_TRANSPORT") from None

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
        capture_started = time.monotonic()
        name = (
            record["role"]
            + "-admission-inspect-"
            + str(len(self._admission_captures)).zfill(2)
            + ".json"
        )
        self.write_new(name, raw, 2097152)  # LOCAL Temp only, before ANY parse/validation
        manifest = {
            "role": record["role"],
            "phase": "cleanup" if cleanup else "admission",
            "raw_name": name,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        self._admission_captures.append(manifest)
        self.save("admission-captures.json", self._admission_captures)
        policy = self.t4["policy"]
        intent = self._intents[record["role"]]
        publish = self._admission_fields["publication"](
            raw,
            policy["ENV"],
            policy["labels_for"](self.state["task"]),
            intent.command,
            policy["ENTRY"],
            cid=record["cid"],
            name=record["name"],
        )
        manifest["publication"] = publish
        self.save("admission-captures.json", self._admission_captures)
        info = self._owned_inspect(record, raw, True)  # OWNERSHIP only, not acceptance
        if cleanup:
            need(0 <= time.monotonic() - capture_started <= 3.0, "REPORT_FACTS")
            return info, raw
        report = self._admission_fields["fields"](
            info, record["role"], policy["labels_for"](self.state["task"]), policy["ENV"]
        )
        report.update(
            profile_accepted=False,
            validator_category=None,
            validator_completed=False,
            predicate_agreement=None,
            raw_name=name,
            raw_sha256=manifest["sha256"],
            raw_bytes=len(raw),
            publication=publish,
        )
        report_name = record["role"] + "-admission-report.json"
        self.write_new(report_name, R["json_bytes"](report))
        accepted, error_code = False, None
        try:
            policy["validate_container"](info, intent)
            accepted = True
        except Exception as error:
            error_code = self._admission_fields["closed_category"](error)
        report.update(
            profile_accepted=accepted and report["profile_predicates_match"],
            validator_category=error_code,
            validator_completed=True,
            predicate_agreement=accepted is report["profile_predicates_match"],
        )
        self.save(report_name, report)
        # Preserve the closed category itself, never remap INTERNAL to SOURCE_PIN.
        if error_code is not None and error_code not in (
            "CONFIG",
            "PROFILE",
            "ISOLATION",
            "SURFACE",
        ):
            raise RuntimeError(error_code) from None
        need(report["predicate_agreement"], "REPORT_FACTS")
        self._admission_reports.append(report)
        self.save("admission-reports.json", self._admission_reports)
        need(0 <= time.monotonic() - capture_started <= 3.0, "REPORT_FACTS")
        return info, raw  # ONLY for capture-only caller; never a transport admission

    async def perform_b(self):
        need(self.cycle.phase is self.libs["core"]["Phase"].B_CONSUMED, "B_REQUIRED")
        need(not self._owners, "HOST_HELD")
        async with asyncio.timeout(80.0):
            for case in (self.t4["policy"]["Case"].NORMAL, self.t4["policy"]["Case"].RETAIN):
                self.pins()
                async with asyncio.timeout(36.0):
                    await self.foreground(self._capture_profile(case))
        self.result["admission_capture_complete"] = len(self._admission_reports) == 2 and all(
            report["state_created"] for report in self._admission_reports
        )

    async def _capture_profile(self, case):
        record = await self.create_own(case)  # inherited second raw copy + exact created/Pid0
        await self._collect(record)
        self._store.publish(None)
        if not self._admission_reports[-1]["publication"]["allowed"]:
            self.result["privacy_review_required"] = True
            raise RuntimeError("REPORT_SCHEMA") from None  # stop before another create


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
        and re.fullmatch(r"maskgw-oracle9-admission-20261028-[0-9a-f]{32}", root.name),
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
            "diagnostic_pins",
            "image",
            "create_measurements",
        }
        and R["json_bytes"](state) == raw,
        "STATE_SCHEMA",
    )
    need(
        state["kind"] == "maskgw-oracle9-admission-v1"
        and state["phase"] == "FRESH"
        and state["invoked"] is False
        and type(state["task"]) is str
        and re.fullmatch(r"[0-9a-f]{32}", state["task"])
        and state["program_sha256"] == PROGRAM_SHA
        and state["v2_sha256"] == V2_SHA
        and state["host_sha256"] == HOST_SHA
        and state["pins"] == dict(R["LIBRARIES"].values())
        and state["t4_pins"] == dict(H["SOURCES"].values())
        and state["diagnostic_pins"] == {CORE_RELATIVE: CORE_SHA}
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
    host = DiagnosticHost(root, state)
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
                "kind": "MASKGW_ADMISSION_INVOKED_V1",
                "task": state["task"],
                "host_sha256": HOST_SHA,
                "entry_sha256": state["entry_sha256"],
            }
        ),
    )
    state.update(phase="INVOKED", invoked=True)
    host.save("attempt.json", state)
    return context


def category(error):
    if isinstance(error, asyncio.CancelledError):
        return "CANCELLED"
    if isinstance(error, TimeoutError):
        return "DEADLINE"
    return CORE["closed_category"](error)


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
        host.result["failure_category"] = category(error)
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
        host.result["cleanup_category"] = category(error)
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
                "admission_capture_complete",
                "owned_cleanup",
                "inventory_restored",
                "desktop_restored",
                "inputs_unchanged",
                "journal_verified",
            )
        )
        and len(host._admission_reports) == 2
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
        outcome="ORACLE9_ADMISSION_CAPTURED" if success else "NOT_PASSED",
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
