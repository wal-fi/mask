# Fase 9 — Etapa 8: isolamento por sessão e gate 2 da D-090 (DESENHO APROVADO)

**Incremento sob delegação em 2026-10-20 (D-114):** receptor limitado e
ownership/pin no ledger já existem internamente, sem worker, registry ou
ingresso SQL. O estado "sem codec/receiver" abaixo é histórico. Contrato e
evidência em `PHASE-9-STAGE-8-RECEIVER-VALIDATION.md`; incerteza é quarentena
permanente, erro pós-envio não autoriza retry, e integração deve garantir um
frame por job/canal quieto. Não fecha B-1 fim a fim, B-2 ou D-090 gate 2.

> **Estado: DESENHO APROVADO em 2026-10-18; isolamento NÃO implementado e NÃO pronto.**
> Escrita em 2026-10-16 por autorização estreita do usuário ("escrever SÓ o
> desenho"), e revista no mesmo dia depois da revisão técnica. Nenhum worker,
> codec, mudança de driver, registry, lease, `db/postgres.py` ou
> canonicalização foi implementado. Nenhuma D-nnn nova é criada aqui.
> Atualização documental autorizada em **2026-10-18**, após a prova temporária
> de memória e cursores medida em 2026-10-17 (§10). O aval foi **somente para
> atualizar este desenho**, não para aprovar suas escolhas, implementar worker,
> trocar o cursor, habilitar SQL ou liberar produção.
> Em seguida, o usuário respondeu **"aprovado"** ao desenho atualizado.
> A aprovação abrange a direção de arquitetura e os contratos descritos;
> não comprova B-1/B-2, não calibra os valores e não autoriza automaticamente
> lotes de implementação, execução de novos testes, commit, push ou produção.
> Exceção posterior, autorizada em **2026-10-19**: somente o núcleo B-1 de
> snapshot e testes de equivalência do masking, local, com revisão, sem
> worker integrado ou SQL. Ele está implementado (D-111), estritamente
> opt-in interno, e o lote e a D-111 foram aprovados pelo usuário na mesma
> data; ver `PHASE-9-STAGE-8-B1-VALIDATION.md`. Isso não autoriza o
> restante do lote 1 da §13 nem fecha B-1 fim a fim/B-2/D-090 gate 2.
>
> Convenção deste documento:
> - **DESENHO** identifica um contrato aprovado documentalmente, com
>   implementação, calibração e comprovação ainda pendentes;
> - **BLOQUEANTE** é um problema empírico ou de segurança ainda sem solução
>   implementada e comprovada, mesmo quando existe alternativa proposta,
>   que impede qualquer integração de SQL de cliente;
> - **ADIADO** é um tema de etapa posterior, que não bloqueia este desenho
>   de infraestrutura.
>
> A D-090 gate 2 continua **aberta**. Nada aqui é afirmação de prontidão para
> produção, nem de conclusão da Etapa 7 ou da Etapa 8.

## 1. Objetivo e limite

A D-090 exige, antes do ingresso PGWire de consultas (Etapa 8), um **limite
efetivo** para validação, execução, leitura e masking locais, **sem abandonar
thread, processo ou conexão**. Hoje:

- `PostgresAdapter.execute_validated` (`db/postgres.py`) roda
  `validate_select` → `analyze_sensitivity` → `execute`, que faz
  `cursor.execute`, `_describe` com proveniência, `decide`, `_read_masked`
  (`max_rows`+1) e `_settle`, **no processo e na thread do chamador**;
- `statement_timeout` e `cancel_safe` limitam só o **servidor**; validação,
  AST, leitura de rede presa e masking não têm teto no cliente;
- `DatasourceRegistry.close` (`runtime/datasources.py`) espera todos os
  releases **sem timeout**.

Este desenho propõe onde o limite efetivo passa a existir **para o ingresso
PGWire**. Ele **não** limita:
- o MCP legado, que continua em processo até a Etapa 11;
- o `Registry.close` global, que também espera sessões em processo;
- a memória agregada do host (§10, BLOQUEANTE).

## 2. Modelo recomendado (DESENHO)

**Um worker persistente e isolado POR SESSÃO PGWire.** O worker:

- é um processo filho `python -I`, com ambiente reconstruído por allowlist
  no mesmo padrão de `_child_environment` da D-107 (sem `PYTHON*`,
  `MASKGW_*`, DSN nem chave);
- é o **único dono** da conexão upstream da sessão, aberta com o `conninfo`
  fixado da geração capturada (`hostaddr` já validado; **nenhuma segunda
  resolução DNS**, D-089);
- roda o **pipeline confiável existente**, sem cópia divergente:
  `PostgresAdapter.connect()` e `execute_validated(sql)`, com o
  `MaskingEngine` reconstruído pelo mesmo código de compilação (§5);
- devolve ao pai **só** resultado já mascarado, no codec fechado da §6.
  Nenhum valor sai sem passar pelo engine; os ramos `ALLOW`/`EXCEPTION`
  podem preservar o original, conforme a política existente. O resultado
  bruto anterior ao engine não sai do worker, e valores não vão para log.

O **pai** é dono de: admissão, geração capturada e referência (lease),
capacidade global e por datasource, processo, pipes, threads de I/O, prazos e
recolhimento. **Não pode haver conexão upstream da sessão nos dois
processos.**

### 2.1. Alternativas recusadas

| alternativa | motivo |
|---|---|
| thread por consulta com timeout | Python não mata thread; `join(timeout)` abandonaria a thread com a conexão (proibido pela D-090) |
| filho novo por consulta, com conexão nova | **viola a D-071** e a §7 da especificação: cada sessão PGWire mantém conexão upstream própria, com estado de transação e prepared statements |
| estender o filho da D-107 | a D-107 é o verificador **one-shot** de candidatos e fica **inalterada**: sem policy, HMAC, `SecretProvider` nem protocolo de várias requisições. O worker é contrato **separado**; pode reutilizar primitivas (allowlist, pumps, ledger) sem mudar o contrato nem o código da D-107 |
| execução em processo confiando no `statement_timeout` | não limita CPU local, leitura presa nem masking (texto da própria D-090) |

## 3. Ownership e colaboradores (DESENHO; nada implementado)

| colaborador | hoje | proposta |
|---|---|---|
| `DatasourceRegistry.open_session` | conta vaga, cria lease e conecta no pai | conta vaga e cria lease **sem conectar** num modo explícito de lease remota; o adapter nunca é aberto no pai |
| `DatasourceLease` | possui `PostgresAdapter`; `use()` serializa consulta × shutdown | possui o handle do worker; `use()` serializa o job; encerramento = fim gracioso → kill → reap (§9) |
| `PreparedRuntime` | `conninfo` e engine em memória | passa a guardar também o **snapshot de worker** capturado na compilação (§5) |
| aposentadoria de geração | fecha após refcount zero | **inalterada**: aposentar **não** fecha sessões admitidas; elas mantêm a geração capturada e drenam até o fim normal ou o shutdown explícito (D-071) |
| `Registry.close` | espera releases sem timeout | **inalterado neste desenho**. Para sessões com worker, o recolhimento passa a ter prazos próprios (§9), mas falha persistente do SO **retém** dono e vaga, e o shutdown reporta incompleto. Sessões legadas em processo continuam sem esse limite |
| D-107 (`datasource/verify.py`) | verificador one-shot | **inalterada** |
| `pgwire/driver._after_ready` | recusa tudo exceto Terminate | **inalterado** até um lote posterior aprovado |

O ledger do worker é **separado** do `_Ledger` da D-107, mas segue a mesma
regra: a vaga sai **exatamente uma vez**, depois de processo, threads e pipes
efetivamente recolhidos. A reserva de memória da §10.3 também tem dono e
liberação única; fim de um job não libera a reserva do worker persistente,
nem a de uma resposta que ainda está sendo enviada ao cliente.

## 4. Ciclo de vida (DESENHO)

1. Autenticação PGWire e callback de alias, como hoje.
2. Admissão sem espera: vagas global e por datasource, vaga de worker e
   reserva de memória para worker **e pai** (§10.3), em transação lógica
   atômica com a barreira de shutdown. Falta de qualquer recurso → recusa
   imediata, sem spawn, fila ou renovação de prazo. Não se presume que o
   limite de 32 sessões seja um orçamento de memória.
3. Spawn e handshake (§5) dentro do prazo de abertura (§8.1).
4. O worker conecta e verifica pelo pipeline existente. Falha → erro fixo e
   fim da sessão.
5. **Um job em voo por sessão, sem fila de aplicação** (§8.1).
6. Fim: Terminate, idle, erro, falha do worker ou shutdown → fim gracioso,
   depois kill e reap se preciso. **Sem reconexão automática, retry ou
   fallback** para execução em processo.

## 5. Snapshot de entrada e segredos (DESENHO, com ponto BLOQUEANTE)

**Problema:** a chave HMAC é lida do `SecretProvider` **uma vez**, na
compilação confiável da geração (`build_hmac_sha256` chama
`secrets.get(HMAC_KEY_ENV)`). O `HmacSha256Transformer` guarda só os bytes.
Se o worker relesse o `EnvSecretProvider` ao subir, ou se o pai buscasse a
chave na geração publicada mais recente, uma rotação de chave entre a
admissão e o spawn mascararia a sessão com uma chave **diferente** da
geração capturada.

**Proposta:**
- Na compilação confiável da geração (`_compile` em `runtime/candidate.py`),
  um provider de **gravação** registra exatamente os nomes e valores que a
  compilação leu (hoje só `MASKGW_HMAC_KEY`, quando há `hmac_sha256`). O
  resultado fica na geração (`PreparedRuntime`), privado, com `repr`
  redigido, pelo tempo de vida dela.
- O snapshot de worker é composto por dados **fechados e serializáveis**,
  nunca objetos Python compilados:
  - a política na forma mapeável já existente (`DatasourcePolicy.to_mapping()`);
  - os limites efetivos da geração (`statement_timeout_ms`, `max_rows`) e a
    política SQL;
  - o `conninfo` fixado (com a senha upstream);
  - o mapa mínimo de segredos gravado na compilação;
  - a identidade `datasource_id`, `generation` e `record_revision`.
- O worker recompila com o **mesmo código confiável** (`parse_config_bundle`
  com um provider estático só com esse mapa). Sem `pickle`, sem import
  dinâmico, sem chave-mestra do catálogo, sem `SecretProvider` completo.
- Transporte: só o stdin privado, uma vez, no handshake, com teto (§8.2).

**Correlação do snapshot (DESENHO, limite declarado):**
- o pai gera por sessão um nonce aleatório de 32 bytes, enviado no snapshot;
- os dois lados calculam `HMAC-SHA256(nonce, bytes canônicos do snapshot)` e
  o worker devolve a tag no handshake; tag diferente → fim da sessão;
- nonce e tag **nunca** vão para log, evidência ou erro;
- **isso prova só que o worker recebeu e decodificou os mesmos bytes**. Não
  autentica o worker contra código malicioso: o código do filho é o mesmo
  código confiável do pai, e um digest só de campos públicos não provaria
  equivalência de segredo.

**BLOQUEANTE (B-1), parcialmente implementado em 2026-10-19:** existe agora
serialização canônica privada de entradas e prova local de recompilação pelo
loader/engine reais (D-111), sob captura opt-in interna. Não existe worker,
nem prova de transporte, handshake ou vínculo automático com lease/geração
admitida: a identidade é vinculada explicitamente no harness. A equivalência
fim a fim no processo isolado, incluindo as mesmas regras, exceções,
parâmetros e segredos, ainda precisa ser demonstrada. Para transformers determinísticos, a prova
compara também a saída byte a byte. Para `random`, duas execuções legítimas
não precisam produzir o mesmo valor: a prova deve conferir os invariantes e
parâmetros aprovados, podendo usar uma fonte de entropia controlada **só no
harness de teste**. Não se propõe seed de produção nem controle de entropia
pelo cliente ou pelo IPC. Sem essa prova de equivalência, nenhum SQL de
cliente pode passar pelo worker.

O contrato implementado do núcleo está em D-111: JSON canônico **privado**
v1 de entradas, ASCII com escapes e chaves ordenadas, limites de bytes e
profundidade, compilação pelo mesmo `parse_config_bundle` e segredos exatos
da compilação original. Não é RFC 8785, codec de resultado nem autenticação.
`capture_snapshot=False` é o default; o teto novo não restringe candidatos
operacionais existentes. Nenhum chamador operacional habilita a captura.
Captura explícita inválida é recusada sem fallback para o ambiente.

**Incremento autorizado em 2026-10-19:** depois de aprovar o núcleo, o
usuário autorizou a prova em outro processo, só em testes, com revisão pelo
Claude2 e sem commit/push. Ela está implementada em um probe autossuficiente
com `python -I -B` e stdin, sem código de produção novo. Compara fingerprints
tipados/agregados de fixtures sintéticas e invariantes, não autenticação nem
identidade literal de bytes. Ver `PHASE-9-STAGE-8-B1-PROCESS-VALIDATION.md`.
O usuário aprovou explicitamente esse incremento em 2026-10-19, sem ampliar
a autorização nem autorizar commit/push.
As frases acima sobre falta de prova de transporte referem-se ao transporte
operacional: não há worker, lease/geração capturada no ingresso ou handshake.
B-1 fim a fim, B-2 e D-090 gate 2 continuam abertos.

## 6. Codec fechado de resultado (DESENHO)

`QueryResult`/`jsonable` (`gateway/models.py`) é orientado ao MCP (o Pydantic
converte `Decimal`/`datetime`/`UUID`; bytes viram base64) e **não** serve
como IPC tipado nem como texto PGWire. O masking tipado e a canonicalização
(D-015) ficam **inalterados**: o engine continua recebendo os objetos do
psycopg. O codec só codifica a **saída** já mascarada.

### 6.1. Primeiro subconjunto fechado

| caso | OID de tipo (futuro `RowDescription`) | valor aceito no worker | texto emitido | recusa |
|---|---|---|---|---|
| coluna mascarada | 25 (`text`) | `str` | o próprio `str` UTF-8 | outro tipo Python |
| NULL, qualquer coluna | o da coluna | `None` | NULL (comprimento −1 no futuro `DataRow`) | — |
| não mascarada `text` 25, `varchar` 1043, `bpchar` 1042, `name` 19 | o da coluna | `str` exato | o `str` | outro tipo Python |
| não mascarada `int2` 21, `int4` 23, `int8` 20 | o da coluna | `int` (não `bool`) dentro da faixa do tipo | decimal, sem sinal `+` nem zeros à esquerda | fora da faixa ou `bool` |
| não mascarada `bool` 16 | 16 | `bool` | `t` ou `f` | outro tipo Python |

Todo o resto fica **fora** do primeiro subconjunto, inclusive `numeric`
(a forma exata de `NaN`, `Infinity`, expoentes e escala não está fechada),
`float4`/`float8`, data e hora, `uuid`, `json`/`jsonb`, `bytea`, arrays,
`char` (18), OIDs próprios de domínios, enums e tipos de usuário.

### 6.2. Regras

**Esclarecimento posterior (2026-10-20, D-115, sob delegação):** a tabela
e a recusa abaixo se aplicam ao OID **anunciado**. Coluna MASK sai text25,
com str exato ou NULL já protegido, sem ler/reter o OID de origem; isso
preserva §6.1 e §5.5 normativa. ALLOW/EXCEPTION conferem o OID anunciado
pelo servidor contra o subconjunto, inclusive NULL. Domínios cujo OID é
anunciado como o tipo base são aceitos e codificados como esse tipo base;
domínio sobre text foi medido como OID25 no PostgreSQL16.15/psycopg3.3.4.
A recusa de domínio abaixo vale quando seu OID próprio é anunciado; não
se promete detectar todo domínio ou preservar tipos arbitrários. OID desconhecido permanece
recusado antes do fetch. O encoder está implementado isoladamente, sem worker
ou SQL operacional; evidência em `PHASE-9-STAGE-8-ENCODER-VALIDATION.md`.
O texto original a seguir conserva o contrato, com essa leitura explícita.

- **OID desconhecido (inclusive OID próprio de domínio) ou tipo anunciado
  fora da tabela → erro fixo antes de
  qualquer resposta ao cliente** (antes do futuro `RowDescription`). O tipo
  só é conhecido **depois** da execução (`cursor.description`); a recusa
  acontece então, não antes do SQL.
- A decisão é **por OID**, nunca inferida pelo valor; o valor Python precisa
  ainda bater com o tipo esperado do OID.
- Nomes duplicados são válidos e posicionais; o IPC carrega lista ordenada.
- Formato binário: nunca (§5.5 da especificação).
- Estouro de teto (§8.2) → **recusa da consulta inteira**, nunca truncamento
  de célula ou de linha. `max_rows` continua o único truncamento, sinalizado
  por `truncated`. O contrato do `NOTICE` é ADIADO (Etapa 8, §5.5).
- Um worker íntegro que detecta esse excesso antes de emitir o resultado
  devolve um erro controlado e limitado; isso **não** é um frame de resposta
  acima do teto. A sessão só continua se a conexão estiver íntegra. Já bytes
  de IPC efetivamente acima do teto são falha de protocolo (§7).
- Nunca `default=str`, JSON genérico com perda, `pickle` ou `repr`.

### 6.3. Metadados

Um DTO **separado** de metadados de resultado, montado no worker:
`(nome, oid_do_subconjunto, mascarada)` por coluna. Ele **não** amplia o
`ColumnDescriptor` do engine e **não** expõe OID de tabela, atributo ou
proveniência (§5.5 da especificação). O OID de tipo vem do
`cursor.description` e só sai se estiver na tabela da §6.1.

### 6.4. Formato do IPC e decodificação no pai

**Atualização de representação (2026-10-20, D-113, sob delegação):** o
núcleo puro agora valida bytes imutáveis completos, com header privado de
76 bytes e corpo PGWire T/D*/C, em vez de montar objetos de linhas/células
no pai. Contrato em `PHASE-9-STAGE-8-RESULT-PLAN.md`; código/testes revisados
pelo Claude2, evidência em `PHASE-9-STAGE-8-RESULT-VALIDATION.md`. Não há
chamador operacional ou worker; B-2/D-090 continuam abertos. O texto abaixo
preserva a proposta anterior de decodificação, substituída **quanto à
representação**, não quanto a validação prévia, limites, identidade ou
orçamento efetivo. O custo futuro inclui recepção + cópia imutável (2F),
scratch/envio/TLS e retenção de traceback/views; não só len(frame).

- **Framing binário fechado** com comprimento prefixado e contagens
  explícitas (colunas, linhas, bytes por célula). Não usa `json` no
  caminho do resultado: o `json` da stdlib não tem limite de profundidade nem
  de nós, e o pai não pode virar um parser sem teto.
- O decodificador do pai é **iterativo**, sem recursão, e confere antes de
  alocar: profundidade fixa 1 (lista plana de células), nº de colunas, nº de
  linhas, bytes por célula e bytes totais (§8.2). Inteiros chegam como texto
  decimal ASCII de até 20 caracteres; strings como UTF-8 validado.
- Conferir cada dimensão isoladamente **não basta**: antes de qualquer
  alocação proporcional a `linhas × colunas`, o produto deve ser validado,
  sem overflow, contra os bytes restantes do frame e o tamanho mínimo do
  cabeçalho de cada célula. Uma contagem declarada incompatível com o frame
  é recusada antes de montar listas ou células. Mesmo um frame estruturalmente
  válido precisa caber na reserva de objetos decodificados, buffers e saída
  do pai (§10.3); o teto de bytes do frame não substitui essa reserva.
  O cálculo e a imposição efetiva desse orçamento continuam no B-2 (§10).
- Cada resposta leva `(sessão, geração, job_id)` monotônico; identidade
  diferente da pendente, ou resposta sem job pendente, é **falha de
  protocolo** (§7).

## 7. Classes de falha (DESENHO)

| classe | exemplos | efeito na sessão | efeito no worker |
|---|---|---|---|
| recusa validada | `validate_select`/`analyze_sensitivity` recusam; tipo fora da §6.1; worker íntegro detecta teto de célula/resultado antes de emitir | erro fixo ao cliente; **sessão continua somente com conexão íntegra** | continua se íntegro |
| erro controlado do banco | erro sanitizado do PostgreSQL, `statement_timeout` do servidor | erro fixo; sessão continua se o worker reportar conexão íntegra | continua |
| falha de protocolo do worker | frame malformado, fora do schema, acima do teto, identidade errada | erro fixo; **sessão encerrada** | kill e reap; vaga retida até reap efetivo |
| prazo do job estourado | CPU local, fetch, leitura de rede presa | erro fixo; sessão encerrada | kill (rompe a conexão upstream) e reap |
| perda do worker | EOF, crash, saída inesperada, pipe quebrado ou saturado | erro fixo; sessão encerrada | reap |
| memória insuficiente no worker | falha de alocação, erro de libpq com sinal de memória ou término durante pressão | erro fixo; sessão encerrada, sem resultado parcial | encerrar e recolher; não reutilizar conexão cuja integridade não foi comprovada |
| falha persistente de recolhimento | `kill`, `poll`, fechamento de pipe ou join falham | sessão já encerrada | **registro fica com dono, vaga não é liberada**, shutdown reporta incompleto |

Em nenhuma classe há reconexão automática, retry ou fallback para execução no
pai.

## 8. Prazos e limites (DESENHO aprovado, valores não calibrados)

Os valores abaixo são **padrões conservadores do desenho aprovado**. Nenhum foi medido
sob carga: **a calibração continua não medida**. No futuro devem ser
**injetáveis e validados** na composição (faixas fechadas, sem 0 nem
negativo, sem "0 = infinito"), **sem** variável de ambiente nova e **sem**
código de produto agora.

### 8.1. Prazos

| orçamento | valor proposto | cobre | justificativa |
|---|---|---|---|
| idle entre mensagens | `idle_timeout_ms` do PGWire (default 300 s), **existente** | espera do primeiro byte da próxima mensagem | já validado na D-110 |
| cabeçalho da mensagem | 10 s a partir do primeiro byte | os 4 bytes de comprimento | impede slowloris no cabeçalho |
| corpo da mensagem | 30 s a partir do fim do cabeçalho | corpo inteiro do `Query`, até o teto de 64 KiB | proporcional ao teto; cliente legítimo envia de uma vez |
| abertura do worker | 12 s | spawn, handshake, `connect` e verificação | igual a `VERIFY_TIMEOUT_SECONDS` da D-107, que já cobre `connect_timeout` (10 s) e a verificação |
| `statement_timeout_ms` | da geração (100 ms – 600 s, default 30 s), **inalterado** | só o servidor | contrato existente, **só do servidor**; não é reaproveitado como prazo do cliente |
| job (antes de codificar o pedido → resposta completa no pai) | `statement_timeout_ms` + 10 s, fixado **antes da codificação e do envio**, nunca renovado | codificação/envio do pedido, validação, AST, execução, fetch, masking, serialização e decodificação limitada no pai | escolha distinta do `statement_timeout`; a margem de 10 s é conservadora e **não medida** |
| escrita da resposta ao cliente | 30 s por resposta | cliente lento lendo o resultado | separado do job: cliente lento não estica seu prazo; o job terminou, não o processo persistente, e a reserva do pai continua retida |
| fim gracioso | 2 s | frame de fim até a saída | igual a `_REAP_GRACE_SECONDS` da D-107 |
| cleanup por passada | 3 × 2 s | kill e reap | mesma semântica de `_cleanup_budget()` da D-107; best-effort, sem teto absoluto |

Regras:
- **um job em voo por sessão e nenhuma fila de aplicação.** O driver só lê a
  mensagem seguinte depois de terminar a atual;
- bytes que um cliente em pipeline deixa no **buffer do socket do kernel**
  não herdam o prazo do job ativo. Eles só passam a contar quando o driver
  começa a lê-los, primeiro sob o idle e depois sob cabeçalho e corpo;
- o pai nunca envia um segundo job com um pendente; se isso ocorresse, seria
  defeito interno (erro fixo e fim da sessão).

### 8.2. Tamanhos

| limite | valor proposto | justificativa | semântica |
|---|---|---|---|
| snapshot do handshake | 64 KiB | igual a `_MAX_INPUT_BYTES` da D-107 | acima → recusa antes do spawn |
| SQL por `Query` | 64 KiB | hoje não há limite de SQL no validator nem no MCP; 64 KiB é folgado para SELECT manual | acima → recusa sem enviar ao worker |
| colunas por resultado | 1.664 | o máximo de colunas do PostgreSQL | acima → recusa |
| célula codificada | 1 MiB | conservador para texto e mascaradas | acima → recusa da consulta |
| resposta completa | 16 MiB | conservador; com `max_rows` alto, a consulta é recusada antes de chegar ao cliente | excesso detectado pelo worker antes de emitir → erro controlado da consulta inteira; frame de IPC efetivamente acima do teto → falha de protocolo, kill e reap (§7) |
| frame de erro | 4 KiB | igual a `MAX_OUTPUT_BYTES` da D-107 | acima → falha de protocolo |

Nenhum desses tetos limita o buffer do libpq (§10), nem define um orçamento
completo de objetos no pai. Os 96/160/384 MiB usados na prova são **parâmetros
de experimento**, não novos defaults de produto. Nenhuma cota de memória ou
variável de ambiente foi implementada por esta atualização.

## 9. Encerramento, retirada e shutdown (DESENHO)

- Reload, disable e remove **não** mudam o destino nem o snapshot de uma
  sessão admitida; o worker segue na geração capturada até o fim normal ou o
  shutdown explícito. **Nenhuma sessão é morta só por retirada** (D-071).
- Shutdown em duas fases, como a D-090: pedir fim a todos e depois recolher
  todos.
- Falha persistente do SO retém dono e vaga e reporta **incompleto**. Não há
  garantia de término absoluto nem de `Registry.close` global limitado, já
  que as sessões legadas em processo continuam fora deste mecanismo.
- A D-107 e a implementação atual de shutdown **não mudam** neste desenho.

## 10. Memória — BLOQUEANTE (B-2), com prova de viabilidade parcial

### 10.1. Código atual e alcance da prova

`PostgresAdapter.execute` continua usando `connection.cursor()` sem nome
(`db/postgres.py`); `_verify_session` também usa cursor comum, mas com
resultado fixo e pequeno. No psycopg **3.3.4** instalado, `Cursor.fetchmany`
carrega linhas de um `PGresult` já existente. Portanto, `fetchmany`,
`max_rows`, teto de IPC e teto de célula **não** contêm, por si só, o buffer
upstream materializado antes do fetch e do masking. Essa distinção entre
cursores cliente e servidor consta na
[documentação oficial do psycopg](https://www.psycopg.org/psycopg3/docs/advanced/cursors.html).

A prova temporária de **2026-10-17** ocorreu fora do checkout, em Windows
nativo, CPython **3.11.3**, psycopg **3.3.4**, com PostgreSQL **16.15** próprio,
sintético e descartável em loopback. Não executou o pipeline do gateway,
masking, snapshot de geração, codec ou IPC de produto. Não mediu POSIX,
CPython 3.14, suporte a IDE nem carga real. Nenhum SQL de cliente foi habilitado.

A rodada PostgreSQL final passou **9/9 casos** e a checagem global de limpeza:
zero sessões upstream remanescentes, processos terminados, credencial removida,
zero correspondências das senhas-canário nos artefatos verificados e inventário
Docker igual antes/depois. Read-only e `statement_timeout` foram conferidos.
O escopo da varredura foi arquivos de até 8 MiB na raiz do PoC e o payload
final do resumo em memória antes da gravação; não é auditoria de todo o host.
Picos abaixo são **commit do processo**, não RSS nem RAM física do host.

| Casos sintéticos | Resultado medido | Pico de commit |
|---|---|---:|
| `client_small` | 256 linhas, 1 MiB de texto, completo | 27,406 MiB |
| `metadata_client` / `metadata_server` | nomes, OIDs de tipo e origem por tabela/atributo corretos antes e depois do fetch, em três colunas conhecidas | 26,363 / 26,367 MiB |
| `server_first11` | leu 11 de 22.528 linhas possíveis | 26,316 MiB |
| `server_large` | leu 22.528 linhas, 88 MiB de texto, em lotes de até 128 linhas | 27,523 MiB |
| `client_large_control` | mesmas linhas e texto completos, controle separado com cota de 160 MiB | 125,352 MiB |
| `client_large` / `client_first11` | ambos recusados com sinal de falta de memória sob cota de 96 MiB, antes da primeira linha | 96,000 / 95,996 MiB |
| `wide_cell` | uma célula de 16 MiB materializada antes da checagem ilustrativa do teto de 1 MiB | 90,828 MiB |

O sinal de memória nos dois casos de negação foi um `DatabaseError` do
psycopg, não necessariamente um `MemoryError` Python: o SQLSTATE era nulo
e o harness reconheceu a substring `out of memory` na mensagem, apenas em
memória. A mensagem original não foi persistida. Esse critério textual é
próprio do experimento, dependente da mensagem/locale, **não** contrato de
classificação de erros do produto. O controle com 160 MiB e os picos próximos
de 96 MiB são coerentes com pressão de memória no cliente, mas a chamada de
alocação que falhou não foi instrumentada; não se atribui só pela categoria
`database_error` uma causa específica ao servidor ou ao SO. Erro genérico ou
morte pelo watchdog **não** bastavam para aprovar os casos. Nos casos completos,
a transação voltou a IDLE e nenhum cursor nomeado restou.

O cursor nomeado exigiu transação explícita, diferente do autocommit do
produto. A prova simples de metadados **não** certifica toda a proveniência,
o validator, `_settle` ou a semântica de masking (§10.4). Uma célula gigante
continua consumindo memória antes de uma checagem após o fetch: lote de
poucas linhas não substitui cota efetiva do processo.

### 10.2. Contenção medida e reprovações preservadas

No ensaio agregado, três filhos mantiveram as alocações simultaneamente
por 3 s. Com limite configurado de **402.653.184 bytes (384 MiB)**,
`PeakJobMemoryUsed` reportou **406.024.192 bytes**. A asserção estrita
`pico <= limite` **REPROVOU**, embora uma alocação tenha sido negada.
Nenhum ensaio posterior substitui essa reprovação.

O binding ctypes foi comparado com o pywin32 já instalado em job vazio:
estrutura, flags e limites concordaram. Um diagnóstico independente com um
filho por vez e limite agregado de 32 MiB reportou picos de **33.697.792** e
**36.872.192 bytes**, para passos de 1 e 4 MiB; as duas consultas concordaram.
A causa do excedente não foi estabelecida: não se declara erro de aritmética,
bug comprovado do Windows, nem sobrecompromisso físico demonstrado.
Os campos usados e sua distinção constam na
[documentação Microsoft de limites de Job Object](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information).

Uma alternativa **separada**, `reserved_budget`, passou no ensaio: cota de
96 MiB por membro, com até quatro membros **incluindo o supervisor**,
totalizando 384 MiB de reserva lógica. Três filhos pediram 120 MiB cada e
receberam negação individual após 80 MiB de alocações; pico agregado
**294.510.592 bytes**, maior pico individual **95.797.248 bytes**.
Isso é evidência parcial de uma alternativa conservadora, não prova de
reserva global implementada nem de teto universal. Não fecha B-2.
Os 384 MiB são o cálculo de reserva por capacidade, **não** consumo medido
de quatro membros no máximo de suas cotas; não houve essa saturação integral.

O proxy de amplificação no pai mediu crescimento de commit de aproximadamente
**49,6 MiB** para um frame de 8 MiB e **96,9 MiB** para um frame de 16 MiB.
São objetos sintéticos, **não o decodificador do produto**. Rejeitar contagens
malformadas antes de alocar não limita, sozinho, a amplificação de um frame
válido. É necessário orçamento dos objetos decodificados e das cópias.

Os casos de recusa de configuração/atribuição, alocação individual, queda do
filho, morte do supervisor e watchdog terminaram e recolheram os membros
exercitados. A criação suspensa seguida de atribuição **não é uma operação
atômica**: a morte do launcher entre `CreateProcess` e `Assign` não foi provada
segura. Também não há garantia absoluta de cleanup se o SO falhar.

Histórico adicional mantido: dois primeiros ensaios detectaram membro extra
com `CREATE_NO_WINDOW`; a identidade não foi estabelecida. Usou-se depois
`DETACHED_PROCESS`, sem elevar o limite de processos. A primeira rodada
PostgreSQL teve 9/9 casos aprovados, mas **reprovou globalmente** por diferença
do ID da rede padrão `bridge`; causa não atribuída. A repetição passou sem
relaxar a checagem de inventário. Nada disso é apresentado como gate de produto.

### 10.3. Orçamento recomendado (DESENHO aprovado, não implementado)

Recomenda-se **defesa em camadas**, não escolher cursor *ou* cota como se
fossem substitutos: reserva antes da admissão + cota individual de processo +
controle de leitura + decodificação e envio orçados no pai. O limite agregado
do SO é defesa adicional; não será a única prova, diante da reprovação da §10.2.

Contrato lógico a demonstrar antes de qualquer integração:

- O orçamento cobre uma base `B` do caminho protegido no pai, margem explícita
  `H`, e, para cada sessão admitida `i`, cota de worker `W_i` e reserva de
  buffers/objetos/saída no pai `P_i`: `B + H + soma(W_i + P_i) <= M`.
  `M` é orçamento interno proposto, **não** memória física reservada no SO.
  Valores e margens ainda dependem de calibração; os números do PoC não
  viram defaults. Nenhuma variável de ambiente ou dependência nova nasce aqui.
- `B` inclui custos fixos e compartilhados imputáveis ao caminho, inclusive
  snapshots e gerações retidas; `W_i` inclui interpretador, imports, estado
  persistente, libpq, AST, lote bruto, masking e codificação. `P_i` cobre os
  buffers simultâneos de leitura, frame, objetos, saída PGWire/TLS e envio
  lento. Qualquer custo ainda não coberto é lacuna bloqueante, não margem
  implicitamente infinita. Isso **não** limita todo o host nem a memória
  independente de MCP legado, Admin ou outros processos.
- Crescimento compartilhado de `B` também exige reserva **antes** de alocar
  ou um limite superior previamente reservado; reload e gerações aposentadas
  não podem aumentar a base silenciosamente e invalidar a desigualdade.
  Esse contrato ainda precisa ser compatibilizado com o registry existente.
- A admissão reserva tudo **antes do spawn**, de forma atômica com as vagas
  e a barreira de shutdown (§4). Falta de orçamento recusa imediatamente,
  sem fila ou fallback. Concorrência entre datasources usa o mesmo ledger
  global; limites por datasource não multiplicam o orçamento disponível.
- O worker só retoma depois de limites configurados e conferidos e de
  atribuição ao domínio de contenção. Falha de configuração/atribuição recusa
  sem executar trabalho e exige recolher o suspenso. Todos os processos
  auxiliares contam: um redirector de `.venv` ou membro inesperado não pode
  ser ignorado nem justificar aumento automático da cota.
- Reservas permanecem durante a sessão, inclusive worker ocioso e resposta
  esperando cliente lento. Não se libera reserva ao terminar apenas o job.
  A liberação é única, após descarte dos buffers/saída e recolhimento de
  processo, threads e pipes; falha persistente retém dono e reserva. Falha
  de spawn só devolve capacidade após comprovar ausência de recurso vivo.
- Antes de decodificar ou construir saída, o pai confere contagens, bytes e
  custo máximo imputável a `P_i`, incluindo overhead, cópias e expansão de
  texto UTF-8 em objetos Python. Estouro é recusa **antes** da alocação
  proporcional; nunca reservar só `len(frame)` e assumir equivalência.

**Lacuna explícita do pai:** a fórmula é contabilidade, não imposição de SO
nem prova de um limite de alocação. Ainda falta demonstrar um custo superior
seguro para o decodificador/encoder real e seu comportamento sob pressão,
ou propor um domínio de processo restrito para esse trabalho, com ownership
e compatibilidade próprios. Isolar a decodificação e devolver ao pai uma
estrutura ilimitada não resolve o problema; montagem e buffers de envio no
pai também precisam permanecer limitados. Não se coloca silenciosamente o
processo inteiro do gateway, MCP, terminal ou ferramentas sob um Job Object
para alegar solução.
O proxy não escolhe nem valida essa alternativa: **B-2 permanece aberto**.

Falha de memória do worker encerra a sessão com erro fixo, sem resultado parcial,
reconexão ou fallback (§7). A recuperação do próprio mecanismo de erro e do
recolhimento sob pressão também precisa ser provada; conseguir emitir JSON
escalar no PoC não certifica o codec nem o lifecycle do produto.

### 10.4. Fetch e transação (DESENHO, condicionado a compatibilidade)

O candidato preferencial para estudo é cursor nomeado com fetch limitado,
**sem reescrever SQL com `LIMIT`**, associado às cotas da §10.3. Nenhuma troca
é feita nesta atualização. O fluxo confiável de validação, análise AST,
proveniência e masking deve continuar único, sem cópia divergente no worker.

A prova exigida abrange, no mínimo:

- consulta de cliente validada e analisada antes de executar; nomes de portal,
  `DECLARE`, `FETCH` e encerramento internos não se tornam entrada administrativa
  controlável pelo cliente nem bypass do validator;
- resolução de proveniência autoritativa **antes do masking**, por posição,
  incluindo aliases, nomes repetidos, joins, expressões, derivados e falha
  operacional do catálogo; não inferir origem só do nome exibido;
- mesma geração, regras, exceptions e segredos capturados, sob os critérios
  determinístico/aleatório do B-1; o PoC não testou essas propriedades;
- transação interna read-only delimitada, mesma conexão upstream por sessão
  (D-071), fechamento de portal e retorno ao estado esperado em sucesso,
  truncamento, erro, timeout e cancelamento. O contrato atual de `_settle`
  reverte transação pendente e nunca faz COMMIT; não pode ser trocado
  silenciosamente pelo commit do context manager usado no PoC;
- leitura de no máximo o necessário para `max_rows + 1`, mantendo o único
  truncamento aprovado e sem transformar a linha excedente. Lote por linhas
  não é teto de bytes; célula gigante, arrays/tipos fora do codec e expansão
  pelo transformer continuam sujeitos a recusa e à contenção de processo;
- erro por cota, fetch interrompido e cliente lento sem vazar resultado parcial,
  dado anterior ao engine ou estado de uma sessão para outra. A prova precisa
  medir worker **e pai**, não apenas mostrar menos memória no fetch.

Isso não antecipa suporte a transação de cliente, prepared statements,
cancelamento PGWire ou metadados de IDE das etapas posteriores.

### 10.5. Evidências e critério para fechar B-2

Originais locais: `%LOCALAPPDATA%\Temp\maskgw-memctl-poc-0f47c4ec\`, mantidos
fora do Git, sem credenciais remanescentes. O relato e hashes abaixo servem
à rastreabilidade: caminhos temporários podem deixar de existir e não são
artefatos embarcados nem substituto de validação reproduzível do produto.

| Artefato relativo à raiz temporária | SHA-256 |
|---|---|
| `REPORT.md` | `1effe36c8675f0ec83487144786131744288f7d5b5f223ce41125455f12c34f3` |
| `run-20261017-110525-11160/summary.json` | `e310b79f3f518a460181528ad98bbbfaa8791cdf633a99baae632043f41a1d66` |
| `accounting-1792246251550879300/evidence.json` | `f4f226c879c50aceff2c0c05b292eedc3da39caf3e0d63de52fdf44f13748c29` |
| `binding-crosscheck.json` | `8733b82b34476fc72592d27d8ad298edef7b75fbfbaaf20effa8bdada4e2a650` |
| `run-20261017-111339-16860/summary.json` | `26a9345694eab0eb38b0fd6875957c11c0eac67dfb5b3150df7368ef21d138bf` |
| `run-20261017-111355-10728/summary.json` | `2ea2cd8209d45e708be6c9328095440c042c795a43c21c59291818d7dbbecd0c` |
| `pg-1792247328216267200/summary.json` | `9ef5ad338725afcdd5144b6f0c257fdf922405caf51c70cbdebcd8c651bd511d` |
| `pg-1792247395553979600/summary.json` | `c828573b7fa6c10df180225bebc4ad3ec7f0702e9af83b4a4ac0bfe150e25883` |

Mesmo com o desenho aprovado, para fechar B-2 ainda são necessários testes do produto
que demonstrem as propriedades das §§10.3–10.4: imposição efetiva de limites
individuais e agregados do caminho protegido, custo do pai, admissão simultânea
até a capacidade configurada e sua recusa além dela, respostas válidas que
amplificam objetos, contagens malformadas, células gigantes, OOM, falhas de
atribuição/spawn e recolhimento, cliente lento e retenção/liberação única das
reservas, inclusive durante reload e retenção de gerações. A janela de
criação/atribuição e morte do supervisor também precisam de tratamento
explícito e prova, não de presunção baseada no job do host.

Cada plataforma/runtime reivindicado exige medição própria. Menos de 32
workers sintéticos no ensaio não certificam 32 sessões reais. A discrepância
do pico agregado deve ser resolvida com evidência ou substituída por contrato
de contenção alternativo explicitamente aprovado e comprovado; não se aumenta
o teto nem se elimina a asserção para obter verde retroativo.

Este desenho **não** altera `db/postgres.py`, **não** introduz cota de SO e
**não** muda a canonicalização. B-1 continua separado e não foi exercitado.
**B-2 bloqueia SQL de cliente e não é risco aceito; a D-090 gate 2 permanece aberta.**

**Preparação autorizada em 2026-10-19:** proposta de próximo lote B-2 com
revisão pelo Claude2 em `PHASE-9-STAGE-8-B2-PLAN.md`. O primeiro diagnóstico
sugerido é pequeno e sintético, sem worker, banco ou mudança operacional.
O primeiro aval foi somente de preparação. Depois, o usuário autorizou
separadamente B2-A (§4 do plano): harness temporário fora do checkout e
execução após revisão do Claude2. Não autoriza produto, banco/Docker,
worker integrado, SQL, commit/push ou os lotes posteriores. Não altera os
critérios acima nem reclassifica a falha agregada histórica; B-2 continua aberto.
O B2-A foi medido no Windows 3.11.3, em processos somente sintéticos: seis
controles e 36 casos, limpeza confirmada. Nos 12 casos com somente cap de
job o pico excedeu 32 MiB; nos 24 com cap individual ativo ficou dentro
dos caps ativos, sem extrapolação para produto ou múltiplos membros. Ver
`PHASE-9-STAGE-8-B2-A-VALIDATION.md`, revisada tecnicamente e com o registro
aprovado pelo usuário em 2026-10-19. O aval não autoriza outros lotes,
commit/push ou produção. Não muda critérios,
defaults ou o FAIL de 384 MiB; B-2 e D-090 gate 2 permanecem abertos.

**Preparação posterior B2-B (2026-10-19):** o usuário autorizou preparar com
o Claude2 o próximo lote de contenção e orçamento global, ainda sem
implementação. `PHASE-9-STAGE-8-B2-B-PLAN.md` propõe começar por um núcleo
lógico isolado, sem conexão com caminhos operacionais. Não altera os
contratos acima nem aprova alternativa de contenção, critérios, números ou
novos testes. Sem pressão, harness novo, worker, SQL, commit/push ou produção.
O plano é proposta, não aprovação ou fechamento de B-2/D-090.

**Autorização posterior B2-B1 (2026-10-19):** somente núcleo lógico isolado
de reservas e testes determinísticos de estado/ordens, com revisão pelo
Claude2. Implementado em `runtime/budget.py` (D-112), sem importação por
chamadores operacionais ou alteração do registry, lease, driver e bootstrap.
Custos e fatos de cleanup declarados não comprovam cotas, memória real,
concorrência ou recolhimento do produto. Evidência em
`PHASE-9-STAGE-8-B2-B1-VALIDATION.md`, revisada tecnicamente sem bloqueador
no núcleo isolado; fechamento e D-112 aprovados pelo usuário em 2026-10-20,
sem ampliar a autorização. Sem integração, SQL,
worker, pressão de memória ou commit/push. B-2 e D-090 gate 2 seguem abertos.

## 11. Itens adiados (não bloqueiam este desenho de infraestrutura)

- `NOTICE` de truncamento (Etapa 8, §5.5);
- `CancelRequest` do cliente e escolha entre `cancel_safe` pelo worker e kill
  (Etapa 9);
- extended protocol e prepared statements (Etapa 9);
- metadados e catálogo de IDE (Etapa 10);
- MCP multi-datasource (Etapa 11).

## 12. Exclusões deste desenho e de qualquer lote derivado sem nova aprovação

`Query` no driver, `RowDescription`/`DataRow`, extended protocol,
cancelamento do cliente, metadados de IDE, MCP, Admin/UI, novas rotas ou
variáveis de ambiente, dependências novas, mudança da D-107 ou do shutdown
atual, push, deploy e produção.

## 13. Lote 1 sugerido (só infraestrutura; implementação não autorizada)

- módulo do worker com framing binário fechado, tetos da §8.2 e handshake
  com a correlação da §5;
- ledger próprio e handle na lease (modo de lease remota);
- snapshot gravado na compilação, com a prova de equivalência do engine
  (B-1);
- codec só do subconjunto da §6.1, com recusa fechada para o resto;
- jobs internos disparados por teste; o driver continua recusando SQL de
  cliente com `0A000`.

O lote 1 completo **não** está autorizado pela aprovação do desenho e **não**
resolve o B-2. Só o núcleo B-1 de snapshot/equivalência foi autorizado em
2026-10-19; não inclui os demais itens acima. A prova temporária é insumo para decisões e testes separados
das §§10.3–10.5, não autorização de implementar o worker. Nenhum lote pode
habilitar SQL de cliente antes de ambos os bloqueantes comprovados e do aval
explícito para a integração.

## 14. Aceite proposto para o lote 1

- segredo ausente de argv, ambiente, stderr e logs (varredura), inclusive
  nonce e tag;
- conexão upstream só no worker, nenhuma no pai, medido no servidor;
- equivalência semântica do engine recompilado com o da geração, para
  políticas com `hmac_sha256`, `regex`, `random` e hashes: saída idêntica nos
  determinísticos; invariantes e parâmetros equivalentes nos aleatórios,
  com eventual entropia controlada só no harness (§5);
- rotação da chave HMAC entre admissão e spawn: a sessão usa a chave da
  geração capturada;
- equivalência do resultado mascarado com `execute_validated` em processo,
  no subconjunto da §6.1 e sob os critérios determinístico/aleatório da §5;
- tipo fora do subconjunto recusado com erro fixo, sem bytes ao cliente;
- upstream que trava após autenticar, durante o fetch e masking lento:
  recusa dentro do prazo, sem processo, thread, pipe ou conexão vivos;
- frame malformado, acima do teto, identidade errada, EOF e crash: kill e
  erro fixo; decodificador do pai sem recursão nem alocação antes de conferir
  teto, produto das contagens e bytes restantes;
- excesso legítimo de célula/resultado detectado pelo worker: recusa inteira,
  sem truncamento nem confusão com frame de IPC malformado; continuidade
  somente com conexão íntegra;
- aposentadoria da geração durante a sessão: a sessão continua;
- shutdown com sessões em voo: duas fases; falha simulada de reap retém vaga
  e reserva de memória, e reporta incompleto;
- se e quando o lote de contenção for autorizado: conferir os critérios da
  §10.5 no worker e no pai reais; medir não só contadores amostrados, mas
  recusa e imposição dos limites. O PoC não conta como aceite desse lote;
- suíte integral nos runtimes legado e moderno temporário.

## 15. Decisões aprovadas como desenho em 2026-10-18

1. **Modelo:** worker persistente por sessão PGWire, dono da conexão
   upstream, com o pipeline existente (§2–§4).
2. **Snapshot e segredos:** provider de gravação na compilação, snapshot
   fechado serializável e recompilação no worker, com a correlação por nonce
   e o limite declarado (§5).
3. **Codec:** subconjunto da §6.1, decisão por OID, framing binário e
   decodificador iterativo (§6).
4. **Prazos e tetos:** os padrões propostos da §8, ainda sem calibração.
5. **Bloqueantes que impedem SQL de cliente:** B-1 (equivalência do engine
   recompilado) e B-2 (memória e controle de fetch) **continuam abertos**.
   A recomendação para B-2 é reserva atômica para worker e pai, cota individual
   e fetch limitado, em camadas, com contenção efetiva do pai ainda por
   demonstrar (§10.3) e compatibilidade de transação/proveniência pendente
   (§10.4). Não é escolha de cursor **ou** cota, nem risco aceito.
6. **POSIX:** sem medição; continua fora de qualquer certificação.

O primeiro aval de 2026-10-18 autorizou apenas a atualização documental.
O **"aprovado" posterior** aprovou o desenho acima, mantendo as pendências,
os bloqueantes e as exclusões. Não é autorização para código, novos testes de
execução, commit, push ou produção. Cada lote de implementação exige aval
explícito próprio; SQL de cliente continua recusado com `0A000`.
Em 2026-10-19 houve aval separado apenas ao núcleo B-1 descrito na §5,
sem worker integrado, commit ou push; não é autorização dos demais lotes.
