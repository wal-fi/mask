"""Auditoria das operacoes v2 que alcancam o handler (Fase 9, Etapa 4, D-095).

Mesma disciplina da v1 (D-060): UM evento por operacao que chega ao handler —
sucesso, recusa ou erro —, nenhum para leitura, recusa de fronteira, path
desconhecido ou falha de schema. O `request_id` e gerado aqui; a duracao e
monotonica; as revisions vem do `DatasourceWriteProbe` que o coordenador
preenche DENTRO da secao critica, e o log e emitido DEPOIS dela.

O registro e o `DatasourceAdminAudit` fechado de `audit/`. `admin/` continua
sem importar `logging`. Uma falha ao montar ou emitir o evento nao muda status,
corpo nem estado: a operacao ja terminou quando a auditoria acontece.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

from maskgw.admin.http.v2.errors import DatasourceAdminError
from maskgw.audit import AdminOutcome, AuditLog
from maskgw.audit.datasource import (
    DATASOURCE_CATEGORY_OUTCOME,
    DatasourceAdminAudit,
    DatasourceAuditErrorCategory,
    DatasourceOperationName,
    DatasourceTargetKind,
)
from maskgw.runtime.datasource_service import DatasourceWriteProbe

_T = TypeVar("_T")

_TESTS = frozenset({DatasourceOperationName.TEST, DatasourceOperationName.TEST_DRAFT})

#: Valor -> membro. Paridade exata com as categorias da v2 provada por teste;
#: uma lacuna aqui nunca transforma a resposta num erro de auditoria.
_AUDIT_CATEGORIES = {item.value: item for item in DatasourceAuditErrorCategory}


@dataclass(slots=True)
class AuditMark:
    """Identidade de UMA operacao auditada e a marca de evento ja emitido."""

    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started: int = field(default_factory=time.monotonic_ns)
    emitted: bool = False


class DatasourceAuditor:
    """Emite exatamente um `DatasourceAdminAudit` por operacao v2."""

    __slots__ = ("_audit",)

    def __init__(self, audit: AuditLog) -> None:
        self._audit = audit

    def run(
        self,
        operation: DatasourceOperationName,
        target_id: str | None,
        call: Callable[[DatasourceWriteProbe], _T],
        *,
        mark: AuditMark | None = None,
    ) -> _T:
        """Executa `call` com um probe novo e audita o desfecho.

        `DatasourceAdminError` e relevantado sem alteracao depois do log, entao
        status e corpo sao os da operacao. Outra excecao nao chega aqui: a
        traducao em `operations.py` fecha toda falha numa categoria.

        `mark` (D-108) carrega `request_id`/inicio da operacao enfileirada e
        registra que o evento ja foi emitido, para que um job que escape da
        traducao nao gere um segundo evento (`unknown`).
        """
        mark = mark if mark is not None else AuditMark()
        request_id = mark.request_id
        started = mark.started
        probe = DatasourceWriteProbe()
        try:
            result = call(probe)
        except DatasourceAdminError as exc:
            category = _AUDIT_CATEGORIES.get(exc.category.value)
            if category is not None:
                mark.emitted = True
                self._emit(
                    request_id,
                    operation,
                    target_id,
                    started,
                    before=probe.catalog_revision_before,
                    after=None,
                    category=category,
                )
            raise
        mark.emitted = True
        self._emit(
            request_id,
            operation,
            target_id,
            started,
            before=probe.catalog_revision_before,
            after=probe.catalog_revision_after,
            category=None,
        )
        return result

    def unknown(
        self, operation: DatasourceOperationName, target_id: str | None, mark: AuditMark
    ) -> None:
        """`INTERNAL_ERROR` de um job que escapou da traducao — so se nada saiu.

        A marca e ligada ANTES de emitir: uma interrupcao entre as duas pode
        perder o evento, nunca duplica-lo (melhor esforco, D-108).
        """
        if mark.emitted:
            return
        mark.emitted = True
        self._emit(
            mark.request_id,
            operation,
            target_id,
            mark.started,
            before=None,
            after=None,
            category=DatasourceAuditErrorCategory.INTERNAL_ERROR,
        )

    def refused(self, operation: DatasourceOperationName, target_id: str | None) -> None:
        """Operacao recusada na admissao da fila (D-108): nada foi executado."""
        mark = AuditMark()
        self._emit(
            mark.request_id,
            operation,
            target_id,
            mark.started,
            before=None,
            after=None,
            category=DatasourceAuditErrorCategory.DATASOURCE_SERVICE_UNAVAILABLE,
        )

    def _emit(  # noqa: PLR0913 - campos de um registro fechado
        self,
        request_id: str,
        operation: DatasourceOperationName,
        target_id: str | None,
        started: int,
        *,
        before: int | None,
        after: int | None,
        category: DatasourceAuditErrorCategory | None,
    ) -> None:
        if operation in _TESTS:
            before = after = None
        outcome = (
            AdminOutcome.SUCCESS if category is None else DATASOURCE_CATEGORY_OUTCOME[category]
        )
        try:
            entry = DatasourceAdminAudit(
                request_id=request_id,
                operation=operation,
                target_kind=DatasourceTargetKind.DATASOURCE,
                target_id=target_id,
                outcome=outcome,
                revision_before=before,
                revision_after=after,
                duration_ms=max(time.monotonic_ns() - started, 0) // 1_000_000,
                error_category=category,
            )
        except (TypeError, ValueError):
            # Nunca muda a resposta de uma operacao ja concluida. Os testes
            # provam que todo caminho monta um evento valido.
            return
        self._audit.record_datasource_admin(entry)


__all__ = ["AuditMark", "DatasourceAuditor"]
