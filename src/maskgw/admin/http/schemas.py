"""Schemas de resposta da Admin API.

Todos com `extra="forbid"` e `frozen=True`, o mesmo `_STRICT` de
`config/models.py` (secao 4.1). Nenhum e compartilhado com o plano MCP: a
Admin API e mais privilegiada, e reaproveitar um schema do MCP arrastaria o
modelo de confianca errado para dentro dela (D-049, secao 9).

Duas regras que estes modelos existem para tornar estruturais:

- **nenhum secret, em forma alguma.** `AdminSecrets` carrega `configured` ou
  `missing`, e o tipo nao admite um terceiro valor. Nao ha campo para valor,
  tamanho, prefixo, ultimos caracteres, hash ou data (secao 11.1). Um campo que
  nao existe nao pode ser preenchido por engano numa etapa futura;
- **a resposta vem do modelo validado do arquivo, nunca dos objetos runtime
  compilados** (D-047). A compilacao descarta informacao: um `RegexTransformer`
  carrega o padrao ja compilado, nao o texto do YAML. Reconstruir o documento a
  partir dali devolveria algo que PARECE a configuracao sem ser ela.

`RuleDocument.config` e o unico `dict[str, Any]` que atravessa a fronteira, e e
a excecao herdada que a secao 4.1 ja declara: o conteudo e validado pelo
transformer alvo na compilacao. Ele chega aqui a partir de uma copia profunda,
entao nao compartilha objeto com o runtime publicado (D-055).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, Strict, model_validator

from maskgw.config.ids import EXCEPTION_ID_PATTERN, RULE_ID_PATTERN
from maskgw.config.models import (
    MAX_MAX_ROWS,
    MAX_STATEMENT_TIMEOUT_MS,
    MIN_MAX_ROWS,
    MIN_STATEMENT_TIMEOUT_MS,
    UNADOPTED_REVISION,
)
from maskgw.masking.rules import MatchMode

#: Mesmo perfil dos modelos de configuracao: chave desconhecida e erro, e o
#: modelo nao aceita reatribuicao de campo.
_STRICT = ConfigDict(extra="forbid", frozen=True)

#: Escalares do request de `config:validate` com validacao ESTRITA por campo
#: (D-058). Sem isto o Pydantic coage `"1"` -> `1`, `1` -> `True` e `True` -> `1`,
#: e o contrato classifica tipo JSON errado como `SCHEMA_INVALID`, nao como um
#: valor silenciosamente normalizado. `Strict()` e aplicado campo a campo, e
#: NUNCA ao modelo inteiro: um `strict=True` global recusaria tambem os enums
#: textuais legitimos (`"contains"`, `"exact"`), que sao string JSON valida para
#: um `StrEnum` — `mode` fica de fora e continua aceitando esses valores.
StrictInt = Annotated[int, Strict()]
StrictBool = Annotated[bool, Strict()]

#: Tipo dos campos `allowed_pg_functions` de escrita (secao 11.3, D-059). E
#: `JsonValue | None` — QUALQUER valor JSON, ou ausente — de proposito: o campo
#: aceita toda forma para que a presenca vire `IMMUTABLE_FIELD` administrativo, e
#: nao `SCHEMA_INVALID`. A presenca e decidida EXCLUSIVAMENTE por
#: `model_fields_set`, nunca pelo valor: `null` explicito e um campo presente.
#: `JsonValue` e totalmente serializavel — sem `object` arbitrario dentro do
#: modelo —, entao `model_json_schema()`, `model_dump()` e `model_dump_json()`
#: funcionam sem warning nem erro, e nenhum sentinela vaza para schema ou dump.
JsonOrAbsent = JsonValue | None


class SecretState(StrEnum):
    """Os dois unicos estados publicaveis de um secret (secao 11.1)."""

    CONFIGURED = "configured"
    MISSING = "missing"


class AdminSecrets(BaseModel):
    """Estado dos secrets. Nunca o valor, e nunca um derivado dele.

    Nao existe endpoint que defina ou rotacione um secret: rotacao e trocar a
    variavel de ambiente e reiniciar.

    `admin_token` e sempre `configured` — sem ele o processo nao teria subido
    (secao 2). O campo existe mesmo assim porque a ausencia dele levantaria a
    duvida de qual token a API usa; o valor constante responde sem revelar nada.
    """

    model_config = _STRICT

    hmac_sha256_key: SecretState
    admin_token: SecretState
    database_dsn: SecretState


class AdminRuntimeState(BaseModel):
    """Estado do runtime publicado e dos aposentados (secao 8)."""

    model_config = _STRICT

    revision: int

    #: No maximo 1, por `MAX_RETIRED_RUNTIMES`. Enquanto for 1, todo reload e
    #: recusado com `RELOAD_BUSY` — e nao ha teto de tempo para isso, porque um
    #: aposentado vive ate a query liberar a referencia (secao 8.5).
    retired_runtimes_open: int


class AdminCounters(BaseModel):
    """Contadores em memoria desde o start (secao 13.4).

    **Sao contadores, nao historico**, e se perdem no restart. Nao existe, e
    nao existira nesta fase, `GET /admin/v1/audit/*`: `audit/` emite metadata
    via `logging` e nao tem armazenamento consultavel, entao um endpoint de
    historico entregaria uma resposta que mente (secao 13.1).
    """

    model_config = _STRICT

    #: Aquisicoes de runtime desde o start. Uma query adquire exatamente uma
    #: vez (D-054), entao isto e a contagem de queries.
    queries_total: int

    #: Operacoes administrativas de escrita/reload TENTADAS desde o start. Desde
    #: a Etapa 9 cada uma das onze rotas de escrita incrementa este contador ao
    #: entrar na secao critica — sucesso ou recusa, e uma tentativa e uma
    #: tentativa. `config:validate` NAO conta: nao e uma escrita.
    admin_operations_total: int


class AdminStatusResponse(BaseModel):
    """`GET /admin/v1/status`."""

    model_config = _STRICT

    revision: int

    #: `false` enquanto a configuracao nao passou por `config:adopt`. Nesse
    #: estado a leitura funciona e os `id` sao nulos; a adocao e a Etapa 9.
    adopted: bool
    runtime: AdminRuntimeState
    counters: AdminCounters
    secrets: AdminSecrets


class RuleDocument(BaseModel):
    """Uma regra como o arquivo a descreve."""

    model_config = _STRICT

    #: Nulo enquanto a configuracao nao foi adotada. IDs nao sao inventados
    #: para preencher o campo: um ID instavel e pior que nenhum ID (secao 5.5).
    id: str | None
    match: str
    mode: MatchMode
    case_sensitive: bool
    transformer: str
    config: dict[str, Any]


class ExceptionDocument(BaseModel):
    """Uma exception como o arquivo a descreve. Nao tem transformer."""

    model_config = _STRICT

    id: str | None
    match: str
    mode: MatchMode
    case_sensitive: bool


class DatabaseDocument(BaseModel):
    """Limites de execucao. Nao ha DSN, host nem credencial — nem para leitura."""

    model_config = _STRICT

    statement_timeout_ms: int
    max_rows: int


class SqlDocument(BaseModel):
    """Extensoes de politica declaradas no arquivo.

    `allowed_pg_functions` aparece como LEITURA e nada mais. Nenhuma rota o
    acrescenta, remove ou altera: o campo pode liberar `pg_read_file`, e
    administra-lo por HTTP reabriria leitura de arquivos do servidor por
    chamada de API (secao 11.3, D-050).
    """

    model_config = _STRICT

    allowed_pg_functions: list[str]
    denied_functions: list[str]


class ConfigDocument(BaseModel):
    """O documento administrativo inteiro, fiel ao arquivo validado."""

    model_config = _STRICT

    revision: int
    masking: list[RuleDocument]
    exceptions: list[ExceptionDocument]
    database: DatabaseDocument
    sql: SqlDocument


class AdminConfigResponse(BaseModel):
    """`GET /admin/v1/config`."""

    model_config = _STRICT

    revision: int
    adopted: bool
    config: ConfigDocument


class RuleView(RuleDocument):
    """Regra com a posicao de avaliacao.

    `position` e DERIVADO da ordem no arquivo, e nao um campo dele. A ordem
    continua semanticamente relevante — *first match wins* (D-004) —, entao o
    ID estavel nao a substitui: sao coisas distintas, e reordenar e operacao
    propria (D-051).
    """

    position: int


class ExceptionView(ExceptionDocument):
    """Exception com a posicao no arquivo.

    Entre exceptions a ordem **nao** e semantica: toda exception que casa
    produz o mesmo desfecho, `ORIGINAL`. `position` esta aqui como referencia
    de leitura, e e por isso que nao existe reordenacao de exceptions.
    """

    position: int


class AdminRulesResponse(BaseModel):
    """`GET /admin/v1/rules`, em ordem de avaliacao."""

    model_config = _STRICT

    revision: int
    adopted: bool
    rules: list[RuleView]


class AdminRuleResponse(BaseModel):
    """`GET /admin/v1/rules/{rule_id}`."""

    model_config = _STRICT

    revision: int
    adopted: bool
    rule: RuleView


class AdminExceptionsResponse(BaseModel):
    """`GET /admin/v1/exceptions`."""

    model_config = _STRICT

    revision: int
    adopted: bool
    exceptions: list[ExceptionView]


class AdminExceptionResponse(BaseModel):
    """`GET /admin/v1/exceptions/{exception_id}`."""

    model_config = _STRICT

    revision: int
    adopted: bool
    exception: ExceptionView


class TransformerView(BaseModel):
    """Um transformer do catalogo: nome e parametros aceitos.

    Nomes, e nada alem de nomes. Nenhum objeto, nenhum callable, nenhum
    default e nenhum exemplo — `hmac_sha256` aparece sem parametro algum
    porque a chave vem do ambiente, e declarar `key` aqui sugeriria que ela
    poderia morar no arquivo.
    """

    model_config = _STRICT

    name: str
    required_parameters: list[str]
    optional_parameters: list[str]


class AdminTransformersResponse(BaseModel):
    """`GET /admin/v1/transformers`: o catalogo fechado do registry."""

    model_config = _STRICT

    revision: int
    transformers: list[TransformerView]


class ProtectedSession(BaseModel):
    """Garantias de sessao conferidas apos conectar (D-026, D-028, D-040)."""

    model_config = _STRICT

    read_only: bool
    statement_timeout_enforced_by: str
    provenance_capability_required: bool


class AdminProtectedResponse(BaseModel):
    """`GET /admin/v1/protected`: as protecoes estruturais, so leitura (D-050).

    Item criado para fechar vulnerabilidade nao pode ser desligado por
    configuracao administrativa. Nao ha rota que altere nada disto — e nao e
    "recusado", e inexistente. Campos como `read_only`,
    `allow_multiple_statements`, `disable_sql_validation`, `disable_masking`,
    `unmatched_policy`, `denied_relations` e `denied_prefixes` **nao existem**
    no documento administrativo (secao 11.2).
    """

    model_config = _STRICT

    revision: int

    #: `pg_statistic` e `pg_stats` carregam AMOSTRAS DOS DADOS em
    #: `most_common_vals` e `histogram_bounds`. Bloquea-las fechou F-05, um
    #: finding CRITICAL (D-039).
    denied_relations: list[str]

    #: Namespace `pg_` e negado por default; a allowlist abaixo e a excecao.
    pg_namespace_default: str
    allowed_pg_functions: list[str]
    denied_functions: list[str]
    denied_function_prefixes: list[str]

    #: As quatro regras do validator, por tipo de no da AST (D-031).
    validator_rules: list[str]

    session: ProtectedSession

    #: Ordem do pipeline de masking, por coluna do result set.
    pipeline: list[str]

    #: Comportamento de coluna sem correspondencia. `allow` e consequencia
    #: direta do modelo, nao um defeito, e mudar isso exige aprovacao propria.
    unmatched_policy: str

    #: Sempre `false`. O campo existe para que a resposta AFIRME a propriedade,
    #: em vez de deixa-la implicita na ausencia de rotas de escrita.
    editable: bool


# -- config:validate (Etapa 8) -------------------------------------------------
#
# O request e o proprio documento candidato na raiz, com os mesmos campos
# administrativos de `MaskingFileConfig`. Estes modelos sao PROPRIOS da fronteira
# HTTP: nao sao compartilhados com o plano MCP (secao 4.1), e tampouco sao os
# modelos de `config/models.py` — reusar aqueles arrastaria os defaults do loader
# para dentro da fronteira e apagaria a distincao entre o que a validacao de
# SCHEMA recusa (tipos, limites, campo desconhecido, formato de ID, adotado sem
# ID) e o que so a COMPILACAO recusa (regex, transformer, parametro, HMAC). O
# schema aqui produz `SCHEMA_INVALID`; a compilacao, feita depois com
# `validate_file_config` + `compile_policy`, produz `CONFIG_INVALID` (D-058).
#
# `expected_revision` NAO existe neste schema. Enviado, cai no `extra="forbid"`
# e vira `422 SCHEMA_INVALID`: o resultado do `validate` e funcao exclusiva do
# documento, e aceitar o campo sugeriria uma garantia de concorrencia que a
# operacao nao presta (secao 1.2).


class ValidateMatchRequest(BaseModel):
    """Campos comuns a regra e exception no request de validacao.

    Espelha `MatchConfig`: `match` nao vazio, `mode` do enum, `case_sensitive`.
    Os defaults sao os MESMOS do loader (`contains` para regra, `exact` para
    exception), para que o documento validado aqui seja identico ao que a
    escrita real compilaria.
    """

    model_config = _STRICT

    match: str = Field(min_length=1)
    #: Estrito: `1`/`0` JSON nao viram `True`/`False` (D-058).
    case_sensitive: StrictBool = False


class ValidateRuleRequest(ValidateMatchRequest):
    """Uma regra candidata. `mode` default `contains`, como em `RuleConfig`."""

    mode: MatchMode = MatchMode.CONTAINS
    transformer: str = Field(min_length=1)

    #: Herdada de §4.1: o unico `dict[str, Any]` da fronteira, validado pelo
    #: transformer alvo na COMPILACAO — que aqui acontece de fato.
    config: dict[str, Any] = Field(default_factory=dict)

    #: Ausente num documento nao adotado; obrigatorio quando `revision >= 1`. O
    #: formato e conferido pelo schema, entao um ID malformado e `SCHEMA_INVALID`.
    id: str | None = Field(default=None, pattern=RULE_ID_PATTERN)


class ValidateExceptionRequest(ValidateMatchRequest):
    """Uma exception candidata. `mode` default `exact`, como `ExceptionConfig`.

    Nao tem `transformer` nem `config`: uma exception que os trouxesse cairia no
    `extra="forbid"` e viraria `SCHEMA_INVALID`, que e o comportamento exigido.
    """

    mode: MatchMode = MatchMode.EXACT
    id: str | None = Field(default=None, pattern=EXCEPTION_ID_PATTERN)


class ValidateDatabaseRequest(BaseModel):
    """Limites de execucao candidatos. Mesmos limites de `DatabaseConfig`.

    Nao ha DSN, host nem credencial — nem para leitura, nem para validacao.
    """

    model_config = _STRICT

    #: Estritos: string numerica JSON (`"100"`) nao e aceita como inteiro (D-058).
    statement_timeout_ms: StrictInt = Field(
        default=30_000,
        ge=MIN_STATEMENT_TIMEOUT_MS,
        le=MAX_STATEMENT_TIMEOUT_MS,
    )
    max_rows: StrictInt = Field(default=1_000, ge=MIN_MAX_ROWS, le=MAX_MAX_ROWS)


class ValidateSqlRequest(BaseModel):
    """Extensoes de politica candidatas.

    `allowed_pg_functions` e aceito aqui porque `config:validate` valida o
    documento inteiro tal como seria escrito — o campo pode existir no arquivo.
    O que a Etapa 8 NAO faz e administra-lo: nao ha rota que o altere, e este
    request nunca persiste nada (D-050, secao 11.3).
    """

    model_config = _STRICT

    allowed_pg_functions: list[str] = Field(default_factory=list)
    denied_functions: list[str] = Field(default_factory=list)


class ConfigValidateRequest(BaseModel):
    """`POST /admin/v1/config:validate`: o documento candidato na raiz.

    Os defaults reproduzem os de `MaskingFileConfig`, entao um documento minimo
    — corpo `{}` — e valido, exatamente como um `masking.yaml` vazio carrega.
    """

    model_config = _STRICT

    #: Estrito: `"1"` JSON nao vira `1` (D-058). O tipo errado e `SCHEMA_INVALID`.
    revision: StrictInt = Field(default=UNADOPTED_REVISION, ge=0)
    masking: list[ValidateRuleRequest] = Field(default_factory=list)
    exceptions: list[ValidateExceptionRequest] = Field(default_factory=list)
    database: ValidateDatabaseRequest = Field(default_factory=ValidateDatabaseRequest)
    sql: ValidateSqlRequest = Field(default_factory=ValidateSqlRequest)

    @model_validator(mode="after")
    def _adopted_requires_ids(self) -> ConfigValidateRequest:
        """Documento adotado tem `id` em TODO item — recusa no BINDING do schema.

        Mesma regra estrutural de `MaskingFileConfig._adopted_requires_ids`, mas
        aplicada aqui, durante o parsing HTTP, para que "adotado sem ID" seja
        `SCHEMA_INVALID` e nao `CONFIG_INVALID` (D-058): a ausencia de ID num
        documento com `revision >= 1` e uma falha de FORMA do request, e o schema
        e quem a classifica. Como falha no binding, `validate_candidate` e
        `compile_policy` nem chegam a ser chamados.

        A mensagem e generica de proposito e, de todo modo, nao sai: o handler de
        `RequestValidationError` emite apenas o CAMINHO do campo (`body`) e um
        reason code fechado. Nenhum indice, ID, padrao ou valor submetido aparece
        na resposta.
        """
        if self.revision == UNADOPTED_REVISION:
            return self
        adopted_without_id = any(item.id is None for item in self.masking) or any(
            item.id is None for item in self.exceptions
        )
        if adopted_without_id:
            msg = "adopted configuration requires an id on every rule and exception"
            raise ValueError(msg)
        return self


class ConfigValidateResponse(BaseModel):
    """Resposta de sucesso de `config:validate`. Quatro booleanos, e nada mais.

    Sem `revision`, sem `applied`, sem conteudo normalizado, sem secret, sem
    detalhe de transformer e sem representacao do objeto compilado: a operacao
    nao le estado nem publica nada, entao a resposta nao carrega identidade de
    configuracao alguma (D-058).

    `database_checks_performed` e sempre `false` nesta fase: `config:validate`
    NAO conecta ao PostgreSQL. Conectar tem custo e efeito no servidor, e a
    verificacao de conexao pertence ao fluxo real de escrita, onde ha um
    candidato a publicar (secao 1.2). A resposta diz isso na propria forma, em
    vez de omitir e deixar o chamador supor.
    """

    model_config = _STRICT

    valid: bool
    schema_validated: bool
    policy_compiled: bool
    database_checks_performed: bool


# -- escrita e adocao (Etapa 9) ------------------------------------------------
#
# Todo request de escrita carrega `expected_revision` (inteiro estrito, >= 0) e o
# payload da operacao. Cada modelo e PROPRIO da fronteira, com `extra="forbid"` e
# `frozen=True`, escalares estritos como na Etapa 8, e nenhum compartilhamento com
# o MCP. A resposta de sucesso e sempre `{"revision", "applied"}`, e nada mais.
#
# Tres regras estruturais que estes modelos existem para tornar impossiveis de
# violar por engano:
#
# - um corpo GRANULAR (criar/substituir regra ou exception) NAO tem `id`,
#   `position` (salvo o create de regra), `revision` nem, numa exception,
#   `transformer`/`config`. IDs sao identidade do servidor (secao 5.5): um `id`
#   no corpo cairia no `extra="forbid"` e viraria `SCHEMA_INVALID`;
# - `allowed_pg_functions` NAO e administravel (secao 11.3). Em `PUT /sql` e `PUT
#   /config` ele e um campo OPCIONAL declarado so para ser recusado com
#   `IMMUTABLE_FIELD` quando presente — declara-lo permite distinguir "presente"
#   (imutavel) de "ausente" (valor atual preservado). Omiti-lo do schema o
#   transformaria em `SCHEMA_INVALID`, que e a categoria errada;
# - `expected_revision` e sempre estrito e nao negativo.


class WriteResponse(BaseModel):
    """Sucesso de qualquer escrita: a revision nova e a confirmacao (secao 4.4).

    Exatamente dois campos. Sem conteudo do documento, sem digest, sem secret:
    o cliente relê o estado com um `GET` se precisar do resto.
    """

    model_config = _STRICT

    revision: int
    applied: Literal[True] = True


class AdoptRequest(BaseModel):
    """`POST /admin/v1/config:adopt` (secao 5.3).

    `confirm_comment_loss` deve ser o booleano JSON literal `true`. Uma volta por
    Pydantic/PyYAML destroi os comentarios do arquivo, e isso e irreversivel —
    precisa ser dito antes, sem ambiguidade.
    """

    model_config = _STRICT

    expected_revision: StrictInt = Field(ge=0)
    #: Estrito por DOIS motivos, e por isso NAO e `Literal[True]` sozinho:
    #: `Literal[True]` aceita o inteiro `1`, porque `1 == True` em Python. Com
    #: `StrictBool`, `1`, `0`, `"true"` e `null` sao recusados pelo tipo — so um
    #: booleano JSON passa —, e o `model_validator` abaixo exige que seja `true`.
    #: Ausencia, `false`, `0`, `1`, `"true"` e `null`: todos `SCHEMA_INVALID`.
    confirm_comment_loss: StrictBool

    @model_validator(mode="after")
    def _must_confirm(self) -> AdoptRequest:
        if self.confirm_comment_loss is not True:
            msg = "adoption requires confirm_comment_loss to be true"
            raise ValueError(msg)
        return self


class DeleteRequest(BaseModel):
    """Corpo de um `DELETE` de regra/exception: so `expected_revision`."""

    model_config = _STRICT

    expected_revision: StrictInt = Field(ge=0)


class RuleContent(BaseModel):
    """O conteudo de uma regra num corpo granular: sem `id`, sem `position`.

    Espelha `RuleConfig` (mesmos defaults do loader), mas sem os campos que sao
    identidade do servidor ou ordem. Um `id` ou `position` aqui cai no
    `extra="forbid"` — `SCHEMA_INVALID`.
    """

    model_config = _STRICT

    match: str = Field(min_length=1)
    mode: MatchMode = MatchMode.CONTAINS
    case_sensitive: StrictBool = False
    transformer: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class ExceptionContent(BaseModel):
    """O conteudo de uma exception num corpo granular: sem `id`, sem `position`.

    Sem `transformer` nem `config`: uma exception que os trouxesse cairia no
    `extra="forbid"`.
    """

    model_config = _STRICT

    match: str = Field(min_length=1)
    mode: MatchMode = MatchMode.EXACT
    case_sensitive: StrictBool = False


class RuleCreateRequest(BaseModel):
    """`POST /admin/v1/rules`: cria uma regra. `position` opcional (default fim)."""

    model_config = _STRICT

    expected_revision: StrictInt = Field(ge=0)
    rule: RuleContent
    #: Zero-based, de 0 a `len(rules)`. `None` = fim. A validade dependente do
    #: estado (0..len) e conferida na mutacao, e vira `CONFIG_INVALID`, nao aqui:
    #: o schema so garante que, se presente, e inteiro estrito e >= 0.
    position: StrictInt | None = Field(default=None, ge=0)


class RuleReplaceRequest(BaseModel):
    """`PUT /admin/v1/rules/{rule_id}`: substitui o conteudo, preserva ID/posicao."""

    model_config = _STRICT

    expected_revision: StrictInt = Field(ge=0)
    rule: RuleContent


class RuleReorderRequest(BaseModel):
    """`POST /admin/v1/rules:reorder`: a lista completa de IDs na nova ordem.

    Cada item de `rule_ids` deve casar `RULE_ID_PATTERN` NO SCHEMA: um ID
    malformado e `SCHEMA_INVALID`, nao `CONFIG_INVALID` — o formato e uma falha de
    forma do request. A lista PODE ser vazia: e a permutacao completa do conjunto
    vazio, valida quando a configuracao nao tem regra alguma.

    Ja a semantica — permutacao completa, sem duplicata, sem ID estranho — depende
    do estado e e conferida na mutacao, que a recusa com `CONFIG_INVALID`.
    """

    model_config = _STRICT

    expected_revision: StrictInt = Field(ge=0)
    #: Formato por item, no schema; sem `min_length`, para aceitar a lista vazia.
    rule_ids: list[Annotated[str, Field(pattern=RULE_ID_PATTERN)]] = Field(default_factory=list)


class ExceptionCreateRequest(BaseModel):
    """`POST /admin/v1/exceptions`: cria uma exception, sempre ao final."""

    model_config = _STRICT

    expected_revision: StrictInt = Field(ge=0)
    exception: ExceptionContent


class ExceptionReplaceRequest(BaseModel):
    """`PUT /admin/v1/exceptions/{exception_id}`: substitui, preserva ID/posicao."""

    model_config = _STRICT

    expected_revision: StrictInt = Field(ge=0)
    exception: ExceptionContent


class DatabaseWriteRequest(BaseModel):
    """`PUT /admin/v1/database`: substitui os dois limites, ambos obrigatorios.

    Nao ha DSN, host, usuario, senha nem parametro de conexao — um campo desses
    cai no `extra="forbid"`.
    """

    model_config = _STRICT

    expected_revision: StrictInt = Field(ge=0)
    statement_timeout_ms: StrictInt = Field(
        ge=MIN_STATEMENT_TIMEOUT_MS,
        le=MAX_STATEMENT_TIMEOUT_MS,
    )
    max_rows: StrictInt = Field(ge=MIN_MAX_ROWS, le=MAX_MAX_ROWS)


class SqlWriteRequest(BaseModel):
    """`PUT /admin/v1/sql`: aditivo em `denied_functions` (secao 11.3).

    `allowed_pg_functions` NAO e administravel. Ele e declarado aqui apenas para
    que sua PRESENCA — em QUALQUER forma, inclusive `null`, `[]`, string, objeto,
    booleano ou numero — seja recusada com `IMMUTABLE_FIELD` na mutacao.

    A presenca e detectada por `model_fields_set`, nunca pelo VALOR: `null`
    explicito e um campo presente, e trata-lo como ausente (checando `is not
    None`) era o bypass corrigido. O tipo do campo e `object` de proposito — nao
    `list[str] | None` —, para que qualquer forma seja ACEITA pelo schema e a
    recusa seja `IMMUTABLE_FIELD` (administrativa), e nao `SCHEMA_INVALID`. O
    default e um sentinela privado, distinto de qualquer valor JSON, para que a
    ausencia seja inequivoca mesmo se `model_fields_set` fosse insuficiente.
    """

    model_config = _STRICT

    expected_revision: StrictInt = Field(ge=0)
    denied_functions: list[str] = Field(default_factory=list)
    allowed_pg_functions: JsonOrAbsent = None

    @property
    def allowed_pg_functions_present(self) -> bool:
        """`True` se o cliente enviou o campo, em qualquer forma (inclusive `null`)."""
        return "allowed_pg_functions" in self.model_fields_set


class ConfigReplaceRule(BaseModel):
    """Uma regra no corpo de `PUT /config`. `id` OPCIONAL: presente preserva a
    identidade; ausente cria (secao 11.3)."""

    model_config = _STRICT

    match: str = Field(min_length=1)
    mode: MatchMode = MatchMode.CONTAINS
    case_sensitive: StrictBool = False
    transformer: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)
    #: Formato conferido pelo schema; pertinencia ao documento, pela mutacao.
    id: str | None = Field(default=None, pattern=RULE_ID_PATTERN)


class ConfigReplaceException(BaseModel):
    """Uma exception no corpo de `PUT /config`. `id` OPCIONAL, como nas regras."""

    model_config = _STRICT

    match: str = Field(min_length=1)
    mode: MatchMode = MatchMode.EXACT
    case_sensitive: StrictBool = False
    id: str | None = Field(default=None, pattern=EXCEPTION_ID_PATTERN)


class ConfigReplaceDatabase(BaseModel):
    """Os dois limites no corpo de `PUT /config`, ambos obrigatorios."""

    model_config = _STRICT

    statement_timeout_ms: StrictInt = Field(
        ge=MIN_STATEMENT_TIMEOUT_MS,
        le=MAX_STATEMENT_TIMEOUT_MS,
    )
    max_rows: StrictInt = Field(ge=MIN_MAX_ROWS, le=MAX_MAX_ROWS)


class ConfigReplaceSql(BaseModel):
    """A secao `sql` no corpo de `PUT /config`: `denied_functions` obrigatorio.

    `denied_functions` e OBRIGATORIO numa substituicao integral: com um default
    vazio, `sql: {}` apagaria em silencio todas as negacoes. Ausente ->
    `SCHEMA_INVALID`.

    `allowed_pg_functions` presente em QUALQUER forma (inclusive `null`) ->
    `IMMUTABLE_FIELD` na mutacao, detectado por `model_fields_set`. Ausente -> o
    valor atual e preservado. E o unico modo de preservar o allowlist imutavel.
    """

    model_config = _STRICT

    denied_functions: list[str]
    allowed_pg_functions: JsonOrAbsent = None

    @property
    def allowed_pg_functions_present(self) -> bool:
        return "allowed_pg_functions" in self.model_fields_set


class ConfigReplaceRequest(BaseModel):
    """`PUT /admin/v1/config`: substituicao integral da configuracao administravel.

    `masking`, `exceptions`, `database` e `sql` (so `denied_functions`) sao
    obrigatorios. A `revision` e escolhida pelo servidor. Regras de ID (secao
    11.3, D-059):

    - item com `id` existente: identidade preservada;
    - item sem `id`: criacao, recebe ID do servidor;
    - `id` que nao pertence ao documento corrente: tentativa de escolher
      identidade -> `IMMUTABLE_FIELD` (na mutacao);
    - IDs atuais omitidos: removidos.

    `sql.allowed_pg_functions` presente em qualquer forma -> `IMMUTABLE_FIELD`;
    ausente -> o valor atual e preservado em conteudo e ordem (secao 11.3).
    """

    model_config = _STRICT

    expected_revision: StrictInt = Field(ge=0)
    masking: list[ConfigReplaceRule]
    exceptions: list[ConfigReplaceException]
    database: ConfigReplaceDatabase
    sql: ConfigReplaceSql
