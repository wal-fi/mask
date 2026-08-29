"""Vazamento no adapter (Fase 2).

Criterio de aceite 6 da Fase 2: nenhum valor sensivel aparece em log. E, por
`docs/SECURITY.md`, tambem nao pode aparecer em `repr`, em excecao nem por
qualquer acessor da API publica.

A API publica de `maskgw.db` nao pode oferecer cursor, result set cru,
`fetchone`/`fetchmany`/`fetchall` cru nem iterador de valores originais.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import pytest

import maskgw.db
from maskgw.config import load_config_text
from maskgw.db.postgres import PostgresAdapter
from maskgw.db.result import MaskedResult
from maskgw.masking.engine import MaskingEngine
from tests.conftest import TEST_HMAC_KEY, FakeColumn, FakeConnection, FakeCursor

DB_DIR = Path(__file__).resolve().parents[1] / "src" / "maskgw" / "db"

CPF = "11122233344"
EMAIL = "joao.silva@empresa.com.br"

#: DSN ficticio, apenas para provar que credencial nunca sai em repr ou erro.
CONNINFO = "host=exemplo dbname=x user=gateway password=senha-ficticia-do-banco"

CONFIG = """
masking:
  - match: cpf
    transformer: hmac_sha256
  - match: email
    transformer: regex
    config:
      pattern: "^(.{2}).*(@.*)$"
      replacement: "\\\\1***\\\\2"
"""

#: Unico conjunto de nomes publicos que cada tipo pode expor. Ampliar esta
#: lista tem de ser uma decisao consciente, nao um acidente.
ADAPTER_PUBLIC_API = frozenset({"connect", "close", "execute", "closed"})
RESULT_PUBLIC_API = frozenset({"columns", "decisions", "rows", "column_names", "row_count"})

#: Nomes que jamais podem existir na API publica de db/.
FORBIDDEN_API = frozenset(
    {
        "cursor",
        "connection",
        "conn",
        "fetchone",
        "fetchmany",
        "fetchall",
        "raw",
        "raw_rows",
        "original",
        "original_rows",
        "unmasked",
        "conninfo",
        "dsn",
    }
)


@pytest.fixture
def engine(secrets):
    return MaskingEngine(load_config_text(CONFIG, secrets=secrets))


@pytest.fixture
def adapter(engine):
    cursor = FakeCursor(
        [FakeColumn("cpf"), FakeColumn("email"), FakeColumn("nome")],
        [(CPF, EMAIL, "Maria"), (None, None, None)],
    )
    built = PostgresAdapter(CONNINFO, engine)
    built._connection = cast("Any", FakeConnection(cursor))
    return built


def public_names(obj: object) -> set[str]:
    return {name for name in dir(obj) if not name.startswith("_")}


class TestPublicApiSurface:
    def test_adapter_exposes_only_the_allowed_names(self, adapter):
        assert public_names(adapter) == ADAPTER_PUBLIC_API

    def test_result_exposes_only_the_allowed_names(self, adapter):
        assert public_names(adapter.execute("SELECT ...")) == RESULT_PUBLIC_API

    @pytest.mark.parametrize("name", sorted(FORBIDDEN_API))
    def test_adapter_has_no_raw_accessor(self, adapter, name):
        assert not hasattr(adapter, name)

    @pytest.mark.parametrize("name", sorted(FORBIDDEN_API))
    def test_result_has_no_raw_accessor(self, adapter, name):
        assert not hasattr(adapter.execute("SELECT ..."), name)

    def test_package_exports_nothing_forbidden(self):
        assert not public_names(maskgw.db) & FORBIDDEN_API

    def test_adapter_keeps_its_state_private(self, adapter):
        assert all(name.startswith("_") for name in vars(adapter))

    def test_iterating_the_result_yields_masked_rows(self, adapter):
        rows = list(adapter.execute("SELECT ..."))
        assert all(CPF not in str(row) for row in rows)


class TestNoLogging:
    def test_execute_emits_no_log_records(self, adapter, caplog):
        with caplog.at_level(logging.DEBUG):
            adapter.execute("SELECT cpf, email, nome FROM cliente")
        assert caplog.records == []

    def test_failed_execute_emits_no_log_records(self, engine, caplog):
        broken = PostgresAdapter(CONNINFO, engine)
        with caplog.at_level(logging.DEBUG), pytest.raises(Exception, match="nao esta aberta"):
            broken.execute("SELECT cpf FROM cliente")
        assert caplog.records == []

    def test_db_package_does_not_import_logging(self):
        """A Fase 2 segue sem log: `audit/` so entra na Fase 5 (D-012)."""
        for path in DB_DIR.rglob("*.py"):
            assert "import logging" not in path.read_text(encoding="utf-8"), path.name


class TestNoValueInRepr:
    def test_result_repr_has_no_values(self, adapter):
        result = adapter.execute("SELECT ...")
        rendered = repr(result)
        assert CPF not in rendered
        assert EMAIL not in rendered
        assert "Maria" not in rendered
        assert rendered == "MaskedResult(columns=3, rows=2)"

    def test_result_repr_survives_a_wide_result(self, adapter):
        assert len(repr(adapter.execute("SELECT ..."))) < 80

    def test_adapter_repr_has_no_credentials(self, adapter):
        rendered = repr(adapter)
        assert "senha-ficticia-do-banco" not in rendered
        assert "password" not in rendered
        assert "gateway" not in rendered
        assert rendered == "PostgresAdapter(closed=False)"

    def test_adapter_repr_has_no_hmac_key(self, adapter):
        assert TEST_HMAC_KEY not in repr(adapter)

    def test_decisions_carry_no_values(self, adapter):
        result = adapter.execute("SELECT ...")
        assert CPF not in repr(result.decisions)
        assert EMAIL not in repr(result.decisions)


class TestMaskedOutputHasNoOriginal:
    def test_masked_rows_do_not_contain_the_original(self, adapter):
        result = adapter.execute("SELECT cpf, email, nome FROM cliente")
        flattened = " ".join(str(value) for row in result.rows for value in row)
        assert CPF not in flattened
        assert "joao.silva" not in flattened

    def test_arity_error_reports_only_counts(self):
        with pytest.raises(ValueError) as info:
            MaskedResult(columns=(), decisions=(), rows=((CPF,),))
        assert CPF not in str(info.value)
