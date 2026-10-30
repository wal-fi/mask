"""Reader watchdog pure/fake lifecycle only. No native thread, CLI or Docker."""

import ast
import json
import runpy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_pg16_public_profile import CID, TASK, encoded, image_info
from tests.test_pg16_public_watchdog import Public
from tests.test_w1_bootstrap_watchdog import Event, Mutex

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/pg16_shell_watchdog.py"))


def monitor(module: Any, tmp_path: Path, *, initial: tuple[str, ...] = ()) -> Any:
    names = (
        "pg16_public_emergency.py",
        "pg16_shell_cleanup_policy.py",
        "run_linux_as_probe.py",
        "w1_bootstrap_identity.py",
        "pg16_public_volumes.py",
    )
    sources = [(REPO / "docs/poc" / name).read_bytes() for name in names]
    store = module["Store"](0.0)
    aborts: list[bool] = []
    watch = module["Watchdog"](tmp_path, store, Mutex(), lambda: aborts.append(True), *sources)
    watch.ack = Event(True)
    p = watch._policy["P"]
    intent = p["Intent"](TASK, p["admit_image"](encoded(image_info(p["P"]))), p["R"]["Case"].BINARY)
    record = module["Snapshot"](
        TASK, "binary", intent.command, initial, CID, 123, 134375857978266391
    )
    return watch, store, record, aborts, intent


@pytest.mark.parametrize(
    "change", ["case", "task", "command", "baseline", "cid", "clear", "birth-change", "birth-clear"]
)
def test_snapshot_cannot_drop_or_replace_owned_case_and_cid(module, change):
    store = module["Store"](0.0)
    first = module["Snapshot"](TASK, "binary", ("-ec", "public"), (), CID, 123, 456)
    store.publish(first)
    current_present = {CID: True}
    if change == "clear":
        second = None
    else:
        variants: dict[str, dict[str, Any]] = {
            "case": {"case": "one"},
            "task": {"task": "b" * 32},
            "command": {"command": ("-ec", "different")},
            "baseline": {"initial_volumes": ("other",)},
            "cid": {"cid": "d" * 64},
            "birth-change": {"pid": 124, "filetime": 457},
            "birth-clear": {"pid": None, "filetime": None},
        }
        changes = variants[change]
        second = replace(first, **changes)
    with pytest.raises(RuntimeError, match="PG16_READER_WATCHDOG_REFUSED"):
        store.publish(second)
    assert current_present[CID] and store.read().snapshot is first


def test_store_allows_only_forward_cid_birth_and_global_bstart_is_not_renewed(module):
    store = module["Store"](10.0)
    store.arm_b(10.0)
    store.pulse(20.0)
    first = module["Snapshot"](TASK, "binary", ("-ec", "public"), ())
    store.publish(first)
    with_cid = replace(first, cid=CID)
    store.publish(with_cid)
    with_birth = replace(with_cid, pid=123, filetime=456)
    store.publish(with_birth)
    store.publish(with_birth)
    assert store.read().snapshot is with_birth
    # A later case needs NEW Store; it still inherits the same global Bstart.
    following = module["Store"](10.0)
    following.arm_b(10.0)
    following.pulse(605.0)
    assert module["reason"](following.read(), 611.0) == "DEADLINE"
    assert module["reason"](following.read(), 610.0) == "DEADLINE"
    with pytest.raises(RuntimeError):
        following.arm_b(605.0)


def test_cases_match_captured_enum_and_legacy_role_cannot_enter(module, tmp_path):
    watch, _, record, _, _ = monitor(module, tmp_path)
    assert module["CASES"] == {case.value for case in watch._policy["P"]["R"]["Case"]}
    assert len(module["CASES"]) == 23 and "pg16-public" not in module["CASES"]
    with pytest.raises(RuntimeError):
        replace(record, case="pg16-public")
    with pytest.raises(RuntimeError):
        replace(record, command=(True, "public"))


@pytest.mark.parametrize("change", ["case", "command"])
def test_bound_rejects_before_begin_or_any_cli_action(module, tmp_path, change, monkeypatch):
    watch, _, record, _, intent = monitor(module, tmp_path)
    public = Public(intent, ())

    def forbidden() -> None:
        raise AssertionError("begin must not precede binding")

    monkeypatch.setattr(public, "begin", forbidden)
    watch._public = public
    bad = replace(record, **({"case": "one"} if change == "case" else {"command": ("-ec", "bad")}))
    with pytest.raises(RuntimeError, match=r"^PG16_READER_SNAPSHOT_BINDING$"):
        watch.check_snapshot(bad)
    watch.emergency(bad)
    assert not public.calls and watch.metadata()["category"] == "SNAPSHOT_BINDING"
    assert watch.metadata()["held"] and not watch.metadata()["released"]


def test_new_policy_parser_and_identity_are_used_without_live_reads(module, tmp_path, monkeypatch):
    watch, _, record, _, intent = monitor(module, tmp_path)
    watch._public = Public(intent, ())

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("live-source-read-forbidden")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    watch.check_snapshot(record)
    watch.emergency(record)
    assert watch.metadata()["cid_absent"] and watch.metadata()["volumes_restored"]
    assert watch.metadata()["held"] and not watch.metadata()["released"]


def test_anonymous_volume_decision_is_durable_before_v_and_final_has_new_kind(
    module, tmp_path, monkeypatch
):
    watch, _, record, _, intent = monitor(module, tmp_path)
    anonymous = "f" * 64
    public = Public(intent, (), [{"Type": "volume", "Name": anonymous}])
    original = public.invoke

    def invoke(action: Any, target: Any) -> Any:
        if action.value == "CID_REMOVE_V":
            paths = list(tmp_path.glob("volume-decision-*.json"))
            assert len(paths) == 1
            decision = json.loads(paths[0].read_bytes())
            assert decision["kind"] == "MASKGW_PG16_READER_VOLUME_DECISION_V1"
            assert decision["mode"] == "WITH_V" and decision["new_anonymous_names"] == [anonymous]
        return original(action, target)

    monkeypatch.setattr(public, "invoke", invoke)
    watch._public = public
    watch.emergency(record)
    final = json.loads(next(tmp_path.glob("volume-final-*.json")).read_bytes())
    assert final["kind"] == "MASKGW_PG16_READER_VOLUME_FINAL_V1"
    assert not public.present and not public.volumes
    assert watch.metadata()["volumes_restored"] and not watch.metadata()["released"]


@pytest.mark.parametrize("name", ["preexisting-named", "f" * 64])
def test_preexisting_volume_is_preserved_without_v(module, tmp_path, name):
    watch, _, record, _, intent = monitor(module, tmp_path, initial=(name,))
    public = Public(intent, (name,), [{"Type": "volume", "Name": name}])
    watch._public = public
    watch.emergency(record)
    assert "CID_REMOVE_V" not in public.calls and public.volumes == {name}
    assert watch.metadata()["volumes_restored"] and not watch.metadata()["released"]


@pytest.mark.parametrize("fault", ["alien-cid", "alien-command", "alien-task"])
def test_alien_inspect_never_kills_or_removes_container(module, tmp_path, fault):
    watch, _, record, _, intent = monitor(module, tmp_path)
    public = Public(intent, ())
    if fault == "alien-cid":
        public.info["Id"] = "d" * 64
    elif fault == "alien-command":
        public.info["Config"]["Cmd"] = ["unknown"]
    else:
        public.info["Config"]["Labels"]["maskgw.task"] = "b" * 32
    watch._public = public
    with pytest.raises(RuntimeError):
        watch.emergency(record)
    assert not {"CID_KILL", "CID_REMOVE", "CID_REMOVE_V"} & set(public.calls)
    assert watch.cleanup_lock.releases == 1 and watch.metadata()["held"]


@pytest.mark.parametrize("mode", ["new-named", "unknown", "already-absent"])
def test_uncertainty_or_difference_never_proves_volume_restore(module, tmp_path, mode):
    watch, _, record, _, intent = monitor(module, tmp_path)
    public = Public(intent, ())
    if mode == "new-named":
        public.info["Mounts"] = [{"Type": "volume", "Name": "new-named"}]
        public.volumes.add("new-named")
        public.named.add("new-named")
    elif mode == "unknown":
        public.info["Mounts"] = None
    else:
        public.present = False
        public.volumes.add("unrelated-new-volume")
    watch._public = public
    watch.emergency(record)
    assert watch.metadata()["held"] and not watch.metadata()["released"]
    if mode == "unknown":
        assert watch.metadata()["volume_uncertain"] and "CID_REMOVE_V" not in public.calls
    else:
        assert not watch.metadata()["volumes_restored"]
    assert "VOLUME_REMOVE" not in public.calls


def test_unknown_cli_identity_never_guesses_pid_and_lock_prevents_parallel_cleanup(
    module, tmp_path
):
    watch, _, record, _, intent = monitor(module, tmp_path)
    public = Public(intent, ())
    watch._public = public
    watch.cleanup_lock = Mutex(False)
    watch.emergency(replace(record, pid=None, filetime=None))
    assert public.calls == [] and watch.metadata()["category"] == "CLEANUP_LOCK"


def test_persistence_failure_before_rm_never_runs_rm(module, tmp_path, monkeypatch):
    watch, _, record, _, intent = monitor(module, tmp_path)
    public = Public(intent, ())
    watch._public = public

    def fsync(_fd: int) -> None:
        # The decision is the only file open at this point with this prefix.
        if list(tmp_path.glob("volume-decision-*.json")):
            raise OSError("fake-fsync")

    monkeypatch.setattr(module["os"], "fsync", fsync)
    with pytest.raises(OSError):
        watch.emergency(record)
    assert not {"CID_REMOVE", "CID_REMOVE_V"} & set(public.calls)
    assert public.present and not watch.metadata()["volumes_restored"]


def test_final_fsync_failure_cannot_set_restored_positive(module, tmp_path, monkeypatch):
    watch, _, record, _, intent = monitor(module, tmp_path)
    watch._public = Public(intent, ())

    def fsync(_fd: int) -> None:
        if list(tmp_path.glob("volume-final-*.json")):
            raise OSError("fake-final-fsync")

    monkeypatch.setattr(module["os"], "fsync", fsync)
    with pytest.raises(OSError):
        watch.emergency(record)
    assert not watch.metadata()["volumes_restored"] and watch.metadata()["held"]


def test_fake_thread_start_join_failures_preserve_held_without_native_thread(
    module, tmp_path, monkeypatch
):
    watch, _, _, _, _ = monitor(module, tmp_path)
    calls = []

    class Thread:
        def __init__(self, **kwargs: Any) -> None:
            assert kwargs["name"] == "maskgw-pg16-reader-watchdog"
            assert kwargs["daemon"] is False

        def start(self) -> None:
            raise OSError("fake-thread-start")

        def join(self, timeout: float) -> None:
            calls.append(timeout)

        def is_alive(self) -> bool:
            return True

    monkeypatch.setattr(module["threading"], "Thread", Thread)
    assert not watch.start() and watch.metadata()["held"]
    assert not watch.close() and calls == [55.0]
    assert watch.metadata()["category"] == "THREAD_JOIN_UNPROVEN"


def test_unchanged_algorithms_remain_ast_equivalent_except_public_names(module):
    before = ast.parse((REPO / "docs/poc/pg16_public_watchdog.py").read_bytes())
    after = ast.parse(Path(module["__file__"]).read_bytes())

    class Names(ast.NodeTransformer):
        def visit_Constant(self, node: ast.Constant) -> ast.AST:
            if type(node.value) is str:
                value = node.value.replace("MASKGW_PG16_READER_", "MASKGW_PG16_PUBLIC_")
                value = value.replace("maskgw-pg16-reader-watchdog", "maskgw-pg16-public-watchdog")
                return ast.copy_location(ast.Constant(value=value), node)
            return node

    for name in ("volume_sha256", "Observation", "reason", "namespace"):
        old = next(n for n in before.body if getattr(n, "name", None) == name)
        new = next(n for n in after.body if getattr(n, "name", None) == name)
        assert ast.dump(old) == ast.dump(new)
    old_class = next(n for n in before.body if isinstance(n, ast.ClassDef) and n.name == "Watchdog")
    new_class = next(n for n in after.body if isinstance(n, ast.ClassDef) and n.name == "Watchdog")
    for name in (
        "_write",
        "_call",
        "_remove_action",
        "_volume_final",
        "_absent",
        "run",
        "start",
        "close",
        "metadata",
    ):
        old = next(n for n in old_class.body if getattr(n, "name", None) == name)
        new = next(n for n in new_class.body if getattr(n, "name", None) == name)
        assert ast.dump(old) == ast.dump(Names().visit(new)), name
    old_store = next(n for n in before.body if isinstance(n, ast.ClassDef) and n.name == "Store")
    new_store = next(n for n in after.body if isinstance(n, ast.ClassDef) and n.name == "Store")
    for name in ("__init__", "pulse", "arm_b", "read"):
        old = next(n for n in old_store.body if getattr(n, "name", None) == name)
        new = next(n for n in new_store.body if getattr(n, "name", None) == name)
        assert ast.dump(old) == ast.dump(new), name


def test_constructor_refuses_nonmain_thread_without_starting_any_thread(
    module, tmp_path, monkeypatch
):
    monkeypatch.setattr(module["threading"], "current_thread", object)
    with pytest.raises(RuntimeError, match="PG16_READER_WATCHDOG_REFUSED"):
        monitor(module, tmp_path)


def test_fake_run_triggers_one_abort_and_stays_held_after_successful_cleanup(
    module, tmp_path, monkeypatch
):
    watch, store, record, aborts, intent = monitor(module, tmp_path)
    store.publish(record)
    watch._public = Public(intent, ())
    watch.stop = Event(False)
    monkeypatch.setitem(watch.run.__globals__, "time", SimpleNamespace(monotonic=lambda: 15.0))
    watch.run()  # synchronous fake run, NEVER Thread.start
    assert aborts == [True] and watch.metadata()["fired"] and watch.metadata()["held"]
    assert watch.metadata()["cid_absent"] and not watch.metadata()["released"]
    assert watch.ack.waits == [2.0]


@pytest.mark.parametrize("linked", [False, True])
def test_third_party_volume_name_is_never_published_in_watchdog_evidence(module, tmp_path, linked):
    name = "third-party-project-canary"
    watch, _, record, _, intent = monitor(module, tmp_path, initial=(name,))
    mounts = [{"Type": "volume", "Name": name}] if linked else []
    watch._public = Public(intent, (name,), mounts)
    watch.emergency(record)
    assert watch.metadata()["volumes_restored"]
    assert all(name.encode() not in path.read_bytes() for path in tmp_path.glob("*.json"))


def test_joined_fake_thread_is_not_release_or_absence_proof(module, tmp_path):
    watch, _, _, _, _ = monitor(module, tmp_path)
    joins = []

    class Thread:
        def join(self, timeout: float) -> None:
            joins.append(timeout)

        def is_alive(self) -> bool:
            return False

    watch._started = True
    watch.thread = Thread()
    assert watch.close() and joins == [55.0]
    assert watch.metadata()["thread_joined"] and not watch.metadata()["released"]
    assert not watch.metadata()["cid_absent"]


def test_snapshot_checks_command_type_before_any_caller_equality(module):
    calls = []

    class Text(str):
        __hash__ = str.__hash__

        def __eq__(self, _other: Any) -> bool:
            calls.append(True)
            return True

    with pytest.raises(RuntimeError, match="PG16_READER_WATCHDOG_REFUSED"):
        module["Snapshot"](TASK, "binary", (Text("-ec"), "public"), ())
    assert not calls
