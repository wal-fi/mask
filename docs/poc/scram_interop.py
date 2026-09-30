"""Interoperabilidade medida: PoC stdlib x `scramp` (versao identificada).

NAO e produto. Roda num venv TEMPORARIO com `scramp` instalado (ver
`SCRAM-COMPARISON.md`); nao adiciona dependencia ao produto. Exercita, de ponta a
ponta, as combinacoes servidor/cliente entre a implementacao propria em stdlib
(`scram_poc`) e a biblioteca `scramp`, e testa mensagens adulteradas.

Uso: <venv-temp>/python.exe docs/poc/scram_interop.py
"""

from __future__ import annotations

import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scram_poc import ScramClient as MyClient  # noqa: E402
from scram_poc import ScramServer as MyServer  # noqa: E402
from scram_poc import StoredCredential  # noqa: E402

import scramp  # noqa: E402

USER = "gateway"
PASSWORD = "senha-correta"


def _results() -> dict[str, bool]:
    return {}


def my_server_vs_scramp_client() -> bool:
    """Servidor stdlib da PoC autentica um cliente `scramp` real."""
    credential = StoredCredential.derive(PASSWORD)
    server = MyServer(credential)
    client = scramp.ScramClient(["SCRAM-SHA-256"], USER, PASSWORD)
    client_first = client.get_client_first()
    server_first = server.first(client_first)
    client.set_server_first(server_first)
    client_final = client.get_client_final()
    server_final = server.final(client_final)
    client.set_server_final(server_final)  # lança se a assinatura do servidor falhar
    return True


def scramp_server_vs_my_client() -> bool:
    """Servidor `scramp` real autentica o cliente stdlib da PoC."""
    mechanism = scramp.ScramMechanism("SCRAM-SHA-256")
    salt, stored_key, server_key, iterations = mechanism.make_auth_info(PASSWORD)

    def auth_fn(_username: str) -> tuple[bytes, bytes, bytes, int]:
        return salt, stored_key, server_key, iterations

    server = mechanism.make_server(auth_fn)
    client = MyClient(USER, PASSWORD)
    server.set_client_first(client.first())
    server_first = server.get_server_first()
    client_final = client.final(server_first)
    server.set_client_final(client_final)
    server_final = server.get_server_final()
    return client.verify_server(server_final, server_key)


def my_server_rejects_tampered_proof() -> bool:
    credential = StoredCredential.derive(PASSWORD)
    server = MyServer(credential)
    client = scramp.ScramClient(["SCRAM-SHA-256"], USER, PASSWORD)
    server_first = server.first(client.get_client_first())
    client.set_server_first(server_first)
    client_final = client.get_client_final()
    # Inverte um byte da prova.
    head, proof_b64 = client_final.rsplit("p=", 1)
    proof = bytearray(base64.b64decode(proof_b64))
    proof[0] ^= 0xFF
    tampered = head + "p=" + base64.b64encode(bytes(proof)).decode()
    try:
        server.final(tampered)
    except ValueError:
        return True
    return False


def my_server_rejects_tampered_channel_binding() -> bool:
    credential = StoredCredential.derive(PASSWORD)
    server = MyServer(credential)
    client = scramp.ScramClient(["SCRAM-SHA-256"], USER, PASSWORD)
    server_first = server.first(client.get_client_first())
    client.set_server_first(server_first)
    client_final = client.get_client_final().replace("c=biws", "c=AAAA", 1)
    try:
        server.final(client_final)
    except ValueError:
        return True
    return False


def main() -> int:
    checks = {
        "PoC server x scramp client": my_server_vs_scramp_client,
        "scramp server x PoC client": scramp_server_vs_my_client,
        "PoC server recusa prova adulterada (cliente scramp)": my_server_rejects_tampered_proof,
        "PoC server recusa channel binding adulterado": my_server_rejects_tampered_channel_binding,
    }
    ok = True
    for name, fn in checks.items():
        try:
            passed = fn()
        except Exception as exc:  # noqa: BLE001 - PoC: reporta qualquer falha
            passed = False
            print(f"{name}: FAIL ({type(exc).__name__}: {exc})")
            ok = False
            continue
        print(f"{name}:", "PASS" if passed else "FAIL")
        ok = ok and passed
    print("scramp:", scramp.__version__)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
