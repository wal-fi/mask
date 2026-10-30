"""Closed transfer admission/fake wheelhouse, no network or package execution."""

import copy
import hashlib
import runpy
from pathlib import Path
from typing import Any

import pytest

M = runpy.run_path(str(Path(__file__).resolve().parents[1] / "docs/poc/oracle9_wheels_download.py"))


def entry() -> dict[str, Any]:
    return {
        "name": "sample",
        "version": "1.0",
        "filename": "sample-1.0-py3-none-any.whl",
        "url": "https://files.pythonhosted.org/packages/aa/sample-1.0-py3-none-any.whl",
        "sha256": hashlib.sha256(b"fake-public-not-a-wheel").hexdigest(),
    }


def house(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    v = entry()
    (tmp_path / "wheels").mkdir()
    (tmp_path / "wheels" / v["filename"]).write_bytes(b"fake-public-not-a-wheel")
    (tmp_path / "requirements.dependencies.lock").write_bytes(M["lock_bytes"]([v]))
    manifest = {
        "kind": "oracle9-closed-wheels-v1",
        "source_evidence_sha256": M["EVIDENCE_SHA"],
        "files": [dict(v, bytes=23)],
        "total_bytes": 23,
    }
    return v, manifest


def test_frozen_resolution_selects_36_wheels_without_network_or_zip():
    files = M["selected_files"]()
    assert len(files) == 36 and len({v["name"] for v in files}) == 36
    assert all(v["url"].startswith("https://files.pythonhosted.org/packages/") for v in files)


def test_download_verification_is_not_zip_or_installation_acceptance(tmp_path):
    v, manifest = house(tmp_path)
    # Deliberately not a ZIP: stage D validates only already selected bytes/hash.
    assert M["check_wheelhouse"](tmp_path, [v], manifest) == 23


@pytest.mark.parametrize(
    "bad", ["missing", "extra", "changed", "source", "size", "total", "lock", "url", "extra-key"]
)
def test_extra_missing_or_altered_wheel_never_closes_manifest(tmp_path, bad):
    v, manifest = house(tmp_path)
    file = tmp_path / "wheels" / v["filename"]
    if bad == "missing":
        file.unlink()
    elif bad == "extra":
        (tmp_path / "wheels" / "unlisted").write_bytes(b"unknown")
    elif bad == "changed":
        file.write_bytes(b"x" * 23)
    elif bad == "source":
        manifest["source_evidence_sha256"] = "0" * 64
    elif bad == "size":
        manifest["files"][0]["bytes"] = True
    elif bad == "total":
        manifest["total_bytes"] = 22
    elif bad == "lock":
        (tmp_path / "requirements.dependencies.lock").write_bytes(b"different")
    elif bad == "url":
        manifest["files"][0]["url"] = "https://different.invalid"
    else:
        manifest["extra"] = True
    with pytest.raises(RuntimeError):
        M["check_wheelhouse"](tmp_path, [v], manifest)


def test_native_curl_options_disable_extra_configuration_and_redirects(tmp_path):
    v = entry()
    argv = M["curl_args"](tmp_path / v["filename"], v, [v], 1234)
    assert argv[1] == "-q" and argv[argv.index("--noproxy") + 1] == "*"
    assert argv[argv.index("--max-filesize") + 1] == "1234"
    assert argv[argv.index("--retry") + 1] == "0"
    assert argv[argv.index("--proto") + 1] == "=https"
    assert "--insecure" not in argv and "--location" not in argv and "--netrc" not in argv
    assert "--no-ssl-auto-client-cert" in argv


@pytest.mark.parametrize("bad", ["foreign", "http", "redirect-host", "name", "zero", "oversize"])
def test_only_exact_selected_https_file_can_be_requested(tmp_path, bad):
    v = entry()
    allowed = [copy.deepcopy(v)]
    path, limit = tmp_path / v["filename"], 1024
    if bad == "foreign":
        v["sha256"] = "0" * 64
    elif bad in ("http", "redirect-host"):
        v["url"] = (
            v["url"].replace("https:", "http:")
            if bad == "http"
            else "https://elsewhere.invalid/file.whl"
        )
        allowed = [v]
    elif bad == "name":
        path = tmp_path / "wrong.whl"
    elif bad == "zero":
        limit = 0
    else:
        limit = M["MAX_FILE"] + 1
    with pytest.raises(RuntimeError):
        M["curl_args"](path, v, allowed, limit)


def test_transfer_env_does_not_inherit_proxy_or_credentials(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "private-canary")
    monkeypatch.setenv("MASKGW_TEST_DSN", "private-canary")
    monkeypatch.setenv("CURL_CA_BUNDLE", "private-canary")
    assert not any("private-canary" in v for v in M["environment"]().values())
