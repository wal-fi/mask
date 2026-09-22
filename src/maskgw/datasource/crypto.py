"""Primitivas criptograficas fechadas do catalogo da Etapa 2."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from collections.abc import Mapping
from typing import Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from maskgw.datasource.models import EncryptedSecret, encode_b64

MASTER_KEY_ENV: Final = "MASKGW_DATASOURCE_MASTER_KEY"
CATALOG_FORMAT: Final = 1
CATALOG_SCHEMA_VERSION: Final = 1
SECRET_FIELD: Final = "upstream_secret"  # noqa: S105 - fixed envelope field name
_NONCE_BYTES: Final = 12
_KEY_BYTES: Final = 32
_MASTER_KEY_HEX_LENGTH: Final = _KEY_BYTES * 2
_AUTH_TAG_HEX_LENGTH: Final = 64
_AUTH_INFO: Final = b"maskgw-datasource-catalog-auth-v1"


class CryptoValidationError(ValueError):
    """Entrada criptografica ausente ou invalida, sem detalhes sensiveis."""

    def __init__(self, message: str = "material criptografico invalido") -> None:
        super().__init__(message)


def validate_master_key(value: str | bytes | None) -> bytes:
    """Valida a chave canonica: 64 hex ASCII, exatamente 32 bytes."""
    if isinstance(value, bytes):
        candidate = value
    elif isinstance(value, str):
        if len(value) != _MASTER_KEY_HEX_LENGTH or any(
            char not in "0123456789abcdefABCDEF" for char in value
        ):
            raise CryptoValidationError("chave-mestra invalida")
        try:
            candidate = bytes.fromhex(value)
        except ValueError:
            raise CryptoValidationError("chave-mestra invalida") from None
    else:
        raise CryptoValidationError("chave-mestra ausente")
    if len(candidate) != _KEY_BYTES:
        raise CryptoValidationError("chave-mestra invalida")
    return candidate


def canonical_json(value: Mapping[str, object]) -> bytes:
    """Serializa sem espacos, ordem estavel e sem numeros NaN/Infinity."""
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        raise CryptoValidationError("payload canonico invalido") from None
    return text.encode("utf-8")


def catalog_digest(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def _auth_key(master_key: bytes) -> bytes:
    try:
        return HKDF(
            algorithm=hashes.SHA256(),
            length=_KEY_BYTES,
            salt=None,
            info=_AUTH_INFO,
        ).derive(validate_master_key(master_key))
    except (TypeError, ValueError):
        raise CryptoValidationError("chave-mestra invalida") from None


def catalog_auth_tag(payload: Mapping[str, object], master_key: bytes) -> str:
    key = _auth_key(master_key)
    return hmac.new(key, canonical_json(payload), hashlib.sha256).hexdigest()


def verify_catalog_auth(payload: Mapping[str, object], tag: object, master_key: bytes) -> None:
    if not isinstance(tag, str) or len(tag) != _AUTH_TAG_HEX_LENGTH:
        raise CryptoValidationError("autenticacao do catalogo invalida")
    expected = catalog_auth_tag(payload, master_key)
    if not hmac.compare_digest(expected, tag):
        raise CryptoValidationError("autenticacao do catalogo invalida")


def _aad(datasource_id: str, *, field: str, schema_version: int, revision: int) -> bytes:
    return canonical_json(
        {
            "datasource_id": datasource_id,
            "field": field,
            "revision": revision,
            "schema_version": schema_version,
        }
    )


def seal_secret(  # noqa: PLR0913 - AAD fields are deliberately explicit
    plaintext: str,
    *,
    master_key: bytes,
    datasource_id: str,
    schema_version: int,
    revision: int,
    field: str = SECRET_FIELD,
) -> EncryptedSecret:
    if not isinstance(plaintext, str) or not plaintext:
        raise CryptoValidationError("segredo ausente")
    key = validate_master_key(master_key)
    nonce = secrets.token_bytes(_NONCE_BYTES)
    try:
        ciphertext = AESGCM(key).encrypt(
            nonce,
            plaintext.encode("utf-8"),
            _aad(datasource_id, field=field, schema_version=schema_version, revision=revision),
        )
    except (TypeError, ValueError, UnicodeError):
        raise CryptoValidationError("falha ao cifrar segredo") from None
    return EncryptedSecret(
        algorithm="AES-256-GCM",
        version=1,
        nonce=nonce,
        ciphertext=ciphertext,
    )


def open_secret(  # noqa: PLR0913 - AAD fields are deliberately explicit
    envelope: EncryptedSecret,
    *,
    master_key: bytes,
    datasource_id: str,
    schema_version: int,
    revision: int,
    field: str = SECRET_FIELD,
) -> str:
    key = validate_master_key(master_key)
    try:
        plaintext = (
            AESGCM(key)
            .decrypt(
                envelope.nonce,
                envelope.ciphertext,
                _aad(datasource_id, field=field, schema_version=schema_version, revision=revision),
            )
            .decode("utf-8")
        )
    except (InvalidTag, TypeError, ValueError, UnicodeError):
        # InvalidTag não deriva de ValueError: sem ela, tag, chave ou AAD
        # divergentes escapariam como exceção crua da biblioteca.
        raise CryptoValidationError("segredo indisponivel") from None
    if not plaintext:
        raise CryptoValidationError("segredo indisponivel")
    return plaintext


def envelope_to_json(envelope: EncryptedSecret) -> dict[str, object]:
    return {
        "algorithm": envelope.algorithm,
        "ciphertext": encode_b64(envelope.ciphertext),
        "nonce": encode_b64(envelope.nonce),
        "version": envelope.version,
    }
