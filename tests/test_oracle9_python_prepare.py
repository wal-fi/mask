"""Security refusals of the disposable vendor-runtime preparation, no Docker."""

import base64
import copy
import hashlib
import json
import runpy
import zlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

M = runpy.run_path(str(Path(__file__).resolve().parents[1] / "docs/poc/oracle9_python_prepare.py"))


def report() -> dict[str, Any]:
    return {
        "directories": ["/usr", "/etc", "/usr/bin", "/var/log"],
        "new_paths": ["/usr/bin/python3.11", "/etc/vendor.conf"],
        "passwd_group_literal_append": True,
        "empty_dirs": {"/tmp": True, "/var/tmp": True, "/var/empty": True},  # noqa: S108
        "linker_cache": {
            "before": {"kind": "regular", "sha256": "a" * 64},
            "after": {"owner": ["glibc", "x86_64"], "kind": "regular"},
        },
    }


@pytest.mark.parametrize(
    "row",
    [
        "C /usr/bin",
        "A /usr/bin/python3.11",
        "A /etc/vendor.conf",
        "C /etc/passwd",
        "C /etc/group",
        "C /etc/ld.so.cache",
        "A /opt/maskgw/venv/bin/python",
        "C /usr/lib/sysimage/rpm/rpmdb.sqlite",
        "C /var/log",
        "C /tmp",
        "C /var/tmp",
        "A /var/empty",
    ],
)
def test_only_declared_changes_can_be_committed(row):
    M["validate_diff"]((row + "\n").encode(), report())


@pytest.mark.parametrize(
    "row",
    [
        "D /usr/bin/bash",
        "C /usr/bin/bash",
        "A /usr/bin/rogue",
        "C /etc/shadow",
        "A /etc/rogue",
        "C /root",
        "A /root/.cache/pip/x",
        "A /tmp/secret",
        "A /var/log/dnf.log",
        "A /var/cache/dnf",
        "C /var/cache/dnf",
        "A /var/cache/dnf/unknown",
        "C /etc/yum.repos.d/vendor.repo",
        "A /run/state",
        "X /usr/bin/python3.11",
        "A relative",
    ],
)
def test_unowned_old_or_extra_files_refuse_commit(row):
    with pytest.raises(RuntimeError):
        M["validate_diff"]((row + "\n").encode(), report())


def prepared_image() -> dict[str, Any]:
    return {
        "Id": "sha256:" + "a" * 64,
        "Os": "linux",
        "Architecture": "amd64",
        "RepoTags": ["maskgw-oracle9-python:own-task"],
        "RootFS": {"Layers": [*M["BASE_LAYERS"], "sha256:" + "b" * 64]},
        "Config": {
            "User": "10001:10001",
            "WorkingDir": "/var/empty",
            "Entrypoint": M["ENTRY"],
            "Env": M["ENV"],
            "Labels": {"maskgw.task": "own-task"},
        },
    }


def test_image_identity_comes_only_from_complete_inspected_metadata():
    value = prepared_image()
    assert (
        M["validate_prepared_image"](value, "own-task", "maskgw-oracle9-python:own-task")
        == value["Id"]
    )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("Id",), "not-an-image"),
        (("Os",), "windows"),
        (("Architecture",), "arm64"),
        (("RepoTags",), ["other:tag"]),
        (("RootFS", "Layers"), ["sha256:" + "a" * 64]),
        (("Config", "User"), "0:0"),
        (("Config", "WorkingDir"), "/root"),
        (("Config", "Entrypoint"), ["/bin/bash"]),
        (("Config", "Cmd"), ["--extra"]),
        (("Config", "Env"), ["SECRET=untrusted"]),
        (("Config", "Labels", "maskgw.task"), "other-task"),
        (("Config", "Volumes"), {"/volume": {}}),
        (("Config", "ExposedPorts"), {"80/tcp": {}}),
        (("Config", "Healthcheck"), {"Test": ["CMD", "unexpected"]}),
    ],
)
def test_image_cannot_be_selected_by_tag_without_its_identity_profile(path, value):
    image = prepared_image()
    node = image
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(RuntimeError):
        M["validate_prepared_image"](image, "own-task", "maskgw-oracle9-python:own-task")


def test_forged_owner_proof_outside_vendor_trees_is_not_authority():
    r = report()
    r["new_paths"].append("/root/secret")
    with pytest.raises(RuntimeError):
        M["validate_diff"](b"A /root/secret\n", r)


def test_nonempty_tmp_and_unproved_account_edits_refuse():
    r = report()
    r["empty_dirs"]["/tmp"] = False  # noqa: S108 -- no filesystem operation
    with pytest.raises(RuntimeError):
        M["validate_diff"](b"C /tmp\n", r)
    r["passwd_group_literal_append"] = False
    with pytest.raises(RuntimeError):
        M["validate_diff"](b"C /etc/passwd\n", r)


def test_nonempty_var_empty_refuses_commit():
    r = report()
    r["empty_dirs"]["/var/empty"] = False
    with pytest.raises(RuntimeError):
        M["validate_diff"](b"A /var/empty\n", r)


def test_gpg_keys_are_separate_from_packages_and_each_other():
    payload = runpy.run_path(str(Path(M["PAYLOAD"])))
    rows, keys = payload["inventory"](
        "gpg-pubkey|(none)|0|aaaa0000|1234\n"
        "gpg-pubkey|(none)|0|bbbb0000|5678\n"
        "python3.11|x86_64|0|3.11.13|10.0.1.el9_8\n"
    )
    assert set(rows) == {("python3.11", "x86_64")}
    assert set(keys) == {("aaaa0000", "1234"), ("bbbb0000", "5678")}
    with pytest.raises(RuntimeError):
        payload["inventory"]("gpg-pubkey|(none)|0|a|1\ngpg-pubkey|(none)|0|a|1\n")


def test_duplicate_package_versions_are_never_accepted():
    payload = runpy.run_path(str(Path(M["PAYLOAD"])))
    with pytest.raises(RuntimeError):
        payload["inventory"]("python3.11|x86_64|0|3.11.13|9\npython3.11|x86_64|0|3.11.13|10\n")


def test_compressed_summary_has_bounded_exact_single_stream():
    data = json.dumps({"new_paths": ["/usr/bin/python3.11"]}).encode()
    packed = zlib.compress(data)
    wire = {
        "encoding": "zlib-base64-v1",
        "raw_bytes": len(data),
        "data": base64.b64encode(packed).decode(),
    }
    assert M["decode_summary"](json.dumps(wire)) == json.loads(data)
    for bad in (packed[:-1], packed + b"junk", packed + packed):
        w = dict(wire, data=base64.b64encode(bad).decode())
        with pytest.raises(RuntimeError):
            M["decode_summary"](json.dumps(w))
    for size in (True, -1, 2 * 1024 * 1024 + 1, len(data) + 1):
        with pytest.raises(RuntimeError):
            M["decode_summary"](json.dumps(dict(wire, raw_bytes=size)))


def test_compressed_summary_expansion_cannot_exceed_limit():
    bomb = zlib.compress(b" " * (2 * 1024 * 1024 + 1))
    wire = {
        "encoding": "zlib-base64-v1",
        "raw_bytes": 2 * 1024 * 1024,
        "data": base64.b64encode(bomb).decode(),
    }
    with pytest.raises(RuntimeError):
        M["decode_summary"](json.dumps(wire))


def profile() -> dict[str, Any]:
    return {
        "Config": {
            "Image": "base",
            "Env": [M["PATH_ENV"]],
            "User": "0:0",
            "Entrypoint": ["/bin/bash"],
            "Cmd": ["-c", "fixed"],
            "Healthcheck": {"Test": ["NONE"]},
        },
        "Mounts": [],
        "HostConfig": {
            "ReadonlyRootfs": False,
            "Privileged": False,
            "Memory": 2 * 1024 * 1024 * 1024,
            "MemorySwap": 2 * 1024 * 1024 * 1024,
            "PidsLimit": 64,
            "NanoCpus": 1000000000,
            "ShmSize": 1048576,
            "NetworkMode": "none",
            "IpcMode": "private",
            "CgroupnsMode": "private",
            "CapDrop": ["ALL"],
            "CapAdd": sorted(M["PREP_CAPS"]),
            "SecurityOpt": ["no-new-privileges=true"],
            "RestartPolicy": {"Name": "no"},
            "LogConfig": {"Type": "none"},
            "Ulimits": [
                {"Name": "nofile", "Soft": 256, "Hard": 256},
                {"Name": "core", "Soft": 0, "Hard": 0},
            ],
        },
    }


@pytest.mark.parametrize(
    ("group", "key", "value"),
    [
        ("Config", "Env", [M["PATH_ENV"], "HTTPS_PROXY=http://host:123"]),
        ("Config", "User", "root"),
        ("HostConfig", "CapAdd", ["SYS_ADMIN"]),
        ("HostConfig", "Privileged", True),
        ("HostConfig", "MemorySwap", -1),
        ("HostConfig", "Memory", 512 * 1024 * 1024),
        ("HostConfig", "NetworkMode", "host"),
        ("HostConfig", "PidMode", "host"),
        ("HostConfig", "Binds", ["/var/run/docker.sock:/var/run/docker.sock"]),
        ("HostConfig", "LogConfig", {"Type": "json-file"}),
        ("HostConfig", "PortBindings", {"5432/tcp": [{"HostPort": "15432"}]}),
    ],
)
def test_profile_drift_refused_before_start(group, key, value):
    value_profile = copy.deepcopy(profile())
    value_profile[group][key] = value
    with pytest.raises(RuntimeError):
        M["profile"](value_profile, "base", ["-c", "fixed"], True)


def test_declared_preparation_and_probe_profiles_are_distinct():
    p = profile()
    M["profile"](p, "base", ["-c", "fixed"], True)
    with pytest.raises(RuntimeError):
        M["profile"](p, "base", ["-c", "fixed"], False)


def test_shell_is_bounded_and_carries_source_without_interpolation():
    payload = Path(M["PAYLOAD"]).read_bytes()
    command = M["shell"](payload, "f" * 32)
    assert len(command) < 25000
    assert "microdnf" not in command and "https://" not in command
    assert "_pkgverify_level all" in command and "signatures OK" in command
    assert "NOKEY" in command and "NOT OK" in command
    assert "--test -i" in command and "-ivh" in command and "-ivvh" not in command
    assert "sha256sum --check inputs.sha256" in command
    assert "python3.11-3.11.13-10.0.1.el9_8.x86_64" in command
    assert "--nogpgcheck" not in command
    assert "test ! -e /opt/maskgw" in command
    assert "/maskgw-rpm-input-" + "f" * 32 in command


def test_builder_caps_are_exact_and_never_apply_to_probe():
    p = profile()
    p["HostConfig"]["CapAdd"] = [v.removeprefix("CAP_") for v in sorted(M["PREP_CAPS"])]
    M["profile"](p, "base", ["-c", "fixed"], True)
    p["HostConfig"]["CapAdd"].append("CAP_CHOWN")
    with pytest.raises(RuntimeError):
        M["profile"](p, "base", ["-c", "fixed"], True)


def test_download_bundle_and_installed_inventory_have_identical_nine_pins():
    dl = runpy.run_path(str(Path(M["DOWNLOADER"])))
    p = runpy.run_path(str(Path(M["PAYLOAD"])))
    expected = {(n, a): ("0", v, r) for _, n, v, r, a in dl["RPM_ROWS"]}
    assert p["EXPECTED"] == expected


def test_rpm_warning_or_error_remains_a_refusal_with_public_diagnostic(monkeypatch, capsys):
    p = runpy.run_path(str(Path(M["PAYLOAD"])))
    for rc, stderr in ((0, b"public package warning"), (2, b"")):
        monkeypatch.setattr(
            p["subprocess"],
            "run",
            lambda *_, _rc=rc, _stderr=stderr, **_kw: SimpleNamespace(
                returncode=_rc, stdout=b"", stderr=_stderr
            ),
        )
        with pytest.raises(RuntimeError):
            p["rpm"]("-Va", allow_verify=True)
        assert "@@RPM_DIAGNOSTIC@@" in capsys.readouterr().out


def test_copy_origin_cannot_substitute_a_package_with_the_same_header():
    rows = [
        {
            "filename": str(i) + ".rpm",
            "url": "fixed",
            "header": "same",
            "bytes": 12345,
            "sha256": "a" * 64,
        }
        for i in range(9)
    ]
    source: dict[str, Any] = {
        "kind": "oracle9-rpms-v1",
        "files": [*rows, {"filename": "runtime_probe.py", "sha256": "old"}],
    }
    raw = json.dumps(source).encode()
    sha = hashlib.sha256(raw).hexdigest()
    current = copy.deepcopy(source)
    current["files"][-1]["sha256"] = "new"
    M["verify_copy_origin"](current, raw, sha)
    for field, value in (("sha256", "b" * 64), ("bytes", 12346), ("url", "changed")):
        bad = copy.deepcopy(current)
        bad["files"][0][field] = value
        with pytest.raises(RuntimeError):
            M["verify_copy_origin"](bad, raw, sha)
    with pytest.raises(RuntimeError):
        M["verify_copy_origin"](current, raw + b" ", sha)


def test_verification_difference_is_bounded_and_still_rejected(capsys):
    p = runpy.run_path(str(Path(M["PAYLOAD"])))
    p["compare_verification"]("unchanged\n", "unchanged\n")
    assert not capsys.readouterr().out
    after = "".join("S.5....T. /usr/public-" + str(i) + "-" + "x" * 1000 + "\n" for i in range(100))
    with pytest.raises(RuntimeError):
        p["compare_verification"]("old public metadata\n", after)
    out = capsys.readouterr().out
    value = json.loads(out.split("@@RPM_VERIFY_DIFF@@")[1])
    assert value["added_count"] == 100 and value["removed_count"] == 1
    assert len(value["added"]) == 40 and all(len(v) <= 512 for v in value["added"])


def test_duplicate_verification_lines_are_not_silently_discarded(capsys):
    p = runpy.run_path(str(Path(M["PAYLOAD"])))
    with pytest.raises(RuntimeError):
        p["compare_verification"]("same\n", "same\nsame\n")
    assert json.loads(capsys.readouterr().out.split("@@RPM_VERIFY_DIFF@@")[1])["added_count"] == 1
