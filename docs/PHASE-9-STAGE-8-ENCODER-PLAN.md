# Etapa 8 — encoder de resultado e pipeline tipado (D-115)

**2026-10-20: incremento interno implementado e validado sob delegação,
com plano/código revisados pelo Claude2 e suíte integral PG16 verde. Sem
habilitar SQL de cliente, worker ou serviço operacional. O texto predeclarado
abaixo é complementado pelas revisões e resultados no final.**

## Entrega e vínculo com o objetivo

Conectar o pipeline real do banco ao formato D-113/D-114, como peça usada pelo
worker por sessão futuro. Não criar outro engine, validação SQL ou prova só
de um modelo. Worker/isolamento, lease e memória física permanecem gates
seguintes; este incremento precisa de PostgreSQL 16 descartável real.

1. DTO `TypedMaskedResult` em `db/result.py`: contém apenas MaskedResult já
   protegido e tupla posicional de OIDs **anunciados**, derivados no mesmo
   cursor. MASK normaliza para 25 sem ler/guardar OID upstream; ALLOW/EXCEPTION
   conferem o OID de origem contra tabela fechada. Repr só
   contagens, sem dados/proveniência. Não ampliar ColumnDescriptor, QueryResult
   nem a resposta MCP. Sem propriedade mutável last_result/metadata que possa
   misturar consultas concorrentes ou reaproveitar estado após erro.
2. `PostgresAdapter._execute_typed_validated(sql)`: mesma validação/análise do
   caminho existente e um único corpo interno compartilhado de execute.
   Captura cursor.description.type_code só no opt-in tipado e em não-MASK, junto de _describe,
   ANTES do fetch; legado não passa a exigir esse atributo dos dublês. Mantém
   decisão/proveniência antes de masking, max_rows+1 e descarte do excedente,
   read-only, timeout, mesma conexão e _settle sem COMMIT. Nenhum cursor ou
   linha crua retornado, sem callback genérico ou dependência db -> encoder.
3. `pgwire/result_encoder.py`: aceita somente DTO tipado fechado, identidade,
   limites e deadline; produz frame completo privado imutável do D-113.
   Chamadores só testes neste incremento. Sem import do listener/main/registry.

## Tipos e representação

Saída de coluna MASK é sempre OID25/texto, com str exato ou NULL, conforme
PHASE-9-SPEC §5.5. O original já passou pelo engine; o OID upstream não é
usado para inferir o tipo do valor mascarado. Questão para revisar: o §6.2
antigo do desenho pode ser lido como recusa de qualquer OID upstream fora
do subconjunto, mesmo depois do masking. Fechar explicitamente a leitura
coerente com §6.1 (coluna mascarada text) antes do código; não alegar suporte
de preservação a tipo desconhecido nem generic str/repr.

Nas colunas ALLOW/EXCEPTION: só OIDs 16,21,23,20,19,25,1042,1043; nenhum
numeric/float/data/uuid/json/bytea/array/domínio customizado preservado.
Mesmo NULL não torna um OID desconhecido anunciável. bool e int exatos
distintos, faixa por OID, texto UTF-8 estrito sem NUL, name até 63 bytes.
Colunas MASK saem text inclusive quando a origem for int/bool; nunca anunciar
OID inteiro e enviar hash/string. Nomes vazios/duplicados preservados por posição.
Metadata de tabela/atributo zero, typmod -1, formato texto, typlen da tabela
fechada já validada por D-113. Zero colunas recusado.

## Limites antes da alocação e atomicidade da resposta

Preflight de metadados, tipos, valores, dimensões e tamanhos; não montar lista
de células/linhas codificadas nem fazer join da resposta. Tuplas/escalares
imutáveis exatos, sem método arbitrário de conversão. Percorrer texto em blocos
de até 4096 caracteres (até 16 KiB UTF-8 temporários), conferir max_cell e total
antes de alocar frame. Inteiros no máximo 20 bytes. Deadline por bloco/célula
e operações estruturais; sem clock renovar prazo. Não tentar preemptar código C.

Depois de preflight: bytearray exato do total <=F, escrever via pack_into e
blocos UTF-8, bytes(buffer), descartar buffer antes de validação D-113 final.
Máximo proporcional 2F + scratch; não é limite de resultado já materializado,
libpq/AST/masking, native/SSL ou memória do worker. B-2 continua obrigatório.
Corpo T, D* e C inteiros, nunca emitir bytes parciais quando falhar. O encoder
não escreve stdout/socket e não cria processo/thread. Recepção e pin continuam
no D-114, não são propriedade do encoder.

Erro só categoria fixa (tipo/limite/protocolo/prazo), sem dados, SQL, OID,
nome, input ou exceção original. OOM capturado sem fallback ou default=str.
Tracebacks privados não devem ser guardados/logados; worker deve descartar
resultado/frames e encerrar se integridade de cleanup não for comprovada.

## Provas necessárias neste incremento

- RED antes das APIs; fixture binária independente + validador D-113 + receiver
  real em socketpair, sem usar encoder como oráculo da própria codificação;
- int bounds, bool != int, OID/value mismatch, tipos não suportados, NULL,
  UTF-8/NUL/surrogate, name, duplicatas, masked OID25, max_rows/truncated,
  limite exato e excesso sem alocar frame, MemoryError e deadline no bloco;
- saída máxima sob 2F + 512 KiB de alocação complementar (entrada criada antes),
  falha de validação sem retorno, sem I/O/importador operacional;
- fixtures do adapter e regressões do legado; falha de OID antes do fetch,
  metadata por posição e por consulta, _settle em todas as saídas;
- PG16 descartável: aliases, duplicatas, exceptions autoritativas, AST derived,
  masking HMAC/regex/random, tipos/NULL, truncamento sem mascarar excedente,
  erro de catálogo fail-closed, read-only/timeout/same session e nenhum dado
  bruto no frame. Não usar banco informado anteriormente pelo usuário;
- Ruff/format/mypy 3.11/3.14, pacotes instalados; runtimes/plataformas/full suite
  só declarados se medidos. Revisão antes de registrar fechamento.

Referências primárias consultadas: PostgreSQL16 Message Formats (RowDescription,
DataRow, CommandComplete) e psycopg3 Column.type_code/description. Não usar
psycoPG2 como contrato. São formatos/OID do tipo, não inferência de proveniência.

## Revisão prévia e contrato fechado

Claude2, sessão somente leitura `8c333756-5a6d-4115-883d-7bcac5c7d519`, leu
plano, contratos e caminhos legados antes do novo código. Seis esclarecimentos adotados
sob delegação, sem aprovação individual fictícia:

- §6.2 do desenho aplica-se ao OID anunciado. MASK (inclusive DERIVED)
  anuncia text25 e aceita somente str exato ou NULL já protegido, sem reter
  tipo de origem; ALLOW/EXCEPTION preservam só os oito OIDs fechados, mesmo
  quando NULL. Não é suporte a preservar tipos arbitrários. Domínios exigem
  medição: type_code pode observar o tipo base, não se promete detectar domínio.
- DTO valida estrutura imutável exata/posicional, decisões e OIDs anunciados;
  o encoder revalida, inclusive contra adulteração interna. Tabela única
  imutável em db/result.py, sem db -> pgwire; teste de paridade com D-113.
- Recusa tipada do adapter: subclasse de DatabaseError com mensagem fixa,
  antes do fetch em OID não suportado/zero colunas. Encoder tem categorias
  próprias TYPE/LIMIT/DEADLINE/PROTOCOL, distinguindo recusa de protocolo
  (contrato posteriormente ampliado com MEMORY fatal, nos ajustes vigentes).
- Preflight obriga rows<=max_rows e truncated=>rows==max_rows antes de alocar,
  sem fingir que limite do encoder pode divergir livremente do adapter.
- UnicodeEncodeError captura a string: reduzir fora do handler; erro não
  anexa input nem cadeia. Referências/cópias do encoder devem ser descartadas
  antes de levantar; traceback ativo no chamador não é apagamento de RAM.
- execute_validated continua chamando execute, e ambos compartilham a análise
  e o corpo de execução com o opt-in tipado. Regressões antigas permanecem.

Esses ajustes fecham os seis pontos do plano antes do RED. B-1/B-2/D-090
permanecem abertos; nenhuma contenção física é inferida deste encoder.

## Ajustes da revisão de código (vigentes)

- `EncodeFailure.MEMORY` é fatal, assim como PROTOCOL/DEADLINE; TYPE/LIMIT
  são recusas validadas e só permitem continuidade se o worker comprovar
  conexão íntegra. OOM não é um limite de tamanho legítimo. Validador D-113
  preserva sua categoria pública LIMIT, adicionando somente bool interno
  `memory_exhausted`, marcado nos catches de OOM existentes; o encoder usa
  esse fato para classificar também OOM na autovalidação como MEMORY.
  Receptor D-114 mantém sua classificação anterior e continua drenando na falha.
- Metadados: AttributeError/OID fora do perfil recusam antes do fetch;
  MemoryError é recriada sem args/contexto, fatal; falha inesperada, divergência
  posicional ou DTO inválido são DatabaseResultIntegrityError, não recusa
  recuperável. Worker futuro deve capturar Integrity e MemoryError ANTES de
  DatabaseError. Não tratar toda subclasse de DatabaseError como recuperável.
- Limites de contagem e prazo são checados antes de percorrer a revalidação do
  DTO. Work counter de 256 unidades; texto longo confere cada bloco de 4096
  caracteres. Texto curto usa o contador no primeiro bloco, evitando uma chamada
  de relógio por célula. Prazo cooperativo, não preempção ou prova de quota.
- `ResultLimits.max_rows` do worker deve vir dos settings da geração capturada,
  nunca de default separado ou do cliente. BaseException interrompendo o codec
  é fatal para o worker; traceback/ownership não comprovado exige encerramento,
  não reutilização ou liberação otimista de créditos.
- Domínios cujo OID o servidor anuncia como tipo base são aceitos/codificados
  como esse tipo base. Domínio text foi observado como OID25 no
  PostgreSQL16.15/psycopg3.3.4; OID próprio de domínio anunciado fora da tabela
  é recusado. Não se promete detectar todos os domínios ou preservar OIDs
  arbitrários, nem se generaliza a observação para outros perfis.

A primeira execução integral foi interrompida deliberadamente a 6% após o
finding de classificação de OOM, para aplicar a correção sem misturar fontes;
processos próprios e conexões conferidos encerrados. Não conta como gate verde.

A primeira rodada integral terminada reprovou a guarda da API pública:
**1 failed, 6.394 passed, 20 skipped em 6.415 testes**, 830,80 s.
O nome originalmente público do método opt-in ampliava `dir(adapter)`.
Corrigido para `_execute_typed_validated`, **sem alterar a allowlist ou o
teste de proteção legado**. `_` preserva o contrato, não é sandbox.
Os 60 testes de leakage/tipagem passaram e o Claude2 revisou o ajuste sem
bloqueador. Nova rodada integral sobre fontes congeladas: **6.395 passed,
20 skips de plataforma, zero falhas/erros em 6.415**, 859,26 s, sem skip DSN
ou deselect. Integração tipada 12/12 executou/passou; evidência própria.

## Ajuste de desempenho medido, sem ampliar limites

A primeira prova densa com 3.200 linhas × 1.024 células de texto curto
atingiu o deadline fixo de 40 s: **1 failed, 372 passed** na rodada relacionada.
O diagnóstico mediu cerca de 9,57 s de preflight e 13,78 s de validação; não
se atribuiu a falha a ruído nem se aumentou o prazo. O caso nulo passou.

O encoder agora evita conversões intermediárias/chamadas redundantes para
ASCII curto, sempre em blocos de no máximo 4.096 caracteres. O D-113 valida
texto de até 4.096 bytes num bloco limitado, com UTF-8 estrito e recusa de
NUL; um byte tem caminho ASCII exato. Texto maior mantém o decoder
incremental. O contador cooperativo de 256 unidades continua ativo por
célula/operação; não há remoção da autovalidação final nem prazo renovado.

A regressão compara todos os 256 valores de um byte e limites UTF-8/NUL
ao redor de 4.096 bytes com a decodificação estrita independente do Python.
Nova rodada relacionada: **403 passed**, 36,55 s; o caso denso curto passou
em 19,11 s e o nulo em 11,63 s. É medição de disponibilidade neste host,
não teto de tempo universal ou contenção física. Claude2 revisou a alteração
antes do freeze, sem bloqueador isolado; reforços e prova Unicode também
passaram (408 relacionados, detalhes na evidência). A suíte integral final
usa esse código funcional congelado.
