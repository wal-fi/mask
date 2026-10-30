"""Specific private Docker attach channel; no effects on import or repr.

Target/Absent facts are supplied by the trusted fixture coordinator, not OS
attestations. Quiesce precedes external CID removal and observed absence.
HELD retains this owner and loop; no loop close until assert_released.
"""

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from functools import wraps
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import select
import subprocess
import sys
import time

if sys.platform == "win32":
    from asyncio.windows_utils import PipeHandle as PIPE_TYPE
else:
    PIPE_TYPE = None

MAX_BODY = 16384
HEADER_BYTES = 16
TRAILER = b"SEEDEND\n"
MAX_FRAME = HEADER_BYTES + MAX_BODY + len(TRAILER)
MAX_READY = 512
MAX_STDOUT = 32768
OPEN_SECONDS = 12.0
CLOSE_SECONDS = 3.0
PG_SETUP_SECONDS = 60.0
PG_LIFETIME_SECONDS = 300.0
CONTROLLER_SECONDS = 120.0
CLI = Path("C:/Users/w.filho/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe")
CLI_SHA = "60028870931ea6e91955bfeaee358ec6c6920f6162c17a3d828c3c82ab3c3599"
HOME = Path("C:/Users/w.filho")
CONFIG = HOME / ".docker/config.json"
META = (
    HOME
    / ".docker/contexts/meta/fe9c6bd7a66301f49ca9b6a70b217107cd1284598bfc254700c989b916da791e/meta.json"
)
CONFIG_SHA = "f173396ef80b3c0bf4f8a5f6f944d3e426cee041ae3a2a8a07602ff6846a9f1a"
META_SHA = "c16649b1a2f1c6fbb68b85158a956862331e86543e25df46341f5fe5df2f9a25"
STDLIB = Path("C:/Users/w.filho/AppData/Local/Programs/Python/Python311/Lib/asyncio")
STDLIB_PINS = {
    "windows_utils.py": "23ff6c7fececfe35a06eaf7615c1e1e67c0740b78ca75a04c548b184be87b958",
    "proactor_events.py": "76eb32c35e8db62d4ce258d512e5870c79ec2d381466013a6ffbcc126e1b3fc5",
    "base_subprocess.py": "0e07c6d91c88e3f2e587e5edceb9f14d6c9afdf9f55bcdbc6610ad1bcde93df7",
    "windows_events.py": "16e963782a4424deb6380601abb19f1dd80df24db0dab03ef3f8a4e6829b5f6c",
    "streams.py": "34a6fca4720f83042e1c4b1567a2a2adc501ebe39b06f30d9327beb55d61fd52",
    "subprocess.py": "a511d0d64d2d8086b7cb8e81dbbb0d906fa12d8731da52f20ff198f44bdf415a",
}


class Role(StrEnum):
    PG = "P"
    CONTROLLER = "C"


class Fault(StrEnum):
    STATE = "STATE"
    RUNTIME = "RUNTIME"
    FRAME = "FRAME"
    SPAWN = "SPAWN"
    READY = "READY"
    DEADLINE = "DEADLINE"
    IO = "IO"
    STDOUT_LIMIT = "STDOUT_LIMIT"
    EXIT = "EXIT"
    HELD = "HELD"


class Delivery(StrEnum):
    """SENT proves local CLI pipe handoff only, never container receipt."""

    NOT_SENT = "NOT_SENT"
    UNKNOWN = "UNKNOWN"
    SENT = "SENT"


class BootstrapError(Exception):
    def __init__(self, category):
        self.category = category if type(category) is Fault else Fault.STATE
        super().__init__(self.category.value)


def need(value, category=Fault.STATE):
    if not value:
        raise BootstrapError(category) from None


@dataclass(frozen=True)
class Target:
    cid: str
    task: str
    image: str
    source_sha256: str
    role: Role

    def __post_init__(self):
        need(type(self.role) is Role)
        for value, pattern in (
            (self.cid, r"[0-9a-f]{64}"),
            (self.task, r"[0-9a-f]{32}"),
            (self.image, r"sha256:[0-9a-f]{64}"),
            (self.source_sha256, r"[0-9a-f]{64}"),
        ):
            need(type(value) is str and re.fullmatch(pattern, value))

    def ready_line(self):
        value = {
            "kind": "MASKGW_BOOTSTRAP_READY_V1",
            "role": self.role.value,
            "task": self.task,
            "source_sha256": self.source_sha256,
            "uid": 70 if self.role is Role.PG else 10001,
            "pid": 1,
        }
        raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
        need(len(raw) <= MAX_READY)
        return raw


@dataclass(frozen=True)
class Quiesced:
    """Public ticket issued once after all CLI resources are collected."""

    cid: str
    nonce: str
    issued: float

    def __post_init__(self):
        need(type(self.cid) is str and re.fullmatch(r"[0-9a-f]{64}", self.cid))
        need(type(self.nonce) is str and re.fullmatch(r"[0-9a-f]{32}", self.nonce))
        need(type(self.issued) is float and math.isfinite(self.issued) and self.issued >= 0)


@dataclass(frozen=True)
class Absent:
    """Trusted coordinator fact: own CID removed/absent AFTER this ticket.

    Coordinator inspects by CID/ownership, kills only if running, reinspects,
    removes without force, then confirms absence by CID. A failed removal
    retains ownership; no implicit cleanup retry or stopped-only substitute.
    """

    ticket: Quiesced
    observed: float

    def __post_init__(self):
        need(type(self.ticket) is Quiesced)
        need(type(self.observed) is float and math.isfinite(self.observed))
        need(self.observed >= self.ticket.issued)


def operation(method):
    """One foreground lifecycle operation at a time on the owner loop."""

    @wraps(method)
    async def run(self, *args, **kwargs):
        self._bind()
        need(not self._busy)
        self._busy = True
        try:
            return await method(self, *args, **kwargs)
        except asyncio.CancelledError:
            if method.__name__ == "send_seed" and self._delivery is not Delivery.NOT_SENT:
                self._delivery = Delivery.UNKNOWN
            self._quiescing = True
            self.phase = "HELD"
            self._mark(Fault.IO)
            raise
        finally:
            self._busy = False

    return run


@dataclass(frozen=True, repr=False, slots=True, init=False)
class Seed:
    role: Role
    _wire: bytes

    def __init__(self, role, body):
        need(type(role) is Role and type(body) is bytes and 1 <= len(body) <= MAX_BODY, Fault.FRAME)
        object.__setattr__(self, "role", role)
        wire = (
            b"MGSEED01"
            + role.value.encode("ascii")
            + f"{len(body):06d}\n".encode("ascii")
            + body
            + TRAILER
        )
        object.__setattr__(self, "_wire", wire)

    def __repr__(self):
        return "Seed(<private>)"

    def reveal_frame(self):
        return self._wire


class PrivateOutput:
    __slots__ = ("_data",)

    def __init__(self, data):
        self._data = data

    def __repr__(self):
        return "PrivateOutput(<private>)"

    def reveal(self):
        return self._data


def body_size(header, role):
    need(type(header) is bytes and len(header) == HEADER_BYTES and type(role) is Role, Fault.FRAME)
    need(
        header[:8] == b"MGSEED01"
        and header[8:9] == role.value.encode("ascii")
        and header[-1:] == b"\n",
        Fault.FRAME,
    )
    digits = header[9:15]
    need(len(digits) == 6 and all(48 <= digit <= 57 for digit in digits), Fault.FRAME)
    size = int(digits)
    need(1 <= size <= MAX_BODY, Fault.FRAME)
    return size


def decode_seed(raw, role):
    need(type(raw) is bytes and HEADER_BYTES < len(raw) <= MAX_FRAME, Fault.FRAME)
    size = body_size(raw[:HEADER_BYTES], role)
    need(
        len(raw) == HEADER_BYTES + size + len(TRAILER) and raw[-len(TRAILER) :] == TRAILER,
        Fault.FRAME,
    )
    return PrivateOutput(raw[HEADER_BYTES : HEADER_BYTES + size])


def read_seed_fd(fd, role, deadline):
    """Python container reader, exact os.read. Does not require Docker EOF."""
    need(sys.platform == "linux" and type(fd) is int and fd >= 0)
    need(type(deadline) is float and math.isfinite(deadline) and deadline > time.monotonic())

    def exact(size):
        value = bytearray(size)
        offset = 0
        while offset < size:
            left = deadline - time.monotonic()
            need(left > 0, Fault.DEADLINE)
            ready, _, _ = select.select([fd], [], [], min(left, 0.25))
            if not ready:
                continue
            piece = os.read(fd, min(4096, size - offset))
            need(piece, Fault.FRAME)
            value[offset : offset + len(piece)] = piece
            offset += len(piece)
        return bytes(value)

    failed = False
    result = None
    try:
        header = exact(HEADER_BYTES)
        size = body_size(header, role)
        body = exact(size)
        need(exact(len(TRAILER)) == TRAILER, Fault.FRAME)
        ready, _, _ = select.select([fd], [], [], 0)
        need(not ready or not os.read(fd, 1), Fault.FRAME)
        result = PrivateOutput(body)
    except BaseException:
        failed = True
    if failed:
        raise BootstrapError(Fault.FRAME) from None
    return result


def environment():
    keys = (
        "SystemRoot",
        "WINDIR",
        "PATH",
        "PATHEXT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
        "HOMEDRIVE",
        "HOMEPATH",
        "ProgramData",
        "ProgramFiles",
    )
    return {key: os.environ[key] for key in keys if key in os.environ}


def admit_runtime():
    need(
        sys.platform == "win32"
        and sys.version_info[:3] == (3, 11, 3)
        and sys.flags.optimize == 0
        and sys.flags.isolated == 1
        and sys.flags.dont_write_bytecode == 1,
        Fault.RUNTIME,
    )
    need(type(asyncio.get_running_loop()) is asyncio.ProactorEventLoop, Fault.RUNTIME)
    for path, expected, limit in (
        (CLI, CLI_SHA, 128 * 1024 * 1024),
        (CONFIG, CONFIG_SHA, 16384),
        (META, META_SHA, 16384),
        *((STDLIB / name, digest, 262144) for name, digest in STDLIB_PINS.items()),
    ):
        info = path.lstat()
        need(
            path.is_file()
            and not getattr(info, "st_file_attributes", 0) & 0x400
            and info.st_size <= limit,
            Fault.RUNTIME,
        )
        raw = path.read_bytes()
        need(
            len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == expected, Fault.RUNTIME
        )
    need(
        json.loads(META.read_bytes())["Endpoints"]["docker"]["Host"]
        in ("npipe:////./pipe/dockerDesktopLinuxEngine", "npipe://./pipe/dockerDesktopLinuxEngine"),
        Fault.RUNTIME,
    )


class ManagedBootstrap:
    def __init__(self, target):
        need(type(target) is Target)
        self.target = target
        self.phase = "NEW"
        self.fault = None
        self._loop = None
        self._process = None
        self._tasks = {}
        self._opened = 0.0
        self._ready = False
        self._delivery = Delivery.NOT_SENT
        self._stdin_closed = False
        self._stdout_eof = False
        self._stdout_closed = False
        self._waited = False
        self._retained = False
        self._quiescing = False
        self._ticket = None
        self._absent = False
        self._busy = False
        self._total_stdout = 0
        self._output = bytearray()

    def __repr__(self):
        return "ManagedBootstrap(<private>)"

    def _bind(self):
        loop = asyncio.get_running_loop()
        need(self._loop is None or self._loop is loop)
        self._loop = loop

    def _mark(self, category):
        if self.fault is None:
            self.fault = category

    def _raise(self):
        if self.fault is not None:
            raise BootstrapError(self.fault) from None

    def _task(self, name, coroutine):
        failed = False
        try:
            task = asyncio.create_task(coroutine, name="maskgw-bootstrap-" + name)
            self._tasks[name] = task
        except BaseException:
            coroutine.close()
            failed = True
        if failed:
            self._mark(Fault.IO)
        return None if failed else task

    async def _until(self, task, deadline):
        if task is None:
            return False
        left = deadline - time.monotonic()
        if left <= 0:
            return task.done()
        try:
            await asyncio.wait_for(asyncio.shield(task), left)
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if current is not None and current.cancelling() > 0:
                raise
            # Cancellation belongs to the owned task, not the caller.
        except TimeoutError:
            pass
        except Exception:
            if task is not self._tasks.get("spawn"):
                self._mark(Fault.IO)  # spawn result is classified by _adopt
        return task.done()

    def _pipe_closed(self, fd):
        """Positive handle proof for the pinned CPython Windows Proactor only."""
        if self._process is None or self._process.returncode is None or not self._waited:
            return False
        try:
            transport = self._process._transport.get_pipe_transport(fd)
            pipe = transport.get_extra_info("pipe")
            return PIPE_TYPE is not None and type(pipe) is PIPE_TYPE and pipe.handle is None
        except Exception:
            return False  # unknown is never a closed-handle proof

    def _adopt(self):
        task = self._tasks.get("spawn")
        if self._process is not None or task is None or not task.done():
            return
        failed = False
        try:
            self._process = task.result()
        except BaseException:
            failed = True
        if failed:
            self._mark(Fault.SPAWN)
        elif self._process is not None:
            self._ensure_pumps()

    def _ensure_pumps(self):
        for name, function, complete in (
            ("stdout", self._pump, self._stdout_eof or self._stdout_closed),
            ("wait", self._wait, self._waited),
        ):
            old = self._tasks.get(name)
            if not complete and (old is None or old.done()):
                self._task(name, function())

    async def _wait(self):
        failed = False
        try:
            await self._process.wait()
            self._waited = self._process.returncode is not None
        except BaseException:
            failed = True
        if failed:
            self._mark(Fault.IO)

    async def _pump(self):
        prefix = bytearray()
        while True:
            failed = False
            block = None
            try:
                block = await self._process.stdout.read(4096)
            except BaseException:
                failed = True
            if failed:
                self._mark(Fault.IO)
                if self._process.returncode is not None:
                    self._stdout_closed = self._pipe_closed(1)
                    return  # closed with IO is terminal for cleanup, never result success
                await asyncio.sleep(0.01)
                continue
            if not block:
                self._stdout_eof = True
                if not self._ready:
                    self._mark(Fault.READY)
                return
            self._total_stdout += len(block)
            if self._total_stdout > MAX_STDOUT:
                self._mark(Fault.STDOUT_LIMIT)
                self._output.clear()
            if self.fault is not None:
                await asyncio.sleep(0)  # continue draining/discarding, including infinite output
                continue
            if not self._ready:
                index = block.find(b"\n")
                end = len(block) if index < 0 else index + 1
                if len(prefix) + end > MAX_READY:
                    self._mark(Fault.READY)
                    continue
                prefix.extend(block[:end])
                if index < 0:
                    continue
                if bytes(prefix) != self.target.ready_line():
                    self._mark(Fault.READY)
                    continue
                self._ready = True
                block = block[end:]
            self._output.extend(block)
            await asyncio.sleep(0)

    @operation
    async def start(self):
        self._bind()
        need(self.phase == "NEW" and not self._quiescing)
        self.phase, self._opened = "STARTING", time.monotonic()  # adopted BEFORE spawn
        failed = False
        try:
            admit_runtime()
        except BaseException:
            failed = True
        if failed:
            self._mark(Fault.RUNTIME)
            self._raise()
        args = [
            str(CLI),
            "--context",
            "desktop-linux",
            "start",
            "--attach",
            "--interactive",
            self.target.cid,
        ]
        self._task(
            "spawn",
            asyncio.create_subprocess_exec(
                *args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=environment(),
                limit=8192,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            ),
        )
        completed = await self._until(self._tasks.get("spawn"), self._opened + OPEN_SECONDS)
        self._adopt()
        if not completed or time.monotonic() >= self._opened + OPEN_SECONDS:
            self._mark(Fault.DEADLINE)
        if self.fault is not None:
            self.phase = "HELD"
        self._raise()
        self.phase = "WAIT_READY"

    @operation
    async def await_ready(self):
        self._bind()
        need(self.phase == "WAIT_READY" and not self._quiescing)
        while (
            not self._ready
            and self.fault is None
            and not self._stdout_eof
            and time.monotonic() < self._opened + OPEN_SECONDS
        ):
            await asyncio.sleep(0.01)
        if not self._ready or time.monotonic() >= self._opened + OPEN_SECONDS:
            self._mark(Fault.DEADLINE if not self._stdout_eof else Fault.READY)
        if self._process.returncode is not None or self._stdout_eof:
            self._mark(Fault.EXIT)
        self._raise()
        self.phase = "READY"

    async def _feed(self, seed):
        failed = False
        try:
            if (
                not self._quiescing
                and self.fault is None
                and time.monotonic() < self._opened + OPEN_SECONDS
            ):
                self._delivery = Delivery.UNKNOWN  # write may partially deliver, including on error
                self._process.stdin.write(seed.reveal_frame())
                await self._process.stdin.drain()
                if (
                    self.fault is None
                    and not self._quiescing
                    and time.monotonic() < self._opened + OPEN_SECONDS
                    and self._process.returncode is None
                ):
                    self._delivery = Delivery.SENT
            else:
                self._mark(Fault.DEADLINE)
        except BaseException:
            failed = True
        if failed:
            self._mark(Fault.IO)

    async def _close_input(self):
        failed = False
        try:
            self._process.stdin.close()
            await self._process.stdin.wait_closed()
            self._stdin_closed = True
        except BaseException:
            failed = True
        if failed:
            self._mark(Fault.IO)
            self._stdin_closed = self._pipe_closed(0)

    @operation
    async def send_seed(self, seed):
        self._bind()
        need(
            self.phase == "READY"
            and not self._quiescing
            and type(seed) is Seed
            and seed.role is self.target.role
            and self._delivery is Delivery.NOT_SENT
        )
        self._raise()
        need(not self._stdout_eof and self._process.returncode is None, Fault.EXIT)
        self.phase = "SENDING"
        task = self._task("feed", self._feed(seed))
        if (
            not await self._until(task, self._opened + OPEN_SECONDS)
            or self._delivery is not Delivery.SENT
        ):
            self._mark(Fault.DEADLINE)
        if self.fault is None:
            task = self._task("input-close", self._close_input())
            if (
                not await self._until(task, time.monotonic() + CLOSE_SECONDS)
                or not self._stdin_closed
            ):
                self._mark(Fault.IO)
        if self.fault is not None:
            if self._delivery is Delivery.SENT:
                self._delivery = Delivery.UNKNOWN
            self.phase = "HELD"
        self._raise()
        self.phase = "ACTIVE"

    def retain(self):
        self._bind()
        need(
            self.phase == "ACTIVE"
            and not self._busy
            and not self._quiescing
            and self.target.role is Role.PG
        )
        if time.monotonic() >= self._opened + PG_SETUP_SECONDS:
            self._mark(Fault.DEADLINE)
        self._raise()
        self._retained = True

    @operation
    async def drain(self):
        self._bind()
        need(self.phase == "ACTIVE" and not self._quiescing)
        need(self.target.role is not Role.PG or self._retained)
        limit = PG_LIFETIME_SECONDS if self.target.role is Role.PG else CONTROLLER_SECONDS
        end = self._opened + limit
        while self._process.returncode is None and self.fault is None and time.monotonic() < end:
            await asyncio.sleep(0.01)
        if self._process.returncode is None:
            self._mark(Fault.DEADLINE)
        if self._process.returncode != 0 and self._process.returncode is not None:
            self._mark(Fault.EXIT)
        for name in ("stdout", "wait"):
            if not await self._until(
                self._tasks.get(name), min(end, time.monotonic() + CLOSE_SECONDS)
            ):
                self._mark(Fault.IO)
        self._raise()
        need(self._stdout_eof and self._waited and self._stdin_closed)
        return PrivateOutput(bytes(self._output))  # never an application-success claim

    @operation
    async def quiesce(self):
        self._bind()
        if self._ticket is not None:
            return self._ticket
        self._quiescing = True  # irreversible; late spawn must never receive seed
        self.phase = "QUIESCING"
        end = time.monotonic() + CLOSE_SECONDS
        await self._until(self._tasks.get("spawn"), end)
        self._adopt()
        spawn = self._tasks.get("spawn")
        if spawn is not None and not spawn.done():
            self.phase = "HELD"
            return None
        if self._process is None:
            return self._issue_ticket()
        for _ in range(3):
            if self._process.returncode is not None:
                break
            try:
                self._process.kill()
            except BaseException:
                pass
            self._ensure_pumps()
            await self._until(self._tasks.get("wait"), min(end, time.monotonic() + 0.25))
        if self._process.returncode is None:
            self.phase = "HELD"
            return None
        if not self._stdin_closed:
            old = self._tasks.get("input-close")
            if old is None or old.done():
                self._task("input-close", self._close_input())
            await self._until(self._tasks.get("input-close"), end)
        self._ensure_pumps()
        for name, task in tuple(self._tasks.items()):
            if name == "feed" and self._stdin_closed and not task.done():
                task.cancel()  # OS process ended and input handle already closed
            await self._until(task, end)
        while True:
            # connection_lost may close the handle on a later loop callback.
            self._stdin_closed = self._stdin_closed or self._pipe_closed(0)
            self._stdout_closed = self._stdout_closed or self._pipe_closed(1)
            complete = (
                self._process.returncode is not None
                and self._waited
                and (self._stdout_eof or self._stdout_closed)
                and self._stdin_closed
                and self._pipe_closed(0)
                and self._pipe_closed(1)
                and all(task.done() for task in self._tasks.values())
            )
            if complete:
                return self._issue_ticket()
            left = end - time.monotonic()
            if left <= 0:
                break
            self._ensure_pumps()
            await asyncio.sleep(min(0.01, left))
        self.phase = "HELD"
        return None

    def _issue_ticket(self):
        need(self._ticket is None and all(task.done() for task in self._tasks.values()))
        self._ticket = Quiesced(self.target.cid, secrets.token_hex(16), time.monotonic())
        self.phase = "QUIESCED"
        return self._ticket

    @operation
    async def close(self, absent=None):
        self._bind()
        if absent is None:
            return False
        need(
            type(absent) is Absent
            and self._ticket is not None
            and absent.ticket is self._ticket
            and absent.ticket.cid == self.target.cid
        )
        need(all(task.done() for task in self._tasks.values()), Fault.HELD)
        self._absent = True
        self.phase = "CLOSED"
        return True

    def metadata(self):
        return {
            "phase": self.phase,
            "role": self.target.role.value,
            "cid": self.target.cid,
            "fault": None if self.fault is None else self.fault.value,
            "seed_delivery": self._delivery.value,
            "stdout_bytes": self._total_stdout,
            "retained_stdout_bytes": len(self._output),
            "released": self.phase == "CLOSED",
        }

    def assert_released(self):
        need(
            self.phase == "CLOSED"
            and self._ticket is not None
            and self._absent
            and not self._busy
            and all(task.done() for task in self._tasks.values()),
            Fault.HELD,
        )
