"""Preparo do TLS de servidor do PGWire (Fase 9, Etapa 7, D-110, lote 1).

`prepare_server_tls(cert_path, key_path)` devolve o `SSLContext` do servidor e
o channel binding `tls-server-end-point` do certificado que esse contexto
EFETIVAMENTE apresenta. Nao abre socket, nao gera certificado, nao grava
arquivo temporario. Toda falha e `ConfigError` com texto fixo, sem caminho,
PEM, cadeia ou mensagem do OpenSSL, e levantada fora de `except` (D-017).

Ordem:

1. **Arquivos.** Para cert e chave: o pai imediato e diretorio real (nao
   symlink, nao reparse point; no POSIX sem escrita de grupo/outros); o
   arquivo e regular, nao symlink, nao reparse point, com tamanho ate o
   limite. No POSIX a chave exige modo privado (nada para grupo/outros) e o
   cert, nenhuma escrita de grupo/outros. **No Windows as ACLs NAO sao
   verificadas** (best-effort documentado: a stdlib nao as expoe); so
   atributos de reparse point. Ancestrais acima do pai imediato nao sao
   conferidos, como na politica de `config/filesystem.py`, que este modulo
   estreita ao recusar reparse points (junctions), que aquela aceita.
2. **Cert lido uma vez**, com `O_NOFOLLOW` onde existe, `fstat` igual ao
   `lstat`, leitura incremental ate `limite + 1` (passar do limite e recusa).
   O primeiro certificado do PEM e o leaf: precisa estar dentro da validade
   (`not_before`/`not_after` em UTC) e ser compativel com o binding (D-109:
   RSA/EC, SHA-256/384/512).
3. **Contexto.** `PROTOCOL_TLS_SERVER`, minimo TLS 1.2, sem compressao, sem
   renegociacao, sem certificado de cliente. `load_cert_chain` com callback de
   senha que RECUSA: chave cifrada nunca abre prompt e e recusada.
4. **Identidade depois do load.** O `lstat` de cert e chave e refeito e tem de
   ser identico (dispositivo, inode, tamanho, mtime).
5. **Handshake em memoria (MemoryBIO)** limitado em voltas, bytes e prazo:
   captura o leaf que o contexto apresenta, exige que seja byte a byte o leaf
   do PEM lido, e calcula o binding DESSE leaf.

**TOCTOU, limites honestos.** O `load_cert_chain` relê os arquivos pelo
caminho; a stdlib nao carrega de memoria. O que se prova: o leaf apresentado e
o do PEM lido, a chave carregada casa com ele (o OpenSSL recusa par
incoerente e o handshake a exercita), e os metadados dos dois arquivos nao
mudaram entre a primeira checagem e o fim do load. O que NAO se prova: que os
bytes da chave inspecionada sao os lidos pelo OpenSSL, nem a ausencia de uma
troca dupla rapida (A -> B -> A) que preserve os metadados, por quem ja pode
escrever no diretorio. Trocar certificado exige reiniciar o processo.

**Runtime.** Medido aqui so com o Python 3.11.3 / OpenSSL 1.1.1t desta
maquina, fora de suporte upstream: nenhum contexto de producao e certificado
por este modulo; o gate de runtime moderno continua aberto.
"""

from __future__ import annotations

import datetime
import hmac
import os
import ssl
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from maskgw.errors import ConfigError
from maskgw.pgwire.channel_binding import tls_server_end_point

_NOFOLLOW: Final = getattr(os, "O_NOFOLLOW", 0)
_BINARY: Final = getattr(os, "O_BINARY", 0)
_UNSAFE_WRITE_BITS: Final = stat.S_IWGRP | stat.S_IWOTH
_PRIVATE_KEY_FORBIDDEN_BITS: Final = 0o077
_READ_CHUNK: Final = 4096

_FILE_REFUSED: Final = "pgwire: arquivo TLS recusado"
_CERT_REFUSED: Final = "pgwire: certificado TLS recusado"
_KEY_REFUSED: Final = "pgwire: chave TLS recusada"
_CONTEXT_REFUSED: Final = "pgwire: contexto TLS recusado"
_CHANGED: Final = "pgwire: arquivo TLS alterado durante o carregamento"


@dataclass(frozen=True, slots=True)
class TlsLimits:
    """Limites do preparo TLS (D-110): defaults delegados, internos."""

    max_cert_bytes: int = 64 * 1024
    max_key_bytes: int = 64 * 1024
    handshake_rounds: int = 32
    handshake_bytes: int = 256 * 1024
    handshake_deadline_ms: int = 2_000

    def __post_init__(self) -> None:
        for value in (
            self.max_cert_bytes,
            self.max_key_bytes,
            self.handshake_rounds,
            self.handshake_bytes,
            self.handshake_deadline_ms,
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                msg = "limite TLS do pgwire invalido"
                raise ValueError(msg)


class ServerTls:
    """Contexto do servidor e o binding do leaf que ele apresenta."""

    __slots__ = ("channel_binding", "context")

    def __init__(self, context: ssl.SSLContext, channel_binding: bytes) -> None:
        self.context = context
        self.channel_binding = channel_binding

    def __repr__(self) -> str:
        return "ServerTls(<configurado>)"


class _PasswordRefusedError(Exception):
    """Chave cifrada: o callback recusa em vez de pedir senha."""


def _refuse_password() -> bytes:
    raise _PasswordRefusedError


def _lstat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except (OSError, ValueError):
        return None


def _is_reparse(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _parent_ok(path: Path) -> bool:
    info = _lstat(path.parent)
    if info is None or stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        return False
    if _is_reparse(info):
        return False
    return not (os.name == "posix" and info.st_mode & _UNSAFE_WRITE_BITS)


def _file_info(path: Path, *, private: bool, max_bytes: int) -> os.stat_result | None:
    """`lstat` validado do arquivo, ou `None` se recusado."""
    if not _parent_ok(path):
        return None
    info = _lstat(path)
    if info is None or stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        return None
    if _is_reparse(info) or info.st_size > max_bytes:
        return None
    if os.name == "posix":
        mode = stat.S_IMODE(info.st_mode)
        forbidden = _PRIVATE_KEY_FORBIDDEN_BITS if private else _UNSAFE_WRITE_BITS
        if mode & forbidden:
            return None
    return info


def _identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _read_bounded(path: Path, expected: os.stat_result, limit: int) -> bytes | None:
    """Le ate `limit + 1` bytes do arquivo ja validado; `None` se recusado."""
    descriptor = -1
    data: bytes | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | _BINARY | _NOFOLLOW)
        opened = os.fstat(descriptor)
        if (
            stat.S_ISREG(opened.st_mode)
            and opened.st_dev == expected.st_dev
            and opened.st_ino == expected.st_ino
        ):
            chunks: list[bytes] = []
            total = 0
            while total <= limit:
                chunk = os.read(descriptor, min(_READ_CHUNK, limit + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            if total <= limit:
                data = b"".join(chunks)
    except (OSError, ValueError):
        data = None
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                data = None
    return data


def _leaf_der(pem: bytes, now: datetime.datetime) -> bytes | None:
    """DER do primeiro certificado do PEM, se valido agora; `None` se nao."""
    try:
        certificates = x509.load_pem_x509_certificates(pem)
    except ValueError:
        return None
    if not certificates:
        return None
    leaf = certificates[0]
    if not leaf.not_valid_before_utc <= now <= leaf.not_valid_after_utc:
        return None
    return leaf.public_bytes(serialization.Encoding.DER)


def _new_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.options |= ssl.OP_NO_COMPRESSION | ssl.OP_NO_RENEGOTIATION
    context.verify_mode = ssl.CERT_NONE
    return context


def _server_context() -> ssl.SSLContext | None:
    """Contexto do servidor; `None` se a criacao falhar (causa descartada)."""
    try:
        return _new_context()
    except Exception:
        return None


def _absolute(path: str | os.PathLike[str]) -> Path | None:
    """Caminho absoluto sem resolver links; `None` se invalido.

    NUL e recusado ANTES de `abspath`: no Windows, `abspath("x\\x00.crt")`
    trunca em silencio no NUL (medido) e apontaria para OUTRO arquivo.
    """
    try:
        text = os.fspath(path)
    except TypeError:
        return None
    if not isinstance(text, str) or not text or "\x00" in text:
        return None
    try:
        return Path(os.path.abspath(text))
    except (OSError, ValueError):
        return None


def _load(context: ssl.SSLContext, cert: Path, key: Path) -> bool:
    try:
        context.load_cert_chain(certfile=cert, keyfile=key, password=_refuse_password)
    except Exception:  # chave cifrada, par incoerente, PEM invalido, I/O
        return False
    return True


def presented_leaf(context: ssl.SSLContext, limits: TlsLimits) -> bytes | None:
    """Leaf que `context` apresenta, por handshake em memoria limitado.

    Limites: `handshake_rounds` voltas, `handshake_bytes` trocados no total e
    `handshake_deadline_ms` de relogio monotonico. Estourar qualquer um, ou o
    handshake falhar, devolve `None`.
    """
    deadline = time.monotonic() + limits.handshake_deadline_ms / 1000
    transferred = 0
    done = {"client": False, "server": False}
    leaf: bytes | None = None
    # Qualquer falha (inclusive ao criar o contexto cliente ou os BIOs) e
    # recusa fechada: a causa e descartada, nunca propagada.
    try:
        client = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        client.check_hostname = False
        client.verify_mode = ssl.CERT_NONE
        client.minimum_version = ssl.TLSVersion.TLSv1_2
        server_in, server_out = ssl.MemoryBIO(), ssl.MemoryBIO()
        client_in, client_out = ssl.MemoryBIO(), ssl.MemoryBIO()
        server = context.wrap_bio(server_in, server_out, server_side=True)
        peer = client.wrap_bio(client_in, client_out, server_side=False)
        for _ in range(limits.handshake_rounds):
            for name, side in (("client", peer), ("server", server)):
                if not done[name]:
                    try:
                        side.do_handshake()
                    except ssl.SSLWantReadError:
                        continue
                    done[name] = True
            to_server, to_client = client_out.read(), server_out.read()
            transferred += len(to_server) + len(to_client)
            if transferred > limits.handshake_bytes or time.monotonic() > deadline:
                break
            server_in.write(to_server)
            client_in.write(to_client)
            if all(done.values()):
                leaf = peer.getpeercert(binary_form=True)
                break
    except Exception:
        leaf = None
    return leaf


def prepare_server_tls(
    cert_path: str | os.PathLike[str],
    key_path: str | os.PathLike[str],
    *,
    limits: TlsLimits | None = None,
    now: datetime.datetime | None = None,
) -> ServerTls:
    """Contexto do servidor e binding do leaf efetivo. Falha FECHADA."""
    bounds = limits if limits is not None else TlsLimits()
    moment = now if now is not None else datetime.datetime.now(datetime.UTC)
    cert = _absolute(cert_path)
    key = _absolute(key_path)
    if cert is None or key is None:
        raise ConfigError(_FILE_REFUSED)

    cert_before = _file_info(cert, private=False, max_bytes=bounds.max_cert_bytes)
    key_before = _file_info(key, private=True, max_bytes=bounds.max_key_bytes)
    if cert_before is None or key_before is None:
        raise ConfigError(_FILE_REFUSED)
    pem = _read_bounded(cert, cert_before, bounds.max_cert_bytes)
    if pem is None:
        raise ConfigError(_FILE_REFUSED)
    expected_leaf = _leaf_der(pem, moment)
    if expected_leaf is None:
        raise ConfigError(_CERT_REFUSED)
    # Compatibilidade com o binding ANTES do load: Ed25519/Ed448/hash fora do
    # perfil saem aqui com o erro fixo do helper.
    tls_server_end_point(expected_leaf)

    context = _server_context()
    if context is None:
        raise ConfigError(_CONTEXT_REFUSED)
    if not _load(context, cert, key):
        raise ConfigError(_KEY_REFUSED)

    cert_after = _file_info(cert, private=False, max_bytes=bounds.max_cert_bytes)
    key_after = _file_info(key, private=True, max_bytes=bounds.max_key_bytes)
    if (
        cert_after is None
        or key_after is None
        or _identity(cert_after) != _identity(cert_before)
        or _identity(key_after) != _identity(key_before)
    ):
        raise ConfigError(_CHANGED)

    leaf = presented_leaf(context, bounds)
    if leaf is None:
        raise ConfigError(_CONTEXT_REFUSED)
    if not hmac.compare_digest(leaf, expected_leaf):
        raise ConfigError(_CHANGED)
    return ServerTls(context, tls_server_end_point(leaf))


__all__ = ["ServerTls", "TlsLimits", "prepare_server_tls", "presented_leaf"]
