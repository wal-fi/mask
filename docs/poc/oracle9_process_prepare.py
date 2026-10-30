"""One owned secretless guard probe. No Docker/Desktop actions on import."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

REPO = Path(__file__).resolve().parents[2]
FOUNDATION = REPO / "docs/poc/oracle9_python_prepare.py"
FOUNDATION_SHA = "0b0bb1719834bdc9ccaa4a2ffd4c8da23824d92320e05bf1218af734d2ede1b5"
POLICY = REPO / "docs/poc/oracle9_offline_prepare.py"
POLICY_SHA = "401afa8cb18156e59016650ac4b87bf3186af1641685fdb05ea2fb7df5363fce"
GUARD = REPO / "src/maskgw/runtime/linux_guard.py"
PAYLOAD = REPO / "deploy/oracle9_process_probe.py"
APP_SOURCE = REPO / "docs/poc/evidence/oracle9-app-wheel-result-20261026.json"
APP_SOURCE_SHA = "d0909fcf1ee17ff4ebb79d42746589f06a84c44a4686b65e30cf6ed22387606a"
IMAGE = "sha256:87871290b01b0e4b8cd9dd90b8001a89ff4e04bd018e12c01ddbff8d6b16483a"
ORIGIN_TASK = "c23dd3df7b4241b4b0757da3863f8f8a"
LAYERS = [
    "sha256:c8033153c9465fa4e4f02df8b57cda30011514f5b1e7438bf521776e63f0abaf",
    "sha256:9a40c1add57e0336e3d66b67f5495c053b7e9dcdc8a635a155570174d926b44d",
]


def need(value, category):
    if not value:
        raise RuntimeError(category)


def regular(path, maximum):
    stat = path.lstat()
    need(
        path.is_file()
        and not path.is_symlink()
        and not getattr(stat, "st_file_attributes", 0) & 0x400,
        "REGULAR",
    )
    need(stat.st_size <= maximum, "FILE_SIZE")
    raw = path.read_bytes()
    need(len(raw) == stat.st_size, "FILE_CHANGED")
    return raw


def frozen(path, expected, name):
    raw = regular(path, 65536)
    need(hashlib.sha256(raw).hexdigest() == expected, "SOURCE_PIN")
    namespace = {"__name__": name, "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace


def source_inputs():
    """No old context admission: its source set predates the new guard."""
    origin = frozen(FOUNDATION, FOUNDATION_SHA, "_process_foundation")
    origin["pins"]()
    original = frozen(POLICY, POLICY_SHA, "_process_image_policy")
    profile = frozen(POLICY, POLICY_SHA, "_process_container_policy")
    native_raw = regular(PAYLOAD, 32768)
    native = frozen(PAYLOAD, hashlib.sha256(native_raw).hexdigest(), "_process_native_probe")
    guard = regular(GUARD, 16384)
    need(hashlib.sha256(guard).hexdigest() == native["GUARD_SHA"], "GUARD_PIN")
    raw = regular(APP_SOURCE, 256 * 1024)
    need(hashlib.sha256(raw).hexdigest() == APP_SOURCE_SHA, "APP_SOURCE_PIN")
    for row in json.loads(raw)["source_manifest"]:
        data = regular(REPO / row["path"], 4 * 1024 * 1024)
        need(
            len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"],
            "OLD_PRODUCT_CHANGED",
        )
    # Same frozen profile functions, rebinding only the NEW CID source label.
    # Original image policy retains the original installer label ee2becec.
    profile["PAYLOAD_SHA"] = hashlib.sha256(native_raw).hexdigest()
    return origin, original, profile, native, guard, native_raw


def admit_captured(state, native, guard, payload):
    need(
        hashlib.sha256(payload).hexdigest() == state["payload_sha256"]
        and hashlib.sha256(guard).hexdigest() == state["guard_sha256"] == native["GUARD_SHA"],
        "CAPTURED_SOURCE_PIN",
    )


def report_line(raw):
    need(len(raw) <= 16384 and len(raw.splitlines()) == 1 and raw.endswith(b"\n"), "REPORT_FRAME")
    value = json.loads(raw)
    need(
        value.get("outcome") == "ORACLE9_PROCESS_GUARD_VERIFIED"
        and value.get("phase") == "COMPLETE",
        "NATIVE_FAILED",
    )
    need(value["remaining_pids"] == [1] and value["pid1_death_proved"] is False, "SCOPE")
    need(
        value["differential"] == dict.fromkeys(("mem", "vm", "ptrace", "environ", "fd"), True),
        "DIFFERENTIAL",
    )
    controller = value["controller"]
    need(
        controller["pid"] == 1
        and controller["dumpable"] == 0
        and controller["pdeathsig"] == 0
        and controller["as_bytes"] == 384 * 1024 * 1024
        and controller["core"] == [0, 0],
        "CONTROLLER",
    )
    pids = []
    for label, dump in (("positive", 1), ("negative", 0)):
        case = value[label]
        ready = case["ready"]
        pid = ready["pid"]
        facts = ready["guard"]
        need(type(pid) is int and 1 < pid < (1 << 31) and ready["dumpable"] == dump, "CHILD_ID")
        need(
            facts["pid"] == pid
            and facts["parent_pid"] == 1
            and facts["pdeathsig"] == 9
            and facts["core"] == [0, 0]
            and facts["as_bytes"] == 256 * 1024 * 1024,
            "CHILD_FACTS",
        )
        need(case["exit_code"] == 0, "CHILD_EXIT")
        for name in ("mem", "vm", "ptrace", "environ", "fd"):
            row = case[name]
            need(
                (row == {"allowed": True, "equal": True, "errno": 0})
                if dump
                else (
                    row["allowed"] is False and row["equal"] is False and row["errno"] in (1, 13)
                ),
                "ACCESS",
            )
        pids.append(pid)
    need(len(set(pids)) == 2, "CHILD_REUSE")
    need(
        value["parent_death"]["grandchild_signal"] == 9
        and value["parent_death"]["reaped"] is True
        and value["parent_death"]["intermediate_exit"] == 0,
        "PARENT_DEATH",
    )
    wrong = value["wrong_parent"]
    need(
        wrong["ready"] is False
        and wrong["refused"] == "PARENT"
        and wrong["dumpable"] == 1
        and wrong["as_unchanged"] is True
        and wrong["actual_parent_pid"] == 1
        and wrong["expected_parent_pid"] not in {1, wrong["pid"]},
        "WRONG_PARENT",
    )
    return value


async def main(root):
    need(os.name == "nt" and sys.flags.isolated and sys.flags.dont_write_bytecode, "HOST_RUNTIME")
    need(
        root.parent.resolve() == (Path(os.environ["LOCALAPPDATA"]) / "Temp").resolve()
        and root.name.startswith("maskgw-oracle9-process-")
        and not root.lstat().st_file_attributes & 0x400,
        "ROOT",
    )
    state = json.loads(regular(root / "attempt.json", 32768))
    need(
        state["kind"] == "maskgw-oracle9-process"
        and state["image"] == IMAGE
        and state["phase"] == "APP_READY"
        and state["invoked"] is False
        and re.fullmatch("[0-9a-f]{32}", state["task"])
        and not (root / "result.json").exists(),
        "STATE",
    )
    origin, image_policy, policy, native, guard, payload = source_inputs()
    admit_captured(state, native, guard, payload)
    helper = frozen(origin["HELPER"], origin["PINS"][origin["HELPER"]], "_process_bounded_helper")
    inputs = {
        GUARD: state["guard_sha256"],
        PAYLOAD: state["payload_sha256"],
        Path(__file__): state["program_sha256"],
    }

    def pins():
        origin["pins"]()
        need(
            all(
                hashlib.sha256(regular(path, 65536)).hexdigest() == expected
                for path, expected in inputs.items()
            ),
            "ACTIVE_SOURCE_CHANGED",
        )

    pins()
    state.update(invoked=True, phase="PROCESS_CONSUMED")
    origin["save"](root / "attempt.json", state)
    result = {
        "profile": "oracle9-process",
        "task": state["task"],
        "commands": [],
        "outcome": "NOT_PASSED",
        "owned_cleanup": False,
        "inventory_restored": False,
    }
    stop, fired = threading.Event(), threading.Event()
    record = None
    active = {"cid": None, "name": None}
    deadline = time.monotonic() + 180

    async def cli(label, *args, timeout=20, cleanup=False):
        (origin["pins"] if cleanup else pins)()
        if not cleanup:
            timeout = min(timeout, deadline - time.monotonic())
            need(timeout > 0, "LOT_DEADLINE")
        start = time.monotonic()
        try:
            code, raw = await helper["bounded"](
                [str(origin["CLI"]), "--context", "desktop-linux", *args],
                timeout=timeout,
                limit=2 * 1024 * 1024,
            )
        except BaseException as failure:
            result["commands"].append(
                {
                    "name": label,
                    "exit": None,
                    "failure_type": type(failure).__name__,
                    "seconds": time.monotonic() - start,
                }
            )
            raise
        result["commands"].append(
            {
                "name": label,
                "exit": code,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "seconds": time.monotonic() - start,
            }
        )
        return code, raw

    def watchdog():
        if not stop.wait(180):
            fired.set()
            if active["cid"] is not None:
                try:
                    origin["pins"]()
                    command = [str(origin["CLI"]), "--context", "desktop-linux"]
                    code, raw = asyncio.run(
                        helper["bounded"](
                            command + ["inspect", "--type", "container", active["cid"]],
                            timeout=15,
                            limit=262144,
                        )
                    )
                    need(code == 0, "WATCHDOG_INSPECT")
                    info = json.loads(raw)[0]
                    policy["identity"](info, active["name"], state["task"], IMAGE)
                    asyncio.run(
                        helper["bounded"](
                            command + ["kill", "--signal", "KILL", active["cid"]],
                            timeout=15,
                            limit=65536,
                        )
                    )
                except BaseException:
                    pass

    thread = threading.Thread(target=watchdog, name="maskgw-process-probe-watchdog", daemon=False)
    thread_started = False

    def write_new(name, raw):
        need(len(raw) <= 2 * 1024 * 1024, "ARTIFACT_SIZE")
        with (root / name).open("xb") as stream:
            stream.write(raw)

    async def inspect(cleanup=False):
        code, raw = await cli(
            "inspect-own",
            "inspect",
            "--type",
            "container",
            record["cid"] or record["name"],
            cleanup=cleanup,
        )
        need(code == 0, "INSPECT")
        info = json.loads(raw)[0]
        cid = policy["identity"](info, record["name"], state["task"], IMAGE)
        need(record["cid"] in (None, cid), "CID_CHANGED")
        record["cid"] = cid
        if not cleanup:
            policy["validate_container"](
                info, record["name"], state["task"], IMAGE, record["command"], True, origin
            )
        return info, raw

    try:
        thread_started = True
        thread.start()
        code, raw = await cli("inventory-before", "ps", "-aq", "--no-trunc")
        need(code == 0 and not raw.strip(), "INITIAL_INVENTORY")
        code, raw = await cli("version", "version", "--format", "{{json .}}")
        need(code == 0, "VERSION")
        write_new("version.json", raw)
        code, raw = await cli("daemon-info", "info", "--format", "{{json .}}")
        need(code == 0, "DAEMON_INFO")
        daemon = json.loads(raw)
        public = {
            key: daemon[key]
            for key in (
                "OSType",
                "Architecture",
                "CgroupVersion",
                "MemTotal",
                "KernelVersion",
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
        result["daemon_public"] = public
        code, raw = await cli("image", "image", "inspect", IMAGE)
        need(code == 0, "IMAGE_MISSING")
        image = json.loads(raw)[0]
        need(
            image_policy["validate_candidate_image"](
                image, ORIGIN_TASK, "maskgw-oracle9-app-candidate:" + ORIGIN_TASK, LAYERS, origin
            )
            == IMAGE,
            "IMAGE_ID",
        )
        write_new("image-inspect.json", raw)
        command = ["-c", native["bootstrap"](guard, payload), "controller"]
        record = {
            "name": "maskgw-ol9-process-" + state["task"][:12],
            "cid": None,
            "command": command,
        }
        code, raw = await cli(
            "create-own",
            *policy["create_args"](IMAGE, record["name"], state["task"], command, True),
        )
        need(code == 0 and re.fullmatch(rb"[0-9a-f]{64}\s*", raw), "CREATE")
        record["cid"] = raw.decode().strip()
        info, raw = await inspect()
        need(info["State"]["Running"] is False and info["State"]["Pid"] == 0, "CREATED_RUNNING")
        write_new("inspect-before.json", raw)
        active.update(cid=record["cid"], name=record["name"])
        code, raw = await cli("run-own", "start", "--attach", record["cid"], timeout=120)
        write_new("native.stdout", raw)
        info, checked = await inspect()
        write_new("inspect-after.json", checked)
        need(
            code == 0
            and info["State"]["Running"] is False
            and info["State"]["Pid"] == 0
            and info["State"]["ExitCode"] == 0
            and not info["State"]["OOMKilled"]
            and not info["State"]["Dead"],
            "RUN_EXIT",
        )
        result["native"] = report_line(raw)
        code, raw = await cli("diff-own", "diff", record["cid"])
        write_new("diff.stdout", raw)
        need(code == 0 and not raw.strip(), "READONLY_DIFF")
        _origin, _image_policy, _policy, final_native, final_guard, final_payload = source_inputs()
        admit_captured(state, final_native, final_guard, final_payload)
        need(not fired.is_set(), "WATCHDOG")
        result["outcome"] = "ORACLE9_PROCESS_GUARD_VERIFIED"
    except BaseException as error:
        result["failure_type"] = type(error).__name__
    finally:
        clean = True
        if record is not None:
            try:
                info, _ = await inspect(cleanup=True)
                if info["State"]["Running"]:
                    code, _ = await cli(
                        "kill-own", "kill", "--signal", "KILL", record["cid"], cleanup=True
                    )
                    need(code == 0, "KILL")
                    info, _ = await inspect(cleanup=True)
                need(
                    info["State"]["Running"] is False and info["State"]["Pid"] == 0,
                    "CLEANUP_RUNNING",
                )
                code, _ = await cli("remove-own", "rm", record["cid"], cleanup=True)
                need(code == 0, "REMOVE")
                code, raw = await cli(
                    "own-absent",
                    "ps",
                    "-aq",
                    "--no-trunc",
                    "--filter",
                    "id=" + record["cid"],
                    cleanup=True,
                )
                need(code == 0 and not raw.strip(), "OWN_REMAINS")
                record["removed"] = True
            except BaseException:
                clean = False
        active["cid"] = None
        stop.set()
        if thread_started:
            try:
                thread.join(timeout=35)
                clean &= not thread.is_alive()
            except RuntimeError:
                clean = False  # Failed/uncertain thread start is not proof of no resource.
        result["watchdog_fired"] = fired.is_set()
        result["owned_cleanup"] = clean
        result["containers"] = (
            [{k: v for k, v in record.items() if k != "command"}] if record else []
        )
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
                key: result[key]
                for key in ("outcome", "owned_cleanup", "inventory_restored", "watchdog_fired")
            },
            sort_keys=True,
        )
    )
    return 0 if result["outcome"] == "ORACLE9_PROCESS_GUARD_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(Path(sys.argv[1]))))
