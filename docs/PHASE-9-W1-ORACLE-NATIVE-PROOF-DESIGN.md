# W1 Oracle: prova nativa benigna do pump/bind e contenção externa — desenho NP-D3

2026-11-13. Somente desenho prospectivo, sob delegação. Claude2, sessão 51ea0d85, claude-opus-5-5/medium.

**Histórico de versões:**
- A D1 (e038841a) e a D2 (c4f56ac3) seguem NATIVE-PROOF-REVIEW NP1–NP4.
- **Esta D3** aplica, só como documento (NP6), as propostas revistas de §2/§4/§5 e o fechamento de consistência de §3/§6/§7/§8, sob NP4/NP5/NP6. O pacote revisado é a9705c5b.

**O que esta D3 não é:**
- não é código, teste, admissão nativa, aceite de S, receita nem aprovação;
- não traz dispensa semântica aprovada individualmente;
- não autoriza nenhuma chamada.

**Ficam fixos:**
- pump e bind publicados em `docs/poc/oracle9_w1_proactor_pump.py`: `ProactorPump`, `_bind_over` (1041–1085) e `bind_proactor_pump` (1088–1109);
- PROACTOR-DESIGN P3 §15 (N1–N16), BIND-DESIGN B2 §2–§5 e BIND-REVIEW B4;
- backend `docs/poc/pg16_shell_admission_win32.py` (10c9058f) e adaptador `docs/poc/pg16_shell_native_control_win32.py` (eaebedd6);
- código 793473a, testes, probes, pins, app124, estado16 e tentativa consumida.

Fontes, APIs, limites e enums não mudam. T5, driver, main e EXPECT existem e não são reabertos.

## 1. Escopo e não-escopo

- **Alvo:** só os fatos N1–N16 do pump e os fatos de construção e close do bind, sobre recursos PRÓPRIOS de uma única tentativa, com um helper benigno.
- **Fora:**
  - `run_host` e owner/ponte/reator com gateway real;
  - T2/T4/T5/T6, Docker, PG, SQL, rede, segredos e produto.

  Um PASS aqui não fecha W1, B1, B2, D-090, C1, D119, TLS, ingressos nem produção.
- **Sem nova camada:** nenhum coordenador, owner, abstração de SO ou lançador novo.
  - O único código futuro previsto é um harness de prova de uso único (§6), sujeito a oráculos, RED e revisão próprios.
  - Esse harness chama só a API pública do pump.

## 2. Fronteira de posse e identidade (antes do loop)

Há três níveis de posse, nesta ordem de criação.

1. **Supervisor externo S, fora de P:**
   - precisa estar ADMITIDO e armado ANTES de qualquer efeito;
   - detém um job do SO por tentativa e uma capacidade de parada externa (§4);
   - TENTA terminar a árvore e observa a contabilidade do job pelas APIs públicas (§7).
2. **Processo de prova P:**
   - é criado por S dentro do job;
   - a thread principal de P é a dona do loop (exigência de `bind_proactor_pump`, 1095).
3. **Dentro de P:** o harness mantém em referências locais FORTES, até o FIM de P:
   - o pump devolvido, OU o Throwable exato de bind com o traceback original (B4);
   - a sequência de eventos;
   - o primeiro controle.

   Regras dessa retenção:
   - nada é descartado cedo, entregue a gc ou finalizador, nem trocado por serialização no relatório;
   - o primeiro controle nunca é testado com `bool`, e `__traceback__`/`__context__` não são alterados;
   - a semântica de controle de S, mais fraca e já existente (§4), é outra e não se confunde com esta.

**Primitivas candidatas, existentes e reutilizadas sem mudança:**
- `Owner` do backend (10c9058f) e `NestedJobOwner` do adaptador (eaebedd6).
- APIs públicas: `setup`, `start`, `wait`, `exit_code`, `accounting`, `members`, `check_config`, `terminate`, `available`, `read` e `close`; mais `close_inner`, se houver aninhamento.
- Não há framework, owner nem lançador novo.
- São CANDIDATAS. Não são um S admitido nem prova física.

**Autenticidade não é identidade de runtime:**
- O SHA do fonte e o contrato público dizem só QUAL código e versão são candidatos.
- A identidade de runtime, ou seja, a custódia do job e do processo reais de cada tentativa, só pode vir do ciclo de vida de um `Owner` ADMITIDO: o que o próprio owner registrou no ledger a partir das chamadas que fez.
- Nem um hash de fonte nem um PID, sozinhos, estabelecem essa identidade.
- Saídas indeterminadas ou em quarentena (`quarantine`, backend 545–546 e 775–786) nunca passam a ser posse conhecida só porque um texto diz isso.
- Nenhum identificador, valor ou operação é definido aqui.

**Ordem estática pretendida, que não é fato do kernel:**
- `_start` cria o processo suspenso, com `JOB_LIST` na criação.
- Antes do `ResumeThread`, `_start` confere `IsProcessInJob`, a configuração, a contagem e os membros (backend 693–809).
- NÃO estão medidos:
  - a atomicidade do `JOB_LIST`;
  - o efeito real dos limites;
  - `KILL_ON_JOB_CLOSE`;
  - a contabilidade real.

**Limite cumulativo:**
- `accounting()` recusa `TotalProcesses > 2`, além de `active > total` (backend 831–840).
- Pelo contrato público da Microsoft, `TotalProcesses` inclui processos encerrados.
- Cada job admite **P mais UM helper durante toda a sua vida**, não apenas um helper de cada vez.
- Um segundo helper posterior também passa do limite, mesmo sem rodar ao mesmo tempo que o primeiro.
- Uma associação recusada pelo limite pode, ela própria, incrementar o contador. Nunca se infere contador zero ou ausência de efeito a partir de uma falha, inclusive no N7.

**Regras:**
- A identidade da tentativa é a do job de S. Nada em P a substitui.
- Throwable retido em P é retenção CONHECIDA, não contenção. Os resíduos desconhecidos (§3) só têm uma TENTATIVA de contenção por S.
- S não lê memória de P nem estado privado do SDK. Recebe só:
  - o canal de evidência (§5);
  - os próprios fatos observados pelas APIs públicas (§7).
- Preparar valores, argv, receitas, raiz, nonce ou estado é proibido aqui.
- Verify (b3755d49), lifecycle (7bbf734c), runner (b4198fe1) e entry (356d2291) pertencem ao lote antigo de três casos. Não certificam o S novo e não recebem rótulos novos por analogia.

**Gap:**
- Há primitivas candidatas, mas faltam vínculo revisado, autoridade, premissas, contenção externa efetivamente admitida e evidência real.
- Sem S admitido, a prova fica BLOQUEADA.

## 3. Resíduos: conhecidos e desconhecidos

A coluna de contenção descreve uma responsabilidade prospectiva, isto é, uma tentativa. Não é resultado garantido.

| Resíduo | Conhecido por P? | Responsabilidade prospectiva (tentativa) | Pode ser declarado |
|---|---|---|---|
| Loop/pump retidos após `close()` False ou BROKEN | sim (pump retido) | P retém até o fim; depois, só tentativa do S candidato | retido, nunca liberado |
| Loop conhecido em F2/F3 (B4) | sim (traceback) | P retém até o fim; depois, só tentativa do S candidato | retido |
| F1: fábrica falhou sem objeto (K1: self-pipe, IOCP, wakeup fd) | não | S candidato, não admitido: só tentativa de contenção pelo job | desconhecido |
| `close()` bloqueado (N8, `IocpProactor.close`) | não retorna | S candidato, via parada externa não admitida; terminar é só tentativa até ser observado | FAIL N8 se o bloqueio for observado; resíduo desconhecido |
| Controle entre o retorno do bind e a atribuição | não | S candidato: só tentativa | desconhecido |
| S4 pendente para sempre; START_FAILED sem handle | parcial (fase) | P retém; depois, só tentativa do S candidato | UNKNOWN |
| EOF pausado no cap (R4/N4) | sim | P retém; depois, só tentativa do S candidato | retido por desenho |
| Automatismos do SDK (`__del__`, close interno; K4) | não | — | nunca contam como quitação |

- **Retenção conhecida em P:** é retenção conhecida, não contenção.
  - P nunca descarta pump, Throwable ou handles para "limpar".
  - O caminho NORMAL esperado de fim de P é a saída própria depois do relatório. Saída inesperada, queda, relatório ausente ou causa não observada deixam o estado UNKNOWN/INCONCLUSIVO, com custódia retida; nunca são sucesso e nenhuma causa é inferida. Observações de saída são separadas de prova de liberação física.
- **Nada se libera sozinho:**
  - Nada é liberado ou dado como descartado automaticamente por kill, saída de processo, silêncio ou prazo vencido.
  - Vencer o prazo do N8 não prova que a árvore terminou.
  - Terminação por S é limpeza, nunca prova.
- **UNKNOWN e falha de contenção:** levam a uma DECISÃO de reter a custódia. Essa decisão não é um estado observado do backend.
  - O relatório traz só o estado do Owner efetivamente lido. Por exemplo, o `Win32Error("WIN32_TREE")` de `accounting()` com `total > 2` deixa o Owner em RUNNING (backend 838–839).
  - Nenhum HELD é fabricado ou gravado, o Owner não é alterado e nenhuma transição de estado é inferida.
  - UNKNOWN nunca vale PASS.
- **Fatos observados:** espera, `accounting` e `members` observados (§7) são fatos delimitados de recursos próprios naquele instante. Não provam handles, memória ou efeito global no SO.

## 4. Tempo: observação limitada, chamadas sem teto e parada externa

- **Limitado e lógico em P:**
  - os alvos de `run_until(target, stop)`, os prazos por caso e as janelas de cada N;
  - valem só enquanto as chamadas retornam.
- **Sem teto em P:**
  - construção do `ProactorEventLoop` e `ProactorPump.__init__` sobre o loop real;
  - `loop.close()` e o `subprocess_exec` interno;
  - qualquer chamada síncrona do SDK.

  Nenhum mecanismo em P as interrompe.
- **Sem teto em S também:**
  - `wait(ms)` aceita só 0..50 (backend 812–819), e `_abort` espera 5000 ms (525).
  - Os orçamentos de decisão são conferidos entre chamadas ao SO.
  - Nada disso é teto absoluto de parede: `CreateProcessW`, `CloseHandle` ou outro `_call` podem bloquear dentro de S.
- **Parada externa:**
  - É um pré-requisito explícito e NÃO ADMITIDO. As APIs existentes não o cumprem, e não há promessa de que ela funcione.
  - Ao vencer, parar ou terminar é só uma TENTATIVA até que algo seja observado.
  - O retorno de `terminate()` ou de kill não garante a limpeza da árvore.
  - Só contam a espera concluída e `accounting`/`members` observados depois, nas condições do §7. Mesmo isso é fato delimitado.
  - Se o resultado é UNKNOWN ou falha, a custódia fica retida (decisão, §3) e a tentativa nunca é PASS.
  - Os N em curso valem FAIL (bloqueio observado) ou INCONCLUSIVO, e nada vale PASS.
- **Controles:**
  - Em P continua valendo: depois do primeiro controle, nenhum efeito, e identidade B4 preservada.
  - S tem semântica própria e mais fraca: `_guarded` chama `_interrupt` dentro do `except` principal, e `_interrupt` captura só Exception na contenção (backend 561–589). Um segundo controle em S pode substituir o primeiro.
  - A garantia de P não é estendida a S, e o backend não muda.
- Observações de limpeza e estados UNKNOWN nunca são sucesso de prova.
- Não se usa `wait_for`, cancelamento, thread auxiliar, sinal ou injeção privada para dar teto ao SDK.

## 5. Canal de evidência limitado

- **Transporte:** stdout de P lido por `available()`/`read()` (backend 866–890).
  - Entrega blocos de no máximo 4096 bytes, NÃO linhas.
  - Um bloco pode trazer linha parcial ou várias linhas.
  - Um `read` vazio, sozinho, não prova EOF. Só conta o EOF confirmado pelo contrato do backend.
- **Contrato de linha:**
  - linhas ASCII canônicas e fechadas, cada uma com no máximo 512 bytes INCLUINDO o LF;
  - um número MÁXIMO de linhas DECLARADO ANTES da tentativa;
  - os limites seguem a família HostLink já usada no W1; os valores são NOT_PREPARED;
  - os limites são aplicados de forma incremental sobre os bytes recebidos;
  - ordem conferida; linha a mais, longa demais, malformada ou fora de ordem é recusada como FAIL de canal, sem nova tentativa.
- **Campos:** só enums fechados e inteiros exatos:
  - caso N;
  - ordem dos eventos por nome do enum de eventos do pump;
  - `BindResult`/`PumpCloseResult` como nomes;
  - returncode;
  - contadores;
  - veredito local do harness.

  Nunca entram argv, comandos, bytes do helper, mensagens, repr ou texto de exceção, caminhos, ambiente ou segredos. Não há logger, framework de parsing nem schema novo.
- **Instante de recebimento:**
  - para cada linha completa, S registra o instante de RECEBIMENTO pelo próprio relógio;
  - as restrições de P depois de um controle não proíbem observações de S;
  - esse instante é observação de S: não prova o envio por P, nem CreateProcess, nem EOF do helper;
  - não há framework de relógio nem valores preparados.
- **READY:**
  - P tenta escrevê-la antes de qualquer import nativo, mas isso é só ordem pretendida;
  - a escrita pode ter ocorrido e o recebimento em S atrasar, falhar ou nunca chegar;
  - sem READY no prazo, o estado é UNKNOWN E a tentativa vale INCONCLUSIVO;
  - ausência de READY nunca prova ausência de import, bind, efeito ou no-op;
  - S mantém a posse e tenta conter pelo job, que pela ordem pretendida já cobria P antes do nascimento (§2);
  - nenhum handshake adicional é criado para fabricar prova negativa.
- **Controles em P:** depois de capturar o primeiro controle, o harness SÓ:
  - mantém a identidade exata, sem `bool` e sem alterar `__traceback__`/`__context__`;
  - retém os próprios dados com leituras puras.

  Nenhuma nova escrita no canal, flush, leitura de relógio, close ou qualquer outro efeito, nem para anunciar o controle. Não existe linha CONTROL nem camada de log.
- **Classificação por S:**
  - S classifica pelos próprios fatos observados: linhas recebidas e seus instantes, prazo, saída de P e contabilidade pública;
  - silêncio ou falta de linha nunca significa ausência de controle;
  - um controle, conhecido ou suspeito, nunca é PASS.
- **Limites de interpretação que continuam valendo:**
  - a janela de eventos do N2 NÃO prova a ordem de CreateProcess;
  - o N4 exige fatos positivos, nunca mera ausência de `pipe_lost` (§7).

## 6. Harness e helper (só categorias)

**Harness de prova**, código futuro, não produto:
- faz uma única chamada a `bind_proactor_pump()` por P;
- depois usa só `now`, `schedule_start`, `run_until`, `close` e os métodos do handle entregues em `started`;
- `StartRequest`/`events` são objetos próprios que só registram, como os já usados nos oráculos do pump; não há owner novo;
- não importa SDK privado, não faz monkeypatch nem substitui classes ou funções do produto;
- não lê variável de ambiente nem configuração.

**Helper benigno**, por categoria:
- programa local do próprio runtime admitido, em modo isolado;
- sem rede, segredos, banco, Docker ou escrita fora de área própria descartável;
- sem criar NENHUM processo descendente:
  - P mais o helper já esgotam `TotalProcesses ≤ 2` durante toda a vida do job (backend 831–840);
  - uma associação recusada pelo limite também pode incrementar o contador;
- comportamentos fechados e sintéticos:
  - emitir N bytes determinísticos no stdout;
  - ler stdin até EOF;
  - aguardar fechamento;
  - sair com código c (inclusive c > 255);
  - ou não iniciar (falha de partida por alvo inexistente);
- argv, caminhos e valores são NOT_PREPARED; uma revisão admite cada perfil antes do uso.

**Casos e jobs:**
- Cada P faz uma única chamada de bind e tem número finito de casos e observações.
- Um mesmo job admite no máximo P mais UM helper durante toda a sua vida. Casos que precisam de mais de um helper NÃO podem reutilizar o mesmo job em série.
- Subcasos independentes, DECLARADOS ANTES, cada um com owner, job e P próprios, são só possibilidade documental. Não são retry, admissão nem alocação.
- Este desenho não faz nenhuma alocação. Casos sem alocação ou acima do limite ficam BLOQUEADOS/NOT_PREPARED.
- Dentro de um job, os casos que retêm (N4) ou bloqueiam (N8) vêm por último e encerram a PROGRESSÃO desta tentativa no job; isso não garante terminação, close ou liberação física. Qualquer contenção por S segue tentada e não admitida, com custódia retida em caso UNKNOWN (§3/§4/§7). Não há nova tentativa no mesmo job.
- Não se reutilizam a tentativa consumida nem o estado16.
- Backend, limites e testes antigos não são alterados para caber.

## 7. Matriz N1–N16

Notação: "Ev" = categoria da evidência; P/F/I = PASS/FAIL/INCONCLUSIVO. O escopo é sempre "este runtime admitido, este helper, este job, esta tentativa". Todo N obrigatório permanece com escopo e status próprios; nenhum é declarado "não aplicável".

**Inventário de S, antes do close:**
- é capturado só pelas APIs públicas, com o Owner ainda RUNNING e os handles ainda em posse, ANTES de `close()`;
- `wait`, `exit_code`, `accounting`, `members`, `check_config` e `available` exigem RUNNING (backend 813, 822, 833, 843, 852, 868);
- depois de CLOSED, esses métodos não podem ser chamados, e nenhum recurso já descartado é consultado.

**Fechamento em falha:** se o inventário público exigido não puder ser obtido (`Win32Error`, total acima do limite, Owner fora de RUNNING ou qualquer outra falha):
- o caso vale UNKNOWN/INCONCLUSIVO ou BLOQUEADO, a custódia fica retida, e nunca vale PASS;
- não se contorna o problema com `_accounting`/`_members` privados, nem mudando backend, API ou limites;
- não se consulta recurso CLOSED, nem se infere quiescência só porque `terminate()` retornou ou porque houve saída;
- não se chama `close()` só para fabricar uma liberação bem-sucedida;
- a parada externa segue não admitida, sem promessa de que funcione.

Isto é restrição de compatibilidade, não incidente nativo reproduzido.

**Owner.close() confirmado:** quer dizer que `Owner.close()` retorna None sem levantar exceção E que o estado lido em seguida é "CLOSED" (backend 916–919). Não é um veredito genérico True.

| N | Ev | PASS | FAIL | INCONCLUSIVO |
|---|---|---|---|---|
| N1 ordem de callbacks | sequência de eventos registrada no harness e retorno de S4 | `started` precede os demais eventos conforme P3 §7. Unicidade exigida só nos fatos únicos do contrato: `started`, `exited`, `closed` e `pipe_lost` por fd. `data` e `write_resumed` podem repetir | evento antes de `started`, ou fato único repetido (`started`/`exited`/`closed`, `pipe_lost` do mesmo fd) | a ordem pendente antes do waiter não ocorreu (não é forçável) |
| N2 authorize → CreateProcess | marca no `authorize` e eventos seguintes | só PASS PARCIAL da janela medida | — (um evento intermediário, sozinho, não é FAIL: pode ser legítimo depois da criação e antes de `started`) | a propriedade authorize→CreateProcess no SO sem evidência que localize a criação; N2 nunca tem PASS completo |
| N3 escrita com high=0 | `write`, `buffer_size`, `write_resumed` | cada escrita classificada como SENT síncrona ou via `write_resumed`, sem perda | SENT com buffer > 0 ou sem classificação | só um dos caminhos ocorreu |
| N4 EOF pausado | fatos POSITIVOS: `pause_reading` registrado, término do helper observado e cenário previsto ocorrido | retenção como R4 prevê, com os três fatos | EOF entregue com a leitura pausada | falta qualquer fato positivo; nunca PASS só porque `pipe_lost` não veio |
| N5 fechamento de pipes e handle | em P: eventos `closed` e close do handle. Em S, com o Owner RUNNING: espera concluída, `accounting` com active 0, `members` vazio e EOF; depois, Owner.close() confirmado | todos esses fatos observados nessa ordem; é fato local delimitado, não liberação física completa | evento ausente, ou close do pump False numa entrada quiescente | handles no SO sem observação admitida; inventário público falho; `close()` com NOT_QUIESCENT ou HELD |
| N6 close assentado não mata; código 1 | returncode antes e depois do CLOSE do handle; `kill` em helper vivo | código natural inalterado; `exited` 1 após kill | código alterado pelo close | — |
| N7 falhas de partida | `start_failed`/`not_started`, fase e categorias de falha preservadas | classificação conforme P3 §6 | NOT_STARTED depois de efeito possível | efeito de criação incerto, ou contador consumido; falha não prova contador zero nem ausência de efeito |
| N8 `loop.close` quiescente | retorno de `close()` do pump dentro da janela | só PASS da SUBPROPRIEDADE medida: retorno True observado localmente. Não fecha wakeup fd, executor nem liberação física; o N8 completo fica pendente | bloqueio observado | prazo vencido não prova contenção nem terminação; wakeup fd e executor; N8 completo |
| N9 logs | registros limitados do logger `asyncio`, por handler público do harness | nenhum canário de argv/dados nos registros capturados | canário presente | ausência de registro não prova ausência de outros destinos |
| N10 exit > 255 | `exited(code)` | código exato entregue | código alterado | — (limite do owner K6 continua) |
| N11 KeyboardInterrupt real | precisa de evento de console externo | — | — | BLOQUEADO até capacidade e autoridade admitidas |
| N12 memória | métricas do processo P observadas por S | dentro de teto declarado antes | acima do teto | sem métrica admitida |
| N13 voltas ociosas | `run_until` sem eventos até o alvo | retorna no alvo sem PumpFault | PumpFault de ociosidade em caso nominal | — |
| N14 estratégia cap/pausa | — | — | — | OPEN: é desenho, não medição; N4 só confirma o risco |
| N15 hooks de auditoria e sinal | admissão do runtime | — | — | não admitido; ASSUMIDO só como precondição; sem enumeração pública |
| N16 inserção parcial de `call_at`/`create_task` | — | — | — | INCONCLUSIVO pelo contrato (não injetável publicamente) |

- **Construção e close do bind (BIND §7.2):**
  - **PASS delimitado:** `bind_result` PUMP e a subpropriedade do N8 (retorno True local). O N8 completo fica pendente.
  - **F2/F3 com Throwable:** retido, nunca PASS.
  - **F1:** desconhecido; só há tentativa de contenção pelo S candidato, não admitido.
  - **Recusas do wrapper** (plataforma, thread, loop rodando): só podem ser observadas como `PumpFault` sem efeito; PASS delimitado.
- **Agregado:**
  - Todo N obrigatório permanece com escopo e status próprios. Nenhum é declarado "não aplicável".
  - Um subconjunto medido pode receber PASS nomeado N a N, e só se:
    - cada N do subconjunto for PASS;
    - o canal estiver íntegro (linhas e máximo declarado antes);
    - P sair por conta própria depois do relatório;
    - S tiver observado, com o Owner RUNNING, espera concluída, active 0, `members` vazio e EOF;
    - em seguida vier Owner.close() confirmado.
  - Em qualquer outro caso: FAIL, INCONCLUSIVO ou BLOQUEADO, com resíduos e custódia retidos.
  - Mesmo o PASS do subconjunto é fato delimitado de recursos próprios, não release global.
- **Gate completo pump/bind continua OPEN:**
  - N2 é parcial, N8 está pendente no todo, N11 bloqueado, N14 OPEN e N15 não admitido; N16 segue o tratamento particular do seu contrato aceito.
  - PASS de subconjunto não é PASS do gate completo.
  - Não há PASS do gate completo até que cada requisito seja cumprido ou receba revisão explícita própria. Este desenho não concede dispensa.

## 8. O que falta e não é resolvido neste lote

1. **Autoridade:** aprovação explícita de uma execução nativa, com host, destino e revisor da evidência.
2. **Admissão do runtime de S e de P:**
   - pins do interpretador real (CPython 3.11.3/Windows é só referência histórica);
   - hooks (N15), handler de sinal e wakeup fd prévio (K1);
   - ambiente herdado.
3. **S:**
   - As primitivas candidatas `Owner` (10c9058f) e `NestedJobOwner` (eaebedd6) existem sem mudança, mas NÃO estão admitidas.
   - Faltam:
     - autoridade;
     - capacidade de parada externa: wait e orçamentos não são teto de parede, e chamadas de S podem bloquear;
     - evidência real da contenção.
   - Faltam também decisões de consistência:
     - alocação de subcasos e jobs (§6), hoje sem alocação, com os casos correspondentes BLOQUEADOS;
     - modo de observar o inventário (§7).
4. **Componentes antigos:** verify (b3755d49), lifecycle (7bbf734c), runner (b4198fe1) e entry (356d2291) são específicos do lote antigo de três casos. Não certificam S nem esta prova.
5. **Perfis do helper e limites do canal:** valores revistos, inclusive o máximo de linhas; hoje NOT_PREPARED.
6. **Ordem do trabalho futuro:** depois de 1–5, só então oráculos e RED do harness, e só então o código do harness.

**Limites deste lote:**
- Nenhum desses itens é resolvido NESTE LOTE, que é só documental: não traz código, teste nem admissão nativa.
- Framework, owner ou camada genérica nova não são aceitos como substituto de autoridade ou evidência.
- Trabalho futuro de implementação e teste continua permitido, desde que revisado, com oráculos e RED e na ordem do item 6, quando autoridade e contrato estiverem de fato fechados.
- Nenhuma restrição atual é dispensada, e não há permissão genérica de chamada nativa.
- N1–N16, o gate do bind, T5 físico e todos os gates de produto continuam OPEN. O Gateway segue indisponível.

Política Senff: desenho e código derivados de IA exigem revisão humana e de segurança antes do merge.
