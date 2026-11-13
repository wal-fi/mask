# W1 Oracle: revisão do desenho do chamador linear

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
