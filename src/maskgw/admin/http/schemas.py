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
from typing import Any

from pydantic import BaseModel, ConfigDict

from maskgw.masking.rules import MatchMode

#: Mesmo perfil dos modelos de configuracao: chave desconhecida e erro, e o
#: modelo nao aceita reatribuicao de campo.
_STRICT = ConfigDict(extra="forbid", frozen=True)


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
