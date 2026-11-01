"""Private benign native control runner. Import defines only.

No __main__, no CLI and no consumer. run(nonce) is the single private entry:
the nonce (32 lowercase hex) is only a freshness/consumption identifier, never
a credential, an approval or a permission. Calling run is a native effect that
still needs its own reviewed procedure, command and root.

Nothing is read at import. run explicitly reads by full SHA the accepted
caller (dfcc4ed6: generic helpers only, never mutated) and the nested-job
adapter (eaebedd6), whose definitions() supply the single backend identity
(10c9058f) used for Request, Owner, NestedJobOwner and Win32Error. Three fixed
benign cases run in order (NORMAL, TERMINATE, LAST_CLOSE); the first rejection
ends the batch. An owner not proven CLOSED stays in this module's registry for
the life of the process and nothing is published. Native behaviour is
unmeasured; budgets are decision budgets checked between OS calls.
"""

import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess  # list2cmdline only: measures the command line, never spawns

REPO = Path(__file__).resolve().parents[2]
TEMP = Path("C:/Users/w.filho/AppData/Local/Temp")
EVIDENCE = REPO / "docs/poc/evidence"
HOST = (
    "docs/poc/pg16_shell_admission_host.py",
    "dfcc4ed6be3ea8ab47b7a38ca8a9d4bfa00b3c75cda41c365be3dd5b1aa3dac7",
)
ADAPTER = (
    "docs/poc/pg16_shell_native_control_win32.py",
    "eaebedd6ac36602ba30cb51a4c30a2a93737f1127c23cdc4ebb8ae8cf9246407",
)
BACKEND_SHA = "10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726"
SOURCE_LIMIT = 65536
NONCE_PATTERN = re.compile(r"[0-9a-f]{32}")
PRIVATE_PREFIX = "maskgw-pg16-native-control-v1-"
PUBLIC_PREFIX = "pg16-native-control-"
NORMAL_LINE = "MASKGW-NATIVE-CONTROL-NORMAL"
READY_LINE = "MASKGW-NATIVE-CONTROL-READY"
NORMAL = 'print("MASKGW-NATIVE-CONTROL-NORMAL")'
SLEEP = 'import time;print("MASKGW-NATIVE-CONTROL-READY",flush=True);time.sleep(120)'
CASES = (("NORMAL", NORMAL), ("TERMINATE", SLEEP), ("LAST_CLOSE", SLEEP))
READY_SECONDS = 10.0
READY_TURNS = 200
TERMINATE_NAMES = ("TerminateJobObject", "TerminateProcess")
CASE_KEYS = (
    "case",
    "outcome",
    "rejection",
    "exit_code",
    "framing",
    "total_processes",
    "terminated",
    "ready",
    "inner_closed",
    "audit_integral",
    "audit_entries",
    "terminate_calls",
    "seconds",
)
REJECTIONS = frozenset(
    (
        "LAUNCH_FAILED",
        "CALLER_CLOCK",
        "DEADLINE",
        "OUTPUT_OVERFLOW",
        "TREE_UNPROVEN",
        "READY_MISSING",
        "READY_MISMATCH",
        "READY_EARLY_EXIT",
        "SNAPSHOT_INVALID",
        "CLOSE_INNER_FAILED",
        "AUDIT_INVALID",
        "FAILED_LAST_CLOSE",
        "MISMATCH",
    )
)
CODES = frozenset(
    (
        "CONTROL_RETAINED",
        "CONTROL_NONCE",
        "CONTROL_SOURCE",
        "CONTROL_RUNTIME",
        "CONTROL_ROOT",
        "CONTROL_CONSUMED",
        "CONTROL_ENVIRONMENT",
        "CONTROL_COMMAND",
        "CONTROL_PERSISTENCE",
        "CONTROL_LAUNCHER",
        "CONTROL_CLOCK",
        "CONTROL_HELD",
        "CONTROL_COMMIT_INDETERMINATE",
        "CONTROL_INTERNAL",
    )
)
# Owners not proven CLOSED. Kept for the life of this process; never
# persisted, never exposed through a recovery method.
_LIVE = []
_SOURCES = {}


class RunError(Exception):
    def __init__(self, code):
        super().__init__(code if type(code) is str and code in CODES else "CONTROL_INTERNAL")


def _check(value, code):
    if not value:
        raise RunError(code) from None


def _step(code, function, *args):
    """Any ordinary failure becomes one closed code, raised outside the except."""
    failed, result = False, None
    try:
        result = function(*args)
    except Exception:
        failed = True
    _check(not failed, code)
    return result


def _int(value):
    return value if type(value) is int else None


def _state(owner):
    state = owner.state
    return state if type(state) is str else None


def _release(owner):
    """Only an owner proven CLOSED leaves the registry."""
    if _state(owner) == "CLOSED":
        _LIVE[:] = [item for item in _LIVE if item is not owner]


def _framing(raw, line):
    body = line.encode("ascii")
    if raw == body + b"\n":
        return "LF"
    if raw == body + b"\r\n":
        return "CRLF"
    return None


# -- pinned sources ------------------------------------------------------------


def _read(relative, digest):
    path = REPO / relative
    raw, failed = None, False
    try:
        info = path.lstat()
        if (
            stat.S_ISREG(info.st_mode)
            and not getattr(info, "st_file_attributes", 0) & 0x400
            and info.st_size <= SOURCE_LIMIT
        ):
            with path.open("rb") as stream:
                raw = stream.read(SOURCE_LIMIT + 1)
            if len(raw) != info.st_size:
                raw = None
    except Exception:
        failed = True
    if failed or raw is None or hashlib.sha256(raw).hexdigest() != digest:
        raise RunError("CONTROL_SOURCE") from None
    return path, raw


def _load():
    """Explicit lazy load of the pinned caller and adapter; cached per module instance."""
    if not _SOURCES:
        host_path, host_raw = _read(*HOST)
        adapter_path, adapter_raw = _read(*ADAPTER)
        host = {"__name__": "_pg16_native_control_host", "__file__": str(host_path)}
        adapter = {"__name__": "_pg16_native_control_adapter", "__file__": str(adapter_path)}
        loaded, single = None, False
        try:
            exec(compile(host_raw, str(host_path), "exec"), host)
            exec(compile(adapter_raw, str(adapter_path), "exec"), adapter)
            loaded = adapter["definitions"]()
            backend = loaded["backend"]
            # One backend identity: a second copy would change Win32Error and
            # the caller's _attempt would turn every code into INTERNAL.
            single = (
                adapter["BACKEND_SHA"] == BACKEND_SHA
                and loaded["Request"] is backend["Request"]
                and loaded["Win32Error"] is backend["Win32Error"]
                and issubclass(loaded["NestedJobOwner"], backend["Owner"])
            )
        except Exception:
            single = False
        _check(single is True, "CONTROL_SOURCE")
        _SOURCES.update(host=host, adapter=adapter, loaded=loaded)
    return _SOURCES["host"], _SOURCES["adapter"], _SOURCES["loaded"]


def _owner_class(loaded, name):
    """Test seam. The single backend identity; INNER only for LAST_CLOSE."""
    return loaded["NestedJobOwner"] if name == "LAST_CLOSE" else loaded["backend"]["Owner"]


# -- records ---------------------------------------------------------------------


def _fields(case):
    facts = case["facts"]
    reason = facts["reason"]
    return {
        "reason": reason if type(reason) is str else None,
        "terminated": facts["terminated"] is True,
        "overflow": facts["overflow"] is True,
        "signaled": facts["signaled"] is True,
        "eof": facts["eof"] is True,
        "exit_code": _int(facts["exit_code"]),
        "total_processes": _int(facts["total_processes"]),
        "turns": _int(facts["turns"]),
        "ready": case["ready"],
        "ready_turns": case["ready_turns"],
        "retained_stdout_bytes": len(facts["retained"]),
        "seconds": case["seconds"],
    }


def _capture(owner, limit):
    """One read of each audit attribute; a malformed shape is never trusted."""
    entries, valid, failed = None, None, False
    try:
        entries, valid = owner.audit, owner.audit_valid
    except Exception:
        failed = True
    if failed or not (
        type(entries) is tuple
        and len(entries) <= limit
        and all(type(entry) is str and 0 < len(entry) <= 64 for entry in entries)
    ):
        return (), False
    return entries, valid is True


def _held_raw(owner, case, label):
    state = getattr(owner, "state", None)
    record = {
        "kind": "MASKGW_PG16_NATIVE_CONTROL_HELD_V1",
        "held": label,
        "case": case["name"],
        "owner_state": state if type(state) is str and len(state) <= 32 else None,
        **_fields(case),
        "audit": None,
    }
    if case["name"] == "LAST_CLOSE":
        # Owner not proven CLOSED: a partial best-effort copy, never a verdict.
        entries, valid = _capture(owner, case["audit_limit"])
        record["audit"] = {"partial": True, "valid": valid, "entries": list(entries)}
    return case["host"]["encoded"](record) + b"\n"


def _retain(owner, case, label):
    """At most one guarded terminate while RUNNING, then a finite private record
    written once (held.json, local-stdout.bin; xb, never replaced, removed or
    retried). Never publishes. Returns the first control interruption absorbed
    here, so an exception already propagating is never replaced."""
    host, facts, pending = case["host"], case["facts"], None
    try:
        state = _state(owner)
        if state == "RUNNING":
            if not case["contained"]:
                # Reserved before the side effect: a reentry after a control,
                # a failed or an interrupted attempt never tries again. The
                # supervisor's own decision terminate is a separate policy.
                case["contained"] = True
                code, _value = host["_attempt"](case["error"], owner.terminate)
                if code is None:
                    # A successful call only; never proof of reaping or release.
                    facts["terminated"] = True
        elif state == "CLOSED":
            _release(owner)
    except Exception:
        pass
    except BaseException as error:
        pending = error
    if case["recorded"]:
        return pending
    case["recorded"] = True
    for name, make in (
        ("held.json", lambda: _held_raw(owner, case, label)),
        ("local-stdout.bin", lambda: bytes(facts["retained"])),
    ):
        try:
            host["write_new"](case["directory"] / name, make())
        except Exception:
            pass
        except BaseException as error:
            if pending is None:
                pending = error
    return pending


def _contain(owner, case, label):
    """The whole retention boundary, protected: ordinary failures (allocation
    included) are absorbed; the first new control interruption returned by
    _retain or raised at its boundary is returned to the caller. The registry
    is reconciled independently, so an owner already proven CLOSED leaves it
    even if retention failed before releasing it; nothing is fabricated."""
    control = None
    try:
        control = _retain(owner, case, label)
    except Exception:
        pass
    except BaseException as error:
        control = error
    try:
        _release(owner)
    except Exception:
        pass
    except BaseException as error:
        if control is None:
            control = error
    return control


def _held(owner, case, label):
    """Owner stays registered; the run ends with nothing published. An
    interruption that arrived while recording is not swallowed."""
    pending = _retain(owner, case, label)
    if pending is not None:
        raise pending
    raise RunError("CONTROL_HELD") from None


# -- one case ----------------------------------------------------------------------


def _close_unstarted(owner, case, reason):
    """No child exists: setup failed, launch failed or no start allowed."""
    case["facts"]["reason"] = reason
    case["host"]["_attempt"](case["error"], owner.close)
    if _state(owner) != "CLOSED":
        _held(owner, case, "LAUNCH")
    _release(owner)


def _ready(owner, case):
    """READY with its own turn counter and budget; the clock history and every
    retained byte stay with the supervisor. Absence, extra bytes, overflow,
    early exit or clock failure set a reason; the tree is then terminated and
    proven by _supervise, never left RUNNING."""
    host, facts, clock = case["host"], case["facts"], case["clock"]
    line = READY_LINE.encode("ascii")
    frames = (line + b"\n", line + b"\r\n")
    begin = clock.now()
    while True:
        if case["ready_turns"] >= READY_TURNS:
            facts["reason"] = "READY_MISSING"
            return
        case["ready_turns"] += 1
        now = clock.now()
        if begin is None or now is None:
            facts["reason"] = "CALLER_CLOCK"
            return
        if now - begin >= READY_SECONDS:
            facts["reason"] = "READY_MISSING"
            return
        code, chunk = host["_attempt"](case["error"], owner.read)
        if code is not None or type(chunk) is not bytes or len(chunk) > case["read_limit"]:
            facts["held"] = "READY"
            return
        room = host["RETAIN_BYTES"] - len(facts["retained"])
        if len(chunk) > room:
            facts["retained"].extend(chunk[: max(room, 0)])
            facts["overflow"] = True
            facts["reason"] = "OUTPUT_OVERFLOW"
            return
        facts["retained"].extend(chunk)
        raw = bytes(facts["retained"])
        if raw in frames:
            case["ready"] = True
            return
        if not any(frame.startswith(raw) for frame in frames):
            facts["reason"] = "READY_MISMATCH"
            return
        code, value = host["_attempt"](case["error"], owner.wait, host["WAIT_MS"])
        if code is not None or type(value) is not bool:
            facts["held"] = "READY"
            return
        if value:
            facts["signaled"] = True
            facts["reason"] = "READY_EARLY_EXIT"
            return


def _snapshot(owner, case):
    """OUTER before the deliberate INNER close; strict types, no truthy values."""
    host, error = case["host"], case["error"]
    code, counts = host["_attempt"](error, owner.accounting)
    listed, pids = host["_attempt"](error, owner.members)
    ledger, verified = owner.ledger, owner.inner_verified is True
    inner = type(ledger) is dict and "inner" in ledger
    numbers = (
        code is None
        and type(counts) is tuple
        and len(counts) == 2
        and all(type(item) is int for item in counts)
    )
    members = (
        listed is None
        and type(pids) is tuple
        and all(type(pid) is int and 0 < pid < (1 << 32) for pid in pids)
    )
    valid = (
        numbers
        and members
        and inner
        and verified
        and counts[0] in (1, 2)
        and counts[1] == counts[0]
        and len(pids) == counts[1]
    )
    return {
        "valid": valid,
        "total": counts[0] if numbers else None,
        "active": counts[1] if numbers else None,
        "members": len(pids) if members else None,
        "inner_present": inner,
        "inner_verified": verified,
    }


def _last_close(owner, case):
    """Snapshot, deliberate close of the only INNER handle, then the decision
    budget restarts at the clock reading taken right after the close."""
    facts = case["facts"]
    case["snapshot"] = _snapshot(owner, case)
    if case["snapshot"]["valid"] is not True:
        facts["reason"] = "SNAPSHOT_INVALID"
        return
    code, _value = case["host"]["_attempt"](case["error"], owner.close_inner)
    case["inner_closed"] = owner.inner_closed is True
    if code is not None or not case["inner_closed"]:
        if _state(owner) != "RUNNING":
            _held(owner, case, "CLOSE_INNER")
        facts["reason"] = "CLOSE_INNER_FAILED"
        return
    since = case["clock"].now()
    if since is None:
        facts["reason"] = "CALLER_CLOCK"
        return
    case["since"] = since


def _lifecycle(owner, case):
    """Setup/start/READY/supervise/close on case-held facts. Unproven resources
    raise CONTROL_HELD; the owner leaves the registry only once CLOSED."""
    host, error, facts = case["host"], case["error"], case["facts"]
    code, _value = host["_attempt"](error, owner.setup)
    if code is not None and _state(owner) == "SETUP_FAILED":
        _close_unstarted(owner, case, "LAUNCH_FAILED")
        return
    if code is not None or _state(owner) != "READY":
        _held(owner, case, "LAUNCH")
    # Budget checked between setup and start: no child once it is spent or
    # once the clock is no longer trusted.
    now = case["clock"].now()
    if now is None or now - case["start"] >= host["DEADLINE_SECONDS"]:
        _close_unstarted(owner, case, "CALLER_CLOCK" if now is None else "DEADLINE")
        return
    code, _value = host["_attempt"](error, owner.start)
    if code is not None and _state(owner) == "LAUNCH_FAILED":
        _close_unstarted(owner, case, "LAUNCH_FAILED")
        return
    if code is not None or _state(owner) != "RUNNING":
        _held(owner, case, "LAUNCH")
    if case["name"] != "NORMAL":
        _ready(owner, case)
        if case["name"] == "LAST_CLOSE" and facts["held"] is None and facts["reason"] is None:
            _last_close(owner, case)
    if facts["held"] is None:
        # A preset reason makes the supervisor terminate first, then prove.
        host["_supervise"](owner, error, case["clock"], case["since"], facts)
    if facts["held"] is not None:
        _held(owner, case, facts["held"])
    host["_attempt"](error, owner.close)
    if _state(owner) != "CLOSED":
        _held(owner, case, "CLOSE")
    _release(owner)


def _verdict(case, audit):
    """Closed per-case summary; LAST_CLOSE uses only the single captured audit."""
    name, facts = case["name"], case["facts"]
    reason, exit_code, total = facts["reason"], facts["exit_code"], facts["total_processes"]
    framing = _framing(bytes(facts["retained"]), NORMAL_LINE if name == "NORMAL" else READY_LINE)
    proven = (
        facts["held"] is None
        and facts["overflow"] is False
        and facts["signaled"] is True
        and facts["eof"] is True
        and type(total) is int
        and total in (1, 2)
        and type(exit_code) is int
        and framing is not None
    )
    last = name == "LAST_CLOSE"
    entries, integral = audit if last else ((), False)
    terminations = sum(entry in TERMINATE_NAMES for entry in entries)
    if name == "NORMAL":
        approved = proven and reason is None and facts["terminated"] is False and exit_code == 0
    elif name == "TERMINATE":
        approved = (
            proven
            and case["ready"] is True
            and reason == "DEADLINE"
            and facts["terminated"] is True
            and exit_code == 1
        )
    else:
        snapshot = case["snapshot"]
        approved = (
            proven
            and case["ready"] is True
            and reason is None
            and facts["terminated"] is False
            and snapshot is not None
            and snapshot["valid"] is True
            and case["inner_closed"] is True
            and integral is True
            and terminations == 0
        )
    if approved:
        rejection = None
    elif last and integral is not True:
        rejection = "AUDIT_INVALID"
    elif last and case["inner_closed"] is True and terminations:
        rejection = "FAILED_LAST_CLOSE"
    elif reason is not None and not (name == "TERMINATE" and reason == "DEADLINE"):
        rejection = reason
    else:
        rejection = "MISMATCH"
    _check(rejection is None or rejection in REJECTIONS, "CONTROL_INTERNAL")
    return {
        "case": name,
        "outcome": "APPROVED" if approved else "REJECTED",
        "rejection": rejection,
        "exit_code": _int(exit_code),
        "framing": framing,
        "total_processes": _int(total),
        "terminated": facts["terminated"] is True,
        "ready": case["ready"] if name != "NORMAL" else None,
        "inner_closed": case["inner_closed"] if last else None,
        "audit_integral": integral if last else None,
        "audit_entries": len(entries) if last else None,
        "terminate_calls": terminations if last else None,
        "seconds": case["seconds"],
    }


def _persist(host, case, artifacts, files):
    for name, raw in files:
        _step("CONTROL_PERSISTENCE", host["write_new"], case["directory"] / name, raw)
        artifacts[case["prefix"] + name] = raw


def _finish(owner, case, artifacts):
    """Owner proven CLOSED and released: audit captured exactly once, verdict,
    then every private raw file durable before any public projection."""
    host, facts = case["host"], case["facts"]
    end = case["clock"].now()
    case["seconds"] = end - case["start"] if end is not None else None
    expected = facts["reason"] is None or (
        case["name"] == "TERMINATE" and facts["reason"] == "DEADLINE"
    )
    if end is None:
        # An invalid final reading (non-float, non-finite or backward) forbids
        # approval even after an expected reason; other reasons already reject.
        if expected:
            facts["reason"] = "CALLER_CLOCK"
    elif facts["reason"] is None and end - case["since"] >= host["DEADLINE_SECONDS"]:
        facts["reason"] = "DEADLINE"  # a late completion never wins
    audit = _capture(owner, case["audit_limit"]) if case["name"] == "LAST_CLOSE" else None
    record = _verdict(case, audit)
    supervision = {
        "kind": "MASKGW_PG16_NATIVE_CONTROL_SUPERVISION_V1",
        "case": case["name"],
        "owner_state": "CLOSED",
        **_fields(case),
    }
    files = [
        ("supervision.json", host["encoded"](supervision) + b"\n"),
        ("local-stdout.bin", bytes(facts["retained"])),
    ]
    if audit is not None:
        entries, integral = audit
        snapshot = {"kind": "MASKGW_PG16_NATIVE_CONTROL_SNAPSHOT_V1", "snapshot": case["snapshot"]}
        trail = {
            "kind": "MASKGW_PG16_NATIVE_CONTROL_AUDIT_V1",
            "integral": integral,
            "limit": case["audit_limit"],
            "entries": list(entries),
            "terminate_calls": record["terminate_calls"],
        }
        files.append(("snapshot.json", host["encoded"](snapshot) + b"\n"))
        files.append(("audit.json", host["encoded"](trail) + b"\n"))
    _persist(host, case, artifacts, files)
    return record


def _case(host, loaded, plan, private, artifacts):
    number, name, argv, request, base = plan
    directory = private / ("case-" + str(number))
    _step("CONTROL_PERSISTENCE", directory.mkdir, 0o777, False, False)
    case = {
        "name": name,
        "directory": directory,
        "prefix": "case-" + str(number) + "/",
        "host": host,
        "error": loaded["Win32Error"],
        "read_limit": loaded["backend"]["MAX_READ"],
        "audit_limit": base["limits"]["audit_limit"],
        "facts": host["_new_facts"](),  # case-held: partial facts survive
        "ready": False,
        "ready_turns": 0,
        "snapshot": None,
        "inner_closed": False,
        "contained": False,  # the one emergency retention terminate was reserved
        "recorded": False,  # the one finite held record was reserved
        "seconds": None,
    }
    invocation = {
        "kind": "MASKGW_PG16_NATIVE_CONTROL_INVOCATION_V1",
        **base,
        "case": name,
        "number": number,
        "argv": list(argv),  # private only; intended canonical absolute argv
        "environment_names": list(host["ENVIRONMENT_NAMES"]),  # never values
    }
    # Durable invocation before any launch.
    _persist(host, case, artifacts, (("invocation.json", host["encoded"](invocation) + b"\n"),))
    _step("CONTROL_LAUNCHER", host["_launcher_pin"])
    clock = host["_Clock"]()
    start = clock.now()  # decision budget starts immediately before setup
    _check(start is not None, "CONTROL_CLOCK")
    case.update(clock=clock, start=start, since=start)
    owner = _owner_class(loaded, name)(request)  # pure constructor
    _LIVE.append(owner)  # registered BEFORE setup; leaves only once CLOSED
    control = None
    try:
        _lifecycle(owner, case)
    except RunError:
        raise  # HELD paths already recorded; owner stays registered
    except Exception:
        control = _contain(owner, case, "INTERNAL")
        if control is None:
            raise  # sanitized to CONTROL_INTERNAL by run
    except BaseException:
        _contain(owner, case, "INTERRUPTED")  # never replaces the original
        raise  # the exact original control exception
    if control is not None:
        # A new control interruption during the cleanup of an ordinary
        # failure is never swallowed behind CONTROL_INTERNAL.
        raise control
    return _finish(owner, case, artifacts)


# -- publication -------------------------------------------------------------------


def _commit(pending, final, descriptor):
    """The last filesystem operation attempted. Nothing follows the attempt."""
    failed = False
    try:
        os.rename(pending, final)  # does not overwrite on Windows
    except Exception:
        failed = True
    if failed:
        # The effect may have happened before the failure: indeterminate,
        # never reported as unpublished; no check, retry or removal.
        raise RunError("CONTROL_COMMIT_INDETERMINATE") from None
    return descriptor


def _publish(host, summary, artifacts, public):
    """Every byte and the return value are prepared before the commit."""
    summary_raw = host["encoded"](summary) + b"\n"
    descriptor = host["strict"](summary_raw[:-1])
    _check(descriptor is not None, "CONTROL_INTERNAL")
    files = [
        {"name": name, "bytes": len(raw), "sha256": host["sha"](raw)}
        for name, raw in sorted(artifacts.items())
    ]
    transport = {
        "kind": "MASKGW_PG16_NATIVE_CONTROL_TRANSPORT_V1",
        "nonce": summary["nonce"],
        "outcome": summary["outcome"],
        "summary": {
            "name": "summary.json",
            "bytes": len(summary_raw),
            "sha256": host["sha"](summary_raw),
        },
        "private": files,
    }
    transport_raw = host["encoded"](transport) + b"\n"
    _check(not _LIVE, "CONTROL_HELD")  # never a final transport beside an unresolved owner
    code = "CONTROL_PERSISTENCE"
    _step(code, host["real_directories"], public.parent)
    _check(_step(code, host["absent"], public) is True, code)
    # From here a partial public directory is consumed: never deleted or retried.
    _step(code, public.mkdir, 0o777, False, False)
    pending, final = public / "transport.json.next", public / "transport.json"
    _step(code, host["write_new"], public / "summary.json", summary_raw)
    _step(code, host["write_new"], pending, transport_raw)
    names = _step(code, host["listing"], public)
    _check(names == ["summary.json", "transport.json.next"], code)
    _check(_step(code, host["absent"], final) is True, code)
    return _commit(pending, final, descriptor)


def _not_run(name):
    record = dict.fromkeys(CASE_KEYS)
    record.update(case=name, outcome="NOT_RUN")
    return record


def _run(nonce):
    _check(type(nonce) is str and NONCE_PATTERN.fullmatch(nonce) is not None, "CONTROL_NONCE")
    host, adapter, loaded = _load()
    _check(_step("CONTROL_RUNTIME", host["_runtime"]) is True, "CONTROL_RUNTIME")
    private = TEMP / (PRIVATE_PREFIX + nonce)
    public = EVIDENCE / (PUBLIC_PREFIX + nonce[:12])
    for parent in (TEMP, EVIDENCE):
        _step("CONTROL_ROOT", host["real_directories"], parent)
    for path in (private, public):
        _check(_step("CONTROL_CONSUMED", host["absent"], path) is True, "CONTROL_CONSUMED")
    environment = _step("CONTROL_ENVIRONMENT", host["_environment"])
    base = {
        "nonce": nonce,
        "host_sha256": HOST[1],
        "adapter_sha256": ADAPTER[1],
        "backend_sha256": BACKEND_SHA,
        "launcher_sha256": host["PYTHON_SHA"],
        "limits": {
            "deadline_seconds": host["DEADLINE_SECONDS"],
            "cleanup_seconds": host["CLEANUP_SECONDS"],
            "max_turns": host["MAX_TURNS"],
            "cleanup_turns": host["CLEANUP_TURNS"],
            "ready_seconds": READY_SECONDS,
            "ready_turns": READY_TURNS,
            "retain_bytes": host["RETAIN_BYTES"],
            "audit_limit": adapter["AUDIT_LIMIT"],
            "active_process_limit": loaded["backend"]["ACTIVE_PROCESS_LIMIT"],
        },
    }
    plans = []
    for number, (name, literal) in enumerate(CASES, 1):
        argv = (str(host["PYTHON"]), "-I", "-B", "-c", literal)
        command_line = subprocess.list2cmdline(argv)
        _check(len(command_line) <= host["COMMAND_LIMIT"], "CONTROL_COMMAND")
        request = _step(
            "CONTROL_COMMAND", loaded["Request"], argv[0], command_line, environment, str(REPO)
        )
        plans.append((number, name, argv, request, base))
    # From here the nonce is consumed: nothing is deleted, retried or reused.
    _step("CONTROL_PERSISTENCE", private.mkdir, 0o777, False, False)
    artifacts, records = {}, []
    for plan in plans:
        if records and records[-1]["outcome"] != "APPROVED":
            records.append(_not_run(plan[1]))
        else:
            records.append(_case(host, loaded, plan, private, artifacts))
    approved = all(record["outcome"] == "APPROVED" for record in records)
    summary = {
        "kind": "MASKGW_PG16_NATIVE_CONTROL_SUMMARY_V1",
        "nonce": nonce,
        "outcome": "APPROVED" if approved else "REJECTED",
        "scope": "BENIGN_CONTROL_ONLY",
        "admission_3s": "NOT_MEASURED",
        "cases": records,
        "host_sha256": HOST[1],
        "adapter_sha256": ADAPTER[1],
        "backend_sha256": BACKEND_SHA,
        "launcher_sha256": host["PYTHON_SHA"],
    }
    return _publish(host, summary, artifacts, public)


def run(nonce):
    """Private entry only; no CLI. Closed RunError; control interruptions propagate."""
    if _LIVE:
        raise RunError("CONTROL_RETAINED") from None
    problem, done, result = None, False, None
    try:
        result = _run(nonce)
        done = True
    except RunError as error:
        problem = error.args[0]
    except Exception:
        problem = "CONTROL_INTERNAL"
    if done:
        return result
    raise RunError(problem) from None
