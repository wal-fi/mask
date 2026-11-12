# W1 Oracle: requisitos de revisão do adaptador Proactor

## Revisão final da P3: primeiros oráculos apenas — 2026-11-12

Execução17315 recuperada exit0/success, na mesma sessão/modelo/medium,
sem denials. Root leu TODAS773linhas/38724bytes da P3
91178c1cfa0ac2d6e7545dee9af2bba0cec3e77eb6288ea2350633590b20d330.
P1/P2/P3 e seus resultados foram preservados localmente. R1–R7 foram
tratados no desenho; nenhuma implementação ou prova nativa decorre disso.

**Aceite sob delegação:** direção P3 aceita SOMENTE para preparar o
primeiro lote de oráculos com SDK falso, com R8 abaixo NORMATIVO.
Não é aceite de fonte, teste verde, recuperação nativa ou produção.

### R8 — precisões normativas antes de escrever os oráculos

Estas precisões completam o pseudocódigo, sem mudar qualquer API, enum,
owner, teste congelado ou arquitetura:

1. Na primeira leitura válida do relógio, _last_time=None é inicializado;
   não se compara um número a None. A partir daí exige-se monotonicidade.
   O primeiro positivo e os casos de relógio inválido devem exercer isso.
2. Depois da entrega de diferidos e da avaliação de stop, obter tempo NOVO
   e conferir target antes de abrir um segmento. Se o callback diferido
   avançou o relógio até/passando target, não iniciar outra partida nem
   run_forever nessa condução. Acrescentar esse oráculo.
3. Gate OPEN/SPENT/CLOSED rege exclusivamente ADMISSÃO de partida em
   _due/_start. SPENT não suprime os eventos reais do protocolo: started,
   dados, exit, perdas e closed continuam chegando ao owner.
4. A drenagem inicial de diferidos observa somente os que já existiam na
   entrada, limitada por seu tamanho e pelas barreiras de latch/stop.
   Diferido criado durante um callback, inclusive de falha de agendamento
   de filho, fica para a condução seguinte. Nunca entregar fora de run_until.

O primeiro teste deve ler P3 E TODA esta revisão, inclusive R8. Fakes devem
respeitar a fábrica padrão não-eager do SDK3.11.3, callback em lote, pausa
real de leitura e controles por identidade. Não adaptar os oráculos a uma
fonte: o módulo e o novo teste ainda estão ausentes.

**Próximo único lote:** tests/test_oracle9_w1_proactor_pump.py pelo mesmo
Claude2/claude-opus-5-5/medium, Read/Edit/Write só esse teste, sem comandos.
Root lê todos os oráculos antes de medir e congelar RED; fonte só depois.
Ownera5d233ae/testese85f8b53/f86f54aa/15upstream/app124/state16/attempt
continuam fixos. T5 físico/B1/B2/D090gate2/C1/D119/TLS/ingressos/produção
continuam OPEN. Sem efeito nativo/Docker/PG/SQL neste lote.

---

## Revisão integral da P2 — 2026-11-12

Execução3500 recuperada exit0/success, mesma sessão/modelo/medium e sem
denials. Root leu TODAS630linhas/31189bytes da P2
49f00da94443054c06e3f954780df43b3236596064b7eeb8231e4f61aab54c36,
preservada literalmente. R1–R4 têm avanço substancial, inclusive retenção
honesta, close idempotente e EOF pausado. Ainda NÃO aceita para oráculos.
Restam as três precisões abaixo, somente no desenho.

### R5 — identidade de controles e barreiras antes de conduzir

- Todos os testes de latch devem usar identidade contra None, nunca
  `if _ctl` ou `_ctl or _fault`. Uma subclasse de BaseException pode ser
  falsa ou lançar no `__bool__`; o contrato preserva o objeto sem chamar
  sua veracidade. Acrescentar oráculos com esses dois controles.
- O handler só pode tratar como controle uma BaseException que não seja
  Exception. Um inteiro ou objeto em `context["exception"]` não pode entrar
  em `_ctl` e depois produzir TypeError em `raise c`.
- R2-c é irrealizável como escrito: com `type(context) is dict`, um
  override de `context.get` não roda. Manter o tipo exato, testar o dict
  normal com controle, um contexto-subclasse cujo get NÃO é chamado e a
  falha do próprio handler via `loop.stop` roteirizado.
- Depois de `_flush_deferred`, reavaliar latches e stop ANTES de criar
  o próximo segmento/timer ou conduzir o loop. O pseudocódigo atual pode
  entrar em run_forever depois de um controle/fault no evento diferido.
  Acrescentar o oráculo: evento diferido falha/controla; outra partida
  devida não pode começar antes do relato na fronteira.

### R6 — call_at não é uma transação atômica de registro

A frase de S1 "call_at só falha antes do heappush" é mais forte que a fonte:
há o heappush e atribuição/retorno posteriores. A API pública não promete
rollback em qualquer Exception; o seam também precisa poder falhar após
inserir o callback, como já acontece no caso de controle de R3-b.

Fechar o caso Exception após inserção sem deduzir ausência de timer nem
emitir NOT_STARTED falso. Escolher um único contrato conservador: ou a
entrada fica incerta como no controle, ou um gate local irrevogavelmente
fechado garante que callback tardio nunca autorize efeito e sustenta a
entrega diferida de not_started. Esse gate não muda owner/API. Definir
também reuso de record_id e bounds da entrada retida. Oráculos antes/depois
da inserção, para Exception e controle, sem inspecionar heap privado.

O owner fixo não resolve essa ambiguidade sozinho: a autorização de SPAWN
confere gate, selo/controle e prazo; não recusa só por protocolo UNKNOWN.
Assim, não confiar nesse estado como trava implícita de uma partida tardia.

### R7 — documento normativo autocontido e detalhes preservados

A P2 substituiu a P1 inteira, mas diz que API/seam/construtor e mapeamentos
ficam "como na P1", cuja cópia hoje é só evidência local. Reincorporar as
assinaturas e regras normativas necessárias ao documento atual, sem mudar
a API proposta nem reabrir arquitetura. Corrigir também:

- `_gate` chama o seam ident; não afirmar que ele não o chama. Fechar
  Exception/controle dessa consulta de identidade sem vazamento.
- Handle é consultado também dentro dos callbacks do owner (por exemplo,
  started consulta pid/limites). Não aplicar a ele uma proibição de toda
  chamada dentro de run_until.
- connection_made configura stdin só quando stdin_pipe=True. Um helper
  sem stdin não deve falhar por get_pipe_transport(0) ser None.
- Se set_write_buffer_limits falhar, inclusive depois de ajustar os
  valores, o handle deve reportar falha à checagem do owner. Não publicar
  spawn ok apenas porque a releitura deu (0,0). Preservar a regra da P1.

Root não alterou design, testes ou fonte para acomodar essas precisões.
Próximo único lote: mesmo Claude2, somente P3 do desenho; sem novos testes,
fonte, execução ou efeitos nativos. Depois root lê a P3/delta inteiro.

---

## Revisão integral da P1 — 2026-11-12

Claude2 execução81141 terminou exit0/success, na sessão51ea0d85 e no
modelo solicitado Opus5.5/medium, sem permission_denials. Root leu TODAS
as551linhas/30510bytes da proposta f3cba358a6a887bb0b74f9e9a31eeca74724012a59587c70be59d23b11291826.
Cópia literal preservada em c2-design-v1-preserved.md. O relatório do
programador dizia cerca de400linhas; a contagem acima é a medida real.
Contadores de uso cumulativos da sessão não são custo/uso desta chamada.
Nenhum teste ou fonte Proactor foi criado. Não há aprovação para isso.

**Parecer:** direção viável para revisão P2, ainda NÃO aceita para oráculos.
São achados de desenho, não defeitos de implementação reproduzidos.
Manter owner/API/testes congelados, sem nova camada genérica de SO.

### Decisão sobre K1–K6

- K1: reconhecer os efeitos do construtor é correto. Aceita-se documentar,
  prospectivamente, a posse exclusiva do wakeup fd e a precondição confiável
  do chamador. Isso não certifica que o fd anterior esteja livre nem admite
  qualquer chamada nativa agora.
- K2: aceitar os efeitos internos transitórios do SDK, com a precondição
  de não existir loop rodando. A fonte zera o running loop no finally e
  restaura os hooks de asyncgen; não afirmar restauração de um loop anterior.
- K3: direção run_forever/stop e cancelamento só dos próprios TimerHandle
  aceita, condicionada ao fechamento de R1 abaixo. Não cancelar Task/Future.
- K4: distinção entre DISPOSE explícito do owner/pump e cleanup automático
  do SDK aceita. Nenhum automatismo produz prova de liberação.
- K5: intenção de preservar o mesmo controle aceita, mas o algoritmo
  descrito não a implementa em todos os caminhos: R1/R2.
- K6: domínio maior que255 continua limitação explícita do owner fixo.
  Não normalizar códigos nem mudar testes. TerminateProcess usa1 neste SDK,
  mas outros exits podem exigir retenção. Não é gate nativo fechado.

### R1 — contrato executável de run_until e precedência de falhas

P1 §7 contradiz o próprio pseudocódigo:

1. Um controle cru de run_forever atravessa o finally e impede executar
   o raise posterior de self._ctl. A prioridade prometida do primeiro
   controle não está definida no algoritmo.
2. timer.cancel no finally pode substituir um controle já registrado.
   Falha ao obter tempo, avaliar stop ou criar o timer também precisa de
   uma saída fechada, sem perder a primeira identidade e sem cadeia original.
3. Os stop fora do loop no pseudocódigo não passam pela proteção anunciada.
   Separar avaliação do predicado da entrega de evento: a avaliação de stop
   não pode recursivamente chamar o wrapper que volta a avaliar stop.
4. Definir entrada com target já atingido: retornar sem conduzir novos
   callbacks/partidas. Especificar também relógio inválido/regressivo e seam
   que retorna sem tempo/progresso; X11 usa um N não definido.

P2 deve fechar essas transições e a limpeza somente dos timers próprios,
com oráculos para primeira/segunda falha, identidade is e próxima condução.
Não usar cancelamento ou finally destrutivo como prova de cleanup.

### R2 — handler fechado inclusive quando ele próprio falha

O texto "o corpo trivial não levanta" não sustenta X6 nem a promessa de
sigilo. BaseEventLoop.call_exception_handler encaminha BaseException que
não seja KeyboardInterrupt/SystemExit ao handler padrão se o handler
customizado a deixar escapar; esse fallback pode formatar o contexto.
Handle._run também encaminha controles BaseException customizados ao handler.

Definir um handler que não deixe exceção comum ou controle customizado
escapar de volta para esse fallback; preservar o primeiro controle para
relançamento na fronteira de run_until. Não ler/formatar mensagens, argv,
bytes ou repr do contexto nem guardá-lo. Inspecionar somente a identidade
de controle exigida pelo contrato não é permissão para reter o contexto.
Uma falha observada fora de run_until não deve desaparecer quando a próxima
chamada zera self._exc. Fechar latch limitado/precedência e oráculos, sem
instalar logger, warnings filter ou handler global.

### R3 — estados de partida, falhas de agendamento e retenções reais

A tabela não cobre falhas de call_at/create_task nem a coroutine criada
antes de create_task falhar. Fechar quem possui timer, coroutine, Task,
request e protocolo em cada ponto, o que fica registrado e como a próxima
condução/close se comporta. Nada de coroutine abandonada ou falso not_started
depois de um efeito possível. Não inspecionar filas/atributos privados.

P1 §11 diz que argv/exceções originais nunca são retidos pelo pump, mas a
partida adiada necessariamente precisa da receita; request, coroutine e
Task suspensa podem retê-la até além do ponto que zera entry.argv.
Corrigir a afirmação, mapear referências e seu descarte real por fase,
incluindo authorize/closures e exceção de controle cuja identidade é exigida.
Não prometer apagamento de memória, sobrescrever traceback do controle ou
trocar o contrato por um stub. Manter apenas a retenção necessária, com
repr/erros redigidos e bounds claros.

### R4 — recuperação limitada por pausa de leitura

P1 já observa que EOF fica retido quando a leitura está pausada. Fechar a
consequência: owner fixo chama pause_reading ao atingir cap e não chama
resume_reading; matar o filho não garante entregar esse EOF. Portanto o
registro pode nunca alcançar SETTLED_RETAINED, CLOSE_HANDLE pode ser recusado
e pump.close pode continuar False. Também falta uma definição consistente
para segundo close do pump já fechado.

Não mudar owner, testes ou API para esconder isso e não fabricar EOF no
FakeLoop enquanto estiver pausado. Declarar o limite como tal e incluir
oráculo de cap atingido -> exit -> EOF retido -> disposição/close recusados,
separado dos positivos completos abaixo do cap. O plano nativo posterior
precisa tratar esse risco antes de alegar recuperação/produção.

### Fontes primárias adicionais lidas, sem execução

Root obteve anonimamente HTTP200 três textos v3.11.3:

- [events.py](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/events.py):
  Handle._run e controles encaminhados ao handler.
- [windows_utils.py](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/windows_utils.py):
  construção de pipes/Popen e fechamento de handles nas falhas.
- [subprocess.py](https://github.com/python/cpython/blob/v3.11.3/Lib/subprocess.py):
  retenção de Popen/handle e TerminateProcess com código1.

Complementam base_events.call_exception_handler/run_forever e
proactor_events.pause_reading/resume_reading já no pacote. Cópias locais
SDK-events.py.txt, SDK-windows_utils.py.txt e SDK-subprocess.py.txt,
com hashes em public-sdk-supplement.json. Não foram importadas/executadas.
Nenhum efeito nativo ou teste novo foi autorizado por esta leitura.

**Próximo único lote:** o mesmo Claude2 revisa SOMENTE PROACTOR-DESIGN para
P2, lendo esta revisão e os três textos adicionais. Root lê toda a P2/delta
antes de decidir sobre testes. Fontes e oráculos congelados continuam fixos.

---

## Histórico do parecer prévio — antes da P1

2026-11-12. Parecer prévio do root sobre o mapeamento público do SDK.
Não é desenho de implementação aprovado, código ou teste nativo.
`PHASE-9-W1-ORACLE-PROACTOR-DESIGN.md` e o módulo do pump permanecem ausentes.

O pedido Gemini55124 terminou exit 3/RESOURCE_EXHAUSTED 429, sem proposta.
O serviço informou quota individual e espera de 101h10m16s, em torno de
14h07UTC de 12/11. Isso é quota observada; não repetir antes do horário
informado, mudar de conta/modelo ou tratar como o erro anterior de saída.
Claude2 continua com tentativa normal permitida somente depois de
12/11 às23hUTC informado, mesma sessão/modelo/medium. Reset não foi observado.

Atualização posterior: o usuário autorizou explicitamente Flash High e
pediu o mesmo CLI do Argon. A chamada61642 solicitou
`gemini-3.8-flash-high`/high na mesma conversa, PLAN/sandbox, somente com
os mesmos14textos públicos. Terminou exit0, porém o JSON devolveu
`status: ERROR`, `finished_reason: error` e quota individual alcançada.
Não retornou o desenho completo; um link para plano privado não foi lido.
Não houve retry após a recusa, alteração de código ou aprovação de desenho.
O serviço não ecoou o modelo efetivo nem comprovou quotas separadas; não
atribuir os contadores cumulativos da conversa a esta chamada.
Ver `evidence/oracle9-w1-proactor-design-review-20261112/flash-quota.json`.

## Fontes examinadas sem executar

Sete arquivos do projeto foram obtidos anonimamente e comparados aos blobs
Git publicados, junto de sete fontes oficiais CPython `v3.11.3`.
Quatorze textos/499.232 bytes; HTTP200 em todos. Manifesto e hashes locais:
`docs/poc/evidence/oracle9-w1-proactor-design-review-20261112/public-package.json`.
Nenhuma configuração, conversa privada, runtime/binário ou valor operacional.

Referências primárias, fixadas na versão do runtime já medido:

- [Criação pública de subprocesso e task factory](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/base_events.py).
- [Transporte de subprocesso, pipes e callbacks](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/base_subprocess.py).
- [Criação do transporte no Windows](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/windows_events.py).
- [Contratos públicos de transporte](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/transports.py).
- [Contratos públicos de protocolo](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/protocols.py).

A implementação interna foi lida para verificar semântica. Isso não autoriza
o futuro pump a acessar atributos privados do SDK ou a copiá-lo como outro
motor de subprocessos.

## Pontos a fechar no desenho

1. **Cleanup automático do SDK.** `BaseSubprocessTransport.close()` fecha
   pipes e pode matar um filho ainda vivo; `__del__` também chama close.
   `_make_subprocess_transport` do Windows fecha o transporte e aguarda
   sua espera interna após certas falhas. Logo, não afirmar que o SDK
   nunca fecha ou mata em falhas. Separar chamadas explícitas DISPOSE
   iniciadas pelo owner dos efeitos internos observados da biblioteca.
   Qualquer conflito com a redação de PORT-DESIGN §2.3 precisa ser
   apresentado, não resolvido por uma alteração silenciosa do contrato.

2. **Janela de partida sem observabilidade.** A criação do processo precede
   a conexão dos pipes. Uma falha antes de `connection_made` pode não expor
   transporte à superfície pública do protocolo. Falta de handle não prova
   NOT_STARTED ou recolhimento físico. Explicar a posse da tentativa,
   UNKNOWN/retido e os fatos que efetivamente permitem recuperação, sem
   fingir sucesso nem tornar todos os casos normais UNKNOWN.

3. **Ordem real e publicação única.** `_connect_pipes` agenda
   `connection_made` e os callbacks pendentes antes de concluir seu waiter.
   A proposta deve tratar essa ordem, falha após aquisição de transporte,
   exit separado de perda dos pipes e falha de startup na mesma rodada.
   Preservar a publicação única do owner, os resultados já observados e a
   retenção de fatos tardios. Não criar um segundo motor de protocolo.

4. **Loop exclusivo e limites de condução.** Preservar §2.3: nenhuma
   alteração de política/global event loop, task factory padrão e loop
   nunca exposto. Fechar `now/schedule_start/run_until` e o momento exato
   de authorize anterior ao efeito. Schedule é inerte. Reavaliar stop e
   o prazo sem callbacks externos ao período controlado, sem busy loop,
   tarefas abandonadas ou cancelamento usado como atestado de cleanup.

5. **Prazos por operação.** Não regredir os quatro casos já medidos:
   handoff tardio, data tardia, EOF tardio e write síncrono que atravessa
   o prazo. O startup concluído não limita a vida da sessão. Eventos usam
   tempo atual, o resultado vencido permanece imutável e bytes retidos
   pertencem ao owner até uma nova leitura válida ou disposição explícita.

6. **Posse e memória limitadas.** Explicar quem mantém cada Task, timer,
   transporte, protocolo e callback pendente. A liberação não pode depender
   de GC, variável global ou de supor que alguém já observou o outcome.
   Mapear as filas e o overhead do SDK sem confundi-los com o teto de bytes
   copiados pelo owner. Não inventar prova nativa pelo walker dos fakes.

7. **Diagnósticos e exceções.** O código do SDK tem caminhos de diagnóstico
   e handler de exceções. A proposta deve fechar configuração de debug e
   tratamento de erros sem registrar argv, bytes ou mensagens originais.
   Preservar a primeira identidade de controle BaseException e categorias
   públicas fechadas, sem cadeia/contexto original. Explicar falha do
   próprio handler e consumo de exceção de Task, sem cleanup implícito
   adicionado pelo pump aos handlers de erro.

8. **Disposição e encerramento.** `is_closing`, buffer zero e callback de
   conexão perdida são observações diferentes. A assinatura de close/kill
   não pode virar quitação física imediata. Fechar a ordem de encerramento
   do loop e a resposta ao término incompleto mantendo posse/capacidade
   coerentes; nenhuma liberação sobre recurso ainda incerto.

9. **Seam mínimo de teste.** Definir a menor superfície tipada específica
   para testar esses fatos com SDK falso, sem criar loop, thread, processo,
   socket ou DLL reais. Exigir caminhos positivos completos e adversariais,
   inclusive falha antes/depois de aquisição, dados/exit/EOF em ordens
   diferentes, erro no transporte, controle e filas saturadas. Isso não
   substitui o adaptador funcional nem é prova nativa. Não alterar owner,
   testes congelados, DTOs/enums ou APIs aceitas para facilitar o binding.

## Ordem da continuação e limites de evidência

Primeiro, o programador devolve somente o desenho concreto e a matriz
determinística. Root lê toda proposta e deltas antes de adotar. Depois vêm
oráculos novos revistos e RED medido; somente então fonte própria. O módulo
Proactor não deve aparecer antes dessa sequência. Não executar o SDK
baixado, importar módulos para experimentar efeitos ou inventar valores
operacionais neste lote.

As futuras provas nativas precisam medir a ordem dos callbacks, efeito de
buffer zero, fechamento/recolhimento e posse por identidade na versão real,
com o plano e o destino explicitamente admitidos. Não são satisfeitas por
bools True, fake OS, exit de um wrapper ou mera ausência de mensagem.

Owner `a5d233ae`, testes `e85f8b53/f86f54aa`, ponte/host/driver/core,
aplicação124, estado16 e tentativa consumida permanecem fixos. Os 1.604
testes e quatro probes do incremento anterior são históricos, não novos
testes deste documento. T5 físico/B-1/B-2/D-090 gate2/C1/D119/TLS/ingressos/
produção continuam abertos; Gateway indisponível.
