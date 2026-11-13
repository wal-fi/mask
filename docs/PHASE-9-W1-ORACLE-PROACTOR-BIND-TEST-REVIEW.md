# W1 Oracle: revisão dos oráculos do bind

## BT5 ? or?culos finais revistos e RED45 congelado

8380 recuperada exit0/success, sem denials. ?nico delta V3: assert de
n?o-None movido depois dos checks din?micos e antes de now; root leu o
hunk inteiro. Teste final f6724a8f/19488bytes/483linhas. Ruff/format e mypy
strict win32311/314 PASS, com3.14 somente est?tico. Mesma sonda1eefc4af
inalterada:3sanidades originais PASS; mutante sem filtro falha na negativa.

RED final medido em Windows Python3.11.3/pilha QA64MiB:45casos,
3sanidades PASS/42KeyError('_bind_over')/0erros/skips/desele??es,1,540s.
Root conferiu TODOS42textos de falha; s? aus?ncia do helper.146textos
protegidos intactos. frozen-bind-red45.json registra o congelamento.
N?o ? comportamento aprovado, prova nativa ou su?te verde de integra??o.

Pr?ximo ?nico incremento de fonte: helper privado _bind_over + delega??o
m?nima do wrapper em docs/poc/oracle9_w1_proactor_pump.py, pelo mesmo C2,
sess?o51ea0d85/claude-opus-5-5/medium. Sem mudar qualquer teste, API p?blica,
enum, owner ou restante do pump. Root l? TODO delta e mede gates antes de
aceitar/publicar fonte+teste juntos. N?o publicar s? o teste RED. B4 de
BIND-REVIEW continua normativo; nenhum efeito/valor operacional preparado.

## BT4 — V2 semântica revista; resta apenas narrowing estático

11324 recuperada0/success. Root leu TODOS os deltas após ler toda V1;
17nós de função inalterados conferidos por AST. Ruff format mecânico com
AST igual:V2final68690d10/19488bytes/483linhas. A MESMA sonda1eefc4af
agora passa:3sanidades originais PASS e o mutante sem filtro reprova a
negativa. Matriz completa e contexto preexistente foram conferidos.
O modo is_running do fixture é resposta adversarial roteirizada do seam,
com close também roteirizado; não é prova de estado de loop/close nativos.

Ruff e format PASS. Mypy311/314 ainda têm os MESMOS2erros em now/close:
o assert não-None foi colocado ANTES das verificações dinâmicas de tipo/
handler, que voltam a estreitar pump para Any|None. Mover SÓ o assert
pump is not None para DEPOIS dessas verificações, imediatamente ANTES de
pump.now(), mantendo todos os asserts de tipo/handler/close e demais
oráculos. Não adicionar cast/ignore/supressão ou alterar fixture/probe.
Root revisa esse único delta e repete os estáticos antes de congelar RED.
Fonte/helper continuam fixos/ausente; nenhum novo finding de produto.

2026-11-13.39680 recuperada exit0/success, mesma sessão/modelo/medium,
sem denials. Root leu TODAS412linhas/16207bytes da V1
14dbf82c54a8525fb9caba66cba541a1e2824f4a2851d9129b7c178aaa6f7375.
Snapshot preservado; fonte0a4dcd57 e teste36b2ba54 intactos. _bind_over
continua AUSENTE. Nenhum oráculo aceito/congelado ou teste parcial publicado.

## Medições antes da correção

- RED inicial:22casos,3sanidades PASS/19KeyError('_bind_over'),0erros/skips,
  1,083s. Todos19textos conferidos. Ausência de helper não é prova
  comportamental nem reprodução nativa; NÃO congelado.
- Ruff:N818 em SyntheticFault; format-check FAIL.
- Mypy strict win32,3.11 e3.14:2erros iguais, pump possivelmente None nas
  chamadas now/close, linhas220–221. Nada de cast/ignore/supressão.
- Sondagem independente do WITNESS (nenhum helper de produto carregado):
  original3/3PASS; mutante sem filtro de identidade de código TAMBÉM3/3PASS.
  Ou seja, a sanidade não detecta exatamente o falsoPASS que B4 exige.
  Código1eefc4af8603983db521a51ed019a559f275c653b0b3a69ffe4b0c5c7b9dac4f;
  probe-bind-witness-filter-v1-red.json preservado antes do fix.

## BT1 — pôr o frame contaminante no traceback recebido

catch_any captura antes de a exceção atravessar o frame do teste. Assim,
este frame nem aparece no Throwable recebido. Manter known nele não
exercita o risco prometido. A checagem this_code → False, nas linhas133 e
344, é por ausência desse frame; não prova que o filtro funcione.

Fortalecer a sanidade NEGATIVA existente, mantendo as3sanidades: o erro
deve atravessar um frame de teste/caller que mantenha referência forte
ao objeto, e ser capturado de modo a preservar esse frame no traceback.
Exemplo de arranjo suficiente: try/catch dentro do teste chamando o
synthetic_drop diretamente, guardando o Throwable após o except. Não é
para implementar o produto nem mudar o witness correto para acomodar erro.

Provar primeiro que o frame contaminante está realmente presente. O
finder genérico recebe um code esperado: se passar de propósito o code do
teste presente, encontrar a referência é um positivo válido desse finder.
O check de RETENÇÃO deve passar o code do HELPER e continuar False quando
o helper apaga sua referência, apesar do frame contaminante. Não impor
recusa impossível de um code arbitrário que o próprio chamador forneceu.
Corrigir também o caso feature BD-7 de acordo com essa semântica.

Root repetirá o MESMO probe, sem mudar seu código: original3sanidades devem
passar e pelo menos a negativa deve reprovar quando o filtro for removido.
Nenhuma modificação do helper ausente, do teste congelado ou do probe.

## BT2 — completar os modos nomeados e preservar contexto preexistente

A tabela de fases vale para F2 e F3. A matriz atual cobre task-factory e
ident-Exception, mas não loop-running nem foreign-type cruzados com close
Exception/controle. Acrescentar esses dois modos nomeados ao arranjo, com
expectativa independente do ramo escolhido pelo próprio fixture. Não deixar
um else genérico transformar um fault nomeado num controle e ajustar
automaticamente a expectativa para ele.

Preservar primáriaC1 × closeC2 com identidade, uma tentativa explícita de
close e zero bool. Além de contextos None, acrescentar caso com contexto
sintético preexistente, criado pelo raise/catch normal do Python, sem
atribuição manual aos atributos do controle. Conferir que o MESMO contexto
continua, não só que foi apagado. Não usar SDK/sinais ou outro runtime.

## BT3 — estáticos sem enfraquecer os oráculos

SyntheticFault é nome privado de fixture, não API aceita: usar sufixo Error
para N818. No positivo, assert explícito de pump is not None é parte válida
do contrato e permite o narrowing antes de now/close. Não cast/ignore.
Root pode aplicar Ruff format mecanicamente com AST igual após a revisão
semântica. Não reescrever partes que já passam nem executar comandos.

Próximo só correção desse MESMO teste pelo mesmo Claude2/sessão/Opus5.5/
medium, Read/Edit/Write apenas tests/test_oracle9_w1_proactor_bind.py.
Root lê TODOS os deltas antes de repetir probe/sanidades/estáticos e medir
novo RED. Fonte/helper, teste135, probe0192ef43, owner/upstream/app124/
state16/attempt continuam FIXOS; sem native/Docker/PG/SQL/runtime/config/
privado/ambiente/binário, receita/valor operacional, outro escritor ou quota
workaround. Todos gates nativos/produto OPEN; Gateway indisponível.
