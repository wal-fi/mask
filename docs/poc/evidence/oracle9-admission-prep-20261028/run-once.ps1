$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_t4_host.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne '88e220ebb342bba6889dc0934a3872b3bac3e29e3583c24f60d5503ad1d18c70') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_admission_run.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne '7c11361734c9107448874c5cdc7fa1f14b5bbdc9899edca55e43ee9babd69c7a') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_admission_prepare.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne '1b0699878b578ca06a39e073fba8cd666fd14fe812c01fc82b6b61aa2eeda424') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_admission_fields.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne '9612a46b3a38ef1d96e90bf12d41975a3acde66209f88e38fdea04a95efec9e3') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_admission_export.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'beeb85d6b47b58a624d57f2fd185b6fbca404ea9bfe441f842ce8c84cd9c058f') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:/Users/w.filho/AppData/Local/Programs/Python/Python311/python.exe' -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'ff9b669828a66882f3d43ed2f9192ea9d8a08f80b8ffbc2186ee946823394418') { throw 'PIN' }
$root = 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-admission-20261028-2dd94bfb4502755ce8fa8cd496f637c8'
$state = Join-Path $root 'attempt.json'
if (@(Get-ChildItem -LiteralPath $root -Force).Count -ne 1 -or -not (Test-Path -LiteralPath $state -PathType Leaf)) { throw 'FRESH_ROOT' }
if ((Get-FileHash -LiteralPath $state -Algorithm SHA256).Hash.ToLowerInvariant() -ne '24d647a044e10cdb25fe42593ee1010587b658382c6634f279f3e7857031ae64') { throw 'STATE_PIN' }
& 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_admission_run.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-admission-20261028-2dd94bfb4502755ce8fa8cd496f637c8'
exit $LASTEXITCODE
