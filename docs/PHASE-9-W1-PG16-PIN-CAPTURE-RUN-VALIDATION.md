# Medição nativa única dos pins — evidência pública

2026-10-31, sob delegação vigente, depois do commit2034cd4 publicado e
sincronizado. Capturadorde8f0391 aceito20331/desenho34978; comando aceito54015
com as três referências global:LASTEXITCODE aplicadas literalmente.41271 e
54015 preservam os P2 anteriores, corrigidos antes da invocação.

## Execução e fechamento

Proposta3eb3f616e3f24f3e943bd2135b0007ba invocada **uma vez**, sem argumentos,
Python nativo3.11.3/-I/-B/optimize0 via launcher do venv, no Windows PowerShell
Desktop5.1. Cwd e SHA externos fixos, ambiente somente Process filtrado/
restaurado no finally, sem exibir valores. Ferramenta terminou exit0 em7,272s
(tempo externo, não soma/limite dos samples). Não devolveu sessão pendente.

Saída observada: resumo MASKGW_PG16_PIN_CAPTURE_V1/MEASURED/categorynull,
task acima e caminho relativo; depois PIN_CAPTURE_SOURCE_UNCHANGED e
PIN_CAPTURE_EXIT_0. Stdout não contém as amostras; stderr foi descartado.
Não houve segunda invocação ou recuperação. A task e seus três arquivos
estão consumidos/imutáveis: não editar, remover ou executar novamente.

Diretório público `docs/poc/evidence/pg16-pin-cost-20261031-3eb3f616e3f2/`:

| Arquivo | Bytes | SHA-256 |
| --- | ---: | --- |
| invoked.json |255|c0f7c58b8e4751963fa4e186e78c1dec33dbe150919ce08c23228f63b61421db|
| result.json |2257|71eb429de39b51c948f139c289c1eeeb77c43100e296c5469b05d6a49470c9ca|
| capture.json |1356|d0af0f0266e0cd23b3778c77a4f36cd5f95e78e538b670a2643c41a3f397f2c9|

Capturador:de8f03910836799f90705265264e2f9fc71c878b517ff06b46c56b7150b0559d;
helper:0195b1e43353167b24f8e66606450e7beeea1e7d2daddcdeec9f6d95b9b12bd8.
Schema/canonicalidade/ASCII/duplicatas/limite/SHA13 validados no processo
antes de gravar. Conferência externa posterior somente leitura confirmou
três arquivos/tipos kind/task/programa/helper, manifesto→resultado2257bytes/
SHA exato, conjuntos13 iguais,20samples/5ciclos e max/mediana recalculados.
Marcador CAPTURE_ARTIFACTS_VERIFIED/exit0. Nenhum arquivo extra na captura.
Essa conferência não chamou o helper collect nem leu binários/config privados.

## Tempos observados, sem garantia de pior caso

Cinco ciclos intercalados; todas20amostras estão no result.json. Construção
e pins anteriores aqueceram fontes. Não é cold-cache, deadline absoluto de
filesystem nem atestação de outro ambiente/host/sistema operacional.

| Operação | Mediana (ms) | Maior observado (ms) |
| --- | ---: | ---: |
| NORMAL |194,4215|242,4909|
| CLEANUP |169,2690|222,1903|
| FINAL0 |186,0038|269,4615|
| FINAL23 |235,5727|348,7221|

Construção, uma amostra de cada: builders57,4824ms; HostContext0 255,1848ms;
HostContext23 192,2365ms;23monitores730,0127ms. Objetos reais sem start/owner/
loop/raiz operacional. O prazo de prepare3s **não foi medido**: este diagnóstico
não chama admit/prepare nem lê uma raiz de ensaio. Não chamar a soma parcial
de prova de admissão. Nenhum construtor iniciou watchdog ou heartbeat.

## Uso na composição seguinte

PIN-COST-VALIDATION contém contagens de código, não tempos fakes. Aqui existem
tempos nativos, mas não attach/CLI/rm/owner/shell. Só para base aritmética:

-6NORMAL+4CLEANUP por caso, nominal positivo, usando os maiores observados:
  6×0,2424909+4×0,2221903 = **2,3437066s/caso**;23casos=**53,9052518s**.
- A preservado:19NORMAL+24CLEANUP conservadores (clock como subconjunto
  contado por CLEANUP inteiro)=**9,9398943s**. Partida própria acrescenta
  1NORMAL=0,2424909s. Esses termos ficam fora da janela B, mas na duração total.
- Pós-B nominal:2CLEANUP globais + até20CLEANUP conservadores de restore +
  FINAL23=**5,2369087s**. Preserva o limite maior20 da revisão de entrada,
  embora a conta corrente do restore típico/capado a10polls seja menor.
- Um record ainda running pode acrescentar kill+reinspect:2CLEANUP=
  0,4443806s. Repetição de coleta pós-fire, polls e branch abort devem ser
  contados separadamente; não reaplicar a conta nominal como máximo do erro.

Esses produtos são base sem margem, não orçamento aceito. Compilação do
bounded nos caminhos PS/clock está fora dos pins medidos; pins próprios do
owner/emergência e IO/persistência/journal/join também precisam entrar.
O limite1s de pin da emergência é checado depois da leitura, não mata uma
leitura síncrona lenta. A aritmética antiga534<600 não é atualizada só por
somar esse nominal: depende de quais custos já estão dentro de cada janela.

Os23owners no teto12s somam276s antes de create/inspect/cleanup/pins; todos
os tetos não cabem emB300. A amostra T4 de rm rápido e a cauda histórica6,3s
continuam preservadas, sem extrapolar latência PG/attach não medida. P2-4
continua aberto até conta por cenário com margem e revisão. Esta medição
remove a lacuna de custo dos pins; não declara viável/segura a matriz23.

## Escopo e continuidade

Somente leitura de fontes/executáveis/configurações fixados e escrita dos
três artefatos públicos próprios. Nenhuma CLI Docker, start/stop/Desktop
observação nova, container, banco, credencial, SQL, worker ou serviço.
Não inferir estado atual do Desktop da ausência de comandos. Configuração
privada não foi copiada, hash privado/caminho/erro não foram publicados.
Oracle621 permanece inalterada. Sem revisão duplicada/quota/job/outro escritor.

## Revisão69592

Claude2 aceitou a evidência para publicação sem P1/P2. Leu os três JSON,
conferiu o conjunto13 contra o capturador, recalculou estatísticas/contas;
não executou código. Exit externo vem da medição acima, não de inferência
do revisor. Precisões incorporadas: só5samples/modo, dispersão quase1,8×,
máximo observado não é teto; Desktop/VM ativos disputarão CPU/IO na rodada;
usar margem explícita, sem extrapolar owner/attach não medidos. A/admissão
ficam fora de B. Parecer não libera matriz23 nem produção.

Orientação1125 e envelope prospectivo SHELL-BUDGET-DESIGN aceito47012 com
quatro precisões incorporadas. Conta estimada176,938915/289,0825036s e cauda
578,8375452s, todas condicionais e com incógnitas expressas; não desempenho
demonstrado. Próximo: exportador/preparador/proposta antes de rodada real.
Gateway indisponível, B1/B2/D090gate2/C1/SQL/produção continuam abertos.
