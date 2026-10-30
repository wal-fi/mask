# Perfil público do leitor PG16 — desenho antes do código

2026-10-30 sob delegação. Owner d6718800 aceito60994 e publicado7d42a49;
reader efe69a79/núcleo80219269 preservados. Próximo incremento é somente
perfil/builder/validador com inspect sintético. Sem Docker, nova raiz,
start/attach/carga/servidor/SQL/segredo ou alteração de fonte consumida.

Novo docs/poc/pg16_shell_profile.py captura por hash o perfil público fe2f8ba8
e o owner d6718800. Usa os mesmos objetos Image/admit_image do namespace
capturado do perfil e Case/reader/channel do namespace capturado do owner.
Não duplica decoder, parser do relatório ou loader do canal. Captura verificada
de fonte não é atestação de CID/perfil em runtime; futuro coordenador deve
inspecionar e admitir o CID real antes de chamar start.

## Perfil e diferenças explícitas

- Imagem exata cf78, UID/GID70:70, workdir/tmp, entrypoint/bin/sh, Cmd -ec
  seguido de wrapper ASCII completo devolvido pelo reader para task/case.
- Nome próprio por task+case; três labels próprias task/source do wrapper/
  manifest. CORE_SHA é somente a identidade do READY. Hash do wrapper
  completo é outro valor e deve coincidir com label/Cmd; sem auto-hash.
- Reutiliza todas as restrições do perfil fe2: read-only, networknone, caps0,
  no-new-privileges, ipc/cgroupnsprivate,512MiB/memoryswapigual/CPU1/pids256,
  shm8MiB/core0/nofile128/restartno/lognone/nohealthcheck, dois tmpfs exatos.
- Diferença planejada: create -i, Ttyfalse, OpenStdintrue e StdinOncetrue.
  O valor true foi medido na T4v2 Oracle; para o novo wrapper/imagem PG é
  precondição a conferir no inspect, não uma nova medição. Divergência aborta
  antes de input, sem normalizar para false ou alterar o validador antigo.
- Sem binds/devices/privileged/Init/AutoRemove/portas/rede externa/DNS extra.
  ExposedPorts5432 do metadata da imagem é herdado; PortBindings/publicação
  real continuam proibidos. Mounts reais somente tmpfs admitidos, sem volume
  anônimo. Inventário/cleanup de volumes continua responsabilidade posterior.

## API pura fechada

Intent(task,Image,Case) congelado captura task/nome/Cmd/labels/wrapper_sha/
core_sha/case/image. Tipos exatos dos namespaces capturados, não objetos
lookalike ou Case de outro runpy. Não aceita comando/backend/corpo arbitrário.
blueprint(task,Case) produz tuple de args+medição antes de A, sem daemon/image
inspect. create_args(Intent) deve ser igual ao blueprint, excluindo labels OCI
herdadas da linha CLI, como no perfil anterior. Reaproveita só o builder
comum _create de fe2, acrescenta -i e **recalcula** list2cmdline completo com
CLI/contexto; teto26000 caracteres. Não reutiliza a margem anterior sem-i.

identity(info,Intent,CID) confere posse por CID/nome/imagem/Cmd/entry e três
labels próprias. Não depende de Env/aceitação/perfil saudável; não concede
remoção/start. validate_container primeiro exige identity e depois todos os
predicados completos, inclusive labels OCI, Env e os três campos de stdin/TTY.
Implementação explícita desses predicados, sem fabricar cópia do inspect com
stdinfalse/Cmd antigo para satisfazer o validador histórico, sem monkeypatch.
info inválido produz categoria fechada, sem str/repr/raw/causa/contexto.

## Gates antes de qualquer chamador

Fakes com imagem/inspect sintéticos: todas as23 combinações, igualdade
blueprint/create_args, SHA do wrapper/Cmd/READYcore distintos, medição real
da string Windows e nomes únicos, imutabilidade/tipos/case/task inválidos;
mutação individual de flags/stdin/TTY/Env/labels/limites/mounts/portas e
identidade alheia; posse continua válida mesmo com perfil recusado. Import/
builder não criam subprocesso, Docker, tentativa ou arquivo operacional.

Não publica o inspect bruto: nenhum export gate genérico novo, S1/local-only
do futuro ensaio deverá projetar os campos admitidos. Escopo público não pode
ser usado para segredos. Layout, política de entrega dos negativos, casos,
watchdog/cleanup/host/entry/exporter e comando único continuam próximos lotes
com revisão própria antes dos efeitos. Nenhum gate de produção fecha aqui.

## Precisões98150 antes do código

Claude2 aceitou o incremento puro: manifesto próprio fechado para o leitor,
prefixo maskgw-ol9-pg16-reader- distinto, AttachStdin/Stdout/Stderr somente
observações booleanas (null se tipo ausente/desconhecido, nunca coerção), não
predicados de aceitação. -i terá posição fixa após create/--pull=never e antes
de quaisquer opções de nome/imagem; medição completa será recalculada para
todos os23 casos, incluindo o maior wrapper. Nenhum efeito nativo.
