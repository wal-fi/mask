$ErrorActionPreference='Stop'
$taskChecks=@{
 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe'='bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82'
 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\oracle9_w1_run.py'='4bc0b083c9df44edd2aa532de7f43cf9f7f9f5a581edb267d8414d21057fd753'
 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\oracle9_w1_restore.py'='9d4fa8b9587221bb67ed7f402010317fce4173b2c78e52c15b38ccc1a7d07bfd'
 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-w1-restore-20261027-e7b054beeff149d68b39aff29e0771cc\state.json'='72f89bfd22195562c34ccba65b1bb6a52ddfd9f71ab45710cb929cf7d8564047'
}
foreach($taskCheck in $taskChecks.GetEnumerator()){
 if((Get-FileHash -LiteralPath $taskCheck.Key -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskCheck.Value){throw 'RESTORE_PIN_CHANGED'}
}
$taskRoot='C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-w1-restore-20261027-e7b054beeff149d68b39aff29e0771cc'
$taskEntries=@(Get-ChildItem -LiteralPath $taskRoot -Force)
if($taskEntries.Count -ne 1 -or $taskEntries[0].Name -ne 'state.json'){throw 'RESTORE_NOT_FRESH'}
& 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\oracle9_w1_restore.py' $taskRoot
$taskRestoreExit=$LASTEXITCODE
exit $taskRestoreExit
