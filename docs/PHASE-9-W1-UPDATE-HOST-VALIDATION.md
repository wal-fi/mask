# W1 host — validadores puros, sem efeitos

2026-10-27, sob delegação. Implementação parcial do desenho
`PHASE-9-W1-UPDATE-HOST-PLAN.md`: construtores e validadores em
`docs/poc/oracle9_w1_prepare.py`. Nenhum coordenador, main, DockerCLI,
Desktop, instalação, sonda Linux ou serviço foi executado neste incremento.

## Contratos implementados

- Duas cópias privadas da policy histórica, admitidas por SHA; somente cinco
  funções exportadas. A cópia nova altera por identidade exclusivamente
  PAYLOAD_SHA e MANIFEST_SHA. A original conserva os metadados antigos.
  Isso delimita o chamador confiável; não constitui sandbox contra introspecção.
- Bootstrap verifica os bytes descomprimidos do payload566c46a8 antes de
  compilar. Mede a linha CreateProcess inteira com list2cmdline, incluindo
  executável/contexto/args; recusa acima de26000 caracteres antes de efeitos.
- Origem87871290 e seus três layers exatos. Config do candidato deve ser
  idêntico ao da origem, salvo três valores de labels; nenhuma normalização
  implícita de Cmd, chaves extras, ENV ou volumes. Labels de CID também exatos.
- Diff limitado, paths canônicos, ancestrais C fechados, atestação nova A,
  cinco módulos novos A e RECORD A/C obrigatórios. D somente para diretório
  comprovadamente idêntico nos snapshots. Sem stash, inputs, tmp ou escape.

## Regressão antes da correção

Uma entrada repetia o mesmo path de RECORD com ações C e A. O teste novo
falhou primeiro: a implementação admitia linhas diferentes para um mesmo
path. O conjunto agora guarda paths; toda duplicata é recusada. Rodada
anterior:1 falha/27 aprovados; após correção:28/28 aprovados.

## Gates medidos

Python nativo Windows3.11.3, somente fakes/arquivos públicos locais:

- Focados:28 aprovados.
- Relacionados (prepare/update/context/offline/app-wheel/install-context/
  clock/freshness):259 aprovados,1 skip de symlink preexistente,14,69s.
- Ruff check/format e mypy strict3.11/3.14:296 arquivos src/tests limpos.
  Helper puro:lint E9/F63/F7/F82 e format limpos (não alegar tipagem do helper).

Hashes submetidos à revisão:

- prepare:7540b7bff5072013cb26613878760cb68e61c3269ab9a842a43c630ead1040cc
- teste:e539459abea7c03633fef6072ef669f22dcf21753c9fdf4e6424819173151feb

Payload566c46a8, contexto d4d4b29b e wheel6b63f239 permanecem congelados.
Não há evidência nova de prefix instalado, W1/PG16, B-1/B-2/D-090/C1,
SQL ou produção. Desktop continua Off; sem commit/push/job ou outro escritor.

## Revisão dos builders e implementação do coordenador

Claude2 aceitou7540b7bf como insumo fixo, com uma exigência antes de B:
recusar Config inesperado da base ainda no preflight. O teste com Hostname,
Domainname, Cmd vazio e label extra falhou primeiro (4 falhas/11 aprovados)
e passa após a conferência exata no coordenador. A fixture de6chaves/4labels
é expectativa a conferir; não é evidência nova de inspect real.

O coordenador agora está em `docs/poc/oracle9_w1_run.py`, separado do builder
congelado. Não houve execução real. Fakes exercitam o ciclo completo, nove
observações, boot/idade, preservação de Desktop alheio, identidade PID/FILETIME
exata, restauração pré-B sem gate de idade e ausência observada após stop.
Um primeiro teste revelou espera10s desnecessária antes do preflight: mover
o cálculo da espera residual para depois dele permite os tetos de sucesso
sem aumentar300s/30s. Custos efetivos extras continuam podendo recusar.

Fakes de B exercitam update+sonda, intent antes de create e commit, cópia
context/., atestação nova/delta L1/diff L3, criação ambígua ou ausente,
processo ainda running, recusa de produto, inputs não removidos, atestação
adulterada, diff inesperado, commit incerto, falha da sonda e cleanup incerto.
Não substituem filesystem/records/pip ou controle de processo Linux reais.
Os primeiros3 vermelhos da matriz B vieram do fake que ignorava filtro id
no ps; ele foi corrigido para responder só ao CID consultado, sem mudar o
código do coordenador.30/30 passaram nessa rodada; novos gates abaixo.

### Rodada do coordenador submetida à revisão

- Focados:39 aprovados,12,66s.
- Relacionados (10 arquivos, incluindo a policy histórica com fakes):
  330 aprovados,1 skip de symlink preexistente,28,33s.
- Ruff check src/tests e mypy strict3.11/3.14:297 arquivos limpos.
- Format src/tests+coordenador:298 arquivos conformes; lint do coordenador
  E9/F63/F7/F82 limpo. git diff --check limpo (avisos LF→CRLF preservados).
- Coordenador:986ae949d2df30ffed09871fe1c595d68fd75d7ded954088ca32e04fc6bf198e,
  39217 bytes. Teste:2ccb5866552dc1194aee95b6f99c0c1dc623a913534d9f5a4e8433c9829879fb.

Somente Windows3.11.3 com fakes/arquivos públicos. Nenhuma invocação de main,
DockerCLI, Desktop, clock real, pip ou laboratório Linux nesta rodada.
O estado e o comando reais ainda não foram preparados/invocados. Revisão
do código não substitui revisão do estado/comando antes de A.

## Primeira revisão do coordenador: rejeitada, correções locais

Claude2 encontrou dois bloqueadores no986ae949. A rejeição foi preservada:

- B1: start herdava as13chaves do CLI. Agora tem ambiente próprio com as34
  chaves Windows já revisadas no HELD-RUN-PLAN, sem mutação do ambiente host,
  sem variáveis de ferramenta/secret e log somente dos nomes presentes.
- B2: rollback exigia Config exato da imagem que podia estar sendo recusada
  por Config divergente. Agora persiste commit-result.json antes de validar;
  para remover somente a tag própria, confere RepoTags exato, ID conhecido
  quando disponível,3labels próprios e layers origem+um. Não relaxa aceitação.

Os dois testes novos falharam antes do fix e passaram depois. Cobertura de
commit incerto inclui agora TimeoutError após a imagem existir; tag de terceiro
continua preservada. O host também reconfere os5 módulos W1 contra a projeção,
mesmo quando stdout e atestação concordam; contraprova falhou antes do fix.

Finding próprio adicional: o caminho calculado do Desktop apontava para o
binário interno resources/Docker Desktop.exe (hash d214a527), em vez do app
raiz f3100322. Um pins() offline recusou antes de qualquer ação; não foi
mudança do software. Teste do path falhou primeiro, cálculo corrigido.

R1: após esse fix, custo offline real de pins completo em3 medições:
0,398/0,299/0,301s; cleanup:0,141/0,183/0,154s. Nenhum DockerCLI/ação Desktop.
Artefato oracle9-w1-pin-cost-20261027.json/SHA604e186e mede a8d19615; a função
pins permanece igual no delta posterior. Mantidos os checks por chamada,
pois ficaram abaixo de1s; não há garantia para lentidão futura e o portão
de idade real continua recusando excesso. Nenhum teto aumentado.

R2: watchdog600s **por execução ativa**, separado do CLI300s, rearmado para
instalação e sonda só depois de recolher a thread anterior. Fronteiras
599,999/600s simuladas e duas execuções com eventos distintos verificadas.
Nenhum teto global600s é alegado para toda a fase B.

Delta761915e29c8cc69441ad2a65af613bdfe46191960c0568a42387ec3543c737a5:
47 testes focados (contagem na seleção),338 relacionados aprovados/1 skip
symlink preexistente,33,02s. Ruff/check/format e mypy3.11/3.14 src/tests
permanecem limpos nos escopos acima. Teste7fac8177. Nenhuma invocação de main,
sampler Windows/CIM, Desktop, Docker ou Linux; revisão do delta pendente.

## Código aceito e estado/comando preparados, ainda sem A

Claude2 aceitou761915e2 como código, B1/B2 corrigidos e R1/R2 resolvidos.
Recomendação N1 incorporada: START_COMMAND remove no próprio PowerShell
as chaves fora da allowlist antes de Start-Process e devolve nomes realmente
presentes junto de identity. Host confere nomes (case-insensitive Windows,
sem duplicatas), sem registrar valores. Fixture recusa PSModulePath, secret
e nomes duplicados. Parser PowerShell5.1 admitiu start/processes:0 erros.
Um if vazio deixado durante a edição gerou48 erros de import de teste;
removido antes de qualquer invocação. Rodada final:48/48,14,57s; Ruff/check
e mypy3.11/3.14 em297arquivos limpos. Não é finding de runtime medido.

Coordenador final4bc0b083c9df44edd2aa532de7f43cf9f7f9f5a581edb267d8414d21057fd753,
43615bytes; testefb6ce119. Payload566c e builders7540 imutáveis.
Root próprio preparado, não invocado:
`C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-w1-run-20261027-5cb698ceef7c4414a30d96e2667d0e58`.
Task8c0680599bcc4a2db241bbfbcf6669dc; raiz contém somente attempt.json FRESH,
invokedfalse/SHA d43f3b2a62fa9f97979c96d3321184a3537b3732e6315956ba038bf02a707725.
Espelho de preparação ef0bff7a em oracle9-w1-run-preparation-20261027.json.
Seis bibliotecas capturadas e cinco pins externos conferidos offline; nenhum
DockerCLI. Medidas reais das listas:install24016/margem1984 e probe23985/
margem2015. Binário .venv Python3.11.3 bfff5171. Snapshot de processos Docker:
zero. Estado real ainda será rechecado por main, sem ancorar clock na preparação.

Comando exato em oracle9-w1-run-command-20261027.ps1: checks de SHA do Python,
programa e attempt, inventário fresco de root, uma invocação -I-B/main, retorno
do exit sem ocultá-lo. Não foi executado. Aguarda revisão N1/estado/comando;
essa revisão é separada do aceite do código anterior e não libera SQL/produção.
