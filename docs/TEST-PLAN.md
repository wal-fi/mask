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

Estado medido ao final da Etapa 11 (suíte adversarial administrativa; a Fase 7
está concluída), contra PostgreSQL 16 real: **2312 coletados, 2304 passed e 8
skips condicionais de plataforma POSIX** (contagens por JUnit XML) — sem nenhum
deselect e sem skip por ausência de DSN. Com `-m integration`, **558 passed e 3
skips** de 561 selecionados (os três testes POSIX de fsync de diretório, que no
Windows não se aplicam). A Etapa 11 somou **38 testes** de
`test_admin_adversarial.py` (37 executados + 1 skip POSIX de plataforma). A Etapa 10 soma **153 testes**: 77 de unidade
(`test_admin_audit.py`), 39 de fechamento real (`test_admin_audit_closed.py`), 36
de instrumentação HTTP contra PostgreSQL real (`test_admin_http_audit.py`) e 1 de
`stdout` MCP limpo sob auditoria (`test_admin_http_mcp_coexistence.py`). A Etapa 9
somou 129, a Etapa 8, 80 de `config:validate`, e a Etapa 7, 406.

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
- `AdminAudit` (Etapa 10, `tests/test_admin_audit.py`): schema fechado **de
  verdade** — os campos categóricos guardam os enums, não strings —, imutável, com
  slots; `as_fields()` converte os enums para strings JSON-compatíveis, sem objeto
  de enum no `LogRecord`; rejeição construtiva de ~25 parâmetros proibidos
  (`match`, `column`, `config`, `body`, `token`, `secret`, `hmac_key`, `dsn`,
  `sql`, `traceback`, `message`, …); enum completo das doze operações, cinco
  `target_kind`, três `outcome`; **paridade exata** de `AdminErrorCategoryName` com
  `AdminErrorCategory`, de `CATEGORY_OUTCOME` com a faixa de status de
  `STATUS_BY_CATEGORY`, e dos padrões de ID com `config/ids.py` (o teste vive fora
  dos dois módulos, para não fechar o ciclo `audit -> admin`);
  `OPERATION_TARGET_KIND` e `CATEGORY_OUTCOME` são as fontes únicas do mapping e da
  classe de desfecho; `AuditLog.record_admin` best-effort — um logger que levanta
  não sobe e não re-emite nada; `QueryAudit` sem regressão
- `AdminAudit` fechamento real (Etapa 10, `tests/test_admin_audit_closed.py`, as
  contraprovas escritas antes da correção — todas falhavam contra `2ff2d43`):
  `operation="inventada"`, `outcome="talvez"`, `error_category="SEGREDO"`,
  `duration_ms` negativa/booleana, revisão negativa/booleana, `request_id` que não
  é UUID v4, e um **CPF em `target_id`** são todos RECUSADOS na construção, antes de
  chegar ao logger; o mapping operação↔alvo, a exigência de `target_id=None` fora
  de update/delete, e a concordância prefixo↔`target_kind` são impostas por
  `__post_init__`. Duas classes de coerência da 2ª rodada corretiva:
  **outcome↔categoria** (`REJECTED` com categoria 5xx como `INTERNAL_ERROR`, e
  `ERROR` com categoria 4xx como `REVISION_CONFLICT`/`CONFIG_INVALID`, são
  recusados; as combinações corretas passam) e **revisões exatas**
  (sucesso de escrita e `CONFIG_DURABILITY_ERROR` exigem `revision_after ==
  revision_before + 1`; falha não-durabilidade não declara `revision_after`;
  `validate` permanece sem revisões)

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

## Fase 7 — Etapas 1–11 concluídas

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

### Etapa 9 — Rotas de escrita e adoção com backup (§1.3, §5–§7, §12, D-059)

`tests/test_admin_http_writes.py`, **50 testes**, todos `integration` contra
PostgreSQL real — cada escrita compila, conecta e verifica um runtime candidato
de verdade.

- **Sucesso de cada uma das onze rotas.** Create/replace/delete/reorder de regra,
  create/replace/delete de exception, `PUT /database`, `PUT /sql` aditivo,
  `PUT /config` integral e `config:adopt`. Cada uma responde `{revision, applied:
  true}`, o `GET` seguinte reflete exatamente a mudança e a `revision` incrementa
  **uma vez**.
- **Concorrência (§12.1).** Seis requests paralelos com o mesmo
  `expected_revision`: exatamente um `200`, os demais `409 REVISION_CONFLICT`,
  revision final = inicial + 1.
- **Adoção (§5, §12.9).** IDs atribuídos, `revision 0 → 1`, `adopted: true` no
  `GET`; escrita antes da adoção → `CONFIG_NOT_ADOPTED`; `adopt` sem
  `confirm_comment_loss` ou com `false` → `SCHEMA_INVALID`; `expected_revision ≠
  0` → `REVISION_CONFLICT`; **segunda adoção recusada sem efeito** (bytes idênticos,
  IDs iguais, nenhum novo backup); **a adoção não altera nenhuma decisão de
  masking** (veredito do engine idêntico antes e depois sobre regra, exception,
  alias e coluna sem correspondência).
- **Backup (§5.4, §12.9).** Byte a byte igual ao original (comentário preservado),
  modo `0600`, criado com `O_EXCL`; **colisão de nome → `CONFIG_WRITE_ERROR`, e o
  backup preexistente e o `masking.yaml` ficam intactos** — via relógio injetável
  que força o nome.
- **Identidade de IDs (D-059).** Update e reorder preservam os IDs; create gera ID
  novo; delete + create gera ID diferente; `id` escolhido pelo cliente que não
  pertence ao documento → `IMMUTABLE_FIELD`.
- **Imutabilidade (§11.3).** `allowed_pg_functions` presente em `PUT /sql` ou
  `PUT /config` (inclusive `[]`) → `IMMUTABLE_FIELD`; ausente → o valor atual é
  preservado **em conteúdo e ordem** (modelo validado contra modelo validado).
- **Recusas sanitizadas.** Alvo inexistente → `NOT_FOUND` sem ecoar o ID; posição
  fora de `0..len` e reorder que não é permutação completa → `CONFIG_INVALID`;
  transformer inexistente → `CONFIG_RELOAD_ERROR`.
- **Falha injetada (§12.4, §7.6).** No POSIX, `fsync` de diretório falho publica o
  runtime novo com `500 CONFIG_DURABILITY_ERROR`, `applied: true`,
  `current_revision` = a nova, e uma retentativa cega recebe `REVISION_CONFLICT`;
  no Windows, o passo é **omitido** e um teste-par afirma a omissão (a escrita
  conclui com `200`). `CONFIG_OUT_OF_SYNC` da segunda verificação: arquivo
  alterado por fora entre a validação e o `replace` → `409`, conteúdo do editor
  preservado.
- **Reload com query em voo (§12.2, §12.3).** Uma referência adquirida antes do
  swap continua sendo a antiga; um aposentado ainda em uso faz o próximo reload
  bater em `RELOAD_BUSY` sem construir candidato.
- **Sem efeito nas recusas.** Para cada categoria de recusa: bytes do arquivo,
  identidade do runtime publicado, revision e digest de referência inalterados.
- **Leakage.** Nem HMAC nem a senha do DSN aparecem em corpo ou header, em sucesso
  ou erro.

**Rodadas corretivas (`test_admin_http_writes_adversarial.py`, 58 testes; mais
regressões HTTP em `test_admin_http_writes.py` e as provas e2e).** Cada teste
nasceu de um defeito reproduzido contra o commit anterior:

- **`confirm_comment_loss` estritamente booleano.** `1`, `0`, `"true"`, `null` e
  ausência → `SCHEMA_INVALID`; só o booleano `true` passa. `Literal[True]`
  sozinho aceitava o inteiro `1` (`1 == True`), então o campo é `StrictBool` mais
  um `model_validator`.
- **`allowed_pg_functions` por presença, não por valor.** Presente em qualquer
  forma — `null`, `[]`, lista, string, objeto, booleano, número — →
  `IMMUTABLE_FIELD`, detectado por `model_fields_set`. `null` explícito
  contornava a checagem `is not None`. Ausente preserva o allowlist. A recusa não
  altera arquivo, digest, revisão nem runtime.
- **O campo `allowed_pg_functions` é totalmente serializável.** O tipo é
  `JsonValue | None`, não um `object()` sentinela: `model_json_schema()` não gera
  `PydanticJsonSchemaWarning`, `model_dump()`/`model_dump_json()` funcionam com o
  campo ausente, nenhum sentinela vaza no dump, e a presença continua decidida só
  por `model_fields_set` — todas as formas presentes ainda produzem
  `IMMUTABLE_FIELD`.
- **`PUT /config` exige `sql.denied_functions`.** `sql: {}` apagaria as negações
  em silêncio; agora é `SCHEMA_INVALID`.
- **`rules:reorder` valida o formato de cada ID no schema.** ID malformado →
  `SCHEMA_INVALID`; lista vazia é permutação válida do conjunto vazio (aceita
  quando há zero regras); duplicata, item ausente e ID desconhecido continuam
  `CONFIG_INVALID` na mutação.
- **Deduplicação semântica em `PUT /sql`.** `Foo`/`foo`/`FOO`/` foo ` colapsam
  pela mesma chave da política (`strip().casefold()`), preservando a primeira
  grafia persistida e a ordem de primeira aparição das novas; a repetição do
  request é idempotente.
- **Robustez do backup, completa.** Fault injection depois da criação exclusiva,
  em cada ponto: `write`, `flush`, fechamento controlado e short write (via stream
  substituído, sem hooks de produção); `fsync` levantando `OSError` e também algo
  **não** derivado de `OSError`; hook após a criação. Para cada falha:
  `CONFIG_WRITE_ERROR`, incompleto removido, principal byte a byte intacto, backup
  preexistente (com outro nome) intocado, nenhum fd vazado (contado por
  `/proc/self/fd` no POSIX). **Exceções de controle** — `KeyboardInterrupt`,
  `SystemExit`, `GeneratorExit` — não viram `CONFIG_WRITE_ERROR`: o cleanup roda
  (incompleto removido, principal intacto, sem fd vazado) e a exceção original é
  relançada intacta.
- **End-to-end pela porta HTTP administrativa real
  (`test_admin_http_writes_e2e.py`).** A aplicação sobe com HTTP administrativo e
  MCP compartilhando o mesmo registry. Uma escrita autêntica `PUT /admin/v1/config`
  — token, headers e payload completos, pela porta admin — devolve `200` e a nova
  revisão; a consulta seguinte pela tool MCP `query_database` (cliente in-memory),
  no mesmo processo e sem restart, vê a política nova, e o valor original nunca
  aparece na resposta MCP (nem antes, nem depois). Segunda prova: uma escrita já na
  seção crítica quando o shutdown começa **termina com exatamente `200`** antes do
  fechamento dos recursos — `close()` não retorna enquanto a escrita está presa; o
  arquivo persiste exatamente a revisão nova; as threads `writer`/`closer`/
  `maskgw-admin-http` não ficam vivas; uma escrita subsequente nem conecta (porta
  fechada) e o serviço reporta `closed`. Determinístico, com eventos/barreiras e
  joins, sem `sleep`.

### Etapa 10 — Auditoria administrativa (§13, D-060)

Dois arquivos. `tests/test_admin_audit.py` (unidade, sem servidor nem banco) cobre
o schema fechado de `AdminAudit`, a imutabilidade, a serialização, a rejeição
construtiva de campos proibidos, os três enums e o comportamento best-effort do
`AuditLog` — resumido em **Auditoria**, acima.

`tests/test_admin_http_audit.py`, `integration` contra PostgreSQL real, prova a
instrumentação ponta a ponta pela porta HTTP administrativa real (mesmo harness de
`test_admin_http_writes.py`, com um `AuditLog` injetado sobre um logger próprio por
teste):

- **uma entrada por operação, mapping completo.** Cada uma das onze escritas e
  `config:adopt` emite exatamente um `AdminAudit` com a `operation`, o
  `target_kind` e o `target_id` corretos; update/delete de regra e de exception
  carregam o `target_id`; create, reorder, config, database, sql e adopt usam
  `None`.
- **`config:validate` auditado, mas não é escrita.** Operação `validate`,
  `target_kind` `config`, `revision_before`/`revision_after` `None`; não
  incrementa `admin_operations_total` e não toca revision — provado lendo o
  contador e a revision antes e depois.
- **recusas representativas.** `REVISION_CONFLICT` (409), `NOT_FOUND` (404),
  `IMMUTABLE_FIELD` (422), `CONFIG_INVALID` (422), `CONFIG_RELOAD_ERROR` (422) e
  `CONFIG_WRITE_ERROR` (500) com `outcome` (`rejected`/`error`) e `error_category`
  coerentes; a que falha antes do `replace` tem `revision_after` `None`.
- **durabilidade (POSIX).** `fsync` de diretório injetado → `outcome=error`,
  `error_category=CONFIG_DURABILITY_ERROR`, `revision_after` = a revisão nova
  publicada (§7.6). Skip condicional no Windows, como o teste-par de escrita.
- **`revision_before` observada dentro da seção crítica.** Duas escritas
  concorrentes com o mesmo `expected_revision`: a que vence observa 3 e publica 4;
  a que perde só entra na seção crítica depois e observa **4**, não 3 — prova de
  que a instrumentação não toma um snapshot antes do lock (sem TOCTOU).
- **UUIDs distintos sob concorrência.** Cinco escritas concorrentes → cinco
  `request_id` distintos.
- **duração monotônica e não negativa**, inteira.
- **target ID malformado nunca registrado.** Um segmento sem barra alcança a rota
  dinâmica, é auditado com `outcome=rejected` e `target_id=None`; um ID canônico
  inexistente é auditado com o próprio ID.
- **fora do handler não gera evento.** Leitura, auth ausente, schema inválido,
  path desconhecido e método não registrado: nenhum `AdminAudit`.
- **nada sensível.** Marcadores no `match`, na config de transformer e em
  `denied_functions`, além de token, HMAC, `postgres`, `password` e `SELECT`: nada
  aparece em record algum; a categoria fechada é registrada, nunca a mensagem
  interna do compilador.
- **falha do logger não altera resposta nem estado.** Com um handler que sempre
  levanta, a escrita ainda devolve `200`/nova revisão e o `GET` seguinte reflete a
  mudança; e uma recusa ainda devolve `409`.
- **nenhuma rota de auditoria.** `GET /admin/v1/audit[...]` é `404`, e o conjunto
  de rotas permanece o da Etapa 9 (afirmado em `test_admin_http_surface.py`).

**`stdout` do MCP limpo sob auditoria** (`test_admin_http_mcp_coexistence.py`): no
processo real, `python -m maskgw.mcp` com a Admin API ativa, uma sessão MCP por
stdio martelada com `config:validate` (rota auditada, com corpo) concorrentemente
— cada chamada emite um `AdminAudit` — mantém o enquadramento JSON-RPC intacto: o
próprio protocolo é o detector.

### Etapa 11 — Suíte adversarial administrativa (§12.6–§12.8)

A Etapa 11 **não reimplementa** a cobertura já existente. Ela começou por uma
**matriz de rastreabilidade** de cada requisito de §12.6–§12.8 contra os testes
que já o fechavam, e só então acrescentou o necessário para as lacunas reais.

#### Matriz de rastreabilidade §12.6–§12.8

| requisito | onde já é coberto | lacuna fechada na Etapa 11 |
|---|---|---|
| §12.6 token/HMAC/DSN nunca em corpo/header/erro (leitura) | `test_admin_http_leakage.py` | — |
| §12.6 idem nos grupos de **erro de escrita** e falhas injetadas **antes** do `replace` | parcial (só reads) | `TestLeakageNasFalhasDeEscrita` (revision_conflict, reload_error exato, write_error injetado, out_of_sync injetado) |
| §12.6 idem em falha injetada **depois** do `replace` (`CONFIG_DURABILITY_ERROR`) | — | `test_durability_error_depois_do_replace_nao_vaza` (POSIX; `500`/`applied:true`/rev 3→4/runtime e arquivo coerentes/audit `error` 3→4/retry rev 3 → `409` sem efeito; skip de plataforma no Windows, onde o fsync de diretório é omitido) |
| §12.6 leakage no **`AdminAudit`** emitido | — | `TestLeakageNasFalhasDeEscrita` varre `audit_text()` em cada falha, inclusive durabilidade |
| §12.6 nenhum `str(exc)`/`__cause__`/`__context__` | `test_admin_http_leakage.py`, `test_admin_http_boundary.py` | `test_error_category_de_falha_e_fechada_nunca_str_exc` (afirma `__cause__`/`__context__` nulos num `AdminError` real) |
| §12.6 leakage no **caminho de adoção** (bytes originais, backup, caminho) | — | `TestLeakageNaAdocao` |
| §12.6 `repr` app/registry/runtime/serviço/servidor sem secret | `test_admin_http_leakage.py::TestReprs`, `TestSuperficieDoApp` | — |
| §12.6 MCP stdio limpo com admin + auditoria concorrente | `test_admin_http_mcp_coexistence.py` | — |
| §12.7 inventário exato de rotas; extras quebram | `test_admin_http_surface.py::TestRouteSet` | — |
| §12.7 `/query`,`/sql`,`/execute`,`/config:reload`,`/docs`,`/redoc`,`/openapi.json`,auditoria → 404 | `test_admin_http_surface.py` (`FORBIDDEN_PATHS`, `FUTURE_PATHS`, `DOC_PATHS`) | — |
| §12.7 token ausente/errado/vazio/truncado/query/cookie/corpo nunca autentica; sem bypass por prefixo/case/Unicode; `compare_digest` | `test_admin_http_boundary.py::TestAuthentication`, `test_admin_http_surface.py::TestAuthenticationOverTheWire` | — |
| §12.7 `401` antes de `422` | `test_admin_http_surface.py`, `test_admin_http_boundary.py::TestStackOrder` | — |
| §12.7 `Origin`/`Referer` → 403; `Host` alheio/porta errada → 400 | `test_admin_http_boundary.py`, `test_admin_http_surface.py::TestBrowserProtections` | — |
| §12.7 `Content-Type` só onde há corpo; `HEAD`/`OPTIONS`/redirects/métodos | `test_admin_http_boundary.py::TestContentType`, `test_admin_http_surface.py` | — |
| §12.7 `Cache-Control: no-store` em toda resposta; nenhum CORS | `test_admin_http_surface.py::TestResponseHeaders`, `test_admin_http_boundary.py` | — |
| §12.7 limite 1 MiB com/sem `Content-Length`/chunked; corte em streaming; memória não acompanha | `test_admin_http_boundary.py::TestBodyLimit`, `TestChunkedOverTheWire` | — |
| §12.7 corpo hostil **não persiste/candidato/swap/audita** numa rota de escrita real | parcial (`TestSemEfeitoNasRecusas` cobre recusas de schema/estado) | `TestCorpoHostilSemEfeito` (grande, tipo errado, sem token, JSON malformado, schema inválido, campos extras, JSON profundamente aninhado, `Content-Length` declarado > 1 MiB — todos sem tocar estado, **sem construir candidato** (contador na `adapter_factory`) e sem auditar) |
| §12.7 parsing: JSON truncado, profundamente aninhado, campos extras, `Content-Length` | `test_admin_http_boundary.py::TestErrorHandlers` (JSON malformado, campo desconhecido, tipos), `TestBodyLimit::test_content_length_acima_do_limite_falha_ANTES_de_ler` e `test_content_length_ilegivel_nao_e_lido_como_cabe` (app interna) | `TestCorpoHostilSemEfeito` os replica **numa rota de escrita real**, provando ausência de efeito. **Limite da prova:** só o `Content-Length` *declarado* é verificado; comprimento *incompatível* com o corpo é território de request smuggling/proxy/TLS, que uma app local não pode provar, e não é alegado |
| §12.7 estado completo sob ataque: bytes, digest, revision, runtime publicado, **IDs**, **decisões de masking** | `test_admin_http_writes.py::TestSemEfeitoNasRecusas` (bytes/digest/revision/runtime) | `TestEstadoCompletoSobAtaque` acrescenta os dois que faltavam: IDs de regras/exceptions idênticos e vereditos do engine idênticos após cada recusa |
| §12.7 `allowed_pg_functions` presente → `IMMUTABLE_FIELD`; ausente preserva | `test_admin_http_writes.py::TestImutabilidade`, `_adversarial.py` | `TestImutabilidadeAdversarial` (alias por capitalização → `SCHEMA_INVALID`; aninhado/misturado → `IMMUTABLE_FIELD`; todos sem efeito) |
| §12.7 MCP sem caminho para configuração | `test_mcp_server.py` (tool única, só `sql`), `test_plan_separation.py` | `TestMcpNaoAlcancaConfig` (superfície pública do `Gateway`; gateway não importa admin) |
| §12.8 separação de planos por AST; `admin/` sem `logging`; `mcp/`↛admin; só `bootstrap/`; `runtime/`↛planos; `masking` puro | `test_plan_separation.py`, `test_purity.py` | — |
| §12.1 concorrência serializada, revisão e auditoria coerentes, sem secret | `test_admin_http_writes.py::TestConcorrenciaERevision`, `test_admin_http_audit.py::TestConcorrencia` | `TestConcorrenciaAdversarial` (N conflitos + ataques mistos: um vencedor, estado e auditoria coerentes, sem leakage) |

#### O que a Etapa 11 acrescentou (`tests/test_admin_adversarial.py`, `integration`)

38 cenários (37 executados + 1 skip POSIX de plataforma), todos `BLOCKED` (a
proteção existe e o teste a afirma), sobre o caminho de **escrita real** contra
PostgreSQL e a **auditoria** — território que os testes de leitura com adapter
falso não alcançam:

- **`TestLeakageNasFalhasDeEscrita`** — em `REVISION_CONFLICT`, `CONFIG_RELOAD_ERROR`
  (regex inválido com marcador — categoria **exata**, é compilação durante escrita,
  passo 6), `CONFIG_WRITE_ERROR` (`os.replace` injetado com mensagem cheia de
  secret), `CONFIG_OUT_OF_SYNC` (editor externo injetado **antes** do `replace`) e
  `CONFIG_DURABILITY_ERROR` (`fsync` de diretório injetado **depois** do `replace`,
  POSIX), nenhum secret/SQL/marcador/caminho/traceback aparece na resposta **nem no
  `AdminAudit`**; o `AdminError` de uma falha real tem `__cause__`/`__context__`
  nulos. O caso de durabilidade também prova `500`/`applied:true`/revisão 3→4/runtime
  e arquivo novos coerentes/audit `error` com `revision_before=3`, `revision_after=4`
  e categoria exata/retentativa com revisão 3 → `409` sem mudar estado. **No Windows
  é skip de plataforma legítimo** (o `fsync` de diretório é omitido, §7.6), não um
  finding ignorado.
- **`TestLeakageNaAdocao`** — o comentário original (que só deve viver no backup),
  o caminho do arquivo e o do diretório não vazam em adoção bem-sucedida nem na
  segunda adoção recusada — esta com a varredura **completa** (corpo, headers,
  auditoria, caminhos).
- **`TestImutabilidadeAdversarial`** — `allowed_pg_functions` em qualquer valor →
  `IMMUTABLE_FIELD` sem efeito; por alias de capitalização → `SCHEMA_INVALID` (o
  `extra=forbid` nunca abre o campo real); aninhado em `sql` ou misturado com
  campos válidos → `IMMUTABLE_FIELD`; omissão preserva conteúdo e ordem.
- **`TestMcpNaoAlcancaConfig`** — a superfície pública do `Gateway` é `{query,
  revision, close}`, sem `apply`/`adopt`/`snapshot`; nenhum módulo de `gateway/`
  importa `maskgw.admin`.
- **`TestCorpoHostilSemEfeito`** — corpo > 1 MiB (413), `Content-Type` errado
  (415), sem token (401), JSON malformado (422), schema inválido (422), campos
  extras (422), JSON profundamente aninhado (422) e `Content-Length` declarado
  > 1 MiB (413, cortado antes de ler) numa rota **de escrita real** não alteram
  bytes/runtime/revision/digest, não incrementam `admin_operations_total`, **não
  constroem candidato** (contador na `adapter_factory` inalterado) e **não emitem
  auditoria** — o handler não roda. O comprimento *incompatível* com o corpo é
  território de request smuggling/proxy/TLS e não é alegado.
- **`TestEstadoCompletoSobAtaque`** — completa `TestSemEfeitoNasRecusas`: após
  cada recusa (immutable, not_found, conflict, schema), os IDs de regras/exceptions
  e os vereditos do engine de masking (sobre cpf/email/tipo_cpf/documento/saldo)
  são idênticos, o objeto runtime publicado é o **mesmo**, e bytes/digest/revisão
  não mudam.
- **`TestConcorrenciaAdversarial`** — 8 escritas concorrentes com o mesmo
  `expected_revision` → um `200` e sete `409`; revision publicada 4; exatamente 8
  eventos de auditoria com `request_id` distintos, um `success` (3→4) e sete
  `rejected` (cada um observou 4 na seção crítica); nenhum secret sob concorrência.
  E uma mistura de ataques (immutable, not_found, schema, conflict) em paralelo com
  uma escrita legítima: só a legítima publica, e o estado final é exatamente uma
  publicação.

Repetida 5×+ sem intermitência; os cenários de concorrência e streaming repetidos
à parte. **Nenhum finding virou `skip` nem `xfail`** (D-041): cada limite conhecido
já era afirmado por teste (o payload gigante em `docs/HANDOFF.md` §11, o oráculo
por predicado e a view que renomeia em `docs/SECURITY-REVIEW.md`), e a Etapa 11 não
encontrou violação inequívoca da especificação que exigisse correção de produção.
O único skip da suíte (a leakage de durabilidade) é condicional de plataforma
POSIX no host Windows, não um finding ignorado.

## Fase 8 — registro histórico da baseline da Etapa 1

**Registro histórico: Etapa 1 concluída e posteriormente publicada.** Contrato integral em
`docs/PHASE-8-SPEC.md`; requisitos F8-001 a F8-065, componentes previstos,
etapas e contraprovas em `docs/PHASE-8-TRACEABILITY.md`. Resultados medidos
desta rodada em `docs/PHASE-8-STAGE-1-VALIDATION.md`; os números das etapas
anteriores acima são evidência histórica, não execução desta rodada.

A Etapa 1 exige a suíte Python completa sem deselect, PostgreSQL 16 real com
MASKGW_TEST_DSN presente, Ruff, format check, mypy strict e git diff --check.
No Windows, aplicar temporariamente threading.stack_size(64 * 1024 * 1024)
no processo pytest, conforme o comando documentado neste arquivo. Não alterar
produto/testes, nem instalar dependências para contornar o gate. Distinguir
skips de plataforma de skips por DSN; estes últimos bloqueiam o fechamento.

As Etapas 2–9 acumulam a tipagem estrita, Node, componentes Playwright,
browsers reais, integração real e pacote instalado de §6, nos marcos de §7.1.
Browser/Node ausente não será substituído por mock ou skip quando seu gate
for devido. Na Etapa 1, esses artefatos e dependências ainda não existem e
sua criação/instalação não está autorizada; não declarar esses gates como
executados. Nenhum teste novo de código é necessário para a entrega documental.

A revisão final deve provar inventários por igualdade, contraprovas de bytes
públicos e autenticação, origem exata e CSRF, XSS armazenado, token leakage,
headers/caminhos hostis, lifecycle/BFCache, concorrência, pós-commit e
indisponibilidade. Nunca converter finding em skip/xfail. Não gravar tokens
ou dados administrativos em traces, HAR, screenshots, vídeos ou logs dos
ensaios. A rastreabilidade não substitui os testes ainda por implementar.


## Fase 8 — Etapa 2 concluída (registro histórico, publicada)

Contrato e limites em `docs/PHASE-8-SPEC.md`; rastreabilidade parcial atualizada
em `docs/PHASE-8-TRACEABILITY.md`. A evidência desta rodada é
`docs/PHASE-8-STAGE-2-VALIDATION.md`, distinguindo-a da baseline histórica.

Testes concretos: `tests/test_admin_ui_resources.py` (74 casos isolados verdes)
e `frontend/test/protocol.test.js` (70 casos Node verdes), com fixtures
positivas tipadas em `frontend/test/contracts.js` e oito contraprovas de
compilação. As contraprovas devem falhar por incompatibilidade de tipos, sem
supressão e sem aceitar erro de importação como evidência. A união tipada
contém dez escritas UI; o décimo primeiro contrato permanece somente da API.

Cobertura: JSON/UTF-8, chaves duplicadas, vocabulário público, escapes e
concatenações, identidade de template, prototype pollution em vários níveis,
referências, ciclos, profundidade, máximos inclusivos, defaults, uniões
fechadas, fontes de projeção, catálogo/modelos, bytes/hashes e manifesto,
recursos faltantes/corrompidos e bytes imutáveis. Erro do carregador deve ser
fixo, sem entrada ou cadeia de exceção. Nenhum teste exige integrar HTTP/UI.

Gates frontend finais: instalação congelada npm ci, typecheck estrito, Node,
dois builds completos com os mesmos hashes dos 14 arquivos gerados e inspeção
dos três recursos públicos contra 193 entradas privadas derivadas. Wheel e
sdist precisam excluir ferramentas, fixtures, sourcemaps e tipos privados;
os dois pacotes são instalados fora do checkout e validados sem Node/npm.
Build e testes consumidores dos recursos devem ser sequenciais, pois o build
regenera assets e âncoras; não testar um conjunto em troca.

O gate Python continua sendo a suíte inteira, sem deselect e com PostgreSQL
16 real, pilha temporária de 64 MiB no Windows, Ruff, format check, mypy strict
e diff check. Resultados medidos: 2.378 aprovados, oito skips exclusivos de POSIX,
zero skips por DSN, zero falhas; Ruff/format/mypy aprovados (127 arquivos).
As evidências completas estão no registro da etapa. Browser real, CSP, autenticação/origem HTTP, sessão,
BFCache e renderização XSS pertencem às etapas seguintes e não são alegados
como cobertos pela fundação desta etapa.

## Fase 8 — Etapa 3 concluída

`tests/test_admin_ui_startup.py` cobre a matriz bruta de 16 valores por fonte
real/injetada e pelo entrypoint, preservação da normalização de secrets,
dependência antes de settings/recursos, settings inválidos antes de assets,
falhas em cada recurso/manifesto e incompatibilidades reancoradas antes de
qualquer efeito operacional. Testa ordem positiva, shutdown, falha após thread
HTTP e construção MCP, imutabilidade e repr sem conteúdo.

`tests/admin_ui_compat_support.py` compara 40 respostas reais com
`tests/fixtures/phase7-ui-off.json`, capturado do commit d080886 em cópia isolada:
status, corpo hex (bytes exatos) e headers determinísticos; somente Date é
excluído. A comparação cobre os dois modos nesta etapa, pois nenhum HTTP novo
está autorizado. O fixture também fixa as fontes HTTP e SecretProvider. Essa
regra de Etapa 3 precisará de revisão explícita ao implementar a Etapa 4.
O antigo teste estrutural da Etapa 2 passou a permitir a chamada autorizada
pelo composition root, mantendo a proibição de dependência HTTP/runtime/MCP
no loader e de importação dos recursos pelo HTTP. Nenhum teste virou skip/xfail.

Os 183 testes direcionados passaram: 91 de startup, 74 de recursos e 18 de
separação de planos, sem falhas ou skips. Suíte completa: 2.477 coletados,
2.469 aprovados, oito skips exclusivamente POSIX, zero skips por DSN, falhas,
erros ou deselects; PostgreSQL 16.15 real. Ruff, format e mypy strict aprovados
em 130 arquivos; 70 testes Node e dois builds idênticos. Resultados completos
em `docs/PHASE-8-STAGE-3-VALIDATION.md`. Builds e testes consumidores são sequenciais.
Nenhum browser, fetch real ou controle de navegador é alegado nesta etapa.
