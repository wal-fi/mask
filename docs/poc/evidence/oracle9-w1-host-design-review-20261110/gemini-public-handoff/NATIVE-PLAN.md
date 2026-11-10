# W1 nativo no Oracle9.8 — plano prospectivo da prova worker/PG16 (v4)

2026-11-06. Plano somente documental, Claude2, sob a delegação vigente.
Escolhas técnicas sob delegação; nenhuma aprovação individual do usuário é
inventada ou necessária para o rotineiro, só revisão técnica e permissões
efetivas. Nada executado para escrevê-lo: nenhum Docker/PG/SQL/runtime/root/
nonce/estado/comando. Disponibilidade atual de imagem/Docker **não** conferida.
Gateway indisponível. Histórico: v1 13bde9be, v2 98bfc054 e v3 28c794d2
arquivadas pelo root como dado. A v4 aplica correções pontuais sobre a v3:
contagens, wire de laboratório fechado, perfil de recursos do PG, T4/T5 e
o primeiro incremento. Preserva a composição pública, o ledger, o read-only,
o validator padrão e a candidata 621cc7f7. Nada aqui afirma código ou
comportamento nativo verificado.

Estado: nenhum contrato de produto ausente bloqueia o início dos
incrementos de código (§15), que dependem de revisão deste plano. A
execução nativa continua bloqueada pelos itens BLOCK_NATIVE (§17).

## 1. Objetivo e fronteira

Uma prova nativa única do caminho W1 real: controlador PID1 e worker Linux do
pacote **instalado** na candidata aceita, contra PostgreSQL16 próprio,
descartável e isolado, com dados sintéticos. Se verde, fecha a etapa3 do
WORKER-SESSION-PLAN em escopo completo, inclusive EOF, e fornece evidência
para B-1 fim a fim no perfil local.

Não é: coordenador Windows simulado novo; ingresso PGWire/MCP/Admin/IDE; SQL
liberada (continua0A000); perfil C1 pronto ou injetado em domain.py; B-2
estrito ou produção; pressão/concorrência/cliente lento/gerações. Independe
do laboratório Windows PG16 shell e não alega Native3s verde (continua
NOT_MEASURED, evidência congelada, sem dispensa). Source20/estado16 e a
tentativa3f12dc584c29 (FAILED_ONLY_OPERATOR_ABORT) permanecem fixos.

## 2. Insumos fixos aceitos

- Candidata `sha256:621cc7f702ec34d7014809411fda7fc89ab6b95f6dc7d16315274d4a7006ef0b`,
  Oracle9.8/Python3.11.13, origem87871290+layer d399fb14 (W1-UPDATE-V2-RUN).
- Wheel6b63f239…877b/448821bytes; manifesto de contexto d4d4b29b…5df8/
  270278bytes. Estrutura conferida pelo root: source_manifest com124 itens
  {bytes,path,sha256} = 123 caminhos do pacote + pyproject (não 124 mais
  pyproject); target com5chaves base_tools/console_scripts/installed_files/
  kind/wheels.
- W1_MODULES (deploy/oracle9_w1_update.py): linux_guard, db.session_state,
  worker_protocol, worker_process, worker_session; worker_job já no pacote.
  Root conferiu os124 inputs contra o checkout atual em2026-11-06: zero
  diferenças. Sem wheel novo, reinstalação ou rebuild; readmissão obrigatória
  antes do uso. Se a admissão achar mudança genuína, a prova para e volta a
  revisão.
- Fatos D-120: controller AS384MiB, filhos AS256MiB, externo512MiB/swap0/
  pids32/CPU1/nofile128/core0/tmpfs16MiB/shm8MiB; imports D-118 pós-guard
  VmSize≈91MB, Threads1.
- Padrões D-117 (WORKER-ERRORS-PG-PLAN, docs/poc/worker_errors_pg.py):
  `postgres:16-alpine` já local, create `--pull never` por ID, SCRAM,
  log-driver none, inspect sem Config.Env, varredura de segredo. Diferença
  deliberada: aqui não há volume anônimo em disco; armazenamento do PG é
  tmpfs limitado (§8a). Reuso de padrão e helpers pinados; nunca replay da raiz
  consumida `maskgw-worker-errors-pg-20261023-3ce74efa`.
- Composição pública de captura verificada pelo root (§6), artefato
  `pure-capture-public-composition-review.json`, registrado pelo root e não
  lido por mim.

## 3. Restrições do código atual (não contornar)

- WorkerSession exige Linux e GuardFacts CONTROLLER com `pid==getpid()==1`,
  dumpable0, core(0,0), PDEATHSIG0: o controlador é **o PID1 do container**.
- protect_process exige UID/GID10001, caps0, NNP1, Seccomp2 e **Threads1 no
  instante do guard**; VmSize+8MiB<AS; AS só diminui. Threads extras só
  nascem depois do guard.
- `open/query/send_result_to/close` passam por `_exclusive`: só a thread que
  chamou open (não daemon). É a thread principal, dona de todo o lifetime e
  criadora do filho (PDEATHSIG). `request_stop` é o único método
  cross-thread.
- Worker: `sys.executable -I -B -m maskgw.runtime.worker_process FD PPID AS
  IDLE`, `child_environment()`, stdout/stderr DEVNULL, stdin vazio até
  GUARD_READY. AS do filho ≤ AS do controlador. O filho conecta com
  `verify_capabilities=True` e S1: a verificação pós-conexão acontece **no
  worker**, nunca no pai.
- Deadlines: abertura12s desde antes de Popen; job `statement_timeout_ms+10s`;
  envio30s; limpeza3s; reap3×0,25s após kill; envio ao filho limitado por
  `idle_end`.

## 4. Topologia e payload

```text
Windows host (programa host novo + ponte duplex mínima §9)
 ├─ rede Docker própria --internal, label/task exclusivos, sem portas no host
 │   ├─ PG16 próprio: servidor upstream explícito, fora do domínio do gateway
 │   └─ gateway na candidata 621cc7f7, rootfs RO
 │        PID1 = python -I -B /lab/controller.py (bind RO de um arquivo)
 │          ├─ thread principal: guard, owner de cada WorkerSession, sonda T5
 │          ├─ thread sink (após guard)            §10
 │          ├─ thread stop-watcher só em T4        §9
 │          └─ worker_process instalado, 1 por vez
 └─ stdin/stdout do container gateway: único canal host↔controlador
```

- **Entrada do payload, sem instalar nem alterar a imagem:** precedente
  público em docs/poc/run_linux_as_probe.py. Uma cópia do arquivo-fonte,
  conferida por hash, fica na raiz da rodada e entra por **um único bind
  mount somente leitura** em destino fixo. O inspect admite exatamente o
  conjunto declarado: esse bind (RW false, origem e destino exatos) **mais**
  os tmpfs explícitos e limitados do perfil (§8), com tamanho/modo
  conferidos. Não há regra cega de "um mount". Ficam ausentes
  Binds/Devices/PortBindings/volumes, e Entrypoint/Cmd são conferidos
  exatamente. `-I` não põe o diretório do script no sys.path; o
  `maskgw` vem só do site-packages instalado (N1, §11). O arquivo não tem
  segredo.
- Rede única `--internal` criada pela rodada; nenhum `-p` ou recurso
  existente. IP do PG lido uma vez do inspect próprio e fixado. Banco
  existente, credencial antiga, serviço ou DSN do host: nunca.

## 5. Segredos e a exceção do PG

Gerados pelo host em memória por rodada: senha superuser PG, senha do papel
read-only, chave HMAC sintética, canários brutos.

- **Exceção única do servidor próprio:** como D-117, a senha superuser vai
  só ao ambiente do processo Docker CLI de create (`-e NOME` sem valor) e,
  por isso, ao Config.Env do container PG próprio. O ambiente não é
  globalmente livre de segredo; mitigação: inspect com template sem
  Config.Env e container removido ao fim. Nunca vale para gateway, worker
  ou credencial de usuário.
- Fixture e senha read-only entram no psql do container PG por stdin.
- Gateway: nenhum segredo em argv/env/imagem/arquivo. Só no LAB_INIT pelo
  stdin, depois da linha GUARD (§9).
- Toda saída/artefato é varrida pelos segredos e canários; qualquer
  ocorrência reprova, mesmo redigida.

## 6. Snapshot: composição pública existente (corrige B1 da v2)

Não é necessária API nova nem rebuild. `_compile` (candidate.py) é só
`parse_config_bundle` + `effective_database_settings` + `GatewayConfig`; o
root verificou a composição pública equivalente. No controlador, com a
**mesma** compilação e o **mesmo** recorder:

```text
recorder = RecordingSecrets(MappingSecretProvider({HMAC_KEY_ENV: chave}))
loaded   = parse_config_bundle(policy.to_mapping(), secrets=recorder)
settings = effective_database_settings(loaded.file_config, limits)
config   = GatewayConfig(masking=loaded.gateway.masking, database=settings,
                         sql=loaded.gateway.sql)
template = capture_template(policy, config, build_conninfo(spec, endereços), recorder)
snapshot = template.bind(SnapshotIdentity(dso, geração, revisão))
```

- Sem `build_candidate`, PreparedRuntime, adapter, verifier nulo, conexão
  ou DNS no pai. Provider fechado em mapping, sem env/fallback/segunda
  leitura. `endereços` vem de §7.
- O controle de revisão já feito pelo root: 4 comparações de bytes de
  `bind` contra o controle D-111 congelado, todas iguais, com
  `psycopg.connect` e `socket.getaddrinfo` interceptados como proibidos. A
  fixture fake de Candidate é só oráculo de comparação; o controlador não a
  usa.
- No teste pré-efeito, o conninfo explícito é obtido por
  `recompile_snapshot(...).connection_target()` e comparado com o
  `build_conninfo` esperado; nunca por campo privado de PreparedRuntime.

## 7. Destino e TLS do laboratório

Lido em datasource/destination.py, datasource/resolver.py e models.py:

- O resolver padrão (`bounded_system_resolver`) sempre cria um filho
  `python -I -S` com `getaddrinfo`, mesmo para IP literal. **Escolha:**
  usar a verificação pública `resolve_destination(ip, porta,
  policy=DestinationPolicy(), resolver=exato, expected_addresses=(ip,))`. O
  `exato` é próprio do laboratório: só aceita `(ip, porta)` idênticos aos
  fixados e devolve `(ip,)`; qualquer outra entrada levanta erro. Sem DNS e
  sem processo extra. Canonicalização, validação de endereço e comparação
  de pinning são as públicas, inalteradas.
- `DestinationPolicy()` default aceita `is_private` sem allowlist; recusa
  loopback, link-local, metadata e multicast. O host também confere, antes
  de B, que o IP é privado; senão aborta.
- `TlsSettings(mode="disable")`: perfil explícito de laboratório isolado
  (rede interna sem outros membros nem portas). SCRAM não transmite a
  senha. Não é alegação de produção: TLS `require`/`verify-full` do upstream
  real é gate separado.

## 8. Perfis, gerações, ledger e custos

Gateway: UID/GID10001, rootfs RO, cap-drop ALL, NNP, seccomp padrão,
memory512MiB, swap0, pids32, CPU1, nofile128, core0, /tmp16MiB, shm8MiB, rede
interna própria. Valores iguais aos já medidos na D-120, fixados antes da
medição; só a rede muda.

- Controlador AS384MiB; WorkerProfile.address_bytes256MiB. Herança 256≤384.
- ResultLimits F=16MiB (teto D-113), célula1MiB.
- G1: policy.database e limits com statement_timeout_ms1000 e max_rows1000.
  G2: statement_timeout_ms30000 e max_rows1000. Mesmo datasource sintético;
  `sql` sem extensões (política padrão inalterada).
- idle_ms30000 em todas as sessões, exceto T3 (1000, o mínimo).
- **Ledger (lido em runtime/budget.py):** `BudgetLedger(BudgetLimits(...),
  (DatasourceCapacity(sessions, candidates),))`, ordinal0. Sequência:
  1. `reserve_candidate(0, shared_bytes=…)` e `publish()` → G1 LIVE;
  2. `reserve_session(G1, worker_bytes=W, parent_bytes=P)` por sessão;
  3. `WorkerSession(ledger, token, lock=threading.Lock(), …)`; open faz
     `adopt_session`; o cleanup faz `begin_drain` + `release`;
  4. antes de T4, `reserve_candidate` + `publish(replacing=G1)` → G2 LIVE e
     G1 DRAINING.

  `publish` recusa uma segunda geração LIVE do mesmo datasource sem
  `replacing`. Por isso T4 e T6 usam G2, depois de todas as sessões G1.
  Valores: W≥256MiB (D-116), P≥2F+overhead (`begin_output`); `total_bytes`
  ≥ base+headroom+shared+W+P, com uma sessão por vez (`sessions=workers=1`).
  Números fixados no estado antes de efeitos.
- AS é virtual: soma 640MiB > memory.max512MiB, declarada sob a semântica
  D-119, sem limite numérico inventado, STRICT, B-2 ou produção.
  OOM/MEMORY é FAIL registrado, sem aumento de limite durante ou depois.
- PG: 512MiB/swap/pids256/CPU1 (D-117), fora do domínio; detalhado em §8a.

## 8a. Perfil de recursos do PG próprio (achado de desenho, não medido)

O `count(*)` sobre `generate_series(1,2000000000)` da v3 foi **removido**.
O root conferiu o código oficial do PG16: FunctionScan materializa o
resultado inteiro antes de devolver linhas. O default de `temp_file_limit` é
-1 (sem limite). Assim, aquela consulta poderia gerar tuplestore e arquivos
temporários enormes. Substituição em §11 (job16) e §12 (T4).

Perfil prospectivo, declarado antes do uso e sem aumento até o verde:
- memory 512MiB inalterado; swap igual; pids256; CPU1.
- `temp_file_limit=32MB`, que vale **por backend**, não agregado;
  `max_parallel_workers_per_gather=0`.
- Demais limites finitos declarados no estado antes do uso, a revisar:
  `max_connections`, `shared_buffers`, `work_mem`. Valores NOT_PREPARED.
- Armazenamento finito, sem disco anônimo nem escrita no host:
  - PGDATA em tmpfs 256MiB;
  - socket e /tmp em tmpfs pequenos e limitados;
  - rootfs RO; usuário UID70 com uid/gid/modo declarados nos tmpfs onde a
    imagem permitir (a admissão futura deve verificar).
- O tmpfs consome memória contada no cgroup do container (doc Docker). O
  limite de 512MiB inclui PGDATA, por isso o tmpfs tem de caber nele junto
  do servidor.
- `temp_file_limit` não limita tabelas temporárias explícitas. Elas são
  barradas pelo papel mínimo só SELECT, sem CREATE/TEMP, e pelo teto do
  PGDATA, aplicados juntos.

Referências consultadas pelo root, aqui parafraseadas:
- https://www.postgresql.org/docs/16/runtime-config-resource.html: temp_file_limit
  é por processo, -1 = sem limite; tabelas temporárias explícitas não entram.
- https://raw.githubusercontent.com/postgres/postgres/REL_16_STABLE/src/backend/executor/nodeFunctionscan.c:
  a função de conjunto é lida por inteiro para um tuplestore.
- https://docs.docker.com/engine/storage/tmpfs/: tmpfs fica em memória do
  host, com opções de tamanho e modo.

## 9. Máquina de estados host↔controlador

Canal: stdin/stdout do PID1 por `docker run -i` sem TTY.

- C→H: linhas JSON fechadas ASCII, ≤512bytes, ≤256 linhas. Escritor único:
  a thread principal.
- H→C: frames binários de tamanho exato.
- Nenhum sleep de coordenação, toda espera com prazo, nenhum retry.

**Leitor único do stdin.** Em cada instante existe exatamente um leitor
corrente: a thread principal, exceto na janela de T4. A passagem para o
watcher é exclusiva e ordenada: a principal lê `GO{T4}` e só então inicia o
watcher. O watcher lê **exatamente um** frame e termina. A principal só
volta a ler depois de `join` bem-sucedido do watcher (prazo = prazo do job
+3s). Join falho → ABORT, sem nova leitura. Nunca há leituras intercaladas.

Fases:

1. `GUARD` (C→H): depois de protect_process CONTROLLER e antes de qualquer
   leitura. Campos pid=1, AS, Threads1, dumpable0. Host confere.
2. `LAB_INIT` (H→C), uma vez, prazo10s (formato abaixo).
3. `INIT_OK` (C→H): snapshots G1/G2 compostos (§6) e sink pronto.
4. Para cada caso, em ordem fixa (§11–§12):
   `READY{case,next_seq}` (C) → ação do host, se houver → `GO{case,seq}` (H)
   → execução → `RESULT{case,next_seq,campos fechados}` (C) →
   `ACK{case,seq}` (H).
5. Em T4, depois de GO: C emite `ARMED{23,next_seq}` e inicia o watcher. O
   host envia exatamente um frame: STOP se observou o job pesado ativo
   (§12), senão NOSTOP ao fim da janela. Watcher: STOP → registra e, se
   aplicável, chama `request_stop()` (§12). NOSTOP → nada, e T4 FAIL.
   Qualquer outro frame → `request_stop()` por segurança e T4 FAIL.
6. `SUMMARY` (C) antes de T6. T6: `READY{25,next_seq}` → `GO{25}` (H) →
   `ARMED{25,next_seq}` (C) → o host mata o container. Depois do GO de T6 o
   controlador não aceita mais nenhum frame: frame ou prazo → exit1 e T6
   FAIL. O host não fecha o stdin (EOF) antes do SUMMARY.

**LAB_INIT** (wire de laboratório, prospectivo sob delegação):
- Cabeçalho de 8 bytes big-endian `>4sI`: magic `MGI1` e comprimento do
  corpo ≤65536.
- Corpo em JSON ASCII canônico (chaves ordenadas, sem espaços). Chaves
  duplicadas, NaN/Infinity, campos desconhecidos ou ausentes são recusados.
- Corpo com exatamente 7 chaves: `kind`, `version`, `target`,
  `readonly_password`, `hmac_key`, `raw_canaries`, `expected`.
- `target`: exatamente 4 chaves `ip`/`port`/`database`/`username`. IP
  literal privado validado (§7), porta 1..65535, nomes próprios da rodada
  limitados e validados.
- `readonly_password`: 48 hex. `hmac_key`: 64 hex, usado como texto, sem
  decodificar hex. `raw_canaries`: 1..16 strings ASCII de 1..128.
- `expected`: lista ordenada dos 19 jobs de P, cada item com exatamente 6
  chaves `job`/`kind`/`rows`/`bytes`/`sha256`/`reason`.
  - Resultado: bytes 1..F, rows 0..1000, sha256 com 64 hex minúsculos,
    reason None.
  - Erro: rows/bytes/sha256 None e reason na categoria fechada esperada.
- Nenhuma SQL arbitrária nem ajuste de perfil por esse canal: os SQL e os
  limites são constantes do controlador.

**LAB_CONTROL**: 16 bytes big-endian `>4sBBHII`.

| campo | tamanho | valor |
|---|---|---|
| magic | 4 | `MGL1` |
| version | u8 | 1 |
| kind | u8 | GO1, STOP2, NOSTOP3, ACK4 |
| case_id | u16 | P1..19 = 1..19; T1..T6 = 20..25 |
| host_frame_seq | u32 | ver abaixo |
| reserved | u32 | 0 |

- `host_frame_seq` começa em1 e soma1 a **cada frame de controle aceito**,
  não por caso. Os eventos READY/ARMED/RESULT de C informam o `next_seq`
  esperado para aquela fase.
- Na janela de T4, o watcher devolve o seq lido à principal **depois do
  join**. Nunca altera um contador compartilhado de forma concorrente; a
  principal valida e avança.
- Tipo permitido por fase:
  - após READY → só GO do mesmo case;
  - após RESULT → só ACK do mesmo case;
  - após `ARMED{23}` → só STOP ou NOSTOP de case 23;
  - após `ARMED{25}` → nenhum.
- Recusados: replay, frame extra, reserved≠0, version≠1, case fora da
  fase, seq diferente do esperado.
- Caminho completo sem abort: no máximo **50** frames de controle
  (24 casos normais × GO+ACK = 48, +1 STOP/NOSTOP de T4, +1 GO de T6).
- Wire só de laboratório: **não** é o MGW2 do produto nem o schema antigo
  do estado16.

Qualquer violação: a principal fecha a sessão ativa, emite `ABORT{fase}` e
sai1; o host faz cleanup e marca FAILED. Casos não alcançados ficam
NOT_RUN, nunca repetidos.

**Ponte duplex do host (falta):** `bounded()` em run_linux_as_probe.py usa
stdin=DEVNULL e só coleta stdout limitado. Não há canal duplex. É preciso
uma ponte específica e mínima: um único processo `docker run -i`, stdin
PIPE com escrita de prazo absoluto, stdout por linhas limitadas (512bytes/
256 linhas), stderr DEVNULL, máquina §9 do lado host, padrão
Watchdog/kill/reap. Testes antes de efeitos: linha longa, excesso de
linhas, prazo de fase, linha fora de ordem, frame de escrita parcial, EOF
antecipado, kill/reap na limpeza, sem retenção de segredo no log. Não é
framework genérico.

## 10. Sink e saída

- Thread sink não daemon, criada depois do guard e antes do primeiro open.
  Lê o par interno de um `socketpair` em buffer fixo de64KiB. Atualiza
  SHA-256 e contagem; nunca guarda o corpo nem o publica. Compara com a
  expectativa do job (comprimento exato) e entrega à principal só
  booleano+contagem.
- A principal chama `send_result_to(RawChannel(par))`: o backpressure é o
  buffer do socket, limitado pelo prazo de30s. BUSY/DEADLINE/ReceiverError
  → a sessão fecha conforme D-114; pin incerto fica HELD e a capacidade
  fica retida.
- Parada: após o último job, a principal faz shutdown do seu par e o sink
  termina por EOF. join de3s; se falhar, FAILED e capacidade retida.
- Não há segundo executor de SQL, conexão no pai nem decoder de linhas.

## 11. Sessão persistente P (G1): 19 jobs, numeração fixa

Admissão no controlador: N1 módulos `maskgw.*` com `__file__` sob o
site-packages instalado; N2 guard antes de ler o stdin. Open não é job:
OPENED/HMAC, GUARD_READY igual a PID/PPID/AS, baseline S1 no worker.
Fixture e policy iguais às de tests/test_db_typed_integration.py (`CONFIG`:
cpf hmac_sha256, email regex, numeric_secret fixed, token random, exception
tipo_cpf exact). Canários gerados pelo host.

| job | SQL (t = schema.tabela sintética) | esperado |
|---|---|---|
| 1 | `SELECT id, active FROM t ORDER BY id` | ALLOW, digest |
| 2 | `SELECT cpf FROM t ORDER BY id` | MASK HMAC text25, canário ausente |
| 3 | `SELECT cpf AS tipo_cpf, tipo_cpf AS cpf FROM t WHERE id=1` | alias + exception autoritativa |
| 4 | `SELECT substr(cpf,1,3) AS same, email AS same, active, id FROM t ORDER BY id` | expressão derivada, duplicadas |
| 5 | `SELECT cpf FROM t WHERE id=1 UNION ALL SELECT cpf FROM t WHERE id=2` | UNION mascarado |
| 6 | `WITH c AS (SELECT cpf AS x FROM t) SELECT x FROM c` | CTE mascarado |
| 7 | `SELECT x FROM (SELECT email AS x FROM t) AS s` | subquery mascarada |
| 8 | `SELECT numeric_secret FROM t ORDER BY id` | MASK numeric→text |
| 9 | `SELECT g FROM generate_series(1,1001) AS g` | truncado rows=1000 |
| 10 | `SELECT repeat('x',1048576) AS v FROM generate_series(1,15) AS g` | maior frame (<F) |
| 11 | `SELECT repeat('x',1048576) AS v FROM generate_series(1,17) AS g` | LIMIT recuperável |
| 12 | `SELECT 1` | saúde após LIMIT |
| 13 | `SELECT '<canário>'::integer` | QUERY recuperável (D-117), canário ausente |
| 14 | `DELETE FROM t` | QUERY (QueryRejected), sem efeito |
| 15 | `SELECT pg_read_file('postgresql.conf')` | QUERY (QueryRejected) |
| 16 | `SELECT count(*) FROM generate_series(1,100000) AS a CROSS JOIN generate_series(1,100000) AS b` | TIMEOUT recuperável (servidor, 1000ms) — hipótese, não medida |
| 17 | `SELECT 2` | saúde e S1 iguais após TIMEOUT |
| 18 | `SELECT amount FROM t WHERE id=1` | TYPE recuperável (numeric fora dos 8 OIDs) |
| 19 | `SELECT 3` | saúde após TYPE |

Após o job19: CLOSE gracioso, reap real, release RELEASED. RESULT só
existe após DONE correlacionado (código atual).

- Driver, S1, validator e SqlPolicy inalterados. `pg_sleep` continua
  proibido. TIMEOUT usa `generate_series` (fora do namespace `pg_`,
  permitido pela política padrão de sql/policy.py).
- Job16 e T4: cross join de duas séries de 100000 linhas. Cada lado é um
  tuplestore pequeno (§8a), e o custo fica no laço de 10^10 combinações. Se
  terminar antes do timeout, ou falhar por RESOURCE/temp, o caso é FAIL,
  sem retry nem ajuste para obter verde.
- Testes pré-efeito: texto SQL exato de cada job, sem parâmetros (simple
  query), policy igual à padrão, decisão do validator/proveniência atual
  com a categoria esperada. Se algum for recusado, substituir em revisão;
  nunca afrouxar regra.
- Após a rodada, o host confere pelo superuser que `t` não mudou. O job16
  pode gerar arquivo temporário no PG próprio, limitado pelo timeout.

## 12. Sessões terminais, ordem fixa, uma vez cada

- **T1 backend terminado** (G1): open → READY → host confirma por psql do
  superuser exatamente1 backend do papel e o termina (1 linha true) → GO →
  `SELECT 1` → ERROR fatal CONNECTION ou INTERNAL, kill/reap.
- **T2 blackhole** (G1): open → READY → host `docker pause` do PG por CID
  conferido → GO → `SELECT 1` → prazo do pai (11s) → JOB fatal, kill/reap →
  RESULT. Depois, o host faz `docker unpause` do mesmo CID por identidade,
  inspect Running/Paused e `pg_isready` em janela finita → ACK.
  **A restauração faz parte de T2.** Se falhar, todos os casos seguintes
  ficam NOT_RUN, o host vai a cleanup e marca FAILED.
- **T3 idle do filho** (G1, idle_ms1000): open → READY → GO → espera local
  limitada (idle_ms+1s, prazo monotônico, não coordenação) → `SELECT 1` →
  envio recusado pelo `idle_end` vencido → JOB fatal, reap. A API pública
  não expõe o returncode: não se alega distinguir saída por idle de kill.
- **T4 request_stop durante job** (G2, case23): open → READY → GO → ARMED,
  watcher → `query` com o mesmo cross join do job16.
  - Host: consulta `pg_stat_activity` até achar uma linha com o **papel e o
    database próprios**, state active e `query` igual ao texto **exato** do
    SQL pesado. A sonda S1 do worker não conta.
  - Janela absoluta de10s, no máximo 20 observações de metadados, cada
    chamada psql com timeout min(3s, restante). Achou → STOP; senão →
    NOSTOP.
  - Controlador: a principal marca `call_active=True` imediatamente antes
    de `query` e `False` imediatamente depois, sob um lock curto separado.
  - Watcher: ao receber STOP, sob esse lock, se `call_active` → chama
    `request_stop()` e registra `stop_applied=True`; senão →
    `stop_applied=False`. Não escreve no stdout, não publica nada e não lê o
    estado do owner.
  - PASS só com `stop_applied=True` e JOB fatal com kill/reap. STOP tardio,
    sem job ativo ou NOSTOP → FAIL, nunca PASS.
  - `request_stop` só seta um Event. Não há promessa de cancelamento
    instantâneo do driver, e o prazo duro do job continua inalterado. O pai
    pode observar o stop no envio ou no recv; o resultado fatal é o mesmo e
    o ponto não é alegado.
- **T5 EOF do canal — BLOCK_NATIVE, escopo mantido:** o ramo idle de T3 não
  substitui EOF. Próximo desenho concreto, a revisar antes do código do
  caso, sem tocar no fd privado de WorkerSession:
  - sonda de IPC própria na thread principal (G2, case24), com o mesmo
    rigor do owner: `reserve_session(G2, W, P)` e `adopt_session` sob o
    lock do ledger, dono enraizado na principal e todos os fds criados
    **antes** do Popen. Os créditos lógicos W/P só são liberados (`release`
    com CleanupConfirmation real) depois de reap físico comprovado. Não há
    worker fora do orçamento só por ser teste;
  - cria seu próprio socketpair e `subprocess.Popen` do worker **instalado
    e inalterado**, com o argv público e `child_environment()`;
  - usa o codec público `worker_protocol`: decode_guard → `encode_init` pelo
    stdin, fechado logo depois → OPENED comparado ao HMAC por compare_digest;
  - fecha o **próprio** RawChannel/socket. PASS exige saída **natural**
    returncode0 dentro de um prazo finito, depois de o filho receber EOF em
    `_next` e fechar o adapter. Kill de fallback é só limpeza: com ele, T5
    não passa;
  - o host confere zero backends do papel em janela finita.

  Não cria método de produção, não faz monkeypatch em runtime e não executa
  controle nativo agora. Até a revisão desse desenho, T5 fica pendente e o
  escopo completo não é declarado verde sem ele. Ordem: T5 depois de T4,
  ainda com G2.
- **T6 morte do PID1/namespace** (G2): SUMMARY → open → READY → host `docker
  kill` do gateway por CID → inspect: Running false, Pid0, sem processos.
  O PG mostra zero backends do papel em janela finita. Reap local não prova
  fim instantâneo upstream.

Em todo fatal: nenhum frame ou saída bruta, nada enviado, HELD/RELEASED
conforme fatos reais. Erro do SO retém capacidade, nunca "limpo" por prazo.
Total: 6 WorkerSession (P, T1–T4, T6) + 1 sonda direta T5 = 7 sessões de
processo. São 19 jobs persistentes + 4 tentativas de query do pai (T1–T4).
T3 recusa localmente antes da transferência, então **não** se alega que os
23 cheguem ao fio. Comportamentos nativos desconhecidos são critérios
futuros, NÃO medidos.

**Sem fechamento automático da etapa3.** Os checks verdes não fecham a
etapa3 sozinhos. Depois da rodada, uma auditoria requisito→evidência
confronta a matriz do WORKER-SESSION-PLAN item a item. Pontos que esta
matriz não exerce e que ficam abertos ou exigem caso próprio:
- INIT máximo maior que a capacidade do pipe: snapshot sintético pequeno;
- ausência de herança cruzada de FD entre sessões: só sessões sequenciais;
- EOF: depende de T5.

Os gates nativos, C1 e B-2 continuam abertos. Pressão e concorrência são
escopo separado, não dispensa.

## 13. Ciclo e frescor

Lido docs/poc/oracle9_cycle_freshness.py e seu teste (não executados).

- Núcleo puro: TOTAL300s A→B, GAP30s, 9 OBSERVE ≥10s, READY, B único;
  boot igual; tick e UTC concordantes (20s + 0,1%); rollback fatal; estado
  canônico persistido antes de agir.
- Suspensão: se o tick inclui o tempo suspenso, cai em TOTAL_AGE/GAP; se não
  inclui, o UTC diverge e cai em DISAGREEMENT. Os dois recusam (teste
  `two_hour_pause_or_suspend_never_enters_b`).
- A camada que lê boot, `tick_ms` e UTC no Windows fica no chamador; não li
  essa fonte. O pin é NOT_PREPARED e tem de ser a mesma camada revisada da
  UPDATE-V2 (mesmo boot, 12 checkpoints).
- O desvio de ~2h16 da D-120 fica preservado como histórico e não se repete.

## 14. Ownership e limpeza

- Uma raiz nova, sentinel de invocação única, ownership (task/label/nomes)
  com fsync **antes** de cada efeito. CID, ID de rede e de volume
  registrados logo após a criação.
- Desktop: padrão D-117/UPDATE-V2, restaurando só o próprio com identidade.
- Finally: inspect por identidade fresca. Unpause se pausado e próprio. Stop
  e rm só dos CIDs próprios; rede por ID. Não há volume: tmpfs some com o
  container. Confere ausência de volume com o label. Inventário final sem o
  label. Identidade incerta: não remove, FAILED, sem nova rodada.
- CLI limitado (`bounded` para comandos de metadados, a ponte §9 só para o
  gateway), lista fechada de comandos no estado, sem retry automático.

## 15. Incrementos de código antes de efeitos

**Primeiro incremento seguro (único próximo passo de código):** só
definições e testes puros e fechados.
- Arquivo do controlador apenas com definições, sem spawn, socket, Docker,
  PG ou main executável.
- Codecs LAB_INIT/LAB_CONTROL e suas recusas.
- Schema `expected`.
- Tabela fixa de case_id e SQL, com o SQL exato e a decisão do validator
  padrão.
- Composição sintética de captura §6 comparada ao controle D-111, com
  connect/getaddrinfo interceptados como proibidos.
- Resolver exato §7.
- Transições da máquina §9: seq, tipo por fase, leitor único/handoff,
  cardinalidade de 50.

Depois, em incrementos separados e revistos:
1. driver do controlador com fakes;
2. o driver físico;
3. só então o programa host e a ponte, quando todos os contratos dele
   estiverem fechados.

O host inteiro não vem antes disso.

1. **Controlador lab PID1**, fonte única montada RO: guard → GUARD →
   LAB_INIT → composição §6 → resolver exato §7 → ledger §8 → tabela fixa
   §11–§12 → linhas fechadas. Testes puros:
   - tabela e cardinalidade finitas; máquina §9 (ordem, seq, leitor único,
     handoff do watcher, extras, EOF);
   - recusa de segredo em argv/env; threads só após o guard;
   - sink sem retenção; SQL exato e decisão do validator; composição §6
     igual ao controle D-111 sem conexão nem DNS;
   - resolver exato recusando qualquer outra entrada; sonda T5 após a
     revisão do seu desenho.
2. **Programa host + ponte duplex** (docs/poc/): rede/PG/gateway próprios,
   mount RO conferido, fixture por stdin, §9 do lado host, pause/unpause
   por identidade, varredura, cleanup, frescor §13. Testes puros de
   ownership/allowlist/comandos/transições e da ponte (§9).
3. **Fixture SQL** pinada por hash e expectativas geradas pelo host.

Sem framework novo, API de produção ou helper genérico. Depois: revisão do
código, estado e comando preparados e revistos, uma invocação, revisão da
evidência.

## 16. NOT_PREPARED

Raiz, task, estado, sentinel, nonce e comandos; arquivos e hashes do
controlador, do host, da ponte e da fixture; ID atual do postgres:16-alpine
local; hashes atuais de Docker CLI/Desktop/config/contexto; rede (nome, ID,
subnet) e IP do PG; SessionKeys; números de BudgetLimits/W/P/overhead;
max_connections/shared_buffers/work_mem e tamanhos dos tmpfs menores do PG;
digests esperados; pin da camada do relógio. Nada disso existe ou foi
simulado.

## 17. Incertezas, classificadas

Fechadas por leitura nesta v3: composição de captura (§6, verificada pelo
root); API do ledger (§8); resolver padrão cria filho (§7); entrada do
payload por bind RO (§4); ausência de canal duplex (§9).

Pendentes antes do código do caso correspondente:
- desenho da sonda T5 (§12), revisão própria.

BLOCK_NATIVE (antes de invocar):
- pin da camada do relógio do Windows (§13);
- T5 até a revisão e o código da sonda;
- presença atual da imagem PG16 e da candidata; IP privado da rede interna;
- se o arquivo montado é legível pelo UID10001 nesse perfil Docker Desktop;
- se `docker pause` congela o PG sem fechar o TCP (premissa de T2);
- se a imagem PG aceita rootfs RO com PGDATA/socket/tmp em tmpfs UID70 e os
  limites de §8a; se o cross join realmente excede 1000ms sem
  temp/RESOURCE (hipótese);
- se T4 encontra o job ativo dentro de 10s/20 observações;
- tempos reais de CLI frente a idle_ms30000, prazo de T4 e janelas finitas.

Fora da matriz: duas sessões simultâneas (concorrência D-119/C1/B-2).

## 18. Abertos mesmo se verde

D-119/C1 novo tipo de perfil; B-2 local com pressão, concorrência, cliente
lento e gerações; D-090 gate2 completo; TLS upstream de produção;
patches/minimalização (OpenSSL3.5.8/cryptography/psycopg/pip/.pth);
ingressos PGWire, MCP, Admin e quatro IDEs; produção. SQL PGWire continua
recusada.
