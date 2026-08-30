"""Criterios de aceite 4, 5, 6 e 7 da Fase 1 (docs/ROADMAP.md).

Pipeline: EXCEPTION -> ORIGINAL / MASKING MATCH -> TRANSFORMER / NO MATCH -> ORIGINAL.
"""

from __future__ import annotations

import hashlib

import pytest

from maskgw.config import load_config_text
from maskgw.masking.descriptor import ColumnDescriptor
from maskgw.masking.engine import Action, MaskingEngine

CPF = "12345678901"
CPF_MD5 = hashlib.md5(CPF.encode(), usedforsecurity=False).hexdigest()

CONFIG = """
masking:
  - match: cpf
    transformer: md5
  - match: email
    transformer: fixed
    config:
      value: "[REDACTED]"

exceptions:
  - match: tipo_cpf
    mode: exact
"""


@pytest.fixture
def engine(secrets):
    return MaskingEngine(load_config_text(CONFIG, secrets=secrets))


def column(output_name: str, origin_name: str | None = None) -> ColumnDescriptor:
    return ColumnDescriptor(output_name=output_name, origin_name=origin_name)


class TestMaskingMatch:
    @pytest.mark.parametrize(
        "name", ["cpf", "CPF", "Cpf", "cPf", "num_cpf", "cod_cpf", "cliente_cpf", "cpf_cliente"]
    )
    def test_matched_column_is_masked(self, engine, name):
        assert engine.mask_value(column(name), CPF) == CPF_MD5

    def test_distinct_rules_use_distinct_transformers(self, engine):
        assert engine.mask_value(column("cpf"), CPF) == CPF_MD5
        assert engine.mask_value(column("email"), "a@b.co") == "[REDACTED]"


class TestExceptionPriority:
    """Criterios 4 e 5: exception vence a regra, pelo nome autoritativo.

    Desde a Fase 6.1 a exception e avaliada contra `origin_name` quando ele
    existe, e contra `output_name` so quando nao ha origem. Ver D-042.
    """

    def test_exception_returns_original(self, engine):
        assert engine.mask_value(column("tipo_cpf"), "fisica") == "fisica"

    def test_sibling_columns_still_masked(self, engine):
        assert engine.mask_value(column("cpf"), CPF) == CPF_MD5
        assert engine.mask_value(column("num_cpf"), CPF) == CPF_MD5

    def test_exception_wins_even_when_rule_also_matches(self, engine):
        decision = engine.decide(column("tipo_cpf"))
        assert decision.action is Action.EXCEPTION
        assert decision.transformer_name is None

    def test_exception_matched_by_origin_name(self, engine):
        """SELECT tipo_cpf AS cpf_x -> exception vence pelo origin_name."""
        assert engine.mask_value(column("cpf_x", "tipo_cpf"), "fisica") == "fisica"

    def test_alias_cannot_create_an_exception(self, engine):
        """Fase 6.1 (D-042): `SELECT cpf AS tipo_cpf` deixa de sair em claro.

        Antes a exception casava tambem o `output_name`, que o cliente escolhe
        — o que fazia de toda exception uma primitiva de desmascaramento.
        """
        assert engine.mask_value(column("tipo_cpf", "cpf"), CPF) == CPF_MD5
        assert engine.decide(column("tipo_cpf", "cpf")).action is Action.MASK

    def test_exception_applies_by_output_name_when_there_is_no_origin(self, engine):
        """Sem origem, o nome de saida e o unico nome autoritativo."""
        assert engine.mask_value(column("tipo_cpf"), "fisica") == "fisica"

    def test_exception_declared_after_rule_still_wins(self, secrets):
        """A ordem no arquivo nao afeta a precedencia das exceptions."""
        policy = load_config_text(
            "masking:\n  - match: cpf\n    transformer: md5\n"
            "exceptions:\n  - match: cpf\n    mode: exact\n",
            secrets=secrets,
        )
        assert MaskingEngine(policy).mask_value(column("cpf"), CPF) == CPF


class TestDefaultAllow:
    """Criterio 6: sem correspondencia, valor original."""

    def test_unmatched_column_passes_through(self, engine):
        assert engine.mask_value(column("nome"), "Maria") == "Maria"

    def test_unmatched_preserves_type(self, engine):
        assert engine.mask_value(column("idade"), 42) == 42
        assert engine.mask_value(column("ativo"), True) is True

    def test_decision_is_allow(self, engine):
        assert engine.decide(column("nome")).action is Action.ALLOW

    def test_empty_policy_masks_nothing(self, secrets):
        engine = MaskingEngine(load_config_text("", secrets=secrets))
        assert engine.mask_value(column("cpf"), CPF) == CPF


class TestAliasProtection:
    """Bypass por alias coberto pelo matching de dois nomes."""

    def test_alias_masked_by_origin(self, engine):
        assert engine.mask_value(column("documento", "cpf"), CPF) == CPF_MD5

    def test_alias_without_origin_passes(self, engine):
        """Sem origem determinavel, resta o `output_name`.

        Na Fase 2 este era o caso de TODA consulta com alias. Desde a Fase 3 a
        proveniencia cobre alias, subquery, CTE, JOIN, cast e view; sobram as
        colunas que o proprio PostgreSQL declara sem origem — expressoes,
        literais, agregados e UNION.
        """
        assert engine.mask_value(column("documento"), CPF) == CPF

    def test_output_name_alone_is_enough(self, engine):
        assert engine.mask_value(column("cpf_cliente", "documento"), CPF) == CPF_MD5


class TestNull:
    """Criterio 7: NULL permanece NULL em todos os ramos."""

    @pytest.mark.parametrize("name", ["cpf", "tipo_cpf", "nome", "email"])
    def test_null_stays_null(self, engine, name):
        assert engine.mask_value(column(name), None) is None

    def test_null_in_rows(self, engine):
        columns = [column("cpf"), column("nome")]
        assert engine.mask_rows(columns, [[None, None]]) == [[None, None]]

    def test_empty_string_is_not_null(self, engine):
        assert engine.mask_value(column("cpf"), "") is not None


class TestRows:
    def test_mask_row(self, engine):
        columns = [column("cpf"), column("nome"), column("tipo_cpf")]
        assert engine.mask_row(columns, [CPF, "Maria", "fisica"]) == [CPF_MD5, "Maria", "fisica"]

    def test_mask_rows_matches_mask_row(self, engine):
        columns = [column("documento", "cpf"), column("nome")]
        rows = [[CPF, "Maria"], [None, "Joao"], ["99999999999", None]]
        assert engine.mask_rows(columns, rows) == [engine.mask_row(columns, row) for row in rows]

    def test_arity_mismatch_raises_without_values(self, engine):
        columns = [column("cpf")]
        with pytest.raises(ValueError) as info:
            engine.mask_row(columns, [CPF, "extra"])
        assert CPF not in str(info.value)

    def test_empty_result_set(self, engine):
        assert engine.mask_rows([column("cpf")], []) == []


class TestDecisionMetadata:
    def test_decision_carries_no_values(self, engine):
        decision = engine.decide(column("documento", "cpf"))
        assert decision.action is Action.MASK
        assert decision.transformer_name == "md5"
        assert decision.output_name == "documento"
        assert decision.origin_name == "cpf"
        assert CPF not in repr(decision)

    def test_rule_index_identifies_the_rule(self, engine):
        assert engine.decide(column("cpf")).rule_index == 0
        assert engine.decide(column("email")).rule_index == 1


class TestRuleConflict:
    """Conflito entre regras: vence a primeira do arquivo (D-004)."""

    def test_first_rule_wins(self, secrets):
        policy = load_config_text(
            "masking:\n"
            "  - match: cpf\n"
            "    transformer: fixed\n"
            "    config:\n"
            "      value: PRIMEIRA\n"
            "  - match: cliente\n"
            "    transformer: fixed\n"
            "    config:\n"
            "      value: SEGUNDA\n",
            secrets=secrets,
        )
        engine = MaskingEngine(policy)
        assert engine.mask_value(column("cliente_cpf"), CPF) == "PRIMEIRA"

    def test_conflict_resolution_is_stable_across_names(self, secrets):
        policy = load_config_text(
            "masking:\n"
            "  - match: cpf\n"
            "    transformer: fixed\n"
            "    config:\n"
            "      value: PRIMEIRA\n"
            "  - match: doc\n"
            "    transformer: fixed\n"
            "    config:\n"
            "      value: SEGUNDA\n",
            secrets=secrets,
        )
        engine = MaskingEngine(policy)
        # A regra 0 casa pelo origin_name, a regra 1 pelo output_name.
        assert engine.mask_value(column("doc", "cpf"), CPF) == "PRIMEIRA"
