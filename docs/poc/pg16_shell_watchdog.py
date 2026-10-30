"""Specific public PG16 reader watchdog/ownership engine. No operational caller; no effects on import."""

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
EMERGENCY_SHA = "54cc8f68ffa7b46e0fbb66c3076cd80fabd849ac2d9284635c2b39253be30ebc"
POLICY_SHA = "96e8a4c430c55e66c95c5c8f5a6fe5c9430fdf8389f418d4c4f7888ac39923b0"
VOLUMES_SHA = "6e3827affcb1a02c00c365a54ecccae5d8e768c188d8232b699efa4c6ddad128"
CASES = frozenset(
    {
        "one",
        "binary",
        "fragmented",
        "retain",
        "bad-magic",
        "bad-role",
        "bad-digit",
        "header-nul",
        "header-inner-nul",
        "header-cr",
        "zero",
        "oversize",
        "short-header",
        "short-body",
        "short-trailer",
        "bad-trailer",
        "trailer-nul",
        "extra-ascii",
        "extra-nul",
        "extra-lf",
        "wait-header",
        "wait-body",
        "wait-trailer",
    }
)


def need(value):
    if not value:
        raise RuntimeError("PG16_READER_WATCHDOG_REFUSED") from None


def volume_sha256(names):
    """Canonical PUBLIC-metadata inventory digest; never a seed/credential digest."""
    raw = (json.dumps(sorted(names), separators=(",", ":")) + "\n").encode("ascii")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Snapshot:
    task: str
    case: str
    command: tuple[str, ...]
    initial_volumes: tuple[str, ...]
    cid: str | None = None
    pid: int | None = None
    filetime: int | None = None

    def __post_init__(self):
        need(type(self.task) is str and re.fullmatch(r"[0-9a-f]{32}", self.task))
        need(type(self.case) is str and self.case in CASES)
        need(type(self.command) is tuple and len(self.command) == 2)
        need(all(type(item) is str for item in self.command))
        need(self.command[0] == "-ec")
        need(type(self.command[1]) is str and 0 < len(self.command[1]) <= 12000)
        need(
            type(self.initial_volumes) is tuple
            and len(self.initial_volumes) <= 256
            and all(
                type(name) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}", name)
                for name in self.initial_volumes
            )
            and len(set(self.initial_volumes)) == len(self.initial_volumes)
        )
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
            previous = self._value.snapshot
            if previous is not None:
                need(snapshot is not None)
                need(
                    (previous.task, previous.case, previous.command, previous.initial_volumes)
                    == (snapshot.task, snapshot.case, snapshot.command, snapshot.initial_volumes)
                )
                need(previous.cid is None or snapshot.cid == previous.cid)
                need(
                    previous.pid is None
                    or (snapshot.pid, snapshot.filetime) == (previous.pid, previous.filetime)
                )
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
        volume_bytes,
    ):
        need(type(store) is Store)
        need(threading.current_thread() is threading.main_thread())
        self.root, self.store, self.cleanup_lock = Path(root), store, cleanup_lock
        self._request_abort = request_abort  # sole callback: main closes call_soon_threadsafe
        self._emergency = namespace(
            emergency_bytes,
            EMERGENCY_SHA,
            "docs/poc/pg16_public_emergency.py",
            "_pg16_reader_watch_executor",
        )
        self._policy = namespace(
            policy_bytes,
            POLICY_SHA,
            "docs/poc/pg16_shell_cleanup_policy.py",
            "_pg16_reader_watch_policy",
        )
        self._volumes = namespace(
            volume_bytes,
            VOLUMES_SHA,
            "docs/poc/pg16_public_volumes.py",
            "_pg16_reader_watch_volumes",
        )
        self._volumes_restored = False
        self._volume_uncertain = False
        self._linked_volumes = frozenset()
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
            "kind": "MASKGW_PG16_READER_EMERGENCY_V1",
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

    def _call(self, action, snapshot, target):
        self._write(action.value, snapshot, "INTENT")
        raw = self._public.invoke(action, target)
        self._write(action.value, snapshot, "COMMAND_OK")
        return raw

    def _inspect(self, snapshot, target):
        raw = self._call(self._emergency["Action"].CID_INSPECT, snapshot, target)
        info = self._policy["P"]["P"]["one"](raw)
        need(
            self._policy["identity"](
                info,
                task=snapshot.task,
                case=snapshot.case,
                command=snapshot.command,
                cid=snapshot.cid,
            )
            == snapshot.cid
        )
        return info

    def _remove_action(self, snapshot, info):
        decision = self._volumes["removal"](frozenset(snapshot.initial_volumes), info.get("Mounts"))
        value = {
            "kind": "MASKGW_PG16_READER_VOLUME_DECISION_V1",
            "cid": snapshot.cid,
            "mode": decision.mode.value,
            "linked_count": len(decision.names),
            "linked_sha256": volume_sha256(decision.names),
            "preexisting_count": len(decision.preexisting),
            "preexisting_sha256": volume_sha256(decision.preexisting),
            "new_anonymous_names": [
                name
                for name in decision.names
                if name not in snapshot.initial_volumes and re.fullmatch(r"[0-9a-f]{64}", name)
            ],
        }
        raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
        need(len(raw) <= 65536)
        path = self.root / ("volume-decision-" + str(self._index).zfill(2) + ".json")
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        self._index += 1
        self._linked_volumes = frozenset(decision.names)
        self._volume_uncertain = decision.mode is self._volumes["Mode"].PRESERVE_UNCERTAIN
        return (
            self._emergency["Action"].CID_REMOVE_V
            if decision.mode is self._volumes["Mode"].WITH_V
            else self._emergency["Action"].CID_REMOVE
        )

    def _volume_final(self, snapshot, target):
        self._volumes_restored = False  # no stale/premature positive evidence state
        raw = self._call(self._emergency["Action"].VOLUME_LIST, snapshot, target)
        final = self._volumes["inventory"](raw)
        delta = self._volumes["difference"](frozenset(snapshot.initial_volumes), final)
        restored = not delta.added and not delta.missing
        value = {
            "kind": "MASKGW_PG16_READER_VOLUME_FINAL_V1",
            "cid": snapshot.cid,
            "initial_count": len(snapshot.initial_volumes),
            "initial_sha256": volume_sha256(snapshot.initial_volumes),
            "final_count": len(final),
            "final_sha256": volume_sha256(final),
            "added_count": len(delta.added),
            "missing_count": len(delta.missing),
            "added_within_linked": set(delta.added) <= self._linked_volumes,
            "restored": restored,
            "uncertain": self._volume_uncertain,
        }
        encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
        need(len(encoded) <= 524288)
        path = self.root / ("volume-final-" + str(self._index).zfill(2) + ".json")
        with path.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        self._index += 1
        self._volumes_restored = restored
        if not self._volumes_restored:
            self._category = "VOLUME_INVENTORY_CHANGED"
            self._write("VOLUMES", snapshot, self._category)
        elif self._volume_uncertain:
            self._category = "VOLUME_OWNERSHIP_UNPROVEN"
            self._write("VOLUMES", snapshot, self._category)

    def _absent(self, snapshot, target):
        raw = self._call(self._emergency["Action"].CID_ABSENCE, snapshot, target)
        if not raw.strip():
            return True
        need(raw.decode("ascii").splitlines() == [snapshot.cid])
        return False

    def _bound(self, snapshot):
        accepted = False
        try:
            if type(snapshot) is Snapshot:
                profile = self._policy["P"]
                case = profile["R"]["Case"](snapshot.case)
                _name, command, _labels, _sha = profile["_capture"](snapshot.task, case)
                accepted = snapshot.command == command
        except Exception:
            pass
        if not accepted:
            raise RuntimeError("PG16_READER_SNAPSHOT_BINDING") from None

    check_snapshot = _bound

    def emergency(self, snapshot):
        """Watchdog-only external actions. NEVER emits ticket/Absent or release."""
        self._held = True  # main still owes quiesce + post-ticket absence even if actions work
        if snapshot is None or snapshot.cid is None:
            self._category = "NO_CID"
            self._write("ABORT", snapshot, "NO_CID")
            return
        accepted = False
        try:
            self._bound(snapshot)
            accepted = True
        except Exception:
            pass
        if not accepted:
            self._category = "SNAPSHOT_BINDING"
            self._write("ABORT", snapshot, "SNAPSHOT_BINDING")
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
                info = self._inspect(snapshot, target)
                if info["State"]["Running"] is True:
                    self._call(action.CID_KILL, snapshot, target)
                    info = self._inspect(snapshot, target)
                need(
                    info["State"]["Running"] is False
                    and type(info["State"]["Pid"]) is int
                    and info["State"]["Pid"] == 0
                )
                raw = self._call(self._remove_action(snapshot, info), snapshot, target)
                need(raw.strip() == snapshot.cid.encode("ascii"))
                need(self._absent(snapshot, target))
            self._cid_absent = True
            self._category = "CID_ABSENT_MAIN_COLLECTION_REQUIRED"
            self._volume_final(snapshot, target)
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
        self.thread = threading.Thread(
            target=self.run, name="maskgw-pg16-reader-watchdog", daemon=False
        )
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
            self.thread.join(timeout=55.0)
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
            "volumes_restored": self._volumes_restored,
            "volume_uncertain": self._volume_uncertain,
            "thread_joined": self._joined,
        }
