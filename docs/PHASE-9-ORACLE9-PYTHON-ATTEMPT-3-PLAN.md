# Oracle9 Python — preparação com perfil do instalador

2026-10-23, decisão sob delegação, **ainda não executada**. As duas rodadas
anteriores permanecem NOT_PASSED em ORACLE9-PYTHON-VALIDATION. Segunda
registrou evento oom durante leitura de metadados, sob512MiB, sem imagem.

Escolha prospectiva para esta nova rodada, a revisar antes de A: **2GiB**
memory com MemorySwap igual (swap0), somente no container descartável de
instalação de RPMs públicos. Nenhum dado/config/segredo do cliente ou
produto entra nele. Não alterar RAM do daemon/Windows/WSL, nem D-119,
cota do worker, sonda128MiB ou outro gate. Não usar esse resultado como
passagem de B-2. Se falhar, parar e registrar; sem aumentar de novo ou
repetir automaticamente. Escolha evita trocar o fornecedor/runtime ou
desabilitar GPG/TLS para contornar o problema do gerenciador de pacotes.

Antes de create: MemTotal do daemon >=8GiB como condição básica de
elegibilidade (não é memória livre nem promessa contra OOM); ps global
vazio. Medição anterior16.689.958.912, revalidar nesta rodada. Memória é
aplicada e inspecionada antes do start, sem mudar container existente.
Demais limites/caps/rede/tempos permanecem iguais. Novo observer persiste
Running/ExitCode/OOMKilled do inspect próprio antes de cleanup, inclusive
na falha, evitando diagnóstico que dependa só de eventos retrospectivos.

Programa v4→v5 muda só perfil512MiB→2GiB/preflight MemTotal e observação
de State no cleanup. Payload inalterado, dois repos HTTPS com GPG/TLS1,
mesmos NEVRAs e todos os guards RPM/OS/diff/commit/Env/sonda.45 testes
puros passaram; testes recusam perfil antigo/divergente. Sem nova carga
real, segundo escritor ou alteração de produto. Controles iguais por
substituição de root/task. Raiz:
`C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-c66036a7`,
taskb4302d50b8774d68b09168839dba6f6a, unobserved/invokedfalse/sem phase.

Fontes/pins: `docs/poc/evidence/oracle9-python-procedure-v5-20261023.json`,
SHA256 `5c55f956fbbb93b9b61811dd22297e52cf938d50eeea6f2e75f17c64d5cf5a07`.
- start6db2d731f64e5df2058d0b5a5598d16cec34a5f9cdb97eb338ff2850ddd07d4e
- control6435d06cbef5fe005a37c9fd3d31c45df1a7f7ece5e9bea922aa69b067e02c09
- restore51f619a8d4abcaf61918ec484c19529c13bba553e7353ce0b13c724496f5fc28
- programa: `b0dd3458108821e8cdce26b8cb201aa7ef170e53648b283d7476cabc306b882f`
- payload1f738b2fb6561f6d478a41ce987df2464b95b25a61e1e0a0f56cd54998631563

Comandos separados, após conferência de pins e revisão, cada exit conferido:
```powershell
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-c66036a7\start_desktop.ps1'
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-c66036a7\state_control.ps1' Observe
# Observe mais duas vezes após cada terminal0, depois:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-c66036a7\state_control.ps1' Ready
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_python_prepare.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-c66036a7'
exit $LASTEXITCODE
# B terminal, cleanup/ps/identidade próprios confirmados, start próprio:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-c66036a7\state_control.ps1' AllowStop
& '.\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-c66036a7\restore_desktop.py'
exit $LASTEXITCODE
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-c66036a7\state_control.ps1' Off
```
Demais contratos ativos da v3/v4 permanecem: instalação300s/commit60s,
watchdog1200s, CLI2MiB, resumo expandido2MiB, perfil read-only/nonroot/
networknone128MiB na sonda, imagem falha em quarentena. Sem SQL, DB,
worker, imagem do produto ou anúncio de disponibilidade por essa rodada.

Revisão87482 terminal sem bloqueador antes de A. Incorporada recomendação
de diagnóstico condicional **somente leitura** nesta rodada: se B falhar,
após terminal e antes de restore, consultar events filtrado pelo CID próprio
registrado/validado (since do start próprio, until atual), e info MemTotal,
via mesmo CLI/contexto/pins e helper bounded; máximo64KiB/10s por consulta.
Persistir saídas/exits em arquivo novo no root próprio. Não criar/reiniciar
container, repetir B ou mudar recurso; falha do diagnóstico não vira nova
carga. Resultado passa pela revisão de evidência. Hash real do programa é
o valor de64 dígitos acima (começa b0dd, sem o a da palavra programa).
