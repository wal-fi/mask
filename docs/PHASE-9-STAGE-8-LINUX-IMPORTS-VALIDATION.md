# Etapa 8 — imports Linux: controle inconclusivo, AS32 não executado

**2026-10-21 — rodada única encerrada sem aprovar o perfil.**
Preparação: `PHASE-9-STAGE-8-LINUX-IMPORTS-PREPARATION.md`.
Plano: `PHASE-9-STAGE-8-LINUX-IMPORTS-PLAN.md`.
Nenhum worker, SQL, banco, ingress operacional ou plataforma foi liberado.

## Preparação e revisão antes da rodada

Wheel D-115 idêntico aos fontes atuais nos dois sentidos (115 arquivos).
Doze wheels Linux/pure e produto, hashes e metadados conferidos; árvore
parcial externa com656 arquivos/73.346.126 bytes, fechamento Linux/extras e
RECORDs aprovados. Não é instalação operacional MCP/HTTP ou pip-check.

Claude2 revisou somente leitura na sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`. Primeiro I1–I6 do plano; depois P1
do preparador (placement fora/acima do repo), corrigido/testado antes da
instalação. Na revisão do harness, R1/baseline e R2/orçamento do relatório
foram tratados antes de Docker. O revisor corrigiu a afirmação de que
exec_module inseriria _lab_support automaticamente em sys.modules; não foi
falha reproduzida, mas houve defesa explícita do baseline e de seus caminhos.

Inventário sem nomes duplicados, baseline separado dos deltas; até1.500
linhas/1MiB raw, zlib<=32KiB, decoder limitado, probe<=56KiB/wrapper<=64KiB.
1.500 linhas estruturadas cabem; alta entropia resulta inconclusiva, sem
truncar ou elevar cap. Prazo interno20s, externo30s/caso e120s/lote; fds
estritos por etapa, proc children opcional/inventário global obrigatório.

Gates antes da rodada: **110 testes puros** (28preparação+36probe+46anteriores),
Ruff/format em247 arquivos, mypy strict alvos3.11/3.14 em247 arquivos limpos.
O alvo3.14 é só estático. Os novos testes de supervisor inicialmente deram
5 falhas/105pass duas vezes por fakes incompletos de sys.flags/sys.version;
depois de corrigir só essas fixtures, 110pass. Não houve processo real nessas
simulações; a morte por sinal foi simulada, não injetada no SO.
Rerevisão não apontou bloqueador para uma rodada estreita, não aprovou gates.

## Ambiente e procedimento efetivamente usados

Host Windows/Python3.11.3 existente, .venv intacta. Desktop inicialmente
desligado e iniciado oculto, sem alterar daemon/WSL/Python. Disco livre
11,74GiB. Preflights limitados: Docker29.7.2/Linux, zero containers,
imagem já em cache com ID e digest exatos
`python@sha256:8a00ecb83ed9d0864dfd102a1bdb2067fda907ceb30bb86d09da9ee558b19590`.
Não houve novo pull. Container: Python3.11.17, glibc2.36, kernel
`6.18.54.1-microsoft-standard-WSL2`, UID65534, -I/-B/-S, dois mounts RO
exatos, rede none, root readonly, sem -e, caps removidas, pids16, CPU1,
192MiB/swap0, nofile64/core0, sem restart/init/healthcheck, log driver none.

Comando do observador, executado **uma vez**:

```powershell
.venv\Scripts\python.exe -I -B docs\poc\run_linux_imports.py --run <docker.exe absoluto> <raiz temporária preparada>
```

## Resultado preservado — não aprovado

- **Controle: inconclusive**, elapsed5,469s. Etapa0 (`maskgw.db.postgres`)
  tem start e end, com1 thread/fds[0,1,2] e proc_children_available=true.
- **Etapa1 (`maskgw.runtime.snapshot`): start, sem end.** Uma linha de módulo
  desta etapa foi coletada: `_cffi_backend`, de
  `/installed/_cffi_backend.cpython-311-x86_64-linux-gnu.so` (distribuição cffi).
  Pelo código, linhas de módulo são emitidas depois do retorno de
  import_module: o import de snapshot retornou; a interrupção foi ao auditar
  ou emitir a linha seguinte do delta. Isso **não** é aceite da etapa, pois
  faltam end/efeitos/verificação final, nem prova de falha de memória. Categoria original
  e returncode do membro não constam do relatório: causa ainda indeterminada.
- Etapa2 não iniciou. Nenhuma verificação final native_check/psycopg binary
  pode ser reivindicada como concluída, mesmo havendo módulos nativos na lista.
- **Caso AS32: não executado**, porque o controle não foi normal. Não houve
  repetição, aumento de limite, fallback ou relaxamento da origem/fds.
- Sumário complete=false, imports_fit_as32=false, total_memory_contained=false.
  Lote5,890s; sem deadline excedido. Ferramenta reportou saída não zero1 do
  PowerShell; o main Python tem contrato de retorno2 para não-fit. Não foi
  capturado separadamente o LASTEXITCODE do Python, portanto não se inventa
  medição independente desse código.

Após etapa0 (valores em bytes, métricas distintas):

| Métrica do membro | Valor |
|---|---:|
| VmPeak | 100.769.792 (96,102MiB de espaço virtual, **não RAM**) |
| VmSize | 97.206.272 |
| VmRSS | 59.273.216 |
| Threads | 1 |

Membro ready: VmSize19.292.160/VmPeak19.574.784; supervisor startup:
VmSize19.730.432/VmPeak20.373.504. AS efetivo [-1,-1] no controle.
Esses números parciais não calibram nova quota nem autorizam substituir32MiB.
Não há pico completo do pipeline/imports ou medição sob AS32.

Inventário coletado:429 linhas (77baseline,351etapa0,1etapa1,0etapa2),
29.177 bytes descomprimidos. Probe6.866 bytes/wrapper7.135 bytes, abaixo dos
caps; não há evidência de estouro do relatório nesta execução. Events cgroup
max/oom/oom_kill=0, State.OOMKilled=false; pico cgroup91.774.976 bytes,
sem exercitar limite externo192MiB. Inventário vivo[1,7], final[1]/pids1.

## Evidência, cleanup e revisão do registro

Originais preservados fora do checkout:
`%LOCALAPPDATA%\Temp\maskgw-linux-import-run-20261021-0xlyhzme`.
Raiz preparada anterior preservada também, sem executar launchers Windows.
Somente um container criado:
`6f1179e890add9796ffcc7c8d286d8e68d4dc8edc3144f1ac16bec2e4d5a0b84`.
Cleanup confirmado, removido por ID próprio; inventário do engine restaurado
vazio, reconferido antes do Desktop stop graciosamente (exit0). Depois:
zero processos Docker Desktop/backend/build e zero Python. Nenhum banco ou
container de terceiros foi tocado; nenhum recurso incerto foi liberado.

Fontes originais/cópias, árvore e runtime.json permaneceram iguais, segundo
observador/executor. SHA-256 dos originais:

- summary.json: `7dfd976571222ac1fb5904574fb4cc650f3c371d08d0a03597e4caa160a5dcee`;
- control.json: `27442025d71375dfbf5198f15e14fb84a853a2a3fa4df617620faa1ae2d15397`;
- probe: `0e735176d13e7dcbfd61161b1b2d3cb2c6dd0d4094362ba74b210f97786f6cfb`;
- observer: `4014082dd1abea2b083cd0f6f0a0c42c68b78b8873bfe99ded9a30ffcf31a24e`.

Bundle sintético para leitura do revisor no checkout:
`docs/poc/evidence/linux-imports-20261021.json`, com sumário, controle original
e inventário decodificado pelo executor. Não é segunda execução, e os hashes
originais não são atribuídos a cálculo do Claude2. Claude2 leu esse bundle
e conferiu o registro sem divergência ou alegação acima do medido; não
executou nada ou certificou B-2. O ramo que recusa linha fora do protocolo
(inclusive collection_failed) não persiste o evento nem faz wait com
returncode no resultado; essa lacuna explica como se perde o diagnóstico,
sem provar qual linha excepcional foi recebida. Nenhuma correção do harness
posterior à execução foi aplicada ainda.

## Próximo passo e gates ainda abertos

Revisar a lacuna de observabilidade da auditoria: ela precisa identificar,
com categoria e nome de módulo limitados, onde parou, sem texto de exceção ou
valores sensíveis. Só depois propor correção e novo lote revisado, preservando
esta rodada inconclusiva; não repetir este perfil até verde nem abrir o caso
AS32 sem controle válido. Não há causa atribuída a CFFI/Rust/AS por suposição.

Produto/dependências e evidência AS anterior intactos; sem suíte integral
PG16 nova, frontend/browsers, pacotes operacionais ou runtime moderno nesta
medição. Efeitos são amostras, não prova de inexistência de efeitos transitórios.
B-1 fim a fim, B-2, D-090 gate2 e produção continuam abertos. Sem commit/push.

## Auditoria final do incremento

317 caminhos no baseline anterior,327 selecionados no fechamento: seis
documentos existentes atualizados e dez arquivos novos (três scripts,
dois testes, quatro documentos e bundle sintético). Nenhum arquivo de
produto/src mudou, nenhum selecionado ficou ausente; fontes do diagnóstico
AS anterior permaneceram idênticas. `.venv/pyvenv.cfg` preservado com hash
`6e2514351382cfae93b50d0e64644884d45febbf6dbc6ed97bcf3cab6536ff82`.
Gates finais repetidos:110 passed, Ruff/format/mypy nos dois alvos verdes
em247 arquivos, diff check limpo e UTF-8 estrito nos arquivos do incremento.
Bundle comparado semanticamente aos originais e ao inventário decodificado;
as cinco fontes originais/cópias executadas conferidas por hash pelo executor.
Nenhuma suíte PG16 integral foi reivindicada ou repetida. Git continua no
checkpoint descrito na preparação; sem fetch, commit ou push, e arquivos
pessoais anteriores preservados. Próximo incremento está apenas preparado
em `PHASE-9-STAGE-8-LINUX-IMPORTS-OBSERVABILITY.md`, sem implementação nova
após esta execução.
