# One-off qualification of public System.Diagnostics.Process stop primitives (W1, 2026-11-14).
# Oracles: native-stop-qualification-oracles-20261114.json (q0..q6). Not product code, not S/P proof.
# One benign child: the caller-supplied pinned base interpreter, -I -B -S, stdlib time.sleep only.
# No redirection, readers, threads, Add-Type/PInvoke/job/DLL, project import or PID-only reopen/kill.
# A possibly live owned child is never dropped: its natural exit is awaited before Dispose. While
# retained, no wall-clock bound is claimed; callers may monitor this probe process on UNKNOWN.
# An attempted Start with unresolved association keeps this qualification active (held) for
# monitoring; nothing is guaranteed if the host terminates this PowerShell process.
# Senff policy: AI-generated code requires human and security review before use or merge.
param(
    [Parameter(Mandatory = $true)][string]$BaseExecutable,
    [Parameter(Mandatory = $true)][string]$ExpectedSha256,
    [Parameter(Mandatory = $true)][long]$ExpectedSizeBytes
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$MaxSizeBytes = 16777216
$ChildArguments = '-I -B -S -c "import time;time.sleep(30)"'  # constant; no caller text
$R = [ordered]@{
    kind = 'MASKGW_W1_NATIVE_STOP_QUALIFICATION_V1'; status = 'UNKNOWN'; error = 'NONE'
    preflight_ok = $false; instance_before_start = $false; start_returned_true = $false
    associated = $false; first_wait_exited = $null; kill_requests = 0; kill_returned = $false
    exit_observed = $false; has_exited = $false; exit_code = $null; kill_to_exit_ms = $null
    natural_wait_slices = 0; disposed = $false; descendants = 'UNKNOWN'; gates = 'OPEN'
    host_ps = $null; host_clr = $null; host_64bit = $null
}
$Custody = @{ P = $null; StartAttempted = $false; Associated = $false; Exited = $false }  # strong custody

function Set-Error([string]$Category, [string]$Status) {
    if ($R.error -eq 'NONE') { $R.error = $Category }
    $R.status = $Status
}

try {
    $R.host_ps = [string]$PSVersionTable.PSVersion
    $R.host_clr = [string][System.Environment]::Version
    $R.host_64bit = [System.Environment]::Is64BitProcess

    # q0: preflight of the single supplied artifact; nothing is launched before it passes.
    $preflight = $false
    if ($ExpectedSha256 -cnotmatch '^[0-9a-f]{64}$' -or $ExpectedSizeBytes -lt 1 -or $ExpectedSizeBytes -gt $MaxSizeBytes) {
        Set-Error 'PREFLIGHT_PARAM' 'REFUSED'
    } elseif (-not [System.IO.Path]::IsPathRooted($BaseExecutable) -or $BaseExecutable.StartsWith('\\') -or
              ([System.IO.Path]::GetFullPath($BaseExecutable) -ne $BaseExecutable)) {
        Set-Error 'PREFLIGHT_PATH' 'REFUSED'
    } else {
        $root = [System.IO.Path]::GetPathRoot($BaseExecutable)
        $file = [System.IO.FileInfo]::new($BaseExecutable)
        $reparse = [System.IO.FileAttributes]::ReparsePoint
        if ([System.IO.DriveInfo]::new($root).DriveType -ne [System.IO.DriveType]::Fixed) {
            Set-Error 'PREFLIGHT_PATH' 'REFUSED'
        } elseif (-not $file.Exists -or ($file.Attributes -band $reparse) -ne 0) {
            Set-Error 'PREFLIGHT_FILE' 'REFUSED'
        } elseif ($file.Length -ne $ExpectedSizeBytes) {
            Set-Error 'PREFLIGHT_SIZE' 'REFUSED'
        } else {
            $digest = $null
            $stream = [System.IO.File]::Open($BaseExecutable, 'Open', 'Read', 'Read')
            try {
                if ($stream.Length -eq $ExpectedSizeBytes) {
                    $sha = [System.Security.Cryptography.SHA256]::Create()
                    try { $digest = -join ($sha.ComputeHash($stream) | ForEach-Object { $_.ToString('x2') }) }
                    finally { $sha.Dispose() }
                }
            } finally { $stream.Dispose() }
            if ($digest -ceq $ExpectedSha256) { $preflight = $true } else { Set-Error 'PREFLIGHT_DIGEST' 'REFUSED' }
        }
    }
    $R.preflight_ok = $preflight

    if ($preflight) {
        # q1: instance allocated into custody BEFORE Start; direct exe, no shell, empty environment.
        $psi = [System.Diagnostics.ProcessStartInfo]::new()
        $psi.FileName = $BaseExecutable
        $psi.Arguments = $ChildArguments
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
        $psi.EnvironmentVariables.Clear()  # never enumerated or printed
        $Custody.P = [System.Diagnostics.Process]::new()
        $Custody.P.StartInfo = $psi
        $R.instance_before_start = $true
        $p = $Custody.P

        $startRaised = $false
        $Custody.StartAttempted = $true  # set BEFORE Start: from here the instance is held
        try { $R.start_returned_true = ($p.Start() -eq $true) } catch { $startRaised = $true }
        try { $null = $p.Id; $Custody.Associated = $true } catch { $Custody.Associated = $false }
        $R.associated = $Custody.Associated
        if (-not $Custody.Associated) {
            Set-Error ($(if ($startRaised) { 'START_RAISED' } else { 'NOT_ASSOCIATED' })) 'UNKNOWN'
        } elseif ($startRaised -or -not $R.start_returned_true) {
            Set-Error ($(if ($startRaised) { 'START_RAISED' } else { 'START_FALSE' })) 'UNKNOWN'
        } else {
            # q2: first finite wait must be false, then exactly one Kill, then positive exit.
            $first = $null
            try { $first = $p.WaitForExit(500) } catch { Set-Error 'FIRST_WAIT_RAISED' 'UNKNOWN' }
            $R.first_wait_exited = $first
            if ($first -eq $true) {
                Set-Error 'CHILD_EXITED_EARLY' 'FAIL'  # factual exit recorded; never OBSERVED
                $early = $false
                try { $early = $p.HasExited } catch { $early = $false }
                if ($early) {
                    $Custody.Exited = $true
                    $R.exit_observed = $true
                    $R.has_exited = $true
                    try { $R.exit_code = [int]$p.ExitCode } catch { }
                }
            } elseif ($first -eq $false) {
                $clock = [System.Diagnostics.Stopwatch]::StartNew()
                $R.kill_requests = 1
                try { $p.Kill(); $R.kill_returned = $true } catch { Set-Error 'KILL_RAISED' 'UNKNOWN' }
                $exited = $false
                try { $exited = $p.WaitForExit(5000) } catch { $exited = $false }
                $clock.Stop()
                if ($exited -and $p.HasExited) {
                    $Custody.Exited = $true
                    $R.exit_observed = $true
                    $R.has_exited = $true
                    $R.kill_to_exit_ms = [int]$clock.ElapsedMilliseconds
                    $code = $p.ExitCode
                    if ($code -is [int]) { $R.exit_code = $code } else { Set-Error 'EXIT_CODE' 'FAIL' }
                    if ($R.error -eq 'NONE') { $R.status = 'OBSERVED' }
                } else {
                    Set-Error 'EXIT_NOT_OBSERVED' 'UNKNOWN'
                }
            }
        }
    }
} catch {
    Set-Error 'INTERNAL' 'UNKNOWN'
} finally {
    # q3/q4: once Start was attempted, the SAME instance is held until a positive exit is
    # observed, rechecking association each slice; no retry, new child or PID reopen.
    $p = $Custody.P
    if ($null -ne $p -and $Custody.StartAttempted -and -not $Custody.Exited) {
        if ($R.status -eq 'OBSERVED') { Set-Error 'INTERNAL' 'UNKNOWN' }
        while (-not $Custody.Exited) {
            $R.natural_wait_slices = [Math]::Min($R.natural_wait_slices + 1, 1000000)
            $done = $false
            try {
                $null = $p.Id
                $Custody.Associated = $true
                $done = $p.WaitForExit(1000) -and $p.HasExited
            } catch { Start-Sleep -Milliseconds 1000 }  # unassociated or failed: keep holding
            if ($done) {
                $Custody.Exited = $true
                $R.associated = $true
                $R.exit_observed = $true
                $R.has_exited = $true
                try { $R.exit_code = [int]$p.ExitCode } catch { }
            }
        }
    }
    # Dispose only after a positive observed exit, or for an instance whose Start was never
    # attempted; a failed Dispose is a closed category, never the original exception.
    if ($null -ne $p -and ($Custody.Exited -or -not $Custody.StartAttempted)) {
        try { $p.Dispose(); $R.disposed = $true } catch { Set-Error 'DISPOSE_RAISED' 'UNKNOWN' }
    }
    # q5: one bounded closed record; no argv, paths, PID, Process object or original exception.
    [Console]::Out.WriteLine(($R | ConvertTo-Json -Compress))
}
