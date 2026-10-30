# Oracle Linux9.8 — identidade da imagem-base no Docker local

**2026-10-23 — CONSUMIDO: A/B/C executados uma vez; B não passou.**
Imagem oficial baixada, mas erro de supervisão/CLI não classificado durante
create impediu retornar esse comando; CID próprio recuperado por nome/label,
removido antes de start/metadata. Resultado BASE_METADATA_NOT_PASSED,
owned_cleanup/inventory_restored true. Não há prova /etc/os-release ainda.
Eventos pós-falha só do próprio CID, read-only, registram create/destroy;
não determinam a classe da falha. Não repetir esta rodada/attempt.
C stop/exit0 e Off/exit0, processos Docker ausentes em20:15:18.1698325Z;
sem desligar/alegar desligamento de WSL/VM. Imagem mantida no cache.
Evidência imutável oracle9-base-attempt1-20261023.json,9183bytes,
SHA24f9e181b2dd5d54069be3031a014004c6988f55d0bcccd44f4455e756f04359.
Procedimento e estados abaixo preservam o registro anterior à execução.
A/start aceito no primeiro parecer, fonte inalterada44d3e761, executou
exit0: inicialmente off, próprio PID29340/FileTime134372589213980307.
Não repetir A. Nenhum pull/CLI/container por B; marcadores corrigidos após
revisão e simulação antes da primeira observação real.
Usuário confirmou Oracle9.8 e depois **A** para o contrato de recursos local.
Não fecha B-2/D-090/B-1 nem ativa SQL. Esta rodada só verifica userland e
limites/metadados do container descartável; sem produto, pacote, dependência,
PostgreSQL, secrets, porta, mount, pressão de memória ou build.

## Fontes e estado

Raiz própria:
C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-base-20261023-542c878d
task=c4a6d654004d4cf6982ccf9f0719ee7b, kind=maskgw-oracle9-base,
invoked=false,desktop_initial=off,started_by_attempt=true,APP_OBSERVED.
Docker observado off antes do preparo; reconferir no script antes de start.
**Pins ativos v3**, fontes exatas em
docs/poc/evidence/oracle9-base-procedure-v3-20261023.json:
- start_desktop.ps1 SHA44d3e761afd2d21263bcea72a01d40b15969fc5656a1dd074d6c1b4258166a90,2967bytes;
- base_probe.py SHAea81f4fc21c7db03e9e8ed5bee189ccc481185d1df387b69a0ee1bd5a1068be0,10218bytes;
- restore_desktop.py SHA5b8565bb556d07fab0f1f014e0359fb4a39cd289d2031f2675595da2493ee512,2690bytes;
- state_control.ps1 SHAc9c86866bf670f16524040c6eec22a6be4fef48c56fd8d89567a4e298901e4bd.
V1 e v2 são cópias históricas preservadas, não pins ativos.
Python compile/runpy+pins sem main:passou, nenhuma CLI. Parser PS:0 erros.
Não são testes de Docker nem aprovação de execução por si mesmos.

Revisão inicial Claude2 aceitou A/B, pediu C1/context explícito+endpoint no
restore e C2/prova real de ausência separada de STOP_RETURNED_ZERO.
Corrigidos antes da ação C; quatro fontes v2 preservadas. V1 histórica; restore
antigo da v1 não será executado. state_control.ps1 contém os passos manuais
de observação/admissão/stop/off agora explícitos para revisão (parser0).
Roundtrip FileTime no PowerShell5.1 confirmou System.Int64 e valor exato.
Rerevisão C1/C2 fechados, M1/M2 antes de marcadores: JSONarray via pipeline
produziaCount1 (medido), corrigido para variável parsed e arrayCount3.
Dry run também achou File.Replace com null convertido em string vazia;
NullString::Value corrigiu. Falha de acesso no sandbox foi medida separada:
mesmo replace em arquivos próprios fora dele passou. Primeira fixture mock
usou escopo script incorreto; corrigida só a fixture. Simulação final sem
Docker/Get-Process/Sleep reais: own e pré-existente contam3/6/9 eReady;
pré-existente não afirma identidade própria; falha persisteOBSERVE_FAILED
eReady recusa. Resultado/scope mock na cópia v3. Nenhum desses dados é uma
observação real do app ou espera real90s. Falha Observe real aborta a rodada.

Helper congelado run_linux_as_probe.py
58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627 fornece
somente CLI bounded/environment, sem editar o arquivo antigo. Watchdog próprio
inclui --context desktop-linux e confere pins antes de kill só do CID validado.
CLI60028870931ea6e91955bfeaee358ec6c6920f6162c17a3d828c3c82ab3c3599,
Desktopf3100322884b025ead78c49b512ece5e8c1f444ea91c57a4e045cc409386a3de,
configf173396ef80b3c0bf4f8a5f6f944d3e426cee041ae3a2a8a07602ff6846a9f1a,
meta/contextoc16649b1a2f1c6fbb68b85158a956862331e86543e25df46341f5fe5df2f9a25.
Hashes conferidos no preparo e novamente antes das ações. Contexto explícito,
endpoint npipe local; env CLI allowlist sem DOCKER_HOST/MASKGW/secrets.

## A — uma observação/start próprio

Uma chamada do start novo, nunca scripts/attempts consumidos:
```powershell
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-base-20261023-542c878d\start_desktop.ps1'
```
Reusa o fluxo já revisto de ambiente Windows padrão, hidden, state reservado
antes de iniciar. Se Docker já ativo, não inicia/para o app alheio.
Se início próprio, guardar PID/FileTime exatos (não converter FileTime para
Number JS), nomes das chaves sem valores. Nove observações10s em blocos30s
com atualizações antes60s, confirmando mesma identidade; intervalos de
orquestração não são observação contínua nem prometem exatamente90s totais.
Só depois, estado APP_READY por temporário exclusivo/flush/fsync/replace e
mesmo PID/FileTime reconferido. Falha/ambiguidade aborta sem B/repetir start.
Comando Observe executado **três** vezes, cada chamada30s/3 observações:
```powershell
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-base-20261023-542c878d\state_control.ps1' Observe
```
Depois uma chamada do mesmo script com Ready; exige9 registros positivos
e identidade atual correta antes de APP_READY atômico. Nenhum DockerCLI
nesses passos. Se Desktop pré-ativo, observações não alegam ownership.

## B — uma invocação, sem serviço do gateway

```powershell
& '.\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-base-20261023-542c878d\base_probe.py'
```
Invoked consumido atomicamente antes de qualquer CLI, -O recusado. Primeiro
docker version com engine linux/amd64 e ps -aq vazio. Pull único --quiet
--platform linux/amd64 da imagem oficial **por digest**:
docker.io/library/oraclelinux@sha256:d8c0a1f95f3394a2b40ece95dbff199cea94d06ac0ed354a7b88e96e2df5bb94.
Origem/digest/tamanho comprimido47.249.168bytes consultados publicamente;
não é cota de disco descompactado. Pull limitado120s/64KiB no CLI; não promete
que cancelar CLI elimine toda atividade interna de download/cache do daemon.
Sem prune/remoção de imagem antiga. Imagem própria baixada é mantida.

Image inspect exige linux/amd64/RepoDigest e ausência de VOLUME implícito.
Create parado usando image ID, label/task/nome únicos; inspect verifica
ownership e perfil completo **antes** de start:128MiB memória/swap iguais,
pids16,CPU1,shm1MiB,nofile64/core0,uid65534,rootfs RO,cap-dropALL/NNP,
rede none/IPC e cgroupns privados, sem mounts/ports/devices/extra cap/init,
restartno,lognone/healthcheckNONE. Não significa AS nem B-2 comprovado.

Comando único fixo /bin/sh -c, só cats de /etc/os-release, kernel/cgroup/
memory.max/swap.max/pids.max/core_pattern/suid_dumpable/memory.stat e
command -v python3.11. No secrets e sem ativar algo no container. Metadados
capturados16KiB/20s. Exige IDol/VERSION_ID9.8, memória128MiB/swap0/pids16 e
campo kernel no memory.stat. Python pode estar ausente: isso é observado,
não alegação de runtime pronto. Core/config do host são apenas lidos.

Cleanup próprio por CID validado; stop se ainda running, confirmar e rm.
Create incerto é investigado só pelo nome/task desta rodada, nunca recurso
alheio. Qualquer cleanup/inventário incerto torna resultado não aprovado e
proíbe C; preservar artefatos/ownership para diagnóstico. Watchdog240s
independente só pode kill do CID conferido, com contexto e pins. CLI normal
limit5s, metadata20s, pull120s, cleanup10s. SO persistente pode impedir
recolhimento: não prometer deadline absoluto ou apagar dono por suposição.

Sem repetir B, aumentar limites, mudar digest automaticamente ou ignorar
versão divergente. Resultado e metadata.txt persistidos na raiz própria.
BASE_METADATA_PASSED não significa produto/SQL/isolamento certificado.
Campo kernel presente no memory.stat não prova ausência de nokmem/contabilização
efetiva; essa prova continua no gate do perfil, não neste resultado-base.
Falha de create sem recurso criado pode deixar cleanup não comprovado:
conservadoramente C fica proibido e Desktop permanece para diagnóstico.

## C — restaurar Desktop se for próprio e sem interferência

B precisa estar terminal e result profile/task corresponder ao attempt,
owned_cleanup=true e inventory_restored=true. Reconfirmar antes de armar
stop_allowed a mesma identidade PID/FileTime em PowerShell. Se app já era
ativo, não executar restore. Se inventário mudou, não parar o Desktop.
Uma chamada state_control.ps1 AllowStop faz essa validação e escrita atômica;
coordenador só a chama depois de B terminal/exit conferido.
```powershell
& '.\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-base-20261023-542c878d\restore_desktop.py'
```
Uma chamada C: verifica pins/profile/task, consome autorização, ps vazio,
desktop stop --timeout20 limitado25s, sem force/kill de app/WSL shutdown.
Restore usa contexto desktop-linux e endpoint npipe conferido. Seu resultado
é apenas STOP_RETURNED_ZERO; não comprova ausência real. **Passo separado**:
uma chamada state_control.ps1 Off verifica restore próprio, observa processos
Docker até10s e só marca COMPLETE_DESKTOP_OFF se ausência positiva.
Se não confirmar, registra OFF_NOT_CONFIRMED e exit2, sem force/repetir stop.
COMPLETE_DESKTOP_OFF significa ausência de processos nomeados docker, como
na observação inicial; não afirma que vmmemWSL, VM ou WSL foram desligados.
Restore ainda grava attempt via write_text, não atomicamente; corte de
escrita pode bloquear confirmação, nunca será tratado como sucesso por isso.
Sem cota/job novo, segundo escritor, commit/push/deploy. Evidência será
revisada antes de avançar ao build de dependências/runtime.
