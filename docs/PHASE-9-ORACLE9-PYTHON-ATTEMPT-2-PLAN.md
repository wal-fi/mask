# Oracle9 Python — nova tentativa corrigida

2026-10-23, sob delegação. Anterior2cb63b66 consumida/NOT_PASSED, log
comprova rejeição de flag global microdnf, cleanup e Desktop off confirmados.
Registro em ORACLE9-PYTHON-VALIDATION; nunca reescrever como sucesso.

Delta único do programa host v3→v4: retirar os setopts globais não aceitos
gpgcheck/sslverify. **Verificações permanecem habilitadas nos dois blocos
repo HTTPS**, gpgcheck1/sslverify1/enabled1, reposdir exclusivo, chave local
vendor, sem --nogpgcheck/fallback/chave remota. O teste agora parseia a
configuração real gerada e exige as duas seções, flags, baseURLs e chave.
Não é desligamento de GPG/TLS nem redução de garantia. Documentação vendor:
https://linux.oracle.com/security/gpg/ e
https://docs.oracle.com/en/operating-systems/oracle-linux/software-management/sfw-SecuringOLPkgDistribution.html.

Payload, capsALL drop, limites, command/setopts restantes, ownership,
NEVRAs, OS/RPM/diff/config/commit/sonda e cleanup não mudaram.44 testes,
Ruff/format/mypy do teste aprovados. Não há ação real nesse attempt.
Não aumentar prazo/cota nem repetir automaticamente em caso de falha.

Raiz nova:
`C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-bb4fc0ab`;
taskfb1112bdf7eb41bfb9ebd7cbd04f7632, unobserved/invokedfalse, sem phase.
Fonte/pins exatos: `docs/poc/evidence/oracle9-python-procedure-v4-20261023.json`,
SHA256 `980a99982eee51fc1b969f67e7c293d486d6db26c0a87463407e26b602bb919d`.
- start142ac32aee647a13919a043de20994148a81714c8bbf7b2305118dd2450da878
- control03ce8c63ab2c49dc44e3b0bab0f49273575053c462ce70fc882a59607f4e2f37
- restore51f619a8d4abcaf61918ec484c19529c13bba553e7353ce0b13c724496f5fc28
- programa2466097f18bb681a83a849e6bb34241dc99601f6e71c128cf834d4d325505c03
- payload1f738b2fb6561f6d478a41ce987df2464b95b25a61e1e0a0f56cd54998631563

Mesma sequência, agora só na raiz nova e após conferência de todos os pins,
cada comando separado com exit conferido:
```powershell
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-bb4fc0ab\start_desktop.ps1'
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-bb4fc0ab\state_control.ps1' Observe
# Observe mais duas vezes, só depois de cada terminal0, depois:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-bb4fc0ab\state_control.ps1' Ready
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_python_prepare.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-bb4fc0ab'
exit $LASTEXITCODE
# Somente B terminal, cleanup/inventário/identidade confirmados, start próprio:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-bb4fc0ab\state_control.ps1' AllowStop
& '.\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-bb4fc0ab\restore_desktop.py'
exit $LASTEXITCODE
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-bb4fc0ab\state_control.ps1' Off
```
Exits pertencem a chamadas separadas; não executar de uma vez.420s da v1
é histórico; watchdog1200s prospectivo da v3 permanece. Demais detalhes
ativos v3 de ORACLE9-PYTHON-PLAN se mantêm. Imagem intermediária local
só após todos os guards; uma falha pós-commit a deixa em quarentena.
Sem produto, DB, worker, SQL, deploy ou disponibilidade por esse resultado.
