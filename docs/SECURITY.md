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

## Superfície exposta ao cliente MCP

Uma tool, `query_database(sql: str)`, sobre stdio. Nenhuma porta de rede.

O cliente controla apenas a SQL — não porque outros parâmetros sejam recusados,
mas porque não existem no schema. Medido no SDK v2.1.1: argumentos extras são
**ignorados**, não rejeitados (D-037); a garantia testada é que nenhum extra
altera o resultado.

Não há `resources` nem `prompts`: nada de `masking://config`,
`database://schema` ou `security://rules`.

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

Desde a Fase 5 existe log, e só em `audit/` — o único módulo do projeto
autorizado a importar `logging`, verificado por teste global. `masking/`
continua proibido.

Os campos auditados são fechados por construção (`QueryAudit`): `request_id`,
`outcome`, `duration_ms`, `row_count`, `truncated`, `error_category`. Não
existe parâmetro para SQL, valores ou segredos.

**Nomes de coluna não são registrados**, ao contrário do que esta seção previa:
uma coluna pode ter nome revelador, e o benefício não compensa. Correlação usa
`request_id`; digest da SQL foi descartado por ser um oráculo sobre predicados
(D-035).

Nunca registrar a chave HMAC.

## Errors

Erros externos vêm de um conjunto fixo e nunca citam a consulta:

| erro | quando |
|---|---|
| `InvalidQuery` | SQL malformada; mensagem fixa, sem o texto do parser |
| `QueryRejected` | SQL válida recusada pela política; `reason` de um conjunto fixo de sete constantes |
| `QueryTimeout` | SQLSTATE 57014, do `statement_timeout` |
| `DatabaseError` | demais erros do PostgreSQL, por classe de SQLSTATE |
| `CapabilityError` | instalação sem uma capacidade essencial; fatal no startup |

Na fronteira MCP tudo isso vira uma de cinco categorias — `INVALID_QUERY`,
`QUERY_REJECTED`, `QUERY_TIMEOUT`, `DATABASE_ERROR`, `CONFIGURATION_ERROR` —
com mensagem curta e fixa. Toda exceção é capturada no Gateway, inclusive as
inesperadas: sem isso o SDK registraria o traceback original nos logs antes de
redigir a resposta (D-038).

Nenhum deles encadeia a exceção original: `__cause__` e `__context__` ficam
nulos (D-017). Nem o nome da função proibida entra na mensagem.

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

Desde a Fase 4 o Gateway aplica, além disso, na própria sessão:

```text
-c default_transaction_read_only=on
-c statement_timeout=<database.statement_timeout_ms>
```

Ambos vão em `options` do DSN, aplicados pelo backend na inicialização — não há
janela entre conectar e proteger — e são **conferidos** em `pg_settings` logo
após a conexão. Se não pegaram, o Gateway não opera (`CapabilityError`).

Isso não substitui a role sem privilégio de escrita. São camadas distintas, e a
suíte prova a de baixo chamando o adapter sem passar pelo validator.

**A role precisa manter EXECUTE apenas no que for necessário.** A política de
funções (D-027) nega o namespace `pg_` por default, mas uma função definida
pelo usuário com efeito colateral e nome comum passa pelo validator. A barreira
real ali é o privilégio: a role não deve ter `EXECUTE` em funções perigosas nem
pertencer a `pg_read_server_files` ou `pg_execute_server_program`.

**A role precisa manter leitura em `pg_catalog`.** A proteção contra bypass por
alias depende de resolver `(oid, attnum)` em `pg_attribute`, `pg_class` e
`pg_namespace`. Uma role sem esse acesso faz toda coluna cair em `UNKNOWN`, e
`SELECT cpf AS documento` volta a passar em claro — **em silêncio**, porque a
falha de resolução é deliberadamente não fatal (D-025). O acesso é concedido a
`PUBLIC` por padrão; um hardening que o remova precisa saber disso.

Bloquear:
INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE.

A validação de SQL é feita por parsing (pglast) com allowlist, nunca por
blocklist de palavras-chave. A role read-only é a segunda camada: a validação
pode falhar, o privilégio do banco não.

Quatro regras, todas por tipo de nó da AST (D-031):

1. exatamente um statement **executável** — o parser descarta os vazios, então
   o critério é a contagem de statements reconhecidos, não a de `;`
2. raiz `SelectStmt`
3. nenhum outro nó `*Stmt` em ponto algum da árvore — cobre CTE modificadora,
   CTE aninhada e CTE dentro de subquery
4. `IntoClause` e `LockingClause` recusadas em qualquer ponto

A regra 4 existe porque **`SELECT 1 INTO nova` parseia como `SelectStmt` e cria
uma tabela**, e `SELECT ... FOR UPDATE` trava linhas. Raiz SELECT não basta.

## Chaves

A chave do `hmac_sha256` vem de secret/variável de ambiente, separada do
`masking.yaml`. Ausência da chave com regra que a exige impede o boot.

## Proteção contra alias

Desde a Fase 3 o `origin_name` é resolvido a partir da metadata do próprio
PostgreSQL — `ftable`/`ftablecol` do result set, cruzados com o catálogo.
Nunca a partir dos valores das linhas, e nunca por parsing textual da SQL.

Cobertos: alias, alias em subquery, alias em CTE, alias sobre JOIN, alias sobre
cast, alias sobre view, `SELECT *` e nomes duplicados.

**Não** cobertos, por o PostgreSQL não informar origem: UNION, expressões,
literais e agregados. Nesses casos resta o `output_name`, e
`SELECT cpf AS documento FROM a UNION ALL SELECT cpf FROM b` passa em claro.
Ver `docs/FUTURE-HARDENING.md`.

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

## Resultado do red team (Fase 6)

`docs/SECURITY-REVIEW.md` traz o relatório completo: 11 findings, dois
corrigidos, nove aceitos com teste que fixa o comportamento.

**Antes de expor este Gateway, entenda que:**

- expressão sobre coluna sensível (`substr(cpf,1,11) AS x`), UNION com alias e
  alias para o nome de uma exception devolvem o valor **em claro**. São três
  bypasses de uma linha de SQL cada.
- a role do Gateway **precisa ter `EXECUTE` revogado** nas funções de usuário —
  `EXECUTE` é concedido a `PUBLIC` por padrão, e uma função pré-existente que
  leia coluna sensível devolve o valor sob o nome dela.
- o oráculo por predicado reconstrói um CPF em 11 consultas.

O Gateway eleva o custo do vazamento acidental. Não resiste a um cliente
adversarial. Uso interno com cliente semi-confiável.

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
