"""Loaded-AS lab observer. No CLI, threads or workload on import.

Requires separate review of the real procedure/command before any invocation.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "loaded_imports_host", Path(__file__).with_name("run_linux_imports.py")
)
IMPORTS = importlib.util.module_from_spec(spec)
spec.loader.exec_module(IMPORTS)
OLD, PREP, PROBE = IMPORTS.OLD, IMPORTS.PREP, IMPORTS.PROTOCOL
CORE = IMPORTS.load("loaded_memory_protocol")
SUPERVISOR = IMPORTS.load("linux_loaded_probe")
BASE, MIB = IMPORTS.BASE, 1024 * 1024
CASES, OUTCOMES = ("control", "private", "shared"), ("control_ok", "imposed", "imposed")
PROBES = {
    "linux_as_probe.py",
    "linux_import_probe.py",
    "loaded_memory_protocol.py",
    "loaded_memory_member.py",
    "loaded_memory_collect.py",
    "linux_loaded_probe.py",
}
STAGES = {"setup", "ready", "imports", "loaded", "pressure", "held", "release", "finish", "exit"}


def validate_profile(
    info, *, image, task, source_hash, name, case, expected, probe, installed, expected_env
):
    OLD.validate_identity(info, task=task, source_hash=source_hash, name=name)
    CORE.parse_case_args(["--case", case, "--expected", expected])
    try:
        cfg, host = info["Config"], info["HostConfig"]
        if (
            cfg["Image"] != image
            or cfg["User"] != "65534:65534"
            or cfg.get("Env") != expected_env
            or cfg["Entrypoint"] != ["python"]
            or cfg["Healthcheck"]["Test"] != ["NONE"]
            or cfg["Cmd"]
            != [
                "-I",
                "-B",
                "-S",
                "/probe/linux_loaded_probe.py",
                "--case",
                case,
                "--expected",
                expected,
            ]
        ):
            raise OLD.HostFault("COMMAND_OR_IMAGE")
        limits = {
            "Memory": 192 * MIB,
            "MemorySwap": 192 * MIB,
            "PidsLimit": 16,
            "NanoCpus": 1_000_000_000,
            "ShmSize": MIB,
        }
        if any(
            type(host.get(key)) is not int or host[key] != value for key, value in limits.items()
        ):
            raise OLD.HostFault("LIMIT_CONFIGURATION")
        if (
            host["ReadonlyRootfs"] is not True
            or host["Privileged"] is not False
            or host["CapDrop"] != ["ALL"]
            or host.get("CapAdd")
            or host["SecurityOpt"] not in (["no-new-privileges"], ["no-new-privileges=true"])
            or host["NetworkMode"] != "none"
            or host["IpcMode"] != "private"
            or host["CgroupnsMode"] != "private"
            or host.get("PidMode", "") != ""
            or host.get("UTSMode", "") != ""
            or host.get("Init") is not None
            and host["Init"] is not False
            or host["RestartPolicy"]["Name"] != "no"
            or host["LogConfig"]["Type"] != "none"
            or any(host.get(key) for key in ("Devices", "DeviceRequests", "Binds", "PortBindings"))
        ):
            raise OLD.HostFault("PRIVILEGE_OR_ACCESS")
        ulimits = host["Ulimits"]
        if (
            type(ulimits) is not list
            or len(ulimits) != 2
            or any(
                type(item["Soft"]) is not int or type(item["Hard"]) is not int for item in ulimits
            )
            or {item["Name"]: (item["Soft"], item["Hard"]) for item in ulimits}
            != {"core": (0, 0), "nofile": (64, 64)}
        ):
            raise OLD.HostFault("ULIMITS")
        mounts = info["Mounts"]
        paths = {"/probe": probe, "/installed": installed}
        if (
            type(mounts) is not list
            or len(mounts) != 2
            or {item["Destination"] for item in mounts} != set(paths)
        ):
            raise OLD.HostFault("MOUNTS")
        for item in mounts:
            if (
                item["Type"] != "bind"
                or item["RW"] is not False
                or item["Source"].replace("\\", "/").lower()
                not in OLD.translated_sources(paths[item["Destination"]])
            ):
                raise OLD.HostFault("MOUNTS")
        return True
    except (KeyError, TypeError, AttributeError, ValueError):
        pass
    raise OLD.HostFault("INSPECT_SCHEMA")


def no_constant(_value):
    raise OLD.HostFault("REPORT_SCHEMA")


def decode_report(raw):
    if type(raw) is not bytes or not raw:
        raise OLD.HostFault("REPORT_MISSING")
    if len(raw) > 65536:
        raise OLD.HostFault("OUTPUT_LIMIT")
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise OLD.HostFault("REPORT_SCHEMA")
    try:
        result = json.loads(
            raw.decode("ascii"), object_pairs_hook=OLD.unique_pairs, parse_constant=no_constant
        )
        if type(result) is dict:
            return result
    except BaseException:
        pass
    raise OLD.HostFault("REPORT_SCHEMA")


def integer(value, minimum=0):
    if type(value) is not int or not minimum <= value <= 1 << 50:
        raise OLD.HostFault("REPORT_SCHEMA")
    return value


def ids(value):
    if type(value) is not list or not 1 <= len(value) <= 16:
        raise OLD.HostFault("REPORT_SCHEMA")
    for item in value:
        integer(item, 1)
    if value != sorted(set(value)):
        raise OLD.HostFault("REPORT_SCHEMA")
    return value


def cgroup(value, previous, *, positive, expected_ids=None):
    if type(value) is not dict or set(value) != {
        "current",
        "peak",
        "events",
        "stat",
        "procs",
        "pids_current",
    }:
        raise OLD.HostFault("REPORT_SCHEMA")
    for key in ("current", "peak", "pids_current"):
        integer(value[key])
    if (
        type(value["events"]) is not dict
        or set(value["events"]) != {"max", "oom", "oom_kill"}
        or type(value["stat"]) is not dict
        or set(value["stat"]) != {"anon", "file", "shmem", "kernel", "sock"}
    ):
        raise OLD.HostFault("REPORT_SCHEMA")
    for number in [*value["events"].values(), *value["stat"].values()]:
        integer(number)
    actual = ids(value["procs"])
    if positive:
        if (
            actual != expected_ids
            or value["pids_current"] != len(actual)
            or not value["current"] <= value["peak"] <= 192 * MIB
            or previous is not None
            and (value["peak"] < previous["peak"] or value["events"] != previous["events"])
        ):
            raise OLD.HostFault("REPORT_CGROUP")
    return value


def validate_report(report, case, expected):
    strong = (
        type(report) is dict
        and type(report.get("outcome")) is str
        and report["outcome"] in ("fail", "incompatible")
    )
    try:
        return _validate_report(report, case, expected)
    except OLD.HostFault as error:
        category = error.category
    except BaseException:
        category = "REPORT_SCHEMA"
    raise OLD.HostFault("REPORT_LIFECYCLE" if strong else category)


def _validate_report(report, case, expected):
    CORE.parse_case_args(["--case", case, "--expected", expected])
    if type(report) is not dict:
        raise OLD.HostFault("REPORT_SCHEMA")
    fallback = {
        "profile": "loaded-as128",
        "outcome": "inconclusive",
        "report_limit": True,
        "total_memory_contained": False,
    }
    if set(report) == set(fallback) and report == fallback:
        if report["report_limit"] is True and report["total_memory_contained"] is False:
            raise OLD.HostFault("REPORT_LIMIT")
        raise OLD.HostFault("REPORT_SCHEMA")
    base = {
        "profile",
        "case",
        "outcome",
        "total_memory_contained",
        "observations",
        "cleanup_confirmed",
    }
    optional = {
        "startup",
        "module_inventory",
        "member_returncode",
        "final_inventory",
        "final_cgroup",
    }
    positive = report.get("outcome") in OUTCOMES
    strong = report.get("outcome") in ("fail", "incompatible")
    checked = positive or strong
    expected_keys = base | optional | ({"inventory_digest"} if case == "control" else set())
    if positive:
        if set(report) != expected_keys or report["outcome"] != (
            "control_ok" if case == "control" else "imposed"
        ):
            raise OLD.HostFault("REPORT_SCHEMA")
    elif (
        not base | {"failure"} <= set(report)
        or not set(report) <= base | optional | {"failure"}
        or report["outcome"] not in ("fail", "inconclusive", "incompatible")
    ):
        raise OLD.HostFault("REPORT_SCHEMA")
    if (
        report["profile"] != "loaded-as128"
        or report["case"] != case
        or report["total_memory_contained"] is not False
        or type(report["cleanup_confirmed"]) is not bool
    ):
        raise OLD.HostFault("REPORT_SCHEMA")
    if not positive:
        failure = report["failure"]
        if (
            type(failure) is not dict
            or set(failure) != {"stage", "category"}
            or failure["stage"] not in STAGES
            or failure["category"] not in SUPERVISOR.CATEGORIES
        ):
            raise OLD.HostFault("REPORT_SCHEMA")
    if "member_returncode" in report and report["member_returncode"] is not None:
        rc = report["member_returncode"]
        if type(rc) is not int or not -255 <= rc <= 255:
            raise OLD.HostFault("REPORT_SCHEMA")
    if "final_inventory" in report:
        ids(report["final_inventory"])
    if strong and (
        case == "control"
        or not {"startup", "member_returncode", "final_inventory", "final_cgroup"} <= set(report)
        or report["cleanup_confirmed"] is not True
        or report["final_inventory"] != [1]
    ):
        raise OLD.HostFault("REPORT_LIFECYCLE")
    if positive and (
        report["cleanup_confirmed"] is not True
        or type(report["member_returncode"]) is not int
        or report["member_returncode"] != 0
        or report["final_inventory"] != [1]
    ):
        raise OLD.HostFault("REPORT_LIFECYCLE")
    limits = [-1, -1] if case == "control" else [128 * MIB] * 2
    previous = None
    if "startup" in report:
        start = report["startup"]
        if type(start) is not dict or set(start) != {
            "startup_vm",
            "startup_cgroup",
            "inherited_as",
            "supervisor_as",
        }:
            raise OLD.HostFault("REPORT_SCHEMA")
        CORE.facts(start["startup_vm"], start["inherited_as"])
        CORE.facts(start["startup_vm"], start["supervisor_as"])
        if checked and start["supervisor_as"] != limits:
            raise OLD.HostFault("REPORT_SCHEMA")
        previous = cgroup(start["startup_cgroup"], None, positive=checked, expected_ids=[1])
    observations = report["observations"]
    if type(observations) is not list or len(observations) > 24:
        raise OLD.HostFault("REPORT_SCHEMA")
    if positive and (
        len(observations) != 9 if case != "control" else not 12 <= len(observations) <= 16
    ):
        raise OLD.HostFault("REPORT_SCHEMA")
    fd_set, member_ids, peak = None, None, 0
    for index, item in enumerate(observations):
        if type(item) is not dict or set(item) != {
            "vm",
            "limits",
            "ppid",
            "fds",
            "inventory",
            "cgroup",
        }:
            raise OLD.HostFault("REPORT_SCHEMA")
        CORE.facts(item["vm"], item["limits"])
        inv = ids(item["inventory"])
        if checked and (
            len(inv) != 2
            or inv[0] != 1
            or type(item["ppid"]) is not int
            or item["ppid"] != 1
            or item["limits"] != limits
            or item["vm"]["peak"] < peak
            or positive
            and case != "control"
            and item["vm"]["peak"] > 128 * MIB
        ):
            raise OLD.HostFault("REPORT_SCHEMA")
        member_ids = member_ids or inv
        if checked and inv != member_ids:
            raise OLD.HostFault("REPORT_SCHEMA")
        peak = item["vm"]["peak"]
        if item["fds"] is not None:
            if (
                type(item["fds"]) is not dict
                or set(item["fds"]) != {"fds", "proc_children_available"}
                or type(item["fds"]["proc_children_available"]) is not bool
            ):
                raise OLD.HostFault("REPORT_SCHEMA")
            descriptors = item["fds"]["fds"]
            if (
                type(descriptors) is not list
                or len(descriptors) != 4
                or any(type(fd) is not int or not 0 <= fd <= 63 for fd in descriptors)
                or descriptors[:3] != [0, 1, 2]
                or descriptors[3] < 3
            ):
                raise OLD.HostFault("REPORT_SCHEMA")
            if checked and fd_set is not None and item["fds"] != fd_set:
                raise OLD.HostFault("REPORT_SCHEMA")
            fd_set = item["fds"]
        if positive and ((item["fds"] is None) != (index in (1, 2, 3))):
            raise OLD.HostFault("REPORT_SCHEMA")
        previous = cgroup(item["cgroup"], previous, positive=checked, expected_ids=inv)
    if "final_cgroup" in report:
        cgroup(report["final_cgroup"], previous, positive=checked, expected_ids=[1])
    if strong:
        validate_strong(report)
    calculated = None
    if "module_inventory" in report:
        rows = PROBE.unpack_inventory(report["module_inventory"])
        calculated = CORE.inventory_digest(rows, PROBE.validate_inventory)
    if positive:
        wanted = report["inventory_digest"] if case == "control" else expected
        if not CORE.valid_digest(wanted) or wanted != calculated:
            raise OLD.HostFault("REPORT_DIGEST")
    return calculated


def validate_strong(report):
    """Strong negative evidence needs lifecycle and an actual witness, not a marker."""
    failure, rc, observations = (
        report["failure"],
        report["member_returncode"],
        report["observations"],
    )
    if not observations:
        raise OLD.HostFault("REPORT_LIFECYCLE")
    if report["outcome"] == "incompatible":
        wanted = {"MEMORY": 72, "IMPORT": 73}.get(failure["category"])
        if failure["stage"] != "imports" or wanted is None or type(rc) is not int or rc != wanted:
            raise OLD.HostFault("REPORT_LIFECYCLE")
    else:
        if (
            failure["category"] != "OBSERVED_FAIL"
            or type(rc) is not int
            or not (rc == -9 or 0 <= rc <= 255)
        ):
            raise OLD.HostFault("REPORT_LIFECYCLE")
        # The last observation is the supervisor's pre-kill confirmation.
        # Limited cases have one allocator: index5 is the pre-pressure reading,
        # never the much smaller pre-import ready baseline (index0).
        observed = observations[-1]["vm"]
        witness = observed["peak"] > 128 * MIB
        if failure["stage"] == "held" and len(observations) >= 7:
            witness = witness or observed["size"] >= observations[5]["vm"]["size"] + 40 * MIB
        if not witness:
            raise OLD.HostFault("REPORT_LIFECYCLE")


class Observer:
    """No legacy case/run/check in MRO; only explicitly selected operations reused."""

    cli, inspect, save = OLD.Observer.cli, OLD.Observer.inspect, OLD.Observer.save
    identity, cleanup = OLD.Observer.identity, OLD.Observer.cleanup
    readiness, preflight = IMPORTS.Observer.readiness, IMPORTS.Observer.preflight

    def __init__(self, docker, root, prepared_root):
        IMPORTS.Observer.__init__(self, docker, BASE, root, prepared_root)
        self.task = "loaded-as128-" + uuid.uuid4().hex
        for filename in (
            "loaded_memory_protocol.py",
            "loaded_memory_member.py",
            "loaded_memory_collect.py",
            "linux_loaded_probe.py",
            "run_linux_loaded.py",
        ):
            original = Path(__file__).with_name(filename)
            sha = OLD.digest(original)
            self.originals[filename] = sha
            IMPORTS.shutil.copyfile(
                original, (self.probe if filename in PROBES else root) / filename
            )
            self.total_written += original.stat().st_size
        self.source_hash = hashlib.sha256(
            json.dumps(
                self.originals, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode("ascii")
        ).hexdigest()
        self.watchdog = OLD.Watchdog(docker, 120)
        self.raw_hashes, self.used_cases, self.grant = {}, set(), None
        self.running = self.started = False
        self.save(
            "owner.json",
            {
                "kind": "loaded-as128",
                "root": str(root),
                "task": self.task,
                "bundle_sha256": self.source_hash,
            },
        )

    def check(self, info, name, case, expected):
        return validate_profile(
            info,
            image=self.image,
            task=self.task,
            source_hash=self.source_hash,
            name=name,
            case=case,
            expected=expected,
            probe=self.probe,
            installed=self.installed,
            expected_env=self.expected_env,
        )

    def integrity(self):
        sources = all(
            OLD.digest(Path(__file__).with_name(name)) == value
            and OLD.digest((self.probe if name in PROBES else self.root) / name) == value
            for name, value in self.originals.items()
        )
        runtime = OLD.digest(self.probe / "runtime.json") == self.runtime_hash
        tree = (
            PREP.verify_tree(self.installed, set(self.prepared["launchers_allowlist"]))
            == self.inventory
        )
        raw = all(
            OLD.digest(self.root / item["file"]) == item["sha256"]
            and (self.root / item["file"]).stat().st_size == item["bytes"]
            for item in self.raw_hashes.values()
        )
        return {
            "sources_unchanged": sources,
            "runtime_manifest_unchanged": runtime,
            "tree_unchanged": tree,
            "raw_artifacts_unchanged": raw,
        }

    def save_raw(self, case, raw):
        if (
            case not in CASES
            or case in self.raw_hashes
            or type(raw) is not bytes
            or len(raw) > 65536
        ):
            raise OLD.HostFault("OUTPUT_LIMIT")
        if self.total_written + len(raw) > MIB:
            raise OLD.HostFault("ARTIFACT_LIMIT")
        name = case + "-diagnostic.json"
        target, temporary = self.root / name, self.root / (name + ".tmp")
        if target.exists() or temporary.exists():
            raise OLD.HostFault("ARTIFACT_EXISTS")
        record = {"file": name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        self.raw_hashes[case] = record
        self.total_written += len(raw)
        with temporary.open("wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        return dict(record)

    def create_args(self, name, case, expected):
        return [
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
            "/probe/linux_loaded_probe.py",
            "--case",
            case,
            "--expected",
            expected,
        ]

    async def case(self, case, *, expected):
        if (
            self.preflight_passed is not True
            or self.running is not True
            or self.grant != (case, expected)
            or case in self.used_cases
        ):
            raise OLD.HostFault("CASE_NOT_ADMITTED")
        CORE.parse_case_args(["--case", case, "--expected", expected])
        self.used_cases.add(case)
        self.grant = None
        started, timer = time.monotonic(), OLD.Watchdog(self.docker, 30)
        name = "maskgw-loaded-" + self.task[-12:] + "-" + case
        cid, attempted = None, False
        result = {"case": case, "outcome": "inconclusive", "cleanup_confirmed": False}
        pending = {
            "profile": "loaded-as128",
            "task": self.task,
            "source_hash": self.source_hash,
            "name": name,
            "id": None,
            "phase": "before_create",
            "expected": expected,
        }
        try:
            timer.start()
            self.save("pending.json", pending)
            if (
                timer.fired.is_set()
                or self.watchdog.fired.is_set()
                or time.monotonic() - started >= 30
                or time.monotonic() >= self.lot_deadline
            ):
                raise OLD.HostFault("DEADLINE")
            attempted = True
            rc, raw = await self.cli(*self.create_args(name, case, expected))
            if rc or not OLD.ID_PATTERN.fullmatch(raw.decode("ascii").strip()):
                raise OLD.HostFault("CREATE")
            cid = raw.decode("ascii").strip()
            result["container_id"] = cid
            pending.update(id=cid, phase="created_before_inspect")
            self.save("pending.json", pending)
            self.check(await self.inspect(cid), name, case, expected)
            timer.container_id = self.watchdog.container_id = cid
            remaining = min(30 - (time.monotonic() - started), self.lot_deadline - time.monotonic())
            if remaining <= 0 or timer.fired.is_set() or self.watchdog.fired.is_set():
                raise OLD.HostFault("DEADLINE")
            rc, raw = await self.cli("start", "--attach", cid, limit=65536, timeout=remaining)
            result["diagnostic_artifact"] = self.save_raw(case, raw)
            info = await self.inspect(cid)
            self.check(info, name, case, expected)
            state = info["State"]
            result["exit_code"], result["oom_killed"] = state["ExitCode"], state["OOMKilled"]
            if not raw:
                raise OLD.HostFault("REPORT_MISSING")
            if (
                type(rc) is not int
                or rc != 0
                or state["Running"] is not False
                or type(state["ExitCode"]) is not int
                or state["ExitCode"] != 0
                or state["OOMKilled"] is not False
            ):
                raise OLD.HostFault("CONTAINER_EXIT")
            report = decode_report(raw)
            result["calculated_digest"] = validate_report(report, case, expected)
            result["outcome"] = report["outcome"]
        except BaseException as error:
            result["outcome"] = "inconclusive"
            result["host_failure"] = (
                error.category if type(error) is OLD.HostFault else "COLLECTION"
            )
        finally:
            clean = result.get("host_failure") != "CLI_CLEANUP"
            try:
                timer.close()
            except BaseException:
                clean = False
                result["host_failure"] = "WATCHDOG_CLEANUP"
            try:
                if cid is None and attempted:
                    clean = False
                    rc, listing = await self.cli(
                        "ps", "-aq", "--no-trunc", "--filter", "name=^/" + name + "$"
                    )
                    if rc:
                        raise OLD.HostFault("CREATION_UNCERTAIN")
                    if listing.strip():
                        cid = listing.decode("ascii").strip()
                        self.identity(await self.inspect(cid), name, cid)
                        result["container_id"] = cid
                        pending.update(id=cid, phase="recovered_before_cleanup")
                        self.save("pending.json", pending)
                if cid is not None:
                    await self.cleanup(cid, name)
                    result["container_cleanup_confirmed"] = True
                    pending.update(id=cid, phase="removed")
                    self.save("pending.json", pending)
                    self.watchdog.container_id = None
                result["cleanup_confirmed"] = clean and (cid is not None or not attempted)
            except BaseException:
                result["cleanup_confirmed"] = False
                result["host_failure"] = "CLEANUP"
            result["elapsed_seconds"] = time.monotonic() - started
            if (
                not result["cleanup_confirmed"]
                or result["elapsed_seconds"] > 30
                or timer.fired.is_set()
                or self.watchdog.fired.is_set()
            ):
                result["outcome"] = "inconclusive"
                result["host_failure"] = result.get("host_failure", "DEADLINE_OR_CLEANUP")
            self.save(case + ".json", result)
        return result

    async def run(self):
        if self.started:
            raise OLD.HostFault("LOT_ALREADY_STARTED")
        self.started, self.running, self.preflight_passed = True, True, False
        started = time.monotonic()
        self.lot_deadline = started + 120
        report = {
            "profile": "loaded-as128",
            "image": self.image,
            "bundle_sha256": self.source_hash,
            "source_hashes": self.originals,
            "cases": [],
            "complete": False,
            "diagnostic_success": False,
            "total_memory_contained": False,
            "preflight": {
                "passed": False,
                "attempts": [],
                "attempt_count": 0,
                "cli_cleanup_confirmed": True,
            },
        }
        try:
            self.watchdog.start()
            await self.preflight(report["preflight"])
            expected = "-"
            for case, outcome in zip(CASES, OUTCOMES, strict=True):
                if (
                    not all(self.integrity().values())
                    or self.watchdog.fired.is_set()
                    or time.monotonic() >= self.lot_deadline
                ):
                    raise OLD.HostFault("INTEGRITY_OR_DEADLINE")
                self.grant = case, expected
                result = await self.case(case, expected=expected)
                after = self.integrity()
                result["integrity"] = after
                if not all(after.values()):
                    result["outcome"], result["host_failure"] = "inconclusive", "INTEGRITY"
                self.save(case + ".json", result)
                report["cases"].append(
                    {
                        "case": case,
                        "outcome": result["outcome"],
                        "cleanup_confirmed": result["cleanup_confirmed"],
                        "host_failure": result.get("host_failure"),
                        "report_sha256": OLD.digest(self.root / (case + ".json")),
                    }
                )
                if (
                    result["outcome"] != outcome
                    or not result["cleanup_confirmed"]
                    or result.get("host_failure")
                    or self.watchdog.fired.is_set()
                ):
                    break
                if case == "control":
                    expected = result["calculated_digest"]
            rc, listing = await self.cli("ps", "-aq", "--no-trunc")
            report["inventory_restored"] = type(rc) is int and rc == 0 and not listing.strip()
        except BaseException as error:
            report["host_failure"] = (
                error.category if type(error) is OLD.HostFault else "COLLECTION"
            )
        finally:
            self.running, self.preflight_passed, self.grant = False, False, None
            report["complete"] = len(report["cases"]) == 3
            report["not_executed"] = [case for case in CASES if case not in self.used_cases]
            try:
                self.watchdog.close()
                report["watchdog_closed"] = True
            except BaseException:
                report["watchdog_closed"] = False
            report["elapsed_seconds"] = time.monotonic() - started
            report["deadline_exceeded"] = (
                self.watchdog.fired.is_set() or report["elapsed_seconds"] > 120
            )
            try:
                report.update(self.integrity())
            except BaseException:
                report["sources_unchanged"] = False
            report["diagnostic_success"] = diagnostic_success(report)
            self.save("summary.json", report)
        return report


def diagnostic_success(report):
    return (
        report.get("profile") == "loaded-as128"
        and report.get("complete") is True
        and report.get("total_memory_contained") is False
        and report.get("inventory_restored") is True
        and report.get("watchdog_closed") is True
        and report.get("deadline_exceeded") is False
        and all(
            report.get(key) is True
            for key in (
                "sources_unchanged",
                "tree_unchanged",
                "runtime_manifest_unchanged",
                "raw_artifacts_unchanged",
            )
        )
        and not report.get("host_failure")
        and len(report.get("cases", [])) == 3
        and all(
            item["case"] == case
            and item["outcome"] == outcome
            and item["cleanup_confirmed"] is True
            and not item.get("host_failure")
            for item, case, outcome in zip(report["cases"], CASES, OUTCOMES, strict=True)
        )
    )


def main():
    if len(sys.argv) != 4 or sys.argv[1] != "--run" or not Path(sys.argv[2]).is_file():
        return 64
    root = Path(tempfile.mkdtemp(prefix="maskgw-loaded-as128-20261022-"))
    try:
        observer = Observer(sys.argv[2], root, Path(sys.argv[3]).resolve())
        result = asyncio.run(observer.run())
        print(
            json.dumps(
                {
                    "artifact_root": str(root),
                    "profile": "loaded-as128",
                    "diagnostic_success": result["diagnostic_success"],
                    "total_memory_contained": False,
                }
            )
        )
        return 0 if result["diagnostic_success"] else 2
    except BaseException:
        print(
            json.dumps(
                {
                    "artifact_root": str(root),
                    "outcome": "inconclusive",
                    "total_memory_contained": False,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
