# Fase 9 — Etapa 8 — B-2: plano por lotes de memória

**Estado (2026-10-19): B2-A autorizado e executado após revisão prévia do
Claude2. Diagnóstico de seis controles e 36 casos, evidência revisada
tecnicamente e registro aprovado pelo usuário em 2026-10-19; não é gate de contenção
aprovado. Execução dos demais lotes não autorizada. Depois, foi autorizada
somente a preparação documental de B2-B com o Claude2 (§8).
Autorização posterior limitada a B2-B1, núcleo lógico e testes isolados (§9).
Sem código de produção, commit/push ou SQL. A preparação histórica da §6
não executou testes.**

## 1. Autoridade, checkpoint e objetivo

Após aprovar a prova B-1 em outro processo, o usuário respondeu **"pode
seguir"** à proposta de **preparar** com o Claude2 o próximo lote para B-2,
ainda sem worker integrado ou SQL de cliente. Este documento não transforma
essa preparação em aprovação das escolhas ou execução dos lotes abaixo.
Houve depois autorização separada de B2-A, registrada na §7.

Checkpoint: `master`, HEAD `4a5e5560abb495898c9e1b8ca44ac2d155681015`,
referência local `origin/master` em
`5d173ea938eb12db33bc880bf67a2e81a208fd5e`, 1 ahead/0 behind; sem fetch.
Working tree preexistente preservado. Freeze da preparação: **438 arquivos**
em `src`, `tests`, `docs`, AGENTS/CLAUDE, dependências e `.venv/pyvenv.cfg`.

Objetivo do próximo lote sugerido, **B2-A**: investigar a divergência entre
limite de commit configurado e pico reportado no Windows, separando medida,
alocador e imposição dos limites. **Não** fechar B-2 ou escolher uma métrica
substituta. Nenhum número do experimento vira default de produto.

## 2. Fatos anteriores que não mudam

Fonte: [desenho aprovado, §§10.1–10.5](PHASE-9-STAGE-8-DESIGN.md) e relatório
histórico em `%LOCALAPPDATA%\Temp\maskgw-memctl-poc-0f47c4ec\REPORT.md`,
SHA-256 conferido nesta preparação:
`1effe36c8675f0ec83487144786131744288f7d5b5f223ce41125455f12c34f3`.

| Evidência histórica | Conclusão preservada |
|---|---|
| Cap agregado 402.653.184 bytes; pico 406.024.192 bytes | **FAIL** estrito, excedente de 3.371.008 bytes. Negação de uma alocação não torna o ensaio aprovado. |
| Job de 32 MiB: picos 33.697.792 e 36.872.192 bytes, passos de 1/4 MiB | Excedentes reproduzidos e leituras ctypes/pywin32 concordantes; causa não estabelecida. |
| `reserved_budget`, 96 MiB × quatro membros incluindo supervisor | Evidência parcial de reserva lógica; não é reserva física ou garantia universal, nem saturação simultânea das quatro cotas. |
| Proxy no pai: 8/16 MiB de frame → cerca de 49,6/96,9 MiB de crescimento | Não é o decoder real; bytes no pipe não orçam objetos, cópias e envio. |
| Cursor nomeado e célula gigante | Resultados parciais não certificam transações, proveniência, masking ou consumo do pai. |
| Criação suspensa seguida de `Assign` | Morte do launcher nessa janela não foi provada segura. Não se presume proteção pelo job do host. |

Não se atribui o excedente a arredondamento, tentativa de commit recusada,
allocator do Python, bug de Windows/binding ou contabilização após saída.
São hipóteses possíveis a distinguir, não conclusões medidas. Correlação
entre passo e excedente não estabelece causalidade.

## 3. Grandezas e regras de metrologia

`ProcessMemoryLimit`/`JobMemoryLimit` são limites de memória virtual
comprometida, e `PeakJobMemoryUsed` é um pico do job, não soma de picos
individuais. A definição não explica por si só o excedente observado.
[Microsoft — limites estendidos de Job Object](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information).

No processo, registrar `PrivateUsage` como commit atual e `PeakPagefileUsage`
como pico de commit de vida; `WorkingSetSize` é outra grandeza e não será
critério de contenção. [Microsoft — PROCESS_MEMORY_COUNTERS_EX](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex).

Regras propostas para o harness:

- Dados primários em **bytes inteiros**, com timestamps monotônicos,
  tamanho de página, granularidade e perfil de runtime/imagem identificados.
  MiB é apresentação, nunca unidade da asserção.
- Novo job por caso/repetição, com flags/cotas relidas e lista real de PIDs,
  identidade por handle e instante de criação. Não somar picos individuais
  como se fossem simultâneos, nem usar amostragem como limite rígido.
- Leitura por ctypes e pywin32 já instalado: conferir estruturas, flags,
  cotas e zero inicial em job vazio. Sob carga, chamadas sequenciais podem
  observar instantes diferentes: registrar os dois timestamps e valores.
  Comparar picos em marcos quiescentes reconhecidos pelo filho, com no
  máximo três pares de leituras; divergência persistente fica inconclusiva
  e interrompe novos casos, não é declarada automaticamente bug de binding.
- Marcos: job vazio; atribuição antes de retomar; baseline após imports;
  antes/depois de cada tentativa de alocação; retenção; liberação; saída.
  Registrar o momento de liberar a reserva de emergência e a fase de
  serialização para não confundir efeitos do relatório com a carga.
- Baseline, instrumentação e reserva de emergência **contam** no consumo.
  Não subtrair baseline, arredondar pico para baixo ou acrescentar tolerância
  à asserção histórica `pico <= limite`.

## 4. B2-A — diagnóstico temporário autorizado e medido

Resultados e limites em `PHASE-9-STAGE-8-B2-A-VALIDATION.md`; os critérios
predeclarados abaixo não foram relaxados para acomodar os resultados.

Somente Windows, CPython **3.11.3** já existente, stdlib/ctypes e pywin32
existente no controlador. Pasta temporária **nova**, fora do checkout e
distinta dos originais. Sem instalação, `.venv` nova, Docker, PostgreSQL,
rede nos probes, dados/chaves reais ou import de `maskgw`.

### 4.1. Pré-requisito de criação e ownership

Investigar `STARTUPINFOEX` com `PROC_THREAD_ATTRIBUTE_JOB_LIST`, opção pública
documentada para Windows 10/Server 2016 em diante. É **candidato**, não
mecanismo já implementado ou prova de segurança neste host.
[Microsoft — UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute).

Antes de qualquer carga:

1. Configurar e reler o job; spawn suspenso com a lista explícita de jobs;
   conferir associação ao job próprio **antes** de chamar `ResumeThread`.
   Configuração sem suporte, associação recusada ou flag divergente → recusa,
   sem fallback silencioso para `CreateProcess` seguido de `Assign`.
2. Definir no código temporário um guardião independente, iniciado antes do
   launcher, dono de handle do job e das inspeções de término. Só launcher
   e filho sintéticos próprios podem ser encerrados. O filho não herda
   handle do job: seu término não depende de ele fechar esse handle.
3. Exercitar morte do launcher antes de criar, após a criação suspensa e
   depois de retomar. O guardião deve conseguir fechar/terminar o job e
   comprovar o término de todos os membros. Ausência de um marcador no
   filho **não** prova ausência de execução nem ausência de processo.
4. Conferir herança de handles, kill-on-last-job-handle-close, identidades e
   ausência de breakaway. Um handle retido pelo guardião muda quando ocorre
   o último fechamento; esse protocolo precisa estar explícito e revisado
   antes da execução, não ser presumido a partir do nome da flag.

Fechar o último handle com `KILL_ON_JOB_CLOSE` termina os membros do job;
herança/breakaway e jobs aninhados afetam o conjunto protegido. Isso não é
prova de recolhimento sob falha persistente do SO.
[Microsoft — Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).

O probe de pressão tem **um único membro** no job. Guardião e launcher ficam
fora dele, mas constam no inventário: no máximo **três processos próprios
simultâneos**. Usar o interpretador base existente, identificado antes do
spawn, como no PoC histórico; não certificar por isso o redirector da `.venv`
ou o runtime do gateway. Qualquer membro adicional é recusa, não aumento
automático do limite de processos. Terminal, gateway e ferramentas nunca
entram em job restritivo. Restrições herdadas desconhecidas devem constar
como limitação; não forçar breakaway para contorná-las.

### 4.2. Matriz pequena e predeclarada

O usuário autorizou esta matriz, condicionada à revisão prévia do harness e
de seus controles de ownership pelo Claude2:

| Grupo | Casos | Objetivo |
|---|---|---|
| M0 | Job vazio/readback e controle de 4 MiB, sem pressão | Conferir binding, configuração, observação e caminho de término normal. |
| M1 | Só job em 32 MiB; limite individual desligado e conferido | Isolar esse perfil de configuração, sem atribuir causa apenas por erro genérico. |
| M2 | Só processo em 32 MiB; limite agregado desligado e conferido | Comparar o limite individual sem usar o pico de working set como substituto. |
| M3 | Ambos em 32 MiB | Controle separado; não confundir as duas cotas nem somar seus valores. |

M1–M3 têm **dois alocadores × dois passos × três repetições = 36 execuções**
sequenciais, sempre com job novo. Passos fixos de **1 e 4 MiB**; pedido de
payload de no máximo **40 MiB** por execução, mantido por até 1 s. Não há
tentativa ilimitada até esgotar o host.

- Alocador Python: `bytearray`, como controle do mecanismo anterior.
- Controle nativo: `VirtualAlloc`, com arena de endereço de no máximo
  64 MiB e commits disjuntos de no máximo 40 MiB ao todo. Registrar retorno
  e `GetLastError` numérico da chamada que falhar, sem relatar só um erro
  genérico do processo. Reservar endereço não é comprometer páginas, nem
  commit equivale a RAM física residente.
  [Microsoft — VirtualAlloc](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualalloc).

A reserva de emergência, se usada, terá **2 MiB**, pré-alocada e incluída no
baseline/cota, liberada somente numa fase identificada. Carga, baseline e
instrumentação permanecem separados no registro. Falha de alocação esperada
não dispensa observar o pico e comprovar cleanup; timeout ou crash não contam
como demonstração de imposição correta de cota.

**O ensaio agregado histórico de 384 MiB não faz parte de B2-A.** Sua eventual
repetição ou saturação de quatro membros exige outro lote. Também não há
reexecução de `reserved_budget` para substituir a reprovação original.

### 4.3. Salvaguardas e parada

- Antes de cada caso: pelo menos **2 GiB de memória física disponível e
  2 GiB de commit disponível**; abaixo disso, recusar sem carga.
  Monitorar durante a carga e solicitar interrupção se cruzar esse piso;
  a amostragem não garante contenção física do host.
- Até **15 s por caso** e **300 s para o lote**, sem renovar prazos nem
  acrescentar repetições até obter verde. Cleanup tem orçamento próprio de
  até 5 s por passada; não promete término absoluto se o SO falhar. Ao
  acabar o prazo global, casos restantes são **não executados**, não aprovados.
- Relatos escalares: até **64 KiB por caso**, amostras limitadas a 128 por
  caso e lote de evidência de até **4 MiB**. Sem dump de memória, captura de
  ambiente completo, credencial, resultado do banco ou saída ilimitada.
- Parar novas cargas por falha de ownership/cleanup, PID desconhecido,
  identidade não confirmável, configuração sem suporte, divergência de
  leitura persistente ou limite de evidência/prazo/preflight atingido.
  Retenção de dono/handles não pode ser confundida com liberação bem-sucedida.
- Excedente de pico é achado preservado, não aprovação da contenção; controles
  pequenos restantes só continuam dentro da matriz fixa se a segurança e a
  limpeza forem confirmadas. Nunca elevar teto para completar a matriz.
- Preservar originais e falhas. Remover somente recursos descartáveis próprios
  identificados; scripts/evidências novos ficam para auditoria. Se houver
  falha persistente de recolhimento, avisar e parar, sem matar por nome ou
  interferir em recursos de terceiros.

### 4.4. Saída e aceite do diagnóstico, não da contenção de produção

Cada caso separa: **execução completa/incompleta**, **observação do limite
respeitado/excedido** e **cleanup confirmado/incompleto**. Matriz incompleta
não vira gate verde. Conclusões admissíveis:

- excedente reproduzido, com sequência temporal e perfil identificados;
- excedente não reproduzido **apenas nos perfis medidos**, sem apagar o FAIL;
- evidência insuficiente/ambígua, declarada inconclusiva.

Padrão correlacionado ao passo não prova causa. Nem sucesso em algum perfil
certifica um teto universal, nem falha em todos prova que o contador é
inutilizável. Explicação causal exige mecanismo e controles que distingam
hipóteses rivais; trocar métrica ou contrato exige proposta e aprovação próprias.
O diagnóstico pode terminar honestamente inconclusivo; isso não autoriza código
de produto nem novas tentativas fora do escopo.

Entregáveis propostos após autorização: scripts temporários versionados por
hash, parâmetros fechados, evidência bruta com bytes/timestamps/PIDs/cotas,
matriz com todos os casos previstos e revisão somente leitura pelo Claude2.
O resultado ainda precisará ser apresentado ao usuário antes de qualquer
mudança operacional ou próximo lote.

## 5. Caminho posterior — não autorizado por este plano

1. **Contenção/admissão:** demonstrar cotas individuais/agregadas e ledger
   global atômico com shutdown, incluindo todos os membros, gerações/snapshots
   retidos e liberação única. `B + H + soma(W_i + P_i) <= M` continua sendo
   contabilidade, não prova de imposição do SO.
2. **Memória do pai:** fechar custo superior de buffers, objetos, expansão
   UTF-8, cópias e envio lento no decoder/encoder reais, ou propor outro
   domínio de contenção com ownership explícito. Não colocar silenciosamente
   o processo inteiro do gateway/MCP/Admin sob uma cota. Retornar estrutura
   ilimitada de outro processo também não resolve o pai.
3. **Fetch/pipeline:** cursor/transação/proveniência, `_settle` sem COMMIT,
   `max_rows + 1`, célula gigante e expansão pelo transformer, com memória
   do worker **e pai**, conexão por sessão e B-1 fim a fim comprovados.
4. **Integração e certificação:** somente em lotes aprovados, sobre produto
   real, com testes adversariais e pacotes/plataformas/runtimes reivindicados.

Nenhum item é substituto dos demais. Alterar o critério agregado, mudar a
arquitetura de memória do pai, trocar cursor ou mecanismo de spawn do produto
exige aprovação explícita; este documento só propõe investigá-los em etapas.

## 6. Revisão e estado histórico da preparação documental

Claude2 leu o desenho e evidência histórica em modo somente leitura e propôs
grupos diagnósticos. A proposta foi restringida a B2-A pequeno, sem a carga
agregada de 384 MiB, com controle nativo e critérios que **não** inferem
garantia universal ou invalidez do contador de uma varredura finita.
Enumerar membros novos não explica retroativamente os membros desconhecidos
antigos. A revisão final deste documento pelo Claude2 não apontou bloqueador
no escopo preparatório; não aprova as escolhas ou a execução do diagnóstico.

Nesta preparação não foram executados novos testes, pressão de memória,
PostgreSQL, Docker, suíte, pacotes ou browsers. Sem instalação ou alteração
funcional. As referências oficiais foram consultadas para conferir contratos
das APIs; não constituem medição deste host.

Conferência final contra o freeze de **438 arquivos desta preparação**:
cinco documentos existentes alterados e este plano adicionado; nenhum
arquivo removido. `src`, `tests`, dependências e `.venv/pyvenv.cfg` continuam
com os mesmos hashes. O relatório histórico também permaneceu idêntico.
`git diff --check`, UTF-8 estrito e whitespace dos seis documentos passaram.
O fechamento da revisão só ajustou este texto; não exigiu repetir suítes.

**B-1 fim a fim, B-2 e D-090 gate 2 permanecem abertos.** As aprovações dos
lotes B-1 não aprovam este plano. PGWire segue recusando SQL de cliente com
`0A000`; sem worker integrado, deploy, commit, push ou produção.

## 7. Autorização posterior de B2-A

Em 2026-10-19, depois da apresentação deste plano revisado, o usuário
respondeu **"sim"** à pergunta: criar o harness temporário e executar B2-A
**após revisão do Claude2**, sem commit/push. O aval vale só para §4, não
autoriza os lotes posteriores, produto, banco, worker integrado ou SQL.

Checkpoint reconfirmado: mesmos HEAD e referência local de origin/master;
freeze de **439 arquivos**, separado do freeze de 438 da preparação.
Harness novo em `%LOCALAPPDATA%\Temp\maskgw-b2a-20261019-311a869add584820b5298206798d3a6c\`.
Só revisão estática de sintaxe foi feita até o envio para revisão; nenhuma
criação de processo de teste ou pressão foi executada antes do parecer.
Os scripts antigos e o FAIL de 384 MiB permanecem intactos.

Execução final em 2026-10-19: seis controles e 36 casos completos, limpeza
confirmada. O pico excedeu o cap nos 12 job-only; os 24 com cota individual
ativa ficaram dentro dos caps apenas nos perfis medidos. Evidência revisada
tecnicamente: `PHASE-9-STAGE-8-B2-A-VALIDATION.md`, com o registro aprovado
pelo usuário em 2026-10-19. Isso não fecha B-2 nem autoriza produto, outros
lotes, commit/push ou alteração do critério estrito histórico.

## 8. Preparação posterior de B2-B

Após a aprovação do registro B2-A, o usuário respondeu **"pode"** à proposta
de preparar com o Claude2 o próximo lote de contenção e orçamento global de
memória, ainda sem implementação. A proposta está em
`PHASE-9-STAGE-8-B2-B-PLAN.md`: núcleo puro de reservas como menor lote
candidato, separado das provas de contenção do SO, custo real do pai,
fetch/pipeline e integração.

Essa preparação não aprova as escolhas do plano nem autoriza código, novo
harness, testes/pressão de memória, worker, banco/Docker ou SQL. Sem
commit/push ou produção. Nenhum resultado, critério ou parâmetro anterior
muda; B-1 fim a fim, B-2 e D-090 gate 2 permanecem abertos.

## 9. Autorização posterior de B2-B1

O usuário respondeu "sim" em 2026-10-19 à proposta revisada: implementar
somente o núcleo lógico de reservas e testes determinísticos, com revisão
pelo Claude2, sem workers, SQL, pressão ou commit/push. A autorização não
inclui integração nem os demais gates de B2-B.

O núcleo foi implementado localmente, sem chamador operacional. D-112 e
`PHASE-9-STAGE-8-B2-B1-VALIDATION.md`, revisados tecnicamente sem bloqueador
no núcleo isolado; fechamento e D-112 aprovados pelo usuário em 2026-10-20,
sem ampliar a autorização.
Não muda resultados, critérios ou parâmetros anteriores. Os créditos são
lógicos; B-1 fim a fim, B-2 e D-090 gate 2 permanecem abertos.
