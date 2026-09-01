"""Plano administrativo.

Este pacote nao conhece o plano de dados: nao importa `maskgw.mcp` e nao fala
com o Gateway. Ele troca o runtime pelo `RuntimeRegistry`, que fica abaixo dos
dois planos. So o composition root em `bootstrap/` conhece os dois ao mesmo
tempo (secao 9), e isso e teste de AST.

Estado na Etapa 6: existe a secao critica administrativa e o fluxo completo de
escrita/reload. Nao existe HTTP — nem FastAPI, nem rota, nem autenticacao, nem
bind, nem porta. A aplicacao HTTP pertence a Etapa 7, `config:validate` a
Etapa 8, as rotas de escrita e a adocao com backup a Etapa 9, e `AdminAudit` a
Etapa 10. Este pacote tambem nao importa `logging`: quando houver registro, ele
sera feito por `audit/`, o unico modulo autorizado a isso.
"""

from __future__ import annotations

from maskgw.admin.document import (
    RenderedDocument,
    decode_document,
    parse_document,
    render_document,
)
from maskgw.admin.errors import (
    APPLIED_CATEGORIES,
    CATEGORY_DETAILS,
    AdminError,
    AdminErrorCategory,
    raise_admin_error,
)
from maskgw.admin.service import (
    AdapterFactory,
    AdminConfigService,
    AdminOperation,
    AdminWriteResult,
    ConfigMutation,
)

__all__ = [
    "APPLIED_CATEGORIES",
    "CATEGORY_DETAILS",
    "AdapterFactory",
    "AdminConfigService",
    "AdminError",
    "AdminErrorCategory",
    "AdminOperation",
    "AdminWriteResult",
    "ConfigMutation",
    "RenderedDocument",
    "decode_document",
    "parse_document",
    "raise_admin_error",
    "render_document",
]
