# Etapa 8 — resultado limitado em bytes no pai

**2026-10-20: escolha sob delegação, plano revisado pelo Claude2 antes do código.
Lote puro, sem chamador operacional, worker, SQL, socket ou dependência nova.
Não fecha B-1 fim a fim, B-2 nem D-090 gate 2.**

## 1. Escolha e fronteira

Trocar a representação proposta de objetos de linhas/células no pai por um
frame completo imutável, cujo corpo já contém as mensagens PGWire textuais
`RowDescription`, `DataRow` e `CommandComplete`. Validar integralmente antes
de expor qualquer fatia para envio. Não decodificar resultados em listas ou
strings proporcionais. O worker futuro codificará **somente após** o engine;
o validador não prova sozinho que houve masking ou geração correta.

É alteração explícita da representação das §§6.4/10.3 do desenho da Etapa 8,
não da semântica do masking nem do subconjunto de tipos da §6.1. D-113 será
registrada após revisão técnica, sob delegação, sem inventar aval individual.
Módulo: `pgwire/result_frame.py`, sem export no `__init__`, nem
import pelo listener/registry/gateway/bootstrap. Não introduzir transporte.

## 2. Formato privado v1

Header binário network-order de **76 bytes**, `!4sBBH16s16sQQQIII`:

| Campo | Regra |
|---|---|
| magic / version | `MGWR` / 1 exatos |
| flags / reserved | só bit 0 (`truncated`); reservado 0 |
| session / datasource | 16 bytes cada, iguais à identidade esperada do pai |
| generation / record_revision / job_id | inteiros 1..2^63−1, iguais aos esperados |
| columns / rows / body_bytes | contagens e comprimento exato do corpo restante |

Identidade é correlação com trabalho pendente, não autenticação de código
malicioso. A autorização/lease e snapshot são gates posteriores separados.

Corpo: exatamente **um T**, **rows mensagens D**, **um C**, sem bytes extras.
Cada comprimento de mensagem PGWire inclui seus quatro bytes, não o tag.
Antes de unpack, frame entre 76 bytes e seu teto; body_bytes igual ao resto.
Cada mensagem tem comprimento pelo menos seu mínimo e no máximo o restante;
campos terminam exatamente no fim declarado. Counts/formato de 16 bits são
lidos como `H` e conferidos contra os limites (0xffff não é aceito como −1).
Nada de Error/Notice/ReadyForQuery no corpo: status e erros serão controlados
pelo driver, não aceitos como mensagem arbitrária do worker. Truncamento só
é válido com rows igual a max_rows; rows nunca excede max_rows. O NOTICE
futuro sairá depois do C e antes do ReadyForQuery, não é implementado aqui.

- T: contagem igual ao header; nomes UTF-8 válidos de 0..256 bytes, terminados
  em NUL; duplicatas válidas. Sem objeto/string de nome retido. `table_oid=0`,
  `attribute=0`, `typmod=-1`, formato texto 0. OIDs e typlen fechados:
  16/1, 21/2, 23/4, 20/8, 19/64, 25/−1, 1042/−1, 1043/−1. O caso name/64
  é perfil PostgreSQL padrão, não certificação de build customizado. typmod
  −1 normaliza deliberadamente varchar(n)/bpchar(n), sem alterar seus valores.
- D: mesmo número de colunas. Tamanho −1 é NULL, nenhum outro negativo;
  zero é texto vazio (só tipos textuais). Conferir tamanho antes de avançar.
- C: tag exato `SELECT <rows>\0`, decimal canônico, inclusive `SELECT 0`.

Limites internos injetados/validados: frame completo até 16 MiB (incluindo
header), célula até 1 MiB, 1..1.664 colunas, nomes até 256 bytes e max_rows
positivo finito de até 2^31−1. Os tetos não viram setting operacional neste
lote; não há zero=infinito. Antes do loop de linhas, validar o mínimo
estrutural `rows × (7 + 4 × columns)` e o CommandComplete contra bytes
restantes. Não alocar a partir de rows×columns ou de comprimento declarado.
Antes dos metadados, conferir o mínimo T de 7 + 19 × columns. SQL de zero
colunas é válida no PostgreSQL, mas o worker futuro a recusará como erro
controlado, não a emitirá como frame malformado para matar a sessão.

## 3. Valores e validação

Mesmos OIDs do primeiro subconjunto da §6.1. Colunas mascaradas serão text
25 no worker; o pai não infere política a partir do OID. NULL é aceito em
qualquer tipo aprovado. Outros OIDs (inclusive OID próprio de domínio)
ou formatos binários recusados. Esclarecimento D-115 posterior: se o servidor
anunciar um domínio como o OID do tipo base aprovado, ele é aceito/codificado
como esse tipo base; foi observado domínio text→25 no PG16.15/psycopg3.3.4.
Não é detecção universal de domínios ou preservação de OID arbitrário.

- Textuais: UTF-8 estrito, sem NUL no valor; name (19) até 63 bytes. Isso é recusa do codec, não
  mudança da regra/transformer; uma saída do transformer contendo NUL será
  recusada inteira, nunca passada crua como fallback.
- Inteiros: ASCII canônico, no máximo 20 bytes, sem `+`, espaços, zeros
  iniciais ou `-0`; faixa do OID conferida antes de crescer acumulador.
- Bool: só `t` ou `f` exatos.

Validação UTF-8 incremental estrita em blocos de até 4 KiB: recusar overlong,
continuation solta, truncamento, surrogate e codepoint acima de U+10FFFF,
inclusive nas fronteiras do orçamento de trabalho. Usar decoder incremental
da stdlib, final=True no fim da célula; string transitória por bloco de até
16 KiB, descartada, nunca lista/str da célula inteira. Sem regex/recursão ou
decode do frame inteiro. Tabela de OIDs de tamanho fixo por validador (até
6.656 bytes), não objetos por célula. OIDs e demais escalares são limitados.
O decoder pode copiar bloco + até três bytes de carry (4 KiB + 3), custo
transitório fixo; não é alegação de validação sem nenhuma cópia.

## 4. Ownership, custo e prazo

Aceitar apenas `bytes` exato como frame completo, não bytearray, memoryview
de dono mutável ou subclasse. Retornar descritor selado interno com referência
ao mesmo bytes e offsets; repr sem conteúdo/identidade. Fatias de saída são
memoryviews somente leitura do **corpo**, nunca do header privado. A referência
`.obj` de uma memoryview mantém o frame inteiro, incluindo header; não é
ocultação contra introspecção Python. Só a fatia será enviada pelo futuro
driver, nunca `.obj`. Não copiar o payload a cada chunk.
A integração futura precisa reservar **antes de ler**:
buffer de recepção F + cópia imutável F + scratch fixo + envio/TLS e demais
custos. `P_i >= 2F + custos` neste caminho, não apenas len(frame); 32 sessões
com F=16 MiB exigiriam pelo menos 1 GiB só para os dois buffers máximos.
Não é prova do SSL, allocator, arenas retidas, worker ou memória total.

Somente comprimento válido é exposto; sem reuso durante validação/envio.
O bytes mantém dono até terminar o cliente lento. Liberação no ledger real,
buffers de recepção, custos nativos e integração ainda não implementados.

Prazo absoluto de validação recebido do chamador, sem renovar: relógio
monotônico injetável, leituras finitas; verificar antes/depois e a cada
4 KiB de texto ou 256 unidades estruturais. Não é preempção de chamada C,
nem prova de teto absoluto sob falha do SO. Fatias até 64 KiB; prazo de
escrita separado conferido a cada solicitação de fatia. Sem I/O no módulo;
a escrita real futura precisa impor seu próprio timeout, não abandonar thread.

Erros fechados de protocolo/limite/identidade/prazo, sem payload, mensagem
original, cause ou logging. Memória/falha do relógio recebem erro fixo fora
do except; a supressão não promete remover contexto já ativo no chamador.
Exceção não guarda offset/valor/OID; descritor não tem atributo público de
payload/header, somente metadados escalares e fatias do corpo validado.
Sem depender de asserts para validar entradas. Não é fronteira de isolamento
contra código Python hostil no próprio processo.
Tracebacks retêm frames/inputs no Python: a integração futura deve registrar
só categoria, nunca locals/traceback com dados, e soltar erro, resultado e
todas as views antes de devolver reserva. Sanitizar args não libera memória.

## 5. Aceite do lote puro

Testes independentes montam frames com struct, não com encoder do módulo.
Positivos: todos os OIDs/faixas, NULL/vazio, Unicode completo, nomes repetidos,
zero linhas, truncamento coerente e limites inclusivos. Contraprovas: cada
campo do header/identidade, comprimentos/truncamentos/bytes extras, contagens,
produto de dimensões, metadados, formatos, célula/frame, valores e UTF-8 em
fronteiras, prazo, buffer mutável, reuse e ausência de vazamento em erros/repr.

Sink falso só recebe fatias depois de sucesso integral; recusa não escreve.
Isso testa a API pura e não comprova o futuro driver. Fixture válida de
16 MiB criada **antes** da medição; tracemalloc de validação+iteração sem
cópia com teto complementar predeclarado de 512 KiB. Contraprova de cópia
integral deve ultrapassá-lo. Não equivale a medição de commit/nativo/SSL.
Provar ausência de import operacional/side effects por análise e import
isolado. Ruff, format, mypy 3.11/3.14 e regressões proporcionais; execução
3.14/POSIX, pacotes, banco e E2E são gates posteriores, não presumidos.

Após revisão do plano, implementar, testar e revisar o código pelo Claude2,
corrigindo findings antes de integrar/publicar. Não pedir aval por lote nem
declarar produto pronto por este núcleo. B-2 e D-090 gate 2 permanecem abertos.

Referência de framing: [PostgreSQL 16 — Message Formats](https://www.postgresql.org/docs/16/protocol-message-formats.html).

## 6. Revisão antes da implementação

Claude2 leu o plano inteiro e as seções relevantes do desenho, somente
leitura, sessão `c8815a75-8bf1-4f41-a57a-07bd5b3a7cb8`. Confirmou formato,
mínimos estruturais, tipos, custo 2F e viabilidade do núcleo puro; seis
correções mínimas foram incorporadas acima (rows, consumo por mensagem,
counts H, zero colunas, UTF-8 por blocos, typmod/name). Sem bloqueador de
arquitetura para implementar após esses ajustes. A revisão não executou
testes nem aprovou produto/integração, que continuam com gates abertos.

Na implementação foi escolhido o namespace `pgwire/` em vez de `runtime/`:
o `runtime/__init__` existente importa registry/psycopg/socket/ssl, enquanto
o `pgwire/__init__` é puro. Isso mantém import normal do novo módulo
estritamente stdlib sem refatorar exports existentes; API/formato/custos
não mudam. A decisão de localização será incluída na revisão de código.

A revisão do código encontrou o núcleo sem bloqueador, mas pediu três
reforços de teste: OIDs distintos na mesma linha e troca de posições,
separação de imports também por token relativo/dinâmico e categorias de erro
explícitas. Foram acrescentados, mais mutações profundas de frame válido,
fixture densa de 65.536 células e OOM de scratch. Código não mudou após essa
revisão; testes e evidência final passam por rerevisão.
