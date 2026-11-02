"""Private, uninvoked entry for the benign native controls. Import defines only.

The only CLI surface: exactly one argument, a 32-hex nonce, which is a
freshness identifier and never a permission. Invoking this file is a native
effect that still needs its own reviewed procedure and exact command.

It pins and executes the accepted runner (b4198fe1), reserves and makes at
most one run(nonce) call, and returns an exit code only while the runner's
ORIGINAL registry list is proven empty. Anything retained, replaced or
unreadable parks in the foreground for good: the namespace, the original
list and the original control stay referenced; no retry, no native cleanup,
no recovery method, no timer, no exit. Console controls raise only during
the call. Nothing protects against console close, logoff, shutdown, an
external kill or a fatal interpreter fault; those are FAILED/UNKNOWN.
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

REPO = Path(__file__).resolve().parents[2]
RUNNER = (
    "docs/poc/pg16_shell_native_control.py",
    "b4198fe1606120e1e2df4fe9bff6a52fce4601a67074fdd7e922ef528341a496",
)
SOURCE_LIMIT = 65536
NONCE_PATTERN = re.compile(r"[0-9a-f]{32}")
KIND = "MASKGW_PG16_NATIVE_CONTROL_ENTRY_V1"
SUMMARY_KIND = "MASKGW_PG16_NATIVE_CONTROL_SUMMARY_V1"
CASE_OUTCOMES = ("APPROVED", "REJECTED", "NOT_RUN")
EXIT_OUTCOMES = {
    0: "APPROVED",
    1: "REJECTED",
    2: "REFUSED",
    4: "COMMIT_INDETERMINATE",
    5: "INTERRUPTED",
}
REASONS = ("HELD", "INTERRUPTED", "UNKNOWN_REGISTRY", "INTERNAL")
CONTROL_CODE = re.compile(r"CONTROL_[A-Z_]{1,40}")
PAUSE_SECONDS = 60.0
# Strong references, never removed: namespace, original registry list,
# progress record and every control or failure seen after S2.
KEEP = []
# "parked", "announced" and "attempted" are only ever set to True.
_STATE = {"active": False, "parked": False, "announced": False, "attempted": False}


# -- seams: module globals only, replaced only by tests -------------------------------


def _read_runner():
    """S1: bounded read and full SHA pin; None on any ordinary failure."""
    path = REPO / RUNNER[0]
    raw = None
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
        raw = None
    if raw is None or hashlib.sha256(raw).hexdigest() != RUNNER[1]:
        return None
    return raw


def _execute(raw, namespace):
    exec(compile(raw, namespace["__file__"], "exec"), namespace)


def _install(signum, handler):
    signal.signal(signum, handler)


def _pids():
    return os.getpid(), os.getppid()


def _pause(seconds):
    time.sleep(seconds)


# -- console controls and pipe events ------------------------------------------------


def _on_console(signum, frame):
    """Raises only during the single run call; otherwise no effect at all."""
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
            "refusal": verdict[2] if code == 2 else None,
        },
    )


def _refuse(nonce, refusal):
    """S0/S1 only: no namespace exists and the runner never executed."""
    _final({"nonce": nonce, "pid": None}, ("EXIT", 2, refusal))
    return 2


# -- registry trust and decision -----------------------------------------------------


def _progress(nonce):
    progress = {
        "nonce": nonce,
        "namespace": None,
        "live": None,
        "entered": False,
        "uncertain": False,
        "loaded": False,
        "captured": False,
        "armed": False,
        "refusal": None,
        "fault": None,
        "outcome": None,
        "decision": None,
        "pid": None,
    }
    KEEP.append(progress)
    return progress


def _trusted(progress):
    """The ORIGINAL list captured at S2, still the registry, exact list, empty."""
    try:
        namespace, live = progress["namespace"], progress["live"]
        return (
            type(namespace) is dict
            and type(live) is list
            and namespace.get("_LIVE") is live
            and len(live) == 0
        )
    except Exception:
        return False


def _summary_outcome(value):
    """Kind and closed labels of the returned descriptor; never truthiness."""
    if type(value) is not dict:
        return None
    kind, outcome, cases = value.get("kind"), value.get("outcome"), value.get("cases")
    scope, admission = value.get("scope"), value.get("admission_3s")
    # Exact str first, so no foreign equality is ever invoked.
    if not all(type(label) is str for label in (kind, outcome, scope, admission)):
        return None
    if not (
        kind == SUMMARY_KIND
        and scope == "BENIGN_CONTROL_ONLY"
        and admission == "NOT_MEASURED"
        and type(cases) is list
        and len(cases) == 3
    ):
        return None
    labels = [case.get("outcome") if type(case) is dict else None for case in cases]
    if not all(type(label) is str and label in CASE_OUTCOMES for label in labels):
        return None
    approved = all(label == "APPROVED" for label in labels)
    if outcome == "APPROVED" and approved:
        return "APPROVED"
    if outcome == "REJECTED" and not approved:
        return "REJECTED"
    return None


def _decide(progress):
    if _STATE["parked"]:
        return ("PARK", "INTERNAL")
    namespace, live = progress["namespace"], progress["live"]
    kind, value = progress["outcome"] if progress["outcome"] is not None else ("NONE", None)
    error_type = namespace.get("RunError") if type(namespace) is dict else None
    run_code = None
    if kind == "RAISED" and error_type is not None and type(value) is error_type:
        arguments = BaseException.args.__get__(value)
        if len(arguments) == 1 and type(arguments[0]) is str:
            run_code = arguments[0]
    faulted = progress["fault"] is not None or progress["uncertain"] is True
    interrupted = faulted or (kind == "RAISED" and not isinstance(value, Exception))
    held = run_code in ("CONTROL_HELD", "CONTROL_RETAINED")
    if held or not _trusted(progress):
        same = type(namespace) is dict and type(live) is list and namespace.get("_LIVE") is live
        if not _STATE["attempted"] or not same:
            return ("PARK", "UNKNOWN_REGISTRY")
        if held:
            return ("PARK", "HELD")
        return ("PARK", "INTERRUPTED" if interrupted else "INTERNAL")
    if not _STATE["attempted"]:
        refusal = progress["refusal"]
        if refusal is None:
            refusal = "ENTRY_INTERRUPTED" if faulted else "ENTRY_INTERNAL"
        return ("EXIT", 2, refusal)
    if interrupted or kind in ("NONE", "NOT_CALLED"):
        return ("EXIT", 5, "INTERRUPTED")  # reserved: never retried
    if kind == "RETURNED":
        outcome = _summary_outcome(value)
        if outcome == "APPROVED":
            return ("EXIT", 0, "APPROVED")
        if outcome == "REJECTED":
            return ("EXIT", 1, "REJECTED")
        return ("EXIT", 2, "ENTRY_RESULT")
    if run_code == "CONTROL_COMMIT_INDETERMINATE":
        return ("EXIT", 4, "COMMIT_INDETERMINATE")
    codes = namespace.get("CODES")
    if (
        run_code is not None
        and type(codes) is frozenset
        and run_code in codes
        and CONTROL_CODE.fullmatch(run_code) is not None
    ):
        return ("EXIT", 2, run_code)
    return ("EXIT", 2, "ENTRY_INTERNAL")


def decide(progress):
    """Pure and total: any failure while deciding parks."""
    try:
        return _decide(progress)
    except Exception:
        return ("PARK", "INTERNAL")


def _exit_shape(decision):
    return (
        type(decision) is tuple
        and len(decision) == 3
        and decision[0] == "EXIT"
        and type(decision[1]) is int
        and decision[1] in EXIT_OUTCOMES
        and type(decision[2]) is str
    )


def _park(progress, reason):
    _STATE["parked"] = True  # sticky: never reset
    _announce(progress, {"event": "PARKED", "reason": reason, "retained": _retained(progress)})


def _retained(progress):
    live = progress["live"]
    return len(live) if type(live) is list else None


def settle(decision, progress):
    """EXIT only for a well-formed decision while not parked and with the
    original registry trusted empty right now; otherwise park, sticky."""
    if not _STATE["parked"] and _exit_shape(decision) and _trusted(progress):
        return decision
    reason = "INTERNAL"
    if (
        type(decision) is tuple
        and len(decision) == 2
        and decision[0] == "PARK"
        and decision[1] in REASONS
    ):
        reason = decision[1]
    _park(progress, reason)
    return ("PARK", reason)


# -- S2-S5 forward pass -------------------------------------------------------------


def _capture(progress):
    if progress["captured"] or type(progress["namespace"]) is not dict:
        return
    progress["captured"] = True
    live = progress["namespace"].get("_LIVE")
    progress["live"] = live
    KEEP.append(live)  # the original object, even if the name is replaced later


def _usable(namespace):
    error_type = namespace.get("RunError")
    return (
        callable(namespace.get("run"))
        and type(error_type) is type
        and issubclass(error_type, Exception)
    )


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


def _invoke(progress):
    namespace = progress["namespace"]
    _STATE["attempted"] = True  # reserved before the call; never retried
    progress["outcome"] = ("NOT_CALLED", None)
    _STATE["active"] = True
    try:
        progress["outcome"] = ("RETURNED", namespace["run"](progress["nonce"]))
    except BaseException as error:
        progress["outcome"] = ("RAISED", error)  # entry-owned original, first
        try:
            KEEP.append(error)  # extra reference; its failure changes nothing
        except BaseException:
            pass
    finally:
        _STATE["active"] = False


def _forward(progress):
    return progress["fault"] is None and progress["uncertain"] is False


def _advance(progress, raw):
    """One forward pass. Each stage is latched before its effect and entered
    at most once. A pass that did not finish is never resumed: re-entry goes
    straight to the decision, and a finished decision is kept as it was."""
    if progress["decision"] is not None:
        return progress["decision"]
    if progress["entered"]:
        progress["uncertain"] = True  # the previous pass was interrupted
    progress["entered"] = True
    if not progress["loaded"] and _forward(progress):
        progress["loaded"] = True
        namespace = {
            "__name__": "_pg16_native_control_entry_runner",
            "__file__": str(REPO / RUNNER[0]),
        }
        progress["namespace"] = namespace
        KEEP.append(namespace)  # held before exec: partial creation stays referenced
        try:
            _execute(raw, namespace)
        except Exception:
            progress["refusal"] = "ENTRY_LOAD"
        _capture(progress)
        if progress["refusal"] is None and not (_trusted(progress) and _usable(namespace)):
            progress["refusal"] = "ENTRY_LOAD"
    _capture(progress)
    if _forward(progress) and progress["refusal"] is None and not progress["armed"]:
        progress["armed"] = True
        armed = False
        try:
            armed = _arm(progress) is True
        except Exception:
            armed = False
        if not armed:
            progress["refusal"] = "ENTRY_ARM"
    if _forward(progress) and progress["refusal"] is None and not _STATE["attempted"]:
        _invoke(progress)
    decision = decide(progress)
    progress["decision"] = decision
    return decision


def _fault(progress, error):
    """Never raises: the first fault is latched in progress before the
    fallible extra reference; a failing record changes nothing."""
    try:
        if progress["fault"] is None:
            progress["fault"] = error
    except BaseException:
        pass
    try:
        KEEP.append(error)
    except BaseException:
        pass


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


def _drive(raw, nonce):
    """S2-S6 under protection. The only return needs an EXIT verdict, no
    parking and the original registry trusted empty immediately before it."""
    progress = _progress(nonce)
    while True:
        try:
            if not _STATE["parked"]:
                verdict = settle(_advance(progress, raw), progress)
                if verdict[0] == "EXIT":
                    _final(progress, verdict)
                    if not _STATE["parked"] and _exit_shape(verdict) and _trusted(progress):
                        return verdict[1]
                _park(progress, "INTERNAL")
            _hold()
        except BaseException as error:
            try:
                _fault(progress, error)
            except BaseException:
                pass


def main(argv):
    """S0/S1 are pure refusals; from S2 on only the protected driver decides."""
    nonce = None
    if type(argv) is list and len(argv) == 1 and type(argv[0]) is str:
        nonce = argv[0] if NONCE_PATTERN.fullmatch(argv[0]) is not None else None
    if nonce is None:
        return _refuse(None, "ENTRY_ARGV")
    raw = _read_runner()
    if raw is None:
        return _refuse(nonce, "ENTRY_SOURCE")
    return _drive(raw, nonce)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
