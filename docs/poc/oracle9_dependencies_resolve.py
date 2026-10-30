"""One-shot public dependency metadata resolution; no Docker calls on import."""

import asyncio
import base64
import hashlib
import json
import os
import pathlib
import re
import runpy
import subprocess
import sys
import threading
import time
import tomllib
import zlib

REPO = pathlib.Path(__file__).resolve().parents[2]
FOUNDATION = REPO / "docs/poc/oracle9_python_prepare.py"
FOUNDATION_SHA = "0b0bb1719834bdc9ccaa4a2ffd4c8da23824d92320e05bf1218af734d2ede1b5"
PAYLOAD = REPO / "deploy/oracle9_dependencies.py"
IMAGE = "sha256:1546afefa358aa8c6049350948b1d5d4f272017da8997ae3974c93af7fdc07c4"
ORIGIN_TASK = "4f1d385b3e18464792773488386438dd"
ORIGIN_TAG = "maskgw-oracle9-python:" + ORIGIN_TASK
TMPFS = "rw,noexec,nosuid,nodev,size=134217728,uid=10001,gid=10001,mode=0700"


def require(value):
    if not value:
        raise RuntimeError("RESOLUTION_PREPARATION_REFUSED")


def frozen_foundation():
    raw = FOUNDATION.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == FOUNDATION_SHA)
    namespace = {"__file__": str(FOUNDATION), "__name__": "_oracle9_frozen_preparation"}
    exec(compile(raw, str(FOUNDATION), "exec"), namespace)
    return namespace


def inputs_from_files():
    raw = (REPO / "pyproject.toml").read_bytes()
    seed = (REPO / "deploy/constraints-tested.txt").read_bytes()
    return {
        "requirements": tomllib.loads(raw.decode("utf8"))["project"]["dependencies"],
        "constraints": seed.decode("utf8"),
        "project_sha256": hashlib.sha256(raw).hexdigest(),
        "seed_sha256": hashlib.sha256(seed).hexdigest(),
    }


def native_command(payload, inputs):
    require(len(payload) <= 65536)
    packed = base64.b64encode(zlib.compress(payload, 9)).decode("ascii")
    digest = hashlib.sha256(payload).hexdigest()
    boot = (
        "import base64,zlib,hashlib; "
        "p=zlib.decompress(base64.b64decode(" + repr(packed) + ")); "
        "assert hashlib.sha256(p).hexdigest()==" + repr(digest) + "; "
        "exec(compile(p,'<oracle9-public-dependency-resolver>','exec'))"
    )
    encoded = base64.b64encode(json.dumps(inputs, sort_keys=True).encode()).decode("ascii")
    require(len(encoded) <= 16384)
    command = ["-c", boot, encoded]
    require(sum(len(v) for v in command) <= 26000)
    return command


def validate_owned_identity(info, task, source_sha, name):
    require(info["Name"] == "/" + name and re.fullmatch("[0-9a-f]{64}", info["Id"]))
    require(info["Image"] == IMAGE)
    labels = info["Config"]["Labels"]
    require(labels["maskgw.task"] == task and labels["maskgw.source-sha256"] == source_sha)
    return info["Id"]


def validate_container(info, task, source_sha, name, command, origin):
    validate_owned_identity(info, task, source_sha, name)
    c, h = info["Config"], info["HostConfig"]
    require(info["Image"] == IMAGE and c["Image"] == IMAGE and c["User"] == "10001:10001")
    require(
        c["Entrypoint"] == origin["ENTRY"] and c["Cmd"] == command and c["Env"] == origin["ENV"]
    )
    require(
        c["Labels"]["maskgw.task"] == task and c["Labels"]["maskgw.source-sha256"] == source_sha
    )
    require(h["Memory"] == h["MemorySwap"] == 512 * 1024 * 1024 and h["PidsLimit"] == 32)
    require(h["NanoCpus"] == 1000000000 and h["ShmSize"] == 1024 * 1024)
    require(h["ReadonlyRootfs"] is True and h["Privileged"] is False)
    require(
        h["NetworkMode"] == "bridge" and not h.get("PortBindings") and not h.get("PublishAllPorts")
    )
    require(not h.get("CapAdd") and h["CapDrop"] == ["ALL"])
    require(h["SecurityOpt"] in (["no-new-privileges"], ["no-new-privileges:true"]))
    require(h["Tmpfs"] == {"/tmp": TMPFS} and not h.get("Binds") and not h.get("Mounts"))
    require(h.get("IpcMode") == "private" and h.get("CgroupnsMode") == "private")
    require(h.get("PidMode", "") == "" and h.get("UTSMode", "") == "")
    require(not h.get("Devices") and not h.get("DeviceRequests") and not h.get("ExtraHosts"))
    require(h["LogConfig"]["Type"] == "none" and h["RestartPolicy"]["Name"] == "no")
    limits = {v["Name"]: (v["Soft"], v["Hard"]) for v in h["Ulimits"]}
    require(limits == {"core": (0, 0), "nofile": (128, 128)})
    mounts = info.get("Mounts", [])
    require(
        len(mounts) <= 1
        and all(
            v["Type"] == "tmpfs" and v["Destination"] == "/tmp" and not v.get("Source")
            for v in mounts
        )
    )
    require(
        not c.get("ExposedPorts")
        and not c.get("Volumes")
        and c.get("Healthcheck") in (None, {"Test": ["NONE"]})
    )
    return info["Id"]


async def main(root):
    require(os.name == "nt" and sys.flags.isolated and not sys.flags.optimize)
    require(root.parent.resolve() == (pathlib.Path(os.environ["LOCALAPPDATA"]) / "Temp").resolve())
    require(root.name.startswith("maskgw-oracle9-resolve-20261025-") and not root.is_symlink())
    require(not root.lstat().st_file_attributes & 0x400)
    state = json.loads((root / "attempt.json").read_bytes())
    require(
        state["kind"] == "maskgw-oracle9-resolve" and re.fullmatch("[0-9a-f]{32}", state["task"])
    )
    require(
        state["invoked"] is False
        and state["phase"] == "APP_READY"
        and not (root / "result.json").exists()
    )
    require(
        hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest() == state["program_sha256"]
    )
    payload = PAYLOAD.read_bytes()
    require(hashlib.sha256(payload).hexdigest() == state["payload_sha256"])
    inputs = inputs_from_files()
    require(
        inputs["project_sha256"] == state["project_sha256"]
        and inputs["seed_sha256"] == state["seed_sha256"]
    )
    ns = {"__name__": "_oracle9_resolution_policy", "__file__": str(PAYLOAD)}
    exec(compile(payload, str(PAYLOAD), "exec"), ns)
    ns["validate_inputs"](inputs)
    origin = frozen_foundation()
    origin["pins"]()
    helper = runpy.run_path(str(origin["HELPER"]))
    cli_path, save = str(origin["CLI"]), origin["save"]
    state.update(invoked=True, phase="RESOLUTION_CONSUMED")
    save(root / "attempt.json", state)
    result = {
        "profile": "oracle9-resolve",
        "task": state["task"],
        "commands": [],
        "outcome": "NOT_PASSED",
        "owned_cleanup": False,
        "inventory_restored": False,
    }
    stop, fired = threading.Event(), threading.Event()
    active = {"cid": None}
    name = "maskgw-ol9-resolve-" + state["task"][:12]
    command = native_command(payload, inputs)
    created = False

    def watchdog():
        if not stop.wait(300):
            fired.set()
            if active["cid"] is not None:
                try:
                    origin["pins"]()
                    subprocess.run(
                        [
                            cli_path,
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
                        timeout=10,
                        check=False,
                        env=helper["environment"](),
                    )
                except Exception:
                    pass

    thread = threading.Thread(target=watchdog, name="maskgw-oracle9-resolve-watchdog", daemon=False)

    async def cli(label, *args, timeout=10, limit=2 * 1024 * 1024):
        origin["pins"]()
        result["stage"] = label
        started = time.monotonic()
        code, raw = await helper["bounded"](
            [cli_path, "--context", "desktop-linux", *args], timeout=timeout, limit=limit
        )
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

    def write_new(filename, raw):
        require(len(raw) <= 2 * 1024 * 1024)
        with (root / filename).open("xb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())

    async def inspect(verify_profile=False):
        code, raw = await cli("inspect-own", "inspect", active["cid"] or name)
        require(code == 0)
        value = json.loads(raw)
        require(type(value) is list and len(value) == 1)
        cid = validate_owned_identity(value[0], state["task"], state["payload_sha256"], name)
        active["cid"] = cid
        if verify_profile:
            validate_container(
                value[0], state["task"], state["payload_sha256"], name, command, origin
            )
        return value[0], raw

    thread_started = False
    try:
        thread.start()
        thread_started = True
        code, raw = await cli("version", "version", "--format", "{{json .}}")
        require(code == 0)
        write_new("version.json", raw)
        code, raw = await cli("inventory-before", "ps", "-aq", "--no-trunc")
        require(code == 0 and not raw.strip())
        code, raw = await cli("daemon-info", "info", "--format", "{{json .}}")
        require(code == 0)
        info = json.loads(raw)
        public = {
            key: info[key]
            for key in (
                "OSType",
                "Architecture",
                "KernelVersion",
                "MemTotal",
                "Driver",
                "CgroupVersion",
                "ServerVersion",
            )
        }
        require(public["OSType"] == "linux" and public["Architecture"] in ("x86_64", "amd64"))
        require(type(public["MemTotal"]) is int and public["MemTotal"] >= 2 * 1024 * 1024 * 1024)
        require(public["CgroupVersion"] == "2")
        save(root / "daemon-public.json", public)
        result["daemon_public"] = public
        code, raw = await cli("base-image", "image", "inspect", IMAGE)
        require(code == 0)
        write_new("image-inspect.json", raw)
        values = json.loads(raw)
        require(type(values) is list and len(values) == 1)
        require(origin["validate_prepared_image"](values[0], ORIGIN_TASK, ORIGIN_TAG) == IMAGE)
        result["base_diffids"] = values[0]["RootFS"]["Layers"]
        args = [
            "create",
            "--pull=never",
            "--name",
            name,
            "--label",
            "maskgw.task=" + state["task"],
            "--label",
            "maskgw.source-sha256=" + state["payload_sha256"],
            "--user",
            "10001:10001",
            "--read-only",
            "--network",
            "bridge",
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
            "1m",
            "--tmpfs",
            "/tmp:" + TMPFS,
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
            *command,
        ]
        require(sum(len(v) + 3 for v in args) + len(cli_path) < 28000)
        created = True
        code, raw = await cli("create-resolver", *args, timeout=20)
        require(code == 0 and re.fullmatch("[0-9a-f]{64}", raw.decode().strip()))
        created_id = raw.decode().strip()
        value, raw = await inspect(True)
        require(value["Id"] == created_id)
        require(not value["State"]["Running"])
        write_new("resolver-inspect-before.json", raw)
        code, raw = await cli("resolve", "start", "--attach", active["cid"], timeout=180)
        write_new("resolution.stdout", raw)
        require(code == 0 and not fired.is_set())
        packet = json.loads(raw)
        original = ns["validate_packet"](packet, inputs)
        result["projection"] = packet["projection"]
        result["raw_report_sha256"] = hashlib.sha256(original).hexdigest()
        result["raw_report_bytes"] = len(original)
        result["resolution_sha256"] = hashlib.sha256(raw).hexdigest()
        value, raw = await inspect(True)
        require(
            not value["State"]["Running"]
            and value["State"]["ExitCode"] == 0
            and value["State"]["OOMKilled"] is False
        )
        write_new("resolver-inspect-after.json", raw)
        require(
            inputs_from_files() == inputs
            and hashlib.sha256(PAYLOAD.read_bytes()).hexdigest() == state["payload_sha256"]
        )
        require(
            hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
            == state["program_sha256"]
        )
        result["outcome"] = "LINUX_DEPENDENCY_REPORT_PASSED"
    except BaseException:
        result["failure_stage"] = result.get("stage", "PRECHECK")
    finally:
        clean = True
        if created:
            try:
                value, _ = await inspect()
                if value["State"]["Running"]:
                    code, _ = await cli(
                        "stop-own", "stop", "--time", "5", active["cid"], timeout=15
                    )
                    require(code == 0)
                    value, _ = await inspect()
                require(not value["State"]["Running"])
                result["state_before_cleanup"] = {
                    k: value["State"][k] for k in ("ExitCode", "OOMKilled", "Running")
                }
                result["container_id"] = active["cid"]
                code, _ = await cli("remove-own", "rm", active["cid"])
                require(code == 0)
            except BaseException:
                clean = False
        stop.set()
        if thread_started:
            thread.join(timeout=15)
        require(not thread.is_alive())
        result["watchdog_fired"] = fired.is_set()
        result["owned_cleanup"] = clean
        try:
            code, raw = await cli("inventory-after", "ps", "-aq", "--no-trunc")
            result["inventory_restored"] = code == 0 and not raw.strip()
        except BaseException:
            result["inventory_restored"] = False
        if not clean or not result["inventory_restored"] or fired.is_set():
            result["outcome"] = "NOT_PASSED"
        save(root / "result.json", result)
        print(json.dumps({k: v for k, v in result.items() if k != "projection"}))
    return 0 if result["outcome"] == "LINUX_DEPENDENCY_REPORT_PASSED" else 2


if __name__ == "__main__":
    require(len(sys.argv) == 2)
    raise SystemExit(asyncio.run(main(pathlib.Path(sys.argv[1]))))
