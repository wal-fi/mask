# Sexta rodada — imports completos no controle;32MiB não aprovado

**2026-10-21 — uma invocação executada; evidência revisada sem bloqueador.**
Plano próprio LIB-RUN-PLAN e código LIB revisados pelo Claude2 na sessão
51ea0d85. R1(a): nenhuma segunda tentativa, mesmo após abort de preflight.
Não houve abort, retry de carga, segunda invocação ou ampliação de cota.
O desvio da quinta continua registrado/não aprovado; esta é outra rodada.

## Preparação e preflights

Desktop inicialmente off, nenhum Python/Docker ativo. Produto D-115 com
115 arquivos correspondentes ao wheel de45edb1..., árvore parcial656 arquivos/
73.346.126 bytes verificada contra tree8a60924c... antes do início; nenhum
download, instalação, build ou modificação do produto. GitHEAD4a5e556,
origin/master **em cache**5d173ea,0behind/1ahead; sem fetch/commit/push.

Desktop iniciado oculto só para este lote. Após espera de30s, preflight
externo via helper bounded5s/16KiB retornou READY/exit0: engine29.7.2,
linux/amd64. Exit code conferido antes de chamar o observador. Snapshot
externo diz observer_invoked=false porque foi gravado **antes** de invocá-lo;
não é a conclusão global da rodada. Nenhum segredo/ambiente encaminhado.

Uma chamada pela .venv existente/Python nativo3.11.3,
`python -I -B docs/poc/run_linux_imports.py --run`, com CLI e
raiz preparada explícitos. Preflight **interno obrigatório** também passou:
uma poll READY, engine29.7.2 linux/amd64, CLI cleanup confirmado, ps vazio,
imagem/config inspecionados e flag de admissão só ao fim. Não foi pulado
por causa do preflight externo. Mesmos imagem pinada8a00ecb8..., dois mounts
RO, UID65534/rede none/capdropALL/NNP,192MiB/swap0/CPU1/pids16/shm1MiB/
nofile64/core0,30s/caso/120s/lote e limites de resposta anteriores.

## Resultados medidos

| Campo | Controle | Limited |
| --- | --- | --- |
| Outcome | normal | inconclusive |
| Tempo de caso | 5,359s | 1,953s |
| RLIMIT_AS supervisor e membro | ilimitado | soft=hard33.554.432 |
| Membro / container exit | 0 / 0 | 73 / 0 |
| Etapas | start/end0,1,2; verified | start0, IMPORT0; nenhum end |
| Inventário aceito | 465 linhas:77 baseline,351 etapa0,34 etapa1,3 etapa2 | 77 baseline; nenhum delta aceito |
| OOMKilled / cgroup max,oom,oom_kill | false /0,0,0 | false /0,0,0 |
| Pico cgroup | 94.932.992 bytes | 35.639.296 bytes |
| Cleanup próprio/container | ambos true | ambos true |

Sumário: **complete=true**, diagnostic_only=false, elapsed7,828s,
limited_classification=`did_not_fit`, imports_fit_as32=false,
total_memory_contained=false. Exit2 do observador é o resultado não-fit,
inspecionado no resumo, não uma autorização de repetição.

O controle completou maskgw.db.postgres -> runtime.snapshot ->
pgwire.result_encoder, cumulativamente, sem SQL, conexão ou serviços.
psycopg.pq.__impl__=binary; native_check identificou pglast.parser,
pydantic_core._pydantic_core, cryptography..._rust e yaml._yaml de /installed.
Sem audit_error/check_error/batch; nenhuma origem aceita por truncamento.
As465 linhas descomprimidas passaram o decoder limitado.

Novas linhas efetivamente observadas na etapa1:

- _openssl: attached-by-identity/installed/cryptography/hazmat/bindings/_rust.abi3.so;
- _openssl.lib: attached-by-identity-slot/lib/installed/mesmo caminho fechado;
- algorithms e modes: owner cryptography, caminhos próprios .py em
  installed/cryptography/hazmat/primitives/ciphers/, pela regra antiga.

A nova rodada mede associação do slot e origens que encontrou; não mede
tipo CFFI ou autoria independente, nem prova que os29 nomes não publicados
na quinta sejam exatamente os nomes desta rodada. Nenhuma exceção nova
para wrappers foi necessária. L1(a) continua: outros caminhos antigos podem
ler o objeto opaco; só regra própria/contexto/batch têm a fronteira declarada.

VmSize/VmPeak/VmRSS do membro no fim de cada etapa do controle:

| Etapa | VmSize | VmPeak | VmRSS |
| --- | --- | --- | --- |
| 0 | 98.181.120 | 101.724.160 | 60.383.232 |
| 1 | 110.063.616 | 110.063.616 | 65.007.616 |
| 2 | 110.063.616 | 110.063.616 | 65.007.616 |

Virtual não é RAM. Threads=1 e fds=[0,1,2] em cada end; children disponível
sem filho no membro. Limited ready VmSize20.357.120/VmPeak20.639.744, sob
limite efetivo32MiB antes de GO; houve IMPORT na etapa0 sem mensagem
original. **Não atribuir causa ao AS**: categoria/etapa/returncode bastam
para a classificação did_not_fit após controle válido. Não aprova32MiB,
quota global, memória total, isolamento de consulta/AST ou contenção nativa.

Linux Python3.11.17/glibc2.36/kernel6.18.54.1-microsoft-standard-WSL2.
Não é medição no runtime3.14 nem instalação operacional completa MCP/HTTP.

## Cleanup e integridade

Inventário final de cada supervisor=[1], pids_current=1, sem órfão no domínio.
Containers exatos removidos e confirmados:
control e5fe4c487fcd04eeb5e1f1cbeb5a140f735f1c34a4c793ebd63fe576737fe55f;
limited65fc3ae9aaa4a1083c239bead01f3768e404242394016a51fa27efb29c221f3c.
Inventário host Docker vazio novamente por chamada bounded/exit0 antes
do stop. Desktop encerrado graciosamente (exit0); depois zero processos
Desktop/backend/build/Python. Nenhum container alheio tocado; imagem e
árvore preparada preservadas. Watchdog fechado, deadline_exceeded=false,
sources/tree/runtime_manifest_unchanged=true, inventory_restored=true.
Hashes das cinco fontes vivas e cópias congeladas reconferidos iguais.

## Artefatos e revisão

Originais fora do checkout:
`%LOCALAPPDATA%/Temp/maskgw-linux-import-run-20261021-88dhq6kc`.
Preflight externo em maskgw-lib-external-preflight-20261021-eugfby_0.
Cópia JSON para revisão somente leitura (não execução pelo revisor):
`docs/poc/evidence/linux-imports-lib-20261021.json`, com originais integrais,
hashes, snapshot externo e dois inventários decodificados separados.

| Artefato | SHA-256 |
| --- | --- |
| Probe executado | e92acbacded3aeab72c8237a26bd9471a0e43a83358f250d8dd0933d63af9c1b |
| Observador executado | 5f85bec97f2c55d7bae13e0663507d78e42698323a3ed460a49a51b45ce60e3e |
| summary.json | f1d75db20538c2084738e89fb781e80e184c4bd90b6f024e1100bf3d889d3e9f |
| control.json | a65e9a2f05ca54f53402a607762d6d19d3eb22406ca81279d670c62c1d2b11a3 |
| limited.json | f303f8d4558cd653891db711d5f466f403501821a5e6476fda46852ac757d415 |
| external-preflight.json | fa59a25ea076352e909d1d0717d93957dc7271bda45d7525f4ef25633306f236 |

Fontes do produto, helpers congelados e alterações antigas preservados.
295 testes puros relacionados e estáticos passaram antes da rodada;
revisão de evidência somente leitura concluída sem bloqueador. Nenhuma suíte PG16 integral,
frontend, pacote ou medição runtime3.14 foi repetida neste lote.
B-1 fim a fim, B-2, D-090 gate2, SQL PGWire e produção permanecem abertos.
Sem novo caso, dependência/configuração, cota observada, job, segundo
escritor, commit ou push. Próximo passo é desenho separado a partir do
resultado não-fit, não aumentar limite neste experimento até passar.

Claude2 conferiu o bundle/docs na sessão51ea0d85: contagens, métricas,
limites, snapshots, hashes declarados e interpretação coerentes. Não
executou a rodada nem calculou hashes; medições/cleanup são do executor.
Nota opcional de reprodutibilidade atendida acima (host3.11.3). Bundle
contém caminhos locais do usuário, sem dados de cliente/segredos; antes
de qualquer publicação externa, decidir redação desses caminhos. Não
publicado neste incremento.

Auditoria do lote:344 caminhos no baseline,349 depois; oito existentes
alterados (sete docs e probe) e cinco novos (três docs, um teste e bundle),
zero ausentes e zero src/produto alterado. Todos os artefatos originais e
.venv/pyvenv.cfg preservados. Esse baseline já continha mudanças antigas,
que não foram descartadas. Git permanece sem fetch/commit/push.
