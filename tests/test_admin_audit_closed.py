"""Contraprovas do fechamento real de `AdminAudit` (Fase 7, Etapa 10 — correção).

A revisão encontrou que `AdminAudit` declarava `operation`, `target_kind`,
`outcome` e `error_category` como `str`: os enums existiam, mas eram decorativos.
O construtor aceitava `operation="inventada"`, `outcome="talvez"`, duração
negativa, `error_category="SEGREDO"` e um `target_id` com CPF — usando campos
autorizados como canal para conteúdo arbitrário.

Estes testes falhavam contra `2ff2d43` (o commit da Etapa 10 antes desta
correção) e passam depois dela: o schema passa a ser fechado de verdade, com
validação incontornável de construção, e um evento inválido é RECUSADO antes de
chegar ao logger.

A segunda rodada desta correção fechou duas lacunas de coerência que `2ff2d43`
ainda deixava passar — a classe de status do `error_category` versus o `outcome`
(um `REJECTED` com categoria 5xx, ou um `ERROR` com categoria 4xx), e a exigência
de `revision_after == revision_before + 1` nas escritas bem-sucedidas e no
`CONFIG_DURABILITY_ERROR`. As regressões dessas duas lacunas estão em
`TestCoerenciaOutcomeCategoria` e `TestCoerenciaExataDeRevisoes`, e também
falhavam contra `2ff2d43`.
"""

from __future__ import annotations

import logging
import uuid

import pytest

from maskgw.audit import (
    AdminAudit,
    AdminErrorCategoryName,
    AdminOperationName,
    AdminOutcome,
    AdminTargetKind,
    AuditLog,
)

RULE_ID = "rul_" + "a" * 32
EXCEPTION_ID = "exc_" + "b" * 32

# Marcadores sensíveis que não podem ser escondidos em campo autorizado nenhum.
CPF = "11122233344"
TOKEN = "admin-token-secreto-de-teste-com-40-caracteres"  # noqa: S105 - marcador de teste
SQL = "SELECT cpf FROM cliente"
INTERNAL = "invalid input syntax for type integer"


def _valid(**overrides: object) -> AdminAudit:
    """Um evento válido, base para variar UM campo por vez.

    `request_id` é um `uuid4().hex` de verdade (o formato que o servidor gera), e
    não uma string hex qualquer: o schema exige UUID versão 4.
    """
    fields: dict[str, object] = {
        "request_id": uuid.uuid4().hex,
        "operation": AdminOperationName.RULE_CREATE,
        "target_kind": AdminTargetKind.RULE,
        "target_id": None,
        "outcome": AdminOutcome.SUCCESS,
        "revision_before": 3,
        "revision_after": 4,
        "duration_ms": 5,
        "error_category": None,
    }
    fields.update(overrides)
    return AdminAudit(**fields)  # type: ignore[arg-type]


class TestOperacaoInventadaRecusada:
    def test_operation_arbitraria_e_recusada(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            _valid(operation="inventada")

    def test_target_kind_arbitrario_e_recusado(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            _valid(
                operation=AdminOperationName.RULE_UPDATE,
                target_kind="qualquer",
                target_id=RULE_ID,
            )

    def test_outcome_arbitrario_e_recusado(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            _valid(outcome="talvez")


class TestErrorCategoryFechada:
    def test_error_category_arbitraria_e_recusada(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            _valid(outcome=AdminOutcome.ERROR, error_category="SEGREDO")

    def test_error_category_texto_sensivel_e_recusada(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            _valid(outcome=AdminOutcome.REJECTED, error_category=INTERNAL)


class TestDuracaoENumerosValidados:
    def test_duracao_negativa_e_recusada(self) -> None:
        with pytest.raises(ValueError):
            _valid(duration_ms=-99)

    def test_duracao_booleana_e_recusada(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            _valid(duration_ms=True)

    def test_revision_negativa_e_recusada(self) -> None:
        with pytest.raises(ValueError):
            _valid(revision_before=-1, revision_after=None, outcome=AdminOutcome.REJECTED)

    def test_revision_booleana_e_recusada(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            _valid(revision_before=True, revision_after=False)


class TestTargetIdFechado:
    def test_cpf_em_target_id_e_recusado(self) -> None:
        # O canal exato que a revisão apontou: um CPF escondido em target_id.
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.RULE_UPDATE,
                target_kind=AdminTargetKind.RULE,
                target_id=CPF,
            )

    def test_target_id_arbitrario_e_recusado(self) -> None:
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.RULE_DELETE,
                target_kind=AdminTargetKind.RULE,
                target_id="nao-e-um-id",
            )

    def test_prefixo_e_target_kind_devem_concordar(self) -> None:
        # ID de regra sob target_kind de exception: incoerente, recusado.
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.EXCEPTION_UPDATE,
                target_kind=AdminTargetKind.EXCEPTION,
                target_id=RULE_ID,
            )

    def test_create_nao_carrega_target_id(self) -> None:
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.RULE_CREATE,
                target_kind=AdminTargetKind.RULE,
                target_id=RULE_ID,
            )

    def test_reorder_nao_carrega_target_id(self) -> None:
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.RULES_REORDER,
                target_kind=AdminTargetKind.RULE,
                target_id=RULE_ID,
            )

    def test_adopt_nao_carrega_target_id(self) -> None:
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.ADOPT,
                target_kind=AdminTargetKind.CONFIG,
                target_id=RULE_ID,
            )


class TestMappingOperacaoAlvoFechado:
    def test_operation_e_target_kind_incompativeis_recusados(self) -> None:
        # rule_create com target_kind sql: viola o mapping fechado.
        with pytest.raises(ValueError):
            _valid(operation=AdminOperationName.RULE_CREATE, target_kind=AdminTargetKind.SQL)

    def test_sql_put_exige_target_kind_sql(self) -> None:
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.SQL_PUT,
                target_kind=AdminTargetKind.RULE,
                outcome=AdminOutcome.SUCCESS,
                revision_before=3,
                revision_after=4,
            )


class TestCoerenciaOutcomeRevisao:
    def test_success_exige_error_category_none(self) -> None:
        # success com categoria preenchida é incoerente.
        with pytest.raises(ValueError):
            _valid(
                outcome=AdminOutcome.SUCCESS,
                error_category=AdminErrorCategoryName.CONFIG_INVALID,
            )

    def test_rejected_exige_categoria(self) -> None:
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.RULE_CREATE,
                outcome=AdminOutcome.REJECTED,
                revision_before=3,
                revision_after=None,
                error_category=None,
            )

    def test_validate_exige_revisoes_none(self) -> None:
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.VALIDATE,
                target_kind=AdminTargetKind.CONFIG,
                outcome=AdminOutcome.SUCCESS,
                revision_before=3,
                revision_after=4,
            )

    def test_falha_sem_publicacao_exige_revision_after_none(self) -> None:
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.RULE_CREATE,
                outcome=AdminOutcome.ERROR,
                revision_before=3,
                revision_after=4,
                error_category=AdminErrorCategoryName.CONFIG_WRITE_ERROR,
            )

    def test_durability_exige_error_e_revision_after(self) -> None:
        # durabilidade com outcome != error é incoerente.
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.DATABASE_PUT,
                target_kind=AdminTargetKind.DATABASE,
                outcome=AdminOutcome.REJECTED,
                revision_before=3,
                revision_after=4,
                error_category=AdminErrorCategoryName.CONFIG_DURABILITY_ERROR,
            )


class TestRequestIdFechado:
    def test_request_id_nao_uuid_e_recusado(self) -> None:
        with pytest.raises(ValueError):
            _valid(request_id="nao-e-uuid")

    def test_request_id_com_texto_sensivel_e_recusado(self) -> None:
        with pytest.raises(ValueError):
            _valid(request_id=CPF)


class TestEventoInvalidoNaoChegaAoLogger:
    def test_evento_invalido_recusado_antes_do_logger(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Construir o evento inválido já levanta; nada é logado.
        with caplog.at_level(logging.INFO), pytest.raises((ValueError, TypeError)):
            AuditLog().record_admin(
                AdminAudit(
                    request_id="x",
                    operation="inventada",  # type: ignore[arg-type]
                    target_kind="qualquer",  # type: ignore[arg-type]
                    target_id=CPF,
                    outcome="talvez",  # type: ignore[arg-type]
                    revision_before=None,
                    revision_after=None,
                    duration_ms=-99,
                    error_category="SEGREDO",  # type: ignore[arg-type]
                )
            )
        assert caplog.records == []


class TestCoerenciaOutcomeCategoria:
    """Lacuna fechada na 2ª rodada: o `outcome` tem de bater com a FAIXA DE STATUS
    do `error_category`. `2ff2d43` aceitava as duas combinações abaixo."""

    def test_rejected_com_categoria_5xx_e_recusado(self) -> None:
        # INTERNAL_ERROR é HTTP 500: exige `error`, não `rejected`.
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.RULE_CREATE,
                outcome=AdminOutcome.REJECTED,
                revision_before=3,
                revision_after=None,
                error_category=AdminErrorCategoryName.INTERNAL_ERROR,
            )

    def test_rejected_com_config_write_error_e_recusado(self) -> None:
        # CONFIG_WRITE_ERROR é HTTP 500.
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.DATABASE_PUT,
                target_kind=AdminTargetKind.DATABASE,
                outcome=AdminOutcome.REJECTED,
                revision_before=3,
                revision_after=None,
                error_category=AdminErrorCategoryName.CONFIG_WRITE_ERROR,
            )

    def test_error_com_categoria_4xx_e_recusado(self) -> None:
        # REVISION_CONFLICT é HTTP 409: exige `rejected`, não `error`.
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.RULE_CREATE,
                outcome=AdminOutcome.ERROR,
                revision_before=3,
                revision_after=None,
                error_category=AdminErrorCategoryName.REVISION_CONFLICT,
            )

    def test_error_com_config_invalid_e_recusado(self) -> None:
        # CONFIG_INVALID é HTTP 422 (rejeição), não erro de servidor.
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.RULE_CREATE,
                outcome=AdminOutcome.ERROR,
                revision_before=3,
                revision_after=None,
                error_category=AdminErrorCategoryName.CONFIG_INVALID,
            )

    def test_rejeicoes_validas_sao_aceitas(self) -> None:
        # As combinações CORRETAS constroem sem erro (contraprova da contraprova).
        _valid(
            operation=AdminOperationName.RULE_CREATE,
            outcome=AdminOutcome.REJECTED,
            revision_before=3,
            revision_after=None,
            error_category=AdminErrorCategoryName.REVISION_CONFLICT,
        )
        _valid(
            operation=AdminOperationName.RULE_CREATE,
            outcome=AdminOutcome.REJECTED,
            revision_before=3,
            revision_after=None,
            error_category=AdminErrorCategoryName.CONFIG_INVALID,
        )

    def test_erro_de_servidor_valido_e_aceito(self) -> None:
        _valid(
            operation=AdminOperationName.DATABASE_PUT,
            target_kind=AdminTargetKind.DATABASE,
            outcome=AdminOutcome.ERROR,
            revision_before=3,
            revision_after=None,
            error_category=AdminErrorCategoryName.CONFIG_WRITE_ERROR,
        )
        # INTERNAL_ERROR (500) como erro, sem publicação.
        _valid(
            operation=AdminOperationName.VALIDATE,
            target_kind=AdminTargetKind.CONFIG,
            outcome=AdminOutcome.ERROR,
            revision_before=None,
            revision_after=None,
            error_category=AdminErrorCategoryName.INTERNAL_ERROR,
        )


class TestCoerenciaExataDeRevisoes:
    """Lacuna fechada na 2ª rodada: escrita bem-sucedida e durabilidade exigem
    `revision_after == revision_before + 1`. `2ff2d43` só exigia `after > before`."""

    def test_sucesso_de_escrita_exige_incremento_de_um(self) -> None:
        # 3 -> 5 é maior, mas não é +1: recusado.
        with pytest.raises(ValueError):
            _valid(revision_before=3, revision_after=5)

    def test_sucesso_de_escrita_com_incremento_de_um_e_aceito(self) -> None:
        _valid(revision_before=3, revision_after=4)  # +1, ok

    def test_durability_exige_incremento_de_um(self) -> None:
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.DATABASE_PUT,
                target_kind=AdminTargetKind.DATABASE,
                outcome=AdminOutcome.ERROR,
                revision_before=3,
                revision_after=5,
                error_category=AdminErrorCategoryName.CONFIG_DURABILITY_ERROR,
            )

    def test_durability_com_incremento_de_um_e_aceito(self) -> None:
        _valid(
            operation=AdminOperationName.DATABASE_PUT,
            target_kind=AdminTargetKind.DATABASE,
            outcome=AdminOutcome.ERROR,
            revision_before=3,
            revision_after=4,
            error_category=AdminErrorCategoryName.CONFIG_DURABILITY_ERROR,
        )

    def test_durability_exige_revision_before_presente(self) -> None:
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.DATABASE_PUT,
                target_kind=AdminTargetKind.DATABASE,
                outcome=AdminOutcome.ERROR,
                revision_before=None,
                revision_after=4,
                error_category=AdminErrorCategoryName.CONFIG_DURABILITY_ERROR,
            )

    def test_falha_nao_durabilidade_nao_pode_declarar_revision_after(self) -> None:
        # CONFIG_WRITE_ERROR (falha antes do replace) não publicou nada.
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.DATABASE_PUT,
                target_kind=AdminTargetKind.DATABASE,
                outcome=AdminOutcome.ERROR,
                revision_before=3,
                revision_after=4,
                error_category=AdminErrorCategoryName.CONFIG_WRITE_ERROR,
            )

    def test_falha_nao_durabilidade_sem_revision_after_e_aceita(self) -> None:
        _valid(
            operation=AdminOperationName.DATABASE_PUT,
            target_kind=AdminTargetKind.DATABASE,
            outcome=AdminOutcome.ERROR,
            revision_before=3,
            revision_after=None,
            error_category=AdminErrorCategoryName.CONFIG_WRITE_ERROR,
        )

    def test_validate_permanece_sem_revisoes(self) -> None:
        _valid(
            operation=AdminOperationName.VALIDATE,
            target_kind=AdminTargetKind.CONFIG,
            outcome=AdminOutcome.SUCCESS,
            revision_before=None,
            revision_after=None,
            error_category=None,
        )
        with pytest.raises(ValueError):
            _valid(
                operation=AdminOperationName.VALIDATE,
                target_kind=AdminTargetKind.CONFIG,
                outcome=AdminOutcome.SUCCESS,
                revision_before=3,
                revision_after=4,
            )
