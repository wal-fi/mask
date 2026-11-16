"""N-S: specific adoption of ONE borrowed external job by S (root contract 0e26bddc).

Import and construction only define data, functions and classes: nothing is resolved,
read, compiled or executed until the explicit ``definitions()`` call. That call reads the
pinned backend (10c9058f) once with a bound, checks the SAME captured bytes (regular file,
no final reparse point, exact size, SHA and the dispatch premises of the inherited
``_start``) and executes them in a fresh private namespace with the backend's OWN compiler
semantics (``dont_inherit``). The complete four-key result is built locally and published
with ONE assignment; ordinary failures leave no cache and raise ``AdoptionError``
(``ADOPT_SOURCE``) without the original error; controls are never swallowed.

``ExternalJobOwner`` is the one specific subclass of that backend's ``Owner``, built with
``type`` and explicit base calls. One ``adopt`` attempt per owner, only in READY, validates
an exact int reference, the exact built-in shapes of its own ledger/quarantine (corruption
leaves the Owner HELD), refuses aliases of owned or quarantined handles, retains a distinct
candidate ``C`` BEFORE its first query, and checks configuration, accounting and members
of ``C``. ``C`` is borrowed: it is only queried as a JOB or passed as the second job of
the creation list; it is never closed, terminated, waited on or treated as a
process/thread, and the inherited ``close`` releases only the backend ledger. The first
control in ``adopt`` is retained by identity and reported as ``REFUSED_CONTROL`` with the
Owner HELD, with no later SDK call and no re-raise.

Not a native or product admission. Author: Claude2 (session 51ea0d85),
claude-opus-5-5/medium. Senff policy: AI-generated code requires human and security review.
"""

from __future__ import annotations

import ast
import ctypes
import hashlib
import stat
from pathlib import Path
from typing import Any

BACKEND_RELATIVE = "docs/poc/pg16_shell_admission_win32.py"
BACKEND_SHA = "10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726"
SOURCE_LIMIT = 65536
_REPARSE_POINT = 0x400
_CACHE: dict[str, Any] | None = None


class AdoptionError(Exception):
    """Closed refusal of ``definitions``: fixed args, never an original error or text."""

    def __init__(self) -> None:
        super().__init__("ADOPT_SOURCE")


# ---------------------------------------------------------------- pinned backend loading


def _dispatch_ok(raw: bytes) -> bool:
    """Reuse premises: _start reaches UpdateProcThreadAttribute via self._ok and
    CreateProcessW/ResumeThread via self._call; _ok itself goes through self._call."""
    tree = ast.parse(raw)
    owner = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Owner"
    )
    methods = {node.name: node for node in owner.body if isinstance(node, ast.FunctionDef)}

    def calls(function: ast.FunctionDef, method: str) -> list[object]:
        found: list[object] = []
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == method
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                found.append(node.args[0].value)
        return found

    def uses_call(function: ast.FunctionDef) -> bool:
        return any(
            isinstance(node, ast.Attribute)
            and node.attr == "_call"
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            for node in ast.walk(function)
        )

    start = methods["_start"]
    return (
        "UpdateProcThreadAttribute" in calls(start, "_ok")
        and "ResumeThread" in calls(start, "_call")
        and "CreateProcessW" in calls(start, "_call")
        and uses_call(methods["_ok"])
    )


def _load() -> dict[str, Any] | None:
    path = Path(__file__).resolve().parents[2] / BACKEND_RELATIVE
    info = path.lstat()
    regular = stat.S_ISREG(info.st_mode) and info.st_size <= SOURCE_LIMIT
    if not regular or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT:
        return None
    with path.open("rb") as stream:
        raw = stream.read(SOURCE_LIMIT + 1)
    if len(raw) != info.st_size or hashlib.sha256(raw).hexdigest() != BACKEND_SHA:
        return None
    if not _dispatch_ok(raw):
        return None  # refused BEFORE any execution of these bytes
    backend: dict[str, Any] = {"__name__": "_xj_backend", "__file__": str(path)}
    exec(compile(raw, str(path), "exec", dont_inherit=True), backend)
    return {
        "backend": backend,
        "Request": backend["Request"],
        "Win32Error": backend["Win32Error"],
        "ExternalJobOwner": _build(backend),
    }


def definitions() -> dict[str, Any]:
    """Explicit lazy load; the complete dictionary is published with ONE assignment."""
    global _CACHE
    cached = _CACHE
    if cached is not None:
        return cached
    failed = False
    candidate: dict[str, Any] | None = None
    try:
        candidate = _load()
    except Exception:
        failed = True
    if failed or candidate is None:
        raise AdoptionError()
    _CACHE = candidate
    return candidate


# ---------------------------------------------------------------- the specific subclass


def _build(b: dict[str, Any]) -> type:
    """The specific ExternalJobOwner of THIS private backend namespace."""
    base: Any = b["Owner"]
    win32_error: Any = b["Win32Error"]
    handle_type, dword, boolean = b["HANDLE"], b["DWORD"], b["BOOL"]
    job_list, invalid, normalize = b["PROC_THREAD_ATTRIBUTE_JOB_LIST"], b["INVALID"], b["_handle"]
    breakaway = b["JOB_LIMIT_BREAKAWAY_OK"] | b["JOB_LIMIT_SILENT_BREAKAWAY_OK"]

    def valid_handle(value: object) -> bool:
        return type(value) is int and 0 < value < invalid

    def init(self: Any, request: object) -> None:
        base.__init__(self, request)  # pure inherited constructor
        self._xj_external = None
        self._xj_state = "NOT_ADOPTED"
        self._xj_attempted = False
        self._xj_control = None
        self._xj_pair = None

    # -- adoption ---------------------------------------------------------------------

    def adopt(self: Any, reference: object) -> str:
        self._expect("READY")  # WIN32_HELD / WIN32_STATE, nothing consumed
        if self._xj_attempted:
            raise win32_error("WIN32_STATE") from None
        self._xj_attempted = True  # consumed BEFORE any validation
        outcome = "REFUSED_INTERNAL"
        try:
            outcome = adopt_body(self, reference)
        except Exception:
            outcome = "REFUSED_INTERNAL"
        except BaseException as control:
            # First (and only) control: pure assignments, no SDK, no re-raise.
            self._xj_control = control
            self._xj_state = "REFUSED"
            self.state = "HELD"
            self.held_reason = "WIN32_INTERRUPTED"
            return "REFUSED_CONTROL"
        self._xj_state = "ADOPTED" if outcome == "ADOPTED" else "REFUSED"
        return outcome

    def adopt_body(self: Any, reference: object) -> str:
        if not valid_handle(reference):
            return "REFUSED_INPUT"
        ledger, quarantine = self.ledger, self.quarantine
        shapes = (
            type(ledger) is dict
            and type(quarantine) is list
            and all(type(key) is str for key in ledger)
            and all(valid_handle(value) for value in ledger.values())
            and all(valid_handle(entry) for entry in quarantine)
        )
        if not shapes:
            self.state = "HELD"  # never forward corrupted data to the SDK later
            self.held_reason = "WIN32_INTERNAL"
            return "REFUSED_INTERNAL"
        if any(value == reference for value in ledger.values()) or any(
            entry == reference for entry in quarantine
        ):
            return "REFUSED_HANDLE"  # owned or quarantined: not a borrowed job
        self._xj_external = reference  # retained BEFORE the first query
        category = query_config(self, reference)
        if category != "OK":
            return category
        category, counts = query_accounting(self, reference)
        if category != "OK":
            return category
        if counts != (0, 0):
            return "REFUSED_NOT_EMPTY"
        category, pids = query_members(self, reference)
        if category != "OK":
            return category
        return "ADOPTED" if pids == () else "REFUSED_NOT_EMPTY"

    # -- queries of C as a JOB, through the BASE dispatch -----------------------------

    def query(self: Any, handle: object, kind: int, info: Any) -> tuple[bool, int]:
        length = dword(0)
        raised, value = base._call(
            self,
            "QueryInformationJobObject",
            handle,
            kind,
            ctypes.byref(info),
            ctypes.sizeof(info),
            ctypes.byref(length),
        )
        ok = not raised and type(value) is int and value != 0
        return ok, int(length.value)

    def query_config(self: Any, handle: object) -> str:
        info = b["ExtendedLimit"]()
        ok, length = query(self, handle, b["JOB_EXTENDED_LIMIT"], info)
        if not ok or length != ctypes.sizeof(info):
            return "REFUSED_QUERY"
        basic = info.BasicLimitInformation
        if (
            basic.LimitFlags != b["LIMIT_FLAGS"]
            or basic.ActiveProcessLimit != b["ACTIVE_PROCESS_LIMIT"]
            or basic.LimitFlags & breakaway
        ):
            return "REFUSED_CONFIG"
        return "OK"

    def query_accounting(self: Any, handle: object) -> tuple[str, tuple[int, int]]:
        info = b["Accounting"]()
        ok, length = query(self, handle, b["JOB_BASIC_ACCOUNTING"], info)
        if not ok or length != ctypes.sizeof(info):
            return "REFUSED_QUERY", (0, 0)
        total, active = int(info.TotalProcesses), int(info.ActiveProcesses)
        if active > total:
            return "REFUSED_QUERY", (0, 0)
        return "OK", (total, active)

    def query_members(self: Any, handle: object) -> tuple[str, tuple[int, ...]]:
        info = b["ProcessIdList"]()
        ok, length = query(self, handle, b["JOB_BASIC_PROCESS_ID_LIST"], info)
        count = int(info.NumberOfProcessIdsInList)
        header = int(b["ProcessIdList"].ProcessIdList.offset)
        minimum = header + count * ctypes.sizeof(ctypes.c_size_t)
        if (
            not ok
            or count != int(info.NumberOfAssignedProcesses)
            or count > b["ACTIVE_PROCESS_LIMIT"]
            or not minimum <= length <= ctypes.sizeof(info)
        ):
            return "REFUSED_QUERY", ()
        pids = tuple(int(info.ProcessIdList[index]) for index in range(count))
        if not all(0 < pid < (1 << 32) for pid in pids):
            return "REFUSED_QUERY", ()
        return "OK", pids

    # -- start: early public refusal, then the inherited path --------------------------

    def start(self: Any) -> None:
        self._expect("READY")
        if self._xj_state != "ADOPTED":
            raise win32_error("WIN32_STATE") from None  # zero SDK, no attributes
        base.start(self)

    # -- dispatch changes ----------------------------------------------------------------

    def call(self: Any, name: str, *args: Any) -> tuple[bool, Any]:
        if name == "UpdateProcThreadAttribute":
            if len(args) != 7:
                return True, None  # never delegated, whatever the attribute
            if type(args[2]) is int and args[2] == job_list:
                return expand(self, *args)
        elif name == "CreateProcessW":
            return create(self, args)
        elif name == "ResumeThread" and not verify(self, args):
            return True, None  # the real ResumeThread is never delegated
        result: tuple[bool, Any] = base._call(self, name, *args)
        return result

    def expand(
        self: Any,
        attributes: Any,
        flags: Any,
        attribute: Any,
        items: Any,
        size: Any,
        previous: Any,
        returned: Any,
    ) -> tuple[bool, Any]:
        outer, borrowed = self.ledger.get("job"), self._xj_external
        expected = handle_type * 1
        if not (
            self._xj_state == "ADOPTED"
            and borrowed is not None
            and type(items) is expected
            and size == ctypes.sizeof(expected) == 8
            and outer is not None
            and items[0] == outer
            and flags == 0
            and previous is None
            and returned is None
            and self._xj_pair is None
        ):
            return True, None  # not delegated; inherited attribute-failure path
        pair = (handle_type * 2)(outer, borrowed)
        self._xj_pair = pair
        self._keep.append(pair)  # alive through CreateProcessW and deletion
        result: tuple[bool, Any] = base._call(
            self,
            "UpdateProcThreadAttribute",
            attributes,
            flags,
            attribute,
            pair,
            ctypes.sizeof(pair),
            None,
            None,
        )
        return result

    def create(self: Any, args: tuple[Any, ...]) -> tuple[bool, Any]:
        borrowed = self._xj_external  # captured BEFORE delegation
        raised, value = base._call(self, "CreateProcessW", *args)
        pending = self._pending  # read-only: the inherited path consumes it
        if type(pending) is not b["ProcessInformation"]:
            return True, None  # unexpected shape: uncertain, never adopted
        outputs = (normalize(pending.hProcess), normalize(pending.hThread))
        if borrowed is not None and any(
            type(output) is int and output == borrowed for output in outputs
        ):
            return True, None  # C would become process/thread: uncertain creation
        return raised, value

    def verify(self: Any, args: tuple[Any, ...]) -> bool:
        """C membership/config/accounting/members of P before the real resume."""
        ledger, borrowed = self.ledger, self._xj_external
        if not (
            self._xj_state == "ADOPTED"
            and borrowed is not None
            and len(args) == 1
            and args[0] == ledger.get("thread")
            and "process" in ledger
            and self._xj_pair is not None
        ):
            return False
        member = boolean(0)
        raised, value = base._call(
            self, "IsProcessInJob", ledger["process"], borrowed, ctypes.byref(member)
        )
        if raised or type(value) is not int or value == 0 or member.value != 1:
            return False
        if query_config(self, borrowed) != "OK":
            return False
        if query_accounting(self, borrowed) != ("OK", (1, 1)):
            return False
        return query_members(self, borrowed) == ("OK", (self.pid,))

    def read_external(self: Any) -> Any:
        return self._xj_external

    def read_state(self: Any) -> Any:
        return self._xj_state

    def read_attempted(self: Any) -> Any:
        return self._xj_attempted

    def read_control(self: Any) -> Any:
        return self._xj_control

    namespace: dict[str, Any] = {
        "__doc__": "One borrowed external job C adopted once in READY (N-S contract).",
        "__init__": init,
        "external": property(read_external),
        "external_state": property(read_state),
        "adopt_attempted": property(read_attempted),
        "adopt_control": property(read_control),
        "adopt": adopt,
        "start": start,
        "_call": call,
    }
    return type("ExternalJobOwner", (base,), namespace)
