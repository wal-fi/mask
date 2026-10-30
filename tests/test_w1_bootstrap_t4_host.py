"""Binding fakes only: no Docker, native process, monitor thread or clock sampler."""

import asyncio
import hashlib
import json
import runpy
import threading
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
TASK = "a" * 32


def encode(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_t4_host.py"))


class Engine:
    def __init__(self, host: Any) -> None:
        self.host = host
        self.rows: dict[str, Any] = {}
        self.events: list[Any] = []
        self.next_id = 0
        self.fail_create = False
        self.fail_absence = False

    def row(self, case: Any, cid: str) -> Any:
        path = REPO / "docs/poc/evidence/oracle9-w1-v2-run-20261027/probe-inspect-before.json"
        old = json.loads(path.read_bytes())
        value = deepcopy(old[0] if isinstance(old, list) else old)
        policy = self.host.t4["policy"]
        value.update(Id=cid, Name="/" + policy["name_for"](TASK, case), Image=policy["IMAGE"])
        value["Config"].update(
            Image=policy["IMAGE"],
            Labels=policy["labels_for"](TASK),
            Cmd=list(self.host._intents[case.value].command),
            OpenStdin=True,
            StdinOnce=False,
            User="70:70" if case.value == "retain" else "10001:10001",
        )
        value["HostConfig"].update(Memory=134217728, MemorySwap=134217728, PidsLimit=8, Tmpfs={})
        value["State"].update(Running=False, Pid=0)
        return value

    async def cli(self, label: str, *args: Any, **kw: Any) -> Any:  # noqa: PLR0911 - closed fake CLI inventory
        self.events.append((label, args, kw))
        action = args[0]
        if action == "create":
            if self.fail_create:
                return 1, b""
            name = args[args.index("--name") + 1]
            policy = self.host.t4["policy"]
            case = next(c for c in policy["Case"] if policy["name_for"](TASK, c) == name)
            self.next_id += 1
            cid = format(self.next_id, "064x")
            self.rows[cid] = self.row(case, cid)
            return 0, cid.encode() + b"\n"
        if action == "inspect":
            return (0, encode([self.rows[args[-1]]])) if args[-1] in self.rows else (1, b"missing")
        if action == "kill":
            self.rows[args[-1]]["State"].update(Running=False, Pid=0)
            return 0, args[-1].encode() + b"\n"
        if action == "rm":
            del self.rows[args[-1]]
            return 0, args[-1].encode() + b"\n"
        assert action == "ps"
        if self.fail_absence:
            return 1, b""
        rows = list(self.rows)
        if "--filter" in args:
            rows = [cid for cid in rows if "id=" + cid == args[-1]]
        return 0, ("\n".join(rows) + ("\n" if rows else "")).encode()


class Owner:
    """Fake resources. Real channel receipt/value types and real policy oracles remain."""

    def __init__(self, host: Any, engine: Engine, target: Any) -> None:
        self.host, self.engine, self.target = host, engine, target
        self._process: Any = None
        self._tasks: dict[str, Any] = {}
        self.ticket: Any = None
        self.released = False
        self.delivery = "NOT_SENT"
        self.fail_start = False
        self.no_ticket = False
        self.case = host._store.read().snapshot.case

    async def start(self) -> None:
        self.engine.events.append(("start", self.case))
        self._process = SimpleNamespace(pid=123)
        self.engine.rows[self.target.cid]["State"].update(Running=True, Pid=456)
        self._tasks["spawn"] = asyncio.get_running_loop().create_future()
        self._tasks["spawn"].set_result(self._process)
        if self.case == "cancel-start":
            await asyncio.sleep(0.01)
        if self.fail_start:
            raise RuntimeError("START_FAILED")

    async def await_ready(self) -> None:
        self.engine.events.append(("ready", self.case))
        if self.case == "bad-ready":
            raise self.host.t4["channel"]["BootstrapError"](self.host.t4["channel"]["Fault"].READY)

    async def send_seed(self, seed: Any) -> None:
        assert seed.reveal_frame().endswith(b"SEEDEND\n")
        self.delivery = "SENT"
        if self.case == "flood":
            raise self.host.t4["channel"]["BootstrapError"](
                self.host.t4["channel"]["Fault"].STDOUT_LIMIT
            )

    def retain(self) -> None:
        assert self.case == "retain"

    async def drain(self) -> Any:
        if self.case == "retain":
            await asyncio.sleep(30)
        value: dict[str, Any] = {
            "kind": "MASKGW_T4_CANARY_V1",
            "case": self.case,
            "bytes": 16384,
            "equality": True,
            "eof_observed": False,
            "observation_ms": 1500,
            "uid": 10001,
            "pid": 1,
        }
        if self.case == "reader-negative":
            value["categories"] = ["FRAME"] * 4
        self.engine.rows[self.target.cid]["State"].update(Running=False, Pid=0)
        return self.host.t4["channel"]["PrivateOutput"](encode(value))

    async def quiesce(self) -> Any:
        self.engine.events.append(("quiesce", self.case))
        if self.no_ticket:
            return None
        if self.ticket is None:
            self.ticket = self.host.t4["channel"]["Quiesced"](
                self.target.cid, "f" * 32, self.host._store.read().heartbeat
            )
        return self.ticket

    async def close(self, absent: Any) -> bool:
        self.engine.events.append(("close", self.case))
        assert absent.ticket is self.ticket and self.target.cid not in self.engine.rows
        self.released = True
        return True

    def metadata(self) -> Any:
        return {
            "released": self.released,
            "seed_delivery": self.delivery,
            "retained_stdout_bytes": 0,
        }

    def assert_released(self) -> None:
        assert self.released


@pytest.fixture
def bound(module: Any, tmp_path: Any) -> Any:
    state: dict[str, Any] = {
        "task": TASK,
        "pins": dict(module["R"]["LIBRARIES"].values()),
        "host_sha256": hashlib.sha256(Path(module["__file__"]).read_bytes()).hexdigest(),
    }
    host = module["Host"](tmp_path, state)
    state["create_measurements"] = {
        key: host.t4["policy"]["create_args"](str(module["R"]["CLI"]), intent)[1]
        for key, intent in host._intents.items()
    }
    engine = Engine(host)
    host.cli = engine.cli
    host.pins = lambda **_kw: None
    host._store = host.t4["watch"]["Store"](0.0)
    host._cleanup_lock = threading.Lock()  # no thread starts

    def capture(process: Any) -> Any:
        engine.events.append(("capture", None if process is None else process.pid))
        return None if process is None else host.t4["identity"]["Birth"](123, 134375857978266391)

    host.t4["identity"]["capture"] = capture
    host.t4["channel"]["ManagedBootstrap"] = lambda target: Owner(host, engine, target)
    return host, engine


def test_only_twelve_declared_overrides_and_no_old_main(module):
    base, cls = module["BaseHost"], module["Host"]
    overrides = {key for key in cls.__dict__ if callable(getattr(base, key, None))}
    assert overrides == {
        "__init__",
        "pins",
        "preflight",
        "create_own",
        "inspect_own",
        "perform_b",
        "watchdog",
        "cleanup_owned",
        "cli",
        "run_own",
        "check_attestation",
        "checkpoint",
    }
    for name in ("save", "write_new", "record_intents", "start_cycle", "sample", "restore_desktop"):
        assert getattr(cls, name) is getattr(base, name)
    assert "main" not in module


def test_all_seven_cases_use_only_bound_transport_and_release(bound):
    host, engine = bound

    async def run() -> Any:
        host.cycle = SimpleNamespace(phase=host.libs["core"]["Phase"].B_CONSUMED)
        await host.perform_b()
        await host.cleanup_owned()
        host._monitor_joined = True
        host.assert_released()

    asyncio.run(run())
    assert host.result["t4_verified"] is True
    assert host.result["owned_cleanup"] is True and not engine.rows
    assert len(host._owners) == len(host._cases) == 7
    assert all(record["removed"] for record in host.records)
    assert host._store.read().snapshot is None
    assert all(
        event[1][0] in ("create", "inspect", "kill", "rm", "ps")
        for event in engine.events
        if len(event) == 3
    )
    for index, event in enumerate(engine.events):
        if event[0] == "ready":
            assert engine.events[index - 1] == ("capture", 123)
    assert json.loads((host.root / "normal-report.json").read_bytes())["eof_observed"] is False
    assert (host.root / "retain-cli-reaped-cid-alive.json").is_file()


@pytest.mark.parametrize("action", ["cp", "commit", "pull", "build", "exec", "run"])
def test_old_paths_cannot_invoke_cli(module, bound, action):
    host, _ = bound
    with pytest.raises(RuntimeError, match="CLI_SCOPE"):
        asyncio.run(module["Host"].cli(host, "forbidden", action, "x"))


def test_old_transport_install_and_watchdog_always_refuse(bound):
    host, _ = bound
    with pytest.raises(RuntimeError, match="OLD_TRANSPORT"):
        asyncio.run(host.run_own({}))
    with pytest.raises(RuntimeError, match="INSTALL"):
        host.check_attestation({})
    with pytest.raises(RuntimeError, match="OLD_WATCHDOG"):
        host.watchdog()


def test_cli_calls_original_not_v2_commit_hook(module, bound):
    host, _ = bound
    calls = []

    async def invoke(*args, **kwargs):
        calls.append((args, kwargs))
        return 0, b""

    host.invoke = invoke
    assert asyncio.run(module["Host"].cli(host, "safe", "ps", "-aq")) == (0, b"")
    assert calls[0][0][1][1:3] == ["--context", "desktop-linux"]
    assert not host.commit_intended and host.commit_id is None


def prepare_owner(host: Any, engine: Engine, case_name: str = "normal") -> Any:
    async def run() -> Any:
        case = host.t4["policy"]["Case"](case_name)
        record = await host.create_own(case)
        target = host.t4["channel"]["Target"](
            record["cid"],
            TASK,
            record["image"],
            host.t4["policy"]["SOURCE_SHA"],
            host.t4["channel"]["Role"].PG
            if case_name == "retain"
            else host.t4["channel"]["Role"].CONTROLLER,
        )
        owner = Owner(host, engine, target)
        host._owners[case_name] = owner
        return record, owner

    return asyncio.run(run())


def test_emergency_removal_requires_fresh_post_ticket_absence(bound):
    host, engine = bound
    record, owner = prepare_owner(host, engine, "retain")
    del engine.rows[record["cid"]]  # external remover wins before owner ticket
    engine.events.clear()
    asyncio.run(host._collect(record))
    assert owner.released
    assert [row[0] for row in engine.events] == [
        "quiesce",
        "capture",
        "inspect-cleanup-retain",
        "absent-after-retain",
        "close",
    ]
    assert not (host.root / "retain-cli-reaped-cid-alive.json").exists()


def test_failed_inspect_is_not_absence(bound):
    host, engine = bound
    record, owner = prepare_owner(host, engine)
    del engine.rows[record["cid"]]
    engine.fail_absence = True
    with pytest.raises(RuntimeError, match="ABSENCE"):
        asyncio.run(host._collect(record))
    assert not owner.released and not record["removed"]


def test_unquiesced_owner_forbids_all_cleanup_commands(bound):
    host, engine = bound
    record, owner = prepare_owner(host, engine)
    owner.no_ticket = True
    engine.events.clear()
    with pytest.raises(RuntimeError, match="OWNER_HELD"):
        asyncio.run(host._collect(record))
    assert not any(len(event) == 3 for event in engine.events)
    assert record["cid"] in engine.rows and not owner.released


def test_create_uncertain_never_released_by_empty_inventory(bound):
    host, engine = bound
    engine.fail_create = True

    async def run() -> Any:
        with pytest.raises(RuntimeError, match="CREATE_EXIT"):
            await host.create_own(host.t4["policy"]["Case"].NORMAL)
        await host.cleanup_owned()

    asyncio.run(run())
    assert not engine.rows and host.result["owned_cleanup"] is False
    assert host.records[0]["create_uncertain"] is True
    assert [event[0] for event in engine.events] == ["create-normal"]


def test_profile_drift_and_extra_label_do_not_block_owned_cleanup(bound):
    host, engine = bound
    record, owner = prepare_owner(host, engine)
    row = engine.rows[record["cid"]]
    row["Config"]["Labels"]["desktop.extra"] = "public"
    row["HostConfig"]["Memory"] = 1
    host.t4["policy"]["channel_bytes"] = lambda: (_ for _ in ()).throw(RuntimeError("SOURCE"))
    asyncio.run(host._collect(record))
    assert owner.released and not engine.rows


def test_wrong_ownership_never_killed_or_removed(bound):
    host, engine = bound
    record, owner = prepare_owner(host, engine)
    engine.rows[record["cid"]]["Config"]["Labels"]["maskgw.task"] = "b" * 32
    engine.events.clear()
    with pytest.raises(RuntimeError, match="OWNERSHIP"):
        asyncio.run(host._collect(record))
    assert not owner.released
    assert [event[1][0] for event in engine.events if len(event) == 3] == ["inspect"]


def test_removed_record_still_closes_unreleased_owner(bound):
    host, engine = bound
    record, owner = prepare_owner(host, engine)
    del engine.rows[record["cid"]]
    record["removed"] = True
    asyncio.run(host.cleanup_owned())
    assert owner.released and host.result["owned_cleanup"] is True


def test_start_failure_publishes_original_handle_before_other_await(bound):
    host, engine = bound

    def owner(target):
        value = Owner(host, engine, target)
        value.fail_start = True
        return value

    host.t4["channel"]["ManagedBootstrap"] = owner
    with pytest.raises(RuntimeError, match="START_FAILED"):
        asyncio.run(host._case(host.t4["policy"]["Case"].NORMAL))
    assert engine.events[-2:] == [("start", "normal"), ("capture", 123)]
    snapshot = host._store.read().snapshot
    assert snapshot.pid == 123 and snapshot.filetime == 134375857978266391


def test_join_failure_does_not_read_mutating_watchdog_metadata(bound):
    host, _ = bound

    def forbidden():
        raise AssertionError("unjoined metadata read")

    host._monitor = SimpleNamespace(close=lambda: False, metadata=forbidden)
    asyncio.run(host.stop_supervision())
    assert host.result["watchdog"] == {"held": True, "category": "THREAD_JOIN_UNPROVEN"}
    with pytest.raises(RuntimeError, match="HOST_HELD"):
        host.assert_released()


def test_task_creation_failure_closes_coroutine(bound, monkeypatch):
    host, _ = bound

    async def run() -> Any:
        async def unsubmitted() -> None:
            raise AssertionError("not submitted")

        pending: Any = unsubmitted()

        def fail(*_args, **_kwargs):
            raise RuntimeError("private-error")

        monkeypatch.setattr(asyncio, "create_task", fail)
        with pytest.raises(RuntimeError, match=r"^TASK_START$") as caught:
            host._task(pending, "fake")
        assert pending.cr_frame is None and caught.value.__context__ is None
        assert host._host_tasks == []

    asyncio.run(run())


@pytest.mark.parametrize("args", [("image", "rm", "x"), ("desktop", "restart"), ("ps",)])
def test_cli_inventory_is_restrictive(module, bound, args):
    host, _ = bound
    calls = []

    async def invoke(*values, **_kwargs):
        calls.append(values)
        return 0, b""

    host.invoke = invoke
    if args == ("ps",):
        asyncio.run(module["Host"].cli(host, "safe", *args))
        assert len(calls) == 1
    else:
        with pytest.raises(RuntimeError, match="CLI_SCOPE"):
            asyncio.run(module["Host"].cli(host, "safe", *args))
        assert calls == []


def test_cleanup_uses_one_absolute_budget_with_calibrated_remove(module, bound, monkeypatch):
    host, engine = bound
    record, owner = prepare_owner(host, engine, "retain")
    engine.rows[record["cid"]]["State"].update(Running=True, Pid=456)
    now = [100.0]
    monkeypatch.setitem(
        module["Host"]._collect.__globals__, "time", SimpleNamespace(monotonic=lambda: now[0])
    )
    original = host.cli
    spent = []

    async def timed(label, *args, **kw):
        spent.append(kw["timeout"])
        now[0] += kw["timeout"]  # simulated command consumes its entire cap
        return await original(label, *args, **kw)

    host.cli = timed
    asyncio.run(host._collect(record, oracle=True))
    assert spent == [3, 4, 3, 8, 3] and now[0] == 121.0
    assert owner.released


def test_late_command_does_not_renew_cleanup_budget(module, bound, monkeypatch):
    host, engine = bound
    record, owner = prepare_owner(host, engine)
    engine.rows[record["cid"]]["State"].update(Running=True, Pid=456)
    now = [100.0]
    monkeypatch.setitem(
        module["Host"]._collect.__globals__, "time", SimpleNamespace(monotonic=lambda: now[0])
    )
    original = host.cli

    async def late(label, *args, **kw):
        result = await original(label, *args, **kw)
        now[0] += 23.0  # delayed OS completion is not a fresh allowance
        return result

    host.cli = late
    with pytest.raises(RuntimeError, match="CLEANUP_DEADLINE"):
        asyncio.run(host._collect(record))
    assert not owner.released and record["cid"] in engine.rows
    assert not any(event[1][0] in ("kill", "rm") for event in engine.events if len(event) == 3)


def test_main_abort_signal_cancels_foreground_then_can_collect(bound):
    host, engine = bound

    async def run() -> Any:
        host._monitor = SimpleNamespace(ack=threading.Event())

        async def pending() -> None:
            await asyncio.Event().wait()

        task = asyncio.create_task(host.foreground(pending()))
        await asyncio.sleep(0)
        host._abort_foreground()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert host._monitor.ack.is_set()
        assert all(owned.done() for owned in host._host_tasks)

    asyncio.run(run())
    assert not engine.rows


def test_b_clock_armed_before_inherited_checkpoint(module, bound, monkeypatch):
    host, _ = bound
    events = []

    async def checkpoint(self, action):
        assert self._store.read().b_started is not None
        events.append(action)

    monkeypatch.setattr(module["BaseHost"], "checkpoint", checkpoint)
    asyncio.run(host.checkpoint("B"))
    assert events == ["B"]


def test_cleanup_pins_use_captured_sources_but_external_pins_still_required(
    module, bound, monkeypatch
):
    host, _ = bound
    reads = []

    def pinned(path, _digest, *_args):
        reads.append(path)
        if str(path).startswith(str(REPO)):
            raise RuntimeError("MUTATED_LIVE_SOURCE")
        return b"public"

    monkeypatch.setitem(module["R"], "pinned", pinned)
    monkeypatch.setitem(
        module["R"],
        "regular",
        lambda *_args: (
            b'{"Endpoints":{"docker":{"Host":"npipe:////./pipe/dockerDesktopLinuxEngine"}}}'
        ),
    )
    module["Host"].pins(host, cleanup=True)
    assert set(reads) == set(module["R"]["EXTERNAL_PINS"])
    with pytest.raises(RuntimeError, match="MUTATED_LIVE_SOURCE"):
        module["Host"].pins(host)


def test_intent_is_durable_and_complete_before_create(bound):
    host, engine = bound
    original = host.cli

    async def checked(label, *args, **kwargs):
        if args[0] == "create":
            intent = json.loads((host.root / "normal-intent.json").read_bytes())
            assert intent["cid"] is None and intent["create_uncertain"] is True
            assert intent["command"] == list(host._intents["normal"].command)
        return await original(label, *args, **kwargs)

    host.cli = checked
    asyncio.run(host.create_own(host.t4["policy"]["Case"].NORMAL))
    assert len(engine.rows) == 1


def test_flood_fault_after_send_is_observed_without_waiting_for_exit(bound):
    host, engine = bound

    class DelayedFlood(Owner):
        async def send_seed(self, seed: Any) -> None:
            assert seed.reveal_frame()
            self.delivery = "SENT"

            async def flood() -> None:
                await asyncio.sleep(0.01)
                self.fault = host.t4["channel"]["Fault"].STDOUT_LIMIT

            host._task(flood(), "fake-flood-pump")

        async def drain(self) -> Any:
            raise AssertionError("infinite flood must not wait for process exit")

    def owner(target):
        value = DelayedFlood(host, engine, target)
        value.fault = None
        return value

    host.t4["channel"]["ManagedBootstrap"] = owner
    asyncio.run(host._case(host.t4["policy"]["Case"].FLOOD))
    assert host._owners["flood"].released and not engine.rows


def test_report_observation_plus_delayed_cli_exit_has_explicit_margin(bound):
    host, engine = bound

    class DelayedReport(Owner):
        async def drain(self) -> Any:
            # Represents 1.5s of EOF observation plus 0.8s CLI exit latency.
            # No actual Docker latency is inferred from this scheduler test.
            await asyncio.sleep(2.3)
            return await super().drain()

    host.t4["channel"]["ManagedBootstrap"] = lambda target: DelayedReport(host, engine, target)
    asyncio.run(host._case(host.t4["policy"]["Case"].NORMAL))
    assert host._owners["normal"].released and not engine.rows


def test_retain_missing_cid_fails_oracle_but_final_cleanup_releases(bound):
    host, engine = bound

    class MissingRetain(Owner):
        async def quiesce(self) -> Any:
            ticket = await super().quiesce()
            engine.rows.pop(self.target.cid, None)
            return ticket

    host.t4["channel"]["ManagedBootstrap"] = lambda target: MissingRetain(host, engine, target)

    async def run() -> None:
        try:
            with pytest.raises(RuntimeError, match="CLI_KILL_DID_NOT_LEAVE_CID_ALIVE"):
                await host._case(host.t4["policy"]["Case"].RETAIN)
        finally:
            await host.cleanup_owned()
        assert host._owners["retain"].released and host.result["owned_cleanup"] is True
        assert host._cases == []

    asyncio.run(run())


def test_recorded_container_has_three_labels_while_image_has_four(bound):
    host, engine = bound
    image = json.loads(
        (REPO / "docs/poc/evidence/oracle9-w1-v2-run-20261027/candidate-image.json").read_bytes()
    )[0]
    old = json.loads(
        (
            REPO / "docs/poc/evidence/oracle9-w1-v2-run-20261027/probe-inspect-before.json"
        ).read_bytes()
    )
    observed = old[0] if isinstance(old, list) else old
    assert image["Id"] == observed["Image"] == host.t4["policy"]["IMAGE"]
    assert set(image["Config"]["Labels"]) == set(observed["Config"]["Labels"]) | {
        "desktop.docker.io/ports.scheme"
    }
    assert set(observed["Config"]["Labels"]) == set(host.t4["policy"]["labels_for"](TASK))
    asyncio.run(host._case(host.t4["policy"]["Case"].NORMAL))
    assert host._owners["normal"].released and not engine.rows


@pytest.mark.parametrize("value", ["v2", "other"])
def test_container_fourth_label_refused_without_weakening_cleanup(bound, value):
    host, engine = bound
    record, owner = prepare_owner(host, engine)
    info = engine.rows[record["cid"]]
    labels = info["Config"]["Labels"]
    labels["desktop.docker.io/ports.scheme"] = value
    raw = encode([info])
    with pytest.raises(RuntimeError, match="CONFIG"):
        host._owned_inspect(record, raw, False)
    assert host._owned_inspect(record, raw, True) == info
    asyncio.run(host._collect(record))
    assert owner.released
