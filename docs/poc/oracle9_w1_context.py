"""Closed public app-only update context. No Docker/install on import or main.

Fakes and read-only review precede materialization. Historical helpers are
captured by hash; only their pure admission/projection functions are used.
"""

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import stat
import sys

REPO = Path(__file__).resolve().parents[2]
BUILDER = REPO / "docs/poc/oracle9_app_wheel.py"
BUILDER_SHA = "a964890b2b6a3acaea87fcaeb0f780f14c0bc4b4656d8f983fb24b3e32a38507"
PROJECTOR = REPO / "docs/poc/oracle9_install_context.py"
PROJECTOR_SHA = "46108ce61026c09c1beb1c562ece6cad427a393d4d8e9e49f19853cc193f1907"
OLD_REPORT = REPO / "docs/poc/evidence/oracle9-app-wheel-result-20261026.json"
OLD_REPORT_SHA = "d0909fcf1ee17ff4ebb79d42746589f06a84c44a4686b65e30cf6ed22387606a"
OLD_ATTEST = REPO / "docs/poc/evidence/oracle9-installed-attestation-20261026.json"
OLD_ATTEST_SHA = "d47914864292c446e3d39591c9c60073f4ec3450b19893f2c577b8513f5d54bd"
NEW_REPORT = REPO / "docs/poc/evidence/oracle9-w1-app-wheel-result-20261026.json"
NEW_REPORT_SHA = "0693d8533065289da5263b94fece42e865b06ca74282c94ca73ab2438bbff83e"
WHEEL_ROOT = Path(
    "C:/Users/w.filho/AppData/Local/Temp/maskgw-oracle9-app-wheel-20261026-3ec5286b98824c32b262c704d464bf95"
)
WHEEL_NAME = "maskgw-0.1.0-py3-none-any.whl"
WHEEL_SHA = "6b63f239fadbc051f8fa850a96b69fbebba4f6b3eb12d3a12e49a9313429877b"
WHEEL_BYTES = 448821
OLD_WHEEL_SHA = "9181d95511ef8f791ab79d84d09705f0e8bcbcbe7c27465a8d1c64039b759724"
BASE_IMAGE = "sha256:87871290b01b0e4b8cd9dd90b8001a89ff4e04bd018e12c01ddbff8d6b16483a"
SITE = "lib/python3.11/site-packages/"
APP = "maskgw/"
DIST = "maskgw-0.1.0.dist-info/"
ADDED = frozenset(
    {
        "maskgw/db/session_state.py",
        "maskgw/runtime/linux_guard.py",
        "maskgw/runtime/worker_process.py",
        "maskgw/runtime/worker_protocol.py",
        "maskgw/runtime/worker_session.py",
    }
)
CHANGED = frozenset({"maskgw/db/postgres.py", "maskgw/runtime/budget.py", DIST + "RECORD"})


_CATEGORIES = frozenset(
    {
        "REGULAR",
        "SIZE",
        "READ_SIZE",
        "PIN",
        "ORIGIN",
        "MEMBERS",
        "ORIGIN_APP",
        "NEW_OWNER",
        "APP_PATH_DELTA",
        "APP_BYTE_DELTA",
        "COLLISION",
        "DISTRIBUTIONS",
        "WHEEL_NAME",
        "ORIGIN_WHEEL",
        "BASE_TOOLS",
        "OTHER_OWNER_CHANGED",
        "ADDED_SET",
        "REMOVED_SET",
        "CHANGED_SET",
        "CHANGED_KIND",
        "CHANGED_METADATA",
        "APP_KIND",
        "APP_BYTES",
        "NEW_METADATA",
        "PREFIX_COUNT",
        "BUILD_OUTCOME",
        "BUILD_ID",
        "CURRENT_SOURCE",
        "TOOLS",
        "WHEEL_READMISSION",
        "APP_SCRIPTS",
        "CONTEXT_DIRECTORY",
        "CONTEXT_EXTRA",
        "WHEEL_EXTRA",
        "MANIFEST_CHANGED",
        "LOCK_CHANGED",
        "WHEEL_SIZE",
        "RUNTIME",
        "OWN_ROOT",
        "ROOT_TYPE",
        "NOT_FRESH",
        "STATE",
        "MANIFEST_SIZE",
        "SOURCES_CHANGED",
        "CONTEXT_CHANGED",
    }
)


class ContextRefusal(RuntimeError):
    def __init__(self, category):
        self.category = category if type(category) is str and category in _CATEGORIES else "STATE"
        super().__init__(self.category)


def need(value, category):
    if not value:
        raise ContextRefusal(category)


def failure_metadata(error):
    return {
        "outcome": "W1_CONTEXT_REFUSED",
        "category": type(error).__name__,
        "reason": error.category if type(error) is ContextRefusal else None,
    }


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_regular(path, maximum):
    info = path.lstat()
    need(
        stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "REGULAR"
    )
    need(info.st_size <= maximum, "SIZE")
    raw = path.read_bytes()
    need(len(raw) == info.st_size, "READ_SIZE")
    return raw


def pinned(path, expected, maximum):
    raw = read_regular(path, maximum)
    need(sha(raw) == expected, "PIN")
    return raw


def frozen(path, expected):
    raw = pinned(path, expected, 65536)
    namespace = {"__name__": "_w1_context_library", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace


def lock_bytes():
    return ("maskgw==0.1.0 --hash=sha256:" + WHEEL_SHA + "\n").encode("ascii")


def target_projection(old, old_files, new_files):
    need(old["kind"] == "oracle9-installed-v1" and len(old["installed_snapshot"]) == 3332, "ORIGIN")
    manifest = old["manifest"]
    original = manifest["installed_files"]
    need(len(original) == 1382 and len(old_files) == 122 and len(new_files) == 127, "MEMBERS")
    need({k: v for k, v in original.items() if v["owner"] == "maskgw"} == old_files, "ORIGIN_APP")
    need(all(v["owner"] == "maskgw" for v in new_files.values()), "NEW_OWNER")
    need(
        set(new_files) - set(old_files) == ADDED and not set(old_files) - set(new_files),
        "APP_PATH_DELTA",
    )
    need({k for k in old_files if old_files[k] != new_files[k]} == CHANGED, "APP_BYTE_DELTA")
    files = {k: dict(v) for k, v in original.items() if v["owner"] != "maskgw"}
    need(not set(files) & set(new_files), "COLLISION")
    files.update({k: dict(v) for k, v in new_files.items()})
    wheels = [dict(row) for row in manifest["wheels"]]
    own = [row for row in wheels if row["name"] == "maskgw"]
    need(len(wheels) == 37 and len(own) == 1 and len(old["versions"]) == 39, "DISTRIBUTIONS")
    need(own[0]["filename"] == WHEEL_NAME and own[0]["version"] == "0.1.0", "WHEEL_NAME")
    need(own[0]["sha256"] == OLD_WHEEL_SHA and own[0]["bytes"] == 429231, "ORIGIN_WHEEL")
    own[0].update(sha256=WHEEL_SHA, bytes=WHEEL_BYTES)
    need(manifest["base_tools"] == {"pip": "22.3.1", "setuptools": "65.5.1"}, "BASE_TOOLS")
    return {
        "kind": "oracle9-w1-installed-target-v1",
        "wheels": wheels,
        "installed_files": dict(sorted(files.items())),
        "console_scripts": dict(manifest["console_scripts"]),
        "base_tools": dict(manifest["base_tools"]),
    }


def in_app(path):
    return path in (SITE + APP[:-1], SITE + DIST[:-1]) or path.startswith((SITE + APP, SITE + DIST))


def check_delta(before, after, projection):
    """L1 exact prefix invariant, additional to the original RECORD verifier."""
    need(
        {k: v for k, v in before.items() if not in_app(k)}
        == {k: v for k, v in after.items() if not in_app(k)},
        "OTHER_OWNER_CHANGED",
    )
    need(set(after) - set(before) == {SITE + k for k in ADDED}, "ADDED_SET")
    need(not set(before) - set(after), "REMOVED_SET")
    changed = {k for k in before if before[k] != after[k]}
    need(changed == {SITE + k for k in CHANGED}, "CHANGED_SET")
    for path in changed:
        need(before[path]["kind"] == after[path]["kind"] == "file", "CHANGED_KIND")
        need(
            {k: v for k, v in before[path].items() if k not in ("bytes", "sha256")}
            == {k: v for k, v in after[path].items() if k not in ("bytes", "sha256")},
            "CHANGED_METADATA",
        )
    for path, expected in projection.items():
        row = after[SITE + path]
        need(row["kind"] == "file", "APP_KIND")
        if not expected["rewritten_record"]:
            need(
                row["bytes"] == expected["bytes"] and row["sha256"] == expected["sha256"],
                "APP_BYTES",
            )
    for path in ADDED:
        row = after[SITE + path]
        need((row["mode"], row["uid"], row["gid"]) == (0o644, 0, 0), "NEW_METADATA")
    need(len(before) == 3332 and len(after) == 3337, "PREFIX_COUNT")


def sources():
    builder, projector = frozen(BUILDER, BUILDER_SHA), frozen(PROJECTOR, PROJECTOR_SHA)
    old_report = json.loads(pinned(OLD_REPORT, OLD_REPORT_SHA, 1024 * 1024))
    new_report = json.loads(pinned(NEW_REPORT, NEW_REPORT_SHA, 1024 * 1024))
    old = json.loads(pinned(OLD_ATTEST, OLD_ATTEST_SHA, 2 * 1024 * 1024))
    need(
        old_report["wheel_sha256"] == OLD_WHEEL_SHA and old_report["wheel_bytes"] == 429231,
        "ORIGIN_WHEEL",
    )
    need(
        old_report["outcome"] == new_report["outcome"] == "APP_WHEEL_BUILT_VERIFIED",
        "BUILD_OUTCOME",
    )
    need(
        new_report["wheel_sha256"] == WHEEL_SHA and new_report["wheel_bytes"] == WHEEL_BYTES,
        "BUILD_ID",
    )
    files, config = builder["capture"](REPO)
    need(builder["manifest"](files) == new_report["source_manifest"], "CURRENT_SOURCE")
    need({k: importlib.metadata.version(k) for k in builder["TOOLS"]} == builder["TOOLS"], "TOOLS")
    inspector = builder["load_inspector"]()
    for index in (1, 2):
        path = WHEEL_ROOT / ("wheel" + str(index)) / WHEEL_NAME
        pinned(path, WHEEL_SHA, 1024 * 1024)
        need(
            builder["validate_own_wheel"](path, files, config, inspector)
            == new_report["inspection"],
            "WHEEL_READMISSION",
        )
    old_files, old_scripts = projector["installed_projection"]([old_report["inspection"]])
    new_files, new_scripts = projector["installed_projection"]([new_report["inspection"]])
    need(not old_scripts and not new_scripts, "APP_SCRIPTS")
    target = target_projection(old, old_files, new_files)
    return target, new_report["source_manifest"]


def write_new(path, raw):
    with path.open("xb") as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())


def check_context(context, manifest_raw):
    for directory in (context, context / "wheels"):
        info = directory.lstat()
        need(
            stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
            "CONTEXT_DIRECTORY",
        )
    need(
        {p.name for p in context.iterdir()} == {"manifest.json", "requirements.lock", "wheels"},
        "CONTEXT_EXTRA",
    )
    need({p.name for p in (context / "wheels").iterdir()} == {WHEEL_NAME}, "WHEEL_EXTRA")
    need(
        pinned(context / "manifest.json", sha(manifest_raw), 2 * 1024 * 1024) == manifest_raw,
        "MANIFEST_CHANGED",
    )
    need(
        pinned(context / "requirements.lock", sha(lock_bytes()), 256) == lock_bytes(),
        "LOCK_CHANGED",
    )
    raw = pinned(context / "wheels" / WHEEL_NAME, WHEEL_SHA, 1024 * 1024)
    need(len(raw) == WHEEL_BYTES, "WHEEL_SIZE")


def main(root):
    need(
        os.name == "nt"
        and sys.flags.isolated
        and sys.flags.dont_write_bytecode
        and not sys.flags.optimize,
        "RUNTIME",
    )
    need(
        root.parent.resolve() == (Path(os.environ["LOCALAPPDATA"]) / "Temp").resolve()
        and re.fullmatch(r"maskgw-oracle9-w1-context-20261027-[0-9a-f]{32}", root.name),
        "OWN_ROOT",
    )
    info = root.lstat()
    need(
        stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
        "ROOT_TYPE",
    )
    need({v.name for v in root.iterdir()} == {"state.json"}, "NOT_FRESH")
    raw = read_regular(root / "state.json", 65536)
    state = json.loads(raw)
    need(
        set(state) == {"kind", "task", "invoked", "program_sha256"}
        and state["kind"] == "oracle9-w1-context-v1"
        and state["invoked"] is False
        and re.fullmatch("[0-9a-f]{32}", state["task"])
        and state["program_sha256"] == sha(Path(__file__).read_bytes()),
        "STATE",
    )
    write_new(root / "invoked.json", b'{"invoked":true}\n')
    target, current = sources()
    wheel = pinned(WHEEL_ROOT / "wheel1" / WHEEL_NAME, WHEEL_SHA, 1024 * 1024)
    context = root / "context"
    context.mkdir()
    (context / "wheels").mkdir()
    write_new(context / "wheels" / WHEEL_NAME, wheel)
    write_new(context / "requirements.lock", lock_bytes())
    manifest = {
        "kind": "oracle9-w1-app-context-v1",
        "base_image": BASE_IMAGE,
        "origin_attestation_sha256": OLD_ATTEST_SHA,
        "origin_program_sha256": "ee2becec0e6683807827e3682a410497f94a24d7509d6670cd88b50654d4c5af",
        "app_report_sha256": NEW_REPORT_SHA,
        "app_wheel_sha256": WHEEL_SHA,
        "app_wheel_bytes": WHEEL_BYTES,
        "target": target,
        "source_manifest": current,
        "delta": {"added": sorted(ADDED), "changed": sorted(CHANGED), "removed": []},
        "lock_sha256": sha(lock_bytes()),
    }
    raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    need(len(raw) <= 2 * 1024 * 1024, "MANIFEST_SIZE")
    write_new(context / "manifest.json", raw)
    need(sources() == (target, current), "SOURCES_CHANGED")
    check_context(context, raw)
    need(
        (context / "manifest.json").read_bytes() == raw
        and (context / "requirements.lock").read_bytes() == lock_bytes()
        and (context / "wheels" / WHEEL_NAME).read_bytes() == wheel,
        "CONTEXT_CHANGED",
    )
    ready = {
        "kind": "oracle9-w1-context-ready-v1",
        "task": state["task"],
        "program_sha256": state["program_sha256"],
        "outcome": "W1_CONTEXT_VERIFIED",
        "manifest_sha256": sha(raw),
        "manifest_bytes": len(raw),
        "wheel_sha256": WHEEL_SHA,
        "wheel_bytes": len(wheel),
        "files": 3,
        "installed": False,
        "docker_invoked": False,
    }
    write_new(root / "ready.json", (json.dumps(ready, sort_keys=True) + "\n").encode())
    print(json.dumps(ready, sort_keys=True))


if __name__ == "__main__":
    try:
        main(Path(sys.argv[1]))
    except Exception as error:
        print(json.dumps(failure_metadata(error)))
        raise SystemExit(1) from None
