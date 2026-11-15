# Specific C0 host (root contract supervisor-c0-host-root-contract-20261114.md). One-off SDK
# qualification script, NOT a guardian, owner or framework. Reuses the measured Process
# custody/stop pattern (native-stop-qualification-20261114.ps1, becc5282).
# Modes: TRANSPORT (fixed 127 ASCII 'T' + LF from the direct base, no project import) and,
# in a SEPARATE invocation only after root reviews a TRANSPORT PASS, C0 (published
# oracle9_w1_supervisor_setup_probe.py 43ffbf92, which never calls Owner.start).
# All four pinned artifacts are held open with sharing-READ streams BEFORE the one Process is
# allocated and until after it is disposed. One owned Process, one direct child S. The 30 x
# WaitForExit(500) budget is a decision budget, not an OS deadline; at most one fallback Kill,
# which never passes. Synchronous Read and SDK/filesystem calls have no proven wall-clock
# ceiling; parent-directory trust and TOCTOU are NOT proven; descendants stay UNKNOWN.
# An unresolved start/exit keeps the SAME instance and streams and emits nothing.
# Exactly one final 21-key ASCII record (<=512 bytes incl. one LF) is written at the end.
# Senff policy: AI-generated code requires human and security review before use or merge.
param(
    [Parameter(Mandatory = $true)][string]$Mode,
    [Parameter(Mandatory = $true)][string]$BaseExecutable,
    [Parameter(Mandatory = $true)][string]$BaseSha256,
    [Parameter(Mandatory = $true)][long]$BaseSizeBytes
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$BaseCap = 16777216
$SourceCap = 65536
$Sources = @(
    @{ Name = 'oracle9_w1_supervisor_setup_probe.py'; Size = 13196
       Digest = '43ffbf92c1fb747f61cc764f6db95fdfed800976cfe17cc2bd4e5c8f5657d511' },
    @{ Name = 'oracle9_w1_supervisor_qualification.py'; Size = 25568
       Digest = '999f4a8d627e1550e8c95c6c6fa42aaa7a5edfb7045acbb33ccf51561d5fe015' },
    @{ Name = 'pg16_shell_admission_win32.py'; Size = 31948
       Digest = '10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726' }
)
$TransportCode = "import sys;sys.stdout.buffer.write(b'T'*127+b'\n');sys.stdout.buffer.flush()"
$TransportFrame = ('T' * 127) + "`n"
$C0Frame = "W1C0 OBSERVED DONE CLOSED`n"
$RefusedSteps = @('INPUT', 'CUSTODY', 'LOAD')
$UnknownSteps = @('INPUT', 'CUSTODY', 'LOAD', 'SETUP', 'CLOSE', 'CONTROL', 'INTERNAL')
$C0States = @(
    'EMPTY', 'NEW', 'SETUP', 'READY', 'SETUP_FAILED', 'STARTING', 'LAUNCH_FAILED', 'RUNNING',
    'HELD', 'CLOSED', 'OTHER'
)
$PrimarySlices = 30
$SliceMs = 500
$OutCap = 129

$R = [ordered]@{
    kind = 'MASKGW_W1_C0_HOST_V1'; mode = 'INVALID'; status = 'FAIL'; error = 'NONE'
    instance = 0; start_attempted = 0; start_true = 0; associated = 0; exit_observed = 0
    disposed = 0; assets_closed = 0; stdout_eof = 0; stderr_eof = 0; exit_code = $null
    kill_requests = 0; wait_slices = 0; stdout_bytes = $null; stderr_bytes = $null
    frame = 'ABSENT'; descendants = 'UNKNOWN'; gates = 'OPEN'
}
$Custody = @{
    P = $null; StartAttempted = $false; Associated = $false; Exited = $false
    Assets = [System.Collections.Generic.List[System.IO.FileStream]]::new()
}

function Set-Error([string]$Category, [string]$Status) {
    if ($R.error -eq 'NONE') { $R.error = $Category }
    if ($R.status -ne 'UNKNOWN') { $R.status = $Status }  # UNKNOWN is never downgraded
}

function Test-LocalPath([string]$PathText) {
    # Local absolute canonical drive path on a Fixed drive; no UNC/device/quote/NUL/CR/LF.
    try {
        if ([string]::IsNullOrEmpty($PathText) -or $PathText.Length -gt 1024) { return $false }
        if ($PathText -cnotmatch '^[A-Za-z]:\\') { return $false }
        if ($PathText.IndexOfAny([char[]]@('"', [char]0, "`r", "`n")) -ge 0) { return $false }
        if ([System.IO.Path]::GetFullPath($PathText) -cne $PathText) { return $false }
        $drive = [System.IO.DriveInfo]::new([System.IO.Path]::GetPathRoot($PathText))
        return ($drive.DriveType -eq [System.IO.DriveType]::Fixed)
    } catch {
        return $false
    }
}

function Format-Argument([string]$PathText) {
    # Quote one validated path; double its terminal backslashes (CommandLineToArgvW rule).
    $trailing = $PathText.Length - $PathText.TrimEnd('\').Length
    return '"' + $PathText + ('\' * $trailing) + '"'
}

function Add-Asset([string]$PathText, [long]$Size, [string]$Digest, [long]$Cap) {
    # Opens with sharing-READ, retains the stream BEFORE hashing, hashes the SAME stream.
    if (-not (Test-LocalPath $PathText)) { return 'PREFLIGHT_PATH' }
    $info = [System.IO.FileInfo]::new($PathText)
    $bad = [System.IO.FileAttributes]::ReparsePoint -bor [System.IO.FileAttributes]::Directory
    if (-not $info.Exists -or ($info.Attributes -band $bad) -ne 0) { return 'PREFLIGHT_FILE' }
    if ($Size -lt 1 -or $Size -gt $Cap -or $info.Length -ne $Size) { return 'PREFLIGHT_SIZE' }
    $stream = $null
    try {
        $stream = [System.IO.File]::Open($PathText, [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    } catch {
        return 'PREFLIGHT_OPEN'
    }
    $Custody.Assets.Add($stream)
    if ($stream.Length -ne $Size) { return 'PREFLIGHT_SIZE' }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hex = -join ($sha.ComputeHash($stream) | ForEach-Object { $_.ToString('x2') })
    } finally {
        $sha.Dispose()
    }
    if ($hex -cne $Digest) { return 'PREFLIGHT_DIGEST' }
    return 'NONE'
}

function Get-Frame([byte[]]$Bytes, [int]$Count) {
    if ($Count -eq 0) { return 'ABSENT' }
    if ($Count -ge $OutCap) { return 'OVERFLOW' }
    for ($k = 0; $k -lt $Count; $k++) { if ($Bytes[$k] -gt 127) { return 'MISMATCH' } }
    $text = [System.Text.Encoding]::ASCII.GetString($Bytes, 0, $Count)
    if ($R.mode -ceq 'TRANSPORT' -and $text -ceq $TransportFrame) { return 'T127' }
    if ($R.mode -ceq 'C0' -and $text -ceq $C0Frame) { return 'C0_OBSERVED' }
    # Full closed C0 frame: exactly 'W1C0 STATUS STEP STATE' + one final LF, no CR/extra data.
    if ($R.mode -cne 'C0' -or -not $text.EndsWith("`n")) { return 'MISMATCH' }
    if ($text.IndexOf("`n") -ne ($text.Length - 1) -or $text.IndexOf("`r") -ge 0) { return 'MISMATCH' }
    $parts = $text.Substring(0, $text.Length - 1).Split(' ')
    if ($parts.Count -ne 4 -or $parts[0] -cne 'W1C0') { return 'MISMATCH' }
    $status, $step, $state = $parts[1], $parts[2], $parts[3]
    if ($status -ceq 'REFUSED' -and $RefusedSteps -ccontains $step -and $state -ceq 'EMPTY') {
        return 'C0_REFUSED'
    }
    if ($status -ceq 'UNKNOWN' -and $UnknownSteps -ccontains $step -and $C0States -ccontains $state) {
        return 'C0_UNKNOWN'
    }
    return 'MISMATCH'
}

try {
    if ($Mode -ceq 'TRANSPORT' -or $Mode -ceq 'C0') { $R.mode = $Mode }
    $scriptDir = $PSScriptRoot
    $preflight = 'NONE'
    if ($R.mode -ceq 'INVALID' -or $BaseSha256 -cnotmatch '^[0-9a-f]{64}$' -or
        $BaseSizeBytes -lt 1 -or $BaseSizeBytes -gt $BaseCap) {
        $preflight = 'PREFLIGHT_PARAM'
    } elseif (-not (Test-LocalPath $scriptDir)) {
        $preflight = 'PREFLIGHT_PATH'
    } else {
        # All four named artifacts are held in BOTH modes, before any Process allocation.
        $preflight = Add-Asset $BaseExecutable $BaseSizeBytes $BaseSha256 $BaseCap
        foreach ($source in $Sources) {
            if ($preflight -ne 'NONE') { break }
            $path = [System.IO.Path]::Combine($scriptDir, $source.Name)
            $preflight = Add-Asset $path $source.Size $source.Digest $SourceCap
        }
    }
    if ($preflight -ne 'NONE') {
        Set-Error $preflight 'REFUSED'
    } else {
        $psi = [System.Diagnostics.ProcessStartInfo]::new()
        $psi.FileName = $BaseExecutable
        if ($R.mode -ceq 'TRANSPORT') {
            $psi.Arguments = '-I -B -S -c "' + $TransportCode + '"'
        } else {
            $entry = [System.IO.Path]::Combine($scriptDir, $Sources[0].Name)
            $psi.Arguments = '-I -B -S ' + (Format-Argument $entry) + ' ' +
                (Format-Argument $BaseExecutable) + ' ' + (Format-Argument $scriptDir)
        }
        $psi.WorkingDirectory = $scriptDir
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.RedirectStandardInput = $false
        $psi.EnvironmentVariables.Clear()  # never enumerated or printed
        $Custody.P = [System.Diagnostics.Process]::new()
        $R.instance = 1  # in caller custody before StartInfo and before any Start attempt
        $Custody.P.StartInfo = $psi
        $p = $Custody.P

        $startRaised = $false
        $Custody.StartAttempted = $true  # set BEFORE the one Start: the instance is now held
        $R.start_attempted = 1
        try { if ($p.Start() -eq $true) { $R.start_true = 1 } } catch { $startRaised = $true }
        try { $null = $p.Id; $Custody.Associated = $true } catch { $Custody.Associated = $false }
        if ($Custody.Associated) { $R.associated = 1 }
        if (-not $Custody.Associated) {
            Set-Error ($(if ($startRaised) { 'START_RAISED' } else { 'NOT_ASSOCIATED' })) 'UNKNOWN'
        } elseif ($startRaised -or $R.start_true -ne 1) {
            Set-Error ($(if ($startRaised) { 'START_RAISED' } else { 'START_FALSE' })) 'UNKNOWN'
        } else {
            for ($i = 0; $i -lt $PrimarySlices; $i++) {
                $R.wait_slices = $i + 1
                $done = $false
                try { $done = $p.WaitForExit($SliceMs) } catch { Set-Error 'WAIT_RAISED' 'UNKNOWN'; break }
                if ($done -and $p.HasExited) {
                    $Custody.Exited = $true
                    $R.exit_observed = 1
                    $R.exit_code = [int]$p.ExitCode
                    if ($R.exit_code -ne 0) { Set-Error 'EXIT_CODE' 'FAIL' }
                    break
                }
            }
        }
        if ($Custody.Associated -and -not $Custody.Exited) {
            # Exhausted or unresolved: at most ONE fallback Kill; it never passes.
            Set-Error 'EXIT_NOT_OBSERVED' 'UNKNOWN'
            $R.kill_requests = 1
            try { $p.Kill() } catch { Set-Error 'KILL_RAISED' 'UNKNOWN' }
        }
    }
} catch {
    Set-Error 'INTERNAL' 'UNKNOWN'
} finally {
    $p = $Custody.P
    # Retention: an attempted Start is held, rechecking association/exit in finite slices,
    # until a positive exit; no new child, no PID reopen, no record while unresolved.
    if ($null -ne $p -and $Custody.StartAttempted -and -not $Custody.Exited) {
        while (-not $Custody.Exited) {
            $seen = $false
            try {
                $null = $p.Id
                $Custody.Associated = $true
                $seen = $p.WaitForExit(1000) -and $p.HasExited
            } catch { Start-Sleep -Milliseconds 1000 }
            if ($seen) {
                $Custody.Exited = $true
                $R.associated = 1
                $R.exit_observed = 1
                try { $R.exit_code = [int]$p.ExitCode } catch { Set-Error 'EXIT_CODE' 'UNKNOWN' }
            }
        }
    }
    # Bounded raw reads ONLY after a positive exit: stdout <=129 sentinel, stderr <=1.
    if ($null -ne $p -and $Custody.Exited) {
        try {
            $buffer = [byte[]]::new($OutCap)
            $total = 0
            $stream = $p.StandardOutput.BaseStream
            while ($total -lt $OutCap) {
                $n = $stream.Read($buffer, $total, $OutCap - $total)
                if ($n -eq 0) { $R.stdout_eof = 1; break }
                $total += $n
            }
            $R.stdout_bytes = $total
            $R.frame = Get-Frame $buffer $total
            if ($R.frame -ceq 'OVERFLOW') {
                Set-Error 'STDOUT_OVERFLOW' 'FAIL'  # stopped at the sentinel: never drained
            } elseif ($R.stdout_eof -ne 1) {
                Set-Error 'STDOUT_EOF' 'FAIL'
            }
            $one = [byte[]]::new(1)
            $m = $p.StandardError.BaseStream.Read($one, 0, 1)
            $R.stderr_bytes = $m
            if ($m -eq 0) { $R.stderr_eof = 1 } else { Set-Error 'STDERR_PRESENT' 'FAIL' }
        } catch {
            Set-Error 'READ_RAISED' 'UNKNOWN'
        }
        try { $p.Dispose(); $R.disposed = 1 } catch { Set-Error 'DISPOSE_RAISED' 'UNKNOWN' }
    }
    # An allocated instance whose Start was NEVER attempted owns no process: dispose it, no reads.
    if ($null -ne $p -and -not $Custody.StartAttempted) {
        try { $p.Dispose(); $R.disposed = 1 } catch { Set-Error 'DISPOSE_RAISED' 'UNKNOWN' }
    }
    # Artifact streams close only after a successful Dispose, or when no instance was allocated.
    if ($null -eq $p -or $R.disposed -eq 1) {
        $closed = $true
        foreach ($asset in $Custody.Assets) {
            try { $asset.Dispose() } catch { $closed = $false }
        }
        if ($closed) { $R.assets_closed = 1 } else { Set-Error 'ASSET_CLOSE_RAISED' 'UNKNOWN' }
    }
    # PASS only as the full conjunction; any other path keeps its closed status.
    $expected = $(if ($R.mode -ceq 'TRANSPORT') { 'T127' } else { 'C0_OBSERVED' })
    $positive = ($R.error -eq 'NONE' -and $R.instance -eq 1 -and $R.start_true -eq 1 -and
        $R.associated -eq 1 -and $R.exit_observed -eq 1 -and $R.exit_code -eq 0 -and
        $R.kill_requests -eq 0 -and $R.frame -ceq $expected -and $R.stdout_eof -eq 1 -and
        $R.stderr_bytes -eq 0 -and $R.stderr_eof -eq 1 -and $R.disposed -eq 1 -and
        $R.assets_closed -eq 1)
    if ($positive) {
        $R.status = 'PASS'
    } elseif ($R.error -eq 'NONE') {
        Set-Error ($(if ($R.frame -cne $expected) { 'STDOUT_FRAME' } else { 'INTERNAL' })) 'FAIL'
    }
    # The single final record: closed keys only, explicit LF, no raw child data or paths.
    $json = $R | ConvertTo-Json -Compress
    [Console]::Out.Write($json + "`n")
    [Console]::Out.Flush()
}
