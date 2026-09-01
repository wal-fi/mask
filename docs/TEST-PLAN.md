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

A Etapa 7 é a próxima e não foi iniciada: HTTP/FastAPI, autenticação, bind,
anti-CSRF, headers, limites, handlers de erro e rotas de leitura. Não há
FastAPI, bind ou porta HTTP no estado coberto por este plano.
