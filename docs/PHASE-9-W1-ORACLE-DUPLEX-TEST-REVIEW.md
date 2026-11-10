# W1 Oracle: revisão dos primeiros testes duplex

2026-11-10. Root revisor/QA, sob delegação. Claude2 é o autor dos testes,
sessão 51ea0d85-05bb-4d24-ba9a-c9627c3f832f, claude-opus-5-5/medium.
O desenho adotado é a V3 Gemini a78d1de1, obrigatoriamente com todo R8 de
DUPLEX-REVIEW. Não há fonte da ponte, prova nativa ou gate de produto fechado.

## Rodada V1 lida integralmente, ainda não congelada

CLI40524 encerrou0/success, sem recusas de permissão, em1646431ms. Root
confirmou zero escritores e leu todas as1791linhas/70435bytes do teste
cb5d50f448b1cc845fd25d2561c59563c5d37fdeedfa05da836b2a7018582108.
Só o novo teste foi criado; fontes/testes anteriores não mudaram.

Ruff e format passaram. Mypy strict alvos3.11 e3.14 apontou os mesmos
4erros: import implícito ht.d1; acesso category/reactor_refusal após
narrowing para Exception; comparação com ready_at que ainda permite None.
Sem ignore/cast/supressão: corrigir import e anotações/refinamentos reais.

RED inicial medido em Python Windows3.11.3, runner QA com pilha64MiB:
178casos,3sanidades PASS/175FileNotFoundFAIL/0erros/skips,33,797s.
Todas as175falhas são ausência da ponte; isto NÃO é prova comportamental.
Snapshot, saída íntegra comprimida, XML e resumo preservados em
docs/poc/evidence/oracle9-w1-duplex-tests-review-20261110/.

## Correções pedidas somente no novo teste, antes de congelar RED

1. Fechar os4erros de mypy sem enfraquecer asserções nem modificar fixtures
   congeladas. Importar explicitamente o módulo driver de testes, em vez
   de depender da reexportação implícita ht.d1. Refino de None deve ter
   asserção explícita antes da comparação. Nenhum comando pelo programador.
2. Binding: os cenários atuais recusam tipos do módulo/instância e estados
   já usados, mas não isolam as exigências de R8 para counts int exatos e
   tuple de25NOT_RUN. Acrescentar negativos para bool/float em counts,
   lista deverdicts e tuple com um verdict diferente. Usar instância real
   com seu status público temporariamente instrumentado pelo monkeypatch
   de teste, restaurado pelo fixture; não outro motor/fake de protocolo.
   Nenhum arquivo do reator ou teste antigo pode mudar.
3. Enqueue central no EOF:57linhas já enfileiradas durante write pendente
   mais parcial sem LF e EOF precisam falhar STDOUT_LIMIT/HELD na tentativa
   de enfileirar o58ºitem. Fila nunca excede57, parcial não é descartado
   para produzir sucesso; operação write original continua retida. Os
   testes separados de58linhas completas e de EOF parcial não isolam isto.
4. ReadOutcome: acrescentar matriz compacta de formas inválidas (ok de
   tipo errado, data não bytes exatos, bloco maior que o max_bytes pedido,
   ok=False com dados) e falha operacional ok=False/data vazia. Resultado
   é PORT fechado e cache/op originais retidos; nenhum feed falso.
5. Prazo global: o teste de poll tardio existente não isola o relógio que
   cruza overall entre uma colheita conhecida e o feed, ou entre a emissão
   de Act pelo modelo e o begin_act_into. Acrescentar esses dois casos
   por Clock.on_now sobre traces/status públicos: nenhuma entrega/feed
   após overall e nenhum início da ação; pending/observações verdadeiras
   preservados. Sem atributo privado ou mudança dos testes anteriores.
6. Quando o modelo termina T6 por orçamento insuficiente antes de kill,
   read/wait ainda estão vivos. Exigir HELD/retained=True e conservar os
   dois slots originais, não apenas occupied=True. Done do reator não
   atesta quietude das portas. Esta é precisão R9 de posse da revisão,
   sob delegação, não uma mudança do HostReactor ou autorização nativa.

## Respostas às ambiguidades levantadas por Claude2

- REENTRY é recusa de uso duplicado, sem callback ou avanço do reator.
  Não precisa envenenar a execução externa ativa. Falha operacional
  anterior deve permanecer pegajosa; nenhuma asserção nova de fault após
  DONE é necessária neste incremento.
- R9 acima fecha o Done precoce com operações ainda vivas: HELD e retained.
- Colher todos os slots elegíveis em cache antes de alimentar as linhas
  corresponde ao algoritmo5.1.3; manter os oráculos de FIFO/WaitOutcome.
- Act FAILED aceito e consumido pode limpar seu slot. DONE/retained=False
  após todas as operações conhecidas e saída observada não é certificado
  de cleanup físico; não mudar os três cenários apontados pelo autor.
- Adotar process de SpawnOutcome exato antes de validar ok/forma continua
  obrigatório, inclusive ok inválido e process sem forma.
- Dreno começa no primeiro evento/transição que o ativa, inclusive recibo
  NOT_SENT e kill sem exit-first. Preservar os anchors exatos do teste.
- Bytes colhidos após overall podem constar de cache verdadeiro; nenhum
  feed/model advance pode acontecer. Não impor queue count nesse caso.
-57linhas cabem na fila. Após UNKNOWN do INIT, a primeira linha{}chega ao
  reator e recusa EVENT. Manter este caso separado do58ºenqueue.

Próximo somente correção aditiva do novo teste pelo mesmo Claude2, com
Read/Edit/Write e sem comandos. Fonte da ponte continua AUSENTE. Root
relerá delta, medirá statics e RED antes de congelar.13pins/app124 e
estado16/attempt permanecem fixos. Sem Docker/PG/SQL ou efeitos nativos.
T5físico/B1/B2/D090gate2/C1/TLS/ingressos/produção continuam abertos.

## V2/V3 relidas e RED195 congelado

CLI7575 terminou0/success em134776ms; root leu todo o delta. Nenhum teste
original removido. Só3funções de teste antigas tiveram delta: tipagem da
refusal, refino None no caminho feliz e o fortalecimento R9 solicitado.
Os5novos testes parametrizados acrescentam17casos. Ficou1erro de mypy no
mapa fresh_tamper; Ruff/format passaram. Snapshot e diagnóstico preservados.

CLI1542 terminou0/success em12847ms, alterando apenas a anotação do mapa
local e o retorno. Root leu esse delta completo. V3 final:
97c26fbfd2823e288a450fdde7ca3d7919ef7a5ec4843021bc3cb98bf585f671,
76446bytes/1935linhas/49funções de teste. Ruff check/format e mypy strict
alvos3.11 e3.14 passaram. Zero escritores confirmado após cada terminal.

RED final em Windows Python3.11.3, runner QA com pilha64MiB:195coletados,
3sanidades PASS/192FileNotFoundFAIL/0erros/skips,37,843s,exit1. As192falhas
são exclusivamente ausência da ponte, sem falha de coleta. Nenhuma evidência
comportamental da ponte existe ainda. frozen-red195.json conserva o hash,
os bytes comprimidos e os resultados; logs/XML originais também foram
preservados comprimidos antes de normalizar espaço final na apresentação.

Os13arquivos protegidos e app124 foram conferidos por SHA/tamanho, intactos.
Os1215verdes anteriores continuam históricos; não foram repetidos neste
lote de teste de contrato com módulo ausente. Nenhum efeito nativo/PG/SQL.

Precisão final do relógio: R8.5 exige observação nova de now antes de feed
e antes de begin_*. Reutilizar o instante anterior do feed para iniciar
efeito ignora tempo transcorrido. Os dois testes novos isolam essa lacuna
sem impor nomes privados, timers reais ou contagem artificial de callbacks.

Sob delegação, aceito este arquivo como primeiro contrato de testes para
o futuro incremento de fonte. Não é aprovação individual do usuário nem
certificação nativa. A fonte continua AUSENTE ao fechar este lote. O teste
fica congelado; futura implementação deve ser do mesmo Claude2, somente
docs/poc/oracle9_w1_duplex_bridge.py, após conferir Git atual/zero escritor
e ler DUPLEX-DESIGN, todo DUPLEX-REVIEW/R8 e este R9/parecer. Root revisa
fonte antes de executá-la. Nenhuma autorização de efeitos físicos nasce.

O agendamento existente entregou esta retomada em10/11às19h35SP/22h35UTC,
LastResult0 e NextRun null. Nenhuma nova quota foi observada nas3chamadas,
nenhum novo job/fallback/segundo escritor foi iniciado. A demora da primeira
chamada não foi atribuída a quota ou defeito sem evidência.

O primeiro check do índice detectou CRLF nas13apresentações de evidência
geradas pelo QA. Foram normalizadas para LF, sem alterar JSON semântico,
teste ou snapshots. Saídas/XML brutos continuam nos registros comprimidos;
o diagnóstico inicial foi preservado em evidence-line-ending-review.json.
Não houve motivo para repetir pytest/estáticos sobre o mesmo teste intacto.
