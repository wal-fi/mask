# Sonda de identidade pré-nativa — proposta revisada (não executada)

Data: 2026-11-02, America/Sao_Paulo. Proposta sob a delegação geral vigente e
revisão do root; não é aprovação individual do usuário. Programador Claude2,
sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço
`medium`. Documento apenas: nenhum arquivo executável, nonce, raiz, comando
materializado, execução ou medição. Nada aqui foi executado ou parseado pelo
programador; nenhum resultado da sonda existe.

Fontes fixas e não tocadas: entrada publicada em `9e88c13`
(`356d2291…0c6`), orquestrador b4198fe1, adaptador eaebedd6, backend
10c9058f, chamador dfcc4ed6, estado de 16 campos e fontes consumidas. Contexto:
seção 7 de `PHASE-9-W1-PG16-SHELL-NATIVE-CONTROL-ENTRY-DESIGN.md`.

## 1. Histórico: proposta anterior rejeitada

A primeira versão (resposta da chamada 16614, só leitura) propunha um
comando de uma linha com `Set-Location ...;` e um `-c '...'` com aspas
simples dobradas. O root analisou esse bloco com
`System.Management.Automation.Language.Parser.ParseInput` e encontrou 10
erros de parse (UnexpectedToken, MissingExpressionAfterOperator,
ExpectedExpression, MissingEndParenthesisInExpression,
TerminatorExpectedAtEndOfString); a AST do comando Python não foi obtida.
Foi rejeitada e **nunca executada**. Fica só como histórico.

## 2. Objetivo e limite

Uma única execução benigna, pela mesma `.venv\Scripts\python.exe -I -B` e
pelo harness de exec existente, para que o root observe por metadados CIM
somente leitura se o par `controller_pid`/`parent_pid` emitido corresponde a
processos vivos e qual é a forma da família de processos, e se uma linha com
`flush` chega pelo pipe através de um yield real. Não valida aninhamento de
jobs, sinais, cleanup, sobrevivência ao app, C1, admissão nem liberação.

## 3. Invocação prospectiva (PowerShell 5.1)

O diretório de trabalho do exec já é o repositório; não há `Set-Location`,
encadeamento por `;`, base64, `-EncodedCommand`, arquivo, `Start-Process` ou
redirecionamento. O corpo Python fica num here-string de aspas simples (sem
expansão de `$` e sem escapar `'`) e não contém aspas duplas.

```powershell
$identityProbeBody = @'
import json, os, sys, time
p, q = os.getpid(), os.getppid()
ok = type(p) is int and type(q) is int and 0 < p < 2**32 and 0 < q < 2**32 and p != q
r = {'kind': 'MASKGW_PG16_NATIVE_CONTROL_IDENTITY_PROBE_V1', 'event': 'IDENTITY' if ok else 'REFUSED', 'controller_pid': p if ok else None, 'parent_pid': q if ok else None}
sys.stdout.write(json.dumps(r, sort_keys=True, separators=(',', ':')) + chr(10))
sys.stdout.flush()
if ok:
    time.sleep(45)
sys.exit(0 if ok else 2)
'@
& '.\.venv\Scripts\python.exe' -I -B -c $identityProbeBody
exit $LASTEXITCODE
```

- Corpo só stdlib (`json`, `os`, `sys`, `time`), ASCII, finito: um registro,
  `flush`, 45 s de pausa natural (escolhidos, não medidos) e saída 0, ou 2
  quando o par é inválido. O corpo não cria filhos, threads, callbacks,
  arquivos, não lê stdin nem carrega código dinamicamente.
- O terminador `'@` precisa estar no início da linha. A forma das quebras de
  linha entregues ao Python e a passagem do argumento nativo pelo PowerShell
  5.1 não foram verificadas pelo programador.
- Antes de qualquer invocação o root ainda precisa: analisar o bloco inteiro
  com o parser do PowerShell (zero erros) e analisar `$identityProbeBody` como
  Python (`ast.parse`/`compile`) **sem executar**, revisar esta proposta e a
  pré-checagem. O programador não fez esses passos; a análise sintática
  posterior do revisor está registrada na seção 9.
- Exatamente um lançamento; sem rerun automático em nenhum desfecho.

## 4. Esquema e parse estrito

stdout: exatamente uma linha não vazia, no máximo 256 bytes, ASCII, terminada
em LF ou CRLF (o modo texto do Windows pode produzir CRLF); stderr vazio. O
corpo deve ser igual byte a byte à sua recodificação canônica (chaves
ordenadas, separadores `,` e `:`). Objeto JSON estrito: sem chaves
duplicadas, sem NaN/Infinity, chaves exatamente `controller_pid`, `event`,
`kind`, `parent_pid`; `kind` igual a
`MASKGW_PG16_NATIVE_CONTROL_IDENTITY_PROBE_V1`; `event` igual a `IDENTITY`;
os dois PIDs inteiros JSON (nunca `true`/`false`), `0 < valor < 2**32` e
distintos. `REFUSED` ou qualquer divergência é NOT_PASSED. O JSON sozinho
nunca prova existência de processo.

## 5. Fontes primárias consultadas pelo revisor (não pelo programador)

- CPython v3.11.3, `PC/launcher.c`
  (https://raw.githubusercontent.com/python/cpython/v3.11.3/PC/launcher.c):
  segundo o revisor, a variante `VENV_REDIRECT` (linhas 42–44) usa o mesmo
  launcher, e `run_child` (linhas 741–774) cria e configura um Job Object com
  KILL_ON_JOB_CLOSE e SILENT_BREAKAWAY_OK, inicia o filho, tenta atribuí-lo ao
  job e espera por ele. É fato do código-fonte, não atestado do binário
  local, da build, da associação nem do sucesso da atribuição.
- Microsoft, Win32_Process
  (https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-process):
  segundo o revisor, `ParentProcessId` pode apontar para um processo que já
  terminou ou cujo identificador foi reutilizado; `CreationDate` ajuda a
  distinguir instâncias. Evidência CIM é amostral, não garantia global.

Inferência de desenho: o corpo não faz efeitos de job, handler ou handle
explicitamente, mas o launcher da venv pode fazê-los; nenhum binário ou
configuração local foi lido. Logo a sonda não pode validar aninhamento de
jobs, KILL_ON_JOB_CLOSE nem cleanup.

## 6. Ordem de observação e orçamentos

Todos os tempos abaixo são orçamentos de decisão do observador, não limites
absolutos do SO, das chamadas CIM ou do launcher.

1. Pré-checagem só leitura: HEAD revisado, árvore rastreada limpa, nenhum
   Claude CLI ou outro escritor ativo. O root anota o horário de lançamento
   `T0` imediatamente antes da chamada.
2. Lançamento único pelo exec com `yield_time_ms` 10000, stdout como pipe,
   sem tty e sem redirecionamento, para que `IDENTITY` chegue enquanto o
   processo vive. Esperas de polling posteriores no mesmo processo de exec,
   cada uma de no máximo 30 s; nenhuma delas é nova execução de sonda.
3. `IDENTITY` deve chegar até `T0 + 30 s`; senão NOT_PASSED (o processo, se
   existir, só é observado).
4. Depois de pelo menos um yield real, duas amostras CIM somente leitura,
   filtradas por PID e limitadas a quatro propriedades (sem `CommandLine`,
   `ExecutablePath` ou caminhos), com pelo menos 10 s entre elas e antes de
   `T0 + 45 s`:

   ```powershell
   Get-CimInstance -ClassName Win32_Process -Property ProcessId,ParentProcessId,Name,CreationDate -Filter 'ProcessId = <P> OR ProcessId = <Q>' |
       Select-Object ProcessId, ParentProcessId, Name, CreationDate
   ```

   `<P>`/`<Q>` só são substituídos por inteiros já validados pelo parse. Nas
   duas amostras: P e Q existem, os respectivos `CreationDate` permanecem
   iguais entre as amostras, `ParentProcessId` de P é Q, P se chama
   `python.exe` e sua criação não é anterior a `T0`. A criação de Q não
   pode ser posterior à de P. Comparação no mesmo relógio do sistema;
   ambiguidade é NOT_PASSED. Sem enumeração ampla da máquina. Falta de
   amostra viva de qualquer membro dentro da janela é NOT_PASSED.
5. Forma da família (inferência amostral, nunca fato de proveniência): se Q
   existe com `CreationDate` entre `T0` e a de P, Q é tratado como componente
   do próprio lançamento; se Q é anterior a `T0`, é pai persistente (por
   exemplo o shell do harness). O nome `python.exe` em Q **não** prova que o
   binário é o redirecionador da venv. A identidade do shell do harness só é
   conhecida se o root tiver evidência própria (por exemplo, o PID informado
   pelo próprio harness); sem isso não é inventada, e DIRECT/REDIRECTED não
   são certificados como fato, só registrados como forma observada.
6. Saída: código 0 relatado pelo harness até `T0 + 120 s`. Depois, uma
   amostra CIM pelos mesmos PIDs: P ausente, ou presente com `CreationDate`
   diferente (PID reutilizado, conta como instância antiga encerrada). P com a
   mesma `CreationDate` é contradição e resulta UNKNOWN. Q só precisa estar
   ausente se foi tratado como componente do lançamento no passo 5; um pai
   persistente do harness não é vazamento.
7. Estouro do orçamento de 120 s, chamada que não retorna ou ambiguidade:
   UNKNOWN, apenas monitoramento; nenhuma ação nativa nova, retry ou kill. Um
   processo inofensivo remanescente é só observado; nunca se certifica saída
   por tempo esgotado.

PIDs ficam só locais: não entram em evidência persistida, Git ou resumo; o
registro do root guarda forma observada, desfechos e horários.

## 7. Desfechos e abortos

- PASS_SAMPLED (ainda não ocorrido): todos os passos acima conferidos.
- NOT_PASSED: linha ausente, múltipla, >256 bytes, não canônica, `REFUSED`,
  stderr não vazio, P ausente/sem pai Q/`CreationDate` instável ou anterior a
  `T0`, falta de yield ou amostra viva na janela, saída diferente de 0.
- UNKNOWN: orçamento de observação esgotado, término inesperado do harness,
  do app ou da sessão, logoff ou reboot.

Qualquer desfecho diferente de PASS_SAMPLED aborta a progressão: nenhuma
execução nativa dos controles e nenhum rerun automático; decisão do root.

## 8. O que isto não prova

Sinais, Ctrl+Break, fechamento de console, aninhamento e associação a jobs,
KILL_ON_JOB_CLOSE, liberação de handles, cleanup, sobrevivência a
encerramento do app/sessão, proveniência do binário, pin do launcher, C1,
admissão 3 s, release ou gates de produção. Ser só stdlib não significa
ausência de leituras implícitas: a partida do Python lê configuração da venv,
site, stdlib e DLLs. Native 3 s NOT_MEASURED, entry_gate NOT_EVALUATED;
Gateway indisponível e B1/B2/D090/C1/SQL/produção abertos.

## 9. Revisão documental e sintática — root, 2026-11-02

CLI10438 terminou0 na mesma sessão/modelo/esforço e escreveu somente este
documento. Não houve código executável, teste ou fonte consumida alterado.
O revisor reforçou a existência/estabilidade amostral de Q, sem transformar
parentesco observado em proveniência de binário ou autorização para controle.

O bloco PowerShell revisado foi analisado com ParseInput: zero erros, um
único here-string literal. O conteúdo foi extraído da AST e passado apenas
a `ast.parse`, com conferência de ASCII e dos quatro imports permitidos.
Resultado final: PowerShell PASS/Python AST PASS/ASCII PASS,exit0; corpo da
sonda **não executado**. Isso não mede a entrega do argumento pela fronteira
nativa do PowerShell. Na primeira tentativa, o próprio checker do revisor
teve NameError por aspas duplas em seu argumento `-c`; corrigiu-se somente
esse checker efêmero e repetiu-se a análise. Não foi falha da sonda e não
houve execução dela nem alteração dos snippets para aprovar a análise.

O parecer aceita este procedimento prospectivo dentro dos limites descritos.
Ainda é necessário reconferir preflight, ausência de escritor e invocação
exata antes de lançar qualquer sonda. Não há resultado PASS_SAMPLED, nova
evidência nativa ou liberação dos controles. Sem nova quota/reset ou tarefa.
