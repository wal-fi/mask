"""Reader-specific cleanup identity adapter. No native effect or release authority."""

import hashlib
from pathlib import Path
import re
import stat

REPO = Path(__file__).resolve().parents[2]
PROFILE = "docs/poc/pg16_shell_profile.py"
PROFILE_SHA = "8906e846a792d7aa01bc53da000e35815ba20a9ffee4a7fb8705b19b1b630912"


def capture():
    raw, namespace = None, None
    path = REPO / PROFILE
    try:
        info = path.lstat()
        if (
            stat.S_ISREG(info.st_mode)
            and not getattr(info, "st_file_attributes", 0) & 0x400
            and info.st_size <= 65536
        ):
            value = path.read_bytes()
            if len(value) == info.st_size and hashlib.sha256(value).hexdigest() == PROFILE_SHA:
                raw = value
                candidate = {"__name__": "_pg16_reader_cleanup", "__file__": str(path)}
                exec(compile(raw, str(path), "exec"), candidate)
                namespace = candidate
    except Exception:
        pass
    if namespace is None:
        raise RuntimeError("PG16_READER_SOURCE") from None
    return namespace, raw


P, PROFILE_RAW = capture()


def _shape(info):
    """Exact JSON types prevent overloaded equality/hooks in ownership comparisons."""
    if type(info) is not dict or not all(type(key) is str for key in info):
        return False
    if not all(type(info.get(key)) is str for key in ("Id", "Name", "Image")):
        return False
    config = info.get("Config")
    if type(config) is not dict or not all(type(key) is str for key in config):
        return False
    if type(config.get("Image")) is not str:
        return False
    for key, count in (("Cmd", 2), ("Entrypoint", 1)):
        values = config.get(key)
        if (
            type(values) is not list
            or len(values) != count
            or not all(type(v) is str for v in values)
        ):
            return False
    labels = config.get("Labels")
    return (
        type(labels) is dict
        and all(type(key) is str for key in labels)
        and all(type(labels.get(key)) is str for key in P["OWN_KEYS"])
    )


def identity(info, *, task, case, command, cid):
    """No image admission, live rereads, CLI, Intent export or cleanup authority."""
    if (
        type(PROFILE_RAW) is not bytes
        or len(PROFILE_RAW) > 65536
        or hashlib.sha256(PROFILE_RAW).hexdigest() != PROFILE_SHA
    ):
        raise RuntimeError("PG16_READER_SOURCE") from None
    accepted = False
    try:
        if (
            type(task) is str
            and re.fullmatch(r"[0-9a-f]{32}", task)
            and type(case) is str
            and 0 < len(case) <= 32
            and type(command) is tuple
            and len(command) == 2
            and all(type(item) is str for item in command)
            and len(command[1]) <= 12000
            and type(cid) is str
            and re.fullmatch(r"[0-9a-f]{64}", cid)
            and _shape(info)
        ):
            selected = P["R"]["Case"](case)
            name, captured_command, labels, source_sha = P["_capture"](task, selected)
            if command == captured_command:
                # Local cleanup-only object; image facts are deliberately absent.
                # Never returned or passed to a create/start/admission path.
                intent = object.__new__(P["Intent"])
                for key, value in {
                    "task": task,
                    "image": None,
                    "case": selected,
                    "command": captured_command,
                    "labels": labels,
                    "source_sha256": source_sha,
                    "core_sha256": P["R"]["CORE_SHA"],
                    "name": name,
                }.items():
                    object.__setattr__(intent, key, value)
                accepted = P["identity"](info, intent, cid) == cid
    except Exception:
        pass
    if not accepted:
        raise RuntimeError("PG16_READER_OWNERSHIP") from None
    return cid
