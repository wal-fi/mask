# Etapa 8 — receptor, ownership e pin de saída

**2026-10-20: implementado localmente sob delegação, revisão do Claude2 antes do código.
Integração interna de ledger + buffers + socket de teste, não de registry,
worker ou ingressos. Não libera SQL nem fecha B-1/B-2/D-090.**

## 1. Entrega concreta

`pgwire/result_receiver.py`: receptor que lê o header fixo antes de alocar
o corpo, valida integralmente com D-113 e envia somente slices já validados
pelo transporte existente. Sem threads/subprocessos criados pelo receptor.
Testar sockets locais reais, leituras curtas, EOF, prazo, falha e cliente
lento; não apenas outro modelo com fatos sintéticos.

Não expor payload, ValidatedResult ou chunks pela API do receptor. `receive`
não retorna dados, `send_to` retorna só metadados escalares. Somente RawChannel
ou TlsChannel auditados recebem views síncronas; não um callback arbitrário
que poderia guardá-las. Isso não é isolamento contra Python hostil/reflexão.
Custos nativos/SSL, socket, allocator e debug que captura locals continuam
exigindo prova/controle próprios antes do produto.

## 2. Cabeçalho e I/O reutilizados

Extrair `inspect_result_header` no núcleo D-113, usado tanto pelo validador
inteiro quanto pelo receptor, sem duplicar gramática. Aceita só 76 bytes e
confere magic, versão/flags, identidade, rows/colunas, limite total e mínimo
estrutural antes de retornar tamanho total/metadados finitos. O frame inteiro
continua tendo consumo exato validado pelo mesmo parser.

Acrescentar `RawChannel.recv_into` para preencher view de bytearray do dono,
com fatias limitadas por TransportLimits e mesmo prazo absoluto, sem expansão
por append ou cópia proporcional intermediária. Somente memoryview 1D,
contígua, gravável, formato B e não vazia. Retorno de recv_into deve ser int
exato, 1..fatia; zero é EOF, outra forma é falha fechada. Timeouts parciais
não renovam o prazo. Sem abandonar uma thread para simular cancelamento.

`ResultDeadline.remaining` permitirá usar o mesmo prazo no transporte e
validação. Anotações do transporte usam um protocolo **privado** de remaining;
Deadline existente continua compatível. send_all aceitará bytes/memoryview,
sem mudar o caminho existente de bytes. Não é interface genérica de produto.

## 3. Vínculo real com a reserva existente

Uma sessão já admitida/mark_live tem parent_bytes reservado. Antes de ler
até mesmo o header, sob **o mesmo lock coordenador externo** que serializa
todo acesso ao ledger, `begin_output(session, frame_bytes, overhead_bytes)`:

- deriva F dos limites do receptor, grava F/overhead no pin e na imagem e
  confere total <= min(limits.max_frame_bytes, pin.frame_bytes) após o header;
  confere sessão LIVE, barreira aberta e custo mínimo `2F + overhead` contra
  seu parent_bytes, sem tomar crédito de outra sessão ou nova reserva parcial;
- recusa se já houver saída pendente;
- publica na imagem imutável um pin e época de saída limitada a 63 bits;
- emite token ligado a ledger/slot/época de sessão/época de saída.

O overhead é parâmetro interno positivo declarado pelo coordenador confiável,
**não** cota de SO nem prova universal derivada do tracemalloc. O receptor
limita buffers proporcionais a 2F; todos os demais custos do pai/SSL continuam
no gate B-2. Não declarar orçamento físico fechado por essa fórmula.

`release(session, confirmação completa)` deve continuar HELD se o pin existir,
mesmo que um chamador peça output=True. `end_output` só limpa o pin, nunca
devolve parent_bytes, worker_bytes ou vaga da sessão. Token velho/de outro
ledger não limpa o pin corrente. Época não dá wrap; sem histórico crescente.
Alterar campos internos do ledger não cria lock próprio ou I/O no núcleo.
`_validate` confere pin só em SESSION, épocas na faixa e custo contra o
parent_bytes. `end_output(discarded, drain)` limpa pin e marca DRAINING,
quando necessário, numa única imagem, nunca em dois commits.

## 4. Ownership e descarte em duas fases

Um ResultReceiver tem estados NEW → READING → READY → SENDING → SENT;
falha vai a FAILED. Toda decisão/ledger usa o mesmo lock externo; I/O,
alocação grande e descarte pesado ficam **fora** do lock. Reentry/segunda
operação em READING/SENDING/DISCARDING é recusa imediata, sem fila.

Depois do pin: header fixo, header validado, bytearray exato do tamanho total,
recv_into do corpo, cópia imutável e validação completa. Até o fim da cópia
coexistem dois buffers de tamanho ≤F; não concatenar para criar um terceiro F.
Após a função interna de leitura retornar, só o receptor guarda o resultado.

send_to consome os chunks internamente, chama send_all síncrono e não os
retorna. Mesmo após SENT, o pin permanece até close explícito. close:

1. sob lock, marca DISCARDING e retira o dono de self;
2. fora do lock, descarta a referência local e todas as views/iteradores;
3. só depois, sob lock, limpa o pin e marca CLOSED. Falha retém pin/estado
   HELD para cleanup posterior; nunca liberar capacidade com dono incerto.

Descarte sem envio ou após falha também marca a sessão DRAINING, impedindo
novo job sobre conexão/saída não comprovada. Após envio normal, sessão pode
continuar LIVE. close não fecha worker/canal nem libera a sessão no ledger;
o coordenador futuro continua responsável por esses recursos.

Sem finalizer que libere crédito automaticamente. Se o chamador perder o
receptor, o pin mantém a sessão retida, não libera orçamento por GC. Não há
retry/reconnect/fallback, nem segundo resultado enquanto o anterior tiver dono.

## 5. Erros sem retenção acidental de frames

Funções internas capturam falhas, reduzem a categoria fechada e limpam
tracebacks inativos antes de retornar. Nada de exc_info/locals/logging.
Exceção externa é criada fora do except, sem input/erro original; ao fazê-lo,
a função externa não guarda buffers em variáveis locais. Em falha, o pin
permanece até close e os outros recursos continuam exigindo cleanup real.

Não se promete apagar dados da RAM ou remover contexto já ativo no chamador.
Views não escapam pelos caminhos auditados; callback/depurador hostil que
guarda locals está fora dessa afirmação e não pode ser habilitado em produção.

## 6. Testes e critérios

Teste primeiro o pin: último crédito, duas saídas, sessão/época/token errado,
release durante pin, barreira, esgotamento, idempotência e falhas modeladas de
commit/rollback. Regressões antigas do ledger devem permanecer verdes.

Receptor: header inválido/oversized/correlação errada não aloca corpo; EOF em
cada fase, reads de 1..N, zero/progresso inválido, I/O/MemoryError sanitizados,
prazo absoluto, corpo inválido não escreve nada, owner preso após SENT,
close/reentry/concorrência nos pontos de estado com barreiras, falha de
descarte retendo pin e nova sessão sem herdar conteúdo anterior. Verificar
ordem real de descarte antes da limpeza do pin, não só booleans de fixture.

Sockets locais reais (sem banco/rede externa/serviço novo) para recepção
fragmentada, EOF, timeout e envio pequeno. Fixture de até 16 MiB com sender
de teste controlado; buffers criados antes da medição, teto complementar de
recepção+cópia+validação **2F + 512 KiB** com tracemalloc. Não prova commit
nativo/SSL/arenas. Threads auxiliares só no harness, com prazo e join real.

Gate de isolamento passa a permitir apenas esse consumidor interno de D-113
e B2-B1, nunca listener/registry/main/gateway. Análise e contraprovas continuam
recusando imports relativos/dinâmicos por outros módulos. Ruff/format/mypy
3.11/3.14 e testes proporcionais, revisão do código antes de integração.
Pacotes/runtimes/plataformas só serão declarados quando medidos.

Decisão candidata D-114, sem nova configuração/dependência, SQL ou ativação.
Mesmo sucesso não prova pipeline, masking, contenção worker/SSL ou produção.

## 7. Revisão e ajustes vigentes antes do código

Claude2 revisou em modo somente leitura, sessão
`e3df1a1e-ecca-4b1f-b5a6-0b2633f83d03`. O contrato acima recebe os seguintes
ajustes obrigatórios, que prevalecem sobre formas abreviadas do texto:

- Pin separado do token de sessão, com época da sessão e época própria;
  frame_bytes/overhead registrados e custo conferido pelo ledger. drain e
  limpeza do pin são uma única transição, inclusive durante closing/HELD.
- Lock é exatamente threading.Lock (não RLock), como o registry existente.
  Aquisição limitada pelo prazo e por uma fatia interna finita de 250 ms;
  falha deixa estado/owner retidos, não executa I/O sob lock já possuído.
  close recebe prazo próprio de cleanup; nunca reutiliza prazo expirado.
- ResultDeadline.remaining retorna float finito não negativo; clock inválido
  ou falho retorna zero, e check/transport fazem a recusa fechada. recv_into
  captura OSError/ValueError/TypeError, sem aceitar bool ou progresso >fatia.
- Views de recepção usam contexto e são liberadas. Mutable buffer é descartado
  antes da validação. Gerador de chunks é fechado e cada view liberada em
  finally, antes de propagar uma falha externa sanitizada.
- Interrupção BaseException sinaliza conclusão anormal e mantém pin; estado
  sob lock vira FAILED/HELD, sem liberar sobre traceback ainda possuído pelo
  chamador. Falha de limpeza de traceback também retém pin, sem fingir descarte.
- Durante descarte, evento factual de término é sinalizado **após** a última
  referência local ser descartada fora do lock. Isso permite retomar a fase 3
  após timeout transitório do lock, sem outro closer roubar um descarte em voo.
  Decisões/ledger continuam sob o lock único; não há finalizer que libere.
- Envio parcial seguido de falha obriga drain=True ao fechar e encerramento
  da conexão pelo coordenador futuro. Nunca retentar/reconectar/reaplicar.
- Testes instrumentam o commit end_output com tracemalloc para comprovar que
  o payload rastreado já caiu antes de limpar o pin; tolerância predeclarada
  de 512 KiB além do baseline. Não é prova de retorno de commit ao SO.

Os oito pontos técnicos da revisão foram incorporados, sem dispensar gates
de produto. Fontes/testes passarão por revisão antes de fechamento.

## 8. Incremento medido e obrigações de integração

Implementação e evidência em `PHASE-9-STAGE-8-RECEIVER-VALIDATION.md`.
As revisões de código acrescentaram retenção por ExceptionGroup e erro
encadeado/opaco sanitizado pelo transporte, inclusive timeout. Sinal escalar
de incerteza não transporta exceção, e nunca confirma descarte.

Incerteza é quarentena permanente neste receptor, sem API de recuperação;
contabilizar créditos como indisponíveis até encerrar/reiniciar o processo.
BUSY/DEADLINE depois do I/O podem ocorrer com corpo já entregue: qualquer
ReceiverError de send_to exige saída não comprovada, drain e fechamento,
nunca retry. Canal do worker deve produzir exatamente um frame por job e
ficar quieto; bytes extras não são consumidos pelo receptor. Integração
deve garantir job novo/identidade e canal quieto ou drenar. Não libera SQL.
