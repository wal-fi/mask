# Etapa 8 — núcleo puro de validação de resultado

**2026-10-20: implementado localmente, revisado pelo Claude2 sem bloqueador
no núcleo isolado. 293 testes novos aprovados; sem importador operacional ou liberação de SQL.
B-1 fim a fim, B-2 e D-090 gate 2 continuam abertos.**

## 1. Contrato e checkpoint

Escolha sob delegação do usuário, D-113 e
`PHASE-9-STAGE-8-RESULT-PLAN.md`. Claude2 revisou o plano antes do código,
sessão `c8815a75-8bf1-4f41-a57a-07bd5b3a7cb8`, somente leitura. As seis
correções mínimas foram incorporadas. A localização mudou para
`pgwire/result_frame.py`: import normal de runtime carregava registry/DB/rede;
o namespace pgwire permite o núcleo stdlib sem refatorar exports antigos.

Checkpoint sem fetch: `master`, HEAD
`4a5e5560abb495898c9e1b8ca44ac2d155681015`, referência `origin/master`
`5d173ea938eb12db33bc880bf67a2e81a208fd5e`, 1 ahead/0 behind. Freeze próprio
de **292 arquivos selecionados** no início, distinto dos anteriores. Preservar
working tree e não rastreados preexistentes; não incluir arquivos pessoais.

## 2. Implementação

- Header privado de 76 bytes, identidade esperada e contagens fechadas;
  corpo bruto PGWire T, D×rows, C com consumo exato antes de qualquer chunk.
- Limites prévios a unpack/cópias proporcionais, mínimo estrutural de
  dimensões, scratch de OIDs fixo; 8 OIDs e gramática/faixas textuais fechadas.
- UTF-8 estrito por decoder incremental e blocos de até 4 KiB; nomes
  posicionais, nenhuma lista de células/linhas ou decode do resultado inteiro.
- Bytes exato imutável, descritor de metadados/chunks sem repr de payload;
  chunks ≤64 KiB somente do corpo, com prazo de escrita separado.
- Falhas fixas de protocolo/limite/identidade/prazo, sem cadeia interna;
  falha de memória do núcleo/chunks também sanitizada. Prazo cooperativo,
  não preempção ou garantia de wall-clock sob falhas do SO.

Não existe ainda encoder de worker, leitura limitada antes de receber frame,
reserva real 2F+custos, socket/SSL, lease, geração capturada no ingresso,
execução de consulta ou garantia de masking por este módulo. SQL operacional
continua recusada com `0A000`. O cliente recebe bytes só na integração futura.

## 3. Testes e falhas preservadas

Fixtures montam bytes com struct, sem encoder do produto. Primeiro teste do
lote deu **um erro de coleta** pelo módulo ainda inexistente (RED da função
nova), não regressão de produto. A primeira implementação passou 272 testes.

A revisão própria adicionou quatro regressões **antes** das correções:
**4 failed, 272 deselected** na seleção `-k test_review`:

1. CommandComplete inválido com 8 MiB copiava o corpo declarado antes de
   recusar: pico tracemalloc de 8.397.247 bytes. Agora confere tamanho exato
   antes da fatia, que só pode ter até 18 bytes.
2. Inteiro de 1.001 dígitos no relógio/prazo levantava OverflowError em
   isfinite. Agora tipos/faixas são conferidos antes de conversão.
3. Deleção de slot privado podia mutar o descritor; agora __delattr__ também
   recusa, além de atribuição e construção pública direta.
4. MemoryError ao criar view de chunk escapava com mensagem original;
   agora é erro fechado levantado fora do handler.

Após correções: 276 aprovados. Testes adicionais de ordem/consumo, counts
0xffff, zero colunas, name/63, prazo no meio de célula e import isolado levaram
a **286 aprovados, zero falhas/skips**, em 0,78 s nessa rodada focada.
Inclui UTF-8 válido/inválido nas fronteiras, scalar canônico, limites inclusivos,
200 frames pseudoaleatórios reprodutíveis, erros sem canários, owner/reuse,
sink falso vazio em recusa e controles de alocação de resultado completo.

Claude2 apontou três lacunas de teste (não bloqueadores de código): OIDs
mistos por posição, separação de import também por token e categorias
explícitas. Foram fechadas, mais mutações profundas do corpo válido, 65.536
células pequenas sob o mesmo teto de memória e OOM de scratch, chegando a
**293 passed em 2,02 s**, zero falhas/skips. O módulo de produto não mudou
depois da primeira revisão de código; só testes/documentos foram reforçados.

## 4. Gates medidos

Windows nativo, CPython **3.11.3** existente; sem instalação/recriar .venv:

- Focado final: **293 passed**.
- Núcleo novo + orçamento/snapshot/pureza/separação: primeiro 909 passed em
  8,26 s; depois dos sete acréscimos, **916 passed em 9,82 s**,
  processo exit 0, sem falhas/skips.
- Ruff check e format de src/tests: aprovados, **233 arquivos**.
- Mypy strict de src/tests com alvos 3.11 e 3.14: aprovados, **233 arquivos**.
  Alvo 3.14 é análise estática, não execução nesse interpretador.

Medição complementar separada, mesmo código/fixtures, frame criado **antes**
de ativar tracemalloc:

| Grandeza | Bytes |
|---|---:|
| frame completo | 16.777.216 |
| corpo exposto em chunks | 16.777.140 |
| pico adicional de validação + iteração sem cópia integral | 16.917 |
| contraprova de cópia integral (bytearray) | 16.777.273 |
| CommandComplete inválido de 8 MiB, pico adicional após correção | 9.406 |

Os testes predeclaram teto complementar de 512 KiB; contraprova de cópia o
ultrapassa. Não são medições de commit nativo, SSL, buffer recebido, arenas
retidas ou contenção de memória total. Não se desconta o frame da reserva
futura: o chamador continua devendo 2F+custos antes de recebê-lo.

Nenhuma suíte integral com banco, PostgreSQL, Docker, frontend/browser,
execução CPython 3.14 ou POSIX neste lote. Não alegar esses gates com base
nos testes puros nem na análise mypy. A sonda de pacote da §6 é limitada.

## 5. Revisão independente e próximos gates

Claude2 leu código, testes, plano e D-113 na sessão acima, somente leitura,
sem outro escritor ou execução por ele. Após os três reforços, confirmou que
os pedidos foram atendidos e não encontrou bloqueador no núcleo isolado.
Contagens/gates foram medidos pelo executor, não reproduzidos pelo reviewer.
Não revisou este arquivo de evidência; seu escopo foi código/testes/contrato.
Fechamento técnico sob delegação, não aprovação individual inventada.

Mesmo seu fechamento não libera SQL/produção: faltam receiver e custos reais
no pai, código nativo/compartilhado/SSL, worker/captura/lease, mesmo pipeline,
fetch/transação e testes de produto. B-1 fim a fim, B-2 e D-090 gate 2 abertos.

## 6. Pacotes: apenas import puro e fixture pequena

Raiz nova `%LOCALAPPDATA%\Temp\maskgw-result-package-20261020-79e991c2`.
Wheel/sdist construídos com ferramentas existentes (`build --no-isolation`),
sem rede, Node ou nova dependência. O sdist foi listado/conferido e extraído
em diretório próprio fora do checkout, onde originou outro wheel. Cada wheel
foi instalado com `pip --no-index --no-deps` em uma venv temporária distinta,
sem alterar a .venv do projeto ou instalar Python no sistema.

De fora do checkout, `python -I -B` em cada venv importou o módulo instalado
e validou uma fixture sintética int4 com uma linha; oito chunks de até sete
bytes recompuseram exatamente o corpo, readonly. Sem psycopg/MCP/FastAPI/socket/
SSL carregados. Não é teste de aplicação instalada com dependências, servidor,
MCP, recursos UI, banco ou E2E. Dependências foram omitidas deliberadamente
para comprovar somente o isolamento stdlib deste módulo.

Ambos os wheels têm 117 entradas, exatamente um `pgwire/result_frame.py`,
sem antigo `runtime/result_frame.py`, docs/poc, testes, frontend ou arquivos
pessoais. O fonte instalado nos dois tem o mesmo SHA-256 do checkout:
`8068c3cc4b50024db9ff3a7a9c2ef7941fe8028a78cfc88555c33adb68892841`.

Hashes dos artefatos (não se reivindica determinismo entre builds):

- wheel direto: `867498632b05fb85006e23c9dc9e2e88d6d0a6b22a92fef497ec7f860d630d76`;
- sdist: `39f805166e489c4605600b133da32da461cb4e224331638123f3591a80fa77dd`;
- wheel reconstruído do sdist: `b32a8b1931d150ba9fed2d17ce0b1f202710d656a0104b690a63228a788fd75d`.

Hashes do lote de código/testes final:

- `pgwire/result_frame.py`: `8068c3cc4b50024db9ff3a7a9c2ef7941fe8028a78cfc88555c33adb68892841`;
- `tests/test_result_frame.py`: `4ca55ff083b3ee659de58887f5ca74206dc347ef8d7fc8aeb949310b614e5484`.

## 7. Conferência final do lote

Contra o freeze próprio de 292 arquivos, sete documentos existentes foram
atualizados, dois documentos foram adicionados e os únicos arquivos funcionais
novos são o módulo puro e seu teste. Nenhum arquivo removido; código/testes
anteriores, recursos UI, dependências e `.venv/pyvenv.cfg` mantiveram hashes.
Fontes final/revisado/instalado concordam; testes finais têm o hash acima.

UTF-8 estrito dos 11 arquivos do lote e `git diff --check` aprovados.
Documentos de estado distinguem o núcleo de receiver/worker ainda pendentes.
Depois dos gates, só documentação mudou; não se repetiu a suíte por edições
editoriais. Sem fetch, commit, emenda ou push; HEAD e referência remota local
continuam no checkpoint da §1, e não rastreados pessoais foram preservados.
