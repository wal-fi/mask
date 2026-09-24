"""Fase 9, Etapa 4: auditoria fechada da v2 e vocabulario de erro (D-095, spec §13).

O `DatasourceAdminAudit` e fechado por construcao como o `AdminAudit` da v1, e
a v1 nao muda: enums, schemas e o gerador da UI v1 continuam os mesmos.
"""

from __future__ import annotations

import ast
import logging
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from maskgw.admin.errors import AdminErrorCategory
from maskgw.admin.http import schemas as v1_schemas
from maskgw.admin.http.v2.errors import (
    V2_DETAILS,
    V2_SHARED_CATEGORIES,
    V2_STATUS,
    DatasourceAdminError,
    DatasourceErrorCategory,
    status_for,
    v2_error_payload,
)
from maskgw.audit import AdminErrorCategoryName, AdminOperationName, AdminOutcome, AuditLog
from maskgw.audit.datasource import (
    DATASOURCE_CATEGORY_OUTCOME,
    DatasourceAdminAudit,
    DatasourceAuditErrorCategory,
    DatasourceOperationName,
    DatasourceTargetKind,
)

DS_ID = "dso_" + "a" * 32


def _event(**overrides: Any) -> DatasourceAdminAudit:
    values: dict[str, Any] = {
        "request_id": uuid.uuid4().hex,
        "operation": DatasourceOperationName.UPDATE,
        "target_kind": DatasourceTargetKind.DATASOURCE,
        "target_id": DS_ID,
        "outcome": AdminOutcome.SUCCESS,
        "revision_before": 4,
        "revision_after": 5,
        "duration_ms": 3,
        "error_category": None,
    }
    values.update(overrides)
    return DatasourceAdminAudit(**values)


def test_v2_vocabulary_is_exactly_mirrored_in_audit() -> None:
    emitted = {item.value for item in DatasourceErrorCategory} | {
        item.value for item in V2_SHARED_CATEGORIES
    }
    assert {item.value for item in DatasourceAuditErrorCategory} == emitted
    # E as proprias da v2 nao existem na v1: a v1 nao muda (D-095).
    v1 = {item.value for item in AdminErrorCategory}
    assert not {item.value for item in DatasourceErrorCategory} & v1
    assert {item.value for item in AdminErrorCategoryName} == v1


def test_outcome_follows_the_status_class_of_every_category() -> None:
    for item in DatasourceAuditErrorCategory:
        category: Any = (
            DatasourceErrorCategory(item.value)
            if item.value in DatasourceErrorCategory.__members__
            else AdminErrorCategory(item.value)
        )
        expected = AdminOutcome.ERROR if status_for(category) >= 500 else AdminOutcome.REJECTED
        assert DATASOURCE_CATEGORY_OUTCOME[item] is expected


def test_every_v2_category_has_fixed_detail_and_status() -> None:
    assert set(V2_DETAILS) == set(DatasourceErrorCategory)
    assert set(V2_STATUS) == set(DatasourceErrorCategory)
    for category in DatasourceErrorCategory:
        payload = v2_error_payload(category)
        assert set(payload) == {"error", "detail"}
    with pytest.raises(ValueError, match="compartilhado"):
        DatasourceAdminError(AdminErrorCategory.CONFIG_DURABILITY_ERROR)


def test_v1_enums_and_schema_module_are_unchanged() -> None:
    # O gerador da UI v1 le estes tres; a v2 nao acrescentou nada neles.
    assert len(AdminOperationName) == 12
    assert len(AdminErrorCategory) == 19
    assert not any("Datasource" in name for name in dir(v1_schemas))


def test_valid_events_build_and_serialize_only_metadata() -> None:
    fields = _event().as_fields()
    assert set(fields) == {
        "request_id",
        "operation",
        "target_kind",
        "target_id",
        "outcome",
        "revision_before",
        "revision_after",
        "duration_ms",
        "error_category",
    }
    assert fields["operation"] == "datasource_update"
    assert fields["target_kind"] == "datasource"
    _event(operation=DatasourceOperationName.ENABLE, revision_after=4)
    _event(operation=DatasourceOperationName.CREATE, target_id=None)
    _event(
        operation=DatasourceOperationName.TEST_DRAFT,
        target_id=None,
        revision_before=None,
        revision_after=None,
    )
    _event(
        outcome=AdminOutcome.ERROR,
        revision_after=None,
        error_category=DatasourceAuditErrorCategory.CATALOG_OUTCOME_UNCERTAIN,
    )


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"operation": "datasource_update"}, TypeError),
        ({"target_kind": "datasource"}, TypeError),
        ({"outcome": "success"}, TypeError),
        ({"error_category": "NOT_FOUND", "outcome": AdminOutcome.REJECTED}, TypeError),
        ({"duration_ms": True}, TypeError),
        ({"revision_before": True}, TypeError),
        ({"duration_ms": -1}, ValueError),
        ({"request_id": "x" * 32}, ValueError),
        ({"request_id": uuid.uuid1().hex}, ValueError),
        ({"target_id": "11122233344"}, ValueError),
        ({"target_id": "crm-producao"}, ValueError),
        ({"operation": DatasourceOperationName.CREATE}, ValueError),
        ({"operation": DatasourceOperationName.TEST_DRAFT}, ValueError),
        ({"operation": DatasourceOperationName.TEST}, ValueError),
        ({"revision_after": 6}, ValueError),
        ({"revision_after": 4}, ValueError),
        ({"revision_after": None}, ValueError),
        ({"error_category": DatasourceAuditErrorCategory.NOT_FOUND}, ValueError),
        (
            {
                "outcome": AdminOutcome.REJECTED,
                "error_category": DatasourceAuditErrorCategory.CATALOG_WRITE_ERROR,
                "revision_after": None,
            },
            ValueError,
        ),
        (
            {
                "outcome": AdminOutcome.ERROR,
                "error_category": DatasourceAuditErrorCategory.REVISION_CONFLICT,
                "revision_after": None,
            },
            ValueError,
        ),
        (
            {
                "outcome": AdminOutcome.REJECTED,
                "error_category": DatasourceAuditErrorCategory.REVISION_CONFLICT,
            },
            ValueError,
        ),
    ],
)
def test_incoherent_events_are_refused_at_construction(
    overrides: dict[str, Any], error: type[Exception]
) -> None:
    with pytest.raises(error):
        _event(**overrides)


def test_record_refuses_foreign_objects_and_contains_logger_failures() -> None:
    class _Boom(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            del record
            raise RuntimeError("handler quebrado")

    logger = logging.getLogger(f"maskgw.audit.test.{uuid.uuid4().hex}")
    logger.propagate = False
    handler = _Boom()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    # Um `emit` que levanta propaga por `Logger.info`; `record_*` o contem.
    try:
        audit = AuditLog(logger)
        with pytest.raises(TypeError):
            audit.record_datasource_admin(replace(_event()).as_fields())  # type: ignore[arg-type]
        audit.record_datasource_admin(_event())
    finally:
        logger.removeHandler(handler)


def test_audit_module_does_not_import_logging() -> None:
    path = Path(__file__).resolve().parents[1] / "src/maskgw/audit/datasource.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "logging" not in names
