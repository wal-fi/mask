"""Public coordinator integration against a closed fake CLI. No Docker/native effects."""

import asyncio
import hashlib
import json
import runpy
import threading
import time
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
TASK = "a" * 32
CID = "c" * 64
OTHER = "third_party_project_data"
ANON = "d" * 64


def encoded(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


class Engine:
    def __init__(self, module: Any, host: Any, fixtures: Any) -> None:
        self.module, self.host, self.fixtures = module, host, fixtures
        self.rows: dict[str, Any] = {}
        self.volumes = {OTHER}
        self.events: list[Any] = []
        self.mounts: Any = []
        self.create_code = 0
        self.volume_code = 0
        self.rm_code = 0
        self.absence_code = 0
        self.alien = False
        self.leftover = False
        self.fail_start = False
        self.no_ticket = False
        self.bad_report = False
        self.nonzero_report = False
        self.exited = True
        self.fail_kill = False
        self.daemon_extra: dict[str, Any] = {}
        self.version_extra: dict[str, Any] = {}

    async def cli(self, label: str, *args: Any, **_kwargs: Any) -> Any:  # noqa: PLR0911, PLR0912 - closed fake command inventory
        self.events.append((label, args))
        if args[0] == "version":
            return 0, encoded({"Client": {"Version": "29.7.2", **self.version_extra}})
        if args[0] == "info":
            return 0, encoded(
                {
                    "OSType": "linux",
                    "Architecture": "x86_64",
                    "KernelVersion": self.module["R"]["KERNEL"],
                    "MemTotal": 4 * 1024**3,
                    "Driver": "overlayfs",
                    "CgroupVersion": "2",
                    "ServerVersion": "29.7.2",
                    **self.daemon_extra,
                }
            )
        if args[0] == "image":
            return 0, encoded([self.fixtures["image_info"](self.host.profile)])
        if args == ("volume", "ls", "-q"):
            return self.volume_code, (
                "\n".join(sorted(self.volumes)) + ("\n" if self.volumes else "")
            ).encode("ascii")
        if args[0] == "create":
            intent_path = self.host.root / "pg16-public-intent.json"
            assert intent_path.is_file() and json.loads(intent_path.read_bytes())["cid"] is None
            assert (self.host.root / "local-volume-baseline.json").is_file()
            assert self.host._store.read().snapshot.cid is None
            _, row = self.fixtures["bound"].__wrapped__(self.host.profile)
            row = deepcopy(row)
            row["Mounts"] = deepcopy(self.mounts)
            row["State"].update(OOMKilled=False, Dead=False, ExitCode=0)
            self.rows[CID] = row
            if type(self.mounts) is list:
                self.volumes.update(m["Name"] for m in self.mounts if m.get("Type") == "volume")
            return self.create_code, CID.encode() + b"\n"
        if args[0] == "inspect":
            if CID not in self.rows:
                return 1, b""
            info = deepcopy(self.rows[CID])
            if self.alien:
                info["Config"]["Labels"]["maskgw.task"] = "f" * 32
            return 0, encoded([info])
        if args[0] == "kill":
            if self.fail_kill:
                return 1, b""
            self.rows[CID]["State"].update(Running=False, Pid=0)
            return 0, CID.encode() + b"\n"
        if args[0] == "rm":
            # Decision is durable BEFORE this effect; old/preexisting names are absent.
            decisions = list(self.host.root.glob("volume-decision-*.json"))
            assert decisions and OTHER.encode() not in decisions[-1].read_bytes()
            if self.rm_code:
                return self.rm_code, b""
            if "--volumes" in args and not self.leftover and type(self.mounts) is list:
                for item in self.mounts:
                    if item.get("Type") == "volume" and len(item["Name"]) == 64:
                        self.volumes.discard(item["Name"])
            self.rows.pop(CID, None)
            return 0, CID.encode() + b"\n"
        assert args[0] == "ps"
        if "--filter" in args and self.absence_code:
            return self.absence_code, b""
        return 0, (CID.encode() + b"\n") if self.rows else b""


class Owner:
    def __init__(self, engine: Engine, target: Any) -> None:
        self.engine, self.target = engine, target
        self._process: Any = None
        self.released = False
        self.ticket: Any = None

    async def start(self) -> None:
        self.engine.events.append(("OWNER_START", self.target.cid))
        self._process = SimpleNamespace(pid=123)
        assert self.engine.host._owners["pg16-public"] is self
        if self.engine.fail_start:
            raise RuntimeError("FAKE_START")
        self.engine.rows[CID]["State"].update(Running=True, Pid=456)

    async def drain(self) -> Any:
        self.engine.events.append(("OWNER_DRAIN", self.target.cid))
        raw = self.engine.fixtures["report"](self.engine.host.profile, self.engine.host._intent)
        if self.engine.bad_report:
            raw = b"bad\n"
        if self.engine.exited:
            self.engine.rows[CID]["State"].update(Running=False, Pid=0)
        return (42 if self.engine.nonzero_report else 0), self.engine.host.channel["PrivateOutput"](
            raw
        )

    async def quiesce(self) -> Any:
        self.engine.events.append(("OWNER_QUIESCE", self.target.cid))
        if self.engine.no_ticket:
            return None
        if self.ticket is None:
            self.ticket = self.engine.host.channel["Quiesced"](CID, "f" * 32, time.monotonic())
        return self.ticket

    async def close(self, absent: Any) -> bool:
        self.engine.events.append(("OWNER_CLOSE", self.target.cid))
        assert absent.ticket is self.ticket and not self.engine.rows
        assert self.engine.host.result["volumes_restored"] is True
        self.released = True
        return True

    def metadata(self) -> Any:
        return {"released": self.released}

    def assert_released(self) -> None:
        assert self.released


@pytest.fixture
def bound(tmp_path: Any, monkeypatch: Any) -> Any:
    module = runpy.run_path(str(REPO / "docs/poc/pg16_public_host.py"))
    fixtures = runpy.run_path(str(REPO / "tests/test_pg16_public_profile.py"))
    state = {
        "task": TASK,
        "pins": dict(module["R"]["LIBRARIES"].values()),
        "host_sha256": hashlib.sha256(Path(module["__file__"]).read_bytes()).hexdigest(),
    }
    profile = runpy.run_path(str(REPO / "docs/poc/pg16_public_profile.py"))
    state["create_measurement"] = profile["blueprint"](TASK)[1]
    host = module["Host"](tmp_path, state)
    engine = Engine(module, host, fixtures)

    async def transport(_self: Any, label: str, *args: Any, **kwargs: Any) -> Any:
        return await engine.cli(label, *args, **kwargs)

    monkeypatch.setattr(module["R"]["Host"], "cli", transport)
    monkeypatch.setattr(host, "pins", lambda **_kwargs: None)
    monkeypatch.setitem(host.pg["owner"], "PublicProbeOwner", lambda target: Owner(engine, target))
    monkeypatch.setitem(host.pg["identity"], "capture", lambda _process: None)
    host._store = host.pg["watch"]["Store"](time.monotonic())
    host._cleanup_lock = threading.Lock()
    return module, host, engine


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def test_normal_probe_stops_reconciles_before_close_and_preserves_other_volume(bound):
    _, host, engine = bound

    async def case() -> None:
        await host.preflight()
        await host._case()
        await host.cleanup_owned()

    run(case())
    assert host.result["owned_cleanup"] is True and host.result["inventory_restored"] is True
    assert host._owners["pg16-public"].released and engine.volumes == {OTHER}
    assert not engine.rows and len(host._cases) == 1
    events = [event[0] for event in engine.events]
    assert (
        events.index("OWNER_QUIESCE")
        < events.index("rm-pg16-public")
        < events.index("absent-after-pg16-public")
        < events.index("OWNER_CLOSE")
    )
    assert (host.root / "local-probe-output.bin").is_file()


@pytest.mark.parametrize(
    "mount,expected_v,clean",
    [
        ({"Type": "volume", "Name": ANON}, True, True),
        ({"Type": "volume", "Name": OTHER}, False, True),
        ({"Type": "volume", "Name": "new_named_volume"}, True, False),
        ({"Type": "unexpected"}, False, False),
    ],
    ids=["new-anonymous", "preexisting", "named-leftover", "unknown"],
)
def test_unexpected_mount_rejected_before_start_but_cleanup_uses_identity(
    bound, mount, expected_v, clean
):
    _, host, engine = bound
    engine.mounts = [mount]

    async def case() -> None:
        await host.preflight()
        with pytest.raises(host.profile["ProbeError"]):
            await host._case()
        await host.cleanup_owned()

    if clean:
        run(case())
        assert host.result["owned_cleanup"] is True
    else:
        # A final volume mismatch is not converted into cleanup success.
        try:
            run(case())
        except RuntimeError as error:
            assert str(error) in ("VOLUME_INVENTORY_CHANGED", "VOLUME_OWNERSHIP_UNPROVEN")
        assert host.result["owned_cleanup"] is False
    assert not any(event[0] == "OWNER_START" for event in engine.events)
    removes = [
        args for _, args in engine.events if type(args) is tuple and args and args[0] == "rm"
    ]
    assert len(removes) == 1 and ("--volumes" in removes[0]) is expected_v
    assert OTHER in engine.volumes


def test_failed_initial_volume_inventory_never_permits_create(bound):
    _, host, engine = bound
    engine.volume_code = 1
    with pytest.raises(RuntimeError, match="VOLUME_INVENTORY_EXIT"):
        run(host.preflight())
    with pytest.raises(RuntimeError, match="CREATE_NOT_ADMITTED"):
        run(host.create_own())
    assert not host.records and not any(args[0] == "create" for _, args in engine.events)


def test_ambiguous_create_is_held_without_name_or_global_absence_fallback(bound):
    _, host, engine = bound
    engine.create_code = 1

    async def case() -> None:
        await host.preflight()
        with pytest.raises(RuntimeError, match="CREATE_EXIT"):
            await host.create_own()
        await host.cleanup_owned()

    run(case())
    assert host.result["owned_cleanup"] is False and host.records[0]["create_uncertain"]
    assert CID in engine.rows
    assert not any(args[0] in ("rm", "kill", "inspect") for _, args in engine.events)


def test_alien_inspect_never_authorizes_mutation(bound):
    _, host, engine = bound

    async def case() -> None:
        await host.preflight()
        await host.create_own()
        engine.alien = True
        await host.cleanup_owned()

    run(case())
    assert host.result["owned_cleanup"] is False and CID in engine.rows
    assert not any(args[0] in ("rm", "kill") for _, args in engine.events)


@pytest.mark.parametrize("fault", ["rm_code", "absence_code", "no_ticket", "leftover"])
def test_incomplete_cleanup_never_releases_owner(bound, fault):
    _, host, engine = bound

    async def case() -> None:
        await host.preflight()
        await host.create_own()
        owner = Owner(engine, SimpleNamespace(cid=CID))
        host._owners["pg16-public"] = owner
        setattr(engine, fault, 1 if fault.endswith("code") else True)
        if fault == "leftover":
            engine.volumes.add("foreign_new_volume")
        await host.cleanup_owned()
        assert not owner.released

    run(case())
    assert host.result["owned_cleanup"] is False


@pytest.mark.parametrize("fault", ["bad_report", "nonzero_report", "fail_start", "exited"])
def test_probe_failure_is_not_success_and_cleanup_still_collects(bound, fault):
    _, host, engine = bound
    setattr(engine, fault, fault != "exited")

    async def case() -> None:
        await host.preflight()
        with pytest.raises((RuntimeError, host.profile["ProbeError"])):
            await host._case()
        await host.cleanup_owned()

    run(case())
    assert host.result["owned_cleanup"] is True and not host._cases
    assert host._owners["pg16-public"].released


def test_volume_names_only_local_no_plaintext_in_public_metadata(bound):
    _, host, _ = bound

    async def case() -> None:
        await host.preflight()
        await host._case()

    run(case())
    for path in host.root.iterdir():
        if not path.name.startswith("local-"):
            assert OTHER.encode() not in path.read_bytes(), path.name
    baseline = json.loads((host.root / "local-volume-baseline.json").read_bytes())
    assert baseline["names"] == [OTHER]
    manifest = json.loads((host.root / "public-cli-manifest.json").read_bytes())
    assert all(row["local_only"] is True for row in manifest)


def test_metadata_failure_does_not_leave_positive_restoration(bound, monkeypatch):
    _, host, _ = bound
    run(host.preflight())
    host.result["volumes_restored"] = True

    def fail(*_args):
        raise OSError("synthetic metadata persistence failure")

    monkeypatch.setattr(host, "_metadata", fail)
    with pytest.raises(OSError):
        run(host._volume_final())
    assert host.result["volumes_restored"] is False


def test_raw_reply_is_persisted_before_profile_failure(bound):
    _, host, engine = bound
    engine.mounts = [{"Type": "volume", "Name": ANON}]

    async def case() -> None:
        await host.preflight()
        with pytest.raises(host.profile["ProbeError"]):
            await host.create_own()

    run(case())
    manifest = json.loads((host.root / "public-cli-manifest.json").read_bytes())
    last = manifest[-1]
    raw = (host.root / last["artifact"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == last["sha256"] and ANON.encode() in raw


@pytest.mark.parametrize(
    "args",
    [
        ("start", "--attach", CID),
        ("volume", "rm", ANON),
        ("system", "prune"),
        ("cp", "x", "y"),
        ("commit", CID, "tag"),
        ("rm", "--force", CID),
        ("image", "pull", "postgres:16"),
        ("inspect", "--type", "container", "d" * 64),
    ],
)
def test_cli_refuses_every_undeclared_effect_before_transport(bound, args):
    _, host, engine = bound
    with pytest.raises(RuntimeError, match="PG16_PUBLIC_CLI_SCOPE"):
        run(host.cli("bad", *args))
    assert not engine.events


def test_second_create_forbidden(bound):
    _, host, _ = bound

    async def case() -> None:
        await host.preflight()
        await host.create_own()
        with pytest.raises(RuntimeError, match="CREATE_NOT_ADMITTED"):
            await host.create_own()

    run(case())


def test_join_and_cleanup_are_required_before_desktop_restore(bound):
    _, host, engine = bound
    host.result["owned_cleanup"] = True
    with pytest.raises(RuntimeError, match="RESTORE_UNPROVEN"):
        run(host.restore_desktop())
    assert not engine.events


def test_final_inventory_change_blocks_desktop_restore(bound):
    _, host, engine = bound
    run(host.preflight())
    host.result["owned_cleanup"] = True
    host._monitor_joined = True
    engine.volumes.add("foreign_new_volume")
    with pytest.raises(RuntimeError, match="VOLUME_INVENTORY_CHANGED"):
        run(host.restore_desktop())
    assert not any(args[:2] == ("desktop", "stop") for _, args in engine.events)


def test_legacy_methods_are_unavailable(bound):
    _, host, _ = bound
    with pytest.raises(RuntimeError, match="OLD_TRANSPORT_FORBIDDEN"):
        run(host.run_own())
    with pytest.raises(RuntimeError, match="INSTALL_FORBIDDEN"):
        host.check_attestation()
    with pytest.raises(RuntimeError, match="OLD_WATCHDOG_FORBIDDEN"):
        host.watchdog()


def test_direct_rm_v_without_persisted_decision_is_refused(bound):
    _, host, engine = bound

    async def case() -> None:
        await host.preflight()
        await host.create_own()
        before = len(engine.events)
        with pytest.raises(RuntimeError, match="PG16_PUBLIC_CLI_SCOPE"):
            await host.cli("bad-rm", "rm", "--volumes", CID, cleanup=True)
        assert len(engine.events) == before

    run(case())


def test_stale_baseline_aborts_before_create(bound):
    _, host, engine = bound

    async def case() -> None:
        await host.preflight()
        host._baseline_at = getattr(host, "_baseline_at", time.monotonic()) - 31.0
        with pytest.raises(RuntimeError, match="VOLUME_BASELINE_STALE"):
            await host.create_own()

    run(case())
    assert not any(args[0] == "create" for _, args in engine.events)


def test_changed_baseline_aborts_before_create(bound):
    _, host, engine = bound

    async def case() -> None:
        await host.preflight()
        engine.volumes.add("another_project_volume")
        with pytest.raises(RuntimeError, match="VOLUME_BASELINE_CHANGED"):
            await host.create_own()

    run(case())
    assert not host.records and not any(args[0] == "create" for _, args in engine.events)


def test_direct_desktop_stop_without_release_and_join_is_refused(bound):
    _, host, engine = bound
    with pytest.raises(RuntimeError, match="PG16_PUBLIC_CLI_SCOPE"):
        run(host.cli("bad-stop", "desktop", "stop", "--timeout", "20", cleanup=True))
    assert not engine.events


def test_create_argv_cannot_retry_after_ambiguous_reply(bound):
    _, host, engine = bound

    async def case() -> None:
        await host.preflight()
        engine.create_code = 1
        with pytest.raises(RuntimeError, match="CREATE_EXIT"):
            await host.create_own()
        before = len(engine.events)
        with pytest.raises(RuntimeError, match="PG16_PUBLIC_CLI_SCOPE"):
            await host.cli("bad-create-retry", *host._blueprint[0])
        assert len(engine.events) == before

    run(case())


@pytest.mark.parametrize("source", ["info", "version"])
def test_configuration_raw_is_discarded_and_public_projection_preserved(bound, source):
    _, host, engine = bound
    sentinel = "SYNTHETIC_PROXY_CREDENTIAL_NEVER_REAL"
    if source == "info":
        engine.daemon_extra["HttpProxy"] = "http://fixture:" + sentinel + "@invalid.example"
    else:
        engine.version_extra["Plugins"] = [{"Config": sentinel}]
    run(host.preflight())
    for path in host.root.iterdir():
        assert sentinel.encode() not in path.read_bytes(), path.name
    daemon = json.loads((host.root / "daemon.json").read_bytes())
    assert set(daemon) == {
        "OSType",
        "Architecture",
        "KernelVersion",
        "MemTotal",
        "Driver",
        "CgroupVersion",
        "ServerVersion",
    }
    assert daemon["Driver"] == "overlayfs"
    version = json.loads((host.root / "version.json").read_bytes())
    assert version["Client"]["Version"] == "29.7.2" and "Plugins" not in version["Client"]


def test_desktop_stop_approval_cleared_when_preserved_active(bound, monkeypatch):
    module, host, _ = bound
    run(host.preflight())
    host._monitor_joined = True
    host.result["owned_cleanup"] = True

    async def preserved(_self: Any) -> None:
        host.result["desktop_restored"] = True

    monkeypatch.setattr(module["R"]["Host"], "restore_desktop", preserved)
    run(host.restore_desktop())
    assert host._stop_approved is False
