"""Specific coordinator with deterministic fakes; never invokes Windows/Docker."""

import asyncio
import contextlib
import hashlib
import json
import re
import runpy
import threading
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/oracle9_w1_run.py"))


@pytest.fixture
def lab(module: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    host = module["Host"].__new__(module["Host"])
    builders = runpy.run_path(str(REPO / "docs/poc/oracle9_w1_prepare.py"))
    foundation = runpy.run_path(str(REPO / "docs/poc/oracle9_python_prepare.py"))
    core = runpy.run_path(str(REPO / "docs/poc/oracle9_cycle_freshness.py"))
    model: dict[str, Any] = {
        "tick": 0,
        "boot": "134372287595000000",
        "ps_cost": 1000,
        "clock_cost": 7000,
        "cli_cost": 3000,
        "calls": [],
        "active": False,
        "stopped": False,
        "rows_override": None,
    }
    created = {"pid": 123, "name": "Docker Desktop", "created": "134372987595123457"}
    base = runpy.run_path(str(REPO / "tests/test_oracle9_w1_prepare.py"))["base"](builders)
    host.root, host.state = tmp_path, {"task": "f" * 32}
    host.libs = {
        "builders": builders,
        "foundation": foundation,
        "core": core,
        "clock": {"_bindings": lambda: (model["tick"], 0)},
    }
    host.old_policy, host.policy, _ = builders["policy_pair"]()
    host.cycle = host.started = host.base = None
    host.initial_active = None
    host.commands, host.process_observations = [], []
    host.result = {"outcome": "NOT_PASSED", "desktop_restored": False, "owned_cleanup": True}
    host.records, host.candidate, host.commit_intended = [], None, False
    host.commit_id = None
    host.active_lock, host.active = threading.Lock(), None
    host.stop, host.fired = threading.Event(), threading.Event()
    host.watchdog_failed, host.watchdog_thread = False, None
    host.tag = "maskgw-oracle9-w1-candidate:" + host.state["task"]
    monkeypatch.setattr(host, "pins", lambda **_kwargs: None)

    async def sample() -> Any:
        model["tick"] += model["clock_cost"]
        return core["Sample"](
            model["boot"], str(model["tick"]), str(134373000000000000 + model["tick"] * 10000)
        )

    async def sleep(seconds: float) -> None:
        assert 0 <= seconds <= 10
        model["tick"] += round(seconds * 1000)

    async def powershell(
        label: str, command: str, timeout: int = 3, cleanup: bool = False, start: bool = False
    ) -> Any:
        assert command in (module["PROCESS_COMMAND"], module["START_COMMAND"])
        assert timeout == 3 and type(cleanup) is bool
        model["calls"].append(label)
        model["tick"] += model["ps_cost"]
        if start:
            model["active"] = True
            return {"identity": dict(created), "environment_keys": ["SystemRoot", "PATH"]}
        if model["rows_override"] is not None:
            return model["rows_override"]
        return [dict(created)] if model["active"] and not model["stopped"] else []

    async def cli(
        label: str,
        *args: str,
        timeout: int = 10,
        limit: int = 2 * 1024 * 1024,
        cleanup: bool = False,
    ) -> Any:
        assert all(type(value) is str for value in args) and limit > 0 and type(cleanup) is bool
        model["calls"].append(label)
        model["tick"] += min(timeout * 1000, model["cli_cost"])
        if label == "version":
            return 0, b'{"Server":{"Version":"public"}}'
        if label == "info":
            return 0, json.dumps(
                {
                    "OSType": "linux",
                    "Architecture": "amd64",
                    "KernelVersion": module["KERNEL"],
                    "MemTotal": 4 * 1024**3,
                    "Driver": "overlayfs",
                    "CgroupVersion": "2",
                    "ServerVersion": "public",
                }
            ).encode()
        if label == "base-image":
            return 0, json.dumps([base]).encode()
        if label == "desktop-stop":
            model["stopped"] = True
        return 0, b""

    monkeypatch.setattr(host, "sample", sample)
    monkeypatch.setattr(host, "powershell", powershell)
    monkeypatch.setattr(host, "cli", cli)
    monkeypatch.setattr(module["asyncio"], "sleep", sleep)
    return host, model, base, created


def test_nine_observations_and_b_persisted_before_return(lab):
    host, model, _, _ = lab
    asyncio.run(host.start_cycle())
    saved = json.loads((host.root / "cycle.json").read_bytes())
    assert saved["phase"] == "B_CONSUMED" and saved["observations"] == 9
    assert model["calls"].count("OBSERVE") == 9
    eighth = [i for i, value in enumerate(model["calls"]) if value == "OBSERVE"][7]
    ninth = [i for i, value in enumerate(model["calls"]) if value == "OBSERVE"][8]
    assert eighth < model["calls"].index("version") < model["calls"].index("tag-free") < ninth
    assert model["calls"].index("inventory-ready") > ninth
    assert model["tick"] <= 300000


def test_timeout_caps_fit_without_widening_thirty_second_interval(lab):
    host, model, _, _ = lab
    model.update(clock_cost=8000, ps_cost=3000, cli_cost=3000)
    asyncio.run(host.start_cycle())
    assert host.cycle.phase.value == "B_CONSUMED"
    assert model["tick"] <= 300000


@pytest.mark.parametrize("fault", ["Hostname", "Domainname", "Cmd", "extra_label"])
def test_base_per_container_or_unknown_config_refused_before_b(lab, fault):
    host, model, base, _ = lab
    if fault == "extra_label":
        base["Config"]["Labels"]["unexpected"] = "public"
    else:
        base["Config"][fault] = "container-value" if fault != "Cmd" else []
    with pytest.raises(RuntimeError, match="BASE_CONFIG_EXACT"):
        asyncio.run(host.start_cycle())
    assert "B" not in model["calls"]
    assert json.loads((host.root / "cycle.json").read_bytes())["observations"] == 8


@pytest.mark.parametrize("clock_cost", [15000, 121000])
def test_actual_late_clock_refuses_without_b_not_extended(lab, clock_cost):
    host, model, _, _ = lab
    model["clock_cost"] = clock_cost
    with pytest.raises(RuntimeError, match=r"CYCLE_REFUSED|WAIT_CLOCK"):
        asyncio.run(host.start_cycle())
    assert "B" not in model["calls"]
    assert json.loads((host.root / "cycle.json").read_bytes())["phase"] != "B_CONSUMED"


def test_initially_active_is_preserved_without_start_or_stop(lab):
    host, model, _, _ = lab
    model["active"] = True
    asyncio.run(host.start_cycle())
    asyncio.run(host.restore_desktop())
    assert host.result["desktop_restored"] is True
    assert host.result["desktop_state"] == "PRESERVED_ACTIVE"
    assert "start-hidden" not in model["calls"] and "desktop-stop" not in model["calls"]


def test_restore_after_long_pre_b_delay_uses_identity_not_age(lab):
    host, model, _, _ = lab
    asyncio.run(host.start_cycle())
    model["tick"] += 2 * 60 * 60 * 1000
    asyncio.run(host.restore_desktop())
    assert host.result["desktop_restored"] is True
    assert model["calls"].index("inventory-before-stop") < model["calls"].index("desktop-stop")
    assert host.result["desktop_state"] == "OFF_CONFIRMED"


@pytest.mark.parametrize("fault", ["boot", "pid", "created", "gone"])
def test_restore_never_stops_unproven_or_replaced_desktop(lab, fault):
    host, model, _, created = lab
    asyncio.run(host.start_cycle())
    if fault == "boot":
        model["boot"] = "134372287595000001"
    else:
        row = dict(created)
        if fault != "gone":
            row[fault] = 456 if fault == "pid" else "134372987595123458"
        model["rows_override"] = [] if fault == "gone" else [row]
    asyncio.run(host.restore_desktop())
    assert host.result["desktop_restored"] is False
    assert "desktop-stop" not in model["calls"]


def test_process_ids_keep_exact_filetime_above_2_to_53(module):
    row = {"pid": 123, "name": "com.docker.backend", "created": "134372987595123457"}
    assert module["process_row"](json.loads(json.dumps(row))) == row
    with pytest.raises(RuntimeError):
        module["process_row"](row | {"created": 134372987595123457})


def test_powershell_and_python_match_same_process_name_regex(module):
    match = re.search(r"-match '([^']+)'", module["PROCESS_COMMAND"])
    assert match
    pattern = match[1]
    assert re.fullmatch(pattern, "com.docker.backend")
    assert re.fullmatch(pattern, "Docker Desktop")
    assert not re.fullmatch(pattern, "unrelated")


@pytest.fixture
def native_lab(lab: Any, monkeypatch: pytest.MonkeyPatch) -> Any:  # noqa: PLR0915 - closed fake-daemon fixture and public attestation.
    host, model, base, _ = lab
    asyncio.run(host.start_cycle())
    builders = host.libs["builders"]
    context = runpy.run_path(str(REPO / "docs/poc/oracle9_w1_context.py"))
    host.libs["context"] = context
    old = json.loads(
        (REPO / "docs/poc/evidence/oracle9-installed-attestation-20261026.json").read_bytes()
    )
    manifest = json.loads(
        (REPO / "docs/poc/evidence/oracle9-w1-context-manifest-20261027.json").read_bytes()
    )
    _, after = runpy.run_path(str(REPO / "tests/test_oracle9_w1_update.py"))["modeled_prefix"](
        old, manifest["target"]
    )
    imports = {
        "modules": {
            path.removesuffix(".py").replace("/", "."): {
                "bytes": manifest["target"]["installed_files"][path]["bytes"],
                "sha256": manifest["target"]["installed_files"][path]["sha256"],
            }
            for path in builders["ADDED"]
        },
        "preloaded": ["maskgw.db.session_state"],
    }
    report = {
        "kind": "oracle9-w1-installed-v1",
        "manifest": manifest,
        "context_manifest_sha256": builders["MANIFEST_SHA"],
        "origin_attestation_sha256": context["OLD_ATTEST_SHA"],
        "origin_installed_snapshot": old["installed_snapshot"],
        "base_snapshot": old["base_snapshot"],
        "base_pth": old["base_pth"],
        "native": old["native"],
        "versions": old["versions"],
        "installed_snapshot": after,
        "w1_imports": imports,
    }
    attestation = (json.dumps(report, sort_keys=True) + "\n").encode()
    installed = {
        "outcome": "W1_APP_UPDATE_VERIFIED",
        "attestation_sha256": hashlib.sha256(attestation).hexdigest(),
        "attestation_bytes": len(attestation),
        "managed_inputs_removed": True,
        "prefix_paths": 3337,
        "versions": old["versions"],
        "native": old["native"],
        "w1_imports": imports,
    }
    image = "sha256:" + "e" * 64
    info = deepcopy(base)
    info.update(Id=image, RepoTags=[host.tag])
    info["RootFS"]["Layers"].append("sha256:" + "f" * 64)
    info["Config"]["Labels"] = builders["expected_labels"](base, host.state["task"])
    model.update(fault=None, containers={}, candidate=None, effects=[], creates=[])
    fixture = runpy.run_path(str(REPO / "tests/test_oracle9_offline_prepare.py"))["container"]
    before_calls = model["calls"][:]
    host.state["create_measurements"] = {}
    payload = (REPO / "deploy/oracle9_w1_update.py").read_bytes()
    for role in ("install", "probe"):
        command = builders["native_command"](
            payload,
            role,
            host.state["task"],
            installed["attestation_sha256"] if role == "probe" else None,
        )
        _, measurement = builders["measured_create"](
            str(host.libs["foundation"]["CLI"]),
            host.policy,
            image=builders["IMAGE"] if role == "install" else image,
            name="maskgw-ol9-w1-" + host.state["task"][:12] + "-" + role,
            task=host.state["task"],
            command=command,
            probe=role == "probe",
        )
        host.state["create_measurements"][role] = measurement

    async def cli(label: str, *args: str, **kwargs: Any) -> Any:  # noqa: PLR0911, PLR0912, PLR0915 - explicit finite daemon command dispatcher, no execution.
        model["effects"].append((label, args, kwargs))
        fault = model["fault"]
        if label.startswith("create-"):
            assert json.loads((host.root / "cycle.json").read_bytes())["phase"] == "B_CONSUMED"
            intent = json.loads((host.root / "ownership.json").read_bytes())[-1]
            record = host.records[-1]
            assert intent["name"] == record["name"] and intent["cid"] is None
            if fault == "create_absent":
                return 1, b""
            container = fixture(
                SimpleNamespace(
                    PAYLOAD_SHA=builders["PAYLOAD_SHA"], MANIFEST_SHA=builders["MANIFEST_SHA"]
                ),
                host.libs["foundation"],
                record["name"],
                host.state["task"],
                record["image"],
                record["command"],
                record["role"] == "probe",
            )
            container["Config"]["Labels"] = builders["expected_labels"](base, host.state["task"])
            if fault == "foreign":
                container["Config"]["Labels"]["maskgw.task"] = "foreign"
            model["containers"][container["Id"]] = container
            model["creates"].append(args)
            return (
                (1, b"") if fault == "create_ambiguous" else (0, (container["Id"] + "\n").encode())
            )
        if label.startswith("inspect-") and label != "inspect-tag-cleanup":
            target = args[-1]
            rows = [
                v
                for v in model["containers"].values()
                if v["Id"] == target or v["Name"] == "/" + target
            ]
            return (0, json.dumps(rows).encode()) if len(rows) == 1 else (1, b"")
        if label == "resolve-intent":
            return 0, (next(iter(model["containers"])) + "\n").encode() if model[
                "containers"
            ] else b""
        if label == "copy-public-inputs":
            assert args[1].endswith("context/.") and "--follow-link" not in args
            return 0, b""
        if label.startswith("run-"):
            role = label.removeprefix("run-")
            if fault in ("install_exit", "running") and role == "install":
                if fault == "running":
                    model["containers"][args[-1]]["State"].update(Running=True, Pid=9, ExitCode=1)
                return 1, b'{"outcome":"W1_UPDATE_REFUSED"}\n'
            if fault == "probe" and role == "probe":
                return 1, b'{"outcome":"W1_UPDATE_REFUSED"}\n'
            result = dict(installed)
            if fault == "inputs_remain":
                result["managed_inputs_removed"] = False
            if role == "probe":
                result["outcome"] = "W1_APP_PROBE_VERIFIED"
            return 0, (json.dumps(result) + "\n").encode()
        if label == "copy-attestation":
            Path(args[-1]).write_bytes(attestation + (b"x" if fault == "attestation" else b""))
            return 0, b""
        if label == "install-diff":
            lines = (
                ["C " + p for p in sorted(builders["ANCESTORS"])]
                + ["A " + builders["ATTEST"]]
                + ["A " + builders["SITE"] + "/" + p for p in sorted(builders["ADDED"])]
                + ["C " + builders["DIST"] + "/RECORD"]
            )
            return 0, ("\n".join(lines) + "\n" + ("C /tmp\n" if fault == "diff" else "")).encode()
        if label == "probe-diff":
            return 0, b"C /tmp\n" if fault == "probe_diff" else b""
        if label == "commit-own":
            assert json.loads((host.root / "commit-intent.json").read_bytes())["tag"] == host.tag
            model["candidate"] = deepcopy(info)
            if fault == "commit_timeout":
                raise TimeoutError("MODEL_CLI_TIMEOUT")
            return (1, b"") if fault == "commit_unknown" else (0, (image + "\n").encode())
        if label in ("candidate-image", "inspect-tag-cleanup"):
            candidate = deepcopy(model["candidate"])
            if fault == "candidate_config":
                candidate["Config"]["Cmd"] = []
            if fault == "tag_foreign":
                candidate["Config"]["Labels"]["maskgw.task"] = "foreign"
            return 0, json.dumps([candidate]).encode()
        if label == "resolve-tag":
            return 0, (host.tag + "\n").encode() if model["candidate"] else b""
        if label == "remove-tag":
            assert args == ("image", "rm", host.tag) and not model["containers"]
            model["candidate"] = None
        if label == "kill-own":
            assert args[:3] == ("kill", "--signal", "KILL")
            model["containers"][args[-1]]["State"].update(Running=False, Pid=0)
        if label == "remove-own":
            assert args == ("rm", args[-1]) and args[-1] in model["containers"]
            if fault == "remove":
                return 1, b""
            del model["containers"][args[-1]]
        if label == "absent-own":
            cid = args[-1].removeprefix("id=")
            return 0, (cid + "\n").encode() if cid in model["containers"] else b""
        if label == "inventory-final":
            return 0, ("\n".join(model["containers"]) + "\n").encode() if model[
                "containers"
            ] else b""
        if label == "tag-absent":
            return 0, (host.tag + "\n").encode() if model["candidate"] else b""
        return 0, b""

    monkeypatch.setattr(host, "cli", cli)
    assert before_calls[-1] == "B"
    return host, model


def test_native_lot_success_keeps_only_verified_own_image(native_lab):
    host, model = native_lab
    asyncio.run(host.perform_b())
    asyncio.run(host.cleanup_owned())
    assert host.result["update_verified"] is True
    assert host.result["owned_cleanup"] is True and host.result["inventory_restored"] is True
    assert not model["containers"] and model["candidate"] is not None
    assert host.watchdog_thread.daemon is False and not host.watchdog_thread.is_alive()
    assert len(model["creates"]) == 2


@pytest.mark.parametrize(
    "fault",
    [
        "create_ambiguous",
        "create_absent",
        "install_exit",
        "inputs_remain",
        "attestation",
        "diff",
        "running",
        "commit_unknown",
        "probe",
        "probe_diff",
    ],
)
def test_failure_never_commits_or_keeps_unverified_candidate_and_removes_owned(native_lab, fault):
    host, model = native_lab
    model["fault"] = fault
    with pytest.raises(RuntimeError):
        asyncio.run(host.perform_b())
    asyncio.run(host.cleanup_owned())
    assert not model["containers"] and model["candidate"] is None
    assert host.result["owned_cleanup"] is True and not host.result.get("update_verified")
    assert host.watchdog_thread is None or not host.watchdog_thread.is_alive()
    effects = [label for label, _, _ in model["effects"]]
    if fault not in ("commit_unknown", "probe", "probe_diff"):
        assert "commit-own" not in effects
    if fault == "running":
        assert "kill-own" in effects


@pytest.mark.parametrize("fault", ["foreign", "remove", "tag_foreign"])
def test_uncertain_cleanup_retains_ownership_and_refuses_stop(native_lab, fault):
    host, model = native_lab
    model["fault"] = fault
    with contextlib.suppress(RuntimeError):
        asyncio.run(host.perform_b())
    asyncio.run(host.cleanup_owned())
    assert host.result["owned_cleanup"] is False
    assert host.watchdog_thread is None or not host.watchdog_thread.is_alive()
    # Lifecycle uses the real guard: uncertainty never authorizes Desktop stop.
    asyncio.run(host.restore_desktop())
    assert host.result["desktop_restored"] is False
    assert "desktop-stop" not in [label for label, _, _ in model["effects"]]


def test_boot_change_persists_rejected_sample_and_terminal_state(lab, monkeypatch):
    host, model, _, _ = lab
    original = host.sample
    count = 0

    async def change_boot():
        nonlocal count
        count += 1
        if count == 4:
            model["boot"] = "134372287595000001"
        return await original()

    monkeypatch.setattr(host, "sample", change_boot)
    with pytest.raises(RuntimeError, match="CYCLE_REFUSED"):
        asyncio.run(host.start_cycle())
    saved = json.loads((host.root / "cycle.json").read_bytes())
    rejected = json.loads((host.root / "rejected-sample.json").read_bytes())
    assert saved["phase"] == "FAILED" and rejected["reason"] == "BOOT"
    assert "version" not in model["calls"] and "B" not in model["calls"]


@pytest.mark.parametrize("fault", ["inventory", "exit", "still_active"])
def test_restore_uses_fresh_empty_inventory_and_observed_absence(lab, monkeypatch, fault):
    host, model, _, _ = lab
    asyncio.run(host.start_cycle())
    original = host.cli

    async def failing_cli(label, *args, **kwargs):
        if fault == "inventory" and label == "inventory-before-stop":
            return 0, b"foreign-resource\n"
        if label == "desktop-stop" and fault in ("exit", "still_active"):
            model["calls"].append(label)
            return (1 if fault == "exit" else 0), b""
        return await original(label, *args, **kwargs)

    monkeypatch.setattr(host, "cli", failing_cli)
    asyncio.run(host.restore_desktop())
    assert host.result["desktop_restored"] is False
    if fault == "inventory":
        assert "desktop-stop" not in model["calls"]
    if fault == "still_active":
        assert len([v for v in model["calls"] if v.startswith("after-stop-")]) == 10


def test_constructed_libraries_admit_captured_bytes_against_state(module, tmp_path):
    state: dict[str, Any] = {
        "task": "f" * 32,
        "pins": dict(module["LIBRARIES"].values()),
    }
    host = module["Host"](tmp_path, state)
    assert set(host.captured) == set(state["pins"])
    state["pins"][module["LIBRARIES"]["builders"][0]] = "0" * 64
    with pytest.raises(RuntimeError, match="CAPTURE_PIN"):
        module["Host"](tmp_path, state)


@pytest.mark.parametrize("fault", ["none", "body", "cleanup", "restore"])
def test_entrypoint_consumes_attempt_before_cycle_and_reports_only_verified_success(
    module, lab, monkeypatch, fault
):
    host, model, _, _ = lab
    state = host.state | {
        "program_sha256": "0" * 64,
        "phase": "FRESH",
        "invoked": False,
        "create_measurements": {"MODEL": "premeasured"},
    }
    host.state = state
    global_map = module["main"].__globals__
    monkeypatch.setitem(global_map, "admit_root", lambda _root: state)
    monkeypatch.setitem(global_map, "Host", lambda _root, _state: host)
    monkeypatch.setitem(global_map, "measure_commands", lambda _host: state["create_measurements"])

    async def start_cycle():
        assert (host.root / "invoked.json").exists()
        assert json.loads((host.root / "attempt.json").read_bytes())["invoked"] is True
        model["calls"].append("A")

    async def body():
        if fault == "body":
            raise RuntimeError("PRIVATE_TEXT_MUST_NOT_BE_LOGGED")
        host.result["update_verified"] = True

    async def cleanup():
        host.result.update(owned_cleanup=fault != "cleanup", inventory_restored=True)

    async def restore():
        host.result["desktop_restored"] = fault != "restore"

    monkeypatch.setattr(host, "start_cycle", start_cycle)
    monkeypatch.setattr(host, "perform_b", body)
    monkeypatch.setattr(host, "cleanup_owned", cleanup)
    monkeypatch.setattr(host, "restore_desktop", restore)
    status = asyncio.run(module["main"](host.root))
    result = json.loads((host.root / "result.json").read_bytes())
    assert status == (0 if fault == "none" else 1)
    assert result["outcome"] == (
        "ORACLE9_W1_CANDIDATE_VERIFIED" if fault == "none" else "NOT_PASSED"
    )
    assert "PRIVATE_TEXT" not in (host.root / "result.json").read_text()
    assert state["invoked"] is True


def test_start_uses_reviewed_windows_app_allowlist_without_forwarding_secret(
    module, lab, monkeypatch
):
    host, _, _, _ = lab
    ns = runpy.run_path(str(REPO / "docs/poc/run_linux_as_probe.py"))
    host.libs.update(
        bounded=ns, clock=runpy.run_path(str(REPO / "docs/poc/oracle9_clock_sample.py"))
    )
    host.captured = {
        module["LIBRARIES"]["bounded"][0]: (REPO / module["LIBRARIES"]["bounded"][0]).read_bytes()
    }
    monkeypatch.setenv("ProgramFiles(x86)", "PUBLIC_PROGRAMS_X86")
    monkeypatch.setenv("NUMBER_OF_PROCESSORS", "16")
    monkeypatch.setenv("MASKGW_SECRET_TEST", "MUST_NOT_BE_FORWARDED")
    seen = []

    class Output:
        done = False

        async def read(self, _size):
            if self.done:
                return b""
            self.done = True
            return b"{}"

    async def create(*_args, **kwargs):
        seen.append(kwargs["env"])

        async def wait():
            return 0

        return SimpleNamespace(returncode=0, stdout=Output(), wait=wait)

    monkeypatch.setattr(module["asyncio"], "create_subprocess_exec", create)
    asyncio.run(
        module["Host"].powershell(host, "start-hidden", module["START_COMMAND"], start=True)
    )
    assert seen[0]["ProgramFiles(x86)"] == "PUBLIC_PROGRAMS_X86"
    assert seen[0]["NUMBER_OF_PROCESSORS"] == "16"
    assert "MASKGW_SECRET_TEST" not in seen[0]


def test_candidate_config_refusal_rolls_back_owned_tag_without_accepting_it(native_lab):
    host, model = native_lab
    model["fault"] = "candidate_config"
    with pytest.raises(RuntimeError, match="CANDIDATE_CONFIG_EXACT"):
        asyncio.run(host.perform_b())
    asyncio.run(host.cleanup_owned())
    assert not model["containers"] and model["candidate"] is None
    assert host.result["owned_cleanup"] is True and not host.result.get("update_verified")


def test_timeout_during_commit_with_created_image_is_owned_rollback(native_lab):
    host, model = native_lab
    model["fault"] = "commit_timeout"
    with pytest.raises(TimeoutError):
        asyncio.run(host.perform_b())
    assert host.commit_id is None and model["candidate"] is not None
    asyncio.run(host.cleanup_owned())
    assert model["candidate"] is None and host.result["candidate_cleanup"] is True


def test_host_checks_w1_hashes_even_if_result_and_attestation_agree(native_lab):
    host, _model = native_lab
    asyncio.run(host.perform_b())
    asyncio.run(host.cleanup_owned())
    report = json.loads((host.root / "installed-attestation.json").read_bytes())
    next(iter(report["w1_imports"]["modules"].values()))["sha256"] = "0" * 64
    raw = (json.dumps(report, sort_keys=True) + "\n").encode()
    installed = host.result["installation"] | {
        "attestation_sha256": hashlib.sha256(raw).hexdigest(),
        "attestation_bytes": len(raw),
        "w1_imports": report["w1_imports"],
    }
    with pytest.raises(RuntimeError, match="W1_IMPORTS"):
        host.check_attestation(raw, installed)


def test_start_targets_app_root_not_internal_resources_binary(module):
    assert module["DESKTOP"] == module["CLI"].parents[2] / "Docker Desktop.exe"


def test_start_validates_environment_names_returned_inside_powershell(module):
    row = {"pid": 123, "name": "Docker Desktop", "created": "134372987595123457"}
    assert module["start_result"](
        {"identity": row, "environment_keys": ["Path", "SystemRoot"]}
    ) == (row, ["Path", "SystemRoot"])
    for keys in (["PSModulePath"], ["MASKGW_SECRET_TEST"], ["PATH", "Path"]):
        with pytest.raises(RuntimeError, match="START_ENV"):
            module["start_result"]({"identity": row, "environment_keys": keys})
    script = module["START_COMMAND"]
    assert script.index("SetEnvironmentVariable") < script.index("Start-Process")
    assert script.index("$keys=@") < script.index("Start-Process")


def test_watchdog_is_rearmed_per_active_execution_with_previous_thread_reaped(
    native_lab, monkeypatch
):
    host, model = native_lab
    events = []
    original = host.watchdog

    def observed():
        events.append(host.stop)
        original()

    monkeypatch.setattr(host, "watchdog", observed)
    asyncio.run(host.perform_b())
    asyncio.run(host.cleanup_owned())
    assert len(events) == 2 and events[0] is not events[1] and all(v.is_set() for v in events)
    assert all(
        kwargs["timeout"] == 300
        for label, _, kwargs in model["effects"]
        if label.startswith("run-")
    )
    assert not host.watchdog_thread.is_alive()


@pytest.mark.parametrize("completion_seconds,expires", [(599.999, False), (600.0, True)])
def test_independent_execution_watchdog_boundary(module, lab, completion_seconds, expires):
    host, _, _, _ = lab

    class Completion:
        def wait(self, seconds):
            assert seconds == module["WATCHDOG_SECONDS"] == 600
            return completion_seconds < seconds

    host.stop = Completion()
    host.active = None  # deadline may expire after an exit; no unowned CLI allowed
    host.watchdog()
    assert host.fired.is_set() is expires
