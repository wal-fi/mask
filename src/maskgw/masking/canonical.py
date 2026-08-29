"""Canonicalizacao deterministica de valores para transformacao.

Um transformer opera sobre texto. O banco, porem, devolve objetos Python de
varios tipos (`Decimal`, `datetime`, `UUID`, `bytes`, `dict` de JSONB...).
Converter esses objetos com `str()` seria errado por dois motivos:

- `str(memoryview)` produz `<memory at 0x...>`, que embute o endereco do
  objeto e MUDA a cada execucao. Isso quebraria em silencio o determinismo
  prometido por `hmac_sha256`, `md5`, `sha256` e `sha512`.
- `str(dict)` produz repr de Python (aspas simples, ordem de insercao), que
  nao e estavel nem interoperavel.

Este modulo define uma conversao explicita, deterministica e testada. Tipo
fora da tabela FALHA FECHADA: levanta `TransformerError` em vez de cair em
`str()`. Ver docs/DECISIONS.md (D-015).

Ele pertence ao nucleo puro: depende apenas da stdlib e de `maskgw.errors`.

Nenhuma mensagem de erro daqui contem o valor — apenas o nome do tipo.
"""

from __future__ import annotations

import base64
import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import Final
from uuid import UUID

from maskgw.errors import TransformerError

#: Separadores sem espaco: forma canonica e estavel entre versoes de Python.
_JSON_SEPARATORS: Final[tuple[str, str]] = (",", ":")


def _unsupported(value: object) -> TransformerError:
    """Erro de tipo nao suportado, citando apenas o nome do tipo."""
    msg = (
        f"tipo nao suportado para transformacao: {type(value).__name__}; "
        "a canonicalizacao falha fechada e nao recorre a str()"
    )
    return TransformerError(msg)


def _binary(data: bytes) -> str:
    """Binario em base64 padrao: deterministico, sem perda e sem endereco."""
    return base64.b64encode(data).decode("ascii")


def _json_default(value: object) -> str:
    """Escalar que o `json` nao conhece: mesma tabela, ou falha fechada."""
    return canonicalize(value)


def _json(value: object) -> str:
    """JSON canonico: chaves ordenadas, sem espacos, UTF-8 preservado."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=_JSON_SEPARATORS,
            ensure_ascii=False,
            allow_nan=False,
            default=_json_default,
        )
    except TransformerError:
        raise
    except (TypeError, ValueError):
        # A mensagem do json embute o repr do objeto ofensor: nunca propagar.
        msg = "estrutura JSON nao canonicalizavel"
        raise TransformerError(msg) from None


def canonicalize(value: object) -> str:  # noqa: PLR0911 - tabela de tipos, uma saida por tipo
    """Converte um valor nao-nulo em texto deterministico.

    A ordem dos testes de tipo importa: `bool` e subclasse de `int` e
    `datetime` e subclasse de `date`. Inverter a ordem produziria saida
    silenciosamente errada.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        # Antes de int: bool e subclasse de int.
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # repr e a forma curta com round-trip garantido em Python 3.
        return repr(value)
    if isinstance(value, Decimal):
        # Preserva a escala vinda do PostgreSQL: '1.10' nao vira '1.1'.
        return str(value)
    if isinstance(value, bytes | bytearray):
        return _binary(bytes(value))
    if isinstance(value, memoryview):
        return _binary(value.tobytes())
    if isinstance(value, datetime):
        # Antes de date: datetime e subclasse de date.
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict | list):
        return _json(value)
    raise _unsupported(value)
