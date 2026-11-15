"""C0 entry: real public Owner setup then close, NEVER start (root C0 contract, 2026-11-14).

Import defines only. ``run_c0`` drives ONE caller-owned ``Owner`` of the pinned backend
through ``setup`` then ``close`` and nothing else: no ``start``, no child, no other Owner
method, no private member. The inert request (``"<application>" -I -B -S -c "pass"``) is
never started. The caller's exact ``QualCustody`` keeps backend, request, owner, the
original error and the first control by identity; ``custody.report`` stays reserved
(None). ``encode_c0`` emits one closed ASCII frame of at most 128 bytes.

``main`` (only under the final ``__name__`` guard) validates its two inputs before loading
anything, loads the fixed sibling qualifier by checked bytes and then the qualifier's own
public pinned ``load_backend``. OBSERVED exits 0 and a resource-free refusal exits 2 after
ONE emission attempt. Any uncertainty emits once and then parks in ``_park_c0`` with every
reference retained, swallowing later controls without replacing the first and without any
cleanup. A control that lands between bytecodes outside a ``try`` is a residual of the
language, not a containment claim; nothing here proves descendant or physical release.

C0 qualifies only this local setup/close path. S admission, child canaries, external stop,
N1-N16 and every product gate remain OPEN.

Author: Claude2 (session 51ea0d85), claude-opus-5-5/medium, from the C0 root contract and
the frozen RED84 test. Senff policy: AI-generated code requires human and security review.
"""

from __future__ import annotations

import hashlib
import re
import stat
import sys
import time
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, NoReturn

_QUALIFIER_NAME: Final = "oracle9_w1_supervisor_qualification.py"
_QUALIFIER_SHA: Final = "999f4a8d627e1550e8c95c6c6fa42aaa7a5edfb7045acbb33ccf51561d5fe015"
_QUALIFIER_LIMIT: Final = 65536
_REPARSE_POINT: Final = 0x400
_PATH_LIMIT: Final = 1024
_COMMAND_LIMIT: Final = 2048
_FRAME_LIMIT: Final = 128
_PARK_SLICE_S: Final = 60.0
_ENV: Final = (("W1_NATIVE_PROBE", "1"),)
_LOCAL_PATH: Final = re.compile(r"[A-Za-z]:[\\/][^\x00\"\r\n]*")
_STATUSES: Final = ("OBSERVED", "REFUSED", "UNKNOWN")
_STEPS: Final = ("INPUT", "CUSTODY", "LOAD", "SETUP", "CLOSE", "CONTROL", "INTERNAL", "DONE")
_STATES: Final = (
    "EMPTY",
    "NEW",
    "SETUP",
    "READY",
    "SETUP_FAILED",
    "STARTING",
    "LAUNCH_FAILED",
    "RUNNING",
    "HELD",
    "CLOSED",
    "OTHER",
)
_BACKEND_STATES: Final = frozenset(
    {
        "NEW",
        "SETUP",
        "READY",
        "SETUP_FAILED",
        "STARTING",
        "LAUNCH_FAILED",
        "RUNNING",
        "HELD",
        "CLOSED",
    }
)


class C0LoadError(Exception):
    """Closed refusal of ``load_qualifier``; never carries a path, digest or cause."""

    def __init__(self) -> None:
        super().__init__("C0_LOAD")


# ---------------------------------------------------------------- pinned qualifier loader


def load_qualifier() -> types.ModuleType:
    """Fixed sibling qualifier: one bounded read, exact SHA, execute THOSE bytes."""
    path = Path(__file__).resolve().parent / _QUALIFIER_NAME
    raw: bytes | None = None
    try:
        info = path.lstat()
        regular = stat.S_ISREG(info.st_mode) and info.st_size <= _QUALIFIER_LIMIT
        reparse = getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
        if regular and not reparse:
            with path.open("rb") as stream:
                raw = stream.read(_QUALIFIER_LIMIT + 1)
            if len(raw) != info.st_size:
                raw = None
    except Exception:
        raw = None
    if raw is None or hashlib.sha256(raw).hexdigest() != _QUALIFIER_SHA:
        raise C0LoadError()
    name = "_w1_c0_qualifier"
    module = types.ModuleType(name)
    module.__dict__["__file__"] = str(path)
    modules = sys.modules
    previous = modules.get(name)
    if previous is None and name in modules:
        raise C0LoadError()  # an existing blocking binding is left untouched
    modules[name] = module  # normal registration ONLY while the checked bytes define it
    failed = False
    try:
        code = compile(raw, str(path), "exec", dont_inherit=True)
        exec(code, module.__dict__)  # the checked bytes are the only bytes executed
    except Exception:
        failed = True
    finally:
        if modules.get(name) is module:  # restore the prior binding, never another's
            if previous is not None:
                modules[name] = previous
            else:
                del modules[name]
    if failed:
        raise C0LoadError()
    return module


# ---------------------------------------------------------------- closed frame


def _record_allowed(status: str, step: str, state: str) -> bool:
    if status not in _STATUSES or step not in _STEPS or state not in _STATES:
        return False
    if status == "OBSERVED":
        return step == "DONE" and state == "CLOSED"
    if status == "REFUSED":
        return step in ("INPUT", "CUSTODY", "LOAD") and state == "EMPTY"
    return step != "DONE"


def encode_c0(result: object) -> bytes:
    """``W1C0 STATUS STEP STATE\\n``, ASCII, <=128 bytes; anything else is C0_RECORD."""
    if type(result) is not tuple or len(result) != 3:
        raise ValueError("C0_RECORD")
    status, step, state = result
    if type(status) is not str or type(step) is not str or type(state) is not str:
        raise ValueError("C0_RECORD")
    if not _record_allowed(status, step, state):
        raise ValueError("C0_RECORD")
    frame = ("W1C0 " + status + " " + step + " " + state + "\n").encode("ascii")
    if len(frame) > _FRAME_LIMIT:
        raise ValueError("C0_RECORD")
    return frame


# ---------------------------------------------------------------- run_c0


def _local_path(value: object) -> bool:
    return (
        type(value) is str
        and 0 < len(value) <= _PATH_LIMIT
        and _LOCAL_PATH.fullmatch(value) is not None
    )


def _command_line(application: str) -> str:
    return '"' + application + '" -I -B -S -c "pass"'


def _inputs_ok(application: object, directory: object) -> bool:
    if type(application) is not str or not _local_path(application):
        return False
    return _local_path(directory) and len(_command_line(application)) <= _COMMAND_LIMIT


def _fresh(q: Any, custody: Any) -> bool:
    """Exact fresh QualCustody of the trusted qualifier; an incomplete carrier is refused."""
    try:
        if type(custody) is not q.QualCustody:
            return False
        return bool(
            custody.claimed is False
            and custody.backend is None
            and custody.request is None
            and custody.owner is None
            and custody.error is None
            and custody.first_control is None
            and custody.report is None
        )
    except Exception:
        return False


def _classes(backend: object) -> tuple[Any, Any] | None:
    """Trusted callable Request/Owner of an exact ModuleType, captured once."""
    if type(backend) is not types.ModuleType:
        return None
    table = vars(backend)
    request_class, owner_class = table.get("Request"), table.get("Owner")
    if not callable(request_class) or not callable(owner_class):
        return None
    return request_class, owner_class


def _state(owner: Any) -> str:
    """The ordinary public ``state`` metadata, sanitized; never invents HELD."""
    try:
        value = owner.state
    except Exception:
        return "OTHER"
    if type(value) is str and value in _BACKEND_STATES:
        return value
    return "OTHER"


def _sdk(custody: Any, call: Callable[[], object]) -> tuple[int, object]:
    """One call: 0 returned, 1 ordinary error retained, 2 first control retained."""
    try:
        return 0, call()
    except Exception as error:
        if custody.error is None:
            custody.error = error
        return 1, None
    except BaseException as control:
        if custody.first_control is None:
            custody.first_control = control
            if custody.error is None:
                custody.error = control
        return 2, None


def run_c0(
    q: Any, backend: types.ModuleType, application: object, directory: object, custody: object
) -> tuple[str, str, str]:
    """C0: custody, input and backend checks, then setup once and close once."""
    if not _fresh(q, custody):
        return ("REFUSED", "CUSTODY", "EMPTY")  # no write to a foreign or used custody
    held: Any = custody
    held.claimed = True
    if not _inputs_ok(application, directory) or type(application) is not str:
        return ("REFUSED", "INPUT", "EMPTY")
    classes = _classes(backend)
    if classes is None:
        return ("REFUSED", "LOAD", "EMPTY")
    request_class, owner_class = classes
    held.backend = backend
    command = _command_line(application)
    kind, request = _sdk(
        held,
        lambda: request_class(
            application=application,
            command_line=command,
            environment=_ENV,
            directory=directory,
        ),
    )
    if kind != 0:
        return ("UNKNOWN", "CONTROL" if kind == 2 else "INTERNAL", "EMPTY")
    held.request = request
    kind, owner = _sdk(held, lambda: owner_class(request))
    if kind != 0:
        return ("UNKNOWN", "CONTROL" if kind == 2 else "INTERNAL", "EMPTY")
    held.owner = owner  # backend, request and owner are retained BEFORE setup
    return _setup_then_close(held, owner)


def _setup_then_close(held: Any, owner: Any) -> tuple[str, str, str]:
    kind, value = _sdk(held, lambda: owner.setup())
    if kind == 2:
        return ("UNKNOWN", "CONTROL", _state(owner))
    state = _state(owner)
    if kind != 0 or value is not None or state != "READY":
        return ("UNKNOWN", "SETUP", state)  # no close after setup uncertainty
    kind, value = _sdk(held, lambda: owner.close())
    if kind == 2:
        return ("UNKNOWN", "CONTROL", _state(owner))
    state = _state(owner)
    if kind != 0 or value is not None or state != "CLOSED":
        return ("UNKNOWN", "CLOSE", state)  # never a second close
    return ("OBSERVED", "DONE", "CLOSED")


# ---------------------------------------------------------------- native entry (guarded main)


def _main_record(argv: object, holder: list[Any]) -> tuple[str, str, str]:
    """Validate the two inputs before loading; then pinned qualifier, backend and C0."""
    if type(argv) is not list or len(argv) != 2:
        return ("REFUSED", "INPUT", "EMPTY")
    application, directory = argv
    if not _inputs_ok(application, directory):
        return ("REFUSED", "INPUT", "EMPTY")
    try:
        q = load_qualifier()
        backend = q.load_backend()
    except Exception:
        return ("REFUSED", "LOAD", "EMPTY")  # definitions only: no native resource yet
    custody = q.QualCustody()
    holder.append(custody)  # strong reference for the whole life of this process
    return run_c0(q, backend, application, directory, custody)


def _emit(record: tuple[str, str, str]) -> tuple[bool, BaseException | None]:
    """At most ONE emission attempt: delivered only when write returned exactly len(frame)
    and flush then returned; a raised failure or control is returned, never retried."""
    try:
        frame = encode_c0(record)
        out = sys.stdout.buffer
        written = out.write(frame)
        if type(written) is not int or written != len(frame):
            return False, None  # short/invalid write: IO failure, no flush, no retry
        out.flush()
    except BaseException as failure:
        return False, failure
    return True, None


def _park_c0(holder: list[Any], first: list[BaseException]) -> NoReturn:
    """Retains every reference forever; later controls never replace the first; no cleanup."""
    retained = (holder, first)
    while True:
        try:
            while retained is not None:
                time.sleep(_PARK_SLICE_S)
        except BaseException:
            continue  # swallowed: the first control stays the first, nothing is released


def main(argv: list[str]) -> int:
    holder: list[Any] = []
    first: list[BaseException] = []
    record: tuple[str, str, str] = ("UNKNOWN", "INTERNAL", "EMPTY")
    try:
        record = _main_record(argv, holder)
    except BaseException as failure:
        first.append(failure)
        owner = holder[0].owner if holder else None
        step = "INTERNAL" if isinstance(failure, Exception) else "CONTROL"
        record = ("UNKNOWN", step, "EMPTY" if owner is None else _state(owner))
    delivered, emission_failure = _emit(record)
    if emission_failure is not None and not first:
        first.append(emission_failure)
    if record[0] == "OBSERVED" and delivered:
        return 0  # the Owner is CLOSED; nothing uncertain is left
    if record[0] == "REFUSED":
        return 2 if delivered else 3  # always before any Request/Owner: resource-free
    if record[0] == "OBSERVED":
        return 3  # closed resources, but the single emission failed; never retried
    _park_c0(holder, first)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
