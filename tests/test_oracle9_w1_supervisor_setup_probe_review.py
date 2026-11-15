"""S2 regression oracles for the C0 entry ``main`` (root source review, 2026-11-14).

Root reproduced S2: a zero-byte ``stdout.buffer.write`` was treated as a delivered refusal
(exit 2, then flush) instead of an IO failure (exit 3). These cases exercise ONLY the safe
pre-acquisition path of the public ``main``: a definitely invalid RELATIVE application is
refused before any qualifier, backend, Request or Owner is touched, so no native effect,
loader or park is reachable. Standard ``contextlib`` stdout/stderr redirection supplies a
small concrete fake with the public ``buffer.write``/``buffer.flush`` surface; nothing in
production is patched or replaced.

The candidate is loaded through the frozen lazy loader of
``tests/test_oracle9_w1_supervisor_setup_probe.py`` as the FIRST statement of each case.
S1 (unregistered qualifier definitions) is already covered by two frozen failing tests.

Author: Claude2 (session 51ea0d85), claude-opus-5-5/medium, from the C0 source review.
Senff policy: AI-generated tests require human and security review before merge.
"""

from __future__ import annotations

import contextlib
import io
from collections.abc import Callable
from typing import Any

import pytest

from tests import test_oracle9_w1_supervisor_qualification as qbase
from tests import test_oracle9_w1_supervisor_setup_probe as c0

REFUSED = ("REFUSED", "INPUT", "EMPTY")
RELATIVE_ARGV = ["relative-python.exe", qbase.DIR]  # refused before any acquisition
_VALID = object()  # sentinel: write returns exactly len(data)


class LoudError(Exception):
    """Ordinary error whose stringification or truthiness is recorded if inspected."""

    def __init__(self, probes: list[str]) -> None:
        super().__init__()
        self.probes = probes

    def __str__(self) -> str:
        self.probes.append("str")
        return qbase.CANARY

    def __repr__(self) -> str:
        self.probes.append("repr")
        return qbase.CANARY

    def __bool__(self) -> bool:
        self.probes.append("bool")
        return True


class FakeBuffer:
    """Public binary buffer surface: records every write/flush; scripted result/failure."""

    def __init__(
        self,
        write_result: object = _VALID,
        write_raises: BaseException | None = None,
        flush_raises: BaseException | None = None,
    ) -> None:
        self.write_result = write_result
        self.write_raises = write_raises
        self.flush_raises = flush_raises
        self.writes: list[bytes] = []
        self.flushes = 0

    def write(self, data: object) -> object:
        assert type(data) is bytes  # the exact frame bytes, never text
        self.writes.append(data)
        if self.write_raises is not None:
            raise self.write_raises
        if self.write_result is _VALID:
            return len(data)
        return self.write_result

    def flush(self) -> None:
        self.flushes += 1
        if self.flush_raises is not None:
            raise self.flush_raises


class FakeStdout(io.StringIO):
    """Text stdout whose binary ``buffer`` property is the concrete fake above."""

    def __init__(self, fake: FakeBuffer) -> None:
        super().__init__()
        self.fake = fake

    @property
    def buffer(self) -> Any:
        return self.fake


def run_main(buffer: FakeBuffer) -> tuple[int, str, str]:
    """Calls the public ``main`` with redirected stdout/stderr; returns code and texts."""
    p = c0.probe_module()
    stdout = FakeStdout(buffer)
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = p.main(list(RELATIVE_ARGV))
    assert type(code) is int
    return code, stdout.getvalue(), stderr.getvalue()


def expected_frame() -> bytes:
    frame = c0.probe_module().encode_c0(REFUSED)
    assert type(frame) is bytes
    return frame


# ---------------------------------------------------------------- independent fake sanity


def test_sanity_fake_buffer_records_writes_results_and_flushes() -> None:
    buffer = FakeBuffer()
    assert buffer.write(b"abc") == 3 and buffer.writes == [b"abc"]
    buffer.flush()
    assert buffer.flushes == 1
    short = FakeBuffer(write_result=1)
    assert short.write(b"abc") == 1
    failing = FakeBuffer(flush_raises=ValueError("x"))
    with pytest.raises(ValueError):
        failing.flush()
    assert failing.flushes == 1
    stdout = FakeStdout(buffer)
    assert stdout.buffer is buffer and stdout.getvalue() == ""


# ---------------------------------------------------------------- valid delivery


def test_refusal_with_full_exact_write_then_flush_exits_2() -> None:
    frame = expected_frame()
    buffer = FakeBuffer()
    code, text, err = run_main(buffer)
    assert code == 2
    assert buffer.writes == [frame] and buffer.flushes == 1
    assert text == "" and err == ""


# ---------------------------------------------------------------- invalid write results


@pytest.mark.parametrize(
    "kind", ["zero", "short", "none", "bool-true", "negative", "oversize", "opaque"]
)
def test_invalid_write_result_is_io_failure_exit_3_without_retry_or_flush(kind: str) -> None:
    frame = expected_frame()
    probes: list[str] = []
    result: object = {
        "zero": 0,
        "short": len(frame) - 1,
        "none": None,
        "bool-true": True,
        "negative": -1,
        "oversize": len(frame) + 1,
        "opaque": qbase.Opaque(probes),
    }[kind]
    buffer = FakeBuffer(write_result=result)
    code, text, err = run_main(buffer)
    assert code == 3  # never acknowledged as a delivered refusal
    assert buffer.writes == [frame]  # exactly one attempt, the exact frame, never retried
    assert buffer.flushes == 0  # no flush after an invalid write result
    assert probes == [] and text == "" and err == ""


# ---------------------------------------------------------------- write/flush failures


FailureFactory = Callable[[list[str]], BaseException]
FAILURES: dict[str, FailureFactory] = {
    "ordinary": LoudError,
    "false-control": qbase.FalseCtl,
    "boom-control": qbase.BoomCtl,
}


@pytest.mark.parametrize("phase", ["write", "flush"])
@pytest.mark.parametrize("kind", sorted(FAILURES))
def test_write_or_flush_failure_is_exit_3_once_without_inspection(phase: str, kind: str) -> None:
    frame = expected_frame()
    probes: list[str] = []
    failure = FAILURES[kind](probes)
    if phase == "write":
        buffer = FakeBuffer(write_raises=failure)
    else:
        buffer = FakeBuffer(flush_raises=failure)
    code, text, err = run_main(buffer)
    assert code == 3
    assert buffer.writes == [frame]  # one attempt only, never retried
    assert buffer.flushes == (1 if phase == "flush" else 0)  # flush only after a valid write
    assert probes == []  # never stringified, repr'd or truth-tested
    assert failure.__context__ is None and failure.__cause__ is None
    assert text == "" and err == ""  # no raw traceback or text on stderr
