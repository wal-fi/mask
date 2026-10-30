# Oracle Linux local — bootstrap de proteção dos processos

2026-10-26. Escolha técnica sob a delegação vigente, sujeita à revisão do
Claude2. Não declara aprovação individual, fechamento de B-2 ou liberação
de SQL. A candidata87871290 foi aceita na revisão final da instalação.

## Incremento e limites

Implementar `runtime/linux_guard.py`, sem chamador operacional: proteção
do processo **final**, depois de exec e antes de receber/ler segredos.
Somente stdlib; nenhuma alteração de dependência, registry, D-107,
PGWire/MCP, catálogo, configuração de ambiente ou comportamento existente.
O módulo pode ser importado no Windows, mas a chamada real nesse SO recusa
antes de tentar qualquer syscall/limite. Testes locais usam backend falso.

Contrato fechado: papel controller exige PID1; papel worker exige PID e PPID
esperado, diferente de si e positivo. Todos os IDs real/efetivo/salvo devem
ser o UID/GID não root10001 e grupos apenas10001; sem capacidades em nenhum
conjunto, NoNewPrivs1 e Seccomp2 no perfil Docker alvo. Não se eleva privilégio
nem se muda UID/GID. CORE soft/hard0; AS soft/hard finito, faixa64MiB–4GiB,
sem aumentar limite anterior. Valores são argumentos internos validados,
não defaults operacionais nem equivalência com a memória cobrada pelo cgroup.

Aplicar PR_SET_DUMPABLE0 e conferir PR_GET_DUMPABLE; worker aplica
PR_SET_PDEATHSIG(SIGKILL), confere PR_GET_PDEATHSIG e PPID antes/depois
para fechar a corrida de pai já morto. Controller confere PDEATHSIG0.
AS/CORE são aplicados e relidos antes de devolver fatos imutáveis, sem
mensagens do SO, caminhos, ambiente ou buffers em erro/repr. Qualquer falha
recusa a admissão. O chamador futuro tem obrigação de encerrar o processo
que falhou; a função não mata silenciosamente um controlador do chamador.
Nenhum sucesso parcial é prontidão para ler segredos.

PDEATHSIG refere-se à thread que cria o processo, não a qualquer thread do
pai. O spawn futuro deve partir de thread com lifetime de todo o worker;
esta prova usa somente a thread principal. Nenhum exec/troca de credenciais
depois da proteção. A proteção é propriedade do processo no instante da
checagem, não autenticação de código malicioso que depois a desative.

## Prova nativa proposta, somente depois de revisão do código/procedimento

Uma rodada secretless na candidata fixa
sha256:87871290b01b0e4b8cd9dd90b8001a89ff4e04bd018e12c01ddbff8d6b16483a,
sem pull/rebuild/install/SQL/DB. Novo payload público fora do pacote carrega
os bytes exatos/hash do módulo novo, pois o wheel instalado antecede esse
módulo. Isso prova o módulo copiado, **não** um novo wheel instalado.

Perfil: UID/GID10001, rootfsRO, networknone, capdropALL/NNP/seccomp padrão,
memory512MiB/swapadicional0/pids32/CPU1/nofile128/core0, tmpfs16MiB/shm8MiB,
sem volume/mount de host/porta/device/log persistente/restart. Controller
PID1 usa AS384MiB; filhos AS256MiB. Estes números são somente para o ensaio,
não capacidade calibrada do serviço. Registrar kernel/cgroup/limites,
core_pattern, fs.suid_dumpable e ptrace_scope. Não alterar sysctl/kernel.
Se suid_dumpable2+core_pattern pipe, recusar o perfil conforme D-119.

1. Controller aplica proteção antes de imports de aplicação; worker a
   aplica antes de sinal READY. Imports reais do corpo D-118 depois disso,
   sem conexão, registrando VmSize/VmRSS como observação, não contenção total.
2. Dois filhos sintéticos de mesmo UID, um dumpable1 de controle e um
   protegido0, mantêm canário **público** em buffer. O pai tenta ler esse
   endereço via /proc/PID/mem, process_vm_readv e PTRACE_ATTACH/DETACH; tenta
   ainda /proc/PID/environ e fd. Nada de ler processo externo. Cada interface
   registra permitido/negado/errno fechado, sem conteúdo da memória/ambiente.
   Controle positivo deve realmente ler/attach antes de atribuir diferença
   a dumpable. Seccomp/Yama podem impedir ambos: não chamar isso de prova
   diferencial, nem afrouxar perfil ou repetir para obter verde.
3. Provar parent-death com pai intermediário que cria filho protegido e
   morre; PID1 permanece para conferir/recolher o órfão. Separar de morte
   do PID1/namespace, que requer segundo container e inspeção externa.
   Caso de PPID esperado errado recusa antes de qualquer entrega sintética.
   A morte do PID1/namespace **não será executada neste incremento**; fica
   para o ensaio fim a fim do worker. O teste do pai intermediário não a
   substitui e a resposta pública terá pid1_death_proved=false.
4. Fechar canal do pai deve causar EOF/fim no futuro worker; este módulo
   não implementa protocolo/loop, portanto não se atribui essa prova a ele.
   Recolhimento e zero descendente efetivamente conferidos antes de liberar
   ownership; SO persistentemente falho deixa registro de cleanup incerto.

Entradas/saídas pequenas e limitadas; stdout somente schema público. Pai
com prazos absolutos, kill/reap e watchdog host independente. Um CID por
perfil necessário, sem retry/repetição da rodada. Novo procedimento prepara
estado/nomes/pins/comandos antes de A. Desktop atualmente Off: iniciar oculto
somente depois de revisão, inventário inicial sem containers, cleanup só
dos CIDs próprios e stop apenas com inventário final vazio/identidade do
Desktop original conferida. Capturar respostas CLI/exit/hash e atestar Off.

## Gates e sequência

Revisão deste contrato → código/matriz determinística → revisão do código
e procedimento → rodada nativa única → revisão da evidência. Falhas reais
permanecem evidência de tentativa; nenhuma repetição ou mudança de limites
durante a rodada. Não criar job de retomada se Claude2 não atingir cota.

Depois: integrar o guard na entrada final do worker/controlador e validar
snapshot/framing/ownership/prazos/conexão em PG16 descartável; reconciliar
reservas e cgroup D-119, pressão e limites, atualizar artefato final e gates
de IDE/MCP/Admin. B-1 fim a fim, B-2/D-090 e SQL seguem abertos. A candidata
atual não é release: três OpenSSL distintos/toolchainvendor registrados;
patch/minimalização antes da entrega final, sem aceitar CVE por inferência.

## Fontes primárias consultadas

- https://man7.org/linux/man-pages/man2/PR_SET_DUMPABLE.2const.html
- https://man7.org/linux/man-pages/man2/PR_SET_PDEATHSIG.2const.html
- https://docs.kernel.org/admin-guide/LSM/Yama.html
- https://man7.org/linux/man-pages/man2/process_vm_readv.2.html
- https://man7.org/linux/man-pages/man5/proc_pid_mem.5.html
- https://man7.org/linux/man-pages/man5/core.5.html
- https://raw.githubusercontent.com/moby/profiles/main/seccomp/default.json

O perfil Moby upstream orienta o desenho; o comportamento do Desktop local
será medido, não presumido a partir dessa versão upstream.

## Revisão do contrato

Claude2, somente leitura, sem bloqueador; ajustes incorporados: pré-condição
thread única tanto em threading.active_count como em Threads do proc; todos
filhos por subprocess fork+exec com close_fds/ambiente explícito; controle
positivo confirma dumpable1 (não herda fork-only0). Entre exec e guard só há
código/argumentos públicos, nunca segredo nem FD secreto herdado. Ambos os
controles aplicam os mesmos limites/PDEATHSIG/UID e diferem no dumpable;
canário público somente depois das checagens. ptrace exige wait de parada,
detach e confirmação de retorno a running; falha de detach exige kill/reap
e reprova. Negativos devem falhar por permissão, não por EOF/PID ausente.
Reap do neto exige status exato SIGKILL, não só ausência no proc. Conferir
zero descendentes/zumbis no namespace antes do término. Caso de morte do
PID1 em segundo container fica explicitamente não provada neste incremento,
sem atribuir a ele o teste distinto de PDEATHSIG. ptrace_scope ausente será
registrado como ausente. AS não vira cota agregada nem calibração final.

Revisão do módulo não encontrou bloqueador. Três ajustes incorporados:
VmSize atual mais8MiB de margem de bootstrap deve ser estritamente menor
que AS antes de qualquer mutação (margem declarada, não custo superior de
allocator/import); infinity vem de resource.RLIM_INFINITY. Três regressões
vermelhas antes da correção, depois53testes verdes. Quando o pai é PID1,
PPID1 sozinho não distingue adoção pelo namespace; a morte desse pai é
garantia de namespace que ainda precisa de sua prova própria. /proc ASCII
inválido recusa, sem normalização de nome do processo.

Revisão da sonda encontrou W1: o negativo usava o PID do próprio filho,
testando a cláusula errada. Regressão vermelha primeiro, correção depois:
PID esperado difere do PID/PPID reais, registro dos três valores, releitura
de dumpable1 e AS herdado inalterado depois da recusa. Sonda aceita sob
essa correção/teste. O módulo usa ABI ctypes medida somente em Linuxamd64;
não extrapolar para outras arquiteturas. As cinco interfaces precisam ser
diferenciais nesta rodada: se Yama/seccomp negar também o positivo, a
rodada falha fechada sem mudar perfil. MALLOC_ARENA_MAX do controller é
definido depois do início e não se afirma que controle suas arenas.

## Host e procedimento preparados, ainda sem executar

Novo docs/poc/oracle9_process_prepare.py, somente fakes/políticas. Reutiliza
**apenas** create_args/validate_container/identity do host de instalação
congelado401afa8c, rebinding do label de fonte do novo CID; a validação da
imagem usa namespace separado com labels originais. Não chama instalação,
context_inputs, commit, exec, pull ou Dockerfile. Os119arquivos originais
da fonte do app são rechecados pelo manifesto d0909fcf, com o novo guard
copiado separadamente. A .venv host e os37wheels continuam intactos.
Primitivas de CLI/ambiente/pins são as fundação0b0bb171/helper58c692a7.
Watchdog próprio180s com inspect de ownership antes de kill, outputs CLI
limitados e prazo absoluto do corpo; cleanup separado só dos CIDs próprios.
Semáforo/ledger de serviço não são usados ou certificados pelo ensaio.

102testes novos no total:53guard+26sonda+23host, todos verdes no Windows
3.11.3 com fakes, sem Docker. Ruff/check em módulo/testes e mypy strict nos
alvos Windows3.11/Linux3.14; script de laboratório apenas format e lint de
sintaxe E9/F63/F7/F82, sem alegação de tipagem/lint integral desses scripts.
Uma regressão W1 da sonda falhou antes do fix, depois passou; histórico
das3regressões do guard mantido. Runtime Linux ainda não executado.

Raiz própria preparada:
C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-process-20261026-f6c89e76
taskb2f6ae6f557943fbadde9da9705cc85f. Estado inicial bce2fb678a278cabfd533e5e437656f0cfe810a5a0aa8188bda2a5abe29c201c,
invokedfalse, Desktopunobserved e semphase. Fontes/controles/snapshot serão
congelados desde A até Off. Nenhum deles foi invocado nesta preparação.

Pins:
- guard:dd10fb725b846ca097d7bef8b434fa4846f80e36216b34a3a16e658f1d15d0b4
- payload:0b3b46b1abb90a743920aa333e5a04d109db9503a133f2168c7edbed897e1332
- host:5c1804071086ea5e4e3b2834077476cb8c54f3d8af8f73e26304819d068be2e0
- start:f6c65ab6712b99f2be53d00c0a2a543000f61a8c9329c7b90f3d09a0782d2d61
- state:cee00e331a2fdc0121182c83dec8d3daa47185d2384844ebded90ea463ebb760
- restore:a0d86c6ea451118683fae60ee27727db34adbed519d1ca2b9dcc0191b68a2ea4
- snapshot público docs/poc/evidence/oracle9-process-procedure-v1-20261026.json:
  a8d4b69473308726c7e9b0c47bf80031474034827be8078aac1fa483a8fc8efa.

O snapshot contém os controles completos, estado inicial, todos os pins
de CLI/Desktop/contexto/ajudantes e os passos. Conferir pins antes de cada
passo. Só antes de A também exigir hash do estado inicial; depois ele muda
pelas transições atômicas. Parse dos PS1 antes de executar, sem invocação.

1. start_desktop.ps1: source_inputs antes de StartProcessHidden, registra
   se já ativo; se Off, saneia ambiente no processo de lançamento e restaura
   o ambiente do shell no finally. Nenhum valor sensível registrado.
2. state_control.ps1 -Mode Observe em3chamadas separadas, cada qual3×10s.
   Conferir9observações de identidade e exits, sem alegar90s contínuos se
   houver pausas. state_control.ps1 -Mode Ready exige essas9observações.
3. Uma chamada B, sem retry:
```powershell
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_process_prepare.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-process-20261026-f6c89e76'
exit $LASTEXITCODE
```
4. Conferir resultado/outputs/owned_cleanup/inventory_restored e ausência
   de watchdog. Preservar diagnóstico em falha, nunca ajustar no meio.
5. Se Desktop já ativo, preservar. Se nós iniciamos: AllowStop só depois
   de comprovar cleanup/inventário vazio/identidade original; restore só
   confere inventário e executa desktop stop; Off confirma ausência real.
6. Rechecar todos os fontes/pins/outputs após Off e registrar/revisar.

No experimento o positivo precisa de acesso nas5interfaces e o negativo
negação por permissão; nenhuma exceção nova para “dar verde”. Um container
somente, secretless. PID1death, EOF do futuro loop, pressão/capacidade,
SQL/rede/read-only upstream, pacote novo e gates B-1/B-2/D-090 **não** são
comprovados por esta rodada. Os limites não serão aumentados automaticamente.

Correção pré-ação do procedimento, ainda invokefalse: o parserPS rejeitou
v1 por chave duplicada no mapa de pins. A troca global do nome do host
havia também trocado indevidamente o caminho do helper policy congelado.
Corrigida **só essa linha** antes de qualquer start/CLI; v1 preservado como
proposta não invocada. Ambos PS1 agora passam no parser sem executar.
Snapshotv2 oracle9-process-procedure-v2-20261026.json substitui v1:
0fe3e2857c92fe4bd5c694d6f0b32c59849f2b073462dff1b99c633a7981c586.
start agora96938ad3d74c3f25048abf765538e5e406aadff91bfd527986f64027de415a9f;
estado inicial/host/payload/guard/outroscontroles inalterados. Matriz
relacionada691/691verde; nenhum processo Linux/Docker executado ainda.

Revisão pré-ação completa encontrou P1 de procedência: comparar leitura
atual do arquivo com o estado não ligava diretamente os bytes já capturados
ao estado. Regressão vermelha reproduziu consumo indevido da tentativa
com payload capturado diferente; fix compara payload/guard capturados aos
hashes do estado e GUARD_SHA antes de consumir e novamente no fim. Mais3
variantes cobrem cada identidade.106testes novos/695relacionados verdes;
Ruff e mypy3.11/3.14 no Windows em283arquivos, mais escopo4alvos Linux3.14,
limpos. Nenhum runtime3.14/Linux foi executado por esses gates estáticos.

Claude2 aceitou condicionalmente a rodada exata com esse delta testado,
declarando que não precisa de nova revisão desse delta. Snapshotv3 substitui
as propostas não invocadas v1/v2 e será o **único** usado em A–Off:
0d26f5a446d53fb1ab90f1a29ebaf3e9024f779762a4fd06aa2a92b2862fe10f.
host final5d258c28b373956d5d96f03f34c074e74420900e17d2ce5935edebf7d73a1326;
estado inicial964b0d3112e9e2b357bad6252e6bf4bbba455351f1d621a56732a7b0cec2d8b4.
Root/task/guard/payload e três controles continuam os de v2. Source_admission
e os pins completos passaram antes de qualquer start; Desktop aindaOff.
O label manifest-sha256 do CID identifica só a origem instalada359a055c,
não afirma novo contexto/wheel desta rodada. CLIstderr é descartado pela
primitiva herdada e não será declarado preservado. Sem retry/increase/SQL.
