"""Pure PG16 lab volume decisions. No CLI, ownership authority or operational caller.

Caller MUST prove own CID/inspect binding first, record this decision before
removal, and prove fresh final inventories plus CID absence independently.
This module never grants start, removal authority, release or Desktop stop.
"""

from dataclasses import dataclass
from enum import StrEnum
import re

MAX_BYTES = 65536
MAX_VOLUMES = 256
MAX_MOUNTS = 32
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}\Z")


class VolumeFault(Exception):
    def __init__(self):
        super().__init__("VOLUME_INVENTORY")


class Mode(StrEnum):
    WITH_V = "WITH_V"
    PRESERVE_EXISTING = "PRESERVE_EXISTING"
    PRESERVE_UNCERTAIN = "PRESERVE_UNCERTAIN"


@dataclass(frozen=True)
class Decision:
    mode: Mode
    names: tuple[str, ...]
    preexisting: tuple[str, ...]


@dataclass(frozen=True)
class Difference:
    added: tuple[str, ...]
    missing: tuple[str, ...]


def valid_name(value):
    return type(value) is str and NAME.fullmatch(value) is not None


def inventory(raw):
    """Parse public `volume ls -q` stdout; caller separately verifies exit/freshness."""
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        raise VolumeFault() from None
    if not raw:
        return frozenset()
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeError:
        raise VolumeFault() from None
    if (
        not 0 < len(lines) <= MAX_VOLUMES
        or not all(valid_name(line) for line in lines)
        or len(set(lines)) != len(lines)
        or not raw.endswith(b"\n")
        or raw.replace(b"\r\n", b"\n") != ("\n".join(lines) + "\n").encode("ascii")
    ):
        raise VolumeFault() from None
    return frozenset(lines)


def checked(values):
    if (
        type(values) is not frozenset
        or len(values) > MAX_VOLUMES
        or not all(valid_name(value) for value in values)
    ):
        raise VolumeFault() from None
    return values


def removal(initial, mounts):
    """Use ONLY own-CID inspect Mounts after ownership proof, never image Mounts.

    WITH_V selects Docker rm -v for that CID, never direct volume rm. Named
    volumes survive -v. Any uncertainty prohibits -v and requires reconciliation.
    A preexisting anonymous volume is protected exactly like a named volume.
    """
    initial = checked(initial)
    if type(mounts) is not list or len(mounts) > MAX_MOUNTS:
        return Decision(Mode.PRESERVE_UNCERTAIN, (), ())
    names = set()
    for mount in mounts:
        if type(mount) is not dict or mount.get("Type") not in ("volume", "tmpfs", "bind"):
            return Decision(Mode.PRESERVE_UNCERTAIN, (), ())
        if mount["Type"] == "volume":
            name = mount.get("Name")
            if not valid_name(name):
                return Decision(Mode.PRESERVE_UNCERTAIN, (), ())
            names.add(name)
    observed = tuple(sorted(names))
    preexisting = tuple(sorted(names & initial))
    return Decision(Mode.PRESERVE_EXISTING if preexisting else Mode.WITH_V, observed, preexisting)


def difference(initial, final):
    """Facts only, no resource release. Caller must retain HELD on any difference."""
    initial, final = checked(initial), checked(final)
    return Difference(tuple(sorted(final - initial)), tuple(sorted(initial - final)))
