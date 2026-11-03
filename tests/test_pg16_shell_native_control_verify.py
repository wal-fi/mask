"""Fake-only tests for the pure native-control evidence verifier core.

The tests were written before docs/poc/pg16_shell_native_control_verify.py
existed; root measured that feature-absent baseline (203 fixture errors and
one pure-source failure, all for the missing file), not a product
regression. Fixtures are hand-written from literal pins, limits
and templates; the builder only recomputes hashes and the batch label, never
a verdict, and never calls the producer or the verifier's own constants.
Nothing here is native: no file is collected, no process, job or DLL is
touched, and these fakes are never native measurements.
"""

import ast
import builtins
import ctypes
import dataclasses
import hashlib
import json
import os
import runpy
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "docs/poc/pg16_shell_native_control_verify.py"
NONCE = "0123456789abcdef0123456789abcdef"
OTHER = "fedcba9876543210fedcba9876543210"
ARGV0 = "C:\\fictitious\\lab\\venv\\Scripts\\python.exe"
PINS = {
    "host_sha256": "dfcc4ed6be3ea8ab47b7a38ca8a9d4bfa00b3c75cda41c365be3dd5b1aa3dac7",
    "adapter_sha256": "eaebedd6ac36602ba30cb51a4c30a2a93737f1127c23cdc4ebb8ae8cf9246407",
    "backend_sha256": "10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726",
    "launcher_sha256": "bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82",
}
LIMITS = {
    "deadline_seconds": 60.0,
    "cleanup_seconds": 10.0,
    "max_turns": 1200,
    "cleanup_turns": 200,
    "ready_seconds": 10.0,
    "ready_turns": 200,
    "retain_bytes": 1024,
    "audit_limit": 512,
    "active_process_limit": 2,
}
ENVIRONMENT_NAMES = [
    "SystemRoot",
    "WINDIR",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
    "HOMEDRIVE",
    "HOMEPATH",
    "SystemDrive",
]
NORMAL_LITERAL = 'print("MASKGW-NATIVE-CONTROL-NORMAL")'
SLEEP_LITERAL = 'import time;print("MASKGW-NATIVE-CONTROL-READY",flush=True);time.sleep(120)'
NORMAL_CRLF = b"MASKGW-NATIVE-CONTROL-NORMAL\r\n"
NORMAL_LF = b"MASKGW-NATIVE-CONTROL-NORMAL\n"
READY_CRLF = b"MASKGW-NATIVE-CONTROL-READY\r\n"
READY_LF = b"MASKGW-NATIVE-CONTROL-READY\n"
CASE_NAMES = ("NORMAL", "TERMINATE", "LAST_CLOSE")
CASE_KEYS = (
    "case",
    "outcome",
    "rejection",
    "exit_code",
    "framing",
    "total_processes",
    "terminated",
    "ready",
    "inner_closed",
    "audit_integral",
    "audit_entries",
    "terminate_calls",
    "seconds",
)
CLEAN_ENTRIES = ["CreateJobObjectW", "CreateProcessW", "ResumeThread", "CloseHandle"]
TERMINATED_ENTRIES = ["CreateJobObjectW", "CreateProcessW", "ResumeThread", "TerminateJobObject"]
REASONS = frozenset(
    (
        "EXPECTED",
        "INPUT",
        "FILESET",
        "CAP",
        "SCHEMA",
        "NONCE",
        "PIN",
        "BINDING",
        "PREFIX",
        "INVOCATION",
        "SUPERVISION",
        "STDOUT",
        "SNAPSHOT",
        "AUDIT",
        "CONTRADICTION",
        "INTERNAL",
    )
)
APPROVED = ("VERIFIED_APPROVED", "OK")
REJECTED = ("VERIFIED_REJECTED", "OK")
GOOD = "good-snapshot"


# -- hand-written fixture builder ---------------------------------------------------


@dataclasses.dataclass
class Bundle:
    summary_raw: Any
    transport_raw: Any
    private: Any


def encode(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def good_snapshot() -> dict[str, Any]:
    return {
        "valid": True,
        "total": 1,
        "active": 1,
        "members": 1,
        "inner_present": True,
        "inner_verified": True,
    }


def invocation(number: int, name: str) -> dict[str, Any]:
    return {
        "kind": "MASKGW_PG16_NATIVE_CONTROL_INVOCATION_V1",
        "nonce": NONCE,
        **PINS,
        "limits": dict(LIMITS),
        "case": name,
        "number": number,
        "argv": [ARGV0, "-I", "-B", "-c", NORMAL_LITERAL if name == "NORMAL" else SLEEP_LITERAL],
        "environment_names": list(ENVIRONMENT_NAMES),
    }


def supervision(name: str, stdout: bytes, **facts: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "kind": "MASKGW_PG16_NATIVE_CONTROL_SUPERVISION_V1",
        "case": name,
        "owner_state": "CLOSED",
        "reason": None,
        "terminated": False,
        "overflow": False,
        "signaled": True,
        "eof": True,
        "exit_code": 0,
        "total_processes": 1,
        "turns": 2,
        "ready": False,
        "ready_turns": 0,
        "retained_stdout_bytes": len(stdout),
        "seconds": 0.5,
    }
    record.update(facts)
    return record


def summary_case(
    sup: dict[str, Any], outcome: str, rejection: Any, framing: Any, **last: Any
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "case": sup["case"],
        "outcome": outcome,
        "rejection": rejection,
        "exit_code": sup["exit_code"],
        "framing": framing,
        "total_processes": sup["total_processes"],
        "terminated": sup["terminated"],
        "ready": None if sup["case"] == "NORMAL" else sup["ready"],
        "inner_closed": None,
        "audit_integral": None,
        "audit_entries": None,
        "terminate_calls": None,
        "seconds": sup["seconds"],
    }
    record.update(last)
    return record


def normal(
    *,
    stdout: bytes = NORMAL_CRLF,
    framing: Any = "CRLF",
    outcome: str = "APPROVED",
    rejection: Any = None,
    **facts: Any,
) -> dict[str, Any]:
    sup = supervision("NORMAL", stdout, **facts)
    return {
        "name": "NORMAL",
        "stdout": stdout,
        "supervision": sup,
        "summary": summary_case(sup, outcome, rejection, framing),
    }


def terminate(
    *,
    stdout: bytes = READY_CRLF,
    framing: Any = "CRLF",
    outcome: str = "APPROVED",
    rejection: Any = None,
    **facts: Any,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "reason": "DEADLINE",
        "terminated": True,
        "exit_code": 1,
        "turns": 1201,
        "ready": True,
        "ready_turns": 1,
        "seconds": 60.5,
    }
    base.update(facts)
    sup = supervision("TERMINATE", stdout, **base)
    return {
        "name": "TERMINATE",
        "stdout": stdout,
        "supervision": sup,
        "summary": summary_case(sup, outcome, rejection, framing),
    }


def last_close(**options: Any) -> dict[str, Any]:
    """Options: stdout, framing, outcome, rejection, snapshot, entries,
    integral and inner_closed; every other key is a supervision fact."""
    stdout = options.pop("stdout", READY_CRLF)
    framing = options.pop("framing", "CRLF")
    outcome = options.pop("outcome", "APPROVED")
    rejection = options.pop("rejection", None)
    snapshot = options.pop("snapshot", GOOD)
    entries = options.pop("entries", None)
    integral = options.pop("integral", True)
    inner_closed = options.pop("inner_closed", True)
    base: dict[str, Any] = {
        "reason": None,
        "terminated": False,
        "exit_code": 0,
        "turns": 3,
        "ready": True,
        "ready_turns": 1,
        "seconds": 2.25,
    }
    base.update(options)
    sup = supervision("LAST_CLOSE", stdout, **base)
    names = list(CLEAN_ENTRIES if entries is None else entries)
    count = sum(1 for name in names if name in ("TerminateJobObject", "TerminateProcess"))
    last = {
        "inner_closed": inner_closed,
        "audit_integral": integral,
        "audit_entries": len(names),
        "terminate_calls": count,
    }
    return {
        "name": "LAST_CLOSE",
        "stdout": stdout,
        "supervision": sup,
        "summary": summary_case(sup, outcome, rejection, framing, **last),
        "snapshot": good_snapshot() if snapshot is GOOD else snapshot,
        "audit": {
            "kind": "MASKGW_PG16_NATIVE_CONTROL_AUDIT_V1",
            "integral": integral,
            "limit": 512,
            "entries": names,
            "terminate_calls": count,
        },
    }


def not_run(name: str) -> dict[str, Any]:
    record: dict[str, Any] = dict.fromkeys(CASE_KEYS)
    record.update(case=name, outcome="NOT_RUN")
    return record


EDITS = frozenset(
    (
        "invocation_edit",
        "private_raw_edit",
        "summary_edit",
        "summary_raw_edit",
        "transport_edit",
        "transport_raw_edit",
        "drop",
    )
)


def build(cases: list[dict[str, Any]], **edits: Any) -> Bundle:
    """Hand-built bundle; edits are optional hooks named in EDITS."""
    assert set(edits) <= EDITS
    invocation_edit = edits.get("invocation_edit")
    private_raw_edit = edits.get("private_raw_edit")
    summary_edit = edits.get("summary_edit")
    summary_raw_edit = edits.get("summary_raw_edit")
    transport_edit = edits.get("transport_edit")
    transport_raw_edit = edits.get("transport_raw_edit")
    drop: tuple[str, ...] = edits.get("drop", ())
    private: dict[str, bytes] = {}
    for number, case in enumerate(cases, 1):
        prefix = "case-" + str(number) + "/"
        record = invocation(number, case["name"])
        if invocation_edit is not None:
            invocation_edit(number, record)
        private[prefix + "invocation.json"] = encode(record)
        private[prefix + "supervision.json"] = encode(case["supervision"])
        private[prefix + "local-stdout.bin"] = case["stdout"]
        if case["name"] == "LAST_CLOSE":
            snapshot = {
                "kind": "MASKGW_PG16_NATIVE_CONTROL_SNAPSHOT_V1",
                "snapshot": case["snapshot"],
            }
            private[prefix + "snapshot.json"] = encode(snapshot)
            private[prefix + "audit.json"] = encode(case["audit"])
    if private_raw_edit is not None:
        private = {name: private_raw_edit(name, raw) for name, raw in private.items()}
    for name in drop:
        del private[name]
    records = [case["summary"] for case in cases]
    records += [not_run(name) for name in CASE_NAMES[len(cases) :]]
    approved = all(record["outcome"] == "APPROVED" for record in records)
    summary: dict[str, Any] = {
        "kind": "MASKGW_PG16_NATIVE_CONTROL_SUMMARY_V1",
        "nonce": NONCE,
        "outcome": "APPROVED" if approved else "REJECTED",
        "scope": "BENIGN_CONTROL_ONLY",
        "admission_3s": "NOT_MEASURED",
        "cases": records,
        **PINS,
    }
    if summary_edit is not None:
        summary_edit(summary)
    summary_raw = encode(summary)
    if summary_raw_edit is not None:
        summary_raw = summary_raw_edit(summary_raw)
    transport: dict[str, Any] = {
        "kind": "MASKGW_PG16_NATIVE_CONTROL_TRANSPORT_V1",
        "nonce": NONCE,
        "outcome": summary["outcome"],
        "summary": {"name": "summary.json", "bytes": len(summary_raw), "sha256": sha(summary_raw)},
        "private": [
            {"name": name, "bytes": len(raw), "sha256": sha(raw)}
            for name, raw in sorted(private.items())
        ],
    }
    if transport_edit is not None:
        transport_edit(transport)
    transport_raw = encode(transport)
    if transport_raw_edit is not None:
        transport_raw = transport_raw_edit(transport_raw)
    return Bundle(summary_raw, transport_raw, private)


# -- scenarios (facts chosen by hand, coherent with the runner contract) ------------


def approved(lf: bool = False) -> list[dict[str, Any]]:
    if lf:
        return [
            normal(stdout=NORMAL_LF, framing="LF"),
            terminate(stdout=READY_LF, framing="LF"),
            last_close(stdout=READY_LF, framing="LF"),
        ]
    return [normal(), terminate(), last_close()]


def rejected_at_1() -> list[dict[str, Any]]:
    return [normal(exit_code=1, outcome="REJECTED", rejection="MISMATCH")]


def rejected_at_2() -> list[dict[str, Any]]:
    return [
        normal(),
        terminate(
            stdout=b"",
            framing=None,
            outcome="REJECTED",
            rejection="READY_MISSING",
            reason="READY_MISSING",
            ready=False,
            ready_turns=200,
        ),
    ]


def failed_last_close(rejection: str = "FAILED_LAST_CLOSE") -> list[dict[str, Any]]:
    return [
        normal(),
        terminate(),
        last_close(
            outcome="REJECTED",
            rejection=rejection,
            reason="DEADLINE",
            terminated=True,
            exit_code=1,
            entries=TERMINATED_ENTRIES,
        ),
    ]


def null_snapshot() -> list[dict[str, Any]]:
    return [
        normal(),
        terminate(),
        last_close(
            stdout=b"",
            framing=None,
            outcome="REJECTED",
            rejection="READY_MISSING",
            reason="READY_MISSING",
            ready=False,
            ready_turns=200,
            terminated=True,
            exit_code=1,
            snapshot=None,
            inner_closed=False,
            entries=TERMINATED_ENTRIES,
        ),
    ]


def snapshot_invalid(rejection: str = "SNAPSHOT_INVALID", snapshot: Any = None) -> list[Any]:
    bad = snapshot if snapshot is not None else {**good_snapshot(), "valid": False, "members": 0}
    return [
        normal(),
        terminate(),
        last_close(
            outcome="REJECTED",
            rejection=rejection,
            reason="SNAPSHOT_INVALID",
            terminated=True,
            exit_code=1,
            snapshot=bad,
            inner_closed=False,
            entries=TERMINATED_ENTRIES,
        ),
    ]


def audit_invalid() -> list[dict[str, Any]]:
    return [
        normal(),
        terminate(),
        last_close(outcome="REJECTED", rejection="AUDIT_INVALID", integral=False),
    ]


def caller_clock() -> list[dict[str, Any]]:
    return [
        normal(reason="CALLER_CLOCK", seconds=None, outcome="REJECTED", rejection="CALLER_CLOCK")
    ]


def with_sup(cases: list[dict[str, Any]], index: int, **changes: Any) -> list[dict[str, Any]]:
    cases[index]["supervision"].update(changes)
    return cases


def with_sum(cases: list[dict[str, Any]], index: int, **changes: Any) -> list[dict[str, Any]]:
    cases[index]["summary"].update(changes)
    return cases


def with_last(**options: Any) -> list[dict[str, Any]]:
    return [normal(), terminate(), last_close(**options)]


CASE_3_FILES = (
    "case-3/invocation.json",
    "case-3/supervision.json",
    "case-3/local-stdout.bin",
    "case-3/snapshot.json",
    "case-3/audit.json",
)


def at(number: int, function: Any) -> Any:
    def edit(current: int, record: dict[str, Any]) -> None:
        if current == number:
            function(record)

    return edit


def only(name: str, function: Any) -> Any:
    def edit(current: str, raw: bytes) -> bytes:
        return function(raw) if current == name else raw

    return edit


# -- fixture and helpers -------------------------------------------------------------


@pytest.fixture
def mod() -> Any:
    module = runpy.run_path(str(MODULE))
    return SimpleNamespace(
        Expected=module["Expected"],
        verify=module["verify"],
        REASONS=module["REASONS"],
        globals=module["verify"].__globals__,
    )


def expected(mod: Any, nonce: str = NONCE, argv0: str = ARGV0) -> Any:
    return mod.Expected(nonce=nonce, argv0=argv0)


def run(mod: Any, bundle: Bundle, record: Any = None) -> Any:
    target = expected(mod) if record is None else record
    return mod.verify(target, bundle.summary_raw, bundle.transport_raw, bundle.private)


def invalid(mod: Any, bundle: Bundle, reason: str, record: Any = None) -> None:
    assert run(mod, bundle, record) == ("INVALID", reason)


# -- positive coherent bundles --


@pytest.mark.parametrize(
    ("make", "result", "files"),
    [
        (approved, APPROVED, 11),
        (lambda: approved(lf=True), APPROVED, 11),
        (rejected_at_1, REJECTED, 3),
        (rejected_at_2, REJECTED, 6),
        (failed_last_close, REJECTED, 11),
        (null_snapshot, REJECTED, 11),
        (snapshot_invalid, REJECTED, 11),
        (audit_invalid, REJECTED, 11),
        (caller_clock, REJECTED, 3),
    ],
    ids=[
        "approved-crlf",
        "approved-lf",
        "rejected-1",
        "rejected-2",
        "failed-last-close",
        "null-snapshot",
        "snapshot-invalid",
        "audit-invalid",
        "caller-clock",
    ],
)
def test_coherent_bundles(mod: Any, capsys: Any, make: Any, result: Any, files: int) -> None:
    bundle = build(make())
    assert len(bundle.private) == files
    before = dict(bundle.private)
    outcome = run(mod, bundle)
    assert outcome == result
    assert type(outcome) is tuple and all(type(item) is str for item in outcome)
    assert bundle.private == before and run(mod, bundle) == result
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


# -- expected record and exact input types --


def test_expected_record_is_minimal_frozen_and_hides_argv0(mod: Any) -> None:
    record = expected(mod)
    assert [field.name for field in dataclasses.fields(record)] == ["nonce", "argv0"]
    assert ARGV0 not in repr(record) and ARGV0 not in str(record)
    assert "fictitious" not in repr(record)
    with pytest.raises(AttributeError):
        record.nonce = OTHER
    assert mod.REASONS == REASONS


class SneakyStr(str):
    pass


class SneakyBytes(bytes):
    pass


class SneakyDict(dict[str, bytes]):
    pass


@pytest.mark.parametrize(
    "kind",
    ["dict", "upper", "short", "int", "empty-argv0", "nul-argv0", "str-subclass", "subclass"],
)
def test_invalid_expected_record(mod: Any, kind: str) -> None:
    bundle = build(approved())
    if kind == "dict":
        record: Any = {"nonce": NONCE, "argv0": ARGV0}
    elif kind == "upper":
        record = expected(mod, nonce=NONCE.upper())
    elif kind == "short":
        record = expected(mod, nonce=NONCE[:-1])
    elif kind == "int":
        record = mod.Expected(nonce=7, argv0=ARGV0)
    elif kind == "empty-argv0":
        record = expected(mod, argv0="")
    elif kind == "nul-argv0":
        record = expected(mod, argv0=ARGV0 + "\x00")
    elif kind == "str-subclass":
        record = mod.Expected(nonce=SneakyStr(NONCE), argv0=ARGV0)
    else:
        subclass = type("Sub", (mod.Expected,), {})
        record = subclass(nonce=NONCE, argv0=ARGV0)
    invalid(mod, bundle, "EXPECTED", record)


@pytest.mark.parametrize(
    "kind",
    [
        "summary-bytearray",
        "summary-memoryview",
        "summary-str",
        "summary-subclass",
        "transport-bytearray",
        "transport-subclass",
        "private-list",
        "private-subclass",
        "key-subclass",
        "key-bytes",
        "value-bytearray",
        "value-subclass",
    ],
)
def test_inexact_input_types(mod: Any, kind: str) -> None:
    bundle = build(approved())
    raw = bundle.summary_raw
    if kind == "summary-bytearray":
        bundle.summary_raw = bytearray(raw)
    elif kind == "summary-memoryview":
        bundle.summary_raw = memoryview(raw)
    elif kind == "summary-str":
        bundle.summary_raw = raw.decode("ascii")
    elif kind == "summary-subclass":
        bundle.summary_raw = SneakyBytes(raw)
    elif kind == "transport-bytearray":
        bundle.transport_raw = bytearray(bundle.transport_raw)
    elif kind == "transport-subclass":
        bundle.transport_raw = SneakyBytes(bundle.transport_raw)
    elif kind == "private-list":
        bundle.private = list(bundle.private.items())
    elif kind == "private-subclass":
        bundle.private = SneakyDict(bundle.private)
    elif kind == "key-subclass":
        name = "case-1/local-stdout.bin"
        value = bundle.private.pop(name)
        bundle.private[SneakyStr(name)] = value
    elif kind == "key-bytes":
        bundle.private[b"case-1/local-stdout.bin"] = bundle.private.pop("case-1/local-stdout.bin")
    elif kind == "value-bytearray":
        bundle.private["case-1/local-stdout.bin"] = bytearray(NORMAL_CRLF)
    else:
        bundle.private["case-1/local-stdout.bin"] = SneakyBytes(NORMAL_CRLF)
    invalid(mod, bundle, "INPUT")


TRAP_CALLS: list[str] = []


class TrapBytes(bytes):
    def __len__(self) -> int:
        TRAP_CALLS.append("len")
        return bytes.__len__(self)

    def __eq__(self, other: object) -> bool:
        TRAP_CALLS.append("eq")
        return bytes.__eq__(self, other)

    def __hash__(self) -> int:
        TRAP_CALLS.append("hash")
        return bytes.__hash__(self)


class TrapStr(str):
    def __eq__(self, other: object) -> bool:
        TRAP_CALLS.append("eq")
        return str.__eq__(self, other)

    def __lt__(self, other: str) -> bool:
        TRAP_CALLS.append("lt")
        return str.__lt__(self, other)

    def __hash__(self) -> int:
        return str.__hash__(self)


def test_input_types_are_checked_before_any_dereference(mod: Any) -> None:
    bundle = build(approved())
    bundle.private["case-1/local-stdout.bin"] = TrapBytes(NORMAL_CRLF)
    name = "case-2/local-stdout.bin"
    bundle.private[TrapStr(name)] = bundle.private.pop(name)
    TRAP_CALLS.clear()
    assert run(mod, bundle) == ("INVALID", "INPUT")
    assert TRAP_CALLS == []


@pytest.mark.parametrize(
    "name",
    [
        "case-1/../case-1/invocation.json",
        "case-1\\invocation.json",
        "C:/case-1/invocation.json",
        "/case-1/invocation.json",
        "case-1/invocation.json:ads",
        "CASE-1/invocation.json",
        "case-1/Invocation.json",
        "case-1/invocation.json\x00",
        "case-1//invocation.json",
        "case-4/invocation.json",
        "case-1/held.json",
        "case-1/snapshot.json",
        "summary.json",
        "",
    ],
)
def test_names_outside_the_whitelist(mod: Any, name: str) -> None:
    bundle = build(approved())
    bundle.private[name] = b"{}\n"
    invalid(mod, bundle, "FILESET")


@pytest.mark.parametrize(
    ("target", "size"),
    [
        ("summary", 16385),
        ("transport", 4097),
        ("case-1/invocation.json", 4097),
        ("case-1/supervision.json", 4097),
        ("case-3/snapshot.json", 4097),
        ("case-3/audit.json", 65537),
        ("case-1/local-stdout.bin", 1025),
    ],
)
def test_size_caps_before_parse(mod: Any, target: str, size: int) -> None:
    bundle = build(approved())
    blob = b"x" * size
    if target == "summary":
        bundle.summary_raw = blob
    elif target == "transport":
        bundle.transport_raw = blob
    else:
        bundle.private[target] = blob
    invalid(mod, bundle, "CAP")


# -- strict JSON and closed schemas --


def _summary_raw(function: Any) -> Any:
    return lambda: build(approved(), summary_raw_edit=function)


def _summary(function: Any, make: Any = approved) -> Any:
    return lambda: build(make(), summary_edit=function)


def _transport(function: Any) -> Any:
    return lambda: build(approved(), transport_edit=function)


def _set(path: tuple[Any, ...], value: Any) -> Any:
    def edit(record: dict[str, Any]) -> None:
        target: Any = record
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return edit


def _delete(key: str) -> Any:
    def edit(record: dict[str, Any]) -> None:
        del record[key]

    return edit


def _duplicate_first_private(transport: dict[str, Any]) -> None:
    transport["private"].insert(0, dict(transport["private"][0]))


def _reverse_private(transport: dict[str, Any]) -> None:
    transport["private"].reverse()


@pytest.mark.parametrize(
    "make",
    [
        _summary_raw(lambda raw: raw + b"\n"),
        _summary_raw(lambda raw: raw[:-1] + b"\r\n"),
        _summary_raw(lambda raw: raw[:-1]),
        _summary_raw(lambda raw: b" " + raw),
        _summary_raw(lambda raw: raw.replace(b",", b", ", 1)),
        _summary_raw(
            lambda raw: raw.replace(
                b'"admission_3s":"NOT_MEASURED",',
                b'"admission_3s":"NOT_MEASURED","admission_3s":"NOT_MEASURED",',
                1,
            )
        ),
        _summary_raw(lambda raw: raw.replace(b'"seconds":0.5', b'"seconds":NaN', 1)),
        _summary_raw(lambda raw: raw.replace(b'"seconds":0.5', b'"seconds":Infinity', 1)),
        _summary_raw(lambda raw: raw.replace(b"BENIGN_CONTROL_ONLY", b"BENIGN_\xc3\x93NLY", 1)),
        _summary_raw(lambda _raw: b'{"a":' + b"[" * 40 + b"]" * 40 + b"}\n"),
        _summary_raw(lambda _raw: b"[]\n"),
        _summary(_set(("extra",), 1)),
        _summary(_delete("scope")),
        _summary(_set(("kind",), "MASKGW_PG16_NATIVE_CONTROL_SUMMARY_V2")),
        _summary(_set(("scope",), "ADMISSION")),
        _summary(_set(("admission_3s",), "WITHIN_3S")),
        _summary(_set(("backend_sha256",), PINS["backend_sha256"].upper())),
        _summary(_set(("cases", 0, "exit_code"), True)),
        _summary(_set(("cases", 0, "exit_code"), 10**30)),
        _summary(_set(("cases", 0, "seconds"), 1)),
        _summary(_set(("cases", 0, "framing"), "CR")),
        _summary(_set(("cases", 0, "ready"), False)),
        _summary(_set(("cases", 0, "inner_closed"), True)),
        _summary(_set(("cases", 2, "inner_closed"), 1)),
        _summary(_set(("cases", 0, "rejection"), "WEIRD"), rejected_at_1),
        _summary(_set(("cases", 0, "outcome"), "MAYBE")),
        _summary(_set(("cases", 0, "extra"), None)),
        _summary(_set(("cases",), [])),
        _transport(_set(("extra",), 1)),
        _transport(_set(("kind",), "OTHER")),
        _transport(_reverse_private),
        _transport(_duplicate_first_private),
        _transport(_set(("private", 0, "sha256"), "A" * 64)),
        _transport(_set(("private", 0, "bytes"), True)),
        _transport(_set(("private", 0, "extra"), 1)),
        _transport(_set(("summary", "name"), "other.json")),
        lambda: build(approved(), transport_raw_edit=lambda raw: raw[:-1] + b"\r\n"),
    ],
)
def test_public_schema_violations(mod: Any, make: Any) -> None:
    invalid(mod, make(), "SCHEMA")


def _crlf(raw: bytes) -> bytes:
    return raw[:-1] + b"\r\n"


@pytest.mark.parametrize(
    "make",
    [
        lambda: build(with_sup(approved(), 0, eof=1)),
        lambda: build(with_sup(approved(), 0, kind="OTHER")),
        lambda: build(with_sup(approved(), 0, turns=None)),
        lambda: build(with_sup(approved(), 0, reason="WEIRD")),
        lambda: build(with_sup(approved(), 0, extra=1)),
        lambda: build(approved(), invocation_edit=at(1, _set(("extra",), 1))),
        lambda: build(approved(), invocation_edit=at(1, _set(("number",), True))),
        lambda: build(approved(), invocation_edit=at(2, _set(("kind",), "OTHER"))),
        lambda: build(approved(), private_raw_edit=only("case-1/invocation.json", _crlf)),
        lambda: build(with_last(entries=[*CLEAN_ENTRIES, 7])),
        lambda: build(with_last(integral=1)),
        lambda: build(with_last(snapshot={**good_snapshot(), "valid": "true"})),
        lambda: build(with_last(snapshot={**good_snapshot(), "total": True})),
        lambda: build(with_last(snapshot={**good_snapshot(), "extra": 1})),
    ],
)
def test_private_schema_violations(mod: Any, make: Any) -> None:
    invalid(mod, make(), "SCHEMA")


# -- nonce, pins, file set, bindings --


@pytest.mark.parametrize(
    "make",
    [
        _transport(_set(("nonce",), OTHER)),
        _summary(_set(("nonce",), OTHER)),
        lambda: build(approved(), invocation_edit=at(3, _set(("nonce",), OTHER))),
    ],
)
def test_nonce_mismatch(mod: Any, make: Any) -> None:
    invalid(mod, make(), "NONCE")


def test_expected_nonce_mismatch(mod: Any) -> None:
    invalid(mod, build(approved()), "NONCE", expected(mod, nonce=OTHER))


@pytest.mark.parametrize(
    "make",
    [
        _summary(_set(("host_sha256",), "0" * 64)),
        _summary(_set(("launcher_sha256",), "1" * 64)),
        lambda: build(approved(), invocation_edit=at(2, _set(("adapter_sha256",), "2" * 64))),
        lambda: build(approved(), invocation_edit=at(1, _set(("launcher_sha256",), "3" * 64))),
    ],
)
def test_pin_mismatch(mod: Any, make: Any) -> None:
    invalid(mod, make(), "PIN")


def test_missing_supplied_file_listed_in_transport(mod: Any) -> None:
    bundle = build(approved())
    del bundle.private["case-3/audit.json"]
    invalid(mod, bundle, "FILESET")


def test_extra_whitelisted_file_not_in_transport(mod: Any) -> None:
    bundle = build(rejected_at_1())
    bundle.private["case-2/local-stdout.bin"] = READY_CRLF
    invalid(mod, bundle, "FILESET")


def test_private_bytes_changed_without_rebinding(mod: Any) -> None:
    bundle = build(approved())
    bundle.private["case-1/local-stdout.bin"] = NORMAL_CRLF.replace(b"NORMAL", b"NORMAX")
    invalid(mod, bundle, "BINDING")


def test_summary_changed_without_rebinding(mod: Any) -> None:
    bundle = build(approved())
    bundle.summary_raw = build(with_sum(approved(), 0, seconds=0.75)).summary_raw
    invalid(mod, bundle, "BINDING")


@pytest.mark.parametrize(
    "edit",
    [
        _set(("private", 0, "bytes"), 1),
        _set(("private", 0, "sha256"), "0" * 64),
        _set(("summary", "bytes"), 1),
        _set(("outcome",), "REJECTED"),
    ],
)
def test_transport_binding_mismatch(mod: Any, edit: Any) -> None:
    invalid(mod, build(approved(), transport_edit=edit), "BINDING")


# -- batch prefix --


def _reject_after_first(summary: dict[str, Any]) -> None:
    summary["cases"][0].update(outcome="REJECTED", rejection="MISMATCH")
    summary["cases"][1] = not_run("TERMINATE")
    summary["cases"][2] = not_run("LAST_CLOSE")
    summary["outcome"] = "REJECTED"


def _swap_first_two(summary: dict[str, Any]) -> None:
    cases = summary["cases"]
    cases[0], cases[1] = cases[1], cases[0]


@pytest.mark.parametrize(
    "make",
    [
        lambda: build(approved(), drop=CASE_3_FILES),
        lambda: build(approved(), drop=CASE_3_FILES[3:]),
        lambda: build(approved(), summary_edit=_reject_after_first),
        lambda: build([rejected_at_1()[0], terminate()]),
        _summary(_set(("cases", 2, "seconds"), 0.0), rejected_at_1),
        _summary(_set(("cases", 0), not_run("NORMAL")), rejected_at_1),
        _summary(_set(("outcome",), "APPROVED"), rejected_at_1),
        _summary(_set(("outcome",), "REJECTED")),
        _summary(_swap_first_two),
    ],
)
def test_batch_prefix_violations(mod: Any, make: Any) -> None:
    invalid(mod, make(), "PREFIX")


# -- invocation, supervision, stdout --


def _append(path: tuple[Any, ...], value: Any) -> Any:
    def edit(record: dict[str, Any]) -> None:
        record[path[0]].append(value)

    return edit


def _reverse_env(record: dict[str, Any]) -> None:
    record["environment_names"].reverse()


def _pop_env(record: dict[str, Any]) -> None:
    record["environment_names"].pop()


@pytest.mark.parametrize(
    "edit",
    [
        at(1, _set(("argv", 4), "print(1)")),
        at(2, _set(("argv", 4), NORMAL_LITERAL)),
        at(1, _append(("argv",), "extra")),
        at(1, _set(("argv", 1), "-E")),
        at(1, _set(("argv", 0), "C:\\other\\python.exe")),
        at(1, _set(("limits", "deadline_seconds"), 60)),
        at(3, _set(("limits", "audit_limit"), 513)),
        at(1, _set(("limits", "extra"), 1)),
        at(1, _reverse_env),
        at(2, _pop_env),
        at(1, _set(("case",), "TERMINATE")),
        at(1, _set(("number",), 2)),
    ],
)
def test_invocation_semantics(mod: Any, edit: Any) -> None:
    invalid(mod, build(approved(), invocation_edit=edit), "INVOCATION")


def test_argv0_mismatch_with_expected(mod: Any) -> None:
    invalid(mod, build(approved()), "INVOCATION", expected(mod, argv0="C:\\other\\python.exe"))


@pytest.mark.parametrize(
    "make",
    [
        lambda: with_sup(approved(), 0, owner_state="HELD"),
        lambda: with_sup(approved(), 0, case="TERMINATE"),
        lambda: with_sup(approved(), 0, exit_code=1),
        lambda: with_sup(approved(), 0, seconds=0.75),
        lambda: with_sup(approved(), 0, terminated=True),
        lambda: with_sup(approved(), 1, total_processes=2),
        lambda: with_sum(approved(), 1, ready=False),
        lambda: [normal(seconds=-1.0), terminate(), last_close()],
        lambda: [normal(ready=True), terminate(), last_close()],
        lambda: [normal(ready_turns=1), terminate(), last_close()],
        lambda: [normal(), terminate(ready_turns=201), last_close()],
    ],
)
def test_supervision_semantics(mod: Any, make: Any) -> None:
    invalid(mod, build(make()), "SUPERVISION")


def _extra_stdout_byte() -> list[dict[str, Any]]:
    cases = approved()
    cases[0]["stdout"] = NORMAL_CRLF + b"x"
    return cases


@pytest.mark.parametrize(
    "make",
    [
        _extra_stdout_byte,
        lambda: [normal(stdout=NORMAL_LF, framing="CRLF"), terminate(), last_close()],
        lambda: [normal(stdout=NORMAL_CRLF, framing="LF"), terminate(), last_close()],
        lambda: [
            normal(stdout=b"MASKGW-NATIVE-CONTROL-NORMAL\r", framing="CRLF"),
            terminate(),
            last_close(),
        ],
        lambda: [normal(), terminate(stdout=NORMAL_CRLF), last_close()],
        lambda: [normal(), terminate(stdout=b"", framing="CRLF"), last_close()],
    ],
)
def test_stdout_and_framing(mod: Any, make: Any) -> None:
    invalid(mod, build(make()), "STDOUT")


# -- snapshot and audit --


@pytest.mark.parametrize(
    "snapshot",
    [
        {**good_snapshot(), "members": 0},
        {**good_snapshot(), "inner_verified": False},
        {**good_snapshot(), "inner_present": False},
        {**good_snapshot(), "total": 3, "active": 3, "members": 3},
        {**good_snapshot(), "active": 2},
        {**good_snapshot(), "total": None},
        {**good_snapshot(), "valid": False},
        None,
    ],
    ids=["members", "verified", "present", "total", "active", "null-total", "declared", "null"],
)
def test_snapshot_recomputed_predicate(mod: Any, snapshot: Any) -> None:
    invalid(mod, build(with_last(snapshot=snapshot)), "SNAPSHOT")


def test_snapshot_invalid_reason_requires_invalid_snapshot(mod: Any) -> None:
    invalid(mod, build(snapshot_invalid(snapshot=good_snapshot())), "SNAPSHOT")


def _audit_append(name: str) -> list[dict[str, Any]]:
    cases = approved()
    cases[2]["audit"]["entries"].append(name)
    return cases


def _audit_set(**changes: Any) -> list[dict[str, Any]]:
    cases = approved()
    cases[2]["audit"].update(changes)
    return cases


@pytest.mark.parametrize(
    "make",
    [
        lambda: _audit_append("TerminateProcess"),
        lambda: _audit_set(limit=511),
        lambda: _audit_set(terminate_calls=1),
        lambda: with_sum(approved(), 2, audit_entries=5),
        lambda: with_sum(approved(), 2, terminate_calls=1),
        lambda: with_sum(approved(), 2, audit_integral=False),
        lambda: with_last(entries=["QueryInformationJobObject"] * 513),
        lambda: with_last(entries=[*CLEAN_ENTRIES, ""]),
        lambda: with_last(entries=[*CLEAN_ENTRIES, "x" * 65]),
    ],
)
def test_audit_semantics(mod: Any, make: Any) -> None:
    invalid(mod, build(make()), "AUDIT")


# -- recomputed verdict contradictions (all bindings recomputed) --


@pytest.mark.parametrize(
    "make",
    [
        lambda: [normal(terminated=True), terminate(), last_close()],
        lambda: [normal(overflow=True), terminate(), last_close()],
        lambda: [normal(signaled=False), terminate(), last_close()],
        lambda: [normal(eof=False), terminate(), last_close()],
        lambda: [normal(total_processes=3), terminate(), last_close()],
        lambda: [normal(total_processes=None), terminate(), last_close()],
        lambda: [normal(exit_code=None), terminate(), last_close()],
        lambda: [normal(exit_code=1), terminate(), last_close()],
        lambda: [normal(reason="DEADLINE"), terminate(), last_close()],
        lambda: [normal(stdout=NORMAL_CRLF + b"x\r\n", framing=None), terminate(), last_close()],
        lambda: [normal(), terminate(exit_code=0), last_close()],
        lambda: [normal(), terminate(reason=None), last_close()],
        lambda: [normal(), terminate(ready=False), last_close()],
        lambda: [normal(), terminate(terminated=False), last_close()],
        lambda: [normal(), terminate(seconds=None), last_close()],
        lambda: [normal(), terminate(), last_close(inner_closed=False)],
        lambda: [normal(), terminate(), last_close(terminated=True)],
        lambda: [normal(), terminate(), last_close(integral=False)],
        lambda: [normal(), terminate(), last_close(entries=TERMINATED_ENTRIES)],
        lambda: [normal(), terminate(), last_close(ready=False)],
        lambda: [normal(exit_code=1, outcome="REJECTED", rejection="DEADLINE")],
        lambda: [normal(outcome="REJECTED", rejection="MISMATCH")],
        lambda: failed_last_close(rejection="DEADLINE"),
        lambda: snapshot_invalid(rejection="MISMATCH"),
    ],
)
def test_rehashed_contradictions(mod: Any, make: Any) -> None:
    invalid(mod, build(make()), "CONTRADICTION")


# -- faults, control and purity --


def test_internal_fault_is_closed_and_silent(mod: Any, capsys: Any, monkeypatch: Any) -> None:
    def broken(_raw: bytes) -> str:
        raise ValueError("secret-detail " + ARGV0)

    monkeypatch.setitem(mod.globals, "_digest", broken)
    assert run(mod, build(approved())) == ("INVALID", "INTERNAL")
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_control_interruption_propagates(mod: Any, monkeypatch: Any) -> None:
    signal = KeyboardInterrupt()

    def interrupted(_raw: bytes) -> str:
        raise signal

    monkeypatch.setitem(mod.globals, "_digest", interrupted)
    with pytest.raises(KeyboardInterrupt) as caught:
        run(mod, build(approved()))
    assert caught.value is signal


def test_no_filesystem_process_or_native_effects(mod: Any, monkeypatch: Any) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("effect attempted")

    for owner, name in (
        (builtins, "open"),
        (os, "open"),
        (os, "stat"),
        (os, "lstat"),
        (os, "listdir"),
        (os, "scandir"),
        (subprocess, "Popen"),
        (ctypes, "WinDLL"),
        (Path, "open"),
        (Path, "stat"),
    ):
        monkeypatch.setattr(owner, name, forbidden)
    assert run(mod, build(approved())) == APPROVED


def test_module_source_is_pure() -> None:
    tree = ast.parse(MODULE.read_bytes())
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported |= {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported <= {"dataclasses", "hashlib", "json", "math", "re"}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names & {"open", "exec", "eval", "compile", "__import__", "print", "input"}
    assert not any(
        isinstance(node, ast.If) and "__main__" in ast.unparse(node.test) for node in ast.walk(tree)
    )


# -- entry snapshot: caller objects are read once, then never again --


def test_inputs_are_captured_once_before_use(mod: Any, monkeypatch: Any) -> None:
    bundle = build(approved())
    record = expected(mod)
    original = dict(bundle.private)
    seen: list[bytes] = []

    def mutating(raw: bytes) -> str:
        if not seen:
            # Mutate the ORIGINAL caller objects during validation.
            bundle.private["case-1/local-stdout.bin"] = b"tampered"
            del bundle.private["case-3/audit.json"]
            bundle.private["case-1/held.json"] = b"{}\n"
            object.__setattr__(record, "nonce", OTHER)
            object.__setattr__(record, "argv0", "C:\\other\\python.exe")
        seen.append(raw)
        return hashlib.sha256(raw).hexdigest()

    monkeypatch.setitem(mod.globals, "_digest", mutating)
    result = mod.verify(record, bundle.summary_raw, bundle.transport_raw, bundle.private)
    assert result == APPROVED  # the captured inputs, not the mutated ones
    assert set(seen) == {bundle.summary_raw, *original.values()}
    assert b"tampered" not in seen
    assert "case-1/held.json" in bundle.private and record.nonce == OTHER


def test_captured_rejected_bundle_is_stable_under_mutation(mod: Any, monkeypatch: Any) -> None:
    bundle = build(rejected_at_1())
    record = expected(mod)
    calls: list[int] = []

    def mutating(raw: bytes) -> str:
        if not calls:
            bundle.private.clear()
            object.__setattr__(record, "argv0", "")
        calls.append(len(raw))
        return hashlib.sha256(raw).hexdigest()

    monkeypatch.setitem(mod.globals, "_digest", mutating)
    result = mod.verify(record, bundle.summary_raw, bundle.transport_raw, bundle.private)
    assert result == REJECTED and bundle.private == {} and len(calls) == 4


def test_oversized_private_count_is_rejected_before_items_are_touched(mod: Any) -> None:
    bundle = build(approved())
    bundle.private = {"x" + str(index): TrapBytes(b"x") for index in range(65)}
    TRAP_CALLS.clear()
    assert run(mod, bundle) == ("INVALID", "CAP")
    assert TRAP_CALLS == []


def test_bounded_count_with_unknown_names_is_a_fileset_error(mod: Any) -> None:
    bundle = build(approved())
    bundle.private = {"x" + str(index): b"x" for index in range(64)}
    assert run(mod, bundle) == ("INVALID", "FILESET")


# -- regressions for review of c833e4c8: native uint32 counter domains (before fix) --

U32 = 1 << 32


def _bad_counts(**changes: Any) -> dict[str, Any]:
    """A snapshot already invalid by members=0 (SNAPSHOT_INVALID path)."""
    return {**good_snapshot(), "valid": False, "members": 0, **changes}


def _rejected_normal(**facts: Any) -> list[dict[str, Any]]:
    return [normal(outcome="REJECTED", rejection="MISMATCH", **facts)]


def _prelaunch() -> list[dict[str, Any]]:
    return [
        normal(
            stdout=b"",
            framing=None,
            outcome="REJECTED",
            rejection="LAUNCH_FAILED",
            reason="LAUNCH_FAILED",
            signaled=False,
            eof=False,
            exit_code=None,
            total_processes=None,
            turns=0,
        )
    ]


@pytest.mark.parametrize(
    "make",
    [
        lambda: with_last(exit_code=-1),
        lambda: with_last(exit_code=U32),
        lambda: _rejected_normal(exit_code=-1),
        lambda: _rejected_normal(exit_code=U32),
        lambda: [normal(), terminate(exit_code=U32, outcome="REJECTED", rejection="MISMATCH")],
        lambda: _rejected_normal(exit_code=1, total_processes=-1),
        lambda: _rejected_normal(exit_code=1, total_processes=U32),
        lambda: snapshot_invalid(snapshot=_bad_counts(total=-1)),
        lambda: snapshot_invalid(snapshot=_bad_counts(total=U32)),
        lambda: snapshot_invalid(snapshot=_bad_counts(active=-1)),
        lambda: snapshot_invalid(snapshot=_bad_counts(active=U32)),
        lambda: snapshot_invalid(snapshot=_bad_counts(members=-1)),
        lambda: snapshot_invalid(snapshot=_bad_counts(members=U32)),
    ],
    ids=[
        "last-exit-minus-one",
        "last-exit-2**32",
        "normal-exit-minus-one",
        "normal-exit-2**32",
        "terminate-exit-2**32",
        "total-minus-one",
        "total-2**32",
        "snapshot-total-minus-one",
        "snapshot-total-2**32",
        "snapshot-active-minus-one",
        "snapshot-active-2**32",
        "snapshot-members-minus-one",
        "snapshot-members-2**32",
    ],
)
def test_counters_outside_the_native_uint32_domain(mod: Any, make: Any) -> None:
    # Coherent bytes with every hash recomputed; the value itself is impossible.
    invalid(mod, build(make()), "SCHEMA")


@pytest.mark.parametrize(
    ("make", "result"),
    [
        (lambda: with_last(exit_code=0xC000013A), APPROVED),
        (lambda: with_last(exit_code=U32 - 1), APPROVED),
        (lambda: _rejected_normal(exit_code=U32 - 1), REJECTED),
        (lambda: _rejected_normal(exit_code=1, total_processes=0), REJECTED),
        (lambda: _rejected_normal(exit_code=1, total_processes=U32 - 1), REJECTED),
        (lambda: snapshot_invalid(snapshot=_bad_counts(total=U32 - 1, active=U32 - 1)), REJECTED),
        (lambda: snapshot_invalid(snapshot=_bad_counts(total=0, active=0)), REJECTED),
        (lambda: snapshot_invalid(snapshot=_bad_counts(total=None, active=None)), REJECTED),
        (_prelaunch, REJECTED),
    ],
    ids=[
        "last-exit-high-bit",
        "last-exit-max",
        "normal-exit-max",
        "total-zero",
        "total-max",
        "snapshot-max",
        "snapshot-zero",
        "snapshot-null-counts",
        "prelaunch-nulls",
    ],
)
def test_counters_inside_the_native_uint32_domain(mod: Any, make: Any, result: Any) -> None:
    assert run(mod, build(make())) == result
