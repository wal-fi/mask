"""Controles positivos do detector de logs do harness, sem serializar registros."""

import logging

from tests.browser_server import MemoryProbe


def test_memory_probe_accepts_operational_info_and_detects_leak():
    probe = MemoryProbe("credential-marker", "dsn-marker")
    probe.emit(logging.LogRecord("uvicorn.error", logging.INFO, "", 0, "Shutting down", (), None))
    assert not probe.failed and not probe.leaked
    probe.emit(logging.LogRecord("test", logging.INFO, "", 0, "credential-marker", (), None))
    assert probe.leaked


def test_memory_probe_rejects_warning_and_unapproved_audit():
    probe = MemoryProbe("credential-marker", "dsn-marker")
    probe.emit(logging.LogRecord("test", logging.WARNING, "", 0, "warning", (), None))
    assert probe.failed
    probe = MemoryProbe("credential-marker", "dsn-marker")
    probe.emit(logging.LogRecord("maskgw.audit", logging.INFO, "", 0, "admin", (), None))
    assert probe.failed and probe.admin_events == 1


def test_peer_reset_is_only_expected_in_explicit_adversarial_scenario():
    error = ConnectionResetError("peer reset")
    error.winerror = 10054
    record = logging.LogRecord(
        "asyncio", logging.ERROR, "", 0, "callback failed", (), (ConnectionResetError, error, None)
    )
    strict = MemoryProbe("credential-marker", "dsn-marker")
    strict.emit(record)
    assert strict.failed and strict.peer_resets == 0
    adversarial = MemoryProbe("credential-marker", "dsn-marker", allow_peer_reset=True)
    adversarial.emit(record)
    assert not adversarial.failed and adversarial.peer_resets == 1
    record.msg = "credential-marker"
    adversarial.emit(record)
    assert adversarial.leaked
    wrong_logger = MemoryProbe("credential-marker", "dsn-marker", allow_peer_reset=True)
    record.name = "uvicorn.error"
    wrong_logger.emit(record)
    assert wrong_logger.failed and wrong_logger.peer_resets == 0
