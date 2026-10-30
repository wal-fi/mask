"""Closed public projections and prefix delta; no Docker/pip or app execution."""

import hashlib
import json
import runpy
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "docs/poc/oracle9_w1_context.py"
m = runpy.run_path(str(SOURCE))


@pytest.fixture
def inputs() -> Any:
    # Public frozen reports, NOT an imported app, installed prefix or wheel read.
    old = json.loads(
        (REPO / "docs/poc/evidence/oracle9-installed-attestation-20261026.json").read_bytes()
    )
    old_wheel = json.loads(
        (REPO / "docs/poc/evidence/oracle9-app-wheel-result-20261026.json").read_bytes()
    )
    new_wheel = json.loads(
        (REPO / "docs/poc/evidence/oracle9-w1-app-wheel-result-20261026.json").read_bytes()
    )
    projector = m["frozen"](m["PROJECTOR"], m["PROJECTOR_SHA"])
    old_files, _ = projector["installed_projection"]([old_wheel["inspection"]])
    new_files, _ = projector["installed_projection"]([new_wheel["inspection"]])
    return old, old_files, new_files


def prefix_pair(inputs: Any) -> Any:
    old, _, projection = inputs
    before = deepcopy(old["installed_snapshot"])
    after = deepcopy(before)
    for name, item in projection.items():
        path = m["SITE"] + name
        row = dict(after.get(path, {"kind": "file", "mode": 0o644, "uid": 0, "gid": 0}))
        row.update(bytes=item["bytes"], sha256=item["sha256"])
        if item["rewritten_record"]:
            # The private pip RECORD verifier has its OWN proof. Model a changed
            # rewritten record here; never claim this row came from installation.
            row.update(bytes=12345, sha256=hashlib.sha256(b"MODEL_REWRITTEN_RECORD").hexdigest())
        after[path] = row
    return before, after, projection


def test_projection_preserves_other_owners_and_exact_counts(inputs):
    old, old_files, new_files = inputs
    original = deepcopy(old)
    target = m["target_projection"](old, old_files, new_files)
    assert old == original and len(target["installed_files"]) == 1387
    assert target["console_scripts"] == old["manifest"]["console_scripts"]
    assert target["base_tools"] == old["manifest"]["base_tools"]
    before = {k: v for k, v in old["manifest"]["installed_files"].items() if v["owner"] != "maskgw"}
    assert {k: v for k, v in target["installed_files"].items() if v["owner"] != "maskgw"} == before
    assert [r for r in target["wheels"] if r["name"] != "maskgw"] == [
        r for r in old["manifest"]["wheels"] if r["name"] != "maskgw"
    ]
    own = next(r for r in target["wheels"] if r["name"] == "maskgw")
    assert own["sha256"] == m["WHEEL_SHA"] and own["bytes"] == m["WHEEL_BYTES"]


@pytest.mark.parametrize("field,value", [("sha256", "0" * 64), ("bytes", 1)])
def test_origin_wheel_row_is_bound_explicitly_before_replacement(inputs, field, value):
    old, old_files, new_files = inputs
    next(row for row in old["manifest"]["wheels"] if row["name"] == "maskgw")[field] = value
    with pytest.raises(RuntimeError, match=r"^ORIGIN_WHEEL$"):
        m["target_projection"](old, old_files, new_files)


@pytest.mark.parametrize(
    "mode",
    ["origin", "new_owner", "extra", "missing", "unexpected_change", "same_version", "base_tools"],
)
def test_projection_rejects_contract_mutations(inputs, mode):
    old, old_files, new_files = inputs
    if mode == "origin":
        old_files["maskgw/__init__.py"]["sha256"] = "0" * 64
    elif mode == "new_owner":
        new_files["maskgw/runtime/linux_guard.py"]["owner"] = "other"
    elif mode == "extra":
        new_files["maskgw/unknown.py"] = dict(new_files["maskgw/__init__.py"])
    elif mode == "missing":
        del new_files["maskgw/runtime/worker_session.py"]
    elif mode == "unexpected_change":
        new_files["maskgw/__init__.py"]["sha256"] = "0" * 64
    elif mode == "same_version":
        next(r for r in old["manifest"]["wheels"] if r["name"] == "maskgw")["version"] = "0.2.0"
    else:
        old["manifest"]["base_tools"]["pip"] = "999"
    expected = {
        "origin": "ORIGIN_APP",
        "new_owner": "NEW_OWNER",
        "extra": "MEMBERS",
        "missing": "MEMBERS",
        "unexpected_change": "APP_BYTE_DELTA",
        "same_version": "WHEEL_NAME",
        "base_tools": "BASE_TOOLS",
    }[mode]
    with pytest.raises(RuntimeError, match=rf"^{expected}$"):
        m["target_projection"](old, old_files, new_files)


def test_exact_prefix_delta_and_independent_record_verifier_boundary(inputs):
    before, after, projection = prefix_pair(inputs)
    m["check_delta"](before, after, projection)
    assert len(after) == 3337


@pytest.mark.parametrize(
    "mode",
    [
        "other_record",
        "other_mode",
        "base_link",
        "app_extra",
        "remove",
        "unplanned_bytes",
        "changed_mode",
        "changed_uid",
        "new_mode",
        "new_hash",
        "app_directory",
    ],
)
def test_exact_prefix_delta_catches_changes_record_consistency_alone_misses(inputs, mode):
    before, after, projection = prefix_pair(inputs)
    site = m["SITE"]
    if mode.startswith("other_"):
        path = next(k for k in after if k.endswith(".dist-info/RECORD") and not m["in_app"](k))
        after[path]["sha256" if mode == "other_record" else "mode"] = (
            "0" * 64 if mode == "other_record" else 0o666
        )
    elif mode == "base_link":
        after["lib64"]["target"] = "../escape"
    elif mode == "app_extra":
        after[site + "maskgw/unknown.py"] = dict(after[site + "maskgw/__init__.py"])
    elif mode == "remove":
        del after[site + "maskgw/__init__.py"]
    elif mode == "unplanned_bytes":
        after[site + "maskgw/__init__.py"]["sha256"] = "0" * 64
    elif mode.startswith("changed_"):
        after[site + "maskgw/db/postgres.py"]["mode" if mode == "changed_mode" else "uid"] = 1
    elif mode.startswith("new_"):
        after[site + "maskgw/runtime/linux_guard.py"][
            "mode" if mode == "new_mode" else "sha256"
        ] = 0o666 if mode == "new_mode" else "0" * 64
    else:
        after[site + "maskgw/runtime"]["mode"] = 0o777
    expected = {
        "other_record": "OTHER_OWNER_CHANGED",
        "other_mode": "OTHER_OWNER_CHANGED",
        "base_link": "OTHER_OWNER_CHANGED",
        "app_extra": "ADDED_SET",
        "remove": "REMOVED_SET",
        "unplanned_bytes": "CHANGED_SET",
        "changed_mode": "CHANGED_METADATA",
        "changed_uid": "CHANGED_METADATA",
        "new_mode": "NEW_METADATA",
        "new_hash": "APP_BYTES",
        "app_directory": "CHANGED_SET",
    }[mode]
    with pytest.raises(RuntimeError, match=rf"^{expected}$"):
        m["check_delta"](before, after, projection)


def test_lock_is_single_by_name_and_hash_only():
    assert m["lock_bytes"]() == ("maskgw==0.1.0 --hash=sha256:" + m["WHEEL_SHA"] + "\n").encode()
    assert b"/" not in m["lock_bytes"]() and b"file:" not in m["lock_bytes"]()


@pytest.mark.parametrize("fault", ["hash", "size", "directory"])
def test_pinned_regular_file_refusal(tmp_path, fault):
    path = tmp_path / "public"
    if fault == "directory":
        path.mkdir()
    else:
        path.write_bytes(b"public")
    expected = hashlib.sha256(b"other" if fault == "hash" else b"public").hexdigest()
    with pytest.raises(RuntimeError):
        m["pinned"](path, expected, 1 if fault == "size" else 64)


def test_pinned_bytes_are_returned_without_import_or_execution(tmp_path):
    raw = b"raise RuntimeError('THIS_IS_PUBLIC_DATA_ONLY')"
    path = tmp_path / "public.py"
    path.write_bytes(raw)
    assert m["pinned"](path, hashlib.sha256(raw).hexdigest(), 128) == raw


def test_closed_context_refuses_extra_before_reading_any_file(tmp_path):
    context = tmp_path / "context"
    (context / "wheels").mkdir(parents=True)
    (context / "unexpected").write_bytes(b"public")
    with pytest.raises(RuntimeError, match="CONTEXT_EXTRA"):
        m["check_context"](context, b"{}\n")


def physical_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, bytes]:
    # Filesystem-only model. This fake blob is NOT a wheel admission/ZIP proof.
    raw = b"MODEL_PUBLIC_WHEEL_BYTES"
    globals_ = m["check_context"].__globals__
    monkeypatch.setitem(globals_, "WHEEL_SHA", hashlib.sha256(raw).hexdigest())
    monkeypatch.setitem(globals_, "WHEEL_BYTES", len(raw))
    context = tmp_path / "context"
    (context / "wheels").mkdir(parents=True)
    (context / "wheels" / m["WHEEL_NAME"]).write_bytes(raw)
    manifest = b"{}\n"
    (context / "manifest.json").write_bytes(manifest)
    (context / "requirements.lock").write_bytes(m["lock_bytes"]())
    return context, manifest


def test_physical_context_checks_all_three_bytes_and_inventory(tmp_path, monkeypatch):
    context, manifest = physical_context(tmp_path, monkeypatch)
    m["check_context"](context, manifest)


@pytest.mark.parametrize(
    "fault", ["root_extra", "wheel_extra", "lock", "wheel", "manifest", "directory"]
)
def test_physical_context_tampering_fails_closed(tmp_path, monkeypatch, fault):
    context, manifest = physical_context(tmp_path, monkeypatch)
    if fault == "root_extra":
        (context / "unknown").write_bytes(b"public")
    elif fault == "wheel_extra":
        (context / "wheels/old-other.whl").write_bytes(b"public")
    elif fault in ("lock", "manifest", "wheel"):
        file = {
            "lock": context / "requirements.lock",
            "manifest": context / "manifest.json",
            "wheel": context / "wheels" / m["WHEEL_NAME"],
        }[fault]
        file.write_bytes(file.read_bytes() + b"changed")
    else:
        # A known name with wrong type; no deletion or recursive mutation.
        other = tmp_path / "other"
        other.mkdir()
        (other / "wheels").write_bytes(b"not a directory")
        context = other
    with pytest.raises(RuntimeError):
        m["check_context"](context, manifest)


def test_regular_size_is_checked_before_reading(tmp_path, monkeypatch):
    path = tmp_path / "public"
    path.write_bytes(b"12345678")

    def forbidden(_path):
        raise AssertionError("MUST_NOT_READ_OVERSIZED_FILE")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    with pytest.raises(RuntimeError, match=r"^SIZE$"):
        m["read_regular"](path, 1)


def test_diagnostics_only_serialize_closed_own_category():
    known = m["failure_metadata"](m["ContextRefusal"]("ORIGIN_WHEEL"))
    assert known["reason"] == "ORIGIN_WHEEL"
    unknown = m["failure_metadata"](RuntimeError("PUBLIC_MARKER_NOT_SERIALIZED"))
    assert unknown["reason"] is None and "PUBLIC_MARKER" not in json.dumps(unknown)
    assert (
        m["failure_metadata"](m["ContextRefusal"]("PUBLIC_MARKER_NOT_SERIALIZED"))["reason"]
        == "STATE"
    )
