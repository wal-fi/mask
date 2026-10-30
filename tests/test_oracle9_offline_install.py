"""Native installation policy with fake snapshots/processes, no Docker or pip."""

import base64
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def native(tmp_path: Path, monkeypatch: Any) -> Any:
    path = Path(__file__).resolve().parents[1] / "deploy/oracle9_offline_install.py"
    spec = importlib.util.spec_from_file_location("_native_policy_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    prefix = tmp_path / "venv"
    site = prefix / "lib/python3.11/site-packages"
    site.mkdir(parents=True)
    monkeypatch.setattr(module, "PREFIX", prefix)
    monkeypatch.setattr(module, "SITE", site)
    monkeypatch.setattr(module, "TEMP_ROOT", tmp_path)
    return module


def file_row(raw: bytes) -> dict[str, Any]:
    return {
        "kind": "file",
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "uid": 0,
        "gid": 0,
        "mode": 0o644,
    }


def record_row(path: str, raw: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode()
    return f"{path},sha256={digest},{len(raw)}\n"


def installed_case(
    native: Any, monkeypatch: Any
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    wheels = [{"name": f"pkg{n}", "version": "1.0"} for n in range(37)]
    manifest: dict[str, Any] = {"wheels": wheels, "installed_files": {}, "console_scripts": {}}
    baseline = b"base remains unchanged"
    (native.PREFIX / "baseline.txt").write_bytes(baseline)
    before = {"baseline.txt": file_row(baseline)}
    for wheel in wheels:
        name = wheel["name"]
        folder = name + "-1.0.dist-info"
        directory = native.SITE / folder
        directory.mkdir()
        rows = []
        for basename, raw in (("INSTALLER", b"pip\n"), ("REQUESTED", b"")):
            (directory / basename).write_bytes(raw)
            rows.append(record_row(folder + "/" + basename, raw))
        if name == "pkg0":
            raw = b"original package bytes"
            (native.SITE / "payload.py").write_bytes(raw)
            rows.append(record_row("payload.py", raw))
            manifest["installed_files"]["payload.py"] = {
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "owner": name,
                "rewritten_record": False,
            }
            bin_dir = native.PREFIX / "bin"
            bin_dir.mkdir()
            script = ("#!" + sys.executable + "\n# generated wrapper\n").encode()
            (bin_dir / "mcp").write_bytes(script)
            rows.append(record_row("../../../bin/mcp", script))
            manifest["console_scripts"]["mcp"] = {"owner": name, "target": "pkg0:main"}
        relative = folder + "/RECORD"
        (directory / "RECORD").write_bytes(("".join(rows) + relative + ",,\n").encode())
        manifest["installed_files"][relative] = {
            "bytes": 1,
            "sha256": "0" * 64,
            "owner": name,
            "rewritten_record": True,
        }
    after = {}
    for path in native.PREFIX.rglob("*"):
        relative = path.relative_to(native.PREFIX).as_posix()
        after[relative] = (
            file_row(path.read_bytes())
            if path.is_file()
            else {"kind": "directory", "uid": 0, "gid": 0, "mode": 0o755}
        )
    monkeypatch.setattr(
        native, "versions", lambda: {v["name"]: v["version"] for v in wheels} | native.BASE_TOOLS
    )
    return manifest, before, after


def test_installed_sources_generated_records_and_wrappers_match(native, monkeypatch):
    manifest, before, after = installed_case(native, monkeypatch)
    versions = native.verify_install(manifest, before, after)
    assert len(versions) == 39 and versions["pkg0"] == "1.0"


@pytest.mark.parametrize(
    "bad",
    [
        "bytes",
        "extra",
        "pyc",
        "direct-url",
        "base",
        "version",
        "symlink",
        "installer",
        "shebang",
        "record",
    ],
)
def test_installation_cannot_hide_modification_or_extra(native, monkeypatch, bad):
    manifest, before, after = installed_case(native, monkeypatch)
    relative = "lib/python3.11/site-packages/payload.py"
    if bad == "bytes":
        after[relative]["sha256"] = "0" * 64
    elif bad in ("extra", "pyc", "direct-url"):
        name = {
            "extra": "unlisted.py",
            "pyc": "__pycache__/extra.pyc",
            "direct-url": "pkg0-1.0.dist-info/direct_url.json",
        }[bad]
        after["lib/python3.11/site-packages/" + name] = file_row(b"extra")
    elif bad == "base":
        after["baseline.txt"]["sha256"] = "0" * 64
    elif bad == "version":
        monkeypatch.setattr(native, "versions", lambda: {"extra": "1"})
    elif bad == "symlink":
        after[relative]["kind"] = "link"
    elif bad == "installer":
        (native.SITE / "pkg0-1.0.dist-info/INSTALLER").write_bytes(b"other\n")
    elif bad == "shebang":
        (native.PREFIX / "bin/mcp").write_bytes(b"#!/wrong/python\n")
    else:
        path = native.SITE / "pkg0-1.0.dist-info/RECORD"
        path.write_bytes(path.read_bytes().replace(b"sha256=", b"md5=", 1))
    with pytest.raises(RuntimeError):
        native.verify_install(manifest, before, after)


def test_base_wrapper_collision_refuses(native, monkeypatch):
    manifest, before, after = installed_case(native, monkeypatch)
    before["bin/mcp"] = after["bin/mcp"]
    with pytest.raises(RuntimeError, match="BASE_SCRIPT_COLLISION"):
        native.verify_install(manifest, before, after)


@pytest.mark.parametrize(
    "path", ["/etc/passwd", "../../../../outside", "a\\b", "C:/outside", "bad\nname", "bad\x00name"]
)
def test_record_paths_cannot_escape_or_use_ambiguous_encoding(native, path):
    with pytest.raises(RuntimeError):
        native.record_target(path)


def test_record_accepts_only_declared_bin_destination(native):
    assert native.record_target("../../../bin/mcp") == "bin/mcp"


@pytest.mark.parametrize("change", ["missing", "duplicate", "hash", "self"])
def test_record_coverage_digest_and_self_marker(native, monkeypatch, change):
    manifest, before, after = installed_case(native, monkeypatch)
    path = native.SITE / "pkg0-1.0.dist-info/RECORD"
    rows = path.read_text().splitlines()
    if change == "missing":
        rows = rows[1:]
    elif change == "duplicate":
        rows.append(rows[0])
    elif change == "hash":
        rows[0] = rows[0].replace("sha256=", "sha256=BAD")
    else:
        rows[-1] = rows[-1].replace("RECORD,,", "RECORD,sha256=X,0")
    path.write_bytes(("\n".join(rows) + "\n").encode())
    with pytest.raises(RuntimeError):
        native.verify_install(manifest, before, after)


def test_child_environment_never_inherits_secret_values(native, monkeypatch):
    monkeypatch.setenv("MASKGW_TEST_DSN", "private-canary")
    monkeypatch.setenv("HTTPS_PROXY", "private-canary")
    env = native.child_environment()
    assert "private-canary" not in str(env) and env["PIP_CONFIG_FILE"] == "/dev/null"


@pytest.mark.parametrize("exit_code", [0, 1])
def test_pip_supervision_uses_fixed_flags_and_reaps(native, monkeypatch, exit_code):
    calls: list[tuple[Any, ...]] = []

    class FakeProcess:
        pid = 999999

        def poll(self):
            return exit_code

        def wait(self, timeout=None):
            calls.append(("wait", timeout))
            return exit_code

    def popen(argv, **kwargs):
        assert argv[:6] == [sys.executable, "-I", "-B", "-m", "pip", "--isolated"]
        assert kwargs["start_new_session"] is True
        assert kwargs["env"] == native.child_environment()
        kwargs["stdout"].write(b"public fake pip log")
        return FakeProcess()

    monkeypatch.setattr(native.subprocess, "Popen", popen)
    if exit_code:
        with pytest.raises(RuntimeError, match="PIP_NONZERO"):
            native.run_pip(["check"], "unit-pip")
    else:
        result = native.run_pip(["check"], "unit-pip")
        assert (
            result["exit"] == 0
            and base64.b64decode(result["prefix_base64"]) == b"public fake pip log"
        )
    assert calls == [("wait", None)]


def test_pip_timeout_kills_group_and_waits(native, monkeypatch):
    calls: list[tuple[Any, ...]] = []
    values = iter([0.0, 121.0])

    class FakeProcess:
        pid = 999999

        def poll(self):
            return None

        def wait(self, timeout=None):
            calls.append(("wait", timeout))
            return -9

    monkeypatch.setattr(native.subprocess, "Popen", lambda *_a, **_kw: FakeProcess())
    monkeypatch.setattr(native.time, "monotonic", lambda: next(values))
    monkeypatch.setattr(native.signal, "SIGKILL", 9, raising=False)
    monkeypatch.setattr(
        native.os, "killpg", lambda pid, sig: calls.append(("kill", pid, sig)), raising=False
    )
    with pytest.raises(RuntimeError, match="PIP_TIMEOUT"):
        native.run_pip(["check"], "unit-timeout")
    assert calls[0][0:2] == ("kill", 999999) and calls[1] == ("wait", 5)


def test_failure_diagnostics_keep_public_log_bytes(native):
    raw = b"failed public package install\xff"
    (native.TEMP_ROOT / "pip-install.log").write_bytes(raw)
    result = native.failure_logs()["pip-install"]
    assert base64.b64decode(result["prefix_base64"]) == raw
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()


def test_regular_file_size_bound_before_read(native, tmp_path):
    path = tmp_path / "large"
    path.write_bytes(b"x" * 20)
    with pytest.raises(RuntimeError, match="REGULAR_SIZE"):
        native.read_regular(path, 10)


def test_parent_environment_is_minimal_before_package_import(native, monkeypatch):
    fake = types.SimpleNamespace(
        environ={"MASKGW_TEST_DSN": "private-canary", "HTTPS_PROXY": "private-canary"}
    )
    monkeypatch.setattr(native, "os", fake)
    native.parent_environment()
    assert "private-canary" not in str(fake.environ)
    assert fake.environ["HOME"] == str(native.TEMP_ROOT / "maskgw-home")
    assert (native.TEMP_ROOT / "maskgw-home").is_dir()


def test_input_prefix_cannot_point_at_arbitrary_directory(native, tmp_path):
    with pytest.raises(RuntimeError, match="INPUT_PREFIX"):
        native.load_inputs(tmp_path, "0" * 64)


def test_maximum_failure_logs_fit_host_output_budget(native):
    for name in ("pip-install", "pip-check", "probe-pip-check"):
        (native.TEMP_ROOT / (name + ".log")).write_bytes(b"x" * (1024 * 1024))
    result = native.failure_logs()
    assert len(json.dumps(result).encode()) < 1536 * 1024
    assert all(v["truncated"] is True for v in result.values())


def test_maximum_success_log_has_bounded_encoded_prefix(native, monkeypatch):
    raw = b"\x00" * (1024 * 1024)

    class FakeProcess:
        def poll(self):
            return 0

        def wait(self):
            return 0

    def popen(*_args, **kwargs):
        kwargs["stdout"].write(raw)
        return FakeProcess()

    monkeypatch.setattr(native.subprocess, "Popen", popen)
    result = native.run_pip(["check"], "unit-large")
    assert len(json.dumps(result).encode()) < 400 * 1024
    assert result["truncated"] is True and result["bytes"] == len(raw)


def test_result_budget_is_checked_before_stdout(native, capsys):
    with pytest.raises(RuntimeError, match="RESULT_OUTPUT_LIMIT"):
        native.emit({"too_large": "x" * (1536 * 1024)})
    assert capsys.readouterr().out == ""
    native.emit({"small": True})
    assert json.loads(capsys.readouterr().out) == {"small": True}
