"""W1 Oracle laboratory main, D2: root, bindings, containment and physical hold.

MAIN-DESIGN 080c37ab plus MAIN-DESIGN-REVIEW and MAIN-TESTS-REVIEW (R1). Importing
this module only defines names. The single entry is the ``__main__`` guard, which
builds the real System and calls ``entry``. Every OS effect goes through the
closed ``System`` seam held by the caller-created ``MainRoot``.

Trusted public source is loaded before the guard (declared bootstrap exception:
it is needed to build the exact Owner). Transitive imports are not claimed to be
free of implicit physical effects, and Linux admission (VmSize, Threads: 1) is
not measured here. LAB_INIT and the pure capture stay after the guard, inside
the pinned driver. This is a one-attempt laboratory policy, not the Gateway's
production shutdown policy. Object facts are not kernel proof.
"""

from __future__ import annotations

import enum
import errno
import hashlib
import os
import select
import signal
import socket
import stat
import sys
import threading
import time
import types
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, NoReturn

from maskgw.pgwire.transport import RawChannel, TransportLimits
from maskgw.runtime.budget import BudgetLedger, ReservationKind
from maskgw.runtime.linux_guard import protect_process
from maskgw.runtime.worker_session import SessionState, WorkerSession

MAIN_PATH: Final = "/opt/maskgw/lab/oracle9_w1_main.py"
DRIVER_PATH: Final = "/opt/maskgw/lab/oracle9_w1_driver.py"
DRIVER_SHA: Final = "39a6890457c3bc9331fc371948fce896cbbc37e2d49f1584a5629490f43d2794"
DRIVER_BYTES: Final = 36956
DRIVER_MODULE: Final = "_maskgw_w1_lab_driver"
PURE_PATH: Final = "/opt/maskgw/lab/oracle9_w1_controller.py"
PURE_SHA: Final = "4c155d76208f113852f95fec4c57253eef480c610aa390423fa6f82baf1f7bc7"
PURE_BYTES: Final = 22453
SOURCE_FLAGS: Final = 0o2400000  # Linux x86-64 O_RDONLY | O_NOFOLLOW | O_CLOEXEC
INIT_HEADER: Final = 8
INIT_BODY_MAX: Final = 65536
CONTROL_BYTES: Final = 16
LINE_MAX: Final = 512  # including the final LF
LINES_MAX: Final = 56
WRITE_CAP_S: Final = 2.0
SLICE_S: Final = 0.25
HOLD_BACKOFF_S: Final = 1.0
HOLD_FAULTS_MAX: Final = 255
SLOTS: Final = ("pair_writer", "pair_reader", "sink_thread", "watcher_thread", "link")
TICKET: Final = "source_fd"
HANDLED_SIGNALS: Final = (15, 2, 1)  # Linux SIGTERM, SIGINT, SIGHUP

_AF_UNIX: Final = 1  # Linux value; no host constant lookup
_INIT_MAGIC: Final = b"MGI1"
_SOURCES: Final = frozenset(
    {
        (DRIVER_PATH, DRIVER_BYTES, DRIVER_BYTES + 1),
        (PURE_PATH, PURE_BYTES, PURE_BYTES + 1),
    }
)
_THREAD_SLOTS: Final = {"sink": "sink_thread", "watcher": "watcher_thread"}
_CONTROLS: Final = frozenset({"KeyboardInterrupt", "SystemExit", "MainSignal", "OTHER"})
_EXIT_OUTCOMES: Final = frozenset({"GUARD_FAILED", "ABORTED", "T6_UNKILLED"})
_FINAL_OUTCOMES: Final = _EXIT_OUTCOMES | {"RETAINED"}


# ---------------------------------------------------------------- closed vocabulary


class SlotState(enum.Enum):
    EMPTY = "EMPTY"
    UNKNOWN = "UNKNOWN"
    OWNED = "OWNED"


class Phase(enum.Enum):
    BOOT = "BOOT"
    BOUND = "BOUND"
    LINKED = "LINKED"
    RUNNING = "RUNNING"
    DECIDING = "DECIDING"
    EXITING = "EXITING"
    HOLDING = "HOLDING"


class MainOutcome(enum.Enum):
    SETUP_FAILED = "SETUP_FAILED"
    LOAD_FAILED = "LOAD_FAILED"
    LINK_FAILED = "LINK_FAILED"
    GUARD_FAILED = "GUARD_FAILED"
    ABORTED = "ABORTED"
    T6_UNKILLED = "T6_UNKILLED"
    CONTROL = "CONTROL"


class HoldStep(enum.Enum):
    WOKE = "WOKE"
    BACKOFF = "BACKOFF"
    FAULT = "FAULT"


class LinkState(enum.Enum):
    ACTIVE = "ACTIVE"
    POISONED = "POISONED"
    RETIRED = "RETIRED"


class LinkStatus(enum.Enum):
    OK = "OK"
    EOF = "EOF"
    EXPIRED = "EXPIRED"
    IO = "IO"
    POISONED = "POISONED"
    CONCURRENT = "CONCURRENT"
    RETIRED = "RETIRED"


EXIT_CODES: Final = {
    MainOutcome.SETUP_FAILED: 64,
    MainOutcome.LOAD_FAILED: 65,
    MainOutcome.LINK_FAILED: 66,
    MainOutcome.GUARD_FAILED: 67,
    MainOutcome.ABORTED: 68,
    MainOutcome.T6_UNKILLED: 69,
    MainOutcome.CONTROL: 70,
}
_CLEAN_FAILURES: Final = (
    MainOutcome.SETUP_FAILED,
    MainOutcome.LOAD_FAILED,
    MainOutcome.LINK_FAILED,
)


class SlotRefusal(Exception):
    """Slot or ticket operation refused before any effect; no input text."""

    def __init__(self) -> None:
        super().__init__("SLOT")


class MainRefusal(Exception):
    """Closed category only; never paths, errno or an original exception."""

    def __init__(self, category: str) -> None:
        super().__init__(category)
        self.category = category


class MainSignal(BaseException):
    """Cooperative observation of the sticky signal mark; carries no text."""

    def __init__(self) -> None:
        super().__init__()


def _refuse(error: BaseException) -> NoReturn:
    """Raise a closed error detached from any active caller exception."""
    try:
        raise error
    except BaseException as raised:
        raised.__context__ = None
        raised.__cause__ = None
        raise


# ---------------------------------------------------------------- OS seam


@dataclass(frozen=True, slots=True)
class System:
    """Closed list of the calls this main makes; not a framework."""

    open: Callable[..., Any]
    read: Callable[..., Any]
    close: Callable[..., Any]
    fstat: Callable[..., Any]
    isatty: Callable[..., Any]
    set_blocking: Callable[..., Any]
    os_read: Callable[..., Any]
    os_write: Callable[..., Any]
    select: Callable[..., Any]
    socketpair: Callable[..., Any]
    thread_class: Callable[..., Any]
    active_count: Callable[..., Any]
    signal: Callable[..., Any]
    monotonic: Callable[..., Any]
    sleep: Callable[..., Any]
    pause: Callable[..., Any]
    urandom: Callable[..., Any]
    protect: Callable[..., Any]
    is_main_thread: Callable[..., Any]
    silence: Callable[..., Any]


def _set_blocking(fd: int, flag: bool) -> None:
    os.set_blocking(fd, flag)


def _pause() -> None:
    signal.pause()


def _protect(*, role: Any, address_limit_bytes: int) -> Any:
    return protect_process(role=role, address_limit_bytes=address_limit_bytes)


def _is_main_thread() -> bool:
    return threading.current_thread() is threading.main_thread()


def _closed_hook(*_args: object) -> None:
    return None


def _silence() -> None:
    # fd2 is borrowed and never touched; Python-level output paths become closed.
    sys.stdout = None
    sys.stderr = None
    sys.excepthook = _closed_hook
    threading.excepthook = _closed_hook
    sys.unraisablehook = _closed_hook


def real_system() -> System:
    """Only references; nothing is opened, started, installed or changed here."""
    return System(
        open=os.open,
        read=os.read,
        close=os.close,
        fstat=os.fstat,
        isatty=os.isatty,
        set_blocking=_set_blocking,
        os_read=os.read,
        os_write=os.write,
        select=select.select,
        socketpair=socket.socketpair,
        thread_class=threading.Thread,
        active_count=threading.active_count,
        signal=signal.signal,
        monotonic=time.monotonic,
        sleep=time.sleep,
        pause=_pause,
        urandom=os.urandom,
        protect=_protect,
        is_main_thread=_is_main_thread,
        silence=_silence,
    )


# ---------------------------------------------------------------- root, slots, ticket


class Slot:
    __slots__ = ("state", "value")

    def __init__(self) -> None:
        self.state = SlotState.EMPTY
        self.value: Any = None


class MainRoot:
    """Strong caller-created root; slots only move EMPTY -> UNKNOWN -> OWNED -> EMPTY."""

    def __init__(self, system: System) -> None:
        self.system = system
        self.phase = Phase.BOOT
        self.namespace: Any = None
        self.owner: Any = None
        self.slots = {name: Slot() for name in SLOTS}
        self.ticket = Slot()
        self.ledger: Any = None
        self.sessions: list[Any] = []
        self.result: Any = None
        self.control: str | None = None
        self.failure: MainOutcome | None = None
        self.signal_seen = False
        self.hold_faults = 0

    def _slot(self, name: object) -> Slot:
        slot = self.slots.get(name) if type(name) is str else None
        if slot is None:
            _refuse(SlotRefusal())
        return slot

    def reserve(self, *names: str) -> None:
        chosen: list[Slot] = []
        for name in names:
            slot = self._slot(name)
            if slot.state is not SlotState.EMPTY or any(slot is item for item in chosen):
                _refuse(SlotRefusal())
            chosen.append(slot)
        if not chosen:
            _refuse(SlotRefusal())
        for slot in chosen:  # all checked first: never a partial reservation
            slot.state = SlotState.UNKNOWN

    def own(self, name: str, value: object) -> None:
        slot = self._slot(name)
        if slot.state is not SlotState.UNKNOWN:
            _refuse(SlotRefusal())
        slot.value = value
        slot.state = SlotState.OWNED

    def clear(self, name: str, value: object) -> None:
        slot = self._slot(name)
        if slot.state is not SlotState.OWNED or slot.value is not value:
            _refuse(SlotRefusal())
        slot.state = SlotState.EMPTY
        slot.value = None

    def reserve_ticket(self) -> None:
        if self.ticket.state is not SlotState.EMPTY:
            _refuse(SlotRefusal())
        self.ticket.state = SlotState.UNKNOWN

    def own_ticket(self, fd: object) -> None:
        if self.ticket.state is not SlotState.UNKNOWN or type(fd) is not int or fd < 0:
            _refuse(SlotRefusal())
        self.ticket.value = fd
        self.ticket.state = SlotState.OWNED

    def clear_ticket(self, fd: object) -> None:
        ticket = self.ticket
        if ticket.state is not SlotState.OWNED or type(fd) is not int or ticket.value != fd:
            _refuse(SlotRefusal())
        ticket.state = SlotState.EMPTY
        ticket.value = None

    def bind(self, module: object, owner: object) -> None:
        valid = (
            self.phase is Phase.BOOT
            and self.namespace is None
            and self.owner is None
            and type(module) is types.ModuleType
            and type(owner) is getattr(module, "Owner", None)
        )
        if not valid:
            _refuse(SlotRefusal())
        self.namespace = module
        self.owner = owner
        self.phase = Phase.BOUND


def _signal_point(root: MainRoot) -> None:
    """Cooperative boundary: main role only, before anything is reserved or consumed."""
    if root.signal_seen is True and root.system.is_main_thread() is True:
        _refuse(MainSignal())


def _sticky_handler(root: MainRoot) -> Callable[[int, object], None]:
    def handler(_signum: int, _frame: object) -> None:
        root.signal_seen = True  # never raises, writes or touches a slot

    return handler


# ---------------------------------------------------------------- pinned sources


def _close_verified(system: System, fd: int) -> bool:
    """One close of the exact fd, then EBADF and a single Python-managed thread."""
    try:
        system.close(fd)
    except Exception:
        return False
    closed = False
    try:
        system.fstat(fd)
    except OSError as error:
        closed = error.errno == errno.EBADF
    except Exception:
        closed = False
    if not closed:
        return False
    try:
        return system.active_count() == 1
    except Exception:
        return False


def _read_source(system: System, fd: int, limit: int) -> bytes:
    data = b""
    while len(data) < limit:
        chunk = system.read(fd, limit - len(data))
        if type(chunk) is not bytes or len(chunk) > limit - len(data):
            _refuse(MainRefusal("SOURCE"))
        if not chunk:
            break
        data += chunk
    return data


def read_pinned(root: MainRoot, path: str, size: int, limit: int) -> bytes:
    """Only the two fixed public pairs; bytes leave only after a verified close."""
    exact = type(path) is str and type(size) is int and type(limit) is int
    if not exact or (path, size, limit) not in _SOURCES:
        _refuse(MainRefusal("SOURCE"))
    system = root.system
    root.reserve_ticket()
    fd = system.open(path, SOURCE_FLAGS)  # failure leaves UNKNOWN: no fd to close
    root.own_ticket(fd)
    data = b""
    failed = False
    try:
        info = system.fstat(fd)
        if stat.S_ISREG(info.st_mode) and info.st_size == size:
            data = _read_source(system, fd, limit)
        failed = len(data) != size
    except Exception:
        failed = True
    if not _close_verified(system, fd):  # single attempt; uncertainty stays OWNED
        data = b""
        _refuse(MainRefusal("CLOSE"))
    root.clear_ticket(fd)
    if failed:
        data = b""
        _refuse(MainRefusal("SOURCE"))
    return data


def _driver_matches(module: types.ModuleType) -> bool:
    return (
        getattr(module, "PURE_SHA", None) == PURE_SHA
        and getattr(module, "PURE_BYTES", None) == PURE_BYTES
        and getattr(module, "PURE_PATH", None) == PURE_PATH
        and isinstance(getattr(module, "Owner", None), type)
        and isinstance(getattr(module, "Ports", None), type)
        and callable(getattr(module, "run", None))
    )


def load_driver(root: MainRoot) -> types.ModuleType:
    """Exact size and SHA-256 before execution; the same bytes are executed."""
    raw = read_pinned(root, DRIVER_PATH, DRIVER_BYTES, DRIVER_BYTES + 1)
    if len(raw) != DRIVER_BYTES or hashlib.sha256(raw).hexdigest() != DRIVER_SHA:
        _refuse(MainRefusal("LOAD"))
    module = types.ModuleType(DRIVER_MODULE)
    module.__file__ = DRIVER_PATH
    sys.modules[DRIVER_MODULE] = module  # dataclasses resolve their module here
    failed = False
    try:
        exec(compile(raw, DRIVER_PATH, "exec"), module.__dict__)
        failed = not _driver_matches(module)
    except Exception:
        failed = True
    if failed:
        if sys.modules.get(DRIVER_MODULE) is module:
            del sys.modules[DRIVER_MODULE]
        _refuse(MainRefusal("LOAD"))
    return module


# ---------------------------------------------------------------- host link


class HostLink:
    """Borrowed fd0/fd1; whole-frame reader lock; poison and retirement are sticky."""

    def __init__(self, root: MainRoot) -> None:
        self._root = root
        self._system = root.system
        self._reader = threading.Lock()
        self._consumed = False
        self._writing = False  # an in-flight write blocks retirement until it unwinds
        self._lines = 0
        self.state = LinkState.ACTIVE
        self.status = LinkStatus.OK

    def _active(self) -> bool:
        return self.state is LinkState.ACTIVE

    def _poison(self) -> None:
        if self.state is LinkState.ACTIVE:
            self.state = LinkState.POISONED

    def _claim(self) -> bool:
        if self.state is not LinkState.ACTIVE:
            retired = self.state is LinkState.RETIRED
            self.status = LinkStatus.RETIRED if retired else LinkStatus.POISONED
            return False
        if not self._reader.acquire(blocking=False):
            self._poison()  # a concurrent reader is a defect, never interleaved
            self.status = LinkStatus.CONCURRENT
            return False
        if not self._active():
            self._reader.release()
            return False
        self._consumed = False
        return True

    def _stop(self, status: LinkStatus) -> None:
        self.status = status
        if self._consumed:
            self._poison()

    def _read_exact(self, size: int, deadline: float) -> bytes | None:
        system = self._system
        data = b""
        while len(data) < size:
            if not self._active():
                return None
            remaining = deadline - system.monotonic()
            if remaining <= 0:
                self._stop(LinkStatus.EXPIRED)
                return None
            if not self._consumed:
                _signal_point(self._root)
            try:
                ready = system.select([0], [], [], min(remaining, SLICE_S))[0]
            except (BlockingIOError, InterruptedError):
                continue  # finite retry: the loop rechecks state and the same deadline
            except OSError:
                self._stop(LinkStatus.IO)
                return None
            if not self._active():
                return None
            if system.monotonic() >= deadline:
                self._stop(LinkStatus.EXPIRED)
                return None
            if not ready:
                continue
            try:
                chunk = system.os_read(0, size - len(data))  # never beyond the frame
            except (BlockingIOError, InterruptedError):
                continue
            except OSError:
                self._stop(LinkStatus.IO)
                return None
            if not self._active():
                return None
            if type(chunk) is not bytes or len(chunk) > size - len(data):
                self._consumed = True
                self._stop(LinkStatus.IO)
                return None
            if not chunk:
                self._stop(LinkStatus.EOF)
                return None
            data += chunk
            self._consumed = True
            if system.monotonic() >= deadline:
                self._stop(LinkStatus.EXPIRED)
                return None
        return data

    def _deliver(self, data: bytes, deadline: float) -> bytes | None:
        if not self._active():
            return None
        if self._system.monotonic() >= deadline:
            self._stop(LinkStatus.EXPIRED)
            return None
        self.status = LinkStatus.OK
        return data

    def read_init(self, *, deadline: float) -> bytes | None:
        _signal_point(self._root)
        if not self._claim():
            return None
        try:
            header = self._read_exact(INIT_HEADER, deadline)
            if header is None:
                return None
            length = int.from_bytes(header[4:INIT_HEADER], "big")
            if header[:4] != _INIT_MAGIC or length > INIT_BODY_MAX:
                return self._deliver(header, deadline)  # the pure decoder refuses it
            body = self._read_exact(length, deadline) if length else b""
            if body is None:
                return None
            return self._deliver(header + body, deadline)
        except BaseException:
            self._poison()
            raise
        finally:
            self._reader.release()

    def read_control(self, *, deadline: float) -> bytes | None:
        _signal_point(self._root)
        if not self._claim():
            return None
        try:
            frame = self._read_exact(CONTROL_BYTES, deadline)
            if frame is None:
                return None
            return self._deliver(frame, deadline)
        except BaseException:
            self._poison()
            raise
        finally:
            self._reader.release()

    def write(self, line: object) -> bool:
        if not self._active() or self._lines >= LINES_MAX:
            return False
        if type(line) is not bytes or not 1 <= len(line) < LINE_MAX:
            return False
        if not line.isascii() or b"\n" in line or b"\r" in line:
            return False
        self._writing = True
        try:
            written = self._write_all(line + b"\n")
        except BaseException:
            self._poison()
            raise
        finally:
            self._writing = False  # only the activity marker; ownership is unchanged
        if written:
            self._lines += 1
        return written

    def _write_all(self, data: bytes) -> bool:
        system = self._system
        deadline = system.monotonic() + WRITE_CAP_S
        offset = 0
        while offset < len(data):
            if not self._active():
                return False
            remaining = deadline - system.monotonic()
            if remaining <= 0:
                self._poison()
                return False
            try:
                ready = system.select([], [1], [], min(remaining, SLICE_S))[1]
            except (BlockingIOError, InterruptedError):
                continue  # finite retry within the same absolute deadline
            except OSError:
                self._poison()
                return False
            if not self._active():
                return False
            if system.monotonic() >= deadline:
                self._poison()
                return False
            if not ready:
                continue
            try:
                sent = system.os_write(1, data[offset:])
            except (BlockingIOError, InterruptedError):
                continue
            except OSError:
                self._poison()
                return False
            if not self._active():
                return False
            if type(sent) is not int or not 0 < sent <= len(data) - offset:
                self._poison()
                return False
            offset += sent
            if system.monotonic() >= deadline:
                self._poison()
                return False
        return self._active()

    def retire(self) -> bool:
        """Logical only: after completion or contained control, with no active reader."""
        root = self._root
        slot = root.slots["link"]
        if slot.state is not SlotState.OWNED or slot.value is not self:
            return False
        if self.state is LinkState.RETIRED or self._writing or not _completed(root):
            return False
        if not self._reader.acquire(blocking=False):
            return False
        try:
            self.state = LinkState.RETIRED
            self.status = LinkStatus.RETIRED
            root.clear("link", self)
        finally:
            self._reader.release()
        return True


def attach_link(root: MainRoot) -> HostLink:
    """B5: reserve first, then check and configure the borrowed descriptors."""
    root.reserve("link")
    system = root.system
    for fd in (0, 1):
        mode = system.fstat(fd).st_mode
        if not (stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode)) or system.isatty(fd):
            _refuse(MainRefusal("LINK"))  # reserved: stays UNKNOWN
    system.set_blocking(0, False)
    system.set_blocking(1, False)
    link = HostLink(root)
    root.own("link", link)
    root.phase = Phase.LINKED
    return link


# ---------------------------------------------------------------- port bindings


class PinnedReader:
    def __init__(self, root: MainRoot) -> None:
        self._root = root

    def read(self, path: str, limit: int) -> bytes:
        _signal_point(self._root)
        if type(path) is not str or path != PURE_PATH or type(limit) is not int:
            _refuse(MainRefusal("SOURCE"))
        if limit != PURE_BYTES + 1:
            _refuse(MainRefusal("SOURCE"))
        return read_pinned(self._root, path, PURE_BYTES, limit)


class ControllerGuard:
    def __init__(self, root: MainRoot) -> None:
        self._root = root

    def protect(self, *, role: Any, address_limit_bytes: int) -> Any:
        return self._root.system.protect(role=role, address_limit_bytes=address_limit_bytes)


class MonotonicClock:
    def __init__(self, root: MainRoot) -> None:
        self._root = root

    def monotonic(self) -> float:
        value: float = self._root.system.monotonic()
        return value

    def sleep_until(self, when: float) -> None:
        system = self._root.system
        while True:
            now = system.monotonic()
            if now >= when:
                return
            _signal_point(self._root)
            system.sleep(min(when - now, SLICE_S))


class SessionIds:
    def __init__(self, root: MainRoot) -> None:
        self._root = root

    def session_id(self) -> bytes:
        value = self._root.system.urandom(16)
        if type(value) is not bytes or len(value) != 16:
            _refuse(MainRefusal("IDS"))
        return value


class SessionFactory:
    def __init__(self, root: MainRoot) -> None:
        self._root = root

    def create(
        self,
        ledger: Any,
        token: Any,
        *,
        lock: Any,
        key: Any,
        limits: Any,
        profile: Any,
        guard: Any,
    ) -> WorkerSession:
        root = self._root
        _signal_point(root)
        if root.ledger is None:
            root.ledger = ledger
        elif root.ledger is not ledger:
            _refuse(MainRefusal("LEDGER"))
        session = WorkerSession(
            ledger, token, lock=lock, key=key, limits=limits, profile=profile, guard=guard
        )
        root.sessions.append(session)
        return session


def _close_endpoint(root: MainRoot, name: str, endpoint: object, sock: Any) -> None:
    sock.close()
    if sock.fileno() != -1:
        _refuse(MainRefusal("CLOSE"))
    root.clear(name, endpoint)


class PairWriter:
    def __init__(self, root: MainRoot, sock: Any) -> None:
        self._root, self._sock = root, sock

    def channel(self, *, stop: Callable[[], bool]) -> RawChannel:
        return RawChannel(self._sock, stop=stop, limits=TransportLimits())

    def shutdown_write(self) -> None:
        self._sock.shutdown(socket.SHUT_WR)

    def close(self) -> None:
        _close_endpoint(self._root, "pair_writer", self, self._sock)


class PairReader:
    def __init__(self, root: MainRoot, sock: Any) -> None:
        self._root, self._sock = root, sock

    def read(self, limit: int, *, deadline: float) -> bytes | None:
        system = self._root.system
        while True:
            remaining = deadline - system.monotonic()
            if remaining <= 0:
                raise TimeoutError
            self._sock.settimeout(min(remaining, SLICE_S))
            try:
                data = self._sock.recv(limit)
            except TimeoutError:
                continue
            if not data:
                return None
            return bytes(data)

    def close(self) -> None:
        _close_endpoint(self._root, "pair_reader", self, self._sock)


class SocketPairs:
    def __init__(self, root: MainRoot) -> None:
        self._root = root

    def create(self) -> tuple[PairWriter, PairReader]:
        root = self._root
        _signal_point(root)
        root.reserve("pair_writer", "pair_reader")  # both before the OS call
        first, second = root.system.socketpair(_AF_UNIX, socket.SOCK_STREAM)
        writer, reader = PairWriter(root, first), PairReader(root, second)
        root.own("pair_writer", writer)
        root.own("pair_reader", reader)
        return writer, reader


class ThreadHandle:
    def __init__(self, root: MainRoot, slot: str, target: Callable[[], object], name: str) -> None:
        self._root, self._slot, self._target = root, slot, target
        self._exited = threading.Event()
        self.ended = ""  # RETURNED | RAISED, never the original exception
        self._thread = root.system.thread_class(target=self._run, name=name, daemon=False)

    def _run(self) -> None:
        ended = "RAISED"
        try:
            self._target()
            ended = "RETURNED"
        except BaseException:
            ended = "RAISED"
        finally:
            self.ended = ended
            self._exited.set()

    def start(self) -> bool:
        self._thread.start()
        return True

    def join(self, *, deadline: float) -> bool:
        system = self._root.system
        while True:
            remaining = deadline - system.monotonic()
            if remaining <= 0:
                return False
            self._thread.join(min(remaining, SLICE_S))  # an exception keeps the slot
            if self._exited.is_set() and not self._thread.is_alive():
                self._root.clear(self._slot, self)
                return True


class ThreadPorts:
    def __init__(self, root: MainRoot) -> None:
        self._root = root

    def create(self, target: Callable[[], object], *, name: str) -> ThreadHandle:
        root = self._root
        _signal_point(root)
        slot = _THREAD_SLOTS.get(name) if type(name) is str else None
        if slot is None:
            _refuse(MainRefusal("THREAD"))
        root.reserve(slot)
        handle = ThreadHandle(root, slot, target, name)
        root.own(slot, handle)
        return handle


def build_ports(root: MainRoot) -> Any:
    link = root.slots["link"].value
    if root.slots["link"].state is not SlotState.OWNED or type(link) is not HostLink:
        _refuse(MainRefusal("PORTS"))
    return root.namespace.Ports(
        reader=PinnedReader(root),
        guard=ControllerGuard(root),
        clock=MonotonicClock(root),
        link=link,
        ids=SessionIds(root),
        factory=SessionFactory(root),
        pair=SocketPairs(root),
        threads=ThreadPorts(root),
    )


# ---------------------------------------------------------------- decision


@dataclass(frozen=True, slots=True)
class MainDecision:
    kind: str
    code: int | None

    def __post_init__(self) -> None:
        kind, code = self.kind, self.code
        if type(kind) is not str:  # exact type first: no callback of a refused value
            _refuse(MainRefusal("DECISION"))
        exiting = kind == "EXIT" and type(code) is int and 64 <= code <= 70
        holding = kind == "HOLD" and code is None
        if not (exiting or holding):
            _refuse(MainRefusal("DECISION"))


def decision_code(decision: object) -> int | None:
    """The only gate to an exit code: exact type, exact str and int, no bool."""
    if type(decision) is not MainDecision:
        return None
    try:
        kind = decision.kind
        code = decision.code
    except AttributeError:
        return None
    if type(kind) is not str or kind != "EXIT":
        return None
    if type(code) is not int or not 64 <= code <= 70:
        return None
    return code


def _completed(root: MainRoot) -> bool:
    if type(root.control) is str and root.control in _CONTROLS:
        return True
    namespace, result = root.namespace, root.result
    return (
        namespace is not None
        and type(result) is getattr(namespace, "DriverResult", None)
        and type(result.outcome) is str
        and result.outcome in _FINAL_OUTCOMES
    )


def _decided(root: MainRoot) -> bool:
    result = root.result
    if result is not None:
        namespace = root.namespace
        if namespace is None or type(result) is not namespace.DriverResult:
            return False
        return type(result.outcome) is str and result.outcome in _EXIT_OUTCOMES
    if type(root.control) is str and root.control in _CONTROLS:
        return True
    return any(root.failure is failure for failure in _CLEAN_FAILURES)


def _owner_settled(root: MainRoot) -> bool:
    owner = root.owner
    if owner is None:
        return True
    namespace = root.namespace
    if namespace is None or type(owner) is not namespace.Owner:
        return False
    return (
        owner.session is None
        and owner.session_token is None
        and owner.endpoints == ()
        and owner.handles == ()
        and owner.unknown == ()
    )


def _ledger_settled(root: MainRoot) -> bool:
    ledger = root.ledger
    if ledger is None:
        return True
    if type(ledger) is not BudgetLedger:
        return False
    status = ledger.status
    if status.failed is not False:
        return False
    entries = list(status.entries)
    for group in status.quarantined_entries:
        entries += list(group)
    for entry in entries:
        if entry is None:
            continue
        if entry.kind is ReservationKind.SESSION or entry.output_pinned is not False:
            return False
    return True


def _safe(root: MainRoot) -> bool:
    return (
        _decided(root)
        and root.ticket.state is SlotState.EMPTY
        and _owner_settled(root)
        and all(
            type(session) is WorkerSession and session.state is SessionState.CLOSED
            for session in root.sessions
        )
        and _ledger_settled(root)
        and all(slot.state is SlotState.EMPTY for slot in root.slots.values())
        and root.system.active_count() == 1
    )


def safe_exit(root: MainRoot) -> bool:
    """Facts of real objects only; labels never replace them; errors mean unsafe."""
    try:
        return _safe(root) is True
    except Exception:
        return False


def _outcome(root: MainRoot) -> MainOutcome:
    if root.control is not None:
        return MainOutcome.CONTROL
    if root.failure is not None:
        return root.failure
    return MainOutcome[root.result.outcome]


def _control_name(control: BaseException) -> str:
    for name, cls in (
        ("KeyboardInterrupt", KeyboardInterrupt),
        ("SystemExit", SystemExit),
        ("MainSignal", MainSignal),
    ):
        if type(control) is cls:
            return name
    return "OTHER"


# ---------------------------------------------------------------- lifecycle


def _attempt(root: MainRoot) -> None:
    """B1..B6, stopping at the first closed failure; controls go to the caller."""
    system = root.system
    handler = _sticky_handler(root)
    try:
        for signum in HANDLED_SIGNALS:
            system.signal(signum, handler)  # B1: permanent, never replaced
        system.silence()  # B2
    except Exception:
        root.failure = MainOutcome.SETUP_FAILED
        return
    try:
        module = load_driver(root)  # B3
        root.bind(module, module.Owner())  # B4
    except Exception:
        if root.ticket.state is SlotState.EMPTY and root.namespace is None:
            root.failure = MainOutcome.LOAD_FAILED
        return
    try:
        attach_link(root)  # B5
    except Exception:
        if root.slots["link"].state is SlotState.EMPTY:
            root.failure = MainOutcome.LINK_FAILED
        return
    ports = build_ports(root)  # B6
    root.phase = Phase.RUNNING
    root.result = root.namespace.run(ports, owner=root.owner)


def _retire_link(root: MainRoot) -> None:
    """B7: logical retirement only when the original link may be retired."""
    slot = root.slots["link"]
    link = slot.value
    if slot.state is SlotState.OWNED and type(link) is HostLink:
        link.retire()


def _run_once(root: MainRoot) -> MainDecision:
    """Finite contained attempt over the caller's root; no ownership is transferred."""
    try:
        _attempt(root)
    except BaseException as control:
        root.control = _control_name(control)
        del control
    try:
        _retire_link(root)
    except BaseException as control:
        if root.control is None:
            root.control = _control_name(control)
        del control
    exit_code: int | None = None
    try:
        root.phase = Phase.DECIDING
        if safe_exit(root):
            exit_code = EXIT_CODES[_outcome(root)]
    except BaseException:
        exit_code = None  # any doubt while deciding means hold
    if exit_code is not None:
        root.phase = Phase.EXITING
        return MainDecision(kind="EXIT", code=exit_code)
    root.phase = Phase.HOLDING
    return MainDecision(kind="HOLD", code=None)


def hold_step(root: MainRoot) -> HoldStep:
    """One finite hold step: blocking pause, else positive blocking backoff."""
    try:
        root.system.pause()
        return HoldStep.WOKE
    except BaseException:
        root.hold_faults = min(root.hold_faults + 1, HOLD_FAULTS_MAX)
    try:
        root.system.sleep(HOLD_BACKOFF_S)
        return HoldStep.BACKOFF
    except BaseException:
        return HoldStep.FAULT


def hold(root: MainRoot) -> NoReturn:
    """Retains the exact root until the host's hard kill; never cleans up or exits."""
    while True:
        hold_step(root)


def entry(system: System) -> int:
    root = MainRoot(system)
    decision: object = None
    try:
        decision = _run_once(root)
    except BaseException:
        decision = None
    code = decision_code(decision)
    if code is not None:
        return code
    hold(root)


if __name__ == "__main__":
    raise SystemExit(entry(real_system()))
