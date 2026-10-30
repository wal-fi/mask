"""Single public PG16 attempt. Import defines only; never invokes historical mains."""

import asyncio
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
import time

REPO = Path(__file__).resolve().parents[2]
HOST_RELATIVE = "docs/poc/pg16_public_host.py"
HOST_SHA = "7275c8ae9e7ccbadc6591cdbb051482ac76c3f3bb52a4f4b86f2966b2261c19e"
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
    ns = {"__name__": "_pg16_public_binding", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), ns)
    return ns


H = binding()
R = H["R"]


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
        and re.fullmatch(r"maskgw-pg16-public-20261030-[0-9a-f]{32}", root.name),
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
            "pg_pins",
            "image",
            "create_measurement",
        }
        and R["json_bytes"](state) == raw,
        "STATE_SCHEMA",
    )
    need(
        state["kind"] == "maskgw-pg16-public-v1"
        and state["phase"] == "FRESH"
        and state["invoked"] is False
        and type(state["task"]) is str
        and re.fullmatch(r"[0-9a-f]{32}", state["task"])
        and state["program_sha256"] == PROGRAM_SHA
        and state["v2_sha256"] == V2_SHA
        and state["host_sha256"] == HOST_SHA
        and state["pins"] == dict(R["LIBRARIES"].values())
        and state["pg_pins"] == dict(H["SOURCES"].values())
        and state["image"] == H["captured"](*H["SOURCES"]["profile"])[0]["IMAGE"],
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
    host = H["Host"](root, state)
    host.pins()
    channel = host.channel
    for name, digest in channel["STDLIB_PINS"].items():
        R["pinned"](channel["STDLIB"] / name, digest, 262144)
    need(host._blueprint[1] == state["create_measurement"], "CREATE_MEASUREMENT")
    need(time.monotonic() - start <= 3.0, "ADMISSION_TIME")
    context = Context(root, state, host)
    host.write_new(
        "invoked.json",
        R["json_bytes"](
            {
                "kind": "MASKGW_PG16_PUBLIC_INVOKED_V1",
                "task": state["task"],
                "host_sha256": HOST_SHA,
                "entry_sha256": state["entry_sha256"],
            }
        ),
    )
    state.update(phase="INVOKED", invoked=True)
    host.save("attempt.json", state)
    return context


RUNTIME_CODES = frozenset(
    (
        "ABSENCE",
        "ADMISSION_TIME",
        "APP_CREATED",
        "APP_DISAPPEARED",
        "APP_DUPLICATE",
        "APP_EXIT",
        "APP_IDENTITY",
        "APP_NAME",
        "APP_PID",
        "APP_SHAPE",
        "ATTEST_BASE",
        "ATTEST_COLLISION",
        "ATTEST_COPY",
        "ATTEST_COPY_EXIT",
        "ATTEST_ORIGIN",
        "ATTEST_RESULT",
        "ATTEST_SIZE",
        "BASE_CONFIG_EXACT",
        "BASE_IMAGE",
        "BASE_SHAPE",
        "B_REQUIRED",
        "CANDIDATE_EXIT",
        "CANDIDATE_ID",
        "CAPTURE",
        "CAPTURE_PIN",
        "CID",
        "CID_REQUIRED",
        "CLEANUP_DEADLINE",
        "CLEANUP_LOCK",
        "CLEANUP_RUNNING",
        "CLEANUP_UNPROVEN",
        "CLI_IDENTITY_CHANGED",
        "CLOCK_KIND",
        "COMMAND",
        "COMMAND_MEASUREMENT",
        "COMMIT_EXIT",
        "COMMIT_OWNER",
        "COMMIT_PUBLIC_LABEL",
        "COMMIT_RUNNING",
        "COMMIT_SHAPE",
        "CONFIG",
        "CONTAINER_LABELS_EXACT",
        "COPY_INPUTS",
        "CREATE_BLUEPRINT",
        "CREATE_EXIT",
        "CREATE_MEASUREMENT",
        "CREATE_NOT_ADMITTED",
        "CREATE_RUNNING",
        "CYCLE_REFUSED",
        "DAEMON",
        "DAEMON_EXIT",
        "DAEMON_PROFILE",
        "DIAGNOSTIC_FIELD",
        "DIFF_EXIT",
        "ENDPOINT",
        "ENTRY_PIN",
        "EVIDENCE_SIZE",
        "EXIT",
        "FILE_CHANGED",
        "FILE_SIZE",
        "FOREGROUND_BUSY",
        "FRESH_ROOT",
        "HOST_CAPTURE",
        "HOST_FILE",
        "HOST_HELD",
        "HOST_LOOP",
        "HOST_PIN",
        "HOST_ROOT",
        "HOST_RUNTIME",
        "IMAGE",
        "IMAGE_ENV",
        "IMAGE_LABELS",
        "INITIAL_UNKNOWN",
        "INNER_PIN",
        "INPUTS_REMAIN",
        "INSPECT",
        "INTENT",
        "INTENT_EXIT",
        "INVENTORY",
        "JOURNAL_ACTION",
        "JOURNAL_ADMISSION",
        "JOURNAL_BINDING",
        "JOURNAL_CHAIN",
        "JOURNAL_COUNT",
        "JOURNAL_FILES",
        "JOURNAL_INCOMPLETE",
        "JOURNAL_SAMPLE",
        "JOURNAL_SCHEMA",
        "JOURNAL_SIZE",
        "JOURNAL_START",
        "JOURNAL_STATE",
        "JOURNAL_TRANSITION",
        "JSON",
        "KILL",
        "KILL_EXIT",
        "MEASURED_COMMAND_CHANGED",
        "MOUNTS",
        "NOT_FRESH",
        "ORIGINAL_PIN",
        "ORIGINAL_TYPE",
        "OS",
        "OWNERSHIP",
        "OWNER_HELD",
        "OWN_COMMAND",
        "OWN_ID_CHANGED",
        "OWN_INSPECT",
        "OWN_SHAPE",
        "PG16_PUBLIC_CLI_SCOPE",
        "PG16_PUBLIC_INSTALL_FORBIDDEN",
        "PG16_PUBLIC_OLD_TRANSPORT_FORBIDDEN",
        "PG16_PUBLIC_OLD_WATCHDOG_FORBIDDEN",
        "PG16_PUBLIC_OWNERSHIP",
        "PG16_PUBLIC_SOURCE",
        "PG16_PUBLIC_WATCHDOG_REFUSED",
        "PIN",
        "PREFLIGHT_REUSED",
        "PROBE_DIFF",
        "PROBE_RESULT",
        "PROBE_STATE",
        "PROFILE",
        "REGULAR",
        "REMOVE",
        "REMOVE_EXIT",
        "REMOVE_UNPROVEN",
        "REPORT",
        "RESTORE_BOOT",
        "RESTORE_UNPROVEN",
        "ROOT",
        "ROOT_TYPE",
        "RUNNING",
        "RUN_EXIT",
        "SOURCE",
        "SOURCE_PIN",
        "START_ENV",
        "START_IDENTITY",
        "START_SHAPE",
        "START_UNPROVEN",
        "STATE",
        "STATE_PINS",
        "STATE_SCHEMA",
        "STATE_SHAPE",
        "STATE_VALUES",
        "STOP_EXIT",
        "STOP_UNPROVEN",
        "SUPERVISION_REQUIRED",
        "SURFACE",
        "TAG_CHANGED",
        "TAG_EXISTS",
        "TAG_ID",
        "TAG_INSPECT",
        "TAG_LABELS",
        "TAG_LAYERS",
        "TAG_REMAINS",
        "TAG_REMOVE",
        "TAG_RESOLVE",
        "TAG_SHAPE",
        "TASK",
        "TASK_START",
        "TOOLS",
        "UID",
        "V2_CAPTURE",
        "VERSION",
        "VOLUME_BASELINE_CHANGED",
        "VOLUME_BASELINE_REQUIRED",
        "VOLUME_BASELINE_STALE",
        "VOLUME_INVENTORY_CHANGED",
        "VOLUME_INVENTORY_EXIT",
        "VOLUME_OWNERSHIP_UNPROVEN",
        "W1_IMPORTS",
        "WAIT_CLOCK",
        "WATCHDOG",
        "WATCHDOG_CLEANUP",
        "WATCHDOG_FIRED",
        "WATCHDOG_ID",
        "WATCHDOG_INSPECT",
        "WATCHDOG_KILL",
        "WATCHDOG_PREVIOUS",
        "WATCHDOG_SHAPE",
        "WATCHDOG_START",
    )
)
PROBE_CODES = frozenset(
    (
        "CID",
        "COMMAND",
        "CONFIG",
        "EXIT",
        "IMAGE",
        "IMAGE_ENV",
        "IMAGE_LABELS",
        "INTENT",
        "JSON",
        "MOUNTS",
        "OS",
        "OWNERSHIP",
        "PROFILE",
        "REPORT",
        "SURFACE",
        "TASK",
        "TOOLS",
        "UID",
        "VERSION",
    )
)
VALUE_CODES = frozenset(
    (
        "CLOCK_REFUSED",
        "CYCLE_SCHEMA",
    )
)
BOUNDED_CODES = frozenset(
    (
        "ARTIFACT_LIMIT",
        "CAPABILITIES",
        "CLEANUP_UNCONFIRMED",
        "CLI_CLEANUP",
        "COMMAND",
        "CONTAINER_EXIT",
        "CONTAINER_STILL_LIVE",
        "CREATE",
        "CREATION_UNCERTAIN",
        "DEADLINE",
        "ENGINE_UNAVAILABLE",
        "ENTRYPOINT",
        "EXTERNAL_ACCESS",
        "IDENTITY",
        "IMAGE_NOT_PINNED",
        "IMAGE_PROFILE",
        "INSPECT",
        "INSPECT_SCHEMA",
        "LIMIT_CONFIGURATION",
        "LOG_OR_USER",
        "LOT_DEADLINE",
        "MOUNTS",
        "NAMESPACE",
        "OUTPUT_LIMIT",
        "PRIVILEGE",
        "PROCESS_CONFIGURATION",
        "REMOVE_FAILED",
        "REMOVE_UNCONFIRMED",
        "REPORT_CLAIM",
        "REPORT_SCHEMA",
        "SOURCE_CHANGED",
        "SOURCE_LIMIT",
        "ULIMITS",
        "WATCHDOG_CLEANUP",
    )
)
EMERGENCY_CODES = frozenset(
    (
        "BUDGET",
        "COMMAND",
        "INPUT",
        "PIN",
    )
)


def _child_bounded_type(error, host):
    """Recognize fresh helper classes held by the EXACT pinned parent frames.

    invoke/public-PS and clock/sample compile separate pinned bounded namespaces.
    Their classes differ from libs[bounded]; filenames/module names are NOT proof.
    Only those two captured caller code objects and their actual helper class count.
    """
    # Anchor to THIS Host's captured base namespace, not another import of the same bytes.
    base = type(host).__init__.__globals__["R"]["Host"]
    callers = (base.invoke, host.libs["clock"]["sample"])
    try:
        trace = BaseException.__traceback__.__get__(error)
    except TypeError:
        return False
    steps = 0
    while trace is not None and steps < 64:
        frame = trace.tb_frame
        for caller in callers:
            if frame.f_code is not caller.__code__ or frame.f_globals is not caller.__globals__:
                continue
            if caller is callers[0] and frame.f_locals.get("self") is not host:
                continue
            helper = frame.f_locals.get("helper")
            if type(helper) is dict and type(error) is helper.get("HostFault"):
                return True
        trace, steps = trace.tb_next, steps + 1
    return False


def diagnostic(error, host):
    kind = type(error)
    for control, code in (
        (asyncio.CancelledError, "CANCELLED"),
        (TimeoutError, "DEADLINE"),
        (KeyboardInterrupt, "INTERRUPTED"),
    ):
        if kind is control:
            return code, "CONTROL"
    bounded = kind is host.libs["bounded"]["HostFault"] or _child_bounded_type(error, host)
    known = (
        host.channel["BootstrapError"],
        host.profile["ProbeError"],
        host.pg["volumes"]["VolumeFault"],
        host.pg["identity"]["IdentityError"],
        host.pg["emergency"]["EmergencyError"],
        RuntimeError,
        ValueError,
    )
    if not bounded and not any(kind is item for item in known):
        return "INTERNAL", "INTERNAL"
    args = BaseException.args.__get__(error)
    literal = args[0] if len(args) == 1 and type(args[0]) is str else None
    if kind is host.channel["BootstrapError"]:
        value = getattr(error, "category", None)
        if type(value) is host.channel["Fault"] and args == (value.value,):
            return value.value, "BOOTSTRAP"
    elif kind is host.profile["ProbeError"]:
        if literal in PROBE_CODES:
            return literal, "PROBE"
    elif kind is host.pg["volumes"]["VolumeFault"]:
        if literal == "VOLUME_INVENTORY":
            return literal, "VOLUME"
    elif kind is host.pg["identity"]["IdentityError"]:
        if literal == "IDENTITY_UNKNOWN":
            return literal, "IDENTITY"
    elif kind is host.pg["emergency"]["EmergencyError"]:
        if literal in EMERGENCY_CODES:
            return literal, "EMERGENCY"
    elif kind is RuntimeError:
        if literal in RUNTIME_CODES:
            return literal, "RUNTIME"
    elif kind is ValueError:
        if literal in VALUE_CODES:
            return literal, "VALUE"
    elif bounded:
        value = getattr(error, "category", None)
        if type(value) is str and value in BOUNDED_CODES and args == (value,):
            return value, "HOST_FAULT"
    return "INTERNAL", "INTERNAL"


def record_error(host, phase, error):
    need(phase in ("failure", "cleanup", "restore"), "DIAGNOSTIC_FIELD")
    code, origin = diagnostic(error, host)
    host.result.update({phase + "_category": code, phase + "_origin": origin})


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
        record_error(host, "failure", error)
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
        record_error(host, "cleanup", error)
    if not join_ready(host):
        return await retain(context, "RESOURCE_COLLECTION_UNPROVEN")
    try:
        await host.stop_supervision()
        host.assert_released()
    except BaseException as error:
        if type(error) is KeyboardInterrupt:
            context.interrupted = True
        return await retain(context, "THREAD_OR_OWNER_UNPROVEN")
    # No independent watchdog now. Overrun reproves the test but MUST NOT skip
    # safe restoration, which still verifies boot/identity/empty inventory.
    restore_budget(host, after=False)
    try:
        await host.restore_desktop()
    except BaseException as error:
        if type(error) is KeyboardInterrupt:
            context.interrupted = True
        host.result["desktop_restored"] = False
        record_error(host, "restore", error)
        return await retain(context, "DESKTOP_RESTORE_UNPROVEN")
    if host.result.get("desktop_restored") is not True:
        return await retain(context, "DESKTOP_RESTORE_UNPROVEN")
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
                "pg16_public_verified",
                "owned_cleanup",
                "inventory_restored",
                "volumes_restored",
                "desktop_restored",
                "inputs_unchanged",
                "journal_verified",
            )
        )
        and len(host._cases) == 1
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
        outcome="PG16_PUBLIC_VERIFIED" if success else "NOT_PASSED",
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
    root = loop.create_task(run(context), name="maskgw-pg16-public-root")
    while True:
        try:
            status = loop.run_until_complete(root)
            if context.released and not any(not task.done() for task in asyncio.all_tasks(loop)):
                loop.close()
                return status
            root = loop.create_task(
                retain(context, "RETURN_WITHOUT_RELEASE"), name="maskgw-pg16-public-held"
            )
        except BaseException:
            context.interrupted = True
            visible(context, "HELD", "RUNNER_INTERRUPTED")
            # No asyncio.run teardown, task cancellation, loop.close or dropping
            # Host. A pending root continues on this same loop after the signal.
            if root.done():
                root = loop.create_task(
                    retain(context, "RUNNER_INTERRUPTED"), name="maskgw-pg16-public-held"
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
