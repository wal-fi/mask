"""Closed PG16 reader profile/builders. Definitions only, no native effects."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess

REPO = Path(__file__).resolve().parents[2]
DEPENDENCIES = {
    "profile": (
        "docs/poc/pg16_public_profile.py",
        "fe2f8ba8bfabc5572fe7aeb85c31c54de38ceaa23c1a6c34dd631425371d9277",
    ),
    "owner": (
        "docs/poc/pg16_shell_owner.py",
        "d671880078d6d1f30067400ae3d3169e17458c471467027835ba2be6897b6c8f",
    ),
}


def capture(key):
    relative, digest = DEPENDENCIES[key]
    path = REPO / relative
    raw = None
    try:
        info = path.lstat()
        if (
            stat.S_ISREG(info.st_mode)
            and not getattr(info, "st_file_attributes", 0) & 0x400
            and info.st_size <= 65536
        ):
            candidate = path.read_bytes()
            if len(candidate) == info.st_size and hashlib.sha256(candidate).hexdigest() == digest:
                raw = candidate
    except OSError:
        pass
    if raw is None:
        raise RuntimeError("PG16_READER_PROFILE_SOURCE") from None
    namespace = {"__name__": "_pg16_reader_" + key, "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace, raw


P, PROFILE_RAW = capture("profile")
O, OWNER_RAW = capture("owner")
R, C = O["R"], O["C"]
IMAGE, ENTRY, TMPFS, CLI = P["IMAGE"], P["ENTRY"], P["TMPFS"], P["CLI"]
OWN_KEYS = P["OWN_KEYS"]
Image, admit_image, ProbeError, need = P["Image"], P["admit_image"], P["ProbeError"], P["need"]
MANIFEST = {
    "kind": "MASKGW_PG16_READER_PROFILE_V1",
    "image": IMAGE,
    "entry": list(ENTRY),
    "tmpfs": dict(TMPFS),
    "profile": "uid70-ro512m-none-pids256-shell-v1",
    "stdin": {"Tty": False, "OpenStdin": True, "StdinOnce": True},
    "reader_sha256": O["DEPENDENCIES"]["reader"][1],
    "core_sha256": R["CORE_SHA"],
    "owner_sha256": DEPENDENCIES["owner"][1],
}
MANIFEST_SHA = hashlib.sha256(
    (json.dumps(MANIFEST, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
).hexdigest()


def _capture(task, case):
    need(type(case) is R["Case"], "INTENT")
    wrapper = R["build"](task, case)
    wrapper_sha = hashlib.sha256(wrapper.encode("ascii")).hexdigest()
    labels = tuple(sorted(zip(OWN_KEYS, (task, wrapper_sha, MANIFEST_SHA), strict=True)))
    name = "maskgw-ol9-pg16-reader-" + task[:12] + "-" + case.value
    need(len(name) <= 63, "COMMAND")
    return name, ("-ec", wrapper), labels, wrapper_sha


@dataclass(frozen=True, init=False)
class Intent:
    task: str
    image: Image
    case: object
    command: tuple
    labels: tuple
    source_sha256: str
    core_sha256: str
    name: str

    def __init__(self, task, image, case):
        need(type(image) is Image, "INTENT")
        name, command, own_labels, source_sha = _capture(task, case)
        labels = dict(image.labels)
        labels.update(own_labels)
        for key, value in {
            "task": task,
            "image": image,
            "case": case,
            "command": command,
            "labels": tuple(sorted(labels.items())),
            "source_sha256": source_sha,
            "core_sha256": R["CORE_SHA"],
            "name": name,
        }.items():
            object.__setattr__(self, key, value)


def _create(name, command, labels):
    original, _old_measurement = P["_create"](name, command, labels)
    args = original[:2] + ("-i",) + original[2:]
    size = len(subprocess.list2cmdline((CLI, "--context", "desktop-linux", *args)))
    need(size <= 26000, "COMMAND")
    return args, {"createprocess_chars": size, "margin_chars": 26000 - size}


def create_args(intent):
    need(type(intent) is Intent, "INTENT")
    own_labels = tuple((key, value) for key, value in intent.labels if key in OWN_KEYS)
    return _create(intent.name, intent.command, own_labels)


def blueprint(task, case):
    name, command, labels, _sha = _capture(task, case)
    return _create(name, command, labels)


def identity(info, intent, cid):
    need(
        type(intent) is Intent
        and type(info) is dict
        and type(cid) is str
        and re.fullmatch(r"[0-9a-f]{64}", cid),
        "CID",
    )
    config = info.get("Config")
    need(type(config) is dict and type(config.get("Labels")) is dict, "OWNERSHIP")
    captured = dict(intent.labels)
    need(
        info.get("Id") == cid
        and info.get("Name") == "/" + intent.name
        and info.get("Image") == IMAGE
        and config.get("Image") == IMAGE
        and config.get("Cmd") == list(intent.command)
        and config.get("Entrypoint") == list(ENTRY)
        and all(config["Labels"].get(key) == captured[key] for key in OWN_KEYS),
        "OWNERSHIP",
    )
    return cid


def attach_observation(info):
    """Closed facts only, never an acceptance predicate or raw publication."""
    config = info.get("Config") if type(info) is dict else None
    config = config if type(config) is dict else {}
    return {
        key: config[key] if type(config.get(key)) is bool else None
        for key in ("AttachStdin", "AttachStdout", "AttachStderr")
    }


def validate_container(info, intent, cid):
    identity(info, intent, cid)
    c, h = info["Config"], info.get("HostConfig")
    need(type(h) is dict, "PROFILE")
    need(
        c.get("Labels") == dict(intent.labels)
        and c.get("User") == "70:70"
        and c.get("WorkingDir") == "/tmp"
        and c.get("Env") == list(intent.image.environment)
        and c.get("Tty") is False
        and c.get("OpenStdin") is True
        and c.get("StdinOnce") is True
        and c.get("Volumes") == {P["DATA"]: {}}
        and c.get("ExposedPorts") == {"5432/tcp": {}}
        and c.get("Healthcheck") == {"Test": ["NONE"]},
        "CONFIG",
    )
    need(
        h.get("ReadonlyRootfs") is True
        and h.get("NetworkMode") == "none"
        and h.get("CapDrop") == ["ALL"]
        and not h.get("CapAdd")
        and h.get("SecurityOpt") == ["no-new-privileges"]
        and type(h.get("Memory")) is int
        and h["Memory"] == 536870912
        and type(h.get("MemorySwap")) is int
        and h["MemorySwap"] == 536870912
        and h.get("PidsLimit") == 256
        and h.get("NanoCpus") == 1000000000
        and h.get("ShmSize") == 8388608
        and h.get("Tmpfs") == TMPFS,
        "PROFILE",
    )
    limits = h.get("Ulimits")
    need(
        type(limits) is list
        and len(limits) == 2
        and all(
            type(item) is dict
            and set(item) == {"Name", "Soft", "Hard"}
            and type(item["Name"]) is str
            and type(item["Soft"]) is int
            and type(item["Hard"]) is int
            for item in limits
        ),
        "PROFILE",
    )
    need(
        {item["Name"]: (item["Soft"], item["Hard"]) for item in limits}
        == {"core": (0, 0), "nofile": (128, 128)}
        and h.get("IpcMode") == h.get("CgroupnsMode") == "private"
        and h.get("PidMode") == ""
        and h.get("RestartPolicy") == {"Name": "no", "MaximumRetryCount": 0}
        and h.get("LogConfig") == {"Type": "none", "Config": {}},
        "PROFILE",
    )
    need(
        not any(
            h.get(key)
            for key in (
                "Privileged",
                "Init",
                "AutoRemove",
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
        ),
        "SURFACE",
    )
    mounts = info.get("Mounts")
    need(type(mounts) is list and len(mounts) <= 2, "MOUNTS")
    seen = set()
    for mount in mounts:
        need(
            type(mount) is dict
            and mount.get("Type") == "tmpfs"
            and type(mount.get("Destination")) is str
            and mount.get("Destination") in TMPFS
            and mount["Destination"] not in seen
            and not mount.get("Name")
            and not mount.get("Source")
            and mount.get("RW") is True,
            "MOUNTS",
        )
        seen.add(mount["Destination"])
    return cid
