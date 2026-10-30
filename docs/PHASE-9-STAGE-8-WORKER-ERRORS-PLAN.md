# Worker — erros tipados e saúde antes de continuidade

**2026-10-23 — plano implementado/revisado; contrato pré-código preservado.**
Resultados e limites em WORKER-ERRORS-VALIDATION; PG16 e pacote concluídos,
revisão final sem bloqueador. Não repetir o procedimento PG consumido.
Pré-requisito do worker persistente da Etapa8, sem spawn/IPC/worker operacional,
ingresso SQL ou alteração dos gates B-1/B-2/D-090. Nenhum destino escolhido.
C1 permanece puro e todos os seus perfis NOT_READY. Não repetir HELD.

## Problema concreto

D-115 compartilha _run entre execute/execute_validated legados e
_execute_typed_validated. Hoje psycopg.Error vira sanitize_error em ambos:
texto fixo preserva sigilo, mas só QueryTimeout mantém classe particular.
Worker futuro não pode distinguir recurso/erro local de consulta controlada
por esse objeto. Não inferir causa de memória pela mensagem localizada.

Além disso, adapter.closed=False isolado não comprova sessão íntegra após
_settle. Continuidade depende simultaneamente de classe permitida e saúde
positiva da mesma conexão. Uma classe de erro não atesta saúde, e saúde não
transforma erro de memória em recusa recuperável.

## Contrato mínimo proposto

Um módulo privado db/execution_error.py, sem novos exports públicos db,
contém enum fechado: QUERY, TIMEOUT, RESOURCE, CONNECTION, INTERNAL.
Exceções novas são subclasses de DatabaseError; timeout tipado permanece
subclasse de QueryTimeout, mantendo compatibilidade dos testes D-115.
Carregam somente enum/mensagem fixa, sem SQLSTATE, texto nativo, SQL,
parâmetros, DSN, exceção/cadeia original ou boolean de saúde inventado.

Somente o catch psycopg.Error de _run(typed=True) usa o classificador novo.
typed=False continua chamando exatamente sanitize_error, com classes,
mensagens e semântica anteriores. connect(), D-107, _settle, provenance,
sensibilidade/validator, masking, cursor, truncamento e canonicalização
permanecem iguais. Sem duplicar pipeline nem exigir novo dado no legado.

Classificação interna antes de descartar o erro:
- SQLSTATE exato57014: cancelamento do servidor, timeout tipado por
  compatibilidade, candidato a continuidade; não prova statement_timeout;
- classes canônicas0A/21/22/23/40/42/54 e código exato25006: QUERY,
  candidato a continuidade; restantes25xxx são INTERNAL/fatais;
- classe53: RESOURCE, sempre fatal no worker futuro;
- classe08 ou SQLSTATE ausente: CONNECTION, fatal;
- outras classes, estado truncado/não canônico, falha ao acessar sqlstate:
  INTERNAL, fatal.
SQLSTATE aceito precisa ser str exata de cinco caracteres A-Z/0-9.
Não ler str/repr/diag ou dados arbitrários; não guardar código recebido.
MEMORYERROR nativa fora de psycopg.Error continua fatal no worker futuro;
este lote não afirma capturar toda alocação nem provar recuperação de OOM.
RESOURCE de servidor não prova OOM local; o encerramento conservador é
política de integridade para essa categoria, não atribuição causal.

O objeto novo é criado sem reutilizar exceção original; _raise_sanitized
continua levantando somente depois do handler. Não alterar strings/classes
de erro do legado. Construtor inválido produz categoria INTERNAL fechada.

Método interno _typed_connection_healthy():
- não conecta, cancela, executa SQL, reconecta, fecha ou faz rollback;
- exige _connection presente, closed is False, broken is False,
  info.status is psycopg.pq.ConnStatus.OK e
  info.transaction_status is psycopg.pq.TransactionStatus.IDLE;
- campo ausente/inválido, estado diferente ou erro de introspecção retorna
  False, sem mensagem/chain original.
É chamada após _settle, pelo dono com uso exclusivo da conexão; não adiciona
lock nem torna leituras atômicas contra acesso concorrente não autorizado.
É evidência local de estado libpq, não atestado de rede viva, read-only
futuro, prazo, upstream confiável ou prova de que a conexão nunca falhará.
Socket já fechado no servidor pode ainda parecer OK no libpq; a próxima
execução falhará CONNECTION fatal, sem retry/reconexão. Worker futuro só
considera continuar quando categoria candidata **e**
saúde positiva **e** nenhum fatal/ownership incerto persistiu. Nunca retry,
reconexão ou fallback para execução no pai. Nenhum chamador operacional
é ligado por este lote.

## Validação e revisão

Antes de código: revisão somente leitura pelo Claude2 desse contrato.
Depois, testes de contrato/sigilo com SQLSTATE real e fakes estritos:
classificação completa, tipo exato/limites, nenhuma leitura de mensagens,
original sem cadeia/referência, timeout preservado, RESOURCE/ausência de
estado nunca recuperáveis, metadados de saúde incompletos/indeterminados,
legado sem chamar classificador novo, mesmo masking/proveniência/_settle.

Testes proporcionais do adapter/typed encoder e regressões existentes,
Ruff/format/mypy3.11 e3.14, execução Windows3.11.3. Se tocar caminho comum,
gate PG16 real deve executar antes de fechar evidência/publicar. Somente
PostgreSQL16 descartável próprio em loopback, sem banco do usuário. Preparo
Docker/estado/ownership/cleanup terão procedimento próprio antes de ação;
nenhum start/CLI/banco ainda é execução deste plano.

Integrações reais: erro de consulta, timeout e conexão terminada por
administrador de fixture própria, com saúde IDLE/pid e sequência posterior
quando permitido. Erro SQLSTATE53 sintético não é pressão nativa nem fecha
B-2. Máscara e readonly devem permanecer comprovados. Sonda de pacote
limitada, se executada, não certifica aplicação completa.
Nada de browser/frontend sem alteração pertinente.

Código e evidência serão revisados pelo Claude2, root único escritor.
Sem novo setting/dependência/porta, ativação Admin v2, SQL PGWire, commit,
push ou deploy neste lote. Escolhas sob delegação, sem aval individual fictício.

## Revisão pré-código

Claude2, somente leitura51ea0d85, não encontrou bloqueador; W1 estreitou25
para25006 (25P02/25P03 fatais), W2 esclareceu57014 como cancelamento e outros
57xxx fatais, W3 acrescentou ConnStatus.OK/uso após settle/limite de rede,
W4 acrescentou classe21 para cardinalidade. Incorporados antes de código.
