"""Public PG16 shell-reader attempt preparation. Import defines only.

Pure FRESH state, an explicit argv proposal and one bounded materialization of
a new root holding only attempt.json. Never spawns the runner, Docker, a clock
sampler or any process. The launcher bytes are read only inside materialize;
admission<=3s is NOT measured here.
"""

import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess  # list2cmdline only: measures the command line, never spawns

REPO = Path(__file__).resolve().parents[2]
EXPORTER_RELATIVE = "docs/poc/pg16_shell_export.py"
EXPORTER_SHA = "ed491c013ed1a731dc47a6fdeaee412db71a902993fd6fb2b257e30e3afebba3"
EXPORTER_LIMIT = 262144
ENTRY_RELATIVE = "docs/poc/pg16_shell_run.py"
ENTRY_SHA = "afaffad00ac2a2e9cd1666bdce5e18e6173240b4719592931b9cbda19c90c657"
PYTHON = REPO / ".venv/Scripts/python.exe"
PYTHON_SHA = "bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82"
PYTHON_LIMIT = 1048576
KIND = "maskgw-pg16-shell-reader-v1"
ROOT_PATTERN = r"maskgw-pg16-shell-reader-v1-[0-9a-f]{32}"
STATE_LIMIT = 32768
MAX_COMMAND_CHARS = 2048
CASE_COUNT = 23
# Exactly the key set literal of the entry admit (afaffad0): 16 keys. Tests
# re-derive it from the entry source AST instead of trusting this copy.
STATE_KEYS = frozenset(
    (
        "kind",
        "task",
        "phase",
        "invoked",
        "program_sha256",
        "v2_sha256",
        "parent_sha256",
        "host_sha256",
        "entry_sha256",
        "pins",
        "pg_pins",
        "transitive_pins",
        "stdlib_pins",
        "image",
        "create_measurements",
        "delivery_plan",
    )
)
CODES = frozenset(
    (
        "PREPARE_REFUSED",
        "PREPARE_SOURCE",
        "PREPARE_TASK",
        "PREPARE_STATE",
        "PREPARE_ROOT",
        "PREPARE_LAUNCHER",
        "PREPARE_COMMAND",
        "PREPARE_SIZE",
        "PREPARE_CHANGED",
        "PREPARE_IO",
        "PREPARE_INTERNAL",
    )
)


class PrepareError(Exception):
    def __init__(self, code):
        super().__init__(code if type(code) is str and code in CODES else "PREPARE_INTERNAL")


def need(value, code="PREPARE_REFUSED"):
    if not value:
        raise PrepareError(code) from None


def guarded(code, function, *args):
    """Pinned helpers raise their own classes; only a closed code leaves here."""
    failed, result = False, None
    try:
        result = function(*args)
    except Exception:
        failed = True
    need(not failed, code)
    return result


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def reparse(info):
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


def regular(path, maximum, code):
    """Bounded read: never allocates more than maximum+1 bytes, even after growth."""
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and not reparse(info), code)
    need(info.st_size <= maximum, "PREPARE_SIZE")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    need(type(raw) is bytes and len(raw) <= maximum, "PREPARE_SIZE")
    need(len(raw) == info.st_size, "PREPARE_CHANGED")
    return raw


def real_directories(path, code):
    """The directory and every ancestor: real directories, no link or reparse point."""
    for item in (path, *path.parents):
        info = item.lstat()
        need(stat.S_ISDIR(info.st_mode) and not reparse(info), code)


def absent(path):
    """True only if nothing, not even a dangling link, occupies the name."""
    missing = False
    try:
        path.lstat()
    except FileNotFoundError:
        missing = True
    return missing


def load():
    """Accepted exporter by SHA, then its pinned definitions of entry afaffad0."""
    path = REPO / EXPORTER_RELATIVE
    raw = guarded("PREPARE_SOURCE", regular, path, EXPORTER_LIMIT, "PREPARE_SOURCE")
    need(sha(raw) == EXPORTER_SHA, "PREPARE_SOURCE")
    exporter = {"__name__": "_pg16_shell_prepare_exporter", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), exporter)
    need(
        exporter["ENTRY_SHA"] == ENTRY_SHA and exporter["ENTRY_RELATIVE"] == ENTRY_RELATIVE,
        "PREPARE_SOURCE",
    )
    return exporter, guarded("PREPARE_SOURCE", exporter["definitions"])


def fresh_state(task, exporter, d):
    need(type(task) is str and re.fullmatch(r"[0-9a-f]{32}", task) is not None, "PREPARE_TASK")
    state = guarded("PREPARE_STATE", exporter["expected_state"], task, "FRESH", d)
    # expected_state describes a terminal export (invoked=True); admit needs FRESH.
    state["invoked"] = False
    need(
        type(state) is dict
        and set(state) == STATE_KEYS
        and state["kind"] == KIND
        and state["task"] == task
        and state["phase"] == "FRESH"
        and state["invoked"] is False
        and state["entry_sha256"] == ENTRY_SHA
        and len(d["cases"]) == CASE_COUNT
        and len(state["create_measurements"]) == CASE_COUNT
        and len(state["delivery_plan"]) == CASE_COUNT,
        "PREPARE_STATE",
    )
    raw = guarded("PREPARE_STATE", d["base"]["json_bytes"], state)
    need(
        type(raw) is bytes and raw.isascii() and raw == exporter["encoded"](state),
        "PREPARE_STATE",
    )
    need(len(raw) <= min(STATE_LIMIT, d["entry"]["STATE_LIMIT"]), "PREPARE_SIZE")
    return state, raw


def check_root(root, d):
    """Exactly the root form the entry admit accepts, new, under real directories."""
    temp = d["base"]["HOME"] / "AppData/Local/Temp"
    need(
        type(root) is type(temp)
        and root.is_absolute()
        and root.parent == temp
        and re.fullmatch(ROOT_PATTERN, root.name) is not None,
        "PREPARE_ROOT",
    )
    # A missing, linked or reparse ancestor is a root refusal, not an IO failure.
    guarded("PREPARE_ROOT", real_directories, temp, "PREPARE_ROOT")
    need(guarded("PREPARE_ROOT", absent, root), "PREPARE_ROOT")


def argv_for(root):
    entry = REPO / ENTRY_RELATIVE
    need(PYTHON.is_absolute() and entry.is_absolute(), "PREPARE_COMMAND")
    argv = (str(PYTHON), "-I", "-B", str(entry), str(root))
    need(len(subprocess.list2cmdline(argv)) <= MAX_COMMAND_CHARS, "PREPARE_COMMAND")
    return argv


def launcher_pin():
    raw = guarded("PREPARE_LAUNCHER", regular, PYTHON, PYTHON_LIMIT, "PREPARE_LAUNCHER")
    need(sha(raw) == PYTHON_SHA, "PREPARE_LAUNCHER")


def recheck(exporter, d):
    path = REPO / EXPORTER_RELATIVE
    raw = guarded("PREPARE_SOURCE", regular, path, EXPORTER_LIMIT, "PREPARE_SOURCE")
    need(sha(raw) == EXPORTER_SHA, "PREPARE_SOURCE")
    guarded("PREPARE_SOURCE", exporter["recheck_sources"], d)


def descriptor(root, task, argv, raw, d, materialized):
    return {
        "kind": "MASKGW_PG16_SHELL_PREPARE_V1",
        "task": task,
        "root": str(root),
        "root_name": root.name,
        "argv": list(argv),
        "command_chars": len(subprocess.list2cmdline(argv)),
        "command_limit": MAX_COMMAND_CHARS,
        "state_bytes": len(raw),
        "state_sha256": sha(raw),
        "state_limit": STATE_LIMIT,
        "state_keys": len(STATE_KEYS),
        "case_count": len(d["cases"]),
        "entry_sha256": ENTRY_SHA,
        "exporter_sha256": EXPORTER_SHA,
        "host_sha256": d["entry"]["HOST_SHA"],
        "launcher_sha256": PYTHON_SHA,
        "launcher_verified": materialized,
        "materialized": materialized,
        "admission_3s": "NOT_MEASURED",
    }


def _state(task):
    exporter, d = load()
    return fresh_state(task, exporter, d)[0]


def _proposal(root, task):
    exporter, d = load()
    _, raw = fresh_state(task, exporter, d)
    check_root(root, d)
    return descriptor(root, task, argv_for(root), raw, d, False)


def _materialize(root, task):
    exporter, d = load()
    _, raw = fresh_state(task, exporter, d)
    check_root(root, d)
    argv = argv_for(root)
    launcher_pin()
    recheck(exporter, d)
    result = descriptor(root, task, argv, raw, d, True)
    check_root(root, d)  # again immediately before the only mkdir
    root.mkdir(exist_ok=False)
    # From here the proposal is consumed: any failure leaves this owned partial
    # directory and raises. It is never cleaned, overwritten, retried or reused.
    path = root / "attempt.json"
    with path.open("xb") as stream:
        written = stream.write(raw)
        need(written == len(raw), "PREPARE_IO")
        stream.flush()
        os.fsync(stream.fileno())
    need([item.name for item in root.iterdir()] == ["attempt.json"], "PREPARE_CHANGED")
    real_directories(root, "PREPARE_ROOT")
    need(regular(path, STATE_LIMIT, "PREPARE_CHANGED") == raw, "PREPARE_CHANGED")
    return result


def closed(function, *args):
    problem, done, result = None, False, None
    try:
        result = function(*args)
        done = True
    except PrepareError as error:
        problem = error.args[0]
    except OSError:
        problem = "PREPARE_IO"
    except Exception:
        problem = "PREPARE_INTERNAL"
    if done:
        return result
    # Deliberately outside except: no original message, cause or context escapes.
    raise PrepareError(problem) from None


def state_for(task):
    """Exact FRESH admit state for task; no write, no launcher read."""
    return closed(_state, task)


def proposal(root, task):
    """Exact sizes/hashes/argv for a new root; no write, no launcher read, no spawn."""
    return closed(_proposal, root, task)


def materialize(root, task):
    """One-shot: new root with only attempt.json. Never runs the entry."""
    return closed(_materialize, root, task)
