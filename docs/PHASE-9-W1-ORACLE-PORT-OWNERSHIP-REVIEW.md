# W1 Oracle: revisão de posse e portas concretas

2026-11-11. Próximo desenho somente, sob delegação. Código e teste duplex
publicados emd9e8293bab4f32295b62ba586d96842f5fb8cb53; fetch confirmou
HEAD/origin iguais,0/0. Bytes dos blobs fonte/teste iguais aos testados.
1410relacionados/195próprios/6sondas e estáticos são evidência desse código;
nenhuma suíte foi repetida por esta reconciliação somente de leitura.

## Reconciliação recebida e lida integralmente

Claude2CLI55131, mesma sessão51ea0d85/claude-opus-5-5/medium, encerrou0/
success em43848ms. Ferramenta permitida somente Read, sem recusas. Root
leu toda a resposta em read-only-reconciliation.json. Não houve edição,
outro escritor, quota ou fallback. A proposta deste próximo escopo é de
Claude2, não atribuir ao Gemini. Nenhuma aprovação individual inventada.

Direção aceita somente para escrever o futuro
docs/PHASE-9-W1-ORACLE-PORT-OWNERSHIP-DESIGN.md, ainda AUSENTE no checkpoint.
Não é aceitação de uma implementação nativa, de argv operacional ou release.
Antes de escrever o desenho, ler este parecer e os contratos atuais; root
lerá o desenho inteiro antes de qualquer teste/RED ou futura fonte.

## Precisões normativas para o desenho, ancoradas no código público

1. Reusar main89c99c65/driverb54a8a94/puro4c155d76/EXPECTce6ff389,
   hoste86f8e32 e bridge5a09be1c sem editar. O reator é o único motor de
   protocolo. Portas/DTOs da ponte,56linhas/512incluindoLF/50controles/
   frames16bytes e reservas originais são fixos. Plano antigo256linhas,
   bind único e APIs antigas não voltam como autoridade.
2. Um owner deve existir por INVOCACAO de helper/ação, não só por classe
   de helper. Os dois ZERO24/ZERO25, erros e resultados tardios precisam
   de registros distintos e retenção, sem sobrescrever a operação anterior.
   Matar/recolher o CLI do gateway não encerra helpers ou conexões de ação.
3. Fechar como owner externo observa fatos físicos tardios sem chamar
   outcome() duas vezes, reobservar op já colhida/quarentenada, alterar
   outcome UNKNOWN original, limpar slot da ponte ou reabrir o protocolo.
   A observação física pertence aos registros nativos próprios do owner;
   o snapshot de protocolo permanece imutável após a primeira observação.
4. Root conferiu runtime/budget.py: CleanupConfirmation é explicitamente
   TRUSTED MODEL, com cinco bools e sem vínculo de identidade. release()
   devolve crédito lógico; BudgetLedger diz que isso não prova retorno
   de commit do SO. Não apresentar esse DTO, todos True ou token lógico
   como atestado nativo. O futuro owner precisa derivar fatos completos
   por identidade/recursos antes de pedir release, com contrato auditável
   próprio, sem modificar BudgetLedger ou criar framework genérico novo.
5. Fixar ponto exato de posse antes de cada efeito e sentido de SENT:
   handoff local completo, nunca ack do peer. NOT_SENT requer zero provado;
   parcial/erro incerto é UNKNOWN e retido. Explicar o que o API público
   concreto pode observar, o que não pode, e como isso produz os DTOs sem
   inventar contagem ou quietude. buffer/drain/is_closing/wait_for cancelado
   não são prova física de cleanup nem preempção do SO.
6. Fechar relógio/poll/deadline e retenção quando o SO não coopera, sem
   prometer teto absoluto com mera task cancelada. Fatos de exit/reap/CID,
   ausência por identidade e cada helper devem ter origens e limites
   claros. O contrato de quiescência fica FORA da ponte, que não ganha
   close/quiesce/ticket/nonce ou outro releaseAPI neste incremento.
7. Propor um adaptador específico e mínimo para o único processo futuro
   de CLI e as seis ações, reaproveitando portas/ledger existentes. Não
   escrever outro motor de protocolo, framework de SO ou cadeia genérica
   de proveniência. Separar a futura ligação concreta e sua prova do fake.
8. Operacionais continuam NOT_PREPARED: runtime/CLI/stdlib pins, perfil,
   margens, raiz, task, nonce, estado, CIDs, rede/IP, credenciais, comandos
   e argv. Não ler nem preencher esses itens agora.300s de freshness não
   é o domínio prospectivo overall300 da ponte. Tentativa consumida não
   renasce por um desenho, ticket de modelo ou novo documento.

## Próximo lote único

Mesmo Claude2/sessão51ea0d85/claude-opus-5-5/medium, após conferir Git
atual e zero agentes ativos. Somente Read/Edit/Write do novo DESIGN, sem
comandos/execução nem outro arquivo editável. Se ativo, apenas monitorar
e recuperar terminal, nunca segunda chamada. Não reutilizar d9e8293 como
guarda de HEAD depois de publicar este checkpoint documental.

Desenho deve fechar assinaturas concretas, fatos/owner/cache/posse e matriz
de falhas para futuros testes determinísticos, incluindo falha antes/depois
de cada reserva/start, escrituras parciais, entrada que não é lida, saída
limitada, wait sem prova, controles originais, late spawn e helper que
sobrevive ao kill do gateway. Testes/RED antes de código; nenhum fake
declara gate físico ou autoriza liberar recurso real.

Fonte/testes/pins/app124/estado16/attempt fixos. Sem Docker/PG/SQL/SO/nativo,
runtime/config/privado/binário/root/nonce/estado/entry/loader/collector/
publisher/comando/deploy. T5físico/B1/B2/D090gate2/C1/D119/TLS/ingressos/
produção continuam abertos; Gateway indisponível. Nenhum novo job/reset:
as5chamadas C2 desse turno terminaram sem quota. A tarefa antiga já entregue
continua sem próximo disparo conhecido; não é promessa de entrega futura.

## V1 lida integralmente: não aceita ainda para testes

CLI53445 encerrou0/success em401481ms, sem recusas. Root confirmou zero
escritores e leu TODAS as472linhas/25913bytes da V1, SHA
be7e0e4b5085a3b4714d4abaa8fd3377e122d8f9fd4848c9865e6c93449e8ecb.
Snapshot/resultado preservados em design-v1.md.txt e metadados. Nenhum
teste, fonte, runtime ou efeito nativo foi criado/executado neste lote.
Os pontos abaixo são problemas do DESENHO, não findings de produto medidos.

Aceitos como direção: reuso dos componentes, owner por invocação, cache
de protocolo separado dos fatos tardios e release lógico distinto de SO.
Antes dos primeiros testes, fechar estes7pontos em V2 do mesmo documento:

1. **Seam sem loop real e reserva antes do efeito.** Os primeiros testes
   continuam sem eventloop/socket/thread/processo nativos; não usar um
   BaseEventLoop real nem alterar globais do asyncio/SDK. Definir uma
   dependência estreita e pública para loop/wait/scheduler com fakes puros,
   exercitando o mesmo caminho de validação, não um _bind_for_fakes que
   pula o binding público. Não é autorização para framework de SO novo.
   A ligação nativa futura deve exigir loop próprio/exclusivo/parado,
   não fechado e sem task factory personalizada, ou garantia equivalente
   explícita. type(Proactor) sozinho não garante create_task preguiçoso:
   o API público permite task factory customizada. Validar/estabelecer
   precondições antes de assumir que schedule não executa código antes
   de arm. [Python: task factories](https://docs.python.org/3.11/library/asyncio-eventloop.html#asyncio.loop.set_task_factory)
2. **Settle não pode iniciar filhos novos de uma ação antiga.** Exemplo
   da V1: ACT ARMED espera CHILD1; ponte termina UNKNOWN; settle bombeia
   o loop, CHILD1 termina e a corrotina inicia CHILD2. É efeito novo
   pós-protocolo, apesar de parent já estar ARMED. Fechar dispatch antes
   do bombeamento observacional e conferir gate/prazo ANTES DE CADA
   efeito, não só na entrada da corrotina. Não iniciado termina sem
   efeito; já iniciado continua observado/retido. Auditoria/recuperação
   explícita, se proposta, é outra invocação autorizada e não reabre ACT.
   Controle original não dispara callback novo no handler.
3. **Cache por op, inclusive read.** V1 não dá registro READ, mas diz
   que todo _Op congela ProtocolState do registro. Fechar como leituras
   sucessivas têm outcomes imutáveis próprios sem sobrescrever estado
   SPAWN ou outra leitura. Limitar registros transitórios e demonstrar
   quem os retém quando há erro/prazo/controle. Não reter histórico
   ilimitado por byte nem limpar slot/célula da ponte por fora.
4. **Assentamento local não é fechamento de handles.** LOCAL_CLOSED da
   V1 usa exit/pipes, enquanto §10 retém transportes/handles para sempre.
   Nome/campos devem revelar recursos ainda retidos e o escopo exato do
   candidato. Fechar trajeto viável e explícito de recuperação/disposição
   e passagem de posse por identidade/prazo fora da ponte, sem execução
   agora. Proibição de cleanup NA PONTE não proíbe desenhar recuperação
   do owner externo. Não substituir o caminho funcional por retenção
   eterna como sucesso. Evitar close/kill ocultos em callback/finally;
   efeitos futuros explícitos devem ter dono e comprovantes próprios.
   Se a prova física depender de SDK/perfil futuro, manter esse gate
   aberto e não emitir release físico com bool de modelo.
   [Python: subprocess close](https://docs.python.org/3.11/library/asyncio-protocol.html#asyncio.SubprocessTransport.close)
5. **Auditorias sem circularidade e com escopo de identidade.** Na V1,
   ambas devem começar depois do último fechamento local, incluindo os
   próprios filhos: A=[10,11], B=[12,13] nunca satisfaz A.start/B.start>=13.
   Capturar fence dos atores de trabalho antes de selar dispatch; separar
   filhos observacionais das auditorias e ainda exigir seu assentamento
   ao concluir. Não mudar o fence por cada próprio filho. CliPlan/Record
   precisam ligar gateway/KILL/auditorias ao MESMO escopo admitido, sem
   valores operacionais agora. Exit0/saída vazia de argv arbitrário não
   prova ausência do alvo. Fechar invalidação/frescor e impedir ator novo
   depois do fence; distinguir observer de backends do papel-alvo.
6. **Outcomes/decoders fechados e completos.** HostReactor._facts_ok,
   linhas437–440, exige facts=None para QUALQUER status que não é OK.
   Corrigir a regra FAILED da V1. Fechar assinaturas/domínios dos decoders
   de helpers e sua ligação a kind/case/token/escopo/resultado bruto
   limitado, mesmo que o perfil nativo e o formato real sigam não
   preparados. Os primeiros testes precisam de oráculos concretos, sem
   um parser mágico ou fatos fornecidos pelo chamador como prova física.
   Separar conclusão UNKNOWN precoce com filho vivo de conclusão conhecida
   OK/FAILED só após assentamento. Erros fechados não são nomes arbitrários
   de classe/mensagens. Nenhuma credencial em argv/erro/relatório.
7. **Buffer e handoff sem alegar mais que o API.** O API público de
   get_write_buffer_size documenta tamanho de buffer; não atesta sozinho
   conclusão de todos os handles/WriteFile ou ausência física. Definir
   SENT como handoff local do contrato e manter inferências nativas não
   medidas como NOT_PREPARED. Conferir também erro/fechamento síncrono
   durante write, antes de receber PIPE_LOST: retorno normal+buffer0
   sozinho não pode aprovar descarte silencioso. UNKNOWN0 deve significar
   explicitamente quantidade não estabelecida/limite confirmado, não
   zero transmitido provado. Para stdout/helpers, cortar/copy-prefix
   ANTES de estender buffers; teto numérico por buffer, inclusive callback
   grande/último bloco/EOF. Overhead do callback nativo ainda precisa de
   perfil/pin, não alegar memória limitada a um bloco de tamanho indefinido.
   [Python: write transports](https://docs.python.org/3.11/library/asyncio-protocol.html#write-only-transports)

V2 deve resolver esses pontos no contrato/API/matriz positivos/adversariais,
sem tornar tudo UNKNOWN, esconder o binding necessário ou adicionar outro
motor/genérico de SO. Preservar o snapshot V1. Somente o DESIGN editável;
sem testes/fonte antes de root ler toda V2 e aceitar oráculos.13pins/app124/
bridge5a/teste97/estado16/attempt fixos;1410verdes históricos, não repetidos.

## V2 inteira relida: direção aceita, precisões antes dos oráculos

CLI42440 encerrou0/success em299684ms; terminal recuperado e zero agentes
conferido. Root leu TODAS612linhas/32755bytes, SHA
abbe742bb9442a6d61b4de6bd30a8b98cdc8d0dd87f2c5efb9ac2ea97529d274.
V2 preservada. Owner puro/Pump estreito com mapeamento Proactor futuro,
fakes sem asyncio, seal, ReadTake separado, SETTLED_RETAINED e disposição
explícita corrigem a direção da V1. Não é abandono do binding nativo:
o módulo Proactor continua entrega necessária posterior, não substituto
sempre-UNKNOWN. Nenhum teste/fonte/loop ou efeito nativo executado.

Sob delegação, pedir apenas estas5precisões na V3 antes de aceitar testes:

1. **Namespaces e DTOs reais, sem import mágico.** O construtor tem só
   pump/plan/limits, mas exige Act exato e cria DTOs/facts de módulos
   carregados pelo chamador. Fechar parâmetros/referências explícitas dos
   namespaces já carregados/confiáveis da ponte e do reator, verificações
   de forma/classe/enum e origem a cargo do chamador. Não autoimportar
   docs.poc ou executar loader não pinado. Mesmo caminho público para
   fake/real. Não é framework genérico de proveniência. Tipar os campos
   públicos ainda sem tipo/limite, incluindo ReadTake e resultados audit.
   Tirar a garantia de padrões de segredo não declarados no CliPlan:
   substring em argv é só coerência estrutural, não autenticação do
   comando/alvo nem detector de segredo. A admissão confiável futura
   deve validar receitas/escopo/canais de segredo antes de efeito real.
2. **Recuperação não pode ser impossível por construção.** A regra de
   authorize exige nenhum first_control para TODOS os efeitos, bloqueando
   depois de KeyboardInterrupt até auditoria/disposição explícitas. Manter
   controle/protocolo originais imutáveis e proibir trabalho novo, mas
   fechar uma via explícita e limitada de recuperação no mesmo escopo,
   sem reabrir a tentativa. Falhas históricas não apagam prova física
   posterior de assentamento; distinguir erro histórico de incerteza ainda
   não resolvida. Outra circularidade: CLOSE_HANDLE de um filho de audit
   incrementa epoch e torna a auditoria STALE; nova audit cria novos
   handles, cuja disposição torna tudo STALE de novo. Separar mudança
   que pode alterar o alvo da simples disposição local de processo já
   terminado. Não invalidar ausência por fechar observador já assentado;
   ainda exigir assentamento/disposição dos helpers e invalidar qualquer
   efeito que realmente mude o alvo. Quietude escopada não é PASS do
   protocolo nem liberação física global; não apagar first_control.
3. **Authorize antes de chamadas diretas.** §4 põe chamada direta de write/
   dispose no passo5 e authorize no6. Fechar ordem inequívoca para essas
   chamadas: reserva/bind/arm, pré-condições, autorização e prazo, só
   depois write/close/kill. Confirmar também antes de cada CHILD. Sem
   callback entre autorização e efeito no contrato síncrono. Especificar
   como high/low0 é configurado ANTES de expor o handle/SpawnOutcome e
   antes de primeira escrita, com falha retida/fechada. Callbacks de
   data podem fazer flow-control limitado, mas não trabalho novo oculto.
4. **Aritmética e buffers exatos.** §5.2 soma len(chunk)-room: um chunk77
   com room28673 produziria dropped negativo. Usar take=min(len,room),
   copiar só take, dropped=len-take; definir aceitos total vs buffer
   residente, contadores não negativos e saturação. Stderr não pode ser
   dito não retido e ao mesmo tempo seguir uma rotina que o armazena;
   fechar count-only/cap/truncamento. Preservar dados antes de EOF/erro,
   limite ReadTake e estado próprio sem alterar SPAWN ou slot da ponte.
5. **Decoders concretos sem inferir sucesso operacional errado.** Fechar
   AuditDecode (referenciado, não definido), índices/quantidades de filhos,
   ordem, nomes/tipos exatos de keys e domínios. Em OBSERVE, found=False
   com1..20observações é fato COERENTE em OK no reator, levando a NOSTOP,
   não uma falha operacional que aborte o protocolo. Definir entrada do
   raw não zero quando deveria trazer JSON, status/faixa e razão fechada;
   FAILED/UNKNOWN sempre facts=None. Completar schema/decoder da remoção
   e estado após KILL/close sem introduzir novo motor do protocolo.
   Nenhuma credencial em argv/saída/erro; formatos/receitas nativas reais
   continuam sujeitos à admissão, não viram prova só por ter scope_id.

V3 deve preservar os acertos de V2 e só fechar esses pontos, com matriz
de contraexemplos e APIs suficientes para os primeiros fakes puros. Não
criar testes/código nem preencher operacionais. Bridge/host/main/driver/
puro/EXPECT/SDK/testes/app124/estado16/attempt fixos. Root lê todo delta e
o documento final antes de aceitar oráculos; gates físicos/produto abertos.

## V3 inteira relida: três precisões finais de recuperação e limites

CLI68333 terminou0/success em187627ms, recuperada. Root confirmou zero
escritores e leu TODAS652linhas/32600bytes da V3, SHA
14410f11fa5c5ac2e9b71cad9d6268c422556cbd8127c4ddc3067ba383ce3e89.
Snapshot preservado. As5precisões anteriores foram atendidas; namespaces,
despachos separados, ordem direta, contadores e decoders têm contratos
explícitos. Aceita sob delegação a correção conservadora de exit não zero
para UNKNOWN: erro de comando não prova ausência de efeito. FAILED fica
restrito a predicado conhecido falso sobre esquema válido; ambos facts=None.
Isso é revisão de desenho, não finding de produto executado.

Antes dos primeiros testes, ajustar SOMENTE estes pontos na V4:

1. **`settle` não considera UNKNOWN assentado.** §7 usa `stop=todos os
   registros fora de OPEN`. Um spawn incerto sem handle é UNKNOWN, logo
   stop já é True e nenhum `started` tardio é bombeado; repetir settle
   não progride. Encerrar cedo só quando todos estão NOT_STARTED,
   SETTLED_RETAINED ou RELEASED_LOCAL. UNKNOWN e OPEN exigem continuar
   observando até target ou prova posterior; sem prova permanecem retidos.
   Não consultar ops quarentenados nem converter ausência em not_started.
   Oráculo: start_failed sem handle, seal, started tardio/exit/pipes dentro
   de target devem ser observados; sem evento, chega a target ainda UNKNOWN.
2. **Assentamento da auditoria é monotônico com CLOSE_HANDLE.** §8 exige
   filhos exatamente SETTLED_RETAINED, mas §9 os muda para RELEASED_LOCAL.
   A época não muda, porém recalcular helpers_settled pelo estado exato
   invalida a auditoria e P1 depois de fechar os handles. Aceitar cada
   helper comprovadamente assentado em SETTLED_RETAINED OU RELEASED_LOCAL,
   mantendo os bytes/resultado da mesma invocação. NOT_STARTED/UNKNOWN
   nunca provam observação. Oráculo antes/depois de CLOSE_HANDLE: mesma
   auditoria válida e quiet_scoped True, com custódia local reduzida.
3. **Fixar construtor e alcance dos limites para oráculos não inventados.**
   OwnerLimits tem campos sem tipos/defaults/validação. Explicitar todos
   como int exato, valores padrão da §3, tetos prospectivos do modelo e
   domínio de limites menores usados em testes. Não ler configuração
   operacional. Explicitar contagem por vida do owner versus por invocação:
   max_children24 não pode ser teto global que impede o P1 com até20filhos
   só em OBSERVE e os demais ACTs/auditorias. Fechar a recusa antes de efeito
   e teto agregado pelo max_records. Preservar512/56/50/51/28673 e todos os
   componentes publicados. Validar coerência estrutural gateway_name !=
   pg_name e observer_role != target_role; continua sem autenticar receitas.

Precisão de implementação do namespace, sem framework novo: acessar as
entradas reais de vars(module), sem acionar __getattr__ de módulo ausente.
Isto dá sentido verificável a "sem chamar código do módulo"; os módulos
continuam confiáveis e pinados pelo chamador, não uma defesa contra classes
hostis arbitrárias. Não criar novo loader ou API de prova física.

V4 deve só ajustar esses contratos e os respectivos contraexemplos, sem
reabrir a arquitetura, preencher operacionais ou criar testes/fonte. Root
lê o delta e fecha a direção para os primeiros testes.13pins/bridge/teste/
app124/estado16/attempt fixos;1410verdes históricos, não reexecutados.

## V4: direção aceita somente para os primeiros testes

CLI79160 encerrou0/success em82774ms; terminal recuperado. CIM posterior
conferiu zero escritores em2026-11-11T13:44:51Z. Root leu todo o delta da
V3 para V4 e já havia lido as652linhas anteriores. V4 tem731linhas,
37799bytes, SHA
527ab514d9006a05f31ca5f4ccd94a472bdebf2ea9973d21f337cdf287249e74.
Snapshots V1–V4 e delta preservados. A captura V4 contém metadados
transcritos pelo root do terminal recuperado, explicitamente não raw stdout.

As três precisões foram atendidas: UNKNOWN não encerra settle antes do
target; prova da mesma auditoria sobrevive à disposição local dos helpers;
limites têm tipos, defaults, domínios e alcance por vida/invocação. Acesso
ao namespace não aciona __getattr__. O número137 é teto conservador de P1,
não cardinalidade exata obrigatória: os filhos das ações descritas somam
até30; usar33 como estimativa superior não autoriza filhos adicionais nem
altera as receitas exatas da §5.5. Os testes devem conferir kinds e limites,
sem inventar uma sequência maior para atingir137.

Sob delegação, direção V4 aceita SOMENTE para escrever os primeiros testes
determinísticos de tests/test_oracle9_w1_port_ownership.py. Root lerá todos
os oráculos e medirá/congelará RED ANTES de qualquer fonte. O módulo
docs/poc/oracle9_w1_port_ownership.py e o futuro módulo Proactor continuam
AUSENTES. Não é aprovação individual do usuário nem implementação nativa.

Mesmo Claude2/sessão51ea0d85-05bb-4d24-ba9a-c9627c3f832f, modelo
claude-opus-5-5/medium. Próximo lote só Read/Edit/Write do novo teste,
sem comandos; conferir HEAD real/zero escritor, ativo só monitorar e
recuperar terminal antes de outra chamada. Fakes de Pump/Handle, ponte e
reator reais publicados. Nenhum efeito real de SO, asyncio/eventloop,
thread/processo/socket/sinal/guard, Docker/PG/SQL, runtime/config/privado/
binário/ambiente/root/nonce/estado/entry/loader/comando/deploy.

13protegidos/bridge5a/teste97/app124/estado16/attempt fixos.1410verdes são
históricos, não repetidos por documentos. Sem quota/fallback/job novo.
T5físico/B1/B2/D090gate2/C1/D119/TLS/ingressos/produção continuam abertos;
Gateway indisponível. Proactor, admissão de receitas/segredos/ambiente,
supervisão externa e prova por identidade continuam NOT_PREPARED, sem
trocar entrega física por fakes ou quiet_scoped.

## Complemento de representação revisto antes da fonte — 2026-11-11

RED171 foi revisto e congelado localmente em e85f8b53:4sanidades PASS,
167falhas exclusivamente por ausência do owner,0erros/skips. Nenhuma
evidência comportamental ou nativa. Ler PORT-OWNERSHIP-TEST-REVIEW completo.

Claude2 permanece em quota semanal observada, sem retry antes12/11 às
23hUTC informado. Fallback Gemini Argon high/high, mesma conversa26d0a462,
CLI42016/15302 recuperadas0/SUCCESS (104,146s/40,110s), somente proposta
read-only sobre os9arquivos públicos já autorizados. Zero escritor após
as entregas. Root leu as duas propostas inteiras; a primeira foi rejeitada
por coerção de failed, política nova de callbacks fora de escopo e redação
que atribuía mutação do protocolo à quarentena da ponte.

Segunda proposta8d4ffabe/7069bytes/60linhas aceita sob delegação SOMENTE
como precisão do modelo em PHASE-9-W1-ORACLE-PORT-OWNERSHIP-CONTRACT.md:
tuple de pipes por fd0/1/2; None sem evento, bool exato igual ao failed
observado; ausência de pipe não vira prova de fechamento. Índices locais
e da ordem imutável de CliPlan são explícitos por kind. UNKNOWN da ponte
não escreve o protocolo do owner; ReadTake não ganha campo parent; prazo
concluído de startup não limita a vida da sessão. Campos/enums/API e
oráculos congelados permanecem idênticos. Não é aprovação individual
inventada nem dispensa de prova por teste ou admissão nativa.

Sob a delegação vigente, próximo incremento pode implementar SOMENTE o
owner puro docs/poc/oracle9_w1_port_ownership.py, pelo programador de
fallback enquanto a quota C2 observada persistir. O módulo Proactor,
testes congelados, upstream/protegidos/app124/state16/attempt não mudam.
Root deve ler TODA fonte antes de executar QA e não publicar parcial
como verde. Sem efeitos nativos, operacionais, Docker/PG/SQL ou deploy.
As demais validações de produto e físicas continuam abertas.
