"""Auditoria estruturada, somente de metadata."""

from __future__ import annotations

from maskgw.audit.log import (
    ADMIN_MESSAGE,
    CATEGORY_OUTCOME,
    FAILURE,
    LOGGER_NAME,
    MESSAGE,
    OPERATION_TARGET_KIND,
    SUCCESS,
    AdminAudit,
    AdminErrorCategoryName,
    AdminOperationName,
    AdminOutcome,
    AdminTargetKind,
    AuditLog,
    QueryAudit,
)

__all__ = [
    "ADMIN_MESSAGE",
    "CATEGORY_OUTCOME",
    "FAILURE",
    "LOGGER_NAME",
    "MESSAGE",
    "OPERATION_TARGET_KIND",
    "SUCCESS",
    "AdminAudit",
    "AdminErrorCategoryName",
    "AdminOperationName",
    "AdminOutcome",
    "AdminTargetKind",
    "AuditLog",
    "QueryAudit",
]
