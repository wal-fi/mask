# PG16 público — composição e supervisão propostas antes do código

2026-10-29, sob delegação. Perfil puro em rerevisão final; volumes6e3827af
aceitos78090. Nada novo de Docker/root/processo de laboratório/PG por este
desenho. Somente variantes explícitas de fontes congeladas, não monkeypatch,
AST em runtime ou reexecução de main consumido. Sem SQL/seed/credencial.

## 1. Owner do CLI público, incremento separado

O probe tem stdinDEVNULL, sem READY/frame privado. `bounded` congelado segue
servindo metadados/PS/CLI de controle. Para o start--attach do probe, escolher
subclasse explícita de ManagedBootstrape6ca pinado: reaproveita tasks/shield/
adoption/quiesce/ticket/freshAbsent/close e prova Proactor do handle de stdout.
Não alterar e6ca nem fingir que o novo stdin possui um PipeHandle.

Novo PublicProbeOwner captura e6ca e perfilPG por hash, Target do namespace
capturado, papelPG/imagemcf78/task/sourceSHA do script fixo. Oito overrides:
__init__, _pipe_closed, _pump, start, drain, await_ready, send_seed, retain.
Demais métodos são os mesmos objetos do e6ca. await_ready/send_seed/retain
são recusados antes de qualquer efeito; o owner não aceita/enfileira segredo.

Spawn fixo docker pinado/contextdesktop-linux/start--attachCID, seminteractive,
stdinDEVNULL/stdoutPIPE/stderrDEVNULL, mesmo ambiente público. Owner antes de
spawn, tarefa registrada antes de await/protegida, adoção tardia conservada.
Prazo absoluto12s desde antes de spawn até fim do probe/EOF, sem renovar por
chunk. Read4096 com teto8192, excesso sticky e drenagem/descarte sem deadlock;
falha/limite/exit nunca aprova prefixo. Saída só para parse_report fechado.

FD0 sem pipe só é reconhecido com stdinNone **e** get_pipe_transport(0)None,
no processo adotado da configuração fixa DEVNULL. Para release ainda exige
processo reaped/waited e todas as tarefas encerradas. FD1 continua exigindo
PipeHandle do tipo exato e handleNone no CPython/stdlib pinados. Desconhecido
é falso, nunca tratar ausência de API/erro como fechamento. Inheritedquiesce
3s/recoleta limitada, depois ausência nova de CID ligada ao ticket e close.
Spawn/handles/tasks incertos retêm owner/loop e HELD, sem Desktopstop.

Fakes antes de uso: args/ambiente/stdin fixos, nenhum caminho de seed/READY,
EOF e saída normal, excesso contínuo, prefixo+IO, nonzero, prazo absoluto,
cancelamento/falha de spawn/task, spawn tardio adotado, FD0 sem pipe vs stdout
desconhecido/handle vivo, quiesce e ausência posterior. Não repetir a prova
nativa de identidade/pipe consumida como se fosse teste puro.

## 2. Política/emergência PG própria, sem usar política621

Adapter público de cleanup captura o perfilPG por hash e reconstitui só task/
comando/imagem/entry/name/labels próprias, sem depender de Env ou arquivo vivo.
Comando precisa ser o script fixo da task; não há backend/argv arbitrários.
Watchdog PG explícito, variante3e98, snapshot imutável por CID, cmd-ec e
inventário inicial de volumes. Mesmo heartbeat1s/atraso15s/pósB600s/callback
único call_soon_threadsafe; sem objetos do loop na thread e sem ticket/release.

PublicEmergency PG explícito, variante2fdc: ações fechadas adicionais somente
volume-ls-q e rm-v do próprio CID. Antes do-v: inspect/posse do mesmo CID e
decisão6e3827af com baseline imutável; qualquer preexistente ou incerteza
proíbe-v. Registrar decisão antes do comando. Nunca volume-rm/force/prune.
CLI só pode ser terminado com PID/FILETIME do handle original conhecido;
desconhecido não adivinha PID. Main ainda recolhe CLI/owner/absent após ticket.

Orçamento PG de emergência50s e join55s, definido antes de efeitos: caminho
mais longo histórico24scomandos+volumeLS2+8pins1s+reserva10s+lock1s=45s,
5s margem. Join inclui ack2+lock1+exec50+2margem. Não muda a T4 consumida nem
promete término de syscall bloqueada. Falha segura mantém HELD/owner/loop.
Fakes de volume preexistente/named novo/rm falha/inspeção alheia/exit inicial
ruim/diferença final/join incerto antes de qualquer chamada operacional.

## 3. Host, entrada e evidência com revisão própria

Classe explícita sobre definições4bc/b593, sem métodos de install/cp/commit
ou watchdog antigos acessíveis. CLI fechada a version/info/ps/imageinspect/
volume-ls/create/startprobe/inspect/kill/rm(+v)/desktopstop. Metadados continuam
com bounded capturado; startprobe somente pelo PublicProbeOwner. Objeto owner
registrado antes de spawn, publicação síncrona de Birth ao voltar/lançar start,
republicação após recoleta como na T4, sem identidade de outro PID.

Preflight readmite imagemcf78, ENV/labels públicos, volumes iniciais com exit0;
nenhum create antes disso. blueprint da proposta calculado antes de A e
create_args do Intent real devem coincidir. Config/perfil/mounts validados
antes de start; raw localxb antes de parse/validação, manifesto e categoria
fechada antes de propagar. Identidade do cleanup independe de aceitação.

Um CID, sem rede nova/porta/DB. Probe concluído só com relatório inteiro,
EOF/exit0, estado parado/Pid0/semOOM/dead, quiesce positivo e nova ausência.
Cleanup serializado com a thread; inventários finais CID e volumes iguais
aos iniciais antes de Desktoprestore. Volume inesperado no create aborta
antes de start e segue decisão conservadora. Sobra/posse/exit/coleta incertos
mantêm HELD; nunca declarar restauração por mera tentativa de rm.

Budget de B público90s, pendência31s (quiesce6+cleanup25), restore93 e join55:
269s<600. Cleanup25 inclui lock1/inspect3/kill4/reinspect3/rm8/absence3/
volumeLS3. São orçamentos supervisórios novos, não medições nem teto do SO.
Root/estado/kind/task novos, journal12/replay e driver que retém HELD. Código,
gates estáticos/fakes, exportador/preparador e comando exato revisados antes
de uma rodada única. Logger/exportador exclusivos para material público;
imagem só por projeção pública/portão próprio, nenhum raw de segredo/DB.

Sequência: owner puro/fakes → adapter/watch/emergency e fakes → host/entrada/
integração CLI fake/evidência → proposta exata → rodada única e revisão dos
fatos. Não fechar B1/B2/D090/C1/SQL/serviço/produção por este laboratório.

## Precisões6796 antes de implementar o owner

P1: prova DEVNULL na adoção (start e início do pump para adoção tardia):
stdinNone e pipe-transport0None marcam stdinclosedtrue; nunca usar falha de
close em None como prova, nem gerar IO espúrio. Final de quiesce ainda exige
processo waited/reaped e _pipe_closed(0). Stdin inesperado mantém prova falsa.
P2: drain devolve returncode e buffer completo protegido ao parser fechado,
inclusive42; não converter42 em EXIT genérico. Só parse_report reconhece a
linha fault e nunca como sucesso. Qualquer IO/limite/prazo impede prefixo útil.
P3: start preserva admit_runtime do namespacee6ca pinado, ambiente público e
registro da task antes de await. P4: exatamente oito overrides, métodos de
seed/READY/retain recusam antes de efeitos; os demais são objetos do e6ca.

## Minimização da evidência de volumes — precisão antes de efeitos

Inventários globais e nomes preexistentes nunca vão em claro aos artefatos
públicos do monitor ou do host. Somente contagens e SHA-256 da lista canônica
JSON ordenada+LF, contagens de added/missing e subset de added nos nomes
ligados ao CID próprio. Decisão registra contagem/hash de linked/preexisting;
somente nomes anônimos novos64hex do próprio CID podem aparecer em claro.
Comparação real continua por conjuntos completos em memória, não por hash.
Se recuperação exigir baseline completa persistida, arquivo **local-only**
de nome fechado deverá ser explicitamente retido pelo exportador futuro;
jamais promovê-lo a metadado público nem inferir posse de um volume pelo hash.
Esse detalhe não implementa ainda persistência/recuperação do host.

Flag de reconciliação só fica positivo depois de volume-final ser escrito/
flush/fsync confirmados. Falha de persistência não deixa positivo prematuro.
A escolha é técnica sob delegação, sem adotar política corporativa externa.
