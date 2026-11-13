# W1 Oracle: revisão dos primeiros oráculos do chamador host

## HT5 — reparação revista; RED4 comportamental congelado antes da fonte V2

39794 terminou exit0/success/is_errorFalse, sem denials; recuperada.
Root leu TODO delta V2→V3; 56 nós de função/classe anteriores inalterados.
As cinco funções alteradas seguem HT4; quatro funções novas cobrem HS2.
H11 agora enumera todos os processos e disposições com unicidade, paridade
exata e conclusão local; H1 e H9 permanecem idênticos. Nenhum motor real
foi substituído. Ruff format não mudou bytes e a AST é igual.

Teste e3ef77375d03ffc5eddddd0412c726edea1ca8a45dced3c03f80d872882e4c97,
49.697 bytes, 1.173 linhas. Ruff/format/mypy strict win32 3.11/3.14 PASS;
3.14 somente estático. Medição: 60 casos, 56 PASS/4 FAIL AttributeError,
0 erros/skips, 2,489 s. Root leu os quatro textos; são precisamente HS2.
A mesma sonda independente confirmou RED4; 149 textos protegidos intactos.

frozen-host-run-red60.json congela estes oráculos e os dois probes antes
de qualquer fonte V2. A fonte V1 5f1e9c permaneceu byte a byte fixa na
reparação e na medição. O freeze original 69545074/RED56 continua histórico
e precedeu V1; ESTE novo freeze é posterior a V1, anterior à correção V2.
Não apagar resultados anteriores nem alegar outra cronologia.

Próximo somente corrigir fonte conforme HS2 e recuperar tipagem, com este
teste/probes e upstream FIXOS. Integração/publicação conjunta só após QA
verde revista; nenhum teste parcial publicado. Nativos/produto OPEN.

## HT4 — reparação de oráculos inválidos comprovada; fonte V1 HELD

A integração V1 revelou7falhas. Root não vai alterar fonte para satisfazer
expectativa inválida. Contraprova independente sobre ProHarness/public APIs
CONGELADOS,SEM fonte host_run para essa atribuição:

- pt._pump_namespace retorna dict;vars(dict) levanta TypeError. Lookup direto
  devolve o MESMO helper cuja identidade de código o witness deve conferir.
  Cinco falhas decorrem das3ocorrências dessa expressão no teste.
- Sem auditorias (STATE no relógio parado),o cenário tem14SPAWN/CHILD;
  o close_all_settled já congelado confirma14closes e TODOSRELEASED_LOCAL.
  Exigir>=15 nesse cenário é um número inventado,distinto de H1 com audits.
- A AST atual procura Call(Attribute(...seal...)),mas seal é bound-method
  passado ao guard. Isso não é falha de execução. Root leu source842linhas
  e verificou a ordem real;H1/H9 também a exercitam. Linhas entre corpos
  de helpers não formam uma prova de ordem de execução.

Medições em host-run-review-findings-initial-red.json. Corrigir SOMENTE
 tests/test_oracle9_w1_host_run.py,pelo mesmo C2/sessão/Opus5.5/medium,
com fonte5f1e9cb HELD/imutável durante esta reparação:

1. Trocar SOMENTE as3expressões vars(pt._pump_namespace()) pelo dict
   pt._pump_namespace(),mantendo acesso _bind_over e TODO witness/assert.
2. H11:substituir o mínimo arbitrário por propriedade MAIS FORTE:enumerar
   TODOS os processos do owner,exigir um CLOSE_HANDLE aceito por processo,
   parent/ids únicos,protocolo SUCCEEDED,parent RELEASED_LOCAL,contagens
   exatas e nenhuma tentativa extra. Assim nenhum processo pode faltar
   mesmo com o número real14;H1 continua com seu>=15 e todos seus asserts.
3. H16:preservar TODO forbidden-import/while/TERMINATE/REMOVE/bind/seam.
   Remover só a falsa comparação de linhas globais para execução indireta;
   pode reconhecer Attribute de seal/settle/begin_audit/begin_dispose/close
   como referências estáticas,sem ditar chamada direta. Ordem é provada
   pelos REGISTROS em H1 e fence atualizado em H9,não por posição de helper.
   Não remover esses oráculos comportamentais nem afrouxar sua lógica.
4. Acrescentar os4casos de admissão de HS2 como regressões pela API pública,
   primeira ação ainda host_run_module(). Apenas carriers OWN com slots
   públicos ausentes via object.__new__/__delattr__,como raw_windows;nenhum
   engine/módulo real ou estado privado alterado. Esperado:refusa apropriada,
   zero bind,custódia inválida sem escrita,input inválido claim+report.

O freeze69545074 fica preservado como histórico ANTERIOR à V1. Este reparo
não muda o contrato para caber na fonte:vars(dict),contagem e AST são erros
comprovados nos oráculos;os4novos casos devem ficar RED contra5f1e9c.
Root relê TODOS os deltas,mede RED4 com fonte V1 FIXA e re-congela sob NOVO
hash ANTES de qualquer correção V2 da fonte. Não alegar que o novo hash
precedeu a criação V1 ou apagar resultados antigos. Nenhuma implementação
ou fonte/testes upstream deve mudar nessa chamada. Publicação só conjunta
após integração verde revista,sem teste parcial ou candidato reprovado.

## HT3 — V2 revista; RED56 congelado antes da fonte

70323 TERMINAL exit0/success,is_errorFalse,sem denials;recuperada. Root leu
TODO delta após ler toda V1;56nós de função/classe inalterados por AST.
Snapshot V2ae9bde9c preservado. Ruff mecânico com AST igual resultou
695450741ed6d6b908327ee25504a594090d0d3985cbd61b4d69cb14376dae78,
46254bytes/1099linhas. Todos os asserts anteriores preservados,ordem de
registros e snapshot pré-bind reforçados somente nos dados próprios do teste.

Ruff/format e mypy strict win32 311/314 PASS;3.14 só estático. RED final:
56casos,1sanidade PASS/55FileNotFoundError pela fonte AUSENTE,0erros/skips/
deseleções,6,822s. Root conferiu TODOS55textos;só ausência do módulo. Mesma
sonda fc7a4646 dos fixtures passou5/5 sem alterar seu código.149textos
anteriores protegidos intactos;teste/probe adicionais agora congelados.
frozen-host-run-red56.json registra a sequência,não comportamento de fonte.

Fonte host_run AUSENTE neste congelamento. Próximo SOMENTE implementar
 docs/poc/oracle9_w1_host_run.py pelo mesmoC2/sessão/Opus5.5/medium,
Read/Edit/Write só esse novo módulo,sem comandos. Testes/probes/DTOs e todo
upstream FIXOS. Root lê TODA fonte antes de executar QA;H14 não testa
validação de done_outcome/conjunção em run_host,que deve ser conferida
explicitamente em HR5/source-review. Não declarar essa cobertura inexistente.
Fonte+teste congelado só publicar juntos após integração verde revista;
nunca publicar só o RED como suíte verde. Nativos/produto OPEN.

## HT1 — V1 integralmente lida; RED inicial não congelado

29652 terminou exit0/success,is_errorFalse,sem denials;terminal recuperado.
Zero novos/próprios escritores confirmado após término. Root leu TODAS
1022linhas/42088bytes da V1 1061ef3c460525bdd5c07c09f5e7a5c3b5aea5d67ca963d7b5af1d2fc237d80c
ANTES de executar QA. Fonte host_run continua AUSENTE;nenhum RED congelado.

Medições iniciais Windows3.11.3/pilha QA64MiB:55casos,1sanidade PASS e
54FileNotFoundError pelo módulo ausente,0erros/skips,5,496s. Todos54textos
conferidos;só ausência do módulo. Mypy strict win32311/314 PASS;3.14 estático.
Ruff:1diagnóstico C420 na linha540;format-check FAIL. Não é suíte de fonte
verde nem prova nativa. Snapshot e medições brutas preservados.

Sonda independente root sobre o ProHarness CONGELADO,sem carregar/criar
host_run e sem mudar produto:testou os fixtures propostos,5/5 PASS.
Relógio tick permite CompleteCandidate/auditoria;congelado recusa STATE;
stdin tardio muda fence None->assentado e admite auditoria;spawn falho
produz SPAWN/UNKNOWN;plano sem scope produz PLAN. Resultado em
host-run-fixture-assumptions-v1.json;script próprio revisado integralmente.
Esses são fatos do MODELO existente,não do chamador futuro/nativo.

## HT2 — correções restritas antes de congelar oráculos

Mesmo C2/sessão51ea0d85/claude-opus-5-5/medium,Read/Edit/Write somente
 tests/test_oracle9_w1_host_run.py,sem comandos. Preservar todos os asserts
já corretos e todo código/teste/pin anterior;fonte continua AUSENTE.

1. Corrigir C420 no objeto alheio usando dict.fromkeys(CUSTODY_FIELDS),sem
   alterar a condição de recusa. Root fará somente Ruff format mecânico,
   com prova de AST igual,depois da revisão semântica.
2. Fortalecer H1 com ordem de REGISTROS observada em runtime do modelo,
   além de AST:ids de work em fence antes dos ids AUDIT;e todos AUDIT
   antes de DISPOSE. Confirmar fechamento por registros/parent/estado,
   distinguindo tentativas aceitas e conclusões locais,não só contadores.
3. Acrescentar oráculo focado da captura única pré-bind:usar apenas cópias
   POR TESTE de owner_ns/pump_ns e o próprio HostRunInputs como dados de
   entrada. Binder devolve pump real sobre fakeSDK,mas antes de retornar
   altera os bindings dessas CÓPIAS e campos públicos do input de teste
   (p.ex.plan/windows) para sentinelas inválidas. O run deve continuar com
   as referências capturadas antes do bind. Não mexer em módulos reais,
   classes/funções do produto,Bridge/Reactor recebidos pelo owner,DTOs
   upstream ou estado privado. Não substituir motores por stubs. Para o
   próprio input frozen de teste,object.__setattr__ em campo público é
   equivalente à construção hostil de raw_windows já usada,não permissão
   para alterar estado de produto. Asserir uma chamada de bind e resultado
   positivo completo dos objetos capturados,sem reler entradas envenenadas.
4. No assert_report_shape,reactor_refusal não-None deve ser str EXATA além
   de pertencer ao conjunto fechado;não aceitar subclasses por igualdade.

Limitação reconhecida da V1:seam H14 não testa validação de done_outcome
nem a conjunção em run_host,pois não recebe result. Não afirmar essa
cobertura;continuará obrigação da fonte/avaliação posterior sob HR5.
Não criar outra seam/API ou substituir classe pública só para simular
resultado impossível pela composição real admitida. Manter essa ressalva
explícita nas evidências;nenhum requisito da fonte foi dispensado.

Root relê TODO delta antes de estáticos/sonda/novo RED. Não publicar teste
parcial ou congelar enquanto HT2 e os gates estiverem pendentes. Nenhum
produto/nativo liberado;N1–N16/T5/B1/B2/D090/C1/D119/TLS/ingressos OPEN.
