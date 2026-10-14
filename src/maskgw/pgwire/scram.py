"""Troca SCRAM-SHA-256 / SCRAM-SHA-256-PLUS do lado servidor (D-109).

Maquina de estados propria, pura e de uso unico: `client_first` e depois
`client_final`, nessa ordem, uma vez cada. Qualquer outra sequencia, ou
qualquer falha, deixa a troca em `FAILED` para sempre.

Regras (RFC 5802/7677, perfil do PostgreSQL):

- a identidade e o `user` do StartupMessage, ja resolvida no `ScramVerifier`
  recebido; o `n=` do client-first e ignorado e pode ser vazio, como o libpq
  envia. As mensagens do cliente entram no AuthMessage EXATAMENTE como
  chegaram, sem reescrita;
- `-PLUS` so e oferecido com channel binding; `-PLUS` exige
  `p=tls-server-end-point`; `p=` sem `-PLUS` e `y` com `-PLUS` oferecido
  (downgrade) sao recusados; authzid e extensoes sao recusados;
- o nonce do servidor tem 18 bytes de `secrets`;
- forma invalida e `PROTOCOL_VIOLATION`. Prova, channel binding, nonce,
  usuario desconhecido e alias recusado sao UMA decisao, tomada no fim com
  todas as comparacoes feitas, e saem como `AUTHENTICATION_FAILED`.

Nenhum erro carrega a entrada do cliente, e todos sao levantados fora de
`except` (D-017).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re
import secrets
from enum import Enum
from typing import Final, NoReturn

from maskgw.pgwire.credential import ScramVerifier
from maskgw.pgwire.errors import PgwireErrorCategory, PgwireStartupError
from maskgw.pgwire.framing import MAX_SASL_MESSAGE

SCRAM_SHA_256: Final = "SCRAM-SHA-256"
SCRAM_SHA_256_PLUS: Final = "SCRAM-SHA-256-PLUS"
CHANNEL_BINDING_TYPE: Final = "tls-server-end-point"
SERVER_NONCE_BYTES: Final = 18
MIN_CLIENT_NONCE: Final = 8
MAX_CLIENT_NONCE: Final = 256
PROOF_BYTES: Final = 32

#: `printable` da RFC 5802, sem `,`.
_NONCE: Final = re.compile(r"[\x21-\x2b\x2d-\x7e]+")
#: client-first-message-bare: `n=saslname,r=nonce`, sem extensoes. O
#: `saslname` so admite `=` como `=2C` ou `=3D`, nenhum caractere de controle,
#: e pode ser vazio.
_CLIENT_FIRST_BARE: Final = re.compile(
    r"n=(?:[^=,\x00-\x1f\x7f]|=2C|=3D)*,r=(?P<nonce>[\x21-\x2b\x2d-\x7e]"
    rf"{{{MIN_CLIENT_NONCE},{MAX_CLIENT_NONCE}}})"
)
#: client-final-message: `c=...,r=...,p=...`, nessa ordem, sem extensoes.
_CLIENT_FINAL: Final = re.compile(
    r"(?P<without_proof>c=(?P<cbind>[A-Za-z0-9+/]*={0,2}),r=(?P<nonce>[\x21-\x2b\x2d-\x7e]+))"
    r",p=(?P<proof>[A-Za-z0-9+/]*={0,2})"
)


def _flag_allowed(plus: bool, flag: str, *, binding_offered: bool) -> bool:
    """Consistencia gs2: mecanismo, flag e oferta do servidor."""
    if plus:
        return flag == f"p={CHANNEL_BINDING_TYPE}"
    if flag == "y":
        # `y`: o cliente suporta binding mas acha que o servidor nao. Com
        # -PLUS oferecido, isso e downgrade.
        return not binding_offered
    return flag == "n"


class _Stage(Enum):
    AWAIT_FIRST = "await_first"
    AWAIT_FINAL = "await_final"
    DONE = "done"
    FAILED = "failed"


class ScramServerExchange:
    """Uma troca SCRAM. Nao reutilizavel."""

    __slots__ = (
        "_auth_prefix",
        "_cbind_input",
        "_channel_binding",
        "_nonce",
        "_server_nonce",
        "_stage",
        "_verifier",
    )

    def __init__(
        self,
        verifier: ScramVerifier,
        *,
        channel_binding: bytes | None,
        server_nonce: str | None = None,
    ) -> None:
        """`channel_binding`: o `tls-server-end-point` do certificado local, ou
        `None` sem TLS. `server_nonce` existe so para vetores normativos."""
        if channel_binding is not None and not channel_binding:
            raise ValueError("channel binding vazio")
        if server_nonce is not None and _NONCE.fullmatch(server_nonce) is None:
            raise ValueError("nonce do servidor invalido")
        self._verifier = verifier
        self._channel_binding = channel_binding
        self._server_nonce = server_nonce
        self._stage = _Stage.AWAIT_FIRST
        self._nonce = ""
        self._auth_prefix = ""
        self._cbind_input = b""

    def __repr__(self) -> str:
        return f"ScramServerExchange(stage={self._stage.value})"

    @property
    def mechanisms(self) -> tuple[str, ...]:
        if self._channel_binding is None:
            return (SCRAM_SHA_256,)
        return (SCRAM_SHA_256_PLUS, SCRAM_SHA_256)

    def _fail(
        self, category: PgwireErrorCategory = PgwireErrorCategory.PROTOCOL_VIOLATION
    ) -> NoReturn:
        self._stage = _Stage.FAILED
        raise PgwireStartupError(category)

    def _text(self, data: bytes) -> str:
        if len(data) > MAX_SASL_MESSAGE:
            self._fail()
        text = _utf8(data)
        if text is None:
            self._fail()
        return text

    def client_first(self, mechanism: str, data: bytes) -> bytes:
        """Valida o client-first e devolve o server-first."""
        if self._stage is not _Stage.AWAIT_FIRST:
            self._fail()
        if mechanism not in self.mechanisms:
            self._fail()
        message = self._text(data)
        flag, sep1, rest = message.partition(",")
        authzid, sep2, bare = rest.partition(",")
        if not sep1 or not sep2 or authzid:
            self._fail()
        plus = mechanism == SCRAM_SHA_256_PLUS
        if not _flag_allowed(plus, flag, binding_offered=self._channel_binding is not None):
            self._fail()
        parsed = _CLIENT_FIRST_BARE.fullmatch(bare)
        if parsed is None:
            self._fail()
        client_nonce = parsed.group("nonce")
        suffix = self._server_nonce or _random_suffix()
        if suffix is None:
            self._fail(PgwireErrorCategory.INTERNAL_ERROR)
        self._nonce = client_nonce + suffix
        salt = base64.b64encode(self._verifier.salt).decode("ascii")
        server_first = f"r={self._nonce},s={salt},i={self._verifier.iterations}"
        header = (flag + ",,").encode("ascii")
        binding = self._channel_binding if plus else None
        self._cbind_input = header + (binding or b"")
        self._auth_prefix = f"{bare},{server_first},"
        self._stage = _Stage.AWAIT_FINAL
        return server_first.encode("ascii")

    def client_final(self, data: bytes, *, identity_accepted: bool) -> bytes:
        """Valida o client-final e devolve o server-final (`v=`).

        `identity_accepted` e a decisao do chamador sobre o restante da
        identidade (o alias): entra na MESMA decisao final, depois de todas as
        comparacoes, para que alias recusado e senha errada sejam iguais.
        """
        if self._stage is not _Stage.AWAIT_FINAL:
            self._fail()
        parsed = _CLIENT_FINAL.fullmatch(self._text(data))
        if parsed is None:
            self._fail()
        raw_proof = _b64decode(parsed.group("proof"))
        if raw_proof is None or len(raw_proof) != PROOF_BYTES:
            self._fail()
        expected_channel = base64.b64encode(self._cbind_input)
        channel_ok = hmac.compare_digest(parsed.group("cbind").encode("ascii"), expected_channel)
        nonce_ok = hmac.compare_digest(
            parsed.group("nonce").encode("ascii"), self._nonce.encode("ascii")
        )
        auth_message = (self._auth_prefix + parsed.group("without_proof")).encode("utf-8")
        verifier = self._verifier
        signature = hmac.new(verifier.stored_key, auth_message, hashlib.sha256).digest()
        client_key = bytes(a ^ b for a, b in zip(raw_proof, signature, strict=True))
        proof_ok = hmac.compare_digest(hashlib.sha256(client_key).digest(), verifier.stored_key)
        server_signature = hmac.new(verifier.server_key, auth_message, hashlib.sha256).digest()
        accepted = channel_ok & nonce_ok & proof_ok & verifier.real & identity_accepted
        if not accepted:
            self._fail(PgwireErrorCategory.AUTHENTICATION_FAILED)
        self._stage = _Stage.DONE
        return b"v=" + base64.b64encode(server_signature)


def _random_suffix() -> str | None:
    """Nonce do servidor; `None` se a fonte do sistema falhar (sem a causa)."""
    try:
        raw = secrets.token_bytes(SERVER_NONCE_BYTES)
    except OSError:
        return None
    return base64.b64encode(raw).decode("ascii")


def _utf8(data: bytes) -> str | None:
    try:
        return data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None


def _b64decode(text: str) -> bytes | None:
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        return None


__all__ = [
    "CHANNEL_BINDING_TYPE",
    "SCRAM_SHA_256",
    "SCRAM_SHA_256_PLUS",
    "ScramServerExchange",
]
