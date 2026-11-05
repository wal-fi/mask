"""Private protected case caller V2. Import defines only.

No __main__, no CLI, no loader and no producer: nothing here reads a source,
builds an owner, creates a directory, writes an invocation or chooses a
nonce. A trusted producer allocates a slot (rooted in KEEP), builds and
registers the owner in the ORIGINAL runner list, builds the case and its
invocation, and keeps its own references until it observes the latch.

- prepare(slot, sources, owner, case) latches the raw references inside one
  protected body, then checks exact shapes and captures the original
  namespaces, hooks, transitive _finish references, registry, ledger and
  case facts. sources is (runner globals, lifecycle globals, reconcile).
- run(slot, artifacts) is one-shot: it binds the returned ctx (kept in the
  slot before any inspection), delegates once to the accepted lifecycle,
  proves CLOSED/released, latches TREE, calls the captured legacy _finish
  and re-checks everything afterwards.

The first terminal outcome, the first delivered ordinary failure and the
first control are sticky; reentry refusals are returned only. Controls
propagate as the same object. There are NO calls to the legacy cleanup
_case/_contain/_held/_release and no extra close: only the lifecycle
releases, from the original list. The local _held is a classifier that only
inspects a closed error; it never cleans up.
READY_FOR_VALIDATION means a record exists for the mandatory later core
verify; no label is permission to exit or publish. Guards check identity
and shape of source-pinned trusted collaborators, a precondition, not
authentication or containment of privileged Python. No native guarantee.
"""

from math import isfinite
from pathlib import Path
from types import FunctionType, MethodType

CASES = ("NORMAL", "TERMINATE", "LAST_CLOSE")
PREFIXES = ("case-1/", "case-2/", "case-3/")
PATH = type(Path())
READ_LIMIT = 4096  # backend MAX_READ
AUDIT_LIMIT = 512  # adapter AUDIT_LIMIT
DIRECTORY_CHARS = 512
CASE_FIELDS = tuple(
    sorted(
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
)
FACT_FIELDS = tuple(
    sorted(
        (
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
    )
)
LEGACY_FUNCTIONS = (
    "_finish",
    "_capture",
    "_verdict",
    "_persist",
    "_step",
    "_check",
    "_fields",
    "_framing",
    "_int",
    "_state",
)
LEGACY_VALUES = (
    ("RunError", type),
    ("CODES", frozenset),
    ("REJECTIONS", frozenset),
    ("TERMINATE_NAMES", tuple),
    ("CASE_KEYS", tuple),
    ("NORMAL_LINE", str),
    ("READY_LINE", str),
    ("_LIVE", list),
)
HOST_HOOKS = ("_attempt", "_supervise")
HOST_SEAMS = ("write_new", "encoded", "_monotonic")
LIFECYCLE_FUNCTIONS = ("context", "lifecycle")
LIFECYCLE_TYPES = ("ContextRefused", "_Context")
FILE_CAPS = {
    "invocation.json": 4096,
    "supervision.json": 4096,
    "local-stdout.bin": 1024,
    "snapshot.json": 4096,
    "audit.json": 65536,
}
NEW_FILES = {
    "NORMAL": ("supervision.json", "local-stdout.bin"),
    "TERMINATE": ("supervision.json", "local-stdout.bin"),
    "LAST_CLOSE": ("supervision.json", "local-stdout.bin", "snapshot.json", "audit.json"),
}
WHITELIST = frozenset(
    prefix + name
    for prefix, case in zip(PREFIXES, CASES, strict=True)
    for name in ("invocation.json", *NEW_FILES[case])
)
MAX_ARTIFACTS = 11
LAST_KEYS = ("inner_closed", "audit_integral", "audit_entries", "terminate_calls")
TREE_REJECTIONS = {
    "NORMAL": frozenset(("TREE_UNPROVEN",)),
    "TERMINATE": frozenset(("TREE_UNPROVEN",)),
    "LAST_CLOSE": frozenset(("AUDIT_INVALID", "FAILED_LAST_CLOSE", "TREE_UNPROVEN")),
}
PREPARED = "PREPARED"
REFUSED = "PREPARE_REFUSED"
READY = "READY_FOR_VALIDATION"
# Strong references, never removed: every allocated slot.
KEEP = []


class _Slot:
    __slots__ = (
        "state",
        "outcome",
        "owner",
        "case",
        "sources",
        "legacy",
        "lifecycle",
        "reconcile",
        "host",
        "registry",
        "clock",
        "facts",
        "retained",
        "ledger",
        "refs",
        "meta",
        "ctx",
        "run_reserved",
        "tree",
        "failure",
        "control",
        "record",
        "artifacts",
    )

    def __init__(self):
        for name in self.__slots__:
            setattr(self, name, None)
        self.state = "EMPTY"
        self.run_reserved = False


class _Refs:
    """Captured originals: (mapping, name, value) entries plus direct handles."""

    __slots__ = (
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


def allocate():
    """Pure: a fresh EMPTY slot, rooted in KEEP before it is returned."""
    slot = _Slot()
    KEEP.append(slot)
    return slot


# -- small exact primitives --------------------------------------------------------------


def _str_keys(mapping):
    """Exact dict whose keys are all exact str, by iteration before any lookup."""
    if type(mapping) is not dict:
        return False
    for key in mapping:
        if type(key) is not str:
            return False
    return True


def _is(value, expected):
    return type(value) is str and value == expected


def _lookup(cls, name):
    """The class attribute found by the MRO, read without descriptors."""
    for klass in cls.__mro__:
        entry = vars(klass).get(name)
        if entry is not None:
            return entry
    return None


def _bound(method, target, function):
    return type(method) is MethodType and method.__self__ is target and method.__func__ is function


def _function_of(namespace, name):
    value = namespace.get(name)
    return value if type(value) is FunctionType and value.__globals__ is namespace else None


def _held(refs, error):
    """The captured RunError carrying exactly CONTROL_HELD."""
    if type(error) is not refs.run_error:
        return False
    args = BaseException.args.__get__(error)
    return type(args) is tuple and len(args) == 1 and _is(args[0], "CONTROL_HELD")


def _fail(slot, error):
    if slot.failure is None:
        slot.failure = error


def _control(slot, error):
    if slot.control is None:
        slot.control = error
    if slot.outcome is None:
        slot.outcome = "INTERRUPTED"
        slot.state = "INTERRUPTED"


def _terminal(slot, label):
    if slot.outcome is None:
        slot.outcome = label
        slot.state = label
    return label


# -- prepare -------------------------------------------------------------------------------


def _meta(case):
    """Immutable exact scalars of the case, or None; keys already exact str."""
    name, prefix, directory = case.get("name"), case.get("prefix"), case.get("directory")
    read, audit, start = case.get("read_limit"), case.get("audit_limit"), case.get("start")
    if not (
        type(name) is str
        and type(prefix) is str
        and type(directory) is PATH
        and type(read) is int
        and type(audit) is int
        and type(start) is float
    ):
        return None
    number = PREFIXES.index(prefix) + 1 if prefix in PREFIXES else 0
    return (name, number, prefix, str(directory), read, audit, start, tuple(sorted(case)))


def _facts_initial(facts):
    if not _str_keys(facts) or tuple(sorted(facts)) != FACT_FIELDS:
        return False
    if not all(facts[key] is None for key in ("reason", "held", "exit_code", "total_processes")):
        return False
    if not all(facts[key] is False for key in ("terminated", "overflow", "signaled", "eof")):
        return False
    turns, retained = facts["turns"], facts["retained"]
    return type(turns) is int and turns == 0 and type(retained) is bytearray and len(retained) == 0


def _case_shape(case):
    """(meta, host, clock, now function) for an exact canonical case, or None."""
    if not _str_keys(case) or tuple(sorted(case)) != CASE_FIELDS:
        return None
    meta = _meta(case)
    if meta is None:
        return None
    name, number, prefix, text, read, audit, start, _keys = meta
    directory, since, error = case["directory"], case["since"], case["error"]
    if not (
        name in CASES
        and number > 0
        and CASES[number - 1] == name
        and len(text) <= DIRECTORY_CHARS
        and directory.name == "case-" + str(number)
        and read == READ_LIMIT
        and audit == AUDIT_LIMIT
        and isfinite(start)
        and type(since) is float
        and since == start
        and type(error) is type
        and issubclass(error, Exception)
        and _facts_initial(case["facts"])
    ):
        return None
    if not all(case[key] is False for key in ("ready", "inner_closed", "contained", "recorded")):
        return None
    if not all(case[key] is False for key in ("lifecycle_reserved", "reconcile_reserved")):
        return None
    turns = case["ready_turns"]
    if not (type(turns) is int and turns == 0):
        return None
    if case["snapshot"] is not None or case["seconds"] is not None:
        return None
    host, clock = case["host"], case["clock"]
    if not _str_keys(host):
        return None
    now = _lookup(type(clock), "now")
    if type(now) is not FunctionType or not _bound(clock.now, clock, now):
        return None
    return meta, host, clock, now


def _capture(slot):
    """Every original reference, or None; no owner method is called."""
    sources = slot.sources
    if type(sources) is not tuple or len(sources) != 3:
        return None
    legacy, lifecycle, reconcile = sources[0], sources[1], sources[2]
    if not (_str_keys(legacy) and _str_keys(lifecycle) and type(reconcile) is FunctionType):
        return None
    owner, case = slot.owner, slot.case
    refs, entries = _Refs(), []
    for name in LEGACY_FUNCTIONS:
        value = _function_of(legacy, name)
        if value is None:
            return None
        entries.append((legacy, name, value))
    for name, kind in LEGACY_VALUES:
        value = legacy.get(name)
        if type(value) is not kind:
            return None
        entries.append((legacy, name, value))
    run_error, case_keys, registry = legacy["RunError"], legacy["CASE_KEYS"], legacy["_LIVE"]
    if not issubclass(run_error, Exception) or not all(type(key) is str for key in case_keys):
        return None
    if not any(item is owner for item in registry):
        return None  # the list is never touched
    for name in LIFECYCLE_FUNCTIONS:
        value = _function_of(lifecycle, name)
        if value is None:
            return None
        entries.append((lifecycle, name, value))
    for name in LIFECYCLE_TYPES:
        value = lifecycle.get(name)
        if type(value) is not type:
            return None
        entries.append((lifecycle, name, value))
    shape = _case_shape(case)
    if shape is None:
        return None
    meta, host, clock, now = shape
    for name in HOST_HOOKS:
        value = _function_of(host, name)
        if value is None:
            return None
        entries.append((host, name, value))
    for name in HOST_SEAMS:
        value = host.get(name)
        if type(value) is not FunctionType:
            return None
        entries.append((host, name, value))
    deadline = host.get("DEADLINE_SECONDS")
    if type(deadline) is not float:
        return None
    entries.append((host, "DEADLINE_SECONDS", deadline))
    name, facts = meta[0], case["facts"]
    state, ledger = owner.state, owner.ledger
    if not (_is(state, "NEW") and _str_keys(ledger) and len(ledger) == 0):
        return None
    inner = _lookup(type(owner), "close_inner")
    if (type(inner) is FunctionType) is not (name == "LAST_CLOSE"):
        return None
    for key in ("facts", "host", "clock", "error", "name"):
        entries.append((case, key, case[key]))
    retained = facts["retained"]
    entries.append((facts, "retained", retained))
    refs.entries, refs.now, refs.case_keys = tuple(entries), now, case_keys
    refs.run_error, refs.finish, refs.state = run_error, legacy["_finish"], legacy["_state"]
    refs.refused, refs.context_type = lifecycle["ContextRefused"], lifecycle["_Context"]
    refs.context, refs.lifecycle = lifecycle["context"], lifecycle["lifecycle"]
    values = (legacy, lifecycle, reconcile, registry, host, clock, facts, retained, ledger)
    return refs, values, meta


def prepare(slot, sources, owner, case):
    """PREPARED, a closed refusal, or a latched control re-raised unchanged."""
    if not (
        type(slot) is _Slot
        and _is(slot.state, "EMPTY")
        and slot.owner is None
        and slot.outcome is None
        and slot.run_reserved is False
    ):
        return "REFUSED_SLOT"
    label = REFUSED
    try:
        slot.owner = owner
        slot.case = case
        slot.sources = sources
        slot.state = "PREPARING"
        captured = _capture(slot)
        if captured is not None:
            refs, values, meta = captured
            (
                slot.legacy,
                slot.lifecycle,
                slot.reconcile,
                slot.registry,
                slot.host,
                slot.clock,
                slot.facts,
                slot.retained,
                slot.ledger,
            ) = values
            slot.refs, slot.meta = refs, meta
            slot.state = PREPARED
            label = PREPARED
    except Exception as error:
        _fail(slot, error)
        label = REFUSED
    except BaseException as error:
        _control(slot, error)
        raise
    if label == PREPARED:
        return label
    return _terminal(slot, label)


# -- guards and proofs -----------------------------------------------------------------------


def _intact(slot):
    """Captured identities, exact key domains and the immutable meta snapshot."""
    try:
        for mapping in (slot.legacy, slot.lifecycle, slot.host, slot.case, slot.facts):
            if not _str_keys(mapping):
                return False
        refs = slot.refs
        for mapping, name, value in refs.entries:
            if mapping.get(name) is not value:
                return False
        if not _bound(slot.clock.now, slot.clock, refs.now):
            return False
        if slot.owner.ledger is not slot.ledger:
            return False
        return _meta(slot.case) == slot.meta
    except Exception:
        return False


def _present(slot):
    """Phase membership in the ORIGINAL list, separate from identity guards."""
    owner = slot.owner
    return any(item is owner for item in slot.registry)


def _closed(slot):
    state = slot.refs.state(slot.owner)
    return _is(state, "CLOSED")


def _bound_ctx(slot):
    """The ctx returned for THIS slot's originals, before the lifecycle."""
    try:
        ctx = slot.ctx
        if type(ctx) is not slot.refs.context_type:
            return False
        pairs = (
            (ctx.owner, slot.owner),
            (ctx.case, slot.case),
            (ctx.legacy, slot.legacy),
            (ctx.reconcile, slot.reconcile),
            (ctx.facts, slot.facts),
            (ctx.retained, slot.retained),
            (ctx.registry, slot.registry),
            (ctx.ledger, slot.ledger),
            (ctx.clock, slot.clock),
            (ctx.host, slot.host),
        )
        return all(current is original for current, original in pairs)
    except Exception:
        return False


def _released(slot):
    """CLOSED, original ledger empty, owner absent; flags and facts exact."""
    try:
        case, facts, ledger = slot.case, slot.facts, slot.ledger
        return (
            not _present(slot)
            and case["lifecycle_reserved"] is True
            and type(case["reconcile_reserved"]) is bool
            and _closed(slot)
            and slot.owner.ledger is ledger
            and len(ledger) == 0
            and facts["held"] is None
            and facts["retained"] is slot.retained
            and _bound_ctx(slot)
        )
    except Exception:
        return False


def _artifacts(slot, artifacts):
    """Snapshot of (key, bytes object) before the finish, or None."""
    if not _str_keys(artifacts) or len(artifacts) > MAX_ARTIFACTS:
        return None
    prefix = slot.meta[2]
    invocation = prefix + "invocation.json"
    items, found = [], False
    for key in artifacts:
        value = artifacts[key]
        if key not in WHITELIST or type(value) is not bytes:
            return None
        if len(value) > FILE_CAPS[key.split("/", 1)[1]]:
            return None
        if key == invocation:
            found = True
        elif key.startswith(prefix):
            return None
        items.append((key, value))
    return tuple(items) if found else None


def _new_artifacts(slot, before):
    artifacts = slot.artifacts
    if not _str_keys(artifacts):
        return False
    for key, value in before:
        if artifacts.get(key) is not value:
            return False
    prefix = slot.meta[2]
    expected = [prefix + name for name in NEW_FILES[slot.meta[0]]]
    if len(artifacts) != len(before) + len(expected):
        return False
    for key in expected:
        value = artifacts.get(key)
        if type(value) is not bytes or len(value) > FILE_CAPS[key.split("/", 1)[1]]:
            return False
    return True


def _record(slot, record):
    """Closed shape and coherence; the precedence stays with the core verify."""
    if not _str_keys(record):
        return False
    keys = slot.refs.case_keys
    if len(record) != len(keys) or not all(key in record for key in keys):
        return False
    name = slot.meta[0]
    outcome, rejection, ready = record["outcome"], record["rejection"], record["ready"]
    if not _is(record["case"], name):
        return False
    if type(outcome) is not str or outcome not in ("APPROVED", "REJECTED"):
        return False
    if rejection is not None and type(rejection) is not str:
        return False
    if (outcome == "APPROVED") is not (rejection is None):
        return False
    if (ready is None) is not (name == "NORMAL"):
        return False
    if name != "LAST_CLOSE" and not all(record[key] is None for key in LAST_KEYS):
        return False
    if slot.tree is True:
        return outcome == "REJECTED" and rejection in TREE_REJECTIONS[name]
    return True


def _finished(slot, before, record):
    """Fresh checks after the finish: nothing drifted, nothing reopened."""
    try:
        if not _intact(slot):
            return False  # exact key domains before any lookup below
        case, facts, ledger = slot.case, slot.facts, slot.ledger
        flag = case["reconcile_reserved"]
        return (
            not _present(slot)
            and _closed(slot)
            and slot.owner.ledger is ledger
            and len(ledger) == 0
            and case["lifecycle_reserved"] is True
            and type(flag) is bool
            and flag is slot.tree
            and facts["held"] is None
            and _new_artifacts(slot, before)
            and _record(slot, record)
        )
    except Exception:
        return False


# -- run -------------------------------------------------------------------------------------


def _context_label(slot, error):
    if type(error) is slot.refs.refused:
        return "RETAINED_CONTEXT_REFUSED"
    if _held(slot.refs, error):
        return "RETAINED_CONTEXT_HELD"
    return "RETAINED_INTERNAL"


def _lifecycle_label(slot, error):
    if error is slot.ctx.held_error:
        return "RETAINED_INTEGRITY"
    if _held(slot.refs, error):
        return "RETAINED_HELD"
    return "RETAINED_INTERNAL"


def _run(slot, artifacts):
    slot.artifacts = artifacts
    before = _artifacts(slot, artifacts)
    if before is None:
        return "RETAINED_ARTIFACTS"
    if not (_intact(slot) and _present(slot)):
        return "RETAINED_DRIFT"
    refs = slot.refs
    try:
        ctx = refs.context(slot.owner, slot.case, slot.legacy, slot.reconcile)
    except Exception as error:
        _fail(slot, error)
        return _context_label(slot, error)
    slot.ctx = ctx  # rooted before any inspection
    if not (_bound_ctx(slot) and _intact(slot) and _present(slot)):
        return "RETAINED_CONTEXT_INVALID"
    slot.state = "CONTEXT"
    slot.state = "LIFECYCLE"
    try:
        result = refs.lifecycle(ctx)
    except Exception as error:
        _fail(slot, error)
        return _lifecycle_label(slot, error)
    if result is not None:
        return "RETAINED_PROOF_FAILED"
    if not _intact(slot):
        return "RETAINED_DRIFT"  # reference drift has priority over the proof
    if not _released(slot):
        return "RETAINED_PROOF_FAILED"
    slot.state = "RELEASED_PROVEN"
    slot.tree = slot.case["reconcile_reserved"]  # exact bool, latched before the finish
    if not (_intact(slot) and not _present(slot)):
        return "RETAINED_DRIFT"
    slot.state = "FINISH"
    try:
        record = refs.finish(slot.owner, slot.case, artifacts)
    except Exception as error:
        _fail(slot, error)  # the error delivered by the trusted _finish
        return "RETAINED_FINISH_FAILED"
    if not _finished(slot, before, record):
        return "RETAINED_POST_FINISH_INVALID"
    slot.record = record
    return READY


def run(slot, artifacts):
    """One-shot. A closed label; a latched control is re-raised unchanged."""
    if type(slot) is not _Slot:
        return "REFUSED_SLOT"
    reserved, state = slot.run_reserved, slot.state
    if reserved is True:
        return "RETAINED_REUSED"
    if reserved is not False or not _is(state, PREPARED):
        return "RETAINED_NOT_PREPARED"
    slot.run_reserved = True  # before any callback: no retry, no second close
    slot.state = "RUN_RESERVED"
    try:
        label = _run(slot, artifacts)
    except Exception as error:
        _fail(slot, error)
        label = "RETAINED_INTERNAL"
    except BaseException as error:
        _control(slot, error)
        raise
    return _terminal(slot, label)
