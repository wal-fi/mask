# Fase 9 — validação da Etapa 7 (infraestrutura de segurança; **em andamento**)

Autorizada pelo usuário em 2026-09-30, somente para a **infraestrutura de
segurança** da Etapa 7, conforme o desenho aprovado nesta conversa. **A Etapa 7
NÃO está concluída**. Entregas, em ordem: gate pós-conexão da D-090 e PoC
comparativa de SCRAM (§1.1–1.2), ownership supervisionado (§1.3, D-107), fila
administrativa, barreira e leitura selada (§1.4, D-108) e as peças puras do
startup PGWire (§1.5, D-109, local e sem commit). O listener PGWire, settings,
`SSLContext` de produto, driver sobre socket, ativação, consultas e as Etapas
8–12 não foram iniciados. A D-090 permanece aberta no gate 2 (validação e
masking locais das Etapas 8/11); a v2 continua proibida em operação real.

## 1. Entregue nesta rodada (§1.1–1.5, em rodadas sucessivas)

### 1.1 Gate pós-conexão de candidato em processo filho (D-090, gate 1)

`src/maskgw/datasource/verify.py`: a verificação pós-conexão — as consultas que
`PostgresAdapter.connect()` executa depois de autenticar (read-only,
`statement_timeout`, capability de proveniência) — passa a ter **limite efetivo**
por processo filho descartável, no padrão da resolução DNS (D-092).

- **Prazo global fixo de 12 s** (`VERIFY_TIMEOUT_SECONDS`), sem variável de
  ambiente, **cobrindo envio, execução e recebimento**. O envio e o recebimento
  rodam em threads próprias nomeadas (`maskgw-verify-stdin`/`-stdout`); o laço
  principal espera o processo até o deadline e **não depende da thread de envio**
  — um filho que não lê o stdin (payload > buffer do pipe) não prende o gate.
  Fail-closed: estourado — ou excedido o teto de stdout —, tenta-se encerrar o
  filho (`kill()`, que rompe os pipes quando entregue) e recolher os recursos.
  **Sucesso e liberação da vaga exigem recolhimento confirmado**. Se ele não
  puder ser confirmado, a verificação falha como `CONNECTION`, conservando
  registro e vaga conforme §1.3; não se promete que todo retorno de falha tenha
  recolhido todos os recursos. O prazo limita **uma verificação** — não é teto
  de fila, DNS
  (5 s próprios), filesystem nem do shutdown inteiro.
- **Teto de stdout durante a leitura** (`MAX_OUTPUT_BYTES`): a saída é lida em
  blocos e cortada **assim que** passa do limite, sem acumular a saída inteira;
  um filho que despeja sem parar é cortado em tempo limitado.
- **Falhas de transporte** (não foi possível criar o filho, pipe quebrado)
  viram categoria fechada (`CONNECTION`), sem mensagem original nem cadeia. O
  `finally` assenta o registro, mas só libera a vaga após confirmar o
  recolhimento; início ou criação incertos retêm capacidade (D-107).
- **Recolhimento por invariante, com retentativa e conferência efetiva** (2ª
  revisão da rodada 1): o `_reap` **mata o filho primeiro** (o que rompe os pipes
  e desbloqueia um writer preso num pipe cheio) e **só então fecha os streams** —
  fechar o stream do writer antes do `kill()` tentaria dar flush num pipe cheio e
  **bloquearia o próprio recolhimento** (medido: 15–24 s). Uma falha **transitória**
  de `kill()`/`wait()`/`poll()` é **retentada** (`_REAP_ATTEMPTS`), não suprimida
  e aceita. O fechamento cobre também o stream de uma **thread que nunca iniciou**
  (ex. reader que não arrancou). O término é conferido **efetivamente**
  (`process.poll()` e `thread.is_alive()`), e a conferência final está protegida:
  um `OSError` ali não escapa cru. Registrar a falha **não** conta como concluir.
- **Decisão operacional — falha persistente de recolhimento:** quando o SO falha
  **persistentemente** em encerrar/recolher o processo ou as threads após todas as
  tentativas, o gate **não finge sucesso nem promete um prazo absoluto** e **não
  libera a vaga de verificação** — a capacidade é consumida permanentemente
  (fail-closed), e a falha vira `CONNECTION` sanitizada (`VerificationResourceError`
  interna, convertida **fora** do `except` para não encadear por `__context__`).
  Um recurso vivo nunca é apresentado como recolhido. O teto nesse caso é
  `_REAP_ATTEMPTS × _REAP_GRACE_SECONDS`, não um prazo absoluto garantido.
  *(Histórico. A revisão do `8261dc7` mostrou que o recolhimento não conferia
  `closed` nos pipes, que o teto real era 3 × (2 + 2 + 2) s e que a retenção
  permanente perdia a referência aos recursos. Substituído pela §1.3.)*
- **Erros de I/O do transporte recusam o sucesso:** um erro de leitura depois de
  o filho ter emitido `{"ok": true}`, ou um erro de envio, marca `io_error` nas
  threads de I/O, e o resultado é recusado (`CONNECTION`) — bytes acumulados após
  falha de I/O nunca são aceitos como verificação válida.
- **`python -I`** (sem `-S`, medido: `-I -S` não importa `psycopg`), ambiente
  reconstruído por allowlist (nenhum `MASKGW_*`, DSN, chave-mestra, token ou
  `PYTHON*` chega ao filho).
- O filho **não** recebe policy, chave HMAC nem `SecretProvider`, e **não**
  resolve DNS: o `conninfo` já traz `hostaddr` com os endereços fixados pelo pai
  (D-089). O **segredo upstream viaja só por `stdin`** (dentro do `conninfo`),
  nunca por `argv` ou ambiente; a resposta é categoria fechada
  (`{"ok":true}`/`{"failure":"CONNECTION|CAPABILITY"}`); `stderr` descartado.
- **Limite de filhos** por semáforo próprio (`MAX_CONCURRENT_VERIFICATIONS=4`);
  sem vaga, falha fechada.
- **Primitiva única de verificação** (`verify_adapter`, em
  `runtime/candidate.py`): o caminho em processo (`verify_prepared`, pai, com o
  adapter da factory injetável) e o filho (`verify_connection`, adapter real do
  `conninfo`) chamam a mesma função; as consultas de sessão/capability vivem em
  `PostgresAdapter.connect()`, sem cópia divergente.
- **Injeção:** `build_candidate` ganhou o colaborador `verifier`; o composition
  root injeta `child_verifier` em produção (quando não há `adapter_factory` nem
  `verifier` de teste), e os testes de concorrência mantêm a verificação em
  processo. O pai continua compilando a policy e publicando o `PreparedRuntime`
  construído dos mesmos insumos verificados, sem segunda resolução.

### 1.2 PoC comparativa de SCRAM-SHA-256 servidor

`docs/poc/` (não é produto, fora do wheel/sdist, sem dependência de produto):
implementação própria em stdlib do lado servidor. Corrigido nesta rodada um
defeito da revisão — o servidor aceitava `c=AAAA` no lugar de `c=biws` com a
mesma prova, porque calculava o `AuthMessage` com um `c` assumido; agora valida o
campo `c` e assina sobre o `c` enviado, com regressão. Medido: handshake correto,
senha errada recusada, `c` adulterado recusado, primitivas == vetor RFC 7677, e
**interoperabilidade com `scramp==1.4.5`** (num venv temporário, sem tocar o
produto) nas duas direções, inclusive recusa de prova e de channel binding
adulterados. **Não** há prova de conformidade integral do protocolo nem interop
com psql/JDBC/IDEs — só o medido acima. SASLprep e channel binding `-PLUS`
continuam fora. Comparação e recomendação (sem escolher mecanismo, dependência ou
restringir senha) em `docs/poc/SCRAM-COMPARISON.md`. **Aguarda aval**; nenhuma
autenticação de produção foi incorporada.

### 1.3 Ownership supervisionado dos filhos (revisão do `8261dc7`)

Três findings confirmados no `8261dc7` e corrigidos nesta rodada, com o
gerenciador supervisionado **aprovado explicitamente pelo usuário**:

1. **Invariante de sucesso.** O `_reap` aceitava processo terminado e threads
   encerradas sem conferir `stream.closed`: um `stdout.close()` com `OSError`
   persistente deixava um ack válido virar sucesso, com pipe aberto e vaga
   liberada (reproduzido no `8261dc7`: a verificação **aprovava**). Agora o
   sucesso exige, conferido **efetivamente**, `poll()` terminado, `is_alive()`
   falso em **todas** as threads e `closed` em **todos** os pipes. Um erro de
   fechamento nunca aprova sobre recurso aberto.
2. **Orçamento compartilhado de cleanup.** A documentação prometia 3 × 2 s, mas
   cada tentativa fazia `wait(2)` + `join(2)` + `join(2)`. Medido no `8261dc7`:
   `kill()` persistente, entrada de 17.977 bytes e prazo de 0,1 s levavam
   **18,19 s** (18,22 s na revisão), com filho e threads vivos. Agora há **um**
   prazo por passada de recolhimento (`_REAP_ATTEMPTS × _REAP_GRACE_SECONDS`,
   6 s), compartilhado entre tentativas, threads e registros, separado do prazo
   da verificação (12 s). Não se espera thread sobre filho vivo, e só se espera o
   processo quando o `kill()` foi entregue. É best-effort: uma chamada do SO que
   bloqueie não tem teto absoluto.
3. **Ownership em vez de retenção permanente.** A vaga retida perdia as
   referências a processo, threads e pipes. Agora:
   - cada filho é um registro (`_ChildRecord`) adotado pelo **ledger do
     processo** (`_Ledger`) **antes** do `Popen`, junto com a vaga que consome;
   - o registro guarda processo, threads e pipes até o recolhimento efetivo;
   - a vaga é liberada **exatamente uma vez**, por quem remove o registro sob o
     lock, e **somente** com tudo recolhido;
   - o recolhimento roda fora do lock, por quem reivindicou o registro, então
     dois coletores nunca recolhem o mesmo;
   - pendentes são retentados **antes de toda nova admissão** (orçamento curto,
     `_ADMISSION_COLLECT_SECONDS` = 1 s) e **no shutdown** (orçamento de cleanup);
   - uma falha transitória do SO devolve a capacidade; uma persistente a retém,
     com dono;
   - um `BaseException` no dono (ex. `KeyboardInterrupt`) não abandona o
     registro.

   Retentar o recolhimento não é replay: o filho só verifica, e nenhuma escrita
   ou operação administrativa é repetida.

**Segunda revisão (2026-10-06/07), três defeitos reproduzidos e corrigidos:**

- **Coleta interrompida (P2-A).** O coletor reivindicava todos os pendentes
  antes do laço, e um `BaseException` no primeiro `reap` deixava os demais
  reivindicados para sempre. Agora cada coletor reivindica **um registro por
  vez**, com token próprio, dentro do `try` cujo `finally` o assenta; só assenta
  o que carrega o seu token, sem desfazer a reivindicação de outro coletor.
- **Thread iniciada antes de `start()` levantar (P2-B).** A thread só era
  registrada depois de `start()` retornar. Agora cada thread de I/O é um pump
  adotado pelo registro **antes** do `start()`. Ela executa um corpo guardado
  que só entra no alvo se o pump não foi cancelado sob lock.
- **Início incerto (garantia estrita, opção 1 escolhida pelo usuário).** Uma
  thread nativa pode existir antes do bootstrap Python com `ident is None` e
  `is_alive()` falso, e cancelar o alvo de I/O **não** comprova término da
  thread nativa. O pump tem estados de ownership: `idle` (`start()` nunca
  tentado), `starting` (gravado antes da chamada; em andamento, levantou ou foi
  interrompido) e `started` (retornou). Só `idle` dispensa prova; nos demais, o
  pump só conta como encerrado com o término físico comprovado (marca de saída
  do corpo guardado e `is_alive()` falso). Consequência aceita: um `start()` que
  não retorna e cuja thread nunca chega a rodar retém registro e vaga **até o
  reinício** (perda conservadora de capacidade). Isso inclui `start()` que falha
  antes do início real, porque o produto não distingue esse caso sem internals
  do CPython.
- **Criação incerta do filho (garantia estrita, opção (a) escolhida pelo
  usuário).** O registro era adotado antes do `Popen`, mas só recebia a
  referência depois de o construtor retornar. Um construtor que criava o filho
  e então levantava deixava o filho vivo e a vaga liberada (reproduzido pela
  revisão independente). Agora:
  - uma subclasse privada de `Popen` (API pública) entrega `self` ao registro
    como primeiro passo do construtor;
  - o registro tem três estados de criação: `idle` (construtor nunca entrado:
    nada criado, libera), `attempted` (construtor entrado que não retornou:
    incerto) e `created`;
  - alcançar o **processo** é separado da completude dos **pipes**. Um objeto
    adotado que expõe PID inteiro tem o processo encerrado pelos métodos
    públicos `kill`/`poll`/`wait`, e cada pipe exposto é fechado, mesmo que o
    outro não tenha sido. Falhas desses métodos, inclusive `AttributeError` de
    construção incompleta, nunca contam como fim, nunca aprovam e nunca liberam;
  - a vaga só é liberada com processo terminado e os dois pipes conhecidos e
    fechados. Sem PID, o processo é incerto e nem pode ser encerrado. Com PID
    mas sem um dos pipes, o processo é encerrado, mas o pipe desconhecido não
    prova fechamento. Em ambos os casos registro e vaga ficam retidos até o
    reinício, com `CONNECTION` sanitizado e `close()` incompleto, sem queimar
    orçamento a cada coleta depois que nada observável pode mudar;
  - inclui o `OSError` comum de spawn levantado dentro do construtor (custo
    aceito pelo usuário: quatro falhas incertas esgotam as verificações até
    reiniciar).

**`VerificationSupervisor`** é o handle de lifecycle sobre o ledger e o `Verifier`
de produção:

- `begin_shutdown()` recusa admissão sem esperar nada;
- `close()` recusa, retenta os pendentes e só se declara fechado sem registro
  seu — nem em voo, nem pendente. Caso contrário, levanta
  `VerificationShutdownIncompleteError`, com mensagem fixa, sem cadeia, sem
  liberar vaga e sem esperar sem teto por verificação em voo. Um `close()`
  posterior retenta;
- não reinicia nem finaliza o gateway e não cria rota, métrica ou contrato
  externo.

**Composition root.** `_open_datasources` compõe um supervisor **só** no caminho
de produção, sem `adapter_factory` nem `verifier` injetados; dublês e `verifier`
de teste continuam injetáveis e não compõem supervisor. O supervisor passa ao
`DatasourceRuntime`:

- `begin_shutdown()` também para a admissão de verificações;
- `close()` fecha o supervisor depois do registry e antes do store, num
  `finally`, para que o lock do catálogo saia mesmo com recolhimento incompleto.
  O filho não toca o catálogo;
- com recurso vivo, `Application.close()` levanta o erro sanitizado, a aplicação
  fica `closing` (não `closed`), e o retry fecha depois que o SO se recupera.

Na **falha de startup parcial**, o erro original nunca é trocado pelo shutdown
incompleto:

- antes de o `DatasourceRuntime` existir, o próprio `_open_datasources` fecha o
  supervisor;
- depois, `_close_partial` faz o mesmo;
- em ambos os casos, o registro do filho segue com dono no ledger do processo.

O modo legado e o catálogo desligado não importam nem compõem nada disso (teste
existente em subprocesso).

### 1.4 Fila administrativa dedicada, barreira e leitura selada (D-108)

**Estado:** em 2026-10-07 o usuário aprovou o fechamento deste incremento e
autorizou o commit e a publicação; o estado de publicação é o que o Git
confirmar. A Etapa 7 continua **incompleta**: a D-090 segue aberta no gate 2,
e a v2 ainda não é ativável em operação real.

Escolhas aprovadas pelo usuário: **A1** (o shutdown conclui todas as operações
aceitas, na fila e em execução), **B** (2 workers + 2 posições de espera,
excesso ou barreira fechada → `503 DATASOURCE_SERVICE_UNAVAILABLE` existente) e
**C** (com drenagem ou início/término incertos, catálogo, registry, supervisor
e store ficam retidos, e o fechamento fica incompleto e repetível). Ver D-108.

- **`AdminWorkQueue`** (`src/maskgw/runtime/admin_work.py`), composta pelo
  composition root só com catálogo + Admin HTTP:
  - workers fixos adotados antes do `start()`, com os estados da D-107;
  - sem `ThreadPoolExecutor`;
  - admissão (aceitar, registrar, enfileirar) sob o mesmo lock da barreira,
    com a capacidade contada no ato de aceitar;
  - uma exceção em qualquer passo protegido da admissão (registrar,
    enfileirar antes ou depois de mutar a fila, acordar o worker) é desfeita
    sob o lock antes de qualquer worker ver o ticket: o job e os callbacks são
    soltos primeiro, depois o registro e a posição na fila. O job recusado
    nunca executa, e o `503` é sem efeito. Uma interrupção assíncrona dentro
    do próprio desfazer não é coberta.
- **Rotas v2:**
  - escritas e testes de conexão rodam num worker, que executa operação e
    auditoria inteiras com ou sem request;
  - o handler espera sob `asyncio.shield` uma notificação leve no loop;
  - cancelar ou desconectar o request não cancela a operação aceita, e a
    resposta perdida é incerta;
  - um loop já fechado não tira o ticket de dono;
  - o erro é sempre fechado e sem cadeia.
- **Leitura selada:**
  - status, list, get e policy leem um selo imutável (`CatalogView`) trocado só
    depois da transição inteira; não tocam o lock do store, o DNS, o
    filesystem nem a verificação;
  - durante persistência e publicação/retirada vale o selo anterior;
  - falha depois de um efeito possível, ou falha ao montar o selo, retira o
    selo e bloqueia o serviço numa só transição permanente (`CATALOG_BLOCKED`
    nas leituras; status degradado);
  - uma escrita com efeito cujo selo não pôde ser trocado responde
    `CATALOG_OUTCOME_UNCERTAIN`, nunca sucesso;
  - a retirada é monotônica: nenhuma troca posterior volta a disponibilizar a
    leitura.
- **Sessões e contadores:** as sessões por datasource vêm da geração **exata**
  do selo, publicada ou aposentada; os contadores globais do registry são
  amostrais e não fazem parte do selo; `registry.published` vem do selo.
- **Estado desconhecido num worker:** fila `broken` e coordenador bloqueado
  antes de despachar qualquer outro ticket. Se essa contenção não for
  confirmada, a fila congela: os aceitos restantes concluem como falha **sem
  executar**, acompanhados, notificados e auditados no máximo uma vez.
- **Shutdown:**
  1. barreira da fila e seção crítica v1;
  2. drenagem integral, com registry e verificador ainda abertos;
  3. `begin_shutdown` do catálogo;
  4. `stop()` HTTP;
  5. runtimes e locks.

  `close()` a partir de um worker ou da thread HTTP é recusado antes de
  qualquer efeito. O startup parcial com fila retém o dono antes de qualquer
  limpeza que possa falhar e nunca substitui o erro original. O dono só é
  solto com a drenagem, o `stop()` HTTP **e** o fechamento de
  catálogo/registry/store comprovados: a drenagem prova os workers, não o
  fechamento. Se a limpeza falhar, os donos dos recursos restantes (registry,
  adapter, store) também ficam retidos. Sem fila, o desmonte é o anterior.

*Rodada histórica, anterior à validação integral registrada mais abaixo
nesta seção.* Resultados direcionados (Windows nativo, sem PG; naquela rodada
a suíte integral, o PG16 e os pacotes ainda não tinham sido executados):

| regressão | antes da correção | depois |
|---|---|---|
| `/status` durante uma verificação presa | **timeout** (event loop bloqueado) | responde em < 1,5 s |
| leitura entre persistir e publicar / persistir e retirar | **mista** (revisão nova sem geração; desabilitado ainda publicado) | selo anterior inteiro |
| leitura após `publish` que falha | **200 misto** | `503 CATALOG_BLOCKED`, status degradado |
| leituras com o lock do store preso (direto, DNS real, filesystem real) | **12 falhas** (todas esperavam) | concluem em < 0,5 s no selo anterior |
| `block_unknown` durante a selagem | **sucesso** e selo de volta | `CATALOG_OUTCOME_UNCERTAIN`, selo retirado |

- Arquivos novos: `test_admin_work_queue.py` (13), `test_admin_v2_executor.py`
  (27) e `test_admin_work_bootstrap.py` (6). Os quatro arquivos de
  concorrência foram repetidos 3×, sem intermitência.
- **Revisão seguinte (F3–F5), regressões escritas antes da correção:**
  - **F3:** com o `notify` falhando, a admissão "recusada" deixava
    `accepted == 1` e o job executava atrás do `503`. A falha reproduziu na
    fila e na ponte v2. Agora a admissão é desfeita nos três pontos (antes de
    mutar, depois de enfileirar, no `notify`), o job nunca executa, a v2
    responde `503` sem cadeia, sem efeito, com 1 auditoria e 0 tickets.
  - **F4:** com drenagem `True` e `stop()` HTTP real, uma falha em
    `_close_partial`, `registry.close_all`, `datasources.close` ou
    `store.close` soltava o dono (4 falhas). Agora o dono fica retido, junto
    com registry e store; o erro original é preservado; nada é retido quando
    a limpeza é comprovada.
  - **F5:** os testes novos soltam barreiras, drenam filas e fecham
    harness/aplicação no `finally`, e só então cancelam o watchdog. A fixture
    da fila drena toda fila iniciada no teardown.
  - Contagem atual dos arquivos novos: 15, 28 e 11. Os quatro arquivos de
    concorrência foram repetidos 3× (59/59). As suítes direcionadas e
    vizinhas tiveram **551 aprovados, 5 skips** (os que exigem DSN). Ruff,
    format e mypy strict: aprovados (183 fontes).
- **F6 — registro global de ownership sem mutex.**
  - Antes: `release_retained` achava o índice por identidade e apagava por
    índice sem lock. Com uma remoção concorrente entre os dois passos, ficava
    `[B]` e saía `C`, um dono de outro startup que não comprovou fechamento
    (regressão determinística, lista instrumentada só no teste).
  - Agora: um lock compartilhado serializa o registro e a busca+remoção por
    identidade. Ele cobre só a lista, sem limpeza nem chamada do SO. Saem só os
    donos pedidos, a remoção concorrente espera, e 8 threads retendo e soltando
    em paralelo terminam com exatamente os donos não soltos.
  - Medido: os casos de ownership foram repetidos 3× (13/13). Os quatro
    arquivos de fila e concorrência: 61/61. Ruff, format e mypy strict:
    aprovados (183 fontes). Vizinhos, PG e pacotes não foram repetidos nesta
    correção.
  - Limite: como no resto da fila, uma interrupção assíncrona entre
    instruções sob o lock não é coberta.
- Suítes direcionadas e vizinhas (v2, fila, composition root, datasource,
  bootstrap, HTTP admin, separação de planos, pureza e gates de verificação):
  **543 aprovados, 5 skips** (os que exigem DSN; sem banco nesta rodada).
- Ruff, format e mypy strict em `src` e `tests`: aprovados (183 fontes).

#### Validação integral do incremento D-108 (2026-10-07, Windows nativo)

Código e testes congelados antes dos gates: 16 arquivos `src`/`tests` com
SHA-256 registrados e reconferidos iguais ao fim. Ambiente: Python 3.11.3 da
`.venv`; PostgreSQL **16.15** em contêiner e volume nomeados novos
(`postgres:16-alpine`, só `127.0.0.1`, porta efêmera), senha aleatória só em
arquivo temporário do perfil e no ambiente dos testes, nunca impressa. O Docker
Desktop estava parado: foi iniciado só para esta medição e encerrado ao final.
Não havia contêiner preexistente; os 17 volumes anônimos preexistentes foram
preservados (lista igual antes e depois). Contêiner, volume, segredos e
diretório de build próprios foram removidos.

| gate | resultado medido |
|---|---|
| suíte Python integral (pilha 64 MiB, JUnit), rodada A | **4.351 testes: 4.338 aprovados, 0 falhas, 0 erros, 13 skips**, 600,066 s, exit 0. Skips: 5 `fsync` de diretório POSIX + 3 bits de modo POSIX + 5 symlink indisponível (WinError 1314). **Nenhum skip por DSN.** Inclui `test_admin_work_queue.py` (17), `test_admin_v2_executor.py` (28) e `test_admin_work_bootstrap.py` (11) |
| seleção `-m integration`, rodada A | **575 testes: 2 falhas**, 0 erros, 3 skips POSIX, 218,391 s. As falhas foram `test_subprocess_startup_is_fail_closed_with_real_postgresql[False/True]`: o Python filho saiu com 3221225794 (`0xC0000142`), stdout e stderr vazios. **Causa não atribuída** (não medida). A rodada foi preservada como reprovada |
| diagnóstico da rodada A | os dois casos isolados: 2/2 aprovados; o bootstrap simples de um Python filho com `PYTHONPATH=src`, repetido 20×: 20/20 com saída 0 e saída correta. Não reproduziu |
| seleção `-m integration`, rodada B | **575 testes: 0 falhas, 0 erros, 3 skips POSIX**, 215,641 s, exit 0; nenhum skip por DSN |
| 61 testes do incremento (fila, executor, composition root, concorrência) com PG16 | 61/61, exit 0 |
| Ruff, format, mypy strict (`src`, `tests`), `git diff --check`, UTF-8 sem U+FFFD | aprovados (183 fontes; 18 arquivos do incremento sem problema) |
| wheel `b52789b6…851c0e` e sdist `2a5bcccf…851f27` (cópia temporária com hashes iguais aos congelados, venvs novas, `python -I`, sem `PYTHONPATH`, cwd fora do checkout, Node/npm fora do `PATH`) | `admin_work.py` embarcado com hash igual; 5 assets da UI iguais aos do checkout; `docs/`, `tests/` e `node_modules` ausentes |
| sonda do pacote pelo composition root interno (sem ativação de operador), PG16 real | wheel e sdist: **46/46 verificações obrigatórias**, exit 0 |
| contraprova da própria sonda (`PROBE_TAMPER=1`) | reprova só a expectativa adulterada (46/47), exit 1 |

O que a sonda verifica nos dois pacotes:

- a fila e o supervisor são compostos, com 2 workers vivos;
- a criação v2 é enfileirada e verificada pelo filho `-I` do pacote contra o
  PG16 real (200; ~1,2–1,3 s), com catálogo na revisão 2 e geração 1;
- com uma atualização presa entre persistir (disco já na revisão 3) e publicar,
  status, list, get e policy respondem 200 em ≤ 16 ms. Os DTOs reais são
  **iguais** aos do snapshot anterior, exceto os contadores amostrais do
  registry;
- depois, o novo selo mostra revisão 3, o nome novo e a geração 2;
- um cliente que desiste (`TimeoutError`) com a atualização presa não abandona
  a operação: ela aplica (revisão 4, geração 3), com tickets 0;
- auditoria: 1 criação `success` e 2 atualizações `success`;
- no fechamento:
  - aplicação `closed`;
  - nenhuma thread HTTP, de worker ou do verificador viva;
  - threads auxiliares da sonda encerradas;
  - tickets 0;
  - supervisor fechado e ledger vazio;
  - catálogo reabrível e porta admin livre;
  - backends do PG de volta à linha de base;
  - diretório próprio da sonda removido.

A sonda é um harness temporário fora do repositório. Na primeira execução ela
reprovou por um corpo de política incompleto no próprio harness
(`422 SCHEMA_INVALID`); corrigido o harness, ela passou. Artefatos (JUnit,
logs, JSON sanitizado e sonda) ficam em diretório temporário fora do
repositório, para conferência. Navegadores e Node não foram reexecutados; o
frontend não mudou. A Etapa 7 **não** está concluída; a D-090 continua aberta
no gate 2, e a v2 segue proibida em operação real.

### 1.5 Peças puras do startup PGWire: framing, credencial, SCRAM e binding (D-109)

**Estado:** implementado localmente, **não commitado**. Validação integral
medida em 2026-10-08 (subseção abaixo); o fechamento depende da revisão
independente, ainda em curso. As
escolhas foram feitas sob delegação do usuário ("faça") e estão registradas na
D-109; os valores de limite não foram aprovados textualmente. Não há
listener, bind, settings, `SSLContext` de produto, driver sobre socket,
ativação por ambiente, prazo, admissão nem rate limit. O pacote
`maskgw.pgwire` não é importado por nenhum outro módulo do produto.

| arquivo | conteúdo |
|---|---|
| `pyproject.toml` | `scramp==1.4.17` e `asn1crypto==1.5.1` fixados; ignores de lint de `tests/test_pgwire_scram.py` justificados |
| `src/maskgw/pgwire/errors.py` | quatro categorias fechadas (`28P01`, `08P01`, `0A000`, `XX000`), texto fixo |
| `src/maskgw/pgwire/framing.py` | pacote inicial, StartupMessage, mensagens SASL e respostas de autenticação; perfil mínimo da D-109 |
| `src/maskgw/pgwire/credential.py` | verifier pela `make_auth_info` (SASLprep + PBKDF2, 4096 iterações) e verifier simulado |
| `src/maskgw/pgwire/scram.py` | máquina SCRAM-SHA-256 / -PLUS própria, de uso único |
| `src/maskgw/pgwire/channel_binding.py` | `tls-server-end-point` a partir do DER (RSA/EC, SHA-256/384/512) |
| `tests/pgwire_support.py` | só teste: certificados em `tmp_path`, `SSLContext` e harness de loopback com worker não daemon e recolhimento provado |
| `tests/test_pgwire_{framing,scram,channel_binding,interop}.py` | 200 testes (contagem da rodada atual) |
| `tests/test_pgwire_increment_review.py` | 11 contraprovas da revisão independente; **não** foi escrito nesta implementação nem alterado por ela |

**O que os testes provam (medido em 2026-10-08, Windows nativo, Python 3.11.3,
libpq 18.0.3 via psycopg 3.3.4):**

- vetor da RFC 7677 §3 reproduzido byte a byte (server-first e `v=`);
- `n=` vazio do libpq autentica; o `n=` é ignorado e não é reescrito no
  AuthMessage, inclusive com escapes `=2C`/`=3D` e UTF-8;
- senha errada, usuário desconhecido e alias recusado levantam o mesmo erro;
  pelo libpq, senha errada, usuário desconhecido, alias inexistente e alias
  inválido recebem os mesmos bytes `28P01`, depois da troca completa, sem
  nome, alias ou senha na mensagem do cliente;
- verifier simulado com salt e iterações (4096) idênticos aos do principal:
  o server-first de usuário real e desconhecido difere só no nonce; as chaves
  simuladas são estáveis por usuário e distintas entre usuários e processos;
- nonce do servidor com 18 bytes aleatórios (50 trocas, 50 valores
  distintos); falha da fonte é `XX000` fixo, sem a causa, e a troca fica
  terminal;
- consistência mecanismo/flag/binding: `y` com `-PLUS` oferecido, `p=` sem
  `-PLUS`, `-PLUS` sem `p=tls-server-end-point`, `tls-unique`, SCRAM-SHA-1,
  PLAIN e MD5 recusados; `c=` de outro certificado ou de SHA-256 usado em
  `-PLUS` recusado;
- forma inválida (authzid, extensões, ordem, base64, prova curta, UTF-8
  inválido, caractere de controle no `n=`, mensagem acima de 2.048 bytes
  mesmo chamando a função diretamente) é `08P01`; a troca é de uso único,
  inclusive após sucesso ou falha;
- SASLprep: "Ⅸ"/"IX" e espaço não separável são equivalentes; senha vazia, que
  normaliza para vazio, com controle, uso privado, bidi inválido ou ponto não
  atribuído é recusada com `ConfigError` fixo, sem fallback;
- channel binding: RSA-SHA256/512, ECDSA-SHA256/P-384-SHA384 calculados;
  Ed25519, Ed448, SHA-224 e DER inválido recusados; o leaf que o contexto
  apresenta é o DER do arquivo;
- interop libpq: SHA-256 sem TLS; `-PLUS` com RSA e ECDSA P-384 com
  `channel_binding=require`; `-PLUS` oferecido e cliente com binding desligado
  → SHA-256 `n`; só SHA-256 oferecido → `y`, e o cliente com `require`
  desiste; `verify-full` com a CA de teste conecta, e com outra CA o cliente
  recusa antes de qualquer troca SCRAM;
- framing hostil por socket cru: GSSENCRequest, CancelRequest, versão 3.2,
  `options`, comprimento 4 ou 20.000 e mensagem SASL de 1.000.000 bytes
  declarados recebem o erro fechado esperado; segundo SSLRequest é `08P01`;
- em todos os cenários a thread do harness terminou e o listener e os sockets
  ficaram fechados; depois de autenticar, o harness só recebeu `Terminate`;
- seleção do principal com o mesmo trabalho de HMAC para usuário certo e
  errado (contado; não é medida de tempo);
- ciclo de vida do harness: worker não daemon; `start` que falha sem iniciar
  ou depois de iniciar o worker fecha o listener e só propaga com o worker
  morto; `__exit__` com `join` falhando só retorna com o worker morto e tudo
  fechado, anotando a falha na falha anterior ou levantando-a se não havia;
  sem conexão, o worker é destravado e termina.

**Rodadas da revisão independente** (o revisor escreveu
`tests/test_pgwire_increment_review.py` durante o trabalho; o arquivo nunca
foi alterado aqui):

| rodada | findings do revisor | correção | resultado medido então |
|---|---|---|---|
| R1 (histórica) | salt simulado só de mesmo formato, não idêntico; parser SASL sem teto na própria entrada; `n=` aceitava controle e excesso; falha do nonce não sanitizada | salt idêntico; teto no parser e no client-first; `n=` sem controle; `XX000` fixo e terminal | 6/6 contraprovas falhavam antes e passaram depois; 201 aprovados nos 5 arquivos `test_pgwire_*` |
| R2 (histórica) | trabalho de HMAC desigual (0 vs 2) na seleção; worker do harness `daemon=True` e `join` com prazo sem prova de fim; `start` falho deixava o listener aberto | derivações simuladas antes da seleção; worker não daemon; recolhimento sob watchdog | 3 contraprovas falhavam antes; **209** aprovados, número de uma rodada que antecede a 11ª contraprova e **não** é o gate atual |
| R3 (atual) | `start` que inicia o worker e depois lança não o recolhia; `__exit__` com `join` falhando retornava com worker vivo, só anotando | `_reap`: fecha listener/sockets e prova a morte por `is_alive()` sob watchdog independente (aborta o processo em 60 s), em `__enter__` e `__exit__`, antes de propagar ou anotar | 1 contraprova falhava antes (10/11); agora 11/11 |

**Comandos da rodada atual (R3), antes do congelamento:** `ruff check`,
`ruff format --check` e `mypy` strict limpos em `src` e `tests` (195 fontes);
`git diff --check` limpo. `pytest tests/test_pgwire*.py` (5 arquivos por
glob): **211 aprovados**, 0 falhas, 0 skips (200 desta implementação + 11 do
revisor). `test_purity`, `test_plan_separation`, `test_leakage`, `test_audit`,
`test_db_leakage` e `test_phase8_final_inventory`: 154 aprovados. A validação
integral, feita depois do congelamento, está na subseção seguinte.

**Limites honestos:**

- não há prova de tempo constante; as comparações usam `compare_digest` e a
  decisão é tomada no fim, mas o tempo não foi medido;
- o mapeamento MD5/SHA-1 → SHA-256 da RFC 5929 não existe: certificados
  assim são recusados;
- GSSENCRequest é recusado com erro, e não com `N` como o PostgreSQL faz;
  clientes com `gssencmode=prefer` e GSS disponível podem falhar (o teste usa
  `gssencmode=disable`);
- o harness é teste: não prova prazo, admissão, rate limit, ownership de
  produção nem encerramento sob carga;
- interop medida só com libpq 18.0.3; nenhuma IDE ou outro driver;
- o Python desta máquina usa OpenSSL 1.1.1t, fora de suporte: o runtime atual
  **não** pode ser certificado como pronto para produção;
- o watchdog do harness aborta o processo de teste (código 97) em vez de
  travar; é proteção de teste, não supervisor de produto.

#### Validação integral do incremento D-109 (2026-10-08, Windows nativo)

**Congelamento:** depois dos testes focados e estáticos verdes (rodada R3),
202 arquivos funcionais (`src/maskgw`, `tests`, `pyproject.toml`) tiveram o
SHA-256 registrado (digest do conjunto
`0c8490b2bcbe7f8f47de99277920d62fc19c96433258794df071306a7cb20f58`). Foram
reconferidos ao fim, iguais, sem arquivo novo nem ausente. Depois do
congelamento só mudaram documentos: três correções do revisor (AGENTS.md
parágrafo final, introdução da PHASE-9-SPEC, linhas F9-006/F9-036/Etapa 7 da
TRACEABILITY) e esta evidência.

**Ambiente:** Python 3.11.3 (`.venv`), libpq 18.0.3 (psycopg 3.3.4),
PostgreSQL **16.15** em contêiner e volume novos e próprios
(`postgres:16-alpine`, só `127.0.0.1`, porta efêmera). A senha aleatória
ficou só num arquivo temporário e no ambiente do runner, nunca impressa. A
`MASKGW_TEST_DSN` ficou só no ambiente. O Docker Desktop estava parado e foi
iniciado só para esta medição. Não havia contêiner preexistente; 17 volumes e
3 redes preexistentes foram preservados (listas iguais antes e depois).

| gate | resultado medido |
|---|---|
| suíte Python integral (pilha 64 MiB só no wrapper, JUnit), sem deselect/skip/xfail adicionados | **4.562 testes: 4.549 aprovados, 0 falhas, 0 erros, 13 skips**, 607,406 s, exit 0. Skips só de plataforma: 5 `fsync` de diretório POSIX, 3 bits de modo POSIX, 5 symlink indisponível. **0 skips por DSN.** Os 211 testes `test_pgwire*` (11 do revisor) estão na contagem, sem falha |
| build (cópia temporária da fonte, 104 arquivos de `src` + `pyproject.toml` conferidos iguais ao congelado; `python -m build`) | wheel `maskgw-0.1.0-py3-none-any.whl` SHA-256 `2bcf338c478eb1f7ba2eb281f135d064c52bb93cc8b2a797c723df3bba66372e` (107 entradas); sdist `maskgw-0.1.0.tar.gz` SHA-256 `36cf0460c3fb185ffeaecec29edb1f874043206d10a1ae0de081b0c4e977a6da` (133 entradas). Os dois com os 6 módulos `pgwire`, sem `tests`, `docs`, `frontend` ou `node_modules`. Metadata: `scramp==1.4.17`, `asn1crypto==1.5.1`, `cryptography==50.0.1` |
| dependências fixadas | restrições da `.venv` validada (`pip freeze`); `scramp-1.4.17` e `asn1crypto-1.5.1` baixadas com SHA-256 iguais aos registrados no desenho (`a4e3fd2e…474ac8`, `db4e4072…f8fd67`) |
| instalação | duas venvs novas e separadas (Python base 3.11.3), fora do checkout: wheel e sdist, exit 0 |
| sonda do pacote instalado (`python -I`, sem `PYTHONPATH`, `PATH` só System32, sem Node/npm, cwd fora do checkout) | **wheel 54/54 e sdist 54/54**, exit 0 |
| contraprova da sonda (`PROBE_TAMPER=1`) | wheel e sdist **53/54**, reprova só `expectativa_adulteravel`, exit 1 |

**O que a sonda verifica nos dois pacotes:**

- origem dos imports: `maskgw` vem de `Lib/site-packages/maskgw/__init__.py`
  da venv; os 5 módulos `pgwire`, `scramp` e `psycopg` também vêm da venv, e
  nenhum do checkout. O harness `tests/pgwire_support.py` do checkout é
  importado e usa o `maskgw.pgwire.framing` instalado;
- `scramp` 1.4.17 e `asn1crypto` 1.5.1 instalados, e os pins declarados em
  `Requires-Dist`;
- os 6 fontes `pgwire` instalados com SHA-256 iguais aos congelados; os 5
  assets da UI (`index.html`, `manifest.json`, `presentation.json`, `ui.css`,
  `ui.js`) iguais aos do checkout; a distribuição sem `tests`, `docs`,
  `frontend` ou `node_modules`;
- autenticação pelo libpq 18.0.3 contra o código instalado, sem SQL e sem
  upstream:
  - SCRAM-SHA-256 sem TLS (flag `n`);
  - -PLUS com RSA e `channel_binding=require`;
  - `verify-full` com a CA de teste e -PLUS;
  - senha errada e usuário errado com `28P01` idêntico;
  - binding de outro certificado recusado com `28P01`;
  - em cada sucesso, o harness só recebeu `Terminate`;
- em todos os cenários: worker morto, listener e sockets fechados; nenhuma
  thread do harness ou do watchdog viva; diretório de certificados da sonda
  removido.

**Limpeza:**
- **Removidos:** contêiner, volume, arquivo de credencial, venvs, cópia da
  fonte e wheelhouse próprios.
- **Restaurado:** o Docker Desktop voltou a ficar parado (`docker desktop
  stop`; `docker info` falha, nenhum processo do Docker).
- **Preservados**, fora do repositório, em
  `%LOCALAPPDATA%\Temp\maskgw-s7-d109-gates\`: JUnit, logs, JSON da sonda, os
  dois pacotes, hashes, restrições e roteiros, todos sem segredo.
- **Fora desta limpeza:** os diretórios temporários do pytest (retenção do
  próprio pytest, compartilhada com rodadas anteriores), que contêm chaves
  apenas de teste.
- **Intactos:** `.codex/`, `.claude/`, stackdumps, `systeminfo` e `dist/`/`build/`
  preexistentes.

Nenhum navegador, Node ou teste de UI foi executado: o frontend não mudou. A
Etapa 7 **não** está concluída; não há listener, settings, bootstrap,
consultas nem ativação. A D-090 continua aberta no gate 2, a v2 segue
proibida em operação real, e o runtime atual (OpenSSL 1.1.1t) não está
certificado para produção.

*(Nota posterior: a frase acima descreve o estado ao fim da §1.5. Settings e
TLS de produto entraram depois, pela D-110 — ver a §1.6.)*

### 1.6 Integração do listener PGWire, lote 1: settings e TLS (D-110)

**Estado:** a autorização explícita do usuário em 2026-10-09 cobre listener,
TLS e autenticação sem SQL, configuração externa, admissão e shutdown seguros,
testes só em loopback e em ambientes descartáveis, e revisão antes de
commit/push. Não cobre deploy nem liberação de produção, e o runtime moderno é
um gate separado. Este lote foi implementado localmente, **sem commit**, e
aguarda revisão. Driver, listener, integração interna e ativação **não**
foram iniciados. O `main` não lê `MASKGW_PGWIRE_*`, e nenhum módulo do
produto importa `maskgw.pgwire`.

| arquivo | conteúdo |
|---|---|
| `src/maskgw/pgwire/settings.py` | `resolve(raw, secrets)`: §5.1, `ENABLED` bruto `1`, defaults da spec, inteiros estritos, bind preservado e classificado, TLS exigido fora de `127.0.0.1`/`::1`, `PgwireLimits` com os defaults delegados |
| `src/maskgw/pgwire/tls.py` | `prepare_server_tls(cert, key)`: arquivos e pais, cert lido de forma limitada, contexto TLS 1.2+, identidade antes e depois do load, handshake em memória limitado, binding do leaf apresentado |
| `tests/test_pgwire_settings.py` | 120 testes (rodada atual) |
| `tests/test_pgwire_tls.py` | 52 aprovados + 7 skips de plataforma (rodada atual) |
| `tests/pgwire_support.py` | gerador de teste: a chave passa a ser criada com `0600` no POSIX (criação exclusiva + `chmod`); o produto não foi relaxado |
| `tests/test_pgwire_tls_increment_review.py` | 4 contraprovas do revisor; **não** foi escrito nem alterado nesta implementação |
| `pyproject.toml` | ignores de lint de `tests/test_pgwire_settings.py`, justificados |

**O que os testes provam (2026-10-09, Windows nativo, Python 3.11.3 /
OpenSSL 1.1.1t):**

- **Ativação:** `ENABLED` liga só com `1` bruto (`" 1"`, `"1 "`, `"01"`,
  `"true"` desligam). Desligado, só `MASKGW_PGWIRE_ENABLED` é lido, e nenhum
  segredo é consultado, mesmo com porta e bind inválidos presentes.
- **Defaults e inteiros:** 127.0.0.1, 6432, 32 (igual ao `MAX_GLOBAL_SESSIONS`
  do registry), 300000. Porta, sessões e idle recusam vazio, zero, sinal,
  espaço, zero à esquerda, dígitos não ASCII e mais de 9 dígitos. Faixa
  efetiva exata, imposta pelo limite de representação/parse (escolha
  delegada): sessões e idle de 1 a 999.999.999 (`999999999` aceito,
  `1000000000` recusado); porta de 1 a 65535. 100000 sessões é aceito: não há
  teto oculto de 32.
- **Usuário e senha:** obrigatórios. A senha ausente, vazia ou só com espaços é
  recusada, e a com bordas é aparada, pela normalização existente.
- **Bind:** `127.0.0.1` e `::1` dispensam TLS; `0.0.0.0`, `::`, `127.0.0.2`,
  `0:0:0:0:0:0:0:1`, `fe80::1%2`, `localhost` e hostnames exigem cert e chave e
  são preservados exatamente como vieram. Nenhum DNS é consultado (espião em
  `getaddrinfo` e `gethostbyname`). Bind malformado é recusado.
- **Settings sem vazamento:** `repr` e erros sem senha, usuário, bind, caminho
  nem valor; sem `__cause__`/`__context__`.
- **TLS aceito:** mínimo TLS 1.2, `OP_NO_COMPRESSION`, `OP_NO_RENEGOTIATION`,
  `CERT_NONE`. O leaf apresentado é o do PEM, e o binding é SHA-256 (RSA) ou
  SHA-384 (ECDSA P-384) do leaf. Com cadeia no PEM, vale o primeiro. Nenhum
  arquivo temporário é criado, e um cliente TLS 1.1 não negocia.
- **TLS recusado:** cert ou chave inexistente, diretório, caminho com NUL
  (prova de que não trunca para outro arquivo), tipo inválido, pai junction
  (medida real no Windows), arquivo com atributo de reparse point, cert e chave
  acima do limite, arquivo que cresce durante a leitura, vencido, ainda não
  válido (limites inclusivos), Ed25519, PEM inválido, chave que não casa,
  chave cifrada (sem prompt) e chave inválida.
- **Troca durante o load:** outro par válido trocado (identidade mudou) e o
  mesmo conteúdo regravado (identidade mudou) são detectados, assim como um
  leaf apresentado diferente do lido.
- **Handshake em memória:** recusa com voltas insuficientes, bytes
  insuficientes ou prazo estourado.
- **Erros TLS:** sem caminho, PEM, "SSL" nem mensagem do OpenSSL.

**Contraprovas do revisor neste lote** (arquivo nunca alterado aqui):

| finding | correção | resultado |
|---|---|---|
| falha ao criar o `SSLContext` do servidor vazava o `OSError` original | criação encapsulada, com `ConfigError` fixo | falhava antes; passa |
| falha ao criar o contexto cliente da sonda em memória vazava a exceção (no teste, a criação do contexto servidor também quebra) | toda a sonda dentro do `try`, com qualquer falha virando recusa fechada | falhava antes; passa |
| caminho com NUL | passava **por acaso**: medido que `abspath` trunca no NUL no Windows; agora há recusa explícita antes do `abspath`, com teste próprio que prova o risco | passa |
| `SSLKEYLOGFILE` não ativa log de chaves | já atendido (o contexto não é `create_default_context`) | passa |

**Rodada 1 do lote (histórica):** ruff e format limpos; mypy com 1 erro só no
arquivo do revisor (`Statement is unreachable`, depois corrigido por ele no
próprio teste); `pytest tests/test_pgwire*.py`: 382 aprovados, 0 falhas,
6 skips; estruturais 154.

**Revisão do lote 1 (rodada 2), achados e correções:**

| achado do revisor | correção |
|---|---|
| o gerador de teste gravava a chave com o modo default (`0644` com umask comum), que o produto recusa no POSIX: os positivos falhariam em Linux | `write_private_key` no gerador cria a chave com `0600` (criação exclusiva + `chmod`); o mesmo gerador serve aos testes do revisor; teste fixa o modo `0600` onde há bits POSIX (skip no Windows) e a criação exclusiva. **Não medido em Linux** |
| a redação dizia que os 9 dígitos "não são teto" | corrigida: limite de representação/parse, escolha delegada, com faixa efetiva exata de 1 a 999.999.999 para sessões e idle (testados `999999999` aceito e `1000000000` recusado) e porta de 1 a 65535 |
| a §2/§5 desta evidência, a SPEC e a TRACEABILITY davam settings e `SSLContext` como totalmente abertos | recorte antigo marcado como histórico; estado atual parcial registrado (lote 1), sem alterar requisitos normativos nem resultados históricos |

**Comandos da rodada 2 (atual):** `ruff check`, `ruff format --check` e
`mypy src tests` (strict) limpos em 200 fontes, **inclusive** o arquivo do
revisor. `git diff --check` limpo. `pytest tests/test_pgwire*.py` (8 arquivos,
por glob): **387 aprovados, 0 falhas, 7 skips de plataforma** (1 symlink
indisponível, WinError 1314; 6 de bits de modo POSIX). Por arquivo: settings
120, TLS 52 + 7 skips, revisor 4/4 (D-110) e 11/11 (D-109); os 211 da D-109
seguem verdes. Estruturais (`test_purity`, `test_plan_separation`,
`test_leakage`, `test_audit`, `test_db_leakage`,
`test_phase8_final_inventory`): 154 aprovados.

**Não executados neste lote** (nenhum aprovado por omissão): suíte integral,
PostgreSQL real, wheel/sdist e runtime TLS moderno. Docker não foi iniciado;
nenhum socket de rede foi aberto pelos testes deste lote.

**Limites honestos:**

- ACL do Windows não é verificada; ancestrais acima do pai imediato não são
  conferidos;
- TOCTOU: não há prova de que os bytes da chave inspecionada são os lidos pelo
  OpenSSL, nem contra uma troca dupla rápida (A→B→A) que preserve dispositivo,
  inode, tamanho e mtime;
- só o leaf é comparado com o apresentado: a stdlib 3.11 não expõe a cadeia
  enviada;
- os testes de modo POSIX e de symlink não rodaram neste host; não há
  execução medida em Linux, e nada aqui afirma que os positivos passam lá;
- o runtime OpenSSL 1.1.1t está fora de suporte: nenhum contexto de produção
  é certificado.

#### Lote 2: transporte e driver de startup/autenticação (D-110)

**Estado:** implementado localmente, **sem commit**, aguardando revisão. Não
há listener, bootstrap nem DNS, e nenhum módulo do produto importa
`maskgw.pgwire`. Os servidores de teste são do próprio teste: `socketpair` ou
um socket em `127.0.0.1` com porta efêmera e uma conexão.

| arquivo | conteúdo |
|---|---|
| `src/maskgw/pgwire/transport.py` | `Deadline`, `RawChannel` (fatias finitas, `send` com offset, `linger` limitado) e `TlsChannel` (`SSLObject`/MemoryBIO sobre o mesmo socket raw) |
| `src/maskgw/pgwire/driver.py` | `run_startup_session`: SSLRequest/TLS, SCRAM, alias pelo selo, reserva antes do `AuthenticationOk`, fachada pós-autenticação, só `Terminate` |
| `src/maskgw/pgwire/errors.py` | categoria `TOO_MANY_CONNECTIONS` (`53300`) |
| `tests/pgwire_driver_support.py` | só teste: `Peer` não daemon com fim provado sob watchdog, `watchdog`, builders e cliente SCRAM mínimo |
| `tests/test_pgwire_transport.py` | 36 testes |
| `tests/test_pgwire_driver.py` | 53 testes |
| `tests/test_pgwire_driver_interop.py` | 9 testes (libpq 18.0.3 real em loopback) |
| `tests/test_pgwire_transport_increment_review.py` | 8 contraprovas do revisor; **não** escrito nem alterado aqui |

**O que os testes provam (2026-10-09, Windows nativo):**

- **Prazo absoluto:** um peer que goteja 1 byte a cada 30 ms estoura o prazo
  de 0,3 s em cerca de 0,34 s. A parada é atendida em menos de uma fatia.
  Startup gotejado e cabeçalho pós-autenticação gotejado não renovam os
  prazos.
- **Envio:** com um peer que não lê, 8 MiB dão TIMEOUT, e o que chegou é
  prefixo exato do payload, sem reenvio. Os blocos no socket ficam em até
  `chunk_bytes`.
- **EOF e erro de I/O:** viram categorias fechadas.
- **TLS sobre o mesmo socket (o fd não muda):** roundtrip de 300 KB;
  recusas de lixo, ClientHello gotejado (TIMEOUT), teto de bytes, teto de
  voltas, EOF no meio do handshake e falha ao criar o objeto TLS.
- **Correções vindas das contraprovas do revisor:**
  - parada e prazo conferidos também em passos só com buffer;
  - teto de bytes também no passo que conclui o handshake;
  - escrita parcial do `SSLObject` preservada.
- **`linger`:** o FIN segue os dados, e o descarte fica limitado em tempo, em
  bytes e pela parada; não fecha o socket. O corpo pode ser descartado no
  transporte, mas nunca é parseado nem executado. A entrega do erro a todo
  peer e sistema operacional não é prometida. A escolha foi aceita
  tecnicamente na revisão como decisão de transporte sob delegação; os
  números não foram aprovados pelo usuário.
- **Driver, sucesso:** sequência exata de mensagens, `ParameterStatus` fixos,
  `BackendKeyData` diferente a cada sessão e `ReadyForQuery 'I'`; o
  `Terminate` encerra limpo. A ordem dos callbacks é alias e depois reserva.
- **Reserva:** recusa dá só `53300`, sem `SASLFinal` nem `AuthenticationOk`;
  erro do callback dá `XX000`, sem o texto do erro.
- **Falha uniforme:** os mesmos bytes `28P01` para senha errada, usuário
  desconhecido, alias inexistente, alias inválido, alias ausente, callback de
  alias que falha e prova adulterada. A reserva não é chamada.
- **Pós-autenticação:** 15 tipos de mensagem (`Q P B D E C S H F d c f p`,
  `0x00` e `0xff`), cada um declarando 1 GB sem enviar corpo, recebem `0A000`
  de imediato. A query simples não é interpretada (só alias e reserva foram
  chamados). `X` com tamanhos 0, 3, 5, 8 e 2³²−1 dá `08P01`, e a ociosidade
  é absoluta.
- **Pré-autenticação:**
  - SSLRequest sem contexto recebe `N`, e o segundo SSLRequest dá `08P01`;
  - TLS exigido recusa o startup em claro (`08P01`), sem chamar callbacks;
  - GSSENC e Cancel dão `0A000`; tamanho 20.000 ou 3 e SSLRequest de 12
    bytes dão `08P01`;
  - EOF em cada estágio e no meio do SCRAM, sem resposta;
  - parada sem resposta.
- **TLS no driver:** SCRAM-PLUS e SHA-256 sobre TLS; falha TLS depois de `S`
  sem `ErrorResponse` em claro; binding de outro certificado dá `28P01`.
- **Ownership:** o driver não fecha o socket do chamador e não cria thread
  (conferido em cada teste).
- **libpq real (loopback):**
  - SHA-256 sem TLS; -PLUS com `channel_binding=require`; `verify-full` com
    a CA de teste; outra CA é recusada;
  - senha errada e alias inexistente com `authentication failed`, sem o
    alias nem a senha;
  - reserva recusada dá `too many connections`;
  - TLS exigido com cliente em claro é recusado;
  - em todos, thread e sockets do servidor de teste fechados.

  Nenhuma query foi enviada ao libpq.

**Achado medido durante o lote:** antes do `linger`, de 5 a 6 dos 15 testes de
mensagem recusada falhavam de forma intermitente. O cliente não recebia o
`0A000`, porque o close com o corpo não lido virava RST. Com o `linger`:
53/53 em três rodadas seguidas.

**Comandos da primeira rodada do lote 2 (histórica):** ruff, format e mypy
limpos em 207 fontes; `pytest tests/test_pgwire*.py` (12 arquivos) com
**500 testes, 493 aprovados, 0 falhas, 7 skips**, em duas rodadas; antes das
correções, as 8 contraprovas do revisor falhavam. Estruturais 154/154.

**Revisão do lote 2: dois contratos corrigidos, com teste primeiro.**

| achado do revisor | correção | prova |
|---|---|---|
| o `_Session` criava o `Deadline` ao começar, e o comentário pedia "logo após o accept": atraso de agendamento da thread **renovava** o prazo | o `Deadline` passa a ser criado pelo dono no accept e é parâmetro **obrigatório** de `run_startup_session`, sem fallback (a guarda `isinstance` foi retirada por ser inalcançável para o mypy; a omissão é `TypeError` do próprio Python) | prazo vencido na entrada: TIMEOUT com **zero** operações de socket (proxy contado: nenhum `settimeout`, `recv` nem `send`), sem alias nem reserva; prazo do accept vencido por atraso da thread, mesmo com `startup_ms` de 60 s; omissão do prazo dá `TypeError` |
| a reserva não conferia o prazo depois do callback de alias | `check` de parada e prazo imediatamente antes de `reserve_session` | callback de alias que consome o prazo: TIMEOUT, reserva não chamada, nenhum `SASLFinal`/`AuthenticationOk`; parada pedida durante o alias: STOPPED, idem |
| `send` devolvendo 0 virava laço de CPU até o prazo | falha de I/O fechada imediata | proxy contado: 1 chamada e falha em menos de 1 s com prazo de 30 s; envio parcial de 1 byte por chamada preserva o offset (6 chamadas, bytes na ordem e sem repetição) |

**Rodadas vermelhas e interrupção (registro procedural).** Antes das
correções, os testes novos falharam como esperado: o driver ainda não
aceitava o `deadline`, e o `send` que devolve 0 girava até o prazo de 30 s.
A matriz vermelha foi repetida duas vezes com timeout de 300 s; em cada
caso, o helper de teste já passava `deadline` antes de a assinatura do
driver mudar, e o peer esperava. O revisor interrompeu só o CLI desta tarefa
e os pytest identificados. Causa procedural medida: o helper foi atualizado
antes da assinatura. Não foi achado novo de produto nem problema de rede, e
as contraprovas do revisor reproduziram os contratos ausentes em 0,41 s.

**Comandos da rodada final (atual):**
- Focados primeiro: os 5 de `TestPrazoDoDono`, os 2 de envio do
  `RawChannel`, o de TLS exigido sem contexto e os 10 do revisor (1 em
  `test_pgwire_driver_increment_review.py`, 9 em
  `test_pgwire_transport_increment_review.py`): **18/18**, o mais lento em
  0,01 s.
- Matriz completa `pytest tests/test_pgwire*.py`, 13 arquivos por glob, com
  JUnit fora do checkout: **509 testes, 502 aprovados, 0 falhas, 0 erros,
  7 skips de plataforma** (1 symlink, WinError 1314; 6 de bits de modo
  POSIX), exit 0, 30,5 s. Nenhum caso travou; o mais lento foi o de recolha
  do harness sem conexão, 5,0 s, como esperado pelo `EXIT_GRACE`.
- Depois disso, a guarda inalcançável do driver foi retirada; os 68 testes
  do driver e a matriz completa foram rodados de novo, **uma vez**, sobre a
  fonte final: **509 testes, 502 aprovados, 0 falhas, 0 erros, 7 skips**,
  exit 0, 32,1 s.
- Estruturais (6 arquivos): **154/154**.
- `ruff check`, `ruff format --check` e `mypy src tests` (strict) limpos em
  208 fontes, inclusive nos arquivos do revisor.

**Não executados** (nenhum aprovado por omissão): suíte integral, PostgreSQL
16 real, wheel/sdist e runtime TLS moderno. Docker não foi iniciado. O
frontend não mudou.

#### Lote 3: listener PGWire (D-110)

**Estado:** implementado localmente, **sem commit**, aguardando revisão. O
bootstrap não foi feito: o listener não é composto nem ativado, e nenhum
módulo do produto importa `maskgw.pgwire`. Testes só em `127.0.0.1`, com
porta efêmera (`test_port=0`).

| arquivo | conteúdo |
|---|---|
| `src/maskgw/pgwire/listener.py` | `PgwireListener`: validação antes do bind, bind síncrono, acceptor, admissão, ownership D-107/D-108, reaper, `stop()` |
| `src/maskgw/pgwire/settings.py` | `validate(settings)` para settings injetados; `_bind_kind` compartilhado |
| `tests/pgwire_listener_support.py` | só teste: fixture que sempre para e recolhe, injeção de falha no `start()` de uma thread nomeada |
| `tests/test_pgwire_listener.py` | 44 testes |
| `tests/test_pgwire_listener_interop.py` | 5 testes (libpq 18.0.3 real, sem query) |
| `tests/test_pgwire_listener_increment_review.py` | 2 contraprovas do revisor; **não** escrito nem alterado aqui |

**O que os testes provam (2026-10-09, Windows nativo):**

- **Configuração antes do bind:** 10 settings injetados inválidos (porta 0 e
  65536, hostname sem marca, marca sem hostname, sessões 0, idle booleano,
  senha vazia, usuário longo, `0.0.0.0` sem TLS, cert sem chave) dão
  `ConfigError` sem criar socket. Também falham antes do bind:
  - TLS incoerente com as settings;
  - TLS ausente para `127.0.0.2`, `::ffff:127.0.0.1` e `localhost`;
  - porta de teste diferente de 0;
  - hostname sem colaborador, com lista vazia, com dois endereços, com um
    nome em vez de literal, ou com uma string;
  - endereço resolvido para bind literal.
- **Hostname com literal resolvido:** bind com `AI_NUMERICHOST` e
  `gethostbyname` proibido; TLS obrigatório recusa o startup em claro com
  `08P01`. Construir o listener com `MASKGW_PGWIRE_ENABLED=1` no ambiente não
  cria thread nem socket.
- **Ciclo:** autenticação, `Terminate`, recolhimento a zero; threads não
  daemon; `start` único; `stop` idempotente; porta fechada depois do `stop`.
- **Admissão:**
  - com P=1, a segunda conexão recebe `53300` sem thread nova;
  - com P=2 e S=1, 3 extras recusadas e no máximo `1 + P + S` threads;
  - sessão autenticada passa de pré-auth para auth, e uma segunda prova sem
    vaga S recebe só `53300`;
  - bucket com relógio falso (burst 2, recarga 1/s): a terceira tentativa,
    com EOF imediato, recebe `53300`; depois de +1 s há uma admissão, e a
    seguinte é recusada.
- **Ownership:**
  - `start()` de conexão que falha antes de rodar: `broken`, socket fechado
    pelo dono, vaga e registro retidos sem prova, nenhuma admissão nova,
    `stop()` repetido continua `incomplete`;
  - `start()` que falha com o alvo retido: cancelado sem entrar (o driver
    nunca é chamado) e recolhido depois;
  - `start()` que falha depois de rodar: recolhido, `stopped`;
  - acceptor que não inicia: `broken`, depois `incomplete` em dois `stop()`;
  - acceptor que falha depois de rodar: `stopped`;
  - `close()` falho retém o registro e quebra;
  - falha inesperada na admissão quebra e fecha o socket não adotado;
  - exceção do driver não chega ao `excepthook`;
  - auto-parada a partir do callback de alias é recusada antes de qualquer
    efeito, e o listener segue `running`.
- **Parada:** `stop()` termina em menos de 3 s e `stopped`:
  - durante o cabeçalho, o TLS truncado, o gotejamento e com um peer que não
    lê;
  - com uma sessão pré-auth e outra autenticada, ambas encerradas;
  - na corrida entre accept e stop, com conexões em martelo.
- **Isolamento:** o módulo não importa `logging`, `maskgw.runtime`,
  `maskgw.db`, `maskgw.datasource`, `maskgw.bootstrap`, `maskgw.audit` nem
  `psycopg`, e não usa `environ`, `getenv`, `print(`, `wrap_socket(` nem
  `daemon=True`. As threads observadas são só `maskgw-pgwire-acceptor` e
  `maskgw-pgwire-connection`.
- **libpq real:**
  - SHA-256 sem TLS; -PLUS com `channel_binding=require`; `verify-full` com
    a CA de teste;
  - senha errada e alias inexistente com `authentication failed`, sem a
    senha nem o alias;
  - S=1 esgotado dá `too many connections`;
  - `stop()` com sessão autenticada aberta: `stopped`, e o cliente recebe
    EOF.

**Contraprovas do revisor neste lote** (arquivo nunca alterado aqui):

| achado | correção | resultado |
|---|---|---|
| um `stop()` durante um `start()` em voo, com o bind ainda podendo criar o socket, declarava `stopped` | `start()` em voo impede o `stop()` de concluir (`incomplete`); com a parada pedida durante o bind, o `start()` desfaz o socket e não inicia o acceptor; o `stop()` seguinte conclui | falhava antes; passa |
| um `accept()` com exceção que não é `OSError` matava o acceptor em silêncio, e o estado continuava `running` | qualquer exceção do `accept()` ou da admissão leva a `broken`; o socket não adotado é fechado pelo dono (teste próprio com o relógio do bucket lançando) | falhava antes; passa |

**Comandos:**
- Lotes focados, nesta ordem: configuração, ciclo e admissão (27/27);
  ownership (8/8); parada, isolamento e o `close()` falho repetido (10/10,
  dois deles depois substituídos por um teste real de nomes de thread);
  interop (5/5); os dois arquivos do listener juntos (48/48). Depois das
  correções das contraprovas: listener, interop e revisor (50/50), mais o
  teste novo de falha na admissão (1/1).
- Primeira matriz completa (histórica): **559 testes, 2 falhas**, só as duas
  contraprovas novas do revisor, em 39,9 s. Elas foram investigadas
  isoladas, sem repetir a matriz.
- Matriz final, sobre a fonte final, **uma vez**: `pytest
  tests/test_pgwire*.py` (16 arquivos por glob), com JUnit fora do checkout:
  **560 testes, 553 aprovados, 0 falhas, 0 erros, 7 skips de plataforma**,
  exit 0, 38,2 s.
- Estruturais: **154/154** (6,2 s).
- `ruff check`, `ruff format --check` e `mypy src tests` (strict) limpos em
  213 fontes, inclusive nos arquivos do revisor.

**Não executados** (nenhum aprovado por omissão): suíte integral, PostgreSQL
16 real, wheel/sdist e runtime TLS moderno. Docker não foi iniciado. O
frontend não mudou. Bootstrap e a resolução limitada de hostname no
composition root seguem pendentes.

#### Lote 4: integração interna no composition root (D-110)

**Estado:** implementado localmente, **sem commit**, aguardando revisão. Só
existe a composição interna (`build_application(pgwire=...)`); o `main`
recusa a ativação. O MCP continua o legado, em stdio e com
`query_database(sql)`.

| arquivo | conteúdo |
|---|---|
| `src/maskgw/pgwire/composition.py` (novo) | `PgwireComposition`, `prepare_pgwire`, `session_limits`, `sealed_alias_check`, `build_listener` |
| `src/maskgw/pgwire/listener.py` | `request_stop()`: barreira curta, idempotente, sem `join` |
| `src/maskgw/bootstrap/application.py` | parâmetro `pgwire`, `pgwire_listener`, preparo antes de efeitos, adoção antes do `start`, `_quiesce` com todas as admissões antes da drenagem, catálogo retido sem prova, `_unwind_partial` com retenção forte e fechamento da v1 |
| `src/maskgw/bootstrap/main.py`, `src/maskgw/bootstrap/settings.py` | recusa de `MASKGW_PGWIRE_ENABLED=1` como primeira flag lida via `RawSettings` (o `MASKGW_CONFIG` já era lido antes, só para o caminho), sem importar `pgwire` |
| `tests/test_pgwire_bootstrap.py` (novo) | 22 testes |
| `tests/test_pgwire_listener.py` | +2 (`request_stop`) |
| `tests/test_admin_ui_startup.py` (rastreado) | fake de `RawSettings` passa a responder por nome; asserção da ordem de leitura |
| `tests/test_pgwire_bootstrap_increment_review.py` | 9 contraprovas do revisor; **não** alteradas por esta implementação (ver o registro abaixo) |

**O que os testes provam (2026-10-12, Windows nativo):**

- **Legado:** sem `pgwire`, um subprocesso com `build_application` e
  `import maskgw.bootstrap.main` não carrega nenhum módulo `maskgw.pgwire`.
- **`main` com flag exata `1`**, em subprocesso:
  - exit 1, stderr só com o `STARTUP_FAILURE`, stdout vazio, nenhum módulo
    `maskgw.pgwire` carregado e a senha-canário ausente;
  - pelo revisor, a única leitura é a flag, e admin e construção não são
    chamados.
- **Flag não exata** (`None`, `0`, `true`, `" 1"`, `"1 "`, `01`, vazio):
  legado intacto, sem nenhuma outra leitura PGWire (revisor).
- **Antes de qualquer efeito:** `pgwire` sem catálogo, settings injetados
  inválidos, porta de teste ≠ 0, endereço resolvido para bind literal,
  hostname sem literal resolvido ou com nome, e TLS com arquivos inexistentes
  falham sem abrir o catálogo e sem preparar o principal.
- **Ordem medida:** `pgwire:tls`, `pgwire:principal`, `datasource:candidate`,
  `pgwire:start`, `mcp:build`; o legado conecta entre o catálogo e o listener.
- **Limites:** S=40 vira `RegistryLimits.max_sessions=40`, com aposentados e
  candidatos iguais aos defaults; sem `pgwire`, os limites são os defaults.
- **Alias:** com um serviço que só expõe `view()` (qualquer outro acesso
  reprova o teste), `crm` é aceito; `hml` (desabilitado), alias inexistente,
  `CRM` e selo indisponível são recusados.
- **libpq pelo listener composto:** handshake com `crm`, sem SQL; `hml` e
  alias inexistente recebem `authentication failed`, sem o alias; a senha não
  aparece no `repr` da aplicação.
- **Fechamento:** a barreira da fila v2 e o `request_stop` do listener
  acontecem antes da drenagem; a drenagem, antes do `stop` do listener; o
  `stop` do listener, antes do `close` do catálogo.
- **Parada incerta:** o catálogo não é fechado; a aplicação fica `closing`;
  `run()` é recusado; o segundo `close()` retenta, fecha o catálogo e chega a
  `closed`.
- **Recusa de `close()` a partir de thread PGWire:** a chamada vinda do
  callback de alias é recusada sem efeito, e o handshake conclui.
- **Startup parcial:**
  - `start()` que roda e lança: o erro original é propagado; nenhuma thread
    do listener fica viva; o catálogo é fechado com prova (reabrível) e nada
    fica retido;
  - com a parada também incerta: o erro original é preservado; o catálogo
    **não** é fechado; listener e catálogo ficam retidos;
  - pelo revisor: a seção crítica v1 fecha antes da drenagem v2.
- **`request_stop`:** sem espera (< 0,1 s), idempotente, estado `stopping`, e
  o `stop()` seguinte conclui `stopped`; antes do `start`, deixa o listener
  `stopped`.

**Contraprovas do revisor neste lote** (arquivo nunca alterado pela
implementação):

| contrato | medido antes | correção |
|---|---|---|
| flag exata `1` recusada antes de admin, secrets e construção, lendo só a flag; valores não exatos não leem outro setting PGWire (8 casos) | vermelhos antes da recusa no `main` | recusa como primeira leitura |
| startup parcial com PGWire fecha a seção crítica v1 antes de drenar a v2 | vermelho (`[False]`) | `_quiesce_partial` fecha `admin` junto com as demais admissões |

**Registro de procedimento (honesto):** durante esta rodada, um `ruff format
src tests` sobre a árvore inteira reformatou também
`tests/test_pgwire_bootstrap_increment_review.py`, uma linha só de
formatação. Restaurei o conteúdo lido no início da rodada; logo depois, o
revisor publicou uma versão nova do próprio arquivo, que é a vigente. Desde
então só formato arquivos meus, nominalmente.

**Comandos da rodada 1 do lote 4 (histórica — anterior à 10ª contraprova do
revisor, portanto NÃO é a fonte final atual):**
- Focados, nesta ordem: as 8 contraprovas de flag do revisor, vermelhas e
  depois 8/8; os 22 de `test_pgwire_bootstrap.py`, vermelhos (`TypeError`) e
  depois 22/22; o contrato v1 do revisor, vermelho e depois 9/9; bootstrap
  com listener e revisores, 77/77; `request_stop`, 2/2.
- Matriz `pytest tests/test_pgwire*.py`, 18 arquivos por glob, com JUnit fora
  do checkout: **593 testes, 586 aprovados, 0 falhas, 0 erros, 7 skips de
  plataforma**, exit 0, 45,8 s.
- Pertinentes (`test_bootstrap`, `test_datasource_bootstrap`,
  `test_admin_work_bootstrap`, `test_admin_work_queue`,
  `test_admin_http_lifecycle`, `test_admin_v2_lifecycle`, `test_mcp_server`,
  `test_admin_ui_startup`), pilha de 64 MiB, JUnit:
  - primeira rodada: 257 testes, **1 falha** (o fake de `RawSettings` acima);
  - depois do ajuste: **257 testes, 255 aprovados, 0 falhas, 2 skips** (o
    teste de integração que exige `MASKGW_TEST_DSN`, não executado aqui).
- Estruturais: **154/154**.
- `ruff check`, `ruff format --check` e `mypy src tests` (strict) limpos em
  216 fontes; `git diff --check` limpo.

**Revisão do lote 4, rodada 2 (atual).** O revisor acrescentou, durante a
rodada 1, a 10ª contraprova
`test_incomplete_close_keeps_catalog_owned_after_caller_drops_application`.
Foi reproduzida isolada, vermelha: depois de um `PgwireListener.stop`
incompleto e do descarte da `Application` pelo chamador, o `gc.collect`
destruía o dono do listener (o weakref morria). Com isso, o lock do catálogo
podia ser solto sem prova. A causa: o startup parcial já retinha os donos,
mas o fechamento normal não.

| achado | correção | prova |
|---|---|---|
| no `close()` normal com PGWire, nenhum dono forte ficava no ledger do processo | com PGWire, `close()` coloca a própria `Application` no ledger D-108 antes de qualquer passo falível (logo depois da recusa de auto-encerramento); retenção mantida sem prova ou com exceção no cleanup; solta só depois de `_closed`, com tudo provado; flag por instância contra duplicatas | contraprova do revisor 1/1 e depois 10/10. Testes próprios: `close()` bem-sucedido e repetido deixa o ledger vazio; duas novas tentativas sem prova retêm a `Application` **uma** vez e a terceira, com prova, solta; o auto-encerramento recusado não retém (ledger vazio no momento da recusa); sem PGWire, o ledger não é tocado |
| `composition.py` dizia "nenhum lock" | `service.view()` toma o `_view_lock` curto da referência do selo; o texto passa a dizer: sem lock do store nem da seção de escrita, sem filesystem, DNS ou upstream; não é lock-free | doc |
| o `main` dizia que a flag era a "primeira leitura" | o `MASKGW_CONFIG` já é lido antes, só para o caminho; o texto passa a dizer "primeira flag lida via `RawSettings`" | doc |

Fora deste recorte, e registrado para revisão: o mesmo vão existe, por
analogia, no fechamento normal com a fila v2 **sem** PGWire.

**Comandos da rodada 2 (fonte final atual), contagens tiradas do JUnit:**
- A contraprova nova, isolada: vermelha e depois verde.
- `tests/test_pgwire_bootstrap_increment_review.py`: **10 coletados, 10
  aprovados**.
- Bootstrap, listener, revisor do listener e interop do listener: **79
  coletados, 79 aprovados**.
- Matriz `pytest tests/test_pgwire*.py`, 18 arquivos por glob, uma vez:
  **598 coletados, 591 aprovados, 0 falhas, 0 erros, 7 skips de
  plataforma**, exit 0, 46,3 s; `test_pgwire_bootstrap` com 26 e o revisor
  com 10.
- Depois da matriz, só a ordenação de um import no meu
  `test_pgwire_bootstrap.py` (ruff I001); o arquivo foi rodado de novo:
  **26/26**.
- Pertinentes (os mesmos 8 arquivos, pilha de 64 MiB): **257 coletados, 255
  aprovados, 0 falhas, 2 skips** (`MASKGW_TEST_DSN`, não executado).
- Estruturais: **154/154**.
- `ruff check`, `ruff format --check` e `mypy src tests` (strict) limpos em
  216 fontes; `git diff --check` limpo. Formatados só arquivos desta
  implementação, nominalmente; nenhuma contraprova foi tocada.

**Não executados** (nenhum aprovado por omissão): suíte integral, PostgreSQL
16 real (inclusive os 2 testes de integração acima), wheel/sdist e runtime TLS
moderno. Docker não foi iniciado por esta implementação; ao fim da rodada 1 o
Docker Desktop estava em execução, sem contêineres, por ação externa, e não foi
alterado. O frontend não mudou. Pendentes: resolução limitada de hostname no
composition root, ativação operacional e full gate.

#### Gates finais do lote 4 (D-110, 2026-10-12, Windows nativo)

**Fonte congelada:** 224 arquivos funcionais (`src` sem `__pycache__` e sem o
`egg-info` gerado, `tests`, `pyproject.toml`, `MANIFEST.in`), 216 deles
Python, com o digest do conjunto `b56ba8cd…2d5f17f6`. Os hashes são
**idênticos** antes e depois de todos os gates. HEAD `886b023`, `master`;
nenhum stage, commit, fetch ou reset. O frontend e os recursos da UI não têm
diferença em relação ao HEAD.

**Ambiente:**
- **Runner:** `.venv/Scripts/python.exe` (Python 3.11.3, OpenSSL 1.1.1t),
  pilha de 64 MiB no próprio processo de teste e watchdog independente. No
  processo do runner, toda variável `MASKGW_*` e `PG*` herdada foi removida e
  só a `MASKGW_TEST_DSN` do contêiner descartável foi injetada. O ambiente
  persistente do usuário não mudou.
- **PostgreSQL 16.15** (`160015`) em contêiner e volume novos, com nome e
  label exclusivos (`maskgw.lote=d110-gates`), porta aleatória em
  `127.0.0.1`: UTF8, `TimeZone` UTC, `password_encryption=scram-sha-256`,
  role armazenada como `SCRAM-SHA-256` e `pg_hba` TCP só `scram-sha-256`. A
  senha aleatória ficou só num arquivo temporário e no ambiente do runner,
  nunca impressa; a varredura dela em todas as evidências não achou nada.
- **Docker:**
  - o Docker Desktop **já estava em execução** no início desta rodada (estado
    inicial preservado: não foi parado);
  - havia 0 contêineres, 17 volumes e 3 redes preexistentes;
  - no fim, contêineres, volumes e nomes de rede são iguais aos do início.
    Só o ID da rede padrão `bridge` mudou: ela foi recriada pelo daemon às
    21:12:36 locais, depois do retrato inicial e cerca de 16 s antes de o
    contêiner próprio se conectar, o que indica um reinício do motor dentro
    da VM. Os processos do Docker Desktop no Windows são de 2026-10-09, e os
    comandos desta rodada foram só `docker volume create`, `docker run`,
    `docker rm` e `docker volume rm`. **Causa não atribuída.**

| gate | resultado medido (contagens do JUnit) |
|---|---|
| suíte integral, sem deselect, ignore ou xfail | **4.949 coletados, 4.929 aprovados, 0 falhas, 0 erros, 20 skips só de plataforma** (5 `fsync` de diretório POSIX, 6 symlink indisponível, 9 bits de modo POSIX), **0 skips por DSN**, 707,9 s, exit 0 |
| seleção `-m integration` | **575 coletados, 572 aprovados, 0 falhas, 0 erros, 3 skips `fsync` POSIX, 0 por DSN**, 221,0 s, exit 0; inclui os 2 testes de bootstrap de datasource com PG real |
| build (cópia temporária: 111 arquivos de `src`, `pyproject.toml` e `MANIFEST.in` iguais ao congelado; `python -m build`) | wheel `maskgw-0.1.0-py3-none-any.whl` SHA-256 `16c42449bd08451d201be93bf6fa2c9d60c7ea802b041e820383b310c2bc338e` (113 entradas); sdist `maskgw-0.1.0.tar.gz` SHA-256 `ef9b244907e4395fbf3d562b55e6b57df7eebeeff5fa5e288752a3429b69bf0a` (139 entradas). Ambos com os 12 módulos `pgwire` (inclusive `composition`, `listener`, `driver`, `transport`) e sem `tests`, `docs`, `poc`, `frontend` ou `node_modules`; `Requires-Dist` com `scramp==1.4.17`, `asn1crypto==1.5.1` e `cryptography==50.0.1` |
| dependências | restrições da `.venv`; `scramp-1.4.17` (`a4e3fd2e…474ac8`) e `asn1crypto-1.5.1` (`db4e4072…f8fd67`) com SHA-256 iguais aos do desenho |
| instalação | duas venvs novas e separadas, com o **mesmo** Python base 3.11.3, fora do checkout; `.venv` intocada; exit 0 nas duas |
| sonda do pacote (`python -I`, sem `PYTHONPATH`, `PATH` só System32, sem Node/npm, cwd fora do checkout) | **wheel 165/165, sdist 165/165**, exit 0 |
| contraprovas da sonda | `checkout`: 141/165 (origens e `embarcado_*`; com o `src/` do checkout no caminho, a metadata passa a vir do `egg-info` do checkout); `tls`: 164/165 (`verify_full_com_a_ca`); `binding`: 163/165 (`plus_channel_binding_require`, `verify_full_com_a_ca`). Exit 1 nos 6 casos (3 por pacote) |

**O que a sonda verifica nos dois pacotes:**
- **Origem:** `maskgw`, bootstrap, verificador, fila v2 e os 12 módulos
  `pgwire` vêm de `Lib/site-packages` da venv e não do checkout; `scramp`,
  `asn1crypto` e `psycopg` também vêm da venv.
- **Hashes:** 104 fontes Python instaladas iguais às congeladas.
- **UI:** os 4 recursos validados pelo `load_resources()` (`index.html`,
  `presentation.json`, `ui.css`, `ui.js`) iguais aos do checkout.
- **`main` em subprocesso `-I`:** com `MASKGW_PGWIRE_ENABLED=1`, exit 1,
  stderr só com o `STARTUP_FAILURE`, stdout vazio e nenhum módulo
  `maskgw.pgwire` carregado. O legado (`build_application` contra o PG16
  real, sem `pgwire`) não carrega `maskgw.pgwire`.
- **Composição interna real**, `build_application(pgwire=..., datasource_catalog=..., admin_http=...)`:
  - catálogo cifrado novo, com o verificador de produção em processo filho
    `-I` do pacote;
  - S=40 também no registry;
  - antes da publicação, o alias `crm` é recusado (`28P01`);
  - `POST /admin/v2/datasources` publica o `crm` (200), verificado pelo filho
    contra o PG16, e o selo passa a conter o alias;
  - **libpq 18.0.3 pelo listener:** SCRAM-SHA-256 sem TLS; -PLUS com
    `channel_binding=require`; `verify-full` com a CA de teste. A outra CA,
    a senha errada e o alias inexistente são recusados, os dois últimos com
    `authentication failed`;
  - conexões recolhidas a 0. Nenhuma query foi enviada pelo PGWire; cada
    sessão terminou com `Terminate`;
  - no fechamento: aplicação `closed`, listener `stopped`, aplicação ausente
    do ledger, nenhuma thread do listener ou da fila viva, catálogo
    reabrível e diretório próprio da sonda removido.

**Limpeza:**
- **Removidos:** contêiner e volume próprios (nome e label conferidos antes),
  o arquivo de credencial, as duas venvs, a cópia da fonte e o wheelhouse
  (alvo absoluto conferido antes).
- **Preservados**, fora do repositório, em
  `%LOCALAPPDATA%\Temp\maskgw-d110-gates\`: JUnit, logs, JSON da sonda, os
  dois pacotes, hashes e roteiros, sem segredo.
- **Não houve:** processo bloqueado nem processo encerrado. O Docker segue em
  execução, como estava.

**Não validados por estes gates** (nenhum aprovado por omissão):
- runtime TLS moderno (o servidor TLS medido é o Python ssl com OpenSSL
  1.1.1t, fora de suporte);
- execução em POSIX;
- resolução limitada de hostname no composition root;
- ativação operacional.

O risco análogo de GC no fechamento normal com a fila v2 sem PGWire fica para
revisão separada. A Etapa 7 e a Fase 9 **não** estão concluídas, e ativação e
produção seguem proibidas.

#### Runtime moderno — lote A (D-110, 2026-10-13, Windows nativo)

**Autoridade:** em 2026-10-13 o usuário aprovou um Python moderno em ambiente
**temporário e isolado**, só para validação de runtime: extração do pacote
oficial num diretório temporário fora do checkout, sem instalador, MSIX,
winget, `py install`, PATH, registro, associações nem configuração global. A
`.venv` e o Python atual ficam intocados. Não houve deploy, ativação, commit,
push nem Etapa 8+. Este lote não usou banco nem Docker.

**Procedência, verificada ANTES de executar:**
- **Pacote:** `python` 3.14.8, autor "Python Software Foundation", listado,
  publicado em 2026-09-30T19:53:06Z. Baixado por HTTPS de
  `api.nuget.org/v3-flatcontainer`, com a verificação TLS padrão.
  - Tamanho 15.554.015 bytes, igual ao do catálogo.
  - SHA512 igual ao `packageHash` publicado no catálogo do nuget.org.
  - SHA256 local
    `ce85f674d9a63029f709cbff7a3da1c6bc5bfcfaefdd9999f98fa0290470c454`.
  - O hash prova só integridade.
- **Ferramenta de verificação:** `nuget.exe` 7.9.0.83 oficial
  (`dist.nuget.org`), com Authenticode `Valid` de `CN=Microsoft Corporation`
  (emissor `Microsoft Code Signing PCA 2024`, carimbo de tempo da Microsoft),
  conferido antes de rodar. Rodou com um `NuGet.Config` isolado; a
  configuração NuGet do usuário continuou inexistente.
- **Assinatura:** `nuget.exe verify -Signatures` concluiu "verificado com
  êxito". A assinatura é só de **repositório**, de `CN=NuGet.org Repository
  by Microsoft`, com cadeia até a `DigiCert Trusted Root G4` e carimbo de
  tempo DigiCert de 2026-09-30. O pacote **não** traz assinatura de autor.
- **Executáveis:** `tools/python.exe`, `python314.dll`, `_ssl.pyd`,
  `libssl-3.dll` e `libcrypto-3.dll` com Authenticode `Valid` de
  `CN=Python Software Foundation` (emissor `Microsoft ID Verified CS EOC CA
  03`); `libssl-3` e `libcrypto-3` na versão 3.5.9.
- **Extração validada:** 1.382 entradas aceitas e 0 recusadas (caminho
  absoluto, drive, `..`, symlink ou fuga do destino seriam recusados); nenhum
  link ou reparse point extraído.

**Perfil medido do runtime** (invocado só pelo caminho absoluto, com `-I`):
- CPython **3.14.8 final**
  (`tags/v3.14.8:8e6e75d, Sep 30 2026, MSC v.1944 64 bit (AMD64)`), AMD64.
- **GIL ativo**, build **não** free-threaded.
- `ssl` da stdlib do próprio runtime (`tools/Lib/ssl.py`,
  `tools/DLLs/_ssl.pyd`) com **OpenSSL 3.5.9 29 Sep 2026**, TLS 1.2 e 1.3
  disponíveis.
- `venv` e `ensurepip` disponíveis.
- Bibliotecas TLS distintas, registradas para não se confundirem:
  - o **servidor** TLS do produto usa o `ssl` da stdlib (OpenSSL 3.5.9);
  - o cliente dos testes é o libpq 18.0.3 do `psycopg-binary`;
  - o `cryptography` 50.0.1 embute um OpenSSL próprio (4.0.2), usado só
    para X.509.
- Este perfil não certifica qualquer outra versão 3.14.

**Venv temporária** (`venv` + `ensurepip` oficiais; pip 26.2.1), fora do
checkout; a `.venv` não foi usada:
- dry-run só com binários (`--only-binary=:all:`) e as restrições da `.venv`:
  51 pacotes, **todos com a mesma versão da `.venv`**. Os nativos têm wheels
  `cp314` (`pglast`, `psycopg-binary`, `pydantic_core`, `PyYAML`, `mypy`,
  `cffi`, `pywin32`, `rpds-py`, `librt`) e o `cryptography` usa `abi3`. Nada
  foi compilado nem atualizado; `build` e `pyproject-hooks` ficaram de fora;
- instalação dos mesmos 51, com exit 0.

**Testes** (`python -m pytest` da venv 3.14, a partir do checkout, sem
`MASKGW_*`/`PG*`, `PYTHONDONTWRITEBYTECODE=1`, JUnit fora do checkout):

| lote | coletados | resultado |
|---|---|---|
| peças puras (framing, scram, settings, channel binding, revisor D-109) | 305 | 305 aprovados |
| TLS, transporte, driver e revisores | 169 | 162 aprovados, 0 falhas, 7 skips de plataforma (6 de bits POSIX, 1 de symlink) |
| interop libpq, listener, bootstrap e revisores | 124 | 124 aprovados |
| matriz `tests/test_pgwire*.py`, 18 arquivos por glob, uma vez | **598** | **591 aprovados, 0 falhas, 0 erros, 7 skips de plataforma**, 42,4 s |

**Sonda de versões TLS** (temporária, fora do checkout; listener com a fonte
do checkout em `127.0.0.1` com porta efêmera; libpq real; sem SQL):
- **Aceitos:** SCRAM-SHA-256-PLUS com `channel_binding=require` no padrão,
  com `ssl_min_protocol_version=TLSv1.3` e com
  `ssl_max_protocol_version=TLSv1.2`; `verify-full` com a CA de teste em
  TLS 1.3 e em TLS 1.2. O libpq recusa conexões fora desses limites, o que
  prova a versão negociada; o psycopg 3.3.4 não expõe `PQsslAttribute`.
- **Recusados:** cliente com no máximo TLS 1.1; senha errada sobre TLS 1.3,
  com `authentication failed`.
- **Fechamento:** listener `stopped` e nenhuma thread restante.
- **Primeira execução da sonda:** falhou por defeito da própria sonda, que
  usava `ssl_attribute`, inexistente no psycopg 3.3.4; o watchdog encerrou o
  processo (código 97). O diretório de certificados de teste que ela deixou
  foi removido pelo caminho exato.

**Estática na venv 3.14** (só check; caches fora do checkout):
- `ruff check` limpo; `ruff format --check` com 216 arquivos já formatados;
- `mypy` 2.3.1 strict **limpo em 216 fontes com o alvo configurado
  (`python_version = 3.11`)**;
- informativo, sem mudar configuração, com `--python-version 3.14`: **4
  erros** `union-attr` em `src/maskgw/datasource/destination.py` (acesso a
  `ipv4_mapped` depois de `address.version == _IPV6`, que os stubs para 3.14
  não estreitam). O comportamento em tempo de execução, medido, é idêntico no
  3.11.3 e no 3.14.8. **Relatado, não corrigido.**

**Estado preservado (comparado com o retrato inicial):**
- iguais: 224 hashes funcionais (216 Python); `pyvenv.cfg`, `python.exe` e
  dependências da `.venv`; `py -0p` (só o 3.11); PATH de usuário e de
  máquina; associação `.py`; chaves `Python` do registro;
- a configuração NuGet do usuário continua inexistente; HEAD `886b023`.
- **Desvio corrigido:** a sonda, rodando com `-I` (que ignora
  `PYTHONDONTWRITEBYTECODE`), gravou 82 `*.cpython-314.pyc` em `__pycache__`
  do checkout. São artefatos gerados e ignorados pelo Git. Foram removidos
  pela lista exata (todos de 2026-10-13); os 217 `.pyc` do 3.11 preexistentes
  ficaram, e `.mypy_cache`/`.ruff_cache` não receberam nenhum arquivo.

**Recursos temporários retidos para o lote B** (removidos seletivamente ao
fim dele), em `%LOCALAPPDATA%\Temp\maskgw-py314-lotA\`:
- `runtime/python-3.14.8/` (pacote extraído), `venv314/`, `download/` (o
  `.nupkg` e a metadata), `tools/nuget.exe`;
- as evidências não secretas: JUnit, logs, perfil, versões TLS e hashes.

**Não validado neste lote:** suíte integral e `integration` com PG16 real,
wheel e sdist no 3.14 (lote B), POSIX, resolução limitada de hostname,
ativação operacional e D-090 gate 2. A Etapa 7 e a Fase 9 **não** estão
concluídas.

#### Runtime moderno — lote B (D-110, 2026-10-13, Windows nativo)

**Escopo:** o mesmo runtime e a mesma venv temporária do lote A (CPython
3.14.8 x64 com GIL, `ssl` da stdlib com OpenSSL 3.5.9), agora com PG16 real e
os pacotes retidos. Sem mudança de produto, testes ou dependências. HEAD
`886b023`. Fonte congelada: 224 arquivos funcionais (216 Python), digest
`b56ba8cd56f2d1d1e639e610a9a5c3bd3bee599e163338606fa4f3ef2d5f17f6`.
Toda invocação isolada usou `-I -B`.

**Código instalado para os filhos `-I`:** a suíte inicia filhos com `-I`, que
importam `maskgw` do site-packages. Na venv 3.14 foi instalada a wheel retida
(SHA-256 `16c42449…c338e`, conferido antes), sem dependências; os 109
arquivos de `src/maskgw` instalados têm hashes iguais aos do checkout. Não
houve instalação editável.

**PG16 próprio:** contêiner e volume novos com label exclusiva
(`maskgw.lote=py314-lotb`), porta efêmera em `127.0.0.1`, PostgreSQL 16.15
(`160015`), UTF8, `TimeZone` UTC, `scram-sha-256`. A senha aleatória ficou só
num arquivo temporário próprio e no ambiente do runner; a varredura dela em
JSON, stderr, logs e JUnit não achou nada.

**Runner** (temporário, fora do checkout): remove `MASKGW_*` e `PG*` herdados
no próprio processo, injeta só `MASKGW_TEST_DSN`, define
`PYTHONDONTWRITEBYTECODE=1`, roda o pytest numa thread com pilha de 64 MiB e
tem watchdog independente de 3.000 s. Sem deselect, ignore, xfail ou skip
novo.

**Histórico da suíte integral:**
- **Rodada 1, interrompida (iniciada depois das 09:05 locais).** Fatos
  medidos durante a execução:
  - a rede `bridge` passou de `90e9ab9b7c61` para `a3a6994adc56`;
  - o buffer de eventos do daemon ficou vazio;
  - o contêiner PG próprio saiu com 255 às 09:19:40 locais, sem OOM;
  - a suíte parou em ~75%, no início de `test_mcp_integration`, com `EEE`.

  Esses fatos são **indícios** de um reinício do motor do Docker. Não há
  evidência direta salva desse reinício, e ele é uma inferência, não um fato
  medido. **Causa da interrupção não atribuída.**
  Encerrei só o runner próprio, conferindo PID, executável e linha de
  comando; o log foi preservado (`suite-full-rodada1-comprometida.log`). O
  mesmo contêiner foi reiniciado (`docker start`), a nova porta e a
  estabilidade da `bridge` foram conferidas, e a rodada 2 foi executada uma
  única vez.
- **Rodada 2 (epochs 1791894156–1791894832):** **4.949 coletados, 4.927
  aprovados, 2 falhas, 0 erros, 20 skips só de plataforma** (9 bits de modo
  POSIX, 6 symlink indisponível, 5 `fsync` de diretório POSIX), **0 skips por
  DSN**, 671,2 s, exit 1.
- **As 2 falhas:** `test_exact_raw_flag[True-1\x00]` e
  `test_process_uses_raw_flag_without_querying_secret_provider[1\x00]`, em
  `tests/test_admin_ui_startup.py`. Ambas com `ValueError: embedded null
  character` no `monkeypatch.setenv`, **antes** de chegar ao Gateway: o
  CPython 3.14.8 no Windows recusa NUL em `os.environ`/`putenv`, e o 3.11.3
  aceitava. Diagnóstico focado nos dois testes: 48 coletados, 46 aprovados e
  as mesmas 2 falhas. Relatadas sem correção, skip ou mudança de produto; a
  correção veio só no lote C, com autorização.

**Demais gates medidos no lote B:**

| gate | resultado medido |
|---|---|
| seleção `-m integration` | **575 coletados, 572 aprovados, 0 falhas, 0 erros, 3 skips `fsync` POSIX, 0 por DSN**, 231,2 s, exit 0 |
| wheel e sdist retidos (SHA-256 conferido antes), cada um numa venv 3.14 nova fora do checkout, com as dependências fixadas do lote A, sem atualização | instalação exit 0; dependências de runtime iguais às do lote A; só `packaging` ausente, por ser exigido apenas pelas ferramentas de desenvolvimento |
| sonda do pacote (`-I -B`, sem `PYTHONPATH`, sem Node/npm), com os checks novos `runtime_3_14_8`, `ssl_stdlib_do_runtime` e `ssl_openssl_3_5_9` | **wheel 168/168, sdist 168/168**, exit 0. Origem em `Lib/site-packages`, 104 fontes iguais às congeladas, 4 recursos da UI, `POST /admin/v2/datasources` 200 com o verificador filho, libpq 18.0.3, SCRAM, -PLUS e `verify-full` pelo listener, sem SQL pelo PGWire |
| contraprovas da sonda, nos dois pacotes | `checkout` 144/168 (`embarcado_*`, `origem_*`); `tls` 167/168 (`verify_full_com_a_ca`); `binding` 166/168 (`plus_channel_binding_require`, `verify_full_com_a_ca`). Exit 1 nos 6 casos |
| estática (venv 3.14, só check, caches fora do checkout) | `ruff check` limpo; `ruff format --check` com 216 arquivos já formatados; mypy strict com o alvo configurado 3.11 limpo em 216 fontes; informativo `--python-version 3.14`: os mesmos **4 `union-attr`** em `datasource/destination.py`, **não corrigidos** |

**Bytecode no checkout:** depois da rodada 1 havia 71 `*.cpython-314.pyc` em
`__pycache__` de `src/maskgw` e `tests`, todos de 09:11 locais. O conjunto
corresponde aos imports do filho de `tests/test_admin_v2_http.py`, que é
iniciado com ambiente mínimo (só `PYTHONPATH` e `SYSTEMROOT`), sem `-I`/`-B`
e sem herdar `PYTHONDONTWRITEBYTECODE`. São artefatos gerados e ignorados pelo
Git. Foram removidos pela lista exata; nenhum `__pycache__` ficou vazio, e os
`.pyc` do 3.11 preexistentes ficaram.

**Fonte preservada:** os 224 hashes funcionais ficaram iguais ao retrato
inicial (digest `b56ba8cd…f17f6`). O `src/maskgw.egg-info` é de 2026-10-02,
anterior ao lote, ignorado pelo Git e não foi tocado.

**Limpeza:** contêiner e volume próprios (nome e label conferidos), o arquivo
de credencial, as venvs dos pacotes e o diretório temporário delas, os caches
do mypy, e do lote A o runtime extraído, a venv 3.14, o download e o
`nuget.exe` com a config isolada. Cada alvo absoluto teve o pai exato
conferido e nenhum symlink ou reparse point na árvore antes da remoção; 12
alvos removidos e nenhuma recusa (`cleanup.log`). Preservados: evidências não
secretas e os pacotes originais em `maskgw-d110-gates/packages`.

**Docker:** estava **parado** no início do lote (0 processos, daemon
parado). Foi iniciado só para a medição e devolvido ao estado parado
(`docker desktop stop`; depois, 0 processos e daemon parado). Contêineres e
volumes no fim iguais aos do início, ignorando a ordem. O ID da `bridge`
mudou na rodada 1, como descrito; causa não atribuída. A imagem
`postgres:16-alpine` (`cf78e766…`) já existia (tag de 2026-09-08) e ficou.

**Host:**
- iguais ao início: `pyvenv.cfg` e `python.exe` da `.venv`; `py -0p` (só o
  3.11); associação `.py`/`Python.File`; entradas e ordem do PATH do usuário;
  configuração NuGet do usuário inexistente;
- **PATH da máquina:** as mesmas 18 entradas, mas em outra ordem
  (`C:\Program Files\WSL\` passou da 15ª para a última posição). **Causa
  desconhecida.** A validação não restaurou nem editou manualmente o PATH;
- **registro:** o inventário final usou um escopo de consulta maior que o
  inicial (incluiu `HKLM\Software\WOW6432Node\Python`) e por isso listou a
  chave `PyLauncher`, ausente do inventário inicial. **Não está provado que
  houve mutação.**

#### Runtime moderno — lote C (D-110, 2026-10-13, Windows nativo)

**Autoridade:** o usuário autorizou adaptar **somente** os dois testes de NUL,
mantendo a cobertura e sem skip novo. O incremento foi aprovado em revisão
independente. A revalidação no runtime moderno temporário faz parte dessa
correção de teste autorizada e se apoia na autorização anterior de runtime
temporário e isolado (2026-10-13); não é uma nova aprovação do usuário. Sem
mudança de produto, dependências ou artefatos de pacote; sem instalação no
sistema, ativação, commit ou push. HEAD `886b023`.

**Correção só de teste** (`tests/test_admin_ui_startup.py`):
- **Por que mudou:** a montagem dos casos `1\x00` usava
  `monkeypatch.setenv`, e o CPython 3.14.8 no Windows recusa NUL em variável
  de ambiente (`ValueError: embedded null character`); o 3.11.3 aceita. Medido
  nos dois runtimes: no 3.14.8 a recusa deixa a variável ausente; no 3.11.3 o
  valor é aceito e lido de volta.
- **Helper `_setenv_or_os_refusal`:** só trata como recusa do SO um
  `ValueError` com mensagem exata `embedded null character`, para valor que
  contém NUL, e exige que a variável continue ausente (lido pelo
  `EnvRawSettings` real). Qualquer outro `ValueError` propaga.
- **`test_exact_raw_flag`:** com o SO aceitando, a variante de ambiente usa o
  `EnvRawSettings` real, como antes. Na recusa, o mesmo valor bruto é
  injetado por `MappingRawSettings`. As asserções não mudaram: valor exato
  em `get_raw`, e a UI só liga com exatamente `"1"`.
- **`test_process_uses_raw_flag_without_querying_secret_provider`:** na
  recusa, o `main` recebe o valor bruto por `raw_settings`. Continuam
  valendo a guarda que impede consultar o `SecretProvider` pela flag, o
  resultado `value == "1"` e o stderr exato.
- **O que não mudou:** `RAW_VALUES`, todos os casos sem NUL, a normalização
  de secrets e ambiente, e a regra de exatamente um valor. Não há skip, xfail
  nem checagem de versão.
- **Alcance:** no 3.14 o NUL é exercitado como setting bruto **injetado**,
  porque não chega ao ambiente. Isso **não** prova que a aplicação lê NUL do
  ambiente no 3.14. O ramo de recusa só roda onde o SO recusa; no 3.11.3 o
  caminho continua sendo o `EnvRawSettings` real.
- **Medido no 3.11.3 da `.venv`, antes da revisão:**
  - `test_admin_ui_startup.py` 90/90; os dois testes 48/48; adjacentes de
    bootstrap e PGWire 181/181;
  - ruff limpo; mypy strict com o alvo configurado limpo em 216 fontes;
  - só esse arquivo mudou entre os 224 funcionais; o diff anterior da D-110
    no mesmo arquivo ficou preservado.
- **Revisão independente:** aprovou o incremento depois de seis contraprovas
  no 3.11:
  - a recusa forçada de NUL pelo SO passa nos dois testes;
  - um `ValueError` inesperado e a recusa de valor sem NUL propagam;
  - habilitar deliberadamente a UI para NUL faz cada teste falhar.

**Fonte congelada do lote C:** 224 arquivos funcionais (216 Python), digest
`c7019c55c24bc7e4c6b835c19a70554400892a3ae4ed47b306cc36a5c416774d`.
Diferem do lote B só em `tests/test_admin_ui_startup.py` (SHA-256
`7bb4c714…e1c2`). No fim, todos os 224 hashes estavam iguais.

**Procedência do runtime, verificada de novo antes de executar** (diretório
novo, exclusivo do lote C):
- **Pacote:** `python` 3.14.8 do nuget.org (catálogo
  `2026.09.30.20.00.00`; autor "Python Software Foundation"; listado;
  publicado em 2026-09-30T19:53:06.703Z). Baixado por HTTPS.
  - Tamanho 15.554.015 bytes, igual ao do catálogo.
  - SHA512 igual ao `packageHash` do catálogo.
  - SHA-256 `ce85f674…c454`, igual ao do lote A.
- **`nuget.exe` 7.9.0.83** (`dist.nuget.org`, SHA-256 `992d70ca…b800`):
  Authenticode `Valid` de `CN=Microsoft Corporation`, emissor `Microsoft Code
  Signing PCA 2024`, conferido antes de rodar. Usou um `NuGet.Config` isolado.
- **Assinatura:** `verify -Signatures` "verificado com êxito", só de
  repositório (`CN=NuGet.org Repository by Microsoft`), com cadeia até a
  `DigiCert Trusted Root G4`, carimbo DigiCert de 2026-09-30 e nenhum `NU3`.
- **Extração validada:** 1.382 entradas aceitas, 0 recusadas, 0 com conteúdo
  divergente do zip e 0 reparse points.
- **Authenticode dos binários:** `Valid`, `CN=Python Software Foundation`.
  - Emissor `Microsoft ID Verified CS EOC CA 03`: `python.exe`,
    `python314.dll`, `python3.dll`, `_ssl.pyd` e `_hashlib.pyd`, versão
    3.14.8.
  - Emissor `Microsoft ID Verified CS AOC CA 04`: `libssl-3.dll` e
    `libcrypto-3.dll`, versão 3.5.9. Esse emissor foi medido agora; a
    evidência do lote A citava um só emissor para o conjunto.

**Perfil exato** (`-I -B`): CPython **3.14.8 final**
(`tags/v3.14.8:8e6e75d, Sep 30 2026, 18:19:33) [MSC v.1944 64 bit (AMD64)]`),
AMD64, **GIL ativo**, não free-threaded. `ssl` da stdlib do próprio runtime
(`tools/Lib/ssl.py`, `tools/DLLs/_ssl.pyd`) com **OpenSSL 3.5.9 29 Sep 2026**
(`(3, 5, 0, 9, 0)`), TLS 1.2 e 1.3. Cliente dos testes: libpq 18.0.3 do
`psycopg-binary`. O `cryptography` 50.0.1 traz OpenSSL próprio, usado só para
X.509.

**Venv temporária** (fora do checkout):
- pip 26.2.1 com `--isolated --no-cache-dir --only-binary=:all:`: o cache e a
  configuração do pip do usuário não foram usados. Restrições e requisitos
  retidos do lote A;
- dry-run com os mesmos 51 pacotes e versões do lote A; instalação exit 0;
  nada compilado; freeze idêntico ao do lote A;
- para os filhos `-I`, a wheel retida (`16c42449…c338e`, conferida antes)
  instalada sem dependências; os 109 arquivos de `src/maskgw` iguais aos do
  checkout. Nenhum pacote foi reconstruído.

**Testes focados no 3.14.8 real**, pelo runner (sem `MASKGW_*`/`PG*`, sem
DSN):
- `tests/test_admin_ui_startup.py`: **90 coletados, 90 aprovados**, 0 falhas,
  0 skips, 7,6 s. Inclui os três casos `1\x00`:
  - `test_exact_raw_flag[True-1\x00]` e
    `test_process_uses_raw_flag_without_querying_secret_provider[1\x00]`
    exercitam a recusa real do SO e, em seguida, a injeção;
  - `test_exact_raw_flag[False-1\x00]` usa só `MappingRawSettings`, como
    antes, sem passar pelo ambiente;
- adjacentes (`test_pgwire_bootstrap`, a contraprova do bootstrap,
  `test_pgwire_settings`, `test_bootstrap`): **181/181**, 12,8 s.

**PG16 próprio:** Docker **parado** no início. Foi iniciado só para a medição.
- Retrato antes dos recursos próprios: 0 contêineres, 17 volumes, 3 redes;
  `bridge` `71b8faa2a28c`. Esse ID difere dos dois do lote B; nenhuma ação
  sobre redes foi feita.
- Contêiner `maskgw-py314-lotc-pg16-5fbb6044` e volume próprio, com label
  `maskgw.lote=py314-lotc` e porta efêmera em `127.0.0.1`.
- PostgreSQL 16.15 (`160015`), UTF8, `TimeZone` UTC,
  `password_encryption=scram-sha-256`, role `SCRAM-SHA-256`, todas as regras
  `host` do `pg_hba` em `scram-sha-256`.
- A credencial aleatória ficou só num arquivo próprio, nunca em argv ou na
  saída. A varredura dela em 98 arquivos de evidência e no log do contêiner
  achou 0 ocorrências.

**Suíte integral** (runner com pilha de 64 MiB só no processo de teste,
watchdog de 3.000 s, sem deselect, ignore, xfail ou skip novo), executada uma
única vez, das 15:41:50 às 15:53:34 locais:
- **4.949 coletados, 4.929 aprovados, 0 falhas, 0 erros, 20 skips só de
  plataforma**: 9 bits de modo POSIX, 6 symlink indisponível, 5 `fsync` de
  diretório POSIX;
- **0 skips por DSN**; 700,2 s pelo JUnit; exit 0;
- monitoramento a cada ~30 s: daemon ativo, `bridge` com o mesmo ID durante
  toda a execução, contêiner PG `running` sem reinício.

Fecha a falha da suíte integral do lote B (2 falhas de NUL). Não foram
repetidos neste lote, e continuam como medições históricas do lote B, com os
mesmos arquivos de produção e os mesmos pacotes:
- `integration`: 572 aprovados, 3 skips POSIX;
- wheel e sdist: 168/168 cada, com as 6 contraprovas reprovando;
- matrizes Node/navegador.

**Bytecode no checkout:** a suíte gerou de novo 71 `*.cpython-314.pyc` (às
15:48–15:49), o mesmo conjunto do lote B, pelo filho de
`tests/test_admin_v2_http.py`, que não foi alterado. Foram removidos pela
lista exata; os 217 `.pyc` anteriores ficaram com caminho, mtime e tamanho
iguais. `.mypy_cache` e `.ruff_cache` do checkout não receberam arquivo.

**Temporários da suíte, não removidos:** a suíte deixou 14 diretórios
`%TEMP%\tmp*` (15:47:30), cada um com `masking.yaml`, `.lock` e às vezes
`.bak.*`. O mesmo padrão de 14 aparece em toda suíte integral desde
2026-10-06, inclusive nas duas rodadas do lote B. O provável gerador é o
`tempfile.mkdtemp()` sem limpeza de
`tests/test_admin_http_writes_adversarial.py`. Ficaram no lugar, porque a
limpeza ampla de Temp não está autorizada; fica para decisão do revisor.

**Estática na venv 3.14** (só check; caches no diretório do lote):
- `ruff check` limpo; `ruff format --check` com 216 arquivos já formatados;
- mypy 2.3.1 strict **limpo em 216 fontes com o alvo configurado 3.11**;
- informativo `--python-version 3.14`: os mesmos **4 `union-attr`** em
  `datasource/destination.py`, **não corrigidos** e sem relaxar a checagem.
  **Não se afirma tipagem strict limpa no alvo 3.14.**

**Limpeza:**
- Removidos o contêiner e o volume próprios, com nome, label e montagem
  conferidos antes.
- Removidos, com pai exato conferido e nenhum symlink ou reparse point,
  sem nenhuma recusa (`cleanup.log`):
  - o arquivo de credencial;
  - `venv314`, `runtime`, `download` (o `.nupkg`) e `tools` (o `nuget.exe`
    e a config isolada);
  - os dois caches do mypy;
  - o cache do mypy do incremento NUL (`lotB/nul-increment`).
- Preservados: JUnit, logs, scripts, perfil, metadata de procedência (com os
  SHA-256 do que foi removido), as evidências dos lotes A e B e os pacotes
  originais.

**Docker:** no fim do uso, contêineres, volumes, redes (inclusive o ID da
`bridge`) e imagens estavam iguais aos do início. O Docker Desktop foi
devolvido ao estado **parado** (0 processos, daemon parado).

**Host:** o retrato antes e depois usou o mesmo script e o mesmo escopo de
consulta.
- **Itens comparados:** `py -0p`; `assoc`/`ftype` de `.py`/`.pyw`; as chaves
  `Python`, `WOW6432Node\Python`, `.py` e `Python.File` em HKCU/HKLM; o PATH
  bruto do usuário e da máquina, lido sem expansão, comparado como conjunto e
  como ordem; `pyvenv.cfg`, `python.exe` e a listagem do site-packages da
  `.venv`; a configuração NuGet e pip do usuário.
- **Resultado:** todos os itens iguais.
- O retrato inicial do PATH da máquina já tinha a ordem observada no fim do
  lote B. Nada foi restaurado.

**Não validado por este lote:** POSIX, resolução limitada de hostname no
composition root, ativação operacional e D-090 gate 2. Também não estão
validados a tipagem strict com o alvo 3.14 e qualquer outro runtime 3.14.
Isto não é afirmação de prontidão para produção. A Etapa 7 e a Fase 9 **não**
estão concluídas.

#### Resolução limitada do hostname do bind — lotes 1 e 2 (D-110, opção B, 2026-10-14)

**Autoridade:** em 2026-10-14, depois da revisão do desenho e das condições,
o usuário aprovou implementar a opção B, em lotes revisados. Sem ativação
operacional, SQL, dependências, settings ou Etapas 8–12, e sem escrita no Git.
HEAD `886b023`. Listener, driver, `main`, settings e dependências **não**
mudaram. O `main` continua recusando `MASKGW_PGWIRE_ENABLED=1`.

**Lote 1 — job DNS fixo sobre a supervisão D-107** (`datasource/verify.py`,
revisado e aprovado):
- método próprio `_ChildRecord.run_bind_dns`. O `run` da verificação, os
  pumps, o `_TrackedPopen`/`_spawn`, o `reap` e o `collect` não mudaram, e
  continuam lendo `_CHILD_CODE`, `_child_environment` e `MAX_OUTPUT_BYTES` na
  execução;
- filho `-I -S -B` com código fixo, só stdlib, ambiente só com `SYSTEMROOT` (no
  POSIX, vazio), host só pelo stdin, stderr descartado;
- o filho devolve as triplas brutas `[family, ip, scope_id]`, sem escolher,
  deduplicar nem filtrar;
- tetos: stdin ≤ 1 KiB antes do spawn; stdout ≤ 16 KiB, cortado na leitura e
  também imposto pelo filho; até 64 entradas brutas;
- 4 vagas próprias (`_BIND_LEDGER`), separadas da verificação e do
  `resolver.py`, sem fila;
- prazo absoluto de 5 s criado antes da admissão e nunca renovado; cleanup
  numa passada separada de 6 s;
- recolhimento incerto fica retido com o dono forte do módulo;
- categorias fechadas `refused`/`failed`/`incomplete`.

**Defeitos achados pelas contraprovas independentes do revisor e corrigidos**
(`tests/test_pgwire_bind_deadline_review.py`, não alterado):
1. um `wait()` que voltava depois do prazo aprovava a resposta (lote 1);
2. a coleta de admissão seguia registros que chegavam durante ela e podia
   passar do prazo. A correção foi um método novo, `_Ledger.collect_until`,
   usado só pelo DNS; o `collect` da verificação não mudou (lote 1);
3. uma resposta lida só durante o cleanup, depois do prazo, era aprovada
   (lote 2). Agora aprovar exige que o leitor chegue ao fim dentro do prazo.

**Lote 2 — política e composição:**
- **`pgwire/bind_resolution.py` (novo).** Só para respostas vindas de DNS.
  - **Esquema estrito:** até 16 KiB ASCII; lista de 1 a 64 entradas brutas;
    `family` int exato (sem `bool` nem `float`) igual a `AF_INET`/`AF_INET6`;
    IP em texto ASCII (IPv4 ≤ 15, IPv6 sem escopo ≤ 45), sem `%`, da mesma
    família; `scope_id` int exato 0. JSON malformado, `NaN` e aninhamento
    profundo (`RecursionError`) falham fechado.
  - **Política, na ordem:** recusa `0.0.0.0`/`::`; aceita `::1`; recusa
    `255.255.255.255`, multicast, `::ffff:0:0/96` e o restante de `::/96`, e
    link-local; aceita `127/8`; aceita o resto, sujeito ao bind. Usa redes
    explícitas, sem `is_reserved`/`is_private`/`is_global`.
  - Qualquer entrada ruim recusa a resposta inteira. Depois da deduplicação
    canônica, só exatamente um endereço é aceito; dual stack é recusado.
  - **Erro:** `ConfigError` fixa, fora de `except`, sem host, endereço, causa
    ou contexto. Só `BindDnsError` vira esse erro; outra exceção propaga.
- **`pgwire/composition.py`, em duas fases:**
  - `_validate`: settings, forma do colaborador, `test_port`, TLS (lê os
    arquivos de cert e chave, portanto não é livre de efeito externo) e
    principal;
  - `_finalize`: só para hostname **sem** colaborador, uma resolução, sem
    retry;
  - só o `PreparedPgwire` final existe, e sempre com o literal final. Tudo
    antes de catálogo, config, lock, upstream, bind, Admin HTTP e MCP;
  - bind literal e o colaborador explícito `resolved_addresses` (inclusive
    wildcard e escopo) mantêm a semântica anterior, sem filho e sem DNS.
- **`bootstrap/application.py`:** só comentário e docstring.
- **Teste existente alterado de propósito:** em `tests/test_pgwire_bootstrap.py`
  saiu da matriz o caso "hostname + `resolved_addresses=None`". Com o fluxo
  novo, ele falharia pelo TLS (`tls_cert="c"`) e esconderia a troca de motivo.
  No lugar entrou um teste dedicado, com TLS válido e falha controlada do
  resolvedor. Ele prova a ordem `tls → principal → dns` e que, depois da
  falha, nada de catálogo, config, upstream, listener ou MCP acontece. Os
  outros casos foram preservados.

**Correção do harness legado feita pelo revisor (só verificação, não é
produto):**
- `test_admin_v2_lifecycle.py::test_shutdown_with_slow_dns_in_flight_is_bounded_and_leaves_nothing`
  falhava com 503 em vez de 422:
  - em 5 de 5 execuções isoladas, no arquivo inteiro e na seleção ampla;
  - igual com o `verify.py` da HEAD, carregado de uma cópia temporária;
  - passava nas três suítes integrais anteriores.
- **Causa diagnosticada pelo revisor:** o espião de `Popen` do teste
  registrava qualquer processo, inclusive o `cmd` de metadados do Windows
  (`platform.win32_ver`) disparado no startup do harness. Isso fazia o teste
  considerar o DNS em voo e fechar a admissão antes de a requisição entrar.
  Aquecer o `platform` antes fazia o teste original passar.
- **Correção:** o revisor mudou **só** o espião, para registrar o argv exato do
  DNS, e acrescentou um filho benigno como controle negativo. O 422 e as
  demais asserções de segurança ficaram iguais.
- A causa **não** era a ausência de DSN.

**Medições** (`.venv` 3.11.3, sem DSN, sem `MASKGW_*`/`PG*` herdados):

| seleção | coletados | resultado |
|---|---|---|
| `test_pgwire_bind_resolution.py` (novo) | 122 | 122 aprovados |
| `test_datasource_verify_bind_dns.py` | 68 | 68 aprovados |
| contraprovas do revisor (`bind_deadline_review`, `*_increment_review`) | 40 | 40 aprovados |
| `test_pgwire_bind_policy_review.py` (revisor) | 3 | 3 aprovados |
| PGWire, bootstrap, `test_bootstrap`, `test_admin_ui_startup` | 455 | 448 aprovados, 7 skips de plataforma (6 de bits POSIX, 1 de symlink) |
| D-107/D-108 e vizinhos | 210 | 197 aprovados, 13 skips por falta de `MASKGW_TEST_DSN` |

- **Mutações temporárias** (restauradas com hash conferido): no lote 1, 14 de
  14 detectadas. No lote 2, 7 de 9 detectadas: escolher o primeiro, filtrar
  entrada ruim, `::1` classificado como `::/96`, `bool` aceito como int,
  `is_reserved`, resolver também com colaborador e leitura no cleanup. As
  outras 2 são mutantes equivalentes, sem efeito observável, e **não** foram
  detectadas (nem poderiam):
  - **B3:** trocar `unique[0]` por `unique[-1]` **depois** da checagem de
    exatamente um endereço. **Não** aceita dois IPs: com um único elemento,
    os dois índices são o mesmo. O rótulo original no registro de mutações
    ("aceita 2+") estava errado;
  - **B9:** remover a recusa explícita de `%`. A defesa é redundante: o
    `ipaddress` recusa `%` no IPv4, e o IPv6 com escopo continua recusado pela
    checagem de `scope_id`.
- **Ajuste de harness depois da revisão:** o caso
  `test_answer_read_only_during_cleanup_cannot_approve` gerava um
  `PytestUnhandledThreadExceptionWarning` (leitura de arquivo já fechado).
  Era uma corrida do próprio teste: o `reap` real fechava o stdout enquanto o
  leitor retido ainda lia. Agora o harness solta o leitor e espera ele
  terminar antes do `reap` real. O cenário adverso, o watchdog, as checagens
  de recurso e a contraprova não mudaram, e o produto não mudou. Medido:
  - 3 rodadas com `-W error::pytest.PytestUnhandledThreadExceptionWarning`,
    sem aviso;
  - o arquivo inteiro: 68/68, sem aviso;
  - a mutação temporária sem a correção do leitor continua detectada, com o
    hash restaurado.
- **Estática:** ruff limpo, 221 arquivos formatados, mypy strict (alvo 3.11)
  limpo em 221 fontes. Nenhum `.pyc` cp314 nem `.pyc` novo no checkout.

**Limites que continuam:**
- a resolução acontece uma vez, no startup, sem seguir mudança de DNS;
- nomes com vários endereços ou dual stack falham fechado;
- chamadas bloqueantes do SO não têm teto absoluto;
- não há garantia de saída do interpretador com recurso incerto;
- registros incompletos só são tentados de novo em admissões futuras;
- o SAN do certificado continua sendo dever do cliente (`verify-full`).

**Não medido nesta fase** (histórico; a validação final no runtime legado
está logo abaixo): suíte integral e `integration` com PG16, wheel e sdist,
runtime moderno 3.14.8 e POSIX. A ativação operacional e a D-090 gate 2
seguem abertas. O incremento **não** está concluído, e a Etapa 7 continua
parcial.

#### Resolução limitada do hostname do bind — validação final no runtime legado (2026-10-14)

**Escopo:** a `.venv` atual, sem mudança: CPython 3.11.3 nativo no Windows,
com o `ssl` da stdlib em OpenSSL 1.1.1t (fora de suporte) e libpq 18.0.3.
Nenhuma mudança de produto durante os gates. A repetição no runtime moderno
temporário (3.14.8) é o próximo lote, autorizado à parte.

**Fonte congelada:** 229 arquivos funcionais (221 Python): `src/`, `tests/`,
`pyproject.toml` e `MANIFEST.in`, inclusive os 13 módulos `pgwire` não
rastreados e os 8 arquivos de contraprova do revisor. Digest
`256d4f1f6bf6f65b8e177b6402d87ddc727c8672c5ff67f5036bd97d1cbfea8f`, igual
antes e depois.
- HEAD `886b023`; o `origin/master` em cache local também aponta para
  `886b023`, mas não houve fetch, então isso não atesta o remoto;
- inventário do `git status` (31 não rastreados, 14 modificados) igual antes
  e depois.

**PG16 próprio:**
- Docker Desktop **parado** no início, iniciado sem janela (`docker desktop
  start`) e devolvido ao estado parado;
- retrato antes dos recursos próprios: 0 contêineres, 17 volumes, 3 redes
  (`bridge` `38646e3ca079`). No fim, contêineres, volumes, redes (inclusive o
  ID) e imagens iguais aos do início;
- contêiner e volume novos com label exclusiva (`maskgw.lote=d110-bind-final`),
  porta efêmera em `127.0.0.1`: PostgreSQL 16.15 (`160015`), UTF8, UTC,
  `scram-sha-256`;
- credencial aleatória só no arquivo próprio e no ambiente do processo; a
  varredura de 100 arquivos de evidência e do log do contêiner achou 0
  ocorrências.

**Suítes** (runner revisado do lote C: limpa `MASKGW_*`/`PG*`, injeta só a
DSN própria, pilha de 64 MiB só no processo de teste, watchdog independente
de 3.000 s; sem deselect, ignore, xfail nem skip novo):

| seleção | coletados | resultado |
|---|---|---|
| suíte integral | **5.145** | **5.125 aprovados, 0 falhas, 0 erros, 20 skips só de plataforma** (9 bits de modo POSIX, 6 symlink indisponível, 5 `fsync` de diretório POSIX), **0 skips por DSN**, 738,0 s, exit 0 |
| `-m integration` | **575** | **572 aprovados, 0 falhas, 0 erros, 3 skips `fsync` POSIX, 0 por DSN**, 218,6 s, exit 0 |

- **Aviso:** a suíte integral registrou um único aviso, `PytestWarning` por
  `pytest.raises(..., match="")` em `tests/test_admin_http_lifecycle.py:679`.
  É um teste antigo, rastreado e inalterado; não foi corrigido.
- **Bytecode:** nenhum caminho novo de `.pyc` e nenhum cp314 no checkout.
  `application.cpython-311.pyc` e `verify.cpython-311.pyc`, que já existiam,
  foram recompilados pelos filhos legados que rodam com `-I` sem `-B`.
- **Temporários da suíte:** mais 14 diretórios `%TEMP%\tmp*` (11:24, durante
  a suíte), no padrão já conhecido. Ficaram no lugar.

**Estática:** ruff 0.16.5 check limpo; `format --check` com 221 arquivos já
formatados; mypy 2.3.1 strict (alvo 3.11) limpo em 221 fontes; `git diff
--check` sem ocorrências. Os não rastreados também não têm espaço no fim de
linha. Os 4 `union-attr` informativos do alvo 3.14 não foram tratados aqui.

**Pacotes gerados da árvore de trabalho atual** (cópia de staging com os 112
arquivos de `src/`, `pyproject.toml` e `MANIFEST.in` iguais aos congelados;
`python -m build` 1.6.1):
- wheel `maskgw-0.1.0-py3-none-any.whl` SHA-256
  `f7741cfc124ab41098b8e8053311eb77a4ab0cb0ea86ab8400de1723040a1d7c`
  (114 entradas);
- sdist `maskgw-0.1.0.tar.gz` SHA-256
  `bfe8cab9f2709b8c1541357b062d85c21472e1aab4cfec658c104960081b4dcd`
  (140 entradas);
- nos dois: os 13 módulos `pgwire`, inclusive `bind_resolution.py`, e os
  hashes de `src/maskgw` iguais aos congelados; nenhum `tests/`, `docs/`,
  `frontend/` ou `node_modules`; pins `cryptography==50.0.1`,
  `scramp==1.4.17` e `asn1crypto==1.5.1`.

**Instalação:** duas venvs novas e separadas, fora do checkout, a partir do
mesmo Python base 3.11.3. As dependências foram restritas ao freeze da
`.venv`, com 38 pacotes de runtime na mesma versão; ficaram de fora só as
ferramentas de desenvolvimento.
- **Primeira tentativa (exit 1, nas duas venvs):** o freeze da `.venv`
  apontava `scramp` e `asn1crypto` para um wheelhouse temporário de 2026-10-08
  que já não existe.
- **Correção:** baixei os dois wheels para um wheelhouse próprio e conferi os
  SHA-256 do desenho (`a4e3fd2e…474ac8` e `db4e4072…f8fd67`). As restrições
  passaram a apontar esses arquivos, e as venvs parciais foram removidas e
  recriadas.

**Sonda dos pacotes** (`python -I -B`, cwd temporário fora do checkout, sem
`PYTHONPATH`, PATH só com System32, sem Node/npm; adaptada da sonda revisada
do lote B, com o guarda de limpeza preservado):
- os itens da sonda revisada:
  - origem de todo módulo do produto em `site-packages` e 105 fontes com hash
    conferido;
  - 4 recursos da UI;
  - `main` com `MASKGW_PGWIRE_ENABLED=1` exato devolve rc 1, stderr fixo e
    stdout vazio;
  - legado real sem `maskgw.pgwire`;
  - composição real com catálogo, verificador filho contra o PG16 e
    `POST /admin/v2/datasources` 200;
  - SCRAM, -PLUS e `verify-full`; CA errada, senha errada e alias inexistente
    recusados; nenhum SQL pelo PGWire;
- **seção nova, bind por hostname** pela composição e pelo listener
  **instalados**. O filho DNS **fixo real** é o do pacote (código idêntico ao
  da fonte), só com o `getaddrinfo` controlado, sem DNS externo:
  - hostname sem TLS é recusado antes de qualquer DNS;
  - respostas dual stack, com escopo e malformada são recusadas, com uma
    resolução cada;
  - o filho travado é recusado em **5,03 s** (wheel) e **5,02 s** (sdist),
    dentro de prazo mais cleanup, sem processo, pipe, thread ou registro vivo,
    e com as 4 vagas devolvidas;
  - no caminho positivo há **exatamente uma** resolução e o literal fica
    selado em `127.0.0.1`;
  - o listener exige TLS: em claro é recusado; -PLUS e `verify-full` passam;
    senha errada é recusada;
  - **nenhum `getaddrinfo` não numérico** e nenhuma resolução nova depois do
    preparo;
  - fechamento sem threads do produto.

| pacote | positiva | `checkout` | `tls` | `binding` |
|---|---|---|---|---|
| wheel | **191/191**, exit 0 | 164/191, exit 1 | 190/191, exit 1 | 189/191, exit 1 |
| sdist | **191/191**, exit 0 | 164/191, exit 1 | 190/191, exit 1 | 189/191, exit 1 |

Reprovações esperadas das contraprovas:
- **`checkout`:** 27, entre origens `maskgw.*` (inclusive
  `maskgw.pgwire.bind_resolution`), `embarcado_*` (inclusive
  `bind_resolution`) e `requires_*`. Importar do checkout editável **não**
  passa como isolamento;
- **`tls`:** `verify_full_com_a_ca`;
- **`binding`:** `plus_channel_binding_require` e `verify_full_com_a_ca`.

**Correção na execução das contraprovas:** na primeira rodada das 7
execuções (sdist positiva e 6 contraprovas), um escape da camada de shell
transformou `\\$name` em `$name` literal. As 7 gravaram por cima umas das
outras um único arquivo **fora** do diretório de evidência
(`%TEMP%\maskgw-d110-bind-final$name.json`, mais `.stdout` e `.stderr`). As
contagens dessa rodada vieram da saída direta e coincidem com a rodada
refeita, mas os JSON se perderam. As 7 foram refeitas com o caminho montado
por `cygpath`.
- A primeira tentativa de remover os 3 arquivos perdidos foi **bloqueada**
  pelo controle de permissões, por usar caminho montado a partir de variável.
  Eles foram removidos depois, com caminho absoluto literal.

**Limpeza** (alvos exatos conferidos antes: pai, sem symlink, sem reparse
point; remoção por caminho absoluto literal):
- **removidos:** o arquivo de credencial, as duas venvs, o wheelhouse, a cópia
  de staging, o cache do mypy, o contêiner e o volume próprios (nome, label e
  montagem conferidos) e os 3 arquivos perdidos;
- **preservados:** JUnit, logs, hashes, JSON das sondas, roteiros e os dois
  pacotes, em `%LOCALAPPDATA%\Temp\maskgw-d110-bind-final\`.

**Host:** o retrato antes e depois, com o mesmo script e escopo, saiu igual
em `py -0p`, associações, registro, PATH de usuário e de máquina (conjunto e
ordem), `.venv` e configuração NuGet/pip do usuário. Docker parado no início
e no fim.

**Estado nesta data** (histórico; a repetição moderna está logo abaixo):
- a resolução limitada do hostname do bind está implementada localmente e
  validada neste incremento no runtime legado;
- falta a repetição no runtime moderno temporário 3.14.8, que é o próximo
  lote;
- a Etapa 7 continua **parcial**: a ativação operacional segue bloqueada no
  `main`, a D-090 gate 2 segue aberta e a v2 não está liberada para produção;
- o MCP legado em stdio não mudou, e não há SQL pelo PGWire.

Nada disso é afirmação de prontidão para produção. POSIX não foi medido.

#### Resolução limitada do hostname do bind — repetição no runtime moderno temporário (2026-10-14)

**Autoridade:** a mesma autorização estreita de runtime moderno temporário e
isolado: CPython 3.14.8 x64 com GIL, do pacote oficial do nuget.org, extraído
fora do checkout e invocado só pelo caminho absoluto. Sem instalação no
sistema, PATH, registro, launcher ou associações, sem escolha de runtime de
produção e sem escrita no Git. Nenhuma mudança de produto.
- **Fonte:** idêntica à da validação legada. Os mesmos 229 arquivos (221
  Python), digest `256d4f1f…ea8f`, iguais antes e depois. HEAD `886b023`;
  inventário do `git status` igual.

**Interrupção e retomada** (histórico, não reescrito):
- a primeira tentativa (raiz `maskgw-d110-bind-modern`) chegou a fazer a
  procedência, a extração, o perfil, a preparação das dependências, a
  instalação do wheel atual e a criação de um PG16
  (`maskgw-d110-bind-modern-pg16-5de379c7`);
- a sessão bateu o limite da conta **antes** de qualquer suíte, sonda ou
  estática;
- depois do limite, o revisor ("root") fez só limpeza e registrou isso em
  `ROOT-INTERRUPTION.md`, na mesma raiz: removeu contêiner, volume, runtime,
  venv, ferramentas, wheelhouse, o nupkg e a credencial, e devolveu o Docker
  ao estado parado;
- na retomada, conferi por medição: esses recursos estavam ausentes, nenhum
  cp314 no checkout, o mesmo número de `tmp*`, e um retrato novo do host
  (mesmo script e escopo) igual ao original em todos os itens;
- tudo o que se segue foi refeito do zero na retomada.

**Procedência, verificada de novo antes de executar:**
- `python.3.14.8.nupkg`: SHA-256
  `ce85f674d9a63029f709cbff7a3da1c6bc5bfcfaefdd9999f98fa0290470c454`; SHA512
  e tamanho (15.554.015 bytes) iguais ao `packageHash`/`packageSize` do
  catálogo oficial, que é idêntico ao do lote C;
- `nuget.exe` 7.9.0.83 (SHA-256 `992d70ca…b800`): Authenticode `Valid` de
  `CN=Microsoft Corporation` (emissor `Microsoft Code Signing PCA 2024`),
  conferido antes de rodar, com `NuGet.Config` isolado; a configuração NuGet do
  usuário continua inexistente;
- `verify -Signatures`: êxito, assinatura **só de repositório**
  (`CN=NuGet.org Repository by Microsoft`, cadeia até a `DigiCert Trusted
  Root G4`), sem `NU3`. O pacote **não** tem assinatura de autor;
- extração validada: 1.382 entradas aceitas, 0 recusadas, 0 com conteúdo
  divergente e 0 reparse points;
- Authenticode `Valid` de `CN=Python Software Foundation`, conferido antes de
  invocar o runtime, igual à verificação anterior:
  - emissor `EOC CA 03`: `python.exe`, `python314.dll`, `python3.dll`,
    `_ssl.pyd` e `_hashlib.pyd`;
  - emissor `AOC CA 04`: `libssl-3.dll` e `libcrypto-3.dll` (3.5.9).

**Perfil medido:**
- CPython **3.14.8 final** (`tags/v3.14.8:8e6e75d`, MSC v.1944, AMD64),
  **GIL ativo**, não free-threaded;
- `ssl` da stdlib do próprio runtime com **OpenSSL 3.5.9 29 Sep 2026**;
- binários **carregados** no processo (enumerados via `EnumProcessModules`):
  `python314.dll`, `DLLs\libssl-3.dll` e `DLLs\libcrypto-3.dll`, todos do
  runtime extraído;
- libpq 18.0.3 do `psycopg-binary`.

**Ambientes temporários** (fora do checkout; a `.venv` e o site-packages do
usuário e do sistema não foram tocados):
- pip com `--isolated --no-cache-dir --only-binary=:all:`;
- restrições e requisitos do lote A; `scramp`/`asn1crypto` de um wheelhouse
  próprio, com os SHA-256 do desenho conferidos;
- `venv314`: 51 pacotes, todos na mesma versão do lote A;
- para os filhos `-I` da suíte: o wheel atual (`f7741cfc…1d7c`, hash
  conferido), com os 110 arquivos instalados iguais a `src/maskgw`.

**PG16 próprio, novo na retomada:**
- Docker Desktop parado no início, iniciado sem janela e devolvido ao estado
  parado;
- contêiner `maskgw-d110-bind-modern-pg16-3a7af9b0` e volume próprio
  (`maskgw.lote=d110-bind-modern`), porta efêmera em `127.0.0.1`: PostgreSQL
  16.15, UTF8, UTC, `scram-sha-256`;
- contêineres, volumes e imagens comparados como **conjuntos**, e redes por
  nome e driver: iguais ao retrato original. Os IDs da `bridge` observados
  foram diferentes entre as duas tentativas (`304caaaad310` na primeira,
  `952e44cb0547` na retomada). Na retomada, o ID ficou igual antes e depois
  do uso; isso não estabelece uma regra geral sobre reinícios do daemon;
- a varredura da credencial em 130 arquivos de evidência e no log do
  contêiner achou 0 ocorrências.

**Suítes** (3.14.8 nativo, `-I -B`, runner revisado do lote C: limpa
`MASKGW_*`/`PG*`, injeta só a DSN própria, pilha de 64 MiB só no processo de
teste, watchdog independente; sem deselect, ignore, xfail nem skip novo):

| seleção | coletados | resultado |
|---|---|---|
| suíte integral | **5.145** | **5.125 aprovados, 0 falhas, 0 erros, 20 skips só de plataforma** (9 bits de modo POSIX, 6 symlink, 5 `fsync` POSIX), **0 por DSN**, 735,3 s, exit 0 |
| `-m integration` | **575** | **572 aprovados, 0 falhas, 0 erros, 3 skips `fsync` POSIX, 0 por DSN**, 214,5 s, exit 0 |
| focada: bind, hostname, as 6 contraprovas novas do revisor, `*_increment_review`, lifecycle, supervisor/gate da verificação, `admin_ui_startup` | **450** | **450 aprovados**, 0 skips, 154,1 s, exit 0 |

- **Avisos da suíte integral** (os dois em testes antigos, rastreados e
  inalterados; nenhum corrigido):
  - `PytestWarning` por `match=""` em `tests/test_admin_http_lifecycle.py:679`,
    que também aparece no 3.11;
  - `PytestUnraisableExceptionWarning` na finalização do stream falso de
    `tests/test_admin_http_writes_adversarial.py`, cujo `close` é injetado.
    Aparece só no 3.14, e já aparecia nos lotes B e C.
- A seleção `integration` e a focada não tiveram avisos. Os três casos `1\x00`
  da correção do lote C passaram.
- **Bytecode:** a suíte gerou 71 `*.cpython-314.pyc` (15:54), o mesmo conjunto
  dos lotes B e C, pelo filho de `tests/test_admin_v2_http.py`.
  - Antes havia 0 cp314, então nenhum era pré-existente. Foram removidos pela
    lista exata, com o padrão de caminho conferido.
  - Os 217 `.pyc` anteriores ficaram com caminho, mtime e tamanho iguais.
- **Temporários da suíte:** mais 14 diretórios `%TEMP%\tmp*` (15:53), no
  padrão conhecido. Ficaram no lugar.

**Pacotes:** os mesmos arquivos gerados na validação legada da árvore atual,
com o hash conferido antes de usar:
- wheel `f7741cfc124ab41098b8e8053311eb77a4ab0cb0ea86ab8400de1723040a1d7c`;
- sdist `bfe8cab9f2709b8c1541357b062d85c21472e1aab4cfec658c104960081b4dcd`.

Não foram usados artefatos anteriores ao DNS nem `git archive`. Cada pacote
foi instalado numa venv 3.14.8 própria, fora do checkout, com as 38
dependências de runtime na mesma versão da `venv314`; a sdist foi construída
na instalação.

**Sonda** (a nova sonda revisada da validação legada, adaptada **só** na
expectativa de perfil: `runtime_3_14_8`, `gil_ativo` e `ssl_openssl_3_5_9` no
lugar de `runtime_3_11_3`; todo o resto inalterado, inclusive o guarda de
limpeza; `python -I -B`, cwd fora do checkout, sem `PYTHONPATH`, PATH só com
System32, sem Node/npm):

| pacote | positiva | `checkout` | `tls` | `binding` |
|---|---|---|---|---|
| wheel | **193/193**, exit 0 | 166/193, exit 1 | 192/193, exit 1 | 191/193, exit 1 |
| sdist | **193/193**, exit 0 | 166/193, exit 1 | 192/193, exit 1 | 191/193, exit 1 |

- **Positivas:**
  - origem em `Lib/site-packages`, 105 fontes com hash conferido;
  - perfil 3.14.8 com GIL e OpenSSL 3.5.9;
  - `main` com a flag exata recusado; legado real; composição real com
    catálogo, verificador filho e `POST /admin/v2/datasources` 200;
  - SCRAM, -PLUS e `verify-full`; CA errada, senha errada e alias recusados;
  - **bind por hostname pelos pacotes instalados**, com o filho DNS fixo real
    (código idêntico ao da fonte) e só o `getaddrinfo` controlado:
    - sem TLS, recusado antes do DNS;
    - dual stack, escopo e malformada recusadas;
    - filho travado recusado em **5,02 s** (wheel) e **5,03 s** (sdist), sem
      recurso vivo;
    - uma resolução; literal `127.0.0.1` selado; em claro recusado; -PLUS e
      `verify-full` aceitos;
    - nenhum `getaddrinfo` não numérico depois do preparo;
  - nenhum SQL pelo PGWire.
- **Contraprovas**, com as reprovações esperadas:
  - `checkout`: 27 (origens, `embarcado_*` e `requires_*`, inclusive
    `bind_resolution`);
  - `tls`: `verify_full_com_a_ca`;
  - `binding`: `plus_channel_binding_require` e `verify_full_com_a_ca`.

**Estática na `venv314`:**
- ruff check limpo; `format --check` com 221 arquivos já formatados;
- mypy strict com o alvo configurado (3.11) limpo em 221 fontes;
- informativo `--python-version 3.14`: **só** os mesmos 4 `union-attr`
  (`ipv4_mapped`) de `datasource/destination.py` do lote C, sem nenhum
  achado novo, inclusive nos arquivos novos. **Não corrigidos**; a tipagem
  strict com o alvo 3.14 **não** está certificada.

**Limpeza** (alvos exatos conferidos antes: dentro da raiz própria, sem
symlink nem reparse point; remoção por caminho absoluto literal):
- **removidos:** o arquivo de credencial, o runtime extraído, a `venv314`, as
  duas venvs de pacote, o wheelhouse, as ferramentas (`nuget.exe` e config
  isolada), o nupkg, os caches do mypy, a cópia dos pacotes, e o contêiner e
  o volume próprios (nome, label e montagem conferidos);
- **preservados:** JUnit, logs, hashes, JSON das sondas, roteiros, a
  metadata de procedência e a nota `ROOT-INTERRUPTION.md`, em
  `%LOCALAPPDATA%\Temp\maskgw-d110-bind-modern\`. Os pacotes originais
  continuam em `maskgw-d110-bind-final\packages`.

**Host:** o retrato final, com o mesmo script e escopo, saiu igual ao original
em `py -0p`, associações, registro, PATH de usuário e de máquina (conjunto e
ordem), `.venv` e configuração NuGet/pip do usuário. Docker parado no início
e no fim.

**Estado atual:**
- a resolução limitada do hostname do bind está implementada localmente, com
  medições finais no Windows, no runtime legado (3.11.3) e no runtime moderno
  temporário (3.14.8);
- nenhuma aprovação do usuário sobre esses resultados é presumida aqui;
- a Etapa 7 continua **parcial**: a ativação operacional segue bloqueada no
  `main`, a D-090 gate 2 segue aberta e a v2 não está liberada para operação;
- o MCP em stdio não mudou, e não há SQL pelo PGWire.

POSIX e tipagem strict com o alvo 3.14 não estão certificados. Nada disso é
afirmação de prontidão para produção.

#### Repetição do bind no runtime moderno — interrompida antes das suítes (2026-10-14)

A repetição autorizada começou em ambiente temporário separado,
`%LOCALAPPDATA%\Temp\maskgw-d110-bind-modern`. O Claude2 atingiu o limite da
conta, com liberação indicada para 15h (`America/Sao_Paulo`), depois do preparo
do ambiente e antes de executar as suítes. O trabalho foi interrompido; não
houve troca de conta, continuação dos testes pelo revisor ou escrita no Git.

**Medido antes da interrupção:**
- pacote oficial `python` 3.14.8 com SHA-256
  `ce85f674d9a63029f709cbff7a3da1c6bc5bfcfaefdd9999f98fa0290470c454`;
  metadados NuGet e assinatura de repositório verificados; Authenticode
  Microsoft válido no `nuget.exe` antes de executá-lo e PSF válido nos
  binários Python/OpenSSL;
- extração de 1.382 entradas, sem escape, link ou reparse point;
- perfil efetivo: CPython 3.14.8 x64 com GIL, OpenSSL 3.5.9 da stdlib, DLLs
  carregadas da extração temporária;
- ambiente temporário preparado com o wheel atual; os 110 arquivos do
  produto instalado conferidos contra os fontes congelados;
- PostgreSQL 16 descartável criado, mas sem execução das suítes.

**Não executado nesta repetição:** suíte integral, seleção `integration`,
testes focados, sondas dos pacotes no 3.14 e estática do lote moderno. Os
resultados anteriores dos lotes A–C são históricos e não fecham o gate do
novo incremento DNS. A validação final no runtime legado, acima, permanece
válida; o gate moderno deste incremento continua pendente.

**Encerramento pelo revisor:**
- contêiner `maskgw-d110-bind-modern-pg16-5de379c7` e seu volume foram
  identificados por label e mount, encerrados e removidos;
- credencial própria, runtime extraído, ambiente `venv314`, ferramentas,
  wheelhouse e pacote baixado removidos somente dos caminhos próprios
  previamente conferidos, sem symlink/reparse point; evidência e metadados
  de procedência preservados;
- recursos Docker preexistentes preservados: 0 contêineres, 17 volumes,
  3 redes e 1 imagem, sem diferenças nos conjuntos consultados; Docker
  Desktop devolvido ao estado parado;
- 229 hashes funcionais inalterados; HEAD continua `886b023`, sem staged
  files, commit ou push;
- `.venv`, launcher, associações e PATH (valores, conjunto e ordem) iguais
  aos retratos anteriores; configs NuGet/pip continuam ausentes;
- o retrato bruto do registro diferiu apenas por encoding: o anterior é
  CP850 e o posterior UTF-8. Decodificados corretamente, os textos são
  exatamente iguais. Nenhum valor do registro foi restaurado ou alterado;
- nenhum bytecode cp314 no checkout. As pastas temporárias preexistentes
  foram preservadas, incluindo as 14 adicionais da suíte legada.

Para retomar, recriar somente o ambiente temporário e o PG16 próprio,
revalidar a mesma procedência e reconstruir os caminhos temporários das
restrições. Não reutilizar referências ao wheelhouse removido. A Etapa 7
continua parcial: ativação operacional bloqueada no `main`, D-090 gate 2
aberta, v2 sem liberação operacional e nenhum SQL via PGWire.

#### Fechamento local do trabalho validado da Etapa 7 (2026-10-14)

O registro acima, da tentativa interrompida, é histórico. A repetição moderna
foi refeita e concluída na retomada (seção "repetição no runtime moderno
temporário", mais acima), e a revisão independente final não achou nenhum
bloqueio.

O usuário aprovou explicitamente fechar o trabalho validado da Etapa 7 num
**commit local novo**, com pai `886b023`. A aprovação não cobre:
- push nem fetch;
- amend nem reset;
- ativação operacional ou de produção;
- trabalho da Etapa 8;
- dependência nova nem mudança funcional.

O commit inclui:
- as peças do startup PGWire, com TLS e autenticação (D-109/D-110);
- a composição interna;
- a resolução limitada do hostname do bind.

Antes do commit, os 229 arquivos funcionais foram conferidos contra o
inventário congelado da validação final, e nenhuma suíte foi repetida só
para o commit.

**Estado depois do fechamento:**
- a Etapa 7 continua **parcial**: a ativação operacional segue bloqueada no
  `main`, a D-090 gate 2 segue aberta e a v2 continua proibida em operação
  real;
- não há SQL pelo PGWire;
- o MCP continua o legado em stdio;
- POSIX e tipagem strict com o alvo 3.14 não estão certificados (os 4
  `union-attr` informativos continuam abertos);
- não há afirmação de prontidão para produção.

## 2. NÃO entregue (estado atual; itens históricos marcados)

- *(Histórico: o item abaixo descreve o estado antes do incremento da §1.4
  (D-108). Estado atual: validado conforme a §1.4, com fechamento aprovado e
  publicação autorizada em 2026-10-07; estado de publicação confirmado pelo
  Git.)*
  **Executor dedicado, barreira atômica de submissão×shutdown e bloqueio de
  composição de leitura** (Contratos 1 e 3 do desenho): desenhados e aprovados,
  mas são um segundo corpo de trabalho, com sua própria matriz de concorrência;
  ficam para um incremento próprio, validado à parte. Os handlers v2 continuam
  `async` chamando o coordenador **de forma síncrona no event loop** (D-059).
  **Sem executor, o event loop continua bloqueado durante uma verificação**: o
  gate torna essa espera **finita** (teto de uma verificação), mas **não a
  remove** — o handler v2 ainda não responde outras rotas enquanto uma
  verificação está em voo. Tornar o event loop responsivo durante a verificação
  é o executor dedicado, fora desta rodada.
- *(Histórico, ao fim da §1.5:)* listener, settings, `SSLContext` de
  produto, driver, prazo, admissão, rate limit, limites de sessão/idle e
  ativação — nada iniciado. **Estado atual, parcial:** settings e preparo do
  `SSLContext` existem como lote 1 da D-110 (§1.6), local e sem commit, sem
  consumidor no produto. **Listener PGWire**, driver de startup sobre socket,
  prazo, admissão, rate limit, aplicação dos limites de sessão/idle,
  integração interna e ativação continuam não iniciados.
- **Consultas, masking PGWire, extended query, cancelamento, catálogo de IDE** —
  Etapas 8–10, não iniciadas.

## 3. Ambiente

Windows 11 Pro 10.0.26200; Python 3.11.3; PostgreSQL 16 em contêiner descartável
`postgres:16-alpine`, só em `127.0.0.1`, senha aleatória em arquivo temporário
privado, removido ao final. Nenhum banco existente foi usado. `maskgw` instalado
editável na venv para que o filho `-I` veja o código vivo do checkout.

Revisão do `8261dc7` (2026-10-06): mesmo host e Python. O Docker Desktop
(instalação por usuário, sem elevação) estava parado; foi iniciado só para esta
medição e encerrado ao final. Não havia contêiner preexistente. PostgreSQL 16.15
em contêiner novo `postgres:16-alpine` publicado só em `127.0.0.1` (porta
efêmera), senha aleatória em arquivo temporário do perfil do usuário, nunca
impressa; contêiner e arquivos removidos ao final. Este host **nega o privilégio
de symlink** (WinError 1314, Modo de Desenvolvedor desligado). Wheel e sdist
foram construídos a partir de uma cópia dos arquivos num diretório temporário,
sem gerar artefato no checkout, e instalados em duas venvs novas fora dele, com
as dependências já declaradas restritas às versões da `.venv`.

Validação final da segunda revisão (2026-10-07): mesmo host, Python 3.11.3. O
Docker Desktop estava parado: foi iniciado só para esta medição e encerrado ao
final, sem contêiner preexistente. PostgreSQL 16.15 em contêiner novo
`postgres:16-alpine`, publicado só em `127.0.0.1` (porta efêmera); senha
aleatória gerada num arquivo temporário do perfil, nunca impressa, exportada só
como `MASKGW_TEST_DSN` no ambiente dos testes. Contêiner, arquivos, venvs e
artefatos foram removidos ao final.

## 4. Resultados medidos

### 4.0 Validação final da segunda revisão (2026-10-07, Windows nativo)

Fontes congelados antes dos gates (SHA-256):

| arquivo | sha256 |
|---|---|
| `src/maskgw/datasource/verify.py` | `e2c16366838236232910174df6bd2c28f0889b9d480cd73e57fa719fc189c141` |
| `src/maskgw/bootstrap/application.py` | `07a42e6caf55d701aeff1c5b597fdde4f3778a82ecc1a0983a079404d6520186` |
| `src/maskgw/runtime/candidate.py` | `88b0852be17e677ea3535ab2db159748c7e0c6288b40317385347e3333fa8fd3` |
| `src/maskgw/runtime/datasource_service.py` | `db8a76c7a26fffc367e2c7dadc346873dff6cd8217bbcfee158d756c5617e200` |
| `tests/test_datasource_verify_gate.py` | `a19532c2a6a6dc3784387c178d0f231f240c7852220f1487492174f23b472c4c` |
| `tests/test_datasource_verify_supervisor.py` | `ad8455a630b21258aba3c2a4a22c376d50119d4e34b410276a86a3e896b4831a` |

Regressões escritas e executadas **antes** de cada correção (reprodução das
revisões independentes):

| defeito | antes | depois |
|---|---|---|
| P2-A — coleta interrompida (primeiro, meio, concorrente) | **3 falhas**: 2, 1 e 2 pendentes nunca recuperados | recuperados, `release()` exatamente uma vez por registro |
| P2-B — `start()` levanta depois de a thread rodar (writer/reader × `RuntimeError`/interrupção) | **4 falhas**: thread viva fora do registro, vaga liberada | registro e vaga retidos até a thread acabar; depois, uma liberação |
| bootstrap nativo incerto (`ident is None`, `start()` interrompido) | **falha** com a regra anterior (`pending` 0) | retido, `close()` incompleto; após o término físico, uma liberação |
| criação real e depois exceção no construtor (`KeyboardInterrupt`/`OSError`), spawn incerto, PID com `poll()` falho, PID com pipe ausente | **6 falhas** sem a adoção antes do construtor (os 2 controles "construtor nunca entrado" passam nos dois casos) | conforme a §1.3 |

| gate | resultado |
|---|---|
| **suíte Python integral** (pilha de 64 MiB), PostgreSQL 16.15, sem deselect | **4.295 testes: 4.282 aprovados, 0 falhas, 0 erros, 13 skips**, 632 s (JUnit). Skips: 8 condicionais de POSIX (5 de `fsync` de diretório, 3 de bits de modo) + 5 de symlink indisponível neste host (WinError 1314). **Nenhum skip por DSN.** Inclui os 39 testes de `test_datasource_verify_gate.py` (3 de PG16 executados) e os 59 de `test_datasource_verify_supervisor.py` |
| focados antes do congelamento | arquivos do gate + bootstrap + separação de planos + lifecycle v2 + resolver: 145 aprovados (5 de DSN sem DSN nessa rodada local); os 12 de criação/início de thread repetidos 5×, sem intermitência |
| Ruff, format, mypy strict, `git diff --check` | aprovados; 179 arquivos/fontes |
| wheel `b7a457b4…3fdf4` e sdist `6bd33ae4…128d` (cópia temporária fora do checkout, venvs novas, `python -I`, sem PYTHONPATH, cwd fora do checkout) | `verify.py` presente; `docs/poc/`, `tests/` e `node_modules` ausentes. Mesmo resultado nos dois: upstream PG16 real aprovado (0,89 s/0,92 s); interrupção após a criação real → filho recolhido, pipes fechados, vaga 4/4, supervisor fechado; spawn incerto → `CONNECTION`, 3 coletas sem liberar, `close()` incompleto, vaga 3/4; bootstrap nativo incerto (`ident is None`) → vaga 3/4 e `close()` incompleto até o término físico, depois fechado com 4/4; `kill()` transitório → recuperado em 0,31 s/0,34 s, 4/4. Nenhuma thread `maskgw-verify-*` viva, nenhum órfão |
| frontend | sem delta rastreado (`git status`/`git diff` em `frontend/` mostram só o `bash.exe.stackdump` alheio); navegadores e Node não foram repetidos nem usados no runtime |

SHA-256 completos dos pacotes, preservados da saída do build antes da remoção
dos temporários:

- wheel: `b7a457b4ffc665f0c746f8e5d3a4b3371f2ba02b1718b35803fa0920dfa3fdf4`;
- sdist: `6bd33ae4b90401ce62ef5ecb36d957eb6046424739081d1fe1fc220a3bcd128d`.

Após estes gates, o fechamento editorial registrou a D-107 e atualizou suas
referências em `CLAUDE.md` e `HANDOFF.md`. Também distinguiu as medições
históricas do contrato atual e corrigiu promessas antigas de liberação no
`finally`. Nenhum código, teste ou recurso funcional mudou; os hashes acima
continuaram idênticos e as suítes não foram repetidas por alterações somente
documentais. Esse fechamento não autoriza commit, push ou etapa posterior.

Comando da suíte (sem senha; `MASKGW_TEST_DSN` exportada antes, só no ambiente
do processo de teste):

```bash
.venv/Scripts/python.exe -c "import threading, pytest; threading.stack_size(64 * 1024 * 1024); raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider', '--junitxml=<tmp>/final.xml']))"
```

### Histórico das rodadas anteriores

### 4.1 Histórico: primeira revisão do `8261dc7` (Windows nativo)

Medições anteriores às correções de coleta interrompida, início incerto de
threads e criação parcial do processo. Os resultados e as expectativas da
matriz abaixo são históricos; o contrato atual está em §1.3/D-107 e a medição
do código final está em §4.0.

Regressões escritas **antes** da correção e executadas contra o `8261dc7`:

| regressão | no `8261dc7` | depois |
|---|---|---|
| finding 1 — `stdout.close()` persistente após ack válido | **falha**: `DID NOT RAISE` (a verificação aprovava) | `CONNECTION`, pipe aberto **não** declarado fechado, vaga retida; após a cura, recolhimento libera a vaga uma vez |
| finding 2 — `kill()` persistente, 17.977 bytes, prazo 0,1 s | **falha**: 18,19 s (limite do teste: prazo + orçamento + 1,5 s = 7,6 s) | 6,16 s; filho vivo e registro pendente com dono até a cura |
| finding 3 — `tests/test_datasource_verify_supervisor.py` (41 casos) | **falha** na coleta: o contrato de ownership (`VerificationSupervisor`, `VerificationShutdownIncompleteError`) não existia | 41/41 |

| gate | resultado |
|---|---|
| testes do gate (`test_datasource_verify_gate.py` 39 + `test_datasource_verify_supervisor.py` 41), PostgreSQL 16 real | **80/80** aprovados, 0 skips; repetidos 8× sem intermitência (5× sem DSN, 3× com DSN) |
| **suíte Python integral** (runner de pilha de 64 MiB), PostgreSQL 16, sem deselect | **4.277 testes: 0 falhas, 0 erros, 13 skips**, 589 s (JUnit). Skips: 8 condicionais de POSIX (os mesmos de antes: 5 de `fsync` de diretório e 3 de bits de modo) + 5 de symlink indisponível neste host (WinError 1314; na medição anterior o privilégio existia). **Nenhum skip por DSN.** |
| Ruff, format, mypy strict | aprovados em `src` e `tests`; ruff/format 179 arquivos; mypy 179 fontes |
| wheel e sdist instalados, `python -I`, cwd fora do checkout, sem PYTHONPATH | `verify.py` embarca no wheel e no sdist; `docs/poc/` e `tests/`, não. Mesmo resultado nos dois pacotes. Upstream real aprovado (1,02 s/0,83 s) com vaga devolvida. Finding 1: `CONNECTION` sem cadeia, pipe aberto, 1 pendente, vaga 3/4; após a cura, recolhido, 4/4. Finding 2: 6,12 s/6,16 s, filho vivo, 1 pendente, 3/4. `close()` incompleto enquanto vivo (`closed=False`); o retry após a cura fecha, 4/4, sem thread. `kill()` transitório recupera em 0,33 s/0,31 s (antes: ~4,3 s), vaga liberada. Nenhum órfão. |

Matriz de combinações (`test_fault_matrix_never_approves_or_frees_over_live_resources`,
23 casos, watchdog independente em cada um; envelopes sobre `Popen`/streams
reais; contagem de `release()` do semáforo):

| falha injetada | resultado |
|---|---|
| `kill` uma vez · `wait` uma vez/sempre · `poll` uma vez · `start` do writer ou do reader · `read` uma vez/sempre · `write` uma vez/sempre · `close` do stdin uma vez | recusado (`CONNECTION`), recolhido |
| `close` do stdout uma vez **após o ack** | aprovado, tudo recolhido |
| `kill` sempre · `poll` sempre · `close` do stdin sempre · `close` do stdout sempre | recusado, **pendente com dono**, vaga retida, 0 `release()`; uma passada sem cura não libera; após a cura, recolhido |
| combinações: `kill` uma vez + `close` stdout sempre · `wait` sempre + `kill` uma vez · `poll` uma vez + `close` stdin uma vez · `read` sempre + `close` stdout uma vez · `start` reader + `kill` uma vez · `write` sempre + `close` stdin sempre · `poll` sempre + `kill` sempre | conforme as linhas acima, incluindo a regra do pendente |

Invariante conferido em todo caso: `poll()` terminado, `closed` nos dois pipes
reais, nenhuma thread `maskgw-verify-*` viva, vaga liberada **exatamente uma
vez** (`releases == 1`) e nunca antes do recolhimento efetivo.

Concorrência, shutdown e composition root:

- 8 coletores simultâneos sobre um pendente curado: 1 `release()`.
- Um pendente retém uma vaga: de 4 verificações simultâneas, 3 entram e 1 é
  recusada **sem criar filho**. Curado o SO, a admissão seguinte recolhe o
  pendente antes de admitir, e a capacidade volta a 4.
- Uma passada de recolhimento com 2 pendentes persistentes cabe em **um**
  orçamento.
- `KeyboardInterrupt` no dono: registro recolhido; com `kill()` persistente,
  continua pendente com dono.
- `close()` do supervisor:
  - com pendente: incompleto, `closed=False`, sem `release()`, admissão
    recusada sem filho; após a cura, o retry fecha e é idempotente;
  - com verificação em voo: incompleto em < 1,5 s, sem esperar o filho;
  - um pendente de outro supervisor é recolhido pelo shutdown do seguinte.
- Startup parcial antes do `DatasourceRuntime` com filho irrecolhível: o erro
  original é preservado (`CONNECTION`, sem `__context__`), nada é publicado, o
  catálogo é solto e o registro fica com dono. Com filho recolhido, o supervisor
  fecha.
- Falha depois do `DatasourceRuntime` (MCP): o `RuntimeError` original é
  preservado e o registro fica com dono.
- `Application.close()` com recurso vivo: erro sanitizado, `state='closing'`,
  catálogo e legado fechados; o retry após a cura chega a `state='closed'`.
- Dublês (`adapter_factory`) e `verifier` injetados não compõem supervisor.

### 4.2 Histórico: 2ª revisão da rodada 1 (Windows nativo)

Histórico preservado: 1ª rodada 25/25 (4.222); revisão 30/30 (4.227). Medições
novas desta revisão:

| gate | resultado |
|---|---|
| testes do gate (`tests/test_datasource_verify_gate.py`), PostgreSQL 16 real | **37/37** aprovados |
| **suíte Python integral** (runner de pilha de 64 MiB), PostgreSQL 16, sem deselect | **4.234 testes: 0 falhas, 0 erros, 8 skips** (condicionais de POSIX; nenhum por DSN); 471 s |
| Ruff, format, mypy strict | aprovados em `src` e `tests`; mypy 91 fontes |
| navegador contra o pacote instalado — checkout/wheel/sdist | `verify.py` embarca no wheel e no sdist; `docs/poc/` não; o filho **importa e roda** via `python -I` (sem PYTHONPATH, cwd fora do checkout) nos dois pacotes instalados: upstream real aprovado; **falha transitória de `kill()` recupera em ~4,3 s, vaga liberada, sem órfão** |
| PoC SCRAM | handshake correto, senha errada recusada, **`c` adulterado recusado**, primitivas == vetor RFC 7677, **interop com `scramp==1.4.5`** nas duas direções (venv temporário) — todos **PASS** |

Matriz determinística de falhas do recolhimento (Windows nativo, watchdog
independente em cada caso de risco de travamento):
- **`kill()`/`wait()`/`poll()` transitório** (falha uma vez): a retentativa
  recolhe tudo; processo encerrado, pipes fechados, threads mortas, vaga
  liberada; `CONNECTION` sem cadeia. (Antes: `kill()` transitório → 15,14 s com
  filho e duas threads vivos; agora ~6 s em processo, ~4,3 s no pacote instalado.)
- **`kill()` persistente** (falha sempre): recolhimento **não confirmado** →
  `VerificationResourceError` → `CONNECTION` sanitizada e **vaga retida
  permanentemente** (fail-closed de capacidade); sem prazo absoluto prometido.
- **`wait()` persistente:** `kill()`+`poll()` ainda confirmam a morte → vaga
  liberada; prova de que o recolhimento não depende de `wait()`.
- **`OSError` na conferência final (`poll()` do `_reap`):** não escapa cru →
  `CONNECTION` sanitizada.
- **Falha ao iniciar o writer (1º start) e ao iniciar o reader (2º start):**
  processo recolhido e **ambos os pipes fechados** (inclusive o da thread que
  nunca iniciou), vaga liberada, sem órfão.
- **P1 — filho que não lê o stdin + payload de 17.977 bytes + prazo 0,25 s:**
  cortado em ~0,28 s, sem órfão.
- **P2 — saída sem parar:** cortada **durante** a leitura.
- **Falha de transporte** (não foi possível criar o filho): `CONNECTION`.
- **Erro de I/O após `{"ok": true}`** (leitura) **e erro de envio** (escrita):
  `io_error` → recusado; bytes acumulados após falha de I/O nunca aprovam.
- **Upstream que conclui o startup/autenticação do PostgreSQL e silencia** nas
  verificações pós-conexão (fake-PG que fala `AuthenticationOk`/`ReadyForQuery` e
  cala na Query): cortado no prazo → `CONNECTION`, sem órfão. O blackhole TCP (que
  nem completa o startup) continua como caso separado.
- Demais: senha errada → `CONNECTION`; capability → `CAPABILITY`; sem vaga →
  `CONNECTION`; saída inválida/grande → categoria fechada; múltiplos endereços
  fixados conectam por `hostaddr` sem segunda resolução; segredo ausente de
  argv/ambiente/stdout/stderr; import do filho sob `python -I` sem PYTHONPATH.

## 5. Limitações e itens abertos

- **D-090 continua aberta:** este gate fecha só a verificação pós-conexão de
  candidatos (gate 1). Validação e masking locais das Etapas 8/11 (gate 2)
  seguem sem teto efetivo.
- *(Histórico, anterior à §1.4:)* executor/barreira/composição não estavam
  implementados, e o event loop ficava bloqueado por até o prazo de uma
  verificação. **Estado atual:** entregues pela D-108 (§1.4), com os limites
  listados abaixo em "Fila dedicada".
- **O prazo de 12 s é teto de UMA verificação**, não de fila, DNS, filesystem nem
  do shutdown inteiro.
- **Falha persistente do SO em recolher** (processo, thread ou pipe que não
  morrem ou não fecham): **não há prazo absoluto garantido**.
  - O registro fica pendente **com dono** no ledger do processo, e a vaga fica
    retida enquanto o recurso viver. O recolhimento é retentado antes de cada
    admissão (até 1 s por verificação, no event loop, sem executor) e no
    shutdown (até 6 s por passada).
  - Com recurso vivo, o shutdown **não se declara concluído**:
    `Application.close()` levanta o erro fixo, e o entrypoint reporta a falha de
    execução. O gateway não se reinicia nem se finaliza sozinho.
  - O ledger vive com o processo: se o processo sair com um filho irrecolhível,
    o que acontece com o filho é do SO.
  - Uma chamada do SO que bloqueie (ex. `close()` preso) não tem teto.
- **Início de thread incerto** (`start()` que não retornou): registro e vaga
  ficam retidos até o término físico comprovado e, se a thread nunca rodar,
  até o reinício do processo. Não há recuperação automática nesse caso.
- **Criação de filho incerta:** um construtor de `Popen` entrado que não
  retorna sem expor PID retém registro e vaga até o reinício, sem recuperação
  automática. Com PID mas sem um dos pipes, o processo é encerrado e o pipe
  conhecido fechado, mas a vaga fica retida pelo pipe desconhecido. A API
  pública **não** cobre uma interrupção entre a criação
  nativa do processo e a exposição do PID/handle dentro do próprio `Popen`.
  Nesse caso o filho pode existir e não é alcançado nem recolhido: não há
  garantia absoluta contra órfãos. Recuperá-lo exigiria um mecanismo de SO novo
  (Job Object, enumeração de processos, subreaper), fora do contrato. A regra
  "PID exposto ⇒ métodos públicos utilizáveis" reflete a ordem do CPython 3.11,
  fixada por teste, não pela documentação da linguagem. Nenhuma das garantias
  cobre toda interrupção assíncrona entre instruções.
- **Fila dedicada (D-108):**
  - não há teto absoluto de shutdown: a drenagem integral espera o trabalho
    aceito, e uma chamada do SO bloqueada não tem limite;
  - concluir o worker antes do `stop()` HTTP não garante a entrega da
    resposta, e a resposta perdida é incerta;
  - interrupções assíncronas entre instruções do próprio ciclo da fila (entre
    registrar e desfazer na admissão, entre concluir e notificar, entre a
    marca de auditoria e a emissão) não são cobertas. A direção é
    conservadora: capacidade retida ou evento perdido, nunca duplicado nem
    executado sem dono;
  - se a própria contenção falhar, uma leitura ainda pode ver o selo anterior
    até o reinício; nenhuma escrita executa;
  - um ticket aceito numa fila congelada conclui como falha sem executar.
- **Janela de admissão (`_admit`), não corrigida:** uma interrupção assíncrona
  entre adquirir a vaga e anexar o registro, ou entre anexar o registro e
  devolvê-lo ao dono, pode reter a vaga sem coletor. A direção é conservadora:
  perde capacidade, nunca libera sobre recurso vivo.
- **Sem teto absoluto:** nem a verificação, nem o cleanup, nem o shutdown têm
  teto absoluto se uma chamada do SO bloquear.
- O histórico da §4.2 descreve a retenção permanente anterior, substituída pela
  §1.3.
- *(Histórico, anterior à §1.5:)* SASLprep, `-PLUS` e a dependência aguardavam
  aval. **Estado atual:** aval recebido em 2026-10-08 (SCRAM-SHA-256, -PLUS
  sobre TLS, SASLprep, `scramp==1.4.17`); as peças puras estão na §1.5 (D-109),
  sem commit. *(Histórico, ao fim da §1.5:)* listener, settings, `SSLContext`
  de produto, driver, prazo, admissão, rate limit e ativação estavam todos
  abertos.
- **Estado atual, parcial (D-110, §1.6):** a integração foi autorizada em
  2026-10-09. Existem, locais e sem commit, o **lote 1** — settings
  (`pgwire/settings.py`) e preparo do `SSLContext` (`pgwire/tls.py`) — e o
  **lote 2** — transporte e driver de startup/autenticação sobre um socket já
  aceito (`pgwire/transport.py`, `pgwire/driver.py`) — e o **lote 3** —
  listener com admissão, rate limit, recolhimento e parada
  (`pgwire/listener.py`) — e o **lote 4** — composição interna em
  `build_application(pgwire=...)`. **Continuam abertos:** resolução limitada
  de hostname no composition root, ativação operacional (recusada no `main`
  enquanto não entregue) e D-090 gate 2. Os gates finais do lote 4 foram
  medidos em 2026-10-12. O gate de runtime moderno foi medido em 2026-10-13
  só no Windows com CPython 3.14.8 temporário (lotes A–C, §1.6): suíte
  integral verde depois da correção só de teste, e os 4 `union-attr` do mypy
  com o alvo 3.14 abertos. O runtime da `.venv` (Python 3.11.3 com OpenSSL
  1.1.1t, fora de suporte) **não** está certificado para produção; nada aqui
  libera operação real.
- O filho depende de `maskgw` instalado na venv do `sys.executable`: em checkout,
  `pip install -e .`; em wheel/sdist, o site-packages é a fonte. `python -I` não
  usa PYTHONPATH.
- Modo legado desligado, separação MCP/PGWire e selos da UI preservados; nenhum
  segredo em erro, log, auditoria ou artefato.
