"""Private nested-job adapter for the future benign native control. Import defines only.

No consumer, no CLI and no __main__. Nothing is read, compiled or loaded at
import or construction. definitions() explicitly reads the accepted backend
(10c9058f) by SHA, executes it into a fresh private namespace and builds a
control-only subclass of its Owner:

- OUTER is the backend's own job (ledger["job"]), retained as observer and
  containment; INNER is an extra owned KILL_ON_JOB_CLOSE job (ledger["inner"]).
- The inherited _start is reused unchanged. Only _call is overridden, narrowly:
  the checked JOB_LIST update becomes [outer, inner], and INNER is verified
  before the real ResumeThread is delegated.
- An audit proxy records every kernel call after setup, including the
  inherited direct terminate of _interrupt. Bounded, immutable snapshots,
  permanent invalidation on loss; control interruptions are never swallowed.

Accepted modules, globals, signatures and live instances are never patched.
"""

import ast
import ctypes
import hashlib
from pathlib import Path
import stat

REPO = Path(__file__).resolve().parents[2]
BACKEND_RELATIVE = "docs/poc/pg16_shell_admission_win32.py"
BACKEND_SHA = "10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726"
SOURCE_LIMIT = 65536
AUDIT_LIMIT = 512
_DEFINITIONS = {}


class ControlError(Exception):
    def __init__(self, code):
        super().__init__(code if code in ("CONTROL_SOURCE",) else "CONTROL_SOURCE")


def _read_backend():
    path = REPO / BACKEND_RELATIVE
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
    if failed or raw is None or hashlib.sha256(raw).hexdigest() != BACKEND_SHA:
        raise ControlError("CONTROL_SOURCE") from None
    return path, raw


def _dispatch_assumptions(raw):
    """The reuse invariant: _start reaches JOB_LIST and ResumeThread via self."""
    tree = ast.parse(raw)
    owner = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Owner"
    )
    methods = {node.name: node for node in owner.body if isinstance(node, ast.FunctionDef)}

    def calls(function, method):
        found = []
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

    def uses_call(function):
        return any(
            isinstance(node, ast.Attribute)
            and node.attr == "_call"
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            for node in ast.walk(function)
        )

    return (
        "UpdateProcThreadAttribute" in calls(methods["_start"], "_ok")
        and "ResumeThread" in calls(methods["_start"], "_call")
        and uses_call(methods["_ok"])
    )


def definitions():
    """Explicit lazy load of pinned definitions; cached per module instance."""
    if not _DEFINITIONS:
        path, raw = _read_backend()
        if not _dispatch_assumptions(raw):
            raise ControlError("CONTROL_SOURCE") from None
        backend = {"__name__": "_pg16_native_control_backend", "__file__": str(path)}
        exec(compile(raw, str(path), "exec"), backend)
        _DEFINITIONS.update(
            backend=backend,
            Request=backend["Request"],
            Win32Error=backend["Win32Error"],
            NestedJobOwner=_build(backend),
        )
    return _DEFINITIONS


def _build(b):
    owner_class, win32_error, handle_type = b["Owner"], b["Win32Error"], b["HANDLE"]
    dword, boolean = b["DWORD"], b["BOOL"]
    job_list = b["PROC_THREAD_ATTRIBUTE_JOB_LIST"]

    class _AuditKernel:
        """Records the call name, then forwards. Exception/overflow invalidate
        the audit but still forward (cleanup is never lost); a BaseException
        while recording propagates before the real call is made."""

        def __init__(self, owner, kernel):
            self._owner, self._kernel = owner, kernel

        def __getattr__(self, name):
            function = getattr(self._kernel, name)
            owner = self._owner

            def audited(*args):
                owner._record(name)
                return function(*args)

            return audited

    class NestedJobOwner(owner_class):
        """Control-only: OUTER = ledger["job"], INNER = ledger["inner"]."""

        def __init__(self, request):
            super().__init__(request)
            self.inner_verified = None
            self.inner_closed = False  # True only after deliberate close_inner
            self.audit = ()
            self.audit_valid = True
            self._pair = None

        # -- audit -----------------------------------------------------------

        def _entry(self, name):
            if type(name) is not str or not 0 < len(name) <= 64:
                raise ValueError()
            return name

        def _record(self, name):
            try:
                entry = self._entry(name)
                if len(self.audit) >= AUDIT_LIMIT:
                    self.audit_valid = False
                else:
                    self.audit = (*self.audit, entry)  # immutable snapshot
            except Exception:
                self.audit_valid = False
            except BaseException:
                self.audit_valid = False
                raise

        # -- queries on an explicit handle (no ledger swapping) ----------------

        def _query(self, handle, kind, info):
            length = dword(0)
            raised, value = super()._call(
                "QueryInformationJobObject",
                handle,
                kind,
                ctypes.byref(info),
                ctypes.sizeof(info),
                ctypes.byref(length),
            )
            ok = not raised and type(value) is int and value != 0
            return ok, length.value

        def _job_config(self, handle):
            info = b["ExtendedLimit"]()
            ok, length = self._query(handle, b["JOB_EXTENDED_LIMIT"], info)
            basic = info.BasicLimitInformation
            return (
                ok
                and length == ctypes.sizeof(info)
                and basic.LimitFlags == b["LIMIT_FLAGS"]
                and basic.ActiveProcessLimit == b["ACTIVE_PROCESS_LIMIT"]
                and not basic.LimitFlags
                & (b["JOB_LIMIT_BREAKAWAY_OK"] | b["JOB_LIMIT_SILENT_BREAKAWAY_OK"])
            )

        def _job_accounting(self, handle):
            info = b["Accounting"]()
            ok, length = self._query(handle, b["JOB_BASIC_ACCOUNTING"], info)
            if not ok or length != ctypes.sizeof(info):
                return None
            return info.TotalProcesses, info.ActiveProcesses

        def _job_members(self, handle):
            info = b["ProcessIdList"]()
            ok, length = self._query(handle, b["JOB_BASIC_PROCESS_ID_LIST"], info)
            count = info.NumberOfProcessIdsInList
            header = b["ProcessIdList"].ProcessIdList.offset
            entry = ctypes.sizeof(ctypes.c_size_t)
            if (
                not ok
                or count != info.NumberOfAssignedProcesses
                or count > b["ACTIVE_PROCESS_LIMIT"]
                or not header + count * entry <= length <= ctypes.sizeof(info)
            ):
                return None
            pids = tuple(int(info.ProcessIdList[index]) for index in range(count))
            return pids if all(0 < pid < (1 << 32) for pid in pids) else None

        # -- setup: inherited OUTER/stdio, then owned INNER --------------------

        def _setup(self):
            super()._setup()  # raises on failure; OUTER/NUL/pipe checked
            self.state = "SETUP"
            api = self._api
            self._api = b["_Api"](_AuditKernel(self, api.k), api.last_error)
            raised, value = self._call("CreateJobObjectW", None, None)
            if raised:
                self._hold("WIN32_JOB")
            inner = b["_handle"](value)
            if inner is None:
                self._fail("WIN32_JOB", "SETUP_FAILED")
            if inner in self.ledger.values():
                self._quarantine((inner,))
                self._hold("WIN32_JOB")
            self.ledger["inner"] = inner
            limits = b["ExtendedLimit"]()
            limits.BasicLimitInformation.LimitFlags = b["LIMIT_FLAGS"]
            limits.BasicLimitInformation.ActiveProcessLimit = b["ACTIVE_PROCESS_LIMIT"]
            raised, ok = self._ok(
                "SetInformationJobObject",
                inner,
                b["JOB_EXTENDED_LIMIT"],
                ctypes.byref(limits),
                ctypes.sizeof(limits),
            )
            if not ok or not self._job_config(inner):
                self._fail("WIN32_CONFIG", "SETUP_FAILED")
            flags = dword(0)
            raised, ok = self._ok("GetHandleInformation", inner, ctypes.byref(flags))
            if not ok or flags.value & b["HANDLE_FLAG_INHERIT"]:
                self._fail("WIN32_INHERIT", "SETUP_FAILED")
            self.state = "READY"

        # -- the only dispatch changes -----------------------------------------

        def _call(self, name, *args):
            if name == "UpdateProcThreadAttribute":
                # Known 7-argument API: any other arity is refused before any
                # native delegation, whatever the attribute value.
                if len(args) != 7:
                    return True, None
                if type(args[2]) is int and args[2] == job_list:
                    return self._expand_job_list(*args)
            if name == "ResumeThread":
                verified = self._verify_inner(args)
                self.inner_verified = verified
                if not verified:
                    return True, None  # real ResumeThread never delegated
            return super()._call(name, *args)

        def _expand_job_list(self, attributes, flags, attribute, items, size, previous, returned):
            outer, inner = self.ledger.get("job"), self.ledger.get("inner")
            expected = handle_type * 1
            if not (
                type(items) is expected
                and size == ctypes.sizeof(expected) == 8
                and outer is not None
                and inner is not None
                and items[0] == outer
                and flags == 0
                and previous is None
                and returned is None
                and self._pair is None
            ):
                return True, None  # not delegated; inherited attribute-failure path
            pair = (handle_type * 2)(outer, inner)
            self._pair = pair
            self._keep.append(pair)  # alive through CreateProcessW and deletion
            return super()._call(
                "UpdateProcThreadAttribute",
                attributes,
                flags,
                attribute,
                pair,
                ctypes.sizeof(pair),
                None,
                None,
            )

        def _verify_inner(self, args):
            """INNER membership/config/accounting/list before the real resume.
            The inherited OUTER checks already ran inside _start."""
            ledger = self.ledger
            if not (
                len(args) == 1
                and args[0] == ledger.get("thread")
                and "process" in ledger
                and "inner" in ledger
                and self._pair is not None
            ):
                return False
            member = boolean(0)
            raised, value = super()._call(
                "IsProcessInJob", ledger["process"], ledger["inner"], ctypes.byref(member)
            )
            if raised or type(value) is not int or value == 0 or member.value != 1:
                return False
            return (
                self._job_config(ledger["inner"])
                and self._job_accounting(ledger["inner"]) == (1, 1)
                and self._job_members(ledger["inner"]) == (self.pid,)
            )

        # -- deliberate live close of INNER -------------------------------------

        def close_inner(self):
            self._expect("RUNNING")
            if "inner" not in self.ledger:
                raise win32_error("WIN32_STATE") from None
            self._guarded(self._close_inner)

        def _close_inner(self):
            if self._close("inner"):
                self.inner_closed = True
                return
            # Still RUNNING: contain on OUTER first, then HELD (INNER retained).
            self._ok("TerminateJobObject", self.ledger["job"], b["ABORT_EXIT_CODE"])
            self._hold("WIN32_CLOSE")

        # -- ordinary close: proof before INNER is dropped -----------------------

        def close(self):
            self._expect("SETUP_FAILED", "READY", "LAUNCH_FAILED", "RUNNING")
            if "inner" in self.ledger:
                # The whole extra-resource transition runs under the inherited
                # guard: refusals (Win32Error) pass unchanged; unexpected
                # exceptions and control interruptions become HELD with INNER
                # retained, exactly as for setup/start.
                self._guarded(self._close_extra)
            super().close()

        def _close_extra(self):
            if "inner" in self.ledger:
                if self.process_created:
                    waited = self._wait(0)
                    if waited is None:
                        self._hold("WIN32_WAIT")
                    counts, pids = self._accounting(), self._members()
                    if counts is None or pids is None or pids == "TOO_MANY":
                        self._hold("WIN32_ACCOUNTING")
                    if not (waited and counts[1] == 0 and pids == ()):
                        raise win32_error("WIN32_NOT_QUIESCENT") from None
                    for name in ("stdin", "stderr", "stdout_write"):
                        if not self._close(name):
                            self._hold("WIN32_CLOSE")
                    available, ok = self._peek()
                    if not ok:
                        self._hold("WIN32_PIPE")
                    if not (available is None and self.eof):
                        raise win32_error("WIN32_NOT_QUIESCENT") from None
                elif self._create_attempted:
                    # Clean failed creation: no hidden member in OUTER, and
                    # therefore none in the nested INNER either.
                    if self._accounting() != (0, 0) or self._members() != ():
                        self._hold("WIN32_ACCOUNTING")
                if not self._close("inner"):
                    self._hold("WIN32_CLOSE")

    return NestedJobOwner
