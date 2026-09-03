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
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, Strict, model_validator

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

    #: Operacoes administrativas de escrita/reload TENTADAS desde o start. Na
    #: Etapa 7 nao ha rota de escrita, entao so cresce por uso programatico da
    #: secao critica.
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
