"""`config:validate`: valida e compila um documento candidato, SEM efeitos.

Etapa 8 da Fase 7. Esta e a unica operacao com corpo que **nao** e uma escrita
(secao 1.2). Ela responde por schema e compilacao, e nada mais:

```text
schema HTTP  -> ConfigValidateRequest       -> 422 SCHEMA_INVALID  (handler do FastAPI)
validacao    -> validate_file_config(doc)    -> 422 CONFIG_INVALID
compilacao   -> compile_policy(doc, secrets) -> 422 CONFIG_INVALID
resultado compilado -> DESCARTADO
```

## Por que compilar, e nao so validar o schema

Um `regex` com padrao invalido, um transformer inexistente, um parametro
obrigatorio ausente, um parametro desconhecido e uma regra `hmac_sha256` sem
chave no ambiente **so aparecem na compilacao**. Um dry-run que parasse no
schema aprovaria configuracao que a escrita real recusaria — e seria pior que
nao existir (secao 1.2). Por isso `compile_policy` e chamado de verdade, com o
`SecretProvider` atual, e so o veredito e mantido.

## O que esta funcao NAO faz, por construcao

Ela recebe o documento ja validado pelo schema, `secrets` e `registry`. Nao
recebe — e portanto nao pode tocar — o `AdminConfigService`, o `RuntimeRegistry`,
o `ConfigFileStore` nem a secao critica. Nao le `snapshot()`, revision nem
digest; nao cria `PostgresAdapter`; nao conecta ao PostgreSQL; nao persiste; nao
altera revision; nao incrementa contador administrativo. A ausencia de efeito e
propriedade da assinatura, e nao de disciplina: o que nao chega aqui nao pode
ser alcancado.

## Sanitizacao

Toda falha vira `AdminError` de categoria fechada, levantado FORA do `except`
que o originou (D-017): `validate_file_config` e `compile_policy` levantam
`ConfigError`, cuja mensagem pode citar o transformer, o indice da regra ou o
texto do `pglast` — e nada disso sai. Uma falha inesperada vira
`INTERNAL_ERROR`. Nem `str(exc)`, nem `match`, nem valor de `config`, nem
traceback, nem cadeia de excecao atravessam a fronteira.
"""

from __future__ import annotations

from maskgw.admin.errors import AdminError, AdminErrorCategory
from maskgw.admin.http.schemas import ConfigValidateRequest, ConfigValidateResponse
from maskgw.config.loader import compile_policy, validate_file_config
from maskgw.errors import ConfigError
from maskgw.masking.transformers.registry import TransformerRegistry, build_default_registry
from maskgw.secretsource import SecretProvider


def validate_candidate(
    request: ConfigValidateRequest,
    *,
    secrets: SecretProvider,
    registry: TransformerRegistry | None = None,
) -> ConfigValidateResponse:
    """Valida e compila o documento candidato; descarta o resultado.

    Quando retorna, o documento passou pelo validator e pela compilacao de TODOS
    os transformers e da `MaskingPolicy`. O objeto compilado e descartado no
    mesmo instante: nada e publicado, nada e persistido, nada e conectado.

    Levanta `AdminError(CONFIG_INVALID)` quando a validacao ou a compilacao
    recusa o documento, e `AdminError(INTERNAL_ERROR)` para qualquer falha
    inesperada. Sempre de categoria fechada, sem detalhe da causa.
    """
    catalog = registry if registry is not None else build_default_registry()

    failure: AdminError | None = None
    try:
        # O documento ja passou pelo schema HTTP; `model_dump` devolve os mesmos
        # campos administrativos que o loader espera. Revalidar aqui e
        # deliberado: garante que o documento compilado seja EXATAMENTE o que a
        # escrita real compilaria, com os mesmos modelos de `config/models.py`.
        # As recusas de FORMA (tipos, limites, campo desconhecido, formato de ID,
        # adotado sem ID) ja aconteceram no binding do schema HTTP e viraram
        # `SCHEMA_INVALID` antes de chegar aqui; o que este passo ainda pega sao
        # recusas do loader que o schema HTTP nao replica.
        document = validate_file_config(request.model_dump())
        # Compila os transformers e a policy. O resultado nao e guardado.
        compile_policy(document, secrets=secrets, registry=catalog)
    except ConfigError:
        failure = AdminError(AdminErrorCategory.CONFIG_INVALID)
    except BaseException:
        # Nada inesperado escapa com detalhe. Sem este ramo, um erro nao
        # previsto subiria com traceback e mensagem originais.
        failure = AdminError(AdminErrorCategory.INTERNAL_ERROR)

    if failure is not None:
        # Levantado FORA do `except`: `__cause__` e `__context__` ficam nulos,
        # mesmo quando a falha nasceu dentro de um handler ativo (D-017).
        raise failure

    return ConfigValidateResponse(
        valid=True,
        schema_validated=True,
        policy_compiled=True,
        # `config:validate` nunca conecta ao PostgreSQL (secao 1.2).
        database_checks_performed=False,
    )
