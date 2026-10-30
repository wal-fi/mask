"""Closed 23-case public shell-reader coordinator. Definitions only, no main.

Captured parents provide journal/clock and common volume evidence, never their
historical entry points. Native execution needs a separate reviewed entry.
"""

import asyncio
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import re
import threading
import time

REPO = Path(__file__).resolve().parents[2]
PARENT_SHA = "7275c8ae9e7ccbadc6591cdbb051482ac76c3f3bb52a4f4b86f2966b2261c19e"
SOURCES = {
    "delivery": (
        "docs/poc/pg16_shell_delivery.py",
        "42f7e647c548c1947be61fb7425142ec0f00b7c0fd12ca7700ecece6d2f56188",
    ),
    "profile": (
        "docs/poc/pg16_shell_profile.py",
        "8906e846a792d7aa01bc53da000e35815ba20a9ffee4a7fb8705b19b1b630912",
    ),
    "policy": (
        "docs/poc/pg16_shell_cleanup_policy.py",
        "96e8a4c430c55e66c95c5c8f5a6fe5c9430fdf8389f418d4c4f7888ac39923b0",
    ),
    "watch": (
        "docs/poc/pg16_shell_watchdog.py",
        "cf6634dae741c977a1ace3ca5bc4498fd6f41d8a349524f2cf1d666b4d84bb65",
    ),
    "volumes": (
        "docs/poc/pg16_public_volumes.py",
        "6e3827affcb1a02c00c365a54ecccae5d8e768c188d8232b699efa4c6ddad128",
    ),
    "emergency": (
        "docs/poc/pg16_public_emergency.py",
        "54cc8f68ffa7b46e0fbb66c3076cd80fabd849ac2d9284635c2b39253be30ebc",
    ),
    "identity": (
        "docs/poc/w1_bootstrap_identity.py",
        "dc2481f5a54c1408f6c91c38f99c138d82431b5b1324afdfe9443087323b140d",
    ),
}

# Bootstrap captures only reviewed definitions; exec never receives __main__.
_path = REPO / "docs/poc/pg16_public_host.py"
_info = _path.lstat()
if (
    not _path.is_file()
    or _info.st_size > 65536
    or getattr(_info, "st_file_attributes", 0) & 0x400
    or _path.is_symlink()
):
    raise RuntimeError("READER_PARENT_SOURCE")
PARENT_RAW = _path.read_bytes()
if len(PARENT_RAW) != _info.st_size or hashlib.sha256(PARENT_RAW).hexdigest() != PARENT_SHA:
    raise RuntimeError("READER_PARENT_PIN")
P = {"__name__": "_reader_parent_definitions", "__file__": str(_path)}
exec(compile(PARENT_RAW, str(_path), "exec"), P)
R, V2, need = P["R"], P["V2"], P["need"]
CASES = (
    "one",
    "binary",
    "fragmented",
    "retain",
    "bad-magic",
    "bad-role",
    "bad-digit",
    "header-nul",
    "header-inner-nul",
    "header-cr",
    "zero",
    "oversize",
    "short-header",
    "short-body",
    "short-trailer",
    "bad-trailer",
    "trailer-nul",
    "extra-ascii",
    "extra-nul",
    "extra-lf",
    "wait-header",
    "wait-body",
    "wait-trailer",
)
B_SECONDS = 300.0


class Host(P["Host"]):
    def __init__(self, root, state):
        # Do not initialize the old single-case coordinator or replace its Intent.
        V2["Host"].__init__(self, root, state)
        self.pg, self.pg_raw = {}, {}
        for key, (relative, digest) in SOURCES.items():
            self.pg[key], self.pg_raw[relative] = P["captured"](relative, digest)
        self.profile = self.pg["profile"]
        self.reader = self.profile["R"]
        self.channel = self.pg["delivery"]["C"]
        need(tuple(case.value for case in self.reader["Case"]) == CASES, "CASE_SET")
        self._entry_raw = R["pinned"](Path(__file__), state["host_sha256"])
        self._original_raw = R["pinned"](REPO / "docs/poc/oracle9_w1_run.py", V2["ORIGINAL_SHA"])
        self._blueprints = {
            case: self.profile["blueprint"](state["task"], self.reader["Case"](case))
            for case in CASES
        }
        self._delivery_plan = {
            case: asdict(self.pg["delivery"]["delivery_for"](case)[1]) for case in CASES
        }
        need(
            R["json_bytes"]({k: v[1] for k, v in self._blueprints.items()})
            == R["json_bytes"](state["create_measurements"]),
            "CREATE_MEASUREMENT",
        )
        need(
            R["json_bytes"](self._delivery_plan) == R["json_bytes"](state["delivery_plan"]),
            "DELIVERY_PLAN",
        )
        self._intents, self._owners, self._births = {}, {}, {}
        self._stores, self._monitors, self._heartbeats, self._heartbeat_stops = {}, {}, {}, {}
        self._monitor_attempted, self._monitor_joined = set(), set()
        self._supervision_errors = {}
        self._monitor_results = {}
        self._active_case, self._b_started = None, None
        self._initial_volumes, self._baseline_at = None, None
        self._create_invoked = set()
        self._remove_approved, self._kill_approved, self._invoke_approved = None, None, None
        self._stop_approved = False
        self._cleanup_lock = threading.Lock()
        self._loop, self._foreground, self._foreground_case = None, None, None
        self._host_tasks, self._cases = [], []
        self._cli_sequence, self._evidence_sequence = 0, 0
        self.result["volumes_restored"] = False

    def _budget(self):
        if self._b_started is not None:
            need(0 <= time.monotonic() - self._b_started < B_SECONDS, "B_DEADLINE")

    def _gate(self):
        need(not any(m.fired.is_set() for m in self._monitors.values()), "WATCHDOG_FIRED")
        self._budget()

    def pins(self, cleanup=False):
        need(hashlib.sha256(PARENT_RAW).hexdigest() == PARENT_SHA, "PARENT_CAPTURE")
        need(hashlib.sha256(P["V2_RAW"]).hexdigest() == P["V2_SHA"], "V2_CAPTURE")
        need(
            hashlib.sha256(self._original_raw).hexdigest() == V2["ORIGINAL_SHA"], "ORIGINAL_CAPTURE"
        )
        if not cleanup:
            R["pinned"](REPO / "docs/poc/pg16_public_host.py", PARENT_SHA)
            R["pinned"](REPO / "docs/poc/oracle9_w1_run_v2.py", P["V2_SHA"])
            R["pinned"](REPO / "docs/poc/oracle9_w1_run.py", V2["ORIGINAL_SHA"])
        for relative, raw in self.captured.items():
            digest = self.state["pins"][relative]
            need(hashlib.sha256(raw).hexdigest() == digest, "CAPTURE")
            if not cleanup:
                R["pinned"](REPO / relative, digest)
        for relative, digest in SOURCES.values():
            need(hashlib.sha256(self.pg_raw[relative]).hexdigest() == digest, "CAPTURE")
            if not cleanup:
                R["pinned"](REPO / relative, digest)
        need(
            hashlib.sha256(self._entry_raw).hexdigest() == self.state["host_sha256"], "HOST_CAPTURE"
        )
        if not cleanup:
            R["pinned"](Path(__file__), self.state["host_sha256"])
        for path, digest in R["EXTERNAL_PINS"].items():
            R["pinned"](path, digest, 134217728)
        need(
            json.loads(R["regular"](R["META"], 16384))["Endpoints"]["docker"]["Host"]
            in (
                "npipe:////./pipe/dockerDesktopLinuxEngine",
                "npipe://./pipe/dockerDesktopLinuxEngine",
            ),
            "ENDPOINT",
        )

    def _stem(self, case):
        need(type(case) is str and case in CASES, "CASE")
        return "case-" + str(CASES.index(case) + 1).zfill(2) + "-" + case

    def _record(self, case):
        records = [r for r in self.records if r["case"] == case]
        need(len(records) == 1, "RECORD")
        return records[0]

    def _barrier(self, case):
        for prior in CASES[: CASES.index(case)]:
            record = self._record(prior)
            owner = self._owners.get(prior)
            need(
                record["removed"]
                and record.get("case_volume_restored") is True
                and owner is not None
                and owner.metadata()["released"] is True
                and prior in self._monitor_joined,
                "PREVIOUS_CASE_HELD",
            )
            metadata = self._monitors[prior].metadata()
            need(
                metadata["thread_joined"] is True
                and not metadata["fired"]
                and not metadata["held"]
                and prior not in self._supervision_errors,
                "PREVIOUS_CASE_HELD",
            )

    def _cid_record(self, cid):
        if type(cid) is not str or not re.fullmatch(r"[0-9a-f]{64}", cid):
            return None
        rows = [r for r in self.records if r["cid"] == cid and not r["create_uncertain"]]
        return rows[0] if len(rows) == 1 else None

    def _cid_allowed(self, cid):
        return self._cid_record(cid) is not None

    def _all_joined(self):
        return self._monitor_attempted <= self._monitor_joined and all(
            self._monitors[case].metadata()["thread_joined"] is True
            for case in self._monitor_attempted
        )

    async def invoke(
        self, label, args, timeout, limit, *, cleanup=False, public_clock=False, app_start=False
    ):
        token = (label, tuple(args), timeout, limit, cleanup, public_clock, app_start)
        need(self._invoke_approved is not None and token == self._invoke_approved, "INVOKE_SCOPE")
        self._invoke_approved = None  # consume before the first await
        self.pins(cleanup=cleanup)
        if not cleanup:
            self._gate()  # hashes may have consumed the remaining B budget
        start = time.monotonic()
        try:
            code, raw = await self._bounded(
                label, args, timeout, limit, public_clock=public_clock, app_start=app_start
            )
        except BaseException as error:
            self.commands.append(
                {
                    "label": label,
                    "exit": None,
                    "category": type(error).__name__,
                    "seconds": time.monotonic() - start,
                }
            )
            raise
        self.commands.append(
            {
                "label": label,
                "exit": code,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "seconds": time.monotonic() - start,
            }
        )
        return code, raw

    async def _bounded(self, label, args, timeout, limit, *, public_clock=False, app_start=False):
        # Private TCB backend, reached only after invoke consumes its token.
        # Environment construction preserves the 4bc distinction.
        helper = self.libs["bounded"]
        if public_clock or app_start:
            raw = self.captured[R["LIBRARIES"]["bounded"][0]]
            helper = {
                "__name__": "_reader_public_ps",
                "__file__": str(REPO / R["LIBRARIES"]["bounded"][0]),
            }
            exec(compile(raw, helper["__file__"], "exec"), helper)
            helper["environment"] = (
                R["desktop_environment"] if app_start else self.libs["clock"]["environment"]
            )
        return await helper["bounded"](args, timeout=timeout, limit=limit)

    async def powershell(self, label, command, timeout=3, cleanup=False, start=False):
        need(
            command == R["PROCESS_COMMAND"]
            or (
                command == R["START_COMMAND"]
                and start is True
                and cleanup is False
                and self.initial_active is False
                and self.started is None
                and self._b_started is None
            ),
            "PS_SCOPE",
        )
        need((command == R["START_COMMAND"]) is start, "PS_SCOPE")
        self._controls(label, timeout, 65536, cleanup)
        self._invoke_approved = (
            label,
            (str(R["SHELL"]), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command),
            timeout,
            65536,
            cleanup,
            not start,
            start,
        )
        try:
            return await R["Host"].powershell(
                self, label, command, timeout=timeout, cleanup=cleanup, start=start
            )
        finally:
            self._invoke_approved = None

    def _controls(self, label, timeout, limit, cleanup):
        need(
            type(label) is str
            and re.fullmatch(r"[A-Za-z0-9_-]{1,96}", label)
            and type(timeout) in (int, float)
            and math.isfinite(timeout)
            and 0 < timeout <= 45
            and type(limit) is int
            and 0 < limit <= 2097152
            and type(cleanup) is bool,
            "CLI_CONTROLS",
        )
        if not cleanup:
            self._gate()

    async def cli(self, label, *args, timeout=3, limit=2097152, cleanup=False):
        self._controls(label, timeout, limit, cleanup)
        need(all(type(a) is str for a in args), "READER_CLI_SCOPE")
        allowed = args in {
            ("version", "--format", "{{json .}}"),
            ("info", "--format", "{{json .}}"),
            ("ps", "-aq", "--no-trunc"),
            ("image", "inspect", self.profile["IMAGE"]),
            ("volume", "ls", "-q"),
        }
        create = next((c for c in CASES if args == self._blueprints[c][0]), None)
        if create is not None:
            self._barrier(create)
            record = self._record(create)
            allowed = (
                not cleanup
                and self._active_case == create
                and create in self._intents
                and record["intent_persisted"] is True
                and record["create_uncertain"]
                and create not in self._create_invoked
                and self._b_started is not None
                and self.cycle.phase is self.libs["core"]["Phase"].B_CONSUMED
                and create in self._monitor_attempted
                and create not in self._monitor_joined
            )
        record = self._cid_record(args[-1]) if args else None
        if (
            record is not None
            and not record["removed"]
            and (cleanup or record["case"] == self._active_case)
        ):
            allowed = allowed or args[:-1] == ("inspect", "--type", "container")
            if args[0] == "rm":
                allowed = cleanup and args == self._remove_approved
            if args[0] == "kill":
                allowed = cleanup and args == self._kill_approved
        if len(args) == 5 and args[:4] == ("ps", "-aq", "--no-trunc", "--filter"):
            allowed = args[-1].startswith("id=") and self._cid_allowed(args[-1][3:])
        if args == ("desktop", "stop", "--timeout", "20"):
            allowed = (
                cleanup
                and self._stop_approved
                and self._all_joined()
                and self.result.get("owned_cleanup") is True
            )
        need(allowed, "READER_CLI_SCOPE")
        if create is not None:
            self._create_invoked.add(create)
            self._record(create)["create_invoked"] = True
            self.record_intents()  # conservative intent, not a syscall receipt
        if args[0] == "rm":
            self._remove_approved = None
        if args[0] == "kill":
            self._kill_approved = None
        if args[0] == "desktop":
            self._stop_approved = False
        self._cli_sequence += 1
        index = self._cli_sequence
        self._invoke_approved = (
            label,
            (str(R["CLI"]), "--context", "desktop-linux", *args),
            timeout,
            limit,
            cleanup,
            False,
            False,
        )
        try:
            code, raw = await R["Host"].cli(
                self, label, *args, timeout=timeout, limit=limit, cleanup=cleanup
            )
        finally:
            self._invoke_approved = None
        prefix = "local-volume-cli-" if args == ("volume", "ls", "-q") else "local-cli-"
        discard = args[0] in ("version", "info")
        artifact = None if discard else prefix + str(index).zfill(3) + ".bin"
        if artifact is not None:
            self.write_new(artifact, raw, limit)
        manifest = [
            *getattr(self, "_reply_manifest", ()),
            {
                "index": index,
                "label": label,
                "artifact": artifact,
                "exit": code,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "local_only": True,
                "raw_disposition": "DISCARDED_CONFIGURATION" if discard else "LOCAL_ONLY",
            },
        ]
        self.save("public-cli-manifest.json", manifest)
        self._reply_manifest = manifest
        return code, raw

    async def preflight(self):
        need(not self._intents and self._initial_volumes is None, "PREFLIGHT_REUSED")
        one = self.profile["P"]["one"]
        code, raw = await self.cli("version", "version", "--format", "{{json .}}")
        need(code == 0, "VERSION")
        version, projected = one(b"[" + raw + b"]"), {}
        pattern = r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(?:[-+][A-Za-z0-9_.-]{1,32})?"
        for side in ("Client", "Server"):
            if side == "Server" and version.get(side) is None:
                continue
            item = version.get(side)
            need(
                type(item) is dict
                and type(item.get("Version")) is str
                and re.fullmatch(pattern, item["Version"]),
                "VERSION",
            )
            projected[side] = {"Version": item["Version"]}
        self.save("version.json", projected)
        code, raw = await self.cli("info", "info", "--format", "{{json .}}")
        need(code == 0, "DAEMON")
        info = one(b"[" + raw + b"]")
        public = {
            key: info.get(key)
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
        need(
            public["OSType"] == "linux"
            and public["Architecture"] in ("amd64", "x86_64")
            and public["CgroupVersion"] == "2"
            and public["KernelVersion"] == R["KERNEL"]
            and type(public["MemTotal"]) is int
            and public["MemTotal"] >= 2 * 1024**3
            and type(public["Driver"]) is str
            and re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", public["Driver"])
            and type(public["ServerVersion"]) is str
            and re.fullmatch(pattern, public["ServerVersion"]),
            "DAEMON_PROFILE",
        )
        self.save("daemon.json", public)
        await self.empty_inventory("inventory-preflight")
        code, raw = await self.cli("reader-image", "image", "inspect", self.profile["IMAGE"])
        need(code == 0, "IMAGE")
        image = self.profile["admit_image"](raw)
        volumes = await self._inventory_volumes("volumes-initial")
        self._baseline_at = time.monotonic()
        self.write_new(
            "local-volume-baseline.json",
            R["json_bytes"](
                {"kind": "MASKGW_PG16_LOCAL_VOLUME_BASELINE_V1", "names": sorted(volumes)}
            ),
            65536,
        )
        self._metadata(
            "volume-baseline",
            {
                "kind": "MASKGW_PG16_PUBLIC_VOLUME_BASELINE_V1",
                "count": len(volumes),
                "sha256": self.pg["watch"]["volume_sha256"](volumes),
            },
        )
        self._initial_volumes = volumes
        for case in CASES:
            intent = self.profile["Intent"](self.state["task"], image, self.reader["Case"](case))
            need(self.profile["create_args"](intent) == self._blueprints[case], "CREATE_BLUEPRINT")
            self._intents[case] = intent

    async def checkpoint(self, action):
        if action == "B":
            need(
                len(self._intents) == 23
                and len(self._monitors) == 23
                and self._active_case == CASES[0]
                and self._b_started is None
                and self._initial_volumes is not None,
                "SUPERVISION_REQUIRED",
            )
            self._b_started = time.monotonic()
            for store in self._stores.values():
                store.arm_b(self._b_started)
        return await R["Host"].checkpoint(self, action)

    def _publish(self, record, owner=None):
        case = record["case"]
        need(case in self._stores and self._initial_volumes is not None, "SUPERVISION_REQUIRED")
        if owner is not None:
            birth = self.pg["identity"]["capture"](owner._process)
            if birth is not None:
                previous = self._births.get(case)
                need(previous is None or previous == birth, "CLI_IDENTITY_CHANGED")
                self._births[case] = birth
        birth = self._births.get(case)
        snapshot = self.pg["watch"]["Snapshot"](
            self.state["task"],
            case,
            self._intents[case].command,
            tuple(sorted(self._initial_volumes)),
            record["cid"],
            None if birth is None else birth.pid,
            None if birth is None else birth.filetime,
        )
        self._monitors[case].check_snapshot(snapshot)
        self._stores[case].publish(snapshot)

    async def create_own(self, case):
        self._stem(case)
        self._barrier(case)
        need(
            case == self._active_case
            and case in self._intents
            and len(self.records) == CASES.index(case)
            and self._initial_volumes is not None,
            "CREATE_NOT_ADMITTED",
        )
        self._budget()
        current = await self._inventory_volumes("volumes-before-" + case)
        need(current == self._initial_volumes, "VOLUME_BASELINE_CHANGED")
        self._baseline_at = time.monotonic()  # fresh equal observation, not renewed baseline
        intent = self._intents[case]
        args, measure = self.profile["create_args"](intent)
        need((args, measure) == self._blueprints[case], "CREATE_BLUEPRINT")
        record = {
            "role": "pg16-reader",
            "case": case,
            "name": intent.name,
            "image": self.profile["IMAGE"],
            "command": list(intent.command),
            "cid": None,
            "removed": False,
            "create_uncertain": True,
            "create_invoked": False,
            "intent_persisted": False,
            "case_volume_restored": False,
        }
        self.records.append(record)
        self.write_new(self._stem(case) + "-intent.json", R["json_bytes"](record))
        self.record_intents()
        record["intent_persisted"] = True
        self._publish(record)
        need(0 <= time.monotonic() - self._baseline_at <= 30.0, "VOLUME_BASELINE_STALE")
        code, raw = await self.cli("create-" + case, *args, timeout=5)
        need(code == 0 and re.fullmatch(rb"[0-9a-f]{64}\s*", raw), "CREATE_EXIT")
        cid = raw.decode("ascii").strip()
        need(not any(r is not record and r["cid"] == cid for r in self.records), "CID_REUSED")
        record.update(cid=cid, create_uncertain=False)
        self.record_intents()
        self._publish(record)
        info, _ = await self.inspect_own(record)
        need(
            info["State"]["Running"] is False
            and type(info["State"]["Pid"]) is int
            and info["State"]["Pid"] == 0,
            "CREATE_RUNNING",
        )
        return record

    async def inspect_own(self, record, cleanup=False, timeout=3, result=False):
        need(type(result) is bool, "INSPECT_PHASE")
        need(self._cid_record(record["cid"]) is record and not record["removed"], "CID_REQUIRED")
        code, raw = await self.cli(
            ("inspect-result-" if result else "inspect-") + record["case"],
            "inspect",
            "--type",
            "container",
            record["cid"],
            cleanup=cleanup,
            timeout=timeout,
        )
        need(code == 0, "INSPECT")
        info = self.profile["P"]["one"](raw)
        intent = self._intents[record["case"]]
        if cleanup:
            self.pg["policy"]["identity"](
                info,
                task=self.state["task"],
                case=record["case"],
                command=intent.command,
                cid=record["cid"],
            )
        else:
            self.profile["validate_container"](info, intent, record["cid"])
        return info, raw

    async def start_supervision(self):
        need(not self._monitors and self._loop is None, "SUPERVISION_REUSED")
        self._loop = asyncio.get_running_loop()
        # Capture every nested definition before A, never between cases in B.
        for index, case in enumerate(CASES, 1):
            root = self.root / ("watch-" + str(index).zfill(2))
            root.mkdir()
            store = self.pg["watch"]["Store"](time.monotonic())
            self._stores[case] = store

            def request_abort(selected=case):
                self._loop.call_soon_threadsafe(self._abort_case, selected)

            self._monitors[case] = self.pg["watch"]["Watchdog"](
                root,
                store,
                self._cleanup_lock,
                request_abort,
                self.pg_raw[SOURCES["emergency"][0]],
                self.pg_raw[SOURCES["policy"][0]],
                self.captured[R["LIBRARIES"]["bounded"][0]],
                self.pg_raw[SOURCES["identity"][0]],
                self.pg_raw[SOURCES["volumes"][0]],
            )
        await self._activate(CASES[0])

    async def _activate(self, case):
        self._barrier(case)
        self._controls("activate", 1, 1, False)
        need(case in self._monitors and case not in self._monitor_attempted, "MONITOR_REUSED")
        self._active_case = case
        self._stores[case].pulse(time.monotonic())
        self._heartbeat_stops[case] = asyncio.Event()
        self._heartbeats[case] = self._task(self._pulse(case), "maskgw-reader-heartbeat-" + case)
        self._monitor_attempted.add(case)  # includes start that raises/returns uncertain
        need(self._monitors[case].start(), "WATCHDOG_START")

    def _abort_case(self, case):
        self._monitors[case].ack.set()
        if (
            self._foreground_case == case
            and self._foreground is not None
            and not self._foreground.done()
        ):
            self._foreground.cancel()

    async def _pulse(self, case):
        stop = self._heartbeat_stops[case]
        while not stop.is_set():
            self._stores[case].pulse(time.monotonic())
            try:
                await asyncio.wait_for(stop.wait(), 1.0)
            except TimeoutError:
                pass

    async def _finish_monitor(self, case, *, require_clean=False):
        monitor = self._monitors[case]
        errors = []
        if case in self._monitor_attempted and case not in self._monitor_joined:
            try:
                if monitor.close() and monitor.metadata()["thread_joined"] is True:
                    self._monitor_joined.add(case)
            except Exception:
                errors.append("MONITOR_CLOSE")
        stop = self._heartbeat_stops.get(case)
        if stop is not None:
            stop.set()
        task = self._heartbeats.get(case)
        if task is not None:
            try:
                await task
            except asyncio.CancelledError:
                current = asyncio.current_task()
                # A later teardown may prove a stopped, already-cancelled child
                # collected. Never suppress cancellation of this foreground.
                if not (
                    stop is not None
                    and stop.is_set()
                    and task.done()
                    and task.cancelled()
                    and current is not None
                    and current.cancelling() == 0
                ):
                    errors.append("HEARTBEAT")
            except Exception:
                errors.append("HEARTBEAT")
        try:
            metadata = monitor.metadata()
        except Exception:
            metadata = {"thread_joined": False, "fired": True, "held": True}
            errors.append("MONITOR_METADATA")
        if case in self._monitor_attempted and (
            case not in self._monitor_joined or metadata["thread_joined"] is not True
        ):
            errors.append("MONITOR_JOIN")
        status = (
            "HELD"
            if errors
            else "NOT_STARTED"
            if case not in self._monitor_attempted
            else "JOINED"
            if case in self._monitor_joined and metadata["thread_joined"] is True
            else "HELD"
        )
        try:
            self._metadata(
                "monitor-" + self._stem(case),
                {"case": case, "status": status, "metadata": metadata, "errors": errors},
            )
        except Exception:
            errors.append("MONITOR_EVIDENCE")
        if errors:
            self._supervision_errors[case] = tuple(errors)
        else:
            self._supervision_errors.pop(case, None)
        self._monitor_results[case] = {
            "status": "HELD" if errors else status,
            "metadata": metadata,
            "errors": list(errors),
        }
        need(not errors, "SUPERVISION_HELD")  # outside except: no raw exception chain
        if require_clean:
            need(
                status == "JOINED" and not metadata["fired"] and not metadata["held"],
                "MONITOR_HELD",
            )

    def _bind_owner(self, owner, record):
        intent = self._intents[record["case"]]
        target = owner.target
        need(
            owner.wrapper == intent.command[1]
            and owner.wrapper_sha256 == intent.source_sha256
            and target.cid == record["cid"]
            and target.task == self.state["task"]
            and target.image == self.profile["IMAGE"]
            and target.source_sha256 == intent.core_sha256
            and asdict(owner.delivery) == self._delivery_plan[record["case"]],
            "OWNER_BINDING",
        )

    async def _case(self, case):
        record = await self.create_own(case)
        owner = self.pg["delivery"]["PublicDeliveryOwner"](self.state["task"], record["cid"], case)
        self._owners[case] = owner  # before any start, including failed/late spawn
        self._bind_owner(owner, record)
        self.pins()
        self._controls("owner-start", 1, 1, False)
        try:
            await owner.start()
        finally:
            self._publish(record, owner)
        await owner.send_vector()
        observation = await owner.drain()
        need(
            type(observation.returncode) is int
            and observation.returncode in (0, 42)
            and type(observation.output) is bytes
            and type(observation.stdout_bytes) is int
            and type(observation.report_bytes) is int
            and observation.report_bytes == len(observation.output)
            and observation.stdout_bytes
            == len(owner.target.ready_line()) + observation.report_bytes,
            "OBSERVATION",
        )
        raw = observation.output
        self.write_new("local-" + self._stem(case) + "-output.bin", raw, self.reader["MAX_OUTPUT"])
        facts = self.reader["parse_report"](
            raw, observation.returncode, self.state["task"], self.reader["Case"](case)
        )
        self.write_new(self._stem(case) + "-report.json", R["json_bytes"](facts), 8192)
        info, _ = await self.inspect_own(record, result=True)
        inspect_reply = self._reply_manifest[-1]
        need(
            inspect_reply["label"] == "inspect-result-" + case
            and inspect_reply["exit"] == 0
            and type(inspect_reply["artifact"]) is str,
            "RESULT_INSPECT_BINDING",
        )
        state = info["State"]
        need(
            state["Running"] is False
            and type(state["Pid"]) is int
            and state["Pid"] == 0
            and state.get("OOMKilled") is False
            and state.get("Dead") is False
            and type(state.get("ExitCode")) is int
            and state["ExitCode"] == observation.returncode,
            "PROBE_STATE",
        )
        await self._collect(record)
        await self._finish_monitor(case, require_clean=True)
        self._cases.append(
            {
                "case": case,
                "owner": owner.metadata(),
                "removed": record["removed"],
                "case_volume_restored": record["case_volume_restored"],
                "returncode": observation.returncode,
                "stdout_bytes": observation.stdout_bytes,
                "report_bytes": observation.report_bytes,
                "inspect_exit_code": state["ExitCode"],
                "oom_killed": state["OOMKilled"],
                "dead": state["Dead"],
                "report_ok": facts["ok"],
                "report_category": facts["category"] if not facts["ok"] else None,
                "inspect_label": "inspect-result-" + case,
                "inspect_cli_index": inspect_reply["index"],
                "inspect_artifact": inspect_reply["artifact"],
                "delivery": self._delivery_plan[case],
                "monitor": self._monitors[case].metadata(),
            }
        )
        self.save("cases.json", self._cases)

    async def _collect(self, record):
        case, cid = record["case"], record["cid"]
        need(self._cid_record(cid) is record, "CID_REQUIRED")
        owner, ticket = self._owners.get(case), None
        if owner is not None:
            for _ in range(2):
                ticket = await owner.quiesce()
                self._publish(record, owner)
                if ticket is not None:
                    break
            need(ticket is not None, "OWNER_HELD")
        end, lock_end = time.monotonic() + 25.0, time.monotonic() + 1.0

        def remaining(cap):
            value = min(cap, end - time.monotonic())
            need(value > 0, "CLEANUP_DEADLINE")
            return value

        acquired = False
        while not acquired and time.monotonic() < lock_end:
            acquired = self._cleanup_lock.acquire(blocking=False)
            if not acquired:
                await asyncio.sleep(0.01)
        need(acquired, "CLEANUP_LOCK")
        try:
            if not record["removed"]:
                code, raw = await self.cli(
                    "inspect-cleanup-" + case,
                    "inspect",
                    "--type",
                    "container",
                    cid,
                    timeout=remaining(3),
                    cleanup=True,
                )
                if code == 0:
                    info = self.profile["P"]["one"](raw)
                    self.pg["policy"]["identity"](
                        info,
                        task=self.state["task"],
                        case=case,
                        command=self._intents[case].command,
                        cid=cid,
                    )
                    if info["State"]["Running"] is True:
                        self._kill_approved = ("kill", "--signal", "KILL", cid)
                        code, _ = await self.cli(
                            "kill-" + case, *self._kill_approved, timeout=remaining(4), cleanup=True
                        )
                        need(code == 0, "KILL")
                        info, _ = await self.inspect_own(record, cleanup=True, timeout=remaining(3))
                    need(
                        info["State"]["Running"] is False
                        and type(info["State"]["Pid"]) is int
                        and info["State"]["Pid"] == 0,
                        "RUNNING",
                    )
                    args = self._removal(record, info)
                    code, raw = await self.cli(
                        "rm-" + case, *args, cid, timeout=remaining(8), cleanup=True
                    )
                    need(code == 0 and raw.strip() == cid.encode("ascii"), "REMOVE")
            code, raw = await self.cli(
                "absent-after-" + case,
                "ps",
                "-aq",
                "--no-trunc",
                "--filter",
                "id=" + cid,
                timeout=remaining(3),
                cleanup=True,
            )
            need(code == 0 and not raw.strip(), "ABSENCE")
            record["removed"] = True
            self.record_intents()
            await self._volume_final(timeout=remaining(3))
            need(time.monotonic() <= end, "CLEANUP_DEADLINE")
            if owner is not None:
                need(
                    await owner.close(self.channel["Absent"](ticket, time.monotonic())),
                    "OWNER_HELD",
                )
                owner.assert_released()
            record["case_volume_restored"] = True
            self.record_intents()
        finally:
            self._remove_approved, self._kill_approved = None, None
            self._cleanup_lock.release()

    async def perform_b(self):
        need(
            self.cycle.phase is self.libs["core"]["Phase"].B_CONSUMED
            and self._b_started is not None
            and not self._cases,
            "B_REQUIRED",
        )
        self._budget()
        async with asyncio.timeout(max(0.001, B_SECONDS - (time.monotonic() - self._b_started))):
            for index, case in enumerate(CASES):
                self.pins()
                self._gate()
                if index:
                    await self._activate(case)
                self._foreground_case = case
                await self.foreground(self._case(case))
                self._foreground_case = None
        self._gate()
        need(
            len(self._cases) == 23
            and len(self._monitor_joined) == 23
            and not self._supervision_errors
            and not any(row.get("exit") is None for row in self.commands),
            "B_INCOMPLETE",
        )
        self.result["pg16_reader_verified"] = True

    async def cleanup_owned(self):
        self.result["owned_cleanup"] = False
        clean = True
        for record in self.records:
            owner = self._owners.get(record["case"])
            if (
                record["case"] not in self._create_invoked
                and record["cid"] is None
                and owner is None
            ):
                # No external create was submitted. This is not CID-absence
                # evidence and never counts as a completed matrix case.
                record["create_not_invoked"] = True
                continue
            if (
                record["removed"]
                and record.get("case_volume_restored") is True
                and (owner is None or owner.metadata()["released"] is True)
                and not record.get("volume_uncertain")
            ):
                continue
            if record["create_uncertain"] or record["cid"] is None:
                clean = False
                record["cleanup_unproven"] = True
                continue
            try:
                await self._collect(record)
            except Exception:
                clean = False
                record["cleanup_unproven"] = True
        clean = clean and not any(row.get("exit") is None for row in self.commands)
        if clean:
            await self.empty_inventory("inventory-final", cleanup=True)
            self.result["inventory_restored"] = True
            if self._initial_volumes is not None:
                await self._volume_final()
            else:
                need(not self.records, "VOLUME_BASELINE_REQUIRED")
            self.result["owned_cleanup"] = True
        self.record_intents()

    async def stop_supervision(self):
        failed = False
        for case in CASES:
            if case in self._monitors:
                try:
                    await self._finish_monitor(case)
                except (Exception, asyncio.CancelledError):
                    failed = True
        self.result["watchdogs"] = {
            case: self._monitor_results.get(
                case, {"status": "HELD", "errors": ["MONITOR_UNPROVEN"]}
            )
            for case in self._monitors
        }
        need(not failed and not self._supervision_errors, "SUPERVISION_HELD")

    async def restore_desktop(self):
        need(
            self._all_joined()
            and self.result.get("owned_cleanup") is True
            and all(task.done() for task in self._host_tasks),
            "RESTORE_UNPROVEN",
        )
        if self._initial_volumes is not None:
            await self._volume_final()
        self._stop_approved = True
        try:
            await R["Host"].restore_desktop(self)
        finally:
            self._stop_approved = False

    def assert_released(self):
        need(
            self.result.get("owned_cleanup") is True
            and self._all_joined()
            and all(task.done() for task in self._host_tasks),
            "HOST_HELD",
        )
        for owner in self._owners.values():
            owner.assert_released()
