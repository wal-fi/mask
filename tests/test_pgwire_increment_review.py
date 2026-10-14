"""Contraprovas independentes do incremento puro PGWire (D-109)."""

from __future__ import annotations

import hmac
import secrets
import socket
import struct
import threading
from typing import Any, NoReturn

import pytest

from maskgw.pgwire.credential import prepare_principal
from maskgw.pgwire.errors import PgwireStartupError
from maskgw.pgwire.framing import MAX_SASL_MESSAGE, parse_sasl_initial
from maskgw.pgwire.scram import SCRAM_SHA_256, ScramServerExchange
from tests.pgwire_support import LoopbackHarness


def test_unknown_principal_has_identical_public_challenge_material() -> None:
    principal = prepare_principal("review_user", secrets.token_urlsafe(32))
    real = principal.verifier_for("review_user")
    dummy = principal.verifier_for("unknown_user")
    assert real.salt == dummy.salt
    assert real.iterations == dummy.iterations
    assert dummy.real is False
    assert dummy.stored_key != real.stored_key


def test_principal_selection_does_equal_hmac_work(monkeypatch: pytest.MonkeyPatch) -> None:
    principal = prepare_principal("review_user", secrets.token_urlsafe(32))
    original = hmac.new
    calls: list[int] = []

    def counted(*args: Any, **kwargs: Any) -> hmac.HMAC:
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr("maskgw.pgwire.credential.hmac.new", counted)
    principal.verifier_for("review_user")
    known_work = len(calls)
    calls.clear()
    principal.verifier_for("unknown_user")
    assert known_work == len(calls)


def test_sasl_parser_bounds_its_own_public_entrypoint() -> None:
    data = b"a" * (MAX_SASL_MESSAGE + 1)
    body = SCRAM_SHA_256.encode("ascii") + b"\x00" + struct.pack("!i", len(data)) + data
    with pytest.raises(PgwireStartupError):
        parse_sasl_initial(body)


@pytest.mark.parametrize(
    "name",
    [b"a" * (MAX_SASL_MESSAGE + 1), b"a\x00b", b"a\nb"],
    ids=["oversize", "nul", "newline"],
)
def test_scram_first_refuses_oversize_and_control_characters(name: bytes) -> None:
    principal = prepare_principal("review_user", secrets.token_urlsafe(32))
    exchange = ScramServerExchange(principal.verifier_for("review_user"), channel_binding=None)
    with pytest.raises(PgwireStartupError):
        exchange.client_first(SCRAM_SHA_256, b"n,,n=" + name + b",r=abcdefgh")


def test_nonce_generation_failure_is_sanitized_and_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = prepare_principal("review_user", secrets.token_urlsafe(32))
    exchange = ScramServerExchange(principal.verifier_for("review_user"), channel_binding=None)

    def fail_nonce(_size: int) -> NoReturn:
        raise OSError("review_nonce_canary")

    monkeypatch.setattr("maskgw.pgwire.scram.secrets.token_bytes", fail_nonce)
    with pytest.raises(PgwireStartupError) as failure:
        exchange.client_first(SCRAM_SHA_256, b"n,,n=,r=abcdefgh")
    assert failure.value.__cause__ is None
    assert failure.value.__context__ is None
    assert "review_nonce_canary" not in str(failure.value)
    assert "failed" in repr(exchange)


def test_harness_does_not_hide_workers_as_daemon() -> None:
    principal = prepare_principal("review_user", secrets.token_urlsafe(32))
    harness = LoopbackHarness(principal)
    try:
        assert harness.thread.daemon is False
    finally:
        harness.listener.close()


def test_harness_disconnect_physically_closes_worker_and_sockets() -> None:
    principal = prepare_principal("review_user", secrets.token_urlsafe(32))
    with (
        LoopbackHarness(principal) as harness,
        socket.create_connection(("127.0.0.1", harness.port), timeout=2),
    ):
        pass
    assert not harness.thread.is_alive()
    assert harness.listener.fileno() == -1
    assert all(item.fileno() == -1 for item in harness.sockets)


def test_harness_start_failure_closes_its_owned_listener(monkeypatch: pytest.MonkeyPatch) -> None:
    principal = prepare_principal("review_user", secrets.token_urlsafe(32))
    harness = LoopbackHarness(principal)

    def fail_start() -> NoReturn:
        raise RuntimeError("review_start_failure")

    monkeypatch.setattr(harness.thread, "start", fail_start)
    try:
        with pytest.raises(RuntimeError):
            harness.__enter__()
        assert harness.listener.fileno() == -1
        assert not harness.thread.is_alive()
    finally:
        harness.listener.close()


def test_harness_start_that_runs_then_raises_reaps_the_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = threading.Event()
    release = threading.Event()

    def paused(_owner: LoopbackHarness) -> None:
        entered.set()
        release.wait(2)

    monkeypatch.setattr(LoopbackHarness, "_serve", paused)
    principal = prepare_principal("review_user", secrets.token_urlsafe(32))
    harness = LoopbackHarness(principal)
    original_start = harness.thread.start
    timer = threading.Timer(0.2, release.set)

    def start_then_raise() -> NoReturn:
        original_start()
        assert entered.wait(1)
        raise RuntimeError("review_start_after_native")

    monkeypatch.setattr(harness.thread, "start", start_then_raise)
    timer.start()
    try:
        with pytest.raises(RuntimeError):
            harness.__enter__()
        assert not harness.thread.is_alive()
        assert harness.listener.fileno() == -1
    finally:
        release.set()
        harness.thread.join(2)
        harness.listener.close()
        timer.cancel()
        timer.join(2)
