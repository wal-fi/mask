# Diagnóstico do registro HELD — contrato prospectivo (testes antes do módulo)

Data: 2026-11-04. Contrato **novo e separado** do PROCEDURE histórico,
proposto pelo root sob a delegação geral do usuário; não é permissão vinda do
nonce, não aprova retroativamente os controles e não é aprovação individual.
Programador Claude2, sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`,
`claude-opus-5-5`, esforço `medium`. Na primeira etapa existiam só este documento e
`tests/test_pg16_shell_native_control_held_projection.py`; o módulo
`docs/poc/pg16_shell_native_control_held_projection.py` não existia na etapa
de testes; foi implementado na V2 (seção 0). Nenhum teste executado pelo
programador; nenhum arquivo privado lido.

Estado no momento do contrato (histórico; atualização ao fim da §5): o controlador do exec 15007 seguia
`PARKED/HELD`, `retained 1`, sem `FINAL` nem terminal; nada o toca (sem sinal,
fechamento, kill, EOF, novo controlador, retry, reuso do nonce ou mutação de
owner). A coleta principal continua proibida após PARK. As dez fontes
consumidas, o estado16, os brutos privados e a evidência ficam congelados.
Não há promessa de recuperação.

## 0. Estado (V2)

RED medido pelo root com o módulo ausente: 107 coletados, 105 erros de setup
+ 2 falhas, todos `FileNotFoundError`, 0,963 s (ausência do recurso, não
regressão); baseline e teste arquivados como dados em
`native-held-projection-review-20261104`. Na V2 o teste recebeu só duas
mudanças mecânicas autorizadas: a constante fictícia `SECRET` passou a
`SYNTHETIC_MARKER` (Ruff S105; não é credencial real) e a assinatura de
`test_unknown_labels_and_wrong_types_are_refused` ficou numa linha. Nenhuma
asserção, caso, fixture ou decorador mudou.

Implementado `docs/poc/pg16_shell_native_control_held_projection.py`: só
`json`, só definições; `_decode` (bytes exatos ≤4096, um LF, ASCII, JSON
estrito com `object_pairs_hook` contra duplicatas e `parse_constant` contra
NaN/Infinity, reencodificação canônica idêntica), `_valid` (17 chaves, tipos
exatos, listas brancas literais, limites, `seconds` nulo, auditoria limitada
só no LAST_CLOSE), `project` (12 chaves fixas no sucesso; recusa fresca e
fechada para qualquer `Exception`). Testes, lint e tipagem não foram
executados pelo programador; resultado então a medir pelo root. Até a V2,
nenhuma leitura real havia acontecido; a leitura única posterior está na §5.

## 1. Produtor (lido nas fontes consumidas)

`_held_raw` do orquestrador (`b4198fe1`) grava, uma única vez, `held.json` em
`case-N/` com `host.encoded(record) + b"\n"` (`json.dumps` com `sort_keys`,
separadores `,`/`:`, `allow_nan=False`, ASCII). As 17 chaves:

- `kind` = `MASKGW_PG16_NATIVE_CONTROL_HELD_V1`; `held` (rótulo); `case`
  (`NORMAL`, `TERMINATE`, `LAST_CLOSE`); `owner_state` (`str` ≤32 ou `null`);
  `audit` (`null`, ou no LAST_CLOSE `{"partial": true, "valid": bool,
  "entries": [str 1..64, ...]}`);
- de `_fields`: `reason` (`str` ou `null`), `terminated`, `overflow`,
  `signaled`, `eof` (`bool`), `exit_code`, `total_processes` (`int` ou
  `null`), `turns` (`int`), `ready` (`bool`), `ready_turns` (`int`),
  `retained_stdout_bytes` (`int`), `seconds` (sempre `null` aqui: só é
  atribuído em `_finish`, que nunca precede `_held`).

Estados do `Owner` no backend `10c9058f` (o adaptador não acrescenta):
`NEW`, `SETUP`, `SETUP_FAILED`, `READY`, `STARTING`, `LAUNCH_FAILED`,
`RUNNING`, `HELD`, `CLOSED`. Motivos: `REJECTIONS` do orquestrador.

**Incompatibilidades reais, tratadas como recusa (não alargam a saída):**

1. O produtor também pode gravar `held` = `INTERNAL` ou `INTERRUPTED`, pelo
   caminho `_contain` (falha comum ou controle no ciclo de vida). Esses
   caminhos levam a `CONTROL_INTERNAL` ou ao controle original, não a
   `CONTROL_HELD`; como o PARK observado é `HELD`, ficam fora da lista
   branca e são recusados.
2. Um registro LAST_CLOSE com auditoria pode passar de 4096 bytes (até 512
   entradas de até 64 caracteres). Acima do teto, recusa; nunca truncar.

## 2. Função pura futura

`project(raw) -> dict`, sem CLI, sem efeito de import, sem sistema de
arquivos, processo, sinal ou chamada nativa; imports só `json`/`math`.

Entrada: `type(raw) is bytes`, 1..4096 bytes, termina num único LF;
decodificação ASCII; JSON estrito (sem chave duplicada, NaN, Infinity,
overflow ou profundidade excessiva, todos capturados); objeto com exatamente
as 17 chaves; reencodificação canônica igual aos bytes. Tipos exatos (`bool`
não é `int`), sem igualdade de objetos estrangeiros; inteiros não negativos
`< 2**32`, `ready_turns ≤ 200`, `retained_stdout_bytes ≤ 1024`; `seconds`
`null`; `audit` `null` fora do LAST_CLOSE e com forma limitada no LAST_CLOSE.

Sucesso (só rótulos fechados): `kind` =
`MASKGW_PG16_HELD_PROJECTION_DIAGNOSTIC_V1`, `outcome` =
`HELD_PROJECTION_DIAGNOSTIC`, `case`, `held` (os 11 rótulos `LAUNCH`,
`CLOSE_INNER`, `CLOSE`, `READY`, `TERMINATE`, `CLEANUP`, `READ`, `WAIT`,
`ACCOUNTING`, `MEMBERS`, `EXIT`), `owner_state` (lista branca acima ou
`null`), `reason` (`REJECTIONS` ou `null`), `terminated`, `signaled`, `eof`,
`ready`, `source_provenance` = `UNATTESTED`, `native_release` =
`NOT_PROVEN`.

Qualquer falha: um único dicionário fechado (`outcome` =
`HELD_PROJECTION_REFUSED`, `error` = `HELD_PROJECTION_INPUT`, mais
`source_provenance`/`native_release`). Nunca ecoa texto da entrada, números,
caminhos, PIDs, argv, entradas de auditoria ou exceções.

## 3. Leitura futura pelo root (não autorizada por esta etapa)

Uma única leitura limitada de **no máximo um** `held.json`, só depois de
revisão do contrato, dos testes, do módulo e da QA exata: caminho derivado do
nonce exato e de `case-1..3`, metadados por `lstat` (regular, sem reparse),
ancestrais reais, `fstat` do handle aberto igual ao `lstat`, leitura de até
4097 bytes; sem listagem ampla nem outros arquivos. Os bytes vão só para
`project`; nenhum bruto em ferramenta, conversa ou Git, só o dicionário
projetado.

Limites: verificações comuns de caminho têm TOCTOU e não provam
proveniência. O resultado é diagnóstico `UNATTESTED`: nunca identidade,
registro autoritativo, liberação, gate ou prova de causa raiz. Não se alega
custódia segura do coletor nativo.

## 4. Testes (antes do módulo)

Pureza do import e do fonte; registros sintéticos válidos de NORMAL,
TERMINATE e LAST_CLOSE (auditoria com segredo não exposta); todos os 11
rótulos, os 9 estados e os 13 motivos aceitos; tipos exatos de entrada;
bytes não canônicos, sem LF, com CRLF, não ASCII, lista, acima do teto
(LAST_CLOSE de 4096 aceito e de 4097 recusado); erros de JSON estrito;
chaves faltando ou extras; rótulos desconhecidos (inclusive `INTERNAL`/
`INTERRUPTED`) e com segredo; `bool` como `int`; valores fora dos limites;
`seconds` não nulo; auditoria malformada ou grande demais; entradas hostis
que não fazem levantar. Native3s NOT_MEASURED, entry_gate NOT_EVALUATED,
B1/B2/D090/C1/SQL e produção abertos; identidade de 2026-11-02 inalterada.

## 5. Gates e leitura diagnóstica medidos pelo revisor

CLI84834 terminou0 antes dos gates. Fonte pura
`9e3c52d49b0c196d4c276bd5b56683da5ba918421f3f0c6b20e9aec3ffe069f3`
(5757bytes); teste
`c7cd9fac21b01c63b5576109cbab3ef57b1ebe1186decf39c28b88ceaac03086`
(13552bytes). **107/107** próprios em **1,257s** e **975/975** relacionados
em **48,837s**, sem falhas/erros/skips. Ruff do teste, erros de PoC, format2
e mypy strict1teste alvos3.11/3.14 aprovados; runtime sóWindows3.11.3, PoC
fora do alvo mypy. AST do teste confere com a baseline após apenas rename
do marcador fictício; asserções/casos/fixtures intactos. S105 e a assinatura
fora do formato anteriores foram corrigidos sem supressão; histórico e
baseline como dados em native-held-projection-review-20261104.

CLI87982 somente leitura terminou0 antes da leitura real. Revisou a QA
exata e a implementação anterior, sem reler seus bytes finais; root já
havia lido a fonte inteira e conferido hash/gates. Uma única QA local foi
executada em cwd do repositório, `-I -B`, `login:false`, após reconferir a
mesma instância retida e zero outro Claude2. Só metadados case1..3 e
**exatamente um** candidato: regular, sem reparse, ancestrais reais,
fingerprint lstat/fstat (volume, inode, tipo, tamanho, mtime) igual antes e
depois, máximo4097bytes. SHA da fonte pura conferido antes de executá-la.
Sem listagem ampla ou leitura de outro privado. Saída fechada, não atestada:

| Campo | Rótulo relatado |
|---|---|
| case / held | NORMAL / CLEANUP |
| owner_state / reason | RUNNING / TREE_UNPROVEN |
| terminated / signaled / eof | true / true / true |
| ready | false |
| source_provenance / native_release | UNATTESTED / NOT_PROVEN |

A QA terminou0; isso **não** é terminal do controlador nem prova de release.
Nenhum bruto/auditoria/número/caminho/PID/exceção foi mostrado/exportado.
Recusa da leitura e recusa da projeção têm rótulos fechados distintos,
intencionalmente; controle na QA vira recusa e não autoriza repetição.
Checagens comuns de caminho têm TOCTOU e não atestam origem; os campos são
relato do registro, não prova de causa ou estado atual. Nenhuma nova leitura
automática. Coleta principal não iniciada; sem novo controlador, nativeAPI,
DLL/job/controle/cleanup sobre o owner. Fontes10/estado16 intactos.

Antes do aborto, exec15007 permanecia estacionado, sem FINAL/terminal. Próxima revisão só de
fontes distingue rejeição de política da árvore de prova de quiescência e
propõe recuperação separada; nada implementado/executado nessa direção.
Nenhum gate de produto avança. Resultado em CONTROL-RUN-VALIDATION.

Atualização posterior: o controlador não está mais vivo. Um protocolo
separado revisado de aborto do teste próprio foi aplicado, sem ler novamente
o registro nem reutilizar nonce. Exec15007 terminou-1, sem FINAL; instâncias
antigas ausentes e parentesco CIM0/0 às15:27:40Z não comprovam quietude do job.
Desfecho FAILED_ONLY_OPERATOR_ABORT em CONTROL-ABORT-PROPOSAL §10; não é
PASS, release ou avanço de gates. A seleção975 não executa controles reais.

Revisão final26025 somente leitura terminou0, semP1/P2; quatroP3 de tempo
verbal foram corrigidos editorialmente após o aborto. Em final-review.json,
`poc_errors:true` significa que a análise estática de erros do PoC passou,
não presença de erros. Esse arquivo registra a etapa pré-aborto; o registro
posterior é operator-abort.json. Sem alteração de medições ou novo teste.
