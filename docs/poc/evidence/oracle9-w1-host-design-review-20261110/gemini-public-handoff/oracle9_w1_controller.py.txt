"""Pure W1 Oracle laboratory controller prefix. Definitions only, no effect on import.

Laboratory wire LAB_INIT/LAB_CONTROL (W1-ORACLE-NATIVE-PLAN v4 + PLAN-REVIEW),
not the product MGW2 protocol or the old state16 schema. No entry point, I/O,
socket, thread, process, Docker, PostgreSQL or SQL execution lives here: the
future driver owns those effects under its own review.

Every refusal is a closed ``LabRefusal(category)`` raised outside any exception
handler, so it carries no input value, cause or context. Secrets reach this
module only inside the decoded LAB_INIT value; the environment is never read.
The snapshot uses the public compilation composition only, with the supplied
HMAC hexadecimal TEXT as the key (never hex-decoded), and no candidate,
verifier, adapter or connection path.
"""

from __future__ import annotations

import ipaddress
import json
import re
import struct
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, NoReturn

from maskgw.config.gateway import GatewayConfig, parse_config_bundle
from maskgw.datasource.destination import resolve_destination
from maskgw.datasource.models import (
    DatasourceLimits,
    DatasourcePolicy,
    DestinationPolicy,
    TlsSettings,
)
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.runtime.candidate import CandidateSpec, build_conninfo, effective_database_settings
from maskgw.runtime.snapshot import RecordingSecrets, SnapshotIdentity, capture_template
from maskgw.secretsource import MappingSecretProvider

GO: Final = 1
STOP: Final = 2
NOSTOP: Final = 3
ACK: Final = 4

INIT_KIND: Final = "MASKGW_W1_LAB_INIT_V1"
INIT_VERSION: Final = 1
MAX_INIT_BODY: Final = 65536
FRAME_LIMIT: Final = 16 * 1024 * 1024
MAX_ROWS: Final = 1000
JOBS: Final = 19
CASES: Final = 25
MAX_HOST_FRAMES: Final = 50
T4_CASE: Final = 23
T5_CASE: Final = 24
T6_CASE: Final = 25
PREFIX_CASES: Final = 24

TABLE: Final = "maskgw_lab.t"
HEAVY_SQL: Final = (
    "SELECT count(*) FROM generate_series(1,100000) AS a CROSS JOIN generate_series(1,100000) AS b"
)
DATASOURCE_ID: Final = "dso_" + "0" * 31 + "1"
RECORD_REVISION: Final = 1

_INIT_HEADER: Final = struct.Struct(">4sI")
_CONTROL: Final = struct.Struct(">4sBBHII")
_INIT_MAGIC: Final = b"MGI1"
_CONTROL_MAGIC: Final = b"MGL1"
_CONTROL_VERSION: Final = 1
_MAX_PORT: Final = 65535
_MAX_CANARIES: Final = 16
_MAX_CANARY: Final = 128
_NAME: Final = r"[a-z][a-z0-9_]{0,62}"
_PASSWORD: Final = r"[0-9a-f]{48}"
_HEX64: Final = r"[0-9a-f]{64}"
_CAST_JOB: Final = 13
_INIT_KEYS: Final = frozenset(
    {"kind", "version", "target", "readonly_password", "hmac_key", "raw_canaries", "expected"}
)
_TARGET_KEYS: Final = frozenset({"ip", "port", "database", "username"})
_RECORD_KEYS: Final = frozenset({"job", "kind", "rows", "bytes", "sha256", "reason"})
_ERRORS: Final = {11: "LIMIT", 13: "QUERY", 14: "QUERY", 15: "QUERY", 16: "TIMEOUT", 18: "TYPE"}
_TIMEOUTS: Final = {1: 1000, 2: 30000}
_SQL: Final = {
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
    16: HEAVY_SQL,
    17: "SELECT 2",
    18: "SELECT amount FROM maskgw_lab.t WHERE id=1",
    19: "SELECT 3",
}

_INIT: Final = "INIT"
_CONTROL_CATEGORY: Final = "CONTROL"
_PHASE: Final = "PHASE"
_SQL_CATEGORY: Final = "SQL"
_CAPTURE: Final = "CAPTURE"
_DESTINATION: Final = "DESTINATION"
REFUSAL_CATEGORIES: Final = frozenset(
    {_INIT, _CONTROL_CATEGORY, _PHASE, _SQL_CATEGORY, _CAPTURE, _DESTINATION}
)


class LabRefusal(Exception):
    """Closed category only; never input values, original exceptions or chains."""

    def __init__(self, category: str) -> None:
        super().__init__(category)
        self.category = category


class _InvalidError(Exception):
    """Private parse signal; always converted to a closed refusal outside handlers."""


@dataclass(frozen=True, slots=True)
class Target:
    ip: str
    port: int
    database: str
    username: str


@dataclass(frozen=True, slots=True, repr=False)
class ExpectedJob:
    job: int
    kind: str
    rows: int | None
    bytes: int | None
    sha256: str | None
    reason: str | None

    def __repr__(self) -> str:
        return "ExpectedJob(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False, eq=False)
class LabInit:
    """Secret-bearing detached value; no zeroization of Python memory is promised."""

    target: Target
    readonly_password: str
    hmac_key: str
    raw_canaries: tuple[str, ...]
    expected: tuple[ExpectedJob, ...]

    def __repr__(self) -> str:
        return "LabInit(<redacted>)"


@dataclass(frozen=True, slots=True)
class Control:
    kind: int
    case: int
    seq: int


@dataclass(frozen=True, slots=True)
class Summary:
    """Prefix summary before T6; never a global PASS."""

    prefix_cases: int
    failed_cases: tuple[int, ...]
    global_pass: bool


# ---------------------------------------------------------------- closed scalars


def _int_or_none(value: object, low: int, high: int) -> int | None:
    if not isinstance(value, int) or type(value) is not int or not low <= value <= high:
        return None
    return value


def _ipv4_or_none(value: object) -> str | None:
    """Canonical private IPv4 literal; loopback/link-local/special refused."""
    if not isinstance(value, str) or type(value) is not str:
        return None
    try:
        address = ipaddress.IPv4Address(value)
    except ValueError:
        return None
    special = (
        address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
    )
    if str(address) != value or not address.is_private or special:
        return None
    return value


def _canary_or_none(value: object) -> str | None:
    """ASCII printable data only (no controls), 1..128 characters."""
    if not isinstance(value, str) or type(value) is not str:
        return None
    if not 1 <= len(value) <= _MAX_CANARY or not all(" " <= char <= "~" for char in value):
        return None
    return value


def _number(value: object, low: int, high: int) -> int:
    result = _int_or_none(value, low, high)
    if result is None:
        raise _InvalidError
    return result


def _text(value: object, pattern: str) -> str:
    if not isinstance(value, str) or type(value) is not str:
        raise _InvalidError
    if re.fullmatch(pattern, value) is None:
        raise _InvalidError
    return value


def _mapping(value: object, keys: frozenset[str]) -> dict[str, object]:
    if not isinstance(value, dict) or type(value) is not dict or set(value) != keys:
        raise _InvalidError
    return value


# ---------------------------------------------------------------- LAB_INIT


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _InvalidError
        result[key] = value
    return result


def _nonfinite(_text_value: str) -> NoReturn:
    raise _InvalidError


def _canonical_body(packet: object) -> dict[str, object]:
    if not isinstance(packet, bytes) or type(packet) is not bytes:
        raise _InvalidError
    if len(packet) < _INIT_HEADER.size:
        raise _InvalidError
    magic, size = _INIT_HEADER.unpack_from(packet)
    if magic != _INIT_MAGIC or not 1 <= size <= MAX_INIT_BODY:
        raise _InvalidError
    if len(packet) != _INIT_HEADER.size + size:
        raise _InvalidError
    body = packet[_INIT_HEADER.size :]
    value = json.loads(body.decode("ascii"), object_pairs_hook=_pairs, parse_constant=_nonfinite)
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")
    if canonical != body:
        raise _InvalidError
    return _mapping(value, _INIT_KEYS)


def _target(value: object) -> Target:
    raw = _mapping(value, _TARGET_KEYS)
    ip = _ipv4_or_none(raw["ip"])
    if ip is None:
        raise _InvalidError
    return Target(
        ip=ip,
        port=_number(raw["port"], 1, _MAX_PORT),
        database=_text(raw["database"], _NAME),
        username=_text(raw["username"], _NAME),
    )


def _canaries(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or type(value) is not list:
        raise _InvalidError
    if not 1 <= len(value) <= _MAX_CANARIES:
        raise _InvalidError
    result: list[str] = []
    for item in value:
        canary = _canary_or_none(item)
        if canary is None:
            raise _InvalidError
        result.append(canary)
    return tuple(result)


def _record(index: int, value: object) -> ExpectedJob:
    raw = _mapping(value, _RECORD_KEYS)
    job = _number(raw["job"], index + 1, index + 1)
    reason = _ERRORS.get(job)
    if reason is None:
        if raw["kind"] != "RESULT" or raw["reason"] is not None:
            raise _InvalidError
        return ExpectedJob(
            job=job,
            kind="RESULT",
            rows=_number(raw["rows"], 0, MAX_ROWS),
            bytes=_number(raw["bytes"], 1, FRAME_LIMIT),
            sha256=_text(raw["sha256"], _HEX64),
            reason=None,
        )
    fields = (raw["kind"], raw["rows"], raw["bytes"], raw["sha256"], raw["reason"])
    if fields != ("ERROR", None, None, None, reason) or type(raw["reason"]) is not str:
        raise _InvalidError
    return ExpectedJob(job=job, kind="ERROR", rows=None, bytes=None, sha256=None, reason=reason)


def _expected(value: object) -> tuple[ExpectedJob, ...]:
    if not isinstance(value, list) or type(value) is not list or len(value) != JOBS:
        raise _InvalidError
    return tuple(_record(index, item) for index, item in enumerate(value))


def _init_from(packet: object) -> LabInit:
    body = _canonical_body(packet)
    kind, version = body["kind"], body["version"]
    if type(kind) is not str or kind != INIT_KIND:
        raise _InvalidError
    _number(version, INIT_VERSION, INIT_VERSION)
    return LabInit(
        target=_target(body["target"]),
        readonly_password=_text(body["readonly_password"], _PASSWORD),
        hmac_key=_text(body["hmac_key"], _HEX64),
        raw_canaries=_canaries(body["raw_canaries"]),
        expected=_expected(body["expected"]),
    )


def _init_or_none(packet: object) -> LabInit | None:
    try:
        return _init_from(packet)
    except Exception:  # every parse/schema failure becomes one closed category below
        return None


def decode_init(packet: object) -> LabInit:
    """Exact ``bytes``: ``>4sI`` MGI1 header, body 1..65536, canonical ASCII JSON."""
    result = _init_or_none(packet)
    if result is None:
        raise LabRefusal(_INIT)
    return result


# ---------------------------------------------------------------- LAB_CONTROL


def _control_or_none(frame: object) -> Control | None:
    if not isinstance(frame, bytes) or type(frame) is not bytes or len(frame) != _CONTROL.size:
        return None
    magic, version, kind, case, seq, reserved = _CONTROL.unpack(frame)
    valid = (
        magic == _CONTROL_MAGIC
        and version == _CONTROL_VERSION
        and GO <= kind <= ACK
        and 1 <= case <= CASES
        and 1 <= seq <= MAX_HOST_FRAMES
        and reserved == 0
    )
    return Control(kind=kind, case=case, seq=seq) if valid else None


def decode_control(frame: object) -> Control:
    """Exact 16 ``bytes`` ``>4sBBHII``: MGL1, version 1, kind, case, seq, reserved 0."""
    control = _control_or_none(frame)
    if control is None:
        raise LabRefusal(_CONTROL_CATEGORY)
    return control


# ---------------------------------------------------------------- transitions

_MAIN_READER: Final = "MAIN"
_WATCHER_READER: Final = "WATCHER"
_READY_DUE: Final = "READY_DUE"
_GO_DUE: Final = "GO_DUE"
_RUNNING: Final = "RUNNING"
_ARMED: Final = "ARMED"
_WATCH: Final = "WATCH"
_JOINED: Final = "JOINED"
_ACK_DUE: Final = "ACK_DUE"
_SUMMARY_DUE: Final = "SUMMARY_DUE"
_TERMINAL: Final = "TERMINAL"
_DUE_KIND: Final = {_GO_DUE: GO, _ACK_DUE: ACK}
_ARMED_CASES: Final = frozenset({T4_CASE, T6_CASE})


class ControlMachine:
    """Pure host-control order: 24 cases, T4 watcher window, SUMMARY, T6 GO.

    Only the main owner accepts frames; during T4 the watcher reads exactly one
    frame that the main commits through ``join`` after joining the watcher, so
    no counter is shared or advanced concurrently. Any refusal is sticky, never
    advances counters and never reopens the state. No thread is created here.
    """

    def __init__(self) -> None:
        self._case = 1
        self._phase = _READY_DUE
        self._reader = _MAIN_READER
        self._accepted = 0
        self._aborted = False
        self._failed: tuple[int, ...] = ()

    @property
    def next_seq(self) -> int:
        return self._accepted + 1

    @property
    def accepted(self) -> int:
        return self._accepted

    @property
    def reader(self) -> str:
        return self._reader

    @property
    def aborted(self) -> bool:
        return self._aborted

    def _refuse(self, category: str) -> NoReturn:
        self._aborted = True
        raise LabRefusal(category)

    def _usable(self) -> None:
        if self._aborted:
            raise LabRefusal(_PHASE)

    def emit(self, event: object, case: object) -> int:
        """Controller event READY/RESULT/ARMED; returns the next expected seq."""
        self._usable()
        if type(event) is not str or not isinstance(case, int) or type(case) is not int:
            self._refuse(_PHASE)
        current, own = self._phase, case == self._case
        if event == "READY" and current == _READY_DUE and own:
            self._phase = _GO_DUE
        elif event == "RESULT" and own and current == _RUNNING and case not in _ARMED_CASES:
            self._phase = _ACK_DUE
        elif event == "RESULT" and own and current == _JOINED:
            self._phase = _ACK_DUE
        elif event == "ARMED" and own and current == _RUNNING and case in _ARMED_CASES:
            self._phase = _ARMED if case == T4_CASE else _TERMINAL
        else:
            self._refuse(_PHASE)
        return self.next_seq

    def accept(self, frame: object) -> Control:
        """Main reader only: GO after READY or ACK after RESULT, exact case/seq."""
        self._usable()
        if self._reader != _MAIN_READER:
            self._refuse(_PHASE)
        control = _control_or_none(frame)
        if control is None:
            self._refuse(_CONTROL_CATEGORY)
        due = _DUE_KIND.get(self._phase)
        expected = (due, self._case, self.next_seq)
        if due is None or (control.kind, control.case, control.seq) != expected:
            self._refuse(_PHASE)
        self._accepted += 1
        if self._phase == _GO_DUE:
            self._phase = _RUNNING
        elif self._case == T5_CASE:
            self._phase = _SUMMARY_DUE
        else:
            self._case += 1
            self._phase = _READY_DUE
        return control

    def handoff(self) -> int:
        """After ARMED{T4}: the watcher becomes the only reader of one frame."""
        self._usable()
        if self._phase != _ARMED or self._reader != _MAIN_READER:
            self._refuse(_PHASE)
        self._reader = _WATCHER_READER
        self._phase = _WATCH
        return self.next_seq

    def join(self, frame: object) -> Control:
        """Main commits the single watcher frame after joining it; None = join failed."""
        self._usable()
        if self._phase != _WATCH or frame is None:
            self._refuse(_PHASE)
        control = _control_or_none(frame)
        if control is None:
            self._refuse(_CONTROL_CATEGORY)
        expected = (T4_CASE, self.next_seq)
        if control.kind not in (STOP, NOSTOP) or (control.case, control.seq) != expected:
            self._refuse(_PHASE)
        self._accepted += 1
        self._reader = _MAIN_READER
        self._phase = _JOINED
        if control.kind == NOSTOP:
            self._failed = (T4_CASE,)
        return control

    def summary(self) -> Summary:
        """Once, after ACK{T5} and before READY{T6}; prefix only."""
        self._usable()
        if self._phase != _SUMMARY_DUE:
            self._refuse(_PHASE)
        self._case = T6_CASE
        self._phase = _READY_DUE
        return Summary(prefix_cases=PREFIX_CASES, failed_cases=self._failed, global_pass=False)

    def eof(self) -> NoReturn:
        """Host EOF is never an accepted transition in this protocol."""
        self._usable()
        self._refuse(_PHASE)


# ---------------------------------------------------------------- fixed SQL table


def job_sql(job: object, canary: object) -> str:
    """Fixed table text; the canary is escaped data inside one string literal."""
    number = _int_or_none(job, 1, JOBS)
    text = _canary_or_none(canary)
    if number is None or text is None:
        raise LabRefusal(_SQL_CATEGORY)
    if number == _CAST_JOB:
        return "SELECT '" + text.replace("'", "''") + "'::integer"
    return _SQL[number]


# ---------------------------------------------------------------- literal resolver


def _pin(ip: object, port: object) -> tuple[str, int]:
    address = _ipv4_or_none(ip)
    number = _int_or_none(port, 1, _MAX_PORT)
    if address is None or number is None:
        raise LabRefusal(_DESTINATION)
    return address, number


def exact_resolver(ip: object, port: object) -> Callable[[object, object], tuple[str, ...]]:
    """Resolver for one validated pinned pair; any other host/port is refused."""
    address, number = _pin(ip, port)

    def resolve(host: object, requested: object) -> tuple[str, ...]:
        if type(host) is not str or host != address:
            raise LabRefusal(_DESTINATION)
        if _int_or_none(requested, number, number) is None:
            raise LabRefusal(_DESTINATION)
        return (address,)

    return resolve


def _resolved_or_none(address: str, number: int) -> tuple[str, ...] | None:
    try:
        resolved = resolve_destination(
            address,
            number,
            policy=DestinationPolicy(),
            resolver=exact_resolver(address, number),
            expected_addresses=(address,),
        ).addresses
    except Exception:  # converted to one closed category by the caller
        return None
    return resolved if resolved == (address,) else None


def pinned_addresses(ip: object, port: object) -> tuple[str, ...]:
    """Public destination validation of the literal pair, without DNS or a child."""
    address, number = _pin(ip, port)
    resolved = _resolved_or_none(address, number)
    if resolved is None:
        raise LabRefusal(_DESTINATION)
    return resolved


# ---------------------------------------------------------------- snapshot capture


def _lab_policy(generation: int) -> DatasourcePolicy:
    return DatasourcePolicy.from_mapping(
        {
            "database": {"statement_timeout_ms": _TIMEOUTS[generation], "max_rows": MAX_ROWS},
            "masking": [
                {"match": "cpf", "transformer": "hmac_sha256"},
                {
                    "match": "email",
                    "transformer": "regex",
                    "config": {"pattern": "^(.{2}).*(@.*)$", "replacement": "\\1***\\2"},
                },
                {
                    "match": "numeric_secret",
                    "transformer": "fixed",
                    "config": {"value": "[NUMBER]"},
                },
                {
                    "match": "token",
                    "transformer": "random",
                    "config": {"strategy": "alphanumeric", "preserve_length": False, "length": 12},
                },
            ],
            "exceptions": [{"match": "tipo_cpf", "mode": "exact"}],
        }
    )


def _snapshot(init: LabInit, generation: int) -> bytes:
    target = init.target
    addresses = pinned_addresses(target.ip, target.port)
    policy = _lab_policy(generation)
    limits = DatasourceLimits(statement_timeout_ms=_TIMEOUTS[generation], max_rows=MAX_ROWS)
    spec = CandidateSpec(
        host=target.ip,
        port=target.port,
        database=target.database,
        username=target.username,
        tls=TlsSettings(mode="disable"),
        policy=policy,
        limits=limits,
        destination_policy=DestinationPolicy(),
        expected_addresses=addresses,
        secret=init.readonly_password,
    )
    # Same compilation and recorder as the public loader; explicit map only.
    recorder = RecordingSecrets(MappingSecretProvider({HMAC_KEY_ENV: init.hmac_key}))
    loaded = parse_config_bundle(policy.to_mapping(), secrets=recorder)
    settings = effective_database_settings(loaded.file_config, limits)
    config = GatewayConfig(
        masking=loaded.gateway.masking, database=settings, sql=loaded.gateway.sql
    )
    template = capture_template(policy, config, build_conninfo(spec, addresses), recorder)
    return template.bind(SnapshotIdentity(DATASOURCE_ID, generation, RECORD_REVISION))


def _snapshot_or_none(init: LabInit, generation: int) -> bytes | None:
    try:
        return _snapshot(init, generation)
    except Exception:  # converted to one closed category by the caller
        return None


def capture(init: object, generation: object) -> bytes:
    """Secret-bearing D-111 snapshot bytes for G1 (1) or G2 (2)."""
    if not isinstance(init, LabInit) or type(init) is not LabInit:
        raise LabRefusal(_CAPTURE)
    number = _int_or_none(generation, 1, len(_TIMEOUTS))
    data = None if number is None else _snapshot_or_none(init, number)
    if data is None:
        raise LabRefusal(_CAPTURE)
    return data
