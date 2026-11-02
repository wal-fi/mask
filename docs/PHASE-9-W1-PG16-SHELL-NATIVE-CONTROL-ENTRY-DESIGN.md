# Entrada privada do controle nativo — posse em primeiro plano (desenho)

Data: 2026-11-02, America/Sao_Paulo. Desenho sob a delegação geral vigente do
usuário e revisão do root; não é nova aprovação individual. Programador
Claude2, sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`,
esforço `medium`. O desenho inicial foi seguido pela entrada privada e seus
testes simulados; notas históricas e correções estão na seção11. Não há
nonce, raiz ou comando operacional, nem execução nativa. O programador não
executou testes; medições do revisor constam da validação da entrada.

Fontes congeladas e não tocadas: orquestrador
`docs/poc/pg16_shell_native_control.py`
`b4198fe1606120e1e2df4fe9bff6a52fce4601a67074fdd7e922ef528341a496`; adaptador
`eaebedd6ac36602ba30cb51a4c30a2a93737f1127c23cdc4ebb8ae8cf9246407`; backend
`10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726`; chamador
`dfcc4ed6be3ea8ab47b7a38ca8a9d4bfa00b3c75cda41c365be3dd5b1aa3dac7`; estado de
16 campos, fontes/raízes consumidas e instantâneos de revisão.

## 1. Problema e invariante

`run(nonce)` mantém owners não provados em `_LIVE`, que só existe enquanto o
processo controlador vive. O backend nunca libera recurso incerto: `_hold`
só marca HELD, `_expect` recusa depois qualquer operação, valores em
quarentena nunca são usados e `close` só chega a `CLOSED` após quietude
provada (leitura do programador das fontes congeladas). Logo, um owner
retido existe apenas na memória do controlador.

Invariante aceito (sem abandono): o controlador só termina por conta própria
com registro **comprovadamente vazio**. Registro retido, desconhecido ou
ilegível leva a um estado estacionado em primeiro plano, que mantém o
namespace e o ledger vivos, não repete `run` nem limpeza nativa e não sai
sozinho.

### Fatos citados (fontes primárias conferidas pelo revisor, não pelo programador)

O revisor consultou em 2026-11-02:
[Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
e
[ExitProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-exitprocess).
Paráfrase breve do que foi relatado pelo revisor:

- A saída de um processo fecha os handles que ele possui; ela não termina,
  em geral, os processos filhos.
- Com `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, fechar o último handle do job
  termina os processos associados ao job.

Inferência de desenho (não fato documental): fechar handles na saída é rede
de segurança, não limpeza observada; não prova que todos os recursos foram
vistos ou colhidos e não alcança, por exemplo, um processo suspenso que
ficou fora dos jobs num caminho de aborto com falha. Sair com owner retido é
abandono.

## 2. Alternativa rejeitada (não implementada)

A proposta anterior do programador de **sair em HELD** com código 3 e rótulo
`RETAINED_UNTIL_EXIT`, contando com o fechamento de handles pelo SO, foi
**rejeitada** na revisão de desenho e nunca foi implementada: contradiz o
invariante, descarta `_LIVE` e aceitava conscientemente um resíduo suspenso
fora dos jobs sem evidência de PID. O rótulo não corrige o abandono. Também
fica rejeitado o prazo externo de 600 s para matar o controlador.

## 3. Arquivo proposto e estágios

Arquivo (implementado no incremento descrito na seção 11, nunca invocado): `docs/poc/pg16_shell_native_control_entry.py`,
cerca de 100 linhas, sem lifecycle, sem cópia do backend, sem limpeza nativa,
sem método de recuperação e sem framework. Único `__main__`:
`raise SystemExit(main(sys.argv[1:]))`. Nada é lido nem instalado no import.

| Estágio | Conteúdo | Saídas permitidas |
|---|---|---|
| S0 PURE | exatamente um argumento, nonce de 32 hex minúsculo | `FINAL` código 2 (`ENTRY_ARGV`) |
| S1 READ | leitura limitada (≤65536) do orquestrador, `lstat` regular sem reparse, SHA b4198fe1 completo | `FINAL` código 2 (`ENTRY_SOURCE`) |
| S2 NAMESPACE | cria o dict `N`, guarda-o em `KEEP` **antes** do `exec`; executa a fonte; captura imediatamente `live = N.get("_LIVE")` e guarda `live` em `KEEP`; valida | registro confiável vazio: `FINAL` 2 (`ENTRY_LOAD`); qualquer outro: **PARK** |
| S3 ARM | valida o par de PIDs, instala handlers na thread principal e emite `IDENTITY` | falha com registro confiável vazio: `FINAL` 2 (`ENTRY_ARM`); senão PARK |
| S4 ACTIVE | uma única chamada `N["run"](nonce)` | — |
| S5 SETTLE | decisão por registro e desfecho | `FINAL` 0/1/2/4/5 só com registro confiável vazio; senão PARK |
| S6 PARKED | estacionado, pegajoso | nenhuma |

Regras dos estágios:

- S0 e S1 são recusas puras: antes de qualquer execução do orquestrador ou
  efeito nativo. São as únicas saídas sem checar registro.
- A partir de S2 (namespace existe, mesmo parcialmente executado) toda saída
  exige registro confiável vazio, inclusive na validação da carga e em
  falha do `exec`. Não existe código 2 com posse retida ou desconhecida.
- Registro confiável vazio: `type(N) is dict`, `N.get("_LIVE") is live`
  (o **objeto original** capturado em S2), `type(live) is list` e
  `len(live) == 0`, avaliado sob `try`; qualquer exceção na inspeção conta
  como não confiável.
- Referências fortes em `KEEP` (lista global do módulo da entrada), todas
  antes de `run`: `N`, o objeto `live` original e, quando ocorrer, a
  `BaseException` original com seu traceback (mantém os frames e, por eles,
  os owners). Nada de `KEEP` é removido.
- S4: `ACTIVE = True` imediatamente antes da chamada e `ACTIVE = False` em
  `finally`. A primeira `BaseException` vinda da chamada é a original e é
  guardada; nunca é impressa nem formatada.
- A transição S2–S5 inteira fica sob o driver protegido, incluindo falha
  parcial do `exec` e captura do registro; não apenas a decisão final.
  Uma reserva `attempted` precede a chamada de `run` e nunca é desfeita:
  interrupção entre a reserva e a chamada pode impedir a chamada, mas nunca
  gera retry. `run` é chamado no máximo uma vez, exatamente uma no caso normal.
- A instalação dos handlers deve estar comprovadamente concluída antes de
  S4. Não se promete proteção de entrega nativa em estágios anteriores à
  instalação, nos quais a fonte pinada ainda não pode ter criado recursos
  dos controles. Falha nessa instalação nunca chega a S4.

Desfechos com registro confiável vazio:

| Código | Desfecho |
|---|---|
| 0 | `run` retornou, lote `APPROVED` (transporte confirmado) |
| 1 | `run` retornou, lote `REJECTED` (transporte confirmado) |
| 2 | recusa fechada (`CONTROL_*` do orquestrador ou `ENTRY_*`) |
| 4 | `CONTROL_COMMIT_INDETERMINATE`: posse resolvida, publicação indeterminada |
| 5 | interrupção com todos os owners provados `CLOSED`; estado da publicação desconhecido, conferido só por leitura |

Código 0/1 exige um descritor retornado de tipo e rótulos fechados esperados;
valor apenas verdadeiro, `bool` no lugar de código inteiro ou descritor
malformado nunca aprova. Não se duplica a validação completa do transporte
do orquestrador na entrada.

PARK: `CONTROL_HELD`, interrupção com posse não resolvida, registro não
vazio, substituído, malformado ou ilegível, ou falha interna da própria
entrada depois de S2.

## 4. Estacionamento pegajoso e unidades testáveis

Estado do módulo: `_STATE = {"active": False, "parked": False,
"announced": False}`. `parked` só recebe `True` em todo o código-fonte; nada
o volta a `False`.

Unidades finitas (testáveis sem laço infinito):

- `decide(N, live, outcome) -> ("EXIT", code, label) | ("PARK", reason)`:
  pura, sem I/O; aplica a tabela acima.
- `settle(decision) -> ("EXIT", code) | ("PARK", reason)`: se `parked` já é
  verdadeiro, devolve PARK sempre. Para EXIT, volta a checar o registro confiável
  vazio no próprio momento; se não confiável, marca `parked = True`. Ao
  estacionar, marca `parked = True` **antes** de escrever e emite `PARKED`
  uma única vez (`announced` marcado antes da escrita). Não chama `run`,
  owners nem nada nativo.
- `cycle()`: uma única pausa (`_pause`, por exemplo `time.sleep` de valor fixo),
  engolindo qualquer `BaseException`; devolve `None`.

Driver protegido (não executado em modo estacionado nos testes; verificado
por AST):

- `_hold()`: `while True:` com `try: cycle()` e `except BaseException: pass`;
  sem `return`, `break` ou condição variável. Não há seam `_forever`.
- `main` depois de S2: `while True:` com `try`: `verdict = settle(decision)`;
  só devolve um código inteiro permitido se o verdict EXIT é válido,
  `parked` é falso e a confiança no registro vazio é revalidada imediatamente
  antes desse `return` (único posterior a S2); caso contrário `_hold()`.
  `except BaseException: continue`, preservando a reserva da chamada.
  Retorno inesperado de qualquer auxiliar, EOF (stdin nunca é
  lido), saída quebrada ou controle repetido não transformam PARK em saída
  nem em `None`.

## 5. Sinais de console

- Um único handler local `_on_console(signum, frame)`: se `_STATE["active"]`
  é verdadeiro, levanta `KeyboardInterrupt`; caso contrário retorna sem
  efeito. Sem contador, sem saída, sem alocação além do mínimo, sem I/O.
- Instalado em S3 para `SIGINT` e `SIGBREAK`, apenas na thread principal
  (`signal.signal` fora dela falha e a entrada recusa em S3), antes de
  qualquer efeito do orquestrador. Nunca no import; nunca restaurado.
- Fase ACTIVE: `SIGINT` mantém a semântica do handler padrão do Python
  (levanta `KeyboardInterrupt`), preservando os caminhos de interrupção do
  orquestrador e do backend. Para `SIGBREAK` o comportamento padrão do SO
  terminaria o processo; aqui vira `KeyboardInterrupt` de propósito, para
  cair no caminho de retenção e não abandonar.
- Fase inativa/estacionada: controles de console esperados são ignorados.
- Lacunas explícitas: handlers Python só rodam entre bytecodes da thread
  principal, depois de chamadas síncronas do SO; há janelas de poucos
  bytecodes perto de S3 e da fronteira de S4 (cobertas pelo laço externo,
  não provadas nulas). Fechamento do console, logoff, desligamento,
  `TerminateProcess` externo e falha fatal do interpretador não são
  bloqueáveis; o mapeamento desses eventos para sinais Python não foi
  verificado pelo programador.

## 6. Eventos no pipe

Saída padrão é exatamente o pipe do harness do root; redirecionamento para
arquivo é proibido pelo procedimento (a entrada não o verifica). Cada evento é
uma linha JSON ASCII canônica, com `flush`, `kind =
"MASKGW_PG16_NATIVE_CONTROL_ENTRY_V1"`, chaves fechadas:

| Evento | Campos além de `kind`/`event` |
|---|---|
| `IDENTITY` (S3, antes de efeitos) | `nonce12`, `controller_pid`, `parent_pid` |
| `FINAL` | `nonce12` (ou `null` em S0), `controller_pid` (ou `null` antes de S3), `code`, `outcome`, `refusal` |
| `PARKED` | `nonce12`, `controller_pid`, `reason` (`HELD`, `INTERRUPTED`, `UNKNOWN_REGISTRY`, `INTERNAL`), `retained` (inteiro ou `null`) |

- `controller_pid` (`os.getpid()`) e `parent_pid` (`os.getppid()`) são
  observáveis só locais, para o root distinguir o interpretador base do
  redirecionador da venv; nunca entram em evidência. `nonce12` já é o nome
  público.
- Sem caminhos, valores de ambiente, tipo ou texto de exceção, nem PIDs de
  filhos. `outcome`/`refusal` são rótulos fechados.
- No máximo um `IDENTITY` e depois exatamente um de `FINAL` ou `PARKED`.
  Falha ao escrever `IDENTITY` antes de S4 é recusa (`FINAL` 2 tentado, com
  registro confiável vazio). Depois de S4, falha de escrita é engolida e
  nunca libera recurso retido nem muda a decisão.
- Depois da chamada a `run` não há I/O explícito de sistema de arquivos em
  nenhum caminho: sem formatação de traceback, sem módulo `traceback`, sem
  log. O rename final do orquestrador continua sendo a última operação de
  arquivo dele; a escrita da linha no stdout vai ao pipe, não a arquivo. No
  caminho de saída o interpretador só esvazia o stdio ao terminar (`-B`
  impede `.pyc`).

## 7. Duração, yield e testemunha existente

- Sem prazo fixo de parede para matar o controlador. Orçamentos do
  orquestrador são estimativas de decisão entre chamadas; chamadas síncronas
  do SO não têm limite absoluto.
- O yield do exec do root devolve o controle com o processo vivo; yield não
  é término.
- Testemunha limitada fornecida pelo revisor (histórico, não nova medição):
  a sessão de exec 44755 executou pytest pela Python da `.venv`, 975 testes em
  284,25 s, atravessando yields/retomadas repetidos em 2026-11-01 e
  terminando 0. Estabelece apenas persistência observada através de yield;
  não estabelece imunidade a encerramento do app/sessão, entrega de
  Ctrl+Break, identidade de PID nem vida indefinida.
- Fechamento do app, logoff, reboot e término fatal são desfechos
  FAILED/UNKNOWN impossíveis de impedir; não há rerun automático nem
  alegação de limpeza. Não se exige prova de sobrevivência a esses eventos.

Sonda pré-nativa ainda necessária (precisa de proposta e revisão próprias;
não autorizada aqui): uma única sonda de identidade só com stdlib, sem
`ctypes`, sem criar subprocessos ou acionar APIs de Job Objects, executada
pela mesma Python da `.venv`
`-I -B` no mesmo harness. Ela emite uma linha no esquema `IDENTITY`,
atravessa um yield do root e termina sozinha com código 0. Objetivo único:
confirmar que o root mapeia `controller_pid`/`parent_pid` a processos vivos
no seu monitor (redirecionador versus Python base) e que linhas com `flush`
chegam pelo pipe através do yield. Não testa queda, Ctrl+Break nem
encerramento do app.

## 8. Pins, TOCTOU e procedimento

- Pins conhecidos: orquestrador b4198fe1…a496, adaptador eaebedd6…6407,
  backend 10c9058f…2726, chamador dfcc4ed6…dac7 (completos acima), launcher
  `bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82`.
  Entrada: `356d22914c21c7fefb195b9471b12591cd7120deb152524104ff3b4559fbf0c6`;
  testes: `1d65de063839bf8a108d13b7d9918c98ca60ec637518faad6f473b2155418f95`.
  Pins medidos após o fix; gates do revisor na validação da entrada.
- A entrada fixa o orquestrador; os bytes da própria entrada só são fixados
  pelo procedimento externo (hash pelo root imediatamente antes), com
  janela TOCTOU até a leitura pela Python. O binário do interpretador que
  executa a entrada não é fixado antes de executar; o launcher é conferido
  pelo orquestrador a cada caso, sem atomicidade com a criação.
- Sem método de recuperação: o processo estacionado não aceita entrada.
  Qualquer recuperação futura exige protocolo próprio revisado.
- Modelo de invocação (somente placeholders; nenhum artefato existe):
  `<REPO>\.venv\Scripts\python.exe -I -B <REPO>\docs\poc\pg16_shell_native_control_entry.py <NONCE32>`,
  diretório `<REPO>`, stdout no pipe do harness, sem redirecionamento, sem
  prazo de término. `<NONCE32>` só nasce numa proposta revisada e não
  concede permissão.
- Uma execução por nonce, sem retry. Qualquer `PARKED`, desfecho 4/5, ou
  término inesperado bloqueia novos lotes nativos até revisão. Procedimento,
  pré-checagens e comando exato continuam exigindo revisão própria antes de
  qualquer efeito.

## 9. Testes com fakes antes da implementação

Seams: leitura/carga do orquestrador (namespace falso com `run`, `_LIVE`,
`RunError`), `_pause`, `signal.signal`, `os.getpid`/`os.getppid`, captura de
stdout/stderr e espião de sistema de arquivos. Bans atuais mantidos:
`ctypes.WinDLL`, `Popen`, `os.system`, `Thread.start`, leitura sob `.venv`.

- Import puro: nada lido, nenhum handler instalado.
- S0/S1: argumentos inválidos e SHA divergente dão `FINAL` 2 sem namespace,
  sem handler, sem `run`.
- S2: `_LIVE` ausente, não-lista, não vazio, objeto com inspeção que levanta e
  `exec` que falha deixando registro ilegível levam a PARK, nunca a código 2;
  `exec` que falha com `_LIVE` vazio confiável dá 2. `N` e `live` estão em
  `KEEP` antes de qualquer validação.
- S3: falha de instalação ou de escrita do `IDENTITY` com registro vazio dá
  2 e `run` não é chamado; `IDENTITY` precede `run`.
- S4: `run` chamado exatamente uma vez; original guardada por identidade;
  `ACTIVE` verdadeiro só durante a chamada.
- `decide`: tabela completa de desfechos (0/1/2/4/5 e PARK), incluindo
  registro substituído depois da chamada e interrupção com e sem posse.
- `settle`: pegajoso (EXIT depois de PARK continua PARK), rechecagem de
  confiança no momento da saída, `PARKED` emitido uma vez com `parked`
  marcado antes da escrita, escrita quebrada engolida sem mudar a decisão.
- `cycle`: uma pausa; exceções e `BaseException` da pausa engolidas.
- Referências: identidade de `N`, do `live` original e da exceção é conferida
  em `KEEP`; `weakref` só em owners/sentinelas falsos que suportem isso, vivos
  após remover as outras referências e executar `gc.collect()`. Não se
  substituem dict/list exatos por subclasses para facilitar o teste.
- Handler: com `active` levanta `KeyboardInterrupt`; inativo não levanta, não
  escreve e não altera estado.
- Saída: só chaves fechadas; nenhum valor de ambiente fictício, caminho,
  texto de exceção ou PID de filho falso; stderr vazio; nenhum I/O de
  arquivo após `run` em saída ou PARK.
- AST: `_hold` sem `return`/`break`; único `return` de `main` após S2 sob
  `parked` falso; `parked` só atribuído com `True`; sem `traceback`,
  `threading`, temporizadores, prazos ou leitura de stdin; nenhuma chamada a
  métodos de owner fora de `run`.

O revisor conferiu a limitação dos builtins na documentação primária de
[weakref do Python3.11](https://docs.python.org/3.11/library/weakref.html):
dict/list comuns não aceitam referência fraca diretamente. Os testes de
retenção usam identidade dos containers e referências fracas aos objetos
internos apropriados, preservando os tipos exatos do contrato.

## 10. Lacunas e limites remanescentes

1. Sobrevivência do controlador a encerramento do app/sessão, logoff, reboot
   ou término externo não é garantida; resulta em FAILED/UNKNOWN.
2. Relação entre o redirecionador da venv e a Python base (inclusive job
   próprio do redirecionador, se houver) não identificada; a sonda de
   identidade da seção 7 só mapeia PIDs.
3. Entrega de Ctrl+Break e mapeamento de fechamento de console para sinais
   Python não verificados pelo programador.
4. Janelas de poucos bytecodes ao redor de S3/S4.
5. Estacionar mantém viva uma árvore possivelmente ativa até decisão do root;
   o literal benigno limita a própria duração do filho, sem prova.
6. Limites herdados: segunda interrupção no terminate de contenção do backend;
   teto 512 da auditoria (`AUDIT_INVALID`); pin do launcher não atômico;
   leituras implícitas de configuração/site/DLLs/stdlib na partida.
7. Nenhum comportamento de Job Objects foi medido. Native 3 s NOT_MEASURED,
   entry_gate NOT_EVALUATED; controles benignos não liberam admissão real.
   Gateway, B1/B2/D090/C1/SQL e produção seguem abertos.

## 11. Notas de implementação (entrada privada e fakes)

2026-11-02, sob a delegação vigente e revisão do root. Escritos, nesta
ordem: `tests/test_pg16_shell_native_control_entry.py` (primeiro),
`docs/poc/pg16_shell_native_control_entry.py` e esta seção. Nenhum outro
arquivo. Orquestrador b4198fe1, adaptador, backend, chamador, estado de 16
campos e instantâneos inalterados. A entrada nunca foi invocada; nenhum
teste foi executado pelo programador; nada nativo foi medido.

Estado: implementação privada revisada com fakes; medições do root em
`PHASE-9-W1-PG16-SHELL-NATIVE-CONTROL-ENTRY-VALIDATION.md`.
Procedimento, comando exato, nonce e sonda de identidade continuam sem
artefato e exigem revisão própria antes de qualquer efeito.

- Estrutura: `main` faz S0 (argumento) e S1 (`_read_runner`, leitura limitada
  e SHA) como únicas recusas puras; a partir daí `_drive` protege S2–S6.
  `_progress` cria e guarda em `KEEP` o registro de progresso; `_advance` faz
  uma passagem com latches (`loaded`, `captured`, `armed` e
  `_STATE["attempted"]`) marcados antes de cada efeito; após falha ou recusa
  vai direto à decisão. O namespace entra em `KEEP` antes do `exec`; o
  objeto `_LIVE` original entra em `KEEP` na captura, mesmo que o nome seja
  trocado depois; toda `BaseException` vista após S2 também.
- Decisão: `decide` (total) e `settle` (pegajoso, revalida o registro
  original vazio no momento da saída). `CONTROL_HELD`/`CONTROL_RETAINED`
  sempre estacionam, mesmo com lista vazia. Código 0/1 exige descritor com
  `kind`, `scope`, `admission_3s`, três casos com rótulos fechados e desfecho
  coerente; código é `int` exato de um conjunto fechado.
- `_drive` só retorna sob `not parked`, forma EXIT válida e registro
  confiável vazio revalidado; caso contrário estaciona e entra em `_hold`.
  `_hold`/`cycle` sem `return`, `break`, temporizador ou leitura de stdin.
- Handler único `_on_console`, instalado em S3 para SIGINT e SIGBREAK (via
  seam `_install`), levanta `KeyboardInterrupt` só com `active`.
- Seams (apenas módulo da entrada, apenas testes): `_read_runner`,
  `_execute`, `_install`, `_pids`, `_pause`; em caminhos positivos de `main`
  os testes trocam `_hold` por uma armadilha de contagem. O invólucro antigo
  de `_fault` foi removido no fix abaixo; ele não é uma saída da proteção
  de produção. Não há seam `_forever` e o `main` estacionado real não termina.
- Os testes nunca chamam o `run` real; o carregador real é testado só
  executando as definições pinadas. Bans: `ctypes.WinDLL`, `Popen`,
  `os.system`, `Thread.start`, `signal.signal` real, criação de diretório e
  leitura sob `.venv`. O laço infinito real só é verificado por AST.
- Limites desta implementação: a escrita de `FINAL` antes do retorno é feita
  e, se a revalidação seguinte falhar (caso teórico), o processo estaciona
  sem nova linha `PARKED`. Interrupção antes de `_drive` (S0/S1) segue o
  padrão do Python, sem namespace. O código não verifica que o stdout é um
  pipe. Demais lacunas da seção 10 permanecem.

### Achados da revisão da entrada a3620eba (regressões antes da correção)

Entrada inicial rejeitada pelo revisor: fonte
`a3620eba2ce9eb6bb486d3afdb8d17f82f36f2e72471a3ce284abf76175f3056` (14018
bytes) e testes
`2024abc90ef80f7f9b1e2872e8df7b3080e40c11494c381cb64ff66235ad36b8` (26008
bytes), preservados como dados de revisão rejeitada em
`docs/poc/evidence/native-entry-review-20261102`. Medições do revisor: 65
testes próprios aprovados, mypy aprovado, Ruff com 3 erros e 1 problema de
formatação (estilo fica para a rodada de correção); sondas finitas
independentes vermelhas com um P1 e dois P2. Nesta etapa só foram anexadas
regressões aos testes da entrada e estas notas; a fonte da entrada não foi
alterada e nenhum teste foi executado pelo programador.

- P1: se registrar em `KEEP` falha (alocação ou outra falha), `_invoke` perde
  a interrupção original antes de salvá-la no progresso, e o `_fault` sem
  proteção do driver levanta de novo, permitindo saída com owner retido.
  Exigido: original salva no progresso da própria entrada antes de qualquer
  registro falível; `_fault` nunca levanta (falha comum, controle ou
  alocação); estacionamento continua pegajoso se o registro falhar; o catch
  externo do driver só alcança o registrador sob proteção.
- P2 identidade: `_pids` inválido (`None`, `bool`, zero, negativo, acima de
  32 bits, controlador igual ao pai, forma errada) ainda emitia `IDENTITY` e
  chamava `run`. Exigido: recusa `ENTRY_ARM` antes de `IDENTITY` e de `run`;
  limite superior `2**32 - 1` aceito.
- P2 descritor: `scope`/`admission_3s` com igualdade hostil aprovavam.
  Exigido: rótulos que não sejam `str` exato são recusados sem invocar
  igualdade hostil, nunca código 0/1; sem duplicar a validação completa do
  transporte do orquestrador.

Regressões são finitas: sem `main` estacionado nem laço infinito; as
armadilhas dos caminhos positivos de `main` continuam só em testes.

RED medido pelo revisor antes da correção, com a entrada a3620eba
inalterada: 22 falhas e 74 aprovados (0,84 s, saída 1); os 65 casos originais
seguem como prefixo exato. Testes vermelhos
`32c411422b952b9ea7a23ed426b1c735beb6f1ad43f2c5a63c7d84cbf580a088` (33498
bytes) preservados na mesma pasta de revisão.

Correções (só na entrada e nos testes; nenhum teste executado pelo
programador; verde não reivindicado):

- P1: `_invoke` salva `("RAISED", original)` no progresso da entrada antes
  de qualquer registro; o `KEEP.append` extra fica sob proteção e sua falha
  (alocação ou segundo controle) não substitui a original. `_fault` latcheia
  a primeira falha no progresso antes do registro falível e nunca levanta. O
  catch externo de `_drive` chama `_fault` sob `try/except BaseException`.
  `_advance` não retoma passagem interrompida: reentrada sem decisão marca
  `uncertain` e vai direto à decisão (tratada como interrupção); decisão
  concluída fica guardada e é devolvida igual. A reserva `attempted` e a
  referência à lista `_LIVE` original no progresso permanecem.
- P2 identidade: `_arm` valida o par completo (`tuple` de dois `int`
  exatos, `0 < valor < 2**32`, distintos) antes de instalar handlers,
  atribuir `pid`, emitir `IDENTITY` ou chegar a `run`; inválido é
  `ENTRY_ARM`.
- P2 descritor: `kind`, `outcome`, `scope` e `admission_3s` exigem `str`
  exato antes de qualquer comparação; rótulos dos casos já exigiam.
- Testes: estilo corrigido sem supressão (parâmetros esperados agrupados em
  uma tupla, assert longo quebrado, duas assinaturas em uma linha). O
  invólucro de teste de `_fault` foi removido: com o catch protegido ele não
  conseguiria mais escapar, e a produção não foi enfraquecida para isso. A
  armadilha de `_hold` só conta e levanta.
- Limite novo e explícito: uma regressão que estacione um caminho positivo
  de `main` em teste pode travar esse processo; não há timeout automático
  comprovado no harness atual, nem aprovação silenciosa. A lógica segue só por
  unidades finitas. Uma falha comum dentro de `_capture` antes de guardar a
  lista original vira falha da passagem e estaciona se o registro não for
  confiável.
