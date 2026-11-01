"""Private caller for the frozen PG16 admission probe. Import defines only.

No __main__, no CLI and no consumer in this increment: run(root, task) stays
unreleased until the separate benign native control and its procedure pass.
The process tree is owned only through the accepted Win32 backend (10c9058f).
An owner whose termination or close is not proven is kept in a module-private
registry for the life of this process; a new run is refused while one exists.
Budgets are decision budgets checked between OS calls, not wall-time bounds.
Accepted evidence never means that the original entry admission passed.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess  # list2cmdline only: measures the command line, never spawns
import sys
import time

REPO = Path(__file__).resolve().parents[2]
HOME = Path("C:/Users/w.filho")
EVIDENCE = REPO / "docs/poc/evidence"
PYTHON = REPO / ".venv/Scripts/python.exe"
PYTHON_SHA = "bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82"
SOURCES = {
    "probe": (
        "docs/poc/pg16_shell_admission_probe.py",
        "738ee1e39466bced17d65671222f7de71661122a34616fde4c98446cb4eee0fe",
    ),
    "preparer": (
        "docs/poc/pg16_shell_prepare.py",
        "8d0bf39e07f058f5b8d53dba279daee0839f2ff50903358a4c59d03a8f695971",
    ),
    "entry": (
        "docs/poc/pg16_shell_run.py",
        "afaffad00ac2a2e9cd1666bdce5e18e6173240b4719592931b9cbda19c90c657",
    ),
    "backend": (
        "docs/poc/pg16_shell_admission_win32.py",
        "10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726",
    ),
}
SOURCE_LIMIT = 65536
LAUNCHER_LIMIT = 1048576
STATE_LIMIT = 32768
ARTIFACT_LIMIT = 4096
COMMAND_LIMIT = 2048
RETAIN_BYTES = 1024
DEADLINE_SECONDS = 60.0
CLEANUP_SECONDS = 10.0
WAIT_MS = 50
PAUSE_SECONDS = 0.05
MAX_TURNS = 1200  # at least one 50 ms wait or pause per turn
CLEANUP_TURNS = 200
LIMIT_SECONDS = 3.0
ROOT_PATTERN = re.compile(r"maskgw-pg16-shell-reader-v1-([0-9a-f]{32})")
TASK_PATTERN = re.compile(r"[0-9a-f]{32}")
CLAIM_PREFIX = "maskgw-pg16-shell-admission-claim-v1-"
RESULT_PREFIX = "maskgw-pg16-shell-admission-result-v1-"
PRIVATE_PREFIX = "maskgw-pg16-shell-admission-caller-v1-"
PUBLIC_PREFIX = "pg16-shell-admission-"
MARKER = "admission-probe.json"
PROBE_RUNTIME = "win32-3.11.3-isolated-nobytecode-optimize0"
ENVIRONMENT_NAMES = (
    "SystemRoot",
    "WINDIR",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
    "HOMEDRIVE",
    "HOMEPATH",
    "SystemDrive",
)
STAGES = ("ADMIT", "HOST", "CONTEXT", "FINAL_PINS")
STAGE_FIELDS = ("stage_admit_ns", "stage_host_ns", "stage_context_ns", "stage_final_pins_ns")
PROBE_OUTCOMES = ("WITHIN_3S", "OVER_3S", "CLOCK_INVALID", "STAGE_FAILED")
IDENTITY_KEYS = (
    "task",
    "nonce",
    "root_name",
    "probe_sha256",
    "preparer_sha256",
    "entry_sha256",
    "state_sha256",
    "state_bytes",
)
RESULT_KEYS = frozenset(
    (
        "kind",
        *IDENTITY_KEYS,
        "outcome",
        "stage",
        "category",
        "clock_valid",
        "elapsed_seconds",
        "stages_ns",
        "limit_seconds",
        "runtime",
        "claim_sha256",
    )
)
NOT_ACCEPTED = frozenset(
    (
        "DEADLINE",
        "LAUNCH_FAILED",
        "TREE_UNPROVEN",
        "OUTPUT_OVERFLOW",
        "OUTPUT_MISMATCH",
        "RESULT_MISSING",
        "RESULT_MISMATCH",
        "INTERRUPTED",
        "CALLER_CLOCK",
    )
)
CODES = frozenset(
    (
        "HOST_RETAINED",
        "HOST_RUNTIME",
        "HOST_TASK",
        "HOST_ROOT",
        "HOST_STATE",
        "HOST_SOURCE",
        "HOST_CONSUMED",
        "HOST_ENVIRONMENT",
        "HOST_COMMAND",
        "HOST_LAUNCHER",
        "HOST_PERSISTENCE",
        "HOST_HELD",
        "HOST_INTERNAL",
    )
)
# Owners whose termination/close is not proven. Kept for the life of this
# process; never persisted, never exposed through a recovery method.
_LIVE = []
_HELD_REASONS = []  # closed labels only, in memory


class HostError(Exception):
    def __init__(self, code):
        super().__init__(code if type(code) is str and code in CODES else "HOST_INTERNAL")


def need(value, code):
    if not value:
        raise HostError(code) from None


def guarded(code, function, *args):
    failed, result = False, None
    try:
        result = function(*args)
    except Exception:
        failed = True
    need(not failed, code)
    return result


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return text.encode("ascii")


def _reject(_value):
    raise ValueError()


def strict(raw):
    """Strict JSON object: ASCII, no duplicate keys, no NaN/Infinity, canonical."""

    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError()
            result[key] = item
        return result

    value, failed = None, False
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=pairs, parse_constant=_reject)
    except (ValueError, UnicodeError, RecursionError):
        failed = True
    if failed or type(value) is not dict:
        return None
    canonical = None
    try:
        canonical = encoded(value)  # rejects overflowed floats such as 1e400
    except (ValueError, TypeError, RecursionError):
        return None
    return value if canonical == raw else None


def reparse(info):
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


def regular(path, maximum):
    """Bounded read: never allocates more than maximum+1 bytes."""
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and not reparse(info), "HOST_SOURCE")
    need(info.st_size <= maximum, "HOST_SOURCE")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    need(type(raw) is bytes and len(raw) == info.st_size <= maximum, "HOST_SOURCE")
    return raw


def optional(path, maximum):
    """Bytes of a regular file, or None when absent/unreadable/oversized."""
    raw, failed = None, False
    try:
        raw = regular(path, maximum)
    except Exception:
        failed = True
    return None if failed else raw


def absent(path):
    missing = False
    try:
        path.lstat()
    except FileNotFoundError:
        missing = True
    return missing


def real_directories(path):
    for item in (path, *path.parents):
        info = item.lstat()
        need(stat.S_ISDIR(info.st_mode) and not reparse(info), "HOST_ROOT")


def listing(path):
    names = []
    for index, item in enumerate(path.iterdir()):
        need(index < 8, "HOST_ROOT")
        names.append(item.name)
    return sorted(names)


def write_new(path, raw):
    """xb, exact count, flush, fsync, bounded read-back. Never overwrites."""
    done = False
    try:
        with path.open("xb") as stream:
            written = stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        done = written == len(raw)
    except Exception:
        done = False
    need(done and optional(path, len(raw)) == raw, "HOST_PERSISTENCE")


# -- test seams: internal module globals only, never parameters ---------------


def _environ():
    return os.environ


def _monotonic():
    return time.monotonic()


def _sleep(seconds):
    time.sleep(seconds)


def _launcher_pin():
    raw = regular(PYTHON, LAUNCHER_LIMIT)
    need(sha(raw) == PYTHON_SHA, "HOST_LAUNCHER")


def _load_backend(raw):
    path = REPO / SOURCES["backend"][0]
    namespace = {"__name__": "_pg16_admission_host_backend", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace


def _expected_state(task):
    """Canonical FRESH state bytes from the accepted preparer (pure, no launcher read)."""
    relative, digest = SOURCES["preparer"]
    path = REPO / relative
    raw = regular(path, SOURCE_LIMIT)
    need(sha(raw) == digest, "HOST_SOURCE")
    prep = {"__name__": "_pg16_admission_host_preparer", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), prep)
    return encoded(prep["state_for"](task)) + b"\n", frozenset(prep["STATE_KEYS"])


# -----------------------------------------------------------------------------


def _runtime():
    flags = sys.flags
    return (
        sys.platform == "win32"
        and tuple(sys.version_info[:3]) == (3, 11, 3)
        and sys.maxsize == (1 << 63) - 1
        and flags.isolated == 1
        and flags.dont_write_bytecode == 1
        and flags.optimize == 0
    )


def _sources():
    digests = {}
    for key, (relative, digest) in SOURCES.items():
        raw = guarded("HOST_SOURCE", regular, REPO / relative, SOURCE_LIMIT)
        need(sha(raw) == digest, "HOST_SOURCE")
        digests[key] = raw
    own = guarded("HOST_SOURCE", regular, Path(__file__), SOURCE_LIMIT)
    # Self-hash is metadata only; the caller is pinned by the external command.
    return digests, sha(own)


def _environment():
    environ = _environ()
    pairs = []
    for name in ENVIRONMENT_NAMES:
        value = environ.get(name)
        need(
            type(value) is str and 0 < len(value) <= 4096 and "\0" not in value,
            "HOST_ENVIRONMENT",
        )
        pairs.append((name, value))
    return tuple(pairs)


class _Clock:
    """Typed, finite, nondecreasing monotonic readings; broken stays broken."""

    def __init__(self):
        self.last, self.broken = None, False

    def now(self):
        if self.broken:
            return None
        value, failed = None, False
        try:
            value = _monotonic()
        except Exception:
            failed = True
        if (
            failed
            or type(value) is not float
            or not math.isfinite(value)
            or (self.last is not None and value < self.last)
        ):
            self.broken = True
            return None
        self.last = value
        return value


def _attempt(error_type, function, *args):
    """(code, value): backend Win32Error code, INTERNAL for anything else."""
    code, value = None, None
    try:
        value = function(*args)
    except Exception as error:
        code = "INTERNAL"
        if type(error) is error_type:
            arguments = BaseException.args.__get__(error)
            if len(arguments) == 1 and type(arguments[0]) is str:
                code = arguments[0]
    return code, value


def _new_facts():
    return {
        "reason": None,
        "held": None,
        "terminated": False,
        "overflow": False,
        "signaled": False,
        "eof": False,
        "exit_code": None,
        "total_processes": None,
        "turns": 0,
        "retained": bytearray(),
    }


def _supervise(owner, error_type, clock, start, facts):
    """Single thread. Mutates the caller-held facts in place, so a control
    interruption at any point still leaves partial facts and bytes reachable.
    facts["held"] set means unproven resources."""
    cleanup_since, cleanup_turns = None, 0

    def call(function, *args):
        code, value = _attempt(error_type, function, *args)
        if code == "WIN32_TREE":
            return "TREE", None
        return ("HELD", None) if code is not None else (None, value)

    while True:
        facts["turns"] += 1
        now = clock.now()
        if facts["reason"] is None:
            if now is None:
                facts["reason"] = "CALLER_CLOCK"
            elif now - start >= DEADLINE_SECONDS or facts["turns"] > MAX_TURNS:
                facts["reason"] = "DEADLINE"
        if facts["reason"] is not None and not facts["terminated"]:
            status, _value = call(owner.terminate)
            if status:
                facts["held"] = "TERMINATE"
                return facts
            facts["terminated"] = True
            cleanup_since, cleanup_turns = now, 0
        if facts["terminated"]:
            cleanup_turns += 1
            expired = cleanup_turns > CLEANUP_TURNS or (
                now is not None
                and cleanup_since is not None
                and now - cleanup_since >= CLEANUP_SECONDS
            )
            if expired:
                facts["held"] = "CLEANUP"
                return facts
        status, chunk = call(owner.read)
        if status or type(chunk) is not bytes or len(chunk) > 4096:
            facts["held"] = "READ"
            return facts
        if chunk:
            room = RETAIN_BYTES - len(facts["retained"])
            if len(chunk) > room:
                facts["retained"].extend(chunk[: max(room, 0)])
                facts["overflow"] = True
                if facts["reason"] is None:
                    facts["reason"] = "OUTPUT_OVERFLOW"
                # No continue: this drain turn still waits or pauses below;
                # terminate happens at the top of the next turn.
            else:
                facts["retained"].extend(chunk)
        if not facts["signaled"]:
            status, value = call(owner.wait, WAIT_MS)
            if status or type(value) is not bool:
                facts["held"] = "WAIT"
                return facts
            facts["signaled"] = value
        else:
            _sleep(PAUSE_SECONDS)  # no busy loop on an already signaled launcher
        facts["eof"] = getattr(owner, "eof", False) is True
        if not (facts["signaled"] and facts["eof"]):
            continue
        status, counts = call(owner.accounting)
        if status == "TREE":
            facts["reason"] = facts["reason"] or "TREE_UNPROVEN"
            continue
        if status:
            facts["held"] = "ACCOUNTING"
            return facts
        if counts[1] != 0:
            continue
        status, pids = call(owner.members)
        if status == "TREE":
            facts["reason"] = facts["reason"] or "TREE_UNPROVEN"
            continue
        if status:
            facts["held"] = "MEMBERS"
            return facts
        if pids != ():
            continue
        status, code = call(owner.exit_code)
        if status or type(code) is not int:
            facts["held"] = "EXIT"
            return facts
        facts["exit_code"], facts["total_processes"] = code, counts[0]
        if counts[0] not in (1, 2) and facts["reason"] is None:
            facts["reason"] = "TREE_UNPROVEN"
        later = clock.now()
        if facts["reason"] is None:
            if later is None:
                facts["reason"] = "CALLER_CLOCK"
            elif later - start >= DEADLINE_SECONDS:
                facts["reason"] = "DEADLINE"  # a late completion never wins
        return facts


def _classification(result):
    """Relations of the frozen probe classify(); never trusts the label alone."""
    outcome, stage, category = result["outcome"], result["stage"], result["category"]
    valid, elapsed, deltas = result["clock_valid"], result["elapsed_seconds"], result["stages_ns"]
    if outcome not in PROBE_OUTCOMES or type(valid) is not bool:
        return False
    if valid:
        if not (type(elapsed) is float and math.isfinite(elapsed) and elapsed >= 0):
            return False
        if type(deltas) is not list or len(deltas) != len(STAGES):
            return False
        filled = [item for item in deltas if item is not None]
        if not all(type(item) is int and item >= 0 for item in filled):
            return False
        if deltas[: len(filled)] != filled:
            return False  # nulls only as a trailing suffix
    elif elapsed is not None or deltas is not None:
        return False
    if outcome == "STAGE_FAILED":
        if stage not in STAGES or category != "STAGE_EXCEPTION":
            return False
        return not valid or len(filled) == STAGES.index(stage) + 1
    if stage is not None:
        return False
    if outcome == "CLOCK_INVALID":
        return category == "CLOCK_INVALID" and not valid
    if category is not None or not valid or len(filled) != len(STAGES):
        return False
    return (outcome == "WITHIN_3S") == (0 <= elapsed <= LIMIT_SECONDS)


def _stdout(raw):
    """Exactly one canonical probe CLI object, LF or CRLF terminated."""
    if raw.endswith(b"\r\n"):
        body = raw[:-2]
    elif raw.endswith(b"\n"):
        body = raw[:-1]
    else:
        return None
    if b"\n" in body or b"\r" in body:
        return None
    value = strict(body)
    if value is None or set(value) != {"kind", "outcome", "category"}:
        return None
    if value["kind"] != "MASKGW_PG16_SHELL_ADMISSION_CLI_V1":
        return None
    return value


def _project(facts, context):
    """Outcome, category and validated probe facts; artifacts already private."""
    probe = None
    if facts["reason"] is not None:
        return "NOT_ACCEPTED", facts["reason"], probe
    cli = _stdout(bytes(facts["retained"]))
    if cli is None:
        return "NOT_ACCEPTED", "OUTPUT_MISMATCH", probe
    exit_code = facts["exit_code"]
    if cli["outcome"] == "INTERRUPTED":
        return "NOT_ACCEPTED", "INTERRUPTED", probe
    if cli["outcome"] not in PROBE_OUTCOMES:
        return "NOT_ACCEPTED", "RESULT_MISSING", probe
    if exit_code != (0 if cli["outcome"] == "WITHIN_3S" else 1):
        return "NOT_ACCEPTED", "OUTPUT_MISMATCH", probe
    temp, nonce = context["temp"], context["nonce"]
    result_raw = optional(temp / (RESULT_PREFIX + nonce + ".json"), ARTIFACT_LIMIT)
    claim_raw = optional(temp / (CLAIM_PREFIX + nonce + ".json"), ARTIFACT_LIMIT)
    if result_raw is None or claim_raw is None:
        return "NOT_ACCEPTED", "RESULT_MISSING", probe
    # Add to, never replace, the private artifacts already bound by _run.
    context["artifacts"].update({"probe-claim": claim_raw, "probe-result": result_raw})
    if not absent(temp / (RESULT_PREFIX + nonce + ".json.next")):
        return "NOT_ACCEPTED", "RESULT_MISMATCH", probe
    root = context["root"]
    marker_raw = optional(root / MARKER, ARTIFACT_LIMIT)
    state_raw = optional(root / "attempt.json", STATE_LIMIT)
    if marker_raw is not None:
        context["artifacts"]["probe-marker"] = marker_raw
    names = guarded("HOST_ROOT", listing, root)
    identity = context["identity"]
    result = strict(result_raw[:-1]) if result_raw.endswith(b"\n") else None
    claim = strict(claim_raw[:-1]) if claim_raw.endswith(b"\n") else None
    marker = strict(marker_raw[:-1]) if marker_raw and marker_raw.endswith(b"\n") else None
    claim_sha = sha(claim_raw)
    coherent = (
        result is not None
        and claim is not None
        and marker is not None
        and names == ["admission-probe.json", "attempt.json"]
        and state_raw == context["state_raw"]
        and set(result) == RESULT_KEYS
        and result["kind"] == "MASKGW_PG16_SHELL_ADMISSION_RESULT_V1"
        and all(
            type(result[key]) is type(identity[key]) and result[key] == identity[key]
            for key in IDENTITY_KEYS
        )
        and type(result["limit_seconds"]) is float
        and result["limit_seconds"] == LIMIT_SECONDS
        and result["runtime"] == PROBE_RUNTIME
        and result["claim_sha256"] == claim_sha
        and claim == {"kind": "MASKGW_PG16_SHELL_ADMISSION_CLAIM_V1", **identity}
        and marker
        == {
            "kind": "MASKGW_PG16_SHELL_ADMISSION_MARKER_V1",
            "task": identity["task"],
            "nonce": identity["nonce"],
            "claim_sha256": claim_sha,
        }
        and _classification(result)
        and result["outcome"] == cli["outcome"]
        and result["category"] == cli["category"]
    )
    if not coherent:
        return "NOT_ACCEPTED", "RESULT_MISMATCH", probe
    return "ACCEPTED_" + result["outcome"], None, result


def _summary(outcome, category, probe, facts, context, seconds):
    deltas = probe["stages_ns"] if probe is not None and probe["stages_ns"] else [None] * 4
    summary = {
        "kind": "MASKGW_PG16_SHELL_ADMISSION_HOST_SUMMARY_V1",
        "outcome": outcome,
        "category": category,
        "entry_gate": "NOT_EVALUATED",
        "task": context["identity"]["task"],
        "nonce": context["identity"]["nonce"],
        "root_name": context["identity"]["root_name"],
        "probe_outcome": None if probe is None else probe["outcome"],
        "probe_stage": None if probe is None else probe["stage"],
        "probe_category": None if probe is None else probe["category"],
        "probe_clock_valid": None if probe is None else probe["clock_valid"],
        "probe_elapsed_seconds": None if probe is None else probe["elapsed_seconds"],
        "limit_seconds": LIMIT_SECONDS,
        "launcher_exit_code": facts["exit_code"],
        "total_processes": facts["total_processes"],
        "terminated": facts["terminated"],
        "overflow": facts["overflow"],
        "retained_stdout_bytes": len(facts["retained"]),
        "caller_seconds": seconds,
        "caller_sha256": context["caller_sha256"],
        "backend_sha256": SOURCES["backend"][1],
        "probe_sha256": SOURCES["probe"][1],
        "preparer_sha256": SOURCES["preparer"][1],
        "entry_sha256": SOURCES["entry"][1],
        "launcher_sha256": PYTHON_SHA,
        "state_sha256": context["identity"]["state_sha256"],
    }
    summary.update(zip(STAGE_FIELDS, deltas, strict=True))
    need(outcome.startswith("ACCEPTED_") or category in NOT_ACCEPTED, "HOST_INTERNAL")
    return summary


def _publish(summary, context):
    """Every byte prepared first; the final rename is the last filesystem operation."""
    summary_raw = encoded(summary) + b"\n"
    files = [
        {"name": name, "bytes": len(raw), "sha256": sha(raw)}
        for name, raw in sorted(context["artifacts"].items())
    ]
    transport = {
        "kind": "MASKGW_PG16_SHELL_ADMISSION_HOST_TRANSPORT_V1",
        "task": summary["task"],
        "nonce": summary["nonce"],
        "outcome": summary["outcome"],
        "summary": {"name": "summary.json", "bytes": len(summary_raw), "sha256": sha(summary_raw)},
        "private": files,
    }
    transport_raw = encoded(transport) + b"\n"
    public = context["public"]
    guarded("HOST_PERSISTENCE", real_directories, public.parent)
    need(guarded("HOST_PERSISTENCE", absent, public), "HOST_PERSISTENCE")
    guarded("HOST_PERSISTENCE", public.mkdir, 0o777, False, False)
    pending, final = public / "transport.json.next", public / "transport.json"
    write_new(public / "summary.json", summary_raw)
    write_new(pending, transport_raw)
    need(
        guarded("HOST_PERSISTENCE", listing, public) == ["summary.json", "transport.json.next"],
        "HOST_PERSISTENCE",
    )
    need(guarded("HOST_PERSISTENCE", absent, final), "HOST_PERSISTENCE")
    descriptor = dict(summary)
    # os.rename does not overwrite on Windows; nothing follows on success.
    guarded("HOST_PERSISTENCE", os.rename, pending, final)
    return descriptor


def _record_held(owner, label, facts, context):
    """Best-effort private HELD record and partial stdout. Each write is xb,
    never overwritten, deleted or retried; any failure, including a second
    control interruption, is absorbed here and never replaces the caller's
    original exception. Never published."""
    state = getattr(owner, "state", None)
    record = {
        "kind": "MASKGW_PG16_SHELL_ADMISSION_SUPERVISION_V1",
        "held": label,
        "owner_state": state if type(state) is str and len(state) <= 32 else None,
        "reason": facts["reason"],
        "terminated": facts["terminated"],
        "overflow": facts["overflow"],
        "signaled": facts["signaled"],
        "eof": facts["eof"],
        "exit_code": facts["exit_code"] if type(facts["exit_code"]) is int else None,
        "total_processes": facts["total_processes"],
        "turns": facts["turns"],
        "retained_stdout_bytes": len(facts["retained"]),
    }
    written = []
    for name, raw in (
        ("supervision.json", lambda: encoded(record) + b"\n"),
        ("local-stdout.bin", lambda: bytes(facts["retained"])),
    ):
        try:
            write_new(context["private"] / name, raw())
            written.append(name)
        except BaseException:
            pass
    context["held_record"] = tuple(written)


def _held(owner, label, facts, context):
    """Owner stays registered; best-effort private record; never published."""
    _HELD_REASONS.append(label)
    _record_held(owner, label, facts, context)
    raise HostError("HOST_HELD") from None


def _interrupted(owner, error_type, facts, context, label):
    """Called while handling a control interruption or unexpected failure.
    Record first (owner is already registered), then at most one guarded
    terminate only if the backend state allows it, then the private record.
    Absorbs everything so the original exception is the one that propagates."""
    _HELD_REASONS.append(label)
    try:
        if getattr(owner, "state", None) == "RUNNING":
            code, _value = _attempt(error_type, owner.terminate)
            if code is None:
                # A successful terminate call only; never proof of reaping or
                # released resources, and never a reason to release the owner.
                facts["terminated"] = True
    except BaseException:
        pass
    try:
        _record_held(owner, label, facts, context)
    except BaseException:
        pass


def _run(root, task):
    need(_runtime(), "HOST_RUNTIME")
    need(type(task) is str and TASK_PATTERN.fullmatch(task) is not None, "HOST_TASK")
    temp = HOME / "AppData/Local/Temp"
    match = ROOT_PATTERN.fullmatch(root.name) if type(root) is type(temp) else None
    need(match is not None and root.is_absolute() and root.parent == temp, "HOST_ROOT")
    nonce = match[1]
    sources, caller_sha = _sources()
    guarded("HOST_ROOT", real_directories, root)
    need(guarded("HOST_ROOT", listing, root) == ["attempt.json"], "HOST_ROOT")
    state_raw = guarded("HOST_STATE", regular, root / "attempt.json", STATE_LIMIT)
    expected, keys = guarded("HOST_STATE", _expected_state, task)
    state = strict(state_raw[:-1]) if state_raw.endswith(b"\n") else None
    need(
        state_raw == expected
        and state is not None
        and set(state) == keys
        and len(keys) == 16
        and state.get("phase") == "FRESH"
        and state.get("invoked") is False
        and state.get("task") == task,
        "HOST_STATE",
    )
    private = temp / (PRIVATE_PREFIX + nonce)
    public = EVIDENCE / (PUBLIC_PREFIX + nonce[:12])
    for path in (
        temp / (CLAIM_PREFIX + nonce + ".json"),
        temp / (RESULT_PREFIX + nonce + ".json"),
        temp / (RESULT_PREFIX + nonce + ".json.next"),
        private,
        public,
    ):
        need(guarded("HOST_CONSUMED", absent, path), "HOST_CONSUMED")
    environment = _environment()
    probe_path = REPO / SOURCES["probe"][0]
    argv = (str(PYTHON), "-I", "-B", str(probe_path), str(root), task)
    command_line = subprocess.list2cmdline(argv)
    need(len(command_line) <= COMMAND_LIMIT, "HOST_COMMAND")
    backend = guarded("HOST_SOURCE", _load_backend, sources["backend"])
    request = guarded(
        "HOST_COMMAND", backend["Request"], str(PYTHON), command_line, environment, str(REPO)
    )
    identity = {
        "task": task,
        "nonce": nonce,
        "root_name": root.name,
        "probe_sha256": SOURCES["probe"][1],
        "preparer_sha256": SOURCES["preparer"][1],
        "entry_sha256": SOURCES["entry"][1],
        "state_sha256": sha(state_raw),
        "state_bytes": len(state_raw),
    }
    invocation = {
        "kind": "MASKGW_PG16_SHELL_ADMISSION_INVOCATION_V1",
        **identity,
        "argv": list(argv),  # private only; intended canonical absolute argv
        "environment_names": list(ENVIRONMENT_NAMES),  # never values
        "caller_sha256": caller_sha,
        "backend_sha256": SOURCES["backend"][1],
        "launcher_sha256": PYTHON_SHA,
        "limits": {
            "deadline_seconds": DEADLINE_SECONDS,
            "cleanup_seconds": CLEANUP_SECONDS,
            "retain_bytes": RETAIN_BYTES,
            "active_process_limit": 2,
        },
    }
    # Durable invocation before any launch; from here the attempt is consumed.
    guarded("HOST_PERSISTENCE", private.mkdir, 0o777, False, False)
    invocation_raw = encoded(invocation) + b"\n"
    write_new(private / "invocation.json", invocation_raw)
    context = {
        "temp": temp,
        "nonce": nonce,
        "root": root,
        "private": private,
        "public": public,
        "identity": identity,
        "state_raw": state_raw,
        "caller_sha256": caller_sha,
        "artifacts": {},
    }
    guarded("HOST_LAUNCHER", _launcher_pin)
    error_type = backend["Win32Error"]
    clock = _Clock()
    start = clock.now()  # decision budget starts immediately before setup
    need(start is not None, "HOST_INTERNAL")
    owner = backend["Owner"](request)  # pure constructor
    _LIVE.append(owner)  # registered BEFORE setup; removed only after CLOSED
    facts = _new_facts()  # caller-held: partial facts survive an interruption
    try:
        _lifecycle(owner, error_type, clock, start, context, facts)
    except HostError:
        raise  # HELD paths already recorded; owner stays registered
    except Exception:
        _interrupted(owner, error_type, facts, context, "INTERNAL")
        raise
    except BaseException:
        _interrupted(owner, error_type, facts, context, "INTERRUPTED")
        raise  # the exact original control exception
    end = clock.now()
    seconds = end - start if end is not None else None
    if facts["reason"] is None:
        # Resources are already proven closed here; a final invalid or late
        # reading still forbids acceptance.
        if end is None:
            facts["reason"] = "CALLER_CLOCK"
        elif end - start >= DEADLINE_SECONDS:
            facts["reason"] = "DEADLINE"
    supervision = {
        "kind": "MASKGW_PG16_SHELL_ADMISSION_SUPERVISION_V1",
        "reason": facts["reason"],
        "terminated": facts["terminated"],
        "overflow": facts["overflow"],
        "signaled": facts["signaled"],
        "eof": facts["eof"],
        "exit_code": facts["exit_code"],
        "total_processes": facts["total_processes"],
        "turns": facts["turns"],
        "retained_stdout_bytes": len(facts["retained"]),
        "owner_state": "CLOSED",
        "caller_seconds": seconds,
    }
    supervision_raw = encoded(supervision) + b"\n"
    stdout_raw = bytes(facts["retained"])
    write_new(private / "supervision.json", supervision_raw)
    write_new(private / "local-stdout.bin", stdout_raw)
    context["artifacts"].update(
        {
            "invocation.json": invocation_raw,
            "supervision.json": supervision_raw,
            "local-stdout.bin": stdout_raw,
        }
    )
    outcome, category, probe = _project(facts, context)
    return _publish(_summary(outcome, category, probe, facts, context, seconds), context)


def _close_unstarted(owner, error_type, facts, context, reason):
    """No child exists (setup failed, launch failed or budget gone before start)."""
    _attempt(error_type, owner.close)
    if owner.state != "CLOSED":
        _held(owner, "LAUNCH", facts, context)
    _LIVE.remove(owner)
    facts["reason"] = reason


def _lifecycle(owner, error_type, clock, start, context, facts):
    """Setup/start/supervise/close on caller-held facts. Unproven resources
    raise HOST_HELD; the owner leaves the registry only after CLOSED."""
    code, _value = _attempt(error_type, owner.setup)
    if code is not None:
        if owner.state == "SETUP_FAILED":
            _close_unstarted(owner, error_type, facts, context, "LAUNCH_FAILED")
            return
        _held(owner, "LAUNCH", facts, context)
    # Decision budget checked between setup and start: no child once expired.
    now = clock.now()
    if now is None or now - start >= DEADLINE_SECONDS:
        if owner.state != "READY":
            _held(owner, "LAUNCH", facts, context)
        reason = "CALLER_CLOCK" if now is None else "DEADLINE"
        _close_unstarted(owner, error_type, facts, context, reason)
        return
    code, _value = _attempt(error_type, owner.start)
    if code is not None:
        if owner.state == "LAUNCH_FAILED":
            _close_unstarted(owner, error_type, facts, context, "LAUNCH_FAILED")
            return
        _held(owner, "LAUNCH", facts, context)
    _supervise(owner, error_type, clock, start, facts)
    if facts["held"] is not None:
        _held(owner, facts["held"], facts, context)
    _attempt(error_type, owner.close)
    if owner.state != "CLOSED":
        _held(owner, "CLOSE", facts, context)
    _LIVE.remove(owner)


def run(root, task):
    """Private caller; no CLI. Closed HostError; control interruptions propagate."""
    if _LIVE:
        raise HostError("HOST_RETAINED") from None
    problem, done, result = None, False, None
    try:
        result = _run(root, task)
        done = True
    except HostError as error:
        problem = error.args[0]
    except Exception:
        problem = "HOST_INTERNAL"
    if done:
        return result
    raise HostError(problem) from None
