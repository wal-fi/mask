"""Criterios de aceite 3 e 14 da Fase 1 (docs/ROADMAP.md).

Matching: case-insensitive + contains, avaliado sobre output_name E origin_name.
"""

from __future__ import annotations

import pytest

from maskgw.masking.descriptor import ColumnDescriptor
from maskgw.masking.matcher import ExceptionMatcher, RuleMatcher, spec_matches_column
from maskgw.masking.rules import MaskingException, MaskingRule, MatchMode, MatchSpec
from maskgw.masking.transformers.simple import FixedTransformer

CONTAINS_CPF = MatchSpec(pattern="cpf")
EXACT_CPF = MatchSpec(pattern="cpf", mode=MatchMode.EXACT)


def column(output_name: str, origin_name: str | None = None) -> ColumnDescriptor:
    return ColumnDescriptor(output_name=output_name, origin_name=origin_name)


class TestContainsCaseInsensitive:
    """Criterio 3: a regra `cpf` casa todas as variacoes do TEST-PLAN."""

    @pytest.mark.parametrize(
        "name",
        [
            "cpf",
            "CPF",
            "Cpf",
            "cPf",
            "num_cpf",
            "cod_cpf",
            "cliente_cpf",
            "cpf_cliente",
            "nr_cpf",
            "tipo_cpf",
            "CPF_CLIENTE",
            "NumCpfCliente",
        ],
    )
    def test_matches(self, name):
        assert CONTAINS_CPF.matches(name)

    @pytest.mark.parametrize("name", ["nome", "email", "cp", "pf", "c_p_f", "documento", ""])
    def test_does_not_match(self, name):
        assert not CONTAINS_CPF.matches(name)

    def test_case_sensitive_mode(self):
        spec = MatchSpec(pattern="cpf", case_sensitive=True)
        assert spec.matches("num_cpf")
        assert not spec.matches("num_CPF")

    def test_casefold_handles_non_ascii(self):
        spec = MatchSpec(pattern="endereço")
        assert spec.matches("ENDEREÇO_CLIENTE")


class TestExactMode:
    def test_matches_only_full_name(self):
        assert EXACT_CPF.matches("cpf")
        assert EXACT_CPF.matches("CPF")
        assert not EXACT_CPF.matches("num_cpf")
        assert not EXACT_CPF.matches("cpf_cliente")

    def test_exact_is_case_insensitive_by_default(self):
        assert MatchSpec(pattern="tipo_cpf", mode=MatchMode.EXACT).matches("TIPO_CPF")


class TestNoneName:
    """Criterio 14: origin_name ausente nao pode quebrar o matching."""

    def test_none_never_matches(self):
        assert not CONTAINS_CPF.matches(None)

    def test_column_without_origin_uses_output_only(self):
        assert spec_matches_column(CONTAINS_CPF, column("num_cpf"))
        assert not spec_matches_column(CONTAINS_CPF, column("documento"))

    def test_names_property_skips_none(self):
        assert column("documento").names == ("documento",)

    def test_names_property_deduplicates(self):
        assert column("cpf", "cpf").names == ("cpf",)


class TestDualName:
    """Matching por output_name OU origin_name."""

    def test_alias_hides_output_but_origin_matches(self):
        """SELECT cpf AS documento -> mascarado pelo origin_name."""
        assert spec_matches_column(CONTAINS_CPF, column("documento", "cpf"))

    def test_output_matches_while_origin_does_not(self):
        """SELECT documento AS cpf_cliente -> mascarado pelo output_name."""
        assert spec_matches_column(CONTAINS_CPF, column("cpf_cliente", "documento"))

    def test_neither_matches(self):
        assert not spec_matches_column(CONTAINS_CPF, column("documento", "identificador"))

    def test_both_match(self):
        assert spec_matches_column(CONTAINS_CPF, column("cpf", "cpf"))

    def test_case_variation_across_the_two_names(self):
        assert spec_matches_column(CONTAINS_CPF, column("DOC", "Cliente_CPF"))


class TestRuleMatcher:
    def test_returns_first_matching_rule(self):
        rules = [
            MaskingRule(MatchSpec("cpf"), FixedTransformer("a"), "fixed", 0),
            MaskingRule(MatchSpec("cpf"), FixedTransformer("b"), "fixed", 1),
        ]
        found = RuleMatcher(rules).find(column("num_cpf"))
        assert found is not None
        assert found.index == 0

    def test_returns_none_when_nothing_matches(self):
        rules = [MaskingRule(MatchSpec("cpf"), FixedTransformer("a"), "fixed", 0)]
        assert RuleMatcher(rules).find(column("nome")) is None

    def test_empty_ruleset(self):
        assert RuleMatcher([]).find(column("cpf")) is None


class TestExceptionMatcher:
    def test_returns_first_matching_exception(self):
        exceptions = [
            MaskingException(MatchSpec("tipo_cpf", MatchMode.EXACT), 0),
            MaskingException(MatchSpec("cpf"), 1),
        ]
        found = ExceptionMatcher(exceptions).find(column("tipo_cpf"))
        assert found is not None
        assert found.index == 0

    def test_matches_by_origin_name(self):
        exceptions = [MaskingException(MatchSpec("tipo_cpf", MatchMode.EXACT), 0)]
        assert ExceptionMatcher(exceptions).find(column("x", "tipo_cpf")) is not None

    def test_empty_exceptions(self):
        assert ExceptionMatcher([]).find(column("cpf")) is None
