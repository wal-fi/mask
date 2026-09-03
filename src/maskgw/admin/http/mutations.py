"""Mutacoes do documento administrativo: o payload de cada rota de escrita.

Etapa 9 da Fase 7. Cada funcao aqui produz um `ConfigMutation` — `MaskingFileConfig
-> Mapping` — que o `AdminConfigService.apply()` executa DENTRO da secao critica,
sobre a copia profunda do documento corrente. A rota HTTP e so uma traducao: ela
valida o corpo pelo schema, constroi a mutacao e chama `apply`. Nenhuma logica de
lock, adocao, `expected_revision`, digest, compilacao, conexao, persistencia ou
swap vive aqui — isso e tudo do servico (secao 1.3, §7.4).

## O que uma mutacao pode e nao pode fazer

Ela recebe o documento inteiro e devolve o documento inteiro, ja alterado, como
`dict`. Ela NAO numera a revision — o servidor a escolhe e sobrescreve qualquer
valor que a mutacao ponha (secao 6). Ela NAO valida transformer, regex nem
conecta: isso e a compilacao, depois. O que ela decide sao os erros ESPECIFICOS
da operacao:

- **alvo inexistente** (`PUT`/`DELETE` de regra/exception por ID que nao existe,
  reorder com ID estranho parcial) -> `NOT_FOUND`;
- **campo imutavel** (`allowed_pg_functions` presente, `id` escolhido pelo cliente
  que nao pertence ao documento) -> `IMMUTABLE_FIELD`;
- **payload invalido dependente do estado** (posicao de insercao fora de
  `0..len`, reorder que nao e permutacao completa) -> `CONFIG_INVALID`.

Esses `AdminError` sobem pelo `_next_document` do servico com a categoria
preservada; a validacao do documento inteiro, que vem depois, produz
`CONFIG_INVALID`. Nada e reencadeado (D-017).

## IDs sao identidade do servidor (D-059)

Criacao granular gera ID novo (`secrets`, D-005). `PUT` preserva o ID do path.
`DELETE` seguido de `POST` gera ID diferente. O cliente nunca escolhe nem altera
um ID: num corpo granular, `id` cai no `extra="forbid"` do schema; num `PUT
/config`, um `id` que nao pertence ao documento corrente e `IMMUTABLE_FIELD`.
IDs sao unicos dentro de uma configuracao adotada — o validator do loader ja
recusaria duplicatas, e a mutacao nunca os introduz.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from maskgw.admin.errors import AdminError, AdminErrorCategory
from maskgw.admin.http.schemas import (
    ConfigReplaceRequest,
    DatabaseWriteRequest,
    ExceptionContent,
    ExceptionCreateRequest,
    ExceptionReplaceRequest,
    RuleContent,
    RuleCreateRequest,
    RuleReorderRequest,
    RuleReplaceRequest,
    SqlWriteRequest,
)
from maskgw.admin.service import ConfigMutation
from maskgw.config.ids import new_exception_id, new_rule_id
from maskgw.config.models import MaskingFileConfig
from maskgw.sql.policy import canonical_function_name

#: Um documento cru, do jeito que `validate_file_config` o consome.
Document = dict[str, Any]

#: Assinatura do gerador de ID injetado em `_resolve_id`.
IdGenerator = Callable[[], str]


def _dump(document: MaskingFileConfig) -> Document:
    """`MaskingFileConfig` -> dict cru, com os `id` preservados.

    `mode="json"` normaliza o enum de `mode` para a string do arquivo. `id`
    nulos (documento nao adotado) sao mantidos como estao — a adocao e a unica
    operacao que parte de um documento sem IDs, e e ela que os atribui.
    """
    return document.model_dump(mode="json")


def _rule_dict(content: RuleContent) -> Document:
    """Conteudo de regra do schema -> dict, sem `id` (o servidor o atribui)."""
    return {
        "match": content.match,
        "mode": content.mode.value,
        "case_sensitive": content.case_sensitive,
        "transformer": content.transformer,
        "config": dict(content.config),
    }


def _exception_dict(content: ExceptionContent) -> Document:
    return {
        "match": content.match,
        "mode": content.mode.value,
        "case_sensitive": content.case_sensitive,
    }


def _current_rule_ids(document: MaskingFileConfig) -> list[str]:
    return [rule.id for rule in document.masking if rule.id is not None]


# -- adocao --------------------------------------------------------------------


def adopt() -> ConfigMutation:
    """`config:adopt`: atribui um `id` novo a cada regra e exception (secao 5.3).

    Nao muda nenhuma decisao de masking: so acrescenta `id`. A `revision` (1) e
    posta pelo servidor. O documento parte de `revision == 0` sem IDs; o servico
    ja garantiu esse estado no passo 1, entao todo item aqui tem `id is None`.
    """

    def mutate(current: MaskingFileConfig) -> Document:
        document = _dump(current)
        for rule in document.get("masking", []):
            rule["id"] = new_rule_id()
        for exception in document.get("exceptions", []):
            exception["id"] = new_exception_id()
        return document

    return mutate


# -- regras --------------------------------------------------------------------


def create_rule(request: RuleCreateRequest) -> ConfigMutation:
    """`POST /rules`: insere uma regra nova em `position` (default: fim)."""

    def mutate(current: MaskingFileConfig) -> Document:
        document = _dump(current)
        rules = document.setdefault("masking", [])
        new_rule = {"id": new_rule_id(), **_rule_dict(request.rule)}
        index = request.position if request.position is not None else len(rules)
        # Zero-based, 0..len inclusive. Fora disso e um pedido invalido
        # dependente do estado, nao um erro de schema (o schema so sabe >= 0).
        if index < 0 or index > len(rules):
            raise AdminError(AdminErrorCategory.CONFIG_INVALID)
        rules.insert(index, new_rule)
        return document

    return mutate


def replace_rule(rule_id: str, request: RuleReplaceRequest) -> ConfigMutation:
    """`PUT /rules/{rule_id}`: substitui o conteudo, preserva ID e posicao."""

    def mutate(current: MaskingFileConfig) -> Document:
        document = _dump(current)
        rules = document.get("masking", [])
        index = _index_of_id(rules, rule_id)
        if index is None:
            raise AdminError(AdminErrorCategory.NOT_FOUND)
        rules[index] = {"id": rule_id, **_rule_dict(request.rule)}
        return document

    return mutate


def delete_rule(rule_id: str) -> ConfigMutation:
    """`DELETE /rules/{rule_id}`: remove a regra."""

    def mutate(current: MaskingFileConfig) -> Document:
        document = _dump(current)
        rules = document.get("masking", [])
        index = _index_of_id(rules, rule_id)
        if index is None:
            raise AdminError(AdminErrorCategory.NOT_FOUND)
        del rules[index]
        return document

    return mutate


def reorder_rules(request: RuleReorderRequest) -> ConfigMutation:
    """`POST /rules:reorder`: `rule_ids` e uma permutacao completa dos IDs atuais.

    Lista incompleta, com duplicata ou com ID que nao pertence ao documento ->
    `CONFIG_INVALID`. A ordem entre regras e semantica (D-004), entao reordenar e
    operacao propria; nao ha reorder de exceptions.
    """

    def mutate(current: MaskingFileConfig) -> Document:
        document = _dump(current)
        rules = document.get("masking", [])
        current_ids = [rule["id"] for rule in rules]
        requested = list(request.rule_ids)
        # Permutacao completa e sem duplicatas: mesmos elementos, mesmo tamanho.
        # `sorted` compara os conjuntos exatos, e o teste de tamanho pega
        # duplicata que por acaso preserve o conjunto.
        if len(requested) != len(current_ids) or sorted(requested) != sorted(current_ids):
            raise AdminError(AdminErrorCategory.CONFIG_INVALID)
        by_id = {rule["id"]: rule for rule in rules}
        document["masking"] = [by_id[rule_id] for rule_id in requested]
        return document

    return mutate


# -- exceptions ----------------------------------------------------------------


def create_exception(request: ExceptionCreateRequest) -> ConfigMutation:
    """`POST /exceptions`: cria uma exception, sempre ao final."""

    def mutate(current: MaskingFileConfig) -> Document:
        document = _dump(current)
        exceptions = document.setdefault("exceptions", [])
        exceptions.append({"id": new_exception_id(), **_exception_dict(request.exception)})
        return document

    return mutate


def replace_exception(exception_id: str, request: ExceptionReplaceRequest) -> ConfigMutation:
    """`PUT /exceptions/{exception_id}`: substitui, preserva ID e posicao."""

    def mutate(current: MaskingFileConfig) -> Document:
        document = _dump(current)
        exceptions = document.get("exceptions", [])
        index = _index_of_id(exceptions, exception_id)
        if index is None:
            raise AdminError(AdminErrorCategory.NOT_FOUND)
        exceptions[index] = {"id": exception_id, **_exception_dict(request.exception)}
        return document

    return mutate


def delete_exception(exception_id: str) -> ConfigMutation:
    """`DELETE /exceptions/{exception_id}`: remove a exception."""

    def mutate(current: MaskingFileConfig) -> Document:
        document = _dump(current)
        exceptions = document.get("exceptions", [])
        index = _index_of_id(exceptions, exception_id)
        if index is None:
            raise AdminError(AdminErrorCategory.NOT_FOUND)
        del exceptions[index]
        return document

    return mutate


# -- database e sql ------------------------------------------------------------


def replace_database(request: DatabaseWriteRequest) -> ConfigMutation:
    """`PUT /database`: substitui os dois limites conjuntamente."""

    def mutate(current: MaskingFileConfig) -> Document:
        document = _dump(current)
        document["database"] = {
            "statement_timeout_ms": request.statement_timeout_ms,
            "max_rows": request.max_rows,
        }
        return document

    return mutate


def replace_sql(request: SqlWriteRequest) -> ConfigMutation:
    """`PUT /sql`: aditivo em `denied_functions`; `allowed_pg_functions` imutavel.

    Aditivo e sem duplicata SEMANTICA: as negacoes atuais sao preservadas, as
    novas acrescentadas, e uma repeticao — mesmo com caixa ou espacos diferentes —
    nao gera duplicata (`_merge_denied` usa a chave da politica). A PRESENCA de
    `allowed_pg_functions`, em qualquer forma inclusive `null`, e `IMMUTABLE_FIELD`
    (secao 11.3), detectada por `model_fields_set`, nunca pelo valor.
    """

    def mutate(current: MaskingFileConfig) -> Document:
        if request.allowed_pg_functions_present:
            raise AdminError(AdminErrorCategory.IMMUTABLE_FIELD)
        document = _dump(current)
        sql = document.setdefault("sql", {})
        merged = _merge_denied(sql.get("denied_functions", []), request.denied_functions)
        sql["denied_functions"] = merged
        return document

    return mutate


# -- PUT /config: substituicao integral ---------------------------------------


def replace_config(request: ConfigReplaceRequest) -> ConfigMutation:
    """`PUT /config`: substituicao integral da configuracao administravel (11.3).

    IDs (D-059): item com `id` existente preserva identidade; sem `id` cria; `id`
    que nao pertence ao documento corrente -> `IMMUTABLE_FIELD`; IDs atuais
    omitidos sao removidos. A ordem da lista e a nova ordem.
    `allowed_pg_functions` presente -> `IMMUTABLE_FIELD`; ausente -> valor atual
    preservado em conteudo e ordem.
    """

    def mutate(current: MaskingFileConfig) -> Document:
        if request.sql.allowed_pg_functions_present:
            raise AdminError(AdminErrorCategory.IMMUTABLE_FIELD)

        current_rule_ids = set(_current_rule_ids(current))
        current_exception_ids = {exc.id for exc in current.exceptions if exc.id is not None}

        masking: list[Document] = []
        for rule in request.masking:
            entry = _rule_dict(
                RuleContent(
                    match=rule.match,
                    mode=rule.mode,
                    case_sensitive=rule.case_sensitive,
                    transformer=rule.transformer,
                    config=rule.config,
                )
            )
            entry["id"] = _resolve_id(rule.id, current_rule_ids, new_rule_id)
            masking.append(entry)

        exceptions: list[Document] = []
        for exception in request.exceptions:
            entry = _exception_dict(
                ExceptionContent(
                    match=exception.match,
                    mode=exception.mode,
                    case_sensitive=exception.case_sensitive,
                )
            )
            entry["id"] = _resolve_id(exception.id, current_exception_ids, new_exception_id)
            exceptions.append(entry)

        # `allowed_pg_functions` ausente: o valor ATUAL e preservado, em conteudo
        # e ordem, a partir do documento persistido (secao 11.3). Nunca apagado
        # por omissao.
        preserved_allowed = list(current.sql.allowed_pg_functions)

        return {
            "masking": masking,
            "exceptions": exceptions,
            "database": {
                "statement_timeout_ms": request.database.statement_timeout_ms,
                "max_rows": request.database.max_rows,
            },
            "sql": {
                "allowed_pg_functions": preserved_allowed,
                "denied_functions": list(request.sql.denied_functions),
            },
        }

    return mutate


# -- auxiliares ----------------------------------------------------------------


def _index_of_id(items: list[Document], target: str) -> int | None:
    for index, item in enumerate(items):
        if item.get("id") == target:
            return index
    return None


def _resolve_id(
    provided: str | None,
    current_ids: set[str],
    generator: IdGenerator,
) -> str:
    """ID de um item num `PUT /config` (D-059).

    Ausente -> ID novo do servidor (criacao). Presente e pertencente ao
    documento corrente -> preservado. Presente mas NAO pertencente -> tentativa
    de escolher identidade, `IMMUTABLE_FIELD`.
    """
    if provided is None:
        return generator()
    if provided not in current_ids:
        raise AdminError(AdminErrorCategory.IMMUTABLE_FIELD)
    return provided


def _merge_denied(existing: list[str], added: list[str]) -> list[str]:
    """Uniao aditiva com deduplicacao SEMANTICA (secao 11.3, D-059).

    A chave e `canonical_function_name` — a MESMA que a politica usa —, entao
    `Foo`, `foo`, `FOO` e ` foo ` colapsam numa entrada. Preserva:

    - a ordem e a primeira grafia JA PERSISTIDA (o que veio de `existing`);
    - a ordem de primeira aparicao das entradas NOVAS que trazem chave inedita.

    Assim uma repeticao do mesmo request — com qualquer caixa ou espaco — nao
    cresce a lista, e a negacao continua so restringindo, nunca abrindo nada.
    """
    merged: list[str] = []
    seen: set[str] = set()
    for name in [*existing, *added]:
        key = canonical_function_name(name)
        if not key or key in seen:
            continue
        merged.append(name)
        seen.add(key)
    return merged
