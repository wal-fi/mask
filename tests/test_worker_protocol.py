"""Private wire bounds, scalar invariants and redaction; no I/O or processes."""

import ast
import math
import struct
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from maskgw.pgwire.result_frame import ResultLimits
from maskgw.runtime import worker_protocol as wire
from maskgw.runtime.worker_job import JobFailure


def key() -> wire.SessionKey:
    return wire.SessionKey(b"s" * 16, b"d" * 16, 1, 2)


def init(**changes: Any) -> wire.SecretInit:
    values: dict[str, Any] = {
        "key": key(),
        "limits": ResultLimits(max_rows=10),
        "expires_at": 120.0,
        "nonce": b"N" * 32,
        "snapshot": b"PRIVATE_SNAPSHOT_MARKER",
    }
    return wire.SecretInit(**(values | changes))


def query(**changes: Any) -> wire.Query:
    values: dict[str, Any] = {
        "key": key(),
        "job_id": 1,
        "expires_at": 120.0,
        "sql": b"SELECT 'PRIVATE_SQL_MARKER'",
    }
    return wire.Query(**(values | changes))


def body(packet: bytes, kind: wire.Kind) -> bytes:
    parsed, size = wire.parse_header(packet[: wire.HEADER_BYTES])
    assert parsed is kind and size == len(packet) - wire.HEADER_BYTES
    return packet[wire.HEADER_BYTES :]


def test_roundtrips_and_exact_lengths() -> None:
    value = init()
    packet = wire.encode_init(value)
    assert wire.encode_init(wire.decode_init(body(packet, wire.Kind.INIT))) == packet
    request = query()
    assert wire.decode_query(body(wire.encode_query(request), wire.Kind.QUERY)) == request
    assert wire.decode_done(body(wire.encode_done(key(), 8), wire.Kind.DONE)) == (key(), 8)
    assert wire.decode_guard(
        body(wire.encode_guard(33, 1, 256 * 1024 * 1024), wire.Kind.GUARD_READY)
    ) == (33, 1, 256 * 1024 * 1024)
    assert wire.decode_opened(body(wire.encode_opened(b"T" * 32), wire.Kind.OPENED)) == b"T" * 32
    assert body(wire.encode_close(), wire.Kind.CLOSE) == b""
    assert key().datasource_text() == "dso_" + (b"d" * 16).hex()
    assert key().result_identity(9).job_id == 9


def test_max_init_exceeds_pipe_capacity_but_is_bounded() -> None:
    value = init(snapshot=b"x" * 65536)
    packet = wire.encode_init(value)
    assert 65536 < len(packet) < 66000
    assert wire.encode_init(wire.decode_init(body(packet, wire.Kind.INIT))) == packet
    with pytest.raises(wire.WorkerProtocolError):
        init(snapshot=b"x" * 65537)


@pytest.mark.parametrize(
    "sql",
    [b"", b"x" * 65537, b"SELECT\0secret", b"\xff", "SELECT 1", None],
    ids=["empty", "over-limit", "nul", "invalid-utf8", "wrong-type", "none"],
)
def test_sql_invalid_inputs(sql: Any) -> None:
    with pytest.raises(wire.WorkerProtocolError) as exc:
        query(sql=sql)
    assert "secret" not in repr(exc.value)
    assert exc.value.__context__ is None


def test_max_sql_and_utf8() -> None:
    for sql in (b"x" * 65536, "SELECT '日本語'".encode()):
        value = query(sql=sql)
        assert wire.decode_query(body(wire.encode_query(value), wire.Kind.QUERY)) == value


@pytest.mark.parametrize(
    "changes",
    [
        {"nonce": b"x" * 31},
        {"nonce": bytearray(32)},
        {"snapshot": b""},
        {"expires_at": math.nan},
        {"expires_at": math.inf},
        {"expires_at": True},
        {"expires_at": -1.0},
        {"expires_at": 120},
        {"limits": object()},
        {"key": object()},
    ],
)
def test_init_is_closed(changes: dict[str, Any]) -> None:
    with pytest.raises(wire.WorkerProtocolError):
        init(**changes)


@pytest.mark.parametrize(
    "sid,ds,gen,rev",
    [
        (b"x", b"d" * 16, 1, 1),
        (b"s" * 16, bytearray(16), 1, 1),
        (b"s" * 16, b"d" * 16, True, 1),
        (b"s" * 16, b"d" * 16, 0, 1),
        (b"s" * 16, b"d" * 16, 1, 1 << 63),
    ],
)
def test_identity_fields_are_exact(sid: Any, ds: Any, gen: Any, rev: Any) -> None:
    with pytest.raises(wire.WorkerProtocolError):
        wire.SessionKey(sid, ds, gen, rev)


@pytest.mark.parametrize(
    "magic,version,tag,reserved,size",
    [
        (b"BAD!", 2, 8, 0, 0),
        (b"MGW2", 3, 8, 0, 0),
        (b"MGW2", 2, 255, 0, 0),
        (b"MGW2", 2, 8, 1, 0),
        (b"MGW2", 2, 8, 0, 1),
        (b"MGW2", 2, 4, 0, 0xFFFFFFFF),
    ],
)
def test_header_is_rejected_before_body_allocation(
    magic: bytes, version: int, tag: int, reserved: int, size: int
) -> None:
    header = struct.pack("!4sBBHI", magic, version, tag, reserved, size)
    with pytest.raises(wire.WorkerProtocolError):
        wire.parse_header(header)


@pytest.mark.parametrize("kind", list(wire.Kind))
def test_lengths_exact_by_kind(kind: wire.Kind) -> None:
    low, high = wire._LENGTHS[kind]
    wire.check_length(kind, low)
    wire.check_length(kind, high)
    for value in (low - 1, high + 1, True):
        with pytest.raises(wire.WorkerProtocolError):
            wire.check_length(kind, value)


@pytest.mark.parametrize("kind", [1, True, "INIT", None])
def test_kind_requires_exact_enum(kind: Any) -> None:
    with pytest.raises(wire.WorkerProtocolError):
        wire.check_length(kind, 0)


@pytest.mark.parametrize("category", list(wire.WireFailure))
@pytest.mark.parametrize("continuing", [False, True])
def test_error_recoverability_is_closed(category: wire.WireFailure, continuing: bool) -> None:
    if continuing and category.name not in {"QUERY", "TIMEOUT", "TYPE", "LIMIT"}:
        with pytest.raises(wire.WorkerProtocolError):
            wire.ErrorReply(key(), 1, category, continuing)
    else:
        value = wire.ErrorReply(key(), 1, category, continuing)
        assert wire.decode_error(body(wire.encode_error(value), wire.Kind.ERROR)) == value
    with pytest.raises(wire.WorkerProtocolError):
        wire.ErrorReply(key(), 0, category, True)


def test_wire_failure_names_match_body_without_importing_body_in_codec() -> None:
    assert set(wire.WireFailure.__members__) == set(JobFailure.__members__)
    root = Path(__file__).resolve().parents[1] / "src/maskgw/runtime/worker_protocol.py"
    nodes = list(ast.walk(ast.parse(root.read_text(encoding="utf-8"))))
    assert not any(
        isinstance(n, ast.ImportFrom) and (n.module or "").endswith("worker_job") for n in nodes
    )


def test_protocol_remains_pure_with_no_operational_importer() -> None:
    root = Path(__file__).resolve().parents[1] / "src/maskgw"
    module = root / "runtime/worker_protocol.py"
    imported: set[str | None] = set()
    for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.update(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module)
    assert imported == {
        "__future__",
        "math",
        "struct",
        "dataclasses",
        "enum",
        "typing",
        "maskgw.pgwire.result_frame",
    }
    for other in root.rglob("*.py"):
        if other in (
            module,
            root / "runtime/worker_process.py",
            root / "runtime/worker_session.py",
        ):
            continue
        for node in ast.walk(ast.parse(other.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert all(not alias.name.endswith("worker_protocol") for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").endswith("worker_protocol")
                assert all(alias.name != "worker_protocol" for alias in node.names)


@pytest.mark.parametrize(
    "expires,now,maximum",
    [
        (100.0, 100.0, 12.0),
        (99.0, 100.0, 12.0),
        (113.0, 100.0, 12.0),
        (math.inf, 100.0, 12.0),
        (110.0, math.nan, 12.0),
        (110.0, 100.0, 0.0),
        (110.0, 100.0, 611.0),
        (True, 100.0, 12.0),
    ],
)
def test_deadline_is_finite_not_expired_and_never_extended(
    expires: Any, now: float, maximum: float
) -> None:
    with pytest.raises(wire.WorkerProtocolError):
        wire.check_deadline(expires, now=now, maximum_seconds=maximum)
    wire.check_deadline(112.0, now=100.0, maximum_seconds=12.0)


def test_result_notice_is_empty_and_not_a_second_size_authority() -> None:
    assert body(wire.encode_result_notice(), wire.Kind.RESULT) == b""
    assert not hasattr(wire, "encode_result_size") and not hasattr(wire, "decode_result_size")


@pytest.mark.parametrize("size", [1, 4, 16 * 1024 * 1024])
def test_result_nonempty_control_body_is_fatal(size: int) -> None:
    with pytest.raises(wire.WorkerProtocolError):
        wire.parse_header(struct.pack("!4sBBHI", b"MGW2", 2, 6, 0, size))


@pytest.mark.parametrize("magic,version", [(b"MGW1", 1), (b"MGW1", 2), (b"MGW2", 1)])
def test_v1_and_cross_version_combinations_are_refused_without_fallback(
    magic: bytes, version: int
) -> None:
    with pytest.raises(wire.WorkerProtocolError):
        wire.parse_header(struct.pack("!4sBBHI", magic, version, 8, 0, 0))


@pytest.mark.parametrize(
    "decoder,packet",
    [
        (wire.decode_init, wire.encode_init(init())),
        (
            wire.decode_error,
            wire.encode_error(wire.ErrorReply(key(), 1, wire.WireFailure.QUERY, False)),
        ),
        (wire.decode_done, wire.encode_done(key(), 1)),
        (wire.decode_guard, wire.encode_guard(2, 1, 256 * 1024 * 1024)),
    ],
)
def test_truncated_and_appended_bodies_do_not_parse(decoder: Any, packet: bytes) -> None:
    data = packet[wire.HEADER_BYTES :]
    for changed in (data[:-1], data + b"x"):
        with pytest.raises(wire.WorkerProtocolError):
            decoder(changed)


def test_repr_and_errors_never_include_payload_or_tag() -> None:
    assert "PRIVATE_" not in repr(init()) + repr(query())
    with pytest.raises(FrozenInstanceError):
        setattr(init(), "snapshot", b"mutated")  # noqa: B010 - intentional frozen-record violation
    value = init()
    object.__setattr__(value, "nonce", b"invalid")
    with pytest.raises(wire.WorkerProtocolError):
        wire.encode_init(value)


def test_variable_sql_requires_exact_framing_at_transport_and_strict_utf8() -> None:
    packet = wire.encode_query(query(sql="SELECT 'あ".encode()))
    data = packet[wire.HEADER_BYTES :]
    for changed in (data[:-1], data + b"\0"):
        with pytest.raises(wire.WorkerProtocolError):
            wire.decode_query(changed)
    # Valid ASCII appended would be a different valid SQL body. The transport
    # must read EXACTLY the header length, never pass an arbitrary larger body.
    declared = wire.parse_header(packet[: wire.HEADER_BYTES])[1]
    assert len(data + b"x") != declared


@pytest.mark.parametrize("code,continuing,reserved", [(255, 0, 0), (1, 2, 0), (1, 0, 1), (5, 1, 0)])
def test_error_raw_fields_are_closed(code: int, continuing: int, reserved: int) -> None:
    packet = wire.encode_error(wire.ErrorReply(key(), 1, wire.WireFailure.QUERY, False))
    data = packet[wire.HEADER_BYTES : -4] + struct.pack("!BBH", code, continuing, reserved)
    with pytest.raises(wire.WorkerProtocolError):
        wire.decode_error(data)


@pytest.mark.parametrize("dumpable,death,reserved", [(1, 9, 0), (0, 0, 0), (0, 9, 1)])
def test_guard_scalar_downgrades_are_rejected(dumpable: int, death: int, reserved: int) -> None:
    packet = wire.encode_guard(2, 1, 256 * 1024 * 1024)
    data = packet[wire.HEADER_BYTES : -4] + struct.pack("!BBH", dumpable, death, reserved)
    with pytest.raises(wire.WorkerProtocolError):
        wire.decode_guard(data)


def test_init_claimed_size_and_limits_must_match() -> None:
    value = init()
    data = body(wire.encode_init(value), wire.Kind.INIT)
    metadata_end = len(data) - len(value.snapshot)
    changed = data[: metadata_end - 4] + struct.pack("!I", len(value.snapshot) + 1) + value.snapshot
    with pytest.raises(wire.WorkerProtocolError):
        wire.decode_init(changed)
    invalid_limits = data[:48] + b"\0" * 4 + data[52:]
    with pytest.raises(wire.WorkerProtocolError) as exc:
        wire.decode_init(invalid_limits)
    assert exc.value.__context__ is None


@pytest.mark.parametrize("operation", ["encode", "decode"])
def test_memory_exhaustion_is_not_misclassified_as_bad_protocol(
    monkeypatch: Any, operation: str
) -> None:
    value = init()
    packet = wire.encode_init(value)

    def exhausted(_self: ResultLimits) -> None:
        raise MemoryError()

    monkeypatch.setattr(ResultLimits, "__post_init__", exhausted)
    with pytest.raises(MemoryError):
        if operation == "encode":
            wire.encode_init(value)
        else:
            wire.decode_init(packet[wire.HEADER_BYTES :])


def test_all_valid_limits_maxima_fit_the_wire_widths() -> None:
    limits = ResultLimits(
        max_rows=(1 << 31) - 1,
        max_frame_bytes=16 * 1024 * 1024,
        max_cell_bytes=1024 * 1024,
        max_columns=1664,
        max_name_bytes=256,
    )
    value = init(limits=limits)
    packet = wire.encode_init(value)
    decoded = wire.decode_init(body(packet, wire.Kind.INIT))
    assert decoded.limits == limits
    assert wire.encode_init(decoded) == packet
    assert decoded != value  # SecretInit equality is deliberately identity-only.


@pytest.mark.parametrize(
    "field,bits",
    [
        ("max_rows", 32),
        ("max_frame_bytes", 32),
        ("max_cell_bytes", 32),
        ("max_columns", 16),
        ("max_name_bytes", 16),
    ],
)
def test_limit_width_overflows_are_refused_before_struct_pack(field: str, bits: int) -> None:
    value = init()
    object.__setattr__(value.limits, field, 1 << bits)
    with pytest.raises(wire.WorkerProtocolError):
        wire.encode_init(value)
