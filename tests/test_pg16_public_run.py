"""Entry orchestration with binding fakes. No native process/thread/Docker."""

import ast
import asyncio
import hashlib
import runpy
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_pg16_public_host import bound as binding_fixture

REPO = Path(__file__).resolve().parents[1]
bound = binding_fixture


@pytest.fixture
def entry() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/pg16_public_run.py"))


@pytest.fixture
def context(entry: Any, bound: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    _, host, engine = bound
    events: list[Any] = []
    stopped = asyncio.Event()
    tick = [0]
    host._checkpoint_records = ()
    context = entry["Context"](host.root, host.state, host)

    async def heartbeat() -> None:
        while not host._heartbeat_stop and not stopped.is_set():
            await asyncio.sleep(0.01)

    def close() -> bool:
        events.append("join")
        assert entry["join_ready"](host)
        stopped.set()
        return True

    async def supervise() -> None:
        events.append("supervision")
        host._monitor = SimpleNamespace(
            close=close,
            metadata=lambda: {"thread_joined": True, "fired": False, "held": False},
            ack=threading.Event(),
        )
        host._heartbeat = host._task(heartbeat(), "fake-heartbeat")

    async def sample() -> Any:
        tick[0] += 10000
        return host.libs["core"]["Sample"](
            "134372287595000000", str(tick[0]), str(134373000000000000 + tick[0] * 10000)
        )

    async def check_app(action, **_kw):
        events.append(action)

    original_preflight = host.preflight

    async def preflight():
        events.append("preflight")
        await original_preflight()

    async def wait_observation():
        return None

    async def processes(*_args, **_kw):
        return [{"pid": 123, "created": "134372987595123457", "name": "Docker Desktop"}]

    async def restore():
        events.append("restore")
        assert host._monitor_joined and host._heartbeat.done()
        host.result["desktop_restored"] = True

    host.start_supervision = supervise
    host.sample = sample
    host.check_app = check_app
    host.preflight = preflight
    host.wait_observation = wait_observation
    host.processes = processes
    host.restore_desktop = restore
    # The actual frozen replay implementation is used against the actual
    # twelve immutable journal files; no fabricated journal success here.
    monkeypatch.setitem(entry["H"], "V2", {"journal_from_disk": module_journal(host)})
    return context, engine, events, stopped


def module_journal(host: Any) -> Any:
    current = host.__class__.__init__.__globals__["V2"]
    return current["journal_from_disk"]


def test_complete_inherited_cycle_replay_one_probe_join_then_restore(entry, context):
    value, engine, events, _ = context
    assert asyncio.run(entry["run"](value)) == 0
    assert value.released and not value.held and not engine.rows
    assert events[0] == "supervision"
    assert events.count("OBSERVE") == 9
    assert (
        events.index("preflight") < [i for i, event in enumerate(events) if event == "OBSERVE"][-1]
    )
    assert events.index("B") < events.index("join") < events.index("restore")
    assert len(list(value.root.glob("checkpoint-*.json"))) == 12
    assert value.host.result["outcome"] == "PG16_PUBLIC_VERIFIED"


@pytest.mark.parametrize("kind", ["cancel", "timeout", "failed"])
def test_case_failure_still_collects_and_restores_without_success(entry, context, kind):
    value, engine, events, _ = context

    async def fail():
        if kind == "cancel":
            raise asyncio.CancelledError
        if kind == "timeout":
            raise TimeoutError("private-error")
        raise RuntimeError("private-error")

    value.host.perform_b = fail
    assert asyncio.run(entry["run"](value)) == 1
    assert value.released and not engine.rows and "restore" in events
    assert (
        value.host.result["failure_category"]
        == {
            "cancel": "CANCELLED",
            "timeout": "DEADLINE",
            "failed": "INTERNAL",
        }[kind]
    )
    assert "private-error" not in (value.root / "result.json").read_text()


@pytest.mark.parametrize("failure", ["cleanup", "foreground", "join"])
def test_held_keeps_loop_and_host_without_restore_or_second_cleanup(entry, context, failure):
    value, _, events, stopped = context
    host = value.host
    cleanups = []
    original = host.cleanup_owned

    async def cleanup():
        cleanups.append(True)
        if failure == "cleanup":
            host.result["owned_cleanup"] = False
            return
        await original()

    original_supervise = host.start_supervision

    async def supervise():
        await original_supervise()
        if failure == "join":
            host._monitor.close = lambda: False

    async def perform():
        if failure == "foreground":
            host._foreground = host._task(asyncio.Event().wait(), "fake-pending-foreground")

    host.start_supervision, host.cleanup_owned, host.perform_b = supervise, cleanup, perform

    async def run() -> None:
        task = asyncio.create_task(entry["run"](value))
        try:
            for _ in range(100):
                if value.held:
                    break
                await asyncio.sleep(0.01)
            assert value.held and not value.released and not task.done()
            assert "restore" not in events
            assert len(cleanups) == (0 if failure == "foreground" else 1)
            assert ("join" in events) is False  # only our failed-close fake ran
        finally:
            # Test-only teardown of fake tasks, never the operational HELD rule.
            stopped.set()
            for owned in host._host_tasks:
                if not owned.done():
                    owned.cancel()
            # Cancel again only in this fake teardown if the first cancellation
            # was caught while the entry was transitioning into HELD.
            for _ in range(5):
                if task.done():
                    break
                task.cancel()
                await asyncio.sleep(0.01)
            assert task.done()
            await asyncio.gather(task, *host._host_tasks, return_exceptions=True)

    asyncio.run(run())


@pytest.mark.parametrize("offset,category", [(508.0, "RESTORE_MARGIN"), (601.0, "POST_B_OVERRUN")])
def test_overrun_reproves_but_never_skips_safe_restore(
    entry, context, monkeypatch, offset, category
):
    value, _, events, _ = context
    host = value.host
    original = host.stop_supervision

    async def stop():
        await original()
        started = host._store.read().b_started
        monkeypatch.setitem(
            entry["restore_budget"].__globals__,
            "time",
            SimpleNamespace(monotonic=lambda: started + offset),
        )

    host.stop_supervision = stop
    assert asyncio.run(entry["run"](value)) == 1
    assert value.released and "restore" in events
    assert host.result["deadline_category"] == category


def test_join_preconditions_are_checked_and_lock_not_stolen(entry, context):
    value, _, _, _ = context
    host = value.host
    host.result["owned_cleanup"] = True
    assert entry["join_ready"](host)
    host._cleanup_lock.acquire()
    try:
        assert not entry["join_ready"](host)
        assert host._cleanup_lock.locked()
    finally:
        host._cleanup_lock.release()


@pytest.fixture
def fresh(entry: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    root = tmp_path / "AppData/Local/Temp" / ("maskgw-pg16-public-20261030-" + "b" * 32)
    root.mkdir(parents=True)
    policy = entry["H"]["captured"](*entry["H"]["SOURCES"]["profile"])[0]
    state = {
        "kind": "maskgw-pg16-public-v1",
        "task": "a" * 32,
        "phase": "FRESH",
        "invoked": False,
        "program_sha256": entry["PROGRAM_SHA"],
        "v2_sha256": entry["V2_SHA"],
        "host_sha256": entry["HOST_SHA"],
        "entry_sha256": hashlib.sha256(Path(entry["__file__"]).read_bytes()).hexdigest(),
        "pins": dict(entry["R"]["LIBRARIES"].values()),
        "pg_pins": dict(entry["H"]["SOURCES"].values()),
        "image": policy["IMAGE"],
        "create_measurement": policy["blueprint"]("a" * 32)[1],
    }
    monkeypatch.setitem(entry["R"], "HOME", tmp_path)
    monkeypatch.setitem(
        entry["admit"].__globals__,
        "sys",
        SimpleNamespace(
            platform="win32",
            version_info=(3, 11, 3),
            flags=SimpleNamespace(isolated=1, dont_write_bytecode=1, optimize=0),
        ),
    )
    (root / "attempt.json").write_bytes(entry["R"]["json_bytes"](state))
    return root, state


def test_closed_admission_accepts_only_fresh_canonical_state(entry, fresh):
    root, state = fresh
    assert entry["admit"](root) == state
    (root / "invoked.json").write_bytes(b"public")
    with pytest.raises(RuntimeError, match="FRESH_ROOT"):
        entry["admit"](root)


@pytest.mark.parametrize(
    "field,value",
    [
        ("phase", "INVOKED"),
        ("invoked", True),
        ("task", "wrong"),
        ("host_sha256", "0" * 64),
        ("v2_sha256", "0" * 64),
        ("pins", {}),
        ("pg_pins", {}),
        ("image", "sha256:" + "0" * 64),
    ],
)
def test_admission_refuses_pin_or_reuse_faults(entry, fresh, field, value):
    root, state = fresh
    state[field] = value
    (root / "attempt.json").write_bytes(entry["R"]["json_bytes"](state))
    with pytest.raises(RuntimeError, match="STATE_VALUES"):
        entry["admit"](root)


def test_noncanonical_state_refused(entry, fresh):
    root, _ = fresh
    path = root / "attempt.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(RuntimeError, match="STATE_SCHEMA"):
        entry["admit"](root)


@pytest.mark.parametrize("fault", [None, "measurement", "admission-time"])
def test_prepare_validates_before_invocation_and_never_runs_native(
    entry, fresh, monkeypatch, fault
):
    root, state = fresh
    policy = entry["H"]["captured"](*entry["H"]["SOURCES"]["profile"])[0]
    state["create_measurement"] = policy["blueprint"](state["task"])[1]
    if fault == "measurement":
        state["create_measurement"]["margin_chars"] -= 1
    (root / "attempt.json").write_bytes(entry["R"]["json_bytes"](state))
    monkeypatch.setattr(entry["H"]["Host"], "pins", lambda _self: None)
    original = entry["R"]["pinned"]
    stdlib_reads = []

    def pinned(path, digest, *args):
        if str(path).endswith(
            (
                "asyncio/windows_utils.py",
                "asyncio\\windows_utils.py",
                "proactor_events.py",
                "base_subprocess.py",
                "windows_events.py",
                "streams.py",
                "subprocess.py",
            )
        ):
            stdlib_reads.append(path)
            return b"fake-public-pin"
        return original(path, digest, *args)

    monkeypatch.setitem(entry["R"], "pinned", pinned)
    times = iter((0.0, 4.0 if fault == "admission-time" else 0.1))
    monkeypatch.setitem(
        entry["prepare"].__globals__, "time", SimpleNamespace(monotonic=lambda: next(times))
    )
    if fault:
        with pytest.raises(RuntimeError, match=r"CREATE_MEASUREMENT|ADMISSION_TIME"):
            entry["prepare"](root)
        assert not (root / "invoked.json").exists()
    else:
        value = entry["prepare"](root)
        assert value.state["invoked"] is True and value.state["phase"] == "INVOKED"
        assert (root / "invoked.json").is_file() and len(stdlib_reads) == 6
        assert value.host._monitor is None and not value.host.records


def test_emergency_join_enqueues_abort_without_touching_loop_tasks(entry, context):
    value, _, events, _ = context
    host = value.host
    original = host.start_supervision

    async def supervise():
        await original()
        close = host._monitor.close

        def joining():
            loop = asyncio.get_running_loop()
            loop.call_soon(host._abort_foreground)
            assert not host._monitor.ack.is_set()  # callback queued while join is synchronous
            assert host._cleanup_lock.acquire(blocking=False)
            host._cleanup_lock.release()
            events.append("emergency-finished")  # simulated separate-loop cleanup has completed
            return close()

        host._monitor.close = joining

    host.start_supervision = supervise
    assert asyncio.run(entry["run"](value)) == 0
    assert host._monitor.ack.is_set()
    assert events.index("emergency-finished") < events.index("restore")


@pytest.mark.parametrize("pending", [True, False])
def test_outer_runner_interrupt_keeps_same_loop_and_never_cancels_owned_tasks(
    entry, context, monkeypatch, pending
):
    value, _, _, _ = context
    calls = []

    class Task:
        def done(self):
            return not pending

        def cancel(self):
            raise AssertionError("runner must not cancel owned task")

    class Loop:
        def __init__(self) -> None:
            self.runs = 0

        def create_task(self, coroutine, *, name):
            coroutine.close()  # definitions-only fake, not a real operational task
            calls.append(name)
            return Task()

        def run_until_complete(self, _task):
            self.runs += 1
            if self.runs == 1:
                raise KeyboardInterrupt
            assert "close" not in calls
            value.released = True  # fake positive resource proof on resumed loop
            return 1

        def call_soon(self, _callback):
            calls.append("abort-queued")

        def close(self):
            assert value.released
            calls.append("close")

    loop = Loop()
    value.host._monitor = object()
    monkeypatch.setattr(asyncio, "new_event_loop", lambda: loop)
    monkeypatch.setattr(asyncio, "set_event_loop", lambda _loop: None)
    monkeypatch.setattr(asyncio, "ProactorEventLoop", Loop)
    monkeypatch.setattr(asyncio, "all_tasks", lambda _loop: set())
    assert entry["drive"](value) == 1 and value.interrupted
    assert calls == [
        "maskgw-pg16-public-root",
        "abort-queued" if pending else "maskgw-pg16-public-held",
        "close",
    ]


def test_interrupt_during_join_is_recorded_and_keeps_retention(entry, context):
    value, _, events, stopped = context

    async def interrupted():
        raise KeyboardInterrupt

    value.host.stop_supervision = interrupted

    async def run() -> None:
        task = asyncio.create_task(entry["run"](value))
        try:
            for _ in range(100):
                if value.held:
                    break
                await asyncio.sleep(0.01)
            assert value.held and value.interrupted and not task.done()
            assert "restore" not in events
        finally:
            stopped.set()
            task.cancel()
            await asyncio.gather(task, *value.host._host_tasks, return_exceptions=True)

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["volume-mismatch", "exception", "pending"])
def test_restore_uncertainty_retains_without_stop_false_interrupt_or_second_cleanup(
    entry, context, failure
):
    value, engine, events, stopped = context
    host = value.host
    cleanups = []
    cleanup = host.cleanup_owned

    async def collect() -> None:
        cleanups.append(True)
        await cleanup()

    async def restore() -> None:
        events.append("restore-attempt")
        assert host._monitor_joined and host._heartbeat.done()
        if failure == "volume-mismatch":
            engine.volumes.add("foreign_volume_after_join")
            await host.__class__.restore_desktop(host)
        elif failure == "exception":
            raise RuntimeError("synthetic-private-restore-error")
        else:
            host.result["desktop_restored"] = False

    host.cleanup_owned, host.restore_desktop = collect, restore

    async def exercise() -> None:
        task = asyncio.create_task(entry["run"](value))
        try:
            for _ in range(100):
                if value.held:
                    break
                await asyncio.sleep(0.01)
            assert value.held and not value.released and not value.interrupted
            assert not task.done() and len(cleanups) == 1
            assert events.index("join") < events.index("restore-attempt")
            assert host.result["retention_category"] == "DESKTOP_RESTORE_UNPROVEN"
            assert not any(
                type(args) is tuple and args[:2] == ("desktop", "stop") for _, args in engine.events
            )
            assert "synthetic-private" not in (host.root / "result.json").read_text()
        finally:
            # Only fake tasks/owners are torn down here, never an operational HELD loop.
            stopped.set()
            task.cancel()
            await asyncio.gather(task, *host._host_tasks, return_exceptions=True)

    asyncio.run(exercise())


def test_success_requires_volume_reconciliation_flag(entry, context):
    value, _, events, _ = context
    original = value.host.restore_desktop

    async def restore() -> None:
        await original()
        value.host.result["volumes_restored"] = False

    value.host.restore_desktop = restore
    assert asyncio.run(entry["run"](value)) == 1
    assert value.released and "restore" in events
    assert value.host.result["outcome"] == "NOT_PASSED"


def diagnostic_error(host: Any, origin: str) -> tuple[BaseException, str]:  # noqa: PLR0911 - one closed constructor per captured origin
    if origin == "RUNTIME":
        return RuntimeError("VOLUME_BASELINE_STALE"), "VOLUME_BASELINE_STALE"
    if origin == "PROBE":
        return host.profile["ProbeError"]("CONFIG"), "CONFIG"
    if origin == "BOOTSTRAP":
        return host.channel["BootstrapError"](host.channel["Fault"].IO), "IO"
    if origin == "VOLUME":
        return host.pg["volumes"]["VolumeFault"](), "VOLUME_INVENTORY"
    if origin == "HOST_FAULT":
        return host.libs["bounded"]["HostFault"]("OUTPUT_LIMIT"), "OUTPUT_LIMIT"
    if origin == "IDENTITY":
        return host.pg["identity"]["IdentityError"](), "IDENTITY_UNKNOWN"
    if origin == "EMERGENCY":
        return host.pg["emergency"]["EmergencyError"]("BUDGET"), "BUDGET"
    assert origin == "VALUE"
    return ValueError("CLOCK_REFUSED"), "CLOCK_REFUSED"


@pytest.mark.parametrize(
    "origin",
    ["RUNTIME", "PROBE", "BOOTSTRAP", "VOLUME", "HOST_FAULT", "IDENTITY", "EMERGENCY", "VALUE"],
)
@pytest.mark.parametrize("phase", ["failure", "cleanup", "restore"])
def test_closed_diagnostic_origin_survives_each_pipeline_boundary(entry, context, origin, phase):
    value, _, _, stopped = context
    host = value.host
    error, code = diagnostic_error(host, origin)

    async def fail() -> None:
        raise error

    setattr(
        host,
        {"failure": "perform_b", "cleanup": "cleanup_owned", "restore": "restore_desktop"}[phase],
        fail,
    )

    async def exercise() -> None:
        task = asyncio.create_task(entry["run"](value))
        try:
            for _ in range(100):
                if value.held or task.done():
                    break
                await asyncio.sleep(0.01)
            assert host.result[phase + "_category"] == code
            assert host.result[phase + "_origin"] == origin
            if phase == "failure":
                assert await task == 1 and value.released
            else:
                assert value.held and not value.released and not task.done()
        finally:
            stopped.set()
            if not task.done():
                task.cancel()
            for owned in host._host_tasks:
                if not owned.done():
                    owned.cancel()
            await asyncio.gather(task, *host._host_tasks, return_exceptions=True)

    asyncio.run(exercise())


DIAGNOSTIC_SOURCES = (
    "pg16_public_run.py",
    "pg16_public_host.py",
    "pg16_public_owner.py",
    "pg16_public_cleanup_policy.py",
    "pg16_public_watchdog.py",
    "pg16_public_emergency.py",
    "pg16_public_profile.py",
    "pg16_public_volumes.py",
    "w1_bootstrap_channel.py",
    "w1_bootstrap_identity.py",
    "oracle9_w1_run.py",
    "oracle9_w1_run_v2.py",
    "oracle9_cycle_freshness.py",
    "oracle9_clock_sample.py",
    "run_linux_as_probe.py",
)


def source_calls(names: tuple[str, ...], constructor: str) -> set[str]:
    result = set()
    for name in names:
        for node in ast.walk(ast.parse((REPO / "docs/poc" / name).read_bytes())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == constructor
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and type(node.args[0].value) is str
            ):
                result.add(node.args[0].value)
    return result


def class_codes(name: str, class_name: str) -> set[str]:
    tree = ast.parse((REPO / "docs/poc" / name).read_bytes())
    cls = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return {
        node.value
        for node in ast.walk(cls)
        if isinstance(node, ast.Constant)
        and type(node.value) is str
        and node.value.isupper()
        and node.value.replace("_", "").isalnum()
    }


def test_exact_diagnostic_sets_equal_pinned_chain_ast_without_runtime_ast(entry):
    codes = source_calls(DIAGNOSTIC_SOURCES, "RuntimeError")
    for name in DIAGNOSTIC_SOURCES:
        for node in ast.walk(ast.parse((REPO / "docs/poc" / name).read_bytes())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "need"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and type(node.args[1].value) is str
            ):
                codes.add(node.args[1].value)
    assert entry["RUNTIME_CODES"] == codes
    assert entry["VALUE_CODES"] == source_calls(DIAGNOSTIC_SOURCES, "ValueError")
    assert entry["BOUNDED_CODES"] == source_calls(("run_linux_as_probe.py",), "HostFault")
    assert entry["PROBE_CODES"] == class_codes("pg16_public_profile.py", "ProbeError")
    assert entry["EMERGENCY_CODES"] == class_codes("pg16_public_emergency.py", "EmergencyError")
    tree = ast.parse(Path(entry["__file__"]).read_bytes())
    assert not any(
        isinstance(node, ast.Import) and any(alias.name == "ast" for alias in node.names)
        for node in ast.walk(tree)
    )


def test_all_declared_literals_and_enum_values_have_closed_origins(entry, bound):
    _, host, _ = bound
    for key, origin, factory in (
        ("RUNTIME_CODES", "RUNTIME", RuntimeError),
        ("VALUE_CODES", "VALUE", ValueError),
        ("PROBE_CODES", "PROBE", host.profile["ProbeError"]),
        ("BOUNDED_CODES", "HOST_FAULT", host.libs["bounded"]["HostFault"]),
        ("EMERGENCY_CODES", "EMERGENCY", host.pg["emergency"]["EmergencyError"]),
    ):
        for code in entry[key]:
            assert entry["diagnostic"](factory(code), host) == (code, origin)
    for fault in host.channel["Fault"]:
        error = host.channel["BootstrapError"](fault)
        assert entry["diagnostic"](error, host) == (fault.value, "BOOTSTRAP")


def test_foreign_subclass_malformed_or_opaque_error_is_internal_without_hooks(entry, bound):
    _, host, _ = bound
    foreign = runpy.run_path(str(REPO / "docs/poc/pg16_public_profile.py"))
    malformed = host.channel["BootstrapError"](host.channel["Fault"].IO)
    malformed.category = "IO"
    bad_args = host.libs["bounded"]["HostFault"]("OUTPUT_LIMIT")
    bad_args.args = ("OUTPUT_LIMIT", "synthetic-private")

    class OpaqueMeta(type):
        def __hash__(cls) -> int:
            raise AssertionError("untrusted class hash must not be called")

        def __eq__(cls, _other: object) -> bool:
            raise AssertionError("untrusted class equality must not be called")

    class OpaqueError(Exception, metaclass=OpaqueMeta):
        def __getattribute__(self, _name: str) -> Any:
            raise AssertionError("untrusted error attributes must not be read")

    child = type("ForeignChild", (RuntimeError,), {})
    for error in (
        foreign["ProbeError"]("CONFIG"),
        child("CONFIG"),
        malformed,
        bad_args,
        RuntimeError("CONFIG", "synthetic-private"),
        RuntimeError("synthetic-private"),
        OpaqueError(),
    ):
        assert entry["diagnostic"](error, host) == ("INTERNAL", "INTERNAL")


@pytest.mark.parametrize("foreign", [False, True])
def test_clock_fresh_helper_class_requires_exact_captured_parent_frame(
    entry, bound, monkeypatch, foreign
):
    _, host, _ = bound
    clock = host.libs["clock"]
    helper = runpy.run_path(str(REPO / "docs/poc/run_linux_as_probe.py"))
    other = runpy.run_path(str(REPO / "docs/poc/run_linux_as_probe.py")) if foreign else helper
    error = other["HostFault"]("OUTPUT_LIMIT")

    async def bounded(*_args: Any, **_kwargs: Any) -> Any:
        raise error

    helper["bounded"] = bounded
    monkeypatch.setitem(clock, "pinned", lambda *_args: b"fake-public-pin")
    monkeypatch.setitem(
        clock,
        "frozen",
        lambda path, *_args: helper if path == clock["HELPER"] else host.libs["core"],
    )

    async def exercise() -> Any:
        try:
            await clock["sample"]()
        except BaseException as caught:
            return entry["diagnostic"](caught, host)
        raise AssertionError("must raise typed fake fault")

    assert asyncio.run(exercise()) == (
        ("INTERNAL", "INTERNAL") if foreign else ("OUTPUT_LIMIT", "HOST_FAULT")
    )


def test_public_ps_fresh_helper_fault_uses_pinned_invoke_frame(entry, bound, monkeypatch):
    module, host, _ = bound

    class Process:
        returncode = 0

        def __init__(self) -> None:
            self.stdout = self
            self.used = False

        async def read(self, _size: int) -> bytes:
            if self.used:
                return b""
            self.used = True
            return b"xx"

        async def wait(self) -> int:
            return 0

    async def spawn(*_args: Any, **_kwargs: Any) -> Any:
        return Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)

    async def exercise() -> Any:
        try:
            await module["R"]["Host"].invoke(
                host, "fake-public-ps", ["NO_NATIVE_PROCESS"], 1, 1, public_clock=True
            )
        except BaseException as caught:
            return entry["diagnostic"](caught, host)
        raise AssertionError("must refuse excessive fake output")

    assert asyncio.run(exercise()) == ("OUTPUT_LIMIT", "HOST_FAULT")


def test_restore_keyboard_interrupt_is_recorded_while_retaining(entry, context):
    value, _, _, stopped = context

    async def interrupted() -> None:
        raise KeyboardInterrupt

    value.host.restore_desktop = interrupted

    async def exercise() -> None:
        task = asyncio.create_task(entry["run"](value))
        try:
            for _ in range(100):
                if value.held:
                    break
                await asyncio.sleep(0.01)
            assert value.held and value.interrupted and not task.done()
            assert value.host.result["restore_category"] == "INTERRUPTED"
            assert value.host.result["restore_origin"] == "CONTROL"
        finally:
            stopped.set()
            task.cancel()
            await asyncio.gather(task, *value.host._host_tasks, return_exceptions=True)

    asyncio.run(exercise())
