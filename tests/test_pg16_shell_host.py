"""Closed coordinator fakes. No Docker, PowerShell, shell or native watchdog."""

import asyncio
import hashlib
import json
import os
import runpy
import threading
import time
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_pg16_public_profile import image_info

REPO = Path(__file__).resolve().parents[1]
TASK = "a" * 32
OTHER = "third_party_project_data"


def encoded(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


class Monitor:
    def __init__(self, engine: Any, root: Any, store: Any, callback: Any) -> None:
        self.engine, self.root, self.store, self.callback = engine, root, store, callback
        self.fired, self.ack = threading.Event(), threading.Event()
        self.started, self.joined, self.held = False, False, False
        self.join_ok, self.fire_at_close = True, False

    def start(self) -> bool:
        assert not self.started
        assert len(self.engine.host._monitors) == 23
        self.started = True
        self.engine.events.append(("MONITOR_START", self.root.name))
        return True

    def check_snapshot(self, snapshot: Any) -> None:
        assert snapshot is not None
        profile = self.engine.host.profile
        assert snapshot.command == profile["_capture"](TASK, profile["R"]["Case"](snapshot.case))[1]

    def close(self) -> bool:
        assert self.started
        self.engine.events.append(("MONITOR_CLOSE", self.root.name))
        if self.fire_at_close:
            self.fired.set()
            self.callback()
        self.joined = self.join_ok
        self.held = not self.joined
        return self.joined

    def metadata(self) -> Any:
        return {
            "fired": self.fired.is_set(),
            "held": self.held,
            "thread_joined": self.joined,
            "released": False,
        }


class Owner:
    def __init__(self, engine: Any, task: str, cid: str, case: str) -> None:
        self.engine, self.case = engine, case
        prototype = engine.real_owner(task, cid, case)
        self.target, self.wrapper = prototype.target, prototype.wrapper
        self.wrapper_sha256, self.delivery = prototype.wrapper_sha256, prototype.delivery
        self._process: Any = None
        self.released, self.ticket = False, None

    async def start(self) -> None:
        host = self.engine.host
        assert host._owners[self.case] is self
        if self.engine.owner_start_checks_budget:
            host._budget()
        self.engine.events.append(("OWNER_START", self.case))
        self._process = SimpleNamespace(pid=100 + host.module_cases.index(self.case))
        self.engine.rows[self.target.cid]["State"].update(Running=True, Pid=456)
        if self.engine.fail_start:
            raise RuntimeError("FAKE_START")

    async def send_vector(self) -> None:
        self.engine.events.append(("OWNER_SEND", self.case))
        if self.engine.cancel_send:
            raise asyncio.CancelledError

    async def drain(self) -> Any:
        self.engine.events.append(("OWNER_DRAIN", self.case))
        reader = self.engine.host.reader
        selected = reader["Case"](self.case)
        vector = reader["vector"](selected)
        code = 0 if vector.fault is None else 42
        raw = (
            encoded(reader["expected_report"](TASK, selected))
            if not code
            else f"fault={vector.fault.value}\n".encode("ascii")
        )
        self.engine.rows[self.target.cid]["State"].update(
            Running=False, Pid=0, ExitCode=code + self.engine.exit_delta
        )
        if self.engine.bad_report:
            raw = b"fault=WRONG\n"
        if self.engine.fail_drain:
            raise RuntimeError("FAKE_IO_AFTER_PREFIX")
        return SimpleNamespace(
            returncode=code,
            stdout_bytes=len(self.target.ready_line()) + len(raw),
            report_bytes=len(raw),
            output=raw,
        )

    async def quiesce(self) -> Any:
        self.engine.events.append(("OWNER_QUIESCE", self.case))
        if self.engine.no_ticket:
            return None
        if self.ticket is None:
            self.ticket = self.engine.host.channel["Quiesced"](
                self.target.cid, "f" * 32, time.monotonic()
            )
        return self.ticket

    async def close(self, absent: Any) -> bool:
        assert absent.ticket is self.ticket
        assert self.target.cid not in self.engine.rows
        assert self.engine.host.result["volumes_restored"] is True
        self.engine.events.append(("OWNER_CLOSE", self.case))
        self.released = not self.engine.owner_held
        return self.released

    def metadata(self) -> Any:
        return {"released": self.released}

    def assert_released(self) -> None:
        assert self.released


class Engine:
    def __init__(self, module: Any, host: Any) -> None:
        self.module, self.host = module, host
        self.rows: dict[str, Any] = {}
        self.volumes = {OTHER}
        self.events: list[Any] = []
        self.real_owner = host.pg["delivery"]["PublicDeliveryOwner"]
        self.real_monitor = host.pg["watch"]["Watchdog"]
        self.create_code, self.rm_code, self.exit_delta = 0, 0, 0
        self.fail_start = self.cancel_send = self.fail_drain = False
        self.no_ticket = self.owner_held = self.bad_report = False
        self.mounts: Any = []
        self.leftover = False
        self.extra: dict[str, Any] = {}
        self.fail_transport = False
        self.owner_start_checks_budget = True

    async def invoke(self, label: str, args: Any, *_args: Any, **_kwargs: Any) -> Any:  # noqa: PLR0911 - fixed fake inventory
        assert args[1:3] == ["--context", "desktop-linux"] or tuple(args[1:3]) == (
            "--context",
            "desktop-linux",
        )
        args = tuple(args[3:])
        self.events.append((label, args))
        if self.fail_transport:
            raise RuntimeError("FAKE_TRANSPORT")
        if args[0] == "version":
            return 0, encoded({"Client": {"Version": "29.7.2", "ProxyPassword": "private-marker"}})
        if args[0] == "info":
            return 0, encoded(
                {
                    "OSType": "linux",
                    "Architecture": "x86_64",
                    "CgroupVersion": "2",
                    "KernelVersion": self.module["R"]["KERNEL"],
                    "MemTotal": 4 * 1024**3,
                    "Driver": "overlayfs",
                    "ServerVersion": "29.7.2",
                    "ProxyPassword": "private-marker",
                    **self.extra,
                }
            )
        if args[0] == "image":
            return 0, encoded([image_info(self.host.profile["P"])])
        if args == ("volume", "ls", "-q"):
            return 0, ("\n".join(sorted(self.volumes)) + "\n").encode("ascii")
        if args[0] == "create":
            case = self.host._active_case
            assert (self.host.root / (self.host._stem(case) + "-intent.json")).is_file()
            assert self.host._stores[case].read().snapshot.cid is None
            assert case in self.host._create_invoked
            assert not self.rows
            cid = format(len(self.host.records), "064x")
            fixtures = runpy.run_path(str(REPO / "tests/test_pg16_shell_profile.py"))
            _, _, row = fixtures["bound"].__wrapped__(self.host.profile)
            row = deepcopy(row)
            intent = self.host._intents[case]
            row.update(Id=cid, Name="/" + intent.name, Mounts=deepcopy(self.mounts))
            row["Config"].update(Cmd=list(intent.command), Labels=dict(intent.labels))
            row["State"] = {
                "Running": False,
                "Pid": 0,
                "OOMKilled": False,
                "Dead": False,
                "ExitCode": 0,
            }
            self.rows[cid] = row
            if type(self.mounts) is list:
                self.volumes.update(
                    item["Name"] for item in self.mounts if item.get("Type") == "volume"
                )
            return self.create_code, cid.encode("ascii") + b"\n"
        if args[0] == "inspect":
            row = self.rows.get(args[-1])
            return (0, encoded([row])) if row is not None else (1, b"")
        if args[0] == "kill":
            assert self.host._kill_approved is None
            self.rows[args[-1]]["State"].update(Running=False, Pid=0)
            return 0, args[-1].encode("ascii") + b"\n"
        if args[0] == "rm":
            assert self.host._remove_approved is None
            decision = sorted(self.host.root.glob("volume-decision-*.json"))[-1]
            assert OTHER.encode() not in decision.read_bytes()
            assert json.loads(decision.read_bytes())["cid"] == args[-1]
            if self.rm_code:
                return self.rm_code, b""
            row = self.rows.pop(args[-1])
            if "--volumes" in args and not self.leftover:
                self.volumes.difference_update(
                    item["Name"]
                    for item in row["Mounts"]
                    if item.get("Type") == "volume" and len(item["Name"]) == 64
                )
            return 0, args[-1].encode("ascii") + b"\n"
        assert args[0] == "ps"
        selected = args[-1][3:] if "--filter" in args else None
        values = [cid for cid in self.rows if selected is None or cid == selected]
        return 0, ("\n".join(values) + ("\n" if values else "")).encode("ascii")


@pytest.fixture
def bound(tmp_path: Any, monkeypatch: Any) -> Any:
    module = runpy.run_path(str(REPO / "docs/poc/pg16_shell_host.py"))
    profile = runpy.run_path(str(REPO / "docs/poc/pg16_shell_profile.py"))
    delivery = runpy.run_path(str(REPO / "docs/poc/pg16_shell_delivery.py"))
    state = {
        "task": TASK,
        "pins": dict(module["R"]["LIBRARIES"].values()),
        "host_sha256": hashlib.sha256(Path(module["__file__"]).read_bytes()).hexdigest(),
        "create_measurements": {
            case: profile["blueprint"](TASK, profile["R"]["Case"](case))[1]
            for case in module["CASES"]
        },
        "delivery_plan": {
            case: asdict(delivery["delivery_for"](case)[1]) for case in module["CASES"]
        },
    }
    host = module["Host"](tmp_path, state)
    host.module_cases = module["CASES"]
    engine = Engine(module, host)

    async def transport(label: str, *args: Any, **kwargs: Any) -> Any:
        return await engine.invoke(label, *args, **kwargs)

    monkeypatch.setattr(host, "_bounded", transport)
    monkeypatch.setattr(host, "pins", lambda **_kwargs: None)
    monkeypatch.setitem(
        host.pg["delivery"], "PublicDeliveryOwner", lambda *args: Owner(engine, *args)
    )
    monkeypatch.setitem(host.pg["identity"], "capture", lambda _process: None)
    monkeypatch.setitem(
        host.pg["watch"],
        "Watchdog",
        lambda root, store, _lock, callback, *_args: Monitor(engine, root, store, callback),
    )
    return module, host, engine


async def prepare(host: Any) -> None:
    await host.start_supervision()
    await host.preflight()
    host._b_started = time.monotonic()
    for store in host._stores.values():
        store.arm_b(host._b_started)
    host.cycle = SimpleNamespace(phase=host.libs["core"]["Phase"].B_CONSUMED)


async def finish(host: Any) -> None:
    await host.cleanup_owned()
    await host.stop_supervision()
    host.assert_released()


def run(coroutine: Any) -> Any:
    # Independent guard is a real auxiliary timer, not a native lab watchdog.
    guard = threading.Timer(40.0, lambda: os._exit(91))
    guard.daemon = True
    guard.start()
    try:
        return asyncio.run(coroutine)
    finally:
        guard.cancel()
        guard.join()


def test_complete_closed23_matrix_orders_release_join_and_next_create(bound: Any) -> None:
    module, host, engine = bound

    async def scenario() -> None:
        await prepare(host)
        stamp = host._b_started
        await host.perform_b()
        await finish(host)
        assert all(s.read().b_started == stamp for s in host._stores.values())

    run(scenario())
    assert host.result["pg16_reader_verified"] is True
    assert len(host._cases) == len(host._monitor_joined) == 23
    assert not engine.rows and engine.volumes == {OTHER}
    assert len(list(host.root.glob("case-*-intent.json"))) == 23
    assert len(list(host.root.glob("case-*-report.json"))) == 23
    assert len(list(host.root.glob("watch-*"))) == 23
    assert sum(row["returncode"] == 42 for row in host._cases) == 19
    for row in host._cases:
        fault = host.reader["vector"](host.reader["Case"](row["case"])).fault
        assert row["report_category"] == (None if fault is None else fault.value)
    assert sum(row["report_category"] == "HEADER" for row in host._cases) == 9
    assert sum(row["report_category"] == "DEADLINE" for row in host._cases) == 3
    assert sum(row["delivery"]["mode"] == "HEADER_PREFIX" for row in host._cases) == 9
    assert all(owner.released for owner in host._owners.values())
    for index, case in enumerate(module["CASES"]):
        close = engine.events.index(("OWNER_CLOSE", case))
        join = engine.events.index(("MONITOR_CLOSE", "watch-" + str(index + 1).zfill(2)))
        assert close < join
        if index + 1 < 23:
            assert join < engine.events.index(
                (
                    "create-" + module["CASES"][index + 1],
                    host._blueprints[module["CASES"][index + 1]][0],
                )
            )
    assert b"private-marker" not in b"".join(path.read_bytes() for path in host.root.glob("*.json"))


@pytest.mark.parametrize(
    "failure", ["fail_start", "cancel_send", "fail_drain", "bad_report", "exit_delta"]
)
def test_failed_case_never_counts_or_starts_next_and_cleanup_releases(
    bound: Any, failure: str
) -> None:
    _, host, engine = bound
    setattr(engine, failure, 1 if failure == "exit_delta" else True)

    async def scenario() -> None:
        await prepare(host)
        with pytest.raises((RuntimeError, asyncio.CancelledError, host.reader["ReaderError"])):
            await host.perform_b()
        await finish(host)

    run(scenario())
    assert not host._cases and len(host.records) == 1 and not engine.rows
    assert host._owners["one"].released
    assert host._stores["one"].read().snapshot is not None
    assert host.result["watchdogs"]["binary"]["status"] == "NOT_STARTED"


@pytest.mark.parametrize("failure", ["release", "volumes", "join", "fire"])
def test_handoff_barrier_rejects_missing_proof(bound: Any, failure: str) -> None:
    _, host, engine = bound

    async def scenario() -> None:
        await prepare(host)
        await host._case("one")
        if failure == "release":
            host._owners["one"].released = False
        elif failure == "volumes":
            host.records[0]["case_volume_restored"] = False
        elif failure == "join":
            host._monitor_joined.remove("one")
        else:
            host._monitors["one"].fired.set()
        with pytest.raises(RuntimeError, match="PREVIOUS_CASE_HELD"):
            await host._activate("binary")
        host._owners["one"].released = True
        host.records[0]["case_volume_restored"] = True
        await finish(host)

    run(scenario())
    assert len(host.records) == 1 and not engine.rows


def test_fire_during_join_aborts_before_next_create_but_cleanup_allowed(bound: Any) -> None:
    _, host, engine = bound

    async def scenario() -> None:
        await prepare(host)
        host._monitors["one"].fire_at_close = True
        with pytest.raises((RuntimeError, asyncio.CancelledError)):
            await host.perform_b()
        await finish(host)
        assert host._monitors["one"].ack.is_set()
        with pytest.raises(RuntimeError, match="WATCHDOG_FIRED"):
            await host.cli("normal", "ps", "-aq", "--no-trunc")
        await host.cli("cleanup", "ps", "-aq", "--no-trunc", cleanup=True)

    run(scenario())
    assert len(host.records) == 1 and not engine.rows


def test_expired_global_b_after_join_cannot_start_new_case(bound: Any) -> None:
    module, host, _ = bound

    async def scenario() -> None:
        await prepare(host)
        await host._case("one")
        host._b_started -= module["B_SECONDS"]
        with pytest.raises(RuntimeError, match="B_DEADLINE"):
            await host._activate("binary")
        await finish(host)

    run(scenario())
    assert len(host.records) == 1


def test_old_callback_acknowledges_only_old_monitor_not_current_foreground(bound: Any) -> None:
    _, host, _ = bound

    async def scenario() -> None:
        await prepare(host)
        await host._case("one")
        await host._activate("binary")
        foreground = asyncio.create_task(asyncio.sleep(0.01))
        host._foreground, host._foreground_case = foreground, "binary"
        host._monitors["one"].callback()
        await foreground
        assert host._monitors["one"].ack.is_set()
        assert not host._monitors["binary"].ack.is_set()
        await finish(host)

    run(scenario())


@pytest.mark.parametrize(
    "args",
    [
        ("run", "alpine"),
        ("start", "--attach", "c" * 64),
        ("exec", "c" * 64, "sh"),
        ("volume", "rm", OTHER),
        ("rm", "c" * 64),
        ("kill", "c" * 64),
    ],
)
def test_unknown_cli_never_reaches_backend(bound: Any, args: Any) -> None:
    _, host, engine = bound
    with pytest.raises(RuntimeError, match="READER_CLI_SCOPE"):
        run(host.cli("scope", *args))
    assert not engine.events


def test_unknown_invoke_and_powershell_never_reach_backend(bound: Any) -> None:
    _, host, engine = bound
    with pytest.raises(RuntimeError, match="INVOKE_SCOPE"):
        run(host.invoke("scope", ["arbitrary"], 1, 10))
    with pytest.raises(RuntimeError, match="PS_SCOPE"):
        run(host.powershell("scope", "Write-Output arbitrary"))
    assert not engine.events


def test_create_once_token_consumed_on_ambiguous_reply_no_retry_or_name_adoption(
    bound: Any,
) -> None:
    _, host, engine = bound
    engine.create_code = 1

    async def scenario() -> None:
        await prepare(host)
        with pytest.raises(RuntimeError, match="CREATE_EXIT"):
            await host._case("one")
        with pytest.raises(RuntimeError):
            await host.cli("repeat", *host._blueprints["one"][0])
        await host.cleanup_owned()
        await host.stop_supervision()

    run(scenario())
    assert host.records[0]["create_uncertain"] and host.result["owned_cleanup"] is False
    assert sum(label == "create-one" for label, _ in engine.events) == 1
    assert len(engine.rows) == 1  # only fake resources; ambiguity is retained


def test_removed_cid_cannot_inspect_kill_rm_only_absence(bound: Any) -> None:
    _, host, _ = bound

    async def scenario() -> None:
        await prepare(host)
        await host._case("one")
        cid = host.records[0]["cid"]
        host._remove_approved, host._kill_approved = ("rm", cid), ("kill", cid)
        for args in (("inspect", "--type", "container", cid), ("rm", cid), ("kill", cid)):
            with pytest.raises(RuntimeError, match="READER_CLI_SCOPE"):
                await host.cli("retired", *args, cleanup=True)
        await host.cli("absent", "ps", "-aq", "--no-trunc", "--filter", "id=" + cid, cleanup=True)
        await finish(host)

    run(scenario())


def test_cleanup_uses_record_case_not_selected_case_and_captures_birth_on_failed_start(
    bound: Any, monkeypatch: Any
) -> None:
    _, host, engine = bound
    engine.fail_start = True
    birth = SimpleNamespace(pid=123, filetime=456)
    monkeypatch.setitem(host.pg["identity"], "capture", lambda process: birth if process else None)

    async def scenario() -> None:
        await prepare(host)
        with pytest.raises(RuntimeError, match="FAKE_START"):
            await host._case("one")
        host._active_case = "binary"
        await finish(host)

    run(scenario())
    snapshot = host._stores["one"].read().snapshot
    assert (snapshot.pid, snapshot.filetime) == (123, 456) and not engine.rows


@pytest.mark.parametrize("field", ["Driver", "ServerVersion"])
def test_untrusted_daemon_projection_refused_without_persisting_marker(
    bound: Any, field: str
) -> None:
    _, host, engine = bound
    engine.extra[field] = "password=private-marker"
    with pytest.raises(RuntimeError, match="DAEMON_PROFILE"):
        run(host.preflight())
    assert not (host.root / "daemon.json").exists()
    assert b"private-marker" not in b"".join(path.read_bytes() for path in host.root.glob("*.json"))


def test_inherited_definitions_are_exact_objects_and_no_entry(bound: Any) -> None:
    module, host, _ = bound
    for name in (
        "_metadata",
        "_inventory_volumes",
        "_task",
        "foreground",
        "_removal",
        "record_intents",
        "_volume_final",
        "run_own",
        "check_attestation",
        "watchdog",
    ):
        assert getattr(module["Host"], name) is getattr(module["P"]["Host"], name)
    assert host.save.__func__ is module["V2"]["Host"].save
    assert "main" not in module


def test_unjoined_monitor_blocks_restore_and_release(bound: Any) -> None:
    _, host, _ = bound

    async def scenario() -> None:
        await prepare(host)
        host._monitors["one"].join_ok = False
        await host.cleanup_owned()
        with pytest.raises(RuntimeError, match="SUPERVISION_HELD"):
            await host.stop_supervision()
        with pytest.raises(RuntimeError, match="RESTORE_UNPROVEN"):
            await host.restore_desktop()
        with pytest.raises(RuntimeError, match="HOST_HELD"):
            host.assert_released()

    run(scenario())
    assert host.result["watchdogs"]["one"]["status"] == "HELD"


def test_all_stores_prepared_without_threads_and_same_b_stamp_not_rearmed(bound: Any) -> None:
    _, host, _ = bound

    async def scenario() -> None:
        await prepare(host)
        assert len(host._stores) == len(host._monitors) == 23
        assert sum(m.started for m in host._monitors.values()) == 1
        assert all(store.read().snapshot is None for store in host._stores.values())
        stamp = host._b_started
        for store in host._stores.values():
            assert store.read().b_started == stamp
            with pytest.raises(RuntimeError):
                store.arm_b(time.monotonic())
        await finish(host)

    run(scenario())


def test_close_error_still_stops_heartbeat_and_collects_other_attempted_monitors(
    bound: Any, monkeypatch: Any
) -> None:
    _, host, _ = bound

    def broken_close() -> bool:
        raise OSError("FAKE_JOIN")

    async def scenario() -> None:
        await prepare(host)
        host._monitor_attempted.add("binary")
        host._monitors["binary"].start()
        monkeypatch.setattr(host._monitors["one"], "close", broken_close)
        await host.cleanup_owned()
        with pytest.raises(RuntimeError, match="SUPERVISION_HELD"):
            await host.stop_supervision()
        assert host._heartbeats["one"].done()
        assert host._monitors["binary"].joined
        assert not host._all_joined()
        assert host.result["watchdogs"]["one"]["status"] == "HELD"

    run(scenario())


def test_join_set_does_not_override_negative_monitor_metadata(bound: Any) -> None:
    _, host, _ = bound

    async def scenario() -> None:
        await prepare(host)
        host._monitor_joined.add("one")
        assert not host._all_joined()
        host._monitor_joined.clear()
        await finish(host)

    run(scenario())


def test_budget_rechecked_after_pins_immediately_before_owner_start(
    bound: Any, monkeypatch: Any
) -> None:
    module, host, engine = bound
    engine.owner_start_checks_budget = False

    def expire(**_kwargs: Any) -> None:
        host._b_started -= module["B_SECONDS"]

    async def scenario() -> None:
        await prepare(host)
        monkeypatch.setattr(host, "pins", expire)
        with pytest.raises(RuntimeError, match="B_DEADLINE"):
            await host._case("one")
        assert not any(label == "OWNER_START" for label, _ in engine.events)
        await finish(host)

    run(scenario())


def test_restore_allows_safe_cleanup_after_fired_case_but_requires_join(
    bound: Any, monkeypatch: Any
) -> None:
    module, host, engine = bound

    async def restored(_self: Any) -> None:
        assert _self._all_joined() and _self.result["owned_cleanup"]
        await _self.cli("desktop-stop", "desktop", "stop", "--timeout", "20", cleanup=True)

    async def transport(_label: str, args: Any, *_args: Any, **_kwargs: Any) -> Any:
        if tuple(args[3:]) == ("volume", "ls", "-q"):
            return await engine.invoke(_label, args, *_args, **_kwargs)
        assert tuple(args[3:]) == ("desktop", "stop", "--timeout", "20")
        assert host._stop_approved is False
        return 0, b""

    async def scenario() -> None:
        await prepare(host)
        await host._case("one")
        host._monitors["one"].fired.set()
        await finish(host)
        monkeypatch.setattr(module["R"]["Host"], "restore_desktop", restored)
        monkeypatch.setattr(host, "_bounded", transport)
        await host.restore_desktop()

    run(scenario())
    assert not engine.rows


@pytest.mark.parametrize("failure", ["intent", "volume-final"])
def test_durability_failure_never_authorizes_next_case(
    bound: Any, monkeypatch: Any, failure: str
) -> None:
    _, host, engine = bound
    original = host.write_new

    def write(name: str, raw: bytes, maximum: int = 4 * 1024 * 1024) -> None:
        if (failure == "intent" and name.endswith("-intent.json")) or (
            failure == "volume-final" and name.startswith("volume-final-")
        ):
            raise OSError("FAKE_DURABILITY")
        original(name, raw, maximum)

    async def scenario() -> None:
        await prepare(host)
        monkeypatch.setattr(host, "write_new", write)
        with pytest.raises(OSError, match="FAKE_DURABILITY"):
            await host._case("one")
        with pytest.raises(RuntimeError):
            await host._activate("binary")
        monkeypatch.setattr(host, "write_new", original)
        if failure == "volume-final":
            assert host.records[0]["removed"]
            assert not host.records[0]["case_volume_restored"]
            await finish(host)
        else:
            assert not any(label == "create-one" for label, _ in engine.events)
            await host.cleanup_owned()
            await host.stop_supervision()
            assert host.result["owned_cleanup"]
            assert host.records[0]["create_not_invoked"]

    run(scenario())
    assert len(host.records) == 1 and not engine.rows


def test_remove_approval_consumed_when_backend_returns_failure(bound: Any) -> None:
    _, host, engine = bound
    engine.rm_code = 1

    async def scenario() -> None:
        await prepare(host)
        with pytest.raises(RuntimeError, match="REMOVE"):
            await host._case("one")
        cid = host.records[0]["cid"]
        assert host._remove_approved is None
        with pytest.raises(RuntimeError, match="READER_CLI_SCOPE"):
            await host.cli("repeated-rm", "rm", "--volumes", cid, cleanup=True)
        engine.rm_code = 0
        await finish(host)

    run(scenario())
    assert not engine.rows and len(host.records) == 1


@pytest.mark.parametrize("failure", ["no_ticket", "owner_held"])
def test_uncollected_owner_blocks_release_and_restore(bound: Any, failure: str) -> None:
    _, host, engine = bound
    setattr(engine, failure, True)

    async def scenario() -> None:
        await prepare(host)
        with pytest.raises(RuntimeError, match="OWNER_HELD"):
            await host._case("one")
        await host.cleanup_owned()
        await host.stop_supervision()
        assert not host.result["owned_cleanup"]
        with pytest.raises(RuntimeError, match="HOST_HELD"):
            host.assert_released()
        with pytest.raises(RuntimeError, match="RESTORE_UNPROVEN"):
            await host.restore_desktop()

    run(scenario())


def test_crossed_owner_wrapper_refused_before_start(bound: Any, monkeypatch: Any) -> None:
    _, host, engine = bound

    def crossed(*args: Any) -> Owner:
        owner = Owner(engine, *args)
        owner.wrapper += "changed"
        return owner

    async def scenario() -> None:
        await prepare(host)
        monkeypatch.setitem(host.pg["delivery"], "PublicDeliveryOwner", crossed)
        with pytest.raises(RuntimeError, match="OWNER_BINDING"):
            await host._case("one")
        await finish(host)

    run(scenario())
    assert not any(label == "OWNER_START" for label, _ in engine.events)


@pytest.mark.parametrize("reason", ["expired", "fired"])
def test_final_source_pins_are_independent_of_execution_gate(
    bound: Any, monkeypatch: Any, reason: str
) -> None:
    module, host, _ = bound
    endpoint = host.root / "endpoint-fixture.json"
    endpoint.write_bytes(
        encoded({"Endpoints": {"docker": {"Host": "npipe:////./pipe/dockerDesktopLinuxEngine"}}})
    )
    monkeypatch.setitem(module["R"], "EXTERNAL_PINS", {})
    monkeypatch.setitem(module["R"], "META", endpoint)
    seen: list[Any] = []
    pinned = module["R"]["pinned"]

    def observed(path: Any, digest: Any, *args: Any) -> Any:
        seen.append(path)
        return pinned(path, digest, *args)

    monkeypatch.setitem(module["R"], "pinned", observed)

    async def scenario() -> None:
        await prepare(host)
        if reason == "expired":
            host._b_started -= module["B_SECONDS"]
        else:
            host._monitors["one"].fired.set()
        module["Host"].pins(host)
        assert REPO / "docs/poc/oracle9_w1_run.py" in seen
        with pytest.raises(RuntimeError, match=r"B_DEADLINE|WATCHDOG_FIRED"):
            await host.cli("normal", "ps", "-aq", "--no-trunc")
        await finish(host)

    run(scenario())


@pytest.mark.parametrize("failure", ["metadata", "heartbeat"])
def test_shutdown_isolates_failure_and_collects_other_active_monitor(
    bound: Any, monkeypatch: Any, failure: str
) -> None:
    _, host, _ = bound
    metadata = host._metadata

    def broken_metadata(prefix: str, value: Any) -> None:
        if prefix == "monitor-case-01-one":
            raise OSError("PRIVATE_DISK_MARKER")
        metadata(prefix, value)

    async def broken_heartbeat() -> None:
        raise RuntimeError("PRIVATE_HEARTBEAT_MARKER")

    async def scenario() -> None:
        await prepare(host)
        if failure == "metadata":
            monkeypatch.setattr(host, "_metadata", broken_metadata)
        else:
            host._heartbeat_stops["one"].set()
            await host._heartbeats["one"]
            host._heartbeats["one"] = host._task(broken_heartbeat(), "failed-heartbeat")
            await asyncio.sleep(0)
        host._monitor_attempted.add("binary")
        host._monitors["binary"].start()
        with pytest.raises(RuntimeError, match=r"^SUPERVISION_HELD$") as caught:
            await host.stop_supervision()
        assert caught.value.__context__ is None
        assert host._monitors["binary"].joined
        assert host._heartbeats["one"].done()
        assert host.result["watchdogs"]["one"]["status"] == "HELD"

    run(scenario())


def test_case_evidence_binds_post_execution_inspect_and_closed_report_fields(bound: Any) -> None:
    _, host, _ = bound

    async def scenario() -> None:
        await prepare(host)
        await host._case("one")
        await finish(host)

    run(scenario())
    row = host._cases[0]
    assert row["inspect_exit_code"] == row["returncode"] == 0
    assert row["oom_killed"] is row["dead"] is False
    assert row["report_ok"] is True and row["report_category"] is None
    assert row["inspect_label"] == "inspect-result-one"
    manifest = next(
        item for item in host._reply_manifest if item["index"] == row["inspect_cli_index"]
    )
    assert manifest["artifact"] == row["inspect_artifact"]
    info = json.loads((host.root / row["inspect_artifact"]).read_bytes())[0]
    assert info["State"]["ExitCode"] == 0 and info["State"]["Pid"] == 0


def test_proven_not_invoked_create_is_distinct_from_ambiguous_create(
    bound: Any, monkeypatch: Any
) -> None:
    _, host, engine = bound
    original = host.write_new

    def rejected(name: str, raw: bytes, maximum: int = 4 * 1024 * 1024) -> None:
        if name.endswith("-intent.json"):
            raise OSError("FAKE_INTENT_WRITE")
        original(name, raw, maximum)

    async def scenario() -> None:
        await prepare(host)
        monkeypatch.setattr(host, "write_new", rejected)
        with pytest.raises(OSError):
            await host._case("one")
        monkeypatch.setattr(host, "write_new", original)
        await host.cleanup_owned()
        await host.stop_supervision()
        assert host.result["owned_cleanup"] is True
        assert host.records[0]["create_not_invoked"] is True
        assert not host._create_invoked and not engine.rows

    run(scenario())


def test_checkpoint_b_really_arms_all_stores_once_and_persists_journal(
    bound: Any, monkeypatch: Any
) -> None:
    module, host, _ = bound
    core = host.libs["core"]
    tick = 0

    def sample_at(value: int) -> Any:
        return core["Sample"](
            "134372287595000000", str(value), str(134373000000000000 + value * 10000)
        )

    async def check_app(_label: str) -> None:
        return None

    async def sample() -> Any:
        nonlocal tick
        tick += 1
        return sample_at(tick)

    async def scenario() -> None:
        nonlocal tick
        await host.start_supervision()
        await host.preflight()
        host.cycle = core["start"](sample_at(0))
        host.save("cycle.json", json.loads(core["encode"](host.cycle)))
        for index in range(1, 10):
            tick = index * 10000
            host.cycle = core["advance"](host.cycle, sample_at(tick), "OBSERVE").state
            host.save("cycle.json", json.loads(core["encode"](host.cycle)))
        tick += 1
        host.cycle = core["advance"](host.cycle, sample_at(tick), "READY").state
        host.save("cycle.json", json.loads(core["encode"](host.cycle)))
        monkeypatch.setattr(host, "check_app", check_app)
        monkeypatch.setattr(host, "sample", sample)
        await host.checkpoint("B")
        assert all(store.read().b_started == host._b_started for store in host._stores.values())
        assert host.cycle.phase is core["Phase"].B_CONSUMED
        assert len(host._checkpoint_records) == 12
        module["V2"]["journal_from_disk"](host)
        with pytest.raises(RuntimeError, match="SUPERVISION_REQUIRED"):
            await host.checkpoint("B")
        await finish(host)

    run(scenario())


@pytest.mark.parametrize("phase", ["drain", "collect"])
def test_asyncio_b_timeout_during_owner_or_cleanup_preserves_collection_path(
    bound: Any, monkeypatch: Any, phase: str
) -> None:
    module, host, engine = bound
    original = host._collect

    async def blocked(*_args: Any) -> None:
        await asyncio.Event().wait()

    async def scenario() -> None:
        await prepare(host)
        # Test-only shorter budget; no production limit widened or native work.
        monkeypatch.setitem(module, "B_SECONDS", 0.5)
        # runpy returns a copy of module globals; alter the function namespace.
        monkeypatch.setitem(module["Host"].perform_b.__globals__, "B_SECONDS", 0.5)
        if phase == "drain":
            monkeypatch.setattr(Owner, "drain", blocked)
        else:
            monkeypatch.setattr(host, "_collect", blocked)
        with pytest.raises(TimeoutError):
            await host.perform_b()
        monkeypatch.setattr(host, "_collect", original)
        await finish(host)

    run(scenario())
    assert len(host.records) == 1 and not host._cases and not engine.rows


def test_real_watchdog_constructors_and_snapshot_binding_with_fake_start_only(
    bound: Any, monkeypatch: Any
) -> None:
    _, host, engine = bound

    def no_native_start(monitor: Any) -> bool:
        monitor._started = True
        monitor.thread = SimpleNamespace(join=lambda **_kwargs: None, is_alive=lambda: False)
        return True

    async def scenario() -> None:
        monkeypatch.setitem(host.pg["watch"], "Watchdog", engine.real_monitor)
        monkeypatch.setattr(engine.real_monitor, "start", no_native_start)
        await prepare(host)
        assert len(host._monitors) == 23
        assert all(
            monitor._policy["P"]["MANIFEST_SHA"] == host.profile["MANIFEST_SHA"]
            for monitor in host._monitors.values()
        )
        for case in host.module_cases:
            snapshot = host.pg["watch"]["Snapshot"](
                TASK, case, host._intents[case].command, (OTHER,)
            )
            host._monitors[case].check_snapshot(snapshot)
        await finish(host)

    run(scenario())


def test_real_new_owner_can_quiesce_and_release_without_spawn(bound: Any) -> None:
    _, host, engine = bound

    async def scenario() -> None:
        owner = engine.real_owner(TASK, "c" * 64, "one")
        ticket = await owner.quiesce()
        assert ticket is not None and owner._process is None
        assert await owner.close(host.channel["Absent"](ticket, time.monotonic()))
        owner.assert_released()

    run(scenario())


def test_no_cli_effect_when_pins_use_up_remaining_b_time(bound: Any, monkeypatch: Any) -> None:
    module, host, engine = bound

    def pins(**kwargs: Any) -> None:
        if not kwargs.get("cleanup", False):
            host._b_started -= module["B_SECONDS"]

    async def scenario() -> None:
        await prepare(host)
        before = len(engine.events)
        monkeypatch.setattr(host, "pins", pins)
        with pytest.raises(RuntimeError, match="B_DEADLINE"):
            await host.cli("expired-during-pins", "ps", "-aq", "--no-trunc")
        assert len(engine.events) == before
        await finish(host)

    run(scenario())


def test_stopped_cancelled_heartbeat_is_collected_on_later_teardown(bound: Any) -> None:
    _, host, _ = bound

    async def scenario() -> None:
        await prepare(host)
        host._heartbeat_stops["one"].set()
        host._heartbeats["one"].cancel()
        await asyncio.sleep(0)
        assert host._heartbeats["one"].cancelled()
        await finish(host)
        assert not host._supervision_errors

    run(scenario())


def test_foreground_cancel_during_monitor_finish_never_advances_case(bound: Any) -> None:
    _, host, _ = bound

    async def blocked() -> None:
        await asyncio.Event().wait()

    async def scenario() -> None:
        await prepare(host)
        host._heartbeat_stops["one"].set()
        await host._heartbeats["one"]
        host._heartbeats["one"] = host._task(blocked(), "blocked-heartbeat")
        task = asyncio.create_task(host._finish_monitor("one", require_clean=True))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(RuntimeError, match="SUPERVISION_HELD"):
            await task
        assert host._supervision_errors["one"] == ("HEARTBEAT",)
        assert not host._cases and not host.records
        with pytest.raises(RuntimeError, match=r"PREVIOUS_CASE_HELD|RECORD"):
            await host._activate("binary")
        await finish(host)

    run(scenario())
