"""Closed public reader delivery. Definitions only; no native caller or private bytes."""

from dataclasses import dataclass, replace
import hashlib
from pathlib import Path
import stat

REPO = Path(__file__).resolve().parents[2]
OWNER = "docs/poc/pg16_shell_owner.py"
OWNER_SHA = "d671880078d6d1f30067400ae3d3169e17458c471467027835ba2be6897b6c8f"


def capture():
    raw, result = None, None
    path = REPO / OWNER
    try:
        info = path.lstat()
        if (
            stat.S_ISREG(info.st_mode)
            and not getattr(info, "st_file_attributes", 0) & 0x400
            and info.st_size <= 65536
        ):
            candidate = path.read_bytes()
            if (
                len(candidate) == info.st_size
                and hashlib.sha256(candidate).hexdigest() == OWNER_SHA
            ):
                raw = candidate
                namespace = {"__name__": "_pg16_delivery_owner", "__file__": str(path)}
                exec(compile(raw, str(path), "exec"), namespace)
                result = namespace
    except Exception:
        pass
    if result is None:
        raise RuntimeError("PG16_READER_DELIVERY_SOURCE") from None
    return result, raw


O, OWNER_RAW = capture()
C, R = O["C"], O["R"]


@dataclass(frozen=True)
class Delivery:
    """Configuration facts only, never syscall counts or receipt attestation."""

    case: str
    mode: str
    wire_bytes: int
    chunk_sizes: tuple[int, ...]
    hold_open: bool


def delivery_for(case):
    selected = None
    if type(case) is str and 0 < len(case) <= 32:
        try:
            selected = R["Case"](case)
        except Exception:
            pass
    if selected is None:
        raise RuntimeError("PG16_READER_DELIVERY_INPUT") from None
    original = R["vector"](selected)
    vector, mode = original, "EXACT_VECTOR"
    if original.fault is R["Code"].HEADER:
        wire = original.wire[:16]
        vector = replace(original, wire=wire, chunks=(wire,))
        mode = "HEADER_PREFIX"
    return vector, Delivery(
        selected.value, mode, len(vector.wire), tuple(map(len, vector.chunks)), vector.hold_open
    )


class PublicDeliveryOwner(O["PublicReaderOwner"]):
    def __init__(self, task, cid, case):
        vector, description = delivery_for(case)
        super().__init__(task, cid, vector.case)
        # Closed canary adaptation before any start; no change to the wrapper,
        # READY, parser, lifecycle, input method or result oracle.
        self._vector = vector
        self.delivery = description
