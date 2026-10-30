# Oracle9 — verificação completa RPM, v9 ativa (v8 não executada)

2026-10-23 local, sob delegação; **nenhuma ação Docker nova**. Quarta
tentativa reprovada preservada em PYTHON-VALIDATION e attempt4. Python e
venv instalados não bastam: nenhuma imagem foi commitada.

## Consulta e diagnóstico, sem flexibilizar o gate

Usar `rpm -Va` depois da instalação, mesmo modo da baseline anterior, e
comparar todas as divergências com ela (mesmas três exceções declaradas e
conferidas separadamente). Isso verifica todos os pacotes, incluindo os
novos, sem depender de lookup nome.arquitetura. Adicionalmente, verificar
os nove RPMs novos por nomes canônicos, exigindo saída vazia. Antes/depois
NEVRA, OS, owner/hash, privilégios e todos os outros guards continuam.
Não declarar que isso prova a causa anterior: seu stderr não foi guardado.

Wrapper ainda recusa **qualquer** stderr ou rc fora0/1 (verify) ou0 (query).
Só na falha, imprime operação/rc/hash/tamanho e prefixo máximo4096bytes do
stderr **público RPM dentro do instalador sem dados/segredos/projeto**.
Serve ao diagnóstico desse laboratório; não é logging do gateway ou
permissão de imprimir erro de banco/cliente. Teto externo2MiB mantido.
Regressão confirma que warning/erro continua recusado.61 testes puros,
Ruff/format e mypy dos dois testes passaram, sem nova carga real.

## Input novo, sem inventar outro download

Root próprio novo
`C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-963040fd`,
task94d91ee3a6d3455288b26b5cbc1932c5. Nove RPMs copiados byte a byte do
bundle original conferido, com hashes iguais antes/depois; original intacto.
Somente probe público novo e manifesto/auxiliares regenerados. Nenhuma
rede ou RPM executado no host por esse preparo. Fonte D original v6 e
evidência5d28e938... preservadas. Estado diz a verdade: download_invoked
**false**, origin verified-local-copy-v1, origem task/manifest/evidência
fixadas; bundle_readytrue, invokedfalse/unobserved/sem phase. B exige a
cópia e confere a evidência original pinada, não forja uma execução D.
Downloader também recusa bundle já pronto antes de rede/consumo.

Manifesto novo
`b4c362d3b7f5ad9020c787bf6cdef1fd4fa43b47139b579a956ab70d4a7d5f24`;
manifesto original21c51656... e RPMs não mudaram. Input/helper privado de
construção não registra nenhum perfil C1 pronto ou libera SQL.

Fonte/pins integrais:
`docs/poc/evidence/oracle9-python-procedure-v8-20261023.json`, SHA256
`8b6f0765a6df3bc4eb2fdd141b76473caa76d090dc9c21c8baaeb309f77c1b38`.
- start: `bbc90f080c1444b7f0bed04b568b48d1a7e7ec7072562046f58aa0016ec0c8d4`
- control: `e28b7215789809805a13086d192018c051c7ec1eda231ac68e3333b917b89c46`
- restore: `51f619a8d4abcaf61918ec484c19529c13bba553e7353ce0b13c724496f5fc28`
- host: `d43960a4a5326099c581589764469737202bc605b9a03e0213141a6bf2a96043`
- payload: `6983c70ffe42485ce971eb17907edf85ff30c28c03582485c929a0d6489fc5d1`
- biblioteca download: `5471e1f61fb6f782055c3695746a2786f223bdf88112e3fe7edf3b42fed8c896`

Após revisão e pins, chamadas separadas com exit conferido, **sem D**:
```powershell
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-963040fd\start_desktop.ps1'
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-963040fd\state_control.ps1' Observe
# Mais duas Observe após cada terminal0, depois:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-963040fd\state_control.ps1' Ready
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_python_prepare.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-963040fd'
exit $LASTEXITCODE
# B terminal/cleanup/ps/identidade próprios confirmados:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-963040fd\state_control.ps1' AllowStop
& '.\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-963040fd\restore_desktop.py'
exit $LASTEXITCODE
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-963040fd\state_control.ps1' Off
```
Mesmos caps7 só builder sem rede,2GiB/swap0, tempos e limites; sonda
128MiB/nonroot/RO/capdropALL. Diagnóstico somente leitura próprio em falha
continua; sem alterar gates, ampliar prazo/cota, override, replay ou force.
Qualquer falha aborta e imagem falha fica em quarentena. Sem produto, DB,
worker, SQL, commit/push/deploy ou disponibilidade por esse resultado.

## P1 da revisão60982, fechado antes de A

O B passa a decodificar os bytes exatos do manifesto de origem da evidência
pinada, conferir seu SHA e comparar **cada dicionário completo** dos nove
RPMs novos com a origem (filename/url/header/bytes/sha256), excluindo só o
probe público que mudou. Não basta referenciar a evidência. Teste recusa
troca de RPM mantendo header, tamanho/URL diferentes e origem alterada;
probe novo é permitido. Checagem real na cópia preparada também passou.
62 testes puros, Ruff/format/mypy dos testes aprovados. V8 nunca executada.

Ativo: `docs/poc/evidence/oracle9-python-procedure-v9-20261023.json`,
SHA256 `213d93a455bacb044b42fef800ce7e498923dd168008a38748891edf927e6d38`.
Host `e70d38792218346b647ca9b8572099fb808d30e14c115f4058f82deea30510b5`;
demais fontes/pins/root/task/manifesto e comandos inalterados. Estado
unobserved/invokedfalse/sem phase alinhado ao host novo, sem novo download
nem mutação de RPM ou bundle preparado. Nunca usar o pin d439 histórico.
