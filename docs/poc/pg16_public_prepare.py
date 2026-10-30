"""Public PG16 attempt materializer only; never invokes runner or Docker."""

import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess

REPO = Path(__file__).resolve().parents[2]
ENTRY = REPO / "docs/poc/pg16_public_run.py"
ENTRY_SHA = "a6089275cbbc3b9db251f587ec69f9bce5e892dcd093f1d285c1ae6efaff67be"
PYTHON = REPO / ".venv/Scripts/python.exe"
PYTHON_SHA = "bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82"


def need(value, category):
    if not value:
        raise RuntimeError(category) from None


def entry():
    info = ENTRY.lstat()
    need(
        stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
        "ENTRY_FILE",
    )
    raw = ENTRY.read_bytes()
    need(len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == ENTRY_SHA, "ENTRY_PIN")
    ns = {"__name__": "_admission_prepared_definitions", "__file__": str(ENTRY)}
    exec(compile(raw, str(ENTRY), "exec"), ns)
    return ns


def state_for(task):
    need(type(task) is str and re.fullmatch(r"[0-9a-f]{32}", task), "TASK")
    definitions = entry()
    host = definitions["H"]
    policy = host["captured"](*host["SOURCES"]["profile"])[0]
    return {
        "kind": "maskgw-pg16-public-v1",
        "task": task,
        "phase": "FRESH",
        "invoked": False,
        "program_sha256": definitions["PROGRAM_SHA"],
        "v2_sha256": definitions["V2_SHA"],
        "host_sha256": definitions["HOST_SHA"],
        "entry_sha256": ENTRY_SHA,
        "pins": dict(definitions["R"]["LIBRARIES"].values()),
        "pg_pins": dict(host["SOURCES"].values()),
        "image": policy["IMAGE"],
        "create_measurement": policy["blueprint"](task)[1],
    }


def command_for(root):
    definitions = entry()
    need(
        type(root) is type(definitions["R"]["HOME"])
        and root.parent == definitions["R"]["HOME"] / "AppData/Local/Temp"
        and re.fullmatch(r"maskgw-pg16-public-20261030-[0-9a-f]{32}", root.name),
        "ROOT",
    )
    definitions["R"]["pinned"](PYTHON, PYTHON_SHA, 1048576)
    argv = (str(PYTHON), "-I", "-B", str(ENTRY), str(root))
    need(len(subprocess.list2cmdline(argv)) <= 26000, "COMMAND_SIZE")
    return argv


def materialize(root, task):
    command = command_for(root)
    state = state_for(task)
    definitions = entry()
    raw = definitions["R"]["json_bytes"](state)
    need(len(raw) <= 16384, "STATE_SIZE")
    root.mkdir(exist_ok=False)
    with (root / "attempt.json").open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {
        "root": str(root),
        "task": task,
        "state_sha256": hashlib.sha256(raw).hexdigest(),
        "state_bytes": len(raw),
        "entry_sha256": ENTRY_SHA,
        "command": list(command),
        "create_measurement": state["create_measurement"],
    }
