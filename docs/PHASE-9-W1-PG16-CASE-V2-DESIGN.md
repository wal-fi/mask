# Fase 9 W1 — PG16 caller protegido de caso V2 (A) e proveniência V2 (B) — design

Status atual: Parte A implementada e revista somente com fakes;72/72
próprios e708/708 relacionados passaram. Parte B permanece somente desenho.
Fonte0fac3c7b/teste72dde65c e gates em CASE-V2-VALIDATION. Não há consumidor
operacional, entrada/loader/batch/publicação ou atestado nativo novo.
As seções de desenho e71 cenários abaixo preservam o contrato anterior à
implementação; a regressão72 consta na validação e complementa a matriz.

Revisão do desenho pelo ROOT (histórico): Parte A fechada para escrever os
testes e medir o RED, sob delegação. Os71 casos eram uma matriz prevista;
a medição posterior é registrada na validação. A Parte B é desenho
prospectivo e exige revisão própria antes
de código; isso inclui a forma exata do ExpectedV2 e a cadeia externa de
confiança. Clarificações editoriais do revisor abaixo preservam a API e
as garantias, sem mudar código ou testes aceitos.

Escrito pelo Claude2 na sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`
(`claude-opus-5-5`, esforço `medium`), sob a delegação geral vigente
(AGENTS.md, "Delegação vigente — 2026-10-20"). A API mínima enraizada
(`allocate` + `prepare(slot, sources, owner, case)` + `run(slot, artifacts)`)
foi aceita como decisão sob essa delegação e após revisão do ROOT. Não é
aprovação individual. O ROOT revisa o contrato e congela o RED dos testes de
A antes de qualquer implementação.

Este documento só cita números do ROOT. Para o lifecycle `7bbf734c…`, a
LIFECYCLE-V2-VALIDATION registra 44/44 testes próprios e 636/636
relacionados. Nada novo foi medido aqui.

**Base lida.**
- Lote V2:
  - `docs/poc/pg16_shell_native_control_lifecycle_v2.py` inteiro
    (`7bbf734c…`, 423 linhas);
  - `PHASE-9-W1-PG16-LIFECYCLE-V2-VALIDATION.md` inteiro;
  - §1–3 de `PHASE-9-W1-PG16-LIFECYCLE-V2-DESIGN.md`.
- Antes, nesta sessão:
  - runner `b4198fe1…` inteiro;
  - host `dfcc4ed6…` inteiro;
  - backend `10c9058f…`, linhas 355–916;
  - entry consumida inteira;
  - core verify `b3755d49…` inteiro;
  - collector `1972ec74…`, linhas 1–60;
  - testes do adapter.

**Limites permanentes.**
- Source10, state16, helper `bb1f1984…`, teste `ad0742c0…`, lifecycle
  `7bbf734c…` e teste `40279844…` continuam congelados.
- A tentativa 3f12dc584c29 continua FAILED_ONLY_OPERATOR_ABORT. Não é relida,
  reutilizada nem reclassificada.
- Native3s NOT_MEASURED, entry_gate NOT_EVALUATED e identidade Nov2
  LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED.
- Gateway, B1, B2, D090gate2, C1, SQL e produção abertos.

**Regra de comparação em todo o documento:** primeiro o tipo exato, depois o
valor. Chaves de mapa precisam ser `str` builtin, verificadas por iteração do
`dict` exato antes de qualquer lookup, hash ou igualdade. Nunca se itera um
iterável estrangeiro; só se iteram `dict`, `list`, `tuple` e `frozenset`
exatos já verificados.

---

# Parte A — caller protegido de um caso

## A1. Escopo e não-escopo

- **Módulo futuro:** `docs/poc/pg16_shell_native_control_case_v2.py`.
- **Teste futuro:** `tests/test_pg16_shell_native_control_case_v2.py`.
- O teste vem primeiro; o ROOT mede e congela seu RED. O módulo só é
  implementado depois desse gate, pelo Claude2.

**O que A faz.** Recebe um owner e um case **já construídos e registrados por
um produtor confiável**. Então:

1. captura as referências originais num slot fixo;
2. executa uma vez o lifecycle V2 aceito;
3. prova o fechamento;
4. chama o `_finish` legado capturado;
5. faz checagens novas depois do finish.

**O que A não faz.** Não cria diretório, raiz, nonce, comando, launcher,
`invocation.json`, owner ou factory. Não lê fonte, não carrega namespace, não
publica e não tem loop de estacionamento. Não copia nenhuma parte de `_case`
e não tem fallback `_case`/`_contain`.

**Obrigações de prova do produtor** (fora de A; citadas, não medidas aqui):

- **Pureza dos construtores.** `Owner.__init__` do backend é puro, conforme o
  comentário "Pure: no validation that can lose ownership, no DLL, no handle"
  no backend `10c9058f…`. A construção pura do `NestedJobOwner` é afirmada
  pelo teste aceito do adapter, `test_import_and_construction_are_pure`.
- **Registro.** O produtor registra o owner na `_LIVE` ORIGINAL **antes** de
  `prepare`, e ele mesmo guarda uma referência forte a esse **objeto lista**,
  capturado logo depois do exec do runner. Não basta o nome mutável
  `legacy["_LIVE"]`. O slot só prende a lista depois que `prepare` a valida;
  antes disso, ou se ela for recusada, a responsabilidade é do produtor.
- **Retenção do owner.** O produtor **mantém sua própria referência** ao
  owner até ter observado que `prepare` o prendeu (`slot.owner is owner`).
  Isso inclui uma interrupção que chegue antes da primeira atribuição dentro
  de `prepare`. Pré-alocar o slot estreita essa janela, mas não torna
  atômicas as atribuições Python.
- **Artifacts e case.** O produtor persiste `case-N/invocation.json` em
  `artifacts` antes de `run` e monta o case no formato exato de §A4.

## A2. Fontes: namespaces reais, não cópias

`sources` deve ser uma `tuple` exata de comprimento 3:
`(legacy, lifecycle, reconcile)`.

| Elemento | Deve ser | Prova de identidade exigida |
|---|---|---|
| `legacy` | os globais reais do runner `b4198fe1…` | `type(legacy) is dict`; chaves `str` exatas; `legacy["_finish"].__globals__ is legacy`, e o mesmo para todo hook legado capturado (§A5) |
| `lifecycle` | os globais reais do módulo `7bbf734c…` | `lifecycle["context"].__globals__ is lifecycle`; `lifecycle["lifecycle"].__globals__ is lifecycle`; `ContextRefused` e `_Context` com `type(x) is type` |
| `reconcile` | o helper `bb1f1984…` ou um espião de teste | `type(reconcile) is FunctionType`; capturado por identidade |

- **Host:** não é parâmetro. Vem de `case["host"]`, com
  `host["_supervise"].__globals__ is host` e `host["_attempt"].__globals__ is host`.
- **`loaded`:** não é parâmetro. `case["error"]` já é a `Win32Error` que o
  produtor obteve do `loaded` original.
- **Cópias de `runpy`:** `runpy.run_path` devolve uma **cópia** dos globais.
  Testes e produtor usam `função.__globals__`; um mapping copiado falha em
  `__globals__ is legacy` e é recusado.
- **Alcance:** isso é identidade e forma, não autenticidade dos bytes, que
  continua sendo precondição de um loader futuro.

**Ordem de captura na entry consumida** (corrige a proposta anterior):

1. retém o namespace em `KEEP` **antes** do exec;
2. captura a `_LIVE` original **depois** do exec e antes do invoke
   (`_advance` → `_capture`).

O coordenador futuro segue essa ordem. A recebe um `legacy` já executado e
não reimplementa isso.

## A3. KEEP, slot pré-alocado e precondição do slot

- O módulo define `KEEP = []`: referências fortes, nunca removidas.
- `allocate()` é pura:
  1. cria um `_Slot` com os campos fixos abaixo;
  2. faz `KEEP.append(slot)`;
  3. devolve o slot.
- O coordenador futuro captura `KEEP` e o slot **antes** de construir o
  owner.

**Campos de `_Slot`** (lista fechada; todos `None`, salvo indicação):

| Grupo | Campos |
|---|---|
| Estado | `state` = `"EMPTY"`; `outcome` |
| Referências cruas | `owner`, `case`, `sources` (a tupla crua, nunca desempacotada antes da validação) |
| Fontes extraídas | `legacy`, `lifecycle`, `reconcile` |
| Do case | `host`, `registry`, `clock`, `facts`, `retained`, `ledger` |
| Capturas | `refs` (§A5); `meta` (§A4.7); `ctx` |
| Execução | `run_reserved` = `False`; `tree`; `failure`; `control`; `record`; `artifacts` |

**Precondição de slot válido**, verificada pelo tipo antes de qualquer
escrita:

- `type(slot) is _Slot`;
- `type(slot.state) is str` e `slot.state == "EMPTY"`;
- `slot.owner is None` e `slot.outcome is None`;
- `slot.run_reserved is False` exatamente.

Se a precondição falhar, `prepare` devolve `"REFUSED_SLOT"` e não escreve
nada. Nesse caso o produtor continua responsável pelo owner e não pode tratar
o retorno como "sem recursos".

O slot e `KEEP` sobrevivem a entradas malformadas e a controles. Nenhum
retorno é permissão implícita de saída.

## A4. `prepare(slot, sources, owner, case)`

1. **Precondição de slot** (§A3). Ela roda fora da proteção porque, se
   falhar, nada foi escrito.
2. **Corpo protegido único.** Logo depois da precondição começa uma única
   proteção. Todo o restante de `prepare`, inclusive a captura crua, roda
   dentro dela.
   - `Exception` vira `PREPARE_REFUSED` e grava `failure`, se ainda for
     `None`.
   - `BaseException` (controle) grava `slot.control`, se ainda for `None`;
     marca `outcome = "INTERRUPTED"`, se ainda for `None`; e relança o mesmo
     objeto.
   - O handler é o mesmo para todas as fases do corpo. Não existe fase fora
     dele.
3. **Primeiras instruções do corpo: captura crua, sem desempacotar nada.**
   - `slot.owner = owner`;
   - `slot.case = case`;
   - `slot.sources = sources`;
   - `slot.state = "PREPARING"`.

   Depois, ainda no mesmo corpo, vêm as checagens de tipo e a extração.
   - **Fontes:** `type(sources) is tuple and len(sources) == 3`. Só então
     a extração por índice `sources[0..2]`. Uma `list` ou outro iterável não
     é iterado; é recusado.

   **Limite.** Uma interrupção antes de entrar na proteção, ou antes da
   primeira atribuição, deixa o slot sem o owner. Por isso o produtor
   continua segurando o owner até observar `slot.owner is owner`. Não há
   garantia absoluta de atomicidade nem contra falta de memória.
4. **Lista de registro.** `registry = legacy["_LIVE"]` precisa ser `list`
   exata contendo `owner` por identidade. Se não for:
   - a lista **não é tocada** (nenhum append nem remoção) e o resultado é
     `PREPARE_REFUSED`;
   - o owner pré-existente continua retido pelo slot e pela lista em que o
     produtor o colocou;
   - `PREPARE_REFUSED` nunca significa "sem recursos": a chamada não teve
     efeito, mas o owner existe com estado desconhecido;
   - uma lista malformada ou estranha **não** pode ser declarada enraizada por
     este slot. Quem responde pela lista original continua sendo o produtor
     (§A1).
5. **Owner.**
   - `type(owner.state) is str` e o estado é exatamente `"NEW"`.
   - `type(owner.ledger) is dict`, com chaves `str` e vazio.
   - `close_inner` resolvido pela MRO é `FunctionType` se e só se o nome é
     `LAST_CLOSE`.
6. **Case.** Primeiro `_str_keys`. Depois exatamente as 20 chaves abaixo,
   cada uma comparada pelo tipo antes do valor:

| Chave | Valor exigido |
|---|---|
| `name` | `str` em CASES |
| `directory` | `type(d) is type(pathlib.Path())`; `str(d)` com no máximo 512 caracteres; `d.name == "case-N"` |
| `prefix` | `str` exatamente `"case-N/"`, com N em 1..3 e `CASES[N-1] == name` |
| `host` | `dict` exato (§A2) |
| `error` | `type(error) is type` e subclasse de `Exception` |
| `read_limit` | `int` builtin exato **4096**, o `MAX_READ` do backend congelado `10c9058f…` (ver nota) |
| `audit_limit` | `int` builtin exato **512**, o `AUDIT_LIMIT` do adapter `eaebedd6…` e o `AUDIT_LIMIT`/limits do core verify |
| `facts` | `dict` exato com as 10 chaves de `_new_facts`, valores iniciais exatos (`None`/`False`/`0`) e `retained` um `bytearray` vazio |
| `ready`, `inner_closed`, `contained`, `recorded` | exatamente `False` |
| `ready_turns` | `int` 0 |
| `snapshot`, `seconds` | `None` |
| `clock` | objeto cujo `now` é o par vinculado (`__self__`, `__func__`) da sua classe |
| `start`, `since` | `float` exatos, finitos (`math.isfinite`), com `since == start` |
| `lifecycle_reserved`, `reconcile_reserved` | exatamente `False` |

   **Origem dos valores.** O ROOT confirmou as constantes por leitura
   independente das fontes congeladas: `MAX_READ = 4096` na linha 57 do
   backend `10c9058f…` e `AUDIT_LIMIT = 512` na linha 30 do adapter
   `eaebedd6…`. É confirmação de constante feita pelo revisor, não uma medição
   nativa nem de teste. Não há relaxamento.
7. **Snapshot imutável `slot.meta`:** a tupla de escalares exatos
   `(name, N, prefix, str(directory), read_limit, audit_limit, start)` mais a
   tupla ordenada das 20 chaves.
   - Não é deep-copy de objetos arbitrários.
   - As estruturas originais (`case`, `facts`, `retained`, `ledger`) são
     mutadas legitimamente pelo lifecycle e pelo finish. Ficam separadas,
     guardadas por identidade.
8. **Captura transitiva** em `slot.refs` (§A5).
9. **Sucesso:**
   - grava `legacy`, `lifecycle`, `reconcile`, `registry`, `host`, `clock`,
     `facts`, `retained` e `ledger`;
   - `state = "PREPARED"`;
   - devolve `"PREPARED"`;
   - `outcome` **continua `None`**.

## A5. Referências transitivas capturadas

Capturadas por identidade e reconferidas antes do contexto, logo depois do
contexto, depois do lifecycle, antes do finish e depois do finish.

| Origem | Nomes | Regra |
|---|---|---|
| `legacy` | `_finish`, `_capture`, `_verdict`, `_persist`, `_step`, `_check`, `_fields`, `_framing`, `_int`, `_state` | `FunctionType` com `__globals__ is legacy` |
| `legacy` | `RunError` (classe); `CODES` e `REJECTIONS` (`frozenset`); `TERMINATE_NAMES` e `CASE_KEYS` (`tuple`); `NORMAL_LINE` e `READY_LINE` (`str`); `_LIVE` | identidade e tipo exato |
| `host` | `_attempt`, `_supervise` | `FunctionType` com `__globals__ is host` |
| `host` | `write_new`, `encoded`, `_monotonic` | `FunctionType`; só identidade, porque produtor ou teste podem tê-los substituído em memória |
| `host` | `DEADLINE_SECONDS` | `float` exato, identidade |
| `case` | `facts`, `host`, `clock`, `error`, `name` | identidade |
| `facts` | `retained` | identidade |
| clock | `now` | par (`__self__`, `__func__`) |
| owner | `ledger` | identidade com o dict original; mutação in loco permitida |
| `lifecycle` | `context`, `lifecycle`, `ContextRefused`, `_Context` | identidade |

**Presença na lista** (prova própria do caller, por fase):

| Fase | Condição |
|---|---|
| antes do contexto e antes do lifecycle | `legacy["_LIVE"] is slot.registry` e owner **presente** por identidade |
| depois do lifecycle, antes e depois do finish | `legacy["_LIVE"] is slot.registry` e owner **ausente** |

O caller **não** chama `lifecycle._intact`. Essa função supõe o owner ainda
registrado e por isso não serve depois do release.

Este é o mesmo limite confiável do lifecycle: detecta substituição visível
antes e depois das chamadas. Não defende código arbitrário nem mutação
maliciosa no meio de um helper.

## A6. `run(slot, artifacts)`

1. `type(slot) is not _Slot` → devolve `"REFUSED_SLOT"`. É só retorno; nada
   é gravado.
2. `slot.run_reserved is True` → devolve `"RETAINED_REUSED"`. Só retorno: não
   substitui `outcome`, `failure`, `control` nem `record`.
3. `slot.run_reserved is not False` (qualquer valor que não seja exatamente
   `False`), ou `type(slot.state) is not str`, ou `slot.state != "PREPARED"` →
   devolve `"RETAINED_NOT_PREPARED"`. Só retorno, sem reserva.
4. **Reserva:** `slot.run_reserved = True` antes de qualquer callback. Daqui
   em diante não há retry nem segundo close.
5. **Artifacts:** `dict` exato; chaves `str` exatas e no `WHITELIST` do core
   verify; valores `bytes` exatos dentro de `FILE_CAPS`; no máximo 11
   entradas.
   - Precisa conter `prefix + "invocation.json"`.
   - Não pode conter outro arquivo deste prefixo.
   - Snapshot: tupla de `(chave, objeto bytes)`.
   - Falha → `RETAINED_ARTIFACTS`.
6. **Guarda pré-contexto** (§A5 com owner presente, mais `meta`) →
   `RETAINED_DRIFT`.
7. **Contexto:** `ctx = context(owner, case, legacy, reconcile)`, usando o
   `context` capturado.

| Exceção | Rótulo |
|---|---|
| tipo exato do `ContextRefused` capturado | `RETAINED_CONTEXT_REFUSED` |
| tipo exato do `RunError` capturado, com args `("CONTROL_HELD",)` | `RETAINED_CONTEXT_HELD` |
| outra `Exception` | `RETAINED_INTERNAL` |
| controle | `INTERRUPTED`, relançado |

8. **Vínculo do ctx, logo depois do retorno e antes de delegar ao lifecycle.**
   - A primeira instrução após o retorno normal de `context` é
     `slot.ctx = ctx`, **antes** de qualquer checagem de tipo, vínculo ou
     atributo.
   - Um objeto inválido, estranho ou parcialmente inicializado fica assim
     fortemente enraizado no slot e não se perde numa variável local.
   - Um controle ou exceção durante a inspeção passa pelo mesmo handler
     travado; o ctx cru continua em `slot.ctx`.
   - `state` só avança para `"CONTEXT"` depois que a validação passa.

   A validação, sobre `slot.ctx`, exige:
   - `type(ctx) is` o `_Context` capturado;
   - `ctx.owner is slot.owner`, `ctx.case is slot.case`,
     `ctx.legacy is slot.legacy` e `ctx.reconcile is slot.reconcile`;
   - `ctx.facts is slot.facts`, `ctx.retained is slot.retained`,
     `ctx.registry is slot.registry` e `ctx.ledger is slot.ledger`;
   - `ctx.clock is slot.clock` e `ctx.host is slot.host`;
   - guarda §A5 com owner presente.

   - Um campo do ctx sem atribuição (`AttributeError`) ou qualquer
     divergência dá `RETAINED_CONTEXT_INVALID`, **sem chamar o lifecycle**.
     O ctx cru fica retido em `slot.ctx`.
   - Se passar, `state = "CONTEXT"`.
9. **Lifecycle:** `state = "LIFECYCLE"`, `result = lifecycle(ctx)`.

| Desfecho | Rótulo |
|---|---|
| `ctx.held_error` (identidade) | `RETAINED_INTEGRITY` |
| `RunError` capturado com CONTROL_HELD, outra instância | `RETAINED_HELD` (hold legítimo do legado) |
| outra `Exception` | `RETAINED_INTERNAL` |
| controle | `INTERRUPTED`, relançado |
| retorno que não é exatamente `None` | `RETAINED_PROOF_FAILED` |

10. **Prova de fechamento**, só depois de um retorno exatamente `None`.
    Primeiro confere as identidades de §A5: deriva de referências devolve
    `RETAINED_DRIFT`, como na matriz45–58. Depois confere os itens restantes;
    prova ausente ou inválida devolve `RETAINED_PROOF_FAILED`, sem close nem
    release. Owner presente quando deveria estar ausente é falha de prova,
    não troca de identidade da lista.
    - Guarda §A5 com owner **ausente** da lista original.
    - `case["lifecycle_reserved"] is True`.
    - `type(case["reconcile_reserved"]) is bool`.
    - `_state(owner)` capturado devolve `"CLOSED"` (`str` exata).
    - `owner.ledger is slot.ledger` e `len(slot.ledger) == 0`.
    - `facts["held"] is None` e `facts["retained"] is slot.retained`.
    - Vínculos do ctx do passo 8 ainda idênticos.

    Se passar, `state = "RELEASED_PROVEN"`.
11. **Trava do TREE antes do finish:**
    `slot.tree = case["reconcile_reserved"]`, já `bool` exato.
12. **Guarda pré-finish** (§A5 completa, owner ausente) → `RETAINED_DRIFT`.
13. **Finish:** `state = "FINISH"`, `record = _finish(owner, case, artifacts)`
    pelo `_finish` capturado.
    - `Exception` → `RETAINED_FINISH_FAILED`.
    - Controle → `INTERRUPTED`, relançado.
    - Nenhum `_contain`, `_release`, `_held` ou close de fallback.
14. **Checagens novas pós-finish.** Falha → `RETAINED_POST_FINISH_INVALID`.
    - §A5 intacta, owner ausente, ledger o mesmo e vazio, estado CLOSED.
    - `case["lifecycle_reserved"] is True`.
    - `type(case["reconcile_reserved"]) is bool` e o valor é `slot.tree`.
    - `facts["held"] is None` e `meta` igual.
    - Artifacts antigos inalterados por identidade. Chaves novas
      exatamente `supervision.json` e `local-stdout.bin`, mais
      `snapshot.json` e `audit.json` só em LAST_CLOSE, todas `bytes` dentro
      de `FILE_CAPS`.
    - Record:
      - `dict` exato com chaves `str` exatas iguais a `CASE_KEYS` e
        `case == name`;
      - outcome `str` em APPROVED/REJECTED, com `APPROVED` se e só se
        `rejection is None`;
      - `ready is None` só em NORMAL;
      - os 4 campos de LAST_CLOSE são `None` fora de LAST_CLOSE.
    - **TREE:** se `slot.tree is True`, o outcome é `REJECTED` e a rejeição
      está em `{"TREE_UNPROVEN"}` para NORMAL/TERMINATE ou em
      `{"AUDIT_INVALID", "FAILED_LAST_CLOSE", "TREE_UNPROVEN"}` para
      LAST_CLOSE. O inverso não é exigido: uma rejeição TREE sem reconcile é
      possível, porque o supervisor pode ver TREE transitório e concluir sem
      o helper.
    - A precedência exata continua sendo recalculada só pelo core verify
      congelado, que é obrigatório depois.
15. Se tudo passar: `slot.record = record`, `state = "READY_FOR_VALIDATION"`.

Qualquer falha comum na própria lógica de `run` dá `RETAINED_INTERNAL`. Um
controle é travado e relançado.

## A7. Estados, resultado primário e retornos de reentrada

- **`state`** só avança:
  `EMPTY → PREPARING → PREPARED → RUN_RESERVED → CONTEXT → LIFECYCLE →
  RELEASED_PROVEN → FINISH → READY_FOR_VALIDATION`. Pode também parar num
  estado terminal igual ao rótulo primário.
- **`outcome` (resultado primário):**
  - começa `None`;
  - um `prepare` bem-sucedido **não** o define;
  - o primeiro desfecho terminal de `prepare` ou `run` o grava **uma única
    vez**;
  - `failure` e `control` guardam só o primeiro valor; `record` só é gravado
    em `READY_FOR_VALIDATION`.
  - A primeira exceção comum é a entregue ao caller nessa fronteira. O
    `_finish` legado sanitiza erros de escrita por `_persist`/`_step`: um
    OSError interno vira RunError(CONTROL_PERSISTENCE) sem cadeia. O caller
    retém a identidade desse erro entregue, sem recuperar o erro suprimido.
- **Retornos de reentrada:** `REFUSED_SLOT`, `RETAINED_REUSED` e
  `RETAINED_NOT_PREPARED` são devolvidos e **nunca** substituem `outcome`,
  `failure`, `control` ou `record`.

**Rótulos terminais primários:**

| Rótulo | Significado |
|---|---|
| `PREPARE_REFUSED` | owner pré-existente retido; não é "sem recursos" |
| `RETAINED_ARTIFACTS`, `RETAINED_DRIFT` | parou antes do lifecycle ou antes do finish |
| `RETAINED_CONTEXT_REFUSED`, `RETAINED_CONTEXT_HELD`, `RETAINED_CONTEXT_INVALID` | o contexto falhou ou é inválido; o lifecycle não foi chamado |
| `RETAINED_INTEGRITY`, `RETAINED_HELD`, `RETAINED_INTERNAL`, `RETAINED_PROOF_FAILED` | resultado do lifecycle não provado |
| `RETAINED_FINISH_FAILED`, `RETAINED_POST_FINISH_INVALID` | owner provado, mas o record não é confiável |
| `INTERRUPTED` | controle travado em `slot.control` e relançado como o mesmo objeto |
| `READY_FOR_VALIDATION` | o record existe para validação posterior |

**Nenhum rótulo autoriza a saída do controlador ou a publicação.**
`READY_FOR_VALIDATION` não é autorização de publicar. O tempo de vida
estacionado é do coordenador futuro, separado.

## A8. Testes de A (matriz finita, RED antes do módulo)

O novo teste reutiliza, via `runpy`, as funções simples do teste congelado
`40279844…`: `lab_kernel_class`, `owner_for`, `case_for`, `published` e
`verified`. Também copia localmente a montagem do fixture `lab`, sem alterar
aquele arquivo.

Regras do harness:
- `Owner` e `NestedJobOwner` reais com kernels falsos;
- `write_new`, `_monotonic` e `_sleep` em memória;
- WinDLL, Popen, `os.system`, `Thread.start` e `time.sleep` proibidos;
- `legacy = run.__globals__` e `lifecycle = lifecycle.__globals__`;
- Todo slot válido alocado permanece por identidade no `KEEP`. Um argumento
  não-slot não é acrescentado nem recebe escrita.
- Quando a captura de `registry` ocorreu, confere-se sua identidade com a
  lista original. Recusas anteriores não fingem que um campo ainda `None`
  contém essa lista: confere-se a referência original retida pelo produtor,
  sem mutação ou append, e a posse do owner pelo slot quando já capturado.
- O produtor mantém o owner e a lista originais durante a janela anterior
  à captura, inclusive nos testes de recusa. Owner ausente por uma entrada
  malformada não é reinserido para satisfazer uma asserção.

| # | Grupo | Casos | Expectativa |
|---|---|---|---|
| 1 | Lote | NORMAL, TERMINATE e LAST_CLOSE via allocate/prepare/run | 3 × READY_FOR_VALIDATION; core verify VERIFIED_APPROVED |
| 2 | TREE NORMAL | TREE quieto | READY, `slot.tree is True`, REJECTED/TREE_UNPROVEN, VERIFIED_REJECTED |
| 3 | TREE LAST_CLOSE | dois aprovados e depois TREE | FAILED_LAST_CLOSE, VERIFIED_REJECTED |
| 4 | Falha precoce | setup falho | READY, REJECTED/LAUNCH_FAILED |
| 5 | Estados | sequência observada; slot em `KEEP` antes do prepare; `outcome` `None` após prepare | exatamente §A7 |
| 6 | Slot inválido | `prepare` em não-slot | REFUSED_SLOT; nenhuma escrita |
| 7 | `sources` lista | objeto com `__iter__` espião | PREPARE_REFUSED; espião nunca chamado; `slot.sources` é o objeto |
| 8 | `sources` curta | tupla com 2 elementos | PREPARE_REFUSED |
| 9 | Prepare duplo | segundo `prepare` | REFUSED_SLOT devolvido; outcome/state/refs do primeiro iguais |
| 10–24 | Case malformado (15) | chave faltando; chave extra; chave não-`str`; `start` int; `start` inf; `since ≠ start`; flag True; `ready` True; facts com chave extra; `retained` não vazio; `read_limit` 4095; `audit_limit` 513; prefixo/nome divergente; LAST_CLOSE com `Owner` simples; estado do owner ≠ NEW | PREPARE_REFUSED; zero chamadas ao kernel; lista intacta; owner retido |
| 25–29 | Fontes malformadas (5) | `legacy` como cópia de `runpy`; `lifecycle` como cópia; host como cópia; owner ausente da `_LIVE`; `_LIVE` que não é lista | PREPARE_REFUSED; lista não tocada; nenhum append |
| 30–35 | Troca depois do prepare (6) | `legacy["_finish"]`, `legacy["_LIVE"]`, `case["facts"]`, `case["host"]`, `lifecycle["context"]`, `owner.ledger` | RETAINED_DRIFT; zero chamadas ao kernel |
| 36–37 | Ctx inválido (2) | `context` instalado antes do prepare via `FunctionType(código, lifecycle)` que devolve um objeto qualquer; `_Context` genuíno construído para **outro** owner registrado | RETAINED_CONTEXT_INVALID; `slot.ctx is` o objeto devolvido (identidade); `slot.state` não é CONTEXT; lifecycle não chamado; zero chamadas ao kernel |
| 38–41 | Injeção controlada no contexto (4) | `_capture_error` devolve `None`; `_build` devolve `None`; `_build` levanta `TypeError`; `_build` levanta `Signal` | CONTEXT_REFUSED; CONTEXT_HELD ×2; INTERRUPTED com o mesmo objeto |
| 42–44 | Retornos falsos (3) | `_flow` vazio; `lifecycle` não-`None` instalado via `FunctionType`; `_release` do lifecycle como no-op | RETAINED_PROOF_FAILED; no terceiro, owner CLOSED ainda na lista e sem segundo close |
| 45–58 | Deriva transitiva antes do finish (14), no callback de reconcile de um TREE quieto | `_verdict`, `_capture`, `_persist`, `_step`, `_check`, `_fields`, `_framing`, `_int`, `REJECTIONS`, `TERMINATE_NAMES`, `write_new`, `encoded`, `DEADLINE_SECONDS`, `_monotonic` | RETAINED_DRIFT antes do finish; sem `supervision.json` |
| 59–61 | Deriva durante o finish (3), via `write_new` falso | troca de `_verdict`; troca de `legacy["_LIVE"]`; `case["reconcile_reserved"]` mudado | RETAINED_POST_FINISH_INVALID |
| 62 | Falha de IO no finish | `write_new` levanta em `supervision.json` | RETAINED_FINISH_FAILED; owner CLOSED e ausente; sem `held.json`; `double_closed == []`; zero chamadas ao kernel depois do lifecycle |
| 63 | Integridade | reconcile forjado (CLOSED + RETAIN) | RETAINED_INTEGRITY; sem `held.json` |
| 64 | Hold legítimo | TREE incerto | RETAINED_HELD; `held.json` legado presente |
| 65–69 | Controle (5) | `now` como property que levanta `Signal` no prepare; `Signal` no setup do kernel; no close do reconcile; no primeiro `now` do finish; no último `write_new` | INTERRUPTED; `slot.control` é o mesmo objeto; relançado; slot em `KEEP` com owner |
| 70 | Execução única | segundo `run` | RETAINED_REUSED devolvido; zero chamadas ao kernel; `outcome`/`record` iguais |
| 71 | Run sem prepare | `run` em slot PREPARE_REFUSED | RETAINED_NOT_PREPARED devolvido; `outcome` continua PREPARE_REFUSED; zero chamadas ao kernel |

Total: 71 casos, sem skip, xfail, supressão ou cast. Se a revisão mudar a
matriz, o total muda junto; ele não é uma meta.

**Alcance dos testes 38–41.** São injeção controlada de falha em seams
específicos do lifecycle, trocados antes do prepare.
- A fase A não é categoricamente inalcançável: erros de forma em `legacy`
  normalmente são pegos pelo caller, mas alocações dentro do `RunError`
  original ou da captura podem falhar sem nenhuma deriva de identidade.
- Esses testes não medem falta de memória real, comportamento nativo ou
  autenticidade.

**Alcance das defesas de coerência do record** (59–61 e o passo 14). Elas não
provam que metadados arbitrários não possam mentir. Um record incoerente sem
deriva não é alcançável com o código congelado, por isso o core verify
continua obrigatório depois.

---

# Parte B — proveniência V2 (somente desenho; nada implementado)

**Revisão posterior, 2026-11-05:** o contrato prospectivo para o próximo RED
está em [PROVENANCE-V2-CONTRACT-REVIEW](PHASE-9-W1-PG16-PROVENANCE-V2-CONTRACT-REVIEW.md).
Essa revisão substitui a forma de ExpectedV2, a API, os motivos, a ordem de
verificação e a matriz preliminares de B3/B4/B6 abaixo. Schemas dos artefatos
e papéis/caminhos de B2 permanecem. Texto abaixo preservado como rascunho de
origem, sem alegação de implementação ou execução dos novos testes.

## B1. Por que o core verify sozinho não basta

- O core verify exige `PINS` fixos (host, adapter, backend, launcher), sem
  runner, lifecycle, helper ou caller.
- Ele exige `SUMMARY_KEYS` e `TRANSPORT_KEYS` exatos e rejeita qualquer
  arquivo privado fora do `WHITELIST` (FILESET).

Os pins que ele confere continuam verdadeiros numa execução V2 (são as mesmas
fontes congeladas), mas não identificam a composição.

Por isso o core verify é reutilizado **inteiro e congelado** para a semântica,
e a composição vai num envelope externo fechado.

## B2. Artefatos novos, fora do mapa `private` do core

| Artefato | Kind (identificador proposto, ainda inexistente) | Limite |
|---|---|---|
| `v2-manifest.json` | `MASKGW_PG16_NATIVE_CONTROL_V2_MANIFEST_V1` | 4096 bytes |
| `case-N/v2-case.json`, para cada caso **executado** (no máximo 3) | `MASKGW_PG16_NATIVE_CONTROL_V2_CASE_V1` | 1024 bytes cada |

**Formato:** as mesmas regras do `_parse` congelado do core:
- ASCII;
- exatamente um LF final e nenhum `\n` ou `\r` antes dele;
- profundidade de colchetes até 32 (`MAX_DEPTH`);
- sem chave duplicada e sem constantes NaN/Infinity;
- inteiros com até 11 caracteres, no intervalo de −2³¹ a 2³²;
- reais finitos, com até 32 caracteres;
- forma canônica `sort_keys` com separadores `(",", ":")`.

**`v2-case.json`**, chaves exatas:

| Chave | Valor |
|---|---|
| `kind` | o kind V2_CASE |
| `number` | int 1..3 |
| `case` | nome do caso |
| `slot_outcome` | `"READY_FOR_VALIDATION"` |
| `lifecycle_reserved` | `true` |
| `reconcile_reserved`, `tree_latched` | bool exatos e iguais entre si |
| `owner_released` | `true` |

`reconcile_reserved: true` implica record `REJECTED`. O inverso não é
exigido.

**`v2-manifest.json`**, chaves exatas:

| Chave | Conteúdo |
|---|---|
| `kind` | o kind V2_MANIFEST |
| `nonce` | 32 hex |
| `executed` | int 1..3, igual ao prefixo do core |
| `summary`, `transport` | cada um `{name, bytes, sha256}` dos bytes reais; os privados ficam ligados transitivamente pelo transport e pelo `_bind` do core |
| `cases` | `executed` itens `{number, name, bytes, sha256}` dos `v2-case.json` |
| `sources` | exatamente 8 itens `{role, path, bytes, sha256}`, nos papéis e na ordem abaixo |
| `launcher` | `{sha256}` apenas |

| Papel | Caminho estático | Bytes / SHA de referência |
|---|---|---|
| `case_caller` | `docs/poc/pg16_shell_native_control_case_v2.py` | 22627 / `0fac3c7bd807e34c46e61a16c20bcda5c3a77b4ebed3c3404ff9250c4405a936` |
| `lifecycle_v2` | `docs/poc/pg16_shell_native_control_lifecycle_v2.py` | 14964 / `7bbf734c8b4a1fefe1617fc8c1cff2a5de0b33f8996eb98b0016233ab0b040cb` |
| `tree_reconcile` | `docs/poc/pg16_shell_tree_reconcile.py` | 2935 / `bb1f1984f5a144564a56e23fb5c4797dc0851651b608012ce229cc14d12a801b` |
| `runner` | `docs/poc/pg16_shell_native_control.py` | 30055 / `b4198fe1606120e1e2df4fe9bff6a52fce4601a67074fdd7e922ef528341a496` |
| `adapter` | `docs/poc/pg16_shell_native_control_win32.py` | 15373 / `eaebedd6ac36602ba30cb51a4c30a2a93737f1127c23cdc4ebb8ae8cf9246407` |
| `backend` | `docs/poc/pg16_shell_admission_win32.py` | 31948 / `10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726` |
| `host` | `docs/poc/pg16_shell_admission_host.py` | 33234 / `dfcc4ed6be3ea8ab47b7a38ca8a9d4bfa00b3c75cda41c365be3dd5b1aa3dac7` |
| `core_verify` | `docs/poc/pg16_shell_native_control_verify.py` | 24616 / `b3755d492ce147596a27dd9a36bc0ecf66686efd65ef60178915ab2d1d1f7a10` |

- **Launcher:** valor de referência
  `bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82`
  (`PYTHON_SHA` do host, `PINS` do core). O tamanho do binário é desconhecido
  neste lote e fica **fora do schema**; nada é lido para preenchê-lo. Se um
  produtor futuro capturar o tamanho, isso exige uma revisão do schema.
- **Tamanhos da tabela:** vêm de notas aceitas do ROOT e servem só como
  referência. O loader futuro mede os bytes que ele próprio executa.
- **Placeholders:** nunca são valor válido. Eles falham o padrão SHA
  `[0-9a-f]{64}`.
- **Escopo dos 8 papéis:** são as declarações de código selecionadas, não o
  fechamento completo da execução. Loader, coordenador, wrapper verificador,
  collector e publicador continuam como obrigações externas de confiança,
  revistas à parte. O manifest não finge incluir todo o código executado.

## B3. Dependências acíclicas e pins de posse do revisor

```
core_verify (congelado) ──pinado por constante──> verificador V2 futuro
helper, lifecycle, runner, adapter, backend, host ──lidos/hasheados/executados──> loader futuro
case_caller ──lido/hasheado/executado──> loader futuro
loader futuro ──hashes dos MESMOS bytes executados──> v2-manifest.json
v2-case.json, summary, transport ──sha──> v2-manifest.json
ExpectedV2 (entrada do revisor) ──comparado com──> manifest.sources/launcher
```

- O caller não calcula nem declara o próprio hash e não referencia o
  manifest.
- `ExpectedV2` é uma **tupla fixa** de 8 tuplas `(role, path, bytes, sha256)`
  com tipos exatos (`str`, `str`, `int`, `str`), mais o sha do launcher. É
  entrada do revisor e não fica embutido no caller.
- O caller agora tem SHA medido na tabela acima. Placeholders ainda
  inexistentes, nunca medição: `<V2_VERIFY_SHA256>` e `<LOADER_V2_SHA256>`,
  ambos NOT_YET_IMPLEMENTED.

## B4. Verificador V2 futuro (desenho)

`verify_v2(expected_v2, expected_core, manifest_raw, summary_raw,
transport_raw, private, metadata)` devolve um par fechado.

**Resultados:**

| Resultado | Quando |
|---|---|
| `("V2_VERIFIED_APPROVED", "OK")` | core VERIFIED_APPROVED e envelope válido |
| `("V2_VERIFIED_REJECTED", "OK")` | core VERIFIED_REJECTED e envelope válido; **nunca** convertido em inválido nem em aprovação de produção |
| `("V2_INVALID", motivo)` | motivo em `EXPECTED`, `INPUT`, `CAP`, `SCHEMA`, `NONCE`, `PIN`, `BINDING`, `PREFIX`, `METADATA`, `CORE_INVALID` ou `INTERNAL` |

**Ordem:**

1. **Congela as entradas por tipo exato antes de qualquer parse ou callback.**
   Nada é convertido a partir de objetos arbitrários.
   - `manifest_raw`, `summary_raw` e `transport_raw` são `bytes` exatos.
   - `private` e `metadata` são `dict` exatos com chaves `str` e valores
     `bytes` exatos, copiados para dicts novos.
   - `metadata` tem no máximo 3 entradas, com chaves exatamente
     `case-N/v2-case.json` para o prefixo executado.
   - `expected_v2` é a tupla fixa de B3, e `expected_core` é exatamente o
     `Expected` do core.
2. **Limites:**

| Item | Limite |
|---|---|
| summary | ≤ 16384 (`SUMMARY_CAP`) |
| transport | ≤ 4096 (`TRANSPORT_CAP`) |
| cada privado | dentro de `FILE_CAPS` |
| summary + transport + privados | ≤ 262144 (`TOTAL_CAP`) |
| manifest | ≤ 4096 |
| cada metadado | ≤ 1024, no máximo 3 |
| total combinado | ≤ 262144 + 3·1024 + 4096 = 269312 |

3. **Manifest:** parse estrito e chaves exatas.
4. **Nonce:** o do manifest é igual a `expected_core.nonce`. O core confere o
   mesmo nonce em transport e summary.
5. **Fontes e launcher:** papel, caminho estático, bytes e sha iguais a
   `expected_v2`. Um placeholder é inválido.
6. **Ligação:** summary e transport por sha e tamanho; cada `v2-case.json`
   por sha e tamanho.
7. **Prefixo e metadados:** `executed` é igual ao prefixo executado do
   summary. Cada metadado precisa ter `reconcile_reserved == tree_latched`
   (bool exatos), e o valor `true` implica record REJECTED.
8. **Core verify:** o verify congelado, executado a partir dos bytes pinados
   como o collector faz, sobre summary, transport e `private` **sem** os
   arquivos V2. Controles propagam.

**Alcance:**
- Prova que as declarações batem com bytes esperados e que a semântica é
  coerente.
- **Não** prova que esse código executou. Isso exige um loader futuro
  confiável que hasheie e execute **os mesmos bytes capturados**. Um
  autorrelato não autenticado nunca é rebatizado como execução real.
- Não há assinatura nem identidade viva/CIM.

## B5. Publicação, collector e entry futuros

- **Publicação:** nada de `_publish` legado seguido de um manifest escrito
  depois do rename final. O publicador futuro monta **todos** os bytes
  (summary, transport, privados, `v2-case.json` e manifest) antes de **um**
  commit terminal. Nenhum publicador existe agora.
- **Collector:** o antigo tem inventário fixo e não consome arquivos extras.
  Um collector V2 novo precisa de revisão própria; não existe seam para isso.
- **Entry:** a entry consumida não é reutilizada. Uma entry ou coordenador V2
  é trabalho futuro e separado.
- State16 e source10 não mudam.
- **Evidência v1** (inclusive 3f12dc584c29) nunca é embrulhada como V2. Sem
  um manifest com nonce novo produzido pelo loader V2, o resultado é
  `V2_INVALID`.

## B6. Testes futuros de B (só desenho)

- **Positivos:** um caminho V2_VERIFIED_APPROVED e um V2_VERIFIED_REJECTED
  (TREE).
- **Negativos:**
  - cada limite de B4 excedido;
  - chave extra ou faltando no manifest e no metadado;
  - papel fora de ordem;
  - caminho trocado;
  - pin trocado em cada um dos 8 papéis;
  - launcher trocado;
  - placeholder no lugar de um valor;
  - sha do summary ou do transport trocado;
  - `executed` divergente;
  - metadado ausente, extra ou com `reconcile_reserved ≠ tree_latched`;
  - `tree_latched` true com record APPROVED;
  - arquivo V2 dentro de `private` (core devolve FILESET → `CORE_INVALID`);
  - nonce divergente entre manifest e expected;
  - `expected_v2` que não é a tupla exata;
  - entradas que não são `bytes` ou `dict` exatos;
  - controle propagado.
- Todos com bytes sintéticos e o core verify real.

---

# Questões em aberto antes de escrever os testes de A

1. (Resolvida.) `MAX_READ = 4096` e `AUDIT_LIMIT = 512` foram confirmados
   pelo revisor nas fontes congeladas (§A4.6).
2. (Parcialmente resolvida por sonda do ROOT.) O reuso via `runpy` e
   `lab.__wrapped__` executou os três casos simulados existentes,11 artefatos
   em memória, owners fechados e core VERIFIED_APPROVED. Isso confirma o
   harness existente, sem medir o caller novo, que ainda não existe. O RED
   futuro continua obrigatório para a nova composição e seus71 cenários.
3. **Teste 37 (`_Context` genuíno para outro owner):** depende de registrar
   um segundo owner na lista original e de instalar, antes do prepare, um
   `context` com `__globals__` do lifecycle. É injeção controlada, não um
   caminho real.
4. **Coordenador e produtor futuros:** construção, registro, invocation,
   ordem de `KEEP`, retenção do owner até o latch e estacionamento são deles.
   A só retém e reporta.
5. **Atribuições Python não são atômicas:** um latch sob `MemoryError` ou sob
   interrupção na primeira atribuição não tem defesa. É o mesmo limite da
   entry e é coberto pela retenção do produtor.
6. **Proveniência de execução real (B):** depende de loader, publicador e
   collector V2 que ainda não existem.

Código gerado por IA: exige revisão humana e de segurança antes do merge.
