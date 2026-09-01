"""Fase 7, etapa 5: filesystem seguro, lock, digest e escrita atomica."""

from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from maskgw.config import (
    ConfigDurabilityError,
    ConfigFileStore,
    ConfigLockUnavailableError,
    ConfigOutOfSyncError,
    ConfigWriteError,
    DigestCheckPoint,
    FilesystemHooks,
    UnsafeConfigFilesystemError,
    digest_bytes,
)

OLD_CONFIG = b"revision: 7\r\nrules: []\r\n"
NEW_CONFIG = b"revision: 8\nrules: []\n"
EXTERNAL_CONFIG = b"revision: 99\nrules: []\n"
SENSITIVE_DSN = "postgresql://user:super-secret@database.invalid/private"
SENSITIVE_VALUE = "11122233344"
SENSITIVE_SQL = "SELECT secret_value FROM private_table"
TEMP_PATTERN = re.compile(r"^\.masking\.yaml\.tmp\.[0-9]+\.[0-9a-f]{16}$")


def make_config(directory: Path, data: bytes = OLD_CONFIG) -> Path:
    path = directory / "masking.yaml"
    path.write_bytes(data)
    return path


def managed_temps(config_path: Path) -> list[Path]:
    return [
        candidate
        for candidate in config_path.parent.iterdir()
        if TEMP_PATTERN.fullmatch(candidate.name) is not None
    ]


def make_symlink(target: Path, link: Path, *, target_is_directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError:
        pytest.skip("criacao de symlink indisponivel nesta instalacao")


class TestValidation:
    def test_snapshot_preserves_exact_bytes_and_hashes_without_normalization(
        self,
        tmp_path: Path,
    ) -> None:
        config = make_config(tmp_path)
        with ConfigFileStore.open(config) as store:
            snapshot = store.read_snapshot()

        assert snapshot.data == OLD_CONFIG
        assert snapshot.digest == digest_bytes(OLD_CONFIG)
        assert snapshot.digest != digest_bytes(OLD_CONFIG.replace(b"\r\n", b"\n"))

    def test_config_symlink_is_rejected(self, tmp_path: Path) -> None:
        target = tmp_path / "real.yaml"
        target.write_bytes(OLD_CONFIG)
        link = tmp_path / "masking.yaml"
        make_symlink(target, link)

        with pytest.raises(UnsafeConfigFilesystemError):
            ConfigFileStore.open(link)

    def test_non_regular_config_is_rejected(self, tmp_path: Path) -> None:
        config = tmp_path / "masking.yaml"
        config.mkdir()

        with pytest.raises(UnsafeConfigFilesystemError):
            ConfigFileStore.open(config)

    def test_symlink_parent_is_rejected(self, tmp_path: Path) -> None:
        real_parent = tmp_path / "real"
        real_parent.mkdir()
        make_config(real_parent)
        linked_parent = tmp_path / "linked"
        make_symlink(real_parent, linked_parent, target_is_directory=True)

        with pytest.raises(UnsafeConfigFilesystemError):
            ConfigFileStore.open(linked_parent / "masking.yaml")

    def test_non_directory_parent_is_rejected(self, tmp_path: Path) -> None:
        parent = tmp_path / "not-a-directory"
        parent.write_bytes(b"not a directory")

        with pytest.raises(UnsafeConfigFilesystemError):
            ConfigFileStore.open(parent / "masking.yaml")

    def test_lock_symlink_is_validated_before_open(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        target = tmp_path / "unrelated.lock"
        target.write_bytes(b"third party")
        make_symlink(target, tmp_path / "masking.yaml.lock")

        with pytest.raises(UnsafeConfigFilesystemError):
            ConfigFileStore.open(config)
        assert target.read_bytes() == b"third party"

    def test_non_regular_lock_is_rejected(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        (tmp_path / "masking.yaml.lock").mkdir()

        with pytest.raises(UnsafeConfigFilesystemError):
            ConfigFileStore.open(config)

    @pytest.mark.skipif(os.name != "posix", reason="bits de modo POSIX")
    def test_group_writable_config_is_rejected_on_posix(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        config.chmod(0o660)

        with pytest.raises(UnsafeConfigFilesystemError):
            ConfigFileStore.open(config)

    @pytest.mark.skipif(os.name != "posix", reason="bits de modo POSIX")
    def test_world_writable_parent_is_rejected_on_posix(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        original_mode = stat.S_IMODE(tmp_path.stat().st_mode)
        tmp_path.chmod(0o777)
        try:
            with pytest.raises(UnsafeConfigFilesystemError):
                ConfigFileStore.open(config)
        finally:
            tmp_path.chmod(original_mode)

    @pytest.mark.skipif(os.name != "posix", reason="bits de modo POSIX")
    def test_reused_lock_must_be_mode_0600_on_posix(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        lock = tmp_path / "masking.yaml.lock"
        lock.write_bytes(b"\0")
        lock.chmod(0o640)

        with pytest.raises(UnsafeConfigFilesystemError):
            ConfigFileStore.open(config)

    @pytest.mark.skipif(os.name != "nt", reason="limitacao especifica do Windows")
    def test_windows_reports_mode_and_directory_fsync_limitations(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        with ConfigFileStore.open(config) as store:
            assert not store.directory_fsync_supported


class TestLockLifecycle:
    def test_sidecar_is_created_once_and_store_close_is_idempotent(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        lock = tmp_path / "masking.yaml.lock"

        store = ConfigFileStore.open(config)
        first_identity = lock.stat().st_ino
        assert lock.is_file()
        if os.name == "posix":
            assert stat.S_IMODE(lock.stat().st_mode) == 0o600
        store.close()
        store.close()

        with ConfigFileStore.open(config):
            assert lock.stat().st_ino == first_identity

    def test_lock_is_held_against_a_real_second_process(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        source_root = Path(__file__).resolve().parents[1] / "src"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(source_root)
        script = """
import sys
from maskgw.config import ConfigFileStore, ConfigLockUnavailableError

try:
    store = ConfigFileStore.open(sys.argv[1])
except ConfigLockUnavailableError:
    raise SystemExit(0 if sys.argv[2] == "locked" else 2)
except BaseException:
    raise SystemExit(3)
else:
    store.close()
    raise SystemExit(2 if sys.argv[2] == "locked" else 0)
"""

        store = ConfigFileStore.open(config)
        try:
            locked = subprocess.run(  # noqa: S603 - interpretador e script constantes
                [sys.executable, "-c", script, str(config), "locked"],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            store.close()

        released = subprocess.run(  # noqa: S603 - interpretador e script constantes
            [sys.executable, "-c", script, str(config), "released"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert locked.returncode == 0
        assert locked.stdout == locked.stderr == ""
        assert released.returncode == 0
        assert released.stdout == released.stderr == ""

    def test_partial_open_failure_releases_the_lock(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        config = make_config(tmp_path)
        original_cleanup = ConfigFileStore.cleanup_orphaned_temps

        def fail_cleanup(_store: ConfigFileStore) -> None:
            raise UnsafeConfigFilesystemError()

        monkeypatch.setattr(ConfigFileStore, "cleanup_orphaned_temps", fail_cleanup)
        with pytest.raises(UnsafeConfigFilesystemError):
            ConfigFileStore.open(config)

        monkeypatch.setattr(ConfigFileStore, "cleanup_orphaned_temps", original_cleanup)
        with ConfigFileStore.open(config) as store:
            assert not store.closed

    def test_store_does_not_create_threads(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        before = {(thread.ident, thread.name, thread.daemon) for thread in threading.enumerate()}
        with ConfigFileStore.open(config):
            assert {
                (thread.ident, thread.name, thread.daemon) for thread in threading.enumerate()
            } == before
        assert {
            (thread.ident, thread.name, thread.daemon) for thread in threading.enumerate()
        } == before


class TestOrphanCleanup:
    def test_only_exact_regular_orphans_are_removed(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        orphan = tmp_path / ".masking.yaml.tmp.123.0123456789abcdef"
        orphan.write_bytes(b"ours")
        wrong_hex = tmp_path / ".masking.yaml.tmp.123.0123456789abcdeg"
        wrong_hex.write_bytes(b"third party")
        wrong_length = tmp_path / ".masking.yaml.tmp.123.0123456789abcde"
        wrong_length.write_bytes(b"third party")
        wrong_prefix = tmp_path / "masking.yaml.tmp.123.0123456789abcdef"
        wrong_prefix.write_bytes(b"third party")
        matching_directory = tmp_path / ".masking.yaml.tmp.456.fedcba9876543210"
        matching_directory.mkdir()

        with ConfigFileStore.open(config):
            pass

        assert not orphan.exists()
        assert wrong_hex.read_bytes() == b"third party"
        assert wrong_length.read_bytes() == b"third party"
        assert wrong_prefix.read_bytes() == b"third party"
        assert matching_directory.is_dir()

    def test_matching_symlink_is_never_followed_or_removed(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        target = tmp_path / "third-party-data"
        target.write_bytes(b"must remain")
        link = tmp_path / ".masking.yaml.tmp.123.0123456789abcdef"
        make_symlink(target, link)

        with ConfigFileStore.open(config):
            pass

        assert link.is_symlink()
        assert target.read_bytes() == b"must remain"


class TestAtomicWrite:
    def test_temp_is_exclusive_private_and_in_the_same_directory(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        observed: list[Path] = []

        def inspect_temp(point: DigestCheckPoint) -> None:
            if point is not DigestCheckPoint.PRE_REPLACE:
                return
            temps = managed_temps(config)
            assert len(temps) == 1
            temp = temps[0]
            observed.append(temp)
            assert temp.parent == config.parent
            assert temp.read_bytes() == NEW_CONFIG
            if os.name == "posix":
                assert stat.S_IMODE(temp.stat().st_mode) == 0o600

        hooks = FilesystemHooks(before_digest_check=inspect_temp)
        with ConfigFileStore.open(config, hooks=hooks) as store:
            old_digest = store.read_snapshot().digest
            result = store.write_atomic(NEW_CONFIG, expected_digest=old_digest)

        assert len(observed) == 1
        assert config.read_bytes() == NEW_CONFIG
        assert result.digest == digest_bytes(NEW_CONFIG)
        assert managed_temps(config) == []

    def test_o_excl_collision_preserves_old_config_and_foreign_file(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        fixed_hex = "0123456789abcdef"
        hooks = FilesystemHooks(temp_token=lambda: fixed_hex)
        with ConfigFileStore.open(config, hooks=hooks) as store:
            collision = tmp_path / f".masking.yaml.tmp.{os.getpid()}.{fixed_hex}"
            collision.write_bytes(b"third party")
            with pytest.raises(ConfigWriteError) as raised:
                store.write_atomic(NEW_CONFIG, expected_digest=digest_bytes(OLD_CONFIG))

        assert not raised.value.applied
        assert config.read_bytes() == OLD_CONFIG
        assert collision.read_bytes() == b"third party"

    def test_replace_failure_is_pre_commit_and_cleans_the_temp(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)

        def fail_replace(_source: str, _destination: str) -> None:
            raise OSError(SENSITIVE_VALUE)

        hooks = FilesystemHooks(replace=fail_replace)
        with (
            ConfigFileStore.open(config, hooks=hooks) as store,
            pytest.raises(ConfigWriteError) as raised,
        ):
            store.write_atomic(NEW_CONFIG, expected_digest=digest_bytes(OLD_CONFIG))

        assert not raised.value.applied
        assert config.read_bytes() == OLD_CONFIG
        assert managed_temps(config) == []

    def test_reader_observes_only_the_old_or_new_complete_file(self, tmp_path: Path) -> None:
        old = b"old:" + b"a" * (256 * 1024)
        new = b"new:" + b"b" * (256 * 1024)
        config = make_config(tmp_path, old)
        stop = threading.Event()
        started = threading.Event()
        observed: set[bytes] = set()
        failures: list[BaseException] = []

        def read_repeatedly() -> None:
            started.set()
            try:
                while not stop.is_set():
                    try:
                        data = config.read_bytes()
                    except PermissionError:
                        # No Windows, uma abertura pode perder a corrida curta
                        # com ReplaceFile. Leituras que abrem sempre veem uma
                        # das duas versoes completas.
                        time.sleep(0.0001)
                        continue
                    observed.add(data)
                    time.sleep(0.0001)
            except BaseException as exc:  # guardado para a thread principal
                failures.append(exc)

        reader = threading.Thread(target=read_repeatedly)
        reader.start()
        assert started.wait(timeout=5)
        try:
            with ConfigFileStore.open(config) as store:
                result = None
                for _attempt in range(100):
                    try:
                        result = store.write_atomic(new, expected_digest=digest_bytes(old))
                    except ConfigWriteError:
                        # Windows pode recusar o replace enquanto o leitor
                        # mantem o destino aberto. Essa falha e pre-commit.
                        assert config.read_bytes() == old
                        assert managed_temps(config) == []
                        continue
                    break
                deadline = time.monotonic() + 5
                while new not in observed and time.monotonic() < deadline:
                    time.sleep(0.001)
        finally:
            stop.set()
            reader.join(timeout=5)

        assert not reader.is_alive()
        assert failures == []
        assert observed <= {old, new}
        assert old in observed
        assert new in observed
        assert result is not None
        assert result.digest == digest_bytes(new)


class TestDigestRaces:
    def test_external_edit_before_the_first_check_is_out_of_sync(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        with ConfigFileStore.open(config) as store:
            reference = store.read_snapshot().digest
            config.write_bytes(EXTERNAL_CONFIG)
            with pytest.raises(ConfigOutOfSyncError) as raised:
                store.write_atomic(NEW_CONFIG, expected_digest=reference)

        assert raised.value.category == "CONFIG_OUT_OF_SYNC"
        assert not raised.value.applied
        assert config.read_bytes() == EXTERNAL_CONFIG
        assert managed_temps(config) == []

    def test_external_edit_after_first_check_is_caught_before_replace(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        points: list[DigestCheckPoint] = []

        def edit_during_operation(point: DigestCheckPoint) -> None:
            points.append(point)
            if point is DigestCheckPoint.PRE_REPLACE:
                config.write_bytes(EXTERNAL_CONFIG)

        hooks = FilesystemHooks(before_digest_check=edit_during_operation)
        with ConfigFileStore.open(config, hooks=hooks) as store:
            reference = store.read_snapshot().digest
            with pytest.raises(ConfigOutOfSyncError):
                store.write_atomic(NEW_CONFIG, expected_digest=reference)

        assert points == [DigestCheckPoint.INITIAL, DigestCheckPoint.PRE_REPLACE]
        assert config.read_bytes() == EXTERNAL_CONFIG
        assert managed_temps(config) == []


class TestDurability:
    def test_temp_fsync_failure_is_pre_commit_and_removes_temp(
        self,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        config = make_config(tmp_path)

        def fail_file_fsync(_descriptor: int) -> None:
            raise OSError(f"{SENSITIVE_DSN} {SENSITIVE_SQL}")

        hooks = FilesystemHooks(file_fsync=fail_file_fsync)
        with (
            ConfigFileStore.open(config, hooks=hooks) as store,
            pytest.raises(ConfigWriteError) as raised,
        ):
            store.write_atomic(NEW_CONFIG, expected_digest=digest_bytes(OLD_CONFIG))

        assert not raised.value.applied
        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None
        assert config.read_bytes() == OLD_CONFIG
        assert managed_temps(config) == []
        rendered = f"{raised.value!s} {raised.value!r}"
        assert SENSITIVE_DSN not in rendered
        assert SENSITIVE_SQL not in rendered
        captured = capsys.readouterr()
        assert captured.out == captured.err == ""

    @pytest.mark.skipif(os.name != "posix", reason="fsync de diretorio somente no POSIX")
    def test_directory_fsync_failure_is_post_commit(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)

        def fail_directory_fsync(_descriptor: int) -> None:
            raise OSError(SENSITIVE_VALUE)

        hooks = FilesystemHooks(directory_fsync=fail_directory_fsync)
        with (
            ConfigFileStore.open(config, hooks=hooks) as store,
            pytest.raises(ConfigDurabilityError) as raised,
        ):
            store.write_atomic(NEW_CONFIG, expected_digest=digest_bytes(OLD_CONFIG))

        assert raised.value.applied
        assert raised.value.digest == digest_bytes(NEW_CONFIG)
        assert config.read_bytes() == NEW_CONFIG
        assert managed_temps(config) == []

    @pytest.mark.skipif(os.name != "nt", reason="omissao especifica do Windows")
    def test_windows_explicitly_omits_directory_fsync(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        calls = 0

        def fail_if_called(_descriptor: int) -> None:
            nonlocal calls
            calls += 1
            raise OSError("nao deve executar")

        hooks = FilesystemHooks(directory_fsync=fail_if_called)
        with ConfigFileStore.open(config, hooks=hooks) as store:
            result = store.write_atomic(NEW_CONFIG, expected_digest=digest_bytes(OLD_CONFIG))

        assert calls == 0
        assert not result.directory_fsync_performed
        assert config.read_bytes() == NEW_CONFIG


class TestLeakage:
    @pytest.mark.parametrize(
        "error",
        [
            UnsafeConfigFilesystemError(),
            ConfigLockUnavailableError(),
            ConfigOutOfSyncError(),
            ConfigWriteError(),
            ConfigDurabilityError(digest_bytes(OLD_CONFIG)),
        ],
    )
    def test_error_text_and_repr_are_fixed_and_sanitized(
        self,
        error: BaseException,
    ) -> None:
        rendered = f"{error!s} {error!r}"

        for sensitive in (
            SENSITIVE_DSN,
            SENSITIVE_VALUE,
            SENSITIVE_SQL,
            OLD_CONFIG.decode(),
            "Traceback",
        ):
            assert sensitive not in rendered

    def test_store_snapshot_and_result_repr_redact_path_content_and_digest(
        self,
        tmp_path: Path,
    ) -> None:
        sensitive_dir = tmp_path / "super-secret-path"
        sensitive_dir.mkdir()
        config = make_config(sensitive_dir, OLD_CONFIG + SENSITIVE_VALUE.encode())

        with ConfigFileStore.open(config) as store:
            snapshot = store.read_snapshot()
            result = store.write_atomic(NEW_CONFIG, expected_digest=snapshot.digest)
            rendered = f"{store!r} {snapshot!r} {result!r}"

        assert "super-secret-path" not in rendered
        assert SENSITIVE_VALUE not in rendered
        assert snapshot.digest not in rendered
        assert OLD_CONFIG.decode() not in rendered
