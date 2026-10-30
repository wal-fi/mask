# W1 — próximo ciclo nativo Oracle9.8, desenho sob delegação

2026-10-26. Somente desenho. Filho e owner privados aceitos pelo Claude2;
nenhuma ligação operacional, execução Docker ou liberação de SQL. Revisão
do procedimento e comandos antes de qualquer efeito real. A imagem87871290
contém fontes anteriores: não alegar que ela inclui o W1. Fontes e evidências
históricas não serão reescritas para admitir um artefato diferente.

## Portão obrigatório de idade do ciclo Desktop

A rodada D-120 teve uma pausa longa não conforme. Para impedir repetição,
o próximo controle terá admissão de idade em código, não só orientação.
Antes de iniciar A, todos os helpers/pins/scripts/comandos já revisados.
O relógio só será ancorado na invocação efetiva de A, não na preparação.

Fonte Windows nativa: GetTickCount64 (Kernel32, uint64), que inclui suspensão
e hibernação, sem depender de UTC/Stopwatch/.NET TickCount. Identidade do boot
pela propriedade local Win32_OperatingSystem.LastBootUpTime, convertida em
FILETIME UTC decimal canônico. Mudança dessa referência, mesmo por erro de
provider, aborta conservadoramente. Não inferir boot por UTC menos uptime.
CIM só local, em PowerShell NoProfile/NonInteractive e execução supervisionada
com prazo/saída limitados; falha/timeout não ganha fallback para relógio fraco.
GetTickCount64 amostrado depois da leitura de boot; tempo do probe é contado.
Não promete cancelamento absoluto de syscall/OS. Nenhum desses valores é
segredo, permissão para Docker ou prova de identidade do aplicativo.

Precisões da revisão: O1 usa A como referência; O2..O9 usam a observação
anterior. READY usa O9 e B usa READY, ambos intervalo0..30000ms inclusivo.
Teto global300000ms prevalece mesmo quando cada intervalo individual cabe;
o mínimo é90000ms. FAILED/ABORTED/B_CONSUMED são terminais. Após falha por
idade, restauração não exige frescor do ciclo, somente ownership/boot e
inventário fresco independente. O estado não volta para A nem é resetado.

F1 incorporado: registrar também GetSystemTimeAsFileTime, inteiro100ns UTC
em string. Exigir avanço UTC não negativo e concordância com ticks, tanto
desde A quanto desde último checkpoint, com tolerância2000ms+0,1% do avanço
do tick (comparação inteira, sem ponto flutuante). UTC não substitui tick;
qualquer divergência acima do teto aborta conservadoramente, inclusive NTP.
F2: manter igualdade exata do boot no núcleo puro. Binding fará várias
leituras de LastBootUpTime antes de qualquer Desktop para medir estabilidade;
se variar, não afrouxar tolerância automaticamente nem supor reboot separado
por minutos. Revisar a referência/política com os fatos antes de usar A/B.
Scripts PowerShell e runner chamarão o mesmo sampler Python fixado/hashado,
que usa kernel32 via ctypes; não haverá duas implementações de P/Invoke.

Estado fechado separado do restante do attempt: versão, boot, começo do
ciclo, último checkpoint, fase e número de observações. Contadores/FILETIME
serializados como strings decimais para evitar arredondamento por JSON/JS.
Leitura valida shape, tipos, largura≤20dígitos, uint64, ordem e continuidade.
Sem leadingzero, bool/float, chave extra, clock rollback ou fase fora de ordem.
Arquivo host escrito atomicamente antes do próximo efeito; failed/consumed
é terminal para B, sem reset/retry/novo A no mesmo attempt.

Limites propostos, em milissegundos, fixos no helper e na evidência:
- A→B no máximo300000, incluindo sleeps/hibernação e pausas de conversa.
- Nove observações O1..O9, em ordem, com ao menos10000ms desde checkpoint
  anterior e no máximo30000ms; cada uma revalida boot e identidade do app.
- READY apenas depois de O9, até30000ms depois dela. Não substitui pins,
  inventário, endpoint/contexto e exits do preflight Docker já exigidos.
- Admissão B uma vez, até30000ms de READY e dentro do teto A→B; conferida
  **na entrada real do runner B**, não apenas no comando anterior. Escrever
  B_CONSUMED antes de CLI/create. Operação B tem watchdog próprio revisado;
  não impor esse teto de5min à duração da suíte/carga depois da admissão.

Controles A/Observe/Ready/B serão invocados em blocos menores que60s. Se
idade/boot falhar, sem B/create. Para restaurar Desktop próprio antes de B:
reobter inventário Docker vazio com exit0 e revalidar PID+FILETIME da instância
iniciada pelo attempt e mesmo boot. Só então stop dessa instância, com exit0
e ausência observada. Se já estava ativo, boot mudou, identidade divergiu,
CLI não respondeu ou apareceu recurso alheio, preservar o estado e registrar
o motivo; não parar app alheio, matar processos por nome ou fazer prune.
Cleanup pós-B exige também inspeção/remoção dos próprios CIDs por identidade.
Freshness não é autoridade para stop e não substitui ownership de recursos.

Matriz antes de uso: limites exatos±1ms, três pausas incluindo2h, suspensão
simulada no contador, rollback, boot diferente, amostra malformada/truncada,
etapa repetida/saltada, READY/B reaplicado, contagem de observações falsa,
JSON acima de2^53 preservado, falha de clock/CIM, abort sem entrar B e caminho
de restauração pré-B sem recurso próprio ou sem inventário confiável.
Primeiro núcleo puro com fakes; binding Windows medido separadamente depois
de revisão. Scripts/runner integrados também terão testes e revisão próprios.

Fontes primárias:
- https://learn.microsoft.com/en-us/windows/win32/sysinfo/windows-time
- https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-gettickcount64
- https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-operatingsystem

## Artefato e prova W1 depois do portão

Construir novo wheel determinístico de fontes W1 fechadas. Reutilizar apenas
primitivas e dependências públicas já admitidas, com novo manifesto/raiz e
evidência própria; não alterar pins históricos para produzir falso replay.
Instalar sem rede sobre a fundação1546afef em novo CID próprio e formar nova
imagem candidata com inventário/atestação completos. Mesmas libs temporárias
aceitas para integração; patches/minimalização continuam gate antes de release.
O wheel deve incluir guard, S1, codec v2, filho e owner, importáveis via -I-B
fora de qualquer checkout/PYTHONPATH. Sem copiar fontes soltas na prova W1.

Prova nativa exige plano detalhado próprio antes de código/execução: PG16
descartável isolado, somente dados sintéticos/roles do teste, rede/TLS/PKI
próprios, conninfo hostaddr fixado, creds só por canal permitido. Não usar
banco/credenciais existentes. Controller PID1 aplica guard antes de secrets,
confere interpretador instalado/flags e usa APIs W1 reais sob perfil nonroot,
RO/caps0/NNP/seccomp/AS/pids/memory/swap/tmpfs previamente fixado.

Matriz obrigatória: guard/INIT máximo, masking/derived/exceptions/HMAC/OIDs,
conexão única, S1 baseline e mudanças, erro recuperável→query seguinte,
blackhole pós-auth, prazo/reap real, Popen tardio sem segredo, EOF em idle e
durante driver, coalescência frame/DONE, sessões concorrentes sem FD cruzado,
envio lento/pin e morte de PID1/namespace. Maior frame/linhas e VmPeak sob
AS256MiB devem ser medidos sem aumentar limites no decorrer da rodada.
Esta proposta não presume que todos esses casos cabem numa única execução;
lotes físicos com seus próprios comandos/falha/cleanup serão definidos antes.
Memória total/C1/D-119 e B-1 fim a fim exigem evidência própria, não são fechados
por uma conexão bem-sucedida ou por testes simulados.
