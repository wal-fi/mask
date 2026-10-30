"""Owned Oracle candidate installation, commit and probe; no calls on import."""

import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import threading
import time
import zlib

REPO = Path(__file__).resolve().parents[2]
FOUNDATION = REPO / "docs/poc/oracle9_python_prepare.py"
FOUNDATION_SHA = "0b0bb1719834bdc9ccaa4a2ffd4c8da23824d92320e05bf1218af734d2ede1b5"
PAYLOAD = REPO / "deploy/oracle9_offline_install.py"
PAYLOAD_SHA = "ee2becec0e6683807827e3682a410497f94a24d7509d6670cd88b50654d4c5af"
CONTEXT_PROGRAM = REPO / "docs/poc/oracle9_install_context.py"
CONTEXT_SHA = "46108ce61026c09c1beb1c562ece6cad427a393d4d8e9e49f19853cc193f1907"
CONTEXT_ROOT = Path(
    "C:/Users/w.filho/AppData/Local/Temp/maskgw-oracle9-install-context-20261026-4efda1b2"
)
READY_SHA = "3c7959cb6f5a0d89cf827e4dbc85216195be7e62a7415da0081292a195cea92e"
MANIFEST_SHA = "359a055ccbd7689dce453f7979f5d0ac137cd5963f599d462400abe7f1d87c22"
IMAGE = "sha256:1546afefa358aa8c6049350948b1d5d4f272017da8997ae3974c93af7fdc07c4"
ORIGIN_TASK = "4f1d385b3e18464792773488386438dd"


def need(value, category):
    if not value:
        raise RuntimeError(category)


def frozen(path, expected, name):
    raw = path.read_bytes()
    need(len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == expected, "SOURCE_PIN")
    ns = {"__name__": name, "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), ns)
    return ns


def context_inputs():
    module = frozen(CONTEXT_PROGRAM, CONTEXT_SHA, "_frozen_install_context")
    raw = (CONTEXT_ROOT / "ready.json").read_bytes()
    need(hashlib.sha256(raw).hexdigest() == READY_SHA, "CONTEXT_READY")
    ready = json.loads(raw)
    need(
        ready["outcome"] == "OFFLINE_CONTEXT_VERIFIED"
        and ready["installed"] is False
        and ready["docker_invoked"] is False
        and ready["manifest_sha256"] == MANIFEST_SHA,
        "CONTEXT_READY",
    )
    manifest = json.loads((CONTEXT_ROOT / "context/manifest.json").read_bytes())
    module["check_context"](CONTEXT_ROOT / "context", manifest, MANIFEST_SHA)
    module["sources"]()
    return manifest


def native_command(payload, mode, *arguments):
    need(
        len(payload) <= 32768 and hashlib.sha256(payload).hexdigest() == PAYLOAD_SHA, "PAYLOAD_PIN"
    )
    need(mode in ("install", "probe"), "ROLE")
    need(
        (
            mode == "install"
            and len(arguments) == 2
            and re.fullmatch(r"/opt/maskgw/install-inputs-[0-9a-f]{32}", arguments[0])
            and arguments[1] == MANIFEST_SHA
        )
        or (mode == "probe" and len(arguments) == 1 and re.fullmatch("[0-9a-f]{64}", arguments[0])),
        "ROLE_ARGUMENTS",
    )
    encoded = base64.b64encode(zlib.compress(payload, 9)).decode()
    bootstrap = (
        "import base64,zlib,hashlib; p=zlib.decompress(base64.b64decode("
        + repr(encoded)
        + ")); assert hashlib.sha256(p).hexdigest()=="
        + repr(PAYLOAD_SHA)
        + "; exec(compile(p,'<maskgw-oracle9-offline-install>','exec'))"
    )
    command = ["-c", bootstrap, mode, *arguments]
    need(sum(len(v) for v in command) < 26000, "COMMAND_SIZE")
    return command


def identity(info, name, task, image):
    need(info["Name"] == "/" + name and re.fullmatch("[0-9a-f]{64}", info["Id"]), "OWNERSHIP")
    need(
        info["Image"] == image
        and info["Config"]["Labels"]["maskgw.task"] == task
        and info["Config"]["Labels"]["maskgw.source-sha256"] == PAYLOAD_SHA
        and info["Config"]["Labels"]["maskgw.manifest-sha256"] == MANIFEST_SHA,
        "OWNERSHIP",
    )
    return info["Id"]


def create_args(image, name, task, command, probe):
    uid = "10001" if probe else "0"
    tmp = "16777216" if probe else "67108864"
    args = [
        "create",
        "--pull=never",
        "--name",
        name,
        "--label",
        "maskgw.task=" + task,
        "--label",
        "maskgw.source-sha256=" + PAYLOAD_SHA,
        "--label",
        "maskgw.manifest-sha256=" + MANIFEST_SHA,
        "--user",
        uid + ":" + uid,
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory",
        "536870912",
        "--memory-swap",
        "536870912",
        "--pids-limit",
        "32",
        "--cpus",
        "1",
        "--shm-size",
        "8388608",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=" + tmp + ",uid=" + uid + ",gid=" + uid + ",mode=0700",
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
    ]
    if probe:
        args.append("--read-only")
    return [*args, image, *command]


def validate_container(info, name, task, image, command, probe, origin):
    identity(info, name, task, image)
    c, h = info["Config"], info["HostConfig"]
    need(
        c["Image"] == image
        and c["User"] == ("10001:10001" if probe else "0:0")
        and c["WorkingDir"] == "/var/empty"
        and c["Entrypoint"] == origin["ENTRY"]
        and c["Cmd"] == command
        and c["Env"] == origin["ENV"],
        "CONTAINER_CONFIG",
    )
    need(
        not c.get("Tty")
        and not c.get("OpenStdin")
        and not c.get("Volumes")
        and not c.get("ExposedPorts")
        and c.get("Healthcheck") == {"Test": ["NONE"]},
        "CONTAINER_SURFACE",
    )
    need(
        h["ReadonlyRootfs"] is probe
        and h["NetworkMode"] == "none"
        and h["CapDrop"] == ["ALL"]
        and not h.get("CapAdd")
        and h["SecurityOpt"] == ["no-new-privileges"],
        "CONTAINER_PRIVILEGE",
    )
    need(
        h["Memory"] == h["MemorySwap"] == 536870912
        and h["PidsLimit"] == 32
        and h["NanoCpus"] == 1000000000
        and h["ShmSize"] == 8388608,
        "CONTAINER_LIMITS",
    )
    need(
        {v["Name"]: (v["Soft"], v["Hard"]) for v in h["Ulimits"]}
        == {"core": (0, 0), "nofile": (128, 128)},
        "CONTAINER_ULIMITS",
    )
    uid = "10001" if probe else "0"
    tmp = "16777216" if probe else "67108864"
    need(
        h["Tmpfs"]
        == {
            "/tmp": "rw,noexec,nosuid,nodev,size="
            + tmp
            + ",uid="
            + uid
            + ",gid="
            + uid
            + ",mode=0700"
        },
        "CONTAINER_TMPFS",
    )
    need(
        h["IpcMode"] == h["CgroupnsMode"] == "private"
        and h["PidMode"] == ""
        and h["RestartPolicy"] == {"Name": "no", "MaximumRetryCount": 0}
        and h["LogConfig"]["Type"] == "none"
        and not h.get("Privileged")
        and not h.get("Init")
        and not h.get("AutoRemove"),
        "CONTAINER_ISOLATION",
    )
    need(
        not info.get("Mounts")
        and not h.get("Binds")
        and not h.get("Mounts")
        and not h.get("Devices")
        and not h.get("DeviceRequests")
        and not h.get("DeviceCgroupRules")
        and not h.get("GroupAdd")
        and not h.get("Sysctls")
        and not h.get("Links")
        and not h.get("ExtraHosts"),
        "CONTAINER_MOUNTS",
    )


def validate_diff(raw):
    text = raw.decode("utf-8")
    need(len(text) <= 1024 * 1024 and text.splitlines(), "DIFF_EMPTY_OR_SIZE")
    seen, has_attest, has_package = set(), False, False
    for line in text.splitlines():
        need(re.fullmatch(r"[AC] /[^\x00-\x1f]+", line) and line not in seen, "DIFF_FORMAT")
        seen.add(line)
        action, path = line.split(" ", 1)
        need(all(v not in (".", "..", "") for v in path.split("/")[1:]), "DIFF_PATH")
        if path in ("/opt", "/opt/maskgw"):
            need(action == "C", "DIFF_PARENT")
        elif path == "/opt/maskgw/oracle9-installed.json":
            need(action == "A", "DIFF_ATTEST")
            has_attest = True
        else:
            need(path == "/opt/maskgw/venv" or path.startswith("/opt/maskgw/venv/"), "DIFF_ESCAPE")
            has_package |= path.endswith("/maskgw/__init__.py") and action == "A"
    need(has_attest and has_package, "DIFF_INCOMPLETE")
    return len(seen)


def validate_candidate_image(info, task, tag, layers, origin):
    need(
        re.fullmatch("sha256:[0-9a-f]{64}", info["Id"])
        and info["Os"] == "linux"
        and info["Architecture"] == "amd64"
        and info["RepoTags"] == [tag],
        "CANDIDATE_IMAGE",
    )
    need(
        info["RootFS"]["Layers"][: len(layers)] == layers
        and len(info["RootFS"]["Layers"]) == len(layers) + 1,
        "CANDIDATE_LAYERS",
    )
    c = info["Config"]
    need(
        c["User"] == "10001:10001"
        and c["WorkingDir"] == "/var/empty"
        and c["Env"] == origin["ENV"]
        and c["Entrypoint"] == origin["ENTRY"]
        and not c.get("Cmd"),
        "CANDIDATE_CONFIG",
    )
    need(
        c["Labels"]["maskgw.task"] == task
        and c["Labels"]["maskgw.source-sha256"] == PAYLOAD_SHA
        and c["Labels"]["maskgw.manifest-sha256"] == MANIFEST_SHA
        and not c.get("Volumes")
        and not c.get("ExposedPorts")
        and c.get("Healthcheck") in (None, {"Test": ["NONE"]}),
        "CANDIDATE_SURFACE",
    )
    return info["Id"]


def report_line(raw, expected):
    need(
        len(raw) <= 1536 * 1024 and raw.endswith(b"\n") and len(raw.splitlines()) == 1,
        "REPORT_FRAME",
    )
    report = json.loads(raw)
    need(type(report) is dict and report.get("outcome") == expected, "NATIVE_OUTCOME")
    need(
        type(report.get("attestation_sha256")) is str
        and re.fullmatch("[0-9a-f]{64}", report["attestation_sha256"]),
        "ATTESTATION_ID",
    )
    return report


async def main(root):
    need(os.name == "nt" and sys.flags.isolated and not sys.flags.optimize, "HOST_RUNTIME")
    need(
        root.parent.resolve() == (Path(os.environ["LOCALAPPDATA"]) / "Temp").resolve()
        and root.name.startswith("maskgw-oracle9-offline-"),
        "HOST_ROOT",
    )
    need(not root.lstat().st_file_attributes & 0x400, "HOST_ROOT_LINK")
    state = json.loads((root / "attempt.json").read_bytes())
    need(
        state["kind"] == "maskgw-oracle9-offline"
        and state["phase"] == "APP_READY"
        and state["invoked"] is False
        and re.fullmatch("[0-9a-f]{32}", state["task"])
        and not (root / "result.json").exists(),
        "HOST_STATE",
    )
    origin = frozen(FOUNDATION, FOUNDATION_SHA, "_frozen_foundation")
    helper = runpy.run_path(str(origin["HELPER"]))
    payload = PAYLOAD.read_bytes()
    context_inputs()

    def pins():
        origin["pins"]()
        need(
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == state["program_sha256"]
            and hashlib.sha256(PAYLOAD.read_bytes()).hexdigest()
            == state["payload_sha256"]
            == PAYLOAD_SHA,
            "ACTIVE_SOURCE_CHANGED",
        )

    pins()
    state.update(invoked=True, phase="OFFLINE_CONSUMED")
    origin["save"](root / "attempt.json", state)
    result = {
        "profile": "oracle9-offline",
        "task": state["task"],
        "commands": [],
        "outcome": "NOT_PASSED",
        "owned_cleanup": False,
        "inventory_restored": False,
    }
    records, active = [], {"cid": None}
    stop, fired = threading.Event(), threading.Event()
    tag = "maskgw-oracle9-app-candidate:" + state["task"]
    result["intended_candidate_tag"] = tag
    inputs = "/opt/maskgw/install-inputs-" + state["task"]

    def watchdog():
        if not stop.wait(600):
            fired.set()
            if active["cid"] is not None:
                try:
                    origin["pins"]()
                    subprocess.run(
                        [
                            str(origin["CLI"]),
                            "--context",
                            "desktop-linux",
                            "kill",
                            "--signal",
                            "KILL",
                            active["cid"],
                        ],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=helper["environment"](),
                        timeout=10,
                        check=False,
                    )
                except Exception:
                    pass

    thread = threading.Thread(target=watchdog, name="maskgw-oracle9-offline-watchdog", daemon=False)
    thread_started = False

    def write_new(name, raw, limit=4 * 1024 * 1024):
        need(len(raw) <= limit, "EVIDENCE_SIZE")
        with (root / name).open("xb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())

    async def cli(label, *args, timeout=10, limit=2 * 1024 * 1024, cleanup=False):
        if cleanup:
            origin["pins"]()
        else:
            pins()
        result["stage"] = label
        started = time.monotonic()
        try:
            code, raw = await helper["bounded"](
                [str(origin["CLI"]), "--context", "desktop-linux", *args],
                timeout=timeout,
                limit=limit,
            )
        except BaseException as exc:
            result["commands"].append(
                {
                    "name": label,
                    "exit": None,
                    "category": type(exc).__name__,
                    "seconds": time.monotonic() - started,
                }
            )
            raise
        result["commands"].append(
            {
                "name": label,
                "exit": code,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "seconds": time.monotonic() - started,
            }
        )
        return code, raw

    async def inspect(record, profile=False, cleanup=False):
        code, raw = await cli(
            "inspect-" + record["role"],
            "inspect",
            "--type",
            "container",
            record["cid"] or record["name"],
            cleanup=cleanup,
        )
        need(code == 0, "INSPECT_OWN")
        values = json.loads(raw)
        need(type(values) is list and len(values) == 1, "INSPECT_SHAPE")
        info = values[0]
        record["cid"] = identity(info, record["name"], state["task"], record["image"])
        if profile:
            validate_container(
                info,
                record["name"],
                state["task"],
                record["image"],
                record["command"],
                record["role"] == "probe",
                origin,
            )
        return info, raw

    async def create(image, role, command):
        record = {
            "role": role,
            "name": "maskgw-ol9-offline-" + state["task"][:12] + "-" + role,
            "image": image,
            "cid": None,
            "command": command,
            "creation_confirmed": False,
        }
        records.append(record)
        code, raw = await cli(
            "create-" + role,
            *create_args(image, record["name"], state["task"], command, role == "probe"),
        )
        need(code == 0 and re.fullmatch(rb"[0-9a-f]{64}\s*", raw), "CREATE_OWN")
        record["cid"] = raw.decode().strip()
        info, raw = await inspect(record, True)
        need(info["State"]["Running"] is False, "CREATE_NOT_STOPPED")
        record["creation_confirmed"] = True
        write_new(role + "-inspect-before.json", raw)
        return record

    async def run(record, expected):
        await inspect(record, True)
        active["cid"] = record["cid"]
        code, raw = await cli(
            "run-" + record["role"], "start", "--attach", record["cid"], timeout=300
        )
        write_new(record["role"] + ".stdout", raw, 2 * 1024 * 1024)
        info, inspected = await inspect(record, True)
        write_new(record["role"] + "-inspect-after.json", inspected)
        need(
            code == 0
            and info["State"]["Running"] is False
            and info["State"]["Pid"] == 0
            and info["State"]["ExitCode"] == 0
            and info["State"]["OOMKilled"] is False
            and info["State"]["Dead"] is False
            and not fired.is_set(),
            "RUN_EXIT",
        )
        active["cid"] = None
        return report_line(raw, expected)

    async def unused_tag():
        code, raw = await cli(
            "tag-collision",
            "image",
            "ls",
            "--no-trunc",
            "--format",
            "{{.Repository}}:{{.Tag}}",
            tag,
        )
        need(code == 0 and not raw.strip(), "TAG_EXISTS")

    try:
        thread.start()
        thread_started = True
        code, raw = await cli("version", "version", "--format", "{{json .}}")
        need(code == 0, "DAEMON_VERSION")
        write_new("version.json", raw)
        code, raw = await cli("inventory-before", "ps", "-aq", "--no-trunc")
        need(code == 0 and not raw.strip(), "INITIAL_INVENTORY")
        code, raw = await cli("daemon-info", "info", "--format", "{{json .}}")
        need(code == 0, "DAEMON_INFO")
        data = json.loads(raw)
        public = {
            k: data[k]
            for k in (
                "OSType",
                "Architecture",
                "KernelVersion",
                "MemTotal",
                "Driver",
                "CgroupVersion",
                "ServerVersion",
            )
        }
        need(
            public["OSType"] == "linux"
            and public["Architecture"] in ("x86_64", "amd64")
            and public["CgroupVersion"] == "2"
            and public["MemTotal"] >= 2 * 1024 * 1024 * 1024,
            "DAEMON_PROFILE",
        )
        origin["save"](root / "daemon-public.json", public)
        result["daemon_public"] = public
        code, raw = await cli("base-image", "image", "inspect", IMAGE)
        need(code == 0, "BASE_IMAGE_MISSING")
        write_new("image-inspect.json", raw)
        base = json.loads(raw)
        need(
            type(base) is list
            and len(base) == 1
            and origin["validate_prepared_image"](
                base[0], ORIGIN_TASK, "maskgw-oracle9-python:" + ORIGIN_TASK
            )
            == IMAGE,
            "BASE_IMAGE",
        )
        layers = base[0]["RootFS"]["Layers"]
        await unused_tag()
        install = await create(
            IMAGE, "install", native_command(payload, "install", inputs, MANIFEST_SHA)
        )
        context_inputs()
        await inspect(install, True)
        code, raw = await cli(
            "copy-public-inputs",
            "cp",
            str(CONTEXT_ROOT / "context"),
            install["cid"] + ":" + inputs,
            timeout=60,
        )
        write_new("copy.stdout", raw)
        need(code == 0, "COPY_INPUTS")
        context_inputs()
        installed = await run(install, "CANDIDATE_INSTALL_VERIFIED")
        result["installation"] = installed
        need(installed["managed_inputs_removed"] is True, "INPUTS_REMAIN")
        await inspect(install, True)
        attestation_path = root / "installed-attestation.json"
        need(not attestation_path.exists(), "ATTESTATION_COLLISION")
        code, raw = await cli(
            "copy-attestation",
            "cp",
            install["cid"] + ":/opt/maskgw/oracle9-installed.json",
            str(attestation_path),
            timeout=20,
        )
        need(
            code == 0
            and attestation_path.stat().st_size == installed["attestation_bytes"] <= 4 * 1024 * 1024
            and hashlib.sha256(attestation_path.read_bytes()).hexdigest()
            == installed["attestation_sha256"],
            "ATTESTATION_COPY",
        )
        code, raw = await cli("candidate-diff", "diff", install["cid"], limit=1024 * 1024)
        write_new("diff.txt", raw)
        need(code == 0, "DIFF_EXIT")
        result["diff_lines"] = validate_diff(raw)
        await unused_tag()
        info, _ = await inspect(install, True)
        need(info["State"]["Running"] is False, "COMMIT_NOT_STOPPED")
        changes = [
            "USER 10001:10001",
            "WORKDIR /var/empty",
            "ENTRYPOINT " + json.dumps(origin["ENTRY"]),
            "CMD []",
        ]
        arguments = ["commit"]
        for value in changes:
            arguments.extend(["--change", value])
        code, raw = await cli("commit-own", *arguments, install["cid"], tag, timeout=60)
        write_new("commit.stdout", raw)
        need(code == 0, "COMMIT_EXIT")
        code, raw = await cli("candidate-image", "image", "inspect", tag)
        need(code == 0, "CANDIDATE_INSPECT")
        write_new("candidate-image-inspect.json", raw)
        values = json.loads(raw)
        need(type(values) is list and len(values) == 1, "CANDIDATE_SHAPE")
        candidate = validate_candidate_image(values[0], state["task"], tag, layers, origin)
        result.update(
            candidate_image=candidate,
            candidate_tag=tag,
            candidate_layers=values[0]["RootFS"]["Layers"],
        )
        probe_record = await create(
            candidate, "probe", native_command(payload, "probe", installed["attestation_sha256"])
        )
        verified = await run(probe_record, "CANDIDATE_PROBE_VERIFIED")
        need(verified["attestation_sha256"] == installed["attestation_sha256"], "PROBE_ATTESTATION")
        result["probe"] = verified
        context_inputs()
        need(not fired.is_set(), "WATCHDOG")
        result["outcome"] = "ORACLE9_APP_CANDIDATE_VERIFIED"
    except BaseException as exc:
        result["failure"] = type(exc).__name__
    finally:
        clean = True
        for record in reversed(records):
            try:
                if record["cid"] is None:
                    clean = False
                info, _ = await inspect(record, cleanup=True)
                if info["State"]["Running"]:
                    code, _ = await cli(
                        "kill-own", "kill", "--signal", "KILL", record["cid"], cleanup=True
                    )
                    need(code == 0, "KILL_EXIT")
                    info, _ = await inspect(record, cleanup=True)
                need(
                    info["State"]["Running"] is False and info["State"]["Pid"] == 0,
                    "CLEANUP_NOT_STOPPED",
                )
                code, _ = await cli("remove-own", "rm", record["cid"], cleanup=True)
                need(code == 0, "REMOVE_EXIT")
                code, raw = await cli(
                    "own-absent",
                    "ps",
                    "-aq",
                    "--no-trunc",
                    "--filter",
                    "id=" + record["cid"],
                    cleanup=True,
                )
                need(code == 0 and not raw.strip(), "OWN_NOT_ABSENT")
                record["removed"] = True
            except BaseException:
                clean = False
                record["cleanup_unproven"] = True
        active["cid"] = None
        stop.set()
        if thread_started:
            thread.join(timeout=12)
            clean &= not thread.is_alive()
        result["watchdog_fired"] = fired.is_set()
        result["owned_cleanup"] = clean
        result["containers"] = [{k: v for k, v in r.items() if k != "command"} for r in records]
        try:
            code, raw = await cli("inventory-after", "ps", "-aq", "--no-trunc", cleanup=True)
            result["inventory_restored"] = code == 0 and not raw.strip()
        except BaseException:
            result["inventory_restored"] = False
        if not clean or not result["inventory_restored"] or fired.is_set():
            result["outcome"] = "NOT_PASSED"
        origin["save"](root / "result.json", result)
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("outcome", "owned_cleanup", "inventory_restored", "watchdog_fired")
            },
            sort_keys=True,
        )
    )
    return 0 if result["outcome"] == "ORACLE9_APP_CANDIDATE_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(Path(sys.argv[1]))))
