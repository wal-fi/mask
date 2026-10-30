"""Independent wire fixtures for the bounded parent result validator (D-113)."""

from __future__ import annotations

import ast
import random
import struct
import subprocess
import sys
import tracemalloc
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

import maskgw.pgwire.result_frame as frame_module
from maskgw.pgwire.result_frame import (
    ResultDeadline,
    ResultErrorCategory,
    ResultFrameError,
    ResultIdentity,
    ResultLimits,
    ValidatedResult,
    validate_result,
)

MIB = 1024 * 1024
HEADER = struct.Struct("!4sBBH16s16sQQQIII")
IDENTITY = ResultIdentity(
    session_id=b"S" * 16,
    datasource_id=b"D" * 16,
    generation=2,
    record_revision=3,
    job_id=4,
)
SIZES = {16: 1, 21: 2, 23: 4, 20: 8, 19: 64, 25: -1, 1042: -1, 1043: -1}


def deadline() -> ResultDeadline:
    return ResultDeadline(expires_at=100.0, clock=lambda: 0.0)


def message(tag: bytes, payload: bytes) -> bytes:
    return tag + struct.pack("!I", 4 + len(payload)) + payload


def column(  # noqa: PLR0913 -- independent wire fixture exposes each corruptible field
    name: bytes = b"x",
    oid: int = 25,
    *,
    table: int = 0,
    attribute: int = 0,
    size: int | None = None,
    modifier: int = -1,
    fmt: int = 0,
) -> bytes:
    return (
        name
        + b"\0"
        + struct.pack(
            "!IhIhih",
            table,
            attribute,
            oid,
            SIZES.get(oid, -1) if size is None else size,
            modifier,
            fmt,
        )
    )


def row(values: Sequence[bytes | None]) -> bytes:
    return message(
        b"D",
        struct.pack("!H", len(values))
        + b"".join(
            struct.pack("!i", -1) if value is None else struct.pack("!i", len(value)) + value
            for value in values
        ),
    )


def frame(
    *,
    columns: Sequence[bytes] | None = None,
    rows: Sequence[Sequence[bytes | None]] = (),
    body: bytes | None = None,
    count: int | None = None,
    fields: dict[int, Any] | None = None,
) -> bytes:
    if columns is None:
        columns = [column()]
    nrows = len(rows) if count is None else count
    if body is None:
        body = (
            message(b"T", struct.pack("!H", len(columns)) + b"".join(columns))
            + b"".join(row(values) for values in rows)
            + message(b"C", b"SELECT " + str(nrows).encode("ascii") + b"\0")
        )
    values: list[Any] = [
        b"MGWR",
        1,
        0,
        0,
        b"S" * 16,
        b"D" * 16,
        2,
        3,
        4,
        len(columns),
        nrows,
        len(body),
    ]
    if fields:
        for index, value in fields.items():
            values[index] = value
    return HEADER.pack(*values) + body


def accepted(
    raw: Any, *, limits: ResultLimits | None = None, clock: ResultDeadline | None = None
) -> ValidatedResult:
    return validate_result(
        raw,
        expected=IDENTITY,
        limits=limits or ResultLimits(max_rows=1000),
        deadline=clock or deadline(),
    )


def output(raw: bytes, **kwargs: Any) -> bytes:
    result = accepted(raw, **kwargs)
    return b"".join(result.iter_chunks(deadline=deadline()))


@pytest.mark.parametrize(
    "oid,value",
    [
        (16, b"t"),
        (16, b"f"),
        (21, b"-32768"),
        (21, b"32767"),
        (23, b"-2147483648"),
        (23, b"2147483647"),
        (20, b"-9223372036854775808"),
        (20, b"9223372036854775807"),
        (25, b""),
        (1042, b"  x  "),
        (1043, b"hello"),
        (19, b"name"),
        (25, "a\u00e9\u20ac\U0001f680\U0010ffff".encode()),
    ],
)
def test_supported_values_roundtrip_without_reencoding(oid, value):
    raw = frame(columns=[column(oid=oid)], rows=[[value], [None]])
    result = accepted(raw)
    assert (result.columns, result.rows, result.truncated) == (1, 2, False)
    chunks = list(result.iter_chunks(deadline=deadline(), chunk_bytes=7))
    assert all(
        type(chunk) is memoryview and chunk.readonly and chunk.obj is raw for chunk in chunks
    )
    assert all(len(chunk) <= 7 for chunk in chunks)
    assert b"".join(chunks) == raw[HEADER.size :]


@pytest.mark.parametrize("oid", list(SIZES))
def test_null_for_every_supported_oid(oid):
    assert output(frame(columns=[column(oid=oid)], rows=[[None]]))


def test_zero_rows_duplicate_names_empty_names_and_truncation():
    raw = frame(columns=[column(), column(), column(name=b"")])
    assert accepted(raw).rows == 0
    raw = frame(rows=[[b"a"], [b"b"]], fields={2: 1})
    assert accepted(raw, limits=ResultLimits(max_rows=2)).truncated
    with pytest.raises(ResultFrameError):
        accepted(raw, limits=ResultLimits(max_rows=3))


@pytest.mark.parametrize(
    "index,value",
    [
        (0, b"FAIL"),
        (1, 0),
        (1, 2),
        (2, 2),
        (2, 255),
        (3, 1),
        (4, b"X" * 16),
        (5, b"X" * 16),
        (6, 0),
        (6, 1),
        (6, 2**63),
        (7, 0),
        (7, 2),
        (7, 2**63),
        (8, 0),
        (8, 5),
        (8, 2**63),
        (9, 0),
        (9, 1665),
        (9, 2**32 - 1),
        (10, 1001),
        (11, 0),
        (11, 2**32 - 1),
    ],
)
def test_invalid_header_and_expected_identity(index, value):
    with pytest.raises(ResultFrameError):
        accepted(frame(rows=[[b"x"]], fields={index: value}))


def test_every_truncated_prefix_and_extra_suffix_rejected():
    raw = frame(rows=[[b"hello"], [None], [b""]])
    for cut in range(len(raw)):
        with pytest.raises(ResultFrameError):
            accepted(raw[:cut])
    for suffix in (b"\0", b"x", raw, b"Z\0\0\0\5I"):
        with pytest.raises(ResultFrameError):
            accepted(raw + suffix)


@pytest.mark.parametrize(
    "descriptor",
    [
        column(table=1),
        column(attribute=1),
        column(modifier=0),
        column(fmt=1),
        column(size=8),
        column(oid=1700),
        column(oid=0),
        column(oid=2**32 - 1),
        column(name=b"a" * 257),
        column(name=b"\xff"),
    ],
)
def test_metadata_is_closed(descriptor):
    with pytest.raises(ResultFrameError):
        accepted(frame(columns=[descriptor]))


@pytest.mark.parametrize(
    "oid,bad",
    [
        (16, b""),
        (16, b"true"),
        (16, b"T"),
        (16, b"0"),
        (21, b"32768"),
        (21, b"-32769"),
        (23, b"2147483648"),
        (23, b"-2147483649"),
        (20, b"9223372036854775808"),
        (20, b"-9223372036854775809"),
    ]
    + [
        (20, value)
        for value in (
            b"",
            b"+1",
            b"01",
            b"-0",
            b"-01",
            b" 1",
            b"1 ",
            b"1.0",
            b"--1",
            b"-",
            b"9" * 21,
            b"\xff",
        )
    ],
)
def test_scalar_value_grammar_and_ranges(oid, bad):
    with pytest.raises(ResultFrameError):
        accepted(frame(columns=[column(oid=oid)], rows=[[bad]]))


@pytest.mark.parametrize(
    "invalid",
    [
        b"\0",
        b"x\0y",
        b"\x80",
        b"\xc0\x80",
        b"\xc1\xbf",
        b"\xc2",
        b"\xc2x",
        b"\xe0\x80\x80",
        b"\xed\xa0\x80",
        b"\xef\xbf",
        b"\xf0\x80\x80\x80",
        b"\xf4\x90\x80\x80",
        b"\xf5\x80\x80\x80",
        b"\xff",
        b"\xe2\x82x",
        b"\xf0\x90\x80",
    ],
)
@pytest.mark.parametrize("prefix", [0, 4094, 4095, 4096, 4097])
def test_utf8_invalid_across_work_boundaries(invalid, prefix):
    with pytest.raises(ResultFrameError):
        accepted(frame(rows=[[b"x" * prefix + invalid]]))


@pytest.mark.parametrize(
    "valid",
    ["\u0080", "\u07ff", "\u0800", "\ud7ff", "\ue000", "\uffff", "\U00010000", "\U0010ffff"],
)
@pytest.mark.parametrize("prefix", [4093, 4094, 4095, 4096])
def test_utf8_valid_across_work_boundaries(valid, prefix):
    raw = frame(rows=[[b"x" * prefix + valid.encode()]])
    assert output(raw) == raw[HEADER.size :]


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"D\0\0\0\3",
        message(b"D", b"\0\0"),
        message(b"D", b"\0\1" + struct.pack("!i", -2)),
        message(b"D", b"\0\1" + struct.pack("!i", 100)),
        message(b"D", b"\0\1" + struct.pack("!i", 0) + b"extra"),
        message(b"N", b"unexpected"),
    ],
)
def test_malformed_data_row(data):
    body = message(b"T", b"\0\1" + column()) + data + message(b"C", b"SELECT 1\0")
    with pytest.raises(ResultFrameError):
        accepted(frame(body=body, count=1))


@pytest.mark.parametrize(
    "tag", [b"SELECT 2\0", b"SELECT 01\0", b"FETCH 1\0", b"SELECT 1", b"SELECT 1\0x"]
)
def test_command_complete_is_exact(tag):
    body = message(b"T", b"\0\1" + column()) + row([b"x"]) + message(b"C", tag)
    with pytest.raises(ResultFrameError):
        accepted(frame(body=body, count=1))


def test_bounds_are_inclusive_and_dimensions_checked_without_allocation():
    raw = frame(columns=[column(name=b"n" * 256)], rows=[[b"x" * MIB]])
    assert output(raw, limits=ResultLimits(max_rows=1, max_frame_bytes=len(raw)))
    for limits in (
        ResultLimits(max_rows=1, max_frame_bytes=len(raw) - 1),
        ResultLimits(max_rows=1, max_cell_bytes=MIB - 1),
        ResultLimits(max_rows=1, max_name_bytes=255),
    ):
        with pytest.raises(ResultFrameError):
            accepted(raw, limits=limits)
    with pytest.raises(ResultFrameError):
        accepted(frame(fields={10: 2**31 - 1}), limits=ResultLimits(max_rows=2**31 - 1))
    many_columns = frame(columns=[column()] * 1664, rows=[[None] * 1664])
    assert accepted(many_columns).columns == 1664
    with pytest.raises(ResultFrameError):
        accepted(many_columns, limits=ResultLimits(max_rows=1, max_columns=1663))


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.5, float("nan"), float("inf"), "10", None])
@pytest.mark.parametrize(
    "field", ["max_rows", "max_frame_bytes", "max_cell_bytes", "max_columns", "max_name_bytes"]
)
def test_limit_inputs_reject_non_exact_positive_integers(field, value):
    with pytest.raises(ResultFrameError):
        ResultLimits(**{"max_rows": 1, field: value})


@pytest.mark.parametrize(
    "changes",
    [
        {"session_id": b"x"},
        {"datasource_id": b"x" * 17},
        {"generation": True},
        {"generation": 0},
        {"generation": 2**63},
        {"record_revision": -1},
        {"job_id": 0},
    ],
)
def test_identity_validates_before_use(changes):
    args: dict[str, Any] = {
        "session_id": b"S" * 16,
        "datasource_id": b"D" * 16,
        "generation": 2,
        "record_revision": 3,
        "job_id": 4,
    }
    with pytest.raises(ResultFrameError):
        ResultIdentity(**(args | changes))


def test_mutable_input_refused_and_result_owner_never_reused():
    raw = frame(rows=[[b"CANARY_OLD"]])
    for mutable in (bytearray(raw), memoryview(raw), memoryview(bytearray(raw))):
        with pytest.raises(ResultFrameError):
            accepted(mutable)
    first = accepted(raw)
    newer = frame(rows=[[b"NEW"]])
    second = accepted(newer)
    assert b"CANARY_OLD" not in b"".join(second.iter_chunks(deadline=deadline()))
    assert b"CANARY_OLD" in b"".join(first.iter_chunks(deadline=deadline()))
    with pytest.raises(AttributeError):
        first.rows = 900  # type: ignore[misc]  # immutable public API counterexample


def test_deadline_during_validation_and_separate_chunk_deadline():
    count = 0

    def clock():
        nonlocal count
        count += 1
        return 101.0 if count > 6 else 0.0

    with pytest.raises(ResultFrameError) as caught:
        accepted(frame(rows=[[b"x" * 20000]]), clock=ResultDeadline(expires_at=100, clock=clock))
    assert caught.value.category is ResultErrorCategory.DEADLINE
    result = accepted(frame(rows=[[b"ok"]]))
    with pytest.raises(ResultFrameError):
        next(result.iter_chunks(deadline=ResultDeadline(expires_at=1, clock=lambda: 2.0)))


@pytest.mark.parametrize("returned", [float("nan"), float("inf"), -1, True, "CANARY_CLOCK"])
def test_invalid_clock_results_are_sanitized(returned):
    with pytest.raises(ResultFrameError) as caught:
        accepted(frame(), clock=ResultDeadline(expires_at=100, clock=lambda: returned))
    assert "CANARY" not in str(caught.value)


def test_clock_exception_and_error_repr_never_contain_payload_or_internal_chain():
    def broken():
        raise OSError("CANARY_CLOCK_SECRET")

    with pytest.raises(ResultFrameError) as caught:
        accepted(frame(rows=[[b"CANARY_DATA"]]), clock=ResultDeadline(expires_at=100, clock=broken))
    assert "CANARY" not in str(caught.value) + repr(caught.value)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    result = accepted(frame(rows=[[b"CANARY_DATA"]]))
    assert "CANARY" not in repr(result)
    assert "SSSS" not in repr(result) and "DDDD" not in repr(result)


def test_refusal_never_yields_bytes_to_sink_and_random_frames_never_raise_raw_errors():
    sink: list[memoryview] = []
    generator = random.Random(71209)  # noqa: S311 -- reproducible malformed-byte fixtures, not entropy
    bad_frames = [generator.randbytes(generator.randrange(0, 400)) for _ in range(200)]
    bad_frames += [frame(rows=[[b"\xff"]]), frame(fields={10: 2**32 - 1})]
    for raw in bad_frames:
        with pytest.raises(ResultFrameError):
            result = accepted(raw)
            sink.extend(result.iter_chunks(deadline=deadline()))
    assert sink == []


@pytest.mark.parametrize("chunk", [0, -1, True, 65537, 1.5, None])
def test_chunk_size_is_bounded(chunk):
    with pytest.raises(ResultFrameError):
        next(accepted(frame()).iter_chunks(deadline=deadline(), chunk_bytes=chunk))


def test_full_16mib_frame_uses_constant_validation_memory_and_copy_control_detects_growth():
    empty = frame(rows=[[b""]] * 16)
    remaining = 16 * MIB - len(empty) - 15 * MIB
    raw = frame(rows=[[b"x" * MIB]] * 15 + [[b"y" * remaining]])
    assert len(raw) == 16 * MIB
    tracemalloc.start()
    try:
        result = accepted(raw)
        total = sum(len(part) for part in result.iter_chunks(deadline=deadline()))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert total == len(raw) - HEADER.size
    assert peak < 512 * 1024
    tracemalloc.start()
    try:
        copy = bytearray(raw)
        _, copy_peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert len(copy) == len(raw) and copy_peak > 512 * 1024


def test_no_operational_importer_or_io_dependency():
    root = Path(__file__).resolve().parents[1] / "src" / "maskgw"
    module = root / "pgwire" / "result_frame.py"
    forbidden = {"socket", "ssl", "subprocess", "logging", "psycopg", "mcp", "fastapi", "pydantic"}
    tree = ast.parse(module.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in forbidden for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] not in forbidden
    for other in root.rglob("*.py"):
        if other not in (
            module,
            root / "pgwire" / "result_receiver.py",
            root / "pgwire" / "result_encoder.py",
            root / "runtime" / "worker_protocol.py",  # pure W1 wire codec, no I/O caller
            root / "runtime" / "worker_process.py",  # private W1 child, no ingress
            root / "runtime" / "worker_session.py",  # private owner, only validated output
        ):
            if other != root / "runtime/worker_job.py":
                assert "result_frame" not in other.read_text(encoding="utf-8")
            assert "result_receiver" not in other.read_text(encoding="utf-8")


def test_review_large_invalid_command_does_not_allocate_declared_body():
    body = message(b"T", b"\0\1" + column()) + message(b"C", b"x" * (8 * MIB))
    raw = frame(body=body)
    tracemalloc.start()
    try:
        with pytest.raises(ResultFrameError):
            accepted(raw)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 512 * 1024


def test_review_large_integer_clock_is_closed_error_not_overflow():
    with pytest.raises(ResultFrameError):
        ResultDeadline(expires_at=10**1000)
    with pytest.raises(ResultFrameError):
        accepted(frame(), clock=ResultDeadline(expires_at=100, clock=lambda: 10**1000))


def test_review_result_slots_cannot_be_deleted():
    result = accepted(frame())
    with pytest.raises(AttributeError):
        del result._wire
    assert list(result.iter_chunks(deadline=deadline()))


def test_review_chunk_allocation_failure_is_sanitized(monkeypatch):
    result = accepted(frame())

    def broken_view(_owner):
        raise MemoryError("CANARY_INTERNAL_MEMORY")

    monkeypatch.setattr(frame_module, "memoryview", broken_view, raising=False)
    with pytest.raises(ResultFrameError) as caught:
        next(result.iter_chunks(deadline=deadline()))
    assert caught.value.__context__ is None
    assert caught.value.memory_exhausted is True
    assert "CANARY" not in str(caught.value)


def test_ordinary_limit_does_not_claim_memory_exhaustion():
    with pytest.raises(ResultFrameError) as caught:
        accepted(frame(rows=[[b"xx"]]), limits=ResultLimits(max_rows=1, max_cell_bytes=1))
    assert caught.value.category is ResultErrorCategory.LIMIT
    assert caught.value.memory_exhausted is False


def test_every_single_byte_text_and_short_utf8_boundary_matches_python_strict_decode():
    values = [bytes([value]) for value in range(256)]
    values += [
        b"x" * 4094 + b"\xc3\xa9",
        b"x" * 4095 + b"\xc3\xa9",
        b"x" * 4094 + b"\xc3",
        b"x" * 4095 + b"\x80",
        b"x" * 4095 + b"\0",
        b"\xf0\x9f\x9a\x80",
        b"\xed\xa0\x80",
    ]
    for value in values:
        valid = False
        with suppress(UnicodeDecodeError):
            valid = "\0" not in value.decode("utf-8", errors="strict")
        if valid:
            assert accepted(frame(rows=[[value]])).rows == 1
        else:
            with pytest.raises(ResultFrameError):
                accepted(frame(rows=[[value]]))


@pytest.mark.parametrize("count", [0, 0xFFFF])
def test_unsigned_pgwire_counts_are_bounded(count):
    body = message(b"T", struct.pack("!H", count) + column()) + message(b"C", b"SELECT 0\0")
    with pytest.raises(ResultFrameError):
        accepted(frame(body=body))
    body = (
        message(b"T", b"\0\1" + column())
        + message(b"D", struct.pack("!H", count) + b"\xff" * 4)
        + message(b"C", b"SELECT 1\0")
    )
    with pytest.raises(ResultFrameError):
        accepted(frame(body=body, count=1))


@pytest.mark.parametrize(
    "body",
    [
        row([b"x"]) + message(b"T", b"\0\1" + column()) + message(b"C", b"SELECT 1\0"),
        message(b"T", b"\0\1" + column() + b"EXTRA") + message(b"C", b"SELECT 0\0"),
        message(b"T", b"\0\1" + column()) + message(b"C", b"SELECT 0\0") * 2,
        message(b"T", b"\0\1" + column()) + message(b"C", b"SELECT  0\0"),
        message(b"T", b"\0\1" + column()) + message(b"C", b"INSERT 0 0\0"),
    ],
)
def test_message_order_and_internal_exact_consumption(body):
    with pytest.raises(ResultFrameError):
        accepted(frame(body=body))


def test_name_value_bound_and_no_zero_column_frame():
    assert output(frame(columns=[column(oid=19)], rows=[[b"n" * 63]]))
    with pytest.raises(ResultFrameError):
        accepted(frame(columns=[column(oid=19)], rows=[[b"n" * 64]]))
    with pytest.raises(ResultFrameError):
        accepted(frame(columns=[]))
    with pytest.raises(TypeError):
        ValidatedResult()


def test_deadline_expires_inside_large_cell_without_output():
    calls = 0

    def clock() -> float:
        nonlocal calls
        calls += 1
        return 101.0 if calls > 20 else 0.0

    with pytest.raises(ResultFrameError) as caught:
        accepted(frame(rows=[[b"x" * MIB]]), clock=ResultDeadline(expires_at=100, clock=clock))
    assert caught.value.category is ResultErrorCategory.DEADLINE
    assert calls == 21


def test_isolated_normal_import_does_not_load_network_database_or_other_planes():
    src = Path(__file__).resolve().parents[1] / "src"
    code = (
        f"import sys;sys.path.insert(0,{str(src)!r});"
        "import maskgw.pgwire.result_frame;"
        "assert not {'psycopg','mcp','fastapi','socket','ssl','maskgw.runtime.registry'}"
        ".intersection(sys.modules);print('PURE_IMPORT_OK')"
    )
    completed = subprocess.run(  # noqa: S603 -- fixed local import probe, no untrusted command
        [sys.executable, "-I", "-B", "-c", code],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert completed.stdout.strip() == "PURE_IMPORT_OK"


def test_review_mixed_oid_columns_use_their_own_positions():
    descriptors = [column(oid=oid) for oid in (23, 16, 25, 21)]
    raw = frame(
        columns=descriptors,
        rows=[[b"42", b"t", "ol\u00e1".encode(), b"-32768"], [None, b"f", b"", b"32767"]],
    )
    assert output(raw) == raw[HEADER.size :]
    for values in (
        [b"t", b"42", b"text", b"1"],
        [b"1", b"text", b"t", b"2"],
        [b"1", b"f", b"32768", b"text"],
    ):
        with pytest.raises(ResultFrameError):
            accepted(frame(columns=descriptors, rows=[values]))


@pytest.mark.parametrize(
    "raw,limits,category",
    [
        (frame(fields={0: b"NOPE"}), ResultLimits(max_rows=1), ResultErrorCategory.PROTOCOL),
        (frame(fields={4: b"X" * 16}), ResultLimits(max_rows=1), ResultErrorCategory.IDENTITY),
        (
            frame(rows=[[b"xx"]]),
            ResultLimits(max_rows=1, max_cell_bytes=1),
            ResultErrorCategory.LIMIT,
        ),
    ],
)
def test_review_error_categories_are_closed_and_specific(raw, limits, category):
    with pytest.raises(ResultFrameError) as caught:
        accepted(raw, limits=limits)
    assert caught.value.category is category
    assert caught.value.args == (category.value,)


def test_review_mutations_of_valid_body_exercise_deep_parser_without_raw_exceptions():
    original = frame(
        columns=[column(oid=23), column(oid=16), column()],
        rows=[[b"42", b"t", "ol\u00e1".encode()]],
    )
    rejected = accepted_count = 0
    for offset in range(HEADER.size, len(original)):
        for bit in (1, 128):
            raw = original[:offset] + bytes([original[offset] ^ bit]) + original[offset + 1 :]
            try:
                result = accepted(raw)
            except ResultFrameError:
                rejected += 1
            else:
                accepted_count += 1
                assert b"".join(result.iter_chunks(deadline=deadline())) == raw[HEADER.size :]
    assert rejected > 100 and accepted_count > 0


def test_review_dense_small_cells_keep_fixed_incremental_memory():
    raw = frame(columns=[column()] * 8, rows=[[b"x"] * 8] * 8192)
    limits = ResultLimits(max_rows=8192)
    tracemalloc.start()
    try:
        result = accepted(raw, limits=limits)
        total = sum(len(part) for part in result.iter_chunks(deadline=deadline()))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result.rows == 8192 and result.columns == 8
    assert total == len(raw) - HEADER.size and peak < 512 * 1024


def test_review_validator_memory_failure_is_closed(monkeypatch):
    def broken_scratch(_length):
        raise MemoryError("CANARY_SCRATCH_SECRET")

    monkeypatch.setattr(frame_module, "bytearray", broken_scratch, raising=False)
    with pytest.raises(ResultFrameError) as caught:
        accepted(frame())
    assert caught.value.category is ResultErrorCategory.LIMIT
    assert caught.value.memory_exhausted is True
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert "CANARY" not in str(caught.value)
