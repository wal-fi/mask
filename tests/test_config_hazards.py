"""Riscos de configuracao confirmados na revisao de seguranca da Fase 1.

Estes testes NAO descrevem comportamento desejado: eles fixam o comportamento
atual para que qualquer mudanca futura seja percebida.

Em todos os casos o Masking Engine funciona como especificado — quem abre a
porta e o `masking.yaml`. Ver docs/DECISIONS.md (D-014).
"""

from __future__ import annotations

import pytest

from maskgw.config import load_config_text
from maskgw.masking import ColumnDescriptor, MaskingEngine

CPF = "12345678901"


@pytest.fixture
def engine_factory(secrets):
    def _build(yaml_text: str) -> MaskingEngine:
        return MaskingEngine(load_config_text(yaml_text, secrets=secrets))

    return _build


class TestBroadExceptionDisablesRule:
    """H-1: exception larga desliga a regra inteira, em silencio.

    `mode` das exceptions tem default `contains`, igual ao das regras. Uma
    exception `cpf` cobre tudo que a regra `cpf` cobriria.
    """

    def test_exception_with_same_pattern_disables_masking(self, engine_factory):
        engine = engine_factory(
            "masking:\n  - match: cpf\n    transformer: md5\nexceptions:\n  - match: cpf\n"
        )
        assert engine.mask_value(ColumnDescriptor("cliente_cpf"), CPF) == CPF

    def test_single_letter_exception_disables_masking(self, engine_factory):
        engine = engine_factory(
            "masking:\n  - match: cpf\n    transformer: md5\nexceptions:\n  - match: c\n"
        )
        assert engine.mask_value(ColumnDescriptor("num_cpf"), CPF) == CPF

    def test_exact_mode_keeps_the_rule_effective(self, engine_factory):
        """Com `mode: exact` a exception fica restrita, como no doc."""
        engine = engine_factory(
            "masking:\n  - match: cpf\n    transformer: md5\n"
            "exceptions:\n  - match: tipo_cpf\n    mode: exact\n"
        )
        assert engine.mask_value(ColumnDescriptor("tipo_cpf"), "fisica") == "fisica"
        assert engine.mask_value(ColumnDescriptor("num_cpf"), CPF) != CPF


class TestTransformerCanBeConfiguredAsIdentity:
    """H-2 e H-3: transformer configurado de forma inocua devolve o original."""

    def test_regex_identity_replacement_returns_original(self, engine_factory):
        engine = engine_factory(
            "masking:\n"
            "  - match: cpf\n"
            "    transformer: regex\n"
            "    config:\n"
            "      pattern: '(.*)'\n"
            "      replacement: '\\1'\n"
        )
        assert engine.mask_value(ColumnDescriptor("cpf"), CPF) == CPF

    def test_truncate_longer_than_value_returns_original(self, engine_factory):
        engine = engine_factory(
            "masking:\n  - match: cpf\n    transformer: truncate\n    config:\n      length: 99\n"
        )
        assert engine.mask_value(ColumnDescriptor("cpf"), CPF) == CPF


class TestRandomLeaksLength:
    """H-4: `preserve_length: true` publica o comprimento do valor original."""

    @pytest.mark.parametrize("value", ["abc", "senha-muito-longa-do-usuario"])
    def test_output_length_equals_input_length(self, engine_factory, value):
        engine = engine_factory(
            "masking:\n"
            "  - match: senha\n"
            "    transformer: random\n"
            "    config:\n"
            "      strategy: alphanumeric\n"
        )
        masked = engine.mask_value(ColumnDescriptor("senha"), value)
        assert len(masked) == len(value)

    def test_fixed_length_does_not_leak(self, engine_factory):
        """Mitigacao disponivel: preserve_length false + length fixo."""
        engine = engine_factory(
            "masking:\n"
            "  - match: senha\n"
            "    transformer: random\n"
            "    config:\n"
            "      strategy: alphanumeric\n"
            "      preserve_length: false\n"
            "      length: 12\n"
        )
        short = engine.mask_value(ColumnDescriptor("senha"), "abc")
        long = engine.mask_value(ColumnDescriptor("senha"), "senha-muito-longa")
        assert len(short) == len(long) == 12
