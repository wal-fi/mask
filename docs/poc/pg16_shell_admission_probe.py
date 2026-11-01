"""PG16 shell-reader admission probe. Import defines only; nothing runs on import.

Measures once the exact prefix timed by the entry prepare (admit, Host,
Context, final_pins) after a prior exclusive claim, then marks the root and
publishes a bounded public result. Never calls prepare/run/drive/supervision,
a clock sampler, Docker, PG or SQL. The 3 s classification is retrospective;
it is evidence, not a replacement for the entry prepare gate.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time

REPO = Path(__file__).resolve().parents[2]
PREPARER_RELATIVE = "docs/poc/pg16_shell_prepare.py"
PREPARER_SHA = "8d0bf39e07f058f5b8d53dba279daee0839f2ff50903358a4c59d03a8f695971"
ENTRY_RELATIVE = "docs/poc/pg16_shell_run.py"
ENTRY_SHA = "afaffad00ac2a2e9cd1666bdce5e18e6173240b4719592931b9cbda19c90c657"
SOURCE_LIMIT = 65536
STATE_LIMIT = 32768
OUTPUT_LIMIT = 4096
LIMIT_SECONDS = 3.0
ROOT_PREFIX = "maskgw-pg16-shell-reader-v1-"
ROOT_PATTERN = re.compile(r"maskgw-pg16-shell-reader-v1-([0-9a-f]{32})")
TASK_PATTERN = re.compile(r"[0-9a-f]{32}")
CLAIM_PREFIX = "maskgw-pg16-shell-admission-claim-v1-"
RESULT_PREFIX = "maskgw-pg16-shell-admission-result-v1-"
MARKER = "admission-probe.json"
STAGES = ("ADMIT", "HOST", "CONTEXT", "FINAL_PINS")
OUTCOMES = frozenset(("WITHIN_3S", "OVER_3S", "CLOCK_INVALID", "STAGE_FAILED"))
RUNTIME = "win32-3.11.3-isolated-nobytecode-optimize0"
CODES = frozenset(
    (
        "PROBE_RUNTIME",
        "PROBE_TASK",
        "PROBE_SOURCE",
        "PROBE_SIZE",
        "PROBE_ROOT",
        "PROBE_STATE",
        "PROBE_CLAIMED",
        "PROBE_CLAIM_IO",
        "PROBE_MARK_IO",
        "PROBE_RESULT_IO",
        "PROBE_INTERNAL",
    )
)


class ProbeError(Exception):
    def __init__(self, code):
        super().__init__(code if type(code) is str and code in CODES else "PROBE_INTERNAL")


def need(value, code):
    if not value:
        raise ProbeError(code) from None


def guarded(code, function, *args):
    """Helpers raise their own classes; only a closed code leaves here."""
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
    return (text + "\n").encode("ascii")


def reparse(info):
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


def regular(path, maximum, code):
    """Bounded read: never allocates more than maximum+1 bytes, even after growth."""
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and not reparse(info), code)
    need(info.st_size <= maximum, "PROBE_SIZE")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    need(type(raw) is bytes and len(raw) <= maximum, "PROBE_SIZE")
    need(len(raw) == info.st_size, code)
    return raw


def real_directories(path):
    for item in (path, *path.parents):
        info = item.lstat()
        need(stat.S_ISDIR(info.st_mode) and not reparse(info), "PROBE_ROOT")


def absent(path):
    """Only a missing name: a file, directory, dangling link or reparse occupies it."""
    missing = False
    try:
        path.lstat()
    except FileNotFoundError:
        missing = True
    return missing


def runtime():
    flags = sys.flags
    need(
        sys.platform == "win32"
        and tuple(sys.version_info[:3]) == (3, 11, 3)
        and flags.isolated == 1
        and flags.dont_write_bytecode == 1
        and flags.optimize == 0,
        "PROBE_RUNTIME",
    )


def definitions(task):
    """Frozen preparer by SHA, then its pinned chain to the entry. No Host is built."""
    path = REPO / PREPARER_RELATIVE
    raw = guarded("PROBE_SOURCE", regular, path, SOURCE_LIMIT, "PROBE_SOURCE")
    need(sha(raw) == PREPARER_SHA, "PROBE_SOURCE")
    prep = {"__name__": "_pg16_admission_preparer", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), prep)
    need(
        prep["ENTRY_SHA"] == ENTRY_SHA and prep["ENTRY_RELATIVE"] == ENTRY_RELATIVE,
        "PROBE_SOURCE",
    )
    entry_path = REPO / ENTRY_RELATIVE
    entry_raw = guarded("PROBE_SOURCE", regular, entry_path, SOURCE_LIMIT, "PROBE_SOURCE")
    need(sha(entry_raw) == ENTRY_SHA, "PROBE_SOURCE")
    exporter, d = guarded("PROBE_SOURCE", prep["load"])
    state_raw = guarded("PROBE_STATE", prep["fresh_state"], task, exporter, d)[1]
    entry = d["entry"]
    return {
        "admit": entry["admit"],
        "Host": entry["H"]["Host"],
        "Context": entry["Context"],
        "final_pins": entry["final_pins"],
        "home": d["base"]["HOME"],
        "state_raw": state_raw,
    }


def listing(root):
    names = []
    for index, item in enumerate(root.iterdir()):
        need(index < 2, "PROBE_ROOT")
        names.append(item.name)
    return names


def check_root(root, home, state_raw):
    temp = home / "AppData/Local/Temp"
    need(
        type(root) is type(temp)
        and root.is_absolute()
        and root.parent == temp
        and ROOT_PATTERN.fullmatch(root.name) is not None,
        "PROBE_ROOT",
    )
    guarded("PROBE_ROOT", real_directories, root)
    need(guarded("PROBE_ROOT", listing, root) == ["attempt.json"], "PROBE_ROOT")
    attempt = guarded("PROBE_STATE", regular, root / "attempt.json", STATE_LIMIT, "PROBE_STATE")
    need(type(state_raw) is bytes and attempt == state_raw, "PROBE_STATE")
    return temp, ROOT_PATTERN.fullmatch(root.name)[1]


def persist(path, raw, code, exists_code):
    """xb only: never truncates, overwrites, retries or removes anything."""
    outcome = "FAILED"
    try:
        with path.open("xb") as stream:
            written = stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        outcome = "WRITTEN" if written == len(raw) else "SHORT"
    except FileExistsError:
        outcome = "EXISTS"
    except OSError:
        pass
    need(outcome != "EXISTS", exists_code)
    need(outcome == "WRITTEN", code)
    need(guarded(code, regular, path, len(raw), code) == raw, code)


def measure(stages, root):
    """One pass. Instrumentation stays inside the total; nothing is subtracted.

    Ordinary stage exceptions are caught without reading message, args or
    attributes. BaseException (interruption) propagates: never a result.
    """
    values = {}
    failed = None
    started = time.monotonic()
    ticks = [time.perf_counter_ns()]
    for index, name in enumerate(STAGES):
        completed = False
        try:
            if index == 0:
                values["state"] = stages["admit"](root)
            elif index == 1:
                values["host"] = stages["Host"](root, values["state"])
            elif index == 2:
                values["context"] = stages["Context"](root, values["state"], values["host"])
            else:
                stages["final_pins"](values["context"])
            completed = True
        except Exception:
            pass
        ticks.append(time.perf_counter_ns())
        if not completed:
            failed = name
            break
    ended = time.monotonic()
    return started, ended, ticks, failed


def classify(started, ended, ticks, failed):
    """Deterministic precedence: STAGE_FAILED, then CLOCK_INVALID, then 3 s."""
    valid = (
        type(started) is float
        and type(ended) is float
        and math.isfinite(started)
        and math.isfinite(ended)
        and all(type(tick) is int for tick in ticks)
        and all(later >= earlier for earlier, later in zip(ticks, ticks[1:]))
    )
    elapsed = ended - started if valid else None
    if elapsed is not None and not (math.isfinite(elapsed) and elapsed >= 0):
        valid, elapsed = False, None
    stages_ns = None
    if valid:
        deltas = [later - earlier for earlier, later in zip(ticks, ticks[1:])]
        stages_ns = deltas + [None] * (len(STAGES) - len(deltas))
    if failed is not None:
        outcome, stage, category = "STAGE_FAILED", failed, "STAGE_EXCEPTION"
    elif not valid:
        outcome, stage, category = "CLOCK_INVALID", None, "CLOCK_INVALID"
    elif 0 <= elapsed <= LIMIT_SECONDS:
        outcome, stage, category = "WITHIN_3S", None, None
    else:
        outcome, stage, category = "OVER_3S", None, None
    return {
        "outcome": outcome,
        "stage": stage,
        "category": category,
        "clock_valid": valid,
        "elapsed_seconds": elapsed,
        "stages_ns": stages_ns,
    }


def _probe(root, task):
    runtime()  # before captured-source loading, external reads or writes
    need(type(task) is str and TASK_PATTERN.fullmatch(task) is not None, "PROBE_TASK")
    own = guarded("PROBE_SOURCE", regular, Path(__file__), SOURCE_LIMIT, "PROBE_SOURCE")
    stages = definitions(task)
    temp, nonce = check_root(root, stages["home"], stages["state_raw"])
    claim = temp / (CLAIM_PREFIX + nonce + ".json")
    final = temp / (RESULT_PREFIX + nonce + ".json")
    pending = temp / (RESULT_PREFIX + nonce + ".json.next")
    for path in (claim, pending, final):
        need(guarded("PROBE_CLAIMED", absent, path) is True, "PROBE_CLAIMED")
    identity = {
        "task": task,
        "nonce": nonce,
        "root_name": root.name,
        "probe_sha256": sha(own),
        "preparer_sha256": PREPARER_SHA,
        "entry_sha256": ENTRY_SHA,
        "state_sha256": sha(stages["state_raw"]),
        "state_bytes": len(stages["state_raw"]),
    }
    claim_raw = encoded({"kind": "MASKGW_PG16_SHELL_ADMISSION_CLAIM_V1", **identity})
    persist(claim, claim_raw, "PROBE_CLAIM_IO", "PROBE_CLAIMED")
    # First measured operation only after the claim was written and read back.
    started, ended, ticks, failed = measure(stages, root)
    result = {
        "kind": "MASKGW_PG16_SHELL_ADMISSION_RESULT_V1",
        **identity,
        **classify(started, ended, ticks, failed),
        "limit_seconds": LIMIT_SECONDS,
        "runtime": RUNTIME,
        "claim_sha256": sha(claim_raw),
    }
    # All validation and serialization precede the completion publication.
    result_raw = guarded("PROBE_RESULT_IO", encoded, result)
    need(len(result_raw) <= OUTPUT_LIMIT and result["outcome"] in OUTCOMES, "PROBE_RESULT_IO")
    marker_raw = encoded(
        {
            "kind": "MASKGW_PG16_SHELL_ADMISSION_MARKER_V1",
            "task": task,
            "nonce": nonce,
            "claim_sha256": sha(claim_raw),
        }
    )
    # The marker makes the root inadmissible for the unchanged entry admit.
    persist(root / MARKER, marker_raw, "PROBE_MARK_IO", "PROBE_MARK_IO")
    persist(pending, result_raw, "PROBE_RESULT_IO", "PROBE_RESULT_IO")
    need(guarded("PROBE_RESULT_IO", absent, final) is True, "PROBE_RESULT_IO")
    # Completion publication is the last filesystem operation; nothing follows.
    guarded("PROBE_RESULT_IO", os.rename, pending, final)
    return result


def probe(root, task):
    """Closed errors only. An interruption (BaseException) propagates, never a result."""
    problem, done, result = None, False, None
    try:
        result = _probe(root, task)
        done = True
    except ProbeError as error:
        problem = error.args[0]
    except Exception:
        problem = "PROBE_INTERNAL"
    if done:
        return result
    raise ProbeError(problem) from None  # outside except: no cause or context


def main(argv):
    """Exit 0 only for a fully persisted WITHIN_3S result; every other path is nonzero."""
    status = 1
    summary = {"kind": "MASKGW_PG16_SHELL_ADMISSION_CLI_V1", "outcome": "REFUSED"}
    try:
        if type(argv) not in (list, tuple) or len(argv) != 3:
            summary["category"] = "PROBE_RUNTIME"
        else:
            result = probe(Path(argv[1]), argv[2])
            summary.update(outcome=result["outcome"], category=result["category"])
            status = 0 if result["outcome"] == "WITHIN_3S" else 1
    except ProbeError as error:
        summary["category"] = error.args[0]
    except BaseException:
        summary.update(outcome="INTERRUPTED", category="PROBE_INTERRUPTED")
        status = 2
    line = json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n"
    try:
        sys.stdout.write(line)
        sys.stdout.flush()
    except BaseException:
        status = status or 1
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
