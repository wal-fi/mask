# Supervisão pública do leitor PG16 — desenho antes do código

2026-10-30 sob delegação. Próximo incremento somente definições do watchdog e
fakes, sem thread/CLI nativa, caller, Docker, nova raiz ou carga. Adapter de
posse96e8a4c foi aceito emreview35578; SHA final será fixado antes do código.
Perfil8906/owner d671/reader efe6 e fontes consumidas anteriores preservados.

## Variante explícita e escopo

Novo docs/poc/pg16_shell_watchdog.py como variante fonte explícita do b86841ea,
sem editar fonte histórica, monkeypatch de globals, AST ou transformação em
runtime. Mantém Store/Snapshot/Observation/reason/lifecycle próprios para que
tipos exatos e conjunto fechado de casos não herdem pg16-public por engano.
Todas as23strings de Case do reader são o conjunto aceito; nenhum outro papel,
nome ou comando arbitrário vira posse por isso. Snapshot recebe task/case/
command públicos, baseline de volumes imutável e CID/PID/FILETIME quando
confirmados pelo main. Não autentica SO nem CID antes de inspect/identity.

Reaproveita sem alteração PublicEmergency54cc (ações só por CID/pid conhecido,
próprio loop, orçamento50s), volumes6e38 e bounded58/identitydc248 pinados.
Esses executores não conhecem o novo perfil nem autorizam mutação por si só;
watchdog novo deve exigir adapter próprio96e8 antes de qualquer kill/rm.
Não carregar policyf1d9 como se reconhecesse o wrapper do leitor.

## Diferenças declaradas da fonte b868

1. Conjunto de23casos, classes exatas próprias e categoria/prefixo público do
   leitor. Thread se chamará maskgw-pg16-reader-watchdog.
2. POLICY_SHA e caminho da policy próprios; capturar bytes aceitos, não ler
   fonte viva durante cleanup. emergency/volumes mantêm seus hashes.
3. _inspect usa o parser one fechado do base fe2 dentro do namespace do perfil
   novo (policy.P.P.one). identity recebe também case do snapshot, além de
   task/command/CID capturados. Nenhum CID/nome é escolhido do inspect alheio.
4. Evidências de emergência/volume decision/final têm kind próprio do leitor,
   sem copiar raw. Somente contagens/digests dos nomes globais/preexistentes;
   nomes anônimos próprios64hex podem aparecer como no b868.

Demais contratos permanecem: heartbeat1s/stale15s, B600s, callback único ao
main via call_soon_threadsafe, Store só contém snapshots imutáveis, nenhum
owner/loop/pump/secret/ticket recebido pela thread. Não inferir morte do CID
pela morte do CLI. PID/FILETIME só do handle original conhecido, nunca lookup
de PID arbitrário. Falha de identidade/pin/CLI/persistência não vira sucesso.
Antes mesmo de qualquer CLI_KILL, emergency deve conferir task/case/command
contra _capture do perfil no namespace da policy já capturada. Forma sintática
de Snapshot não concede comando nem PID. Kill de container continua exigindo
inspect atual e identity do CID. Nenhuma releitura viva depois de armado.

## Encerramento e volumes

Mesmo mutex externo com main. inspect próprio→kill se running→reinspect/Pid0→
decisão durável sobre baseline/Mounts→rm ou rm-v permitido→ausência por ID→
volume-ls atual reconciliado por conjuntos completos. Nunca volume-rm/prune/
force ou apagar preexistente. Falha de fsync não deixa flag restored prematura.
Caso CID já esteja ausente, ainda reconciliar volumes. Ledger/espaço de
artefatos só xb/flush/fsync, com nome/shape fechados, sem raw de Docker.

Fired sempre mantém lote reprovado/HELD para o main, mesmo se emergência
conseguiu remover o CID. Nunca ticket/Absent/release pela thread. Join55s
é orçamento de coleta, não teto absoluto de syscall; thread incerta mantém
HELD e não permite parar Desktop/fechar o loop. Baseline volumes local-only
deverá ser retida no exportador futuro, que ainda não existe para este lote.

## Fakes antes de consumidor

Tipos exatos/casos/clock/heartbeat/B, callback/cancel/lock/join/start falhando;
namespace/hashes e parser/adapter novos; cleanup próprio em running/stopped/
já ausente, alienCID/perfil inválido, named/preexistente/anônimo/incerto,
falha de persistência antes de rm e antes de marcar final, diferença final
retém, CLI desconhecido sem kill, fired nunca libera. Nenhuma thread real
ou DockerCLI nos testes; lifecycle de Thread será fake. Gates estáticos e
revisão de código antes de caller/estado/rodada. Gateway e SQL seguem fechados.

## B1 e precisões68182, antes do código

Claude2 apontou que Store.publish do b868 pode substituir ou apagar snapshot,
adequado ao caso único anterior, mas inseguro para vários CIDs. Escolha sob
delegação: **um Store/Watchdog por caso e CID**, com **monotonicidade também
exigida pelo Store**. Depois do primeiro Snapshot, task/case/command/baseline
nunca mudam e não se publica None. CID pode passar deNone para um valor uma
vez; nunca troca/volta. PID/FILETIME podem ser adicionados uma vez para o mesmo
CID; depois não mudam/voltam. Não há reset/release desse Store. Fake vermelho
primeiro deve recusar segundo CID enquanto o anterior ainda pertence ao lote.

Main só pode iniciar próximo caso após CLI/pumps/handles/ticket/ausência/
volumes/release positivos e join do watchdog anterior. Se fired, aborta o
lote inteiro, mesmo com cleanup bom, sem próximo caso. Cada Store novo deve
ser inicializado/armado com o **mesmo Bstart global**, depois pulse(now) antes
de iniciar thread. Isso preserva reason600s para o B inteiro, sem renovar o
prazo entre casos. Esse protocolo do caller ainda não foi implementado.

Capturas/exec aninhados acontecem somente em __init__ na thread principal,
antes de armar; namespaces têm nomes próprios. _bound(snapshot), também
disponível como check_snapshot sem mutação, confere task/case/Cmd reconstruído
antes de begin/CLI_KILL. Falha registra SNAPSHOT_BINDING/HELD, nenhum invoke.
Snapshot exige caso str fechado e Cmd≤12000; PID/FILETIME continuam fatos do
handle original, não autenticados por _bound. identity recebe case e _inspect
usa policy.P.P.one. 54cc/6e38 ficam intactos. Diferenças permitidas do b868:
as quatro listadas antes, Store.publish monotônico, _bound/check_snapshot,
guard __init__ da thread principal e sua chamada antes de qualquer CLI. Teste
AST (somente em testes) deve confirmar equivalência dos demais métodos/tempos.
