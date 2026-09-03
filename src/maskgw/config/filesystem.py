"""Primitivos de filesystem seguro para a configuracao administrativa.

Este modulo nao conhece HTTP, runtime candidato ou a secao critica do admin.
Ele implementa somente a fronteira de filesystem da Fase 7, etapa 5:

* validacao do arquivo, diretorio pai e sidecar de lock;
* lock exclusivo nao bloqueante mantido pelo lifecycle do objeto;
* snapshots dos bytes exatos acompanhados de SHA-256;
* escrita atomica no mesmo diretorio, com resultados pre e pos-``replace``;
* limpeza estrita de temporarios orfaos pertencentes a este protocolo.

No POSIX, os bits de modo sao validados e o diretorio e sincronizado depois
do ``replace``. No Windows, ``mode`` nao representa as ACLs reais; criacao com
``0o600`` e apenas best effort e o fsync de diretorio e deliberadamente
omitido, conforme a limitacao documentada na especificacao.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import re
import secrets
import stat
import threading
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from maskgw.errors import CapabilityError, MaskGatewayError

_LOCK_SUFFIX: Final = ".lock"
#: Prefixo do backup da adocao (secao 5.4). O nome completo e
#: `<config>.bak.<epoch>`, no mesmo diretorio, criado com `O_EXCL` e `0600`.
_BACKUP_INFIX: Final = ".bak."
_TEMP_TOKEN_BYTES: Final = 8
_PRIVATE_MODE: Final = 0o600
_UNSAFE_WRITE_BITS: Final = stat.S_IWGRP | stat.S_IWOTH
_BINARY_FLAG: Final = getattr(os, "O_BINARY", 0)
_NOFOLLOW_FLAG: Final = getattr(os, "O_NOFOLLOW", 0)


class DigestCheckPoint(StrEnum):
    """Pontos deterministas das duas verificacoes contra edicao externa."""

    INITIAL = "initial"
    PRE_REPLACE = "pre_replace"


def _ignore_digest_check(_point: DigestCheckPoint) -> None:
    return None


def _random_temp_token() -> str:
    return secrets.token_hex(_TEMP_TOKEN_BYTES)


def _ignore_backup_create(_path: str) -> None:
    return None


@dataclass(frozen=True, slots=True, repr=False)
class FilesystemHooks:
    """Pontos controlados para testar corridas e falhas de durabilidade.

    Os defaults sao as operacoes reais. A API nao transporta dados sensiveis
    aos callbacks: os hooks recebem o ponto fixo da operacao ou o caminho alvo,
    nunca os bytes.
    """

    before_digest_check: Callable[[DigestCheckPoint], None] = _ignore_digest_check
    file_fsync: Callable[[int], None] = os.fsync
    replace: Callable[[str, str], None] = os.replace
    directory_fsync: Callable[[int], None] = os.fsync
    temp_token: Callable[[], str] = _random_temp_token
    #: Chamado no backup da adocao DEPOIS da criacao exclusiva e ANTES de escrever
    #: (secao 5.4, D-059). Ponto de injecao de falha: um teste levanta aqui e
    #: confirma que o incompleto e removido, o preexistente fica intacto e nenhum
    #: fd vaza. Recebe so o caminho alvo, nunca os bytes.
    after_backup_create: Callable[[str], None] = _ignore_backup_create


class UnsafeConfigFilesystemError(CapabilityError):
    """Arquivo, diretorio ou sidecar nao satisfaz a politica de seguranca."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("filesystem da configuracao nao e seguro")


class ConfigLockUnavailableError(CapabilityError):
    """Outro processo detem o lock ou a plataforma nao consegue obte-lo."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("lock exclusivo da configuracao indisponivel")


class ConfigOutOfSyncError(MaskGatewayError):
    """Os bytes em disco divergiram do digest da revisao ativa."""

    __slots__ = ()
    category: Final = "CONFIG_OUT_OF_SYNC"
    applied: Final = False

    def __init__(self) -> None:
        super().__init__("configuracao em disco divergiu da revisao ativa")


class ConfigWriteError(MaskGatewayError):
    """A escrita falhou antes de instalar o arquivo novo."""

    __slots__ = ()
    category: Final = "CONFIG_WRITE_ERROR"
    applied: Final = False

    def __init__(self) -> None:
        super().__init__("falha ao persistir a configuracao")


class ConfigDurabilityError(MaskGatewayError):
    """O arquivo novo foi instalado, mas a durabilidade nao foi confirmada."""

    __slots__ = ("digest",)
    category: Final = "CONFIG_DURABILITY_ERROR"
    applied: Final = True

    def __init__(self, digest: str) -> None:
        super().__init__("configuracao instalada sem confirmacao de durabilidade")
        self.digest = digest


@dataclass(frozen=True, slots=True, repr=False)
class ConfigSnapshot:
    """Bytes exatos e digest correspondente, sem exposicao acidental no repr."""

    data: bytes
    digest: str

    def __repr__(self) -> str:
        return "ConfigSnapshot(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class AtomicWriteResult:
    """Resultado de uma instalacao atomica concluida."""

    digest: str
    directory_fsync_performed: bool

    def __repr__(self) -> str:
        return f"AtomicWriteResult(directory_fsync_performed={self.directory_fsync_performed!r})"


@dataclass(frozen=True, slots=True, repr=False)
class BackupResult:
    """Resultado de um backup byte a byte concluido (secao 5.4)."""

    #: Nome do arquivo criado, sem o diretorio. Nao carrega bytes nem caminho
    #: absoluto: e so o suficiente para o teste conferir o padrao `.bak.<epoch>`.
    name: str

    def __repr__(self) -> str:
        return "BackupResult(<redacted>)"


def digest_bytes(data: bytes) -> str:
    """Calcula SHA-256 sobre os bytes exatos, sem decodificacao ou normalizacao."""
    return hashlib.sha256(data).hexdigest()


def _absolute_without_resolving(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _same_file(before: os.stat_result, after: os.stat_result) -> bool:
    return before.st_dev == after.st_dev and before.st_ino == after.st_ino


def _validate_parent(path: Path) -> None:
    info: os.stat_result | None = None
    failed = False
    try:
        info = path.lstat()
    except OSError:
        failed = True

    if failed or info is None:
        raise UnsafeConfigFilesystemError()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise UnsafeConfigFilesystemError()
    if os.name == "posix" and info.st_mode & _UNSAFE_WRITE_BITS:
        raise UnsafeConfigFilesystemError()


def _validate_regular_file(
    path: Path,
    *,
    require_private_mode: bool,
) -> os.stat_result:
    info: os.stat_result | None = None
    failed = False
    try:
        info = path.lstat()
    except OSError:
        failed = True

    if failed or info is None:
        raise UnsafeConfigFilesystemError()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise UnsafeConfigFilesystemError()
    if os.name == "posix":
        mode = stat.S_IMODE(info.st_mode)
        if require_private_mode:
            if mode != _PRIVATE_MODE:
                raise UnsafeConfigFilesystemError()
        elif mode & _UNSAFE_WRITE_BITS:
            raise UnsafeConfigFilesystemError()
    return info


def _open_validated_regular(path: Path, expected: os.stat_result) -> int:
    descriptor = -1
    failed = False
    try:
        descriptor = os.open(path, os.O_RDONLY | _BINARY_FLAG | _NOFOLLOW_FLAG)
        opened = os.fstat(descriptor)
    except OSError:
        failed = True
        opened = None

    if failed or opened is None:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        raise UnsafeConfigFilesystemError()
    if not stat.S_ISREG(opened.st_mode) or not _same_file(expected, opened):
        with suppress(OSError):
            os.close(descriptor)
        raise UnsafeConfigFilesystemError()
    if os.name == "posix" and opened.st_mode & _UNSAFE_WRITE_BITS:
        with suppress(OSError):
            os.close(descriptor)
        raise UnsafeConfigFilesystemError()
    return descriptor


def _read_all(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    failed = False
    try:
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
    except OSError:
        failed = True
    finally:
        try:
            os.close(descriptor)
        except OSError:
            failed = True

    if failed:
        raise UnsafeConfigFilesystemError()
    return b"".join(chunks)


def _ensure_lock_byte(descriptor: int) -> bool:
    failed = False
    try:
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"\0")
            os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
    except OSError:
        failed = True
    return not failed


def _create_lock_file(path: Path) -> int | None:
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | _BINARY_FLAG | _NOFOLLOW_FLAG,
            _PRIVATE_MODE,
        )
    except FileExistsError:
        return None
    except OSError:
        descriptor = -1

    if descriptor < 0:
        raise UnsafeConfigFilesystemError()

    valid = True
    try:
        opened = os.fstat(descriptor)
        valid = stat.S_ISREG(opened.st_mode)
        if os.name == "posix":
            valid = valid and stat.S_IMODE(opened.st_mode) == _PRIVATE_MODE
    except OSError:
        valid = False

    if not valid or not _ensure_lock_byte(descriptor):
        with suppress(OSError):
            os.close(descriptor)
        raise UnsafeConfigFilesystemError()
    return descriptor


def _open_existing_lock(path: Path) -> int:
    expected = _validate_regular_file(path, require_private_mode=True)
    descriptor = -1
    failed = False
    try:
        descriptor = os.open(path, os.O_RDWR | _BINARY_FLAG | _NOFOLLOW_FLAG)
        opened = os.fstat(descriptor)
    except OSError:
        failed = True
        opened = None

    if failed or opened is None:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        raise UnsafeConfigFilesystemError()
    valid = stat.S_ISREG(opened.st_mode) and _same_file(expected, opened)
    if os.name == "posix":
        valid = valid and stat.S_IMODE(opened.st_mode) == _PRIVATE_MODE
    if not valid or not _ensure_lock_byte(descriptor):
        with suppress(OSError):
            os.close(descriptor)
        raise UnsafeConfigFilesystemError()
    return descriptor


def _open_lock(path: Path) -> int:
    descriptor = _create_lock_file(path)
    if descriptor is not None:
        return descriptor
    return _open_existing_lock(path)


def _acquire_lock(descriptor: int) -> bool:
    acquired = False
    try:
        if os.name == "posix":
            fcntl = importlib.import_module("fcntl")
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            msvcrt = importlib.import_module("msvcrt")
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        acquired = True
    except (ImportError, OSError):
        acquired = False
    return acquired


def _release_lock(descriptor: int) -> None:
    try:
        if os.name == "posix":
            fcntl = importlib.import_module("fcntl")
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        else:
            msvcrt = importlib.import_module("msvcrt")
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    except (ImportError, OSError):
        pass
    with suppress(OSError):
        os.close(descriptor)


class ConfigFileStore:
    """Filesystem validado com lock exclusivo detido ate ``close()``."""

    __slots__ = (
        "_closed",
        "_config_path",
        "_hooks",
        "_lifecycle_lock",
        "_lock_descriptor",
        "_temp_pattern",
    )

    def __init__(
        self,
        *,
        config_path: Path,
        lock_descriptor: int,
        hooks: FilesystemHooks,
    ) -> None:
        self._config_path = config_path
        self._lock_descriptor = lock_descriptor
        self._hooks = hooks
        self._lifecycle_lock = threading.Lock()
        self._closed = False
        self._temp_pattern = re.compile(
            rf"^\.{re.escape(config_path.name)}\.tmp\.[0-9]+\.[0-9a-f]{{16}}$"
        )

    @classmethod
    def open(
        cls,
        config_path: str | Path,
        *,
        hooks: FilesystemHooks | None = None,
    ) -> ConfigFileStore:
        """Valida o filesystem, adquire o lock e limpa orfaos seguros."""
        path = _absolute_without_resolving(config_path)
        _validate_parent(path.parent)
        _validate_regular_file(path, require_private_mode=False)

        lock_path = path.with_name(f"{path.name}{_LOCK_SUFFIX}")
        descriptor = _open_lock(lock_path)
        if not _acquire_lock(descriptor):
            with suppress(OSError):
                os.close(descriptor)
            raise ConfigLockUnavailableError()

        store = cls(
            config_path=path,
            lock_descriptor=descriptor,
            hooks=hooks if hooks is not None else FilesystemHooks(),
        )
        try:
            store.cleanup_orphaned_temps()
            store.read_snapshot()
        except BaseException:
            store.close()
            raise
        return store

    @property
    def closed(self) -> bool:
        with self._lifecycle_lock:
            return self._closed

    @property
    def directory_fsync_supported(self) -> bool:
        """Indica se esta plataforma executa fsync do diretorio."""
        return os.name == "posix"

    def _ensure_open(self) -> None:
        with self._lifecycle_lock:
            closed = self._closed
        if closed:
            msg = "filesystem da configuracao ja encerrado"
            raise RuntimeError(msg)

    def read_snapshot(self) -> ConfigSnapshot:
        """Le os bytes exatos sem seguir symlink e calcula o SHA-256."""
        self._ensure_open()
        _validate_parent(self._config_path.parent)
        expected = _validate_regular_file(self._config_path, require_private_mode=False)
        descriptor = _open_validated_regular(self._config_path, expected)
        data = _read_all(descriptor)
        return ConfigSnapshot(data=data, digest=digest_bytes(data))

    def _verify_digest(self, expected_digest: str, point: DigestCheckPoint) -> None:
        hook_failed = False
        try:
            self._hooks.before_digest_check(point)
        except OSError:
            hook_failed = True
        if hook_failed:
            raise ConfigWriteError()
        if self.read_snapshot().digest != expected_digest:
            raise ConfigOutOfSyncError()

    def _new_temp_path(self) -> Path:
        token = self._hooks.temp_token()
        if re.fullmatch(r"[0-9a-f]{16}", token) is None:
            raise ConfigWriteError()
        return self._config_path.with_name(f".{self._config_path.name}.tmp.{os.getpid()}.{token}")

    def _is_managed_temp(self, path: Path) -> bool:
        return (
            path.parent == self._config_path.parent
            and self._temp_pattern.fullmatch(path.name) is not None
        )

    def _unlink_regular_temp(self, path: Path) -> bool:
        if not self._is_managed_temp(path):
            return False

        info: os.stat_result | None = None
        missing = False
        failed = False
        try:
            info = path.lstat()
        except FileNotFoundError:
            missing = True
        except OSError:
            failed = True

        if missing:
            return True
        if failed or info is None:
            return False
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            return False

        removed = False
        try:
            os.unlink(path)
            removed = True
        except FileNotFoundError:
            removed = True
        except OSError:
            removed = False
        return removed

    def cleanup_orphaned_temps(self) -> None:
        """Remove somente nomes exatos, regulares e nao symlink do protocolo."""
        self._ensure_open()
        entries: list[os.DirEntry[str]] = []
        failed = False
        try:
            with os.scandir(self._config_path.parent) as iterator:
                entries = list(iterator)
        except OSError:
            failed = True

        if failed:
            raise UnsafeConfigFilesystemError()

        for entry in entries:
            candidate = self._config_path.parent / entry.name
            if self._is_managed_temp(candidate) and not self._unlink_regular_temp(candidate):
                info: os.stat_result | None = None
                try:
                    info = candidate.lstat()
                except FileNotFoundError:
                    continue
                except OSError:
                    pass
                if info is not None and (
                    stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
                ):
                    continue
                raise UnsafeConfigFilesystemError()

    def _create_temp(self, path: Path) -> int:
        descriptor = -1
        try:
            descriptor = os.open(
                path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | _BINARY_FLAG | _NOFOLLOW_FLAG,
                _PRIVATE_MODE,
            )
            opened = os.fstat(descriptor)
        except OSError:
            opened = None

        if descriptor < 0 or opened is None:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
                self._unlink_regular_temp(path)
            raise ConfigWriteError()
        valid = stat.S_ISREG(opened.st_mode)
        if os.name == "posix":
            valid = valid and stat.S_IMODE(opened.st_mode) == _PRIVATE_MODE
        if not valid:
            with suppress(OSError):
                os.close(descriptor)
            self._unlink_regular_temp(path)
            raise ConfigWriteError()
        return descriptor

    def _write_and_sync_temp(self, descriptor: int, data: bytes) -> bool:
        succeeded = False
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                written = stream.write(data)
                stream.flush()
                self._hooks.file_fsync(stream.fileno())
            if written != len(data):
                return False
            succeeded = True
        except OSError:
            succeeded = False
            with suppress(OSError):
                os.close(descriptor)
        return succeeded

    def _replace(self, temp_path: Path) -> bool:
        succeeded = False
        try:
            self._hooks.replace(os.fspath(temp_path), os.fspath(self._config_path))
            succeeded = True
        except OSError:
            succeeded = False
        return succeeded

    def _sync_parent_directory(self) -> bool:
        descriptor = -1
        succeeded = False
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | _NOFOLLOW_FLAG
        try:
            descriptor = os.open(self._config_path.parent, flags)
            opened = os.fstat(descriptor)
            if not stat.S_ISDIR(opened.st_mode):
                return False
            self._hooks.directory_fsync(descriptor)
            succeeded = True
        except OSError:
            succeeded = False
        finally:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
        return succeeded

    def backup_path(self, epoch: int) -> Path:
        """Caminho do backup `<config>.bak.<epoch>` no mesmo diretorio."""
        return self._config_path.with_name(f"{self._config_path.name}{_BACKUP_INFIX}{epoch}")

    def write_backup(self, data: bytes, *, epoch: int) -> BackupResult:
        """Grava `data` byte a byte em `<config>.bak.<epoch>` (secao 5.4).

        `O_CREAT | O_EXCL`, modo `0600`, `O_NOFOLLOW`, arquivo regular conferido
        por `fstat`, `fsync` do arquivo antes de retornar. **Nunca sobrescreve:**
        se o nome ja existe, ou qualquer passo falha, levanta `ConfigWriteError`
        e o arquivo alvo, se ja existia, fica intacto — sobrescrever um backup
        destruiria o unico registro dos comentarios originais.

        Diferente de `write_atomic`, isto NAO e uma instalacao atomica: e a
        criacao de um arquivo NOVO, ao lado do principal, sem `replace`. O
        principal nao e tocado aqui.
        """
        self._ensure_open()
        path = self.backup_path(epoch)

        # A criacao exclusiva vem PRIMEIRO e SOZINHA no seu proprio try: uma
        # `FileExistsError` aqui e colisao de nome, e o arquivo existente e o
        # backup de alguem — nunca o removemos (secao 5.4). Nenhum passo de
        # escrita/fsync/cleanup pertence a este bloco, entao a colisao nunca
        # alcanca o caminho que apaga o incompleto.
        descriptor = -1
        try:
            descriptor = os.open(
                path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | _BINARY_FLAG | _NOFOLLOW_FLAG,
                _PRIVATE_MODE,
            )
        except FileExistsError:
            raise ConfigWriteError() from None
        except OSError:
            raise ConfigWriteError() from None

        # A partir daqui o arquivo e NOSSO e recem-criado. O CLEANUP — fechar o
        # descritor e remover o incompleto — acontece SEMPRE que este bloco
        # falha, seja qual for a excecao. Mas a CONVERSAO e seletiva:
        #
        # - `Exception` (write/flush/fsync/close, short write, hook operacional)
        #   -> `ConfigWriteError`, depois do cleanup;
        # - `BaseException` de controle — `KeyboardInterrupt`, `SystemExit`,
        #   `GeneratorExit` — NAO e mascarada: o cleanup roda e a excecao original
        #   e RELANCADA. Converte-la em `ConfigWriteError` engoliria um Ctrl-C ou
        #   um pedido de encerramento, que precisam subir intactos.
        try:
            opened = os.fstat(descriptor)
            valid = stat.S_ISREG(opened.st_mode)
            if os.name == "posix":
                valid = valid and stat.S_IMODE(opened.st_mode) == _PRIVATE_MODE
            if not valid:
                raise ConfigWriteError()
            # Ponto de injecao de falha, depois da criacao exclusiva. A partir de
            # `_write_backup_stream`, o descritor e consumido — `os.fdopen` com
            # `closefd=True` passa a posse ao stream, cujo `with` fecha em todos
            # os caminhos —, entao ele nao pode ser fechado de novo aqui (o numero
            # poderia ja ter sido reusado por outro arquivo).
            self._hooks.after_backup_create(os.fspath(path))
            fd_to_close = descriptor
            descriptor = -1
            self._write_backup_stream(fd_to_close, data)
        except Exception:
            # Operacional (write/flush/fsync/close, short write, hook): cleanup e
            # entao converte em ConfigWriteError. Excecoes de controle nao caem
            # aqui — sao `BaseException` e nao `Exception`.
            self._cleanup_incomplete_backup(descriptor, path)
            raise ConfigWriteError() from None
        except BaseException:
            # Controle (Ctrl-C, exit): mesmo cleanup, mas a original SOBE intacta.
            self._cleanup_incomplete_backup(descriptor, path)
            raise

        return BackupResult(name=path.name)

    def _write_backup_stream(self, descriptor: int, data: bytes) -> None:
        """Escreve, flush e fsync do backup, ASSUMINDO a posse do descritor.

        Ponto unico de escrita — e o lugar que os testes de falha exercitam
        diretamente (patch em `os.fdopen` ou no stream), sem precisar de hooks de
        producao para `write`/`flush`/`close`. Um short write levanta
        `ConfigWriteError`; o `with` fecha o stream mesmo quando `write`, `flush`
        ou `fsync` levantam, e um erro no proprio fechamento propaga. Se
        `os.fdopen` levantar antes de tomar posse, o descritor e fechado aqui,
        exatamente uma vez.
        """
        try:
            stream = os.fdopen(descriptor, "wb", closefd=True)
        except BaseException:
            with suppress(OSError):
                os.close(descriptor)
            raise
        with stream:
            written = stream.write(data)
            stream.flush()
            self._hooks.file_fsync(stream.fileno())
            if written != len(data):
                raise ConfigWriteError()

    def _cleanup_incomplete_backup(self, descriptor: int, path: Path) -> None:
        """Fecha o descritor (se ainda aberto) e remove o backup incompleto.

        Chamado no caminho de falha, SEMPRE — inclusive quando a falha e de
        controle. `descriptor` so e >= 0 quando a falha ocorreu ANTES de o stream
        assumir a posse do fd (validacao, hook `after_backup_create`); depois
        disso o `with` de `_write_backup_stream` ja fechou. O unlink acontece de
        qualquer forma, porque um incompleto nunca pode ficar para tras. Nunca
        toca o preexistente: a colisao ja falhou antes deste caminho.
        """
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        self._unlink_regular_backup(path)

    def _unlink_regular_backup(self, path: Path) -> None:
        """Remove um backup RECEM-CRIADO por esta operacao, se for regular.

        So e chamado depois de uma criacao com `O_EXCL` bem-sucedida desta mesma
        chamada, quando um passo posterior falhou: entao o arquivo e nosso e
        nunca preexistia. Nao segue symlink e ignora ausencia.
        """
        info: os.stat_result | None = None
        try:
            info = path.lstat()
        except OSError:
            return
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            return
        with suppress(OSError):
            os.unlink(path)

    def write_atomic(self, data: bytes, *, expected_digest: str) -> AtomicWriteResult:
        """Instala ``data`` atomicamente se os dois digest checks coincidirem.

        Antes de ``os.replace``, toda falha preserva o arquivo anterior e tenta
        remover apenas o temporario desta operacao. Depois do ``replace``, uma
        falha de fsync do diretorio levanta ``ConfigDurabilityError`` com
        ``applied=True``: o arquivo novo permanece instalado.
        """
        self._ensure_open()
        self._verify_digest(expected_digest, DigestCheckPoint.INITIAL)

        temp_path = self._new_temp_path()
        descriptor = self._create_temp(temp_path)
        if not self._write_and_sync_temp(descriptor, data):
            self._unlink_regular_temp(temp_path)
            raise ConfigWriteError()

        try:
            self._verify_digest(expected_digest, DigestCheckPoint.PRE_REPLACE)
        except BaseException:
            self._unlink_regular_temp(temp_path)
            raise

        if not self._replace(temp_path):
            self._unlink_regular_temp(temp_path)
            raise ConfigWriteError()

        new_digest = digest_bytes(data)
        if os.name == "posix":
            if not self._sync_parent_directory():
                raise ConfigDurabilityError(new_digest)
            directory_fsync_performed = True
        else:
            directory_fsync_performed = False

        return AtomicWriteResult(
            digest=new_digest,
            directory_fsync_performed=directory_fsync_performed,
        )

    def close(self) -> None:
        """Libera o lock e o descritor exatamente uma vez."""
        with self._lifecycle_lock:
            if self._closed:
                return
            self._closed = True
            descriptor = self._lock_descriptor
            self._lock_descriptor = -1
        _release_lock(descriptor)

    def __enter__(self) -> ConfigFileStore:
        self._ensure_open()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        with self._lifecycle_lock:
            state = "closed" if self._closed else "locked"
        return f"ConfigFileStore(state={state!r})"
