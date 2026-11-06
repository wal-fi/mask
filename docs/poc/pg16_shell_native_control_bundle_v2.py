"""Private in-memory A->B bundle builder. Import defines only.

No __main__, no CLI, no loader, no collector and no publisher. Nothing here
reads a file, loads or executes source, starts a process or prints.

bundle(group, slots, measured, nonce) turns completed slots of the case V2
caller (A) into a candidate envelope for the provenance validator (B):

- group: (case_ns, keep, legacy, lifecycle, reconcile, host, registry,
  private), the original references a trusted producer captured BEFORE the
  first allocate and before any effect;
- slots: 1..3 slots of that caller, allocated serially on demand;
- measured: the loader's declarations (8 source rows, launcher sha), NOT the
  reviewer's expected policy;
- nonce: 32 lowercase hex, origin and freshness guaranteed externally.

Result: ("BUNDLE_READY", (manifest, summary, transport, private, metadata))
or ("BUNDLE_REFUSED", reason), reason one of 13 closed labels. A candidate is
not verified: the full B validation stays mandatory and nothing here permits
exit, publication, release or retry. Owner release is a fresh logical
observation (empty original list and ledger, CLOSED), not OS quiescence.

Shapes, counts and key domains are checked before any lookup, hash, equality
or callback; scalars are bounded before encoding; a global fingerprint of the
group and of every slot is rechecked around each of at most nine trusted read
helpers of A and once more after the bytes are built. The builder never
writes slots, owners, lists, ledgers or latches and never calls run,
lifecycle, finish, close, reconcile or _finished. The original classes and
descriptors (_Slot, _Refs, _Context, clock, Owner) and the standard library
are trusted premises; a malicious initial namespace or coherent changes made
before the snapshot are not authenticated by identity guards.
"""

import hashlib
import json
import math
from types import FunctionType

CASES = ("NORMAL", "TERMINATE", "LAST_CLOSE")
PREFIXES = ("case-1/", "case-2/", "case-3/")
META_NAMES = ("case-1/v2-case.json", "case-2/v2-case.json", "case-3/v2-case.json")
CASE_FILES = (
    ("invocation.json", "supervision.json", "local-stdout.bin"),
    ("invocation.json", "supervision.json", "local-stdout.bin"),
    ("invocation.json", "supervision.json", "local-stdout.bin", "snapshot.json", "audit.json"),
)
FILE_CAPS = {
    "invocation.json": 4096,
    "supervision.json": 4096,
    "local-stdout.bin": 1024,
    "snapshot.json": 4096,
    "audit.json": 65536,
}
WHITELIST = frozenset(
    PREFIXES[index] + leaf for index in range(len(CASES)) for leaf in CASE_FILES[index]
)
MAX_PRIVATE = 11
PRIVATE_CAP = 97280
CALLER_KEYS = 128
SOURCE_KEYS = 256
KEY_CHARS = 64
RETAINED_CAP = 1024
UINT32 = 1 << 32
AUDIT_CAP = 512
FLOAT_CHARS = 32
SUMMARY_CAP = 16384
TRANSPORT_CAP = 4096
MANIFEST_CAP = 4096
METADATA_CAP = 1024
CASE_FIELDS = frozenset(
    (
        "name",
        "directory",
        "prefix",
        "host",
        "error",
        "read_limit",
        "audit_limit",
        "facts",
        "ready",
        "ready_turns",
        "snapshot",
        "inner_closed",
        "contained",
        "recorded",
        "seconds",
        "clock",
        "start",
        "since",
        "lifecycle_reserved",
        "reconcile_reserved",
    )
)
FACT_FIELDS = (
    "reason",
    "held",
    "terminated",
    "overflow",
    "signaled",
    "eof",
    "exit_code",
    "total_processes",
    "turns",
    "retained",
)
FACT_SCALARS = ("reason", "terminated", "overflow", "signaled", "eof")
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
REJECTIONS = FACT_REASONS | frozenset(("AUDIT_INVALID", "FAILED_LAST_CLOSE", "MISMATCH"))
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
ROLES = (
    "case_caller",
    "lifecycle_v2",
    "tree_reconcile",
    "runner",
    "adapter",
    "backend",
    "host",
    "core_verify",
)
PATHS = (
    "docs/poc/pg16_shell_native_control_case_v2.py",
    "docs/poc/pg16_shell_native_control_lifecycle_v2.py",
    "docs/poc/pg16_shell_tree_reconcile.py",
    "docs/poc/pg16_shell_native_control.py",
    "docs/poc/pg16_shell_native_control_win32.py",
    "docs/poc/pg16_shell_admission_win32.py",
    "docs/poc/pg16_shell_admission_host.py",
    "docs/poc/pg16_shell_native_control_verify.py",
)
SOURCE_CAP = 65536
HEX = frozenset("0123456789abcdef")
PINS = (
    ("host_sha256", "dfcc4ed6be3ea8ab47b7a38ca8a9d4bfa00b3c75cda41c365be3dd5b1aa3dac7"),
    ("adapter_sha256", "eaebedd6ac36602ba30cb51a4c30a2a93737f1127c23cdc4ebb8ae8cf9246407"),
    ("backend_sha256", "10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726"),
    ("launcher_sha256", "bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82"),
)
SUMMARY_KIND = "MASKGW_PG16_NATIVE_CONTROL_SUMMARY_V1"
TRANSPORT_KIND = "MASKGW_PG16_NATIVE_CONTROL_TRANSPORT_V1"
MANIFEST_KIND = "MASKGW_PG16_NATIVE_CONTROL_V2_MANIFEST_V1"
CASE_KIND = "MASKGW_PG16_NATIVE_CONTROL_V2_CASE_V1"
READY = "READY_FOR_VALIDATION"
BOUND = ("_Slot", "_Refs", "_intact", "_released", "_record", "KEEP")
SLOT_REFS = (
    "owner",
    "case",
    "facts",
    "retained",
    "ledger",
    "ctx",
    "record",
    "refs",
    "meta",
    "clock",
)
GROUP_INDEX = (
    (2, "legacy"),
    (3, "lifecycle"),
    (4, "reconcile"),
    (5, "host"),
    (6, "registry"),
    (7, "artifacts"),
)
DISTINCT = SLOT_REFS
REFS_FIELDS = (
    "entries",
    "now",
    "run_error",
    "refused",
    "context_type",
    "context",
    "lifecycle",
    "finish",
    "state",
    "case_keys",
)
CASE_META = ("name", "prefix", "read_limit", "audit_limit", "start")
READ_LIMIT = 4096  # backend MAX_READ in the A profile
AUDIT_LIMIT = 512  # adapter AUDIT_LIMIT in the A profile
CTX_BINDINGS = (
    "owner",
    "case",
    "legacy",
    "reconcile",
    "facts",
    "retained",
    "registry",
    "ledger",
    "clock",
    "host",
)
ENTRIES = 34
META_ITEMS = 8


class _Refuse(Exception):
    def __init__(self, reason):
        super().__init__()
        self.reason = reason


class _State:
    """Frozen locals of one build: bound originals and typed snapshots."""

    __slots__ = ("group", "bound", "context_type", "lengths", "slots", "rows", "private")


class _Row:
    """Snapshot of one slot: original identities and typed scalar values."""

    __slots__ = (
        "slot",
        "refs",
        "tree",
        "entries",
        "ctx",
        "meta",
        "facts",
        "retained",
        "record",
        "outcome",
        "fields",
        "case_meta",
    )


def _require(condition, reason):
    if condition is not True:
        raise _Refuse(reason) from None


def _attr(target, name):
    """A mandatory attribute of a genuine trusted object; missing is SHAPE."""
    missing, value = False, None
    try:
        value = getattr(target, name)
    except AttributeError:
        missing = True
    _require(not missing, "SHAPE")
    return value


# -- exact shapes, no foreign hash/equality -------------------------------------------------


def _str_keys(mapping):
    """Exact dict whose keys are all exact str, by iteration before any lookup."""
    if type(mapping) is not dict:
        return False
    for key in mapping:
        if type(key) is not str:
            return False
    return True


def _namespace(mapping, limit):
    """Exact dict, bounded count, then bounded exact str names."""
    if type(mapping) is not dict or len(mapping) > limit:
        return False
    for key in mapping:
        if type(key) is not str or not 0 < len(key) <= KEY_CHARS:
            return False
    return True


def _keyed(mapping, count, names):
    """Exact dict with exactly `count` exact str keys equal to `names`."""
    if type(mapping) is not dict or len(mapping) != count:
        return False
    if not _str_keys(mapping):
        return False
    return all(name in mapping for name in names)


def _hex(value, size):
    if type(value) is not str or len(value) != size:
        return False
    return all(char in HEX for char in value)


def _uint(value, limit):
    return type(value) is int and 0 <= value < limit


def _same(left, right):
    return type(left) is type(right) and left == right


def _enum(value, allowed):
    return type(value) is str and value in allowed


def _optional(value, check):
    return value is None or check(value)


# -- 1-4. group, input, caps, keep -------------------------------------------------------------


def _function(namespace, name):
    value = namespace.get(name)
    return type(value) is FunctionType and value.__globals__ is namespace


def _group(group):
    _require(type(group) is tuple and len(group) == 8, "GROUP")
    case_ns, keep, legacy, lifecycle, reconcile, host, registry, private = group
    _require(_namespace(case_ns, CALLER_KEYS), "GROUP")
    slot_class, refs_class = case_ns.get("_Slot"), case_ns.get("_Refs")
    _require(type(slot_class) is type and type(refs_class) is type, "GROUP")
    init = vars(slot_class).get("__init__")
    _require(type(init) is FunctionType and init.__globals__ is case_ns, "GROUP")
    for name in ("_intact", "_released", "_record"):
        _require(_function(case_ns, name), "GROUP")
    _require(case_ns.get("KEEP") is keep, "GROUP")
    for namespace in (legacy, lifecycle, host):
        _require(_namespace(namespace, SOURCE_KEYS), "GROUP")
    _require(type(registry) is list and legacy.get("_LIVE") is registry, "GROUP")
    _require(type(private) is dict and len(private) <= MAX_PRIVATE, "GROUP")
    context_type = lifecycle.get("_Context")
    _require(type(context_type) is type, "GROUP")
    state = _State()
    state.group = group
    state.bound = tuple((name, case_ns[name]) for name in BOUND)
    state.context_type = context_type
    state.lengths = _lengths(group)  # exact initial sizes of the bounded namespaces
    return state


def _lengths(group):
    return tuple(len(group[index]) for index in (0, 2, 3, 5))


def _measured(measured):
    _require(type(measured) is tuple and len(measured) == 2, "INPUT")
    rows, launcher = measured[0], measured[1]
    _require(type(rows) is tuple and len(rows) == len(ROLES), "INPUT")
    frozen = []
    for index in range(len(ROLES)):
        row = rows[index]
        _require(type(row) is tuple and len(row) == 4, "INPUT")
        role, path, size, digest = row[0], row[1], row[2], row[3]
        _require(
            _enum(role, (ROLES[index],))
            and _enum(path, (PATHS[index],))
            and type(size) is int
            and 0 < size <= SOURCE_CAP
            and _hex(digest, 64),
            "INPUT",
        )
        frozen.append((role, path, size, digest))
    _require(_hex(launcher, 64), "INPUT")
    return tuple(frozen), launcher


def _input(state, slots, measured, nonce):
    _require(type(slots) is tuple and 0 < len(slots) <= len(CASES), "INPUT")
    declared = _measured(measured)
    _require(_hex(nonce, 32), "INPUT")
    private = state.group[7]
    _require(_str_keys(private), "INPUT")
    items = []
    for key in private:
        value = private[key]
        _require(key in WHITELIST and type(value) is bytes, "INPUT")
        items.append((key, value))
    state.private = tuple(items)
    return declared


def _caps(state):
    total = 0
    for key, value in state.private:
        size = len(value)
        _require(size <= FILE_CAPS[key.split("/", 1)[1]], "CAP")
        total += size
    _require(total <= PRIVATE_CAP, "CAP")


def _keep(state, slots):
    keep = state.group[1]
    _require(type(keep) is list and len(keep) == len(slots), "KEEP")
    for index in range(len(slots)):
        _require(keep[index] is slots[index], "KEEP")
    state.slots = slots


# -- 5-7. slot, shape, record ---------------------------------------------------------------------


def _slot(state, slot):
    """Genuine class and sticky terminal latches only; refs are not read here."""
    _require(type(slot) is state.bound[0][1], "SLOT")
    status, outcome = _attr(slot, "state"), _attr(slot, "outcome")
    reserved, tree = _attr(slot, "run_reserved"), _attr(slot, "tree")
    failure, control = _attr(slot, "failure"), _attr(slot, "control")
    _require(_enum(status, (READY,)) and _enum(outcome, (READY,)), "SLOT")
    _require(reserved is True and failure is None and control is None, "SLOT")
    _require(type(tree) is bool, "SLOT")
    row = _Row()
    row.slot, row.tree, row.outcome = slot, tree, outcome
    return row


def _facts_domain(facts):
    reason = facts["reason"]
    _require(_optional(reason, lambda value: _enum(value, FACT_REASONS)), "SHAPE")
    for name in ("terminated", "overflow", "signaled", "eof"):
        _require(type(facts[name]) is bool, "SHAPE")
    for name in ("exit_code", "total_processes"):
        _require(_optional(facts[name], lambda value: _uint(value, UINT32)), "SHAPE")
    _require(_uint(facts["turns"], UINT32), "SHAPE")
    return tuple((name, facts[name]) for name in FACT_FIELDS if name not in ("held", "retained"))


def _shape(state, row):
    slot, group = row.slot, state.group
    legacy, lifecycle, host = group[2], group[3], group[5]
    refs = _attr(slot, "refs")
    _require(type(refs) is state.bound[1][1], "SHAPE")
    fields = tuple((name, _attr(refs, name)) for name in REFS_FIELDS)
    entries, context_type = fields[0][1], fields[4][1]
    case, facts = _attr(slot, "case"), _attr(slot, "facts")
    _require(type(entries) is tuple and len(entries) == ENTRIES, "SHAPE")
    for entry in entries:
        _require(type(entry) is tuple and len(entry) == 3, "SHAPE")
        mapping, name = entry[0], entry[1]
        _require(type(name) is str and 0 < len(name) <= KEY_CHARS, "SHAPE")
        known = (legacy, lifecycle, host, case, facts)
        _require(any(mapping is item for item in known), "SHAPE")
    _require(context_type is state.context_type, "SHAPE")
    ctx = _attr(slot, "ctx")
    _require(type(ctx) is context_type, "SHAPE")
    row.ctx = tuple((name, _attr(ctx, name)) for name in CTX_BINDINGS)
    meta = _attr(slot, "meta")
    _require(type(meta) is tuple and len(meta) == META_ITEMS, "SHAPE")
    kinds = (str, int, str, str, int, int, float, tuple)
    _require(all(type(meta[index]) is kinds[index] for index in range(META_ITEMS)), "SHAPE")
    _require(len(meta[7]) == len(CASE_FIELDS), "SHAPE")
    _require(all(type(name) is str for name in meta[7]), "SHAPE")
    # A profile domains (types already exact): limits and a finite start
    _require(meta[4] == READ_LIMIT and meta[5] == AUDIT_LIMIT, "SHAPE")
    _require(math.isfinite(meta[6]), "SHAPE")
    for index, name in GROUP_INDEX:
        _require(_attr(slot, name) is group[index], "SHAPE")
    _require(_keyed(case, len(CASE_FIELDS), CASE_FIELDS), "SHAPE")
    _require(_keyed(facts, len(FACT_FIELDS), FACT_FIELDS), "SHAPE")
    record = _attr(slot, "record")
    _require(_keyed(record, len(CASE_KEYS), CASE_KEYS), "SHAPE")
    expected = (meta[0], meta[2], meta[4], meta[5], meta[6])
    scalars = tuple((name, case[name]) for name in CASE_META)
    _require(all(_same(scalars[i][1], expected[i]) for i in range(len(CASE_META))), "SHAPE")
    row.case_meta = (scalars, case["directory"])  # original directory object, by identity
    row.refs = tuple((name, _attr(slot, name)) for name in SLOT_REFS)
    row.fields, row.entries, row.meta = fields, entries, meta
    row.facts = _facts_domain(facts)


def _distinct(rows):
    for name in DISTINCT:
        values = [dict(row.refs)[name] for row in rows]
        for first in range(len(values)):
            for second in range(first + 1, len(values)):
                _require(values[first] is not values[second], "SHAPE")


def _seconds(value):
    if value is None:
        return True
    return (
        type(value) is float
        and math.isfinite(value)
        and value >= 0.0
        and len(repr(value)) <= FLOAT_CHARS
    )


def _record(row):
    """Exact scalar domains of the 13 record fields, then a typed snapshot."""
    record = dict(row.refs)["record"]
    values = {name: record[name] for name in CASE_KEYS}
    _require(
        _enum(values["case"], CASES)
        and _enum(values["outcome"], ("APPROVED", "REJECTED"))
        and _optional(values["rejection"], lambda value: _enum(value, REJECTIONS))
        and _optional(values["exit_code"], lambda value: _uint(value, UINT32))
        and _optional(values["framing"], lambda value: _enum(value, ("LF", "CRLF")))
        and _optional(values["total_processes"], lambda value: _uint(value, UINT32))
        and type(values["terminated"]) is bool
        and all(
            _optional(values[name], lambda value: type(value) is bool)
            for name in ("ready", "inner_closed", "audit_integral")
        )
        and all(
            _optional(values[name], lambda value: _uint(value, AUDIT_CAP + 1))
            for name in ("audit_entries", "terminate_calls")
        )
        and _seconds(values["seconds"]),
        "RECORD",
    )
    row.record = tuple((name, values[name]) for name in CASE_KEYS)


# -- 8-10. prefix, artifacts, release -------------------------------------------------------------


def _prefix(rows):
    k = len(rows)
    for index in range(k):
        row = rows[index]
        meta, record = row.meta, dict(row.record)
        _require(
            _same(meta[0], CASES[index])
            and _same(meta[1], index + 1)
            and _same(meta[2], PREFIXES[index])
            and _same(record["case"], CASES[index]),
            "PREFIX",
        )
        outcome = record["outcome"]
        if index < k - 1:
            _require(outcome == "APPROVED", "PREFIX")
        else:
            _require(outcome == "REJECTED" or k == len(CASES), "PREFIX")
    return k


def _artifacts(state, k):
    expected = {PREFIXES[index] + leaf for index in range(k) for leaf in CASE_FILES[index]}
    _require({key for key, _value in state.private} == expected, "ARTIFACTS")


def _release(state, rows):
    registry = state.group[6]
    _require(len(registry) == 0, "RELEASE")  # before any helper or list traversal
    for row in rows:
        refs, slot = dict(row.refs), row.slot
        originals = {
            "owner": refs["owner"],
            "case": refs["case"],
            "legacy": state.group[2],
            "reconcile": state.group[4],
            "facts": refs["facts"],
            "retained": refs["retained"],
            "registry": registry,
            "ledger": refs["ledger"],
            "clock": refs["clock"],
            "host": state.group[5],
        }
        _require(all(value is originals[name] for name, value in row.ctx), "RELEASE")
        case, facts, ledger, owner = refs["case"], refs["facts"], refs["ledger"], refs["owner"]
        _require(type(ledger) is dict and len(ledger) == 0, "RELEASE")
        _require(case["lifecycle_reserved"] is True, "RELEASE")
        flag = case["reconcile_reserved"]
        _require(type(flag) is bool and flag is row.tree, "RELEASE")
        retained = facts["retained"]
        _require(facts["held"] is None and retained is refs["retained"], "RELEASE")
        _require(type(retained) is bytearray and len(retained) <= RETAINED_CAP, "RELEASE")
        _require(_attr(owner, "ledger") is ledger, "RELEASE")
        _require(_enum(_attr(owner, "state"), ("CLOSED",)), "RELEASE")
        row.retained = (len(retained), bytes(retained))
    state.rows = tuple(rows)


# -- 11-12. global guard and trusted read helpers ----------------------------------------------


def _row_stable(state, row):
    slot = row.slot
    if type(slot) is not state.bound[0][1]:
        return False
    if not (
        _enum(slot.state, (READY,))
        and _enum(slot.outcome, (READY,))
        and slot.run_reserved is True
        and slot.failure is None
        and slot.control is None
        and slot.tree is row.tree
    ):
        return False
    refs = dict(row.refs)
    for name, value in row.refs:
        if getattr(slot, name) is not value:
            return False
    for index, name in GROUP_INDEX:
        if getattr(slot, name) is not state.group[index]:
            return False
    slot_refs = refs["refs"]
    if not all(getattr(slot_refs, name) is value for name, value in row.fields):
        return False
    if slot_refs.context_type is not state.context_type:
        return False
    ctx = refs["ctx"]
    if not all(getattr(ctx, name) is value for name, value in row.ctx):
        return False
    case, facts, record = refs["case"], refs["facts"], refs["record"]
    if not _keyed(case, len(CASE_FIELDS), CASE_FIELDS):
        return False
    if case["lifecycle_reserved"] is not True or case["reconcile_reserved"] is not row.tree:
        return False
    scalars, directory = row.case_meta
    if not all(_same(case[name], value) for name, value in scalars):
        return False
    if case["directory"] is not directory:
        return False
    if not _keyed(facts, len(FACT_FIELDS), FACT_FIELDS):
        return False
    # original pointers named by the captured entries, over the 5 known maps
    # whose key domains were just rechecked (namespaces in _stable, case/facts)
    if not all(mapping.get(name) is value for mapping, name, value in row.entries):
        return False
    if facts["held"] is not None or facts["retained"] is not refs["retained"]:
        return False
    if not all(_same(facts[name], value) for name, value in row.facts):
        return False
    retained = refs["retained"]
    if type(retained) is not bytearray or len(retained) != row.retained[0]:
        return False
    if bytes(retained) != row.retained[1]:
        return False
    if not _keyed(record, len(CASE_KEYS), CASE_KEYS):
        return False
    if not all(_same(record[name], value) for name, value in row.record):
        return False
    owner, ledger = refs["owner"], refs["ledger"]
    if not _enum(owner.state, ("CLOSED",)) or owner.ledger is not ledger:
        return False
    return type(ledger) is dict and len(ledger) == 0


def _stable(state):
    """Bounded fingerprint of the group and of ALL selected slots; no helper calls."""
    try:
        case_ns, keep, legacy, lifecycle, _reconcile, host, registry, private = state.group
        if not _namespace(case_ns, CALLER_KEYS):
            return False
        if not all(_namespace(item, SOURCE_KEYS) for item in (legacy, lifecycle, host)):
            return False
        if _lengths(state.group) != state.lengths:
            return False
        if not all(case_ns.get(name) is value for name, value in state.bound):
            return False
        if legacy.get("_LIVE") is not registry:
            return False
        if lifecycle.get("_Context") is not state.context_type:
            return False
        if type(keep) is not list or len(keep) != len(state.slots):
            return False
        if not all(keep[index] is state.slots[index] for index in range(len(state.slots))):
            return False
        if type(registry) is not list or len(registry) != 0:
            return False
        if type(private) is not dict or len(private) != len(state.private):
            return False
        if not _str_keys(private):
            return False
        if not all(private.get(key) is value for key, value in state.private):
            return False
        return all(_row_stable(state, row) for row in state.rows)
    except Exception:
        return False


def _helper(state, function, values, reason):
    """Global pre-guard, one trusted read helper, global post-guard first.
    Controls propagate immediately as the same object, without a post-guard."""
    _require(_stable(state), "DRIFT")
    failed, result = False, None
    try:
        result = function(*values)
    except Exception:
        failed = True
    _require(_stable(state), "DRIFT")
    _require(not failed and type(result) is bool, "INTERNAL")
    _require(result, reason)


def _helpers(state):
    bound = dict(state.bound)
    for row in state.rows:
        slot, record = row.slot, dict(row.refs)["record"]
        _helper(state, bound["_intact"], (slot,), "DRIFT")
        _helper(state, bound["_released"], (slot,), "RELEASE")
        _helper(state, bound["_record"], (slot, record), "RECORD")


# -- 13. encode from snapshots only ---------------------------------------------------------------


def _encoded(value):
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return text.encode("ascii") + b"\n"


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _descriptor(name, raw):
    return {"name": name, "bytes": len(raw), "sha256": _sha(raw)}


def _not_run(name):
    record = dict.fromkeys(CASE_KEYS)
    record.update(case=name, outcome="NOT_RUN")
    return record


def _encode(state, declared, nonce):
    rows, k = state.rows, len(state.rows)
    records = [dict(row.record) for row in rows]
    approved = k == len(CASES) and all(record["outcome"] == "APPROVED" for record in records)
    outcome = "APPROVED" if approved else "REJECTED"
    summary = {
        "kind": SUMMARY_KIND,
        "nonce": nonce,
        "outcome": outcome,
        "scope": "BENIGN_CONTROL_ONLY",
        "admission_3s": "NOT_MEASURED",
        "cases": records + [_not_run(name) for name in CASES[k:]],
    }
    summary.update(PINS)
    summary_raw = _encoded(summary)
    private = dict(state.private)
    transport = {
        "kind": TRANSPORT_KIND,
        "nonce": nonce,
        "outcome": outcome,
        "summary": _descriptor("summary.json", summary_raw),
        "private": [_descriptor(name, raw) for name, raw in sorted(state.private)],
    }
    transport_raw = _encoded(transport)
    metadata, cases = {}, []
    for index in range(k):
        row = rows[index]
        raw = _encoded(
            {
                "kind": CASE_KIND,
                "number": row.meta[1],
                "case": row.meta[0],
                "slot_outcome": row.outcome,
                "lifecycle_reserved": True,
                "reconcile_reserved": row.tree,
                "tree_latched": row.tree,
                "owner_released": True,
            }
        )
        metadata[META_NAMES[index]] = raw
        case = _descriptor(META_NAMES[index], raw)
        case["number"] = index + 1
        cases.append(case)
    rows_declared, launcher = declared
    manifest = {
        "kind": MANIFEST_KIND,
        "nonce": nonce,
        "executed": k,
        "summary": _descriptor("summary.json", summary_raw),
        "transport": _descriptor("transport.json", transport_raw),
        "cases": cases,
        "sources": [
            {"role": role, "path": path, "bytes": size, "sha256": digest}
            for role, path, size, digest in rows_declared
        ],
        "launcher": {"sha256": launcher},
    }
    manifest_raw = _encoded(manifest)
    _require(len(summary_raw) <= SUMMARY_CAP and len(transport_raw) <= TRANSPORT_CAP, "SIZE")
    _require(len(manifest_raw) <= MANIFEST_CAP, "SIZE")
    _require(all(len(raw) <= METADATA_CAP for raw in metadata.values()), "SIZE")
    return (manifest_raw, summary_raw, transport_raw, private, metadata)


# -- entry --------------------------------------------------------------------------------------


def _build(group, slots, measured, nonce):
    state = _group(group)
    declared = _input(state, slots, measured, nonce)
    _caps(state)
    _keep(state, slots)
    rows = [_slot(state, slot) for slot in slots]
    for row in rows:
        _shape(state, row)
    _distinct(rows)
    for row in rows:
        _record(row)
    k = _prefix(rows)
    _artifacts(state, k)
    _release(state, rows)
    _helpers(state)
    evidence = _encode(state, declared, nonce)
    _require(_stable(state), "DRIFT")  # final global guard after assembly
    return evidence


def bundle(group, slots, measured, nonce):
    """Closed pair of exact str and evidence. Controls propagate unchanged."""
    reason = "INTERNAL"
    try:
        return ("BUNDLE_READY", _build(group, slots, measured, nonce))
    except _Refuse as refusal:
        reason = refusal.reason
    except Exception:
        reason = "INTERNAL"
    return ("BUNDLE_REFUSED", reason)
