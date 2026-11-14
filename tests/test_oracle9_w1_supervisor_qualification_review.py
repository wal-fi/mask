"""SQ3 regression oracles: the report state after a first control is the ACTUAL public state.

Root review SQ3 (2026-11-14) reproduced that the pinned backend ``_interrupt`` sets the
ordinary public ``state`` to ``HELD`` before propagating a control, while the qualifier
reported its last previously read state. These cases reuse the FROZEN fake backend of
``tests/test_oracle9_w1_supervisor_qualification.py`` (7905f229) unchanged: its
``fail_states`` transition sets the public state before the scripted raise, exactly like
``_interrupt``. Nothing in production is patched or duplicated.

The candidate is loaded through the frozen lazy loader as the FIRST statement of each
case, never at collection. Pure public metadata observation after the control is allowed;
any later SDK method call, cleanup or invented HELD is not. These are fake-only oracles,
not a native containment observation.

Author: Claude2 (session 51ea0d85), claude-opus-5-5/medium, from SQ3 with SQ1/SQ2.
Senff policy: AI-generated tests require human and security review before merge.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tests import test_oracle9_w1_supervisor_qualification as base

CONTROL_METHODS = ("setup", "start", "wait", "close")


@pytest.mark.parametrize("method", CONTROL_METHODS)
@pytest.mark.parametrize("ctl_type", [base.FalseCtl, base.BoomCtl])
def test_control_report_uses_the_actual_public_held_state(
    method: str, ctl_type: Callable[[list[str]], BaseException]
) -> None:
    q = base.qual_module()
    probes: list[str] = []
    ctl = ctl_type(probes)
    script = base.natural_script(raises={method: [ctl]}, fail_states={method: "HELD"})
    backend = base.make_backend(script)
    custody = q.QualCustody()
    script.custody = custody
    spec = base.raw_spec(q, q.QualCase.NATURAL, base.APP, base.DIR, 40)

    raised = base.control_of(lambda: q.qualify(spec, custody, backend=backend))

    assert raised is ctl and probes == []  # same object; truthiness never inspected
    assert ctl.__context__ is None and ctl.__cause__ is None
    assert script.calls[-1] == method and script.calls.count(method) == 1  # zero later calls
    owner = script.owners[0]
    assert owner.state == "HELD"  # the faithful fake transition really happened
    assert custody.first_control is ctl and custody.error is ctl
    assert custody.claimed is True and custody.backend is backend
    assert custody.request is script.requests[0] and custody.owner is owner
    assert len(script.owners) == len(script.requests) == 1
    report = custody.report
    assert report is not None
    base.assert_report(q, report)
    assert report.status is q.QualStatus.UNKNOWN and report.fault is q.QualFault.CONTROL
    assert report.owner_state is q.OwnerState.HELD  # actual public state, not a stale read
    expected_close = q.CloseResult.RAISED if method == "close" else q.CloseResult.NOT_ATTEMPTED
    assert report.close is expected_close  # no successful cleanup is invented
    assert report.close is not q.CloseResult.NONE_CLOSED and report.eof in (0, 1)
    assert script.calls.count("close") == (1 if method == "close" else 0)
    assert script.violations == []
