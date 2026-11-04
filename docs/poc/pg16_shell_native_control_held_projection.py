"""Pure projection of one HELD record to closed diagnostic labels. Import defines only.

project(raw) receives the exact bytes of a single held.json as written by the
consumed benign-control runner (b4198fe1, _held_raw + _fields, encoded by the
caller dfcc4ed6) and returns a fresh dictionary of closed labels. No CLI, no
filesystem, process, signal or native call. Any malformed, noncanonical,
oversized, unknown or wrongly typed input gives the same closed refusal; no
input text, number, path, PID, argv, audit entry or exception is ever echoed.

The result is a diagnostic only: source provenance is UNATTESTED and native
release is NOT_PROVEN. It is never identity, an authoritative record, a
release, a gate or a root-cause proof.
"""

import json

RAW_LIMIT = 4096
KIND_IN = "MASKGW_PG16_NATIVE_CONTROL_HELD_V1"
KIND_OUT = "MASKGW_PG16_HELD_PROJECTION_DIAGNOSTIC_V1"
CASES = ("NORMAL", "TERMINATE", "LAST_CLOSE")
HELD_LABELS = (
    "LAUNCH",
    "CLOSE_INNER",
    "CLOSE",
    "READY",
    "TERMINATE",
    "CLEANUP",
    "READ",
    "WAIT",
    "ACCOUNTING",
    "MEMBERS",
    "EXIT",
)
# Every literal the backend Owner (10c9058f) assigns to its state.
OWNER_STATES = (
    "NEW",
    "SETUP",
    "SETUP_FAILED",
    "READY",
    "STARTING",
    "LAUNCH_FAILED",
    "RUNNING",
    "HELD",
    "CLOSED",
)
# The runner's REJECTIONS; a held reason is one of them or null.
REJECTIONS = (
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
KEYS = frozenset(
    (
        "kind",
        "held",
        "case",
        "owner_state",
        "reason",
        "terminated",
        "overflow",
        "signaled",
        "eof",
        "exit_code",
        "total_processes",
        "turns",
        "ready",
        "ready_turns",
        "retained_stdout_bytes",
        "seconds",
        "audit",
    )
)
FLAGS = ("terminated", "overflow", "signaled", "eof", "ready")
AUDIT_KEYS = frozenset(("partial", "valid", "entries"))
UINT_LIMIT = 1 << 32
READY_TURNS = 200
RETAIN_BYTES = 1024
AUDIT_LIMIT = 512
ENTRY_LIMIT = 64


def _refused():
    return {
        "kind": KIND_OUT,
        "outcome": "HELD_PROJECTION_REFUSED",
        "error": "HELD_PROJECTION_INPUT",
        "source_provenance": "UNATTESTED",
        "native_release": "NOT_PROVEN",
    }


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _constant(_name):
    raise ValueError("non-finite constant")


def _decode(raw):
    """Exact bytes, at most RAW_LIMIT, one trailing LF, ASCII, strict JSON and
    byte-identical to the producer's canonical encoding; None otherwise."""
    if type(raw) is not bytes or not 0 < len(raw) <= RAW_LIMIT or raw[-1:] != b"\n":
        return None
    body = raw[:-1]
    value = json.loads(body.decode("ascii"), object_pairs_hook=_pairs, parse_constant=_constant)
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return value if canonical.encode("ascii") == body else None


def _label(value, allowed):
    return type(value) is str and value in allowed  # exact str: no foreign equality


def _uint(value, limit=UINT_LIMIT):
    return type(value) is int and 0 <= value < limit


def _audit(case, audit):
    if case != "LAST_CLOSE":
        return audit is None
    if type(audit) is not dict or set(audit) != AUDIT_KEYS:
        return False
    entries = audit["entries"]
    return (
        audit["partial"] is True
        and type(audit["valid"]) is bool
        and type(entries) is list
        and len(entries) <= AUDIT_LIMIT
        and all(type(entry) is str and 0 < len(entry) <= ENTRY_LIMIT for entry in entries)
    )


def _valid(value):
    if type(value) is not dict or len(value) != len(KEYS) or set(value) != KEYS:
        return False
    owner_state, reason = value["owner_state"], value["reason"]
    exit_code, total = value["exit_code"], value["total_processes"]
    return (
        type(value["kind"]) is str
        and value["kind"] == KIND_IN
        and _label(value["case"], CASES)
        and _label(value["held"], HELD_LABELS)
        and (owner_state is None or _label(owner_state, OWNER_STATES))
        and (reason is None or _label(reason, REJECTIONS))
        and all(type(value[name]) is bool for name in FLAGS)
        and (exit_code is None or _uint(exit_code))
        and (total is None or _uint(total))
        and _uint(value["turns"])
        and _uint(value["ready_turns"], READY_TURNS + 1)
        and _uint(value["retained_stdout_bytes"], RETAIN_BYTES + 1)
        and value["seconds"] is None  # set only in _finish, never before _held
        and _audit(value["case"], value["audit"])
    )


def project(raw):
    """A fresh closed dictionary; every ordinary failure is the same refusal."""
    try:
        value = _decode(raw)
        if value is None or not _valid(value):
            return _refused()
        return {
            "kind": KIND_OUT,
            "outcome": "HELD_PROJECTION_DIAGNOSTIC",
            "case": value["case"],
            "held": value["held"],
            "owner_state": value["owner_state"],
            "reason": value["reason"],
            "terminated": value["terminated"],
            "signaled": value["signaled"],
            "eof": value["eof"],
            "ready": value["ready"],
            "source_provenance": "UNATTESTED",
            "native_release": "NOT_PROVEN",
        }
    except Exception:
        return _refused()
