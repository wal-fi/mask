"""Private, uninvoked entry for the evidence collection. Import defines only.

The only CLI surface: exactly one argument, a 32-hex nonce, which is a
freshness identifier and never a permission. Invoking this file, capturing
its sources or running its native helper are effects that still need their
own reviewed procedure, exact command and effective permissions.

It captures exactly three pinned public Python sources (the composition, the
collector policy and its Win32 backend), checks all three before any exec,
executes the received composition bytes into a namespace held before the
exec, and makes at most one composition call with a private api factory.
The factory captures the ORIGINAL record and policy ledgers before the lazy
native helper; a fixed seven-operation observation adapter captures the
ORIGINAL backend ledgers before delegating the first operation. An exit code
is returned only while every captured original is proven empty by identity
and exact type; anything retained, replaced, unreadable or uncaptured parks
in the foreground for good: no retry, no cleanup, no recovery, no timer, no
exit. A recorded reference is retention, not cleanup. The entry runner's own
registry does not cover these handles and is not used. Console controls
raise only during the call; console close, logoff, shutdown, an external
kill or a fatal interpreter fault are FAILED/UNKNOWN.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import time

REPO = Path(__file__).parents[2]  # lexical; resolved only in S1
SOURCES = (
    (
        "docs/poc/pg16_shell_native_control_collect_pinned.py",
        "37b098cf604099a8aa9e64c4a3569ce06c6fe389188eba9a2b46478b04a8285e",
        5373,
    ),
    (
        "docs/poc/pg16_shell_native_control_collect.py",
        "1972ec74d96f93d824dfe18da0e0288a7fc21b7f2997e28d5afe497b782c9f52",
        20571,
    ),
    (
        "docs/poc/pg16_shell_native_control_collect_win32.py",
        "ccb3f74af75be04bbe685bc195c84d17e0457efe15732ed6cdbe9f9f057c3b3a",
        22315,
    ),
)
NONCE_PATTERN = re.compile(r"[0-9a-f]{32}")
KIND = "MASKGW_PG16_NATIVE_COLLECT_ENTRY_V1"
EXIT_OUTCOMES = {0: "VERIFIED_APPROVED", 1: "VERIFIED_REJECTED", 2: "REFUSED", 5: "INTERRUPTED"}
PARK_REASONS = ("RETAINED", "UNKNOWN_CUSTODY", "INTERRUPTED", "INTERNAL")
OPERATIONS = (
    "create",
    "query_info",
    "query_file",
    "query_volume",
    "query_directory",
    "read",
    "close",
)
# Closed reasons the composition itself may return before the collector exists.
COMPOSITION_REASONS = (
    "COLLECT_SOURCE",
    "COLLECT_UNAVAILABLE",
    "COLLECT_POISONED",
    "COLLECT_ARGUMENT",
    "COLLECT_INTERNAL",
)
VERIFIED = ("VERIFIED_APPROVED", "VERIFIED_REJECTED")
HEX = frozenset("0123456789abcdef")
RESERVED = {"__name__": "_pg16_collect_entry_composition"}
PAUSE_SECONDS = 60.0
# Strong references, never removed: progress records, the namespace and every
# failure or control seen; the captured originals stay in the progress record.
KEEP = []
# "parked", "announced" and "attempted" are only ever set to True.
_STATE = {"active": False, "parked": False, "announced": False, "attempted": False}


# -- seams: module globals only, replaced only by tests -------------------------------


def _read_sources():
    """S1 only: bounded reads of exactly the three pinned public Python
    sources; None on any ordinary failure. No runtime, config or binary."""
    captured = []
    try:
        repo = REPO.resolve()
        for relative, _digest, size in SOURCES:
            path = repo / relative
            info = path.lstat()
            if not (
                stat.S_ISREG(info.st_mode)
                and not getattr(info, "st_file_attributes", 0) & 0x400
                and info.st_size == size
            ):
                return None
            with path.open("rb") as stream:
                raw = stream.read(size + 1)
            if len(raw) != size:
                return None
            captured.append(raw)
    except Exception:
        return None
    return tuple(captured)


def _argv0():
    """S1 only: the orchestrator's host["PYTHON"] form, derived from the
    repository path; never sys.executable, the current argv or the binary."""
    try:
        return str(Path(__file__).resolve().parents[2] / ".venv" / "Scripts" / "python.exe")
    except Exception:
        return None


def _execute(raw, namespace):
    exec(compile(raw, "<pinned-composition>", "exec"), namespace)


def _install(signum, handler):
    signal.signal(signum, handler)


def _pids():
    return os.getpid(), os.getppid()


def _pause(seconds):
    time.sleep(seconds)


def _native_api(namespace):
    """Prospective lazy native helper of the pinned backend namespace. Never
    invoked by tests; calling it is native activation needing its own review."""
    return namespace["_load_native"]()


# -- console controls and pipe events ------------------------------------------------


def _on_console(signum, frame):
    """Raises only during the single composition call; otherwise no effect."""
    if _STATE["active"]:
        raise KeyboardInterrupt


def _emit(record):
    line = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _announce(progress, fields):
    """At most one FINAL or PARKED event; a broken pipe changes nothing."""
    if _STATE["announced"]:
        return
    _STATE["announced"] = True
    nonce = progress["nonce"]
    try:
        _emit(
            {
                "kind": KIND,
                "nonce12": nonce[:12] if type(nonce) is str else None,
                "controller_pid": progress["pid"],
                **fields,
            }
        )
    except Exception:
        pass


def _final(progress, verdict):
    code = verdict[1]
    _announce(
        progress,
        {
            "event": "FINAL",
            "code": code,
            "outcome": EXIT_OUTCOMES[code],
            "reason": verdict[2],
            "summary_sha256": verdict[3],
            "transport_sha256": verdict[4],
        },
    )


def _refuse(nonce, refusal):
    """S0/S1 only: no namespace exists and nothing was executed."""
    _final({"nonce": nonce, "pid": None}, ("EXIT", 2, refusal, None, None))
    return 2


# -- progress, failures and the captured originals -----------------------------------


def _progress(nonce, argv0):
    progress = {
        "nonce": nonce,
        "argv0": argv0,
        "pid": None,
        "namespace": None,
        "attempts": None,
        "registered": False,
        "native_ns": None,
        "record": None,
        "collector": None,
        "active": None,
        "poison": None,
        "backend": None,
        "open": None,
        "retained": None,
        "factory_entered": False,
        "record_captured": False,
        "native_started": False,
        "op_entered": False,
        "backend_captured": False,
        "inspection_unknown": False,  # sticky: only ever set to True
        "entered": False,
        "uncertain": False,
        "loaded": False,
        "armed": False,
        "refusal": None,
        "fault": None,
        "control": None,
        "outcome": None,
        "decision": None,
    }
    KEEP.append(progress)
    return progress


def _fault(progress, error):
    """Never raises. The first ordinary failure and the first control are
    kept apart, written into the preallocated record before the fallible
    extra reference; tracebacks are kept as they are."""
    try:
        slot = "fault" if isinstance(error, Exception) else "control"
        if progress[slot] is None:
            progress[slot] = error
    except BaseException:
        pass
    try:
        KEEP.append(error)
    except BaseException:
        pass


def _capture_failed():
    raise OSError("collect entry capture refused") from None


def _capture_record(progress, native_ns):
    """Inside the factory, before the native helper: the original record,
    its collector namespace and the original _ACTIVE/_POISON lists."""
    attempts = progress["attempts"]
    if type(attempts) is not list or len(attempts) != 1:
        _capture_failed()
    record = attempts[0]
    if record.native is not native_ns:
        _capture_failed()
    collector = record.collector
    if type(collector) is not dict:
        _capture_failed()
    active, poison = collector.get("_ACTIVE"), collector.get("_POISON")
    if type(active) is not list or type(poison) is not list:
        _capture_failed()
    progress["record"], progress["collector"] = record, collector
    progress["active"], progress["poison"] = active, poison
    progress["record_captured"] = True


def _capture_backend(progress):
    """At the first operation, before delegating: the original backend and
    its _open/_retained containers, kept as they are (never copied)."""
    if not progress["record_captured"]:
        _capture_failed()
    backend = progress["record"].backend
    if backend is None:
        _capture_failed()
    opened, pending = backend._open, backend._retained
    if type(opened) is not dict or type(pending) is not list:
        _capture_failed()
    progress["backend"], progress["open"], progress["retained"] = backend, opened, pending
    progress["backend_captured"] = True


def _chain(progress):
    """The captured identity chain: every original is still the original
    object with its exact type. Emptiness is NOT checked here: the original
    containers are normally non-empty while operations run."""
    namespace, attempts = progress["namespace"], progress["attempts"]
    record, collector, native = progress["record"], progress["collector"], progress["native_ns"]
    active, poison = progress["active"], progress["poison"]
    if type(namespace) is not dict or type(attempts) is not list or type(native) is not dict:
        return False
    if namespace.get("_ATTEMPTS") is not attempts or len(attempts) != 1:
        return False
    if attempts[0] is not record or record.native is not native:
        return False
    if record.collector is not collector or type(collector) is not dict:
        return False
    if type(active) is not list or type(poison) is not list:
        return False
    if collector.get("_ACTIVE") is not active or collector.get("_POISON") is not poison:
        return False
    if progress["backend_captured"]:
        backend, opened, pending = progress["backend"], progress["open"], progress["retained"]
        if record.backend is not backend:
            return False
        if type(opened) is not dict or type(pending) is not list:
            return False
        if backend._open is not opened or backend._retained is not pending:
            return False
    return True


def _guard(progress):
    """The single structural guard, before every delegation: refuses once the
    chain is unknown, and latches that for good. Never adopts a later copy."""
    known = False
    try:
        known = progress["inspection_unknown"] is False and _chain(progress) is True
    except BaseException as error:
        _fault(progress, error)
        known = False
    if not known:
        progress["inspection_unknown"] = True
        _capture_failed()


class _Observed:
    """Fixed seven-operation observation adapter over the returned api. The
    constructor's attribute lookups delegate and capture nothing; the first
    operation latches, captures the original backend ledgers, then delegates."""

    __slots__ = ("_progress", "_api")

    def __init__(self, progress, api):
        self._progress, self._api = progress, api

    def _call(self, name, args):
        progress = self._progress
        try:
            progress["op_entered"] = True
            if not progress["backend_captured"]:
                _capture_backend(progress)
            _guard(progress)  # before EACH delegation, close included
            return getattr(self._api, name)(*args)
        except BaseException as error:
            _fault(progress, error)
            raise

    def create(self, *args):
        return self._call("create", args)

    def query_info(self, *args):
        return self._call("query_info", args)

    def query_file(self, *args):
        return self._call("query_file", args)

    def query_volume(self, *args):
        return self._call("query_volume", args)

    def query_directory(self, *args):
        return self._call("query_directory", args)

    def read(self, *args):
        return self._call("read", args)

    def close(self, *args):
        return self._call("close", args)


def _factory(progress):
    def factory(native_ns):
        progress["factory_entered"] = True  # latched before any inspection
        try:
            progress["native_ns"] = native_ns  # the original, before the native helper
            _capture_record(progress, native_ns)
            progress["native_started"] = True
            api = _native_api(native_ns)
            if api is None:
                return None
            return _Observed(progress, api)
        except BaseException as error:
            _fault(progress, error)
            raise

    return factory


# -- custody and decision -------------------------------------------------------------


def _inspect(progress):
    if progress["inspection_unknown"] is not False:
        return "UNKNOWN"  # sticky: a later readable or empty state never promotes
    namespace, attempts = progress["namespace"], progress["attempts"]
    if type(namespace) is not dict:
        return "UNKNOWN"
    if not progress["registered"]:
        # Only a pure failure before the registry existed: the namespace must
        # still hold exactly the reserved initial keys and values.
        if _STATE["attempted"] or progress["factory_entered"]:
            return "UNKNOWN"
        if set(namespace) != set(RESERVED):
            return "UNKNOWN"
        for key, value in RESERVED.items():
            held = namespace[key]
            if type(held) is not str or held != value:
                return "UNKNOWN"
        return "QUIESCENT"
    if type(attempts) is not list or namespace.get("_ATTEMPTS") is not attempts:
        return "UNKNOWN"
    if not progress["factory_entered"]:
        limit = 1 if _STATE["attempted"] else 0
        return "QUIESCENT" if len(attempts) <= limit else "UNKNOWN"
    if not progress["record_captured"]:
        return "UNKNOWN"
    if (progress["native_started"] or progress["op_entered"]) and not progress["backend_captured"]:
        return "UNKNOWN"  # a native attempt without a captured backend
    if _chain(progress) is not True:
        return "UNKNOWN"
    sizes = [len(progress["active"]), len(progress["poison"])]
    if progress["backend_captured"]:
        sizes += [len(progress["open"]), len(progress["retained"])]
    return "RETAINED" if any(size > 0 for size in sizes) else "QUIESCENT"


def _custody(progress):
    """QUIESCENT, RETAINED or UNKNOWN over the captured originals. Closed to
    every BaseException: the first control or failure is kept directly in the
    progress record, and any UNKNOWN latches inspection_unknown for good
    before it is returned."""
    verdict = "UNKNOWN"
    try:
        verdict = _inspect(progress)
    except BaseException as error:
        _fault(progress, error)
        verdict = "UNKNOWN"
    if verdict not in ("QUIESCENT", "RETAINED"):
        progress["inspection_unknown"] = True
        verdict = "UNKNOWN"
    return verdict


def _hash_ok(value):
    return type(value) is str and len(value) == 64 and set(value) <= HEX


def _reasons(progress):
    if progress["record_captured"]:
        reasons = progress["collector"].get("REASONS")
        return reasons if type(reasons) is frozenset else frozenset()
    return frozenset(COMPOSITION_REASONS)


def _verdict(progress, value):
    """Exact four-tuple with exact strings and a lawful pair; never 0/1 else."""
    malformed = ("EXIT", 2, "COLLECT_ENTRY_RESULT", None, None)
    if type(value) is not tuple or len(value) != 4:
        return malformed
    label, reason, summary, transport = value
    if type(label) is not str or type(reason) is not str:
        return malformed
    if label in VERIFIED and reason == "OK" and _hash_ok(summary) and _hash_ok(transport):
        return ("EXIT", 0 if label == "VERIFIED_APPROVED" else 1, "OK", summary, transport)
    lawful = reason != "OK" and reason in _reasons(progress)
    if label == "INVALID" and lawful and summary is None and transport is None:
        return ("EXIT", 2, reason, None, None)
    return malformed


def _decide(progress):
    if _STATE["parked"]:
        return ("PARK", "INTERNAL")
    custody = _custody(progress)
    if custody == "RETAINED":
        return ("PARK", "RETAINED")
    if custody != "QUIESCENT":
        return ("PARK", "UNKNOWN_CUSTODY")
    if not _STATE["attempted"]:
        refusal = progress["refusal"]
        if refusal is None:
            interrupted = progress["uncertain"] or progress["control"] is not None
            refusal = "COLLECT_ENTRY_INTERRUPTED" if interrupted else "COLLECT_ENTRY_INTERNAL"
        return ("EXIT", 2, refusal, None, None)
    outcome = progress["outcome"]
    if type(outcome) is not tuple or outcome[0] != "RETURNED" or progress["uncertain"]:
        return ("EXIT", 5, "INTERRUPTED", None, None)  # reserved: never retried
    return _verdict(progress, outcome[1])


def decide(progress):
    """Total and closed to every BaseException: any failure while deciding
    keeps the first control or fault, latches the inspection and parks."""
    try:
        return _decide(progress)
    except BaseException as error:
        _fault(progress, error)
        progress["inspection_unknown"] = True
        return ("PARK", "INTERNAL")


def _exit_shape(decision):
    """Fully normalized EXIT: exact types and a lawful code/reason/hash set."""
    if type(decision) is not tuple or len(decision) != 5:
        return False
    tag, code, reason, summary, transport = decision
    if type(tag) is not str or tag != "EXIT" or type(code) is not int or type(reason) is not str:
        return False
    if code in (0, 1):
        return reason == "OK" and _hash_ok(summary) and _hash_ok(transport)
    if code == 2:
        return reason != "OK" and summary is None and transport is None
    if code == 5:
        return reason == "INTERRUPTED" and summary is None and transport is None
    return False


def _same(decision, expected):
    """Element by element: exact type first, then equality of exact values."""
    return all(
        type(given) is type(wanted) and given == wanted
        for given, wanted in zip(decision, expected, strict=True)
    )


def _accepted(decision, progress):
    """A normalized EXIT equal to the decision recomputed now from the
    current validated outcome; a stale or forged decision never passes."""
    try:
        if _STATE["parked"] or not _exit_shape(decision):
            return False
        expected = decide(progress)
        return _exit_shape(expected) and _same(decision, expected)
    except BaseException as error:
        _fault(progress, error)
        progress["inspection_unknown"] = True
        return False


def _park(progress, reason):
    _STATE["parked"] = True  # sticky: never reset
    _announce(progress, {"event": "PARKED", "reason": reason})


def _park_reason(decision):
    try:
        if type(decision) is tuple and len(decision) == 2:
            tag, reason = decision
            if type(tag) is str and tag == "PARK" and type(reason) is str:
                return reason if reason in PARK_REASONS else "INTERNAL"
    except BaseException:
        pass
    return "INTERNAL"


def settle(decision, progress):
    """EXIT only for a normalized decision equal to the current one, while not
    parked and with every captured original proven empty right now;
    otherwise park, sticky. Never leaks an inspection failure or control."""
    if _accepted(decision, progress):
        return decision
    reason = _park_reason(decision)
    _park(progress, reason)
    return ("PARK", reason)


# -- S2-S5 forward pass -------------------------------------------------------------


def _register(progress):
    """After a healthy load: the original attempt list, exact and empty."""
    namespace = progress["namespace"]
    attempts = namespace.get("_ATTEMPTS")
    if type(attempts) is list and len(attempts) == 0 and callable(namespace.get("_collect_pinned")):
        progress["attempts"] = attempts
        progress["registered"] = True
    else:
        progress["refusal"] = "COLLECT_ENTRY_LOAD"


def _identity(pair):
    """The complete pid/parent pair: exact ints, 0 < value < 2**32, distinct."""
    if type(pair) is not tuple or len(pair) != 2:
        return None
    if not all(type(item) is int and 0 < item < (1 << 32) for item in pair):
        return None
    return pair if pair[0] != pair[1] else None


def _arm(progress):
    """Identity validated first, then the handlers, then the IDENTITY event."""
    pair = _identity(_pids())
    if pair is None:
        return False
    for name in ("SIGINT", "SIGBREAK"):
        _install(getattr(signal, name), _on_console)
    progress["pid"] = pair[0]
    _emit(
        {
            "kind": KIND,
            "event": "IDENTITY",
            "nonce12": progress["nonce"][:12],
            "controller_pid": pair[0],
            "parent_pid": pair[1],
        }
    )
    return True


def _invoke(progress, sources):
    namespace = progress["namespace"]
    _STATE["attempted"] = True  # reserved before the call; never retried
    progress["outcome"] = ("NOT_CALLED", None)
    _STATE["active"] = True
    try:
        result = namespace["_collect_pinned"](
            sources[1],
            sources[2],
            None,
            progress["nonce"],
            progress["argv0"],
            api_factory=_factory(progress),
        )
        progress["outcome"] = ("RETURNED", result)
    except BaseException as error:
        progress["outcome"] = ("RAISED", error)  # entry-owned original, first
        _fault(progress, error)
    finally:
        _STATE["active"] = False


def _forward(progress):
    return (
        progress["fault"] is None and progress["control"] is None and progress["uncertain"] is False
    )


def _advance(progress, sources):
    """One forward pass, each stage latched before its effect and entered at
    most once. An unfinished pass is never resumed: re-entry goes straight to
    the decision, and a finished decision is kept as it was."""
    if progress["decision"] is not None:
        return progress["decision"]
    if progress["entered"]:
        progress["uncertain"] = True  # the previous pass was interrupted
    progress["entered"] = True
    if not progress["loaded"] and _forward(progress):
        progress["loaded"] = True
        namespace = dict(RESERVED)
        progress["namespace"] = namespace  # held before exec: partial loads stay referenced
        try:
            KEEP.append(namespace)  # extra reference; the progress record already holds it
        except BaseException:
            pass
        try:
            _execute(sources[0], namespace)
        except Exception as error:
            progress["refusal"] = "COLLECT_ENTRY_LOAD"
            _fault(progress, error)
        if progress["refusal"] is None:
            _register(progress)
    if progress["loaded"] and progress["refusal"] is None and not progress["armed"]:
        progress["armed"] = True
        armed = False
        try:
            armed = _arm(progress) is True
        except Exception:
            armed = False
        if not armed:
            progress["refusal"] = "COLLECT_ENTRY_ARM"
    if _forward(progress) and progress["refusal"] is None and not _STATE["attempted"]:
        _invoke(progress, sources)
    decision = decide(progress)
    progress["decision"] = decision
    return decision


def cycle():
    """One parked pause; everything raised by it is swallowed."""
    try:
        _pause(PAUSE_SECONDS)
    except BaseException:
        pass


def _hold():
    """Sticky foreground parking: no exit, no retry, no cleanup, no timer."""
    while True:
        try:
            cycle()
        except BaseException:
            pass


def _drive(sources, nonce, argv0):
    """S2-S6 under protection. The only return needs an EXIT verdict, no
    parking and every captured original proven empty immediately before it;
    the FINAL line written before it is not proof of exit."""
    progress = _progress(nonce, argv0)
    while True:
        try:
            if not _STATE["parked"]:
                verdict = settle(_advance(progress, sources), progress)
                if verdict[0] == "EXIT":
                    _final(progress, verdict)
                    if _accepted(verdict, progress):
                        return verdict[1]
                _park(progress, "INTERNAL")
            _hold()
        except BaseException as error:
            try:
                _fault(progress, error)
            except BaseException:
                pass


def _pinned_sources(value):
    """All three exact bytes objects, sizes and SHA-256 pins, before any exec."""
    if type(value) is not tuple or len(value) != len(SOURCES):
        return None
    for raw, (_relative, digest, size) in zip(value, SOURCES, strict=True):
        if type(raw) is not bytes or len(raw) != size:
            return None
        if hashlib.sha256(raw).hexdigest() != digest:
            return None
    return value


def main(argv):
    """S0/S1 are pure refusals; from S2 on only the protected driver decides."""
    nonce = None
    if type(argv) is list and len(argv) == 1 and type(argv[0]) is str:
        nonce = argv[0] if NONCE_PATTERN.fullmatch(argv[0]) is not None else None
    if nonce is None:
        return _refuse(None, "COLLECT_ENTRY_ARGV")
    sources = _pinned_sources(_read_sources())
    if sources is None:
        return _refuse(nonce, "COLLECT_ENTRY_SOURCE")
    argv0 = _argv0()
    if not (type(argv0) is str and 0 < len(argv0) <= 1024 and "\x00" not in argv0):
        return _refuse(nonce, "COLLECT_ENTRY_SOURCE")
    return _drive(sources, nonce, argv0)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
