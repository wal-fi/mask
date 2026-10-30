# Entrada do ensaio público do leitor PG16 — proposta técnica

2026-10-30, sob delegação vigente. Host8c41605f aceito61196 e publicado em
c5cacc2;52próprios/304relacionados aprovados. Este texto não cria entrada,
root, estado ou comando operacional e não inicia Docker/CLI/shell/PG.

## Fonte e admissão

Criar variante fonte explícita `pg16_shell_run.py`, sem editar/monkeypatchar
o run públicoa608 consumido. Capturar Host8c41605f por SHA e executar só
definições. Não herdar main/drive de outro ensaio. Import continua sem efeito
nativo. Runtime da futura entrada: Windows/Python3.11.3/Proactor, -I/-B e
optimize0, mesmos pins de stdlib/canal; uma raiz Temp nova e uma tentativa.

Admissão fecha esquema/canonicalidade/tipos do estado; task32hex, fontes/
imagem/medidas dos23creates e delivery_plan exatos. Incluir pins transientes
e transitivos efetivamente usados (reader/owner/channel/perfil-base, host,
V2/original e dependências), sem inferir que SHA do módulo superior cobre a
imutabilidade dos arquivos inferiores depois do import. Validar root e seus
pais contra symlink/reparse; parent exato do Temp conhecido e conteúdo inicial
somente attempt.json. Não aceitar root/estado anterior ou recuperar a invocação
do ensaio consumido. Estado máximo32768bytes escolhido antes da materialização;
medir tamanho canônico no preparador antes da proposta. Nenhum input privado.

Preparo chama constructor do Host e pins puros, confere stdlib e blueprints,
e grava invoked.json XB/fsync antes de marcar attempt INVOKED. Colisão recusa;
não repetir main nessa raiz. Manter alvo de admissão3s do ensaio anterior;
excesso reprova antes de A, sem ampliar depois. Os23Watchdogs ainda só serão
construídos em run/start_supervision, antes de start_cycle/A. Falhas antes de
gravar INVOKED não executam A e não são motivo para apagar/reciclar a raiz.

## Execução e diagnóstico

Context mantém Host/estado/loop e flags de interrupção/released/held. Sequência
única: start_supervision → foreground(start_cycle) → replay12checkpoints →
perform_b → coleta → joins → restauração → pins finais → resultado terminal.
Na fase A o foreground é atribuído explicitamente ao primeiro monitor/case,
para seu callback poder cancelar esse startup; depois cada caso usa o vínculo
próprio já implementado no host. Não repontar heartbeat nem callback antigo.

Erros de fora viram categorias fechadas sem str/repr/traceback/argv/ambiente.
Reconhecer classes exatas dos namespaces capturados do Host, incluindo
ReaderError do parser e as classes fechadas do canal/perfil/volumes/identidade.
BootstrapError só com enum próprio, argumentos consistentes e valor permitido.
Classificar namespaces frescos do bounded para PowerShell/clock somente pela
identidade dos code objects + globals dos callers fixados (`Host._bounded` e
clock.sample), self do Host quando aplicável e classe HostFault daquele helper;
filename/module-name iguais não são prova. Unknown/subclasse/objeto hostil
fica INTERNAL. RuntimeCodes somente literais enumerados; não exportar erro
original. O novo invoke/TCB não é o invoke antigo4bc para esse reconhecimento.

## Recursos, cancelamento e HELD

Não usar asyncio.run no driver nativo. Um único Proactor loop próprio é
mantido enquanto houver foreground, CLI, owner, task ou thread pendente.
Interrupção não fecha loop nem lança limpeza paralela/segundo escritor. Root
pendente continua no mesmo loop; cancelar o foreground efetivamente ativo
quando apropriado, sem dar ack ao monitor errado. Flag de interrupção é sticky
e impede passe mesmo se a coleta posterior for comprovada.

Após falha, tentar recolher os mesmos records. Se a emergência do monitor
disparado estiver com o mutex e a primeira coleta falhar, aguardar close/join
desse monitor, confirmar coleta da thread e tentar cleanup novamente uma vez.
Não criar CID novo nem repetir B; não limpar paralelamente ao watchdog. Se
monitor normal ainda protege recurso vivo e não há emergência/join positivo,
não removê-lo só para liberar o mutex: reter contexto/loop em HELD.

Join-ready distingue tarefas heartbeat das demais e inspeciona todos owners/
monitores, não o último. Falhas independentes de evidence/heartbeat não impedem
as outras tentativas de stop/join. Erros podem ser resolvidos numa tentativa
posterior com prova positiva, mas o finding/resultado original continua no
histórico e o lote não passa por isso. SUPERVISION_HELD bloqueia a conclusão
até prova física; nunca é interpretado como sucesso. Fired é verificado
separadamente nos resultados cacheados, não por _supervision_errors vazio.

Só restaurar Desktop após todos recursos próprios/threads iniciadas coletados,
CLI sem cleanup incerto, CIDs/volumes reconciliados e boot/identidade iguais.
Prazo excedido reprova e não dispensa restauração segura. Sem positivo físico,
HELD retém Host/loop e evidencia categoria fechada; nenhuma exportação ou
outra rodada. Uma falha de preparo antes de chamar start_cycle pode registrar
Desktop UNTOUCHED_PRE_A apenas após provar ausência de efeito externo e coleta
das threads locais. Depois que start_cycle entrou, initial_active desconhecido
não vira OFF por suposição. A entrada futura precisa testar esses limites.

Passa só com23casos na ordem exata, relatório e inspect ligados, todos monitores
iniciados/joined/nofire/noheld, tarefas/owners/CLI recolhidos, inventários e
Desktop restaurados, fontes inalteradas e journal revalidado. Nenhum erro de
falha/coleta/restore/interrupção/deadline pode sumir do resultado para converter
o lote. Terminal persiste estado/result e só libera contexto após confirmação;
falha ao persistir mantém HELD em vez de imprimir sucesso.

## Orçamento: gate anterior à proposta nativa

P2-4 de29625/59784/61196 permanece aberto. seconds de CLI não incluem pins.
Antes de qualquer proposta que inicie A, medir leitura/hash das fontes e dos
três executáveis em cada pins (inclusive cleanup), em diagnóstico público
somente leitura revisado, sem invocar os executáveis ou escrever raiz do ensaio.
Registrar amostras/conteúdo identificado por hash e custo total, sem caminhos/
configuração privados ou prometer estabilidade de cache/tempo do filesystem.

Projetar os23casos, contagem de CLIs/pins explícitos,3WAIT≥24s e custo máximo
individual owner12s/shell8s. Os tempos T4 medidos são insumo parcial, não prova
do reader/PG. B300 é fail-closed para duração típica e não soma de todos piores
casos. Primeira execução dos23casos só pode ser medida depois da proposta;
logo, antes dela existe estimativa explícita, jamais medição nativa inventada.
Se a revisão exigir medição do total real prévio, será preciso aceitar um
plano diagnóstico próprio de casos reduzidos antes da matriz, ou manter o
gate bloqueado; não circularmente declarar o total já comprovado.

Não aumentar owner12/shell8/watch600 nem repetir/ampliar depois de falha. A
justificativa pode manterB300 com margem típica mensurada ou propor revisão
prospectiva separada, preservando limite e resultado da fonte anterior. Sem
evidência suficiente, a entrada pode existir/testar com fakes, mas não é invocada.

## Gates do código futuro

Fakes: admissão/colisão/canonicalidade/pins; diagnósticos e subclasses hostis;
pre-A falho sem daemon acionado; cancelamento em A/B/coleta/join/restore; mutex
da emergência e segunda coleta dos mesmos records; monitor/owner/CLI incertos;
heartbeat cancelado vs foreground cancelado; fired com erros resolvidos;
23evidências e todos monitores; fonte alterada após B; terminal persistência;
driver não fecha loop com tarefa pendente e não reinicia B após interrupção.

Depois: exportador recursivo por projeção com23pastas fechadas e sem links,
orçamento diagnóstico, preparador/proposta/script/pins e revisão de uma única
rodada. Nenhum servidor/initdb/SQL/secret/worker/Gateway. B1/B2/D090/C1 e
produção continuam abertos. Perfil Oracle621 segue inalterado e indisponível
como serviço. Nenhum job/quota observado ou segundo escritor.

## Precisões23065 incorporadas antes do código

Claude2 aceitou a direção do desenho/fakes com estas precisões. Não autorizou
execução nem fechou orçamento/gates de produção.

1. Estado enumera os pins transitivos d671/efe6/e6ca/fe2 e stdlib. No final
   comparar ao vivo e também em memória: delivery.OWNER_RAW, delivery.O.
   CHANNEL_RAW/READER_RAW, profile.PROFILE_RAW/OWNER_RAW, policy.PROFILE_RAW.
   Incluir as mesmas capturas equivalentes alcançadas pelos monitores; código
   duplicado por namespace não permite aceitar uma cópia alterada. Conferência
   final pura, independente de prazo/fire, sem rerodar scripts consumidos.
2. RuntimeCodes é conjunto fechado derivado por AST dos literais need/raise
   dos bytes capturados/fixados, não de mensagens arbitrárias em runtime.
   Incluir B_DEADLINE/WATCHDOG_FIRED/SUPERVISION_HELD/RESULT_INSPECT_BINDING/
   INVOKE_SCOPE/PS_SCOPE/READER_CLI_SCOPE/CLI_CONTROLS/MONITOR_HELD/
   PREVIOUS_CASE_HELD/OWNER_BINDING e os literais reader-watch/policy/delivery.
   HostFault da CLI comum usa identidade de libs.bounded.HostFault; namespaces
   novos somente pelos callers _bounded/clock.sample e seus globals exatos.
   ReaderError/BootstrapError exigem enum próprio; Timeout/Cancel próprios.
3. Foreground de A recebe case one antes de start_cycle; fake de fire em A
   deve cancelar esse startup sem armar B. Replay síncrono fora do foreground.
4. Não inferir que cleanup falhou por mutex: o host não exporta essa causa.
   Tabela: cleanup positivo→stop; cleanup negativo com active.fired→stop/join
   comprovado→uma nova coleta dos mesmos records; negativo sem fire→preservar
   monitor. Se Bstart existir, aguardar fire dentro da janela Bstart+600 e sua
   coleta por até55s; observação atrasada/join não provado conserva HELD, sem
   aumentar essa janela nem fazer nova chamada de coleta. Se B não foi armado,
   não inventar deadline de fire: HELD retém loop até recuperação explícita.
   A espera/recuperação de falha não é passe nem garantia de restore dentro
   dos600s: se exceder, registrar POST_B_OVERRUN e continuar só restauração
   segura quando houver prova, sem soltar recursos por prazo.
5. Pré-A é estritamente antes da entrada em start_cycle, pois sample já chama
   processo de clock. UNTOUCHED_PRE_A só com todos threads/tasks locais
   coletados e commands vazio, sem inventário/restauração medida do daemon.
6. Passe exige pg16_reader_verified/owned_cleanup/inventory_restored/
   volumes_restored/desktop_restored/pins finais/journal,23JOINED sem fired/
   held, _supervision_errors vazio e nenhum erro histórico/interrupção/prazo/
   SUPERVISION_HELD. Resolver a coleta não apaga a reprovação histórica.
7. Preparador mede admissão≤3s e estado≤32768 antes da proposta; valores não
   são ampliados para fazer passar uma tentativa. Constructor/admit não são
   usados como prova de execução shell ou release.

Orçamento:23065 confirmou que diagnóstico nativo reduzido não é obrigatório.
A primeira matriz23 pode ser a medição, se houver diagnóstico de pins revisado
(pinsFalse/True/transitivo-final), estimativa por caso com contagem de CLI/pins,
3WAIT≥24s, attach/rm parcialT4 e cauda histórica6,3s, margem explícita e
aritmética de cleanup/restore incluindo hashes. Meta típica recomendada≤70%
deB300; se não couber, revisar prospectivamente antes da proposta ou manter
bloqueado. A parte de segurança deve incluir um pins e join55 de estouro
síncrono, pins dos CLIs de cleanup e dos cerca20 de restore, não só os seconds
antigos. Se a conta não fechar com margem, gate não abre. ExcederB consome a
rodada NOT_PASSED, sem retry/ampliação de12/8/600 ou releitura como passe.
