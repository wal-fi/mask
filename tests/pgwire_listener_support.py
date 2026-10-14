"""Suporte de TESTE do listener PGWire (D-110, lote 3). Nada aqui e produto.

- `make_settings`: `PgwireSettings` de teste (loopback, limites rapidos);
- `running`: inicia um listener em porta efemera (`test_port=0`) e SEMPRE o
  para e recolhe, inclusive se falhar antes do `yield`;
- `FaultyThread`/`faulty_factory`: injecao de falha no `start()` de UMA
  thread nomeada (antes de rodar, rodando com o alvo retido, ou depois de
  rodar), para provar o ownership D-107/D-108 no produto;
- `listener_threads`, `wait_until`: observacao limitada, sem sleeps longos.

O cliente roda na thread do teste (socket cru ou psycopg); nao ha `Peer` aqui.
"""

from __future__ import annotations

import contextlib
import secrets
import socket
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

from maskgw.pgwire.credential import PrincipalCredential, prepare_principal
from maskgw.pgwire.listener import (
    PgwireListener,
    PgwireListenerError,
    ThreadFactory,
)
from maskgw.pgwire.settings import PgwireLimits, PgwireSettings
from maskgw.pgwire.tls import ServerTls
from tests.pgwire_driver_support import watchdog

USER = "gwuser"
THREAD_PREFIX = "maskgw-pgwire-"


def new_credential() -> tuple[PrincipalCredential, str]:
    password = "senha-listener-" + secrets.token_urlsafe(12)
    return prepare_principal(USER, password), password


def make_settings(  # noqa: PLR0913 - cada campo e ajustavel pelo teste
    password: str,
    *,
    bind: str = "127.0.0.1",
    bind_is_hostname: bool = False,
    tls: bool = False,
    max_sessions: int = 4,
    idle_ms: int = 5_000,
    **limits: int,
) -> PgwireSettings:
    defaults = {
        "poll_ms": 20,
        "startup_deadline_ms": 3_000,
        "pre_auth_slots": 4,
        "admission_burst": 50,
        "admission_refill_per_s": 50,
    }
    defaults.update(limits)
    return PgwireSettings(
        username=USER,
        password=password,
        bind=bind,
        bind_is_hostname=bind_is_hostname,
        tls_cert="cert-de-teste.crt" if tls else None,
        tls_key="chave-de-teste.key" if tls else None,
        max_sessions=max_sessions,
        idle_timeout_ms=idle_ms,
        limits=PgwireLimits(**defaults),
    )


@contextlib.contextmanager
def running(  # noqa: PLR0913 - colaboradores do listener, ajustaveis pelo teste
    settings: PgwireSettings,
    principal: PrincipalCredential,
    *,
    tls: ServerTls | None = None,
    aliases: frozenset[str] = frozenset({"crm"}),
    alias_accepted: Callable[[str], bool] | None = None,
    allow_incomplete: bool = False,
    **options: Any,
) -> Iterator[PgwireListener]:
    """Listener iniciado e SEMPRE parado; prova o fim de todas as threads."""
    listener = PgwireListener(
        settings,
        principal=principal,
        tls=tls,
        alias_accepted=alias_accepted or (lambda alias: alias in aliases),
        test_port=0,
        **options,
    )
    with watchdog(60.0):
        try:
            listener.start()
            yield listener
        finally:
            if allow_incomplete:
                with contextlib.suppress(PgwireListenerError):
                    listener.stop()
            else:
                listener.stop()


def listener_threads() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name.startswith(THREAD_PREFIX)]


def wait_until(condition: Callable[[], bool], seconds: float = 5.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def connect_raw(listener: PgwireListener, timeout: float = 5.0) -> socket.socket:
    sock = socket.create_connection(("127.0.0.1", listener.port), timeout=timeout)
    sock.settimeout(timeout)
    return sock


def drain(sock: socket.socket) -> bytes:
    data = bytearray()
    with contextlib.suppress(OSError):
        while chunk := sock.recv(65536):
            data += chunk
    return bytes(data)


class FaultyThread(threading.Thread):
    """Thread de teste cujo `start()` falha num dos modos de D-107."""

    def __init__(
        self, *args: Any, mode: str, gate: threading.Event | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.mode = mode
        self.gate = gate

    def run(self) -> None:
        if self.gate is not None:
            self.gate.wait(10)  # segura o alvo ANTES de entrar no wrapper
        super().run()

    def start(self) -> None:
        if self.mode == "before":
            msg = "canario-start-antes"
            raise RuntimeError(msg)
        super().start()
        if self.mode == "after_run":
            time.sleep(0.2)  # o alvo ja entrou
        msg = "canario-start-depois"
        raise RuntimeError(msg)


def faulty_factory(
    target_name: str, mode: str, *, gate: threading.Event | None = None, once: bool = True
) -> ThreadFactory:
    used = {"count": 0}

    def factory(*, target: Callable[[], None], name: str, daemon: bool) -> threading.Thread:
        if name == target_name and (not once or used["count"] == 0):
            used["count"] += 1
            return FaultyThread(target=target, name=name, daemon=daemon, mode=mode, gate=gate)
        return threading.Thread(target=target, name=name, daemon=daemon)

    return factory
