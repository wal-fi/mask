"""T4 monitor/ownership fakes only. No native thread, process, Docker or clock sampling."""

import json
import runpy
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
TASK = "a" * 32


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_watchdog.py"))


class Mutex:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.acquired: list[float] = []
        self.releases = 0

    def acquire(self, *, timeout):
        self.acquired.append(timeout)
        return self.available

    def release(self):
        self.releases += 1


class Event:
    def __init__(self, ready: bool = False) -> None:
        self.ready = ready
        self.waits: list[float] = []

    def wait(self, timeout):
        self.waits.append(timeout)
        return self.ready

    def set(self):
        self.ready = True


def monitor(module: Any, tmp_path: Any) -> tuple[Any, Any, list[Any], list[Any]]:
    paths = [
        "w1_bootstrap_emergency.py",
        "w1_bootstrap_probe.py",
        "run_linux_as_probe.py",
        "w1_bootstrap_identity.py",
    ]
    raw = [(REPO / "docs/poc" / name).read_bytes() for name in paths]
    store = module["Store"](0.0)
    events: list[Any] = []
    aborts: list[Any] = []
    owner = module["Watchdog"](tmp_path, store, Mutex(), lambda: aborts.append(True), *raw)
    owner._write = lambda action, snapshot, category: events.append((action, snapshot, category))
    owner.ack = Event(True)
    return owner, store, events, aborts


def snapshot(module: Any, owner: Any, *, pid: bool = True, cid: bool = True) -> Any:
    policy = owner._policy
    intent = policy["Intent"](TASK, policy["Case"].NORMAL)
    return module["Snapshot"](
        TASK,
        "normal",
        intent.command,
        "c" * 64 if cid else None,
        123 if pid and cid else None,
        134375857978266391 if pid and cid else None,
    )


class Public:
    def __init__(
        self,
        owner: Any,
        record: Any,
        *,
        extra_label: bool = False,
        wrong_owner: bool = False,
        fail_cli: bool = False,
    ) -> None:
        self.begins = 0
        self.calls: list[str] = []
        self.present = True
        self.fail_cli = fail_cli
        path = REPO / "docs/poc/evidence/oracle9-w1-v2-run-20261027/probe-inspect-before.json"
        saved = json.loads(path.read_bytes())
        self.info = deepcopy(saved[0] if isinstance(saved, list) else saved)
        self.info.update(
            Id=record.cid,
            Name="/" + owner._policy["name_for"](record.task, owner._policy["Case"](record.case)),
            Image=owner._policy["IMAGE"],
        )
        self.info["Config"].update(
            Image=owner._policy["IMAGE"],
            Cmd=list(record.command),
            Labels=owner._policy["labels_for"](record.task),
            Entrypoint=owner._policy["ENTRY"],
        )
        self.info["State"].update(Running=True, Pid=4321)
        if extra_label:
            self.info["Config"]["Labels"]["desktop.docker.io/ports.scheme"] = "v2"
        if wrong_owner:
            self.info["Config"]["Labels"]["maskgw.task"] = "b" * 32

    def begin(self):
        self.begins += 1

    def invoke(self, action, target):
        self.calls.append(action.value)
        if action.value == "CLI_KILL":
            if self.fail_cli:
                raise RuntimeError("COMMAND")
            return b'{"status":"KILLED"}'
        if action.value == "CID_ABSENCE":
            return (target.cid.encode() + b"\n") if self.present else b""
        if action.value == "CID_INSPECT":
            return json.dumps([self.info]).encode()
        if action.value == "CID_KILL":
            self.info["State"].update(Running=False, Pid=0)
            return target.cid.encode() + b"\n"
        assert action.value == "CID_REMOVE"
        self.present = False
        return target.cid.encode() + b"\n"


@pytest.mark.parametrize("mode", ["normal", "extra-label", "source-missing", "cli-unknown"])
def test_cleanup_uses_captured_intent_and_never_emits_a_release(module, tmp_path, mode):
    owner, _, events, _ = monitor(module, tmp_path)
    record = snapshot(module, owner, pid=mode != "cli-unknown")
    public = Public(owner, record, extra_label=mode == "extra-label")
    owner._public = public

    def unreadable(*_args):
        raise RuntimeError("CHANNEL_PIN")

    owner._policy["channel_bytes"] = unreadable
    owner.emergency(record)
    assert not public.present and owner.cleanup_lock.releases == 1
    assert owner.metadata()["cid_absent"] and owner.metadata()["held"]
    assert not owner.metadata()["released"]
    assert "CID_REMOVE" in public.calls and public.calls[-1] == "CID_ABSENCE"
    assert bool("CLI_KILL" in public.calls) is (mode != "cli-unknown")
    assert events and not hasattr(owner, "ticket")


def test_watchdog_rechecks_absence_even_if_main_already_removed_cid(module, tmp_path):
    owner, _, _, _ = monitor(module, tmp_path)
    record = snapshot(module, owner)
    public = Public(owner, record)
    public.present = False
    owner._public = public
    owner.emergency(record)
    assert public.calls == ["CLI_KILL", "CID_ABSENCE"]
    assert owner.metadata()["cid_absent"] and not owner.metadata()["released"]


def test_wrong_ownership_never_runs_kill_or_remove(module, tmp_path):
    owner, _, _, _ = monitor(module, tmp_path)
    record = snapshot(module, owner)
    public = Public(owner, record, wrong_owner=True)
    owner._public = public
    with pytest.raises(RuntimeError):
        owner.emergency(record)
    assert "CID_KILL" not in public.calls and "CID_REMOVE" not in public.calls
    assert owner.cleanup_lock.releases == 1 and not owner.metadata()["released"]


def test_cleanup_lock_contention_never_runs_parallel_cid_actions(module, tmp_path):
    owner, _, _, _ = monitor(module, tmp_path)
    record = snapshot(module, owner)
    public = Public(owner, record)
    owner._public = public
    owner.cleanup_lock = Mutex(False)
    owner.emergency(record)
    assert public.calls == ["CLI_KILL"]
    assert owner.cleanup_lock.acquired == [1.0] and not owner.cleanup_lock.releases
    assert owner.metadata()["category"] == "CLEANUP_LOCK"


@pytest.mark.parametrize(
    "now,b_started,heartbeat,expected",
    [
        (16.0, None, 0.0, "HEARTBEAT"),
        (601.0, 0.0, 601.0, "DEADLINE"),
        (10.0, None, 10.0, None),
        (1.0, None, 2.0, "CLOCK"),
    ],
)
def test_trigger_before_a_and_after_b_has_closed_reasons(
    module, now, b_started, heartbeat, expected
):
    value = module["Observation"](heartbeat, b_started, None)
    assert module["reason"](value, now) == expected


@pytest.mark.parametrize("with_cid", [False, True])
def test_stale_heartbeat_requests_abort_then_only_own_external_cleanup(
    module, tmp_path, monkeypatch, with_cid
):
    owner, store, events, aborts = monitor(module, tmp_path)
    record = snapshot(module, owner, cid=with_cid)
    store.publish(record)
    public = Public(owner, snapshot(module, owner))
    owner._public = public
    owner.stop = Event(False)
    monkeypatch.setitem(
        module["Watchdog"].run.__globals__, "time", SimpleNamespace(monotonic=lambda: 16.0)
    )
    owner.run()
    assert owner.fired.is_set() and aborts == [True] and owner.ack.waits == [2.0]
    assert events and owner.metadata()["held"] and not owner.metadata()["released"]
    assert bool(public.calls) is with_cid


def test_pid_mismatch_does_not_progress_to_cid_mutation(module, tmp_path, monkeypatch):
    owner, store, _, _ = monitor(module, tmp_path)
    record = snapshot(module, owner)
    store.publish(record)
    public = Public(owner, record, fail_cli=True)
    owner._public = public
    owner.stop = Event(False)
    monkeypatch.setitem(
        module["Watchdog"].run.__globals__, "time", SimpleNamespace(monotonic=lambda: 16.0)
    )
    owner.run()
    assert public.calls == ["CLI_KILL"]
    assert owner.metadata()["category"] == "EMERGENCY_ERROR" and owner.metadata()["held"]


@pytest.mark.parametrize("failure", ["none", "start", "join", "alive"])
def test_native_thread_is_not_started_in_fakes_and_join_is_bounded(
    module, tmp_path, monkeypatch, failure
):
    owner, _, _, _ = monitor(module, tmp_path)
    joins = []

    class Thread:
        def __init__(self, *, target, name, daemon):
            assert callable(target) and name == "maskgw-t4-watchdog" and daemon is False

        def start(self):
            if failure == "start":
                raise RuntimeError("public-marker-must-not-escape")

        def join(self, *, timeout):
            joins.append(timeout)
            if failure in ("start", "join"):
                raise RuntimeError("public-marker-must-not-escape")

        def is_alive(self):
            return failure == "alive"

    monkeypatch.setitem(
        module["Watchdog"].start.__globals__, "threading", SimpleNamespace(Thread=Thread)
    )
    assert owner.start() is (failure != "start")
    assert owner.close() is (failure == "none")
    assert joins == [50.0] and not owner.metadata()["released"]
    if failure != "none":
        assert owner.metadata()["held"]


def test_store_publishes_only_frozen_plain_data(module, tmp_path):
    owner, store, _, _ = monitor(module, tmp_path)
    record = snapshot(module, owner)
    store.publish(record)
    old = store.read()
    store.pulse(1.0)
    store.arm_b(1.0)
    current = store.read()
    assert old.heartbeat == 0.0 and current.heartbeat == current.b_started == 1.0
    assert current.snapshot is record
    with pytest.raises(AttributeError):
        record.cid = "d" * 64
    with pytest.raises(RuntimeError):
        store.publish(SimpleNamespace(owner=object()))


@pytest.mark.parametrize(
    "field,value",
    [
        ("task", "../other"),
        ("case", "arbitrary"),
        ("command", ["-c", "mutable"]),
        ("cid", "short"),
        ("pid", True),
        ("filetime", 1.25),
    ],
)
def test_snapshot_cannot_smuggle_mutable_objects_or_imprecise_identity(module, field, value):
    data = {
        "task": TASK,
        "case": "normal",
        "command": ("-c", "public-code"),
        "cid": "c" * 64,
        "pid": 123,
        "filetime": 134375857978266391,
    }
    data[field] = value
    with pytest.raises(RuntimeError):
        module["Snapshot"](**data)


def test_monitor_error_fails_closed_without_external_actions(module, tmp_path, monkeypatch):
    owner, _, _, aborts = monitor(module, tmp_path)
    public = Public(owner, snapshot(module, owner))
    owner._public = public
    owner.stop = Event(False)
    monkeypatch.setitem(
        module["Watchdog"].run.__globals__, "time", SimpleNamespace(monotonic=lambda: float("nan"))
    )
    owner.run()
    assert owner.fired.is_set() and owner.metadata()["held"]
    assert owner.metadata()["category"] == "MONITOR_ERROR"
    assert aborts == [True] and not public.calls
