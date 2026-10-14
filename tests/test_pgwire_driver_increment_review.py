"""Independent proof that the caller's accept deadline cannot be renewed."""

from __future__ import annotations

import socket
from typing import cast

from maskgw.pgwire.credential import prepare_principal
from maskgw.pgwire.driver import DriverLimits, SessionOutcome, run_startup_session
from maskgw.pgwire.transport import Deadline


def test_expired_accept_deadline_prevents_all_socket_io_and_reservation():
    class UnusedSocket:
        def settimeout(self, _timeout: float) -> None:
            raise AssertionError("expired accept deadline must prevent socket I/O")

    calls: list[str] = []

    def alias(_value: str) -> bool:
        calls.append("alias")
        return True

    def reserve() -> bool:
        calls.append("reserve")
        return True

    result = run_startup_session(
        cast(socket.socket, UnusedSocket()),
        principal=prepare_principal("review-user", "review-pass"),
        tls=None,
        tls_required=False,
        alias_accepted=alias,
        reserve_session=reserve,
        limits=DriverLimits(10_000, 300_000),
        stop=lambda: False,
        deadline=Deadline(0),
    )
    assert result.outcome is SessionOutcome.TIMEOUT
    assert not result.authenticated
    assert calls == []
