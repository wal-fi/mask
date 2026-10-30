"""Closed input assembly checks with tiny fake bytes, no Docker/install."""

import base64
import hashlib
import importlib.util
import json
import zlib
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def context_module() -> Any:
    path = Path(__file__).resolve().parents[1] / "docs/poc/oracle9_install_context.py"
    spec = importlib.util.spec_from_file_location("_context_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def packet(payload: bytes, extra: bytes = b"") -> bytes:
    return json.dumps(
        {
            "kind": "oracle9-wheel-inspection-envelope-v1",
            "raw_bytes": len(payload),
            "raw_sha256": hashlib.sha256(payload).hexdigest(),
            "zlib_base64": base64.b64encode(zlib.compress(payload) + extra).decode(),
        }
    ).encode()


def fake_inventory(name: str = "sample") -> dict[str, Any]:
    return {
        "name": name,
        "members": [
            {"path": "sample/module.py", "bytes": 4, "sha256": "a" * 64, "directory": False}
        ],
        "pth_unapproved": [],
        "scripts": [],
        "entry_points": {},
    }


def fake_context(tmp_path: Path, module: Any, monkeypatch: Any) -> tuple[Path, dict[str, Any], str]:
    root = tmp_path / "context"
    (root / "wheels").mkdir(parents=True)
    entries: list[dict[str, Any]] = []
    for index in range(37):
        raw = b"fake-public-wheel-bytes" + str(index).encode()
        filename = f"sample{index}-1.0-py3-none-any.whl"
        (root / "wheels" / filename).write_bytes(raw)
        entries.append(
            {
                "name": f"sample{index}",
                "version": "1.0",
                "filename": filename,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    lock = module.lock_bytes(entries)
    manifest = {
        "kind": "oracle9-offline-context-v1",
        "wheels": entries,
        "wheel_bytes": sum(v["bytes"] for v in entries),
        "lock_sha256": hashlib.sha256(lock).hexdigest(),
    }
    (root / "requirements.lock").write_bytes(lock)
    raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    (root / "manifest.json").write_bytes(raw)
    monkeypatch.setattr(module, "TOTAL_WHEEL_BYTES", manifest["wheel_bytes"])
    return root, manifest, hashlib.sha256(raw).hexdigest()


def test_historical_context_refuses_the_updated_w1_sources(context_module):
    """The 119-file artifact is historical, never silently rebound to W1.

    Its former positive execution is preserved in the installation evidence.
    The forward 124-file artifact has its own reviewed admission/projection.
    """
    with pytest.raises(RuntimeError, match=r"^APP_SOURCE_CHANGED$"):
        context_module.sources()


def test_inspection_envelope_roundtrip(context_module):
    raw = json.dumps(
        {"outcome": "WHEELS_INSPECTED_STRUCTURALLY", "category": None, "wheels": [{}] * 36}
    ).encode()
    assert len(context_module.inspection_packet(packet(raw))["wheels"]) == 36


@pytest.mark.parametrize("bad", ["tail", "hash", "size", "base64", "expansion", "outcome"])
def test_inspection_envelope_never_accepts_corruption(context_module, bad):
    payload = json.dumps(
        {"outcome": "WHEELS_INSPECTED_STRUCTURALLY", "category": None, "wheels": [{}] * 36}
    ).encode()
    raw = packet(payload, b"tail" if bad == "tail" else b"")
    if bad == "expansion":
        raw = packet(b"x" * (16 * 1024 * 1024 + 1))
    elif bad == "outcome":
        raw = packet(payload.replace(b"WHEELS_INSPECTED_STRUCTURALLY", b"REFUSED"))
    elif bad in ("hash", "size", "base64"):
        value = json.loads(raw)
        value[{"hash": "raw_sha256", "size": "raw_bytes", "base64": "zlib_base64"}[bad]] = (
            1 if bad == "size" else "bad"
        )
        raw = json.dumps(value).encode()
    with pytest.raises((RuntimeError, ValueError)):
        context_module.inspection_packet(raw)


@pytest.mark.parametrize(
    "bad", ["collision", "data", "pth", "script", "path", "console-name", "console-collision"]
)
def test_installed_mapping_rejects_collision_or_startup_change(context_module, bad):
    wheel = fake_inventory()
    wheels = [wheel]
    if bad == "collision":
        wheels.append(fake_inventory("other"))
    elif bad == "data":
        wheel["members"][0]["path"] = "sample-1.0.data/data/file"
    elif bad == "pth":
        wheel["pth_unapproved"] = [{}]
    elif bad == "script":
        wheel["scripts"] = ["sample-1.0.data/scripts/script"]
    elif bad == "path":
        wheel["members"][0]["path"] = "../outside"
    else:
        wheel["entry_points"] = {
            "console_scripts": {".." if bad == "console-name" else "hello": "sample:main"}
        }
        if bad == "console-collision":
            other = fake_inventory("other")
            other["members"][0]["path"] = "other.py"
            other["entry_points"] = wheel["entry_points"]
            wheels.append(other)
    with pytest.raises(RuntimeError):
        context_module.installed_projection(wheels)


def test_directory_members_do_not_become_installed_files(context_module):
    wheel = fake_inventory()
    wheel["members"].append({"path": "sample/", "directory": True})
    files, scripts = context_module.installed_projection([wheel])
    assert set(files) == {"sample/module.py"} and not scripts


def test_closed_context_is_hash_verification_not_zip_interpretation(
    tmp_path, context_module, monkeypatch
):
    root, manifest, digest = fake_context(tmp_path, context_module, monkeypatch)
    context_module.check_context(root, manifest, digest)
    assert len(list((root / "wheels").iterdir())) == 37


@pytest.mark.parametrize("bad", ["extra", "extra-wheel", "missing", "bytes", "lock", "manifest"])
def test_modified_context_never_becomes_ready(tmp_path, context_module, monkeypatch, bad):
    root, manifest, digest = fake_context(tmp_path, context_module, monkeypatch)
    first = root / "wheels" / manifest["wheels"][0]["filename"]
    if bad == "extra":
        (root / "unexpected").write_bytes(b"no")
    elif bad == "extra-wheel":
        (root / "wheels" / "extra.whl").write_bytes(b"no")
    elif bad == "missing":
        first.unlink()
    elif bad == "bytes":
        first.write_bytes(b"x" * first.stat().st_size)
    elif bad == "lock":
        (root / "requirements.lock").write_bytes(b"changed")
    else:
        (root / "manifest.json").write_bytes(b"{}")
    with pytest.raises((RuntimeError, OSError)):
        context_module.check_context(root, manifest, digest)


def test_pinned_read_checks_size_before_loading(tmp_path, context_module):
    path = tmp_path / "public"
    path.write_bytes(b"x" * 100)
    with pytest.raises(RuntimeError, match="INPUT_SIZE"):
        context_module.read_pinned(path, "0" * 64, 10)
