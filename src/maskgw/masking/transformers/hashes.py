"""Transformers de hash e HMAC.

`md5`, `sha256` e `sha512` sao hashes SEM chave. Permanecem disponiveis porque
o Gateway e um motor generico de transformacao, mas NAO sao recomendados para
pseudonimizacao de dominios pequenos (CPF, CNPJ, telefone, CEP): o espaco de
valores e pequeno o bastante para reversao por forca bruta. Use `hmac_sha256`.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable, Mapping
from typing import Any, ClassVar

from maskgw.errors import ConfigError
from maskgw.masking.transformers.base import Transformer
from maskgw.masking.transformers.params import reject_secret_params
from maskgw.secretsource import SecretProvider

#: Variavel de ambiente que carrega a chave do HMAC-SHA256.
HMAC_KEY_ENV = "MASKGW_HMAC_KEY"

#: Comprimento minimo aceito para a chave HMAC. Ver docs/DECISIONS.md (D-006).
HMAC_KEY_MIN_LENGTH = 32

_ALGORITHMS: dict[str, Callable[[bytes], hashlib._Hash]] = {
    "md5": lambda data: hashlib.md5(data, usedforsecurity=False),
    "sha256": hashlib.sha256,
    "sha512": hashlib.sha512,
}


class HashTransformer(Transformer):
    """Hash hexadecimal sem chave."""

    deterministic: ClassVar[bool] = True

    def __init__(self, algorithm: str) -> None:
        if algorithm not in _ALGORITHMS:
            msg = f"algoritmo de hash desconhecido: {algorithm!r}"
            raise ConfigError(msg)
        self._algorithm = algorithm
        self._digest = _ALGORITHMS[algorithm]

    def transform(self, value: str) -> str:
        return self._digest(value.encode("utf-8")).hexdigest()

    def __repr__(self) -> str:
        return f"HashTransformer(algorithm={self._algorithm!r})"


class HmacSha256Transformer(Transformer):
    """HMAC-SHA256 com chave secreta vinda do ambiente.

    Deterministico para uma mesma chave; trocar a chave troca toda a saida.
    """

    deterministic: ClassVar[bool] = True

    def __init__(self, key: bytes) -> None:
        if not key:
            msg = "chave HMAC vazia"
            raise ConfigError(msg)
        self._key = key

    def transform(self, value: str) -> str:
        return hmac.new(self._key, value.encode("utf-8"), hashlib.sha256).hexdigest()

    def __repr__(self) -> str:
        # A chave nunca aparece em repr, log, traceback ou mensagem de erro.
        return "HmacSha256Transformer(key=<redacted>)"


def build_hash(algorithm: str) -> Callable[[Mapping[str, Any], SecretProvider], Transformer]:
    """Fabrica de builder para um algoritmo de hash sem chave."""

    def builder(config: Mapping[str, Any], secrets: SecretProvider) -> Transformer:  # noqa: ARG001
        # A recusa de segredos vem primeiro para que a mensagem identifique o
        # parametro proibido em vez do erro generico.
        reject_secret_params(config, transformer=algorithm)
        if config:
            msg = f"transformer {algorithm!r} nao aceita parametros"
            raise ConfigError(msg)
        return HashTransformer(algorithm)

    return builder


def build_hmac_sha256(config: Mapping[str, Any], secrets: SecretProvider) -> Transformer:
    """Constroi o HMAC lendo a chave apenas do provider de segredos."""
    reject_secret_params(config, transformer="hmac_sha256")
    if config:
        msg = (
            "transformer 'hmac_sha256' nao aceita parametros; "
            f"a chave vem exclusivamente de {HMAC_KEY_ENV}"
        )
        raise ConfigError(msg)

    key = secrets.get(HMAC_KEY_ENV)
    if key is None:
        msg = (
            "chave HMAC ausente: defina a variavel de ambiente "
            f"{HMAC_KEY_ENV} para usar o transformer 'hmac_sha256'"
        )
        raise ConfigError(msg)

    if len(key) < HMAC_KEY_MIN_LENGTH:
        msg = (
            f"chave HMAC muito curta: {HMAC_KEY_ENV} exige ao menos "
            f"{HMAC_KEY_MIN_LENGTH} caracteres"
        )
        raise ConfigError(msg)

    return HmacSha256Transformer(key.encode("utf-8"))
