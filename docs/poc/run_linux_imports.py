"""Import-only lab observer; reuse frozen low-level lifecycle, never old cases."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path

MIB = 1024 * 1024
BASE = "python@sha256:8a00ecb83ed9d0864dfd102a1bdb2067fda907ceb30bb86d09da9ee558b19590"
FROZEN = {
    "linux_as_probe.py": "8170a37b892bd6d2bdae351bacd05f0e047d8bbc9b2b54bad695da7419380e0b",
    "run_linux_as_probe.py": "58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627",
}


def load(name):
    path = Path(__file__).with_name(name + ".py")
    if path.name in FROZEN and hashlib.sha256(path.read_bytes()).hexdigest() != FROZEN[path.name]:
        raise ValueError("FROZEN_SOURCE_CHANGED")
    spec = importlib.util.spec_from_file_location("lab_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OLD = load("run_linux_as_probe")
PREP = load("prepare_linux_imports")
PROTOCOL = load("linux_import_probe")


def validate_profile(info, *, image, task, source_hash, name, case, probe, installed, expected_env):
    OLD.validate_identity(info, task=task, source_hash=source_hash, name=name)
    try:
        cfg, host = info["Config"], info["HostConfig"]
        if cfg["Image"] != image or cfg["User"] != "65534:65534":
            raise OLD.HostFault("IMAGE_USER")
        if cfg.get("Env") != expected_env:
            raise OLD.HostFault("ENVIRONMENT")
        expected = {
            "Memory": 192 * MIB,
            "MemorySwap": 192 * MIB,
            "PidsLimit": 16,
            "NanoCpus": 1_000_000_000,
            "ShmSize": MIB,
        }
        if any(
            type(host.get(key)) is not int or host[key] != value for key, value in expected.items()
        ):
            raise OLD.HostFault("LIMIT_CONFIGURATION")
        if (
            host["ReadonlyRootfs"] is not True
            or host["Privileged"] is not False
            or host["CapDrop"] != ["ALL"]
            or host.get("CapAdd")
            or host["SecurityOpt"] not in (["no-new-privileges"], ["no-new-privileges=true"])
        ):
            raise OLD.HostFault("PRIVILEGE")
        if (
            host["NetworkMode"] != "none"
            or host["IpcMode"] != "private"
            or host["CgroupnsMode"] != "private"
            or host.get("PidMode", "") != ""
            or host.get("UTSMode", "") != ""
        ):
            raise OLD.HostFault("NAMESPACE")
        if (
            host.get("Init") not in (False, None)
            or host["RestartPolicy"]["Name"] != "no"
            or host["LogConfig"]["Type"] != "none"
            or host.get("Devices")
            or host.get("DeviceRequests")
            or host.get("Binds")
            or host.get("PortBindings")
        ):
            raise OLD.HostFault("EXTERNAL_ACCESS")
        limits = host["Ulimits"]
        if len(limits) != 2 or {x["Name"]: (x["Soft"], x["Hard"]) for x in limits} != {
            "core": (0, 0),
            "nofile": (64, 64),
        }:
            raise OLD.HostFault("ULIMITS")
        mounts = info["Mounts"]
        expected_mounts = {"/probe": probe, "/installed": installed}
        if len(mounts) != 2 or {x["Destination"] for x in mounts} != expected_mounts.keys():
            raise OLD.HostFault("MOUNTS")
        for item in mounts:
            if (
                item["Type"] != "bind"
                or item["RW"] is not False
                or item["Source"].replace("\\", "/").lower()
                not in OLD.translated_sources(expected_mounts[item["Destination"]])
            ):
                raise OLD.HostFault("MOUNTS")
        if (
            cfg["Entrypoint"] != ["python"]
            or cfg["Healthcheck"]["Test"] != ["NONE"]
            or case not in ("control", "limited")
            or cfg["Cmd"] != ["-I", "-B", "-S", "/probe/linux_import_probe.py", "--case", case]
        ):
            raise OLD.HostFault("COMMAND")
    except (KeyError, TypeError, AttributeError):
        raise OLD.HostFault("INSPECT_SCHEMA") from None


def classify_limited(control, limited):
    if any(
        item.get("diagnostic_failure")
        or item.get("audit_error")
        or item.get("check_error")
        or item.get("member_wait")
        or "batch" in item
        for item in (control, limited)
    ):
        return "inconclusive"
    if control.get("outcome") != "normal" or control.get("cleanup_confirmed") is not True:
        return "inconclusive"
    if [
        event.get("stage") for event in control.get("events", []) if event.get("phase") == "end"
    ] != [0, 1, 2]:
        return "inconclusive"
    if limited.get("cleanup_confirmed") is not True or limited.get("outer_pressure"):
        return "inconclusive"
    if limited.get("outcome") == "normal":
        ends = [event for event in limited["events"] if event["phase"] == "end"]
        if (
            [event.get("stage") for event in ends] == [0, 1, 2]
            and all(x["vm"]["peak"] <= 32 * MIB for x in ends)
            and {
                tuple(row)
                for _stage, row in PROTOCOL.unpack_inventory(limited.get("module_inventory"))
            }
            == {
                tuple(row)
                for _stage, row in PROTOCOL.unpack_inventory(control.get("module_inventory"))
            }
        ):
            return "fits_as32"
        return "inconclusive"
    if limited.get("outcome") == "incompatible":
        return "incompatible"
    if limited.get("failure") in ("MEMORY", "IMPORT", "SIGNAL") and limited.get(
        "failure_stage"
    ) in (0, 1, 2):
        return "did_not_fit"  # observed mismatch, NOT proof that AS caused the failure
    return "inconclusive"


class Observer(OLD.Observer):
    """Only cli/inspect/save/identity/cleanup inherited; own init/case/run/profile."""

    def __init__(self, docker, image, root, prepared_root):
        if image != BASE:
            raise OLD.HostFault("IMAGE_NOT_PINNED")
        self.docker, self.image, self.root = docker, image, root
        self.preflight_passed = False
        self.task = "linux-imports-" + uuid.uuid4().hex
        self.prepared_root = prepared_root
        PREP.check_placement(prepared_root, Path(__file__).resolve().parents[2])
        if json.loads((prepared_root / "owner.json").read_bytes()) != {
            "kind": "maskgw-linux-imports",
            "root": str(prepared_root),
        }:
            raise OLD.HostFault("PREPARATION_OWNER")
        self.prepared = json.loads((prepared_root / "prepared.json").read_bytes())
        self.installed = prepared_root / "installed"
        self.inventory = PREP.verify_tree(self.installed, set(self.prepared["launchers_allowlist"]))
        if self.inventory != json.loads((prepared_root / "tree.json").read_bytes()):
            raise OLD.HostFault("INSTALLED_TREE_CHANGED")
        self.probe = root / "probe"
        self.probe.mkdir()
        self.source_hash = OLD.digest(Path(__file__).with_name("linux_import_probe.py"))
        self.originals = {}
        for filename in (
            "linux_as_probe.py",
            "linux_import_probe.py",
            "run_linux_as_probe.py",
            "prepare_linux_imports.py",
            "run_linux_imports.py",
        ):
            original = Path(__file__).with_name(filename)
            self.originals[filename] = OLD.digest(original)
            if filename in FROZEN and self.originals[filename] != FROZEN[filename]:
                raise OLD.HostFault("FROZEN_SOURCE_CHANGED")
            if filename in ("linux_as_probe.py", "linux_import_probe.py"):
                shutil.copyfile(original, self.probe / filename)
            else:
                shutil.copyfile(original, root / filename)
        owners = {}
        for item in self.prepared["details"]:
            for member in item["members"]:
                top = member.split("/")[0]
                if top in owners and owners[top] != item["name"]:
                    raise OLD.HostFault("OWNER_COLLISION")
                owners[top] = item["name"]
        generated = {}
        # Closed names found in the already-hashed native files, not a wildcard
        # permission for arbitrary fileless modules. Runtime must also have the
        # corresponding exact extension path loaded.
        for relative, _size, _sha in self.inventory["files"]:
            if relative.endswith(".so"):
                names = set()
                tail = b""
                with (self.installed / relative).open("rb") as native:
                    while block := native.read(65536):
                        data = tail + block
                        names.update(
                            match.decode("ascii")
                            for match in re.findall(
                                rb"\b(?:cython_runtime|_cython_[0-9]+_[0-9]+_[0-9]+)\b", data
                            )
                        )
                        tail = data[-64:]
                for name in sorted(names):
                    generated.setdefault(name, []).append(relative)
        self.total_written = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
        self.save(
            "probe/runtime.json", {"owners": owners, "versions": PREP.PINS, "generated": generated}
        )
        self.runtime_hash = OLD.digest(self.probe / "runtime.json")
        self.watchdog = OLD.Watchdog(docker, 120)
        self.expected_env = None

    def check(self, info, name, case):
        validate_profile(
            info,
            image=self.image,
            task=self.task,
            source_hash=self.source_hash,
            name=name,
            case=case,
            probe=self.probe,
            installed=self.installed,
            expected_env=self.expected_env,
        )

    async def readiness(self, evidence):
        deadline = time.monotonic() + 20
        for attempt in range(1, 4):
            if self.watchdog.fired.is_set():
                raise OLD.HostFault("PREFLIGHT_INVALID")
            if deadline - time.monotonic() < 5:
                break
            evidence["attempt_count"] = attempt
            try:
                rc, raw = await self.cli(
                    "version", "--format", "{{json .}}", limit=16384, timeout=5
                )
            except TimeoutError:
                outcome = (
                    "TIMEOUT"  # bounded's finally succeeded, otherwise CLI_CLEANUP replaces it.
                )
            else:
                if rc:
                    outcome = "NONZERO"
                else:
                    data = json.loads(raw, object_pairs_hook=OLD.unique_pairs)
                    if type(data) is not dict or type(data.get("Server")) is not dict:
                        raise OLD.HostFault("PREFLIGHT_INVALID")
                    server = data["Server"]
                    version = server.get("Version")
                    if (
                        server.get("Os") != "linux"
                        or server.get("Arch") != "amd64"
                        or type(version) is not str
                        or not 1 <= len(version) <= 64
                        or re.fullmatch(r"[A-Za-z0-9._+-]{1,64}", version) is None
                    ):
                        raise OLD.HostFault("PREFLIGHT_INVALID")
                    if time.monotonic() > deadline:
                        evidence["attempts"].append({"attempt": attempt, "outcome": "LATE"})
                        raise OLD.HostFault("PREFLIGHT_NOT_READY")
                    evidence["attempts"].append({"attempt": attempt, "outcome": "READY"})
                    return {key: server[key] for key in ("Version", "Os", "Arch")}
            evidence["attempts"].append({"attempt": attempt, "outcome": outcome})
            if attempt < 3 and deadline - time.monotonic() >= 6:
                await asyncio.sleep(1)
            else:
                break
        raise OLD.HostFault("PREFLIGHT_NOT_READY")

    async def preflight(self, evidence):
        self.preflight_passed = False
        try:
            evidence["stage"] = "READINESS"
            evidence["engine"] = await self.readiness(evidence)
            evidence["stage"] = "INVENTORY"
            rc, listing = await self.cli("ps", "-aq", "--no-trunc")
            if rc or listing.strip():
                raise OLD.HostFault("PREFLIGHT_INVALID")
            evidence["stage"] = "IMAGE"
            image = await self.inspect(self.image)
            if (
                image.get("Os") != "linux"
                or image.get("Architecture") != "amd64"
                or image["Config"].get("Volumes")
            ):
                raise OLD.HostFault("PREFLIGHT_INVALID")
            self.expected_env = image["Config"].get("Env")
            if type(self.expected_env) is not list:
                raise OLD.HostFault("PREFLIGHT_INVALID")
            if self.watchdog.fired.is_set():
                raise OLD.HostFault("PREFLIGHT_INVALID")
            evidence["stage"], evidence["passed"] = "READY", True
            self.preflight_passed = True
        except OLD.HostFault as error:
            if error.category == "CLI_CLEANUP":
                evidence["cli_cleanup_confirmed"] = False
            if error.category == "PREFLIGHT_NOT_READY":
                raise OLD.HostFault("PREFLIGHT_NOT_READY") from None
            raise OLD.HostFault("PREFLIGHT_INVALID") from None
        except Exception:
            raise OLD.HostFault("PREFLIGHT_INVALID") from None

    async def case(self, case):
        if getattr(self, "preflight_passed", False) is not True:
            raise OLD.HostFault("PREFLIGHT_REQUIRED")
        started = time.monotonic()
        name = "maskgw-imports-" + self.task[-12:] + "-" + case
        timer = OLD.Watchdog(self.docker, 30)
        container_id = None
        result = {"case": case, "outcome": "inconclusive", "cleanup_confirmed": False}
        pending = {"task": self.task, "name": name, "id": None, "phase": "before_create"}
        timer.start()
        try:
            self.save("pending.json", pending)
            args = [
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
                f"type=bind,src={self.probe},dst=/probe,readonly",
                "--mount",
                f"type=bind,src={self.installed},dst=/installed,readonly",
                "--entrypoint",
                "python",
                self.image,
                "-I",
                "-B",
                "-S",
                "/probe/linux_import_probe.py",
                "--case",
                case,
            ]
            rc, raw = await self.cli(*args)
            if rc or not OLD.ID_PATTERN.fullmatch(raw.decode("ascii").strip()):
                raise OLD.HostFault("CREATE")
            container_id = raw.decode("ascii").strip()
            result["container_id"] = container_id
            pending.update(id=container_id, phase="created_before_inspect")
            self.save("pending.json", pending)
            self.check(await self.inspect(container_id), name, case)
            timer.container_id = self.watchdog.container_id = container_id
            remaining = 30 - (time.monotonic() - started)
            if remaining <= 0 or timer.fired.is_set() or self.watchdog.fired.is_set():
                raise OLD.HostFault("DEADLINE")
            rc, data = await self.cli(
                "start", "--attach", container_id, limit=65536, timeout=remaining
            )
            if len(data) > PROTOCOL.MAX_PROBE + 1:
                raise OLD.HostFault("REPORT_LIMIT")
            info = await self.inspect(container_id)
            self.check(info, name, case)
            state = info["State"]
            result["exit_code"], result["oom_killed"] = state["ExitCode"], state["OOMKilled"]
            if rc or state["Running"] or state["ExitCode"] != 0 or state["OOMKilled"]:
                raise OLD.HostFault("CONTAINER_EXIT")
            report = json.loads(data, object_pairs_hook=OLD.unique_pairs)
            if (
                type(report) is not dict
                or report.get("case") != case
                or report.get("total_memory_contained") is not False
                or report.get("outcome") not in ("normal", "inconclusive", "incompatible")
            ):
                raise OLD.HostFault("REPORT_SCHEMA")
            result["diagnostic"] = report
            if report.get("cleanup_confirmed") is True and report.get("final_inventory") == [1]:
                result["outcome"] = report["outcome"]
        except Exception as error:
            result["host_failure"] = (
                error.category if isinstance(error, OLD.HostFault) else "COLLECTION"
            )
        finally:
            host_clean = result.get("host_failure") != "CLI_CLEANUP"
            try:
                timer.close()
            except Exception:
                host_clean = False
            try:
                if container_id is None:
                    host_clean = False
                    rc, listing = await self.cli(
                        "ps", "-aq", "--no-trunc", "--filter", "name=^/" + name + "$"
                    )
                    if rc:
                        raise OLD.HostFault("CREATION_UNCERTAIN")
                    if listing.strip():
                        container_id = listing.decode("ascii").strip()
                        self.identity(await self.inspect(container_id), name, container_id)
                        result["container_id"] = container_id
                        pending.update(id=container_id, phase="recovered_before_cleanup")
                        self.save("pending.json", pending)
                if container_id is not None:
                    await self.cleanup(container_id, name)
                    pending.update(id=container_id, phase="removed")
                    self.save("pending.json", pending)
                    self.watchdog.container_id = None
                    result["container_cleanup_confirmed"] = True
                result["cleanup_confirmed"] = host_clean and container_id is not None
            except Exception:
                result["cleanup_confirmed"] = False
            result["elapsed_seconds"] = time.monotonic() - started
            if (
                not result["cleanup_confirmed"]
                or timer.fired.is_set()
                or result["elapsed_seconds"] > 30
                or self.watchdog.fired.is_set()
            ):
                result["outcome"] = "inconclusive"
                result["host_failure"] = result.get("host_failure", "DEADLINE_OR_CLEANUP")
            self.save(case + ".json", result)
        return result

    async def run(self, *, diagnostic_only=False):
        self.preflight_passed = False
        report = {
            "image": self.image,
            "source_hashes": self.originals,
            "cases": [],
            "total_memory_contained": False,
            "complete": False,
            "imports_fit_as32": False,
            "diagnostic_only": diagnostic_only,
            "preflight": {
                "passed": False,
                "attempts": [],
                "attempt_count": 0,
                "cli_cleanup_confirmed": True,
            },
        }
        started = time.monotonic()
        self.watchdog.start()
        try:
            await self.preflight(report["preflight"])
            control = None
            for case in ("control",) if diagnostic_only else ("control", "limited"):
                if self.watchdog.fired.is_set():
                    raise OLD.HostFault("LOT_DEADLINE")
                result = await self.case(case)
                report["cases"].append(
                    {
                        "case": case,
                        "outcome": result["outcome"],
                        "cleanup_confirmed": result["cleanup_confirmed"],
                        "report_sha256": OLD.digest(self.root / (case + ".json")),
                    }
                )
                if not result["cleanup_confirmed"]:
                    raise OLD.HostFault("CLEANUP_UNCONFIRMED")
                if case == "control":
                    control = result.get("diagnostic")
                    if (
                        result.get("host_failure")
                        or result["outcome"] != "normal"
                        or "batch" in (control or {})
                    ):
                        break
                elif not result.get("host_failure"):
                    report["limited_classification"] = classify_limited(
                        control, result.get("diagnostic", {})
                    )
                    report["imports_fit_as32"] = report["limited_classification"] == "fits_as32"
            rc, listing = await self.cli("ps", "-aq", "--no-trunc")
            report["inventory_restored"] = rc == 0 and not listing.strip()
            report["complete"] = len(report["cases"]) == 2
        except Exception as error:
            report["host_failure"] = (
                error.category if isinstance(error, OLD.HostFault) else "COLLECTION"
            )
        finally:
            self.preflight_passed = False
            try:
                self.watchdog.close()
                report["watchdog_closed"] = True
            except Exception:
                report["watchdog_closed"] = False
            report["elapsed_seconds"] = time.monotonic() - started
            report["deadline_exceeded"] = (
                self.watchdog.fired.is_set() or report["elapsed_seconds"] > 120
            )
            report["sources_unchanged"] = all(
                OLD.digest(Path(__file__).with_name(name)) == value
                and OLD.digest(
                    (
                        self.probe
                        if name in ("linux_as_probe.py", "linux_import_probe.py")
                        else self.root
                    )
                    / name
                )
                == value
                for name, value in self.originals.items()
            )
            report["tree_unchanged"] = (
                PREP.verify_tree(self.installed, set(self.prepared["launchers_allowlist"]))
                == self.inventory
            )
            report["runtime_manifest_unchanged"] = (
                OLD.digest(self.probe / "runtime.json") == self.runtime_hash
            )
            if (
                not report["sources_unchanged"]
                or not report["tree_unchanged"]
                or not report["runtime_manifest_unchanged"]
                or not report["watchdog_closed"]
                or report["deadline_exceeded"]
                or not report.get("inventory_restored")
                or report.get("host_failure")
            ):
                report["imports_fit_as32"] = False
            self.save("summary.json", report)
        print(
            json.dumps(
                {
                    "artifact_root": str(self.root),
                    "complete": report["complete"],
                    "limited_classification": report.get("limited_classification"),
                    "imports_fit_as32": report["imports_fit_as32"],
                    "total_memory_contained": False,
                }
            )
        )
        return report


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ("--run", "--diagnose"):
        return 64
    if not Path(sys.argv[2]).is_file():
        return 64
    root = Path(tempfile.mkdtemp(prefix="maskgw-linux-import-run-20261021-"))
    try:
        observer = Observer(sys.argv[2], BASE, root, Path(sys.argv[3]).resolve())
        result = asyncio.run(observer.run(diagnostic_only=sys.argv[1] == "--diagnose"))
        return 0 if result["imports_fit_as32"] else 2
    except Exception:
        print(json.dumps({"artifact_root": str(root), "outcome": "inconclusive"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
