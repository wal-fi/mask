# Chamador nativo da sonda de admissão — desenho antes de código

Data: 2026-11-01, America/Sao_Paulo. Sob delegação vigente. Desenho do
chamador, ainda não implementado. O núcleo Win32 privado e seus testes com
fakes foram implementados no incremento descrito ao final; nenhuma raiz,
claim, comando ou execução nativa neste lote. Sonda
congelada 738ee1e3, preparador 8d0bf39e, entrada afaffad0, exportador
ed491c01 e raízes consumidas ficam intactos. Admissão de 3 s continua
NOT_MEASURED; este desenho não a mede, não limita memória e não fecha
C1/B1/B2/D090 nem libera produção.

## Desvio registrado

Em 2026-11-01T15:32:13.035Z, durante a elaboração da primeira versão deste
desenho, o programador fez um Grep em `.venv/pyvenv.cfg`. Foi leitura fora
do escopo autorizado, de configuração de runtime, não de fonte aceita do
repositório. Não é aprovada retroativamente; seu conteúdo não é repetido nem
usado como evidência. A versão anterior deste texto afirmava que nenhum
arquivo de configuração tinha sido lido; essa afirmação estava errada e foi
removida. O comportamento do launcher (iniciar ou não um interpretador base
como filho) continua **não provado** e será estabelecido só pelo controle
nativo da seção "Gate de controle nativo".

## O problema que o chamador precisa resolver

`.venv/Scripts/python.exe` (pin bfff5171) é um launcher de venv. É plausível,
mas não provado aqui, que ele inicie o interpretador base como processo filho.
Por isso matar e coletar só o processo criado diretamente não prova que todo
o trabalho parou. Os helpers existentes não cobrem a árvore:

- `run_linux_as_probe.bounded` (58c6) espera e mata só o processo direto.
- `w1_bootstrap_identity` (dc24) mata um único processo por PID+FILETIME via
  PowerShell; não cobre filhos e criaria outro processo.
- O padrão Job Object do B2-B2 (`b2b2_controls.py` 41c80c10, com helpers
  privados `native.py`/`winjob.py` fora do repositório) usava atribuição
  depois da criação suspensa e outro contrato; não é reutilizável como fonte
  aceita e tem a janela descrita em P1 abaixo.

Conclusão: módulo ctypes novo e mínimo, revisado, com fakes, e um gate de
controle nativo benigno antes de qualquer raiz de sonda.

## Escopo do chamador proposto: `docs/poc/pg16_shell_admission_host.py`

API pública: `run(root, task)` e `__main__` com exatamente esses dois
argumentos. Nenhum parâmetro de executável, argv, ambiente, módulo, callback,
diretório de saída ou deadline. Constantes fechadas, limites iniciais fixos e
**não medidos**, que não mudam depois de uma execução:

- Executável: `REPO/.venv/Scripts/python.exe`, SHA bfff5171 conferido com
  leitura limitada imediatamente antes da criação. Não troca para o
  interpretador base nem para outro Python.
- argv literal: `(launcher, "-I", "-B", REPO/docs/poc/pg16_shell_admission_probe.py,
  root, task)`; sonda conferida por SHA 738ee1e3 antes; linha de comando
  medida com `list2cmdline`, teto 2048.
- Ambiente explícito sem herança: `SystemRoot`, `WINDIR`, `TEMP`, `TMP`,
  `USERPROFILE`, `LOCALAPPDATA`, `APPDATA`, `HOMEDRIVE`, `HOMEPATH`,
  `SystemDrive`, copiados do chamador; nada de `PATH`, `PYTHON*`, `DOCKER*`,
  `MASKGW*`, tokens ou variáveis livres. Valores nunca impressos ou
  persistidos; só a lista fixa de nomes.
- `ActiveProcessLimit = 2`, `DEADLINE_SECONDS = 60`, `CLEANUP_SECONDS = 10`,
  stdout retido no máximo 1024 bytes. O limite de 3 s continua classificação
  retrospectiva da sonda, não prazo do chamador.

## Contenção da árvore (corrige P1)

Referências primárias Microsoft:
[UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute),
[JOBOBJECT_BASIC_LIMIT_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information),
[PeekNamedPipe](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-peeknamedpipe).

1. Job anônimo (`CreateJobObjectW`, handle **não herdável** e nunca passado
   ao filho) com `KILL_ON_JOB_CLOSE`, `ActiveProcessLimit=2`, sem
   `BREAKAWAY_OK`/`SILENT_BREAKAWAY_OK`; configuração relida com
   `QueryInformationJobObject` antes de criar o processo.
2. Handles do filho: NUL para stdin, NUL para stderr e a ponta de escrita de
   um pipe anônimo para stdout, os três herdáveis; a ponta de leitura não.
3. `STARTUPINFOEX` com lista de atributos contendo exatamente:
   `PROC_THREAD_ATTRIBUTE_JOB_LIST` = [job] (documentado a partir do Windows
   10) e `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` = [NUL de stdin, NUL de stderr,
   escrita do stdout]. `CreateProcessW` com
   `EXTENDED_STARTUPINFO_PRESENT | CREATE_SUSPENDED | CREATE_NO_WINDOW |
   CREATE_UNICODE_ENVIRONMENT` e `STARTF_USESTDHANDLES` no startup e
   `bInheritHandles=TRUE` restrito pela lista. O processo nasce **já membro**
   do job: não existe janela entre criação e atribuição, e a queda do
   chamador nesse instante encerra o processo pelo `KILL_ON_JOB_CLOSE`.
4. Logo após `CreateProcessW`: o chamador fecha suas cópias dos dois NUL e da
   ponta de escrita do stdout, para que o EOF dependa só da árvore.
5. Verificação antes de retomar: `IsProcessInJob(processo, job)` verdadeiro,
   configuração do job relida igual, contas do job com `ActiveProcesses == 1`.
   Só então `ResumeThread` com retorno 1.
6. Sem fallback com atribuição posterior. Se o atributo de job não estiver
   disponível ou falhar, nada é criado e o desfecho é `LAUNCH_FAILED`.
7. Se existir um processo próprio que não seja membro do job (verificação
   do passo 5 falha), ele é encerrado pelo **handle** devolvido por
   `CreateProcessW` (`TerminateProcess` + `WaitForSingleObject`), nunca só por
   PID nem apenas por `TerminateJobObject` de um job vazio. Desfecho
   `LAUNCH_FAILED`, ou `HELD` se o término não for comprovado.

## Supervisor de uma thread só (corrige P2)

Nenhuma thread nova de leitura bloqueante. Um único laço no chamador, com
turnos curtos (espera de no máximo 50 ms no handle do launcher por turno):

- `PeekNamedPipe` na ponta de leitura informa bytes disponíveis; `ReadFile`
  lê só `min(disponível, 4096)` por turno, sem iniciar uma leitura sem dados.
  Isso não elimina as limitações gerais de chamadas síncronas do SO.
- Se o launcher já estiver sinalizado, mas a árvore/EOF ainda não terminaram,
  deve haver pausa cooperativa entre turnos, sem laço ocupado no handle sinalizado.
- Retenção de no máximo 1024 bytes. Ao passar disso: marca de estouro,
  `TerminateJobObject` e desfecho `OUTPUT_OVERFLOW`; os bytes seguintes são
  lidos e descartados até o EOF, sem crescer a memória.
- EOF é observado quando `PeekNamedPipe`/`ReadFile` informam pipe quebrado
  (todas as cópias da escrita fechadas).
- Prazo de decisão: ao atingir `DEADLINE_SECONDS` sem as três condições
  abaixo, `TerminateJobObject` e desfecho `DEADLINE`, nunca sucesso.
- Aceite da supervisão só com as três condições juntas: EOF do stdout, conta
  do job com `ActiveProcesses == 0` e lista de PIDs vazia, e handle do
  launcher sinalizado com `GetExitCodeProcess` lido. `TotalProcesses` é
  registrado e deve ficar em {1, 2}; fora disso, `TREE_UNPROVEN`.
- Depois de terminate (por estouro, prazo ou falha), o laço continua até
  `CLEANUP_SECONDS` esperando as mesmas três condições.

Limite honesto: o prazo é um orçamento de decisão verificado entre chamadas.
Chamadas síncronas do SO (`CreateProcessW`, `ReadFile` de arquivo, `fsync`,
rename, `TerminateJobObject`, `CloseHandle`) podem travar sem limite; nada
neste desenho garante um prazo absoluto de parede, e um chamador travado
depende de intervenção externa. O fechamento do job pelo SO cobre a queda
do chamador, não seu travamento.

## Política HELD

`HELD` significa: há recurso próprio cuja liberação não foi comprovada.

- Entra em HELD: terminate do job ou do processo falhou; espera não chegou às
  três condições em `CLEANUP_SECONDS`; contas/lista do job não puderam ser
  lidas; `CloseHandle` falhou; leitor não chegou ao EOF.
- Em HELD o chamador não declara recursos liberados, não fecha o handle do
  job nem do processo sobre recursos não comprovados (exceto pela queda do
  próprio processo), não grava desfecho aceito, não publica evidência pública
  e não permite próxima tentativa: o nonce e a proposta ficam consumidos.
- Grava `supervision.json` privado com `HELD` e a categoria fechada da
  falha, se a gravação for possível; sai com código não zero.
- A retenção explícita vale enquanto o chamador está vivo. Se seu CLI sair,
  o SO fecha seus handles e aplica a política do job; isso não é prova de
  limpeza concluída. O responsável externo deve tratar a tentativa como
  pendente de recuperação, sem lançar outra tentativa ou declará-la liberada.
- Separação explícita: o orçamento de decisão (60 s + 10 s) é finito e
  verificado; não existe limite universal de tempo para a limpeza pelo SO,
  e o desenho não promete um.

## Ordem e artefatos

Duas áreas distintas, mesmo nonce para ligação:

- Privada: `Temp/maskgw-pg16-shell-admission-caller-v1-<nonce>/`, com
  ancestrais reais sem link/reparse, criada com `mkdir` exclusivo.
- Pública: `docs/poc/evidence/pg16-shell-admission-<nonce12>/`, criada só
  depois da projeção validada.

Sequência:

1. Runtime do chamador (Windows, 3.11.3, `-I -B`, optimize 0); fontes da
   sonda/preparador/entrada e do próprio chamador por SHA, leitura limitada.
2. Raiz/task: forma exata da sonda; raiz já materializada pelo preparador
   congelado, só com `attempt.json`; claim, resultado e diretório privado
   ausentes. Qualquer ocupante significa consumido: recusa sem tocar.
3. `invocation.json` privado com `xb`/contagem/flush/fsync/releitura **antes**
   de criar o job: task, nonce, root_name, SHAs, argv canônico sem ambiente,
   limites fixos. Falha aqui: nada é lançado e a proposta fica queimada.
4. Launcher pinado relido; job; criação já no job; verificação; resume.
5. Supervisor de uma thread (seção anterior).
6. `supervision.json` privado (xb/fsync/releitura): exit code, contas do
   job, flags de prazo/estouro/terminate/HELD, segundos de parede;
   `local-stdout.bin` privado com os bytes retidos.
7. Projeção: stdout parseado só como uma linha JSON do schema fechado do CLI
   da sonda; resultado final da sonda lido com limite de 4096 bytes, JSON
   canônico sem NaN, schema exato, task/nonce/root_name/SHAs iguais,
   `claim_sha256` igual ao hash do claim, marca ligada ao mesmo claim,
   desfecho do stdout igual ao do resultado e exit code coerente (0 só com
   WITHIN_3S; 1 para outros desfechos; 2 interrupção).
8. Pública: `summary.json` (escalares projetados) e `transport.json`
   (hashes/tamanhos dos brutos privados, nunca os bytes) com `.next` +
   releitura. O transporte vincula o hash/tamanho do resumo e é a única
   marca de conclusão. Resumo sem transporte final não é laudo completo.
   Todos os bytes/checks são preparados antes; o rename final do transporte
   é a última operação de filesystem. Falha anterior deixa lote parcial,
   nunca um laudo aceito, sem remoção ou retry.

Desfechos: `ACCEPTED_WITHIN_3S`, `ACCEPTED_OVER_3S`, `ACCEPTED_STAGE_FAILED`,
`ACCEPTED_CLOCK_INVALID` (resultado íntegro e árvore comprovadamente
encerrada), e `NOT_ACCEPTED` com categoria fechada (`DEADLINE`,
`LAUNCH_FAILED`, `TREE_UNPROVEN`, `OUTPUT_OVERFLOW`, `OUTPUT_MISMATCH`,
`RESULT_MISSING`, `RESULT_MISMATCH`, `PERSISTENCE`, `INTERRUPTED`, `HELD`).
Exit 0 só para `ACCEPTED_WITHIN_3S` publicado. Uma amostra, sem retry,
remoção ou sobrescrita; diretório parcial significa consumido.

## O que pode e o que não pode ser provado

- Pode: que todo processo criado na árvore terminou, pelas contas do próprio
  job em que o launcher nasceu; que sonda e launcher eram os arquivos pinados
  no instante da leitura; que o resultado publicado é o gravado pela sonda e
  ligado ao claim/marca.
- Não pode: prazo absoluto para chamadas síncronas do SO; pinar o
  interpretador base nem a stdlib inteira (a entrada só checa versão/flags e
  os seis arquivos de `C.STDLIB_PINS`); limitar memória; impedir adulteração
  pelo mesmo usuário; provar durabilidade de entrada de diretório após falta
  de energia.
- Janela da sonda: queda entre claim e marca deixa raiz FRESH; o chamador
  trata qualquer claim/raiz/diretório existente como consumido.

## Gate de controle nativo (escolhido sob delegação)

Antes de qualquer raiz de sonda, um controle nativo benigno separado, com o
**mesmo** módulo de contenção e o **mesmo** launcher fixo, argv fixo sem
importar a sonda nem nada do repositório (por exemplo `-I -B -c` com código
literal constante), sem configuração real, banco, SQL, Docker ou rede:

1. Saída normal: filho imprime uma linha fixa e sai 0; exige EOF, job com
   zero ativos, lista vazia, `TotalProcesses` registrado (estabelece se o
   launcher cria filho) e exit code repassado.
2. Término forçado: filho dorme além de um prazo curto fixo; exige
   `TerminateJobObject`, as três condições e desfecho de prazo.
3. Fechamento do último handle do job: um chamador de controle fecha o job
   sem terminate; exige que a árvore desapareça (verificado por handle de
   processo próprio retido e sinalizado), sem PID-only.

O controle tem raiz/nonce próprios, nunca é confundido com sonda, e exige
procedimento, comando e revisão próprios antes de executar. Falha em qualquer
caso bloqueia a sonda.

## Contrato de testes com fakes (lote seguinte)

Camada nativa atrás de uma interface interna única, substituída por fake;
nenhum processo, job, handle ou thread real nos testes.

- Ordem: invocação → job relido → atributos JOB_LIST+HANDLE_LIST exatos →
  criação suspensa no job → fechamento das cópias do filho → verificação →
  resume → supervisão → supervisão gravada → projeção → pública.
- Lançamento: atributo indisponível, falha em cada passo antes do resume,
  processo fora do job encerrado por handle, terminate por handle falho → HELD;
  handle do job herdável recusado; lista de handles diferente recusada.
- Supervisor: leituras só do disponível, chunk máximo, estouro de 1024 com
  terminate, EOF sem job zero, job zero sem EOF, launcher não sinalizado,
  `TotalProcesses` 0 ou >2, prazo e limpeza esgotados.
- HELD: cada falha de terminate/close/wait/conta mantém handles abertos,
  não publica, não libera nonce e sai não zero.
- Saída/resultado/persistência/entradas: como na versão anterior (estouro,
  linha extra, JSON inválido, desfechos divergentes, resultado ausente/grande/
  não canônico/SHA divergente, escrita curta/fsync/releitura em cada artefato,
  ocupantes prévios, pins e runtime, ambiente sem herança, AST sem
  `shell=True`, `os.system`, Docker, prepare/run/drive, nenhuma `Thread`).

## Sequência futura, cada passo com revisão própria

1. Revisão deste desenho.
2. Código e fakes do módulo de contenção e do chamador.
   Primeiro, módulo privado `pg16_shell_admission_win32.py` e seus testes,
   sem consumidor/CLI operacional nem carga de DLL ou criação de handle/job/
   processo real.
   Após revisão e gates desse núcleo, o chamador usa o SHA aceito do módulo.
3. Procedimento, comando e execução única do controle nativo benigno.
4. Proposta da sonda: task/nonce exclusivos, raiz materializada pelo
   preparador congelado, comando literal (PowerShell 5.1, ambiente Process
   filtrado, `$global:LASTEXITCODE`), sem execução.
5. Uma única execução nativa da sonda; laudo só com árvore comprovadamente
   encerrada, artefatos relidos e conferência externa somente leitura.

## Escolhas em aberto

1. Se o launcher real não criar filho, `TotalProcesses=1` é aceito e
   registrado pelo controle; se criar mais de um, o limite 2 faz a criação
   falhar visivelmente.
2. Pinar o executável base exigiria ler um binário real numa proposta
   futura; fica como limitação declarada.
3. Os limites 60/10/1024/2 são iniciais e não medidos.

## Notas de implementação — núcleo Win32 privado (primeiro incremento)

2026-11-01, America/Sao_Paulo. Só `docs/poc/pg16_shell_admission_win32.py` e
`tests/test_pg16_shell_admission_win32.py`. Sem chamador, controle nativo,
raiz, proposta, comando ou execução. Testes NÃO executados pelo programador.

- Sem consumidor, CLI ou `__main__`; importa só stdlib (`ctypes`, `dataclasses`,
  `ntpath`, `sys`). Import e `Owner(request)` não carregam DLL nem criam
  handle. `setup()` valida `Request`, runtime (win32, 3.11.3, x64 por
  `sys.maxsize`, `-I`, `-B`, optimize 0) e ABI x64 (tamanhos/offsets fixos)
  antes de `ctypes.WinDLL("kernel32")` com assinaturas explícitas.
- `Request` é dado interno (aplicação e diretório absolutos com drive,
  linha de comando ≤2048, ambiente tupla fechada ≤16 nomes únicos sem `=`);
  o chamador futuro fixa os valores. Nenhum callback ou módulo.
- Ledger: somente handles confirmados por sucesso coerente entram no ledger.
  Saídas de chamadas que falharam ou foram interrompidas, valores inválidos,
  repetidos ou com alias de handle próprio ficam em quarentena, sem operações
  de terminate/wait/close sobre eles. Handle próprio só sai após `CloseHandle`
  bem-sucedido; nenhuma saída indeterminada é tratada como propriedade.
- Job: anônimo, não herdável (conferido por `GetHandleInformation`),
  `KILL_ON_JOB_CLOSE | ACTIVE_PROCESS` com limite 2, sem breakaway, relido.
  Stdio: NUL leitura/escrita e escrita do pipe herdáveis; leitura do pipe não.
- Criação: lista de atributos dimensionada (≤4096 bytes) e mantida viva até
  depois de `CreateProcessW`; `JOB_LIST`=[job], `HANDLE_LIST`=[stdin,
  stdout_write, stderr]; flags `EXTENDED_STARTUPINFO_PRESENT |
  CREATE_SUSPENDED | CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT`,
  `STARTF_USESTDHANDLES`. Sem atribuição posterior.
- Depois da criação: apaga a lista, fecha as cópias do pai, confirma
  `IsProcessInJob`, configuração, contas (1,1) e lista exatamente [pid];
  `ResumeThread` deve devolver 1.
- Abort antes do resume: membro comprovado → `TerminateJobObject`; não
  comprovado → `TerminateProcess` pelo handle (filho suspenso não pode ter
  criado netos); depois espera 5000 ms e, no job, contas com zero ativos.
  Sem prova → HELD. Falha ao fechar cópia do pai ou apagar a lista → abort e
  HELD.
- Primitivas de supervisão (só em RUNNING): `wait(0..50)`, `exit_code()` só
  depois de sinalizado, `accounting()`/`members()` limitados a 2,
  `check_config()`, `terminate()`, `available()` via `PeekNamedPipe` e
  `read()` só do disponível até 4096. EOF (pipe quebrado) é separado de
  processo sinalizado e de job zerado.
- `close()`: sem processo, fecha tudo; com processo, exige sinalizado, zero
  ativos e lista vazia, depois fecha cópias restantes do pai e exige EOF;
  ordem thread, processo, leitura, job. Falha → HELD com ledger retido.
- HELD recusa todas as operações seguintes. Falhas de API tratadas são
  `Win32Error` com código fechado, sem mensagem estrangeira; falhas comuns
  inesperadas de setup/start são sanitizadas fora do except. Interrupções de
  controle são repropagadas depois de registrar HELD. Retenção
  vale só enquanto o processo dono vive; não há limite universal de tempo do
  SO, nem limite de memória.

### Correção após revisão independente (bloqueio do 24b717e5/a07944a2)

Rodada do revisor: 87 passed/1 failed (fixture AST tratava símbolos de
ImportFrom como módulos) e cinco contraprovas do hook independente, todas
falhando no código anterior. Registro do revisor, não execução do programador.

- P1-A: `CreatePipe` FALSE com saídas 0x9001/0x9002 era adotado e fechado.
  Agora saídas de chamada que falhou, levantou ou devolveu valor inválido/
  repetido/alias de handle próprio vão para `quarantine`, nunca para o ledger,
  e nunca são passadas a terminate/wait/close (documentação Microsoft:
  saídas de `CreatePipe` em falha são indeterminadas). FALSE limpo →
  SETUP_FAILED; exceção ou sucesso incoerente → HELD.
- P1-B: `CreateProcessW` FALSE com handles alheios levava a
  `TerminateProcess(0x9001)`. Agora só sucesso com dois handles válidos,
  distintos, sem alias e PID>0 é adotado. FALSE limpo: saídas em quarentena;
  contas do job (0,0) e lista vazia → LAUNCH_FAILED; senão terminate do job
  próprio e HELD. Exceção ou sucesso incoerente: terminate do job (JOB_LIST
  atômico) e HELD. Sucesso válido fora do job mantém término direto pelo
  handle próprio.
- P2-C/P2-D: `setup`/`start` passam por `_guarded`. `Win32Error` segue;
  outra exceção comum (ex.: MemoryError de alocação) vira HELD
  `WIN32_INTERNAL`, sanitizado fora de except, com saídas pendentes em
  quarentena, tentativa de apagar a lista de atributos e, se a criação já foi
  tentada, terminate do job. Interrupção (`BaseException`): saídas pendentes
  em quarentena, HELD `WIN32_INTERRUPTED`, um terminate do job se a criação
  foi tentada, e a interrupção original é repropagada. Nenhum estado normal
  ou liberado sobre ambiguidade.
- Lista de atributos: o registro só é limpo depois de deleção confirmada.
- P2-E: lista de PIDs exige retorno com cabeçalho + count×ponteiro ≤ tamanho,
  além da coerência de contagens; quadro curto é HELD, nunca lista vazia.
- Testes: fixture AST corrigida, leitura de `eof` por `observed()` sem
  ignores, quebras de linha pedidas; regressões para os cinco casos, alias em
  retorno falso e verdadeiro, exceção estrangeira hostil, interrupção no setup
  e no start, falhas de alocação e quadros de membros curtos.

Limites restantes: o terminate de contenção na interrupção é uma tentativa
única cujo resultado não é provado (o owner fica HELD de qualquer forma);
uma segunda interrupção durante essa tentativa propaga; a quarentena não é
liberada por este módulo e fica como pendência de recuperação externa.

Faltam (não implementados, sem consumidor): o chamador `run(root, task)`, o
laço de supervisão com retenção de 1024 bytes/prazos 60+10 s, a persistência,
o controle nativo benigno e qualquer prova nativa. A correção do ABI e dos
`argtypes` reais só é verificada pela futura execução do controle; os fakes
conferem tamanhos/offsets, ordem, flags, listas e ciclo de vida.

Gateway, B1/B2/D090/C1/SQL e produção seguem abertos.
