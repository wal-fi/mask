"""Fake container admission/ownership, no Docker process or network."""

import copy
import runpy
from pathlib import Path
from typing import Any

import pytest

M = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "docs/poc/oracle9_dependencies_resolve.py")
)
ORIGIN = {"ENTRY": ["/opt/maskgw/venv/bin/python", "-I", "-B"], "ENV": ["known-public=only"]}


def info() -> dict[str, Any]:
    return {
        "Id": "a" * 64,
        "Name": "/own-name",
        "Image": M["IMAGE"],
        "Mounts": [],
        "Config": {
            "Image": M["IMAGE"],
            "User": "10001:10001",
            "Entrypoint": ORIGIN["ENTRY"],
            "Cmd": ["-c", "public", "data"],
            "Env": ORIGIN["ENV"],
            "Labels": {"maskgw.task": "own-task", "maskgw.source-sha256": "source"},
        },
        "HostConfig": {
            "Memory": 512 * 1024 * 1024,
            "MemorySwap": 512 * 1024 * 1024,
            "PidsLimit": 32,
            "NanoCpus": 1000000000,
            "ShmSize": 1024 * 1024,
            "ReadonlyRootfs": True,
            "Privileged": False,
            "NetworkMode": "bridge",
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
            "Tmpfs": {"/tmp": M["TMPFS"]},  # noqa: S108 -- fake inspect, no filesystem write
            "IpcMode": "private",
            "CgroupnsMode": "private",
            "LogConfig": {"Type": "none"},
            "RestartPolicy": {"Name": "no"},
            "Ulimits": [
                {"Name": "core", "Soft": 0, "Hard": 0},
                {"Name": "nofile", "Soft": 128, "Hard": 128},
            ],
        },
    }


def check(v: dict[str, Any]) -> Any:
    return M["validate_container"](
        v, "own-task", "source", "own-name", ["-c", "public", "data"], ORIGIN
    )


def test_exact_preparation_profile_is_admitted_and_owned_even_if_later_profile_wrong():
    value = info()
    assert check(value) == "a" * 64
    value["HostConfig"]["Privileged"] = True
    with pytest.raises(RuntimeError):
        check(value)
    # Ownership still allows removal of our stopped misconfigured container.
    assert M["validate_owned_identity"](value, "own-task", "source", "own-name") == "a" * 64


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("Name",), "/other"),
        (("Image",), "sha256:" + "0" * 64),
        (("Config", "Labels", "maskgw.task"), "other"),
        (("Config", "User"), "0:0"),
        (("Config", "Cmd"), ["other"]),
        (("Config", "Env"), ["DSN=private"]),
        (("Config", "Volumes"), {"/private": {}}),
        (("HostConfig", "ReadonlyRootfs"), False),
        (("HostConfig", "NetworkMode"), "host"),
        (("HostConfig", "MemorySwap"), -1),
        (("HostConfig", "PidsLimit"), -1),
        (("HostConfig", "Tmpfs"), {"/tmp": "unbounded"}),  # noqa: S108 -- negative fixture only
        (("HostConfig", "CapDrop"), []),
        (("HostConfig", "Binds"), ["/var/run/docker.sock:/socket"]),
        (("HostConfig", "SecurityOpt"), []),
        (("HostConfig", "RestartPolicy", "Name"), "always"),
    ],
)
def test_profile_refuses_wrong_owner_privilege_mounts_or_budget(path, value):
    v = copy.deepcopy(info())
    target = v
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(RuntimeError):
        check(v)
