$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_t4_host.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne '88e220ebb342bba6889dc0934a3872b3bac3e29e3583c24f60d5503ad1d18c70') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_t4_run.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne '835c2e21b216e984028d14d684ad0380b348f0c3b45ea336f462469d4468defd') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_t4_prepare.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'c7892639f42ebb1eccbb39fc4c717e6649fb66cde96140ff9d94d4b3957d0727') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:/Users/w.filho/AppData/Local/Programs/Python/Python311/python.exe' -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'ff9b669828a66882f3d43ed2f9192ea9d8a08f80b8ffbc2186ee946823394418') { throw 'PIN' }
$root = 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-t4-20261028-86e5417cd7958015ace880173d138553'
$state = Join-Path $root 'attempt.json'
if (@(Get-ChildItem -LiteralPath $root -Force).Count -ne 1 -or -not (Test-Path -LiteralPath $state -PathType Leaf)) { throw 'FRESH_ROOT' }
if ((Get-FileHash -LiteralPath $state -Algorithm SHA256).Hash.ToLowerInvariant() -ne '2654800305d0159d005567d28016b66cb635e2f8566484369b9505dfce22373a') { throw 'STATE_PIN' }
& 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_t4_run.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-t4-20261028-86e5417cd7958015ace880173d138553'
exit $LASTEXITCODE
