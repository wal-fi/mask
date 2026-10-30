"""Reader profile predicates and command builders, against synthetic inspect only."""

import dataclasses
import hashlib
import os
import runpy
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from tests.test_pg16_public_profile import encoded, image_info

REPO = Path(__file__).resolve().parents[1]
TASK, CID = "a" * 32, "c" * 64


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/pg16_shell_profile.py"))


@pytest.fixture
def bound(module: Any) -> Any:
    image = module["admit_image"](encoded(image_info(module["P"])))
    intent = module["Intent"](TASK, image, module["R"]["Case"].BINARY)
    info = {
        "Id": CID,
        "Name": "/" + intent.name,
        "Image": module["IMAGE"],
        "Config": {
            "Image": module["IMAGE"],
            "Cmd": list(intent.command),
            "Entrypoint": list(module["ENTRY"]),
            "Labels": dict(intent.labels),
            "User": "70:70",
            "WorkingDir": "/tmp",  # noqa: S108 - declared synthetic tmpfs
            "Env": list(image.environment),
            "Tty": False,
            "OpenStdin": True,
            "StdinOnce": True,
            "Volumes": {module["P"]["DATA"]: {}},
            "ExposedPorts": {"5432/tcp": {}},
            "Healthcheck": {"Test": ["NONE"]},
        },
        "HostConfig": {
            "ReadonlyRootfs": True,
            "NetworkMode": "none",
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
            "Memory": 536870912,
            "MemorySwap": 536870912,
            "PidsLimit": 256,
            "NanoCpus": 1000000000,
            "ShmSize": 8388608,
            "Tmpfs": deepcopy(module["TMPFS"]),
            "Ulimits": [
                {"Name": "core", "Soft": 0, "Hard": 0},
                {"Name": "nofile", "Soft": 128, "Hard": 128},
            ],
            "IpcMode": "private",
            "CgroupnsMode": "private",
            "PidMode": "",
            "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
            "LogConfig": {"Type": "none", "Config": {}},
        },
        "Mounts": [],
    }
    return image, intent, info


def test_all_cases_bound_wrapper_manifest_and_measured_argv(module, bound):
    image, _, _ = bound
    names, sizes = set(), []
    assert module["MANIFEST_SHA"] != module["P"]["MANIFEST_SHA"]
    for case in module["R"]["Case"]:
        intent = module["Intent"](TASK, image, case)
        args, measurement = module["create_args"](intent)
        assert (args, measurement) == module["blueprint"](TASK, case)
        assert args[:3] == ("create", "--pull=never", "-i")
        assert args[-3:] == (module["IMAGE"], *intent.command)
        assert args.count("-i") == 1 and "--publish" not in args and "--env" not in args
        actual = len(subprocess.list2cmdline((module["CLI"], "--context", "desktop-linux", *args)))
        assert actual == measurement["createprocess_chars"] <= 26000
        assert measurement["margin_chars"] == 26000 - actual
        assert hashlib.sha256(intent.command[1].encode("ascii")).hexdigest() == intent.source_sha256
        assert intent.core_sha256 == module["R"]["CORE_SHA"] != intent.source_sha256
        assert dict(intent.labels)["maskgw.manifest-sha256"] == module["MANIFEST_SHA"]
        assert intent.name.startswith("maskgw-ol9-pg16-reader-") and len(intent.name) <= 63
        assert intent.name not in names
        names.add(intent.name)
        sizes.append(actual)
    assert len(names) == 23 and max(sizes) < 26000


def test_new_and_old_profile_do_not_accept_each_others_intent_or_name(module, bound):
    image, intent, info = bound
    assert module["validate_container"](info, intent, CID) == CID
    base_intent = module["P"]["Intent"](TASK, image)
    assert base_intent.name != intent.name
    with pytest.raises(module["ProbeError"], match="CID"):
        module["P"]["identity"](info, intent, CID)
    with pytest.raises(module["ProbeError"], match="CID"):
        module["identity"](info, base_intent, CID)
    with pytest.raises(dataclasses.FrozenInstanceError):
        intent.command = ("-ec", "arbitrary")


def test_oci_labels_are_inherited_but_never_reemitted_on_cli(module):
    value = image_info(module["P"])
    value["Config"]["Labels"] = {"org.opencontainers.image.title": "public-fixture"}
    image = module["admit_image"](encoded(value))
    intent = module["Intent"](TASK, image, module["R"]["Case"].ONE)
    assert dict(intent.labels)["org.opencontainers.image.title"] == "public-fixture"
    args, _ = module["create_args"](intent)
    assert not any("org.opencontainers.image" in item for item in args)


@pytest.mark.parametrize(
    "key,value,category",
    [
        ("OpenStdin", False, "CONFIG"),
        ("StdinOnce", False, "CONFIG"),
        ("Tty", True, "CONFIG"),
        ("User", "0:0", "CONFIG"),
        ("WorkingDir", "/", "CONFIG"),
        ("Env", ["PGPASSWORD=public-marker"], "CONFIG"),
        ("Volumes", {}, "CONFIG"),
        ("ExposedPorts", {}, "CONFIG"),
        ("Healthcheck", {"Test": ["CMD", "false"]}, "CONFIG"),
    ],
)
def test_config_failure_keeps_cleanup_identity(module, bound, key, value, category):
    _, intent, info = bound
    info["Config"][key] = value
    assert module["identity"](info, intent, CID) == CID
    with pytest.raises(module["ProbeError"], match=category) as caught:
        module["validate_container"](info, intent, CID)
    assert "public-marker" not in str(caught.value) and caught.value.__context__ is None


@pytest.mark.parametrize(
    "key,value,category",
    [
        ("ReadonlyRootfs", False, "PROFILE"),
        ("NetworkMode", "bridge", "PROFILE"),
        ("CapDrop", [], "PROFILE"),
        ("CapAdd", ["SYS_ADMIN"], "PROFILE"),
        ("SecurityOpt", [], "PROFILE"),
        ("Memory", True, "PROFILE"),
        ("MemorySwap", 0, "PROFILE"),
        ("PidsLimit", 128, "PROFILE"),
        ("NanoCpus", 2000000000, "PROFILE"),
        ("ShmSize", 67108864, "PROFILE"),
        ("Tmpfs", {}, "PROFILE"),
        ("Ulimits", [], "PROFILE"),
        ("IpcMode", "host", "PROFILE"),
        ("CgroupnsMode", "host", "PROFILE"),
        ("PidMode", "host", "PROFILE"),
        ("RestartPolicy", {"Name": "always"}, "PROFILE"),
        ("LogConfig", {"Type": "json-file"}, "PROFILE"),
        ("PortBindings", {"5432/tcp": [{"HostPort": "15432"}]}, "SURFACE"),
        ("Binds", ["unrelated:/x"], "SURFACE"),
        ("Init", True, "SURFACE"),
        ("AutoRemove", True, "SURFACE"),
        ("Devices", [{}], "SURFACE"),
        ("Dns", ["1.1.1.1"], "SURFACE"),
    ],
)
def test_host_predicate_failure_keeps_cleanup_identity(module, bound, key, value, category):
    _, intent, info = bound
    info["HostConfig"][key] = value
    assert module["identity"](info, intent, CID) == CID
    with pytest.raises(module["ProbeError"], match=category):
        module["validate_container"](info, intent, CID)


@pytest.mark.parametrize("field", ["Id", "Name", "Image", "Cmd", "Entrypoint", "Labels"])
def test_alien_identity_is_rejected_even_with_safe_profile(module, bound, field):
    _, intent, info = bound
    if field in ("Id", "Name", "Image"):
        info[field] = "alien-public-value"
    else:
        info["Config"][field] = {} if field == "Labels" else ["alien-public-value"]
    with pytest.raises(module["ProbeError"], match="OWNERSHIP"):
        module["identity"](info, intent, CID)


@pytest.mark.parametrize("value", [True, False, None, 1, "true"])
def test_attach_fields_observe_closed_types_without_becoming_predicates(module, bound, value):
    _, intent, info = bound
    info["Config"].update(dict.fromkeys(("AttachStdin", "AttachStdout", "AttachStderr"), value))
    assert module["validate_container"](info, intent, CID) == CID
    observed = module["attach_observation"](info)
    assert all(item is (value if type(value) is bool else None) for item in observed.values())


@pytest.mark.parametrize(
    "mount",
    [
        {"Type": "volume", "Name": "f" * 64, "Destination": "/var/lib/postgresql/data"},
        {"Type": "bind", "Source": "/unexpected", "Destination": "/tmp"},  # noqa: S108
        {"Type": "tmpfs", "Destination": "/unknown", "RW": True},
        {"Type": "tmpfs", "Destination": [], "RW": True},
        {"Type": "tmpfs", "Destination": {}, "RW": True},
    ],
)
def test_unsupported_or_malformed_mount_has_closed_error(module, bound, mount):
    _, intent, info = bound
    info["Mounts"] = [mount]
    assert module["identity"](info, intent, CID) == CID
    with pytest.raises(module["ProbeError"], match="MOUNTS") as caught:
        module["validate_container"](info, intent, CID)
    assert caught.value.__cause__ is None and caught.value.__context__ is None


@pytest.mark.parametrize("task,case", [("A" * 32, "ONE"), (TASK, "one"), (True, "ONE")])
def test_untrusted_task_or_enum_is_never_an_arbitrary_command(module, task, case):
    selected = getattr(module["R"]["Case"], case, case)
    with pytest.raises((module["ProbeError"], module["R"]["ReaderError"])):
        module["blueprint"](task, selected)


def test_original_source_pins_and_no_native_effects(module, monkeypatch):
    for rel, digest in module["DEPENDENCIES"].values():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("profile attempted native effect")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    loaded = runpy.run_path(str(REPO / "docs/poc/pg16_shell_profile.py"))
    assert loaded["blueprint"](TASK, loaded["R"]["Case"].BINARY)
