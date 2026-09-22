"""Gates adversariais da Etapa 2: catálogo, cifragem, replay e migração."""

from __future__ import annotations

import errno
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from typing import Literal

import pytest

from maskgw.datasource import (
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
    DatasourceDraft,
    DatasourceRecord,
    DatasourceValidationError,
    DestinationChangedError,
    DestinationPolicy,
    LegacyMigrationError,
    MasterKeyError,
    MasterKeyRotationStatus,
    migrate_legacy_datasource,
)
from maskgw.datasource.crypto import (
    CATALOG_SCHEMA_VERSION,
    CryptoValidationError,
    open_secret,
    seal_secret,
)
from maskgw.datasource.destination import resolve_destination
from maskgw.datasource.models import EncryptedSecret, decode_b64
from maskgw.secretsource import MappingSecretProvider

KEY = "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
ROTATED_KEY = "ffeeddccbbaa99887766554433221100ffeeddccbbaa99887766554433221100"
WRONG_KEY = "0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c4b5a69788796a5b4c3d2e1f0"
TEST_SECRET = "synthetic-upstream-fixture-value"  # noqa: S105 - test-only marker


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "datasources.store", tmp_path / "private-anchor" / "datasources.anchor"


def _draft(*, alias: str = "primary", display_name: str = "Primary") -> DatasourceDraft:
    return DatasourceDraft(
        alias=alias,
        display_name=display_name,
        host="db.internal.example",
        port=5432,
        database="app",
        username="gateway",
    )


def _resolver(_host: str, _port: int) -> tuple[str, ...]:
    return ("10.0.0.7",)


def _new_catalog(tmp_path: Path) -> tuple[CatalogStore, Path, Path]:
    store_path, anchor_path = _paths(tmp_path)
    catalog = CatalogStore.initialize(store_path, anchor_path=anchor_path, master_key=KEY)
    return catalog, store_path, anchor_path


def _interrupted_initialization(tmp_path: Path, crash_point: CrashPoint) -> tuple[Path, Path]:
    store_path, anchor_path = _paths(tmp_path)

    def crash(point: CrashPoint) -> None:
        if point == crash_point:
            raise CatalogWriteError("synthetic initialization boundary")

    with pytest.raises(CatalogWriteError):
        CatalogStore.initialize(
            store_path,
            anchor_path=anchor_path,
            master_key=KEY,
            hooks=CatalogHooks(after_point=crash),
        )
    return store_path, anchor_path


def test_create_persists_ciphertext_only_and_reopens(tmp_path: Path) -> None:
    catalog, store_path, anchor_path = _new_catalog(tmp_path)
    try:
        record = catalog.create(_draft(), TEST_SECRET, resolver=_resolver)
        assert record.secret_configured
        assert "upstream_secret=<redacted>" in repr(record)
        assert TEST_SECRET not in store_path.read_text(encoding="utf-8")
        assert TEST_SECRET not in anchor_path.read_text(encoding="utf-8")
        revision = catalog.revision
    finally:
        catalog.close()

    with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY) as reopened:
        assert reopened.revision == revision
        assert reopened.by_alias("primary").id == record.id
        assert reopened.read_upstream_secret(record.id) == TEST_SECRET


def test_wrong_key_tamper_and_anchor_transplant_fail_closed(tmp_path: Path) -> None:
    catalog, store_path, anchor_path = _new_catalog(tmp_path)
    catalog.create(_draft(), TEST_SECRET, resolver=_resolver)
    catalog.close()

    with pytest.raises((CatalogKeyError, MasterKeyError)):
        CatalogStore.open(store_path, anchor_path=anchor_path, master_key=ROTATED_KEY)

    original_store = store_path.read_bytes()
    store_path.write_bytes(original_store[:-1] + bytes([original_store[-1] ^ 1]))
    with pytest.raises((CatalogKeyError, CatalogCorruptError)):
        CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY)
    store_path.write_bytes(original_store)

    transplanted_anchor = tmp_path / "transplanted" / "datasources.anchor"
    transplanted_anchor.parent.mkdir()
    transplanted_anchor.write_bytes(anchor_path.read_bytes())
    anchor_path.write_text(
        '{"catalog_digest":"' + "0" * 64 + '","catalog_revision":1,"format":1}',
        encoding="utf-8",
    )
    with pytest.raises(CatalogAnchorError):
        CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY)


def test_revision_conflict_and_immutable_snapshot(tmp_path: Path) -> None:
    catalog, _store_path, _anchor_path = _new_catalog(tmp_path)
    try:
        record = catalog.create(_draft(), TEST_SECRET, resolver=_resolver)
        updated = catalog.update(
            record.id,
            _draft(display_name="Updated"),
            expected_revision=catalog.revision,
            resolver=_resolver,
        )
        assert updated.display_name == "Updated"
        assert catalog.read_upstream_secret(record.id) == TEST_SECRET
        snapshot = catalog.snapshot()
        with pytest.raises(CatalogRevisionConflictError):
            catalog.rotate_secret(record.id, "another-synthetic-secret", expected_revision=1)
        assert snapshot.catalog_revision == 3
        assert snapshot.datasources[0].revision == 2
        with pytest.raises(AttributeError):
            snapshot.datasources.append(record)  # type: ignore[attr-defined]
    finally:
        catalog.close()


def test_concurrent_creates_at_same_revision_serialize_without_lost_update(
    tmp_path: Path,
) -> None:
    catalog, store_path, anchor_path = _new_catalog(tmp_path)
    start = Barrier(3)

    def create(alias: str) -> str:
        start.wait(timeout=5)
        try:
            catalog.create(
                _draft(alias=alias),
                TEST_SECRET,
                expected_revision=1,
                resolver=_resolver,
            )
            return "created"
        except CatalogRevisionConflictError:
            return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(create, alias) for alias in ("first", "second")]
            start.wait(timeout=5)
            outcomes = [future.result(timeout=10) for future in futures]

        assert outcomes.count("created") == 1
        assert outcomes.count("conflict") == 1
        snapshot = catalog.snapshot()
        assert snapshot.catalog_revision == 2
        assert len(snapshot.datasources) == 1
        stored = json.loads(store_path.read_text(encoding="utf-8"))
        anchored = json.loads(anchor_path.read_text(encoding="utf-8"))
        assert stored["catalog_revision"] == snapshot.catalog_revision
        assert anchored["catalog_revision"] == snapshot.catalog_revision
        assert anchored["catalog_digest"] == snapshot.digest
        assert [item["alias"] for item in stored["datasources"]] == [snapshot.datasources[0].alias]
        catalog.close()
        with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY) as reopened:
            assert reopened.snapshot() == snapshot
    finally:
        catalog.close()


def test_concurrent_create_and_key_rotation_keep_one_coherent_generation(
    tmp_path: Path,
) -> None:
    catalog, store_path, anchor_path = _new_catalog(tmp_path)
    start = Barrier(3)

    def create() -> str:
        start.wait(timeout=5)
        try:
            catalog.create(_draft(), TEST_SECRET, expected_revision=1, resolver=_resolver)
            return "created"
        except CatalogRevisionConflictError:
            return "conflict"

    def rotate() -> str:
        start.wait(timeout=5)
        catalog.rotate_master_key(ROTATED_KEY)
        return "rotated"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            create_future = executor.submit(create)
            rotate_future = executor.submit(rotate)
            start.wait(timeout=5)
            create_result = create_future.result(timeout=10)
            assert rotate_future.result(timeout=10) == "rotated"

        final = catalog.snapshot()
        assert final.catalog_revision == (3 if create_result == "created" else 2)
        assert len(final.datasources) == (1 if create_result == "created" else 0)
        stored = json.loads(store_path.read_text(encoding="utf-8"))
        anchored = json.loads(anchor_path.read_text(encoding="utf-8"))
        assert stored["catalog_revision"] == final.catalog_revision
        assert anchored["catalog_revision"] == final.catalog_revision
        assert anchored["catalog_digest"] == final.digest
        catalog.close()
        with CatalogStore.open(
            store_path, anchor_path=anchor_path, master_key=ROTATED_KEY
        ) as reopened:
            assert reopened.snapshot() == final
            if final.datasources:
                assert reopened.read_upstream_secret(final.datasources[0].id) == TEST_SECRET
        with pytest.raises(CatalogKeyError):
            CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY)
    finally:
        catalog.close()


def test_close_waits_for_in_progress_persistence(tmp_path: Path) -> None:
    store_path, anchor_path = _paths(tmp_path)
    write_paused = Event()
    release_write = Event()
    close_started = Event()
    close_finished = Event()

    def pause_after_journal(point: CrashPoint) -> None:
        if point == CrashPoint.AFTER_JOURNAL_FSYNC:
            write_paused.set()
            if not release_write.wait(timeout=5):
                raise CatalogWriteError("synthetic write release timeout")

    initialized = CatalogStore.initialize(
        store_path,
        anchor_path=anchor_path,
        master_key=KEY,
    )
    initialized.close()
    catalog = CatalogStore.open(
        store_path,
        anchor_path=anchor_path,
        master_key=KEY,
        hooks=CatalogHooks(after_point=pause_after_journal),
    )

    def write() -> DatasourceRecord:
        return catalog.create(_draft(), TEST_SECRET, resolver=_resolver)

    def close() -> None:
        close_started.set()
        catalog.close()
        close_finished.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        write_future = executor.submit(write)
        try:
            assert write_paused.wait(timeout=5)
            close_future = executor.submit(close)
            assert close_started.wait(timeout=5)
            assert not close_finished.wait(timeout=0.1)
            release_write.set()
            created = write_future.result(timeout=10)
            close_future.result(timeout=10)
            assert close_finished.is_set()
            assert catalog.closed
            with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY) as reopened:
                assert reopened.revision == 2
                assert reopened.get(created.id).alias == "primary"
        finally:
            release_write.set()
            if not write_future.done():
                write_future.result(timeout=10)


def test_rotation_requires_new_key_and_reencrypts_all_secrets(tmp_path: Path) -> None:
    catalog, store_path, anchor_path = _new_catalog(tmp_path)
    record = catalog.create(_draft(), TEST_SECRET, resolver=_resolver)
    catalog.update(record.id, _draft(display_name="Two"), expected_revision=2, resolver=_resolver)
    assert _backups(store_path) == ["datasources.store.bak.1", "datasources.store.bak.2"]
    catalog.rotate_master_key(ROTATED_KEY)
    catalog.close()

    assert _backups(store_path) == []
    assert _readable_with(KEY, store_path.parent, anchor_path.parent) == []
    assert _readable_with(ROTATED_KEY, store_path.parent, anchor_path.parent) == [
        "datasources.store"
    ]
    assert not anchor_path.with_name("datasources.anchor.txn").exists()
    with pytest.raises(CatalogKeyError):
        CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY)
    with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=ROTATED_KEY) as reopened:
        assert reopened.read_upstream_secret(record.id) == TEST_SECRET


@pytest.mark.parametrize(
    "crash_point",
    [
        CrashPoint.AFTER_JOURNAL_FSYNC,
        CrashPoint.AFTER_STORE_DIRECTORY_FSYNC,
        CrashPoint.AFTER_STORE_REPLACE,
        CrashPoint.AFTER_ANCHOR_DIRECTORY_FSYNC,
        CrashPoint.AFTER_ANCHOR_REPLACE,
    ],
)
def test_crash_recovery_reconciles_every_commit_boundary(
    tmp_path: Path, crash_point: CrashPoint
) -> None:
    catalog, store_path, anchor_path = _new_catalog(tmp_path)
    catalog.close()

    def crash(point: CrashPoint) -> None:
        if point == crash_point:
            raise CatalogWriteError("synthetic crash boundary")

    hooks = CatalogHooks(after_point=crash)
    with (
        CatalogStore.open(
            store_path,
            anchor_path=anchor_path,
            master_key=KEY,
            hooks=hooks,
        ) as active,
        pytest.raises(CatalogWriteError),
    ):
        active.create(_draft(), TEST_SECRET, resolver=_resolver)

    with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY) as recovered:
        expected_count = 0 if crash_point == CrashPoint.AFTER_JOURNAL_FSYNC else 1
        assert len(recovered.snapshot().datasources) == expected_count
        assert not anchor_path.with_name("datasources.anchor.txn").exists()


@pytest.mark.parametrize(
    ("crash_point", "opens_after_recovery"),
    [
        (CrashPoint.AFTER_JOURNAL_FSYNC, False),
        (CrashPoint.AFTER_STORE_DIRECTORY_FSYNC, True),
        (CrashPoint.AFTER_STORE_REPLACE, True),
        (CrashPoint.AFTER_ANCHOR_DIRECTORY_FSYNC, True),
        (CrashPoint.AFTER_ANCHOR_REPLACE, True),
    ],
)
def test_initialization_recovery_boundaries(
    tmp_path: Path, crash_point: CrashPoint, opens_after_recovery: bool
) -> None:
    store_path, anchor_path = _interrupted_initialization(tmp_path, crash_point)
    journal_path = anchor_path.with_name("datasources.anchor.txn")
    assert journal_path.exists()
    if not opens_after_recovery:
        with pytest.raises(CatalogAnchorError):
            CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY)
        assert not store_path.exists()
        assert not anchor_path.exists()
    else:
        with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY) as recovered:
            assert recovered.revision == 1
            assert recovered.snapshot().datasources == ()
        assert not journal_path.exists()
        with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY) as reopened:
            assert reopened.revision == 1
            assert reopened.snapshot().datasources == ()


@pytest.mark.parametrize(
    "mutation",
    ["truncated", "noncanonical", "tampered"],
)
def test_initialization_invalid_journal_never_repairs_missing_anchor(
    tmp_path: Path, mutation: str
) -> None:
    store_path, anchor_path = _interrupted_initialization(tmp_path, CrashPoint.AFTER_STORE_REPLACE)
    journal_path = anchor_path.with_name("datasources.anchor.txn")
    journal = journal_path.read_bytes()
    if mutation == "truncated":
        journal_path.write_bytes(journal[:-1])
    elif mutation == "noncanonical":
        journal_path.write_bytes(journal + b" ")
    else:
        journal_path.write_bytes(journal[:-1] + bytes([journal[-1] ^ 1]))
    with pytest.raises((CatalogAnchorError, CatalogCorruptError, CatalogKeyError)):
        CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY)
    assert store_path.exists()
    assert not anchor_path.exists()
    assert journal_path.exists()


def test_initialization_wrong_key_never_repairs_missing_anchor(tmp_path: Path) -> None:
    store_path, anchor_path = _interrupted_initialization(tmp_path, CrashPoint.AFTER_STORE_REPLACE)
    with pytest.raises(CatalogKeyError):
        CatalogStore.open(store_path, anchor_path=anchor_path, master_key=ROTATED_KEY)
    assert store_path.exists()
    assert not anchor_path.exists()


def test_normal_update_with_missing_anchor_is_not_inferred_as_initialization(
    tmp_path: Path,
) -> None:
    catalog, store_path, anchor_path = _new_catalog(tmp_path)
    catalog.close()

    def crash(point: CrashPoint) -> None:
        if point == CrashPoint.AFTER_STORE_REPLACE:
            raise CatalogWriteError("synthetic normal update boundary")

    active = CatalogStore.open(
        store_path,
        anchor_path=anchor_path,
        master_key=KEY,
        hooks=CatalogHooks(after_point=crash),
    )
    anchor_path.unlink()
    with pytest.raises(CatalogWriteError):
        active.create(_draft(), TEST_SECRET, resolver=_resolver)
    active.close()

    with pytest.raises(CatalogAnchorError):
        CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY)
    assert store_path.exists()
    assert not anchor_path.exists()
    assert anchor_path.with_name("datasources.anchor.txn").exists()


def test_incomplete_pair_without_journal_fails_closed(tmp_path: Path) -> None:
    catalog, store_path, anchor_path = _new_catalog(tmp_path)
    catalog.close()
    anchor_path.unlink()
    with pytest.raises(CatalogAnchorError):
        CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY)
    with pytest.raises(CatalogAlreadyExistsError):
        CatalogStore.initialize(store_path, anchor_path=anchor_path, master_key=KEY)
    assert store_path.exists()
    assert not anchor_path.exists()


@pytest.mark.parametrize(
    "crash_point", [CrashPoint.AFTER_STORE_REPLACE, CrashPoint.AFTER_ANCHOR_REPLACE]
)
def test_failed_replace_poisoned_object_requires_reopen(
    tmp_path: Path, crash_point: CrashPoint
) -> None:
    catalog, store_path, anchor_path = _new_catalog(tmp_path)
    catalog.close()

    def crash(point: CrashPoint) -> None:
        if point == crash_point:
            raise CatalogWriteError("synthetic write boundary")

    active = CatalogStore.open(
        store_path,
        anchor_path=anchor_path,
        master_key=KEY,
        hooks=CatalogHooks(after_point=crash),
    )
    try:
        with pytest.raises(CatalogWriteError) as error:
            active.create(_draft(), TEST_SECRET, resolver=_resolver)
        assert TEST_SECRET not in repr(active)
        assert TEST_SECRET not in str(error.value)
        with pytest.raises(CatalogWriteError):
            active.create(_draft(alias="second"), TEST_SECRET, resolver=_resolver)
        for path in (*store_path.parent.iterdir(), *anchor_path.parent.iterdir()):
            if path.is_file() and not path.name.endswith(".lock"):
                assert TEST_SECRET.encode() not in path.read_bytes()
    finally:
        active.close()

    with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY) as recovered:
        assert len(recovered.snapshot().datasources) == 1


def test_recovery_does_not_remove_unknown_files(tmp_path: Path) -> None:
    store_path, anchor_path = _interrupted_initialization(tmp_path, CrashPoint.AFTER_STORE_REPLACE)
    store_unknown = store_path.parent / "operator-note.txt"
    anchor_unknown = anchor_path.parent / "operator-note.txt"
    store_unknown.write_text("preserve", encoding="utf-8")
    anchor_unknown.write_text("preserve", encoding="utf-8")
    with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY):
        pass
    assert store_unknown.read_text(encoding="utf-8") == "preserve"
    assert anchor_unknown.read_text(encoding="utf-8") == "preserve"


def test_lock_rejects_second_writer(tmp_path: Path) -> None:
    first, store_path, anchor_path = _new_catalog(tmp_path)
    try:
        with pytest.raises(CatalogAnchorError):
            CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY)
    finally:
        first.close()


def test_dns_pinning_and_ssrf_policy() -> None:
    policy = DestinationPolicy()
    assert resolve_destination(
        "db.internal.example", 5432, policy=policy, resolver=lambda _h, _p: ("10.0.0.7",)
    ).addresses == ("10.0.0.7",)
    with pytest.raises(DatasourceValidationError):
        resolve_destination(
            "169.254.169.254", 5432, policy=policy, resolver=lambda _h, _p: ("169.254.169.254",)
        )
    with pytest.raises(DestinationChangedError):
        resolve_destination(
            "db.internal.example",
            5432,
            policy=policy,
            resolver=lambda _h, _p: ("10.0.0.8",),
            expected_addresses=("10.0.0.7",),
        )


def test_migration_is_explicit_and_does_not_touch_legacy_file(tmp_path: Path) -> None:
    catalog, store_path, anchor_path = _new_catalog(tmp_path)
    config_path = tmp_path / "masking.yaml"
    config_bytes = b"masking: []\nexceptions: []\n"
    config_path.write_bytes(config_bytes)
    provider = MappingSecretProvider(
        {
            "MASKGW_DATABASE_DSN": (
                "host=db.internal.example port=5432 dbname=app user=gateway password=fixture"
            )
        }
    )
    try:
        record = migrate_legacy_datasource(
            catalog,
            alias="legacy",
            config_path=config_path,
            secrets_provider=provider,
            resolver=_resolver,
        )
        assert record.alias == "legacy"
        assert config_path.read_bytes() == config_bytes
        assert "fixture" not in store_path.read_text(encoding="utf-8")
        assert anchor_path.exists()
    finally:
        catalog.close()


def test_migration_is_not_automatic_when_dsn_is_absent(tmp_path: Path) -> None:
    catalog, _store_path, _anchor_path = _new_catalog(tmp_path)
    try:
        with pytest.raises(LegacyMigrationError):
            migrate_legacy_datasource(
                catalog,
                alias="legacy",
                config_path=tmp_path / "missing.yaml",
                secrets_provider=MappingSecretProvider({}),
            )
    finally:
        catalog.close()


def test_secret_and_paths_are_not_in_repr_or_errors(tmp_path: Path) -> None:
    catalog, _store_path, _anchor_path = _new_catalog(tmp_path)
    try:
        with pytest.raises(CatalogStoreError) as error:
            catalog.read_upstream_secret("dso_" + "0" * 32)
        rendered = repr(catalog) + str(error.value)
        assert TEST_SECRET not in rendered
        assert KEY not in rendered
    finally:
        catalog.close()


# --------------------------------------------------------------------------
# Rotação de master key: resultado incerto e recuperação explícita (D-081/D-082)
# --------------------------------------------------------------------------
#
# Cada limite de crash deixa um estado persistido diferente. A tabela registra o
# estado e a chave que o autentica; os testes abaixo provam que nenhuma
# tentativa com chave única consome o journal ou avança a âncora enquanto o
# resultado é incerto, e que a recuperação explícita com as duas chaves
# determina o mesmo resultado de forma idempotente.

ROTATION_BOUNDARIES: dict[CrashPoint, tuple[str, bool, Literal["old", "new"], int]] = {
    # ponto: (estado store/âncora, journal pendente, chave confirmada, revision)
    CrashPoint.AFTER_JOURNAL_FSYNC: ("old/old", True, "old", 2),
    CrashPoint.AFTER_STORE_DIRECTORY_FSYNC: ("new/old", True, "new", 3),
    CrashPoint.AFTER_STORE_REPLACE: ("new/old", True, "new", 3),
    CrashPoint.AFTER_ANCHOR_DIRECTORY_FSYNC: ("new/new", True, "new", 3),
    CrashPoint.AFTER_ANCHOR_REPLACE: ("new/new", True, "new", 3),
    CrashPoint.AFTER_BACKUP_PURGE: ("new/new", True, "new", 3),
    CrashPoint.AFTER_JOURNAL_CLEANUP: ("new/new", False, "new", 3),
}
BACKUPS_BEFORE_ROTATION = ["datasources.store.bak.1", "datasources.store.bak.2"]
# bak.1 é o catálogo vazio da revision 1; só bak.2 tem segredo sob a chave antiga.
OLD_KEY_READABLE_BACKUPS = ["datasources.store.bak.2"]
PURGED_BOUNDARIES = {CrashPoint.AFTER_BACKUP_PURGE, CrashPoint.AFTER_JOURNAL_CLEANUP}
PENDING_ROTATION_BOUNDARIES = [
    point for point, (_state, pending, _key, _rev) in ROTATION_BOUNDARIES.items() if pending
]
KEYS = {"old": KEY, "new": ROTATED_KEY, "wrong": WRONG_KEY}


def _rotation_fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    catalog, store_path, anchor_path = _new_catalog(tmp_path)
    try:
        record = catalog.create(_draft(), TEST_SECRET, resolver=_resolver)
        assert catalog.revision == 2
    finally:
        catalog.close()
    return store_path, anchor_path, record.id


def _files(*directories: Path) -> dict[str, bytes | None]:
    """Estado persistido dos diretórios; locks sidecar comparados só por presença.

    Com o catálogo aberto no Windows, ``msvcrt.locking`` mantém o byte do lock
    travado e ler o arquivo levanta ``PermissionError``. O conteúdo do lock não
    é estado do catálogo: store, âncora, journal, backups e temporários seguem
    comparados byte a byte, e cada lock continua na comparação pelo nome.
    """
    return {
        f"{directory.name}/{path.name}": (
            None if path.name.endswith(".lock") else path.read_bytes()
        )
        for directory in directories
        for path in sorted(directory.iterdir())
        if path.is_file()
    }


def _backups(store_path: Path) -> list[str]:
    """Backups gerenciados presentes: nome estrito do protocolo e arquivo regular."""
    return sorted(
        path.name
        for path in store_path.parent.iterdir()
        if re.fullmatch(r"datasources\.store\.bak\.[1-9][0-9]*", path.name) and path.is_file()
    )


def _backups_before_commit(crash_point: CrashPoint) -> list[str]:
    """O backup da própria rotação só existe depois do journal durável."""
    if crash_point == CrashPoint.AFTER_JOURNAL_FSYNC:
        return BACKUPS_BEFORE_ROTATION[:1]
    return BACKUPS_BEFORE_ROTATION


def _readable_with(key: str, *directories: Path) -> list[str]:
    """Arquivos cujo envelope de algum datasource ainda abre com ``key``."""
    readable: list[str] = []
    for directory in directories:
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.is_symlink() or path.name.endswith(".lock"):
                continue
            try:
                document = json.loads(path.read_bytes())
            except (UnicodeDecodeError, ValueError):
                continue
            if not isinstance(document, dict) or not isinstance(document.get("datasources"), list):
                continue
            for item in document["datasources"]:
                envelope = item["upstream_secret"]
                try:
                    open_secret(
                        EncryptedSecret(
                            "AES-256-GCM",
                            1,
                            decode_b64(envelope["nonce"]),
                            decode_b64(envelope["ciphertext"]),
                        ),
                        master_key=bytes.fromhex(key),
                        datasource_id=item["id"],
                        schema_version=CATALOG_SCHEMA_VERSION,
                        revision=item["revision"],
                    )
                except ValueError:
                    continue
                readable.append(path.name)
                break
    return readable


def _revisions(store_path: Path, anchor_path: Path) -> tuple[int, int]:
    stored = json.loads(store_path.read_text(encoding="utf-8"))
    anchored = json.loads(anchor_path.read_text(encoding="utf-8"))
    return stored["catalog_revision"], anchored["catalog_revision"]


def _assert_sanitized(text: str, store_path: Path, anchor_path: Path) -> None:
    stored = json.loads(store_path.read_text(encoding="utf-8"))
    envelopes = [item["upstream_secret"] for item in stored["datasources"]]
    forbidden = [
        KEY,
        ROTATED_KEY,
        WRONG_KEY,
        TEST_SECRET,
        "db.internal.example",
        "10.0.0.7",
        str(store_path),
        str(anchor_path),
        *(envelope["ciphertext"] for envelope in envelopes),
        *(envelope["nonce"] for envelope in envelopes),
    ]
    for value in forbidden:
        assert value not in text


def _interrupted_rotation(tmp_path: Path, crash_point: CrashPoint) -> tuple[Path, Path, str]:
    store_path, anchor_path, record_id = _rotation_fixture(tmp_path)

    def crash(point: CrashPoint) -> None:
        if point == crash_point:
            raise CatalogWriteError("synthetic rotation boundary")

    active = CatalogStore.open(
        store_path,
        anchor_path=anchor_path,
        master_key=KEY,
        hooks=CatalogHooks(after_point=crash),
    )
    try:
        with pytest.raises(CatalogWriteError) as error:
            active.rotate_master_key(ROTATED_KEY)
        uncertain = crash_point != CrashPoint.AFTER_JOURNAL_FSYNC
        assert isinstance(error.value, CatalogOutcomeUncertainError) is uncertain
        if uncertain:
            assert error.value.__cause__ is None
            assert error.value.__context__ is None
        _assert_sanitized(str(error.value) + repr(active), store_path, anchor_path)
        with pytest.raises(CatalogWriteError):
            active.create(_draft(alias="blocked"), TEST_SECRET, resolver=_resolver)
    finally:
        active.close()
    state, pending, _key, _revision = ROTATION_BOUNDARIES[crash_point]
    journal_path = anchor_path.with_name("datasources.anchor.txn")
    assert journal_path.exists() is pending
    store_revision, anchor_revision = _revisions(store_path, anchor_path)
    expected_store, expected_anchor = state.split("/")
    assert store_revision == (2 if expected_store == "old" else 3)
    assert anchor_revision == (2 if expected_anchor == "old" else 3)
    if crash_point in PURGED_BOUNDARIES:
        assert _backups(store_path) == []
        assert _readable_with(KEY, store_path.parent, anchor_path.parent) == []
    else:
        assert _backups(store_path) == _backups_before_commit(crash_point)
    for path in (*store_path.parent.iterdir(), *anchor_path.parent.iterdir()):
        if path.is_file():
            assert TEST_SECRET.encode() not in path.read_bytes()
    return store_path, anchor_path, record_id


def _single_key_open_outcome(crash_point: CrashPoint, key_name: str) -> str:
    state, pending, _key, _revision = ROTATION_BOUNDARIES[crash_point]
    if key_name == "wrong":
        return "key_error"
    if not pending:
        return "opens" if key_name == "new" else "key_error"
    if state == "old/old" and key_name == "old":
        return "opens"
    if state == "new/new" and key_name == "new":
        return "opens"
    return "pending"


@pytest.mark.parametrize("key_name", ["old", "new", "wrong"])
@pytest.mark.parametrize("crash_point", list(ROTATION_BOUNDARIES))
def test_interrupted_rotation_single_key_open_never_consumes_uncertain_state(
    tmp_path: Path, crash_point: CrashPoint, key_name: str
) -> None:
    store_path, anchor_path, record_id = _interrupted_rotation(tmp_path, crash_point)
    journal_path = anchor_path.with_name("datasources.anchor.txn")
    before = _files(store_path.parent, anchor_path.parent)
    revisions_before = _revisions(store_path, anchor_path)
    outcome = _single_key_open_outcome(crash_point, key_name)
    _state, _pending, confirmed, expected_revision = ROTATION_BOUNDARIES[crash_point]

    if outcome == "opens":
        with CatalogStore.open(
            store_path, anchor_path=anchor_path, master_key=KEYS[key_name]
        ) as opened:
            assert key_name == confirmed
            assert opened.revision == expected_revision
            assert opened.read_upstream_secret(record_id) == TEST_SECRET
        assert not journal_path.exists()
        store_revision, anchor_revision = _revisions(store_path, anchor_path)
        assert store_revision == anchor_revision == expected_revision
        assert anchor_revision >= revisions_before[1]
        if key_name == "new":
            assert _backups(store_path) == []
            assert _readable_with(KEY, store_path.parent, anchor_path.parent) == []
        else:
            assert _backups(store_path) == _backups_before_commit(crash_point)
        return

    expected_error = CatalogRotationPendingError if outcome == "pending" else CatalogKeyError
    with pytest.raises(expected_error) as error:
        CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEYS[key_name])
    assert error.value.__cause__ is None
    _assert_sanitized(str(error.value), store_path, anchor_path)
    assert _files(store_path.parent, anchor_path.parent) == before
    assert _revisions(store_path, anchor_path) == revisions_before


@pytest.mark.parametrize("crash_point", list(ROTATION_BOUNDARIES))
def test_explicit_rotation_recovery_determines_key_and_is_idempotent(
    tmp_path: Path, crash_point: CrashPoint
) -> None:
    store_path, anchor_path, record_id = _interrupted_rotation(tmp_path, crash_point)
    journal_path = anchor_path.with_name("datasources.anchor.txn")
    _state, pending, confirmed, expected_revision = ROTATION_BOUNDARIES[crash_point]
    before = _files(store_path.parent, anchor_path.parent)
    anchor_before = _revisions(store_path, anchor_path)[1]

    inspected = CatalogStore.inspect_master_key_rotation(
        store_path, anchor_path=anchor_path, old_master_key=KEY, new_master_key=ROTATED_KEY
    )
    assert inspected == MasterKeyRotationStatus(confirmed, expected_revision, pending)
    assert _files(store_path.parent, anchor_path.parent) == before
    _assert_sanitized(repr(inspected), store_path, anchor_path)

    recovered = CatalogStore.recover_master_key_rotation(
        store_path, anchor_path=anchor_path, old_master_key=KEY, new_master_key=ROTATED_KEY
    )
    assert recovered == MasterKeyRotationStatus(confirmed, expected_revision, False)
    assert not journal_path.exists()
    if confirmed == "new":
        assert _backups(store_path) == []
        assert _readable_with(KEY, store_path.parent, anchor_path.parent) == []
    else:
        assert _backups(store_path) == _backups_before_commit(crash_point)
        for name in _backups_before_commit(crash_point):
            key_name = f"{store_path.parent.name}/{name}"
            assert (store_path.parent / name).read_bytes() == before[key_name]
    store_revision, anchor_revision = _revisions(store_path, anchor_path)
    assert store_revision == anchor_revision == expected_revision
    assert anchor_revision >= anchor_before
    after_first = _files(store_path.parent, anchor_path.parent)

    repeated = CatalogStore.recover_master_key_rotation(
        store_path, anchor_path=anchor_path, old_master_key=KEY, new_master_key=ROTATED_KEY
    )
    assert repeated == recovered
    assert _files(store_path.parent, anchor_path.parent) == after_first
    assert (
        CatalogStore.inspect_master_key_rotation(
            store_path, anchor_path=anchor_path, old_master_key=KEY, new_master_key=ROTATED_KEY
        )
        == recovered
    )

    confirmed_key = KEYS[confirmed]
    other_key = KEYS["new" if confirmed == "old" else "old"]
    with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=confirmed_key) as done:
        assert done.revision == expected_revision
        assert done.read_upstream_secret(record_id) == TEST_SECRET
    settled = _files(store_path.parent, anchor_path.parent)
    with pytest.raises(CatalogKeyError):
        CatalogStore.open(store_path, anchor_path=anchor_path, master_key=other_key)
    assert _files(store_path.parent, anchor_path.parent) == settled


@pytest.mark.parametrize(
    ("old_key", "new_key", "error"),
    [
        (KEY, WRONG_KEY, CatalogKeyError),
        (WRONG_KEY, ROTATED_KEY, CatalogKeyError),
        (ROTATED_KEY, KEY, CatalogKeyError),
        (KEY, KEY, MasterKeyError),
        ("not-a-key", ROTATED_KEY, MasterKeyError),
    ],
    ids=["wrong-new", "wrong-old", "swapped", "equal", "malformed"],
)
@pytest.mark.parametrize("crash_point", PENDING_ROTATION_BOUNDARIES)
def test_rotation_recovery_with_wrong_keys_never_mutates(
    tmp_path: Path,
    crash_point: CrashPoint,
    old_key: str,
    new_key: str,
    error: type[CatalogStoreError],
) -> None:
    store_path, anchor_path, _record_id = _interrupted_rotation(tmp_path, crash_point)
    before = _files(store_path.parent, anchor_path.parent)
    for operation in (
        CatalogStore.inspect_master_key_rotation,
        CatalogStore.recover_master_key_rotation,
    ):
        with pytest.raises(error) as raised:
            operation(
                store_path,
                anchor_path=anchor_path,
                old_master_key=old_key,
                new_master_key=new_key,
            )
        assert raised.value.__cause__ is None
        _assert_sanitized(str(raised.value), store_path, anchor_path)
        assert _files(store_path.parent, anchor_path.parent) == before


def test_rotation_recovery_without_journal_rejects_keys_that_do_not_authenticate(
    tmp_path: Path,
) -> None:
    store_path, anchor_path, _record_id = _interrupted_rotation(
        tmp_path, CrashPoint.AFTER_JOURNAL_CLEANUP
    )
    before = _files(store_path.parent, anchor_path.parent)
    with pytest.raises(CatalogKeyError):
        CatalogStore.recover_master_key_rotation(
            store_path, anchor_path=anchor_path, old_master_key=KEY, new_master_key=WRONG_KEY
        )
    assert _files(store_path.parent, anchor_path.parent) == before


@pytest.mark.parametrize(
    "recovery_crash",
    [
        CrashPoint.AFTER_ANCHOR_REPLACE,
        CrashPoint.AFTER_ANCHOR_DIRECTORY_FSYNC,
        CrashPoint.AFTER_JOURNAL_CLEANUP,
    ],
)
def test_interrupted_explicit_recovery_resumes_to_same_result(
    tmp_path: Path, recovery_crash: CrashPoint
) -> None:
    store_path, anchor_path, record_id = _interrupted_rotation(
        tmp_path, CrashPoint.AFTER_STORE_REPLACE
    )

    def crash(point: CrashPoint) -> None:
        if point == recovery_crash:
            raise CatalogWriteError("synthetic recovery boundary")

    with pytest.raises(CatalogWriteError):
        CatalogStore.recover_master_key_rotation(
            store_path,
            anchor_path=anchor_path,
            old_master_key=KEY,
            new_master_key=ROTATED_KEY,
            hooks=CatalogHooks(after_point=crash),
        )
    assert _revisions(store_path, anchor_path) == (3, 3)
    status = CatalogStore.recover_master_key_rotation(
        store_path, anchor_path=anchor_path, old_master_key=KEY, new_master_key=ROTATED_KEY
    )
    assert status == MasterKeyRotationStatus("new", 3, False)
    assert not anchor_path.with_name("datasources.anchor.txn").exists()
    with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=ROTATED_KEY) as done:
        assert done.read_upstream_secret(record_id) == TEST_SECRET


def test_rotation_recovery_is_serialized_with_open_catalog(tmp_path: Path) -> None:
    store_path, anchor_path, _record_id = _rotation_fixture(tmp_path)
    store_lock = store_path.with_name("datasources.store.lock")
    anchor_lock = anchor_path.with_name("datasources.anchor.lock")
    journal_path = anchor_path.with_name("datasources.anchor.txn")
    store_key = f"{store_path.parent.name}/{store_path.name}"
    anchor_key = f"{anchor_path.parent.name}/{anchor_path.name}"
    with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY):
        assert store_lock.is_file()
        assert anchor_lock.is_file()
        before = _files(store_path.parent, anchor_path.parent)
        assert isinstance(before[store_key], bytes)
        assert isinstance(before[anchor_key], bytes)
        assert not journal_path.exists()
        with pytest.raises(CatalogAnchorError):
            CatalogStore.recover_master_key_rotation(
                store_path,
                anchor_path=anchor_path,
                old_master_key=KEY,
                new_master_key=ROTATED_KEY,
            )
        assert _files(store_path.parent, anchor_path.parent) == before
        assert not journal_path.exists()
        assert store_lock.is_file()
        assert anchor_lock.is_file()


def test_rotation_recovery_rejects_tampered_journal_and_regressed_anchor(
    tmp_path: Path,
) -> None:
    store_path, anchor_path, _record_id = _interrupted_rotation(
        tmp_path, CrashPoint.AFTER_STORE_REPLACE
    )
    journal_path = anchor_path.with_name("datasources.anchor.txn")
    journal = journal_path.read_bytes()
    journal_path.write_bytes(journal.replace(b'"new_revision":3', b'"new_revision":4'))
    before = _files(store_path.parent, anchor_path.parent)
    for key in (KEY, ROTATED_KEY):
        with pytest.raises((CatalogAnchorError, CatalogKeyError)):
            CatalogStore.open(store_path, anchor_path=anchor_path, master_key=key)
    with pytest.raises((CatalogAnchorError, CatalogKeyError)):
        CatalogStore.recover_master_key_rotation(
            store_path, anchor_path=anchor_path, old_master_key=KEY, new_master_key=ROTATED_KEY
        )
    assert _files(store_path.parent, anchor_path.parent) == before

    journal_path.write_bytes(journal)
    anchor_path.write_text(
        '{"catalog_digest":"' + "0" * 64 + '","catalog_revision":1,"format":1}',
        encoding="utf-8",
    )
    before = _files(store_path.parent, anchor_path.parent)
    with pytest.raises(CatalogAnchorError):
        CatalogStore.recover_master_key_rotation(
            store_path, anchor_path=anchor_path, old_master_key=KEY, new_master_key=ROTATED_KEY
        )
    assert _files(store_path.parent, anchor_path.parent) == before


@pytest.mark.parametrize(
    ("crash_point", "uncertain"),
    [
        (CrashPoint.AFTER_JOURNAL_FSYNC, False),
        (CrashPoint.AFTER_STORE_REPLACE, True),
        (CrashPoint.AFTER_ANCHOR_REPLACE, True),
        (CrashPoint.AFTER_JOURNAL_CLEANUP, True),
    ],
)
def test_same_key_write_classifies_uncertain_outcome_and_recovers_on_open(
    tmp_path: Path, crash_point: CrashPoint, uncertain: bool
) -> None:
    catalog, store_path, anchor_path = _new_catalog(tmp_path)
    catalog.close()

    def crash(point: CrashPoint) -> None:
        if point == crash_point:
            raise CatalogWriteError("synthetic write boundary")

    with CatalogStore.open(
        store_path, anchor_path=anchor_path, master_key=KEY, hooks=CatalogHooks(after_point=crash)
    ) as active:
        with pytest.raises(CatalogWriteError) as error:
            active.create(_draft(), TEST_SECRET, resolver=_resolver)
        assert isinstance(error.value, CatalogOutcomeUncertainError) is uncertain
    with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY) as recovered:
        assert recovered.revision == (2 if uncertain else 1)
    assert not anchor_path.with_name("datasources.anchor.txn").exists()


# --------------------------------------------------------------------------
# Rotação confirmada remove os backups cifrados com chaves anteriores (D-083)
# --------------------------------------------------------------------------


def _failing_remove(fail_at: int) -> tuple[list[str], object]:
    calls: list[str] = []

    def remove(path: str) -> None:
        calls.append(os.path.basename(path))
        if len(calls) == fail_at:
            raise OSError(errno.EACCES, "synthetic remove failure")
        os.unlink(path)

    return calls, remove


@pytest.mark.parametrize("recovery", ["open_new", "explicit"])
@pytest.mark.parametrize("fail_at", [1, 2])
def test_backup_purge_failure_keeps_rotation_uncertain_and_recoverable(
    tmp_path: Path, fail_at: int, recovery: str
) -> None:
    store_path, anchor_path, record_id = _rotation_fixture(tmp_path)
    journal_path = anchor_path.with_name("datasources.anchor.txn")
    calls, remove = _failing_remove(fail_at)
    active = CatalogStore.open(
        store_path,
        anchor_path=anchor_path,
        master_key=KEY,
        hooks=CatalogHooks(remove=remove),  # type: ignore[arg-type]
    )
    try:
        with pytest.raises(CatalogOutcomeUncertainError) as error:
            active.rotate_master_key(ROTATED_KEY)
        assert error.value.__cause__ is None
        assert error.value.__context__ is None
        _assert_sanitized(str(error.value) + repr(active), store_path, anchor_path)
        with pytest.raises(CatalogWriteError):
            active.create(_draft(alias="blocked"), TEST_SECRET, resolver=_resolver)
    finally:
        active.close()

    assert calls == BACKUPS_BEFORE_ROTATION[:fail_at]
    assert _revisions(store_path, anchor_path) == (3, 3)
    assert journal_path.exists()
    assert _backups(store_path) == BACKUPS_BEFORE_ROTATION[fail_at - 1 :]
    assert _readable_with(KEY, store_path.parent) == OLD_KEY_READABLE_BACKUPS

    before = _files(store_path.parent, anchor_path.parent)
    with pytest.raises(CatalogRotationPendingError):
        CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY)
    assert _files(store_path.parent, anchor_path.parent) == before
    assert CatalogStore.inspect_master_key_rotation(
        store_path, anchor_path=anchor_path, old_master_key=KEY, new_master_key=ROTATED_KEY
    ) == MasterKeyRotationStatus("new", 3, True)
    assert _files(store_path.parent, anchor_path.parent) == before

    if recovery == "open_new":
        with CatalogStore.open(
            store_path, anchor_path=anchor_path, master_key=ROTATED_KEY
        ) as reopened:
            assert reopened.read_upstream_secret(record_id) == TEST_SECRET
    else:
        assert CatalogStore.recover_master_key_rotation(
            store_path, anchor_path=anchor_path, old_master_key=KEY, new_master_key=ROTATED_KEY
        ) == MasterKeyRotationStatus("new", 3, False)
    assert not journal_path.exists()
    assert _backups(store_path) == []
    assert _readable_with(KEY, store_path.parent, anchor_path.parent) == []
    settled = _files(store_path.parent, anchor_path.parent)
    assert CatalogStore.recover_master_key_rotation(
        store_path, anchor_path=anchor_path, old_master_key=KEY, new_master_key=ROTATED_KEY
    ) == MasterKeyRotationStatus("new", 3, False)
    assert _files(store_path.parent, anchor_path.parent) == settled
    with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=ROTATED_KEY) as done:
        assert done.read_upstream_secret(record_id) == TEST_SECRET


@pytest.mark.parametrize("recovery", ["open_new", "explicit"])
def test_purge_interrupted_during_recovery_resumes_without_consuming_journal(
    tmp_path: Path, recovery: str
) -> None:
    store_path, anchor_path, record_id = _interrupted_rotation(
        tmp_path, CrashPoint.AFTER_ANCHOR_REPLACE
    )
    journal_path = anchor_path.with_name("datasources.anchor.txn")
    calls, remove = _failing_remove(2)
    hooks = CatalogHooks(remove=remove)  # type: ignore[arg-type]
    with pytest.raises(CatalogWriteError) as error:
        if recovery == "open_new":
            CatalogStore.open(
                store_path, anchor_path=anchor_path, master_key=ROTATED_KEY, hooks=hooks
            )
        else:
            CatalogStore.recover_master_key_rotation(
                store_path,
                anchor_path=anchor_path,
                old_master_key=KEY,
                new_master_key=ROTATED_KEY,
                hooks=hooks,
            )
    _assert_sanitized(str(error.value), store_path, anchor_path)
    assert calls == BACKUPS_BEFORE_ROTATION
    assert journal_path.exists()
    assert _revisions(store_path, anchor_path) == (3, 3)
    assert _backups(store_path) == BACKUPS_BEFORE_ROTATION[1:]

    assert CatalogStore.recover_master_key_rotation(
        store_path, anchor_path=anchor_path, old_master_key=KEY, new_master_key=ROTATED_KEY
    ) == MasterKeyRotationStatus("new", 3, False)
    assert not journal_path.exists()
    assert _backups(store_path) == []
    assert _readable_with(KEY, store_path.parent, anchor_path.parent) == []
    with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=ROTATED_KEY) as done:
        assert done.read_upstream_secret(record_id) == TEST_SECRET


def test_backup_purge_is_verified_after_removal(tmp_path: Path) -> None:
    """Remoção que retorna sem erro mas não apaga não pode virar sucesso."""
    store_path, anchor_path, record_id = _rotation_fixture(tmp_path)
    journal_path = anchor_path.with_name("datasources.anchor.txn")
    silent: list[str] = []

    def remove_without_effect(path: str) -> None:
        silent.append(os.path.basename(path))

    active = CatalogStore.open(
        store_path,
        anchor_path=anchor_path,
        master_key=KEY,
        hooks=CatalogHooks(remove=remove_without_effect),
    )
    try:
        with pytest.raises(CatalogOutcomeUncertainError):
            active.rotate_master_key(ROTATED_KEY)
    finally:
        active.close()
    assert silent == BACKUPS_BEFORE_ROTATION
    assert journal_path.exists()
    assert _backups(store_path) == BACKUPS_BEFORE_ROTATION
    assert _revisions(store_path, anchor_path) == (3, 3)

    assert CatalogStore.recover_master_key_rotation(
        store_path, anchor_path=anchor_path, old_master_key=KEY, new_master_key=ROTATED_KEY
    ) == MasterKeyRotationStatus("new", 3, False)
    assert _backups(store_path) == []
    assert not journal_path.exists()
    with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=ROTATED_KEY) as done:
        assert done.read_upstream_secret(record_id) == TEST_SECRET


def test_backup_purge_never_touches_unknown_or_non_regular_entries(tmp_path: Path) -> None:
    store_path, anchor_path, _record_id = _rotation_fixture(tmp_path)
    parent = store_path.parent
    unknown = {
        "operator-note.txt": b"preserve",
        "datasources.store.bak.01": b"not a protocol name",
        "datasources.store.bak.2.orig": b"operator copy",
        "datasources.store.bak": b"no revision",
    }
    for name, data in unknown.items():
        (parent / name).write_bytes(data)
    directory = parent / "datasources.store.bak.98"
    directory.mkdir()
    (directory / "inside").write_bytes(b"inside")
    anchor_note = anchor_path.parent / "operator-note.txt"
    anchor_note.write_bytes(b"preserve")

    with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY) as active:
        active.rotate_master_key(ROTATED_KEY)

    assert _backups(store_path) == []
    for name, data in unknown.items():
        assert (parent / name).read_bytes() == data
    assert directory.is_dir()
    assert (directory / "inside").read_bytes() == b"inside"
    assert anchor_note.read_bytes() == b"preserve"
    assert _readable_with(KEY, parent, anchor_path.parent) == []


def test_backup_purge_never_follows_or_removes_symlinks(tmp_path: Path) -> None:
    store_path, anchor_path, _record_id = _rotation_fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "target"
    target.write_bytes(b"external")
    link = store_path.parent / "datasources.store.bak.99"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("criacao de symlink indisponivel nesta instalacao")

    with CatalogStore.open(store_path, anchor_path=anchor_path, master_key=KEY) as active:
        active.rotate_master_key(ROTATED_KEY)

    assert link.is_symlink()
    assert target.read_bytes() == b"external"
    assert _backups(store_path) == ["datasources.store.bak.99"]  # o link, não um backup
    assert not (store_path.parent / "datasources.store.bak.1").exists()
    assert not (store_path.parent / "datasources.store.bak.2").exists()


def test_same_key_writes_keep_backup_retention(tmp_path: Path) -> None:
    catalog, store_path, _anchor_path = _new_catalog(tmp_path)
    try:
        record = catalog.create(_draft(), TEST_SECRET, resolver=_resolver)
        for index in range(4):
            catalog.update(
                record.id,
                _draft(display_name=f"Name {index}"),
                expected_revision=catalog.revision,
                resolver=_resolver,
            )
        assert catalog.revision == 6
    finally:
        catalog.close()
    assert _backups(store_path) == [
        "datasources.store.bak.3",
        "datasources.store.bak.4",
        "datasources.store.bak.5",
    ]


@pytest.mark.parametrize("mismatch", ["key", "datasource", "revision", "field", "tag"])
def test_open_secret_fails_closed_on_key_aad_or_tag_mismatch(mismatch: str) -> None:
    datasource_id = "dso_" + "a" * 32
    sealed = seal_secret(
        TEST_SECRET,
        master_key=bytes.fromhex(KEY),
        datasource_id=datasource_id,
        schema_version=CATALOG_SCHEMA_VERSION,
        revision=1,
    )
    arguments: dict[str, object] = {
        "master_key": bytes.fromhex(KEY),
        "datasource_id": datasource_id,
        "schema_version": CATALOG_SCHEMA_VERSION,
        "revision": 1,
    }
    envelope = sealed
    if mismatch == "key":
        arguments["master_key"] = bytes.fromhex(ROTATED_KEY)
    elif mismatch == "datasource":
        arguments["datasource_id"] = "dso_" + "b" * 32
    elif mismatch == "revision":
        arguments["revision"] = 2
    elif mismatch == "field":
        arguments["field"] = "other_secret"
    else:
        envelope = EncryptedSecret(
            "AES-256-GCM",
            1,
            sealed.nonce,
            sealed.ciphertext[:-1] + bytes([sealed.ciphertext[-1] ^ 1]),
        )
    with pytest.raises(CryptoValidationError) as error:
        open_secret(envelope, **arguments)  # type: ignore[arg-type]
    assert str(error.value) == "segredo indisponivel"
    assert error.value.__cause__ is None
    assert TEST_SECRET not in str(error.value) + repr(error.value)
