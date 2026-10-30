"""Fixed public PG16 probe owner. No operational caller or effects on import.

Captures reviewed source definitions. Never accepts a seed or a READY protocol.
Only the coordinator can attest own CID removal after quiesce and close.
"""

import asyncio
import hashlib
from pathlib import Path
import stat
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
DEPENDENCIES = {
    "channel": (
        "docs/poc/w1_bootstrap_channel.py",
        "e6ca9e606567289fa312049b071aa777e1764579813829747cb32df05d4ee87a",
    ),
    "profile": (
        "docs/poc/pg16_public_profile.py",
        "fe2f8ba8bfabc5572fe7aeb85c31c54de38ceaa23c1a6c34dd631425371d9277",
    ),
}


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
        raise RuntimeError("PG16_PUBLIC_SOURCE") from None
    namespace = {"__name__": "_pg16_public_" + key, "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace, raw


C, CHANNEL_RAW = capture("channel")
P, PROFILE_RAW = capture("profile")
MAX_STDOUT = 8192
OPEN_SECONDS = 12.0


def no_input(process):
    if process is None:
        return False
    try:
        return process.stdin is None and process._transport.get_pipe_transport(0) is None
    except Exception:
        return False


class PublicProbeOwner(C["ManagedBootstrap"]):
    def __init__(self, target):
        C["need"](
            type(target) is C["Target"]
            and target.role is C["Role"].PG
            and target.image == P["IMAGE"]
        )
        script = P["blueprint"](target.task)[0][-1]
        C["need"](target.source_sha256 == hashlib.sha256(script.encode("ascii")).hexdigest())
        super().__init__(target)

    def _pipe_closed(self, fd):
        if fd == 0:
            return (
                self._process is not None
                and self._process.returncode is not None
                and self._waited
                and no_input(self._process)
            )
        return super()._pipe_closed(fd)

    async def _pump(self):
        self._stdin_closed = no_input(self._process)  # also runs after late adoption
        while True:
            failed, block = False, None
            try:
                block = await self._process.stdout.read(4096)
            except BaseException:
                failed = True
            if failed:
                self._mark(C["Fault"].IO)
                self._output.clear()
                if self._process.returncode is not None:
                    self._stdout_closed = self._pipe_closed(1)
                    return
                await asyncio.sleep(0.01)
                continue
            if not block:
                self._stdout_eof = True
                return
            self._total_stdout += len(block)
            if self._total_stdout > MAX_STDOUT:
                self._mark(C["Fault"].STDOUT_LIMIT)
                self._output.clear()
            if self.fault is None:
                self._output.extend(block)
            await asyncio.sleep(0)  # drain/discard excess without starving supervision

    @C["operation"]
    async def start(self):
        self._bind()
        C["need"](self.phase == "NEW" and not self._quiescing)
        self.phase, self._opened = "STARTING", time.monotonic()
        failed = False
        try:
            C["admit_runtime"]()
        except BaseException:
            failed = True
        if failed:
            self._mark(C["Fault"].RUNTIME)
            self._raise()
        if time.monotonic() >= self._opened + OPEN_SECONDS:
            self._mark(C["Fault"].DEADLINE)
            self._raise()
        self._task(
            "spawn",
            asyncio.create_subprocess_exec(
                str(C["CLI"]),
                "--context",
                "desktop-linux",
                "start",
                "--attach",
                self.target.cid,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=C["environment"](),
                limit=8192,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            ),
        )
        try:
            completed = await self._until(self._tasks.get("spawn"), self._opened + OPEN_SECONDS)
        finally:
            self._adopt()
            if self._process is not None:
                self._stdin_closed = no_input(self._process)
        if not completed or time.monotonic() >= self._opened + OPEN_SECONDS:
            self._mark(C["Fault"].DEADLINE)
        if self.fault is not None:
            self.phase = "HELD"
        self._raise()
        self.phase = "ACTIVE"

    @C["operation"]
    async def drain(self):
        self._bind()
        C["need"](self.phase == "ACTIVE" and not self._quiescing)
        end = self._opened + OPEN_SECONDS
        while not self._waited and self.fault is None and time.monotonic() < end:
            await asyncio.sleep(0.01)
        if not self._waited and self.fault is None:
            self._mark(C["Fault"].DEADLINE)
        if time.monotonic() >= end:
            self._mark(C["Fault"].DEADLINE)
        self._raise()
        for name in ("stdout", "wait"):
            if not await self._until(self._tasks.get(name), end):
                self._mark(C["Fault"].DEADLINE)
        if time.monotonic() >= end:
            self._mark(C["Fault"].DEADLINE)
        self._raise()
        C["need"](
            self._stdout_eof
            and self._waited
            and self._stdin_closed
            and type(self._process.returncode) is int
        )
        # 42/137 go intact to the closed parser. No container-success claim here.
        return self._process.returncode, C["PrivateOutput"](bytes(self._output))

    async def await_ready(self):
        raise C["BootstrapError"](C["Fault"].STATE) from None

    async def send_seed(self, _seed):
        raise C["BootstrapError"](C["Fault"].STATE) from None

    def retain(self):
        raise C["BootstrapError"](C["Fault"].STATE) from None
