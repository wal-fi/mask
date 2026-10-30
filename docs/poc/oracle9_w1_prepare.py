"""Specific W1 host preparation. Pure helpers first; NO actions on import.

Coordinator/effects are a later reviewed increment. These helpers neither start
Desktop nor invoke Docker. Historical code is private; only five policy functions
are exported. This is trusted-code architecture, NOT an introspection sandbox.
"""

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
from types import MappingProxyType
import zlib

REPO = Path(__file__).resolve().parents[2]
POLICY = REPO / "docs/poc/oracle9_offline_prepare.py"
POLICY_SHA = "401afa8cb18156e59016650ac4b87bf3186af1641685fdb05ea2fb7df5363fce"
PAYLOAD = REPO / "deploy/oracle9_w1_update.py"
PAYLOAD_SHA = "566c46a80675a08a45c6283e9960a8a1b7f946225d2497e42e17404472b74ea6"
MANIFEST_SHA = "d4d4b29b302215b00d56ce249caebe6c5f76943d85725c654b8063d4940c5df8"
IMAGE = "sha256:87871290b01b0e4b8cd9dd90b8001a89ff4e04bd018e12c01ddbff8d6b16483a"
OLD_TASK = "c23dd3df7b4241b4b0757da3863f8f8a"
OLD_TAG = "maskgw-oracle9-app-candidate:" + OLD_TASK
LAYERS = (
    "sha256:c8033153c9465fa4e4f02df8b57cda30011514f5b1e7438bf521776e63f0abaf",
    "sha256:9a40c1add57e0336e3d66b67f5495c053b7e9dcdc8a635a155570174d926b44d",
    "sha256:ca050d12ca449791dea8645f7e616e3131d316e1ace95f0b03cec736c5e0a5ff",
)
EXPORTS = frozenset(
    {"create_args", "validate_container", "identity", "validate_candidate_image", "report_line"}
)
PREFIX = "/opt/maskgw/venv"
SITE = PREFIX + "/lib/python3.11/site-packages"
APP = SITE + "/maskgw"
DIST = SITE + "/maskgw-0.1.0.dist-info"
ATTEST = "/opt/maskgw/oracle9-w1-installed.json"
ANCESTORS = frozenset(
    {"/opt", "/opt/maskgw", PREFIX, PREFIX + "/lib", PREFIX + "/lib/python3.11", SITE}
)
ADDED = frozenset(
    {
        "maskgw/db/session_state.py",
        "maskgw/runtime/linux_guard.py",
        "maskgw/runtime/worker_process.py",
        "maskgw/runtime/worker_protocol.py",
        "maskgw/runtime/worker_session.py",
    }
)
CREATE_MAX_CHARS = 26000


def need(value, category):
    if not value:
        raise RuntimeError(category)


def read_pinned(path, expected, limit):
    info = path.lstat()
    need(
        stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
        "SOURCE_FILE",
    )
    need(0 <= info.st_size <= limit, "SOURCE_SIZE")
    raw = path.read_bytes()
    need(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == expected, "SOURCE_PIN")
    return raw


def _policy_namespace(raw, name):
    need(
        type(raw) is bytes and len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == POLICY_SHA,
        "POLICY_PIN",
    )
    ns = {"__name__": name, "__file__": str(POLICY)}
    exec(compile(raw, str(POLICY), "exec"), ns)
    return ns


def _rebind_metadata(namespace):
    before = dict(namespace)
    namespace["PAYLOAD_SHA"] = PAYLOAD_SHA
    namespace["MANIFEST_SHA"] = MANIFEST_SHA
    changed = {k for k in before if namespace[k] is not before[k]}
    need(
        set(namespace) == set(before) and changed == {"PAYLOAD_SHA", "MANIFEST_SHA"},
        "POLICY_REBIND",
    )
    return sorted(changed)


def policy_pair():
    raw = read_pinned(POLICY, POLICY_SHA, 65536)
    old = _policy_namespace(raw, "_w1_original_policy")
    new = _policy_namespace(raw, "_w1_new_policy")
    changed = _rebind_metadata(new)
    return (
        MappingProxyType({k: old[k] for k in EXPORTS}),
        MappingProxyType({k: new[k] for k in EXPORTS}),
        changed,
    )


def native_command(payload, mode, task, attestation=None):
    need(
        type(payload) is bytes
        and len(payload) <= 32768
        and hashlib.sha256(payload).hexdigest() == PAYLOAD_SHA,
        "PAYLOAD_PIN",
    )
    need(type(task) is str and re.fullmatch("[0-9a-f]{32}", task), "TASK")
    need(mode in ("install", "probe"), "ROLE")
    if mode == "probe":
        need(
            type(attestation) is str and re.fullmatch("[0-9a-f]{64}", attestation), "ATTESTATION_ID"
        )
    else:
        need(attestation is None, "ATTESTATION_ID")
    encoded = base64.b64encode(zlib.compress(payload, 9)).decode("ascii")
    bootstrap = (
        "import base64,zlib,hashlib\np=zlib.decompress(base64.b64decode("
        + repr(encoded)
        + "))\n"
        + "if hashlib.sha256(p).hexdigest()!="
        + repr(PAYLOAD_SHA)
        + ": raise RuntimeError('PAYLOAD_PIN')\n"
        + "exec(compile(p,'<maskgw-w1-update>','exec'))"
    )
    return [
        "-c",
        bootstrap,
        mode,
        *(["/opt/maskgw/w1-inputs-" + task, MANIFEST_SHA] if mode == "install" else [attestation]),
    ]


def measured_create(cli, policy, *, image, name, task, command, probe):
    need(
        type(cli) is str and type(image) is str and re.fullmatch("sha256:[0-9a-f]{64}", image),
        "CREATE_INPUT",
    )
    need(type(task) is str and re.fullmatch("[0-9a-f]{32}", task), "TASK")
    expected_name = "maskgw-ol9-w1-" + task[:12] + ("-probe" if probe else "-install")
    need(name == expected_name and type(probe) is bool, "CREATE_NAME")
    args = policy["create_args"](image, name, task, command, probe)
    full = [cli, "--context", "desktop-linux", *args]
    chars = len(subprocess.list2cmdline(full))
    need(chars <= CREATE_MAX_CHARS, "CREATE_ARGV_LIMIT")
    return args, {
        "role": "probe" if probe else "install",
        "createprocess_chars": chars,
        "margin_chars": CREATE_MAX_CHARS - chars,
    }


def expected_labels(base, task):
    result = dict(base["Config"]["Labels"])
    result.update(
        {
            "maskgw.task": task,
            "maskgw.source-sha256": PAYLOAD_SHA,
            "maskgw.manifest-sha256": MANIFEST_SHA,
        }
    )
    return result


def validate_base(info, policy, foundation):
    need(info["Id"] == IMAGE and info["RootFS"]["Layers"] == list(LAYERS), "ORIGIN_IMAGE")
    return policy["validate_candidate_image"](info, OLD_TASK, OLD_TAG, list(LAYERS[:2]), foundation)


def validate_new_image(info, base, policy, foundation, task, tag):
    result = policy["validate_candidate_image"](info, task, tag, list(LAYERS), foundation)
    expected = deepcopy(base["Config"])
    expected["Labels"] = expected_labels(base, task)
    need(info["Config"] == expected, "CANDIDATE_CONFIG_EXACT")
    return result


def validate_own_container(info, policy, foundation, *, base, name, task, image, command, probe):
    policy["validate_container"](info, name, task, image, command, probe, foundation)
    need(info["Config"]["Labels"] == expected_labels(base, task), "CONTAINER_LABELS_EXACT")
    return info["Id"]


def _in_m(path):
    return path in (APP, DIST) or path.startswith((APP + "/", DIST + "/"))


def validate_diff(raw, before, after):
    need(type(raw) is bytes and 0 < len(raw) <= 1024 * 1024, "DIFF_SIZE")
    text = raw.decode("utf-8")
    seen, added, record, attest = set(), set(), False, False
    for line in text.splitlines():
        need(re.fullmatch(r"[ACD] /[^\x00-\x1f\\]+", line), "DIFF_FORMAT")
        action, path = line.split(" ", 1)
        need(path not in seen, "DIFF_FORMAT")
        need(all(v not in ("", ".", "..") for v in path.split("/")[1:]), "DIFF_PATH")
        seen.add(path)
        if path in ANCESTORS:
            need(action == "C", "DIFF_ANCESTOR")
        elif path == ATTEST:
            need(action == "A", "DIFF_ATTEST")
            attest = True
        else:
            need(_in_m(path), "DIFF_ESCAPE")
            relative = path.removeprefix(PREFIX + "/")
            need(relative in after, "DIFF_MISSING")
            if action == "D":
                need(
                    after[relative]["kind"] == "directory"
                    and before.get(relative) == after[relative],
                    "DIFF_OPAQUE",
                )
            if path.startswith(APP + "/") and action == "A":
                added.add(path.removeprefix(SITE + "/"))
            if path == DIST + "/RECORD":
                need(action in ("A", "C"), "DIFF_RECORD")
                record = True
    need(attest and record and ADDED <= added, "DIFF_INCOMPLETE")
    return len(seen)
