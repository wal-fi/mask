# Checkpoint para continuidade em outro local

Criado por solicitação do usuário em2026-10-30. Inclui o trabalho acumulado
após4a5e556, preservando resultados históricos e tentativas reprovadas. É
checkpoint de desenvolvimento incompleto da Fase9, não release de produção.

## Preparador parcial; retomada agendada — 2026-10-31

Após a publicação de `9e4e37e`, Claude2 iniciou `pg16_shell_prepare.py` e
atingiu a quota (CLI 82419, exit 1/API 429). O arquivo parcial tem 9.391 bytes,
SHA `b0359405`; ainda faltam testes próprios, desenho e aprovação. Não há
escritor ativo. Somente Claude2 programa, sempre Opus 5.5/esforço medium;
o assistente principal revisa e testa. A sonda em memória confirmou 16 campos,
6.959 bytes e 23 casos, FRESH/invokedFalse; não mede a admissão em 3 segundos.
A entrada exige 16 campos, corrigindo os 17 da primeira instrução deste lote.

O limite informa liberação às 21h40 de São Paulo. A tarefa existente
`Maskgw-Claude2-Resume-01a05804` foi reprogramada para uma única execução em
2026-10-31T21:45:00-03:00. Readback: Ready, NextRunTime exato, IgnoreNew e
RunLevel Limited, mesma conversa e argumentos conferidos. A mensagem exige
conferir ausência de Claude2 ativo antes de retomar. Registro confirmado,
execução futura ainda não observada; depende de máquina ligada, usuário
conectado e aplicativo disponível. Ver SHELL-PREPARE-REVIEW e
CLAUDE2-PENDING-REVIEW. Nenhuma raiz operacional, Docker, PG, SQL, worker ou
serviço criado neste lote. Fontes aceitas e medição consumida `3eb3` intactas.
Gateway indisponível; B1/B2/D090/C1/produção abertos. Registros abaixo históricos.

## Registro anterior — leitor PG16 e supervisão revisados

2026-10-31: Claude2 programou novo exportadored491c01/testes906a8cae; modelo
Opus5.5/esforço medium fixados por solicitação atual. Assistente principal é
revisor/validador.54passed/110,51s e hook independente5CLEAN/18,21s, estáticos
341/338 alvos311/314 limpos. QuatroP2/umP3 anteriores reproduzidos antes do
fix,13regressões acrescentadas pelo Claude2. Relacionados481passed/213,91s,
sem falhas/skips/deselected; revisão aprovada no componente, sem P1/P2
remanescentes. Sem escritor/revisor/Claude2 ativo/quota/job novo ou novo
Docker/PG/worker/SQL/serviço. Gateways/B1/B2/D090/C1/produção abertos. Próximo
após fechamento: preparador/estado/admissão/proposta/comando;3eb3 intacta,
consumida, não executar. Este estado substitui os registros históricos abaixo.

Após2034cd4 publicado: task3eb3f616e3f24f3e943bd2135b0007ba executada uma vez,
exit0/MEASURED/SOURCE_UNCHANGED em7,272s. Três artefatos públicos conferidos,
result2257bytes/SHA71eb429d,20samples. Root público consumido, NÃO editar ou
reexecutar. Ver PIN-CAPTURE-RUN-VALIDATION; evidência/contas base aceitas
69592; envelope prospectivo47012 aceito com quatro precisões incorporadas,
sem desempenho nativo de owner/CLI/fsync alegado. Próximo exportador23dirs,
preparador/estado/admissão/proposta/comando antes de qualquer rodada. Nenhuma
revisão ativa/CLI Docker/PG/worker/SQL/serviço/
observação nova do Desktop. Sem quota/job/outro escritor, Gateway indisponível.
Este é o estado atual; registros seguintes históricos.

Capturadorde8f0391 aceito20331/desenho34978,34próprios0,99s e426relacionados
91,17s (33da captura nessa seleção), Ruff/format339/mypy337 alvos311/314.
Comando54015 aceito após correções P2 (stderr/Stop e global:LASTEXITCODE),
parse sem executar. Task3eb3f616e3f24f3e943bd2135b0007ba/root ainda ausente,
nenhuma medição; commit antes da leitura. Sem revisão ativa/quota/job/outro
escritor ou Docker/PG/worker/SQL/serviço. Orçamento/produção ainda abertos.
Ver PIN-CAPTURE-COMMAND e PIN-CAPTURE-VALIDATION. Registros abaixo históricos.

Helper de pins0195b1e4/12028bytes aceito99073, código/fakes apenas.37focados
11,61s/399relacionados104,82s, Ruff/format339/mypy336 alvos3.11/3.14 limpos. Dois Hosts/final0/final23,
20amostras, sem captura ao importar ou efeito de root/processo/thread. Fakes
de construtores negam efeitos; contagens por A/B/collect/retry/restore separam
observado de substituído, sem usar tempos fakes. Duas regressões bool/duas
stdout IO vermelhas antes dos fixes. Ver PIN-COST-VALIDATION. Nenhuma medição
de executável/config real; próximo revisar launcher/comando e leitura única.
Sem revisão ativa/quota/job/outro escritor. Fonteafaf/8c preservadas, gates
de produção ainda abertos. PIN-COST-VALIDATION registra tetos/compile/emergência
que ainda entram na estimativa, sem promover tempo fake a medição nativa.

Próximo desenho PIN-COST-DESIGN aceito8601, seis precisões incorporadas.
Entradaafaf publicada em0e370e4. Diagnóstico ainda sem código/execução:
dois Hosts para final0/final23, quatro modos/cinco ciclos20amostras, só leitura
com schema sem privados. Construtores reais23sem start/loop/raiz materializada.
Admissão estimada por construção+final0; prepare ainda gate3s. Recusa prévia
também consome raiz sem retry/nova raiz até passar sem nova revisão. Próximo:
helper/fakes/revisão antes de comando único de leitura; orçamento continua
aberto. Nenhuma revisão ativa/quota/job/segundo escritor ou efeito nativo novo.

Continuação2026-10-31: entradaafaffad0/24081bytes aceita58487, código/fakes
somente.58próprios35,14s/362relacionados77,86s, Ruff/format336/mypy334 alvos
3.11/3.14 limpos.7256 e regressões vermelhas preservados; prova precede
passed/escritas e HELD não mantém released. Ver ENTRY-VALIDATION para nota
residual de callback externo/TCB. FonteHost8c intacta, sem raiz/comando de
execução/export/prep ou efeito nativo. Nenhuma revisão ativa/quota/job/outro
escritor. Próximo: publicar verificado e seguir orçamento/exportador, antes
de proposta nativa. Gateway e B1/B2/D090/C1/produção continuam bloqueados.

Desenho seguinte ENTRY-DESIGN aceito23065, sete precisões incorporadas antes
do código: pins transitivos/puro-final, categorias AST/identidades, foreAone,
coleta/retry único por fire/join, pré-A, sucesso23 e medidas de admissão/estado.
Host8c41605f publicado emc5cacc2. Entrada/export/prep ainda sem implementação.
Orçamento exige diagnóstico de pins revisado + estimativa por caso/margem,
incluindo hashes em cleanup/restore. Primeira matriz pode medir23 reais;
nenhuma medição nativa antecipada é inventada. Sem revisão ativa/novo job/
quota/outro escritor ou efeito nativo. Próximo: implementar entrada com fakes.

Atualização mais recente: Host8c41605f/40791bytes aceito pelo Claude2 em61196,
só definições/fakes, sem main/efeito nativo.52próprios/49,90s e Ruff/format334/
mypy333 alvos3.11/3.14 limpos, runtime sóWindows3.11.3. Recusas29625/59784
e regressões vermelhas antes dos fixes preservadas em SHELL-HOST-VALIDATION.
Pins só fontes, gate após hashes, teardown coleta todos, inspect ligado e
categorias dos19negativos conferidas. Fired sempre reprova. Nenhuma revisão
ativa/outro escritor/quota/job ou Docker/shell/PG novo. Próximo: entry/HELD,
orçamento (medir pins fora de seconds), export/prep/proposta antes de rodada.
B1/B2/D090/C1 abertos, Gateway indisponível. Fontes consumidas intactas.
Este parágrafo substitui o estado corrente das atualizações anteriores.

Atualização posterior: entrega42f7e647 foi aceita42864, com25testes próprios
incluídos em143relacionados/5,97s. Só constructor da subclasse muda: HEADER
envia prefixo≤16 (short15), demais wire/chunks intactos. Oráculos/prazos/IO
inalterados; metadata não prova recepção. Fonte pinada separadamente do owner
base no futuro host, sem reescrever manifesto8906. HOST-DESIGN foi revisto2192
e as oito precisões foram incorporadas; host ainda sem código nesta atualização.
Store/Watchdogs preparados antes de A, todos armados com mesmo Bstart;
join→heartbeat→metadata antes de ativar próximo. Gate de CLI/Intent/owner por
record, artefatos case-NN e pastas watch-NN, exit CLI vs State0/42. B300 é
meta típica fail-closed; margem com join dentro de B passa a534<600.
Últimos estáticos: Ruff/format333/mypy strict332 alvos3.11/3.14; runtime só
Windows3.11.3. Nenhum Docker/shell/seed privado/raiz operacional novo.

Esta seção substitui o estado corrente dos registros históricos abaixo.
Publicações de referência:486481f (sonda pública), aed24fb (reader),7d42a49
(owner),8a8d063 (perfil),270eaad (posse). O fechamento do watchdog integra
este checkpoint; confirmar HEAD/origin/ahead/behind pelo Git, sem presumir
hash autorreferente neste documento.

Sonda pública PG16 task81e72756/rootc3a916a7 terminou exit0/PUBLIC_VERIFIED,
revisão factual aceita. PG16.15/Alpine3.24.1/UID70,12checkpoints119515ms,
owner/CID/volumes recolhidos;17volumes preservados.50fontes/77312bytes retidas
no Temp desta máquina; somente summary/transport derivados estão no Git.
Não transportar brutos ou reexecutar fontes/root/script consumidos. Resultado
não mede servidor PG, SQL, segredo ou Gateway. Ver PUBLIC-RUN-VALIDATION.

Componentes novos do leitor, ainda sem execução shell/Docker:

| Componente | SHA da fonte | Revisão final | Gate próprio/relacionado |
| --- | --- | --- | --- |
| pg16_shell_reader.py | efe69a79 |32442|30/408 |
| pg16_shell_owner.py | d6718800 |60994|33/168,1 unidade nativa desmarcada |
| pg16_shell_profile.py |8906e846|28829|55/205 |
| pg16_shell_cleanup_policy.py |96e8a4c|35578|37/117 |
| pg16_shell_watchdog.py |cf6634da|74378|33/122 |
| pg16_shell_delivery.py |42f7e647|42864|25/143 |

São seleções sobrepostas, não somar. Validações SHELL-*-VALIDATION preservam
falhas/regressões: NUL final no desenho, L1 de callbacks, Mounts malformados,
Store não monotônico e ordem de __eq__. A unidade histórica nativa de pipes
incluída por engano falhou no sandbox/WinError5; não foi elevada nem repetida.
Nas seleções de fakes que incluam esse arquivo, excluir explicitamente:

    -k 'not test_pinned_native_windows_pipe_handle_has_explicit_closed_state'

Estáticos mais recentes: Ruff/format332/mypy strict331 (alvos3.11/3.14),
runtime apenas Windows3.11.3. Helpers docs/poc têm check E9/F63/F7/F82,
não alegar mypy strict dos helpers. Get-Process confirmou DesktopOff em
2026-10-30T18:05:18.9591291Z, observação pontual. Nenhum job novo, revisão
ativa ou segundo escritor. Limite transitório do aprovador OpenAI foi
resolvido; não houve quota do Claude2 medida neste lote.

Próximo incremento seguro: desenho do coordenador público do leitor,
classificação fechada dos comandos, entrega dos negativos antes da rodada,
Store/Watchdog por caso e CID com Bstart global. check_snapshot precede
publish; próximo caso somente após CLI/pumps/handles/ticket/ausência/volumes/
release positivos e join; fired aborta tudo. Propagação real do exit42 deve
concordar com inspect;12s do host não vira DEADLINE esperado do leitor.
Depois vêm exportador próprio, entrada/preparador/proposta/comando exatos e
revisão antes de um ensaio. Não usar logger/exportador público com segredos.

**Gateway continua indisponível.** SQL PGWire recusada; B1 fim a fim/B2/
D090gate2/C1/produção não fechados. Oracle9.8 candidata621 inalterada. Destino
continua Docker desta máquina; pins/daemons/imagens/Temp não são portáveis
por inferência a outro computador. Código/evidência públicos estão no Git;
arquivos pessoais .codex/.claude/stackdumps/systeminfo permanecem excluídos.

## Continuidade posterior ao checkpoint81ead94

Exportador95f09bbb e preparador02d1 implementados e aceitos em55166/94684.
378 testes conjuntos passaram em52,39s, estáticos326 limpos, só fakes. Próximo
atual: proposta exata e revisão antes de materializar ou executar a sonda.
Nenhuma raiz operacional/PG/SQL/serviço novo. Brutos continuam fora do Git.

Entrada pública PG16a6089275 implementada e aceita pelo Claude2 (32225),
com319 testes conjuntos aprovados em43,26s; condição do parecer atendida.
Estáticos324 limpos, só fakes; nenhuma execução PG16 ou serviço ativados.
Próximo: exportador S1 próprio que retém local-* e baseline completa, depois
preparador/proposta/estado/raiz/comando revisados antes de uma rodada única.
Os contratos de HELD e diagnóstico constam em PUBLIC-ENTRY-VALIDATION.

Incremento de entrada commitado emf51d63a; clone novo autocrlftrue confirmou
698/698 arquivos sem diferenças, com entradaa6089275 preservada. Prova em
`docs/poc/evidence/checkpoint-entry-portability-20261030/verification.json`.
A publicação e o HEAD mais recente devem ser conferidos pelo Git. Novas
medições continuam só de fakes/bytes, sem iniciar serviço ou banco.

## Estado no checkpoint81ead94

- Destino aceito: Docker local nesta máquina, Oracle Linux9.8 sobre WSL2.
  Não presumir esse mesmo destino, daemon, imagens, pins ou credenciais em
  outra máquina. Confirmar o novo ambiente antes de efeitos nativos.
- Último laboratório real: T4v2/task42d363a1, exit0, sete owners liberados,
  sete CIDs removidos, Desktop restaurado Off; transporte3a274347 aceito39884.
  Fontes/raízes consumidas não podem ser alteradas ou reexecutadas.
- Núcleos B1/snapshot, resultado tipado/encoder/receiver, job/worker privado,
  guard Linux e instalação Oracle possuem evidências próprias em docs/.
  Não são integração fim a fim ou permissão operacional de SQL.
- PG16 público: perfilfe2f/owner a02f/adapterf1d9/volumes6e38 e watchb868/
  emergência54cc aceitos em revisões próprias. Novo coordenador7275c8ae
  aceito10847 após correções,39 testes simulados aprovados. Sem entrada,
  exportador, preparador, estado, raiz ou execução PG16 novos.
- B1 fim a fim/B2/D090gate2/C1 continuam abertos, SQL PGWire continua recusada.
  Gateway indisponível para teste IDE/MCP/Admin ou produção. Nenhum banco
  existente ou credencial antiga de aceitação deve ser utilizado.

## Próximo incremento registrado em81ead94 (histórico)

Implementar entrada PG16 pública sobre o coordenador aceito, com driver que
retém loop/owners em HELD e captura falha de reconciliação no restore como
categoria fechada, sem Desktopstop nem falsa interrupção do runner. Depois,
exportador S1 próprio (retém todos `local-*` e baseline completa), preparador,
proposta de estado/raiz/comando e revisão antes de uma única execução nativa.
Somente ferramentas/versões/UID/tmpfs públicos, sem initdb/SQL/seed privado.
Leitor shell e laboratório privado PG16 são passos posteriores com gates próprios.

As instruções de autonomia e de revisão pelo Claude2 continuam em AGENTS.md.
Não iniciar segundo escritor nem reexecutar tentativas históricas. A revisão
mais recente está em docs/CLAUDE2-PENDING-REVIEW.md; não há quota/job ativo.
Não pedir novas aprovações por lote para o escopo já delegado.

## Portabilidade e dados locais

O Git contém código/testes/documentos e evidência pública exportada. Imagens
Docker locais, wheels/RPMs no Temp, ambientes Python/Node, raízes de laboratório,
credenciais e dados privados não estão incluídos. Referências históricas a
caminhos/pins Windows são fatos de medição, não configuração pronta em outra
máquina. Preparar novo ambiente isolado e reprovar pins divergentes; nunca
reduzir verificações só para conseguir executar.

`.gitattributes` estabelece preservação de bytes exatos em docs/poc, deploy,
pyproject.toml e fontes Python src/tests, inclusive CRLF já medido. A comparação
do índice encontrou várias fontes históricas CRLF, além de postgres.py/result.py;
por isso todas as fontes Python usam preservação exata, sem normalização.
O objetivo é impedir que core.autocrlf altere os hashes; a segunda verificação
por clone novo confirmou os bytes no escopo abaixo. Nenhuma fonte consumida foi
renormalizada. Fixtures de tests também preservam bytes exatos. Configuração
.codex/.claude local, stackdumps e systeminfo ficam fora
do checkpoint e são preservados no disco.

Varredura dos candidatos encontrou só três URLs sintéticas nos testes de
recusa de proxy/URL. Nenhuma chave privada/token/credencial real detectada;
essa varredura é limitada por padrões e não equivale a DLP. Novas saídas do
daemon não foram coletadas: a correção de minimização foi medida só por fakes.

Seleção final dos sete componentes PG16 públicos:257passed em16,70s, só fakes.
Estáticos atuais: Ruff e mypy strict alvos3.11/3.14 em323 arquivos limpos;
runtime medido Windows3.11.3. A suíte PostgreSQL integral e os pacotes de
incrementos anteriores mantêm seus resultados nas evidências; não foram
reexecutados para este fechamento de checkpoint. Nenhuma alegação de
validação integral nova ou de disponibilidade de produção.

## Primeira verificação por clone novo

Commit7875dc8 clonado localmente em diretório novo, sem hardlinks, com
core.autocrlf=true:693/694 arquivos de fonte/evidência iguais, pyproject917fe735
e fonte histórica CRLF preservados. Um fixture JSON (phase7-ui-off.json)
foi convertido por autocrlf; rodada reprovada preservada em
`docs/poc/evidence/checkpoint-portability-20261030/verification.json`.
Acrescentada proteção de bytes para tests/fixtures, sem editar o fixture;
nova verificação concluída abaixo. Não é teste de execução do app.

## Segunda verificação por clone novo — aprovada

Commit5dc1f6a clonado em outro diretório novo, sem hardlinks, com
core.autocrlf=true: **695/695 arquivos comparados, zero diferença de bytes**.
Escopo: docs/poc, deploy, src, tests e pyproject.toml rastreados naquele
commit, incluindo a primeira medição reprovada. Fonte histórica CRLF,
pyproject917fe735, fontes e fixtures preservados. Evidência pública em
`docs/poc/evidence/checkpoint-portability-20261030-b/verification.json`.
Não houve execução de aplicativo, Docker, banco ou laboratório nativo.
As duas cópias locais de verificação estão no Temp, fora do Git; não são
instalações nem ambientes operacionais. A cópia dos bytes não certifica
o ambiente externo de outra máquina, conforme os limites acima.

Rerevisão64823, sessão51ea0d85: metadados e prova do clone aceitos para
checkpoint incompleto, sem bloqueador e sem declarar release. Depois de
5dc1f6a mudaram somente registros/documentos de fechamento, sem alterar
fontes executáveis, fixtures, atributos ou os bytes medidos.
