"""W1 entry of S for the adoption of ONE external job (XE2 under ER1-ER3, test 1835ba81).

Import only defines data, classes and functions. ``load_adoption()`` reads the fixed sibling
N-S module once (regular file, no final reparse point, bounded, size equal to the captured
bytes, exact SHA-256) and executes those SAME bytes with ``dont_inherit`` in a private
namespace; the trusted result is the frozen ``AdoptionLoad`` carrying the four N-S
definitions with their identities checked. Ordinary failures raise ``EntryLoadError``
(``ENTRY_LOAD``) without the original error; controls propagate before any acquisition.

``run_entry`` uses only the public Owner/N-S surface: setup before input, one bounded
ASCII record read until the true EOF, one adopt, one ack (exact write length, then flush),
start only after ADOPTED and local delivery, then one shared finite turn budget with at
most one ``wait(MAX_WAIT_MS)`` and one ``read()`` per turn. A turn after the positive exit
inventory ends with a FRESH ``available()`` call made after the inventory and after the
turn's read; only its ``None`` is EOF (the backend may answer it from its cached EOF).
Every public return is checked against its exact domain; anything else, any close that is
not None+CLOSED and any first control end in ``RETAIN`` without cleanup, with the caller's
``EntryCustody`` keeping every reference. The only write after a control is the single
``REFUSED CONTROL`` ack when ``adopt`` itself reported its retained first control.

Not admitted here: main, park, Request profile, argv, operational values, stdin/stdout
binding, native invocation. Author: Claude2 (session 51ea0d85), claude-opus-5-5/medium.
Senff policy: AI-generated code requires human and security review.
"""

from __future__ import annotations

import enum
import hashlib
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ADOPTION_NAME = "oracle9_w1_external_job_adoption.py"
ADOPTION_SHA = "465ae9067e0f24fe656259e3757f45e8a5788f55ed177db2ab82160d5b6ba5ae"
LOAD_LIMIT = 65536
MAX_TURNS = 400  # the qualifier's cap reused by XE2/ER2
_REPARSE_POINT = 0x400
_RECORD_LIMIT = 24  # a valid record has at most 23 bytes
_HEX = b"0123456789abcdef"
_INVALID = 0xFFFFFFFFFFFFFFFF
_DWORD = 0xFFFFFFFF
_KEYS = frozenset({"backend", "Request", "Win32Error", "ExternalJobOwner"})
_ACKS: dict[str, bytes] = {
    "ADOPTED": b"W1XA1 ADOPTED\n",
    "REFUSED_INPUT": b"W1XA1 REFUSED INPUT\n",
    "REFUSED_HANDLE": b"W1XA1 REFUSED HANDLE\n",
    "REFUSED_CONFIG": b"W1XA1 REFUSED CONFIG\n",
    "REFUSED_NOT_EMPTY": b"W1XA1 REFUSED NOT_EMPTY\n",
    "REFUSED_QUERY": b"W1XA1 REFUSED QUERY\n",
    "REFUSED_CONTROL": b"W1XA1 REFUSED CONTROL\n",
    "REFUSED_INTERNAL": b"W1XA1 REFUSED INTERNAL\n",
}


class EntryLoadError(Exception):
    """Closed refusal of ``load_adoption``: fixed args, never an original error or text."""

    def __init__(self) -> None:
        super().__init__("ENTRY_LOAD")


class EntryStage(enum.Enum):
    NEW = "NEW"
    CLAIMED = "CLAIMED"
    OWNER = "OWNER"
    SETUP = "SETUP"
    INPUT = "INPUT"
    ADOPT = "ADOPT"
    ACK = "ACK"
    START = "START"
    SUPERVISE = "SUPERVISE"
    DRAIN = "DRAIN"
    CLOSE = "CLOSE"
    DONE = "DONE"


@dataclass(frozen=True, slots=True, repr=False)
class AdoptionLoad:
    """Trusted carrier built only by ``load_adoption`` from ONE loaded N-S namespace."""

    definitions: dict[str, Any]
    backend: dict[str, Any]
    Request: type
    ExternalJobOwner: type
    Win32Error: type

    def __repr__(self) -> str:
        return "AdoptionLoad(<redacted>)"


@dataclass(slots=True, repr=False)
class EntryCustody:
    """Caller-owned strong custody; created empty, claimed once by ``run_entry``."""

    claimed: bool = False
    adoption: AdoptionLoad | None = None
    request: Any = None
    owner: Any = None
    reference: int | None = None
    adopt_result: str | None = None
    ack: str = "NOT_ATTEMPTED"
    output_bytes: int = 0
    first_error: Exception | None = None
    first_control: BaseException | None = None
    stage: EntryStage = EntryStage.NEW

    def __repr__(self) -> str:
        return "EntryCustody(<redacted>)"


# ---------------------------------------------------------------- pinned sibling loading


def _trusted(adoption: object) -> bool:
    """Exact carrier shape and identities; not a defence against privileged forgers."""
    if type(adoption) is not AdoptionLoad:
        return False
    definitions, backend = adoption.definitions, adoption.backend
    if type(definitions) is not dict or type(backend) is not dict or set(definitions) != _KEYS:
        return False
    owner_class = adoption.ExternalJobOwner
    limits = (backend.get("MAX_WAIT_MS"), backend.get("MAX_READ"))
    return (
        definitions["backend"] is backend
        and definitions["Request"] is adoption.Request is backend.get("Request")
        and definitions["Win32Error"] is adoption.Win32Error is backend.get("Win32Error")
        and definitions["ExternalJobOwner"] is owner_class
        and type(owner_class) is type
        and owner_class.__bases__ == (backend.get("Owner"),)
        and all(type(limit) is int and limit > 0 for limit in limits)
    )


def _carrier(definitions: object) -> AdoptionLoad | None:
    if type(definitions) is not dict or set(definitions) != _KEYS:
        return None
    backend = definitions["backend"]
    if type(backend) is not dict:
        return None
    carrier = AdoptionLoad(
        definitions=definitions,
        backend=backend,
        Request=definitions["Request"],
        ExternalJobOwner=definitions["ExternalJobOwner"],
        Win32Error=definitions["Win32Error"],
    )
    return carrier if _trusted(carrier) else None


def _load() -> AdoptionLoad | None:
    path = Path(__file__).resolve().parent / ADOPTION_NAME
    info = path.lstat()
    regular = stat.S_ISREG(info.st_mode) and info.st_size <= LOAD_LIMIT
    if not regular or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT:
        return None
    with path.open("rb") as stream:
        raw = stream.read(LOAD_LIMIT + 1)  # the ONE capture; nothing is read again
    if len(raw) != info.st_size or hashlib.sha256(raw).hexdigest() != ADOPTION_SHA:
        return None
    namespace: dict[str, Any] = {"__name__": "_xe_adoption", "__file__": str(path)}
    exec(compile(raw, str(path), "exec", dont_inherit=True), namespace)
    return _carrier(namespace["definitions"]())


def load_adoption() -> AdoptionLoad:
    """Explicit load; ordinary failures are closed, controls are never swallowed."""
    failed = False
    loaded: AdoptionLoad | None = None
    try:
        loaded = _load()
    except Exception:
        failed = True
    if failed or loaded is None:
        raise EntryLoadError()
    return loaded


# ---------------------------------------------------------------- one observed step


def _attempt(custody: EntryCustody, function: Callable[..., Any], *args: object) -> tuple[str, Any]:
    """Runs one public call; keeps the FIRST ordinary error and the FIRST control by identity.

    Nothing is called, converted or re-raised while handling them.
    """
    kind, value = "OK", None
    try:
        value = function(*args)
    except Exception as error:
        kind = "ERROR"
        if custody.first_error is None:
            custody.first_error = error
    except BaseException as control:
        kind = "CONTROL"
        if custody.first_control is None:
            custody.first_control = control
    return kind, value


def _empty(custody: object) -> bool:
    if type(custody) is not EntryCustody:
        return False
    return (
        custody.claimed is False
        and custody.adoption is None
        and custody.request is None
        and custody.owner is None
        and custody.reference is None
        and custody.adopt_result is None
        and type(custody.ack) is str
        and custody.ack == "NOT_ATTEMPTED"
        and type(custody.output_bytes) is int
        and custody.output_bytes == 0
        and custody.first_error is None
        and custody.first_control is None
        and custody.stage is EntryStage.NEW
    )


def _ports(reader: Any, writer: Any) -> tuple[Any, Any, Any]:
    return reader.read, writer.write, writer.flush  # captured ONCE


# ---------------------------------------------------------------- input and ack


def _parse(data: bytes) -> int | None:
    if len(data) < 8 or data[:6] != b"W1XT1 " or data[-1:] != b"\n":
        return None
    digits = data[6:-1]
    if not 1 <= len(digits) <= 16 or any(byte not in _HEX for byte in digits):
        return None
    value = int(digits.decode("ascii"), 16)
    return value if 0 < value < _INVALID else None


def _read_record(custody: EntryCustody, read: Callable[..., Any]) -> tuple[str, int | None]:
    """Reads only what is missing up to 24 bytes, until a true EOF (``b""``)."""
    data = b""
    while len(data) < _RECORD_LIMIT:
        want = _RECORD_LIMIT - len(data)
        kind, chunk = _attempt(custody, read, want)
        if kind == "CONTROL":
            return "CONTROL", None
        if kind != "OK" or type(chunk) is not bytes or len(chunk) > want:
            return "REFUSED", None
        if not chunk:
            return "EOF", _parse(data)
        data += chunk
    return "REFUSED", None  # 24 bytes: longer than any record


def _ack(custody: EntryCustody, ports: tuple[Any, Any, Any], line: bytes) -> bool:
    """ONE attempt, no retry; False only when a control interrupted it."""
    _read, write, flush = ports
    custody.stage = EntryStage.ACK
    kind, written = _attempt(custody, write, line)
    if kind != "OK" or type(written) is not int or written != len(line):
        custody.ack = "WRITE_FAILED"
        return kind != "CONTROL"
    kind, _flushed = _attempt(custody, flush)
    custody.ack = "DELIVERED_LOCAL" if kind == "OK" else "FLUSH_FAILED"
    return kind != "CONTROL"


# ---------------------------------------------------------------- release and supervision


def _closed(custody: EntryCustody, owner: Any) -> bool:
    custody.stage = EntryStage.CLOSE
    kind, value = _attempt(custody, owner.close)
    return kind == "OK" and value is None and owner.state == "CLOSED"


def _release(custody: EntryCustody, owner: Any, expected: str, delivered: str) -> str:
    """Branch without P: close only from the expected public state, else retain."""
    if owner.state != expected or not _closed(custody, owner):
        return "RETAIN"
    custody.stage = EntryStage.DONE
    return delivered if custody.ack == "DELIVERED_LOCAL" else "ACK_FAILED"


def _available_ok(value: object) -> bool:
    return value is None or (type(value) is int and 0 <= value <= _DWORD)


def _drain_once(custody: EntryCustody, owner: Any, max_read: int) -> bool:
    """One ``available`` and, when positive, the turn's single ``read``."""
    kind, available = _attempt(custody, owner.available)
    if kind != "OK" or not _available_ok(available):
        return False
    if available is None or available == 0:
        return True
    kind, chunk = _attempt(custody, owner.read)
    if kind != "OK" or type(chunk) is not bytes or len(chunk) > max_read:
        return False
    custody.output_bytes += len(chunk)  # counted, never retained
    return True


def _counts_ok(counts: object) -> bool:
    """ER3: P plus at most one helper over the job's life, none active."""
    return (
        type(counts) is tuple
        and len(counts) == 2
        and type(counts[0]) is int
        and type(counts[1]) is int
        and counts[0] in (1, 2)
        and counts[1] == 0
    )


def _inventory(custody: EntryCustody, owner: Any) -> int | None:
    """Exit code, accounting and members, in this order, after the first positive wait."""
    kind, code = _attempt(custody, owner.exit_code)
    if kind != "OK" or type(code) is not int or not 0 <= code <= _DWORD:
        return None
    kind, counts = _attempt(custody, owner.accounting)
    if kind != "OK" or not _counts_ok(counts):
        return None
    kind, members = _attempt(custody, owner.members)
    if kind != "OK" or type(members) is not tuple or len(members) != 0:
        return None
    return code


def _supervise(custody: EntryCustody, owner: Any, budget: int, backend: dict[str, Any]) -> str:
    wait_ms, max_read = backend["MAX_WAIT_MS"], backend["MAX_READ"]
    custody.stage = EntryStage.SUPERVISE
    code: int | None = None
    for _turn in range(budget):
        kind, signaled = _attempt(custody, owner.wait, wait_ms)
        if kind != "OK" or type(signaled) is not bool:
            return "RETAIN"
        if code is not None and not signaled:
            return "RETAIN"  # the exit is a retained fact: a later False is inconsistent
        if not _drain_once(custody, owner, max_read):
            return "RETAIN"
        if signaled and code is None:
            code = _inventory(custody, owner)
            if code is None:
                return "RETAIN"
            custody.stage = EntryStage.DRAIN
        if code is not None:
            # FRESH call after the positive inventory AND after this turn's read.
            kind, fresh = _attempt(custody, owner.available)
            if kind != "OK" or not _available_ok(fresh):
                return "RETAIN"
            if fresh is None:
                return _finish(custody, owner, code)
    return "RETAIN"


def _finish(custody: EntryCustody, owner: Any, code: int) -> str:
    if not _closed(custody, owner):
        return "RETAIN"
    custody.stage = EntryStage.DONE
    return "DONE" if code == 0 else "DONE_NONZERO"


# ---------------------------------------------------------------- the entry


def _adopt(custody: EntryCustody, owner: Any, ports: tuple[Any, Any, Any], budget: int) -> str:
    custody.stage = EntryStage.INPUT
    kind, reference = _read_record(custody, ports[0])
    if kind == "CONTROL":
        return "RETAIN"
    if reference is None:
        if not _ack(custody, ports, _ACKS["REFUSED_INPUT"]):
            return "RETAIN"
        return _release(custody, owner, "READY", "REFUSED")
    custody.reference = reference
    custody.stage = EntryStage.ADOPT
    kind, result = _attempt(custody, owner.adopt, reference)
    if kind != "OK" or type(result) is not str or result not in _ACKS:
        return "RETAIN"  # outside the eight closed results: no invented ack
    custody.adopt_result = result
    if result == "REFUSED_CONTROL":
        if custody.first_control is None:
            custody.first_control = owner.adopt_control  # the exact retained object
        _ack(custody, ports, _ACKS[result])  # the sole write after a control; no SDK
        return "RETAIN"
    if not _ack(custody, ports, _ACKS[result]):
        return "RETAIN"
    if result != "ADOPTED" or custody.ack != "DELIVERED_LOCAL":
        return _release(custody, owner, "READY", "REFUSED")
    custody.stage = EntryStage.START
    kind, value = _attempt(custody, owner.start)
    if kind != "OK" or value is not None or owner.state != "RUNNING":
        return "RETAIN"
    assert custody.adoption is not None
    return _supervise(custody, owner, budget, custody.adoption.backend)


def run_entry(
    adoption: Any, request: object, reader: Any, writer: Any, budget: object, custody: Any
) -> str:
    """Returns DONE, DONE_NONZERO, REFUSED, SETUP_REFUSED, ACK_FAILED, REJECTED or RETAIN.

    Never parks: on RETAIN the caller keeps ``custody`` (and everything in it) alive until
    the end of S; the future main owns the park.
    """
    if not (_empty(custody) and _trusted(adoption)):
        return "REJECTED"
    if type(request) is not adoption.Request or type(budget) is not int:
        return "REJECTED"
    if not 1 <= budget <= MAX_TURNS:
        return "REJECTED"
    custody.claimed = True
    custody.adoption, custody.request = adoption, request
    custody.stage = EntryStage.CLAIMED
    kind, ports = _attempt(custody, _ports, reader, writer)
    if kind != "OK":
        return "RETAIN"
    custody.stage = EntryStage.OWNER
    kind, owner = _attempt(custody, adoption.ExternalJobOwner, request)
    if kind != "OK" or type(owner) is not adoption.ExternalJobOwner:
        return "RETAIN"
    custody.owner = owner  # retained BEFORE setup
    custody.stage = EntryStage.SETUP
    kind, value = _attempt(custody, owner.setup)
    if kind == "CONTROL":
        return "RETAIN"
    if kind != "OK" or value is not None or owner.state != "READY":
        # Early ack before any input read: the record may stay unconsumed.
        if not _ack(custody, ports, _ACKS["REFUSED_INTERNAL"]):
            return "RETAIN"
        return _release(custody, owner, "SETUP_FAILED", "SETUP_REFUSED")
    return _adopt(custody, owner, ports, budget)
