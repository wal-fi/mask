"""Migração explícita e não destrutiva do DSN legado para o catálogo."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Final

from psycopg import Error as PsycopgError
from psycopg.conninfo import conninfo_to_dict

from maskgw.config.loader import deserialize, read_config_text, validate_file_config
from maskgw.datasource.models import (
    DatasourceDraft,
    DatasourcePolicy,
    DatasourceRecord,
    DatasourceValidationError,
    DestinationPolicy,
)
from maskgw.datasource.store import CatalogStore, CatalogStoreError, LegacyMigrationError
from maskgw.errors import ConfigError
from maskgw.secretsource import EnvSecretProvider, SecretProvider

LEGACY_DSN_ENV: Final = "MASKGW_DATABASE_DSN"
DEFAULT_CONFIG_PATH: Final = Path("config/masking.yaml")
_MAX_PORT: Final = 65_535


def _required_text(values: Mapping[str, object], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value:
        raise LegacyMigrationError("DSN legado sem campos obrigatorios")
    return value


def _single_port(values: Mapping[str, object]) -> int:
    raw_port = _required_text(values, "port")
    if "," in raw_port:
        raise LegacyMigrationError("DSN legado com destinos multiplos")
    try:
        port = int(raw_port)
    except ValueError:
        raise LegacyMigrationError("DSN legado com porta invalida") from None
    if not 1 <= port <= _MAX_PORT:
        raise LegacyMigrationError("DSN legado com porta invalida")
    return port


def migrate_legacy_datasource(  # noqa: PLR0913 - migration inputs are explicit
    catalog: CatalogStore,
    *,
    alias: str,
    display_name: str | None = None,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    secrets_provider: SecretProvider | None = None,
    destination_policy: DestinationPolicy | None = None,
    resolver: Callable[[str, int], Sequence[str]] | None = None,
) -> DatasourceRecord:
    """Copia o datasource legado para o catálogo, sem alterar a fonte legada.

    A função só pode ser chamada explicitamente por uma futura composição de
    startup/admin. Ela lê o DSN em memória, cifra a senha dentro de
    ``CatalogStore.create`` e não retorna nem persiste o DSN original.
    """

    provider = secrets_provider if secrets_provider is not None else EnvSecretProvider()
    dsn = provider.get(LEGACY_DSN_ENV)
    if dsn is None:
        raise LegacyMigrationError("DSN legado ausente")
    try:
        parsed = conninfo_to_dict(dsn)
    except (PsycopgError, TypeError, ValueError):
        raise LegacyMigrationError("DSN legado invalido") from None

    host = _required_text(parsed, "host")
    database = _required_text(parsed, "dbname")
    username = _required_text(parsed, "user")
    password = _required_text(parsed, "password")
    if "," in host:
        raise LegacyMigrationError("DSN legado com destinos multiplos")
    port = _single_port(parsed)

    try:
        raw_config = deserialize(read_config_text(config_path))
        file_config = validate_file_config(raw_config)
        policy = DatasourcePolicy.from_mapping(file_config.model_dump(mode="json"))
    except (ConfigError, DatasourceValidationError, OSError, TypeError, ValueError):
        raise LegacyMigrationError("configuracao legada invalida") from None

    draft = DatasourceDraft(
        alias=alias,
        display_name=display_name if display_name is not None else alias,
        host=host,
        port=port,
        database=database,
        username=username,
        policy=policy,
        destination_policy=destination_policy or DestinationPolicy(),
    )
    try:
        return catalog.create(draft, password, resolver=resolver)
    except CatalogStoreError:
        raise LegacyMigrationError("migracao legada recusada") from None
