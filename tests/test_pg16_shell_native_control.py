"""Fake-owner tests for the private benign native control runner.

No real WinDLL, kernel object, process, thread or loop. The pinned caller,
adapter and backend sources are read by SHA into private namespaces; only the
runner's own TEMP/EVIDENCE/_owner_class and the caller copy's seams are
replaced. Paths are redirected to tmp_path. No .venv, pyvenv.cfg or binary read.
"""

import ast
import ctypes
import functools
import hashlib
import json
import os
import runpy
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "docs/poc/pg16_shell_native_control.py"
NONCE = "0123456789abcdef0123456789abcdef"
OTHER = "fedcba9876543210fedcba9876543210"
PID = 4242
NORMAL = b"MASKGW-NATIVE-CONTROL-NORMAL"
READY = b"MASKGW-NATIVE-CONTROL-READY"
CASES = ("NORMAL", "TERMINATE", "LAST_CLOSE")


class Signal(BaseException):
    """A fictitious control interruption (never an ordinary Exception)."""


class Return:
    """A planned result that replaces the fake method body."""

    def __init__(self, value: Any) -> None:
        self.value = value


class World:
    def __init__(self, error: Any, private: Path) -> None:
        self.error = error
        self.private = private
        self.owners: list[Any] = []
        self.calls: list[tuple[str, str]] = []
        self.plan: dict[Any, Any] = {}
        self.chunks: dict[str, list[bytes]] = {
            "NORMAL": [NORMAL + b"\r\n"],
            "TERMINATE": [READY + b"\r\n"],
            "LAST_CLOSE": [READY + b"\r\n"],
        }
        self.lives = {"NORMAL": False, "TERMINATE": True, "LAST_CLOSE": True}
        self.exit = {"NORMAL": 0, "TERMINATE": 0, "LAST_CLOSE": 0}
        self.terminate_exit = 1
        self.kill_on_close = True
        self.total = 1
        self.now = 1000.0
        self.step = 0.01
        self.ticks = 0
        self.special: dict[int, Any] = {}
        self.pins: list[int] = []
        self.armed = False
        self.post_io: list[str] = []

    def tick(self) -> Any:
        self.ticks += 1
        if self.ticks in self.special:
            return self.special[self.ticks]
        self.now += self.step
        return self.now


class FakeOwner:
    """Backend-shaped public surface; never a handle, a kernel or a process."""

    def __init__(self, world: World, case: str, request: Any) -> None:
        self.world, self.case, self.request = world, case, request
        self.state = "NEW"
        self.eof = False
        self.signaled = False
        self.ledger: Any = {}
        self.inner_verified: Any = None
        self.inner_closed: Any = False
        self._audit: Any = ()
        self._audit_valid: Any = True
        self.audit_reads: list[tuple[str, str]] = []
        self.alive = False
        self.code: Any = None
        self.pending: list[bytes] = []
        self.counts: dict[str, int] = {}
        world.owners.append(self)

    @property
    def audit(self) -> Any:
        self.audit_reads.append(("audit", self.state))
        return self._audit

    @property
    def audit_valid(self) -> Any:
        self.audit_reads.append(("audit_valid", self.state))
        return self._audit_valid

    def _gate(self, method: str) -> Any:
        self.world.calls.append((self.case, method))
        count = self.counts[method] = self.counts.get(method, 0) + 1
        plan = self.world.plan
        action = plan.get((self.case, method, count), plan.get((self.case, method)))
        return action(self) if action is not None else None

    def _note(self, name: str) -> None:
        if self.case == "LAST_CLOSE":
            self._audit = (*self._audit, name)

    def setup(self) -> Any:
        planned = self._gate("setup")
        if isinstance(planned, Return):
            return planned.value
        assert self.state == "NEW"
        number = CASES.index(self.case) + 1
        assert (self.world.private / f"case-{number}" / "invocation.json").is_file()
        self.ledger = {"job": 0x104}
        if self.case == "LAST_CLOSE":
            self.ledger["inner"] = 0x108
            self._note("CreateJobObjectW")
        self.state = "READY"
        return None

    def start(self) -> Any:
        planned = self._gate("start")
        if isinstance(planned, Return):
            return planned.value
        assert self.state == "READY"
        self.pending = list(self.world.chunks[self.case])
        self.alive = self.world.lives[self.case]
        self.code = None if self.alive else self.world.exit[self.case]
        if self.case == "LAST_CLOSE":
            self.inner_verified = True
            self._note("CreateProcessW")
            self._note("ResumeThread")
        self.state = "RUNNING"
        return None

    def read(self) -> Any:
        planned = self._gate("read")
        if isinstance(planned, Return):
            return planned.value
        assert self.state == "RUNNING"
        if self.pending:
            return self.pending.pop(0)
        if not self.alive:
            self.eof = True
        return b""

    def wait(self, milliseconds: int) -> Any:
        planned = self._gate("wait")
        if isinstance(planned, Return):
            return planned.value
        assert self.state == "RUNNING" and milliseconds == 50
        self.signaled = not self.alive
        return self.signaled

    def accounting(self) -> Any:
        planned = self._gate("accounting")
        if isinstance(planned, Return):
            return planned.value
        return self.world.total, 1 if self.alive else 0

    def members(self) -> Any:
        planned = self._gate("members")
        if isinstance(planned, Return):
            return planned.value
        return (PID,) if self.alive else ()

    def exit_code(self) -> Any:
        planned = self._gate("exit_code")
        if isinstance(planned, Return):
            return planned.value
        assert self.signaled
        return self.code

    def terminate(self) -> Any:
        planned = self._gate("terminate")
        if isinstance(planned, Return):
            return planned.value
        if self.state != "RUNNING":
            raise self.world.error("WIN32_STATE")
        self._note("TerminateJobObject")
        if self.alive:
            self.alive, self.code = False, self.world.terminate_exit
        return None

    def close_inner(self) -> Any:
        planned = self._gate("close_inner")
        if isinstance(planned, Return):
            return planned.value
        assert self.state == "RUNNING" and self.case == "LAST_CLOSE"
        self._note("CloseHandle")
        del self.ledger["inner"]
        self.inner_closed = True
        if self.world.kill_on_close and self.alive:
            self.alive, self.code = False, 0
        return None

    def close(self) -> Any:
        planned = self._gate("close")
        if isinstance(planned, Return):
            return planned.value
        if self.state not in ("SETUP_FAILED", "READY", "LAUNCH_FAILED", "RUNNING"):
            raise self.world.error("WIN32_HELD" if self.state == "HELD" else "WIN32_STATE")
        if self.state == "RUNNING" and (self.alive or not self.eof):
            raise self.world.error("WIN32_NOT_QUIESCENT")
        self.state = "CLOSED"
        return None


# -- planned actions -------------------------------------------------------------


def held(owner: Any) -> None:
    owner.state = "HELD"
    raise owner.world.error("WIN32_HELD")


def failed(state: str, code: str) -> Any:
    def action(owner: Any) -> None:
        owner.state = state
        raise owner.world.error(code)

    return action


def raising(error: BaseException) -> Any:
    def action(_owner: Any) -> None:
        raise error

    return action


def returning(value: Any) -> Any:
    def action(_owner: Any) -> Return:
        return Return(value)

    return action


def mutate(**values: Any) -> Any:
    def action(owner: Any) -> None:
        for name, value in values.items():
            setattr(owner, name, value)

    return action


def drop_inner(owner: Any) -> None:
    owner.ledger.pop("inner")


def drop_ledger(owner: Any) -> None:
    del owner.ledger


def over_budget(owner: Any) -> None:
    owner.world.now += 60.0


# -- fixture -------------------------------------------------------------------------


def runtime() -> Any:
    flags = SimpleNamespace(isolated=1, dont_write_bytecode=1, optimize=0)
    return SimpleNamespace(
        platform="win32", version_info=(3, 11, 3), maxsize=(1 << 63) - 1, flags=flags
    )


def no_runtime_read(real: Any) -> Any:
    def guard(self: Path, *args: Any, **kwargs: Any) -> Any:
        if ".venv" in self.parts:
            raise AssertionError("runtime read attempted")
        return real(self, *args, **kwargs)

    return guard


def recorder(world: World, name: str, real: Any) -> Any:
    def spy(*args: Any, **kwargs: Any) -> Any:
        if world.armed:
            world.post_io.append(name)
        return real(*args, **kwargs)

    return spy


@pytest.fixture
def lab(tmp_path: Path, monkeypatch: Any) -> Any:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("native, subprocess or thread effect attempted")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(threading.Thread, "start", forbidden)
    for name in ("open", "lstat", "stat"):
        monkeypatch.setattr(Path, name, no_runtime_read(getattr(Path, name)))
    module = runpy.run_path(str(MODULE))
    glob = module["run"].__globals__
    host, adapter, loaded = glob["_load"]()
    temp, evidence = tmp_path / "temp", tmp_path / "evidence"
    temp.mkdir()
    evidence.mkdir()
    private = temp / ("maskgw-pg16-native-control-v1-" + NONCE)
    world = World(loaded["Win32Error"], private)
    environment = {
        name: "fictitious-value-" + str(index) + "-q7z"
        for index, name in enumerate(host["ENVIRONMENT_NAMES"])
    }

    def owner_class(_loaded: Any, name: str) -> Any:
        return functools.partial(FakeOwner, world, name)

    # Seams of the private copies only; the accepted files are untouched.
    monkeypatch.setitem(glob, "TEMP", temp)
    monkeypatch.setitem(glob, "EVIDENCE", evidence)
    monkeypatch.setitem(glob, "_owner_class", owner_class)
    monkeypatch.setitem(host, "_environ", lambda: dict(environment))
    monkeypatch.setitem(host, "_monotonic", world.tick)
    monkeypatch.setitem(host, "_sleep", lambda _seconds: None)
    monkeypatch.setitem(host, "_launcher_pin", lambda: world.pins.append(len(world.owners)))
    monkeypatch.setitem(host, "sys", runtime())
    return SimpleNamespace(
        module=module,
        glob=glob,
        host=host,
        adapter=adapter,
        loaded=loaded,
        world=world,
        environment=environment,
        temp=temp,
        evidence=evidence,
        private=private,
        public=evidence / ("pg16-native-control-" + NONCE[:12]),
    )


def run(lab: Any, nonce: Any = NONCE) -> Any:
    return lab.glob["run"](nonce)


def refused(lab: Any, code: str, nonce: Any = NONCE) -> Any:
    with pytest.raises(lab.glob["RunError"]) as caught:
        run(lab, nonce)
    assert caught.value.args == (code,)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    return caught.value


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def owner(lab: Any, case: str) -> Any:
    return next(item for item in lab.world.owners if item.case == case)


def committed(lab: Any) -> Any:
    """Parsed committed transport, or None when no final transport exists."""
    final = lab.public / "transport.json"
    return json.loads(final.read_bytes()) if final.is_file() else None


def private_json(lab: Any, name: str) -> Any:
    return json.loads((lab.private / name).read_bytes())


def outcomes(result: Any) -> list[Any]:
    return [case["outcome"] for case in result["cases"]]


def spy_io(lab: Any, monkeypatch: Any) -> None:
    """Records every filesystem call made once lab.world.armed is set."""
    for name in ("open", "lstat", "stat", "mkdir", "iterdir", "exists", "unlink", "rmdir"):
        monkeypatch.setattr(Path, name, recorder(lab.world, "Path." + name, getattr(Path, name)))
    for name in ("open", "stat", "lstat", "mkdir", "listdir", "scandir", "remove", "unlink"):
        monkeypatch.setattr(os, name, recorder(lab.world, "os." + name, getattr(os, name)))
    for name in ("rmdir", "replace", "fsync"):
        monkeypatch.setattr(os, name, recorder(lab.world, "os." + name, getattr(os, name)))


# -- sources, purity and identity ----------------------------------------------------


def test_import_defines_only_and_has_no_entry_point(monkeypatch: Any) -> None:
    source = MODULE.read_bytes()

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("read at import")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "lstat", forbidden)
    module = runpy.run_path(str(MODULE))
    assert module["_SOURCES"] == {} and module["_LIVE"] == []
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {
        (node.value.id, node.attr)
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
    }
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "__name__" not in names
    assert imported == {"hashlib", "os", "Path", "re", "stat", "subprocess"}
    assert {attr for base, attr in attributes if base == "subprocess"} == {"list2cmdline"}
    assert {attr for base, attr in attributes if base == "os"} == {"rename"}
    assert ("sys", "argv") not in attributes


def test_full_pins_and_single_backend_identity(lab: Any) -> None:
    glob, loaded, backend = lab.glob, lab.loaded, lab.loaded["backend"]
    assert glob["HOST"][1] == "dfcc4ed6be3ea8ab47b7a38ca8a9d4bfa00b3c75cda41c365be3dd5b1aa3dac7"
    assert glob["ADAPTER"][1] == "eaebedd6ac36602ba30cb51a4c30a2a93737f1127c23cdc4ebb8ae8cf9246407"
    assert glob["BACKEND_SHA"] == lab.adapter["BACKEND_SHA"]
    for relative, digest in (glob["HOST"], glob["ADAPTER"]):
        assert sha((REPO / relative).read_bytes()) == digest
    assert loaded["Win32Error"] is backend["Win32Error"]
    assert loaded["Request"] is backend["Request"]
    assert issubclass(loaded["NestedJobOwner"], backend["Owner"])
    real = lab.module["_owner_class"]
    assert real(loaded, "LAST_CLOSE") is loaded["NestedJobOwner"]
    assert real(loaded, "NORMAL") is backend["Owner"]
    assert real(loaded, "TERMINATE") is backend["Owner"]
    assert lab.adapter["AUDIT_LIMIT"] == 512


def test_caller_loader_unused_and_limits_unchanged(lab: Any, monkeypatch: Any) -> None:
    def forbidden(*_args: Any) -> Any:
        raise AssertionError("second backend copy")

    monkeypatch.setitem(lab.host, "_load_backend", forbidden)
    result = run(lab)
    assert result["outcome"] == "APPROVED"
    host = lab.host
    assert (host["DEADLINE_SECONDS"], host["CLEANUP_SECONDS"]) == (60.0, 10.0)
    assert (host["MAX_TURNS"], host["CLEANUP_TURNS"], host["RETAIN_BYTES"]) == (1200, 200, 1024)
    assert host["_LIVE"] == [] and host["_HELD_REASONS"] == []
    requests = [item.request for item in lab.world.owners]
    assert all(type(request) is lab.loaded["Request"] for request in requests)


def test_source_pin_mismatch_refused(tmp_path: Path, monkeypatch: Any) -> None:
    module = runpy.run_path(str(MODULE))
    glob = module["run"].__globals__
    monkeypatch.setitem(glob, "TEMP", tmp_path)
    monkeypatch.setitem(glob, "EVIDENCE", tmp_path)
    monkeypatch.setitem(glob, "ADAPTER", (glob["ADAPTER"][0], "0" * 64))
    with pytest.raises(glob["RunError"]) as caught:
        glob["run"](NONCE)
    assert caught.value.args == ("CONTROL_SOURCE",) and caught.value.__context__ is None
    assert list(tmp_path.iterdir()) == [] and glob["_SOURCES"] == {}


@pytest.mark.parametrize(
    "nonce",
    [None, 7, NONCE.upper(), NONCE[:-1], NONCE + "0", "g" * 32, NONCE + "\n", NONCE.encode()],
)
def test_malformed_nonce_is_refused_before_any_artifact(lab: Any, nonce: Any) -> None:
    refused(lab, "CONTROL_NONCE", nonce)
    assert list(lab.temp.iterdir()) == [] and list(lab.evidence.iterdir()) == []
    assert lab.world.owners == []


@pytest.mark.parametrize("occupied", ["private", "public"])
def test_occupied_area_is_refused_before_any_artifact(lab: Any, occupied: str) -> None:
    getattr(lab, occupied).mkdir()
    before = sorted(lab.temp.rglob("*")) + sorted(lab.evidence.rglob("*"))
    refused(lab, "CONTROL_CONSUMED")
    assert sorted(lab.temp.rglob("*")) + sorted(lab.evidence.rglob("*")) == before
    assert lab.world.owners == [] and lab.world.pins == []


# -- happy path, transport and persistence -------------------------------------------


def test_three_cases_publish_bound_transport(lab: Any) -> None:
    result = run(lab)
    assert result["outcome"] == "APPROVED" and outcomes(result) == ["APPROVED"] * 3
    assert lab.glob["_LIVE"] == [] and all(item.state == "CLOSED" for item in lab.world.owners)
    assert lab.world.pins == [0, 1, 2]  # launcher pinned before each owner exists
    assert sorted(path.name for path in lab.public.iterdir()) == ["summary.json", "transport.json"]
    summary_raw = (lab.public / "summary.json").read_bytes()
    assert result == json.loads(summary_raw)
    transport = committed(lab)
    assert transport["summary"] == {
        "name": "summary.json",
        "bytes": len(summary_raw),
        "sha256": sha(summary_raw),
    }
    on_disk = {
        path.relative_to(lab.private).as_posix(): path.read_bytes()
        for path in lab.private.rglob("*")
        if path.is_file()
    }
    assert [entry["name"] for entry in transport["private"]] == sorted(on_disk)
    for entry in transport["private"]:
        assert entry["bytes"] == len(on_disk[entry["name"]])
        assert entry["sha256"] == sha(on_disk[entry["name"]])
    assert {name.split("/")[1] for name in on_disk if name.startswith("case-3/")} == {
        "invocation.json",
        "supervision.json",
        "local-stdout.bin",
        "snapshot.json",
        "audit.json",
    }
    normal, terminate, last = result["cases"]
    assert (normal["framing"], normal["exit_code"], normal["terminated"]) == ("CRLF", 0, False)
    assert (terminate["ready"], terminate["exit_code"], terminate["terminated"]) == (True, 1, True)
    nested = owner(lab, "LAST_CLOSE")
    assert nested.audit_reads == [("audit", "CLOSED"), ("audit_valid", "CLOSED")]
    audit = json.loads(on_disk["case-3/audit.json"])
    assert audit["entries"] == list(nested._audit) and audit["integral"] is True
    assert audit["terminate_calls"] == 0 and audit["limit"] == 512
    assert last["inner_closed"] is True and last["audit_integral"] is True
    assert last["terminate_calls"] == 0 and last["audit_entries"] == len(nested._audit)
    assert json.loads(on_disk["case-3/snapshot.json"])["snapshot"]["valid"] is True


def test_no_environment_value_is_written_and_argv_is_fixed(lab: Any) -> None:
    run(lab)
    blobs = [path.read_bytes() for path in lab.temp.rglob("*") if path.is_file()]
    blobs += [path.read_bytes() for path in lab.evidence.rglob("*") if path.is_file()]
    for value in lab.environment.values():
        assert all(value.encode() not in blob for blob in blobs)
    literals = (lab.glob["NORMAL"], lab.glob["SLEEP"], lab.glob["SLEEP"])
    for number, literal in enumerate(literals, 1):
        invocation = private_json(lab, f"case-{number}/invocation.json")
        assert invocation["argv"][1:] == ["-I", "-B", "-c", literal]
        assert invocation["environment_names"] == list(lab.environment)
    request = lab.world.owners[0].request
    assert request.environment == tuple(lab.environment.items())


def test_first_rejection_stops_and_raw_precedes_public(lab: Any, monkeypatch: Any) -> None:
    lab.world.chunks["NORMAL"] = [NORMAL + b"\r\nextra\r\n"]
    order: list[Path] = []
    real = lab.host["write_new"]

    def logged(path: Path, raw: bytes) -> Any:
        order.append(path)
        return real(path, raw)

    monkeypatch.setitem(lab.host, "write_new", logged)
    result = run(lab)
    assert result["outcome"] == "REJECTED"
    assert outcomes(result) == ["REJECTED", "NOT_RUN", "NOT_RUN"]
    assert result["cases"][0]["rejection"] == "MISMATCH"
    not_run = dict.fromkeys(lab.glob["CASE_KEYS"])
    assert result["cases"][1] == {**not_run, "case": "TERMINATE", "outcome": "NOT_RUN"}
    assert [item.case for item in lab.world.owners] == ["NORMAL"] and lab.glob["_LIVE"] == []
    private = [path for path in order if lab.private in path.parents]
    assert {path.name for path in private} == {
        "invocation.json",
        "supervision.json",
        "local-stdout.bin",
    }
    first_public = order.index(lab.public / "summary.json")
    assert all(order.index(path) < first_public for path in private)
    assert committed(lab) is not None


# -- per-case verdicts -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "outcome", "rejection"),
    [
        ("lf", "APPROVED", None),
        ("exit-one", "REJECTED", "MISMATCH"),
        ("extra", "REJECTED", "MISMATCH"),
        ("silent", "REJECTED", "MISMATCH"),
        ("tree", "REJECTED", "TREE_UNPROVEN"),
        ("overflow", "REJECTED", "OUTPUT_OVERFLOW"),
    ],
)
def test_normal_case_verdicts(lab: Any, label: str, outcome: str, rejection: Any) -> None:
    world = lab.world
    if label == "lf":
        world.chunks["NORMAL"] = [NORMAL + b"\n"]
    elif label == "exit-one":
        world.exit["NORMAL"] = 1
    elif label == "extra":
        world.chunks["NORMAL"] = [NORMAL + b"\n", b"x"]
    elif label == "silent":
        world.chunks["NORMAL"] = []
    elif label == "tree":
        world.total = 3
    else:
        world.chunks["NORMAL"] = [b"x" * 1025]
    first = run(lab)["cases"][0]
    assert (first["outcome"], first["rejection"]) == (outcome, rejection)
    assert owner(lab, "NORMAL").state == "CLOSED" and lab.glob["_LIVE"] == []
    if label == "lf":
        assert first["framing"] == "LF"
    assert committed(lab) is not None


@pytest.mark.parametrize(
    ("label", "outcome", "rejection"),
    [
        ("split", "APPROVED", None),
        ("absent", "REJECTED", "READY_MISSING"),
        ("slow", "REJECTED", "READY_MISSING"),
        ("extra", "REJECTED", "READY_MISMATCH"),
        ("trailing", "REJECTED", "MISMATCH"),
        ("early-exit", "REJECTED", "READY_EARLY_EXIT"),
        ("exit", "REJECTED", "MISMATCH"),
    ],
)
def test_terminate_case_verdicts_never_leave_a_running_tree(
    lab: Any, label: str, outcome: str, rejection: Any
) -> None:
    world = lab.world
    if label == "split":
        world.chunks["TERMINATE"] = [READY[:10], READY[10:] + b"\n"]
    elif label == "absent":
        world.chunks["TERMINATE"] = []
    elif label == "slow":
        world.chunks["TERMINATE"] = []
        world.step = 1.0
    elif label == "extra":
        world.chunks["TERMINATE"] = [READY + b"!\r\n"]
    elif label == "trailing":
        world.chunks["TERMINATE"] = [READY + b"\r\n", b"late\r\n"]
    elif label == "early-exit":
        world.chunks["TERMINATE"], world.lives["TERMINATE"] = [], False
    else:
        world.terminate_exit = 9
    second = run(lab)["cases"][1]
    assert (second["outcome"], second["rejection"]) == (outcome, rejection)
    child = owner(lab, "TERMINATE")
    assert child.state == "CLOSED" and child.alive is False and lab.glob["_LIVE"] == []
    assert ("TERMINATE", "terminate") in world.calls and second["terminated"] is True
    supervision = private_json(lab, "case-2/supervision.json")
    if label == "split":
        assert supervision["ready_turns"] == 2 and second["framing"] == "LF"
        assert (lab.private / "case-2/local-stdout.bin").read_bytes() == READY + b"\n"
    if label == "absent":
        assert supervision["ready_turns"] == 200 and supervision["turns"] >= 1
    if label == "early-exit":
        assert supervision["ready_turns"] == 1 and supervision["signaled"] is True
    assert committed(lab) is not None


@pytest.mark.parametrize(
    ("label", "key", "action", "rejection"),
    [
        ("no-kill", None, None, "FAILED_LAST_CLOSE"),
        ("audit-invalid", ("LAST_CLOSE", "close"), mutate(_audit_valid=False), "AUDIT_INVALID"),
        ("audit-truthy", ("LAST_CLOSE", "close"), mutate(_audit_valid=1), "AUDIT_INVALID"),
        ("audit-list", ("LAST_CLOSE", "close"), mutate(_audit=["CloseHandle"]), "AUDIT_INVALID"),
        (
            "audit-overflowed",
            ("LAST_CLOSE", "close"),
            mutate(_audit=("QueryInformationJobObject",) * 512, _audit_valid=False),
            "AUDIT_INVALID",
        ),
        (
            "audit-too-long",
            ("LAST_CLOSE", "close"),
            mutate(_audit=("QueryInformationJobObject",) * 513),
            "AUDIT_INVALID",
        ),
        ("snapshot-empty", ("LAST_CLOSE", "members", 1), returning(()), "SNAPSHOT_INVALID"),
        (
            "snapshot-truthy",
            ("LAST_CLOSE", "accounting", 1),
            returning((True, True)),
            "SNAPSHOT_INVALID",
        ),
        ("inner-missing", ("LAST_CLOSE", "accounting", 1), drop_inner, "SNAPSHOT_INVALID"),
        (
            "unverified",
            ("LAST_CLOSE", "accounting", 1),
            mutate(inner_verified=1),
            "SNAPSHOT_INVALID",
        ),
        (
            "close-inner-noop",
            ("LAST_CLOSE", "close_inner"),
            returning(None),
            "CLOSE_INNER_FAILED",
        ),
    ],
)
def test_last_close_rejections_use_one_audit_capture(
    lab: Any, label: str, key: Any, action: Any, rejection: str
) -> None:
    if key is None:
        lab.world.kill_on_close = False
    else:
        lab.world.plan[key] = action
    third = run(lab)["cases"][2]
    assert (third["outcome"], third["rejection"]) == ("REJECTED", rejection)
    nested = owner(lab, "LAST_CLOSE")
    assert nested.state == "CLOSED" and nested.alive is False and lab.glob["_LIVE"] == []
    assert nested.audit_reads == [("audit", "CLOSED"), ("audit_valid", "CLOSED")]
    audit = private_json(lab, "case-3/audit.json")
    assert audit["integral"] is third["audit_integral"]
    assert len(audit["entries"]) == third["audit_entries"]
    assert audit["terminate_calls"] == third["terminate_calls"]
    if label == "no-kill":
        assert third["inner_closed"] is True and third["terminate_calls"] == 1
        assert "TerminateJobObject" in audit["entries"]
    if label == "audit-overflowed":
        assert third["audit_entries"] == 512 and audit["limit"] == 512
    if label in ("audit-list", "audit-too-long"):
        assert audit["entries"] == [] and audit["integral"] is False
    assert committed(lab) is not None


# -- budget and launch -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "rejection"),
    [("nan", "CALLER_CLOCK"), ("int", "CALLER_CLOCK"), ("over-budget", "DEADLINE")],
)
def test_bad_clock_or_spent_budget_prevents_start(lab: Any, label: str, rejection: str) -> None:
    if label == "nan":
        lab.world.special[2] = float("nan")
    elif label == "int":
        lab.world.special[2] = 5
    else:
        lab.world.plan[("NORMAL", "setup")] = over_budget
    first = run(lab)["cases"][0]
    assert (first["outcome"], first["rejection"]) == ("REJECTED", rejection)
    assert ("NORMAL", "start") not in lab.world.calls
    assert owner(lab, "NORMAL").state == "CLOSED" and lab.glob["_LIVE"] == []


def test_invalid_initial_clock_refuses_before_any_owner(lab: Any) -> None:
    lab.world.special[1] = "1.0"
    refused(lab, "CONTROL_CLOCK")
    assert lab.world.owners == [] and lab.glob["_LIVE"] == []
    assert (lab.private / "case-1/invocation.json").is_file()
    assert not lab.public.exists()


@pytest.mark.parametrize(
    ("method", "action"),
    [
        ("setup", failed("SETUP_FAILED", "WIN32_REQUEST")),
        ("start", failed("LAUNCH_FAILED", "WIN32_CREATE")),
    ],
)
def test_clean_launch_failure_is_closed_rejection(lab: Any, method: str, action: Any) -> None:
    lab.world.plan[("NORMAL", method)] = action
    first = run(lab)["cases"][0]
    assert (first["outcome"], first["rejection"]) == ("REJECTED", "LAUNCH_FAILED")
    assert owner(lab, "NORMAL").state == "CLOSED" and lab.glob["_LIVE"] == []
    assert committed(lab) is not None


@pytest.mark.parametrize(
    ("method", "action"),
    [("start", held), ("setup", returning(None)), ("start", returning(None))],
)
def test_unproven_launch_is_held_and_retained(lab: Any, method: str, action: Any) -> None:
    lab.world.plan[("NORMAL", method)] = action
    refused(lab, "CONTROL_HELD")
    retained = owner(lab, "NORMAL")
    assert lab.glob["_LIVE"] == [retained] and retained.state != "CLOSED"
    assert private_json(lab, "case-1/held.json")["held"] == "LAUNCH"
    assert not lab.public.exists()


# -- HELD, interruption and exception preservation ---------------------------------------


def test_held_owner_is_retained_never_published_and_blocks_next_run(lab: Any) -> None:
    lab.world.plan[("TERMINATE", "close")] = held
    refused(lab, "CONTROL_HELD")
    retained = owner(lab, "TERMINATE")
    assert lab.glob["_LIVE"] == [retained] and retained.state == "HELD"
    record = private_json(lab, "case-2/held.json")
    assert record["kind"] == "MASKGW_PG16_NATIVE_CONTROL_HELD_V1"
    assert record["held"] == "CLOSE" and record["case"] == "TERMINATE"
    assert record["owner_state"] == "HELD"
    assert (lab.private / "case-2/local-stdout.bin").read_bytes() == READY + b"\r\n"
    assert not lab.public.exists() and committed(lab) is None
    assert lab.host["_HELD_REASONS"] == []
    before = sorted(lab.temp.rglob("*"))
    refused(lab, "CONTROL_RETAINED", OTHER)
    assert sorted(lab.temp.rglob("*")) == before and len(lab.world.owners) == 2


def test_failed_read_during_ready_is_held_after_one_terminate(lab: Any) -> None:
    lab.world.plan[("TERMINATE", "read", 1)] = raising(ValueError("secret-detail"))
    refused(lab, "CONTROL_HELD")
    retained = owner(lab, "TERMINATE")
    assert lab.glob["_LIVE"] == [retained]
    assert lab.world.calls.count(("TERMINATE", "terminate")) == 1 and retained.alive is False
    record = private_json(lab, "case-2/held.json")
    assert record["held"] == "READY" and record["terminated"] is True
    assert b"secret-detail" not in (lab.private / "case-2/held.json").read_bytes()


def test_unexpected_exception_is_closed_internal_and_retained(lab: Any) -> None:
    lab.world.plan[("LAST_CLOSE", "members", 1)] = drop_ledger
    refused(lab, "CONTROL_INTERNAL")
    retained = owner(lab, "LAST_CLOSE")
    assert lab.glob["_LIVE"] == [retained] and retained.alive is False
    record = private_json(lab, "case-3/held.json")
    assert record["held"] == "INTERNAL" and record["audit"]["partial"] is True
    assert not lab.public.exists()


@pytest.mark.parametrize(
    ("case", "method", "count"),
    [
        ("NORMAL", "setup", 1),
        ("NORMAL", "start", 1),
        ("TERMINATE", "read", 1),
        ("TERMINATE", "wait", 3),
        ("LAST_CLOSE", "accounting", 1),
        ("LAST_CLOSE", "close_inner", 1),
        ("LAST_CLOSE", "exit_code", 1),
        ("NORMAL", "close", 1),
    ],
)
def test_control_interruption_propagates_by_identity_and_retains(
    lab: Any, case: str, method: str, count: int
) -> None:
    signal = Signal("fictitious")
    lab.world.plan[(case, method, count)] = raising(signal)
    with pytest.raises(Signal) as caught:
        run(lab)
    assert caught.value is signal
    retained = owner(lab, case)
    assert lab.glob["_LIVE"] == [retained] and retained.state != "CLOSED"
    number = CASES.index(case) + 1
    assert private_json(lab, f"case-{number}/held.json")["held"] == "INTERRUPTED"
    if retained.state == "RUNNING":
        assert (case, "terminate") in lab.world.calls and retained.alive is False
    assert not lab.public.exists() and committed(lab) is None


def test_second_interruption_during_cleanup_never_replaces_first(
    lab: Any, monkeypatch: Any
) -> None:
    first, second, third = Signal("first"), Signal("second"), Signal("third")
    lab.world.plan[("TERMINATE", "read", 1)] = raising(first)
    lab.world.plan[("TERMINATE", "terminate")] = raising(second)
    real = lab.host["write_new"]

    def flaky(path: Path, raw: bytes) -> Any:
        if path.name == "held.json":
            raise third
        return real(path, raw)

    monkeypatch.setitem(lab.host, "write_new", flaky)
    with pytest.raises(Signal) as caught:
        run(lab)
    assert caught.value is first
    assert lab.glob["_LIVE"] == [owner(lab, "TERMINATE")]
    assert (lab.private / "case-2/local-stdout.bin").is_file()
    assert not (lab.private / "case-2/held.json").exists() and not lab.public.exists()


def test_interruption_while_recording_a_held_owner_is_not_swallowed(
    lab: Any, monkeypatch: Any
) -> None:
    lab.world.plan[("TERMINATE", "close")] = held
    signal = Signal("while-recording")
    real = lab.host["write_new"]

    def flaky(path: Path, raw: bytes) -> Any:
        if path.name == "held.json":
            raise signal
        return real(path, raw)

    monkeypatch.setitem(lab.host, "write_new", flaky)
    with pytest.raises(Signal) as caught:
        run(lab)
    assert caught.value is signal
    assert lab.glob["_LIVE"] == [owner(lab, "TERMINATE")]
    assert (lab.private / "case-2/local-stdout.bin").is_file() and not lab.public.exists()


def test_interruption_after_proven_close_does_not_retain_the_owner(lab: Any) -> None:
    signal = Signal("after-close")

    def close_then_interrupt(item: Any) -> None:
        item.state = "CLOSED"
        raise signal

    lab.world.plan[("NORMAL", "close")] = close_then_interrupt
    with pytest.raises(Signal) as caught:
        run(lab)
    assert caught.value is signal
    assert lab.glob["_LIVE"] == [] and not lab.public.exists()


# -- publication boundary ---------------------------------------------------------------------


@pytest.mark.parametrize("target", ["summary.json", "transport.json.next"])
def test_interruption_during_publication_retains_no_owner(
    lab: Any, monkeypatch: Any, target: str
) -> None:
    signal = Signal("publication")
    real = lab.host["write_new"]

    def flaky(path: Path, raw: bytes) -> Any:
        if path.parent == lab.public and path.name == target:
            raise signal
        return real(path, raw)

    monkeypatch.setitem(lab.host, "write_new", flaky)
    with pytest.raises(Signal) as caught:
        run(lab)
    assert caught.value is signal
    assert lab.glob["_LIVE"] == [] and all(item.state == "CLOSED" for item in lab.world.owners)
    assert lab.public.is_dir()  # consumed partial: never deleted or retried
    assert committed(lab) is None
    refused(lab, "CONTROL_CONSUMED")


def test_ordinary_publication_failure_leaves_partial(lab: Any, monkeypatch: Any) -> None:
    real = lab.host["write_new"]

    def flaky(path: Path, raw: bytes) -> Any:
        if path.name == "transport.json.next":
            raise OSError("fictitious")
        return real(path, raw)

    monkeypatch.setitem(lab.host, "write_new", flaky)
    refused(lab, "CONTROL_PERSISTENCE")
    assert sorted(path.name for path in lab.public.iterdir()) == ["summary.json"]
    assert committed(lab) is None and lab.glob["_LIVE"] == []


def test_rename_that_performs_then_raises_is_indeterminate_without_later_io(
    lab: Any, monkeypatch: Any
) -> None:
    spy_io(lab, monkeypatch)
    real_rename = os.rename

    def performing(source: Any, target: Any) -> None:
        real_rename(source, target)
        lab.world.armed = True
        raise OSError("fictitious late failure")

    monkeypatch.setattr(os, "rename", performing)
    caught: Any = None
    try:
        run(lab)
    except lab.glob["RunError"] as error:
        caught = error
    observed, lab.world.armed = list(lab.world.post_io), False
    assert observed == []
    assert caught is not None and caught.args == ("CONTROL_COMMIT_INDETERMINATE",)
    assert caught.__cause__ is None and caught.__context__ is None
    assert committed(lab) is not None  # the effect happened: never reported as absent
    assert lab.glob["_LIVE"] == []


def test_interrupted_rename_propagates_by_identity_without_later_io(
    lab: Any, monkeypatch: Any
) -> None:
    spy_io(lab, monkeypatch)
    signal = Signal("rename")

    def interrupted(_source: Any, _target: Any) -> None:
        lab.world.armed = True
        raise signal

    monkeypatch.setattr(os, "rename", interrupted)
    caught: Any = None
    try:
        run(lab)
    except Signal as error:
        caught = error
    observed, lab.world.armed = list(lab.world.post_io), False
    assert observed == [] and caught is signal
    assert lab.glob["_LIVE"] == []
    assert (lab.public / "transport.json.next").is_file() and committed(lab) is None


def test_successful_commit_has_no_later_io(lab: Any, monkeypatch: Any) -> None:
    spy_io(lab, monkeypatch)
    real_rename = os.rename

    def committing(source: Any, target: Any) -> None:
        real_rename(source, target)
        lab.world.armed = True

    monkeypatch.setattr(os, "rename", committing)
    result = run(lab)
    observed, lab.world.armed = list(lab.world.post_io), False
    assert observed == []
    assert result == json.loads((lab.public / "summary.json").read_bytes())
    assert committed(lab)["outcome"] == "APPROVED"


# -- regressions for the review of runner 0dfcd0f4 (written before any fix) -------------


def failing_retention(error: BaseException) -> Any:
    """Replaces the runner's retention helper: fails at its boundary, outside
    the helper's own try blocks (allocation failure or a new control)."""

    def retain(*_args: Any) -> None:
        raise error

    return retain


@pytest.mark.parametrize("reading", ["nan", "backward", "int"])
def test_invalid_final_clock_refuses_even_with_expected_reason(lab: Any, reading: str) -> None:
    world = lab.world

    def poison_next_reading(_owner: Any) -> None:
        # The next reading after the real fake close is the final one.
        values = {"nan": float("nan"), "backward": world.now - 5.0, "int": 5}
        world.special[world.ticks + 1] = values[reading]

    world.plan[("TERMINATE", "close")] = poison_next_reading
    result = run(lab)
    second = result["cases"][1]
    assert (second["outcome"], second["rejection"]) == ("REJECTED", "CALLER_CLOCK")
    assert second["seconds"] is None
    assert result["outcome"] == "REJECTED"
    assert outcomes(result) == ["APPROVED", "REJECTED", "NOT_RUN"]
    child = owner(lab, "TERMINATE")
    assert child.state == "CLOSED" and lab.glob["_LIVE"] == []
    # Cleanup proof and private bytes are preserved.
    supervision = private_json(lab, "case-2/supervision.json")
    assert supervision["terminated"] is True and supervision["eof"] is True
    assert supervision["signaled"] is True and supervision["seconds"] is None
    assert (lab.private / "case-2/local-stdout.bin").read_bytes() == READY + b"\r\n"
    assert committed(lab) is not None


@pytest.mark.parametrize("arrival", ["terminate", "held-record"])
def test_control_during_cleanup_after_ordinary_failure_propagates(
    lab: Any, monkeypatch: Any, arrival: str
) -> None:
    signal = Signal("during-cleanup")
    lab.world.plan[("LAST_CLOSE", "members", 1)] = drop_ledger  # ordinary AttributeError
    if arrival == "terminate":
        lab.world.plan[("LAST_CLOSE", "terminate")] = raising(signal)
    else:
        real = lab.host["write_new"]

        def flaky(path: Path, raw: bytes) -> Any:
            if path.name == "held.json":
                raise signal
            return real(path, raw)

        monkeypatch.setitem(lab.host, "write_new", flaky)
    with pytest.raises(Signal) as caught:
        run(lab)
    assert caught.value is signal
    retained = owner(lab, "LAST_CLOSE")
    assert lab.glob["_LIVE"] == [retained] and retained.state != "CLOSED"
    assert (lab.private / "case-3/local-stdout.bin").is_file()
    assert not lab.public.exists() and committed(lab) is None


@pytest.mark.parametrize("failure", ["memory", "control"])
def test_retention_failure_never_replaces_original_control(
    lab: Any, monkeypatch: Any, failure: str
) -> None:
    original = Signal("original")
    replacement = MemoryError() if failure == "memory" else Signal("replacement")
    lab.world.plan[("NORMAL", "start", 1)] = raising(original)
    monkeypatch.setitem(lab.glob, "_retain", failing_retention(replacement))
    with pytest.raises(Signal) as caught:
        run(lab)
    assert caught.value is original
    retained = owner(lab, "NORMAL")
    assert lab.glob["_LIVE"] == [retained] and retained.state == "READY"
    assert not lab.public.exists() and committed(lab) is None


def test_retention_failure_after_proven_close_still_releases(lab: Any, monkeypatch: Any) -> None:
    original = Signal("after-close")

    def close_then_interrupt(item: Any) -> None:
        item.state = "CLOSED"
        raise original

    lab.world.plan[("NORMAL", "close")] = close_then_interrupt
    monkeypatch.setitem(lab.glob, "_retain", failing_retention(MemoryError()))
    with pytest.raises(Signal) as caught:
        run(lab)
    assert caught.value is original
    assert lab.glob["_LIVE"] == [] and not lab.public.exists()


@pytest.mark.parametrize("failure", ["memory", "control"])
def test_retention_failure_after_ordinary_failure(lab: Any, monkeypatch: Any, failure: str) -> None:
    signal = Signal("retention")
    lab.world.plan[("LAST_CLOSE", "members", 1)] = drop_ledger  # ordinary AttributeError
    replacement = MemoryError() if failure == "memory" else signal
    monkeypatch.setitem(lab.glob, "_retain", failing_retention(replacement))
    if failure == "memory":
        refused(lab, "CONTROL_INTERNAL")
    else:
        with pytest.raises(Signal) as caught:
            run(lab)
        assert caught.value is signal
    retained = owner(lab, "LAST_CLOSE")
    assert lab.glob["_LIVE"] == [retained] and retained.state != "CLOSED"
    assert not lab.public.exists() and committed(lab) is None


# -- regressions for reentrant retention in runner 31fd2ead (before any fix) -------------


def case_two_writes(lab: Any, monkeypatch: Any, signal: Any = None) -> list[str]:
    """Records every write attempt in case-2; optionally interrupts held.json."""
    attempts: list[str] = []
    real = lab.host["write_new"]

    def logged(path: Path, raw: bytes) -> Any:
        if path.parent.name == "case-2":
            attempts.append(path.name)
        if signal is not None and path.name == "held.json":
            raise signal
        return real(path, raw)

    monkeypatch.setitem(lab.host, "write_new", logged)
    return attempts


def test_reentrant_retention_after_record_control_terminates_once(
    lab: Any, monkeypatch: Any
) -> None:
    signal = Signal("held-record")
    lab.world.plan[("TERMINATE", "read", 1)] = raising(ValueError("secret-detail"))
    attempts = case_two_writes(lab, monkeypatch, signal)
    with pytest.raises(Signal) as caught:
        run(lab)
    assert caught.value is signal
    # The emergency retention phase attempts at most one guarded terminate.
    assert lab.world.calls.count(("TERMINATE", "terminate")) == 1
    retained = owner(lab, "TERMINATE")
    assert lab.glob["_LIVE"] == [retained] and retained.state == "RUNNING"
    assert attempts == ["invocation.json", "held.json", "local-stdout.bin"]  # never retried
    assert not (lab.private / "case-2/held.json").exists()
    assert not lab.public.exists() and committed(lab) is None


def test_control_during_first_retention_terminate_is_not_retried(
    lab: Any, monkeypatch: Any
) -> None:
    signal = Signal("retention-terminate")
    lab.world.plan[("TERMINATE", "read", 1)] = raising(ValueError("secret-detail"))
    lab.world.plan[("TERMINATE", "terminate")] = raising(signal)
    attempts = case_two_writes(lab, monkeypatch)
    with pytest.raises(Signal) as caught:
        run(lab)
    assert caught.value is signal
    assert lab.world.calls.count(("TERMINATE", "terminate")) == 1
    retained = owner(lab, "TERMINATE")
    assert lab.glob["_LIVE"] == [retained] and retained.state == "RUNNING"
    assert attempts == ["invocation.json", "held.json", "local-stdout.bin"]
    record = private_json(lab, "case-2/held.json")
    assert record["held"] == "READY" and record["terminated"] is False
    assert not lab.public.exists() and committed(lab) is None


def test_supervisor_terminate_is_separate_from_the_retention_terminate(lab: Any) -> None:
    def fail_after_terminate(item: Any) -> None:
        if ("TERMINATE", "terminate") in item.world.calls:
            raise ValueError("secret-detail")

    # The supervisor's decision terminate happens first; the read after it
    # fails, so the emergency retention phase still gets its own single attempt.
    lab.world.plan[("TERMINATE", "read")] = fail_after_terminate
    refused(lab, "CONTROL_HELD")
    assert lab.world.calls.count(("TERMINATE", "terminate")) == 2
    retained = owner(lab, "TERMINATE")
    assert lab.glob["_LIVE"] == [retained]
    record = private_json(lab, "case-2/held.json")
    assert record["held"] == "READ" and record["terminated"] is True
    assert not lab.public.exists() and committed(lab) is None
