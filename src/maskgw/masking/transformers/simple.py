"""Transformers `fixed` e `truncate`."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from maskgw.errors import ConfigError
from maskgw.masking.transformers.base import Transformer
from maskgw.masking.transformers.params import require_int, require_params
from maskgw.secretsource import SecretProvider


class FixedTransformer(Transformer):
    """Substitui qualquer valor nao-nulo por uma constante."""

    deterministic: ClassVar[bool] = True

    def __init__(self, value: str) -> None:
        self._value = value

    def transform(self, value: str) -> str:  # noqa: ARG002 - saida independe da entrada
        return self._value

    def __repr__(self) -> str:
        return f"FixedTransformer(value={self._value!r})"


class TruncateTransformer(Transformer):
    """Mantem os primeiros `length` caracteres do valor.

    Atencao: este transformer PRESERVA um prefixo do dado original. E uma
    reducao de exposicao, nao um anonimizador. Ver docs/MASKING-SPEC.md.
    """

    deterministic: ClassVar[bool] = True

    def __init__(self, length: int) -> None:
        if length < 0:
            msg = "transformer 'truncate': 'length' deve ser >= 0"
            raise ConfigError(msg)
        self._length = length

    def transform(self, value: str) -> str:
        return value[: self._length]

    def __repr__(self) -> str:
        return f"TruncateTransformer(length={self._length!r})"


def build_fixed(config: Mapping[str, Any], secrets: SecretProvider) -> Transformer:  # noqa: ARG001
    params = require_params(config, transformer="fixed", required=("value",))
    value = params["value"]
    if not isinstance(value, str):
        msg = "transformer 'fixed': parametro 'value' deve ser string"
        raise ConfigError(msg)
    return FixedTransformer(value)


def build_truncate(config: Mapping[str, Any], secrets: SecretProvider) -> Transformer:  # noqa: ARG001
    params = require_params(config, transformer="truncate", required=("length",))
    length = require_int(params, "length", transformer="truncate", minimum=0)
    return TruncateTransformer(length)
