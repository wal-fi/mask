"""Specific T4 identity fakes; one explicitly named native own-child proof."""

import base64
import ctypes
import hashlib
import json
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
CREATED = 134375857978266391
BASE_SHA = "ff9b669828a66882f3d43ed2f9192ea9d8a08f80b8ffbc2186ee946823394418"


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_identity.py"))


@pytest.mark.parametrize("pid", [False, 0, -1, 2**32, "123"])
def test_pid_must_be_exact_positive_uint32(module, pid):
    with pytest.raises(module["IdentityError"], match="IDENTITY_UNKNOWN"):
        module["Birth"](pid, CREATED)


@pytest.mark.parametrize("value", [False, 0, -1, 2**63, 1.25, str(CREATED)])
def test_creation_time_is_exact_positive_int64(module, value):
    with pytest.raises(module["IdentityError"], match="IDENTITY_UNKNOWN"):
        module["Birth"](123, value)


def test_template_retains_one_process_handle_and_never_kills_again_by_pid(module):
    birth = module["Birth"](123, CREATED)
    script = module["kill_script"](birth)
    assert script.count("GetProcessById(") == 1
    assert (
        script.index("[void]$p.Handle") < script.index("$p.StartTime") < script.index("$p.Kill()")
    )
    assert "Stop-Process" not in script and "WaitForExit(3000)" in script
    assert str(CREATED) in script and "$p.Dispose()" in script
    args = module["kill_args"](birth)
    assert args[0] == module["SHELL"] and args[-2] == "-EncodedCommand"
    assert base64.b64decode(args[-1]).decode("utf-16-le") == script


@pytest.mark.parametrize("result", ["success", "failure", "error", "zero"])
def test_getprocesstimes_only_borrows_original_handle_and_never_looks_up_pid(
    module, monkeypatch, result
):
    called = []

    class Function:
        argtypes: Any = None
        restype: Any = None

        def __call__(self, handle, created, _exit, _kernel, _user):
            called.append(handle.value)
            if result == "error":
                raise OSError("public-marker-must-not-escape")
            value = 0 if result == "zero" else CREATED
            created._obj.dwHighDateTime = value >> 32
            created._obj.dwLowDateTime = value & 0xFFFFFFFF
            return result != "failure"

    fake = SimpleNamespace(
        WinDLL=lambda *_args, **_kwargs: SimpleNamespace(GetProcessTimes=Function()),
        POINTER=ctypes.POINTER,
        byref=ctypes.byref,
    )
    api = module["raw_filetime"].__globals__
    monkeypatch.setitem(api, "ctypes", fake)
    monkeypatch.setitem(api, "sys", SimpleNamespace(platform="win32", version_info=(3, 11, 3)))
    if result == "success":
        assert module["raw_filetime"](777) == CREATED
    else:
        with pytest.raises(module["IdentityError"], match="IDENTITY_UNKNOWN") as caught:
            module["raw_filetime"](777)
        assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert called == [777]  # fake has no OpenProcess/CloseHandle to call


def test_capture_from_adopted_process_uses_borrowed_handle_without_await(module, monkeypatch):
    seen = []

    def raw(handle):
        seen.append(handle)
        return CREATED

    monkeypatch.setitem(module["capture"].__globals__, "raw_filetime", raw)
    process = SimpleNamespace(
        pid=123, _transport=SimpleNamespace(_proc=SimpleNamespace(_handle=777))
    )
    assert module["capture"](process) == module["Birth"](123, CREATED)
    assert seen == [777]
    assert module["capture"](None) is None
    assert module["capture"](SimpleNamespace(pid=123)) is None


@pytest.mark.parametrize("status", ["KILLED", "ABSENT", "IDENTITY_MISMATCH", "ERROR"])
def test_report_is_closed_and_uint64_not_rounded_through_json(module, status):
    birth = module["Birth"](123, CREATED)
    value = {
        "status": status,
        "pid": 123,
        "observed_filetime": str(CREATED + 1 if status == "IDENTITY_MISMATCH" else CREATED),
    }
    raw = json.dumps(value).encode()
    assert module["parse_report"](raw, birth) == value
    value["seed"] = "public-marker-must-not-escape"
    with pytest.raises(module["IdentityError"]):
        module["parse_report"](json.dumps(value).encode(), birth)


@pytest.mark.parametrize(
    "value", [CREATED, "01", "-1", "+1", "\uff11\uff12\uff13", "0", str(2**63)]
)
def test_report_does_not_accept_numeric_or_noncanonical_time(module, value):
    raw = json.dumps({"status": "KILLED", "pid": 123, "observed_filetime": value}).encode()
    with pytest.raises(module["IdentityError"]):
        module["parse_report"](raw, module["Birth"](123, CREATED))


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows own-process identity proof")
def test_native_original_handle_matches_ps_and_kills_only_own_process(module):
    """Run only AFTER its exact script/command review. No Docker or private bytes.

    Use the base interpreter directly: the venv redirector would create a second
    Python process, and killing only that wrapper would leave its child alive.
    """
    private_sys: Any = sys
    base_python = Path(private_sys._base_executable)
    assert base_python == Path(
        "C:/Users/w.filho/AppData/Local/Programs/Python/Python311/python.exe"
    )
    # Actual binary pin is filled/checked before this native proof is executed.
    assert hashlib.sha256(base_python.read_bytes()).hexdigest() == BASE_SHA
    channel = runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_channel.py"))
    environment = channel["environment"]()
    child = subprocess.Popen(  # noqa: S603
        [str(base_python), "-I", "-B", "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=environment,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        private_child: Any = child
        created = module["raw_filetime"](int(private_child._handle))
        for adjustment, expected in ((1, "IDENTITY_MISMATCH"), (0, "KILLED")):
            birth = module["Birth"](child.pid, created + adjustment)
            reply = subprocess.run(  # noqa: S603
                module["kill_args"](birth),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=environment,
                timeout=8,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            assert reply.returncode == 0
            result = module["parse_report"](reply.stdout, birth)
            assert result["status"] == expected
            assert result["observed_filetime"] == str(created)
            if adjustment:
                assert child.poll() is None  # mismatched FILETIME never kills
        child.wait(timeout=3)
        assert child.returncode is not None
    finally:
        if child.poll() is None:
            child.kill()  # original owned handle, never a PID lookup
        child.wait(timeout=5)
