$ErrorActionPreference='Stop'
$taskChecks=@{
 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe'='bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82'
 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\oracle9_w1_run.py'='4bc0b083c9df44edd2aa532de7f43cf9f7f9f5a581edb267d8414d21057fd753'
 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\oracle9_w1_run_v2.py'='b59388f52a38319c19c2c60b25100347d319a59c2778395cc68bea64d2bc0c37'
 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-w1-run-v2-20261027-9eb3e1f3c8d144bba31f0b4240ed4d23\attempt.json'='a19394f906ec2645e49443f3f40beed92d48461dd52ff74a081eb8f69443a968'
}
foreach($taskCheck in $taskChecks.GetEnumerator()){
 if((Get-FileHash -LiteralPath $taskCheck.Key -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskCheck.Value){throw 'V2_PIN_CHANGED'}
}
$taskRoot='C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-w1-run-v2-20261027-9eb3e1f3c8d144bba31f0b4240ed4d23'
$taskEntries=@(Get-ChildItem -LiteralPath $taskRoot -Force)
if($taskEntries.Count -ne 1 -or $taskEntries[0].Name -ne 'attempt.json'){throw 'V2_NOT_FRESH'}
if(@(Get-Process -ErrorAction SilentlyContinue|Where-Object {$_.ProcessName -match '^(Docker Desktop|com\.docker\..*|docker.*|vpnkit)$'}).Count -ne 0){throw 'V2_DESKTOP_STATE_CHANGED'}
& 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\oracle9_w1_run_v2.py' $taskRoot
$taskV2Exit=$LASTEXITCODE
exit $taskV2Exit
