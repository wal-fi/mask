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
    """As categorias da secao 10.2 alcancaveis pelo fluxo de escrita/reload.

    O conjunto e fechado. As categorias exclusivas da fronteira HTTP —
    `UNAUTHORIZED`, `NOT_FOUND`, `SCHEMA_INVALID`, `IMMUTABLE_FIELD` — nascem
    com a aplicacao HTTP da Etapa 7 e nao pertencem a este modulo, porque
    nenhum caminho desta etapa pode produzi-las.
    """

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
