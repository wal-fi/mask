# HELD III — rodada real com transporte e envelope preservados

**2026-10-23 — uma execução concluída; evidência revisada sem bloqueador.**
Escolhas sob delegação vigente, não aprovação individual inventada. Fecha
somente a pergunta deste laboratório: persistir HELD real junto ao original,
revalidável pelo host. Não fecha B-1 fim a fim, B-2 ou D-090 gate2; não
libera SQL, Admin v2 operacional ou produção. Resultados anteriores intactos.

## Procedimento e execução única

Plano HELD-RUN-PLAN, código I/II e 14 fontes congelados. Revisão somente
leitura pelo Claude2, sessão51ea0d85, antes de qualquer start/CLI/carga.
Primeiro parecer bloqueou S1: ambiente curto para iniciar o Desktop. Opção(b)
corrigiu o start por allowlist Windows padrão; R1 adotou espera90s em nove
intervalos10s, apenas observação de processos. Rerevisão fechou S1/R1 e
permitiu start/A/B/C uma vez sob os guards. Revisor não executou comandos.

Desktop inicialmente off, confirmado sem processos Docker. Leitura opcional
CIM foi negada na preparação e depois medida com permissão efetiva: memória
física livre17.544.864KiB, total33.395.688KiB; virtual livre18.611.064KiB
não foi chamada de commit disponível. Nenhuma tentativa real consumida nessa
leitura. CLI/config/contexto/endpoint/tree/fontes/scripts guardados antes das
ações. Nenhum download, install, rebuild, mudança de daemon/contexto/global
env ou recurso alheio.

Start próprio: um Start-Process Hidden do executável já existente, PID3044,
com19 chaves Windows presentes na allowlist aprovada; valores não impressos.
Ambiente do processo PowerShell restaurado no finally. Após90s, o mesmo PID
continuava vivo e nove processos Docker observados; não houve version extra.

A: uma chamada externa version5s/16KiB, exit0, READY em1,172s,
engine29.7.2/linux/amd64. external.json lido/validado em outra chamada antes
de B. Seu observer_invoked=false é snapshot pré-B; não significa que B não
ocorreu. attempt.json final registra observer_invoked=true.

B: uma invocação --run com Python Windows3.11.3 da .venv existente,
-I -B, cwd explícito. Preflight interno passou antes de create:1 poll READY,
cleanupCLI=true, ps global vazio e imagem pinada inspecionada. Nenhum retry,
ajuste de cota ou caso adicional. Retorno do processo observador **0**.

Perfil loaded-as128-held-v1:20s internos,30s/caso,120s/lote; AS128MiB
nos dois limitados; defesa externa192MiB/swap0/CPU1/pids16/shm1MiB/nofile64/
core0/UID65534/NNP/capdropALL/rede none/mounts RO. Mesma imagem imutável
python@sha256:8a00ecb83ed9d0864dfd102a1bdb2067fda907ceb30bb86d09da9ee558b19590.
Preparação parcial656 arquivos/73.346.126 bytes,13 pins, sem modificar;
tree SHA8a60924c364882a1395d72415c1e166bca41da6a7208c1cfad32bbaede196002.
Imagem histórica3.11.17/glibc2.36; não se mediu novamente patchversion do
Python no container. Startup validou os guards/imports desse perfil.

C: somente depois de cleanup próprio e inventário restaurado confirmados,
stop_allowed=true. Uma chamada restore: ps vazio/exit0 e um
docker desktop stop --timeout20, limitado a25s/16KiB, exit0. Observação
posterior: nenhum processo Docker. Desktop restaurado off, sem --force,
kill, wsl shutdown ou remoção de imagem/volume. attempt.json final
COMPLETED_DESKTOP_OFF, stop_allowed=false previne segundo stop.
[Comando oficial utilizado](https://docs.docker.com/reference/cli/docker/desktop/stop/).

## Resultados

| Campo | Controle | Privado128 | Compartilhado128 |
| --- | --- | --- | --- |
| Outcome revalidado | control_ok | imposed | imposed |
| Tempo externo do caso |10,500s|5,328s|5,203s|
| Avaliação host E |0,046s|0,078s|0,031s|
| AS do supervisor/membro |ilimitado|134.217.728|134.217.728|
| Inventário completo |467 linhas|467 linhas|467 linhas|
| Observações independentes |12|9|9|
| VmSize pré-pressão |112.058.368|112.058.368|112.058.368|
| VmPeak no platô |154.042.368|133.050.368|133.029.888|
| VmSize no platô observado |154.042.368|130.953.216|130.932.736|
| Pico cgroup |138.907.648|94.740.480|94.666.752|
| Eventos max/oom/oom_kill |0/0/0|0/0/0|0/0/0|
| Membro/container exit |0/0|0/0|0/0|
| Inventário final do supervisor |[1]|[1]|[1]|
| Cleanup membro/container |true/true|true/true|true/true|

Sumário: complete=true, diagnostic_success=true,
evidence_artifacts_complete=true, total_memory_contained=false,
not_executed=[], deadline_exceeded=false, watchdog_closed=true,
inventory_restored=true; todos sources/tree/runtime/raw_unchanged=true.
Elapsed37,141s, escopo explícito
through_final_integrity_and_watchdog_close_before_summary_write:
não inclui preparação/start/A nem gravação/fsync final do summary.
Não apresentar como teto absoluto de todo o comando.

HELD persistido e rechecado, sem inferir só de outcome:

| Campo relatado pelo membro | Controle privado | Controle shared | Privado128 | Shared128 |
| --- | --- | --- | --- | --- |
| Blocos de4MiB retidos |10|10|5|5|
| accepted_bytes |41.943.040|41.943.040|20.971.520|20.971.520|
| touched_pages |10.240|10.240|5.120|5.120|
| failure |NONE|NONE|MEMORY|ENOMEM|
| errno |null|null|null|12|

São **relatos do membro**, não medição independente de cada alocação.
O replayer valida schema, relação bytes/blocos/páginas/categoria, pico e
limites contra observações independentes e sequência lógica. Não inventa
tempo real, EOF ou origem física. A linha HELD registra VmSize antes de
liberar a reserva emergencial2MiB; a observação posterior tem VmSize2MiB
menor nos limitados, mesmo VmPeak. Isso é esperado pelo protocolo congelado.

Controle: VmSize privado154.042.368→112.058.368; anon98.770.944→56.786.944,
queda41.984.000>=32MiB, antes do shared40MiB. Shared controle shmem
41.943.040→0; limitado shared20.971.520→0. Sem malloc_trim ou relaxar
regras. Estáveis: fds[0,1,2,3], fd3 sampler próprio,
proc_children_available=true; transitórios entre imports fds=null.
Não certifica disponibilidade de proc/readlink em outro perfil/kernel.

Os três inventários foram descomprimidos de modo limitado e comparados
linha a linha,467 cada e digest único recalculado
1d25ea3c8b9b85388ac7482f28a4f1feae6641ea484406756052ac5047d48c74.
Digest do controle atual admitido antes de cada limitado; não se exigiu
reutilizar inventário anterior. Imports cumulativos db.postgres,
runtime.snapshot e pgwire.result_encoder, origem/efeitos/native_check,
não consulta/masking reais.

## Artefatos, integridade e rechecagem

Originais externos preservados sem edição:
- rodada: %LOCALAPPDATA%/Temp/maskgw-held-as128-20261022-wrf4yvbb;
- externo: %LOCALAPPDATA%/Temp/maskgw-held-external-20261023-9im8bjrw;
- comandos: %LOCALAPPDATA%/Temp/maskgw-held-command-20261023-675f9a2c.

Prefixo20261022 congelado de N não muda a data real23. Alias8.3 impresso e
caminho longo w.filho designam a mesma pasta. Rodada reteve27 arquivos/
352.039 bytes, sem confundir tamanho retido com soma de regravações.
Task held-as128-c1c96f9b18db4d509f39f258b56626c5; bundle14 fontes
88480ded935a19b5afbd73bf839e3e457bef64de17e4a80dd107fd019ec1b66f.
Hashes/slots completos e scripts externos em HELD-RUN-PLAN.

Transportes e envelopes são arquivos diferentes, imutáveis, cada um<64KiB;
E só no host depois do removal. Raiz sob cap1MiB. Conferidos contra originais:

| Caso | Bytes transporte | SHA256 transporte | Bytes envelope | SHA256 envelope |
| --- | --- | --- | --- | --- |
| control | 12655 | c6bd6d6980b79a6d32d896d399b6ff69eddbd387124baced101afa6a9344a9cd | 12822 | 298c3ccd5d45b57e7ad932076093a88d543f90b09c259469adf0ac67d1148ea9 |
| private | 11184 | f4d89ebf813f97b6302b6b4d9ea9e66070212adb4a916c54377b2e77f4cefdef | 11348 | d429c855292bde212233cd0000f00d7e6475b014dcbc47ed5e74482fdb8fbf4f |
| shared | 11187 | 9c71cad9cc1a657b222845ae97bed62ab0c8fcf7ceb3e1079f131e07bb1e2234 | 11350 | eebf57cbfd43fc66da843b8f14b75b2223c9037446933381191739ee2074637c |

| Original | SHA256 |
| --- | --- |
| summary.json | 695e1f21a8db7581800879dd13b0463e93d205b0b9b2d6abff3ea5a8df702cfb |
| probe/runtime.json | dc5f7e5ab500a708dd67bda6164bd02b26a00e2d4481da7e9e57ac7f4b1dc5d1 |
| external.json | 35a7f4486f6f55d5d51965c89582ba2862604f8a0bdd6220ac00f40f118a20c7 |
| attempt.json | 783be71fc675b702d5e5f3bc1f5fbafd890b59f9a821edb330f4eb9b6c69b813 |
| restore.json | ee1f034029817891a45331cd8a9964858fbb190a419cd9ae7f03a6b674ac2bc3 |

Cópia de revisão docs/poc/evidence/linux-held-20261023.json:
442.356 bytes, SHA
8d4d60de764be866c6287b7d85fb7cbd61efa494084c98e4d3d84aad48aba794.
Contém18 arquivos com bytes UTF8 originais/hash/tamanho, JSONs auxiliares,
HELD decodificados e inventários completos. Não é raw de caso sujeito64KiB.
Executor recalculou hashes/tamanhos, conferiu original idêntico dentro de
transport/envelope, HELD byte a byte e E.decode+HOST.validate sobre os
envelopes salvos;14 originais/cópias e pins conferidos. Essa rechecagem
não chama CLI nem repete carga. Revisor lê a cópia no checkout e não recebe
atribuição de executar medições ou hashes que não executou.

## Gates e limites que permanecem

Nenhum código de produto/teste/helper mudou neste lote. Gates anteriores
I/II preservados:92 novos/895 relacionados, Ruff/format/mypy3.11/3.14;
execução Windows3.11.3, não repetidos sem mudança. Neste lote15 simulações
dos programas externos A/C, leitura/validação de artefatos reais e diff check;
não executar suíte Python/PG/frontend/browsers/pacotes só por editar relatório.

Os192MiB não foram deliberadamente saturados. AS128 limita espaço virtual
por processo, não RAM total, e não é default de produto. Não prova pressão
interna de libpq/pglast/Rust/TLS, consulta/AST/masking reais, workers
concorrentes, pai/auxiliares, memória global, threads abandonadas sob essas
falhas nem domínio de produção. cgroup peak/eventos deste ensaio não
certificam contenção externa; não foi alterado contrato para aprovar.

Linux/WSL2 é laboratório candidato, não seleção silenciosa de OS de deploy.
Falhas anteriores Windows/Jobs/shared continuam falhas; esta evidência não
as reescreve. B-1 fim a fim, B-2, D-090 gate2, SQL PGWire e produção abertos.
Próxima tarefa útil: desenho/revisão do domínio agregado e do pai/auxiliares,
com critérios de falha/limite e plano próprio antes de carga; não repetir
este plano, já consumido. Sem outro escritor, quota observada, job novo,
commit/push ou deploy.

## Revisão somente leitura e fechamento do registro

Claude2, sessão51ea0d85, revisou plano consumido, relatório e cópia JSON.
Sem bloqueador para fechar **este diagnóstico**. Não executou medições,
não recalculou hashes nem recontou467 linhas: isso foi feito pelo executor.
Ressalvas1–5 preservadas: campos HELD são relatos do membro; inventários
comparados pelo executor; uma imagem/kernel e nenhum gate de memória total;
proc/fd só neste perfil; start/A/B/C únicos, cleanup próprio e Desktop off
confirmados pelo executor. Replay é lógico e não prova tempo/EOF/origem.
Revisor explicitamente manteve B-1/B-2/D-090/SQL/produção abertos.
