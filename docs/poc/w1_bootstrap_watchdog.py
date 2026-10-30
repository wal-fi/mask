"""Specific T4 watchdog/ownership engine. No operational caller; no effects on import."""

from dataclasses import dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time

REPO = Path(__file__).resolve().parents[2]
EMERGENCY_SHA = "2fdc0084f4bf91ad0186779867353d2dfe4ff5943c54d973b4913ec8b12ed2d3"
POLICY_SHA = "e3cf9f4d5b6150c4c3d975fd17d6296348fa14b9e22a43543c9913d34361afd4"
CASES = frozenset(
    {"normal", "retain", "bad-ready", "blackhole", "flood", "cancel-start", "reader-negative"}
)


def need(value):
    if not value:
        raise RuntimeError("T4_WATCHDOG_REFUSED") from None


@dataclass(frozen=True)
class Snapshot:
    task: str
    case: str
    command: tuple[str, ...]
    cid: str | None = None
    pid: int | None = None
    filetime: int | None = None

    def __post_init__(self):
        need(type(self.task) is str and re.fullmatch(r"[0-9a-f]{32}", self.task))
        need(type(self.case) is str and self.case in CASES)
        need(type(self.command) is tuple and len(self.command) == 2 and self.command[0] == "-c")
        need(type(self.command[1]) is str and 0 < len(self.command[1]) <= 26000)
        need(
            self.cid is None or (type(self.cid) is str and re.fullmatch(r"[0-9a-f]{64}", self.cid))
        )
        need((self.pid is None) == (self.filetime is None))
        if self.pid is not None:
            need(self.cid is not None and type(self.pid) is int and 0 < self.pid < 2**32)
            need(type(self.filetime) is int and 0 < self.filetime < 2**63)


@dataclass(frozen=True)
class Observation:
    heartbeat: float
    b_started: float | None
    snapshot: Snapshot | None

    def __post_init__(self):
        need(
            type(self.heartbeat) is float and math.isfinite(self.heartbeat) and self.heartbeat >= 0
        )
        need(
            self.b_started is None
            or (
                type(self.b_started) is float
                and math.isfinite(self.b_started)
                and self.b_started >= 0
            )
        )
        need(self.snapshot is None or type(self.snapshot) is Snapshot)


class Store:
    """Main is the sole publisher. Watchdog receives only immutable data."""

    def __init__(self, now):
        need(type(now) is float and math.isfinite(now) and now >= 0)
        self._lock = threading.Lock()
        self._value = Observation(now, None, None)

    def pulse(self, now):
        need(type(now) is float and math.isfinite(now))
        with self._lock:
            need(now >= self._value.heartbeat)
            self._value = replace(self._value, heartbeat=now)

    def arm_b(self, now):
        need(type(now) is float and math.isfinite(now))
        with self._lock:
            need(self._value.b_started is None and now >= self._value.heartbeat)
            self._value = replace(self._value, b_started=now)

    def publish(self, snapshot):
        need(snapshot is None or type(snapshot) is Snapshot)
        with self._lock:
            self._value = replace(self._value, snapshot=snapshot)

    def read(self):
        with self._lock:
            return self._value


def reason(observation, now):
    need(type(observation) is Observation and type(now) is float and math.isfinite(now))
    if now < observation.heartbeat:
        return "CLOCK"
    if now - observation.heartbeat >= 15.0:
        return "HEARTBEAT"
    if observation.b_started is not None and now - observation.b_started >= 600.0:
        return "DEADLINE"
    return None


def namespace(raw, digest, relative, name):
    need(type(raw) is bytes and len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == digest)
    result = {"__name__": name, "__file__": str(REPO / relative)}
    exec(compile(raw, result["__file__"], "exec"), result)
    return result


class Watchdog:
    def __init__(
        self,
        root,
        store,
        cleanup_lock,
        request_abort,
        emergency_bytes,
        policy_bytes,
        bounded_bytes,
        identity_bytes,
    ):
        need(type(store) is Store)
        self.root, self.store, self.cleanup_lock = Path(root), store, cleanup_lock
        self._request_abort = request_abort  # sole callback: main closes call_soon_threadsafe
        self._emergency = namespace(
            emergency_bytes,
            EMERGENCY_SHA,
            "docs/poc/w1_bootstrap_emergency.py",
            "_t4_watch_executor",
        )
        self._policy = namespace(
            policy_bytes, POLICY_SHA, "docs/poc/w1_bootstrap_probe.py", "_t4_watch_policy"
        )
        self._public = self._emergency["PublicEmergency"](bounded_bytes, identity_bytes)
        self.stop, self.fired, self.ack = threading.Event(), threading.Event(), threading.Event()
        self.thread = None
        self._index = 0
        self._started = False
        self._held = False
        self._category = None
        self._cid_absent = False
        self._joined = False

    def _write(self, action, snapshot, category):
        value = {
            "kind": "MASKGW_T4_EMERGENCY_V1",
            "action": action,
            "category": category,
            "cid": None if snapshot is None else snapshot.cid,
            "pid": None if snapshot is None else snapshot.pid,
        }
        raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
        need(len(raw) <= 4096)
        path = self.root / ("emergency-" + str(self._index).zfill(2) + ".json")
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        self._index += 1

    def _intent(self, snapshot):
        """Rehydrate admitted immutable capture, never rerun its source-reading constructor."""
        policy = self._policy
        intent = object.__new__(policy["Intent"])
        object.__setattr__(intent, "task", snapshot.task)
        object.__setattr__(intent, "case", policy["Case"](snapshot.case))
        object.__setattr__(intent, "command", snapshot.command)
        return intent

    def _call(self, action, snapshot, target):
        self._write(action.value, snapshot, "INTENT")
        raw = self._public.invoke(action, target)
        self._write(action.value, snapshot, "COMMAND_OK")
        return raw

    def _inspect(self, snapshot, target, intent):
        raw = self._call(self._emergency["Action"].CID_INSPECT, snapshot, target)
        values = json.loads(raw)
        need(type(values) is list and len(values) == 1)
        info = values[0]
        need(self._policy["identity"](info, intent) == snapshot.cid)
        return info

    def _absent(self, snapshot, target):
        raw = self._call(self._emergency["Action"].CID_ABSENCE, snapshot, target)
        if not raw.strip():
            return True
        need(raw.decode("ascii").splitlines() == [snapshot.cid])
        return False

    def emergency(self, snapshot):
        """Watchdog-only external actions. NEVER emits ticket/Absent or release."""
        self._held = True  # main still owes quiesce + post-ticket absence even if actions work
        if snapshot is None or snapshot.cid is None:
            self._category = "NO_CID"
            self._write("ABORT", snapshot, "NO_CID")
            return
        self._public.begin()
        target = self._emergency["Target"](snapshot.cid, snapshot.pid, snapshot.filetime)
        action = self._emergency["Action"]
        if snapshot.pid is not None:
            self._call(action.CLI_KILL, snapshot, target)
        else:
            self._write("CLI_KILL", snapshot, "IDENTITY_UNKNOWN_NO_PID_GUESS")
        if not self.cleanup_lock.acquire(timeout=1.0):
            self._category = "CLEANUP_LOCK"
            return
        try:
            if not self._absent(snapshot, target):
                intent = self._intent(snapshot)
                info = self._inspect(snapshot, target, intent)
                if info["State"]["Running"] is True:
                    self._call(action.CID_KILL, snapshot, target)
                    info = self._inspect(snapshot, target, intent)
                need(
                    info["State"]["Running"] is False
                    and type(info["State"]["Pid"]) is int
                    and info["State"]["Pid"] == 0
                )
                raw = self._call(action.CID_REMOVE, snapshot, target)
                need(raw.strip() == snapshot.cid.encode("ascii"))
                need(self._absent(snapshot, target))
            self._cid_absent = True
            self._category = "CID_ABSENT_MAIN_COLLECTION_REQUIRED"
        finally:
            self.cleanup_lock.release()

    def run(self):
        while not self.stop.wait(0.1):
            try:
                observation = self.store.read()
                why = reason(observation, time.monotonic())
            except Exception:
                self.fired.set()
                self._held = True
                self._category = "MONITOR_ERROR"
                try:
                    self._request_abort()
                except Exception:
                    pass
                return
            if why is None:
                continue
            self.fired.set()
            self._category = why
            try:
                self._write("TRIGGER", observation.snapshot, why)
                self._request_abort()  # no asyncio object inspected or closed here
                self.ack.wait(2.0)
                if why == "CLOCK":
                    self._held = True
                    self._category = "CLOCK_UNPROVEN"
                else:
                    self.emergency(observation.snapshot)
            except Exception:
                self._held = True
                self._category = "EMERGENCY_ERROR"
                try:
                    self._write("ABORT", observation.snapshot, "EMERGENCY_ERROR")
                except Exception:
                    pass
            return

    def start(self):
        need(not self._started)
        self._started = True
        self.thread = threading.Thread(target=self.run, name="maskgw-t4-watchdog", daemon=False)
        failed = False
        try:
            self.thread.start()
        except Exception:
            failed = True
        if failed:
            self.fired.set()
            self._held = True
            self._category = "THREAD_START_UNPROVEN"
        return not failed

    def close(self):
        need(self._started and self.thread is not None)
        self.stop.set()
        joined = False
        try:
            self.thread.join(timeout=50.0)
            joined = not self.thread.is_alive()
        except Exception:
            pass
        self._joined = joined
        if not joined:
            self._held = True
            self._category = "THREAD_JOIN_UNPROVEN"
        return joined  # only thread collection, never a CID/CLI/owner release proof

    def metadata(self):
        return {
            "fired": self.fired.is_set(),
            "held": self._held,
            "category": self._category,
            "cid_absent": self._cid_absent,
            "released": False,
            "thread_joined": self._joined,
        }
