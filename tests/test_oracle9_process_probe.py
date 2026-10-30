"""Native probe policy only, with fakes; never starts a process or Linux test."""

import errno
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from maskgw.runtime import linux_guard

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def probe(monkeypatch: Any) -> Any:
    path = ROOT / "deploy/oracle9_process_probe.py"
    spec = importlib.util.spec_from_file_location("_process_probe_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module,
        "GUARD_SOURCE",
        (ROOT / "src/maskgw/runtime/linux_guard.py").read_bytes(),
        raising=False,
    )
    monkeypatch.setattr(module, "PROBE_SOURCE", path.read_bytes(), raising=False)
    return module


def test_pins_guard_bytes_and_bootstrap_is_public_and_bounded(probe: Any) -> None:
    assert hashlib.sha256(probe.GUARD_SOURCE).hexdigest() == probe.GUARD_SHA
    code = probe.bootstrap(probe.GUARD_SOURCE, probe.PROBE_SOURCE)
    assert len(code) < 25000
    compile(code, "<public-probe-bootstrap>", "exec")
    assert len(probe.environment()) == 6
    assert all(not k.startswith(("PYTHON", "MASKGW")) for k in probe.environment())
    assert probe.child_command("protected", 1) == [
        probe.PYTHON,
        "-I",
        "-B",
        "-c",
        code,
        "protected",
        "1",
    ]


@pytest.mark.parametrize(
    "role,parent", [("x", 1), ("protected", True), ("protected", 0), ("protected", 1 << 31)]
)
def test_child_role_and_parent_validation(probe: Any, role: Any, parent: Any) -> None:
    with pytest.raises(RuntimeError):
        probe.child_command(role, parent)


@pytest.mark.parametrize("mutate", [b"different", b"x" * 16384])
def test_guard_source_never_runs_on_bad_pin(probe: Any, mutate: bytes) -> None:
    probe.GUARD_SOURCE = mutate
    with pytest.raises(RuntimeError, match="GUARD_PIN"):
        probe.load_guard()


def test_verified_guard_can_be_loaded_without_a_syscall(probe: Any) -> None:
    guard = probe.load_guard()
    assert guard.ProcessRole.WORKER.value == "WORKER"


def test_permission_denial_is_specific_and_does_not_leak_error(probe: Any) -> None:
    def denied() -> bool:
        raise OSError(errno.EPERM, "PRIVATE_ERROR_MARKER")

    assert probe.permission_call(denied) == {"allowed": False, "equal": False, "errno": 1}
    assert probe.permission_call(lambda: True) == {"allowed": True, "equal": True, "errno": 0}


@pytest.mark.parametrize("number", [errno.ENOENT, errno.EIO, errno.ESRCH])
def test_missing_or_broken_target_is_not_security_success(probe: Any, number: int) -> None:
    def broken() -> None:
        raise OSError(number, "not denial")

    with pytest.raises(RuntimeError, match="ACCESS_NOT_PERMISSION"):
        probe.permission_call(broken)


@pytest.mark.parametrize("blocks", [[b"{}\nextra"], [b"{}\n{}\n"], [b"x" * 16385], [b""]])
def test_ready_frame_is_closed(probe: Any, monkeypatch: Any, blocks: list[bytes]) -> None:
    stream = types.SimpleNamespace(fileno=lambda: 5)
    monkeypatch.setattr(probe.select, "select", lambda *_args: ([5], [], []))
    monkeypatch.setattr(probe.os, "read", lambda *_args: blocks.pop(0))
    with pytest.raises(RuntimeError):
        probe.read_line(stream)


def test_ready_wait_is_deadline_bounded_and_partial_reads_are_allowed(
    probe: Any, monkeypatch: Any
) -> None:
    stream = types.SimpleNamespace(fileno=lambda: 5)
    blocks = [b'{"ready":', b"true}\n"]
    monkeypatch.setattr(probe.select, "select", lambda *_args: ([5], [], []))
    monkeypatch.setattr(probe.os, "read", lambda *_args: blocks.pop(0))
    assert probe.read_line(stream) == {"ready": True}
    monkeypatch.setattr(probe.select, "select", lambda *_args: ([], [], []))
    with pytest.raises(RuntimeError, match="READY_TIMEOUT"):
        probe.read_line(stream)


@pytest.mark.parametrize(
    "role,parent",
    [
        ("bad", "1"),
        ("protected", "-1"),
        ("protected", "0"),
        ("protected", " 1"),
        ("protected", "\u0661"),
    ],
)
def test_main_refuses_unknown_and_noncanonical_args_before_child(
    probe: Any, monkeypatch: Any, role: str, parent: str
) -> None:
    monkeypatch.setattr(sys, "argv", ["-c", role, parent])
    monkeypatch.setattr(probe, "child", lambda *_args: pytest.fail("child ran"))
    with pytest.raises(RuntimeError):
        probe.main()


def test_spawn_uses_exact_env_close_fds_and_no_shell(probe: Any, monkeypatch: Any) -> None:
    calls = []
    monkeypatch.setattr(probe.subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
    probe.spawn("protected", 1)
    args, options = calls[0]
    assert args[0] == probe.child_command("protected", 1)
    assert options["env"] == probe.environment() and options["close_fds"] is True
    assert "shell" not in options and "pass_fds" not in options


def test_error_diagnostic_stays_small_even_with_both_controls(probe: Any) -> None:
    # Public addresses/metadata only. No memory or environ content is serialized.
    value = {
        "positive": {"mem": {"allowed": True, "equal": True}},
        "negative": {"mem": {"allowed": False}},
    }
    assert len(json.dumps(value)) < probe.MAX_LINE
    assert probe.CANARY.startswith(b"PUBLIC_")


def test_reap_kills_before_pipe_close_and_checks_completion(probe: Any) -> None:
    events = []
    state: dict[str, int | None] = {"code": None}

    def kill() -> None:
        events.append("kill")
        state["code"] = -9

    def stream() -> Any:
        result = types.SimpleNamespace(closed=False)

        def close() -> None:
            events.append("close")
            result.closed = True

        result.close = close
        return result

    process = types.SimpleNamespace(
        poll=lambda: state["code"],
        kill=kill,
        wait=lambda **_kwargs: events.append("wait"),
        stdin=stream(),
        stdout=stream(),
        stderr=None,
        returncode=-9,
    )
    assert probe.reap(process) == -9
    assert events == ["kill", "wait", "close", "close"]


def test_wrong_parent_uses_a_pid_distinct_from_self_and_actual_parent(
    probe: Any, monkeypatch: Any
) -> None:
    system = types.SimpleNamespace(
        dumpable=lambda: 1, get_limit=lambda _name: (384 * probe.MIB,) * 2
    )
    calls = []

    def refuse(**kwargs: Any) -> None:
        expected = kwargs["expected_parent_pid"]
        assert expected not in {33, 1}
        calls.append(expected)
        raise linux_guard.ProcessGuardError(linux_guard.GuardFailure.PARENT)

    fake = types.SimpleNamespace(
        _LinuxSystem=lambda: system,
        protect_process=refuse,
        ProcessRole=linux_guard.ProcessRole,
        ProcessGuardError=linux_guard.ProcessGuardError,
    )
    monkeypatch.setattr(probe, "load_guard", lambda: fake)
    monkeypatch.setattr(probe.os, "getpid", lambda: 33)
    monkeypatch.setattr(probe.os, "getppid", lambda: 1)
    monkeypatch.setattr(probe.os, "environ", probe.environment())
    reports: list[dict[str, Any]] = []
    monkeypatch.setattr(probe, "emit", reports.append)
    probe.child("wrong-parent", 1)
    assert calls and reports[0]["ready"] is False
    assert reports[0]["as_unchanged"] is True and reports[0]["dumpable"] == 1
