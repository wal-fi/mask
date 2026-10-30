"""Public reader contracts only. Does not execute a shell, Docker or PostgreSQL."""

import dataclasses
import hashlib
import json
import os
import runpy
import shlex
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
TASK = "a" * 32


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/pg16_shell_reader.py"))


@pytest.fixture
def channel(module: Any) -> Any:
    path = REPO / "docs/poc/w1_bootstrap_channel.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == module["CHANNEL_SHA"]
    return runpy.run_path(str(path))


@pytest.mark.parametrize("name", ["ONE", "BINARY", "FRAGMENTED", "RETAIN"])
def test_positive_vectors_match_authoritative_python_decoder(module, channel, name):
    case = getattr(module["Case"], name)
    vector = module["vector"](case)
    seed = channel["Seed"](channel["Role"].PG, vector.body)
    assert seed.reveal_frame() == vector.wire
    decoded = channel["decode_seed"](vector.wire, channel["Role"].PG)
    assert decoded.reveal() == vector.body
    assert b"".join(vector.chunks) == vector.wire
    assert vector.fault is None
    assert vector.hold_open is (name == "RETAIN")
    assert vector.tail == ("QUIET" if name == "RETAIN" else "EOF")


def test_binary_canary_covers_all_bytes_nul_and_internal_trailer(module):
    vector = module["vector"](module["Case"].BINARY)
    assert len(vector.body) == 16384 and set(vector.body) == set(range(256))
    assert b"SEEDEND\n" in vector.body and b"\x00" in vector.body
    assert len(module["vector"](module["Case"].ONE).body) == 1
    fragmented = module["vector"](module["Case"].FRAGMENTED)
    assert len(fragmented.chunks) > 4 and all(fragmented.chunks)


def test_all_negative_vectors_are_refused_by_authoritative_decoder(module, channel):
    cases = [module["vector"](case) for case in module["Case"]]
    bad = [case for case in cases if case.fault is not None]
    assert len(bad) == 19
    for vector in bad:
        with pytest.raises(channel["BootstrapError"], match="FRAME"):
            channel["decode_seed"](vector.wire, channel["Role"].PG)


@pytest.mark.parametrize("name", ["HEADER_NUL", "HEADER_INNER_NUL", "TRAILER_NUL"])
def test_nul_fault_vectors_preserve_frame_length_but_cannot_pass_bytes(module, name):
    good = module["vector"](module["Case"].BINARY)
    bad = module["vector"](getattr(module["Case"], name))
    assert len(good.wire) == len(bad.wire) and good.wire != bad.wire
    actual = bad.wire[-8:] if name == "TRAILER_NUL" else bad.wire[:16]
    expected = good.wire[-8:] if name == "TRAILER_NUL" else good.wire[:16]
    assert hashlib.sha256(actual).digest() != hashlib.sha256(expected).digest()


def test_source_uses_byte_exact_header_and_trailer_hashes_before_body_use(module):
    source = module["READER_SOURCE"]
    assert module["CORE_SHA"] == hashlib.sha256(source.encode("ascii")).hexdigest()
    assert module["TRAILER_SHA"] == hashlib.sha256(b"SEEDEND\n").hexdigest()
    assert "expected=$(hash_of /tmp/maskgw-reader/expected-header)" in source
    assert '[ "$received" = "$expected" ] || fail HEADER' in source
    assert source.index("fail HEADER\nlength=") < source.index("of=/tmp/maskgw-reader/body")
    assert f"[ \"$received\" = '{module['TRAILER_SHA']}' ] || fail TRAILER" in source
    assert "of=/tmp/maskgw-reader/header 2>/dev/null" in source
    assert "of=/tmp/maskgw-reader/body 2>/dev/null" in source
    assert "of=/tmp/maskgw-reader/trailer 2>/dev/null" in source


def test_ready_line_matches_channel_schema_and_core_not_recursive_wrapper_hash(module, channel):
    target = channel["Target"](
        "c" * 64, TASK, "sha256:" + "d" * 64, module["CORE_SHA"], channel["Role"].PG
    )
    assert module["ready_line"](TASK) == target.ready_line()
    script = module["build"](TASK, module["Case"].BINARY)
    assert hashlib.sha256(script.encode("ascii")).hexdigest() != module["CORE_SHA"]
    assert module["CORE_SHA"] in script
    assert len(module["ready_line"](TASK)) < channel["MAX_READY"]


def test_wrapper_has_pid1_parent_fixed_paths_umask_and_one_global_deadline(module):
    script = module["build"](TASK, module["Case"].BINARY)
    assert script.encode("ascii") and len(script) <= 12000
    assert script.index("umask 077") < script.index("mkdir /tmp/maskgw-reader || precheck")
    assert '[ "$$" -eq 1 ] || precheck' in script
    assert "exec timeout" not in script and "conv=excl" not in script
    marker = "timeout -s KILL 8 /bin/sh -ec "
    segment = script[script.index(marker) : script.rfind(" || status=$?")]
    argv = shlex.split(segment)
    assert argv[:6] == ["timeout", "-s", "KILL", "8", "/bin/sh", "-ec"]
    assert len(argv) == 7 and argv[6].startswith(module["READER_SOURCE"])
    assert "digest=$(hash_of /tmp/maskgw-reader/body)" in argv[6]
    assert 'case "$status" in\n    0) exit 0;;' in script
    assert "wait " not in script
    assert "exec 2>/dev/null" in script
    assert "head " not in script and "cat " not in script and "read -" not in script
    assert "iflag=" not in script and "eval " not in script
    assert "timeout -s KILL 1 dd bs=1 count=1" in argv[6]


def test_records_are_immutable_deterministic_and_never_encode_operator_data(module):
    for case in module["Case"]:
        first = module["vector"](case)
        second = module["vector"](case)
        assert first == second
        with pytest.raises(dataclasses.FrozenInstanceError):
            first.wire = b"changed"
        assert module["build"](TASK, case) == module["build"](TASK, case)


@pytest.mark.parametrize("task", [None, True, "", "a" * 31, "A" * 32, "../" + "a" * 29])
def test_untrusted_task_never_reaches_shell_template(module, task):
    with pytest.raises(module["ReaderError"], match="INPUT"):
        module["build"](task, module["Case"].ONE)


@pytest.mark.parametrize("case", [None, True, b"one", "one", "$(id)", "retain;evil"])
def test_untrusted_case_and_body_encoding_are_not_supported(module, case):
    with pytest.raises(module["ReaderError"], match="INPUT"):
        module["build"](TASK, case)


def test_success_reports_are_exact_public_oracles_and_actual_exit_is_required(module):
    for case in (module["Case"].ONE, module["Case"].BINARY, module["Case"].RETAIN):
        value = module["expected_report"](TASK, case)
        raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
        result = module["parse_report"](raw, 0, TASK, case)
        assert result == {"ok": True, **value}
        for code in (True, False, None, "0", 1, 42, 137):
            with pytest.raises(module["ReaderError"], match="OUTPUT"):
                module["parse_report"](raw, code, TASK, case)


def test_negative_cases_require_their_exact_closed_fault_and_actual_exit42(module):
    for case in module["Case"]:
        vector = module["vector"](case)
        if vector.fault is None:
            continue
        raw = f"fault={vector.fault.value}\n".encode("ascii")
        assert module["parse_report"](raw, 42, TASK, case) == {
            "ok": False,
            "category": vector.fault.value,
        }
        for bad, code in ((raw, 0), (b"fault=UNKNOWN\n", 42), (b"prefix\n" + raw, 42)):
            with pytest.raises(module["ReaderError"], match="OUTPUT"):
                module["parse_report"](bad, code, TASK, case)


def test_parser_refuses_extra_duplicate_noncanonical_cross_case_and_untrusted_bytes(module):
    case = module["Case"].BINARY
    value = module["expected_report"](TASK, case)
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
    mutations = [
        raw[:-1],
        raw + b"extra\n",
        raw + raw,
        module["ready_line"](TASK) + raw,
        b" " + raw,
        raw.replace(b'"body_bytes":16384', b'"body_bytes":true'),
        raw.replace(b'"tail":"EOF"', b'"tail":"QUIET"'),
        raw.replace(b'"task":"' + TASK.encode(), b'"task":"' + b"b" * 32),
        raw.replace(b'"case":"binary"', b'"case":"one"'),
        raw.replace(b"{", b'{"extra":0,', 1),
        b"\xff\x00",
        b"x" * 2049,
        raw.decode("ascii"),
        bytearray(raw),
        None,
    ]
    for bad in mutations:
        with pytest.raises(module["ReaderError"], match="OUTPUT"):
            module["parse_report"](bad, 0, TASK, case)


def test_hostile_objects_are_not_formatted_or_chained_in_errors(module):
    class Hostile:
        def __str__(self):
            raise AssertionError("untrusted str called")

        def __repr__(self):
            raise AssertionError("untrusted repr called")

    for method, args in (
        (module["build"], (Hostile(), module["Case"].ONE)),
        (module["build"], (TASK, Hostile())),
        (module["parse_report"], (Hostile(), 0, TASK, module["Case"].ONE)),
    ):
        with pytest.raises(module["ReaderError"]) as failure:
            method(*args)
        assert failure.value.__cause__ is None and failure.value.__context__ is None
        assert str(failure.value) in ("INPUT", "OUTPUT")


def test_module_import_and_build_do_not_spawn_or_write(monkeypatch):
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("pure builder attempted native effect")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    loaded = runpy.run_path(str(REPO / "docs/poc/pg16_shell_reader.py"))
    assert loaded["build"](TASK, loaded["Case"].BINARY)
