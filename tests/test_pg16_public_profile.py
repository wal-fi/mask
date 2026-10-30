"""PG16 admission contracts against synthetic inspect/report fixtures only."""

import dataclasses
import hashlib
import json
import runpy
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
TASK = "a" * 32
CID = "c" * 64


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/pg16_public_profile.py"))


def image_info(module: Any) -> Any:
    return {
        "Id": module["IMAGE"],
        "Os": "linux",
        "Architecture": "amd64",
        "Config": {
            "Env": [
                "PATH=" + module["PATH"],
                "LANG=en_US.utf8",
                "PG_MAJOR=16",
                "PG_VERSION=16.15",
                "PGDATA=" + module["DATA"],
                "PG_SHA256=" + "a" * 64,
                "GOSU_VERSION=1.17",
            ],
            "Labels": None,
            "Volumes": {module["DATA"]: {}},
            "ExposedPorts": {"5432/tcp": {}},
        },
    }


def encoded(info: Any) -> bytes:
    return json.dumps([info]).encode("ascii")


@pytest.fixture
def bound(module: Any) -> Any:
    image = module["admit_image"](encoded(image_info(module)))
    intent = module["Intent"](TASK, image)
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
            "WorkingDir": "/tmp",  # noqa: S108 - declared private UID70 tmpfs in inspect fixture
            "Env": list(image.environment),
            "Tty": False,
            "OpenStdin": False,
            "StdinOnce": False,
            "Volumes": {module["DATA"]: {}},
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
        "State": {"Running": False, "Pid": 0},
    }
    return intent, info


def report(module: Any, intent: Any) -> bytes:
    values = {
        "kind": "MASKGW_PG16_PUBLIC_V1",
        "task": intent.task,
        "uid": "70",
        "gid": "70",
        "os_id": "alpine",
        "os_version": "3.22.2",
        "busybox": "BusyBox v1.37.0 (public build) multi-call binary.",
    }
    values.update({tool: tool + " (PostgreSQL) 16.15" for tool in module["PG_TOOLS"]})
    values.update({"tool_" + tool: "1" for tool in module["TOOLS"]})
    values.update(pgdata_mode="70:70:700", pgdata_fs="tmpfs", tmp_mode="70:70:700", tmp_fs="tmpfs")
    return "".join(key + "=" + value + "\n" for key, value in values.items()).encode("ascii")


def test_declared_image_port_is_not_a_published_port(module, bound):
    intent, info = bound
    assert info["Config"]["ExposedPorts"] == {"5432/tcp": {}}
    assert (
        not info["HostConfig"].get("PortBindings") and info["HostConfig"]["NetworkMode"] == "none"
    )
    assert module["validate_container"](info, intent, CID) == CID


def test_fixed_builder_has_no_server_stdin_bind_or_published_port(module, bound):
    intent, _ = bound
    args, measured = module["create_args"](intent)
    assert args[:2] == ("create", "--pull=never") and measured["margin_chars"] > 0
    assert args[-3:] == (module["IMAGE"], *intent.command)
    for forbidden in (
        "--interactive",
        "-i",
        "--publish",
        "-p",
        "--volume",
        "-v",
        "--env",
        "--privileged",
    ):
        assert forbidden not in args
    assert args[args.index("--entrypoint") + 1] == "/bin/sh"
    assert sum(arg == "--tmpfs" for arg in args) == 2
    assert all(tool + " --version" in module["SOURCE"] for tool in module["PG_TOOLS"])
    assert "pg_ctl start" not in module["SOURCE"] and "POSTGRES_PASSWORD" not in str(args)


def test_report_is_structured_without_free_version_text(module, bound):
    intent, _ = bound
    facts = module["parse_report"](report(module, intent), 0, intent)
    assert facts["busybox_version"] == "1.37.0" and facts["uid"] == 70
    assert set(facts["postgres_versions"].values()) == {"16.15"}
    assert "public build" not in json.dumps(facts) and facts["tmpfs_owner_mode_verified"] is True


@pytest.mark.parametrize(
    "change", ["id", "arch", "volumes", "env-secret", "env-duplicate", "env-unsafe-name", "label"]
)
def test_unknown_image_input_fails_before_any_intent(module, change):
    info = image_info(module)
    if change == "id":
        info["Id"] = "sha256:" + "0" * 64
    elif change == "arch":
        info["Architecture"] = "arm64"
    elif change == "volumes":
        info["Config"]["Volumes"]["/unexpected"] = {}
    elif change == "env-secret":
        info["Config"]["Env"].append("PGPASSWORD=fake-private")
    elif change == "env-duplicate":
        info["Config"]["Env"].append("PG_MAJOR=16")
    elif change == "env-unsafe-name":
        info["Config"]["Env"].append("BAD-NAME=fake-private")
    else:
        info["Config"]["Labels"] = {"auth-token": "fake-private"}
    with pytest.raises(module["ProbeError"]) as caught:
        module["admit_image"](encoded(info))
    assert "fake-private" not in str(caught.value) and caught.value.__context__ is None


@pytest.mark.parametrize("raw", [b"[]", b"{}", b"[NaN]", b"[{},{}]", b'[{"Id":1,"Id":2}]', b"\xff"])
def test_json_ambiguity_is_sanitized_without_context(module, raw):
    with pytest.raises(module["ProbeError"], match="JSON") as caught:
        module["admit_image"](raw)
    assert caught.value.__context__ is None


def test_intent_captures_command_labels_and_env_without_mutating_image(module, bound, monkeypatch):
    intent, info = bound
    before = (intent.command, intent.labels, intent.image.environment)
    monkeypatch.setitem(module["Intent"].__init__.__globals__, "SOURCE", "changed")
    assert module["identity"](info, intent, CID) == CID
    assert (intent.command, intent.labels, intent.image.environment) == before
    assert hashlib.sha256(intent.command[1].encode("ascii")).hexdigest() == intent.source_sha256
    with pytest.raises(dataclasses.FrozenInstanceError):
        intent.task = "b" * 32


@pytest.mark.parametrize(
    "change",
    [
        ("Config", "Env", ["PGPASSWORD=fake-private"], "CONFIG"),
        ("Config", "OpenStdin", True, "CONFIG"),
        ("Config", "StdinOnce", True, "CONFIG"),
        ("Config", "Tty", True, "CONFIG"),
        ("Config", "User", "0:0", "CONFIG"),
        ("Config", "ExposedPorts", {"9999/tcp": {}}, "CONFIG"),
        ("HostConfig", "NetworkMode", "bridge", "PROFILE"),
        ("HostConfig", "CapAdd", ["SYS_ADMIN"], "PROFILE"),
        ("HostConfig", "MemorySwap", 0, "PROFILE"),
        ("HostConfig", "Tmpfs", {}, "PROFILE"),
        ("HostConfig", "Ulimits", [], "PROFILE"),
        ("HostConfig", "PortBindings", {"5432/tcp": [{"HostPort": "15432"}]}, "SURFACE"),
        ("HostConfig", "VolumesFrom", ["unrelated"], "SURFACE"),
        ("HostConfig", "Binds", ["unrelated:/unexpected"], "SURFACE"),
    ],
)
def test_profile_failure_does_not_lose_cleanup_identity(module, bound, change):
    section, field, value, category = change
    intent, info = bound
    info[section][field] = value
    assert module["identity"](info, intent, CID) == CID
    with pytest.raises(module["ProbeError"], match=category):
        module["validate_container"](info, intent, CID)


@pytest.mark.parametrize(
    "mount",
    [
        {"Type": "volume", "Name": "a" * 64, "Destination": "/var/lib/postgresql/data"},
        {"Type": "bind", "Source": "/unexpected", "Destination": "/tmp"},  # noqa: S108 - negative fixture only
        {"Type": "tmpfs", "Destination": "/unexpected", "RW": True},
    ],
)
def test_volume_bind_or_unknown_tmpfs_is_never_profile_accepted(module, bound, mount):
    intent, info = bound
    info["Mounts"] = [mount]
    assert module["identity"](info, intent, CID) == CID
    with pytest.raises(module["ProbeError"], match="MOUNTS"):
        module["validate_container"](info, intent, CID)


@pytest.mark.parametrize("change", ["cid", "name", "command", "entry", "labels"])
def test_identity_never_accepts_a_different_cid_or_intent(module, bound, change):
    intent, info = bound
    if change == "cid":
        info["Id"] = "d" * 64
    elif change == "name":
        info["Name"] = "/unrelated"
    elif change == "command":
        info["Config"]["Cmd"] = ["-ec", "different"]
    elif change == "entry":
        info["Config"]["Entrypoint"] = ["docker-entrypoint.sh"]
    else:
        info["Config"]["Labels"]["maskgw.task"] = "b" * 32
    with pytest.raises(module["ProbeError"], match="OWNERSHIP"):
        module["identity"](info, intent, CID)


@pytest.mark.parametrize(
    "kind",
    [
        "extra",
        "duplicate",
        "truncated",
        "nonascii",
        "large",
        "version",
        "mode",
        "tools",
        "task",
        "uid",
    ],
)
def test_report_never_accepts_partial_ambiguous_or_unsafe_facts(module, bound, kind):
    intent, _ = bound
    raw = report(module, intent)
    if kind == "extra":
        raw += b"unexpected=fake-private\n"
    elif kind == "duplicate":
        raw += b"uid=70\n"
    elif kind == "truncated":
        raw = raw[:-1]
    elif kind == "nonascii":
        raw += b"\xff"
    elif kind == "large":
        raw = b"x" * 8193
    elif kind == "version":
        raw = raw.replace(b"16.15", b"15.9")
    elif kind == "mode":
        raw = raw.replace(b"70:70:700", b"0:0:777")
    elif kind == "tools":
        raw = raw.replace(b"tool_dd=1", b"tool_dd=0")
    elif kind == "task":
        raw = raw.replace(TASK.encode(), b"b" * 32)
    else:
        raw = raw.replace(b"uid=70", b"uid=0")
    with pytest.raises(module["ProbeError"]) as caught:
        module["parse_report"](raw, 0, intent)
    assert "fake-private" not in str(caught.value)


@pytest.mark.parametrize("fault", ["TOOLS", "UID", "OS", "MOUNTS", "VERSION"])
def test_closed_probe_faults_preserve_category_without_raw(module, bound, fault):
    intent, _ = bound
    with pytest.raises(module["ProbeError"], match=fault):
        module["parse_report"](("fault=" + fault + "\n").encode(), 42, intent)


def test_publication_uses_the_admitted_pg_image_env_and_labels(module, bound):
    intent, info = bound
    raw = encoded(info)
    result = module["publication"](raw, intent, CID)
    assert result["allowed"] is True
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["bytes"] == len(raw) and "Config" not in result


@pytest.mark.parametrize(
    "where", ["env", "label", "cmd", "id", "name", "nested-auth", "nested-proxy"]
)
def test_export_filter_refuses_private_or_misbound_raw_without_copying_values(module, bound, where):
    intent, info = bound
    canary = "fake-private-canary"
    if where == "env":
        info["Config"]["Env"].append("PGPASSWORD=" + canary)
    elif where == "label":
        info["Config"]["Labels"]["unexpected"] = canary
    elif where == "cmd":
        info["Config"]["Cmd"] = [canary]
    elif where == "id":
        info["Id"] = "d" * 64
    elif where == "name":
        info["Name"] = "/unrelated"
    elif where == "nested-auth":
        info["State"]["extra"] = [{"AuTh": canary}]
    else:
        info["NetworkSettings"] = {"extra": [{"pRoXy": canary}]}
    result = module["publication"](encoded(info), intent, CID)
    assert result["allowed"] is False and result["categories"]
    assert canary not in json.dumps(result)


def test_deep_publication_input_is_closed_instead_of_recursing_out(module, bound):
    intent, info = bound
    base = encoded(info)
    raw = base[:-2] + b',"nested":' + b"[" * 600 + b"0" + b"]" * 600 + b"}]"
    result = module["publication"](raw, intent, CID)
    assert result["allowed"] is False and result["categories"] == ["SHAPE"]


def test_ulimits_order_is_not_an_admission_premise(module, bound):
    intent, info = bound
    info["HostConfig"]["Ulimits"].reverse()
    assert module["validate_container"](info, intent, CID) == CID


@pytest.mark.parametrize("fault", ["duplicate", "extra-key", "bool", "unknown-name"])
def test_ulimits_require_exact_names_types_keys_and_count(module, bound, fault):
    intent, info = bound
    limits = info["HostConfig"]["Ulimits"]
    if fault == "duplicate":
        limits[1] = deepcopy(limits[0])
    elif fault == "extra-key":
        limits[0]["Unexpected"] = 0
    elif fault == "bool":
        limits[0]["Soft"] = False
    else:
        limits[0]["Name"] = "unknown"
    with pytest.raises(module["ProbeError"], match="PROFILE"):
        module["validate_container"](info, intent, CID)


def test_build_metadata_keys_are_admitted_without_guessing_a_complete_env_list(module):
    info = image_info(module)
    info["Config"]["Env"].append("DOCKER_PG_LLVM_DEPS=llvm19-dev clang19")
    image = module["admit_image"](encoded(info))
    assert image.environment[-1] == "DOCKER_PG_LLVM_DEPS=llvm19-dev clang19"


@pytest.mark.parametrize(
    "key", ["PROXY_URL", "AUTH_DATA", "PGPASSWORD", "SECRET", "TOKEN", "API_KEY"]
)
def test_sensitive_env_key_parts_are_never_admitted_from_the_image(module, key):
    info = image_info(module)
    info["Config"]["Env"].append(key + "=fake-private")
    with pytest.raises(module["ProbeError"], match="IMAGE_ENV"):
        module["admit_image"](encoded(info))


def test_optional_build_env_tabs_are_preserved_exactly_in_profile_and_publication(module, bound):
    base = image_info(module)
    base["Config"]["Env"].append("DOCKER_PG_LLVM_DEPS=a \t\tb")
    image = module["admit_image"](encoded(base))
    intent = module["Intent"](TASK, image)
    _, info = bound
    info["Config"]["Env"] = list(image.environment)
    assert module["validate_container"](info, intent, CID) == CID
    assert module["publication"](encoded(info), intent, CID)["allowed"] is True
    info["Config"]["Env"][-1] = "DOCKER_PG_LLVM_DEPS=a b"
    assert module["publication"](encoded(info), intent, CID)["allowed"] is False
    with pytest.raises(module["ProbeError"], match="CONFIG"):
        module["validate_container"](info, intent, CID)


@pytest.mark.parametrize(
    "row", ["EXTRA=a\nb", "EXTRA=a\rb", "EXTRA=a\x00b", "PG_VERSION=16.15\t", "BAD\tNAME=value"]
)
def test_env_control_characters_and_required_field_tabs_remain_forbidden(module, row):
    info = image_info(module)
    info["Config"]["Env"].append(row)
    with pytest.raises(module["ProbeError"], match="IMAGE_ENV"):
        module["admit_image"](encoded(info))


def test_blueprint_is_exact_before_image_admission_and_does_not_resend_image_labels(module):
    args, measured = module["blueprint"](TASK)
    info = image_info(module)
    info["Config"]["Labels"] = {"org.opencontainers.image.title": "Public fixture"}
    intent = module["Intent"](TASK, module["admit_image"](encoded(info)))
    assert module["create_args"](intent) == (args, measured)
    assert sum(item == "--label" for item in args) == 3
    assert ("org.opencontainers.image.title", "Public fixture") in intent.labels
    assert "org.opencontainers.image.title=Public fixture" not in args


@pytest.mark.parametrize("task", [None, False, "", "x" * 32, "a" * 31])
def test_blueprint_refuses_unknown_task_without_image_or_cli(module, task):
    with pytest.raises(module["ProbeError"], match="TASK"):
        module["blueprint"](task)
