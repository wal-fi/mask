"""External observer with fake CLI/watchdogs and tiny local artifacts only."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_linux_as_observer import CID, IMAGE
from tests.test_linux_imports_probe import import_profile, load
from tests.test_loaded_memory_supervisor import FakeIO as SupervisorIO
from tests.test_loaded_memory_supervisor import run as supervisor_run
from tests.test_loaded_memory_supervisor import vm as supervisor_vm

H = load("run_linux_loaded")


def profile(tmp_path: Path, case: str = "control", expected: str = "-") -> dict[str, Any]:
    info = import_profile(tmp_path)
    info["Name"] = "/loaded-" + case
    info["Config"]["Labels"]["maskgw.task"] = "loaded-task"
    info["Config"]["Labels"]["maskgw.source-sha256"] = "b" * 64
    info["Config"]["Cmd"] = [
        "-I",
        "-B",
        "-S",
        "/probe/linux_loaded_probe.py",
        "--case",
        case,
        "--expected",
        expected,
    ]
    return info


def validate(info: Any, tmp_path: Path, case: str = "control", expected: str = "-") -> None:
    H.validate_profile(
        info,
        image=IMAGE,
        task="loaded-task",
        source_hash="b" * 64,
        name="loaded-" + case,
        case=case,
        expected=expected,
        probe=tmp_path / "probe",
        installed=tmp_path / "installed",
        expected_env=info["Config"]["Env"],
    )


@pytest.mark.parametrize("case", ["control", "private", "shared"])
def test_direct_profile_exact_new_argv(tmp_path, case):
    expected = "-" if case == "control" else "a" * 64
    validate(profile(tmp_path, case, expected), tmp_path, case, expected)


@pytest.mark.parametrize(
    "key,value",
    [
        ("Memory", 0),
        ("MemorySwap", -1),
        ("PidsLimit", True),
        ("NanoCpus", 0),
        ("ReadonlyRootfs", False),
        ("NetworkMode", "host"),
        ("CapAdd", ["SYS_ADMIN"]),
        ("Privileged", True),
        ("Devices", [{"PathOnHost": "x"}]),
        ("Binds", ["x"]),
        ("PortBindings", {"x": []}),
        ("Init", True),
        ("LogConfig", {"Type": "json-file"}),
    ],
)
def test_profile_drift_refused(tmp_path, key, value):
    info = profile(tmp_path)
    info["HostConfig"][key] = value
    with pytest.raises(H.OLD.HostFault):
        validate(info, tmp_path)


@pytest.mark.parametrize(
    "mode", ["old-command", "wrong-digest", "extra-flag", "old-label", "extra-mount"]
)
def test_legacy_or_forged_profile_never_rewritten_to_pass(tmp_path, mode):
    info = profile(tmp_path, "private", "a" * 64)
    if mode == "old-command":
        info["Config"]["Cmd"] = [
            "-I",
            "-B",
            "-S",
            "/probe/linux_import_probe.py",
            "--case",
            "limited",
        ]
    elif mode == "wrong-digest":
        info["Config"]["Cmd"][-1] = "c" * 64
    elif mode == "extra-flag":
        info["Config"]["Cmd"].append("--anything")
    elif mode == "old-label":
        info["Config"]["Labels"]["maskgw.source-sha256"] = "old-import-sha"
    else:
        info["Mounts"].append(dict(info["Mounts"][0]))
    before = copy.deepcopy(info)
    with pytest.raises(H.OLD.HostFault):
        validate(info, tmp_path, "private", "a" * 64)
    assert info == before


def realistic_report(case: str) -> dict[str, Any]:
    report, _io = supervisor_run(case)
    # The earlier coordinator fake omits parent-only setup details. Model the
    # actual backend's four-key startup here, without editing that frozen test.
    report["startup"]["inherited_as"] = [-1, -1]
    report["startup"]["startup_cgroup"]["procs"] = [1]
    report["startup"]["startup_cgroup"]["pids_current"] = 1
    report["final_cgroup"]["procs"] = [1]
    report["final_cgroup"]["pids_current"] = 1
    result: dict[str, Any] = report
    return result


def reports() -> tuple[dict[str, Any], str]:
    control = realistic_report("control")
    return control, control["inventory_digest"]


@pytest.mark.parametrize("case", ["control", "private", "shared"])
def test_report_accepts_real_fake_supervisor_and_recomputes_digest(case):
    control, digest = reports()
    report = control if case == "control" else realistic_report(case)
    assert H.validate_report(report, case, "-" if case == "control" else digest) == digest


@pytest.mark.parametrize(
    "mode",
    [
        "extra",
        "bool-rc",
        "bool-id",
        "claim",
        "digest",
        "failure",
        "fd",
        "limits",
        "counter",
        "case",
        "forged-positive",
    ],
)
def test_report_forgery_refused(mode):
    report, _digest = reports()
    if mode == "extra":
        report["imports_fit_as32"] = True
    elif mode == "bool-rc":
        report["member_returncode"] = False
    elif mode == "bool-id":
        report["final_inventory"] = [True]
    elif mode == "claim":
        report["total_memory_contained"] = True
    elif mode == "digest":
        report["inventory_digest"] = "a" * 64
    elif mode == "failure":
        report["failure"] = {"stage": "held", "category": "MEMORY"}
    elif mode == "fd":
        report["observations"][0]["fds"]["fds"].append(8)
    elif mode == "limits":
        report["observations"][0]["limits"] = [128 << 20] * 2
    elif mode == "counter":
        report["final_cgroup"]["events"]["oom_kill"] = 1
    elif mode == "case":
        report["case"] = "private"
    else:
        report = {
            "profile": "loaded-as128",
            "case": "control",
            "outcome": "control_ok",
            "cleanup_confirmed": True,
            "final_inventory": [1],
            "total_memory_contained": False,
        }
    with pytest.raises(H.OLD.HostFault):
        H.validate_report(report, "control", "-")


def test_limited_inventory_mismatch_stops_without_exported_control_digest():
    _control, digest = reports()
    report = realistic_report("private")
    rows = H.PROBE.unpack_inventory(report["module_inventory"])
    rows[0][1][1] = "other-owner"
    report["module_inventory"] = H.PROBE.pack_inventory(rows)
    with pytest.raises(H.OLD.HostFault):
        H.validate_report(report, "private", digest)


def test_fallback_and_missing_report_are_not_positive():
    fallback = {
        "profile": "loaded-as128",
        "outcome": "inconclusive",
        "report_limit": True,
        "total_memory_contained": False,
    }
    with pytest.raises(H.OLD.HostFault, match=r"^REPORT_LIMIT$"):
        H.validate_report(fallback, "control", "-")
    with pytest.raises(H.OLD.HostFault, match=r"^REPORT_MISSING$"):
        H.decode_report(b"")


@pytest.mark.parametrize(
    "raw",
    [b'{"x":NaN}\n', b'{"x":1,"x":2}\n', b"{}\n{}\n", b"{}", b"x" * 65537],
    ids=["nan", "duplicate", "extra", "partial", "large"],
)
def test_decode_report_is_closed_and_bounded(raw):
    with pytest.raises(H.OLD.HostFault):
        H.decode_report(raw)


def test_no_legacy_case_algorithm_in_class_mro():
    assert H.Observer.__bases__ == (object,)
    assert H.Observer.case is not H.IMPORTS.Observer.case
    assert H.Observer.run is not H.IMPORTS.Observer.run
    assert H.Observer.check is not H.IMPORTS.Observer.check


def test_raw_artifact_accounted_immutable_and_written_before_validation(tmp_path):
    observer = H.Observer.__new__(H.Observer)
    observer.root, observer.total_written, observer.raw_hashes = tmp_path, 0, {}
    raw = b'{"profile":"loaded-as128"}\n'
    result = observer.save_raw("control", raw)
    assert (tmp_path / result["file"]).read_bytes() == raw
    assert result["bytes"] == len(raw) and result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert observer.total_written == len(raw)
    with pytest.raises(H.OLD.HostFault):
        observer.save_raw("control", raw)


class Watchdog:
    def __init__(self, *_args: Any) -> None:
        self.container_id = None
        self.started = self.closed = False
        self.fired = SimpleNamespace(is_set=lambda: False)

    def start(self) -> None:
        self.started = True

    def close(self) -> None:
        self.closed = True


def fake_observer(tmp_path: Path) -> Any:
    observer = H.Observer.__new__(H.Observer)
    observer.root, observer.docker, observer.image = tmp_path, "unused-docker", IMAGE
    observer.task, observer.source_hash = "loaded-task", "b" * 64
    observer.probe, observer.installed = tmp_path / "probe", tmp_path / "installed"
    observer.probe.mkdir()
    observer.installed.mkdir()
    (observer.probe / "runtime.json").write_bytes(b"{}")
    observer.runtime_hash = hashlib.sha256(b"{}").hexdigest()
    observer.originals, observer.inventory = {}, {}
    observer.prepared = {"launchers_allowlist": []}
    observer.total_written = 0
    observer.raw_hashes, observer.used_cases, observer.grant = {}, set(), None
    observer.running = observer.started = observer.preflight_passed = False
    observer.watchdog, observer.expected_env = Watchdog(), None
    return observer


async def fake_sleep(data: Any, delay: float) -> None:
    data.now += delay


@pytest.fixture
def simulated(tmp_path, monkeypatch):
    observer = fake_observer(tmp_path)
    data = SimpleNamespace(
        observer=observer,
        now=0.0,
        calls=[],
        created=[],
        removed=[],
        current=None,
        report_hook=None,
        version=(
            0,
            json.dumps({"Server": {"Version": "29.7.2", "Os": "linux", "Arch": "amd64"}}).encode(),
        ),
        ps=b"",
        create_timeout=False,
        foreign=False,
        exit_code=0,
        oom=False,
        integrity_calls=0,
        raw_override=None,
    )
    monkeypatch.setattr(H.OLD, "Watchdog", Watchdog)
    monkeypatch.setattr(H, "time", SimpleNamespace(monotonic=lambda: data.now))
    monkeypatch.setattr(H.IMPORTS, "time", SimpleNamespace(monotonic=lambda: data.now))
    monkeypatch.setattr(H.PREP, "verify_tree", lambda *_args: {})

    async def cli(*args, **kwargs):
        data.calls.append((args, kwargs))
        command = args[0]
        if command == "version":
            if isinstance(data.version, BaseException):
                raise data.version
            return data.version
        if command == "create":
            case = args[args.index("--case") + 1]
            expected = args[args.index("--expected") + 1]
            data.current = {
                "case": case,
                "expected": expected,
                "name": args[args.index("--name") + 1],
            }
            data.created.append(data.current)
            if data.create_timeout:
                raise TimeoutError
            return 0, (CID + "\n").encode()
        if command == "start":
            assert observer.raw_hashes.get(data.current["case"]) is None
            assert observer.watchdog.container_id == CID
            report = realistic_report(data.current["case"])
            if data.report_hook:
                report = data.report_hook(report, data)
            raw = data.raw_override
            if raw is None:
                raw = json.dumps(report, separators=(",", ":")).encode() + b"\n"
            return 0, raw
        if command == "ps":
            if "--filter" in args:
                return 0, CID.encode() if data.current else b""
            return 0, data.ps
        if command == "rm":
            assert args[1] == CID
            data.removed.append(data.current["case"])
            data.current = None
            return 0, b""
        if command == "kill":
            raise AssertionError("no kill is needed in these exited-container fakes")
        raise AssertionError("unexpected-cli")

    async def inspect(target):
        if target == IMAGE:
            return {
                "Os": "linux",
                "Architecture": "amd64",
                "Config": {"Env": profile(tmp_path)["Config"]["Env"]},
            }
        assert target == CID and data.current
        current = data.current
        result = profile(tmp_path, current["case"], current["expected"])
        result["Name"] = "/" + current["name"]
        result["State"] = {
            "Running": False,
            "Pid": 0,
            "ExitCode": data.exit_code,
            "OOMKilled": data.oom,
        }
        if data.foreign:
            result["Config"]["Labels"]["maskgw.source-sha256"] = "old-import-sha"
        return result

    monkeypatch.setattr(observer, "cli", cli)
    monkeypatch.setattr(observer, "inspect", inspect)
    monkeypatch.setattr(H.IMPORTS, "asyncio", SimpleNamespace(sleep=partial(fake_sleep, data)))
    return data


def test_full_fake_lot_labels_digest_order_and_immutable_raws(simulated):
    data = simulated
    report = asyncio.run(data.observer.run())
    assert report["diagnostic_success"] is True and report["complete"] is True
    assert data.removed == ["control", "private", "shared"]
    assert data.created[0]["expected"] == "-"
    control = json.loads((data.observer.root / "control-diagnostic.json").read_bytes())
    digest = control["inventory_digest"]
    assert [item["expected"] for item in data.created] == ["-", digest, digest]
    creates = [args for args, _kwargs in data.calls if args[0] == "create"]
    assert all("maskgw.source-sha256=" + "b" * 64 in args for args in creates)
    assert not any("linux_import_probe.py" in args for args in creates)
    for case in H.CASES:
        saved = json.loads((data.observer.root / (case + ".json")).read_bytes())
        assert "diagnostic" not in saved
        artifact = saved["diagnostic_artifact"]
        raw = (data.observer.root / artifact["file"]).read_bytes()
        assert (
            len(raw) == artifact["bytes"] and hashlib.sha256(raw).hexdigest() == artifact["sha256"]
        )
    with pytest.raises(H.OLD.HostFault):
        asyncio.run(data.observer.run())


@pytest.mark.parametrize("mode", ["nonzero", "timeout", "malformed", "foreign-inventory"])
def test_preflight_failure_never_creates_and_lot_stops(simulated, mode):
    data = simulated
    data.version = {"nonzero": (1, b""), "timeout": TimeoutError(), "malformed": (0, b"{}")}.get(
        mode, data.version
    )
    if mode == "foreign-inventory":
        data.ps = CID.encode()
    report = asyncio.run(data.observer.run())
    assert not data.created and not report["diagnostic_success"]
    assert report["not_executed"] == list(H.CASES)
    assert data.observer.watchdog.closed


@pytest.mark.parametrize(
    "mode", ["digest", "fallback", "missing", "bad-rc", "oom", "inconclusive", "private-mismatch"]
)
def test_invalid_case_never_admits_next_case(simulated, mode):
    data = simulated

    def hook(report, state):
        if mode == "private-mismatch" and state.current["case"] == "private":
            rows = H.PROBE.unpack_inventory(report["module_inventory"])
            rows[0][1][1] = "changed"
            report["module_inventory"] = H.PROBE.pack_inventory(rows)
        elif mode == "digest":
            report["inventory_digest"] = "a" * 64
        elif mode == "fallback":
            report = {
                "profile": "loaded-as128",
                "outcome": "inconclusive",
                "report_limit": True,
                "total_memory_contained": False,
            }
        elif mode == "inconclusive":
            report.pop("inventory_digest", None)
            report["outcome"], report["failure"] = (
                "inconclusive",
                {"stage": "held", "category": "OTHER"},
            )
        return report

    if mode == "missing":
        data.exit_code = 70
        data.raw_override = b""
    elif mode == "bad-rc":
        data.exit_code = 64
    elif mode == "oom":
        data.oom = True
    data.report_hook = hook
    report = asyncio.run(data.observer.run())
    assert not report["diagnostic_success"]
    assert len(data.created) == (2 if mode == "private-mismatch" else 1)
    assert data.removed == [item["case"] for item in data.created]


@pytest.mark.parametrize("foreign", [False, True])
def test_uncertain_create_only_cleans_matching_bundle_identity(simulated, foreign):
    data = simulated
    data.create_timeout, data.foreign = True, foreign
    report = asyncio.run(data.observer.run())
    assert len(data.created) == 1 and report["diagnostic_success"] is False
    assert data.removed == ([] if foreign else ["control"])
    assert report["cases"][0]["cleanup_confirmed"] is False


def test_case_requires_preflight_active_grant_and_one_attempt(simulated):
    data = simulated
    with pytest.raises(H.OLD.HostFault):
        asyncio.run(data.observer.case("control", expected="-"))
    assert not data.created
    asyncio.run(data.observer.run())
    with pytest.raises(H.OLD.HostFault):
        asyncio.run(data.observer.case("control", expected="-"))
    assert len(data.created) == 3


def test_elapsed_lot_deadline_blocks_create_even_if_watchdog_thread_is_late(simulated, monkeypatch):
    data = simulated
    original = data.observer.integrity

    def slow_integrity():
        data.now = 121.0
        return original()

    monkeypatch.setattr(data.observer, "integrity", slow_integrity)
    report = asyncio.run(data.observer.run())
    assert not data.created
    assert report["diagnostic_success"] is False and report["deadline_exceeded"] is True


def test_case_deadline_never_admits_next(simulated):
    data = simulated

    def slow(report, world):
        world.now += 31.0
        return report

    data.report_hook = slow
    report = asyncio.run(data.observer.run())
    assert len(data.created) == 1 and not report["diagnostic_success"]
    assert data.removed == ["control"]


def test_validated_raw_tamper_blocks_next_case(simulated, monkeypatch):
    data = simulated
    original = data.observer.integrity

    def tamper():
        path = data.observer.root / "control-diagnostic.json"
        if path.exists():
            path.write_bytes(path.read_bytes() + b"\n")
        return original()

    monkeypatch.setattr(data.observer, "integrity", tamper)
    report = asyncio.run(data.observer.run())
    assert len(data.created) == 1 and report["diagnostic_success"] is False
    assert report["raw_artifacts_unchanged"] is False


@pytest.mark.parametrize("mode", ["file", "lot"])
def test_raw_caps_apply_before_any_artifact_write(tmp_path, mode):
    observer = H.Observer.__new__(H.Observer)
    observer.root, observer.total_written, observer.raw_hashes = tmp_path, 0, {}
    if mode == "lot":
        observer.total_written = H.MIB
    with pytest.raises(H.OLD.HostFault):
        observer.save_raw("control", b"x" * (65537 if mode == "file" else 3))
    assert not list(tmp_path.iterdir()) and not observer.raw_hashes


def test_selected_preparation_init_does_not_expose_old_algorithms(tmp_path, monkeypatch):
    calls: list[Any] = []

    def prepare(self, docker, image, root, prepared_root):
        calls.append("prepare-only")
        self.docker, self.image, self.root = docker, image, root
        self.task, self.source_hash = "old-import-task", "old-import-sha"
        self.probe, self.installed = root / "probe", root / "installed"
        self.probe.mkdir()
        self.installed.mkdir()
        self.originals = {}
        for name in (
            "linux_as_probe.py",
            "linux_import_probe.py",
            "run_linux_as_probe.py",
            "prepare_linux_imports.py",
            "run_linux_imports.py",
        ):
            source = Path(H.__file__).with_name(name)
            self.originals[name] = H.OLD.digest(source)
            (self.probe if name in H.PROBES else root).joinpath(name).write_bytes(
                source.read_bytes()
            )
        (self.probe / "runtime.json").write_bytes(b"{}")
        self.runtime_hash = hashlib.sha256(b"{}").hexdigest()
        self.total_written = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
        self.inventory, self.prepared = {}, {"launchers_allowlist": []}
        self.watchdog, self.expected_env = Watchdog(), None
        assert prepared_root == root / "unused"

    monkeypatch.setattr(H.IMPORTS.Observer, "__init__", prepare)
    monkeypatch.setattr(H.OLD, "Watchdog", Watchdog)
    monkeypatch.setattr(H.PREP, "verify_tree", lambda *_args: {})
    observer = H.Observer("unused-docker", tmp_path, tmp_path / "unused")
    owner = json.loads((tmp_path / "owner.json").read_bytes())
    expected = hashlib.sha256(
        json.dumps(observer.originals, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert observer.source_hash == expected and owner["bundle_sha256"] == expected
    assert observer.task.startswith("loaded-as128-") and owner["task"] == observer.task
    assert len(observer.originals) == 10 and all(observer.integrity().values())
    assert observer.watchdog.started is False and observer.started is False
    assert calls == ["prepare-only"]


def strong_report(outcome: str) -> dict[str, Any]:
    io = SupervisorIO("private")
    if outcome == "incompatible":
        io.import_error, io.rc = "MEMORY", 72
    else:

        def held(event):
            event.update(
                accepted_bytes=40 << 20, blocks=10, touched_pages=10240, failure="NONE", errno=None
            )

        def independent(observed, world):
            if world.phase == "held":
                observed["vm"] = supervisor_vm(140, 144)

        io.held_mutation, io.observe_mutation = held, independent
        io.natural_exit, io.rc = False, -9
    report, _io = supervisor_run("private", io=io)
    assert report["outcome"] == outcome
    report["startup"]["inherited_as"] = [-1, -1]
    report["startup"]["startup_cgroup"].update(procs=[1], pids_current=1)
    report["final_cgroup"].update(procs=[1], pids_current=1)
    result: dict[str, Any] = report
    return result


@pytest.mark.parametrize(
    "mode", ["cleanup", "no-witness", "wrong-code", "wrong-stage", "control", "outer"]
)
def test_strong_negative_without_evidence_is_refused(mode):
    report = strong_report("fail" if mode in ("cleanup", "no-witness", "outer") else "incompatible")
    case, expected = "private", reports()[1]
    if mode == "cleanup":
        report["cleanup_confirmed"] = False
    elif mode == "no-witness":
        report["observations"][-1]["vm"] = supervisor_vm(124, 126)
    elif mode == "wrong-code":
        report["member_returncode"] = 73
    elif mode == "wrong-stage":
        report["failure"]["stage"] = "held"
    elif mode == "control":
        report["case"], case, expected = "control", "control", "-"
    else:
        report["final_cgroup"]["events"]["oom_kill"] = 1
    with pytest.raises(H.OLD.HostFault, match=r"^REPORT_LIFECYCLE$"):
        H.validate_report(report, case, expected)


@pytest.mark.parametrize("outcome", ["fail", "incompatible"])
def test_strong_negative_from_real_supervisor_fake_is_preserved_and_stops(simulated, outcome):
    data = simulated
    negative = strong_report(outcome)
    H.validate_report(negative, "private", reports()[1])

    def hook(report, state):
        return copy.deepcopy(negative) if state.current["case"] == "private" else report

    data.report_hook = hook
    report = asyncio.run(data.observer.run())
    assert report["cases"][1]["outcome"] == outcome
    assert len(data.created) == 2 and report["diagnostic_success"] is False


@pytest.mark.parametrize("mode", ["cleanup", "no-witness"])
def test_unproven_strong_negative_is_recorded_inconclusive_with_raw_preserved(simulated, mode):
    data = simulated
    negative = strong_report("fail")
    if mode == "cleanup":
        negative["cleanup_confirmed"] = False
    else:
        negative["observations"][-1]["vm"] = supervisor_vm(124, 126)

    def hook(report, state):
        return copy.deepcopy(negative) if state.current["case"] == "private" else report

    data.report_hook = hook
    summary = asyncio.run(data.observer.run())
    saved = json.loads((data.observer.root / "private.json").read_bytes())
    raw = json.loads((data.observer.root / "private-diagnostic.json").read_bytes())
    assert saved["outcome"] == "inconclusive" and saved["host_failure"] == "REPORT_LIFECYCLE"
    assert raw == negative and len(data.created) == 2 and not summary["diagnostic_success"]
