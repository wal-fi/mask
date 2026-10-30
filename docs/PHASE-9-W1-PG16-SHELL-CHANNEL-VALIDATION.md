# Canal público do leitor PG16 — fakes, sem chamador operacional

2026-10-30 sob delegação. Novo pg16_shell_owner.py captura e6ca e reader
efe69a79 por hash. Não edita as fontes anteriores. Apenas definições e fakes,
sem executar shell, DockerCLI, cluster, consulta ou credencial.

## Contrato e implementação

Desenho aceito pelo Claude2/review10641 antes do código, com três precisões
incorporadas: prazo total do host12s inclui leitor8s/attach/saída CLI; atraso
do host não vira DEADLINE esperado do caso; propagação do exit42 precisa de
medição e confronto com inspect; política dos negativos de header será fixada
antes da rodada nativa. Nenhum teto ampliado neste incremento.

PublicReaderOwner sobrescreve somente __init__, _pump, send_seed, retain e
drain. start/adopt/tarefas/cancelamento/_until/close de input/quiesce/ticket/
ausência/close e prova exata de PipeHandle são os mesmos objetos do e6ca.
send_seed e retain recusam, send_vector não recebe bytes do operador. Captura
os vetores públicos do reader, uma vez após READY; entrega UNKNOWN/SENT local.
RETAIN/WAIT mantêm stdin aberto até o processo terminar, diferente de send_seed
histórico. Fragmentação em chunks fixos/pausa0,02s sob o mesmo prazo12s.

Pump limita READY512/relatório2048/total2560 incrementalmente e drena excesso
descartando. IO não aproveita prefixo. drain aceita apenas exit real0 ou42
como transporte, conserva stdout total e bytes do relatório em observação
congelada. Parser do reader decide resultado. Processo/EOF/handles precisam
de prova positiva. Observação não substitui ticket/ausência/release.

## Gates medidos até a revisão de código

32 testes próprios passaram em1,30s; primeira seleção27/1,11s antes de ampliar
os contratos de erro. Os testes cobrem vetores exatos, stdin fechado/retido,
sem envio antes de READY ou duplicado, API privada recusada, deadline sem
renovação, host atrasado não confundido com leitor, exit real, limites total
e do relatório, IO após prefixo, BrokenPipe que não vira recusa válida,
cancelamento, spawn tardio/falho, falha de task e handle vivo que mantém HELD.

Ruff inicialmente apontou import não usado/linhas e formatação nos dois
arquivos novos; corrigidos sem mexer em código consumido. Seleção relacionada
e estáticos amplos ainda pendentes nesta seção. Não houve medição nativa de
tempo, pipe/EOF do Docker, shell, exit42, profile ou recursos de container.

## Seleção relacionada — falha ambiental preservada

A primeira seleção incluiu por engano a unidade histórica nativa
test_pinned_native_windows_pipe_handle_has_explicit_closed_state. Resultado:
167passed/1failed em7,13s. O CreateFile do segundo handle recebeu WinError5
dentro do sandbox; a rotina windows_utils.pipe fecha o primeiro no except.
Não é medição bem-sucedida de PipeHandles nem regressão atribuída ao owner.
Não repetir a prova nativa consumida nem elevar para refazê-la neste lote.
A seleção seguinte deve excluir explicitamente só essa unidade, medindo os
fakes de lifecycle e o reader. Nenhuma fonte/teste foi alterado ou tornado
skip para esconder a falha. Nenhum Docker, shell, banco ou processo filho.

A repetição explícita sem a unidade nativa passou:167passed/1deselected em
8,33s. Esse deselect delimita o escopo de fakes; não é suíte integral nem
substitui a medição nativa antiga. Foi anterior ao fix L1 abaixo.

## L1 da revisão52446 — vermelho primeiro e correção

Claude2 aceitou ligação de fontes/envio/falha fechada, mas exigiu corrigir
uma corrida de callbacks antes de integrar: EOF/wait podem chegar antes de
PipeHandle.handle virar None no callback de transporte. A prova imediata
reprovava um caminho saudável com STATE. Nenhum processo nativo envolvido.

Novo fake mantém stdout handle vivo por0,02s depois de EOF. Antes do fix:
1failed/32deselected em0,50s, exatamente STATE no drain final. Depois:33passed
em1,41s. O drain agora reavalia as duas provas a cada0,01s, limitado por
min(deadline absoluto12s, agora+CLOSE_SECONDS). Fechamento do stdin também
respeita esse deadline para aprovar resultado. Se o relógio do host esgota,
DEADLINE nunca é convertido em negativo esperado do leitor. Sem aumento de
prazo ou alteração do e6ca. Handles vivos continuam não sendo prova de release.

Ruff src/tests e mypy strict alvos3.11/3.14 haviam passado em328 arquivos;
format329 conforme antes do L1. Runtime executado apenas Windows3.11.3.

## Gates finais e aceite

- Seleção final de fakes/reader/owners: **168 passed,1deselected/7,61s**.
  O deselect é somente a unidade nativa histórica, preservada sem mudança.
- Ruff src/tests e check isolado E9/F63/F7/F82 do helper: aprovados.
- Format src/tests mais helper novo:329 arquivos conformes.
- Mypy strict src/tests, alvos3.11 e3.14:328 arquivos limpos.
- Fonte do owner:9727bytes, SHA-256
  d671880078d6d1f30067400ae3d3169e17458c471467027835ba2be6897b6c8f.
- Claude2/sessão51ea0d85/review60994 aceitou o L1 e o owner isolado, sem
  bloqueador. Perfil/caller e provas nativas continuam posteriores.

O revisor recomenda separar a unidade nativa por marcador. Para preservar o
arquivo histórico, nenhum marcador/skip foi acrescentado aqui. A seleção de
fakes usa explicitamente:

    -k 'not test_pinned_native_windows_pipe_handle_has_explicit_closed_state'

Não executar o arquivo histórico inteiro sob a alegação de ser só fakes.
Nenhum pacote/app/PG/browser integral foi refeito: produto/dependências
inalterados. Nenhuma prova de recursos reais deste owner foi inferida.

## Próximo incremento e limites

Perfil OpenStdintrue/StdinOncetrue para esse wrapper ainda ausente. Cleanup,
watchdog, host/entrada/exportador/proposta novos precisam de revisão própria.
O owner inicial envia o vetor exato, inclusive negativos; early-reject mais
BrokenPipe é falha de transporte e reprova, sem ser escondida pelo fault.
Não usar a variante pública para seed privado. Código aceito isoladamente.
Gateway indisponível; B1/B2/D090gate2/C1/SQL/produção seguem abertos.
