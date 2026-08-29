"""Transformer de substituicao por expressao regular.

Deterministico: `pattern` e `replacement` sao fixos na configuracao.

Fail-closed: se o padrao nao casar o valor, o resultado NAO e o valor original
— seria um vazamento silencioso. Devolve-se `REDACTED`.
Ver docs/DECISIONS.md (D-003).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, ClassVar

from maskgw.errors import ConfigError
from maskgw.masking.transformers.base import REDACTED, Transformer
from maskgw.masking.transformers.params import require_params
from maskgw.secretsource import SecretProvider


class RegexTransformer(Transformer):
    """Aplica `pattern.sub(replacement, value)` com fallback redigido."""

    deterministic: ClassVar[bool] = True

    def __init__(self, pattern: re.Pattern[str], replacement: str) -> None:
        self._pattern = pattern
        self._replacement = replacement

    def transform(self, value: str) -> str:
        try:
            result, count = self._pattern.subn(self._replacement, value)
        except (re.error, IndexError):
            # Nao deve ocorrer: o template e validado no boot. Ainda assim,
            # falhar redigido e melhor que propagar o valor.
            return REDACTED
        if count == 0:
            return REDACTED
        return result

    def __repr__(self) -> str:
        return f"RegexTransformer(pattern={self._pattern.pattern!r})"


def build_regex(config: Mapping[str, Any], secrets: SecretProvider) -> Transformer:  # noqa: ARG001
    params = require_params(
        config,
        transformer="regex",
        required=("pattern", "replacement"),
    )

    raw_pattern = params["pattern"]
    replacement = params["replacement"]

    if not isinstance(raw_pattern, str):
        msg = "transformer 'regex': parametro 'pattern' deve ser string"
        raise ConfigError(msg)
    if not isinstance(replacement, str):
        msg = "transformer 'regex': parametro 'replacement' deve ser string"
        raise ConfigError(msg)

    try:
        pattern = re.compile(raw_pattern)
    except re.error as exc:
        msg = f"transformer 'regex': pattern invalido ({exc.msg})"
        raise ConfigError(msg) from exc

    # `sub` compila o template antes de varrer o texto, entao um backreference
    # invalido e detectado aqui, no boot, mesmo sem nenhuma correspondencia.
    try:
        pattern.sub(replacement, "")
    except re.error as exc:
        msg = f"transformer 'regex': replacement invalido ({exc.msg})"
        raise ConfigError(msg) from exc
    except IndexError as exc:
        msg = f"transformer 'regex': replacement referencia grupo inexistente ({exc})"
        raise ConfigError(msg) from exc

    return RegexTransformer(pattern, replacement)
