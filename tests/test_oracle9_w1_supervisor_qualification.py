"""W1 supervisor qualification oracles (root contract SQ1, 2026-11-14); RED-first.

Contract for the FUTURE ``docs/poc/oracle9_w1_supervisor_qualification.py``: the concrete
caller around the EXISTING public ``Owner`` of the pinned backend (10c9058f), not a new
owner, guardian or reducer framework. The module stays absent until the root reads these
oracles and freezes RED. It is loaded lazily as the FIRST statement of each feature case
(``qual_module()``), never at collection, in a fixture or inside ``pytest.raises``, so its
absence fails per case with ``FileNotFoundError``. ``test_sanity_*`` cases never load it.

The fake backend is a typed, single-threaded model of the PUBLIC backend surface only:
``Request(application, command_line, environment, directory)``, ``Owner(request)`` with
``state`` and ``setup/start/check_config/wait/exit_code/accounting/members/terminate/
available/read/close``, and ``Win32Error``. Its state checks mirror the backend
``_expect`` rules. Time model: only ``wait()`` lets fake time pass; each wait delivers at
most one scripted stdout chunk, a natural child exits after its scripted wait count with
all chunks delivered, a terminated child exits at the next wait, and EOF (``available()``
None) becomes visible ``eof_lag`` waits after exit with an empty buffer. One TURN is one
``wait(WAIT_MS)`` in any phase (SQ1 global turn counter). Private members (``ledger``,
``pid``, ``_accounting`` ...) record a violation when touched. Nothing here loads a DLL or
starts a process; ``load_backend`` cases only execute the pinned backend definitions.

Author: Claude2 (session 51ea0d85), claude-opus-5-5/medium, from SQ1.
Senff policy: AI-generated tests require human and security review before merge.
"""

from __future__ import annotations

import ast
import dataclasses
import functools
import hashlib
import runpy
import types
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

REPO = Path(__file__).resolve().parents[1]
QUAL_FILE = REPO / "docs/poc/oracle9_w1_supervisor_qualification.py"
BACKEND_FILE = REPO / "docs/poc/pg16_shell_admission_win32.py"
BACKEND_NAME = "pg16_shell_admission_win32.py"
BACKEND_SHA = "10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726"
APP = r"C:\fictional\w1\base\python.exe"  # fictional; never touched by qualify
DIR = r"C:\fictional\w1\work"
NATURAL = b"MASKGW-W1-SUPERVISOR-NATURAL"
LIVE = b"MASKGW-W1-SUPERVISOR-LIVE"
ENV = (("W1_NATIVE_PROBE", "1"),)
CANARY = "SYNTHETIC-SUPQUAL-CANARY-DO-NOT-RETAIN"
WAIT_MS = 50
CUSTODY_FIELDS = ("claimed", "backend", "request", "owner", "error", "first_control", "report")
PRIVATE_NAMES = frozenset(
    {
        "ledger",
        "pid",
        "held_reason",
        "quarantine",
        "_accounting",
        "_members",
        "_wait",
        "_peek",
        "_call",
        "_ok",
        "_close",
        "_api",
        "_hold",
        "_fail",
        "_guarded",
        "_interrupt",
    }
)
_ABSENT = object()
_RAISED = object()


# ---------------------------------------------------------------- lazy loading of the absent module


@functools.cache
def _qual_namespace() -> dict[str, Any]:
    return runpy.run_path(str(QUAL_FILE), run_name="_w1_supervisor_qualification_test")


def qual_module() -> Any:
    """FIRST statement of every feature case; never called inside pytest.raises."""
    return SimpleNamespace(**_qual_namespace())


# ---------------------------------------------------------------- controls and opaque values


class FalseCtl(BaseException):
    """Control whose truthiness is False; any bool() probe is recorded."""

    def __init__(self, probes: list[str]) -> None:
        super().__init__()
        self.probes = probes

    def __bool__(self) -> bool:
        self.probes.append("bool")
        return False


class BoomCtl(BaseException):
    """Control whose truthiness explodes; any bool() probe is recorded first."""

    def __init__(self, probes: list[str]) -> None:
        super().__init__()
        self.probes = probes

    def __bool__(self) -> bool:
        self.probes.append("bool")
        raise AssertionError("control truthiness inspected")


class Opaque:
    """Opaque SDK result: truthiness, repr, str, equality and int conversion are recorded."""

    def __init__(self, probes: list[str]) -> None:
        self.probes = probes

    def __bool__(self) -> bool:
        self.probes.append("bool")
        raise AssertionError("opaque truthiness inspected")

    def __repr__(self) -> str:
        self.probes.append("repr")
        return CANARY

    def __str__(self) -> str:
        self.probes.append("str")
        return CANARY

    def __eq__(self, other: object) -> bool:
        self.probes.append("eq")
        return False

    def __hash__(self) -> int:
        self.probes.append("hash")
        return 0

    def __index__(self) -> int:
        self.probes.append("index")
        return 0


def control_of(call: Callable[[], object]) -> BaseException | None:
    """Runs ``call`` expecting a non-Exception control; returns it by identity."""
    try:
        call()
    except Exception:
        return None
    except BaseException as control:
        return control
    return None


def refused(call: Callable[[], object]) -> bool:
    """True when ``call`` raises an ordinary Exception (any closed refusal type)."""
    try:
        call()
    except Exception:
        return True
    return False


# ---------------------------------------------------------------- faithful minimal fake backend


class FakeWin32Error(Exception):
    """Mirrors the backend Win32Error; the canary detects any leakage of its text."""

    def __init__(self, code: str) -> None:
        super().__init__(code + " " + CANARY)


@dataclasses.dataclass
class Script:
    chunks: list[bytes] = dataclasses.field(default_factory=list)
    natural_exit_after: int | None = 1  # waits; None means alive until terminated
    code: int = 0
    eof_lag: int = 0
    close_state: object = "CLOSED"
    returns: dict[str, list[object]] = dataclasses.field(default_factory=dict)
    raises: dict[str, list[BaseException]] = dataclasses.field(default_factory=dict)
    fail_states: dict[str, object] = dataclasses.field(default_factory=dict)
    custody: Any = None
    backend: Any = None
    calls: list[str] = dataclasses.field(default_factory=list)
    args: list[tuple[object, ...]] = dataclasses.field(default_factory=list)
    results: list[object] = dataclasses.field(default_factory=list)
    violations: list[str] = dataclasses.field(default_factory=list)
    owners: list[Any] = dataclasses.field(default_factory=list)
    requests: list[Any] = dataclasses.field(default_factory=list)
    buffer: bytearray = dataclasses.field(default_factory=bytearray)
    next_chunk: int = 0
    waits: int = 0
    exited: bool = False
    terminated: bool = False
    code_now: int | None = None
    waits_since_exit: int = 0
    last_available: object = -1
    consumed: int = 0
    owned_before_setup: bool | None = None
    consumed_at_terminate: int | None = None


class FakeRequestBase:
    """Same signature as the backend Request; its four data fields are immutable (frozen)."""

    SCRIPT: ClassVar[Script]
    __slots__ = ("application", "command_line", "directory", "environment")

    application: object
    command_line: object
    environment: object
    directory: object

    def __init__(
        self, application: object, command_line: object, environment: object, directory: object
    ) -> None:
        object.__setattr__(self, "application", application)
        object.__setattr__(self, "command_line", command_line)
        object.__setattr__(self, "environment", environment)
        object.__setattr__(self, "directory", directory)
        type(self).SCRIPT.requests.append(self)

    def __setattr__(self, name: str, value: object) -> None:
        raise dataclasses.FrozenInstanceError(f"cannot assign to field {name!r}")

    def __delattr__(self, name: str) -> None:
        raise dataclasses.FrozenInstanceError(f"cannot delete field {name!r}")

    def __repr__(self) -> str:
        return "Request(<redacted>)"


class FakeOwnerBase:
    """Public Owner surface over the scripted process/pipe model of the module docstring."""

    SCRIPT: ClassVar[Script]

    def __init__(self, request: object) -> None:
        self.request = request  # pure: no validation, DLL or handle (backend 365-383)
        self.state: object = "NEW"
        type(self).SCRIPT.owners.append(self)

    def __repr__(self) -> str:
        return "Owner(<redacted>)"

    # -- fake machinery (names never collide with the monitored private backend names)

    def _fk_enter(self, name: str, args: tuple[object, ...]) -> tuple[bool, object]:
        s = self.SCRIPT
        s.calls.append(name)
        s.args.append(args)
        s.results.append(_RAISED)
        if type(self.state) is str and self.state == "CLOSED":
            s.violations.append("after_closed:" + name)
            raise FakeWin32Error("WIN32_STATE")
        if name == "setup":
            c = s.custody
            s.owned_before_setup = (
                c is not None
                and getattr(c, "owner", None) is self
                and getattr(c, "request", None) is self.request
                and getattr(c, "backend", None) is s.backend
            )
        raise_queue = s.raises.get(name)
        if raise_queue:
            if name in s.fail_states:
                self.state = s.fail_states[name]
            raise raise_queue.pop(0)
        return_queue = s.returns.get(name)
        if return_queue:
            return True, self._fk_done(return_queue.pop(0))
        return False, None

    def _fk_done(self, value: object) -> object:
        self.SCRIPT.results[-1] = value
        return value

    def _fk_expect(self, *states: str) -> None:
        state = self.state
        if type(state) is str and state in states:
            return
        held = type(state) is str and state == "HELD"
        raise FakeWin32Error("WIN32_HELD" if held else "WIN32_STATE")

    def _fk_tick(self) -> None:
        s = self.SCRIPT
        if s.exited:
            s.waits_since_exit += 1
            return
        if s.next_chunk < len(s.chunks):
            s.buffer += s.chunks[s.next_chunk]
            s.next_chunk += 1
        s.waits += 1
        drained = s.next_chunk >= len(s.chunks)
        natural = s.natural_exit_after is not None and s.waits >= s.natural_exit_after
        if s.terminated or (natural and drained):
            s.exited = True
            s.code_now = 1 if s.terminated else s.code

    # -- public surface

    def setup(self) -> object:
        hit, value = self._fk_enter("setup", ())
        if hit:
            return value
        self._fk_expect("NEW")
        self.state = "READY"
        return self._fk_done(None)

    def start(self) -> object:
        hit, value = self._fk_enter("start", ())
        if hit:
            return value
        self._fk_expect("READY")
        self.state = "RUNNING"
        return self._fk_done(None)

    def check_config(self) -> object:
        hit, value = self._fk_enter("check_config", ())
        if hit:
            return value
        self._fk_expect("RUNNING")
        return self._fk_done(None)

    def wait(self, milliseconds: object) -> object:
        hit, value = self._fk_enter("wait", (milliseconds,))
        if hit:
            return value
        self._fk_expect("RUNNING")
        if type(milliseconds) is not int or not 0 <= milliseconds <= WAIT_MS:
            self.SCRIPT.violations.append("wait_argument")
            raise FakeWin32Error("WIN32_REQUEST")
        self._fk_tick()
        return self._fk_done(self.SCRIPT.exited)

    def exit_code(self) -> object:
        hit, value = self._fk_enter("exit_code", ())
        if hit:
            return value
        self._fk_expect("RUNNING")
        if not self.SCRIPT.exited:
            raise FakeWin32Error("WIN32_STATE")  # backend: only after a signaled wait
        return self._fk_done(self.SCRIPT.code_now)

    def accounting(self) -> object:
        hit, value = self._fk_enter("accounting", ())
        if hit:
            return value
        self._fk_expect("RUNNING")
        return self._fk_done((1, 0) if self.SCRIPT.exited else (1, 1))

    def members(self) -> object:
        hit, value = self._fk_enter("members", ())
        if hit:
            return value
        self._fk_expect("RUNNING")
        return self._fk_done(() if self.SCRIPT.exited else (4242,))

    def terminate(self) -> object:
        hit, value = self._fk_enter("terminate", ())
        if hit:
            return value
        self._fk_expect("RUNNING")
        s = self.SCRIPT
        s.terminated = True
        s.consumed_at_terminate = s.consumed
        return self._fk_done(None)

    def available(self) -> object:
        s = self.SCRIPT
        hit, value = self._fk_enter("available", ())
        if hit:
            s.last_available = value
            return value
        self._fk_expect("RUNNING")
        result: object
        if s.buffer:
            result = len(s.buffer)
        elif s.exited and s.waits_since_exit >= s.eof_lag:
            result = None
        else:
            result = 0
        s.last_available = result
        return self._fk_done(result)

    def read(self) -> object:
        s = self.SCRIPT
        hit, value = self._fk_enter("read", ())
        previous = s.last_available
        s.last_available = -1  # every read needs a FRESH positive available()
        if not (type(previous) is int and previous > 0):
            s.violations.append("read_without_positive_available")
        if hit:
            return value
        self._fk_expect("RUNNING")
        size = min(len(s.buffer), 4096)
        data = bytes(s.buffer[:size])
        del s.buffer[:size]
        s.consumed += size
        return self._fk_done(data)

    def close(self) -> object:
        hit, value = self._fk_enter("close", ())
        if hit:
            return value
        self._fk_expect("SETUP_FAILED", "READY", "LAUNCH_FAILED", "RUNNING")
        s = self.SCRIPT
        if self.state == "RUNNING" and (not s.exited or s.buffer):
            s.violations.append("close_not_quiescent")
        self.state = s.close_state
        return self._fk_done(None)

    # -- monitored private/PID surface: any access is a violation

    @property
    def ledger(self) -> object:
        self.SCRIPT.violations.append("private:ledger")
        return {}

    @property
    def pid(self) -> object:
        self.SCRIPT.violations.append("private:pid")
        return 4242

    @property
    def held_reason(self) -> object:
        self.SCRIPT.violations.append("private:held_reason")
        return None

    def _accounting(self) -> object:
        self.SCRIPT.violations.append("private:_accounting")
        return (1, 0)

    def _members(self) -> object:
        self.SCRIPT.violations.append("private:_members")
        return ()

    def _wait(self, _milliseconds: object) -> object:
        self.SCRIPT.violations.append("private:_wait")
        return True

    def _peek(self) -> object:
        self.SCRIPT.violations.append("private:_peek")
        return (None, True)


def make_backend(script: Script) -> types.ModuleType:
    class Request(FakeRequestBase):
        SCRIPT = script

    class Owner(FakeOwnerBase):
        SCRIPT = script

    module = types.ModuleType("_w1_fake_backend")
    module.__dict__.update(Request=Request, Owner=Owner, Win32Error=FakeWin32Error)
    script.backend = module
    return module


def raw_spec(q: Any, case: object, application: object, directory: object, turns: object) -> Any:
    """Unvalidated QualSpec instance, so qualify's own admission is exercised."""
    spec = object.__new__(q.QualSpec)
    object.__setattr__(spec, "case", case)
    object.__setattr__(spec, "application", application)
    object.__setattr__(spec, "directory", directory)
    object.__setattr__(spec, "max_turns", turns)
    return spec


def run_case(q: Any, script: Script, case: Any, max_turns: int = 40) -> tuple[Any, Any]:
    backend = make_backend(script)
    custody = q.QualCustody()
    script.custody = custody
    spec = raw_spec(q, case, APP, DIR, max_turns)
    report = q.qualify(spec, custody, backend=backend)
    return report, custody


def custody_snapshot(custody: object) -> tuple[object, ...]:
    return tuple(getattr(custody, name, _ABSENT) for name in CUSTODY_FIELDS)


def indexes(script: Script, name: str) -> list[int]:
    return [i for i, call in enumerate(script.calls) if call == name]


def wait_count(script: Script, milliseconds: int) -> int:
    return sum(
        1
        for name, args in zip(script.calls, script.args, strict=True)
        if name == "wait" and args == (milliseconds,)
    )


def fresh_eof_after_inventory(script: Script) -> bool:
    members = indexes(script, "members")
    closes = indexes(script, "close")
    if not members or not closes:
        return False
    return any(
        script.calls[i] == "available" and script.results[i] is None
        for i in range(members[-1] + 1, closes[0])
    )


def assert_report(q: Any, report: Any) -> None:
    """Closed SQ1 domains, redaction and the OBSERVED conjunction on every report."""
    assert type(report) is q.QualReport
    assert report.case is None or type(report.case) is q.QualCase
    assert type(report.status) is q.QualStatus and type(report.fault) is q.QualFault
    assert report.step is None or type(report.step) is q.QualStep
    assert type(report.owner_state) is q.OwnerState and type(report.line) is q.LineResult
    assert type(report.close) is q.CloseResult and type(report.terminate) is q.TermResult
    for name, high in (("exit_code", 2**32 - 1), ("total", 2), ("active", 2), ("members", 2)):
        value = getattr(report, name)
        assert value is None or (type(value) is int and 0 <= value <= high)
    for name, high in (("stdout_bytes", 400 * 4096), ("eof", 1), ("turns", 400)):
        value = getattr(report, name)
        assert type(value) is int and 0 <= value <= high
    assert report.eof in (0, 1)
    if report.status is q.QualStatus.OBSERVED:
        assert report.fault is q.QualFault.NONE and report.line is q.LineResult.MATCH
        assert report.eof == 1 and report.close is q.CloseResult.NONE_CLOSED
        assert report.owner_state is q.OwnerState.CLOSED
        assert (report.total, report.active, report.members) == (1, 0, 0)
    text = repr(report)
    for secret in (APP, DIR, CANARY, "MASKGW-W1", "W1_NATIVE_PROBE"):
        assert secret not in text


def assert_retained_without_close(q: Any, report: Any, custody: Any, script: Script) -> None:
    assert report.status in (q.QualStatus.FAIL, q.QualStatus.UNKNOWN)
    assert report.close is q.CloseResult.NOT_ATTEMPTED and "close" not in script.calls
    assert len(script.owners) == 1 and custody.owner is script.owners[0]
    assert custody.request is script.requests[0] and custody.report is report
    assert script.violations == []


def natural_script(**changes: Any) -> Script:
    script = Script(chunks=[NATURAL + b"\n"], natural_exit_after=1)
    for name, value in changes.items():
        setattr(script, name, value)
    return script


def live_script(**changes: Any) -> Script:
    script = Script(chunks=[LIVE + b"\n"], natural_exit_after=None)
    for name, value in changes.items():
        setattr(script, name, value)
    return script


# ---------------------------------------------------------------- independent fake sanities


def test_sanity_fake_natural_drive_matches_the_public_backend_model() -> None:
    script = natural_script()
    backend = make_backend(script)
    custody = SimpleNamespace(owner=None, request=None, backend=backend)
    script.custody = custody
    request = backend.Request(APP, "cmd", ENV, DIR)
    owner = backend.Owner(request)
    custody.owner, custody.request = owner, request
    assert owner.setup() is None and owner.state == "READY" and script.owned_before_setup is True
    assert owner.start() is None and owner.state == "RUNNING"
    assert owner.check_config() is None and owner.available() == 0
    assert owner.wait(WAIT_MS) is True and owner.exit_code() == 0
    assert owner.accounting() == (1, 0) and owner.members() == ()
    assert owner.available() == len(NATURAL) + 1 and owner.read() == NATURAL + b"\n"
    assert owner.available() is None
    assert owner.close() is None and owner.state == "CLOSED"
    assert script.violations == []


def test_sanity_fake_live_child_terminates_and_eof_lags() -> None:
    script = live_script(eof_lag=2)
    backend = make_backend(script)
    owner = backend.Owner(backend.Request(APP, "cmd", ENV, DIR))
    owner.setup()
    owner.start()
    assert owner.wait(WAIT_MS) is False and owner.available() == len(LIVE) + 1
    assert owner.read() == LIVE + b"\n" and owner.wait(0) is False
    with pytest.raises(FakeWin32Error):
        owner.exit_code()  # no signaled wait yet
    assert owner.accounting() == (1, 1) and owner.members() == (4242,)
    assert owner.terminate() is None and script.consumed_at_terminate == len(LIVE) + 1
    assert owner.wait(WAIT_MS) is True and owner.exit_code() == 1
    assert owner.available() == 0  # EOF not visible yet
    owner.wait(WAIT_MS)
    assert owner.available() == 0
    owner.wait(WAIT_MS)
    assert owner.available() is None
    assert owner.close() is None and script.violations == []


def test_sanity_fake_records_every_misuse() -> None:
    script = live_script()
    backend = make_backend(script)
    owner = backend.Owner(backend.Request(APP, "cmd", ENV, DIR))
    owner.setup()
    owner.start()
    owner.read()  # without a positive available()
    owner.wait(0)
    owner.available()
    owner.read()
    owner.read()  # stale positive available() is not reused
    assert owner.ledger == {} and owner.pid == 4242
    owner._accounting()
    owner.close()  # live child
    with pytest.raises(FakeWin32Error):
        owner.members()  # after CLOSED
    assert script.violations == [
        "read_without_positive_available",
        "read_without_positive_available",
        "private:ledger",
        "private:pid",
        "private:_accounting",
        "close_not_quiescent",
        "after_closed:members",
    ]


def test_sanity_fake_overrides_fail_states_and_opaque_probes() -> None:
    probes: list[str] = []
    error = FakeWin32Error("WIN32_JOB")
    script = natural_script(raises={"setup": [error]}, fail_states={"setup": "SETUP_FAILED"})
    backend = make_backend(script)
    owner = backend.Owner(backend.Request(APP, "cmd", ENV, DIR))
    with pytest.raises(FakeWin32Error) as caught:
        owner.setup()
    assert caught.value is error and owner.state == "SETUP_FAILED"
    assert script.results == [_RAISED]
    opaque = Opaque(probes)
    assert type(opaque) is Opaque and opaque is not None and probes == []
    assert repr(opaque) == CANARY and probes == ["repr"]
    script2 = natural_script(returns={"wait": [7]})
    owner2 = make_backend(script2).Owner(None)
    owner2.setup()
    owner2.start()
    assert owner2.wait(WAIT_MS) == 7 and script2.results[-1] == 7 and script2.waits == 0


def test_sanity_fake_request_is_frozen_like_the_backend_request() -> None:
    script = natural_script()
    request = make_backend(script).Request(APP, "cmd", ENV, DIR)
    assert script.requests == [request]
    for name in ("application", "command_line", "environment", "directory"):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(request, name, "changed")
        with pytest.raises(dataclasses.FrozenInstanceError):
            delattr(request, name)
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.extra = 1
    assert (request.application, request.command_line) == (APP, "cmd")
    assert (request.environment, request.directory) == (ENV, DIR)


def test_sanity_pinned_backend_artifact_and_fixed_candidate_path() -> None:
    raw = BACKEND_FILE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == BACKEND_SHA
    assert QUAL_FILE.parent == BACKEND_FILE.parent and BACKEND_FILE.name == BACKEND_NAME


# ---------------------------------------------------------------- closed surface


def test_closed_enums_constants_and_carriers() -> None:
    q = qual_module()
    expected = {
        "QualCase": ["NATURAL", "TERMINATE"],
        "QualStatus": ["OBSERVED", "FAIL", "UNKNOWN", "REFUSED_CUSTODY", "REFUSED_INPUT"],
        "QualStep": [
            "SETUP",
            "START",
            "CONFIG",
            "LIVE_LINE",
            "TERMINATE",
            "WAIT",
            "EXIT_CODE",
            "ACCOUNTING",
            "MEMBERS",
            "EOF",
            "CLOSE",
        ],
        "QualFault": [
            "NONE",
            "INPUT",
            "CUSTODY",
            "BACKEND",
            "SETUP",
            "START",
            "CONFIG",
            "IO",
            "TIME_BUDGET",
            "EXIT_CODE",
            "ACCOUNTING",
            "MEMBERS",
            "CLOSE",
            "CONTROL",
            "STATE",
            "INTERNAL",
        ],
        "OwnerState": [
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
        ],
        "LineResult": ["MATCH", "MISMATCH", "OVERFLOW", "ABSENT"],
        "CloseResult": [
            "NOT_ATTEMPTED",
            "NONE_CLOSED",
            "NONE_NOT_CLOSED",
            "INVALID_RETURN",
            "RAISED",
        ],
        "TermResult": ["NOT_REQUESTED", "RETURNED", "INVALID_RETURN", "RAISED"],
    }
    for name, members in expected.items():
        assert [member.name for member in vars(q)[name]] == members
    assert type(q.OUTPUT_CAP) is int and q.OUTPUT_CAP == 4096
    assert type(q.READ_CAP) is int and q.READ_CAP == 4096
    assert type(q.WAIT_MS) is int and q.WAIT_MS == WAIT_MS
    fresh = q.QualCustody()
    assert custody_snapshot(fresh) == (False, None, None, None, None, None, None)
    assert not hasattr(fresh, "__dict__")
    assert not hasattr(raw_spec(q, None, APP, DIR, 1), "__dict__")
    spec = q.QualSpec(case=q.QualCase.NATURAL, application=APP, directory=DIR, max_turns=5)
    with pytest.raises(AttributeError):
        spec.max_turns = 6
    for text in (repr(spec), repr(fresh)):
        assert APP not in text and DIR not in text


# ---------------------------------------------------------------- Q2/Q3 positive canaries


NATURAL_CHUNKS = {
    "lf": [NATURAL + b"\n"],
    "crlf": [NATURAL + b"\r\n"],
    "fragments": [b"MASKGW-W1-", b"SUPERVISOR-", b"NATURAL\r", b"\n"],
    "bytewise": [bytes([byte]) for byte in NATURAL + b"\n"],
}


@pytest.mark.parametrize("variant", sorted(NATURAL_CHUNKS))
def test_q2_natural_canary_is_observed_in_exact_public_order(variant: str) -> None:
    q = qual_module()
    chunks = NATURAL_CHUNKS[variant]
    script = Script(chunks=list(chunks), natural_exit_after=len(chunks))
    report, custody = run_case(q, script, q.QualCase.NATURAL, max_turns=80)
    assert_report(q, report)
    assert report.status is q.QualStatus.OBSERVED and report.case is q.QualCase.NATURAL
    assert report.exit_code == 0 and report.terminate is q.TermResult.NOT_REQUESTED
    assert report.stdout_bytes == len(b"".join(chunks)) and 1 <= report.turns <= 80
    assert report.turns == wait_count(script, WAIT_MS) and wait_count(script, 0) == 0
    assert len(indexes(script, "read")) <= wait_count(script, WAIT_MS)  # <=1 read per turn
    calls = script.calls
    assert calls[:3] == ["setup", "start", "check_config"] and "terminate" not in calls
    assert indexes(script, "close") == [len(calls) - 1]
    assert calls.index("exit_code") < calls.index("accounting") < calls.index("members")
    assert fresh_eof_after_inventory(script) and script.owned_before_setup is True
    assert script.violations == [] and len(script.requests) == len(script.owners) == 1
    request = script.requests[0]
    assert custody.backend is script.backend and custody.request is request
    assert custody.owner is script.owners[0] and custody.report is report
    assert custody.claimed is True and custody.error is None and custody.first_control is None
    assert type(request.application) is str and request.application == APP
    assert type(request.directory) is str and request.directory == DIR
    assert type(request.environment) is tuple and request.environment == ENV
    assert all(type(item) is tuple for item in request.environment)
    line = request.command_line
    assert type(line) is str and len(line) <= 2048 and APP in line and "-I -B -S" in line
    assert "MASKGW-W1-SUPERVISOR-NATURAL" in line and "time.sleep" not in line


def test_q3_terminate_canary_observes_live_then_one_terminate_then_positive_exit() -> None:
    q = qual_module()
    script = live_script()
    report, custody = run_case(q, script, q.QualCase.TERMINATE)
    assert_report(q, report)
    assert report.status is q.QualStatus.OBSERVED and report.case is q.QualCase.TERMINATE
    assert report.exit_code == 1 and report.terminate is q.TermResult.RETURNED
    assert report.stdout_bytes == len(LIVE) + 1
    assert wait_count(script, 0) == 1  # the immediate alive probe, not a budget turn (SQ2)
    assert report.turns == wait_count(script, WAIT_MS)
    assert len(indexes(script, "read")) <= wait_count(script, WAIT_MS)  # <=1 read per turn
    terminates = indexes(script, "terminate")
    assert len(terminates) == 1
    before = terminates[0] - 1
    assert script.calls[before] == "wait" and script.args[before] == (0,)
    assert script.results[before] is False  # positive alive observation right before
    assert script.consumed_at_terminate == len(LIVE) + 1  # full LIVE marker first
    after = script.calls[terminates[0] + 1 :]
    assert after.index("exit_code") < after.index("accounting") < after.index("members")
    assert fresh_eof_after_inventory(script)
    assert indexes(script, "close") == [len(script.calls) - 1]
    line = script.requests[0].command_line
    assert "MASKGW-W1-SUPERVISOR-LIVE" in line and "time.sleep(30)" in line and "-I -B -S" in line
    assert script.violations == [] and custody.report is report


@pytest.mark.parametrize(
    ("chunks", "exit_after", "line"),
    [
        ([b"MASKGW-W1-SUPERVISOR-LIVX\n"], None, "MISMATCH"),
        ([LIVE + b"\n"], 1, "MATCH"),  # child exits by itself before any terminate
    ],
)
def test_terminate_requires_full_live_marker_and_a_live_child(
    chunks: list[bytes], exit_after: int | None, line: str
) -> None:
    q = qual_module()
    script = Script(chunks=list(chunks), natural_exit_after=exit_after)
    report, _custody = run_case(q, script, q.QualCase.TERMINATE)
    assert_report(q, report)
    assert report.status is q.QualStatus.FAIL and "terminate" not in script.calls
    assert report.terminate is q.TermResult.NOT_REQUESTED  # an unexpected exit is no kill
    assert report.line is getattr(q.LineResult, line)
    assert script.violations == []


def test_partial_live_marker_exhausts_the_budget_without_terminate_or_close() -> None:
    q = qual_module()
    script = Script(chunks=[b"MASKGW-W1-SUPERVISOR-LI"], natural_exit_after=None)
    report, custody = run_case(q, script, q.QualCase.TERMINATE, max_turns=10)
    assert_report(q, report)
    assert report.status is q.QualStatus.UNKNOWN and report.fault is q.QualFault.TIME_BUDGET
    assert "terminate" not in script.calls and wait_count(script, WAIT_MS) <= 10
    assert report.owner_state is q.OwnerState.RUNNING
    assert_retained_without_close(q, report, custody, script)


# ---------------------------------------------------------------- global turn budget


@pytest.mark.parametrize(("turns", "observed"), [(6, False), (20, True)])
def test_one_global_turn_budget_across_live_wait_and_eof_drain(turns: int, observed: bool) -> None:
    """LIVE needs 5 waits, exit 1 and EOF 3 more: each phase fits 6, the sum does not."""
    q = qual_module()
    script = Script(chunks=[b"", b"", b"", b"", LIVE + b"\n"], natural_exit_after=None, eof_lag=3)
    report, custody = run_case(q, script, q.QualCase.TERMINATE, max_turns=turns)
    assert_report(q, report)
    assert report.turns <= turns and wait_count(script, WAIT_MS) <= turns
    if observed:
        assert report.status is q.QualStatus.OBSERVED and script.violations == []
        return
    assert report.status is q.QualStatus.UNKNOWN and report.fault is q.QualFault.TIME_BUDGET
    assert report.eof == 0 and report.owner_state is q.OwnerState.RUNNING
    assert_retained_without_close(q, report, custody, script)


def test_natural_child_that_never_exits_is_unknown_without_terminate_or_close() -> None:
    q = qual_module()
    script = natural_script(natural_exit_after=None)
    report, custody = run_case(q, script, q.QualCase.NATURAL, max_turns=7)
    assert_report(q, report)
    assert report.status is q.QualStatus.UNKNOWN and report.fault is q.QualFault.TIME_BUDGET
    assert "terminate" not in script.calls and wait_count(script, WAIT_MS) <= 7
    assert_retained_without_close(q, report, custody, script)


# ---------------------------------------------------------------- Q4/Q5 channel semantics


def test_empty_read_is_never_eof_and_never_closes() -> None:
    q = qual_module()
    script = natural_script(returns={"read": [b""] * 2000})
    report, custody = run_case(q, script, q.QualCase.NATURAL, max_turns=8)
    assert_report(q, report)
    assert report.eof == 0 and report.status is not q.QualStatus.OBSERVED
    assert len(indexes(script, "read")) <= 4 * 8 + 8
    assert wait_count(script, WAIT_MS) <= 8  # never a wait(50) beyond max_turns (SQ2)
    assert len(indexes(script, "read")) <= wait_count(script, WAIT_MS)  # <=1 read per turn
    assert_retained_without_close(q, report, custody, script)


def test_available_zero_never_reads_and_every_read_follows_a_fresh_positive_available() -> None:
    q = qual_module()
    script = Script(chunks=[b"", b"", b"", NATURAL + b"\n"], natural_exit_after=4)
    report, _custody = run_case(q, script, q.QualCase.NATURAL)
    assert_report(q, report)
    assert report.status is q.QualStatus.OBSERVED and script.violations == []
    positives = sum(
        1
        for name, result in zip(script.calls, script.results, strict=True)
        if name == "available" and type(result) is int and result > 0
    )
    assert len(indexes(script, "read")) == positives


CHANNEL_FAILURES = {
    "absent": ([], "ABSENT"),
    "wrong-text": ([b"MASKGW-W1-SUPERVISOR-NATURAX\n"], "MISMATCH"),
    "two-lines": ([NATURAL + b"\n", NATURAL + b"\n"], "MISMATCH"),
    "no-newline": ([NATURAL], "MISMATCH"),
    "bare-cr": ([NATURAL + b"\r"], "MISMATCH"),
    "overflow": ([NATURAL + b"\n", b"x" * 5000], "OVERFLOW"),
}


@pytest.mark.parametrize("case", sorted(CHANNEL_FAILURES))
def test_channel_fail_cleans_up_only_after_full_public_quiescence_and_never_observes(
    case: str,
) -> None:
    q = qual_module()
    chunks, line = CHANNEL_FAILURES[case]
    script = Script(chunks=list(chunks), natural_exit_after=max(len(chunks), 1))
    report, custody = run_case(q, script, q.QualCase.NATURAL)
    assert_report(q, report)
    assert report.status is q.QualStatus.FAIL and report.fault is q.QualFault.IO
    assert report.line is getattr(q.LineResult, line)
    assert report.exit_code == 0 and (report.total, report.active, report.members) == (1, 0, 0)
    assert report.eof == 1 and report.close is q.CloseResult.NONE_CLOSED
    assert report.owner_state is q.OwnerState.CLOSED and len(indexes(script, "close")) == 1
    assert fresh_eof_after_inventory(script) and script.violations == []
    assert custody.owner is script.owners[0] and custody.report is report


# ---------------------------------------------------------------- Q6 uncertainty never closes


Uncertain = tuple[dict[str, list[object]], dict[str, list[BaseException]], str | None]


def _uncertain_cases() -> dict[str, Uncertain]:
    error = FakeWin32Error("WIN32_TREE")
    return {
        "accounting-total-2": ({"accounting": [(2, 0)]}, {}, "ACCOUNTING"),
        "accounting-bool": ({"accounting": [(True, 0)]}, {}, "ACCOUNTING"),
        "accounting-list": ({"accounting": [[1, 0]]}, {}, "ACCOUNTING"),
        "accounting-raises": ({}, {"accounting": [error]}, "ACCOUNTING"),
        "members-live": ({"members": [(7,)]}, {}, "MEMBERS"),
        "members-list": ({"members": [[]]}, {}, "MEMBERS"),
        "members-raises": ({}, {"members": [error]}, "MEMBERS"),
        "exit-code-bool": ({"exit_code": [True]}, {}, "EXIT_CODE"),
        "exit-code-wrong": ({"exit_code": [3]}, {}, "EXIT_CODE"),
        "exit-code-huge": ({"exit_code": [2**32]}, {}, "EXIT_CODE"),
        "exit-code-negative": ({"exit_code": [-1]}, {}, "EXIT_CODE"),
        "accounting-oversize": ({"accounting": [(2**32, 0)]}, {}, "ACCOUNTING"),
        "accounting-negative": ({"accounting": [(1, -1)]}, {}, "ACCOUNTING"),
        "accounting-three": ({"accounting": [(1, 0, 0)]}, {}, "ACCOUNTING"),
        "members-bool": ({"members": [(True,)]}, {}, "MEMBERS"),
        "members-negative": ({"members": [(-1,)]}, {}, "MEMBERS"),
        "members-oversize": ({"members": [(2**32,)]}, {}, "MEMBERS"),
        "available-over-dword": ({"available": [2**32]}, {}, None),
        "config-raises": ({}, {"check_config": [error]}, "CONFIG"),
        "wait-int": ({"wait": [1]}, {}, None),
        "available-bool": ({"available": [True]}, {}, None),
        "available-negative": ({"available": [-1]}, {}, None),
        "read-bytearray": ({"available": [3], "read": [bytearray(b"MAS")]}, {}, None),
        "read-oversized": ({"available": [5000], "read": [b"x" * 5000]}, {}, None),
        "available-raises": ({}, {"available": [error]}, None),
    }


UNCERTAIN = _uncertain_cases()


@pytest.mark.parametrize("case", sorted(UNCERTAIN))
def test_inventory_api_or_type_uncertainty_retains_custody_and_never_closes(case: str) -> None:
    q = qual_module()
    returns, raises, fault = UNCERTAIN[case]
    raised = [error for queue in raises.values() for error in queue]
    script = natural_script(
        returns={k: list(v) for k, v in returns.items()},
        raises={k: list(v) for k, v in raises.items()},
    )
    report, custody = run_case(q, script, q.QualCase.NATURAL)
    assert_report(q, report)
    assert_retained_without_close(q, report, custody, script)
    if fault is not None:
        assert report.fault is getattr(q.QualFault, fault)
    assert report.owner_state is q.OwnerState.RUNNING  # actual state; HELD never fabricated
    if raised:
        assert custody.error is raised[0]  # the original SDK error, by identity
    else:
        assert custody.error is None  # an invalid return is not an invented exception


@pytest.mark.parametrize("method", ["wait", "available", "accounting", "members", "exit_code"])
def test_opaque_sdk_results_are_never_inspected(method: str) -> None:
    q = qual_module()
    probes: list[str] = []
    script = natural_script(returns={method: [Opaque(probes)]})
    report, custody = run_case(q, script, q.QualCase.NATURAL)
    assert_report(q, report)
    assert probes == []
    assert_retained_without_close(q, report, custody, script)


def test_original_sdk_error_is_retained_by_identity_and_never_leaks() -> None:
    q = qual_module()
    error = FakeWin32Error("WIN32_TREE")
    script = natural_script(raises={"accounting": [error]})
    report, custody = run_case(q, script, q.QualCase.NATURAL)
    assert_report(q, report)
    assert custody.error is error and error.__context__ is None
    assert CANARY not in repr(custody) and APP not in repr(custody)
    assert_retained_without_close(q, report, custody, script)


# ---------------------------------------------------------------- Q7 close outcomes


@pytest.mark.parametrize("kind", ["invalid-return", "raises", "not-closed", "opaque-state"])
def test_failed_or_invalid_close_is_retained_once_and_never_observed(kind: str) -> None:
    q = qual_module()
    probes: list[str] = []
    expected = {
        "invalid-return": ("INVALID_RETURN", "RUNNING"),
        "raises": ("RAISED", "RUNNING"),
        "not-closed": ("NONE_NOT_CLOSED", "RUNNING"),
        "opaque-state": ("NONE_NOT_CLOSED", "OTHER"),
    }[kind]
    script = natural_script()
    if kind == "invalid-return":
        script.returns = {"close": [0]}
    elif kind == "raises":
        script.raises = {"close": [FakeWin32Error("WIN32_CLOSE")]}
    elif kind == "not-closed":
        script.close_state = "RUNNING"
    else:
        script.close_state = Opaque(probes)
    report, custody = run_case(q, script, q.QualCase.NATURAL)
    assert_report(q, report)
    assert report.status in (q.QualStatus.FAIL, q.QualStatus.UNKNOWN)
    assert report.close is getattr(q.CloseResult, expected[0])
    assert report.owner_state is getattr(q.OwnerState, expected[1])
    assert len(indexes(script, "close")) == 1 and script.calls[-1] == "close"
    assert custody.owner is script.owners[0] and probes == [] and script.violations == []


# ---------------------------------------------------------------- Q8 setup/start states


@pytest.mark.parametrize(
    ("method", "state", "expected", "fault"),
    [
        ("setup", "SETUP_FAILED", "SETUP_FAILED", "SETUP"),
        ("setup", "HELD", "HELD", "SETUP"),
        ("setup", "WEIRD", "OTHER", "SETUP"),
        ("start", "LAUNCH_FAILED", "LAUNCH_FAILED", "START"),
        ("start", "HELD", "HELD", "START"),
    ],
)
def test_setup_or_start_failure_reports_the_actual_public_state(
    method: str, state: str, expected: str, fault: str
) -> None:
    q = qual_module()
    script = natural_script(
        raises={method: [FakeWin32Error("WIN32_JOB")]}, fail_states={method: state}
    )
    report, custody = run_case(q, script, q.QualCase.NATURAL)
    assert_report(q, report)
    assert report.owner_state is getattr(q.OwnerState, expected)
    assert report.fault is getattr(q.QualFault, fault)
    assert script.calls[-1] == method and script.calls.count(method) == 1
    assert_retained_without_close(q, report, custody, script)


def test_opaque_state_after_failed_setup_is_other_without_inspection() -> None:
    q = qual_module()
    probes: list[str] = []
    script = natural_script(
        raises={"setup": [FakeWin32Error("WIN32_JOB")]}, fail_states={"setup": Opaque(probes)}
    )
    report, custody = run_case(q, script, q.QualCase.NATURAL)
    assert_report(q, report)
    assert report.owner_state is q.OwnerState.OTHER and probes == []
    assert_retained_without_close(q, report, custody, script)


@pytest.mark.parametrize("method", ["setup", "start", "check_config", "terminate"])
def test_invalid_none_api_return_is_never_success(method: str) -> None:
    q = qual_module()
    script = live_script(returns={method: [7]})
    report, custody = run_case(q, script, q.QualCase.TERMINATE)
    assert_report(q, report)
    assert report.status in (q.QualStatus.FAIL, q.QualStatus.UNKNOWN)
    if method == "terminate":
        assert report.terminate is q.TermResult.INVALID_RETURN
    assert_retained_without_close(q, report, custody, script)


def test_terminate_raising_is_retained_without_close() -> None:
    q = qual_module()
    script = live_script(raises={"terminate": [FakeWin32Error("WIN32_TERMINATE")]})
    report, custody = run_case(q, script, q.QualCase.TERMINATE)
    assert_report(q, report)
    assert report.terminate is q.TermResult.RAISED and script.calls.count("terminate") == 1
    assert_retained_without_close(q, report, custody, script)


# ---------------------------------------------------------------- Q0 refusals before construction


def _bad_specs(q: Any) -> dict[str, Any]:
    natural = q.QualCase.NATURAL
    return {
        "not-a-spec": SimpleNamespace(case=natural, application=APP, directory=DIR, max_turns=5),
        "case-str": raw_spec(q, "NATURAL", APP, DIR, 5),
        "case-none": raw_spec(q, None, APP, DIR, 5),
        "app-relative": raw_spec(q, natural, "python.exe", DIR, 5),
        "app-drive-relative": raw_spec(q, natural, "C:python.exe", DIR, 5),
        "app-unc": raw_spec(q, natural, r"\\server\share\python.exe", DIR, 5),
        "app-quote": raw_spec(q, natural, 'C:\\x"\\python.exe', DIR, 5),
        "app-lf": raw_spec(q, natural, "C:\\x\n\\python.exe", DIR, 5),
        "app-cr": raw_spec(q, natural, "C:\\x\r\\python.exe", DIR, 5),
        "app-nul": raw_spec(q, natural, "C:\\x\x00\\python.exe", DIR, 5),
        "app-empty": raw_spec(q, natural, "", DIR, 5),
        "app-long": raw_spec(q, natural, "C:\\" + "a" * 1022, DIR, 5),
        "app-bytes": raw_spec(q, natural, APP.encode(), DIR, 5),
        "app-device": raw_spec(q, natural, "\\\\?\\C:\\x\\python.exe", DIR, 5),
        "dir-relative": raw_spec(q, natural, APP, "work", 5),
        "dir-quote": raw_spec(q, natural, APP, 'C:\\w"', 5),
        "dir-unc": raw_spec(q, natural, APP, "\\\\server\\share\\work", 5),
        "dir-device": raw_spec(q, natural, APP, "\\\\.\\C:\\work", 5),
        "dir-nul": raw_spec(q, natural, APP, "C:\\w\x00", 5),
        "turns-zero": raw_spec(q, natural, APP, DIR, 0),
        "turns-401": raw_spec(q, natural, APP, DIR, 401),
        "turns-bool": raw_spec(q, natural, APP, DIR, True),
        "turns-float": raw_spec(q, natural, APP, DIR, 5.0),
        "turns-str": raw_spec(q, natural, APP, DIR, "5"),
    }


BAD_SPEC_NAMES = (
    "not-a-spec",
    "case-str",
    "case-none",
    "app-relative",
    "app-drive-relative",
    "app-unc",
    "app-quote",
    "app-lf",
    "app-cr",
    "app-nul",
    "app-empty",
    "app-long",
    "app-bytes",
    "app-device",
    "dir-relative",
    "dir-quote",
    "dir-unc",
    "dir-device",
    "dir-nul",
    "turns-zero",
    "turns-401",
    "turns-bool",
    "turns-float",
    "turns-str",
)


@pytest.mark.parametrize("name", BAD_SPEC_NAMES)
def test_invalid_spec_refuses_before_request_or_owner(name: str) -> None:
    q = qual_module()
    spec = _bad_specs(q)[name]
    script = natural_script()
    backend = make_backend(script)
    custody = q.QualCustody()
    script.custody = custody
    report = q.qualify(spec, custody, backend=backend)
    assert_report(q, report)
    assert report.status is q.QualStatus.REFUSED_INPUT and report.fault is q.QualFault.INPUT
    assert report.owner_state is q.OwnerState.EMPTY
    assert script.requests == [] and script.owners == [] and script.calls == []
    assert custody.request is None and custody.owner is None
    assert custody.report is None or custody.report is report


def _bad_backends() -> dict[str, object]:
    def without(name: str) -> types.ModuleType:
        module = make_backend(natural_script())
        del module.__dict__[name]
        return module

    not_type = make_backend(natural_script())
    not_type.__dict__["Owner"] = object()
    return {
        "not-module": SimpleNamespace(**vars(make_backend(natural_script()))),
        "no-owner": without("Owner"),
        "no-request": without("Request"),
        "no-error": without("Win32Error"),
        "owner-not-type": not_type,
    }


@pytest.mark.parametrize(
    "name", ["not-module", "no-owner", "no-request", "no-error", "owner-not-type"]
)
def test_invalid_backend_refuses_before_request_or_owner(name: str) -> None:
    q = qual_module()
    backend = _bad_backends()[name]
    custody = q.QualCustody()
    spec = raw_spec(q, q.QualCase.NATURAL, APP, DIR, 5)
    report = q.qualify(spec, custody, backend=backend)
    assert_report(q, report)
    assert report.status is q.QualStatus.REFUSED_INPUT and report.fault is q.QualFault.BACKEND
    assert report.owner_state is q.OwnerState.EMPTY
    assert custody.request is None and custody.owner is None


@pytest.mark.parametrize("kind", ["foreign", "claimed", "errored", "subclass", "reused"])
def test_invalid_or_reused_custody_is_refused_without_any_write(kind: str) -> None:
    q = qual_module()
    script = natural_script()
    backend = make_backend(script)
    custody: Any
    if kind == "foreign":
        custody = SimpleNamespace(**dict.fromkeys(CUSTODY_FIELDS))
    elif kind == "subclass":
        custody = type("SubCustody", (q.QualCustody,), {"__slots__": ()})()
    else:
        custody = q.QualCustody()
        if kind == "claimed":
            custody.claimed = True
        elif kind == "errored":
            custody.error = FakeWin32Error("WIN32_STATE")
        else:
            script.custody = custody
            first = q.qualify(
                raw_spec(q, q.QualCase.NATURAL, APP, DIR, 40), custody, backend=backend
            )
            assert first.status is q.QualStatus.OBSERVED
    before = custody_snapshot(custody)
    calls_before = len(script.calls)
    requests_before = len(script.requests)
    report = q.qualify(raw_spec(q, q.QualCase.NATURAL, APP, DIR, 5), custody, backend=backend)
    assert_report(q, report)
    assert report.status is q.QualStatus.REFUSED_CUSTODY and report.fault is q.QualFault.CUSTODY
    assert report.case is None or report.case is q.QualCase.NATURAL
    assert all(x is y for x, y in zip(before, custody_snapshot(custody), strict=True))
    assert len(script.calls) == calls_before and len(script.requests) == requests_before


# ---------------------------------------------------------------- Q9 first control


CONTROL_POINTS = (
    "setup",
    "start",
    "check_config",
    "wait",
    "available",
    "read",
    "exit_code",
    "accounting",
    "members",
    "terminate",
    "close",
)


@pytest.mark.parametrize("method", CONTROL_POINTS)
@pytest.mark.parametrize("ctl_type", [FalseCtl, BoomCtl])
def test_first_control_is_reraised_by_identity_with_report_and_zero_later_sdk_calls(
    method: str, ctl_type: Callable[[list[str]], BaseException]
) -> None:
    q = qual_module()
    probes: list[str] = []
    ctl = ctl_type(probes)
    case = q.QualCase.TERMINATE if method == "terminate" else q.QualCase.NATURAL
    script = live_script() if method == "terminate" else natural_script()
    script.raises = {method: [ctl]}
    backend = make_backend(script)
    custody = q.QualCustody()
    script.custody = custody
    spec = raw_spec(q, case, APP, DIR, 40)
    raised = control_of(lambda: q.qualify(spec, custody, backend=backend))
    assert raised is ctl and probes == []
    assert ctl.__context__ is None and ctl.__cause__ is None
    assert script.calls[-1] == method  # zero SDK calls after the first control
    assert custody.first_control is ctl and custody.error is ctl
    report = custody.report
    assert report is not None
    assert_report(q, report)
    assert report.status is q.QualStatus.UNKNOWN and report.fault is q.QualFault.CONTROL
    assert report.close in (q.CloseResult.NOT_ATTEMPTED, q.CloseResult.RAISED)
    assert custody.owner is script.owners[0] and script.violations == []


# ---------------------------------------------------------------- Q10 redaction and immutability


def test_reports_are_immutable_and_reprs_redacted_on_success_and_failure() -> None:
    q = qual_module()
    ok_script = natural_script()
    ok, ok_custody = run_case(q, ok_script, q.QualCase.NATURAL)
    bad_script = natural_script(raises={"members": [FakeWin32Error("WIN32_TREE")]})
    bad, bad_custody = run_case(q, bad_script, q.QualCase.NATURAL)
    for report, custody in ((ok, ok_custody), (bad, bad_custody)):
        assert_report(q, report)
        with pytest.raises(AttributeError):
            report.status = q.QualStatus.OBSERVED
        text = repr(custody) + repr(raw_spec(q, q.QualCase.NATURAL, APP, DIR, 5))
        for secret in (APP, DIR, CANARY, "MASKGW-W1", "W1_NATIVE_PROBE"):
            assert secret not in text
    assert ok.status is q.QualStatus.OBSERVED and bad.status is not q.QualStatus.OBSERVED
    for field in dataclasses.fields(ok):
        assert type(getattr(ok, field.name)) is not str  # enums/ints/None only


# ---------------------------------------------------------------- loader integrity


def _copy_pair(tmp_path: Path, backend_bytes: bytes | None) -> Path:
    qual = tmp_path / QUAL_FILE.name
    qual.write_bytes(QUAL_FILE.read_bytes())  # source-identical copy; absent source fails here
    if backend_bytes is not None:
        (tmp_path / BACKEND_NAME).write_bytes(backend_bytes)
    return qual


def test_load_backend_returns_the_pinned_public_namespace() -> None:
    q = qual_module()
    module = q.load_backend()
    assert type(module) is types.ModuleType
    for name in ("Request", "Owner", "Win32Error"):
        assert isinstance(vars(module)[name], type)
    assert issubclass(vars(module)["Win32Error"], Exception)


def test_load_backend_reads_the_fixed_sibling_and_executes_only_checked_bytes(
    tmp_path: Path,
) -> None:
    q = qual_module()
    assert callable(q.load_backend)
    good_dir = tmp_path / "good"
    good_dir.mkdir()
    good = _copy_pair(good_dir, BACKEND_FILE.read_bytes())
    module = runpy.run_path(str(good), run_name="_w1_supqual_copy")["load_backend"]()
    assert type(module) is types.ModuleType and isinstance(vars(module)["Owner"], type)

    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    marker = bad_dir / "tamper-executed"
    payload = f"\nimport pathlib as _tamper\n_tamper.Path({str(marker)!r}).write_text('x')\n"
    tampered = BACKEND_FILE.read_bytes() + payload.encode("utf-8")
    ast.parse(tampered.decode("utf-8"))  # valid Python: a refusal cannot be a SyntaxError
    compile(tampered, str(bad_dir / BACKEND_NAME), "exec")
    bad = _copy_pair(bad_dir, tampered)
    namespace = runpy.run_path(str(bad), run_name="_w1_supqual_tampered")
    assert not marker.exists()  # importing the qualifier never loads the backend
    assert refused(namespace["load_backend"])  # closed refusal before any execution
    assert not marker.exists()

    missing_dir = tmp_path / "missing"
    missing_dir.mkdir()
    missing = _copy_pair(missing_dir, None)
    loader = runpy.run_path(str(missing), run_name="_w1_supqual_missing")["load_backend"]
    assert refused(loader)  # absent sibling is refused


# ---------------------------------------------------------------- Q11 static shape


def test_static_shape_public_owner_only_and_fixed_pinned_loader() -> None:
    q = qual_module()
    assert callable(q.qualify)
    source = QUAL_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_modules = {
        "subprocess",
        "threading",
        "socket",
        "ctypes",
        "asyncio",
        "signal",
        "multiprocessing",
        "importlib",
        "runpy",
        "time",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not {alias.name.split(".")[0] for alias in node.names} & forbidden_modules
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden_modules
            assert (node.module or "").split(".")[0] != "docs"
        if isinstance(node, ast.Attribute):
            assert node.attr not in PRIVATE_NAMES and node.attr not in {"kill", "getpid"}
        if isinstance(node, ast.While):
            assert not (isinstance(node.test, ast.Constant) and node.test.value is True)
    assert BACKEND_SHA in source and BACKEND_NAME in source
    assert "W1_NATIVE_PROBE" in source
