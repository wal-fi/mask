"""Private compilation snapshot, not a worker, IPC transport or client API.

B-1: record the secrets consumed by THIS compilation and recompile through the
existing loader. Explicit capture only; no environment reread on reconstruction.
The canonical format is local version 1, not a claim of RFC 8785 compliance.
Bytes contain secrets: only the explicit encode operation may expose them.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NoReturn

from maskgw.config.gateway import DatabaseSettings, GatewayConfig, parse_config_bundle
from maskgw.config.models import (
    MAX_MAX_ROWS,
    MAX_STATEMENT_TIMEOUT_MS,
    MIN_MAX_ROWS,
    MIN_STATEMENT_TIMEOUT_MS,
)
from maskgw.datasource.models import DatasourcePolicy, validate_datasource_id
from maskgw.masking.engine import MaskingEngine
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.secretsource import SecretProvider

MAX_SNAPSHOT_BYTES: Final = 64 * 1024
_MAX_DEPTH: Final = 32
_MAX_IDENTITY: Final = (1 << 63) - 1
_IDENTITY_ALLOWANCE: Final = 512
_BACKSLASH: Final = ord("\\")
_QUOTE: Final = ord('"')
_RUNTIME_FIELDS: Final = frozenset({"policy", "database", "conninfo", "secrets"})


class SnapshotFailure(StrEnum):
    INVALID = "INVALID"
    POLICY = "POLICY"
    UNAVAILABLE = "UNAVAILABLE"


class SnapshotError(ValueError):
    """Closed internal category; never input values or original exception chains."""

    def __init__(self, category: SnapshotFailure = SnapshotFailure.INVALID) -> None:
        super().__init__("snapshot de compilacao recusado")
        self.category = category


def _refuse(category: SnapshotFailure = SnapshotFailure.INVALID) -> NoReturn:
    raise SnapshotError(category) from None


@dataclass(frozen=True, slots=True)
class SnapshotIdentity:
    datasource_id: str
    generation: int
    record_revision: int

    def __post_init__(self) -> None:
        failed = False
        try:
            validate_datasource_id(self.datasource_id)
            if any(
                type(value) is not int or not 1 <= value <= _MAX_IDENTITY
                for value in (self.generation, self.record_revision)
            ):
                failed = True
        except (TypeError, ValueError):
            failed = True
        if failed:
            _refuse()

    def _mapping(self) -> dict[str, object]:
        return {
            "datasource_id": self.datasource_id,
            "generation": self.generation,
            "record_revision": self.record_revision,
        }


class RecordingSecrets:
    """First read per name wins within one compilation; no second source read.

    Only HMAC is in this closed version. A future secret requires a format and
    code review, not silent forwarding of a catalog master key or environment.
    Exact provider values are preserved, including whitespace from custom
    providers. Normalization remains the original provider's responsibility.
    """

    __slots__ = ("_source", "_values")

    def __init__(self, source: SecretProvider) -> None:
        self._source = source
        self._values: dict[str, str | None] = {}

    def get(self, name: str) -> str | None:
        if name != HMAC_KEY_ENV:
            _refuse(SnapshotFailure.POLICY)
        failed = False
        if name not in self._values:
            try:
                value = self._source.get(name)
                if value is not None and type(value) is not str:
                    failed = True
                else:
                    self._values[name] = value
            except Exception:
                failed = True
        if failed:
            _refuse(SnapshotFailure.POLICY)
        return self._values[name]

    def _captured(self) -> dict[str, str]:
        return {name: value for name, value in self._values.items() if value is not None}

    def __repr__(self) -> str:
        return "RecordingSecrets(<redacted>)"


class _ClosedSecrets:
    __slots__ = ("_read", "_values")

    def __init__(self, values: dict[str, str]) -> None:
        self._values = dict(values)
        self._read: set[str] = set()

    def get(self, name: str) -> str | None:
        if name not in self._values:
            _refuse(SnapshotFailure.POLICY)
        self._read.add(name)
        return self._values[name]

    def complete(self) -> bool:
        return self._read == self._values.keys()

    def __repr__(self) -> str:
        return "ClosedSnapshotSecrets(<redacted>)"


def _canonical(value: object) -> bytes:
    result: bytes | None = None
    with contextlib.suppress(TypeError, ValueError, OverflowError, RecursionError):
        result = json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("ascii")
    if result is None or len(result) > MAX_SNAPSHOT_BYTES:
        _refuse()
    return result


def _depth_guard(data: bytes) -> None:
    depth = 0
    quoted = escaped = False
    for byte in data:
        if quoted:
            if escaped:
                escaped = False
            elif byte == _BACKSLASH:
                escaped = True
            elif byte == _QUOTE:
                quoted = False
        elif byte == _QUOTE:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            if depth > _MAX_DEPTH:
                _refuse()
        elif byte in (93, 125):
            depth -= 1


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _refuse()
        result[key] = value
    return result


def _constant(_value: str) -> NoReturn:
    _refuse()


def _decode(data: bytes) -> dict[str, object]:
    if type(data) is not bytes or not 0 < len(data) <= MAX_SNAPSHOT_BYTES:
        _refuse()
    failure: SnapshotFailure | None = None
    value: object = None
    try:
        _depth_guard(data)
        value = json.loads(
            data.decode("ascii"), object_pairs_hook=_object, parse_constant=_constant
        )
        if type(value) is not dict or _canonical(value) != data:
            failure = SnapshotFailure.INVALID
    except (MemoryError, RecursionError):
        failure = SnapshotFailure.UNAVAILABLE
    except Exception:
        failure = SnapshotFailure.INVALID
    if failure is not None or not isinstance(value, dict):
        _refuse(failure or SnapshotFailure.INVALID)
    return value


def _database(raw: object) -> DatabaseSettings:
    if not isinstance(raw, dict) or set(raw) != {"statement_timeout_ms", "max_rows"}:
        _refuse()
    timeout, rows = raw["statement_timeout_ms"], raw["max_rows"]
    if (
        type(timeout) is not int
        or not MIN_STATEMENT_TIMEOUT_MS <= timeout <= MAX_STATEMENT_TIMEOUT_MS
        or type(rows) is not int
        or not MIN_MAX_ROWS <= rows <= MAX_MAX_ROWS
    ):
        _refuse()
    return DatabaseSettings(statement_timeout_ms=timeout, max_rows=rows)


def _identity(raw: object) -> SnapshotIdentity:
    if not isinstance(raw, dict) or set(raw) != {"datasource_id", "generation", "record_revision"}:
        _refuse()
    return SnapshotIdentity(raw["datasource_id"], raw["generation"], raw["record_revision"])


def _runtime(
    raw: dict[str, object],
) -> tuple[DatasourcePolicy, DatabaseSettings, str, _ClosedSecrets]:
    if set(raw) != _RUNTIME_FIELDS:
        _refuse()
    policy_raw = raw["policy"]
    if not isinstance(policy_raw, dict):
        _refuse()
    policy = DatasourcePolicy.from_mapping(policy_raw)
    if _canonical(policy.to_mapping()) != _canonical(policy_raw):
        _refuse()
    database = _database(raw["database"])
    source_database = _database(policy.to_mapping()["database"])
    if (
        database.max_rows > source_database.max_rows
        or database.statement_timeout_ms > source_database.statement_timeout_ms
    ):
        _refuse()
    conninfo, secrets = raw["conninfo"], raw["secrets"]
    if type(conninfo) is not str or not conninfo or "\x00" in conninfo:
        _refuse()
    if not isinstance(secrets, dict) or any(
        name != HMAC_KEY_ENV or type(value) is not str for name, value in secrets.items()
    ):
        _refuse()
    values: dict[str, str] = {name: str(value) for name, value in secrets.items()}
    return policy, database, conninfo, _ClosedSecrets(values)


@dataclass(frozen=True, slots=True, repr=False)
class SnapshotTemplate:
    """Detached canonical inputs captured at compile time, without generation ID."""

    _payload: bytes

    def __post_init__(self) -> None:
        failed = False
        try:
            if len(self._payload) > MAX_SNAPSHOT_BYTES - _IDENTITY_ALLOWANCE:
                failed = True
            else:
                _runtime(_decode(self._payload))
        except Exception:
            failed = True
        if failed:
            _refuse()

    def bind(self, identity: SnapshotIdentity) -> bytes:
        """Explicit secret-bearing bytes; trusted generation identity only.

        This is serialization, not authentication. No client or transport is
        wired here; future handshake ownership/correlation remain separate.
        """
        if type(identity) is not SnapshotIdentity:
            _refuse()
        return _canonical(
            {"version": 1, "identity": identity._mapping(), "runtime": _decode(self._payload)}
        )

    def __repr__(self) -> str:
        return "SnapshotTemplate(<redacted>)"


def capture_template(
    policy: DatasourcePolicy,
    config: GatewayConfig,
    conninfo: str,
    secrets: RecordingSecrets,
) -> SnapshotTemplate:
    """Called only after the SAME compilation using ``secrets`` succeeded."""
    return SnapshotTemplate(
        _canonical(
            {
                "policy": policy.to_mapping(),
                "database": {
                    "statement_timeout_ms": config.database.statement_timeout_ms,
                    "max_rows": config.database.max_rows,
                },
                "conninfo": conninfo,
                "secrets": secrets._captured(),
            }
        )
    )


@dataclass(frozen=True, slots=True, repr=False)
class RecompiledSnapshot:
    identity: SnapshotIdentity
    config: GatewayConfig
    engine: MaskingEngine
    _conninfo: str

    def connection_target(self) -> str:
        """Secret-bearing pinned target; no connect or DNS operation."""
        return self._conninfo

    def __repr__(self) -> str:
        return "RecompiledSnapshot(<redacted>)"


def recompile_snapshot(data: bytes, *, expected: SnapshotIdentity) -> RecompiledSnapshot:
    """Closed bounded decoding and existing compiler; never environment fallback."""
    failure = SnapshotFailure.INVALID
    result: RecompiledSnapshot | None = None
    try:
        raw = _decode(data)
        if (
            type(expected) is not SnapshotIdentity
            or set(raw) != {"version", "identity", "runtime"}
            or type(raw["version"]) is not int
            or raw["version"] != 1
            or _identity(raw["identity"]) != expected
            or not isinstance(raw["runtime"], dict)
        ):
            _refuse()
        policy, database, conninfo, provider = _runtime(raw["runtime"])
        failure = SnapshotFailure.POLICY
        loaded = parse_config_bundle(policy.to_mapping(), secrets=provider)
        if not provider.complete():
            _refuse(SnapshotFailure.POLICY)
        config = GatewayConfig(
            masking=loaded.gateway.masking, database=database, sql=loaded.gateway.sql
        )
        result = RecompiledSnapshot(expected, config, MaskingEngine(config.masking), conninfo)
    except SnapshotError as error:
        failure = error.category
    except (MemoryError, RecursionError):
        failure = SnapshotFailure.UNAVAILABLE
    except Exception:
        result = None
    if result is None:
        _refuse(failure)
    return result
