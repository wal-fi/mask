"""Fonte bruta de settings de processo, separada da normalizacao de secrets."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Final, Protocol

from maskgw.errors import ConfigError

ADMIN_UI_ENABLED_ENV: Final = "MASKGW_ADMIN_UI_ENABLED"

#: Flag do ingresso PGWire (spec §5.1), lida pela fronteira de processo SEM
#: importar `maskgw.pgwire`. Mesmo nome de `maskgw.pgwire.settings.ENABLED_ENV`.
PGWIRE_ENABLED_ENV: Final = "MASKGW_PGWIRE_ENABLED"
PGWIRE_ENABLED_VALUE: Final = "1"

#: Caminhos operacionais do catalogo (spec §5.1 e D-080). Mesmos nomes e
#: layout de `maskgw.datasource.store` (um teste confere a igualdade), mas
#: definidos AQUI para que o ramo desligado nao importe o catalogo.
DATASOURCE_STORE_ENV: Final = "MASKGW_DATASOURCE_STORE"
DATASOURCE_ANCHOR_ENV: Final = "MASKGW_DATASOURCE_ANCHOR"
DATASOURCE_STORE_NAME: Final = "datasources.store"
DATASOURCE_ANCHOR_DIRECTORY: Final = ".maskgw-anchor"
DATASOURCE_ANCHOR_NAME: Final = "datasources.anchor"


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


def _raw_path(raw: RawSettings, name: str) -> Path | None:
    """Caminho bruto validado; `None` se ausente.

    Vazio, so espacos ou com NUL e invalido. Caminho com raiz ou drive mas
    SEM ser absoluto (`\\x` ou `C:x` no Windows) e ambiguo e recusado, em vez
    de ser resolvido contra o drive ou o cwd atuais.
    """
    value = raw.get_raw(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        msg = f"caminho invalido em {name}"
        raise ConfigError(msg)
    path = Path(value)
    if path.anchor and not path.is_absolute():
        msg = f"caminho invalido em {name}"
        raise ConfigError(msg)
    return path


def resolve_catalog_paths(raw: RawSettings, config_path: str | Path) -> tuple[Path, Path]:
    """Caminhos operacionais do store e da ancora, resolvidos UMA vez.

    - store ausente: `<pai absoluto do MASKGW_CONFIG efetivo>/datasources.store`;
      absoluto explicito fica como esta; relativo explicito e relativo a esse
      mesmo pai (nunca ao cwd, nunca `config/config/...`);
    - ancora ausente: `<pai do store resolvido>/.maskgw-anchor/datasources.anchor`
      (D-080); explicita, precisa ser ABSOLUTA.

    So calcula: nao toca o filesystem. Os dois caminhos sao passados
    explicitamente ao catalogo, que faz as checagens autoritativas (symlink,
    diretorio, lock); nada e relido do ambiente depois. Erro fixo, sem valor.
    """
    config_parent = Path(os.path.abspath(os.fspath(config_path))).parent
    store_raw = _raw_path(raw, DATASOURCE_STORE_ENV)
    if store_raw is None:
        store = config_parent / DATASOURCE_STORE_NAME
    elif store_raw.is_absolute():
        store = store_raw
    else:
        store = config_parent / store_raw
    store = Path(os.path.abspath(store))
    anchor_raw = _raw_path(raw, DATASOURCE_ANCHOR_ENV)
    if anchor_raw is None:
        anchor = store.parent / DATASOURCE_ANCHOR_DIRECTORY / DATASOURCE_ANCHOR_NAME
    elif anchor_raw.is_absolute():
        anchor = Path(os.path.abspath(anchor_raw))
    else:
        msg = f"{DATASOURCE_ANCHOR_ENV} precisa ser um caminho absoluto"
        raise ConfigError(msg)
    return store, anchor
