# W1 — primeira prova privada com PostgreSQL16, proposta antes do código

2026-10-28, sob delegação. Candidata621cc7f7/atestaçãof0c3cd54 aceita como
insumo fixo. Não reinstalar, copiar checkout, executar main de rodada consumida
ou liberar SQL de cliente. A direção e os contratos T1–T6/P1–P5/R1 foram
aceitos pelo Claude2; código, sonda T4, fixture PG e comando real têm revisão
própria antes de uso. A aceitação de desenho não é medição nativa.

## Resultado delimitado

Exercitar WorkerSession real e o filho instalado, em um controller PID1,
contra PG16 próprio: guard→INIT→conexão TLS/SCRAM→S1→masking/encoder→D114/
DONE→envio de resultado mascarado→close/reap/créditos. Sem ingressos PGWire,
MCP/Admin, registro operacional ou cliente externo. Não fecha B-1 inteiro,
B-2, D-090 ou C1 por inferência. Casos de carga/pressão/namespace/cliente lento
continuam lotes próprios após esta primeira prova.

Imagem PG proposta, por ID histórico a readmitir no próximo preflight:
`sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685`.
O artefato worker-errors-pg-run-20261023 registrou PG16.15 nessa imagem;
versão real será medida novamente. Sem pull ou instalar pacote no host/imagem.
Libpq18 do cliente contra servidor16 será combinação efetivamente testada.

## Topologia e perfis

Uma rede Docker bridge **interna**, task/labels/ID próprios, sem portas no host,
sem rede externa ou acesso a DB existente. Inventário inicial/final e intents
atômicos para rede/CIDs; não apagar rede/volume/preexistente por suposição.

- PGfixture: imagem por ID, UID/GIDpostgres70 a confirmar por perfil público
  antes de consumir seed; root RO/caps0/NNP/seccomp;512MiB/swap0/pids256/CPU1,
  core0/nofile128; PGDATA128MiB e tmp16MiB em tmpfs0700 do UID70. Sem bind
  mount/volume persistente, saúde/restart ou log-driver com armazenamento.
  PG16 Alpine/UID70 é expectativa, não fato novo; divergência aborta antes
  de DB/seed, sem afrouxar o perfil. Mounts inesperados ficam identificados
  e registrados, sem limpeza genérica ou falsa restauração.
- Controller: candidata621cc7f7 por ID e atestação, UID/GID10001, PID1/thread
  principal, root RO/caps0/NNP/seccomp/CPU1/pids32/512MiB/swap0/core0/nofile128,
  tmp16MiB0700, única rede interna. Guard controladorAS384MiB antes de secrets;
  filho usa guardAS256MiB/PPID1/PDEATHSIG9 com os APIs W1 existentes.
  São limites de ensaio fixos, não adequação C1 ou total de toda a máquina.

IP upstream vem do inspect do CID/rede próprios. `hostaddr` é esse IP fixado;
`host` é o alias .invalid único do certificado. Nenhum segundo DNS. TLS
verify-full, sem fallback. CA/leaf/key gerados para o lote; CA privada só na
memória do host e nunca enviada ao PG/controller. Leaf privada só no seed
privado do PG e em tmpfs0700/arquivo0600. Certificados públicos podem ter
SHA/bytes na evidência. Nenhuma chave privada em argv/env/estado/artefato.

## Pré-requisito menor: bootstrap privado supervisionado

Antes de qualquer Docker/carga, implementar e revisar um canal **específico
do ensaio**, com fakes; depois uma sonda pequena Windows de transporte, se
necessária e revisada. Não transformar D-107 em executor genérico nem mudar
produto/verificador existente. A primitiva pública histórica tem stdinDEVNULL
e não pode ser reutilizada como se já transportasse segredo.

O canal gerencia exclusivamente `docker start --attach --interactive` dos
CIDs já identificados/perfilados deste lote, com fonte pública/argv fixos.
Owner registrado antes do Popen, ambiente Windows público fechado. Processo
CLI, tarefas de pump e CID têm ownership explícito. Sem shell no host,
communicate síncrono, thread writer bloqueada ou segredo em linha de comando.

Primeira linha de stdout≤512bytes é READY fechado por papel/task/PID/UID e
hash de fonte esperados. Não autentica produtor malicioso: a confiança é no
CID/imagem/fonte/FD privados admitidos. Somente após READY aprovado o host
envia **um** seed≤16KiB pelo stdin privado, com prazo absoluto cobrindo envio,
recepção e execução; fecha stdin após frame completo. Sem progresso/erro que
contenha seed, seu hash, senha, HMAC, nonce secreto, PEM privado ou conninfo.

stdout é incremental e limitado≤32KiB, stderr descartado. O bootstrap PG
mantém seu CLI attach supervisionado até parar o CID; não declarar CLI limpo
porque o banco ficou ready. Controller termina naturalmente após a matriz.
Cleanup R1 em ordem: quiesce/reap do CLI e pipes/pumps, ticket; depois parar/
remover o CID próprio, confirmar ausência ligada ao ticket e liberar o canal.
Isso substitui a proposta inicial de observar CID parado antes de reap do
CLI, vulnerável ao start tardio. Falha retém ownership/pendência. Watchdog
independente só age nos CIDs identificados, nunca por nome parcial.

Matrix do transporte antes de uso: READY ausente/errado/fragmentado, nada
escrito antes dele, filho que nunca lê stdin com16KiB, stdout infinito,
EOF/saída após erro de I/O, spawn tardio/falha de tarefa, prazo em cada fase,
close/kill/wait transitórios/persistentes, fechamento dos pipes e ausência
de tarefa/processo órfão. Segredo-canário aleatório só em memória; artefatos
relatam categorias/contagens/ownership, sem conteúdo ou digest dele.

## Bootstrap do PG, depois do pré-requisito

Wrapper público no PG começa verificando UID70, tmpfs/donos/modos e perfil,
emite READY e só então lê seed privado limitado: senhas aleatórias separadas
do superuser/reader, leaf/key/CA públicos-privados apropriados. Sem segredo
em ENV, POSTGRES_PASSWORD no estado Docker ou arquivo persistente do host.

initdb UTF8/localeC/localtrust no socket privado/hostSCRAM, usando pwfile0600
em tmpfs, removido depois. Servidor temporário apenas Unix para semear;
papel reader com SELECT estrito e default_transaction_read_onlyon. Senha
reader só por stdin local do psql, nunca -v/argv/env; caracteres gerados
hex permitem SQL de configuração fechado. SQL de seed revisado; logs sem
statement/erro contendo texto (stderr descartado e log_min_error_statement
restrito). O fixture não é superfície DBA do produto.

O wrapper para o servidor temporário e faz exec do PG final como PID1, TLSon,
cert/key em tmpfs e HBA recusando hostnossl, SCRAM para hostssl. Nenhum trust
TCP ou liberação temporária na rede. Readiness é observação finita, sem
retry de criação/escrita/start. Parâmetros/SQL/limites exatos serão fechados
com o código antes de executar; não inventar binário openssl na imagem PG.
PKI é gerada pelo cryptography já instalado no host, somente em memória.

## Controller e matriz inicial

Python-I-B no pacote instalado, sem PYTHONPATH/Node/checkout. Fonte de ensaio
pública hashada, separada do produto. Aplica guard, importa APIs instalados,
emite READY; só depois lê seed privado (reader password, HMAC efêmero, CA
pública e hostaddr/identidades). Gera snapshot pelo loader/captura existentes,
sem duplicar parser/masking nem reler env; mesmos bytes por stdin do W1 após
GUARD_READY. Privados não aparecem em repr/erro/stdout/evidência.

Matriz a concretizar em código/fakes antes da rodada:
1. abrir worker real, sessão S1 e TLS verify-full/SCRAM; versão PG16 medida;
2. dados integralmente fictícios, MASK/HMAC/exception/derived pelo pipeline
   original; OIDs pós-masking e frame D113 validado/recebido pelo D114;
3. duas consultas sequenciais na mesma sessão, PID upstream único conferido
   por oráculo fechado do fixture, sem conexão/decoder bruto no parent;
4. erro recuperável com saúde/S1 válidos seguido de consulta correta;
5. novo worker com senha/CA incorretas: sem OPENED/resultado, recolhimento;
6. close, processo encerrado, FDs fechados e créditos liberados só após prova.

Resultados para socketpair local de teste por RawChannel/send_result_to, nunca
resultset bruto de worker ou endpoint externo. O parent do ensaio só compara
valores esperados já mascarados; oráculos HMAC/fixture conhecidos não viram
nova engine de produto. Presença de original proibido em qualquer saída
gera recusa. Consultas/seed/dados exatos serão apresentados antes da carga.

Ledger é usado de verdade para ownership/pin/release, mas seus custos de
fixture são declarados, sem fingir medição/cota física. AS virtual e RSS/
cgroup são grandezas distintas; eventuais medidas de pico alimentam desenho
posterior, não qualificam B-2/C1 automaticamente. Não aumentar AS/memória
durante a rodada se não couber.

## Coordenador e encerramento

Reutilizar ciclo fresco/journal12/replay/posse separada da aceitação revisados,
com programa/estado/raiz novos. Nenhum main consumido é repetido. Recursos
de rede/PG/controller e CLIs de bootstrap têm intents e confirmação próprios;
remoção reversa por ID/labels/perfil de posse, sem force/prune. Globalvazio
antes de stop do Desktop próprio, mesmo boot/PID/FILETIME e ausência observada.
Matriz, deadlines, hashes, comando único e perfil exatos passam por revisão
antes de A. Falha aborta e registra, sem relaxamento de segurança ou retry.

Este desenho não executa nem instala nada. Nenhuma dependência nova, listener,
serviço, alteração de dados existentes ou produção. Próximo incremento
proposto é **apenas o transporte privado com fakes**, após revisão do plano.

## T1–T6 incorporados antes do código do transporte

Claude2 aceitou a direção e o incremento mínimo, condicionados a T1–T4.
Escolhas concretas sob delegação:

- T1: seed autod delimitado, sem depender de EOF do attach. Cabeçalho ASCII
  fixo16bytes: magic/version8bytes `MGSEED01`, papel1byte P/C, comprimento
  decimal de6dígitos e LF. Corpo1..16384bytes, seguido de trailer8bytes
  `SEEDEND\n`. Leitura exata com prazo; recusar frame parcial, header/trailer
  incorretos e sobra já recebida/visível. Não afirmar ausência eterna de
  bytes futuros. Host só envia um frame e fecha stdin depois; leitor não
  aguarda EOF. A exceção é só o bootstrap Docker: stdin interno do W1
  continua com seu frame/EOF obrigatório inalterado.
- `create -i`, TTYfalse, OpenStdintrue/StdinOncefalse são o contrato proposto,
  a conferir no inspect e na sonda T4. Não presumir que foram medidos.
- T2: **escolhido argv público**, sem fonte no stdin e sem docker cp em RO/
  tmpfs. Controller usa bootstrap Python-I-B que verifica SHA do código
  descomprimido antes de compile; PG usa shell público com base64/sha256sum
  admitidos no preflight, confere SHA antes de interpretar o wrapper público
  no tmpfs. Não executar binário do tmpfs noexec. Nada privado no argv.
  Medir create inteiro com list2cmdline,≤26000; excesso aborta antes de A.
- T3: validador novo por papel, com OpenStdin/StdinOnce exatos e demais
  limites/identidades; não editar validate_container histórico que exige
  stdin fechado. Posse continua independente de aceitação.
- T4: sonda nativa de attach/pipe com **canário público fixo é obrigatória**
  depois de código/fakes revisados e antes de qualquer segredo. Mede READY,
  frame/trailer/sobra, stdin/EOF, saída limitada, morte do CLI com CID ainda
  vivo, cleanup completo e Proactor Windows. Tem fonte/ciclo/raiz/comando
  próprios revisados antes de A. Fakes não substituem essa sonda.
- API do canal é fechada aos papéis P/C e a um CID admitido: start,
  await_ready, send_seed, drain/status, retain, quiesce e close. Comando é sempre
  CLI pinada +--contextdesktop-linux+start --attach --interactive CID;
  nenhum comando/flag/backend arbitrário fornecido pelo usuário.
- Envio só em READY válido e uma vez; owner existe antes de spawn. READY
  exige task/source/UID/papel/PID1 do registro admitido; não autentica TCB
  malicioso. Ambiente Windows público, stderrDEVNULL, stdout incremental
 32KiB (sem devolver stdout cru em erro), primeira linha512bytes.
- Prazo proposto para spawn+READY+envio:12s absoluto desde antes do spawn;
  PGsetup60s e attachPG retido até quiesce (lifetime300s de lote);
  controller120s. Nenhum deadline renovado por chunk. Reap/fechamento têm
  orçamento separado3s; sem promessa absoluta para syscall que não retorna.
  Spawn tardio não recebe seed; spawn/pipe/kill incertos mantêm HELD/owner.
  O chamador deve conservar o owner/loop para collect, nunca abandonar
  tarefas vivas ou declarar capacidade livre só porque um await expirou.
- IO/spawn/reader/writer com falha não pode aproveitar prefixo de sucesso.
  Cancelar/aguardar pumps e confirmar término/handles; matar CLI não prova
  CID parado. CID permanece como ownership externo até inspect/stop/reap
  próprio. Transporta bytes privados mas só emite categorias/metadata;
  __repr__/exceções/artefatos não contêm seed ou seu hash.

T5: bytes transitam na memória do docker.exe/engine/shim e Python; não há
promessa de zeroização ou proteção contra administrador local. Sem log-driver,
sem salvar input/inspect com secrets. T6 será fechado no lote PG: socket Unix
em tmpfs70, shared_buffers/DSM/shm dimensionados e versão/UID medidos por
perfil público; ausência de cf78 local aborta sem pull. Não antecipar código
PG/controller/SQL ou segredos na implementação de transporte com fakes.

Fechamento T1–T6 aceito pelo Claude2 antes do código. P1–P5 incorporados:
corpo≤16384 e frame≤16408bytes,6dígitos ASCII exatos com zeros à esquerda;
trailer no corpo não delimita nada. Acima de32KiB, sticky STDOUT_LIMIT mas
pump continua drenando/descartando até EOF ou parada do CID pelo coordenador;
não bloquear PID1 deixando pipe sem leitor. READY conta LF no teto512 e
tem linha ASCII canônica/chaves exatas esperadas pelo papel/task/source/UID/PID.
Saída posterior não prova sucesso; é privada até parser fechado do fixture.

Implementação escolhida: subprocesso/pipes asyncio no host Windows, com pumps
registrados e deadlines absolutos. Fechar stdin é close+wait_closed dentro
de3s; matar/reap do CLI não prova CID parado. Quiesce encerra os pumps e
emite ticket somente após recolhimento confirmado; release exige confirmação
tipada de ausência posterior do CID pelo owner confiável (R1). Antes disso
retém owner/loop, inclusive em falha. Falha de leitura
irrecuperável exige que o coordenador pare o CID próprio; erro/limite nunca
vira prefixo de sucesso. Testar recolhimento completo antes de fechar loop.
Leitor Python do canário/controller usa os.read exato com prazo, sem buffer;
reader shell exato do PG permanece para seu lote, não presumir head seguro.
Sonda T4 mede a implementação asyncio/Proactor real, não apenas fakes.

## R1 — corrida de spawn tardio reproduzida antes do fix

O primeiro teste de lifecycle mediu15pass/1fail: um spawn pendente termina
depois de o coordenador observar CID parado; o docker start então inicia o
CID. O draft aceitava aquela observação antiga, recolhia só o CLI e liberava
o canal apesar do CID ainda vivo. Nenhum Docker/segredo real foi usado.

Refinamento proposto, a revisar antes do fix: substituir Stopped por duas
fases irreversíveis. `quiesce()` proíbe novo envio/start e só emite um ticket
de identidade por owner depois de spawn resolvido, CLI recolhido, pumps
concluídos e pipes fechados. Spawn ainda incerto mantém HELD/loop; ticket
não existe. Após o ticket, o coordenador confiável inspeciona e encerra/remove
o CID próprio por sua identidade, até confirmar **ausência**, não apenas
Runningfalse. A ausência é ligada ao mesmo ticket. `close(absent)` só libera
com CID/ticket exatos; observação anterior, de outro owner ou só parada não
serve. O ticket não é atestação de SO e o coordenador continua responsável
pela evidência causal e pela posse do CID. Remoção impede um start pendente
do engine de reativar aquele CID; não inferir cancelamento de request porque
o CLI morreu. Cleanup por ID/posse permanece separado de aceitação.

Não cancelar spawn sem resultado nem fechar loop com tarefas pendentes.
Quiesce é o único caminho de encerramento do canal e não permite retomada de
seed; falha persistente retém ownership, sem declarar CID ausente ou release.
O ciclo real T4 deve provar essa ordem antes de usar credenciais.

R1 aceito pelo Claude2 antes do fix, com P1–P6: ticket público aleatório
único por owner, identidade exata, monotonicidade coerente; quiesce só pode
ser repetido para collect, nunca reabrir envio. Remoção por posse/ID:
inspect→kill se vivo→reinspect→rm semforce→ausência. Falha conserva pendência;
nenhum retry de Docker implícito no canal. Saída depois de matar CLI é perdida
na limpeza, não resultado; não presumir semântica real de buffering do engine
até a sonda T4. Sucesso natural também exige ticket/ausência/close.

## B1/B2 — fechamento positivo e cancelamento antes da sonda

Revisão do código recusou o draft por HELD eterno com IO pegajoso e
cancelamento externo absorvido. Delta sob contrato estreito revisado:
CPython3.11.3/Proactor e6arquivos stdlib pinados; handle real PipeHandle,
atributo handleNone, processo recolhido e tipo exato para fd0/fd1. Exceção
sozinha nunca prova fechamento. Falta de prova mantém HELD; IO permanece
erro e não vira sucesso sem EOF. Unidade local dos dois handles não é T4.

Foreground é uma tarefa do coordenador: no aborto ele cancela/aguarda
essa tarefa, que propaga cancelamento e libera busy, depois quiesce e
remove/observa ausência do CID por posse/ID. Tarefas internas protegidas
continuam adotadas; cancelamento delas não é confundido com o do chamador.
Após cancelamento o envio não reabre. Metadata público do seed tem estados
NOT_SENT/SENT/UNKNOWN; write iniciado e envio falho/cancelado é UNKNOWN,
e SENT comprova somente handoff ao pipe local, nunca receipt do container.

Spawn tardio após HELD exige nova coleta limitada pelo coordenador, sem
abandonar owner/loop; a sonda T4 terá watchdog independente e provará a
ordem real. Código/fakes ainda aguardam revisão final do delta; nenhum
DockerCLI/PG/credencial novo foi invocado por este desenho.

## Baseline medida posterior — 2026-10-29

T4v2 passou e foi aceita pelo Claude2, transporte3a274347, sete canários
públicos/owners liberados, DesktopOff. StdinOncetrue medido substitui a
expectativa false dos parágrafos históricos acima somente para o futuro
perfil com attach privado; não se reescrevem fontes/raízes consumidas.
EOFtrue foi observado, continua não delimitador. Nenhum segredo ou PG medido.
Próximo desenho em PG16-PUBLIC-ADMISSION-PLAN: ferramentas/UID/tmpfs públicos
primeiro, sem DB/initdb/SQL; depois leitor shell exato público antes de seed
privado. Proibido reutilizar o logger/exportador públicos com esses segredos.
