"""Configuracao dos limites de execucao (Fase 4).

Fail-closed como o resto: valor fora dos limites impede a inicializacao.
DSN e credenciais continuam fora do `masking.yaml`.
"""

from __future__ import annotations

import pytest

from maskgw.config import load_gateway_config, load_gateway_config_text
from maskgw.config.models import (
    MAX_MAX_ROWS,
    MAX_STATEMENT_TIMEOUT_MS,
    MIN_MAX_ROWS,
    MIN_STATEMENT_TIMEOUT_MS,
)
from maskgw.errors import ConfigError
from tests.conftest import REPO_CONFIG


class TestDefaults:
    def test_absent_section_uses_defaults(self, secrets):
        config = load_gateway_config_text("masking: []\n", secrets=secrets)
        assert config.database.statement_timeout_ms == 30_000
        assert config.database.max_rows == 1_000

    def test_repository_config_loads(self, secrets):
        config = load_gateway_config(REPO_CONFIG, secrets=secrets)
        assert config.database.statement_timeout_ms >= MIN_STATEMENT_TIMEOUT_MS
        assert config.database.max_rows >= MIN_MAX_ROWS
        assert config.masking.rules

    def test_default_function_policy_is_applied(self, secrets):
        config = load_gateway_config_text("masking: []\n", secrets=secrets)
        assert config.sql.allows("lower")
        assert not config.sql.allows("pg_read_file")


class TestValidValues:
    def test_custom_values(self, secrets):
        text = "database:\n  statement_timeout_ms: 5000\n  max_rows: 25\n"
        config = load_gateway_config_text(text, secrets=secrets)
        assert config.database.statement_timeout_ms == 5000
        assert config.database.max_rows == 25

    @pytest.mark.parametrize("value", [MIN_STATEMENT_TIMEOUT_MS, 30_000, MAX_STATEMENT_TIMEOUT_MS])
    def test_timeout_bounds_are_inclusive(self, secrets, value):
        text = f"database:\n  statement_timeout_ms: {value}\n"
        assert (
            load_gateway_config_text(text, secrets=secrets).database.statement_timeout_ms == value
        )

    @pytest.mark.parametrize("value", [MIN_MAX_ROWS, 1_000, MAX_MAX_ROWS])
    def test_max_rows_bounds_are_inclusive(self, secrets, value):
        text = f"database:\n  max_rows: {value}\n"
        assert load_gateway_config_text(text, secrets=secrets).database.max_rows == value


class TestFailClosed:
    @pytest.mark.parametrize(
        "text",
        [
            "database:\n  statement_timeout_ms: 0\n",
            "database:\n  statement_timeout_ms: 50\n",
            "database:\n  statement_timeout_ms: -1\n",
            f"database:\n  statement_timeout_ms: {MAX_STATEMENT_TIMEOUT_MS + 1}\n",
            "database:\n  statement_timeout_ms: nao-e-numero\n",
            "database:\n  max_rows: 0\n",
            "database:\n  max_rows: -5\n",
            f"database:\n  max_rows: {MAX_MAX_ROWS + 1}\n",
            "database:\n  max_rows: 1.5\n",
        ],
    )
    def test_out_of_bounds_prevents_startup(self, secrets, text):
        with pytest.raises(ConfigError):
            load_gateway_config_text(text, secrets=secrets)

    def test_unknown_key_prevents_startup(self, secrets):
        with pytest.raises(ConfigError, match="database"):
            load_gateway_config_text("database:\n  timeout: 1000\n", secrets=secrets)

    def test_unknown_sql_key_prevents_startup(self, secrets):
        with pytest.raises(ConfigError, match="sql"):
            load_gateway_config_text("sql:\n  allow_everything: true\n", secrets=secrets)

    @pytest.mark.parametrize(
        "field", ["dsn", "url", "host", "password", "user", "connection_string"]
    )
    def test_credentials_cannot_be_declared(self, secrets, field):
        """Credencial no masking.yaml e erro fatal, nao um campo ignorado."""
        with pytest.raises(ConfigError):
            load_gateway_config_text(f"database:\n  {field}: qualquer-coisa\n", secrets=secrets)

    def test_error_does_not_echo_the_value(self, secrets):
        text = "database:\n  password: senha-ficticia-do-banco\n"
        with pytest.raises(ConfigError) as info:
            load_gateway_config_text(text, secrets=secrets)
        assert "senha-ficticia-do-banco" not in str(info.value)


class TestSqlPolicySection:
    def test_extra_allowed_pg_function(self, secrets):
        text = "sql:\n  allowed_pg_functions:\n    - pg_backend_pid\n"
        config = load_gateway_config_text(text, secrets=secrets)
        assert config.sql.allows("pg_backend_pid")
        assert not config.sql.allows("pg_read_file")

    def test_extra_denied_function(self, secrets):
        text = "sql:\n  denied_functions:\n    - minha_funcao\n"
        config = load_gateway_config_text(text, secrets=secrets)
        assert not config.sql.allows("minha_funcao")
        assert config.sql.allows("lower")

    def test_config_cannot_reopen_a_dangerous_function(self, secrets):
        """Liberar `pg_read_file` exige listar explicitamente; nao e acidente."""
        config = load_gateway_config_text("sql:\n  allowed_pg_functions: []\n", secrets=secrets)
        assert not config.sql.allows("pg_read_file")


class TestMaskingIsUnchanged:
    def test_gateway_config_carries_the_same_policy(self, secrets):
        text = "masking:\n  - match: cpf\n    transformer: md5\n"
        config = load_gateway_config_text(text, secrets=secrets)
        assert len(config.masking.rules) == 1
        assert config.masking.rules[0].transformer_name == "md5"

    def test_invalid_masking_still_fails(self, secrets):
        text = "database:\n  max_rows: 10\nmasking:\n  - match: cpf\n    transformer: inexistente\n"
        with pytest.raises(ConfigError, match="transformer"):
            load_gateway_config_text(text, secrets=secrets)
