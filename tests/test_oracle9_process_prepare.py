"""Host admission/command/report policy only; no Docker calls or Desktop."""

import asyncio
import copy
import hashlib
import importlib.util
import json
import types
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def host() -> Any:
    path = ROOT / "docs/poc/oracle9_process_prepare.py"
    spec = importlib.util.spec_from_file_location("_guard_host_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report() -> dict[str, Any]:
    controller = {
        "pid": 1,
        "dumpable": 0,
        "pdeathsig": 0,
        "as_bytes": 384 * 1024 * 1024,
        "core": [0, 0],
    }

    def case(pid: int, dump: int) -> dict[str, Any]:
        ready = {
            "pid": pid,
            "dumpable": dump,
            "guard": {
                "pid": pid,
                "parent_pid": 1,
                "pdeathsig": 9,
                "as_bytes": 256 * 1024 * 1024,
                "core": [0, 0],
            },
        }
        result = {"ready": ready, "exit_code": 0}
        for key in ("mem", "vm", "ptrace", "environ", "fd"):
            result[key] = {"allowed": bool(dump), "equal": bool(dump), "errno": 0 if dump else 1}
        return result

    return {
        "outcome": "ORACLE9_PROCESS_GUARD_VERIFIED",
        "phase": "COMPLETE",
        "remaining_pids": [1],
        "pid1_death_proved": False,
        "differential": dict.fromkeys(("mem", "vm", "ptrace", "environ", "fd"), True),
        "controller": controller,
        "positive": case(3, 1),
        "negative": case(4, 0),
        "parent_death": {"grandchild_signal": 9, "reaped": True, "intermediate_exit": 0},
        "wrong_parent": {
            "ready": False,
            "refused": "PARENT",
            "dumpable": 1,
            "as_unchanged": True,
            "actual_parent_pid": 1,
            "expected_parent_pid": 2,
            "pid": 9,
        },
    }


def encoded(value: dict[str, Any]) -> bytes:
    return json.dumps(value).encode() + b"\n"


def test_success_requires_concrete_contrast_and_reap(host: Any) -> None:
    value = report()
    assert host.report_line(encoded(value)) == value


@pytest.mark.parametrize(
    "field,value",
    [
        ("remaining_pids", [1, 3]),
        ("pid1_death_proved", True),
        ("outcome", "NOT_PASSED"),
        ("phase", "NOT_COMPLETE"),
    ],
)
def test_no_gate_overclaim_or_process_residue(host: Any, field: str, value: Any) -> None:
    item = report()
    item[field] = value
    with pytest.raises(RuntimeError):
        host.report_line(encoded(item))


@pytest.mark.parametrize("interface", ["mem", "vm", "ptrace", "environ", "fd"])
def test_each_interface_must_differ_and_preserve_canary_in_control(
    host: Any, interface: str
) -> None:
    item = report()
    item["positive"][interface]["equal"] = False
    with pytest.raises(RuntimeError):
        host.report_line(encoded(item))
    item = report()
    item["negative"][interface]["errno"] = 3
    with pytest.raises(RuntimeError):
        host.report_line(encoded(item))
    item = report()
    item["differential"][interface] = False
    with pytest.raises(RuntimeError):
        host.report_line(encoded(item))


@pytest.mark.parametrize(
    "section,field,value",
    [
        ("controller", "dumpable", 1),
        ("controller", "pdeathsig", 9),
        ("parent_death", "grandchild_signal", 15),
        ("parent_death", "reaped", False),
        ("wrong_parent", "as_unchanged", False),
        ("wrong_parent", "expected_parent_pid", 9),
        ("wrong_parent", "expected_parent_pid", 1),
    ],
)
def test_core_lifecycle_and_wrong_parent_facts_are_required(
    host: Any, section: str, field: str, value: Any
) -> None:
    item = report()
    item[section][field] = value
    with pytest.raises(RuntimeError):
        host.report_line(encoded(item))


def test_child_role_limits_and_unique_pid_are_bound(host: Any) -> None:
    item = report()
    item["negative"] = copy.deepcopy(item["positive"])
    with pytest.raises(RuntimeError):
        host.report_line(encoded(item))
    item = report()
    item["positive"]["ready"]["guard"]["as_bytes"] = -1
    with pytest.raises(RuntimeError):
        host.report_line(encoded(item))


@pytest.mark.parametrize("raw", [b"{}", b"{}\n{}\n", b"x" * 16385])
def test_report_has_one_bounded_frame(host: Any, raw: bytes) -> None:
    with pytest.raises(RuntimeError):
        host.report_line(raw)


def test_owned_container_profile_reuses_frozen_validated_policy_only(host: Any) -> None:
    policy = host.frozen(host.POLICY, host.POLICY_SHA, "_frozen_profile_test")
    policy["PAYLOAD_SHA"] = "b" * 64
    command = ["-c", "public_payload", "controller"]
    args = policy["create_args"](host.IMAGE, "maskgw-owned", "a" * 32, command, True)
    assert args[:2] == ["create", "--pull=never"]
    assert args[-4:] == [host.IMAGE, *command]
    assert "--read-only" in args and "--cap-drop" in args
    assert "maskgw.source-sha256=" + "b" * 64 in args
    assert args[args.index("--network") + 1] == "none"
    assert args[args.index("--log-driver") + 1] == "none"
    assert not any(
        token in args for token in ("--volume", "--mount", "--privileged", "--cap-add", "--publish")
    )


def test_regular_source_size_and_hash_are_checked_before_execution(
    host: Any, tmp_path: Path
) -> None:
    path = tmp_path / "source.py"
    path.write_bytes(b"raise AssertionError('must not run')\n")
    with pytest.raises(RuntimeError, match="SOURCE_PIN"):
        host.frozen(path, "0" * 64, "_never_exec")
    with pytest.raises(RuntimeError, match="FILE_SIZE"):
        host.regular(path, 1)


def test_captured_payload_must_match_state_even_if_current_file_matches(
    host: Any, tmp_path: Path, monkeypatch: Any
) -> None:
    root = tmp_path / "Temp/maskgw-oracle9-process-test"
    root.mkdir(parents=True)
    guard_path = tmp_path / "guard.py"
    payload_path = tmp_path / "payload.py"
    helper = tmp_path / "helper.py"
    guard_path.write_bytes(b"guard bytes")
    payload_path.write_bytes(b"expected payload")
    helper.write_bytes(b"# fake helper, no command\n")

    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    state = {
        "kind": "maskgw-oracle9-process",
        "image": host.IMAGE,
        "phase": "APP_READY",
        "invoked": False,
        "task": "a" * 32,
        "guard_sha256": sha(guard_path),
        "payload_sha256": sha(payload_path),
        "program_sha256": sha(Path(host.__file__)),
    }
    (root / "attempt.json").write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(host, "GUARD", guard_path)
    monkeypatch.setattr(host, "PAYLOAD", payload_path)
    monkeypatch.setattr(
        host,
        "sys",
        types.SimpleNamespace(flags=types.SimpleNamespace(isolated=True, dont_write_bytecode=True)),
    )
    saved: list[Any] = []

    def forbidden_save(*args: Any) -> None:
        saved.append(args)
        raise RuntimeError("CONSUMED_STATE_BEFORE_CAPTURE_PIN")

    origin = {
        "HELPER": helper,
        "PINS": {helper: sha(helper)},
        "pins": lambda: None,
        "save": forbidden_save,
    }
    native = {"GUARD_SHA": sha(guard_path)}
    # Captured bytes differ; a separate later read of the real file would pass.
    monkeypatch.setattr(
        host,
        "source_inputs",
        lambda: (origin, {}, {}, native, guard_path.read_bytes(), b"OTHER_CAPTURED_PAYLOAD"),
    )
    with pytest.raises(RuntimeError, match="CAPTURED_SOURCE_PIN"):
        asyncio.run(host.main(root))
    assert saved == []


@pytest.mark.parametrize("change", ["guard", "payload", "declared_guard"])
def test_each_captured_identity_matches_the_immutable_state(host: Any, change: str) -> None:
    guard, payload = b"GUARD", b"PAYLOAD"
    guard_sha = hashlib.sha256(guard).hexdigest()
    state = {"guard_sha256": guard_sha, "payload_sha256": hashlib.sha256(payload).hexdigest()}
    native = {"GUARD_SHA": guard_sha}
    host.admit_captured(state, native, guard, payload)
    if change == "guard":
        guard += b"CHANGED"
    elif change == "payload":
        payload += b"CHANGED"
    else:
        native["GUARD_SHA"] = "0" * 64
    with pytest.raises(RuntimeError, match="CAPTURED_SOURCE_PIN"):
        host.admit_captured(state, native, guard, payload)
