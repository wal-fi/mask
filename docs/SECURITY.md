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
`pg_namespace`. O acesso é concedido a `PUBLIC` por padrão; um hardening que o
remova precisa saber disso.

Sem esse acesso o Gateway **não responde**, em vez de responder errado:

- no **startup**, `check_provenance_capability` falha e o processo não sobe
  (D-026);
- em **runtime**, a falha de consulta ao catálogo **rejeita a consulta** com
  `CONFIGURATION_ERROR` sanitizado (D-040, que emendou D-025).

A distinção que importa: `DERIVED` — o PostgreSQL afirmando que a coluna não
tem origem única — continua sendo estado legítimo e segue o fluxo normal.
Falha *operacional* de resolução é outra coisa, e derruba a consulta.

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

## Filesystem da configuração administrativa

Os primitivos da Etapa 5 falham fechado antes de administrar o arquivo:

- `masking.yaml`, seu diretório pai e `masking.yaml.lock` são inspecionados sem
  seguir symlink; arquivo/lock precisam ser regulares e o pai, diretório real;
- no POSIX, arquivo e pai não podem ser graváveis por group/other, e lock e
  temporários usam modo `0600`;
- o sidecar é criado com `O_CREAT | O_EXCL`, nunca truncado, e fica aberto com
  lock exclusivo não bloqueante até `ConfigFileStore.close()`;
- a escrita usa temporário de nome estrito no mesmo diretório, `O_EXCL`, flush,
  `fsync` e `os.replace`; somente depois sincroniza o diretório no POSIX;
- limpeza remove apenas regular não-symlink que case exatamente
  `.masking.yaml.tmp.<pid>.<16 hex>`;
- SHA-256 é calculado sobre bytes exatos, com verificações no início e
  imediatamente antes do `replace`; divergência nunca sobrescreve o editor.

No Windows, os bits de `mode` são sintéticos e não validam ACLs; `0600` é
best-effort e `fsync` de diretório é omitido. Filesystem remoto (NFS, SMB/CIFS)
continua não suportado e não há detecção automática. Resta também a janela
portável, documentada, entre a segunda verificação de digest e o `replace`.

## Seção crítica administrativa

A Etapa 6 acrescentou o fluxo de escrita/reload em `admin/`. Ele **não** é uma
superfície de rede: não há HTTP, porta, bind, autenticação nem thread nova, e
isso pertence à Etapa 7. Os invariantes que já valem:

- **toda escrita administrativa é serializada** por um único lock in-process,
  e é dentro dele que o estado de adoção, o `expected_revision`, o digest do
  arquivo e o limite de aposentados são verificados. Duas operações com o mesmo
  `expected_revision` não vencem ambas (D-052);
- **nada é criado para uma operação condenada**: os quatro primeiros passos
  precedem compilar, construir e conectar qualquer candidato;
- **o candidato é comprovado antes de ser persistido** — compilado, conectado e
  submetido aos três capability checks (read-only, `statement_timeout`,
  proveniência). Uma configuração que derrubaria o Gateway falha aqui, com o
  runtime antigo intacto (D-048);
- **falha antes do `os.replace`** preserva o arquivo byte a byte, mantém o
  mesmo objeto runtime publicado — em identidade **e em conteúdo** —, mantém o
  digest e fecha o candidato exatamente uma vez;
- **nenhum objeto mutável do runtime publicado atravessa a fronteira
  administrativa.** A mutação recebe uma cópia profunda do documento, e a
  leitura administrativa também devolve cópia. O `frozen=True` do Pydantic é
  superficial: ele impede reatribuir um campo, mas `masking`, `exceptions`,
  `sql.allowed_pg_functions` e o `config` de cada regra continuam sendo lista e
  dicionário comuns. Sem a cópia, uma mutação que falhasse ainda esvaziaria as
  regras do runtime publicado, e a escrita seguinte — válida e sem relação com
  ela — persistiria zero regras e publicaria um engine **sem masking** (D-055);
- **falha de durabilidade depois do `replace`** não afirma rollback: o runtime
  novo é publicado e a resposta é `CONFIG_DURABILITY_ERROR` com `applied=true`;
- **nenhum adapter é fechado com query em andamento**, e o aposentado é fechado
  exatamente uma vez (D-054);
- **o DSN não chega ao plano administrativo**: ele fica capturado numa fábrica
  de adapters construída pelo composition root. A chave HMAC continua vindo do
  `SecretProvider`, nunca do arquivo;
- **erros administrativos são de um conjunto fechado**, com texto fixo por
  categoria, sem `str(exc)`, sem traceback e com `__cause__` e `__context__`
  nulos. Um erro do PostgreSQL na verificação do candidato vira
  `CONFIG_RELOAD_ERROR`, como no plano MCP;
- **`admin/` não importa `logging`** e não escreve em `stdout`, que continua
  sendo exclusivamente o canal do protocolo MCP.

O que ainda não existe, e não deve ser presumido: autenticação, bind em
loopback, anti-CSRF, limites de corpo, rotas, `config:validate`, adoção com
backup e `AdminAudit`.

## Proteção contra alias

Desde a Fase 3 o `origin_name` é resolvido a partir da metadata do próprio
PostgreSQL — `ftable`/`ftablecol` do result set, cruzados com o catálogo.
Nunca a partir dos valores das linhas, e nunca por parsing textual da SQL.

Cobertos pela proveniência: alias, alias em subquery, alias em CTE, alias sobre
JOIN, alias sobre cast, alias sobre view, `SELECT *` e nomes duplicados.

Onde o PostgreSQL **não** informa origem — expressões, agregados, literais e
UNION — entra a **análise de sensitividade por AST** (D-043), que identifica de
quais colunas a expressão depende e aplica a regra delas ao resultado:

- expressão que depende de uma regra sensível → **mascarada**, inclusive as
  formas reversíveis (`reverse`, base64, hex)
- UNION: um ramo sensível torna a posição inteira sensível → **mascarada**
- duas regras diferentes na mesma posição → **consulta rejeitada**
- serialização de linha inteira (`row_to_json`) → **consulta rejeitada** (D-044)

Além disso, um **alias não pode criar exception** (D-042): exceptions respondem
pelo nome autoritativo — `origin_name` quando existe.

Permanece descoberto: view que renomeia coluna sensível (F-03), porque a
definição da view não está na árvore da consulta. Ver `docs/SECURITY-REVIEW.md`.

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

```text
DERIVED (a AST provou dependência sensível)  -> TRANSFORMER
EXCEPTION (pelo nome AUTORITATIVO)           -> ORIGINAL
MASKING (por output_name OU origin_name)     -> TRANSFORMER
NO MATCH                                     -> ORIGINAL
```

Duas precisões da Fase 6.1:

- **O nome autoritativo** de uma exception é `origin_name` quando ele existe, e
  `output_name` só quando não há origem. Um alias não converte coluna sensível
  em exceção (D-042).
- **A análise de AST vem antes de tudo.** Quando ela prova que a posição
  depende de coluna sensível — expressão, agregado, ramo de UNION — a regra
  dessa coluna se aplica ao resultado (D-043).

## Resultado do red team (Fases 6 e 6.1)

`docs/SECURITY-REVIEW.md` traz o relatório completo: 11 findings, **seis
corrigidos**, cinco aceitos com teste que fixa o comportamento.

Fechados na Fase 6.1: expressão sobre coluna sensível, UNION com alias, alias
para o nome de uma exception, e o hazard H-1.

**Antes de expor este Gateway, entenda que:**

- a role do Gateway **precisa ter `EXECUTE` revogado** nas funções de usuário —
  `EXECUTE` é concedido a `PUBLIC` por padrão, e uma função pré-existente que
  leia coluna sensível devolve o valor sob o nome dela.
- o oráculo por predicado reconstrói um CPF em 11 consultas, e está fora do
  escopo do MVP.
- uma view que renomeia coluna sensível continua expondo o valor.

Com o `EXECUTE` revogado e o oráculo aceito: uso interno com cliente
semi-confiável. Não adequado a exposição externa — não há autenticação e o
transporte é stdio.

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
