"""Prepare a closed 37-wheel public input directory, no Docker or install."""

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import zlib

REPO = Path(__file__).resolve().parents[2]
HOUSE = Path("C:/Users/w.filho/AppData/Local/Temp/maskgw-oracle9-wheels-20261025-8ca7de53")
OWN_ROOT = Path("C:/Users/w.filho/AppData/Local/Temp/maskgw-oracle9-app-wheel-20261026-ad017213")
BASE_IMAGE = "sha256:1546afefa358aa8c6049350948b1d5d4f272017da8997ae3974c93af7fdc07c4"
BUILDER = REPO / "docs/poc/oracle9_app_wheel.py"
BUILDER_SHA = "a964890b2b6a3acaea87fcaeb0f780f14c0bc4b4656d8f983fb24b3e32a38507"
OWN_EVIDENCE = REPO / "docs/poc/evidence/oracle9-app-wheel-result-20261026.json"
OWN_EVIDENCE_SHA = "d0909fcf1ee17ff4ebb79d42746589f06a84c44a4686b65e30cf6ed22387606a"
ENVELOPE = REPO / "docs/poc/evidence/oracle9-wheel-inspection-envelope-20261026.json"
ENVELOPE_SHA = "d2c186d4afa32ad1d32979797cdf4fd94baa386efcc6e9c7906af0c1223528eb"
TOTAL_WHEEL_BYTES = 22643029


def need(value, category):
    if not value:
        raise RuntimeError(category)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path):
    s = path.lstat()
    need(
        stat.S_ISREG(s.st_mode) and not getattr(s, "st_file_attributes", 0) & 0x400, "CONTEXT_FILE"
    )


def read_pinned(path, expected, limit):
    regular(path)
    need(path.stat().st_size <= limit, "INPUT_SIZE")
    raw = path.read_bytes()
    need(sha(raw) == expected, "INPUT_HASH")
    return raw


def inspection_packet(raw):
    need(len(raw) <= 2 * 1024 * 1024, "ENVELOPE_SIZE")
    envelope = json.loads(raw)
    need(
        set(envelope) == {"kind", "raw_bytes", "raw_sha256", "zlib_base64"}
        and envelope["kind"] == "oracle9-wheel-inspection-envelope-v1",
        "ENVELOPE",
    )
    compressed = base64.b64decode(envelope["zlib_base64"], validate=True)
    decoder = zlib.decompressobj()
    payload = decoder.decompress(compressed, 16 * 1024 * 1024 + 1)
    need(
        decoder.eof
        and not decoder.unused_data
        and not decoder.unconsumed_tail
        and len(payload) <= 16 * 1024 * 1024,
        "ENVELOPE_EXPANSION",
    )
    need(
        len(payload) == envelope["raw_bytes"] and sha(payload) == envelope["raw_sha256"],
        "ENVELOPE_HASH",
    )
    report = json.loads(payload)
    need(
        report["outcome"] == "WHEELS_INSPECTED_STRUCTURALLY"
        and report["category"] is None
        and len(report["wheels"]) == 36,
        "I_NOT_READY",
    )
    return report


def installed_projection(wheels):
    files, scripts = {}, {}
    for wheel in wheels:
        for item in wheel["members"]:
            name = item["path"]
            need(
                type(name) is str
                and 0 < len(name.encode()) <= 512
                and not any(ord(c) < 32 or c in "\\:" for c in name)
                and all(v not in ("", ".", "..") for v in name.rstrip("/").split("/")),
                "MEMBER_PATH",
            )
            need(not name.split("/", 1)[0].endswith(".data"), "DATA_NOT_SUPPORTED")
            if item["directory"]:
                continue
            need(name not in files, "WHEEL_PATH_COLLISION")
            files[name] = {
                "bytes": item["bytes"],
                "sha256": item["sha256"],
                "owner": wheel["name"],
                "rewritten_record": name.endswith(".dist-info/RECORD"),
            }
        need(not wheel["pth_unapproved"] and not wheel["scripts"], "WHEEL_STARTUP_SURFACE")
        for name, target in wheel["entry_points"].get("console_scripts", {}).items():
            need(
                name not in scripts and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name),
                "SCRIPT_COLLISION",
            )
            scripts[name] = {"owner": wheel["name"], "target": target}
    return dict(sorted(files.items())), dict(sorted(scripts.items()))


def sources():
    source = read_pinned(BUILDER, BUILDER_SHA, 65536)
    builder = {"__name__": "_frozen_own_wheel_admission", "__file__": str(BUILDER)}
    exec(compile(source, str(BUILDER), "exec"), builder)
    inspector = builder["load_inspector"]()
    native_files, manifest, admission = inspector["admission"](HOUSE)
    own = json.loads(read_pinned(OWN_EVIDENCE, OWN_EVIDENCE_SHA, 1024 * 1024))
    need(
        own["outcome"] == "APP_WHEEL_BUILT_VERIFIED"
        and own["installed"] is False
        and own["two_builds_identical"] is True,
        "APP_NOT_READY",
    )
    need(
        builder["manifest"](builder["capture"](REPO)[0]) == own["source_manifest"],
        "APP_SOURCE_CHANGED",
    )
    own_path = OWN_ROOT / "wheel1/maskgw-0.1.0-py3-none-any.whl"
    own_path2 = OWN_ROOT / "wheel2/maskgw-0.1.0-py3-none-any.whl"
    read_pinned(own_path, own["wheel_sha256"], 8 * 1024 * 1024)
    read_pinned(own_path2, own["wheel_sha256"], 8 * 1024 * 1024)
    report = inspection_packet(read_pinned(ENVELOPE, ENVELOPE_SHA, 2 * 1024 * 1024))
    need(
        report["manifest_sha256"] == inspector["MANIFEST_SHA"]
        and report["lock_sha256"] == inspector["LOCK_SHA"],
        "I_INPUT",
    )
    rows = []
    for source, checked, size in zip(
        native_files, report["wheels"], manifest["files"], strict=True
    ):
        need(
            all(source[k] == checked[k] for k in ("name", "version", "filename"))
            and source["sha256"] == checked["archive_sha256"],
            "I_PROJECTION",
        )
        rows.append(
            {
                "name": source["name"],
                "version": source["version"],
                "filename": source["filename"],
                "bytes": size["bytes"],
                "sha256": source["sha256"],
                "source": HOUSE / "wheels" / source["filename"],
            }
        )
    rows.append(
        {
            "name": "maskgw",
            "version": "0.1.0",
            "filename": own_path.name,
            "bytes": own["wheel_bytes"],
            "sha256": own["wheel_sha256"],
            "source": own_path,
        }
    )
    rows.sort(key=lambda v: v["name"])
    need(
        len(rows) == 37
        and len({v["filename"] for v in rows}) == 37
        and sum(v["bytes"] for v in rows) == TOTAL_WHEEL_BYTES,
        "WHEEL_SET",
    )
    installed, scripts = installed_projection(report["wheels"] + [own["inspection"]])
    need(
        set(scripts)
        == {"cffi-gen-src", "fastapi", "httpx2", "idna", "jsonschema", "mcp", "pgpp", "uvicorn"},
        "SCRIPT_SET",
    )
    return (
        rows,
        installed,
        scripts,
        lambda: admission["check_wheelhouse"](HOUSE, native_files, manifest),
    )


def lock_bytes(rows):
    return (
        "# Closed candidate Linux CPython3.11 set, no dev extras.\n"
        + "".join(
            v["name"] + "==" + v["version"] + " --hash=sha256:" + v["sha256"] + "\n" for v in rows
        )
    ).encode("ascii")


def write_new(path, raw):
    with path.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def check_context(context, manifest, expected_sha):
    for directory in (context, context / "wheels"):
        s = directory.lstat()
        need(
            stat.S_ISDIR(s.st_mode) and not getattr(s, "st_file_attributes", 0) & 0x400,
            "CONTEXT_DIRECTORY",
        )
    need(
        {v.name for v in context.iterdir()} == {"wheels", "requirements.lock", "manifest.json"},
        "CONTEXT_EXTRA",
    )
    need(
        {v.name for v in (context / "wheels").iterdir()}
        == {v["filename"] for v in manifest["wheels"]},
        "WHEELS_EXTRA",
    )
    read_pinned(context / "manifest.json", expected_sha, 2 * 1024 * 1024)
    need(
        (context / "manifest.json").read_bytes()
        == (json.dumps(manifest, sort_keys=True) + "\n").encode(),
        "MANIFEST_CHANGED",
    )
    need(
        len(manifest["wheels"]) == 37 and manifest["kind"] == "oracle9-offline-context-v1",
        "CONTEXT_SCHEMA",
    )
    total = 0
    for entry in manifest["wheels"]:
        need(
            entry["filename"].endswith(".whl")
            and Path(entry["filename"]).name == entry["filename"],
            "CONTEXT_PATH",
        )
        raw = read_pinned(context / "wheels" / entry["filename"], entry["sha256"], 32 * 1024 * 1024)
        need(len(raw) == entry["bytes"], "CONTEXT_SIZE")
        total += len(raw)
    need(total == manifest["wheel_bytes"] == TOTAL_WHEEL_BYTES, "CONTEXT_TOTAL")
    read_pinned(context / "requirements.lock", manifest["lock_sha256"], 65536)
    need(
        (context / "requirements.lock").read_bytes() == lock_bytes(manifest["wheels"]),
        "LOCK_CHANGED",
    )


def main(root):
    need(os.name == "nt" and sys.flags.isolated and not sys.flags.optimize, "RUNTIME")
    need(
        root.parent.resolve() == (Path(os.environ["LOCALAPPDATA"]) / "Temp").resolve()
        and root.name.startswith("maskgw-oracle9-install-context-"),
        "OUTPUT_ROOT",
    )
    s = root.lstat()
    need(stat.S_ISDIR(s.st_mode) and not getattr(s, "st_file_attributes", 0) & 0x400, "OUTPUT_ROOT")
    need({v.name for v in root.iterdir()} == {"state.json"}, "OUTPUT_NOT_FRESH")
    regular(root / "state.json")
    need((root / "state.json").stat().st_size <= 65536, "STATE_SIZE")
    state = json.loads((root / "state.json").read_bytes())
    need(
        state["kind"] == "oracle9-install-context-v1"
        and state["invoked"] is False
        and state["program_sha256"] == sha(Path(__file__).read_bytes()),
        "STATE",
    )
    write_new(root / "invoked.json", b'{"invoked":true}\n')
    rows, installed, scripts, recheck = sources()
    context = root / "context"
    context.mkdir()
    (context / "wheels").mkdir()
    for entry in rows:
        raw = read_pinned(entry["source"], entry["sha256"], 32 * 1024 * 1024)
        need(len(raw) == entry["bytes"], "SOURCE_CHANGED")
        write_new(context / "wheels" / entry["filename"], raw)
    lock = lock_bytes(rows)
    write_new(context / "requirements.lock", lock)
    manifest = {
        "kind": "oracle9-offline-context-v1",
        "base_image": BASE_IMAGE,
        "source_i_sha256": ENVELOPE_SHA,
        "source_app_sha256": OWN_EVIDENCE_SHA,
        "wheels": [{k: v for k, v in entry.items() if k != "source"} for entry in rows],
        "wheel_bytes": sum(v["bytes"] for v in rows),
        "lock_sha256": sha(lock),
        "installed_files": installed,
        "console_scripts": scripts,
        "base_tools": {"pip": "22.3.1", "setuptools": "65.5.1"},
    }
    raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    need(len(raw) <= 2 * 1024 * 1024, "MANIFEST_SIZE")
    write_new(context / "manifest.json", raw)
    check_context(context, manifest, sha(raw))
    recheck()
    need(sources()[0] == rows, "ORIGIN_CHANGED")
    ready = {
        "kind": "oracle9-offline-context-ready-v1",
        "task": state["task"],
        "program_sha256": state["program_sha256"],
        "outcome": "OFFLINE_CONTEXT_VERIFIED",
        "manifest_sha256": sha(raw),
        "manifest_bytes": len(raw),
        "lock_sha256": sha(lock),
        "wheel_count": 37,
        "wheel_bytes": manifest["wheel_bytes"],
        "installed_paths": len(installed),
        "docker_invoked": False,
        "installed": False,
    }
    write_new(root / "ready.json", (json.dumps(ready, sort_keys=True) + "\n").encode())
    print(json.dumps(ready, sort_keys=True))


if __name__ == "__main__":
    try:
        main(Path(sys.argv[1]))
    except Exception as exc:
        print(json.dumps({"outcome": "OFFLINE_CONTEXT_REFUSED", "category": type(exc).__name__}))
        raise SystemExit(1) from None
