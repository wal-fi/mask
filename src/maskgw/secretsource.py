"""Origem de segredos.

Segredos (hoje: a chave do HMAC-SHA256) vem exclusivamente do ambiente ou de um
provider explicito. Nunca do `masking.yaml` e nunca do cliente MCP.

Este modulo depende apenas da stdlib para nao contaminar `masking/`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Protocol


class SecretProvider(Protocol):
    """Fonte de segredos consultada durante o carregamento da configuracao."""

    def get(self, name: str) -> str | None:
        """Devolve o segredo `name`, ou None se ausente/vazio."""
        ...


def _normalize(value: str | None) -> str | None:
    """Trata segredo vazio ou so com espacos como ausente (fail-closed)."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class EnvSecretProvider:
    """Le segredos de variaveis de ambiente."""

    def get(self, name: str) -> str | None:
        return _normalize(os.environ.get(name))

    def __repr__(self) -> str:
        return "EnvSecretProvider()"


class MappingSecretProvider:
    """Provider explicito, a partir de um mapa em memoria.

    Usado em testes para nao depender de mutacao de `os.environ`.
    """

    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)

    def get(self, name: str) -> str | None:
        return _normalize(self._values.get(name))

    def __repr__(self) -> str:
        # Nunca expor valores.
        return f"MappingSecretProvider(names={sorted(self._values)!r})"
