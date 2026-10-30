"""HELD host profile/lifecycle/artifacts with fake CLI, timers and small files."""

from __future__ import annotations

import asyncio
import hashlib
import json
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_linux_imports_probe import load
from tests.test_loaded_memory_evidence import RecordingIO, original
from tests.test_loaded_memory_host import H as FROZEN_HOST
from tests.test_loaded_memory_host import Watchdog, fake_sleep, profile, strong_report
from tests.test_loaded_memory_host import simulated as old_simulated
from tests.test_loaded_memory_supervisor import PARTS, S

N = load("run_linux_held")


@pytest.fixture
def simulated(tmp_path, monkeypatch):
    # Only fixture mechanics reused. The frozen observer's case/run never execute.
    initializer: Any = old_simulated
    data = initializer.__wrapped__(tmp_path, monkeypatch)
    legacy = data.observer
    observer = N.Observer.__new__(N.Observer)
    observer.__dict__.update(legacy.__dict__)
    data.observer = observer
    cli, inspect = legacy.cli, legacy.inspect

    async def commands(*args: Any, **kwargs: Any) -> Any:
        rc, raw = await cli(*args, **kwargs)
        if args[0] == "start" and data.raw_override is None:
            _source, held = original(data.current["case"])
            raw = N.T.transport(raw, held, False)
        return rc, raw

    async def observed(target: str) -> Any:
        value = await inspect(target)
        if target != observer.image:
            value["Config"]["Cmd"][3] = "/probe/linux_held_probe.py"
        return value

    monkeypatch.setattr(observer, "cli", commands)
    monkeypatch.setattr(observer, "inspect", observed)
    monkeypatch.setattr(observer, "pins_consistent", lambda: True)
    monkeypatch.setattr(N.OLD, "Watchdog", Watchdog)
    monkeypatch.setattr(N, "time", SimpleNamespace(monotonic=lambda: data.now))
    monkeypatch.setattr(N.IMPORTS, "time", SimpleNamespace(monotonic=lambda: data.now))
    monkeypatch.setattr(N.IMPORTS, "asyncio", SimpleNamespace(sleep=partial(fake_sleep, data)))
    monkeypatch.setattr(N.PREP, "verify_tree", lambda *_args: {})
    return data


def test_new_profile_saves_two_artifacts_each_and_validates_all_cases(simulated):
    data = simulated
    result = asyncio.run(data.observer.run())
    assert result["profile"] == "loaded-as128-held-v1"
    assert result["diagnostic_success"] is True, result
    assert result["evidence_artifacts_complete"] is True
    assert result["total_memory_contained"] is False and data.removed == [
        "control",
        "private",
        "shared",
    ]
    assert len(data.observer.raw_hashes) == 6
    for item in result["cases"]:
        case = json.loads((data.observer.root / (item["case"] + ".json")).read_bytes())
        assert case["evidence_validated"] is True
        for key in ("transport_artifact", "envelope_artifact"):
            ref = case[key]
            raw = (data.observer.root / ref["file"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == ref["sha256"] and len(raw) == ref["bytes"]


def test_evidence_runs_after_removal_outside_case_timer_but_inside_lot(simulated, monkeypatch):
    data = simulated
    encode = N.E.encode

    def slow(*args: Any, **kwargs: Any) -> Any:
        assert data.current is None and data.removed
        assert (data.observer.root / (data.removed[-1] + "-transport.json")).exists()
        data.now += 35
        return encode(*args, **kwargs)

    monkeypatch.setattr(N.E, "encode", slow)
    result = asyncio.run(data.observer.run())
    assert result["diagnostic_success"] is True and result["elapsed_seconds"] == 105
    for case in ("control", "private", "shared"):
        saved = json.loads((data.observer.root / (case + ".json")).read_bytes())
        assert saved["elapsed_seconds"] == 0 and saved["evaluation_seconds"] == 35


def test_evidence_past_lot_deadline_stops_without_second_create(simulated, monkeypatch):
    data = simulated
    encode = N.E.encode

    def late(*args: Any, **kwargs: Any) -> Any:
        data.now = 121
        return encode(*args, **kwargs)

    monkeypatch.setattr(N.E, "encode", late)
    result = asyncio.run(data.observer.run())
    assert not result["diagnostic_success"] and result["cases"][0]["outcome"] == "inconclusive"
    assert len(data.created) == 1 and result["not_executed"] == ["private", "shared"]


@pytest.mark.parametrize(
    "code,raw,oom",
    [
        (70, b"", False),
        (64, b"bad\n", False),
        (1, b"bad\n", False),
        (0, b"", False),
        (0, b"bad\n", True),
    ],
)
def test_exit_mapping_keeps_raw_and_never_builds_envelope(simulated, code, raw, oom):
    data = simulated
    data.exit_code, data.raw_override, data.oom = code, raw, oom
    result = asyncio.run(data.observer.run())
    assert result["cases"][0]["outcome"] == "inconclusive" and len(data.created) == 1
    assert (data.observer.root / "control-transport.json").read_bytes() == raw
    assert not (data.observer.root / "control-envelope.json").exists()
    assert data.removed == ["control"]


@pytest.mark.parametrize(
    "mode", ["fallback", "old", "missing-held", "extra", "broken-positive", "bool-broken"]
)
def test_invalid_transport_or_evidence_cannot_admit_second_case(simulated, mode):
    source, held = original("control")
    data = simulated
    if mode == "fallback":
        raw = N.T.FALLBACK
    elif mode == "old":
        raw = source
    else:
        value = json.loads(N.T.transport(source, held, False))
        if mode == "missing-held":
            value["held"] = []
        elif mode == "extra":
            value["extra"] = True
        elif mode == "broken-positive":
            value["tap_broken"] = True
        else:
            value["tap_broken"] = 0
        raw = json.dumps(value).encode() + b"\n"
    data.raw_override = raw
    result = asyncio.run(data.observer.run())
    assert not result["diagnostic_success"] and len(data.created) == 1
    assert result["cases"][0]["outcome"] == "inconclusive"
    assert (data.observer.root / "control-transport.json").read_bytes() == raw
    if mode in ("fallback", "missing-held", "broken-positive"):
        assert (data.observer.root / "control-envelope.json").read_bytes() == N.E.FALLBACK


@pytest.mark.parametrize(
    "version,ps", [(TimeoutError(), b""), ((1, b""), b""), ((0, b"{}"), b""), (None, b"foreign")]
)
def test_preflight_failure_prevents_every_create(simulated, version, ps):
    if version is not None:
        simulated.version = version
    simulated.ps = ps
    result = asyncio.run(simulated.observer.run())
    assert not result["diagnostic_success"] and simulated.created == []


@pytest.mark.parametrize("mode", ["uncertain", "foreign", "pins"])
def test_identity_or_pin_problem_never_admits_following_case(simulated, monkeypatch, mode):
    data = simulated
    if mode == "uncertain":
        data.create_timeout = True
    elif mode == "foreign":
        data.foreign = True
    else:
        monkeypatch.setattr(data.observer, "pins_consistent", lambda: False)
    result = asyncio.run(data.observer.run())
    assert not result["diagnostic_success"] and len(data.created) <= 1
    if mode == "foreign":
        assert data.removed == []
    if mode == "pins":
        assert data.created == []


@pytest.mark.parametrize("flag", ["-I", "-B", "-S"])
def test_inspect_requires_every_runtime_flag(tmp_path, flag):
    info = profile(tmp_path)
    info["Config"]["Image"] = N.BASE
    info["Config"]["Cmd"][3] = "/probe/linux_held_probe.py"
    checked = partial(
        N.validate_profile,
        image=N.BASE,
        task="loaded-task",
        source_hash="b" * 64,
        name="loaded-control",
        case="control",
        expected="-",
        probe=tmp_path / "probe",
        installed=tmp_path / "installed",
        expected_env=info["Config"]["Env"],
    )
    assert checked(info) is True
    info["Config"]["Cmd"].remove(flag)
    with pytest.raises(N.OLD.HostFault):
        N.validate_profile(
            info,
            image=N.BASE,
            task="loaded-task",
            source_hash="b" * 64,
            name="loaded-control",
            case="control",
            expected="-",
            probe=tmp_path / "probe",
            installed=tmp_path / "installed",
            expected_env=info["Config"]["Env"],
        )


def test_no_legacy_algorithms_in_class_or_success_classifier():
    assert N.Observer.__bases__ == (object,)
    assert N.Observer.case is not FROZEN_HOST.Observer.case
    assert N.Observer.run is not FROZEN_HOST.Observer.run
    assert not N.diagnostic_success({"profile": "loaded-as128", "complete": True})


def test_artifacts_are_accounted_individually_and_immutable(tmp_path):
    observer = N.Observer.__new__(N.Observer)
    observer.root, observer.total_written, observer.raw_hashes = tmp_path, 0, {}
    for kind in ("transport", "envelope"):
        ref = observer.save_artifact("control", kind, b"abc\n")
        assert ref["file"] == "control-" + kind + ".json"
    assert observer.total_written == 8 and len(observer.raw_hashes) == 2
    with pytest.raises(N.OLD.HostFault):
        observer.save_artifact("control", "transport", b"changed")
    assert (tmp_path / "control-transport.json").read_bytes() == b"abc\n"


def test_constructor_positions_fourteen_sources_and_pin_crosschecks(tmp_path, monkeypatch):
    def prepared(self: Any, docker: str, image: str, root: Path, _prepared_root: Path) -> None:
        self.docker, self.image, self.root = docker, image, root
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
            source = Path(N.__file__).with_name(name)
            self.originals[name] = N.OLD.digest(source)
            (self.probe if name in N.PROBES else root).joinpath(name).write_bytes(
                source.read_bytes()
            )
        (self.probe / "runtime.json").write_bytes(b"{}")
        self.runtime_hash = hashlib.sha256(b"{}").hexdigest()
        self.total_written = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
        self.prepared, self.inventory = {"launchers_allowlist": []}, {}
        self.watchdog, self.expected_env = Watchdog(), None

    monkeypatch.setattr(N.IMPORTS.Observer, "__init__", prepared)
    monkeypatch.setattr(N.OLD, "Watchdog", Watchdog)
    monkeypatch.setattr(N.PREP, "verify_tree", lambda *_args: {})
    observer = N.Observer("unused-docker", tmp_path, tmp_path / "unused")
    assert len(observer.originals) == 14 and len(N.PROBES) == 8
    assert observer.task.startswith("held-as128-") and all(observer.integrity().values())
    for name in observer.originals:
        assert ((observer.probe if name in N.PROBES else tmp_path) / name).is_file()
    assert not (observer.probe / "loaded_memory_evidence.py").exists()
    owner = json.loads((tmp_path / "owner.json").read_bytes())
    assert owner["kind"] == N.PROFILE and owner["bundle_sha256"] == observer.source_hash
    (observer.probe / "loaded_memory_tap.py").write_bytes(b"wrong")
    assert (
        observer.pins_consistent() is False and observer.integrity()["sources_unchanged"] is False
    )


@pytest.mark.parametrize(
    "code,category", [(64, "TRANSPORT_ARGV"), (70, "TRANSPORT_EXECUTION"), (0, "TRANSPORT_MISSING")]
)
def test_empty_output_preserves_precise_exit_category(simulated, code, category):
    simulated.exit_code, simulated.raw_override = code, b""
    result = asyncio.run(simulated.observer.run())
    assert result["cases"][0]["host_failure"] == category


@pytest.mark.parametrize(
    "raw",
    [bytearray(b"x"), None, "text", bytearray(N.T.FALLBACK)],
    ids=["bytearray", "none", "text", "fallback-bytearray"],
)
def test_transport_type_checked_before_fallback_equality(raw):
    with pytest.raises(N.OLD.HostFault):
        N.decode_transport(raw)


def test_final_pin_failure_cannot_be_diagnostic_success(simulated):
    result = asyncio.run(simulated.observer.run())
    assert result["diagnostic_success"] is True
    result["pins_consistent"] = False
    assert N.diagnostic_success(result) is False


def test_strong_negative_is_validated_and_preserved_then_stops(simulated):
    def incompatible(report: Any, data: Any) -> Any:
        return strong_report("incompatible") if data.current["case"] == "private" else report

    simulated.report_hook = incompatible
    result = asyncio.run(simulated.observer.run())
    assert [item["outcome"] for item in result["cases"]] == ["control_ok", "incompatible"]
    assert result["not_executed"] == ["shared"] and simulated.removed == ["control", "private"]
    envelope = json.loads((simulated.observer.root / "private-envelope.json").read_bytes())
    assert envelope["outcome"] == "incompatible" and envelope["validated_held"] == []


def test_broken_negative_keeps_original_but_never_admits(simulated):
    io = RecordingIO("control")
    io.import_error, io.rc = "MEMORY", 72
    source = S.bounded_report(S.supervise("control", "-", io, PARTS, deadline=120.0))
    simulated.raw_override = N.T.transport(source, (), True)
    result = asyncio.run(simulated.observer.run())
    assert len(simulated.created) == 1 and result["cases"][0]["host_failure"] == "TAP_BROKEN"
    raw = (simulated.observer.root / "control-envelope.json").read_bytes()
    assert raw != N.E.FALLBACK and json.loads(raw)["original_report"].encode("ascii") == source


def test_envelope_write_error_occurs_after_cleanup_and_stops(simulated, monkeypatch):
    save = simulated.observer.save_artifact

    def failed(case: str, kind: str, raw: bytes) -> Any:
        if kind == "envelope":
            assert simulated.current is None and simulated.removed == ["control"]
            raise N.OLD.HostFault("ARTIFACT_LIMIT")
        return save(case, kind, raw)

    monkeypatch.setattr(simulated.observer, "save_artifact", failed)
    result = asyncio.run(simulated.observer.run())
    assert len(simulated.created) == 1 and result["cases"][0]["outcome"] == "inconclusive"
    assert (simulated.observer.root / "control-transport.json").is_file()


@pytest.mark.parametrize(
    "raw",
    [b'{"a":NaN}\n', b'{"a":1,"a":2}\n', b"{}\n{}\n", b"\xff\n", b"x" * 65537],
    ids=["nan", "duplicate", "extra-document", "nonascii", "overflow"],
)
def test_transport_parser_reuses_closed_bounded_json(raw):
    with pytest.raises(N.OLD.HostFault) as error:
        N.decode_transport(raw)
    assert error.value.__cause__ is None and error.value.__context__ is None


def test_raw_corruption_after_removal_is_detected_before_evidence_parse(simulated, monkeypatch):
    cli = simulated.observer.cli

    async def corrupted(*args: Any, **kwargs: Any) -> Any:
        result = await cli(*args, **kwargs)
        if args[0] == "rm":
            (simulated.observer.root / "control-transport.json").write_bytes(b"tampered\n")
        return result

    monkeypatch.setattr(simulated.observer, "cli", corrupted)
    result = asyncio.run(simulated.observer.run())
    assert result["cases"][0]["host_failure"] == "INTEGRITY" and len(simulated.created) == 1
    assert not (simulated.observer.root / "control-envelope.json").exists()


def test_late_clock_blocks_create_even_when_watchdog_did_not_fire(simulated, monkeypatch):
    preflight = simulated.observer.preflight

    async def late(evidence: Any) -> None:
        await preflight(evidence)
        simulated.now = 121

    monkeypatch.setattr(simulated.observer, "preflight", late)
    result = asyncio.run(simulated.observer.run())
    assert result["deadline_exceeded"] is True and simulated.created == []
    assert simulated.observer.watchdog.fired.is_set() is False


def test_final_integrity_cost_cannot_escape_lot_deadline(simulated, monkeypatch):
    integrity = simulated.observer.integrity

    def late_final_check() -> Any:
        result = integrity()
        if simulated.observer.started and simulated.observer.running is False:
            simulated.now = 121
        return result

    monkeypatch.setattr(simulated.observer, "integrity", late_final_check)
    result = asyncio.run(simulated.observer.run())
    assert result["diagnostic_success"] is False and result["deadline_exceeded"] is True
