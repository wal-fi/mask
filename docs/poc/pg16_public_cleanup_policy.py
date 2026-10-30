"""PG16 public cleanup identity adapter. No CLI, release authority or live rereads.

Trusted caller supplies the CID captured from create and current own inspect.
Rehydrates only cleanup fields, never an image admission or a create Intent.
"""

import hashlib
from pathlib import Path
import re
import stat

REPO = Path(__file__).resolve().parents[2]
PROFILE = "docs/poc/pg16_public_profile.py"
PROFILE_SHA = "fe2f8ba8bfabc5572fe7aeb85c31c54de38ceaa23c1a6c34dd631425371d9277"


def capture():
    path, raw = REPO / PROFILE, None
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
    except OSError:
        pass
    if raw is None:
        raise RuntimeError("PG16_PUBLIC_SOURCE") from None
    namespace = {"__name__": "_pg16_cleanup_profile", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace, raw


P, PROFILE_RAW = capture()
SOURCE, MANIFEST_SHA = P["SOURCE"], P["MANIFEST_SHA"]


def identity(info, *, task, command, cid):
    """Compare against captured CID, not one inferred from an untrusted inspect.

    No Env/image read or acceptance check is needed to remove an owned CID.
    No authority to mutate any resource is returned by this identity parser.
    """
    if hashlib.sha256(PROFILE_RAW).hexdigest() != PROFILE_SHA:
        raise RuntimeError("PG16_PUBLIC_SOURCE") from None
    if (
        type(task) is not str
        or re.fullmatch(r"[0-9a-f]{32}", task) is None
        or type(command) is not tuple
        or len(command) != 2
        or not all(type(item) is str for item in command)
        or command != ("-ec", "TASK='" + task + "'\n" + SOURCE)
    ):
        raise RuntimeError("PG16_PUBLIC_OWNERSHIP") from None
    labels = dict(
        zip(
            P["OWN_KEYS"],
            (task, hashlib.sha256(command[1].encode("ascii")).hexdigest(), MANIFEST_SHA),
            strict=True,
        )
    )
    # This LOCAL object is never returned or used to create/start anything.
    # The pinned identity method reads exactly these captured fields, no image Env.
    intent = object.__new__(P["Intent"])
    for key, value in {
        "task": task,
        "image": None,
        "command": command,
        "labels": tuple(sorted(labels.items())),
        "source_sha256": labels["maskgw.source-sha256"],
        "name": "maskgw-ol9-pg16-admit-" + task[:12],
    }.items():
        object.__setattr__(intent, key, value)
    accepted = False
    try:
        accepted = P["identity"](info, intent, cid) == cid
    except Exception:
        pass
    if not accepted:
        raise RuntimeError("PG16_PUBLIC_OWNERSHIP") from None
    return cid
