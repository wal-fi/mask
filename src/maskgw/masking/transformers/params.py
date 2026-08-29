"""Validacao dos parametros de configuracao de transformers.

Toda violacao e `ConfigError`: configuracao invalida impede a inicializacao.

As mensagens citam apenas NOMES de parametro, nunca valores — um parametro mal
posicionado pode conter algo sensivel.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from maskgw.errors import ConfigError

#: Nomes de parametro que nunca podem aparecer no `masking.yaml`. Segredos vem
#: exclusivamente do ambiente. Ver docs/SECURITY.md.
FORBIDDEN_PARAMS = frozenset(
    {
        "key",
        "keys",
        "hmac_key",
        "secret",
        "secret_key",
        "password",
        "passwd",
        "token",
        "salt",
        "pepper",
        "credential",
        "credentials",
    }
)


def reject_secret_params(config: Mapping[str, Any], *, transformer: str) -> None:
    """Recusa qualquer tentativa de embutir segredo na configuracao."""
    found = sorted(name for name in config if name.casefold() in FORBIDDEN_PARAMS)
    if found:
        msg = (
            f"transformer {transformer!r}: parametro(s) {found} nao sao permitidos "
            "no masking.yaml; segredos vem exclusivamente do ambiente"
        )
        raise ConfigError(msg)


def require_params(
    config: Mapping[str, Any],
    *,
    transformer: str,
    required: tuple[str, ...] = (),
    optional: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Valida presenca e ausencia de parametros e devolve uma copia."""
    reject_secret_params(config, transformer=transformer)

    allowed = set(required) | set(optional)
    unknown = sorted(set(config) - allowed)
    if unknown:
        msg = (
            f"transformer {transformer!r}: parametro(s) desconhecido(s) {unknown}; "
            f"aceitos: {sorted(allowed)}"
        )
        raise ConfigError(msg)

    missing = sorted(name for name in required if name not in config)
    if missing:
        msg = f"transformer {transformer!r}: parametro(s) obrigatorio(s) ausente(s) {missing}"
        raise ConfigError(msg)

    return dict(config)


def require_int(
    params: Mapping[str, Any],
    name: str,
    *,
    transformer: str,
    minimum: int = 0,
) -> int:
    """Extrai um inteiro validado. `bool` nao e aceito como inteiro."""
    value = params[name]
    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"transformer {transformer!r}: parametro {name!r} deve ser inteiro"
        raise ConfigError(msg)
    if value < minimum:
        msg = f"transformer {transformer!r}: parametro {name!r} deve ser >= {minimum}"
        raise ConfigError(msg)
    return value
