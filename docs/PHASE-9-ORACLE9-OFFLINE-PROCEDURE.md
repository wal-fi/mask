# Oracle9 — procedimento offline: D v6 consumido; A/B/C v7 pendentes

Estágio D v6 passou uma vez; não repetir. Evidência em
ORACLE9-RPM-DOWNLOAD-VALIDATION. Para A/B/C usar **pins v7** nessa evidência
e JSONv7, após revisão do manifesto. Os pins/comandos v6 abaixo preservam
o procedimento anterior a D, não autorizam executar o host8d205 antigo.

2026-10-23. Três falhas preservadas, Desktop off. Desenho em
ORACLE9-RPM-BUNDLE-PLAN, com B1 fechado por log RPM normal `-ivh` em vez
de -vv por arquivo. Não houve download de RPM, novo start ou imagem.

Fontes completas e scripts exatos em
`docs/poc/evidence/oracle9-python-procedure-v6-20261023.json`, SHA256
`e3b9c4674c260baf19361c684574c380aeed91293394cd871929e125e0a84b0e`.
Root novo `C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-499ec65a`,
task2fb1281fc0094e6f9ec10a9204e883b0. Estado unobserved/invokedfalse,
bundle_download_invokedfalse/bundle_readyfalse. Não usar attempts antigos.

Pins:
- start: `1dd304b5c777472c3ae4623d473242d6a64eff382e157da0a2696bf18904f23f`
- control: `7bcaa37b26ca8d0c8c9503545e56b094cbbfa6afe8bf7195a391c6f0f8918f3e`
- restore: `51f619a8d4abcaf61918ec484c19529c13bba553e7353ce0b13c724496f5fc28`
- host: `8d205eba90827fa71500f2e594daed4040955a92056baba841462fa367194342`
- payload: `32a1a972548fb35160e5c9bbe5d85117a478c03ebd4ca77bebf2a5cc87f688df`
- download: `7b610a37e44d75d2268ada50a27ebc041c77431e27663ceae03f4854113a2a27`
- curl.exe8.21.0: `73d24149ff289afc49ec41f08918ef9faa727d39ad993e929757dc2ddafab805`

## Estágio D: download público, antes de Docker

Após revisão do código/comando, uma vez, com hashes conferidos:
```powershell
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_rpm_download.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-499ec65a'
exit $LASTEXITCODE
```
Admissão exige source hashes e estado, marca consumo antes da rede. Nove
URLs literais, max-time30/connect10/limite16MiB ou saldo64MiB, supervisão
35s do curl nativo, sem proxy/curlrc/redirect/auth/client-cert automático.
TLS normal do Windows; status200/URL exata, magic RPM, arquivos exclusivos,
fsync e manifesto. Nenhum RPM executa no host. Falha aborta sem retry ou
start do Desktop, preserva parcial e resultado NOT_PASSED/último arquivo e
exit disponível, sem categoria fina de causa. Falha de IO anterior ao try
pode deixar só estado consumido, sem download.json; isso não permite replay.

Só D terminal0/BUNDLE_DOWNLOADED permite conferir/revisar o manifesto e
hashes gerados antes de A. Bundle plano contém nove RPMs, probe próprio e
três arquivos de manifesto/header/hash; nada do checkout/.venv/frontend/
config/chaves. Todos os nomes e bytes conferidos, zero symlink/reparse/
junction ou extra. Manifesto protegido por hash no estado. Isso é prova
de transporte, assinatura só será conferida no Linux.

## Estágio A/B/C, só após revisão do bundle gerado

```powershell
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-499ec65a\start_desktop.ps1'
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-499ec65a\state_control.ps1' Observe
# Mais duas Observe após cada terminal0, depois:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-499ec65a\state_control.ps1' Ready
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_python_prepare.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-499ec65a'
exit $LASTEXITCODE
# Só após B terminal/cleanup/ps/identidade, start próprio:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-499ec65a\state_control.ps1' AllowStop
& '.\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-499ec65a\restore_desktop.py'
exit $LASTEXITCODE
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-499ec65a\state_control.ps1' Off
```
Cada chamada separada/pins/exits conferidos, não um script cego. A recusa
bundle não pronto. B reconfere manifesto/arquivos antes de consumo e cp;
container parado/perfil validado, cp só para seu CID:/opt/maskgw e novo
inspect antes de start. Bash fixo da base, rede none; caps7 só builder,
2GiB/swap0, MemTotal>=8GiB não é headroom livre. Sonda128MiB/nonroot/
read-only/capdropALL segue. Sem autoridade de host ou produção ampliada.

Dentro: sha256sum completo; chave vendor local permitida; `_pkgverify_level
all` na verificação/query/test/instalação, signatures OK sem NOKEY/NOT OK;
keyID RSAHEADER permitido e nove headers exatos. FILEMODES sem6000,
FILECAPS opcional deve ser vazio/(none), sem arrays de tamanhos diferentes.
rpm --test -i e rpm -ivh uma vez. Depois RPMs/base/OS invariantes, real
stat/xattr dos novos arquivos sem bits especiais ou security.capability;
remove somente nove RPMs conferidos, guarda manifesto e inventários.
Commit só após todos os guards/diff; imagem e probe validadas pelo hash.

59 testes puros, Ruff/format e mypy dos dois testes passaram. Não provam
download real, RPMs autênticos, instalação, Linux completo ou gateway.
Sem ampliação automática/override/replay. Qualquer falha aborta; diagnóstico
condicional events próprio/info read-only com limites já declarados;
quarentena se houver imagem reprovada. Sem SQL, DB, worker, D-119 pronto,
B-1/B-2/D-090 fechados, commit/push/deploy ou disponibilidade.

Revisão15171 terminal: D aceito uma vez após pins, A/B/C ainda dependem
do manifesto real. Notas de compatibilidade /bin/bash, /opt e documentação
ficam para essa revisão. Teste de sintaxe Git Bash não executado porque
esse executável não foi encontrado no caminho consultado; não é gate Linux.
