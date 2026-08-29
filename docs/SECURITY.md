# Security Requirements

## Critical Rule

Nenhum valor retornado pelo banco pode ser enviado ao cliente MCP antes da
aplicação das regras.

## Postura do MVP

O comportamento default é **ALLOW**: coluna que não corresponde a nenhuma
regra passa em claro.

Consequência aceita conscientemente: uma coluna sensível cujo nome não casa
nenhuma regra — nem por `output_name`, nem por `origin_name` — não é
mascarada. A proteção depende da qualidade do `masking.yaml`.

Mitigação operacional: revisar o schema e cadastrar as regras antes de expor
o Gateway. Default deny está documentado como hardening futuro.

## Cliente

A IA é um cliente não confiável. Nunca aceitar do cliente:
- alteração das regras
- desativação do masking
- bypass
- credenciais do banco
- chaves de transformação

## Obrigatório no MVP

- somente SELECT
- role PostgreSQL read-only
- `statement_timeout` configurado
- limite máximo de linhas por resposta
- configuração fail-closed
- nenhuma informação sensível em logs
- erros do PostgreSQL sanitizados
- cliente não pode alterar ou desabilitar masking

## Logs

Nunca registrar valores originais de CPF, CNPJ, e-mail, telefone, senha,
tokens ou outros dados sensíveis.

Logs devem conter somente metadata: identificador da consulta, nomes de
coluna, regra aplicada, contagem de linhas, duração.

Nunca registrar a chave HMAC.

## Errors

Não retornar ao cliente:
- result sets
- valores sensíveis
- parâmetros sensíveis
- stack traces internos
- mensagem bruta do PostgreSQL

Mensagens do PostgreSQL podem embutir valores — por exemplo
`invalid input syntax for type integer: "..."` — e por isso nunca são
repassadas. O erro é mapeado para uma mensagem genérica; o detalhe fica
apenas no lado servidor, com redação.

## Database

Usar conexão read-only, com role dedicada sem permissão de escrita.

Bloquear:
INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE.

A validação de SQL é feita por parsing (pglast) com allowlist, nunca por
blocklist de palavras-chave. A role read-only é a segunda camada: a validação
pode falhar, o privilégio do banco não.

## Chaves

A chave do `hmac_sha256` vem de secret/variável de ambiente, separada do
`masking.yaml`. Ausência da chave com regra que a exige impede o boot.

## Bypass a testar

- aliases
- SELECT *
- JOIN
- UNION
- subquery
- CTE
- views
- funções SQL
- casts
- uppercase/lowercase/mixed case
- prefixos e sufixos
- NULL
- erros
- logs
- metadata

## Regra de prioridade

EXCEPTION > MASKING > ORIGINAL

## Fora do escopo do MVP

Os itens abaixo são riscos conhecidos e **aceitos** nesta versão. Estão
detalhados em `docs/FUTURE-HARDENING.md`:

- bloqueio de WHERE sobre dados sensíveis
- bloqueio de ORDER BY / GROUP BY sobre dados sensíveis
- supressão de agregações
- controle de cardinalidade
- RBAC
- column-level GRANT automático
- inspeção profunda de JSONB
- transformers Python customizados
- multi-tenant
