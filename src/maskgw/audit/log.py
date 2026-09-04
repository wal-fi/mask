"""Auditoria minima: apenas metadata operacional.

Este e o UNICO lugar do projeto autorizado a importar `logging`. Ate a Fase 4
nenhum modulo logava (D-012); a Fase 5 abre a excecao, e a abre estreita. A
Fase 7 / Etapa 10 acrescenta a auditoria administrativa, e a abre igualmente
estreita: `AdminAudit` e fechada por CONSTRUCAO, exatamente como `QueryAudit`.

O que entra no log e definido por CONSTRUCAO, nao por disciplina: `QueryAudit` e
`AdminAudit` tem exatamente os campos permitidos, e `AuditLog.record`/`record_admin`
so serializam esses campos. Nao ha caminho pelo qual uma SQL, um valor de linha,
um `match`, um nome de coluna, a config de um transformer, o corpo da requisicao,
um token ou um segredo cheguem aqui — nao existe parametro para isso.

NUNCA registrado: a SQL, valores, linhas, parametros, o result set (original ou
mascarado), segredos, o DSN, a senha, o `match` de uma regra, nomes de coluna, a
config de um transformer, o corpo de uma requisicao administrativa, o bearer
token, a chave HMAC, o digest ou os bytes do arquivo, e a mensagem original de
qualquer excecao.

Correlacao entre entradas usa `request_id`, um UUID gerado por operacao.
Deliberadamente NAO se registra hash da SQL: um digest permitiria confirmar,
por comparacao, que uma consulta especifica foi executada — e com predicados
como `WHERE cpf = '...'` isso vira um oraculo sobre o dado. Ver D-035.

A exclusao do `match` na auditoria administrativa e a mesma consistencia com
D-035 e docs/SECURITY.md: o `match` de uma regra E um nome de coluna, e um nome
pode ser revelador. Registra-se o `target_id` administrativo (`rul_...`,
`exc_...`) e a operacao, que correlacionam sem revelar (secao 13.3).
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Final

#: Nome do logger. O operador controla destino e nivel por configuracao de
#: logging padrao do Python, sem que o Gateway precise saber onde vai parar. E o
#: MESMO logger para o plano MCP e o administrativo: nao se cria handler global
#: nem se configura logging implicitamente (secao 13, requisito de integracao).
LOGGER_NAME: Final = "maskgw.audit"

#: Mensagem fixa das entradas de consulta. O conteudo util vai em campos
#: estruturados, nunca no texto.
MESSAGE: Final = "query"

#: Mensagem fixa das entradas administrativas. Fixa como `MESSAGE`, e distinta
#: para separar os dois planos no log sem carregar nenhum dado no texto.
ADMIN_MESSAGE: Final = "admin"

#: Desfechos possiveis de uma consulta.
SUCCESS: Final = "success"
FAILURE: Final = "failure"


class AdminOperationName(StrEnum):
    """As doze operacoes administrativas auditaveis (secao 13.2).

    Fechado. Uma por rota que alcanca o handler: `config:validate` e as onze
    escritas da Etapa 9. Nao ha operacao para leitura, para recusa anterior ao
    handler, para path desconhecido ou para metodo nao registrado — e nao se
    inventa uma.
    """

    ADOPT = "adopt"
    VALIDATE = "validate"
    CONFIG_PUT = "config_put"
    RULE_CREATE = "rule_create"
    RULE_UPDATE = "rule_update"
    RULE_DELETE = "rule_delete"
    RULES_REORDER = "rules_reorder"
    EXCEPTION_CREATE = "exception_create"
    EXCEPTION_UPDATE = "exception_update"
    EXCEPTION_DELETE = "exception_delete"
    DATABASE_PUT = "database_put"
    SQL_PUT = "sql_put"


class AdminTargetKind(StrEnum):
    """O tipo de alvo de uma operacao administrativa (secao 13.2). Fechado."""

    RULE = "rule"
    EXCEPTION = "exception"
    CONFIG = "config"
    DATABASE = "database"
    SQL = "sql"


class AdminOutcome(StrEnum):
    """Desfecho de uma operacao administrativa (secao 13.2). Fechado.

    `success` para o sucesso; `rejected` para uma recusa controlada com resposta
    4xx; `error` para uma falha 5xx (inclusive `CONFIG_DURABILITY_ERROR`, que
    publica a mudanca mas nao confirma durabilidade — secao 7.6).
    """

    SUCCESS = "success"
    REJECTED = "rejected"
    ERROR = "error"


class AdminErrorCategoryName(StrEnum):
    """Espelho FECHADO das categorias administrativas, no modulo neutro `audit/`.

    `error_category` de um `AdminAudit` precisa ser fechado — uma categoria
    administrativa existente ou `None`, nunca texto arbitrario. Referenciar
    `maskgw.admin.errors.AdminErrorCategory` daqui criaria o ciclo
    `audit -> admin -> audit` (o plano administrativo ja importa `audit/` para
    registrar). A saida e declarar o conjunto AQUI, no modulo neutro, e provar a
    paridade EXATA com `AdminErrorCategory` por teste (`test_admin_audit.py`): se
    um lado ganhar ou perder uma categoria, o teste quebra.

    Os valores sao identicos aos de `AdminErrorCategory` (secao 10.2), entao a
    tradução entre os dois enums e `AdminErrorCategoryName(categoria.value)`.
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
    IMMUTABLE_FIELD = "IMMUTABLE_FIELD"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    HOST_NOT_ALLOWED = "HOST_NOT_ALLOWED"
    CROSS_ORIGIN_REJECTED = "CROSS_ORIGIN_REJECTED"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"


#: Mapping FECHADO de operacao para tipo de alvo (secao 13.2). Fonte UNICA: o
#: `AdminAudit` valida contra ela e o `AdminAuditor` deriva `target_kind` dela, em
#: vez de manter uma segunda tabela que poderia divergir. Total sobre as doze
#: operacoes.
OPERATION_TARGET_KIND: Final[dict[AdminOperationName, AdminTargetKind]] = {
    AdminOperationName.ADOPT: AdminTargetKind.CONFIG,
    AdminOperationName.VALIDATE: AdminTargetKind.CONFIG,
    AdminOperationName.CONFIG_PUT: AdminTargetKind.CONFIG,
    AdminOperationName.RULE_CREATE: AdminTargetKind.RULE,
    AdminOperationName.RULE_UPDATE: AdminTargetKind.RULE,
    AdminOperationName.RULE_DELETE: AdminTargetKind.RULE,
    AdminOperationName.RULES_REORDER: AdminTargetKind.RULE,
    AdminOperationName.EXCEPTION_CREATE: AdminTargetKind.EXCEPTION,
    AdminOperationName.EXCEPTION_UPDATE: AdminTargetKind.EXCEPTION,
    AdminOperationName.EXCEPTION_DELETE: AdminTargetKind.EXCEPTION,
    AdminOperationName.DATABASE_PUT: AdminTargetKind.DATABASE,
    AdminOperationName.SQL_PUT: AdminTargetKind.SQL,
}

#: As UNICAS operacoes que podem carregar `target_id`: update/delete de uma
#: unica regra ou exception (secao 13.3). Criar, reordenar, adotar, validar e as
#: substituicoes de config/database/sql exigem `target_id=None`.
_TARGET_ID_OPERATIONS: Final[frozenset[AdminOperationName]] = frozenset(
    {
        AdminOperationName.RULE_UPDATE,
        AdminOperationName.RULE_DELETE,
        AdminOperationName.EXCEPTION_UPDATE,
        AdminOperationName.EXCEPTION_DELETE,
    }
)

#: Categoria que afirma publicacao apesar do erro (secao 7.6): `outcome=error` e
#: `revision_after` preenchida.
_DURABILITY_CATEGORY: Final = AdminErrorCategoryName.CONFIG_DURABILITY_ERROR

#: As categorias de FALHA DO SERVIDOR (HTTP 5xx). O resto e recusa controlada do
#: cliente (4xx). Declarado AQUI, no modulo neutro, e nao derivado de
#: `STATUS_BY_CATEGORY` (que vive em `admin.http`, e importa-lo fecharia o ciclo).
#: A paridade EXATA com a faixa de status daquela tabela e provada por teste
#: (`test_admin_audit.py`): 5xx -> `error`, 4xx -> `rejected`.
_SERVER_ERROR_CATEGORIES: Final[frozenset[AdminErrorCategoryName]] = frozenset(
    {
        AdminErrorCategoryName.CONFIG_WRITE_ERROR,
        AdminErrorCategoryName.CONFIG_DURABILITY_ERROR,
        AdminErrorCategoryName.INTERNAL_ERROR,
    }
)

#: Desfecho EXIGIDO por cada categoria, pela sua faixa de status. Total sobre
#: todas as categorias: `error` para as 5xx, `rejected` para as demais. E o que
#: fecha a coerencia `outcome <-> error_category` — `REJECTED` com `INTERNAL_ERROR`
#: (5xx) ou `ERROR` com `REVISION_CONFLICT` (4xx) sao recusados na construcao.
CATEGORY_OUTCOME: Final[dict[AdminErrorCategoryName, AdminOutcome]] = {
    category: (
        AdminOutcome.ERROR if category in _SERVER_ERROR_CATEGORIES else AdminOutcome.REJECTED
    )
    for category in AdminErrorCategoryName
}

#: Prefixo e padrao de ID por `target_kind`, para validar `target_id`. Duplicados
#: aqui de proposito, no modulo neutro, para nao arrastar `maskgw.config` (e seus
#: `__init__` pesados) para dentro de `audit/`. A paridade com
#: `maskgw.config.ids` e provada por teste (`test_admin_audit.py`).
_RULE_ID_PATTERN: Final = re.compile(r"^rul_[0-9a-f]{32}$")
_EXCEPTION_ID_PATTERN: Final = re.compile(r"^exc_[0-9a-f]{32}$")

#: `request_id` e o `uuid.uuid4().hex` gerado pelo servidor: 32 hex minusculos,
#: e um UUID de versao 4. Validar o FORMATO fecha o campo — um CPF ou um token
#: nao casa —, e validar a VERSAO garante que so o formato realmente gerado passa.
_REQUEST_ID_PATTERN: Final = re.compile(r"^[0-9a-f]{32}$")


def _is_int(value: object) -> bool:
    """Inteiro de verdade, nunca `bool` — `True`/`False` sao `int` em Python."""
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True, slots=True)
class QueryAudit:
    """Metadata de uma consulta. Estes sao os UNICOS campos auditados."""

    request_id: str
    outcome: str
    duration_ms: int
    row_count: int | None = None
    truncated: bool | None = None
    error_category: str | None = None

    def as_fields(self) -> dict[str, Any]:
        """Campos estruturados. Nada alem do que a dataclass declara."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AdminAudit:
    """Metadata de uma operacao administrativa. Estes sao os UNICOS campos (13.2).

    Fechada por construcao, e AGORA de verdade: os campos categoricos guardam os
    ENUMS, nao suas strings, entao um valor fora do conjunto nem constroi. Sem
    `**kwargs`, sem dicionario livre, sem campo de texto aberto. NENHUM parametro
    para `match`, nome de coluna, config de transformer, corpo de requisicao,
    token, secret, DSN, SQL, valor, digest, bytes do arquivo ou mensagem original
    de excecao — eles nem existem na assinatura (secao 13.3).

    `__post_init__` impoe as invariantes de construcao: um evento incoerente
    (operacao inventada, `target_id` com CPF, duracao negativa, categoria
    arbitraria, mapping operacao/alvo violado, revisoes incoerentes com o
    desfecho) e RECUSADO com `TypeError`/`ValueError` ANTES de qualquer chance de
    chegar ao logger. Um campo autorizado deixa de ser canal para conteudo
    arbitrario.

    Os tipos categoricos sao enums; `as_fields()` os converte para os valores
    string, entregando somente dados JSON-compativeis.
    """

    request_id: str
    operation: AdminOperationName
    target_kind: AdminTargetKind | None
    target_id: str | None
    outcome: AdminOutcome
    revision_before: int | None
    revision_after: int | None
    duration_ms: int
    error_category: AdminErrorCategoryName | None

    def __post_init__(self) -> None:
        self._check_types()
        self._check_request_id()
        self._check_durations()
        self._check_target()
        self._check_outcome_and_revisions()

    def _check_types(self) -> None:
        """Os campos categoricos DEVEM ser os enums, nunca strings cruas.

        As anotacoes de tipo nao valem em runtime: Python nao impede um chamador
        de passar `operation="inventada"`. Estas verificacoes sao a barreira
        real, e por isso os valores sao lidos como `object` (via um mapa
        `nome -> tipo`) — se fossem lidos ja com o tipo anotado, o proprio mypy
        os narraria e consideraria a recusa inalcancavel, apagando a defesa.
        """
        required: dict[str, type] = {
            "operation": AdminOperationName,
            "outcome": AdminOutcome,
        }
        optional: dict[str, type] = {
            "target_kind": AdminTargetKind,
            "error_category": AdminErrorCategoryName,
        }
        fields: dict[str, object] = asdict(self)
        for name, expected in required.items():
            if not isinstance(fields[name], expected):
                msg = f"{name} must be a {expected.__name__} member"
                raise TypeError(msg)
        for name, expected in optional.items():
            value = fields[name]
            if value is not None and not isinstance(value, expected):
                msg = f"{name} must be a {expected.__name__} member or None"
                raise TypeError(msg)

        # `bool` é `int`, e um `duration_ms=True` seria aceito por um teste de
        # `int` ingênuo. Recusa explícita.
        if not _is_int(fields["duration_ms"]):
            msg = "duration_ms must be a non-boolean int"
            raise TypeError(msg)
        for name in ("revision_before", "revision_after"):
            value = fields[name]
            if value is not None and not _is_int(value):
                msg = f"{name} must be a non-boolean int or None"
                raise TypeError(msg)
        if not isinstance(fields["request_id"], str):
            msg = "request_id must be a str"
            raise TypeError(msg)
        target_id = fields["target_id"]
        if target_id is not None and not isinstance(target_id, str):
            msg = "target_id must be a str or None"
            raise TypeError(msg)

    def _check_request_id(self) -> None:
        """`request_id` e o `uuid4().hex` do servidor: 32 hex e versao 4."""
        if not _REQUEST_ID_PATTERN.fullmatch(self.request_id):
            msg = "request_id must be a 32-char lowercase hex uuid4"
            raise ValueError(msg)
        try:
            parsed = uuid.UUID(hex=self.request_id)
        except ValueError as exc:
            msg = "request_id is not a valid uuid"
            raise ValueError(msg) from exc
        if parsed.version != 4:  # noqa: PLR2004 - v4 e o que o servidor gera
            msg = "request_id must be a version-4 uuid"
            raise ValueError(msg)

    def _check_durations(self) -> None:
        if self.duration_ms < 0:
            msg = "duration_ms must be >= 0"
            raise ValueError(msg)
        for name in ("revision_before", "revision_after"):
            value = getattr(self, name)
            if value is not None and value < 0:
                msg = f"{name} must be >= 0 or None"
                raise ValueError(msg)

    def _check_target(self) -> None:
        """`target_kind` concorda com a operacao; `target_id` so onde e valido."""
        expected_kind = OPERATION_TARGET_KIND[self.operation]
        if self.target_kind != expected_kind:
            msg = "target_kind does not match the operation mapping"
            raise ValueError(msg)

        if self.target_id is None:
            return

        # `target_id` presente: so update/delete de regra/exception podem te-lo.
        if self.operation not in _TARGET_ID_OPERATIONS:
            msg = "this operation must not carry a target_id"
            raise ValueError(msg)

        # E o ID deve casar EXATAMENTE o padrao do seu `target_kind` — um path
        # cru (um CPF, um texto arbitrario) nunca casa (secao 13.3).
        if self.target_kind is AdminTargetKind.RULE:
            if not _RULE_ID_PATTERN.fullmatch(self.target_id):
                msg = "target_id must be a canonical rule id"
                raise ValueError(msg)
        elif self.target_kind is AdminTargetKind.EXCEPTION:
            if not _EXCEPTION_ID_PATTERN.fullmatch(self.target_id):
                msg = "target_id must be a canonical exception id"
                raise ValueError(msg)
        else:  # pragma: no cover - impossivel: as quatro operacoes sao rule/exception
            msg = "target_id is only valid for rule or exception targets"
            raise ValueError(msg)

    def _check_outcome_and_revisions(self) -> None:
        """Desfecho, categoria e revisoes precisam ser coerentes entre si."""
        self._check_outcome_category()
        self._check_revisions()

    def _check_outcome_category(self) -> None:
        """`outcome` e `error_category` concordam, e a categoria bate com a faixa.

        Sucesso nao tem categoria; recusa e erro tem. E o desfecho tem de bater
        com a FAIXA DE STATUS da categoria: uma 5xx (`CONFIG_WRITE_ERROR`,
        `CONFIG_DURABILITY_ERROR`, `INTERNAL_ERROR`) exige `error`, e as demais
        (4xx) exigem `rejected`. Sem isso, `REJECTED` com `INTERNAL_ERROR` ou
        `ERROR` com `REVISION_CONFLICT` passariam — combinacoes que o proprio
        `STATUS_BY_CATEGORY` torna impossiveis na resposta HTTP.
        """
        if self.outcome is AdminOutcome.SUCCESS:
            if self.error_category is not None:
                msg = "success requires error_category=None"
                raise ValueError(msg)
            return

        if self.error_category is None:
            msg = "rejected and error require a closed error_category"
            raise ValueError(msg)

        required_outcome = CATEGORY_OUTCOME[self.error_category]
        if self.outcome is not required_outcome:
            msg = "outcome does not match the status class of error_category"
            raise ValueError(msg)

    def _check_revisions(self) -> None:
        """Revisoes coerentes com a operacao e o desfecho.

        `validate` nunca tem revisoes. Um sucesso de escrita publica exatamente a
        proxima revision (`before + 1`). `CONFIG_DURABILITY_ERROR` publicou apesar
        do erro (secao 7.6): `error`, as duas revisoes presentes e `before + 1`.
        Qualquer outra falha nao publicou nada — `revision_after` e `None`.
        """
        # `validate` nao le runtime nem publica: revisoes sempre None (secao 13.2).
        if self.operation is AdminOperationName.VALIDATE:
            if self.revision_before is not None or self.revision_after is not None:
                msg = "validate requires revision_before and revision_after to be None"
                raise ValueError(msg)
            return

        if self.error_category is _DURABILITY_CATEGORY:
            # Ja se sabe (por `_check_outcome_category`) que outcome e `error`.
            if self.revision_before is None or self.revision_after is None:
                msg = "CONFIG_DURABILITY_ERROR requires both revisions"
                raise ValueError(msg)
            if self.revision_after != self.revision_before + 1:
                msg = "CONFIG_DURABILITY_ERROR requires revision_after == revision_before + 1"
                raise ValueError(msg)
            return

        if self.outcome is AdminOutcome.SUCCESS:
            # Sucesso de escrita: publica EXATAMENTE a proxima revision.
            if self.revision_before is None or self.revision_after is None:
                msg = "a successful write requires both revisions"
                raise ValueError(msg)
            if self.revision_after != self.revision_before + 1:
                msg = "a successful write requires revision_after == revision_before + 1"
                raise ValueError(msg)
        # Falha sem publicacao (nao durabilidade): nada publicado, `after` e None.
        elif self.revision_after is not None:
            msg = "a failure without publication requires revision_after=None"
            raise ValueError(msg)

    def as_fields(self) -> dict[str, Any]:
        """Campos estruturados, JSON-compativeis: os enums viram seus valores.

        `asdict` copia os membros de enum como estao; convertemos para as strings
        aqui para que o `LogRecord` carregue so dados JSON-serializaveis, sem
        objeto de enum.
        """
        fields = asdict(self)
        fields["operation"] = self.operation.value
        fields["outcome"] = self.outcome.value
        fields["target_kind"] = self.target_kind.value if self.target_kind is not None else None
        fields["error_category"] = (
            self.error_category.value if self.error_category is not None else None
        )
        return fields


class AuditLog:
    """Escreve entradas de auditoria. Sem estado, sem buffer, sem I/O proprio.

    Serve os dois planos com o MESMO logger: `record` para consulta, `record_admin`
    para administracao. Uma falha do handler/logger e best-effort — nunca desfaz
    nem repete uma escrita, nao muda o status/body HTTP, nao impede o fechamento
    de candidato/runtime e nao cria um segundo evento (secao 13, falha da propria
    auditoria). O `logging` do Python ja engole excecoes do handler por padrao
    (`logging.raiseExceptions` afeta so o stderr interno), mas nao se pode
    depender disso: `record_admin` isola a emissao para que uma excecao do logger
    jamais suba ao chamador.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger if logger is not None else logging.getLogger(LOGGER_NAME)

    def record(self, entry: QueryAudit) -> None:
        """Registra uma consulta ja concluida."""
        self._logger.info(MESSAGE, extra={"maskgw": entry.as_fields()})

    def record_admin(self, entry: AdminAudit) -> None:
        """Registra uma operacao administrativa ja concluida, best-effort.

        Uma excecao do logger (handler lento que falha, formatter quebrado) e
        contida aqui: ela nao pode alterar a resposta HTTP nem o estado do
        processo, ja fixados quando este metodo e chamado (secao 13). Nao ha
        segunda tentativa e nao ha segundo evento — a auditoria e melhor esforco,
        e o custo de perder um registro e menor que o de deixar a falha vazar.
        Nada da excecao contida e re-emitido: um traceback do handler poderia
        carregar detalhe, e nao ha para onde manda-lo sem tocar `stdout`.
        """
        try:
            self._logger.info(ADMIN_MESSAGE, extra={"maskgw": entry.as_fields()})
        except Exception:
            # Best-effort: a auditoria nunca derruba a operacao. So `Exception`,
            # nunca `BaseException` — `KeyboardInterrupt`/`SystemExit` continuam
            # subindo. Nada da excecao contida e re-emitido (secao 13).
            return

    def __repr__(self) -> str:
        return f"AuditLog(logger={self._logger.name!r})"
