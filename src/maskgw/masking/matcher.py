"""Matchers de coluna.

Um nome so nao decide nada: cada matcher avalia `output_name` e `origin_name`
do `ColumnDescriptor`. Basta UM dos nomes casar para a regra ser aplicada.

Isso e o que impede o bypass por alias:

    SELECT cpf AS documento
        output_name = "documento"  -> nao casa
        origin_name = "cpf"        -> casa
        resultado: mascarado

Para EXCEPTIONS a regra e outra, desde a Fase 6.1: vale o nome autoritativo da
coluna — `origin_name` quando existe, `output_name` quando nao ha origem. Um
alias nao pode criar uma exception. Ver `ExceptionMatcher.find_by_name` e
D-042.
"""

from __future__ import annotations

from collections.abc import Sequence

from maskgw.masking.descriptor import ColumnDescriptor
from maskgw.masking.rules import MaskingException, MaskingRule, MatchSpec


def spec_matches_column(spec: MatchSpec, column: ColumnDescriptor) -> bool:
    """True se o criterio casar `output_name` OU `origin_name`."""
    return any(spec.matches(name) for name in column.names)


class ExceptionMatcher:
    """Localiza a primeira exception que cobre a coluna.

    Exceptions tem prioridade absoluta: se alguma casar, nenhuma regra de
    masking e avaliada.
    """

    def __init__(self, exceptions: Sequence[MaskingException]) -> None:
        self._exceptions = tuple(exceptions)

    def find(self, column: ColumnDescriptor) -> MaskingException | None:
        for exception in self._exceptions:
            if spec_matches_column(exception.spec, column):
                return exception
        return None

    def find_by_name(self, name: str) -> MaskingException | None:
        """Avalia a exception contra UM nome — o autoritativo da coluna.

        O `output_name` e escolhido pelo cliente. Deixar a exception casar por
        ele transformava toda exception configurada numa primitiva de
        desmascaramento: `SELECT cpf AS tipo_cpf` saia em claro. Quando a
        origem e conhecida, e ela que responde. Ver D-042.
        """
        for exception in self._exceptions:
            if exception.spec.matches(name):
                return exception
        return None


class RuleMatcher:
    """Localiza a primeira regra de masking que cobre a coluna.

    Em caso de conflito entre regras, vence a que aparece primeiro no
    `masking.yaml`. Ver docs/DECISIONS.md (D-004).
    """

    def __init__(self, rules: Sequence[MaskingRule]) -> None:
        self._rules = tuple(rules)

    def find(self, column: ColumnDescriptor) -> MaskingRule | None:
        for rule in self._rules:
            if spec_matches_column(rule.spec, column):
                return rule
        return None
