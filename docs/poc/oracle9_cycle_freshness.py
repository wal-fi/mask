"""Pure one-attempt Desktop cycle age admission. NO OS, clock, file or CLI I/O.

Caller samples the reviewed Windows binding and persists EACH returned state
before acting. A decision is explicit, not implied by phase. This is neither
Docker ownership nor authority to restore/stop anything.
"""

from dataclasses import dataclass, replace
from enum import StrEnum
import json

TOTAL_MS = 300000
GAP_MS = 30000
OBSERVE_MIN_MS = 10000
OBSERVATIONS = 9
UTC_SLACK_100NS = 20000000
MAX_U64 = (1 << 64) - 1
MAX_FILETIME = (1 << 63) - 1


def need(value):
    if not value:
        raise ValueError("CYCLE_SCHEMA")


def number(value, maximum):
    need(
        type(value) is str
        and 1 <= len(value) <= 20
        and value.isascii()
        and value.isdecimal()
        and (value == "0" or not value.startswith("0"))
    )
    result = int(value)
    need(result <= maximum)
    return result


@dataclass(frozen=True, slots=True)
class Sample:
    boot: str
    tick_ms: str
    utc_100ns: str

    def __post_init__(self):
        need(number(self.boot, MAX_FILETIME) > 0)
        number(self.tick_ms, MAX_U64)
        need(number(self.utc_100ns, MAX_FILETIME) > 0)


class Phase(StrEnum):
    A = "A"
    OBSERVING = "OBSERVING"
    READY = "READY"
    FAILED = "FAILED"
    ABORTED = "ABORTED"
    B_CONSUMED = "B_CONSUMED"


class Decision(StrEnum):
    ACCEPT = "ACCEPT"
    REFUSE = "REFUSE"

    def __bool__(self):
        raise TypeError("compare cycle admission explicitly")


class Reason(StrEnum):
    ORDER = "ORDER"
    TERMINAL = "TERMINAL"
    BOOT = "BOOT"
    ROLLBACK = "ROLLBACK"
    DISAGREEMENT = "DISAGREEMENT"
    TOTAL_AGE = "TOTAL_AGE"
    GAP = "GAP"
    TOO_EARLY = "TOO_EARLY"


@dataclass(frozen=True, slots=True)
class Cycle:
    anchor: Sample
    last: Sample
    phase: Phase
    observations: int
    failure: Reason | None = None

    def __post_init__(self):
        need(type(self.anchor) is Sample and type(self.last) is Sample)
        Sample.__post_init__(self.anchor)
        Sample.__post_init__(self.last)
        need(type(self.phase) is Phase and type(self.observations) is int)
        need(0 <= self.observations <= OBSERVATIONS)
        need(self.anchor.boot == self.last.boot)
        need(int(self.last.tick_ms) >= int(self.anchor.tick_ms))
        need(int(self.last.utc_100ns) >= int(self.anchor.utc_100ns))
        elapsed = int(self.last.tick_ms) - int(self.anchor.tick_ms)
        utc_elapsed = int(self.last.utc_100ns) - int(self.anchor.utc_100ns)
        extra = {Phase.A: 0, Phase.OBSERVING: 0, Phase.READY: 1}.get(self.phase, 2)
        need(self.observations * OBSERVE_MIN_MS <= elapsed <= TOTAL_MS)
        need(elapsed <= (self.observations + extra) * GAP_MS)
        need(abs(utc_elapsed - elapsed * 10000) <= UTC_SLACK_100NS + elapsed * 10)
        need((self.phase is Phase.FAILED) == (type(self.failure) is Reason))
        need(self.failure is None or type(self.failure) is Reason)
        if self.phase is Phase.A:
            need(self.observations == 0 and self.anchor == self.last)
        if self.phase is Phase.OBSERVING:
            need(1 <= self.observations <= OBSERVATIONS)
        if self.phase in (Phase.READY, Phase.B_CONSUMED):
            need(self.observations == OBSERVATIONS)


@dataclass(frozen=True, slots=True)
class Admission:
    state: Cycle
    decision: Decision
    reason: Reason | None


def start(sample):
    need(type(sample) is Sample)
    return Cycle(sample, sample, Phase.A, 0)


def _check_age(state, sample):
    if sample.boot != state.anchor.boot:
        return Reason.BOOT
    for base in (state.anchor, state.last):
        ticks = int(sample.tick_ms) - int(base.tick_ms)
        utc = int(sample.utc_100ns) - int(base.utc_100ns)
        if ticks < 0 or utc < 0:
            return Reason.ROLLBACK
        # 1 ms = 10000 units of 100ns; 0.1% of tick ms = tick * 10 units.
        if abs(utc - ticks * 10000) > UTC_SLACK_100NS + ticks * 10:
            return Reason.DISAGREEMENT
    if int(sample.tick_ms) - int(state.anchor.tick_ms) > TOTAL_MS:
        return Reason.TOTAL_AGE
    if int(sample.tick_ms) - int(state.last.tick_ms) > GAP_MS:
        return Reason.GAP
    return None


def advance(state, sample, action):
    need(type(state) is Cycle and type(sample) is Sample and type(action) is str)
    Cycle.__post_init__(state)
    Sample.__post_init__(sample)
    if state.phase in (Phase.FAILED, Phase.ABORTED, Phase.B_CONSUMED):
        return Admission(state, Decision.REFUSE, Reason.TERMINAL)
    reason = _check_age(state, sample)
    count, phase = state.observations, state.phase
    if reason is None:
        if action == "OBSERVE" and phase in (Phase.A, Phase.OBSERVING) and count < OBSERVATIONS:
            if int(sample.tick_ms) - int(state.last.tick_ms) < OBSERVE_MIN_MS:
                reason = Reason.TOO_EARLY
            else:
                count, phase = count + 1, Phase.OBSERVING
        elif action == "READY" and phase is Phase.OBSERVING and count == OBSERVATIONS:
            phase = Phase.READY
        elif action == "B" and phase is Phase.READY:
            phase = Phase.B_CONSUMED
        else:
            reason = Reason.ORDER
    if reason is not None:
        return Admission(
            replace(state, phase=Phase.FAILED, failure=reason), Decision.REFUSE, reason
        )
    return Admission(Cycle(state.anchor, sample, phase, count), Decision.ACCEPT, None)


def abort(state):
    need(type(state) is Cycle)
    Cycle.__post_init__(state)
    if state.phase in (Phase.FAILED, Phase.ABORTED, Phase.B_CONSUMED):
        return state
    return replace(state, phase=Phase.ABORTED)


def _sample_map(sample):
    return {"boot": sample.boot, "tick_ms": sample.tick_ms, "utc_100ns": sample.utc_100ns}


def encode(state):
    need(type(state) is Cycle)
    Cycle.__post_init__(state)
    value = {
        "version": 1,
        "anchor": _sample_map(state.anchor),
        "last": _sample_map(state.last),
        "phase": state.phase.value,
        "observations": state.observations,
        "failure": None if state.failure is None else state.failure.value,
    }
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def _pairs(values):
    result = {}
    for name, value in values:
        need(name not in result)
        result[name] = value
    return result


def decode(raw):
    need(type(raw) is bytes and 0 < len(raw) <= 2048)
    value = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs)
    need(
        type(value) is dict
        and set(value) == {"version", "anchor", "last", "phase", "observations", "failure"}
    )
    need(type(value["version"]) is int and value["version"] == 1)
    for name in ("anchor", "last"):
        need(type(value[name]) is dict and set(value[name]) == {"boot", "tick_ms", "utc_100ns"})
    state = Cycle(
        Sample(**value["anchor"]),
        Sample(**value["last"]),
        Phase(value["phase"]),
        value["observations"],
        None if value["failure"] is None else Reason(value["failure"]),
    )
    need(encode(state) == raw)  # canonical, no duplicate keys or alternative representations
    return state
