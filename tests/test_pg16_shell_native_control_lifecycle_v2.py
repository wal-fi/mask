"""Fake-only tests for the private lifecycle v2 composition, written first.

docs/poc/pg16_shell_native_control_lifecycle_v2.py does not exist yet: the
`v2` fixture loads it, so every test that needs it fails at setup until it
exists (feature-absent baseline). Legacy characterization and the synthetic
batch harness only use the consumed sources and already run.

The consumed runner (b4198fe1), caller (dfcc4ed6), adapter (eaebedd6),
backend (10c9058f), verifier (b3755d49) and helper (bb1f1984) are executed
unchanged into fresh namespaces; only their private seams are replaced
(backend _load_api/sys, caller write_new/_monotonic/_sleep). Real Owner and
NestedJobOwner run against a local fake kernel: historical totals separate
from active members and pipe data for READY. No real WinDLL, thread,
subprocess, sleep, entry, operational run or filesystem write. Artifacts
carry the old pins only as synthetic schema wiring, never as truthful
provenance of a v2 run. No broad arbitrary-tamper guarantee is tested.
"""

import ctypes
import os
import runpy
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "docs/poc/pg16_shell_native_control_lifecycle_v2.py"
RUNNER = REPO / "docs/poc/pg16_shell_native_control.py"
HOST = REPO / "docs/poc/pg16_shell_admission_host.py"
ADAPTER = REPO / "docs/poc/pg16_shell_native_control_win32.py"
VERIFIER = REPO / "docs/poc/pg16_shell_native_control_verify.py"
HELPER = REPO / "docs/poc/pg16_shell_tree_reconcile.py"
ADAPTER_TESTS = REPO / "tests/test_pg16_shell_native_control_win32.py"
NONCE = "0123456789abcdef0123456789abcdef"
ARGV0 = "C:\\fictitious\\lab\\venv\\Scripts\\python.exe"
NORMAL_LINE = b"MASKGW-NATIVE-CONTROL-NORMAL\r\n"
READY_LINE = b"MASKGW-NATIVE-CONTROL-READY\r\n"
CASES = ("NORMAL", "TERMINATE", "LAST_CLOSE")


class Signal(BaseException):
    """A fictitious control interruption."""


class SneakyStr(str):
    pass


def forbidden(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("native, process, thread, sleep or filesystem effect")


def lab_kernel_class(base: Any) -> Any:
    """The adapter tests' two-job fake plus: READY/NORMAL pipe data on resume,
    a historical total reported once the child is gone, ReadFile, and planned
    control interruptions by (call, count)."""

    def init(self: Any) -> None:
        base.__init__(self)
        self.history = None
        self.on_resume = None
        self.extra_on_resume = ()
        self.raise_at = {}

    def gate(self: Any, name: str, *handles: int) -> Any:
        count = self.counts.get(name, 0) + 1
        spec = base._gate(self, name, *handles)
        error = self.raise_at.get((name, count))
        if error is not None:
            raise error
        return spec

    def query(self: Any, *args: Any) -> int:
        result: int = base.QueryInformationJobObject(self, *args)
        if args[1] == 1 and result and self.history is not None and not self.alive:
            args[2]._obj.TotalProcesses = self.history
        return result

    def resume(self: Any, thread: int) -> int:
        result: int = base.ResumeThread(self, thread)
        if self.on_resume == "NORMAL":
            self.pipe.extend(NORMAL_LINE)
            self.alive = False
        elif self.on_resume == "READY":
            self.pipe.extend(READY_LINE)
        if self.extra_on_resume:
            self.extra["job"] = self.extra_on_resume
        return result

    def read(self: Any, *args: Any) -> int:
        handle, buffer, size, got, _overlapped = args
        self._gate("ReadFile", handle)
        data = bytes(self.pipe[:size])
        del self.pipe[:size]
        ctypes.memmove(buffer, data, len(data))
        got._obj.value = len(data)
        return 1

    return type(
        "LabKernel",
        (base,),
        {
            "__init__": init,
            "_gate": gate,
            "QueryInformationJobObject": query,
            "ResumeThread": resume,
            "ReadFile": read,
        },
    )


@pytest.fixture
def lab(monkeypatch: Any) -> SimpleNamespace:
    runner: dict[str, Any] = runpy.run_path(str(RUNNER))["run"].__globals__
    host: dict[str, Any] = runpy.run_path(str(HOST))["_supervise"].__globals__
    adapter: dict[str, Any] = runpy.run_path(str(ADAPTER))["definitions"].__globals__
    loaded = adapter["definitions"]()
    backend = loaded["backend"]
    adapter_tests = runpy.run_path(str(ADAPTER_TESTS))
    verifier = runpy.run_path(str(VERIFIER))
    helper = runpy.run_path(str(HELPER))["reconcile"]
    holder: list[Any] = []
    monkeypatch.setitem(
        backend, "_load_api", lambda: backend["_Api"](holder[-1], lambda: holder[-1].last)
    )
    monkeypatch.setitem(backend, "sys", adapter_tests["runtime"]())
    store: dict[str, bytes] = {}

    def write_new(path: Any, raw: bytes) -> None:
        key = str(path)
        assert key not in store
        store[key] = bytes(raw)

    ticks = [0.0]

    def monotonic() -> float:
        ticks[0] += 0.5
        return ticks[0]

    monkeypatch.setitem(host, "write_new", write_new)
    monkeypatch.setitem(host, "_monotonic", monotonic)
    monkeypatch.setitem(host, "_sleep", lambda _seconds: None)
    for owner, name in (
        (ctypes, "WinDLL"),
        (subprocess, "Popen"),
        (os, "system"),
        (threading.Thread, "start"),
        (time, "sleep"),
    ):
        monkeypatch.setattr(owner, name, forbidden)
    request = loaded["Request"](
        "C:\\launcher\\python.exe",
        '"C:\\launcher\\python.exe" -I -B -c "print(1)"',
        (("SystemRoot", "C:\\Windows"),),
        "C:\\work",
    )
    return SimpleNamespace(
        runner=runner,
        host=host,
        adapter=adapter,
        loaded=loaded,
        backend=backend,
        verifier=verifier,
        helper=helper,
        Kernel=lab_kernel_class(adapter_tests["Kernel"]),
        holder=holder,
        store=store,
        ticks=ticks,
        request=request,
        registry=runner["_LIVE"],
        RunError=runner["RunError"],
    )


@pytest.fixture
def v2() -> dict[str, Any]:
    return runpy.run_path(str(MODULE))


# -- synthetic case construction (mirrors the consumed _case/_run/_publish shapes) --


def owner_for(lab: SimpleNamespace, name: str) -> tuple[Any, Any]:
    kernel = lab.Kernel()
    kernel.on_resume = "NORMAL" if name == "NORMAL" else "READY"
    lab.holder.append(kernel)
    owner_class = lab.loaded["NestedJobOwner"] if name == "LAST_CLOSE" else lab.backend["Owner"]
    owner = owner_class(lab.request)
    lab.registry.append(owner)  # registered before setup, as the consumed _case does
    return owner, kernel


def limits(lab: SimpleNamespace) -> dict[str, Any]:
    host, runner = lab.host, lab.runner
    return {
        "deadline_seconds": host["DEADLINE_SECONDS"],
        "cleanup_seconds": host["CLEANUP_SECONDS"],
        "max_turns": host["MAX_TURNS"],
        "cleanup_turns": host["CLEANUP_TURNS"],
        "ready_seconds": runner["READY_SECONDS"],
        "ready_turns": runner["READY_TURNS"],
        "retain_bytes": host["RETAIN_BYTES"],
        "audit_limit": lab.adapter["AUDIT_LIMIT"],
        "active_process_limit": lab.backend["ACTIVE_PROCESS_LIMIT"],
    }


def pins(lab: SimpleNamespace) -> dict[str, Any]:
    """Old pins: synthetic schema wiring only, not provenance of a v2 run."""
    return {
        "host_sha256": lab.runner["HOST"][1],
        "adapter_sha256": lab.runner["ADAPTER"][1],
        "backend_sha256": lab.runner["BACKEND_SHA"],
        "launcher_sha256": lab.host["PYTHON_SHA"],
    }


def case_for(
    lab: SimpleNamespace, name: str, number: int, artifacts: dict[str, bytes]
) -> dict[str, Any]:
    clock = lab.host["_Clock"]()
    start = clock.now()
    case: dict[str, Any] = {
        "name": name,
        "directory": Path("C:/fictitious/private") / ("case-" + str(number)),
        "prefix": "case-" + str(number) + "/",
        "host": lab.host,
        "error": lab.loaded["Win32Error"],
        "read_limit": lab.backend["MAX_READ"],
        "audit_limit": lab.adapter["AUDIT_LIMIT"],
        "facts": lab.host["_new_facts"](),
        "ready": False,
        "ready_turns": 0,
        "snapshot": None,
        "inner_closed": False,
        "contained": False,
        "recorded": False,
        "seconds": None,
        "clock": clock,
        "start": start,
        "since": start,
        "lifecycle_reserved": False,
        "reconcile_reserved": False,
    }
    literal = dict(lab.runner["CASES"])[name]
    invocation = {
        "kind": "MASKGW_PG16_NATIVE_CONTROL_INVOCATION_V1",
        "nonce": NONCE,
        **pins(lab),
        "limits": limits(lab),
        "case": name,
        "number": number,
        "argv": [ARGV0, "-I", "-B", "-c", literal],
        "environment_names": list(lab.host["ENVIRONMENT_NAMES"]),
    }
    raw = lab.host["encoded"](invocation) + b"\n"
    lab.runner["_persist"](lab.host, case, artifacts, (("invocation.json", raw),))
    return case


def published(
    lab: SimpleNamespace, records: list[dict[str, Any]], artifacts: dict[str, bytes]
) -> tuple[bytes, bytes, dict[str, bytes]]:
    host = lab.host
    approved = len(records) == 3 and all(item["outcome"] == "APPROVED" for item in records)
    summary = {
        "kind": "MASKGW_PG16_NATIVE_CONTROL_SUMMARY_V1",
        "nonce": NONCE,
        "outcome": "APPROVED" if approved else "REJECTED",
        "scope": "BENIGN_CONTROL_ONLY",
        "admission_3s": "NOT_MEASURED",
        "cases": records + [lab.runner["_not_run"](name) for name in CASES[len(records) :]],
        **pins(lab),
    }
    summary_raw = host["encoded"](summary) + b"\n"
    files = [
        {"name": name, "bytes": len(raw), "sha256": host["sha"](raw)}
        for name, raw in sorted(artifacts.items())
    ]
    transport = {
        "kind": "MASKGW_PG16_NATIVE_CONTROL_TRANSPORT_V1",
        "nonce": NONCE,
        "outcome": summary["outcome"],
        "summary": {
            "name": "summary.json",
            "bytes": len(summary_raw),
            "sha256": host["sha"](summary_raw),
        },
        "private": files,
    }
    return summary_raw, host["encoded"](transport) + b"\n", dict(artifacts)


def verified(lab: SimpleNamespace, records: list[Any], artifacts: dict[str, bytes]) -> Any:
    summary_raw, transport_raw, files = published(lab, records, artifacts)
    expected = lab.verifier["Expected"](nonce=NONCE, argv0=ARGV0)
    return lab.verifier["verify"](expected, summary_raw, transport_raw, files)


def legacy_driver(lab: SimpleNamespace) -> Any:
    def drive(owner: Any, case: dict[str, Any]) -> None:
        lab.runner["_lifecycle"](owner, case)

    return drive


def v2_driver(lab: SimpleNamespace, v2: dict[str, Any], reconcile: Any = None) -> Any:
    def drive(owner: Any, case: dict[str, Any]) -> None:
        ctx = v2["context"](owner, case, lab.runner, lab.helper if reconcile is None else reconcile)
        v2["lifecycle"](ctx)

    return drive


Plan = tuple[int, str]  # (case number, case name)


def run_case(
    lab: SimpleNamespace,
    plan: Plan,
    artifacts: dict[str, bytes],
    drive: Any,
    prepare: Any = None,
) -> SimpleNamespace:
    number, name = plan
    owner, kernel = owner_for(lab, name)
    if prepare is not None:
        prepare(kernel)
    case = case_for(lab, name, number, artifacts)
    drive(owner, case)
    record = lab.runner["_finish"](owner, case, artifacts)
    return SimpleNamespace(owner=owner, kernel=kernel, case=case, record=record)


def registered(lab: SimpleNamespace, owner: Any) -> bool:
    return any(item is owner for item in lab.registry)


def held_written(lab: SimpleNamespace, case: dict[str, Any]) -> bool:
    return str(case["directory"] / "held.json") in lab.store


def tree(kernel: Any) -> None:
    kernel.history = 3


# -- harness and legacy characterization (consumed sources only) --


def test_the_synthetic_legacy_batch_verifies_approved(lab: SimpleNamespace) -> None:
    artifacts: dict[str, bytes] = {}
    records = [
        run_case(lab, plan, artifacts, legacy_driver(lab)).record for plan in enumerate(CASES, 1)
    ]
    assert [item["outcome"] for item in records] == ["APPROVED"] * 3
    assert verified(lab, records, artifacts) == ("VERIFIED_APPROVED", "OK")
    assert list(lab.registry) == []


@pytest.mark.parametrize("name", ["NORMAL", "LAST_CLOSE"])
def test_legacy_lifecycle_parks_a_quiet_over_counted_tree(lab: SimpleNamespace, name: str) -> None:
    owner, kernel = owner_for(lab, name)
    tree(kernel)
    case = case_for(lab, name, 1, {})
    with pytest.raises(lab.RunError) as caught:
        lab.runner["_lifecycle"](owner, case)
    assert caught.value.args == ("CONTROL_HELD",)
    assert case["facts"]["held"] == "CLEANUP" and case["facts"]["reason"] == "TREE_UNPROVEN"
    assert registered(lab, owner) and held_written(lab, case)


# -- parity of the three cases and the early failures --


def snapshot_invalid(kernel: Any) -> None:
    kernel.extra_on_resume = (0x9001, 0x9002)


def launch_failed(kernel: Any) -> None:
    kernel.plan["CreateProcessW"] = ("false", 2)


def setup_failed(kernel: Any) -> None:
    kernel.plan["CreateJobObjectW"] = ("false", 5)


def ready_missing(kernel: Any) -> None:
    kernel.on_resume = None


PARITY: list[tuple[str, Any]] = [
    ("NORMAL", None),
    ("TERMINATE", None),
    ("LAST_CLOSE", None),
    ("NORMAL", setup_failed),
    ("TERMINATE", launch_failed),
    ("TERMINATE", ready_missing),
    ("LAST_CLOSE", snapshot_invalid),
]


def observed(
    lab: SimpleNamespace, number: int, name: str, drive: Any, prepare: Any
) -> dict[str, Any]:
    """Everything a caller can see; a legacy CONTROL_HELD is an outcome too."""
    lab.ticks[0] = 0.0
    owner, kernel = owner_for(lab, name)
    if prepare is not None:
        prepare(kernel)
    case = case_for(lab, name, number, {})
    error: Any = None
    record: Any = None
    try:
        drive(owner, case)
    except lab.RunError as caught:
        error = caught.args
    if error is None:
        record = lab.runner["_finish"](owner, case, {})
    return {
        "error": error,
        "record": record,
        "facts": {key: value for key, value in case["facts"].items() if key != "retained"},
        "retained": bytes(case["facts"]["retained"]),
        "state": owner.state,
        "calls": list(kernel.calls),
        "closed": list(kernel.closed),
        "registered": registered(lab, owner),
        "held": held_written(lab, case),
    }


@pytest.mark.parametrize(("name", "prepare"), PARITY)
def test_v2_matches_the_legacy_lifecycle(
    lab: SimpleNamespace, v2: dict[str, Any], name: str, prepare: Any
) -> None:
    legacy = observed(lab, 1, name, legacy_driver(lab), prepare)
    composed = observed(lab, 2, name, v2_driver(lab, v2), prepare)
    assert composed == legacy
    if prepare is None:
        assert composed["error"] is None and composed["state"] == "CLOSED"
        assert composed["registered"] is False


def test_the_budget_refusal_matches_the_legacy_lifecycle(
    lab: SimpleNamespace, v2: dict[str, Any]
) -> None:
    outcomes: list[tuple[Any, ...]] = []
    for number, drive in enumerate((legacy_driver(lab), v2_driver(lab, v2)), 1):
        lab.ticks[0] = 0.0
        owner, kernel = owner_for(lab, "NORMAL")
        case = case_for(lab, "NORMAL", number, {})
        case["start"] = case["since"] = -1000.0
        drive(owner, case)
        outcomes.append((case["facts"]["reason"], owner.state, list(kernel.calls)))
        assert not registered(lab, owner)
    assert outcomes[0] == outcomes[1] and outcomes[0][0] == "DEADLINE"


# -- TREE quiet: closed once, rejected, verified --


def test_a_quiet_normal_tree_is_closed_once_and_verified_rejected(
    lab: SimpleNamespace, v2: dict[str, Any]
) -> None:
    parked = observed(lab, 9, "NORMAL", legacy_driver(lab), tree)["facts"]
    lab.ticks[0] = 0.0
    artifacts: dict[str, bytes] = {}
    result = run_case(lab, (1, "NORMAL"), artifacts, v2_driver(lab, v2), tree)
    facts = result.case["facts"]
    assert result.owner.state == "CLOSED" and not registered(lab, result.owner)
    assert result.owner.ledger == {} and result.kernel.double_closed == []
    assert facts["held"] is None and facts["reason"] == "TREE_UNPROVEN"
    # Nothing fabricated: exactly the parked legacy facts except the held label.
    assert {key: value for key, value in facts.items() if key not in ("held", "retained")} == {
        key: value for key, value in parked.items() if key != "held"
    }
    assert result.case["reconcile_reserved"] is True and result.case["lifecycle_reserved"] is True
    assert result.record["outcome"] == "REJECTED"
    assert result.record["rejection"] == "TREE_UNPROVEN"
    assert not held_written(lab, result.case)
    assert verified(lab, [result.record], artifacts) == ("VERIFIED_REJECTED", "OK")


def test_a_quiet_last_close_tree_keeps_the_exact_precedence(
    lab: SimpleNamespace, v2: dict[str, Any]
) -> None:
    artifacts: dict[str, bytes] = {}
    records = [
        run_case(lab, (1, "NORMAL"), artifacts, v2_driver(lab, v2)).record,
        run_case(lab, (2, "TERMINATE"), artifacts, v2_driver(lab, v2)).record,
    ]
    last = run_case(lab, (3, "LAST_CLOSE"), artifacts, v2_driver(lab, v2), tree)
    records.append(last.record)
    assert last.owner.state == "CLOSED" and not registered(lab, last.owner)
    assert last.kernel.double_closed == []
    assert last.record["outcome"] == "REJECTED" and last.record["audit_integral"] is True
    assert last.record["rejection"] == "FAILED_LAST_CLOSE"  # before the TREE reason
    assert last.record["inner_closed"] is True and last.record["terminate_calls"] >= 1
    assert verified(lab, records, artifacts) == ("VERIFIED_REJECTED", "OK")


def test_a_benign_second_registry_entry_is_preserved(
    lab: SimpleNamespace, v2: dict[str, Any]
) -> None:
    other = object()
    lab.registry.append(other)
    result = run_case(lab, (1, "NORMAL"), {}, v2_driver(lab, v2), tree)
    assert not registered(lab, result.owner)
    assert len(lab.registry) == 1 and lab.registry[0] is other


# -- uncertain TREE and ineligible CLEANUP: legitimate legacy retention --


def spying(lab: SimpleNamespace, before: Any = None) -> tuple[Any, list[int]]:
    calls: list[int] = []

    def reconcile(owner: Any, facts: Any) -> Any:
        calls.append(1)
        if before is not None:
            before(owner)
        return lab.helper(owner, facts)

    return reconcile, calls


def legacy_held(
    lab: SimpleNamespace, v2: dict[str, Any], name: str, reconcile: Any, prepare: Any
) -> SimpleNamespace:
    owner, kernel = owner_for(lab, name)
    prepare(kernel)
    case = case_for(lab, name, 1, {})
    ctx = v2["context"](owner, case, lab.runner, reconcile)
    with pytest.raises(lab.RunError) as caught:
        v2["lifecycle"](ctx)
    return SimpleNamespace(owner=owner, kernel=kernel, case=case, ctx=ctx, error=caught.value)


@pytest.mark.parametrize("fault", ["member", "close"])
def test_an_uncertain_tree_is_retained_by_the_legacy_path(
    lab: SimpleNamespace, v2: dict[str, Any], fault: str
) -> None:
    kernels: list[Any] = []

    def disturb(_owner: Any) -> None:
        kernel = kernels[0]
        if fault == "member":
            kernel.extra["job"] = (0x9001,)
        else:
            kernel.plan["CloseHandle"] = ("false", 6)

    reconcile, calls = spying(lab, disturb)

    def prepare(kernel: Any) -> None:
        kernels.append(kernel)
        tree(kernel)

    result = legacy_held(lab, v2, "NORMAL", reconcile, prepare)
    assert result.error is not result.ctx.held_error
    assert result.error.args == ("CONTROL_HELD",)
    assert calls == [1] and result.owner.state != "CLOSED"
    assert registered(lab, result.owner) and result.owner.ledger != {}
    assert result.kernel.double_closed == [] and held_written(lab, result.case)


def test_terminate_with_deadline_and_tree_stays_outside_the_helper(
    lab: SimpleNamespace, v2: dict[str, Any]
) -> None:
    reconcile, calls = spying(lab)
    result = legacy_held(lab, v2, "TERMINATE", reconcile, tree)
    assert result.case["facts"]["reason"] == "DEADLINE"
    assert calls == [] and registered(lab, result.owner) and held_written(lab, result.case)
    assert result.case["reconcile_reserved"] is False


# -- integrity refusals: the preconstructed original error, no legacy cleanup --


def integrity(lab: SimpleNamespace, v2: dict[str, Any], reconcile: Any) -> SimpleNamespace:
    owner, kernel = owner_for(lab, "NORMAL")
    tree(kernel)
    case = case_for(lab, "NORMAL", 1, {})
    ledger = owner.ledger
    ctx = v2["context"](owner, case, lab.runner, reconcile)
    with pytest.raises(BaseException) as caught:
        v2["lifecycle"](ctx)
    assert caught.value is ctx.held_error
    assert type(caught.value) is lab.RunError and caught.value.args == ("CONTROL_HELD",)
    assert registered(lab, owner) and not held_written(lab, case)
    assert kernel.double_closed == []
    return SimpleNamespace(owner=owner, kernel=kernel, case=case, ctx=ctx, ledger=ledger)


def forged_verdict(_owner: Any, _facts: Any) -> Any:
    return "REJECTED_CLOSED"


def sneaky_verdict(_owner: Any, _facts: Any) -> Any:
    return SneakyStr("REJECTED_CLOSED")


def forged_closed(owner: Any, _facts: Any) -> Any:
    owner.state = "CLOSED"
    return "REJECTED_CLOSED"


def forged_closed_retain(owner: Any, _facts: Any) -> Any:
    owner.state = "CLOSED"
    return "RETAIN"


def forged_closed_not_applicable(owner: Any, _facts: Any) -> Any:
    owner.state = "CLOSED"
    return "NOT_APPLICABLE"


def replaced_ledger(owner: Any, _facts: Any) -> Any:
    owner.ledger = {}
    owner.state = "CLOSED"
    return "REJECTED_CLOSED"


FORGED = [
    forged_verdict,
    sneaky_verdict,
    forged_closed,
    forged_closed_retain,
    forged_closed_not_applicable,
    replaced_ledger,
]


@pytest.mark.parametrize("reconcile", FORGED)
def test_forged_results_are_refused_without_release(
    lab: SimpleNamespace, v2: dict[str, Any], reconcile: Any
) -> None:
    result = integrity(lab, v2, reconcile)
    # Nothing was closed: the original ledger still holds every handle.
    assert result.ledger != {}
    assert (result.owner.ledger is result.ledger) is (reconcile is not replaced_ledger)


def drifting(lab: SimpleNamespace, drift: Any, close: bool = True) -> Any:
    def reconcile(owner: Any, facts: Any) -> Any:
        drift(owner, facts)
        return lab.helper(owner, facts) if close else "RETAIN"

    return reconcile


def test_mutated_facts_after_a_real_close_are_refused(
    lab: SimpleNamespace, v2: dict[str, Any]
) -> None:
    def drift(_owner: Any, facts: Any) -> None:
        facts["exit_code"] = 0

    result = integrity(lab, v2, drifting(lab, drift))
    assert result.owner.state == "CLOSED"  # closed but never released
    assert result.case["facts"]["held"] == "CLEANUP"


def test_replaced_case_facts_are_refused(lab: SimpleNamespace, v2: dict[str, Any]) -> None:
    holder: list[Any] = []

    def drift(_owner: Any, _facts: Any) -> None:
        holder[0]["facts"] = dict(holder[0]["facts"])

    reconcile = drifting(lab, drift)
    owner, kernel = owner_for(lab, "NORMAL")
    tree(kernel)
    case = case_for(lab, "NORMAL", 1, {})
    holder.append(case)
    ctx = v2["context"](owner, case, lab.runner, reconcile)
    with pytest.raises(BaseException) as caught:
        v2["lifecycle"](ctx)
    assert caught.value is ctx.held_error and registered(lab, owner)
    assert not held_written(lab, case)


def test_a_replaced_registry_is_never_written(lab: SimpleNamespace, v2: dict[str, Any]) -> None:
    replacement: list[Any] = []

    def drift(_owner: Any, _facts: Any) -> None:
        lab.runner["_LIVE"] = replacement

    integrity(lab, v2, drifting(lab, drift))
    assert replacement == []


def test_a_replaced_legacy_hook_is_never_called(lab: SimpleNamespace, v2: dict[str, Any]) -> None:
    spy: list[int] = []

    def drift(_owner: Any, _facts: Any) -> None:
        lab.runner["_held"] = lambda *_args: spy.append(1)

    integrity(lab, v2, drifting(lab, drift, close=False))
    assert spy == []


def test_a_replaced_host_hook_is_refused(lab: SimpleNamespace, v2: dict[str, Any]) -> None:
    def drift(_owner: Any, _facts: Any) -> None:
        lab.host["_attempt"] = forbidden

    integrity(lab, v2, drifting(lab, drift, close=False))


def test_a_replaced_owner_close_method_is_refused(lab: SimpleNamespace, v2: dict[str, Any]) -> None:
    calls: list[int] = []

    def drift(owner: Any, _facts: Any) -> None:
        owner.close = lambda: calls.append(1)

    integrity(lab, v2, drifting(lab, drift, close=False))
    assert calls == []


def test_codes_and_run_error_drift_use_the_preconstructed_error(
    lab: SimpleNamespace, v2: dict[str, Any]
) -> None:
    def drift(_owner: Any, _facts: Any) -> None:
        lab.runner["RunError"] = type("ForeignError", (Exception,), {})
        lab.runner["CODES"] = frozenset()
        lab.holder[-1].extra["job"] = (0x9001,)  # the close will not prove quiescence

    result = integrity(lab, v2, drifting(lab, drift))
    assert result.owner.state != "CLOSED"


# -- flags, one lifecycle and one reconcile --


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("lifecycle_reserved", None),
        ("lifecycle_reserved", True),
        ("lifecycle_reserved", 0),
        ("reconcile_reserved", None),
        ("reconcile_reserved", True),
        ("reconcile_reserved", "False"),
    ],
)
def test_malformed_or_reserved_flags_refuse_before_effects(
    lab: SimpleNamespace, v2: dict[str, Any], key: str, value: Any
) -> None:
    owner, kernel = owner_for(lab, "NORMAL")
    case = case_for(lab, "NORMAL", 1, {})
    if value is None:
        del case[key]
    else:
        case[key] = value
    with pytest.raises(lab.RunError) as caught:
        v2["context"](owner, case, lab.runner, lab.helper)
    assert caught.value.args == ("CONTROL_HELD",)
    assert kernel.calls == [] and owner.state == "NEW" and registered(lab, owner)


def test_an_unregistered_owner_refuses_before_effects(
    lab: SimpleNamespace, v2: dict[str, Any]
) -> None:
    owner, kernel = owner_for(lab, "NORMAL")
    lab.registry.remove(owner)
    case = case_for(lab, "NORMAL", 1, {})
    with pytest.raises(lab.RunError):
        v2["context"](owner, case, lab.runner, lab.helper)
    assert kernel.calls == [] and owner.state == "NEW"


def test_the_lifecycle_runs_once_per_case(lab: SimpleNamespace, v2: dict[str, Any]) -> None:
    owner, kernel = owner_for(lab, "NORMAL")
    case = case_for(lab, "NORMAL", 1, {})
    ctx = v2["context"](owner, case, lab.runner, lab.helper)
    v2["lifecycle"](ctx)
    calls = list(kernel.calls)
    with pytest.raises(BaseException) as caught:
        v2["lifecycle"](ctx)
    assert caught.value is ctx.held_error and kernel.calls == calls
    second, _kernel = owner_for(lab, "NORMAL")
    with pytest.raises(lab.RunError):
        v2["context"](second, case, lab.runner, lab.helper)


def test_reconcile_is_called_at_most_once(lab: SimpleNamespace, v2: dict[str, Any]) -> None:
    reconcile, calls = spying(lab)
    result = run_case(lab, (1, "NORMAL"), {}, v2_driver(lab, v2, reconcile), tree)
    assert calls == [1] and result.owner.state == "CLOSED"
    assert result.kernel.calls.count("CloseHandle") == len(set(result.kernel.closed))


# -- control interruptions keep the original identity and ownership --


@pytest.mark.parametrize("moment", ["setup", "close", "after-close"])
def test_a_control_interruption_propagates_with_ownership(
    lab: SimpleNamespace, v2: dict[str, Any], moment: str
) -> None:
    signal = Signal()
    owner, kernel = owner_for(lab, "NORMAL")
    tree(kernel)
    if moment == "setup":
        kernel.raise_at[("CreateJobObjectW", 1)] = signal

    def reconcile(target: Any, facts: Any) -> Any:
        if moment == "close":
            count = kernel.counts.get("CloseHandle", 0)
            kernel.raise_at[("CloseHandle", count + 1)] = signal
        verdict = lab.helper(target, facts)
        if moment == "after-close":
            raise signal
        return verdict

    case = case_for(lab, "NORMAL", 1, {})
    ctx = v2["context"](owner, case, lab.runner, reconcile)
    with pytest.raises(Signal) as caught:
        v2["lifecycle"](ctx)
    assert caught.value is signal
    assert registered(lab, owner) and ctx.held_error is not signal
    assert kernel.double_closed == []


# -- ledger field identity: a replaced ledger is drift at every boundary --


def test_a_ledger_replaced_before_the_lifecycle_is_refused(
    lab: SimpleNamespace, v2: dict[str, Any]
) -> None:
    owner, kernel = owner_for(lab, "NORMAL")
    case = case_for(lab, "NORMAL", 1, {})
    ctx = v2["context"](owner, case, lab.runner, lab.helper)
    original = ctx.ledger
    foreign: dict[str, Any] = {}
    owner.ledger = foreign
    with pytest.raises(BaseException) as caught:
        v2["lifecycle"](ctx)
    assert caught.value is ctx.held_error
    assert owner.state == "NEW" and registered(lab, owner)
    assert ctx.ledger is original and original is not foreign
    assert owner.ledger is foreign and foreign == {}
    assert kernel.calls == [] and not held_written(lab, case)


def test_a_ledger_replaced_during_reconcile_is_refused(
    lab: SimpleNamespace, v2: dict[str, Any]
) -> None:
    owner, kernel = owner_for(lab, "NORMAL")
    tree(kernel)
    case = case_for(lab, "NORMAL", 1, {})
    replacement: dict[str, Any] = {}
    seen: list[Any] = []

    def reconcile(target: Any, _facts: Any) -> Any:
        seen.append((dict(target.ledger), list(kernel.calls)))
        target.ledger = replacement
        return "RETAIN"

    ctx = v2["context"](owner, case, lab.runner, reconcile)
    original = ctx.ledger
    with pytest.raises(BaseException) as caught:
        v2["lifecycle"](ctx)
    assert caught.value is ctx.held_error
    assert len(seen) == 1
    contents, calls = seen[0]
    assert ctx.ledger is original and original is not replacement
    assert original == contents and original != {}
    assert owner.ledger is replacement and replacement == {}
    assert kernel.calls == calls  # nothing native after the drift
    assert registered(lab, owner) and not held_written(lab, case)
    assert case["recorded"] is False and case["contained"] is False  # no legacy hold
