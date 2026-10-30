"""Offline transport-manifest guards; no network or RPM execution."""

import hashlib
import json
import runpy
from pathlib import Path
from typing import Any

import pytest

M = runpy.run_path(str(Path(__file__).resolve().parents[1] / "docs/poc/oracle9_rpm_download.py"))


def bundle(root: Path) -> dict[str, Any]:
    target = root / "bundle"
    target.mkdir()
    rows = M["manifest_rows"]()
    for v in rows:
        data = b"\xed\xab\xee\xdb" + v["filename"].encode()
        (target / v["filename"]).write_bytes(data)
        v["bytes"] = len(data)
        v["sha256"] = hashlib.sha256(data).hexdigest()
    data = b"public probe fake"
    (target / "runtime_probe.py").write_bytes(data)
    payload_sha = hashlib.sha256(data).hexdigest()
    rows.append({"filename": "runtime_probe.py", "bytes": len(data), "sha256": payload_sha})
    mraw = (json.dumps({"kind": "oracle9-rpms-v1", "files": rows}) + "\n").encode()
    (target / "bundle.json").write_bytes(mraw)
    headers = ("\n".join(sorted(v["header"] for v in M["manifest_rows"]())) + "\n").encode()
    (target / "expected-rpms.txt").write_bytes(headers)
    checked = [(v["filename"], v["sha256"]) for v in rows]
    checked += [
        ("bundle.json", hashlib.sha256(mraw).hexdigest()),
        ("expected-rpms.txt", hashlib.sha256(headers).hexdigest()),
    ]
    (target / "inputs.sha256").write_bytes(
        "".join(f"{h}  {n}\n" for n, h in sorted(checked)).encode()
    )
    return {
        "payload_sha256": payload_sha,
        "bundle_manifest_sha256": hashlib.sha256(mraw).hexdigest(),
    }


def test_closed_nine_package_origins_and_finite_transport(tmp_path):
    rows = M["manifest_rows"]()
    assert len(rows) == len({v["filename"] for v in rows}) == 9
    for v in rows:
        args = M["curl_args"](tmp_path / "own.part", v["url"], 12345)
        assert args[1] == "-q"
        for flag, value in (
            ("--noproxy", "*"),
            ("--proto", "=https"),
            ("--max-time", "30"),
            ("--connect-timeout", "10"),
            ("--max-filesize", "12345"),
            ("--max-redirs", "0"),
        ):
            assert args[args.index(flag) + 1] == value
        assert "--location" not in args and "--insecure" not in args and "--retry" not in args
        assert "--no-ssl-auto-client-cert" in args


@pytest.mark.parametrize(
    "url",
    [
        "http://yum.oracle.com/x",
        "https://evil.test/x",
        "https://yum.oracle.com/private",
        "file:///etc/passwd",
    ],
)
def test_unlisted_urls_never_reach_curl(tmp_path, url):
    with pytest.raises(RuntimeError):
        M["curl_args"](tmp_path / "own.part", url, 100)


def test_proxy_and_client_identity_settings_do_not_cross(monkeypatch):
    for name in (
        "HTTPS_PROXY",
        "ALL_PROXY",
        "CURL_HOME",
        "HOME",
        "MASKGW_ADMIN_TOKEN",
        "SSLKEYLOGFILE",
    ):
        monkeypatch.setenv(name, "DO_NOT_COPY")
    assert all(v != "DO_NOT_COPY" for v in M["environment"]().values())


def test_exact_bundle_passes_without_claiming_signature(tmp_path):
    state = bundle(tmp_path)
    value = M["check_bundle"](tmp_path, state)
    assert len(value["files"]) == 10


def test_ready_copy_cannot_start_a_second_download(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    root = tmp_path / "Temp" / "maskgw-oracle9-python-20261023-00000000"
    root.mkdir(parents=True)
    state = {
        "kind": "maskgw-oracle9-python",
        "invoked": False,
        "desktop_initial": "unobserved",
        "bundle_download_invoked": False,
        "bundle_ready": True,
    }
    raw = json.dumps(state).encode()
    (root / "attempt.json").write_bytes(raw)
    with pytest.raises(RuntimeError):
        M["main"](root)
    assert (root / "attempt.json").read_bytes() == raw


@pytest.mark.parametrize("change", ["extra", "hash", "missing", "headers", "sums"])
def test_modified_bundle_cannot_be_copied_into_container(tmp_path, change):
    state = bundle(tmp_path)
    root = tmp_path / "bundle"
    name = M["manifest_rows"]()[0]["filename"]
    if change == "extra":
        (root / "extra-secret").write_bytes(b"x")
    elif change == "hash":
        (root / name).write_bytes(b"\xed\xab\xee\xdbTAMPERED")
    elif change == "missing":
        (root / name).unlink()
    elif change == "headers":
        (root / "expected-rpms.txt").write_bytes(b"other\n")
    else:
        (root / "inputs.sha256").write_bytes(b"other\n")
    with pytest.raises((RuntimeError, FileNotFoundError)):
        M["check_bundle"](tmp_path, state)
