"""Contrato dos transformers.

Um transformer e responsavel SOMENTE pela transformacao. Ele nao conhece
regras, exceptions, matching, banco ou MCP.

Regras invariantes:

- NULL permanece NULL: `apply(None)` devolve None sem chamar o transformer.
- A saida e sempre `str` (ou None). Nao ha transformacao dependente de tipo.
- Nenhum transformer registra o valor recebido em log ou mensagem de erro.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

#: Marcador usado quando um transformer nao consegue produzir uma saida valida.
#: Nunca devolver o valor original nesse caso (fail-closed).
REDACTED = "[REDACTED]"


class Transformer(ABC):
    """Transformacao determinada exclusivamente pela configuracao."""

    #: Mesma entrada produz sempre a mesma saida. `random` e a excecao.
    deterministic: ClassVar[bool] = True

    def apply(self, value: object) -> str | None:
        """Ponto de entrada do engine. Trata NULL e normaliza para texto."""
        if value is None:
            return None
        text = value if isinstance(value, str) else str(value)
        return self.transform(text)

    @abstractmethod
    def transform(self, value: str) -> str:
        """Transforma um valor ja garantido nao-nulo e em texto."""

    def __repr__(self) -> str:
        # Reprs nao expoem configuracao sensivel.
        return f"{type(self).__name__}()"
