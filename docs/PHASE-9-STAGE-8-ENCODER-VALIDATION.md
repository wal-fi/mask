# Etapa 8 — pipeline tipado e encoder de resultado já mascarado (D-115)

**2026-10-20: lote interno implementado e validado localmente sob delegação,
com revisão somente leitura do Claude2 e suíte integral final verde. Não é
worker, fechamento de B-1/B-2/D-090, liberação de SQL ou produção.**

## 1. Escopo, ambiente e revisão

Plano: `PHASE-9-STAGE-8-ENCODER-PLAN.md`. Claude2 revisou somente leitura na
sessão `8c333756-5a6d-4115-883d-7bcac5c7d519`: contrato antes do código,
taxonomia de falhas, código/testes e otimização posterior. Não executou testes
nem aprovou produção. O único escritor foi esta conversa; sem aval individual
fictício de decisões. Nenhum segundo escritor, commit ou push.

Windows nativo, CPython **3.11.3** da .venv existente, sem recriação; pytest
9.1.1, psycopg 3.3.4, pglast 8.4, Ruff 0.16.5, mypy 2.3.1, build 1.6.1.
PostgreSQL **16.15** em `postgres:16-alpine`, container descartável próprio,
porta aleatória publicada só em 127.0.0.1. Senha aleatória só no ambiente
dos testes, não em argv, documento ou arquivo do repositório. Nenhum banco
informado pelo usuário foi acessado. Docker Desktop estava parado e foi
iniciado para este lote; remoção/restauração conferidas na §8.

## 2. Produto implementado e limites

- `db/result.py`: `TypedMaskedResult` frozen/posicional contém somente o
  resultado já protegido e OIDs **anunciados**, com tuplas estruturais;
  os tipos exatos das células são conferidos no preflight. Tabela imutável com
  oito OIDs, sem ampliar export público legado, ColumnDescriptor ou MCP.
- `db/postgres.py`: opt-in `_execute_typed_validated`, compartilhando análise,
  execução, proveniência, decisão, fetch/masking, limite e `_settle` existentes.
  Legado não passa a exigir type_code. Em MASK o tipo de origem nem é lido:
  saída text25. ALLOW/EXCEPTION conferem OID antes do fetch, inclusive NULL.
- `pgwire/result_encoder.py`: preflight fechado, bytearray do tamanho exato,
  escrita limitada, cópia imutável e autovalidação independente pelo D-113.
  Não monta coleção de células codificadas, não faz I/O, nem cria processo ou
  thread. Nenhum chamador operacional da API tipada ou do encoder.
- `result_frame.py`: somente sinal escalar interno de OOM e caminhos limitados
  de UTF-8 curto; categoria pública anterior preservada. D-114 continua
  recusando como LIMIT e mantendo ownership até close; o receptor não consulta
  `memory_exhausted`. Classificação de OOM no pai permanece contrato aberto
  da integração D-114/B-2. No worker futuro, OOM do encoder é fatal.

Wire privado v1 com header de 76 bytes e corpo T/D*/C; metadados de
tabela/atributo zero, typmod -1, formato texto. Subconjunto: bool16,
int2/4/8 (21/23/20), name19, text25, bpchar1042 e varchar1043. Inteiros e bool
exatos/distintos; texto UTF-8 estrito sem NUL; name até 63 bytes; duplicatas,
nomes vazios e NULL posicionais. MASK recebe str exato ou NULL, nunca
conversão genérica ou OID numérico com string mascarada.

Domínios cujo OID o servidor anuncia como tipo base são aceitos e codificados
como esse tipo base; a recusa vale para OID próprio anunciado fora da tabela.
Domínio text **apareceu como OID25** no PostgreSQL16.15/psycopg3.3.4 medidos;
não se generaliza para outros perfis ou se promete detectar todos os domínios.
OID desconhecido anunciado continua recusado, mesmo NULL. MASK normaliza
o OID, conforme §5.5 normativa; não promete
preservar o tipo original. Esta é a leitura esclarecida da §6.2 do desenho.

## 3. Falhas, fatalidade e ownership

Erro externo fechado, sem valores, SQL, OID, nome ou exceção nativa. Recusa de
tipo do adapter é `DatabaseResultTypeError`; estrutura/metadados incoerentes
são `DatabaseResultIntegrityError` (fatal). OOM ao ler metadata é recriada sem
args/contexto, não convertida em tipo não suportado.

Encoder: `EncodeError.fatal` é o critério de fatalidade que o worker deverá
usar, evitando outra tabela de categorias. TYPE/LIMIT são recusas controladas,
e só permitem continuar se a
conexão for comprovadamente íntegra. MEMORY/PROTOCOL/DEADLINE são **fatais**.
O worker futuro precisa capturar Integrity e MemoryError **antes** de
DatabaseError e nunca reciclar sessão fatal. Interrupção BaseException também
exige encerrar; traceback/ownership não comprovado impede release otimista.

O encoder limpa frames inativos e solta referências que possui ao reduzir
falhas; isso não apaga memória nem controla locals do chamador ou debugger.
Nenhum byte parcial é retornado. A entrada já materializada não entra no
cálculo 2F; o pai/receptor, libpq, AST, masking, SSL/nativa/compartilhada e
alocador/SO continuam no gate B-2.

Limites são anteriores à alocação: até 16 MiB no frame, 1 MiB por célula,
1.664 colunas e 256 bytes por nome. rows<=max_rows, truncated implica igualdade.
No worker, max_rows deve vir dos settings da geração capturada, não do cliente
ou de default divergente. Prazo absoluto cooperativo em blocos de até 4.096
caracteres/bytes e contador de 256 unidades, sem renovar por progresso ou
prometer preempção de C.

## 4. Histórico de falhas e regressões

Os testes das APIs novas tiveram inicialmente dois erros de coleta (RED).
A primeira rodada real de integração teve **1 failed, 58 passed, 10 errors**:
harness com fixture em escopo incorreto e estratégia `alnum` inexistente.
Corrigidos para fixture por função e `alphanumeric`, sem retirar asserts;
repetição **69 passed**.

Regressão de OOM na metadata: **1 failed, 12 deselected** antes do fix; quatro
estágios do encoder: **4 failed, 55 deselected** (LIMIT ou PROTOCOL em vez de
MEMORY fatal) antes do fix. Os asserts finais cobrem preflight, alocação,
cópia e validação. Esses deselects são seleções diagnósticas, não suíte integral.
A primeira suíte integral foi deliberadamente interrompida a 6% para corrigir
o finding e congelar fontes novas. Não é execução aprovada; os processos
próprios e suas conexões foram confirmados encerrados antes da nova rodada.

A primeira rodada integral terminada deu **1 failed, 6.394 passed,
20 skipped em 6.415 testes**, 830,80 s, exit 1. Falha:
`TestPublicApiSurface.test_adapter_exposes_only_the_allowed_names` em
`test_db_leakage.py`; o nome público novo ampliava a superfície do adapter.
Fix: método agora privado `_execute_typed_validated`, sem ampliar allowlist,
export ou alterar o teste legado. `_` é contrato interno, não barreira de
segurança. Leakage/tipagem: **60 passed**; integração privada real:
**12 passed em 1,17 s**. Claude2 releu o fix, sem bloqueador isolado.
A repetição integral passou (resultado na §5); a rodada reprovada permanece
preservada no JUnit `final.xml` e não vale como gate verde.

Desempenho: caso denso 3.200×1.024 textos curtos falhou no deadline fixo de
40 s: **1 failed, 372 passed** relacionados. Perfil: ~9,57 s de preflight,
~13,78 s de validação, ~39,99 s até a recusa. Não se alteraram prazo, tetos
ou autovalidação. Otimização ASCII/UTF-8 em blocos limitados foi revisada.
Primeira repetição: **403 passed**, texto curto 19,11 s, NULL 11,63 s.
Depois dos reforços da revisão: **408 passed em 71,40 s**, texto curto
22,71 s, NULL 10,81 s, Unicode curto 32,29 s (2.600×1.024 células).
São provas neste host; podem falhar por disponibilidade em hardware mais
lento. Não se promete teto universal nem se calibra deadline ao ruído.

Cobertura adicional: fixtures binárias independentes completas, bytes exatos
nas fronteiras ASCII 4.096/4.097, UTF-8/NUL/surrogate, todos os 256 valores
de um byte no D-113, name/nome Unicode, zero linhas, truncamento, valores vazios
vs NULL, colunas/nomes duplicados, ints extremos, tipos hostis sem conversão,
preflight antes da alocação e OOM/erro depois dela com traceback salvo.

Medição complementar máxima em tracemalloc: frame de 16 MiB, entrada criada
antes, pico **<2F+512 KiB**, retenção de um F. Não é cota física ou memória
total do pipeline. O buffer mutável é descartado antes da validação final.

## 5. Banco real e gates

**12 testes novos de integração** passaram inicialmente sobre código anterior
às otimizações de desempenho; os 408 relacionados posteriores não incluem
esse arquivo. Depois, os **12 executaram/passaram sem skip** na primeira
rodada integral (reprovada pela API pública), já sobre o codec otimizado.
Após o rename privado, **12/12** passaram novamente na seleção isolada.
A repetição integral final executou/passou os **12 sem skip**, conferidos
individualmente no JUnit. A sonda instalada não substitui esses casos.
Casos: alias/exception autoritativa, AST-derived, nomes duplicados, HMAC,
regex/random, NULL, masked numeric→text, numeric não mascarado recusado
antes do fetch, domínio text observado, max_rows/excedente não mascarado,
mesma conexão, SELECT-only/read-only, statement_timeout e recuperação.
Erro operacional de catálogo foi injetado **no resolver após uma consulta
real**, não provocado por falha real de permissões no servidor. Todos os
oito loaders do subconjunto foram medidos no psycopg real, incluindo bpchar
com espaços, true e mínimos de int2/4/8. Sockets locais reais completam
encoder→receiver.

| Gate já terminado | Resultado |
|---|---|
| Encoder/validador/receptor relacionados | **408 passed**, 71,40 s, sem skips |
| Proteção pública original + tipagem, após fix privado | **60 passed**, 0,27 s |
| Integração tipada PG16, após fix privado | **12 passed**, 1,17 s, zero skips |
| Ruff check e format src/tests | **243 arquivos**, aprovados |
| Mypy strict alvos 3.11 e 3.14 | **243 arquivos**, aprovados |
| Suíte integral final, PG16 real, sem seleção/deselect | **6.415 total: 6.395 passed, 20 skipped**, 859,26 s |
| Integração tipada dentro dessa suíte | **12/12 passed**, zero skips/falhas/erros |

Exit 0, zero falhas/erros/xfail, sem skip por ausência de DSN. Os 20 skips:
**5 fsync de diretório POSIX, 9 bits de modo POSIX, 6 criação de symlink
indisponível** nesta instalação Windows. Não chamar todos de skips POSIX.
Um warning preexistente de pytest (`match=""`) em teste de lifecycle foi
preservado, sem correção fora do escopo. Pilha de thread de 64 MiB aplicada
somente ao processo de teste, sem setting novo ou alteração no produto.

JUnit final privado fora do checkout:
`%LOCALAPPDATA%/Temp/maskgw-encoder-gates-20261020-72f4c6b1/final-private.xml`,
SHA-256 `290ed76bbf01252d670f0befa261de0ca5e56a14d45d619925f6018754ca1275`.
Casos densos nessa rodada: NULL **9,010 s**, ASCII **14,108 s**, Unicode
**25,374 s**, todos sob os mesmos 40 s, sem ampliar limites.

Mypy 3.14 é alvo de análise estática no 3.11, não execução em CPython 3.14.
POSIX, runtime moderno e browsers/frontend não foram executados neste lote.
Código, recursos, testes e dependências de frontend não mudaram.

## 6. Pacotes — prova instalada limitada

Raiz temporária final:
`%LOCALAPPDATA%/Temp/maskgw-encoder-package-20261020-5c8e1394/after-private-api/`.
Builds sem isolamento/rede nem alteração da .venv; wheel direto e wheel
reconstruído do sdist extraído fora do checkout. **145 membros** do sdist
conferidos antes da extração (só regulares/diretórios, sem caminhos de escape
ou links); **119 entradas** em cada wheel, sem docs/tests/frontend,
.codex/.claude, stackdump ou systeminfo.

Instalação em dois targets novos com `--no-index --no-deps`. A sonda
`tests/result_encoder_package_probe.py` rodou de cwd temporário, `python -I -B`,
sem PYTHONPATH. Dependências vêm do interpretador existente: **não** é app
com dependências isoladas. Todos os módulos maskgw vieram do target instalado.

Nos dois pacotes: PostgreSQL16 real→proveniência/decisão/masking→DTO tipado→
encoder→socketpair/receptor→outro socketpair; frame de 160 bytes, OIDs int2/text,
original sintético ausente, apenas corpo validado entregue, pin retido até
close e depois limpo. Não é PGWire operacional, TLS instalado ou MCP E2E.
Uma primeira chamada de inspeção de archive falhou por quoting do comando
Windows; refeita com script multiline, sem mudança de produto.

| Artefato | SHA-256 |
|---|---|
| Wheel direto | `de45edb1c8ea30bbccd9ef73cb9533c7d705fd1ade76cdb926f90a60c4b45449` |
| Sdist | `1af47891424d7fd0a9a7171fc1b048073806c987d824b8e14eb6b6d502e09e90` |
| Wheel reconstruído do sdist | `7963dac30caec6e243839a11edaf3aa0a51b2ee225e8217305370a9b08949db2` |

Não há alegação de determinismo entre wheels. Os sete módulos abaixo tiveram
hashes conferidos iguais no checkout, nos dois wheels e nos dois targets:

| Módulo | SHA-256 |
|---|---|
| db/postgres.py | `170dafb9c792f113b8892a52b3a0c6603c98010004dac40983d729f6d1ca6081` |
| db/result.py | `adf586c7608acf2dd32e9e57d28844a439fc0362411ee3552f2eb12a2487c01b` |
| pgwire/result_encoder.py | `707e8431d0cd5d33f24fe43c5181086dc0eb894e0e02d01bf89a5f9e95436d4f` |
| pgwire/result_frame.py | `0a83171ff85b2ea01b1fd55d1e1213328a640adf53b1750b756a7f361a156778` |
| pgwire/result_receiver.py | `730c6c8e2cf7f1df6b4ef0f02325e0927ddaa173cf0689eaba54e6eb4c652495` |
| pgwire/transport.py | `2ae86fe27b288d59d1f6d7e8c63113e1188152b14ec16ae664e4c07f64115444` |
| runtime/budget.py | `510ca741cac660afb33ce5ae97da2685f472ebcac36e90dc8cd94fd2dcf1ed7e` |

Os primeiros pacotes, anteriores à correção da superfície pública, continuam
na raiz temporária pai, mas não representam o produto final. Seus hashes:
wheel `e21d9dd921ad16fa623eea25dcfb8fb4df3a3e5eb554127b619fe3cddc9299ba`,
sdist `ded2ad91dc81708530b0b5c9ed6e27c8d0ba40386a07b848c60973bbc9b30005`,
wheel reconstruído `c9b12603bfd961da184cbaebfdb6e80c906609a750d3ffcda487a8fbd0d7fea4`.
As sondas e conferências de hashes foram repetidas nos dois pacotes finais.

## 7. Integração pendente

Nenhum worker, captura/lease no ingresso, SQL de cliente, listener novo,
configuração, dependência ou deploy entregue. B-1 fim a fim, B-2 e D-090
gate 2 continuam abertos. A sonda do encoder não integra orçamento físico,
seções compartilhadas, alocador, nativa ou SSL. Próximo trabalho deve fechar
o contrato de execução/isolamento real, não inferir segurança só deste codec.

## 8. Fechamento, limpeza e continuidade

Antes de remover o banco próprio: **zero outras sessões client backend** no
database descartável, excluída a conexão da própria conferência. Scan exato
da senha descartável em **27 XML/log/JSON próprios de até 8 MiB**: zero
correspondências. Não é varredura de todos os segredos ou do host.

Container próprio `3d2719cc...` removido por stop normal após conferência do
ID completo; `--rm` eliminou o banco/volume anônimo temporário. Inventário
Docker posterior: **zero containers**. Docker Desktop, inicialmente parado,
foi encerrado por `desktop stop --timeout 45`, exit 0. Conferência posterior
sem processos Docker Desktop, backend/build ou Python ativos. O comando de
status informa Desktop não disponível para consulta (parado), coerente com o
encerramento. Nenhum dado de banco existente foi alterado; os dados sintéticos
descartáveis não foram mantidos.
Relatórios e pacotes privados temporários preservados para auditoria.

Claude2 confirmou o fix privado sem bloqueador isolado, condicionado à nova
suíte verde e cleanup, agora medidos pelo executor. Não executou a suíte nem
aprovou produção. Guarda pública antiga permanece intacta e os hashes dos
pacotes finais correspondem ao código final. Escolha/fechamento sob delegação,
sem inventar aval individual do usuário.

Preparação independente do próximo lote, só documental e sem carga:
`PHASE-9-STAGE-8-CONTAINMENT-NEXT.md`, revisada na sessão somente leitura
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`. Permite preparar/revisar o harness,
não certifica contenção nem escolhe SO/destino de produção. Sem imagem nova,
worker ou SQL. B-1 fim a fim, B-2 e D-090 gate 2 seguem abertos.

Auditoria do freeze: **303→311 arquivos selecionados**, 14 alterados e oito
novos pertinentes (incluindo a proposta documental seguinte), nenhum ausente.
Fora desses 22, hashes anteriores preservados, inclusive guarda pública
original, lotes antigos, typing/snapshot/candidate, UI, dependências e testes
não abrangidos. .venv/pyvenv.cfg idêntico. HEAD `4a5e5560...`, referência
origin/master **local, sem fetch** `5d173ea9...`, 1 ahead/0 behind, sem
index.lock. Arquivos pessoais não rastreados preservados. Sem commit/push;
suítes não repetidas após os últimos ajustes exclusivamente documentais.
