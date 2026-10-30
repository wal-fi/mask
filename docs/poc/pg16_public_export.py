"""Terminal PG16 evidence projection only. No source raw is ever published.

This public-only lab exporter is not a DLP filter or a release/cleanup authority.
Import defines functions; no process, Docker, clock or laboratory action.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import stat

REPO = Path(__file__).resolve().parents[2]
TEMP_ROOT = Path("C:/Users/w.filho/AppData/Local/Temp")
OUTPUT_PARENT = REPO / "docs/poc/evidence"
ENTRY_SHA = "a6089275cbbc3b9db251f587ec69f9bce5e892dcd093f1d285c1ae6efaff67be"
PREPARE_RELATIVE = "docs/poc/pg16_public_prepare.py"
PREPARE_SHA = "02d1dadd0772a873943f434423bb103ad8781ffaf4dea44274c49e2e71846c7c"
FIXED = frozenset(
    (
        "attempt.json",
        "invoked.json",
        "result.json",
        "ownership.json",
        "cycle.json",
        "desktop.json",
        "processes.json",
        "version.json",
        "daemon.json",
        "start-environment-keys.json",
        "public-cli-manifest.json",
        "cases.json",
        "pg16-public-intent.json",
        "pg16-public-report.json",
        "local-probe-output.bin",
        "local-volume-baseline.json",
        "rejected-sample.json",
        "checkpoint-rejected.json",
    )
)
LABELS = frozenset(
    (
        "version",
        "info",
        "initial",
        "start-hidden",
        "OBSERVE",
        "READY",
        "B",
        "inventory-preflight",
        "pg16-image",
        "volumes-initial",
        "inventory-ready",
        "volumes-before-create",
        "create-pg16-public",
        "inspect-pg16-public",
        "inspect-cleanup",
        "kill-pg16-public",
        "rm-pg16-public",
        "absent-after-pg16-public",
        "volumes-final",
        "inventory-final",
        "preserved-after",
        "never-started",
        "before-stop",
        "inventory-before-stop",
        "desktop-stop",
        *("after-stop-" + str(i) for i in range(10)),
    )
)
CODES = frozenset(
    (
        "EXPORT_REFUSED",
        "EXPORT_SOURCE",
        "EXPORT_JSON",
        "EXPORT_ROOT",
        "EXPORT_DESTINATION",
        "EXPORT_ARTIFACT",
        "EXPORT_SIZE",
        "EXPORT_STATE",
        "EXPORT_TERMINAL",
        "EXPORT_RESOURCE",
        "EXPORT_LEDGER",
        "EXPORT_CAPTURE",
        "EXPORT_IMAGE",
        "EXPORT_CID",
        "EXPORT_JOURNAL",
        "EXPORT_REPORT",
        "EXPORT_OWNER",
        "EXPORT_VOLUME",
        "EXPORT_DIAGNOSTIC",
        "EXPORT_CHANGED",
        "EXPORT_IO",
        "EXPORT_INTERNAL",
    )
)
CLI_LABELS = LABELS - frozenset(
    (
        "initial",
        "start-hidden",
        "OBSERVE",
        "READY",
        "B",
        "preserved-after",
        "never-started",
        "before-stop",
        *("after-stop-" + str(i) for i in range(10)),
    )
)


class ExportError(Exception):
    def __init__(self, code):
        super().__init__(code if type(code) is str and code in CODES else "EXPORT_INTERNAL")


def need(value, code="EXPORT_REFUSED"):
    if not value:
        raise ExportError(code) from None


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def hex64(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def count(value, maximum=256):
    return type(value) is int and 0 <= value <= maximum


def value(raw):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError()
            result[key] = item
        return result

    decoded, valid = None, False
    try:
        decoded = json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_constant=lambda _v: (_ for _ in ()).throw(ValueError()),
        )
        valid = True
    except (ValueError, UnicodeError, RecursionError):
        pass
    need(valid, "EXPORT_JSON")
    return decoded


def regular(path, maximum=4194304):
    info = path.lstat()
    need(
        stat.S_ISREG(info.st_mode)
        and not getattr(info, "st_file_attributes", 0) & 0x400
        and info.st_size <= maximum,
        "EXPORT_ARTIFACT",
    )
    raw = path.read_bytes()
    need(len(raw) == info.st_size, "EXPORT_CHANGED")
    return raw


def definitions():
    path = REPO / PREPARE_RELATIVE
    raw = regular(path, 65536)
    need(sha(raw) == PREPARE_SHA, "EXPORT_SOURCE")
    prep = {"__name__": "_pg16_export_prepare", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), prep)
    need(prep["ENTRY_SHA"] == ENTRY_SHA, "EXPORT_SOURCE")
    entry = prep["entry"]()
    host = entry["H"]
    helpers = {
        key: host["captured"](*host["SOURCES"][key])[0] for key in ("profile", "volumes", "watch")
    }
    helpers.update(
        entry=entry, prepare=prep, core=host["captured"](*entry["R"]["LIBRARIES"]["core"])[0]
    )
    return helpers


def allowed_name(name):
    return (
        name in FIXED
        or re.fullmatch(
            r"checkpoint-(?:0[0-9]|1[01])\.json|local-(?:volume-cli|cli)-[0-9]{3}\.bin|volume-(?:baseline|decision|final)-[0-9]{2,3}\.json|emergency-[0-9]{2}\.json",
            name,
        )
        is not None
    )


def snapshot(root):
    paths = sorted(root.iterdir(), key=lambda path: path.name)
    need(1 <= len(paths) <= 256, "EXPORT_SIZE")
    result, total = {}, 0
    for path in paths:
        need(allowed_name(path.name), "EXPORT_ARTIFACT")
        raw = regular(path)
        total += len(raw)
        need(total <= 16777216, "EXPORT_SIZE")
        result[path.name] = raw
    return result


def command_ledger(result):
    rows = result.get("commands")
    need(type(rows) is list and len(rows) <= 256, "EXPORT_LEDGER")
    projected = []
    for row in rows:
        need(
            type(row) is dict
            and row.get("label") in LABELS
            and type(row.get("exit")) is int
            and -(1 << 31) <= row["exit"] < 1 << 32
            and count(row.get("bytes"), 2097152)
            and hex64(row.get("sha256")),
            "EXPORT_LEDGER",
        )
        projected.append({key: row[key] for key in ("label", "exit", "bytes", "sha256")})
    return projected


def captures(files, commands):
    rows = value(files["public-cli-manifest.json"])
    need(type(rows) is list and len(rows) <= 256, "EXPORT_CAPTURE")
    cli_rows = [row for row in commands if row["label"] in CLI_LABELS]
    need(len(cli_rows) == len(rows), "EXPORT_CAPTURE")
    result, seen = [], set()
    schema = {"index", "artifact", "exit", "sha256", "bytes", "local_only", "raw_disposition"}
    for index, row in enumerate(rows, 1):
        need(
            type(row) is dict
            and set(row) == schema
            and type(row["index"]) is int
            and row["index"] == index
            and row["local_only"] is True,
            "EXPORT_CAPTURE",
        )
        command = cli_rows[index - 1]
        need(
            all(
                command[key] == row[key] and type(command[key]) is type(row[key])
                for key in ("exit", "bytes", "sha256")
            ),
            "EXPORT_CAPTURE",
        )
        labels = {command["label"]}
        name = row["artifact"]
        if name is None:
            need(
                row["raw_disposition"] == "DISCARDED_CONFIGURATION"
                and labels <= {"version", "info"},
                "EXPORT_CAPTURE",
            )
            continue
        need(
            type(name) is str
            and re.fullmatch(r"local-(?:volume-cli|cli)-[0-9]{3}\.bin", name)
            and name.endswith(str(index).zfill(3) + ".bin")
            and name in files
            and name not in seen
            and row["raw_disposition"] == "LOCAL_ONLY",
            "EXPORT_CAPTURE",
        )
        raw = files[name]
        need(len(raw) == row["bytes"] and sha(raw) == row["sha256"], "EXPORT_CAPTURE")
        need(
            ("volume-cli" in name) == all(label.startswith("volumes-") for label in labels),
            "EXPORT_CAPTURE",
        )
        seen.add(name)
        result.append(
            {
                "index": index,
                "raw": raw,
                "labels": labels,
                "exit": row["exit"],
                "bytes": len(raw),
                "sha256": sha(raw),
            }
        )
    expected = {
        name for name in files if re.fullmatch(r"local-(?:volume-cli|cli)-[0-9]{3}\.bin", name)
    }
    need(seen == expected, "EXPORT_CAPTURE")
    return result


def diagnostic_projection(result, entry):
    origins = {
        "RUNTIME": entry["RUNTIME_CODES"],
        "PROBE": entry["PROBE_CODES"],
        "VALUE": entry["VALUE_CODES"],
        "HOST_FAULT": entry["BOUNDED_CODES"],
        "EMERGENCY": entry["EMERGENCY_CODES"],
        "VOLUME": {"VOLUME_INVENTORY"},
        "IDENTITY": {"IDENTITY_UNKNOWN"},
        "BOOTSTRAP": {
            "STATE",
            "RUNTIME",
            "FRAME",
            "SPAWN",
            "READY",
            "DEADLINE",
            "IO",
            "STDOUT_LIMIT",
            "EXIT",
            "HELD",
        },
        "CONTROL": {"CANCELLED", "DEADLINE", "INTERRUPTED"},
        "INTERNAL": {"INTERNAL"},
    }
    output = {}
    for phase in ("failure", "cleanup", "restore"):
        code, origin = result.get(phase + "_category"), result.get(phase + "_origin")
        if code is None and origin is None:
            continue
        need(
            type(origin) is str
            and origin in origins
            and type(code) is str
            and code in origins[origin],
            "EXPORT_DIAGNOSTIC",
        )
        output[phase] = {"category": code, "origin": origin}
    return output


def journal_projection(files, result, helpers, success):
    names = sorted(name for name in files if re.fullmatch(r"checkpoint-[0-9]{2}\.json", name))
    need(
        names == ["checkpoint-" + str(i).zfill(2) + ".json" for i in range(len(names))],
        "EXPORT_JOURNAL",
    )
    head, elapsed, equal, replayed = None, None, None, False
    if names:
        state, head = helpers["entry"]["H"]["V2"]["replay"](
            helpers["core"], [files[name] for name in names], require_b=len(names) == 12
        )
        equal = state.anchor.boot == state.last.boot
        replayed = True
        if len(names) == 12:
            elapsed = int(state.last.tick_ms) - int(state.anchor.tick_ms)
    if success or result.get("journal_verified") is True:
        need(len(names) == 12 and result.get("journal_last_sha256") == head, "EXPORT_JOURNAL")
    if success:
        need(
            "cycle.json" in files and helpers["core"]["encode"](state) == files["cycle.json"],
            "EXPORT_JOURNAL",
        )
    return {
        "checkpoint_count": len(names),
        "head": head,
        "interval_a_b_ms": elapsed,
        "boot_equal": equal,
        "replayed": replayed,
    }


def state_projection(info):
    current = info.get("State")
    need(
        type(current) is dict
        and all(type(current.get(key)) is bool for key in ("Running", "OOMKilled", "Dead"))
        and count(current.get("Pid"), 1 << 32)
        and type(current.get("ExitCode")) is int,
        "EXPORT_CID",
    )
    return {key: current[key] for key in ("Running", "Pid", "OOMKilled", "Dead", "ExitCode")}


def profile_projection(replies, record, intent, profile):
    observations, infos = [], []
    if record is None:
        return observations, infos
    for reply in replies:
        if reply["exit"] != 0 or not reply["labels"] & {"inspect-pg16-public", "inspect-cleanup"}:
            continue
        info = profile["one"](reply["raw"])
        profile["identity"](info, intent, record["cid"])
        category, accepted = None, False
        try:
            profile["validate_container"](info, intent, record["cid"])
            accepted = True
        except profile["ProbeError"] as error:
            category = error.args[0]
        groups = {
            key: True if accepted else False if category == key.upper() else None
            for key in ("config", "profile", "surface", "mounts")
        }
        groups["identity"] = True
        observations.append(
            {
                "index": reply["index"],
                "sha256": reply["sha256"],
                "bytes": reply["bytes"],
                "cid": record["cid"],
                "accepted": accepted,
                "category": category,
                "groups": groups,
                "state": state_projection(info),
            }
        )
        infos.append(info)
    return observations, infos


def owner_projection(files, record, helpers, success):
    cases = value(files.get("cases.json", b"[]"))
    need(type(cases) is list and len(cases) <= 1, "EXPORT_OWNER")
    if not cases:
        need(not success, "EXPORT_OWNER")
        return None
    need(record is not None, "EXPORT_OWNER")
    row = cases[0]
    need(
        type(row) is dict
        and row.get("case") == "pg16-public"
        and row.get("removed") is True
        and type(row.get("owner")) is dict,
        "EXPORT_OWNER",
    )
    owner = row["owner"]
    need(
        owner.get("phase") == "CLOSED"
        and owner.get("role") == "P"
        and owner.get("cid") == record["cid"]
        and owner.get("seed_delivery") == "NOT_SENT"
        and owner.get("released") is True,
        "EXPORT_OWNER",
    )
    fault = owner.get("fault")
    channel = helpers["entry"]["H"]["captured"](*helpers["entry"]["H"]["SOURCES"]["owner"])[0]["C"]
    need(
        fault is None or type(fault) is str and fault in {item.value for item in channel["Fault"]},
        "EXPORT_OWNER",
    )
    need(not success or fault is None, "EXPORT_OWNER")
    return {
        key: owner[key] for key in ("phase", "fault", "seed_delivery", "released", "role", "cid")
    }


def volumes_projection(files, replies, infos, record, helpers, result, success):
    core, digest = helpers["volumes"], helpers["watch"]["volume_sha256"]
    baseline_raw = files.get("local-volume-baseline.json")
    if baseline_raw is None:
        need(
            not success
            and record is None
            and result.get("volumes_restored") is False
            and not any(name.startswith("volume-") for name in files),
            "EXPORT_VOLUME",
        )
        return {
            "status": "NOT_ADMITTED",
            "initial_count": None,
            "initial_sha256": None,
            "final_count": None,
            "final_sha256": None,
            "decisions": [],
            "finals": [],
        }
    baseline = value(baseline_raw)
    need(
        type(baseline) is dict
        and set(baseline) == {"kind", "names"}
        and baseline["kind"] == "MASKGW_PG16_LOCAL_VOLUME_BASELINE_V1"
        and type(baseline["names"]) is list
        and len(baseline["names"]) == len(set(baseline["names"])),
        "EXPORT_VOLUME",
    )
    initial = core["checked"](frozenset(baseline["names"]))
    captures = [
        (reply["labels"], core["inventory"](reply["raw"]))
        for reply in replies
        if reply["exit"] == 0 and any(label.startswith("volumes-") for label in reply["labels"])
    ]
    need(
        any("volumes-initial" in labels and names == initial for labels, names in captures),
        "EXPORT_VOLUME",
    )
    expected_decisions, linked = [], set()
    for info in infos:
        decision = core["removal"](initial, info.get("Mounts"))
        linked.update(decision.names)
        expected_decisions.append(
            {
                "kind": "MASKGW_PG16_PUBLIC_VOLUME_DECISION_V1",
                "cid": record["cid"],
                "mode": decision.mode.value,
                "linked_count": len(decision.names),
                "linked_sha256": digest(decision.names),
                "preexisting_count": len(decision.preexisting),
                "preexisting_sha256": digest(decision.preexisting),
                "new_anonymous_names": [
                    name for name in decision.names if name not in initial and hex64(name)
                ],
            }
        )
    need(all(item["mode"] != "PRESERVE_UNCERTAIN" for item in expected_decisions), "EXPORT_VOLUME")
    decisions, finals = [], []
    for name in sorted(files):
        if name.startswith("volume-baseline-"):
            need(
                encoded(value(files[name]))
                == encoded(
                    {
                        "kind": "MASKGW_PG16_PUBLIC_VOLUME_BASELINE_V1",
                        "count": len(initial),
                        "sha256": digest(initial),
                    }
                ),
                "EXPORT_VOLUME",
            )
        elif name.startswith("volume-decision-"):
            item = value(files[name])
            need(
                any(
                    type(item) is dict
                    and set(item) == set(expected)
                    and encoded(item) == encoded(expected)
                    for expected in expected_decisions
                ),
                "EXPORT_VOLUME",
            )
            decisions.append(item)
        elif name.startswith("volume-final-"):
            item = value(files[name])
            need(type(item) is dict, "EXPORT_VOLUME")
            base = {
                "kind",
                "initial_count",
                "initial_sha256",
                "final_count",
                "final_sha256",
                "added_count",
                "missing_count",
                "added_within_linked",
                "restored",
                "uncertain",
            }
            need(
                set(item) in (base, base | {"cid"})
                and ("cid" not in item or record is not None and item["cid"] == record["cid"]),
                "EXPORT_VOLUME",
            )
            matched = False
            for labels, names in captures:
                if "volumes-final" not in labels:
                    continue
                delta = core["difference"](initial, names)
                expected = {
                    "kind": "MASKGW_PG16_PUBLIC_VOLUME_FINAL_V1",
                    "initial_count": len(initial),
                    "initial_sha256": digest(initial),
                    "final_count": len(names),
                    "final_sha256": digest(names),
                    "added_count": len(delta.added),
                    "missing_count": len(delta.missing),
                    "added_within_linked": set(delta.added) <= linked,
                    "restored": not delta.added and not delta.missing,
                    "uncertain": False,
                }
                if "cid" in item:
                    expected["cid"] = record["cid"]
                matched = (
                    matched
                    or type(item.get("uncertain")) is bool
                    and encoded(item) == encoded(expected)
                )
            need(matched, "EXPORT_VOLUME")
            finals.append(item)
    need(
        result.get("volumes_restored") is True
        and any(item["restored"] is True and item["uncertain"] is False for item in finals),
        "EXPORT_RESOURCE",
    )
    return {
        "status": "RESTORED",
        "initial_count": len(initial),
        "initial_sha256": digest(initial),
        "final_count": len(initial),
        "final_sha256": digest(initial),
        "decisions": decisions,
        "finals": finals,
    }


def project(files, reported_exit, helpers):
    entry, profile = helpers["entry"], helpers["profile"]
    state, result = value(files["attempt.json"]), value(files["result.json"])
    need(
        type(state) is dict
        and type(result) is dict
        and type(state.get("task")) is str
        and re.fullmatch(r"[0-9a-f]{32}", state["task"]),
        "EXPORT_STATE",
    )
    task = state["task"]
    need(
        state.get("phase") in ("FINISHED", "ABORTED") and state.get("invoked") is True,
        "EXPORT_TERMINAL",
    )
    expected = helpers["prepare"]["state_for"](task)
    expected.update(phase=state["phase"], invoked=True)
    need(encoded(state) == files["attempt.json"] and state == expected, "EXPORT_STATE")
    need(
        value(files["invoked.json"])
        == {
            "kind": "MASKGW_PG16_PUBLIC_INVOKED_V1",
            "task": task,
            "host_sha256": entry["HOST_SHA"],
            "entry_sha256": ENTRY_SHA,
        },
        "EXPORT_STATE",
    )
    success = reported_exit == 0
    need(
        success == (state["phase"] == "FINISHED")
        and result.get("outcome") == ("PG16_PUBLIC_VERIFIED" if success else "NOT_PASSED"),
        "EXPORT_TERMINAL",
    )
    need(
        all(
            result.get(key) is True
            for key in ("owned_cleanup", "inventory_restored", "desktop_restored")
        )
        and type(result.get("volumes_restored")) is bool,
        "EXPORT_RESOURCE",
    )
    watch = result.get("watchdog")
    need(
        type(watch) is dict
        and watch.get("thread_joined") is True
        and type(watch.get("fired")) is bool
        and type(watch.get("held")) is bool,
        "EXPORT_RESOURCE",
    )
    if success:
        need(
            all(
                result.get(key) is True
                for key in (
                    "pg16_public_verified",
                    "journal_verified",
                    "inputs_unchanged",
                    "volumes_restored",
                )
            )
            and watch["fired"] is False
            and watch["held"] is False
            and not any(
                key in result
                for key in (
                    "failure_category",
                    "cleanup_category",
                    "restore_category",
                    "abort_category",
                    "deadline_category",
                )
            ),
            "EXPORT_RESOURCE",
        )
    records = value(files["ownership.json"])
    need(type(records) is list and len(records) <= 1, "EXPORT_CID")
    record = records[0] if records else None
    if record is not None:
        need(
            type(record) is dict
            and record.get("role") == "pg16-public"
            and record.get("removed") is True
            and record.get("create_uncertain") is False
            and record.get("intent_persisted") is True
            and record.get("image") == profile["IMAGE"]
            and record.get("name") == "maskgw-ol9-pg16-admit-" + task[:12]
            and hex64(record.get("cid"))
            and record.get("volume_uncertain") is False,
            "EXPORT_CID",
        )
    commands = command_ledger(result)
    replies = captures(files, commands)
    image, image_category = None, None
    images = [reply for reply in replies if "pg16-image" in reply["labels"] and reply["exit"] == 0]
    need(len(images) <= 1, "EXPORT_IMAGE")
    if images:
        try:
            image = profile["admit_image"](images[0]["raw"])
        except profile["ProbeError"] as error:
            image_category = error.args[0]
    need(not success or image is not None, "EXPORT_IMAGE")
    need(record is None or image is not None, "EXPORT_IMAGE")
    intent = profile["Intent"](task, image) if image is not None else None
    if record is not None:
        initial = {
            "role": "pg16-public",
            "name": record["name"],
            "image": profile["IMAGE"],
            "command": list(intent.command),
            "cid": None,
            "removed": False,
            "create_uncertain": True,
            "intent_persisted": False,
        }
        need(
            "pg16-public-intent.json" in files
            and files["pg16-public-intent.json"] == encoded(initial),
            "EXPORT_CID",
        )
    observations, infos = profile_projection(replies, record, intent, profile)
    report = None
    if "pg16-public-report.json" in files:
        need(intent is not None and "local-probe-output.bin" in files, "EXPORT_REPORT")
        report = profile["parse_report"](files["local-probe-output.bin"], 0, intent)
        need(encoded(report) == files["pg16-public-report.json"], "EXPORT_REPORT")
    post = observations[-1]["state"] if report is not None and observations else None
    owner = owner_projection(files, record, helpers, success)
    if success:
        need(
            report is not None
            and record is not None
            and len(observations) >= 3
            and all(item["accepted"] for item in observations),
            "EXPORT_REPORT",
        )
        need(
            post is not None
            and post
            == {"Running": False, "Pid": 0, "OOMKilled": False, "Dead": False, "ExitCode": 0},
            "EXPORT_CID",
        )
    desktop = value(files["desktop.json"])
    need(
        type(desktop) is dict
        and type(desktop.get("initial_active")) is bool
        and result.get("desktop_state")
        in ("PRESERVED_ACTIVE", "OFF_WITHOUT_START", "OFF_CONFIRMED"),
        "EXPORT_RESOURCE",
    )
    desktop_modes = {
        "PRESERVED_ACTIVE": (True, "PRESERVED"),
        "OFF_WITHOUT_START": (False, "START_RESERVED"),
        "OFF_CONFIRMED": (False, "STARTED"),
    }
    active, phase = desktop_modes[result["desktop_state"]]
    need(desktop["initial_active"] is active and desktop.get("phase") == phase, "EXPORT_RESOURCE")
    return {
        "kind": "MASKGW_PG16_PUBLIC_SUMMARY_V1",
        "task": task,
        "entry_sha256": ENTRY_SHA,
        "host_sha256": entry["HOST_SHA"],
        "reported_exit": reported_exit,
        "outcome": result["outcome"],
        "resources": {
            key: result[key] for key in ("owned_cleanup", "inventory_restored", "volumes_restored")
        },
        "cycle": journal_projection(files, result, helpers, success),
        "commands": commands,
        "image": {
            "id": profile["IMAGE"],
            "admitted": image is not None,
            "category": image_category,
            "pg_version": None if image is None else image.version,
            "oci_labels_present": None if image is None else bool(image.labels),
            "oci_label_count": None if image is None else len(image.labels),
        },
        "cid": None if record is None else record["cid"],
        "profile_observations": observations,
        "post_execution_state": post,
        "probe": report,
        "owner": owner,
        "volumes": volumes_projection(files, replies, infos, record, helpers, result, success),
        "watchdog": {key: watch[key] for key in ("fired", "held", "thread_joined")},
        "desktop": {
            "initial_active": desktop["initial_active"],
            "state": result["desktop_state"],
            "restored": True,
        },
        "diagnostics": diagnostic_projection(result, entry),
    }


def _export(root, destination, reported_exit):
    need(type(reported_exit) is int and reported_exit in (0, 1), "EXPORT_TERMINAL")
    need(
        type(root) is type(TEMP_ROOT)
        and root.parent == TEMP_ROOT
        and re.fullmatch(r"maskgw-pg16-public-20261030-[0-9a-f]{32}", root.name),
        "EXPORT_ROOT",
    )
    info = root.lstat()
    need(
        stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
        "EXPORT_ROOT",
    )
    files = snapshot(root)
    required = {
        "attempt.json",
        "invoked.json",
        "result.json",
        "ownership.json",
        "desktop.json",
        "public-cli-manifest.json",
    }
    need(required <= files.keys(), "EXPORT_ARTIFACT")
    summary = project(files, reported_exit, definitions())
    task = summary["task"]
    need(
        type(destination) is type(OUTPUT_PARENT)
        and destination.parent == OUTPUT_PARENT
        and destination.name == "pg16-public-run-20261030-" + task[:12],
        "EXPORT_DESTINATION",
    )
    parent = destination.parent.lstat()
    need(
        stat.S_ISDIR(parent.st_mode)
        and not getattr(parent, "st_file_attributes", 0) & 0x400
        and not destination.exists(),
        "EXPORT_DESTINATION",
    )
    summary_raw = encoded(summary)
    entries = [
        {
            "name": name,
            "bytes": len(raw),
            "sha256": sha(raw),
            "published": False,
            "reason": "LOCAL_ONLY" if name.startswith("local-") else "PROJECTION_ONLY",
        }
        for name, raw in sorted(files.items())
    ]
    manifest = {
        "kind": "MASKGW_PG16_PUBLIC_TRANSPORT_V1",
        "task": task,
        "root_name": root.name,
        "reported_exit": reported_exit,
        "entry_sha256": ENTRY_SHA,
        "source_count": len(files),
        "source_bytes": sum(map(len, files.values())),
        "published_source_count": 0,
        "withheld_source_count": len(files),
        "derived_artifacts": [
            {"name": "summary.json", "bytes": len(summary_raw), "sha256": sha(summary_raw)}
        ],
        "files": entries,
        "source_unchanged": True,
    }
    need({p.name for p in root.iterdir()} == set(files), "EXPORT_CHANGED")
    for name, raw in files.items():
        need(regular(root / name) == raw, "EXPORT_CHANGED")
    destination.mkdir(exist_ok=False)
    manifest_raw = encoded(manifest)
    for name, raw in (("summary.json", summary_raw), ("transport.json.next", manifest_raw)):
        with (destination / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    need(
        {path.name for path in destination.iterdir()} == {"summary.json", "transport.json.next"},
        "EXPORT_CHANGED",
    )
    need(
        regular(destination / "summary.json") == summary_raw
        and regular(destination / "transport.json.next") == manifest_raw,
        "EXPORT_CHANGED",
    )
    os.rename(destination / "transport.json.next", destination / "transport.json")
    return manifest


def export(root, destination, reported_exit):
    problem = None
    try:
        return _export(root, destination, reported_exit)
    except ExportError as error:
        problem = error.args[0]
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        problem = "EXPORT_IO"
    except Exception:
        problem = "EXPORT_INTERNAL"
    # Deliberately outside except: no original message, cause or context escapes.
    raise ExportError(problem) from None
