# Canal público do leitor PG16 — composição antes do código

2026-10-30, sob delegação. Leitor efe69a79/núcleo80219269 aceito e publicado
em aed24fb. Próximo incremento: somente owner público e fakes, sem caller,
novo perfil operacional, raiz, DockerCLI, shell, servidor ou credencial.
O perfil/cleanup/watchdog/host/entrada/exportador próprios continuam posteriores.
Fontes e6ca/T4/PG16 da rodada anterior ficam congeladas.

## Decisões fechadas antes da implementação

Criar docs/poc/pg16_shell_owner.py, variante explícita de ManagedBootstrap do
e6ca pinado, capturando também o reader efe69a79 por hash. Sem alterar globals,
AST ou funções históricas. Seus namespaces capturados são privados e imutáveis
por contrato do coordenador confiável. Continua CPython3.11.3/Proactor/stdlibs
pinados, mesmo docker.exe/contexto e ambiente público fechado, stderrDEVNULL.

Constructor(task,cid,case) só aceita task32hex, CID64hex e enum fechado do
reader capturado. Cria Target(P, imagemcf78, CORE_SHA); source do wrapper
completo/hash ficam no registro imutável do owner. Antes de start, o futuro
coordenador deve provar o CID/perfil/command e labels ligados a esse wrapper
exato. Target não é prova de inspect e o owner não concede autoridade create.

O comando continua somente docker start --attach --interactive CID, com
stdinPIPE/stdoutPIPE/stderrDEVNULL. start/adopt/task/shield/cancel/quiesce/
ticket/ausência/close herdados são os mesmos objetos do e6ca. O owner existe
antes do spawn e mantém processos/handles/tarefas incertos em HELD/loop.

Overrides declarados: __init__, _pump, send_seed, retain, drain. Novo método
send_vector e coroutine _feed_vector, decorados/registrados pelo mecanismo
original. Nenhuma alteração em start, _until, _adopt, _ensure_pumps, _wait,
_close_input, quiesce, close ou prova dos PipeHandles. send_seed e retain
recusam antes de qualquer efeito: essa variante só envia canários públicos.

## Envio público e EOF/QUIET

- send_vector não recebe bytes nem Seed. Envia somente o Vector capturado no
  constructor, uma vez e após READY canônico do núcleo/task/UID70/PID1.
- Prazo absoluto12s desde antes do spawn cobre READY e envio; não é renovado
  por chunk. deliveryUNKNOWN antes do primeiro write; SENT só depois de todos
  os writes/drains concluídos sem erro/prazo/cancelamento. SENT é handoff local,
  não recepção/aplicação no container. Nenhuma escrita pode começar depois de
  quiesce/fault/deadline. Todos os pumps são registrados antes de await.
- FRAGMENTED: chunks fechados do vetor, com pausa0,02s entre chunks, sob o
  mesmo deadline. Prova writes separados, sem inventar fronteiras de read do
  kernel. Os demais casos têm um único chunk. Não há taxa configurável.
- hold_open=false: fecha e aguarda stdin pelo _close_input herdado, orçamento3s.
  hold_open=true (RETAIN e WAIT_*): conserva stdin aberto durante a leitura;
  só fecha após processo observado terminado, ou durante quiesce do aborto.
  Assim RETAIN pode realmente observar QUIET; não reutilizar send_seed e6ca,
  que fecharia o pipe e mudaria o oráculo para EOF.
- Matriz de erros de header pode ser cortada ao prefixo16 (ou15 parcial)
  em uma política pública explícita antes da rodada, se necessária para não
  alimentar corpo após rejeição; esse owner inicial envia os vetores exatos.
  Não ignorar BrokenPipe/erro de close só porque um fault esperado apareceu.
  Negativo que teve erro de transporte não é resultado comprovado: aborta e
  registra. Não prometer antecipadamente que todos os23 casos funcionarão no
  mesmo caminho; desenho nativo fixará a entrega exata antes de executar.

## Recepção e resultado

_pump variante do e6ca conserva validação do READY≤512, limite incremental,
erro pegajoso e drenagem/descarte sem deixar PID1 preso no pipe. Limite total
de stdout = READY≤512 + corpo de relatório≤2048 =2560bytes, read4096. Prefixo
de sucesso seguido de IO/limite nunca vira resultado. Não devolve raw em erro.

drain público só roda em ACTIVE. Prazo absoluto12s desde o spawn para resultado
e EOF. Prova de handles tem até3s, limitada também ao deadline de12s para
aprovar resultado; quiesce de aborto continua com seu orçamento próprio.
Só aceita returncode real0
ou42 como transporte concluído; código42 não vira sucesso de aplicação nem
Fault.EXIT prematuro, pois o parser de casos decide se é a recusa esperada.
Qualquer outro exit é EXIT. Espera tasks stdout/wait, fecha stdin mantido
aberto somente depois de returncode observado, exige EOF e handles fechados.

Retorna registro público congelado com returncode real, stdout_bytes total,
report_bytes depois do READY e output bytes. O total deve concordar com
READY+len(output), contagem preservada mesmo se os bytes forem descartados
em falha. O futuro coordenador chama parse_report(raw,returncode,task,case);
nunca usa código fixo0 para reparsear. Observação de processo não substitui
quiesce→ticket→ausência posterior CID→close, mesmo em conclusão natural.

## Gates de fakes antes de qualquer caller

API/argv/ambiente fechados, case/task/CID/source inválidos antes de spawn,
nenhum envio antes de READY e só uma vez; entrega exata dos vetores; RETAIN
não fecha antes do resultado, EOF normal fecha; fragmentação/prazo global;
spawn tardio/cancelamento/falha de task e stdout; limite incremental e IO
após relatório; exit0/42/outros, contagens reais e oráculos; quiesce/handle
vivo/ausência anterior ou de outro CID não liberam. Sem processo real nos testes.

Ainda não há perfil com OpenStdintrue/StdinOncetrue para este wrapper, nem
watchdog/cleanup que o reconheça. Não adaptar o validador histórico stdinfalse
por monkeypatch/projeção que esconda divergências. Próximo incremento deverá
validar explicitamente as diferenças e preservar todos os outros predicados.
Resumo nativo deverá publicar returncode/stdout_bytes e rótulo do inspect
final. Nenhum gate de produto é fechado; Gateway continua indisponível.

## Precisões da revisão10641, antes do código

Claude2 aceitou o incremento de owner/fakes com estas precisões:

1. Nos WAIT_*, spawn/attach + READY/envio + leitor8s + impressão/saída do
   PID1 + saída CLI/EOF precisam caber nos12s absolutos do host. A margem
   restante ainda não foi medida nesse caminho. Se CLI/EOF chegam depois
   de12s, é falha DEADLINE do host, nunca o fault=DEADLINE esperado do leitor.
   Fake obrigatório: leitor terminou em8s, CLI só depois de12s; host recusa.
   Nenhum teto será ampliado sem revisão própria.
2. Código42 do PID1 propagado como returncode42 do docker start --attach
   ainda não foi medido. A rodada nativa deverá confrontar CLI real e
   ExitCode do inspect pós-execução; divergência reprova, sem adaptação.
3. Política de negativos de header (wire inteiro ou prefixo) será fechada
   no desenho nativo antes de qualquer efeito. O owner inicial envia vetor
   exato, sem ignorar IO/BrokenPipe. Oráculos efe69a79 permanecem intactos.
