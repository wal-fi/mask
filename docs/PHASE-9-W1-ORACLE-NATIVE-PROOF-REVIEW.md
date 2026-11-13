# W1 Oracle: revisão da reconciliação após o chamador host

## NP5 — primitivas existentes reconciliadas; S continua não admitido

2026-11-13. 58426 e23493 TERMINAIS exit0/success/is_errorFalse, sem denials;
recuperadas. Mesmo Claude2/sessão51ea0d85/Opus5.5/medium, ferramentas Read
restritas, sem edição ou execução. Root leu AMBOS relatórios completos.
O primeiro omitiu o desenho e dois contratos; o suplemento os leu e corrigiu
o alcance de cap2. Nenhuma medição nativa ou teste novo decorre desta leitura.

Root conferiu diretamente os trechos citados e os seis fontes contra os
blobs publicados, além dos153textos protegidos/fixos. Candidatos existentes:
backend10c9058f, adaptadoreaebedd6, runnerb4198fe1, entry356d2291,
verifyb3755d49 e lifecycle7bbf734c. Nenhum foi carregado ou invocado.

| Capacidade | Evidência estática e limite |
|---|---|
| Posse antes do código do filho | Backend _start: JOB_LIST na criação suspensa; membership/config/accounting/lista antes de ResumeThread (693–809). Semântica do kernel não medida nesta revisão. |
| Aninhamento | NestedJobOwner preserva o _start herdado, expande JOB_LIST e verifica INNER antes de delegar resume (adapter273–324). Candidato, não admissão. |
| Encerramento/observação | Owner.terminate, wait, accounting, members e close já existem (backend812–919). Não são supervisor completo nem prazo absoluto. |
| Transporte | available/read (866–890) fornecem blocos disponíveis, não linhas já enquadradas; close exige quiescência e EOF. |
| Limite cumulativo | accounting recusa total>2, além de active>total (831–840). Um P e um helper em TODA a vida do job; outro helper posterior também excede o contrato, mesmo sem simultaneidade. |
| Orçamento | Argumento finito de wait e budgets verificados entre chamadas não limitam bloqueio dentro de CreateProcess/CloseHandle/outro _call. O admission_host declara isso explicitamente no docstring. |
| Controles | _guarded chama _interrupt dentro do except primário; _interrupt captura só Exception na contenção (561–589). Um segundo controle pode substituir o primeiro. Não há garantia global B4 pela simples reutilização. |

Qualificações normativas para a continuação documental:

1. A frase universal do desenho §2 sobre inexistência de API não é aceita.
   Há primitivas candidatas; faltam vínculo, premissas, autoridade, contenção
   externa efetivamente admitida e evidência real. Não afirmar capacidade S
   concluída por essa leitura. Kill ou retorno de função não prova liberação.
2. Cap2 vale no lifetime da contabilidade pública, não só para processos
   simultâneos. Subcasos independentes previamente declarados, cada qual
   com owner/job próprios e total<=2, são apenas possibilidade documental;
   não são retry, autorização ou valores preparados. N7 com efeito de
   criação incerto requer observação própria; não inferir total pela falha.
   Root confirmou o contrato público de
   [TotalProcesses na Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information):
   inclui processos encerrados e pode incrementar numa associação recusada
   por limite. Isso reforça a recusa de inferir contador zero por falha;
   não mede uma tentativa local nem autoriza consultas ao kernel.
3. A parada de efeitos após controle no processo P permanece distinta da
   contenção que S já tenta após seu próprio controle. Não transportar uma
   garantia de identidade mais forte para S. O limite de segundo controle
   é compatibilidade estática, não incidente nativo reproduzido nem motivo
   para modificar o backend congelado neste lote.
4. Transporte em blocos NÃO substitui o contrato de linhas fechadas da
   evidência. Um read pode conter linha parcial ou várias linhas; qualquer
   vínculo futuro deve preservar limites incrementais, ordem e recusa de
   excesso. Não tratar read de4096bytes como linha válida ou nova API de
   framing. Não foi criado parser, logger ou framework.
5. Verify(Expected/verify) é fechado nos pins, três casos e filesets antigos;
   atesta apenas bytes fornecidos. Lifecycle(context/lifecycle) captura
   hooks/registro/facts originais dos casos antigos. Runner/entry são seus
   consumidores específicos. Nenhum certifica S novo ou pode receber novos
   rótulos/estado16/receitas por analogia. Não ler artefatos de tentativa.

Aceite somente da reconciliação pública sob este parecer. N1–N16/B4/K1/N8,
T5 físico e todos os gates de produto continuam OPEN; nenhuma autoridade
operacional foi acrescentada. Nenhum defeito nativo foi reproduzido.

Próximo único lote seguro:mesmoC2 SOMENTE Read das referências públicas,
retornando em texto uma proposta curta de vínculo documental para §2/§4/§5
do desenho, sob NP4/NP5. Não editar arquivos, criar fonte/teste ou preparar
receita/valor operacional. Root lê TODA proposta antes de definir qualquer
alteração. Reusar primitivas, não criar outro owner/framework/lançador.

## NP4 — D2 revista; somente direção documental, BLOCK_NATIVE mantido

50139 terminou exit0/success/is_errorFalse, sem denials; recuperada.
Root leu TODO delta D1→D2 após as140linhas D1. D2 original55519010,
13.926bytes/154linhas, preservada. Corrigiu as quatro solicitações NP3.
Root ajustou apenas o rótulo editorial NP-D1→NP-D2 no título; corpo
idêntico. Nenhum código/teste/probe anterior foi alterado ou reexecutado.

Aceite somente da direção documental sob ESTE parecer, não admissão
nativa nem autorização de oráculos/código do harness. Contenção externa
S continua capacidade NÃO admitida; matriz não pode fechar gate global.

Precisões normativas antes de qualquer uso futuro da matriz:

- N2: a janela observável authorize→started/start_failed é maior que a
  propriedade authorize→CreateProcess. Um evento intermediário pode ser
  legítimo DEPOIS da criação e ANTES de started; por si só, não é FAIL da
  propriedade N2. Sem evidência que localize a criação nessa ordem, classificar
  a propriedade nativa INCONCLUSIVA. A célula FAIL resumida não se aplica
  automaticamente. Não criar instrumentação privada para fabricar prova.
- N4: a ausência de pipe_lost não prova EOF pausado. Antes de interpretar
  retenção como evidência desse cenário, exigir os fatos positivos próprios
  que demonstrem pausa, término do helper e que o cenário previsto ocorreu.
  Sem eles, INCONCLUSIVO, nunca PASS por mero silêncio. Não há execução aqui.
- Um contêiner de processos descrito em palavras não constitui contenção
  implementada/admitida. Nenhuma afirmação de inexistência de API em TODO
  repositório decorre dos poucos textos lidos. Verificar os contratos públicos
  antigos antes de propor novo proprietário, framework ou código de SO.

Próximo único lote seguro:reconciliação SOMENTE LEITURA dos contratos/fontes
públicos já existentes de pg16_shell_native_control e seus bindings win32,
comparados à capacidade S e B4/K1/N8. Identificar se algum pode ser reusado
inalterado, suas premissas e evidências ainda não medidas. Não transportar
estado16/tentativa consumida, preparar valores, gerar receitas nem executar
qualquer DLL/job/process/control. Nenhuma nova implementação por inferência.
Root lê TODO relatório antes de definir continuação. MesmoC2/sessão/medium,
Read restrito, sem comandos; zero escritor antes de chamar.

Fontec8d38d21/testee3ef7737 e153textos protegidos/fixos continuam conferidos.
1.844PASS/373estáticos são históricos deste lote de código, não medição do
desenho. Gate completo pump/bind, T5 físico e todos os gates de produto OPEN.

## NP3 — D1 lida integralmente; corrigir antes de aceitar

62109 terminou exit0/success/is_errorFalse, sem denials; recuperada.
Root leu TODAS140linhas/12.177bytes, desenho e038841a5dbeb1d8535e124fd2d22e4b20ece7a47e30cef93814224f9d059ab7.
Snapshot preservado. Direção de prova benigna separada, sem outra camada
pura e com posse externa prévia, é adequada; desenho AINDA NÃO aceito.
Gaps de S e da admissão são explícitos, não capacidades implementadas.

Corrigir somente o mesmo desenho, sem efeitos/código/testes:

1. §5: ausência de READY não prova ausência de bind/import/efeito. Uma
   escrita pode ter ocorrido e seu recibo atrasar, falhar ou não chegar.
   Sem READY: estado UNKNOWN/INCONCLUSIVO, S mantém posse e contém por
   identidade. Não acrescentar handshake/framework para fabricar essa
   prova negativa; a contenção de S já deve anteceder o nascimento de P.
2. §5 controles: emitir CONTROL depois de capturar o primeiro controle
   contradiz a parada de efeitos e pode bloquear/falhar no próprio canal.
   Após o controle, só retenção/leituras puras próprias; nada de nova
   escrita/flush/relógio/close/efeito para tentar anunciar o controle.
   Não alterar seu traceback/contexto ou substituir sua identidade. S
   decide UNKNOWN pelos fatos externos que tiver; falta de linha CONTROL
   não é ausência de controle. Não transformar a correção em outro logger.
3. §7 N1: data e write_resumed podem repetir legitimamente. Unicidade
   só onde o contrato publicado exigir (started, exited, closed e perdas
   por fd); não declarar FAIL por qualquer evento ou bytes repetidos.
4. §7 N2/agregado: observação authorize→evento não prova o intervalo
   authorize→CreateProcess no SO. Manter resultado parcial/INCONCLUSIVO
   para a propriedade não observável; nenhum PASS completo de N2. Definir
   PASS apenas do subconjunto explicitamente medido, sem retirar um N
   obrigatório por conveniência. N11 bloqueado/N14 OPEN/N15 não admitido
   não podem desaparecer no termo "aplicável" e virar gate global verde.
   N16 mantém seu tratamento particular do contrato já aceito. Explicitar
   que a prova completa pump/bind continua aberta com pendências.

São defeitos estáticos do DESENHO, não incidentes ou medições nativas.
Root conferiu as APIs de _Handle/ProactorPump e as distinções entre
eventos repetíveis e fatos únicos; nenhum SDK foi executado. Depois da
correção ler TODO delta antes de aceitar; nenhum novo código/teste aqui.

2026-11-13. Somente leitura e direção documental prospectiva.

## NP1 — reconciliação aceita com correções e limites

81650 e 53349 terminaram exit0/success/is_errorFalse, sem denials, na
mesma sessão Claude2/Opus5.5/medium. Root recuperou os dois terminais e
leu os dois relatórios inteiros. Nenhum arquivo foi editado pelo agente.

O primeiro relatório não leu os fontes deploy e repetiu uma pendência
histórica de desenho/código T5. Root pediu correção e conferiu diretamente:
_Driver.t5 e probe_open/probe_eof/probe_cleanup, ProbeChildren/build_ports,
bind_proactor_pump/_bind_over, HOST-DESIGN §12 e PROACTOR-DESIGN §15.
EXPECT está em docs/poc/oracle9_w1_expect.py; o caminho deploy/expect
fornecido na primeira allowlist estava errado e foi corrigido.

T5 já tem código e oráculos congelados no driver/main. O que continua
aberto é sua medição física. Não reabrir os módulos ou testes para
implementar o que existe. Nenhum novo defeito de código foi reproduzido
nessa reconciliação. A composição run_host publicada já basta; um novo
lançador ou camada pura não é pré-requisito para a prova benigna pump/bind.

Não se adota a sugestão inicial de fazer outro lançador como caminho
crítico. A prioridade é o contrato documental da prova benigna e de sua
contenção externa. Nos referenciais lidos há matriz N1–N16 e riscos
B4/K1/N8, mas ainda não uma admissão específica revisada dessa prova.
Isso não afirma busca exaustiva por todos os arquivos do repositório.

## NP2 — próximo único desenho, antes de qualquer novo código

Somente docs/PHASE-9-W1-ORACLE-NATIVE-PROOF-DESIGN.md, pelo mesmo Claude2,
Read/Edit/Write só esse documento, referências públicas restritas. Sem
comandos/execução e sem editar fonte/teste/pin/contrato já aceito.
Root lerá TODO desenho antes de qualquer aceite; nenhum teste ou código
novo antes de revisão dos oráculos e RED, quando aplicáveis.

O desenho deve ser pequeno, específico ao pump/bind já publicados:

1. Mapear N1–N16 a observações e evidências de identidade/ordem/recursos,
   distinguindo PASS, FAIL e INCONCLUSIVO. Não inventar observabilidade
   pública, cobertura nativa nem fechamento de N16 por injeção privada.
2. Fechar a posse EXTERNA da tentativa ANTES de construir loop/pump,
   preservada em F1 sem objeto, close bloqueado e controle na entrega.
   Reter traceback é retenção conhecida, não contenção. Nenhum teto
   absoluto do SDK nem sucesso por mero kill/ausência de mensagem.
3. Definir por categorias um helper benigno sem rede, segredos, banco ou
   Docker, seu canal de evidência limitado e tratamento de resíduos;
   nada de receitas, argv, comandos, raízes, nonce, estado operacional,
   handles reais, DLL, instalação ou escolha de novos valores operacionais.
4. Usar APIs existentes e deixar explícito qualquer gap de autoridade,
   admissão ou capacidade externa. Não inventar outro framework genérico,
   proprietário de processo ou camada pura para ocultar um gate nativo.
   Se não puder provar uma propriedade por essa superfície, bloqueá-la.
5. Separar prova física delimitada dos próprios recursos, quando houver
   fatos suficientes, de quitação global/produção. Não é correto dizer
   que nenhuma prova física seria possível em princípio, nem que um
   sucesso do modelo já a realizou. T5/W1/PG/ingressos ficam separados.

Nenhuma execução nativa autorizada por este parecer. Admissão explícita
de destino/host/runtime/controles e revisão das evidências vêm antes de
qualquer efeito futuro. CPython3.11.3/Windows é a referência histórica;
não houve inspeção atual do runtime, hooks, wakeup fd ou ambiente.

Código793473a/fontec8d38d21/testee3ef7737/probes e todos os anteriores,
app124/state16/tentativa permanecem fixos. Nativos/produto OPEN. Nenhum
rebuild, suíte repetida ou deploy decorre desta leitura documental.
