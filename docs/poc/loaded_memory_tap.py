"""Capture-only transport, stdlib only. No host validator, backend or workload.

HELD lines are syntactic candidates, never independently validated measurements.
The host must persist transport then validate original/replay through E.
"""

from __future__ import annotations

import json

PROFILE = "loaded-as128-held-transport-v1"
FALLBACK = (
    b'{"profile":"loaded-as128-held-transport-v1","outcome":"inconclusive",'
    b'"transport_failure":"EVIDENCE","total_memory_contained":false}\n'
)


class TapFault(Exception):
    def __init__(self):
        super().__init__("TAP")


class Tap:
    def __init__(self, io, core):
        self.io, self.core, self._lines, self.broken = io, core, (), False
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
            raise TapFault()
        raw = self.io.read()  # Delegated errors keep type, identity and category.
        try:
            return self._candidate(raw)
        except BaseException:
            self.broken = True
        raise TapFault()  # Only own failure, outside except: no original context.

    def _candidate(self, raw):
        try:
            self.core.decode_held(raw)
        except self.core.ProtocolFault:
            return raw
        if len(self._lines) == 2:
            raise TapFault()
        self._lines += (raw,)
        return raw


def transport(original, held, broken):
    """Opaque original + bounded candidates. No semantic success is declared."""
    try:
        if (
            type(original) is not bytes
            or not 1 <= len(original) <= 65536
            or not original.endswith(b"\n")
            or original.count(b"\n") != 1
            or type(held) is not tuple
            or len(held) > 2
            or type(broken) is not bool
            or any(type(raw) is not bytes or not 1 <= len(raw) <= 1024 for raw in held)
        ):
            return FALLBACK
        value = {
            "profile": PROFILE,
            "original": original.decode("ascii"),
            "held": [raw.decode("ascii") for raw in held],
            "tap_broken": broken,
        }
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
        return raw if len(raw) <= 65536 else FALLBACK
    except BaseException:
        return FALLBACK


def capture(supervisor, case, expected, io, parts, *, deadline):
    try:
        parts.protocol.parse_case_args(["--case", case, "--expected", expected])
        tap = Tap(io, parts.protocol)
        report = supervisor.supervise(case, expected, tap, parts, deadline=deadline)
        return transport(supervisor.bounded_report(report), tap.lines, tap.broken)
    except BaseException:
        return FALLBACK
