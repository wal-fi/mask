# W1 Oracle: revisão do desenho do chamador linear

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
