$ErrorActionPreference='Stop'
$taskChecks=@{
 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe'='bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82'
 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\oracle9_w1_run.py'='4bc0b083c9df44edd2aa532de7f43cf9f7f9f5a581edb267d8414d21057fd753'
 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-w1-run-20261027-5cb698ceef7c4414a30d96e2667d0e58\attempt.json'='d43f3b2a62fa9f97979c96d3321184a3537b3732e6315956ba038bf02a707725'
}
foreach($taskCheck in $taskChecks.GetEnumerator()){
 if((Get-FileHash -LiteralPath $taskCheck.Key -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskCheck.Value){throw 'RUN_PIN_CHANGED'}
}
$taskRoot='C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-w1-run-20261027-5cb698ceef7c4414a30d96e2667d0e58'
$taskEntries=@(Get-ChildItem -LiteralPath $taskRoot -Force)
if($taskEntries.Count -ne 1 -or $taskEntries[0].Name -ne 'attempt.json'){throw 'RUN_NOT_FRESH'}
& 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\oracle9_w1_run.py' $taskRoot
$taskRunExit=$LASTEXITCODE
exit $taskRunExit
