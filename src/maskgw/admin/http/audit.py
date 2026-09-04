"""Instrumentacao de auditoria administrativa da fronteira HTTP (Etapa 10).

Cada execucao que alcanca o handler de `config:validate` ou de uma das onze
rotas de escrita da Etapa 9 emite EXATAMENTE um `AdminAudit` — sucesso, recusa
controlada ou erro. As oito rotas de leitura, as recusas anteriores ao handler
(auth, host, origin, content-type, corpo grande), os paths desconhecidos e os
metodos nao registrados NAO ganham `AdminAudit`: o enum aprovado nao tem
operacao para eles, e nao se inventa uma (secao 13.2). Uma falha de schema, que
impede o handler de executar, tambem nao gera evento — o corpo nunca chega ao
handler.

## Onde a auditoria se encaixa, e por que aqui

`admin/http/` nao importa `logging` — quem loga e `audit/`, o unico modulo
autorizado. Este modulo recebe um `AuditLog` injetado pelo composition root e o
usa; ele nao configura logging, nao cria handler global e usa o MESMO `AuditLog`
do plano MCP (secao 13, integracao).

O evento nasce no handler, e nao dentro do servico, por dois motivos:

- o handler e quem conhece a `operation`, o `target_kind` e o `target_id` da
  rota — a secao critica so conhece uma mutacao opaca;
- o log e emitido FORA dos locks criticos: um handler de logging lento nao pode
  manter a secao critica administrativa ocupada (secao 13). `apply` preenche um
  `AdminAuditProbe` dentro do lock, e a emissao acontece depois que ele retorna.

## `request_id`, duracao e desfecho

`request_id` e um UUID NOVO por operacao, gerado aqui pelo servidor. Nunca vem
de header, query string ou corpo — nao ha parametro que o aceite de fora.

`duration_ms` vem de `time.monotonic_ns`, imune a ajuste de relogio, e e um
inteiro nao negativo por construcao.

O desfecho deriva do STATUS que a categoria produz: sucesso -> `success`; recusa
4xx -> `rejected`; falha 5xx -> `error`. `CONFIG_DURABILITY_ERROR` e 500, entao
`error`, e mesmo assim `revision_after` e a revision nova publicada (secao 7.6).

## Falha da propria auditoria

`record_admin` e best-effort: uma excecao do logger e contida la e nao sobe.
Este modulo tambem nao deixa a montagem do evento derrubar a operacao — o evento
so e montado a partir de metadata que ja existe (categoria, revisions do probe,
IDs ja validados pelo schema). O caminho HTTP — status e corpo — e definido pelo
`AdminError` que sobe, independentemente de a auditoria ter sido emitida.
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from maskgw.admin.errors import AdminError, AdminErrorCategory
from maskgw.admin.service import AdminAuditProbe, AdminConfigService, AdminOperation, ConfigMutation
from maskgw.audit import (
    CATEGORY_OUTCOME,
    OPERATION_TARGET_KIND,
    AdminAudit,
    AdminErrorCategoryName,
    AdminOperationName,
    AdminOutcome,
    AdminTargetKind,
    AuditLog,
)
from maskgw.config.ids import EXCEPTION_ID_PATTERN, RULE_ID_PATTERN

#: `validate` recebe uma callable ja parcialmente aplicada pelo handler, para
#: nao arrastar o schema HTTP nem o `SecretProvider` para dentro deste modulo. O
#: resultado e opaco aqui: quem o consome e o handler, que o devolve como resposta.
ValidateResult = TypeVar("ValidateResult")
ValidateCallable = Callable[[], ValidateResult]


@dataclass(frozen=True, slots=True)
class AuditContext:
    """Identidade de uma operacao auditavel, conhecida pelo handler da rota.

    So a `operation` e o `target_id` viajam: o `target_kind` NAO e um campo, e
    sim DERIVADO da operacao por `OPERATION_TARGET_KIND` — a mesma tabela fechada
    que `AdminAudit` valida. Manter o `target_kind` aqui seria uma segunda tabela,
    que poderia divergir; a fonte e unica (secao 13.2).

    `target_id` so e informado para update/delete de uma unica regra ou exception,
    e mesmo assim so quando casa o padrao do ID — um path malformado nao vira
    `target_id` (secao 13.3).
    """

    operation: AdminOperationName
    target_id: str | None = None

    @property
    def target_kind(self) -> AdminTargetKind:
        """Derivado da operacao pela tabela fechada. Nunca uma segunda fonte."""
        return OPERATION_TARGET_KIND[self.operation]


def rule_target_id(path_value: str) -> str | None:
    """`target_id` de regra: o path so quando casa `rul_...`; senao `None`.

    Um ID malformado ou fora do padrao NUNCA e registrado, mesmo que a operacao
    seja recusada com `NOT_FOUND` (secao 13.3): registrar texto arbitrario
    recebido no path abriria um canal para valores no log.
    """
    return path_value if re.fullmatch(RULE_ID_PATTERN, path_value) else None


def exception_target_id(path_value: str) -> str | None:
    """`target_id` de exception: o path so quando casa `exc_...`; senao `None`."""
    return path_value if re.fullmatch(EXCEPTION_ID_PATTERN, path_value) else None


def _category_name(category: AdminErrorCategory) -> AdminErrorCategoryName:
    """Traduz a categoria do plano admin para o enum fechado de `audit/`.

    Os dois enums tem os MESMOS valores (a paridade e provada por teste), entao a
    traducao e por valor — sem uma segunda tabela, e sem arrastar
    `AdminErrorCategory` para dentro de `audit/` (o que fecharia o ciclo).
    """
    return AdminErrorCategoryName(category.value)


def _outcome_for(category: AdminErrorCategory) -> AdminOutcome:
    """Desfecho pela categoria, da FONTE UNICA `CATEGORY_OUTCOME` em `audit/`.

    Nao se deriva mais de `STATUS_BY_CATEGORY` aqui: `CATEGORY_OUTCOME` e a mesma
    tabela que `AdminAudit.__post_init__` usa para validar, entao o desfecho que o
    auditor emite JAMAIS pode divergir do que o record exige. A paridade de
    `CATEGORY_OUTCOME` com a faixa de status de `STATUS_BY_CATEGORY` e provada por
    teste (`test_admin_audit.py`).
    """
    return CATEGORY_OUTCOME[_category_name(category)]


def _duration_ms(started_ns: int) -> int:
    """Duracao monotonica em ms, inteiro e nunca negativa."""
    elapsed_ns = max(time.monotonic_ns() - started_ns, 0)
    return elapsed_ns // 1_000_000


class AdminAuditor:
    """Emite um `AdminAudit` por operacao administrativa que alcanca o handler.

    Injetado no roteador pelo composition root. Sem estado por requisicao: cada
    chamada de `write`/`validate` gera seu proprio `request_id`, mede sua propria
    duracao e emite exatamente um evento.
    """

    __slots__ = ("_audit",)

    def __init__(self, audit: AuditLog) -> None:
        self._audit = audit

    def write(
        self,
        service: AdminConfigService,
        mutation: ConfigMutation,
        *,
        expected_revision: int,
        operation: AdminOperation,
        context: AuditContext,
    ) -> int:
        """Executa uma escrita auditada e devolve a revision publicada.

        Um unico evento e emitido, no sucesso ou na recusa. O `AdminError` de
        recusa e RELEVANTADO sem alteracao apos o log, para que o caminho HTTP —
        status e corpo — permaneca exatamente o da Etapa 9 (secao 13, falha da
        auditoria nao muda a resposta).
        """
        request_id = uuid.uuid4().hex
        started_ns = time.monotonic_ns()
        probe = AdminAuditProbe()
        try:
            result = service.apply(
                mutation,
                expected_revision=expected_revision,
                operation=operation,
                audit_probe=probe,
            )
        except AdminError as exc:
            self._emit(
                request_id=request_id,
                context=context,
                outcome=_outcome_for(exc.category),
                probe=probe,
                duration_ms=_duration_ms(started_ns),
                error_category=_category_name(exc.category),
            )
            raise
        self._emit(
            request_id=request_id,
            context=context,
            outcome=AdminOutcome.SUCCESS,
            probe=probe,
            duration_ms=_duration_ms(started_ns),
            error_category=None,
        )
        return result.revision

    def validate(self, run: ValidateCallable[ValidateResult]) -> ValidateResult:
        """Executa `config:validate` auditado e devolve o resultado da validacao.

        `validate` NAO e escrita (secao 13.2): a operacao e `validate`, o
        `target_kind` e `config`, `revision_before` e `revision_after` sao `None`
        — nao se le o runtime so para preencher auditoria —, e o contador
        `admin_operations_total` nao e tocado, porque `validate_candidate` nao
        entra na secao critica. `run` compila e descarta; o desfecho vem de ele
        ter levantado `AdminError` (compilacao invalida) ou nao.
        """
        request_id = uuid.uuid4().hex
        started_ns = time.monotonic_ns()
        try:
            result = run()
        except AdminError as exc:
            self._emit(
                request_id=request_id,
                context=_VALIDATE_CONTEXT,
                outcome=_outcome_for(exc.category),
                probe=_EMPTY_PROBE,
                duration_ms=_duration_ms(started_ns),
                error_category=_category_name(exc.category),
            )
            raise
        self._emit(
            request_id=request_id,
            context=_VALIDATE_CONTEXT,
            outcome=AdminOutcome.SUCCESS,
            probe=_EMPTY_PROBE,
            duration_ms=_duration_ms(started_ns),
            error_category=None,
        )
        return result

    def _emit(  # noqa: PLR0913 - campos de um record fechado, todos keyword-only
        self,
        *,
        request_id: str,
        context: AuditContext,
        outcome: AdminOutcome,
        probe: AdminAuditProbe,
        duration_ms: int,
        error_category: AdminErrorCategoryName | None,
    ) -> None:
        # Membros de enum, nunca `.value`: `AdminAudit` guarda os enums e valida
        # por construcao. `target_kind` vem da tabela fechada (via `context`).
        self._audit.record_admin(
            AdminAudit(
                request_id=request_id,
                operation=context.operation,
                target_kind=context.target_kind,
                target_id=context.target_id,
                outcome=outcome,
                revision_before=probe.revision_before,
                revision_after=probe.revision_after,
                duration_ms=duration_ms,
                error_category=error_category,
            )
        )


#: Contexto fixo de `config:validate`: operacao `validate` (alvo `config`,
#: derivado da tabela), sem ID.
_VALIDATE_CONTEXT: AuditContext = AuditContext(
    operation=AdminOperationName.VALIDATE,
    target_id=None,
)

#: Probe vazio para `config:validate`: `revision_before`/`after` permanecem None,
#: porque a operacao nao le o runtime nem publica nada (secao 13.2). Compartilhado
#: e nunca mutado: `validate` nao chama `apply`, entao ninguem escreve nele.
_EMPTY_PROBE: AdminAuditProbe = AdminAuditProbe()
