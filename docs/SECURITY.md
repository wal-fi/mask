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

## Fronteira HTTP administrativa (Etapa 7)

A Etapa 7 abriu a **primeira porta de rede do projeto**. Ela é opcional,
desligada por default, e cercada. O que vale:

- **desligada por default.** Sem `MASKGW_ADMIN_ENABLED=1` o processo é
  exatamente o de antes: nenhuma porta, nenhuma thread, nenhum lock de arquivo
  e nenhum caminho de escrita. Qualquer outro valor da variável — `0`, `true`,
  `yes` — **não** habilita, e isso é literal e é teste;
- **somente loopback.** `MASKGW_ADMIN_BIND` aceita `127.0.0.1`, `::1` e
  `localhost`, e nada mais. Bind externo **impede o startup**, e não existe
  variável de escape: sem TLS, uma interface externa poria o bearer token em
  HTTP claro, em todo request. Bind externo é Fase 9;
- **um token estático, só por header.** `MASKGW_ADMIN_TOKEN`, mínimo de 32
  caracteres como a chave HMAC (D-006), nunca no `masking.yaml` e nunca em
  argumento de linha de comando. Aceito exclusivamente em
  `Authorization: Bearer`; **nunca** por query string nem por cookie — a
  primeira vaza em log de proxy, em histórico e em `Referer`, e a segunda é o
  que torna CSRF possível. Comparação por `hmac.compare_digest`, em tempo
  constante. Token ausente, malformado e errado produzem o **mesmo** `401`,
  com o mesmo corpo;
- **anti-CSRF em quatro camadas** (§3.3): token em header customizado;
  `Origin` ou `Referer` presentes → `403`, recusado pela **presença** e não pelo
  valor; `Content-Type` diferente de `application/json` em método com corpo →
  `415`; `Host` fora de `127.0.0.1:<porta>`, `localhost:<porta>` e
  `[::1]:<porta>` → `400`, que fecha DNS rebinding;
- **autenticação antes do schema.** Sem credencial válida nunca ocorre um
  `422`: um `422` que chegasse antes do `401` transformaria o schema num
  oráculo para quem não tem token;
- **corpo limitado a 1 MiB**, com ou sem `Content-Length`. Um envio chunked de
  vários MiB é cortado contando os bytes no `receive` cru, sem bufferizar, e o
  chunk que estoura o limite não é repassado adiante;
- **nenhum header CORS, em nenhuma resposta.** Não há middleware de CORS,
  `OPTIONS` não é registrado, e a camada externa **apaga** qualquer header CORS
  que escape. Um `Access-Control-Allow-Origin` num plano administrativo
  deixaria qualquer página aberta no navegador do administrador ler a
  configuração;
- **`Cache-Control: no-store` em toda resposta**, inclusive `401`, `403`,
  `404`, `405`, `413`, `415`, `422` e `500`;
- **nenhuma rota implícita.** O conjunto de rotas é comparado por teste com a
  lista literal da especificação. `/docs`, `/redoc` e `/openapi.json` são
  desligados na construção — entregariam a superfície inteira a um chamador não
  autenticado. `redirect_slashes` é desligado: `/rules/` é `404`, nunca `307`;
- **a Admin API não executa SQL** (D-049), e nesta etapa **não escreve nada**:
  as oito rotas são `GET`/`HEAD`;
- **secrets só como `configured`/`missing`.** Nunca o valor, e nunca um
  derivado — tamanho, prefixo, sufixo, hash ou data. O tipo do campo não admite
  um terceiro valor;
- **erro sempre da mesma forma**, com categoria de conjunto fechado e texto
  fixo. Nunca `str(exc)`, traceback, `repr` arbitrário, o `input` rejeitado ou
  cadeia de exceção. O `422` lista **caminhos de campo** e reason codes
  fechados, jamais valores — o handler default do FastAPI inclui o `input` que
  falhou, e por isso é substituído;
- **nenhuma exceção chega ao servidor.** A camada mais externa contém tudo:
  sem ela o `ServerErrorMiddleware` do Starlette responde e **relevanta**, e o
  uvicorn registraria o traceback com `exc_info` (D-056);
- **`stdout` permanece do MCP.** uvicorn sobe sem handlers default e sem access
  log; `admin/` não importa `logging` e não referencia `sys.stdout`. Uma sessão
  MCP real, com a Admin API sob carga, não vê byte estranho — verificado em
  subprocesso, contra PostgreSQL real;
- **o startup confirma o bind antes de o MCP existir**, e o shutdown faz `join`
  da thread HTTP **antes** de fechar os runtimes, liberando o lock por último.
  O `join` **não tem timeout**: `stop()` espera até a thread terminar, e só
  então os runtimes fecham e o lock sai. Com a thread viva, uma requisição
  administrativa pode estar tocando o registry, e nem abandoná-la nem devolver
  o controle com o shutdown pela metade seriam aceitáveis. O uvicorn recebe
  `timeout_graceful_shutdown`, então o que é limitado é o trabalho, não a
  espera. A referência do servidor é adotada antes de `start()`, e `_closing`
  impede `run()` sobre uma aplicação em desmontagem (D-057);
- **cada resposta administrativa nasce de UMA leitura do runtime publicado**
  (D-057): revision, documento e política vêm do mesmo snapshot, e `adopted` sai
  da revision capturada. Não é só higiene de leitura — a Etapa 9 aceita
  `expected_revision`, e essa proteção só vale se a revision que o administrador
  leu descrever o conteúdo que ele leu. Com o par misturado, uma escrita passaria
  pelo controle de concorrência e sobrescreveria em silêncio a mudança de outra
  pessoa.

- **`config:validate` valida sem tocar em nada** (Etapa 8, D-058): a rota compila
  o documento candidato — inclusive os transformers e a policy, usando o
  `SecretProvider` atual — e descarta o resultado. Não conecta, não persiste, não
  altera revision, não entra na seção crítica. A ausência de efeito é propriedade
  da assinatura de `validate_candidate`, provada por contadores estruturais. Os
  erros são sanitizados.

- **As onze rotas de escrita são só uma tradução para a seção crítica** (Etapa 9,
  D-059): cada handler valida o corpo, constrói um `ConfigMutation` e chama
  `AdminConfigService.apply()`. Nenhuma delas replica lock, `expected_revision`,
  digest, compilação, conexão, persistência ou swap; a mutação roda **dentro** do
  lock, sobre a cópia profunda do documento corrente — não há `snapshot()` antes
  da escrita para decidir a mutação, e portanto não há janela TOCTOU. Os handlers
  são `async def` sem `to_thread`: uma escrita não sobrevive ao graceful shutdown.
  As proteções estruturais permanecem inalcançáveis pela escrita —
  `allowed_pg_functions` no corpo é `IMMUTABLE_FIELD` (§11.3, D-050), e não há rota
  que edite `denied_relations`, o validator, a sessão read-only ou o default
  ALLOW. A adoção grava um backup byte a byte dos bytes originais com `O_EXCL` e
  `0600`, dentro da seção crítica, e recusa colisão sem sobrescrever nada. Os
  erros da mutação — `NOT_FOUND`, `IMMUTABLE_FIELD`, `CONFIG_INVALID` — chegam com
  categoria fechada, sem citar o ID pedido, o campo recusado, o valor nem a causa.

O que ainda não existe, e não deve ser presumido: `AdminAudit` (Etapa 10) e a
suíte adversarial geral (Etapa 11).

**Isto não muda a conclusão de exposição.** A Admin API é loopback, sem TLS, com
um token estático e um único papel. Ela não torna o Gateway adequado a
exposição externa; o transporte de dados continua stdio, e o `EXECUTE` revogado
(F-04) continua sendo pré-requisito.

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
