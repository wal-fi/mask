# W1 Oracle: prova nativa benigna do pump/bind e contenção externa — desenho NP-D2

2026-11-13. Somente desenho prospectivo, sob delegação. Claude2, sessão 51ea0d85, claude-opus-5-5/medium, conforme NATIVE-PROOF-REVIEW NP1/NP2. Esta D2 corrige as quatro precisões de NP3 sobre a D1 (e038841a): READY, controle, N1 e N2/agregado. Não é admissão nativa, receita, teste, fonte ou aprovação. Não autoriza nenhuma chamada.

Ficam fixos: pump/bind publicados (`docs/poc/oracle9_w1_proactor_pump.py`: `ProactorPump`, `_bind_over` 1041–1085, `bind_proactor_pump` 1088–1109), PROACTOR-DESIGN P3 §15 (N1–N16), BIND-DESIGN B2 §2–§5, BIND-REVIEW B4, código 793473a, testes, probes, app124, estado16 e tentativa. T5, driver, main e EXPECT existem e não são reabertos.

## 1. Escopo e não-escopo

- **Alvo:** só os fatos N1–N16 do pump e os fatos de construção e close do bind, sobre recursos PRÓPRIOS de uma única tentativa, com um helper benigno.
- **Fora:** `run_host`, owner/ponte/reator com gateway real, T2/T4/T5/T6, Docker, PG, SQL, rede, segredos e produto. Um PASS aqui não fecha W1, B1, B2, D-090, C1, D119, TLS, ingressos nem produção.
- **Sem nova camada:** nenhum coordenador, owner, abstração de SO ou lançador novo. O único código futuro previsto é um harness de prova de uso único (§6), sujeito a oráculos, RED e revisão próprios, que chama só a API pública do pump.

## 2. Fronteira de posse e identidade (antes do loop)

Há três níveis de posse, nesta ordem de criação:

1. **Supervisor externo S**, fora do processo da prova:
   - existe e está armado ANTES de o processo de prova nascer;
   - detém um contêiner de processos do SO para a tentativa e um prazo de parede absoluto;
   - pode terminar toda a árvore e inventariar os processos que restam nesse contêiner.
2. **Processo de prova P:** um interpretador admitido, criado por S dentro desse contêiner. A thread principal de P é a dona do loop (exigência de `bind_proactor_pump`, 1095).
3. **Dentro de P:** o harness guarda por identidade, em variáveis locais fortes até o fim de P:
   - o pump devolvido;
   - ou o Throwable exato de bind, com o traceback original (B4);
   - a sequência de eventos;
   - o primeiro controle.

Regras:
- A identidade da tentativa é a do contêiner de S. Nada em P a substitui.
- Retenção em P é retenção CONHECIDA, não contenção. Ela não cobre os resíduos desconhecidos (§3). Só S os cobre, e apenas pela terminação da árvore.
- S não lê memória de P nem estado privado do SDK. Recebe só o canal de evidência (§5) e os seus próprios fatos: início, fim, código de saída e inventário do contêiner.

**Gap de capacidade:** nenhuma API publicada neste repositório implementa S. Sua existência, autoridade e mecanismo são uma capacidade externa a ADMITIR. Não é código a escrever aqui. Sem S admitido, a prova fica BLOQUEADA.

## 3. Resíduos: conhecidos e desconhecidos

| Resíduo | Conhecido por P? | Quem contém | Pode ser declarado |
|---|---|---|---|
| Loop/pump retidos após `close()` False ou BROKEN | sim (pump retido) | P até o fim; depois S | retido, nunca liberado |
| Loop conhecido em F2/F3 (B4) | sim (traceback) | P até o fim; depois S | retido |
| F1: fábrica falhou sem objeto (K1: self-pipe, IOCP, wakeup fd) | não | só S | desconhecido |
| `close()` bloqueado (N8, `IocpProactor.close`) | não retorna | só S, pelo prazo de parede | FAIL N8; desconhecido |
| Controle entre o retorno do bind e a atribuição | não | só S | desconhecido |
| S4 pendente para sempre; START_FAILED sem handle | parcial (fase) | P retém; depois S | UNKNOWN |
| EOF pausado no cap (R4/N4) | sim | P retém; depois S | retido por desenho |
| Automatismos do SDK (`__del__`, close interno; K4) | não | — | nunca contam como quitação |

- P nunca descarta pump, Throwable ou handles para "limpar".
- O fim de P ocorre só por saída própria depois do relatório, ou por terminação de S.
- **A terminação por S é limpeza, nunca prova.** Kill, código de saída ou ausência de mensagem não provam liberação completa.
- Inventário vazio do contêiner depois da terminação é um fato delimitado: nenhum processo próprio visível naquele instante. Não prova handles, memória ou efeito global no SO.

## 4. Tempo: observação limitada versus chamadas sem teto

- **Limitado e lógico:** os alvos de `run_until(target, stop)`, os prazos do harness por caso e a janela de observação de cada N. Valem só enquanto as chamadas retornam.
- **Sem teto:** construção do `ProactorEventLoop`, `ProactorPump.__init__` sobre o loop real, `loop.close()`, `subprocess_exec` síncrono interno e qualquer chamada síncrona do SDK. Nenhum mecanismo em P as interrompe.
- **Parada externa obrigatória:** só o prazo de parede de S limita esses pontos. Quando ele vence:
  - S termina a árvore;
  - os N em curso valem FAIL (bloqueio observado) ou INCONCLUSIVO, conforme a matriz;
  - nada vale PASS.
- Não se usa `wait_for`, cancelamento, thread auxiliar, sinal ou injeção privada para "dar teto" ao SDK.

## 5. Canal de evidência limitado

- Um canal unidirecional P→S de linhas canônicas ASCII: cada uma com no máximo 512 bytes incluindo o LF, e um número máximo de linhas fixado antes da tentativa. Os limites seguem a família HostLink já usada no W1; os valores são NOT_PREPARED.
- Campos só de enums fechados e inteiros exatos:
  - caso N;
  - ordem dos eventos por nome do enum de eventos do pump;
  - `BindResult`/`PumpCloseResult` como nomes;
  - returncode;
  - contadores;
  - veredito local do harness.
- Nunca entram argv, bytes do helper, mensagens, repr de exceção, caminhos ou ambiente.
- Para cada linha, S registra o instante pelo próprio relógio. Linha a mais, malformada ou fora de ordem invalida a tentativa (FAIL de canal), sem nova tentativa.
- P tenta escrever a primeira linha (READY) antes de qualquer import nativo. Isso é só ordem pretendida, não prova:
  - a escrita pode ter ocorrido e o recibo em S atrasar, falhar ou nunca chegar;
  - sem READY no prazo, o estado é UNKNOWN e a tentativa vale INCONCLUSIVO; ausência de READY NÃO prova ausência de import, bind ou efeito;
  - S mantém a posse e contém por identidade do contêiner, que já cobria P antes do nascimento (§2). Nenhum handshake adicional é criado para fabricar essa prova negativa.
- **Controles:** depois de capturar o primeiro controle, o harness faz SÓ isto:
  - mantém a identidade exata, sem `bool` e sem alterar `__traceback__`/`__context__`;
  - retém os próprios dados com leituras puras.

  Nenhuma nova escrita no canal, flush, leitura de relógio, close ou qualquer outro efeito, nem para anunciar o controle. Isso evita bloquear, falhar ou mascarar o controle. Não existe linha CONTROL nem camada de log.
- S classifica a tentativa como UNKNOWN pelos próprios fatos observados: linhas recebidas, prazo, saída de P e inventário. Ausência de linha de controle não é ausência de controle. Um controle, conhecido ou suspeito, nunca é PASS.

## 6. Harness e helper (só categorias)

**Harness de prova**, código futuro, não produto:
- Faz uma única chamada a `bind_proactor_pump()`.
- Depois usa só `now`, `schedule_start`, `run_until`, `close` e os métodos do handle entregues em `started`.
- `StartRequest`/`events` são objetos próprios que só registram, como os já usados nos oráculos do pump. Não há owner novo.
- Não importa SDK privado, não faz monkeypatch nem substitui classes ou funções do produto.
- Não lê variável de ambiente nem configuração.

**Helper benigno**, por categoria:
- programa local do próprio runtime admitido, em modo isolado;
- sem rede, segredos, banco, Docker, escrita fora de área própria descartável ou criação de netos;
- comportamentos fechados e sintéticos: emitir N bytes determinísticos no stdout, ler stdin até EOF, aguardar fechamento, sair com código c (inclusive c > 255), ou não iniciar (falha de partida por alvo inexistente);
- argv, caminhos e valores são NOT_PREPARED; uma revisão admite cada perfil antes do uso.

**Ordem dos casos:**
1. casos que terminam quiescentes;
2. depois os que retêm por desenho (N4) ou bloqueiam (N8 no limite);
3. nesse ponto a tentativa termina.

Não há nova tentativa no mesmo contêiner.

## 7. Matriz N1–N16

Notação: "Ev" = categoria da evidência; P/F/I = PASS/FAIL/INCONCLUSIVO. O escopo é sempre "este runtime admitido, este helper, esta tentativa".

| N | Ev | PASS | FAIL | INCONCLUSIVO |
|---|---|---|---|---|
| N1 ordem de callbacks | sequência de eventos registrada no harness e retorno de S4 | `started` precede os demais eventos conforme P3 §7. Unicidade exigida só nos fatos únicos do contrato: `started`, `exited`, `closed` e `pipe_lost` por fd. `data` e `write_resumed` podem repetir | evento antes de `started`, ou fato único repetido (`started`/`exited`/`closed`, `pipe_lost` do mesmo fd) | a ordem pendente antes do waiter não ocorreu (não é forçável) |
| N2 authorize → CreateProcess | marca no `authorize` do request e o próximo evento | só PASS PARCIAL do subconjunto medido: nenhum evento do owner entre o retorno de `authorize` e `started`/`start_failed` | evento intermediário | a propriedade completa (intervalo authorize→CreateProcess no SO) fica sempre INCONCLUSIVA; N2 nunca tem PASS completo |
| N3 escrita com high=0 | `write`, `buffer_size`, `write_resumed` | cada escrita classificada como SENT síncrona ou via `write_resumed`, sem perda | SENT com buffer > 0 ou sem classificação | só um dos caminhos ocorreu |
| N4 EOF pausado | `pause_reading`, ausência de `pipe_lost(1)`, `close()` False | retenção exatamente como R4 prevê | EOF entregue com a leitura pausada | — (residual: termina a tentativa) |
| N5 fechamento de pipes e handle | `closed()`, `close()` do handle e inventário de S | eventos e `close` True; S sem processo próprio após a saída de P | evento ausente ou close False em entrada quiescente | handles no SO sem observação externa admitida |
| N6 close assentado não mata; código 1 | returncode antes e depois do CLOSE do handle; `kill` em helper vivo | código natural inalterado; `exited` 1 após kill | código alterado pelo close | — |
| N7 falhas de partida | `start_failed`/`not_started` e fase | classificação conforme P3 §6 | NOT_STARTED após efeito possível | vazamento parcial de pipe: inobservável |
| N8 `loop.close` quiescente | retorno de `close()` dentro do prazo de S | True dentro da janela | bloqueio até o prazo de S (S termina) | wakeup fd e executor: sem leitura pública não destrutiva |
| N9 logs | registros limitados do logger `asyncio`, por handler público do harness | nenhum canário de argv/dados nos registros capturados | canário presente | ausência de registro não prova ausência de outros destinos |
| N10 exit > 255 | `exited(code)` | código exato entregue | código alterado | — (limite do owner K6 continua) |
| N11 KeyboardInterrupt real | precisa de evento de console externo | — | — | BLOQUEADO até capacidade e autoridade admitidas |
| N12 memória | métricas do processo P observadas por S | dentro de teto declarado antes | acima do teto | sem métrica admitida |
| N13 voltas ociosas | `run_until` sem eventos até o alvo | retorna no alvo sem PumpFault | PumpFault de ociosidade em caso nominal | — |
| N14 estratégia cap/pausa | — | — | — | OPEN: é desenho, não medição; N4 só confirma o risco |
| N15 hooks de auditoria e sinal | admissão do runtime | — | — | ASSUMIDO como precondição; sem enumeração pública |
| N16 inserção parcial de `call_at`/`create_task` | — | — | — | INCONCLUSIVO pelo contrato (não injetável publicamente) |

- **Construção e close do bind (BIND §7.2):**
  - **PASS:** `bind_result` PUMP e `close()` True, junto com N8.
  - **F2/F3 com Throwable:** retido, nunca PASS.
  - **F1:** desconhecido, só S contém.
  - Recusas do wrapper (plataforma, thread, loop rodando) só podem ser observadas como `PumpFault` sem efeito: PASS delimitado.
- **Agregado:** nenhum N obrigatório é retirado por ser chamado de "não aplicável".
  - Uma tentativa pode, no máximo, rotular PASS um SUBCONJUNTO medido, nomeado explicitamente N a N. Para isso, cada N do subconjunto precisa ser PASS, o canal precisa estar íntegro, P precisa sair por conta própria depois do relatório e o inventário de S precisa estar vazio.
  - Em qualquer outro caso: FAIL ou INCONCLUSIVO, com resíduos registrados.
  - Mesmo o PASS do subconjunto é fato delimitado de recursos próprios, não release global.
- **Gate completo pump/bind continua OPEN.** N2 é parcial, N11 está bloqueado, N14 está OPEN e N15 não está admitido; N16 segue o tratamento particular do seu contrato aceito.
  - Não há PASS do gate completo até que cada requisito seja cumprido ou receba revisão explícita própria.
  - Este desenho não concede dispensa.

## 8. O que falta e não é código

1. **Autoridade:** aprovação explícita de uma execução nativa, com host, destino e revisor da evidência.
2. **Admissão do runtime:** pins do interpretador real (CPython 3.11.3/Windows é só referência histórica), hooks (N15), handler de sinal e wakeup fd prévio (K1) e ambiente herdado.
3. **Capacidade S:** contêiner de processos externo, prazo de parede, terminação da árvore e inventário, admitidos e revistos antes de P existir.
4. **Perfis do helper e limites do canal:** valores revistos (hoje NOT_PREPARED).
5. **Depois:** só então oráculos e RED do harness, e só então o código do harness.

Nenhum desses itens é resolvido por camada pura nova. Até que 1–3 existam, N1–N16 e o gate do bind seguem OPEN, e nenhuma chamada nativa é autorizada.

Política Senff: desenho e código derivados de IA exigem revisão humana e de segurança antes do merge.
