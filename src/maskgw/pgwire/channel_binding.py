"""`tls-server-end-point` (RFC 5929 §4.1) a partir do DER do certificado (D-109).

Funcao pura sobre bytes: nao le arquivo e nao cria contexto TLS. Quem chama
deve passar o leaf que o servidor EFETIVAMENTE apresenta, e nao um arquivo
relido depois (TOCTOU); obter esse leaf e responsabilidade de um incremento
futuro e, por ora, so do harness de testes.

Aceita apenas chave RSA ou EC com assinatura em SHA-256, SHA-384 ou SHA-512;
o binding usa o mesmo hash. MD5, SHA-1, SHA-224, Ed25519, Ed448, outras chaves
ou hash desconhecido sao recusados: sem binding possivel, nao ha queda
silenciosa para SCRAM-SHA-256 sozinho.
"""

from __future__ import annotations

import hashlib
from typing import Final

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from maskgw.errors import ConfigError

_UNSUPPORTED: Final = "pgwire: certificado incompativel com SCRAM-SHA-256-PLUS"

#: Sem MD5/SHA-1: a RFC 5929 os mapearia para SHA-256, mas um certificado assim
#: assinado e recusado (mais estrito, e o mapeamento nao teria prova medida).
_HASHES: Final[dict[str, str]] = {
    hashes.SHA256.name: "sha256",
    hashes.SHA384.name: "sha384",
    hashes.SHA512.name: "sha512",
}


def _hash_name(certificate_der: bytes) -> str | None:
    try:
        certificate = x509.load_der_x509_certificate(certificate_der)
        key = certificate.public_key()
        algorithm = certificate.signature_hash_algorithm
    except (ValueError, TypeError, UnsupportedAlgorithm):
        return None
    if not isinstance(key, rsa.RSAPublicKey | ec.EllipticCurvePublicKey) or algorithm is None:
        return None
    return _HASHES.get(algorithm.name)


def tls_server_end_point(certificate_der: bytes) -> bytes:
    """Dados de channel binding do certificado; `ConfigError` fixo se recusado."""
    if not isinstance(certificate_der, bytes) or not certificate_der:
        raise ConfigError(_UNSUPPORTED)
    name = _hash_name(certificate_der)
    if name is None:
        raise ConfigError(_UNSUPPORTED)
    return hashlib.new(name, certificate_der).digest()


__all__ = ["tls_server_end_point"]
