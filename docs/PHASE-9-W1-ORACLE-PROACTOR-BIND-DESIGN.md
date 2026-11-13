# W1 Oracle: contrato mínimo do bind Proactor — desenho B2

2026-11-13. Somente desenho, sob delegação, Claude2, sessão 51ea0d85, claude-opus-5-5/medium. Revisa B1 (812bc0fb) conforme BIND-REVIEW B2.1–B2.6 e B3.1–B3.5. Não é fonte, teste, prova nativa nem aprovação.

Ficam fixos: fonte 0a4dcd57, teste 36b2ba54, probe 0192ef43, owner/upstream/app124/state16/attempt. `tests/test_oracle9_w1_proactor_bind.py` fica AUSENTE até o root revisar e congelar os oráculos.

## 1. Assinatura (B2.1)

A API pública fica igual: `bind_proactor_pump() -> ProactorPump`. Helper privado no mesmo módulo:

`_bind_over(loop_class: object, *, pipe: object, devnull: object, ident: object) -> ProactorPump`

- `loop_class` é fábrica e referência de tipo ao mesmo tempo. O helper exige `isinstance(loop_class, type)`, constrói com `loop = loop_class()` e confere `type(loop) is loop_class`.
- O wrapper real passa `asyncio.ProactorEventLoop`; os testes passam classes falsas. Nenhuma constante de teste entra no produto.
- `pipe`/`devnull`/`ident` vão sem conversão para `ProactorPump`, que já os valida.
- O wrapper fica com os imports locais e as recusas de plataforma, thread principal e loop rodando, ANTES de uma única chamada a `_bind_over`.

## 2. Fases, referência conhecida e efeitos não observáveis (B2.5, B3.4)

| Fase | Falha | Resultado | Loop conhecido? | close explícito |
|---|---|---|---|---|
| W0 recusa no wrapper | — | `PumpFault()` | não: nada criado pelo bind | 0 |
| F0 `loop_class` não é classe | — | `PumpFault()` | não | 0 |
| F1 `loop_class()` | Exception ou controle | `PumpFault()` / o mesmo controle | **não**: a fábrica não devolveu objeto | 0 |
| F2 `type(loop) is not loop_class` | fault | §3 | sim: o objeto devolvido | 1 |
| F3 `ProactorPump(loop=loop, ...)` | Exception ou controle | §3 | sim | 1 |
| F3 | sucesso | devolve o pump | sim: o pump é o dono | 0 |

Em F1 há efeitos parciais possíveis e não observáveis: self-pipe, IOCP e wakeup fd (K1). Em F1–F3 podem atuar os finalizadores automáticos do SDK (`SDK-base_events.py.txt:690-694`, `__del__` → `close()`). Eles não são o close explícito do helper e não quitam nada. Nenhum caminho afirma zero efeito no SO ou liberação física.

## 3. Precedência do cleanup (B2.2)

Em F2/F3, a falha primária é registrada dentro do `except` PRIMÁRIO, e o fluxo sai dele. Depois, um único `loop.close()` explícito corre no seu **próprio** try/except de cleanup, que é necessário para classificar a falha do close. O relançamento acontece fora de qualquer `except`, sempre a partir do frame do helper. Controles são comparados só com `is` / `is not None`, nunca com `bool`.

| Primária | close ok | close com Exception | close com controle C2 |
|---|---|---|---|
| fault | `PumpFault()` | `PumpFault()` | C2, pela identidade (vira o primeiro controle) |
| controle C1 | C1 | C1 | C1 (C2 descartado) |

Todo `PumpFault()` é novo, com `args == ()`, `__cause__ is None` e `__context__ is None`. O cleanup não acrescenta `__context__` à falha primária nem ao controle do close.

## 4. Posse do loop conhecido e obrigação do chamador (B2.4, B3.1–B3.2, B3.4)

- **Sucesso:** o loop pertence só ao pump. O chamador retém o pump; `pump.close()` é a única tentativa de liberação (P3 §12).
- **Correção de L1:** `args` vazio não impede retenção. Em F2/F3 o helper levanta de dentro do próprio frame, e o local `loop` NÃO é apagado (sem `del` e sem `frame.clear`). O `__traceback__` do Throwable levantado inclui esse frame enquanto o objeto for mantido vivo. A prova sintética do root (`synthetic-traceback-reference-proof.json`) é evidência só da linguagem: não é do bind nem de cleanup.
- **Obrigação mínima proposta para o futuro chamador (prospectiva):** por invocação, reter o Throwable exato de bind (`PumpFault` ou controle), com o traceback original. Proibido:
  - serializar, substituir, `with_traceback(None)` ou `traceback.clear_frames`;
  - deixá-lo morrer no fim de `except ... as`.

  Isso vale até uma recuperação admitida. Sem atributo novo em exceção, sem registro global e sem mudança de API.
- **Estado atual:** nenhum chamador existe (o chamador host está ausente) e esta obrigação não está implementada nem provada. Sem ela, a referência ao loop se perde e o destino fica com os finalizadores do SDK.
- **Caminhos que NÃO sustentam a obrigação:**
  - **W0, F0 e F1:** não há objeto conhecido. Efeitos parciais de F1 seguem sem dono observável.
  - **close que bloqueia (N8):** não surge Throwable. O frame do helper fica vivo e bloqueado, e o chamador não recebe nada.
  - **controle assíncrono entre o retorno do pump e a atribuição no chamador:** o pump pode se perder.
  - **reter o Throwable não é cleanup.** Close falho continua sem quitação.

  A contenção e a posse externa da tentativa ficam para o gate nativo, antes de qualquer efeito.

## 5. Testes puros versus gate nativo (B2.3)

Os testes cobrem só `_bind_over`, com classes falsas próprias. Eles nunca certificam:
- as recusas de plataforma, thread principal e loop rodando do wrapper real;
- o efeito real de `ProactorEventLoop()` ou do close;
- wakeup fd, finalizadores, KeyboardInterrupt real ou fechamento físico.

Esses itens pertencem ao gate nativo separado (N8, N11, N15, construção e close), hoje NÃO preparado. Nenhum teste chama `bind_proactor_pump` ou cria loop real.

## 6. Oráculos aditivos antes da fonte (B2.6, B3.3, B3.5)

Arquivo novo `tests/test_oracle9_w1_proactor_bind.py`. Ele importa sem alterar `FakeLoop`, `FalseCtl`/`BoomCtl`, `assert_pump_fault`, `control_of` e `pump_module` do teste 36b2ba54. A carga do módulo é preguiçosa, fora de `pytest.raises`, e as classes de falha são subclasses próprias de `FakeLoop`.

- **BD-1:** `_bind_over(OkLoop, ...)` devolve o pump; `set_debug(False)` e handler ligados; zero `loop.close`; `close()` devolve True com um único close.
- **BD-2:** `loop_class` é instância, função ou `None` → `PumpFault`, zero construção.
- **BD-3 (F1):**
  - OSError(canário) → `PumpFault` sem canário e sem cadeia; zero close;
  - controle `FalseCtl` → o mesmo objeto, com zero `__bool__`.
- **BD-4 (F2):** `__new__` devolve outra classe → um close → `PumpFault`.
- **BD-5:** primária fault (task factory, loop rodando ou `ident` com Exception), cruzada com close {ok, Exception, C2}:
  - resultado `PumpFault`, `PumpFault` ou C2 (`is`);
  - sempre um close;
  - `C2.__context__` inalterado; `PumpFault` sem contexto, o que prova o close fora do `except` primário.
- **BD-6:** primária C1 (`ident` levanta `BoomCtl`), cruzada com close {ok, Exception, C2}: sempre C1 (`is`), `C1.__context__` inalterado, um close, zero `__bool__`.
- **BD-7 (retenção, B3.3):** em F2 e em F3 (fault e controle), o teste recebe o Throwable `t`.
  - O fake conhece só `weakref`/`id` da instância construída; não guarda referência forte própria.
  - O teste percorre `t.__traceback__` → `tb_next` e, para cada `tb_frame` desses frames recebidos, procura em `f_locals.values()` um objeto `o` com `o is ref()`.
  - Exige que o caminho forte exista, e a identidade exata.
  - Não chama GC nem finalizadores, não inspeciona SDK nem runtime alheio, e não altera controles ou tracebacks.
  - Em F1, nenhum loop conhecido é afirmado.
- **BD-8 (AST, só forma do wrapper):** `bind_proactor_pump` chama `_bind_over` uma única vez, com `asyncio.ProactorEventLoop`, `PIPE`, `DEVNULL` e `get_ident`, depois das recusas W0. Os imports nativos ficam só no wrapper. O módulo de teste não chama `bind_proactor_pump`. A regra "close fora do except primário" é provada por comportamento em BD-5/BD-6, sem proibir o try/except de cleanup.

Os 135 casos de 36b2ba54 e o probe 0192ef43 continuam valendo. Nada disso é reprodução nativa nem readmissão.

## 7. Autoridade e itens em aberto

1. Adoção da obrigação de §4 pelo futuro chamador e a definição de "recuperação admitida". Decisão do root/usuário; o chamador está ausente.
2. Gate nativo do bind: construção e close reais, bloqueio, wakeup fd, KeyboardInterrupt real e contenção/posse externa da tentativa. Hoje NÃO preparado.
3. `CliPlan`, receitas e readmissão continuam NOT_PREPARED.

N1–N16, T5, B1 fim a fim, B2, D-090 gate2, C1, D119, TLS, ingressos e produção seguem OPEN. Gateway indisponível.

Política Senff: desenho e código derivados por IA exigem revisão humana e de segurança antes do merge.
