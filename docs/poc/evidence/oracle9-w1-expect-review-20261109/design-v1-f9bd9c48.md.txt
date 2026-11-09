# W1 Oracle — contrato do gerador puro de fixture e expectativas (v1)

2026-11-09. Só desenho, Claude2 sessão51ea0d85/claude-opus-5-5/medium, sob a
delegação vigente; proposta para revisão do root, não aprovação individual.
Nada executado para escrevê-lo. Base HEAD 9e56df41. Source27/app124/estado16/
tentativa consumida intactos. T5 continua BLOCK_NATIVE para o laboratório
completo; este gerador não relaxa nada nem autoriza diagnóstico limitado.

## 1. Escopo e arquivos

- `tests/test_oracle9_w1_expect.py` (próximo lote, único) e depois
  `docs/poc/oracle9_w1_expect.py` (programa de host, fora do mypy como os
  demais PoC; root pode preferir `deploy/`). Ambos ausentes até revisão.
- Só definições: nenhum main/CLI, I/O, arquivo, env, relógio, aleatoriedade,
  socket, processo, thread, Docker, PG ou SQL executado. Sem framework novo.
- Fontes lidas: db/result.py, masking engine/descriptor/canonical, hashes/
  regex/simple/registry, config/gateway.py, secretsource.py, result_encoder,
  result_frame, result_receiver (sink recebe `iter_chunks`, corpo do byte76
  em diante), controlador puro (`_SQL`, `_ERRORS`, `_lab_policy`), driver
  (`sink_drain`, `expect_result`), NativePlan v4 §9/§11 e a fixture de
  tests/test_db_typed_integration.py (só lida, nunca importada).

## 2. API (fechada, imutável)

```python
CANARY_COUNT: Final = 4
RESULT_JOBS: Final = (1,2,3,4,5,6,7,8,9,10,12,17,19)
ERRORS: Final = {11:"LIMIT",13:"QUERY",14:"QUERY",15:"QUERY",16:"TIMEOUT",18:"TYPE"}

class ExpectRefusal(Exception): category: str   # INPUT | MODEL | ENCODE | SIZE

@dataclass(frozen=True, slots=True, repr=False)
class ExpectRecord:                 # exatamente os seis campos de decode_init
    job: int; kind: str; rows: int | None; bytes: int | None
    sha256: str | None; reason: str | None

def seed_sql(canaries: tuple[str, ...]) -> bytes
def result_body(job: int, *, hmac_key: str, canaries: tuple[str, ...]) -> bytes
def expected_records(*, hmac_key: str, canaries: tuple[str, ...]) -> tuple[ExpectRecord, ...]
def lab_init_packet(*, ip: str, port: int, database: str, username: str,
                    readonly_password: str, hmac_key: str,
                    canaries: tuple[str, ...],
                    records: tuple[ExpectRecord, ...]) -> bytes
```

- Tipos exatos (`type(x) is`), sem bool-como-int, subclasses de str/tuple ou
  coerção. Recusa sempre fora de handler, `str(e)==category`, sem causa,
  contexto, valor ou índice. `repr` de ExpectRecord redigido; nenhum log,
  print ou persistência. Não promete zeroização de memória.
- `hmac_key`: str 64 hex minúsculos (mesma gramática do LAB_INIT), usada como
  texto UTF-8. Provider só `MappingSecretProvider({HMAC_KEY_ENV: hmac_key})`
  em memória; nenhum `EnvSecretProvider`, arquivo ou segunda leitura.
- `result_body` só aceita jobs de RESULT_JOBS; é o acessor exato para testes
  e o único caminho interno de `expected_records` (sem duplicar corpo no DTO).
- `lab_init_packet` valida cada campo com as gramáticas do LAB_INIT
  (IPv4 privada canônica, porta, nomes `[a-z][a-z0-9_]{0,62}`, senha48hex),
  exige records idênticos em forma à tabela §4 e serializa JSON ASCII
  canônico (sort_keys, separadores compactos, allow_nan False) com `>4sI`
  MGI1; corpo >65536 → SIZE. Não chama o controlador; o teste valida com ele.
- Segredos de execução aparecem só onde pretendido: senha/chave apenas nos
  campos do LAB_INIT; canários em `raw_canaries` e, por desenho, em
  `seed_sql` (dado bruto a semear). Chave e senha nunca em seed_sql/records.

## 3. Fixture autoritativa única

Uma constante interna gera seed_sql E as linhas modeladas; nenhuma outra
fonte de valores. Esquema espelha CONFIG da integração tipada:

| coluna | tipo | linha1 | linha2 | linha3 |
|---|---|---|---|---|
| id | integer | 1 | 2 | 3 |
| cpf | text | C0 | C1 | NULL |
| tipo_cpf | text | 'physical' | 'company' | NULL |
| email | text | C2+'@example.test' | C3+'@example.test' | NULL |
| numeric_secret | numeric | 123 | 456 | NULL |
| amount | numeric | 19.5 | 99.5 | NULL |
| token | text | 'secret1' | 'secret2' | NULL |
| active | boolean | true | false | NULL |
| label | maskgw_lab.label (domínio text) | 'label1' | 'label2' | NULL |

- Canários: tupla exata de 4, gramática `[A-Z][A-Z0-9]{15}`, distintos.
  Comprimento igual impede um ser substring de outro; maiúscula inicial
  impede entrada inteira do PG16 (inclusive 0x/0o/0b/underscore), logo
  job13 continua ERROR; sem aspas/barra/espaço, nenhum escape necessário.
  Fora da gramática → INPUT, nunca escapar/normalizar.
- `token` e `label` existem só por fidelidade; nenhum job os seleciona. O
  transformer random é compilado pela política mas nunca aplicado (§5).
- seed_sql: ASCII, LF, palavras-chave minúsculas (canários maiúsculos não
  colidem), uma transação: `begin;` create schema maskgw_lab; create domain
  maskgw_lab.label as text; create table maskgw_lab.t (colunas na ordem
  acima); um único `insert ... values` com as 3 linhas em ordem de id;
  `commit;`. Literais: inteiro `str(int)` exato; booleano `true/false`;
  NULL `null`; numeric só das constantes fechadas `123/456/19.5/99.5`
  conferidas por `-?[0-9]+(\.[0-9]+)?`; texto `'...'` só de constantes
  fixas ou canários na gramática. Sem papel, senha, GRANT ou DSN (lote host).
  Devolve bytes e não executa nada.

## 4. Tabela dos 19 jobs (modelo, não fato do PG)

Política = `_lab_policy` do controlador: regras cpf(0,hmac), email(1,regex
`^(.{2}).*(@.*)$`→`\1***\2`), numeric_secret(2,fixed `[NUMBER]`),
token(3,random); exception tipo_cpf(0,exact). H(s)=HMAC-SHA256 hex de s;
m(E)=E[:2]+'***@example.test'. OID: MASK sempre 25; ALLOW o anunciado.

| job | colunas: nome(OID, decisão; origem/derivada) | linhas modeladas |
|---|---|---|
| 1 | id(23,ALLOW;id) active(16,ALLOW;active) | (1,t)(2,f)(3,NULL) |
| 2 | cpf(25,MASK r0;cpf) | H(C0) H(C1) NULL |
| 3 | tipo_cpf(25,MASK r0;cpf) cpf(25,EXC e0;tipo_cpf) | (H(C0),'physical') |
| 4 | same(25,MASK r0;derivada0) same(25,MASK r1;email) active(16) id(23) | (H(C0[:3]),m(C2),t,1)(H(C1[:3]),m(C3),f,2)(NULL,NULL,NULL,3) |
| 5 | cpf(25,MASK r0;derivada0) | H(C0) H(C1) |
| 6 | x(25,MASK r0;cpf) | H(C0) H(C1) NULL |
| 7 | x(25,MASK r1;email) | m(C2) m(C3) NULL |
| 8 | numeric_secret(25,MASK r2;numeric_secret) | '[NUMBER]' ×2, NULL |
| 9 | g(23,ALLOW;sem origem) | 1..1000, truncated |
| 10 | v(25,ALLOW;sem origem) | 15 × 'x'*1048576 |
| 12/17/19 | ?column?(23,ALLOW) | 1 / 2 / 3 |
| 11,13,14,15,16,18 | ERROR LIMIT,QUERY,QUERY,QUERY,TIMEOUT,TYPE | — |

- Origem/derivada vem desta tabela revista (metadata esperada do PG ou
  análise AST), nunca inferida do alias. Descriptors: origin_schema
  `maskgw_lab`, origin_table `t`, provenance DIRECT ou DERIVED.
- Raw do modelo no tipo que o psycopg entregaria: int, bool, str,
  `Decimal('123')`; job9 modela só as 1000 linhas já cortadas (nunca 1001).
- Ordem: ORDER BY nos jobs 1,2,4,8; job5 assume ramos UNION ALL na ordem;
  jobs 6/7 (CTE/subquery sem ORDER BY) assumem ordem de inserção num heap
  recém-semeado. Premissas NÃO provadas; jobs 9/10 dependem da ordem da série.
- Limite do oráculo: o corpo D-113 grava table OID/attnum 0 e não carrega a
  Decision. Proveniência divergente que leve ao mesmo transformer é
  invisível aos bytes; divergência que mude bytes (ex.: ALLOW de cpf) vira
  MISMATCH. Qualquer divergência nativa é achado, nunca verde forçado ou
  ajuste do modelo para casar.
- ERROR: só a tabela; o gerador não modela nem executa esses jobs.

## 5. Cadeia pública exata, por job RESULT, sequencial

1. `parse_config_bundle(policy_mapping, secrets=provider)`; exigir
   `gateway.database.max_rows == 1000`.
2. `engine = MaskingEngine(loaded.gateway.masking)`.
3. `decisions = tuple(engine.decide(c) for c in cols)`; MODEL se qualquer
   decisão ≠ tabela §4 ou se rule_index 3/transformer `random` aparecer
   (verificado ANTES de qualquer `mask_rows`).
4. `rows = tuple(tuple(r) for r in engine.mask_rows(cols, raw_rows))`.
5. `MaskedResult(cols, decisions, rows, truncated=(job==9))` e
   `TypedMaskedResult(masked, oids)`.
6. `encode_result(result, identity=ID(job), limits=LIMITS, deadline=DL)`:
   - ID: `ResultIdentity(session_id=bytes(16), datasource_id=bytes.fromhex(
     "0"*31+"1"), generation=1, record_revision=1, job_id=job)`; só
     enquadramento offline, descartado com o cabeçalho.
   - LIMITS: `ResultLimits(max_rows=1000, max_frame_bytes=16 MiB)`, demais
     defaults (célula 1MiB), iguais ao driver; nunca alterados para caber.
   - DL: `ResultDeadline(expires_at=1.0, clock=_zero)`, `_zero()` devolve
     0.0: sem tempo do host, nunca expira.
7. Corpo = `frame[RESULT_HEADER_BYTES:]`. expected_records faz sha256 sobre
   `memoryview(frame)[76:]` e libera a vista, guardando só rows/len/sha.
   Exceção do encoder → ENCODE; corpo vazio ou >F−76 → SIZE.

Alocação: um job por vez; job10 usa um único str de 1MiB repetido; pico
transitório ≈ buffer do encoder + cópia + corpo (≈3×15MiB), estimativa não
medida. Entradas limitadas por gramática (4×16 + 64 caracteres).

## 6. Vetores independentes

- **SELECT 1 (job12)**, corpo de 60 bytes, derivado à mão do formato de
  mensagens do protocolo PG (T/D/C) com os campos fixos D-113 (table OID 0,
  attnum 0, typlen 4, typmod −1, formato 0), não do encoder:

```text
54 00000021 0001 3f636f6c756d6e3f00 00000000 0000 00000017 0004 ffffffff 0000
44 0000000b 0001 00000001 31
43 0000000d 53454c4543542031 00
```

  Jobs 17/19 diferem só no byte de dado (0x32/0x33); a tag é `SELECT 1`
  (uma linha). O teste fixa o hex literal; SHA calculado pelo hashlib do teste.
- **HMAC**: com chave fixa de teste `"0123456789abcdef"*4` e canários
  fixos sintéticos, a 1ª célula de job2 deve ser igual a
  `hmac.new(key.encode(), C0.encode(), sha256).hexdigest()` via stdlib,
  caminho independente de engine/encoder. Além disso, um literal hex
  calculado uma vez pelo root fora do maskgw e revisto antes de congelar o
  RED; não há valor afirmado aqui porque nada foi executado.
- Consistência engine+encoder compartilhados não é oráculo final; só a
  rodada nativa contra PG compara de fato.

## 7. Matriz mínima de testes (RED antes da fonte)

1. Forma: 19 records em ordem, kinds/razões exatos, rows
   `[3,3,1,3,2,3,3,3,1000,15,1,1,1]` nos RESULT, bytes≥1, sha lowerhex64.
2. `lab_init_packet` aceito pelo `decode_init` do controlador pinado;
   campos iguais; canário/senha/chave ocorrem uma vez cada, só nos campos.
3. Para cada corpo: cabeçalho reconstruído pelo próprio teste (struct
   `!4sBBH16s16sQQQIII`) + `validate_result` aceita; truncated só no job9;
   job10 tem tamanho pela fórmula D-113 e ≤ SINK_CAP do driver.
4. Vetor SELECT 1 exato; 17/19 por diferença de um byte.
5. HMAC stdlib e literal; células: 'physical' (exception), `[NUMBER]`,
   m(C2), NULL como −1; nenhum canário em corpo algum.
6. Determinismo: duas chamadas iguais; outra chave muda exatamente os jobs
   {2,3,4,5,6} e preserva {1,7,8,9,10,12,17,19}.
7. Sem env: com `MASKGW_HMAC_KEY` ausente ou diferente, saídas idênticas.
8. Armadilhas durante as chamadas: socket/getaddrinfo, subprocess.Popen,
   psycopg.connect, time.monotonic/time.time, os.urandom/secrets e
   `transform` do RandomTransformer levantam → resultado inalterado.
9. Recusas: canários (contagem, minúscula, dígito inicial, aspas, 15/17,
   duplicados, subclasse), chave (forma, subclasse), job fora de
   RESULT_JOBS, alvo/senha/records adulterados → categoria exata, sem
   cause/context, sem segredo em str/repr.
10. seed_sql igual a um literal completo no teste (revisável), ASCII, cada
    canário exatamente uma vez, sem chave/senha/role/grant.
11. Composição finita: `sink_drain` do driver pinado com leitor fake em
    blocos de 64KiB sobre cada corpo e os records → OK; último byte
    alterado → MISMATCH; relógio fake fixo.

Política: o teste confere o mapping do gerador com `_lab_policy(1)`
do controlador (leitura pura de nome privado; ver §9).

## 8. Término e sequência

- Próximo lote seguro: SÓ `tests/test_oracle9_w1_expect.py`; gerador
  ausente. Root revê oráculos, mede e congela RED (falha só por módulo
  ausente; sanidades à parte). Depois Claude2 escreve só a fonte contra o
  teste fixo; verde exige todos os próprios, relacionados, Ruff/format e
  mypy dos testes limpos, sem noqa/cast/ignore/skip/xfail.
- Não altera driver, controlador, main, SDK, pins nem limites nativos.
- Continuam abertos: T5 (emenda revista do driver), programa host/ponte,
  raiz/estado/identidade frescos, readmissão 621cc7f7 e postgres:16-alpine,
  B1/B2/D-090gate2/C1, ingressos PGWire/MCP/IDE e produção.

## 9. Pontos não resolvidos

- Fonte da política: `_lab_policy` é privado no controlador pinado.
  Proposta: literal no gerador + igualdade em teste; alternativa é
  expor pública em emenda futura (muda SHA pinado; não agora).
- Mapeamento OID ALLOW = anunciado e MASK→25 pelo adapter tipado é premissa
  lida em TypedMaskedResult, não reconferida no adapter neste desenho.
- Ordem 5/6/7, origem do CTE (origem ou derivada) e categorias 13/16/18
  são hipóteses só verificáveis na rodada nativa.
- job11 (17×1MiB → LIMIT no preflight) poderia ter teste offline; omitido
  para não duplicar modelo de ERROR.
- Local do módulo (docs/poc sem mypy vs deploy/) fica para o root.
