"""Pure runtime observer/protocol tests; no native imports, daemon or Linux load."""

from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import importlib.util
import json
import signal
import subprocess
import sys
import time
import zlib
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from tests.test_linux_as_observer import CID, IMAGE, profile


def load(name: str) -> Any:
    path = Path(__file__).resolve().parents[1] / "docs/poc" / (name + ".py")
    spec = importlib.util.spec_from_file_location("test_" + name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROBE = load("linux_import_probe")
HOST = load("run_linux_imports")
LAB = HOST.load("linux_as_probe")


def import_profile(tmp_path: Path) -> dict[str, Any]:
    info = profile(tmp_path / "unused")
    info["Name"] = "/test-control"
    info["Config"]["Env"] = ["PATH=/usr/local/bin:/usr/bin"]
    info["Config"]["Cmd"] = ["-I", "-B", "-S", "/probe/linux_import_probe.py", "--case", "control"]
    info["Mounts"] = [
        {"Type": "bind", "Source": str(tmp_path / "probe"), "Destination": "/probe", "RW": False},
        {
            "Type": "bind",
            "Source": str(tmp_path / "installed"),
            "Destination": "/installed",
            "RW": False,
        },
    ]
    return info


def validate(info: dict[str, Any], tmp_path: Path) -> None:
    HOST.validate_profile(
        info,
        image=IMAGE,
        task="task",
        source_hash="sha",
        name="test-control",
        case="control",
        probe=tmp_path / "probe",
        installed=tmp_path / "installed",
        expected_env=["PATH=/usr/local/bin:/usr/bin"],
    )


def test_exact_two_readonly_mounts_and_isolated_command(tmp_path):
    validate(import_profile(tmp_path), tmp_path)


@pytest.mark.parametrize(
    "key,value",
    [
        ("Memory", 0),
        ("MemorySwap", -1),
        ("PidsLimit", 0),
        ("Privileged", True),
        ("NetworkMode", "host"),
        ("PidMode", "host"),
        ("ReadonlyRootfs", False),
        ("LogConfig", {"Type": "json-file"}),
    ],
)
def test_profile_drift_rejected(tmp_path, key, value):
    info = import_profile(tmp_path)
    info["HostConfig"][key] = value
    with pytest.raises(HOST.OLD.HostFault):
        validate(info, tmp_path)


def test_mount_and_environment_cannot_expand(tmp_path):
    original = import_profile(tmp_path)
    mutations: tuple[Callable[[dict[str, Any]], Any], ...] = (
        lambda x: x["Mounts"][0].update(RW=True),
        lambda x: x["Mounts"][1].update(Source=str(tmp_path)),
        lambda x: x["Config"].update(Cmd=["-I", "-B", "/probe/linux_import_probe.py"]),
        lambda x: x["Config"].update(Env=["MASKGW_TOKEN=NOT_FORWARDED"]),
    )
    for mutate in mutations:
        info = copy.deepcopy(original)
        mutate(info)
        with pytest.raises(HOST.OLD.HostFault):
            validate(info, tmp_path)


def normal() -> dict[str, Any]:
    return {
        "outcome": "normal",
        "cleanup_confirmed": True,
        "module_inventory": PROBE.pack_inventory(
            [[-1, ["fixture", "fixture", "installed/fixture.py"]]]
        ),
        "events": [
            {"phase": "end", "stage": n, "vm": {"peak": 20 * 1024 * 1024}} for n in range(3)
        ],
    }


@pytest.mark.parametrize("failure", ["MEMORY", "IMPORT", "SIGNAL"])
def test_failure_after_valid_control_is_mismatch_not_as_cause(failure):
    limited = {
        "outcome": "inconclusive",
        "cleanup_confirmed": True,
        "failure": failure,
        "failure_stage": 1,
        "member_returncode": -6 if failure == "SIGNAL" else 72,
    }
    assert HOST.classify_limited(normal(), limited) == "did_not_fit"
    assert HOST.classify_limited({"outcome": "inconclusive"}, limited) == "inconclusive"


def test_fit_requires_all_steps_same_modules_and_peak():
    assert HOST.classify_limited(normal(), normal()) == "fits_as32"
    for change in (
        {
            "module_inventory": PROBE.pack_inventory(
                [[0, ["different", "fixture", "installed/different.py"]]]
            )
        },
        {"cleanup_confirmed": False},
        {"outer_pressure": True},
    ):
        limited = {**normal(), **change}
        assert HOST.classify_limited(normal(), limited) == "inconclusive"
    limited = normal()
    limited["events"][2]["vm"]["peak"] = 32 * 1024 * 1024 + 1
    assert HOST.classify_limited(normal(), limited) == "inconclusive"
    control = normal()
    control["events"] = []
    assert HOST.classify_limited(control, normal()) == "inconclusive"


def test_protocol_handles_coalesced_lines_without_extra_allocation():
    reader = PROBE.LineReader(None, LAB)
    reader.buffer = b'{"phase":"start"}\n{"phase":"end"}\n'
    assert reader.read(time.monotonic() + 1) == {"phase": "start"}
    assert reader.read(time.monotonic() + 1) == {"phase": "end"}
    assert reader.buffer == b""
    reader.buffer = b"x" * 4097
    with pytest.raises(PROBE.ImportFault):
        reader.read(time.monotonic() + 1)


@pytest.mark.parametrize("name", ["mcp", "maskgw.admin.http", "fastapi", "scramp"])
def test_forbidden_import_never_passes_provenance(name):
    with pytest.raises(PROBE.ImportFault):
        PROBE.module_row(name, SimpleNamespace(__file__="/installed/fixture.py"), {})


def test_file_origins_and_fileless_native_generated_modules(monkeypatch):
    class VirtualPath(PurePosixPath):
        def resolve(self) -> VirtualPath:
            return self

    native = SimpleNamespace(__file__="/installed/fixture/native.so")
    monkeypatch.setattr(PROBE, "Path", VirtualPath)
    monkeypatch.setattr(
        PROBE,
        "sys",
        SimpleNamespace(modules={"fixture.native": native}, stdlib_module_names={"os"}),
    )
    owners = {"fixture": "fixture-distribution"}
    assert PROBE.module_row("fixture.native", native, owners)[1] == "fixture-distribution"
    with pytest.raises(PROBE.ImportFault):
        PROBE.module_row("bad", SimpleNamespace(__file__="/elsewhere/bad.py"), owners)
    generated = SimpleNamespace()
    with pytest.raises(PROBE.ImportFault):
        PROBE.module_row("_cython_3_2_8", generated, owners, {})
    row = PROBE.module_row(
        "_cython_3_2_8", generated, owners, {"_cython_3_2_8": ["fixture/native.so"]}
    )
    assert row[2] == "generated-cython/installed/fixture/native.so"


@pytest.fixture
def attached_native(monkeypatch):
    class VirtualPath(PurePosixPath):
        def resolve(self):
            return self

    child = ModuleType("_openssl")
    provider = ModuleType("cryptography.hazmat.bindings._rust")
    provider.__file__ = "/installed/cryptography/hazmat/bindings/_rust.abi3.so"
    provider.__dict__["_openssl"] = child
    modules = {child.__name__: child, provider.__name__: provider}
    monkeypatch.setattr(PROBE, "Path", VirtualPath)
    monkeypatch.setattr(PROBE, "sys", SimpleNamespace(modules=modules, stdlib_module_names=set()))
    return child, provider, modules, {"cryptography": "cryptography"}


def test_native_attachment_requires_same_object_and_verified_origin(attached_native):
    child, _provider, _modules, owners = attached_native
    row = PROBE.module_row("_openssl", child, owners)
    assert row == [
        "_openssl",
        "cryptography",
        "attached-by-identity/installed/cryptography/hazmat/bindings/_rust.abi3.so",
    ]


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "fileless",
        "outside",
        "wrong_path",
        "wrong_owner",
        "unowned",
        "different_object",
        "cache_mismatch",
    ],
)
def test_native_attachment_rejects_missing_evidence(attached_native, fault):
    child, provider, modules, owners = attached_native
    if fault == "missing":
        modules.pop(provider.__name__)
    elif fault == "fileless":
        del provider.__file__
    elif fault == "outside":
        provider.__file__ = "/outside/SECRET.so"
    elif fault == "wrong_path":
        provider.__file__ = "/installed/cryptography/other.so"
    elif fault == "wrong_owner":
        owners["cryptography"] = "other"
    elif fault == "unowned":
        owners.clear()
    elif fault == "different_object":
        provider.__dict__["_openssl"] = ModuleType("_openssl")
    else:
        modules["_openssl"] = ModuleType("_openssl")
    with pytest.raises(PROBE.ImportFault):
        PROBE.module_row("_openssl", child, owners)


@pytest.mark.parametrize("which", ["child", "provider"])
def test_native_attachment_rejects_hostile_subclass_before_attribute_read(attached_native, which):
    child, _provider, modules, owners = attached_native
    reads: list[str] = []

    class Hostile(ModuleType):
        def __getattribute__(self, name):
            reads.append(name)
            raise RuntimeError("SECRET")

    if which == "child":
        child = Hostile("_openssl")
        modules["_openssl"] = child
    else:
        modules["cryptography.hazmat.bindings._rust"] = Hostile("provider")
    with pytest.raises(PROBE.ImportFault):
        PROBE.module_row("_openssl", child, owners)
    assert not reads


def test_native_attachment_uses_identity_not_equality_or_other_attribute(attached_native):
    child, provider, _modules, owners = attached_native
    comparisons: list[object] = []

    class EqualButDifferent:
        def __hash__(self):
            return 0

        def __eq__(self, other):
            comparisons.append(other)
            return True

    provider.__dict__["_openssl"] = EqualButDifferent()
    provider.__dict__["SECRET"] = EqualButDifferent()
    with pytest.raises(PROBE.ImportFault):
        PROBE.module_row("_openssl", child, owners)
    assert not comparisons


def test_native_attachment_diagnostic_does_not_call_module_getattr(attached_native):
    child, provider, _modules, owners = attached_native
    reads: list[str] = []

    def hostile(name):
        reads.append(name)
        raise RuntimeError("SECRET")

    child.__dict__["__getattr__"] = hostile
    provider.__dict__["_openssl"] = ModuleType("_openssl")
    emitted: list[dict[str, Any]] = []
    assert not PROBE.audit_module(
        SimpleNamespace(emit=emitted.append), 1, "_openssl", child, owners, {}
    )
    assert emitted[0]["category"] == "FILELESS_UNATTRIBUTED"
    assert not emitted[0]["has_file"] and not reads
    assert "SECRET" not in json.dumps(emitted)


def test_native_attachment_does_not_admit_other_name_or_override_file_origin(attached_native):
    child, provider, modules, owners = attached_native
    provider.__dict__["_other"] = child
    modules["_other"] = child
    with pytest.raises(PROBE.ImportFault):
        PROBE.module_row("_other", child, owners)
    child.__file__ = "/installed/cryptography/file_backed.py"
    assert PROBE.module_row("_openssl", child, owners) == [
        "_openssl",
        "cryptography",
        "installed/cryptography/file_backed.py",
    ]


@pytest.mark.parametrize("implementation", ["python", "c", None])
def test_binary_psycopg_required(implementation, monkeypatch):
    modules = {"psycopg": SimpleNamespace(pq=SimpleNamespace(__impl__=implementation))}
    monkeypatch.setattr(PROBE, "sys", SimpleNamespace(modules=modules))
    with pytest.raises(PROBE.ImportFault):
        PROBE.native_check()


def test_baseline_harness_origin_is_explicit_and_not_first_delta(monkeypatch):
    class VirtualPath(PurePosixPath):
        def resolve(self) -> VirtualPath:
            return self

    monkeypatch.setattr(PROBE, "Path", VirtualPath)
    monkeypatch.setattr(PROBE, "__file__", "/probe/linux_import_probe.py")
    monkeypatch.setattr(PROBE, "sys", SimpleNamespace(stdlib_module_names={"sys"}, modules={}))
    row = PROBE.module_row("_lab_support", SimpleNamespace(__file__="/probe/linux_as_probe.py"), {})
    assert row == ["_lab_support", "harness", "probe/linux_as_probe.py"]
    source = Path(__file__).resolve().parents[1] / "docs/poc/linux_import_probe.py"
    assert "previous = set(sys.modules)" in source.read_text(encoding="utf-8")


def test_inventory_1500_structured_long_modules_fits_all_caps():
    rows = [
        [
            index % 3,
            [
                f"fixture.long_module_name_{index:04d}",
                "fixture-distribution",
                f"installed/fixture/very_long_subpackage_name/long_module_name_{index:04d}.py",
            ],
        ]
        for index in range(1500)
    ]
    blob = PROBE.pack_inventory(rows)
    assert PROBE.unpack_inventory(blob) == rows
    diagnostic = {
        "case": "control",
        "outcome": "normal",
        "cleanup_confirmed": True,
        "module_inventory": blob,
        "final_inventory": [1],
    }
    raw = PROBE.bounded_report(diagnostic)
    assert len(raw) <= 56 * 1024
    wrapped = {
        "case": "control",
        "container_id": "a" * 64,
        "diagnostic": json.loads(raw),
        "cleanup_confirmed": True,
        "metadata_margin": "x" * 4096,
    }
    assert len(json.dumps(wrapped).encode()) < 64 * 1024


def test_high_entropy_inventory_fails_closed_instead_of_truncating():
    rows = [
        [
            0,
            [
                hashlib.sha256(str(index).encode()).hexdigest(),
                "fixture",
                "installed/" + hashlib.sha512(str(index).encode()).hexdigest(),
            ],
        ]
        for index in range(1500)
    ]
    with pytest.raises(PROBE.ImportFault):
        PROBE.pack_inventory(rows)
    result = {
        "case": "control",
        "outcome": "normal",
        "cleanup_confirmed": True,
        "final_inventory": [1],
        "oversized": "x" * 60000,
    }
    bounded = json.loads(PROBE.bounded_report(result))
    assert bounded["outcome"] == "inconclusive" and bounded["report_limit"]


def test_inventory_decompression_is_bounded_and_rejects_trailing_data():
    blob = PROBE.pack_inventory([[0, ["fixture", "fixture", "installed/fixture.py"]]])
    compressed = base64.b64decode(blob["payload"])
    malformed = {**blob, "payload": base64.b64encode(compressed + b"extra").decode()}
    with pytest.raises(PROBE.ImportFault):
        PROBE.unpack_inventory(malformed)
    bomb = {
        "codec": "zlib-base64",
        "raw_bytes": PROBE.MAX_RAW,
        "payload": base64.b64encode(zlib.compress(b"x" * (PROBE.MAX_RAW + 1))).decode(),
    }
    with pytest.raises(PROBE.ImportFault):
        PROBE.unpack_inventory(bomb)


@pytest.mark.parametrize(
    "name,filename,owners,category",
    [
        ("fastapi", "/installed/fixture.py", {}, "FORBIDDEN"),
        ("fixture", "/elsewhere/fixture.py", {}, "OUTSIDE_ORIGIN"),
        ("fixture", "/installed/fixture.py", {}, "UNOWNED_TOP"),
        ("fixture", None, {}, "FILELESS_UNATTRIBUTED"),
    ],
)
def test_audit_failure_categories_do_not_change_origin_acceptance(
    monkeypatch, name, filename, owners, category
):
    class VirtualPath(PurePosixPath):
        def resolve(self):
            return self

    monkeypatch.setattr(PROBE, "Path", VirtualPath)
    monkeypatch.setattr(PROBE, "sys", SimpleNamespace(modules={}, stdlib_module_names=set()))
    emitted: list[dict[str, Any]] = []
    assert not PROBE.audit_module(
        SimpleNamespace(emit=emitted.append),
        1,
        name,
        SimpleNamespace(__file__=filename),
        owners,
        {},
    )
    assert emitted == [
        {
            "phase": "audit_error",
            "stage": 1,
            "module": name,
            "category": category,
            "has_file": filename is not None,
            "under_installed": bool(filename and filename.startswith("/installed/")),
        }
    ]
    assert "/elsewhere" not in json.dumps(emitted) and "fixture.py" not in json.dumps(emitted)


@pytest.mark.parametrize("name", ["bad\nSECRET", "bad/path", "x" * 201, "", "m\u00f3dulo", None])
def test_invalid_module_name_is_never_reflected(name):
    emitted: list[dict[str, Any]] = []
    module = SimpleNamespace(__file__="/outside/fixture.py")
    assert not PROBE.audit_module(SimpleNamespace(emit=emitted.append), -1, name, module, {}, {})
    assert emitted == [
        {
            "phase": "audit_error",
            "stage": -1,
            "module": None,
            "category": "OTHER",
            "has_file": True,
            "under_installed": False,
        }
    ]


def test_known_stdlib_name_with_hyphen_keeps_frozen_success_row(monkeypatch):
    class VirtualPath(PurePosixPath):
        def resolve(self):
            return self

    monkeypatch.setattr(PROBE, "Path", VirtualPath)
    name = "_sysconfigdata__linux_x86_64-linux-gnu"
    module = SimpleNamespace(__file__="/usr/local/lib/python3.11/" + name + ".py")
    expected = [name, "stdlib", "stdlib/" + name + ".py"]
    assert PROBE.module_row(name, module, {}) == expected
    emitted: list[dict[str, Any]] = []
    assert PROBE.audit_module(SimpleNamespace(emit=emitted.append), 0, name, module, {}, {})
    assert emitted == [{"phase": "module", "stage": 0, "row": expected}]
    assert not PROBE.valid_module_name(name)  # still unsafe for the new error-name field


def test_all_frozen_names_retain_original_acceptance_path(monkeypatch):
    bundle = Path(__file__).resolve().parents[1] / "docs/poc/evidence/linux-imports-20261021.json"
    rows = json.loads(bundle.read_bytes())["decoded_module_inventory"]
    assert len(rows) == 429
    accepted = {row[1][0]: row[1] for row in rows}
    monkeypatch.setattr(PROBE, "module_row", lambda name, *_args: accepted[name])
    emitted: list[dict[str, Any]] = []
    for stage, row in rows:
        assert PROBE.audit_module(SimpleNamespace(emit=emitted.append), stage, row[0], None, {}, {})
        assert emitted[-1]["row"] == row


def test_unexpected_module_attribute_failure_is_closed_other():
    class Hostile:
        def __getattribute__(self, _name):
            raise RuntimeError("SECRET /absolute/path")

    emitted: list[dict[str, Any]] = []
    assert not PROBE.audit_module(
        SimpleNamespace(emit=emitted.append), 0, "fixture", Hostile(), {}, {}
    )
    assert emitted[0]["category"] == "OTHER"
    assert not emitted[0]["has_file"] and not emitted[0]["under_installed"]
    assert "SECRET" not in json.dumps(emitted)


@pytest.mark.parametrize("fail_fallback", [False, True])
def test_emission_failure_never_continues_audit_or_leaks_exception(fail_fallback):
    attempted: list[dict[str, Any]] = []

    def emit(event):
        attempted.append(event)
        if len(attempted) == 1 or fail_fallback:
            raise OSError("SECRET")

    assert not PROBE.audit_module(SimpleNamespace(emit=emit), -1, "sys", None, {}, {})
    assert [event["phase"] for event in attempted] == ["baseline", "audit_error"]
    assert attempted[1]["category"] == "OTHER"
    assert "SECRET" not in json.dumps(attempted)


def test_module_name_boundary_and_null_marker_validation():
    assert PROBE.valid_module_name("a" * 200)
    assert PROBE.valid_module_name("A_9.name")
    event = {**audit_event(-1), "module": None, "category": "OTHER"}
    assert PROBE.valid_audit_error(event, -1)
    assert not PROBE.valid_audit_error({**event, "under_installed": True}, -1)


@pytest.mark.parametrize("bad_stage", [-1, 0])
def test_member_stops_immediately_on_baseline_or_import_audit_failure(monkeypatch, bad_stage):
    monkeypatch.setitem(
        sys.modules, "resource", SimpleNamespace(RLIMIT_AS=9, getrlimit=lambda _: (-1, -1))
    )
    modules: dict[str, Any] = {"baseline_fixture": None}
    monkeypatch.setattr(PROBE, "sys", SimpleNamespace(path=[], modules=modules))
    monkeypatch.setattr(PROBE, "os", SimpleNamespace(getpid=lambda: 7, getppid=lambda: 1))
    monkeypatch.setattr(
        PROBE,
        "Path",
        lambda _path: SimpleNamespace(
            with_name=lambda _name: SimpleNamespace(
                read_bytes=lambda: b'{"owners":{},"generated":{}}'
            )
        ),
    )
    emitted: list[dict[str, Any]] = []
    commands: list[bytes] = []
    lab = SimpleNamespace(
        emit=emitted.append,
        command=commands.append,
        vm_status=lambda: {"threads": 1},
    )
    monkeypatch.setattr(PROBE, "support", lambda: lab)
    monkeypatch.setattr(PROBE, "effects", lambda: {"fds": [0, 1, 2]})
    stages: list[int] = []

    def audit(_lab, stage, _name, _module, _owners, _generated, **_kwargs):
        stages.append(stage)
        return stage != bad_stage

    monkeypatch.setattr(PROBE, "audit_module", audit)
    imported: list[str] = []

    def importing(name):
        imported.append(name)
        modules["new_fixture"] = None

    # Replace the module's reference, not global importlib used by pytest.
    monkeypatch.setattr(PROBE, "importlib", SimpleNamespace(import_module=importing))
    assert PROBE.member() == 75
    assert stages == ([-1] if bad_stage == -1 else [-1, 0])
    assert imported == ([] if bad_stage == -1 else [PROBE.ROOTS[0]])
    assert commands == [b"GO\n"]
    assert not any(event["phase"] in ("end", "verified") for event in emitted)


@pytest.fixture
def isolated_supervisor(monkeypatch):
    """No child, Linux system call or Docker; strict scripted member stream."""
    limits = [-1, -1]
    monkeypatch.setitem(
        sys.modules,
        "resource",
        SimpleNamespace(
            RLIMIT_AS=9,
            getrlimit=lambda _key: tuple(limits),
            setrlimit=lambda _key, value: limits.__setitem__(slice(None), value),
        ),
    )
    monkeypatch.setattr(
        PROBE,
        "sys",
        SimpleNamespace(
            flags=SimpleNamespace(no_site=1, isolated=1),
            executable="not-called",
            version="3.11.17 fixture",
        ),
    )
    monkeypatch.setattr(signal, "signal", lambda *_args: None)
    monkeypatch.setattr(
        PROBE,
        "os",
        SimpleNamespace(
            getpid=lambda: 1,
            getuid=lambda: 65534,
            uname=lambda: SimpleNamespace(release="fixture"),
            confstr=lambda _key: "glibc 2.36",
            environ={"PATH": "/usr/bin"},
        ),
    )
    vm = {"size": 20 * 1024 * 1024, "peak": 20 * 1024 * 1024, "rss": 1, "threads": 1}
    cgroup = {"events": {"max": 0, "oom": 0, "oom_kill": 0}}
    lab = SimpleNamespace(
        MIB=1024 * 1024,
        AS_BYTES=32 * 1024 * 1024,
        _stop=lambda *_args: None,
        read_text=lambda path: (
            "0::/" if path.endswith("cgroup") else "NoNewPrivs:\t1\nCapEff:\t0000000000000000"
        ),
        number_file=lambda path: {
            "memory.max": 192 * 1024 * 1024,
            "memory.swap.max": 0,
            "pids.max": 16,
        }[path.rsplit("/", 1)[1]],
        vm_status=lambda: dict(vm),
        cgroup_sample=lambda: copy.deepcopy(cgroup),
        inventory=sorted,
        send=lambda *_args: None,
        reap=lambda _items: True,
    )
    monkeypatch.setattr(PROBE, "support", lambda: lab)

    def run(events, returncode=75, read_error=None, stopped=False):
        lab.STOP = stopped

        class Process:
            pid = 7
            stdout = object()
            returncode = None

            def wait(self, **_kwargs):
                self.returncode = returncode

        process = Process()
        monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: process)
        ready = {"phase": "ready", "pid": 7, "ppid": 1, "limits": [-1, -1], "vm": vm}

        class Reader:
            def __init__(self, *_args):
                self.events = iter([ready, *events])

            def read(self, _deadline):
                try:
                    return next(self.events)
                except StopIteration:
                    raise (read_error or EOFError()) from None

        monkeypatch.setattr(PROBE, "LineReader", Reader)
        return PROBE.supervisor("control")

    return run


def audit_event(stage: int = 0) -> dict[str, Any]:
    return {
        "phase": "audit_error",
        "stage": stage,
        "module": "fixture.generated",
        "category": "FILELESS_UNATTRIBUTED",
        "has_file": False,
        "under_installed": False,
    }


@pytest.mark.parametrize("baseline", [False, True])
def test_audit_error_is_collected_before_start_and_after_valid_row(isolated_supervisor, baseline):
    events = [] if baseline else [{"phase": "start", "stage": 0}]
    row = ["fixture", "fixture", "installed/fixture.py"]
    events.append(
        {"phase": "baseline", "row": row}
        if baseline
        else {"phase": "module", "stage": 0, "row": row}
    )
    event = audit_event(-1 if baseline else 0)
    terminal = (
        []
        if baseline
        else [
            {
                "phase": "batch_end",
                "stage": 0,
                "examined": 0,
                "details": 0,
                "non_module_total": 0,
                "module_exact_total": 0,
                "absent_total": 0,
                "incomplete": False,
                "anchor": "UNANCHORED",
            }
        ]
    )
    result = isolated_supervisor([*events, event, *terminal])
    assert result["audit_error"] == event and result["member_returncode"] == 75
    assert result["diagnostic_failure"] == "AUDIT_ERROR"
    assert result["outcome"] == "inconclusive" and result["cleanup_confirmed"]
    assert PROBE.unpack_inventory(result["module_inventory"]) == [[-1 if baseline else 0, row]]
    assert HOST.classify_limited(normal(), result) == "inconclusive"
    assert (
        HOST.classify_limited(normal(), {**result, "failure": "MEMORY", "failure_stage": 0})
        == "inconclusive"
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda x: x.update(stage=-1),
        lambda x: x.update(stage=True),
        lambda x: x.update(module="bad/SECRET"),
        lambda x: x.update(module="x" * 201),
        lambda x: x.update(category="SECRET"),
        lambda x: x.update(has_file=1),
        lambda x: x.update(path="/SECRET"),
    ],
)
def test_malformed_audit_event_is_closed_protocol_failure(isolated_supervisor, mutate):
    event = audit_event()
    mutate(event)
    result = isolated_supervisor([{"phase": "start", "stage": 0}, event])
    assert result["diagnostic_failure"] == "PROTOCOL"
    assert "audit_error" not in result and result["member_returncode"] == 75
    assert "SECRET" not in json.dumps(result)


@pytest.mark.parametrize(
    "ending,marker,returncode",
    [
        ({"outcome": "inconclusive", "collection_failed": True}, "COLLECTION_FAILED", 70),
        ({"phase": "SECRET", "payload": "/SECRET"}, "PROTOCOL", 70),
        (None, "EOF", 0),
    ],
)
def test_unexpected_line_and_eof_capture_returncode_without_body(
    isolated_supervisor, ending, marker, returncode
):
    events = [{"phase": "start", "stage": 0}]
    if ending is not None:
        events.append(ending)
    result = isolated_supervisor(events, returncode=returncode)
    assert result["member_returncode"] == returncode
    assert result["diagnostic_failure"] == marker and result["outcome"] == "inconclusive"
    assert "SECRET" not in json.dumps(result) and result["cleanup_confirmed"]


@pytest.mark.parametrize(
    "error,marker", [(TimeoutError(), "TIMEOUT"), (RuntimeError("SECRET"), "DIAGNOSTIC")]
)
def test_read_timeout_and_diagnostic_exception_are_distinct(isolated_supervisor, error, marker):
    result = isolated_supervisor([{"phase": "start", "stage": 0}], read_error=error)
    assert result["diagnostic_failure"] == marker and result["outcome"] == "inconclusive"
    assert result["cleanup_confirmed"] and "SECRET" not in json.dumps(result)


def test_malformed_json_line_is_protocol_failure_with_returncode(isolated_supervisor):
    result = isolated_supervisor([], read_error=PROBE.ImportFault("SECRET"), returncode=70)
    assert result["diagnostic_failure"] == "PROTOCOL" and result["member_returncode"] == 70
    assert result["cleanup_confirmed"] and "SECRET" not in json.dumps(result)


@pytest.mark.parametrize("category", ["SOCKET_FD", "CHILD"])
def test_effects_still_refuses_socket_or_child_with_closed_category(monkeypatch, category):
    monkeypatch.setattr(
        PROBE,
        "os",
        SimpleNamespace(
            listdir=lambda _path: ["0"],
            readlink=lambda _path: (
                "socket:[SECRET]" if category == "SOCKET_FD" else "pipe:[SECRET]"
            ),
            getpid=lambda: 7,
        ),
    )
    monkeypatch.setattr(
        PROBE, "Path", lambda _path: SimpleNamespace(read_text=lambda: "999 SECRET")
    )
    with pytest.raises(PROBE.CheckFault) as caught:
        PROBE.effects()
    assert caught.value.category == category
    emitted: list[dict[str, Any]] = []
    assert PROBE.check_failure(SimpleNamespace(emit=emitted.append), 0, caught.value) == 76
    assert emitted == [{"phase": "check_error", "stage": 0, "category": category, "root": None}]
    assert "SECRET" not in json.dumps(emitted)


def test_native_missing_records_only_closed_root(monkeypatch):
    modules = {"psycopg": SimpleNamespace(pq=SimpleNamespace(__impl__="binary"))}
    monkeypatch.setattr(PROBE, "sys", SimpleNamespace(modules=modules))
    with pytest.raises(PROBE.CheckFault) as caught:
        PROBE.native_check()
    assert (caught.value.category, caught.value.root) == ("NATIVE_MISSING", "pglast")


@pytest.mark.parametrize("stage", [-1, 0, 3])
def test_check_failure_at_baseline_stage_or_final_never_means_as_mismatch(
    isolated_supervisor, stage
):
    events = []
    if stage == 0:
        events.append({"phase": "start", "stage": 0})
    elif stage == 3:
        for index in range(3):
            events.extend(
                [
                    {"phase": "start", "stage": index},
                    {
                        "phase": "end",
                        "stage": index,
                        "vm": {"threads": 1, "peak": 20 * 1024 * 1024},
                    },
                ]
            )
    event = {"phase": "check_error", "stage": stage, "category": "NATIVE_MISSING", "root": "pglast"}
    result = isolated_supervisor([*events, event], returncode=76)
    assert result["diagnostic_failure"] == "CHECK_ERROR" and result["member_returncode"] == 76
    assert result["check_error"] == event and result["cleanup_confirmed"]
    assert (
        HOST.classify_limited(normal(), {**result, "failure": "SIGNAL", "failure_stage": 0})
        == "inconclusive"
    )


@pytest.mark.parametrize(
    "field,value", [("root", "/SECRET"), ("category", "SECRET"), ("stage", True)]
)
def test_invalid_check_failure_never_reflects_body(isolated_supervisor, field, value):
    event = {"phase": "check_error", "stage": 0, "category": "THREADS", "root": None, field: value}
    result = isolated_supervisor([{"phase": "start", "stage": 0}, event], returncode=76)
    assert result["diagnostic_failure"] == "PROTOCOL" and result["member_returncode"] == 76
    assert "check_error" not in result and "SECRET" not in json.dumps(result)


@pytest.mark.parametrize("category,returncode", [("SECRET", 72), ("IMPORT", 72), ("MEMORY", -6)])
def test_invalid_import_error_or_exit_mismatch_cannot_be_classified(
    isolated_supervisor, category, returncode
):
    result = isolated_supervisor(
        [{"phase": "start", "stage": 0}, {"phase": "error", "stage": 0, "category": category}],
        returncode=returncode,
    )
    assert result["diagnostic_failure"] == "PROTOCOL"
    assert result["member_returncode"] == returncode and "SECRET" not in json.dumps(result)
    assert HOST.classify_limited(normal(), result) == "inconclusive"


def test_stopped_reader_is_not_reported_as_deadline_timeout(isolated_supervisor):
    result = isolated_supervisor([], read_error=TimeoutError(), stopped=True)
    assert result["diagnostic_failure"] == "STOPPED" and result["cleanup_confirmed"]


@pytest.mark.parametrize("ending", ["success", "MEMORY", "IMPORT", "OTHER", "SIGNAL"])
def test_supervisor_protocol_sequence_and_eof_are_collected_without_processes(monkeypatch, ending):
    limits = [-1, -1]
    resource = SimpleNamespace(
        RLIMIT_AS=9,
        getrlimit=lambda _key: tuple(limits),
        setrlimit=lambda _key, value: limits.__setitem__(slice(None), value),
    )
    monkeypatch.setitem(sys.modules, "resource", resource)
    monkeypatch.setattr(
        PROBE,
        "sys",
        SimpleNamespace(
            flags=SimpleNamespace(no_site=1, isolated=1),
            executable="not-called",
            version="3.11.17 fixture",
        ),
    )
    monkeypatch.setattr(signal, "signal", lambda *_args: None)
    monkeypatch.setattr(
        PROBE,
        "os",
        SimpleNamespace(
            getpid=lambda: 1,
            getuid=lambda: 65534,
            uname=lambda: SimpleNamespace(release="fixture"),
            confstr=lambda _key: "glibc 2.36",
            environ={"PATH": "/usr/bin"},
        ),
    )
    vm = {"size": 20 * 1024 * 1024, "peak": 20 * 1024 * 1024, "rss": 1, "threads": 1}
    cgroup = {"events": {"max": 0, "oom": 0, "oom_kill": 0}}
    lab = SimpleNamespace(
        MIB=1024 * 1024,
        AS_BYTES=32 * 1024 * 1024,
        _stop=lambda *_args: None,
        read_text=lambda path: (
            "0::/" if path.endswith("cgroup") else "NoNewPrivs:\t1\nCapEff:\t0000000000000000"
        ),
        number_file=lambda path: {
            "memory.max": 192 * 1024 * 1024,
            "memory.swap.max": 0,
            "pids.max": 16,
        }[path.rsplit("/", 1)[1]],
        vm_status=lambda: dict(vm),
        cgroup_sample=lambda: copy.deepcopy(cgroup),
        inventory=sorted,
        send=lambda *_args: None,
        reap=lambda _items: True,
    )
    monkeypatch.setattr(PROBE, "support", lambda: lab)

    class Process:
        pid = 7
        stdout = object()
        returncode: int | None = None

        def wait(self, **_kwargs: Any) -> None:
            self.returncode = {"success": 0, "SIGNAL": -6, "MEMORY": 72, "IMPORT": 73, "OTHER": 74}[
                ending
            ]

    process = Process()
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: process)
    ready = {"phase": "ready", "pid": 7, "ppid": 1, "limits": [32 * 1024 * 1024] * 2, "vm": vm}
    events = [ready]
    if ending == "success":
        for stage in range(3):
            events.extend(
                [
                    {"phase": "start", "stage": stage},
                    {
                        "phase": "module",
                        "stage": stage,
                        "row": [f"fixture{stage}", "fixture", f"installed/fixture{stage}.py"],
                    },
                    {"phase": "end", "stage": stage, "vm": vm, "fds": [0, 1, 2]},
                ]
            )
        events.append({"phase": "verified", "psycopg_impl": "binary", "native": {}})
    else:
        events.append({"phase": "start", "stage": 0})
        if ending != "SIGNAL":
            events.append({"phase": "error", "stage": 0, "category": ending})

    class Reader:
        def __init__(self, *_args: Any) -> None:
            self.events = iter(events)

        def read(self, _deadline: float) -> Any:
            try:
                return next(self.events)
            except StopIteration:
                raise EOFError from None

    monkeypatch.setattr(PROBE, "LineReader", Reader)
    result = PROBE.supervisor("limited")
    assert result["cleanup_confirmed"] and result["final_inventory"] == [1]
    if ending == "success":
        assert result["outcome"] == "normal"
        assert len(PROBE.unpack_inventory(result["module_inventory"])) == 3
    else:
        assert result["outcome"] == "inconclusive"
        assert result["failure"] == ending and result["failure_stage"] == 0
        expected = "inconclusive" if ending == "OTHER" else "did_not_fit"
        assert HOST.classify_limited(normal(), result) == expected


@pytest.mark.parametrize("watchdog_error", [False, True])
@pytest.mark.parametrize("save_failure", [False, True])
def test_profile_drift_removed_even_if_watchdog_close_fails(
    tmp_path, monkeypatch, watchdog_error, save_failure
):
    calls: list[str] = []

    class Watchdog:
        def __init__(self, *_args: Any) -> None:
            self.container_id = None
            self.fired = SimpleNamespace(is_set=lambda: False)

        def start(self):
            return None

        def close(self):
            if watchdog_error:
                raise HOST.OLD.HostFault("WATCHDOG_CLEANUP")

    observer = HOST.Observer.__new__(HOST.Observer)
    observer.preflight_passed = True  # explicit fake admission for lifecycle tests only
    observer.docker, observer.image, observer.root = "not-called", IMAGE, tmp_path
    observer.task, observer.source_hash = "task", "sha"
    observer.probe, observer.installed = tmp_path / "probe", tmp_path / "installed"
    observer.expected_env = ["PATH=/usr/local/bin:/usr/bin"]
    observer.total_written = 0
    observer.watchdog = Watchdog()
    original_save = observer.save

    def save(name: str, data: Any) -> None:
        if save_failure and name == "control.json":
            raise HOST.OLD.HostFault("ARTIFACT_LIMIT")
        original_save(name, data)

    monkeypatch.setattr(observer, "save", save)
    monkeypatch.setattr(HOST.OLD, "Watchdog", Watchdog)

    async def cli(*args: str, **_kwargs: Any) -> tuple[int, bytes]:
        calls.append(args[0])
        return (0, CID.encode()) if args[0] == "create" else (0, b"")

    async def inspect(_target: str) -> dict[str, Any]:
        pending = json.loads((tmp_path / "pending.json").read_bytes())
        assert pending["id"] == CID
        info = import_profile(tmp_path)
        info["Name"] = "/maskgw-imports-task-control"
        info["HostConfig"]["Memory"] = 0
        info["State"] = {"Running": False, "Pid": 0}
        return info

    monkeypatch.setattr(observer, "cli", cli)
    monkeypatch.setattr(observer, "inspect", inspect)
    if save_failure:
        with pytest.raises(HOST.OLD.HostFault):
            asyncio.run(observer.case("control"))
        assert "start" not in calls and "rm" in calls
        assert observer.watchdog.container_id is None
        return
    result = asyncio.run(observer.case("control"))
    assert "start" not in calls and "rm" in calls
    assert result["container_cleanup_confirmed"]
    assert result["cleanup_confirmed"] is not watchdog_error
