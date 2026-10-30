"""Pure metadata comparisons/publication guards. No native effects."""

import ast
import hashlib
import json
import runpy
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from tests.test_w1_bootstrap_probe import inventory

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_admission_fields.py"))


@pytest.fixture
def example() -> Any:
    policy = runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_probe.py"))
    info, intent = inventory(policy, policy["Case"].NORMAL)
    return policy, info, intent


def report(module: Any, example: Any) -> Any:
    policy, info, intent = example
    return module["fields"](
        info, intent.case.value, policy["labels_for"](intent.task), policy["ENV"]
    )


def gate(module: Any, example: Any) -> Any:
    policy, info, intent = example
    return module["publication"](
        json.dumps([info]).encode(),
        policy["ENV"],
        policy["labels_for"](intent.task),
        intent.command,
        policy["ENTRY"],
        cid="c" * 64,
        name=policy["name_for"](intent.task, intent.case),
    )


def test_category_set_is_exactly_the_two_consumed_sources(module):
    codes = set()
    for name, pin in (
        (
            "w1_bootstrap_probe.py",
            "e3cf9f4d5b6150c4c3d975fd17d6296348fa14b9e22a43543c9913d34361afd4",
        ),
        (
            "w1_bootstrap_t4_host.py",
            "88e220ebb342bba6889dc0934a3872b3bac3e29e3583c24f60d5503ad1d18c70",
        ),
    ):
        raw = (REPO / "docs/poc" / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == pin
        for node in ast.walk(ast.parse(raw)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "need"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                codes.add(node.args[1].value)
    assert module["CATEGORY_CODES"] == codes
    for code in codes:
        assert module["closed_category"](RuntimeError(code)) == code


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("fake-private-value"),
        RuntimeError("CONFIG", "fake-private-value"),
        ValueError("CONFIG"),
    ],
)
def test_unknown_or_wrong_typed_category_never_serializes_error(module, error):
    assert module["closed_category"](error) == "INTERNAL"


@pytest.mark.parametrize("role", ["normal", "retain"])
def test_both_positive_profiles_agree_with_original_validator(module, role):
    policy = runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_probe.py"))
    info, intent = inventory(policy, policy["Case"](role))
    assert policy["validate_container"](info, intent) == info["Id"]
    result = report(module, (policy, info, intent))
    assert result["profile_predicates_match"] is True
    assert result["divergent_fields"] == [] and result["state_created"] is True
    assert gate(module, (policy, info, intent))["allowed"] is True


@pytest.mark.parametrize(
    "change",
    [
        ("Config", "Labels", {}, "CONFIG"),
        ("Config", "User", "0:0", "CONFIG"),
        ("Config", "WorkingDir", "/", "CONFIG"),
        ("Config", "Env", ["FAKE_PRIVATE=value"], "CONFIG"),
        ("Config", "Tty", True, "CONFIG"),
        ("Config", "OpenStdin", False, "CONFIG"),
        ("Config", "StdinOnce", True, "CONFIG"),
        ("Config", "Volumes", {"/public-canary-only": {}}, "CONFIG"),
        ("Config", "ExposedPorts", {"123/tcp": {}}, "CONFIG"),
        ("Config", "Healthcheck", {"Test": ["CMD", "fake-private-value"]}, "CONFIG"),
        ("HostConfig", "ReadonlyRootfs", False, "PROFILE"),
        ("HostConfig", "NetworkMode", "bridge", "PROFILE"),
        ("HostConfig", "CapDrop", [], "PROFILE"),
        ("HostConfig", "CapAdd", ["SYS_ADMIN"], "PROFILE"),
        ("HostConfig", "SecurityOpt", [], "PROFILE"),
        ("HostConfig", "Memory", 1, "PROFILE"),
        ("HostConfig", "MemorySwap", 1, "PROFILE"),
        ("HostConfig", "PidsLimit", 2, "PROFILE"),
        ("HostConfig", "NanoCpus", 1, "PROFILE"),
        ("HostConfig", "ShmSize", 1, "PROFILE"),
        ("HostConfig", "Ulimits", [], "ISOLATION"),
        ("HostConfig", "IpcMode", "host", "ISOLATION"),
        ("HostConfig", "CgroupnsMode", "host", "ISOLATION"),
        ("HostConfig", "PidMode", "host", "ISOLATION"),
        ("HostConfig", "RestartPolicy", {"Name": "always"}, "ISOLATION"),
        ("HostConfig", "LogConfig", {"Type": "json-file", "Config": {}}, "ISOLATION"),
    ],
)
def test_each_profile_field_is_measured_without_first_failure_shortcut(module, example, change):
    section, field, value, group = change
    policy, info, intent = example
    info[section][field] = deepcopy(value)
    result = report(module, example)
    assert result["profile_predicates_match"] is False
    assert section + "." + field in result["divergent_fields"]
    with pytest.raises(RuntimeError) as caught:
        policy["validate_container"](info, intent)
    # Changing the own labels also trips identity before group CONFIG.
    assert module["closed_category"](caught.value) == ("OWNERSHIP" if field == "Labels" else group)
    assert "fake-private-value" not in json.dumps(result)
    assert "FAKE_PRIVATE=value" not in json.dumps(result)


@pytest.mark.parametrize(
    "name",
    [
        "Privileged",
        "Init",
        "AutoRemove",
        "Tmpfs",
        "Binds",
        "Mounts",
        "Devices",
        "DeviceRequests",
        "DeviceCgroupRules",
        "GroupAdd",
        "Sysctls",
        "Links",
        "ExtraHosts",
        "PortBindings",
        "PublishAllPorts",
        "VolumesFrom",
        "Dns",
        "DnsOptions",
        "DnsSearch",
    ],
)
def test_every_surface_predicate_is_in_diff_and_original(module, example, name):
    policy, info, intent = example
    info["HostConfig"][name] = True
    result = report(module, example)
    assert "HostConfig." + name in result["divergent_fields"]
    with pytest.raises(RuntimeError, match="SURFACE"):
        policy["validate_container"](info, intent)


def test_all_simultaneous_differences_and_unmeasured_attach_flags(module, example):
    _, info, _ = example
    info["Config"].update(StdinOnce=True, AttachStdin=True, AttachStdout=False, Tty=True)
    info["HostConfig"]["Memory"] = 42
    info["HostConfig"]["Tmpfs"] = {"/public-canary-only": "size=1m"}
    result = report(module, example)
    assert set(result["divergent_fields"]) == {
        "Config.StdinOnce",
        "Config.Tty",
        "HostConfig.Memory",
        "HostConfig.Tmpfs",
    }
    assert result["observations"]["Config.AttachStdin"] is True
    assert result["observations"]["Config.AttachStdout"] is False


def test_duplicate_ulimit_and_top_mounts_do_not_hide_behind_mapping(module, example):
    _, info, _ = example
    info["HostConfig"]["Ulimits"].append(deepcopy(info["HostConfig"]["Ulimits"][0]))
    info["Mounts"] = [{"Source": "fake-private-value"}]
    result = report(module, example)
    assert "HostConfig.Ulimits.count" in result["divergent_fields"]
    assert "Mounts" in result["divergent_fields"]
    assert "fake-private-value" not in json.dumps(result)


@pytest.mark.parametrize("where", ["env", "nested-auth", "nested-proxy", "label", "cmd"])
def test_unexpected_credentials_never_pass_export_gate_or_diff(module, example, where):
    _, info, _ = example
    private_canary = "fake-private-DO-NOT-PUBLISH"
    if where == "env":
        info["Config"]["Env"].append(
            "HTTPS_PROXY=http://user:" + private_canary + "@example.invalid"
        )
    elif where == "nested-auth":
        info["HostConfig"]["Annotations"] = {"a": [{"AuTh": private_canary}]}
    elif where == "nested-proxy":
        info["Config"]["nested"] = {"No_pRoXy": private_canary}
    elif where == "label":
        info["Config"]["Labels"]["unexpected"] = private_canary
    else:
        info["Config"]["Cmd"] = [private_canary]
    result = gate(module, example)
    assert result["allowed"] is False and result["categories"]
    assert private_canary not in json.dumps(result) and private_canary not in json.dumps(
        report(module, example)
    )


def test_expected_presentation_label_is_public_but_still_not_profile_accepted(module, example):
    _, info, _ = example
    info["Config"]["Labels"]["desktop.docker.io/ports.scheme"] = "v2"
    assert gate(module, example)["allowed"] is True
    assert report(module, example)["profile_predicates_match"] is False


@pytest.mark.parametrize(
    "raw", [b"not-json", b"[]", b'{"Config":{}}', b'[{"Config":{},"Config":{}}]', b"[NaN]"]
)
def test_malformed_or_ambiguous_raw_is_not_publishable(module, example, raw):
    policy, _, intent = example
    assert (
        module["publication"](
            raw,
            policy["ENV"],
            policy["labels_for"](intent.task),
            intent.command,
            policy["ENTRY"],
            cid="c" * 64,
            name=policy["name_for"](intent.task, intent.case),
        )["allowed"]
        is False
    )


@pytest.mark.parametrize("pid", [False, 1])
def test_state_requires_exact_zero_int_and_false_running(module, example, pid):
    _, info, _ = example
    info["State"].update(Running=False, Pid=pid)
    assert report(module, example)["state_created"] is False


@pytest.mark.parametrize("field,value", [("Id", "d" * 64), ("Name", "/different-own-name")])
def test_export_gate_rejects_misbound_identity(module, example, field, value):
    _, info, _ = example
    info[field] = value
    assert gate(module, example)["allowed"] is False


@pytest.mark.parametrize("field", ["AuTh", "NetworkSettings"])
def test_private_keys_outside_config_are_not_publishable(module, example, field):
    _, info, _ = example
    info[field] = {"nested": [{"pRoXyAuth": "fake-private-canary"}]}
    assert gate(module, example)["allowed"] is False


def test_label_observations_have_only_known_names_and_counts(module, example):
    _, info, _ = example
    del info["Config"]["Labels"]["maskgw.task"]
    info["Config"]["Labels"]["fake-private-name"] = "fake-private-value"
    info["Config"]["Labels"]["desktop.docker.io/ports.scheme"] = "v2"
    observation = report(module, example)["label_observations"]
    assert observation["own_value_matches"]["maskgw.task"] is False
    assert observation["presentation_present"] is True and observation["count"] == 4
    assert "fake-private" not in json.dumps(observation)
