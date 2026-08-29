"""Masking Engine.

Nucleo puro: sem I/O, sem banco, sem MCP, sem rede.

Pipeline, por coluna:

    EXCEPTION MATCH   -> ORIGINAL
    MASKING MATCH     -> TRANSFORMER
    NO MATCH          -> ORIGINAL      (default ALLOW do MVP)

NULL permanece NULL em qualquer ramo.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from maskgw.masking.descriptor import ColumnDescriptor
from maskgw.masking.matcher import ExceptionMatcher, RuleMatcher
from maskgw.masking.rules import MaskingPolicy
from maskgw.masking.transformers.base import Transformer


class Action(StrEnum):
    """Desfecho do pipeline para uma coluna."""

    EXCEPTION = "exception"
    MASK = "mask"
    ALLOW = "allow"


@dataclass(frozen=True, slots=True)
class Decision:
    """Resultado do matching de uma coluna.

    Contem apenas metadata — nenhum valor de dado. E seguro para auditoria.
    """

    action: Action
    output_name: str
    origin_name: str | None = None
    rule_index: int | None = None
    transformer_name: str | None = None


class MaskingEngine:
    """Aplica uma `MaskingPolicy` a valores de result set."""

    def __init__(self, policy: MaskingPolicy) -> None:
        self._policy = policy
        self._exceptions = ExceptionMatcher(policy.exceptions)
        self._rules = RuleMatcher(policy.rules)

    @property
    def policy(self) -> MaskingPolicy:
        return self._policy

    def _resolve(self, column: ColumnDescriptor) -> tuple[Decision, Transformer | None]:
        """Decide o desfecho da coluna e devolve o transformer, se houver."""
        exception = self._exceptions.find(column)
        if exception is not None:
            # Prioridade absoluta: nenhuma regra de masking e avaliada.
            decision = Decision(
                action=Action.EXCEPTION,
                output_name=column.output_name,
                origin_name=column.origin_name,
                rule_index=exception.index,
            )
            return decision, None

        rule = self._rules.find(column)
        if rule is not None:
            decision = Decision(
                action=Action.MASK,
                output_name=column.output_name,
                origin_name=column.origin_name,
                rule_index=rule.index,
                transformer_name=rule.transformer_name,
            )
            return decision, rule.transformer

        decision = Decision(
            action=Action.ALLOW,
            output_name=column.output_name,
            origin_name=column.origin_name,
        )
        return decision, None

    def decide(self, column: ColumnDescriptor) -> Decision:
        """Decisao de matching para uma coluna, sem tocar em valores."""
        decision, _ = self._resolve(column)
        return decision

    def mask_value(self, column: ColumnDescriptor, value: Any) -> Any:  # noqa: ANN401
        """Aplica a politica a um unico valor.

        `Any` e deliberado: o valor vem do banco e pode ter qualquer tipo. A
        saida e `str` quando ha transformacao, ou o valor original quando nao ha.
        """
        if value is None:
            # NULL permanece NULL antes de qualquer matching.
            return None
        _, transformer = self._resolve(column)
        if transformer is None:
            return value
        return transformer.apply(value)

    def mask_row(self, columns: Sequence[ColumnDescriptor], row: Sequence[Any]) -> list[Any]:
        """Aplica a politica a uma linha."""
        self._check_arity(columns, row)
        return [self.mask_value(column, value) for column, value in zip(columns, row, strict=True)]

    def mask_rows(
        self,
        columns: Sequence[ColumnDescriptor],
        rows: Iterable[Sequence[Any]],
    ) -> list[list[Any]]:
        """Aplica a politica a varias linhas, resolvendo o matching uma vez."""
        resolved = [self._resolve(column) for column in columns]
        transformers = [transformer for _, transformer in resolved]

        masked: list[list[Any]] = []
        for row in rows:
            self._check_arity(columns, row)
            masked.append(
                [
                    value if value is None or transformer is None else transformer.apply(value)
                    for transformer, value in zip(transformers, row, strict=True)
                ]
            )
        return masked

    @staticmethod
    def _check_arity(columns: Sequence[ColumnDescriptor], row: Sequence[Any]) -> None:
        if len(columns) != len(row):
            # Mensagem sem valores: apenas as contagens.
            msg = f"linha com {len(row)} valores para {len(columns)} colunas"
            raise ValueError(msg)
