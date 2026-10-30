"""T4-only public emergency executor, no operational caller or effects on import.

Every instance owns its captured namespaces and event loop. It never receives a
main-loop object, seed, ManagedBootstrap, ticket or Absent. Thread lifecycle and
ownership validation belong to the later reviewed T4 watchdog/coordinator.
"""

import asyncio
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import re
import stat
import time

REPO = Path(__file__).resolve().parents[2]
CLI = "C:/Users/w.filho/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"
SHELL = "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
CONFIG = "C:/Users/w.filho/.docker/config.json"
META = (
    "C:/Users/w.filho/.docker/contexts/meta/"
    "fe9c6bd7a66301f49ca9b6a70b217107cd1284598bfc254700c989b916da791e/meta.json"
)
PINS = (
    (CLI, "60028870931ea6e91955bfeaee358ec6c6920f6162c17a3d828c3c82ab3c3599", 134217728),
    (SHELL, "60c9b29843624dd8af6b6a7b26147753be6aeef65098b9a503cc50850afe410f", 134217728),
    (CONFIG, "f173396ef80b3c0bf4f8a5f6f944d3e426cee041ae3a2a8a07602ff6846a9f1a", 16384),
    (META, "c16649b1a2f1c6fbb68b85158a956862331e86543e25df46341f5fe5df2f9a25", 16384),
)
BOUNDED_SHA = "58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627"
IDENTITY_SHA = "dc2481f5a54c1408f6c91c38f99c138d82431b5b1324afdfe9443087323b140d"


class Action(StrEnum):
    CLI_KILL = "CLI_KILL"
    CID_ABSENCE = "CID_ABSENCE"
    CID_INSPECT = "CID_INSPECT"
    CID_KILL = "CID_KILL"
    CID_REMOVE = "CID_REMOVE"


class EmergencyError(Exception):
    def __init__(self, category):
        super().__init__(category if category in ("INPUT", "PIN", "BUDGET", "COMMAND") else "INPUT")


def need(value):
    if not value:
        raise EmergencyError("INPUT") from None


@dataclass(frozen=True)
class Target:
    """Public immutable identity data from main; not an ownership attestation."""

    cid: str
    pid: int | None = None
    filetime: int | None = None

    def __post_init__(self):
        need(type(self.cid) is str and re.fullmatch(r"[0-9a-f]{64}", self.cid))
        need((self.pid is None) == (self.filetime is None))
        if self.pid is not None:
            need(type(self.pid) is int and 0 < self.pid < 2**32)
            need(type(self.filetime) is int and 0 < self.filetime < 2**63)


def cleanup_pins():
    for name, digest, maximum in PINS:
        path = Path(name)
        info = path.lstat()
        need(stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400)
        need(info.st_size <= maximum)
        raw = path.read_bytes()
        need(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == digest)
    need(
        json.loads(Path(META).read_bytes())["Endpoints"]["docker"]["Host"]
        in ("npipe:////./pipe/dockerDesktopLinuxEngine", "npipe://./pipe/dockerDesktopLinuxEngine")
    )


def captured_namespace(raw, digest, relative, name):
    need(type(raw) is bytes and 0 < len(raw) <= 65536)
    need(hashlib.sha256(raw).hexdigest() == digest)
    namespace = {"__name__": name, "__file__": str(REPO / relative)}
    exec(compile(raw, namespace["__file__"], "exec"), namespace)
    return namespace


class PublicEmergency:
    def __init__(self, bounded_bytes, identity_bytes):
        self._bounded = captured_namespace(
            bounded_bytes, BOUNDED_SHA, "docs/poc/run_linux_as_probe.py", "_t4_watch_bounded"
        )
        self._identity = captured_namespace(
            identity_bytes, IDENTITY_SHA, "docs/poc/w1_bootstrap_identity.py", "_t4_watch_identity"
        )
        self._end = None
        self._failed = False
        self._steps = []

    def begin(self):
        need(self._end is None)
        self._end = time.monotonic() + 45.0

    def _arguments(self, action, target):
        need(type(action) is Action and type(target) is Target)
        if action is Action.CLI_KILL:
            need(target.pid is not None)
            birth = self._identity["Birth"](target.pid, target.filetime)
            return self._identity["kill_args"](birth), 512, 4.0
        fixed = {
            Action.CID_ABSENCE: ["ps", "-aq", "--no-trunc", "--filter", "id=" + target.cid],
            Action.CID_INSPECT: ["inspect", "--type", "container", target.cid],
            Action.CID_KILL: ["kill", "--signal", "KILL", target.cid],
            Action.CID_REMOVE: ["rm", target.cid],
        }
        limit = 2097152 if action is Action.CID_INSPECT else 65536
        maximum = {Action.CID_KILL: 4.0, Action.CID_REMOVE: 8.0}.get(action, 2.0)
        return [CLI, "--context", "desktop-linux", *fixed[action]], limit, maximum

    def invoke(self, action, target):
        """Watchdog thread only. Caller must validate CID ownership before mutations.

        Unknown spawn/OS failure is HELD by the caller, never a release proof.
        No retry here, no raw output stored in metadata/emergency artifacts.
        """
        need(not self._failed and self._end is not None)
        running_loop = False
        try:
            asyncio.get_running_loop()
            running_loop = True
        except RuntimeError:
            pass
        need(not running_loop)  # reject main-loop misuse before creating any coroutine
        args, limit, maximum = self._arguments(action, target)
        pin_failed = False
        pin_started = time.monotonic()
        try:
            cleanup_pins()
            if time.monotonic() - pin_started > 1.0:
                pin_failed = True
        except Exception:
            pin_failed = True
        if pin_failed:
            self._failed = True
            raise EmergencyError("PIN") from None
        remaining = self._end - time.monotonic()
        timeout = min(maximum, remaining - 10.0)  # reserve both5s final collects of frozen helper
        if timeout <= 0:
            self._failed = True
            raise EmergencyError("BUDGET") from None

        async def execute():
            return await self._bounded["bounded"](args, limit=limit, timeout=timeout)

        failed = False
        result = None
        try:
            result = asyncio.run(execute())  # OWN loop, never main-loop objects
            if time.monotonic() > self._end:
                failed = True
            elif (
                type(result) is not tuple
                or len(result) != 2
                or type(result[0]) is not int
                or result[0] != 0
            ):
                failed = True
            elif type(result[1]) is not bytes or len(result[1]) > limit:
                failed = True
            elif action is Action.CLI_KILL:
                report = self._identity["parse_report"](
                    result[1], self._identity["Birth"](target.pid, target.filetime)
                )
                failed = report["status"] not in ("KILLED", "ABSENT")
        except Exception:
            failed = True
        self._steps.append({"action": action.value, "outcome": "ERROR" if failed else "OK"})
        if failed:
            self._failed = True
            raise EmergencyError("COMMAND") from None
        return result[
            1
        ]  # only to the closed ownership/status parser, never directly to an artifact

    def metadata(self):
        return {"failed": self._failed, "steps": [dict(step) for step in self._steps]}
