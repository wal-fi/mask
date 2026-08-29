"""Registry extensivel de transformers.

Adicionar um transformer nao exige alteracao no nucleo do Masking Engine:
basta registrar um builder aqui.

O registry e consultado no boot. Referencia a um transformer inexistente e
`ConfigError` — impede a inicializacao.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from maskgw.errors import ConfigError
from maskgw.masking.transformers.base import Transformer
from maskgw.masking.transformers.hashes import build_hash, build_hmac_sha256
from maskgw.masking.transformers.randomize import build_random
from maskgw.masking.transformers.regex_transformer import build_regex
from maskgw.masking.transformers.simple import build_fixed, build_truncate
from maskgw.secretsource import SecretProvider

TransformerBuilder = Callable[[Mapping[str, Any], SecretProvider], Transformer]


class TransformerRegistry:
    """Mapa nome -> builder."""

    def __init__(self) -> None:
        self._builders: dict[str, TransformerBuilder] = {}

    def register(self, name: str, builder: TransformerBuilder, *, replace: bool = False) -> None:
        if not name:
            msg = "nome de transformer vazio"
            raise ConfigError(msg)
        if name in self._builders and not replace:
            msg = f"transformer {name!r} ja registrado"
            raise ConfigError(msg)
        self._builders[name] = builder

    def available(self) -> tuple[str, ...]:
        return tuple(sorted(self._builders))

    def __contains__(self, name: object) -> bool:
        return name in self._builders

    def build(
        self,
        name: str,
        config: Mapping[str, Any] | None,
        secrets: SecretProvider,
    ) -> Transformer:
        """Constroi um transformer. Erros aqui sao fatais no boot."""
        builder = self._builders.get(name)
        if builder is None:
            msg = f"transformer desconhecido: {name!r}; disponiveis: {list(self.available())}"
            raise ConfigError(msg)
        return builder(config or {}, secrets)


def build_default_registry() -> TransformerRegistry:
    """Registry com os transformers do MVP."""
    registry = TransformerRegistry()
    registry.register("md5", build_hash("md5"))
    registry.register("sha256", build_hash("sha256"))
    registry.register("sha512", build_hash("sha512"))
    registry.register("hmac_sha256", build_hmac_sha256)
    registry.register("regex", build_regex)
    registry.register("random", build_random)
    registry.register("fixed", build_fixed)
    registry.register("truncate", build_truncate)
    return registry
