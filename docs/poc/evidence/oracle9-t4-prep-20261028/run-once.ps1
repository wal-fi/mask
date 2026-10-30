$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_t4_host.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne '1f70876507c8d35d6bfa35e97ea84831e42a0a20f44cb0dacee7c56427cb23a8') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_t4_run.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne '8580df979222538cc49bb03a04f1c81855d8832236393051ce28d1fcfc07633d') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_t4_prepare.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'fda9be066a6a91197d94e003444026af24980606b71ce49e82c7c9b09949a9cb') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:/Users/w.filho/AppData/Local/Programs/Python/Python311/python.exe' -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'ff9b669828a66882f3d43ed2f9192ea9d8a08f80b8ffbc2186ee946823394418') { throw 'PIN' }
$root = 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-t4-20261028-d5bd03a1adb80cd962fab37ae0bdb78b'
$state = Join-Path $root 'attempt.json'
if (@(Get-ChildItem -LiteralPath $root -Force).Count -ne 1 -or -not (Test-Path -LiteralPath $state -PathType Leaf)) { throw 'FRESH_ROOT' }
if ((Get-FileHash -LiteralPath $state -Algorithm SHA256).Hash.ToLowerInvariant() -ne '3e2849e3af1a991264cce51113cb3319c9623ad34b65e16a320ad3e5972cc15d') { throw 'STATE_PIN' }
& 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_t4_run.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-t4-20261028-d5bd03a1adb80cd962fab37ae0bdb78b'
exit $LASTEXITCODE
