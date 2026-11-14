"""W1 supervisor qualification around the EXISTING public backend Owner (SQ1 + SQ2).

Import defines only: no ``__main__``, no automatic backend load, no DLL. ``qualify`` drives
ONE caller-owned ``Owner`` of the pinned backend (10c9058f) through ONE fixed benign
direct-base child (``-I -B -S``) using only its public methods ``setup/start/
check_config/wait/exit_code/accounting/members/terminate/available/read/close`` and its
public ``state``; never private members, ledger or PID. The caller's ``QualCustody``
holds backend, request and owner BEFORE ``setup`` and keeps them afterwards.

One global finite TURN budget counts every ``wait(WAIT_MS)`` over the LIVE, WAIT and EOF
drain phases; ``wait(0)`` is only the immediate alive observation right before the single
``terminate`` and is not a turn. At most one ``read`` per turn, only after a fresh
positive ``available()``. The budget is a decision budget, not a wall-clock bound: an
operating-system call inside the backend may block. ``close`` is attempted only after a
positive exit, the expected exit code, ``accounting() == (1, 0)``, ``members() == ()``
and a FRESH ``available() is None`` read after that inventory. A channel mismatch or
overflow may still close after that full public quiescence, but is never OBSERVED; any
SDK error, invalid value or unresolved EOF retains the custody without close. The first
control (a BaseException that is not an Exception) is kept by identity, recorded with a
pure report and re-raised outside any ``except`` with zero further SDK calls.

Two canaries qualify only these public Owner paths for one direct child. They do not
admit S, external stop, descendant cleanup or any N1-N16/product gate.

Author: Claude2 (session 51ea0d85), claude-opus-5-5/medium, from SQ1/SQ2 and the
frozen RED tests. Senff policy: AI-generated code requires human and security review.
"""

from __future__ import annotations

import enum
import hashlib
import re
import stat
import types
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NoReturn

OUTPUT_CAP: Final = 4096
READ_CAP: Final = 4096
WAIT_MS: Final = 50
MAX_TURNS: Final = 400
_U32_MAX: Final = (1 << 32) - 1
_PATH_LIMIT: Final = 1024
_COMMAND_LIMIT: Final = 2048
_BACKEND_NAME: Final = "pg16_shell_admission_win32.py"
_BACKEND_SHA: Final = "10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726"
_BACKEND_LIMIT: Final = 65536
_REPARSE_POINT: Final = 0x400
_ENV: Final = (("W1_NATIVE_PROBE", "1"),)
_LOCAL_PATH: Final = re.compile(r"[A-Za-z]:[\\/][^\x00\"\r\n]*")
_NATURAL_LINE: Final = b"MASKGW-W1-SUPERVISOR-NATURAL"
_LIVE_LINE: Final = b"MASKGW-W1-SUPERVISOR-LIVE"
_NATURAL_CODE: Final = "print('MASKGW-W1-SUPERVISOR-NATURAL')"
_LIVE_CODE: Final = "import time;print('MASKGW-W1-SUPERVISOR-LIVE',flush=True);time.sleep(30)"
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


# ---------------------------------------------------------------- closed enums


class QualCase(enum.Enum):
    NATURAL = "NATURAL"
    TERMINATE = "TERMINATE"


class QualStatus(enum.Enum):
    OBSERVED = "OBSERVED"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    REFUSED_CUSTODY = "REFUSED_CUSTODY"
    REFUSED_INPUT = "REFUSED_INPUT"


class QualStep(enum.Enum):
    SETUP = "SETUP"
    START = "START"
    CONFIG = "CONFIG"
    LIVE_LINE = "LIVE_LINE"
    TERMINATE = "TERMINATE"
    WAIT = "WAIT"
    EXIT_CODE = "EXIT_CODE"
    ACCOUNTING = "ACCOUNTING"
    MEMBERS = "MEMBERS"
    EOF = "EOF"
    CLOSE = "CLOSE"


class QualFault(enum.Enum):
    NONE = "NONE"
    INPUT = "INPUT"
    CUSTODY = "CUSTODY"
    BACKEND = "BACKEND"
    SETUP = "SETUP"
    START = "START"
    CONFIG = "CONFIG"
    IO = "IO"
    TIME_BUDGET = "TIME_BUDGET"
    EXIT_CODE = "EXIT_CODE"
    ACCOUNTING = "ACCOUNTING"
    MEMBERS = "MEMBERS"
    CLOSE = "CLOSE"
    CONTROL = "CONTROL"
    STATE = "STATE"
    INTERNAL = "INTERNAL"


class OwnerState(enum.Enum):
    EMPTY = "EMPTY"
    NEW = "NEW"
    SETUP = "SETUP"
    READY = "READY"
    SETUP_FAILED = "SETUP_FAILED"
    STARTING = "STARTING"
    LAUNCH_FAILED = "LAUNCH_FAILED"
    RUNNING = "RUNNING"
    HELD = "HELD"
    CLOSED = "CLOSED"
    OTHER = "OTHER"


class LineResult(enum.Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    OVERFLOW = "OVERFLOW"
    ABSENT = "ABSENT"


class CloseResult(enum.Enum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    NONE_CLOSED = "NONE_CLOSED"
    NONE_NOT_CLOSED = "NONE_NOT_CLOSED"
    INVALID_RETURN = "INVALID_RETURN"
    RAISED = "RAISED"


class TermResult(enum.Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    RETURNED = "RETURNED"
    INVALID_RETURN = "INVALID_RETURN"
    RAISED = "RAISED"


_STEP_FAULT: Final = {
    QualStep.SETUP: QualFault.SETUP,
    QualStep.START: QualFault.START,
    QualStep.CONFIG: QualFault.CONFIG,
    QualStep.LIVE_LINE: QualFault.IO,
    QualStep.TERMINATE: QualFault.STATE,
    QualStep.WAIT: QualFault.IO,
    QualStep.EXIT_CODE: QualFault.EXIT_CODE,
    QualStep.ACCOUNTING: QualFault.ACCOUNTING,
    QualStep.MEMBERS: QualFault.MEMBERS,
    QualStep.EOF: QualFault.IO,
    QualStep.CLOSE: QualFault.CLOSE,
}
_EARLY_STEPS: Final = frozenset({QualStep.SETUP, QualStep.START, QualStep.CONFIG})


# ---------------------------------------------------------------- carriers (redacted repr)


@dataclass(frozen=True, slots=True, repr=False)
class QualSpec:
    case: QualCase
    application: str
    directory: str
    max_turns: int

    def __repr__(self) -> str:
        return "QualSpec(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class QualReport:
    case: QualCase | None
    status: QualStatus
    fault: QualFault
    step: QualStep | None
    owner_state: OwnerState
    exit_code: int | None
    total: int | None
    active: int | None
    members: int | None
    stdout_bytes: int
    line: LineResult
    eof: int
    close: CloseResult
    terminate: TermResult
    turns: int

    def __repr__(self) -> str:
        return "QualReport(<redacted>)"


@dataclass(slots=True, repr=False)
class QualCustody:
    """Caller-created EMPTY; one qualification per custody; keeps every original."""

    claimed: bool = False
    backend: object | None = None
    request: object | None = None
    owner: object | None = None
    error: BaseException | None = None
    first_control: BaseException | None = None
    report: QualReport | None = None

    def __repr__(self) -> str:
        return "QualCustody(<redacted>)"


class BackendRefused(Exception):
    """Closed refusal of ``load_backend``; never carries a path, digest or cause."""

    def __init__(self) -> None:
        super().__init__("BACKEND")


# ---------------------------------------------------------------- pinned backend loader


def _backend_bytes(path: Path) -> bytes | None:
    """Bounded single read of a regular non-reparse file; None on any ordinary failure."""
    raw: bytes | None = None
    try:
        info = path.lstat()
        regular = stat.S_ISREG(info.st_mode) and info.st_size <= _BACKEND_LIMIT
        reparse = getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
        if regular and not reparse:
            with path.open("rb") as stream:
                raw = stream.read(_BACKEND_LIMIT + 1)
            if len(raw) != info.st_size:
                raw = None
    except Exception:
        raw = None
    if raw is None or hashlib.sha256(raw).hexdigest() != _BACKEND_SHA:
        return None
    return raw  # the checked bytes are the only bytes ever executed


def load_backend() -> types.ModuleType:
    """Reads the fixed sibling backend once, checks the pinned SHA, executes THOSE bytes."""
    path = Path(__file__).resolve().parent / _BACKEND_NAME
    raw = _backend_bytes(path)
    if raw is None:
        raise BackendRefused()
    module = types.ModuleType("_w1_supervisor_backend")
    module.__dict__["__file__"] = str(path)
    failed = False
    try:
        code = compile(raw, str(path), "exec", dont_inherit=True)
        exec(code, module.__dict__)
    except Exception:
        failed = True
    if failed:
        raise BackendRefused()
    return module


# ---------------------------------------------------------------- pure admission


def _u32(value: object) -> bool:
    return type(value) is int and 0 <= value <= _U32_MAX


def _local_path(value: object) -> bool:
    return (
        type(value) is str
        and 0 < len(value) <= _PATH_LIMIT
        and _LOCAL_PATH.fullmatch(value) is not None
    )


def _command_line(case: QualCase, application: str) -> str:
    code = _NATURAL_CODE if case is QualCase.NATURAL else _LIVE_CODE
    return '"' + application + '" -I -B -S -c "' + code + '"'


def _admit(spec: object) -> tuple[QualCase, str, str, int] | None:
    """Pure validation; no filesystem or environment inspection."""
    if type(spec) is not QualSpec:
        return None
    case: object = None
    application: object = None
    directory: object = None
    turns: object = None
    try:  # an underinitialized own carrier is a refusal, never an escaping error
        case, application = spec.case, spec.application
        directory, turns = spec.directory, spec.max_turns
    except Exception:
        return None
    if type(case) is not QualCase or type(application) is not str or type(directory) is not str:
        return None
    if not _local_path(application) or not _local_path(directory):
        return None
    if type(turns) is not int or not 1 <= turns <= MAX_TURNS:
        return None
    if len(_command_line(case, application)) > _COMMAND_LIMIT:
        return None
    return case, application, directory, turns


def _fresh(custody: object) -> bool:
    if type(custody) is not QualCustody:
        return False
    try:
        return (
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


def _capture(backend: object) -> tuple[Any, Any] | None:
    """Request and Owner classes from an exact ModuleType namespace, captured once."""
    if type(backend) is not types.ModuleType:
        return None
    table = vars(backend)
    request, owner, error = table.get("Request"), table.get("Owner"), table.get("Win32Error")
    if not (isinstance(request, type) and isinstance(owner, type) and isinstance(error, type)):
        return None
    if not issubclass(error, Exception):
        return None
    return request, owner


def _refusal(status: QualStatus, fault: QualFault) -> QualReport:
    return QualReport(
        case=None,
        status=status,
        fault=fault,
        step=None,
        owner_state=OwnerState.EMPTY,
        exit_code=None,
        total=None,
        active=None,
        members=None,
        stdout_bytes=0,
        line=LineResult.ABSENT,
        eof=0,
        close=CloseResult.NOT_ATTEMPTED,
        terminate=TermResult.NOT_REQUESTED,
        turns=0,
    )


# ---------------------------------------------------------------- one qualification


class _Done(Exception):
    """Internal: the run has recorded its outcome; never escapes ``qualify``."""


class _Run:
    """State of ONE qualification; the originals live in the caller custody."""

    def __init__(self, custody: QualCustody, case: QualCase, max_turns: int) -> None:
        self.custody = custody
        self.case = case
        self.max_turns = max_turns
        self.owner: Any = None
        self.turns = 0
        self.reads = 0
        self.read_in_turn = False
        self.retained = bytearray()
        self.consumed = 0
        self.overflow = False
        self.status = QualStatus.UNKNOWN
        self.fault = QualFault.INTERNAL
        self.step: QualStep | None = None
        self.line: LineResult | None = None
        self.exit_code: int | None = None
        self.total: int | None = None
        self.active: int | None = None
        self.members: int | None = None
        self.eof = 0
        self.close = CloseResult.NOT_ATTEMPTED
        self.terminate = TermResult.NOT_REQUESTED
        self.control: BaseException | None = None
        self.last_state = OwnerState.EMPTY

    # -------------------------------------------------------- outcome helpers

    def stop(self, status: QualStatus, fault: QualFault, step: QualStep | None) -> NoReturn:
        self.status, self.fault, self.step = status, fault, step
        raise _Done()

    def invoke(self, step: QualStep, call: Callable[[], object]) -> object:
        """One SDK call: an Exception is retained and stops; a control is kept by identity."""
        value: object = None
        caught: BaseException | None = None
        is_control = False
        try:
            value = call()
        except Exception as error:
            caught = error
        except BaseException as control:
            caught = control
            is_control = True
        if caught is None:
            return value
        if step is QualStep.TERMINATE:
            self.terminate = TermResult.RAISED
        elif step is QualStep.CLOSE:
            self.close = CloseResult.RAISED
        if self.custody.error is None:
            self.custody.error = caught
        if is_control:
            self.control = caught
            self.custody.first_control = caught
            self.stop(QualStatus.UNKNOWN, QualFault.CONTROL, step)
        status = QualStatus.FAIL if step in _EARLY_STEPS else QualStatus.UNKNOWN
        self.stop(status, _STEP_FAULT[step], step)

    def state_now(self) -> OwnerState:
        """The public state, sanitized; never truthiness, repr or equality of a foreign value."""
        try:
            value = self.owner.state
        except Exception:
            value = None
        state = OwnerState.OTHER
        if type(value) is str and value in _BACKEND_STATES:
            state = OwnerState[value]
        self.last_state = state
        return state

    # -------------------------------------------------------- acquisition and phases

    def acquire(self, classes: tuple[Any, Any], application: str, directory: str) -> None:
        request_class, owner_class = classes
        request = self.invoke(
            QualStep.SETUP,
            lambda: request_class(
                application=application,
                command_line=_command_line(self.case, application),
                environment=_ENV,
                directory=directory,
            ),
        )
        self.custody.request = request
        owner = self.invoke(QualStep.SETUP, lambda: owner_class(request))
        self.custody.owner = owner  # caller custody holds the original BEFORE setup
        self.owner = owner
        self.last_state = OwnerState.NEW

    def execute(self) -> None:
        owner = self.owner
        self.expect_none(QualStep.SETUP, self.invoke(QualStep.SETUP, lambda: owner.setup()))
        self.expect_state(QualStep.SETUP, OwnerState.READY)
        self.expect_none(QualStep.START, self.invoke(QualStep.START, lambda: owner.start()))
        self.expect_state(QualStep.START, OwnerState.RUNNING)
        self.expect_none(
            QualStep.CONFIG, self.invoke(QualStep.CONFIG, lambda: owner.check_config())
        )
        if self.case is QualCase.TERMINATE:
            self.live_then_terminate()
        self.wait_for_exit()
        self.inventory()
        self.drain_to_eof()
        self.close_after_quiescence()

    def expect_none(self, step: QualStep, value: object) -> None:
        if value is not None:
            self.stop(QualStatus.FAIL, _STEP_FAULT[step], step)

    def expect_state(self, step: QualStep, expected: OwnerState) -> None:
        if self.state_now() is not expected:
            self.stop(QualStatus.FAIL, _STEP_FAULT[step], step)

    def turn(self, step: QualStep) -> bool:
        """One budget turn: exactly one wait(WAIT_MS); never beyond max_turns."""
        if self.turns >= self.max_turns:
            self.stop(QualStatus.UNKNOWN, QualFault.TIME_BUDGET, step)
        self.turns += 1
        self.read_in_turn = False
        owner = self.owner
        exited = self.invoke(step, lambda: owner.wait(WAIT_MS))
        if type(exited) is not bool:
            self.stop(QualStatus.UNKNOWN, QualFault.STATE, step)
        return exited

    def poll(self, step: QualStep) -> bool:
        """One available() and at most one read per turn; True only for a positive EOF."""
        owner = self.owner
        size = self.invoke(step, lambda: owner.available())
        if size is None:
            return True
        if not _u32(size):
            self.stop(QualStatus.UNKNOWN, QualFault.IO, step)
        if type(size) is int and size > 0 and not self.read_in_turn:
            data = self.invoke(step, lambda: owner.read())
            if type(data) is not bytes or len(data) > READ_CAP:
                self.stop(QualStatus.UNKNOWN, QualFault.IO, step)
            self.read_in_turn = True
            self.reads += 1
            self.take(data)
        return False

    def take(self, data: bytes) -> None:
        self.consumed += len(data)
        room = OUTPUT_CAP - len(self.retained)
        self.retained += data[:room]
        if len(data) > room:
            self.overflow = True

    def live_verdict(self) -> LineResult | None:
        """MATCH, MISMATCH, or None while the retained bytes are still a LIVE prefix."""
        retained = bytes(self.retained)
        if retained in (_LIVE_LINE + b"\n", _LIVE_LINE + b"\r\n"):
            return LineResult.MATCH
        prefix = (_LIVE_LINE + b"\r\n").startswith(retained) or (_LIVE_LINE + b"\n").startswith(
            retained
        )
        if self.overflow or b"\n" in retained or not prefix:
            return LineResult.MISMATCH
        return None

    def live_then_terminate(self) -> None:
        for _ in range(self.max_turns + 1):
            exited = self.turn(QualStep.LIVE_LINE)
            self.poll(QualStep.LIVE_LINE)
            verdict = self.live_verdict()
            if verdict is LineResult.MISMATCH:
                self.line = LineResult.MISMATCH
                self.stop(QualStatus.FAIL, QualFault.IO, QualStep.LIVE_LINE)
            if exited:  # an unexpected exit is never a kill observation
                self.line = verdict if verdict is not None else self.final_line()
                self.stop(QualStatus.FAIL, QualFault.STATE, QualStep.LIVE_LINE)
            if verdict is LineResult.MATCH:
                break
        else:
            self.stop(QualStatus.UNKNOWN, QualFault.TIME_BUDGET, QualStep.LIVE_LINE)
        owner = self.owner
        alive = self.invoke(QualStep.TERMINATE, lambda: owner.wait(0))  # not a budget turn
        if type(alive) is not bool:
            self.stop(QualStatus.UNKNOWN, QualFault.STATE, QualStep.TERMINATE)
        if alive:
            self.stop(QualStatus.FAIL, QualFault.STATE, QualStep.TERMINATE)
        result = self.invoke(QualStep.TERMINATE, lambda: owner.terminate())
        if result is not None:
            self.terminate = TermResult.INVALID_RETURN
            self.stop(QualStatus.UNKNOWN, QualFault.STATE, QualStep.TERMINATE)
        self.terminate = TermResult.RETURNED

    def wait_for_exit(self) -> None:
        for _ in range(self.max_turns + 1):
            exited = self.turn(QualStep.WAIT)
            self.poll(QualStep.WAIT)
            if exited:
                return
        self.stop(QualStatus.UNKNOWN, QualFault.TIME_BUDGET, QualStep.WAIT)

    def inventory(self) -> None:
        owner = self.owner
        code = self.invoke(QualStep.EXIT_CODE, lambda: owner.exit_code())
        if type(code) is not int or not _u32(code):
            self.stop(QualStatus.UNKNOWN, QualFault.EXIT_CODE, QualStep.EXIT_CODE)
        self.exit_code = code
        expected = 0 if self.case is QualCase.NATURAL else 1
        if code != expected:  # conservative early failure, before any inventory
            self.stop(QualStatus.FAIL, QualFault.EXIT_CODE, QualStep.EXIT_CODE)
        counts = self.invoke(QualStep.ACCOUNTING, lambda: owner.accounting())
        if type(counts) is not tuple or len(counts) != 2 or not all(_u32(v) for v in counts):
            self.stop(QualStatus.UNKNOWN, QualFault.ACCOUNTING, QualStep.ACCOUNTING)
        total, active = counts
        if total <= 2 and active <= 2:
            self.total, self.active = total, active
        if total != 1 or active != 0:
            self.stop(QualStatus.FAIL, QualFault.ACCOUNTING, QualStep.ACCOUNTING)
        pids = self.invoke(QualStep.MEMBERS, lambda: owner.members())
        if type(pids) is not tuple or len(pids) > 2 or not all(_u32(v) and v > 0 for v in pids):
            self.stop(QualStatus.UNKNOWN, QualFault.MEMBERS, QualStep.MEMBERS)
        self.members = len(pids)
        if len(pids) != 0:
            self.stop(QualStatus.FAIL, QualFault.MEMBERS, QualStep.MEMBERS)

    def drain_to_eof(self) -> None:
        """A FRESH positive EOF after the inventory; bounded by the shared turn budget."""
        for _ in range(2 * self.max_turns + 2):
            reads = self.reads
            if self.poll(QualStep.EOF):
                self.eof = 1
                return
            if self.reads == reads:
                if not self.turn(QualStep.EOF):  # an exited child cannot become alive
                    self.stop(QualStatus.UNKNOWN, QualFault.STATE, QualStep.EOF)
        self.stop(QualStatus.UNKNOWN, QualFault.TIME_BUDGET, QualStep.EOF)

    def final_line(self) -> LineResult:
        if self.overflow:
            return LineResult.OVERFLOW
        if not self.retained:
            return LineResult.ABSENT
        literal = _NATURAL_LINE if self.case is QualCase.NATURAL else _LIVE_LINE
        if bytes(self.retained) in (literal + b"\n", literal + b"\r\n"):
            return LineResult.MATCH
        return LineResult.MISMATCH

    def close_after_quiescence(self) -> None:
        """Only after full positive public quiescence; one close, never retried."""
        self.line = self.final_line()
        owner = self.owner
        result = self.invoke(QualStep.CLOSE, lambda: owner.close())
        if result is not None:
            self.close = CloseResult.INVALID_RETURN
            self.stop(QualStatus.FAIL, QualFault.CLOSE, QualStep.CLOSE)
        if self.state_now() is not OwnerState.CLOSED:
            self.close = CloseResult.NONE_NOT_CLOSED
            self.stop(QualStatus.FAIL, QualFault.CLOSE, QualStep.CLOSE)
        self.close = CloseResult.NONE_CLOSED
        if self.line is not LineResult.MATCH:
            self.stop(QualStatus.FAIL, QualFault.IO, None)  # cleanup done; never OBSERVED
        self.stop(QualStatus.OBSERVED, QualFault.NONE, None)

    # -------------------------------------------------------- pure report

    def report(self) -> QualReport:
        # The ordinary public ``state`` attribute is pure metadata, read also after a
        # control (the backend may have set HELD); never an SDK method, cleanup or clock.
        owner_state = self.state_now() if self.owner is not None else self.last_state
        return QualReport(
            case=self.case,
            status=self.status,
            fault=self.fault,
            step=self.step,
            owner_state=owner_state,
            exit_code=self.exit_code,
            total=self.total,
            active=self.active,
            members=self.members,
            stdout_bytes=min(self.consumed, MAX_TURNS * READ_CAP),
            line=self.line if self.line is not None else self.final_line(),
            eof=self.eof,
            close=self.close,
            terminate=self.terminate,
            turns=self.turns,
        )


def qualify(spec: object, custody: object, *, backend: types.ModuleType) -> QualReport:
    """One qualification over a fresh caller-owned custody (SQ1 + SQ2)."""
    if not _fresh(custody) or type(custody) is not QualCustody:
        return _refusal(QualStatus.REFUSED_CUSTODY, QualFault.CUSTODY)  # no write
    custody.claimed = True
    admitted = _admit(spec)
    if admitted is None:
        report = _refusal(QualStatus.REFUSED_INPUT, QualFault.INPUT)
        custody.report = report
        return report
    classes = _capture(backend)
    if classes is None:
        report = _refusal(QualStatus.REFUSED_INPUT, QualFault.BACKEND)
        custody.report = report
        return report
    case, application, directory, max_turns = admitted
    custody.backend = backend
    run = _Run(custody, case, max_turns)
    try:
        run.acquire(classes, application, directory)
        run.execute()
    except _Done:
        pass
    except Exception as error:
        if custody.error is None:
            custody.error = error
        run.status, run.fault = QualStatus.UNKNOWN, QualFault.INTERNAL
    except BaseException as control:
        if run.control is None:
            run.control = control
            custody.first_control = control
            if custody.error is None:
                custody.error = control
        run.status, run.fault = QualStatus.UNKNOWN, QualFault.CONTROL
    report = run.report()
    custody.report = report
    first = run.control
    if first is not None:
        raise first  # outside any except: identity, traceback and context untouched
    return report
