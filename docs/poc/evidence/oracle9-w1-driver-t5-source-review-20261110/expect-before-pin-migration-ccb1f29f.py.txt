"""EXPECT generator contract over public masking/encoder APIs; RED-first, no effect.

Contract for the FUTURE ``docs/poc/oracle9_w1_expect.py`` (EXPECT-DESIGN v1 f9bd9c48
plus EXPECT-DESIGN-REVIEW precisions 1-10, which override the v1 open points). The
module stays absent until the root reviews these oracles; every feature case loads it
inside ``gen()`` (cached runpy, run_name "_lab_test_expect"), so absence fails at
execution, never at collection. The ``test_sanity_*`` cases never load it.

Stable API expected from the runpy namespace:

- Constants: ``CANARY_COUNT`` 4; ``RESULT_JOBS`` (1..10, 12, 17, 19); ``ERRORS``
  {11 LIMIT, 13/14/15 QUERY, 16 TIMEOUT, 18 TYPE}; ``POLICY_MAPPING`` (local literal
  that DatasourcePolicy normalizes to the pinned pure ``_lab_policy(1)``).
- ``ExpectRefusal(category)``: Exception, ``args == (category,)``, ``.category`` in
  INPUT/MODEL/ENCODE/SIZE, never a cause/context, even inside a caller handler.
- ``ExpectRecord(*, job, kind, rows, bytes, sha256, reason)``: frozen slotted
  dataclass with exactly these six fields, validated in the constructor (exact
  types, job/kind/reason coherent with ERRORS, RESULT rows 0..1000, bytes
  1..F-76, sha256 lowercase hex64); invalid -> ExpectRefusal("INPUT");
  ``repr`` == "ExpectRecord(<redacted>)".
- ``seed_sql(canaries) -> bytes``; ``result_body(job, *, hmac_key, canaries) ->
  bytes``; ``expected_records(*, hmac_key, canaries) -> tuple[ExpectRecord, ...]``;
  ``lab_init_packet(*, ip, port, database, username, readonly_password, hmac_key,
  canaries) -> bytes`` (no records input: it derives them from the same key/canaries).
- The module imports ``encode_result`` by name; tests replace that module-global
  name with a delegating spy to observe descriptors/decisions/OIDs/identity.
- The module imports ``MappingSecretProvider`` by name (maskgw.secretsource) and
  builds exactly one per ``result_body`` call from ``{HMAC_KEY_ENV: hmac_key}``;
  tests replace that module-global name with a spy delegating to the real public
  class. The process environment is never read nor mutated by these tests.

Oracles: exact bytes come from independent-vectors.json (root, stdlib only) and
from stdlib hmac/struct in this file, never from the generator or the encoder.
Shared engine/encoder agreement is consistency only; PostgreSQL order (jobs 5/6/7),
CTE provenance and the ERROR categories 13/16/18 stay native hypotheses.

Harness limits: no real socket/thread/process/signal/guard/Docker/PG/SQL. Guards are
module-namespace seams, AST checks of the source and a temporary RandomTransformer
tripwire; stdlib and SDK algorithms are never patched. MODEL and SIZE are not driven
at runtime (no injection API by design); only their closed category names are fixed.
The retention guard walks only the module's own globals through exact builtin
containers (bounded depth/nodes, cycles by identity, no foreign callbacks); it is not
a heap, closure, cache-wrapper or zeroization proof.
"""

from __future__ import annotations

import ast
import dataclasses
import functools
import hashlib
import hmac
import inspect
import json
import runpy
import struct
import traceback
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from maskgw.datasource.models import DatasourcePolicy
from maskgw.db.result import MaskedResult, TypedMaskedResult
from maskgw.masking.descriptor import ColumnDescriptor, ProvenanceKind
from maskgw.masking.engine import Action, Decision
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.masking.transformers.randomize import RandomTransformer
from maskgw.pgwire.result_encoder import EncodeError, EncodeFailure, encode_result
from maskgw.pgwire.result_frame import (
    ResultDeadline,
    ResultIdentity,
    ResultLimits,
    validate_result,
)
from maskgw.secretsource import MappingSecretProvider

REPO = Path(__file__).resolve().parents[1]
GEN_FILE = REPO / "docs/poc/oracle9_w1_expect.py"
VECTORS_FILE = REPO / "docs/poc/evidence/oracle9-w1-expect-review-20261109/independent-vectors.json"
PURE_FILE = REPO / "deploy/oracle9_w1_controller.py"
PURE_SHA = "4c155d76208f113852f95fec4c57253eef480c610aa390423fa6f82baf1f7bc7"
PURE_SIZE = 22453
DRIVER_FILE = REPO / "deploy/oracle9_w1_driver.py"
DRIVER_SHA = "39a6890457c3bc9331fc371948fce896cbbc37e2d49f1584a5629490f43d2794"
DRIVER_SIZE = 36956

MIB = 1024 * 1024
FRAME_LIMIT = 16 * MIB
SINK_CAP = FRAME_LIMIT - 76
SINK_CHUNK = 65536
HEADER = struct.Struct("!4sBBH16s16sQQQIII")
INIT_HEADER = struct.Struct(">4sI")
COLUMN = struct.Struct("!IhIhih")
U16 = struct.Struct("!H")
U32 = struct.Struct("!I")
I32 = struct.Struct("!i")
DATASOURCE = bytes.fromhex("0" * 31 + "1")
TYPLEN = {16: 1, 23: 4, 25: -1}

KEY = "0123456789abcdef" * 4
KEY2 = "fedcba9876543210" * 4
CANARIES = ("ABCDEFGHIJKLMNOP", "BCDEFGHIJKLMNOPQ", "CDEFGHIJKLMNOPQR", "DEFGHIJKLMNOPQRS")
CANARIES2 = ("QRSTUVWXYZ012345", "RSTUVWXYZ0123456", "STUVWXYZ01234567", "TUVWXYZ012345678")
PASSWORD = "0123456789abcdef" * 3  # valid and deliberately a substring of KEY
IP = "10.0.0.7"
PORT = 5432
DATABASE = "maskgw_lab"
USERNAME = "maskgw_ro"
MARKER = "SYNTHETIC-CALLER-MARKER-7f3a"

HMAC_C0 = "a9745149ad94f4460daff322d00912444b9e506bef7d63d1f2843399b3f5e695"
HMAC_C1 = "0d124adf6bbaa297b2fae12e245088439d3d55717a641673eaa0cdc4eb60c1ac"
SELECT1_HEX = (
    "540000002100013f636f6c756d6e3f00"
    "000000000000000000170004ffffffff0000"
    "440000000b00010000000131"
    "430000000d53454c454354203100"
)
SELECT1_SHA = "aa19842a612ea62536e94011790cd8c6a8b7e8c0d5c9bb1557daf2a5ecd99420"
JOB2_HEX = (
    "540000001c00016370660000000000000000000019ffffffffffff0000"
    "440000004a000100000040"
    "6139373435313439616439346634343630646166663332326430303931323434"
    "3462396535303662656637643633643166323834333339396233663565363935"
    "440000004a000100000040"
    "3064313234616466366262616132393762326661653132653234353038383433"
    "3964336435353731376136343136373365616130636463346562363063316163"
    "440000000a0001ffffffff"
    "430000000d53454c454354203300"
)
JOB2_SHA = "169b93d9914e1987d390d8181efe154a02d0086bcc68a2a7ffa1f42f8bc704f0"
JOB10_BYTES = 15728847  # 27 + 15 * (1048576 + 11) + 15, D-113 layout
DATA_OFFSET = 45  # T(34) + D tag/len/count/cell-len (11): the single data byte

SEED_LINES = (
    "begin;",
    "create schema maskgw_lab;",
    "create domain maskgw_lab.label as text;",
    "create table maskgw_lab.t (id integer, cpf text, tipo_cpf text, email text, "
    "numeric_secret numeric, amount numeric, token text, active boolean, "
    "label maskgw_lab.label);",
    "insert into maskgw_lab.t (id, cpf, tipo_cpf, email, numeric_secret, amount, "
    "token, active, label) values "
    "(1, 'ABCDEFGHIJKLMNOP', 'physical', 'CDEFGHIJKLMNOPQR@example.test', 123, 19.5, "
    "'secret1', true, 'label1'), "
    "(2, 'BCDEFGHIJKLMNOPQ', 'company', 'DEFGHIJKLMNOPQRS@example.test', 456, 99.5, "
    "'secret2', false, 'label2'), "
    "(3, null, null, null, null, null, null, null, null);",
    "commit;",
)
SEED_FIXED = ("\n".join(SEED_LINES) + "\n").encode("ascii")

RESULT_JOBS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 17, 19)
ERRORS = {11: "LIMIT", 13: "QUERY", 14: "QUERY", 15: "QUERY", 16: "TIMEOUT", 18: "TYPE"}
ROWS = {1: 3, 2: 3, 3: 1, 4: 3, 5: 2, 6: 3, 7: 3, 8: 3, 9: 1000, 10: 15, 12: 1, 17: 1, 19: 1}
QCOL = (("?column?", 23),)
COLUMNS: dict[int, tuple[tuple[str, int], ...]] = {
    1: (("id", 23), ("active", 16)),
    2: (("cpf", 25),),
    3: (("tipo_cpf", 25), ("cpf", 25)),
    4: (("same", 25), ("same", 25), ("active", 16), ("id", 23)),
    5: (("cpf", 25),),
    6: (("x", 25),),
    7: (("x", 25),),
    8: (("numeric_secret", 25),),
    9: (("g", 23),),
    10: (("v", 25),),
    12: QCOL,
    17: QCOL,
    19: QCOL,
}
HMAC_NAME, REGEX_NAME, FIXED_NAME = "hmac_sha256", "regex", "fixed"


def direct(name: str, origin: str) -> ColumnDescriptor:
    return ColumnDescriptor(name, origin, "maskgw_lab", "t", ProvenanceKind.DIRECT, None)


def derived(name: str, rule: int | None) -> ColumnDescriptor:
    return ColumnDescriptor(name, None, None, None, ProvenanceKind.DERIVED, rule)


def allow(column: ColumnDescriptor) -> tuple[ColumnDescriptor, Decision]:
    return column, Decision(Action.ALLOW, column.output_name, column.origin_name)


def mask(column: ColumnDescriptor, rule: int, name: str) -> tuple[ColumnDescriptor, Decision]:
    return column, Decision(Action.MASK, column.output_name, column.origin_name, rule, name)


def exempt(column: ColumnDescriptor, index: int) -> tuple[ColumnDescriptor, Decision]:
    return column, Decision(Action.EXCEPTION, column.output_name, column.origin_name, index)


# Reviewed provenance: from the table, never from aliases. Job 6 origin is a native hypothesis.
MODEL: dict[int, tuple[tuple[ColumnDescriptor, Decision], ...]] = {
    1: (allow(direct("id", "id")), allow(direct("active", "active"))),
    2: (mask(direct("cpf", "cpf"), 0, HMAC_NAME),),
    3: (mask(direct("tipo_cpf", "cpf"), 0, HMAC_NAME), exempt(direct("cpf", "tipo_cpf"), 0)),
    4: (
        mask(derived("same", 0), 0, HMAC_NAME),
        mask(direct("same", "email"), 1, REGEX_NAME),
        allow(direct("active", "active")),
        allow(direct("id", "id")),
    ),
    5: (mask(derived("cpf", 0), 0, HMAC_NAME),),
    6: (mask(direct("x", "cpf"), 0, HMAC_NAME),),
    7: (mask(direct("x", "email"), 1, REGEX_NAME),),
    8: (mask(direct("numeric_secret", "numeric_secret"), 2, FIXED_NAME),),
    9: (allow(derived("g", None)),),
    10: (allow(derived("v", None)),),
    12: (allow(derived("?column?", None)),),
    17: (allow(derived("?column?", None)),),
    19: (allow(derived("?column?", None)),),
}


# ---------------------------------------------------------------- loaders and oracles


def pinned(path: Path, sha: str, size: int) -> dict[str, Any]:
    raw = path.read_bytes()
    assert len(raw) == size
    assert hashlib.sha256(raw).hexdigest() == sha
    return runpy.run_path(str(path))


@functools.cache
def pure() -> dict[str, Any]:
    return pinned(PURE_FILE, PURE_SHA, PURE_SIZE)


@functools.cache
def driver() -> dict[str, Any]:
    return pinned(DRIVER_FILE, DRIVER_SHA, DRIVER_SIZE)


@functools.cache
def gen() -> dict[str, Any]:
    return runpy.run_path(str(GEN_FILE), run_name="_lab_test_expect")


@functools.cache
def records(key: str, canaries: tuple[str, ...]) -> tuple[Any, ...]:
    result: tuple[Any, ...] = gen()["expected_records"](hmac_key=key, canaries=canaries)
    return result


def body(job: int, key: str = KEY, canaries: tuple[str, ...] = CANARIES) -> bytes:
    data: bytes = gen()["result_body"](job, hmac_key=key, canaries=canaries)
    return data


def packet(key: str = KEY, canaries: tuple[str, ...] = CANARIES, **overrides: Any) -> bytes:
    fields: dict[str, Any] = {
        "ip": IP,
        "port": PORT,
        "database": DATABASE,
        "username": USERNAME,
        "readonly_password": PASSWORD,
        "hmac_key": key,
        "canaries": canaries,
    }
    fields.update(overrides)
    data: bytes = gen()["lab_init_packet"](**fields)
    return data


def fields_of(record: Any) -> tuple[Any, ...]:
    return (record.job, record.kind, record.rows, record.bytes, record.sha256, record.reason)


Cells = list[tuple[bytes | None, ...]]


def h(key: str, text: str) -> bytes:
    digest = hmac.new(key.encode("ascii"), text.encode("ascii"), hashlib.sha256)
    return digest.hexdigest().encode("ascii")


def m(local: str) -> bytes:
    return (local[:2] + "***@example.test").encode("ascii")


def expected_cells(key: str, canaries: tuple[str, ...]) -> dict[int, Cells]:
    c0, c1, c2, c3 = canaries
    return {
        1: [(b"1", b"t"), (b"2", b"f"), (b"3", None)],
        2: [(h(key, c0),), (h(key, c1),), (None,)],
        3: [(h(key, c0), b"physical")],
        4: [
            (h(key, c0[:3]), m(c2), b"t", b"1"),
            (h(key, c1[:3]), m(c3), b"f", b"2"),
            (None, None, None, b"3"),
        ],
        5: [(h(key, c0),), (h(key, c1),)],
        6: [(h(key, c0),), (h(key, c1),), (None,)],
        7: [(m(c2),), (m(c3),), (None,)],
        8: [(b"[NUMBER]",), (b"[NUMBER]",), (None,)],
        9: [(str(value).encode("ascii"),) for value in range(1, 1001)],
        12: [(b"1",)],
        17: [(b"2",)],
        19: [(b"3",)],
    }


def parse(data: bytes) -> tuple[list[tuple[str, int, int]], Cells, bytes]:
    """Independent T/D/C reader (stdlib struct only); asserts D-113 fixed fields."""
    assert data[:1] == b"T"
    end = 1 + U32.unpack_from(data, 1)[0]
    count = U16.unpack_from(data, 5)[0]
    offset, columns = 7, []
    for _ in range(count):
        zero = data.index(b"\0", offset, end)
        name = data[offset:zero].decode("utf-8")
        table, attnum, oid, typlen, typmod, fmt = COLUMN.unpack_from(data, zero + 1)
        assert (table, attnum, typmod, fmt) == (0, 0, -1, 0)
        columns.append((name, oid, typlen))
        offset = zero + 1 + COLUMN.size
    assert offset == end
    rows: Cells = []
    while data[offset : offset + 1] == b"D":
        end = offset + 1 + U32.unpack_from(data, offset + 1)[0]
        assert U16.unpack_from(data, offset + 5)[0] == count
        offset += 7
        cells: list[bytes | None] = []
        for _ in range(count):
            size = I32.unpack_from(data, offset)[0]
            offset += 4
            if size == -1:
                cells.append(None)
            else:
                cells.append(data[offset : offset + size])
                offset += size
        assert offset == end
        rows.append(tuple(cells))
    assert data[offset : offset + 1] == b"C"
    end = offset + 1 + U32.unpack_from(data, offset + 1)[0]
    assert end == len(data)
    return columns, rows, data[offset + 5 : end]


def job2_body(first: bytes, second: bytes) -> bytes:
    """Job 2 D-113 body assembled with stdlib struct from two 64-byte HMAC hex cells."""
    text_column = b"cpf\0" + COLUMN.pack(0, 0, 25, -1, -1, 0)
    assembled = b"T" + U32.pack(4 + 2 + len(text_column)) + U16.pack(1) + text_column
    for cell in (first, second):
        assembled += b"D" + U32.pack(4 + 2 + 4 + 64) + U16.pack(1) + I32.pack(64) + cell
    assembled += b"D" + U32.pack(10) + U16.pack(1) + I32.pack(-1)
    return assembled + b"C" + U32.pack(4 + 9) + b"SELECT 3\0"


RETAIN_DEPTH = 8
RETAIN_NODES = 100_000
CONTAINERS = (dict, list, tuple, set, frozenset)


def retained(namespace: dict[str, object], needles: tuple[str, ...]) -> list[str]:
    """Findings in a namespace's own values, exact builtin containers only.

    Dunder metadata is skipped; modules, functions, classes and any foreign object are
    never inspected (no getattr, __dict__, hash, eq or iteration of non-exact types).
    Cycles are tracked by identity; exceeding depth/node bounds is itself a finding.
    """
    raw = tuple(needle.encode("ascii") for needle in needles)
    stack: list[tuple[object, int]] = [
        (value, 0) for name, value in namespace.items() if not name.startswith("__")
    ]
    seen: set[int] = set()
    findings: list[str] = []
    nodes = 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > RETAIN_NODES or depth > RETAIN_DEPTH:
            findings.append("LIMIT")
            break
        kind = type(value)
        if kind is str and isinstance(value, str):
            if any(needle in value for needle in needles):
                findings.append("TEXT")
        elif (kind is bytes or kind is bytearray) and isinstance(value, bytes | bytearray):
            if len(value) > SINK_CHUNK:
                findings.append("BODY")
            if any(needle in value for needle in raw):
                findings.append("BYTES")
        elif any(kind is container for container in CONTAINERS) and id(value) not in seen:
            seen.add(id(value))
            if kind is dict and isinstance(value, dict):
                stack.extend((item, depth + 1) for item in (*value.keys(), *value.values()))
            elif isinstance(value, list | tuple | set | frozenset):
                stack.extend((item, depth + 1) for item in value)
    return findings


def frame_of(job: int, data: bytes) -> bytes:
    columns, rows = len(COLUMNS[job]), ROWS[job]
    header = HEADER.pack(
        b"MGWR", 1, int(job == 9), 0, bytes(16), DATASOURCE, 1, 1, job, columns, rows, len(data)
    )
    return header + data


def zero_clock() -> float:
    return 0.0


def fixed_deadline() -> ResultDeadline:
    return ResultDeadline(expires_at=1.0, clock=zero_clock)


def limits() -> ResultLimits:
    return ResultLimits(max_rows=1000, max_frame_bytes=FRAME_LIMIT)


def identity(job: int) -> ResultIdentity:
    return ResultIdentity(
        session_id=bytes(16),
        datasource_id=DATASOURCE,
        generation=1,
        record_revision=1,
        job_id=job,
    )


class FixedClock:
    def monotonic(self) -> float:
        return 0.0


def chunk_reader(data: bytes) -> Callable[..., bytes | None]:
    position = [0]

    def read(limit: int, *, deadline: float) -> bytes | None:
        assert deadline == 1.0
        start = position[0]
        if start >= len(data):
            return None
        piece = data[start : start + min(limit, SINK_CHUNK)]
        position[0] = start + len(piece)
        return piece

    return read


def drain(data: bytes, expected_bytes: int, expected_sha: str) -> Any:
    return driver()["sink_drain"](
        chunk_reader(data),
        expected_bytes=expected_bytes,
        expected_sha256=expected_sha,
        cap=SINK_CAP,
        chunk=SINK_CHUNK,
        deadline=1.0,
        clock=FixedClock(),
    )


CALLS: list[str] = []


class StrProbe(str):
    """Foreign value whose callbacks must never run before the exact-type refusal."""

    def __eq__(self, value: object, /) -> bool:
        CALLS.append("eq")
        return str.__eq__(self, value)

    def __ne__(self, value: object, /) -> bool:
        CALLS.append("ne")
        return str.__ne__(self, value)

    def __hash__(self) -> int:
        CALLS.append("hash")
        return str.__hash__(self)

    def __len__(self) -> int:
        CALLS.append("len")
        return str.__len__(self)

    def __contains__(self, key: object, /) -> bool:
        CALLS.append("contains")
        if type(key) is not str or not isinstance(key, str):
            return False
        return str.__contains__(self, key)

    def isascii(self) -> bool:
        CALLS.append("isascii")
        return str.isascii(self)

    def encode(self, encoding: str = "utf-8", errors: str = "strict") -> bytes:
        CALLS.append("encode")
        return str.encode(self, encoding, errors)


class IntProbe(int):
    def __eq__(self, value: object, /) -> bool:
        CALLS.append("eq")
        return int.__eq__(self, value)

    def __ne__(self, value: object, /) -> bool:
        CALLS.append("ne")
        return int.__ne__(self, value)

    def __hash__(self) -> int:
        CALLS.append("hash")
        return int.__hash__(self)

    def __index__(self) -> int:
        CALLS.append("index")
        return int.__index__(self)

    def __lt__(self, value: int, /) -> bool:
        CALLS.append("lt")
        return int.__lt__(self, value)

    def __le__(self, value: int, /) -> bool:
        CALLS.append("le")
        return int.__le__(self, value)


class TupleProbe(tuple[str, ...]):
    def __len__(self) -> int:
        CALLS.append("len")
        return tuple.__len__(self)

    def __iter__(self) -> Iterator[str]:
        CALLS.append("iter")
        return tuple.__iter__(self)


def refused(category: str, call: Callable[[], object]) -> None:
    """Closed refusal raised while a caller handler is active: no chain, no marker."""
    refusal = gen()["ExpectRefusal"]
    CALLS.clear()
    try:
        raise LookupError(MARKER)
    except LookupError:
        with pytest.raises(refusal) as info:
            call()
    error = info.value
    assert type(error) is refusal
    assert error.args == (category,)
    assert str(error) == category
    assert error.category == category
    assert error.__cause__ is None
    assert error.__context__ is None
    rendered = "".join(traceback.format_exception(error))
    for secret in (MARKER, KEY, PASSWORD, *CANARIES):
        assert secret not in rendered
        assert secret not in repr(error)
    assert CALLS == []


# ---------------------------------------------------------------- sanity (no generator)


def test_sanity_vectors_file_matches_fixed_literals() -> None:
    vectors = json.loads(VECTORS_FILE.read_text(encoding="ascii"))
    assert vectors["test_hmac_key"] == KEY
    assert tuple(vectors["canaries"]) == CANARIES
    assert vectors["hmac_c0"] == HMAC_C0
    assert vectors["hmac_c1"] == HMAC_C1
    assert vectors["select1_body_hex"] == SELECT1_HEX
    assert vectors["select1_body_bytes"] == 60
    assert vectors["select1_body_sha256"] == SELECT1_SHA
    assert vectors["job2_body_hex"] == JOB2_HEX
    assert vectors["job2_body_bytes"] == 204
    assert vectors["job2_body_sha256"] == JOB2_SHA
    assert vectors["job10_body_bytes"] == JOB10_BYTES


def test_sanity_vectors_independent_stdlib_checks() -> None:
    assert h(KEY, CANARIES[0]).decode() == HMAC_C0
    assert h(KEY, CANARIES[1]).decode() == HMAC_C1
    select1 = bytes.fromhex(SELECT1_HEX)
    job2 = bytes.fromhex(JOB2_HEX)
    assert (len(select1), hashlib.sha256(select1).hexdigest()) == (60, SELECT1_SHA)
    assert (len(job2), hashlib.sha256(job2).hexdigest()) == (204, JOB2_SHA)
    assert job2_body(HMAC_C0.encode(), HMAC_C1.encode()) == job2
    assert parse(select1) == ([("?column?", 23, 4)], [(b"1",)], b"SELECT 1\0")
    assert select1[DATA_OFFSET : DATA_OFFSET + 1] == b"1"
    assert JOB10_BYTES == 27 + 15 * (MIB + 11) + 15 <= SINK_CAP


def test_sanity_public_encoder_preflight_limits_17_rows() -> None:
    """17 x 1 MiB exceeds F in the encoder preflight; NOT a claim about PG job 11."""
    value = "x" * MIB  # one shared object, never 17 copies
    column = derived("v", None)
    decision = Decision(Action.ALLOW, "v")

    def typed(rows: int) -> TypedMaskedResult:
        masked = MaskedResult((column,), (decision,), tuple((value,) for _ in range(rows)))
        return TypedMaskedResult(masked, (25,))

    deadline = fixed_deadline()
    with pytest.raises(EncodeError) as info:
        encode_result(typed(17), identity=identity(11), limits=limits(), deadline=deadline)
    assert info.value.category is EncodeFailure.LIMIT
    frame = encode_result(typed(15), identity=identity(10), limits=limits(), deadline=deadline)
    assert len(frame) - HEADER.size == JOB10_BYTES


def test_sanity_seed_literal_shape() -> None:
    text = SEED_FIXED.decode("ascii")
    assert text.endswith("\n") and "\r" not in text
    assert text.splitlines() == list(SEED_LINES)
    stripped = text
    for canary in CANARIES:
        assert text.count(canary) == 1
        stripped = stripped.replace(canary, "")
    assert stripped == stripped.lower()
    for forbidden in (KEY, PASSWORD, "role", "grant", "password"):
        assert forbidden not in text


def test_sanity_pinned_collaborators_load() -> None:
    assert callable(pure()["decode_init"])
    assert callable(pure()["_lab_policy"])
    assert callable(driver()["sink_drain"])


# ---------------------------------------------------------------- API shape


def test_api_constants_and_signatures() -> None:
    g = gen()
    assert g["CANARY_COUNT"] == 4
    assert tuple(g["RESULT_JOBS"]) == RESULT_JOBS
    assert dict(g["ERRORS"]) == ERRORS
    assert issubclass(g["ExpectRefusal"], Exception)
    keyword = inspect.Parameter.KEYWORD_ONLY
    positional = inspect.Parameter.POSITIONAL_OR_KEYWORD
    shapes = {
        "seed_sql": (("canaries", positional),),
        "result_body": (("job", positional), ("hmac_key", keyword), ("canaries", keyword)),
        "expected_records": (("hmac_key", keyword), ("canaries", keyword)),
        "lab_init_packet": tuple(
            (name, keyword)
            for name in (
                "ip",
                "port",
                "database",
                "username",
                "readonly_password",
                "hmac_key",
                "canaries",
            )
        ),
    }
    for name, shape in shapes.items():
        parameters = inspect.signature(g[name]).parameters.values()
        assert tuple((item.name, item.kind) for item in parameters) == shape


def test_policy_mapping_normalizes_to_pinned_pure_policy() -> None:
    normalized = DatasourcePolicy.from_mapping(gen()["POLICY_MAPPING"]).to_mapping()
    assert normalized == pure()["_lab_policy"](1).to_mapping()


def test_source_imports_and_names_are_closed() -> None:
    tree = ast.parse(GEN_FILE.read_text(encoding="utf-8"))
    allowed = {
        "__future__",
        "collections.abc",
        "dataclasses",
        "decimal",
        "enum",
        "hashlib",
        "ipaddress",
        "json",
        "re",
        "struct",
        "traceback",
        "types",
        "typing",
        "maskgw.config.gateway",
        "maskgw.db.result",
        "maskgw.errors",
        "maskgw.masking.descriptor",
        "maskgw.masking.engine",
        "maskgw.masking.transformers.hashes",
        "maskgw.pgwire.result_encoder",
        "maskgw.pgwire.result_frame",
        "maskgw.secretsource",
    }
    imported: set[str] = set()
    encoder_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0 and node.module is not None
            imported.add(node.module)
            if node.module == "maskgw.pgwire.result_encoder":
                encoder_names.update(alias.name for alias in node.names)
    assert imported <= allowed
    assert "encode_result" in encoder_names
    names = {
        "environ",
        "getenv",
        "EnvSecretProvider",
        "open",
        "exec",
        "eval",
        "compile",
        "__import__",
        "print",
        "input",
        "breakpoint",
    }
    attributes = {"environ", "getenv", "EnvSecretProvider", "system", "popen"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id not in names
        elif isinstance(node, ast.Attribute):
            assert node.attr not in attributes
        elif isinstance(node, ast.FunctionDef | ast.ClassDef):
            assert node.name not in ("main", "entry")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value != "__main__"


# ---------------------------------------------------------------- ExpectRecord


def test_expect_record_is_closed_frozen_and_redacted() -> None:
    record_type = gen()["ExpectRecord"]
    names = tuple(field.name for field in dataclasses.fields(record_type))
    assert names == ("job", "kind", "rows", "bytes", "sha256", "reason")
    result = record_type(job=12, kind="RESULT", rows=1, bytes=60, sha256=SELECT1_SHA, reason=None)
    error = record_type(job=11, kind="ERROR", rows=None, bytes=None, sha256=None, reason="LIMIT")
    assert fields_of(result) == (12, "RESULT", 1, 60, SELECT1_SHA, None)
    assert fields_of(error) == (11, "ERROR", None, None, None, "LIMIT")
    for record in (result, error):
        assert repr(record) == "ExpectRecord(<redacted>)"
        assert not hasattr(record, "__dict__")
        with pytest.raises(AttributeError):
            record.rows = 2


GOOD_RESULT: dict[str, Any] = {
    "job": 12,
    "kind": "RESULT",
    "rows": 1,
    "bytes": 60,
    "sha256": SELECT1_SHA,
    "reason": None,
}
GOOD_ERROR: dict[str, Any] = {
    "job": 11,
    "kind": "ERROR",
    "rows": None,
    "bytes": None,
    "sha256": None,
    "reason": "LIMIT",
}
BAD_RECORDS: list[dict[str, Any]] = [
    {**GOOD_RESULT, "job": 0},
    {**GOOD_RESULT, "job": 20},
    {**GOOD_RESULT, "job": True},
    {**GOOD_RESULT, "job": 12.0},
    {**GOOD_RESULT, "kind": "ERROR"},
    {**GOOD_RESULT, "kind": "result"},
    {**GOOD_RESULT, "rows": None},
    {**GOOD_RESULT, "rows": -1},
    {**GOOD_RESULT, "rows": 1001},
    {**GOOD_RESULT, "rows": False},
    {**GOOD_RESULT, "bytes": 0},
    {**GOOD_RESULT, "bytes": SINK_CAP + 1},
    {**GOOD_RESULT, "sha256": SELECT1_SHA.upper()},
    {**GOOD_RESULT, "sha256": SELECT1_SHA[:63]},
    {**GOOD_RESULT, "sha256": None},
    {**GOOD_RESULT, "reason": "QUERY"},
    {**GOOD_ERROR, "job": 12},
    {**GOOD_ERROR, "reason": "QUERY"},
    {**GOOD_ERROR, "rows": 0},
    {**GOOD_ERROR, "bytes": 1},
    {**GOOD_ERROR, "sha256": SELECT1_SHA},
    {**GOOD_ERROR, "kind": "RESULT"},
    {**GOOD_ERROR, "reason": None},
    {**GOOD_RESULT, "kind": StrProbe("RESULT")},
    {**GOOD_RESULT, "job": IntProbe(12)},
    {**GOOD_RESULT, "sha256": StrProbe(SELECT1_SHA)},
    {**GOOD_ERROR, "reason": StrProbe("LIMIT")},
]


@pytest.mark.parametrize("values", BAD_RECORDS)
def test_expect_record_refuses_incoherent_or_foreign_fields(values: dict[str, Any]) -> None:
    refused("INPUT", lambda: gen()["ExpectRecord"](**values))


# ---------------------------------------------------------------- input refusals

BAD_CANARIES: list[Any] = [
    list(CANARIES),
    CANARIES[:3],
    (*CANARIES, "EFGHIJKLMNOPQRST"),
    (CANARIES[0], CANARIES[0], CANARIES[2], CANARIES[3]),
    ("abcdefghijklmnop", *CANARIES[1:]),
    ("0XABCDEF12345678", *CANARIES[1:]),
    ("1234567890123456", *CANARIES[1:]),
    ("ABCDEFGHIJKLMNO'", *CANARIES[1:]),
    ("ABCDEFGHIJKLM;--", *CANARIES[1:]),
    ("ABCDEFGHIJKLMNO", *CANARIES[1:]),
    ("ABCDEFGHIJKLMNOPQ", *CANARIES[1:]),
    ("A" * 100000, *CANARIES[1:]),
    ("ÁBCDEFGHIJKLMNOP", *CANARIES[1:]),
    (b"ABCDEFGHIJKLMNOP", *CANARIES[1:]),
    (None, *CANARIES[1:]),
    (StrProbe(CANARIES[0]), *CANARIES[1:]),
    TupleProbe(CANARIES),
    None,
]
BAD_KEYS: list[Any] = [
    KEY.upper(),
    KEY[:63],
    KEY + "0",
    "g" * 64,
    "é" * 64,
    KEY.encode("ascii"),
    None,
    StrProbe(KEY),
]


@pytest.mark.parametrize("canaries", BAD_CANARIES)
def test_every_entry_refuses_bad_canaries(canaries: Any) -> None:
    refused("INPUT", lambda: gen()["seed_sql"](canaries))
    refused("INPUT", lambda: gen()["result_body"](12, hmac_key=KEY, canaries=canaries))
    refused("INPUT", lambda: gen()["expected_records"](hmac_key=KEY, canaries=canaries))
    refused("INPUT", lambda: packet(canaries=canaries))


@pytest.mark.parametrize("key", BAD_KEYS)
def test_every_keyed_entry_refuses_bad_key(key: Any) -> None:
    refused("INPUT", lambda: gen()["result_body"](12, hmac_key=key, canaries=CANARIES))
    refused("INPUT", lambda: gen()["expected_records"](hmac_key=key, canaries=CANARIES))
    refused("INPUT", lambda: packet(key=key))


@pytest.mark.parametrize("job", [0, 11, 13, 14, 15, 16, 18, 20, True, 12.0, "12", IntProbe(12)])
def test_result_body_refuses_non_result_jobs(job: Any) -> None:
    refused("INPUT", lambda: gen()["result_body"](job, hmac_key=KEY, canaries=CANARIES))


BAD_TARGETS: list[dict[str, Any]] = [
    {"ip": "127.0.0.1"},
    {"ip": "8.8.8.8"},
    {"ip": "169.254.1.1"},
    {"ip": "10.0.0.07"},
    {"ip": " 10.0.0.7"},
    {"ip": "::1"},
    {"ip": StrProbe(IP)},
    {"port": 0},
    {"port": 65536},
    {"port": True},
    {"port": 5432.0},
    {"port": "5432"},
    {"port": IntProbe(PORT)},
    {"database": ""},
    {"database": "Maskgw"},
    {"database": "1lab"},
    {"database": "a" * 64},
    {"database": "lab-db"},
    {"database": StrProbe(DATABASE)},
    {"username": "RO"},
    {"username": "a" * 100000},
    {"username": StrProbe(USERNAME)},
    {"readonly_password": ""},
    {"readonly_password": PASSWORD[:47]},
    {"readonly_password": PASSWORD + "0"},
    {"readonly_password": PASSWORD.upper()},
    {"readonly_password": "g" * 48},
    {"readonly_password": StrProbe(PASSWORD)},
]


@pytest.mark.parametrize("override", BAD_TARGETS)
def test_lab_init_packet_refuses_bad_explicit_fields(override: dict[str, Any]) -> None:
    refused("INPUT", lambda: packet(**override))


def test_encoder_failures_become_closed_encode(monkeypatch: pytest.MonkeyPatch) -> None:
    namespace = gen()["result_body"].__globals__

    def limit(*_args: object, **_kwargs: object) -> bytes:
        raise EncodeError(EncodeFailure.LIMIT)

    def foreign(*_args: object, **_kwargs: object) -> bytes:
        raise RuntimeError(MARKER)

    for failing in (limit, foreign):
        monkeypatch.setitem(namespace, "encode_result", failing)
        refused("ENCODE", lambda: gen()["result_body"](12, hmac_key=KEY, canaries=CANARIES))
        refused("ENCODE", lambda: gen()["expected_records"](hmac_key=KEY, canaries=CANARIES))


# ---------------------------------------------------------------- seed


def test_seed_sql_exact_literal_and_shared_canaries() -> None:
    seed = gen()["seed_sql"](CANARIES)
    assert type(seed) is bytes
    assert seed == SEED_FIXED
    expected2 = SEED_FIXED.decode("ascii")
    for old, new in zip(CANARIES, CANARIES2, strict=True):
        expected2 = expected2.replace(old, new)
    seed2 = gen()["seed_sql"](CANARIES2)
    assert seed2 == expected2.encode("ascii")
    for canary in CANARIES2:
        assert seed2.count(canary.encode("ascii")) == 1


# ---------------------------------------------------------------- model and bodies


def test_records_shape_and_known_values() -> None:
    result = records(KEY, CANARIES)
    record_type = gen()["ExpectRecord"]
    assert type(result) is tuple and len(result) == 19
    known_bytes = {2: 204, 10: JOB10_BYTES, 12: 60, 17: 60, 19: 60}
    select1 = bytes.fromhex(SELECT1_HEX)
    known_sha = {
        2: JOB2_SHA,
        12: SELECT1_SHA,
        17: hashlib.sha256(select1[:DATA_OFFSET] + b"2" + select1[DATA_OFFSET + 1 :]).hexdigest(),
        19: hashlib.sha256(select1[:DATA_OFFSET] + b"3" + select1[DATA_OFFSET + 1 :]).hexdigest(),
    }
    for job, record in enumerate(result, start=1):
        assert type(record) is record_type
        if job in ERRORS:
            assert fields_of(record) == (job, "ERROR", None, None, None, ERRORS[job])
            continue
        assert (record.job, record.kind, record.rows, record.reason) == (
            job,
            "RESULT",
            ROWS[job],
            None,
        )
        assert type(record.bytes) is int and 1 <= record.bytes <= SINK_CAP
        assert type(record.sha256) is str and len(record.sha256) == 64
        assert set(record.sha256) <= set("0123456789abcdef")
        if job in known_bytes:
            assert record.bytes == known_bytes[job]
        if job in known_sha:
            assert record.sha256 == known_sha[job]


@pytest.mark.parametrize(("key", "canaries"), [(KEY, CANARIES), (KEY2, CANARIES2)])
def test_small_bodies_exact_columns_and_cells(key: str, canaries: tuple[str, ...]) -> None:
    cells = expected_cells(key, canaries)
    for job in RESULT_JOBS:
        if job == 10:
            continue
        columns, rows, tag = parse(body(job, key, canaries))
        assert columns == [(name, oid, TYPLEN[oid]) for name, oid in COLUMNS[job]]
        assert rows == cells[job]
        assert tag == f"SELECT {ROWS[job]}\0".encode("ascii")


def test_independent_vectors_select1_and_hmac_job2() -> None:
    select1 = bytes.fromhex(SELECT1_HEX)
    assert body(12) == select1
    assert body(17) == select1[:DATA_OFFSET] + b"2" + select1[DATA_OFFSET + 1 :]
    assert body(19) == select1[:DATA_OFFSET] + b"3" + select1[DATA_OFFSET + 1 :]
    job2 = body(2)
    assert job2 == bytes.fromhex(JOB2_HEX)
    assert hashlib.sha256(job2).hexdigest() == JOB2_SHA
    assert parse(job2)[1][0] == (h(KEY, CANARIES[0]),)


def test_job10_layout_by_formula() -> None:
    data = body(10)
    assert len(data) == JOB10_BYTES
    column = b"v\0" + COLUMN.pack(0, 0, 25, -1, -1, 0)
    assert data[:27] == b"T" + U32.pack(4 + 2 + len(column)) + U16.pack(1) + column
    row_header = b"D" + U32.pack(4 + 2 + 4 + MIB) + U16.pack(1) + I32.pack(MIB)
    xs = b"x" * MIB
    for row in range(15):
        start = 27 + row * (MIB + 11)
        assert data[start : start + 11] == row_header
        assert data[start + 11 : start + 11 + MIB] == xs
    assert data[-15:] == b"C" + U32.pack(14) + b"SELECT 15\0"


def test_public_chain_descriptors_decisions_oids_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    namespace = gen()["result_body"].__globals__
    seen: list[tuple[Any, ...]] = []

    def spy(result: Any, *, identity: Any, limits: Any, deadline: Any) -> bytes:
        masked = result.masked
        assert type(result) is TypedMaskedResult and type(masked) is MaskedResult
        assert type(deadline) is ResultDeadline
        seen.append(
            (
                masked.columns,
                masked.decisions,
                result.type_oids,
                masked.row_count,
                masked.truncated,
                identity,
                limits,
                deadline.expires_at,
                deadline.clock(),
            )
        )
        frame: bytes = encode_result(result, identity=identity, limits=limits, deadline=deadline)
        return frame

    monkeypatch.setitem(namespace, "encode_result", spy)
    for job in RESULT_JOBS:
        seen.clear()
        data = body(job)
        assert len(seen) == 1
        columns, decisions, oids, row_count, truncated, ident, limit, expires, now = seen[0]
        assert columns == tuple(column for column, _ in MODEL[job])
        assert decisions == tuple(decision for _, decision in MODEL[job])
        assert oids == tuple(oid for _, oid in COLUMNS[job])
        assert (row_count, truncated) == (ROWS[job], job == 9)
        assert ident == identity(job)
        assert limit == limits()
        assert (expires, now) == (1.0, 0.0)
        del data


def test_records_process_jobs_in_order_without_random(monkeypatch: pytest.MonkeyPatch) -> None:
    namespace = gen()["result_body"].__globals__
    jobs: list[int] = []
    random_calls: list[str] = []

    def spy(result: Any, *, identity: Any, limits: Any, deadline: Any) -> bytes:
        jobs.append(identity.job_id)
        frame: bytes = encode_result(result, identity=identity, limits=limits, deadline=deadline)
        return frame

    def tripwire(_self: RandomTransformer, _value: str) -> str:
        random_calls.append("transform")
        raise AssertionError("random transformer applied")

    monkeypatch.setitem(namespace, "encode_result", spy)
    monkeypatch.setattr(RandomTransformer, "transform", tripwire)
    again = gen()["expected_records"](hmac_key=KEY, canaries=CANARIES)
    assert tuple(jobs) == RESULT_JOBS
    assert random_calls == []
    assert tuple(map(fields_of, again)) == tuple(map(fields_of, records(KEY, CANARIES)))


def test_determinism_and_exact_dependency_sets() -> None:
    base = {record.job: record.sha256 for record in records(KEY, CANARIES)}
    keyed = {record.job: record.sha256 for record in records(KEY2, CANARIES)}
    moved = {record.job: record.sha256 for record in records(KEY, CANARIES2)}
    assert {job for job in RESULT_JOBS if base[job] != keyed[job]} == {2, 3, 4, 5, 6}
    assert {job for job in RESULT_JOBS if base[job] != moved[job]} == {2, 3, 4, 5, 6, 7}
    assert body(12) == body(12)
    assert body(4) == body(4)


def test_key_reaches_masking_only_through_explicit_mapping_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local namespace spy delegating to the real public class; no environment access."""
    namespace = gen()["result_body"].__globals__
    assert namespace["MappingSecretProvider"] is MappingSecretProvider
    provided: list[tuple[tuple[object, object], ...]] = []

    def spy(values: Mapping[str, str]) -> MappingSecretProvider:
        assert type(values) is dict
        provided.append(tuple(values.items()))
        return MappingSecretProvider(values)

    monkeypatch.setitem(namespace, "MappingSecretProvider", spy)
    c0, c1 = CANARIES[0], CANARIES[1]
    for key in (KEY, KEY2):
        provided.clear()
        data = body(2, key)
        assert provided == [((HMAC_KEY_ENV, key),)]
        assert data == job2_body(h(key, c0), h(key, c1))
    assert body(2, KEY) == bytes.fromhex(JOB2_HEX)


def test_composition_validate_sink_and_canary_absence() -> None:
    """Sequential: header rebuilt here, public validate_result, pinned decode/sink."""
    init = pure()["decode_init"](packet())
    for job in RESULT_JOBS:
        data = body(job)
        record = records(KEY, CANARIES)[job - 1]
        expected = init.expected[job - 1]
        assert (record.bytes, record.sha256) == (len(data), hashlib.sha256(data).hexdigest())
        assert (expected.bytes, expected.sha256) == (record.bytes, record.sha256)
        for canary in CANARIES:
            assert canary.encode("ascii") not in data
        frame = frame_of(job, data)
        validated = validate_result(
            frame, expected=identity(job), limits=limits(), deadline=fixed_deadline()
        )
        assert (validated.rows, validated.columns, validated.truncated) == (
            ROWS[job],
            len(COLUMNS[job]),
            job == 9,
        )
        del frame, validated
        sink = drain(data, expected.bytes, expected.sha256)
        assert (sink.status, sink.count) == ("OK", len(data))
        del data
    altered = bytearray(body(12))
    altered[-1] ^= 1
    sink = drain(bytes(altered), init.expected[11].bytes, init.expected[11].sha256)
    assert sink.status == "MISMATCH"


# ---------------------------------------------------------------- LAB_INIT


@pytest.mark.parametrize(("key", "canaries"), [(KEY, CANARIES), (KEY2, CANARIES), (KEY, CANARIES2)])
def test_lab_init_packet_matches_records_of_same_inputs(
    key: str, canaries: tuple[str, ...]
) -> None:
    raw = packet(key, canaries)
    assert type(raw) is bytes
    magic, size = INIT_HEADER.unpack_from(raw)
    assert magic == b"MGI1" and size == len(raw) - INIT_HEADER.size <= 65536
    document = raw[INIT_HEADER.size :]
    parsed = json.loads(document.decode("ascii"))
    canonical = json.dumps(
        parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    assert canonical.encode("ascii") == document
    assert parsed["kind"] == "MASKGW_W1_LAB_INIT_V1" and parsed["version"] == 1
    assert parsed["target"] == {"database": DATABASE, "ip": IP, "port": PORT, "username": USERNAME}
    assert parsed["readonly_password"] == PASSWORD
    assert parsed["hmac_key"] == key
    assert parsed["raw_canaries"] == list(canaries)
    rest = {
        name: value
        for name, value in parsed.items()
        if name not in ("readonly_password", "hmac_key", "raw_canaries")
    }
    rest_text = json.dumps(rest, sort_keys=True)
    for secret in (PASSWORD, key, *canaries):
        assert secret not in rest_text
    init = pure()["decode_init"](raw)
    assert (init.target.ip, init.target.port) == (IP, PORT)
    assert (init.target.database, init.target.username) == (DATABASE, USERNAME)
    assert (init.readonly_password, init.hmac_key) == (PASSWORD, key)
    assert init.raw_canaries == canaries
    own = tuple(map(fields_of, records(key, canaries)))
    assert tuple(map(fields_of, init.expected)) == own
    if (key, canaries) != (KEY, CANARIES):
        assert own != tuple(map(fields_of, records(KEY, CANARIES)))


RETAIN_NEEDLES = (KEY, KEY2, PASSWORD, *CANARIES, *CANARIES2)


class Foreign:
    """Foreign value: the retention walker must never call any of its hooks."""

    def __eq__(self, value: object, /) -> bool:
        CALLS.append("eq")
        return False

    def __hash__(self) -> int:
        CALLS.append("hash")
        return 0

    def __iter__(self) -> Iterator[str]:
        CALLS.append("iter")
        return iter((KEY,))

    def __getattribute__(self, name: str) -> Any:
        CALLS.append("getattr")
        return object.__getattribute__(self, name)


def test_sanity_retention_walker_detects_nested_caches() -> None:
    clean: dict[str, object] = {
        "__doc__": KEY,
        "SAFE": (1, "ok", frozenset({"a"}), [b"short"]),
        "dataclasses": dataclasses,
        "retained": retained,
    }
    assert retained(clean, RETAIN_NEEDLES) == []
    cycle: list[object] = []
    cycle.append(cycle)
    assert retained({"CYCLE": cycle}, RETAIN_NEEDLES) == []
    assert retained({"CACHE": {"k": [({"deep": (KEY,)},)]}}, RETAIN_NEEDLES) == ["TEXT"]
    assert retained({"CACHE": {("x", PASSWORD): 1}}, RETAIN_NEEDLES) == ["TEXT"]
    nested_body = frozenset({(b"x" * (SINK_CHUNK + 1),)})
    assert retained({"CACHE": [nested_body]}, RETAIN_NEEDLES) == ["BODY"]
    canary_bytes = bytearray(b"--" + CANARIES2[3].encode("ascii") + b"--")
    assert retained({"CACHE": {"a": [canary_bytes]}}, RETAIN_NEEDLES) == ["BYTES"]
    deep: object = KEY
    for _ in range(RETAIN_DEPTH + 2):
        deep = [deep]
    assert retained({"DEEP": deep}, RETAIN_NEEDLES) == ["LIMIT"]
    foreign = Foreign()
    hostile: dict[str, object] = {"CACHE": [foreign, (foreign,)], "MAP": {foreign: foreign}}
    CALLS.clear()
    assert retained(hostile, RETAIN_NEEDLES) == []
    assert CALLS == []


def test_no_retention_of_keys_canaries_or_bodies_in_module_namespace() -> None:
    namespace = gen()["result_body"].__globals__
    body(10)
    records(KEY2, CANARIES2)
    packet(KEY2, CANARIES2)
    assert type(namespace) is dict
    CALLS.clear()
    assert retained(namespace, RETAIN_NEEDLES) == []
    assert CALLS == []
