"""Framing limitado do startup PostgreSQL 3.0 (D-109).

Funcoes puras sobre bytes: nenhuma toca socket. Quem le do fio valida o
comprimento declarado com `initial_length`/`message_length` ANTES de alocar o
corpo. Qualquer forma fora do perfil minimo e recusa deterministica, nunca
negociacao nem encaminhamento.

Perfil (D-109, escolhido sob delegacao):

- protocolo 3.0 exato; SSLRequest de exatamente 8 bytes;
- GSSENCRequest, CancelRequest, versao menor != 0 e opcoes `_pq_.` recusados;
- StartupMessage so com `user`, `database`, `application_name` e
  `client_encoding` (este so UTF-8); nenhum abre efeito de sessao;
- pacote inicial de 8 a 10.000 bytes, ate 32 pares, chave <= 63 bytes,
  valor <= 256 bytes, UTF-8 estrito, sem duplicatas;
- mensagens SASL do cliente com no maximo 2.048 bytes.

O alias (`database`) invalido ou ausente NAO falha aqui: e decidido depois da
prova SCRAM, com a mesma falha de autenticacao de usuario e senha errados.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NoReturn

from maskgw.pgwire.errors import PgwireErrorCategory, PgwireStartupError

LENGTH_BYTES: Final = 4
TYPED_HEADER_BYTES: Final = 5
MIN_INITIAL_PACKET: Final = 8
MAX_INITIAL_PACKET: Final = 10_000
MAX_STARTUP_PAIRS: Final = 32
MAX_KEY_BYTES: Final = 63
MAX_VALUE_BYTES: Final = 256
MAX_SASL_MESSAGE: Final = 2_048
MAX_MECHANISM_NAME: Final = 32

PROTOCOL_3_0: Final = 196608
SSL_REQUEST_CODE: Final = 80877103
GSSENC_REQUEST_CODE: Final = 80877104
CANCEL_REQUEST_CODE: Final = 80877102

STARTUP_KEYS: Final[frozenset[str]] = frozenset(
    {"user", "database", "application_name", "client_encoding"}
)
UTF8_NAMES: Final[frozenset[str]] = frozenset({"utf8", "utf-8", "unicode"})

#: Alias como `dbname` (D-066): 1 a 63 caracteres, ASCII minusculo, digitos,
#: `_` e `-`, primeiro alfanumerico.
ALIAS_PATTERN: Final = re.compile(r"[a-z0-9][a-z0-9_-]{0,62}")


class InitialKind(StrEnum):
    SSL_REQUEST = "ssl_request"
    STARTUP = "startup"


@dataclass(frozen=True, slots=True)
class StartupMessage:
    """StartupMessage validado. `database` pode faltar (decidido depois)."""

    user: str
    database: str | None
    application_name: str | None


def _fail(category: PgwireErrorCategory = PgwireErrorCategory.PROTOCOL_VIOLATION) -> NoReturn:
    raise PgwireStartupError(category)


def _utf8(raw: bytes) -> str | None:
    """Decodifica estrito; `None` se invalido. Quem chama levanta FORA do except."""
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None


def initial_length(header: bytes) -> int:
    """Comprimento total do pacote inicial a partir dos 4 bytes do cabecalho."""
    if len(header) != LENGTH_BYTES:
        _fail()
    (length,) = struct.unpack("!I", header)
    if not MIN_INITIAL_PACKET <= length <= MAX_INITIAL_PACKET:
        _fail()
    return int(length)


def classify_initial(body: bytes) -> InitialKind:
    """Tipo do pacote inicial (corpo SEM os 4 bytes de comprimento)."""
    if len(body) < LENGTH_BYTES:
        _fail()
    (code,) = struct.unpack("!I", body[:4])
    if code == SSL_REQUEST_CODE:
        if len(body) != LENGTH_BYTES:
            _fail()
        return InitialKind.SSL_REQUEST
    if code in (GSSENC_REQUEST_CODE, CANCEL_REQUEST_CODE):
        _fail(PgwireErrorCategory.FEATURE_NOT_SUPPORTED)
    if code == PROTOCOL_3_0:
        return InitialKind.STARTUP
    if code >> 16 == PROTOCOL_3_0 >> 16:
        _fail(PgwireErrorCategory.FEATURE_NOT_SUPPORTED)
    _fail()


def parse_startup(body: bytes) -> StartupMessage:
    """Valida o StartupMessage 3.0 inteiro (corpo SEM o comprimento)."""
    if classify_initial(body) is not InitialKind.STARTUP:
        _fail()
    payload = body[4:]
    if not payload.endswith(b"\x00\x00"):
        _fail()
    fields = payload[:-2].split(b"\x00")
    if len(fields) % 2 != 0 or len(fields) // 2 > MAX_STARTUP_PAIRS:
        _fail()
    values: dict[str, str] = {}
    for index in range(0, len(fields), 2):
        raw_key, raw_value = fields[index], fields[index + 1]
        if not raw_key or len(raw_key) > MAX_KEY_BYTES or len(raw_value) > MAX_VALUE_BYTES:
            _fail()
        key, value = _utf8(raw_key), _utf8(raw_value)
        if key is None or value is None or key in values:
            _fail()
        if key not in STARTUP_KEYS:
            _fail(PgwireErrorCategory.FEATURE_NOT_SUPPORTED)
        values[key] = value
    user = values.get("user")
    if not user:
        _fail()
    encoding = values.get("client_encoding")
    if encoding is not None and encoding.lower() not in UTF8_NAMES:
        _fail(PgwireErrorCategory.FEATURE_NOT_SUPPORTED)
    return StartupMessage(user, values.get("database"), values.get("application_name"))


def valid_alias(value: str | None) -> bool:
    """Forma do alias (D-066). Usar so DEPOIS da prova, com falha uniforme."""
    return value is not None and ALIAS_PATTERN.fullmatch(value) is not None


def message_length(header: bytes, *, expected_type: bytes) -> int:
    """Comprimento do corpo de uma mensagem tipada do cliente, limitado."""
    if len(header) != TYPED_HEADER_BYTES or header[:1] != expected_type:
        _fail()
    (length,) = struct.unpack("!I", header[1:])
    if not LENGTH_BYTES <= length <= MAX_SASL_MESSAGE:
        _fail()
    return int(length) - LENGTH_BYTES


def parse_sasl_initial(body: bytes) -> tuple[str, bytes]:
    """`SASLInitialResponse`: nome do mecanismo e a resposta inicial exata."""
    if len(body) > MAX_SASL_MESSAGE - LENGTH_BYTES:
        _fail()
    end = body.find(b"\x00")
    if end <= 0 or end > MAX_MECHANISM_NAME or not body[:end].isascii():
        _fail()
    mechanism = body[:end].decode("ascii")
    rest = body[end + 1 :]
    if len(rest) < LENGTH_BYTES:
        _fail()
    (declared,) = struct.unpack("!i", rest[:4])
    data = rest[4:]
    if declared < 0 or declared != len(data):
        _fail()
    return mechanism, data


# ---- mensagens do servidor -----------------------------------------------------


def _message(kind: bytes, body: bytes) -> bytes:
    return kind + struct.pack("!I", len(body) + 4) + body


def authentication_sasl(mechanisms: tuple[str, ...]) -> bytes:
    names = b"".join(name.encode("ascii") + b"\x00" for name in mechanisms) + b"\x00"
    return _message(b"R", struct.pack("!I", 10) + names)


def authentication_sasl_continue(data: bytes) -> bytes:
    return _message(b"R", struct.pack("!I", 11) + data)


def authentication_sasl_final(data: bytes) -> bytes:
    return _message(b"R", struct.pack("!I", 12) + data)


def authentication_ok() -> bytes:
    return _message(b"R", struct.pack("!I", 0))


__all__ = [
    "MAX_INITIAL_PACKET",
    "MAX_SASL_MESSAGE",
    "InitialKind",
    "StartupMessage",
    "authentication_ok",
    "authentication_sasl",
    "authentication_sasl_continue",
    "authentication_sasl_final",
    "classify_initial",
    "initial_length",
    "message_length",
    "parse_sasl_initial",
    "parse_startup",
    "valid_alias",
]
