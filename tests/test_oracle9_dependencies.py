"""Resolution report security, no Docker, PyPI access or dependency installation."""

import base64
import copy
import hashlib
import json
import runpy
import zlib
from pathlib import Path
from typing import Any

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "deploy/oracle9_dependencies.py"


def module() -> dict[str, Any]:
    return runpy.run_path(str(SOURCE))


def inputs() -> dict[str, Any]:
    seed = "mcp==2.1.1\n"
    return {
        "requirements": ["mcp>=2.1,<3"],
        "constraints": seed,
        "project_sha256": "a" * 64,
        "seed_sha256": hashlib.sha256(seed.encode()).hexdigest(),
    }


def report() -> dict[str, Any]:
    return {
        "version": "0",
        "pip_version": "22.3.1",
        "environment": {
            "sys_platform": "linux",
            "platform_machine": "x86_64",
            "python_full_version": "3.11.13",
            "implementation_name": "cpython",
            "platform_system": "Linux",
        },
        "install": [
            {
                "is_direct": False,
                "requested": True,
                "download_info": {
                    "url": "https://files.pythonhosted.org/packages/aa/bb/mcp-2.1.1-py3-none-any.whl",
                    "archive_info": {"hash": "sha256=" + "b" * 64},
                },
                "metadata": {"name": "mcp", "version": "2.1.1", "requires_python": ">=3.10"},
            }
        ],
    }


def test_vendor_pip_schema_zero_produces_closed_linux_projection():
    m = module()
    projected = m["project_report"](report(), inputs(), (2, 34))
    assert projected["files"][0]["name"] == "mcp"
    assert projected["files"][0]["sha256"] == "b" * 64
    assert projected["files"][0]["requires_dist"] == []


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("version",), "1"),
        (("pip_version",), "26.2.2"),
        (("environment", "sys_platform"), "win32"),
        (("environment", "python_full_version"), "3.14.8"),
        (("install", 0, "is_direct"), True),
        (("install", 0, "requested"), False),
        (("install", 0, "metadata", "version"), "2.1.2"),
        (("install", 0, "metadata", "name"), "pywin32"),
        (("install", 0, "download_info", "archive_info"), {"hashes": {"sha256": "b" * 64}}),
        (("install", 0, "download_info", "archive_info", "hash"), "md5=" + "b" * 32),
        (("install", 0, "metadata", "requires_dist"), "not-a-list"),
        (("install", 0, "unexpected"), True),
    ],
)
def test_wrong_report_platform_hash_source_or_schema_never_resolves(path, value):
    v = report()
    target: Any = v
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(RuntimeError):
        module()["project_report"](v, inputs(), (2, 34))


@pytest.mark.parametrize(
    "url",
    [
        "http://files.pythonhosted.org/packages/mcp-2.1.1-py3-none-any.whl",
        "https://files.pythonhosted.org.evil/packages/mcp-2.1.1-py3-none-any.whl",
        "https://user@files.pythonhosted.org/packages/mcp-2.1.1-py3-none-any.whl",
        "https://files.pythonhosted.org/packages/mcp-2.1.1-py3-none-any.whl?secret=x",
        "https://files.pythonhosted.org/packages/mcp-2.1.1-py3-none-any.whl#hash=x",
        "https://files.pythonhosted.org/packages/../mcp-2.1.1-py3-none-any.whl",
        "https://files.pythonhosted.org/packages/%2e%2e/mcp-2.1.1-py3-none-any.whl",
        "\nhttps://files.pythonhosted.org/packages/mcp-2.1.1-py3-none-any.whl",
        "https://files.pythonhosted.org/packages/mcp-2.1.1.tar.gz",
    ],
)
def test_only_canonical_public_wheel_url_can_enter_download_plan(url):
    v = report()
    v["install"][0]["download_info"]["url"] = url
    with pytest.raises(RuntimeError):
        module()["project_report"](v, inputs(), (2, 34))


@pytest.mark.parametrize(
    ("tag", "valid"),
    [
        ("py3-none-any", True),
        ("py2.py3-none-any", True),
        ("cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64", True),
        ("cp39-abi3-manylinux_2_28_x86_64", True),
        ("cp312-abi3-manylinux_2_28_x86_64", False),
        ("cp311-cp311-musllinux_1_2_x86_64", False),
        ("cp311-cp311-linux_x86_64", False),
        ("cp311-cp311-manylinux_2_35_x86_64", False),
        ("cp311-cp311-manylinux_2_28_aarch64", False),
        ("cp311-cp311-win_amd64", False),
    ],
)
def test_wheel_tags_match_actual_interpreter_architecture_and_libc(tag, valid):
    m = module()
    if valid:
        m["wheel_filename"]("mcp-2.1.1-" + tag + ".whl", "mcp", "2.1.1", (2, 34))
    else:
        with pytest.raises(RuntimeError):
            m["wheel_filename"]("mcp-2.1.1-" + tag + ".whl", "mcp", "2.1.1", (2, 34))


def test_duplicate_packages_and_omitted_pins_never_become_complete():
    v = report()
    v["install"].append(copy.deepcopy(v["install"][0]))
    with pytest.raises(RuntimeError):
        module()["project_report"](v, inputs(), (2, 34))
    i = inputs()
    i["constraints"] += "other==1.0\n"
    i["seed_sha256"] = hashlib.sha256(i["constraints"].encode()).hexdigest()
    with pytest.raises(RuntimeError):
        module()["project_report"](report(), i, (2, 34))


def test_original_report_roundtrip_and_compressed_truncation_tail_hash_refusals():
    m = module()
    raw = json.dumps(report()).encode()
    packed = m["pack_report"](raw)
    assert m["unpack_report"](packed) == raw
    stream = base64.b64decode(packed["data"])
    for data in (stream[:-1], stream + b"extra", stream + stream):
        value = dict(packed, data=base64.b64encode(data).decode())
        with pytest.raises(RuntimeError):
            m["unpack_report"](value)
    with pytest.raises(RuntimeError):
        m["unpack_report"](dict(packed, sha256="0" * 64))
    with pytest.raises(RuntimeError):
        m["unpack_report"](dict(packed, raw_bytes=True))
    bomb = base64.b64encode(zlib.compress(b"0" * (m["MAX_RAW"] + 1))).decode()
    with pytest.raises(RuntimeError):
        m["unpack_report"](dict(packed, data=bomb, raw_bytes=m["MAX_RAW"]))


def test_child_env_and_argv_do_not_inherit_secrets_or_enable_installs(monkeypatch):
    monkeypatch.setenv("MASKGW_TEST_DSN", "private-canary")
    monkeypatch.setenv("PIP_INDEX_URL", "https://private.example")
    m = module()
    env = m["child_environment"]()
    assert "MASKGW_TEST_DSN" not in env and "PIP_INDEX_URL" not in env
    assert not any("private" in value for value in env.values())
    argv = m["pip_args"](inputs()["requirements"])
    assert "--dry-run" in argv and "--only-binary=:all:" in argv and "--isolated" in argv
    assert "--trusted-host" not in argv and "--no-deps" not in argv


def packet(m: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(report()).encode()
    empty = hashlib.sha256(b"").hexdigest()
    return {
        "kind": "oracle9-pip-resolution-v1",
        "inputs": inputs(),
        "projection": m["project_report"](report(), inputs(), (2, 34)),
        "raw": m["pack_report"](raw),
        "config_absent": list(m["CONFIGS"]),
        "child_environment": m["child_environment"](),
        "cert": {
            "path": m["CERT"],
            "resolved_path": "/etc/pki/trust/public.pem",
            "uid": 0,
            "gid": 0,
            "mode": 0o644,
            "bytes": 123,
            "sha256": "c" * 64,
        },
        "diagnostic": {
            "exit": 0,
            "stdout_bytes": 0,
            "stdout_sha256": empty,
            "stdout_utf8": "",
            "stderr_bytes": 0,
            "stderr_sha256": empty,
            "stderr_utf8": "",
        },
    }


def test_projection_and_original_are_bound_by_exact_bytes():
    m = module()
    v = packet(m)
    assert json.loads(m["validate_packet"](v, inputs())) == report()
    v["projection"]["files"][0]["sha256"] = "0" * 64
    with pytest.raises(RuntimeError):
        m["validate_packet"](v, inputs())


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("kind",), "other"),
        (("config_absent",), []),
        (("child_environment", "PIP_INDEX_URL"), "private"),
        (("cert", "uid"), True),
        (("cert", "mode"), 0o666),
        (("cert", "resolved_path"), "/outside/ca"),
        (("cert", "sha256"), "wrong"),
        (("diagnostic", "stderr_utf8"), "lost-warning"),
        (("diagnostic", "exit"), True),
    ],
)
def test_packet_cannot_forge_environment_ca_or_diagnostic(path, value):
    m = module()
    v = packet(m)
    target = v
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(RuntimeError):
        m["validate_packet"](v, inputs())


def test_failed_pip_log_keeps_full_hash_with_only_a_bounded_lossy_prefix(tmp_path):
    raw = b"failure:" + b"\xff" * 100000
    path = tmp_path / "public-pip-error"
    path.write_bytes(raw)
    value = module()["failure_log"](path, 16384)
    assert value["bytes"] == len(raw) and value["sha256"] == hashlib.sha256(raw).hexdigest()
    assert value["prefix_bytes"] == 16384 and "\ufffd" in value["prefix_utf8"]
    assert len(value["prefix_utf8"]) == 16384
