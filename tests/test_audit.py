"""Auditoria: somente metadata (Fase 5).

`audit/` e o unico modulo do projeto autorizado a logar. O que se prova aqui e
que nao existe caminho pelo qual uma SQL, um valor ou um segredo cheguem ao
log — nem por parametro, nem por acidente.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from maskgw.audit import FAILURE, LOGGER_NAME, MESSAGE, SUCCESS, AuditLog, QueryAudit

CPF = "11122233344"
EMAIL = "joao@example.com"
SQL = f"SELECT nome, cpf FROM cliente WHERE cpf = '{CPF}'"

AUDIT_DIR = Path(__file__).resolve().parents[1] / "src" / "maskgw" / "audit"

#: Os UNICOS campos que uma entrada de auditoria pode ter.
ALLOWED_FIELDS = {
    "request_id",
    "outcome",
    "duration_ms",
    "row_count",
    "truncated",
    "error_category",
}


@pytest.fixture
def audit():
    return AuditLog()


class TestFieldsAreClosedByConstruction:
    def test_entry_has_only_the_allowed_fields(self):
        entry = QueryAudit(request_id="abc", outcome=SUCCESS, duration_ms=12)
        assert set(entry.as_fields()) == ALLOWED_FIELDS

    def test_there_is_no_parameter_for_the_sql(self):
        with pytest.raises(TypeError):
            QueryAudit(request_id="a", outcome=SUCCESS, duration_ms=1, sql=SQL)  # type: ignore[call-arg]

    @pytest.mark.parametrize(
        "field", ["sql", "query", "rows", "values", "params", "dsn", "password", "secret"]
    )
    def test_forbidden_parameters_do_not_exist(self, field):
        extra: dict[str, object] = {field: "x"}
        with pytest.raises(TypeError):
            QueryAudit(request_id="a", outcome=SUCCESS, duration_ms=1, **extra)  # type: ignore[arg-type]

    def test_entry_is_immutable(self):
        entry = QueryAudit(request_id="a", outcome=SUCCESS, duration_ms=1)
        with pytest.raises(AttributeError):
            entry.request_id = "b"  # type: ignore[misc]


class TestWhatIsLogged:
    def test_success_entry(self, audit, caplog):
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            audit.record(
                QueryAudit(
                    request_id="r1",
                    outcome=SUCCESS,
                    duration_ms=7,
                    row_count=3,
                    truncated=False,
                )
            )
        record = caplog.records[0]
        assert record.getMessage() == MESSAGE
        assert record.maskgw["request_id"] == "r1"
        assert record.maskgw["outcome"] == SUCCESS
        assert record.maskgw["row_count"] == 3
        assert record.maskgw["truncated"] is False
        assert record.maskgw["error_category"] is None

    def test_failure_entry(self, audit, caplog):
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            audit.record(
                QueryAudit(
                    request_id="r2",
                    outcome=FAILURE,
                    duration_ms=2,
                    error_category="QUERY_REJECTED",
                )
            )
        record = caplog.records[0]
        assert record.maskgw["outcome"] == FAILURE
        assert record.maskgw["error_category"] == "QUERY_REJECTED"
        assert record.maskgw["row_count"] is None

    def test_message_is_fixed(self, audit, caplog):
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            audit.record(QueryAudit(request_id="r3", outcome=SUCCESS, duration_ms=1))
        assert caplog.records[0].getMessage() == MESSAGE
        assert len(MESSAGE) < 40


class TestNothingSensitiveCanReachTheLog:
    def test_no_sql_no_values_in_any_record(self, audit, caplog):
        with caplog.at_level(logging.DEBUG):
            audit.record(
                QueryAudit(
                    request_id="r4",
                    outcome=SUCCESS,
                    duration_ms=5,
                    row_count=1,
                    truncated=True,
                )
            )
        rendered = " ".join(
            f"{record.getMessage()} {getattr(record, 'maskgw', '')}" for record in caplog.records
        )
        assert CPF not in rendered
        assert EMAIL not in rendered
        assert "SELECT" not in rendered
        assert "cliente" not in rendered

    def test_request_id_is_the_only_correlation_key(self):
        """Digest da SQL seria um oraculo sobre o predicado. Ver D-035."""
        entry = QueryAudit(request_id="r5", outcome=SUCCESS, duration_ms=1)
        fields = entry.as_fields()
        assert "sql_hash" not in fields
        assert "sql_digest" not in fields
        assert "query_hash" not in fields
        assert fields["request_id"] == "r5"

    def test_audit_repr_has_no_payload(self, audit):
        assert repr(audit) == f"AuditLog(logger={LOGGER_NAME!r})"


class TestModuleBoundary:
    def test_audit_is_the_only_module_importing_logging(self):
        src = Path(__file__).resolve().parents[1] / "src" / "maskgw"
        offenders = [
            path.relative_to(src).as_posix()
            for path in src.rglob("*.py")
            if "import logging" in path.read_text(encoding="utf-8")
        ]
        assert offenders == ["audit/log.py"]

    def test_audit_does_not_import_the_database_or_the_engine(self):
        for path in AUDIT_DIR.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "psycopg" not in source, path.name
            assert "maskgw.db" not in source, path.name
            assert "maskgw.masking" not in source, path.name
