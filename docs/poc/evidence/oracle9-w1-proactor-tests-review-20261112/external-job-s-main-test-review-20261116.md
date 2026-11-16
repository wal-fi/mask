# Main S: revisão dos primeiros oráculos

## V5 — oráculos f8d congelados após RED102 medido

47382 TERMINAL0/success/is_errorFalse, sem denials, recuperada. Root leu TODO delta115linhas antes de QA. As sete funções de regressão (seis simples e uma com seis parâmetros) e o literal negativo independente permaneceram iguais em AST; positivos e fluxos dinâmicos não foram enfraquecidos. O controle de escritas agora considera todos os stores/deletes dos slots no handler, só aceitando as atribuições diretamente sob o guard de preservação. Fonte do main ainda AUSENTE.

Teste final f8d519e5cc839b10b713b1eceafbc1f37c5bf01cbdb07da69e5be9d2e5a416c3,75.589bytes/1.836linhas CONGELADO. Root leu1.296linhas originais e TODOS os deltas66/942/33/115.47sanidades PASS,15contraprovas AST independentes PASS nas expectativas, Ruff/format/mypy strict win32 alvos3.11/3.14 PASS em1teste;3.14 somente estático.

RED FINAL do arquivo inteiro, sem seleção/deseleção:102casos,47sanidades PASS e55FAIL EXCLUSIVAMENTE por ausência do fonte,0erros/skips,1,494s. Root conferiu CADA mensagem de falha exatamente como `Failed: docs/poc/oracle9_w1_external_job_s_main.py is absent (RED)`, antes e depois verificou fonte ausente e SHA do teste imutável. Recibo frozen-red-verified e snapshot local preservados; RED6 e RED-W6 históricos intactos. Esse RED não é bug de fixture/collection nem teste de produto.

Próximo único lote: mesmo Claude2 escreve SOMENTE o fonte novo `docs/poc/oracle9_w1_external_job_s_main.py`, Read/Edit/Write restritos, sem comandos/execução. Teste f8d, SM3 e TODA revisão SM-R4/R3/R2/R1/MB4/antigos/pins ficam READONLY. Cumprir a costura da MESMA AdoptionLoad, erro de carga fechado, controles e custódia/portas retidos, guard de reentrada/custódia, perfil NATURAL fixo por compatibilidade estática, fases/saídas/silêncio/park específicos. Não criar Owner/framework/host novo, não editar testes para obter verde. Root lê TODA implementação e confere frozen/pins ANTES de QA. Fonte e teste só serão integrados JUNTOS depois dos gates; não publicar o teste RED isolado.

Não executar main válido, park real, DLL/job/processo/thread/loop/Docker/PG/SQL/credencial/rede externa/deploy, nem ler runtime/config/ambiente/privado/binário/estado16/tentativa. SDK falso é evidência só do componente; native/product gates OPEN e Gateway indisponível.

## V4 — regressões de todas as escritas medidas; corrigir lote D

72666 TERMINAL0/success/is_errorFalse sem denials, recuperada. Root leu TODO delta33linhas:182nós anteriores idênticos em AST. Atual teste de7905ce94678e1436ea7bdeffcc256640a9b37becdf202fb35e93fbad46113a,74.192bytes/1.810linhas, snapshot local preservado. Root mediu47sanidades:41PASS,6FAIL esperadas nos seis parâmetros `root_extra_write`,0erros/skips. Todos os seis motivos são o classificador aceitando a segunda escrita incondicional. Recibo red-w6-verified. Ainda NÃO é RED final por ausência do fonte; teste NÃO congelado.

Próximo único lote D: mesmo Claude2 corrige SÓ o teste. Em `_records_first` e helpers específicos, validar TODAS as escritas do slot no handler, recusando a escrita extra que substitui o primeiro objeto, tanto para error quanto control nas três regiões. Conservar os dois grupos de regressões e os positivos; sem framework genérico. Não refazer loader ou outros fluxos já revistos. As seis funções root_regression e o novo teste parametrizado root_extra_write não podem ser enfraquecidos nem perder parâmetros.

Fechar também os gates já medidos em b489: SIM102 na dupla condicional `_first_test`/`_assigns` dentro de `_records_first`; type narrowing EXPLÍCITO de ast.Name em `_live_names` antes de `target.id`, sem cast/ignore; quatro pontos de formato: concatenação final de RUN_S_A numa linha com RUN_S_ERROR/RUN_S_CONTROL e assinaturas curtas de test_argv_outside_the_domain_exits_2_without_file_access, test_each_custody_guard_parks_before_entry_without_effect, test_wrong_request_type_with_fresh_custody_is_rejected_14. Nenhum comando/formatador pelo programador; Root executa checks após ler TODO delta.

Fonte fica AUSENTE. Nenhum gate nativo/produto ou fonte/teste/pin antigo muda. Só depois de contraprovas, sanidades e estáticos verdes será medido/congelado o RED final. Não declarar isso encerrado com base no retorno do serviço.

## V3 — B lido inteiro; fechar TODAS as escritas dos primeiros slots

79390 TERMINAL0/success/is_errorFalse, sem denials, recuperada. Root leu TODO delta942linhas antes de QA. Teste b48954e64ec325b04c260e2ffa7be9bfbf4b79c3b5b5abe5e45943c2d624bae3,72.661bytes/1.777linhas. As seis regressões anteriores continuam idênticas em AST; literal negativo independente preservado. As41sanidades passaram, incluindo RED6 anterior reparado, e os nove probes anteriores/positivos foram conferidos. Ruff ainda1SIM102 em330, format4locais e mypy311/314 ainda1erro: target.id em496 sem narrow de ast.Name.

O reparo ainda acha UMA escrita protegida e ignora outra escrita posterior fora dela. Root mediu a mesma família concreta nas três regiões: adicionar uma atribuição incondicional ao mesmo slot logo depois do bloco protegido. `_enter_violations`, `_main_region_violations` e `_region_a_violations` aceitam a variante tanto para first_error quanto first_control (seis falsos aceites). Recibo first-slot-extra-writes-red preserva os seis resultados sobre texto AST inerte; nenhum main sintético executado. Não é pedido de analisador universal: são as mesmas escritas dos slots cuja preservação o contrato já exige.

**Próximo lote C, único:** mesmo Claude2 edita SÓ o teste para ACRESCENTAR a regressão dessa família, parametrizada por região enter/main/region-a e slot first_error/first_control, seis casos. Usa os classificadores reais e fixtures atuais com inserção pontual; nomes incluem `root_extra_write`. Não corrigir helpers, fixtures antigas ou gates agora. Root mede as seis falhas com as41sanidades positivas e confere AST anterior antes do lote D.

**Lote D posterior:** depois do RED, corrigir `_records_first`/validadores para que TODAS as escritas do slot no handler obedeçam ao guard correto, não apenas uma delas. Preservar os objetos anteriores, não aceitar escritas extras que os substituam, conservar positivos legítimos e todas as regressões anteriores. Corrigir o SIM102, narrowing explícito de ast.Name sem cast/ignore e exatamente os formatos apontados. Sem refazer loader ou alterar semântica dinâmica já revista; sem novo framework. Root repete contraprovas/sanidades/gates antes de RED final. Teste ainda NÃO congelado; fonte continua AUSENTE.

## V2 — RED6 medido; agora corrigir SOMENTE teste

29677 TERMINAL exit0/success/is_errorFalse sem denials, recuperada. Root leu TODO delta66linhas. Os138nós de módulo anteriores continuam idênticos em AST; só seis funções de regressão e um literal independente foram acrescentados. Teste97d8c411d65462a46c6e0d12fe40d08e0d08f520f4ec3c3b5f1a56301284dfca,55.122bytes/1.362linhas, snapshot local preservado.

Root mediu seleção de sanidades:38casos,32PASS,6FAIL nas seis novas regressões,0erros/skips. TODAS as falhas são o classificador incorreto retornando lista vazia diante do AST defeituoso, não ausência do fonte, fixture ou collection. Recibo red6-verified registra os nomes e limites. Não é RED final da implementação; teste NÃO congelado. Fonte do main segue AUSENTE.

Próximo único lote B: mesmo Claude2 corrige SÓ `tests/test_oracle9_w1_external_job_s_main.py`: helpers/fixtures dos classificadores, gates Ruff/format/mypy e alinhamento direto do loader sob TODO SM-R4. Preservar as seis regressões fortes, o literal negativo independente e todos os assertions de segurança anteriores. Não alterar fontes/pins/testes antigos nem copiar/executar um main substituto. Conservar positivos significativos para as formas permitidas e negativos das famílias reproduzidas; não apenas rejeitar todo fixture ou reconhecer seu nome. Não ampliar para outro framework de análise genérico.

Corrigir também a fixture positiva MAIN_GOOD para registrar os primeiros objetos conforme o contrato. A fase A deve ter oráculo próprio das duas classes de falha/controle, guardando primeiros objetos e mapeando só recusa pré-entered para3. O fato de ler first_control/entered em algum lugar não prova direção nem preservação. Root repetirá contraprovas e lerá TODO delta antes de QA ou congelamento. Não executar comandos pelo programador, `_run_s` válido, main válido ou park real. Todos os limites e gates OPEN permanecem.

## V1 — teste7fe8 lido inteiro; ainda sem RED congelado

80442 TERMINAL exit0/success/is_errorFalse, sem denials, stderr vazio; recuperada. Root leu TODAS1.296linhas/52.228bytes, SHA7fe8f5cdfd747704ac4f3a2377f8118306140599000e6f87ea2267273e72054b. Uma saída de leitura foi truncada no meio; Root releu integralmente881–1296 em dois blocos menores antes de executar QA. Fonte do main continua AUSENTE. O teste permanece LOCAL, não congelado e não publicado.

Sanidades iniciais:32PASS,0falhas/erros/skips (seleção parcial, não suíte integral). Ruff:5findings; format recusou; mypy win32 alvos3.11/3.14:1erro em cada, linha964 Path(entry.__file__) ainda opcional. 3.14 só estático. Não alterar supressões para obter verde. Os resultados foram medidos pelo Root, não pelo programador.

### Findings reproduzidos por contraprovas dos classificadores reais

Recibo `external-job-s-main-test-initial-root-probes-20261116.json`. Root carregou só as definições do teste e passou textos inertes ao AST; não executou nenhum dos mains sintéticos. Três fixtures de referência foram aceitas, mas CINCO variantes incorretas também foram aceitas:

1. `_enter_violations` aceita inverter `custody.owner is not None` para `is None`. O classificador identifica o nome, mas ignora a direção/efeito do ramo de guarda.
2. O mesmo classificador aceita inverter a condição de retenção do primeiro controle da custódia. Presença do atributo não prova a proteção do objeto.
3. `_main_region_violations` aceita saída3 quando entered é True, invertendo o ramo que deveria reter recursos. Presença de entered em algum handler não prova a decisão.
4. `_park_violations` aceita atribuir None tanto ao parâmetro holder quanto à referência retained antes do laço. Uma leitura anterior de holder não prova retenção de referência até o fim da função.
5. O classificador do park aceita inner while False, com sleep sintaticamente presente mas inalcançável. Isso não é o park específico fechado.

Além disso, MAIN_GOOD atual não guarda primeiro erro comum nem primeiro controle. Não é fixture positiva válida do contrato completo, mesmo sendo aceita pelo classificador atual. Sua classificação precisa ser corrigida sem executar um main substituto. Os oráculos são uma prova parcial de forma, não um analisador universal ou prova física; corrigir essas famílias concretas, não inventar cobertura global.

### Ordem obrigatória da correção

**Lote A, único próximo:** mesmo Claude2 edita SOMENTE o teste novo para ACRESCENTAR seis regressões de sanidade AST: as cinco contraprovas acima e a recusa de main que perde primeiros erro/controle. Os cinco casos usam os classificadores reais e os mesmos textos inertes já definidos, com alterações pontuais. O sexto deve preservar como literal independente a forma sem slots, para não mudar de significado quando MAIN_GOOD for corrigido depois. Nomes de teste incluem `root_regression`; nenhuma nova implementação substituta é executada. Não corrigir helpers, fixtures positivas existentes, lint/format/mypy ou outros testes neste lote. Root verifica AST dos nós anteriores e mede as seis falhas antes de pedir o lote B. Não editar fonte ou contrato.

**Depois do RED dessas seis**, lote B corrigirá os classificadores/fixtures e os gates estáticos, sem enfraquecer assertions. Não basta procurar nomes em AST: fechar direção/retorno das guardas, forma de preservação dos primeiros objetos, ramo entered e retenção/espera do park. Não impor um único texto de implementação quando uma forma equivalente cumpre o contrato. Root repetirá contraprovas, sanidades e checks antes de medir/congelar RED final por ausência do fonte.

### Ambiguidade de carregamento — resolver antes de congelar

O programador relatou corretamente que os testes de recusa chamam `_run_s` com argv fictício válido, embora SM3 proíba `_run_s` válido. Não autorizar esse prefixo por analogia. No lote B, testar diretamente o loader sobre árvores temporárias e manter o mapeamento da fase A como obrigação estrutural, sem invocar `_run_s` com inputs válidos ou main válido. O contrato do erro privado do loader e os oráculos de controle precisam de precisão normativa do Root antes dessa alteração. Nenhum trap nativo deve ser considerado licença para atravessar um caminho proibido, nem uma AssertionError do trap pode contar como a recusa correta.

As interpretações declaradas pelo teste (`_inputs` retorna par exato; nomes de constantes compatíveis; `_load_entry` preenche adoption) são compatíveis com SM3, sob a revisão concreta. Isso não admite testar nem alterar o fonte. Sem fake Owner/fake entrada/patch de produto vivo, skip/xfail/cast/ignore/noqa/assert fraco. Fonte e todos os pins antigos ficam fixos; sdk só falso; native/product gates OPEN.
