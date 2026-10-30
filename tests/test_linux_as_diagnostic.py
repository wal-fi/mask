"""Pure harness contracts; importing these tests never creates Linux workloads."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "docs/poc/linux_as_probe.py"
SPEC = importlib.util.spec_from_file_location("linux_as_probe", SOURCE)
assert SPEC is not None and SPEC.loader is not None
PROBE: Any = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)
MIB = 1024 * 1024


def member(**updates: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "phase": "held",
        "pid": 2,
        "ppid": 1,
        "kind": "private",
        "limits": [32 * MIB, 32 * MIB],
        "vm": {"size": 28 * MIB, "peak": 28 * MIB, "rss": 20 * MIB, "threads": 1},
        "accepted_bytes": 12 * MIB,
        "touched_pages": 12 * MIB // 4096,
        "blocks": 3,
        "failure": "MEMORY",
        "errno": None,
    }
    result.update(updates)
    return result


def test_steps_need_not_hit_limit_exactly_to_observe_imposition():
    assert PROBE.classify_member(member(), limited=True, target=None) == "imposed"


@pytest.mark.parametrize("failure,number", [("MEMORY", None), ("ENOMEM", 12)])
def test_only_controlled_allocation_denial_is_evidence(failure, number):
    assert (
        PROBE.classify_member(member(failure=failure, errno=number), limited=True, target=None)
        == "imposed"
    )


@pytest.mark.parametrize("failure,number", [("OTHER", 13), ("ENOMEM", 13), ("NONE", None)])
def test_unrelated_errors_or_no_denial_are_not_imposition(failure, number):
    assert (
        PROBE.classify_member(member(failure=failure, errno=number), limited=True, target=None)
        != "imposed"
    )


def test_peak_above_limit_is_failure_even_when_allocation_was_denied():
    item = member(vm={"size": 28 * MIB, "peak": 32 * MIB + 4096, "rss": 1, "threads": 1})
    assert PROBE.classify_member(item, limited=True, target=None) == "fail"


def test_unchecked_or_raised_limit_is_not_accepted():
    assert (
        PROBE.classify_member(member(limits=[-1, -1]), limited=True, target=None) == "incompatible"
    )


def test_payloads_must_stay_retained_and_every_page_must_be_touched():
    with pytest.raises(PROBE.ProbeFault):
        PROBE.classify_member(member(touched_pages=1), limited=True, target=None)


def test_first_allocation_denial_is_not_accumulated_pressure():
    item = member(accepted_bytes=0, touched_pages=0, blocks=0)
    assert PROBE.classify_member(item, limited=True, target=None) == "inconclusive"


def test_control_and_baseline_require_complete_payload_without_denial():
    item = member(
        accepted_bytes=MIB,
        touched_pages=MIB // 4096,
        blocks=1,
        failure="NONE",
    )
    assert PROBE.classify_member(item, limited=True, target=MIB) == "normal"
    assert PROBE.classify_member(item, limited=True, target=40 * MIB) != "control_ok"
    item.update(limits=[-1, -1], accepted_bytes=40 * MIB, touched_pages=40 * MIB // 4096, blocks=10)
    assert PROBE.classify_member(item, limited=False, target=40 * MIB) == "control_ok"


@pytest.mark.parametrize("value", [True, -1, 40 * MIB + 1, "12"])
def test_invalid_counts_never_pass(value):
    with pytest.raises(PROBE.ProbeFault):
        PROBE.classify_member(member(accepted_bytes=value), limited=True, target=None)


def test_report_parser_refuses_extra_fields_and_duplicate_keys():
    raw = PROBE.encode_line(member())
    assert PROBE.decode_line(raw) == member()
    with pytest.raises(PROBE.ProbeFault):
        PROBE.decode_line(b'{"phase":"held","phase":"ready"}\n')
    with pytest.raises(PROBE.ProbeFault):
        PROBE.classify_member(member(extra_field="MUST_NOT_BE_ACCEPTED"), limited=True, target=None)


def test_protocol_lines_are_bounded_before_json_parsing():
    with pytest.raises(PROBE.ProbeFault):
        PROBE.decode_line(b"x" * (4096 + 1))
    with pytest.raises(PROBE.ProbeFault):
        PROBE.encode_line({"value": "x" * 4096})


def test_proc_status_uses_bytes_not_kib_and_requires_all_fields():
    assert PROBE.parse_status(
        "VmSize:\t1024 kB\nVmPeak:\t2048 kB\nVmRSS:\t512 kB\nThreads:\t1\n"
    ) == {
        "size": MIB,
        "peak": 2 * MIB,
        "rss": MIB // 2,
        "threads": 1,
    }
    with pytest.raises(PROBE.ProbeFault):
        PROBE.parse_status("VmSize: 123 bytes\n")


def test_selftest_is_pure_and_does_not_claim_total_memory_containment():
    result = PROBE.selftest()
    assert result["ok"] and result["total_memory_contained"] is False
    text = SOURCE.read_text(encoding="utf-8")
    assert "maskgw." not in text and "preexec_fn=" not in text
