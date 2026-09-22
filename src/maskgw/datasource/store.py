"""Store cifrado e autenticado de datasources com âncora contra replay."""

from __future__ import annotations

import errno
import hmac
import json
import os
import re
import secrets
import stat
import threading
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from functools import wraps
from pathlib import Path
from typing import Any, Final, Literal, ParamSpec, TypeVar, cast

if os.name == "posix":
    import fcntl
else:
    import msvcrt

from maskgw.datasource.crypto import (
    CATALOG_FORMAT,
    CATALOG_SCHEMA_VERSION,
    MASTER_KEY_ENV,
    canonical_json,
    catalog_auth_tag,
    catalog_digest,
    envelope_to_json,
    open_secret,
    seal_secret,
    validate_master_key,
    verify_catalog_auth,
)
from maskgw.datasource.destination import resolve_destination
from maskgw.datasource.models import (
    CatalogSnapshot,
    DatasourceDraft,
    DatasourceLimits,
    DatasourcePolicy,
    DatasourceRecord,
    DatasourceValidationError,
    DestinationPolicy,
    EncryptedSecret,
    LastTest,
    TlsSettings,
    decode_b64,
    new_datasource_id,
    validate_alias,
    validate_datasource_id,
)
from maskgw.secretsource import EnvSecretProvider, SecretProvider

STORE_ENV: Final = "MASKGW_DATASOURCE_STORE"
ANCHOR_ENV: Final = "MASKGW_DATASOURCE_ANCHOR"
DEFAULT_STORE_PATH: Final = Path("config/datasources.store")
_ANCHOR_DIRECTORY: Final = ".maskgw-anchor"
_ANCHOR_NAME: Final = "datasources.anchor"
_JOURNAL_NAME: Final = "datasources.anchor.txn"
_LOCK_SUFFIX: Final = ".lock"
_PRIVATE_MODE: Final = 0o600
_PRIVATE_DIRECTORY_MODE: Final = 0o700
_UNSAFE_WRITE_BITS: Final = stat.S_IWGRP | stat.S_IWOTH
_NOFOLLOW: Final = getattr(os, "O_NOFOLLOW", 0)
_BINARY: Final = getattr(os, "O_BINARY", 0)
_BACKUP_RE: Final = re.compile(r"^datasources\.store\.bak\.[1-9][0-9]*$")
_TEMP_RE: Final = re.compile(r"^\.datasources\.store\.tmp\.[0-9]+\.[0-9a-f]{16}$")
_JOURNAL_TEMP_RE: Final = re.compile(r"^\.datasources\.anchor\.txn\.tmp\.[0-9]+\.[0-9a-f]{16}$")
_HEX_LENGTH: Final = 64


class CatalogStoreError(Exception):
    """Erro sanitizado do store local."""


class CatalogCorruptError(CatalogStoreError):
    """Store autenticado, schema ou documento inconsistente."""


class CatalogAnchorError(CatalogStoreError):
    """Âncora ausente, insegura, divergente ou journal incoerente."""


class CatalogKeyError(CatalogStoreError):
    """Chave ausente, incorreta ou incapaz de abrir o catálogo."""


class MasterKeyError(CatalogKeyError):
    """Master key fora do formato canônico."""


class CatalogWriteError(CatalogStoreError):
    """Falha antes de confirmar o par store/âncora."""


class CatalogOutcomeUncertainError(CatalogWriteError):
    """Falha depois de tentar o replace do store: o resultado não é conhecido.

    O store pode estar no estado antigo ou no novo. O chamador não pode inferir
    o resultado pelo erro; em uma rotação de master key, as chaves antiga e nova
    precisam ser preservadas até a determinação explícita.
    """


class CatalogRotationPendingError(CatalogStoreError):
    """Rotação de master key interrompida exige recuperação explícita."""


class CatalogAlreadyExistsError(CatalogStoreError):
    """Inicialização solicitada sobre arquivos existentes."""


class FilesystemPolicyError(CatalogStoreError):
    """Arquivo, diretório, symlink ou permissão fora da política."""


class LegacyMigrationError(CatalogStoreError):
    """Migração explícita do DSN legado recusada."""


class CatalogRevisionConflictError(CatalogStoreError):
    """Revision otimista divergente."""


_P = ParamSpec("_P")
_R = TypeVar("_R")


def _serialized_operation(method: Callable[_P, _R]) -> Callable[_P, _R]:
    @wraps(method)
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        catalog = cast(CatalogStore, args[0])
        with catalog._lifecycle_lock:
            catalog._ensure_open()
            return method(*args, **kwargs)

    return wrapped


class CrashPoint(StrEnum):
    """Pontos de falha controláveis usados pelos testes adversariais."""

    AFTER_JOURNAL_FSYNC = "after_journal_fsync"
    AFTER_STORE_REPLACE = "after_store_replace"
    AFTER_STORE_DIRECTORY_FSYNC = "after_store_directory_fsync"
    AFTER_ANCHOR_REPLACE = "after_anchor_replace"
    AFTER_ANCHOR_DIRECTORY_FSYNC = "after_anchor_directory_fsync"
    AFTER_BACKUP_PURGE = "after_backup_purge"
    AFTER_JOURNAL_CLEANUP = "after_journal_cleanup"


@dataclass(frozen=True, slots=True)
class MasterKeyRotationStatus:
    """Resultado explícito de uma rotação interrompida, sem material sensível.

    ``confirmed_key`` diz qual das duas chaves fornecidas autentica o estado
    confirmado e deve ser configurada; ``journal_pending`` indica se ainda
    existe journal da rotação no momento da leitura.
    """

    confirmed_key: Literal["old", "new"]
    catalog_revision: int
    journal_pending: bool


@dataclass(frozen=True, slots=True)
class CatalogHooks:
    """Hooks operacionais sem bytes ou plaintext nos callbacks."""

    file_fsync: Callable[[int], None] = os.fsync
    directory_fsync: Callable[[int], None] = os.fsync
    replace: Callable[[str, str], None] = os.replace
    remove: Callable[[str], None] = os.unlink
    temp_token: Callable[[], str] = lambda: secrets.token_hex(8)
    after_point: Callable[[CrashPoint], None] = lambda _point: None


@dataclass(frozen=True, slots=True)
class _Anchor:
    revision: int
    digest: str


@dataclass(frozen=True, slots=True)
class _Journal:
    old_revision: int
    old_digest: str | None
    new_revision: int
    new_digest: str
    old_auth_tag: str
    new_auth_tag: str


@dataclass(frozen=True, slots=True)
class _ParsedCatalog:
    revision: int
    digest: str
    records: tuple[DatasourceRecord, ...]


def _absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _fixed_hex(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _HEX_LENGTH
        and all(char in "0123456789abcdef" for char in value)
    )


def _safe_json_loads(data: bytes) -> object:
    def reject_constant(_value: str) -> object:
        raise ValueError()

    def reject_duplicate(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError()
            result[key] = value
        return result

    try:
        return json.loads(
            data.decode("utf-8"),
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicate,
        )
    except (UnicodeDecodeError, ValueError, TypeError):
        raise CatalogCorruptError("catalogo invalido") from None


def _require_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise CatalogCorruptError("catalogo invalido")
    return value


def _require_keys(value: Mapping[str, object], expected: set[str]) -> None:
    if set(value) != expected:
        raise CatalogCorruptError("schema do catalogo invalido")


def _require_int(value: object, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise CatalogCorruptError("numero do catalogo invalido")
    return value


def _require_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise CatalogCorruptError("booleano do catalogo invalido")
    return value


def _require_str(value: object) -> str:
    if not isinstance(value, str):
        raise CatalogCorruptError("texto do catalogo invalido")
    return value


def _require_str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise CatalogCorruptError("lista do catalogo invalida")
    return tuple(value)


def _validate_parent(path: Path, *, anchor: bool) -> None:
    try:
        info = path.lstat()
    except OSError:
        raise FilesystemPolicyError("diretorio do catalogo indisponivel") from None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise FilesystemPolicyError("diretorio do catalogo inseguro")
    if os.name == "posix":
        mode = stat.S_IMODE(info.st_mode)
        if anchor and mode != _PRIVATE_DIRECTORY_MODE:
            raise FilesystemPolicyError("diretorio da ancora inseguro")
        if not anchor and mode & _UNSAFE_WRITE_BITS:
            raise FilesystemPolicyError("diretorio do catalogo inseguro")


def _validate_regular(path: Path, *, anchor: bool) -> os.stat_result:
    kind = "ancora" if anchor else "catalogo"
    try:
        info = path.lstat()
    except OSError:
        raise FilesystemPolicyError(f"arquivo da {kind} indisponivel") from None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise FilesystemPolicyError(f"arquivo da {kind} inseguro")
    if os.name == "posix":
        mode = stat.S_IMODE(info.st_mode)
        if mode != _PRIVATE_MODE:
            raise FilesystemPolicyError(f"arquivo da {kind} inseguro")
    return info


def _ensure_private_directory(path: Path) -> None:
    try:
        path.mkdir(mode=_PRIVATE_DIRECTORY_MODE, parents=False, exist_ok=False)
    except FileExistsError:
        pass
    except OSError:
        raise FilesystemPolicyError("diretorio da ancora indisponivel") from None
    if os.name == "posix":
        with suppress(OSError):
            os.chmod(path, _PRIVATE_DIRECTORY_MODE, follow_symlinks=False)
    _validate_parent(path, anchor=True)


def _ensure_no_symlink_parent(path: Path) -> None:
    current = path
    while current != current.parent:
        try:
            info = current.lstat()
        except OSError:
            current = current.parent
            continue
        if stat.S_ISLNK(info.st_mode):
            raise FilesystemPolicyError("path do catalogo contém symlink")
        current = current.parent


class _SidecarLock:
    __slots__ = ("_closed", "_descriptor", "_path")

    def __init__(self, path: Path, descriptor: int) -> None:
        self._path = path
        self._descriptor = descriptor
        self._closed = False

    @classmethod
    def acquire(cls, path: Path, *, anchor: bool) -> _SidecarLock:
        _validate_parent(path.parent, anchor=anchor)
        if os.path.lexists(path):
            _validate_regular(path, anchor=anchor)
        descriptor = -1
        try:
            descriptor = os.open(
                path,
                os.O_RDWR | os.O_CREAT | _BINARY | _NOFOLLOW,
                _PRIVATE_MODE,
            )
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise OSError(errno.EPERM, "not regular")
            if info.st_size == 0:
                os.write(descriptor, b"\0")
                os.fsync(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.name == "posix" and stat.S_IMODE(info.st_mode) != _PRIVATE_MODE:
                raise OSError(errno.EPERM, "unsafe mode")
            if os.name == "posix":
                fcntl_module = cast(Any, fcntl)
                fcntl_module.flock(descriptor, fcntl_module.LOCK_EX | fcntl_module.LOCK_NB)
            else:
                msvcrt_module = cast(Any, msvcrt)
                msvcrt_module.locking(descriptor, msvcrt_module.LK_NBLCK, 1)
        except FileExistsError:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
            raise CatalogAnchorError("lock do catalogo indisponivel") from None
        except (ImportError, OSError):
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
            raise CatalogAnchorError("lock do catalogo indisponivel") from None
        return cls(path, descriptor)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with suppress(ImportError, OSError):
            if os.name == "posix":
                fcntl_module = cast(Any, fcntl)
                fcntl_module.flock(self._descriptor, fcntl_module.LOCK_UN)
            else:
                os.lseek(self._descriptor, 0, os.SEEK_SET)
                msvcrt_module = cast(Any, msvcrt)
                msvcrt_module.locking(self._descriptor, msvcrt_module.LK_UNLCK, 1)
        with suppress(OSError):
            os.close(self._descriptor)


def _default_anchor_path(store_path: Path) -> Path:
    return store_path.parent / _ANCHOR_DIRECTORY / _ANCHOR_NAME


def resolve_store_paths(
    store_path: str | Path | None = None,
    anchor_path: str | Path | None = None,
) -> tuple[Path, Path]:
    selected_store = store_path
    if selected_store is None:
        env_store = os.environ.get(STORE_ENV)
        if env_store is not None and not env_store.strip():
            raise FilesystemPolicyError("caminho do store invalido")
        selected_store = env_store if env_store is not None else DEFAULT_STORE_PATH
    store = _absolute(selected_store)
    selected_anchor = anchor_path
    if selected_anchor is None:
        env_anchor = os.environ.get(ANCHOR_ENV)
        if env_anchor is not None and not env_anchor.strip():
            raise FilesystemPolicyError("caminho da ancora invalido")
        selected_anchor = env_anchor
    anchor = _absolute(selected_anchor or _default_anchor_path(store))
    if store.parent == anchor.parent:
        raise FilesystemPolicyError("store e ancora nao podem compartilhar diretorio")
    _ensure_no_symlink_parent(store)
    _ensure_no_symlink_parent(anchor)
    return store, anchor


def _key_from_provider(
    master_key: str | bytes | None,
    secrets_provider: SecretProvider | None,
) -> bytes:
    value: str | bytes | None = master_key
    if value is None:
        provider = secrets_provider if secrets_provider is not None else EnvSecretProvider()
        value = provider.get(MASTER_KEY_ENV)
    try:
        return validate_master_key(value)
    except ValueError:
        raise MasterKeyError("master key ausente ou invalida") from None


def _make_payload(revision: int, records: Sequence[DatasourceRecord]) -> dict[str, object]:
    ordered = sorted(records, key=lambda record: record.id)
    return {
        "catalog_revision": revision,
        "datasources": [_record_to_json(record) for record in ordered],
        "format": CATALOG_FORMAT,
        "schema_version": CATALOG_SCHEMA_VERSION,
    }


def _record_to_json(record: DatasourceRecord) -> dict[str, object]:
    return {
        "alias": record.alias,
        "database": record.database,
        "destination_policy": {
            "allow_loopback": record.destination_policy.allow_loopback,
            "allow_public": record.destination_policy.allow_public,
            "allowed_hosts": list(record.destination_policy.allowed_hosts),
        },
        "display_name": record.display_name,
        "enabled": record.enabled,
        "host": record.host,
        "id": record.id,
        "last_test": {
            "checked_at": record.last_test.checked_at,
            "status": record.last_test.status,
        },
        "limits": {
            "max_rows": record.limits.max_rows,
            "max_sessions": record.limits.max_sessions,
            "statement_timeout_ms": record.limits.statement_timeout_ms,
        },
        "policy": record.policy.to_mapping(),
        "port": record.port,
        "resolved_addresses": list(record.resolved_addresses),
        "revision": record.revision,
        "tls": {"mode": record.tls.mode, "server_name": record.tls.server_name},
        "upstream_secret": envelope_to_json(record._upstream_secret),
        "username": record.username,
    }


def _serialize_document(payload: Mapping[str, object], master_key: bytes) -> bytes:
    body = dict(payload)
    document: dict[str, object] = {
        **body,
        "auth": {"algorithm": "HMAC-SHA256", "tag": catalog_auth_tag(body, master_key)},
    }
    return canonical_json(document)


def _parse_envelope(value: object) -> EncryptedSecret:
    raw = _require_mapping(value)
    if set(raw) != {"algorithm", "ciphertext", "nonce", "version"}:
        raise CatalogCorruptError("envelope criptografico invalido")
    if raw["algorithm"] != "AES-256-GCM" or raw["version"] != 1:
        raise CatalogCorruptError("envelope criptografico invalido")
    try:
        nonce = decode_b64(raw["nonce"])
        ciphertext = decode_b64(raw["ciphertext"])
        return EncryptedSecret("AES-256-GCM", 1, nonce, ciphertext)
    except (ValueError, TypeError):
        raise CatalogCorruptError("envelope criptografico invalido") from None


def _parse_record(value: object) -> DatasourceRecord:
    raw = _require_mapping(value)
    expected = {
        "alias",
        "database",
        "destination_policy",
        "display_name",
        "enabled",
        "host",
        "id",
        "last_test",
        "limits",
        "policy",
        "port",
        "resolved_addresses",
        "revision",
        "tls",
        "upstream_secret",
        "username",
    }
    _require_keys(raw, expected)
    try:
        destination_raw = _require_mapping(raw["destination_policy"])
        _require_keys(destination_raw, {"allow_loopback", "allow_public", "allowed_hosts"})
        destination_policy = DestinationPolicy(
            allow_loopback=_require_bool(destination_raw["allow_loopback"]),
            allow_public=_require_bool(destination_raw["allow_public"]),
            allowed_hosts=_require_str_tuple(destination_raw["allowed_hosts"]),
        )
        tls_raw = _require_mapping(raw["tls"])
        _require_keys(tls_raw, {"mode", "server_name"})
        tls = TlsSettings(
            mode=cast(Literal["disable", "require", "verify-full"], tls_raw["mode"]),
            server_name=cast(str | None, tls_raw["server_name"]),
        )
        limits_raw = _require_mapping(raw["limits"])
        _require_keys(limits_raw, {"max_rows", "max_sessions", "statement_timeout_ms"})
        limits = DatasourceLimits(
            max_rows=_require_int(limits_raw["max_rows"], minimum=1),
            max_sessions=_require_int(limits_raw["max_sessions"], minimum=1),
            statement_timeout_ms=_require_int(limits_raw["statement_timeout_ms"], minimum=1),
        )
        last_raw = _require_mapping(raw["last_test"])
        _require_keys(last_raw, {"checked_at", "status"})
        last_test = LastTest(
            status=cast(Literal["never", "passed", "failed"], last_raw["status"]),
            checked_at=cast(str | None, last_raw["checked_at"]),
        )
        policy_raw = _require_mapping(raw["policy"])
        policy_draft = DatasourceDraft(
            alias=_require_str(raw["alias"]),
            display_name=_require_str(raw["display_name"]),
            host=_require_str(raw["host"]),
            port=_require_int(raw["port"], minimum=1),
            database=_require_str(raw["database"]),
            username=_require_str(raw["username"]),
            enabled=_require_bool(raw["enabled"]),
            tls=tls,
            policy=DatasourcePolicy.from_mapping(policy_raw),
            limits=limits,
            destination_policy=destination_policy,
            resolved_addresses=_require_str_tuple(raw["resolved_addresses"]),
        )
        envelope = _parse_envelope(raw["upstream_secret"])
        return DatasourceRecord(
            id=validate_datasource_id(raw["id"]),
            alias=policy_draft.alias,
            display_name=policy_draft.display_name,
            enabled=policy_draft.enabled,
            host=policy_draft.host,
            port=policy_draft.port,
            database=policy_draft.database,
            username=policy_draft.username,
            tls=policy_draft.tls,
            policy=policy_draft.policy,
            limits=policy_draft.limits,
            destination_policy=policy_draft.destination_policy,
            resolved_addresses=policy_draft.resolved_addresses,
            revision=_require_int(raw["revision"], minimum=1),
            last_test=last_test,
            _upstream_secret=envelope,
        )
    except (KeyError, TypeError, ValueError, AttributeError, DatasourceValidationError):
        raise CatalogCorruptError("registro de datasource invalido") from None


def _parse_catalog(
    data: bytes,
    master_key: bytes,
    *,
    authenticate: bool = True,
) -> _ParsedCatalog:
    document = _safe_json_loads(data)
    raw = _require_mapping(document)
    _require_keys(raw, {"auth", "catalog_revision", "datasources", "format", "schema_version"})
    if raw["format"] != CATALOG_FORMAT or raw["schema_version"] != CATALOG_SCHEMA_VERSION:
        raise CatalogCorruptError("versao do catalogo nao suportada")
    revision = _require_int(raw["catalog_revision"], minimum=1)
    auth = _require_mapping(raw["auth"])
    _require_keys(auth, {"algorithm", "tag"})
    if auth["algorithm"] != "HMAC-SHA256":
        raise CatalogCorruptError("autenticacao do catalogo invalida")
    payload = dict(raw)
    del payload["auth"]
    if canonical_json(raw) != data:
        raise CatalogCorruptError("catalogo nao canonico")
    if authenticate:
        try:
            verify_catalog_auth(payload, auth["tag"], master_key)
        except ValueError:
            raise CatalogKeyError("nao foi possivel autenticar o catalogo") from None
    raw_records = raw["datasources"]
    if not isinstance(raw_records, list):
        raise CatalogCorruptError("datasources invalido")
    records = tuple(_parse_record(item) for item in raw_records)
    if tuple(sorted(record.id for record in records)) != tuple(record.id for record in records):
        raise CatalogCorruptError("datasources fora de ordem")
    if len({record.id for record in records}) != len(records):
        raise CatalogCorruptError("IDs de datasource duplicados")
    if len({record.alias for record in records}) != len(records):
        raise CatalogCorruptError("aliases de datasource duplicados")
    return _ParsedCatalog(revision, catalog_digest(payload), records)


def _anchor_bytes(anchor: _Anchor) -> bytes:
    return canonical_json(
        {"catalog_digest": anchor.digest, "catalog_revision": anchor.revision, "format": 1}
    )


def _parse_anchor(data: bytes) -> _Anchor:
    raw = _safe_json_loads(data)
    mapping = _require_mapping(raw)
    _require_keys(mapping, {"catalog_digest", "catalog_revision", "format"})
    if mapping["format"] != 1 or not _fixed_hex(mapping["catalog_digest"]):
        raise CatalogAnchorError("ancora invalida")
    revision = _require_int(mapping["catalog_revision"], minimum=1)
    if canonical_json(mapping) != data:
        raise CatalogAnchorError("ancora invalida")
    return _Anchor(revision, cast(str, mapping["catalog_digest"]))


def _journal_payload(journal: _Journal) -> dict[str, object]:
    return {
        "format": 1,
        "new_digest": journal.new_digest,
        "new_revision": journal.new_revision,
        "old_digest": journal.old_digest,
        "old_revision": journal.old_revision,
    }


def _journal_bytes(journal: _Journal) -> bytes:
    return canonical_json(
        {
            **_journal_payload(journal),
            "new_auth_tag": journal.new_auth_tag,
            "old_auth_tag": journal.old_auth_tag,
        }
    )


def _parse_journal_document(data: bytes) -> _Journal:
    """Valida schema e forma canônica; a autenticação é feita por papel."""
    raw = _safe_json_loads(data)
    mapping = _require_mapping(raw)
    expected = {
        "format",
        "new_auth_tag",
        "new_digest",
        "new_revision",
        "old_auth_tag",
        "old_digest",
        "old_revision",
    }
    _require_keys(mapping, expected)
    if mapping["format"] != 1 or not _fixed_hex(mapping["new_digest"]):
        raise CatalogAnchorError("journal invalido")
    old_digest = mapping["old_digest"]
    if old_digest is not None and not _fixed_hex(old_digest):
        raise CatalogAnchorError("journal invalido")
    old_revision = _require_int(mapping["old_revision"], minimum=0)
    new_revision = _require_int(mapping["new_revision"], minimum=1)
    if new_revision != old_revision + 1:
        raise CatalogAnchorError("journal invalido")
    if (old_revision == 0) != (old_digest is None):
        raise CatalogAnchorError("journal invalido")
    old_tag = mapping["old_auth_tag"]
    new_tag = mapping["new_auth_tag"]
    if not _fixed_hex(old_tag) or not _fixed_hex(new_tag):
        raise CatalogAnchorError("journal invalido")
    if canonical_json(mapping) != data:
        raise CatalogAnchorError("journal invalido")
    return _Journal(
        old_revision=old_revision,
        old_digest=cast(str | None, old_digest),
        new_revision=new_revision,
        new_digest=cast(str, mapping["new_digest"]),
        old_auth_tag=cast(str, old_tag),
        new_auth_tag=cast(str, new_tag),
    )


def _journal_roles(journal: _Journal, master_key: bytes) -> tuple[bool, bool]:
    """Diz se a chave autentica o papel antigo e/ou o novo do journal."""
    expected = catalog_auth_tag(_journal_payload(journal), master_key)
    return (
        hmac.compare_digest(expected, journal.old_auth_tag),
        hmac.compare_digest(expected, journal.new_auth_tag),
    )


def _is_rotation_journal(journal: _Journal) -> bool:
    """Tags distintas só são produzidas quando a transação troca a master key."""
    return not hmac.compare_digest(journal.old_auth_tag, journal.new_auth_tag)


def _parse_journal(data: bytes, master_key: bytes) -> tuple[_Journal, bool, bool]:
    journal = _parse_journal_document(data)
    as_old, as_new = _journal_roles(journal, master_key)
    if not (as_old or as_new):
        raise CatalogKeyError("journal nao autenticado")
    return journal, as_old, as_new


def _new_journal(  # noqa: PLR0913 - transaction metadata is deliberately explicit
    *,
    old_revision: int,
    old_digest: str | None,
    new_revision: int,
    new_digest: str,
    old_key: bytes,
    new_key: bytes,
) -> _Journal:
    payload = {
        "format": 1,
        "new_digest": new_digest,
        "new_revision": new_revision,
        "old_digest": old_digest,
        "old_revision": old_revision,
    }
    return _Journal(
        old_revision=old_revision,
        old_digest=old_digest,
        new_revision=new_revision,
        new_digest=new_digest,
        old_auth_tag=catalog_auth_tag(payload, old_key),
        new_auth_tag=catalog_auth_tag(payload, new_key),
    )


class CatalogStore:
    """Catálogo aberto sob locks sidecar e âncora monotônica externa."""

    __slots__ = (
        "_anchor_lock",
        "_anchor_path",
        "_closed",
        "_digest",
        "_hooks",
        "_lifecycle_lock",
        "_master_key",
        "_poisoned",
        "_records",
        "_revision",
        "_store_lock",
        "_store_path",
    )

    def __init__(  # noqa: PLR0913 - the open store state is explicit
        self,
        *,
        store_path: Path,
        anchor_path: Path,
        store_lock: _SidecarLock,
        anchor_lock: _SidecarLock,
        master_key: bytes,
        parsed: _ParsedCatalog,
        hooks: CatalogHooks,
    ) -> None:
        self._store_path = store_path
        self._anchor_path = anchor_path
        self._store_lock = store_lock
        self._anchor_lock = anchor_lock
        self._master_key = master_key
        self._revision = parsed.revision
        self._records = parsed.records
        self._digest = parsed.digest
        self._hooks = hooks
        self._closed = False
        self._poisoned = False
        self._lifecycle_lock = threading.Lock()

    @classmethod
    def open(
        cls,
        store_path: str | Path | None = None,
        *,
        anchor_path: str | Path | None = None,
        master_key: str | bytes | None = None,
        secrets_provider: SecretProvider | None = None,
        hooks: CatalogHooks | None = None,
    ) -> CatalogStore:
        store, anchor = resolve_store_paths(store_path, anchor_path)
        _validate_parent(store.parent, anchor=False)
        _validate_parent(anchor.parent, anchor=True)
        key = _key_from_provider(master_key, secrets_provider)
        effective_hooks = hooks if hooks is not None else CatalogHooks()
        store_lock: _SidecarLock | None = None
        anchor_lock: _SidecarLock | None = None
        try:
            store_lock = _SidecarLock.acquire(
                store.with_name(store.name + _LOCK_SUFFIX), anchor=False
            )
            anchor_lock = _SidecarLock.acquire(
                anchor.with_name(anchor.name + _LOCK_SUFFIX), anchor=True
            )
            plan = _plan_recovery(store, anchor, key)
            if plan is not None:
                _apply_recovery(plan, anchor, effective_hooks)
            parsed = _read_pair(store, anchor, key)
            _cleanup_managed(store.parent)
            _cleanup_managed(anchor.parent)
            return cls(
                store_path=store,
                anchor_path=anchor,
                store_lock=store_lock,
                anchor_lock=anchor_lock,
                master_key=key,
                parsed=parsed,
                hooks=effective_hooks,
            )
        except BaseException:
            if anchor_lock is not None:
                anchor_lock.close()
            if store_lock is not None:
                store_lock.close()
            raise

    @classmethod
    def initialize(
        cls,
        store_path: str | Path | None = None,
        *,
        anchor_path: str | Path | None = None,
        master_key: str | bytes | None = None,
        secrets_provider: SecretProvider | None = None,
        hooks: CatalogHooks | None = None,
    ) -> CatalogStore:
        store, anchor = resolve_store_paths(store_path, anchor_path)
        _validate_parent(store.parent, anchor=False)
        if os.path.lexists(anchor.parent):
            _validate_parent(anchor.parent, anchor=True)
        else:
            _ensure_private_directory(anchor.parent)
        if os.path.lexists(store) or os.path.lexists(anchor):
            raise CatalogAlreadyExistsError("catalogo ja existe")
        key = _key_from_provider(master_key, secrets_provider)
        effective_hooks = hooks if hooks is not None else CatalogHooks()
        store_lock: _SidecarLock | None = None
        anchor_lock: _SidecarLock | None = None
        try:
            store_lock = _SidecarLock.acquire(
                store.with_name(store.name + _LOCK_SUFFIX), anchor=False
            )
            anchor_lock = _SidecarLock.acquire(
                anchor.with_name(anchor.name + _LOCK_SUFFIX), anchor=True
            )
            payload = _make_payload(1, ())
            data = _serialize_document(payload, key)
            parsed = _ParsedCatalog(1, catalog_digest(payload), ())
            journal = _new_journal(
                old_revision=0,
                old_digest=None,
                new_revision=1,
                new_digest=parsed.digest,
                old_key=key,
                new_key=key,
            )
            _persist_transaction(
                store=store,
                anchor=anchor,
                journal=journal,
                data=data,
                new_anchor=_Anchor(1, parsed.digest),
                hooks=effective_hooks,
                backup=None,
                purge_backups=False,
            )
            return cls(
                store_path=store,
                anchor_path=anchor,
                store_lock=store_lock,
                anchor_lock=anchor_lock,
                master_key=key,
                parsed=parsed,
                hooks=effective_hooks,
            )
        except BaseException:
            if anchor_lock is not None:
                anchor_lock.close()
            if store_lock is not None:
                store_lock.close()
            raise

    @classmethod
    def inspect_master_key_rotation(
        cls,
        store_path: str | Path | None = None,
        *,
        anchor_path: str | Path | None = None,
        old_master_key: str | bytes,
        new_master_key: str | bytes,
    ) -> MasterKeyRotationStatus:
        """Determina, sem escrita, qual chave o operador deve configurar.

        Exige as duas chaves: o journal de rotação só é aceito quando a antiga
        autentica o papel antigo e a nova autentica o papel novo; o store precisa
        ser autenticado pela chave do estado que ele representa, a âncora
        precisa coincidir com um dos dois estados do journal e todos os
        segredos precisam abrir com a chave confirmada.
        """
        return cls._rotation_recovery(
            store_path,
            anchor_path=anchor_path,
            old_master_key=old_master_key,
            new_master_key=new_master_key,
            hooks=None,
            apply=False,
        )

    @classmethod
    def recover_master_key_rotation(
        cls,
        store_path: str | Path | None = None,
        *,
        anchor_path: str | Path | None = None,
        old_master_key: str | bytes,
        new_master_key: str | bytes,
        hooks: CatalogHooks | None = None,
    ) -> MasterKeyRotationStatus:
        """Recuperação explícita e idempotente de uma rotação interrompida.

        Aplica somente a conclusão já determinada pelos arquivos autenticados:
        descarta a intenção (old/old), avança a âncora (new/old) ou remove o
        journal (new/new). Nunca faz rollback do store nem aceita as duas chaves
        depois de retornar. Repetir a chamada devolve o mesmo resultado.
        """
        return cls._rotation_recovery(
            store_path,
            anchor_path=anchor_path,
            old_master_key=old_master_key,
            new_master_key=new_master_key,
            hooks=hooks,
            apply=True,
        )

    @classmethod
    def _rotation_recovery(  # noqa: PLR0913 - explicit recovery inputs
        cls,
        store_path: str | Path | None,
        *,
        anchor_path: str | Path | None,
        old_master_key: str | bytes,
        new_master_key: str | bytes,
        hooks: CatalogHooks | None,
        apply: bool,
    ) -> MasterKeyRotationStatus:
        store, anchor = resolve_store_paths(store_path, anchor_path)
        _validate_parent(store.parent, anchor=False)
        _validate_parent(anchor.parent, anchor=True)
        try:
            old_key = validate_master_key(old_master_key)
            new_key = validate_master_key(new_master_key)
        except ValueError:
            raise MasterKeyError("master key ausente ou invalida") from None
        if hmac.compare_digest(old_key, new_key):
            raise MasterKeyError("chaves de rotacao devem ser distintas")
        effective_hooks = hooks if hooks is not None else CatalogHooks()
        store_lock: _SidecarLock | None = None
        anchor_lock: _SidecarLock | None = None
        try:
            store_lock = _SidecarLock.acquire(
                store.with_name(store.name + _LOCK_SUFFIX), anchor=False
            )
            anchor_lock = _SidecarLock.acquire(
                anchor.with_name(anchor.name + _LOCK_SUFFIX), anchor=True
            )
            determination = _determine_rotation(store, anchor, old_key, new_key)
            if not apply or determination.plan is None:
                return determination.status
            _apply_recovery(determination.plan, anchor, effective_hooks)
            confirmed = _read_pair(store, anchor, determination.confirmed_key)
            if _state_of(confirmed) != _state_of(determination.confirmed):
                raise CatalogAnchorError("store e ancora divergentes")
            _cleanup_managed(store.parent)
            _cleanup_managed(anchor.parent)
            return MasterKeyRotationStatus(
                confirmed_key=determination.status.confirmed_key,
                catalog_revision=confirmed.revision,
                journal_pending=False,
            )
        finally:
            if anchor_lock is not None:
                anchor_lock.close()
            if store_lock is not None:
                store_lock.close()

    @property
    def closed(self) -> bool:
        with self._lifecycle_lock:
            return self._closed

    @property
    @_serialized_operation
    def revision(self) -> int:
        return self._revision

    @property
    def store_path(self) -> Path:
        return self._store_path

    @property
    def anchor_path(self) -> Path:
        return self._anchor_path

    @_serialized_operation
    def snapshot(self) -> CatalogSnapshot:
        return CatalogSnapshot(self._revision, self._records, self._digest)

    @_serialized_operation
    def get(self, datasource_id: str) -> DatasourceRecord:
        return self._get_record(datasource_id)

    @_serialized_operation
    def by_alias(self, alias: str) -> DatasourceRecord:
        validate_alias(alias)
        for record in self._records:
            if record.alias == alias:
                return record
        raise CatalogStoreError("datasource nao encontrado")

    @_serialized_operation
    def read_upstream_secret(self, datasource_id: str) -> str:
        """Primitiva interna explícita; não é usada por snapshots/respostas."""
        return self._read_upstream_secret(self._get_record(datasource_id))

    def _get_record(self, datasource_id: str) -> DatasourceRecord:
        validate_datasource_id(datasource_id)
        for record in self._records:
            if record.id == datasource_id:
                return record
        raise CatalogStoreError("datasource nao encontrado")

    def _read_upstream_secret(self, record: DatasourceRecord) -> str:
        try:
            return open_secret(
                record._upstream_secret,
                master_key=self._master_key,
                datasource_id=record.id,
                schema_version=CATALOG_SCHEMA_VERSION,
                revision=record.revision,
            )
        except ValueError:
            raise CatalogKeyError("segredo indisponivel") from None

    @_serialized_operation
    def create(
        self,
        draft: DatasourceDraft,
        upstream_secret: str,
        *,
        expected_revision: int | None = None,
        resolver: Callable[[str, int], Sequence[str]] | None = None,
    ) -> DatasourceRecord:
        self._ensure_open()
        self._check_revision(expected_revision)
        if any(record.alias == draft.alias for record in self._records):
            raise CatalogStoreError("alias ja existe")
        resolved = resolve_destination(
            draft.host,
            draft.port,
            policy=draft.destination_policy,
            resolver=resolver,
            expected_addresses=draft.resolved_addresses or None,
        )
        datasource_id = new_datasource_id()
        record_revision = 1
        envelope = seal_secret(
            upstream_secret,
            master_key=self._master_key,
            datasource_id=datasource_id,
            schema_version=CATALOG_SCHEMA_VERSION,
            revision=record_revision,
        )
        record = DatasourceRecord(
            id=datasource_id,
            alias=draft.alias,
            display_name=draft.display_name,
            enabled=draft.enabled,
            host=draft.host,
            port=draft.port,
            database=draft.database,
            username=draft.username,
            tls=draft.tls,
            policy=draft.policy,
            limits=draft.limits,
            destination_policy=draft.destination_policy,
            resolved_addresses=resolved.addresses,
            revision=record_revision,
            last_test=LastTest(),
            _upstream_secret=envelope,
        )
        self._commit((*self._records, record), expected_revision=self._revision)
        return record

    @_serialized_operation
    def update(
        self,
        datasource_id: str,
        draft: DatasourceDraft,
        *,
        expected_revision: int,
        resolver: Callable[[str, int], Sequence[str]] | None = None,
    ) -> DatasourceRecord:
        self._ensure_open()
        self._check_revision(expected_revision)
        current = self._get_record(datasource_id)
        if any(
            record.alias == draft.alias and record.id != datasource_id for record in self._records
        ):
            raise CatalogStoreError("alias ja existe")
        resolved = resolve_destination(
            draft.host,
            draft.port,
            policy=draft.destination_policy,
            resolver=resolver,
            expected_addresses=draft.resolved_addresses or None,
        )
        next_record_revision = current.revision + 1
        updated = DatasourceRecord(
            id=current.id,
            alias=draft.alias,
            display_name=draft.display_name,
            enabled=draft.enabled,
            host=draft.host,
            port=draft.port,
            database=draft.database,
            username=draft.username,
            tls=draft.tls,
            policy=draft.policy,
            limits=draft.limits,
            destination_policy=draft.destination_policy,
            resolved_addresses=resolved.addresses,
            revision=next_record_revision,
            last_test=LastTest(),
            _upstream_secret=seal_secret(
                self._read_upstream_secret(current),
                master_key=self._master_key,
                datasource_id=current.id,
                schema_version=CATALOG_SCHEMA_VERSION,
                revision=next_record_revision,
            ),
        )
        self._commit(
            tuple(updated if record.id == current.id else record for record in self._records),
            expected_revision=expected_revision,
        )
        return updated

    @_serialized_operation
    def rotate_secret(
        self,
        datasource_id: str,
        upstream_secret: str,
        *,
        expected_revision: int,
    ) -> DatasourceRecord:
        self._ensure_open()
        self._check_revision(expected_revision)
        current = self._get_record(datasource_id)
        updated = DatasourceRecord(
            id=current.id,
            alias=current.alias,
            display_name=current.display_name,
            enabled=current.enabled,
            host=current.host,
            port=current.port,
            database=current.database,
            username=current.username,
            tls=current.tls,
            policy=current.policy,
            limits=current.limits,
            destination_policy=current.destination_policy,
            resolved_addresses=current.resolved_addresses,
            revision=current.revision + 1,
            last_test=LastTest(),
            _upstream_secret=seal_secret(
                upstream_secret,
                master_key=self._master_key,
                datasource_id=current.id,
                schema_version=CATALOG_SCHEMA_VERSION,
                revision=current.revision + 1,
            ),
        )
        self._commit(
            tuple(updated if record.id == current.id else record for record in self._records),
            expected_revision=expected_revision,
        )
        return updated

    @_serialized_operation
    def rotate_master_key(self, new_master_key: str | bytes) -> CatalogSnapshot:
        try:
            new_key = validate_master_key(new_master_key)
        except ValueError:
            raise MasterKeyError("nova master key invalida") from None
        records: list[DatasourceRecord] = []
        for current in self._records:
            plaintext = self._read_upstream_secret(current)
            records.append(
                DatasourceRecord(
                    id=current.id,
                    alias=current.alias,
                    display_name=current.display_name,
                    enabled=current.enabled,
                    host=current.host,
                    port=current.port,
                    database=current.database,
                    username=current.username,
                    tls=current.tls,
                    policy=current.policy,
                    limits=current.limits,
                    destination_policy=current.destination_policy,
                    resolved_addresses=current.resolved_addresses,
                    revision=current.revision + 1,
                    last_test=current.last_test,
                    _upstream_secret=seal_secret(
                        plaintext,
                        master_key=new_key,
                        datasource_id=current.id,
                        schema_version=CATALOG_SCHEMA_VERSION,
                        revision=current.revision + 1,
                    ),
                )
            )
        self._commit(tuple(records), expected_revision=self._revision, new_key=new_key)
        self._master_key = new_key
        return CatalogSnapshot(self._revision, self._records, self._digest)

    @_serialized_operation
    def remove(self, datasource_id: str, *, expected_revision: int) -> None:
        self._check_revision(expected_revision)
        self._get_record(datasource_id)
        self._commit(
            tuple(record for record in self._records if record.id != datasource_id),
            expected_revision=expected_revision,
        )

    @_serialized_operation
    def validate_destination(
        self,
        datasource_id: str,
        *,
        resolver: Callable[[str, int], Sequence[str]] | None = None,
    ) -> tuple[str, ...]:
        record = self._get_record(datasource_id)
        return resolve_destination(
            record.host,
            record.port,
            policy=record.destination_policy,
            resolver=resolver,
            expected_addresses=record.resolved_addresses,
        ).addresses

    def _check_revision(self, expected_revision: int | None) -> None:
        if expected_revision is not None and expected_revision != self._revision:
            raise CatalogRevisionConflictError("revision do catalogo divergiu")

    def _commit(
        self,
        records: Sequence[DatasourceRecord],
        *,
        expected_revision: int,
        new_key: bytes | None = None,
    ) -> None:
        if expected_revision != self._revision:
            raise CatalogRevisionConflictError("revision do catalogo divergiu")
        key = self._master_key if new_key is None else new_key
        new_revision = self._revision + 1
        payload = _make_payload(new_revision, records)
        data = _serialize_document(payload, key)
        new_digest = catalog_digest(payload)
        journal = _new_journal(
            old_revision=self._revision,
            old_digest=self._digest,
            new_revision=new_revision,
            new_digest=new_digest,
            old_key=self._master_key,
            new_key=key,
        )
        try:
            old_data = _read_optional(self._store_path, anchor=False)
            if old_data is None:
                raise CatalogWriteError("store do catalogo ausente")
            _persist_transaction(
                store=self._store_path,
                anchor=self._anchor_path,
                journal=journal,
                data=data,
                new_anchor=_Anchor(new_revision, new_digest),
                hooks=self._hooks,
                backup=(old_data, self._revision),
                purge_backups=not hmac.compare_digest(key, self._master_key),
            )
        except BaseException:
            self._poisoned = True
            raise
        _cleanup_managed(self._store_path.parent)
        self._records = tuple(sorted(records, key=lambda record: record.id))
        self._revision = new_revision
        self._digest = new_digest

    def _ensure_open(self) -> None:
        if self._closed:
            raise CatalogStoreError("catalogo encerrado")
        if self._poisoned:
            raise CatalogWriteError("catalogo requer reabertura apos falha de persistencia")

    def close(self) -> None:
        with self._lifecycle_lock:
            if self._closed:
                return
            self._closed = True
            self._anchor_lock.close()
            self._store_lock.close()

    def __enter__(self) -> CatalogStore:
        with self._lifecycle_lock:
            self._ensure_open()
            return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        with self._lifecycle_lock:
            return f"CatalogStore(revision={self._revision}, datasources={len(self._records)})"


def _read_optional(path: Path, *, anchor: bool) -> bytes | None:
    if not os.path.lexists(path):
        return None
    expected = _validate_regular(path, anchor=anchor)
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY | _BINARY | _NOFOLLOW)
        opened = os.fstat(descriptor)
        if opened.st_dev != expected.st_dev or opened.st_ino != expected.st_ino:
            raise OSError(errno.EPERM, "changed")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    except (OSError, ValueError):
        raise FilesystemPolicyError("arquivo do catalogo ilegivel") from None
    finally:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)


def _read_pair(store: Path, anchor: Path, key: bytes) -> _ParsedCatalog:
    store_data = _read_optional(store, anchor=False)
    anchor_data = _read_optional(anchor, anchor=True)
    if store_data is None or anchor_data is None:
        raise CatalogAnchorError("store e ancora devem existir")
    try:
        parsed = _parse_catalog(store_data, key)
    except CatalogKeyError:
        raise
    except CatalogCorruptError:
        raise
    parsed_anchor = _parse_anchor(anchor_data)
    if parsed.revision != parsed_anchor.revision or parsed.digest != parsed_anchor.digest:
        raise CatalogAnchorError("store e ancora divergentes")
    return parsed


_State = tuple[int, str]


@dataclass(frozen=True, slots=True)
class _RecoveryPlan:
    """Mutação de recuperação decidida só depois de autenticar e reconciliar."""

    journal_path: Path
    advance_anchor: _Anchor | None
    purge_backups_in: Path | None = None


@dataclass(frozen=True, slots=True)
class _RotationDetermination:
    status: MasterKeyRotationStatus
    confirmed: _ParsedCatalog
    confirmed_key: bytes
    plan: _RecoveryPlan | None


def _state_of(parsed: _ParsedCatalog | _Anchor) -> _State:
    return parsed.revision, parsed.digest


def _journal_states(journal: _Journal) -> tuple[_State | None, _State]:
    old_state = (
        None if journal.old_revision == 0 else (journal.old_revision, cast(str, journal.old_digest))
    )
    return old_state, (journal.new_revision, journal.new_digest)


def _authenticated_or_none(data: bytes, key: bytes) -> _ParsedCatalog | None:
    """Catálogo autenticado pela chave, ou ``None`` se a chave não o autentica.

    Corrupção estrutural continua falhando fechada; somente a falha de
    autenticação vira ``None``. Nunca há leitura não autenticada.
    """
    try:
        return _parse_catalog(data, key)
    except CatalogKeyError:
        return None


def _optional_anchor_state(anchor: Path) -> _State | None:
    data = _read_optional(anchor, anchor=True)
    return None if data is None else _state_of(_parse_anchor(data))


def _plan_recovery(store: Path, anchor: Path, key: bytes) -> _RecoveryPlan | None:
    """Decide a recuperação de ``open`` sem nenhuma escrita.

    Journal, store e âncora são autenticados/reconciliados antes de qualquer
    mutação. Uma chave que não autentica o estado do store nunca consome o
    journal nem avança a âncora.
    """
    journal_path = anchor.with_name(_JOURNAL_NAME)
    journal_data = _read_optional(journal_path, anchor=True)
    if journal_data is None:
        return None
    journal, as_old, as_new = _parse_journal(journal_data, key)
    old_state, new_state = _journal_states(journal)
    store_data = _read_optional(store, anchor=False)
    anchor_state = _optional_anchor_state(anchor)
    if _is_rotation_journal(journal):
        return _plan_rotation_with_single_key(
            journal_path,
            store.parent,
            store_data,
            anchor_state,
            key,
            old_state=old_state,
            new_state=new_state,
            as_old=as_old,
            as_new=as_new,
        )
    store_state = None if store_data is None else _state_of(_parse_catalog(store_data, key))
    # (store, âncora) -> âncora a gravar. old/old descarta a intenção, new/old
    # conclui a âncora e new/new só limpa o journal. Com ``old_state is None``
    # (inicialização) o estado antigo é a ausência dos dois arquivos.
    allowed: dict[tuple[_State | None, _State | None], _Anchor | None] = {
        (old_state, old_state): None,
        (new_state, old_state): _Anchor(*new_state),
        (new_state, new_state): None,
    }
    pair = (store_state, anchor_state)
    if pair not in allowed:
        raise CatalogAnchorError("journal e arquivos do catalogo incoerentes")
    return _RecoveryPlan(journal_path, allowed[pair])


def _plan_rotation_with_single_key(  # noqa: PLR0913 - reconciled state is explicit
    journal_path: Path,
    store_directory: Path,
    store_data: bytes | None,
    anchor_state: _State | None,
    key: bytes,
    *,
    old_state: _State | None,
    new_state: _State,
    as_old: bool,
    as_new: bool,
) -> _RecoveryPlan:
    """Uma chave só completa a rotação quando o resultado já não é incerto.

    - old/old aberto com a chave antiga: o store nunca foi substituído; a
      intenção é descartada e a chave antiga continua válida.
    - new/new aberto com a chave nova: a âncora já confirmou o commit; restam
      a remoção dos backups da chave anterior e a do journal, nessa ordem.
    - new/old, ou qualquer chave que não autentique o estado do store: o
      resultado é incerto para quem recebeu o erro, e a determinação exige a
      recuperação explícita com as duas chaves. Nada é alterado.
    """
    parsed = None if store_data is None else _authenticated_or_none(store_data, key)
    if parsed is not None and old_state is not None:
        store_state = _state_of(parsed)
        if as_old and store_state == old_state and anchor_state == old_state:
            return _RecoveryPlan(journal_path, None)
        if as_new and store_state == new_state and anchor_state == new_state:
            return _RecoveryPlan(journal_path, None, purge_backups_in=store_directory)
    raise CatalogRotationPendingError(
        "rotacao de master key pendente; determine o resultado com as chaves antiga e nova"
    )


def _apply_recovery(plan: _RecoveryPlan, anchor: Path, hooks: CatalogHooks) -> None:
    if plan.advance_anchor is not None:
        _atomic_write(anchor, _anchor_bytes(plan.advance_anchor), hooks, "anchor")
    if plan.purge_backups_in is not None:
        _purge_rotated_backups(plan.purge_backups_in, hooks)
    _remove_journal(plan.journal_path, hooks)


def _verify_secrets(parsed: _ParsedCatalog, key: bytes) -> None:
    """Prova em memória que a chave confirmada abre todos os segredos."""
    for record in parsed.records:
        try:
            open_secret(
                record._upstream_secret,
                master_key=key,
                datasource_id=record.id,
                schema_version=CATALOG_SCHEMA_VERSION,
                revision=record.revision,
            )
        except ValueError:
            raise CatalogKeyError("segredo indisponivel") from None


def _determine_rotation(
    store: Path,
    anchor: Path,
    old_key: bytes,
    new_key: bytes,
) -> _RotationDetermination:
    """Determina, sem escrita, qual chave autentica o estado confirmado."""
    journal_path = anchor.with_name(_JOURNAL_NAME)
    journal_data = _read_optional(journal_path, anchor=True)
    store_data = _read_optional(store, anchor=False)
    anchor_data = _read_optional(anchor, anchor=True)
    if store_data is None or anchor_data is None:
        raise CatalogAnchorError("store e ancora devem existir")
    anchor_state = _state_of(_parse_anchor(anchor_data))
    by_old = _authenticated_or_none(store_data, old_key)
    by_new = _authenticated_or_none(store_data, new_key)
    if by_old is not None and by_new is not None:
        raise CatalogAnchorError("catalogo autenticado por duas chaves")
    if journal_data is None:
        return _determine_without_journal(anchor_state, by_old, by_new, old_key, new_key)
    journal = _parse_journal_document(journal_data)
    old_roles = _journal_roles(journal, old_key)
    new_roles = _journal_roles(journal, new_key)
    if not _is_rotation_journal(journal):
        if any(old_roles) or any(new_roles):
            raise CatalogAnchorError("journal pendente nao pertence a uma rotacao")
        raise CatalogKeyError("journal nao autenticado")
    if not (old_roles[0] and new_roles[1]):
        raise CatalogKeyError("journal nao autenticado pelas duas chaves")
    old_state, new_state = _journal_states(journal)
    if old_state is None:
        raise CatalogAnchorError("journal e arquivos do catalogo incoerentes")
    if by_old is not None and _state_of(by_old) == old_state:
        role: Literal["old", "new"] = "old"
        confirmed, key = by_old, old_key
    elif by_new is not None and _state_of(by_new) == new_state:
        role = "new"
        confirmed, key = by_new, new_key
    else:
        raise CatalogAnchorError("journal e arquivos do catalogo incoerentes")
    # Store antigo com âncora nova seria regressão: nunca é aceito.
    transitions = {
        ("old", old_state): None,
        ("new", old_state): _Anchor(*new_state),
        ("new", new_state): None,
    }
    if (role, anchor_state) not in transitions:
        raise CatalogAnchorError("journal e arquivos do catalogo incoerentes")
    _verify_secrets(confirmed, key)
    status = MasterKeyRotationStatus(
        confirmed_key=role,
        catalog_revision=confirmed.revision,
        journal_pending=True,
    )
    plan = _RecoveryPlan(
        journal_path,
        transitions[(role, anchor_state)],
        purge_backups_in=store.parent if role == "new" else None,
    )
    return _RotationDetermination(status, confirmed, key, plan)


def _determine_without_journal(
    anchor_state: _State,
    by_old: _ParsedCatalog | None,
    by_new: _ParsedCatalog | None,
    old_key: bytes,
    new_key: bytes,
) -> _RotationDetermination:
    """Par sem journal: a chave confirmada é a que autentica store e âncora."""
    if by_old is not None:
        role: Literal["old", "new"] = "old"
        confirmed, key = by_old, old_key
    elif by_new is not None:
        role = "new"
        confirmed, key = by_new, new_key
    else:
        raise CatalogKeyError("nenhuma das chaves autentica o catalogo")
    if _state_of(confirmed) != anchor_state:
        raise CatalogAnchorError("store e ancora divergentes")
    _verify_secrets(confirmed, key)
    status = MasterKeyRotationStatus(
        confirmed_key=role,
        catalog_revision=confirmed.revision,
        journal_pending=False,
    )
    return _RotationDetermination(status, confirmed, key, None)


def _persist_transaction(  # noqa: PLR0913 - the commit protocol is explicit
    *,
    store: Path,
    anchor: Path,
    journal: _Journal,
    data: bytes,
    new_anchor: _Anchor,
    hooks: CatalogHooks,
    backup: tuple[bytes, int] | None,
    purge_backups: bool,
) -> None:
    """Executa o protocolo journal → backup → store → âncora → limpeza.

    Em uma rotação de master key (``purge_backups``), todos os backups
    gerenciados são anteriores à rotação e, portanto, cifrados com chaves
    anteriores. Eles são preservados até o ponto de commit (âncora nova
    durável) e removidos, com verificação, antes do journal.

    Falhas antes de tentar o replace do store preservam o par antigo e mantêm a
    categoria original. A partir da tentativa de replace, o store pode já ser o
    novo: qualquer falha vira ``CatalogOutcomeUncertainError`` com texto fixo.
    A recuperação decide depois pelo trio autenticado journal/store/âncora.
    """
    replace_attempted = False

    def mark_replace_attempted() -> None:
        nonlocal replace_attempted
        replace_attempted = True

    outcome_uncertain = False
    try:
        _atomic_write(anchor.with_name(_JOURNAL_NAME), _journal_bytes(journal), hooks, "journal")
        if backup is not None:
            _write_backup(store.parent, backup[0], backup[1])
        _atomic_write(store, data, hooks, "store", on_replace=mark_replace_attempted)
        _atomic_write(anchor, _anchor_bytes(new_anchor), hooks, "anchor")
        if purge_backups:
            _purge_rotated_backups(store.parent, hooks)
        _remove_journal(anchor.with_name(_JOURNAL_NAME), hooks)
    except Exception:
        if not replace_attempted:
            raise
        outcome_uncertain = True
    if outcome_uncertain:
        # Levantado fora do ``except``: nem ``__cause__`` nem ``__context__``
        # carregam a exceção original (D-017).
        raise CatalogOutcomeUncertainError(
            "resultado da persistencia incerto; reabra ou recupere explicitamente"
        )


def _managed_backups(parent: Path) -> list[Path]:
    """Backups gerenciados: nome estrito do protocolo e arquivo regular.

    Symlinks, diretórios e nomes desconhecidos nunca são incluídos.
    """
    try:
        names = sorted(entry.name for entry in os.scandir(parent))
    except OSError:
        raise CatalogWriteError("diretorio do catalogo ilegivel") from None
    backups: list[Path] = []
    for name in names:
        if _BACKUP_RE.fullmatch(name) is None:
            continue
        path = parent / name
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise CatalogWriteError("diretorio do catalogo ilegivel") from None
        if stat.S_ISREG(info.st_mode):
            backups.append(path)
    return backups


def _purge_rotated_backups(parent: Path, hooks: CatalogHooks) -> None:
    """Remove os backups gerenciados depois do ponto de commit de uma rotação.

    Todo backup presente é anterior à rotação e está cifrado com uma chave
    anterior. A remoção é seletiva (``_managed_backups``), o diretório é
    sincronizado no POSIX e o resultado é conferido por nova varredura. Qualquer
    falha levanta erro antes da remoção do journal, que continua sendo a prova
    para a recuperação. Remover cópias locais não revoga cópias já obtidas por
    terceiros: isso exige trocar as credenciais upstream.
    """
    _validate_parent(parent, anchor=False)
    for path in _managed_backups(parent):
        try:
            hooks.remove(os.fspath(path))
        except FileNotFoundError:
            continue
        except OSError:
            raise CatalogWriteError("falha ao remover backups da chave anterior") from None
    if os.name == "posix":
        try:
            directory = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | _NOFOLLOW)
            try:
                hooks.directory_fsync(directory)
            finally:
                os.close(directory)
        except OSError:
            raise CatalogWriteError("falha ao remover backups da chave anterior") from None
    if _managed_backups(parent):
        raise CatalogWriteError("backups da chave anterior permanecem")
    hooks.after_point(CrashPoint.AFTER_BACKUP_PURGE)


def _remove_journal(path: Path, hooks: CatalogHooks) -> None:
    """Remove o journal somente depois da âncora durável, com erro explícito.

    Diferente da limpeza seletiva, falhar aqui não é silencioso: um journal que
    permanece é estado de recuperação, não lixo.
    """
    try:
        info = path.lstat()
    except FileNotFoundError:
        info = None
    except OSError:
        raise CatalogWriteError("falha ao remover journal") from None
    if info is not None:
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise FilesystemPolicyError("journal inseguro")
        try:
            path.unlink()
        except OSError:
            raise CatalogWriteError("falha ao remover journal") from None
        if os.name == "posix":
            try:
                directory = os.open(
                    path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | _NOFOLLOW
                )
                try:
                    hooks.directory_fsync(directory)
                finally:
                    os.close(directory)
            except OSError:
                raise CatalogWriteError("falha ao remover journal") from None
    hooks.after_point(CrashPoint.AFTER_JOURNAL_CLEANUP)


def _atomic_write(  # noqa: PLR0912, PLR0915 - each branch is a crash-safe boundary
    path: Path,
    data: bytes,
    hooks: CatalogHooks,
    kind: str,
    *,
    on_replace: Callable[[], None] | None = None,
) -> None:
    parent = path.parent
    _validate_parent(parent, anchor=kind in {"anchor", "journal"})
    if os.path.lexists(path):
        _validate_regular(path, anchor=kind in {"anchor", "journal"})
    token = hooks.temp_token()
    if not isinstance(token, str) or re.fullmatch(r"[0-9a-f]{16}", token) is None:
        raise CatalogWriteError("token temporario invalido")
    prefix = ".datasources.anchor.txn.tmp" if kind == "journal" else ".datasources.store.tmp"
    temp = parent / f"{prefix}.{os.getpid()}.{token}"
    descriptor = -1
    try:
        descriptor = os.open(
            temp,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | _BINARY | _NOFOLLOW,
            _PRIVATE_MODE,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = -1
            written = stream.write(data)
            stream.flush()
            hooks.file_fsync(stream.fileno())
        if written != len(data):
            raise OSError(errno.EIO, "short write")
        if on_replace is not None:
            on_replace()
        hooks.replace(os.fspath(temp), os.fspath(path))
        if os.name == "posix":
            directory = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | _NOFOLLOW)
            try:
                hooks.directory_fsync(directory)
            finally:
                os.close(directory)
            if kind == "store":
                hooks.after_point(CrashPoint.AFTER_STORE_DIRECTORY_FSYNC)
            elif kind == "anchor":
                hooks.after_point(CrashPoint.AFTER_ANCHOR_DIRECTORY_FSYNC)
        elif kind == "store":
            hooks.after_point(CrashPoint.AFTER_STORE_DIRECTORY_FSYNC)
        elif kind == "anchor":
            hooks.after_point(CrashPoint.AFTER_ANCHOR_DIRECTORY_FSYNC)
        if kind == "journal":
            hooks.after_point(CrashPoint.AFTER_JOURNAL_FSYNC)
        elif kind == "store":
            hooks.after_point(CrashPoint.AFTER_STORE_REPLACE)
        else:
            hooks.after_point(CrashPoint.AFTER_ANCHOR_REPLACE)
    except BaseException as exc:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        _remove_managed(temp)
        if isinstance(exc, (CatalogStoreError, KeyboardInterrupt, SystemExit, GeneratorExit)):
            raise
        raise CatalogWriteError("falha ao persistir catalogo") from None


def _write_backup(parent: Path, data: bytes, revision: int) -> None:
    _validate_parent(parent, anchor=False)
    path = parent / f"datasources.store.bak.{revision}"
    if os.path.lexists(path):
        _validate_regular(path, anchor=False)
        return
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | _BINARY | _NOFOLLOW,
            _PRIVATE_MODE,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = -1
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        raise CatalogWriteError("backup do catalogo ja existe") from None
    except BaseException:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        _remove_managed(path)
        raise CatalogWriteError("falha no backup do catalogo") from None


def _remove_managed(path: Path) -> None:
    is_managed = (
        _TEMP_RE.fullmatch(path.name) is not None
        or _JOURNAL_TEMP_RE.fullmatch(path.name) is not None
        or _BACKUP_RE.fullmatch(path.name) is not None
    )
    if not is_managed:
        return
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    except OSError:
        return
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        return
    with suppress(OSError):
        path.unlink()


def _cleanup_managed(parent: Path) -> None:
    entries: list[Path] = []
    try:
        entries = [parent / entry.name for entry in os.scandir(parent)]
    except OSError:
        return
    backups: list[tuple[int, Path]] = []
    for path in entries:
        if _TEMP_RE.fullmatch(path.name) or _JOURNAL_TEMP_RE.fullmatch(path.name):
            _remove_managed(path)
        match = _BACKUP_RE.fullmatch(path.name)
        if match is not None:
            with suppress(ValueError):
                backups.append((int(path.name.rsplit(".", 1)[1]), path))
    for _revision, path in sorted(backups, reverse=True)[3:]:
        _remove_managed(path)
