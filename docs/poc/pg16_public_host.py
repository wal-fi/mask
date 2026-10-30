"""Public PG16 probe coordinator definitions only. No main or native effects on import."""

import asyncio
import hashlib
import json
from pathlib import Path
import re
import stat
import threading
import time

REPO = Path(__file__).resolve().parents[2]
V2_SHA = "b59388f52a38319c19c2c60b25100347d319a59c2778395cc68bea64d2bc0c37"
SOURCES = {
    "owner": (
        "docs/poc/pg16_public_owner.py",
        "a02f0b71311fabd44685606e36134c50b719ecf863de98f164268a04d6b54e4c",
    ),
    "profile": (
        "docs/poc/pg16_public_profile.py",
        "fe2f8ba8bfabc5572fe7aeb85c31c54de38ceaa23c1a6c34dd631425371d9277",
    ),
    "policy": (
        "docs/poc/pg16_public_cleanup_policy.py",
        "f1d94928112afc6a2c0f179201cab74e60dd515c94337e625e1ea8912d28a46c",
    ),
    "volumes": (
        "docs/poc/pg16_public_volumes.py",
        "6e3827affcb1a02c00c365a54ecccae5d8e768c188d8232b699efa4c6ddad128",
    ),
    "identity": (
        "docs/poc/w1_bootstrap_identity.py",
        "dc2481f5a54c1408f6c91c38f99c138d82431b5b1324afdfe9443087323b140d",
    ),
    "emergency": (
        "docs/poc/pg16_public_emergency.py",
        "54cc8f68ffa7b46e0fbb66c3076cd80fabd849ac2d9284635c2b39253be30ebc",
    ),
    "watch": (
        "docs/poc/pg16_public_watchdog.py",
        "b86841ea9c7329e1636ee08e3314e29dde6b9572b45c121a1095b4eb5b13cf03",
    ),
}
CASE = "pg16-public"


def need(value, category):
    if not value:
        raise RuntimeError(category) from None


def captured(relative, digest):
    path = REPO / relative
    info = path.lstat()
    need(
        stat.S_ISREG(info.st_mode)
        and not getattr(info, "st_file_attributes", 0) & 0x400
        and info.st_size <= 65536,
        "SOURCE",
    )
    raw = path.read_bytes()
    need(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == digest, "SOURCE_PIN")
    namespace = {"__name__": "_pg16_public_definitions", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace, raw


V2, V2_RAW = captured("docs/poc/oracle9_w1_run_v2.py", V2_SHA)
R = V2["R"]


class Host(V2["Host"]):
    def __init__(self, root, state):
        super().__init__(root, state)
        self.pg, self.pg_raw = {}, {}
        for key, (relative, digest) in SOURCES.items():
            self.pg[key], self.pg_raw[relative] = captured(relative, digest)
        # Use the owner's profile namespace so Intent/Target exact-type checks agree.
        self.profile = self.pg["owner"]["P"]
        self.channel = self.pg["owner"]["C"]
        self._entry_raw = R["pinned"](Path(__file__), state["host_sha256"])
        self._blueprint = self.profile["blueprint"](state["task"])
        need(self._blueprint[1] == state["create_measurement"], "CREATE_MEASUREMENT")
        self._intent, self._initial_volumes = None, None
        self._baseline_at = None
        self._create_invoked = False
        self._remove_approved, self._kill_approved = None, None
        self._stop_approved = False
        self._owners, self._births = {}, {}
        self._store, self._monitor, self._cleanup_lock = None, None, None
        self._loop, self._foreground, self._heartbeat = None, None, None
        self._heartbeat_stop = False
        self._monitor_joined = False
        self._host_tasks, self._cases = [], []
        self._cli_sequence = 0
        self._evidence_sequence = 0
        self.result["volumes_restored"] = False

    def pins(self, cleanup=False):
        need(hashlib.sha256(V2_RAW).hexdigest() == V2_SHA, "V2_CAPTURE")
        if not cleanup:
            R["pinned"](REPO / "docs/poc/oracle9_w1_run_v2.py", V2_SHA)
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
            need(self._monitor is None or not self._monitor.fired.is_set(), "WATCHDOG_FIRED")
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

    def _cid_allowed(self, cid):
        return (
            type(cid) is str
            and re.fullmatch(r"[0-9a-f]{64}", cid)
            and any(r["cid"] == cid and not r["create_uncertain"] for r in self.records)
        )

    async def cli(self, label, *args, timeout=3, limit=2097152, cleanup=False):
        fixed = {
            ("version", "--format", "{{json .}}"),
            ("info", "--format", "{{json .}}"),
            ("ps", "-aq", "--no-trunc"),
            ("image", "inspect", self.profile["IMAGE"]),
            ("volume", "ls", "-q"),
        }
        allowed = args in fixed
        if args == self._blueprint[0]:
            allowed = (
                self._intent is not None
                and len(self.records) == 1
                and self.records[0]["create_uncertain"]
                and self.records[0].get("intent_persisted") is True
                and not self._create_invoked
            )
        if len(args) >= 2 and self._cid_allowed(args[-1]):
            allowed = allowed or args[:-1] in (("inspect", "--type", "container"),)
            if args[0] == "rm":
                allowed = args == self._remove_approved
            if args[0] == "kill":
                allowed = args == self._kill_approved
        if args == ("desktop", "stop", "--timeout", "20"):
            allowed = (
                self._stop_approved
                and self._monitor_joined
                and self.result.get("owned_cleanup") is True
            )
        if len(args) == 5 and args[:4] == ("ps", "-aq", "--no-trunc", "--filter"):
            allowed = args[-1].startswith("id=") and self._cid_allowed(args[-1][3:])
        need(allowed, "PG16_PUBLIC_CLI_SCOPE")
        if args == self._blueprint[0]:
            self._create_invoked = True
        if args[0] == "rm":
            self._remove_approved = None
        if args[0] == "kill":
            self._kill_approved = None
        if args[0] == "desktop":
            self._stop_approved = False
        self._cli_sequence += 1
        index = self._cli_sequence
        code, raw = await R["Host"].cli(
            self, label, *args, timeout=timeout, limit=limit, cleanup=cleanup
        )
        # Configuration replies can contain daemon proxy/plugin credentials.
        # Discard their raw bytes; only the validated projection may be persisted.
        prefix = "local-volume-cli-" if args == ("volume", "ls", "-q") else "local-cli-"
        discard = args[0] in ("version", "info")
        artifact = None if discard else prefix + str(index).zfill(3) + ".bin"
        if artifact is not None:
            self.write_new(artifact, raw, limit)
        self.save(
            "public-cli-manifest.json",
            [
                *getattr(self, "_reply_manifest", ()),
                {
                    "index": index,
                    "artifact": artifact,
                    "exit": code,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw),
                    "local_only": prefix.startswith("local-"),
                    "raw_disposition": "DISCARDED_CONFIGURATION" if discard else "LOCAL_ONLY",
                },
            ],
        )
        self._reply_manifest = json.loads((self.root / "public-cli-manifest.json").read_bytes())
        return code, raw

    async def run_own(self, *_args, **_kwargs):
        raise RuntimeError("PG16_PUBLIC_OLD_TRANSPORT_FORBIDDEN")

    def check_attestation(self, *_args, **_kwargs):
        raise RuntimeError("PG16_PUBLIC_INSTALL_FORBIDDEN")

    def watchdog(self):
        raise RuntimeError("PG16_PUBLIC_OLD_WATCHDOG_FORBIDDEN")

    def _metadata(self, prefix, value):
        self._evidence_sequence += 1
        self.write_new(
            prefix + "-" + str(self._evidence_sequence).zfill(3) + ".json",
            R["json_bytes"](value),
            65536,
        )

    async def _inventory_volumes(self, label, *, cleanup=False, timeout=3):
        code, raw = await self.cli(
            label, "volume", "ls", "-q", timeout=timeout, limit=65536, cleanup=cleanup
        )
        need(code == 0, "VOLUME_INVENTORY_EXIT")
        return self.pg["volumes"]["inventory"](raw)

    async def preflight(self):
        code, raw = await self.cli("version", "version", "--format", "{{json .}}")
        need(code == 0, "VERSION")
        version = self.profile["one"](b"[" + raw + b"]")
        projected = {}
        for side in ("Client", "Server"):
            if side == "Server" and version.get(side) is None:
                continue
            item = version.get(side)
            need(
                type(item) is dict
                and type(item.get("Version")) is str
                and re.fullmatch(
                    r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(?:[-+][A-Za-z0-9_.-]{1,32})?",
                    item["Version"],
                ),
                "VERSION",
            )
            projected[side] = {"Version": item["Version"]}
        self.save("version.json", projected)
        code, raw = await self.cli("info", "info", "--format", "{{json .}}")
        need(code == 0, "DAEMON")
        info = self.profile["one"](b"[" + raw + b"]")
        keys = (
            "OSType",
            "Architecture",
            "KernelVersion",
            "MemTotal",
            "Driver",
            "CgroupVersion",
            "ServerVersion",
        )
        public = {key: info[key] for key in keys}
        need(
            public["OSType"] == "linux"
            and public["Architecture"] in ("amd64", "x86_64")
            and public["CgroupVersion"] == "2"
            and public["KernelVersion"] == R["KERNEL"]
            and type(public["MemTotal"]) is int
            and public["MemTotal"] >= 2 * 1024**3,
            "DAEMON_PROFILE",
        )
        self.save("daemon.json", public)
        await self.empty_inventory("inventory-preflight")
        code, raw = await self.cli("pg16-image", "image", "inspect", self.profile["IMAGE"])
        need(code == 0, "IMAGE")
        image = self.profile["admit_image"](raw)
        need(self._initial_volumes is None and self._intent is None, "PREFLIGHT_REUSED")
        volumes = await self._inventory_volumes("volumes-initial")
        baseline_at = time.monotonic()
        # Local-only recovery datum, explicitly withheld by the future exporter.
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
        self._baseline_at = baseline_at
        self._intent = self.profile["Intent"](self.state["task"], image)
        need(self.profile["create_args"](self._intent) == self._blueprint, "CREATE_BLUEPRINT")

    async def checkpoint(self, action):
        if action == "B":
            need(
                self._store is not None
                and self._initial_volumes is not None
                and self._intent is not None,
                "SUPERVISION_REQUIRED",
            )
            self._store.arm_b(time.monotonic())
        return await super().checkpoint(action)

    def _publish(self, record, owner=None):
        if self._store is None:
            return
        need(self._initial_volumes is not None, "VOLUME_BASELINE_REQUIRED")
        if owner is not None:
            birth = self.pg["identity"]["capture"](owner._process)
            if birth is not None:
                old = self._births.get(CASE)
                need(old is None or old == birth, "CLI_IDENTITY_CHANGED")
                self._births[CASE] = birth
        birth = self._births.get(CASE)
        self._store.publish(
            self.pg["watch"]["Snapshot"](
                self.state["task"],
                CASE,
                self._intent.command,
                tuple(sorted(self._initial_volumes)),
                record["cid"],
                None if birth is None else birth.pid,
                None if birth is None else birth.filetime,
            )
        )

    async def create_own(self):
        need(
            self._intent is not None and self._initial_volumes is not None and not self.records,
            "CREATE_NOT_ADMITTED",
        )
        age = time.monotonic() - self._baseline_at
        need(0 <= age <= 30.0, "VOLUME_BASELINE_STALE")
        current = await self._inventory_volumes("volumes-before-create")
        need(current == self._initial_volumes, "VOLUME_BASELINE_CHANGED")
        need(0 <= time.monotonic() - self._baseline_at <= 30.0, "VOLUME_BASELINE_STALE")
        args, measure = self.profile["create_args"](self._intent)
        need(
            (args, measure) == self._blueprint and measure == self.state["create_measurement"],
            "CREATE_BLUEPRINT",
        )
        record = {
            "role": CASE,
            "name": self._intent.name,
            "image": self.profile["IMAGE"],
            "command": list(self._intent.command),
            "cid": None,
            "removed": False,
            "create_uncertain": True,
            "intent_persisted": False,
        }
        self.records.append(record)
        self.write_new("pg16-public-intent.json", R["json_bytes"](record))
        self.record_intents()
        record["intent_persisted"] = True
        self._publish(record)
        code, raw = await self.cli("create-pg16-public", *args, timeout=5)
        need(code == 0 and re.fullmatch(rb"[0-9a-f]{64}\s*", raw), "CREATE_EXIT")
        record.update(cid=raw.decode("ascii").strip(), create_uncertain=False)
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

    async def inspect_own(self, record, cleanup=False, timeout=3):
        need(self._cid_allowed(record["cid"]), "CID_REQUIRED")
        code, raw = await self.cli(
            "inspect-pg16-public",
            "inspect",
            "--type",
            "container",
            record["cid"],
            cleanup=cleanup,
            timeout=timeout,
        )
        need(code == 0, "INSPECT")
        info = self.profile["one"](raw)
        if cleanup:
            self.pg["policy"]["identity"](
                info, task=self.state["task"], command=self._intent.command, cid=record["cid"]
            )
        else:
            self.profile["validate_container"](info, self._intent, record["cid"])
        return info, raw

    async def start_supervision(self):
        self._loop = asyncio.get_running_loop()
        self._store = self.pg["watch"]["Store"](time.monotonic())
        self._cleanup_lock = threading.Lock()

        def request_abort():
            self._loop.call_soon_threadsafe(self._abort_foreground)

        self._monitor = self.pg["watch"]["Watchdog"](
            self.root,
            self._store,
            self._cleanup_lock,
            request_abort,
            self.pg_raw[SOURCES["emergency"][0]],
            self.pg_raw[SOURCES["policy"][0]],
            self.captured[R["LIBRARIES"]["bounded"][0]],
            self.pg_raw[SOURCES["identity"][0]],
            self.pg_raw[SOURCES["volumes"][0]],
        )
        self._heartbeat = self._task(self._pulse(), "maskgw-pg16-public-heartbeat")
        need(self._monitor.start(), "WATCHDOG_START")

    def _abort_foreground(self):
        self._monitor.ack.set()
        if self._foreground is not None and not self._foreground.done():
            self._foreground.cancel()

    async def _pulse(self):
        while not self._heartbeat_stop:
            self._store.pulse(time.monotonic())
            await asyncio.sleep(1.0)

    def _task(self, coroutine, name):
        task, failed = None, False
        try:
            task = asyncio.create_task(coroutine, name=name)
            self._host_tasks.append(task)
        except Exception:
            coroutine.close()
            failed = True
        if failed:
            raise RuntimeError("TASK_START") from None
        return task

    async def foreground(self, coroutine):
        if self._foreground is not None and not self._foreground.done():
            coroutine.close()
            raise RuntimeError("FOREGROUND_BUSY")
        self._foreground = self._task(coroutine, "maskgw-pg16-public-foreground")
        return await self._foreground

    async def _case(self):
        record = await self.create_own()
        owner = self.pg["owner"]["PublicProbeOwner"](
            self.channel["Target"](
                record["cid"],
                self.state["task"],
                self.profile["IMAGE"],
                self._intent.source_sha256,
                self.channel["Role"].PG,
            )
        )
        self._owners[CASE] = owner  # before spawn
        try:
            await owner.start()
        finally:
            self._publish(record, owner)  # synchronous birth capture on return/raise
        code, output = await owner.drain()
        raw = output.reveal()
        self.write_new("local-probe-output.bin", raw, 8192)
        facts = self.profile["parse_report"](raw, code, self._intent)
        self.write_new("pg16-public-report.json", R["json_bytes"](facts), 8192)
        info, _ = await self.inspect_own(record)
        state = info["State"]
        need(
            state["Running"] is False
            and type(state["Pid"]) is int
            and state["Pid"] == 0
            and state.get("OOMKilled") is False
            and state.get("Dead") is False
            and type(state.get("ExitCode")) is int
            and state["ExitCode"] == 0,
            "PROBE_STATE",
        )
        await self._collect(record)
        self._cases.append({"case": CASE, "owner": owner.metadata(), "removed": record["removed"]})
        self.save("cases.json", self._cases)
        self._store.publish(None)

    def _removal(self, record, info):
        decision = self.pg["volumes"]["removal"](self._initial_volumes, info.get("Mounts"))
        digest = self.pg["watch"]["volume_sha256"]
        self._metadata(
            "volume-decision",
            {
                "kind": "MASKGW_PG16_PUBLIC_VOLUME_DECISION_V1",
                "cid": record["cid"],
                "mode": decision.mode.value,
                "linked_count": len(decision.names),
                "linked_sha256": digest(decision.names),
                "preexisting_count": len(decision.preexisting),
                "preexisting_sha256": digest(decision.preexisting),
                "new_anonymous_names": [
                    name
                    for name in decision.names
                    if name not in self._initial_volumes and re.fullmatch(r"[0-9a-f]{64}", name)
                ],
            },
        )
        record["linked_volumes"] = decision.names  # memory-only, never ownership.json
        record["volume_uncertain"] = decision.mode is self.pg["volumes"]["Mode"].PRESERVE_UNCERTAIN
        args = (
            ("rm", "--volumes") if decision.mode is self.pg["volumes"]["Mode"].WITH_V else ("rm",)
        )
        self._remove_approved = (*args, record["cid"])
        return args

    def record_intents(self):
        self.save(
            "ownership.json",
            [
                {
                    key: value
                    for key, value in record.items()
                    if key not in ("command", "linked_volumes")
                }
                for record in self.records
            ],
        )

    async def _volume_final(self, *, cleanup=True, timeout=3):
        self.result["volumes_restored"] = False
        need(self._initial_volumes is not None, "VOLUME_BASELINE_REQUIRED")
        final = await self._inventory_volumes("volumes-final", cleanup=cleanup, timeout=timeout)
        delta = self.pg["volumes"]["difference"](self._initial_volumes, final)
        digest = self.pg["watch"]["volume_sha256"]
        restored = not delta.added and not delta.missing
        self._metadata(
            "volume-final",
            {
                "kind": "MASKGW_PG16_PUBLIC_VOLUME_FINAL_V1",
                "initial_count": len(self._initial_volumes),
                "initial_sha256": digest(self._initial_volumes),
                "final_count": len(final),
                "final_sha256": digest(final),
                "added_count": len(delta.added),
                "missing_count": len(delta.missing),
                "added_within_linked": set(delta.added)
                <= set().union(*(set(r.get("linked_volumes", ())) for r in self.records)),
                "restored": restored,
                "uncertain": any(r.get("volume_uncertain", False) for r in self.records),
            },
        )
        self.result["volumes_restored"] = restored
        need(restored, "VOLUME_INVENTORY_CHANGED")
        need(
            not any(r.get("volume_uncertain", False) for r in self.records),
            "VOLUME_OWNERSHIP_UNPROVEN",
        )

    async def _collect(self, record):
        owner = self._owners.get(CASE)
        ticket = None
        if owner is not None:
            for _ in range(2):
                ticket = await owner.quiesce()
                self._publish(record, owner)
                if ticket is not None:
                    break
            need(ticket is not None, "OWNER_HELD")
        end = time.monotonic() + 25.0
        lock_end = time.monotonic() + 1.0

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
            code, raw = await self.cli(
                "inspect-cleanup",
                "inspect",
                "--type",
                "container",
                record["cid"],
                timeout=remaining(3),
                cleanup=True,
            )
            if code == 0:
                info = self.profile["one"](raw)
                self.pg["policy"]["identity"](
                    info, task=self.state["task"], command=self._intent.command, cid=record["cid"]
                )
                if info["State"]["Running"] is True:
                    self._kill_approved = ("kill", "--signal", "KILL", record["cid"])
                    code, _ = await self.cli(
                        "kill-pg16-public",
                        "kill",
                        "--signal",
                        "KILL",
                        record["cid"],
                        timeout=remaining(4),
                        cleanup=True,
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
                    "rm-pg16-public", *args, record["cid"], timeout=remaining(8), cleanup=True
                )
                need(code == 0 and raw.strip() == record["cid"].encode("ascii"), "REMOVE")
            code, raw = await self.cli(
                "absent-after-pg16-public",
                "ps",
                "-aq",
                "--no-trunc",
                "--filter",
                "id=" + record["cid"],
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
        finally:
            self._cleanup_lock.release()

    async def perform_b(self):
        need(self.cycle.phase is self.libs["core"]["Phase"].B_CONSUMED, "B_REQUIRED")
        async with asyncio.timeout(90.0):
            self.pins()
            await self.foreground(self._case())
        self.result["pg16_public_verified"] = True

    async def cleanup_owned(self):
        clean = True
        for record in self.records:
            owner = self._owners.get(CASE)
            if (
                record["removed"]
                and (owner is None or owner.metadata()["released"])
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
        self.result["owned_cleanup"] = False
        if clean:
            await self.empty_inventory("inventory-final", cleanup=True)
            self.result["inventory_restored"] = True
            # If preflight failed before any create, no volume mutation was permitted.
            if self._initial_volumes is not None:
                await self._volume_final()
            else:
                need(not self.records, "VOLUME_BASELINE_REQUIRED")
            self.result["owned_cleanup"] = True
        self.record_intents()

    async def stop_supervision(self):
        if self._monitor is None:
            return
        self._monitor_joined = self._monitor.close()
        self.result["watchdog"] = (
            self._monitor.metadata()
            if self._monitor_joined
            else {"held": True, "category": "THREAD_JOIN_UNPROVEN"}
        )
        self._heartbeat_stop = True
        if self._heartbeat is not None:
            await self._heartbeat

    async def restore_desktop(self):
        # The entry must join the monitor first. Reconcile volumes again before stop.
        need(self._monitor_joined and self.result.get("owned_cleanup") is True, "RESTORE_UNPROVEN")
        if self._initial_volumes is not None:
            await self._volume_final()
        self._stop_approved = True
        try:
            await super().restore_desktop()
        finally:
            self._stop_approved = False

    def assert_released(self):
        need(self.result.get("owned_cleanup") is True and self._monitor_joined, "HOST_HELD")
        need(self._heartbeat is None or self._heartbeat.done(), "HOST_HELD")
        need(self._foreground is None or self._foreground.done(), "HOST_HELD")
        need(all(task.done() for task in self._host_tasks), "HOST_HELD")
        for owner in self._owners.values():
            owner.assert_released()
