# Proposta de comando único — captura diagnóstica dos pins

2026-10-31, sob delegação vigente. Desenho34978 e capturadorde8f0391 aceito
20331, sem P1/P2, somente código/fakes. Este arquivo ainda não foi executado.
Não é comando de rodada PG16/Oracle nem de serviço. Proposta/task fixa
3eb3f616e3f24f3e943bd2135b0007ba; evidência ainda ausente. Qualquer falha,
inclusive anterior ao mkdir, consome a proposta; não repetir automaticamente.

Executar uma única vez pela sessão da ferramenta, Windows PowerShell5.1
Desktop (`shell=powershell`), cwd abaixo. É uma invocação Python; o launcher
do venv Windows pode iniciar o interpretador base e aguardar/repassar seu exit.
Não é garantia de um único PID. Nenhuma CLI Docker/PowerShell adicional,
loop/thread do diagnóstico ou processo verificador. Se devolver sessão,
aguardar a mesma sessão até o término. Não iniciar uma segunda invocação.

O comando descarta stderr. Stdout do Python é somente resumo fechado do
capturador, não o relatório. As duas linhas externas são marcadores fixos:
exit observado do Python e fonte pública inalterada. Orçamento exige também
verificação posterior do manifesto e SHA/tamanho do resultado, não só exit.
Não há promessa de teto absoluto para leitura síncrona do filesystem.

## Comando literal proposto

```powershell
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -ne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1){throw 'PIN_CAPTURE_SHELL'}
$repo='C:\Users\w.filho\Desktop\codes\mask'
$python='C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe'
$capture='C:\Users\w.filho\Desktop\codes\mask\docs\poc\pg16_shell_pin_capture.py'
$expected='de8f03910836799f90705265264e2f9fc71c878b517ff06b46c56b7150b0559d'
$evidence='C:\Users\w.filho\Desktop\codes\mask\docs\poc\evidence\pg16-pin-cost-20261031-3eb3f616e3f2'
if((Get-Location).Path -ne $repo){throw 'PIN_CAPTURE_CWD'}
if(Test-Path -LiteralPath $evidence){throw 'PIN_CAPTURE_CONSUMED'}
if((Get-FileHash -Algorithm SHA256 -LiteralPath $capture).Hash.ToLowerInvariant() -cne $expected){throw 'PIN_CAPTURE_SOURCE'}
$savedEnvironment=[Environment]::GetEnvironmentVariables('Process')
$allowed=@('SystemRoot','WINDIR','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA','HOMEDRIVE','HOMEPATH','SystemDrive','ComSpec')
$captureExit=1
try {
    foreach($name in @($savedEnvironment.Keys)){
        if(([string]$name) -notmatch '^=' -and $allowed -notcontains [string]$name){
            [Environment]::SetEnvironmentVariable([string]$name,$null,'Process')
        }
    }
    $nativePreference=$ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        $global:LASTEXITCODE=$null
        & $python -I -B $capture 2>$null
        if($null -eq $global:LASTEXITCODE){throw 'PIN_CAPTURE_NO_EXIT'}
        $captureExit=$global:LASTEXITCODE
    } finally {
        $ErrorActionPreference=$nativePreference
    }
} finally {
    foreach($name in @([Environment]::GetEnvironmentVariables('Process').Keys)){
        if(([string]$name) -notmatch '^=' -and -not $savedEnvironment.Contains($name)){
            [Environment]::SetEnvironmentVariable([string]$name,$null,'Process')
        }
    }
    foreach($entry in $savedEnvironment.GetEnumerator()){
        if(([string]$entry.Key) -notmatch '^='){
            [Environment]::SetEnvironmentVariable([string]$entry.Key,[string]$entry.Value,'Process')
        }
    }
}
if((Get-FileHash -Algorithm SHA256 -LiteralPath $capture).Hash.ToLowerInvariant() -cne $expected){throw 'PIN_CAPTURE_SOURCE_CHANGED'}
Write-Output 'PIN_CAPTURE_SOURCE_UNCHANGED'
if($captureExit -eq 0){Write-Output 'PIN_CAPTURE_EXIT_0'}else{Write-Output 'PIN_CAPTURE_EXIT_NONZERO'}
exit $captureExit
```

Ambiente somente Process, nenhum valor é exibido ou escrito. Entradas especiais
de drive que a API possa devolver começando com `=` não são alteradas pela
API de variáveis; não são variáveis de configuração herdada. Os nomes da
whitelist são comparados sem distinção de caixa. Nenhum PATH, PYTHON, DOCKER,
MASKGW, DSN ou token normal é herdado. USERPROFILE e home são conservados.
finally restaura o ambiente inteiro sem alterar User/Machine. Não usa variável
reservada HOME, home ou CODEX_HOME. Não há comando construído com conteúdo de
arquivo ou ambiente. SHA do capturador é externo; seu self-hash é só dado.
Continue fica restrito à invocação nativa para stderr não interromper o
acompanhamento/exit no Windows PowerShell5.1; demais checagens seguem Stop.
exit encerra somente o processo PowerShell desta exec da ferramenta, depois
da restauração, não uma sessão interativa/persistente do usuário.

## Revisão41271 e correção

Comando inicial recusado por P2: stderr nativo com Stop no PS5.1 pode abortar
antes de observar o exit. Corrigido por Continue local/restauração; fixada
edição5.1Desktop. Corrigidas também duas precisões: launcher pode criar PID
base, cwd agora compara sem caixa. Não houve execução da medição inicial,
nenhum artefato/root criado. Fonte do capturador/testes não mudou.

54015 conferiu o primeiro fix e exigiu explicitar o escopo global de
LASTEXITCODE nas três referências, evitando sombra quando a ferramenta usa
script em vez de Command. Precisão aplicada literalmente acima. Aceite de
54015 condicionado a essa troca está satisfeito, para uma execução somente
leitura depois do commit; nenhuma invocação anterior. Parse PowerShell
conferido sem executar o literal. Nenhum revisor ou job ativo.

## Ainda pendente

Commit do conjunto verificado antes da única execução. Depois dela, guardar
resultado e exit inclusive se NOT_PASSED; não
remover/reexecutar nem criar nova task para eliminar falha ou amostra lenta.
Nenhuma raiz operacional, banco, SQL, secret, worker ou serviço será criado.
Gateway/B1/B2/D090/C1/SQL/produção permanecem indisponíveis ou abertos.
