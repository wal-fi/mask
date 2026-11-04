# Aborto pelo operador do controlador benigno estacionado — proposta (documento)

Data: 2026-11-04. Programador Claude2, sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço `medium`.
Proposta V2 escrita sem execução (após revisão do root): naquela etapa nada foi executado,
medido, aberto, hasheado ou encerrado. Nenhum PID, `CreationDate`, caminho,
linha de comando, hash ou nonce real aparece aqui; só placeholders,
preenchidos pelo root a partir do registro local antes de revisar e parsear
cada comando exato.

## 1. Autoridade versus protocolo

- **Autoridade do usuário: não falta.** O AGENTS.md (seção "Delegação vigente
  — 2026-10-20") autoriza seguir autonomamente, substitui os limites de
  autorização por lote e pede que decisões novas registrem que foram tomadas
  sob delegação, sem inventar aprovação individual. Encerrar o **próprio**
  controlador de teste benigno, criado por este trabalho, está dentro dessa
  delegação; o root aceitou prospectivamente a abordagem do handle guardado
  nesses termos. A sugestão anterior do programador de pedir confirmação
  individual era interpretação, não restrição explícita do usuário.
- **Protocolo e permissões: faltavam antes da execução da §10.** O texto histórico diz "Nunca encerrar o
  controlador para obter resultado do exec" (PROCEDURE, seção 4.4), "Não
  existe interface de recuperação" (seção 5) e "Qualquer recuperação futura
  exige protocolo próprio revisado" (ENTRY-DESIGN, seção 8). Este documento é
  esse protocolo, posteriormente revisado pelo root; o AGENTS.md também exige respeitar as
  permissões efetivas das ferramentas e não dispensa revisão.

## 2. Alvo e desfecho

Um único processo: o controlador (`python.exe`) do exec 15007, que emitiu
`IDENTITY` e depois `PARKED/HELD/retained 1` e foi ligado por duas amostras
CIM vivas com `CreationDate` estável. Nunca o pai (redirecionador da venv),
nunca filhos, nunca outro processo.

Desfecho: **`FAILED_ONLY_OPERATOR_ABORT`**, ou `FAILED_ONLY_UNKNOWN` /
`FAILED_ONLY_OBSERVER_CLEANUP_UNKNOWN` quando o efeito ou a limpeza do objeto
de observação não puderem ser confirmados. Nunca PASS, quietude, limpeza,
liberação, causa raiz ou avanço de gate. O diretório privado, o `held.json`,
os pins, as dez fontes e o nonce estão consumidos. Arquivos privados não são
relidos/alterados; nonce e rodada não são reutilizados. Fontes só são conferidas
por hash, nunca alteradas/reexecutadas nesta tentativa. Nenhuma coleta principal
ou mutação do owner por sua API; aborto externo só pelo protocolo abaixo.

O registro histórico das amostras vivas guarda `CreationDate`, nome, pai e
um booleano de "comando esperado"; **não** guarda a linha de comando bruta, e
o root nunca a expõe por ferramenta. Por isso a comparação exata da linha de
comando é feita por um hash preparado na seção 5. O hash não confere
autoridade e não afirma que houve captura bruta original.

## 3. Comportamento do .NET em que o comando se apoia

Fonte primária fornecida pelo root (código de referência do .NET Framework,
não medição local):
<https://github.com/microsoft/referencesource/blob/main/System/services/monitoring/system/diagnosticts/Process.cs>.
Segundo a leitura do root: `Handle` chama `OpenProcessHandle`, que guarda o
handle nativo (`SetProcessHandle`); `StartTime` usa `GetProcessTimes` via
`GetProcessHandle`; `GetProcessHandle` devolve o handle guardado quando
`haveProcessHandle`; `Kill` chama `GetProcessHandle(PROCESS_TERMINATE)`.
Logo, materializar `.Handle` primeiro liga `StartTime` e `Kill` ao **mesmo**
handle aberto. Isso é o código de referência, não o comportamento medido do
runtime local; os comandos só conferem metadados (PowerShell exatamente 5.1,
edição `Desktop`, CLR 4) e não inspecionam DLL, configuração ou binário, nem
criam processo de autoteste. Não há nova busca por PID para o `Kill`, nem
`Refresh`, `Close` ou reabertura entre a conferência e o `Kill`.

## 4. Guardas comuns aos dois comandos

Exec do root com `login: false`, em primeiro plano, sem tty, sem
redirecionamento, sem timeout ou kill do tool. Ambos começam com:

```powershell
$ErrorActionPreference = 'Stop'
$controllerPidText = '<CONTROLLER_PID>'
$parentPidText = '<PARENT_PID>'
$controllerCreation = '<CONTROLLER_CREATION_UTC_US>'
$parentCreation = '<PARENT_CREATION_UTC_US>'
$culture = [Globalization.CultureInfo]::InvariantCulture
$timePattern = '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$'
$version = $PSVersionTable.PSVersion
if ($PSVersionTable.PSEdition -cne 'Desktop' -or $version.Major -ne 5 -or $version.Minor -ne 1 -or $PSVersionTable.CLRVersion.Major -ne 4) { 'REFUSED_RUNTIME'; exit 70 }
$controllerPid = 0
$parentPid = 0
$parsed = [int]::TryParse($controllerPidText, [Globalization.NumberStyles]::None, $culture, [ref]$controllerPid)
$parsed = $parsed -and [int]::TryParse($parentPidText, [Globalization.NumberStyles]::None, $culture, [ref]$parentPid)
if (-not $parsed -or $controllerPid -le 0 -or $parentPid -le 0 -or $controllerPid -eq $parentPid -or $controllerPid -eq $PID -or $parentPid -eq $PID) { 'REFUSED_PLACEHOLDER'; exit 64 }
if ($controllerCreation -cnotmatch $timePattern -or $parentCreation -cnotmatch $timePattern) { 'REFUSED_PLACEHOLDER'; exit 64 }
function Format-UtcMicro([datetime]$value) { $value.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.ffffff', $culture) + 'Z' }
function Get-Utf8Sha256([string]$text) {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $digest = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($text))
    -join ($digest | ForEach-Object { $_.ToString('x2', $culture) })
  } finally { $sha.Dispose() }
}
function Test-SameInstances($controller, $parent) {
  $controller.Count -eq 1 -and $parent.Count -eq 1 -and
  $controller[0].Name -ceq 'python.exe' -and $parent[0].Name -ceq 'python.exe' -and
  [int64]$controller[0].ParentProcessId -eq $parentPid -and
  (Format-UtcMicro $controller[0].CreationDate) -ceq $controllerCreation -and
  (Format-UtcMicro $parent[0].CreationDate) -ceq $parentCreation
}
```

O PID é validado por `TryParse` sem sinal nem espaços, positivo, distinto do
pai e diferente do próprio processo do PowerShell (`$PID`), antes de qualquer
conversão perigosa. Placeholders não substituídos não passam no `TryParse`
nem no padrão de horário. O `CreationDate` de controlador e pai é comparado
com 6 dígitos de microssegundo (truncamento do `ToString`); isso é a
resolução da comparação, não imunidade absoluta a colisões, e a conversão de
cada valor ao microssegundo não foi medida (uma diferença só causa recusa).

## 5. Preparação revisada do hash da linha de comando (somente leitura)

Também é protocolo próprio, somente leitura e sem efeito: uma consulta CIM
dos **mesmos dois PIDs** (sem busca arbitrária), a linha de comando atual só
em memória, estrutura de argv ancorada e nonce exatos conferidos **antes** do
hash. Volta ao tool só o booleano e o digest, nunca a linha de comando.

```powershell
# (guardas comuns da seção 4 acima)
$nonce = '<NONCE32>'
if ($nonce -cnotmatch '^[0-9a-f]{32}$') { 'REFUSED_PLACEHOLDER'; exit 64 }
$tail = ' -I -B .\docs\poc\pg16_shell_native_control_entry.py ' + $nonce
$guard = $false
$digest = ''
try {
  $controller = @(Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $controllerPid" -ErrorAction Stop)
  $parent = @(Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $parentPid" -ErrorAction Stop)
  if (Test-SameInstances $controller $parent) {
    $line = $controller[0].CommandLine
    if ($line -is [string] -and $line.EndsWith($tail, [StringComparison]::Ordinal)) {
      $head = $line.Substring(0, $line.Length - $tail.Length)
      if ($head -cmatch '^"[A-Za-z]:\\[^"]+\\python\.exe"$') {
        $digest = Get-Utf8Sha256 $line
        $guard = $true
      }
    }
    $line = $null
  }
} catch {
  $guard = $false
  $digest = ''
}
if ($guard) { 'PREPARE_GUARD_TRUE ' + $digest } else { 'PREPARE_GUARD_FALSE' }
```

A cabeça aceita é só um caminho absoluto entre aspas, sem aspas internas,
terminando em `python.exe`, seguido exatamente de `-I -B`, do caminho
relativo revisado da entrada e do nonce, sem argumentos extras. O formato real
da linha de comando do controlador **não foi medido**: se não bater, a guarda
é falsa, nada é hasheado e não há aborto (o root revisa). O digest preparado
entra no comando da seção 6 como `<CONTROLLER_COMMANDLINE_SHA256>`.

## 6. Comando de aborto (placeholders apenas)

```powershell
# (guardas comuns da seção 4 acima)
$expectedCommandLineSha256 = '<CONTROLLER_COMMANDLINE_SHA256>'
if ($expectedCommandLineSha256 -cnotmatch '^[0-9a-f]{64}$') { 'ABORT_REFUSED_PLACEHOLDER'; exit 64 }
$verdict = 'ABORT_REFUSED_IDENTITY'
$code = 71
$attempted = $false
$process = $null
try {
  $controller = @(Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $controllerPid" -ErrorAction Stop)
  $parent = @(Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $parentPid" -ErrorAction Stop)
  $known = Test-SameInstances $controller $parent
  if ($known) {
    $line = $controller[0].CommandLine
    $known = $line -is [string] -and (Get-Utf8Sha256 $line) -ceq $expectedCommandLineSha256
    $line = $null
  }
  if ($known) {
    $process = [System.Diagnostics.Process]::GetProcessById($controllerPid)
    $null = $process.Handle
    if ((Format-UtcMicro $process.StartTime) -ceq $controllerCreation) {
      $attempted = $true
      $verdict = 'FAILED_ONLY_UNKNOWN'
      $code = 73
      $process.Kill()
      if ($process.WaitForExit(5000)) {
        $verdict = 'FAILED_ONLY_OPERATOR_ABORT'
        $code = 0
      }
    } else {
      $verdict = 'ABORT_REFUSED_HANDLE_IDENTITY'
      $code = 72
    }
  }
} catch {
  if ($attempted) { $verdict = 'FAILED_ONLY_UNKNOWN'; $code = 73 }
  else { $verdict = 'ABORT_REFUSED_ACCESS'; $code = 74 }
} finally {
  if ($null -ne $process) {
    try { $process.Dispose() }
    catch {
      if ($attempted) { $verdict = 'FAILED_ONLY_OBSERVER_CLEANUP_UNKNOWN'; $code = 73 }
      else { $verdict = 'ABORT_REFUSED_ACCESS'; $code = 74 }
    }
  }
}
$verdict
exit $code
```

Regras:

- `$ErrorActionPreference = 'Stop'` e `-ErrorAction Stop` tornam toda falha
  operacional terminante dentro do `try`; os `catch` só trocam o rótulo e
  nunca imprimem exceção, mensagem, caminho ou linha de comando. A saída é um
  único rótulo fechado e um código.
- **Antes do `Kill`, qualquer divergência, falha de acesso ou exceção recusa
  sem encerrar nada** (64, 70, 71, 72, 74). O hash da linha de comando é
  recomputado localmente e comparado com o preparado; a linha não sai do
  processo do PowerShell.
- **No máximo um `Kill`**, pelo objeto cujo handle já foi materializado e cujo
  `StartTime` conferiu. Sem `Stop-Process`, `taskkill`, nova tentativa,
  `SeDebugPrivilege`, injeção ou segundo controlador.
- **`WaitForExit(5000)`** é só observação limitada, uma vez. Sem confirmação,
  ou com exceção depois de `attempted`, o rótulo é `FAILED_ONLY_UNKNOWN`
  (73), sem retry; nunca PASS.
- **`Dispose`** só do objeto `Process` de observação do próprio root, num
  `try/catch` protegido; falha vira `FAILED_ONLY_OBSERVER_CLEANUP_UNKNOWN`
  (73) se houve tentativa, sem retry nem alternativa; nunca toca handles do
  owner estrangeiro.

Janela de reuso de PID: entre a amostra CIM e a abertura do handle o processo
original pode morrer e o PID ser reutilizado; nesse caso o `StartTime` do
handle novo difere e o comando recusa (72). Depois de aberto o handle, o
processo identificado não pode trocar.

## 7. Antes e depois

Antes (somente leitura): o root preenche os placeholders do registro local,
parseia os dois comandos exatos sem executá-los, reconfere a identidade das
fontes e que não há outro escritor, roda uma vez a preparação da seção 5 e só
então, com guarda verdadeira, um único aborto. Owner, dez fontes, arquivos
privados e coleta principal continuam intocados.

Depois: o pai deve sair naturalmente; o root acompanha só o exec 15007
original e as mesmas instâncias antigas por CIM (ausência ou PID reutilizado
com outra `CreationDate`). Um terminal do exec sem `FINAL` não é PASS. O
fechamento dos handles do controlador pelo núcleo pode afetar membros
associados ao job (o backend usa `KILL_ON_JOB_CLOSE`), mas isso **não** é
prova de quietude do job nem de limpeza.

## 8. Opção separada: resíduos por CIM (somente contagens)

Somente leitura, antes ou depois do aborto, com vínculo forte ao pai
conhecido: processos com `ParentProcessId` igual ao controlador e
`CreationDate` posterior à dele, e, para cada um, seus filhos com
`CreationDate` posterior (profundidade máxima 2). Sai só a contagem por nível
e o rótulo `NOT_PROVEN`. Sem busca arbitrária por `python.exe`, sem PIDs,
caminhos ou linhas de comando na saída, sem encerrar nada. Reuso de PID e a
ausência de visão de pertencimento ao job impedem prova.

## 9. Fora do escopo

O defeito lógico de `accounting`/`_supervise` (total cumulativo contra o
limite de ativos) e sua reprodução com fakes ficam para um lote próprio;
nenhuma fonte consumida muda. Native3s NOT_MEASURED, entry_gate
NOT_EVALUATED; B1/B2/D090gate2/C1/SQL e produção abertos; destino final
Docker Oracle Linux 9.8. Sem Docker/PG/SQL/deploy, outro escritor, conta,
modelo ou contorno de cota.

## 10. Execução posterior pelo revisor — falha consumida

Após os terminais0 de26073/52796, root revisou o protocolo e os dois comandos
concretos, parseados sem erros. Fontes10consumidas e fonte/teste da projeção
conferidos intactos; zero Claude2 ativo. Guardas PS5.1/Desktop/CLR4 e duas
instâncias históricas conferidas. Preparação única retornou guarda verdadeira
e digest; a linha de comando bruta não foi exposta nem publicada. Hash real,
PIDs e CreationDate permaneceram só nos registros locais, não neste documento.

Um aborto único retornou **FAILED_ONLY_OPERATOR_ABORT**, código0 do comando
de observação. Não houve fallback/retry. O comando fixou Handle antes de
StartTime, comparou a identidade e chamou Kill uma vez pelo mesmo objeto;
WaitForExit confirmou saída e Dispose do observador não reportou erro.
O exec original15007 foi recuperado com **terminal-1**, sem FINAL. Nenhuma
passagem ou liberação dos controles é alegada.

Às15:27:40Z as duas instâncias antigas estavam ausentes. Contagens CIM do
parentesco consultado eram0/0 antes e depois; escopo apenas de dois níveis,
**NOT_PROVEN** para quietude do job. Não se encerrou outro processo; o pai
saiu sem ação de término direcionada a ele. Nenhum privado relido/editado,
coleta principal, EOF/sinal, novo controlador, nonce ou rodada. Fontes e
evidência da falha preservadas. Nenhum gate de produto/produção avança.
