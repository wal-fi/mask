"""Strict measured T4 v2 profile, no runtime AST transforms or native effects."""

import asyncio
import hashlib
import json
from pathlib import Path
import re
import stat

REPO = Path(__file__).resolve().parents[2]
DEPENDENCIES = {
    "policy": (
        "docs/poc/w1_bootstrap_probe.py",
        "e3cf9f4d5b6150c4c3d975fd17d6296348fa14b9e22a43543c9913d34361afd4",
    ),
    "core": (
        "docs/poc/w1_bootstrap_admission_fields.py",
        "9612a46b3a38ef1d96e90bf12d41975a3acde66209f88e38fdea04a95efec9e3",
    ),
    "channel": (
        "docs/poc/w1_bootstrap_channel.py",
        "e6ca9e606567289fa312049b071aa777e1764579813829747cb32df05d4ee87a",
    ),
    "coordinator": (
        "docs/poc/oracle9_w1_run.py",
        "4bc0b083c9df44edd2aa532de7f43cf9f7f9f5a581edb267d8414d21057fd753",
    ),
    "v2": (
        "docs/poc/oracle9_w1_run_v2.py",
        "b59388f52a38319c19c2c60b25100347d319a59c2778395cc68bea64d2bc0c37",
    ),
    "clock": (
        "docs/poc/oracle9_clock_sample.py",
        "6bcbdbe5b9345a5d70e408e1988226ad300d4e57d64eb6beec1d4d7cd55a692d",
    ),
    "cycle": (
        "docs/poc/oracle9_cycle_freshness.py",
        "d2b485c29d2cef36599af51fc342ac39a991f9564bb919baa18d3cb1ff7e5b66",
    ),
    "bounded": (
        "docs/poc/run_linux_as_probe.py",
        "58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627",
    ),
    "host": (
        "docs/poc/w1_bootstrap_t4_host.py",
        "88e220ebb342bba6889dc0934a3872b3bac3e29e3583c24f60d5503ad1d18c70",
    ),
}


def need(ok):
    if not ok:
        raise RuntimeError("SOURCE_PIN") from None


def capture():
    result = {}
    for key, (relative, digest) in DEPENDENCIES.items():
        p = REPO / relative
        info = p.lstat()
        need(
            stat.S_ISREG(info.st_mode)
            and not getattr(info, "st_file_attributes", 0) & 0x400
            and info.st_size <= 65536
        )
        raw = p.read_bytes()
        need(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == digest)
        result[key] = raw
    return result


RAW = capture()
CORE = {"__name__": "_t4_v2_closed_codes", "__file__": str(REPO / DEPENDENCIES["core"][0])}
exec(compile(RAW["core"], CORE["__file__"], "exec"), CORE)
EMERGENCY_CODES = frozenset(("INPUT", "PIN", "BUDGET", "COMMAND"))
RUNTIME_CODES = frozenset(
    (
        "ABSENCE",
        "ADMISSION_TIME",
        "APP_CREATED",
        "APP_DISAPPEARED",
        "APP_DUPLICATE",
        "APP_EXIT",
        "APP_IDENTITY",
        "APP_NAME",
        "APP_PID",
        "APP_SHAPE",
        "ATTEST_BASE",
        "ATTEST_COLLISION",
        "ATTEST_COPY",
        "ATTEST_COPY_EXIT",
        "ATTEST_ORIGIN",
        "ATTEST_RESULT",
        "ATTEST_SIZE",
        "BASE_CONFIG_EXACT",
        "BASE_IMAGE",
        "BASE_SHAPE",
        "BLACKHOLE_ORACLE",
        "B_REQUIRED",
        "CANDIDATE_EXIT",
        "CANDIDATE_ID",
        "CAPTURE",
        "CAPTURE_PIN",
        "CASE",
        "CHANNEL_FILE",
        "CHANNEL_PIN",
        "CID_CHANGED",
        "CID_REQUIRED",
        "CLEANUP_DEADLINE",
        "CLEANUP_LOCK",
        "CLEANUP_RUNNING",
        "CLEANUP_UNPROVEN",
        "CLI",
        "CLI_IDENTITY_CHANGED",
        "CLI_KILL_DID_NOT_LEAVE_CID_ALIVE",
        "CLI_SCOPE",
        "CLOCK_KIND",
        "COMMAND_MEASUREMENT",
        "COMMIT_EXIT",
        "COMMIT_OWNER",
        "COMMIT_PUBLIC_LABEL",
        "COMMIT_RUNNING",
        "COMMIT_SHAPE",
        "CONFIG",
        "CONTAINER_LABELS_EXACT",
        "COPY_INPUTS",
        "CREATE_EXIT",
        "CREATE_MEASUREMENT",
        "CREATE_MEASUREMENTS",
        "CREATE_RUNNING",
        "CREATE_SIZE",
        "CYCLE_REFUSED",
        "DAEMON",
        "DAEMON_EXIT",
        "DAEMON_PROFILE",
        "DIFF_EXIT",
        "ENDPOINT",
        "ENTRY_PIN",
        "EVIDENCE_SIZE",
        "FILE_CHANGED",
        "FILE_SIZE",
        "FOREGROUND_BUSY",
        "FRESH_ROOT",
        "HOST_CAPTURE",
        "HOST_FILE",
        "HOST_HELD",
        "HOST_LOOP",
        "HOST_PIN",
        "HOST_ROOT",
        "HOST_RUNTIME",
        "IMAGE",
        "IMAGE_EXACT",
        "INITIAL_UNKNOWN",
        "INNER_PIN",
        "INPUTS_REMAIN",
        "INSPECT",
        "INSPECT_SHAPE",
        "INTENT",
        "INTENT_EXIT",
        "INVENTORY",
        "ISOLATION",
        "JOURNAL_ACTION",
        "JOURNAL_ADMISSION",
        "JOURNAL_BINDING",
        "JOURNAL_CHAIN",
        "JOURNAL_COUNT",
        "JOURNAL_FILES",
        "JOURNAL_INCOMPLETE",
        "JOURNAL_SAMPLE",
        "JOURNAL_SCHEMA",
        "JOURNAL_SIZE",
        "JOURNAL_START",
        "JOURNAL_STATE",
        "JOURNAL_TRANSITION",
        "KILL",
        "KILL_EXIT",
        "MEASURED_COMMAND_CHANGED",
        "NOT_FRESH",
        "ORIGINAL_PIN",
        "ORIGINAL_TYPE",
        "OUTPUT_ORACLE",
        "OWNERSHIP",
        "OWNER_HELD",
        "OWN_COMMAND",
        "OWN_ID_CHANGED",
        "OWN_INSPECT",
        "OWN_SHAPE",
        "PIN",
        "PROBE_DIFF",
        "PROBE_RESULT",
        "PROFILE",
        "READY_ORACLE",
        "REGULAR",
        "REMOVE",
        "REMOVE_EXIT",
        "REMOVE_UNPROVEN",
        "REPORT_CANONICAL",
        "REPORT_CASE",
        "REPORT_FACTS",
        "REPORT_SCHEMA",
        "REPORT_SIZE",
        "RESTORE_BOOT",
        "ROOT",
        "ROOT_TYPE",
        "RUNNING",
        "RUN_EXIT",
        "SEND_FAILED",
        "SOURCE",
        "SOURCE_PIN",
        "SPAWN_NOT_REGISTERED",
        "START_ENV",
        "START_IDENTITY",
        "START_SHAPE",
        "START_UNPROVEN",
        "STATE",
        "STATE_PINS",
        "STATE_SCHEMA",
        "STATE_SHAPE",
        "STATE_VALUES",
        "STOP_EXIT",
        "STOP_UNPROVEN",
        "SUPERVISION_REQUIRED",
        "SURFACE",
        "T4_INSTALL_FORBIDDEN",
        "T4_OLD_TRANSPORT_FORBIDDEN",
        "T4_OLD_WATCHDOG_FORBIDDEN",
        "T4_WATCHDOG_REFUSED",
        "TAG_CHANGED",
        "TAG_EXISTS",
        "TAG_ID",
        "TAG_INSPECT",
        "TAG_LABELS",
        "TAG_LAYERS",
        "TAG_REMAINS",
        "TAG_REMOVE",
        "TAG_RESOLVE",
        "TAG_SHAPE",
        "TASK",
        "TASK_START",
        "UNEXPECTED_SEND",
        "V2_CAPTURE",
        "VERSION",
        "W1_IMPORTS",
        "WAIT_CLOCK",
        "WATCHDOG",
        "WATCHDOG_CLEANUP",
        "WATCHDOG_FIRED",
        "WATCHDOG_ID",
        "WATCHDOG_INSPECT",
        "WATCHDOG_KILL",
        "WATCHDOG_PREVIOUS",
        "WATCHDOG_SHAPE",
        "WATCHDOG_START",
    )
)

VALUE_CODES = frozenset(("CLOCK_REFUSED", "CYCLE_SCHEMA"))
BOUNDED_CODES = frozenset(
    (
        "ARTIFACT_LIMIT",
        "CAPABILITIES",
        "CLEANUP_UNCONFIRMED",
        "CLI_CLEANUP",
        "COMMAND",
        "CONTAINER_EXIT",
        "CONTAINER_STILL_LIVE",
        "CREATE",
        "CREATION_UNCERTAIN",
        "DEADLINE",
        "ENGINE_UNAVAILABLE",
        "ENTRYPOINT",
        "EXTERNAL_ACCESS",
        "IDENTITY",
        "IMAGE_NOT_PINNED",
        "IMAGE_PROFILE",
        "INSPECT",
        "INSPECT_SCHEMA",
        "LIMIT_CONFIGURATION",
        "LOG_OR_USER",
        "LOT_DEADLINE",
        "MOUNTS",
        "NAMESPACE",
        "OUTPUT_LIMIT",
        "PRIVILEGE",
        "PROCESS_CONFIGURATION",
        "REMOVE_FAILED",
        "REMOVE_UNCONFIRMED",
        "REPORT_CLAIM",
        "REPORT_SCHEMA",
        "SOURCE_CHANGED",
        "SOURCE_LIMIT",
        "ULIMITS",
        "WATCHDOG_CLEANUP",
    )
)


def pins(cleanup=False):
    for key, (relative, digest) in DEPENDENCIES.items():
        need(hashlib.sha256(RAW[key]).hexdigest() == digest)
        if not cleanup:
            p = REPO / relative
            info = p.lstat()
            need(
                stat.S_ISREG(info.st_mode)
                and not getattr(info, "st_file_attributes", 0) & 0x400
                and info.st_size <= 65536
            )
            need(hashlib.sha256(p.read_bytes()).hexdigest() == digest)


def closed_category(error, namespaces):
    kind = type(error)
    if kind is asyncio.CancelledError:
        return "CANCELLED"
    if kind is TimeoutError:
        return "DEADLINE"
    channel = namespaces["channel"]
    if kind is channel["BootstrapError"]:
        return error.category.value if type(error.category) is channel["Fault"] else "INTERNAL"
    if kind is ValueError:
        return (
            error.args[0]
            if len(error.args) == 1 and type(error.args[0]) is str and error.args[0] in VALUE_CODES
            else "INTERNAL"
        )
    if kind is namespaces["bounded"]["HostFault"]:
        return (
            error.category
            if type(error.category) is str
            and error.category in BOUNDED_CODES
            and error.args == (error.category,)
            else "INTERNAL"
        )
    if kind is namespaces["identity"]["IdentityError"]:
        return "IDENTITY_UNKNOWN"
    if kind is namespaces["emergency"]["EmergencyError"]:
        return (
            error.args[0]
            if len(error.args) == 1
            and type(error.args[0]) is str
            and error.args[0] in EMERGENCY_CODES
            else "INTERNAL"
        )
    if (
        kind is RuntimeError
        and len(error.args) == 1
        and type(error.args[0]) is str
        and error.args[0] in RUNTIME_CODES
    ):
        return error.args[0]
    return "INTERNAL"


def validate_container(info, intent, factory):
    identity = factory["identity"]
    channel_bytes = factory["channel_bytes"]
    Case = factory["Case"]
    ENV = factory["ENV"]
    need = factory["need"]
    labels_for = factory["labels_for"]
    cid = identity(info, intent)
    channel_bytes()  # acceptance may fail on changed input; cleanup ownership never rereads it
    task, case = intent.task, intent.case
    config, host = info["Config"], info["HostConfig"]
    uid = "70" if case is Case.RETAIN else "10001"
    need(
        config["Labels"] == labels_for(task)
        and config["User"] == uid + ":" + uid
        and config["WorkingDir"] == "/var/empty"
        and config["Env"] == ENV
        and config["Tty"] is False
        and config["OpenStdin"] is True
        and config["StdinOnce"] is True
        and not config.get("Volumes")
        and not config.get("ExposedPorts")
        and config.get("Healthcheck") == {"Test": ["NONE"]},
        "CONFIG",
    )
    need(
        host["ReadonlyRootfs"] is True
        and host["NetworkMode"] == "none"
        and host["CapDrop"] == ["ALL"]
        and not host.get("CapAdd")
        and host["SecurityOpt"] == ["no-new-privileges"]
        and host["Memory"] == host["MemorySwap"] == 134217728
        and host["PidsLimit"] == 8
        and host["NanoCpus"] == 1000000000
        and host["ShmSize"] == 8388608,
        "PROFILE",
    )
    need(
        {item["Name"]: (item["Soft"], item["Hard"]) for item in host["Ulimits"]}
        == {"core": (0, 0), "nofile": (128, 128)}
        and len(host["Ulimits"]) == 2
        and host["IpcMode"] == host["CgroupnsMode"] == "private"
        and host["PidMode"] == ""
        and host["RestartPolicy"] == {"Name": "no", "MaximumRetryCount": 0}
        and host["LogConfig"] == {"Type": "none", "Config": {}},
        "ISOLATION",
    )
    need(
        not any(
            host.get(key)
            for key in (
                "Privileged",
                "Init",
                "AutoRemove",
                "Tmpfs",
                "Binds",
                "Mounts",
                "Devices",
                "DeviceRequests",
                "DeviceCgroupRules",
                "GroupAdd",
                "Sysctls",
                "Links",
                "ExtraHosts",
                "PortBindings",
                "PublishAllPorts",
                "VolumesFrom",
                "Dns",
                "DnsOptions",
                "DnsSearch",
            )
        )
        and not info.get("Mounts"),
        "SURFACE",
    )
    return cid


def publication(raw, environment, labels, command, entrypoint, *, cid, name):
    """Export gate only. Caller retains raw locally, never receives it in result."""
    if type(raw) is not bytes or not 0 < len(raw) <= 2097152:
        return {"allowed": False, "categories": ["SIZE"], "bytes": 0, "sha256": None}
    result = {
        "allowed": False,
        "categories": [],
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }

    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("DUPLICATE")
            value[key] = item
        return value

    def private_key(value):
        if type(value) is dict:
            return any(
                "proxy" in key.casefold() or "auth" in key.casefold() or private_key(item)
                for key, item in value.items()
            )
        if type(value) is list:
            return any(private_key(item) for item in value)
        return False

    try:
        values = json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_constant=lambda _v: (_ for _ in ()).throw(ValueError("NON_JSON")),
        )
        if type(values) is not list or len(values) != 1:
            raise ValueError("SHAPE")
        info = values[0]
        config, host = info["Config"], info["HostConfig"]
        if type(config) is not dict or type(host) is not dict:
            raise ValueError("SHAPE")
        if config.get("Env") != environment:
            result["categories"].append("ENV")
        if private_key(info):
            result["categories"].append("PRIVATE_KEY")
        if (
            type(cid) is not str
            or re.fullmatch(r"[0-9a-f]{64}", cid) is None
            or type(name) is not str
            or re.fullmatch(
                r"maskgw-ol9-t4-[0-9a-f]{12}-(normal|retain|bad-ready|blackhole|flood|cancel-start|reader-negative)",
                name,
            )
            is None
            or info.get("Id") != cid
            or info.get("Name") != "/" + name
        ):
            result["categories"].append("IDENTITY")
        observed = config.get("Labels")
        if (
            type(observed) is not dict
            or not all(observed.get(k) == v for k, v in labels.items())
            or any(
                key not in labels and (key != "desktop.docker.io/ports.scheme" or value != "v2")
                for key, value in observed.items()
            )
        ):
            result["categories"].append("LABELS")
        if config.get("Cmd") != list(command) or config.get("Entrypoint") != list(entrypoint):
            result["categories"].append("COMMAND")
    except (ValueError, KeyError, TypeError, RecursionError, UnicodeError):
        result["categories"].append("SHAPE")
    result["allowed"] = not result["categories"]
    return result
