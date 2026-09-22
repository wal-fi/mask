"""Modelos fechados e imutaveis do catalogo de datasources.

Os modelos deste modulo nao guardam senha em plaintext. O envelope cifrado e
redigido em ``repr`` e o snapshot administrativo nunca possui um caminho que
devolva o plaintext.
"""

from __future__ import annotations

import base64
import ipaddress
import re
import secrets
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final, Literal, TypeAlias, cast

from pydantic import ValidationError

from maskgw.config.models import MaskingFileConfig

DATASOURCE_ID_PREFIX: Final = "dso_"
DATASOURCE_ID_HEX_LENGTH: Final = 32
DATASOURCE_ID_PATTERN: Final = rf"^{DATASOURCE_ID_PREFIX}[0-9a-f]{{{DATASOURCE_ID_HEX_LENGTH}}}$"
ALIAS_PATTERN: Final = r"^[a-z][a-z0-9_-]{0,62}$"
_CONTROL_RE: Final = re.compile(r"[\x00-\x1f\x7f]")
_B64_RE: Final = re.compile(r"^[A-Za-z0-9_-]+$")
_MAX_HOST_LABEL: Final = 63
_MAX_PORT: Final = 65_535
_NONCE_BYTES: Final = 12
_GCM_TAG_BYTES: Final = 16
_MIN_TIMEOUT_MS: Final = 100
_MAX_TIMEOUT_MS: Final = 600_000
_MAX_ROWS: Final = 1_000_000
_MAX_SESSIONS: Final = 1_000

JsonScalar: TypeAlias = bool | int | float | str | None


class DatasourceValidationError(ValueError):
    """Modelo de datasource invalido, sem ecoar valores sensiveis."""

    def __init__(self, message: str = "modelo de datasource invalido") -> None:
        super().__init__(message)


class DatasourceIdError(DatasourceValidationError):
    """ID opaco ausente ou fora do schema."""


def _safe_text(value: object, *, field: str, max_length: int) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise DatasourceValidationError(f"{field} invalido")
    if value.strip() != value or _CONTROL_RE.search(value) is not None:
        raise DatasourceValidationError(f"{field} invalido")
    return value


def validate_datasource_id(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(DATASOURCE_ID_PATTERN, value) is None:
        raise DatasourceIdError()
    return value


def new_datasource_id() -> str:
    return f"{DATASOURCE_ID_PREFIX}{secrets.token_hex(DATASOURCE_ID_HEX_LENGTH // 2)}"


def validate_alias(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(ALIAS_PATTERN, value) is None:
        raise DatasourceValidationError("alias invalido")
    return value


def validate_host(value: object) -> str:
    host = _safe_text(value, field="host", max_length=253)
    if "/" in host or "@" in host or "://" in host or "\\" in host:
        raise DatasourceValidationError("host invalido")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if "." not in host and ":" not in host:
            raise DatasourceValidationError("host invalido") from None
        labels = host.rstrip(".").split(".")
        if any(not label or len(label) > _MAX_HOST_LABEL for label in labels):
            raise DatasourceValidationError("host invalido") from None
        if any(not re.fullmatch(r"[A-Za-z0-9-]+", label) for label in labels):
            raise DatasourceValidationError("host invalido") from None
    return host


def validate_resolved_address(value: object) -> str:
    if not isinstance(value, str):
        raise DatasourceValidationError("endereco resolvido invalido")
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        raise DatasourceValidationError("endereco resolvido invalido") from None
    return address.compressed


@dataclass(frozen=True, slots=True, repr=False)
class EncryptedSecret:
    """Ciphertext GCM interno; a representacao nao vaza bytes."""

    algorithm: Literal["AES-256-GCM"]
    version: int
    nonce: bytes
    ciphertext: bytes

    def __post_init__(self) -> None:
        if (
            self.algorithm != "AES-256-GCM"
            or not isinstance(self.version, int)
            or isinstance(self.version, bool)
            or self.version != 1
            or not isinstance(self.nonce, bytes)
            or not isinstance(self.ciphertext, bytes)
        ):
            raise DatasourceValidationError("envelope criptografico invalido")
        if len(self.nonce) != _NONCE_BYTES or len(self.ciphertext) < _GCM_TAG_BYTES:
            raise DatasourceValidationError("envelope criptografico invalido")

    def __repr__(self) -> str:
        return "EncryptedSecret(<redacted>)"


@dataclass(frozen=True, slots=True)
class TlsSettings:
    mode: Literal["disable", "require", "verify-full"] = "disable"
    server_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mode, str) or self.mode not in {
            "disable",
            "require",
            "verify-full",
        }:
            raise DatasourceValidationError("politica TLS invalida")
        if self.server_name is not None and not isinstance(self.server_name, str):
            raise DatasourceValidationError("server_name TLS invalido")
        if self.server_name is not None:
            validate_host(self.server_name)


@dataclass(frozen=True, slots=True)
class DatasourceLimits:
    statement_timeout_ms: int = 30_000
    max_rows: int = 1_000
    max_sessions: int = 8

    def __post_init__(self) -> None:
        if (
            not isinstance(self.statement_timeout_ms, int)
            or isinstance(self.statement_timeout_ms, bool)
            or not _MIN_TIMEOUT_MS <= self.statement_timeout_ms <= _MAX_TIMEOUT_MS
        ):
            raise DatasourceValidationError("statement_timeout_ms invalido")
        if (
            not isinstance(self.max_rows, int)
            or isinstance(self.max_rows, bool)
            or not 1 <= self.max_rows <= _MAX_ROWS
        ):
            raise DatasourceValidationError("max_rows invalido")
        if (
            not isinstance(self.max_sessions, int)
            or isinstance(self.max_sessions, bool)
            or not 1 <= self.max_sessions <= _MAX_SESSIONS
        ):
            raise DatasourceValidationError("max_sessions invalido")


@dataclass(frozen=True, slots=True)
class DestinationPolicy:
    """Politica de rede persistida junto ao datasource."""

    allow_public: bool = False
    allow_loopback: bool = False
    allowed_hosts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.allow_public, bool) or not isinstance(self.allow_loopback, bool):
            raise DatasourceValidationError("politica de destino invalida")
        if not isinstance(self.allowed_hosts, tuple) or any(
            not isinstance(host, str) for host in self.allowed_hosts
        ):
            raise DatasourceValidationError("allowlist de destino invalida")
        normalized = tuple(host.lower() for host in self.allowed_hosts)
        if normalized != tuple(self.allowed_hosts) or len(set(normalized)) != len(normalized):
            raise DatasourceValidationError("allowlist de destino invalida")
        for host in normalized:
            validate_host(host)
        object.__setattr__(self, "allowed_hosts", normalized)


@dataclass(frozen=True, slots=True)
class LastTest:
    status: Literal["never", "passed", "failed"] = "never"
    checked_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, str) or self.status not in {"never", "passed", "failed"}:
            raise DatasourceValidationError("status de teste invalido")
        if self.checked_at is not None and not isinstance(self.checked_at, str):
            raise DatasourceValidationError("timestamp de teste invalido")
        if self.checked_at is not None:
            try:
                parsed = datetime.fromisoformat(self.checked_at.replace("Z", "+00:00"))
            except ValueError:
                raise DatasourceValidationError("timestamp de teste invalido") from None
            if parsed.tzinfo is None:
                raise DatasourceValidationError("timestamp de teste invalido")

    @classmethod
    def now(cls, status: Literal["passed", "failed"]) -> LastTest:
        return cls(status=status, checked_at=datetime.now(UTC).isoformat())


class FrozenObject(Mapping[str, "JsonValue"]):
    """Mapping recursivamente imutavel usado para a policy fechada."""

    __slots__ = ("_items",)

    def __init__(self, items: tuple[tuple[str, JsonValue], ...]) -> None:
        self._items = items

    def __getitem__(self, key: str) -> JsonValue:
        for item_key, value in self._items:
            if item_key == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _value in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __repr__(self) -> str:
        return "FrozenObject(<redacted>)"


JsonValue: TypeAlias = JsonScalar | tuple["JsonValue", ...] | FrozenObject


def freeze_json(value: object) -> JsonValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        items: list[tuple[str, JsonValue]] = []
        for key, item in value.items():
            if not isinstance(key, str):
                raise DatasourceValidationError("policy invalida")
            items.append((key, freeze_json(item)))
        return FrozenObject(tuple(sorted(items)))
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(item) for item in value)
    raise DatasourceValidationError("policy invalida")


def thaw_json(value: JsonValue) -> object:
    if isinstance(value, FrozenObject):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class DatasourcePolicy:
    """Politica validada pelo mesmo schema fechado do masking.yaml."""

    value: FrozenObject

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object] | None = None) -> DatasourcePolicy:
        candidate: object = {} if raw is None else dict(raw)
        try:
            parsed = MaskingFileConfig.model_validate(candidate)
        except ValidationError as exc:
            raise DatasourceValidationError("policy invalida") from exc
        dumped = cast(Mapping[str, object], parsed.model_dump(mode="json"))
        frozen = freeze_json(dumped)
        if not isinstance(frozen, FrozenObject):
            raise DatasourceValidationError("policy invalida")
        return cls(value=frozen)

    def to_mapping(self) -> dict[str, object]:
        value = thaw_json(self.value)
        if not isinstance(value, dict):
            raise DatasourceValidationError("policy invalida")
        return value


@dataclass(frozen=True, slots=True)
class DatasourceDraft:
    """Dados nao secretos para criar ou substituir um datasource."""

    alias: str
    display_name: str
    host: str
    port: int
    database: str
    username: str
    enabled: bool = True
    tls: TlsSettings = TlsSettings()
    policy: DatasourcePolicy = field(default_factory=DatasourcePolicy.from_mapping)
    limits: DatasourceLimits = DatasourceLimits()
    destination_policy: DestinationPolicy = DestinationPolicy()
    resolved_addresses: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_alias(self.alias)
        _safe_text(self.display_name, field="display_name", max_length=128)
        validate_host(self.host)
        if (
            not isinstance(self.port, int)
            or isinstance(self.port, bool)
            or not 1 <= self.port <= _MAX_PORT
        ):
            raise DatasourceValidationError("porta invalida")
        _safe_text(self.database, field="database", max_length=63)
        _safe_text(self.username, field="username", max_length=63)
        if not isinstance(self.enabled, bool):
            raise DatasourceValidationError("enabled invalido")
        if len(set(self.resolved_addresses)) != len(self.resolved_addresses):
            raise DatasourceValidationError("enderecos resolvidos duplicados")
        for address in self.resolved_addresses:
            validate_resolved_address(address)


@dataclass(frozen=True, slots=True, repr=False)
class DatasourceRecord:
    """Registro persistido, sem plaintext de segredo."""

    id: str
    alias: str
    display_name: str
    enabled: bool
    host: str
    port: int
    database: str
    username: str
    tls: TlsSettings
    policy: DatasourcePolicy
    limits: DatasourceLimits
    destination_policy: DestinationPolicy
    resolved_addresses: tuple[str, ...]
    revision: int
    last_test: LastTest
    _upstream_secret: EncryptedSecret = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self._upstream_secret, EncryptedSecret):
            raise DatasourceValidationError("envelope criptografico invalido")
        validate_datasource_id(self.id)
        draft = DatasourceDraft(
            alias=self.alias,
            display_name=self.display_name,
            host=self.host,
            port=self.port,
            database=self.database,
            username=self.username,
            enabled=self.enabled,
            tls=self.tls,
            policy=self.policy,
            limits=self.limits,
            destination_policy=self.destination_policy,
            resolved_addresses=self.resolved_addresses,
        )
        del draft
        if self.revision < 1:
            raise DatasourceValidationError("revision invalida")

    @property
    def secret_configured(self) -> bool:
        return True

    def __repr__(self) -> str:
        return (
            f"DatasourceRecord(id={self.id!r}, alias={self.alias!r}, "
            f"revision={self.revision}, enabled={self.enabled!r}, "
            "upstream_secret=<redacted>)"
        )


@dataclass(frozen=True, slots=True, repr=False)
class CatalogSnapshot:
    catalog_revision: int
    datasources: tuple[DatasourceRecord, ...]
    digest: str

    def __repr__(self) -> str:
        return (
            f"CatalogSnapshot(catalog_revision={self.catalog_revision}, "
            f"datasources={len(self.datasources)}, digest=<redacted>)"
        )


def encode_b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def decode_b64(value: object) -> bytes:
    if not isinstance(value, str) or not value or _CONTROL_RE.search(value) is not None:
        raise DatasourceValidationError("envelope criptografico invalido")
    if _B64_RE.fullmatch(value) is None:
        raise DatasourceValidationError("envelope criptografico invalido")
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (ValueError, TypeError):
        raise DatasourceValidationError("envelope criptografico invalido") from None
