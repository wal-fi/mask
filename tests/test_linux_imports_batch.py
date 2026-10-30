"""Read-free lab diagnostics; no Docker, native import, SQL or real process."""

from __future__ import annotations

import asyncio
import hashlib
import json
import select
import time
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from tests import test_linux_imports_probe as lab_fixtures
from tests.test_linux_imports_probe import HOST, PROBE, audit_event, normal

attached_native = lab_fixtures.attached_native
isolated_supervisor = lab_fixtures.isolated_supervisor


def detail(
    name: str | None = "fixture", kind: str = "NON_MODULE", slot: str = "NONE"
) -> dict[str, Any]:
    return {
        "phase": "batch_detail",
        "stage": 0,
        "module": name,
        "kind": kind,
        "dict_file": False if kind == "MODULE_EXACT" else None,
        "identity_slot": slot,
    }


def ending(details: int = 1, **updates: Any) -> dict[str, Any]:
    return {
        "phase": "batch_end",
        "stage": 0,
        "examined": details,
        "details": details,
        "non_module_total": details,
        "module_exact_total": 0,
        "absent_total": 0,
        "incomplete": False,
        "anchor": "ANCHORED",
        **updates,
    }


def consume(
    events: list[dict[str, Any]],
    returncode: int = 75,
    read_error: BaseException | None = None,
    extra_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    class Process:
        returncode: int | None = None

        def wait(self, **_kwargs: Any) -> None:
            self.returncode = returncode

    class Reader:
        def __init__(self) -> None:
            self.events = iter(events)

        def read(self, _deadline: float) -> dict[str, Any]:
            try:
                return next(self.events)
            except StopIteration:
                raise (read_error or EOFError()) from None

    result = {
        "outcome": "inconclusive",
        "diagnostic_failure": "AUDIT_ERROR",
        **(extra_result or {}),
    }
    PROBE.consume_batch(result, Reader(), Process(), time.monotonic() + 3, 0)
    return result


def test_batch_never_reads_candidate_attributes_or_equality(attached_native, monkeypatch):
    child, _provider, modules, owners = attached_native
    reads: list[str] = []

    class Hostile:
        def __getattribute__(self, name):
            reads.append(name)
            raise AssertionError("SECRET")

        def __getattr__(self, name):
            reads.append(name)
            raise AssertionError("SECRET")

        def __eq__(self, _other):
            reads.append("equality")
            raise AssertionError("SECRET")

        def __hash__(self):
            return 0

    candidate = Hostile()
    child.__dict__["lib"] = candidate
    child.__dict__["ffi"] = candidate
    modules["_openssl.lib"] = candidate
    modules["none"] = None
    modules["module"] = ModuleType("module")
    backed = ModuleType("backed")
    backed.__file__ = "/SECRET.py"
    modules["backed"] = backed
    real_row = PROBE.module_row

    def anchor_only(name, *args):
        assert name == "cryptography.hazmat.bindings._rust"
        return real_row(name, *args)

    monkeypatch.setattr(PROBE, "module_row", anchor_only)
    rows, end = PROBE.batch_candidates(
        0,
        ["_openssl", "_openssl.lib", "backed", "missing", "module", "none"],
        {"_openssl"},
        owners,
        {},
        time.monotonic() + 3,
    )
    assert not reads
    assert [row["module"] for row in rows] == ["_openssl.lib", "none", "module", "missing"]
    assert [row["identity_slot"] for row in rows] == ["BOTH", "NONE", "NONE", "NONE"]
    assert (end["non_module_total"], end["module_exact_total"], end["absent_total"]) == (2, 1, 1)
    assert end["examined"] == 6 and not end["incomplete"] and end["anchor"] == "ANCHORED"
    assert "SECRET" not in json.dumps([rows, end])


@pytest.mark.parametrize("count", [8, 9])
def test_batch_eight_nine_candidates_priority_and_totals(attached_native, count):
    _child, _provider, modules, owners = attached_native
    names = ["accepted", "module"] + [f"z{n}" for n in range(count)]
    modules["accepted"] = ModuleType("accepted")
    modules["module"] = ModuleType("module")
    for name in names[2:]:
        modules[name] = object()
    rows, end = PROBE.batch_candidates(
        0, names, {"accepted", "module"}, owners, {}, time.monotonic() + 3
    )
    assert len(rows) == 8 and all(row["kind"] == "NON_MODULE" for row in rows)
    assert end["non_module_total"] == count and end["incomplete"] is (count == 9)
    assert end["module_exact_total"] == 0


def test_batch_name_cap_and_invalid_name_never_reflect_input(attached_native):
    _child, _provider, modules, owners = attached_native
    names = [f"n{n:04d}" for n in range(1501)]
    modules.update(dict.fromkeys(names))
    rows, end = PROBE.batch_candidates(0, names, set(), owners, {}, time.monotonic() + 3)
    assert len(rows) == 8 and end["examined"] == 1500 and end["incomplete"]
    assert end["non_module_total"] == 1500
    modules["bad/SECRET"] = object()
    rows, end = PROBE.batch_candidates(0, ["bad/SECRET"], set(), owners, {}, time.monotonic() + 3)
    assert rows[0]["module"] is None and "SECRET" not in json.dumps([rows, end])


@pytest.mark.parametrize("anchor", ["missing", "wrong_identity", "missing_slots"])
def test_batch_unanchored_and_none_never_create_false_identity(attached_native, anchor):
    child, provider, modules, owners = attached_native
    modules["none"] = None
    if anchor == "missing":
        modules.pop(provider.__name__)
    elif anchor == "wrong_identity":
        provider.__dict__["_openssl"] = ModuleType("_openssl")
    child.__dict__.pop("lib", None)
    child.__dict__.pop("ffi", None)
    rows, end = PROBE.batch_candidates(0, ["none"], set(), owners, {}, time.monotonic() + 3)
    assert rows[0]["identity_slot"] == "NONE"
    assert end["anchor"] == ("ANCHORED" if anchor == "missing_slots" else "UNANCHORED")


def test_batch_module_subclass_is_not_inspected(attached_native):
    _child, _provider, modules, owners = attached_native
    reads: list[str] = []

    class Hostile(ModuleType):
        def __getattribute__(self, name):
            reads.append(name)
            raise RuntimeError("SECRET")

    modules["hostile"] = Hostile("hostile")
    rows, _end = PROBE.batch_candidates(0, ["hostile"], set(), owners, {}, time.monotonic() + 3)
    assert rows[0]["kind"] == "NON_MODULE" and not reads


def test_batch_deadline_refuses_without_emitting(attached_native):
    _child, _provider, _modules, owners = attached_native
    with pytest.raises(TimeoutError):
        PROBE.batch_candidates(0, ["none"], set(), owners, {}, time.monotonic() - 1)


def test_batch_unknown_nonmodule_is_prioritized_over_fileless_exact_modules(attached_native):
    _child, _provider, modules, owners = attached_native
    names = [f"a{index}" for index in range(10)] + ["z_nonmodule"]
    for name in names[:-1]:
        modules[name] = ModuleType(name)
    modules[names[-1]] = object()
    rows, end = PROBE.batch_candidates(0, names, set(), owners, {}, time.monotonic() + 3)
    assert rows[0]["module"] == "z_nonmodule"
    assert end["non_module_total"] == 1 and end["module_exact_total"] == 10
    assert len(rows) == 8 and end["incomplete"]


def test_batch_odd_dictionary_is_a_null_fact_not_getattr_fallback(attached_native, monkeypatch):
    _child, _provider, modules, owners = attached_native

    class SimulatedExactModule:
        __dict__: Any = []

    # Synthetic exact-type branch; real ModuleType's dict is a builtin getset.
    monkeypatch.setattr(PROBE, "ModuleType", SimulatedExactModule)
    modules["odd"] = SimulatedExactModule()
    rows, end = PROBE.batch_candidates(0, ["odd"], set(), owners, {}, time.monotonic() + 3)
    assert rows == [detail("odd", "MODULE_EXACT") | {"dict_file": None}]
    assert end["anchor"] == "UNANCHORED"


@pytest.mark.parametrize("fault", ["owner", "path", "outside", "nonstring", "child_file"])
def test_batch_anchor_rechecks_origin_and_fileless_identity(attached_native, fault):
    child, provider, modules, owners = attached_native
    candidate = object()
    child.__dict__["lib"] = candidate
    modules["candidate"] = candidate
    if fault == "owner":
        owners["cryptography"] = "different"
    elif fault == "path":
        provider.__file__ = "/installed/cryptography/other.so"
    elif fault == "outside":
        provider.__file__ = "/outside/SECRET.so"
    elif fault == "nonstring":
        provider.__dict__["__file__"] = object()
    else:
        child.__file__ = "/installed/cryptography/other.py"
    rows, end = PROBE.batch_candidates(0, ["candidate"], set(), owners, {}, time.monotonic() + 3)
    assert rows[0]["identity_slot"] == "NONE" and end["anchor"] == "UNANCHORED"
    assert "SECRET" not in json.dumps([rows, end])


@pytest.mark.parametrize("fail_phase", [None, "batch_detail", "batch_end"])
def test_batch_emitter_terminal_and_transport_failure_stop(attached_native, fail_phase):
    _child, _provider, modules, owners = attached_native
    modules["candidate"] = ModuleType("candidate")
    attempted: list[dict[str, Any]] = []

    def emit(event):
        attempted.append(event)
        if event["phase"] == fail_phase:
            raise OSError("SECRET")

    assert not PROBE.audit_module(
        SimpleNamespace(emit=emit),
        0,
        "candidate",
        modules["candidate"],
        owners,
        {},
        batch=(["candidate"], set(), time.monotonic() + 3),
    )
    expected = ["audit_error", "batch_detail"]
    if fail_phase != "batch_detail":
        expected.append("batch_end")
    assert [event["phase"] for event in attempted] == expected
    assert "SECRET" not in json.dumps(attempted)


@pytest.mark.parametrize("tail", [b"", b"partial SECRET"])
def test_terminal_eof_with_partial_line_is_protocol_not_eof(monkeypatch, tail):
    monkeypatch.setattr(select, "select", lambda *_args: ([9], [], []))
    monkeypatch.setattr(PROBE, "os", SimpleNamespace(read=lambda *_args: b""))
    lab = SimpleNamespace(STOP=False, LINE_BYTES=4096)
    reader = PROBE.LineReader(SimpleNamespace(fileno=lambda: 9), lab)
    reader.buffer = tail
    with pytest.raises(PROBE.ImportFault if tail else EOFError):
        reader.read(time.monotonic() + 1)


def test_terminal_batch_does_not_become_inventory_or_fit(isolated_supervisor):
    accepted = ["accepted", "fixture", "installed/accepted.py"]
    result = isolated_supervisor(
        [
            {"phase": "start", "stage": 0},
            {"phase": "module", "stage": 0, "row": accepted},
            audit_event(),
            detail(),
            ending(),
        ]
    )
    assert result["diagnostic_failure"] == "AUDIT_ERROR" and result["member_returncode"] == 75
    assert result["batch"]["details"] == [detail()] and not result["batch"]["incomplete"]
    assert PROBE.unpack_inventory(result["module_inventory"]) == [[0, accepted]]
    assert not any(row["phase"].startswith("batch") for row in result["events"])
    assert result["cleanup_confirmed"] and HOST.classify_limited(normal(), result) == "inconclusive"
    assert HOST.classify_limited(normal(), {**normal(), "batch": {}}) == "inconclusive"


@pytest.mark.parametrize(
    "field,value",
    [
        ("stage", True),
        ("module", "bad/SECRET"),
        ("kind", "SECRET"),
        ("dict_file", 0),
        ("identity_slot", "SECRET"),
        ("extra", "SECRET"),
    ],
)
def test_batch_forged_detail_never_copied(field, value):
    event = {**detail(), field: value}
    result = consume([event, ending()])
    assert result["diagnostic_failure"] == "PROTOCOL" and result["batch"]["incomplete"]
    assert "SECRET" not in json.dumps(result)


@pytest.mark.parametrize(
    "changes",
    [
        {"details": 2},
        {"non_module_total": -1},
        {"non_module_total": True},
        {"examined": 0},
        {"examined": 1500},
        {"stage": 1},
        {"anchor": "UNANCHORED"},
        {"module_exact_total": 1},
        {"absent_total": 1},
        {"incomplete": 0},
        {"extra": "SECRET"},
    ],
)
def test_batch_forged_end_never_approved(changes):
    result = consume([detail(slot="LIB"), ending(**changes)])
    assert result["diagnostic_failure"] == "PROTOCOL" and result["batch"]["incomplete"]
    assert "SECRET" not in json.dumps(result)


def test_batch_counts_must_match_each_kind_even_if_incomplete():
    result = consume([detail(), ending(non_module_total=0, module_exact_total=1, incomplete=True)])
    assert result["diagnostic_failure"] == "PROTOCOL" and result["batch"]["incomplete"]


@pytest.mark.parametrize("terminal", ["missing", "extra", "timeout", "wrong_exit", "ninth"])
def test_batch_terminal_failures_are_protocol_incomplete(terminal):
    events = [detail()]
    if terminal == "ninth":
        events = [detail(f"n{n}") for n in range(9)]
    elif terminal != "missing":
        events.append(ending())
    if terminal == "extra":
        events.append({"phase": "SECRET", "body": "SECRET"})
    result = consume(
        events,
        returncode=-6 if terminal == "wrong_exit" else 75,
        read_error=TimeoutError() if terminal == "timeout" else None,
    )
    assert result["diagnostic_failure"] == "PROTOCOL" and result["batch"]["incomplete"]
    assert len(result["batch"]["details"]) <= 8 and "SECRET" not in json.dumps(result)


def test_batch_metadata_cap_fails_closed():
    result = consume([detail(), ending()], extra_result={"bounded_fixture": "x" * 7990})
    assert result["diagnostic_failure"] == "PROTOCOL" and result["batch"]["incomplete"]


@pytest.mark.parametrize("stage,category", [(-1, "FILELESS_UNATTRIBUTED"), (0, "OTHER")])
def test_batch_not_triggered_for_baseline_or_other_error(monkeypatch, stage, category):
    emitted: list[dict[str, Any]] = []

    def failure(*_args):
        raise PROBE.AuditFault(category)

    monkeypatch.setattr(PROBE, "module_row", failure)
    assert not PROBE.audit_module(
        SimpleNamespace(emit=emitted.append),
        stage,
        "fixture",
        None,
        {},
        {},
        batch=(["fixture"], set(), time.monotonic() + 3),
    )
    assert [event["phase"] for event in emitted] == ["audit_error"]


@pytest.mark.parametrize("diagnostic_only", [False, True])
def test_host_never_starts_limited_for_batch_or_diagnostic_only(
    tmp_path, monkeypatch, diagnostic_only
):
    observer = HOST.Observer.__new__(HOST.Observer)
    observer.root, observer.image = tmp_path, HOST.BASE
    observer.total_written, observer.originals = 0, {}
    observer.installed, observer.inventory = tmp_path / "unused", {}
    observer.prepared = {"launchers_allowlist": []}
    observer.probe = tmp_path / "probe"
    observer.probe.mkdir()
    (observer.probe / "runtime.json").write_bytes(b"{}")
    observer.runtime_hash = hashlib.sha256(b"{}").hexdigest()
    observer.watchdog = SimpleNamespace(
        start=lambda: None, close=lambda: None, fired=SimpleNamespace(is_set=lambda: False)
    )
    monkeypatch.setattr(HOST.PREP, "verify_tree", lambda *_args: {})
    cases: list[str] = []

    async def cli(*_args, **_kwargs):
        if _args[0] == "version":
            return 0, json.dumps(
                {"Server": {"Version": "29.7.2", "Os": "linux", "Arch": "amd64"}}
            ).encode()
        return 0, b""

    async def inspect(_target):
        return {"Os": "linux", "Architecture": "amd64", "Config": {"Env": []}}

    async def case(name):
        cases.append(name)
        diagnostic = normal()
        if not diagnostic_only:
            diagnostic["batch"] = {}
        value = {
            "case": name,
            "outcome": "normal",
            "cleanup_confirmed": True,
            "diagnostic": diagnostic,
        }
        observer.save(name + ".json", value)
        return value

    monkeypatch.setattr(observer, "cli", cli)
    monkeypatch.setattr(observer, "inspect", inspect)
    monkeypatch.setattr(observer, "case", case)
    result = asyncio.run(observer.run(diagnostic_only=True) if diagnostic_only else observer.run())
    assert cases == ["control"]
    assert not result["complete"] and not result["imports_fit_as32"]
