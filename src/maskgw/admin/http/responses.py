"""Forma unica de resposta de erro e o mapeamento categoria -> status HTTP.

Toda resposta de erro administrativa tem a MESMA forma (secao 4.4): um `error`
do conjunto fechado de `AdminErrorCategory` e um `detail` de texto FIXO por
categoria. Nunca `str(exc)`, nunca traceback, nunca `repr` arbitrario, nunca o
`input` rejeitado, nunca a cadeia de excecao.

Uma unica categoria acompanha `applied: true` — `CONFIG_DURABILITY_ERROR`
(secao 7.6) — e ela e derivada da categoria, jamais informada pelo chamador.

`Cache-Control: no-store` NAO e aplicado aqui: ele e responsabilidade do
middleware de fronteira, que o poe em TODA resposta, inclusive nas que este
modulo nunca ve — o 404 do router, o 405 do Starlette e o 500 do catch-all.
Aplicar nos dois lugares esconderia um buraco em vez de fecha-lo.
"""

from __future__ import annotations

from typing import Any, Final

from fastapi.responses import JSONResponse

from maskgw.admin.errors import CATEGORY_DETAILS, AdminErrorCategory

#: Status HTTP por categoria. Total sobre as categorias alcancaveis na Etapa 7.
#:
#: As categorias de escrita/reload (CONFIG_*, REVISION_CONFLICT, RELOAD_BUSY)
#: aparecem porque a tabela e o contrato do plano inteiro e ja esta decidida
#: pelas secoes 6 e 7.6 — nao porque alguma rota desta etapa as produza.
#: Nenhuma rota de escrita existe aqui, e um teste afirma isso.
STATUS_BY_CATEGORY: Final[dict[AdminErrorCategory, int]] = {
    # Fronteira HTTP.
    AdminErrorCategory.HOST_NOT_ALLOWED: 400,
    AdminErrorCategory.UNAUTHORIZED: 401,
    AdminErrorCategory.CROSS_ORIGIN_REJECTED: 403,
    AdminErrorCategory.NOT_FOUND: 404,
    AdminErrorCategory.METHOD_NOT_ALLOWED: 405,
    AdminErrorCategory.PAYLOAD_TOO_LARGE: 413,
    AdminErrorCategory.UNSUPPORTED_MEDIA_TYPE: 415,
    AdminErrorCategory.SCHEMA_INVALID: 422,
    # Secao 6: controle otimista e pre-condicoes de estado.
    AdminErrorCategory.REVISION_CONFLICT: 409,
    AdminErrorCategory.CONFIG_NOT_ADOPTED: 409,
    AdminErrorCategory.CONFIG_ALREADY_ADOPTED: 409,
    AdminErrorCategory.CONFIG_OUT_OF_SYNC: 409,
    AdminErrorCategory.RELOAD_BUSY: 409,
    # Documento candidato recusado.
    AdminErrorCategory.CONFIG_INVALID: 422,
    AdminErrorCategory.CONFIG_RELOAD_ERROR: 422,
    # Campo protegido/imutavel no corpo de uma escrita (secao 11.3, Etapa 9).
    AdminErrorCategory.IMMUTABLE_FIELD: 422,
    # Falhas do servidor. `CONFIG_DURABILITY_ERROR` e 500 COM `applied: true`
    # (secao 7.6): a mudanca valeu, e a durabilidade dela nao esta confirmada.
    AdminErrorCategory.CONFIG_WRITE_ERROR: 500,
    AdminErrorCategory.CONFIG_DURABILITY_ERROR: 500,
    AdminErrorCategory.INTERNAL_ERROR: 500,
}

#: Reason codes fechados de um `422` de schema (secao 4.5). O corpo lista
#: CAMINHOS de campo e um destes codigos — nunca o valor submetido. Um
#: `fixed.value` ou um `regex.replacement` recusado voltaria no corpo do erro
#: e dali para o log do cliente.
REASON_UNKNOWN_FIELD: Final = "unknown_field"
REASON_MISSING: Final = "missing"
REASON_OUT_OF_RANGE: Final = "out_of_range"
REASON_WRONG_TYPE: Final = "wrong_type"
REASON_TOO_SHORT: Final = "too_short"
REASON_IMMUTABLE: Final = "immutable"

CLOSED_REASONS: Final[frozenset[str]] = frozenset(
    {
        REASON_UNKNOWN_FIELD,
        REASON_MISSING,
        REASON_OUT_OF_RANGE,
        REASON_WRONG_TYPE,
        REASON_TOO_SHORT,
        REASON_IMMUTABLE,
    }
)

#: Prefixos de `type` do Pydantic v2 -> reason code fechado. A ordem importa:
#: o primeiro prefixo que casar decide. Um `type` desconhecido vira
#: `wrong_type`, e nunca o texto do Pydantic — que cita o valor.
_REASON_BY_PYDANTIC_TYPE: Final[tuple[tuple[str, str], ...]] = (
    ("extra_forbidden", REASON_UNKNOWN_FIELD),
    ("missing", REASON_MISSING),
    ("frozen", REASON_IMMUTABLE),
    ("too_short", REASON_TOO_SHORT),
    ("string_too_short", REASON_TOO_SHORT),
    ("too_long", REASON_OUT_OF_RANGE),
    ("string_too_long", REASON_OUT_OF_RANGE),
    ("greater_than", REASON_OUT_OF_RANGE),
    ("less_than", REASON_OUT_OF_RANGE),
    ("multiple_of", REASON_OUT_OF_RANGE),
)


def reason_for(pydantic_type: str) -> str:
    """Traduz o `type` do Pydantic num reason code do conjunto fechado."""
    for prefix, reason in _REASON_BY_PYDANTIC_TYPE:
        if pydantic_type.startswith(prefix):
            return reason
    return REASON_WRONG_TYPE


def field_path(location: tuple[object, ...]) -> str:
    """Caminho do campo, e so ele.

    O ultimo item de um erro `extra_forbidden` e o NOME do campo desconhecido,
    que o cliente enviou — e um nome de campo nao e um valor de dado. Nomes de
    campo sao o que a secao 4.5 autoriza explicitamente; valores, nunca.
    """
    return ".".join(str(item) for item in location) or "<root>"


def error_payload(
    category: AdminErrorCategory,
    *,
    current_revision: int | None = None,
    fields: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Corpo de erro canonico. Fechado por construcao, nao por disciplina."""
    payload: dict[str, Any] = {
        "error": category.value,
        "detail": CATEGORY_DETAILS[category],
    }
    if category is AdminErrorCategory.CONFIG_DURABILITY_ERROR:
        # Derivado da categoria. O administrador precisa saber as duas coisas:
        # a mudanca valeu, e a durabilidade dela nao esta confirmada.
        payload["applied"] = True
    if current_revision is not None:
        # Nao e vazamento: o mesmo chamador autenticado le esse numero num GET.
        payload["current_revision"] = current_revision
    if fields is not None:
        payload["fields"] = fields
    return payload


def error_response(
    category: AdminErrorCategory,
    *,
    current_revision: int | None = None,
    fields: list[dict[str, str]] | None = None,
) -> JSONResponse:
    """Resposta de erro pronta, com o status que a categoria determina."""
    return JSONResponse(
        status_code=STATUS_BY_CATEGORY[category],
        content=error_payload(
            category,
            current_revision=current_revision,
            fields=fields,
        ),
    )
