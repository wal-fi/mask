"""Contraprovas do detector da Etapa 7; nenhum registro sensivel serializado."""

import logging
from dataclasses import replace

from maskgw.audit import AdminAudit, AdminOperationName, AdminOutcome, AdminTargetKind
from tests.browser_edit_server import EditProbe


def event() -> AdminAudit:
    return AdminAudit(
        request_id="0123456789ab4cde8fab0123456789ab",
        operation=AdminOperationName.RULE_CREATE,
        target_kind=AdminTargetKind.RULE,
        target_id=None,
        outcome=AdminOutcome.SUCCESS,
        revision_before=1,
        revision_after=2,
        duration_ms=0,
        error_category=None,
    )


def test_edit_probe_accepts_serialized_enum_contract() -> None:
    probe = EditProbe("credential-marker", "dsn-marker")
    record = logging.LogRecord("maskgw.audit", logging.INFO, "", 0, "admin", (), None)
    record.maskgw = event().as_fields()
    probe.emit(record)
    assert not probe.failed and len(probe.events) == 1


def test_edit_probe_rejects_wrong_revision_and_unknown_field() -> None:
    for invalid in ({"revision_after": 5}, {"extra": "private"}):
        probe = EditProbe("credential-marker", "dsn-marker")
        record = logging.LogRecord("maskgw.audit", logging.INFO, "", 0, "admin", (), None)
        record.maskgw = {**event().as_fields(), **invalid}
        probe.emit(record)
        assert probe.failed and not probe.events


def test_edit_probe_detects_secret_and_unexpected_warning() -> None:
    for text, level in (("credential-marker", logging.INFO), ("warning", logging.WARNING)):
        probe = EditProbe("credential-marker", "dsn-marker")
        probe.emit(logging.LogRecord("test", level, "", 0, text, (), None))
        assert probe.failed


def test_validate_audit_has_no_write_revisions() -> None:
    probe = EditProbe("credential-marker", "dsn-marker")
    value = replace(
        event(),
        operation=AdminOperationName.VALIDATE,
        target_kind=AdminTargetKind.CONFIG,
        target_id=None,
        revision_before=None,
        revision_after=None,
    )
    record = logging.LogRecord("maskgw.audit", logging.INFO, "", 0, "admin", (), None)
    record.maskgw = value.as_fields()
    probe.emit(record)
    assert not probe.failed and len(probe.events) == 1
