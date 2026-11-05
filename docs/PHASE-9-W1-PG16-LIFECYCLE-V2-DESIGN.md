# Fase 9 W1 — PG16 lifecycle v2 (composição TREE/reconcile) — design

Status: MÓDULO PRIVADO REVISTO COM FAKES (TREE_COMPOSE_V8). Root mediu44/44
próprios e636/636 relacionados após a correção de ledger. Sem caller
operacional ou garantia nativa. Evidência final em
`PHASE-9-W1-PG16-LIFECYCLE-V2-VALIDATION.md` e `final-review.json`.
As notas de não medido nas seções históricas registram a entrega do
programador antes desses gates, não o estado atual.

Histórico medido pelo ROOT:
- RED42 do módulo ausente, arquivado em
  `docs/poc/evidence/lifecycle-v2-review-20261105/red42*`, com AST do teste
  `9f4955d9d9091caf48c005e7a4ccbc193c7c19b148f5313c0a835e8d3a4fc30c`;
- verde inicial 42/42 do módulo `580392b2…` (V6);
- RED44 (V7) do mesmo módulo, com os testes
  `4027984417a9dc811fb26859fd87acedb36b108a6b45d0090de681c0a8d065f8`
  congelados (§11).

Este documento cita só medições do ROOT; não produz medições próprias.

Os lotes TREE_COMPOSE_V4–V8 foram escritos pelo Claude2 sob a delegação
geral vigente (AGENTS.md, "Delegação vigente — 2026-10-20"). As decisões
abaixo foram tomadas sob essa delegação; nenhuma é uma aprovação individual.
Qualquer efeito nativo continua dependendo de um protocolo revisado e das
permissões efetivas da ferramenta. O ROOT executa e congela o RED antes de
cada implementação.

## 1. Escopo

- Módulo futuro: `docs/poc/pg16_shell_native_control_lifecycle_v2.py`, que só
  define coisas no import, sem `__main__`, CLI ou consumidor.
- Testes: `tests/test_pg16_shell_native_control_lifecycle_v2.py`, apenas com
  fakes.
- Expõe `context(owner, case, legacy, reconcile)` e `lifecycle(ctx)`.
- Não há chamador novo. O runner consumido (source10/state16), o helper e o
  teste congelado do helper ficam inalterados. Nenhum teste antigo é
  enfraquecido.
- Tentativa 3f12dc584c29: continua FAILED_ONLY_OPERATOR_ABORT, sem rerun, sem
  reuso de nonce e sem releitura privada.
- Gates continuam abertos:
  - Native3s NOT_MEASURED;
  - entry_gate NOT_EVALUATED;
  - identity Nov2 LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED;
  - Gateway/B1/B2/D090gate2/C1/SQL/produção.

## 2. Pins de origem (referência, não proveniência)

Os valores completos foram copiados das constantes dos fontes aceitos ou da
nota de validação aceita indicada.

| Peça | SHA-256 completo | Fonte do valor |
|---|---|---|
| runner `docs/poc/pg16_shell_native_control.py` | `b4198fe1606120e1e2df4fe9bff6a52fce4601a67074fdd7e922ef528341a496` | `RUNNER` em `pg16_shell_native_control_entry.py` |
| caller `docs/poc/pg16_shell_admission_host.py` | `dfcc4ed6be3ea8ab47b7a38ca8a9d4bfa00b3c75cda41c365be3dd5b1aa3dac7` | `HOST` no runner |
| adapter `docs/poc/pg16_shell_native_control_win32.py` | `eaebedd6ac36602ba30cb51a4c30a2a93737f1127c23cdc4ebb8ae8cf9246407` | `ADAPTER` no runner |
| backend `docs/poc/pg16_shell_admission_win32.py` | `10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726` | `BACKEND_SHA` no runner |
| verifier `docs/poc/pg16_shell_native_control_verify.py` | `b3755d492ce147596a27dd9a36bc0ecf66686efd65ef60178915ab2d1d1f7a10` | `VERIFY_SHA` em `pg16_shell_native_control_collect.py` |
| helper `docs/poc/pg16_shell_tree_reconcile.py` | `bb1f1984f5a144564a56e23fb5c4797dc0851651b608012ce229cc14d12a801b` | `PHASE-9-W1-PG16-TREE-RECONCILE-VALIDATION.md` (V7) |
| teste do helper `tests/test_pg16_shell_tree_reconcile.py` | `ad0742c02abe3544b9b4c5607df88563d1c0bf6458f278050cc0829adefe3a04` | idem, congelado |
| launcher (pin de schema) | `bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82` | `PINS` no verificador |

**Lacuna de proveniência.**
- Os artefatos sintéticos dos testes carregam os pins host/adapter/backend/
  launcher só para cumprir o schema do verificador congelado. Eles não
  descrevem uma execução v2 e nunca valem como proveniência de uma.
- Um chamador v2 futuro precisa de:
  - um registro de proveniência próprio (módulo v2 + helper + runner);
  - um verificador/schema revisado antes de qualquer evidência real.
- Neste lote isso fica "não identificado / em aberto".

## 3. Precondição confiável ≠ autenticação

`context` pressupõe que os colaboradores originais já foram carregados por
SHA, a partir de fontes fixadas. São eles:

- `legacy`, que são os globais reais do runner;
- o `RunError` e o `CODES` desses globais;
- `host`, owner, relógio e `reconcile`.

Essa é uma **precondição** e não é verificada como autenticidade.

Os guardas verificam só identidade e forma das referências já capturadas
(`is`, tipo exato, chaves `str` builtin). Servem para detectar deriva de
referências mutáveis no cenário de teste. Eles **não**:

- autenticam o código;
- contêm Python arbitrário malicioso;
- contêm reflexão, `gc`, `ctypes` ou mutação de `__code__`/`__class__`;
- defendem nada no meio de um helper legado confiável;
- dão garantia nativa.

Não é um framework de segurança geral. Nenhuma garantia ampla contra
adulteração arbitrária é feita ou testada.

## 4. `context(owner, case, legacy, reconcile)`: captura antes de efeitos

Não chama nenhum método do owner e não produz efeito nativo. Lê atributos e
captura referências.

### 4.1 Erro: duas fases

**Fase A — antes de capturar a classe de erro.** Verifica:

1. `type(legacy) is dict`, com toda chave `str` exata (por iteração, antes
   de qualquer lookup);
2. `legacy` contém `RunError` e `CODES`;
3. `RunError` é classe (`type(RunError) is type`) e subclasse de
   `Exception`; `RunError.__init__` é função com
   `__globals__ is legacy`;
4. `CODES` é `frozenset` exato e contém `"CONTROL_HELD"`;
5. `held_error = RunError("CONTROL_HELD")`, com
   `type(held_error) is RunError` e `held_error.args == ("CONTROL_HELD",)`.

Qualquer falha nesta fase **não** promete o `RunError` original, porque ele
ainda não foi capturado nem pode ser confiado. Nesse caso `context` levanta
uma recusa fechada e pura do próprio módulo v2: uma exceção local com código
fixo `"CONTEXT_REFUSED"`, sem argumentos variáveis, sem `__cause__`/
`__context__` e sem tocar `legacy`, `case`, owner ou registro.

Construir `held_error` executa `RunError.__init__` do runner. Isso só é
aceitável sob a precondição do §3 de que esse `RunError` é o original
fixado. Não é autenticação.

**Fase B — depois da captura.** Qualquer falha levanta o `held_error`
pré-construído. O `case` fica intacto e o owner continua registrado.

### 4.2 Referências capturadas (fase B)

1. **Hooks** de `legacy`: `_held`, `_ready`, `_last_close` e `_state` (função
   do runner, não do owner).
   - Exige `type(f) is FunctionType` e `f.__globals__ is legacy`.
   - `_close_unstarted` não é capturado nem delegado (ver §5.2).
2. **Registro:** `registry = legacy["_LIVE"]`, `list` exata contendo `owner`
   por identidade.
3. **`case`:** `dict` exato com chaves `str` exatas.
   - `case["facts"]` é `dict` exato.
   - `case["host"]` é `dict` exato. `_supervise` e `_attempt` são funções com
     `__globals__ is host`. `DEADLINE_SECONDS` é `float` exato.
   - `case["error"]` é classe; `case["name"]` é `str` exato em CASES.
   - `case["start"]` e `case["since"]` são `float` exatos.
4. **Flags:** `case["lifecycle_reserved"] is False` e
   `case["reconcile_reserved"] is False`, ambos presentes e preparados pelo
   produtor. Ausente, `True`, `0`, `"False"` ou outro valor → recusa antes de
   efeitos. As flags não alteram state16, e o `_case` antigo nunca as cria.
5. **Ledger:** `ledger = owner.ledger`, `dict` exato. O backend o muta in
   loco (`del self.ledger[name]`).
6. **Métodos vinculados originais.** Cada um é gravado como o par
   `(m.__self__, m.__func__)` e relido e comparado por esse par, nunca pela
   identidade do bound method efêmero:
   - `owner.setup`, `owner.start` e `owner.close`, com
     `m.__self__ is owner` e `m.__func__ is type(owner).<nome>`;
   - `case["clock"].now`, com `__self__ is clock` e
     `__func__ is type(clock).now`.
7. **`reconcile`:** capturado como objeto.

Os demais métodos do owner usados dentro de `_ready`/`_last_close`/
`_supervise` (read, wait, accounting, members, close_inner, terminate)
pertencem aos helpers confiáveis (§5.3) e não são pares capturados.

O contexto usa `__slots__` e expõe `held_error` aos testes.

## 5. `lifecycle(ctx)`

### 5.1 Fluxo

Pré-condição: o guarda completo (§6) vale. Depois:

1. **Reserva** `case["lifecycle_reserved"] = True` antes do setup. Uma
   segunda chamada levanta `held_error` sem efeitos.
2. Segue o fluxo mínimo copiado de `_lifecycle` (cerca de 35 linhas), com os
   mesmos códigos e a mesma ordem: setup → budget (`clock.now` capturado) →
   start → `_ready` (não NORMAL) → `_last_close` (LAST_CLOSE) →
   `_supervise`.
   - Usa só os pares e hooks capturados.
   - Faz o guarda imediatamente antes e depois de cada callback.
3. Se `facts["held"] is not None`:
   - **Elegível** quando os fatos têm chaves `str` exatas, `held` é
     exatamente `"CLEANUP"` (`str`), `reason` é exatamente `"TREE_UNPROVEN"`
     e `terminated`/`signaled`/`eof` são `True`. Nesse caso:
     1. guarda;
     2. `reconcile_reserved = True`;
     3. snapshot raso dos fatos (`retained` como `bytes`);
     4. `verdict = reconcile(owner, facts)` uma única vez;
     5. guarda.
   - **Não elegível**: o mesmo que TERMINATE com DEADLINE preexistente,
     READY, LAUNCH etc. Não chama `reconcile` e cai no `_held` legítimo
     (§5.3).
4. **Decisão pós-reconcile**, com uma leitura do estado pelo hook `_state`
   capturado:

| verdict (tipo exato `str`) | estado | ledger original | fatos == snapshot | registro/identidades | resultado |
|---|---|---|---|---|---|
| `REJECTED_CLOSED` | `CLOSED` | dict exato, vazio, `owner.ledger is ledger` | sim | ok | normaliza `facts["held"] = None`, **sem segundo close**, release local (§5.2), retorna |
| `RETAIN` / `NOT_APPLICABLE` | não `CLOSED` | — | sim | ok | `_held` legítimo (§5.3) |
| qualquer outro, inclusive `str` subclasse ou valor fora de VERDICTS | — | — | — | — | integridade → `raise held_error` |
| qualquer | `CLOSED` sem prova completa (veredito forjado, ledger substituído/não vazio, fatos alterados) | — | — | — | integridade → `raise held_error` |
| qualquer | qualquer | — | — | deriva de hook, host, registro, `RunError`/`CODES`, par de método ou `case["facts"]` | integridade → `raise held_error` |

5. **Sem TREE**, o caminho é o legado:
   1. guarda;
   2. `host["_attempt"](error, close)` pelo par capturado;
   3. guarda;
   4. estado `CLOSED` → release local; senão → `_held("CLOSE")` legítimo.
6. **A rejeição TREE nunca é apagada:**
   - `reason` continua `TREE_UNPROVEN`;
   - `exit_code`/`total_processes` ficam como o supervisor deixou, sem
     fabricação;
   - `_finish`/`_verdict` congelados produzem REJECTED.

### 5.2 Fechamento não iniciado e release: locais, sem `_release` legado

O `_close_unstarted` legado chama internamente `_release`, que resolve
`_LIVE` e `_state` como globais mutáveis, antes que qualquer pós-guarda
possa rodar. Por isso v2 **não** o delega. Usa um passo local mínimo,
`_unstarted(reason)`, nos três pontos em que o legado o chama (setup falho,
budget/relógio e launch falho):

1. `facts["reason"] = reason`;
2. guarda;
3. `host["_attempt"](error, close)` pelo par capturado;
4. guarda;
5. lê o estado pelo `_state` capturado;
6. `CLOSED` → release local; senão → `_held("LAUNCH")` legítimo (§5.3).

O **release local** é único em v2:
- `registry[:] = [item for item in registry if item is not owner]`;
- aplicado apenas na lista original capturada;
- só depois de guarda válida e estado `CLOSED` lido pelo hook capturado;
- nunca passa pelo `_release` legado nem por `legacy["_LIVE"]`.

Os efeitos observáveis (códigos, ordem de chamadas, fatos, registro) são os
mesmos do legado. Os testes de paridade de setup, launch e budget comparam
isso.

### 5.3 Delegação limitada aos helpers legados confiáveis

`_held`, `_ready`, `_last_close` e `host["_supervise"]` são delegados como
estão. A delegação é segura apenas dentro destes limites:

- **Precondição fixada:** os internos desses helpers são os do runner e do
  caller fixados (§2, §3). v2 não promete defender código arbitrário
  malicioso nem deriva de globais ocorrida *durante* um desses helpers. O
  pós-guarda detecta deriva visível depois do retorno; não desfaz efeitos.
- **`_held`:** só é chamado com guarda válida imediatamente antes e estado
  não `CLOSED`.
  - Internamente, `_retain` faz no máximo um terminate se RUNNING e escreve
    `held.json`. O ramo interno `_release` (estado `CLOSED`) não é alcançável
    sob a precondição, porque terminate não fecha o owner.
  - v2 não alega release protegido por esse ramo. Ele sempre termina
    levantando o CONTROL_HELD do próprio legado.
- **`_last_close`:** pode chamar `_held` internamente em falha de
  `close_inner` com estado não RUNNING. É o mesmo comportamento legado, sob
  a mesma precondição.
- **Nenhum helper legado** é chamado depois de uma recusa de integridade.

## 6. Guardas e recusa de integridade

- O guarda compara as referências capturadas com as atuais:
  - `legacy[nome] is hook` para os hooks do §4.2, `legacy["_LIVE"] is
    registry`, `owner` presente em `registry` por identidade,
    `legacy["RunError"] is RunError` e `legacy["CODES"] is CODES`;
  - `case["facts"] is facts`, `case["host"] is host` e os hooks de host;
  - os pares `(__self__, __func__)` relidos.
- Ele não passa pelos globais mutáveis sob teste: usa `type(...) is`, `is` e
  iteração. Nenhum lookup com chave estrangeira e nenhum `==` antes de
  verificar o tipo exato.
- A recusa de integridade:
  - levanta **diretamente** o `held_error` pré-construído;
  - nunca chama `_held`, `_contain`, `_release`, `close` ou o release local;
  - nunca escreve `held.json`;
  - deixa o owner, mesmo `CLOSED`, na lista original, e o ledger original
    sobrevive.
- Os snapshots dos fatos existem só em volta de `reconcile`, porque setup e
  supervise mutam os fatos legitimamente.

## 7. Chamador futuro protegido (não implementado)

O `_case` antigo **não é seguro** para este contrato:
- `except RunError` resolve o global mutável;
- o fallback genérico chama `_contain`, que libera um `CLOSED`.

Ele não é reutilizado sob deriva, nem nos testes. O chamador futuro deve:

1. registrar o owner na lista original **antes** de `context`. Diante de
   **qualquer** falha de construção (recusa fechada da fase A, `held_error`
   da fase B, outra `Exception` ou `BaseException`), o chamador retém o owner
   já registrado e o que tiver do contexto, e não aplica limpeza legada;
2. tratar o resultado de `lifecycle` pela identidade do `ctx.held_error` ou
   do `RunError` capturado, nunca pelo global;
3. não aplicar `_contain`/`_release` em falha de integridade;
4. deixar interrupções de controle (BaseException) propagarem com a
   identidade original antes, durante e depois do close, mantendo a posse;
5. ter sua própria proveniência revisada (§2).

## 8. Testes (matriz finita, 42 coletados)

Cenário de teste:
- `Owner` e `NestedJobOwner` reais com um kernel falso local derivado do
  `Kernel` dos testes do adaptador:
  - total histórico separado dos membros ativos;
  - pipe READY/NORMAL no resume;
  - ReadFile;
  - interrupções planejadas por (chamada, contagem).
- `write_new`/`_monotonic`/`_sleep` do host ficam em memória.
- `_finish` congelado e `verify(Expected, summary, transport, private)`
  completo.
- WinDLL, Popen, `os.system`, `Thread.start` e `time.sleep` ficam proibidos.
- Sem entry, sem runner operacional e sem I/O real.
- As execuções de paridade usam números de caso distintos, para que o
  `write_new` em memória não colida (`CONTROL_PERSISTENCE`).
- `run_case` recebe `(número, nome)` como uma única tupla tipada `Plan`.

| Grupo | Casos |
|---|---|
| Caracterização (só fontes consumidas) | 3: lote sintético legado → `VERIFIED_APPROVED`; legado estaciona TREE quieto em NORMAL e LAST_CLOSE |
| Paridade v2 = legado | 7 (NORMAL, TERMINATE, LAST_CLOSE; setup, launch, READY ausente, snapshot inválido) + 1 budget/DEADLINE |
| TREE quieto | 3: NORMAL → CLOSED uma vez, fatos = legado exceto `held`, `VERIFIED_REJECTED`/TREE_UNPROVEN; LAST_CLOSE → FAILED_LAST_CLOSE com audit íntegro, lote `VERIFIED_REJECTED`; segunda entrada benigna no registro preservada |
| Retenção legítima | 3: membro estrangeiro ou CloseHandle falho no close do reconcile → `_held` legado; TERMINATE+DEADLINE+TREE fora do helper |
| Integridade (`held_error`, sem `held.json`, sem release) | 13: 6 resultados forjados; fatos mutados após close real; `case["facts"]` substituído; `_LIVE` substituído; `_held` substituído; `host["_attempt"]` substituído; `owner.close` substituído; deriva de `RunError`+`CODES` |
| Flags/one-flight | 9: 6 flags malformadas, ausentes ou reservadas; owner não registrado; segundo `lifecycle` e segundo `context`; reconcile no máximo uma vez |
| Controle | 3: `Signal` no setup, durante o close e depois do close; identidade preservada, owner registrado, sem duplo close |

A recusa fechada da fase A (§4.1) é contrato documentado. Este lote não
acrescenta cenário para ela, para manter os 42 cenários. Medição do ROOT
sobre os testes `58bce1f9…`: 42 coletados, 3 aprovados e 39 erros de setup
por `FileNotFoundError`, porque o módulo não existe. É só a linha de base de
ausência, não correção de comportamento. Depois disso este lote fez só
ajustes de lint e assinatura no teste, ainda não medidos.

## 9. Lacunas em aberto

- Proveniência v2 e verificador/schema para evidência real: não
  identificados (§2).
- Chamador protegido (§7): não implementado. Nenhum caminho operacional usa
  v2.
- Recusa fechada da fase A: sem teste dedicado neste lote.
- O kernel falso modela a semântica documentada de JOBOBJECT apenas como
  suposição de teste:
  - `TotalProcesses` cumulativo;
  - KILL_ON_JOB_CLOSE no CloseHandle;
  - EOF por pipe vazio, processo morto e writer fechado.
  Não há medição nativa.
- O EOF em cache continua confiado pelo `_peek` do backend (limitação
  herdada do helper).
- A precedência LAST_CLOSE (AUDIT_INVALID > FAILED_LAST_CLOSE > TREE) vem dos
  fontes congelados. O caso de teste supõe que o supervisor faz terminate
  após o close do INNER no fake.
- Detecção de deriva só por identidade, sem defesa dentro dos helpers
  confiáveis (§3, §5.3).
- Docker Oracle Linux 9.8 (alvo final), Native3s, entry_gate e produção:
  abertos.

## 10. Notas factuais de implementação (V6, não medidas)

Módulo: `docs/poc/pg16_shell_native_control_lifecycle_v2.py`. Importa só
`FunctionType`/`MethodType` de `types`. No import define apenas constantes,
`ContextRefused`, `_Context` (`__slots__`) e funções. Não é loader, CLI nem
chamador.

| Ponto do design | Como ficou |
|---|---|
| Recusa fase A (§4.1) | `ContextRefused("CONTEXT_REFUSED")`, instância nova a cada recusa; `lifecycle` com `ctx` que não é `_Context` usa a mesma recusa |
| Fase B | `_build` devolve `None` ou é interrompido por `Exception`; nos dois casos sobe o `held_error` capturado, `from None`, fora de qualquer `except` |
| Métodos | `_lookup` pela MRO (`vars(klass)`), `_bound` compara `__self__`/`__func__`; as chamadas usam `MethodType(func, alvo)` refeito dos originais |
| Guarda | `_intact`: chaves `str` exatas de `legacy`/`case`/`host`/`facts`, identidade de hooks, `_LIVE`, `RunError`, `CODES`, `name`/`facts`/`host`/`clock`/`error` do case, `_attempt`/`_supervise`, `facts["retained"]`, `owner.ledger is ctx.ledger` (V8), owner presente na lista original e pares de métodos |
| Snapshot | Valores `None`/`bool`/`int`/`str` por tipo exato e valor; `bytearray` por identidade e `bytes`. Qualquer outro tipo → recusa |
| Falha comum inesperada | Retida atrás do `held_error`, sem cadeia. O CONTROL_HELD do `_held` legado capturado (tipo `RunError` original, `args` exatos) e o próprio `held_error` são relançados como estão |

Diferenças em relação ao texto do design:

1. **Correção aplicada no V8 (§11), ainda não medida.** No V6, a identidade
   `owner.ledger is ctx.ledger` ficou fora do `_intact` e só é exigida no
   ponto de prova pós-reconcile. Isso **não** é fail-closed, e o argumento
   de que "o backend muta o ledger in loco" justifica exigir a identidade,
   não dispensá-la. Como o backend original nunca reatribui `self.ledger`,
   um ledger substituído é sempre deriva. A identidade de campo deve valer
   em cada fronteira de guarda.
   - Repro do ROOT no lab falso, sem efeito nativo: o reconcile troca
     `target.ledger` por `{}` e retorna RETAIN. O módulo `580392b2…` levanta
     um RunError legado novo em vez de `ctx.held_error` e escreve
     `held.json`. O owner continua na lista original.
   - O §11 registra as regressões e a correção mínima.
2. `case["since"]` precisa ser `float` exato antes do `_supervise`; senão,
   `held_error`.
3. O estado é lido sempre depois de setup e de start (o legado só o lê
   quando precisa). Não há efeito nativo extra.
4. O CONTROL_HELD do `_held` legado é distinguido pelo tipo `RunError`
   capturado e pelos `args`, não pela origem exata.

Os itens 2 a 4 são fail-closed.

Medição do ROOT sobre o módulo
`580392b2af67b2fb2ebfb583a718be1633f202e24d1ee217ac8eb2cafbae905c`:
- testes: 42/42 em 3,811 s;
- Ruff check do PoC (E9, F63, F7, F82) e do teste completo: aprovado;
- format dos 2 arquivos: aprovado;
- teste `614029d6…` com AST inalterada (`9f4955d9…`, 60 asserts).

## 11. Regressões de identidade do ledger (V7) e correção (V8)

Dois testes foram acrescentados ao final do arquivo de teste. Os 42
anteriores não mudaram. Ambos usam a referência real `ctx.ledger` e
comparam a identidade do objeto original, não só o conteúdo.

1. `test_a_ledger_replaced_before_the_lifecycle_is_refused`: o ledger é
   trocado por um dict vazio novo depois de `context` e antes de
   `lifecycle`. Exige:
   - identidade `ctx.held_error`;
   - owner ainda NEW e na lista original;
   - `ctx.ledger` como o objeto original;
   - dict estrangeiro intacto;
   - zero chamadas ao kernel falso e nenhum `held.json`.
2. `test_a_ledger_replaced_during_reconcile_is_refused`: num TREE elegível,
   o reconcile troca o ledger e retorna RETAIN. Exige:
   - identidade `ctx.held_error`;
   - nenhum `held.json` e nenhum hold legado (`recorded`/`contained`
     continuam `False`);
   - o ledger original (mesmo objeto, conteúdo igual ao visto no drift,
     não vazio) e a lista original retidos;
   - substituto intacto;
   - nenhuma chamada ao kernel falso depois do drift.

**RED44 medido pelo ROOT** sobre o módulo `580392b2…`, sem alteração:
44 coletados, 42 aprovados e 2 falhas em 4,324 s. As 2 falhas são
exatamente os dois testes acrescentados. A AST dos 42 originais ficou
inalterada. Os testes `40279844…` foram congelados e arquivados como
`red44-tests.py.txt` e `red44-ledger.json`; Ruff check e format aprovados.

O snapshot completo `580392b2…` fica arquivado como dado anterior à guarda
de ledger. Não foi reexecutado operacionalmente.

**Correção mínima (V8).** Uma única mudança de código:
- a tupla de identidades do `_intact` ganhou o par
  `(ctx.owner.ledger, ctx.ledger)`;
- toda fronteira de guarda (`_check`, `_reserve`, `_state`, os pré e
  pós-guardas de callbacks e o guarda após reconcile) passa a exigir que o
  campo atual seja o objeto original capturado em `context`, antes de
  qualquer efeito;
- mutação in loco do dict original continua permitida;
- uma troca do campo é deriva e leva ao `held_error` direto, sem hold
  legado, sem escrita e sem chamada nativa adicional.

Sem mudança em schema, flags, helper, limites, semântica do lifecycle ou
testes. A prova pós-reconcile (`owner.ledger is ledger`, dict vazio) ficou
como estava e agora é redundante com o guarda. O verde 44 não foi medido;
o ROOT executa.

Código gerado por IA: exige revisão humana e de segurança antes do merge.
