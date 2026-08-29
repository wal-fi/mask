"""Criterio de aceite 16 da Fase 1 (docs/ROADMAP.md).

Nenhum valor processado, nem a chave HMAC, pode aparecer em log, repr,
excecao ou mensagem de erro.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from maskgw.config import load_config_text
from maskgw.errors import ConfigError
from maskgw.masking.descriptor import ColumnDescriptor
from maskgw.masking.engine import MaskingEngine
from tests.conftest import TEST_HMAC_KEY

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "maskgw"

SENSITIVE = "12345678901"
SENSITIVE_EMAIL = "joao.silva@empresa.com.br"

CONFIG = """
masking:
  - match: cpf
    transformer: hmac_sha256
  - match: email
    transformer: regex
    config:
      pattern: "^(.{2}).*(@.*)$"
      replacement: "\\\\1***\\\\2"
  - match: telefone
    transformer: random
    config:
      strategy: digits

exceptions:
  - match: tipo_cpf
    mode: exact
"""


@pytest.fixture
def engine(secrets):
    return MaskingEngine(load_config_text(CONFIG, secrets=secrets))


class TestNoLogging:
    def test_masking_emits_no_log_records(self, engine, caplog):
        columns = [
            ColumnDescriptor("documento", "cpf"),
            ColumnDescriptor("email"),
            ColumnDescriptor("nome"),
        ]
        with caplog.at_level(logging.DEBUG):
            engine.mask_rows(columns, [[SENSITIVE, SENSITIVE_EMAIL, "Maria"]])
        assert caplog.records == []

    def test_config_loading_emits_no_log_records(self, secrets, caplog):
        with caplog.at_level(logging.DEBUG):
            load_config_text(CONFIG, secrets=secrets)
        assert caplog.records == []

    def test_core_does_not_import_logging(self):
        """A Fase 1 nao registra nada: audit/ so entra na Fase 5."""
        for path in SRC_DIR.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "import logging" not in source, f"{path.name} usa logging"


class TestNoValueInRepr:
    def test_policy_repr_has_no_secret(self, secrets):
        policy = load_config_text(CONFIG, secrets=secrets)
        assert TEST_HMAC_KEY not in repr(policy)

    def test_engine_repr_has_no_values(self, engine):
        engine.mask_value(ColumnDescriptor("cpf"), SENSITIVE)
        assert SENSITIVE not in repr(engine)
        assert SENSITIVE not in repr(engine.policy)

    def test_decision_repr_has_no_values(self, engine):
        decision = engine.decide(ColumnDescriptor("documento", "cpf"))
        assert SENSITIVE not in repr(decision)


class TestNoValueInExceptions:
    def test_arity_error_reports_only_counts(self, engine):
        with pytest.raises(ValueError) as info:
            engine.mask_row([ColumnDescriptor("cpf")], [SENSITIVE, SENSITIVE_EMAIL])
        message = str(info.value)
        assert SENSITIVE not in message
        assert SENSITIVE_EMAIL not in message

    def test_config_error_does_not_echo_param_values(self, secrets):
        text = (
            "masking:\n"
            "  - match: cpf\n"
            "    transformer: fixed\n"
            "    config:\n"
            "      value: 12345678901\n"
        )
        with pytest.raises(ConfigError) as info:
            load_config_text(text, secrets=secrets)
        assert SENSITIVE not in str(info.value)

    def test_config_error_does_not_echo_secret(self, secrets):
        text = (
            "masking:\n"
            "  - match: cpf\n"
            "    transformer: hmac_sha256\n"
            "    config:\n"
            "      secret: super-secreto-do-cliente\n"
        )
        with pytest.raises(ConfigError) as info:
            load_config_text(text, secrets=secrets)
        assert "super-secreto-do-cliente" not in str(info.value)

    def test_traceback_chain_has_no_secret(self, secrets):
        """A causa encadeada tambem nao pode conter a chave."""
        text = "masking:\n  - match: cpf\n    transformer: hmac_sha256\n    config:\n      key: x\n"
        with pytest.raises(ConfigError) as info:
            load_config_text(text, secrets=secrets)
        chain: list[str] = []
        current: BaseException | None = info.value
        while current is not None:
            chain.append(str(current))
            current = current.__cause__
        assert TEST_HMAC_KEY not in " ".join(chain)


class TestMaskedOutputDoesNotContainOriginal:
    def test_hmac_output_has_no_original(self, engine):
        masked = engine.mask_value(ColumnDescriptor("documento", "cpf"), SENSITIVE)
        assert masked is not None
        assert SENSITIVE not in masked

    def test_random_output_has_no_original(self, engine):
        masked = engine.mask_value(ColumnDescriptor("telefone"), "11987654321")
        assert masked is not None
        assert masked != "11987654321"

    def test_regex_output_keeps_only_configured_fragment(self, engine):
        masked = engine.mask_value(ColumnDescriptor("email"), SENSITIVE_EMAIL)
        assert masked == "jo***@empresa.com.br"
        assert "silva" not in masked
