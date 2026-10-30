# Worker — composição de um job, sem processo ou ingresso operacional

**2026-10-23 — implementado; J1–J6 incorporados antes de código.**
Código revisto sem bloqueador; J7 corrigida depois com regressão vermelha
primeiro.1.410 relacionados finais verdes; WORKER-JOB-VALIDATION e J7
rerevistos sem bloqueador. Plano abaixo preserva o contrato anterior ao código.
Depois de D-117, o próximo incremento conecta as peças existentes para
executar **um** job interno: adapter D-115 → encoder D-115/D-113 → resultado
fechado, usando D-117 para decidir se continuidade sequer é candidata.
Não cria outra máquina de estados, ledger ou framework de adapters.
Não é worker integrado, domínio físico, IPC ou liberação de SQL PGWire.
Todos os perfis D-116 continuam NOT_READY; B-1/B-2/D-090 permanecem abertos.

## Composição mínima proposta

Um módulo privado runtime/worker_job.py, sem export em runtime/__init__ e
sem import por bootstrap/listener/registry/MCP. Função run_job recebe um
PostgresAdapter exato já conectado e de dono exclusivo, SQL str exata,
ResultIdentity/ResultLimits/ResultDeadline exatos. Não constrói adapter,
conecta, resolve DNS, lê ambiente/secret, faz cancel/rollback/close, log,
spawn, thread, transporte, retry ou reconexão. O adapter continua executando
todo o pipeline existente e seu settle; não há cópia de parser/masking.

Valida identidade/limites/deadline antes de tocar no adapter. SQL até64KiB
UTF8, conferida por blocos pequenos; tipo, excesso, NUL ou Unicode inválido
é PROTOCOL fatal sem executar. SQL vazia ou sintaticamente inválida dentro
do envelope segue o validator, não é reescrita. max_rows do ResultLimits
precisa ser igual ao settings da geração no adapter, para truncamento
consistente. Ler uma vez _settings.max_rows, exigir int exato. Inputs
estruturais inválidos são erro fechado/fatal. Identidade só é conferida
quanto a tipo/validade; vínculo com geração/lease do adapter é obrigação
do dono futuro, não comprovado por esta função.

Não abre conexão implicitamente. Exige saúde positiva antes de executar;
chama uma vez _execute_typed_validated, uma vez encode_result com as mesmas
identidade/limites/deadline; não devolve TypedMaskedResult ou linhas.
Após execução confere deadline/saúde; depois de codificar confere novamente
deadline/saúde, com deadline também após essa leitura final, e só então permite
retornar o frame completo. Resultado parcial nunca é publicado. Prazos são
cooperativos aqui; um processo supervisor futuro ainda precisa impor o
deadline de todo job, inclusive chamadas/saúde bloqueadas.

## Resultado privado e erros

JobOutcome frozen/repr redigido contém somente frame bytes ou categoria
JobFailure enum e bool can_continue. Invariantes fechadas: sucesso exige
frame imutável e can_continue=True; erro nunca carrega frame; só QUERY,
TIMEOUT, TYPE e LIMIT podem admitir continuidade, sempre após saúde
positiva e deadline ainda vigente. bool(outcome) recusa uso implícito.
Não é autenticador de bytes nem decoder IPC; construção por código Python
confiável não é sandbox contra reflexão. Futuro receiver valida o frame.

- InvalidQuery/QueryRejected exatos → QUERY; DatabaseResultTypeError exato
  → TYPE. D-117 QUERY/TIMEOUT → categoria correspondente. Candidatos somente
  com saúde positiva e deadline; perder saúde dá CONNECTION fatal.
- EncodeError TYPE/LIMIT → candidatos com as mesmas condições; MEMORY,
  DEADLINE e PROTOCOL fatais. Nenhum frame do encoder é retido em erro.
- RESOURCE/CONNECTION/INTERNAL de D-117, DatabaseResultIntegrityError,
  MemoryError nativa, timeout genérico não tipado, DatabaseError genérica,
  erro desconhecido, interrupção/grupo ou estrutura inválida → fatal.
  Nunca inspecionar mensagem/SQLSTATE ou transformar erro opaco em QUERY.
- Não propagar erro de colaborador nem cadeia nativa. Capturar somente
  categoria/booleans, limpar frames inativos quando possível, descartar
  resultado local e sair do handler antes de produzir outcome. Falha na
  própria limpeza vira INTERNAL fatal, sem promessa de recuperação de todo
  OOM. Nenhuma alegação de apagar RAM/debugger/objetos que outro dono retém.

Mapeamento por **tipo exato**, antes das bases: TypedExecutionTimeout,
TypedExecutionError com categoria enum exata, InvalidQuery/QueryRejected,
DatabaseResultTypeError, EncodeError. Subclasses não listadas são INTERNAL
fatal, inclusive subclasses de recusa/timeout. MemoryError exata é MEMORY;
subclasses desconhecidas também fatais. EncodeError usa sua categoria
fechada/fatal, nunca string de erro. Falha de saúde após execução/candidato
ou após encode → CONNECTION; prazo/clock inválido em qualquer fase →
DEADLINE. Fatal anterior nunca é convertido em candidato por saúde positiva.

J6, escolha explícita sob delegação: esta função privada também converte
KeyboardInterrupt/SystemExit/GeneratorExit e grupos BaseException em
INTERNAL **fatal**, sem frame ou referência original. Preserva sigilo e
o protocolo fechado; não é sucesso nem cancelamento recuperável. Não há
loop operacional que possa engolir o sinal: integração futura deverá tratar
qualquer fatal como ordem de parar/reap, nunca apenas mostrar erro e seguir.
Não usar esta função como wrapper de cancelamento/shutdown de aplicação.

O bool é condição necessária local, não autorização para reutilizar sessão.
Futuro loop precisa manter fatal persistente, um job pendente, IDs monotônicos,
geração/lease corretos, canal quieto e reservas D-112/D-114. Este módulo não
fecha adapter nem libera crédito mesmo em fatal: o dono mantém recursos
até encerramento/reap comprovado. Não introduzir estado global ou fila.

## Validação delimitada e sequência

1. Claude2 revisa este contrato antes de código; root único escritor.
2. Testes primeiro, depois composição privada sem modificar arquivos de
   produto existentes. Fakes de conexão/cursor do adapter real, engine e
   parser reais, encoder e validate_result reais, saúde/deadline reais com
   relógio confiável injetado. Não fingir medição PG/SO com esses fakes.
3. Provar que mascaramento precede o frame (segredo original ausente),
   exceção/derivação/alias preservados pelo mesmo pipeline, múltiplas colunas
   e truncamento coerentes, execução única/sem retry, mesma conexão e
   erro controlado só continua saudável. Nativas/OOM/ownership incerto,
   healthFalse/erro, clock inválido, deadline vencido durante etapas e
   falha de encode não retornam frame. Categorias/mensagens/repr sem canary.
4. Contraprovas de envelope SQL/tipos/bytes, max_rows e limite exato/+1,
   input inválido antes de executar, resultado frozen e uso bool proibido;
   fronteira estrutural impede import operacional (com contraprovas).
5. Seleção adapter/encoder/receiver/snapshot/security/plan relevante;
   Ruff/format/mypy3.11/3.14. Runtime somente Windows3.11.3. Sonda instalada
   limitada, se executada, identifica origem/bytes dos módulos e não atesta
   aplicação completa ou isolamento de dependências.
6. Revisão de código/evidência pelo Claude2; corrigir finding antes de fechar.

Sem novo PG/DockerCLI, carga física, processo de worker ou integração neste
lote: nenhum código de caminho compartilhado é modificado. PG16 real de
D-117 permanece evidência do adapter/encoder anteriores, não deste módulo.
O job ainda deverá executar no worker/domínio real e provar B-1 fim a fim
antes de SQL de cliente. Sem frontend/browser, dependência, setting, porta,
commit/push/deploy. Escolha sob delegação, sem novo aval fictício do usuário.

## Revisão pré-código

Claude2 sessão51ea0d85 aceitou a composição mínima sem bloqueador, pedindo
J1 tipos exatos/ordem/subclasses fatais, J2 lenSQL antes do encode por
blocos, J3 max_rows único/exato, J4 deadline/saúde em cada fase, J5 limite
de correlação e J6 interrupção explícita. Incorporados acima antes de
código; J6 usa a alternativa fatal admitida pelo revisor, não propagação
do erro original. Provas PG/SO e loop/IPC continuam fora deste incremento.
