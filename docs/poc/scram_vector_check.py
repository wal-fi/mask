"""Conformidade da PoC contra o vetor de teste do RFC 7677 (SCRAM-SHA-256).

RFC 7677, secao 3: user=user, password=pencil, com o nonce e salt do exemplo.
Prova que a derivacao (Hi/ClientKey/StoredKey/ServerKey) e as assinaturas da PoC
batem com o vetor normativo. Nao e produto; roda com stdlib.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

# Valores literais do RFC 7677 secao 3.
CLIENT_NONCE = "rOprNGfwEbeRWgbNEkqO"
SERVER_NONCE = "%hvYDpWUa2RaTCAfuxFIlj)hNlF$k0"
NONCE = CLIENT_NONCE + SERVER_NONCE
SALT = "W22ZaJ0SNY7soEsUEjb6gQ=="
ITERATIONS = 4096
PASSWORD = b"pencil"

EXPECTED_CLIENT_PROOF = "dHzbZapWIk4jUhN+Ute9ytag9zjfMHgsqmmiz7AndVQ="
EXPECTED_SERVER_SIGNATURE = "6rriTRBi23WpRR/wtup+mMhUZUn/dB5nLTJRsjl95G4="


def _hmac(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, "sha256").digest()


def main() -> int:
    salt = base64.b64decode(SALT)
    salted = hashlib.pbkdf2_hmac("sha256", PASSWORD, salt, ITERATIONS, dklen=32)
    client_key = _hmac(salted, b"Client Key")
    stored_key = hashlib.sha256(client_key).digest()
    server_key = _hmac(salted, b"Server Key")

    client_first_bare = f"n=user,r={CLIENT_NONCE}"
    server_first = f"r={NONCE},s={SALT},i={ITERATIONS}"
    client_final_without_proof = f"c=biws,r={NONCE}"
    auth_message = (
        f"{client_first_bare},{server_first},{client_final_without_proof}"
    ).encode("ascii")

    client_signature = _hmac(stored_key, auth_message)
    client_proof = bytes(a ^ b for a, b in zip(client_key, client_signature, strict=True))
    server_signature = _hmac(server_key, auth_message)

    proof_ok = base64.b64encode(client_proof).decode() == EXPECTED_CLIENT_PROOF
    sig_ok = base64.b64encode(server_signature).decode() == EXPECTED_SERVER_SIGNATURE
    print("ClientProof vector:", "PASS" if proof_ok else "FAIL")
    print("ServerSignature vector:", "PASS" if sig_ok else "FAIL")
    return 0 if (proof_ok and sig_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
