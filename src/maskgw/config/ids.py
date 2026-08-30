"""IDs administrativos estaveis para regras e exceptions.

Um ID identifica um item ao longo da vida dele, independentemente da posicao.
CRUD por indice de lista e fragil: remover a regra 2 renumera a 3, e duas telas
abertas ao mesmo tempo editam coisas diferentes achando que editam a mesma.
Ver docs/DECISIONS.md (D-051).

O ID NAO substitui a ordem. A ordem das regras continua semanticamente
relevante — "first match wins" (D-004) — e a reordenacao e operacao propria.

O ID e opaco e nao carrega informacao: nao deriva do conteudo da regra, porque
editar a regra mudaria o ID e o item deixaria de ser o mesmo item.
"""

from __future__ import annotations

import secrets
from typing import Final

#: Prefixos por tipo de item. Um ID de regra num campo de exception e recusado
#: pelo schema, em vez de ser aceito e apontar para o lugar errado.
RULE_ID_PREFIX: Final = "rul_"
EXCEPTION_ID_PREFIX: Final = "exc_"

#: 32 digitos hexadecimais = 128 bits. Colisao acidental nao e uma preocupacao
#: pratica, e o ID nunca e secreto.
ID_HEX_LENGTH: Final = 32

RULE_ID_PATTERN: Final = rf"^{RULE_ID_PREFIX}[0-9a-f]{{{ID_HEX_LENGTH}}}$"
EXCEPTION_ID_PATTERN: Final = rf"^{EXCEPTION_ID_PREFIX}[0-9a-f]{{{ID_HEX_LENGTH}}}$"


def new_rule_id() -> str:
    """Gera um ID de regra. `secrets`, nunca `random` (D-005)."""
    return f"{RULE_ID_PREFIX}{secrets.token_hex(ID_HEX_LENGTH // 2)}"


def new_exception_id() -> str:
    """Gera um ID de exception."""
    return f"{EXCEPTION_ID_PREFIX}{secrets.token_hex(ID_HEX_LENGTH // 2)}"
