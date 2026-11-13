# W1 Oracle: chamador host-side linear mínimo — desenho H3

2026-11-13. Somente desenho, sob delegação. Claude2, sessão 51ea0d85, claude-opus-5-5/medium. Revisa H2 (9024c3d7) conforme HOST-RUN-REVIEW HR2.1–5 e conclui o rascunho parcial 46545539 conforme HR3 e HR4, mantendo o que HR1 fechou. Não é fonte, teste, entrypoint, prova nativa nem aprovação.

Fixos, reusados sem alteração: ProactorPump/_bind_over (3cb74292), PortOwnership (a5d233ae), DuplexBridge (5a09be1c), HostReactor (e86f8e32), testes/probes, app124, state16 e tentativa. `docs/poc/oracle9_w1_host_run.py` e o teste ficam AUSENTES até revisão integral e RED congelado. A contagem de linhas não é afirmada como medida.

## 1. Fronteira

- Uma função linear que compõe objetos existentes na ordem do Harness (`tests/test_oracle9_w1_port_ownership.py:929-948, 1474-1531`).
- Sem motor, coordenador, porta, camada de SO, laço `while` ou API nova.
- Não importa asyncio, subprocess, socket, threading, signal, os nem docs.poc.
- Não lê arquivo, ambiente nem relógio próprio: o tempo vem só de `owner.clock().now()`, e apenas nas fases normais.
- `CliPlan` real, argv, scope, packet, segredos, root/nonce/estado e pins são NOT_PREPARED e injetados pelo chamador confiável. O pin dos bytes é obrigação do loader confiável; nenhum loader novo aqui.

## 2. Tipos (repr redigido constante; dataclasses com `slots`)

```text
HostRunWindows(frozen): settle_s, audit_s, dispose_s   # float exato, finito, 0<x<=30
HostRunInputs(frozen): owner_ns, bridge_ns, reactor_ns, pump_ns, core: object;
    packet, policy, plan, limits, budget: object; windows: object; bind: object
HostCustody(mutável, slots; valores iniciais):
    claimed: bool = False;  stage: HostRunStage | None = None
    bind_result: BindResult = BindResult.NOT_CALLED
    bind_throwable: BaseException | None = None;  bind_candidate: object | None = None
    pump, owner, host, bridge, result: object | None = None
    first_control: BaseException | None = None;   report: HostRunReport | None = None
HostRunStep(enum): ADMISSION BIND OWNER HOST BRIDGE RUN SEAL SETTLE AUDIT
    DISPOSE CLOSE REPORT
HostRunStage(enum): REFUSED_CUSTODY REFUSED_INPUT BIND_REFUSED OWNER_REFUSED
    HOST_REFUSED BRIDGE_REFUSED RUN_REFUSED CLEANUP_FAULT RUN_DONE CONTROL
BindResult(enum): NOT_CALLED PUMP FAULT CONTROL INVALID_RETURN
PumpCloseResult(enum): NOT_ATTEMPTED RETURNED_TRUE RETURNED_FALSE INVALID_RETURN
    FAULT CONTROL
FaultSource(enum): OWNER HOST BRIDGE PUMP BOUNDARY
HostFault(frozen): step: HostRunStep; source: FaultSource; category: str
HostRunReport(frozen): stage: HostRunStage; bind_result: BindResult;
    faults: tuple[HostFault, ...]       # <= len(HostRunStep) == 12, um por passo
    reactor_refusal: str | None; done_outcome: object | None  # membro Outcome
    bridge_status: object | None; fence: object | None   # domínios exatos em §9
    audit: object | None; custody_view: object | None
    audit_ready: bool; dispose_attempts: int; closed_handles: int
    pump_close: PumpCloseResult; report_complete: bool
def run_host(inputs: object, custody: object) -> HostRunReport
# seam privada única da montagem (§9.1); run_host e o oráculo H14 usam a MESMA
_Snapshots(frozen): audit: object | None; fence: object | None
    custody_view: object | None; bridge_status: object | None
    complete: bool; report_fault: bool; first_control: BaseException | None
def _collect_snapshots(
    readers: tuple[Callable[[], object] | None, Callable[[], object] | None,
                   Callable[[], object] | None],          # audit, custody, status
    domains: tuple[type, type, type, type],                # AuditReport, WorkFence,
                                                           # CustodyView, BridgeStatus
    first_control: BaseException | None,
) -> _Snapshots
```

**Domínio fechado de `category`:**
- `.value` de um membro do `OwnershipFault` capturado, para source OWNER;
- `.value` de um membro do `BridgeFault` capturado, para source BRIDGE;
- para source HOST, um dos rótulos `HostRefusal` aceitos pela própria ponte publicada (`oracle9_w1_duplex_bridge.py:66-81`): CORE, INIT, POLICY, INPUT, TIME, RECEIPT, ORDER, LINE, EVENT, SEQUENCE, SUMMARY, EXIT;
- `"PUMP"` para PumpFault;
- `"BOUNDARY"`.

Um rótulo fora desse domínio, de um tipo inesperado ou de uma Exception comum vira `(BOUNDARY, "BOUNDARY")`. Nunca entram objeto de exceção, args ou texto. `reactor_refusal` só aceita a mesma lista; fora dela vira None.

## 3. Custódia e admissão exatas (HR2.2)

1. **Custódia.** É recusada com REFUSED_CUSTODY, SEM escrita, sem bind e sem efeito, se acontecer qualquer um destes:
   - `type(custody) is not HostCustody`;
   - `custody.claimed is not False` (isso inclui um não-bool);
   - qualquer outro campo diferente do valor inicial, comparado com `is`.

   Uma custódia anterior ou alheia fica intacta.
2. **Claim one-shot:** `custody.claimed = True` antes de qualquer outra validação. Daí em diante, toda saída grava `stage` e `report`.
3. **Inputs.** `type(inputs) is HostRunInputs`. Cada campo é lido UMA vez para variáveis locais; não há releitura depois do bind.
   - `type(windows) is HostRunWindows`;
   - cada janela é float exato, finito e em 0 < x ≤ 30, copiado para local;
   - `callable(bind)`.
4. **Namespaces.** Para cada um, `type(ns) is types.ModuleType` ANTES de `vars(ns)`. Lê `vars` uma única vez e captura as identidades da tabela, todas exigindo `isinstance(x, type)`. Depois só essas são usadas.

   | ns | identidades |
   |---|---|
   | owner | PortOwnership, CliPlan, OwnerLimits, AuditKind, DisposeKind, PhysicalState, InvocationKind, ProtocolState, OwnershipRefusal, OwnershipFault, WorkFence, AuditReport, CustodyView |
   | bridge | DuplexBridge, DuplexBudget, BridgeRefusal, BridgeFault, BridgeStatus, BridgeRunResult |
   | reactor | HostReactor, HostRefusal, Done, Outcome |
   | pump | ProactorPump, PumpFault |
5. **Tipos exatos antes do bind:** `type(plan) is CliPlan`, `type(limits) is OwnerLimits` e `type(budget) is DuplexBudget`.

Qualquer falha em 3–5 dá REFUSED_INPUT. O conteúdo de plan/budget/policy/ packet/core só é validado pelos construtores existentes, DEPOIS do bind.

## 4. Ordem, prazos e snapshots

| # | Passo | Prazo / natureza |
|---|---|---|
| 1 | bind (§5) | sem teto nativo (K1/N8) |
| 2–4 | PortOwnership → HostReactor → DuplexBridge | puros (owner:1308-1350; bridge:406-463) |
| 5 | `result = bridge.run()` | uma vez; `budget.overall_s <= 300` lógico |
| 6 | `owner.seal()` | explícito; consulta o relógio só no primeiro |
| 7 | `Ds = now + settle_s`; `settle(Ds)` | Ds calculado uma vez |
| 8 | `fence = owner.seal()` | refresh: fence atual (owner:2401-2459) |
| 9 | auditorias (§6) | `Da = now + audit_s`, comum às duas e aos seus settles |
| 10 | disposições (§7) | `Dd = now + dispose_s`, uma vez |
| 11 | `pump.close()` | sem teto nativo |
| 12 | relatório (§9) | só leituras puras protegidas, sem seal nem relógio |

- Nenhum prazo é renovado ao passar de etapa.
- Prazos lógicos limitam só o agendamento owner/pump. Bind, close e chamadas síncronas do SDK não têm teto de parede; NÃO se afirma duração total limitada.
- Decisões depois de um settle usam o fence refrescado.
- **Relógio grosso.** Se `now <= fence.work_settled_at`, `begin_audit` recusa com STATE. Isso vira `HostFault(AUDIT, OWNER, "STATE")` e `audit_ready=False`, sem retry. `ClockAdapter.poll` exige tupla de slots NÃO vazia (owner:1510-1530): não há poll vazio. Usar `pump.run_until` diretamente exigiria rever reentrada e posse. Fica sem API nova e sem prova nativa.

## 5. Bind e B4 (normativo)

- `bind()` é chamado uma vez, dentro de `try`. A BaseException é atribuída a `custody.bind_throwable`, só a referência, ainda dentro do `except`. Fora dele:
  - **controle:** `bind_result=CONTROL`, `first_control` e relançamento;
  - **Exception:** `bind_result=FAULT` e BIND_REFUSED.
- Sem atributo novo, sem mudar `__context__`/`__traceback__`, sem serialização, limpeza de frame ou registro global. Controles só por `is`/`is not None`.
- Com loop conhecido, o traceback retido mantém o frame de `_bind_over`.
- `type(x) is not ProactorPump` → `bind_candidate = x`, retido e NÃO fechado, `INVALID_RETURN`, BIND_REFUSED.
- Sucesso: `custody.pump = pump` imediatamente.
- Sem contenção provada: F1, close bloqueado e controle assíncrono entre o retorno e a atribuição. Nunca marcam liberação nem readmitem.

## 6. Auditorias

- Só se o fence refrescado tiver `work_settled_at` não None. A sequência é GATEWAY_ABSENT → `settle(Da)` → BACKENDS_ZERO → `settle(Da)`.
- A primeira recusa interrompe, sem retry.
- `audit_ready=True` só se as duas foram iniciadas. O veredito está no `audit` final.

## 7. Disposição local finita

- Snapshot único dos `record_id` SPAWN/CHILD em SETTLED_RETAINED, em uma passagem: `begin_dispose(CLOSE_HANDLE, id, Dd)` para cada um, depois um único `settle(Dd)`.
- Cada DISPOSE consome `max_records` e `max_disposals`. A primeira OwnershipRefusal encerra a passagem.
- `dispose_attempts` conta os `begin_dispose` aceitos. `closed_handles` conta só DISPOSE desses ids com `protocol is ProtocolState.SUCCEEDED` e alvo em RELEASED_LOCAL, no snapshot do relatório.
- TERMINATE e REMOVE não são autorizados; processos OPEN ficam retidos.

## 8. Falhas, precedência e um fault por passo (HR2.3)

| Origem | Tratamento |
|---|---|
| OwnershipRefusal em 2 / HostRefusal em 3 / BridgeRefusal em 4 | OWNER_/HOST_/BRIDGE_REFUSED; depois close (pump vazio) e relatório |
| BridgeRefusal em 5 | RUN_REFUSED, mais `reactor_refusal`; SEGUE 6–12 |
| OwnershipRefusal em 6–10 | fault do passo; pula o que depende dele; faz 11 e 12 |
| PumpFault / retorno não bool exato em 11 | FAULT / INVALID_RETURN |
| outra Exception comum em qualquer passo | (BOUNDARY, "BOUNDARY") |
| controle | §9 |

- `faults` guarda no máximo UM HostFault por HostRunStep: o PRIMEIRO, em ordem de ocorrência. Os seguintes do mesmo passo são descartados. O teto é `len(HostRunStep)`.
- `first_control` é separado e nunca substituído.
- Precedência de `stage`: CONTROL > recusa de custódia/input/bind/construção/run > CLEANUP_FAULT (qualquer fault em passo ≥ 6, inclusive REPORT; `pump_close` fora de RETURNED_TRUE/RETURNED_FALSE; ou `report_complete=False`) > RUN_DONE.
- RUN_DONE só acontece sem nenhum fault e com `report_complete=True`.

## 9. Montagem protegida do relatório (HR2.1, HR2.3)

O relatório usa exatamente três leituras puras, cada uma uma única vez e num guard próprio:
- `owner.audit()`: o `fence` do relatório é `audit.fence`, que é None se ainda não selado. Essa chamada não consulta relógio nem muda estado (owner:1378-1391).
- `owner.custody()`.
- `bridge.status()`.

`seal()` NUNCA é chamado na montagem nem no fallback.

- Uma leitura que falha com Exception deixa o campo None, `report_complete=False` e um `HostFault(REPORT, BOUNDARY, "BOUNDARY")`, se ainda não houver fault de REPORT.
- Um controle durante a montagem:
  - se já existe `first_control`, é descartado e a montagem segue;
  - senão vira `first_control` e a montagem continua com as leituras restantes.
- Fluxo com controle: grava `custody.report` e relança `first_control` fora de `except`, com identidade e `__context__` preservados. Depois do controle fica vedado qualquer efeito: `begin_audit`, `settle`, `begin_dispose`, `pump.close`, `seal` ou leitura de relógio. Continuam permitidas SÓ as três leituras puras protegidas acima, `owner.audit()`, `owner.custody()` e `bridge.status()`, que não iniciam auditoria nem consultam relógio.
- **Domínios exatos do relatório** (identidades capturadas uma vez em §3):

  | Campo | Domínio |
  |---|---|
  | `bridge_status` | `type(x) is BridgeStatus` |
  | `audit` | `type(x) is AuditReport` |
  | `fence` | `audit.fence`, com `type(x) is WorkFence`, ou None |
  | `custody_view` | `type(x) is CustodyView` |
  | `done_outcome` | `type(result) is BridgeRunResult`, depois `type(result.done) is Done` (antes de ler `outcome`), depois `type(result.done.outcome) is Outcome`; ou None |

  Todos são snapshots FINAIS, lidos uma vez na montagem. Um valor de tipo ou rótulo fora do domínio vira campo None, `report_complete=False` e o primeiro `HostFault(REPORT, BOUNDARY, "BOUNDARY")`; nunca RUN_DONE. Sem getters novos, inspeção de runtime privado, loader ou API.
- **Ausência legítima (HR4.1):** se o objeto anterior não existe, o campo é None sem leitura e sem fault: owner não criado → nada de audit nem custody; ponte ausente → nada de status; run sem retorno → `done_outcome` None; owner não selado → `audit.fence` None aceito. Só a API de um objeto EXISTENTE que devolve tipo errado (ou None onde o domínio não permite) gera fault de REPORT. Recusas de bind e input não ganham fault extra.

### 9.1 Seam única `_collect_snapshots` (HR4.3)

É a única função privada da montagem. Não é motor, porta nem fábrica.
- `run_host` a chama exatamente uma vez por saída. Os leitores são os métodos ligados `owner.audit`, `owner.custody` e `bridge.status`, ou None quando o objeto não existe. `domains` recebe as identidades capturadas em §3, na ordem AuditReport, WorkFence, CustodyView, BridgeStatus. `first_control` recebe o atual.
- O oráculo H14 chama a MESMA função, carregada do módulo, com leitores sintéticos puros e classes sintéticas próprias. Não implementa guard no teste nem faz monkeypatch do produto.

Semântica, nesta ordem fixa: audit, custody, status.

1. Leitor None → campo None, sem chamada e sem fault.
2. Senão chama o leitor uma vez, dentro de `try`:
   - Exception → campo None, `complete=False`, `report_fault=True`;
   - BaseException que não é Exception → campo None, `complete=False`; vira `first_control` só se este era None, senão é descartado. Não há fault de REPORT; o controle continua sendo o primeiro.
   - retorno com `type(x) is not` o domínio → campo None, `complete=False`, `report_fault=True`.
3. `fence`:
   - None se `audit` é None;
   - senão é `audit.fence`, que pode ser None (não selado);
   - um valor que não é None e não é `type(x) is WorkFence` → fence None, `complete=False`, `report_fault=True`.
4. Devolve `_Snapshots` e nunca levanta Exception. Não chama `seal`, relógio, pump nem SDK, e não lê `vars` nem atributos privados.

Uso pelo `run_host`:
- `report_fault=True` → o primeiro `HostFault(REPORT, BOUNDARY, "BOUNDARY")`, se ainda não existe fault de REPORT;
- `report_complete = complete`;
- se `_Snapshots.first_control` é um controle NOVO (o anterior era None): stage CONTROL, grava `custody.first_control`, grava `custody.report` e relança fora de `except`.

Um controle que interrompa a própria seam fora do seu `try` (assíncrono) não tem garantia.
- Não se promete imunidade física a controle assíncrono nem a falta de memória.

## 10. Quatro conclusões distintas

1. Protocolo: `done_outcome is Outcome.COMPLETE_CANDIDATE`.
2. Escopo do owner: `audit.quiet_scoped` final.
3. Disposição local: `closed_handles` e `pump_close`.
4. Liberação física: não existe campo e nunca é afirmada.

UNKNOWN nunca vira sucesso, e fatos tardios ficam no owner. A custódia é retida pelo chamador até uma recuperação admitida (gate nativo); descartá-la viola B4 e PORT §9. O chamador operacional ainda não existe.

## 11. Oráculos fake-only (antes de código)

Usam os reais owner/ponte/reator/pump com `_bind_over` sobre o FakeLoop e o ProcScript congelados. Sem mutar produto e sem chamar o wrapper nativo.

- **H1 positivo:** COMPLETE_CANDIDATE, `quiet_scoped=True`, `closed_handles >= 15`, RETURNED_TRUE, `faults == ()`, `report_complete=True`, RUN_DONE.
- **H2–H4 bind:** Exception, controle (fábrica e ident) e close Exception/C2 retidos por identidade; `bind_result` exato; witness congelado no frame de `_bind_over`.
- **H5:** retorno inválido → INVALID_RETURN, candidato retido, zero owner, zero close.
- **H6 entrada:** inputs/janelas/namespaces/tipos errados → REFUSED_INPUT, custódia claimed, zero bind. Segunda chamada → REFUSED_CUSTODY com todos os campos idênticos (`is`).
- **H6b custódia corrompida:** `claimed=1`, `claimed=False` com `pump` pré-preenchido, e subclasse de HostCustody → REFUSED_CUSTODY, todos os campos inalterados, zero bind.
- **H7 construção:** policy inválida → HOST_REFUSED, categoria do domínio; budget inválido → BRIDGE_REFUSED; ambos com RETURNED_TRUE.
- **H8:** spawn `raise_before` → RUN_REFUSED, 6–12 executados, RETURNED_FALSE.
- **H9 fence tardio:** o EOF do gateway chega depois do Done; fence do passo 6 não assentado; refresh do passo 8 assentado; auditorias executadas.
- **H10:** EOF pausado no cap → `quiet_scoped=False`, sem TERMINATE, RETURNED_FALSE.
- **H11:** relógio parado → STATE honesto, sem retry.
- **H12 close:** `loop.close` com Exception → RETURNED_FALSE; ident trocado → FAULT; controle → CONTROL relançado.
- **H13 controle ANTES do seal (durante run):** o mesmo objeto; nenhuma chamada `time()` do FakeLoop depois do controle; nenhum seal; `audit.fence is None`; `custody.report` montado.
- **H14 seam `_collect_snapshots`:** chamada direta, com leitores e domínios sintéticos puros, porque APIs reais e o fake SDK não disparam essas falhas:
  - leitor None → campo None e `complete=True`;
  - Exception → `report_fault` e `complete=False`;
  - tipo errado → `report_fault`;
  - `fence` None aceito; `fence` de tipo errado → `report_fault`;
  - controle com `first_control` None → vira o primeiro (`is`), e os leitores seguintes ainda são chamados;
  - controle com `first_control` existente → o existente é preservado (`is`), sem `__bool__`.

  No `run_host` (fake SDK), um owner/ponte reais ausentes por recusa anterior não geram fault de REPORT.
- **H15 capacidade:** `max_disposals` pequeno → CAPACITY encerra; contagens exatas.
- **H16 AST:** sem imports nativos, sem `bind_proactor_pump`, sem `while`, sem TERMINATE/REMOVE; sem `seal` em `_collect_snapshots`; `run_host` só chama `audit`/`custody`/`status` através da seam; ordem settle → seal → audit → dispose → close.

## 12. Aceite nativo separado e itens em aberto

NOT_PREPARED:
- bind real (N8, N11, N15);
- `CliPlan`, receitas, loader e pins;
- readmissão da imagem e do PG16;
- contenção do bind;
- granularidade do relógio;
- EOF, saída natural e quiescência físicos.

A saída natural 0 do T5 DEVERÁ ser provada no futuro main/driver dentro do container (`deploy/oracle9_w1_driver.py:14-18`); isso não foi medido neste lote e T5 permanece OPEN. Um kill só pode provar limpeza, separadamente, e apenas quando efetivamente observado; pedir o kill não prova nada.

Itens em aberto:
1. Espera sem trabalho antes das auditorias.
2. TERMINATE/REMOVE: autoridade mais plano.
3. Definição de "recuperação admitida" e destino da custódia.

N1–N16, T5, B1, B2, D-090 gate2, C1, D119, TLS, ingressos e produção seguem OPEN. Gateway indisponível.

Política Senff: desenho e código derivados por IA exigem revisão humana e de segurança antes do merge.
