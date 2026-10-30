"""Pure lab protocol only. Trusted collectors supply facts; no OS proof or I/O."""

from __future__ import annotations

import hashlib
import json
import math
from functools import wraps

MIB = 1024 * 1024
AS_BYTES = 128 * MIB
READY_MAX = 124 * MIB
STEP = 4 * MIB
TARGET = 40 * MIB
PAGE = 4096
MAX_ROWS = 1500
MAX_RAW = 1024 * 1024
MAX_LINE = 1024
DOMAIN = b"loaded-as128-v1\n"
CASES = ("control", "private", "shared")
HELD_FIELDS = {
    "phase",
    "kind",
    "limits",
    "vm",
    "accepted_bytes",
    "touched_pages",
    "blocks",
    "failure",
    "errno",
}
CODES = {
    "CASE",
    "DIGEST",
    "DEADLINE",
    "STATE",
    "SCHEMA",
    "INVENTORY",
    "LIMIT",
    "OBSERVED_FAIL",
    "OBSERVED_INCONCLUSIVE",
    "RELEASE",
    "PROCESS",
}


class ProtocolFault(Exception):
    def __init__(self, code):
        self.code = code if code in CODES else "SCHEMA"
        super().__init__(self.code)


def closed(method):
    """Any failed public transition is terminal; never expose an unexpected chain."""

    @wraps(method)
    def guarded(self, *args, **kwargs):
        code = "PROCESS" if method.__name__ in ("release", "completed") else "SCHEMA"
        try:
            return method(self, *args, **kwargs)
        except ProtocolFault as error:
            if type(error) is ProtocolFault:
                code = error.code
        except BaseException:
            pass
        self._abort(code)  # Outside except: no cause/context from the original failure.

    return guarded


def integer(value, minimum=0, maximum=1 << 50):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ProtocolFault("SCHEMA")
    return value


def valid_digest(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def parse_case_args(args):
    if (
        type(args) is not list
        or len(args) != 4
        or any(type(item) is not str for item in args)
        or args[0] != "--case"
        or args[2] != "--expected"
        or args[1] not in CASES
        or (args[3] != "-" if args[1] == "control" else not valid_digest(args[3]))
    ):
        raise ProtocolFault("CASE")
    return args[1], args[3]


def inventory_digest(entries, validator):
    """One bounded digest for host and supervisor; validator is trusted, not origin proof."""
    if type(entries) is not list or not 1 <= len(entries) <= MAX_ROWS:
        raise ProtocolFault("INVENTORY")
    rows, names = [], set()
    for entry in entries:
        if (
            type(entry) is not list
            or len(entry) != 2
            or type(entry[0]) is not int
            or entry[0] not in (-1, 0, 1, 2)
            or type(entry[1]) is not list
            or len(entry[1]) != 3
            or any(type(value) is not str or len(value) > 768 for value in entry[1])
        ):
            raise ProtocolFault("INVENTORY")
        row = entry[1]
        if row[0] in names:
            raise ProtocolFault("INVENTORY")
        names.add(row[0])
        rows.append(tuple(row))
    invalid = False
    try:
        validator(entries)
    except BaseException:
        invalid = True
    if invalid:
        raise ProtocolFault("INVENTORY")  # Outside except: no original exception chain.
    result, size = hashlib.sha256(DOMAIN), 0
    encoder = json.JSONEncoder(separators=(",", ":"), ensure_ascii=True)
    for part in encoder.iterencode(sorted(rows)):
        raw = part.encode("ascii")
        size += len(raw)
        if size > MAX_RAW:
            raise ProtocolFault("INVENTORY")
        result.update(raw)
    return result.hexdigest()


def facts(vm, limits):
    if (
        type(vm) is not dict
        or any(type(key) is not str for key in vm)
        or set(vm) != {"size", "peak", "rss", "threads"}
    ):
        raise ProtocolFault("SCHEMA")
    for value in vm.values():
        integer(value)
    if vm["threads"] != 1 or not 0 < vm["size"] <= vm["peak"] or vm["rss"] > vm["size"]:
        raise ProtocolFault("SCHEMA")
    if type(limits) is not list or len(limits) != 2 or any(type(x) is not int for x in limits):
        raise ProtocolFault("SCHEMA")
    return dict(vm)


def unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ProtocolFault("SCHEMA")
        result[key] = value
    return result


def invalid_constant(_value):
    raise ProtocolFault("SCHEMA")


def decode_held(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_LINE or not raw.endswith(b"\n"):
        raise ProtocolFault("SCHEMA")
    invalid = False
    try:
        event = json.loads(
            raw.decode("ascii"), object_pairs_hook=unique_pairs, parse_constant=invalid_constant
        )
    except Exception:
        invalid = True
    if invalid:
        raise ProtocolFault("SCHEMA")
    if type(event) is not dict or set(event) != HELD_FIELDS:
        raise ProtocolFault("SCHEMA")
    if raw != json.dumps(event, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n":
        raise ProtocolFault("SCHEMA")
    if event["phase"] != "held" or event["kind"] not in ("private", "shared"):
        raise ProtocolFault("SCHEMA")
    facts(event["vm"], event["limits"])
    accepted = integer(event["accepted_bytes"], 0, TARGET)
    blocks = integer(event["blocks"], 0, TARGET // STEP)
    pages = integer(event["touched_pages"], 0, TARGET // PAGE)
    if accepted % STEP or blocks != accepted // STEP or pages != accepted // PAGE:
        raise ProtocolFault("SCHEMA")
    failure, number = event["failure"], event["errno"]
    if failure not in ("NONE", "MEMORY", "ENOMEM", "OTHER"):
        raise ProtocolFault("SCHEMA")
    if number is not None:
        integer(number, 1, 4095)
    if (
        (failure in ("NONE", "MEMORY") and number is not None)
        or (failure == "ENOMEM" and number != 12)
        or (failure != "NONE" and accepted == TARGET)
    ):
        raise ProtocolFault("SCHEMA")
    return event


class PressureProtocol:
    """Commands follow trusted observations. This does not collect or enforce them."""

    @closed
    def __init__(self, case, expected, *, deadline, clock, validator, pid):
        self.state, self.outcome = "READY", "inconclusive"
        self.case, self.expected = parse_case_args(["--case", case, "--expected", expected])
        self.pid = integer(pid, 2)
        self.clock, self.validator, self.deadline = clock, validator, deadline
        self.last_time = 0
        self.kind = "shared" if case == "shared" else "private"
        self._digest, self._held = None, None
        self.pre_size = self.plateau_anon = self.release_samples = 0
        self.next_sample = 0
        now = self._tick()
        if deadline - now > 20:
            self._abort("DEADLINE")

    def _abort(self, code):
        self.state = "ABORTED"
        self.outcome = "fail" if code == "OBSERVED_FAIL" else "inconclusive"
        raise ProtocolFault(code)

    def _tick(self):
        invalid = False
        try:
            now = self.clock()
        except BaseException:
            invalid = True
        if invalid:
            self._abort("DEADLINE")
        if (
            type(now) not in (int, float)
            or type(self.deadline) not in (int, float)
            or not 0 <= now <= 1 << 50
            or not 0 <= self.deadline <= 1 << 50
            or not math.isfinite(now)
            or not math.isfinite(self.deadline)
            or now < self.last_time
            or now >= self.deadline
        ):
            self._abort("DEADLINE")
        self.last_time = now
        return now

    def _guard(self, state):
        if self.state != state:
            self._abort("STATE")
        return self._tick()

    def _facts(self, vm, limits):
        error = None
        try:
            result = facts(vm, limits)
        except ProtocolFault:
            error = "SCHEMA"
        if error:
            self._abort(error)
        expected = [-1, -1] if self.case == "control" else [AS_BYTES, AS_BYTES]
        if limits != expected:
            self._abort("LIMIT")
        if self.case != "control" and result["peak"] > AS_BYTES:
            self._abort("OBSERVED_FAIL")
        return result

    @closed
    def ready(self, vm, limits, *, pid, ppid):
        self._guard("READY")
        observed = self._facts(vm, limits)
        if type(pid) is not int or pid != self.pid or type(ppid) is not int or ppid != 1:
            self._abort("PROCESS")
        if self.case != "control" and observed["size"] > READY_MAX:
            self._abort("LIMIT")
        self.state = "IMPORTING"
        return b"GO_IMPORTS\n"

    @closed
    def admit_imports(self, rows, vm, limits):
        self._guard("IMPORTING")
        invalid = False
        try:
            value = inventory_digest(rows, self.validator)
        except BaseException:
            invalid = True
        if invalid:
            self._abort("INVENTORY")
        self._guard("IMPORTING")  # Validator/hash time never renews the deadline.
        self._facts(vm, limits)
        if self.case != "control" and value != self.expected:
            self._abort("DIGEST")
        self._digest, self.state = value, "ADMITTED"
        return True  # Do not export a control digest before successful final cleanup.

    @closed
    def pressure(self, vm, limits):
        self._guard("ADMITTED")
        self.pre_size = self._facts(vm, limits)["size"]
        self.state = "PRESSURING"
        return b"PRESSURE_PRIVATE\n" if self.kind == "private" else b"PRESSURE_SHARED\n"

    @closed
    def held(self, raw):
        self._guard("PRESSURING")
        invalid = False
        try:
            event = decode_held(raw)
        except BaseException:
            invalid = True
        if invalid:
            self._abort("SCHEMA")
        self._held = event
        observed = self._facts(event["vm"], event["limits"])
        if event["kind"] != self.kind:
            self._abort("SCHEMA")
        if self.case == "control":
            ok = event["failure"] == "NONE" and event["accepted_bytes"] == TARGET
        else:
            if event["failure"] == "NONE" and event["accepted_bytes"] == TARGET:
                self._abort("OBSERVED_FAIL")
            ok = (
                event["failure"] in ("MEMORY", "ENOMEM")
                and event["accepted_bytes"] >= STEP
                and observed["peak"] <= AS_BYTES
            )
        if not ok:
            self._abort("OBSERVED_INCONCLUSIVE")
        self.state = "HELD"
        return "control_ok" if self.case == "control" else "imposed"

    @closed
    def release(self, vm, limits, *, anon, inventory):
        self._guard("HELD")
        observed = self._facts(vm, limits)
        if observed["peak"] != self._held["vm"]["peak"]:
            self._abort("OBSERVED_INCONCLUSIVE")
        if (
            type(inventory) is not list
            or len(inventory) != 2
            or any(type(value) is not int for value in inventory)
            or inventory != [1, self.pid]
            or type(anon) is not int
            or not 0 <= anon <= 1 << 50
        ):
            self._abort("PROCESS")
        self.plateau_anon, self.state = anon, "RELEASE_SENT"
        return b"RELEASE_PRIVATE\n" if self.kind == "private" else b"RELEASE_SHARED\n"

    def _release_check(self, vm, limits, anon, now):
        observed = self._facts(vm, limits)
        if type(anon) is not int or not 0 <= anon <= 1 << 50:
            self._abort("SCHEMA")
        if self.case != "control" or self.kind == "shared":
            self.state = "FINISH_READY"
            return True
        self.release_samples += 1
        if observed["size"] <= self.pre_size + STEP and self.plateau_anon - anon >= 32 * MIB:
            self.kind, self.state = "shared", "ADMITTED"
            return True
        if self.release_samples >= 5:
            self._abort("RELEASE")
        self.state, self.next_sample = "RELEASE_CHECK", now + 1
        return False

    @closed
    def released(self, vm, limits, *, anon):
        now = self._guard("RELEASE_SENT")
        return self._release_check(vm, limits, anon, now)

    @closed
    def release_wait(self):
        now = self._guard("RELEASE_CHECK")
        if self.deadline - now < 1:
            self._abort("DEADLINE")
        return 1.0

    @closed
    def release_sample(self, vm, limits, *, anon):
        now = self._guard("RELEASE_CHECK")
        if now < self.next_sample:
            self._abort("STATE")
        return self._release_check(vm, limits, anon, now)

    @closed
    def finish(self):
        self._guard("FINISH_READY")
        self.state = "EXITING"
        return b"FINISH\n"

    @closed
    def completed(self, marker, *, eof, returncode, cleanup, inventory):
        self._guard("EXITING")
        if (
            type(marker) is not dict
            or len(marker) != 1
            or any(type(key) is not str for key in marker)
            or set(marker) != {"phase"}
            or type(marker["phase"]) is not str
            or marker["phase"] != "done"
            or eof is not True
            or type(returncode) is not int
            or returncode != 0
            or cleanup is not True
            or type(inventory) is not list
            or len(inventory) != 1
            or any(type(value) is not int for value in inventory)
            or inventory != [1]
        ):
            self._abort("PROCESS")
        self.state = "DONE"
        self.outcome = "control_ok" if self.case == "control" else "imposed"
        return self.outcome

    @closed
    def control_digest(self):
        self._guard("DONE")
        if self.case != "control":
            self._abort("STATE")
        return self._digest
