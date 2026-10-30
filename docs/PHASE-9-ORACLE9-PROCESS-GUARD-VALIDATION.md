# Oracle9 — proteção pré-segredo de processos, 2026-10-26

**ORACLE9_PROCESS_GUARD_VERIFIED/exit0**, primeira e única execução nativa
deste incremento. Um container secretless na candidata fixa87871290; sem
pull/rebuild/install, rede, SQL, banco, segredo ou novo chamador operacional.
O gateway ainda não está disponível para uso. B-1 fim a fim, B-2/D-090 e SQL
seguem abertos. Escolha técnica sob delegação, não aprovação individual.

## Código e revisão

Novo src/maskgw/runtime/linux_guard.py, sem chamador: gate Linux antes de
bindings, somente stdlib. Papéis fechados controllerPID1/worker com PPID
esperado; UID/GID real/efetivo/salvo/filesystem10001, grupos restritos,
cinco conjuntos de capabilities0, NoNewPrivs1/Seccomp2, uma thread Python
e nativa antes/depois. CORE0, AS finito/hard sem elevar limite anterior,
VmSize atual+8MiB de margem de bootstrap estritamente menor que AS antes
de mutação, comparação com RLIM_INFINITY do SO. Margem não é limite de
allocator nem calibração de capacidade. DUMPABLE0/PDEATHSIG relidos, PPID
conferido antes/depois; fatos imutáveis, erros em categoria fechada sem
mensagem/chaining do SO. Falha exige encerrar/recolher o processo pelo dono.

Executado no processo final depois de exec, antes de material secreto; o
módulo não entrega segredos, spawn nem protocolo. Fork sem exec de processo
com segredo não está autorizado pelo contrato. Janela exec→guard contém só
entradas públicas. Guard não é proteção contra comprometimento do código
confiável, não garante que ele depois não altere dumpable. PDEATHSIG trata
a thread que criou o processo; esta prova usa thread principal de lifetime
integral. Mudança posterior de credenciais/exec invalida a proteção.

Contrato, módulo, sonda e host revisados em sequência pelo Claude2, somente
leitura, sem segundo escritor. Findings corrigidos antes da rodada:
- VmSize/margem/infinity:3regressões vermelhas primeiro,53testes guard verdes.
- W1: negativo de PPID errado usava PID do próprio filho/cláusula errada;
  regressão vermelha, fix distinto de PID/PPID, releitura de AS/dumpable1.
- P1 do host: ligar diretamente bytes capturados ao estado; regressão
  vermelha mostrou consumo antes desse pin, depois fix inicial/final e
  mais3variantes de hash verdes. Revisão aceitou sob delta testado, sem
  necessidade de nova revisão do delta, antes de executar A.
- Procedimento v1 foi recusado pelo parserPS por chave duplicada causada
  por substituição ampla de caminho. Nenhuma ação foi invocada. v2 corrigiu
  uma linha; v3 incorporou P1/novos pins. As três propostas preservadas.

Fontes congeladas durante A–Off e rechecadas depois:
- guard dd10fb725b846ca097d7bef8b434fa4846f80e36216b34a3a16e658f1d15d0b4
- deploy/oracle9_process_probe.py
  0b3b46b1abb90a743920aa333e5a04d109db9503a133f2168c7edbed897e1332
- docs/poc/oracle9_process_prepare.py
  5d258c28b373956d5d96f03f34c074e74420900e17d2ce5935edebf7d73a1326
- procedurev3 0d26f5a446d53fb1ab90f1a29ebaf3e9024f779762a4fd06aa2a92b2862fe10f.

## Gates locais e procedimento

Windows nativo3.11.3: **106novos** (53guard+26sonda+27host), **695relacionados**,
todos aprovados. Estes usam fakes/recusa de plataforma, não syscallLinux.
Ruff check src/tests e mypy strict alvos3.11/3.14:283arquivos limpos; escopo
do módulo e3testes também limpo com alvo Linux3.14. Runtime3.14 não medido
neste incremento. Format6arquivos; scripts laboratório só lint de sintaxe
E9/F63/F7/F82, sem alegar lint/mypy completos desses scripts. Não houve
mudança de UI/pipeline/adapter ou repetição da suíte PG integral sem motivo.

Rootf6c89e76/taskb2f6ae6f557943fbadde9da9705cc85f, estado inicial964b0d31.
Source_admission conferiu119arquivos originais do produto contra d0909fcf;
guard novo separado. Não chamou context/install/commit antigos; reutilizou
apenas funções de perfil/ownership congeladas401afa8c, em dois namespaces:
imagem com label original, CID com label do probe novo. Label manifest359a
indica só a origem instalada, não um wheel/contexto novo.

Desktop começou Off. A lançou oculto, ambiente saneado e depois restaurado
no shell; PID31052, FileTimeUtc134375004832370747 mantido em inteiro64.
Observe em3chamadas3×10s:9observações reais de identidade, exits0. Houve
intervalo entre chamadas (primeiro bloco15:01–15:02Z, demais17:18–17:19Z);
**90s de espera comandada, não90s contínuos**. Ready/exit0 antes da única B.

**13CLI no corpo, todos exit0**, soma13,622s de durações CLI, não walltime.
Watchdog180s não disparou, término e thread conferidos. Um CID próprio:
a9cfc5652e9e9be182126be89d8917fbba763a3687060a6568faa9e580c5b887,
removido sem force após inspect Runningfalse/Pid0; filtro de ausência e
inventário final vazio conferidos. Diff readonly vazio. AllowStop confirmou
identidade/cleanup antes de restore, que fez2CLI com exit0 (ps e desktopstop).
Off efetivamente confirmado **2026-10-26T17:21:32.6804182Z**. Nenhuma imagem
removida, nenhum container/serviço existente tocado, nenhum retry.

**Desvio de procedimento:** houve cerca de2h16 entre os blocos de observação,
contrário à regra anterior de não pausar/abortar antes de B em interrupção
(DIRECTORY-RESTORATION-PLAN §203 e DEPENDENCIES-PLAN §72). A rodada não foi
contínua, e o Desktop ficou iniciado pela tentativa durante esse intervalo.
Identidade foi conferida de novo, inventários antes/depois vazios e fontes
congeladas foram revalidadas depois. A revisão final aceitou os fatos do
guard com esse desvio explicitado, sem transformar a pausa em procedimento
aprovado. Próximo ciclo deve impor idade máxima por relógio monotônico em
código entre A/Observe/Ready/B, abortando sem B se vencer; não repetir esta
medição retroativamente ou afrouxar a regra para esconder o desvio.

## Medição nativa e diferenciais

Imagem sha256:87871290b01b0e4b8cd9dd90b8001a89ff4e04bd018e12c01ddbff8d6b16483a,
Oracle9.8/Python3.11.13, kernel6.18.54.1-microsoft-standard-WSL2. Perfil
UID/GID10001/RO/networknone/capdropALL/NNP,512MiB/swap0/pids32/CPU1/
nofile128/core0/tmpfs16MiB/shm8MiB. Limites observados:
memory.max536870912, memory.swap.max0, pids.max32, cpu.max100000100000.
Não é host RHEL/Oraclebaremetal/SELinux/FIPS nem contenção total comprovada.

CORE0/DUMPABLE0 efetivos; fs.suid_dumpable0;
core_pattern `|/wsl-capture-crash %t %E %p %s`; Yama ptrace_scope1.
Nenhum sysctl/kernel foi modificado e não houve ensaio de core/segredo real.
Regra bloqueante suid_dumpable2+pipe não foi atingida. A observação não
certifica outra combinação/kernel nem swap do Windows.

Ambos filhos fork+exec, mesmo UID/perfil/paiPID1, mesmo guard/AS256MiB/
PDEATHSIG9. Só o controle deliberadamente voltou dumpable1, confirmado
antes de imports/canário público/READY. Protegido permaneceu0. Parent
protegido0/AS384MiB fez as tentativas **só depois** de READY. Comparou
memória somente com canário público, registrando booleanos, sem conteúdo
de memória/environ. Nenhum processo externo foi acessado.

| interface | positivo dumpable1 | protegido dumpable0 |
|---|---|---|
| /proc/PID/mem open+pread | bytes iguais ao canário | EACCES13 |
| process_vm_readv | bytes iguais ao canário | EPERM1 |
| ptrace attach/waitstop/detach/retomada | todas etapas confirmadas | EPERM1 |
| /proc/PID/environ | conjunto igual ao env público | EACCES13 |
| /proc/PID/fd | listagem permitida | EACCES13 |

Os5diferenciais passaram; nenhuma interface contou “ambos negados” como
prova. Ambos filhos terminaram exit0 e seus pipes foram fechados/recolhidos.
Imports reais do corpo D-118 depois do guard, sem abrir conexão:
controller VmSize/VmPeak91184kB/VmRSS53240kB, positivo91256/91256/53152kB,
protegido91248/91248/53728kB, todos Threads1. São observações de import,
não máximo de worker/query/concorrência nem cota agregada. ABI ctypes
conferida apenas Linuxamd64, não outras arquiteturas.

Pai intermediárioPID9 saiu0 após netoPID10 emitir READY protegido; neto
ignorava EOF, então não podia declarar fim por canal fechado. PID1 recolheu
status exato **SIGKILL9** do neto reparentado, sem zumbi. Negativo PID11
recebeu PPID esperado2 diferente de si/do pai real1; recusou PARENT antes
de READY, AS herdado e dumpable1 permaneceram iguais. Ao fim, proc sóPID1.

## Evidências e limites

docs/poc/evidence/:
- oracle9-process-attempt1-20261026.json:119932bytes,
  df6ae40585bd4509efd7cf016a8cf65b5cf6b99ae5cc5143d8363d8a796ad528
- oracle9-process-summary-20261026.json:10248bytes,
  bc9348dfa196caa7b7420f57744b9be8a2df609afa6d165d979da99158fa50a0
- native.stdout: SHA63e7015534f06fbbf212eb3821fddbd6a4d10f7a9870e55f04892afcdf3376ec,
  preservado com tamanho/hash/base64 no envelope, assim como estados,
  observações, inspects, versão, resultado/restore e diff originais.

PostOff: pins completos/estado/int64/artefatos e119fontes originais
revalidados. CLIstderr e stderr dos filhos são descartados, não preservados.
Guard foi copiado e compilado dos bytes pinados; o wheel candidato
**ainda não inclui** esse módulo. Não é sonda de um novo pacote instalado.

Morte do PID1/namespace, EOF do futuro loop, pressão/capacidade/global,
protocolo/snapshot secreto, conexão upstream, SQL/read-only/masking fim a
fim, D-112/D-114 operacionais, novo release/patch e IDE/MCP/Admin permanecem
pendentes. `pid1_death_proved=false` explícito. Quando o pai éPID1, a
checagem PPID1 não distingue adoção; morte do namespace terá prova própria.
Não cria perfil C1 pronto nem fecha B-1/B-2/D-090. Sem commit/push/deploy,
quota observada/job agendado ou troca de conta. Revisão final da evidência
antecede uso desses fatos na integração do worker.

Revisão final somente leitura do Claude2 aceitou a consistência da evidência
e os fatos guard dd10fb72 como entrada fixa do desenho da integração privada
do worker, condicionada à declaração do desvio acima, incorporada. Nenhum
novo finding de código/evidência bloqueante. Antes de uso operacional, novo
wheel instalado deverá incluir o guard e provar a mesma ordem pré-segredo.
