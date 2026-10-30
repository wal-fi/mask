"""Bounded host observer for four disposable synthetic cases; never product.

No Docker calls on import. Requires an already running engine and already pinned
local image. Does not pull, start Desktop, change the daemon or run docker exec.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

MIB = 1024 * 1024
MAX_REPORT = 65536
MAX_METADATA = 256 * 1024
LOT_SECONDS = 180
CASE_SECONDS = 30
CASES = ("baseline", "control", "private", "shared")
IMAGE_PATTERN = re.compile(r"python@sha256:[0-9a-f]{64}\Z")
ID_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class HostFault(Exception):
    def __init__(self, category="COLLECTION"):
        self.category = category
        super().__init__(category)


def digest(path):
    data = path.read_bytes()
    if len(data) > MAX_REPORT:
        raise HostFault("SOURCE_LIMIT")
    return hashlib.sha256(data).hexdigest()


def environment():
    keys = (
        "SystemRoot",
        "WINDIR",
        "PATH",
        "PATHEXT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
        "HOMEDRIVE",
        "HOMEPATH",
        "ProgramData",
        "ProgramFiles",
    )
    return {key: os.environ[key] for key in keys if key in os.environ}


def translated_sources(path):
    normalized = str(path).replace("\\", "/").lower()
    result = {normalized}
    if re.match(r"^[a-z]:/", normalized):
        suffix = normalized[0] + normalized[2:]
        result.update({"/run/desktop/mnt/host/" + suffix, "/host_mnt/" + suffix})
    return result


def validate_identity(info, *, task, source_hash, name, container_id=None):
    try:
        if info["Name"] != "/" + name or not ID_PATTERN.fullmatch(info["Id"]):
            raise HostFault("IDENTITY")
        if container_id is not None and info["Id"] != container_id:
            raise HostFault("IDENTITY")
        labels = info["Config"]["Labels"]
        if labels.get("maskgw.task") != task or labels.get("maskgw.source-sha256") != source_hash:
            raise HostFault("IDENTITY")
    except (KeyError, TypeError, AttributeError):
        raise HostFault("INSPECT_SCHEMA") from None


def validate_inspect(info, *, image, task, source_hash, source, name):
    validate_identity(info, task=task, source_hash=source_hash, name=name)
    try:
        cfg, host = info["Config"], info["HostConfig"]
        if cfg["Image"] != image:
            raise HostFault("IMAGE_PROFILE")
        required = {
            "Memory": 192 * MIB,
            "MemorySwap": 192 * MIB,
            "PidsLimit": 16,
            "NanoCpus": 1_000_000_000,
            "ShmSize": MIB,
        }
        if any(type(host.get(k)) is not int or host[k] != v for k, v in required.items()):
            raise HostFault("LIMIT_CONFIGURATION")
        if host["ReadonlyRootfs"] is not True or host["Privileged"] is not False:
            raise HostFault("PRIVILEGE")
        if (
            host["NetworkMode"] != "none"
            or host["IpcMode"] != "private"
            or host["CgroupnsMode"] != "private"
            or host.get("PidMode", "") != ""
            or host.get("UTSMode", "") != ""
        ):
            raise HostFault("NAMESPACE")
        if host.get("Init") not in (None, False) or host["RestartPolicy"]["Name"] != "no":
            raise HostFault("PROCESS_CONFIGURATION")
        if host["LogConfig"]["Type"] != "none" or cfg["User"] != "65534:65534":
            raise HostFault("LOG_OR_USER")
        if host["CapDrop"] != ["ALL"] or host.get("CapAdd"):
            raise HostFault("CAPABILITIES")
        if host["SecurityOpt"] not in (["no-new-privileges"], ["no-new-privileges=true"]):
            raise HostFault("PRIVILEGE")
        if (
            host.get("Devices")
            or host.get("DeviceRequests")
            or host.get("PortBindings")
            or host.get("Binds")
        ):
            raise HostFault("EXTERNAL_ACCESS")
        limits = host["Ulimits"]
        actual = {item["Name"]: (item["Soft"], item["Hard"]) for item in limits}
        if len(actual) != len(limits) or actual != {"nofile": (64, 64), "core": (0, 0)}:
            raise HostFault("ULIMITS")
        mounts = info["Mounts"]
        if len(mounts) != 1 or mounts[0]["Type"] != "bind" or mounts[0]["RW"] is not False:
            raise HostFault("MOUNTS")
        if mounts[0]["Destination"] != "/probe.py" or mounts[0]["Source"].replace(
            "\\", "/"
        ).lower() not in translated_sources(source):
            raise HostFault("MOUNTS")
        if cfg["Entrypoint"] != ["python"] or cfg["Healthcheck"]["Test"] != ["NONE"]:
            raise HostFault("ENTRYPOINT")
        case = name.rsplit("-", 1)[-1]
        if case not in CASES or cfg["Cmd"] != ["-I", "-B", "/probe.py", "--case", case]:
            raise HostFault("COMMAND")
    except (KeyError, TypeError, AttributeError):
        raise HostFault("INSPECT_SCHEMA") from None


async def bounded(args, *, limit=MAX_METADATA, timeout=5):
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=environment(),
        limit=8192,
    )
    output = bytearray()
    exceeded = False

    def kill_cli():
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            except OSError:
                raise HostFault("CLI_CLEANUP") from None

    async def pump():
        nonlocal exceeded
        while block := await process.stdout.read(4096):
            if len(output) + len(block) > limit:
                exceeded = True
                kill_cli()
                continue  # drain without retaining more, to close the transport
            if not exceeded:
                output.extend(block)

    reader = asyncio.create_task(pump())
    work = asyncio.gather(process.wait(), reader)
    try:
        await asyncio.wait_for(asyncio.shield(work), timeout)
        if exceeded:
            raise HostFault("OUTPUT_LIMIT")
        return process.returncode, bytes(output)
    finally:
        try:
            kill_cli()
            await asyncio.wait_for(process.wait(), 5)
            await asyncio.wait_for(asyncio.shield(reader), 5)
        except Exception:
            raise HostFault("CLI_CLEANUP") from None
        finally:
            if work.done() and not work.cancelled():
                work.exception()  # consume any earlier pump failure after cleanup


class Watchdog:
    """Independent host thread; only exact already verified owned container IDs."""

    def __init__(self, docker, seconds):
        self.docker = docker
        self.seconds = seconds
        self.container_id = None
        self.done = threading.Event()
        self.fired = threading.Event()
        self.failed = False
        self.thread = threading.Thread(target=self.run, name="maskgw-as-watchdog", daemon=False)

    def run(self):
        if not self.done.wait(self.seconds):
            self.fired.set()
            container_id = self.container_id
            if container_id is not None:
                try:
                    subprocess.run(
                        [self.docker, "kill", "--signal", "KILL", container_id],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=environment(),
                        timeout=5,
                        check=False,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    self.failed = True

    def start(self):
        self.thread.start()

    def close(self):
        self.done.set()
        self.thread.join(timeout=7)
        if self.thread.is_alive() or self.failed:
            raise HostFault("WATCHDOG_CLEANUP")


class Observer:
    def __init__(self, docker, image, root):
        if not IMAGE_PATTERN.fullmatch(image):
            raise HostFault("IMAGE_NOT_PINNED")
        self.docker, self.image, self.root = docker, image, root
        self.task = "linux-as-" + uuid.uuid4().hex
        original = Path(__file__).with_name("linux_as_probe.py")
        self.original = original
        self.source_hash = digest(original)
        self.source = root / "linux_as_probe.py"
        shutil.copyfile(original, self.source)
        if digest(self.source) != self.source_hash:
            raise HostFault("SOURCE_CHANGED")
        self.observer_original = Path(__file__).resolve()
        self.observer_hash = digest(self.observer_original)
        shutil.copyfile(self.observer_original, root / self.observer_original.name)
        self.total_written = self.source.stat().st_size + self.observer_original.stat().st_size
        self.watchdog = Watchdog(docker, LOT_SECONDS)

    async def cli(self, *args, limit=MAX_METADATA, timeout=5):
        return await bounded([self.docker, *args], limit=limit, timeout=timeout)

    async def inspect(self, target):
        rc, data = await self.cli("inspect", target)
        if rc:
            raise HostFault("INSPECT")
        try:
            items = json.loads(data)
            if type(items) is not list or len(items) != 1:
                raise HostFault("INSPECT_SCHEMA")
            return items[0]
        except ValueError:
            raise HostFault("INSPECT_SCHEMA") from None

    def check(self, info, name):
        validate_inspect(
            info,
            image=self.image,
            task=self.task,
            source_hash=self.source_hash,
            source=self.source,
            name=name,
        )

    def save(self, name, value):
        data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
            "ascii"
        )
        if len(data) > MAX_REPORT or self.total_written + len(data) > MIB:
            raise HostFault("ARTIFACT_LIMIT")
        temporary = self.root / (name + ".tmp")
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.root / name)
        self.total_written += len(data)

    def identity(self, info, name, container_id=None):
        validate_identity(
            info, task=self.task, source_hash=self.source_hash, name=name, container_id=container_id
        )

    async def cleanup(self, container_id, name):
        info = await self.inspect(container_id)
        self.identity(info, name, container_id)
        if info["State"]["Running"]:
            await self.cli("kill", "--signal", "KILL", container_id)
            info = await self.inspect(container_id)
            self.identity(info, name, container_id)
        if info["State"]["Running"] or info["State"]["Pid"] != 0:
            raise HostFault("CONTAINER_STILL_LIVE")
        rc, _ = await self.cli("rm", container_id)
        if rc:
            raise HostFault("REMOVE_FAILED")
        rc, remaining = await self.cli("ps", "-aq", "--no-trunc", "--filter", "id=" + container_id)
        if rc or remaining.strip():
            raise HostFault("REMOVE_UNCONFIRMED")

    async def case(self, case):
        started = time.monotonic()
        name = "maskgw-as-" + self.task[-12:] + "-" + case
        container_id = None
        timer = Watchdog(self.docker, CASE_SECONDS)
        result = {"case": case, "outcome": "inconclusive", "cleanup_confirmed": False}
        timer.start()
        try:
            pending = {
                "task": self.task,
                "name": name,
                "id": None,
                "image": self.image,
                "source_sha256": self.source_hash,
                "phase": "before_create",
            }
            self.save("pending.json", pending)
            rc, raw_id = await self.cli(
                "create",
                "--name",
                name,
                "--label",
                "maskgw.task=" + self.task,
                "--label",
                "maskgw.source-sha256=" + self.source_hash,
                "--pull",
                "never",
                "--network",
                "none",
                "--ipc",
                "private",
                "--cgroupns",
                "private",
                "--read-only",
                "--user",
                "65534:65534",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "16",
                "--memory",
                str(192 * MIB),
                "--memory-swap",
                str(192 * MIB),
                "--cpus",
                "1",
                "--shm-size",
                str(MIB),
                "--ulimit",
                "core=0:0",
                "--ulimit",
                "nofile=64:64",
                "--log-driver",
                "none",
                "--restart",
                "no",
                "--no-healthcheck",
                "--mount",
                "type=bind,src=" + str(self.source) + ",dst=/probe.py,readonly",
                "--entrypoint",
                "python",
                self.image,
                "-I",
                "-B",
                "/probe.py",
                "--case",
                case,
            )
            if rc or not ID_PATTERN.fullmatch(raw_id.decode("ascii").strip()):
                raise HostFault("CREATE")
            container_id = raw_id.decode("ascii").strip()
            result["container_id"] = container_id
            pending.update(id=container_id, phase="created_before_inspect")
            self.save("pending.json", pending)
            self.check(await self.inspect(container_id), name)
            self.watchdog.container_id = timer.container_id = container_id
            remaining = CASE_SECONDS - (time.monotonic() - started)
            if remaining <= 0 or timer.fired.is_set() or self.watchdog.fired.is_set():
                raise HostFault("DEADLINE")
            rc, payload = await self.cli(
                "start", "--attach", container_id, limit=MAX_REPORT, timeout=remaining
            )
            info = await self.inspect(container_id)
            self.check(info, name)
            result["container_id"] = container_id
            result["exit_code"] = info["State"]["ExitCode"]
            result["oom_killed"] = info["State"]["OOMKilled"]
            if rc or info["State"]["Running"] or info["State"]["ExitCode"] != 0:
                raise HostFault("CONTAINER_EXIT")
            data = json.loads(payload, object_pairs_hook=unique_pairs)
            if type(data) is not dict or data.get("case") != case:
                raise HostFault("REPORT_SCHEMA")
            result["diagnostic"] = data
            if data.get("outcome") not in (
                "normal",
                "control_ok",
                "imposed",
                "fail",
                "inconclusive",
                "incompatible",
            ):
                raise HostFault("REPORT_SCHEMA")
            if data.get("total_memory_contained") is not False or info["State"]["OOMKilled"]:
                raise HostFault("REPORT_CLAIM")
            if data.get("cleanup_confirmed") is True and data.get("final_inventory") == [1]:
                result["outcome"] = data["outcome"]
            if timer.fired.is_set() or self.watchdog.fired.is_set():
                raise HostFault("DEADLINE")
        except Exception as error:
            result["host_failure"] = (
                error.category if isinstance(error, HostFault) else "COLLECTION"
            )
            result["outcome"] = "inconclusive"
        finally:
            host_clean = result.get("host_failure") != "CLI_CLEANUP"
            try:
                if timer.thread.ident is not None:
                    timer.close()
            except HostFault:
                host_clean = False
                result["host_failure"] = "WATCHDOG_CLEANUP"
            try:
                if container_id is None:
                    # A late daemon create cannot be ruled out just from a failed CLI.
                    host_clean = False
                    rc, listing = await self.cli(
                        "ps", "-aq", "--no-trunc", "--filter", "name=^/" + name + "$"
                    )
                    if rc:
                        raise HostFault("CREATION_UNCERTAIN")
                    if listing.strip():
                        container_id = listing.decode("ascii").strip()
                        self.identity(await self.inspect(container_id), name, container_id)
                        result["container_id"] = container_id
                        pending.update(id=container_id, phase="recovered_before_cleanup")
                        self.save("pending.json", pending)
                if container_id is not None:
                    await self.cleanup(container_id, name)
                    result["container_cleanup_confirmed"] = True
                    self.watchdog.container_id = None
                    pending.update(id=container_id, phase="removed")
                    self.save("pending.json", pending)
                result["cleanup_confirmed"] = host_clean and container_id is not None
            except Exception:
                result["cleanup_confirmed"] = False
                result["cleanup_failure"] = "COLLECTION"
            if not result["cleanup_confirmed"]:
                result["outcome"] = "inconclusive"
            result["elapsed_seconds"] = time.monotonic() - started
            if result["elapsed_seconds"] > CASE_SECONDS or timer.fired.is_set():
                result["outcome"] = "inconclusive"
                result["host_failure"] = "DEADLINE"
            self.save(case + ".json", result)
        return result

    async def run(self):
        report = {
            "image": self.image,
            "source_sha256": self.source_hash,
            "observer_sha256": self.observer_hash,
            "total_memory_contained": False,
            "cases": [],
            "complete": False,
        }
        self.watchdog.start()
        started = time.monotonic()
        try:
            rc, before = await self.cli("ps", "-aq", "--no-trunc")
            if rc:
                raise HostFault("ENGINE_UNAVAILABLE")
            image = await self.inspect(self.image)
            if (
                image.get("Os") != "linux"
                or image.get("Architecture") != "amd64"
                or image["Config"].get("Volumes")
            ):
                raise HostFault("IMAGE_PROFILE")
            for case in CASES:
                if self.watchdog.fired.is_set():
                    raise HostFault("LOT_DEADLINE")
                result = await self.case(case)
                report["cases"].append(result)
                if not result["cleanup_confirmed"]:
                    raise HostFault("CLEANUP_UNCONFIRMED")
                if case in ("baseline", "control") and result["outcome"] not in (
                    "normal",
                    "control_ok",
                ):
                    break
            rc, after = await self.cli("ps", "-aq", "--no-trunc")
            report["container_inventory_restored"] = rc == 0 and set(after.split()) == set(
                before.split()
            )
            report["complete"] = len(report["cases"]) == len(CASES)
        except Exception as error:
            report["host_failure"] = (
                error.category if isinstance(error, HostFault) else "COLLECTION"
            )
        finally:
            try:
                self.watchdog.close()
                report["watchdog_closed"] = True
            except HostFault:
                report["watchdog_closed"] = False
            report["elapsed_seconds"] = time.monotonic() - started
            report["deadline_exceeded"] = (
                self.watchdog.fired.is_set() or report["elapsed_seconds"] > LOT_SECONDS
            )
            report["not_executed"] = [
                case for case in CASES if case not in {item["case"] for item in report["cases"]}
            ]
            report["source_unchanged"] = (
                digest(self.source) == digest(self.original) == self.source_hash
            )
            report["observer_unchanged"] = (
                digest(self.root / Path(__file__).name)
                == digest(self.observer_original)
                == self.observer_hash
            )
            report["diagnostic_success"] = diagnostic_success(report)
            self.save("summary.json", report)
        print(
            json.dumps(
                {
                    "artifact_root": str(self.root),
                    "complete": report["complete"],
                    "diagnostic_success": report["diagnostic_success"],
                    "outcomes": [r["outcome"] for r in report["cases"]],
                    "total_memory_contained": False,
                },
                sort_keys=True,
            )
        )
        return report


def unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise HostFault("REPORT_SCHEMA")
        result[key] = value
    return result


def diagnostic_success(report):
    """Success is only this four-case mapping diagnostic, never total containment."""
    expected = ("normal", "control_ok", "imposed", "imposed")
    cases = report.get("cases", [])
    return (
        report.get("complete") is True
        and report.get("container_inventory_restored") is True
        and report.get("watchdog_closed") is True
        and report.get("deadline_exceeded") is False
        and report.get("source_unchanged") is True
        and report.get("observer_unchanged") is True
        and report.get("total_memory_contained") is False
        and "host_failure" not in report
        and len(cases) == len(CASES)
        and all(
            item.get("case") == case
            and item.get("outcome") == outcome
            and item.get("cleanup_confirmed") is True
            and "host_failure" not in item
            for item, case, outcome in zip(cases, CASES, expected, strict=True)
        )
    )


def main():
    if len(sys.argv) != 4 or sys.argv[1] != "--run":
        return 64
    docker, image = sys.argv[2:]
    if not Path(docker).is_file() or not IMAGE_PATTERN.fullmatch(image):
        return 64
    root = Path(tempfile.mkdtemp(prefix="maskgw-linux-as-20261020-"))
    try:
        observer = Observer(docker, image, root)
        report = asyncio.run(observer.run())
        return 0 if report["diagnostic_success"] else 2
    except Exception as error:
        print(
            json.dumps(
                {
                    "artifact_root": str(root),
                    "host_failure": (
                        error.category if isinstance(error, HostFault) else "COLLECTION"
                    ),
                    "diagnostic_success": False,
                    "total_memory_contained": False,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
