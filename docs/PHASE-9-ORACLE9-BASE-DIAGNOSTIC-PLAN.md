# Oracle9 — diagnóstico único com imagem já em cache

**2026-10-23 — consumido uma vez; BASE_METADATA_PASSED, Desktop restaurado.**
O texto abaixo preserva o procedimento preparado antes da execução.
Resultado e limitações em `PHASE-9-ORACLE9-BASE-VALIDATION.md`; não repetir
nenhum comando deste attempt ou tratar a base como gateway disponível.
Antecessor542c878d consumido/NOT_PASSED: pull/image-inspect passaram; create
não retornou pela supervisão e não teve exit/categoria capturados. Container
próprio foi recuperado por label/nome, removido sem start, global ps vazio;
Desktop restaurado off/confirmado. Eventos pós-falha registraram somente
create/destroy. Timeout de CLI5s é hipótese, não causa comprovada. Não usar
o sucesso futuro para reclassificar esse resultado ou ocultar o diagnóstico.

O novo lote pergunta se os metadados da base podem ser lidos, **sem novo
pull**, capturando tempo/categoria/exit por estágio. Mesmo digest e perfil
128MiB/swap0/pids16/CPU1/nofile64/core0, rede none/RO/nonroot/no caps/ports/
mounts/logs. Nenhuma cota de memória, SQL/job deadline, pressão ou gate B-2
mudam. Só o prazo da operação de controle **create** é20s nesta nova rodada,
declarado antes: não é timeout de query e não será ampliado automaticamente.

Nova raiz própria
C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-base-20261023-700c8624,
taskbae87fe0b3084922942da5889c8a56be. Dados iniciais unobserved/invokedfalse;
nenhuma ação real feita nesse attempt. Script A/control têm só novo root/task;
fluxo corrigido e simulado da v3 anterior. Restore5b8565... é idêntico.
Fonte B **v1 histórica**9b36d45666747cfd97525b3daba97e39b2c3c9a90f60f113e70f1920c0839ad1:
sem pull, categorias CLI_TIMEOUT/TRANSPORT/OS/FAULT/NONZERO fechadas, sem
texto/cadeia nativa; elapsed monotônico, estágio da falha preservado, inspect
--type container e metadata.txt com close/flush/fsync explícitos.
Um erro de sintaxe na montagem do programa de preparo foi detectado por
compile antes de gravar/invocar B; corrigido, sem ação de Docker.

Fontes/pins **v1 históricos**, preservados sem execução, em
docs/poc/evidence/oracle9-base-diagnostic-procedure-20261023.json,
SHAecdd26f527af657a136cf9b7706b318686aadbe188ef2cad8b385b19011604e7.
A a8467854...; B9b36d456...; control a3f494a6...; restore5b8565bb....
Nenhuma alteração nos helpers históricos ou scripts do attempt consumido.

Revisão aceitou segurança/ownership e registro da falha anterior; incorporados
D1 (HostFault OUTPUT_LIMIT/CLI_CLEANUP preservados como categorias fechadas)
e D2 (started_unix_ns do host por CLI, junto a elapsed monotônico).
**Pins ativos v2:** B18d2a339055dceac0b1a43014c0c204e1255508e0b31ae0e3b98f259e3e81b29,
10968bytes, em oracle9-base-diagnostic-procedure-v2-20261023.json,
SHA4049e99793ce312ecaddec28fae9bc5e0de18164dcc352bef61b02ea8be569c5;
v1 histórica, sem ações executadas com ela. A/control/restore inalterados.
D3, interpretação fixada **antes**: create passar com elapsed>5s é só
compatível com timeout antigo, não prova causa. Passar com elapsed<=5s
deixa causa antiga inexplicada. Primeiro NOT_PASSED nunca muda. Relógios
host/daemon não têm sincronização quantitativa comprovada; timestamps não
autorizam atribuição causal por igualdade. failure_stage é o rótulo de CLI:
validação pós-CLI OK pode falhar depois sem erro de transporte.

## Sequência única, mesmos guards da v3

1. Conferir hashes/config/contexto/processos, rodar **novo** start uma vez.
2. Observe três vezes30s, Ready após9 positivos e identidade; chamadas reais
   fora do sandbox que bloqueou Replace. Gap curto entre observações,
   atualizar usuário antes60s. Nunca repetir Observe real que falhou.
3. B uma vez; version/ps vazio/imagem cached pinada/sem volumes, create20s,
   inspect completo antes de start; metadata20s16KiB, expectedIDol/VERSION9.8,
   cgroup limites e ausência de OOM; cleanup por CID e ps restaurado.
   Watchdog240s segue só CID confirmado, contexto/pins. Nada de fallback.
4. B terminal: AllowStop só identidade/cleanup/inventário confirmados,
   restore uma vez, Off separado. Se app pré-existente, não parar.
   Falha de controle/cleanup/identidade mantém estado para diagnóstico,
   sem force/prune/WSL shutdown nem novo retry automático.

Comandos, a partir do checkout (mesmas operações, raiz nova):
```powershell
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-base-20261023-700c8624\start_desktop.ps1'
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-base-20261023-700c8624\state_control.ps1' Observe
# Observe mais duas vezes, só após cada terminal/exit0; depois:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-base-20261023-700c8624\state_control.ps1' Ready
& '.\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-base-20261023-700c8624\base_probe.py'
# Após terminal/cleanup/identidade positivos:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-base-20261023-700c8624\state_control.ps1' AllowStop
& '.\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-base-20261023-700c8624\restore_desktop.py'
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-base-20261023-700c8624\state_control.ps1' Off
```
São comandos sequenciais com checagem de cada exit, não um script que
continua cegamente após falha. Guardas/pins antes de cada ação. Não extrapolar
campo kernel de memory.stat para comprovação completa de contabilização;
não há leitura de cmdline/nokmem neste probe. BaseOS não é produto pronto.
Não executar build/runtime/SQL/worker por esse resultado. D-119/A aprovada
continua exigindo evidência própria. Sem segundo escritor/commit/push/deploy.
