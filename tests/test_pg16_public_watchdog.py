"""PG16 watchdog with fake CLI/clock/thread only. No native effects."""

import ast
import json
import runpy
from pathlib import Path
from typing import Any, cast

import pytest

from tests.test_pg16_public_profile import CID, TASK, encoded, image_info
from tests.test_w1_bootstrap_watchdog import Event, Mutex

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/pg16_public_watchdog.py"))


def monitor(module: Any, tmp_path: Path, *, initial: tuple[str, ...] = ()) -> Any:
    files = (
        "pg16_public_emergency.py",
        "pg16_public_cleanup_policy.py",
        "run_linux_as_probe.py",
        "w1_bootstrap_identity.py",
        "pg16_public_volumes.py",
    )
    sources = [(REPO / "docs/poc" / name).read_bytes() for name in files]
    store = module["Store"](0.0)
    aborts: list[bool] = []
    owner = module["Watchdog"](tmp_path, store, Mutex(), lambda: aborts.append(True), *sources)
    owner.ack = Event(True)
    p = owner._policy["P"]
    intent = p["Intent"](TASK, p["admit_image"](encoded(image_info(p))))
    record = module["Snapshot"](
        TASK, "pg16-public", intent.command, initial, CID, 123, 134375857978266391
    )
    return owner, store, record, aborts, intent


class Public:
    def __init__(self, intent: Any, initial: tuple[str, ...], mounts: Any = None) -> None:
        self.calls: list[str] = []
        self.present = True
        self.fail: str | None = None
        self.volumes = set(initial)
        self.named: set[str] = set()
        self.info = {
            "Id": CID,
            "Name": "/" + intent.name,
            "Image": "sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685",
            "Config": {
                "Image": "sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685",
                "Cmd": list(intent.command),
                "Entrypoint": ["/bin/sh"],
                "Labels": dict(intent.labels),
            },
            "State": {"Running": True, "Pid": 4321},
            "Mounts": [] if mounts is None else mounts,
        }
        for mount in self.info["Mounts"]:
            if mount.get("Type") == "volume":
                self.volumes.add(mount["Name"])

    def begin(self):
        return None

    def invoke(self, action: Any, target: Any) -> bytes:
        self.calls.append(action.value)
        if action.value == self.fail:
            raise RuntimeError("fake-private-canary")
        if action.value == "CLI_KILL":
            return b'{"status":"KILLED"}'
        if action.value == "CID_ABSENCE":
            return (cast(str, target.cid).encode() + b"\n") if self.present else b""
        if action.value == "CID_INSPECT":
            return encoded(self.info)
        if action.value == "CID_KILL":
            self.info["State"].update(Running=False, Pid=0)
            return cast(str, target.cid).encode() + b"\n"
        if action.value in ("CID_REMOVE", "CID_REMOVE_V"):
            self.present = False
            if action.value == "CID_REMOVE_V":
                for mount in self.info["Mounts"] or []:
                    if mount.get("Type") == "volume" and mount["Name"] not in self.named:
                        self.volumes.discard(mount["Name"])
            return cast(str, target.cid).encode() + b"\n"
        assert action.value == "VOLUME_LIST"
        return "".join(name + "\n" for name in sorted(self.volumes)).encode("ascii")


def test_anonymous_volume_is_decided_and_recorded_before_v_then_reconciled(
    module, tmp_path, monkeypatch
):
    owner, _, record, _, intent = monitor(module, tmp_path)
    name = "a" * 64
    public = Public(intent, (), [{"Type": "volume", "Name": name}])
    original = public.invoke

    def invoke(action, target):
        if action.value == "CID_REMOVE_V":
            paths = list(tmp_path.glob("volume-decision-*.json"))
            assert len(paths) == 1
            decision = json.loads(paths[0].read_bytes())
            assert decision["new_anonymous_names"] == [name] and decision["mode"] == "WITH_V"
        return original(action, target)

    monkeypatch.setattr(public, "invoke", invoke)
    owner._public = public
    owner.emergency(record)
    assert not public.present and not public.volumes
    assert owner.metadata()["cid_absent"] and owner.metadata()["volumes_restored"]
    assert owner.metadata()["held"] and not owner.metadata()["released"]
    assert public.calls[-2:] == ["CID_ABSENCE", "VOLUME_LIST"]
    assert len(list(tmp_path.glob("volume-final-*.json"))) == 1


@pytest.mark.parametrize("name", ["existing-named", "b" * 64])
def test_preexisting_volume_never_uses_v_and_survives(module, tmp_path, name):
    owner, _, record, _, intent = monitor(module, tmp_path, initial=(name,))
    public = Public(intent, (name,), [{"Type": "volume", "Name": name}])
    owner._public = public
    owner.emergency(record)
    assert "CID_REMOVE_V" not in public.calls and "CID_REMOVE" in public.calls
    assert public.volumes == {name} and owner.metadata()["volumes_restored"] is True


def test_new_named_volume_left_by_v_is_held_never_directly_deleted(module, tmp_path):
    owner, _, record, _, intent = monitor(module, tmp_path)
    public = Public(intent, (), [{"Type": "volume", "Name": "new-named"}])
    public.named.add("new-named")
    owner._public = public
    owner.emergency(record)
    meta = owner.metadata()
    assert not public.present and public.volumes == {"new-named"}
    assert meta["held"] and not meta["released"] and not meta["volumes_restored"]
    assert meta["category"] == "VOLUME_INVENTORY_CHANGED"
    assert "VOLUME_REMOVE" not in public.calls


def test_unknown_mounts_preserve_and_remain_uncertain_even_if_inventory_matches(module, tmp_path):
    owner, _, record, _, intent = monitor(module, tmp_path)
    public = Public(intent, ())
    public.info["Mounts"] = None
    owner._public = public
    owner.emergency(record)
    meta = owner.metadata()
    assert "CID_REMOVE_V" not in public.calls and "CID_REMOVE" in public.calls
    assert (
        meta["volume_uncertain"]
        and meta["held"]
        and meta["category"] == "VOLUME_OWNERSHIP_UNPROVEN"
    )


@pytest.mark.parametrize("fault", ["alien-cid", "alien-command", "alien-task"])
def test_alien_inspect_never_reaches_cid_kill_or_remove(module, tmp_path, fault):
    owner, _, record, _, intent = monitor(module, tmp_path)
    public = Public(intent, ())
    if fault == "alien-cid":
        public.info["Id"] = "d" * 64
    elif fault == "alien-command":
        public.info["Config"]["Cmd"] = ["different"]
    else:
        public.info["Config"]["Labels"]["maskgw.task"] = "b" * 32
    owner._public = public
    with pytest.raises(RuntimeError):
        owner.emergency(record)
    assert not {"CID_KILL", "CID_REMOVE", "CID_REMOVE_V"} & set(public.calls)
    assert owner.cleanup_lock.releases == 1


def test_failed_remove_cannot_prove_absence_or_inventory_restoration(module, tmp_path):
    owner, _, record, _, intent = monitor(module, tmp_path)
    public = Public(intent, ())
    public.fail = "CID_REMOVE_V"
    owner._public = public
    with pytest.raises(RuntimeError):
        owner.emergency(record)
    assert public.present and not owner.metadata()["cid_absent"]
    assert not owner.metadata()["volumes_restored"] and owner.metadata()["held"]


def test_unknown_cli_identity_never_guesses_a_pid(module, tmp_path):
    owner, _, known, _, intent = monitor(module, tmp_path)
    record = module["Snapshot"](known.task, known.case, known.command, (), known.cid)
    public = Public(intent, ())
    owner._public = public
    owner.emergency(record)
    assert "CLI_KILL" not in public.calls and not public.present


def test_cleanup_lock_prevents_parallel_container_and_volume_actions(module, tmp_path):
    owner, _, record, _, intent = monitor(module, tmp_path)
    public = Public(intent, ())
    owner._public = public
    owner.cleanup_lock = Mutex(False)
    owner.emergency(record)
    assert public.calls == ["CLI_KILL"] and owner.metadata()["category"] == "CLEANUP_LOCK"


def test_already_absent_cid_still_requires_fresh_volume_reconciliation(module, tmp_path):
    owner, _, record, _, intent = monitor(module, tmp_path)
    public = Public(intent, ())
    public.present = False
    public.volumes.add("unexpected")
    owner._public = public
    owner.emergency(record)
    assert public.calls == ["CLI_KILL", "CID_ABSENCE", "VOLUME_LIST"]
    assert not owner.metadata()["volumes_restored"] and owner.metadata()["held"]


def test_fresh_baseline_is_mandatory_and_snapshot_immutable(module, tmp_path):
    owner, _, record, _, _ = monitor(module, tmp_path)
    with pytest.raises(TypeError):
        module["Snapshot"](TASK, "pg16-public", record.command)
    with pytest.raises(RuntimeError):
        module["Snapshot"](TASK, "pg16-public", record.command, ("duplicate", "duplicate"))
    assert owner.metadata()["released"] is False


def test_monitor_core_and_deadline_logic_preserved_by_ast(module):
    old = ast.parse((REPO / "docs/poc/w1_bootstrap_watchdog.py").read_bytes())
    new = ast.parse(Path(module["__file__"]).read_bytes())
    for name in ("Observation", "Store", "reason", "namespace"):
        before = next(node for node in old.body if getattr(node, "name", None) == name)
        after = next(node for node in new.body if getattr(node, "name", None) == name)
        assert ast.dump(before) == ast.dump(after)
    before_class = next(node for node in old.body if getattr(node, "name", None) == "Watchdog")
    after_class = next(node for node in new.body if getattr(node, "name", None) == "Watchdog")
    assert isinstance(before_class, ast.ClassDef) and isinstance(after_class, ast.ClassDef)
    before = next(node for node in before_class.body if getattr(node, "name", None) == "run")
    after = next(node for node in after_class.body if getattr(node, "name", None) == "run")
    assert ast.dump(before) == ast.dump(after)


def test_join_uses_new_predeclared_budget_and_never_proves_resources_released(module, tmp_path):
    owner, _, _, _, _ = monitor(module, tmp_path)
    calls = []

    class Thread:
        def join(self, timeout):
            calls.append(timeout)

        def is_alive(self):
            return False

    owner._started = True
    owner.thread = Thread()
    assert owner.close() is True and calls == [55.0]
    assert owner.metadata()["thread_joined"] and owner.metadata()["released"] is False


def test_live_source_change_cannot_block_captured_policy_emergency(module, tmp_path, monkeypatch):
    owner, _, record, _, intent = monitor(module, tmp_path)
    public = Public(intent, ())
    owner._public = public

    def changed(_path):
        raise OSError("fake-private-canary")

    monkeypatch.setattr(Path, "read_bytes", changed)
    owner.emergency(record)
    assert not public.present and owner.metadata()["volumes_restored"]


@pytest.mark.parametrize("linked", [False, True])
def test_third_party_volume_names_never_reach_public_evidence(module, tmp_path, linked):
    name = "third-party-project-canary"
    owner, _, record, _, intent = monitor(module, tmp_path, initial=(name,))
    mounts = [{"Type": "volume", "Name": name}] if linked else []
    public = Public(intent, (name,), mounts)
    owner._public = public
    owner.emergency(record)
    assert owner.metadata()["volumes_restored"]
    assert all(name.encode() not in path.read_bytes() for path in tmp_path.glob("*.json"))


def test_final_evidence_persistence_failure_never_sets_positive_reconciliation(
    module, tmp_path, monkeypatch
):
    owner, _, record, _, intent = monitor(module, tmp_path)
    owner._public = Public(intent, ())
    owner._write = lambda *_args: None

    def fail(_fd):
        raise OSError("public-write-failure")

    monkeypatch.setattr(module["os"], "fsync", fail)
    with pytest.raises(OSError):
        owner._volume_final(record, owner._emergency["Target"](record.cid))
    assert owner.metadata()["volumes_restored"] is False
