# Verificador de evidência dos controles nativos — desenho (núcleo puro)

Data: 2026-11-03, America/Sao_Paulo. Sob a delegação vigente e revisão do
root; não é aprovação individual do usuário. Programador Claude2, sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço `medium`.
Base `002c6a4`. Desenho e testes foram escritos antes do módulo. Com o
módulo ausente, o root mediu a baseline de recurso ausente: 204 coletados,
203 erros de fixture e 1 falha do teste de fonte pura, todos por arquivo
inexistente (não é regressão de produto). Depois o programador implementou
`docs/poc/pg16_shell_native_control_verify.py`; estado atual: núcleo puro
revisado pelo root, com gates medidos na validação correspondente. Nenhum
teste foi executado pelo programador; as medições são do revisor.

Fontes fixas e não tocadas: entrada 356d2291, orquestrador b4198fe1,
adaptador eaebedd6, backend 10c9058f, chamador dfcc4ed6, estado de 16 campos.
Contrato de origem: seção 6 de `PHASE-9-W1-PG16-SHELL-NATIVE-CONTROL-PROCEDURE.md`
e o código do orquestrador (`_fields`, `_snapshot`, `_verdict`, `_finish`,
`_case`, `_publish`, `_run`).

## 1. Escopo

Núcleo puro e limitado: recebe bytes já coletados e devolve um rótulo
fechado. Sem sistema de arquivos, processos, `ctypes`, carga de código,
efeitos no import ou junção de caminhos. A coleta do disco (leitura sem
links/reparse/ADS e sem corrida) fica **fora** deste incremento: no Windows
exige verificação por handle nativo, e `lstat`+`open` é corrida. Coletor
confiável e pré-checagem nativa exata continuam pendentes, com desenho e
revisão próprios. O veredito atesta somente os bytes fornecidos; não prova
execução no SO, amostras CIM, proveniência das fontes nem cleanup.

## 2. API

- `Expected(nonce, argv0)`: registro congelado; `repr`/`str` não expõem
  `argv0`. Únicos campos do chamador. Pins, limites, nomes de ambiente,
  literais e listas brancas são constantes do módulo, copiadas do código
  aceito, nunca ajustáveis.
- `verify(expected, summary_raw, transport_raw, private) -> (label, reason)`:
  - `("VERIFIED_APPROVED", "OK")`, `("VERIFIED_REJECTED", "OK")` ou
    `("INVALID", <motivo>)`.
  - `REASONS = {EXPECTED, INPUT, FILESET, CAP, SCHEMA, NONCE, PIN, BINDING,
    PREFIX, INVOCATION, SUPERVISION, STDOUT, SNAPSHOT, AUDIT, CONTRADICTION,
    INTERNAL}`.
- Nunca devolve caminho, PID, argv, conteúdo ou texto de exceção; não
  imprime. Falha comum interna vira `("INVALID", "INTERNAL")`.
  `BaseException` que não seja `Exception` (controle) propaga: não há owner
  nativo a proteger. Seam de teste único: `_digest(raw)` (SHA-256).
- Importações permitidas: `dataclasses`, `hashlib`, `json`, `math`, `re`.

## 3. Ordem das verificações (o primeiro motivo vence)

1. `EXPECTED`: `type(expected) is Expected`; `nonce` e `argv0` são lidos
   **uma única vez** para referências locais e só então validados
   (`nonce` `str` exato de 32 hex minúsculos; `argv0` `str` exato, 1–1024
   caracteres, sem NUL). Alterações posteriores do objeto (por exemplo via
   `object.__setattr__`) não são vistas.
2. `INPUT`: `summary_raw`/`transport_raw` `bytes` exatos; `private` `dict`
   exato. `CAP` se houver mais de 64 entradas, antes de qualquer varredura ou
   cópia. Depois, chaves `str` exatas e valores `bytes` exatos, conferidos
   por `type` antes de qualquer `len`, igualdade, hash ou ordenação.
3. `FILESET`: cada chave pertence à lista branca de 11 nomes:
   `case-1/`, `case-2/`, `case-3/` × `invocation.json`, `supervision.json`,
   `local-stdout.bin`, mais `case-3/snapshot.json` e `case-3/audit.json`.
   Comparação exata de string; nenhuma normalização. Em seguida uma cópia
   privada (`dict` novo com no máximo 11 valores `bytes` imutáveis) passa a
   ser a única visão usada; o `dict` do chamador nunca é relido.
4. `CAP` (antes de parse): summary ≤ 16384, transport ≤ 4096, invocation/
   supervision/snapshot ≤ 4096, audit ≤ 65536, stdout ≤ 1024 bytes; soma
   ≤ 262144.
5. `SCHEMA` de transport e summary (seção 4).
6. `NONCE`: transport e summary iguais a `expected.nonce`.
7. `PIN`: quatro pins do summary.
8. `FILESET`: nomes da tabela do transport iguais ao conjunto fornecido.
9. `BINDING`: tamanho/SHA do summary e de cada arquivo privado; `outcome` do
   transport igual ao do summary.
10. `PREFIX`: estrutura do lote (seção 6) e conjunto de arquivos do prefixo.
11. Por caso executado, em ordem: invocation (`SCHEMA`, `NONCE`, `PIN`,
    `INVOCATION`), supervision (`SCHEMA`, `SUPERVISION`), stdout (`STDOUT`),
    e no caso 3 snapshot (`SCHEMA`, `SNAPSHOT`) e audit (`SCHEMA`, `AUDIT`).
12. `CONTRADICTION`: veredito e rejeição recalculados (seção 7).

## 4. Parse e esquemas fechados

JSON: exatamente um LF final (`encoded(value) + b"\n"` do produtor); corpo
ASCII sem CR/LF, sem duplicatas, sem NaN/Infinity, profundidade ≤ 32,
inteiros dentro de `[-2**31, 2**32]`, igual à recodificação canônica
(`sort_keys`, separadores `,`/`:`). Parser próprio; o chamador e o produtor
não são oráculo. Inteiros nunca `bool`; `seconds` é `float` (finito pelo
parse) ou `null`; o sinal é semântica de supervisão (seção 5). Tipos de cada
campo de caso admitem `null` (registros `NOT_RUN`); as restrições
dependentes do caso são aplicadas pelo nome do caso, não pela posição (a
ordem é verificada em `PREFIX`). Para casos executados, `ready` booleano é
conferido contra a supervisão.

| Artefato | Chaves exatas |
|---|---|
| transport | 5: `kind` = TRANSPORT_V1, `nonce`, `outcome`, `summary`, `private` |
| transport.summary | 3: `name` = `summary.json`, `bytes`, `sha256` |
| transport.private[i] | 3: `name`, `bytes`, `sha256`; lista ordenada, sem nome repetido |
| summary | 10: `kind` = SUMMARY_V1, `nonce`, `outcome` (`APPROVED`/`REJECTED`), `scope` = `BENIGN_CONTROL_ONLY`, `admission_3s` = `NOT_MEASURED`, `cases` (3), quatro pins |
| summary.cases[i] | 13 `CASE_KEYS`; `ready` nulo para NORMAL; `inner_closed`/`audit_*`/`terminate_calls` nulos fora do caso 3; enums fechados de `outcome`, `rejection` (13 rótulos do orquestrador) e `framing` (`LF`/`CRLF`/nulo) |
| invocation.json | 11: `kind` = INVOCATION_V1, `nonce`, quatro pins, `limits`, `case`, `number`, `argv`, `environment_names` |
| supervision.json | 15: `kind` = SUPERVISION_V1, `case`, `owner_state`, e os 12 de `_fields` (`reason` em 10 motivos fechados ou nulo; `turns` int ≥ 0) |
| snapshot.json | 2: `kind` = SNAPSHOT_V1, `snapshot` nulo ou 6 chaves (`valid`, `total`, `active`, `members`, `inner_present`, `inner_verified`) |
| audit.json | 5: `kind` = AUDIT_V1, `integral`, `limit`, `entries`, `terminate_calls` |

## 5. Semântica por arquivo

- Invocation: `case`/`number` do caso; `argv` exatamente
  `[argv0, "-I", "-B", "-c", LITERAL]` (literal NORMAL ou SLEEP do
  orquestrador); `limits` igual, com tipos, a 60.0/10.0/1200/200/10.0/200/
  1024/512/2; `environment_names` igual, em ordem, aos 10 nomes do chamador.
- Supervision: `owner_state = CLOSED`; `case` correto; `exit_code`,
  `total_processes`, `terminated`, `seconds` iguais ao caso do summary;
  `ready` igual ao summary fora de NORMAL; NORMAL com `ready = false` e
  `ready_turns = 0`; `ready_turns` ≤ 200; `seconds` não negativo. O nome do
  caso dentro do arquivo deve ser o do diretório (`SUPERVISION`).
- Stdout: `retained_stdout_bytes` igual ao tamanho; `framing` recalculado
  (linha exata do literal com LF ou CRLF, senão nulo) igual ao summary.
- Snapshot: `valid` declarado igual ao predicado recalculado dos 6 campos
  (`total` int em {1, 2}, `active == total`, `members == active`, todos int
  não `bool`, `inner_present` e `inner_verified` verdadeiros). Nulo só se o
  caso no summary é `REJECTED`. Motivo `SNAPSHOT_INVALID` exige snapshot
  presente e inválido.
- Audit: `limit = 512`; `entries` até 512 `str` de 1–64 caracteres;
  `terminate_calls` igual à contagem de `TerminateJobObject` e
  `TerminateProcess`; `audit_integral`, `audit_entries` e `terminate_calls`
  do summary iguais.

## 6. Lote e prefixo

Casos na ordem NORMAL, TERMINATE, LAST_CLOSE. `APPROVED` exige os três
`APPROVED` e os 11 arquivos. Senão, o primeiro não aprovado é `REJECTED`
(nunca `NOT_RUN`), os seguintes são exatamente `NOT_RUN` (todas as outras
11 chaves nulas) e o conjunto é 3, 6 ou 11 arquivos. `REJECTED` nunca vira
aprovação.

## 7. Veredito recalculado (independente do produtor)

`proven`: `overflow` falso, `signaled` e `eof` verdadeiros, `total_processes`
int em {1, 2}, `exit_code` int, `framing` não nulo e `seconds` float (o
orquestrador troca o motivo quando a leitura final falha). Aprovação:
NORMAL `proven`, motivo nulo, não terminado, saída 0; TERMINATE `proven`,
`ready`, motivo `DEADLINE`, terminado, saída 1; LAST_CLOSE `proven`,
`ready`, motivo nulo, não terminado, snapshot válido, `inner_closed`
verdadeiro, auditoria íntegra e zero terminate. Rejeição na precedência do
orquestrador: `AUDIT_INVALID`, `FAILED_LAST_CLOSE`, motivo (exceto
TERMINATE/DEADLINE), `MISMATCH`. Divergência de `outcome`/`rejection` do
summary é `CONTRADICTION`, mesmo com todos os hashes recalculados.

## 8. Lacunas declaradas

- `inner_closed` só existe no summary: autodeclaração do produtor; nomes da
  auditoria não o provam.
- Nenhum artefato contém pins da entrada ou do orquestrador; esses ficam na
  pré-checagem externa. Esquemas aceitos não são ampliados.
- Sem teto global de 60 s em LAST_CLOSE (o orçamento reinicia após fechar
  INNER).
- Bytes fornecidos pelo chamador podem já ter sido alocados por ele; os
  tetos limitam o trabalho do núcleo, não a memória do chamador.

## 9. Testes (fakes, sem execução nativa)

Fixtures escritas à mão no teste (literais de pins/limites/modelos e fatos
coerentes); o montador só recalcula hashes e o resultado do lote, sem usar o
produtor nem constantes do verificador como oráculo. Positivos: APPROVED com
LF e CRLF; REJECTED nos casos 1, 2 e 3 (3/6/11 arquivos), incluindo
FAILED_LAST_CLOSE, snapshot nulo, SNAPSHOT_INVALID, AUDIT_INVALID e
CALLER_CLOCK. Adversários: contradições com hashes recalculados, arquivos e
nomes faltantes/extras/inválidos (travessia, ADS, absoluto, barra invertida,
maiúsculas, NUL), pins/nonce/argv0/limites/ordem de ambiente/tipos,
`bool` como int e subclasses de `str`/`bytes`/`dict`, JSON malformado/
excessivo/profundo, enums desconhecidos, stdout/framing, prefixo, todos os
bits do snapshot, auditoria, falha interna sem texto, controle propagado,
pureza de import e ausência de efeitos.

Testes acrescentados antes do código nesta rodada (requisito do root, não
defeito descoberto): o seam `_digest` muta o `dict` original e os campos do
`Expected` durante a validação, e o resultado continua refletindo a cópia
capturada; mais de 64 entradas dão `CAP` sem tocar métodos hostis; 64
nomes desconhecidos dão `FILESET`. Estilo dos testes ajustado sem remover
casos nem asserções (opções agrupadas em `last_close`/`build`, comentários
encurtados, assert final formatado).

### Achado da revisão de c833e4c8 (regressões antes da correção)

Candidato `c833e4c86109f49275b88471bf4b40b88ab0f7ba28af46bb7ffba3547df7e69d`
(24292 bytes) e testes `4fe9fb07…0058` (41511 bytes) preservados pelo root
como dados de revisão rejeitada em
`docs/poc/evidence/native-verify-review-20261103`; nenhuma execução nativa.
Um P2, classe de domínio numérico nativo: com todos os hashes recalculados e
summary/supervisão coerentes, `exit_code` −1 ou 2**32 no LAST_CLOSE era
aprovado, e `total_processes` ou contadores do snapshot (`total`, `active`,
`members`) −1 ou 2**32 em casos coerentes REJECTED eram aceitos como
REJECTED em vez de INVALID.

Fato de fonte (backend congelado, lido pelo programador em chamada anterior
desta sessão e reconferido pelo revisor): código de saída e
`TotalProcesses`/`ActiveProcesses` são `DWORD`; `members` é o tamanho
não negativo de uma lista de PIDs limitada. O revisor consultou a
documentação primária de `GetExitCodeProcess`
(https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getexitcodeprocess;
não consultada pelo programador), coerente com o domínio
`0 <= valor < 2**32`. A faixa genérica de inteiros do parser JSON não é o
domínio do campo.

Invariante da correção futura: antes do veredito semântico, `exit_code` e
`total_processes` (summary e supervisão, anuláveis) e `snapshot.total`,
`snapshot.active` e `snapshot.members` (anuláveis) devem ser `int` exato
(nunca `bool`) em `0 <= valor < 2**32`, senão `INVALID/SCHEMA`, mesmo com
desfecho REJECTED coerente. Nulos de pré-lançamento continuam permitidos e
REJECTED nunca vira APPROVED. Regressões acrescentadas (todos os casos
anteriores intactos): 13 negativos parametrizados exigindo `SCHEMA` e 9
controles positivos (0, 2**32−1, bit alto `0xC000013A` aprovado no
LAST_CLOSE, contadores nulos e pré-lançamento). Fonte do módulo ainda não
alterada nesta etapa; nenhum teste executado pelo programador.

RED medido pelo root antes da correção, com a fonte c833e4c8 inalterada e o
prefixo exato dos 208 casos: 230 coletados, 13 falhas e 217 aprovados
(13 AssertionError, 2,853 s, saída 1). Testes `808869aa…6c14c` (44944 bytes)
e manifesto preservados como dados na mesma pasta de revisão.

Correção (só no módulo; testes inalterados): novo auxiliar de domínio
`_opt_u32` (nulo, ou `int` exato não `bool` com `0 <= v < 2**32`), aplicado
na validação de esquema a `exit_code` e `total_processes` do caso do summary
e da supervisão e a `total`, `active` e `members` do snapshot, antes de
qualquer veredito; violação é `INVALID/SCHEMA`. A gramática de inteiros do
parser JSON não mudou. Também juntada em uma linha a assinatura de `verify`
pedida pelo formatter. Nenhum teste executado pelo programador; verde não
alegado.

## 10. Estado

Módulo implementado (só `dataclasses`, `hashlib`, `json`, `math`, `re`) e
revisado pelo root:230próprios e1301relacionados/22arquivos aprovados,
13contraprovas independentes CLEAN; ver VERIFY-VALIDATION para escopos,
tempos e limitações. Nenhum teste executado pelo programador.
Coletor confiável, pré-checagem nativa (incluindo pins da
entrada e do orquestrador), OS/CIM e proposta de execução continuam
pendentes.
Identidade segue LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED; Native 3 s
NOT_MEASURED, entry_gate NOT_EVALUATED; destino do produto Docker Oracle
Linux 9.8 inalterado; gates de produção abertos.

Pins finais medidos pelo revisor: módulo
`b3755d492ce147596a27dd9a36bc0ecf66686efd65ef60178915ab2d1d1f7a10`
(24616bytes), teste
`808869aac6429d6738d6ee3976e63bdd1f8fdaf491f14385d529c4b173a6c14c`
(44944bytes). O resultado não autentica o produtor nem prova execução
nativa ou origem dos bytes; essas composições ficam fora deste núcleo.
