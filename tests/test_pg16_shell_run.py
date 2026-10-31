"""Entry lifecycle and admission fakes. No Docker, clock helper or native watchdog."""

import asyncio
import hashlib
import json
import runpy
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_pg16_shell_host import bound as host_fixture
from tests.test_pg16_shell_host import run

REPO = Path(__file__).resolve().parents[1]
bound = host_fixture


@pytest.fixture
def entry() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/pg16_shell_run.py"))


@pytest.fixture
def context(entry: Any, bound: Any, monkeypatch: Any) -> Any:
    module, host, engine = bound
    # Same reviewed source in an independently loaded exact namespace.
    monkeypatch.setitem(entry["H"], "Host", module["Host"])
    value = entry["Context"](host.root, host.state, host)
    tick = 0

    async def sample() -> Any:
        nonlocal tick
        tick += 10000
        return host.libs["core"]["Sample"](
            "134372287595000000", str(tick), str(134373000000000000 + tick * 10000)
        )

    async def processes(*_args: Any, **_kwargs: Any) -> Any:
        return [{"pid": 123, "name": "Docker Desktop", "created": "134372987595123457"}]

    async def wait_observation() -> None:
        return None

    monkeypatch.setattr(host, "sample", sample)
    monkeypatch.setattr(host, "processes", processes)
    monkeypatch.setattr(host, "wait_observation", wait_observation)
    # External binary/stdlib pins are not measured by transport fakes.
    monkeypatch.setitem(entry["run"].__globals__, "final_pins", lambda _value: None)
    return value, host, engine, module


def test_full23_case_entry_actual_journal_and_host_with_fake_transports(
    entry: Any, context: Any
) -> None:
    value, host, engine, _ = context
    assert run(entry["run"](value)) == 0
    assert value.released and not value.held and value.a_entered
    assert host.result["outcome"] == "PG16_SHELL_READER_VERIFIED"
    assert host.result["checkpoint_count"] == 12 and len(host._cases) == 23
    assert host.result["cleanup_attempts"] == 1
    assert not engine.rows and all(task.done() for task in host._host_tasks)
    entry["H"]["V2"]["journal_from_disk"](host)
    for row in host.result["watchdogs"].values():
        assert row["status"] == "JOINED" and row["metadata"]["fired"] is False


def test_fire_during_a_cancels_foreground_and_never_arms_b(
    entry: Any, context: Any, monkeypatch: Any
) -> None:
    value, host, engine, _ = context

    async def startup() -> None:
        assert host._foreground_case == "one"
        host.initial_active = True
        host._monitors["one"].fired.set()
        host._monitors["one"].callback()
        await asyncio.Event().wait()

    monkeypatch.setattr(host, "start_cycle", startup)
    assert run(entry["run"](value)) == 1
    assert value.released and not engine.rows and host._b_started is None
    assert not host.records and any(row["category"] == "CANCELLED" for row in value.history)


@pytest.mark.parametrize("failure", ["fail_start", "cancel_send", "fail_drain", "bad_report"])
def test_b_failure_collects_and_restores_without_pass(
    entry: Any, context: Any, failure: str
) -> None:
    value, host, engine, _ = context
    setattr(engine, failure, True)
    assert run(entry["run"](value)) == 1
    assert value.released and host.result["desktop_restored"]
    assert not engine.rows and value.history and not host.result.get("pg16_reader_verified", False)


def test_pre_a_failure_joins_without_touching_daemon(
    entry: Any, context: Any, monkeypatch: Any
) -> None:
    value, host, engine, _ = context
    original = host.start_supervision

    async def broken() -> None:
        await original()
        raise RuntimeError("SUPERVISION_HELD")

    monkeypatch.setattr(host, "start_supervision", broken)
    assert run(entry["run"](value)) == 1
    assert value.released and not value.a_entered and not host.commands
    assert all(label.startswith("MONITOR_") for label, _ in engine.events)
    assert host.result["desktop_state"] == "UNTOUCHED_PRE_A"
    assert not host.result.get("inventory_restored", False)


def test_cleanup_failure_with_fire_joins_before_single_same_record_retry(
    entry: Any, context: Any, monkeypatch: Any
) -> None:
    value, host, engine, _ = context
    engine.fail_start = True
    collect = host.cleanup_owned
    calls: list[Any] = []

    async def cleanup() -> None:
        calls.append(tuple(id(r) for r in host.records))
        if len(calls) == 1:
            host.result["owned_cleanup"] = False
            host._monitors["one"].fired.set()
            return
        assert host._all_joined()
        await collect()

    monkeypatch.setattr(host, "cleanup_owned", cleanup)
    assert run(entry["run"](value)) == 1
    assert value.released and len(calls) == 2 and calls[0] == calls[1]
    assert len(host.records) == 1 and not engine.rows
    assert value.history and host.result["watchdogs"]["one"]["metadata"]["fired"]


async def held_task(entry: Any, value: Any) -> Any:
    task = asyncio.create_task(entry["run"](value))
    end = asyncio.get_running_loop().time() + 5.0
    while not value.held and not task.done() and asyncio.get_running_loop().time() < end:
        await asyncio.sleep(0.01)
    assert value.held and not task.done() and not value.released
    return task


def test_unproven_cleanup_without_b_or_fire_retains_monitor_and_loop(
    entry: Any, context: Any, monkeypatch: Any
) -> None:
    value, host, _, _ = context

    async def startup() -> None:
        host.initial_active = True
        raise RuntimeError("HOST_HELD")

    async def cleanup() -> None:
        host.result["owned_cleanup"] = False

    monkeypatch.setattr(host, "start_cycle", startup)
    monkeypatch.setattr(host, "cleanup_owned", cleanup)

    async def scenario() -> None:
        task = await held_task(entry, value)
        assert host._monitors["one"].started and not host._monitors["one"].joined
        assert value.cleanup_attempts == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        # Explicit fake-only teardown; operational HELD loops are never cancelled.
        await host.stop_supervision()

    run(scenario())


@pytest.mark.parametrize("failure", ["join", "owner", "restore", "persist"])
def test_uncertainty_retains_same_context_without_second_writer(
    entry: Any, context: Any, monkeypatch: Any, failure: str
) -> None:
    value, host, engine, _ = context
    original = host.start_supervision
    save = host.save

    async def supervise() -> None:
        await original()
        if failure == "join":
            host._monitors["one"].join_ok = False

    async def restore() -> None:
        host.result["desktop_restored"] = False

    async def before_matrix() -> None:
        # Target this lifecycle fault without making a five-second retention
        # assertion depend on the duration of the entire 23-case fake matrix.
        raise RuntimeError("HOST_HELD")

    def persist(name: str, data: Any) -> None:
        if failure == "persist" and name == "result.json":
            raise OSError("PRIVATE_PERSISTENCE_MARKER")
        save(name, data)

    monkeypatch.setattr(host, "start_supervision", supervise)
    monkeypatch.setattr(host, "save", persist)
    if failure in ("restore", "persist"):
        monkeypatch.setattr(host, "perform_b", before_matrix)
    if failure == "owner":
        engine.owner_held = True
        # Fake time past the wait window, with no fire, to retain promptly.
        monkeypatch.setitem(
            entry["run"].__globals__, "time", SimpleNamespace(monotonic=lambda: 10**12)
        )
    if failure == "restore":
        monkeypatch.setattr(host, "restore_desktop", restore)

    async def scenario() -> None:
        task = await held_task(entry, value)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        engine.owner_held = False
        host._monitors["one"].join_ok = True
        monkeypatch.setattr(host, "save", save)
        await host.cleanup_owned()
        await host.stop_supervision()

    run(scenario())


def test_error_history_survives_resolved_supervision_and_fire_blocks_success(
    entry: Any, context: Any
) -> None:
    value, host, _, _ = context
    assert run(entry["run"](value)) == 0
    entry["record_error"](value, "stop", RuntimeError("SUPERVISION_HELD"))
    host._supervision_errors.clear()
    assert not entry["success"](value)
    value.history.clear()
    host.result["watchdogs"]["one"]["metadata"]["fired"] = True
    assert not entry["success"](value)


@pytest.mark.parametrize(
    "kind",
    ["unknown", "subclass", "runtime", "reader", "bootstrap", "bounded", "cancel", "timeout"],
)
def test_diagnostics_are_closed_exact_and_never_call_hostile_str(
    entry: Any, context: Any, kind: str
) -> None:
    value, host, _, _ = context

    class HostileError(Exception):
        def __str__(self) -> str:
            raise AssertionError("STR_CALLED")

    class DerivedError(RuntimeError):
        pass

    errors = {
        "unknown": HostileError("PRIVATE_MARKER"),
        "subclass": DerivedError("HOST_HELD"),
        "runtime": RuntimeError("B_DEADLINE"),
        "reader": host.reader["ReaderError"](host.reader["Code"].OUTPUT),
        "bootstrap": host.channel["BootstrapError"](host.channel["Fault"].IO),
        "bounded": host.libs["bounded"]["HostFault"]("DEADLINE"),
        "cancel": asyncio.CancelledError(),
        "timeout": TimeoutError("PRIVATE_MARKER"),
    }
    expected = {
        "unknown": ("INTERNAL", "INTERNAL"),
        "subclass": ("INTERNAL", "INTERNAL"),
        "runtime": ("B_DEADLINE", "RUNTIME"),
        "reader": ("OUTPUT", "READER"),
        "bootstrap": ("IO", "BOOTSTRAP"),
        "bounded": ("DEADLINE", "HOST_FAULT"),
        "cancel": ("CANCELLED", "CONTROL"),
        "timeout": ("DEADLINE", "CONTROL"),
    }
    assert entry["diagnostic"](errors[kind], value) == expected[kind]


def test_runtime_vocabulary_is_from_pinned_literals_not_arbitrary_messages(
    entry: Any, context: Any
) -> None:
    value, _, _, _ = context
    for code in (
        "B_DEADLINE",
        "WATCHDOG_FIRED",
        "SUPERVISION_HELD",
        "RESULT_INSPECT_BINDING",
        "INVOKE_SCOPE",
        "PS_SCOPE",
        "READER_CLI_SCOPE",
        "CLI_CONTROLS",
        "MONITOR_HELD",
        "PREVIOUS_CASE_HELD",
        "OWNER_BINDING",
    ):
        assert code in value.runtime_codes
    assert entry["diagnostic"](RuntimeError("PRIVATE_MARKER"), value) == ("INTERNAL", "INTERNAL")


@pytest.mark.parametrize(
    "where", ["delivery-owner", "delivery-channel", "profile-base", "policy-profile"]
)
def test_transitive_capture_mutation_is_detected_without_editing_consumed_sources(
    entry: Any, bound: Any, monkeypatch: Any, where: str
) -> None:
    _, host, _ = bound
    value = entry["Context"](host.root, {**host.state, "entry_sha256": "a" * 64}, host)
    monkeypatch.setitem(entry["R"], "pinned", lambda *_args: b"")
    locations = {
        "delivery-owner": (host.pg["delivery"], "OWNER_RAW"),
        "delivery-channel": (host.pg["delivery"]["O"], "CHANNEL_RAW"),
        "profile-base": (host.profile, "PROFILE_RAW"),
        "policy-profile": (host.pg["policy"], "PROFILE_RAW"),
    }
    namespace, name = locations[where]
    monkeypatch.setitem(namespace, name, namespace[name] + b"\n")
    with pytest.raises(RuntimeError, match="TRANSITIVE_CAPTURE"):
        entry["final_pins"](value)


def test_final_live_transitive_and_stdlib_pins_rechecked_after_b(
    entry: Any, bound: Any, monkeypatch: Any
) -> None:
    _, host, _ = bound
    value = entry["Context"](host.root, {**host.state, "entry_sha256": "a" * 64}, host)
    paths: list[Any] = []
    monkeypatch.setitem(entry["R"], "pinned", lambda path, *_args: paths.append(path))
    host._b_started = 0.0
    entry["final_pins"](value)
    for relative in entry["TRANSITIVE_PINS"]:
        assert REPO / relative in paths
    for relative in entry["C"]["STDLIB_PINS"]:
        assert entry["C"]["STDLIB"] / relative in paths


@pytest.fixture
def admission(entry: Any, bound: Any, tmp_path: Any, monkeypatch: Any) -> Any:
    _, host, _ = bound
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
    root = tmp_path / "AppData/Local/Temp" / ("maskgw-pg16-shell-reader-v1-" + "b" * 32)
    root.mkdir(parents=True)
    state = {
        **host.state,
        "kind": "maskgw-pg16-shell-reader-v1",
        "phase": "FRESH",
        "invoked": False,
        "program_sha256": entry["H"]["V2"]["ORIGINAL_SHA"],
        "v2_sha256": entry["H"]["P"]["V2_SHA"],
        "parent_sha256": entry["H"]["PARENT_SHA"],
        "entry_sha256": hashlib.sha256(Path(entry["__file__"]).read_bytes()).hexdigest(),
        "pg_pins": dict(entry["H"]["SOURCES"].values()),
        "transitive_pins": dict(entry["TRANSITIVE_PINS"]),
        "stdlib_pins": dict(entry["C"]["STDLIB_PINS"]),
        "image": entry["IMAGE"],
    }
    (root / "attempt.json").write_bytes(entry["R"]["json_bytes"](state))
    return root, state, host


def test_admission_canonical_complete_state_with_closed_pins(entry: Any, admission: Any) -> None:
    root, state, _ = admission
    assert entry["R"]["json_bytes"](entry["admit"](root)) == entry["R"]["json_bytes"](state)
    assert len((root / "attempt.json").read_bytes()) <= entry["STATE_LIMIT"]


@pytest.mark.parametrize(
    "failure",
    ["invoked", "extra-file", "noncanonical", "transitive", "stdlib", "task", "extra-key"],
)
def test_admission_rejects_mutated_or_reused_state(
    entry: Any, admission: Any, failure: str
) -> None:
    root, original, _ = admission
    state = deepcopy(original)
    if failure == "invoked":
        state["invoked"] = True
    elif failure == "extra-file":
        (root / "invoked.json").write_bytes(b"preserve")
    elif failure == "transitive":
        state["transitive_pins"].clear()
    elif failure == "stdlib":
        state["stdlib_pins"].clear()
    elif failure == "task":
        state["task"] = "../PRIVATE_MARKER"
    elif failure == "extra-key":
        state["unexpected"] = "PRIVATE_MARKER"
    raw = entry["R"]["json_bytes"](state)
    (root / "attempt.json").write_bytes(raw + (b"\n" if failure == "noncanonical" else b""))
    with pytest.raises(RuntimeError):
        entry["admit"](root)
    assert not (root / "result.json").exists()


def test_prepare_invocation_is_durable_one_shot_and_precedes_a(
    entry: Any, admission: Any, monkeypatch: Any
) -> None:
    root, state, host = admission
    host.root, host.state = root, state
    monkeypatch.setitem(entry["H"], "Host", lambda *_args: host)
    monkeypatch.setitem(entry["prepare"].__globals__, "final_pins", lambda _value: None)
    value = entry["prepare"](root)
    assert not value.a_entered and (root / "invoked.json").is_file()
    assert json.loads((root / "attempt.json").read_bytes())["invoked"] is True
    with pytest.raises(RuntimeError, match="FRESH_ROOT"):
        entry["prepare"](root)


def test_prepare_time_exceeded_writes_no_invocation(
    entry: Any, admission: Any, monkeypatch: Any
) -> None:
    root, state, host = admission
    host.root, host.state = root, state
    monkeypatch.setitem(entry["H"], "Host", lambda *_args: host)
    monkeypatch.setitem(entry["prepare"].__globals__, "final_pins", lambda _value: None)
    samples = iter((0.0, 3.01))
    monkeypatch.setitem(
        entry["prepare"].__globals__, "time", SimpleNamespace(monotonic=lambda: next(samples))
    )
    with pytest.raises(RuntimeError, match="ADMISSION_TIME"):
        entry["prepare"](root)
    assert not (root / "invoked.json").exists() and not host.commands


def test_physical_readiness_error_is_unknown_not_unhandled(
    entry: Any, context: Any, monkeypatch: Any
) -> None:
    _, host, _, _ = context

    def unknown() -> bool:
        raise OSError("PRIVATE_METADATA_MARKER")

    monkeypatch.setattr(host, "_all_joined", unknown)
    assert entry["physical_ready"](host) is False


def test_late_fire_observation_does_not_extend_emergency_join_window(
    entry: Any, context: Any, monkeypatch: Any
) -> None:
    value, host, _, _ = context
    monkeypatch.setitem(entry["run"].__globals__, "time", SimpleNamespace(monotonic=lambda: 700.0))

    async def scenario() -> None:
        await host.start_supervision()
        host._b_started = 0.0
        host._monitors["one"].fired.set()
        assert await entry["await_emergency"](value) is False
        assert not host._monitors["one"].joined
        await host.stop_supervision()

    run(scenario())


@pytest.mark.parametrize("foreign", [False, True])
def test_fresh_clock_fault_requires_exact_captured_caller_and_class(
    entry: Any, context: Any, monkeypatch: Any, foreign: bool
) -> None:
    value, host, _, _ = context
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

    async def scenario() -> Any:
        try:
            await clock["sample"]()
        except Exception as caught:
            return entry["diagnostic"](caught, value)
        raise AssertionError("EXPECTED_FAKE_FAULT")

    assert run(scenario()) == (
        ("INTERNAL", "INTERNAL") if foreign else ("OUTPUT_LIMIT", "HOST_FAULT")
    )


def test_fresh_public_ps_fault_is_bound_to_real_bounded_method(
    entry: Any, context: Any, monkeypatch: Any
) -> None:
    value, host, _, module = context

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

    async def scenario() -> Any:
        try:
            await module["Host"]._bounded(
                host, "fake-public-ps", ["NO_NATIVE_PROCESS"], 1, 1, public_clock=True
            )
        except Exception as error:
            return entry["diagnostic"](error, value)
        raise AssertionError("EXPECTED_FAKE_LIMIT")

    assert run(scenario()) == ("OUTPUT_LIMIT", "HOST_FAULT")


def test_live_transitive_change_after_b_reproves_sources(
    entry: Any, bound: Any, monkeypatch: Any
) -> None:
    _, host, _ = bound
    value = entry["Context"](host.root, {**host.state, "entry_sha256": "a" * 64}, host)
    host._b_started = 0.0
    target = REPO / "docs/poc/pg16_shell_reader.py"

    def pin(path: Any, *_args: Any) -> bytes:
        if path == target:
            raise RuntimeError("SOURCE_PIN")
        return b""

    monkeypatch.setitem(entry["R"], "pinned", pin)
    with pytest.raises(RuntimeError, match="SOURCE_PIN"):
        entry["final_pins"](value)


def test_root_reparse_flag_refused_without_following_link(entry: Any) -> None:
    path = SimpleNamespace(
        lstat=lambda: SimpleNamespace(st_mode=0o040700, st_file_attributes=0x400),
        is_symlink=lambda: False,
    )
    with pytest.raises(RuntimeError, match="ROOT_DIRECTORY"):
        entry["_directory"](path)


def test_monitor_captured_copy_is_independently_checked(
    entry: Any, bound: Any, monkeypatch: Any
) -> None:
    _, host, _ = bound
    value = entry["Context"](host.root, {**host.state, "entry_sha256": "a" * 64}, host)
    policy = {**host.pg["policy"], "PROFILE_RAW": host.pg["policy"]["PROFILE_RAW"] + b"\n"}
    host._monitors["one"] = SimpleNamespace(_policy=policy)
    monkeypatch.setitem(entry["R"], "pinned", lambda *_args: b"")
    with pytest.raises(RuntimeError, match="TRANSITIVE_CAPTURE"):
        entry["final_pins"](value)


@pytest.mark.parametrize("phase", ["before-fire", "after-join"])
def test_emergency_wait_uses_original_b_deadline_without_renewal(
    entry: Any, context: Any, monkeypatch: Any, phase: str
) -> None:
    value, host, _, _ = context
    tick = [599.0]
    public_async = dict(vars(asyncio))

    async def sleep(seconds: float) -> None:
        tick[0] += seconds
        if phase == "after-join":
            host._monitors["one"].fired.set()

    public_async["sleep"] = sleep
    monkeypatch.setitem(
        entry["run"].__globals__, "time", SimpleNamespace(monotonic=lambda: tick[0])
    )
    monkeypatch.setitem(entry["run"].__globals__, "asyncio", SimpleNamespace(**public_async))

    async def scenario() -> None:
        await host.start_supervision()
        host._b_started = 0.0
        stamp = host._b_started
        if phase == "after-join":
            original = host._monitors["one"].close

            def close() -> bool:
                tick[0] = 656.0
                return bool(original())

            monkeypatch.setattr(host._monitors["one"], "close", close)
        assert await entry["await_emergency"](value) is False
        assert host._b_started == stamp
        await host.stop_supervision()

    run(scenario())


class DriverTask:
    def __init__(self) -> None:
        self.completed = False

    def done(self) -> bool:
        return self.completed

    def cancel(self) -> None:
        self.completed = True


class DriverLoop:
    def __init__(self, value: Any, mode: str) -> None:
        self.value, self.mode = value, mode
        self.tasks: list[DriverTask] = []
        self.names: list[str] = []
        self.calls, self.closed, self.cancelled = 0, False, 0

    def create_task(self, coroutine: Any, name: str) -> Any:
        coroutine.close()  # fake control flow only; never executes entry/HELD
        task = DriverTask()
        self.tasks.append(task)
        self.names.append(name)
        return task

    def get_task_factory(self) -> Any:
        return None

    def call_soon(self, function: Any) -> None:
        function()

    def run_until_complete(self, task: Any) -> int:
        self.calls += 1
        if self.calls == 1 and self.mode == "interrupt":
            raise KeyboardInterrupt
        task.completed = True
        if self.calls == 1 and self.mode == "pending":
            self.value.released = False
            return 1
        self.value.released = True
        for known in self.tasks:
            known.completed = True
        return 1

    def close(self) -> None:
        assert all(task.done() for task in self.tasks)
        self.closed = True


@pytest.mark.parametrize("mode", ["normal", "interrupt", "pending"])
def test_driver_keeps_single_loop_and_never_restarts_root(
    entry: Any, context: Any, monkeypatch: Any, mode: str
) -> None:
    value, host, _, _ = context
    loop = DriverLoop(value, mode)
    host._foreground = SimpleNamespace(
        done=lambda: False, cancel=lambda: setattr(loop, "cancelled", loop.cancelled + 1)
    )
    public_async = dict(vars(asyncio)) | {
        "ProactorEventLoop": DriverLoop,
        "new_event_loop": lambda: loop,
        "set_event_loop": lambda _loop: None,
        "all_tasks": lambda _loop: set(loop.tasks),
    }
    monkeypatch.setitem(entry["drive"].__globals__, "asyncio", SimpleNamespace(**public_async))
    assert entry["drive"](value) == 1
    assert loop.closed and loop.names.count("maskgw-pg16-shell-root") == 1
    assert loop.cancelled == (1 if mode == "interrupt" else 0)
    assert value.interrupted is (mode == "interrupt")
    assert ("maskgw-pg16-shell-held" in loop.names) is (mode == "pending")


def test_wrong_empty_loop_is_closed_before_refusal(
    entry: Any, context: Any, monkeypatch: Any
) -> None:
    value, _, _, _ = context
    loop = DriverLoop(value, "normal")
    public_async = dict(vars(asyncio)) | {
        "ProactorEventLoop": type("OtherLoop", (), {}),
        "new_event_loop": lambda: loop,
        "set_event_loop": lambda _loop: None,
    }
    monkeypatch.setitem(entry["drive"].__globals__, "asyncio", SimpleNamespace(**public_async))
    assert entry["drive"](value) == 1
    assert loop.closed and not loop.names


@pytest.mark.parametrize("registered", [False, True])
def test_driver_setup_failure_collects_unstarted_coroutine_and_any_registered_task(
    entry: Any, context: Any, monkeypatch: Any, registered: bool
) -> None:
    value, _, _, _ = context
    loop = DriverLoop(value, "normal")
    coroutines: list[Any] = []

    def create(coroutine: Any, **_kwargs: Any) -> Any:
        coroutines.append(coroutine)
        if registered:
            loop.tasks.append(DriverTask())
        raise RuntimeError("PRIVATE_CREATE_TASK_MARKER")

    def gathered(*tasks: Any, **_kwargs: Any) -> Any:
        assert tasks and all(task.done() for task in tasks)
        return object()

    monkeypatch.setattr(loop, "create_task", create)
    monkeypatch.setattr(loop, "run_until_complete", lambda _value: None)
    public_async = dict(vars(asyncio)) | {
        "ProactorEventLoop": DriverLoop,
        "new_event_loop": lambda: loop,
        "set_event_loop": lambda _loop: None,
        "all_tasks": lambda _loop: set(loop.tasks),
        "gather": gathered,
    }
    monkeypatch.setitem(entry["drive"].__globals__, "asyncio", SimpleNamespace(**public_async))
    assert entry["drive"](value) == 1
    assert loop.closed and not value.a_entered
    assert coroutines and coroutines[0].cr_frame is None


@pytest.mark.parametrize("failure", ["physical", "extra-task"])
def test_terminal_proof_precedes_success_even_when_held_rewrite_fails(
    entry: Any, context: Any, monkeypatch: Any, failure: str
) -> None:
    value, host, _, _ = context
    save = host.save
    foreign: list[Any] = []

    def persist(name: str, data: Any) -> None:
        if value.held:
            raise OSError("FAKE_HELD_REWRITE_FAILURE")
        save(name, data)

    async def restore() -> None:
        host.result["desktop_restored"] = True
        if failure == "physical":
            monkeypatch.setitem(entry["run"].__globals__, "physical_ready", lambda _host: False)
        else:
            foreign.append(asyncio.create_task(asyncio.Event().wait(), name="foreign-pending-fake"))

    async def scenario() -> None:
        # Isolate terminal ordering from transport/matrix timing. The complete
        # real journal/23-case flow is tested separately above.
        await host.start_supervision()
        value.a_entered = True
        for case in entry["H"]["CASES"]:
            host._monitor_attempted.add(case)
            host._monitors[case].started = True
        host._cases = [{"case": case} for case in entry["H"]["CASES"]]
        host.result.update(pg16_reader_verified=True, volumes_restored=True, journal_verified=True)
        monkeypatch.setitem(entry["H"]["V2"], "journal_from_disk", lambda _host: ((), "a" * 64))
        monkeypatch.setattr(host, "restore_desktop", restore)
        monkeypatch.setattr(host, "save", persist)
        loop = asyncio.get_running_loop()
        task = asyncio.current_task()
        assert task is not None
        timers: list[Any] = []
        end = loop.time() + 5.0

        def observe() -> None:
            if value.held or loop.time() >= end:
                task.cancel()
            else:
                timers.append(loop.call_later(0.01, observe))

        timers.append(loop.call_later(0.01, observe))
        try:
            # The entry is this root task. No supervising task is introduced
            # accidentally into the pending-task proof; only the injected
            # foreign task may be pending in the extra-task case.
            with pytest.raises(asyncio.CancelledError):
                await entry["finish"](value)
            contents = b"".join(path.read_bytes() for path in host.root.glob("*.json"))
            assert b"PG16_SHELL_READER_VERIFIED" not in contents
            assert b'"phase":"FINISHED"' not in contents
            assert value.held and not value.released
        finally:
            for timer in timers:
                timer.cancel()
            for extra in foreign:
                extra.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await extra

    run(scenario())


@pytest.mark.parametrize("foreign_enum", [False, True])
def test_delivery_reader_category_requires_its_own_enum(
    entry: Any, context: Any, foreign_enum: bool
) -> None:
    value, host, _, _ = context
    reader = host.pg["delivery"]["R"]
    error = reader["ReaderError"](reader["Code"].OUTPUT)
    if foreign_enum:
        error.category = host.reader["Code"].OUTPUT
    assert entry["diagnostic"](error, value) == (
        ("INTERNAL", "INTERNAL") if foreign_enum else ("OUTPUT", "READER")
    )
