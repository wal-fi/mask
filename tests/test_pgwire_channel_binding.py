"""Fase 9, Etapa 7 (D-109): `tls-server-end-point` a partir do DER, sem TLS.

Certificados gerados em `tmp_path` pelo `cryptography`; nenhum arquivo do
usuario. Aceitos: RSA/EC com assinatura SHA-256/384/512. Recusados com erro
fixo: Ed25519, Ed448, SHA-224, DER invalido ou vazio.
"""

from __future__ import annotations

import hashlib

import pytest
from cryptography.hazmat.primitives import hashes

import tests.pgwire_support as support
from maskgw.errors import ConfigError
from maskgw.pgwire.channel_binding import tls_server_end_point
from tests.pgwire_support import make_certificate


@pytest.mark.parametrize(
    ("kind", "algorithm"),
    [
        ("rsa-sha256", "sha256"),
        ("rsa-sha512", "sha512"),
        ("ecdsa-sha256", "sha256"),
        ("ecdsa-p384-sha384", "sha384"),
    ],
)
def test_hash_do_certificado(tmp_path, kind, algorithm):
    cert, _, _ = make_certificate(tmp_path, kind)
    assert tls_server_end_point(cert.der) == hashlib.new(algorithm, cert.der).digest()


@pytest.mark.parametrize("kind", ["ed25519", "ed448"])
def test_edwards_recusado(tmp_path, kind):
    cert, _, _ = make_certificate(tmp_path, kind)
    with pytest.raises(ConfigError) as info:
        tls_server_end_point(cert.der)
    assert info.value.__cause__ is None
    assert info.value.__context__ is None


def test_sha224_recusado(tmp_path, monkeypatch):
    monkeypatch.setattr(support, "_hash", lambda _kind: hashes.SHA224())
    cert, _, _ = make_certificate(tmp_path, "rsa-sha256")
    with pytest.raises(ConfigError):
        tls_server_end_point(cert.der)


@pytest.mark.parametrize("der", [b"", b"\x30\x03\x02\x01\x00", b"nao-e-der", "texto", None])
def test_entrada_invalida(der):
    with pytest.raises(ConfigError) as info:
        tls_server_end_point(der)
    assert info.value.__context__ is None
    assert str(info.value) == "pgwire: certificado incompativel com SCRAM-SHA-256-PLUS"
