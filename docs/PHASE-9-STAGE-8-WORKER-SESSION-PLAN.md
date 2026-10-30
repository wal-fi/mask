# Worker persistente privado — protocolo e integração W1

2026-10-26. Escolha técnica sob delegação, proposta para revisão do Claude2
antes de código. D-118 é o corpo do job; D-120 fornece fatos do guard
dd10fb72 medidos no Oracle9.8/amd64. Não é ativação de SQL ou de perfil C1.

## Resultado concreto do próximo incremento

Um processo persistente por sessão privada, com uma única conexão upstream,
snapshot da mesma compilação e jobs sequenciais. Pai não abre conexão da
sessão, não executa parser/masking nem recebe resultset bruto. Filho usa
recompile_snapshot → PostgresAdapter → run_job existentes, sem cópia de
pipeline, segredo relido do ambiente ou segunda resolução DNS. Sem retry,
reconexão, fallback ou fila de aplicação. Nenhum hook em driver/registry,
MCP/Admin/entrypoint operacional neste incremento; SQL atual continua0A000.
Integração de lease remota, C1/D-119 e ingressos é lote posterior próprio.

Peças: worker_protocol.py (schema/binário fechado), worker_process.py
(entrada final e loop Linux), worker_session.py (dono do processo/canais e
resposta), com testes determinísticos e prova nativa/PG16 separados. Não
criar mais uma engine, ledger ou decoder de resultado. D-107 inalterada.

## Bootstrap, confiança e canais

Parent/controller final já deve ter guard aplicado antes de compilar/ler
segredos. Esse é contrato do chamador, não algo que open(snapshot) possa
retroativamente garantir. O futuro entrypoint operacional terá gate próprio.
O ensaio privado usa PID1/thread principal e aplica guard antes dos fixtures.

Filho `python -I -B -m maskgw.runtime.worker_process`, ambiente público mínimo
explícito, close_fds e somente um FD adicional de socketpair AF_UNIX/SOCK_STREAM
herdado. Nenhum preexec_fn, fork-only, segredo em argv/env ou FD com dados
secretos antes de exec. argv contém só número do FD, PPID e AS internos.
stdout/stderr DEVNULL; stdin é PIPE privado inicialmente **vazio**. O pacote
e seus imports anteriores ao guard devem continuar sem leitura de secrets
ou efeitos externos; teste estrutural/sonda. Filho aplica guard no processo
final, confere perfil e FD de socket, só então emite GUARD_READY no socket.
Qualquer falha anterior encerra sem READY e sem ler stdin.

Preservar §5 do desenho: **snapshot secreto chega uma vez pelo stdin
privado**, depois de GUARD_READY conferido contra PID/PPID/AS esperados.
Parent escreve por fd não bloqueante com select e prazo absoluto, fecha o
pipe após o frame; filho exige EOF após esse frame. Nunca communicate,
thread de envio bloqueada, pickle, linha JSON ilimitada ou shell. O socket
privado leva handshake público, tag e depois comandos/respostas limitados.
É extensão do mecanismo interno, não transporte externo novo.

socketpair foi criado pelo pai: SO_PEERCRED pode identificar seu criador,
**não autentica o PID do filho**. Não fazer essa alegação. Confiança é no
código/fd privado/procedência do spawn. GuardFacts/READY não autenticam
código malicioso nem tornam C1 pronto. Exec/credenciais não mudam depois
do guard. Thread criadora do subprocesso vive até o recolhimento completo.

## Wire interno v2, sem conteúdo em logs/erros

Cabeçalho fixo big-endian12bytes `!4sBBHI`: magicMGW2, versão2, kind fechado,
reserved0, comprimento. Tipos GUARD_READY, INIT, OPENED, QUERY, ERROR,
RESULT, DONE, CLOSE. Comprimento exato/limite por kind antes de alocação.
Controle em buffer pequeno pré-dimensionado, até256bytes; SQL e snapshot
são os únicos inputs variáveis, cada qual no máximo64KiB. Leitura exata
com recv_into/offset/blocos limitados, deadline fixo, sem concatenação de
chunks ilimitada. EOF/parcial/versão/reserved/kind inválidos são fatais.

- GUARD_READY: campos binários fixos PID/PPID/AS/DUMPABLE0/PDEATHSIG9,
  enviados após o guard e antes de segredos. Parent compara com o processo
  criado. Não contém secret, nonce ou digest de secret.
- INIT no stdin: metadata fixa com identidade da sessão e geração, limites
  ResultLimits, deadline de abertura, nonce aleatório32bytes e tamanho do
  snapshot canônico D-111, seguido dos bytes exatos (≤65536). Não alterar o
  schema D-111 para pôr o nonce: ele pertence ao envelope. datasource_id
  externo `dso_`+32hex é mapeado para16bytes e recomposto sem UUID inventado.
- Filho valida metadata, recompila snapshot com identidade esperada, cria
  **um** PostgresAdapter com config/engine/conninfo capturados e conecta uma
  vez (verificações existentes ligadas). OPENED só depois de conectar e
  verificar, com HMAC-SHA256(nonce, bytes canônicos) em payload fixo32bytes.
  Parent compare_digest; nonce/tag/snapshot nunca em log, repr, evidência
  ou erro. Isso correlaciona os mesmos bytes, não autentica worker malicioso.
- QUERY: identidade completa D-113, job_id monotônico1..2^63−1, deadline
  absoluto do mesmo relógio monotônico Linux e SQL UTF8 sem NUL≤64KiB.
  Não renova prazo no recebimento/recompilação/encode. Uma operação em voo;
  job repetido/saltado/identidade divergente/corpoextra encerra.
- ERROR: categoria fechada D-118 e can_continue binário. Somente QUERY,
  TIMEOUT, TYPE e LIMIT podem continuar quando o corpo real confirmou
  conexão íntegra. Nenhum texto, SQL, trace ou erro nativo transportado.
  OPENED failure e demais categorias são sempre fatais/sticky.
- RESULT tem payload vazio e precede um frame D-113 completo cru, sem
  reempacotar linhas ou duplicar tamanho. D-114 confere seu cabeçalho/
  identidade/limites antes de alocar buffer variável; pin usa o máximo da
  sessão. Frame já mascarado/validado pelo encoder D-115 é a única
  autoridade do comprimento. Nenhum leitor com buffering/overread.
- DONE de identidade/job exatos termina a resposta. Parent exige DONE
  depois do frame **antes de permitir envio ao cliente**, para que sobra
  entre frame e terminador seja erro antes da exposição. Filho então espera
  próximo QUERY/CLOSE; não emite segundo frame autonomamente. Dados extras
  após DONE são erro no próximo cabeçalho; não se afirma provar ausência
  eterna de bytes de um produtor arbitrariamente malicioso por peek.
- CLOSE sem payload inicia fim gracioso; EOF ocioso tem mesmo efeito. Sem
  resposta de dados no encerramento. Parent conhece término por reap real.

## Ownership, saída e prazos

W1 é interno sem chamador operacional, mas usa D-112/D-114 reais: reserva
de sessão/generation/worker/parent feita pelo chamador confiável antes do
spawn, token/lock/ledger únicos; custos declarados não são cota do SO. AS
virtual e bytes cobrados continuam duas grandezas, sem equiparação. O perfil
Docker agregado e sua reconciliação C1 ainda bloqueiam ativação operacional.
Abrir inicia ownership antes de spawn: falha incerta retém token/HELD.

WorkerSession serializa open/job/close, sem waiting queue e sem segunda
consulta enquanto houver resposta/saída pendente. Depois de RESULT header,
constrói ResultReceiver que pina os créditos **antes de ler/alocar o frame**;
antes disso só buffers de controle fixos. ERROR não cria receiver/pin de
resposta inexistente, preservando continuação de erro recuperável sem
alterar D-114. Reserva P da sessão já existe durante o job.

Receiver READY fica privado até DONE. Resposta oferece send_to pelos canais
existentes, ou descarte explícito. Só send completo seguido de discard/unpin
confirmado permite próximo job; descarte sem envio mantém contrato D-114
de drain e encerra sessão. Cliente lento retém pin/reserva; fim de job não
libera sessão. Falha no envio pode deixar prefixo já validado/mascarado:
completude não comprovada, fecha, sem retry. Pin incerto fica HELD.

Abertura12s totais desde antes de spawn: guard, stdin, compilação, conexão,
verificação e OPENED. Job deadline statement_timeout_ms+10s desde antes de
codificar/enviar SQL. Leitura/body/encode/recepção/DONE usam o mesmo fim.
Idle no filho é limite finito injetado para este teste; valor de produção
virá do perfil existente. Envio ao cliente30s próprio, sem renovar prazo
de execução. Graceful close1s, kill/reap em janelas finitas separadas,
verificação real de processo/canais/refs antes de devolver qualquer token.
Erro de SO persistente deixa ownership/quarentena, não “limpo” por timeout.

Filho fecha seu adapter uma vez no finally; se driver/close bloquear, o
parent mata/recolhe. EOF durante driver bloqueado não é cancelamento: prazo
do pai/PDEATHSIG/namespace são gates separados. Reap local não prova término
instantâneo da query no PostgreSQL. OOM/crash/timeout/protocolo são fatais,
sem resultado bruto/parcial nem execução alternativa no pai.

## Matriz e sequência de evidência

1. Revisão deste contrato antes de código. Matriz de codecs/estados e
   transporte simulado: tamanhos/tipos/identidade/job/order, segredo sem
   origem/env, redaction, framing extra/parcial, erro recuperável/fatal,
   concorrência sem fila, outputpin/HELD e todos os limites/prazos/cleanup.
2. Revisão do código e de artefatos/comandos/procedimento antes de Docker.
   Novo ciclo impõe idade máxima **monotônica** entre A/Observe/Ready/B,
   com aborto sem B se vencer. Abort pré-B também precisa de restauração
   segura do Desktop próprio com inventário fresco vazio. Não herdar o
   controle antigo sem esse gate nem repetir a pausa da evidência D-120.
3. Prova nativa do worker final protegido com PG16 descartável e dados
   sintéticos próprios, ambiente/rede/TLS/creds/perfil previamente revistos.
   Conninfo fixado sem nova resolução. Provar masking/derived/exceptions/
   HMAC da geração, OIDs e limites, conexão única persistente, recoverable→
   query seguinte, fatal/deadline/blackhole/EOF/shutdown e nenhum envio antes
   de frame+DONE. Provar parent/controller e morte de PID1/namespace. Cotas
   não aumentadas para obter verde; pressão agregada/capacidade tem matriz
   própria, não é consequência do teste funcional.
4. Novo wheel instalado deve conter guard/protocolo/loop/owner e provar
   o caminho real; copiar módulos só vale como prova privada declarada.
   Nenhum ingresso operacional antes de B-1/B-2/D-090 próprios, C1 e revisão.

Não altera o catálogo, Admin/UI, MCP legado, configuração externa, listener,
dependências ou SQL aceitas hoje. Foco é entregar um worker funcional
privado, não expandir requisitos do produto. Release final ainda requer
patch/minimalização de ferramentas/libs e todos os gates de uso/deploy.

## Revisão do desenho e ajustes incorporados

Claude2 não encontrou bloqueador de desenho e aceitou implementar sob a
delegação com os ajustes seguintes, antes de revisão do código/procedimento:

- S1: validador existente só aceita SelectStmt; SqlPolicy recusa set_config,
  setseed e famílias perigosas, namespace pg_ por allowlist. **Não** recusa
  toda função definida pelo usuário com efeito colateral (risco aceito
  D-027/SECURITY-REVIEW); não inventar garantia geral de imutabilidade.
  Worker captura e confere antes/depois de cada job, inclusive erro, um
  fingerprint fechado e privado de current_user/session_user, search_path
  **e schemas efetivos/pg_temp**, readonly, statement_timeout, client_encoding,
  TimeZone/DateStyle/isolamento/row_security. Divergência/falha de probe é
  fatal antes de resultado/DONE/ERROR recuperável. Prepared statements
  gerenciados pelo driver são estado esperado, não comparação “tudo igual”.
  Probes confiáveis de metadata ficam no adapter, sem masking/pipeline
  paralelo ou retorno desses valores ao pai/logs. Não fecha riscos de UDF
  nem efeitos externos que continuam exigindo privilégio read-only mínimo.
- Spawn apenas por thread dona de lifetime integral (principal/event loop,
  nunca pool). Registrar ident e conferir ao recolher; shutdown em outra
  thread pode solicitar parada, mas não fingir a thread dona recolhida.
- Pai e filho Linux no mesmo CLOCK_MONOTONIC/sem time namespace diferente;
  deadlines vencidos ou além do teto do papel são recusados no filho. Pai
  impõe prazo/reap independentemente. ERROR só recuperável com categoria,
  saúde, S1 e recebimento ainda dentro do prazo; nunca renovar prazo.
- Matriz cobre INIT máximo maior que a capacidade do pipe, EOF, e duas
  sessões simultâneas sem herança de FD cruzada. Referências de snapshot/
  nonce/tag do pai descartadas após handshake, sem promessa de zeroização
  de bytes Python. Bytes não vão para evidência, inclusive fixtures sintéticas.
- Prova PG16 medirá o maior frame e limite de linhas sob AS escolhido
  previamente; OOM/falha não provoca aumento durante a rodada.
- Falha antes de GUARD_READY fecha o processo/canal sem diagnóstico nativo;
  parent recebe somente EOF/prazo/categoria local fechada. Limitação aceita
  desta interface; não abrir stderr para obter traceback com secrets.
- Frescor do procedimento usa contador monotônico **que inclui suspensão**
  e identidade do boot, não só UTC/Stopwatch presumido. Boot alterado ou
  idade vencida aborta antes de B, com restauração pré-B segura e sem retry.

### S1 implementável, sem promessa de auditoria completa do PostgreSQL

Sonda fixa25colunas, funções e operadores explicitamente pg_catalog para
não depender de resolução do search_path observado. Inclui estado acima,
backendPID/database, standard_conforming_strings e contagens de advisory
locks/canais LISTEN da própria sessão. Baseline exige freshsession sem
pg_temp/locks/canais, readonly padrão/atual on, UTF8, row_security on e
standard_conforming_strings on. Não altera GUC nem repara a sessão.
Uso é opt-in só no worker, sem efeito em connect/execute legados.

Registro privado imutável, sem hash/tag serializado, arrays desanexadas,
metadata total≤64KiB, campo≤8KiB e até64schemas. Contenção do fetch/libpq
continua AS/cgroup do worker; validar depois não é teto de alocação nativa.
Qualquer shape/tipo/estado/mudança/erro do probe é fatal, MemoryError mantém
categoria de recurso. Probe antes e depois de sucesso/erro recuperável no
mesmo prazo; em fatal já não há continuação nem envio, sem query extra para
“provar saúde”. São invariantes selecionadas, não inventário de todo estado
nem revogação dos riscos aceitos de UDF/servidor/privilégio.

Fontes primárias consultadas em2026-10-26:
- https://www.postgresql.org/docs/16/functions-info.html
- https://www.postgresql.org/docs/16/view-pg-locks.html
- https://www.postgresql.org/docs/16/runtime-config-client.html

Revisão de S1 aceitou o hook isolado. Recomendação de formatos incorporada:
IntervalStyle, bytea_output, extra_float_digits, lc_monetary, lc_numeric e
xmloption também são invariantes comparadas. PREPARE/EXECUTE/DECLARE/SET e
set_config diretos são recusados pelo validator existente, com5contraprovas
puras. Não contar pg_prepared_statements genericamente: o cache automático
do driver é estado esperado e não será desativado silenciosamente. Funções
de usuário continuam risco D-027 explícito; não se afirma impedir todo
efeito/estado arbitrário. Mudança externa legítima nos schemas efetivos
também encerra conservadoramente a sessão, sem reset/rebase automático.

## Ajuste de integração revisado, antes do loop/owner

O v1 puro b3371532 foi aceito/testado, mas não tem consumidor nem foi usado
em processo. Ao integrar, ficou explícita a duplicação de comprimento:
RESULT trazia uint32 externo, enquanto D-113 já traz comprimento próprio.
D-114 não exporta frame_bytes nem recebe um segundo comprimento esperado.
Não acessar buffers privados nem alterar D-113/D-114 só para comparar duas
cópias da mesma informação.

Versão v2 interna aceita em revisão, sem compatibilidade/fallback com v1: magicMGW2 e byte
versão2; RESULT passa a payload vazio (só sinaliza que vem um frame D-113).
Parent constrói receiver/pin pelo **máximo da sessão**, antes de ler o
cabeçalho D-113; o receptor existente valida comprimento/identidade/limites
antes de alocar o corpo e lê exatamente aquele frame. Depois exige DONE
correlacionado antes de enviar. Mantém16MiB/2F/pin/terminador e elimina a
necessidade de mudar os núcleos já revisados ou confiar em tamanho externo
menor para reservar capacidade. Demais kinds/metadata/tetos permanecem.
O v1 e suas evidências são históricos; v2 será revisado/testado antes de
qualquer uso. Não é mudança de PGWire externo ou de API administrativa.

Ownership concreto: construir/adotar o handle **antes** do spawn, marcando
token RESERVED→LIVE sob o lock comum como adoção exclusiva; isso modela
ownership/custo de bootstrap, não certifica SO/ResumeThread/C1. Segundo
owner do mesmo token recusa antes de adquirir ownership e não o libera.
Chamador confiável registra o handle antes de chamar open; shutdown pode
marcar stop mesmo com spawn pendente. Quem cria o filho é thread principal
ou thread dedicada de sessão, como as não daemon já usadas no listener,
nunca executor de pool. Guardar objetoThread+ident e conferir no recolher;
outro thread só solicita stop, sem declarar dono encerrado.

Prazo de abertura é contabilizado antes de Popen e testado ao retornar,
sem entregar segredo se já venceu. Falha persistente/chamada de SO que
não retorna não ganha promessa de teto absoluto: ownership/capacidade
ficam retidos, shutdown incompleto, nunca abandono ou crédito livre.
Execução/parser/driver/masking após spawn continuam limitados pelo pai.

Timeout idle é argumento interno público adicional ao argv (milissegundos
finitos/validados), junto de FD/PPID/AS; permite usar o perfil futuro sem
segredo/env e sem chumbá-lo em300s. Sem configuração externa nova neste
lote. Estes ajustes são escolhas técnicas sob delegação revisadas antes
de código, não aval individual inventado ou liberação de SQL.

Revisão do delta v2/ownership aceitou sem bloqueador, com requisitos
incorporados: leitura recv_into/exata sem makefile ou perda de sobra;
RESULT vazio→pinmáximo→D113header/body→DONE correlacionado→exposição;
v1/versões cruzadas recusadas sem fallback; Popen tardio não recebe byte
de INIT e é recolhido antes de liberação. Testar frame+DONE coalescidos,
DONE fragmentado, extra entre frame/DONE e latePopen. O v1 puro permanece
como história: fonte/teste originais b3371532/ec94091f preservados em
worker-protocol-v1-accepted-20261026.json (SHA eb9553886abdd79f7264c352ec4c9f82e516b97d255185314c65fe40934257dc),
sem uso nativo/operacional. v2 substitui v1, não coexiste com ele.
