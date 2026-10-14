"""Fonte bruta de settings de processo, separada da normalizacao de secrets."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Final, Protocol

ADMIN_UI_ENABLED_ENV: Final = "MASKGW_ADMIN_UI_ENABLED"

#: Flag do ingresso PGWire (spec §5.1), lida pela fronteira de processo SEM
#: importar `maskgw.pgwire`. Mesmo nome de `maskgw.pgwire.settings.ENABLED_ENV`.
PGWIRE_ENABLED_ENV: Final = "MASKGW_PGWIRE_ENABLED"
PGWIRE_ENABLED_VALUE: Final = "1"


class RawSettings(Protocol):
    def get_raw(self, name: str) -> str | None:
        """Devolve o valor sem strip, coercao ou conversao de vazio em ausencia."""
        ...


class EnvRawSettings:
    def get_raw(self, name: str) -> str | None:
        return os.environ.get(name)

    def __repr__(self) -> str:
        return "EnvRawSettings()"


class MappingRawSettings:
    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)

    def get_raw(self, name: str) -> str | None:
        return self._values.get(name)

    def __repr__(self) -> str:
        return "MappingRawSettings()"
