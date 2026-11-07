"""Pure W1 Oracle lab controller prefix: wire, schema, SQL table, capture, transitions.

RED-first contract for the FUTURE ``deploy/oracle9_w1_controller.py``. The module
stays absent until the root reviews these oracles: feature tests then fail with
FileNotFoundError, while the ``test_sanity_*`` checks below never load it. No
main, spawn, socket, thread, Docker, PostgreSQL or SQL execution is involved.
Lab wire only (W1-ORACLE-NATIVE-PLAN v4 + PLAN-REVIEW), not MGW2 or state16.

Minimal stable API of the future pure module (``runpy`` namespace):

- ``LabRefusal``: ``category`` in INIT/CONTROL/PHASE/SQL/CAPTURE/DESTINATION,
  ``args == (category,)``, no cause/context/input value.
- ``decode_init(packet) -> LabInit``: ``>4sI`` MGI1 + canonical ASCII JSON body.
  Frozen, redacted: ``target`` (ip/port/database/username), ``readonly_password``,
  ``hmac_key``, ``raw_canaries`` (tuple), ``expected`` (tuple of records with
  job/kind/rows/bytes/sha256/reason).
- ``decode_control(frame) -> Control`` (kind/case/seq); ``GO``/``STOP``/
  ``NOSTOP``/``ACK``.
- ``ControlMachine()``: ``emit(event, case) -> next_seq`` for READY/RESULT/ARMED,
  ``accept(frame)``, ``handoff()``, ``join(frame | None)``, ``summary()``
  (prefix_cases/failed_cases/global_pass), ``eof()``; properties ``next_seq``,
  ``accepted``, ``reader`` (MAIN/WATCHER), ``aborted``.
- ``job_sql(job, canary)``, ``HEAVY_SQL``, ``TABLE``.
- ``exact_resolver(ip, port)``, ``pinned_addresses(ip, port)``.
- ``DATASOURCE_ID``, ``RECORD_REVISION``, ``capture(init, generation) -> bytes``
  for generation 1 (G1) and 2 (G2), through the public composition only.
"""

from __future__ import annotations

import ast
import functools
import hashlib
import json
import runpy
import socket
import struct
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

import psycopg
import pytest

from maskgw.config.gateway import GatewayConfig, parse_config_bundle
from maskgw.datasource import resolver as dns_resolver
from maskgw.datasource.models import (
    DatasourceLimits,
    DatasourcePolicy,
    DestinationPolicy,
    TlsSettings,
)
from maskgw.errors import QueryRejected
from maskgw.masking.descriptor import ColumnDescriptor
from maskgw.masking.engine import Action
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.runtime.candidate import (
    CandidateSpec,
    build_candidate,
    build_conninfo,
    effective_database_settings,
)
from maskgw.runtime.snapshot import (
    RecordingSecrets,
    SnapshotIdentity,
    capture_template,
    recompile_snapshot,
)
from maskgw.secretsource import EnvSecretProvider, MappingSecretProvider
from maskgw.sql.policy import DEFAULT_SQL_POLICY
from maskgw.sql.validator import validate_select
from tests.datasource_runtime_support import FakeFactory
from tests.datasource_runtime_support import resolver as support_resolver

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "deploy/oracle9_w1_controller.py"

INIT_HEADER = struct.Struct(">4sI")
CONTROL = struct.Struct(">4sBBHII")
MAX_BODY = 65536
FRAME_LIMIT = 16 * 1024 * 1024
GO, STOP, NOSTOP, ACK = 1, 2, 3, 4
T4, T6 = 23, 25

IP = "10.0.0.7"
PORT = 5432
DATABASE = "maskgw_lab"
USERNAME = "maskgw_reader"
READONLY_HEX = "0123456789abcdef" * 3
HMAC_KEY = "fedcba9876543210" * 4
CANARIES = ("canary-alpha-7Q", "canary-beta-9Z")
UNSPECIFIED = ".".join(["0"] * 4)
E_ACUTE = chr(0xE9)
SURROGATE = chr(0xD800)
DATASOURCE_ID = "dso_" + "0" * 31 + "1"
ERRORS = {11: "LIMIT", 13: "QUERY", 14: "QUERY", 15: "QUERY", 16: "TIMEOUT", 18: "TYPE"}
TABLE = "maskgw_lab.t"
HEAVY = (
    "SELECT count(*) FROM generate_series(1,100000) AS a CROSS JOIN generate_series(1,100000) AS b"
)
SQL = {
    1: "SELECT id, active FROM maskgw_lab.t ORDER BY id",
    2: "SELECT cpf FROM maskgw_lab.t ORDER BY id",
    3: "SELECT cpf AS tipo_cpf, tipo_cpf AS cpf FROM maskgw_lab.t WHERE id=1",
    4: "SELECT substr(cpf,1,3) AS same, email AS same, active, id FROM maskgw_lab.t ORDER BY id",
    5: "SELECT cpf FROM maskgw_lab.t WHERE id=1 UNION ALL SELECT cpf FROM maskgw_lab.t WHERE id=2",
    6: "WITH c AS (SELECT cpf AS x FROM maskgw_lab.t) SELECT x FROM c",
    7: "SELECT x FROM (SELECT email AS x FROM maskgw_lab.t) AS s",
    8: "SELECT numeric_secret FROM maskgw_lab.t ORDER BY id",
    9: "SELECT g FROM generate_series(1,1001) AS g",
    10: "SELECT repeat('x',1048576) AS v FROM generate_series(1,15) AS g",
    11: "SELECT repeat('x',1048576) AS v FROM generate_series(1,17) AS g",
    12: "SELECT 1",
    14: "DELETE FROM maskgw_lab.t",
    15: "SELECT pg_read_file('postgresql.conf')",
    16: HEAVY,
    17: "SELECT 2",
    18: "SELECT amount FROM maskgw_lab.t WHERE id=1",
    19: "SELECT 3",
}
TIMEOUTS = {1: 1000, 2: 30000}
LAB_MASKING = [
    {"match": "cpf", "transformer": "hmac_sha256"},
    {
        "match": "email",
        "transformer": "regex",
        "config": {"pattern": "^(.{2}).*(@.*)$", "replacement": "\\1***\\2"},
    },
    {"match": "numeric_secret", "transformer": "fixed", "config": {"value": "[NUMBER]"}},
    {
        "match": "token",
        "transformer": "random",
        "config": {"strategy": "alphanumeric", "preserve_length": False, "length": 12},
    },
]
MISSING = object()

Step = tuple[str, int, int]


@functools.cache
def lab() -> dict[str, Any]:
    return runpy.run_path(str(SOURCE))


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def packet(body: bytes) -> bytes:
    return INIT_HEADER.pack(b"MGI1", len(body)) + body


def sha_for(job: int) -> str:
    return hashlib.sha256(bytes([job])).hexdigest()


SHAS = tuple(sha_for(job) for job in range(1, 20) if job not in ERRORS)
LEAKS = (READONLY_HEX, HMAC_KEY, *CANARIES, *SHAS)


def expected_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for job in range(1, 20):
        if job in ERRORS:
            records.append(
                {
                    "job": job,
                    "kind": "ERROR",
                    "rows": None,
                    "bytes": None,
                    "sha256": None,
                    "reason": ERRORS[job],
                }
            )
        else:
            records.append(
                {
                    "job": job,
                    "kind": "RESULT",
                    "rows": 3,
                    "bytes": 100 + job,
                    "sha256": sha_for(job),
                    "reason": None,
                }
            )
    return records


RECORDS = expected_records()


def valid_body() -> dict[str, Any]:
    return {
        "kind": "MASKGW_W1_LAB_INIT_V1",
        "version": 1,
        "target": {"ip": IP, "port": PORT, "database": DATABASE, "username": USERNAME},
        "readonly_password": READONLY_HEX,
        "hmac_key": HMAC_KEY,
        "raw_canaries": list(CANARIES),
        "expected": expected_records(),
    }


VALID = canonical(valid_body())
SPACED = json.dumps(valid_body(), sort_keys=True, indent=1).encode()
UNSORTED = json.dumps(valid_body(), separators=(",", ":")).encode()
OVER_CAP = INIT_HEADER.pack(b"MGI1", MAX_BODY + 1) + b" " * (MAX_BODY + 1)
NON_ASCII = packet(VALID.replace(b"canary-alpha", b"c\xe4nary-alpha"))
ESCAPED = packet(VALID.replace(b"canary-alpha", b"c\\u0061nary-alpha"))
DUPLICATE_TARGET = packet(VALID.replace(b'"port":5432,', b'"port":5432,"port":5432,'))
DUPLICATE_RECORD = packet(VALID.replace(b'{"bytes":101,', b'{"bytes":101,"bytes":101,'))


class BytesSubclass(bytes):
    """Exact ``bytes`` is the public decoder boundary; subclasses are refused."""


def version_as(text: bytes) -> bytes:
    return packet(VALID.replace(b'"version":1}', b'"version":' + text + b"}"))


def mutated(path: tuple[str | int, ...], value: object) -> bytes:
    body = valid_body()
    node: Any = body
    for key in path[:-1]:
        node = node[key]
    if value is MISSING:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return packet(canonical(body))


def expected_sql(job: int, canary: str = CANARIES[0]) -> str:
    if job == 13:
        return "SELECT '" + canary.replace("'", "''") + "'::integer"
    return SQL[job]


def frame(kind: int, case: int, seq: int) -> bytes:
    return CONTROL.pack(b"MGL1", 1, kind, case, seq, 0)


def assert_refusal(info: pytest.ExceptionInfo[Any], category: str) -> None:
    error = info.value
    assert error.category == category
    assert error.args == (category,)
    assert error.__cause__ is None
    assert error.__context__ is None
    text = str(error) + repr(error)
    for leak in LEAKS:
        assert leak not in text


@pytest.fixture
def forbidden(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Real network, DNS, process, thread and environment secret paths are traps."""
    calls: list[str] = []

    def trap(name: str) -> Callable[..., NoReturn]:
        def blocked(*_args: object, **_kwargs: object) -> NoReturn:
            calls.append(name)
            raise AssertionError(name)

        return blocked

    monkeypatch.setattr(psycopg, "connect", trap("psycopg.connect"))
    monkeypatch.setattr(socket, "getaddrinfo", trap("socket.getaddrinfo"))
    monkeypatch.setattr(socket, "socketpair", trap("socket.socketpair"))
    monkeypatch.setattr(socket, "create_connection", trap("socket.create_connection"))
    monkeypatch.setattr(subprocess, "Popen", trap("subprocess.Popen"))
    monkeypatch.setattr(threading.Thread, "start", trap("Thread.start"))
    monkeypatch.setattr(dns_resolver, "bounded_system_resolver", trap("bounded_resolver"))
    monkeypatch.setattr(EnvSecretProvider, "get", trap("EnvSecretProvider.get"))
    monkeypatch.setenv(HMAC_KEY_ENV, "synthetic-poisoned-environment-hmac-key-0000")
    return calls


# ---------------------------------------------------------------- sanity, no module


def test_sanity_golden_headers_are_spec_arithmetic_not_roundtrip() -> None:
    assert INIT_HEADER.pack(b"MGI1", 5) == b"MGI1\x00\x00\x00\x05"
    assert INIT_HEADER.size == 8
    assert CONTROL.size == 16
    assert frame(STOP, T4, 46) == bytes.fromhex("4d474c31 01 02 0017 0000002e 00000000")
    assert frame(GO, 1, 1) == bytes.fromhex("4d474c31 01 01 0001 00000001 00000000")


def test_sanity_manual_canonical_init_body() -> None:
    assert VALID.startswith(b'{"expected":[{"bytes":101,"job":1,"kind":"RESULT"')
    assert VALID.endswith(b',"version":1}')
    assert b" " not in VALID
    assert b"\n" not in VALID
    assert json.loads(VALID) == valid_body()
    assert len(VALID) < MAX_BODY
    for crafted in (DUPLICATE_TARGET, DUPLICATE_RECORD):
        assert crafted != packet(VALID)
        assert INIT_HEADER.unpack(crafted[:8]) == (b"MGI1", len(crafted) - 8)
        assert json.loads(crafted[8:]) == valid_body()  # last duplicate wins in plain json


def script(t4: int) -> list[Step]:
    """Host/controller order: 24 normal cases, T4 watcher window, SUMMARY, T6 GO."""
    steps: list[Step] = []
    for case in range(1, 25):
        steps += [("READY", 0, case), ("accept", GO, case)]
        if case == T4:
            steps += [("ARMED", 0, T4), ("handoff", 0, T4), ("join", t4, T4)]
        steps += [("RESULT", 0, case), ("accept", ACK, case)]
    steps += [("summary", 0, 0), ("READY", 0, T6), ("accept", GO, T6), ("ARMED", 0, T6)]
    return steps


@pytest.mark.parametrize("t4", [STOP, NOSTOP], ids=["stop", "nostop"])
def test_sanity_manual_host_plan_has_exactly_fifty_frames(t4: int) -> None:
    frames = [(kind, case) for action, kind, case in script(t4) if action in ("accept", "join")]
    kinds = [kind for kind, _ in frames]
    assert len(frames) == 50
    assert kinds.count(GO) == 25
    assert kinds.count(ACK) == 24
    assert kinds.count(t4) == 1
    assert frames.index((t4, T4)) + 1 == 46  # seq of the single watcher frame
    assert frames[-1] == (GO, T6)
    assert sorted({case for _, case in frames}) == list(range(1, 26))


@pytest.mark.parametrize("job", range(1, 20))
def test_sanity_sql_intent_with_default_validator(job: int) -> None:
    sql = expected_sql(job)
    assert "pg_sleep" not in sql
    if job in (14, 15):
        with pytest.raises(QueryRejected):
            validate_select(sql)
    else:
        validate_select(sql)


def test_sanity_default_policy_has_no_sleep_allowance() -> None:
    assert DEFAULT_SQL_POLICY.allows("pg_sleep") is False
    assert DEFAULT_SQL_POLICY.allows("pg_read_file") is False
    for name in ("generate_series", "repeat", "substr", "count"):
        assert DEFAULT_SQL_POLICY.allows(name) is True


def spec(policy: DatasourcePolicy, limits: DatasourceLimits, ip: str = IP) -> CandidateSpec:
    return CandidateSpec(
        host=ip,
        port=PORT,
        database=DATABASE,
        username=USERNAME,
        tls=TlsSettings(mode="disable"),
        policy=policy,
        limits=limits,
        destination_policy=DestinationPolicy(),
        expected_addresses=(ip,),
        secret=READONLY_HEX,
    )


def oracle(policy: DatasourcePolicy, limits: DatasourceLimits, ident: SnapshotIdentity) -> bytes:
    """Accepted D-111 fake-candidate control: comparison ONLY, never producer path."""
    prepared = build_candidate(
        spec(policy, limits),
        secrets=MappingSecretProvider({HMAC_KEY_ENV: HMAC_KEY}),
        resolver=support_resolver,
        adapter_factory=FakeFactory(),
        verifier=lambda _prepared: None,
        capture_snapshot=True,
    )
    template = prepared.snapshot_template
    assert template is not None
    return template.bind(ident)


def compose(policy: DatasourcePolicy, limits: DatasourceLimits, ident: SnapshotIdentity) -> bytes:
    recorder = RecordingSecrets(MappingSecretProvider({HMAC_KEY_ENV: HMAC_KEY}))
    loaded = parse_config_bundle(policy.to_mapping(), secrets=recorder)
    settings = effective_database_settings(loaded.file_config, limits)
    config = GatewayConfig(
        masking=loaded.gateway.masking, database=settings, sql=loaded.gateway.sql
    )
    conninfo = build_conninfo(spec(policy, limits), (IP,))
    return capture_template(policy, config, conninfo, recorder).bind(ident)


@pytest.mark.parametrize("policy_name", ["default-policy", "hmac-policy"])
@pytest.mark.parametrize("limits_name", ["default-limits", "tight-limits"])
def test_sanity_public_composition_equals_fake_candidate_oracle(
    forbidden: list[str], policy_name: str, limits_name: str
) -> None:
    raw: dict[str, Any] = {}
    if policy_name == "hmac-policy":
        raw = {"masking": [{"match": "cpf", "transformer": "hmac_sha256"}]}
    policy = DatasourcePolicy.from_mapping(raw)
    limits = (
        DatasourceLimits()
        if limits_name == "default-limits"
        else DatasourceLimits(statement_timeout_ms=1000, max_rows=7)
    )
    ident = SnapshotIdentity(DATASOURCE_ID, 1, 1)
    assert compose(policy, limits, ident) == oracle(policy, limits, ident)
    assert forbidden == []


# ---------------------------------------------------------------- module purity


FORBIDDEN_IMPORTS = frozenset(
    {
        "asyncio",
        "ctypes",
        "io",
        "multiprocessing",
        "os",
        "pathlib",
        "psycopg",
        "select",
        "shutil",
        "signal",
        "socket",
        "subprocess",
        "sys",
        "tempfile",
        "threading",
    }
)
FORBIDDEN_CALLS = frozenset(
    {"open", "print", "input", "exec", "eval", "compile", "__import__", "breakpoint"}
)
FORBIDDEN_NAMES = frozenset(
    {
        "build_candidate",
        "verify_prepared",
        "verify_adapter",
        "PreparedRuntime",
        "EnvSecretProvider",
        "bounded_system_resolver",
        "getaddrinfo",
        "connect",
        "main",
    }
)
REQUIRED_NAMES = frozenset(
    {
        "parse_config_bundle",
        "effective_database_settings",
        "GatewayConfig",
        "RecordingSecrets",
        "MappingSecretProvider",
        "build_conninfo",
        "capture_template",
        "resolve_destination",
    }
)


def test_module_source_is_definitions_only_and_uses_public_composition() -> None:
    tree = ast.parse(SOURCE.read_text("utf-8"))
    imports: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Name):
            names.add(node.id)
            assert node.id != "__name__"
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in FORBIDDEN_CALLS
    assert not imports & FORBIDDEN_IMPORTS
    assert not names & FORBIDDEN_NAMES
    assert names >= REQUIRED_NAMES


def test_module_load_has_no_effect(forbidden: list[str]) -> None:
    namespace = runpy.run_path(str(SOURCE))
    assert forbidden == []
    assert callable(namespace["decode_init"])


# ---------------------------------------------------------------- LAB_INIT


def test_decode_init_golden_packet_detached_redacted_immutable() -> None:
    m = lab()
    raw = packet(VALID)
    assert raw[:8] == b"MGI1" + len(VALID).to_bytes(4, "big")
    init = m["decode_init"](raw)
    target = init.target
    assert (target.ip, target.port, target.database, target.username) == (
        IP,
        PORT,
        DATABASE,
        USERNAME,
    )
    assert init.readonly_password == READONLY_HEX
    assert init.hmac_key == HMAC_KEY  # text, never hex-decoded
    assert init.raw_canaries == CANARIES
    assert type(init.raw_canaries) is tuple
    assert type(init.expected) is tuple
    fields = ("job", "kind", "rows", "bytes", "sha256", "reason")
    for record, source in zip(init.expected, RECORDS, strict=True):
        assert tuple(getattr(record, name) for name in fields) == tuple(
            source[name] for name in fields
        )
    for text in (repr(init), str(init), *(repr(record) for record in init.expected)):
        for leak in LEAKS:
            assert leak not in text
    with pytest.raises(AttributeError):
        init.hmac_key = "changed"
    with pytest.raises(AttributeError):
        init.expected[0].rows = 1
    with pytest.raises(AttributeError):
        init.target.ip = "10.0.0.8"
    with pytest.raises(AttributeError):
        init.target.port = 1
    with pytest.raises(AttributeError):
        init.target = None


RAW_REFUSALS = [
    pytest.param(packet(VALID) + b"\x00", id="trailing-byte"),
    pytest.param(packet(VALID + b"\n"), id="trailing-lf"),
    pytest.param(packet(VALID)[:-1], id="truncated-body"),
    pytest.param(INIT_HEADER.pack(b"MGI1", len(VALID) + 1) + VALID, id="header-longer"),
    pytest.param(INIT_HEADER.pack(b"MGI1", 0), id="empty-body"),
    pytest.param(OVER_CAP, id="body-over-cap"),
    pytest.param(INIT_HEADER.pack(b"MGI2", len(VALID)) + VALID, id="magic"),
    pytest.param(b"MGI1", id="short-header"),
    pytest.param(b"", id="empty-packet"),
    pytest.param(bytearray(packet(VALID)), id="bytearray"),
    pytest.param(NON_ASCII, id="non-ascii-byte"),
    pytest.param(packet(SPACED), id="spaces"),
    pytest.param(packet(UNSORTED), id="unsorted"),
    pytest.param(version_as(b'1,"version":1'), id="duplicate-key"),
    pytest.param(version_as(b"NaN"), id="nan"),
    pytest.param(version_as(b"Infinity"), id="infinity"),
    pytest.param(ESCAPED, id="escaped"),
    pytest.param(packet(b"[]"), id="array-root"),
    pytest.param(packet(b"null"), id="null-root"),
    pytest.param(DUPLICATE_TARGET, id="duplicate-target-key"),
    pytest.param(DUPLICATE_RECORD, id="duplicate-record-key"),
    pytest.param(BytesSubclass(packet(VALID)), id="bytes-subclass"),
]


@pytest.mark.parametrize("raw", RAW_REFUSALS)
def test_decode_init_refuses_raw_packet(raw: object) -> None:
    m = lab()
    with pytest.raises(m["LabRefusal"]) as info:
        m["decode_init"](raw)
    assert_refusal(info, "INIT")


def schema(path: tuple[str | int, ...], value: object, name: str) -> Any:
    return pytest.param(path, value, id=name)


SCHEMA_REFUSALS = [
    schema(("kind",), "MASKGW_W1_LAB_INIT_V2", "kind"),
    schema(("version",), True, "version-bool"),
    schema(("version",), 2, "version-2"),
    schema(("version",), 1.0, "version-float"),
    schema(("version",), "1", "version-str"),
    schema(("sql",), "SELECT 1", "extra-sql"),
    schema(("statement_timeout_ms",), 1, "extra-profile-knob"),
    schema(("hmac_key",), MISSING, "missing-key"),
    schema(("target",), [IP, PORT, DATABASE, USERNAME], "target-list"),
    schema(("target",), IP, "target-str"),
    schema(("target", "extra"), 1, "target-extra"),
    schema(("target", "username"), MISSING, "target-missing"),
    schema(("target", "ip"), "127.0.0.1", "ip-loopback"),
    schema(("target", "ip"), "169.254.169.254", "ip-metadata"),
    schema(("target", "ip"), "8.8.8.8", "ip-public"),
    schema(("target", "ip"), UNSPECIFIED, "ip-unspecified"),
    schema(("target", "ip"), "fd00::1", "ip-v6"),
    schema(("target", "ip"), "010.0.0.7", "ip-noncanonical"),
    schema(("target", "ip"), "10.0.0.7 ", "ip-space"),
    schema(("target", "ip"), "10.0.0.256", "ip-invalid"),
    schema(("target", "ip"), "db.internal.example", "ip-hostname"),
    schema(("target", "ip"), 7, "ip-int"),
    schema(("target", "port"), 0, "port-0"),
    schema(("target", "port"), 65536, "port-65536"),
    schema(("target", "port"), True, "port-bool"),
    schema(("target", "port"), "5432", "port-str"),
    schema(("target", "port"), 5432.0, "port-float"),
    schema(("target", "database"), "d" * 64, "database-64"),
    schema(("target", "database"), "Maskgw", "database-upper"),
    schema(("target", "database"), "1abc", "database-digit"),
    schema(("target", "database"), "a-b", "database-hyphen"),
    schema(("target", "database"), "", "database-empty"),
    schema(("target", "username"), "u" * 64, "username-64"),
    schema(("target", "username"), "user" + E_ACUTE, "username-non-ascii"),
    schema(("readonly_password",), "0" * 47, "password-47"),
    schema(("readonly_password",), "0" * 49, "password-49"),
    schema(("readonly_password",), "A" * 48, "password-upper"),
    schema(("readonly_password",), "g" * 48, "password-non-hex"),
    schema(("readonly_password",), 10**47, "password-int"),
    schema(("readonly_password",), [READONLY_HEX], "password-list"),
    schema(("hmac_key",), None, "hmac-null"),
    schema(("hmac_key",), 10**63, "hmac-int"),
    schema(("hmac_key",), "0" * 63, "hmac-63"),
    schema(("hmac_key",), "0" * 65, "hmac-65"),
    schema(("hmac_key",), "F" * 64, "hmac-upper"),
    schema(("raw_canaries",), [], "canaries-empty"),
    schema(("raw_canaries",), ["c"] * 17, "canaries-17"),
    schema(("raw_canaries",), [""], "canary-empty"),
    schema(("raw_canaries",), ["c" * 129], "canary-129"),
    schema(("raw_canaries",), ["a\nb"], "canary-lf"),
    schema(("raw_canaries",), ["a\x7fb"], "canary-del"),
    schema(("raw_canaries",), ["caf" + E_ACUTE], "canary-non-ascii"),
    schema(("raw_canaries",), [SURROGATE], "canary-surrogate"),
    schema(("raw_canaries",), [5], "canary-int"),
    schema(("raw_canaries",), "canary", "canaries-str"),
    schema(("expected",), RECORDS[:18], "expected-18"),
    schema(("expected",), [*RECORDS, RECORDS[0]], "expected-20"),
    schema(("expected",), [RECORDS[1], RECORDS[0], *RECORDS[2:]], "expected-order"),
    schema(("expected", 0, "job"), True, "job-bool"),
    schema(("expected", 0, "job"), "1", "job-str"),
    schema(("expected", 0, "job"), MISSING, "job-missing"),
    schema(("expected", 0, "extra"), 1, "record-extra"),
    schema(("expected", 0), list(RECORDS[0].values()), "record-list"),
    schema(("expected", 0), "RESULT", "record-str"),
    schema(("expected", 0, "job"), 1.0, "job-float"),
    schema(("expected", 0, "rows"), 3.0, "rows-float"),
    schema(("expected", 0, "bytes"), True, "bytes-bool"),
    schema(("expected", 0, "kind"), "ERROR", "result-job-as-error"),
    schema(("expected", 0, "kind"), "PASS", "kind-unknown"),
    schema(("expected", 0, "reason"), "QUERY", "result-with-reason"),
    schema(("expected", 0, "rows"), 1001, "rows-1001"),
    schema(("expected", 0, "rows"), -1, "rows-negative"),
    schema(("expected", 0, "rows"), True, "rows-bool"),
    schema(("expected", 0, "rows"), None, "result-rows-null"),
    schema(("expected", 0, "bytes"), 0, "bytes-0"),
    schema(("expected", 0, "bytes"), FRAME_LIMIT + 1, "bytes-over-frame"),
    schema(("expected", 0, "bytes"), 1.5, "bytes-float"),
    schema(("expected", 0, "sha256"), "A" * 64, "sha-upper"),
    schema(("expected", 0, "sha256"), "a" * 63, "sha-63"),
    schema(("expected", 0, "sha256"), None, "result-sha-null"),
    schema(("expected", 10, "kind"), "RESULT", "limit-job-as-result"),
    schema(("expected", 10, "reason"), "QUERY", "limit-wrong-reason"),
    schema(("expected", 15, "reason"), "QUERY", "timeout-wrong-reason"),
    schema(("expected", 17, "reason"), "LIMIT", "type-wrong-reason"),
    schema(("expected", 12, "reason"), None, "error-without-reason"),
    schema(("expected", 10, "rows"), 0, "error-with-rows"),
    schema(("expected", 13, "bytes"), 1, "error-with-bytes"),
    schema(("expected", 14, "sha256"), "a" * 64, "error-with-sha"),
]


@pytest.mark.parametrize(("path", "value"), SCHEMA_REFUSALS)
def test_decode_init_refuses_schema(path: tuple[str | int, ...], value: object) -> None:
    m = lab()
    with pytest.raises(m["LabRefusal"]) as info:
        m["decode_init"](mutated(path, value))
    assert_refusal(info, "INIT")


def observed(init: Any, path: tuple[str | int, ...]) -> object:
    if path[0] == "target":
        return getattr(init.target, str(path[1]))
    if path[0] == "expected":
        return getattr(init.expected[int(path[1])], str(path[2]))
    return list(init.raw_canaries)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        schema(("target", "port"), 1, "port-1"),
        schema(("target", "port"), 65535, "port-65535"),
        schema(("target", "database"), "d" * 63, "database-63"),
        schema(("target", "username"), "u_" * 31 + "u", "username-63"),
        schema(("target", "ip"), "172.31.255.254", "ip-172"),
        schema(("target", "ip"), "192.168.0.1", "ip-192"),
        schema(("expected", 0, "rows"), 0, "rows-0"),
        schema(("expected", 0, "rows"), 1000, "rows-1000"),
        schema(("expected", 0, "bytes"), 1, "bytes-1"),
        schema(("expected", 0, "bytes"), FRAME_LIMIT, "bytes-frame-limit"),
        schema(("raw_canaries",), ["c" * 128] * 16, "canaries-16x128"),
    ],
)
def test_decode_init_accepts_boundaries(path: tuple[str | int, ...], value: object) -> None:
    init = lab()["decode_init"](mutated(path, value))
    assert observed(init, path) == value


def test_large_valid_near_bound_sample_is_accepted_below_cap() -> None:
    """Large valid sample near the closed field limits, NOT a proved exact maximum.

    16 canaries of 128 chars that each escape to 2 bytes (quote/backslash), 19
    records with 8-digit bytes and 64-hex digests, and 63-char names. The sample
    does not maximize IPv4 or port widths. The closed field limits imply any
    valid body stays under 8 KiB, so the 65536 cap is not reachable through the
    schema; its reachable negative is ``body-over-cap`` above (no huge alloc)."""
    body = valid_body()
    worst = '"\\' * 64
    body["raw_canaries"] = [worst] * 16
    body["target"]["database"] = "d" * 63
    body["target"]["username"] = "u" * 63
    for record in body["expected"]:
        if record["kind"] == "RESULT":
            record["rows"] = 1000
            record["bytes"] = FRAME_LIMIT
    raw = canonical(body)
    assert len(raw) < MAX_BODY // 8
    init = lab()["decode_init"](packet(raw))
    assert init.raw_canaries == (worst,) * 16


# ---------------------------------------------------------------- LAB_CONTROL


def test_decode_control_golden_vector_and_kinds() -> None:
    m = lab()
    assert (m["GO"], m["STOP"], m["NOSTOP"], m["ACK"]) == (GO, STOP, NOSTOP, ACK)
    raw = bytes.fromhex("4d474c31 01 02 0017 0000002e 00000000")
    control = m["decode_control"](raw)
    assert (control.kind, control.case, control.seq) == (STOP, T4, 46)


@pytest.mark.parametrize(
    ("kind", "case", "seq"),
    [(GO, 1, 1), (ACK, 25, 50), (NOSTOP, 23, 46), (STOP, 1, 50)],
    ids=["go-min", "ack-max", "nostop", "stop-shape"],
)
def test_decode_control_accepts_bounds(kind: int, case: int, seq: int) -> None:
    control = lab()["decode_control"](frame(kind, case, seq))
    assert (control.kind, control.case, control.seq) == (kind, case, seq)


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(frame(GO, 1, 1)[:15], id="short"),
        pytest.param(frame(GO, 1, 1) + b"\x00", id="long"),
        pytest.param(bytearray(frame(GO, 1, 1)), id="bytearray"),
        pytest.param(memoryview(frame(GO, 1, 1)), id="memoryview"),
        pytest.param(BytesSubclass(frame(GO, 1, 1)), id="bytes-subclass"),
        pytest.param(CONTROL.pack(b"MGL2", 1, GO, 1, 1, 0), id="magic"),
        pytest.param(CONTROL.pack(b"MGL1", 0, GO, 1, 1, 0), id="version-0"),
        pytest.param(CONTROL.pack(b"MGL1", 2, GO, 1, 1, 0), id="version-2"),
        pytest.param(CONTROL.pack(b"MGL1", 1, 0, 1, 1, 0), id="kind-0"),
        pytest.param(CONTROL.pack(b"MGL1", 1, 5, 1, 1, 0), id="kind-5"),
        pytest.param(CONTROL.pack(b"MGL1", 1, GO, 0, 1, 0), id="case-0"),
        pytest.param(CONTROL.pack(b"MGL1", 1, GO, 26, 1, 0), id="case-26"),
        pytest.param(CONTROL.pack(b"MGL1", 1, GO, 1, 0, 0), id="seq-0"),
        pytest.param(CONTROL.pack(b"MGL1", 1, GO, 1, 51, 0), id="seq-51"),
        pytest.param(CONTROL.pack(b"MGL1", 1, GO, 1, 1, 1), id="reserved-1"),
        pytest.param(CONTROL.pack(b"MGL1", 1, GO, 1, 1, 1 << 31), id="reserved-high"),
    ],
)
def test_decode_control_refuses(raw: object) -> None:
    m = lab()
    with pytest.raises(m["LabRefusal"]) as info:
        m["decode_control"](raw)
    assert_refusal(info, "CONTROL")


# ---------------------------------------------------------------- transitions


def run(machine: Any, steps: list[Step], seq: int = 1, *, check: bool = True) -> int:
    """Drive the pure machine; the test keeps its own independent seq counter."""
    for action, kind, case in steps:
        if action in ("READY", "RESULT", "ARMED"):
            assert machine.emit(action, case) == seq
        elif action == "accept":
            if check:
                assert machine.reader == "MAIN"
            control = machine.accept(frame(kind, case, seq))
            assert (control.kind, control.case, control.seq) == (kind, case, seq)
            seq += 1
        elif action == "handoff":
            assert machine.handoff() == seq
            if check:
                assert machine.reader == "WATCHER"
                assert machine.next_seq == seq  # no advance before join
        elif action == "join":
            before = machine.accepted
            control = machine.join(frame(kind, case, seq))
            assert (control.kind, control.case, control.seq) == (kind, case, seq)
            assert machine.accepted == before + 1
            if check:
                assert machine.reader == "MAIN"
            seq += 1
        else:
            summary = machine.summary()
            assert summary.global_pass is False
            assert summary.prefix_cases == 24
    return seq


@pytest.mark.parametrize("t4", [STOP, NOSTOP], ids=["stop", "nostop"])
def test_complete_walk_fifty_frames_without_threads(forbidden: list[str], t4: int) -> None:
    machine = lab()["ControlMachine"]()
    assert (machine.next_seq, machine.accepted, machine.reader) == (1, 0, "MAIN")
    assert run(machine, script(t4)) == 51
    assert (machine.next_seq, machine.accepted, machine.aborted) == (51, 50, False)
    assert forbidden == []


@pytest.mark.parametrize(("t4", "failed"), [(STOP, ()), (NOSTOP, (T4,))], ids=["stop", "nostop"])
def test_summary_is_prefix_only_and_nostop_is_failed(t4: int, failed: tuple[int, ...]) -> None:
    machine = lab()["ControlMachine"]()
    steps = script(t4)
    seq = run(machine, steps[: steps.index(("summary", 0, 0))])
    summary = machine.summary()
    assert summary.failed_cases == failed
    assert summary.prefix_cases == 24
    assert summary.global_pass is False
    assert machine.emit("READY", T6) == seq


ACTIONS: dict[str, Callable[[Any, int, int, int], object]] = {
    "accept": lambda x, k, c, s: x.accept(frame(k, c, s)),
    "accept-short": lambda x, k, c, s: x.accept(frame(k, c, s)[:15]),
    "accept-bytearray": lambda x, k, c, s: x.accept(bytearray(frame(k, c, s))),
    "accept-subclass": lambda x, k, c, s: x.accept(BytesSubclass(frame(k, c, s))),
    "join": lambda x, k, c, s: x.join(frame(k, c, s)),
    "join-short": lambda x, k, c, s: x.join(frame(k, c, s)[:-1]),
    "join-none": lambda x, _k, _c, _s: x.join(None),
    "handoff": lambda x, _k, _c, _s: x.handoff(),
    "summary": lambda x, _k, _c, _s: x.summary(),
    "eof": lambda x, _k, _c, _s: x.eof(),
    "READY": lambda x, _k, c, _s: x.emit("READY", c),
    "RESULT": lambda x, _k, c, _s: x.emit("RESULT", c),
    "ARMED": lambda x, _k, c, _s: x.emit("ARMED", c),
    "DONE": lambda x, _k, c, _s: x.emit("DONE", c),
    "bool-case": lambda x, _k, _c, _s: x.emit("READY", True),
}

TRANSITION_REFUSALS = [
    pytest.param(("accept", GO, 1), ("accept", GO, 2, 0), "PHASE", id="go-wrong-case"),
    pytest.param(("accept", GO, 1), ("accept", ACK, 1, 0), "PHASE", id="ack-for-go"),
    pytest.param(("accept", ACK, 1), ("accept", ACK, 1, -1), "PHASE", id="replay"),
    pytest.param(("accept", ACK, 1), ("accept", ACK, 1, 1), "PHASE", id="skip-seq"),
    pytest.param(("accept", GO, 5), ("accept", STOP, 5, 0), "PHASE", id="stop-outside-t4"),
    pytest.param(("accept", GO, T4), ("accept", NOSTOP, T4, 0), "PHASE", id="nostop-for-go"),
    pytest.param(("join", STOP, T4), ("accept", STOP, T4, 0), "PHASE", id="main-in-watch"),
    pytest.param(("handoff", 0, T4), ("join", STOP, T4, 0), "PHASE", id="join-no-handoff"),
    pytest.param(("ARMED", 0, T4), ("handoff", 0, 0, 0), "PHASE", id="handoff-no-armed"),
    pytest.param(("RESULT", 0, 1), ("ARMED", 0, 1, 0), "PHASE", id="armed-wrong-case"),
    pytest.param(("accept", GO, 1), ("RESULT", 0, 1, 0), "PHASE", id="result-before-go"),
    pytest.param(("READY", 0, 1), ("READY", 0, 2, 0), "PHASE", id="ready-out-of-order"),
    pytest.param(("READY", 0, 1), ("summary", 0, 0, 0), "PHASE", id="summary-early"),
    pytest.param(("summary", 0, 0), ("READY", 0, T6, 0), "PHASE", id="t6-before-summary"),
    pytest.param(("READY", 0, T6), ("summary", 0, 0, 0), "PHASE", id="second-summary"),
    pytest.param(None, ("accept", ACK, T6, -1), "PHASE", id="frame-after-t6-armed"),
    pytest.param(None, ("eof", 0, 0, 0), "PHASE", id="eof-after-t6-armed"),
    pytest.param(("join", STOP, T4), ("join-none", 0, 0, 0), "PHASE", id="join-failed"),
    pytest.param(("join", STOP, T4), ("join", GO, T4, 0), "PHASE", id="join-go"),
    pytest.param(("join", STOP, T4), ("join", ACK, T4, 0), "PHASE", id="join-ack"),
    pytest.param(("join", STOP, T4), ("join", STOP, 22, 0), "PHASE", id="join-wrong-case"),
    pytest.param(("join", STOP, T4), ("join", STOP, T4, 1), "PHASE", id="join-wrong-seq"),
    pytest.param(("join", STOP, T4), ("join-short", STOP, T4, 0), "CONTROL", id="join-short"),
    pytest.param(("accept", GO, 1), ("eof", 0, 0, 0), "PHASE", id="eof-start"),
    pytest.param(("summary", 0, 0), ("eof", 0, 0, 0), "PHASE", id="eof-before-summary"),
    pytest.param(("accept", GO, 1), ("accept-short", GO, 1, 0), "CONTROL", id="short"),
    pytest.param(("accept", GO, 1), ("accept-bytearray", GO, 1, 0), "CONTROL", id="bytearray"),
    pytest.param(("READY", 0, 1), ("DONE", 0, 1, 0), "PHASE", id="unknown-event"),
    pytest.param(("READY", 0, 1), ("bool-case", 0, 0, 0), "PHASE", id="bool-case"),
    pytest.param(("accept", GO, 1), ("accept-subclass", GO, 1, 0), "CONTROL", id="subclass"),
    pytest.param(("accept", GO, 1), ("READY", 0, 1, 0), "PHASE", id="ready-repeated"),
    pytest.param(("handoff", 0, T4), ("RESULT", 0, T4, 0), "PHASE", id="result-before-handoff"),
    pytest.param(("join", STOP, T4), ("RESULT", 0, T4, 0), "PHASE", id="result-in-watch"),
    pytest.param(("ARMED", 0, T6), ("accept", ACK, T6, -1), "PHASE", id="frame-before-t6-armed"),
    pytest.param(("ARMED", 0, T6), ("accept", GO, T6, 0), "CONTROL", id="seq51-before-armed"),
]


@pytest.mark.parametrize(("marker", "bad", "category"), TRANSITION_REFUSALS)
def test_transition_refusal_is_sticky_and_never_advances(
    marker: Step | None, bad: tuple[str, int, int, int], category: str
) -> None:
    m = lab()
    machine = m["ControlMachine"]()
    steps = script(STOP)
    position = len(steps) if marker is None else steps.index(marker)
    seq = run(machine, steps[:position])
    before = (machine.accepted, machine.next_seq)
    verb, kind, case, delta = bad
    with pytest.raises(m["LabRefusal"]) as info:
        ACTIONS[verb](machine, kind, case, seq + delta)
    assert_refusal(info, category)
    assert machine.aborted is True
    assert (machine.accepted, machine.next_seq) == before
    with pytest.raises(m["LabRefusal"]) as again:
        if position < len(steps):
            run(machine, steps[position : position + 1], seq, check=False)
        else:
            machine.summary()
    assert_refusal(again, "PHASE")


# ---------------------------------------------------------------- SQL table


@pytest.mark.parametrize("job", range(1, 20))
def test_job_sql_is_exact_fixed_table(job: int) -> None:
    m = lab()
    assert m["job_sql"](job, CANARIES[0]) == expected_sql(job)
    assert m["HEAVY_SQL"] == HEAVY == SQL[16]
    assert m["TABLE"] == TABLE


@pytest.mark.parametrize(
    "canary",
    ["x'; DELETE FROM maskgw_lab.t; --", "a\\b", "'", "''--", "$$x$$", '"\\' * 64],
    ids=["quote-injection", "backslash", "lone-quote", "doubled-quote", "dollar", "worst-128"],
)
def test_canary_cannot_alter_fixed_sql_syntax(canary: str) -> None:
    m = lab()
    sql = m["job_sql"](13, canary)
    assert sql == expected_sql(13, canary)
    validate_select(sql)  # one SelectStmt under the default policy
    assert m["job_sql"](14, canary) == SQL[14]


@pytest.mark.parametrize(
    ("job", "canary"),
    [
        (0, CANARIES[0]),
        (20, CANARIES[0]),
        (True, CANARIES[0]),
        ("1", CANARIES[0]),
        (13, ""),
        (13, "a\nb"),
        (13, "caf" + E_ACUTE),
        (13, "c" * 129),
        (1, 5),
    ],
    ids=["job-0", "job-20", "job-bool", "job-str", "empty", "lf", "non-ascii", "129", "int"],
)
def test_job_sql_refuses_inputs_outside_table(job: object, canary: object) -> None:
    m = lab()
    with pytest.raises(m["LabRefusal"]) as info:
        m["job_sql"](job, canary)
    assert_refusal(info, "SQL")


# ---------------------------------------------------------------- literal resolver


def test_pinned_literal_address_uses_no_dns_or_child(forbidden: list[str]) -> None:
    m = lab()
    assert m["pinned_addresses"](IP, PORT) == (IP,)
    exact = m["exact_resolver"](IP, PORT)
    assert tuple(exact(IP, PORT)) == (IP,)
    assert forbidden == []


@pytest.mark.parametrize(
    ("host", "port"),
    [
        ("10.0.0.8", PORT),
        (IP, 5433),
    ],
    ids=["foreign-host", "foreign-port"],
)
def test_exact_resolver_only_pinned_pair(forbidden: list[str], host: str, port: int) -> None:
    m = lab()
    with pytest.raises(m["LabRefusal"]) as info:
        m["exact_resolver"](IP, PORT)(host, port)
    assert_refusal(info, "DESTINATION")
    assert forbidden == []


@pytest.mark.parametrize(
    ("host", "port"),
    [
        ("127.0.0.1", PORT),
        ("8.8.8.8", PORT),
        ("db.internal.example", PORT),
        ("010.0.0.7", PORT),
        (IP, 0),
        (IP, True),
        (IP, 5432.0),
    ],
    ids=["loopback", "public", "hostname", "noncanonical", "port-0", "port-bool", "port-float"],
)
def test_exact_resolver_factory_validates_pinned_pair(
    forbidden: list[str], host: object, port: object
) -> None:
    m = lab()
    with pytest.raises(m["LabRefusal"]) as info:
        m["exact_resolver"](host, port)
    assert_refusal(info, "DESTINATION")
    assert forbidden == []


@pytest.mark.parametrize("port", [True, 1.0], ids=["bool", "float"])
def test_exact_resolver_refuses_numeric_equal_port_coercion(
    forbidden: list[str], port: object
) -> None:
    m = lab()
    exact = m["exact_resolver"](IP, 1)
    assert tuple(exact(IP, 1)) == (IP,)
    with pytest.raises(m["LabRefusal"]) as info:
        exact(IP, port)
    assert_refusal(info, "DESTINATION")
    assert forbidden == []


@pytest.mark.parametrize(
    ("host", "port"),
    [
        ("127.0.0.1", PORT),
        ("169.254.169.254", PORT),
        ("8.8.8.8", PORT),
        (UNSPECIFIED, PORT),
        ("db.internal.example", PORT),
        ("fd00::1", PORT),
        ("010.0.0.7", PORT),
        (IP, 0),
        (IP, 65536),
        (IP, True),
    ],
    ids=[
        "loopback",
        "metadata",
        "public",
        "unspecified",
        "hostname",
        "ipv6",
        "noncanonical",
        "port-0",
        "port-65536",
        "port-bool",
    ],
)
def test_pinned_addresses_refuse_before_dns(
    forbidden: list[str], host: object, port: object
) -> None:
    m = lab()
    with pytest.raises(m["LabRefusal"]) as info:
        m["pinned_addresses"](host, port)
    assert_refusal(info, "DESTINATION")
    assert forbidden == []


# ---------------------------------------------------------------- capture


def lab_policy(timeout_ms: int) -> DatasourcePolicy:
    """Same masking as tests/test_db_typed_integration.CONFIG, explicit database."""
    return DatasourcePolicy.from_mapping(
        {
            "database": {"statement_timeout_ms": timeout_ms, "max_rows": 1000},
            "masking": LAB_MASKING,
            "exceptions": [{"match": "tipo_cpf", "mode": "exact"}],
        }
    )


def lab_limits(generation: int) -> DatasourceLimits:
    return DatasourceLimits(statement_timeout_ms=TIMEOUTS[generation], max_rows=1000)


@pytest.mark.parametrize("generation", [1, 2], ids=["g1", "g2"])
def test_capture_matches_oracle_per_generation(forbidden: list[str], generation: int) -> None:
    m = lab()
    assert m["DATASOURCE_ID"] == DATASOURCE_ID
    assert m["RECORD_REVISION"] == 1
    init = m["decode_init"](packet(VALID))
    ident = SnapshotIdentity(DATASOURCE_ID, generation, 1)
    policy, limits = lab_policy(TIMEOUTS[generation]), lab_limits(generation)
    data = m["capture"](init, generation)
    assert data == oracle(policy, limits, ident)
    assert json.loads(data)["runtime"]["secrets"] == {HMAC_KEY_ENV: HMAC_KEY}
    rebuilt = recompile_snapshot(data, expected=ident)
    assert rebuilt.connection_target() == build_conninfo(spec(policy, limits), (IP,))
    assert rebuilt.config.database.statement_timeout_ms == TIMEOUTS[generation]
    assert rebuilt.config.database.max_rows == 1000
    assert rebuilt.engine.decide(ColumnDescriptor("cpf")).action is Action.MASK
    assert rebuilt.engine.decide(ColumnDescriptor("tipo_cpf")).action is Action.EXCEPTION
    assert forbidden == []


def test_capture_generations_are_isolated() -> None:
    m = lab()
    init = m["decode_init"](packet(VALID))
    first, second = m["capture"](init, 1), m["capture"](init, 2)
    assert first != second
    with pytest.raises(ValueError):
        recompile_snapshot(first, expected=SnapshotIdentity(DATASOURCE_ID, 2, 1))


@pytest.mark.parametrize("generation", [0, 3, True], ids=["zero", "three", "bool"])
def test_capture_refuses_unknown_generation(forbidden: list[str], generation: object) -> None:
    m = lab()
    init = m["decode_init"](packet(VALID))
    with pytest.raises(m["LabRefusal"]) as info:
        m["capture"](init, generation)
    assert_refusal(info, "CAPTURE")
    assert forbidden == []
