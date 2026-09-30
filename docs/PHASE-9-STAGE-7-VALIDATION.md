# Fase 9 — validação da Etapa 7 (infraestrutura de segurança; **em andamento**)

Autorizada pelo usuário em 2026-09-30, somente para a **infraestrutura de
segurança** da Etapa 7, conforme o desenho aprovado nesta conversa. **A Etapa 7
NÃO está concluída**: esta rodada entrega o gate pós-conexão da D-090 e uma PoC
comparativa de SCRAM; o listener PGWire, consultas e os itens das Etapas 8–12 não
foram iniciados. A D-090 permanece aberta enquanto os demais gates (validação e
masking locais das Etapas 8/11) não existirem; a v2 continua proibida em operação
real.

## 1. Entregue nesta rodada

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

## 2. NÃO entregue nesta rodada (segue não iniciado)

- **Executor dedicado, barreira atômica de submissão×shutdown e bloqueio de
  composição de leitura** (Contratos 1 e 3 do desenho): desenhados e aprovados,
  mas são um segundo corpo de trabalho, com sua própria matriz de concorrência;
  ficam para um incremento próprio, validado à parte. Os handlers v2 continuam
  `async` chamando o coordenador **de forma síncrona no event loop** (D-059).
  **Sem executor, o event loop continua bloqueado durante uma verificação**: o
  gate torna essa espera **finita** (teto de uma verificação), mas **não a
  remove** — o handler v2 ainda não responde outras rotas enquanto uma
  verificação está em voo. Tornar o event loop responsivo durante a verificação
  é o executor dedicado, fora desta rodada.
- **Listener PGWire**, TLS, `SSLRequest`, `StartupMessage`, autenticação SCRAM de
  produção, limites de sessão/idle, framing — nada iniciado.
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
- **Executor/barreira/composição** ainda não implementados (§2). **Sem executor,
  o event loop continua bloqueado por até o prazo de uma verificação** — o gate
  limita essa espera, não a remove.
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
- **Janela de admissão (`_admit`), não corrigida:** uma interrupção assíncrona
  entre adquirir a vaga e anexar o registro, ou entre anexar o registro e
  devolvê-lo ao dono, pode reter a vaga sem coletor. A direção é conservadora:
  perde capacidade, nunca libera sobre recurso vivo.
- **Sem teto absoluto:** nem a verificação, nem o cleanup, nem o shutdown têm
  teto absoluto se uma chamada do SO bloquear.
- O histórico da §4.2 descreve a retenção permanente anterior, substituída pela
  §1.3.
- **SCRAM de produção** aguarda aval (SASLprep e channel binding `-PLUS` em
  aberto); a PoC não restringe senha a ASCII nem escolhe mecanismo/dependência.
- O filho depende de `maskgw` instalado na venv do `sys.executable`: em checkout,
  `pip install -e .`; em wheel/sdist, o site-packages é a fonte. `python -I` não
  usa PYTHONPATH.
- Modo legado desligado, separação MCP/PGWire e selos da UI preservados; nenhum
  segredo em erro, log, auditoria ou artefato.
