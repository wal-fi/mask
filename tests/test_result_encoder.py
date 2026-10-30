"""Independent typed output fixtures for the worker encoder (D-115)."""

from __future__ import annotations

import ast
import struct
import time
import tracemalloc
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, cast

import pytest

import maskgw.pgwire.result_encoder as encoder_module
import maskgw.pgwire.result_frame as frame_module
from maskgw.db.result import (
    WIRE_TYPE_SIZES,
    DatabaseResultIntegrityError,
    MaskedResult,
    TypedMaskedResult,
)
from maskgw.masking.descriptor import ColumnDescriptor
from maskgw.masking.engine import Action, Decision
from maskgw.pgwire.result_encoder import EncodeError, EncodeFailure, encode_result
from maskgw.pgwire.result_frame import ResultDeadline, ResultLimits
from tests.test_result_frame import HEADER, IDENTITY, column, deadline, frame


def typed(
    values: tuple[Any, ...], oids: tuple[int, ...], *, masked: bool = False
) -> TypedMaskedResult:
    columns = tuple(ColumnDescriptor(f"c{index}") for index in range(len(oids)))
    decisions = tuple(
        Decision(Action.MASK if masked else Action.ALLOW, item.output_name) for item in columns
    )
    return TypedMaskedResult(MaskedResult(columns, decisions, (values,)), oids)


@pytest.mark.parametrize(
    "oid,value,text",
    [
        (16, True, b"t"),
        (16, False, b"f"),
        (21, -32768, b"-32768"),
        (21, 32767, b"32767"),
        (23, -2147483648, b"-2147483648"),
        (23, 2147483647, b"2147483647"),
        (20, -(1 << 63), b"-9223372036854775808"),
        (20, (1 << 63) - 1, b"9223372036854775807"),
        (19, "name", b"name"),
        (25, "text", b"text"),
        (1042, "  x  ", b"  x  "),
        (1043, "\u00e9", b"\xc3\xa9"),
    ],
)
def test_canonical_bytes_match_independent_wire_fixture(oid, value, text):
    raw = encode_result(
        typed((value,), (oid,)),
        identity=IDENTITY,
        limits=ResultLimits(max_rows=10),
        deadline=deadline(),
    )
    assert raw == frame(columns=[column(name=b"c0", oid=oid)], rows=[[text]])


@pytest.mark.parametrize("oid", [16, 21, 23, 20, 19, 25, 1042, 1043])
def test_null_is_not_coerced(oid):
    raw = encode_result(
        typed((None,), (oid,)),
        identity=IDENTITY,
        limits=ResultLimits(max_rows=10),
        deadline=deadline(),
    )
    assert raw == frame(columns=[column(name=b"c0", oid=oid)], rows=[[None]])


@pytest.mark.parametrize(
    "oid,value",
    [
        (21, True),
        (16, 1),
        (25, b"bytes"),
        (23, 1 << 31),
        (20, 1 << 1000),
        (19, "x" * 64),
        (25, "x\0y"),
        (25, "\ud800"),
    ],
)
def test_mismatched_values_are_controlled_type_error(oid, value):
    with pytest.raises(EncodeError) as caught:
        encode_result(
            typed((value,), (oid,)),
            identity=IDENTITY,
            limits=ResultLimits(max_rows=10),
            deadline=deadline(),
        )
    assert caught.value.category is EncodeFailure.TYPE
    assert caught.value.__cause__ is None and caught.value.__context__ is None


def test_masked_type_must_be_announced_as_text():
    with pytest.raises(DatabaseResultIntegrityError):
        typed(("masked",), (23,), masked=True)
    result = typed(("masked",), (25,), masked=True)
    assert encode_result(
        result, identity=IDENTITY, limits=ResultLimits(max_rows=1), deadline=deadline()
    ) == frame(columns=[column(name=b"c0")], rows=[[b"masked"]])
    assert "masked" not in repr(result)


@pytest.mark.parametrize("oid", [1700, 701, 1082, 2950, 3802, 17, 1007, 18, 999999, True])
def test_unsupported_type_refuses_even_for_null(oid):
    with pytest.raises(DatabaseResultIntegrityError):
        typed((None,), (oid,))


def test_duplicate_names_are_positional_and_metadata_private():
    columns = (ColumnDescriptor("same", origin_name="secret"),) * 2
    decisions = (Decision(Action.MASK, "same"), Decision(Action.EXCEPTION, "same"))
    result = TypedMaskedResult(MaskedResult(columns, decisions, (("masked", 42),)), (25, 23))
    raw = encode_result(
        result, identity=IDENTITY, limits=ResultLimits(max_rows=2), deadline=deadline()
    )
    assert raw == frame(
        columns=[column(name=b"same"), column(name=b"same", oid=23)], rows=[[b"masked", b"42"]]
    )
    assert b"secret" not in raw
    fields = HEADER.unpack(raw[: HEADER.size])
    assert fields[9:11] == (2, 1)


def test_truncated_shape_is_checked_before_encoding():
    item = typed(("x",), (25,))
    result = TypedMaskedResult(
        MaskedResult(item.masked.columns, item.masked.decisions, item.masked.rows, truncated=True),
        item.type_oids,
    )
    with pytest.raises(EncodeError):
        encode_result(
            result, identity=IDENTITY, limits=ResultLimits(max_rows=2), deadline=deadline()
        )


def test_bad_dto_structure_cannot_be_constructed():
    item = typed(("x",), (25,))
    for oids in ((), (25, 25), [25], (25.0,)):
        with pytest.raises(DatabaseResultIntegrityError):
            TypedMaskedResult(item.masked, cast(Any, oids))


def test_zero_columns_refused():
    with pytest.raises(DatabaseResultIntegrityError):
        TypedMaskedResult(MaskedResult((), (), ()), ())


def test_exact_message_lengths_are_pgwire_not_generic_json():
    raw = encode_result(
        typed(("x",), (25,)),
        identity=IDENTITY,
        limits=ResultLimits(max_rows=1),
        deadline=deadline(),
    )
    offset = HEADER.size
    tags = []
    while offset < len(raw):
        tags.append(chr(raw[offset]))
        offset += 1 + struct.unpack_from("!I", raw, offset + 1)[0]
    assert offset == len(raw) and tags == ["T", "D", "C"]


def test_exact_limit_and_one_byte_less_preflight_before_frame_allocation(monkeypatch):
    item = typed(("hello",), (25,))
    expected = frame(columns=[column(name=b"c0")], rows=[[b"hello"]])
    sizes = []

    def allocate(size):
        sizes.append(size)
        return bytearray(size)

    monkeypatch.setattr(encoder_module, "bytearray", allocate, raising=False)
    assert (
        encode_result(
            item,
            identity=IDENTITY,
            limits=ResultLimits(max_rows=1, max_frame_bytes=len(expected)),
            deadline=deadline(),
        )
        == expected
    )
    assert sizes == [len(expected)]
    sizes.clear()
    with pytest.raises(EncodeError) as caught:
        encode_result(
            item,
            identity=IDENTITY,
            limits=ResultLimits(max_rows=1, max_frame_bytes=len(expected) - 1),
            deadline=deadline(),
        )
    assert caught.value.category is EncodeFailure.LIMIT and not sizes


def test_cell_byte_limit_is_utf8_not_character_count():
    item = typed(("\U0001f680",), (25,))
    for limit in (1, 2, 3):
        with pytest.raises(EncodeError) as caught:
            encode_result(
                item,
                identity=IDENTITY,
                limits=ResultLimits(max_rows=1, max_cell_bytes=limit),
                deadline=deadline(),
            )
        assert caught.value.category is EncodeFailure.LIMIT
    assert encode_result(
        item,
        identity=IDENTITY,
        limits=ResultLimits(max_rows=1, max_cell_bytes=4),
        deadline=deadline(),
    )


def test_name_63_utf8_boundary_and_name_byte_limit():
    assert encode_result(
        typed(("x" * 63,), (19,)),
        identity=IDENTITY,
        limits=ResultLimits(max_rows=1),
        deadline=deadline(),
    )
    with pytest.raises(EncodeError) as caught:
        encode_result(
            typed(("\u00e9" * 32,), (19,)),
            identity=IDENTITY,
            limits=ResultLimits(max_rows=1),
            deadline=deadline(),
        )
    assert caught.value.category is EncodeFailure.TYPE


def test_deadline_during_utf8_preflight_never_allocates_frame(monkeypatch):
    calls = 0
    allocated: list[int] = []

    def clock():
        nonlocal calls
        calls += 1
        return 100.0 if calls > 4 else 0.0

    monkeypatch.setattr(encoder_module, "bytearray", allocated.append, raising=False)
    with pytest.raises(EncodeError) as caught:
        encode_result(
            typed(("x" * 20000,), (25,)),
            identity=IDENTITY,
            limits=ResultLimits(max_rows=1),
            deadline=ResultDeadline(expires_at=100, clock=clock),
        )
    assert caught.value.category is EncodeFailure.DEADLINE and not allocated


def test_encoder_oom_is_fixed_error_and_not_original_context(monkeypatch):
    def broken(_size):
        raise MemoryError("CANARY_MEMORY")

    monkeypatch.setattr(encoder_module, "bytearray", broken, raising=False)
    with pytest.raises(EncodeError) as caught:
        encode_result(
            typed(("CANARY_DATA",), (25,)),
            identity=IDENTITY,
            limits=ResultLimits(max_rows=1),
            deadline=deadline(),
        )
    assert caught.value.category is EncodeFailure.MEMORY and caught.value.fatal
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert "CANARY" not in str(caught.value) + repr(caught.value)


def test_immutable_dto_and_exact_scalars_no_custom_conversion():
    class HostileInt(int):
        def __str__(self):
            raise AssertionError("no arbitrary conversion")

    class HostileText(str):
        def encode(self, *args, **kwargs):
            del args, kwargs
            raise AssertionError("no arbitrary conversion")

    for oid, value in ((23, HostileInt(1)), (25, HostileText("x"))):
        with pytest.raises(EncodeError) as caught:
            encode_result(
                typed((value,), (oid,)),
                identity=IDENTITY,
                limits=ResultLimits(max_rows=1),
                deadline=deadline(),
            )
        assert caught.value.category is EncodeFailure.TYPE
    item = typed(("x",), (25,))
    with pytest.raises(FrozenInstanceError):
        cast(Any, item).type_oids = ()


def test_tampered_dto_is_revalidated_before_encoding():
    item = typed(("x",), (25,))
    object.__setattr__(item, "type_oids", (1700,))
    with pytest.raises(EncodeError) as caught:
        encode_result(item, identity=IDENTITY, limits=ResultLimits(max_rows=1), deadline=deadline())
    assert caught.value.category is EncodeFailure.PROTOCOL


def test_empty_rows_and_valid_truncation():
    item = typed(("x",), (25,))
    for rows, truncated in (((), False), (item.masked.rows, True)):
        data = TypedMaskedResult(
            MaskedResult(item.masked.columns, item.masked.decisions, rows, truncated), (25,)
        )
        raw = encode_result(
            data, identity=IDENTITY, limits=ResultLimits(max_rows=1), deadline=deadline()
        )
        assert HEADER.unpack(raw[: HEADER.size])[2] == int(truncated)


def test_full_16mib_output_uses_at_most_two_proportional_buffers():
    mib = 1024 * 1024
    columns = (ColumnDescriptor("c0"),)
    decisions = (Decision(Action.ALLOW, "c0"),)
    empty = frame(columns=[column(name=b"c0")], rows=[[b""]] * 16)
    remaining = 16 * mib - len(empty) - 15 * mib
    rows = (("x" * mib,),) * 15 + (("y" * remaining,),)
    item = TypedMaskedResult(MaskedResult(columns, decisions, rows), (25,))
    tracemalloc.start()
    try:
        raw = encode_result(
            item, identity=IDENTITY, limits=ResultLimits(max_rows=100), deadline=deadline()
        )
        retained, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert len(raw) == 16 * mib
    assert len(raw) <= retained < len(raw) + 512 * 1024
    assert peak < 2 * len(raw) + 512 * 1024


def test_closed_type_tables_agree_and_import_boundary_is_narrow():
    assert dict(WIRE_TYPE_SIZES) == frame_module._TYPE_SIZES
    with pytest.raises(TypeError):
        cast(Any, WIRE_TYPE_SIZES)[99999] = -1
    root = Path(__file__).resolve().parents[1] / "src/maskgw"
    source = root / "pgwire/result_encoder.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imported <= {
        "__future__",
        "struct",
        "traceback",
        "contextlib",
        "dataclasses",
        "enum",
        "typing",
        "maskgw.db.result",
        "maskgw.pgwire.result_frame",
    }
    for path in root.rglob("*.py"):
        # Private composition only; its own guard still rejects operational importers.
        if path not in (source, root / "runtime/worker_job.py"):
            assert "result_encoder" not in path.read_text(encoding="utf-8")
    for path in (root / "db").rglob("*.py"):
        assert "maskgw.pgwire" not in path.read_text(encoding="utf-8")


def test_failure_after_frame_allocation_drops_owned_buffers_and_error_chain(monkeypatch):
    columns = (ColumnDescriptor("c0"),)
    decisions = (Decision(Action.ALLOW, "c0"),)
    item = TypedMaskedResult(MaskedResult(columns, decisions, (("x" * (1024 * 1024),),)), (25,))
    native = RuntimeError("CANARY_PRIVATE_WRITE")

    def broken(self, value):
        del self, value
        raise native

    monkeypatch.setattr(encoder_module._Writer, "put", broken)
    tracemalloc.start()
    try:
        with pytest.raises(EncodeError) as caught:
            encode_result(
                item, identity=IDENTITY, limits=ResultLimits(max_rows=10), deadline=deadline()
            )
        retained, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert retained < 512 * 1024
    assert caught.value.category is EncodeFailure.PROTOCOL and caught.value.__context__ is None
    tb = native.__traceback__
    while tb is not None:
        assert not any(
            isinstance(value, bytearray) and len(value) > 512 * 1024
            for value in tb.tb_frame.f_locals.values()
        )
        tb = tb.tb_next


@pytest.mark.parametrize("stage", ["preflight", "allocation", "copy", "validation"])
def test_memory_failure_at_every_stage_is_fatal_not_a_recoverable_limit(monkeypatch, stage):
    def broken(*_args, **_kwargs):
        raise MemoryError("CANARY_STAGE_OOM")

    if stage == "preflight":
        monkeypatch.setattr(encoder_module._Encoder, "preflight", broken)
    elif stage == "allocation":
        monkeypatch.setattr(encoder_module, "bytearray", broken, raising=False)
    elif stage == "copy":
        monkeypatch.setattr(encoder_module, "bytes", broken, raising=False)
    else:
        monkeypatch.setattr(frame_module, "bytearray", broken, raising=False)
    with pytest.raises(EncodeError) as caught:
        encode_result(
            typed(("CANARY_DATA",), (25,)),
            identity=IDENTITY,
            limits=ResultLimits(max_rows=1),
            deadline=deadline(),
        )
    assert caught.value.category.value == "RESULT_ENCODE_MEMORY"
    assert caught.value.fatal
    assert caught.value.__context__ is None and "CANARY" not in str(caught.value)


def test_multiline_multicolumn_empty_null_and_zero_byte_exact():
    columns = (ColumnDescriptor("same"),) * 3
    decisions = (Decision(Action.ALLOW, "same"),) * 3
    item = TypedMaskedResult(
        MaskedResult(columns, decisions, (("", None, 0), (None, False, -1))), (25, 16, 21)
    )
    expected = frame(
        columns=[
            column(name=b"same", oid=25),
            column(name=b"same", oid=16),
            column(name=b"same", oid=21),
        ],
        rows=[[b"", None, b"0"], [None, b"f", b"-1"]],
    )
    assert (
        encode_result(item, identity=IDENTITY, limits=ResultLimits(max_rows=2), deadline=deadline())
        == expected
    )


@pytest.mark.parametrize("truncated", [False, True])
def test_zero_rows_and_truncation_match_whole_independent_frame(truncated):
    base = typed(("x",), (25,))
    rows = base.masked.rows if truncated else ()
    item = TypedMaskedResult(
        MaskedResult(base.masked.columns, base.masked.decisions, rows, truncated), (25,)
    )
    assert encode_result(
        item, identity=IDENTITY, limits=ResultLimits(max_rows=1), deadline=deadline()
    ) == frame(
        columns=[column(name=b"c0")], rows=[[b"x"]] if truncated else [], fields={2: int(truncated)}
    )


def test_rows_above_limit_refused_before_expensive_dto_revalidation(monkeypatch):
    base = typed(("x",), (25,))
    item = TypedMaskedResult(
        MaskedResult(base.masked.columns, base.masked.decisions, base.masked.rows * 2), (25,)
    )
    calls = []

    def forbidden(_self):
        calls.append(True)
        raise AssertionError("must reject count before walking rows")

    monkeypatch.setattr(TypedMaskedResult, "__post_init__", forbidden)
    with pytest.raises(EncodeError) as caught:
        encode_result(item, identity=IDENTITY, limits=ResultLimits(max_rows=1), deadline=deadline())
    assert caught.value.category is EncodeFailure.LIMIT and not calls


def test_encoder_type_branches_cover_exact_wire_table():
    assert (
        encoder_module._TEXT | encoder_module._INTEGER_BITS.keys() | {16} == WIRE_TYPE_SIZES.keys()
    )


@pytest.mark.parametrize("size", [4096, 4097])
def test_ascii_fast_path_boundary_matches_independent_complete_frame(size):
    value = "x" * size
    assert encode_result(
        typed((value,), (25,)),
        identity=IDENTITY,
        limits=ResultLimits(max_rows=1),
        deadline=deadline(),
    ) == frame(columns=[column(name=b"c0")], rows=[[b"x" * size]])


def test_short_unicode_column_name_and_name_value_match_independent_frame():
    value = "\u00e9" * 31 + "x"  # exactly 63 UTF-8 bytes
    columns = (ColumnDescriptor("col\u00e9"),)
    decisions = (Decision(Action.ALLOW, "col\u00e9"),)
    item = TypedMaskedResult(MaskedResult(columns, decisions, ((value,),)), (19,))
    assert encode_result(
        item, identity=IDENTITY, limits=ResultLimits(max_rows=1), deadline=deadline()
    ) == frame(columns=[column(name=b"col\xc3\xa9", oid=19)], rows=[[b"\xc3\xa9" * 31 + b"x"]])


def test_long_ascii_nul_rejected_before_frame_allocation(monkeypatch):
    def forbidden(_size):
        raise AssertionError("invalid text must never allocate a frame")

    monkeypatch.setattr(encoder_module, "bytearray", forbidden, raising=False)
    with pytest.raises(EncodeError) as caught:
        encode_result(
            typed(("x" * 4096 + "\0",), (25,)),
            identity=IDENTITY,
            limits=ResultLimits(max_rows=1),
            deadline=deadline(),
        )
    assert caught.value.category is EncodeFailure.TYPE


@pytest.mark.parametrize("kind", ["null", "short_text", "short_unicode"])
def test_dense_near_maximum_frame_finishes_within_fixed_job_deadline(kind):
    columns = tuple(ColumnDescriptor(f"c{index}") for index in range(1024))
    decisions = tuple(Decision(Action.ALLOW, col.output_name) for col in columns)
    row_count, value = {
        "null": (4000, None),
        "short_text": (3200, "x"),
        "short_unicode": (2600, "\u00e9"),
    }[kind]
    rows = ((value,) * 1024,) * row_count
    item = TypedMaskedResult(MaskedResult(columns, decisions, rows), (25,) * 1024)
    started = time.monotonic()
    raw = encode_result(
        item,
        identity=IDENTITY,
        limits=ResultLimits(max_rows=row_count),
        deadline=ResultDeadline(expires_at=started + 40),
    )
    elapsed = time.monotonic() - started
    assert 15 * 1024 * 1024 < len(raw) < 16 * 1024 * 1024
    assert elapsed < 40
