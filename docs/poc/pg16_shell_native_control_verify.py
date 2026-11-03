"""Pure evidence verifier for the benign native controls. Import defines only.

verify() checks only the bytes it is handed: the public summary/transport and
the private artifacts of one control batch, against closed schemas, the
fixed pins/limits/environment names/literals of the accepted runner and an
independent recomputation of every case verdict. It never reads files,
starts processes, loads code or prints, and returns closed labels only. It
attests the provided bytes, not OS execution, CIM samples, source provenance
or cleanup; the trusted collector and the native preflight are separate.
"""

import dataclasses
import hashlib
import json
import math
import re

NONCE_PATTERN = re.compile(r"[0-9a-f]{32}")
SHA_PATTERN = re.compile(r"[0-9a-f]{64}")
PINS = (
    ("host_sha256", "dfcc4ed6be3ea8ab47b7a38ca8a9d4bfa00b3c75cda41c365be3dd5b1aa3dac7"),
    ("adapter_sha256", "eaebedd6ac36602ba30cb51a4c30a2a93737f1127c23cdc4ebb8ae8cf9246407"),
    ("backend_sha256", "10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726"),
    ("launcher_sha256", "bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82"),
)
PIN_KEYS = tuple(key for key, _value in PINS)
LIMITS = (
    ("deadline_seconds", 60.0),
    ("cleanup_seconds", 10.0),
    ("max_turns", 1200),
    ("cleanup_turns", 200),
    ("ready_seconds", 10.0),
    ("ready_turns", 200),
    ("retain_bytes", 1024),
    ("audit_limit", 512),
    ("active_process_limit", 2),
)
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
NORMAL_LITERAL = 'print("MASKGW-NATIVE-CONTROL-NORMAL")'
SLEEP_LITERAL = 'import time;print("MASKGW-NATIVE-CONTROL-READY",flush=True);time.sleep(120)'
CASES = ("NORMAL", "TERMINATE", "LAST_CLOSE")
LITERALS = {"NORMAL": NORMAL_LITERAL, "TERMINATE": SLEEP_LITERAL, "LAST_CLOSE": SLEEP_LITERAL}
LINES = {
    "NORMAL": b"MASKGW-NATIVE-CONTROL-NORMAL",
    "TERMINATE": b"MASKGW-NATIVE-CONTROL-READY",
    "LAST_CLOSE": b"MASKGW-NATIVE-CONTROL-READY",
}
KINDS = {
    "transport": "MASKGW_PG16_NATIVE_CONTROL_TRANSPORT_V1",
    "summary": "MASKGW_PG16_NATIVE_CONTROL_SUMMARY_V1",
    "invocation": "MASKGW_PG16_NATIVE_CONTROL_INVOCATION_V1",
    "supervision": "MASKGW_PG16_NATIVE_CONTROL_SUPERVISION_V1",
    "snapshot": "MASKGW_PG16_NATIVE_CONTROL_SNAPSHOT_V1",
    "audit": "MASKGW_PG16_NATIVE_CONTROL_AUDIT_V1",
}
TRANSPORT_KEYS = ("kind", "nonce", "outcome", "summary", "private")
BINDING_KEYS = ("name", "bytes", "sha256")
SUMMARY_KEYS = ("kind", "nonce", "outcome", "scope", "admission_3s", "cases", *PIN_KEYS)
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
LAST_KEYS = ("inner_closed", "audit_integral", "audit_entries", "terminate_calls")
INVOCATION_KEYS = (
    "kind",
    "nonce",
    *PIN_KEYS,
    "limits",
    "case",
    "number",
    "argv",
    "environment_names",
)
SUPERVISION_KEYS = (
    "kind",
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
)
SNAPSHOT_KEYS = ("valid", "total", "active", "members", "inner_present", "inner_verified")
AUDIT_KEYS = ("kind", "integral", "limit", "entries", "terminate_calls")
BATCH_OUTCOMES = ("APPROVED", "REJECTED")
CASE_OUTCOMES = ("APPROVED", "REJECTED", "NOT_RUN")
FRAMINGS = ("LF", "CRLF")
FACT_REASONS = frozenset(
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
    )
)
REJECTIONS = FACT_REASONS | {"AUDIT_INVALID", "FAILED_LAST_CLOSE", "MISMATCH"}
TERMINATE_NAMES = ("TerminateJobObject", "TerminateProcess")
CASE_FILES = ("invocation.json", "supervision.json", "local-stdout.bin")
CASE_1 = tuple("case-1/" + name for name in CASE_FILES)
CASE_2 = tuple("case-2/" + name for name in CASE_FILES)
CASE_3 = (
    *("case-3/" + name for name in CASE_FILES),
    "case-3/snapshot.json",
    "case-3/audit.json",
)
PREFIX_FILES = {
    1: frozenset(CASE_1),
    2: frozenset(CASE_1 + CASE_2),
    3: frozenset(CASE_1 + CASE_2 + CASE_3),
}
WHITELIST = PREFIX_FILES[3]
FILE_CAPS = {
    "invocation.json": 4096,
    "supervision.json": 4096,
    "local-stdout.bin": 1024,
    "snapshot.json": 4096,
    "audit.json": 65536,
}
SUMMARY_CAP = 16384
TRANSPORT_CAP = 4096
TOTAL_CAP = 262144
MAX_PRIVATE = 64
MAX_DEPTH = 32
AUDIT_LIMIT = 512
UINT32_LIMIT = 1 << 32  # native DWORD exit code and process counters
REASONS = frozenset(
    (
        "EXPECTED",
        "INPUT",
        "FILESET",
        "CAP",
        "SCHEMA",
        "NONCE",
        "PIN",
        "BINDING",
        "PREFIX",
        "INVOCATION",
        "SUPERVISION",
        "STDOUT",
        "SNAPSHOT",
        "AUDIT",
        "CONTRADICTION",
        "INTERNAL",
    )
)
APPROVED = ("VERIFIED_APPROVED", "OK")
REJECTED = ("VERIFIED_REJECTED", "OK")


@dataclasses.dataclass(frozen=True, repr=False, eq=False)
class Expected:
    """The only caller-supplied facts; everything else is fixed here."""

    nonce: object
    argv0: object

    def __repr__(self) -> str:
        return "Expected(<hidden>)"


class _Invalid(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__()
        self.reason = reason


def _require(condition: object, reason: str) -> None:
    if condition is not True:
        raise _Invalid(reason) from None


def _digest(raw: bytes) -> str:
    """Test seam: SHA-256 of bytes already captured."""
    return hashlib.sha256(raw).hexdigest()


# -- strict JSON (own parser rules; neither the producer nor the caller is an oracle) --


def _pairs(items: list) -> dict:
    record = {}
    for key, value in items:
        if key in record:
            raise ValueError
        record[key] = value
    return record


def _constant(_text: str) -> object:
    raise ValueError


def _integer(text: str) -> int:
    if len(text) > 11:
        raise ValueError
    value = int(text)
    if not -(1 << 31) <= value <= (1 << 32):
        raise ValueError
    return value


def _real(text: str) -> float:
    if len(text) > 32:
        raise ValueError
    value = float(text)
    if not math.isfinite(value):
        raise ValueError
    return value


def _shallow(text: str) -> bool:
    """Bracket depth outside strings never exceeds MAX_DEPTH."""
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                return False
        elif char in "]}":
            depth -= 1
    return True


def _parse(raw: bytes) -> object:
    """Exactly one final LF, ASCII, shallow, no duplicates/NaN, canonical."""
    _require(len(raw) >= 2 and raw[-1:] == b"\n", "SCHEMA")
    body = raw[:-1]
    _require(b"\n" not in body and b"\r" not in body, "SCHEMA")
    text, value, canonical, failed = "", None, None, False
    try:
        text = body.decode("ascii")
    except UnicodeDecodeError:
        failed = True
    _require(not failed and _shallow(text), "SCHEMA")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_constant=_constant,
            parse_int=_integer,
            parse_float=_real,
        )
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, RecursionError):
        failed = True
    _require(not failed and canonical is not None and canonical.encode("ascii") == body, "SCHEMA")
    return value


def _record(value: object, keys: tuple, kind: object = None) -> dict:
    _require(type(value) is dict and len(value) == len(keys) and set(value) == set(keys), "SCHEMA")
    if kind is not None:
        _require(value["kind"] == kind, "SCHEMA")
    return value


def _int(value: object) -> bool:
    return type(value) is int


def _opt_int(value: object) -> bool:
    return value is None or type(value) is int


def _bool(value: object) -> bool:
    return type(value) is bool


def _opt_bool(value: object) -> bool:
    return value is None or type(value) is bool


def _opt_u32(value: object) -> bool:
    """Field domain, not JSON grammar: null or exact int (never bool) in
    0 <= value < 2**32, as the native DWORD fields of the runner."""
    return value is None or (type(value) is int and 0 <= value < UINT32_LIMIT)


def _opt_float(value: object) -> bool:
    return value is None or type(value) is float


def _nonce(value: object) -> bool:
    return type(value) is str and NONCE_PATTERN.fullmatch(value) is not None


def _sha(value: object) -> bool:
    return type(value) is str and SHA_PATTERN.fullmatch(value) is not None


def _same(left: object, right: object) -> bool:
    return type(left) is type(right) and left == right


# -- public schemas --


def _check_transport(value: object) -> dict:
    record = _record(value, TRANSPORT_KEYS, KINDS["transport"])
    _require(_nonce(record["nonce"]) and record["outcome"] in BATCH_OUTCOMES, "SCHEMA")
    summary = _record(record["summary"], BINDING_KEYS)
    _require(
        summary["name"] == "summary.json"
        and _int(summary["bytes"])
        and summary["bytes"] >= 0
        and _sha(summary["sha256"]),
        "SCHEMA",
    )
    entries = record["private"]
    _require(type(entries) is list and len(entries) <= len(WHITELIST), "SCHEMA")
    names = []
    for entry in entries:
        _record(entry, BINDING_KEYS)
        _require(
            type(entry["name"]) is str
            and _int(entry["bytes"])
            and entry["bytes"] >= 0
            and _sha(entry["sha256"]),
            "SCHEMA",
        )
        names.append(entry["name"])
    _require(all(left < right for left, right in zip(names, names[1:])), "SCHEMA")
    return record


def _check_case(value: object) -> None:
    record = _record(value, CASE_KEYS)
    name, rejection = record["case"], record["rejection"]
    _require(
        name in CASES
        and record["outcome"] in CASE_OUTCOMES
        and (rejection is None or (type(rejection) is str and rejection in REJECTIONS))
        and _opt_u32(record["exit_code"])
        and (record["framing"] is None or record["framing"] in FRAMINGS)
        and _opt_u32(record["total_processes"])
        and _opt_bool(record["terminated"])
        and _opt_bool(record["ready"])
        and _opt_bool(record["inner_closed"])
        and _opt_bool(record["audit_integral"])
        and _opt_int(record["audit_entries"])
        and _opt_int(record["terminate_calls"])
        and _opt_float(record["seconds"]),
        "SCHEMA",
    )
    if name == "NORMAL":
        _require(record["ready"] is None, "SCHEMA")
    if name != "LAST_CLOSE":
        _require(all(record[key] is None for key in LAST_KEYS), "SCHEMA")


def _check_summary(value: object) -> dict:
    record = _record(value, SUMMARY_KEYS, KINDS["summary"])
    _require(
        _nonce(record["nonce"])
        and record["outcome"] in BATCH_OUTCOMES
        and record["scope"] == "BENIGN_CONTROL_ONLY"
        and record["admission_3s"] == "NOT_MEASURED"
        and all(_sha(record[key]) for key in PIN_KEYS),
        "SCHEMA",
    )
    cases = record["cases"]
    _require(type(cases) is list and len(cases) == len(CASES), "SCHEMA")
    for case in cases:
        _check_case(case)
    return record


def _bind(transport: dict, summary: dict, summary_raw: bytes, files: dict) -> None:
    entry = transport["summary"]
    _require(
        entry["bytes"] == len(summary_raw) and entry["sha256"] == _digest(summary_raw), "BINDING"
    )
    for item in transport["private"]:
        raw = files[item["name"]]
        _require(item["bytes"] == len(raw) and item["sha256"] == _digest(raw), "BINDING")
    _require(transport["outcome"] == summary["outcome"], "BINDING")


def _not_run(case: dict) -> bool:
    return case["outcome"] == "NOT_RUN" and all(
        case[key] is None for key in CASE_KEYS if key not in ("case", "outcome")
    )


def _prefix(summary: dict, files: dict) -> int:
    """Executed prefix: the first non-approved case ends the batch."""
    cases = summary["cases"]
    _require(tuple(case["case"] for case in cases) == CASES, "PREFIX")
    first = None
    for index, case in enumerate(cases):
        if case["outcome"] != "APPROVED":
            first = index
            break
    if first is None:
        executed, batch = len(CASES), "APPROVED"
    else:
        _require(cases[first]["outcome"] == "REJECTED", "PREFIX")
        _require(all(_not_run(case) for case in cases[first + 1 :]), "PREFIX")
        executed, batch = first + 1, "REJECTED"
    _require(summary["outcome"] == batch and set(files) == PREFIX_FILES[executed], "PREFIX")
    return executed


# -- private artifacts --


def _limits(value: dict) -> bool:
    return (
        len(value) == len(LIMITS)
        and set(value) == {key for key, _expected in LIMITS}
        and all(_same(value[key], expected) for key, expected in LIMITS)
    )


def _check_invocation(raw: bytes, number: int, name: str, captured: tuple) -> None:
    nonce, argv0 = captured
    record = _record(_parse(raw), INVOCATION_KEYS, KINDS["invocation"])
    _require(
        _nonce(record["nonce"])
        and all(_sha(record[key]) for key in PIN_KEYS)
        and type(record["limits"]) is dict
        and type(record["case"]) is str
        and _int(record["number"])
        and type(record["argv"]) is list
        and type(record["environment_names"]) is list,
        "SCHEMA",
    )
    _require(record["nonce"] == nonce, "NONCE")
    _require(all(record[key] == pin for key, pin in PINS), "PIN")
    argv = (argv0, "-I", "-B", "-c", LITERALS[name])
    names = record["environment_names"]
    _require(
        record["case"] == name
        and record["number"] == number
        and len(record["argv"]) == len(argv)
        and all(_same(left, right) for left, right in zip(record["argv"], argv))
        and _limits(record["limits"])
        and len(names) == len(ENVIRONMENT_NAMES)
        and all(_same(left, right) for left, right in zip(names, ENVIRONMENT_NAMES)),
        "INVOCATION",
    )


def _check_supervision(raw: bytes, name: str, case: dict) -> dict:
    record = _record(_parse(raw), SUPERVISION_KEYS, KINDS["supervision"])
    reason = record["reason"]
    _require(
        type(record["case"]) is str
        and type(record["owner_state"]) is str
        and (reason is None or (type(reason) is str and reason in FACT_REASONS))
        and all(_bool(record[key]) for key in ("terminated", "overflow", "signaled", "eof"))
        and _bool(record["ready"])
        and _opt_u32(record["exit_code"])
        and _opt_u32(record["total_processes"])
        and _int(record["turns"])
        and _int(record["ready_turns"])
        and _int(record["retained_stdout_bytes"])
        and _opt_float(record["seconds"]),
        "SCHEMA",
    )
    seconds = record["seconds"]
    if name == "NORMAL":
        ready = record["ready"] is False and record["ready_turns"] == 0
    else:
        ready = _same(case["ready"], record["ready"])
    _require(
        record["owner_state"] == "CLOSED"
        and record["case"] == name
        and _same(case["exit_code"], record["exit_code"])
        and _same(case["total_processes"], record["total_processes"])
        and _same(case["terminated"], record["terminated"])
        and _same(case["seconds"], seconds)
        and ready
        and 0 <= record["ready_turns"] <= 200
        and record["turns"] >= 0
        and 0 <= record["retained_stdout_bytes"] <= FILE_CAPS["local-stdout.bin"]
        and (seconds is None or seconds >= 0.0),
        "SUPERVISION",
    )
    return record


def _framing(raw: bytes, line: bytes) -> object:
    if raw == line + b"\n":
        return "LF"
    if raw == line + b"\r\n":
        return "CRLF"
    return None


def _check_stdout(raw: bytes, name: str, supervision: dict, case: dict) -> object:
    _require(len(raw) == supervision["retained_stdout_bytes"], "STDOUT")
    framing = _framing(raw, LINES[name])
    _require(_same(framing, case["framing"]), "STDOUT")
    return framing


def _check_snapshot(raw: bytes, supervision: dict, case: dict) -> object:
    record = _record(_parse(raw), ("kind", "snapshot"), KINDS["snapshot"])
    snapshot = record["snapshot"]
    if snapshot is None:
        _require(case["outcome"] == "REJECTED", "SNAPSHOT")
    else:
        _record(snapshot, SNAPSHOT_KEYS)
        total, active, members = snapshot["total"], snapshot["active"], snapshot["members"]
        _require(
            _bool(snapshot["valid"])
            and _opt_u32(total)
            and _opt_u32(active)
            and _opt_u32(members)
            and _bool(snapshot["inner_present"])
            and _bool(snapshot["inner_verified"]),
            "SCHEMA",
        )
        # Validity is recomputed from all six fields, never trusted.
        valid = (
            _int(total)
            and total in (1, 2)
            and _same(active, total)
            and _same(members, active)
            and snapshot["inner_present"] is True
            and snapshot["inner_verified"] is True
        )
        _require(valid == snapshot["valid"], "SNAPSHOT")
    if supervision["reason"] == "SNAPSHOT_INVALID":
        _require(snapshot is not None and snapshot["valid"] is False, "SNAPSHOT")
    return snapshot


def _check_audit(raw: bytes, case: dict) -> dict:
    record = _record(_parse(raw), AUDIT_KEYS, KINDS["audit"])
    entries = record["entries"]
    _require(
        _bool(record["integral"])
        and _int(record["limit"])
        and _int(record["terminate_calls"])
        and type(entries) is list
        and all(type(entry) is str for entry in entries),
        "SCHEMA",
    )
    count = sum(1 for entry in entries if entry in TERMINATE_NAMES)
    _require(
        record["limit"] == AUDIT_LIMIT
        and len(entries) <= AUDIT_LIMIT
        and all(0 < len(entry) <= 64 for entry in entries)
        and record["terminate_calls"] == count
        and _same(case["audit_integral"], record["integral"])
        and _same(case["audit_entries"], len(entries))
        and _same(case["terminate_calls"], count),
        "AUDIT",
    )
    return record


# -- independent verdict --


def _recompute(name: str, supervision: dict, framing: object, evidence: tuple) -> tuple:
    """Per-case verdict and rejection in the runner's precedence, from facts."""
    case, snapshot, audit = evidence
    reason, exit_code = supervision["reason"], supervision["exit_code"]
    total = supervision["total_processes"]
    proven = (
        supervision["overflow"] is False
        and supervision["signaled"] is True
        and supervision["eof"] is True
        and _int(total)
        and total in (1, 2)
        and _int(exit_code)
        and framing is not None
        and type(supervision["seconds"]) is float
    )
    last = name == "LAST_CLOSE"
    integral = audit["integral"] if last else False
    terminations = audit["terminate_calls"] if last else 0
    inner_closed = case["inner_closed"] if last else None
    if name == "NORMAL":
        approved = (
            proven and reason is None and supervision["terminated"] is False and exit_code == 0
        )
    elif name == "TERMINATE":
        approved = (
            proven
            and supervision["ready"] is True
            and reason == "DEADLINE"
            and supervision["terminated"] is True
            and exit_code == 1
        )
    else:
        approved = (
            proven
            and supervision["ready"] is True
            and reason is None
            and supervision["terminated"] is False
            and snapshot is not None
            and snapshot["valid"] is True
            and inner_closed is True
            and integral is True
            and terminations == 0
        )
    if approved:
        rejection = None
    elif last and integral is not True:
        rejection = "AUDIT_INVALID"
    elif last and inner_closed is True and terminations > 0:
        rejection = "FAILED_LAST_CLOSE"
    elif reason is not None and not (name == "TERMINATE" and reason == "DEADLINE"):
        rejection = reason
    else:
        rejection = "MISMATCH"
    return ("APPROVED" if approved else "REJECTED", rejection)


# -- entry --


def _capture(expected: object, summary_raw: object, transport_raw: object, private: object):
    """Reads the caller objects once; afterwards only the returned copies are used."""
    _require(type(expected) is Expected, "EXPECTED")
    nonce, argv0 = expected.nonce, expected.argv0  # single read of each field
    _require(
        _nonce(nonce) and type(argv0) is str and 0 < len(argv0) <= 1024 and "\x00" not in argv0,
        "EXPECTED",
    )
    _require(
        type(summary_raw) is bytes and type(transport_raw) is bytes and type(private) is dict,
        "INPUT",
    )
    _require(len(private) <= MAX_PRIVATE, "CAP")
    items = list(private.items())
    _require(all(type(key) is str and type(raw) is bytes for key, raw in items), "INPUT")
    _require(all(key in WHITELIST for key, _raw in items), "FILESET")
    files = dict(items)  # the only private view used from here on
    total = len(summary_raw) + len(transport_raw) + sum(len(raw) for raw in files.values())
    _require(
        len(summary_raw) <= SUMMARY_CAP
        and len(transport_raw) <= TRANSPORT_CAP
        and all(len(raw) <= FILE_CAPS[name.split("/", 1)[1]] for name, raw in files.items())
        and total <= TOTAL_CAP,
        "CAP",
    )
    return (nonce, argv0), summary_raw, transport_raw, files


def _verify(expected: object, summary_raw: object, transport_raw: object, private: object):
    captured, summary_raw, transport_raw, files = _capture(
        expected, summary_raw, transport_raw, private
    )
    nonce = captured[0]
    transport = _check_transport(_parse(transport_raw))
    summary = _check_summary(_parse(summary_raw))
    _require(transport["nonce"] == nonce and summary["nonce"] == nonce, "NONCE")
    _require(all(summary[key] == pin for key, pin in PINS), "PIN")
    _require({item["name"] for item in transport["private"]} == set(files), "FILESET")
    _bind(transport, summary, summary_raw, files)
    executed = _prefix(summary, files)
    verdicts = []
    for index in range(executed):
        name, number, case = CASES[index], index + 1, summary["cases"][index]
        prefix = "case-" + str(number) + "/"
        _check_invocation(files[prefix + "invocation.json"], number, name, captured)
        supervision = _check_supervision(files[prefix + "supervision.json"], name, case)
        framing = _check_stdout(files[prefix + "local-stdout.bin"], name, supervision, case)
        snapshot, audit = None, None
        if name == "LAST_CLOSE":
            snapshot = _check_snapshot(files[prefix + "snapshot.json"], supervision, case)
            audit = _check_audit(files[prefix + "audit.json"], case)
        verdict = _recompute(name, supervision, framing, (case, snapshot, audit))
        verdicts.append((case, verdict))
    for case, (outcome, rejection) in verdicts:
        _require(
            _same(case["outcome"], outcome) and _same(case["rejection"], rejection),
            "CONTRADICTION",
        )
    return APPROVED if summary["outcome"] == "APPROVED" else REJECTED


def verify(expected: object, summary_raw: object, transport_raw: object, private: object) -> tuple:
    """Closed (label, reason) only; never prints or returns paths, PIDs, argv or
    text. Ordinary internal failures are INVALID/INTERNAL; control
    interruptions (BaseException that is not Exception) propagate unchanged."""
    reason = "INTERNAL"
    try:
        return _verify(expected, summary_raw, transport_raw, private)
    except _Invalid as error:
        reason = error.reason
    except Exception:
        reason = "INTERNAL"
    return ("INVALID", reason if type(reason) is str and reason in REASONS else "INTERNAL")
