# W1 Oracle — reator puro do host e contrato da ponte (v2)

2026-11-10. Só desenho prospectivo, Claude2, sessão 51ea0d85, claude-opus-5-5,
esforço medium, sob a delegação vigente. É proposta para revisão do root, não
aprovação individual. Nada foi executado para escrevê-lo: nenhum teste, comando,
Docker, PG, SQL, socket, thread, processo, guard ou sinal.

Base: HEAD/origin 23d8669, que contém o código 861969d.

A v1 (54b5ec87/20241 bytes) fica como dado do root. Esta v2 fecha R1–R5 do
HOST-DESIGN-REVIEW. NATIVE-PLAN v4 e as revisões anteriores ficam como
histórico.

## 1. Fatos fixos lidos na fonte pública

| Peça | Pin | Usado aqui |
|---|---|---|
| main `deploy/oracle9_w1_main.py` | 89c99c65 / 46787 | caminhos, HostLink (linha <512 + LF, 56 linhas), códigos 64–70/HOLD |
| driver `deploy/oracle9_w1_driver.py` | b54a8a94 / 51913 | eventos, prazos, fases/razões de ABORT, `load_pure` |
| puro `deploy/oracle9_w1_controller.py` | 4c155d76 / 22453 | `decode_init`, `decode_control`, `ControlMachine`, constantes |
| EXPECT `docs/poc/oracle9_w1_expect.py` | ce6ff389 / 22114 | gera o pacote LAB_INIT; o reator não o importa |

Nenhum arquivo acima muda.

Itens históricos que este desenho **não** readmite:
- imagem 621cc7f7, wheel 6b63f239 e contexto d4d4b29b;
- postgres:16-alpine;
- CLI, Desktop e pins de config/contexto.

A igualdade do app124 com o checkout também não é readmissão.

## 2. Topologia reconciliada

- **Binds:** três binds RO de arquivo individual, sem bind de diretório, nos
  destinos `MAIN_PATH`, `DRIVER_PATH` e `PURE_PATH` do main.
- **Verificação de origem:**
  - O main confere driver e puro antes de executá-los.
  - O main não se auto-pina: o hash 89c99c65/46787 da cópia montada é
    conferido pela admissão futura do host.
  - Montagem, legibilidade pelo UID 10001 e conjunto exato de mounts são
    fatos nativos.
- **Canal:**
  - Entrada pelo fd0: INIT `>4sI` MGI1 + corpo, e frames de controle de 16
    bytes.
  - Saída pelo fd1: linhas JSON canônicas ASCII de até 512 bytes contando o
    LF, no máximo 56 linhas.
- **NOT_PREPARED:** shell, raiz, nonce, task, estado, comando, rede, IP e
  credenciais.

## 3. Núcleo confiável e fonte única de expectativas (R2)

O chamador fornece o namespace do puro já carregado.

- **Carga do puro (lote futuro do programa host):**
  - Usa o `load_pure(reader)` público do driver, com um `reader` sobre os
    mesmos bytes que serão montados.
  - O próprio arquivo do driver tem os bytes b54 conferidos antes do import.
  - Não há loader nem camada de proveniência novos.
- **O que o reator confere:**
  - `type(core) is types.ModuleType`;
  - presença e callable de `decode_init`, `decode_control` e `ControlMachine`;
  - constantes exatas: `GO`=1, `STOP`=2, `NOSTOP`=3, `ACK`=4, `T4_CASE`=23,
    `T5_CASE`=24, `T6_CASE`=25, `MAX_HOST_FRAMES`=50, `JOBS`=19,
    `CASES`=25, `PREFIX_CASES`=24.
- **Limite da conferência:** ModuleType não autentica origem. A autenticidade
  vem só do pin do chamador.

**Expectativas — fonte única:** o reator recebe o **mesmo** `init_packet` que
enviará. Não recebe records independentes.

- Antes do parse, confere `type(init_packet) is bytes` e
  `8 < len ≤ 8 + 65536`.
- Em seguida chama uma vez `core.decode_init(init_packet)` e guarda só:
  - `expected: tuple[ExpectedJob, ...]`, o objeto público do puro, com 19
    itens;
  - os bytes do pacote, privados, para o único `Send(INIT)`.
- O `LabInit` decodificado é descartado logo após extrair `expected`: senha,
  chave e canários não ficam em atributo.
- Não há promessa de zeroização da memória Python.
- **Sem efeitos:** nenhum gerador do EXPECT é chamado pelo reator, nenhuma
  leitura de segredo externo, nenhuma geração. `LabRefusal` do core vira
  `HostRefusal("INIT")`.

## 4. API exata (R1)

Futuro `docs/poc/oracle9_w1_host_reactor.py`, só definições:
- sem relógio, I/O, arquivo, env, CLI, thread, processo, socket ou import do
  driver;
- todos os DTOs `@dataclass(frozen=True, slots=True)`, com repr redigido onde
  há bytes.

### 4.1 Construção e métodos

```python
class HostReactor:
    def __init__(self, core: types.ModuleType, init_packet: bytes, policy: HostPolicy) -> None
    def feed(self, item: Line | Delivered | ActDone | Exited) -> Step
    def status(self) -> HostStatus          # leitura pura, sem efeito
Step = Send | Act | Wait | Done
```

**Protocolo único de falha:**
- Qualquer entrada inválida ou fora de ordem **levanta** `HostRefusal(category)`.
- O reator passa a REFUSED de forma pegajosa: toda chamada posterior de
  `feed` levanta `HostRefusal` com a **mesma** categoria.
- `status()` continua disponível e expõe a categoria e a pendência original
  por identidade.
- `Done` só é devolvido por um fim legítimo do protocolo (§8). Recusa nunca
  produz `Done`.
- **Depois de `Done`:** todo `feed` levanta ORDER e o reator passa a REFUSED
  com ORDER. Nada é reaberto e nenhum recibo é aceito. O `Done` já devolvido
  é imutável: guarda a referência original do `orphan` para o chamador
  externo e nunca muda depois.
- **Onde se valida:**
  - Validação de `core`, `init_packet` e `HostPolicy` pertence ao
    construtor; falha levanta CORE, INIT ou POLICY e não cria instância.
  - Os DTOs de entrada (§4.2) são **carriers** frozen sem `__post_init__`
    que levante: aceitam qualquer valor.
  - Toda validação de tipo, domínio e tempo das entradas ocorre **dentro de
    `feed`**, para que a recusa fique registrada de forma pegajosa na
    instância.

**Estados que não são recusa:** falha legítima de efeito (Delivery
NOT_SENT/UNKNOWN/tardia, ActStatus FAILED/UNKNOWN, T4 NOT_FOUND) não é
recusa. Ela leva a fases explícitas (`DRAINING` ou caso FAIL), descritas
em §6–§8.

**`HostRefusal(Exception)`:**
- atributo `category`, e `args == (category,)`;
- levantada fora de handler, sem causa, contexto ou valor bruto.

Categorias:

| Categoria | Quando |
|---|---|
| CORE | namespace inválido |
| INIT | pacote inválido |
| POLICY | política inválida |
| INPUT | tipo de entrada |
| TIME | tempo inválido ou regressivo |
| RECEIPT | token, tipo ou kind de recibo errado |
| ORDER | entrada fora da fase |
| LINE | enquadramento |
| EVENT | esquema ou valor do evento |
| SEQUENCE | next_seq ou espelho |
| SUMMARY | incoerência do SUMMARY |
| EXIT | saída incoerente com as linhas |

**Precedência de verificação** (a primeira que falha decide a categoria):
1. já REFUSED;
2. INPUT;
3. TIME;
4. RECEIPT/ORDER;
5. LINE;
6. EVENT;
7. SEQUENCE/SUMMARY;
8. EXIT.

### 4.2 Entradas

Todo tempo é monotônico do host, em **segundos**, `int` ou `float` exatos
(bool não), finito e ≥ 0, injetado pelo chamador. O reator não chama relógio.

**Ordem dos instantes:** é monotônica não decrescente em todas as entradas.
Cada instante tem de ser ≥ o último já visto (`last_at`); senão TIME.

**Origem dos instantes:**
- São leituras do **owner da ponte**, feitas no ponto em que ele serializa
  cada observação para `feed`, depois da observação.
- Não valem timestamps pré-capturados por pumps de leitura que, entregues
  depois de um `Delivered.post`, regrediriam; isso é TIME.
- Um recibo atrasado nunca é retrodatado.
- Não se presume igualdade entre relógios do host e do container.

```python
Line(raw: bytes, at: float)                              # at = instante pós-leitura da linha
Delivered(token: int, delivery: Delivery, pre: float, post: float)   # pre ≤ post
ActDone(token: int, kind: ActKind, status: ActStatus, facts: ActFacts | None, at: float)
Exited(at: float, status: ExitStatus, code: int | None, eof: bool, reaped: bool)
```

**Domínios:**
- `Delivery`: NOT_SENT / SENT / UNKNOWN.
  - SENT significa só que o pipe local da CLI aceitou todos os bytes.
  - SENT nunca é prova de recebimento pelo container.
- `ActStatus`: OK / FAILED / UNKNOWN.
- `ExitStatus`: EXITED / NO_EXIT / UNKNOWN.
  - Com EXITED, `code` é int exato 0..255; nos outros, `code` é None.
  - `eof` e `reaped` são bool exatos.
  - NO_EXIT significa que o processo seguia vivo no fim do orçamento da
    ponte.
- **Vínculo do recibo:**
  - `Delivered.pre` ≥ `Send.issued_at` e `post` ≥ `pre`.
  - `ActDone.at` é o instante em que a porta **retornou**; só ele conta para
    prazo.
  - Nenhum tempo declarado dentro de `facts` é aceito: os facts não têm
    campo de tempo.

**`ActFacts`** — fechados por `ActKind`. Tipo errado para o kind dá RECEIPT;
com OK, `facts` é obrigatório; com FAILED/UNKNOWN, `facts` é None.

| ActKind | Facts | Condição para OK coerente |
|---|---|---|
| TERMINATE_ONE_BACKEND | `TerminateFacts(found: int ≥0, terminated: bool)` | `found == 1` e `terminated is True` |
| PAUSE_PG | `PauseFacts(paused: bool)` | `paused is True` |
| RESTORE_PG | `RestoreFacts(running: bool, paused: bool, ready: bool)` | running True, paused False, ready True |
| OBSERVE_HEAVY | `ObserveFacts(found: bool, observations: int 1..20)` | qualquer `found` |
| ZERO_BACKENDS | `ZeroFacts(backends: int ≥0)` | `backends == 0` |
| KILL_GATEWAY | `KillFacts(stop_confirmed: bool, oom_killed: bool)` | stop_confirmed True e oom_killed False |

OK com facts incoerentes dá RECEIPT. A porta deve relatar FAILED, nunca OK.

### 4.3 Saídas

```python
Send(token: int, purpose: Purpose, payload: bytes, issued_at: float, deadline: float)
Act(token: int, kind: ActKind, case: int, issued_at: float, deadline: float)
Wait()
Done(outcome: Outcome, verdicts: tuple[Verdict, ...], controller_retained: bool,
     orphan: Send | Act | None)
```

- **`Purpose`:** INIT / GO / ACK / STOP / NOSTOP. O payload é o pacote INIT
  ou um frame de 16 bytes (§5). O repr é redigido.
- **`Verdict`:** PASS / FAIL / NOT_RUN. `verdicts` tem exatamente 25 itens,
  um por caso, na ordem dos casos.
- **`Outcome`:**
  - COMPLETE_CANDIDATE: T6 cumprido conforme §7;
  - T6_FAILED, ABORTED e RETAINED;
  - GUARD_FAILED, SETUP_FAILED, LOAD_FAILED, LINK_FAILED e CONTROL;
  - BROKEN: o host parou de enviar e o fim chegou sem linhas terminais;
  - ENDED_UNKNOWN: sem prova suficiente de fim.
- **`token`:** int exato 1, 2, 3… crescente; um por `Send`/`Act`.
- **`deadline`:** absoluto, `trigger.at + orçamento` da política. `issued_at`
  é o `at` da entrada que gerou a saída.
- **`Done` não libera nada:**
  - É só um resumo modelado e candidato a evidência.
  - Não concede limpeza, release, kill ou remoção.
  - `controller_retained` relata só o que as linhas e a saída do controlador
    disseram.
  - A limpeza física por identidade fica inteira fora deste modelo, assim
    como qualquer status simples de cleanup.

### 4.4 Pendência única e vista de status

Há no máximo **uma** pendência (`Send` ou `Act`) por vez. A próxima saída só
é emitida depois do recibo exato da pendência, com token, tipo e kind iguais.

| Recibo | Resultado |
|---|---|
| SENT com `post < deadline` | avança: o espelho faz `accept`/`join` só agora; INIT não usa o espelho |
| SENT com `post ≥ deadline` | entrega tardia: fase DRAINING, sem retry |
| NOT_SENT ou UNKNOWN | fase DRAINING, sem retry nem rebase de seq/prazo |
| ActDone com `at ≥ deadline` | tardio: FAILED do efeito, mesmo que os facts digam OK |
| ActDone FAILED/UNKNOWN | caso FAIL conforme §6, depois DRAINING; o reator não emite mais Send |

Uma Line não terminal durante pendência dá ORDER. A exceção são ABORT e
TERMINAL, regidos por §8.

```python
HostStatus(phase: HostPhase, lines: int, controls_sent: int, last_at: float | None,
           pending: Send | Act | None, orphan: Send | Act | None,
           orphan_receipt: Delivered | ActDone | None,
           refusal: str | None, verdicts: tuple[Verdict, ...])
```

- **`HostPhase`:** AWAIT_GUARD, AWAIT_INIT_OK, RUNNING, DRAINING, ENDING,
  DONE, REFUSED.
- **Identidade:** `pending` e `orphan` são os mesmos objetos emitidos, por
  identidade.
- **Pendência única:** há no máximo uma pendência. Quando ela vira orphan
  (§8), `pending` passa a None e `orphan` guarda o original.
- **Recibo do orphan:**
  - Em ENDING, um recibo válido do orphan (mesmo token, tipo e kind) é
    registrado **uma vez** em `orphan_receipt`.
  - Esse registro não avança o espelho nem emite Send/Act.
  - Um segundo recibo do mesmo orphan é recusado (RECEIPT).

### 4.5 Política (sem nomes indefinidos)

```python
HostPolicy(init_s, go_s, ack_s, fatal_ack_s, act_s, t4_window_s,
           t6_epsilon, t6_margin_s, t6_kill_min_s)
```

Todos os campos são `float` ou `int` exatos e finitos, em segundos, exceto
`t6_epsilon`, que é adimensional. Os domínios ficam abaixo de cada cap do
driver; o atraso de trânsito só reduz o tempo disponível.

| Campo | Domínio | Cap do driver |
|---|---|---|
| `init_s` | 0 < x < 10 | INIT_CAP_S 10 |
| `go_s` | 0 < x < 19 | GO_CAP_S 20, e `window − 1` |
| `ack_s` | 0 < x < 20 | ACK_CAP_S 20 |
| `fatal_ack_s` | 0 < x < 90 | FATAL_ACK_CAP_S 90 |
| `act_s` | 0 < x < go_s | — |
| `t4_window_s` | 0 < x ≤ 10 | janela de observação do plano |
| `t6_epsilon` | 0 ≤ x < 0.01 | erro relativo de taxa entre monotônicos |
| `t6_margin_s` | 0 ≤ x | — |
| `t6_kill_min_s` | 0 < x | — |

**Restrição:** uma ação pré-GO ou pré-ACK consome o mesmo orçamento do envio
seguinte. Assim, o `Send` seguinte vence em `trigger.at + go_s` (ou `ack_s`
/ `fatal_ack_s`), contados do mesmo `trigger.at`, com `act_s` menor que esse
orçamento.

**Valores:**
- Para uso nativo, os valores são NOT_PREPARED e serão fixados no estado
  antes de qualquer efeito.
- Nos testes, a política é entrada explícita.
- A ε **não é medida**: é premissa.

## 5. Encoder mínimo e espelho do controle

```python
pack_control(core: types.ModuleType, *, kind: int, case: int, seq: int) -> bytes
# struct.pack(">4sBBHII", b"MGL1", 1, kind, case, seq, 0)
```

- **Função pública pura:**
  - Recebe explicitamente o core confiável já carregado, sem global, cache
    ou loader.
  - Nunca toca nem avança `ControlMachine`.
  - O reator a chama com o próprio core do construtor.
- **Conferência imediata:** todo frame é decodificado por
  `core.decode_control(frame)`, que tem de devolver `(kind, case, seq)`
  idênticos.
- **Domínios aceitos:** kind ∈ {1, 2, 3, 4}, case 1..25 e seq 1..50, todos
  int exatos.
- **Falhas:**
  - primitivo fora de tipo ou domínio → `HostRefusal("SEQUENCE")`, sem frame;
  - core inválido, `decode_control` ausente, recusa ou ida e volta diferente
    → `HostRefusal("CORE")`.
- **Espelho:** é um `core.ControlMachine()` próprio.
  - A linha READY/RESULT/ARMED chama `emit` e exige `next_seq` igual ao do
    evento; senão SEQUENCE.
  - O SENT completo de GO/ACK chama `accept(frame)`.
  - ARMED{23} chama `handoff()`; o SENT de STOP/NOSTOP chama `join(frame)`.
  - A linha SUMMARY chama `summary()`.
  - Uma `LabRefusal` do espelho vira SEQUENCE.

**Fronteiras exatas do caminho feliz** (o seq de cada frame é o next_seq do
evento que o pede):

| Caso | READY | Frame host | RESULT/ARMED | Frame host |
|---|---|---|---|---|
| P k (1..19) | 2k−1 | GO 2k−1 | RESULT 2k | ACK 2k |
| T1 20 | 39 | GO 39 | RESULT 40 | ACK 40 |
| T2 21 | 41 | GO 41 | RESULT 42 | ACK 42 |
| T3 22 | 43 | GO 43 | RESULT 44 | ACK 44 |
| T4 23 | 45 | GO 45 | ARMED 46 → STOP/NOSTOP 46 → RESULT 47 | ACK 47 |
| T5 24 | 48 | GO 48 | RESULT 49 | ACK 49 |
| T6 25 | 50 | GO 50 | ARMED 51 | **nenhum** |

**Contagens:**
- Frames enviados: 50, o máximo. Não existe frame 51; o `next_seq` 51 do
  ARMED{25} é informativo.
- Linhas: GUARD 1 + INIT_OK 1 + READY 25 + RESULT 24 + ARMED 2 + SUMMARY 1 =
  54.
- Sobram 2 para ABORT/TERMINAL, total 56. A **57ª linha é recusada (LINE)
  antes do parse**: se já houve 56 linhas, qualquer `Line` dá LINE.

## 6. Eventos, domínios e ações por caso (R5)

### 6.1 Enquadramento e esquema

**LINE (só enquadramento):**
- `raw` não é `bytes`;
- `len(raw) > 512`;
- não termina em um único LF final;
- contém outro LF ou CR;
- não é ASCII;
- contador já em 56.

O limite de 512 é só elegibilidade de enquadramento; não cria nem afrouxa
esquema.

**EVENT (passou pelo enquadramento):**
- JSON inválido;
- chave duplicada;
- NaN ou Infinity;
- re-dump `sort_keys`, `(",", ":")`, `ensure_ascii` diferente dos bytes sem
  LF;
- chaves que não sejam exatas;
- tipo ou valor fora do domínio.

O teste distingue os dois pela API pública. Exemplos: 511 bytes ASCII que
não são JSON, mais o LF, dão EVENT; 512 + LF (513 bytes) dão LINE. Nenhum
campo de enchimento é inventado.

| `e` | Chaves | Domínio |
|---|---|---|
| GUARD | as, dumpable, e, pdeathsig, pid | 402653184, 0, 0, 1 (sem Threads; Threads 1 é fato nativo) |
| INIT_OK | e | — |
| READY | case, e, next_seq | case = próximo caso |
| ARMED | case, e, live_window_ms, next_seq | 23 com None; 25 com int 1000..30000 |
| RESULT | 12 chaves (abaixo) | — |
| SUMMARY | e, failed, global_pass, prefix_cases | list de ints crescentes ⊆ 1..24, false, 24 |
| ABORT | case, e, phase, reason, retained | ver 6.3 |
| TERMINAL | e, outcome | ABORTED / RETAINED / T6_UNKILLED |

**RESULT** — chaves: bytes, case, e, kind, next_seq, reason, release, rows,
sink, stop_applied, truncated, verdict. "null" significa JSON null exato.

| Caso | kind | verdict | reason | release | rows | bytes | truncated | sink | stop_applied |
|---|---|---|---|---|---|---|---|---|---|
| P RESULT (1–10, 12, 17, 19) | RESULT | PASS | null | null | = expected.rows | = expected.bytes | true só no job 9 | "OK" | null |
| P ERROR (11, 13–16, 18) | ERROR | PASS | = expected.reason | null | null | null | null | null | null |
| 20 | FATAL | PASS | CONNECTION ou INTERNAL | ∈ REL | null | null | null | null | null |
| 21, 22 | FATAL | PASS | JOB | ∈ REL | null | null | null | null | null |
| 23 | FATAL | PASS sse stop_applied true, senão FAIL | JOB | ∈ REL | null | null | null | null | bool |
| 24 | EOF | PASS sse reason null | null, EXIT_NONZERO, EXIT_LATE, WAIT_LATE ou NO_EXIT | "RELEASED" | null | null | null | null | null |

**Legenda e limites:**
- `REL = {ReleaseOutcome.RELEASED.value, ReleaseOutcome.ALREADY_RELEASED.value}`,
  lidos do enum público pelo reator e pelo teste.
- O RESULT não traz digest. `sink` "OK", rows e bytes são **relato do
  controlador**, comparado com o expected do mesmo pacote. Não são observação
  independente do host.

### 6.2 Ações e consequências

| Caso | Gatilho | Ação | OK | FAILED/UNKNOWN/tardio |
|---|---|---|---|---|
| 20 | READY | TERMINATE_ONE_BACKEND | Send GO | DRAINING, sem GO |
| 21 | READY | PAUSE_PG | Send GO | DRAINING |
| 21 | RESULT | RESTORE_PG | Send ACK | DRAINING, sem ACK |
| 23 | ARMED{23} | OBSERVE_HEAVY, até `t4_window_s` | found True → STOP; found False (NOT_FOUND) → NOSTOP | DRAINING, sem frame |
| 24 | RESULT | ZERO_BACKENDS | Send ACK | DRAINING, sem ACK |
| 25 | ARMED{25} | KILL_GATEWAY (§7) | — | T6 FAIL |

- **Sem ação:** nos demais casos, READY leva a Send GO e RESULT a Send ACK.
- **Prazos:** o orçamento de ACK é `fatal_ack_s` nos casos 20–23 e `ack_s`
  nos demais; o de GO é sempre `go_s`.
- **T4 — FAIL legítimo, não recusa:**
  - NOSTOP depois de NOT_FOUND;
  - STOP com RESULT23 `stop_applied` false (STOP tardio ou não aplicado).
- **T4 — FAIL, recusa ou DRAINING:**
  - STOP com `stop_applied` true é PASS;
  - NOSTOP com `stop_applied` true dá EVENT, porque o watcher só aplica STOP;
  - observação FAILED/UNKNOWN é DRAINING.
- **DRAINING:** nenhum Send/Act novo. O reator espera ABORT/TERMINAL e
  Exited. O controlador vence o próprio prazo e aborta.

### 6.3 ABORT e TERMINAL (domínios da fonte b54)

**Campos do ABORT:**
- `case`: int 0..25. 0 é a partida, antes do caso 1.
- `phase` ∈ {LOAD, INIT, CAPTURE, LEDGER, CASE, CLEANUP}.
- `reason` ∈ {LOAD, INIT, CAPTURE, LEDGER, SESSION, OUTPUT, IDLE_WINDOW, EOF,
  TIMEOUT, SINK, JOIN, WATCHER, EXPECTATION, PHASE, CONTROL, SQL, DESTINATION}.
- `retained`: bool.

**Sequência:**
- ABORT pode vir seguido de TERMINAL ABORTED (retained false) ou RETAINED
  (retained true). Outra combinação dá EVENT.
- Pode chegar TERMINAL sem ABORT anterior, quando a escrita do ABORT falhou.
- TERMINAL T6_UNKILLED só é válido depois de ARMED{25}.

### 6.4 SUMMARY

Válido só depois de ACK{24} SENT. Exige:
- `prefix_cases` 24 e `global_pass` false;
- `failed == sorted({c ∈ 1..24 : verdict[c] == FAIL} ∪ set(espelho.summary().failed_cases))`.

`failed_cases` é `(23,)` depois de NOSTOP. Qualquer diferença dá SUMMARY.

## 7. Cerca de T6 e conclusão positiva (R3, R5)

**Dados:**
- `t_go_pre` = `Delivered.pre` do Send GO 25, válido só com SENT e `post <
  deadline`.
- `live_s` = `live_window_ms / 1000` (ms → s).

**Raciocínio:**
- O driver calcula `live` depois de aceitar o GO completo. Logo o instante
  real desse cálculo é ≥ `t_go_pre`.
- O `floor` só reduz.
- Portanto, o fim real da janela é ≥ `t_go_pre + live_s` em tempo real.

**Premissa obrigatória, não medida:**
- Durações medidas pelo monotônico do host e do container diferem no
  máximo por uma fração ε.
- Não se presume igualdade de relógios entre host e container.
- Suspensão, WSL2 ou VM podem violar a premissa. O frescor recusa pausas
  longas, mas não prova a ausência de skew curto.

**Fórmula** (capturada uma vez, nunca recalculada):

```text
fence = t_go_pre + live_s * (1 - t6_epsilon) - t6_margin_s
```

**Admissão do kill:** só emite `Act(KILL_GATEWAY, 25, deadline=fence)` se
`fence - ARMED25.at ≥ t6_kill_min_s`. Senão devolve `Done(T6_FAILED)` sem
kill de salvamento; a limpeza é externa.

**T6 PASS candidato** (Outcome COMPLETE_CANDIDATE, verdict[25] PASS) exige
todos, em entradas separadas:
1. ActDone KILL_GATEWAY OK, `KillFacts(stop_confirmed=True, oom_killed=False)`,
   com `ActDone.at < fence`. OOM nunca substitui o kill próprio.
2. Nenhuma Line depois de ARMED{25}. Qualquer linha, inclusive TERMINAL,
   resulta em T6 FAIL.
3. `Exited(status=EXITED, eof=True, reaped=True)`, com `code ≠ 69` e `at ≥`
   o recibo do kill. O código 137 sozinho não basta: vale só em conjunto
   com o item 1.
4. Depois de Exited, `Act(ZERO_BACKENDS, 25)` com OK e `backends == 0`.

**Exceção explícita à regra geral de fim por Exited (§8):**
- Só depois do ActDone KILL_GATEWAY OK e no prazo (item 1), um Exited válido
  **não** encerra. Ele devolve `Act(ZERO_BACKENDS, 25)`.
- Só o OK exato desse Act produz `Done(COMPLETE_CANDIDATE)`. ZERO_BACKENDS
  FAILED, UNKNOWN ou tardio produz `Done(T6_FAILED)`.
- Exited que chega com o KILL ainda pendente encerra de forma conservadora:
  - o KILL vira orphan;
  - o resultado é `Done(T6_FAILED)` com EXITED, ou `ENDED_UNKNOWN` com
    NO_EXIT/UNKNOWN;
  - um recibo posterior do orphan nunca transforma isso em sucesso
    retroativo.
- **Obrigação da ponte:** para o caminho positivo, a ponte serializa o
  recibo do kill **antes** de coletar e entregar o Exited.

**Natureza dos fatos:**
- Kill, EOF/reap e backends são **fatos de portas futuras confiáveis**,
  separados.
- O bool de um modelo não é prova nativa.
- COMPLETE_CANDIDATE não é PASS global nem nativo: é só candidato a
  evidência para a auditoria futura.

## 8. Fim e precedência entre linha terminal, saída e pendência (R5)

- **Linha terminal durante pendência:** ABORT ou TERMINAL válidos são aceitos
  mesmo com pendência. A pendência vira `orphan` e não se emite mais
  Send/Act.
  - Recibo posterior do orphan, com token igual, é aceito e registrado.
  - Recibo de outro token dá RECEIPT.
  - A fase vai para ENDING.
- **Saída durante pendência:** Exited é aceito em qualquer fase não terminal.
  Também transforma a pendência em orphan e decide o `Done`.
  - Única exceção: o caminho positivo de T6 da §7, onde o Exited depois do
    kill OK devolve `Act(ZERO_BACKENDS, 25)`.

**Mapeamento de saída** (incoerência dá EXIT, retido via status):

| Linhas vistas | Exited | Outcome |
|---|---|---|
| nenhuma | EXITED 64/65/66/67/70 | SETUP/LOAD/LINK/GUARD_FAILED/CONTROL |
| nenhuma, ou parcial sem terminal | NO_EXIT/UNKNOWN | RETAINED/ENDED_UNKNOWN; inclui o defeito inesperado do driver, que retém sem linha |
| TERMINAL ABORTED | EXITED 68 | ABORTED |
| TERMINAL ABORTED | NO_EXIT | RETAINED (main em HOLD por `safe_exit` falso) |
| TERMINAL RETAINED | NO_EXIT | RETAINED |
| TERMINAL RETAINED | EXITED qualquer | EXIT |
| TERMINAL T6_UNKILLED | EXITED 69 | T6_FAILED |
| ARMED{25} sem linha posterior | EXITED ≠ 69, eof e reaped, com §7.1 OK | segue §7.4 |
| ARMED{25} sem linha posterior | EXITED sem kill OK, ou oom_killed | T6_FAILED |
| ARMED{25} sem linha posterior | NO_EXIT/UNKNOWN | ENDED_UNKNOWN |
| DRAINING sem terminal | EXITED 70 | CONTROL |
| DRAINING sem terminal | outro EXITED | BROKEN |

- `controller_retained` é true para RETAINED, para ABORT retained, para
  todo NO_EXIT e para todo UNKNOWN (ExitStatus UNKNOWN e ENDED_UNKNOWN).
  - É conservador.
  - Nenhum valor desse flag, nem um `Done` de conclusão, autoriza limpeza
    física.
- `verdicts`: PASS/FAIL dos RESULT recebidos, T6 só por §7, demais NOT_RUN.

## 9. Reuso conferido e limites (fontes lidas, não importadas nem executadas)

- **Reutilizados:**
  - controlador puro (§3, §5);
  - `load_pure` do driver, pelo chamador futuro;
  - pacote do EXPECT, só via `init_packet`;
  - `oracle9_cycle_freshness.py` puro (TOTAL 300 s, GAP 30 s, 9 observações)
    como admissão antes de B. Não limita a duração da rodada.
- **Não lido, sem reuso afirmado:** `oracle9_clock_sample.py`.
- **Não reutilizáveis como módulo:**
  - `oracle9_w1_run.py`: coordenador one-shot com caminhos e pins históricos
    no topo.
  - `w1_bootstrap_channel.py`: um frame + trailer, READY ≤512, stdout
    ≤32768, pins históricos.
  - Deles ficam só os conceitos de Delivery, ticket e release por ausência
    de CID.
- **Sem camadas novas:** nenhuma camada nova de SO, transporte ou
  proveniência.

## 10. Contrato das portas futuras da ponte (fora deste lote)

**A ponte produz exatamente as entradas da §4.2:**
- `Line` com o `at` pós-leitura, montada em blocos sem alocar mais de 512
  bytes por linha;
- `Delivered` com `pre` lido antes do primeiro byte e `post` lido depois do
  retorno;
- `ActDone` com o `at` lido no retorno da porta;
- `Exited` com status, EOF do stdout e reap reais.

**Regras:**
- Um único processo de CLI para o gateway, com stdin PIPE, stdout PIPE e
  stderr DEVNULL.
- Escrita parcial no prazo vira UNKNOWN, sem retry.
- Kill e reap por identidade só na ação T6 ou na limpeza externa.
- O pacote INIT nunca é registrado.
- **Escopo:** pins de CLI, stdlib/Proactor e contexto, PG, comandos/SQL das
  ações, admissão e limpeza são lotes próprios.

## 11. Oráculos futuros e primeiro incremento

O único primeiro incremento é `tests/test_oracle9_w1_host_reactor.py`. O
módulo `docs/poc/oracle9_w1_host_reactor.py` fica ausente até o root rever,
medir e congelar o RED.

| Grupo | Oráculo |
|---|---|
| H1 | `pack_control(core, …)` dos 4 kinds, ida e volta por `decode_control`; kind 0/5, case 0/26 e seq 0/51 → SEQUENCE sem frame |
| H2 | 511 bytes + LF não-JSON → EVENT; 513 bytes → LINE; sem LF, LF/CR interno, não ASCII → LINE; duplicada, NaN, não canônica, chave extra ou faltante, bool como int → EVENT; 57ª linha → LINE antes do parse |
| H3 | construtor: core inválido → CORE; pacote não-bytes, ≤8 ou >65544 → INIT antes do parse; `decode_init` recusando → INIT; status sem segredo; expected igual ao `decode_init` do mesmo pacote |
| H4 | caminho feliz completo com linhas b54 sintéticas: fronteiras da tabela §5, ARMED{25} com next_seq 51, nenhum frame 51, 50 frames e 54 linhas; COMPLETE_CANDIDATE só com §7 |
| H5 | domínios RESULT 1–24 da §6.1, sem digest; T5 com 5 razões; T4 PASS sse stop_applied true |
| H6 | pendência única; token, tipo ou kind errados → RECEIPT; linha não terminal pendente → ORDER; recusa pegajosa com a mesma categoria e pendência por identidade |
| H7 | NOT_SENT/UNKNOWN/SENT tardio → DRAINING, espelho parado, sem novo Send |
| H8 | tempos: bool, NaN, inf, negativo ou regressivo → TIME; ActDone tardio com facts OK → efeito FAILED |
| H9 | ações 20/21/24 e facts incoerentes com OK → RECEIPT |
| H10 | T4: NOT_FOUND → NOSTOP e RESULT FAIL legítimo; STOP não aplicado → FAIL; observação FAILED → DRAINING; NOSTOP com stop_applied true → EVENT |
| H11 | T6: fence por `t_go_pre` (nunca pelo recebimento); kill em `fence − δ` PASS, em `fence` FAIL; orçamento < kill_min → T6_FAILED sem Act; oom_killed → FAIL; linha após ARMED{25} → FAIL; 69 → FAIL; ZERO_BACKENDS exigido |
| H12 | ABORT/TERMINAL durante pendência → orphan; domínios 6.3; mapa de saída §8 inteiro; SUMMARY incoerente → SUMMARY |
| H13 | estáticos por AST: sem import de time/os/socket/threading/subprocess/driver, sem chamada de relógio. Admite só o armazenamento privado necessário do `init_packet`/payload do `Send(INIT)`, com repr redigido. Proíbe reter o `LabInit` inteiro ou campos separados de chave/senha/canário. Sem promessa de zeroização |
| H14 | `pack_control(core, …)`: primitivo inválido → SEQUENCE; core sem `decode_control` ou ida e volta divergente → CORE; o espelho não avança |
| H15 | carriers com valores inválidos são construídos sem erro e recusados só em `feed`, de forma pegajosa |
| H16 | orphan: recibo em ENDING registrado uma vez em `orphan_receipt`; segundo recibo → RECEIPT; `feed` depois de `Done` → ORDER; `Done.orphan` é o original |
| H17 | T6: Exited depois do kill OK → `Act(ZERO_BACKENDS)`; Exited com kill pendente → T6_FAILED/ENDED_UNKNOWN sem sucesso retroativo; UNKNOWN → `controller_retained` true |

Relógio e portas dos testes são só valores injetados; nenhum sleep real.

## 12. Separação de prontidão

- **Concluído só com fakes:** puro, driver (T5 incluído), main com SO
  simulado e EXPECT. Os 849 relacionados verdes são históricos.
- **Restante:**
  1. reator (este desenho → testes/RED → código);
  2. ponte;
  3. preparo do PG16;
  4. admissão da imagem, pacote, três binds e perfil;
  5. frescor e relógio;
  6. ownership, journal, varredura de segredos, exportação e limpeza;
  7. estado e comando revistos;
  8. uma invocação;
  9. auditoria requisito→evidência.
- **T5 físico e T2/T4/T6 nativos:** BLOCK_NATIVE.
- **Gates de produto:** B1, B2, D-090 gate 2, C1/D-119, ingressos
  PGWire/MCP/Admin/IDE, TLS upstream, patches e produção continuam abertos.
  Um laboratório nativo verde não é produto pronto. SQL PGWire continua
  recusada e o Gateway segue indisponível.

Nenhuma raiz, estado, nonce, credencial, comando ou deploy foi criado.
Nenhuma leitura de runtime, config, binário, ambiente ou arquivo privado.
Estado16 e a tentativa consumida continuam fixos.
