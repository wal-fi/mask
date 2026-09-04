"""Auditoria administrativa: `AdminAudit` fechado por construcao (Fase 7, Etapa 10).

Nivel de unidade: o schema fechado de `AdminAudit`, a imutabilidade, a
serializacao, a rejeicao construtiva de campos proibidos, o enum completo das
doze operacoes e o comportamento best-effort do `AuditLog`. Nada aqui sobe um
servidor HTTP nem toca PostgreSQL — a instrumentacao ponta a ponta esta em
`test_admin_http_audit.py`.

O que se prova: nao existe caminho pelo qual um `match`, um nome de coluna, a
config de um transformer, o corpo de uma requisicao, um token, um secret, um DSN,
uma SQL, um valor ou a mensagem original de uma excecao cheguem a um `AdminAudit`
— eles nem existem na assinatura (secao 13.3).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import pytest

from maskgw.audit import (
    ADMIN_MESSAGE,
    CATEGORY_OUTCOME,
    LOGGER_NAME,
    OPERATION_TARGET_KIND,
    AdminAudit,
    AdminErrorCategoryName,
    AdminOperationName,
    AdminOutcome,
    AdminTargetKind,
    AuditLog,
    QueryAudit,
)


def _uuid4() -> str:
    """Um `request_id` no formato que o servidor gera: `uuid4().hex`."""
    return uuid.uuid4().hex


#: Os UNICOS nove campos que uma entrada administrativa pode ter (secao 13.2).
ALLOWED_ADMIN_FIELDS = {
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

#: Os doze nomes de operacao aprovados, e nada alem deles (secao 13.2).
EXPECTED_OPERATIONS = {
    "adopt",
    "validate",
    "config_put",
    "rule_create",
    "rule_update",
    "rule_delete",
    "rules_reorder",
    "exception_create",
    "exception_update",
    "exception_delete",
    "database_put",
    "sql_put",
}

EXPECTED_TARGET_KINDS = {"rule", "exception", "config", "database", "sql"}
EXPECTED_OUTCOMES = {"success", "rejected", "error"}

#: Marcadores sensiveis que nunca podem aparecer num record.
MATCH = "cpf"
COLUMN = "num_cpf"
SQL = "SELECT cpf FROM cliente"
VALUE = "11122233344"
TOKEN = "admin-token-secreto-de-teste-com-40-caracteres"
HMAC = "hmac-key-marker-com-mais-de-32-caracteres"


def _maskgw(record: logging.LogRecord) -> dict[str, Any]:
    """Campos estruturados de um `LogRecord`, injetados por `extra={"maskgw": ...}`."""
    fields = record.maskgw  # type: ignore[attr-defined]
    assert isinstance(fields, dict)
    return fields


def _entry(**overrides: object) -> AdminAudit:
    """Um evento VALIDO, com membros de enum e `request_id` no formato do servidor.

    Os campos categoricos sao enums (nao `.value`), porque `AdminAudit` os
    guarda e valida por construcao: uma string crua nem constroi.
    """
    fields: dict[str, object] = {
        "request_id": _uuid4(),
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


class TestSchemaFechado:
    def test_entry_tem_exatamente_os_nove_campos(self) -> None:
        assert set(_entry().as_fields()) == ALLOWED_ADMIN_FIELDS

    def test_entry_e_imutavel(self) -> None:
        entry = _entry()
        with pytest.raises(AttributeError):
            entry.request_id = "outro"  # type: ignore[misc]

    def test_entry_usa_slots(self) -> None:
        entry = _entry()
        with pytest.raises((AttributeError, TypeError)):
            entry.campo_novo = "x"  # type: ignore[attr-defined]

    def test_serializacao_e_json_compativel(self) -> None:
        import json

        fields = _entry(
            operation=AdminOperationName.RULE_UPDATE, target_id="rul_" + "a" * 32
        ).as_fields()
        # Sem objeto nao serializavel: um dump JSON completa sem custom encoder.
        dumped = json.dumps(fields)
        assert json.loads(dumped) == fields
        # Os campos categoricos saem como strings, nunca como objeto de enum.
        assert fields["operation"] == "rule_update"
        assert fields["target_kind"] == "rule"
        assert fields["outcome"] == "success"

    def test_valores_sao_serializaveis(self) -> None:
        entry = _entry(
            operation=AdminOperationName.EXCEPTION_UPDATE,
            target_kind=AdminTargetKind.EXCEPTION,
            target_id="exc_" + "b" * 32,
        )
        for value in entry.as_fields().values():
            assert value is None or isinstance(value, (str, int))

    def test_campos_categoricos_saem_como_string(self) -> None:
        fields = _entry(
            outcome=AdminOutcome.ERROR,
            error_category=AdminErrorCategoryName.CONFIG_WRITE_ERROR,
            revision_after=None,
        ).as_fields()
        assert fields["error_category"] == "CONFIG_WRITE_ERROR"
        assert not any(
            hasattr(value, "value") for value in fields.values()
        )  # nenhum objeto de enum


class TestRejeicaoConstrutivaDeCamposProibidos:
    @pytest.mark.parametrize(
        "field",
        [
            "match",
            "column",
            "column_name",
            "transformer",
            "config",
            "body",
            "request_body",
            "token",
            "bearer",
            "secret",
            "hmac_key",
            "dsn",
            "host",
            "user",
            "password",
            "sql",
            "query",
            "rows",
            "values",
            "digest",
            "file_bytes",
            "traceback",
            "message",
            "error_message",
            "exc",
        ],
    )
    def test_parametro_proibido_nao_existe(self, field: str) -> None:
        with pytest.raises(TypeError):
            _entry(**{field: "x"})

    def test_nao_ha_kwargs_livre(self) -> None:
        with pytest.raises(TypeError):
            AdminAudit(  # type: ignore[call-arg]
                request_id=_uuid4(),
                operation=AdminOperationName.ADOPT,
                target_kind=AdminTargetKind.CONFIG,
                target_id=None,
                outcome=AdminOutcome.SUCCESS,
                revision_before=0,
                revision_after=1,
                duration_ms=1,
                error_category=None,
                extra="proibido",
            )


class TestEnums:
    def test_doze_operacoes_exatamente(self) -> None:
        assert {op.value for op in AdminOperationName} == EXPECTED_OPERATIONS

    def test_cinco_target_kinds(self) -> None:
        assert {kind.value for kind in AdminTargetKind} == EXPECTED_TARGET_KINDS

    def test_tres_outcomes(self) -> None:
        assert {outcome.value for outcome in AdminOutcome} == EXPECTED_OUTCOMES


class TestParidadeComOModuloAdmin:
    """`audit/` e neutro: espelha os conjuntos do plano admin sem importa-lo em
    runtime. A paridade EXATA e o que garante que os espelhos nao divergem."""

    def test_error_category_tem_paridade_exata_com_admin(self) -> None:
        # O import fica AQUI, no teste, nunca em `audit/`: importar
        # `maskgw.admin.errors` de dentro de `audit/` fecharia o ciclo
        # `audit -> admin -> audit`. O teste vive fora dos dois.
        from maskgw.admin.errors import AdminErrorCategory

        assert {c.value for c in AdminErrorCategoryName} == {c.value for c in AdminErrorCategory}
        assert {c.name for c in AdminErrorCategoryName} == {c.name for c in AdminErrorCategory}

    def test_id_patterns_tem_paridade_com_config_ids(self) -> None:
        from maskgw.audit.log import _EXCEPTION_ID_PATTERN, _RULE_ID_PATTERN
        from maskgw.config.ids import EXCEPTION_ID_PATTERN, RULE_ID_PATTERN

        assert _RULE_ID_PATTERN.pattern == RULE_ID_PATTERN
        assert _EXCEPTION_ID_PATTERN.pattern == EXCEPTION_ID_PATTERN

    def test_category_outcome_tem_paridade_com_status_by_category(self) -> None:
        """A faixa de status decide o desfecho: 4xx -> rejected, 5xx -> error.

        `CATEGORY_OUTCOME` (em `audit/`) e a fonte que `AdminAudit` valida; ela
        NAO deriva de `STATUS_BY_CATEGORY` (em `admin.http`, que fecharia o ciclo).
        Este teste liga as duas: para toda categoria, o desfecho declarado bate com
        o que a faixa de status daquela tabela implica.
        """
        from maskgw.admin.errors import AdminErrorCategory
        from maskgw.admin.http.responses import STATUS_BY_CATEGORY

        server_error_floor = 500
        for category in AdminErrorCategory:
            name = AdminErrorCategoryName(category.value)
            expected = (
                AdminOutcome.ERROR
                if STATUS_BY_CATEGORY[category] >= server_error_floor
                else AdminOutcome.REJECTED
            )
            assert CATEGORY_OUTCOME[name] is expected, category

    def test_category_outcome_e_total_sobre_as_categorias(self) -> None:
        assert set(CATEGORY_OUTCOME) == set(AdminErrorCategoryName)


class TestMappingOperacaoAlvo:
    def test_mapping_e_total_sobre_as_operacoes(self) -> None:
        assert set(OPERATION_TARGET_KIND) == set(AdminOperationName)

    def test_mapping_bate_com_a_especificacao(self) -> None:
        expected = {
            AdminOperationName.ADOPT: AdminTargetKind.CONFIG,
            AdminOperationName.VALIDATE: AdminTargetKind.CONFIG,
            AdminOperationName.CONFIG_PUT: AdminTargetKind.CONFIG,
            AdminOperationName.RULE_CREATE: AdminTargetKind.RULE,
            AdminOperationName.RULE_UPDATE: AdminTargetKind.RULE,
            AdminOperationName.RULE_DELETE: AdminTargetKind.RULE,
            AdminOperationName.RULES_REORDER: AdminTargetKind.RULE,
            AdminOperationName.EXCEPTION_CREATE: AdminTargetKind.EXCEPTION,
            AdminOperationName.EXCEPTION_UPDATE: AdminTargetKind.EXCEPTION,
            AdminOperationName.EXCEPTION_DELETE: AdminTargetKind.EXCEPTION,
            AdminOperationName.DATABASE_PUT: AdminTargetKind.DATABASE,
            AdminOperationName.SQL_PUT: AdminTargetKind.SQL,
        }
        assert expected == OPERATION_TARGET_KIND


class TestBestEffortDoLogger:
    def test_record_admin_emite_no_logger(self, caplog: pytest.LogCaptureFixture) -> None:
        audit = AuditLog()
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            audit.record_admin(_entry())
        record = caplog.records[0]
        assert record.getMessage() == ADMIN_MESSAGE
        fields = _maskgw(record)
        assert fields["operation"] == "rule_create"
        assert fields["revision_before"] == 3
        assert fields["revision_after"] == 4

    def test_mensagem_fixa_e_curta(self, caplog: pytest.LogCaptureFixture) -> None:
        audit = AuditLog()
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            audit.record_admin(_entry())
        assert caplog.records[0].getMessage() == ADMIN_MESSAGE
        assert len(ADMIN_MESSAGE) < 40

    def test_falha_do_logger_nao_sobe(self) -> None:
        class _Boom(logging.Logger):
            def info(self, *_args: object, **_kwargs: object) -> None:
                msg = "handler quebrado"
                raise RuntimeError(msg)

        boom = _Boom("test.admin.audit.boom")
        audit = AuditLog(boom)
        # Nao pode levantar: a auditoria e best-effort (secao 13).
        audit.record_admin(_entry())

    def test_falha_do_logger_nao_reemite_nada(self, capsys: pytest.CaptureFixture[str]) -> None:
        class _Boom(logging.Logger):
            def info(self, *_args: object, **_kwargs: object) -> None:
                msg = "detalhe interno que nao pode vazar"
                raise RuntimeError(msg)

        audit = AuditLog(_Boom("test.admin.audit.boom2"))
        audit.record_admin(_entry())
        captured = capsys.readouterr()
        assert "detalhe interno" not in captured.out
        assert "detalhe interno" not in captured.err
        assert captured.out == ""


class TestNadaSensivelChegaAoRecord:
    def test_nenhum_marcador_nos_campos(self) -> None:
        rendered = " ".join(str(value) for value in _entry().as_fields().values())
        for marker in (MATCH, COLUMN, SQL, VALUE, TOKEN, HMAC):
            assert marker not in rendered

    def test_target_id_valido_e_permitido(self) -> None:
        # Um ID administrativo (`rul_...`) e explicitamente permitido (secao 13.3),
        # numa operacao que pode carrega-lo (update/delete).
        entry = _entry(operation=AdminOperationName.RULE_UPDATE, target_id="rul_" + "a" * 32)
        assert entry.as_fields()["target_id"] == "rul_" + "a" * 32

    @pytest.mark.parametrize("sensitive", [VALUE, TOKEN, SQL, "invalid input syntax", "SEGREDO"])
    def test_texto_sensivel_nao_cabe_em_request_id(self, sensitive: str) -> None:
        with pytest.raises((ValueError, TypeError)):
            _entry(request_id=sensitive)

    @pytest.mark.parametrize("sensitive", [VALUE, TOKEN, SQL, "inventada", "SEGREDO"])
    def test_texto_sensivel_nao_cabe_em_operation(self, sensitive: str) -> None:
        with pytest.raises((ValueError, TypeError)):
            _entry(operation=sensitive)

    @pytest.mark.parametrize("sensitive", [VALUE, TOKEN, SQL, "qualquer"])
    def test_texto_sensivel_nao_cabe_em_target_kind(self, sensitive: str) -> None:
        with pytest.raises((ValueError, TypeError)):
            _entry(operation=AdminOperationName.RULE_UPDATE, target_kind=sensitive)

    @pytest.mark.parametrize("sensitive", [VALUE, TOKEN, SQL, "nao-e-um-id"])
    def test_texto_sensivel_nao_cabe_em_target_id(self, sensitive: str) -> None:
        with pytest.raises(ValueError):
            _entry(operation=AdminOperationName.RULE_UPDATE, target_id=sensitive)

    @pytest.mark.parametrize("sensitive", [VALUE, TOKEN, SQL, "talvez"])
    def test_texto_sensivel_nao_cabe_em_outcome(self, sensitive: str) -> None:
        with pytest.raises((ValueError, TypeError)):
            _entry(outcome=sensitive)

    @pytest.mark.parametrize("sensitive", [VALUE, TOKEN, SQL, "SEGREDO", "invalid input syntax"])
    def test_texto_sensivel_nao_cabe_em_error_category(self, sensitive: str) -> None:
        with pytest.raises((ValueError, TypeError)):
            _entry(outcome=AdminOutcome.ERROR, error_category=sensitive, revision_after=None)


class TestQueryAuditSemRegressao:
    def test_query_audit_mantem_os_campos(self) -> None:
        from maskgw.audit import SUCCESS

        entry = QueryAudit(request_id="q1", outcome=SUCCESS, duration_ms=3)
        assert set(entry.as_fields()) == {
            "request_id",
            "outcome",
            "duration_ms",
            "row_count",
            "truncated",
            "error_category",
        }

    def test_query_audit_ainda_recusa_sql(self) -> None:
        from maskgw.audit import SUCCESS

        with pytest.raises(TypeError):
            QueryAudit(request_id="q", outcome=SUCCESS, duration_ms=1, sql=SQL)  # type: ignore[call-arg]

    def test_record_de_consulta_intacto(self, caplog: pytest.LogCaptureFixture) -> None:
        from maskgw.audit import MESSAGE, SUCCESS

        audit = AuditLog()
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            audit.record(QueryAudit(request_id="q2", outcome=SUCCESS, duration_ms=1))
        assert caplog.records[0].getMessage() == MESSAGE
