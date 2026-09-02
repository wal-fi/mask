"""Vocabulario fechado de erro do plano administrativo (secao 10.2).

O plano administrativo tem o proprio conjunto de categorias e nao reexporta as
excecoes internas dos modulos que ele compoe. Isso e deliberado: `config/` e
`runtime/` levantam erros que descrevem o MECANISMO (lock indisponivel, digest
divergente, aposentado em uso), e a fronteira administrativa responde por
CATEGORIA. Traduzir num lugar so mantem a superficie fechada e impede que uma
excecao interna nova apareca na resposta sem ninguem decidir por isso.

Regras que valem para toda instancia:

- a mensagem e FIXA por categoria; nunca deriva de `str(exc)`, de caminho de
  arquivo, de DSN, de SQL ou de valor;
- `applied` e derivado da categoria, nunca informado pelo chamador: so
  `CONFIG_DURABILITY_ERROR` o carrega verdadeiro (secao 7.6);
- `current_revision` e um inteiro de metadata administrativa. Nao e vazamento:
  o mesmo chamador autenticado le esse numero num `GET` (secao 6).

O erro sanitizado e levantado FORA do bloco `except` que o originou, por
`raise_admin_error` (D-017). Este trap ja foi introduzido duas vezes neste
projeto e pego por teste nas duas.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, NoReturn

from maskgw.errors import MaskGatewayError


class AdminErrorCategory(StrEnum):
    """As categorias da secao 10.2, mais as da fronteira HTTP da Etapa 7.

    O conjunto e fechado. A primeira metade e alcancavel pelo fluxo de
    escrita/reload da Etapa 6; a segunda nasceu com a aplicacao HTTP, e nenhum
    caminho da secao critica pode produzi-la.

    `IMMUTABLE_FIELD`, tambem prevista na secao 10.2, NAO esta aqui: ela so e
    alcancavel por uma rota de escrita com corpo, e a Etapa 7 nao registra
    nenhuma. Declara-la agora fixaria, sem necessidade, o status HTTP de uma
    operacao da Etapa 9.

    Quatro categorias — `HOST_NOT_ALLOWED`, `CROSS_ORIGIN_REJECTED`,
    `UNSUPPORTED_MEDIA_TYPE` e `PAYLOAD_TOO_LARGE` — nao constam da secao 10.2.
    A especificacao fixa os STATUS dessas recusas (secao 3.3: 400, 403, 415, e
    o limite de 1 MiB de 12.7) e fixa que toda resposta de erro tem a MESMA
    forma, com `error` de conjunto fechado (secao 4.4) — e nao fornece o nome
    para elas. Reaproveitar uma categoria existente mentiria sobre o motivo;
    omitir o campo quebraria a forma unica. Ver docs/DECISIONS.md (D-056).
    """

    # -- secao 10.2, alcancaveis pela secao critica administrativa --------
    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_RELOAD_ERROR = "CONFIG_RELOAD_ERROR"
    CONFIG_WRITE_ERROR = "CONFIG_WRITE_ERROR"
    CONFIG_DURABILITY_ERROR = "CONFIG_DURABILITY_ERROR"
    CONFIG_OUT_OF_SYNC = "CONFIG_OUT_OF_SYNC"
    CONFIG_NOT_ADOPTED = "CONFIG_NOT_ADOPTED"
    CONFIG_ALREADY_ADOPTED = "CONFIG_ALREADY_ADOPTED"
    REVISION_CONFLICT = "REVISION_CONFLICT"
    RELOAD_BUSY = "RELOAD_BUSY"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    # -- fronteira HTTP (Etapa 7) -----------------------------------------
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    HOST_NOT_ALLOWED = "HOST_NOT_ALLOWED"
    CROSS_ORIGIN_REJECTED = "CROSS_ORIGIN_REJECTED"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"


#: Texto fixo por categoria. Nenhum deles cita arquivo, campo, valor ou causa.
CATEGORY_DETAILS: Final[dict[AdminErrorCategory, str]] = {
    AdminErrorCategory.CONFIG_INVALID: "The candidate configuration is not valid.",
    AdminErrorCategory.CONFIG_RELOAD_ERROR: (
        "The candidate configuration could not be compiled or verified."
    ),
    AdminErrorCategory.CONFIG_WRITE_ERROR: (
        "The configuration could not be persisted; the previous file is unchanged."
    ),
    AdminErrorCategory.CONFIG_DURABILITY_ERROR: (
        "The configuration was applied, but its durability is not confirmed."
    ),
    AdminErrorCategory.CONFIG_OUT_OF_SYNC: (
        "The configuration file no longer matches the published runtime."
    ),
    AdminErrorCategory.CONFIG_NOT_ADOPTED: (
        "The configuration has not been adopted by the Admin API."
    ),
    AdminErrorCategory.CONFIG_ALREADY_ADOPTED: "The configuration has already been adopted.",
    AdminErrorCategory.REVISION_CONFLICT: (
        "The expected revision does not match the current revision."
    ),
    AdminErrorCategory.RELOAD_BUSY: "A retired runtime is still in use; retry later.",
    AdminErrorCategory.INTERNAL_ERROR: "The administrative operation could not be completed.",
    # Fronteira HTTP. Nenhum destes cita header recebido, caminho, metodo,
    # tamanho medido ou qualquer coisa que o chamador tenha enviado: um texto
    # que ecoasse a entrada seria o mesmo vazamento que o handler default do
    # FastAPI produz com `input` (secao 4.5).
    AdminErrorCategory.UNAUTHORIZED: "Authentication is required.",
    AdminErrorCategory.NOT_FOUND: "The requested resource does not exist.",
    AdminErrorCategory.SCHEMA_INVALID: "The request does not match the expected schema.",
    AdminErrorCategory.METHOD_NOT_ALLOWED: "The method is not allowed for this resource.",
    AdminErrorCategory.HOST_NOT_ALLOWED: "The Host header is not accepted.",
    AdminErrorCategory.CROSS_ORIGIN_REJECTED: "Browser-originated requests are not accepted.",
    AdminErrorCategory.UNSUPPORTED_MEDIA_TYPE: "The request body must be application/json.",
    AdminErrorCategory.PAYLOAD_TOO_LARGE: "The request body is too large.",
}

#: A unica categoria que afirma que a mudanca tomou efeito (secao 7.6). Depois
#: do `os.replace` nao ha rollback de arquivo, e um erro de durabilidade que
#: dissesse `applied: false` estaria mentindo.
APPLIED_CATEGORIES: Final = frozenset({AdminErrorCategory.CONFIG_DURABILITY_ERROR})


class AdminError(MaskGatewayError):
    """Unico erro que sai do plano administrativo.

    Carrega categoria, a mensagem fixa correspondente e, quando a categoria
    pede, a revision corrente. Nada mais: nem excecao encadeada, nem caminho,
    nem detalhe do PostgreSQL, nem trecho da configuracao.
    """

    __slots__ = ("category", "current_revision")

    def __init__(
        self,
        category: AdminErrorCategory,
        *,
        current_revision: int | None = None,
    ) -> None:
        super().__init__(CATEGORY_DETAILS[category])
        self.category = category
        self.current_revision = current_revision

    @property
    def applied(self) -> bool:
        """Se a mudanca ja esta instalada em disco apesar do erro."""
        return self.category in APPLIED_CATEGORIES

    def __repr__(self) -> str:
        return (
            f"AdminError(category={self.category.value!r}, applied={self.applied!r}, "
            f"current_revision={self.current_revision!r})"
        )


def raise_admin_error(error: AdminError) -> NoReturn:
    """Levanta o erro ja sanitizado FORA do handler que o originou.

    `raise ... from None` zera `__cause__`, mas o interpretador ainda pendura a
    excecao original em `__context__` quando o `raise` ocorre dentro de um
    handler ativo. Uma cadeia assim alcancaria a mensagem do PostgreSQL, o
    caminho do arquivo ou o traceback — qualquer formatador que percorra a
    cadeia os exporia. Levantar aqui, ja fora do handler, deixa os dois nulos.
    """
    raise error from None
