# W1: host H e N-C vivo — desenho prospectivo D4

2026-11-21. Somente desenho, sob HOST-DESIGN-REVIEW HD-R3, HD-R2 e HD-R1 e HOST-BINDING-REVIEW NH3/NH2/NH1 (normativas), com XJ3 e EJ1–EJ6. Claude2, sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, claude-opus-5-5/medium. D4 substitui D3 (`170bf382`), D2 (`3987e239`) e D1 (`ff007326`), que o root preserva. A mudança de D4 se limita às cinco cláusulas da HD-R3. Decisões sob a delegação vigente; não é aprovação individual nem admissão nativa.

**O que não é:**
- fonte, teste, oráculo ou corpo de binding;
- assinatura, direito ou constante nativa numérica;
- valor de caminho, argv preparado, raiz operacional, perfil novo ou canário.

Fonte e teste do host continuam AUSENTES até o root ler todo o desenho, revisar todos os oráculos e medir e congelar o RED.

**Ficam fixos:** XJ3, main S `9ef5a21e` (incluindo o perfil NATURAL), testes `f8d519e5`/`9e1142cf`, entrada `b4826e0b`, N-S `465ae906`, backend `10c9058f`, adaptador `eaebedd6`, C0 `43ffbf92`/`c695a68b`, qualificador `999f4a8d`, pins, app124, state16 e a tentativa.

## 1. Arquivos e fronteira

- **Fonte futuro único:** `docs/poc/oracle9_w1_external_job_host.ps1`.
- **Teste futuro único:** `tests/test_oracle9_w1_external_job_host_fake.ps1`.
- O C0 é só precedente de padrão (custódia, Start, espera, `Dispose`), citado por linha. Não há dot-source, import, segundo Owner, launcher, módulo, framework ou flag de teste.
- **Definição vs execução das portas:** a entrada DEFINE as portas como script blocks que contêm os corpos reais, mas NÃO executa nenhuma. Toda execução de efeito, inclusive construir o binding (`BindNative`), alocar `Process` e capturar streams, acontece por chamada da MESMA lógica testável, na ordem da §7, com as portas da §6. O resultado é capturado em `$C` imediatamente após o retorno.
- **Corpos de binding:** assinaturas e direitos continuam pré-requisito de revisão própria antes do binding real (§12). Nenhum corpo é fixado aqui.

## 2. Entradas de H e de S (simbólicas)

- **Parâmetros de H** (domínios do C0, `ps1:16-19`, `136-138`):
  - `BaseExecutable` ([string], caminho local absoluto);
  - `BaseSha256` ([string], 64 hex minúsculos);
  - `BaseSizeBytes` ([long], 1..teto do C0).
- **Diretório de H:** o diretório do próprio arquivo de H (`$PSScriptRoot`), que contém os artefatos pinados.
- **Os dois inputs exatos do main S** (`_inputs:94-104`, `_prepare:176-185`):
  - `application` = o MESMO valor de `BaseExecutable`, depois de preflight positivo por SHA e tamanho. Ele vira o `application` do Request de P no perfil NATURAL inalterado.
  - `directory` = o diretório de H.
  - Ambos passam ANTES do Start por `Test-W1XLocalPath`, cujo padrão literal e limite são estaticamente IGUAIS a `_LOCAL_PATTERN`/`_PATH_LIMIT` do main S pinado (§10). Falha → REFUSED antes de F, `PARAM`.
- **Processo S:**
  - executável = `BaseExecutable`;
  - argumentos = as flags de interpretador já usadas pelo C0 (`ps1:159-160`), o caminho do main S pinado no diretório de H, depois `application` e `directory`;
  - composição feita só por `Format-W1XArguments` (puro). Os valores validados não contêm aspas; a regra de barras finais de `ps1:78-82` é precedente, conferido por oráculo, não um valor preparado.

## 3. Gramática exata do arquivo

O nível superior contém SOMENTE:
1. **`ParamBlock`:**
   - exatamente os três parâmetros da §2, nessa ordem;
   - cada um com exatamente um atributo `[Parameter(Mandatory = $true)]` e uma restrição de tipo (`[string]`, `[string]`, `[long]`);
   - sem default, sem `CmdletBinding`, sem outro atributo.
2. **`FunctionDefinitionAst`** com os 14 nomes da §4.
   - Cada nome aparece exatamente uma vez, comparado sem diferença de caixa.
   - Sem `filter`/`workflow`, sem blocos `begin`/`process`/`end`/`dynamicparam` nomeados.
   - `param` interno só com restrição de tipo, sem default nem atributo.
3. **UMA última instrução:** o comando `Invoke-W1XHostEntry` com os três parâmetros por nome, passando as variáveis de mesmo nome.

Nada mais é permitido no nível superior: `#requires`, `using`, atribuições, outras instruções, dot-source.

## 4. Funções (14, conjunto fechado) e retornos exatos

| Função | Retorno exato (UM valor) |
|---|---|
| `Invoke-W1XHostEntry` | nada para a lógica; destinos da §9.1 (`exit 0`, `exit 3` ou retenção) |
| `New-W1XCustody` | `[hashtable]` com exatamente as chaves da §5, nos defaults da §5 |
| `Invoke-W1XPort` | `[hashtable]` com exatamente `Status`, `Ref`, `Number`, `Number2` (§5) |
| `Invoke-W1XHostLogic` | `[string]` ∈ {`EMITTED`, `EMIT_RAISED`, `RETAIN`} |
| `Invoke-W1XPreStartRelease` | `[string]` ∈ {`RELEASED`, `RETAIN`} |
| `Invoke-W1XPostExit` | `[string]` ∈ {`RELEASED`, `RETAIN`} |
| `Read-W1XAck` | `[hashtable]` com exatamente `Ack` ∈ {`ADOPTED`,`REFUSED`,`MALFORMED`,`MISSING`}, `Category` ([string] `CAT` XJ3 ou `$null`), `Extra` [int] 0..24, `Fault` [bool] |
| `Read-W1XTuple` | `[hashtable]` com exatamente `Valid` [bool], `Total`/`Active`/`Members` ([int] 0..2 ou `$null`, todos nulos se `Valid` falso) |
| `Test-W1XReleasable` | `[bool]` |
| `Test-W1XLocalPath` | `[bool]` |
| `Format-W1XArguments` | `[string]` |
| `New-W1XRecord` | `[System.Collections.Specialized.OrderedDictionary]` com as 21 chaves |
| `Test-W1XRecordCoherence` | `[bool]` |
| `ConvertTo-W1XRecordLine` | `[string]` ASCII de 1..511 caracteres, SEM LF |

- **Carriers:** `[hashtable]` e `[OrderedDictionary]` são os ÚNICOS carriers compostos. Cada função devolve EXATAMENTE um valor via `return $<variável>`.
- **Guarda de tipo exato:** o chamador nunca usa `-is` sozinho, que só testa compatibilidade. A guarda é `$null -ne $v` E `$v.GetType() -eq [<tipo declarado>]`, seguida, para dicionários, da contagem e do conjunto exato de chaves. Para escalares (`[string]`, `[bool]`, `[int]`, `[UInt64]`) vale a mesma igualdade de tipo.
- Array, `[object[]]`, coleção de resultados ou valor coagido são recusados como falha.
- **Buffers:** nenhuma função devolve `[byte[]]`. A lógica aloca os buffers e os passa às portas.

## 5. Resultados de porta, custódia e referências

**Resultado normalizado:** `Invoke-W1XPort` chama a porta por nome e normaliza o retorno para `{Status, Ref, Number, Number2}`.
- `Status` é uma string do conjunto da porta (§6), que SEMPRE inclui `CONTROL`.
- TODO retorno bruto, inclusive `CONTROL`, é UM `[hashtable]` com EXATAMENTE as quatro chaves `Status`, `Ref`, `Number`, `Number2`, sob a guarda de tipo exato da §4. `CONTROL` exige `Ref` não nulo (objeto de controle opaco) e `Number`/`Number2` nulos.
- Uma exceção ordinária, ou qualquer forma inválida, vira o status de falha fechado da porta (coluna "Falha" da §6). Isso inclui: chave faltante ou extra, array de resultados, `CONTROL` com `Ref` nulo ou com número não nulo. Nunca se inventa um objeto de controle.
- `Ref` é uma referência OPACA ou `$null`. Ela é guardada só por identidade num slot. Nunca é comparada com outra, convertida, formatada, enumerada ou serializada. O único teste admitido é presença com `$null` à esquerda.
- `Number`/`Number2`: `[int]` (contagens, `ExitCode`, leitura) ou `[UInt64]` (só `DeriveC`), ou `$null`. O tipo errado é tratado como falha.
- **Nos fakes**, uma `Ref` é qualquer objeto novo (por exemplo `[object]::new()`). O adaptador real futuro decide a representação sob revisão própria, sem que isso seja admitido aqui.

**Custódia `$C`** (criada por `New-W1XCustody` na entrada, antes de qualquer efeito, nunca substituída), com estas chaves exatas:

| Chave | Domínio | Default |
|---|---|---|
| `Asset` | hashtable com chaves fixas `BASE`,`S_MAIN`,`ENTRY`,`NS`,`BACKEND`; valor `Ref` ou `$null` | as 5 chaves com `$null` |
| `AssetState` | hashtable com as mesmas 5 chaves; `NONE`/`OPEN`/`UNKNOWN`/`VERIFIED`/`MISMATCH`/`CLOSED`/`CLOSE_RAISED` | todas `NONE` |
| `Bind` | `NONE`/`OK`/`FAILED`/`UNKNOWN` | `NONE` |
| `F`, `Q` | `Ref` ou `$null` | `$null` |
| `FState`, `QState` | `NONE`/`KNOWN`/`REFUSED`/`UNKNOWN`/`CLOSED`/`CLOSE_RAISED` | `NONE` |
| `Pre` | `OK`/`MISMATCH`/`UNKNOWN`/`NOT_RUN` | `NOT_RUN` |
| `PS` | `Ref` ou `$null` | `$null` |
| `PSState` | `NONE`/`ALLOCATED`/`CONFIGURED`/`UNKNOWN`/`DISPOSED`/`DISPOSE_RAISED` | `NONE` |
| `Start` | `NEVER_ATTEMPTED`/`POSITIVE`/`UNCERTAIN` | `NEVER_ATTEMPTED` |
| `In`, `Out`, `Err` | `Ref` ou `$null` | `$null` |
| `Streams` | `NONE`/`OK`/`UNKNOWN` | `NONE` |
| `InState` | `NONE`/`OPEN`/`CLOSED`/`CLOSE_RAISED` | `NONE` |
| `CValue` | `[UInt64]` ou `$null` | `$null` |
| `CState` | `NOT_ATTEMPTED`/`OK`/`REFUSED`/`UNKNOWN` | `NOT_ATTEMPTED` |
| `Xfer` | domínio XJ3 §10 | `NOT_ATTEMPTED` |
| `Ack` | domínio XJ3 §10 | `NONE` |
| `AckExtra` | [int] 0..24 | `0` |
| `Unconfirmed` | [bool] (§8.3) | `$false` |
| `Exited` | [bool] | `$false` |
| `ExitCode` | [int] ou `$null` | `$null` |
| `Fallback` | [bool] | `$false` |
| `Run` | domínio XJ3 §10 | `NOT_RUN` |
| `PostTotal`, `PostActive`, `PostMembers` | [int] 0..2 ou `$null` | `$null` |
| `XTerm` | domínio XJ3 §10 | `NOT_REQUESTED` |
| `XClose` | domínio XJ3 §10 ou `$null` | `$null` |
| `OutExtra`, `StderrPresent` | [bool] | `$false` |
| `FirstError` | categoria XJ3 §10 ou `NONE` | `NONE` |
| `FirstFault` | primeiro objeto de exceção ORDINÁRIA capturado, ou `$null` | `$null` |
| `FirstControl` | primeiro objeto de controle (§9), ou `$null` | `$null` |

Os 21 campos W1XJ1 derivam SÓ dessas chaves.
- `Disposed` deriva de `PSState=DISPOSED`.
- **`AssetsClosed`:** todo asset POSITIVAMENTE adquirido (estado que já passou por `OPEN`) está `CLOSED`, e nenhum asset está `UNKNOWN` ou `CLOSE_RAISED`.
- `NONE` é recurso nunca adquirido: não impede `AssetsClosed` e nunca é marcado `CLOSED`. Um `ABSENT` deixa o próprio asset em `NONE`.
- As exceções de resíduo declaradas da XJ3 (Create/Q incertos) não mudam.

## 6. Portas (corpo na entrada, execução pela lógica)

**Aquisição antes de verificação:** cada porta de aquisição executa UM único passo de aquisição e retorna logo. Toda verificação ou configuração do recurso adquirido é uma porta SEPARADA, chamada só depois de a lógica ter gravado a `Ref` em `$C`. Assim nenhum recurso conhecido fica fora da custódia durante uma verificação que pode falhar.

Todas as portas aceitam também `CONTROL` (§9); a coluna "Falha" é o status para exceção ordinária ou forma inválida.

| Porta | Status no domínio | Falha | Cardinalidade |
|---|---|---|---|
| `OpenAsset(kind)` | `OK`(Ref, stream aberto com leitura compartilhada) / `ABSENT` (positivamente nada aberto: caminho inválido ou atributos recusados antes do open, `ps1:86-90`) | `UNKNOWN` (sem Ref; abertura incerta) | 1 por kind |
| `VerifyAsset(ref, kind)` | `MATCH` / `MISMATCH` (tamanho ou digest no MESMO stream, `ps1:99-106`) | `UNKNOWN` | 1 por kind |
| `CloseAsset(ref)` | `CLOSED` | `RAISED` | 1 por kind |
| `BindNative()` | `OK` / `FAILED` | `UNKNOWN` | 1 |
| `CreateJob()` | `OK`(Ref) / `FAILED` | `UNKNOWN` | 1 |
| `ConfigureJob(F)` | `OK` / `FAILED` | `UNKNOWN` | 1 |
| `DeriveQ(F)` | `OK`(Ref) / `REFUSED` (falha definida, sem efeito) | `UNKNOWN` | 1 |
| `DeriveC(F, PS)` | `OK`(Number=`[UInt64]` 1..2^64−2) / `REFUSED` | `UNKNOWN` | 1 |
| `TerminateJob(Q)` | `RETURNED` | `RAISED` | ≤1 |
| `CloseRef(ref)` | `CLOSED` | `RAISED` (indeterminado) | 1 por ref |
| `NewProcess()` | `OK`(Ref de instância NÃO configurada) | `UNKNOWN` (instância incerta) | 1 |
| `ConfigureProcess(PS, arguments)` | `OK` / `FAILED` (definida, instância conhecida e não iniciada). Corpo: redireção dos três streams, sem shell e sem janela, ambiente limpo (`ps1:153-172`) | `UNKNOWN` | 1 |
| `StartS(PS)` | `TRUE` / `FALSE` | `RAISED` | 1 |
| `CaptureIn/Out/Err(PS)` | `OK`(Ref) | `UNKNOWN` | 1 cada |
| `KillS(PS)` | `RETURNED` | `RAISED` | ≤1 |
| `DisposeS(PS)` | `OK` | `RAISED` | 1 |
| `WriteIn(In, buf, count)`, `FlushIn(In)`, `CloseIn(In)` | `OK` | `RAISED` | 1 cada |
| `EmitRecord(line)` | `OK` | `RAISED` | ≤1 |
| `Sleep(slice)` | `OK` | `RAISED` | repetível nas esperas e na retenção |
| `QueryConfig(ref)` | `MATCH` / `MISMATCH` / `FAILED` | `UNKNOWN` | repetível; só ref `KNOWN` |
| `QueryCounts(ref)` | `OK`(Number=total, Number2=active) / `FAILED` | `UNKNOWN` | repetível; só ref `KNOWN` |
| `QueryMembers(ref)` | `OK`(Number) / `TOO_MANY` / `FAILED` | `UNKNOWN` | repetível; só ref `KNOWN` |
| `Associated(PS)` | `TRUE` / `FALSE` | `RAISED` | 1 (logo após `StartS`) |
| `WaitExit(PS, slice)` | `EXITED` (espera da MESMA instância verdadeira E saída reportada, `ps1:190`) / `RUNNING` | `RAISED` | repetível; só `Start=POSITIVE` |
| `ExitCode(PS)` | `OK`(Number=[int]) | `UNKNOWN` | 1, depois de `EXITED` |
| `ReadOut(Out, buf, off, count)`, `ReadErr(...)` | `OK`(Number 0..count) | `RAISED` / `INVALID` | só leitores da §8; só `Streams=OK` |

**Regras de uso:**
- Uma observação nunca vira certificado de ausência ou de limpeza.
- `Number` ausente ou de tipo errado num `OK` é forma inválida. Nunca há default para `0`, EOF ou `$false`.

## 7. Ordem da lógica (XJ3 §4/§5/§6/§8)

0. **Qualquer `CONTROL`, em qualquer passo:** registro de §9, nenhuma porta de efeito posterior, `RETAIN`.
1. **Preflight:**
   - Para cada um dos 5 artefatos (BASE com os parâmetros; S main `9ef5…`/10.029 B; entrada `b482…`/16.809 B; N-S `465a…`/15.836 B; backend `10c9…`/31.948 B): `OpenAsset` → grava `Ref` e `AssetState=OPEN` → `VerifyAsset` → `VERIFIED` ou `MISMATCH`.
   - Depois, `Test-W1XLocalPath` dos dois inputs de S.
   - `ABSENT`, `MISMATCH` ou input recusado → fechar os assets `OPEN`/`VERIFIED`/`MISMATCH` → registro `REFUSED` (`ASSET`, ou `PARAM` para input), `NO_JOB`.
   - `OpenAsset UNKNOWN`, `VerifyAsset UNKNOWN` ou `CloseAsset RAISED` → `RETAIN`, sem registro.
2. **`BindNative`:** `FAILED`/`UNKNOWN` → fechar assets → `REFUSED`, `INTERNAL`, `NO_JOB`. O binding não tem efeito de job.
3. **`CreateJob`:**
   - `OK` → `F` `KNOWN`, `xjob=1`;
   - `FAILED` → `NO_JOB`/`XJOB_CREATE`;
   - `UNKNOWN` → o mesmo, com resíduo declarado (XJ3 §4.1). Não prova ausência de J.
   - Nos dois últimos: fechar assets → registro `REFUSED`.
4. **`ConfigureJob`**, depois `Read-W1XTuple(F)` + `QueryConfig(F)` → `Pre`.
5. **`DeriveQ(F)`:** `OK` → `Q` `KNOWN`; `REFUSED` → sem efeito; `UNKNOWN` → `Q` `UNKNOWN`, resíduo até o fim de H, nunca usado nem fechado.
6. **Processo:** com `Pre=OK` e Q `KNOWN`:
   - `NewProcess` → `OK`: grava `PS`, `PSState=ALLOCATED`; `UNKNOWN`: `PSState=UNKNOWN` → `RETAIN`, sem descarte nem registro. Instância incerta não é ausência.
   - Com `ALLOCATED`: `ConfigureProcess(PS, Format-W1XArguments(...))` → `OK`: `CONFIGURED`; `FAILED`: segue o item 6.A com instância conhecida e nunca iniciada; `UNKNOWN`: `RETAIN`.
6.A. **Ramo sem Start** (`Pre≠OK`, Q não `KNOWN`, ou `ConfigureProcess FAILED`), com `Start=NEVER_ATTEMPTED` E `PSState` ∈ {`NONE`,`ALLOCATED`}: `Invoke-W1XPreStartRelease`.
   1. Releitura completa NOVA por F; só (0,0,0) válida continua. Caso contrário, `RETAIN`.
   2. `CloseRef(F)` com Q ainda `KNOWN` (se existir). `RAISED` → §7.A, Q retido.
   3. Se Q `KNOWN`: `CloseRef(Q)`. `RAISED` → `XCLOSE_RAISED`, `RETAIN`, sem etapas posteriores.
   4. Se `PSState=ALLOCATED`: `DisposeS`. `RAISED` → `RETAIN`.
   5. `CloseAsset` de cada asset `OPEN`/`VERIFIED`. Qualquer `RAISED` → `RETAIN`.
   6. Registro `REFUSED`, `xclose=PRE_START`, `s_start=NONE`, `post_*=null` (XJ3:197).
   - `PSState=UNKNOWN` nunca entra aqui.
7. **Start** (só com `CONFIGURED`):
   - `Start=UNCERTAIN` é gravado ANTES do único `StartS` (`ps1:176-178`), depois um `Associated`.
   - Só `TRUE` + `TRUE` → `Start=POSITIVE`.
   - Qualquer outro resultado continua `UNCERTAIN` (`ps1:181-184`) e não prova ausência de S. Sem `DeriveC`, sem `CloseIn` (não há stream obtido), sem registro, nunca. `RETAIN`.
8. **Streams:** `CaptureIn` → `CaptureOut` → `CaptureErr`, gravando cada `Ref`.
   - Os três `OK` → `Streams=OK`, `InState=OPEN`.
   - O primeiro `UNKNOWN` encerra as capturas: `Streams=UNKNOWN`, `CState=NOT_ATTEMPTED`, depois `RETAIN` DIRETO.
   - Nesse caso: sem `DeriveC`, escrita, `CloseIn`, espera, kill, sondas ou descarte. F fica retido (XJ3 §4.6 não cumprida).
9. **`DeriveC(F, PS)`:**
   - `OK` → escrita da §8.1;
   - `REFUSED` → `xfer=REFUSED_NO_EFFECT`, um `CloseIn`;
   - `UNKNOWN` → `xfer=UNKNOWN`, um `CloseIn`.
10. **`CloseRef(F)`** (XJ3 §4.6: tentativa de C terminada, Q `KNOWN`). `RAISED` → §7.A.
11. **Ack:** só com `xfer=WRITTEN`, `Read-W1XAck` (§8.2). ADOPTED ou REFUSED válido → `xfer=ACKED`.
12. **`Run`:** uma tupla informativa por Q.
13. **Espera:** fatias `WaitExit` com o orçamento de decisão do C0 (`ps1:43-44`, conferido estaticamente). Sem `EXITED` → UM `KillS`, `Fallback`, novas fatias. Sem `EXITED` depois disso → `RETAIN`.
14. **Pós-saída** (`Invoke-W1XPostExit`, só com `Streams=OK`):
    1. `ExitCode` `OK` obrigatório; `UNKNOWN` → `RETAIN`, sem `Dispose` nem registro.
    2. Leituras da §8.3.
    3. Tuplas por Q em fatias. Liberável → `CloseRef(Q)` → `POST_S`. `active>0` no fim → UM `TerminateJob`, depois novas fatias. Inválida ou sem liberável → `RETAIN`. `CloseRef RAISED` → `XCLOSE_RAISED`, `RETAIN`.
    4. `DisposeS`, depois `CloseAsset`s. Qualquer `RAISED` → `RETAIN`.

**7.B Categoria (`FirstError`, só se ainda `NONE`) por operação:**

| Situação | Categoria XJ3 |
|---|---|
| parâmetros de H fora do domínio, input de S recusado | `PARAM` |
| `OpenAsset ABSENT`, `VerifyAsset MISMATCH` | `ASSET` |
| `BindNative` não `OK`; `Capture*`, `ExitCode`, `OpenAsset`/`VerifyAsset UNKNOWN`; falha de leitor/sonda (§8.3); forma inválida de porta | `INTERNAL` |
| `CreateJob` não `OK` | `XJOB_CREATE` |
| `ConfigureJob` não `OK`, `QueryConfig ≠ MATCH` | `XJOB_CONFIG` |
| tupla `pre` não (0,0,0) válida | `XJOB_PRE` |
| `DeriveQ` não `OK` | `XJOB_ATTENUATE` |
| `NewProcess`/`ConfigureProcess` não `OK`, `Start` incerto | `S_START` |
| `DeriveC REFUSED` | `DUP_REFUSED` |
| `DeriveC UNKNOWN`, qualquer `RAISED` na escrita | `XFER_UNKNOWN` |
| ack `REFUSED` / `MALFORMED` / `MISSING` | `ACK_REFUSED` / `ACK_MALFORMED` / `ACK_MISSING` |
| `KillS` usado | `S_EXIT_FALLBACK` |
| código de saída ≠ 0 | `S_EXIT_CODE` |
| tupla pós-S inválida | `POST_QUERY` |
| `active>0` no fim do orçamento | `POST_ACTIVE` |
| (0,0,0) depois de `ACKED` | `POST_EMPTY` |
| `TerminateJob RAISED` | `XTERM_RAISED` |
| `CloseRef(Q) RAISED` | `XCLOSE_RAISED` |
| `CloseRef(F) RAISED` | `F_CLOSE_RAISED` |
| `OutExtra` / `StderrPresent` | `OUT_EXTRA` / `STDERR_PRESENT` |
| `DisposeS RAISED` / `CloseAsset RAISED` | `DISPOSE_RAISED` / `ASSET_CLOSE_RAISED` |
| `CONTROL` | `CONTROL` |

**7.C Seleção de status** (só para registro emitido):
- `xclose` ∈ {`NO_JOB`, `PRE_START`} → `REFUSED`.
- Senão (`POST_S`), primeira regra que vale:
  1. predicado PASS da XJ3 §12 → `PASS`;
  2. predicado FORCED → `FORCED`;
  3. `xfer=UNKNOWN` ou `ack` ∈ {`MISSING`,`MALFORMED`} → `UNKNOWN`;
  4. demais → `FAIL`.
- `CONTROL` nunca chega aqui: sempre `RETAIN`.

**7.A `F_CLOSE_RAISED`:**
- `FState=CLOSE_RAISED`; a `Ref` permanece em `$C.F` e nunca mais é passada a porta alguma.
- `FirstError=F_CLOSE_RAISED` se ainda vazio.
- Nenhum outro close, `Dispose` ou registro: nunca `POST_S`, `PASS`, `FORCED` ou `PRE_START`.
- Observações posteriores (espera, tuplas por Q) não autorizam fechar Q, declarar F fechado ou emitir.
- Resultado `RETAIN` até o fim de H.

## 8. N-C, emissão e silêncio

**8.1 Escrita:**
- A lógica monta num buffer `[byte[]]` fixo de 23 os bytes ASCII `W1XT1 ` + `CValue` em 1..16 hex minúsculos + LF.
- UM `WriteIn` → `FlushIn` → `CloseIn`.
- O primeiro `RAISED` → `xfer=UNKNOWN`; os passos restantes da escrita não são feitos, exceto UM `CloseIn` se ainda não tentado.
- Três `OK` → `WRITTEN`. Entrega local não é recebimento.

**8.2 Ack** (com `WRITTEN`), `Read-W1XAck`:
- Buffer fixo de 25, `total=0`; laço enquanto `total<25` com `ReadOut(Out, buf, total, 25-total)`.
  - `RAISED`/`INVALID` → `Fault`, `MALFORMED`; para.
  - `Number=0` (EOF) → com `total=0`, `MISSING`; senão `MALFORMED`. Para.
  - Senão, soma e para no PRIMEIRO LF, sem esperar EOF do stdout vivo.
- 25 sem LF → `MALFORMED`.
- `ADOPTED`/`REFUSED <CAT>` exatos, ASCII, sem CR, ≤24 com LF (XJ3 §5).
- `Extra` = só a contagem de bytes depois do primeiro LF no buffer, levada para `OutExtra` após saída positiva.

**8.3 Pós-saída positiva** (só com `Streams=OK`):
- **Leitura da resposta não consumida** (com transferência sem `WRITTEN`: `REFUSED_NO_EFFECT`/`UNKNOWN`/`NOT_ATTEMPTED`): `Read-W1XAck` roda UMA vez sobre `Out`.
  - `ADOPTED` ou `REFUSED <CAT>` de gramática exata → resposta não consumida de S. Não é `OUT_EXTRA` nem recebimento: `Ack` permanece `NONE`, `Unconfirmed=$true`, `Xfer` e erro de transferência inalterados. Aqui `Ack=NONE` significa só "não aceito na fase viva", nunca "nenhuma resposta observada".
  - `MISSING` (EOF sem bytes) → nada.
  - `MALFORMED` (lixo, CR, `CAT` desconhecido, 25 sem LF, EOF depois de bytes) → `OutExtra`.
  - `Extra>0` → `OutExtra`.
  - `Fault` (`RAISED`/`INVALID`) → `INTERNAL` e nenhuma inferência sobre esse stream (nem EOF, nem `OutExtra`). As sondas seguintes de `Out` não são feitas.
- **Sonda final de `Out`**, se não houve `Fault`: `ReadOut(Out, buf1, 0, 1)`.
  - `OK` 0 → EOF; `OK` 1 → `OutExtra`.
  - `RAISED`/`INVALID` → `INTERNAL`, sem default.
- **Sonda de `Err`:** `ReadErr(Err, buf1, 0, 1)`.
  - `OK` 0 → nada; `OK` 1 → `StderrPresent`.
  - `RAISED`/`INVALID` → `INTERNAL`, sem default.
- **Consequência das falhas:** uma `INTERNAL` de leitura não impede o descarte; essa é uma escolha prospectiva, depois de saída positiva e de inventário liberável. O status continua sendo o da seleção da §7.C sobre a primeira categoria: a falha de leitura só impede `PASS`/`FORCED`. Nunca prova EOF nem limpeza de P.
- **Bloqueio:** leitor e sondas podem bloquear. Fatias não são teto de parede.

**8.4 Emissão:**
- Ocorre só se `Invoke-W1XPreStartRelease`/`Invoke-W1XPostExit`, ou o ramo `REFUSED`, liberaram tudo.
- `New-W1XRecord` → `Test-W1XRecordCoherence` → `ConvertTo-W1XRecordLine` (string ASCII ≤511, sem LF; com o único LF, ≤512).
- UM `EmitRecord(line)`, cujo corpo escreve os bytes ASCII da linha mais exatamente UM LF e faz flush (`ps1:279-282`).
- `OK` → `EMITTED`. `RAISED` → `EMIT_RAISED`, sem retry e sem segunda linha.
- Coerência falsa → `RETAIN` (é bug, não categoria).

**8.5 Silêncio e pipeline:**
- Nas 13 funções de lógica, cada instrução é uma destas:
  - atribuição (inclusive `$null = …`);
  - `[void](…)`;
  - `if`/`elseif`/`else`, `while`, `for`, `foreach` (bloco com as mesmas regras);
  - `break`/`continue`;
  - `return $<variável>` ou `return '<literal>'`.
- `try`/`catch` só em `Invoke-W1XPort`; `throw` nunca.
- **Expressões permitidas**, também em condições, lados direitos e laços:
  - variáveis locais e parâmetros; constantes; `$true`/`$false`/`$null`;
  - acesso a membros de `$C`, de carriers de resultado (`$r.Status`) e de `$C.Asset`/`$C.AssetState` por chave literal;
  - operadores de comparação, lógicos e aritméticos sobre `[int]`/`[UInt64]`;
  - `.Length` e índice `[i]` SÓ sobre variáveis locais `[string]` ou `[byte[]]` cujo tipo exato já foi conferido (leitor de ack, montagem do registro W1XT1, regra de aspas). Nenhum outro membro ou método dessas variáveis;
  - a guarda de tipo exato da §4 (`$v.GetType() -eq [T]`, `.Count` e `.ContainsKey('<literal>')`), SÓ sobre carriers de resultado, `$C`/`$C.Asset`/`$C.AssetState` e escalares locais de dados. NUNCA sobre um valor `Ref`;
  - `-in`/`-contains` sobre listas literais.
- **Chamadas permitidas, fechadas:**
  - as 13 funções de lógica pelo nome;
  - `Invoke-W1XPort` com nome literal de porta;
  - `[byte[]]::new(<literal>)`;
  - métodos `GetBytes`/`GetString` de `[System.Text.Encoding]::ASCII` sobre bytes ou texto locais;
  - `$C.CValue.ToString('x')`, só depois da guarda de tipo exato `[UInt64]` e do domínio 1..2^64−2. Produz hex minúsculo sem zeros à esquerda;
  - `ConvertTo-Json -Compress` só em `ConvertTo-W1XRecordLine` e só sobre o `OrderedDictionary`;
  - `[ordered]@{…}` e `@{…}` literais.
- **Proibido:**
  - toda outra chamada de comando, método ou static, inclusive `[System.Convert]::ToString`, que falha a partir de 2^63 (recibo do root `host-design-uint64-format-probe-20261121`);
  - `&`/`.Invoke()` sobre script block (exceto dentro de `Invoke-W1XPort`, que invoca a porta);
  - reflexão (`.PSObject`, `[type]`, `-as`, e `GetType` fora da guarda acima);
  - conversão, cast, interpolação, comparação ou acesso a membro sobre um valor `Ref`. Uma `Ref` só pode ser atribuída de `$r.Ref` a um slot de `$C` e passada como argumento de porta;
  - `Write-*`, `Out-*`, `[Console]`, `$host`, `Read-Host`.
- **Fonte única de stdout:** o único escritor de stdout de H é o corpo de `EmitRecord`. Valores de SDK ou de auxiliares não escapam como saída.
- **Limite:** esta lista é checada por AST (§10). Não é um analisador universal de efeitos e não protege contra objetos com extensões privilegiadas do engine.

## 9. Primeiro erro e controle

**Três slots separados, por identidade, sem formatação e sem substituição:**
- **`FirstFault`:** o primeiro objeto de exceção ORDINÁRIA que `Invoke-W1XPort` captura de uma porta (exceção mapeada para a coluna "Falha" da §6).
- **`FirstControl`:** o primeiro objeto de controle, isto é, a `Ref` de um resultado com status `CONTROL`. Ele é gravado mesmo que `FirstFault` ou `FirstError` já estejam preenchidos.
- **`FirstError`:** a primeira categoria XJ3 pela §7.B. `CONTROL` só entra se ainda estiver `NONE`.
- Um `FirstControl` preenchido força `RETAIN` qualquer que seja a categoria anterior.

**Modelo nos fakes:** uma porta falsa devolve o resultado fechado de quatro chaves `@{Status='CONTROL'; Ref=<objeto opaco novo, não nulo>; Number=$null; Number2=$null}` (§5). Ela NÃO lança `PipelineStoppedException` nem outro sinal de parada real dentro do harness. Assim se testa só o CONSUMO dessa classificação pela lógica.

**Porta real:** o corpo real classificaria uma parada do engine como `CONTROL`. Esse mecanismo NÃO é medido nem admitido aqui; nenhum retorno `CONTROL` de fake é garantia física.

**9.1 Entrada e destinos:**
- Dentro da entrada: `Set-StrictMode -Version Latest`, `$ErrorActionPreference='Stop'`, `$C = New-W1XCustody`, definição das portas (sem executar), depois `try { $o = Invoke-W1XHostLogic … } catch { … }`.
- O `catch` não escreve nada: só atribui `FirstFault` (se vazio), `FirstError` (`INTERNAL` se `NONE`) e `$o='RETAIN'`.
- Destinos:

| `$o` | Destino |
|---|---|
| `EMITTED` | `exit 0` |
| `EMIT_RAISED` | `exit 3`, sem retry, sem segunda linha e sem diagnóstico |
| `RETAIN`, ou qualquer valor fora do conjunto | laço de retenção, que nunca sai: `Sleep` com a fatia de retenção do C0 (`ps1:218-219`) e captura vazia; retém `$C` inteiro, sem close, kill, dispose ou registro |

**NÃO medido e NÃO garantido:**
- que um pedido de parada real do engine chegue a um `catch` ou a uma porta;
- que `catch`/`finally` executem sob parada real;
- que a retenção sobreviva a uma parada do engine;
- que o interpretador não escreva diagnóstico próprio em stderr.

Nenhum sucesso de fake prova isso. Não há guardião genérico.

## 10. Costura de QA falsa

**Executor:**
- O próprio `tests/test_oracle9_w1_external_job_host_fake.ps1`.
- Requisito prospectivo: Windows PowerShell 5.1 Desktop, verificado pelo próprio teste ao iniciar, com falha explícita se não for essa edição. Não afirmo instalação.
- Sem Pester e sem dependência nova.

**Passos:**
1. **Captura única dos bytes do host:** UMA leitura dos bytes do caminho fixo do host (quando existir), SHA-256 calculado e impresso numa linha `SOURCE_SHA256=<hex>` como evidência da captura. O teste NÃO contém SHA esperado do host: a guarda externa do root registra o hash concreto depois da entrega e da revisão, sem reabrir o teste congelado.
2. Decodificar esses MESMOS bytes como UTF-8 estrito para UM texto. Esse mesmo texto é usado no parse (parser nativo sobre o texto, sem reler o arquivo) e na extração. O parse não executa nada.
3. Checar a gramática da §3, o conjunto da §4 e as regras da §8.5.
4. Checar que `Add-Type`/`DllImport`/tipos de `Process`/`[Console]` só aparecem no corpo da entrada.
5. Checar que constantes e literais estão estaticamente iguais a:
   - `_LOCAL_PATTERN`/`_PATH_LIMIT` do main S;
   - orçamento e fatias do C0 (`ps1:43-44`, `218-219`);
   - as 21 chaves da XJ3.
   Os artefatos ANTIGOS (main S, C0) continuam conferidos pelos seus SHAs pinados exatos.
6. Extrair o `Extent.Text` exato das 13 funções, EXCETO a entrada, do texto capturado. Montar UM script block novo com essas definições e o corpo de cada caso, e invocá-lo em escopo filho.
7. Nunca avaliar `param`, entrada, defaults ou a instrução final.

**Portas falsas:**
- Hashtable de script blocks roteirizados que registram chamadas e devolvem os domínios da §6, formas inválidas, exceções ordinárias e o resultado fechado `CONTROL` (§9). Nunca lançam parada real.
- `Sleep` falsa não espera. A retenção é testada só como retorno `RETAIN`; o laço real da entrada é apenas estrutural.

**Contabilidade:**
- Cada caso tem nome único e roda em seu próprio `try`/`catch`; um `throw` não aborta os demais.
- Uma linha `CASE <nome> PASS|FAIL` por caso.
- Resumo final: `W1XH_FAKE TOTAL=<n> SANITY_PASS=<s> PASS=<p> FAIL=<f>`.
- `exit 0` só sem falhas.
- Com a fonte AUSENTE: os casos de fonte falham com o motivo fixo `SOURCE_ABSENT` e as sanidades do checador passam. Esse é o RED medido pelo root.

**Oráculos:**
- **Sanidades** sobre fixtures de texto inertes (só parse):
  - aceitar a forma correta;
  - recusar:
    - instrução extra no nível superior; nome duplicado sem diferença de caixa; default em parâmetro;
    - dot-source; `Add-Type` em lógica; `Write-Output`; `$global:`; `throw` fora da porta; função fora do conjunto;
    - instrução não atribuída; retorno de array;
    - efeito escondido numa condição ou num lado direito (chamada de comando ou método fora da lista, `&`, `.Invoke()`);
    - reflexão (`.PSObject`, `-as`, `GetType` fora da guarda de tipo exato);
    - `GetType`/`.Count`/`.Length` sobre um valor `Ref`; cast, interpolação ou acesso a membro sobre um valor `Ref`;
    - `[System.Convert]::ToString` ou qualquer outro formatador de `CValue`.
  - aceitar: a guarda de tipo exato sobre carriers/escalares; `.Length`/índice sobre `[string]`/`[byte[]]` locais conferidos; `$C.CValue.ToString('x')` depois da guarda.
- **Ramos da §7:**
  - preflight: `ABSENT`, `MISMATCH`, `UNKNOWN`, `CloseAsset RAISED`;
  - recusa no PRIMEIRO asset (`ABSENT`, demais `NONE`) → registro `REFUSED` com `assets_closed=1` e nenhum `CloseAsset`; recusa depois de assets já abertos → só eles fechados; `UNKNOWN`/`CLOSE_RAISED` em qualquer asset → sem registro;
  - escrita W1XT1 com `CValue` de fronteira, sobre valores sintéticos: 2^63−1 → `7fffffffffffffff`; 2^63 → `8000000000000000`; 2^64−2 → `fffffffffffffffe`; e o registro W1XT1 resultante ≤23 bytes;
  - `Bind`; `NO_JOB` falha e incerto;
  - `Pre≠OK` com Q `KNOWN`, `REFUSED` e `UNKNOWN`;
  - `NewProcess UNKNOWN` com `RETAIN` sem descarte; `ConfigureProcess FAILED` com descarte e `UNKNOWN` com `RETAIN`;
  - ordem F → Q → PS → assets e cada `RAISED` dela;
  - Start `UNCERTAIN` em três formas;
  - `Capture*` `UNKNOWN` em cada posição, com `RETAIN` direto e nenhuma chamada posterior;
  - C `REFUSED`/`UNKNOWN`; escrita `RAISED` em cada passo; §7.A.
- **7.B/7.C:** primeira categoria preservada; seleção de status para cada predicado.
- **Ack:** fragmentação, LF no meio, 25 sem LF, EOF com 0 e com bytes, CR, `CAT` desconhecido, excesso, `RAISED`/`INVALID`, `Number` ausente ou de tipo errado.
- **§8.3:** ADOPTED/REFUSED não confirmados vs `MALFORMED`/`Extra` → `OutExtra`; `Fault` sem inferência; cada sonda `OK` 0, `OK` 1, `RAISED`, `INVALID`.
- **Pós-saída:** NATURAL, FALLBACK, `ExitCode UNKNOWN`, `POST_EMPTY`, `POST_ACTIVE` com um terminate, tupla inválida, `XCLOSE_RAISED`.
- **Emissão:** `OK` → `EMITTED`; `RAISED` → `EMIT_RAISED` sem retry; coerência falsa → `RETAIN`.
- **§9:**
  - `CONTROL` em cada fase → `RETAIN` sem efeito posterior;
  - `CONTROL` malformado (sem chave, chave extra, `Ref` nulo, número não nulo, array de resultados) → status de falha da porta, sem objeto de controle inventado;
  - exceção ordinária antes de `CONTROL` → `FirstFault` e `FirstControl` ambos preservados por identidade;
  - segundo `CONTROL` não substitui o primeiro.
- **Cardinalidade:** nenhuma porta de efeito chamada duas vezes em qualquer caso; `Sleep` e observações só nos ramos próprios.

**Limite:** a checagem AST é parcial e específica. Não prova a ausência de efeito de chamadas .NET dentro de portas reais. Positivos e negativos do próprio harness são exigidos. Ordem: oráculos → contraprovas do root → RED congelado → fonte.

## 11. Registro W1XJ1

- **Referência normativa:** as 21 chaves, os domínios, a nullabilidade, a coerência e os predicados da XJ3 §10–§12, sem mudança e sem campo novo.
- **Domínios fixos:** `descendants` sempre `UNKNOWN`; `gates` sempre `OPEN`.
- **Contagem:** `TotalProcesses ≤ 2` vale pela VIDA do job. H e S nunca são membros de J.
- **O que não emite:**
  - PASS com custódia incompleta;
  - inferência de limpeza, de descendentes ou de EOF de P.
- **`Unconfirmed`** não aparece no registro. Só impede tratar bytes como `OUT_EXTRA` ou como recebimento.

## 12. Estrutural vs físico

- **Os fakes provam:** ordem de custódia e portas, ramos, classificação, coerência e tamanho do registro, e as formas de silêncio checadas.
- **Continua pré-requisito físico não medido:**
  - ABI e compilação do binding; assinaturas, layouts, valores de direitos e constantes;
  - R1–R3, direitos de `Process.Handle`, atenuação;
  - identidade, proveniência e atribuição de J entre F, Q e C; `JOB_LIST` com ASSIGN|QUERY e aninhamento;
  - bloqueio real de pipes e EOF;
  - semântica real de parada do engine; efeito de kill/terminate; LAST_CLOSE; descendentes.
- O objetivo de produção não se reduz a passar fakes.

Todos os gates nativos e de produto continuam OPEN. O Gateway segue indisponível.
