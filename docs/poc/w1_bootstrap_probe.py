"""Pure public T4 canary/builders. No Docker, subprocess or native action on import."""

import base64
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import zlib

REPO = Path(__file__).resolve().parents[2]
CHANNEL = REPO / "docs/poc/w1_bootstrap_channel.py"
CHANNEL_SHA = "e6ca9e606567289fa312049b071aa777e1764579813829747cb32df05d4ee87a"
IMAGE = "sha256:621cc7f702ec34d7014809411fda7fc89ab6b95f6dc7d16315274d4a7006ef0b"
ENTRY = ["/opt/maskgw/venv/bin/python", "-I", "-B"]
ENV = [
    "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "HOME=/var/empty",
    "LANG=C.UTF-8",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTHONUNBUFFERED=1",
]
SOURCE = r'''"""Public T4 Linux canary. Credentials and product imports forbidden."""
import json
import os
import select
import sys
import time


def need(ok):
    if not ok:
        raise RuntimeError("T4_REFUSED")


def body():
    pattern = b"W1_PUBLIC_CANARY_SEEDEND\n"
    return (pattern * ((16384 // len(pattern)) + 1))[:16384]


def emit(value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
    need(len(raw) <= 512)
    offset = 0
    while offset < len(raw):
        count = os.write(1, raw[offset:])
        need(count > 0)
        offset += count


def reader_negatives(role):
    good = CHANNEL_NS["Seed"](role, b"p").reveal_frame()
    bad = (
        good[:9] + b"000000" + good[15:],
        good[:-8] + b"WRONGEND",
        good + b"extra",
        good[:16],
    )
    categories = []
    for raw in bad:
        read_fd, write_fd = os.pipe()
        try:
            need(os.write(write_fd, raw) == len(raw))
            os.close(write_fd)
            write_fd = None
            try:
                CHANNEL_NS["read_seed_fd"](read_fd, role, time.monotonic() + 1.0)
            except CHANNEL_NS["BootstrapError"] as error:
                categories.append(error.category.value)
            else:
                raise RuntimeError("T4_FALSE_ACCEPT")
        finally:
            os.close(read_fd)
            if write_fd is not None:
                os.close(write_fd)
    need(categories == ["FRAME"] * 4)
    return categories


def observe_eof():
    started = time.monotonic()
    eof = False
    while not eof:
        left = 1.5 - (time.monotonic() - started)
        if left <= 0:
            break
        visible, _, _ = select.select([0], [], [], min(left, 0.05))
        if visible:
            extra = os.read(0, 1)
            need(not extra)
            eof = True
    return eof, int((time.monotonic() - started) * 1000)


def main():
    uid = 70 if CASE == "retain" else 10001
    need(sys.platform == "linux" and sys.version_info[:3] == (3, 11, 13))
    need(sys.flags.isolated == 1 and sys.flags.dont_write_bytecode == 1)
    need(sys.flags.optimize == 0 and os.getuid() == os.getgid() == uid and os.getpid() == 1)
    need(os.getcwd() == "/var/empty")
    with open("/proc/self/status", encoding="ascii") as stream:
        status = dict(line.split(":", 1) for line in stream if ":" in line)
    for key in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"):
        need(status[key].strip() == "0000000000000000")
    need(status["NoNewPrivs"].strip() == "1" and status["Seccomp"].strip() == "2")
    role = CHANNEL_NS["Role"].PG if CASE == "retain" else CHANNEL_NS["Role"].CONTROLLER
    target = CHANNEL_NS["Target"]("0" * 64, TASK, IMAGE_ID, SOURCE_SHA, role)
    ready = target.ready_line()
    if CASE == "bad-ready":
        ready = ready.replace(SOURCE_SHA.encode("ascii"), b"0" * 64)
    need(os.write(1, ready) == len(ready))
    if CASE in ("bad-ready", "blackhole", "cancel-start"):
        while True:
            time.sleep(1.0)
    private = CHANNEL_NS["read_seed_fd"](0, role, time.monotonic() + 12.0)
    received = private.reveal()
    need(received == body())
    if CASE == "retain":
        while True:
            time.sleep(1.0)
    if CASE == "flood":
        block = b"T4_PUBLIC_OUTPUT" * 256
        while True:
            need(os.write(1, block) > 0)
    need(CASE in ("normal", "reader-negative"))
    eof, observation_ms = observe_eof()
    result = {
        "kind": "MASKGW_T4_CANARY_V1", "case": CASE,
        "bytes": len(received), "equality": True, "eof_observed": eof,
        "observation_ms": observation_ms,
        "uid": os.getuid(), "pid": os.getpid(),
    }
    if CASE == "reader-negative":
        result["categories"] = reader_negatives(role)
    emit(result)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        os.write(1, b'{"kind":"MASKGW_T4_FAILED"}\n')
        raise SystemExit(1) from None
'''
SOURCE_SHA = hashlib.sha256(SOURCE.encode("ascii")).hexdigest()


class Case(StrEnum):
    NORMAL = "normal"
    RETAIN = "retain"
    BAD_READY = "bad-ready"
    BLACKHOLE = "blackhole"
    FLOOD = "flood"
    CANCEL_START = "cancel-start"
    READER_NEGATIVE = "reader-negative"


MANIFEST_BYTES = (
    json.dumps(
        {
            "kind": "MASKGW_T4_PUBLIC_INPUTS_V1",
            "image": IMAGE,
            "channel_sha256": CHANNEL_SHA,
            "source_sha256": SOURCE_SHA,
            "cases": [case.value for case in Case],
            "profile": "uid10001-or70-ro128m-pids8-networknone-v1",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    + "\n"
).encode("ascii")
MANIFEST_SHA = hashlib.sha256(MANIFEST_BYTES).hexdigest()


@dataclass(frozen=True, init=False)
class Intent:
    """Capture public argv exactly once BEFORE create, also used during cleanup."""

    task: str
    case: Case
    command: tuple[str, ...]

    def __init__(self, task, case):
        native = tuple(command(task, case))
        object.__setattr__(self, "task", task)
        object.__setattr__(self, "case", case)
        object.__setattr__(self, "command", native)


def need(ok, category):
    if not ok:
        raise RuntimeError(category) from None


def channel_bytes():
    info = CHANNEL.lstat()
    need(
        stat.S_ISREG(info.st_mode)
        and not getattr(info, "st_file_attributes", 0) & 0x400
        and info.st_size <= 65536,
        "CHANNEL_FILE",
    )
    raw = CHANNEL.read_bytes()
    need(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == CHANNEL_SHA, "CHANNEL_PIN")
    return raw


def public_body():
    pattern = b"W1_PUBLIC_CANARY_SEEDEND\n"
    return (pattern * ((16384 // len(pattern)) + 1))[:16384]


def command(task, case):
    need(type(task) is str and re.fullmatch(r"[0-9a-f]{32}", task), "TASK")
    need(type(case) is Case, "CASE")
    blobs = []
    for raw, digest in ((channel_bytes(), CHANNEL_SHA), (SOURCE.encode("ascii"), SOURCE_SHA)):
        blobs.append((base64.b64encode(zlib.compress(raw, 9)).decode("ascii"), digest))
    loader = (
        "import base64,hashlib,zlib\n"
        "def unpack(blob,digest):\n"
        " d=zlib.decompressobj();r=d.decompress(base64.b64decode(blob,validate=True),65537)\n"
        " if len(r)>65536 or not d.eof or d.unused_data or d.unconsumed_tail: raise SystemExit(3)\n"
        " if hashlib.sha256(r).hexdigest()!=digest: raise SystemExit(3)\n"
        " return r\n"
        + "r=unpack("
        + repr(blobs[0][0])
        + ","
        + repr(blobs[0][1])
        + ")\n"
        + "n={'__name__':'_t4_channel','__file__':'<pinned-channel>'}\n"
        + "exec(compile(r,'<pinned-channel>','exec'),n)\n"
        + "r=unpack("
        + repr(blobs[1][0])
        + ","
        + repr(blobs[1][1])
        + ")\n"
        + "n={'__name__':'__main__','__file__':'<public-t4>',"
        + "'CHANNEL_NS':n,'TASK':"
        + repr(task)
        + ",'CASE':"
        + repr(case.value)
        + ",'IMAGE_ID':"
        + repr(IMAGE)
        + ",'SOURCE_SHA':"
        + repr(SOURCE_SHA)
        + "}\n"
        + "exec(compile(r,'<public-t4>','exec'),n)\n"
    )
    return ["-c", loader]


def name_for(task, case):
    need(type(task) is str and re.fullmatch(r"[0-9a-f]{32}", task), "TASK")
    need(type(case) is Case, "CASE")
    return "maskgw-ol9-t4-" + task[:12] + "-" + case.value


def labels_for(task):
    need(type(task) is str and re.fullmatch(r"[0-9a-f]{32}", task), "TASK")
    return {
        "maskgw.task": task,
        "maskgw.source-sha256": SOURCE_SHA,
        "maskgw.manifest-sha256": MANIFEST_SHA,
    }


def create_args(cli, intent):
    need(type(intent) is Intent, "INTENT")
    task, case, native = intent.task, intent.case, list(intent.command)
    uid = "70" if case is Case.RETAIN else "10001"
    labels = [
        value for key, data in labels_for(task).items() for value in ("--label", key + "=" + data)
    ]
    args = [
        "create",
        "--pull=never",
        "--name",
        name_for(task, case),
        *labels,
        "--interactive",
        "--user",
        uid + ":" + uid,
        "--read-only",
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory",
        "134217728",
        "--memory-swap",
        "134217728",
        "--pids-limit",
        "8",
        "--cpus",
        "1",
        "--shm-size",
        "8388608",
        "--ulimit",
        "core=0:0",
        "--ulimit",
        "nofile=128:128",
        "--ipc",
        "private",
        "--cgroupns",
        "private",
        "--log-driver",
        "none",
        "--restart",
        "no",
        "--no-healthcheck",
        IMAGE,
        *native,
    ]
    need(type(cli) is str and cli, "CLI")
    size = len(subprocess.list2cmdline([cli, "--context", "desktop-linux", *args]))
    need(size <= 26000, "CREATE_SIZE")
    return args, {"case": case.value, "createprocess_chars": size, "margin_chars": 26000 - size}


def identity(info, intent):
    need(type(info) is dict and type(intent) is Intent, "OWNERSHIP")
    task, case = intent.task, intent.case
    cid = info["Id"]
    need(type(cid) is str and re.fullmatch(r"[0-9a-f]{64}", cid), "OWNERSHIP")
    need(
        info["Name"] == "/" + name_for(task, case)
        and info["Image"] == IMAGE
        and info["Config"]["Image"] == IMAGE
        and all(
            info["Config"]["Labels"].get(key) == value for key, value in labels_for(task).items()
        )
        and info["Config"]["Cmd"] == list(intent.command)
        and info["Config"]["Entrypoint"] == ENTRY,
        "OWNERSHIP",
    )
    return cid


def validate_container(info, intent):
    cid = identity(info, intent)
    channel_bytes()  # acceptance may fail on changed input; cleanup ownership never rereads it
    task, case = intent.task, intent.case
    config, host = info["Config"], info["HostConfig"]
    uid = "70" if case is Case.RETAIN else "10001"
    need(
        config["Labels"] == labels_for(task)
        and config["User"] == uid + ":" + uid
        and config["WorkingDir"] == "/var/empty"
        and config["Env"] == ENV
        and config["Tty"] is False
        and config["OpenStdin"] is True
        and config["StdinOnce"] is False
        and not config.get("Volumes")
        and not config.get("ExposedPorts")
        and config.get("Healthcheck") == {"Test": ["NONE"]},
        "CONFIG",
    )
    need(
        host["ReadonlyRootfs"] is True
        and host["NetworkMode"] == "none"
        and host["CapDrop"] == ["ALL"]
        and not host.get("CapAdd")
        and host["SecurityOpt"] == ["no-new-privileges"]
        and host["Memory"] == host["MemorySwap"] == 134217728
        and host["PidsLimit"] == 8
        and host["NanoCpus"] == 1000000000
        and host["ShmSize"] == 8388608,
        "PROFILE",
    )
    need(
        {item["Name"]: (item["Soft"], item["Hard"]) for item in host["Ulimits"]}
        == {"core": (0, 0), "nofile": (128, 128)}
        and len(host["Ulimits"]) == 2
        and host["IpcMode"] == host["CgroupnsMode"] == "private"
        and host["PidMode"] == ""
        and host["RestartPolicy"] == {"Name": "no", "MaximumRetryCount": 0}
        and host["LogConfig"] == {"Type": "none", "Config": {}},
        "ISOLATION",
    )
    need(
        not any(
            host.get(key)
            for key in (
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
        )
        and not info.get("Mounts"),
        "SURFACE",
    )
    return cid


def report(raw, case):
    need(type(case) is Case and case in (Case.NORMAL, Case.READER_NEGATIVE), "REPORT_CASE")
    need(type(raw) is bytes and 0 < len(raw) <= 512 and raw.endswith(b"\n"), "REPORT_SIZE")
    value = json.loads(raw)
    keys = {"kind", "case", "bytes", "equality", "eof_observed", "observation_ms", "uid", "pid"}
    if case is Case.READER_NEGATIVE:
        keys.add("categories")
    need(type(value) is dict and set(value) == keys, "REPORT_SCHEMA")
    need(
        (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii") == raw,
        "REPORT_CANONICAL",
    )
    need(
        value["kind"] == "MASKGW_T4_CANARY_V1"
        and value["case"] == case.value
        and type(value["bytes"]) is int
        and value["bytes"] == 16384
        and value["equality"] is True
        and type(value["eof_observed"]) is bool
        and type(value["observation_ms"]) is int
        and 0 <= value["observation_ms"] <= 2000
        and type(value["uid"]) is int
        and value["uid"] == 10001
        and type(value["pid"]) is int
        and value["pid"] == 1,
        "REPORT_FACTS",
    )
    need(case is not Case.READER_NEGATIVE or value["categories"] == ["FRAME"] * 4, "REPORT_FACTS")
    return value
