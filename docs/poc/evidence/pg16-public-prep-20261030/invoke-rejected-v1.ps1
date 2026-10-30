$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$OutputEncoding=[Console]::OutputEncoding
$desktop=@(Get-Process -ErrorAction SilentlyContinue | Where-Object {$_.ProcessName -match '^(Docker Desktop|com\.docker\..*|docker.*|vpnkit)$'})
if($desktop.Count -ne 0){throw 'PG16_PUBLIC_DESKTOP_PRECONDITION'}
& 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' '-I' '-B' 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\pg16_public_run.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-pg16-public-20261030-c3a916a7a7ff43f89608c6e8a1d26428'
exit $LASTEXITCODE
