"""Five-hook revision, shared frozen fakes, no Desktop/Docker/clock."""

import ast
import asyncio
import hashlib
import inspect
import json
import runpy
import textwrap
from copy import deepcopy
from pathlib import Path
from types import MethodType
from typing import Any

import pytest

from tests.test_oracle9_w1_run import lab as original_lab_fixture
from tests.test_oracle9_w1_run import native_lab as original_native_fixture

REPO = Path(__file__).resolve().parents[1]
lab = original_lab_fixture
native_lab = original_native_fixture


@pytest.fixture
def module() -> Any:
    current = runpy.run_path(str(REPO / "docs/poc/oracle9_w1_run_v2.py"))
    return current["R"] | current


@pytest.fixture
def native_v2(module: Any, native_lab: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    host, model = native_lab
    fake = host.cli

    async def invoke(label, args, timeout, limit, *, cleanup=False):
        assert args[:3] == [str(module["CLI"]), "--context", "desktop-linux"]
        if label in ("inspect-install", "inspect-probe"):
            role = label.removeprefix("inspect-")
            counts = model.setdefault("inspect_counts", {})
            counts[role] = counts.get(role, 0) + 1
            if model.get("extra_at_inspection") == (role, counts[role]):
                for info in model["containers"].values():
                    if (info["Config"]["User"] == "10001:10001") is (role == "probe"):
                        info["Config"]["Labels"]["unexpected.presentation"] = "public"
        result = await fake(label, *args[3:], timeout=timeout, limit=limit, cleanup=cleanup)
        if label.startswith("create-"):
            for info in model["containers"].values():
                info["Config"]["Labels"].pop("desktop.docker.io/ports.scheme", None)
                role = "probe" if info["Config"]["User"] == "10001:10001" else "install"
                if model.get("extra_role") == role:
                    info["Config"]["Labels"]["unexpected.presentation"] = "public"
                if model.get("bad_limit_role") == role:
                    info["HostConfig"]["Memory"] = 0
        return result

    monkeypatch.setattr(host, "invoke", invoke)
    monkeypatch.setattr(host, "cli", MethodType(module["Host"].cli, host))
    return host, model


def test_exactly_five_overrides_and_all_other_functions_are_inherited(module):
    new, old = module["Host"], module["BaseHost"]
    overrides = {k for k, v in new.__dict__.items() if callable(v)}
    assert overrides == {"save", "cli", "inspect_own", "watchdog", "pins"}
    for name, function in old.__dict__.items():
        if callable(function) and name not in overrides:
            assert getattr(new, name) is function


def test_watchdog_ast_diff_is_only_the_ownership_block(module):
    old = ast.parse(textwrap.dedent(inspect.getsource(module["BaseHost"].watchdog)))
    new = ast.parse(textwrap.dedent(inspect.getsource(module["Host"].watchdog)))

    def normalize(tree: ast.Module, legacy: bool) -> str:
        inner = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef))
        index = next(
            i
            for i, n in enumerate(inner.body)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "cid" for t in n.targets)
        )
        inner.body[index : index + (2 if legacy else 1)] = [ast.Pass()]
        return ast.dump(tree, include_attributes=False)

    assert normalize(old, True) == normalize(new, False)


def test_two_pins_are_checked_without_mutating_either(module, tmp_path, monkeypatch):
    state = {
        "task": "f" * 32,
        "program_sha256": module["ORIGINAL_SHA"],
        "entry_sha256": "a" * 64,
        "pins": dict(module["R"]["LIBRARIES"].values()),
    }
    host = module["Host"](tmp_path, state)
    before = deepcopy(state)
    calls = []

    def inner(_host, cleanup=False):
        assert cleanup is True and state == before
        calls.append("inner")

    def pin(path, expected):
        assert (
            path.name == "oracle9_w1_run_v2.py"
            and expected == state["entry_sha256"]
            and state == before
        )
        calls.append("outer")

    monkeypatch.setattr(module["BaseHost"], "pins", inner)
    monkeypatch.setitem(module["R"], "pinned", pin)
    host.pins(cleanup=True)
    assert calls == ["inner", "outer"] and state == before


def test_twelve_checkpoints_from_inherited_cycle_replay_before_b_effect(module, lab):
    host, _, _, _ = lab
    asyncio.run(host.start_cycle())
    state, head = module["journal_from_disk"](host)
    records = host._checkpoint_records
    assert len(records) == 12 and state.phase.value == "B_CONSUMED"
    assert json.loads(records[0])["action"] == "START"
    assert [json.loads(raw)["action"] for raw in records[1:]] == ["OBSERVE"] * 9 + ["READY", "B"]
    assert head == hashlib.sha256(records[-1]).hexdigest()
    host.save("cycle.json", json.loads(host.libs["core"]["encode"](state)))
    assert len(host._checkpoint_records) == 12  # abort after B cannot duplicate


@pytest.mark.parametrize(
    "fault", ["chain", "action", "sample", "state", "index", "extra", "noncanonical"]
)
def test_replay_refuses_modified_or_reordered_evidence(module, lab, fault):
    host, _, _, _ = lab
    asyncio.run(host.start_cycle())
    records = list(host._checkpoint_records)
    value = json.loads(records[-1])
    if fault == "chain":
        value["previous_sha256"] = "0" * 64
    elif fault == "action":
        value["action"] = "OBSERVE"
    elif fault == "sample":
        value["sample"]["utc_100ns"] = str(int(value["sample"]["utc_100ns"]) + 1)
    elif fault == "state":
        value["state_encoded"] = value["state_encoded"].replace("B_CONSUMED", "READY")
    elif fault == "index":
        value["index"] = True
    elif fault == "extra":
        value["unexpected"] = "public"
    records[-1] = module["R"]["json_bytes"](value) + (b" " if fault == "noncanonical" else b"")
    reasons = {
        "chain": "JOURNAL_CHAIN",
        "action": "JOURNAL_ADMISSION",
        "sample": "JOURNAL_STATE",
        "state": "JOURNAL_STATE",
        "index": "JOURNAL_CHAIN",
        "extra": "JOURNAL_SCHEMA",
        "noncanonical": "JOURNAL_SCHEMA",
    }
    with pytest.raises(RuntimeError, match="^" + reasons[fault] + "$"):
        module["replay"](host.libs["core"], records)


@pytest.mark.parametrize("fault", ["state", "head"])
def test_disk_replay_must_match_live_state_and_last_memory_record(module, lab, fault):
    host, _, _, _ = lab
    asyncio.run(host.start_cycle())
    if fault == "state":
        host.cycle = host.libs["core"]["decode"](
            json.loads(host._checkpoint_records[-2])["state_encoded"].encode()
        )
    else:
        host._checkpoint_records = (
            *host._checkpoint_records[:-1],
            host._checkpoint_records[-1] + b" ",
        )
    with pytest.raises(RuntimeError, match="JOURNAL_BINDING"):
        module["journal_from_disk"](host)


def test_journal_collision_prevents_later_effect_and_never_overwrites(lab):
    host, model, _, _ = lab
    path = host.root / "checkpoint-01.json"
    path.write_bytes(b"preserve")
    with pytest.raises(FileExistsError):
        asyncio.run(host.start_cycle())
    assert path.read_bytes() == b"preserve"
    assert "version" not in model["calls"] and "B" not in model["calls"]


def test_rejected_sample_has_separate_immutable_link_not_false_checkpoint(module, lab, monkeypatch):
    host, model, _, _ = lab
    old = host.sample
    count = 0

    async def sample():
        nonlocal count
        count += 1
        if count == 4:
            model["boot"] = "134372287595000001"
        return await old()

    monkeypatch.setattr(host, "sample", sample)
    with pytest.raises(RuntimeError, match="CYCLE_REFUSED"):
        asyncio.run(host.start_cycle())
    assert len(host._checkpoint_records) == 3
    rejected = json.loads((host.root / "checkpoint-rejected.json").read_bytes())
    assert (
        rejected["reason"] == "BOOT"
        and rejected["previous_sha256"] == hashlib.sha256(host._checkpoint_records[-1]).hexdigest()
    )
    module["replay"](host.libs["core"], host._checkpoint_records, require_b=False)


def test_three_label_native_fake_lot_and_explicit_commit_label(module, native_v2):
    host, model = native_v2
    asyncio.run(host.perform_b())
    asyncio.run(host.cleanup_owned())
    assert host.result["update_verified"] is True and host.result["owned_cleanup"] is True
    args = json.loads((host.root / "commit-arguments.json").read_bytes())
    assert args[-4:] == ["--change", "LABEL desktop.docker.io/ports.scheme=v2", "c" * 64, host.tag]
    assert not model["containers"] and model["candidate"] is not None
    module["journal_from_disk"](host)


@pytest.mark.parametrize("role", ["install", "probe"])
@pytest.mark.parametrize("fault", ["extra_role", "bad_limit_role"])
def test_acceptance_refuses_but_cleanup_removes_owned_cids(native_v2, role, fault):
    host, model = native_v2
    model[fault] = role
    with pytest.raises(RuntimeError):
        asyncio.run(host.perform_b())
    asyncio.run(host.cleanup_owned())
    assert not model["containers"] and model["candidate"] is None
    assert host.result["owned_cleanup"] is True
    assert not host.result.get("update_verified")


def test_wrong_own_label_remains_foreign_and_is_preserved(native_v2):
    host, model = native_v2
    model["fault"] = "foreign"
    with pytest.raises(RuntimeError):
        asyncio.run(host.perform_b())
    asyncio.run(host.cleanup_owned())
    assert model["containers"] and host.result["owned_cleanup"] is False
    assert "remove-own" not in [label for label, _, _ in model["effects"]]


def test_ambiguous_create_with_extra_label_still_has_owned_cleanup(native_v2):
    host, model = native_v2
    model.update(fault="create_ambiguous", extra_role="install")
    with pytest.raises(RuntimeError):
        asyncio.run(host.perform_b())
    asyncio.run(host.cleanup_owned())
    assert not model["containers"] and host.result["owned_cleanup"] is True


@pytest.mark.parametrize(
    "role,inspection,blocked",
    [
        ("install", 2, "copy-public-inputs"),
        ("install", 3, "run-install"),
        ("install", 4, "copy-attestation"),
        ("install", 5, "copy-attestation"),
        ("install", 6, "commit-own"),
        ("probe", 2, "run-probe"),
        ("probe", 3, "probe-diff"),
    ],
)
def test_every_normal_caller_requires_acceptance_before_following_effect(
    native_v2, role, inspection, blocked
):
    host, model = native_v2
    model["extra_at_inspection"] = (role, inspection)
    with pytest.raises(RuntimeError, match="CONTAINER_LABELS_EXACT"):
        asyncio.run(host.perform_b())
    assert blocked not in [label for label, _, _ in model["effects"]]
    asyncio.run(host.cleanup_owned())
    assert host.result["owned_cleanup"] is True and not model["containers"]


def test_cli_other_calls_are_unmodified_and_malformed_commit_never_reaches_cli(native_v2):
    host, model = native_v2
    args = ("ps", "-aq", "--filter", "id=" + "a" * 64)
    asyncio.run(host.cli("other-readonly", *args, cleanup=True))
    assert model["effects"][-1][1] == args
    count = len(model["effects"])
    with pytest.raises(RuntimeError, match="COMMIT_OWNER"):
        asyncio.run(host.cli("commit-own", "commit", "bad"))
    assert len(model["effects"]) == count and not (host.root / "commit-arguments.json").exists()


def test_main_refuses_corrupt_disk_journal_before_body(module, lab, monkeypatch):
    host, model, _, _ = lab
    state = host.state
    state.update(
        program_sha256=module["ORIGINAL_SHA"], entry_sha256="a" * 64, invoked=False, phase="FRESH"
    )
    state["create_measurements"] = module["R"]["measure_commands"](host)
    globals_ = module["main"].__globals__
    monkeypatch.setitem(globals_, "admit", lambda _root: state)
    monkeypatch.setitem(globals_, "Host", lambda _root, _state: host)
    replay_disk = module["journal_from_disk"]

    def corrupt_then_replay(target):
        path = target.root / "checkpoint-11.json"
        path.write_bytes(path.read_bytes() + b" ")
        return replay_disk(target)

    async def body():
        model["calls"].append("BODY_MUST_NOT_RUN")

    async def cleanup():
        host.result.update(owned_cleanup=True, inventory_restored=True)

    async def restore():
        host.result["desktop_restored"] = True

    monkeypatch.setitem(globals_, "journal_from_disk", corrupt_then_replay)
    monkeypatch.setattr(host, "perform_b", body)
    monkeypatch.setattr(host, "cleanup_owned", cleanup)
    monkeypatch.setattr(host, "restore_desktop", restore)
    assert asyncio.run(module["main"](host.root)) == 1
    assert "BODY_MUST_NOT_RUN" not in model["calls"]
    assert len(host._checkpoint_records) == 12
    assert json.loads((host.root / "result.json").read_bytes())["outcome"] == "NOT_PASSED"


@pytest.mark.parametrize("role", ["install", "probe"])
def test_watchdog_ownership_allows_extra_label_but_no_foreign_command(
    module, native_v2, monkeypatch, role
):
    host, model = native_v2
    asyncio.run(host.perform_b())
    record = next(r for r in host.records if r["role"] == role)
    info = model["containers"][record["cid"]]
    info["Config"]["Labels"]["extra"] = "public"
    info["State"].update(Running=True, Pid=9)
    host.active = record
    calls = []

    class Expired:
        def wait(self, seconds):
            assert seconds == 600
            return False

    async def bounded(args, **kwargs):
        assert kwargs["timeout"] == 10
        calls.append(args)
        return (0, json.dumps([info]).encode()) if "inspect" in args else (0, b"owned")

    monkeypatch.setitem(
        host.libs["bounded"] if "bounded" in host.libs else host.libs.setdefault("bounded", {}),
        "bounded",
        bounded,
    )
    host.stop = Expired()
    host.watchdog()
    assert len(calls) == 2 and calls[-1][-4:] == ["kill", "--signal", "KILL", record["cid"]]
    calls.clear()
    info["Config"]["Cmd"] = ["foreign"]
    host.watchdog_failed = False
    host.watchdog()
    assert len(calls) == 1 and host.watchdog_failed is True
    host.stop = module["R"]["threading"].Event()
    info["Config"]["Cmd"] = record["command"]
    info["State"].update(Running=False, Pid=0)
    asyncio.run(host.cleanup_owned())
