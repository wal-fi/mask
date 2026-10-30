"""HELD evidence capture/replay with fakes only: no lab factory, CLI or load."""

from __future__ import annotations

import copy
import hashlib
import json
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_linux_imports_probe import load
from tests.test_loaded_memory_host import reports
from tests.test_loaded_memory_supervisor import PARTS, FakeIO, S, line

E = load("loaded_memory_evidence")


class RecordingIO(FakeIO):
    def __init__(self, case: str) -> None:
        super().__init__(case)
        self.emitted: list[bytes] = []
        self.unapproved_attribute = "not-forwarded"

    def prepare(self, case: str, deadline: float) -> dict[str, Any]:
        value = super().prepare(case, deadline)
        value["inherited_as"] = [-1, -1]
        value["startup_cgroup"].update(procs=[1], pids_current=1)
        return value

    def final(self) -> dict[str, Any]:
        value = super().final()
        value["cgroup"].update(procs=[1], pids_current=1)
        return value

    def read(self) -> bytes | None:
        raw = super().read()
        if raw is not None and json.loads(raw).get("phase") == "held":
            self.emitted.append(raw)
        return raw


def expectation(case: str) -> str:
    return "-" if case == "control" else reports()[1]


def original(case: str = "private") -> tuple[bytes, tuple[bytes, ...]]:
    io = RecordingIO(case)
    report = S.supervise(case, expectation(case), io, PARTS, deadline=120.0)
    return S.bounded_report(report), tuple(io.emitted)


def wire(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"


@pytest.mark.parametrize("case", ["control", "private", "shared"])
def test_capture_keeps_exact_original_and_held_lines_with_replay(case):
    io = RecordingIO(case)
    raw = E.capture(case, expectation(case), io, PARTS, deadline=120.0)
    parsed = E.decode(raw, case, expectation(case))
    assert parsed["profile"] == "loaded-as128-held-v1"
    assert parsed["outcome"] == ("control_ok" if case == "control" else "imposed")
    assert [text.encode("ascii") for text in parsed["validated_held"]] == io.emitted
    source = parsed["original_report"].encode("ascii")
    assert parsed["original_bytes"] == len(source)
    assert parsed["original_sha256"] == hashlib.sha256(source).hexdigest()
    assert parsed["total_memory_contained"] is False
    assert io.trace[-2:] == ["cleanup", "final"] and io.closed


def test_encode_never_reserializes_original_even_with_unusual_whitespace():
    raw, held = original()
    raw = json.dumps(json.loads(raw), separators=(", ", ": ")).encode("ascii") + b"\n"
    parsed = E.decode(
        E.encode(raw, held, "private", expectation("private")), "private", expectation("private")
    )
    assert parsed["original_report"].encode("ascii") == raw


@pytest.mark.parametrize(
    "mode",
    [
        "missing",
        "extra",
        "wrong-kind",
        "false-refusal",
        "zero-held",
        "peak",
        "limits",
        "blocks",
        "errno",
    ],
)
def test_held_forgery_cannot_retain_positive(mode):
    source, held = original()
    value = json.loads(held[0])
    changed: tuple[bytes, ...]
    if mode == "missing":
        changed = ()
    elif mode == "extra":
        changed = held + held
    else:
        if mode == "wrong-kind":
            value["kind"] = "shared"
        elif mode == "false-refusal":
            value["failure"] = "NONE"
        elif mode == "zero-held":
            value.update(accepted_bytes=0, blocks=0, touched_pages=0)
        elif mode == "peak":
            value["vm"]["peak"] -= 1
        elif mode == "limits":
            value["limits"] = [-1, -1]
        elif mode == "blocks":
            value["blocks"] = True
        else:
            value["errno"] = 12
        changed = (line(value),)
    assert E.encode(source, changed, "private", expectation("private")) == E.FALLBACK


def test_control_allocator_order_is_not_inferred_or_repaired():
    source, held = original("control")
    assert E.encode(source, tuple(reversed(held)), "control", "-") == E.FALLBACK


@pytest.mark.parametrize(
    "mode",
    [
        "hash",
        "size",
        "bool-size",
        "case",
        "outcome",
        "claim",
        "profile",
        "extra",
        "original",
        "line",
    ],
)
def test_envelope_is_revalidated_not_trusted(mode):
    source, held = original()
    parsed = json.loads(E.encode(source, held, "private", expectation("private")))
    replacements: dict[str, Any] = {
        "hash": ("original_sha256", "a" * 64),
        "size": ("original_bytes", parsed["original_bytes"] + 1),
        "bool-size": ("original_bytes", True),
        "case": ("case", "shared"),
        "outcome": ("outcome", "control_ok"),
        "claim": ("total_memory_contained", 0),
        "profile": ("profile", "loaded-as128"),
        "extra": ("trusted", True),
        "original": ("original_report", parsed["original_report"].rstrip()),
        "line": ("validated_held", []),
    }
    key, value = replacements[mode]
    parsed[key] = value
    with pytest.raises(E.EvidenceFault, match=r"^EVIDENCE$") as error:
        E.decode(wire(parsed), "private", expectation("private"))
    assert error.value.__cause__ is None and error.value.__context__ is None


@pytest.mark.parametrize(
    "raw",
    [b"", b"{}", b"{}\n{}\n", b'{"a":NaN}\n', b'{"a":1,"a":2}\n', b"\xff\n", b"x" * 65537],
    ids=["empty", "partial", "two", "nan", "duplicate", "nonascii", "large"],
)
def test_raw_parser_closed_and_bounded(raw):
    with pytest.raises(E.EvidenceFault):
        E.decode(raw, "private", expectation("private"))


@pytest.mark.parametrize("case", ["control", "private", "shared"])
def test_legacy_positive_report_without_envelope_is_refused(case):
    source, _held = original(case)
    with pytest.raises(E.EvidenceFault):
        E.decode(source, case, expectation(case))


def test_decode_returns_independent_snapshots_without_mutating_inputs():
    source, held = original()
    unchanged = (source, held)
    encoded = E.encode(source, held, "private", expectation("private"))
    one = E.decode(encoded, "private", expectation("private"))
    one["validated_held"].clear()
    two = E.decode(encoded, "private", expectation("private"))
    assert len(two["validated_held"]) == 1 and (source, held) == unchanged


def test_tap_forwards_only_explicit_members_and_preserves_reads():
    io = RecordingIO("private")
    tap = E.Tap(io)
    io.prepare("private", 120.0)
    io.spawn("private")
    raw = tap.read()
    assert json.loads(raw)["phase"] == "ready" and tap.lines == ()
    io.pid = 9
    assert tap.pid == 9
    io.unapproved_attribute = "not-forwarded"
    with pytest.raises(AttributeError):
        _ = tap.unapproved_attribute


def test_negative_import_or_cleanup_never_publishes_partial_held():
    for failure in ("imports", "cleanup"):
        io = RecordingIO("private")
        if failure == "imports":
            io.import_error, io.rc = "MEMORY", 72
        else:
            io.clean = False
        parsed = E.decode(
            E.capture("private", expectation("private"), io, PARTS, deadline=120.0),
            "private",
            expectation("private"),
        )
        assert parsed["outcome"] not in ("control_ok", "imposed")
        if "validated_held" in parsed:
            assert parsed["validated_held"] == []
        assert io.closed


def test_held_appearing_during_imports_stays_negative(monkeypatch):
    _source, held = original()
    io = RecordingIO("private")
    send = io.send

    def wrong_position(command: bytes) -> None:
        send(command)
        if command == b"GO_IMPORTS\n":
            io.queue.insert(0, held[0])

    monkeypatch.setattr(io, "send", wrong_position)
    parsed = E.decode(
        E.capture("private", expectation("private"), io, PARTS, deadline=120.0),
        "private",
        expectation("private"),
    )
    assert parsed["outcome"] == "inconclusive" and parsed["validated_held"] == []
    assert io.commands == [b"GO_IMPORTS\n"] and io.trace[-2:] == ["cleanup", "final"]


def test_tap_failure_still_runs_supervisor_cleanup_without_later_send(monkeypatch):
    io = RecordingIO("private")
    seen = []

    def broken_read(_self: Any) -> None:
        seen.append(len(io.commands))
        raise E.EvidenceFault()

    monkeypatch.setattr(E.Tap, "read", broken_read)
    parsed = E.decode(
        E.capture("private", expectation("private"), io, PARTS, deadline=120.0),
        "private",
        expectation("private"),
    )
    assert parsed["outcome"] == "inconclusive"
    assert io.trace[-2:] == ["cleanup", "final"] and seen == [0] and io.commands == []


def test_replay_checks_original_observations_not_just_held():
    source, held = original()
    report = copy.deepcopy(json.loads(source))
    report["observations"][6]["vm"]["peak"] -= 1
    assert E.encode(wire(report), held, "private", expectation("private")) == E.FALLBACK


def test_exact_fallback_is_only_inconclusive_without_original_or_lines():
    parsed = E.decode(E.FALLBACK, "control", "-")
    assert parsed == {
        "profile": "loaded-as128-held-v1",
        "outcome": "inconclusive",
        "evidence_failure": "EVIDENCE",
        "total_memory_contained": False,
    }


@pytest.mark.parametrize("mode", ["line", "envelope"])
def test_caps_include_escaped_lines_and_original_overhead(mode):
    source, held = original()
    if mode == "line":
        held = (b"x" * 1025,)
    else:
        source = source[:-1] + b" " * (65000 - len(source)) + b"\n"
        assert len(source) == 65000
    assert E.encode(source, held, "private", expectation("private")) == E.FALLBACK


def test_third_candidate_breaks_tap_and_stays_terminal():
    _source, held = original()
    io = RecordingIO("private")
    io.queue = [held[0], held[0], held[0]]
    tap = E.Tap(io)
    assert tap.read() == tap.read() == held[0]
    with pytest.raises(E.EvidenceFault):
        tap.read()
    assert tap.broken and tap.lines == held + held
    with pytest.raises(E.EvidenceFault):
        tap.read()


def test_tap_retention_failure_still_cleans_up_and_stops_commands(monkeypatch):
    io = RecordingIO("private")
    init = E.Tap.__init__

    def exhausted(self: Any, supplied: Any) -> None:
        init(self, supplied)
        self._lines = (b"reserved", b"reserved")

    monkeypatch.setattr(E.Tap, "__init__", exhausted)
    raw = E.capture("private", expectation("private"), io, PARTS, deadline=120.0)
    assert raw == E.FALLBACK
    assert io.commands == [b"GO_IMPORTS\n", b"PRESSURE_PRIVATE\n"]
    assert io.trace[-2:] == ["cleanup", "final"]


@pytest.mark.parametrize(
    "mode", ["missing", "extra", "wrong-pid", "descriptors", "outer", "bool-rc"]
)
def test_replay_requires_full_original_lifecycle(mode):
    source, held = original("control")
    report = json.loads(source)
    if mode == "missing":
        report["observations"].pop()
    elif mode == "extra":
        report["observations"].append(copy.deepcopy(report["observations"][-1]))
    elif mode == "wrong-pid":
        report["observations"][6]["inventory"] = [1, 8]
    elif mode == "descriptors":
        report["observations"][-1]["fds"]["fds"].append(9)
    elif mode == "outer":
        report["final_cgroup"]["events"]["oom"] = 1
    else:
        report["member_returncode"] = False
    assert E.encode(wire(report), held, "control", "-") == E.FALLBACK


@pytest.mark.parametrize("samples", [1, 4])
def test_control_extra_release_samples_replayed_in_order(samples):
    source, held = original("control")
    report = json.loads(source)
    stalled = copy.deepcopy(report["observations"][7])
    stalled["vm"]["size"] = 140 << 20
    stalled["cgroup"]["stat"]["anon"] = 99 << 20
    report["observations"][7:7] = [copy.deepcopy(stalled) for _ in range(samples)]
    raw = E.encode(wire(report), held, "control", "-")
    assert E.decode(raw, "control", "-")["outcome"] == "control_ok"


def test_control_five_failed_release_samples_cannot_be_repaired():
    source, held = original("control")
    report = json.loads(source)
    stalled = copy.deepcopy(report["observations"][7])
    stalled["vm"]["size"] = 140 << 20
    report["observations"][7] = copy.deepcopy(stalled)
    report["observations"][7:7] = [copy.deepcopy(stalled) for _ in range(4)]
    assert E.HOST.validate_report(report, "control", "-") == report["inventory_digest"]
    assert E.encode(wire(report), held, "control", "-") == E.FALLBACK


def test_serialization_failure_returns_exact_fallback(monkeypatch):
    source, held = original()
    expected = expectation("private")

    def failed(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("not-in-the-error")

    monkeypatch.setattr(E, "json", SimpleNamespace(dumps=failed))
    assert E.encode(source, held, "private", expected) == E.FALLBACK


def test_unexpected_tap_decoder_failure_is_not_a_normal_nonheld_line(monkeypatch):
    io = RecordingIO("private")
    expected = expectation("private")

    def failed(_raw: Any) -> None:
        raise MemoryError("must-not-escape")

    monkeypatch.setattr(E.CORE, "decode_held", failed)
    raw = E.capture("private", expected, io, PARTS, deadline=120.0)
    assert raw == E.FALLBACK
    assert io.trace[-2:] == ["cleanup", "final"] and io.commands == []


@pytest.mark.parametrize("category", ["DEADLINE", "PROTOCOL"])
def test_delegated_read_fault_keeps_original_category_and_cleanup(monkeypatch, category):
    io = RecordingIO("private")
    expected = expectation("private")

    def failed() -> None:
        raise E.SUPERVISOR.SupervisorFault(category)

    monkeypatch.setattr(io, "read", failed)
    raw = E.capture("private", expected, io, PARTS, deadline=120.0)
    parsed = E.decode(raw, "private", expected)
    report = json.loads(parsed["original_report"])
    assert report["failure"] == {"stage": "ready", "category": category}
    assert parsed["validated_held"] == [] and parsed["outcome"] == "inconclusive"
    assert io.commands == [] and io.trace[-2:] == ["cleanup", "final"]


def test_delegated_read_exception_is_identical_and_does_not_break_tap(monkeypatch):
    io = RecordingIO("private")
    fault = E.SUPERVISOR.SupervisorFault("DEADLINE")

    def failed() -> None:
        raise fault

    monkeypatch.setattr(io, "read", failed)
    tap = E.Tap(io)
    with pytest.raises(E.SUPERVISOR.SupervisorFault) as error:
        tap.read()
    assert error.value is fault and tap.broken is False
