# W1 Oracle: pré-revisão da ponte duplex

2026-11-10. Root revisor, sob delegação; desenho apenas. CODE7ecf056 publicado,
checkpoint documental cad2edf. HostReactor e86f8e32/teste f177102a imutáveis.
1215 relacionados/366 próprios/18sondas verdes são históricos: nenhum gate
nativo/produto fechado e nenhuma suíte repetida por esta leitura.

## Lote e autoria

Somente proposta docs/PHASE-9-W1-ORACLE-DUPLEX-DESIGN.md, antes de testes/
fonte/efeitos. Claude2 sessão51ea0d85/claude-opus-5-5/medium retornou429 na
CLI65449 antes de editar. Reset informado19h30SP/22h30UTC10/11, não observado.
Usuário autorizou fallback Gemini ArgonHigh/Flash3.8High com pacotes públicos
necessários. Fallback agora é planejamento readonly com cópias isoladas; não
muda conta/modelo do Claude2 nem lê conversas/credenciais privadas. Não é
recuperação da UI que teve aprovação expirada antes. Nenhum conteúdo desse
outro contexto é exportado. Só um agente ativo de cada vez.

## Reuso e contrato que a proposta precisa fechar

- HostReactor síncrono puro é o único decisor de frames/ações. Sem outra
  máquina concorrente que reproduza sequência, verdict ou cercaT6.
- ManagedBootstrap é referência de conceitos, não import reutilizável: wire,
  limits e pins antigos. NATIVE-PLAN histórico diz256linhas, mas fonte e86/
  desenho posterior exigem56 e512bytes incluindoLF. Exceção do teto57 antes
  de ORDER permanece. Não editar esses arquivos congelados.
- API mínima da ponte específica, owner caller forte/uso único e slots antes
  de efeitos. Sem SO genérico/novo sistema de proveniência. Primeiro módulo
  e testes devem funcionar com portas determinísticas falsas, sem criar loop
  nativo, socket, thread, processo, guard ou sinal de verdade.
- Referências do spawn, processo, pipes, leitor, writer e ações pendentes
  permanecem retidas. Cancel/timeout/kill/CLIexit não demonstram fechamento.
  Erro fechado não equivale a cleanup. Primeiro BaseException de controle
  é preservado, sem perder referências ou executar efeitos ocultos.
- Stdout drenado enquanto stdin/action espera, limites durante leitura e
  fila finita. Uma linha parcial/EOF/flood precisa domínio fechado, sem
  acumular antes de conferir, bloquear pipe ou descartar prova como sucesso.
- Serialização é concreta: não alimentar Line/Exited durante write/action
  pendente e depois entregar Delivered.pre antigo. Primeiro recibo do efeito,
  depois bytes já enfileirados com tempo pós-observação do owner. Fila FIFO
  finita, não timestamp do pump; não retrodatação. Se operação continua viva
  ao deadline, UNKNOWN e retenção explícita, nunca falso recibo completo.
- Só seis ActKind existentes e facts após o efeito completo. Nenhum executor
  arbitrário de comando/SQL. T6killOK deve anteceder Exited; ZERO25 somente
  após EOF/reap alegados. Resultado candidato não autoriza limpeza física.
- Tudo operacional (argv/comando/root/nonce/estado/CIDs/rede/credenciais/PG,
  perfil/margens/pins de runtime) permanece NOT_PREPARED. Não ler ambiente,
  config, runtime/binários/privados. Estado16/attempt consumido intactos.

## Verificação primária das semânticas, sem executar runtime

Consultadas as páginas oficiais Python3.11 em10/11/2026 (publicadas como
3.11.18); não é certificação do CPython3.11.3 instalado nem dos seus handles:

- [Subprocesses](https://docs.python.org/3.11/library/asyncio-subprocess.html):
  wait pode travar com pipes cheios; communicate acumula saída na memória.
  limit do StreamReader não é prova de teto global de memória/saída.
- [Tasks](https://docs.python.org/3.11/library/asyncio-task.html): wait_for
  aguarda cancelamento e pode exceder seu timeout. Guardar referência forte
  das tasks; cancelamento não prova término ou ausência do processo/efeito.
- [Streams](https://docs.python.org/3.11/library/asyncio-stream.html): drain
  controla buffer local; não é confirmação do container. is_closing não
  distingue fechamento concluído. wait_closed pode envolver flush pendente.

A futura proposta precisa dizer qual porta garante retorno/limite e qual
parte fica retida quando o SO/loop não coopera. Nenhum timeout absoluto
mágico ou Bool de fake apresentado como prova nativa.

## Próximos oráculos esperados

Transcript com queue/timestamps; writes curtos/não leitor/timeout; flood e
linha parcial/EOF; falha após cada reserva/start; ação desconhecida viva;
killreceipt antes de Exited; terminaldrain/refusal; controle original e dono
retido; só cleanup comprovado limpa slot. Plano define os alvos e ordem
RED antes de fonte, sem executar nada neste lote.

## Revisão integral V1 Gemini — ainda não aceita para testes

AGY48746 terminou0/SUCCESS em371,219s, terminal recuperado; conversa
85368f37-6b19-40f7-b51c-97e9180f4566. Root leu toda a proposta (pin/tamanho
em proposal-v1-review-meta.json); dez cópias públicas intactas. Nenhum teste/
fonte foi criado. O arquivo definitivo DUPLEX-DESIGN segue ausente.

R1 — posse antes de efeitos não está fechada. spawn()/read_stdout()/
write_stdin()/execute() retornam TaskHandle já agendado, só depois entra em
_tasks. Uma exceção após alocar/agendar mas antes de retornar deixa recurso
fora do owner. Declarar retained não conserva referência inexistente. Fechar
porta específica reserve/bind/start (slot original antes de chamar efeito),
ou begin_into(slot) que publica a operação inerte antes de iniciar. Aplicar
também a read/wait/action/write. Slot ocupado nunca é sobrescrito. Resultado
tardio de spawn/processo precisa adoção antes de limpar handle concluído;
Task.done/cancel não demonstra efeito quieto. Sem SO genérico novo.

R2 — cortar cleanup deste primeiro incremento. BridgeQuiesced/Absent/nonce,
issue_ticket e quiesce/close/assert_released replicam prova/gerador que era
lote futuro. Matriz quiesce cancela act depois de matar gateway e considera
done suficiente, sem provar quiescência da ação PG/helper/daemon. Constructor
externo fabrica BridgeAbsent com ticket original sem atestado real de
ausência. Remover essas APIs/tickets/geração de nonce deste desenho mínimo.
Bridge é dono retido pelo chamador ANTES de run; conserva todos slots, não
fornece released/cleanupOK nem elimina pendência incerta. Done só candidato
de protocolo. Cleanup/ausência física será contrato separado antes de ligar
SO real. Não trocar cancelamento por outro bool fake de prova.

R3 — limites/pump contraditórios. D3 promete continuar drenando >32768, mas
5.2 manda parar no teto. Fila57 não tem check central antes de cada append
(inclusive EOF parcial). (_partial_buf+seg)[:513] aloca primeiro até4609B.
Contador sobe por bloco4096 acima do teto antes de verificar. Escolher uma
única regra finita e verificável: cap de bytes admitidos + uma observação
de overflow, read_size=min(chunk, remaining+1), enqueue central com57slots,
partial<=512 +1byte somente diagnóstico sem concat grande. Ao teto, falha
fechada/HELD, slots conservados; não promete dreno infinito nem pipe sempre
livre depois de HELD. Nenhum sucesso/limpeza nessa parada. Alternativa de
descarte deve ter byte/tempo finitos explícitos e admitir retenção quando
esses limites acabam. Teto56/57 do reator continua imutável.

R4 — API incompleta: WakeEvent, ActResult e WaitOutcome não são definidos
(no último há só menção); TaskHandle done/result/exception/cancel não fecha
registro/obtenção da operação antes de efeito. Reuso direto por import de
docs.poc pode depender de resolução de path fora do pin. Fechar DTOs, campos,
nomes/enums exatos e erro args/category/context. Preferir ponte síncrona com
um wait/poll específico de portas injetadas que avança relógio falso sem
loop nativo, ou definir exatamente async falso sem asyncio.run/loop/socket
nativo. Sem motor genérico de eventos. Receber namespace confiável do reator
já carregado/pinado pelo chamador e instância fresca correspondente; forma
não autentica origem. Não criar loader/import executor automático.

R5 — prazo global e janela terminal. ActPort.execute(act) não recebe o
effective_deadline que a ponte usa. Retorno após overall mas antes do
deadline original pode gerar reciboOK/SENT que ainda avança o reator. Toda
porta recebe deadline efetivo; se overall venceu, recusa OVERALL_DEADLINE
sem alimentar sucesso no reator, conserva original/observação verdadeira
no owner (não inventa UNKNOWN se a conclusão foi conhecida). Deadline de
dreno captura UMA vez na primeira transição DRAINING/ENDING/aguardarExitT6,
não se renova por linha/wakeup. Silêncio não se renova por wake espúrio.
posttime sempre observado pelo owner; nenhum timestamp retrodatado.

R6 — escrita e efeitos incertos. Exceção depois de invocar uma porta não
prova zero bytes; só resultado fechado de porta confiável prova NOT_SENT.
Definir count/status/complete local e seus domínios, sempre deadline/post
conferidos; sem retry de payload. Operação que vence prazo mas permanece
viva fica em slot original retido, não gera nova operação no mesmo slot.
UNKNOWN é o recibo legítimo dessa observação, não confirmação do efeito.
Fatos tardios não viram um segundo recibo nem novo frame. O primeiro fault
e o primeiro BaseException de controle precisam regra explícita pegajosa;
relança mesma instância e não inicia I/O oculto em finally.

Mantidos/aceitos prospectivamente: filas de raw sem timestamps; recibo antes
de Line/Exited; cercaT6 do reator; seis ações fechadas e falta de prontidão
nativa. Entretanto, ordenação de mensagens não prova causalidade do kill
nativo: ActPort deve provar a identidade/efeito próprio no lote nativo.
Uma CLI gateway persistente é distinta de helpers futuros de ações, que
terão seu próprio owner; não alegar que matar gateway encerra esses efeitos.

Pedir somente V2 documental curta (aprox250–350linhas), sem primeiroteste
ainda. Modelo real de transporte/projeto/runtime permanece NOT_PREPARED.
Nenhuma alteração nas fontes/testes ou descarte do históricoV1.

## V2 inteira relida: fechamento pequeno R7 antes de testes

AGY99723 recuperada0/SUCCESS em221,141s;12cópias públicas intactas. Root
leu todaV2 (pin/bytes/linhas em proposal-v2-review-meta.json). Direção de
ponte síncrona/sem cleanup, begin_into e fila finita aceita prospectivamente;
API/ordem de execução ainda precisam as precisões abaixo. Nenhum teste/fonte.

R7.1 — Slot consumido não é slot quieto. Definir exatamente a colheita uma
vez (cache do outcome OU erro original antes de qualquer validação). Nomear
o método PRIVADO da ponte que libera _op só após resultado conhecido válido
colhido. Fake/porta não limpam slot. UNKNOWN/erro/failure parcial retêm op
original e observação em cache, mesmo done=True; não chamar outcome() duas
vezes. Não incluir operação já reportada/quarentenada no conjunto de espera,
senão poll retorna imediatamente para sempre com done=True. status() é
leitura pura de observações em cache: não chama done/outcome/clock/portas nem
colhe spawn tardio. Se spawn retornar processo mesmo ok=False, reter/adotar
referência antes de recusar; erro com processo alocado fica no op original.
Controle original não pode ser substituído por uma nova falha ao colher
spawn no handler: só adotar observação JÁ em cache ali, sem callbacks novos.

R7.2 — Portas de espera/leitura. Assinatura explícita
ClockPort.poll(watched: tuple[OperationSlot,...], deadline: float) -> float;
observa só slots ainda não reportados. Contrato retorna por NOVA conclusão
ou deadline atingido; retorno sem progresso (mesmo tempo, sem nova conclusão)
dá PORT, nunca busyloop/rebase. begin_read_into(slot,max_bytes,deadline)
recebe overall_deadline, coerente com R5. Clock/portas são contratos confiáveis
de lógica; fake não mede preempção/latência do SO. _attempt_consumed é
marcado ANTES da primeira chamada de clock/porta em run, não depois.

R7.3 — Falta o algoritmo normativo de Wait/EOF/saída. Acrescentar passos
concretos do loop, sem segunda máquina do protocolo: adotar spawn; armar
read e wait nos slots originais; a cada poll colher read/wait em cache e
enfileirar bytes/EOF enquanto write/action ainda aguarda; reagendar SOMENTE
read com outcome conhecido consumido. Nunca alimentar linha/Exited antes
do recibo ativo. Quando não há efeito ativo, consumir filaFIFO antes de
Exited; EOF verdadeiro com parcial entra na fila (não vira sucesso).

Se existe resultado validado de waitEXITED, guardar code/reaped e continuar
leitura até EOF ou primeiro drain_deadline (sem renovar). Se EOF veio mas
wait não completou, drenar/aguardar até mesmo deadline. No final, alimentar
Exited com fatos reais em cache: EXITED/code/reaped com eof real mesmo falso;
NO_EXIT apenas quando a porta prova processo ainda vivo, UNKNOWN quando
faltam fatos. Não inferir NO_EXIT só por taskwait pendente. Definir como
observar vivo no WaitOutcome da porta (statusNO_EXIT retornado ao deadline)
ou fechar UNKNOWN conservador; não fabricar prova. Em dreno vencido sem
prova, UNKNOWN; em overall vencido, OVERALL_DEADLINE antes de qualquerfeed.

Antes de iniciar NOVO efeito Send/Act, se EOF/saída já está em cache e não
há operação nativa ativa, entregar Exited conservador e deixar o reator
transformar pending em orphan, sem executar efeito desnecessário/fabricar
NOT_SENT. Se efeito já começou, recibo primeiro como contrato existente.
Após killOK T6 e wait/EOF positivos, Exited gera ZERO25; esse efeito ainda
precisa executar mesmo com saída/EOF já conhecidos. Essa é a exceção de
ZERO25 já emitido pelo Exited, não novo comando para processo morto.
Se há pending nativo desconhecido, preservar slot e nunca novo mesmo papel.

R7.4 — Pequenas precisões fechadas. §5.2.3 não pode abrir exceção de feed
após overall para operação que alega ter concluído antes: só tempo observado
do owner governa; observaragora>=overall recusa sempre antes de sucesso.
Definir validação de ActOutcome antes de liberar slot; facts/status errados
ficam retidos e dão erro fechado (coerência fica no HostReactor). Redigir
repr também de SlotView/SpawnOutcome/WriteOutcome/ActOutcome/WaitOutcome/
BridgeRunResult porque carriers aceitam objetos arbitrários, sem invocar
repr do op/processo/dado bruto. Declarar freshverdicts NOT_RUN25/exatidão
dos contadores no binding. Corrigir indentação ReadOutcome e typo _ slots.

A nova seção deve bastar para oráculos D1–D6 sem impor atributo privado
arbitrário ao código. Estado de operações em cache/one-shot é do bridge,
não outra máquina que calcule protocolo. Cleanup continua fora; nenhuma
API de liberação nasce. Valores de DuplexBudget são domínio prospectivo de
testes; não alegar que300s de freshness é limite nativo medido da rodada.
Root relerá todo delta/V3 antes de aceitar os primeiros testes.

## Parecer final: direção aceita para primeiros testes, com R8 normativo

AGY44702 recuperada0/SUCCESS em206,297s;14cópias públicas intactas, zero
escritor confirmado. Root leu TODA a V3, além das V1/V2 inteiras. Pin da
proposta em final-design-review.json. Sob delegação, aceita SOMENTE para
os primeiros testes D1–D6 após as precisões normativas abaixo. Não é
aprovação individual do usuário nem certificação da ponte nativa.

R8 prevalece sobre exemplos abreviados ou contraditórios da V3:

1. Repr: os exemplos que acessam .name de enum estrangeiro ou !r de fields
arbitrários NÃO são implementação normativa. Todos os DTOs/carriers/vistas
podem usar repr constante Class(<redacted>), sem callback/atributo de valor
injetado, inclusive DuplexBudget e SlotView. Não invocar repr/str de op,
process, facts ou enum estrangeiro. Testar com objetos sentinela que falham
se inspecionados. É o mesmo invariante de sigilo, sem mudar campos públicos.
2. Colheita: outcome() é no máximo UMA vez por operação concluída. done()
pode repetir ENQUANTO pendente, nunca depois de harvest/quarentena, nem em
status. O texto D1 'done/outcome uma única vez' não proíbe polling de done
ainda pendente. Cache guarda o primeiro outcome/erro antes de validação.
3. poll: capturar old_now ANTES da chamada. Retorno deve ser finito/exato/
>=old_now, podendo exceder deadline real (não há preempção garantida). Se
não há NOVA conclusão e returned_now < deadline, recusar PORT mesmo se o
clock avançou um pouco; a porta deve aguardar conclusão ou deadline, sem
wakeup espúrio público. Não comparar com last_clock já atualizado. Se não
houver slot elegível, não chamar poll com tupla vazia: usar fatos em cache
para dreno/Exited ou recusar PORT/HELD se nada permite progresso, sem loop.
4. Dreno pré-efeito: condição é ausência de operação NATIVA ativa, não
pending=None no modelo. Se EOF/saída já estão em cache antes de iniciar
Send/Act, alimentar TODOS os raw em FIFO antes de Exited, mesmo que exista
pending do reator: ABORT/TERMINAL usam a exceção já implementada e preservam
orphan; qualquer outra linha vai ao reator e pode recusar ORDER. Não pular
linhas para obter Done. Não há parser paralelo na ponte. ZERO25 solicitado
pelo Exited positivo segue como exceção explícita e ainda executa.
5. Prazo global: checar no tempo observado ANTES de todo feed e ANTES de
qualquer início de efeito. Se >=overall, guardar observações verdadeiras,
recusar OVERALL_DEADLINE e manter pending/slots, sem exceção para alegação
de término anterior. Nenhum sucesso tardio, timestamp retrodatado ou retry.
6. Construtor: binding fresco com tipos exatos, tuple de25NOT_RUN e counts
int exatos; orçamento tipoDuplexBudget,4campos int/float exatos finitos
(OverflowError fechado),0<spawn<=30,0<silence<=60,0<drain<=30 e
max(spawn,silence,drain)<overall<=300. Portas têm métodos callable exigidos.
REACTOR/BUDGET/PORT fechados antes de I/O. Domínios são de teste prospectivo;
nenhum perfil operacional fixado ou runtime nativo medido.
7. Primeira falha é pegajosa. Toda exceção de porta/slot marca retenção e
fault antes de recusa fechada fora de handler, sem mensagem/cause/context.
Categoria de reactor_refusal pertence à lista fechada do HostReactor, não
a um str arbitrário copiado. Primeiro controle BaseException fica retido
por identidade, é relançado intacto e não dispara callbacks novos no handler.

Essas precisões são de root/revisão sob delegação; a proposta V3 é do Gemini.
Próximo somente tests/test_oracle9_w1_duplex_bridge.py pelo programador
autorizado, primeiro ler todos os oráculos e medir/congelar RED antes da
fonte. A tarefa confirmada19h35SP volta a mesma sessãoC2/modelo/medium após
22h30UTC informado, verificando estado/zero escritor. Não repetir antes,
nem iniciar conta/escritor paralelo.

Fonte/testes/app124/estado16/attempt intactos,1215verdes históricos. Validação
deste lote é documental (diff/hashes/JSON/revisão de API), não nova suíte ou
prova de SO. T5físico/B1/B2/D090gate2/C1/TLS/ingressos/produção abertos.
