# HELD III — procedimento e comandos da rodada única

**2026-10-23 — plano CONSUMIDO; start/A/B/C executados uma vez.**
Resultado e restauração do Desktop em HELD-RUN-VALIDATION. Não repetir estes
comandos. O conteúdo abaixo preserva o procedimento revisado antes da execução.
I/II revisados somente com fakes; este plano não reaproveita nenhuma tentativa
anterior. Pergunta: persistir a resposta HELD real, original e envelope,
rechecáveis no host, no mesmo perfil128/192. Não é B-2 total, worker/SQL ou
produção. Primeiro resultado não esperado interrompe, sem repetir até verde.

## Checkpoint e estado inicial verificados

HEAD4a5e556, origin/master **em cache**5d173ea,0behind/1ahead. .git somente
leitura; sem fetch/commit/push. Novo baseline609 arquivos versionáveis+
.venv/pyvenv.cfg, incluindo imagens; exclui pessoais .codex/.claude/stackdumps/
systeminfo. Contagem difere dos384 do lote anterior por abranger imagens,
não por inferir arquivos novos. Diferenças anteriores preservadas.

Windows PowerShell5.1.26100.9711, Python Windows3.11.3 da .venv existente.
2026-10-23 por volta de12:21UTC: **nenhum processo com nome Docker**;
Desktop inicialmente off, nenhum processo Python de teste observado.
Não presumir off se mudar antes do start; abortar por interferência, sem
encerrar app/processo preexistente. Nenhum outro escritor será iniciado.

Caminhos, todos já existentes salvo a raiz de comandos:
- checkout C:\Users\w.filho\Desktop\codes\mask;
- Docker CLI C:\Users\w.filho\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe,
  SHA60028870931ea6e91955bfeaee358ec6c6920f6162c17a3d828c3c82ab3c3599;
- Desktop C:\Users\w.filho\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe,
  SHAf3100322884b025ead78c49b512ece5e8c1f444ea91c57a4e045cc409386a3de;
- config .docker/config.json, currentContext=desktop-linux,
  SHAf173396ef80b3c0bf4f8a5f6f944d3e426cee041ae3a2a8a07602ff6846a9f1a;
- meta em .docker/contexts/meta/fe9c6bd7a66301f49ca9b6a70b217107cd1284598bfc254700c989b916da791e/meta.json,
  endpoint npipe:////./pipe/dockerDesktopLinuxEngine,
  SHAc16649b1a2f1c6fbb68b85158a956862331e86543e25df46341f5fe5df2f9a25;
- preparação %LOCALAPPDATA%\Temp\maskgw-linux-imports-20261021-a81ce6d2;
  tree.json SHA8a60924c364882a1395d72415c1e166bca41da6a7208c1cfad32bbaede196002,
  656 arquivos/73.346.126 bytes. Observer confere toda árvore antes de CLI.
Não baixar/instalar/buildar/mudar daemon/contexto, montar checkout/segredos
ou usar outro banco. Imagem pinada python@sha256:8a00ecb83ed9d0864dfd102a1bdb2067fda907ceb30bb86d09da9ee558b19590,
--pull never, rede none.

## Fontes conferidas, repetir guards antes de cada ação

Mapeamento fonte/SHA/posição (runtime.json separado). Conferir originais antes
de start/A/B/C; Observer confere originais/cópias/pins antes de cada create.
Nenhuma edição de código depois destes hashes sem nova revisão.

| Fonte docs/poc | SHA256 | Cópia |
| --- | --- | --- |
| linux_as_probe.py | 8170a37b892bd6d2bdae351bacd05f0e047d8bbc9b2b54bad695da7419380e0b | probe RO |
| run_linux_as_probe.py | 58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627 | host |
| linux_import_probe.py | e92acbacded3aeab72c8237a26bd9471a0e43a83358f250d8dd0933d63af9c1b | probe RO |
| prepare_linux_imports.py | 506f7eb057320377371224e687fb8c79d5ce79208dc31d82c8986961fa38c9f0 | host |
| run_linux_imports.py | 5f85bec97f2c55d7bae13e0663507d78e42698323a3ed460a49a51b45ce60e3e | host |
| loaded_memory_protocol.py | 384fe081261086b6437cd9b53b8afe76c72c97262855d9c6465a4488cf1c5b1c | probe RO |
| loaded_memory_member.py | fea05d739b61eff9ba8b23d49cf283f8de9837e711218f7f1965d7392d47eddd | probe RO |
| loaded_memory_collect.py | 6d06bfe5344e53596dbbde9e3ae14914b6550cb73147b399e788300e54a733bb | probe RO |
| linux_loaded_probe.py | 40ead31f7fe57cb2102f30c1be3f535fa342e3ae22d8696e0970d4eab4315466 | probe RO |
| run_linux_loaded.py | d95cdfe231ab273fba96c4ecd808ce829327caea466992ee90c98c9d27a0e821 | host |
| loaded_memory_evidence.py | 7f0307106e9a139f626c96b7bade14395863cd468f83e22730fceb57dc7d9f53 | host |
| loaded_memory_tap.py | aae25eb187ccd483847b725049e8932df469a5d1b9722dad786cb328436f504d | probe RO |
| linux_held_probe.py | 3ec0b4fd4c0b061687e388ca735ee4061492a051d0fb68ba55f169720e2e56b4 | probe RO |
| run_linux_held.py | 02d2774a4c7af48a8e2f3b1491bc4384872806231d8e2dbfee5c210736f2a0b0 | host |

Conferir também scripts externos/config/meta/CLI/Desktop/tree. Mudança:
abort durável sem carga. O programa N ainda cria raiz
maskgw-held-as128-**20261022**-<uuid>;22 é prefixo congelado, não data da
medição. Não alterar N para trocar o nome; evidência terá data real23.

## Start próprio, uma vez, só depois da revisão deste plano

Raiz de comandos criada por New-Item, arquivos por apply_patch:
C:\Users\w.filho\AppData\Local\Temp\maskgw-held-command-20261023-675f9a2c.
attempt.json inicial PREPARED/desktop_initial=off/started=false/observer=false/
stop_allowed=false. Atualizar metadados por apply_patch conforme fatos, não
aprovação fictícia. Erro antes de A é abort e não autoriza retry desta tentativa.

No mesmo comando, guards/hashes e nova conferência de ausência de processo
Docker. Iniciar só app existente, oculto, preservando as chaves do ambiente
Windows padrão descritas abaixo (valores nunca impressos); restaurar
ambiente **do processo PowerShell** no finally, sem mudar ambiente global.
Não capturar/encaminhar stderr/stdout de usuário ou secrets. Comando:
```powershell
Set-Location -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask'
if (@(Get-Process | Where-Object {$_.ProcessName -match 'docker'}).Count -ne 0) { throw 'DESKTOP_STATE_CHANGED' }
$taskKeep=@('SystemRoot','WINDIR','PATH','PATHEXT','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA','HOMEDRIVE','HOMEPATH','ProgramData','ProgramFiles','ComSpec','SystemDrive','ProgramFiles(x86)','ProgramW6432','CommonProgramFiles','CommonProgramFiles(x86)','CommonProgramW6432','ALLUSERSPROFILE','PUBLIC','USERNAME','USERDOMAIN','USERDOMAIN_ROAMINGPROFILE','COMPUTERNAME','LOGONSERVER','OS','PROCESSOR_ARCHITECTURE','PROCESSOR_IDENTIFIER','PROCESSOR_LEVEL','PROCESSOR_REVISION','NUMBER_OF_PROCESSORS','SESSIONNAME')
$taskRemoved=@{}
foreach($taskEntry in [Environment]::GetEnvironmentVariables('Process').GetEnumerator()) {
    if($taskEntry.Key -notin $taskKeep) {
        $taskRemoved[$taskEntry.Key]=$taskEntry.Value
        [Environment]::SetEnvironmentVariable($taskEntry.Key,$null,'Process')
    }
}
try {
    $taskApp=Start-Process -FilePath 'C:\Users\w.filho\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe' -WindowStyle Hidden -PassThru -ErrorAction Stop
    [pscustomobject]@{LaunchPid=$taskApp.Id;EnvironmentKeys=@([Environment]::GetEnvironmentVariables('Process').Keys|Sort-Object)}|ConvertTo-Json -Compress
} finally {
    foreach($taskEntry in $taskRemoved.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($taskEntry.Key,$taskEntry.Value,'Process')
    }
}
```

Registrar PID/fato do start, confirmar processo próprio via inventário e
aguardar90s (nove intervalos10s, sem CLI readiness extra), com atualizações.
Erro do start/estado incerto: não executar A/B, registrar abort. Se surgirem
recursos/processos alheios, não forçar encerramento. S1 da revisão: não aplicar
a lista curta do CLI ao app. Opção(b) preserva chaves Windows padrão de
sistema/usuário, incluindo ComSpec/SystemDrive/arquitetura/perfil/ProgramFiles
e domínio/sessão. Não repassar variáveis de sessão de ferramentas/secrets ou
imprimir valores. Não alterar variáveis globais/configuração do Desktop.
R1 adotada:90s só por processos antes de uma única versão externa; falha
ainda consome tentativa, sem retry. C mantém ambiente curto de CLI, não o
ambiente de inicialização de uma aplicação duradoura.

## A — um único version externo, sem carga

Programa ASCII em external_preflight.py na raiz acima, SHA
b3888968310bdf34619bcc52259f633bf863d0588de476fb9b81a831bab04913.
Conferir hash do próprio programa imediatamente antes de executá-lo.
```python
import asyncio, hashlib, json, re, runpy, sys, tempfile, time
from pathlib import Path
from types import SimpleNamespace
helper = Path('C:/Users/w.filho/Desktop/codes/mask/docs/poc/run_linux_as_probe.py')
if hashlib.sha256(helper.read_bytes()).hexdigest() != '58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627':
    raise SystemExit(2)
old = runpy.run_path(str(helper))
root = Path(tempfile.mkdtemp(prefix='maskgw-held-external-20261023-'))
sink = SimpleNamespace(root=root, total_written=0)
record = {'profile':'loaded-as128-held-v1', 'desktop_initial':'off',
          'desktop_started_by_attempt':True, 'observer_invoked':False,
          'outcome':'PENDING', 'attempt_count':1}
old['Observer'].save(sink, 'external.json', record)
started = time.monotonic()
try:
    rc, raw = asyncio.run(old['bounded'](
        [sys.argv[1], 'version', '--format', '{{json .}}'], limit=16384, timeout=5))
    record['cli_exit_code'] = rc
    if type(rc) is not int or rc != 0:
        raise ValueError('NONZERO')
    data = json.loads(raw, object_pairs_hook=old['unique_pairs'])
    server = data.get('Server') if type(data) is dict else None
    if type(server) is not dict:
        raise ValueError('SCHEMA')
    version = server.get('Version')
    if (server.get('Os') != 'linux' or server.get('Arch') != 'amd64'
        or type(version) is not str
        or re.fullmatch(r'[A-Za-z0-9._+-]{1,64}', version) is None):
        raise ValueError('SCHEMA')
    if time.monotonic() - started > 5:
        raise ValueError('LATE')
    record.update(outcome='READY', engine={k:server[k] for k in ('Version','Os','Arch')})
except BaseException:
    record['outcome'] = 'ABORT'
record['elapsed_seconds'] = time.monotonic() - started
old['Observer'].save(sink, 'external.json', record)
print(json.dumps({'artifact_root':str(root), 'outcome':record['outcome']}))
raise SystemExit(0 if record['outcome'] == 'READY' else 2)
```

Comando exato A, **chamada separada**, depois dos guards e do start confirmado:
```powershell
Set-Location -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask'
& 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-held-command-20261023-675f9a2c\external_preflight.py' 'C:\Users\w.filho\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
```

Version5s/16KiB via bounded congelado e ambiente fechado, registro PENDING/
READY ou ABORT durável. Conferir exit_code **e** external.json em outra chamada.
Qualquer erro/timeout/nonzero/schema/cleanup/PENDING/registro faltante encerra
a tentativa antes de B. Nenhuma segunda versão externa ou observador depois
de abort; só checks/cleanup seguros. Falha de save deixa PENDING ou nada:
registrar abort na evidência, nunca inventar READY. Snapshot observer_invoked
false é pré-invocação; se B ocorrer, registrar esse fato depois em attempt/
validação, sem reescrever snapshot A.

## B — uma única invocação do observador HELD

Só após A READY+exit0+registro verificado e guards reconferidos. Não usar -c
com aspas embutidas no PowerShell5.1 nem encadear sem conferir exits.
```powershell
Set-Location -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask'
& 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\run_linux_held.py' --run 'C:\Users\w.filho\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-linux-imports-20261021-a81ce6d2'
```

Preflight interno obrigatório não substituído: até3 polls limitadas em20s,
ps global vazio e inspect da imagem/config antes de create. Se container
alheio existir, abort sem remoção/interferência.14 fontes em posições exatas;
wrapper8 no probe, E6 hosts fora. Parent STD somente, filho entry antigo.
Nenhum SQL/banco/policy/secret. Mesmos128MiB AS nos limitados/192MiB externos,
swap0/CPU1/pids16/shm1MiB/nofile64/core0/UID65534/capdropALL/NNP/RO/rede none.

Controle -> privado -> compartilhado só conforme grants/digest/replay/cleanup/
integridade. Primeiro resultado não esperado encerra o lote, not_executed
explícito.30s/caso,120s/lote,20s medição interna,2s emissão,64KiB por raw e
1MiB/lote, sem elevação. E depois do cleanup, fora30s/dentro120s. Timestamp do
lote inclui integrity final e watchdog.close, **não** startup/preparação nem
persistência/fsync do summary. Não prometer teto absoluto de SO ou chamar
esse checkpoint de duração total da invocação.

Conferir exit0/2/erro e arquivos; exit2 sozinho não é aprovação ou retry.
Transport e envelope originais imutáveis, hashes/tamanhos/replay/digest,
cleanup/inventários/sem órfão/flags de integridade/pins/elapsed_scope.
Captura de errno/blocos ainda é relato do membro, só pico/limites corroborados.
Novo inventário entre casos, não467/digest antigo obrigatório. Se não couber
ou import/proc/fd/readlink falhar: inconclusivo, sem ajuste/fallback permissivo.

## C — restaurar Desktop somente com segurança confirmada

Somente se este start realmente ocorreu/estado inicial off, cleanup próprio
auditado ou B não invocado, e ausência de interferência. Marcar stop_allowed
true em attempt.json somente após essa conferência. Novo ps limitado confirma
globalmente vazio imediatamente antes de stop. Se não vazio/falhar, não parar
app nem tocar recurso alheio. Sem --force/Stop-Process/wsl --shutdown.
Comando oficial com timeout:
[Docker desktop stop](https://docs.docker.com/reference/cli/docker/desktop/stop/).

restore_desktop.py na mesma raiz, SHA
736f35adbfaa8ae70443a9949a1b8c3c0c3d298c5cca63fe7e2567d9535f20fb:
```python
import asyncio, hashlib, json, runpy, sys
from pathlib import Path
from types import SimpleNamespace
helper = Path('C:/Users/w.filho/Desktop/codes/mask/docs/poc/run_linux_as_probe.py')
if hashlib.sha256(helper.read_bytes()).hexdigest() != '58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627':
    raise SystemExit(2)
old = runpy.run_path(str(helper))
root = Path(__file__).resolve().parent
state = json.loads((root/'attempt.json').read_bytes())
if (state.get('kind') != 'maskgw-held-attempt' or state.get('date') != '2026-10-23'
    or state.get('desktop_initial') != 'off'
    or state.get('desktop_started_by_attempt') is not True
    or state.get('stop_allowed') is not True):
    raise SystemExit(2)
sink = SimpleNamespace(root=root, total_written=0)
record = {'profile':'loaded-as128-held-v1', 'outcome':'PENDING', 'stop_attempted':False}
old['Observer'].save(sink, 'restore.json', record)
try:
    rc, raw = asyncio.run(old['bounded']([sys.argv[1], 'ps', '-aq', '--no-trunc'], limit=16384, timeout=5))
    record['inventory_exit_code'] = rc
    if type(rc) is not int or rc != 0 or raw.strip():
        raise ValueError('INVENTORY_NOT_EMPTY')
    record['inventory_empty'] = True
    record['stop_attempted'] = True
    old['Observer'].save(sink, 'restore.json', record)
    rc, raw = asyncio.run(old['bounded']([sys.argv[1], 'desktop', 'stop', '--timeout', '20'], limit=16384, timeout=25))
    record['stop_exit_code'] = rc
    record['outcome'] = 'STOP_RETURNED_ZERO' if type(rc) is int and rc == 0 else 'NOT_CONFIRMED'
except BaseException:
    record['outcome'] = 'NOT_CONFIRMED'
old['Observer'].save(sink, 'restore.json', record)
print(json.dumps(record))
raise SystemExit(0 if record['outcome'] == 'STOP_RETURNED_ZERO' else 2)
```

Depois de confirmar guards/ownership/stop_allowed, uma chamada:
```powershell
Set-Location -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask'
& 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-held-command-20261023-675f9a2c\restore_desktop.py' 'C:\Users\w.filho\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
```

ps5s/16KiB, depois stop com --timeout20 e bounded25s/16KiB; conferir cada rc,
sem segundo stop/forçar/repetir. Stop_returned_zero não prova app parado:
confirmar ausência de processos UI/backend com observações limitadas até10s.
Se não confirmar, registrar restauração não comprovada e deixar sem força.
Restaurar não apaga artefatos, volumes ou imagens. Não tocar outros containers.

## Depois do ensaio

Preservar originais/snapshots das rodadas anteriores e deste lote. Publicar
cópia JSON limitada no checkout para revisão, com original/hash/bytes e HELD
real decodificado. Recomputar SHA/tamanho dos14 fontes/cópias/transportes/
envelopes/manifesto/árvore, sem escrever na preparação; comparar baseline.
Revisão de evidência antes do próximo incremento. Plano consumido mesmo se
A/B abortarem; qualquer nova carga exige registro/plano/revisão próprios.
Sem publicação Git/deploy ou declaração de B-1/B-2/D-090/produção fechados.

15 simulações dos programas A/C passaram sem CLI/processos/escritas: ready,
nonzero/schema/duplicata/OS/timeout/cleanup/late, inventário alheio/erro,
stop não-zero/timeout/ownership/bool-rc.

Primeira revisão somente leitura51ea0d85 bloqueou somente S1 (ambiente curto
do app), antes de qualquer start. A/B/C e invariantes considerados corretos.
Start corrigido por opção(b), lista Windows acima; R1 espera90s adotada antes
da execução. Rerevisão somente leitura51ea0d85 fechou S1/R1 sem bloqueador,
permitindo start/A/B/C uma vez sob os guards, não certificação de produção.
Antes desse parecer, leitura CIM opcional de memória foi negada pela sandbox
durante preparação; não era start/A/B/C nem chamada CLI/carga. Não foi
interpretada como sucesso ou como consumo/repetição de uma versão externa.
