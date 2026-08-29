"""Descritor de coluna consumido pelo Masking Engine.

O engine nao opera sobre uma string solta de nome de coluna: ele recebe os dois
nomes usados no matching.

- `output_name`: nome da coluna como sera devolvida ao cliente (o alias).
- `origin_name`: nome real da coluna de origem, quando determinavel.

Na Fase 1 `origin_name` e sempre fornecido por quem chama (tipicamente None).
A resolucao automatica a partir do PostgreSQL entra na Fase 3.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ColumnDescriptor:
    """Identificacao de uma coluna do result set."""

    output_name: str
    origin_name: str | None = None

    @property
    def names(self) -> tuple[str, ...]:
        """Nomes avaliados no matching, sem duplicatas e sem None."""
        if self.origin_name is None or self.origin_name == self.output_name:
            return (self.output_name,)
        return (self.output_name, self.origin_name)
