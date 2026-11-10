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
