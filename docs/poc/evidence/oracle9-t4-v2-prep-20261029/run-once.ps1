$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_t4_host.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne '88e220ebb342bba6889dc0934a3872b3bac3e29e3583c24f60d5503ad1d18c70') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_transport_profile_v2.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne '3a5bb9a3c6b38fcefb910fd498d01fc3a4fc9c04ae379d81dbc48b462f8c116a') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_t4_v2_run.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne '28b5601348fb7c8e95df9780b7f2424cb49ecf21306fffd3d2e39cb18d124538') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_t4_v2_prepare.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne '8e024cf4c24ddfe66fa1cc54f8fcf65d952f75cb65fde388403f823d97f41826') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_t4_v2_export.py' -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'aeade45d01106756489e8e1cbe2bfdd6758b5b3ee07b3e16dc246bda750f900a') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82') { throw 'PIN' }
if ((Get-FileHash -LiteralPath 'C:\Users\w.filho\AppData\Local\Programs\Python\Python311\python.exe' -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'ff9b669828a66882f3d43ed2f9192ea9d8a08f80b8ffbc2186ee946823394418') { throw 'PIN' }
$root = 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-t4-v2-20261029-de8e832ca4c67fd35f3647779adfaad0'
$state = Join-Path $root 'attempt.json'
if (@(Get-ChildItem -LiteralPath $root -Force).Count -ne 1 -or -not (Test-Path -LiteralPath $state -PathType Leaf)) { throw 'FRESH_ROOT' }
if ((Get-FileHash -LiteralPath $state -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'bec0accdf51e18e94fd66a14a2272d8b54464005ad40cc133b1bd4e068ac4116') { throw 'STATE_PIN' }
& 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\w1_bootstrap_t4_v2_run.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-t4-v2-20261029-de8e832ca4c67fd35f3647779adfaad0'
exit $LASTEXITCODE
