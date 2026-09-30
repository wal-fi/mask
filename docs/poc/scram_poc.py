"""PoC comparativa de SCRAM-SHA-256 servidor (Fase 9, Etapa 7) — NAO e produto.

Fontes primarias:
- RFC 5802 (SCRAM), secoes 3 (algoritmo) e 5 (mensagens);
- RFC 7677 (SCRAM-SHA-256 e -PLUS);
- RFC 4013 (SASLprep) — aqui NAO implementado; ver "Limitacoes".

Este arquivo NAO e importado por `maskgw`, nao entra no wheel/sdist e nao
adiciona dependencia. Serve so para comparar uma implementacao propria em stdlib
com uma biblioteca mantida, medir conformidade e interoperabilidade, e embasar a
recomendacao. Nenhuma autenticacao de producao e incorporada antes do aval.

Implementa o LADO SERVIDOR do handshake (o Gateway autentica o cliente) com
`hashlib`/`hmac`/`base64`/`secrets` da stdlib, e um cliente minimo para exercitar
o servidor de ponta a ponta. Um `main()` roda o handshake e imprime PASS/FAIL.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

_HASH = "sha256"
_DIGEST_LEN = hashlib.new(_HASH).digest_size


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b, strict=True))


def _hi(password: bytes, salt: bytes, iterations: int) -> bytes:
    """RFC 5802 Hi (PBKDF2-HMAC), a SaltedPassword."""
    return hashlib.pbkdf2_hmac(_HASH, password, salt, iterations, dklen=_DIGEST_LEN)


def _hmac(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, _HASH).digest()


def _h(msg: bytes) -> bytes:
    return hashlib.new(_HASH, msg).digest()


@dataclass(frozen=True)
class StoredCredential:
    """O que o servidor guarda por usuario (RFC 5802 §3): nunca a senha.

    Em producao viria do catalogo/segredo; aqui e derivado da senha uma vez.
    """

    salt: bytes
    iterations: int
    stored_key: bytes
    server_key: bytes

    @classmethod
    def derive(cls, password: str, *, iterations: int = 4096) -> StoredCredential:
        salt = secrets.token_bytes(16)
        salted = _hi(password.encode("utf-8"), salt, iterations)
        client_key = _hmac(salted, b"Client Key")
        server_key = _hmac(salted, b"Server Key")
        return cls(
            salt=salt,
            iterations=iterations,
            stored_key=_h(client_key),
            server_key=server_key,
        )


class ScramServer:
    """Servidor SCRAM-SHA-256 (sem channel binding), passo a passo.

    Uso: `first(client_first)` -> server-first; `final(client_final)` ->
    server-final ou erro. Comparacao de prova com `hmac.compare_digest`.
    """

    def __init__(self, credential: StoredCredential) -> None:
        self._credential = credential
        self._server_nonce = _b64e(secrets.token_bytes(18))
        self._client_first_bare = ""
        self._server_first = ""
        self._nonce = ""

    def first(self, client_first: str) -> str:
        # client-first: "n,,n=user,r=<cnonce>"
        if not client_first.startswith("n,,"):
            raise ValueError("gs2 header nao suportado nesta PoC")
        self._client_first_bare = client_first[3:]
        parts = dict(item.split("=", 1) for item in self._client_first_bare.split(","))
        client_nonce = parts["r"]
        self._nonce = client_nonce + self._server_nonce
        cred = self._credential
        self._server_first = (
            f"r={self._nonce},s={_b64e(cred.salt)},i={cred.iterations}"
        )
        return self._server_first

    def final(self, client_final: str) -> str:
        # client-final: "c=<channel binding>,r=<nonce>,p=<proof>"
        parts = dict(item.split("=", 1) for item in client_final.split(",", 2))
        # RFC 5802 §5.1: para o gs2 header "n,," (sem channel binding), o campo
        # `c` DEVE ser base64("n,,") == "biws". O servidor valida isso — senao um
        # cliente poderia enviar outro `c` e, pior, a assinatura tem de ser
        # calculada sobre o `c` REALMENTE enviado, nao sobre um valor assumido.
        channel_binding = parts["c"]
        if channel_binding != "biws":
            raise ValueError("channel binding invalido")
        if parts["r"] != self._nonce:
            raise ValueError("nonce divergente")
        proof = _b64d(parts["p"])
        without_proof = f"c={channel_binding},r={parts['r']}"
        auth_message = (
            f"{self._client_first_bare},{self._server_first},{without_proof}"
        ).encode("ascii")
        client_signature = _hmac(self._credential.stored_key, auth_message)
        client_key = _xor(proof, client_signature)
        # RFC 5802 §3: o servidor confere H(ClientKey) == StoredKey.
        if not hmac.compare_digest(_h(client_key), self._credential.stored_key):
            raise ValueError("prova do cliente invalida")
        server_signature = _hmac(self._credential.server_key, auth_message)
        return f"v={_b64e(server_signature)}"


class ScramClient:
    """Cliente minimo, so para exercitar o servidor da PoC de ponta a ponta."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._client_nonce = _b64e(secrets.token_bytes(18))
        self._client_first_bare = ""
        self._auth_message = b""

    def first(self) -> str:
        self._client_first_bare = f"n={self._username},r={self._client_nonce}"
        return f"n,,{self._client_first_bare}"

    def final(self, server_first: str) -> str:
        parts = dict(item.split("=", 1) for item in server_first.split(","))
        nonce, salt, iterations = parts["r"], _b64d(parts["s"]), int(parts["i"])
        salted = _hi(self._password.encode("utf-8"), salt, iterations)
        client_key = _hmac(salted, b"Client Key")
        stored_key = _h(client_key)
        without_proof = f"c=biws,r={nonce}"
        self._auth_message = (
            f"{self._client_first_bare},{server_first},{without_proof}"
        ).encode("ascii")
        client_signature = _hmac(stored_key, self._auth_message)
        proof = _xor(client_key, client_signature)
        return f"{without_proof},p={_b64e(proof)}"

    def verify_server(self, server_final: str, server_key: bytes) -> bool:
        parts = dict(item.split("=", 1) for item in server_final.split(","))
        expected = _hmac(server_key, self._auth_message)
        return hmac.compare_digest(_b64d(parts["v"]), expected)


def run_handshake(username: str, password: str, *, attempt: str | None = None) -> bool:
    """Handshake completo. `attempt` != None testa uma senha errada."""
    credential = StoredCredential.derive(password)
    server = ScramServer(credential)
    client = ScramClient(username, attempt if attempt is not None else password)
    server_first = server.first(client.first())
    client_final = client.final(server_first)
    try:
        server_final = server.final(client_final)
    except ValueError:
        return False
    return client.verify_server(server_final, credential.server_key)


def run_with_tampered_channel_binding() -> bool:
    """Reenvia a prova valida com `c=AAAA` em vez de `c=biws`.

    Regressao do bug encontrado na revisao: o servidor tem de recusar, tanto por
    validar o campo `c` quanto por calcular a assinatura sobre o `c` enviado.
    Retorna True se o servidor RECUSOU (comportamento correto).
    """
    credential = StoredCredential.derive("senha-correta")
    server = ScramServer(credential)
    client = ScramClient("gateway", "senha-correta")
    server_first = server.first(client.first())
    client_final = client.final(server_first)
    tampered = client_final.replace("c=biws", "c=AAAA", 1)
    try:
        server.final(tampered)
    except ValueError:
        return True
    return False


def main() -> int:
    ok = run_handshake("gateway", "senha-correta")
    bad = run_handshake("gateway", "senha-correta", attempt="senha-errada")
    tampered_rejected = run_with_tampered_channel_binding()
    print("handshake correto:", "PASS" if ok else "FAIL")
    print("senha errada recusada:", "PASS" if not bad else "FAIL")
    print("channel binding adulterado recusado:", "PASS" if tampered_rejected else "FAIL")
    return 0 if (ok and not bad and tampered_rejected) else 1


if __name__ == "__main__":
    raise SystemExit(main())
