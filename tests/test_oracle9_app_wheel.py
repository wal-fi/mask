"""Source capture and synthetic own-wheel checks; never invokes the real backend."""

import base64
import hashlib
import importlib.util
import io
import json
import os
import sys
import types
import zipfile
from pathlib import Path
from typing import Any

import pytest
from packaging.requirements import Requirement

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def builder() -> Any:
    path = REPO / "docs/poc/oracle9_app_wheel.py"
    spec = importlib.util.spec_from_file_location("_app_builder_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_source(tmp_path: Path) -> Path:
    repo = tmp_path / "source-repo"
    package = repo / "src/maskgw"
    package.mkdir(parents=True)
    (repo / "pyproject.toml").write_bytes((REPO / "pyproject.toml").read_bytes())
    (package / "__init__.py").write_bytes(b"raise AssertionError('do not import source')\r\n")
    for index in range(20):
        (package / f"file{index}.py").write_bytes(f"VALUE = {index}\r\n".encode())
    return repo


def synthetic_wheel(path: Path, files: dict[str, bytes], config: Any, bad: str = "") -> None:
    dist = "maskgw-0.1.0.dist-info/"
    values = {k.removeprefix("src/"): v for k, v in files.items() if k != "pyproject.toml"}
    requires = list(config["project"]["dependencies"])
    requires.extend(
        r + '; extra == "dev"' for r in config["project"]["optional-dependencies"]["dev"]
    )
    if bad == "requires":
        requires.pop()
    metadata = (
        "Metadata-Version: 2.4\nName: maskgw\nVersion: 0.1.0\n"
        "Requires-Python: >=3.11\nProvides-Extra: dev\n"
    )
    metadata += "".join("Requires-Dist: " + str(Requirement(v)) + "\n" for v in requires)
    values[dist + "METADATA"] = metadata.encode() + b"\n"
    values[dist + "WHEEL"] = b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n\n"
    values[dist + "top_level.txt"] = b"maskgw\n"
    if bad == "extra":
        values[".env"] = b"must-never-be-packaged"
    elif bad == "bytes":
        values["maskgw/__init__.py"] = b"x" * len(values["maskgw/__init__.py"])
    elif bad == "missing":
        del values["maskgw/__init__.py"]
    elif bad == "entrypoint":
        values[dist + "entry_points.txt"] = b"[console_scripts]\nmaskgw = maskgw:main\n"
    rows = []
    for name, raw in values.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode()
        rows.append(f"{name},sha256={digest},{len(raw)}\n")
    values[dist + "RECORD"] = ("".join(rows) + dist + "RECORD,,\n").encode()
    with zipfile.ZipFile(path, "w", compression=8) as archive:
        for name, raw in values.items():
            archive.writestr(name, raw)


def test_capture_is_byte_exact_no_checkout_mutation(tmp_path, builder):
    repo = fake_source(tmp_path)
    files, config = builder.capture(repo)
    assert len(files) == 22 and config["project"]["name"] == "maskgw"
    assert files["src/maskgw/__init__.py"].endswith(b"\r\n")
    assert all(not name.startswith((".venv", ".git", ".codex")) for name in files)
    destination = tmp_path / "captured"
    builder.copy_source(destination, files)
    assert all((destination / name).read_bytes() == raw for name, raw in files.items())
    assert builder.capture(repo)[0] == files


@pytest.mark.parametrize("bad", ["project", "config", "unknown", "large", "link"])
def test_source_fail_closed_on_changed_project_or_unknown_file(tmp_path, builder, bad):
    repo = fake_source(tmp_path)
    package = repo / "src/maskgw"
    if bad == "project":
        with (repo / "pyproject.toml").open("ab") as f:
            f.write(b"\n")
    elif bad == "large":
        (package / "large.py").write_bytes(b"x" * (1024 * 1024 + 1))
    elif bad == "link":
        try:
            (package / "link.py").symlink_to(package / "__init__.py")
        except OSError:
            pytest.skip("symlink privilege not available")
    else:
        (package / ("settings.yaml" if bad == "config" else ".private")).write_bytes(b"private")
    with pytest.raises(RuntimeError):
        builder.capture(repo)


def test_cache_is_skipped_but_other_directory_is_not_ignored(tmp_path, builder):
    repo = fake_source(tmp_path)
    cache = repo / "src/maskgw/__pycache__"
    cache.mkdir()
    (cache / "generated.pyc").write_bytes(b"ignored-cache")
    files, _ = builder.capture(repo)
    assert all("__pycache__" not in name for name in files)
    private = repo / "src/maskgw/private"
    private.mkdir()
    (private / "catalog.json").write_bytes(b"must-not-package")
    with pytest.raises(RuntimeError, match="SOURCE_ALLOWLIST"):
        builder.capture(repo)


def test_assets_only_at_declared_package_location(tmp_path, builder):
    repo = fake_source(tmp_path)
    assets = repo / "src/maskgw/admin/ui/assets"
    assets.mkdir(parents=True)
    (assets / "ui.js").write_bytes(b"public asset")
    files, _ = builder.capture(repo)
    assert files["src/maskgw/admin/ui/assets/ui.js"] == b"public asset"
    (repo / "src/maskgw/private.js").write_bytes(b"private")
    with pytest.raises(RuntimeError):
        builder.capture(repo)


@pytest.mark.parametrize("bad", ["", "requires", "extra", "bytes", "missing", "entrypoint"])
def test_own_wheel_matches_source_bytes_and_all_requirements(tmp_path, builder, bad):
    files, config = builder.capture(fake_source(tmp_path))
    path = tmp_path / "maskgw-0.1.0-py3-none-any.whl"
    synthetic_wheel(path, files, config, bad)
    if bad:
        with pytest.raises(RuntimeError):
            builder.validate_own_wheel(path, files, config, builder.load_inspector())
    else:
        result = builder.validate_own_wheel(path, files, config, builder.load_inspector())
        assert result["name"] == "maskgw" and not result["entry_points"]
        assert len(result["metadata"]["requires_dist"]) == 14


def test_minimal_environment_never_inherits_secrets(monkeypatch, tmp_path, builder):
    monkeypatch.setenv("MASKGW_TEST_DSN", "private-canary")
    monkeypatch.setenv("HTTPS_PROXY", "private-canary")
    monkeypatch.setenv("PYTHONPATH", "private-canary")
    env = builder.minimal_environment(tmp_path)
    assert "private-canary" not in json.dumps(env)
    assert env["SOURCE_DATE_EPOCH"] == "315532800" and env["PIP_NO_INDEX"] == "1"


def test_backend_logs_are_bounded_in_encoded_bytes(builder):
    log = builder.BoundedLog()
    log.write("a" * (1024 * 1024 - 1))
    with pytest.raises(RuntimeError, match="BUILD_LOG_LIMIT"):
        log.write("é")
    assert len(log.getvalue().encode()) < 1024 * 1024


@pytest.mark.parametrize("fail", [False, True])
def test_fake_backend_restores_environment_cwd_and_keeps_logs(monkeypatch, tmp_path, builder, fail):
    source, output = tmp_path / "source1", tmp_path / "wheel1"
    source.mkdir()
    original_cwd, original_env = Path.cwd(), dict(os.environ)
    monkeypatch.setenv("MASKGW_FAKE_SECRET", "private-canary")
    backend: Any = types.ModuleType("setuptools.build_meta")

    def fake_hook(destination):
        assert Path.cwd() == source and "MASKGW_FAKE_SECRET" not in os.environ
        assert os.environ["SOURCE_DATE_EPOCH"] == "315532800"
        print("public fake backend log")
        if fail:
            raise RuntimeError("fake backend failure")
        name = "maskgw-0.1.0-py3-none-any.whl"
        (Path(destination) / name).write_bytes(b"fake-wheel-no-import")
        return name

    backend.build_wheel = fake_hook
    monkeypatch.setitem(sys.modules, "setuptools.build_meta", backend)
    if fail:
        with pytest.raises(RuntimeError, match="fake backend failure"):
            builder.run_backend(source, output, tmp_path)
    else:
        path, log = builder.run_backend(source, output, tmp_path)
        assert path.name.endswith(".whl") and b"fake backend log" in log
    assert Path.cwd() == original_cwd
    assert os.environ["MASKGW_FAKE_SECRET"] == "private-canary"  # noqa: S105 -- leak-test canary.
    assert all(os.environ[k] == v for k, v in original_env.items() if k != "MASKGW_FAKE_SECRET")
    assert b"public fake backend log" in (tmp_path / "source1-backend.log").read_bytes()


def test_zip_preflight_before_unbounded_central_directory(builder):
    inspector = builder.load_inspector()
    with pytest.raises(RuntimeError):
        inspector["central_preflight"](io.BytesIO(b"not-a-zip"))


def test_declared_build_plugins_are_metadata_only(builder):
    rows = builder.plugin_inventory()
    assert len(rows) == 46
    assert {r["owner"] for r in rows} == {"setuptools", "wheel", "cffi"}
    cffi = [r for r in rows if r["owner"] == "cffi"]
    assert len(cffi) == 1 and cffi[0]["name"] == "cffi_modules"


def test_unknown_build_plugin_refuses_without_loading(monkeypatch, builder):
    original = builder.importlib.metadata.entry_points

    def unexpected(*, group):
        rows = list(original(group=group))
        if group == "setuptools.finalize_distribution_options":
            rows.append(
                types.SimpleNamespace(
                    name="unexpected",
                    value="not_allowed:run",
                    dist=types.SimpleNamespace(metadata={"Name": "unlisted-plugin"}, version="1"),
                    load=lambda: pytest.fail("must never load plugin"),
                )
            )
        return rows

    monkeypatch.setattr(builder.importlib.metadata, "entry_points", unexpected)
    with pytest.raises(RuntimeError, match="BUILD_PLUGIN_SET"):
        builder.plugin_inventory()
