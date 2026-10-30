# loaded-as128 — procedimento da rodada única

**2026-10-22 — tentativa consumida; evidência própria revisada.**
Código HOST-VALIDATION revisado com fakes, não certificação de contenção.
Este plano não reabre AS32 nem as seis rodadas anteriores. B-1/B-2/D-090,
SQL e produção continuam abertos. Uma invocação, sem repetir até verde.

## Estado e pré-condições, antes de qualquer Docker CLI

Checkout C:\Users\w.filho\Desktop\codes\mask, HEAD4a5e556, origin em
cache5d173ea,0behind/1ahead. Baseline novo368 arquivos, diferenças anteriores
preservadas. Nenhum escritor adicional será iniciado; processos Claude
preexistentes observados não são encerrados nem declarados inativos por nome.

Desktop **já ativo**, UI PID12848/13336/20380/23560/29276 e backend22400/26900,
iniciados aproximadamente09:26 locais. Este lote não o iniciou: **não o parar**,
mesmo se inventário vazio. Se ele deixar de estar ativo antes do preflight,
abortar esta tentativa; não iniciar Desktop sob este procedimento concreto.
Não há comando de start/stop/pull/download/install/build neste plano.

CLI existente:
`C:\Users\w.filho\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe`
SHA256:60028870931ea6e91955bfeaee358ec6c6920f6162c17a3d828c3c82ab3c3599.
Config local .docker/config.json:currentContext=desktop-linux,
SHA256:f173396ef80b3c0bf4f8a5f6f944d3e426cee041ae3a2a8a07602ff6846a9f1a.
Meta do contexto, diretório fe9c6bd7a66301f49ca9b6a70b217107cd1284598bfc254700c989b916da791e:
SHA256:c16649b1a2f1c6fbb68b85158a956862331e86543e25df46341f5fe5df2f9a25;
endpoint exato `npipe:////./pipe/dockerDesktopLinuxEngine`, não remoto.
Conferir ambos hashes imediatamente antes do version e do observador; mudança
aborta, nunca reconfigurar contexto/daemon. Ambiente do helper é allowlist
congelada, sem DOCKER_HOST/DOCKER_CONTEXT/segredos herdados.

Preparação existente (sem reconstrução):
`C:\Users\w.filho\AppData\Local\Temp\maskgw-linux-imports-20261021-a81ce6d2`.
tree.json:8a60924c364882a1395d72415c1e166bca41da6a7208c1cfad32bbaede196002.
656 arquivos/73.346.126 bytes; integridade completa comparada pelo Observer
antes de qualquer CLI/create. Nenhum banco, SQL, dado, credencial ou checkout
inteiro montado. Imagem pinada no MEMORY-PLAN, --pull never; dois mounts RO.

## Fontes congeladas para esta tentativa

SHA256 dos arquivos em docs/poc, reconferir antes de cada comando:

| Nome | SHA256 |
| --- | --- |
| linux_as_probe.py | 8170a37b892bd6d2bdae351bacd05f0e047d8bbc9b2b54bad695da7419380e0b |
| run_linux_as_probe.py | 58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627 |
| linux_import_probe.py | e92acbacded3aeab72c8237a26bd9471a0e43a83358f250d8dd0933d63af9c1b |
| prepare_linux_imports.py | 506f7eb057320377371224e687fb8c79d5ce79208dc31d82c8986961fa38c9f0 |
| run_linux_imports.py | 5f85bec97f2c55d7bae13e0663507d78e42698323a3ed460a49a51b45ce60e3e |
| loaded_memory_protocol.py | 384fe081261086b6437cd9b53b8afe76c72c97262855d9c6465a4488cf1c5b1c |
| loaded_memory_member.py | fea05d739b61eff9ba8b23d49cf283f8de9837e711218f7f1965d7392d47eddd |
| loaded_memory_collect.py | 6d06bfe5344e53596dbbde9e3ae14914b6550cb73147b399e788300e54a733bb |
| linux_loaded_probe.py | 40ead31f7fe57cb2102f30c1be3f535fa342e3ae22d8696e0970d4eab4315466 |
| run_linux_loaded.py | d95cdfe231ab273fba96c4ecd808ce829327caea466992ee90c98c9d27a0e821 |

## Comando A — somente um version externo, sem carga

Windows PowerShell5.1.26100.9711. A1 da revisão: não usar `-c` com aspas
embutidas; isso pode corromper o programa na passagem para o executável nativo.
Programa ASCII abaixo gravado por apply_patch, **sem executar**, no arquivo
`C:\Users\w.filho\AppData\Local\Temp\maskgw-loaded-command-20261022-1b49c2ad\external_preflight.py`.
SHA256:bbceb94b972641ea61d3dc5ba6ba918e744ad66f6496175e2d55152eae4fbc66.
Reusa bounded, unique_pairs e save já revisados; não é wrapper operacional.
Não chama Observer nem cria container. Raiz própria fora do checkout e registro durável
antes/depois do CLI. Uma chamada version5s/16KiB; cleanup pode exceder5s e
isso não estende a admissão. Exceção/nonzero/schema/atraso = abort, exit2.

```python
import asyncio, hashlib, json, re, runpy, sys, tempfile, time
from pathlib import Path
from types import SimpleNamespace
helper = Path('C:/Users/w.filho/Desktop/codes/mask/docs/poc/run_linux_as_probe.py')
if hashlib.sha256(helper.read_bytes()).hexdigest() != '58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627':
    raise SystemExit(2)
old = runpy.run_path(str(helper))
root = Path(tempfile.mkdtemp(prefix='maskgw-loaded-external-20261022-'))
sink = SimpleNamespace(root=root, total_written=0)
record = {'profile':'loaded-as128', 'desktop_initial':'active',
          'desktop_started_by_attempt':False, 'observer_invoked':False,
          'outcome':'PENDING', 'attempt_count':1}
old['Observer'].save(sink, 'external.json', record)
started = time.monotonic()
try:
    rc, raw = asyncio.run(old['bounded'](
        [sys.argv[1], 'version', '--format', '{{json .}}'],
        limit=16384, timeout=5))
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

Comando exato A, em chamada própria após as conferências:
Incluir explicitamente o hash do próprio external_preflight.py nas
conferências imediatamente antes de A (C2), além das fontes/CLI/contexto.

```powershell
Set-Location -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask'
& 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-loaded-command-20261022-1b49c2ad\external_preflight.py' 'C:\Users\w.filho\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
```

Conferir **exit_code da ferramenta e JSON/arquivo** antes do próximo comando.
Erro do Python/save/kill também aborta; PENDING não é READY. Falha do save
final pode deixar somente PENDING: registrar abort na evidência do checkout,
sem inventar fechamento do JSON. Falha antes do save inicial pode não criar
artefato; registrar o exit observado e observer_invoked=false. Registrar abort
no checkout, observer_invoked=false; nenhuma segunda chamada version externa
ou observador sob este plano, mesmo que o engine volte depois. Preservar
artefatos, sem cleanup global. O snapshot externo permanecerá pré-invocação;
se B ocorrer, a evidência da rodada documentará essa distinção temporal.

## Comando B — exatamente uma invocação, somente após A válido

PowerShell, checkout acima; executar em chamada separada, nunca encadear
dependências sem checar saída. Reconferir hashes/estado/contexto. Comando exato:

```powershell
Set-Location -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask'
& 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -I -B 'docs/poc/run_linux_loaded.py' --run 'C:\Users\w.filho\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-linux-imports-20261021-a81ce6d2'
```

Nova raiz maskgw-loaded-as128-20261022-*; host sem segunda invocação.
Preflight interno obrigatório continua até3 polls/20s, ps global vazio e
imagem inspecionada antes de create; readiness externa não o substitui.
Se houver container alheio, abort interno sem remoção/interferência.
Controle completo/cleanup/integridade admite privado128; imposed privado
admite shared128, com digest do controle **deste lote** antes da pressão.
Primeiro fail/incompatible/inconclusive interrompe, not_executed explícito.
30s/caso,120s/lote,20s internos,64KiB raw/caso e1MiB/lote sem aumentos.

## Depois, qualquer resultado encerra a rodada

Conferir exit0/2/erro e summary/casos/raw, hashes, limites, tempos e motivo
sem interpretar exit2 sozinho. Confirmação de remoção própria/inventário,
watchdog fechado e fontes/árvore/runtime/raw iguais. Inspecionar sem nova
carga; consulta ps bounded de verificação somente se necessária para cleanup.
Não repetir caso, corrigir e rerodar nem relaxar igualdade de pico/ptrace/fds.
Se /proc/fd falhar, registrar inconclusivo; sem CAP_SYS_PTRACE/fallback.
Nunca remover recurso por nome sem identidade task/bundle/ID confirmada.
Desktop já ativo será preservado, não shutdown. Publicar cópia de evidência
JSON limitada no checkout para revisão somente leitura; originais preservados.
Nenhum resultado fecha contenção total/B-2 ou libera SQL/produção. Revisão da
evidência antes do próximo incremento. Sem commit/push/deploy neste lote.

## Revisão anterior à execução

Claude2, sessão51ea0d85, somente leitura: A1 (invocação -c frágil/ausência de
comando exato) bloqueou o primeiro desenho. Corrigido por arquivo externo
hashado, helper absoluto/hash em programa e estado PENDING/abort explícito.
Rerevisão fechou A1/R-A2/R-A3, admitindo uma tentativa com C1 (cwd próprio em
B, acima) e C2 (hash do programa em A, acima). Revisor não executou código.
Oito simulações do programa passaram sem Docker/I/O; os primeiros harnesses
simulados falharam por relógio global interferindo no asyncio e por aspas do
-c nativo. Corrigiu-se o harness, não os critérios ou o código congelado.
Isso não foi version real nem consumiu/repetiu a tentativa. Revisão da
evidência continua necessária depois. Nenhuma cota observada/job novo.

Tentativa executada uma vez após os guards, preflight externo READY/exit0,
depois --run exit0. Este plano está consumido, não permite nova invocação.
Resultados e ressalvas em LOADED-RUN-VALIDATION, revisão somente leitura
concluída sem bloqueador para registro diagnóstico. Não autoriza outra carga.
