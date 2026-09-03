"""Modelos de configuracao (Pydantic).

`extra="forbid"` em todos os modelos: uma chave desconhecida — inclusive um
erro de digitacao como `transfomer:` — impede a inicializacao. Fail-closed.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from maskgw.config.ids import EXCEPTION_ID_PATTERN, RULE_ID_PATTERN
from maskgw.masking.rules import MatchMode

_STRICT = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)


class MatchConfig(BaseModel):
    """Campos comuns a regras e exceptions."""

    model_config = _STRICT

    match: str = Field(min_length=1, description="Padrao comparado ao nome da coluna")
    mode: MatchMode = MatchMode.CONTAINS
    case_sensitive: bool = False


class ExceptionConfig(MatchConfig):
    """Exception: tem prioridade absoluta e nao possui transformer.

    O default de `mode` e `exact`, e nao `contains` como nas regras. A
    assimetria e deliberada: uma regra larga protege demais, uma exception
    larga protege de menos. Ver docs/DECISIONS.md (D-045) e o hazard H-1.
    """

    mode: MatchMode = MatchMode.EXACT

    #: ID administrativo estavel (D-051). Ausente num arquivo ainda nao
    #: adotado; obrigatorio depois da adocao. Nao participa do matching.
    id: str | None = Field(default=None, pattern=EXCEPTION_ID_PATTERN)


class RuleConfig(MatchConfig):
    """Regra de masking. `mode` default `contains`, herdado de MatchConfig."""

    transformer: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)

    #: ID administrativo estavel (D-051). Ausente num arquivo ainda nao
    #: adotado; obrigatorio depois da adocao. Nao participa do matching.
    id: str | None = Field(default=None, pattern=RULE_ID_PATTERN)


#: Limites do `statement_timeout`. Abaixo do minimo qualquer consulta real
#: falharia; acima do maximo o timeout deixaria de ser uma protecao.
MIN_STATEMENT_TIMEOUT_MS = 100
MAX_STATEMENT_TIMEOUT_MS = 600_000

#: Limites do numero maximo de linhas devolvidas por consulta.
MIN_MAX_ROWS = 1
MAX_MAX_ROWS = 1_000_000


class DatabaseConfig(BaseModel):
    """Limites de execucao aplicados no lado do PostgreSQL.

    Nao ha DSN nem credencial aqui: elas continuam fora do `masking.yaml`.
    """

    model_config = _STRICT

    statement_timeout_ms: int = Field(
        default=30_000,
        ge=MIN_STATEMENT_TIMEOUT_MS,
        le=MAX_STATEMENT_TIMEOUT_MS,
        description="Timeout por statement, aplicado pelo PostgreSQL",
    )
    max_rows: int = Field(
        default=1_000,
        ge=MIN_MAX_ROWS,
        le=MAX_MAX_ROWS,
        description="Maximo de linhas devolvidas; o excesso marca truncated",
    )


class SqlConfig(BaseModel):
    """Extensoes da politica de funcoes SQL.

    A politica default vive em `maskgw.sql.policy`. Aqui so se acrescenta.
    Em conflito, a negacao vence.
    """

    model_config = _STRICT

    allowed_pg_functions: list[str] = Field(default_factory=list)
    denied_functions: list[str] = Field(default_factory=list)


#: `revision` 0 significa "configuracao ainda nao adotada pela Admin API".
#: Um `masking.yaml` escrito a mao nao tem o campo e cai aqui — e continua
#: carregando normalmente, sem Admin API e sem adocao. Ver a spec da Fase 7,
#: secao 5.2, e docs/DECISIONS.md (D-052).
UNADOPTED_REVISION = 0


class MaskingFileConfig(BaseModel):
    """Conteudo completo do `masking.yaml`.

    `revision` e os `id` das regras e exceptions sao metadata ADMINISTRATIVA:
    nao participam do matching e nao alteram nenhuma decisao de masking. Um
    arquivo sem eles carrega normalmente — e o requisito de compatibilidade da
    Fase 7.
    """

    model_config = _STRICT

    #: Contador otimista de concorrencia administrativa (D-052). Monotonico,
    #: nunca reutilizado, escolhido pelo servidor e nunca pelo cliente.
    #: Persistido DENTRO do arquivo: fora dele, arquivo e revision poderiam
    #: divergir na janela de crash entre persistir e trocar (D-048).
    revision: int = Field(default=UNADOPTED_REVISION, ge=0)

    masking: list[RuleConfig] = Field(default_factory=list)
    exceptions: list[ExceptionConfig] = Field(default_factory=list)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    sql: SqlConfig = Field(default_factory=SqlConfig)

    @model_validator(mode="after")
    def _adopted_requires_ids(self) -> MaskingFileConfig:
        """Uma configuracao adotada tem ID em TODO item.

        Sem esta regra existe um estado do qual nao se sai: `revision >= 1`
        com um item sem ID faria toda escrita ser recusada por
        `CONFIG_NOT_ADOPTED`, enquanto `config:adopt` — que exige
        `expected_revision = 0` — seria recusada por `REVISION_CONFLICT`. A
        Admin API ficaria travada, sem operacao possivel.

        Acontece na pratica: edicao manual de um arquivo ja adotado para
        acrescentar uma regra, que e o caminho suportado para edicao externa.
        Falhar no carregamento, com uma mensagem que diz o que fazer, e melhor
        que subir e travar a administracao depois.
        """
        if self.revision == UNADOPTED_REVISION:
            return self

        missing = [
            f"masking[{index}]" for index, item in enumerate(self.masking) if item.id is None
        ] + [
            f"exceptions[{index}]" for index, item in enumerate(self.exceptions) if item.id is None
        ]
        if missing:
            locations = ", ".join(missing)
            msg = (
                f"configuracao adotada (revision={self.revision}) exige `id` em todo item; "
                f"faltam em: {locations}. Acrescente um `id` unico a cada um, ou remova "
                f"`revision` para voltar ao estado nao adotado."
            )
            raise ValueError(msg)

        # IDs sao identidade estavel (D-051, D-059): dois itens com o mesmo `id`
        # tornam CRUD por ID ambiguo — um `PUT /rules/{id}` nao saberia qual
        # substituir. Prefixos distintos ja impedem um ID de regra colidir com um
        # de exception, entao a checagem por lista basta. Recusar no carregamento
        # e coerente com "adotado exige ID": um estado inconsistente nao sobe.
        rule_ids = [item.id for item in self.masking if item.id is not None]
        exception_ids = [item.id for item in self.exceptions if item.id is not None]
        if len(set(rule_ids)) != len(rule_ids) or len(set(exception_ids)) != len(exception_ids):
            msg = (
                f"configuracao adotada (revision={self.revision}) exige `id` UNICO em cada "
                f"regra e em cada exception; ha IDs repetidos."
            )
            raise ValueError(msg)
        return self
