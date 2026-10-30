"""T4 binding on frozen coordinator definitions. NO main, root creation or effects on import."""

import asyncio
import hashlib
import json
from pathlib import Path
import re
import sys
import time

REPO = Path(__file__).resolve().parents[2]
V2_SHA = "b59388f52a38319c19c2c60b25100347d319a59c2778395cc68bea64d2bc0c37"
SOURCES = {
    "channel": (
        "docs/poc/w1_bootstrap_channel.py",
        "e6ca9e606567289fa312049b071aa777e1764579813829747cb32df05d4ee87a",
    ),
    "policy": (
        "docs/poc/w1_bootstrap_probe.py",
        "e3cf9f4d5b6150c4c3d975fd17d6296348fa14b9e22a43543c9913d34361afd4",
    ),
    "identity": (
        "docs/poc/w1_bootstrap_identity.py",
        "dc2481f5a54c1408f6c91c38f99c138d82431b5b1324afdfe9443087323b140d",
    ),
    "emergency": (
        "docs/poc/w1_bootstrap_emergency.py",
        "2fdc0084f4bf91ad0186779867353d2dfe4ff5943c54d973b4913ec8b12ed2d3",
    ),
    "watch": (
        "docs/poc/w1_bootstrap_watchdog.py",
        "3e98cd31308545fab264c67173c5b5ecc33c11daca5aabc1ba1757b0921f51a5",
    ),
}
IMAGE_RECORD = "docs/poc/evidence/oracle9-w1-v2-run-20261027/candidate-image.json"
IMAGE_RECORD_SHA = "c224641de98420e4308d528aca45bd5d03f34124b90cb6651e8a6db3d9747653"


def need(value, category):
    if not value:
        raise RuntimeError(category) from None


def captured(relative, digest):
    path = REPO / relative
    info = path.lstat()
    need(
        path.is_file()
        and not getattr(info, "st_file_attributes", 0) & 0x400
        and info.st_size <= 65536,
        "SOURCE",
    )
    raw = path.read_bytes()
    need(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == digest, "SOURCE_PIN")
    namespace = {"__name__": "_t4_frozen_definitions", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace, raw


V2, V2_RAW = captured("docs/poc/oracle9_w1_run_v2.py", V2_SHA)
R = V2["R"]
BaseHost = V2["Host"]


class Host(BaseHost):
    def __init__(self, root, state):
        super().__init__(root, state)
        self.t4, self.t4_raw = {}, {}
        for key, (relative, digest) in SOURCES.items():
            self.t4[key], self.t4_raw[relative] = captured(relative, digest)
        self._entry_raw = R["pinned"](Path(__file__), state["host_sha256"])
        self._intents = {
            case.value: self.t4["policy"]["Intent"](state["task"], case)
            for case in self.t4["policy"]["Case"]
        }
        self._owners, self._births = {}, {}
        self._store, self._monitor, self._cleanup_lock = None, None, None
        self._loop, self._foreground, self._heartbeat = None, None, None
        self._heartbeat_stop = False
        self._monitor_joined = False
        self._cases = []
        self._host_tasks = []

    def pins(self, cleanup=False):
        # Captured source integrity survives live-file changes during cleanup.
        need(hashlib.sha256(V2_RAW).hexdigest() == V2_SHA, "V2_CAPTURE")
        if not cleanup:
            R["pinned"](REPO / "docs/poc/oracle9_w1_run_v2.py", V2_SHA)
        for relative, raw in self.captured.items():
            need(hashlib.sha256(raw).hexdigest() == self.state["pins"][relative], "CAPTURE")
            if not cleanup:
                R["pinned"](REPO / relative, self.state["pins"][relative])
        for key, (relative, digest) in SOURCES.items():
            need(hashlib.sha256(self.t4_raw[relative]).hexdigest() == digest, "CAPTURE")
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

    async def cli(self, label, *args, timeout=3, limit=2097152, cleanup=False):
        need(
            args
            and args[0]
            in ("version", "info", "ps", "inspect", "create", "kill", "rm", "desktop", "image"),
            "CLI_SCOPE",
        )
        need(not label.startswith(("commit", "copy")), "CLI_SCOPE")
        need(args[0] != "image" or args[1:2] == ("inspect",), "CLI_SCOPE")
        need(args[0] != "desktop" or args == ("desktop", "stop", "--timeout", "20"), "CLI_SCOPE")
        return await R["Host"].cli(
            self, label, *args, timeout=timeout, limit=limit, cleanup=cleanup
        )

    async def run_own(self, *_args, **_kwargs):
        raise RuntimeError("T4_OLD_TRANSPORT_FORBIDDEN")

    def check_attestation(self, *_args, **_kwargs):
        raise RuntimeError("T4_INSTALL_FORBIDDEN")

    def watchdog(self):
        raise RuntimeError("T4_OLD_WATCHDOG_FORBIDDEN")

    async def preflight(self):
        code, raw = await self.cli("version", "version", "--format", "{{json .}}")
        need(code == 0 and type(json.loads(raw)) is dict, "VERSION")
        self.save("version.json", json.loads(raw))
        code, raw = await self.cli("info", "info", "--format", "{{json .}}")
        need(code == 0, "DAEMON")
        info = json.loads(raw)
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
        expected = json.loads(R["pinned"](REPO / IMAGE_RECORD, IMAGE_RECORD_SHA))[0]
        code, raw = await self.cli("t4-image", "image", "inspect", self.t4["policy"]["IMAGE"])
        need(code == 0, "IMAGE")
        values = json.loads(raw)
        need(type(values) is list and len(values) == 1, "IMAGE")
        current = values[0]
        need(
            all(
                current[key] == expected[key]
                for key in ("Id", "Os", "Architecture", "Config", "RootFS")
            ),
            "IMAGE_EXACT",
        )
        self.base = current
        self.save("candidate-image.json", current)

    async def checkpoint(self, action):
        if action == "B":
            need(self._store is not None, "SUPERVISION_REQUIRED")
            self._store.arm_b(time.monotonic())  # conservative, before B is consumed
        return await super().checkpoint(action)

    def _publish(self, record, owner=None):
        if self._store is None:
            return
        if owner is not None:
            birth = self.t4["identity"]["capture"](owner._process)
            if birth is not None:
                old = self._births.get(record["role"])
                need(old is None or old == birth, "CLI_IDENTITY_CHANGED")
                self._births[record["role"]] = birth
        birth = self._births.get(record["role"])
        self._store.publish(
            self.t4["watch"]["Snapshot"](
                self.state["task"],
                record["role"],
                self._intents[record["role"]].command,
                record["cid"],
                None if birth is None else birth.pid,
                None if birth is None else birth.filetime,
            )
        )

    async def create_own(self, case):
        policy = self.t4["policy"]
        intent = self._intents[case.value]
        args, measure = policy["create_args"](str(R["CLI"]), intent)
        need(measure == self.state["create_measurements"][case.value], "CREATE_MEASUREMENT")
        record = {
            "role": case.value,
            "name": policy["name_for"](intent.task, case),
            "image": policy["IMAGE"],
            "command": list(intent.command),
            "cid": None,
            "removed": False,
            "create_uncertain": True,
        }
        self.records.append(record)
        self.write_new(case.value + "-intent.json", R["json_bytes"](dict(record)))
        self.record_intents()
        self._publish(record)
        code, raw = await self.cli("create-" + case.value, *args, timeout=5)
        need(code == 0 and re.fullmatch(rb"[0-9a-f]{64}\s*", raw), "CREATE_EXIT")
        record.update(cid=raw.decode("ascii").strip(), create_uncertain=False)
        self.record_intents()
        self._publish(record)
        info, raw = await self.inspect_own(record)
        need(info["State"]["Running"] is False and info["State"]["Pid"] == 0, "CREATE_RUNNING")
        self.write_new(case.value + "-inspect-before.json", raw)
        return record

    async def inspect_own(self, record, cleanup=False, timeout=3):
        need(record["cid"] is not None, "CID_REQUIRED")
        code, raw = await self.cli(
            "inspect-" + record["role"],
            "inspect",
            "--type",
            "container",
            record["cid"],
            cleanup=cleanup,
            timeout=timeout,
        )
        need(code == 0, "INSPECT")
        return self._owned_inspect(record, raw, cleanup), raw

    def _owned_inspect(self, record, raw, cleanup):
        values = json.loads(raw)
        need(type(values) is list and len(values) == 1, "INSPECT_SHAPE")
        validator = self.t4["policy"]["identity" if cleanup else "validate_container"]
        need(validator(values[0], self._intents[record["role"]]) == record["cid"], "CID_CHANGED")
        return values[0]

    async def start_supervision(self):
        import threading

        self._loop = asyncio.get_running_loop()
        self._store = self.t4["watch"]["Store"](time.monotonic())
        self._cleanup_lock = threading.Lock()

        def request_abort():
            self._loop.call_soon_threadsafe(self._abort_foreground)

        self._monitor = self.t4["watch"]["Watchdog"](
            self.root,
            self._store,
            self._cleanup_lock,
            request_abort,
            self.t4_raw[SOURCES["emergency"][0]],
            self.t4_raw[SOURCES["policy"][0]],
            self.captured[R["LIBRARIES"]["bounded"][0]],
            self.t4_raw[SOURCES["identity"][0]],
        )
        self._heartbeat = self._task(self._pulse(), "maskgw-t4-heartbeat")
        need(self._monitor.start(), "WATCHDOG_START")

    def _abort_foreground(self):
        self._monitor.ack.set()  # informative, does not cancel external cleanup
        if self._foreground is not None and not self._foreground.done():
            self._foreground.cancel()

    async def _pulse(self):
        while not self._heartbeat_stop:
            self._store.pulse(time.monotonic())
            await asyncio.sleep(1.0)

    async def foreground(self, coroutine):
        if self._foreground is not None and not self._foreground.done():
            coroutine.close()
            raise RuntimeError("FOREGROUND_BUSY")
        self._foreground = self._task(coroutine, "maskgw-t4-foreground")
        return await self._foreground

    def _task(self, coroutine, name):
        failed = False
        task = None
        try:
            task = asyncio.create_task(coroutine, name=name)
            self._host_tasks.append(task)
        except Exception:
            coroutine.close()
            failed = True
        if failed:
            raise RuntimeError("TASK_START") from None
        return task

    async def _case(self, case):
        channel = self.t4["channel"]
        record = await self.create_own(case)
        role = channel["Role"].PG if case.value == "retain" else channel["Role"].CONTROLLER
        owner = channel["ManagedBootstrap"](
            channel["Target"](
                record["cid"],
                self.state["task"],
                record["image"],
                self.t4["policy"]["SOURCE_SHA"],
                role,
            )
        )
        self._owners[case.value] = owner  # before start/spawn
        if case.value == "cancel-start":
            task = self._task(owner.start(), "maskgw-t4-cancel-start")
            try:
                await asyncio.sleep(0)
                need("spawn" in owner._tasks, "SPAWN_NOT_REGISTERED")
                task.cancel()
                await task
            except asyncio.CancelledError:
                if asyncio.current_task().cancelling():
                    raise
            finally:
                self._publish(record, owner)
            need(owner.metadata()["seed_delivery"] == "NOT_SENT", "UNEXPECTED_SEND")
        else:
            try:
                await owner.start()
            finally:
                self._publish(record, owner)  # synchronous immediately after start returns/raises
            if case.value == "bad-ready":
                category = None
                try:
                    await owner.await_ready()
                except channel["BootstrapError"] as error:
                    category = error.category.value
                need(
                    category == "READY" and owner.metadata()["seed_delivery"] == "NOT_SENT",
                    "READY_ORACLE",
                )
            else:
                await owner.await_ready()
                category = None
                try:
                    await owner.send_seed(channel["Seed"](role, self.t4["policy"]["public_body"]()))
                except channel["BootstrapError"] as error:
                    category = error.category.value
                if case.value == "blackhole":
                    need(
                        (category is None and owner.metadata()["seed_delivery"] == "SENT")
                        or (
                            category == "DEADLINE"
                            and owner.metadata()["seed_delivery"] == "UNKNOWN"
                        ),
                        "BLACKHOLE_ORACLE",
                    )
                elif case.value == "flood":
                    if category is None:
                        # Pump already drains/discards. This producer never exits;
                        # drain() would wait for EOF/process exit before raising.
                        async with asyncio.timeout(2.0):
                            while owner.fault is None:
                                await asyncio.sleep(0.01)
                        category = owner.fault.value
                    need(
                        category == "STDOUT_LIMIT"
                        and owner.metadata()["retained_stdout_bytes"] == 0,
                        "OUTPUT_ORACLE",
                    )
                else:
                    need(category is None, "SEND_FAILED")
                    if case.value == "retain":
                        owner.retain()
                        task = self._task(owner.drain(), "maskgw-t4-passive-drain")
                        try:
                            await asyncio.sleep(0.1)
                            task.cancel()
                            await task
                        except asyncio.CancelledError:
                            if asyncio.current_task().cancelling():
                                raise
                    else:
                        async with asyncio.timeout(4.0):
                            output = await owner.drain()
                        result = self.t4["policy"]["report"](output.reveal(), case)
                        self.write_new(case.value + "-report.json", R["json_bytes"](result))
        await self._collect(record, oracle=True)
        self._cases.append(
            {"case": case.value, "owner": owner.metadata(), "removed": record["removed"]}
        )
        self.save("cases.json", self._cases)
        self._store.publish(None)

    async def _collect(self, record, *, oracle=False):
        owner = self._owners.get(record["role"])
        ticket = None
        if owner is not None:
            for _ in range(2):
                ticket = await owner.quiesce()
                self._publish(record, owner)
                if ticket is not None:
                    break
            need(ticket is not None, "OWNER_HELD")
        end = time.monotonic() + 22.0
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
                "inspect-cleanup-" + record["role"],
                "inspect",
                "--type",
                "container",
                record["cid"],
                timeout=remaining(3),
                cleanup=True,
            )
            if oracle and record["role"] == "retain":
                need(code == 0, "CLI_KILL_DID_NOT_LEAVE_CID_ALIVE")
            if code == 0:
                info = self._owned_inspect(record, raw, True)
                if oracle and record["role"] == "retain":
                    need(info["State"]["Running"] is True, "CLI_KILL_DID_NOT_LEAVE_CID_ALIVE")
                    self.write_new("retain-cli-reaped-cid-alive.json", raw)
                if info["State"]["Running"] is True:
                    code, _ = await self.cli(
                        "kill-" + record["role"],
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
                code, _ = await self.cli(
                    "rm-" + record["role"], "rm", record["cid"], timeout=remaining(8), cleanup=True
                )
                need(code == 0, "REMOVE")
            # Even a failed inspect is never absence. Only this fresh, successful
            # post-ticket CID inventory can authorize close (also after emergency).
            code, raw = await self.cli(
                "absent-after-" + record["role"],
                "ps",
                "-aq",
                "--no-trunc",
                "--filter",
                "id=" + record["cid"],
                timeout=remaining(3),
                cleanup=True,
            )
            need(code == 0 and not raw.strip(), "ABSENCE")
            need(time.monotonic() <= end, "CLEANUP_DEADLINE")
            record["removed"] = True
            self.record_intents()
            if owner is not None:
                need(
                    await owner.close(self.t4["channel"]["Absent"](ticket, time.monotonic())),
                    "OWNER_HELD",
                )
                owner.assert_released()
        finally:
            self._cleanup_lock.release()

    async def perform_b(self):
        need(self.cycle.phase is self.libs["core"]["Phase"].B_CONSUMED, "B_REQUIRED")
        async with asyncio.timeout(414.0):
            for case in self.t4["policy"]["Case"]:
                self.pins()
                async with asyncio.timeout(56.0):
                    await self.foreground(self._case(case))
        self.result["t4_verified"] = True

    async def cleanup_owned(self):
        clean = True
        for record in reversed(self.records):
            owner = self._owners.get(record["role"])
            if record["removed"] and (owner is None or owner.metadata()["released"]):
                continue
            if record["create_uncertain"] or record["cid"] is None:
                clean = False  # never infer a completed create from transient name/global absence
                record["cleanup_unproven"] = True
                continue
            try:
                await self._collect(record)
            except Exception:
                clean = False
                record["cleanup_unproven"] = True
        clean = clean and not any(row.get("exit") is None for row in self.commands)
        self.result["owned_cleanup"] = clean
        if clean:
            await self.empty_inventory("inventory-final", cleanup=True)
            self.result["inventory_restored"] = True
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

    def assert_released(self):
        need(self.result.get("owned_cleanup") is True and self._monitor_joined, "HOST_HELD")
        need(self._heartbeat is None or self._heartbeat.done(), "HOST_HELD")
        need(self._foreground is None or self._foreground.done(), "HOST_HELD")
        need(all(task.done() for task in self._host_tasks), "HOST_HELD")
        for owner in self._owners.values():
            owner.assert_released()
