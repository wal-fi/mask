# W1 Oracle: revisão do desenho do chamador linear

## HR5 — direção aceita somente para primeiros oráculos puros

21715 e64205 recuperadas exit0/success,is_error=False,sem denials;mesmo
C2/sessão51ea0d85/claude-opus-5-5/medium. Uma chamada por vez. Root leu
TODAS309linhas da conclusão0f98f8bf e79linhas do delta;depois TODAS378linhas
b6f34c88 e TODOS134linhas do delta. Não se infere reset de cota futuro.

Root juntou apenas117soft-wraps da versão final,sem mudança semântica:
palavras/blocos normalizados,títulos,tabelas,marcadores/indentação de listas
e blocos de código idênticos. Releu TODA versão resultante,261linhas/
19216bytes,7e2308833348e5da336901024fa0ad2efac54dc22602615e72ccabdf28393282.
Não é comparação de AST Markdown. O teto180 era editorial do pedido do
root;aceito este desvio sob delegação para preservar o contrato completo,
sem cortar requisitos ou enfraquecer limites de produto/segurança.

Direção H3 aceita APENAS para criar tests/test_oracle9_w1_host_run.py,
sob TODO este parecer. Não é aprovação de código,nativo ou produto.
A fonte docs/poc/oracle9_w1_host_run.py continua AUSENTE até root ler TODOS
os oráculos e medir/congelar RED. Na sequência correta,o teste surge após
esta revisão;quem permanece ausente durante RED é a fonte. O teste novo
ainda está AUSENTE neste aceite. Não publicar testes parciais como verdes.

Precisões NORMATIVAS para os oráculos e a futura fonte:

- A seam privada tem os inputs já admitidos da assinatura:tupla exata de
  três leitores callable/None,quatro classes de domínio capturadas e
  first_control BaseException/None. Não é nova fronteira genérica de dados
  arbitrários;usar leitores e classes sintéticos próprios nos testes H14.
- A proteção inclui a leitura ÚNICA de audit.fence e suas validações,não
  apenas a chamada ao leitor. Exception nessa leitura -> fence None,
  completeFalse/report_faultTrue;controle -> primeira identidade retida,
  completeFalse,sem bool,sem substituir um controle anterior. Testar os
  dois casos por domínio sintético próprio,sem mexer no produto/SDK.
- report_complete é conjunção de TODAS as validações do relatório,com
  _Snapshots.complete;uma validação de done_outcome/rótulo já reprovada
  nunca volta a True só porque a coleta passou. Um único REPORT fault
  basta;é sempre o PRIMEIRO desse passo,sem perder o controle separado.
- None legítimo em fase não alcançada não é erro. Resultado existente é
  BridgeRunResult exato,Done exato antes de ler outcome,Outcome exato;
  snapshots existentes também seguem seus tipos capturados. Não executar
  getters de DTO de tipo estrangeiro para tentar validar seu conteúdo.
- H9 deve usar uma sequência admitida pelo reator/ponte reais;Done pode
  ser um resultado terminal antecipado diferente de COMPLETE_CANDIDATE.
  Não fabricar CompleteCandidate antes de fatos exigidos de EOF/exit.
  O que prova é a atualização do fence após settle com fato tardio real
  do SDK falso,independente da conclusão de protocolo que o precedeu.
- H14 usa _collect_snapshots REAL do módulo futuro,nunca um guard escrito
  no teste nem monkeypatch de métodos do produto. Relato pós-controle usa
  só as três leituras puras;nenhum seal/clock/efeito subsequente.

Próximo único lote:novo TESTE pelo mesmo C2,Read/Edit/Write somente esse
arquivo,sem comandos. Fonte e TODO código/teste/pin anterior FIXOS. Root
lê TODOS os oráculos antes de QA/RED;nenhuma fonte ou integração antes de
revisão e congelamento. Oráculos só de fakes,sem wrapper/binding real.

148protegidos permanecem fixos.1784PASS do bind são históricos,sem nova
suíte por desenho. N1–N16/T5/B1/B2/D090gate2/C1/D119/TLS/ingressos/produção
seguem OPEN;Gateway indisponível. Nenhum efeito/valor operacional admitido.

## HR4 — conclusão após o horário; fechar só a seam dos oráculos

21715 recuperada exit0/success,is_error=False,sem denials. Tentativa normal
após19h20UTC informado,sem contorno de quota. Root leu TODAS309linhas/
15719bytes da conclusão0f98f8bf e TODOS79linhas do delta. Os148textos
protegidos continuam intactos. Fonte/teste host_run permanecem AUSENTES.

As três correções de HR3 estão presentes. Antes de aceitar os primeiros
oráculos,fechar somente estas precisões do mesmo documento:

1. None por AUSÊNCIA legítima do objeto anterior não é retorno inválido:
   owner ainda não criado -> sem leitura audit/custody;bridge ausente ->
   sem status;run não retornou -> done_outcome=None;fence não selado ->
   None permitido. API de objeto EXISTENTE devolvendo tipo errado/None
   continua REPORT/BOUNDARY e report_complete=False. Não chamar objeto
   inexistente,não produzir falha artificial extra em recusa de bind/input.
2. BridgeRunResult.done é anotado object na API publicada. Para fechar o
   domínio sem getter arbitrário,capturar Done do reator uma vez e exigir
   type(result.done) is Done ANTES de ler outcome;depois Outcome exato.
   Usar apenas DTOs existentes,não uma nova API/getter ou inspeção privada.
3. H14 pede um guard/leitor privado,mas nenhuma assinatura foi fixada.
   Escolher a MENOR seam privada concreta necessária aos testes:fixar nome,
   assinatura,entradas,saídas e lógica de precedência em palavras. O oráculo
   de Exception/controle durante montagem deve chamar essa MESMA seam que
   o futuro run_host usará,sem implementar o guard no próprio teste,sem
   monkeypatch do produto ou segunda máquina de relato. Restringir à
   coleta dos três snapshots e proteção do primeiro controle;sem camada
   genérica/fábrica/porta nova. Se basta um helper simples,apenas esse.
   Não escrever o código ainda. Todo caso usa leitores reais ou sintéticos
   puros próprios,nunca SDK/runtime ou callback de efeito.

A direção linear permanece;sem reabrir o restante já revisto. Root pode
juntar soft-wraps mecanicamente depois com palavras/estrutura idênticas.
Nenhum aceite de fonte,nativo ou produção;sem novo teste/RED até a revisão.

## HR3 — limite após escrita parcial; não retomar antes do horário informado

30974 recuperada:exit1,is_error=True;subtype success NÃO significa entrega
bem-sucedida neste caso. Mensagem do serviço:session limit,resets4:20pm
America/Sao_Paulo. Horário inferido2026-11-13T19:20:00Z,não reset observado.
Não repetir antes dele,nem usar AGY/outra conta/modelo para contornar.

O limite veio DEPOIS de editar:rascunho H3 parcial46545539/14445bytes/
289linhas. Root leu TODAS289linhas;original H2 e nova candidata preservados
localmente. Não afirmar antes-de-editar ou conclusão integral do programador.
Fonte e teste host_run continuam AUSENTES;nenhum RED congelado.

H3 inclui as correções principais de HR2,mas NÃO está aceita para oráculos.
Depois do horário,só o MESMO C2 deve concluir a revisão do MESMO documento:

- Retomar HR2 inteiro e confirmar o rascunho antes de qualquer edição.
- Corrigir §12:"A saída natural0 do T5 é provada" sugere medição já feita.
  O contrato exige que ela SEJA provada no main/driver no container futuro;
  T5 permanece OPEN,não medido neste lote. Kill só pode provar cleanup
  separadamente quando efetivamente observado,não por ser solicitado.
- Esclarecer §9:proibido depois do controle é begin_audit/efeitos,mas as
  leituras puras owner.audit(),owner.custody(),bridge.status() explicitadas
  seguem permitidas e protegidas. Não dizer que todo audit está proibido
  enquanto exige essas mesmas leituras. Nenhum seal/clock na montagem.
- Restaurar os domínios exatos dos campos de relatório tipados object:
  tipo exato capturado de BridgeStatus,WorkFence,AuditReport,CustodyView,
  membro Outcome ou None;documentar que os snapshots são finais e que
  tipos/rótulos inválidos geram BOUNDARY e report_complete=False. Não
  introduzir novos getters,loader ou introspecção de runtime privado.
- Nenhuma promessa sobre falta de memória/controle assíncrono. Fonte e
  testes continuam ausentes;root relê a conclusão inteira antes de oráculos.
- O teto180 não foi atendido. Não estimar como medido;root pode apenas
  juntar soft-wraps após revisão semântica,com prova de palavras/estrutura
  preservadas,sem alterar contrato. Candidata parcial continua só local.

1784verdes e estaticos do bind são históricos,sem repetição por docs.
Todos gates nativos/produto OPEN;sem efeito ou valor operacional.

## HR2 — H2 relida integralmente; correções finais antes de oráculos

81871 terminou0/success,recuparada sem denials. Root leu TODAS265linhas/
13733bytes da H2 9024c3d7. A estimativa170 não era medição; ainda excede
180. Snapshot preservado. Sem novos testes/fonte ou efeitos nativos.

H2 fecha fence após settle,prazos lógicos,disposição finita,controle de
close e escopos distintos. Restam precisões concretas:

1. **seal não é leitura pura antes do primeiro seal.** Owner2401–2407
   chama _now e muda estado. §9 promete apenas leitura pura após controle,
   mas inclui seal; isso pode chamar pump.now DEPOIS do controle ou depois
   de falha de construção. Retirar seal da montagem/fallback do relatório.
   Usar UMA leitura protegida de owner.audit(),e seu campo fence;audit()
   já devolve None se ainda não selado e não consulta relógio. Manter seal
   só na fase explícita normal e refresh após settle. Não nova API.
2. **Admissão exata.** Dizer type(inputs) is HostRunInputs e type(custody)
   is HostCustody,claimed is False exato e demais campos nos valores
   iniciais. Rejeitar custódia alheia/corrompida/usada sem escrevê-la.
   Depois claim antes de input admission. Para cada namespace,exigir
   type(ns) is types.ModuleType antes de vars;capturar janelas e demais
   entradas uma vez,sem releituras após bind. Os pins continuam obrigação
   do loader confiável,já declarada;nenhum loader novo neste lote.
3. **Relato falho é visível e limitado.** Cada leitura de relatório falha
   ordinária produz campo None,report_complete=False E primeiro HostFault
   do passo REPORT,então CLEANUP_FAULT salvo recusa/controle prioritário.
   Não deixar RUN_DONE com report_complete=False. No máximo um fault POR
   PASSO significa conservar o PRIMEIRO na ordem de ocorrência;explicitar
   teto pelo número de HostRunStep,sem perder first_control separado.
   Se já há primeiro controle,nenhuma nova falha/controle da montagem pode
   substituí-lo. Não prometer imunidade física a controle assíncrono/memória.
4. Guardar tipos/defaults explícitos dos campos de HostCustody (None ou
   enum inicial fechado;claimed=False),e definir o conjunto fechado usado
   em category sem depender de uma contagem estimada de strings. Validação
   de rótulos de exceção ordinária fora desses conjuntos -> BOUNDARY.
5. Oráculos: controle ANTES de seal deve montar relato sem seal/clock;
   falha ordinária de REPORT não vira RUN_DONE;custódia com claimed não-bool
   ou campos prévios é recusada sem escrita. Reusar guards sintéticos só
   para falhas de leitura que APIs reais/fakeSDK não conseguem disparar.

Revisar SOMENTE o desenho,sem acrescentar camadas,código ou testes. Root
pode juntar soft-wraps mecanicamente depois,com prova de palavras/marcadores
idênticos,sem significado novo. Não estimar linhas como gate cumprido.
Gates nativos/produto OPEN. Não há oráculos aceitos ou RED de host_run.

## HR1 — primeira proposta lida integralmente; ainda não aceita para testes

2026-11-13.74461 terminou exit0/success e foi recuperada,sem denials.
Root leu TODAS249linhas/12464bytes da H1 d4c58fad. A resposta estimava175
linhas; o teto pedido era180. Snapshot original preservado. Nenhum teste ou
fonte host_run existe. Bind54c5478 e todos os testes/pins seguem fixos.
Os itens abaixo são findings de DESENHO por leitura,não falhas nativas
reproduzidas. Direção linear/reuso aceita; ainda não criar oráculos.

1. **Fence atual depois do settle.** §3 guarda fence do seal ANTES da
   observação tardia e o usa para decidir auditorias DEPOIS. WorkFence é
   snapshot imutável. Reobter fence atual por API pública após settle,
   antes da decisão; especificar também snapshots finais após disposições.
   Não reusar versões anteriores para afirmar quiet. Owner:2401–2459,2631–2657.
2. **Todas as saídas e precedência.** Fechar HostRefusal real do construtor
   do reator (categoria string fechada),PumpFault em now/close,demais
   Exceptions ordinárias de fronteira e retorno inválido do binder/close.
   A tabela atual menciona HOST_REFUSED,mas não trata HostRefusal nem campo
   host_fault; não define falha de pump.close. Preservar primeiro controle
   mesmo se uma leitura de relatório falhar: não deixar montagem do relato
   substituir o controle ou produzir novo efeito. Retenção antes de relançar.
   Nenhuma exceção original/args/texto no relatório e nenhuma cadeia nova.
3. **Relatório fechado exato.** Dar tipos/universos e None de cada campo,
   incluindo stage/faults e owner/host/bridge/pump. pump_closed=True/False
   só se close DEVOLVEU bool exato; nunca chamado ou sem retorno válido
   precisa ser distinguido. closed_handles conta conclusão local confirmada,
   não begin_dispose tentado. RUN_DONE não pode esconder erro de cleanup.
4. **Admissão e custódia antes do bind.** Mapear nomes por namespace,
   ler/snapshot uma única vez e usar as identidades capturadas; loader/pins
   permanecem pré-condição confiável,sem verificação de bytes/runtime aqui.
   Explicar limite entre validação de tipo pré-bind e conteúdo validado por
   construtores existentes depois. HostCustody exata,repr redigido,claim
   one-shot antes da admissão: reuso não altera relato nem objetos anteriores,
   incluindo primeira tentativa recusada por input. Exceção de bind exata
   fica retida; não atribuir estado a uma custódia inválida/alheia.
5. **Prazo lógico não é limite global de parede.** Bind,close e chamadas
   síncronas públicas não preemptíveis NÃO têm teto nativo. Tirar a afirmação
   de total limitado. Para cada fase,calcular deadline uma vez e reutilizar
   begin/settle,sem renovar ao avançar etapas. Explicar limites efetivos de
   registros/disposições: cada begin_dispose também consome max_records e
   max_disposals. Uma passagem sobre snapshot finito,não live-loop crescente.
6. **Relógio grosso.** A recusa honesta sem retry é aceitável neste lote,
   mas não declarar uma nova API como única solução sem a qualificação do
   contrato escolhido. ClockAdapter.poll exige watched tuple NÃO VAZIA
   (owner1510–1530);não inventar empty poll. run_until do pump é público,
   mas usá-lo diretamente exigiria revisar reentrada/posse; este desenho
   pode manter audit_ready=False sem mudar owner ou pressupor prova nativa.
7. **Oráculos proporcionais.** Acrescentar fence que passa de não assentado
   a assentado durante settle,snapshot final atual,falha/controle de close,
   HostRefusal/Exception de construção,retorno inválido,relato falhando após
   primeiro controle e custódia já usada por input inválido. Positivo deve
   exercer APIs reais e fake SDK existentes;sem mutação de módulo/callback
   de produto para fabricar sucesso. Nenhum wrapper nativo executado.
8. Reescrever SOMENTE o desenho em <=180linhas reais legíveis,sem perder
   contratos/limites. Fonte/teste host_run ficam AUSENTES até nova revisão
   integral,posteriores oráculos e RED medido/congelado. Não criar outro
   coordenador,motor genérico,porta ou API de owner/pump.

Não é autorização de efeito nativo,receita,loader/pin operacional ou produto.
N1–N16/T5/B1/B2/D090gate2/C1/D119/TLS/ingressos/produção seguem OPEN.
