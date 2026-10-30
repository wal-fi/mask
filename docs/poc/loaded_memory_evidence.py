"""Isolated HELD evidence codec/tap. No backend, entrypoint, timers or workload.

Replay verifies logical consistency, not wall time, physical origin or real EOF.
Actual integration and another run require separate review. Frozen sources stay
unchanged; all module loading below is source reading, not lab IO.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from functools import wraps
from pathlib import Path
from types import SimpleNamespace

PROFILE = "loaded-as128-held-v1"
FALLBACK = (
    b'{"profile":"loaded-as128-held-v1","outcome":"inconclusive",'
    b'"evidence_failure":"EVIDENCE","total_memory_contained":false}\n'
)
MAX_REPORT, MAX_LINE = 65536, 1024
FIELDS = {
    "profile",
    "case",
    "outcome",
    "total_memory_contained",
    "original_report",
    "original_sha256",
    "original_bytes",
    "validated_held",
}


class EvidenceFault(Exception):
    def __init__(self):
        super().__init__("EVIDENCE")


def closed(method):
    @wraps(method)
    def guarded(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except BaseException:
            pass
        raise EvidenceFault()  # Outside except: no original message/cause/context.

    return guarded


def load_host():
    path = Path(__file__).with_name("run_linux_loaded.py")
    if hashlib.sha256(path.read_bytes()).hexdigest() != (
        "d95cdfe231ab273fba96c4ecd808ce829327caea466992ee90c98c9d27a0e821"
    ):
        raise EvidenceFault()
    spec = importlib.util.spec_from_file_location("held_frozen_host", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HOST = load_host()
CORE, SUPERVISOR = HOST.CORE, HOST.SUPERVISOR


class Tap:
    """Only read is intercepted. A syntactic candidate is not yet evidence."""

    def __init__(self, io):
        self.io, self._lines, self.broken = io, (), False
        self.prepare, self.spawn, self.clock = io.prepare, io.spawn, io.clock
        self.observe, self.send, self.sleep = io.observe, io.send, io.sleep
        self.wait, self.cleanup, self.final = io.wait, io.cleanup, io.final

    @property
    def pid(self):
        return self.io.pid

    @property
    def lines(self):
        return self._lines

    def read(self):
        if self.broken:
            raise EvidenceFault()
        raw = self.io.read()  # Delegated faults keep their category/identity.
        return self._capture(raw)

    @closed
    def _capture(self, raw):
        try:
            return self._candidate(raw)
        except BaseException:
            self.broken = True
        raise EvidenceFault()

    def _candidate(self, raw):
        try:
            CORE.decode_held(raw)
        except CORE.ProtocolFault:
            return raw  # Ordinary/invalid lines go unchanged to supervise.
        if len(self._lines) == 2:
            self.broken = True
            raise EvidenceFault()
        self._lines += (raw,)  # bytes are immutable; at most two <=1KiB lines.
        return raw


def _observation(report, index):
    observations = report["observations"]
    if type(index) is not int or not 0 <= index < len(observations):
        raise EvidenceFault()
    return observations[index]


def _replay(report, lines, case, expected, digest):
    """Host validation must precede this. All clock advances are synthetic."""
    observations = report["observations"]
    pid = observations[0]["inventory"][1]
    if type(pid) is not int or pid < 2:
        raise EvidenceFault()
    if any(item["inventory"] != [1, pid] for item in observations):
        raise EvidenceFault()
    if any(item["fds"] is not None for item in observations[1:4]):
        raise EvidenceFault()
    logical = SimpleNamespace(now=0.0)
    core = CORE.PressureProtocol(
        case,
        expected,
        deadline=20.0,
        clock=lambda: logical.now,
        validator=HOST.PROBE.validate_inventory,
        pid=pid,
    )
    first, loaded = observations[0], observations[4]
    core.ready(first["vm"], first["limits"], pid=pid, ppid=1)
    core.admit_imports(
        HOST.PROBE.unpack_inventory(report["module_inventory"]), loaded["vm"], loaded["limits"]
    )
    index = 5
    for raw in lines:
        pressure = _observation(report, index)
        core.pressure(pressure["vm"], pressure["limits"])
        core.held(raw)
        plateau = _observation(report, index + 1)
        core.release(
            plateau["vm"],
            plateau["limits"],
            anon=plateau["cgroup"]["stat"]["anon"],
            inventory=plateau["inventory"],
        )
        released = _observation(report, index + 2)
        complete = core.released(
            released["vm"], released["limits"], anon=released["cgroup"]["stat"]["anon"]
        )
        index += 3
        while not complete:
            delay = core.release_wait()
            if type(delay) is not float or delay != 1.0:
                raise EvidenceFault()
            logical.now += delay
            sample = _observation(report, index)
            complete = core.release_sample(
                sample["vm"], sample["limits"], anon=sample["cgroup"]["stat"]["anon"]
            )
            index += 1
    if index != len(observations) - 1 or observations[index]["fds"] != first["fds"]:
        raise EvidenceFault()
    core.finish()
    outcome = core.completed(
        {"phase": "done"},
        eof=True,
        returncode=report["member_returncode"],
        cleanup=True,
        inventory=report["final_inventory"],
    )
    if outcome != report["outcome"]:
        raise EvidenceFault()
    if case == "control" and not core.control_digest() == report["inventory_digest"] == digest:
        raise EvidenceFault()


def _validate(data, case, expected):
    CORE.parse_case_args(["--case", case, "--expected", expected])
    if (
        set(data) == {"profile", "outcome", "evidence_failure", "total_memory_contained"}
        and all(type(data[key]) is str for key in ("profile", "outcome", "evidence_failure"))
        and data["profile"] == PROFILE
        and data["outcome"] == "inconclusive"
        and data["evidence_failure"] == "EVIDENCE"
        and data["total_memory_contained"] is False
    ):
        return data
    if (
        set(data) != FIELDS
        or type(data["profile"]) is not str
        or data["profile"] != PROFILE
        or type(data["case"]) is not str
        or data["case"] != case
        or type(data["outcome"]) is not str
        or data["total_memory_contained"] is not False
        or type(data["original_report"]) is not str
        or type(data["original_bytes"]) is not int
        or not 1 <= data["original_bytes"] <= MAX_REPORT
        or not CORE.valid_digest(data["original_sha256"])
        or type(data["validated_held"]) is not list
    ):
        raise EvidenceFault()
    original = data["original_report"].encode("ascii")
    if len(original) != data["original_bytes"] or (
        hashlib.sha256(original).hexdigest() != data["original_sha256"]
    ):
        raise EvidenceFault()
    report = HOST.decode_report(original)
    digest = HOST.validate_report(report, case, expected)
    if data["outcome"] != report["outcome"]:
        raise EvidenceFault()
    positive = report["outcome"] in ("control_ok", "imposed")
    count = (2 if case == "control" else 1) if positive else 0
    if len(data["validated_held"]) != count:
        raise EvidenceFault()
    lines = []
    for text in data["validated_held"]:
        if type(text) is not str:
            raise EvidenceFault()
        raw = text.encode("ascii")
        CORE.decode_held(raw)
        lines.append(raw)
    if positive:
        _replay(report, lines, case, expected, digest)
    return data


@closed
def decode(raw, case, expected):
    """Returns a fresh validated dict; FALLBACK is inconclusive, never positive."""
    return _validate(HOST.decode_report(raw), case, expected)


def encode(original_raw, lines, case, expected):
    try:
        report = HOST.decode_report(original_raw)
        HOST.validate_report(report, case, expected)
        if type(lines) is not tuple or len(lines) > 2:
            raise EvidenceFault()
        # Negative reports never expose syntactic or partially validated HELD.
        selected = lines if report["outcome"] in ("control_ok", "imposed") else ()
        if any(type(raw) is not bytes or not 1 <= len(raw) <= MAX_LINE for raw in selected):
            raise EvidenceFault()
        data = {
            "profile": PROFILE,
            "case": case,
            "outcome": report["outcome"],
            "total_memory_contained": False,
            "original_report": original_raw.decode("ascii"),
            "original_sha256": hashlib.sha256(original_raw).hexdigest(),
            "original_bytes": len(original_raw),
            "validated_held": [raw.decode("ascii") for raw in selected],
        }
        raw = json.dumps(data, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
        if len(raw) > MAX_REPORT:
            raise EvidenceFault()
        decode(raw, case, expected)
        return raw
    except BaseException:
        return FALLBACK


def capture(case, expected, io, parts, *, deadline):
    try:
        CORE.parse_case_args(["--case", case, "--expected", expected])
        tap = Tap(io)
        report = SUPERVISOR.supervise(case, expected, tap, parts, deadline=deadline)
        if tap.broken:
            return FALLBACK
        return encode(SUPERVISOR.bounded_report(report), tap.lines, case, expected)
    except BaseException:
        return FALLBACK
