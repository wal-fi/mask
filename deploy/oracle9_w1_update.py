"""Closed app-only Oracle candidate update/probe. No effect on import.

Laboratory payload, not a product entrypoint. No SQL, worker or data source.
Historical installer and new context core are captured as hash-bound libraries,
never invoked as programs. Only named public inputs and owned files are used.
"""

import base64
import contextlib
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import threading
from unittest.mock import patch
import zlib

ORIGIN_SHA = "ee2becec0e6683807827e3682a410497f94a24d7509d6670cd88b50654d4c5af"
CORE_SHA = "94cfa9118625d175a67a398bb2c416b5ca392e7a3b458cc433dc63fa02c75d78"
MANIFEST_SHA = "d4d4b29b302215b00d56ce249caebe6c5f76943d85725c654b8063d4940c5df8"
MANIFEST_BYTES = 270278
OLD_ATTEST_SHA = "d47914864292c446e3d39591c9c60073f4ec3450b19893f2c577b8513f5d54bd"
ORIGIN_BLOB = "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"
CORE_BLOB = "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"
ATTEST = Path("/opt/maskgw/oracle9-w1-installed.json")
SITE = Path("/opt/maskgw/venv/lib/python3.11/site-packages")
PHASE = "admission"
W1_MODULES = (
    "maskgw.runtime.linux_guard",
    "maskgw.db.session_state",
    "maskgw.runtime.worker_protocol",
    "maskgw.runtime.worker_process",
    "maskgw.runtime.worker_session",
)
_ORIGIN = None
_CORE = None
_ORIGIN_REASONS = frozenset(
    (
        "ARGUMENTS",
        "ATTEST_HASH",
        "ATTEST_KIND",
        "ATTEST_SIZE",
        "BASE_CHANGED",
        "BASE_LIB64_LINK",
        "BASE_PTH_CHANGED",
        "BASE_SCRIPT_COLLISION",
        "BASE_TOOLS",
        "CGROUP",
        "CPU",
        "DIST_INFO",
        "DIST_INFO_SET",
        "DUPLICATE_DISTRIBUTION",
        "FILENAME",
        "FILE_COLLISION",
        "GENERATED_COLLISION",
        "GENERATED_CONTENT",
        "IMPORT_PREFIX_WRITE",
        "INPUT_DIRECTORY",
        "INPUT_EXTRA",
        "INPUT_OWNER",
        "INPUT_PREFIX",
        "INSTALLED_BYTES",
        "INSTALLED_FILE_TYPE",
        "INSTALLED_SET",
        "INSTALL_PID_OR_EXISTING",
        "LOCK",
        "MANIFEST",
        "MANIFEST_HASH",
        "NETWORK",
        "PIP_CONFIG",
        "PIP_NONZERO",
        "PIP_OUTPUT",
        "PIP_TIMEOUT",
        "PREFIX_COUNT",
        "PREFIX_EXTRA_OR_MISSING",
        "PREFIX_LINK",
        "PREFIX_MODE",
        "PREFIX_OWNER",
        "PREFIX_ROOT",
        "PREFIX_SPECIAL_OR_SIZE",
        "PREFIX_TOTAL",
        "PRIVILEGE",
        "PRIVILEGE_BOUND",
        "PROBE_NATIVE_OR_FILES",
        "PROBE_PREFIX_CHANGED",
        "PROBE_PTH_CHANGED",
        "PSYCOPG_CRYPTO_HASH",
        "PSYCOPG_CRYPTO_VERSION",
        "PSYCOPG_IMPL",
        "READ_SIZE",
        "RECORD_ALGORITHM",
        "RECORD_COLUMNS",
        "RECORD_COVERAGE",
        "RECORD_ESCAPE",
        "RECORD_HASH",
        "RECORD_MEMBER",
        "RECORD_PATH",
        "RECORD_SELF",
        "RECORD_SIZE",
        "REGULAR_SIZE",
        "RESULT_OUTPUT_LIMIT",
        "RLIMIT",
        "ROOT_MODE",
        "RUNTIME",
        "RUNTIME_USER",
        "SCRIPT_NAME",
        "SCRIPT_SHEBANG",
        "SOURCE_PATH",
        "TMP_MODE",
        "TMP_OWNER",
        "TMP_SIZE",
        "UI_ASSETS",
        "UI_RESOURCES",
        "WHEELS_EXTRA",
        "WHEEL_HASH",
        "WHEEL_TOTAL",
    )
)
_REASONS = frozenset(
    {
        "LIBRARY",
        "LIBRARY_SIZE",
        "LIBRARY_FRAME",
        "LIBRARY_HASH",
        "INPUT_PATH",
        "MANIFEST",
        "MANIFEST_ID",
        "TARGET",
        "INPUT_OWNER",
        "SOURCE_MANIFEST",
        "ROW",
        "MODE",
        "PID1",
        "ORIGIN_ATTEST",
        "PREFIX_BEFORE",
        "PTH",
        "NATIVE",
        "IMPORT_PREFIX",
        "W1_MODULE",
        "ATTEST_SIZE",
        "ATTEST_HASH",
        "ATTEST_KIND",
        "PREFIX_AFTER",
        "INPUTS_REMAIN",
        "CLI",
        "VERSIONS",
        "RUNTIME",
        "STATE",
    }
)


class UpdateRefusal(RuntimeError):
    def __init__(self, reason):
        self.reason = reason if type(reason) is str and reason in _REASONS else "STATE"
        super().__init__(self.reason)


def need(value, reason):
    if not value:
        raise UpdateRefusal(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def thaw(blob, expected, role):
    need(role in ("origin", "context") and type(blob) is str and len(blob) <= 65536, "LIBRARY")
    compressed = base64.b64decode(blob, validate=True)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed, 65537)
    need(len(raw) <= 65536, "LIBRARY_SIZE")
    need(decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data, "LIBRARY_FRAME")
    need(sha(raw) == expected, "LIBRARY_HASH")
    filename = "/opt/maskgw/lab/" + role + ".py"
    namespace = {"__name__": "_w1_" + role + "_library", "__file__": filename}
    exec(compile(raw, filename, "exec"), namespace)
    return namespace


def libraries():
    global _ORIGIN, _CORE
    _ORIGIN = thaw(ORIGIN_BLOB, ORIGIN_SHA, "origin")
    _CORE = thaw(CORE_BLOB, CORE_SHA, "context")
    return _ORIGIN, _CORE


def read_old(origin):
    raw = origin["read_regular"](origin["ATTEST"], 2 * 1024 * 1024)
    need(sha(raw) == OLD_ATTEST_SHA, "ORIGIN_ATTEST")
    old = json.loads(raw)
    need(old["kind"] == "oracle9-installed-v1", "ORIGIN_ATTEST")
    return old


def validate_manifest(manifest, old, core):
    need(
        type(manifest) is dict
        and set(manifest)
        == {
            "kind",
            "base_image",
            "origin_attestation_sha256",
            "origin_program_sha256",
            "app_report_sha256",
            "app_wheel_sha256",
            "app_wheel_bytes",
            "target",
            "source_manifest",
            "delta",
            "lock_sha256",
        },
        "MANIFEST",
    )
    need(
        manifest["kind"] == "oracle9-w1-app-context-v1"
        and manifest["base_image"] == core["BASE_IMAGE"]
        and manifest["origin_attestation_sha256"] == OLD_ATTEST_SHA
        and manifest["origin_program_sha256"] == ORIGIN_SHA
        and manifest["app_report_sha256"] == core["NEW_REPORT_SHA"]
        and manifest["app_wheel_sha256"] == core["WHEEL_SHA"]
        and type(manifest["app_wheel_bytes"]) is int
        and manifest["app_wheel_bytes"] == core["WHEEL_BYTES"]
        and manifest["lock_sha256"] == sha(core["lock_bytes"]()),
        "MANIFEST_ID",
    )
    need(
        manifest["delta"]
        == {"added": sorted(core["ADDED"]), "changed": sorted(core["CHANGED"]), "removed": []},
        "TARGET",
    )
    target = manifest["target"]
    need(
        type(target) is dict
        and set(target) == {"kind", "wheels", "installed_files", "console_scripts", "base_tools"}
        and target["kind"] == "oracle9-w1-installed-target-v1",
        "TARGET",
    )
    old_files = {
        k: v for k, v in old["manifest"]["installed_files"].items() if v["owner"] == "maskgw"
    }
    new_files = {k: v for k, v in target["installed_files"].items() if v["owner"] == "maskgw"}
    for path, row in new_files.items():
        need(
            type(row) is dict and set(row) == {"bytes", "sha256", "owner", "rewritten_record"},
            "ROW",
        )
        need(
            type(row["bytes"]) is int
            and 0 <= row["bytes"] <= 64 * 1024 * 1024
            and type(row["sha256"]) is str
            and re.fullmatch("[0-9a-f]{64}", row["sha256"])
            and type(row["rewritten_record"]) is bool
            and row["rewritten_record"] is path.endswith(".dist-info/RECORD"),
            "ROW",
        )
    need(core["target_projection"](old, old_files, new_files) == target, "TARGET")
    need(
        type(manifest["source_manifest"]) is list and len(manifest["source_manifest"]) == 124,
        "SOURCE_MANIFEST",
    )
    return target, new_files


def load_context(root, origin, core):
    need(isinstance(root, Path), "INPUT_PATH")
    need(re.fullmatch(r"/opt/maskgw/w1-inputs-[0-9a-f]{32}", str(root)), "INPUT_PATH")
    raw = origin["read_regular"](root / "manifest.json", 2 * 1024 * 1024)
    need(len(raw) == MANIFEST_BYTES and sha(raw) == MANIFEST_SHA, "MANIFEST")
    core["check_context"](root, raw)  # counts, regular types and three exact bytes
    old = read_old(origin)
    manifest = json.loads(raw)
    validate_manifest(manifest, old, core)
    modes = {}
    for path in (
        root,
        root / "wheels",
        root / "manifest.json",
        root / "requirements.lock",
        root / "wheels" / core["WHEEL_NAME"],
    ):
        info = path.lstat()
        need(info.st_uid == info.st_gid == 0 and not stat.S_ISLNK(info.st_mode), "INPUT_OWNER")
        modes[path.relative_to(root).as_posix()] = stat.S_IMODE(info.st_mode)
        os.chmod(path, 0o755 if stat.S_ISDIR(info.st_mode) else 0o644)
    return manifest, old, modes


def w1_imports(origin, projection):
    import socket

    def reject(*_args, **_kwargs):
        raise UpdateRefusal("W1_MODULE")

    result = {}
    preloaded = [name for name in W1_MODULES if name in sys.modules]
    with contextlib.ExitStack() as stack:
        for name in ("connect", "connect_ex", "bind", "listen", "accept", "makefile"):
            stack.enter_context(patch.object(socket.socket, name, reject))
        for name in ("socketpair", "create_connection"):
            stack.enter_context(patch.object(socket, name, reject))
        stack.enter_context(patch.object(subprocess, "Popen", reject))
        stack.enter_context(patch.object(threading.Thread, "start", reject))
        for name in W1_MODULES:
            module = importlib.import_module(name)
            relative = name.replace(".", "/") + ".py"
            path = SITE / relative
            need(Path(module.__file__).resolve() == path and relative in projection, "W1_MODULE")
            raw = origin["read_regular"](path, 65536)
            expected = projection[relative]
            need(len(raw) == expected["bytes"] and sha(raw) == expected["sha256"], "W1_MODULE")
            result[name] = {"bytes": len(raw), "sha256": sha(raw)}
    return {"modules": result, "preloaded": preloaded}


def install(root, origin, core):
    global PHASE
    PHASE = "preparation-profile"
    profile = origin["runtime_profile"](False)
    need(os.getpid() == 1 and not ATTEST.exists(), "PID1")
    os.umask(0o022)
    manifest, old, modes = load_context(root, origin, core)
    origin["parent_environment"]()
    PHASE = "origin-prefix"
    before = origin["scan_prefix"]()
    need(before == old["installed_snapshot"], "PREFIX_BEFORE")
    origin["verify_install"](old["manifest"], old["base_snapshot"], before)
    need(origin["base_pth"]() == old["base_pth"], "PTH")
    PHASE = "pip-update"
    installed = origin["run_pip"](
        [
            "install",
            "--no-input",
            "--no-index",
            "--no-deps",
            "--require-hashes",
            "--only-binary=:all:",
            "--no-compile",
            "--no-cache-dir",
            "--force-reinstall",
            "--find-links",
            str(root / "wheels"),
            "-r",
            str(root / "requirements.lock"),
        ],
        "pip-install",
    )
    importlib.invalidate_caches()
    PHASE = "pip-check"
    checked = origin["run_pip"](["check"], "pip-check")
    PHASE = "verify-update"
    after = origin["scan_prefix"]()
    target, projection = validate_manifest(manifest, old, core)
    versions = origin["verify_install"](target, old["base_snapshot"], after)
    need(versions == old["versions"], "VERSIONS")
    core["check_delta"](before, after, projection)
    need(origin["base_pth"]() == old["base_pth"], "PTH")
    PHASE = "imports"
    native = origin["imports_and_native"]()
    need(native == old["native"], "NATIVE")
    imports = w1_imports(origin, projection)
    need(origin["scan_prefix"]() == after, "IMPORT_PREFIX")
    need(read_old(origin) == old, "ORIGIN_ATTEST")
    report = {
        "kind": "oracle9-w1-installed-v1",
        "context_manifest_sha256": MANIFEST_SHA,
        "manifest": manifest,
        "origin_attestation_sha256": OLD_ATTEST_SHA,
        "origin_installed_snapshot": before,
        "base_snapshot": old["base_snapshot"],
        "installed_snapshot": after,
        "base_pth": old["base_pth"],
        "versions": versions,
        "native": native,
        "w1_imports": imports,
    }
    raw = (json.dumps(report, sort_keys=True) + "\n").encode()
    need(len(raw) <= 4 * 1024 * 1024, "ATTEST_SIZE")
    origin["write_new"](ATTEST, raw)
    PHASE = "cleanup-inputs"
    load_context(root, origin, core)  # revalidate SAME three bytes before selective deletion
    (root / "wheels" / core["WHEEL_NAME"]).unlink()
    (root / "wheels").rmdir()
    (root / "requirements.lock").unlink()
    (root / "manifest.json").unlink()
    root.rmdir()
    need(not root.exists(), "INPUTS_REMAIN")
    return {
        "outcome": "W1_APP_UPDATE_VERIFIED",
        "profile": profile,
        "attestation_sha256": sha(raw),
        "attestation_bytes": len(raw),
        "prefix_paths": len(after),
        "versions": versions,
        "native": native,
        "w1_imports": imports,
        "input_modes_before": modes,
        "pip_install": installed,
        "pip_check": checked,
        "managed_inputs_removed": True,
    }


def probe(expected, origin, core):
    global PHASE
    PHASE = "probe-profile"
    profile = origin["runtime_profile"](True)
    origin["parent_environment"]()
    raw = origin["read_regular"](ATTEST, 4 * 1024 * 1024)
    need(sha(raw) == expected, "ATTEST_HASH")
    report = json.loads(raw)
    need(
        report["kind"] == "oracle9-w1-installed-v1"
        and report["context_manifest_sha256"] == MANIFEST_SHA
        and report["origin_attestation_sha256"] == OLD_ATTEST_SHA,
        "ATTEST_KIND",
    )
    need(
        sha((json.dumps(report["manifest"], sort_keys=True) + "\n").encode()) == MANIFEST_SHA,
        "MANIFEST",
    )
    current = origin["scan_prefix"]()
    need(current == report["installed_snapshot"], "PREFIX_AFTER")
    target = report["manifest"]["target"]
    versions = origin["verify_install"](target, report["base_snapshot"], current)
    need(versions == report["versions"], "VERSIONS")
    projection = {k: v for k, v in target["installed_files"].items() if v["owner"] == "maskgw"}
    core["check_delta"](report["origin_installed_snapshot"], current, projection)
    need(origin["base_pth"]() == report["base_pth"], "PTH")
    checked = origin["run_pip"](["check"], "probe-pip-check")
    native = origin["imports_and_native"]()
    imports = w1_imports(origin, projection)
    need(native == report["native"] and imports == report["w1_imports"], "NATIVE")
    need(origin["scan_prefix"]() == current, "IMPORT_PREFIX")
    return {
        "outcome": "W1_APP_PROBE_VERIFIED",
        "profile": profile,
        "attestation_sha256": expected,
        "prefix_paths": len(current),
        "versions": versions,
        "native": native,
        "w1_imports": imports,
        "pip_check": checked,
    }


def main():
    need(
        sys.platform == "linux"
        and sys.flags.isolated == 1
        and sys.flags.dont_write_bytecode == 1
        and sys.flags.optimize == 0,
        "RUNTIME",
    )
    need(len(sys.argv) in (3, 4), "CLI")
    origin, core = libraries()
    if sys.argv[1] == "install":
        need(len(sys.argv) == 4 and sys.argv[3] == MANIFEST_SHA, "CLI")
        result = install(Path(sys.argv[2]), origin, core)
    else:
        need(
            sys.argv[1] == "probe"
            and len(sys.argv) == 3
            and re.fullmatch("[0-9a-f]{64}", sys.argv[2]),
            "CLI",
        )
        result = probe(sys.argv[2], origin, core)
    origin["emit"](result)


def failure_metadata(error):
    reason = None
    if type(error) is UpdateRefusal and type(error.reason) is str and error.reason in _REASONS:
        reason = error.reason
    elif _CORE is not None and type(error) is _CORE["ContextRefusal"]:
        if type(error.category) is str and error.category in _CORE["_CATEGORIES"]:
            reason = error.category
    elif type(error) is RuntimeError and len(error.args) == 1:
        if type(error.args[0]) is str and error.args[0] in _ORIGIN_REASONS:
            reason = error.args[0]  # no str() conversion/custom object execution
    return {
        "outcome": "W1_UPDATE_REFUSED",
        "phase": PHASE,
        "category": type(error).__name__,
        "reason": reason,
    }


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        result = failure_metadata(error)
        if _ORIGIN is not None:
            result["logs"] = _ORIGIN["failure_logs"]()
            _ORIGIN["emit"](result)
        else:
            print(json.dumps(result, sort_keys=True))
        raise SystemExit(1) from None
