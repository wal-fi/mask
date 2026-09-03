# Test Plan

Toda funcionalidade nova deve possuir testes. Nenhuma fase é concluída com
teste falhando. Critérios de aceite por fase estão em `docs/ROADMAP.md`.

Estado medido ao final da Etapa 5 da Fase 7, com PostgreSQL real: **1418
passed, 8 skips condicionais de plataforma** entre 1426 coletados; **408
passed, 1018 deselected** com `-m integration`. Dos 408 marcados como
integração, 405 dependiam de `MASKGW_TEST_DSN`; todos executaram e nenhum teste
foi pulado por ausência de DSN.

Estado medido ao final da Etapa 6, com PostgreSQL 16.15 real: **1494
coletados, 1485 passed e 9 skips condicionais de plataforma** — a suíte
inteira, sem nenhum deselect e sem skip por ausência de `MASKGW_TEST_DSN`. Com
`-m integration`, **410 passed e 0 skipped**. A Etapa 6 acrescentou 68 testes,
dois deles marcados `integration` — o reload contra banco real —, e os dois
executam.

Estado medido ao final da Etapa 8, contra PostgreSQL 16.15 real: **1995
coletados, 1986 passed e os mesmos 9 skips condicionais de plataforma** — sem
nenhum deselect e sem skip por ausência de DSN. Com `-m integration`, **415
passed e 0 skipped**. A Etapa 8 acrescentou 80 testes de `config:validate` — 61
na primeira entrega e mais 19 na correção de D-058 (adotado sem ID como
`SCHEMA_INVALID` e escalares estritos); a Etapa 7 havia acrescentado 406, cinco
deles marcados `integration` — a coexistência dos dois planos num processo real,
que continua verde com a rota nova ativa.

**Como rodar neste host Windows.** `test_large_query_payload_does_not_crash`,
da Fase 6, monta uma consulta com 100.000 termos e estoura a pilha da thread na
análise recursiva da AST, derrubando o interpretador. Rode o pytest com a pilha
de thread ampliada — 64 MiB bastou:

```bash
.venv/Scripts/python.exe -c "import threading, pytest; threading.stack_size(64 * 1024 * 1024); raise SystemExit(pytest.main(['-q']))"
```

Isso é ajuste do **ambiente de teste**, não do produto: nenhuma correção foi
feita e o Gateway continua sem limite de tamanho de consulta. A limitação está
em `docs/HANDOFF.md` seção 11 e em `docs/SECURITY-REVIEW.md`. O teste não foi
transformado em `skip` nem alterado, porque um limite conhecido vira teste que
o afirma (D-041).

## Config Loader (Fase 1)

Deve **impedir a inicialização**:
- YAML malformado
- transformer inexistente
- `mode` inválido
- regex inválida
- parâmetro obrigatório ausente (`value`, `pattern`, `length`)
- regra com `hmac_sha256` sem chave disponível no ambiente
- chave HMAC declarada dentro do `masking.yaml`

Deve carregar com sucesso o `config/masking.yaml` do repositório.

## Matching (Fase 1)

Regra `cpf` deve casar:
- cpf
- CPF
- Cpf
- cPf
- num_cpf
- cod_cpf
- cliente_cpf
- cpf_cliente
- nr_cpf

Modo `exact` deve casar apenas o nome exato, case-insensitive.

Matching com `origin_name = None` usa somente `output_name`.

## Exceptions (Fase 1)

Regra: `cpf → md5`
Exception: `tipo_cpf` (exact)

Esperado:
- cpf → masked
- num_cpf → masked
- tipo_cpf → original

Exception casando por `origin_name` também tem prioridade.

## Default ALLOW (Fase 1)

Coluna que não casa nenhuma regra retorna o valor original.

## Transformers (Fase 1)

Cada transformer deve testar:
- entrada normal
- NULL
- string vazia
- Unicode
- valores grandes
- valores inválidos quando aplicável

Além disso:
- determinismo de md5, sha256, sha512, hmac_sha256, regex, fixed e truncate
- não-determinismo de random
- hmac_sha256 com chaves diferentes produz saídas diferentes

## Database (Fase 2)

Testar:
- SELECT cpf
- SELECT *
- SELECT cpf, email
- JOIN
- UNION
- CTE
- subquery
- view
- NULL vindo do banco

Implementado em duas camadas:

- **sem banco** (`test_db_columns`, `test_db_masking`, `test_db_errors`,
  `test_db_leakage`), com dublês de conexao e cursor — roda em qualquer
  maquina e mantem a suite verde sem PostgreSQL;
- **com PostgreSQL real** (`test_db_integration`), marcado `integration` e
  pulado com SKIP limpo quando `MASKGW_TEST_DSN` nao esta definida.

O DSN vem exclusivamente do ambiente. Nenhum usuario, senha ou host aparece no
codigo ou nos testes.

Alem dos itens acima, a Fase 2 cobre:

- canonicalizacao deterministica por tipo e falha fechada em tipo nao
  suportado (`test_canonical`, D-015)
- preservacao do objeto Python nas colunas sem transformacao
- nomes de coluna duplicados, que nao podem ser colapsados
- leitura em lotes: o resultado nao muda com o tamanho do lote
- estado transacional observado de fora, por `pg_stat_activity` (D-016)
- ausencia de `__cause__` e `__context__` no erro sanitizado (D-017)
- superficie publica de `db/` sem cursor, fetch cru ou acessor de original

### Lacuna da Fase 2, fixada em teste

`SELECT cpf AS documento` passa **em claro**, porque nao ha lineage. Coberto
por `TestPhaseTwoAliasGap`, nas duas camadas. Esses testes serao **invertidos**
na Fase 3.

## Provenance / alias (Fase 3)

- `SELECT cpf AS documento` → masked
- alias em JOIN, subquery, CTE e view → masked
- `SELECT md5(cpf)` → `origin_name is None`, sem erro no pipeline
- teste que mede o que o PostgreSQL devolve em `ftable` por cenário

Implementado em três camadas:

- **medição** (`test_pgresult_metadata`) — não testa código do Gateway. Mede o
  que o PostgreSQL e o psycopg devolvem em `cursor.pgresult.ftable(i)` e
  `ftablecol(i)`, cenário a cenário, e fixa o resultado. Foi escrito **antes**
  da implementação: o resolver segue o que foi medido, não a documentação
  anterior — que estava errada sobre onde esses campos vivem.
- **sem banco** (`test_db_provenance`) — classificação, cache, alinhamento
  posicional e comportamento quando o catálogo falha.
- **com PostgreSQL real** (`test_db_integration`) — os quinze cenários
  obrigatórios ponta a ponta, com a política aplicada.

Ressalva sobre UNION: o PostgreSQL **não** preserva proveniência em UNION
(`ftable = 0`), então o critério original do roadmap ("alias em UNION → masked")
não é alcançável **por metadata**.

Isso foi resolvido na Fase 6.1 por outro caminho: a análise de AST (D-043)
avalia cada posição em todos os ramos, e um ramo sensível torna a posição
inteira sensível. `SELECT cpf AS documento FROM a UNION ALL SELECT 'x'` sai
mascarado; classes sensíveis conflitantes na mesma posição são rejeitadas.
Coberto por `tests/security/test_attack_union_views.py` e
`tests/test_sensitivity.py`.

### Testes invertidos

`TestPhaseTwoAliasGap`, que na Fase 2 fixava `SELECT cpf AS documento` passando
em claro, virou `TestAliasProtection` nas duas camadas. O valor agora sai
transformado pela regra `cpf`.

## Security (Fase 4)

Verificar bloqueio de:
- INSERT
- UPDATE
- DELETE
- MERGE
- DROP
- ALTER
- TRUNCATE
- CREATE
- GRANT
- REVOKE
- COPY, CALL, DO, VACUUM, ANALYZE, REFRESH, SET, RESET
- CTE modificadora de dados, inclusive aninhada e dentro de subquery
- múltiplos statements
- `SELECT ... INTO` e `SELECT ... FOR UPDATE`
- funções perigosas, com schema explícito e com variação de caixa

Verificar:
- `statement_timeout` interrompe consulta longa
- limite de linhas trunca a resposta e sinaliza truncamento
- escrita que passe pelo validator ainda falha pelo privilégio da role

Implementado em três camadas:

- **medição** (`test_sql_parser`) — o que o pglast considera um statement
  executável. `SELECT 1;;` é um; `;` é nenhum. O critério do validator segue o
  que foi medido, nunca a contagem de `;`.
- **adversarial sem banco** (`test_sql_validator`) — todos os cenários acima,
  mais as garantias de que nenhuma mensagem cita a consulta.
- **com PostgreSQL real** (`test_execution_safety`) — read-only, timeout, row
  limit e capability check.

### Defesa em profundidade

`TestReadOnlyIsEnforcedByPostgres` chama `execute`, a porta **sem validação**,
de propósito. Se o PostgreSQL não barrasse, as escritas aconteceriam e a suíte
acusaria. Um teste de controle confere, por uma segunda conexão, que a tabela
continua com as 50 linhas depois de todas as tentativas.

### Capability check de proveniência

Testado com uma role real sem `SELECT` em `pg_attribute`: `check_provenance_
capability` levanta `CapabilityError`, e um teste seguinte confirma que o acesso
ao catálogo foi restaurado.

## Leakage (todas as fases)

Verificar que o valor original não aparece:
- na resposta
- nos logs
- nas exceções
- no stack trace retornado
- na mensagem de erro do PostgreSQL repassada ao cliente

Verificar que a chave HMAC não aparece em log, erro ou resposta.

## Riscos aceitos (Fase 6)

Testes que **documentam o comportamento atual**, para que uma mudança futura
seja percebida. Implementados em `tests/security/`, 209 testes organizados por
classe de ataque:

```text
tests/security/
  conftest.py                        schema, dados fictícios, política
  test_attack_expressions.py         expressões sobre coluna sensível
  test_attack_union_views.py         UNION e views
  test_attack_functions_catalog.py   funções de usuário e catálogo
  test_attack_oracle_errors.py       inferência por predicado e erro
  test_attack_protocol.py            nomes hostis, exceptions, serialização,
                                     segredos, MCP, concorrência, row limit,
                                     perda de capability
```

Cada teste declara o veredito: **BLOCKED**, **MASKED** ou **KNOWN LIMITATION**.
Um KNOWN LIMITATION **afirma que o ataque funciona** — nunca vira `skip`, para
que o inventário de riscos fique executável e para que uma correção futura
quebre o teste e seja notada (D-041).

Findings e severidades em `docs/SECURITY-REVIEW.md`.

## MCP e Gateway (Fase 5)

Todos os testes de protocolo passam pelo cliente in-memory do SDK
(`mcp.Client(server)`), nunca chamando a função Python decorada diretamente.

- `tools/list` encontra `query_database` e nada mais
- o `input_schema` tem exatamente `sql`, e nenhum dos doze nomes de controle
- o `output_schema` não menciona provenance
- consulta simples, com CPF, com alias, `SELECT *`, JOIN, nomes duplicados,
  NULL, Unicode, resultado truncado, resultado vazio
- SQL inválida, INSERT, `SELECT INTO`, multi-statement, CTE modificadora,
  função proibida, `SET`, erro do PostgreSQL, timeout
- argumento extra não muda o resultado, e não chega ao Gateway

### O teste fundamental

`TestTheFundamentalSecurityTest`, contra PostgreSQL real, com
`nome = "Joao"`, `cpf = "11122233344"`, `email = "joao@example.com"`:

- `nome` passa original
- `cpf` sai transformado por `hmac_sha256`
- `email` segue o transformer `regex` configurado
- o CPF original não aparece no structured output, no conteúdo textual, no
  `model_dump()`, no `repr`, nos logs, na exceção nem no traceback — inclusive
  quando a consulta **falha** com o CPF no predicado

### Auditoria

- `QueryAudit` não tem parâmetro para SQL, valores, DSN ou segredo: passar um
  levanta `TypeError`
- nenhum registro contém o CPF, o nome ou a palavra `SELECT`
- `audit/log.py` é o único arquivo de `src/` que importa `logging`

## Sensitividade por AST (Fase 6.1)

`tests/test_sensitivity.py`, 54 testes sem banco, sobre `sql/sensitivity.py`:

- dependência direta encontrada em expressão, agregado, cast, subquery escalar
  e referência qualificada
- **sem falso positivo**: `upper(nome)`, `count(*)`, literais e
  `substr(tipo_cpf, 1, 3)` continuam sem regra
- UNION: qualquer ramo sensível torna a posição sensível; posições
  independentes entre si
- ambiguidade entre duas regras → `QueryRejected`, e o motivo não cita coluna
- `row_to_json(c)` → `QueryRejected`; `c.cpf` qualificado não é confundido
- nomes exportados por CTE e subquery resolvidos, sem over-masking do inocente
- limites: `SELECT *` não mapeia posição; 200 níveis aninhados em menos de 2 s;
  além de 16 níveis a análise desiste em vez de adivinhar

### Custo

Dois testes garantem que a análise é **por consulta, nunca por linha**: um com
10.000 linhas comparando o custo contra uma única linha, e um contador de
chamadas ao analisador que exige exatamente 1 por query.

## Fase 7 — Etapas 1–6 concluídas

Commits de referência:

- Etapa 1: `053cf66` — IDs e revision no modelo do arquivo;
- Etapa 2: `3114c14` — `RuntimeRegistry`;
- Etapa 3: `3c8de4c` — aquisição/liberação de runtime por query;
- Etapa 4: `7c06132` — composition root e lifecycle;
- Etapa 5: `d651fe0` — filesystem seguro;
- Etapa 6: seção crítica administrativa e fluxo de escrita/reload — o commit
  que introduziu `src/maskgw/admin/`.

A sincronização com `origin/master` deve ser conferida pelo Git, não inferida
deste documento.

### Etapa 1 — IDs e revision

`tests/test_config_ids.py` cobre geração/migração de IDs, estabilidade, ordem e
validação. Configuração com `revision >= 1` e qualquer rule ou exception sem
`id` falha no carregamento. `LoadedConfig` preserva juntos o modelo validado do
arquivo e os objetos runtime compilados.

### Etapa 2 — RuntimeRegistry

`tests/test_runtime_registry.py` cobre acquire/release, aposentadoria, limite de
runtimes aposentados, concorrência, shutdown idempotente e fechamento único do
último runtime.

### Etapa 3 — Gateway por runtime

`tests/test_gateway_runtime.py` comprova que cada query adquire e libera um
runtime, inclusive em erro, e que o comportamento de query, masking e auditoria
permanece inalterado.

### Etapa 4 — Composition root e lifecycle

`tests/test_bootstrap.py` e `tests/test_plan_separation.py` cobrem:

- `bootstrap/` como único composition root autorizado a conhecer MCP e o futuro
  plano administrativo;
- ausência atual de `admin/` e FastAPI;
- remoção de `gateway/factory.py`;
- compatibilidade de `python -m maskgw` e `python -m maskgw.mcp`, ambos
  delegando ao bootstrap com transporte MCP stdio;
- startup e shutdown ordenados, shutdown idempotente e runtimes fechados uma
  única vez;
- falha parcial de startup fechando todos os recursos já construídos;
- nenhum byte não protocolar em `stdout`;
- ausência de DSN, secret, SQL, valor ou traceback nos erros e logs da
  aplicação;
- nenhuma thread daemon ou recurso abandonado.

### Etapa 5 — Filesystem seguro

`tests/test_config_filesystem.py` acrescenta 32 verificações e cobre:

- arquivo, diretório pai e sidecar sem symlink ou tipo inseguro;
- permissões POSIX, criação privada e limitação explícita de ACL/modo no
  Windows;
- lock não bloqueante entre dois processos reais e liberação em falha parcial;
- digest SHA-256 dos bytes exatos e `CONFIG_OUT_OF_SYNC` nas duas verificações;
- temporário no mesmo diretório, `O_EXCL`, modo `0600`, flush e `fsync`;
- visibilidade concorrente apenas do arquivo antigo ou novo, nunca parcial;
- falhas distintas antes do `replace` e no `fsync` posterior do diretório;
- omissão explícita do `fsync` de diretório no Windows;
- limpeza estrita de órfãos, sem seguir ou remover symlink/tipo alheio;
- `repr` e erros sem caminho sensível, configuração, DSN, SQL, valor ou
  traceback.

### Etapa 6 — Seção crítica administrativa e escrita/reload

`tests/test_admin_service.py` acrescenta 58 testes e cobre:

- **§12.1, concorrência.** N escritas paralelas com o mesmo
  `expected_revision`: exatamente uma vence, as demais recebem
  `REVISION_CONFLICT` com `current_revision` correto, a revision final é
  inicial + 1, o arquivo contém só a mudança vencedora e **nenhum perdedor
  construiu candidato**. Escritas concorrentes diferentes, com um leitor
  paralelo: todo documento lido é válido e vem de uma única operação. Escrita
  concorrente com queries em voo: nenhuma query falha e nenhum adapter é
  fechado enquanto a referência está adquirida.
- **§7.4, passos 1 a 4.** Conflito de revision, escrita antes da adoção, adoção
  sobre configuração já adotada, adoção a partir de `expected_revision != 0`,
  edição externa antes da operação e `RELOAD_BUSY` — este último **provado por
  contador**: nenhum candidato construído e nenhuma conexão aberta. A ordem
  entre os passos é observável: a revision é conferida antes do limite de
  aposentados.
- **§12.4, falhas antes do `os.replace`.** Mutação que levanta, documento
  inválido, transformer inexistente, `regex` de padrão inválido, construção do
  adapter, conexão, colisão de `O_EXCL` do temporário, `fsync` do temporário,
  `replace`, arquivo ilegível e a corrida real de digest entre a primeira
  verificação e o `replace`. Para cada uma: bytes do arquivo idênticos, runtime
  publicado é o **mesmo objeto**, digest de referência inalterado, candidato
  fechado **exatamente uma vez**, categoria correta, sem `applied`, `__cause__`
  e `__context__` nulos.
- **§7.6, depois do `replace`.** O runtime novo é publicado, o digest e a
  revision são atualizados, a resposta é `CONFIG_DURABILITY_ERROR` com
  `applied=true` e `current_revision` nova, e uma retentativa cega recebe
  `409 REVISION_CONFLICT` sem sobrescrever nada. A falha real de `fsync` de
  diretório é exercitada no POSIX; no Windows a **omissão é afirmada**, nunca
  simulada como sucesso; e um duble de store cobre a semântica de
  depois-do-`replace` nas duas plataformas.
- **Swap e ciclo de vida.** Runtime novo por inteiro, o antigo inalterado,
  query em voo terminando com o antigo, query nova já com o novo, aposentado
  fechado uma única vez, 15 reloads sem vazar adapter, e o digest de referência
  igual ao SHA-256 dos bytes em disco — que reproduzem exatamente o documento
  publicado.
- **Vazamento.** Texto e `repr` fixos por categoria para todas as categorias;
  falha cujo erro interno carrega DSN, SQL e valor não os propaga; `repr` do
  serviço sem caminho, digest ou colaborador; `stdout`, `stderr` e `logging`
  vazios em sucesso e em falha.
- **Isolamento do runtime publicado contra a mutação** (11 testes,
  regressão de um finding P1). Uma mutação hostil esvazia `masking`,
  `exceptions` ou `sql.allowed_pg_functions`, ou reescreve o `config` aninhado
  de uma regra, e então falha — em dois pontos distintos do fluxo: antes de
  qualquer candidato existir, e com o candidato já construído. Em ambos: bytes
  do arquivo idênticos, `registry.current` é o **mesmo objeto**, o documento e
  os objetos compilados do runtime continuam campo a campo intactos, revisão e
  digest inalterados, e o candidato ou não é criado ou é fechado exatamente uma
  vez. Uma escrita válida e sem relação, executada depois da falha, não
  persiste resíduo algum e não desliga o masking. Mutar o objeto devolvido por
  `service.document` também não alcança o runtime. Os onze testes **falhavam**
  contra o código anterior à correção.
- **Contra PostgreSQL real** (`integration`, 2 testes): reload publicando a
  política nova sem restart, com o arquivo, o runtime e o digest concordando, e
  o número de sessões do banco não crescendo; e um candidato inválido deixando
  o runtime publicado servindo queries.

`tests/test_bootstrap.py` acrescenta a composição do admin plane: admin
desabilitado é o processo de hoje e não cria sequer o arquivo de lock; admin
habilitado prende o lock exclusivo contra um segundo `ConfigFileStore` e expõe
o digest dos bytes que originaram o runtime; o shutdown libera o lock **depois**
de fechar os runtimes, uma única vez; falha parcial de startup libera lock e
conexão; e nenhuma thread é criada, porque a Etapa 6 não abre porta.

`tests/test_plan_separation.py` deixa de valer por vacuidade: o pacote `admin/`
existe, não importa `maskgw.mcp` nem `maskgw.gateway`, não importa `logging`,
não tem superfície HTTP nesta etapa, e só `bootstrap/application.py` importa os
dois planos.

### Etapa 7 — Fronteira HTTP e rotas de leitura

Oito arquivos novos, **406 testes**, e a suíte passa de 1494 para 1915
coletados.

```text
tests/admin_http_support.py            apoio: cliente HTTP cru + serviço real
tests/test_admin_http_settings.py   51 enable, token, bind e porta
tests/test_admin_http_boundary.py   88 as camadas, sobre uma app ASGI interna
tests/test_admin_http_surface.py   108 conjunto literal de rotas e métodos
tests/test_admin_http_reads.py      64 o conteúdo das oito rotas
tests/test_admin_http_lifecycle.py  44 bind real, porta ocupada, shutdown
tests/test_admin_http_snapshot.py   26 coerência do snapshot sob reload (D-057)
tests/test_admin_http_leakage.py    20 vazamento em sucesso e em erro
tests/test_admin_http_mcp_coexistence.py 5 os dois planos, em processo real
```

**Por que um cliente por socket, e não um TestClient.** Metade do que a etapa
precisa provar não passa por um cliente educado: um `Host` alheio, um corpo
`chunked` de vários MiB **sem** `Content-Length`, um `HEAD` cujo corpo precisa
vir literalmente vazio no fio, e um token em query string que precisa ser
ignorado. `http.client` com `skip_host=True` deixa cada header sob controle.

**Por que uma app ASGI interna.** Nenhuma rota desta etapa tem corpo, então o
limite de 1 MiB e a exigência de `Content-Type` **não são alcançáveis por
endpoint de produção**. Registrar um só para provocá-los criaria superfície que
a especificação não pede — e o teste de conjunto literal passaria a proteger uma
rota inventada pelo próprio teste. Os middlewares são exercitados sobre uma app
que existe só dentro do arquivo de teste.

O que os 371 cobrem:

- **§12.7, superfície.** O conjunto de rotas registradas é comparado com a
  lista literal da §1.1 — oito caminhos, `{GET, HEAD}` cada um. `/query`,
  `/sql`, `/execute`, `/config:reload`, `/docs`, `/openapi.json`, `/redoc` e as
  rotas das Etapas 8–10 são `404`. `OPTIONS` responde `405` sem header CORS.
  `HEAD` exige autenticação, devolve o mesmo status e corpo vazio. `/rules/`
  é `404`, nunca `307`, e nenhuma resposta carrega `Location`.
- **§2, autenticação.** Ausente, malformado e errado dão o **mesmo** `401`, com
  o mesmo corpo. Token em query string (quatro formas) e em cookie (três
  formas) é recusado. O `401` chega **antes** de qualquer `422`. Um teste lê o
  fonte e afirma o uso de `hmac.compare_digest`.
- **§3.3, anti-CSRF.** `Origin` e `Referer` recusados pela **presença**,
  inclusive quando o valor aponta para o próprio servidor. Sete formas de
  `Host` alheio, incluindo `127.0.0.1.evil.example` e `127.0.0.1:<outra porta>`.
  `Content-Type` exigido só em método com corpo.
- **Limite de corpo.** `Content-Length` acima do limite falha **antes de ler**,
  provado por contador na app de baixo. Chunked de 8 MiB é cortado com `413`, e
  o que chegou embaixo é `<= 1 MiB` — que é a propriedade de memória, medida
  também com `tracemalloc`. E o servidor continua atendendo depois do corte.
- **Ordem entre camadas.** `Host` e `Origin` vencem a ausência de token; o
  `401` vence o `415`; o `413` por `Content-Length` vence o `401`.
- **Headers.** `Cache-Control: no-store` numa amostra que cobre 200, 400, 401,
  403, 404, 405, 413 e 415 — e o teste **afirma que a amostra cobre esses oito
  status**, para não passar por vacuidade. Nenhum header CORS, nem `Server`.
- **§12.6, vazamento.** Token, chave HMAC, DSN e suas partes, valor de dado, SQL
  e caminho do arquivo não aparecem em corpo, header ou `repr` — em sucesso
  **e** em todos os caminhos de erro. Nem prefixo, nem sufixo, nem MD5/SHA-1/
  SHA-256 do segredo. Uma app que levanta com DSN, SQL e valor na mensagem vira
  `INTERNAL_ERROR` sem nada da original, sem traceback e sem derrubar a thread.
- **§10.3, handlers.** `RequestValidationError` é exercitado sobre uma app de
  teste — nenhuma rota desta etapa o alcança —, e o valor rejeitado **nunca**
  aparece no corpo. Todo reason code pertence ao conjunto fechado.
- **§1.1, conteúdo.** Os oito payloads, com `adopted: false` e IDs nulos numa
  configuração não adotada, sem inventar IDs. Contadores acompanhando
  aquisições e aposentados. O catálogo de transformers é **confrontado com o
  comportamento real dos builders** — omitir um obrigatório falha, um parâmetro
  fora do declarado é recusado —, para que a declaração não vire documentação
  falsa. `/protected` mostra `denied_relations`, as quatro regras do validator,
  o deny-by-default de `pg_`, `allowed_pg_functions` como leitura, e afirma
  `editable: false`.
- **Cópia defensiva.** Esvaziar `masking`, `exceptions` e
  `sql.allowed_pg_functions` do documento devolvido **não** alcança o runtime, e
  a resposta HTTP seguinte continua completa (D-055).
- **Coerência do snapshot** (D-057, 26 testes). Um `RuntimeRegistry` de teste
  troca o runtime publicado **a cada leitura** de `current`, o que torna o swap
  determinístico em vez de uma corrida. O arquivo abre com a **contraprova**: o
  padrão antigo — `service.document` e depois `service.revision` — devolve, ali,
  o documento da revision 3 rotulado como 4, e `adopted` verdadeiro sobre uma
  revision 0. Sem essa contraprova os demais testes poderiam passar por não
  provocarem nada. Sobre esse cenário, cada view e cada rota são verificadas:
  nunca `revision != config.revision`, nunca conteúdo ou política de uma
  revision sob outra, e uma regra removida no reload ou aparece inteira sob a
  revision antiga ou responde `NOT_FOUND`. Há ainda um teste de que o lock do
  registry **não** fica preso durante a cópia profunda, e um de reload contínuo
  numa thread separada, contra leituras HTTP reais.
- **§12.10, lifecycle.** Bind real e porta exposta; porta ocupada falhando
  **sem deixar thread**, com o erro sem host, porta, `errno`, `__cause__` nem
  `__context__`; timeout de confirmação; falha da fábrica de app liberando o
  socket; `stop` idempotente; thread não-daemon; `threading.enumerate` idêntico
  antes e depois. No composition root: a ordem
  `runtime:connected → http:listening → mcp:started → mcp:stopped → http:joined
  → runtime:closed → lock:released` é comparada **elemento a elemento**.
- **Shutdown que não abandona a thread** (D-057). Uma aplicação ASGI segura uma
  requisição até um `Event` ser liberado. `stop()` roda numa **thread
  auxiliar** — chamá-lo direto travaria o teste em vez de reprová-lo — e o que
  se afirma é a sequência: ele **não** retorna enquanto a requisição está presa,
  a thread `maskgw-admin-http` continua viva, e depois da liberação ele conclui
  **sozinho**, sem nova chamada. As referências internas só são soltas nesse
  ponto. Um terceiro caso nunca libera a requisição e prova que o shutdown
  termina mesmo assim, pelo `timeout_graceful_shutdown` do uvicorn: o limite
  está no trabalho, não na espera.
- **Ownership na falha parcial de startup** (D-057). Um duble sobe a thread e só
  então falha, como um timeout de confirmação faria. O composition root precisa
  ter ficado com a referência: o teste afirma `stop_calls == 1` e a ordem
  `runtime:connected → http:stopped → runtime:closed → lock:released`, mais
  `threading.enumerate` idêntico ao inicial e o lock de arquivo liberado. Com a
  atribuição antiga — só após `start()` retornar — `stop_calls` é `0`.
- **Estado durante a desmontagem** (D-057). Um duble inspeciona a aplicação de
  **dentro** do `stop()`, a única janela em que o shutdown começou e não
  terminou: `repr()` reporta `closing`, nunca `ready`, e `run()` é recusado ali
  — sondado de outra thread, para que um `run()` indevidamente aceito reprove em
  vez de travar. Um quarto teste prende uma requisição por mais de 25 s — acima
  dos dois timeouts de 10 s que existiam — e verifica que nada fecha enquanto
  isso, que a liberação conclui tudo na ordem `HTTP → runtime → lock`, e que
  nenhuma thread `maskgw-admin-http` sobra.
- **§12.8, separação.** HTTP confinado a `admin/http/`; `mcp/`, `gateway/` e
  `runtime/` sem dependência de rede; importar `maskgw.admin` **não** carrega
  FastAPI — com contraprova de que importar `maskgw.admin.http` carrega.
  Nenhum `print` em `admin/`, e nenhuma referência a `sys.stdout` em `admin/`
  ou `bootstrap/`.
- **Coexistência, contra PostgreSQL real** (`integration`, 5 testes). Um
  processo de verdade — `python -m maskgw.mcp` com a Admin API habilitada por
  ambiente —, uma sessão MCP real por stdio e, **enquanto ela está aberta**, 75
  requisições administrativas. O enquadramento JSON-RPC é o próprio detector:
  um byte estranho em `stdout` quebraria o parsing. O CPF sai mascarado, o
  `stderr` carrega só as duas linhas fixas de startup — sem access log, sem
  traceback, sem segredo —, o token é exigido também ali, e a porta é liberada
  no encerramento. Com a variável ausente, nenhuma porta é aberta e o arquivo
  de lock não chega a existir.

**Uma armadilha de instrumentação, registrada.** Sob pytest, o access log do
uvicorn **volta a existir**: o `LogCaptureHandler` é anexado deliberadamente a
todo logger com `propagate=False` — inclusive `uvicorn.access` —, e o uvicorn
decide emitir por `hasHandlers()`, avaliado por conexão. Contar registros
capturados provaria o contrário do que se quer. O teste afirma a **configuração**
— sem handler próprio e sem propagação — e a ausência real é verificada onde a
instrumentação não alcança: no subprocesso do teste de coexistência.

### Etapa 8 — `config:validate` (§12.11, D-058)

`tests/test_admin_http_validate.py`, **80 testes**. A rota valida o schema,
compila os transformers e a policy, e descarta o resultado.

- **Sucesso.** Documento mínimo (`{}`) e documento adotado completo → `200` com
  a forma exata `{"valid": true, "schema_validated": true, "policy_compiled":
  true, "database_checks_performed": false}` — nada além dos quatro campos, sem
  `revision`, `applied`, conteúdo normalizado, secret ou `current_revision`.
  `no-store` e ausência de CORS. Cada um dos oito transformers válidos (md5,
  sha256, sha512, hmac_sha256, regex, fixed, truncate, random) compila.
- **Compila, não só valida schema.** Uma regex **válida** passa; a mesma rota com
  regex **inválida** recusa. As duas juntas provam que a regex é de fato
  compilada — uma string qualquer passaria pelo schema.
- **Autenticação e fronteira.** Sem token, token errado, token em query e em
  cookie → `401`; sem token e corpo inválido → `401`, nunca `422`; `text/plain`
  → `415`; JSON malformado → `422 SCHEMA_INVALID` sanitizado; `Origin`/`Referer`
  → `403`; `Host` alheio → `400`; corpo acima de 1 MiB por `Content-Length` e
  **chunked** → `413`. Os demais métodos (GET/HEAD → `405`, PUT/PATCH/DELETE com
  `text/plain` → `415`) não executam a validação.
- **As duas categorias de `422`.** `SCHEMA_INVALID` para `expected_revision`,
  campo desconhecido em qualquer nível, tipo errado, limite inválido, ID ausente
  em documento adotado, ID malformado, exception com transformer. `CONFIG_INVALID`
  para regex inválida, transformer inexistente, parâmetro obrigatório ausente,
  parâmetro desconhecido e HMAC sem chave. Nenhum `SCHEMA_INVALID` carrega o
  valor submetido; nenhum `CONFIG_INVALID` cita a causa. Os testes afirmam a
  **categoria** no corpo, não só o status `422` — as duas classes são `422`, e
  conferir só o status não distinguiria uma da outra.
- **Schema estrito, por regressão (D-058).** "Documento adotado sem ID" é
  `SCHEMA_INVALID`, não `CONFIG_INVALID`, tanto para regra quanto para exception,
  e a recusa acontece no binding: espiões provam que `validate_file_config` e
  `compile_policy` **não são chamados** nesse caso. Os escalares são estritos:
  string numérica (`"1"`) não é aceita como inteiro em `revision`,
  `statement_timeout_ms` e `max_rows`; `0`/`1` não são aceitos como booleano em
  `case_sensitive`; um booleano não é aceito como inteiro. A contraparte fica
  intacta: o enum textual JSON (`"contains"`, `"exact"`) continua aceito, e o
  booleano legítimo passa. Nenhum valor rejeitado aparece na resposta, e cada
  falha continua sem efeito (é mais um caso da parametrização de ausência de
  efeito).
- **Ausência de efeito**, para sucesso e para cada tipo de falha, parametrizado:
  bytes do arquivo idênticos, revision idêntica, `registry.current` é o **mesmo
  objeto**, digest de referência inalterado, `admin_operations_total` e
  `queries_total` inalterados, nenhum adapter novo, o adapter existente sem
  `connect`/`execute`/`close`, nenhuma thread `maskgw-admin-http` a mais. Um
  espião prova que `snapshot()` **nunca é chamado**, e que a seção crítica nunca
  é adquirida (o contador de operações não sobe).
- **Leakage.** Nem HMAC nem partes do DSN aparecem em corpo ou header, em sucesso
  ou erro. Uma exceção **não-`ConfigError`** injetada na compilação vira
  `INTERNAL_ERROR` sem `str(exc)`. O erro sanitizado tem `__cause__` e
  `__context__` nulos (D-017).

**A rota é a primeira com corpo, e expôs uma correção de fronteira** (D-058). O
`BodyLimitMiddleware` sinalizava o excesso levantando uma exceção interna e a
capturava no próprio `__call__` — o que funciona com um app que deixa a exceção
propagar (o `EchoApp` dos testes de fronteira), mas o roteador do FastAPI lê o
corpo dentro de `wrap_app_handling_exceptions`, que captura a exceção antes que
ela volte. O corte passou a ser **autoritativo no `receive`**: o `413` é enviado
ali, o app interno recebe `http.disconnect` e qualquer resposta dele é engolida.
A contraprova mede as duas coisas: sem a correção, o chunked na rota dá `400`; e
sem a rota registrada, a suíte de superfície e a de validação quebram.

As rotas de escrita e a adoção com backup são a Etapa 9; `AdminAudit` é a Etapa
10; a suíte adversarial HTTP é a Etapa 11.
