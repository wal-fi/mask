# W1 Oracle — revisão do próximo contrato host

2026-11-10, sob delegação. Base publicada9d49b55 (código861969d). Este registro
fecha somente o escopo do desenho prospectivo, sem autorizar efeitos nativos.

## Reconciliação de leitura

CLI16500 recuperada0, ferramentas somente Read, sem edição. Root leu o plano
nativo v4 inteiro (599linhas), revisão e contratos pertinentes de pure/driver/
main. O relatório do programador está preservado em host-design-review-20261110.
Fontes atuais e849gates do lote anterior não mudaram; nenhum novo gate medido.

Precisões do root para o desenho mínimo:

- Três binds RO de arquivos públicos exatos, sem bind de diretório, são a
  direção escolhida sob delegação. Destinos: constantes MAIN_PATH/DRIVER_PATH/
  PURE_PATH do main. O host deve conferir o hash do main antes de uso; main
  não se auto-pina: confere driver e puro. Montagem/legibilidade são nativas.
- Protocolo público tem decode_control e ControlMachine, mas NÃO encoder
  público. Host poderá ter só pack fechado16bytes por ABI aprovado, validado
  por decode_control. Não mudar SDK/puro para inventar nova API nem importar
  estruturas privadas do driver. Máquina existente modela a ordem de controle.
- Linha<=512bytes incluindoLF, máximo56, frames50. GUARD não contém Threads:
  usa as/dumpable/pdeathsig/pid. Fato Threads1 está no guard e na admissão,
  nunca inferido de campo inexistente. RESULT não contém digestsha256:
  usar campos reais por caso e sink/bytes; não inventar observação do host.
- Ação e transmissão só avançam após confirmação do efeito completo. SENT
  local não comprova recebimento pelo container. UNKNOWN é terminal, sem retry.
- T6: live_window_ms chega depois de tráfego. Somar janela ao horário de
  recebimento a amplia indevidamente. O desenho precisa de limite conservador
  baseado no instante do host anterior ao envio de GO25 (precede o cálculo
  do driver), ou outra prova equivalente, antes de chamar um kill como tempestivo.
  Recibo de kill sem observação física continua somente hipótese de porta.
- Proposta de reuso de Proactor/clock/ownership antigo precisa leitura pública
  própria. Não presumir fonte operacional pronta ou importar/executar scripts
  antigos que têm código de topo. Este lote apenas desenho de reator puro e
  contrato da ponte, sem nova infraestrutura genérica de SO/proveniência.

## Próximo lote delimitado

Mesmo Claude2/sessão51ea0d85/claude-opus-5-5/medium escreve SOMENTE
PHASE-9-W1-ORACLE-HOST-DESIGN.md. Reator puro, esquema real de eventos,
controle/ações/recibos/prazos/retidos e contrato futuro da ponte, antes de
qualquer teste ou fonte. Fonte nativa antiga é história; novo documento faz
a reconciliação sem reescrever requisitos medidos. Root lerá o desenho inteiro.

Sem Docker/PG/SQL/socket/thread/processo/guard/sinal/native real, runtime,
config/ambiente/binário/privado, raiz/nonce/estado/comando operacional ou deploy.
App124/SDK/puro/main/driver/EXPECT/estado16/tentativa consumida fixos.
T5 físico/B1/B2/D090gate2/C1/ingressos/produção continuam abertos.

## Interrupção por quota, sem desenho entregue

CLI26058 encerrou1/API429 antes de qualquer edição. Arquivo HOST-DESIGN
permanece ausente; não confundir a reconciliação16500 recebida com desenho
novo escrito. Mensagem: session limit, resets1:50pm America/Sao_Paulo,
inferido10/11/2026 às16h50UTC. Reset não observado, sem retry. Zero escritor
confirmado após recuperar o terminal; oito fontes/testes correntes e app124
intactos. Não há fonte/teste novo nem razão para repetir849gates históricos.

Mesma tarefa Maskgw-Claude2-Resume-01a05804 foi reprogramada e relida Ready
para10/11 às13h55-03:00/16h55UTC, uma vez. Limited/Interactive/IgnoreNew,
um action/trigger e mensagem queue nesta conversa conferidos. Registro não
comprova entrega nem reset; requer computador/logon/app disponíveis. Próximo
lote continua somente o desenho HOST, com as precisões deste documento.

Fallback Gemini: a revisão automática anterior exigiu consentimento específico
de envio, e o consentimento registrado nomeou somente4arquivos EXPECT. Não
se exportou conteúdo novo para contornar essa decisão. Pacote público8arquivos/
204.803bytes preparado, manifesto e cópias imutáveis locais; nenhum envio.
Foi solicitada autorização para esse pacote e contexto público necessário do
projeto em futuras retomadas, com exclusão de credenciais/config/ambiente/
runtime/histórico. Resposta ainda não recebida neste checkpoint. Não tratar
preparação, opção preselecionada ou agendamento como consentimento.

Consulta à documentação oficial de tarefas locais confirmou a dependência do
computador ligado e app em execução (https://learn.chatgpt.com/docs/automations).
O registro efetivo desta retomada é a tarefa Windows relida, não uma automação
criada pela API ou uma garantia de entrega do app.

## Autorização ampliada e timeout do fallback

Usuário autorizou qualquer pacote público necessário ao Gemini, substituindo
o limite4EXPECT. Novo envio ArgonHigh/high ocorreu em scratch8cópias, modo
plan/readonly, sem fonte/teste editado. CLI76884 retornou3/DEADLINE_EXCEEDED,
904,907s, sem resposta de desenho capturada. Limitações e falhas de acesso/
revisão automática descritas em gemini-timeout-and-resume-review.json.
O disparo13h55 foi entregue; após passar16h50UTC e guarda0escritores, a
continuação segura é a mesma sessãoC2, somente desenho. Não houve reprovação
técnica de desenho Gemini: nenhum desenho chegou para revisão.

## Revisão da v1 — ainda não liberada para testes

CLI32936 recuperada0, mesma sessão/modelo/esforço. Root leu389linhas da
v1:54b5ec87/20.241bytes. Só desenho, nenhuma execução de teste/source/nativo.
Direção de três binds, core público e recibos é adequada, mas há lacunas:

- R1: API e DTOs não fechados (§5): não há métodos/retornos exatos, tipos
  de token/facts/status/tempos/verdicts/Finish, ou relação inequívoca entre
  HostRefusal levantada e Finish devolvido. Entrada Line não tem timestamp,
  ActDone não tem pós-retorno; o reator puro não pode aplicar cercas assim.
- R2: records EXPECT independente de init_packet opaco permite incoerência
  de expectativas. Direção mínima: extrair expected do mesmo init_packet
  por core.decode_init público, sem segundo records, manter apenas expected
  e bytes privados necessários e sem promessa de zeroização. Nenhuma API nova.
- R3: orçamento de T6 exige unidade de tempo e política explícita; margem,
  epsilon e KILL_MIN podem ser parâmetros de testes, ainda NOT_PREPARED para
  uso nativo, mas seus domínios e fórmula precisam ser fechados. Recibo tardio
  não passa por comparação só de timestamp declarado sem amarração à ação.
- R4: 50controles não limitam next_seq do evento a50: após GO50, ARMED25
  tem next_seq51. A57ªlinha precisa ser recusada (não só ultrapassar57).
- R5: campos nulos de T1–T4, domínios ABORT, falha durante pendência e T4
  NOSTOP sem achado normal versus falha de observação precisam ter regra
  exata. Não permitir facts genérico ou Finish interpretado como cleanup
  físico. Modelos só produzem candidato a evidência, não aprovação nativa.

V1 preservada como dados; próximo mesmo C2 edita SOMENTE HOST-DESIGN.
Nenhum teste/source antes de root ler a revisão. Loader público load_pure
via chamador é aceito prospectivamente, após pin do driver antes de import;
receber ModuleType não autentica origem por si só. Não criar camada nova.

## Revisão completa da v2 — precisões finais R6

CLI6393 recuperada0. Root leu todas592linhas:62a8b804/27.046bytes. R1–R5
fecharam a maior parte do contrato. API do encoder ainda não recebe o core
que deve decodificar o frame; não criar global/cache/loader para resolver.
Adicionar core explícito a pack_control. DTOs de entrada são carriers frozen
e suas validações pertencem ao feed, para marcar recusa pegajosa na instância.

Fechar sequência final: status expõe orphan original; recebido em ENDING
pode ser registrado uma vez sem avançar espelho/reabrir ações. Depois de
Done, feed não aceita mais recibo (ORDER), e Done conserva a referência
para o chamador. T6 positivo é exceção ao fim por Exited: só depois de kill
OK, Exited válido retorna ZERO_BACKENDS25; apenas seu OK encerra candidato.
Exited antes de kill OK nunca vira sucesso retroativamente. Bridge deve
serializar confirmação de kill antes de coletar/emitir Exited para esse
caminho; timestamps são observações seriadas do owner, não pré-timestamps
de pumps que seriam regressivos ao serem entregues. UNKNOWN retém de modo
conservador. H13 admite packet/payloadINIT privado redigido; proíbe reter
LabInit ou credenciais separadas, não o armazenamento necessário do pacote.

Somente precisão documental pequena, nenhuma nova camada, teste ou fonte.
Demais fontes fixas. Root lerá o diff final antes de aceitar primeiro teste.

## Parecer final do desenho, sob delegação

CLI29500 recuperada0; root leu diff inteiro R6 sobre a V2 toda já lida.
Documento final (V2+R6):aed85ad4/30.976bytes/655linhas. Aceito como direção
técnica SOMENTE para os primeiros testes H1–H17. Nenhum teste/código do
reator existe; root deverá ler todos oráculos e congelar RED antes da fonte.
pack_control recebe core explícito e compara os campos kind/case/seq do
Control público retornado por decode_control, não Control==tuple. Modelo
recebe core confiável já carregado pelo chamador; shape não autentica origem.

DTOs de entrada carriers são validados no feed, recusa pegajosa; expectativa
vem do mesmo INIT. Timestamps seriados do owner, orphan original preservado,
e Done não libera recurso físico. T6 só chega a candidato depois do kill
tempestivo alegado pela porta, Exited próprio e ZERO_BACKENDS positivo;
Exited precoce não pode ser promovido por recibo posterior. Nada disso
mede kernel/PG/frescor/identidade. Margens nativas continuam NOT_PREPARED.

Oito fontes/testes correntes e app124 intactos por SHA/tamanho; nenhum
SDK/estado16/attempt tocado.849verdes são históricos, não suíte repetida.
Validação desta mudança é documental (diff/JSON/hashes/revisão de API).
Usuário autorizou os pacotes públicos Gemini, não aprovou individualmente
este desenho. Autor real do desenho é C2; Gemini expirou sem resposta útil.

A atualização da mensagem agendada foi rejeitada por cota do revisor antes
de executar e não foi contornada. A mensagem antiga foi entregue16h55UTC
com result0/sem próximo disparo; o contexto posterior foi aplicado. A
recuperação UI do AGY teve app approval timed out e foi interrompida.
Retomada C2 após horário informado e guarda0, mesma sessão/modelo, funcionou.

Próximo incremento sob delegação: somente tests/test_oracle9_w1_host_reactor.py,
sem módulo antes do RED revisto. Conferir Git atual e zero escritor; ativo
só monitorar/recuperar terminal antes de nova chamada. Não repetir erro de
guarda HEAD23d8669 depois de publicar estes documentos. Sem execução nativa
/Docker/PG/SQL/runtime/config/privado/root/nonce/comando/deploy. Gates abertos.
