"""Specific, one-attempt W1 coordinator. No effects on import.

The reviewed pure builders remain frozen in oracle9_w1_prepare.py. This
Implements Desktop lifecycle/freshness and one app-only install/probe.
Tests replace concrete methods; there is no user command/backend interface.
"""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time

REPO = Path(__file__).resolve().parents[2]
HOME = Path("C:/Users/w.filho")
CLI = HOME / "AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"
DESKTOP = CLI.parents[2] / "Docker Desktop.exe"
SHELL = Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
META = (
    HOME
    / ".docker/contexts/meta/fe9c6bd7a66301f49ca9b6a70b217107cd1284598bfc254700c989b916da791e/meta.json"
)
CONTEXT_ROOT = (
    HOME / "AppData/Local/Temp/maskgw-oracle9-w1-context-20261027-35fdbf68fbf04dc4a849c7d4392db0b2"
)
KERNEL = "6.18.54.1-microsoft-standard-WSL2"
RUN_TIMEOUT_SECONDS = 300
WATCHDOG_SECONDS = 600
LIBRARIES = {
    "builders": (
        "docs/poc/oracle9_w1_prepare.py",
        "7540b7bff5072013cb26613878760cb68e61c3269ab9a842a43c630ead1040cc",
    ),
    "foundation": (
        "docs/poc/oracle9_python_prepare.py",
        "0b0bb1719834bdc9ccaa4a2ffd4c8da23824d92320e05bf1218af734d2ede1b5",
    ),
    "bounded": (
        "docs/poc/run_linux_as_probe.py",
        "58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627",
    ),
    "context": (
        "docs/poc/oracle9_w1_context.py",
        "94cfa9118625d175a67a398bb2c416b5ca392e7a3b458cc433dc63fa02c75d78",
    ),
    "clock": (
        "docs/poc/oracle9_clock_sample.py",
        "6bcbdbe5b9345a5d70e408e1988226ad300d4e57d64eb6beec1d4d7cd55a692d",
    ),
    "core": (
        "docs/poc/oracle9_cycle_freshness.py",
        "d2b485c29d2cef36599af51fc342ac39a991f9564bb919baa18d3cb1ff7e5b66",
    ),
}
EXTERNAL_PINS = {
    CLI: "60028870931ea6e91955bfeaee358ec6c6920f6162c17a3d828c3c82ab3c3599",
    DESKTOP: "f3100322884b025ead78c49b512ece5e8c1f444ea91c57a4e045cc409386a3de",
    SHELL: "60c9b29843624dd8af6b6a7b26147753be6aeef65098b9a503cc50850afe410f",
    HOME
    / ".docker/config.json": "f173396ef80b3c0bf4f8a5f6f944d3e426cee041ae3a2a8a07602ff6846a9f1a",
    META: "c16649b1a2f1c6fbb68b85158a956862331e86543e25df46341f5fe5df2f9a25",
}
APP_ENV_KEYS = (
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
    "ComSpec",
    "SystemDrive",
    "ProgramFiles(x86)",
    "ProgramW6432",
    "CommonProgramFiles",
    "CommonProgramFiles(x86)",
    "CommonProgramW6432",
    "ALLUSERSPROFILE",
    "PUBLIC",
    "USERNAME",
    "USERDOMAIN",
    "USERDOMAIN_ROAMINGPROFILE",
    "COMPUTERNAME",
    "LOGONSERVER",
    "OS",
    "PROCESSOR_ARCHITECTURE",
    "PROCESSOR_IDENTIFIER",
    "PROCESSOR_LEVEL",
    "PROCESSOR_REVISION",
    "NUMBER_OF_PROCESSORS",
    "SESSIONNAME",
)
PROCESS_COMMAND = (
    "$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';"
    "$rows=@(Get-Process -ErrorAction SilentlyContinue|"
    "Where-Object {$_.ProcessName -match '^(Docker Desktop|com\\.docker\\..*|docker.*|vpnkit)$'}|"
    "Sort-Object Id|ForEach-Object {"
    "[pscustomobject]@{pid=$_.Id;name=$_.ProcessName;"
    "created=$_.StartTime.ToUniversalTime().ToFileTimeUtc().ToString([Globalization.CultureInfo]::InvariantCulture)}});"
    "[Console]::Out.Write((ConvertTo-Json -InputObject $rows -Compress))"
)
START_COMMAND = (
    "$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';"
    "$allowed=@(" + ",".join(repr(key) for key in APP_ENV_KEYS) + ");"
    "foreach($e in [Environment]::GetEnvironmentVariables('Process').GetEnumerator()){"
    "if($e.Key -notin $allowed){[Environment]::SetEnvironmentVariable($e.Key,$null,'Process')}};"
    "$keys=@([Environment]::GetEnvironmentVariables('Process').Keys|Sort-Object);"
    "$p=Start-Process -FilePath '" + str(DESKTOP) + "' -WindowStyle Hidden -PassThru;"
    "[Console]::Out.Write((ConvertTo-Json -Compress -InputObject "
    "([pscustomobject]@{environment_keys=$keys;identity=[pscustomobject]@{pid=$p.Id;name='Docker Desktop';"
    "created=$p.StartTime.ToUniversalTime().ToFileTimeUtc().ToString([Globalization.CultureInfo]::InvariantCulture)}})))"
)


def need(value, reason):
    if not value:
        raise RuntimeError(reason)


def regular(path, maximum):
    info = path.lstat()
    need(
        stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "REGULAR"
    )
    need(0 <= info.st_size <= maximum, "FILE_SIZE")
    raw = path.read_bytes()
    need(len(raw) == info.st_size, "FILE_CHANGED")
    return raw


def pinned(path, expected, maximum=65536):
    raw = regular(path, maximum)
    need(hashlib.sha256(raw).hexdigest() == expected, "PIN")
    return raw


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def desktop_environment():
    return {key: os.environ[key] for key in APP_ENV_KEYS if key in os.environ}


def start_result(value):
    need(type(value) is dict and set(value) == {"identity", "environment_keys"}, "START_SHAPE")
    keys = value["environment_keys"]
    need(type(keys) is list and all(type(key) is str for key in keys), "START_ENV")
    folded = [key.casefold() for key in keys]
    need(
        len(set(folded)) == len(folded) and set(folded) <= {key.casefold() for key in APP_ENV_KEYS},
        "START_ENV",
    )
    return process_row(value["identity"]), keys


def process_row(value):
    need(type(value) is dict and set(value) == {"pid", "name", "created"}, "APP_SHAPE")
    need(type(value["pid"]) is int and 0 < value["pid"] <= 0xFFFFFFFF, "APP_PID")
    need(
        type(value["name"]) is str
        and re.fullmatch(r"Docker Desktop|com\.docker\..*|docker.*|vpnkit", value["name"]),
        "APP_NAME",
    )
    need(
        type(value["created"]) is str and re.fullmatch(r"[1-9][0-9]{0,18}", value["created"]),
        "APP_CREATED",
    )
    need(int(value["created"]) < 1 << 63, "APP_CREATED")
    return dict(value)


class Host:
    def __init__(self, root, state):
        self.root, self.state = root, state
        self.libs, self.captured = {}, {}
        for name, (relative, expected) in LIBRARIES.items():
            raw = pinned(REPO / relative, expected)
            need(state["pins"][relative] == expected, "CAPTURE_PIN")
            ns = {"__name__": "_w1_run_" + name, "__file__": str(REPO / relative)}
            exec(compile(raw, str(REPO / relative), "exec"), ns)
            self.libs[name], self.captured[relative] = ns, raw
        self.old_policy, self.policy, _ = self.libs["builders"]["policy_pair"]()
        self.cycle, self.started, self.base = None, None, None
        self.initial_active = None
        self.commands, self.process_observations = [], []
        self.result = {
            "outcome": "NOT_PASSED",
            "desktop_restored": False,
            "inventory_restored": False,
        }
        self.tag = "maskgw-oracle9-w1-candidate:" + state["task"]
        self.records = []
        self.candidate = None
        self.commit_intended = False
        self.commit_id = None
        self.active_lock = threading.Lock()
        self.active = None
        self.stop = threading.Event()
        self.fired = threading.Event()
        self.watchdog_failed = False
        self.watchdog_thread = None

    def save(self, name, value):
        raw = json_bytes(value)
        need(len(raw) <= 4 * 1024 * 1024, "EVIDENCE_SIZE")
        path = self.root / name
        temporary = path.with_suffix(path.suffix + ".next")
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)

    def pins(self, cleanup=False):
        for relative, captured in self.captured.items():
            expected = self.state["pins"][relative]
            need(hashlib.sha256(captured).hexdigest() == expected, "CAPTURE_PIN")
            pinned(REPO / relative, expected)
        pinned(Path(__file__), self.state["program_sha256"])
        for path, expected in EXTERNAL_PINS.items():
            pinned(path, expected, 128 * 1024 * 1024)
        need(
            json.loads(regular(META, 16384))["Endpoints"]["docker"]["Host"]
            in (
                "npipe:////./pipe/dockerDesktopLinuxEngine",
                "npipe://./pipe/dockerDesktopLinuxEngine",
            ),
            "ENDPOINT",
        )
        if not cleanup:
            context = self.libs["context"]
            raw = pinned(
                CONTEXT_ROOT / "context/manifest.json",
                self.libs["builders"]["MANIFEST_SHA"],
                1024 * 1024,
            )
            context["check_context"](CONTEXT_ROOT / "context", raw)
            context["sources"]()
            pinned(REPO / "deploy/oracle9_w1_update.py", self.libs["builders"]["PAYLOAD_SHA"])

    async def invoke(
        self, label, args, timeout, limit, *, cleanup=False, public_clock=False, app_start=False
    ):
        self.pins(cleanup=cleanup)
        helper = self.libs["bounded"]
        if public_clock or app_start:
            # Separate globals: the watchdog never observes this temporary env.
            raw = self.captured[LIBRARIES["bounded"][0]]
            helper = {"__name__": "_w1_public_ps", "__file__": str(REPO / LIBRARIES["bounded"][0])}
            exec(compile(raw, helper["__file__"], "exec"), helper)
            helper["environment"] = (
                desktop_environment if app_start else self.libs["clock"]["environment"]
            )
        start = time.monotonic()
        try:
            code, raw = await helper["bounded"](args, timeout=timeout, limit=limit)
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

    async def cli(self, label, *args, timeout=10, limit=2 * 1024 * 1024, cleanup=False):
        return await self.invoke(
            label, [str(CLI), "--context", "desktop-linux", *args], timeout, limit, cleanup=cleanup
        )

    async def powershell(self, label, command, timeout=3, cleanup=False, start=False):
        code, raw = await self.invoke(
            label,
            [str(SHELL), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
            timeout,
            65536,
            cleanup=cleanup,
            public_clock=not start,
            app_start=start,
        )
        need(code == 0, "APP_EXIT")
        return json.loads(raw)

    async def processes(self, label, cleanup=False):
        rows = await self.powershell(label, PROCESS_COMMAND, cleanup=cleanup)
        need(type(rows) is list and len(rows) <= 128, "APP_SHAPE")
        values = [process_row(row) for row in rows]
        need(len({v["pid"] for v in values}) == len(values), "APP_DUPLICATE")
        self.process_observations.append({"label": label, "processes": values})
        self.save("processes.json", self.process_observations)
        return values

    async def sample(self):
        self.pins(cleanup=True)
        value = await self.libs["clock"]["sample"]()
        need(value["kind"] == "maskgw-windows-cycle-clock-v1", "CLOCK_KIND")
        return self.libs["core"]["Sample"](value["boot"], value["tick_ms"], value["utc_100ns"])

    async def check_app(self, label, cleanup=False):
        rows = await self.processes(label, cleanup=cleanup)
        need(bool(rows), "APP_DISAPPEARED")
        if self.started is not None:
            need(self.started in rows, "APP_IDENTITY")
        return rows

    async def checkpoint(self, action):
        await self.check_app(action)
        sample = await self.sample()
        core = self.libs["core"]
        admission = core["advance"](self.cycle, sample, action)
        self.cycle = admission.state
        self.save("cycle.json", json.loads(core["encode"](self.cycle)))
        if admission.decision != core["Decision"].ACCEPT:
            self.save(
                "rejected-sample.json",
                {
                    "action": action,
                    "sample": core["_sample_map"](sample),
                    "reason": admission.reason.value,
                },
            )
            raise RuntimeError("CYCLE_REFUSED")

    async def wait_observation(self):
        tick = self.libs["clock"]["_bindings"]()[0]
        delta = tick - int(self.cycle.last.tick_ms)
        need(0 <= delta <= 30000, "WAIT_CLOCK")
        if delta < 10000:
            await asyncio.sleep((10000 - delta) / 1000)

    async def empty_inventory(self, label, *, timeout=3, cleanup=False):
        code, raw = await self.cli(
            label, "ps", "-aq", "--no-trunc", timeout=timeout, cleanup=cleanup
        )
        need(code == 0 and not raw.strip(), "INVENTORY")

    async def preflight(self):
        code, raw = await self.cli("version", "version", "--format", "{{json .}}", timeout=3)
        need(code == 0 and type(json.loads(raw)) is dict, "VERSION")
        self.save("version.json", json.loads(raw))
        code, raw = await self.cli("info", "info", "--format", "{{json .}}", timeout=3)
        need(code == 0, "DAEMON_EXIT")
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
        self.save("daemon.json", public)
        need(
            public["OSType"] == "linux"
            and public["Architecture"] in ("amd64", "x86_64")
            and public["CgroupVersion"] == "2"
            and type(public["MemTotal"]) is int
            and public["MemTotal"] >= 2 * 1024**3
            and public["KernelVersion"] == KERNEL,
            "DAEMON_PROFILE",
        )
        await self.empty_inventory("inventory-preflight")
        code, raw = await self.cli(
            "base-image", "image", "inspect", self.libs["builders"]["IMAGE"], timeout=3
        )
        need(code == 0, "BASE_IMAGE")
        values = json.loads(raw)
        need(type(values) is list and len(values) == 1, "BASE_SHAPE")
        expected = {
            "Entrypoint": self.libs["foundation"]["ENTRY"],
            "Env": self.libs["foundation"]["ENV"],
            "Healthcheck": {"Test": ["NONE"]},
            "User": "10001:10001",
            "WorkingDir": "/var/empty",
            "Labels": {
                "desktop.docker.io/ports.scheme": "v2",
                "maskgw.task": self.libs["builders"]["OLD_TASK"],
                "maskgw.source-sha256": "ee2becec0e6683807827e3682a410497f94a24d7509d6670cd88b50654d4c5af",
                "maskgw.manifest-sha256": "359a055ccbd7689dce453f7979f5d0ac137cd5963f599d462400abe7f1d87c22",
            },
        }
        need(values[0]["Config"] == expected, "BASE_CONFIG_EXACT")
        self.libs["builders"]["validate_base"](values[0], self.old_policy, self.libs["foundation"])
        self.base = values[0]
        self.save("base-image.json", self.base)
        code, raw = await self.cli(
            "tag-free",
            "image",
            "ls",
            "--no-trunc",
            "--format",
            "{{.Repository}}:{{.Tag}}",
            self.tag,
            timeout=3,
        )
        need(code == 0 and not raw.strip(), "TAG_EXISTS")

    async def start_cycle(self):
        self.pins()
        self.cycle = self.libs["core"]["start"](await self.sample())
        self.save("cycle.json", json.loads(self.libs["core"]["encode"](self.cycle)))
        rows = await self.processes("initial")
        self.initial_active = bool(rows)
        self.save(
            "desktop.json",
            {
                "initial_active": self.initial_active,
                "phase": "PRESERVED" if rows else "START_RESERVED",
            },
        )
        if not rows:
            value = await self.powershell("start-hidden", START_COMMAND, start=True)
            self.started, keys = start_result(value)
            self.save("start-environment-keys.json", keys)
            need(self.started["name"] == "Docker Desktop", "START_IDENTITY")
            self.save(
                "desktop.json",
                {"initial_active": False, "phase": "STARTED", "identity": self.started},
            )
        for index in range(1, 10):
            if index == 9:
                await self.preflight()  # H1: after O8, BEFORE O9
            await self.wait_observation()
            await self.checkpoint("OBSERVE")
            print(json.dumps({"phase": "OBSERVE", "count": index}), flush=True)
        await self.empty_inventory("inventory-ready")
        await self.checkpoint("READY")
        await self.checkpoint("B")  # B_CONSUMED is durably saved before any B effect

    async def restore_desktop(self):
        try:
            if self.initial_active is True:
                await self.check_app("preserved-after", cleanup=True)
                self.result["desktop_restored"] = True
                self.result["desktop_state"] = "PRESERVED_ACTIVE"
                return
            if self.started is None:
                need(self.initial_active is False, "INITIAL_UNKNOWN")
                need(not await self.processes("never-started", cleanup=True), "START_UNPROVEN")
                self.result.update(desktop_restored=True, desktop_state="OFF_WITHOUT_START")
                return
            sample = await self.sample()
            need(sample.boot == self.cycle.anchor.boot, "RESTORE_BOOT")
            need(self.result.get("owned_cleanup") is True, "CLEANUP_UNPROVEN")
            await self.check_app("before-stop", cleanup=True)
            await self.empty_inventory("inventory-before-stop", cleanup=True)
            code, _ = await self.cli(
                "desktop-stop", "desktop", "stop", "--timeout", "20", timeout=45, cleanup=True
            )
            need(code == 0, "STOP_EXIT")
            for index in range(10):
                if not await self.processes("after-stop-" + str(index), cleanup=True):
                    self.result.update(desktop_restored=True, desktop_state="OFF_CONFIRMED")
                    return
                if index < 9:
                    await asyncio.sleep(1)
            raise RuntimeError("STOP_UNPROVEN")
        except BaseException as error:
            self.result.update(
                desktop_restored=False,
                desktop_state="PENDING",
                restore_category=type(error).__name__,
            )

    def write_new(self, name, raw, maximum=4 * 1024 * 1024):
        need(type(raw) is bytes and len(raw) <= maximum, "EVIDENCE_SIZE")
        with (self.root / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())

    def record_intents(self):
        self.save(
            "ownership.json",
            [{k: v for k, v in record.items() if k != "command"} for record in self.records],
        )

    async def inspect_own(self, record, cleanup=False):
        code, raw = await self.cli(
            "inspect-" + record["role"],
            "inspect",
            "--type",
            "container",
            record["cid"] or record["name"],
            cleanup=cleanup,
        )
        need(code == 0, "OWN_INSPECT")
        values = json.loads(raw)
        need(type(values) is list and len(values) == 1, "OWN_SHAPE")
        info = values[0]
        cid = self.libs["builders"]["validate_own_container"](
            info,
            self.policy,
            self.libs["foundation"],
            base=self.base,
            name=record["name"],
            task=self.state["task"],
            image=record["image"],
            command=record["command"],
            probe=record["role"] == "probe",
        )
        need(record["cid"] is None or record["cid"] == cid, "OWN_ID_CHANGED")
        record["cid"] = cid
        self.record_intents()
        return info, raw

    async def create_own(self, image, role, command):
        task = self.state["task"]
        record = {
            "role": role,
            "name": "maskgw-ol9-w1-" + task[:12] + "-" + role,
            "image": image,
            "command": command,
            "cid": None,
            "removed": False,
        }
        args, measurement = self.libs["builders"]["measured_create"](
            str(CLI),
            self.policy,
            image=image,
            name=record["name"],
            task=task,
            command=command,
            probe=role == "probe",
        )
        need(measurement == self.state["create_measurements"][role], "MEASURED_COMMAND_CHANGED")
        self.records.append(record)
        self.record_intents()  # durable intent BEFORE create, including ambiguous reply
        code, raw = await self.cli("create-" + role, *args)
        need(code == 0 and re.fullmatch(rb"[0-9a-f]{64}\s*", raw), "CREATE_EXIT")
        record["cid"] = raw.decode("ascii").strip()
        info, raw = await self.inspect_own(record)
        need(info["State"]["Running"] is False and info["State"]["Pid"] == 0, "CREATE_RUNNING")
        self.write_new(role + "-inspect-before.json", raw)
        return record

    async def run_own(self, record, expected):
        await self.inspect_own(record)
        need(
            self.watchdog_thread is None or not self.watchdog_thread.is_alive(), "WATCHDOG_PREVIOUS"
        )
        self.stop = threading.Event()
        with self.active_lock:
            self.active = record
        self.watchdog_thread = threading.Thread(
            target=self.watchdog, name="maskgw-w1-watchdog", daemon=False
        )
        self.watchdog_thread.start()
        try:
            code, raw = await self.cli(
                "run-" + record["role"],
                "start",
                "--attach",
                record["cid"],
                timeout=RUN_TIMEOUT_SECONDS,
                limit=1536 * 1024,
            )
        finally:
            self.stop.set()
            self.watchdog_thread.join(timeout=45)
        need(not self.watchdog_thread.is_alive() and not self.watchdog_failed, "WATCHDOG_CLEANUP")
        self.write_new(record["role"] + ".stdout", raw, 1536 * 1024)
        info, inspected = await self.inspect_own(record)
        self.write_new(record["role"] + "-inspect-after.json", inspected)
        status = info["State"]
        need(
            code == 0
            and status["Running"] is False
            and status["Pid"] == 0
            and status["ExitCode"] == 0
            and status["OOMKilled"] is False
            and status["Dead"] is False
            and not self.fired.is_set(),
            "RUN_EXIT",
        )
        with self.active_lock:
            self.active = None
        return self.policy["report_line"](raw, expected)

    def watchdog(self):
        if self.stop.wait(WATCHDOG_SECONDS):
            return
        self.fired.set()
        with self.active_lock:
            record = None if self.active is None else dict(self.active)
        if record is None:
            return
        try:
            self.pins(cleanup=True)
            bounded = self.libs["bounded"]["bounded"]

            async def stop_exact():
                code, raw = await bounded(
                    [
                        str(CLI),
                        "--context",
                        "desktop-linux",
                        "inspect",
                        "--type",
                        "container",
                        record["cid"],
                    ],
                    timeout=10,
                    limit=2 * 1024 * 1024,
                )
                need(code == 0, "WATCHDOG_INSPECT")
                values = json.loads(raw)
                need(type(values) is list and len(values) == 1, "WATCHDOG_SHAPE")
                info = values[0]
                cid = self.policy["identity"](
                    info, record["name"], self.state["task"], record["image"]
                )
                need(
                    cid == record["cid"]
                    and info["Config"]["Labels"]
                    == self.libs["builders"]["expected_labels"](self.base, self.state["task"]),
                    "WATCHDOG_ID",
                )
                if info["State"]["Running"]:
                    code, _ = await bounded(
                        [str(CLI), "--context", "desktop-linux", "kill", "--signal", "KILL", cid],
                        timeout=10,
                        limit=65536,
                    )
                    need(code == 0, "WATCHDOG_KILL")

            asyncio.run(stop_exact())
        except BaseException:
            self.watchdog_failed = True

    def check_attestation(self, raw, installed):
        need(
            type(installed.get("attestation_bytes")) is int
            and 0 < installed["attestation_bytes"] <= 4 * 1024 * 1024,
            "ATTEST_SIZE",
        )
        need(
            len(raw) == installed["attestation_bytes"]
            and hashlib.sha256(raw).hexdigest() == installed["attestation_sha256"],
            "ATTEST_COPY",
        )
        report = json.loads(raw)
        context = self.libs["context"]
        old = json.loads(pinned(context["OLD_ATTEST"], context["OLD_ATTEST_SHA"], 2 * 1024 * 1024))
        manifest = json.loads(
            pinned(
                CONTEXT_ROOT / "context/manifest.json",
                self.libs["builders"]["MANIFEST_SHA"],
                1024 * 1024,
            )
        )
        need(
            report["kind"] == "oracle9-w1-installed-v1"
            and report["manifest"] == manifest
            and report["context_manifest_sha256"] == self.libs["builders"]["MANIFEST_SHA"]
            and report["origin_attestation_sha256"] == context["OLD_ATTEST_SHA"],
            "ATTEST_ORIGIN",
        )
        need(
            report["origin_installed_snapshot"] == old["installed_snapshot"]
            and report["base_snapshot"] == old["base_snapshot"]
            and report["base_pth"] == old["base_pth"]
            and report["native"] == old["native"]
            and report["versions"] == old["versions"],
            "ATTEST_BASE",
        )
        projection = {
            k: v for k, v in manifest["target"]["installed_files"].items() if v["owner"] == "maskgw"
        }
        expected_imports = {
            path.removesuffix(".py").replace("/", "."): {
                "bytes": projection[path]["bytes"],
                "sha256": projection[path]["sha256"],
            }
            for path in self.libs["builders"]["ADDED"]
        }
        imports = report["w1_imports"]
        need(
            type(imports) is dict
            and set(imports) == {"modules", "preloaded"}
            and imports["modules"] == expected_imports
            and type(imports["preloaded"]) is list
            and all(type(name) is str for name in imports["preloaded"])
            and len(set(imports["preloaded"])) == len(imports["preloaded"])
            and set(imports["preloaded"]) <= set(expected_imports),
            "W1_IMPORTS",
        )
        context["check_delta"](old["installed_snapshot"], report["installed_snapshot"], projection)
        need(
            installed["prefix_paths"] == len(report["installed_snapshot"]) == 3337
            and installed["versions"] == report["versions"]
            and installed["native"] == report["native"]
            and installed["w1_imports"] == report["w1_imports"],
            "ATTEST_RESULT",
        )
        return report

    async def perform_b(self):
        need(self.cycle.phase is self.libs["core"]["Phase"].B_CONSUMED, "B_REQUIRED")
        self.pins()
        builders = self.libs["builders"]
        payload = pinned(REPO / "deploy/oracle9_w1_update.py", builders["PAYLOAD_SHA"])
        install = await self.create_own(
            builders["IMAGE"],
            "install",
            builders["native_command"](payload, "install", self.state["task"]),
        )
        await self.inspect_own(install)
        inputs = "/opt/maskgw/w1-inputs-" + self.state["task"]
        self.pins()
        code, raw = await self.cli(
            "copy-public-inputs",
            "cp",
            str(CONTEXT_ROOT / "context") + "/.",
            install["cid"] + ":" + inputs,
            timeout=60,
        )
        need(code == 0, "COPY_INPUTS")
        self.write_new("copy.stdout", raw)
        self.pins()
        installed = await self.run_own(install, "W1_APP_UPDATE_VERIFIED")
        self.result["installation"] = installed
        need(installed.get("managed_inputs_removed") is True, "INPUTS_REMAIN")
        await self.inspect_own(install)
        copied = self.root / "installed-attestation.json"
        need(not copied.exists(), "ATTEST_COLLISION")
        code, _ = await self.cli(
            "copy-attestation",
            "cp",
            install["cid"] + ":" + builders["ATTEST"],
            str(copied),
            timeout=20,
        )
        need(code == 0, "ATTEST_COPY_EXIT")
        report = self.check_attestation(regular(copied, 4 * 1024 * 1024), installed)
        code, raw = await self.cli("install-diff", "diff", install["cid"], limit=1024 * 1024)
        need(code == 0, "DIFF_EXIT")
        self.write_new("install-diff.txt", raw)
        builders["validate_diff"](
            raw, report["origin_installed_snapshot"], report["installed_snapshot"]
        )
        code, raw = await self.cli(
            "tag-free-before-commit",
            "image",
            "ls",
            "--no-trunc",
            "--format",
            "{{.Repository}}:{{.Tag}}",
            self.tag,
        )
        need(code == 0 and not raw.strip(), "TAG_EXISTS")
        info, _ = await self.inspect_own(install)
        need(info["State"]["Running"] is False and info["State"]["Pid"] == 0, "COMMIT_RUNNING")
        changes = [
            "USER 10001:10001",
            "WORKDIR /var/empty",
            "ENTRYPOINT " + json.dumps(self.libs["foundation"]["ENTRY"]),
            "CMD []",
        ]
        args = ["commit"]
        for change in changes:
            args.extend(["--change", change])
        self.commit_intended = True
        self.save("commit-intent.json", {"tag": self.tag, "cid": install["cid"]})
        code, raw = await self.cli("commit-own", *args, install["cid"], self.tag, timeout=60)
        need(code == 0 and re.fullmatch(rb"sha256:[0-9a-f]{64}\s*", raw), "COMMIT_EXIT")
        image = raw.decode("ascii").strip()
        self.commit_id = image
        self.save("commit-result.json", {"tag": self.tag, "image": image})
        code, raw = await self.cli("candidate-image", "image", "inspect", self.tag)
        need(code == 0, "CANDIDATE_EXIT")
        self.write_new("candidate-image.json", raw)
        values = json.loads(raw)
        need(type(values) is list and len(values) == 1 and values[0]["Id"] == image, "CANDIDATE_ID")
        self.candidate = builders["validate_new_image"](
            values[0], self.base, self.policy, self.libs["foundation"], self.state["task"], self.tag
        )
        probe = await self.create_own(
            self.candidate,
            "probe",
            builders["native_command"](
                payload, "probe", self.state["task"], installed["attestation_sha256"]
            ),
        )
        verified = await self.run_own(probe, "W1_APP_PROBE_VERIFIED")
        need(
            all(
                verified[k] == installed[k]
                for k in ("attestation_sha256", "prefix_paths", "versions", "native", "w1_imports")
            ),
            "PROBE_RESULT",
        )
        code, raw = await self.cli("probe-diff", "diff", probe["cid"], limit=1024 * 1024)
        need(code == 0 and not raw.strip(), "PROBE_DIFF")
        self.pins()
        need(not self.fired.is_set(), "WATCHDOG")
        self.result.update(
            probe=verified,
            candidate_image=self.candidate,
            candidate_tag=self.tag,
            update_verified=True,
        )

    async def cleanup_owned(self):
        self.stop.set()
        clean = True
        if self.watchdog_thread is not None and self.watchdog_thread.ident is not None:
            self.watchdog_thread.join(timeout=45)
            clean = not self.watchdog_thread.is_alive() and not self.watchdog_failed
        for record in reversed(self.records):
            try:
                # Even a failed create may have created the exact intended name.
                if record["cid"] is None:
                    code, raw = await self.cli(
                        "resolve-intent",
                        "ps",
                        "-aq",
                        "--no-trunc",
                        "--filter",
                        "name=^/" + record["name"] + "$",
                        cleanup=True,
                    )
                    need(code == 0, "INTENT_EXIT")
                    if not raw.strip():
                        record["removed"] = True
                        continue
                info, _ = await self.inspect_own(record, cleanup=True)
                if info["State"]["Running"]:
                    code, _ = await self.cli(
                        "kill-own", "kill", "--signal", "KILL", record["cid"], cleanup=True
                    )
                    need(code == 0, "KILL_EXIT")
                    info, _ = await self.inspect_own(record, cleanup=True)
                need(
                    info["State"]["Running"] is False and info["State"]["Pid"] == 0,
                    "CLEANUP_RUNNING",
                )
                code, _ = await self.cli("remove-own", "rm", record["cid"], cleanup=True)
                need(code == 0, "REMOVE_EXIT")
                code, raw = await self.cli(
                    "absent-own",
                    "ps",
                    "-aq",
                    "--no-trunc",
                    "--filter",
                    "id=" + record["cid"],
                    cleanup=True,
                )
                need(code == 0 and not raw.strip(), "REMOVE_UNPROVEN")
                record["removed"] = True
            except BaseException:
                clean = False
                record["cleanup_unproven"] = True
            self.record_intents()
        with self.active_lock:
            self.active = None
        self.result["owned_cleanup"] = clean
        if self.commit_intended and not self.result.get("update_verified"):
            try:
                need(clean, "CLEANUP_UNPROVEN")
                code, raw = await self.cli(
                    "resolve-tag",
                    "image",
                    "ls",
                    "--no-trunc",
                    "--format",
                    "{{.Repository}}:{{.Tag}}",
                    self.tag,
                    cleanup=True,
                )
                need(code == 0, "TAG_RESOLVE")
                if raw.strip():
                    need(raw.decode("ascii").strip() == self.tag, "TAG_RESOLVE")
                    code, raw = await self.cli(
                        "inspect-tag-cleanup", "image", "inspect", self.tag, cleanup=True
                    )
                    need(code == 0, "TAG_INSPECT")
                    values = json.loads(raw)
                    need(type(values) is list and len(values) == 1, "TAG_SHAPE")
                    info = values[0]
                    image = info["Id"]
                    labels = info["Config"]["Labels"]
                    need(
                        type(image) is str
                        and re.fullmatch(r"sha256:[0-9a-f]{64}", image)
                        and info["RepoTags"] == [self.tag],
                        "TAG_ID",
                    )
                    need(self.commit_id is None or self.commit_id == image, "TAG_CHANGED")
                    need(
                        info["RootFS"]["Layers"][:3] == list(self.libs["builders"]["LAYERS"])
                        and len(info["RootFS"]["Layers"]) == 4
                        and re.fullmatch(r"sha256:[0-9a-f]{64}", info["RootFS"]["Layers"][-1]),
                        "TAG_LAYERS",
                    )
                    need(
                        all(
                            labels.get(key)
                            == self.libs["builders"]["expected_labels"](
                                self.base, self.state["task"]
                            )[key]
                            for key in (
                                "maskgw.task",
                                "maskgw.source-sha256",
                                "maskgw.manifest-sha256",
                            )
                        ),
                        "TAG_LABELS",
                    )
                    code, _ = await self.cli("remove-tag", "image", "rm", self.tag, cleanup=True)
                    need(code == 0, "TAG_REMOVE")
                code, raw = await self.cli(
                    "tag-absent",
                    "image",
                    "ls",
                    "--no-trunc",
                    "--format",
                    "{{.Repository}}:{{.Tag}}",
                    self.tag,
                    cleanup=True,
                )
                need(code == 0 and not raw.strip(), "TAG_REMAINS")
                self.result["candidate_cleanup"] = True
            except BaseException:
                self.result["candidate_cleanup"] = False
                self.result["owned_cleanup"] = False
        try:
            await self.empty_inventory("inventory-final", cleanup=True)
            self.result["inventory_restored"] = True
        except BaseException:
            self.result["inventory_restored"] = False


def admit_root(root):
    need(
        sys.platform == "win32"
        and sys.flags.isolated == 1
        and sys.flags.dont_write_bytecode == 1
        and sys.flags.optimize == 0
        and sys.version_info[:3] == (3, 11, 3),
        "HOST_RUNTIME",
    )
    need(
        root.parent == HOME / "AppData/Local/Temp"
        and re.fullmatch(r"maskgw-oracle9-w1-run-20261027-[0-9a-f]{32}", root.name),
        "HOST_ROOT",
    )
    info = root.lstat()
    need(
        stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
        "ROOT_TYPE",
    )
    need({p.name for p in root.iterdir()} == {"attempt.json"}, "NOT_FRESH")
    state = json.loads(regular(root / "attempt.json", 16384))
    need(
        type(state) is dict
        and set(state)
        == {"kind", "task", "program_sha256", "pins", "phase", "invoked", "create_measurements"},
        "STATE_SHAPE",
    )
    need(
        state["kind"] == "maskgw-oracle9-w1-run-v1"
        and state["phase"] == "FRESH"
        and state["invoked"] is False
        and type(state["task"]) is str
        and re.fullmatch(r"[0-9a-f]{32}", state["task"]),
        "STATE",
    )
    need(
        type(state["program_sha256"]) is str
        and re.fullmatch(r"[0-9a-f]{64}", state["program_sha256"])
        and state["pins"] == {relative: digest for relative, digest in LIBRARIES.values()},
        "STATE_PINS",
    )
    pinned(Path(__file__), state["program_sha256"])
    return state


def measure_commands(host):
    builders = host.libs["builders"]
    payload = pinned(REPO / "deploy/oracle9_w1_update.py", builders["PAYLOAD_SHA"])
    measured = {}
    for role in ("install", "probe"):
        command = builders["native_command"](
            payload, role, host.state["task"], "0" * 64 if role == "probe" else None
        )
        _, measurement = builders["measured_create"](
            str(CLI),
            host.policy,
            image=builders["IMAGE"],
            name="maskgw-ol9-w1-" + host.state["task"][:12] + "-" + role,
            task=host.state["task"],
            command=command,
            probe=role == "probe",
        )
        measured[role] = measurement
    return measured


async def main(root):
    state = admit_root(root)
    host = Host(root, state)
    host.pins()
    need(measure_commands(host) == state["create_measurements"], "COMMAND_MEASUREMENT")
    host.write_new(
        "invoked.json",
        json_bytes({"task": state["task"], "program_sha256": state["program_sha256"]}),
    )
    state.update(invoked=True, phase="INVOKED")
    host.save("attempt.json", state)
    try:
        await host.start_cycle()
        await host.perform_b()
    except BaseException as error:
        host.result["failure_category"] = type(error).__name__
        if host.cycle is not None:
            host.cycle = host.libs["core"]["abort"](host.cycle)
            host.save("cycle.json", json.loads(host.libs["core"]["encode"](host.cycle)))
    finally:
        try:
            await host.cleanup_owned()
        except BaseException as error:
            host.result.update(owned_cleanup=False, cleanup_category=type(error).__name__)
        await host.restore_desktop()
        try:
            host.pins()
            host.result["inputs_unchanged"] = True
        except BaseException:
            host.result["inputs_unchanged"] = False
        success = (
            all(
                host.result.get(key) is True
                for key in (
                    "update_verified",
                    "owned_cleanup",
                    "inventory_restored",
                    "desktop_restored",
                    "inputs_unchanged",
                )
            )
            and not host.fired.is_set()
            and not host.watchdog_failed
            and "failure_category" not in host.result
        )
        host.result.update(
            outcome="ORACLE9_W1_CANDIDATE_VERIFIED" if success else "NOT_PASSED",
            commands=host.commands,
            watchdog_fired=host.fired.is_set(),
        )
        if host.result.get("update_verified"):
            host.result["candidate_disposition"] = (
                "VERIFIED_LOCAL_RETAINED"
                if success
                else "VERIFIED_LOCAL_RETAINED_OVERALL_NOT_PASSED"
            )
        state.update(phase="FINISHED" if success else "ABORTED")
        host.save("attempt.json", state)
        host.save("result.json", host.result)
    print(
        json.dumps(
            {
                key: host.result[key]
                for key in ("outcome", "owned_cleanup", "inventory_restored", "desktop_restored")
            }
        ),
        flush=True,
    )
    return 0 if success else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(2)
    try:
        status = asyncio.run(main(Path(sys.argv[1])))
    except BaseException as error:
        print(
            json.dumps({"outcome": "W1_HOST_REFUSED", "category": type(error).__name__}), flush=True
        )
        status = 1
    raise SystemExit(status)
