"""Pure admission predicates and publication guard. No files/process/CLI effects."""

import hashlib
import json
import re

# Generated from literal need calls in pinned e3cf/88e2; equality tested by AST.
CATEGORY_CODES = frozenset(
    {
        "ABSENCE",
        "BLACKHOLE_ORACLE",
        "B_REQUIRED",
        "CAPTURE",
        "CASE",
        "CHANNEL_FILE",
        "CHANNEL_PIN",
        "CID_CHANGED",
        "CID_REQUIRED",
        "CLEANUP_DEADLINE",
        "CLEANUP_LOCK",
        "CLI",
        "CLI_IDENTITY_CHANGED",
        "CLI_KILL_DID_NOT_LEAVE_CID_ALIVE",
        "CLI_SCOPE",
        "CONFIG",
        "CREATE_EXIT",
        "CREATE_MEASUREMENT",
        "CREATE_RUNNING",
        "CREATE_SIZE",
        "DAEMON",
        "DAEMON_PROFILE",
        "ENDPOINT",
        "HOST_CAPTURE",
        "HOST_HELD",
        "IMAGE",
        "IMAGE_EXACT",
        "INSPECT",
        "INSPECT_SHAPE",
        "INTENT",
        "ISOLATION",
        "KILL",
        "OUTPUT_ORACLE",
        "OWNERSHIP",
        "OWNER_HELD",
        "PROFILE",
        "READY_ORACLE",
        "REMOVE",
        "REPORT_CANONICAL",
        "REPORT_CASE",
        "REPORT_FACTS",
        "REPORT_SCHEMA",
        "REPORT_SIZE",
        "RUNNING",
        "SEND_FAILED",
        "SOURCE",
        "SOURCE_PIN",
        "SPAWN_NOT_REGISTERED",
        "SUPERVISION_REQUIRED",
        "SURFACE",
        "TASK",
        "UNEXPECTED_SEND",
        "V2_CAPTURE",
        "VERSION",
        "WATCHDOG_FIRED",
        "WATCHDOG_START",
    }
)
PRESENCE_FIELDS = (
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
)


def closed_category(error):
    if isinstance(error, RuntimeError) and len(error.args) == 1:
        value = error.args[0]
        if type(value) is str and value in CATEGORY_CODES:
            return value
    return "INTERNAL"


def safe_observed(value, expected):
    if type(value) is bool or value is None:
        return value
    if type(value) is int and -(2**63) <= value < 2**63:
        return value
    if value == expected and type(value) is type(expected):
        return expected
    return "DIFFERENT"  # never free text, lists of strings, env or unknown labels


def fields(info, role, labels, environment):
    if type(info) is not dict or role not in ("normal", "retain"):
        raise RuntimeError("INSPECT_SHAPE") from None
    config, host = info.get("Config"), info.get("HostConfig")
    if type(config) is not dict or type(host) is not dict:
        raise RuntimeError("INSPECT_SHAPE") from None
    rows = []

    def add(group, field, value, expected, mode="eq", hidden=False):
        if mode == "bool":
            match = value is expected
        else:
            match = value == expected
        rows.append(
            {
                "group": group,
                "field": field,
                "expected": "EXACT_PUBLIC_ENV" if hidden else expected,
                "observed": ("EQUAL" if match else "DIFFERENT")
                if hidden
                else safe_observed(value, expected),
                "matches": bool(match),
            }
        )

    add("config", "Config.Labels", config.get("Labels"), labels)
    add("config", "Config.User", config.get("User"), "70:70" if role == "retain" else "10001:10001")
    add("config", "Config.WorkingDir", config.get("WorkingDir"), "/var/empty")
    add("config", "Config.Env", config.get("Env"), environment, hidden=True)
    for name, expected in (("Tty", False), ("OpenStdin", True), ("StdinOnce", False)):
        add("config", "Config." + name, config.get(name), expected, "bool")
    for name in ("Volumes", "ExposedPorts"):
        add("config", "Config." + name, bool(config.get(name)), False, "bool")
    add("config", "Config.Healthcheck", config.get("Healthcheck"), {"Test": ["NONE"]})
    add("profile", "HostConfig.ReadonlyRootfs", host.get("ReadonlyRootfs"), True, "bool")
    for name, expected in (
        ("NetworkMode", "none"),
        ("CapDrop", ["ALL"]),
        ("SecurityOpt", ["no-new-privileges"]),
        ("Memory", 134217728),
        ("MemorySwap", 134217728),
        ("PidsLimit", 8),
        ("NanoCpus", 1000000000),
        ("ShmSize", 8388608),
    ):
        add("profile", "HostConfig." + name, host.get(name), expected)
    add("profile", "HostConfig.CapAdd", bool(host.get("CapAdd")), False, "bool")
    limits = host.get("Ulimits")
    shaped = type(limits) is list and all(
        type(item) is dict and {"Name", "Soft", "Hard"} <= set(item) and type(item["Name"]) is str
        for item in limits
    )
    mapping = {item["Name"]: [item["Soft"], item["Hard"]] for item in limits} if shaped else None
    add("isolation", "HostConfig.Ulimits", mapping, {"core": [0, 0], "nofile": [128, 128]})
    add("isolation", "HostConfig.Ulimits.count", len(limits) if shaped else None, 2)
    for name, expected in (
        ("IpcMode", "private"),
        ("CgroupnsMode", "private"),
        ("PidMode", ""),
        ("RestartPolicy", {"Name": "no", "MaximumRetryCount": 0}),
        ("LogConfig", {"Type": "none", "Config": {}}),
    ):
        add("isolation", "HostConfig." + name, host.get(name), expected)
    for name in PRESENCE_FIELDS:
        add("surface", "HostConfig." + name, bool(host.get(name)), False, "bool")
    add("surface", "Mounts", bool(info.get("Mounts")), False, "bool")
    groups = {
        name: all(row["matches"] for row in rows if row["group"] == name)
        for name in ("config", "profile", "isolation", "surface")
    }
    state = info.get("State")
    state_ok = (
        type(state) is dict
        and state.get("Running") is False
        and type(state.get("Pid")) is int
        and state["Pid"] == 0
    )
    return {
        "kind": "MASKGW_ADMISSION_FIELDS_V1",
        "role": role,
        "checks": rows,
        "groups": groups,
        "profile_predicates_match": all(groups.values()),
        "state_created": state_ok,
        "divergent_fields": [row["field"] for row in rows if not row["matches"]],
        "label_observations": {
            "own_value_matches": {
                key: type(config.get("Labels")) is dict and config["Labels"].get(key) == value
                for key, value in labels.items()
            },
            "presentation_present": type(config.get("Labels")) is dict
            and "desktop.docker.io/ports.scheme" in config["Labels"],
            "count": len(config["Labels"]) if type(config.get("Labels")) is dict else None,
        },
        "observations": {
            "Config." + name: safe_observed(config.get(name), None)
            for name in (
                "AttachStdin",
                "AttachStdout",
                "AttachStderr",
                "Tty",
                "OpenStdin",
                "StdinOnce",
            )
        },
    }


def publication(raw, environment, labels, command, entrypoint, *, cid, name):
    """Export gate only. Caller retains raw locally, never receives it in result."""
    if type(raw) is not bytes or not 0 < len(raw) <= 2097152:
        return {"allowed": False, "categories": ["SIZE"], "bytes": 0, "sha256": None}
    result = {
        "allowed": False,
        "categories": [],
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }

    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("DUPLICATE")
            value[key] = item
        return value

    def private_key(value):
        if type(value) is dict:
            return any(
                "proxy" in key.casefold() or "auth" in key.casefold() or private_key(item)
                for key, item in value.items()
            )
        if type(value) is list:
            return any(private_key(item) for item in value)
        return False

    try:
        values = json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_constant=lambda _v: (_ for _ in ()).throw(ValueError("NON_JSON")),
        )
        if type(values) is not list or len(values) != 1:
            raise ValueError("SHAPE")
        info = values[0]
        config, host = info["Config"], info["HostConfig"]
        if type(config) is not dict or type(host) is not dict:
            raise ValueError("SHAPE")
        if config.get("Env") != environment:
            result["categories"].append("ENV")
        if private_key(info):
            result["categories"].append("PRIVATE_KEY")
        if (
            type(cid) is not str
            or re.fullmatch(r"[0-9a-f]{64}", cid) is None
            or type(name) is not str
            or re.fullmatch(r"maskgw-ol9-t4-[0-9a-f]{12}-(normal|retain)", name) is None
            or info.get("Id") != cid
            or info.get("Name") != "/" + name
        ):
            result["categories"].append("IDENTITY")
        observed = config.get("Labels")
        if (
            type(observed) is not dict
            or not all(observed.get(k) == v for k, v in labels.items())
            or any(
                key not in labels and (key != "desktop.docker.io/ports.scheme" or value != "v2")
                for key, value in observed.items()
            )
        ):
            result["categories"].append("LABELS")
        if config.get("Cmd") != list(command) or config.get("Entrypoint") != list(entrypoint):
            result["categories"].append("COMMAND")
    except (ValueError, KeyError, TypeError, RecursionError, UnicodeError):
        result["categories"].append("SHAPE")
    result["allowed"] = not result["categories"]
    return result
