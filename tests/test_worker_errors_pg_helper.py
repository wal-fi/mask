"""Pure ownership and loopback guards of the disposable PG gate; no CLI or SQL."""

from __future__ import annotations

import copy
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "docs/poc/worker_errors_pg.py"
SPEC = importlib.util.spec_from_file_location("worker_errors_pg_fixture", SOURCE)
assert SPEC is not None and SPEC.loader is not None
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)
TASK = "c" * 32
NAME = "maskgw-worker-errors-" + TASK[:12]
IMAGE = "sha256:" + "d" * 64


def metadata() -> dict[str, Any]:
    return {
        "Id": "e" * 64,
        "Name": "/" + NAME,
        "Image": IMAGE,
        "Labels": {"maskgw-test-owner": TASK},
        "Running": False,
        "Bindings": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": ""}]},
        "Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "55499"}]},
    }


def test_exact_owned_identity_and_private_loopback_port():
    info = metadata()
    assert HELPER.owned(info, TASK, NAME, IMAGE)
    assert HELPER.port(info) == 55499


@pytest.mark.parametrize(
    "field,value",
    [
        ("Id", "prefix-" + "e" * 64),
        ("Name", "/someone-else"),
        ("Image", "other"),
        ("Labels", {}),
        ("Labels", {"maskgw-test-owner": "someone-else"}),
        ("Running", 0),
    ],
)
def test_foreign_or_ambiguous_metadata_never_authorizes_cleanup(field, value):
    info = metadata()
    info[field] = value
    assert HELPER.owned(info, TASK, NAME, IMAGE) is False


@pytest.mark.parametrize("ip", ["0.0.0.0", "::", "192.0.2.1", None])  # noqa: S104 - rejection fixtures only
def test_public_or_wrong_binding_is_rejected(ip):
    info = copy.deepcopy(metadata())
    info["Bindings"]["5432/tcp"][0]["HostIp"] = ip
    with pytest.raises(ValueError, match="PG_BINDING"):
        HELPER.port(info)


@pytest.mark.parametrize("value", ["0", "65536", "-1", "\uff155499", 55499, ""])
def test_port_must_be_canonical_ascii_decimal_in_range(value):
    info = metadata()
    info["Ports"]["5432/tcp"][0]["HostPort"] = value
    with pytest.raises(ValueError, match="PG_BINDING"):
        HELPER.port(info)


def test_import_does_not_start_action_and_environment_forwards_no_secrets(monkeypatch):
    for key in (
        "MASKGW_TEST_DSN",
        "MASKGW_DATASOURCE_MASTER_KEY",
        "POSTGRES_PASSWORD",
        "PYTHONPATH",
        "AWS_SECRET_ACCESS_KEY",
        "DOCKER_HOST",
    ):
        monkeypatch.setenv(key, "CANARY")
    forwarded = HELPER.env()
    assert not any(value == "CANARY" for value in forwarded.values())
    assert not (SOURCE.parent / "result.json").exists()


@pytest.mark.parametrize("optimize", [1, 2])
def test_main_refuses_optimization_before_parsing_or_io(monkeypatch, optimize):
    monkeypatch.setattr(HELPER, "sys", SimpleNamespace(flags=SimpleNamespace(optimize=optimize)))
    with pytest.raises(SystemExit) as caught:
        HELPER.main()
    assert caught.value.code == 64


def suite() -> ET.Element:
    result = ET.Element("testsuite")
    for module, name in HELPER.EXPECTED_CASES:
        ET.SubElement(result, "testcase", classname=module, name=name)
    return result


def test_requires_five_new_and_twelve_existing_real_cases():
    result = HELPER.required_cases(suite())
    assert len(result) == 17 and len(set(result)) == 17
    assert sum("test_db_execution_error_integration::" in name for name in result) == 5


@pytest.mark.parametrize("failure", ["missing", "skipped", "failure", "error", "duplicate"])
def test_unrun_or_failed_required_case_refuses_even_with_unrelated_skip_message(failure):
    result = suite()
    case = result.find("testcase")
    assert case is not None
    if failure == "missing":
        result.remove(case)
    elif failure == "duplicate":
        result.append(copy.deepcopy(case))
    else:
        ET.SubElement(case, failure, message="unrelated reason with no DSN text")
    with pytest.raises(ValueError, match="REQUIRED_PG_CASE_NOT_PASSED"):
        HELPER.required_cases(result)
