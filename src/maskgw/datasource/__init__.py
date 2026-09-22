"""Catalogo local de datasources da Etapa 2.

Este pacote nao publica listener, registry, Admin API ou mudanca no MCP. Ele
fornece somente modelos, destino validado, cifragem e persistencia explicita.
"""

from maskgw.datasource.crypto import CryptoValidationError
from maskgw.datasource.destination import (
    DestinationChangedError,
    DestinationValidationError,
    ResolvedDestination,
    resolve_destination,
)
from maskgw.datasource.migration import migrate_legacy_datasource
from maskgw.datasource.models import (
    CatalogSnapshot,
    DatasourceDraft,
    DatasourceIdError,
    DatasourceLimits,
    DatasourceRecord,
    DatasourceValidationError,
    DestinationPolicy,
    EncryptedSecret,
    LastTest,
    TlsSettings,
)
from maskgw.datasource.store import (
    CatalogAlreadyExistsError,
    CatalogAnchorError,
    CatalogCorruptError,
    CatalogHooks,
    CatalogKeyError,
    CatalogOutcomeUncertainError,
    CatalogRevisionConflictError,
    CatalogRotationPendingError,
    CatalogStore,
    CatalogStoreError,
    CatalogWriteError,
    CrashPoint,
    FilesystemPolicyError,
    LegacyMigrationError,
    MasterKeyError,
    MasterKeyRotationStatus,
)

__all__ = [
    "CatalogAlreadyExistsError",
    "CatalogAnchorError",
    "CatalogCorruptError",
    "CatalogHooks",
    "CatalogKeyError",
    "CatalogOutcomeUncertainError",
    "CatalogRevisionConflictError",
    "CatalogRotationPendingError",
    "CatalogSnapshot",
    "CatalogStore",
    "CatalogStoreError",
    "CatalogWriteError",
    "CrashPoint",
    "CryptoValidationError",
    "DatasourceDraft",
    "DatasourceIdError",
    "DatasourceLimits",
    "DatasourceRecord",
    "DatasourceValidationError",
    "DestinationChangedError",
    "DestinationPolicy",
    "DestinationValidationError",
    "EncryptedSecret",
    "FilesystemPolicyError",
    "LastTest",
    "LegacyMigrationError",
    "MasterKeyError",
    "MasterKeyRotationStatus",
    "ResolvedDestination",
    "TlsSettings",
    "migrate_legacy_datasource",
    "resolve_destination",
]
