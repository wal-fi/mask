"""Projection exporter against a full fake entry run. No Docker/native effects."""

import asyncio
import hashlib
import json
import runpy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_pg16_public_run import bound as binding_fixture
from tests.test_pg16_public_run import context as context_fixture
from tests.test_pg16_public_run import entry as entry_fixture

REPO = Path(__file__).resolve().parents[1]
TASK = "a" * 32
OTHER = "third_party_project_data"
bound = binding_fixture
context = context_fixture
entry = entry_fixture


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/pg16_public_export.py"))


def write(path: Path, data: Any) -> None:
    path.write_bytes(
        (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
    )


@pytest.fixture
def prepared(module: Any, entry: Any, context: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    value, engine, _, _ = context
    host = value.host
    root = value.root / ("maskgw-pg16-public-20261030-" + "b" * 32)
    root.mkdir()
    value.root = host.root = root
    prep = runpy.run_path(str(REPO / "docs/poc/pg16_public_prepare.py"))
    value.state.update(prep["state_for"](TASK))
    value.state.update(phase="INVOKED", invoked=True)  # fake admission, before the real entry flow
    write(
        root / "invoked.json",
        {
            "kind": "MASKGW_PG16_PUBLIC_INVOKED_V1",
            "task": TASK,
            "host_sha256": entry["HOST_SHA"],
            "entry_sha256": prep["ENTRY_SHA"],
        },
    )
    original_cli = engine.cli

    async def recorded(label: str, *args: Any, **kwargs: Any) -> Any:
        code, raw = await original_cli(label, *args, **kwargs)
        host.commands.append(
            {
                "label": label,
                "exit": code,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "seconds": 0.0,
            }
        )
        return code, raw

    engine.cli = recorded
    factory = host.pg["owner"]["PublicProbeOwner"]

    def owner(target: Any) -> Any:
        item = factory(target)
        item.metadata = lambda: {
            "phase": "CLOSED" if item.released else "OPEN",
            "role": "P",
            "cid": target.cid,
            "fault": None,
            "seed_delivery": "NOT_SENT",
            "released": item.released,
        }
        return item

    monkeypatch.setitem(host.pg["owner"], "PublicProbeOwner", owner)
    restore = host.restore_desktop

    async def restored() -> None:
        await restore()
        host.result["desktop_state"] = "PRESERVED_ACTIVE"

    host.restore_desktop = restored
    public = root.parent / "public"
    public.mkdir()
    destination = public / ("pg16-public-run-20261030-" + TASK[:12])
    monkeypatch.setitem(module["_export"].__globals__, "TEMP_ROOT", root.parent)
    monkeypatch.setitem(module["_export"].__globals__, "OUTPUT_PARENT", public)
    return value, engine, root, destination


@pytest.fixture
def complete(entry: Any, prepared: Any) -> Any:
    value, engine, root, destination = prepared
    assert asyncio.run(entry["run"](value)) == 0
    return root, destination, engine


def test_export_replays_full_cycle_and_publishes_only_closed_projection(module, complete):
    root, destination, _ = complete
    manifest = module["export"](root, destination, 0)
    assert {p.name for p in destination.iterdir()} == {"summary.json", "transport.json"}
    summary = json.loads((destination / "summary.json").read_bytes())
    assert set(summary) == {
        "kind",
        "task",
        "entry_sha256",
        "host_sha256",
        "reported_exit",
        "outcome",
        "resources",
        "cycle",
        "commands",
        "image",
        "cid",
        "profile_observations",
        "post_execution_state",
        "probe",
        "owner",
        "volumes",
        "watchdog",
        "desktop",
        "diagnostics",
    }
    assert summary["cycle"]["checkpoint_count"] == 12
    assert summary["cycle"]["interval_a_b_ms"] == 110000 and summary["cycle"]["boot_equal"] is True
    assert summary["probe"]["uid"] == summary["probe"]["gid"] == 70
    assert summary["image"]["pg_version"] == "16.15"
    assert summary["owner"]["phase"] == "CLOSED" and summary["owner"]["seed_delivery"] == "NOT_SENT"
    assert summary["post_execution_state"] == {
        "Running": False,
        "Pid": 0,
        "OOMKilled": False,
        "Dead": False,
        "ExitCode": 0,
    }
    assert all(set(row) == {"label", "exit", "bytes", "sha256"} for row in summary["commands"])
    assert manifest["published_source_count"] == 0 and manifest["withheld_source_count"] == len(
        list(root.iterdir())
    )
    assert all(row["published"] is False for row in manifest["files"])
    assert (root / "local-volume-baseline.json").exists()
    for path in destination.iterdir():
        assert OTHER.encode() not in path.read_bytes()
    assert (
        hashlib.sha256((destination / "summary.json").read_bytes()).hexdigest()
        == manifest["derived_artifacts"][0]["sha256"]
    )


def test_empty_volume_inventory_does_not_alias_ps_or_create_replies(module, entry, prepared):
    value, engine, root, destination = prepared
    engine.volumes.clear()
    assert asyncio.run(entry["run"](value)) == 0
    module["export"](root, destination, 0)
    summary = json.loads((destination / "summary.json").read_bytes())
    assert summary["volumes"]["initial_count"] == 0 and summary["volumes"]["status"] == "RESTORED"


def test_failed_profile_is_not_success_but_restored_resources_allow_diagnostic(
    module, entry, prepared
):
    value, engine, root, destination = prepared
    engine.mounts = [{"Type": "volume", "Name": "d" * 64}]
    assert asyncio.run(entry["run"](value)) == 1 and value.released
    module["export"](root, destination, 1)
    summary = json.loads((destination / "summary.json").read_bytes())
    assert summary["outcome"] == "NOT_PASSED" and summary["probe"] is None
    assert summary["diagnostics"]["failure"] == {"category": "MOUNTS", "origin": "PROBE"}
    assert any(
        row["accepted"] is False and row["groups"]["mounts"] is False
        for row in summary["profile_observations"]
    )
    assert summary["volumes"]["decisions"][0]["new_anonymous_names"] == ["d" * 64]


def test_volume_inventory_not_admitted_is_unknown_not_empty_or_restored(module, entry, prepared):
    value, engine, root, destination = prepared
    engine.volume_code = 1
    assert asyncio.run(entry["run"](value)) == 1 and value.released
    module["export"](root, destination, 1)
    summary = json.loads((destination / "summary.json").read_bytes())
    assert summary["volumes"]["status"] == "NOT_ADMITTED"
    assert summary["volumes"]["initial_count"] is None and summary["volumes"]["final_count"] is None
    assert summary["resources"]["volumes_restored"] is False


@pytest.mark.parametrize("phase", ["HELD", "FRESH", "INVOKED"])
def test_nonterminal_roots_never_publish(module, complete, phase):
    root, destination, _ = complete
    state = json.loads((root / "attempt.json").read_bytes())
    state["phase"] = phase
    write(root / "attempt.json", state)
    with pytest.raises(module["ExportError"], match="EXPORT_TERMINAL"):
        module["export"](root, destination, 0)
    assert not destination.exists()


@pytest.mark.parametrize(
    "field", ["owned_cleanup", "inventory_restored", "desktop_restored", "volumes_restored"]
)
def test_missing_resource_proof_refuses_before_destination(module, complete, field):
    root, destination, _ = complete
    result = json.loads((root / "result.json").read_bytes())
    result[field] = False
    write(root / "result.json", result)
    with pytest.raises(module["ExportError"], match="EXPORT_RESOURCE"):
        module["export"](root, destination, 0)
    assert not destination.exists()


@pytest.mark.parametrize("fault", ["pin", "task", "extra-state", "image", "measurement"])
def test_state_tampering_cannot_be_published(module, complete, fault):
    root, destination, _ = complete
    state = json.loads((root / "attempt.json").read_bytes())
    if fault == "pin":
        state["entry_sha256"] = "0" * 64
    elif fault == "task":
        state["task"] = "f" * 32
    elif fault == "image":
        state["image"] = "sha256:" + "0" * 64
    elif fault == "measurement":
        state["create_measurement"]["margin_chars"] -= 1
    else:
        state["extra"] = "synthetic-private"
    write(root / "attempt.json", state)
    with pytest.raises(module["ExportError"]):
        module["export"](root, destination, 0)
    assert not destination.exists()


@pytest.mark.parametrize(
    "fault",
    [
        "raw-sha",
        "alias",
        "extra-manifest",
        "owner-cid",
        "journal",
        "report",
        "volume-extra",
        "volume-name",
    ],
)
def test_capture_owner_journal_and_volume_tampering_refused(module, complete, fault):
    root, destination, _ = complete
    if fault in ("raw-sha", "alias", "extra-manifest"):
        path = root / "public-cli-manifest.json"
        data = json.loads(path.read_bytes())
        row = next(row for row in data if row["artifact"] is not None)
        if fault == "raw-sha":
            row["sha256"] = "0" * 64
        elif fault == "alias":
            row["artifact"] = "local-volume-baseline.json"
        else:
            row["unapproved"] = True
    elif fault == "owner-cid":
        path = root / "ownership.json"
        data = json.loads(path.read_bytes())
        data[0]["cid"] = "e" * 64
    elif fault == "journal":
        path = root / "checkpoint-03.json"
        data = json.loads(path.read_bytes())
        data["previous_sha256"] = "0" * 64
    elif fault == "report":
        path = root / "pg16-public-report.json"
        data = json.loads(path.read_bytes())
        data["uid"] = 10001
    else:
        path = next(root.glob("volume-decision-*.json"))
        data = json.loads(path.read_bytes())
        if fault == "volume-extra":
            data["preexisting_names"] = [OTHER]
        else:
            data["new_anonymous_names"] = [OTHER]
    write(path, data)
    with pytest.raises(module["ExportError"]):
        module["export"](root, destination, 0)
    assert not destination.exists()


def test_arbitrary_metadata_is_not_copied_and_no_local_raw_is_ever_published(module, complete):
    root, destination, _ = complete
    result = json.loads((root / "result.json").read_bytes())
    result["notes"] = "SYNTHETIC_NOT_A_REAL_SECRET"
    write(root / "result.json", result)
    module["export"](root, destination, 0)
    assert all(
        b"SYNTHETIC_NOT_A_REAL_SECRET" not in path.read_bytes() for path in destination.iterdir()
    )
    assert not any(path.name.startswith("local-") for path in destination.iterdir())


def test_unknown_file_and_existing_destination_preserved(module, complete):
    root, destination, _ = complete
    bad = root / "unapproved.json"
    bad.write_bytes(b"public-sentinel")
    with pytest.raises(module["ExportError"], match="EXPORT_ARTIFACT"):
        module["export"](root, destination, 0)
    bad.unlink()  # test-only file, never an operational artifact
    destination.mkdir()
    (destination / "notes.txt").write_bytes(b"preserve-existing")
    with pytest.raises(module["ExportError"], match="EXPORT_DESTINATION"):
        module["export"](root, destination, 0)
    assert (destination / "notes.txt").read_bytes() == b"preserve-existing"


@pytest.mark.parametrize("boundary", [1, 2])
def test_transport_manifest_is_not_published_when_its_fsync_fails(
    module, complete, monkeypatch, boundary
):
    root, destination, _ = complete
    calls = []
    fsync = module["os"].fsync

    def fail(fd: int) -> None:
        calls.append(fd)
        if len(calls) == boundary:
            raise OSError("synthetic-fsync-failure")
        fsync(fd)

    monkeypatch.setattr(module["os"], "fsync", fail)
    with pytest.raises(module["ExportError"]) as caught:
        module["export"](root, destination, 0)
    assert len(calls) == boundary
    assert not (destination / "transport.json").exists()
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert "synthetic" not in str(caught.value)


@pytest.mark.parametrize("fault", ["baseline-bool", "desktop", "intent-flag", "uncertain-int"])
def test_projection_rejects_contradictory_or_wrong_typed_proof(module, complete, fault):
    root, destination, _ = complete
    if fault == "baseline-bool":
        path = next(root.glob("volume-baseline-*.json"))
        data = json.loads(path.read_bytes())
        data["count"] = True  # initial_count is 1: equality alone is insufficient
    elif fault == "desktop":
        path = root / "result.json"
        data = json.loads(path.read_bytes())
        data["desktop_state"] = "OFF_CONFIRMED"  # initial_active is True
    else:
        path = root / "ownership.json"
        data = json.loads(path.read_bytes())
        data[0]["intent_persisted" if fault == "intent-flag" else "volume_uncertain"] = (
            False if fault == "intent-flag" else 0
        )
    write(path, data)
    with pytest.raises(module["ExportError"]):
        module["export"](root, destination, 0)
    assert not destination.exists()


def test_unknown_volume_mode_cannot_be_hidden_by_false_final_flags(module, entry, prepared):
    value, engine, root, destination = prepared
    engine.mounts = [{"Type": "volume", "Name": "d" * 64}]
    assert asyncio.run(entry["run"](value)) == 1
    manifest_path = root / "public-cli-manifest.json"
    result_path = root / "result.json"
    manifest = json.loads(manifest_path.read_bytes())
    result = json.loads(result_path.read_bytes())
    for row in manifest:
        if row["artifact"] is None:
            continue
        path = root / row["artifact"]
        try:
            raw = json.loads(path.read_bytes())
        except json.JSONDecodeError:
            continue
        if (
            type(raw) is not list
            or not raw
            or type(raw[0]) is not dict
            or raw[0].get("Id") != "c" * 64
        ):
            continue
        old_hash = row["sha256"]
        raw[0]["Mounts"] = [{"Type": "unknown"}]
        write(path, raw)
        row.update(
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=len(path.read_bytes())
        )
        for command in result["commands"]:
            if command["sha256"] == old_hash:
                command.update(sha256=row["sha256"], bytes=row["bytes"])
    write(manifest_path, manifest)
    write(result_path, result)
    for path in root.glob("volume-decision-*.json"):
        data = json.loads(path.read_bytes())
        data.update(
            mode="PRESERVE_UNCERTAIN",
            linked_count=0,
            preexisting_count=0,
            linked_sha256=hashlib.sha256(b"[]\n").hexdigest(),
            preexisting_sha256=hashlib.sha256(b"[]\n").hexdigest(),
            new_anonymous_names=[],
        )
        write(path, data)
    with pytest.raises(module["ExportError"]):
        module["export"](root, destination, 1)
    assert not destination.exists()


@pytest.mark.parametrize("syntax", ["duplicate", "nan"])
def test_non_json_or_duplicate_metadata_refused_even_in_uncopied_fields(module, complete, syntax):
    root, destination, _ = complete
    path = root / "result.json"
    raw = path.read_bytes()
    extra = b'"outcome":"PG16_PUBLIC_VERIFIED",' if syntax == "duplicate" else b'"unapproved":NaN,'
    path.write_bytes(b"{" + extra + raw[1:])
    with pytest.raises(module["ExportError"], match="EXPORT_JSON"):
        module["export"](root, destination, 0)
    assert not destination.exists()


@pytest.mark.parametrize("limit", ["file", "total", "count"])
def test_artifact_limits_refused_before_publication(module, complete, limit):
    root, destination, _ = complete
    if limit == "file":
        (root / "local-cli-999.bin").write_bytes(b"A" * (4194304 + 1))
    elif limit == "total":
        for index in range(990, 995):
            (root / ("local-cli-" + str(index) + ".bin")).write_bytes(b"A" * 4194304)
    else:
        for index in range(400, 657):
            (root / ("local-cli-" + str(index) + ".bin")).write_bytes(b"public")
    with pytest.raises(module["ExportError"], match=r"EXPORT_ARTIFACT|EXPORT_SIZE"):
        module["export"](root, destination, 0)
    assert not destination.exists()


@pytest.mark.parametrize("target", ["root", "source"])
def test_reparse_flag_refused_without_following_the_source(module, complete, monkeypatch, target):
    root, destination, _ = complete
    path = root if target == "root" else root / "local-probe-output.bin"
    lstat = Path.lstat

    def flagged(item: Path) -> Any:
        info = lstat(item)
        return (
            SimpleNamespace(st_mode=info.st_mode, st_size=info.st_size, st_file_attributes=0x400)
            if item == path
            else info
        )

    monkeypatch.setattr(Path, "lstat", flagged)
    with pytest.raises(module["ExportError"], match=r"EXPORT_ROOT|EXPORT_ARTIFACT"):
        module["export"](root, destination, 0)
    assert not destination.exists()


def test_source_changed_on_recheck_does_not_publish(module, complete, monkeypatch):
    root, destination, _ = complete
    original = module["regular"]
    reads = []

    def changed(path: Path, maximum: int = 4194304) -> bytes:
        raw = original(path, maximum)
        assert isinstance(raw, bytes)
        if path == root / "result.json":
            reads.append(path)
            if len(reads) == 2:
                return raw + b" "
        return raw

    monkeypatch.setitem(module["_export"].__globals__, "regular", changed)
    with pytest.raises(module["ExportError"], match="EXPORT_CHANGED"):
        module["export"](root, destination, 0)
    assert len(reads) == 2 and not destination.exists()


def test_final_rename_failure_keeps_incomplete_marker_and_sanitizes_error(
    module, complete, monkeypatch
):
    root, destination, _ = complete

    def fail(_source: Path, _target: Path) -> None:
        raise OSError("synthetic-private-rename-error")

    monkeypatch.setattr(module["os"], "rename", fail)
    with pytest.raises(module["ExportError"], match="EXPORT_IO") as caught:
        module["export"](root, destination, 0)
    assert (destination / "transport.json.next").is_file()
    assert not (destination / "transport.json").exists()
    assert caught.value.__context__ is None and caught.value.__cause__ is None
