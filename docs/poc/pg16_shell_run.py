"""Single closed public reader attempt. Import defines only; no native effects."""

import ast
import asyncio
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
import time

REPO = Path(__file__).resolve().parents[2]
HOST_RELATIVE = "docs/poc/pg16_shell_host.py"
HOST_SHA = "8c41605f5f44f355632b05167c6348fb09752472b6d59b26961604023a613018"
TRANSITIVE_PINS = {
    "docs/poc/pg16_shell_owner.py": "d671880078d6d1f30067400ae3d3169e17458c471467027835ba2be6897b6c8f",
    "docs/poc/pg16_shell_reader.py": "efe69a79a0743e49de602067d624c075cf5af8321a2654b7c2e87d023f498a85",
    "docs/poc/w1_bootstrap_channel.py": "e6ca9e606567289fa312049b071aa777e1764579813829747cb32df05d4ee87a",
    "docs/poc/pg16_public_profile.py": "fe2f8ba8bfabc5572fe7aeb85c31c54de38ceaa23c1a6c34dd631425371d9277",
}
IMAGE = "sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685"
STATE_LIMIT = 32768
ADMISSION_SECONDS = 3.0


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
    need(
        len(raw) == info.st_size
        and len(raw) <= 65536
        and hashlib.sha256(raw).hexdigest() == HOST_SHA,
        "HOST_PIN",
    )
    ns = {"__name__": "_pg16_shell_host_binding", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), ns)
    return ns, raw


H, HOST_RAW = binding()
R = H["R"]
C, CHANNEL_RAW = H["P"]["captured"](
    "docs/poc/w1_bootstrap_channel.py", TRANSITIVE_PINS["docs/poc/w1_bootstrap_channel.py"]
)


def runtime_literals(raw):
    """Closed vocabulary from pinned source, never from runtime messages."""
    values = set()
    for node in ast.walk(ast.parse(raw)):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in (
            "need",
            "RuntimeError",
            "ValueError",
        ):
            index = 1 if node.func.id == "need" else 0
            if len(node.args) > index:
                item = node.args[index]
                if (
                    isinstance(item, ast.Constant)
                    and type(item.value) is str
                    and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", item.value)
                ):
                    values.add(item.value)
    return frozenset(values)


def vocabulary(host):
    raw = (
        HOST_RAW,
        H["PARENT_RAW"],
        host._original_raw,
        *host.captured.values(),
        *host.pg_raw.values(),
    )
    result = frozenset().union(*(runtime_literals(value) for value in raw))
    return result | frozenset(
        (
            "CYCLE_SCHEMA",
            "SOURCE_PIN",
            "CAPTURE_PIN",
            "ENTRY_PIN",
            "FINAL_PINS",
            "TERMINAL_PERSISTENCE",
        )
    )


def _directory(path):
    info = path.lstat()
    need(
        stat.S_ISDIR(info.st_mode)
        and not getattr(info, "st_file_attributes", 0) & 0x400
        and not path.is_symlink(),
        "ROOT_DIRECTORY",
    )


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
        and root.is_absolute()
        and root.parent == R["HOME"] / "AppData/Local/Temp"
        and re.fullmatch(r"maskgw-pg16-shell-reader-v1-[0-9a-f]{32}", root.name),
        "ROOT",
    )
    for path in (root, *root.parents):
        _directory(path)
    need({path.name for path in root.iterdir()} == {"attempt.json"}, "FRESH_ROOT")
    raw = R["regular"](root / "attempt.json", STATE_LIMIT)
    state = json.loads(raw)
    keys = {
        "kind",
        "task",
        "phase",
        "invoked",
        "program_sha256",
        "v2_sha256",
        "parent_sha256",
        "host_sha256",
        "entry_sha256",
        "pins",
        "pg_pins",
        "transitive_pins",
        "stdlib_pins",
        "image",
        "create_measurements",
        "delivery_plan",
    }
    need(
        type(state) is dict and set(state) == keys and R["json_bytes"](state) == raw, "STATE_SCHEMA"
    )
    need(
        state["kind"] == "maskgw-pg16-shell-reader-v1"
        and state["phase"] == "FRESH"
        and state["invoked"] is False
        and type(state["task"]) is str
        and re.fullmatch(r"[0-9a-f]{32}", state["task"])
        and state["program_sha256"] == H["V2"]["ORIGINAL_SHA"]
        and state["v2_sha256"] == H["P"]["V2_SHA"]
        and state["parent_sha256"] == H["PARENT_SHA"]
        and state["host_sha256"] == HOST_SHA
        and state["image"] == IMAGE,
        "STATE_VALUES",
    )
    expected = {
        "pins": dict(R["LIBRARIES"].values()),
        "pg_pins": dict(H["SOURCES"].values()),
        "transitive_pins": TRANSITIVE_PINS,
        "stdlib_pins": C["STDLIB_PINS"],
    }
    need(
        all(
            R["json_bytes"](state[key]) == R["json_bytes"](value) for key, value in expected.items()
        ),
        "STATE_PINS",
    )
    need(
        type(state["entry_sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", state["entry_sha256"]),
        "ENTRY_PIN",
    )
    R["pinned"](Path(__file__), state["entry_sha256"])
    return state


def transitive_captures(host):
    rows = [("docs/poc/w1_bootstrap_channel.py", CHANNEL_RAW)]

    def owner(namespace, raw):
        rows.extend(
            (
                ("docs/poc/pg16_shell_owner.py", raw),
                ("docs/poc/w1_bootstrap_channel.py", namespace["CHANNEL_RAW"]),
                ("docs/poc/pg16_shell_reader.py", namespace["READER_RAW"]),
            )
        )

    def profile(namespace, raw=None):
        if raw is not None:
            rows.append((H["SOURCES"]["profile"][0], raw))
        rows.append(("docs/poc/pg16_public_profile.py", namespace["PROFILE_RAW"]))
        owner(namespace["O"], namespace["OWNER_RAW"])

    delivery = host.pg["delivery"]
    owner(delivery["O"], delivery["OWNER_RAW"])
    profile(host.profile)
    policy = host.pg["policy"]
    profile(policy["P"], policy["PROFILE_RAW"])
    for monitor in host._monitors.values():
        policy = monitor._policy
        profile(policy["P"], policy["PROFILE_RAW"])
    return tuple(rows)


def final_pins(context):
    host = context.host
    host.pins()  # pure source proof, including live parent/V2/original/external pins
    need(hashlib.sha256(HOST_RAW).hexdigest() == HOST_SHA, "HOST_CAPTURE")
    for relative, raw in transitive_captures(host):
        expected = TRANSITIVE_PINS.get(relative, dict(H["SOURCES"].values()).get(relative))
        need(
            type(raw) is bytes
            and expected is not None
            and hashlib.sha256(raw).hexdigest() == expected,
            "TRANSITIVE_CAPTURE",
        )
        R["pinned"](REPO / relative, expected)
    for relative, digest in TRANSITIVE_PINS.items():
        R["pinned"](REPO / relative, digest)
    for name, digest in C["STDLIB_PINS"].items():
        R["pinned"](C["STDLIB"] / name, digest, 262144)
    R["pinned"](Path(__file__), context.state["entry_sha256"])


class Context:
    def __init__(self, root, state, host):
        self.root, self.state, self.host = root, state, host
        self.released = self.interrupted = self.held = self.a_entered = False
        self.history = []
        self.runtime_codes = vocabulary(host)
        self.cleanup_attempts = 0


def prepare(root):
    opened = time.monotonic()
    state = admit(root)
    host = H["Host"](root, state)
    context = Context(root, state, host)
    final_pins(context)
    need(0 <= time.monotonic() - opened <= ADMISSION_SECONDS, "ADMISSION_TIME")
    host.write_new(
        "invoked.json",
        R["json_bytes"](
            {
                "kind": "MASKGW_PG16_SHELL_INVOKED_V1",
                "task": state["task"],
                "host_sha256": HOST_SHA,
                "entry_sha256": state["entry_sha256"],
            }
        ),
    )
    state.update(phase="INVOKED", invoked=True)
    host.save("attempt.json", state)
    return context


def child_bounded_type(error, host):
    callers = (H["Host"]._bounded, host.libs["clock"]["sample"])
    trace = BaseException.__traceback__.__get__(error)
    for _ in range(64):
        if trace is None:
            return False
        frame = trace.tb_frame
        for caller in callers:
            if frame.f_code is not caller.__code__ or frame.f_globals is not caller.__globals__:
                continue
            if caller is callers[0] and frame.f_locals.get("self") is not host:
                continue
            helper = frame.f_locals.get("helper")
            if type(helper) is dict and type(error) is helper.get("HostFault"):
                return True
        trace = trace.tb_next
    return False


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


def diagnostic(error, context):
    host, kind = context.host, type(error)
    for control, code in (
        (asyncio.CancelledError, "CANCELLED"),
        (TimeoutError, "DEADLINE"),
        (KeyboardInterrupt, "INTERRUPTED"),
    ):
        if kind is control:
            return code, "CONTROL"
    args = BaseException.args.__get__(error)
    literal = args[0] if len(args) == 1 and type(args[0]) is str else None
    for namespace, error_name, enum_name, origin in (
        (host.channel, "BootstrapError", "Fault", "BOOTSTRAP"),
        (host.reader, "ReaderError", "Code", "READER"),
        (host.pg["delivery"]["R"], "ReaderError", "Code", "READER"),
    ):
        if kind is namespace[error_name]:
            category = error.category
            if type(category) is namespace[enum_name] and args == (category.value,):
                return category.value, origin
            return "INTERNAL", "INTERNAL"
    if kind is RuntimeError and literal in context.runtime_codes:
        return literal, "RUNTIME"
    if kind is ValueError and literal == "CYCLE_SCHEMA":
        return literal, "VALUE"
    if kind is host.profile["ProbeError"] and literal in (
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
    ):
        return literal, "PROFILE"
    for namespace, name, values, origin in (
        (host.pg["volumes"], "VolumeFault", ("VOLUME_INVENTORY",), "VOLUME"),
        (host.pg["identity"], "IdentityError", ("IDENTITY_UNKNOWN",), "IDENTITY"),
        (
            host.pg["emergency"],
            "EmergencyError",
            ("BUDGET", "COMMAND", "INPUT", "PIN"),
            "EMERGENCY",
        ),
    ):
        if kind is namespace[name] and literal in values:
            return literal, origin
    if kind is host.libs["bounded"]["HostFault"] or child_bounded_type(error, host):
        category = error.category
        if type(category) is str and category in BOUNDED_CODES and args == (category,):
            return category, "HOST_FAULT"
    return "INTERNAL", "INTERNAL"


def record_error(context, phase, error):
    need(
        phase in ("failure", "cleanup", "stop", "restore", "pins", "persist", "deadline"),
        "DIAGNOSTIC_PHASE",
    )
    code, origin = diagnostic(error, context)
    context.history.append({"phase": phase, "category": code, "origin": origin})
    context.host.result["error_history"] = list(context.history)
    if type(error) is KeyboardInterrupt:
        context.interrupted = True


def foreground_collected(host):
    return host._foreground is None or host._foreground.done()


def physical_ready(host):
    try:
        if (
            not foreground_collected(host)
            or not host._all_joined()
            or any(not task.done() for task in host._host_tasks)
        ):
            return False
        if any(row.get("exit") is None for row in host.commands):
            return False
        for owner in host._owners.values():
            owner.assert_released()
        acquired = host._cleanup_lock.acquire(blocking=False)
        if acquired:
            host._cleanup_lock.release()
        return bool(acquired)
    except Exception:
        return False


def visible(phase, code):
    print(json.dumps({"phase": phase, "category": code}), flush=True)


def terminal_ready(host):
    if not physical_ready(host):
        return False
    try:
        current = asyncio.current_task()
        return current is not None and all(
            task is current or task.done() for task in asyncio.all_tasks()
        )
    except Exception:
        return False


async def retain(context, category):
    context.released = False
    context.held = True
    context.host.result.update(outcome="NOT_PASSED", retention_category=category)
    context.state["phase"] = "HELD"
    try:
        context.host.save("attempt.json", context.state)
        context.host.save("result.json", context.host.result)
    except BaseException:
        pass
    visible("HELD", category)
    await asyncio.Event().wait()  # same owning loop; no duplicate cleanup/writer


async def stop(context):
    try:
        await context.host.stop_supervision()
    except BaseException as error:
        record_error(context, "stop", error)


async def collect(context):
    context.cleanup_attempts += 1
    need(context.cleanup_attempts <= 2, "CLEANUP_ATTEMPTS")
    try:
        await context.host.cleanup_owned()
    except BaseException as error:
        record_error(context, "cleanup", error)
    if context.host.result.get("owned_cleanup") is not True:
        # A record's category is deliberately not exposed by the host.
        record_error(context, "cleanup", RuntimeError("HOST_HELD"))


async def await_emergency(context):
    host = context.host
    monitor = host._monitors.get(host._active_case)
    if monitor is None:
        return False
    if host._b_started is not None and not (0 <= time.monotonic() - host._b_started < 655.0):
        return False
    if not monitor.fired.is_set():
        if host._b_started is None:
            return False
        end = host._b_started + 600.0
        while not monitor.fired.is_set() and time.monotonic() < end:
            await asyncio.sleep(min(0.25, max(0.0, end - time.monotonic())))
        if not monitor.fired.is_set():
            return False
    # No own cleanup while the emergency has the mutex. close performs its
    # fixed join, and only a physical positive permits the one later retry.
    await stop(context)
    if host._b_started is not None and not (0 <= time.monotonic() - host._b_started < 655.0):
        return False
    try:
        return host._all_joined() and monitor.metadata().get("thread_joined") is True
    except Exception:
        return False


def restore_budget(context, after):
    start = context.host._b_started
    if start is not None:
        elapsed = time.monotonic() - start
        if elapsed < 0 or elapsed >= (600.0 if after else 507.0):
            code = "POST_B_OVERRUN" if after else "RESTORE_MARGIN"
            context.history.append({"phase": "deadline", "category": code, "origin": "CONTROL"})
            context.host.result["error_history"] = list(context.history)


def success(context):
    host = context.host
    if context.history or context.interrupted or host._supervision_errors:
        return False
    if not all(
        host.result.get(key) is True
        for key in (
            "pg16_reader_verified",
            "owned_cleanup",
            "inventory_restored",
            "volumes_restored",
            "desktop_restored",
            "inputs_unchanged",
            "journal_verified",
            "terminal_resources_verified",
        )
    ):
        return False
    if tuple(row.get("case") for row in host._cases) != H["CASES"]:
        return False
    watchdogs = host.result.get("watchdogs", {})
    if set(watchdogs) != set(H["CASES"]) or len(host._monitor_attempted) != 23:
        return False
    return all(
        row.get("status") == "JOINED"
        and row.get("metadata", {}).get("thread_joined") is True
        and row["metadata"].get("fired") is False
        and row["metadata"].get("held") is False
        and row.get("errors") == []
        for row in watchdogs.values()
    )


async def finish(context):
    host = context.host
    if not foreground_collected(host):
        return await retain(context, "FOREGROUND_UNPROVEN")
    if not context.a_entered:
        await stop(context)
        if host.commands or host.records or not physical_ready(host):
            return await retain(context, "PRE_A_UNPROVEN")
        host.result.update(desktop_restored=True, desktop_state="UNTOUCHED_PRE_A")
    else:
        await collect(context)
        if host.result.get("owned_cleanup") is not True:
            if not await await_emergency(context):
                return await retain(context, "RESOURCE_COLLECTION_UNPROVEN")
            await collect(context)
            if host.result.get("owned_cleanup") is not True:
                return await retain(context, "RESOURCE_COLLECTION_UNPROVEN")
        await stop(context)
        if not physical_ready(host):
            return await retain(context, "THREAD_OR_OWNER_UNPROVEN")
        restore_budget(context, False)
        try:
            await host.restore_desktop()
        except BaseException as error:
            record_error(context, "restore", error)
        if host.result.get("desktop_restored") is not True:
            return await retain(context, "DESKTOP_RESTORE_UNPROVEN")
        restore_budget(context, True)
    try:
        final_pins(context)
        host.result["inputs_unchanged"] = True
    except BaseException as error:
        host.result["inputs_unchanged"] = False
        record_error(context, "pins", error)
    if context.a_entered:
        try:
            _, head = H["V2"]["journal_from_disk"](host)
            host.result.update(journal_verified=True, journal_last_sha256=head)
        except BaseException as error:
            host.result["journal_verified"] = False
            record_error(context, "failure", error)
    # No await between this owning-loop/physical proof and the synchronous
    # terminal writes. Never publish success first and rely on HELD rewrites.
    ready = terminal_ready(host)
    if not ready:
        return await retain(context, "RETURN_WITHOUT_RELEASE")
    host.result["terminal_resources_verified"] = ready
    passed = ready and success(context)
    host.result.update(
        outcome="PG16_SHELL_READER_VERIFIED" if passed else "NOT_PASSED",
        commands=host.commands,
        checkpoint_count=len(getattr(host, "_checkpoint_records", ())),
        cleanup_attempts=context.cleanup_attempts,
        interrupted=context.interrupted,
    )
    context.state["phase"] = "FINISHED" if passed else "ABORTED"
    try:
        host.save("attempt.json", context.state)
        host.save("result.json", host.result)
    except BaseException as error:
        record_error(context, "persist", error)
        return await retain(context, "TERMINAL_PERSISTENCE")
    context.released = True
    visible(context.state["phase"], host.result["outcome"])
    return 0 if passed else 1


async def run(context):
    host = context.host
    try:
        await host.start_supervision()
        host._foreground_case = H["CASES"][0]
        context.a_entered = True  # sample() can already invoke the clock helper
        await host.foreground(host.start_cycle())
        host._foreground_case = None
        _, head = H["V2"]["journal_from_disk"](host)
        host.result.update(journal_verified=True, journal_last_sha256=head)
        await host.perform_b()
    except BaseException as error:
        record_error(context, "failure", error)
        if host.cycle is not None:
            try:
                host.cycle = host.libs["core"]["abort"](host.cycle)
                host.save("cycle.json", json.loads(host.libs["core"]["encode"](host.cycle)))
            except BaseException as abort_error:
                record_error(context, "failure", abort_error)
    return await finish(context)


def drive(context):
    loop, coroutine = None, None
    try:
        loop = asyncio.new_event_loop()
        need(
            type(loop) is asyncio.ProactorEventLoop and loop.get_task_factory() is None, "HOST_LOOP"
        )
        asyncio.set_event_loop(loop)
        coroutine = run(context)
        root = loop.create_task(coroutine, name="maskgw-pg16-shell-root")
    except BaseException:
        # The loop has never run: no root body, child or native operation has
        # started. Collect even a task registered before create_task raised.
        context.interrupted = True
        if coroutine is not None:
            coroutine.close()
        if loop is None:
            visible("REFUSED", "HOST_LOOP")
            return 1
        try:
            pending = tuple(asyncio.all_tasks(loop))
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            need(not any(not task.done() for task in asyncio.all_tasks(loop)), "HOST_LOOP")
            loop.close()
        except BaseException:
            # Unknown loop collection is retained, never an implicit release.
            context.held = True
            visible("HELD", "LOOP_SETUP_UNPROVEN")
            while True:
                try:
                    loop.run_forever()
                except BaseException:
                    context.interrupted = True
                    time.sleep(0.1)
        visible("REFUSED", "HOST_LOOP")
        return 1
    while True:
        try:
            status = loop.run_until_complete(root)
            if context.released and not any(not task.done() for task in asyncio.all_tasks(loop)):
                loop.close()
                return status
            context.released = False
            root = loop.create_task(
                retain(context, "RETURN_WITHOUT_RELEASE"), name="maskgw-pg16-shell-held"
            )
        except BaseException:
            context.interrupted = True
            visible("HELD", "RUNNER_INTERRUPTED")
            if root.done():
                context.released = False
                root = loop.create_task(
                    retain(context, "RUNNER_INTERRUPTED"), name="maskgw-pg16-shell-held"
                )
            elif context.host._foreground is not None and not context.host._foreground.done():
                loop.call_soon(context.host._foreground.cancel)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(2)
    try:
        context = prepare(Path(sys.argv[1]))
    except BaseException:
        visible("REFUSED", "ADMISSION")
        raise SystemExit(1) from None
    raise SystemExit(drive(context))
