# B-2 — próximo diagnóstico de cobertura, não contrato de produção

**2026-10-20: diagnóstico sob delegação, preparado/revisado e executado uma
vez após correções. Quatro casos com resultados esperados e cleanup
confirmado; evidência em `PHASE-9-STAGE-8-LINUX-AS-VALIDATION.md`. Sem worker,
mudança de plataforma suportada ou liberação de SQL.**

## Problema e alternativa a avaliar

B2-B2a provou a lacuna: seções compartilhadas de 40 MiB coexistiram sob cota
privada Windows de 32 MiB. Essa reprovação não será apagada ou reinterpretada.
D-113–D-115 limitam representação/saída, mas não o processo que materializa
libpq/AST/masking. Repetir apenas pressão privada não resolve o vetor conhecido.

Avaliar um perfil **Linux isolado em container descartável**, sem presumir
que será o SO de produção. Primeiro testar a combinação de espaço de endereços
limitado e domínio de memória/processos, antes de integrar o worker. Windows
nativo continua não certificado para SQL PGWire; não remover APIs existentes.
O destino real ainda depende de informação externa, não desta escolha de laboratório.

## Contratos documentados, não resultados

- RLIMIT_AS limita espaço virtual; brk/mmap/mremap podem falhar com ENOMEM.
  Não é contador de RAM/commit privado nem limite de memória do kernel.
  Filhos herdam limites e exec os preserva. Configurar soft=hard antes de
  nascer o workload evita janela de atribuição posterior; conferir o limite
  efetivo, sem CAP_SYS_RESOURCE. [Linux man-pages](https://man7.org/linux/man-pages/man2/getrlimit.2.html)
  e [Python resource](https://docs.python.org/3.11/library/resource.html).
- Cgroup v2 contabiliza anon/file/shmem e buffers de socket; `memory.max`
  **pode ter excesso temporário**, segundo o próprio contrato. Não resolve
  sozinho a asserção histórica estrita `peak<=quota`. Não tratar estatísticas
  como disjuntas: shmem já integra file. [Kernel cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html).
- Docker sem limites é ilimitado; memória e swap exigem configuração explícita.
  `--memory-swap` igual a `--memory` impede swap nesse perfil. O domínio nasce
  com limites externos finitos; `--ulimit as` não é suportado. AS será aplicado
  no supervisor antes de criar membros, conforme a sequência abaixo.
  [Restrições](https://docs.docker.com/engine/containers/resource_constraints/)
  e [docker run](https://docs.docker.com/reference/cli/docker/container/run/).

**Inferência a testar, não garantia:** RLIMIT_AS pode cobrir a expansão de
mapeamentos que escapou do limite privado Windows; o domínio externo pode
conter custos não cobertos pelo espaço virtual individual. A composição não
prova automaticamente limite total: contabilização, kernel, processos extras,
cleanup, excessos transitórios e custo do pai continuam requisitos separados.

## Menor lote candidato

1. Somente diagnóstico sintético, sem produto, rede, PostgreSQL, secrets,
   código de produção ou Docker socket dentro do container. Revisar harness
   antes de executar. Imagem oficial Python por digest, versão/base registradas;
   disponibilidade, origem e tamanho conferidos antes de eventual download,
   respeitando as permissões efetivas da ferramenta (sem bypass). Não
   alterar Python do host ou .venv, serviço Docker ou configuração da VM.
2. Um container próprio por caso, sem restart. Rede none, filesystem read-only,
   UID não-root, cap-drop ALL/no-new-privileges, core=0, nofile=64, pids=16,
   CPU=1 e shm-size=1 MiB. Sem init/shell extra. Limites
   externos predeclarados: memória/swap total **192 MiB**, para supervisor e
   até dois membros com controle positivo de 40 MiB cada mais baselines/margem.
   Não é nova cota de produção, substituição dos 32 MiB ou gate B-2 aprovado.
   Logging driver none, sem log de payload na VM; conferir attach vivo antes
   da carga. Se não funcionar, falha de harness, sem fallback para log ilimitado.
3. Nos casos limitados, supervisor Python de uma única thread aplica a si
   **soft=hard RLIMIT_AS 32 MiB antes de criar qualquer membro**; seus filhos
   herdam o limite efetivo e exec o preserva. Não usar preexec_fn, prlimit
   posterior ao spawn, auxiliar de limite, thread interna ou restauração
   privilegiada. Supervisor também fica sujeito a AS após essa aplicação;
   seu startup anterior só pertence ao domínio externo e será registrado
   separadamente, nunca declarado sob AS desde a criação.
   Antes de aplicar AS, conferir VmSize do supervisor
   <=28 MiB (folga predeclarada de 4 MiB); exceder é incompatível, não tentar
   setrlimit abaixo do uso atual. ENOMEM no supervisor/spawn/coleta é falha
   de coleta, nunca prova de contenção do membro. Membro reporta o
   limite próprio antes de receber go/payload. Se supervisor ou interpretador
   mínimo não couber, registrar incompatível, não elevar até verde. Controle
   separado sem AS continua sob domínio externo finito. **32 MiB de espaço
   virtual Linux não equivale a 32 MiB de commit privado Windows.**
4. Quatro casos: baseline sob AS, com um membro mantendo 1 MiB e folga de
   VmSize registrada; controle sem AS com um membro mantendo bytearray de
   40 MiB e outro MAP_SHARED anônimo de 40 MiB; dois membros acumulando
   bytearray em passos de 4 MiB até recusa (até 40 MiB cada); dois acumulando
   MAP_SHARED anônimo nos mesmos passos, sem liberar os mapas anteriores.
   Registrar última alocação aceita e pedido/errno na recusa, não só recusar
   uma alocação maior que a cota inteira. Sem matriz maior ainda.
   Registrar fases criar/mapear/tocar/manter, negação observada, limites
   efetivos via `getrlimit(RLIMIT_AS)` (não captura textual de /proc/limits),
   inventário, VmSize/VmPeak, cgroup.current/peak/events/stat e cleanup.
   Métricas distintas permanecem distintas; ausência de erro ou uma amostra
   baixa não provam imposição. Não resetar picos para esconder excedentes.
   Para membros limitados, VmPeak<=33.554.432 e negação por memória devem ser
   verificadas distintamente; supervisor tem seu startup anterior separado.
   Classificar antes de executar:
   **imposição observada** = MemoryError/ENOMEM na alocação do próprio membro,
   limite próprio conferido, pico <=32 MiB e blocos anteriores tocados/retidos
   (também bytearray) até a amostra; não exige pico exatamente igual ao teto,
   pois degraus de 4 MiB podem parar antes. **FAIL** = sem recusa até 40 MiB
   ou pico acima do teto. **Inconclusivo** = outro errno, sinal, timeout ou
   falha de supervisor/coleta. Baseline incompatível não aprova pressão.
5. No máximo 80 MiB de payload sintético coexistente e três processos conhecidos
   (supervisor e dois membros); limite pids inclui threads, não justifica
   ignorar processo extra. Relatório até 64 KiB/caso, 1 MiB/lote, protocolo
   fixo sem repr de erro nativo. Sem exportar handles/payload a outro domínio.
6. Criar parado, guardar ID e inspecionar antes de start: Memory=MemorySwap=
   201.326.592, PidsLimit=16, rede none, read-only, user não-root, caps/security,
   limites esperados e mounts. Só um arquivo próprio de harness montado RO,
   hash conferido antes/depois, nenhum mount gravável ou Docker socket.
   Dentro, antes dos membros: cgroup v2 efetivo, memory.max, swap.max=0,
   pids.max, presença de memory.peak, limites do supervisor e kernel. Não
   confiar só no docker inspect ou em valor declarado. Relatório por stdout,
   limitado no observador do host; sem docker exec durante casos.
7. Deadline de 30 s/caso e 180 s/lote, watchdog independente **no host**;
   excedente ou
   falha de coleta torna o caso não aprovado. Observador externo confere
   exit/inventário do container, sem liberar crédito por EOF/pedido de kill.
   Limpeza só por ID exato de recursos próprios; falha interrompe o lote.
   Supervisor PID1 faz reap, trata término explicitamente e não presume
   default SIGTERM suficiente. Observador pode pedir kill só do ID próprio
   em timeout, mas precisa confirmar término real e processos ausentes.
   Registrar events oom/oom_kill e State.OOMKilled sem inferir causa só de -9.

**Lacunas predeclaradas:** nenhum caso satura os 192 MiB externos; imposição
de memory.max **não exercitada**. /dev/shm/tmpfs por write sem mmap, page cache,
kernel, sockets/pipes, VM/containerd/dockerd fora do domínio e possíveis
excessos temporários não são cobertos pelo AS. /dev/shm pequeno não elimina
esses vetores. Imports do worker, threads/arenas/TLS e orçamento do pai não
foram medidos. Não somar shmem a file nem chamar VmPeak de RAM/commit.
MAP_SHARED anônimo usa shmem do kernel, não o mount /dev/shm; shm-size=1 MiB
não limita nem explica a recusa desse caso. Runtime/containerd/dockerd/VM
ficam fora do domínio de 192 MiB. Não alegar ausência de logging em todo host.

Após revisão, o harness e o comando ainda serão preparados/revisados, sem
executar produto ou pressão não declarada. Não começar esse diagnóstico
enquanto a suíte integral D-115 usa o ambiente; evita disputa e medição ambígua.

**Preflight de CLI declarado antes da execução:** somente `docker version`,
`docker ps -aq --no-trunc` e `docker image inspect <digest>`; saída capturada
até 256 KiB e prazo de 5 s por chamada pelo observador. Sem probes extras de
processo/payload, docker exec ou pressão fora dos quatro casos. Ligar o
Desktop existente (oculto) e baixar somente a imagem pinada são preparação
separada, sujeita às permissões da ferramenta; não mudar daemon/WSL/Python.
O estado inicial do Desktop é desligado, sem containers em uso pela D-115;
reconferir antes da carga. Se outro uso aparecer, não iniciar a rodada.

## Saída e trabalho que não desaparece

Registrar todos os casos, inclusive FAIL/incompatível/não executado. Resultado
verde pode justificar o próximo experimento com imports reais e depois o
worker interno, nunca SQL no listener por inferência. Antes de produção:
orçamento global real incluindo pai/auxiliares/gerações/TLS, limites desde
spawn, quotas/margens com semântica honesta, cleanup em falhas, snapshots/lease
e pipeline completo. Não afirmar que um limite de espaço virtual é toda a
memória do host. B-1 fim a fim, B-2 e D-090 gate 2 seguem abertos.

## Preparação e revisão

Claude2 revisou somente leitura, sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`:
sete bloqueadores no primeiro rascunho (aplicação AS, tmpfs, pressão acumulada,
controle compartilhado, domínio externo não exercitado, preflight efetivo,
imagem/mount/relatório). Os ajustes acima respondem a esses pontos, com escolha
de supervisor também sob AS, em vez do preexec_fn sugerido. Na rerevisão,
Claude2 não apontou bloqueador para preparar/revisar o harness; pediu preflight
de VmSize/folga, classificação dos casos, distinção shm-size/MAP_SHARED e
limite de logging, agora explicitados acima. As condições do harness ainda
precisam de revisão antes da execução; não são aprovação por silêncio.
Revisor não executou nada nem certificou B-2 ou produto. Na revisão do
harness real, bloqueou recusa inicial sem bloco retido e ausência de
identidade durável/cleanup para perfil divergente. Corrigidos com regressões;
rerevisão não apontou bloqueador restante, condicionada a declarar os
preflights exatos (acima). Rodada única posterior registrou baseline,
controle positivo e recusa privada/shared; B-2 continua aberto, conforme
lacunas e evidência própria. O trecho de consulta abaixo é histórico anterior
à preparação, não afirma que nenhum caso foi executado depois.

Consulta somente leitura do executor: Docker disponível com backend Linux,
cgroup2/cgroupfs, kernel `6.18.54.1-microsoft-standard-WSL2`; nenhuma imagem
oficial Python local. A validação sintática de `docker create --ulimit as=...`
foi recusada pelo próprio CLI (`invalid ulimit type: as`), antes de criar
container ou chamar o daemon. Nenhum payload/experimento/novo container foi
executado. Esses fatos não certificam Linux de produção ou Windows nativo.
