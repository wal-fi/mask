"""Independent counterproofs for listener startup/shutdown ownership."""

from __future__ import annotations

import secrets
import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest

from maskgw.pgwire.credential import prepare_principal
from maskgw.pgwire.listener import ListenerState, PgwireListener
from maskgw.pgwire.settings import PgwireSettings
from tests.pgwire_driver_support import watchdog


@pytest.fixture(autouse=True)
def _bounded_review() -> Iterator[None]:
    with watchdog(20):
        yield


def test_stop_cannot_complete_while_bind_can_still_create_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pause before socket creation: stop must retain in-flight startup."""
    entered = threading.Event()
    release = threading.Event()
    original = socket.getaddrinfo

    def paused_lookup(*args: Any, **kwargs: Any) -> Any:
        entered.set()
        assert release.wait(5), "test startup barrier expired"
        return original(*args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", paused_lookup)
    password = secrets.token_urlsafe(16)
    listener = PgwireListener(
        PgwireSettings(username="review", password=password),
        principal=prepare_principal("review", password),
        tls=None,
        alias_accepted=lambda _alias: True,
        test_port=0,
    )
    errors: list[BaseException] = []

    def start() -> None:
        try:
            listener.start()
        except BaseException as exc:
            errors.append(exc)

    starter = threading.Thread(target=start, name="review-listener-starter", daemon=False)
    stopper: threading.Thread | None = None
    stop_done = threading.Event()

    def stop() -> None:
        try:
            listener.stop()
        except BaseException as exc:
            errors.append(exc)
        finally:
            stop_done.set()

    try:
        starter.start()
        assert entered.wait(5)
        stopper = threading.Thread(target=stop, name="review-listener-stopper", daemon=False)
        stopper.start()
        # Either wait for startup or report incomplete, never claim STOPPED.
        stop_done.wait(0.2)
        assert listener.status().state is not ListenerState.STOPPED
    finally:
        release.set()
        starter.join(5)
        if stopper is not None:
            stopper.join(5)
        listener.stop()
        assert not starter.is_alive()
        assert stopper is None or not stopper.is_alive()


def test_unexpected_accept_failure_cannot_leave_listener_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Containing an exception also requires an honest unavailable state."""
    attempted = threading.Event()

    class ExplodingAcceptSocket(socket.socket):
        def accept(self) -> tuple[socket.socket, Any]:
            attempted.set()
            raise RuntimeError("review-private-canary")

    monkeypatch.setattr(socket, "socket", ExplodingAcceptSocket)
    password = secrets.token_urlsafe(16)
    listener = PgwireListener(
        PgwireSettings(username="review", password=password),
        principal=prepare_principal("review", password),
        tls=None,
        alias_accepted=lambda _alias: True,
        test_port=0,
    )
    try:
        listener.start()
        assert attempted.wait(5)
        deadline = time.monotonic() + 1
        while listener.status().state is ListenerState.RUNNING and time.monotonic() < deadline:
            time.sleep(0.01)
        assert listener.status().state is not ListenerState.RUNNING
    finally:
        listener.stop()
