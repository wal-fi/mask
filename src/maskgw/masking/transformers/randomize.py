"""Transformer aleatorio.

Unico transformer NAO deterministico: a mesma entrada produz saidas diferentes
a cada execucao. Descaracteriza, nao pseudonimiza — nao preserva correlacao nem
joins do lado do cliente.

A estrategia e explicita na configuracao. Nao ha inferencia a partir do tipo do
dado.

    config:
      strategy: alphanumeric | digits
      preserve_length: true (default) | false
      length: obrigatorio quando preserve_length = false
"""

from __future__ import annotations

import secrets as secrets_module
import string
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, ClassVar

from maskgw.errors import ConfigError
from maskgw.masking.transformers.base import Transformer
from maskgw.masking.transformers.params import require_int, require_params
from maskgw.secretsource import SecretProvider


class RandomStrategy(StrEnum):
    """Alfabeto usado na geracao."""

    ALPHANUMERIC = "alphanumeric"
    DIGITS = "digits"


_ALPHABETS: dict[RandomStrategy, str] = {
    RandomStrategy.ALPHANUMERIC: string.ascii_letters + string.digits,
    RandomStrategy.DIGITS: string.digits,
}


class RandomTransformer(Transformer):
    """Gera texto aleatorio com o alfabeto e o comprimento configurados."""

    deterministic: ClassVar[bool] = False

    def __init__(
        self,
        strategy: RandomStrategy,
        *,
        preserve_length: bool,
        length: int | None,
    ) -> None:
        self._strategy = strategy
        self._alphabet = _ALPHABETS[strategy]
        self._preserve_length = preserve_length
        self._length = length

    def transform(self, value: str) -> str:
        size = len(value) if self._preserve_length else self._length
        if size is None:  # pragma: no cover - impedido na validacao do boot
            msg = "transformer 'random': comprimento indefinido"
            raise ConfigError(msg)
        # `secrets` em vez de `random`: gerador criptografico, sem estado
        # global previsivel. Ver docs/DECISIONS.md (D-005).
        return "".join(secrets_module.choice(self._alphabet) for _ in range(size))

    def __repr__(self) -> str:
        return (
            f"RandomTransformer(strategy={self._strategy.value!r}, "
            f"preserve_length={self._preserve_length!r}, length={self._length!r})"
        )


def build_random(config: Mapping[str, Any], secrets: SecretProvider) -> Transformer:  # noqa: ARG001
    params = require_params(
        config,
        transformer="random",
        required=("strategy",),
        optional=("preserve_length", "length"),
    )

    raw_strategy = params["strategy"]
    if not isinstance(raw_strategy, str):
        msg = "transformer 'random': parametro 'strategy' deve ser string"
        raise ConfigError(msg)
    try:
        strategy = RandomStrategy(raw_strategy)
    except ValueError as exc:
        supported = sorted(item.value for item in RandomStrategy)
        msg = f"transformer 'random': strategy {raw_strategy!r} invalida; aceitas: {supported}"
        raise ConfigError(msg) from exc

    preserve_length = params.get("preserve_length", True)
    if not isinstance(preserve_length, bool):
        msg = "transformer 'random': parametro 'preserve_length' deve ser booleano"
        raise ConfigError(msg)

    has_length = "length" in params
    if preserve_length and has_length:
        msg = (
            "transformer 'random': 'length' nao pode ser combinado com "
            "'preserve_length: true' (configuracao ambigua)"
        )
        raise ConfigError(msg)
    if not preserve_length and not has_length:
        msg = "transformer 'random': 'length' e obrigatorio quando 'preserve_length' e false"
        raise ConfigError(msg)

    length = require_int(params, "length", transformer="random", minimum=0) if has_length else None

    return RandomTransformer(strategy, preserve_length=preserve_length, length=length)
