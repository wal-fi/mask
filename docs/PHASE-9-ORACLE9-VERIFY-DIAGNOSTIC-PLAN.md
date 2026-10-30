# Oracle9 — diagnóstico limitado da divergência RPM (v10)

2026-10-23 local, sob delegação. Quinta tentativa preservada NOT_PASSED;
consulta completa executou sem stderr mas comparação recusou. Desktop off,
nenhuma imagem ou gateway disponível. Não inventar que divergência é benigna.

Delta do probe: `compare_verification` mantém **igualdade exata** da lista
normalizada, incluindo multiplicidade. Antes de recusar, imprime contagens,
hashes integrais e até40 linhas adicionadas/removidas,512 caracteres por
linha. Somente metadados públicos de RPM no builder sem cliente/segredo,
máximo de saída pequeno sob CLI2MiB. Persiste verify-after.txt na própria
camada; sem publicação se falhar. Nenhuma exceção nova, skip, limite ou
permissão alterada. Testes provam recusa ainda presente e duplicados não
descartados. Ownership restante usa nomes canônicos também; filtro do
par nome/arch instalado continua exato, não aceita outro pacote.64 testes
puros e Ruff/format/mypy dos dois testes passaram; não são evidência Linux.

Fresh root
`C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-90167519`,
task4a3d43d0405e4b0d803747f7e9127ec0. Nova cópia local byte a byte dos
mesmos nove RPMs originais, sem download; probe diagnóstico novo, origem
original5d28e938.../task2fb1281f/manifest21c51656 intacta. Check_bundle e
comparação real dos nove dicionários com origem passaram antes de preparo.
State downloadfalse/originverified-copy/readytrue/invokedfalse/unobserved,
sem phase. Nunca repetir D ou qualquer attempt consumido.

Manifesto novo `648090c897870f90470985a11b3061908041f8704d6a410c4e738fb4072cc73b`.
Fontes/pins em `docs/poc/evidence/oracle9-python-procedure-v10-20261023.json`,
SHA256 `fc3f586802f834dcc04ea94e2c620f5092267a99e07bc132637b9d98b63b0351`.
- start: `6b6bb9e73f5d963cc014c20cc7d4931dc6f00c0963e150d58750422a4e10f195`
- control: `f4b7ae825f6e45991e19d63baced39faca5c7dbce210b5715c0f943ac5a9f72b`
- restore: `51f619a8d4abcaf61918ec484c19529c13bba553e7353ce0b13c724496f5fc28`
- host: `e70d38792218346b647ca9b8572099fb808d30e14c115f4058f82deea30510b5`
- payload: `abdc5cca1bbcc2db271d8a3eca06efb4459df82b7769707de9ada382515f27f4`
- biblioteca: `5471e1f61fb6f782055c3695746a2786f223bdf88112e3fe7edf3b42fed8c896`

Após revisão, pins e exits, chamadas separadas, uma vez, sem D:
```powershell
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-90167519\start_desktop.ps1'
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-90167519\state_control.ps1' Observe
# Mais duas Observe após cada terminal0, depois:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-90167519\state_control.ps1' Ready
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_python_prepare.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-90167519'
exit $LASTEXITCODE
# B terminal/cleanup/ps/identidade confirmados, start próprio:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-90167519\state_control.ps1' AllowStop
& '.\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-90167519\restore_desktop.py'
exit $LASTEXITCODE
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-90167519\state_control.ps1' Off
```
Mesmos caps7 só builder/networknone2GiB, prazos, commit guards e sonda
128MiB/nonroot/RO/capdropALL. Resultado elegível só se TODOS os guards
passarem; diagnóstico não relaxa commit, produção ou C1. Falha aborta,
sem replay/override/cota/prazo ampliados. Diagnóstico de eventos próprio
somente leitura já declarado continua disponível; restore sob ownership.
Sem produto, SQL, banco, worker, B-1/B-2/D-090 fechados, commit/push/deploy.
