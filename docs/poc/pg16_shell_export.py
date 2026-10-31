"""Public projection of one terminal 23-case PG16 shell-reader root.

Projection only: no source byte is copied to the destination. Import defines
functions; no process, Docker, clock, Desktop or laboratory action. This is not
a DLP filter, a release authority or a cleanup authority. Definitions come only
from the accepted entry afaffad0 and the sources it pins.
"""

from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

REPO = Path(__file__).resolve().parents[2]
TEMP_ROOT = Path("C:/Users/w.filho/AppData/Local/Temp")
OUTPUT_PARENT = REPO / "docs/poc/evidence"
ENTRY_RELATIVE = "docs/poc/pg16_shell_run.py"
ENTRY_SHA = "afaffad00ac2a2e9cd1666bdce5e18e6173240b4719592931b9cbda19c90c657"
ORIGINAL_RELATIVE = "docs/poc/oracle9_w1_run.py"
ROOT_PATTERN = r"maskgw-pg16-shell-reader-v1-[0-9a-f]{32}"
DESTINATION_PREFIX = "pg16-shell-reader-run-"
MAX_FILES = 1024
MAX_FILE_BYTES = 4194304
MAX_TOTAL_BYTES = 33554432
MAX_COMMANDS = 512
MAX_OUTPUT_BYTES = 4194304
VERIFIED = "PG16_SHELL_READER_VERIFIED"
CODES = frozenset(
    (
        "EXPORT_REFUSED",
        "EXPORT_SOURCE",
        "EXPORT_JSON",
        "EXPORT_ROOT",
        "EXPORT_DESTINATION",
        "EXPORT_ARTIFACT",
        "EXPORT_SIZE",
        "EXPORT_STATE",
        "EXPORT_TERMINAL",
        "EXPORT_RESOURCE",
        "EXPORT_LEDGER",
        "EXPORT_CAPTURE",
        "EXPORT_DESKTOP",
        "EXPORT_JOURNAL",
        "EXPORT_IMAGE",
        "EXPORT_RECORD",
        "EXPORT_CASE",
        "EXPORT_REPORT",
        "EXPORT_INSPECT",
        "EXPORT_OWNER",
        "EXPORT_WATCHDOG",
        "EXPORT_VOLUME",
        "EXPORT_DIAGNOSTIC",
        "EXPORT_CHANGED",
        "EXPORT_IO",
        "EXPORT_INTERNAL",
    )
)
ROOT_FIXED = frozenset(
    (
        "attempt.json",
        "invoked.json",
        "result.json",
        "ownership.json",
        "cycle.json",
        "desktop.json",
        "processes.json",
        "version.json",
        "daemon.json",
        "start-environment-keys.json",
        "public-cli-manifest.json",
        "cases.json",
        "local-volume-baseline.json",
        "rejected-sample.json",
        "checkpoint-rejected.json",
    )
)
CHECKPOINT = re.compile(r"checkpoint-(?:0[0-9]|1[01])\.json")
REPLY = re.compile(r"local-(?:volume-)?cli-[0-9]{3}\.bin")
METADATA = re.compile(r"volume-(baseline|decision|final)-([0-9]{3})\.json")
MONITOR = re.compile(r"monitor-case-([0-9]{2})-([a-z-]{1,32})-([0-9]{3})\.json")
CASE_FILE = re.compile(r"case-([0-9]{2})-([a-z-]{1,32})-(intent|report)\.json")
OUTPUT_FILE = re.compile(r"local-case-([0-9]{2})-([a-z-]{1,32})-output\.bin")
WATCH_DIRECTORY = re.compile(r"watch-(?:0[1-9]|1[0-9]|2[0-3])")
WATCH_FILE = re.compile(r"(?:emergency|volume-decision|volume-final)-[0-9]{2}\.json")
PS_LABELS = frozenset(
    (
        "initial",
        "start-hidden",
        "OBSERVE",
        "READY",
        "B",
        "preserved-after",
        "never-started",
        "before-stop",
        *("after-stop-" + str(index) for index in range(10)),
    )
)
GLOBAL_LABELS = frozenset(
    (
        "version",
        "info",
        "inventory-preflight",
        "reader-image",
        "volumes-initial",
        "inventory-ready",
        "volumes-final",
        "inventory-final",
        "inventory-before-stop",
        "desktop-stop",
    )
)
SINGLE_LABELS = GLOBAL_LABELS - {"volumes-final"}
# Longest first: inspect-result-/inspect-cleanup- must win over inspect-.
CASE_PREFIXES = (
    "inspect-result-",
    "inspect-cleanup-",
    "volumes-before-",
    "absent-after-",
    "inspect-",
    "create-",
    "kill-",
    "rm-",
)
BLOCK = ("volumes-before-", "create-", "inspect-", "inspect-result-", "inspect-cleanup-")
BLOCK_TAIL = ("rm-", "absent-after-")
MANIFEST_KEYS = frozenset(
    ("index", "label", "artifact", "exit", "sha256", "bytes", "local_only", "raw_disposition")
)
RESULT_REQUIRED = frozenset(
    (
        "outcome",
        "desktop_restored",
        "inventory_restored",
        "volumes_restored",
        "desktop_state",
        "terminal_resources_verified",
        "inputs_unchanged",
        "commands",
        "checkpoint_count",
        "cleanup_attempts",
        "interrupted",
        "watchdogs",
    )
)
RESULT_OPTIONAL = frozenset(
    (
        "owned_cleanup",
        "pg16_reader_verified",
        "journal_verified",
        "journal_last_sha256",
        "error_history",
    )
)
RESOURCE_KEYS = (
    "owned_cleanup",
    "inventory_restored",
    "volumes_restored",
    "desktop_restored",
    "terminal_resources_verified",
    "inputs_unchanged",
    "journal_verified",
    "pg16_reader_verified",
)
RECORD_KEYS = frozenset(
    (
        "role",
        "case",
        "name",
        "image",
        "cid",
        "removed",
        "create_uncertain",
        "create_invoked",
        "intent_persisted",
        "case_volume_restored",
    )
)
RECORD_OPTIONAL = frozenset(("volume_uncertain", "cleanup_unproven", "create_not_invoked"))
CASE_ROW_KEYS = frozenset(
    (
        "case",
        "owner",
        "removed",
        "case_volume_restored",
        "returncode",
        "stdout_bytes",
        "report_bytes",
        "inspect_exit_code",
        "oom_killed",
        "dead",
        "report_ok",
        "report_category",
        "inspect_label",
        "inspect_cli_index",
        "inspect_artifact",
        "delivery",
        "monitor",
    )
)
OWNER_KEYS = frozenset(
    (
        "phase",
        "role",
        "cid",
        "fault",
        "seed_delivery",
        "stdout_bytes",
        "retained_stdout_bytes",
        "released",
    )
)
WATCH_KEYS = frozenset(
    (
        "fired",
        "held",
        "category",
        "cid_absent",
        "released",
        "volumes_restored",
        "volume_uncertain",
        "thread_joined",
    )
)
MONITOR_ERRORS = frozenset(
    ("MONITOR_CLOSE", "HEARTBEAT", "MONITOR_METADATA", "MONITOR_JOIN", "MONITOR_EVIDENCE")
)
PHASES = frozenset(("failure", "cleanup", "stop", "restore", "pins", "persist", "deadline"))
DEADLINE_MARKERS = frozenset(("RESTORE_MARGIN", "POST_B_OVERRUN"))
# Same literal tuple as the accepted entry diagnostic for ProbeError.
PROFILE_CODES = frozenset(
    (
        "CID",
        "COMMAND",
        "CONFIG",
        "EXIT",
        "IMAGE",
        "IMAGE_ENV",
        "IMAGE_LABELS",
        "INTENT",
        "JSON",
        "MOUNTS",
        "OS",
        "OWNERSHIP",
        "PROFILE",
        "REPORT",
        "SURFACE",
        "TASK",
        "TOOLS",
        "UID",
        "VERSION",
    )
)
DESKTOP_MODES = {
    "PRESERVED_ACTIVE": (True, "PRESERVED"),
    "OFF_WITHOUT_START": (False, "START_RESERVED"),
    "OFF_CONFIRMED": (False, "STARTED"),
}


class ExportError(Exception):
    def __init__(self, code):
        super().__init__(code if type(code) is str and code in CODES else "EXPORT_INTERNAL")


def need(value, code="EXPORT_REFUSED"):
    if not value:
        raise ExportError(code) from None


def guarded(code, function, *args, **kwargs):
    """Pinned helpers raise their own classes; only a closed code leaves here."""
    failed, result = False, None
    try:
        result = function(*args, **kwargs)
    except Exception:
        failed = True
    need(not failed, code)
    return result


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def same(left, right):
    """Typed JSON equality: False is not 0, 1.0 is not 1, list order matters."""
    return encoded(left) == encoded(right)


def hex64(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def _reject(_value):
    raise ValueError()


def value(raw, code="EXPORT_JSON"):
    need(type(raw) is bytes, code)

    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError()
            result[key] = item
        return result

    decoded, valid = None, False
    try:
        decoded = json.loads(raw, object_pairs_hook=pairs, parse_constant=_reject)
        valid = True
    except (ValueError, UnicodeError, RecursionError):
        pass
    need(valid, code)
    return decoded


def canonical(raw, code):
    """Every parsed source artifact was written with the canonical json_bytes."""
    item = value(raw, code)
    need(encoded(item) == raw, code)
    return item


def reparse(info):
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


def regular(path, maximum=None):
    """Bounded read: never allocates more than limit+1 bytes, even if the file grew."""
    limit = MAX_FILE_BYTES if maximum is None else maximum
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and not reparse(info), "EXPORT_ARTIFACT")
    need(info.st_size <= limit, "EXPORT_SIZE")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    need(type(raw) is bytes and len(raw) <= limit, "EXPORT_SIZE")
    need(len(raw) == info.st_size, "EXPORT_CHANGED")
    return raw


def directory_chain(path, code):
    """The directory and every ancestor: real directories, no link or reparse point."""
    for item in (path, *path.parents):
        info = item.lstat()
        need(stat.S_ISDIR(info.st_mode) and not reparse(info), code)


def absent(path):
    missing = False
    try:
        path.lstat()
    except FileNotFoundError:
        missing = True
    return missing


class _Sources:
    """Exact pinned bytes for the accepted entry vocabulary; no Host is built."""

    def __init__(self, original, captured, pg_raw):
        self._original_raw, self.captured, self.pg_raw = original, captured, pg_raw


def definitions():
    path = REPO / ENTRY_RELATIVE
    raw = regular(path, 65536)
    need(sha(raw) == ENTRY_SHA, "EXPORT_SOURCE")
    entry = {"__name__": "_pg16_shell_export_entry", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), entry)
    host, base = entry["H"], entry["R"]
    captured = host["P"]["captured"]
    loaded = {
        key: captured(*host["SOURCES"][key])[0]
        for key in ("profile", "delivery", "policy", "volumes", "watch")
    }
    libraries = {
        relative: base["pinned"](REPO / relative, digest)
        for relative, digest in base["LIBRARIES"].values()
    }
    sources = {
        relative: base["pinned"](REPO / relative, digest)
        for relative, digest in host["SOURCES"].values()
    }
    original = base["pinned"](REPO / ORIGINAL_RELATIVE, host["V2"]["ORIGINAL_SHA"])
    loaded.update(
        entry=entry,
        host=host,
        base=base,
        core=captured(*base["LIBRARIES"]["core"])[0],
        reader=loaded["profile"]["R"],
        cases=tuple(host["CASES"]),
        runtime_codes=entry["vocabulary"](_Sources(original, libraries, sources)),
    )
    loaded["pins"] = public_pins(loaded)
    return loaded


def public_pins(d):
    """Every public repository source captured above; no configuration or binary."""
    entry, host, base = d["entry"], d["host"], d["base"]
    pins = {
        ENTRY_RELATIVE: ENTRY_SHA,
        entry["HOST_RELATIVE"]: entry["HOST_SHA"],
        "docs/poc/pg16_public_host.py": host["PARENT_SHA"],
        "docs/poc/oracle9_w1_run_v2.py": host["P"]["V2_SHA"],
        ORIGINAL_RELATIVE: host["V2"]["ORIGINAL_SHA"],
    }
    for relative, digest in (
        *base["LIBRARIES"].values(),
        *host["SOURCES"].values(),
        *entry["TRANSITIVE_PINS"].items(),
    ):
        need(pins.setdefault(relative, digest) == digest, "EXPORT_SOURCE")
    return pins


def recheck_sources(d):
    for relative, digest in d["pins"].items():
        need(sha(regular(REPO / relative, 65536)) == digest, "EXPORT_SOURCE")


def case_pair(number, name, cases):
    return 1 <= int(number) <= len(cases) and cases[int(number) - 1] == name


def allowed(name, cases):
    if name in ROOT_FIXED or CHECKPOINT.fullmatch(name) or REPLY.fullmatch(name):
        return True
    if METADATA.fullmatch(name):
        return True
    for pattern in (MONITOR, CASE_FILE, OUTPUT_FILE):
        match = pattern.fullmatch(name)
        if match is not None:
            return case_pair(match[1], match[2], cases)
    return False


def snapshot(root, cases):
    """Root plus closed watch-NN directories, one depth, with caps before reads."""
    entries, files, dirs, total = [], {}, [], 0
    for index, path in enumerate(root.iterdir()):
        need(index < MAX_FILES, "EXPORT_SIZE")
        entries.append(path)
    for path in sorted(entries, key=lambda item: item.name):
        info = path.lstat()
        need(not reparse(info), "EXPORT_ARTIFACT")
        if stat.S_ISDIR(info.st_mode):
            need(WATCH_DIRECTORY.fullmatch(path.name) is not None, "EXPORT_ARTIFACT")
            dirs.append(path.name)
            children = []
            for index, child in enumerate(path.iterdir()):
                need(index < MAX_FILES, "EXPORT_SIZE")
                children.append(child)
            for child in sorted(children, key=lambda item: item.name):
                need(WATCH_FILE.fullmatch(child.name) is not None, "EXPORT_ARTIFACT")
                raw = regular(child)
                total += len(raw)
                files[path.name + "/" + child.name] = raw
                need(len(files) + len(dirs) <= MAX_FILES, "EXPORT_SIZE")
                need(total <= MAX_TOTAL_BYTES, "EXPORT_SIZE")
        else:
            need(allowed(path.name, cases), "EXPORT_ARTIFACT")
            raw = regular(path)
            total += len(raw)
            files[path.name] = raw
        need(len(files) + len(dirs) <= MAX_FILES, "EXPORT_SIZE")
        need(total <= MAX_TOTAL_BYTES, "EXPORT_SIZE")
    return files, tuple(dirs)


def label_kind(label, cases):
    if type(label) is not str:
        return None
    if label in PS_LABELS:
        return ("ps", None, None)
    if label in GLOBAL_LABELS:
        return ("cli", None, None)
    for prefix in CASE_PREFIXES:
        if label.startswith(prefix) and label[len(prefix) :] in cases:
            return ("case", prefix, label[len(prefix) :])
    return None


def expected_state(task, phase, d):
    entry, host, base = d["entry"], d["host"], d["base"]
    profile, delivery, case = d["profile"], d["delivery"], d["reader"]["Case"]
    return {
        "kind": "maskgw-pg16-shell-reader-v1",
        "task": task,
        "phase": phase,
        "invoked": True,
        "program_sha256": host["V2"]["ORIGINAL_SHA"],
        "v2_sha256": host["P"]["V2_SHA"],
        "parent_sha256": host["PARENT_SHA"],
        "host_sha256": entry["HOST_SHA"],
        "entry_sha256": ENTRY_SHA,
        "pins": dict(base["LIBRARIES"].values()),
        "pg_pins": dict(host["SOURCES"].values()),
        "transitive_pins": dict(entry["TRANSITIVE_PINS"]),
        "stdlib_pins": dict(entry["C"]["STDLIB_PINS"]),
        "image": entry["IMAGE"],
        "create_measurements": {
            name: profile["blueprint"](task, case(name))[1] for name in d["cases"]
        },
        "delivery_plan": {name: asdict(delivery["delivery_for"](name)[1]) for name in d["cases"]},
    }


def terminal(result, phase, reported_exit):
    need(
        type(result) is dict
        and RESULT_REQUIRED <= set(result) <= RESULT_REQUIRED | RESULT_OPTIONAL,
        "EXPORT_TERMINAL",
    )
    success = reported_exit == 0
    need(
        success == (phase == "FINISHED")
        and result["outcome"] == (VERIFIED if success else "NOT_PASSED"),
        "EXPORT_TERMINAL",
    )
    need(
        result["terminal_resources_verified"] is True and result["desktop_restored"] is True,
        "EXPORT_RESOURCE",
    )
    need(
        all(type(result.get(key, False)) is bool for key in RESOURCE_KEYS)
        and type(result["interrupted"]) is bool
        and integer(result["cleanup_attempts"], 0, 2)
        and integer(result["checkpoint_count"], 0, 12)
        and ("journal_last_sha256" not in result or hex64(result["journal_last_sha256"])),
        "EXPORT_TERMINAL",
    )
    if success:
        need(
            all(result.get(key) is True for key in RESOURCE_KEYS)
            and result["interrupted"] is False
            and result["cleanup_attempts"] == 1
            and not result.get("error_history"),
            "EXPORT_RESOURCE",
        )
    return success


def ledger(result, cases):
    rows = result["commands"]
    need(type(rows) is list and len(rows) <= MAX_COMMANDS, "EXPORT_LEDGER")
    output = []
    for position, row in enumerate(rows, 1):
        need(
            type(row) is dict
            and set(row) == {"label", "exit", "bytes", "sha256", "seconds"}
            and label_kind(row["label"], cases) is not None
            and integer(row["exit"], -(1 << 31), (1 << 32) - 1)
            and integer(row["bytes"], 0, 2097152)
            and hex64(row["sha256"])
            and type(row["seconds"]) is float
            and math.isfinite(row["seconds"])
            and 0 <= row["seconds"] <= 3600,
            "EXPORT_LEDGER",
        )
        output.append({"position": position, **{key: row[key] for key in sorted(row)}})
    return output


def captures(files, commands, cases):
    raw = files.get("public-cli-manifest.json")
    rows = [] if raw is None else canonical(raw, "EXPORT_CAPTURE")
    need(type(rows) is list and len(rows) <= MAX_COMMANDS, "EXPORT_CAPTURE")
    cli = [row for row in commands if label_kind(row["label"], cases)[0] != "ps"]
    need(len(cli) == len(rows), "EXPORT_CAPTURE")
    replies, seen, previous = [], set(), 0
    for row, command in zip(rows, cli, strict=True):
        need(
            type(row) is dict
            and set(row) == MANIFEST_KEYS
            and integer(row["index"], previous + 1, 999)
            and row["local_only"] is True
            and row["label"] == command["label"]
            and all(
                type(row[key]) is type(command[key]) and row[key] == command[key]
                for key in ("exit", "bytes", "sha256")
            ),
            "EXPORT_CAPTURE",
        )
        previous = row["index"]
        name, body = row["artifact"], None
        if name is None:
            need(
                row["raw_disposition"] == "DISCARDED_CONFIGURATION"
                and row["label"] in ("version", "info"),
                "EXPORT_CAPTURE",
            )
        else:
            prefix = "local-volume-cli-" if row["label"].startswith("volumes-") else "local-cli-"
            need(
                row["label"] not in ("version", "info")
                and row["raw_disposition"] == "LOCAL_ONLY"
                and name == prefix + str(row["index"]).zfill(3) + ".bin"
                and name in files
                and name not in seen,
                "EXPORT_CAPTURE",
            )
            body = files[name]
            need(len(body) == row["bytes"] and sha(body) == row["sha256"], "EXPORT_CAPTURE")
            seen.add(name)
        replies.append(
            {
                "position": len(replies),
                "index": row["index"],
                "label": row["label"],
                "exit": row["exit"],
                "bytes": row["bytes"],
                "sha256": row["sha256"],
                "artifact": name,
                "raw": body,
            }
        )
    need(seen == {name for name in files if REPLY.fullmatch(name)}, "EXPORT_CAPTURE")
    return replies


def desktop_projection(files, result, a_entered):
    current = result["desktop_state"]
    if not a_entered:
        need(
            current == "UNTOUCHED_PRE_A"
            and "desktop.json" not in files
            and "cycle.json" not in files
            and not result["commands"]
            and "owned_cleanup" not in result
            and result["inventory_restored"] is False
            and result["volumes_restored"] is False,
            "EXPORT_DESKTOP",
        )
        return {"state": current, "initial_active": None}
    need(current in DESKTOP_MODES and "desktop.json" in files, "EXPORT_DESKTOP")
    desktop = canonical(files["desktop.json"], "EXPORT_DESKTOP")
    active, phase = DESKTOP_MODES[current]
    need(
        type(desktop) is dict
        and set(desktop) <= {"initial_active", "phase", "identity"}
        and desktop.get("initial_active") is active
        and desktop.get("phase") == phase
        and ("identity" in desktop) == (phase == "STARTED"),
        "EXPORT_DESKTOP",
    )
    need(
        result.get("owned_cleanup") is True and result["inventory_restored"] is True,
        "EXPORT_RESOURCE",
    )
    return {"state": current, "initial_active": active}


def journal_projection(files, result, d, success, a_entered):
    names = sorted(name for name in files if CHECKPOINT.fullmatch(name))
    need(
        names == ["checkpoint-" + str(i).zfill(2) + ".json" for i in range(len(names))]
        and result["checkpoint_count"] == len(names),
        "EXPORT_JOURNAL",
    )
    rejected = "rejected-sample.json" in files or "checkpoint-rejected.json" in files
    if not a_entered:
        need(not names and not rejected and "journal_verified" not in result, "EXPORT_JOURNAL")
    head, interval, equal, state = None, None, None, None
    if names:
        state, head = guarded(
            "EXPORT_JOURNAL",
            d["host"]["V2"]["replay"],
            d["core"],
            [files[name] for name in names],
            require_b=len(names) == 12,
        )
        equal = state.anchor.boot == state.last.boot
        if len(names) == 12:
            interval = int(state.last.tick_ms) - int(state.anchor.tick_ms)
    if success or result.get("journal_verified") is True:
        need(len(names) == 12 and result.get("journal_last_sha256") == head, "EXPORT_JOURNAL")
    if success:
        cycle = guarded("EXPORT_JOURNAL", d["core"]["encode"], state)
        need(
            not rejected
            and "cycle.json" in files
            and encoded(value(cycle, "EXPORT_JOURNAL")) == files["cycle.json"],
            "EXPORT_JOURNAL",
        )
    return {
        "checkpoint_count": len(names),
        "head": head,
        "interval_a_b_ms": interval,
        "boot_equal": equal,
        "rejected_sample_present": rejected,
    }


def diagnostics(result, d, success):
    history = result.get("error_history", [])
    origins = {
        "CONTROL": frozenset(("CANCELLED", "DEADLINE", "INTERRUPTED")) | DEADLINE_MARKERS,
        "BOOTSTRAP": frozenset(item.value for item in d["entry"]["C"]["Fault"]),
        "READER": frozenset(item.value for item in d["reader"]["Code"]),
        "RUNTIME": d["runtime_codes"],
        "VALUE": frozenset(("CYCLE_SCHEMA",)),
        "PROFILE": PROFILE_CODES,
        "VOLUME": frozenset(("VOLUME_INVENTORY",)),
        "IDENTITY": frozenset(("IDENTITY_UNKNOWN",)),
        "EMERGENCY": frozenset(("BUDGET", "COMMAND", "INPUT", "PIN")),
        "HOST_FAULT": d["entry"]["BOUNDED_CODES"],
        "INTERNAL": frozenset(("INTERNAL",)),
    }
    need(type(history) is list and len(history) <= 64, "EXPORT_DIAGNOSTIC")
    for item in history:
        need(
            type(item) is dict
            and set(item) == {"phase", "category", "origin"}
            and item["phase"] in PHASES
            and item["origin"] in origins
            and type(item["category"]) is str
            and item["category"] in origins[item["origin"]]
            and (item["phase"] == "deadline") == (item["category"] in DEADLINE_MARKERS),
            "EXPORT_DIAGNOSTIC",
        )
    need(not success or not history, "EXPORT_DIAGNOSTIC")
    return {
        "history": [dict(item) for item in history],
        "interrupted": result["interrupted"],
        "cleanup_attempts": result["cleanup_attempts"],
    }


def watchdog_projection(files, dirs, result, cases, success):
    rows = result["watchdogs"]
    need(type(rows) is dict, "EXPORT_WATCHDOG")
    count = len(rows)
    need(
        set(rows) == set(cases[:count])
        and list(dirs) == ["watch-" + str(i).zfill(2) for i in range(1, len(dirs) + 1)]
        and len(dirs) in (count, count + 1)
        and (not success or count == len(dirs) == len(cases)),
        "EXPORT_WATCHDOG",
    )
    # A watchdog writes evidence only after a fire; fired lots are not exported here.
    need(not any("/" in name for name in files), "EXPORT_WATCHDOG")
    evidence = {}
    for name in files:
        match = MONITOR.fullmatch(name)
        if match is not None:
            evidence.setdefault(match[2], []).append((int(match[3]), name))
    need(set(evidence) <= set(cases[:count]), "EXPORT_WATCHDOG")
    output, attempted = [], []
    for case in cases[:count]:
        row = rows[case]
        need(
            type(row) is dict
            and set(row) == {"status", "metadata", "errors"}
            and row["errors"] == []
            and row["status"] in ("NOT_STARTED", "JOINED"),
            "EXPORT_WATCHDOG",
        )
        meta = row["metadata"]
        need(
            type(meta) is dict
            and set(meta) == WATCH_KEYS
            and meta["fired"] is False
            and meta["held"] is False
            and meta["released"] is False
            and meta["category"] is None
            and meta["cid_absent"] is False
            and meta["volumes_restored"] is False
            and meta["volume_uncertain"] is False
            and meta["thread_joined"] is (row["status"] == "JOINED"),
            "EXPORT_WATCHDOG",
        )
        if row["status"] == "JOINED":
            attempted.append(case)
        items = sorted(evidence.get(case, []))
        need(bool(items), "EXPORT_WATCHDOG")
        unproven = False
        for _, name in items:
            item = canonical(files[name], "EXPORT_WATCHDOG")
            need(
                type(item) is dict
                and set(item) == {"case", "status", "metadata", "errors"}
                and item["case"] == case
                and item["status"] in ("NOT_STARTED", "JOINED", "HELD")
                and type(item["errors"]) is list
                and all(error in MONITOR_ERRORS for error in item["errors"])
                and type(item["metadata"]) is dict
                and set(item["metadata"]) <= WATCH_KEYS,
                "EXPORT_WATCHDOG",
            )
            unproven = unproven or item["status"] == "HELD" or bool(item["errors"])
        need(files[items[-1][1]] == encoded({"case": case, **row}), "EXPORT_WATCHDOG")
        need(not success or not unproven, "EXPORT_WATCHDOG")
        output.append(
            {
                "case": case,
                "status": row["status"],
                "thread_joined": meta["thread_joined"],
                "fired": False,
                "held": False,
                "evidence_count": len(items),
                "earlier_unproven": unproven,
            }
        )
    need(attempted == list(cases[: len(attempted)]), "EXPORT_WATCHDOG")
    return output, len(attempted), {case: rows[case]["metadata"] for case in cases[:count]}


def metadata_sequence(files, success):
    sequence = []
    for name in files:
        for pattern, group in ((METADATA, 2), (MONITOR, 3)):
            match = pattern.fullmatch(name)
            if match is not None:
                sequence.append(int(match[group]))
    need(len(sequence) == len(set(sequence)), "EXPORT_ARTIFACT")
    # A failed evidence write consumes a number; only a passing lot is gapless.
    need(not success or sorted(sequence) == list(range(1, len(sequence) + 1)), "EXPORT_ARTIFACT")


def records_projection(files, cases, task, image, d, success):
    profile, case_type = d["profile"], d["reader"]["Case"]
    raw = files.get("ownership.json")
    rows = [] if raw is None else canonical(raw, "EXPORT_RECORD")
    need(type(rows) is list and len(rows) <= len(cases), "EXPORT_RECORD")
    need(not rows or image is not None, "EXPORT_IMAGE")
    intents, cids = {}, set()
    for index, record in enumerate(rows):
        case = cases[index]
        need(
            type(record) is dict
            and RECORD_KEYS <= set(record) <= RECORD_KEYS | RECORD_OPTIONAL
            and record["case"] == case
            and record["role"] == "pg16-reader"
            and record["image"] == profile["IMAGE"]
            and record["intent_persisted"] is True
            and "cleanup_unproven" not in record
            and record.get("volume_uncertain", False) is False,
            "EXPORT_RECORD",
        )
        intent = guarded("EXPORT_RECORD", profile["Intent"], task, image, case_type(case))
        intents[case] = intent
        initial = {
            "role": "pg16-reader",
            "case": case,
            "name": intent.name,
            "image": profile["IMAGE"],
            "command": list(intent.command),
            "cid": None,
            "removed": False,
            "create_uncertain": True,
            "create_invoked": False,
            "intent_persisted": False,
            "case_volume_restored": False,
        }
        stem = "case-" + str(index + 1).zfill(2) + "-" + case
        need(
            record["name"] == intent.name and files.get(stem + "-intent.json") == encoded(initial),
            "EXPORT_RECORD",
        )
        if record.get("create_not_invoked") is True:
            need(
                index == len(rows) - 1
                and not success
                and record["cid"] is None
                and record["create_invoked"] is False
                and record["create_uncertain"] is True
                and record["removed"] is False
                and record["case_volume_restored"] is False,
                "EXPORT_RECORD",
            )
        else:
            need(
                "create_not_invoked" not in record
                and record["create_invoked"] is True
                and record["create_uncertain"] is False
                and hex64(record["cid"])
                and record["cid"] not in cids
                and record["removed"] is True
                and record["case_volume_restored"] is True,
                "EXPORT_RECORD",
            )
            cids.add(record["cid"])
    for name in files:
        for pattern in (CASE_FILE, OUTPUT_FILE):
            match = pattern.fullmatch(name)
            if match is not None:
                need(int(match[1]) <= len(rows), "EXPORT_RECORD")
    return rows, intents


def inspected(case, items, record, intent, d, task):
    """Every exit-0 inspect of an own CID must pass the pinned ownership identity."""
    infos = {}
    for position, prefix, reply in items:
        if prefix not in ("inspect-", "inspect-result-", "inspect-cleanup-") or reply["exit"] != 0:
            continue
        info = guarded("EXPORT_INSPECT", d["profile"]["P"]["one"], reply["raw"])
        guarded(
            "EXPORT_INSPECT",
            d["policy"]["identity"],
            info,
            task=task,
            case=case,
            command=intent.command,
            cid=record["cid"],
        )
        infos[position] = info
    return infos


def state_projection(info):
    current = info.get("State")
    need(
        type(current) is dict
        and all(type(current.get(key)) is bool for key in ("Running", "OOMKilled", "Dead"))
        and integer(current.get("Pid"), 0, 1 << 32)
        and type(current.get("ExitCode")) is int,
        "EXPORT_INSPECT",
    )
    return {key: current[key] for key in ("Running", "Pid", "OOMKilled", "Dead", "ExitCode")}


def verified_report(files, index, case, returncode, task, d):
    reader = d["reader"]
    stem = str(index + 1).zfill(2) + "-" + case
    output = files.get("local-case-" + stem + "-output.bin")
    report = files.get("case-" + stem + "-report.json")
    if report is None:
        return None, output
    need(output is not None, "EXPORT_REPORT")
    facts = guarded(
        "EXPORT_REPORT", reader["parse_report"], output, returncode, task, reader["Case"](case)
    )
    need(type(facts) is dict and encoded(facts) == report, "EXPORT_REPORT")
    return facts, output


def report_projection(facts, vector):
    positive = vector.fault is None
    need(facts["ok"] is positive, "EXPORT_REPORT")
    category = None if positive else facts["category"]
    need(category == (None if positive else vector.fault.value), "EXPORT_REPORT")
    return {
        "ok": positive,
        "category": category,
        "tail": facts.get("tail") if positive else None,
        "body_bytes": facts.get("body_bytes") if positive else None,
        "body_sha256": facts.get("body_sha256") if positive else None,
    }


def complete_block(items, replies, cid):
    prefixes = tuple(prefix for _, prefix, _ in items)
    need(
        prefixes in (BLOCK + BLOCK_TAIL, BLOCK + ("kill-", "inspect-") + BLOCK_TAIL),
        "EXPORT_CASE",
    )
    positions = [position for position, _, _ in items]
    first = positions[0]
    need(positions == list(range(first, first + len(positions))), "EXPORT_CASE")
    after = positions[-1] + 1
    need(
        after < len(replies)
        and replies[after]["label"] == "volumes-final"
        and replies[after]["exit"] == 0
        and all(reply["exit"] == 0 for _, _, reply in items),
        "EXPORT_CASE",
    )
    create, remove, gone = items[1][2]["raw"], items[-2][2]["raw"], items[-1][2]["raw"]
    need(
        re.fullmatch(rb"[0-9a-f]{64}\s*", create) is not None
        and create.strip() == cid.encode("ascii")
        and remove.strip() == cid.encode("ascii")
        and not gone.strip(),
        "EXPORT_RECORD",
    )
    return first, after, "kill-" in prefixes


def incomplete_items(items, record):
    if record["cid"] is None:
        need(all(prefix == "volumes-before-" for _, prefix, _ in items), "EXPORT_CASE")
        return
    creates = [reply for _, prefix, reply in items if prefix == "create-"]
    need(
        len(creates) == 1
        and creates[0]["exit"] == 0
        and creates[0]["raw"].strip() == record["cid"].encode("ascii")
        and items[-1][1] == "absent-after-"
        and items[-1][2]["exit"] == 0
        and not items[-1][2]["raw"].strip(),
        "EXPORT_CASE",
    )


def owner_projection(owner, row, cid):
    need(
        type(owner) is dict
        and set(owner) == OWNER_KEYS
        and owner["phase"] == "CLOSED"
        and owner["role"] == "P"
        and owner["cid"] == cid
        and owner["fault"] is None
        and owner["seed_delivery"] == "SENT"
        and owner["released"] is True
        and same(owner["stdout_bytes"], row["stdout_bytes"])
        and same(owner["retained_stdout_bytes"], row["report_bytes"]),
        "EXPORT_OWNER",
    )
    # The inherited channel field names the PUBLIC vector here: local CLI pipe
    # handoff only, never a private seed or proof of container receipt.
    return {
        "phase": "CLOSED",
        "released": True,
        "fault": None,
        "vector_delivery": "SENT_LOCAL_HANDOFF",
        "private_seed": "NOT_APPLICABLE",
    }


def volume_projection(files, replies, records, infos, result, d, success):
    core, digest = d["volumes"], d["watch"]["volume_sha256"]
    metadata = []
    for name in files:
        match = METADATA.fullmatch(name)
        if match is not None:
            metadata.append((int(match[2]), match[1], name))
    metadata.sort()
    raw = files.get("local-volume-baseline.json")
    if raw is None:
        need(
            not records
            and not metadata
            and result["volumes_restored"] is False
            and not any(reply["label"].startswith("volumes-") for reply in replies),
            "EXPORT_VOLUME",
        )
        return {
            "status": "NOT_ADMITTED",
            "initial_count": None,
            "initial_sha256": None,
            "decisions": [],
            "finals": [],
        }, frozenset()
    baseline = canonical(raw, "EXPORT_VOLUME")
    need(
        type(baseline) is dict
        and set(baseline) == {"kind", "names"}
        and baseline["kind"] == "MASKGW_PG16_LOCAL_VOLUME_BASELINE_V1"
        and type(baseline["names"]) is list
        and all(type(name) is str for name in baseline["names"])
        and baseline["names"] == sorted(set(baseline["names"])),
        "EXPORT_VOLUME",
    )
    initial = guarded("EXPORT_VOLUME", core["checked"], frozenset(baseline["names"]))
    starts = [reply for reply in replies if reply["label"] == "volumes-initial"]
    need(
        len(starts) == 1
        and starts[0]["exit"] == 0
        and guarded("EXPORT_VOLUME", core["inventory"], starts[0]["raw"]) == initial,
        "EXPORT_VOLUME",
    )
    recorded = {record["case"] for record in records}
    for reply in replies:
        if reply["label"].startswith("volumes-before-") and reply["exit"] == 0:
            if reply["label"][len("volumes-before-") :] in recorded:
                names = guarded("EXPORT_VOLUME", core["inventory"], reply["raw"])
                need(names == initial, "EXPORT_VOLUME")
    by_case = {record["case"]: record["cid"] for record in records if record["cid"] is not None}
    # Chronology from the ledger: the host writes a decision immediately before
    # each rm of that CID, and a final immediately after each successful
    # volumes-final listing. Metadata must follow exactly this order.
    events = []
    for reply in replies:
        if reply["label"].startswith("rm-"):
            cid = by_case.get(reply["label"][len("rm-") :])
            need(cid is not None, "EXPORT_VOLUME")
            events.append(("decision", cid, reply))
        elif reply["label"] == "volumes-final" and reply["exit"] == 0:
            events.append(("final", None, reply))
    expected_baseline = encoded(
        {
            "kind": "MASKGW_PG16_PUBLIC_VOLUME_BASELINE_V1",
            "count": len(initial),
            "sha256": digest(initial),
        }
    )
    need(
        bool(metadata)
        and metadata[0][1] == "baseline"
        and files[metadata[0][2]] == expected_baseline
        and all(kind != "baseline" for _, kind, _ in metadata[1:]),
        "EXPORT_VOLUME",
    )
    pointer, latest, decisions, finals_out, restored = 0, {}, [], [], set()
    for _, kind, name in metadata[1:]:
        event = events[pointer] if pointer < len(events) else None
        if kind == "decision":
            item = canonical(files[name], "EXPORT_VOLUME")
            need(type(item) is dict and hex64(item.get("cid")), "EXPORT_VOLUME")
            need(item["cid"] in infos, "EXPORT_VOLUME")
            known = infos[item["cid"]]
            if event is not None and event[0] == "decision" and event[1] == item["cid"]:
                pointer += 1
                # Bound to the last own inspect before THIS rm, never a later one.
                before = [position for position in sorted(known) if position < event[2]["position"]]
                need(bool(before), "EXPORT_VOLUME")
                candidates = [known[before[-1]]]
            else:
                # Abort only: a decision whose rm never ran is followed later by
                # a retried decision for the same CID; never in a passing lot.
                need(
                    not success
                    and any(
                        later[0] == "decision" and later[1] == item["cid"]
                        for later in events[pointer:]
                    ),
                    "EXPORT_VOLUME",
                )
                candidates = list(known.values())
            matched = None
            for info in candidates:
                decision = guarded("EXPORT_VOLUME", core["removal"], initial, info.get("Mounts"))
                expected = {
                    "kind": "MASKGW_PG16_PUBLIC_VOLUME_DECISION_V1",
                    "cid": item["cid"],
                    "mode": decision.mode.value,
                    "linked_count": len(decision.names),
                    "linked_sha256": digest(decision.names),
                    "preexisting_count": len(decision.preexisting),
                    "preexisting_sha256": digest(decision.preexisting),
                    "new_anonymous_names": [
                        volume
                        for volume in decision.names
                        if volume not in initial and hex64(volume)
                    ],
                }
                if files[name] == encoded(expected):
                    matched = decision
            need(
                matched is not None and matched.mode.value in ("WITH_V", "PRESERVE_EXISTING"),
                "EXPORT_VOLUME",
            )
            latest[item["cid"]] = frozenset(matched.names)
            decisions.append({key: item[key] for key in sorted(item) if key != "kind"})
        else:
            need(event is not None and event[0] == "final", "EXPORT_VOLUME")
            pointer += 1
            reply = event[2]
            names = guarded("EXPORT_VOLUME", core["inventory"], reply["raw"])
            delta = guarded("EXPORT_VOLUME", core["difference"], initial, names)
            ok = not delta.added and not delta.missing
            expected = {
                "kind": "MASKGW_PG16_PUBLIC_VOLUME_FINAL_V1",
                "initial_count": len(initial),
                "initial_sha256": digest(initial),
                "final_count": len(names),
                "final_sha256": digest(names),
                "added_count": len(delta.added),
                "missing_count": len(delta.missing),
                "added_within_linked": set(delta.added) <= set().union(*latest.values()),
                "restored": ok,
                "uncertain": False,
            }
            need(files[name] == encoded(expected), "EXPORT_VOLUME")
            if ok:
                restored.add(reply["position"])
            finals_out.append(
                {
                    "cli_index": reply["index"],
                    "final_count": len(names),
                    "final_sha256": digest(names),
                    "added_count": len(delta.added),
                    "missing_count": len(delta.missing),
                    "restored": ok,
                }
            )
    need(
        pointer == len(events)
        and bool(finals_out)
        and finals_out[-1]["restored"] is True
        and result["volumes_restored"] is True,
        "EXPORT_VOLUME",
    )
    return {
        "status": "RESTORED",
        "initial_count": len(initial),
        "initial_sha256": digest(initial),
        "decisions": decisions,
        "finals": finals_out,
    }, frozenset(restored)


def global_replies(replies, success, a_entered, desktop_state):
    counts = Counter(reply["label"] for reply in replies)
    need(all(counts[label] <= 1 for label in SINGLE_LABELS), "EXPORT_LEDGER")
    if success:
        need(
            all(
                counts[label] == 1
                for label in (
                    "version",
                    "info",
                    "inventory-preflight",
                    "reader-image",
                    "volumes-initial",
                    "inventory-ready",
                    "inventory-final",
                )
            ),
            "EXPORT_LEDGER",
        )
    if a_entered:
        need(counts["inventory-final"] == 1, "EXPORT_RESOURCE")
    for reply in replies:
        if reply["label"] in ("inventory-final", "inventory-before-stop") or (
            success and reply["label"].startswith("inventory-")
        ):
            need(reply["exit"] == 0 and not reply["raw"].strip(), "EXPORT_RESOURCE")
    stops = [reply for reply in replies if reply["label"] == "desktop-stop"]
    if desktop_state == "OFF_CONFIRMED":
        need(
            len(stops) == 1 and stops[0]["exit"] == 0 and counts["inventory-before-stop"] == 1,
            "EXPORT_DESKTOP",
        )
    else:
        need(not stops, "EXPORT_DESKTOP")


def image_projection(replies, profile, success):
    images = [reply for reply in replies if reply["label"] == "reader-image"]
    image = None
    if images and images[0]["exit"] == 0:
        image = guarded("EXPORT_IMAGE", profile["admit_image"], images[0]["raw"])
    need(not success or image is not None, "EXPORT_IMAGE")
    version = None
    if image is not None and re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,3}){0,2}", image.version):
        version = image.version
    return image, {
        "id": profile["IMAGE"],
        "admitted": image is not None,
        "pg_version": version,
        "oci_label_count": None if image is None else len(image.labels),
    }


def project(files, dirs, reported_exit, d):
    cases, entry, profile, reader = d["cases"], d["entry"], d["profile"], d["reader"]
    for name in ("attempt.json", "invoked.json", "result.json"):
        need(name in files, "EXPORT_ARTIFACT")
    state = canonical(files["attempt.json"], "EXPORT_STATE")
    need(
        type(state) is dict
        and type(state.get("task")) is str
        and re.fullmatch(r"[0-9a-f]{32}", state["task"]) is not None,
        "EXPORT_STATE",
    )
    task = state["task"]
    need(
        state.get("phase") in ("FINISHED", "ABORTED") and state.get("invoked") is True,
        "EXPORT_TERMINAL",
    )
    expected = guarded("EXPORT_STATE", expected_state, task, state["phase"], d)
    need(encoded(expected) == files["attempt.json"], "EXPORT_STATE")
    need(
        files["invoked.json"]
        == encoded(
            {
                "kind": "MASKGW_PG16_SHELL_INVOKED_V1",
                "task": task,
                "host_sha256": entry["HOST_SHA"],
                "entry_sha256": ENTRY_SHA,
            }
        ),
        "EXPORT_STATE",
    )
    result = canonical(files["result.json"], "EXPORT_STATE")
    success = terminal(result, state["phase"], reported_exit)
    a_entered = result["desktop_state"] != "UNTOUCHED_PRE_A"
    commands = ledger(result, cases)
    replies = captures(files, commands, cases)
    desktop = desktop_projection(files, result, a_entered)
    global_replies(replies, success, a_entered, result["desktop_state"])
    cycle = journal_projection(files, result, d, success, a_entered)
    image, image_out = image_projection(replies, profile, success)
    records, intents = records_projection(files, cases, task, image, d, success)
    monitors, started, watch_meta = watchdog_projection(files, dirs, result, cases, success)
    metadata_sequence(files, success)
    raw = files.get("cases.json")
    rows = [] if raw is None else canonical(raw, "EXPORT_CASE")
    need(type(rows) is list, "EXPORT_CASE")
    complete, recorded = len(rows), len(records)
    need(
        complete <= recorded <= complete + 1
        and recorded <= started <= complete + 1
        and (a_entered or (started <= 1 and recorded == 0))
        and (not success or complete == len(cases)),
        "EXPORT_CASE",
    )
    by_case = {case: [] for case in cases}
    for reply in replies:
        kind = label_kind(reply["label"], cases)
        if kind[0] == "case":
            by_case[kind[2]].append((reply["position"], kind[1], reply))
    for index, case in enumerate(cases):
        if index >= recorded:
            permitted = index == recorded and not success
            need(
                all(prefix == "volumes-before-" and permitted for _, prefix, _ in by_case[case]),
                "EXPORT_CASE",
            )
    plans = {case: value(encoded(asdict(d["delivery"]["delivery_for"](case)[1]))) for case in cases}
    ready = len(reader["ready_line"](task))
    infos, projected, blocks, after_positions = {}, [], [], []
    positive = negative = 0
    for index, record in enumerate(records):
        case, intent = cases[index], intents[records[index]["case"]]
        items = by_case[case]
        vector = reader["vector"](reader["Case"](case))
        expected_code = 0 if vector.fault is None else 42
        if index < complete:
            row = rows[index]
            need(
                type(row) is dict
                and set(row) == CASE_ROW_KEYS
                and row["case"] == case
                and "create_not_invoked" not in record,
                "EXPORT_CASE",
            )
            first, after, killed = complete_block(items, replies, record["cid"])
            blocks.append((first, after))
            after_positions.append(after)
            case_infos = inspected(case, items, record, intent, d, task)
            infos[record["cid"]] = case_infos
            created, result_reply = items[2], items[3]
            for position in (created[0], result_reply[0]):
                guarded(
                    "EXPORT_INSPECT",
                    profile["validate_container"],
                    case_infos[position],
                    intent,
                    record["cid"],
                )
            need(
                row["removed"] is True
                and row["case_volume_restored"] is True
                and integer(row["returncode"], 0, 255)
                and row["returncode"] == expected_code
                and integer(row["stdout_bytes"], 1, 1 << 20)
                and integer(row["report_bytes"], 1, 1 << 20),
                "EXPORT_REPORT",
            )
            facts, output = verified_report(files, index, case, row["returncode"], task, d)
            need(facts is not None, "EXPORT_REPORT")
            report = report_projection(facts, vector)
            need(
                row["report_ok"] is report["ok"]
                and row["report_category"] == report["category"]
                and row["stdout_bytes"] == ready + len(output)
                and row["report_bytes"] == len(output),
                "EXPORT_REPORT",
            )
            post = state_projection(case_infos[result_reply[0]])
            need(
                row["inspect_label"] == "inspect-result-" + case
                and same(row["inspect_cli_index"], result_reply[2]["index"])
                and same(row["inspect_artifact"], result_reply[2]["artifact"])
                and post
                == {
                    "Running": False,
                    "Pid": 0,
                    "OOMKilled": False,
                    "Dead": False,
                    "ExitCode": row["returncode"],
                }
                and same(row["inspect_exit_code"], post["ExitCode"])
                and row["oom_killed"] is False
                and row["dead"] is False,
                "EXPORT_INSPECT",
            )
            need(same(row["delivery"], plans[case]), "EXPORT_CASE")
            owner = owner_projection(row["owner"], row, record["cid"])
            need(same(row["monitor"], watch_meta[case]), "EXPORT_WATCHDOG")
            if report["ok"]:
                positive += 1
            else:
                negative += 1
            projected.append(
                {
                    "index": index + 1,
                    "case": case,
                    "status": "COMPLETE",
                    "cid": record["cid"],
                    "expected": "POSITIVE" if vector.fault is None else "NEGATIVE",
                    "delivery": plans[case],
                    "returncode": row["returncode"],
                    "stdout_bytes": row["stdout_bytes"],
                    "report_bytes": row["report_bytes"],
                    "report": report,
                    "inspect_result": {"cli_index": result_reply[2]["index"], "state": post},
                    "profile_accepted": True,
                    "kill_used": killed,
                    "cli_indexes": [reply["index"] for _, _, reply in items],
                    "volumes_final_cli_index": replies[after]["index"],
                    "owner": owner,
                    "monitor": "JOINED",
                }
            )
        else:
            need(not success, "EXPORT_CASE")
            incomplete_items(items, record)
            if record["cid"] is not None:
                infos[record["cid"]] = inspected(case, items, record, intent, d, task)
            facts, output = verified_report(files, index, case, expected_code, task, d)
            projected.append(
                {
                    "index": index + 1,
                    "case": case,
                    "status": "INCOMPLETE",
                    "cid": record["cid"],
                    "create_invoked": record["create_invoked"],
                    "removed": record["removed"],
                    "report": None if facts is None else report_projection(facts, vector),
                    "output_withheld": output is not None,
                }
            )
    need(
        all(previous[1] < current[0] for previous, current in zip(blocks, blocks[1:])),
        "EXPORT_CASE",
    )
    need(not success or (positive == 4 and negative == 19), "EXPORT_REPORT")
    volumes, restored = volume_projection(files, replies, records, infos, result, d, success)
    need(all(position in restored for position in after_positions), "EXPORT_VOLUME")
    return {
        "kind": "MASKGW_PG16_SHELL_READER_SUMMARY_V1",
        "task": task,
        "entry_sha256": ENTRY_SHA,
        "host_sha256": entry["HOST_SHA"],
        "reported_exit": reported_exit,
        "phase": state["phase"],
        "outcome": result["outcome"],
        "a_entered": a_entered,
        "resources": {key: result.get(key) for key in RESOURCE_KEYS},
        "desktop": desktop,
        "cycle": cycle,
        "commands": commands,
        "image": image_out,
        "counts": {
            "cases_total": len(cases),
            "records": recorded,
            "complete": complete,
            "monitors_started": started,
            "positive": positive,
            "negative": negative,
        },
        "cases": projected,
        "watchdogs": monitors,
        "volumes": volumes,
        "diagnostics": diagnostics(result, d, success),
    }


def write_new(path, raw):
    with path.open("xb") as stream:
        written = stream.write(raw)
        need(written == len(raw), "EXPORT_IO")
        stream.flush()
        os.fsync(stream.fileno())


def _export(root, destination, reported_exit):
    need(type(reported_exit) is int and reported_exit in (0, 1), "EXPORT_TERMINAL")
    need(
        type(root) is type(TEMP_ROOT)
        and root.parent == TEMP_ROOT
        and re.fullmatch(ROOT_PATTERN, root.name) is not None,
        "EXPORT_ROOT",
    )
    directory_chain(root, "EXPORT_ROOT")
    d = guarded("EXPORT_SOURCE", definitions)
    files, dirs = snapshot(root, d["cases"])
    summary = project(files, dirs, reported_exit, d)
    task = summary["task"]
    need(
        type(destination) is type(OUTPUT_PARENT)
        and destination.parent == OUTPUT_PARENT
        and destination.name == DESTINATION_PREFIX + task[:12],
        "EXPORT_DESTINATION",
    )
    directory_chain(OUTPUT_PARENT, "EXPORT_DESTINATION")
    need(absent(destination), "EXPORT_DESTINATION")
    summary_raw = encoded(summary)
    manifest = {
        "kind": "MASKGW_PG16_SHELL_READER_TRANSPORT_V1",
        "task": task,
        "root_name": root.name,
        "reported_exit": reported_exit,
        "entry_sha256": ENTRY_SHA,
        "source_count": len(files),
        "source_bytes": sum(map(len, files.values())),
        "source_directories": list(dirs),
        "published_source_count": 0,
        "withheld_source_count": len(files),
        "derived_artifacts": [
            {"name": "summary.json", "bytes": len(summary_raw), "sha256": sha(summary_raw)}
        ],
        "files": [
            {
                "name": name,
                "bytes": len(raw),
                "sha256": sha(raw),
                "published": False,
                "reason": "LOCAL_ONLY" if name.startswith("local-") else "PROJECTION_ONLY",
            }
            for name, raw in sorted(files.items())
        ],
        "source_unchanged": True,
    }
    manifest_raw = encoded(manifest)
    need(
        len(summary_raw) <= MAX_OUTPUT_BYTES and len(manifest_raw) <= MAX_OUTPUT_BYTES,
        "EXPORT_SIZE",
    )
    # Recheck every captured public source pin, both directory chains and the
    # complete source tree before the first write.
    guarded("EXPORT_SOURCE", recheck_sources, d)
    directory_chain(root, "EXPORT_ROOT")
    directory_chain(OUTPUT_PARENT, "EXPORT_DESTINATION")
    again, again_dirs = snapshot(root, d["cases"])
    need(again == files and again_dirs == dirs, "EXPORT_CHANGED")
    need(absent(destination), "EXPORT_DESTINATION")
    destination.mkdir(exist_ok=False)
    pending = destination / "transport.json.next"
    write_new(destination / "summary.json", summary_raw)
    write_new(pending, manifest_raw)
    need(
        {path.name for path in destination.iterdir()} == {"summary.json", "transport.json.next"},
        "EXPORT_CHANGED",
    )
    need(
        regular(destination / "summary.json", MAX_OUTPUT_BYTES) == summary_raw
        and regular(pending, MAX_OUTPUT_BYTES) == manifest_raw,
        "EXPORT_CHANGED",
    )
    directory_chain(destination, "EXPORT_DESTINATION")
    # Completion marker: every fallible check is above. The rename is the last
    # operation; after it nothing can fail, so a visible transport.json always
    # means a complete, read-back export.
    os.rename(pending, destination / "transport.json")
    return manifest


def export(root, destination, reported_exit):
    problem = None
    try:
        return _export(root, destination, reported_exit)
    except ExportError as error:
        problem = error.args[0]
    except OSError:
        problem = "EXPORT_IO"
    except Exception:
        problem = "EXPORT_INTERNAL"
    # Deliberately outside except: no original message, cause or context escapes.
    raise ExportError(problem) from None
