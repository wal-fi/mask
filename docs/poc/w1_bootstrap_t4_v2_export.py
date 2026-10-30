"""Specific terminal T4 v2 export. No Docker/CLI; raw aliases default denied."""

import hashlib
import json
import os
from pathlib import Path
import re
import stat

REPO = Path(__file__).resolve().parents[2]
TEMP_ROOT = Path("C:/Users/w.filho/AppData/Local/Temp")
OUTPUT_PARENT = REPO / "docs/poc/evidence"
RUN_RELATIVE = "docs/poc/w1_bootstrap_t4_v2_run.py"
RUN_SHA = "28b5601348fb7c8e95df9780b7f2424cb49ecf21306fffd3d2e39cb18d124538"
IMAGE_RECORD = "docs/poc/evidence/oracle9-w1-v2-run-20261027/candidate-image.json"
IMAGE_RECORD_SHA = "c224641de98420e4308d528aca45bd5d03f34124b90cb6651e8a6db3d9747653"
ROLES = ("normal", "retain", "bad-ready", "blackhole", "flood", "cancel-start", "reader-negative")
FIXED = frozenset(
    {
        "attempt.json",
        "candidate-image.json",
        "cycle.json",
        "daemon.json",
        "desktop.json",
        "invoked.json",
        "ownership.json",
        "processes.json",
        "start-environment-keys.json",
        "version.json",
        "result.json",
        "transport-captures.json",
        "cases.json",
        "rejected-sample.json",
        "checkpoint-rejected.json",
    }
)


def need(value, category):
    if not value:
        raise RuntimeError(category) from None


def definitions():
    path = REPO / RUN_RELATIVE
    info = path.lstat()
    need(
        stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "SOURCE"
    )
    raw = path.read_bytes()
    need(len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == RUN_SHA, "SOURCE_PIN")
    ns = {"__name__": "_admission_export_definitions", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), ns)
    return ns


def raw_role(name):
    if name == "retain-cli-reaped-cid-alive.json":
        return "retain"
    match = re.fullmatch(
        r"(normal|retain|bad-ready|blackhole|flood|cancel-start|reader-negative)-(transport-inspect-[0-9]{2}|inspect-before)\.json",
        name,
    )
    return None if match is None else match.group(1)


def allowed_name(name):
    return (
        name in FIXED
        or raw_role(name) is not None
        or re.fullmatch(r"checkpoint-(0[0-9]|1[01])\.json", name) is not None
        or re.fullmatch(r"emergency-[0-9]{2}\.json", name) is not None
        or name in {role + tail for role in ROLES for tail in ("-intent.json", "-report.json")}
    )


def metadata_publication(raw):
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
        return type(value) is list and any(private_key(item) for item in value)

    try:
        value = json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_constant=lambda _v: (_ for _ in ()).throw(ValueError("NON_JSON")),
        )
        if type(value) not in (dict, list):
            raise ValueError("SHAPE")
        if private_key(value):
            return {"allowed": False, "categories": ["METADATA_PRIVATE_KEY"]}
    except (ValueError, TypeError, RecursionError, UnicodeError):
        return {"allowed": False, "categories": ["METADATA_SHAPE"]}
    return {"allowed": True, "categories": []}


def export(root, destination, reported_exit):
    need(type(reported_exit) is int and reported_exit in (0, 1), "EXIT")
    need(
        root.parent == TEMP_ROOT
        and re.fullmatch(r"maskgw-oracle9-t4-v2-20261029-[0-9a-f]{32}", root.name),
        "ROOT",
    )
    info = root.lstat()
    need(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "ROOT")
    ns = definitions()
    r, host = ns["R"], ns["H"]
    policy, _ = host["captured"](*host["SOURCES"]["policy"])
    snapshot = {}
    total = 0
    children = sorted(root.iterdir(), key=lambda path: path.name)
    need(1 <= len(children) <= 256, "ARTIFACTS")
    for path in children:
        item = path.lstat()
        need(
            allowed_name(path.name)
            and stat.S_ISREG(item.st_mode)
            and not getattr(item, "st_file_attributes", 0) & 0x400
            and item.st_size <= 4194304,
            "ARTIFACTS",
        )
        raw = path.read_bytes()
        need(len(raw) == item.st_size, "SOURCE_CHANGED")
        total += len(raw)
        need(total <= 67108864, "SIZE")
        snapshot[path.name] = raw
    state = json.loads(snapshot["attempt.json"])
    need(r["json_bytes"](state) == snapshot["attempt.json"], "STATE")
    need(type(state.get("task")) is str and re.fullmatch(r"[0-9a-f]{32}", state["task"]), "STATE")
    task = state["task"]
    need(
        state.get("phase") in ("FINISHED", "ABORTED") and state.get("invoked") is True,
        "NOT_TERMINAL",
    )
    expected = {
        "kind": "maskgw-oracle9-t4-v2",
        "task": task,
        "phase": state["phase"],
        "invoked": True,
        "program_sha256": ns["PROGRAM_SHA"],
        "v2_sha256": ns["V2_SHA"],
        "host_sha256": ns["HOST_SHA"],
        "entry_sha256": RUN_SHA,
        "pins": dict(r["LIBRARIES"].values()),
        "t4_pins": dict(host["SOURCES"].values()),
        "transport_pins": ns["TRANSPORT_PINS"],
        "image": policy["IMAGE"],
        "create_measurements": {
            case.value: policy["create_args"](str(r["CLI"]), policy["Intent"](task, case))[1]
            for case in policy["Case"]
        },
    }
    need(state == expected, "STATE")
    need(
        destination.parent == OUTPUT_PARENT
        and destination.name == "oracle9-t4-v2-run-20261029-" + task[:12],
        "DESTINATION",
    )
    result = json.loads(snapshot["result.json"])
    need((state["phase"] == "FINISHED") == (reported_exit == 0), "EXIT")
    need(
        all(
            result.get(key) is True
            for key in ("owned_cleanup", "inventory_restored", "desktop_restored")
        ),
        "RESOURCE_UNPROVEN",
    )
    need(result.get("watchdog", {}).get("thread_joined") is True, "RESOURCE_UNPROVEN")
    need((reported_exit == 0) == (result.get("outcome") == "ORACLE9_T4_V2_VERIFIED"), "EXIT")
    if reported_exit == 0:
        need(
            all(
                result.get(key) is True
                for key in ("t4_verified", "journal_verified", "inputs_unchanged")
            )
            and result["watchdog"].get("fired") is False,
            "RESULT",
        )
    registry = json.loads(snapshot["ownership.json"])
    need(type(registry) is list and len(registry) <= 7, "OWNERSHIP")
    records = {}
    for record in registry:
        role = record["role"]
        need(
            role in ROLES
            and role not in records
            and record["removed"] is True
            and record["create_uncertain"] is False
            and record["image"] == policy["IMAGE"]
            and re.fullmatch(r"[0-9a-f]{64}", record["cid"]),
            "OWNERSHIP",
        )
        need(record["name"] == policy["name_for"](task, policy["Case"](role)), "OWNERSHIP")
        records[role] = record
    captures = json.loads(snapshot.get("transport-captures.json", b"[]"))
    need(type(captures) is list, "CAPTURE")
    raw_metadata = {}
    for capture in captures:
        name = capture["raw_name"]
        need(
            raw_role(name) == capture["role"]
            and capture["role"] in records
            and name not in raw_metadata
            and capture["phase"] in ("admission", "cleanup")
            and name in snapshot,
            "CAPTURE",
        )
        raw = snapshot[name]
        need(
            len(raw) == capture["bytes"] and hashlib.sha256(raw).hexdigest() == capture["sha256"],
            "CAPTURE_CHANGED",
        )
        raw_metadata[name] = capture
    if reported_exit == 0:
        cases = json.loads(snapshot.get("cases.json", b"[]"))
        need(
            set(records) == set(ROLES)
            and type(cases) is list
            and len(cases) == 7
            and {item["case"] for item in cases} == set(ROLES)
            and all(item["removed"] is True and item["owner"]["released"] is True for item in cases)
            and "retain-cli-reaped-cid-alive.json" in snapshot,
            "RESULT",
        )
    # Image metadata is public only if it is EXACTLY the pinned historical image.
    if "candidate-image.json" in snapshot:
        image_raw = r["pinned"](REPO / IMAGE_RECORD, IMAGE_RECORD_SHA)
        need(snapshot["candidate-image.json"] == r["json_bytes"](json.loads(image_raw)[0]), "IMAGE")
    output = {}
    entries = []
    for name, raw in snapshot.items():
        role = raw_role(name)
        gate = metadata_publication(raw) if role is None else None
        if role is not None:
            record = records.get(role)
            captured = raw_metadata.get(name)
            if name == role + "-inspect-before.json":
                candidates = [
                    item
                    for item in captures
                    if item["role"] == role and item["phase"] == "admission"
                ]
                captured = candidates[0] if len(candidates) == 1 else None
                if captured is not None:
                    need(
                        hashlib.sha256(raw).hexdigest() == captured["sha256"]
                        and len(raw) == captured["bytes"],
                        "CAPTURE_CHANGED",
                    )
            if name == "retain-cli-reaped-cid-alive.json":
                commands = result.get("commands", [])
                need(type(commands) is list, "COMMANDS")
                matches = [
                    row
                    for row in commands
                    if type(row) is dict
                    and row.get("label") == "inspect-cleanup-retain"
                    and row.get("exit") == 0
                    and row.get("sha256") == hashlib.sha256(raw).hexdigest()
                    and row.get("bytes") == len(raw)
                ]
                captured = {"live_retain": True} if matches else None
            if record is None or captured is None:
                gate = {"allowed": False, "categories": ["UNREGISTERED_RAW"]}
            else:
                intent = policy["Intent"](task, policy["Case"](role))
                gate = ns["PROFILE"]["publication"](
                    raw,
                    policy["ENV"],
                    policy["labels_for"](task),
                    intent.command,
                    policy["ENTRY"],
                    cid=record["cid"],
                    name=record["name"],
                )
        permitted = gate is None or gate["allowed"]
        entries.append(
            {
                "name": name,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "published": permitted,
                "publication": gate,
            }
        )
        if permitted:
            output[name] = raw
    # Validate ALL sources before mkdir; no partially published unclassified input.
    need({path.name for path in root.iterdir()} == set(snapshot), "SOURCE_CHANGED")
    for name, raw in snapshot.items():
        need((root / name).read_bytes() == raw, "SOURCE_CHANGED")
    manifest = {
        "kind": "MASKGW_T4_V2_TRANSPORT_V1",
        "root": str(root),
        "task": task,
        "reported_exit": reported_exit,
        "source_count": len(snapshot),
        "source_bytes": total,
        "published_count": len(output),
        "published_bytes": sum(map(len, output.values())),
        "withheld_count": len(snapshot) - len(output),
        "files": entries,
        "source_unchanged": True,
    }
    parent = destination.parent.lstat()
    need(
        stat.S_ISDIR(parent.st_mode) and not getattr(parent, "st_file_attributes", 0) & 0x400,
        "DESTINATION",
    )
    destination.mkdir(exist_ok=False)
    for name, raw in output.items():
        with (destination / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    need({path.name for path in root.iterdir()} == set(snapshot), "SOURCE_CHANGED")
    for name, original in snapshot.items():
        need((root / name).read_bytes() == original, "SOURCE_CHANGED")
    raw = r["json_bytes"](manifest)
    with (destination / "transport.json").open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {
        "destination": str(destination),
        "source_count": len(snapshot),
        "published_count": len(output),
        "withheld_count": manifest["withheld_count"],
        "transport_sha256": hashlib.sha256(raw).hexdigest(),
    }
