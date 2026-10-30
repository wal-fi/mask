"""Public vector owner definitions/fakes only; no operational caller/native effects.

Source reads bind reviewed definitions. Native start is inherited unchanged;
the trusted future coordinator must admit CID/profile/wrapper before invoking it.
"""

import asyncio
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import stat
import time

REPO = Path(__file__).resolve().parents[2]
DEPENDENCIES = {
    "channel": (
        "docs/poc/w1_bootstrap_channel.py",
        "e6ca9e606567289fa312049b071aa777e1764579813829747cb32df05d4ee87a",
    ),
    "reader": (
        "docs/poc/pg16_shell_reader.py",
        "efe69a79a0743e49de602067d624c075cf5af8321a2654b7c2e87d023f498a85",
    ),
}
IMAGE = "sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685"
RESULT_SECONDS = 12.0
MAX_STDOUT = 2560
FRAGMENT_SECONDS = 0.02


def capture(key):
    relative, digest = DEPENDENCIES[key]
    path = REPO / relative
    raw = None
    try:
        info = path.lstat()
        if (
            stat.S_ISREG(info.st_mode)
            and not getattr(info, "st_file_attributes", 0) & 0x400
            and info.st_size <= 65536
        ):
            candidate = path.read_bytes()
            if len(candidate) == info.st_size and hashlib.sha256(candidate).hexdigest() == digest:
                raw = candidate
    except OSError:
        pass
    if raw is None:
        raise RuntimeError("PG16_SHELL_SOURCE") from None
    namespace = {"__name__": "_pg16_shell_" + key, "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace, raw


C, CHANNEL_RAW = capture("channel")
R, READER_RAW = capture("reader")


@dataclass(frozen=True)
class Observation:
    returncode: int
    stdout_bytes: int
    report_bytes: int
    output: bytes

    def __post_init__(self):
        C["need"](
            type(self.returncode) is int
            and self.returncode in (0, 42)
            and type(self.stdout_bytes) is int
            and 0 < self.stdout_bytes <= MAX_STDOUT
            and type(self.report_bytes) is int
            and type(self.output) is bytes
            and 0 < self.report_bytes == len(self.output) <= R["MAX_OUTPUT"]
            and self.report_bytes < self.stdout_bytes
        )


class PublicReaderOwner(C["ManagedBootstrap"]):
    def __init__(self, task, cid, case):
        C["need"](type(case) is R["Case"])
        C["need"](type(cid) is str and re.fullmatch(r"[0-9a-f]{64}", cid))
        # Validates task before template/hash/Target construction.
        ready = R["ready_line"](task)
        self._vector = R["vector"](case)
        self.wrapper = R["build"](task, case)
        self.wrapper_sha256 = hashlib.sha256(self.wrapper.encode("ascii")).hexdigest()
        super().__init__(C["Target"](cid, task, IMAGE, R["CORE_SHA"], C["Role"].PG))
        C["need"](self.target.ready_line() == ready)

    async def _pump(self):
        prefix = bytearray()
        while True:
            failed, block = False, None
            try:
                block = await self._process.stdout.read(4096)
            except BaseException:
                failed = True
            if failed or type(block) is not bytes:
                self._mark(C["Fault"].IO)
                self._output.clear()
                if self._process.returncode is not None:
                    self._stdout_closed = self._pipe_closed(1)
                    return
                await asyncio.sleep(0.01)
                continue
            if not block:
                self._stdout_eof = True
                if not self._ready:
                    self._mark(C["Fault"].READY)
                return
            self._total_stdout += len(block)
            if self._total_stdout > MAX_STDOUT:
                self._mark(C["Fault"].STDOUT_LIMIT)
                self._output.clear()
            if self.fault is not None:
                await asyncio.sleep(0)
                continue
            if not self._ready:
                index = block.find(b"\n")
                end = len(block) if index < 0 else index + 1
                if len(prefix) + end > C["MAX_READY"]:
                    self._mark(C["Fault"].READY)
                    continue
                prefix.extend(block[:end])
                if index < 0:
                    continue
                if bytes(prefix) != self.target.ready_line():
                    self._mark(C["Fault"].READY)
                    continue
                self._ready = True
                block = block[end:]
            if len(self._output) + len(block) > R["MAX_OUTPUT"]:
                self._mark(C["Fault"].STDOUT_LIMIT)
                self._output.clear()
            else:
                self._output.extend(block)
            await asyncio.sleep(0)

    async def send_seed(self, _seed):
        C["need"](False)

    def retain(self):
        C["need"](False)

    async def _feed_vector(self):
        failed = False
        try:
            for index, block in enumerate(self._vector.chunks):
                if (
                    self._quiescing
                    or self.fault is not None
                    or time.monotonic() >= self._opened + C["OPEN_SECONDS"]
                ):
                    self._mark(C["Fault"].DEADLINE)
                    return
                if self._process.returncode is not None:
                    self._mark(C["Fault"].EXIT)
                    return
                self._delivery = C["Delivery"].UNKNOWN
                self._process.stdin.write(block)
                await self._process.stdin.drain()
                if index + 1 < len(self._vector.chunks):
                    await asyncio.sleep(FRAGMENT_SECONDS)
            if (
                not self._quiescing
                and self.fault is None
                and time.monotonic() < self._opened + C["OPEN_SECONDS"]
            ):
                self._delivery = C["Delivery"].SENT
            else:
                self._mark(C["Fault"].DEADLINE)
        except BaseException:
            failed = True
        if failed:
            self._mark(C["Fault"].IO)

    @C["operation"]
    async def send_vector(self):
        self._bind()
        C["need"](
            self.phase == "READY"
            and not self._quiescing
            and self._delivery is C["Delivery"].NOT_SENT
        )
        self._raise()
        C["need"](not self._stdout_eof and self._process.returncode is None, C["Fault"].EXIT)
        self.phase = "SENDING"
        try:
            task = self._task("feed", self._feed_vector())
            if (
                not await self._until(task, self._opened + C["OPEN_SECONDS"])
                or self._delivery is not C["Delivery"].SENT
            ):
                self._mark(C["Fault"].DEADLINE)
            if self.fault is None and not self._vector.hold_open:
                task = self._task("input-close", self._close_input())
                if (
                    not await self._until(task, time.monotonic() + C["CLOSE_SECONDS"])
                    or not self._stdin_closed
                ):
                    self._mark(C["Fault"].IO)
            if self.fault is not None:
                if self._delivery is C["Delivery"].SENT:
                    self._delivery = C["Delivery"].UNKNOWN
                self.phase = "HELD"
            self._raise()
            self.phase = "ACTIVE"
        except asyncio.CancelledError:
            if self._delivery is not C["Delivery"].NOT_SENT:
                self._delivery = C["Delivery"].UNKNOWN
            raise

    @C["operation"]
    async def drain(self):
        self._bind()
        C["need"](self.phase == "ACTIVE" and not self._quiescing)
        end = self._opened + RESULT_SECONDS
        if time.monotonic() >= end:
            self._mark(C["Fault"].DEADLINE)
        while self._process.returncode is None and self.fault is None and time.monotonic() < end:
            await asyncio.sleep(0.01)
        if self._process.returncode is None or time.monotonic() >= end:
            self._mark(C["Fault"].DEADLINE)
        if self._process.returncode is not None and (
            type(self._process.returncode) is not int or self._process.returncode not in (0, 42)
        ):
            self._mark(C["Fault"].EXIT)
        for name in ("stdout", "wait"):
            if not await self._until(
                self._tasks.get(name), min(end, time.monotonic() + C["CLOSE_SECONDS"])
            ):
                self._mark(C["Fault"].IO)
        self._raise()
        C["need"](self._stdout_eof and self._waited)
        # A held stdin is closed only AFTER the actual process has exited.
        if not self._stdin_closed:
            task = self._task("input-close", self._close_input())
            if not await self._until(task, min(end, time.monotonic() + C["CLOSE_SECONDS"])):
                self._mark(C["Fault"].IO)
        self._raise()
        # EOF/wait can precede Proactor connection_lost callbacks. Give them
        # bounded loop turns; never mistake pending callbacks for handle proof.
        collected_by = min(end, time.monotonic() + C["CLOSE_SECONDS"])
        while (
            not (self._pipe_closed(0) and self._pipe_closed(1)) and time.monotonic() < collected_by
        ):
            await asyncio.sleep(0.01)
        if time.monotonic() >= end:
            self._mark(C["Fault"].DEADLINE)
        self._raise()
        C["need"](self._stdin_closed and self._pipe_closed(0) and self._pipe_closed(1))
        C["need"](self._total_stdout == len(self.target.ready_line()) + len(self._output))
        return Observation(
            self._process.returncode, self._total_stdout, len(self._output), bytes(self._output)
        )
