"""HELD lab observer: own profile, flow and two immutable artifacts.

No CLI/threads/workload on import; real procedure and command require review.
Derived lifecycle contract reviewed separately; frozen helpers are unchanged.
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
FROZEN = {
    "linux_as_probe.py": "8170a37b892bd6d2bdae351bacd05f0e047d8bbc9b2b54bad695da7419380e0b",
    "run_linux_as_probe.py": "58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627",
    "linux_import_probe.py": "e92acbacded3aeab72c8237a26bd9471a0e43a83358f250d8dd0933d63af9c1b",
    "prepare_linux_imports.py": "506f7eb057320377371224e687fb8c79d5ce79208dc31d82c8986961fa38c9f0",
    "run_linux_imports.py": "5f85bec97f2c55d7bae13e0663507d78e42698323a3ed460a49a51b45ce60e3e",
    "loaded_memory_protocol.py": "384fe081261086b6437cd9b53b8afe76c72c97262855d9c6465a4488cf1c5b1c",
    "loaded_memory_member.py": "fea05d739b61eff9ba8b23d49cf283f8de9837e711218f7f1965d7392d47eddd",
    "loaded_memory_collect.py": "6d06bfe5344e53596dbbde9e3ae14914b6550cb73147b399e788300e54a733bb",
    "linux_loaded_probe.py": "40ead31f7fe57cb2102f30c1be3f535fa342e3ae22d8696e0970d4eab4315466",
    "run_linux_loaded.py": "d95cdfe231ab273fba96c4ecd808ce829327caea466992ee90c98c9d27a0e821",
    "loaded_memory_evidence.py": "7f0307106e9a139f626c96b7bade14395863cd468f83e22730fceb57dc7d9f53",
    "loaded_memory_tap.py": "aae25eb187ccd483847b725049e8932df469a5d1b9722dad786cb328436f504d",
    "linux_held_probe.py": "3ec0b4fd4c0b061687e388ca735ee4061492a051d0fb68ba55f169720e2e56b4",
}
for _name, _sha in FROZEN.items():
    if OLD.digest(Path(__file__).with_name(_name)) != _sha:
        raise OLD.HostFault("FROZEN_SOURCE_CHANGED")
E = IMPORTS.load("loaded_memory_evidence")
T = IMPORTS.load("loaded_memory_tap")
W = IMPORTS.load("linux_held_probe")
PROFILE = E.PROFILE

CASES, OUTCOMES = ("control", "private", "shared"), ("control_ok", "imposed", "imposed")
PROBES = {
    "linux_as_probe.py",
    "linux_import_probe.py",
    "loaded_memory_protocol.py",
    "loaded_memory_member.py",
    "loaded_memory_collect.py",
    "linux_loaded_probe.py",
    "loaded_memory_tap.py",
    "linux_held_probe.py",
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
                "/probe/linux_held_probe.py",
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


def decode_transport(raw):
    if type(raw) is not bytes:
        raise OLD.HostFault("REPORT_TRANSPORT")
    if raw == T.FALLBACK:
        return None
    failed = False
    try:
        data = E.HOST.decode_report(raw)
        if (
            set(data) != {"profile", "original", "held", "tap_broken"}
            or type(data["profile"]) is not str
            or data["profile"] != T.PROFILE
            or type(data["original"]) is not str
            or type(data["held"]) is not list
            or len(data["held"]) > 2
            or type(data["tap_broken"]) is not bool
        ):
            raise OLD.HostFault("REPORT_TRANSPORT")
        original = data["original"].encode("ascii")
        if (
            not 1 <= len(original) <= 65536
            or not original.endswith(b"\n")
            or original.count(b"\n") != 1
        ):
            raise OLD.HostFault("REPORT_TRANSPORT")
        for text in data["held"]:
            if type(text) is not str or not 1 <= len(text.encode("ascii")) <= 1024:
                raise OLD.HostFault("REPORT_TRANSPORT")
        return data
    except BaseException:
        failed = True
    if failed:
        raise OLD.HostFault("REPORT_TRANSPORT")


class Observer:
    """No legacy case/run/check in MRO; only explicitly selected operations reused."""

    cli, inspect, save = OLD.Observer.cli, OLD.Observer.inspect, OLD.Observer.save
    identity, cleanup = OLD.Observer.identity, OLD.Observer.cleanup
    readiness, preflight = IMPORTS.Observer.readiness, IMPORTS.Observer.preflight

    def __init__(self, docker, root, prepared_root):
        IMPORTS.Observer.__init__(self, docker, BASE, root, prepared_root)
        self.task = "held-as128-" + uuid.uuid4().hex
        for filename in (
            "loaded_memory_protocol.py",
            "loaded_memory_member.py",
            "loaded_memory_collect.py",
            "linux_loaded_probe.py",
            "run_linux_loaded.py",
            "loaded_memory_evidence.py",
            "loaded_memory_tap.py",
            "linux_held_probe.py",
            "run_linux_held.py",
        ):
            original = Path(__file__).with_name(filename)
            sha = OLD.digest(original)
            self.originals[filename] = sha
            IMPORTS.shutil.copyfile(
                original, (self.probe if filename in PROBES else root) / filename
            )
            self.total_written += original.stat().st_size
        if set(self.originals) != set(FROZEN) | {"run_linux_held.py"}:
            raise OLD.HostFault("SOURCE_SET")
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
                "kind": PROFILE,
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
            "pins_consistent": self.pins_consistent(),
        }

    def pins_consistent(self):
        return (
            OLD.digest(self.probe / "linux_loaded_probe.py") == W.SUPERVISOR_SHA
            and OLD.digest(self.probe / "loaded_memory_tap.py") == W.TAP_SHA
            and OLD.digest(self.root / "run_linux_loaded.py") == FROZEN["run_linux_loaded.py"]
            and OLD.digest(self.root / "loaded_memory_evidence.py")
            == FROZEN["loaded_memory_evidence.py"]
            and all(self.originals[name] == sha for name, sha in FROZEN.items())
        )

    def save_artifact(self, case, kind, raw):
        if (
            type(case) is not str
            or case not in CASES
            or type(kind) is not str
            or kind not in ("transport", "envelope")
            or type(raw) is not bytes
            or len(raw) > 65536
        ):
            raise OLD.HostFault("OUTPUT_LIMIT")
        key = case + "-" + kind
        if key in self.raw_hashes:
            raise OLD.HostFault("ARTIFACT_EXISTS")
        if self.total_written + len(raw) > MIB:
            raise OLD.HostFault("ARTIFACT_LIMIT")
        name = key + ".json"
        target, temporary = self.root / name, self.root / (name + ".tmp")
        if target.exists() or temporary.exists():
            raise OLD.HostFault("ARTIFACT_EXISTS")
        record = {"file": name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        self.raw_hashes[key] = record
        self.total_written += len(raw)
        with temporary.open("wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        return dict(record)

    def evaluate(self, result, case, expected):
        started = time.monotonic()
        result["evidence_validated"] = False
        try:
            if (
                self.running is not True
                or self.watchdog.fired.is_set()
                or time.monotonic() >= self.lot_deadline
                or result.get("transport_ready") is not True
                or result.get("cleanup_confirmed") is not True
                or result.get("host_failure")
            ):
                raise OLD.HostFault("EVIDENCE_NOT_ADMITTED")
            ref = self.raw_hashes[case + "-transport"]
            path = self.root / (case + "-transport.json")
            raw = path.read_bytes()
            if len(raw) != ref["bytes"] or hashlib.sha256(raw).hexdigest() != ref["sha256"]:
                raise OLD.HostFault("INTEGRITY")
            payload = decode_transport(raw)
            if payload is None:
                envelope = E.FALLBACK
            else:
                original = payload["original"].encode("ascii")
                held = tuple(text.encode("ascii") for text in payload["held"])
                original_data = E.HOST.decode_report(original)
                envelope = (
                    E.FALLBACK
                    if payload["tap_broken"] and original_data.get("outcome") in OUTCOMES
                    else E.encode(original, held, case, expected)
                )
            result["envelope_artifact"] = self.save_artifact(case, "envelope", envelope)
            decoded = E.decode(envelope, case, expected)
            if payload is None:
                raise OLD.HostFault("TRANSPORT_FALLBACK")
            if payload["tap_broken"]:
                raise OLD.HostFault("TAP_BROKEN")
            if envelope == E.FALLBACK:
                raise OLD.HostFault("EVIDENCE_FALLBACK")
            report = E.HOST.decode_report(decoded["original_report"].encode("ascii"))
            result["calculated_digest"] = E.HOST.validate_report(report, case, expected)
            result["outcome"] = decoded["outcome"]
            result["evidence_validated"] = decoded["outcome"] in OUTCOMES
        except BaseException as error:
            result["outcome"], result["evidence_validated"] = "inconclusive", False
            result["host_failure"] = error.category if type(error) is OLD.HostFault else "EVIDENCE"
        finally:
            result["evaluation_seconds"] = time.monotonic() - started
            if self.watchdog.fired.is_set() or time.monotonic() >= self.lot_deadline:
                result["outcome"], result["evidence_validated"] = "inconclusive", False
                result["host_failure"] = result.get("host_failure", "LOT_DEADLINE")
        return result

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
            "/probe/linux_held_probe.py",
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
        name = "maskgw-held-" + self.task[-12:] + "-" + case
        cid, attempted = None, False
        result = {"case": case, "outcome": "inconclusive", "cleanup_confirmed": False}
        pending = {
            "profile": PROFILE,
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
            result["transport_artifact"] = self.save_artifact(case, "transport", raw)
            info = await self.inspect(cid)
            self.check(info, name, case, expected)
            state = info["State"]
            result["exit_code"], result["oom_killed"] = state["ExitCode"], state["OOMKilled"]
            if state["ExitCode"] == 64:
                raise OLD.HostFault("TRANSPORT_ARGV")
            if state["ExitCode"] == 70:
                raise OLD.HostFault("TRANSPORT_EXECUTION")
            if (
                type(rc) is not int
                or rc != 0
                or state["Running"] is not False
                or type(state["ExitCode"]) is not int
                or state["ExitCode"] != 0
                or state["OOMKilled"] is not False
            ):
                raise OLD.HostFault("CONTAINER_EXIT")
            if not raw:
                raise OLD.HostFault("TRANSPORT_MISSING")
            result["transport_ready"] = True
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
            "profile": PROFILE,
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
                before_eval = self.integrity()
                if not all(before_eval.values()):
                    result["host_failure"] = "INTEGRITY"
                if result.get("transport_ready") and not result.get("host_failure"):
                    result = self.evaluate(result, case, expected)
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
                        "transport_artifact": result.get("transport_artifact"),
                        "envelope_artifact": result.get("envelope_artifact"),
                        "evidence_validated": result.get("evidence_validated", False),
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
                report.update(self.integrity())
            except BaseException:
                report["sources_unchanged"] = False
            try:
                self.watchdog.close()
                report["watchdog_closed"] = True
            except BaseException:
                report["watchdog_closed"] = False
            report["elapsed_seconds"] = time.monotonic() - started
            report["elapsed_scope"] = (
                "through_final_integrity_and_watchdog_close_before_summary_write"
            )
            report["deadline_exceeded"] = (
                self.watchdog.fired.is_set() or report["elapsed_seconds"] > 120
            )
            report["evidence_artifacts_complete"] = len(report["cases"]) == 3 and all(
                type(item.get("transport_artifact")) is dict
                and type(item.get("envelope_artifact")) is dict
                for item in report["cases"]
            )
            report["diagnostic_success"] = diagnostic_success(report)
            self.save("summary.json", report)
        return report


def diagnostic_success(report):
    return (
        report.get("profile") == PROFILE
        and report.get("complete") is True
        and report.get("evidence_artifacts_complete") is True
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
                "pins_consistent",
            )
        )
        and not report.get("host_failure")
        and len(report.get("cases", [])) == 3
        and all(
            item["case"] == case
            and item["outcome"] == outcome
            and item["cleanup_confirmed"] is True
            and not item.get("host_failure")
            and item.get("evidence_validated") is True
            for item, case, outcome in zip(report["cases"], CASES, OUTCOMES, strict=True)
        )
    )


def main():
    if len(sys.argv) != 4 or sys.argv[1] != "--run" or not Path(sys.argv[2]).is_file():
        return 64
    root = Path(tempfile.mkdtemp(prefix="maskgw-held-as128-20261022-"))
    try:
        observer = Observer(sys.argv[2], root, Path(sys.argv[3]).resolve())
        result = asyncio.run(observer.run())
        print(
            json.dumps(
                {
                    "artifact_root": str(root),
                    "profile": PROFILE,
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
