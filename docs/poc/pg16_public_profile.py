"""PG16 public admission builders/parsers. No native effects or operational caller."""

from dataclasses import dataclass
import hashlib
import json
import re
import subprocess

IMAGE = "sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685"
CLI = "C:/Users/w.filho/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"
DATA = "/var/lib/postgresql/data"
ENTRY = ("/bin/sh",)
PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
TMPFS = {
    DATA: "rw,noexec,nosuid,nodev,size=134217728,uid=70,gid=70,mode=0700",
    "/tmp": "rw,noexec,nosuid,nodev,size=16777216,uid=70,gid=70,mode=0700",
}
OWN_KEYS = ("maskgw.task", "maskgw.source-sha256", "maskgw.manifest-sha256")
LABEL_KEYS = frozenset(
    "org.opencontainers.image." + key
    for key in (
        "title",
        "version",
        "ref.name",
        "source",
        "url",
        "licenses",
        "revision",
        "created",
        "documentation",
        "vendor",
        "base.digest",
        "base.name",
        "description",
    )
)
TOOLS = (
    "sh",
    "base64",
    "sha256sum",
    "dd",
    "wc",
    "timeout",
    "stat",
    "busybox",
    "postgres",
    "initdb",
    "pg_ctl",
    "psql",
)
PG_TOOLS = ("postgres", "initdb", "pg_ctl", "psql")
SOURCE = r"""set -efu
export LC_ALL=C
fail() { printf 'fault=%s\n' "$1"; exit 42; }
for tool in sh base64 sha256sum dd wc timeout stat busybox postgres initdb pg_ctl psql; do
    command -v "$tool" >/dev/null 2>&1 || fail TOOLS
done
uid=$(id -u) || fail UID
gid=$(id -g) || fail UID
[ "$uid:$gid" = '70:70' ] || fail UID
os_id=$(. /etc/os-release; printf '%s' "$ID") || fail OS
os_version=$(. /etc/os-release; printf '%s' "$VERSION_ID") || fail OS
pgdata_mode=$(stat -c '%u:%g:%a' /var/lib/postgresql/data) || fail MOUNTS
pgdata_fs=$(stat -f -c '%T' /var/lib/postgresql/data) || fail MOUNTS
tmp_mode=$(stat -c '%u:%g:%a' /tmp) || fail MOUNTS
tmp_fs=$(stat -f -c '%T' /tmp) || fail MOUNTS
busybox_version=$(busybox 2>/dev/null | { IFS= read -r line; printf '%s' "$line"; }) || fail VERSION
postgres_version=$(postgres --version) || fail VERSION
initdb_version=$(initdb --version) || fail VERSION
pg_ctl_version=$(pg_ctl --version) || fail VERSION
psql_version=$(psql --version) || fail VERSION
printf 'kind=MASKGW_PG16_PUBLIC_V1\ntask=%s\nuid=%s\ngid=%s\nos_id=%s\nos_version=%s\n' "$TASK" "$uid" "$gid" "$os_id" "$os_version"
printf 'busybox=%s\npostgres=%s\ninitdb=%s\npg_ctl=%s\npsql=%s\n' "$busybox_version" "$postgres_version" "$initdb_version" "$pg_ctl_version" "$psql_version"
for tool in sh base64 sha256sum dd wc timeout stat busybox postgres initdb pg_ctl psql; do
    printf 'tool_%s=1\n' "$tool"
done
printf 'pgdata_mode=%s\npgdata_fs=%s\ntmp_mode=%s\ntmp_fs=%s\n' "$pgdata_mode" "$pgdata_fs" "$tmp_mode" "$tmp_fs"
"""
MANIFEST = {
    "kind": "MASKGW_PG16_PUBLIC_PROFILE_V1",
    "image": IMAGE,
    "source_sha256": hashlib.sha256(SOURCE.encode("ascii")).hexdigest(),
    "entry": list(ENTRY),
    "tmpfs": TMPFS,
    "profile": "uid70-ro512m-none-pids256-v1",
}
MANIFEST_SHA = hashlib.sha256(
    (json.dumps(MANIFEST, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
).hexdigest()


class ProbeError(Exception):
    def __init__(self, category):
        super().__init__(
            category
            if category
            in (
                "JSON",
                "IMAGE",
                "IMAGE_ENV",
                "IMAGE_LABELS",
                "TASK",
                "INTENT",
                "OWNERSHIP",
                "CID",
                "CONFIG",
                "PROFILE",
                "SURFACE",
                "MOUNTS",
                "REPORT",
                "VERSION",
                "TOOLS",
                "UID",
                "OS",
                "EXIT",
                "COMMAND",
            )
            else "REPORT"
        )


def need(ok, category):
    if not ok:
        raise ProbeError(category) from None


def one(raw):
    need(type(raw) is bytes and 0 < len(raw) <= 2097152, "JSON")

    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError()
            value[key] = item
        return value

    decoded = None
    try:
        decoded = json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_constant=lambda _v: (_ for _ in ()).throw(ValueError()),
        )
    except (ValueError, UnicodeError, RecursionError):
        pass
    need(type(decoded) is list and len(decoded) == 1 and type(decoded[0]) is dict, "JSON")
    return decoded[0]


def public_text(value, maximum=1024):
    return (
        type(value) is str
        and 0 < len(value) <= maximum
        and all(32 <= ord(char) <= 126 for char in value)
    )


@dataclass(frozen=True)
class Image:
    """Immutable facts from the exact public fixture image, not a release attestation."""

    environment: tuple
    labels: tuple
    volumes: tuple
    version: str
    raw_sha256: str


def admit_image(raw):
    info = one(raw)
    need(
        info.get("Id") == IMAGE
        and info.get("Os") == "linux"
        and info.get("Architecture") == "amd64",
        "IMAGE",
    )
    config = info.get("Config")
    need(
        type(config) is dict
        and config.get("Volumes") == {DATA: {}}
        and config.get("ExposedPorts") == {"5432/tcp": {}},
        "IMAGE",
    )
    rows = config.get("Env")
    need(type(rows) is list and 1 <= len(rows) <= 16, "IMAGE_ENV")
    patterns = {
        "PATH": re.escape(PATH),
        "PG_MAJOR": "16",
        "PG_VERSION": r"16\.(?:0|[1-9][0-9]{0,2})",
        "PGDATA": re.escape(DATA),
    }
    env = {}
    for row in rows:
        need(type(row) is str and 0 < len(row) <= 1024 and "=" in row, "IMAGE_ENV")
        key, value = row.split("=", 1)
        need(
            re.fullmatch(r"[A-Z_][A-Z0-9_]{0,127}", key) is not None
            and not any(
                part in key.upper() for part in ("PROXY", "AUTH", "PASS", "SECRET", "TOKEN", "KEY")
            )
            and key not in env
            and all(
                32 <= ord(char) <= 126 or (key not in patterns and char == "\t") for char in value
            )
            and (key not in patterns or re.fullmatch(patterns[key], value) is not None),
            "IMAGE_ENV",
        )
        env[key] = value
    need({"PATH", "PG_MAJOR", "PG_VERSION", "PGDATA"} <= env.keys(), "IMAGE_ENV")
    labels = config.get("Labels")
    need(labels is None or type(labels) is dict, "IMAGE_LABELS")
    labels = {} if labels is None else labels
    need(
        all(key in LABEL_KEYS and public_text(value) for key, value in labels.items()),
        "IMAGE_LABELS",
    )
    return Image(
        tuple(rows),
        tuple(sorted(labels.items())),
        (DATA,),
        env["PG_VERSION"],
        hashlib.sha256(raw).hexdigest(),
    )


def _capture(task):
    need(type(task) is str and re.fullmatch(r"[0-9a-f]{32}", task), "TASK")
    script = "TASK='" + task + "'\n" + SOURCE
    source_sha = hashlib.sha256(script.encode("ascii")).hexdigest()
    labels = tuple(sorted(zip(OWN_KEYS, (task, source_sha, MANIFEST_SHA), strict=True)))
    return "maskgw-ol9-pg16-admit-" + task[:12], ("-ec", script), labels, source_sha


@dataclass(frozen=True, init=False)
class Intent:
    task: str
    image: Image
    command: tuple
    labels: tuple
    source_sha256: str
    name: str

    def __init__(self, task, image):
        name, command, own_labels, source_sha = _capture(task)
        need(type(image) is Image, "INTENT")
        labels = dict(image.labels)
        labels.update(own_labels)
        for key, value in {
            "task": task,
            "image": image,
            "command": command,
            "labels": tuple(sorted(labels.items())),
            "source_sha256": source_sha,
            "name": name,
        }.items():
            object.__setattr__(self, key, value)


def create_args(intent):
    need(type(intent) is Intent, "INTENT")
    own_labels = tuple((key, value) for key, value in intent.labels if key in OWN_KEYS)
    return _create(intent.name, intent.command, own_labels)


def blueprint(task):
    """Exact public command/measurement before A, without reading/admitting an image.

    This grants no create/start authority; the coordinator still must admit
    the exact image and require create_args(actual_intent) equals this plan.
    """
    name, command, labels, _sha = _capture(task)
    return _create(name, command, labels)


def _create(name, command, labels):
    args = [
        "create",
        "--pull=never",
        "--name",
        name,
        "--user",
        "70:70",
        "--workdir",
        "/tmp",
        "--read-only",
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--ipc",
        "private",
        "--cgroupns",
        "private",
        "--memory",
        "512m",
        "--memory-swap",
        "512m",
        "--cpus",
        "1",
        "--pids-limit",
        "256",
        "--shm-size",
        "8m",
        "--ulimit",
        "core=0:0",
        "--ulimit",
        "nofile=128:128",
        "--restart",
        "no",
        "--log-driver",
        "none",
        "--no-healthcheck",
        "--entrypoint",
        "/bin/sh",
    ]
    for key, value in labels:
        args.extend(("--label", key + "=" + value))
    for path, value in TMPFS.items():
        args.extend(("--tmpfs", path + ":" + value))
    args.extend((IMAGE, *command))
    size = len(subprocess.list2cmdline((CLI, "--context", "desktop-linux", *args)))
    need(size <= 26000, "COMMAND")
    return tuple(args), {"createprocess_chars": size, "margin_chars": 26000 - size}


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
        and c.get("OpenStdin") is False
        and c.get("StdinOnce") is False
        and c.get("Volumes") == {DATA: {}}
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
            and mount.get("Destination") in TMPFS
            and mount["Destination"] not in seen
            and not mount.get("Name")
            and not mount.get("Source")
            and mount.get("RW") is True,
            "MOUNTS",
        )
        seen.add(mount["Destination"])
    return cid


def parse_report(raw, code, intent):
    need(type(intent) is Intent and type(code) is int and type(raw) is bytes, "REPORT")
    if code == 42 and raw in tuple(
        ("fault=" + value + "\n").encode("ascii")
        for value in ("TOOLS", "UID", "OS", "MOUNTS", "VERSION")
    ):
        raise ProbeError(raw.decode("ascii")[6:-1]) from None
    need(code == 0, "EXIT")
    need(0 < len(raw) <= 8192, "REPORT")
    text = None
    try:
        text = raw.decode("ascii")
    except UnicodeError:
        pass
    need(text is not None and text.endswith("\n"), "REPORT")
    keys = (
        "kind",
        "task",
        "uid",
        "gid",
        "os_id",
        "os_version",
        "busybox",
        *PG_TOOLS,
        *("tool_" + tool for tool in TOOLS),
        "pgdata_mode",
        "pgdata_fs",
        "tmp_mode",
        "tmp_fs",
    )
    lines = text.split("\n")[:-1]
    need(len(lines) == len(keys) and len(lines) <= 32, "REPORT")
    values = {}
    for key, line in zip(keys, lines, strict=True):
        need(line.startswith(key + "=") and public_text(line), "REPORT")
        values[key] = line[len(key) + 1 :]
    need(values["kind"] == "MASKGW_PG16_PUBLIC_V1" and values["task"] == intent.task, "REPORT")
    need(values["uid"] == values["gid"] == "70", "UID")
    need(
        values["os_id"] == "alpine"
        and re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", values["os_version"]),
        "OS",
    )
    busybox = re.fullmatch(
        r"BusyBox v([0-9]+\.[0-9]+\.[0-9]+)(?: \([^\r\n]*\))? multi-call binary\.",
        values["busybox"],
    )
    need(busybox is not None, "VERSION")
    versions = {}
    for tool in PG_TOOLS:
        matched = re.fullmatch(
            re.escape(tool) + r" \(PostgreSQL\) (16\.(?:0|[1-9][0-9]{0,2}))", values[tool]
        )
        need(matched is not None and matched.group(1) == intent.image.version, "VERSION")
        versions[tool] = matched.group(1)
    need(all(values["tool_" + tool] == "1" for tool in TOOLS), "TOOLS")
    need(
        values["pgdata_mode"] == values["tmp_mode"] == "70:70:700"
        and values["pgdata_fs"] == values["tmp_fs"] == "tmpfs",
        "MOUNTS",
    )
    return {
        "kind": "MASKGW_PG16_PUBLIC_FACTS_V1",
        "task": intent.task,
        "uid": 70,
        "gid": 70,
        "os": {"id": "alpine", "version": values["os_version"]},
        "busybox_version": busybox.group(1),
        "postgres_versions": versions,
        "tools_present": list(TOOLS),
        "tmpfs_owner_mode_verified": True,
    }


def publication(raw, intent, cid):
    """CID raw export gate only. Never publishes raw image metadata or private seeds."""
    if type(raw) is not bytes or not 0 < len(raw) <= 2097152:
        return {"allowed": False, "categories": ["SIZE"], "bytes": 0, "sha256": None}
    result = {
        "allowed": False,
        "categories": [],
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    if (
        type(intent) is not Intent
        or type(cid) is not str
        or re.fullmatch(r"[0-9a-f]{64}", cid) is None
    ):
        result["categories"].append("IDENTITY")
        return result
    try:
        info = one(raw)
    except ProbeError:
        info = None
    if info is None:
        result["categories"].append("JSON")
        return result

    def private_key(value):
        pending, visited = [(value, 0)], 0
        while pending:
            item, depth = pending.pop()
            visited += 1
            if depth > 64 or visited > 65536:
                raise ValueError() from None
            if type(item) is dict:
                if any("auth" in key.casefold() or "proxy" in key.casefold() for key in item):
                    return True
                if len(item) + len(pending) > 65536:
                    raise ValueError() from None
                pending.extend((child, depth + 1) for child in item.values())
            elif type(item) is list:
                if len(item) + len(pending) > 65536:
                    raise ValueError() from None
                pending.extend((child, depth + 1) for child in item)
        return False

    forbidden, invalid = False, False
    try:
        forbidden = private_key(info)
    except ValueError:
        invalid = True
    if invalid:
        result["categories"].append("SHAPE")
        return result
    if forbidden:
        result["categories"].append("PRIVATE_KEY")
    config = info.get("Config")
    if type(config) is not dict:
        result["categories"].append("SHAPE")
        return result
    if config.get("Env") != list(intent.image.environment):
        result["categories"].append("ENV")
    if config.get("Labels") != dict(intent.labels):
        result["categories"].append("LABELS")
    if config.get("Cmd") != list(intent.command) or config.get("Entrypoint") != list(ENTRY):
        result["categories"].append("COMMAND")
    if info.get("Id") != cid or info.get("Name") != "/" + intent.name:
        result["categories"].append("IDENTITY")
    if info.get("Image") != IMAGE or config.get("Image") != IMAGE:
        result["categories"].append("IMAGE")
    result["allowed"] = not result["categories"]
    return result
